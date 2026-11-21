"""Check identified upgrade pairs with the pinned or current class reader and native verifier.

Source preparation is shared across builds. A successful preparation contains the original source
digest and ordered, content-checked client and dependency JARs. Run this command in the queue.
"""

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from types import SimpleNamespace

from pin import OPERATOR, ROOT, digest

sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import runtime, upgrade_claims


HERE = Path(__file__).resolve().parent
V0 = json.loads((HERE / "v0.json").read_text())


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n")


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args])


def dependency_file(case, side):
    group, artifact = case["dependency"].split(":")
    version = case["versions"][side]
    return Path(*group.split("."), artifact, version, f"{artifact}-{version}.jar")


def failure(output):
    clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", output)
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    lines = [line for line in lines if line not in ("[ERROR]", "[WARNING]", "[INFO]")
             and not re.search(r"Re-run Maven|full stack trace|For more information|Help [0-9]|Picked up JAVA_TOOL_OPTIONS", line)]
    causes = [line for line in lines if re.search(r"non-resolvable|could not|cannot|not found|failed to|error:|exception|unsupported|unverifiable|fatal", line, re.I)]
    return (causes or lines or ["no diagnostic was emitted"])[:5]


def run(cmd, cwd, env, seconds):
    try:
        result = subprocess.run(cmd, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=seconds)
        return result.returncode, result.stdout.decode(errors="replace")
    except subprocess.TimeoutExpired as exc:
        return 124, (exc.stdout or b"").decode(errors="replace") + f"\nTimed out after {seconds} seconds."


def source_side(case, side, repo):
    commit = case["revisions"][side]
    if git(repo, "rev-parse", commit + "^{commit}").decode().strip() != commit:
        raise ValueError("source revision does not identify a commit")
    blob = git(repo, "show", f"{commit}:{case['source']}")
    if hashlib.sha256(blob).hexdigest() != case["sourceSha256"]:
        raise ValueError("source bytes do not match the selected original caller")
    return commit


def snapshot(repo, commit, src, temp):
    # Git archives are data. Refuse links that escape the new, empty source tree.
    with tempfile.TemporaryFile(dir=temp) as archive:
        subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", commit], stdout=archive, check=True)
        archive.seek(0)
        with tarfile.open(fileobj=archive) as stream:
            stream.extractall(src, filter="data")


def make_jar(classes, dest):
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as jar:
        for file in sorted(classes.rglob("*.class")):
            entry = zipfile.ZipInfo(file.relative_to(classes).as_posix())
            jar.writestr(entry, file.read_bytes(), compress_type=zipfile.ZIP_DEFLATED)


def classpath_rows(files):
    return [{"file": str(f.resolve()), "sha256": digest(f)} for f in files]


def prepare_side(case, side, repo, args, jdk, out):
    commit = source_side(case, side, repo)
    record = {"commit": commit, "sourceSha256": case["sourceSha256"], "subjectJdk": jdk.name}
    cached = out / "prepared.json"
    if cached.is_file():
        saved = read(cached)
        if (saved.get("commit") != commit or saved.get("sourceSha256") != case["sourceSha256"] or
                any(digest(r["file"]) != r["sha256"] for r in saved["classpath"])):
            raise ValueError("the reusable original preparation changed")
        return saved
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.work, prefix="compile-") as temporary:
        temp = Path(temporary)
        src = temp / "source"
        snapshot(repo, commit, src, temp)
        env = dict(os.environ, TZ="UTC", LC_ALL="C.UTF-8", JAVA_HOME=str(jdk),
                   PATH=str(jdk / "bin") + os.pathsep + os.environ["PATH"],
                   JAVA_TOOL_OPTIONS=f"-Djava.io.tmpdir={temp}")
        env["MAVEN_OPTS"] = (f"-Xmx768m -Djava.io.tmpdir={temp} -Dmaven.artifact.threads=1 "
                             "-Daether.connector.basic.threads=1 -Daether.metadataResolver.threads=1")
        cp_file = temp / "compile-classpath"
        maven = args.maven8 if case["origin"].startswith("CompSuite") and args.maven8 else args.maven
        argv = [str(maven), "-B", "-q", "-T", "1", "-f", str(src / case["modulePom"]),
                "-Dmaven.repo.local=" + str(args.maven_cache), "-DincludeScope=compile",
                "-Dmdep.outputFile=" + str(cp_file),
                "org.apache.maven.plugins:maven-dependency-plugin:3.6.1:build-classpath"]
        # Retroactive HTTP mirrors or credentials from this account are not inputs to an original POM.
        settings = temp / "settings.xml"
        settings.write_text("<settings><mirrors><mirror><id>central</id><mirrorOf>*</mirrorOf>"
                            "<url>https://repo.maven.apache.org/maven2</url></mirror></mirrors></settings>\n")
        argv[1:1] = ["--settings", str(settings)]
        with (args.maven_cache.parent / "resolution.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            code, log = run(argv, src, env, args.resolve_seconds)
            runtime_cp = temp / "runtime-classpath"
            if code == 0 and cp_file.is_file():
                argv[argv.index("-DincludeScope=compile")] = "-DincludeScope=runtime"
                argv[argv.index("-Dmdep.outputFile=" + str(cp_file))] = "-Dmdep.outputFile=" + str(runtime_cp)
                code, log = run(argv, src, env, args.resolve_seconds)
        if code or not cp_file.is_file() or not runtime_cp.is_file():
            return dict(record, stage="original Maven classpath", exit=code, diagnostic=failure(log))
        deps = [Path(s) for s in cp_file.read_text().strip().split(os.pathsep) if s]
        runtime_deps = [Path(s) for s in runtime_cp.read_text().strip().split(os.pathsep) if s]
        expected = args.maven_cache / dependency_file(case, side)
        if expected not in runtime_deps:
            return dict(record, stage="original classpath", diagnostic=["The selected module did not resolve the changed coordinate on its runtime classpath."])
        source = src / case["source"]
        owner = case["entry"].split("#")[0]
        root = source
        for _ in owner.split("."):
            root = root.parent
        classes = temp / "classes"
        classes.mkdir()
        argv = [str(jdk / "bin/javac"), "-g", "-parameters", "-proc:none", "-encoding", "UTF-8",
                "-classpath", os.pathsep.join(map(str, deps)), "-sourcepath", str(root), "-d", str(classes), str(source)]
        code, log = run(argv, src, env, args.compile_seconds)
        if code:
            return dict(record, stage="original source compilation", exit=code, diagnostic=failure(log))
        jar = out / "client.jar"
        make_jar(classes, jar)
        record.update(stage="artifacts ready", scope="original caller and javac-discovered source dependencies",
                      compiledClasses=len(list(classes.rglob("*.class"))), compilerSha256=digest(jdk / "bin/javac"),
                      compilerClasspathSha256=[digest(f) for f in deps], classpath=classpath_rows([jar, *runtime_deps]))
        write(cached, record)
        return record


def reader(build, work):
    path = "examples/tools/targets/runtime_jar.py"
    if build == "V0":
        saved = work / "v0-runtime_jar.py"
        raw = saved.read_bytes() if saved.is_file() else git(ROOT, "show", f"{V0['revision']}:{path}")
        if hashlib.sha256(raw).hexdigest() != "2d69c271b84783a11b102dcacda4a301879c93b2438b53a91cc66de3ea370b61":
            raise ValueError("V0 class reader differs from its frozen bytes")
    else:
        raw = (ROOT / path).read_bytes()
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader("corpus_class_reader", loader=None))
    exec(compile(raw, path, "exec"), module.__dict__)
    return module, hashlib.sha256(raw).hexdigest()


def screen(case, inputs, build, checker, args):
    parser, reader_sha = reader(build, args.work)
    report = {"id": case["id"], "build": build, "operator": OPERATOR, "entry": case["entry"],
              "observer": case["observer"], "revisions": case["revisions"], "result": "open",
              "readerSha256": reader_sha, "checkerSha256": digest(checker), "sides": {}}
    paths = {}
    caller_bytes = {}
    owner, method = case["entry"].split("#")
    for side, prepared in inputs.items():
        evidence = {k: v for k, v in prepared.items() if k != "classpath"}
        report["sides"][side] = evidence
        if prepared.get("stage") != "artifacts ready":
            report.setdefault("firstBlocker", prepared.get("stage"))
            continue
        cp = prepared["classpath"]
        evidence["orderedSha256"] = [r["sha256"] for r in cp]
        paths[side] = [Path(r["file"]) for r in cp]
        try:
            data = parser.read_class(paths[side][0], owner.replace(".", "/"))
            if not data:
                raise ValueError("the original artifact does not contain the selected caller class")
            caller_bytes[side] = data
            evidence["callerClassSha256"] = hashlib.sha256(data).hexdigest()
            names = sorted(d for n,d in parser.methods(data) if n == method)
            if not names:
                raise ValueError("original class does not declare " + method)
            evidence["descriptors"] = names
        except (ValueError, KeyError, OSError) as exc:
            evidence["diagnostic"] = [str(exc)]
            report.setdefault("firstBlocker", "original caller declaration")
    if "firstBlocker" in report:
        return report
    env = dict(os.environ, JAVA_HOME=str(args.verifier_jdk), TZ="UTC", LC_ALL="C.UTF-8",
               JAVA_TOOL_OPTIONS="-Djava.io.tmpdir=" + str(args.work),
               JVMCONTRACT_BITWUZLA=str(Path.home() / "tools/bitwuzla/current/lib/x86_64-linux-gnu/libbitwuzla.so.0"),
               JVMCONTRACT_SOLVER=V0["native"]["solver"], PATH=str(args.verifier_jdk / "bin") + os.pathsep + os.environ["PATH"])
    if build != "V0":
        env["JVMCONTRACT_JAR_RELEASE"] = runtime.runtime_jdk.identity(args.verifier_jdk)["feature"]
    with tempfile.TemporaryDirectory(dir=args.work, prefix="checker-") as td:
        work = Path(td)
        originals = {s: [SimpleNamespace(path=cp[0].name, sha256=inputs[s]["classpath"][0]["sha256"])]
                     for s, cp in paths.items()}
        sides = {s: (cp[0].parent, None, originals[s]) for s, cp in paths.items()}
        feature = int(env["JVMCONTRACT_JAR_RELEASE"]) if build != "V0" else None
        bindings = {side: {"entry": case["entry"], "classSha256": row["callerClassSha256"]}
                    for side, row in report["sides"].items()}
        directories = runtime._class_dirs(sides, work, work, {s: [{"path": a[0].path}] for s,a in originals.items()},
                                          feature, bindings if feature is not None else None)
        targets = [case.get("checkerTarget", case["entry"])]
        if build == "current":
            overloads = upgrade_claims.named_overloads(caller_bytes["old"], caller_bytes["new"], method)
            report["declarations"] = overloads
            targets = list(dict.fromkeys(runtime.java_target(case["entry"] + desc) for desc in overloads["common"]))
        if not targets:
            report["firstBlocker"] = "no common original overload"
            return report
        results = []
        first = time.monotonic()
        for index, target in enumerate(targets):
            remaining = args.check_seconds - (time.monotonic() - first)
            if remaining < 1:
                results.append({"target": target, "firstBlocker": "shared overload time budget", "exit": 124})
                continue
            seconds = max(1, int(remaining / (len(targets) - index)))
            # Single-target runs retain their full configured limit.
            if len(targets) == 1:
                seconds = args.check_seconds
            stage = work / ("overload-" + str(index))
            stage.mkdir()
            cmd = [str(checker), "equivalence", "--before", str(work / directories["old"]["dir"]),
                   "--after", str(work / directories["new"]["dir"]), "--engine", "native", "--gaps", "strict",
                   "--target", target, "--timeout", str(seconds), "--work", str(stage), "--json"]
            for side, flag in (("old", "--before-classpath"), ("new", "--classpath")):
                for jar in paths[side][1:]:
                    cmd.extend([flag, str(jar)])
            started = time.monotonic()
            code, output = run(cmd, ROOT, env, min(seconds + 2, max(1, remaining)))
            output = output.replace(str(args.work), "$WORK").replace(str(args.maven_cache), "$MAVEN_REPOSITORY")
            item = {"target": target, "exit": code, "seconds": round(time.monotonic() - started, 3),
                    "outputSha256": hashlib.sha256(output.encode()).hexdigest()}
            try:
                value = json.loads(output[output.index("{"):output.rindex("}") + 1])
                item["outcome"] = value
                item["firstBlocker"] = value.get("problem") or "review native outcome and original observer"
                if value.get("verdict") in ("verified", "violation"):
                    item["scopeReviewRequired"] = True
            except (ValueError, AttributeError):
                item["diagnostic"] = failure(output)
                item["firstBlocker"] = "native time budget" if code == 124 else "native checker"
            results.append(item)
        report["native"] = results[0]
        report["firstBlocker"] = results[0]["firstBlocker"]
        if len(results) > 1:
            report["nativeOverloads"] = results
            report["firstBlocker"] = "review the recorded exact overloads"
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case", action="append", default=[])
    ap.add_argument("--set", choices=("main","transfer"))
    ap.add_argument("--build", choices=("V0", "current"), action="append", required=True)
    ap.add_argument("--repositories", required=True, type=Path, help="JSON mapping case IDs to original local Git repositories")
    ap.add_argument("--work", type=Path, required=True, help="reusable input preparations, outside the checkout")
    ap.add_argument("--maven-cache", type=Path, required=True)
    ap.add_argument("--maven", type=Path, default=Path(shutil.which("mvn") or "mvn"))
    ap.add_argument("--maven8", type=Path)
    ap.add_argument("--verifier-jdk", type=Path, default=Path.home()/".sdkman/candidates/java/21.0.13.0+9-tem")
    ap.add_argument("--historical-jdk", type=Path, default=Path.home()/".sdkman/candidates/java/8.0.512.0+9-tem")
    ap.add_argument("--checker", type=Path, help="current checker; V0 always uses its frozen binary")
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--resolve-seconds", type=int, default=180)
    ap.add_argument("--compile-seconds", type=int, default=60)
    ap.add_argument("--check-seconds", type=int, default=90)
    a=ap.parse_args()
    a.work=a.work.resolve(); a.maven_cache=a.maven_cache.resolve()
    if a.work.is_relative_to(ROOT) or a.maven_cache.is_relative_to(ROOT):
        ap.error("put compilation and the Maven cache outside the checkout")
    a.work.mkdir(parents=True,exist_ok=True)
    a.maven_cache.mkdir(parents=True,exist_ok=True)
    repos=read(a.repositories);cases=read(HERE/"corpus.json")["cases"]
    chosen=[c for c in cases if (not a.case or c["id"] in a.case) and (not a.set or c["set"]==a.set)]
    if not chosen or set(a.case)-{c["id"] for c in chosen}:
        ap.error("unknown case or empty selection")
    checkers = {"V0": Path.home()/".cache/in-the-loop/external-upgrades"/V0["sha256"]["jvmcontract"]/"jvmcontract",
                "current": a.checker or Path(os.environ.get("JVMCONTRACT", ROOT/"lib/target/test-fast/jvmcontract"))}
    for build in a.build:
        checker = checkers[build]
        if not checker.is_file() or (build == "V0" and digest(checker) != V0["sha256"]["jvmcontract"]):
            ap.error("the selected checker is unavailable or differs from the V0 pin")
    for case in chosen:
        files = {build: a.output/build/(case["id"]+".json") for build in a.build}
        if any(f.exists() for f in files.values()):
            raise SystemExit("refusing to replace an existing first result for "+case["id"])
        start=time.monotonic(); cachedir=a.work/case["id"];cachedir.mkdir(exist_ok=True)
        with (cachedir/"prepare.lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            inputs={}
            for side in ("old","new"):
                try:
                    jdk=a.historical_jdk if case["origin"].startswith("CompSuite") else a.verifier_jdk
                    prepared=prepare_side(case,side,Path(repos[case["id"]]),a,jdk,cachedir/side)
                except (OSError,ValueError,subprocess.SubprocessError,tarfile.TarError,KeyError) as exc:
                    prepared={"stage":"source preparation","diagnostic": [str(exc)]}
                inputs[side]=prepared
            setup=time.monotonic()-start
            for build in a.build:
                checking=time.monotonic()
                report=screen(case,inputs,build,checkers[build],a)
                report.update(elapsedSeconds=round(setup+time.monotonic()-checking,3),sourceSha256=case["sourceSha256"])
                write(files[build],report)
                print(case["id"],build,report["result"],report.get("firstBlocker",""),flush=True)


if __name__=="__main__":
    main()

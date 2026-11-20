"""Replay two disclosed BUMP build decisions with their historical Alpine JDK, Maven and per-side cached artifacts."""

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import runtime_image as runtime
from import_cache import member_name

CASES = {
    "fscrawler": {"pre": "f6238f5aa1b1cebee9b9f0c87c26c088a7d1e6bc", "breaking": "097d93fbb2f9998ef1390ad10f92d1b70fda8b90",
                  "preLayer": "9b6d45901ed24a6eb9e899f2b59fe7dd9e92cadfb7c9b21003448a38225de04b",
                  "breakingLayer": "2ec3b483cfdeace9b4441302fff1114dd3eba5ec7edd3c04be22c00c6cccaa94"},
    "assertj": {"pre": "5705970602ede90f3dc8c001d0d749461c20d56f", "breaking": "0968864d08e0fce1e5e1caaf89afddd2cc1b2569",
                "preLayer": "d6c1f88f74b301c71eef77deb3254ad93a175263a861a674797e664455a76318",
                "breakingLayer": "402e51150703da0d6657a95f2a231c89ad970d848ef28a5f47abe693fa8a3111"},
}
FSC_SUITE = "fr.pilato.elasticsearch.crawler.fs.tika.TikaDocParserTest"
FSC_METHODS = ("testExtractFromDocx", "testExtractFromTxt")


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def git(repo, *args):
    return subprocess.check_output(["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args])


def scratch_export(repo, rev, dest):
    dest.mkdir()
    process = subprocess.Popen(["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), "archive", rev], stdout=subprocess.PIPE)
    with process.stdout, tarfile.open(fileobj=process.stdout, mode="r|") as archive:
        for item in archive:
            name = runtime.clean(item.name)
            if not name or not item.isreg():
                continue
            file = dest / name
            file.parent.mkdir(exist_ok=True, parents=True)
            with file.open("xb") as out:
                shutil.copyfileobj(archive.extractfile(item), out)
            file.chmod(0o755 if item.mode & 0o111 else 0o644)
    if process.wait() != 0:
        raise ValueError("git archive failed")


def local_repository(layer, sha, destination):
    if runtime.sha(layer) != sha:
        raise ValueError("subject layer digest mismatch")
    repo = destination / "repository"
    repo.mkdir(parents=True)
    files = []
    with tarfile.open(layer, "r|gz") as stream:
        for item in stream:
            key = member_name(item.name)
            if not key or not item.isreg() or key.suffix not in (".pom", ".jar"):
                continue
            artifact, version, filename = key.parts[-3:]
            if not filename.startswith(artifact + "-" + version + ".") and not filename.startswith(artifact + "-" + version + "-"):
                continue
            if not 0 < item.size <= 128 * 1024**2:
                raise ValueError("unexpected local Maven dependency size")
            file = repo / key
            file.parent.mkdir(parents=True, exist_ok=True)
            with file.open("xb") as out:
                shutil.copyfileobj(stream.extractfile(item), out)
            files.append((key.as_posix(), runtime.sha(file)))
    return {"files": len(files), "listingSha256": hashlib.sha256(json.dumps(sorted(files)).encode()).hexdigest()}


def events(path):
    text = path.read_text(errors="strict")
    decode = json.JSONDecoder().raw_decode
    at = 0
    while at < len(text):
        while at < len(text) and text[at].isspace():
            at += 1
        if at == len(text):
            break
        entry, at = decode(text, at)
        yield entry


def bind_classpath(paths, project, m2, image):
    providers = []
    for name in paths:
        p = PurePosixPath(name)
        if p.is_relative_to("/work/project"):
            actual = project / p.relative_to("/work/project")
        elif p.is_relative_to("/work/home/.m2"):
            actual = m2 / p.relative_to("/work/home/.m2")
        elif p.is_absolute() and ".." not in p.parts:
            actual = image / str(p).lstrip("/")
        else:
            raise ValueError("unbound runtime classpath")
        if actual.is_file():
            digest = runtime.sha(actual)
        elif actual.is_dir():
            digest = hashlib.sha256()
            for cl in sorted(actual.rglob("*.class")):
                digest.update((cl.relative_to(actual).as_posix() + "\0" + runtime.sha(cl) + "\n").encode())
            digest = digest.hexdigest()
        else:
            raise ValueError("classpath path absent: " + name)
        providers.append({"path": name, "sha256": digest})
    return providers


def run(image, project, m2, tmp, argv):
    start, clock = stamp(), time.monotonic()
    result = subprocess.run(runtime.isolate(image, project, m2, tmp, argv), env=runtime.environment(),
                            capture_output=True, text=True, errors="replace", timeout=480)
    text = result.stdout + result.stderr
    return text, {"command": argv, "startedUtc": start, "wallSeconds": round(time.monotonic() - clock, 3),
                  "exit": result.returncode, "outputSha256": hashlib.sha256(text.encode()).hexdigest()}


def first_errors(text):
    return [line.strip()[:1200] for line in text.splitlines() if line.startswith("[ERROR]") or
            "Found Banned Dependency:" in line or "BannedDependencies failed with message" in line][:8]


def fscrawler(image, project, m2, tmp):
    results, cp = {}, None
    for n, method in enumerate(FSC_METHODS):
        target = project / "tika/target"
        previous = set(target.glob("junit4-*.events"))
        argv = ["mvn", "-o", "-ntp", "-B", "-Dmaven.repo.local=/work/home/.m2/repository", "-pl", "tika", "-am",
                *(["clean"] if n == 0 else []), "test", "-Dtests.class=" + FSC_SUITE, "-Dtests.method=" + method,
                "-Dtests.seed=4A36F2E33D8CB9CF", "-Dtests.locale=tzm-MA", "-Dtests.timezone=Asia/Anadyr",
                "-Dtests.verbose=true", "-Dtests.leaveTemporary=true"]
        output, row = run(image, project, m2, tmp, argv)
        finished, failures = 0, []
        for f in sorted(set(target.glob("junit4-*.events")) - previous):
            for e in events(f):
                if not isinstance(e, list) or len(e) < 2:
                    continue
                what, data = e[:2]
                if what == "BOOTSTRAP":
                    cp = data["systemProperties"]["java.class.path"].split(":")
                if not isinstance(data, dict) or method not in str(data.get("description", "")):
                    continue
                if what == "TEST_FINISHED":
                    finished += 1
                elif what == "TEST_FAILURE":
                    failures.append({"throwable": data.get("throwableClass"), "message": data.get("message")})
        row.update(actualNamedTests=finished, failures=failures, diagnostics=first_errors(output))
        results[method] = row
    if cp:
        programs = project / "observers"
        programs.mkdir()
        shutil.copyfile(HERE / "DocumentObservation.java", programs / "DocumentObservation.java")
        javac = ["javac", "-proc:none", "-cp", ":".join(cp), "-d", "/work/project/observers", "/work/project/observers/DocumentObservation.java"]
        compile_out, compilation = run(image, project, m2, tmp, javac)
        if compilation["exit"]:
            raise ValueError("observer compilation: " + compile_out[:600])
        output, actual = run(image, project, m2, tmp, ["java", "-Xmx512m", "-Duser.timezone=UTC", "-cp",
            "/work/project/observers:" + ":".join(cp), "fr.pilato.elasticsearch.crawler.fs.tika.DocumentObservation"])
        fields = {}
        for line in output.splitlines():
            if line.startswith("BUMP_FIELD "):
                _, filename, value = line.split(" ", 2)
                if value == "NULL":
                    fields[filename] = None
                else:
                    data = base64.b64decode(value.removeprefix("UTF8:"), validate=True)
                    fields[filename] = {"utf8Bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                        "containsExpectedPassage": (b"This is a sample text available in page" if filename.endswith(".docx")
                                                   else b"This file contains some words.") in data}
            if line.startswith("BUMP_LINK "):
                actual["linkage"] = line.removeprefix("BUMP_LINK ")
        actual["command"][4] = "$BOUND_CLASSPATH_WITH_OBSERVER" if len(actual["command"])>4 else ""
        actual.update(fields=fields, orderedClasspath=bind_classpath(cp, project, m2, image))
        results["direct"] = actual
    return results


def assertj(image, project, m2, tmp):
    output, row = run(image, project, m2, tmp, ["mvn", "-o", "-ntp", "-B", "-Dmaven.repo.local=/work/home/.m2/repository", "clean", "test"])
    suites = re.findall(r"Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)(?:\s*$)", output, re.M)
    row.update(diagnostics=first_errors(output), surefireTotals=list(map(int,suites[-1])) if suites else None)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case", choices=CASES)
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.inputs is None:
        places = list((Path.home()/".cache/in-the-loop/agent-tmp").glob("*/external-upgrade-open/bump-disclosed"))
        if len(places) != 1:
            parser.error("supply the locked input directory with --inputs")
        args.inputs = places[0]
    inputs = args.inputs.resolve()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    case, item = args.case, CASES[args.case]
    gitdb = inputs / (case + ".git")
    if git(gitdb, "rev-parse", item["breaking"]+"^").decode().strip() != item["pre"]:
        raise ValueError("original first parent differs")
    record = {"case":case, "changedFiles":git(gitdb,"diff","--name-only",item["pre"],item["breaking"]).decode().splitlines(),
              "runtimeLayers":[runtime.ALPINE,runtime.RUNTIME], "sides":{}}
    with tempfile.TemporaryDirectory(prefix="bump-original-", dir=inputs.parent) as d:
        root=Path(d)
        image=root/"image"
        runtime.rootfs(inputs,image)
        record["jdkReleaseSha256"]=runtime.sha(image/(runtime.JAVA[1:]+"/release"))
        for side in ("pre","breaking"):
            work=root/side;work.mkdir();tmp=work/"tmp";tmp.mkdir();project=work/"project";m2=work/"m2"
            rev=item[side];scratch_export(gitdb,rev,project)
            layer=inputs/("fscrawler-final-layer.tgz" if (case,side)==("fscrawler","pre") else f"{case}-{side}-final.tgz")
            repo=local_repository(layer,item[side+"Layer"],m2)
            version, vrow = run(image,project,m2,tmp,["mvn","--version"])
            if vrow["exit"] or "11.0.19" not in version or "3.9.2" not in version:
                raise ValueError("historical runtime did not start: "+version[:300])
            data={"revision":rev,"sourceTree":git(gitdb,"rev-parse",rev+"^{tree}").decode().strip(),"mavenVersion":version.strip(),
                  "repo":repo,"finalLayerSha256":item[side+"Layer"]}
            data["observations"]=(fscrawler if case=="fscrawler" else assertj)(image,project,m2,tmp)
            record["sides"][side]=data
            args.output.write_text(json.dumps(record,indent=2)+"\n")
            print(case,side,"measured",flush=True)


if __name__ == "__main__":
    main()

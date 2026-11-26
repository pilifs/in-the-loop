"""Replay a finite public caller on byte-pinned deployments in separate JVMs."""
import argparse
import base64
from contextlib import ExitStack
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from targets import runtime_jdk, upgrade_claims, upgrade_replay

EXAMPLES = Path(__file__).resolve().parents[2]
SIDES = ("parent", "fix")


def read(path):
    return json.loads(path.read_text())


def agrees(expected, actual):
    if "contains" in expected:
        return isinstance(actual.get("return"), str) and all(part in actual["return"] for part in expected["contains"])
    return actual == expected


def comparison_plan(folder):
    spec = read(folder / "comparison.json")
    runtime = read(folder / "runtime.json")
    if spec["schema"] != "public-comparison/v1" or set(spec["revisions"]) != set(SIDES):
        raise ValueError("invalid public comparison")
    if not runtime["deployments"]:
        raise ValueError("no registered deployments")
    for name in (runtime["cache"], runtime["jdk"], *runtime["deployments"]):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+\-]*", name):
            raise ValueError("a runtime name must be a single directory component")
    for deploy in runtime["deployments"].values():
        paths = deploy["classpath"]
        if set(paths) != set(SIDES) or not deploy["providers"]:
            raise ValueError("each deployment needs both classpaths and a provider")
        for index in deploy["providers"].values():
            if type(index) is not int or not 0 <= index < min(map(len, paths.values())):
                raise ValueError("provider outside its original classpath")
        for package in deploy.get("openModules", []):
            if not re.fullmatch(r"[a-zA-Z][\w.]*/[a-zA-Z][\w.]*", package):
                raise ValueError("invalid JVM module/package to open")
    ids = [row["id"] for row in spec["questions"]]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError("empty or duplicate public questions")
    for row in spec["questions"]:
        if not row["basis"] or not row["args"] or not row.get("expected"):
            raise ValueError(f"incomplete question {row['id']}")
        for side, outcome in row["expected"].items():
            if side not in SIDES or set(outcome) not in ({"return"}, {"throws"}, {"contains"}):
                raise ValueError(f"invalid {side} prediction in {row['id']}")
            parts = outcome.get("contains", [])
            if "contains" in outcome and (not isinstance(parts, list) or not parts or not all(isinstance(p, str) and p for p in parts)):
                raise ValueError("partial return prediction requires nonempty fragments")
        if set(row.get("omit", {})) & row["expected"].keys():
            raise ValueError("cannot omit a registered side prediction")
    services = {d["service"] for d in runtime["deployments"].values() if "service" in d}
    if services - {"postgres", "mysql"}:
        raise ValueError("unknown public comparison service")
    required = ["javac", "java"] + (["docker"] if services else [])
    if any("sourceSlice" in d or "upstreamTestInputs" in d for d in runtime["deployments"].values()):
        required.append("git")
    if any("callOwner" in d for d in runtime["deployments"].values()):
        required.append("javap")
    return {"example": folder.name[:3], "approach": "B8", "executable": True, "notExecuted": None,
            "runner": "public-comparison", "revisions": spec["revisions"], "questions": ids,
            "deployments": list(runtime["deployments"]), "tools": {"required": required, "optional": []}}


def classpath(cache, runtime, deployment, side, work):
    files = []
    for index, name in enumerate(deployment["classpath"][side]):
        jar = (cache / name).resolve(strict=True)
        if not jar.is_relative_to(cache) or upgrade_replay.sha(jar) != runtime["sha256"][name]:
            raise ValueError(f"changed {side} dependency {jar.name}")
        # Local javac overlays share a package with their original classes. Keep all other
        # packages in the original signed JAR so its split packages retain compatible signers.
        for part in deployment.get("overlayPackages", []):
            if part["baseIndex"] != index:
                continue
            package = part["package"].split(".")
            if not all(p.isidentifier() for p in package):
                raise ValueError("invalid overlay package")
            expanded = work / side / part["package"]
            dest = expanded.joinpath(*package)
            dest.mkdir(parents=True)
            with zipfile.ZipFile(jar) as archive:
                for member in archive.namelist():
                    path = Path(member)
                    if path.parent == Path(*package) and path.suffix == ".class":
                        (dest / path.name).write_bytes(archive.read(member))
            if not any(dest.iterdir()):
                raise ValueError(f"missing package {part['package']} in {jar.name}")
            files.append(expanded)
        files.append(jar)
    return os.pathsep.join(map(str, files))


def observe(jdk, classpath, trial, caller, args, providers, *, label, service_env=None, open_modules=()):
    """Run one public history and check which artifact actually supplied each original class."""
    obs = trial / "observed"
    log = trial / "loaded"
    # HotSpot 8 writes class origins to stdout. Unified class logging starts with JDK 9.
    legacy = runtime_jdk.feature(runtime_jdk.release(jdk)["JAVA_VERSION"]) == "8"
    class_log = "-verbose:class" if legacy else f"-Xlog:class+load=info:file={log}"
    encoded = [base64.b64encode(s.encode("utf-16-be")).decode() for s in args]
    cmd = [jdk / "bin/java", "-XX:-UsePerfData", "-Xmx256m",
           *(f"--add-opens={package}=ALL-UNNAMED" for package in open_modules), f"-Djava.io.tmpdir={trial}",
           f"-Duser.home={trial}", "-Duser.timezone=UTC", "-Dfile.encoding=UTF-8",
           f"-Dupgrade.observation.file={obs}", class_log,
           "-cp", classpath, "UpgradeObservation", caller, *encoded]
    env = {"PATH": str(jdk / "bin") + ":/usr/bin:/bin", "HOME": str(trial),
           "TMPDIR": str(trial), "TZ": "UTC", "LANG": "C.UTF-8", **(service_env or {})}
    proc = subprocess.run(cmd, cwd=trial, env=env, capture_output=True, text=True, timeout=40)
    if proc.returncode or not obs.is_file():
        raise ValueError(f"{label} failed to run: {proc.stderr[-1200:]}")
    records = obs.read_text().splitlines()
    outcome = upgrade_replay.typed_outcome(records)
    loaded = upgrade_replay.class_origins(proc.stdout if legacy else log.read_text())
    for cls, required in providers.items():
        if loaded.get(cls) != {required.resolve()}:
            details = next((s.split(" ", 1)[1] for s in records if s.startswith("UPGRADE-DETAIL ")), "")
            detail = base64.b64decode(details).decode("utf-16-be", "replace")
            for key, value in (service_env or {}).items():
                if key.endswith("_PASSWORD"):
                    detail = detail.replace(value, "<fixture credential>")
            raise ValueError(f"{label}: {cls} did not load from {required.name}. {detail}")
    return outcome


def compile_java(jdk, classpath, dest, sources, options=()):
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run([jdk / "bin/javac", "-J-XX:-UsePerfData", "-J-Xmx192m", "-g", "-proc:none",
                    "-encoding", "UTF-8", *options, "-cp", classpath, "-d", dest, *sources], check=True)


def class_digests(folder):
    return {p.relative_to(folder).as_posix(): upgrade_replay.sha(p) for p in sorted(folder.rglob("*.class"))}


def jar_classes(archive):
    """Identify the actual bytecode of each class in a prepared source slice."""
    with zipfile.ZipFile(archive) as jar:
        members = [item.filename for item in jar.infolist() if item.filename.endswith(".class")]
        if not members or len(set(members)) != len(members):
            raise ValueError("empty or duplicate slice classes")
        return {name: hashlib.sha256(jar.read(name)).hexdigest() for name in sorted(members)}


def upstream_test_inputs(cache, spec, deployment, work):
    """Materialize the same original test types and resources at both caller boundaries."""
    fixtures = deployment.get("upstreamTestInputs")
    if not fixtures:
        return [], None
    tree = (cache / fixtures["tree"]).resolve(strict=True)
    if not tree.is_relative_to(cache):
        raise ValueError("upstream fixture tree outside cache")
    revision = spec["revisions"]["fix"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("invalid original fixture revision")
    sources = []
    resources = work / "resources"
    for name, digest in fixtures["sha256"].items():
        match = re.fullmatch(r"[\w-]+/src/(?:test|testFixtures)/(java|resources)/(.+)", name)
        if not match or any(p in ("", ".", "..") for p in name.split("/")):
            raise ValueError(f"invalid upstream test fixture path: {name}")
        data = subprocess.check_output(["git", "-C", tree, "show", f"{revision}:{name}"])
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"upstream test fixture differs: {name}")
        java = match[1] == "java"
        dest = (work / "java" if java else resources) / match[2]
        if dest.exists() or (java and dest.suffix != ".java"):
            raise ValueError(f"ambiguous upstream test fixture: {name}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        if java:
            sources.append(dest)
    return sources, resources if resources.exists() else None


def caller_invocations(jdk, folder, owner):
    code = upgrade_claims.disassemble(jdk, [folder], "PublicCaller", 15)
    sites = [{"caller": member[0], "offset": pc, "method": method, "descriptor": descriptor}
             for member, pc, (target, method, descriptor) in upgrade_claims.invocation_sites(code, "PublicCaller")
             if target == owner.replace(".", "/")]
    if not sites:
        raise ValueError(f"compiled caller has no direct calls to {owner}")
    return sites


def compile_kotlin(jdk, cache, compiler, sources, classpath, classes):
    """Compile the same Kotlin client against each library's inline extension bodies."""
    jars = []
    for name, digest in compiler.items():
        jar = (cache / name).resolve(strict=True)
        if not jar.is_relative_to(cache) or upgrade_replay.sha(jar) != digest:
            raise ValueError(f"changed Kotlin compiler dependency {jar.name}")
        jars.append(str(jar))
    subprocess.run([jdk / "bin/java", "-XX:-UsePerfData", "-Xmx384m", "-cp", os.pathsep.join(jars),
                    "org.jetbrains.kotlin.cli.jvm.K2JVMCompiler", "-no-stdlib", "-no-reflect", "-jvm-target", "17",
                    "-classpath", str(classes) + os.pathsep + classpath, "-d", classes, *sources], check=True)


def compile_source_slice(cache, jdk, deployment, revisions, side, cp, work):
    """Overlay one original source blob on the same released dependencies on both sides."""
    source = deployment["sourceSlice"]
    tree = (cache / source["worktrees"][side]).resolve(strict=True)
    if not tree.is_relative_to(cache) or not re.fullmatch(r"[0-9a-f]{40}", revisions[side]):
        raise ValueError("invalid pinned source tree or revision")
    path = Path(source["path"])
    if path.is_absolute() or ".." in path.parts or path.suffix != ".java":
        raise ValueError("invalid source slice path")
    data = subprocess.check_output(["git", "-C", tree, "show", f"{revisions[side]}:{path}"])
    blob = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    if blob != source["blobs"][side] or hashlib.sha256(data).hexdigest() != source["sha256"][side]:
        raise ValueError(f"{side} original source digest differs")
    work.mkdir(parents=True)
    original = work / path.name
    original.write_bytes(data)
    classes = work / "classes"
    compile_java(jdk, cp, classes, [original], ["--release", "8", "-implicit:none"])
    if not (classes / (source["class"].replace(".", "/") + ".class")).is_file():
        raise ValueError("source slice did not produce its registered class")
    return classes


def replay(folder, record=False):
    comparison_plan(folder)
    spec = read(folder / "comparison.json")
    runtime = read(folder / "runtime.json")
    cache = Path(os.environ.get("PUBLIC_COMPARISON_CACHE", Path.home() / ".cache/in-the-loop" / runtime["cache"])).resolve()
    jdk = Path(os.environ.get("PUBLIC_COMPARISON_JDK", Path.home() / ".sdkman/candidates/java" / runtime["jdk"]))
    sha = upgrade_replay.sha
    if sha(jdk / "release") != runtime["jdkReleaseSha256"]:
        raise ValueError("JDK release differs from the registered deployment")
    sources = sorted((folder / "caller").rglob("*.java"))
    kotlin = sorted((folder / "caller").rglob("*.kt"))
    adapters = {side: sorted((folder / "adapters" / side).rglob("*.java")) for side in SIDES}
    fixtures = sorted(p for p in (folder / "fixtures").rglob("*") if p.is_file())
    if not sources:
        raise ValueError("missing public caller")
    result = {"schema": "public-observations/v1", "comparisonSha256": sha(folder / "comparison.json"),
              "runtimeSha256": sha(folder / "runtime.json"), "launcherSha256": sha(upgrade_replay.LAUNCHER),
              "inputs": {str(p.relative_to(folder)): sha(p) for p in sources + kotlin + fixtures +
                         adapters["parent"] + adapters["fix"]}, "deployments": {}}
    with tempfile.TemporaryDirectory(prefix="public-comparison-") as tmp, ExitStack() as services:
        work = Path(tmp)
        for name, deploy in runtime["deployments"].items():
            services.close()
            service_env = {}
            if deploy.get("service") == "postgres":
                from targets.public_postgres import postgres
                image = deploy.get("postgresImage") or runtime["postgresImage"]
                service_env = services.enter_context(postgres(image))
            elif deploy.get("service") == "mysql":
                from targets.public_mysql import mysql
                service_env = services.enter_context(mysql(deploy["mysqlImage"]))
            cp = {side: classpath(cache, runtime, deploy, side, work / "packages" / name) for side in SIDES}
            slices = {}
            if "sourceSlice" in deploy:
                for side in SIDES:
                    slices[side] = compile_source_slice(cache, jdk, deploy, spec["revisions"], side, cp[side],
                                                        work / "slices" / name / side)
                    cp[side] = str(slices[side]) + os.pathsep + cp[side]
            per_side = deploy.get("compilePerSide", False)
            compile_side = deploy.get("compileAgainst", "fix")
            if compile_side not in SIDES or (per_side and "compileAgainst" in deploy):
                raise ValueError("invalid caller compilation side")
            if any(adapters.values()) and not (per_side and all(adapters.values())):
                raise ValueError("revision-specific adapters require separate compilation on both revisions")
            upstream, resources = upstream_test_inputs(cache, spec, deploy, work / "test-inputs" / name)
            classes = {}
            for side in (SIDES if per_side else (compile_side,)):
                classes[side] = work / name / side
                compile_java(jdk, cp[side], classes[side], [upgrade_replay.LAUNCHER, *sources, *adapters[side], *upstream],
                             ["-parameters"] if deploy.get("parameterNames") else [])
            if not per_side:
                classes = dict.fromkeys(SIDES, classes[compile_side])
            if bool(kotlin) != bool(deploy.get("kotlinCompiler")):
                raise ValueError("Kotlin caller sources require a locked compiler")
            if kotlin:
                for side in SIDES:
                    dest = work / "kotlin" / name / side
                    shutil.copytree(classes[side], dest)
                    compile_kotlin(jdk, cache, deploy["kotlinCompiler"], kotlin, cp[side], dest)
                    classes[side] = dest
            runs = []
            for side in SIDES:
                providers = {cls: cache / deploy["classpath"][side][index] for cls, index in deploy["providers"].items()}
                if slices:
                    providers[deploy["sourceSlice"]["class"]] = slices[side]
                for row in spec["questions"]:
                    if side in row.get("omit", {}):
                        continue
                    with tempfile.TemporaryDirectory(dir=work) as trial_path:
                        trial = Path(trial_path)
                        if fixtures:
                            shutil.copytree(folder / "fixtures", trial / "fixtures")
                        caller_path = [str(classes[side]), *([str(resources)] if resources else []), cp[side]]
                        actual = observe(jdk, os.pathsep.join(caller_path), trial, "PublicCaller",
                                         row["args"], providers, label=f"{folder.name} {side} {row['id']}",
                                         service_env=service_env, open_modules=deploy.get("openModules", ()))
                        print(f"{name} {side} {row['id']} {actual}", flush=True)
                        expected = row["expected"].get(side)
                        runs.append({"side": side, "id": row["id"], "outcome": actual,
                                     "prediction": "observed only" if expected is None else
                                     ("matched" if agrees(expected, actual) else "refuted")})
            record_entry = {"callerClasses": class_digests(classes["fix"]), "observations": runs}
            if per_side or kotlin:
                record_entry["callerClassesBySide"] = {side: class_digests(classes[side]) for side in SIDES}
            if "callOwner" in deploy:
                record_entry["callerInvocations"] = {
                    side: caller_invocations(jdk, classes[side], deploy["callOwner"]) for side in SIDES}
            if slices:
                record_entry["sourceSliceClasses"] = {side: class_digests(slices[side]) for side in SIDES}
            if deploy.get("preparedSlice"):
                record_entry["preparedSliceClasses"] = {
                    side: jar_classes(cache / deploy["classpath"][side][0]) for side in SIDES}
            result["deployments"][name] = record_entry
            if deploy.get("service") == "postgres":
                result["deployments"][name]["postgresVersionNumber"] = int(service_env["PUBLIC_COMPARISON_PG_VERSION"])
            elif deploy.get("service") == "mysql":
                result["deployments"][name]["mysqlVersion"] = service_env["PUBLIC_COMPARISON_MYSQL_VERSION"]
    receipt = folder / "observations.json"
    if record:
        receipt.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    elif read(receipt) != result:
        raise ValueError(f"{folder.name}: fresh observations differ from {receipt.name}")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example")
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args(argv)
    folder, = EXAMPLES.glob(args.example + "-*")
    replay(folder, args.record)


if __name__ == "__main__":
    main()

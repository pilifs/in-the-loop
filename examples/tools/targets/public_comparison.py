"""Replay a finite public caller on byte-pinned deployments in separate JVMs."""
import argparse
import base64
from contextlib import ExitStack
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from targets import upgrade_replay

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
    uses_postgres = any(d.get("service") == "postgres" for d in runtime["deployments"].values())
    required = ["javac", "java"] + (["docker"] if uses_postgres else [])
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
    encoded = [base64.b64encode(s.encode("utf-16-be")).decode() for s in args]
    cmd = [jdk / "bin/java", "-XX:-UsePerfData", "-Xmx256m",
           *(f"--add-opens={package}=ALL-UNNAMED" for package in open_modules), f"-Djava.io.tmpdir={trial}",
           f"-Duser.home={trial}", "-Duser.timezone=UTC", "-Dfile.encoding=UTF-8",
           f"-Dupgrade.observation.file={obs}", f"-Xlog:class+load=info:file={log}",
           "-cp", classpath, "UpgradeObservation", caller, *encoded]
    env = {"PATH": str(jdk / "bin") + ":/usr/bin:/bin", "HOME": str(trial),
           "TMPDIR": str(trial), "TZ": "UTC", "LANG": "C.UTF-8", **(service_env or {})}
    proc = subprocess.run(cmd, cwd=trial, env=env, capture_output=True, text=True, timeout=40)
    if proc.returncode or not obs.is_file():
        raise ValueError(f"{label} failed to run: {proc.stderr[-1200:]}")
    records = obs.read_text().splitlines()
    outcome = upgrade_replay.typed_outcome(records)
    loaded = upgrade_replay.class_origins(log.read_text())
    for cls, required in providers.items():
        if loaded.get(cls) != {required.resolve()}:
            details = next((s.split(" ", 1)[1] for s in records if s.startswith("UPGRADE-DETAIL ")), "")
            detail = base64.b64decode(details).decode("utf-16-be", "replace")
            if service_env and "PUBLIC_COMPARISON_PG_PASSWORD" in service_env:
                detail = detail.replace(service_env["PUBLIC_COMPARISON_PG_PASSWORD"], "<fixture credential>")
            raise ValueError(f"{label}: {cls} did not load from {required.name}. {detail}")
    return outcome


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
    fixtures = sorted(p for p in (folder / "fixtures").rglob("*") if p.is_file())
    if not sources:
        raise ValueError("missing public caller")
    result = {"schema": "public-observations/v1", "comparisonSha256": sha(folder / "comparison.json"),
              "runtimeSha256": sha(folder / "runtime.json"), "launcherSha256": sha(upgrade_replay.LAUNCHER),
              "inputs": {str(p.relative_to(folder)): sha(p) for p in sources + fixtures}, "deployments": {}}
    with tempfile.TemporaryDirectory(prefix="public-comparison-") as tmp, ExitStack() as services:
        work = Path(tmp)
        for name, deploy in runtime["deployments"].items():
            services.close()
            service_env = {}
            if deploy.get("service") == "postgres":
                from targets.public_postgres import postgres
                image = deploy.get("postgresImage") or runtime["postgresImage"]
                service_env = services.enter_context(postgres(image))
            cp = {side: classpath(cache, runtime, deploy, side, work / "packages" / name) for side in SIDES}
            classes = work / name
            classes.mkdir(exist_ok=True)
            subprocess.run([jdk / "bin/javac", "-J-XX:-UsePerfData", "-J-Xmx192m", "-g", "-proc:none", "-encoding", "UTF-8",
                            "-cp", cp["fix"], "-d", classes, upgrade_replay.LAUNCHER, *sources], check=True)
            runs = []
            for side in SIDES:
                providers = {cls: cache / deploy["classpath"][side][index] for cls, index in deploy["providers"].items()}
                for row in spec["questions"]:
                    if side in row.get("omit", {}):
                        continue
                    with tempfile.TemporaryDirectory(dir=work) as trial_path:
                        trial = Path(trial_path)
                        if fixtures:
                            shutil.copytree(folder / "fixtures", trial / "fixtures")
                        actual = observe(jdk, str(classes) + os.pathsep + cp[side], trial, "PublicCaller",
                                         row["args"], providers, label=f"{folder.name} {side} {row['id']}",
                                         service_env=service_env, open_modules=deploy.get("openModules", ()))
                        print(f"{name} {side} {row['id']} {actual}", flush=True)
                        expected = row["expected"].get(side)
                        runs.append({"side": side, "id": row["id"], "outcome": actual,
                                     "prediction": "observed only" if expected is None else
                                     ("matched" if agrees(expected, actual) else "refuted")})
            result["deployments"][name] = {"callerClasses": {p.relative_to(classes).as_posix(): sha(p)
                for p in sorted(classes.rglob("*.class"))}, "observations": runs}
            if service_env:
                result["deployments"][name]["postgresVersionNumber"] = int(service_env["PUBLIC_COMPARISON_PG_VERSION"])
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

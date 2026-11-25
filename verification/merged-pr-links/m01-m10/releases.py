"""Repeat the three historical counterexamples on two published releases apiece."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
sys.path.insert(0, str(HERE.parent / "upstream"))
from targets import public_comparison as comparison
from recheck import classpath, jars_for, sha


def measure(number, project, lock, local_cache, fetch):
    folder, = (ROOT / "examples").glob(number + "-*")
    runtime = comparison.read(folder / "runtime.json")
    spec = comparison.read(folder / "comparison.json")
    physical = comparison.read(folder / "observations.json")
    sources = sorted((folder / "caller").rglob("*.java"))
    fixtures = sorted(p for p in (folder / "fixtures").rglob("*") if p.is_file())
    if (physical["inputs"] != {p.relative_to(folder).as_posix(): sha(p) for p in sources + fixtures}
            or physical["comparisonSha256"] != sha(folder / "comparison.json")
            or physical["runtimeSha256"] != sha(folder / "runtime.json")
            or physical["launcherSha256"] != sha(comparison.upgrade_replay.LAUNCHER)):
        raise ValueError(f"{number}: changed registered inputs")
    setup = Path.home() / ".cache/in-the-loop" / runtime["cache"]
    jdks = Path.home() / ".sdkman/candidates/java"
    compiler = jdks / runtime["jdk"]
    jdk = jdks / project["jdk"]
    if sha(compiler / "release") != runtime["jdkReleaseSha256"] or sha(jdk / "release") != project["jdkReleaseSha256"]:
        raise ValueError(f"{number}: JDK differs from lock")
    artifact_keys = [key for version in project["versions"].values() for key in version]
    jars = jars_for({"modules": [], "dependencies": artifact_keys}, local_cache, fetch, lock["sha256"], setup)
    receipt = {"example": number, "releaseInputsSha256": sha(HERE / "release-inputs.json"),
               "historicalObservationsSha256": sha(folder / "observations.json"),
               "jdkReleaseSha256": project["jdkReleaseSha256"], "versions": {}}
    with tempfile.TemporaryDirectory(prefix="public-releases-") as temporary:
        work = Path(temporary)
        compile_cp = classpath([jars[key] for key in project["versions"][project["compileVersion"]]])
        classes = work / "caller"
        classes.mkdir()
        subprocess.run([compiler / "bin/javac", "-g", "-proc:none", "-encoding", "UTF-8", "-cp", compile_cp,
                        "-d", classes, comparison.upgrade_replay.LAUNCHER, *sources], check=True)
        fingerprints = {p.relative_to(classes).as_posix(): sha(p) for p in classes.rglob("*.class")}
        if fingerprints != physical["deployments"]["pins"]["callerClasses"]:
            raise ValueError(f"{number}: different historical caller bytecode")
        receipt["callerClasses"] = fingerprints
        for version, keys in project["versions"].items():
            files = [jars[k] for k in keys]
            origins = {cls: files[i] for cls, i in project["providers"].items()}
            rows = []
            for question in spec["questions"]:
                with tempfile.TemporaryDirectory(dir=work) as t:
                    trial = Path(t)
                    if fixtures:
                        shutil.copytree(folder / "fixtures", trial / "fixtures")
                    actual = comparison.observe(jdk, classpath([classes, *files]), trial, "PublicCaller",
                                                question["args"], origins, label=f"{number} {version} {question['role']}",
                                                open_modules=project.get("openModules", []))
                rows.append({"question": question["id"], "outcome": actual,
                             "matchesMergedPrediction": comparison.agrees(question["expected"]["fix"], actual)})
            receipt["versions"][version] = {
                "classpath": [{"coordinate": key, "sha256": sha(jars[key])} for key in keys],
                "observations": rows}
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path.home() / ".cache/in-the-loop/merged-pr-links-m01-m10-followup")
    parser.add_argument("--fetch", action="store_true", help="retrieve missing Maven artifacts and check their pinned digests")
    parser.add_argument("--output", type=Path, help="write the fresh observations to this path")
    args = parser.parse_args()
    lock = comparison.read(HERE / "release-inputs.json")
    reports = [measure(n, p, lock, args.cache.resolve(), args.fetch) for n, p in lock["projects"].items()]
    if args.output:
        args.output.write_text(json.dumps(reports, indent=2, ensure_ascii=False) + "\n")
    elif reports != comparison.read(HERE / "release-observations.json"):
        raise SystemExit("release observations differ from the recorded histories")
    for report in reports:
        for version, result in report["versions"].items():
            print(report["example"], version, [q["matchesMergedPrediction"] for q in result["observations"]])

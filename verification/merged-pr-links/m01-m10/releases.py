"""Repeat registered public callers on the published releases in an input lock."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
sys.path.insert(0, str(HERE.parent / "upstream"))
from targets import public_comparison as comparison
from recheck import classpath, jars_for, sha


def measure(number, project, lock, local_cache, fetch, inputs=HERE / "release-inputs.json"):
    folder, = (ROOT / "examples").glob(number + "-*")
    if "variant" in project:
        variant = project["variant"]
        if variant in ("", ".", "..") or Path(variant).name != variant:
            raise ValueError("a release variant must name an example subdirectory")
        folder = folder / variant
    runtime = comparison.read(folder / "runtime.json")
    spec = comparison.read(folder / "comparison.json")
    physical = comparison.read(folder / "observations.json")
    sources = sorted((folder / "caller").rglob("*.java"))
    adapters = {side: sorted((folder / "adapters" / side).rglob("*.java")) for side in comparison.SIDES}
    fixtures = sorted(p for p in (folder / "fixtures").rglob("*") if p.is_file())
    if (physical["inputs"] != {p.relative_to(folder).as_posix(): sha(p)
                               for p in sources + fixtures + adapters["parent"] + adapters["fix"]}
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
    receipt = {"example": number, "releaseInputsSha256": sha(inputs),
               "historicalObservationsSha256": sha(folder / "observations.json"),
               "jdkReleaseSha256": project["jdkReleaseSha256"], "versions": {}}
    with tempfile.TemporaryDirectory(prefix="public-releases-") as temporary:
        work = Path(temporary)
        original = project.get("deployment", "pins")
        deployment = runtime["deployments"][original]
        if "compileVersion" in project:
            compile_cp = classpath([jars[key] for key in project["versions"][project["compileVersion"]]])
        else:
            compile_cp = comparison.classpath(setup, runtime, deployment, deployment.get("compileAgainst", "fix"), work)
        classes = work / "caller"
        originals, resources = comparison.upstream_test_inputs(setup, spec, deployment, work / "test-inputs")
        comparison.compile_java(compiler, compile_cp, classes,
                                [comparison.upgrade_replay.LAUNCHER, *sources, *adapters["fix"], *originals],
                                ["-parameters"] if deployment.get("parameterNames") else [])
        fingerprints = comparison.class_digests(classes)
        if fingerprints != physical["deployments"][original]["callerClasses"]:
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
                    actual = comparison.observe(jdk, classpath([classes, *([resources] if resources else []), *files]), trial, "PublicCaller",
                                                question["args"], origins, label=f"{number} {version} {question['role']}",
                                                open_modules=project.get("openModules", []))
                rows.append({"question": question["id"], "outcome": actual,
                             "matchesMergedPrediction": comparison.agrees(question["expected"]["fix"], actual)})
            receipt["versions"][version] = {
                "classpath": [{"coordinate": key, "sha256": sha(jars[key])} for key in keys],
                "observations": rows}
    return receipt


def check_observations(lock_file, result_file, references, release_changes=None):
    """Bind released caller bytes and outcomes to their pinned side, including named later changes."""
    release_changes = release_changes or {}
    if release_changes.keys() - {(number, version) for number, versions in references.items() for version in versions}:
        raise ValueError("override refers to an unregistered release")
    lock = comparison.read(lock_file)
    results = comparison.read(result_file)
    if list(lock["projects"]) != list(references) or [r["example"] for r in results] != list(references):
        raise ValueError("release example missing, duplicated or reordered")
    total = 0
    for r in results:
        number = r["example"]
        folder, = (ROOT / "examples").glob(number + "-*")
        spec = comparison.read(folder / "comparison.json")
        project = lock["projects"][number]
        physical = comparison.read(folder / "observations.json")["deployments"][project.get("deployment", "pins")]
        roles = references[number]
        if (r["releaseInputsSha256"] != comparison.upgrade_replay.sha(lock_file)
                or r["historicalObservationsSha256"] != comparison.upgrade_replay.sha(folder / "observations.json")
                or r["jdkReleaseSha256"] != project["jdkReleaseSha256"] or r["callerClasses"] != physical["callerClasses"]
                or list(r["versions"]) != list(roles) or list(project["versions"]) != list(roles)):
            raise ValueError(f"{number}: different lock, caller or released version")
        for version, side in roles.items():
            measured = r["versions"][version]
            coordinates = project["versions"][version]
            classpath = [{"coordinate": k, "sha256": lock["sha256"][k]} for k in coordinates]
            if measured["classpath"] != classpath:
                raise ValueError(f"{number} {version}: altered classpath or digest")
            actual = [row for row in physical["observations"] if row["side"] == side]
            if [r["id"] for r in actual] != [q["id"] for q in spec["questions"]]:
                raise ValueError(f"{number}: reordered original histories")
            changes = release_changes.get((number, version), {})
            if set(changes) - {row["id"] for row in actual}:
                raise ValueError(f"{number} {version}: unknown release-specific question")
            actual = [{**row, "outcome": changes.get(row["id"], row["outcome"])} for row in actual]
            expected = [{"question": q["id"], "outcome": row["outcome"],
                         "matchesMergedPrediction": comparison.agrees(q["expected"]["fix"], row["outcome"])}
                        for q, row in zip(spec["questions"], actual, strict=True)]
            if measured["observations"] != expected:
                raise ValueError(f"{number} {version}: differs from the {side} observations")
            total += len(expected)
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=HERE / "release-inputs.json", help="campaign release input lock")
    parser.add_argument("--cache", type=Path, help="local Maven artifact cache")
    parser.add_argument("--fetch", action="store_true", help="retrieve missing Maven artifacts and check their pinned digests")
    parser.add_argument("--output", type=Path, help="write the fresh observations to this path")
    args = parser.parse_args()
    lock = comparison.read(args.inputs)
    cache = args.cache or Path.home() / ".cache/in-the-loop" / lock.get("cache", "merged-pr-links-m01-m10-followup")
    reports = [measure(n, p, lock, cache.resolve(), args.fetch, args.inputs) for n, p in lock["projects"].items()]
    if args.output:
        args.output.write_text(json.dumps(reports, indent=2, ensure_ascii=False) + "\n")
    elif reports != comparison.read(args.inputs.with_name("release-observations.json")):
        raise SystemExit("release observations differ from the recorded histories")
    for report in reports:
        for version, result in report["versions"].items():
            print(report["example"], version, [q["matchesMergedPrediction"] for q in result["observations"]])

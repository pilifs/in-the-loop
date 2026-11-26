"""Execute extra public histories with the same compiled client at both pins and on releases."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "m01-m10"))
from releases import classpath, comparison, jars_for, sha

CASES = {
    "539": ("IndexedAdds", ["duplicate", "distinct"]),
    "549": ("MarkWindow", ["0", "1", "2"]),
    "574": ("DecimalViews", ["heap", "read-only", "direct"]),
    "581": ("GroupOrder", ["change", "constant"]),
}


def expected(number, version, side, history):
    if number == "539":
        if history == "distinct":
            return {"return": "true/true, calls=1/2, set=[01, 2], lookup=01"}
        calls = 2 if version == "4.6.0" else 1
        return {"return": f"true/false, calls=1/{calls}, set=[01], lookup=01"}
    if number == "549":
        return {"return": {"0": "afterMark=ab, delegate=c, afterReset=a",
                           "1": "afterMark=b, delegate=c, afterReset=b",
                           "2": "afterMark=, delegate=c, afterReset=EOF"}[history]}
    if number == "574":
        if side == "parent":
            return {"throws": "java.lang.NoClassDefFoundError"}
        if history == "heap":
            return {"return": "1230@2, cursor=0"}
        return {"throws": "java.nio.ReadOnlyBufferException" if history == "read-only"
                else "java.lang.UnsupportedOperationException"}
    phase = "published" if side == "parent" and history == "change" else "initial"
    order = "group:K, select" if side == "parent" else "select, group:K"
    return {"return": f"[{order}, value:{phase}-7, inner-complete, outer-complete]"}


def contracts(work, cache, release_cache, fetch):
    lock = comparison.read(HERE / "release-inputs.json")
    references = comparison.read(HERE / "release-references.json")
    results = {}
    for number, (name, histories) in CASES.items():
        folder, = (ROOT / "examples").glob(number + "-*")
        runtime = comparison.read(folder / "runtime.json")
        project = lock["projects"][number]
        jdk = Path.home() / ".sdkman/candidates/java" / runtime["jdk"]
        if sha(jdk / "release") != runtime["jdkReleaseSha256"]:
            raise ValueError(f"{number}: different JDK")
        pins = runtime["deployments"]["pins"]
        files = {side: [Path(p) for p in comparison.classpath(cache, runtime, pins, side, work).split(":")]
                 for side in comparison.SIDES}
        coordinates = [k for keys in project["versions"].values() for k in keys]
        jars = jars_for({"modules": [], "dependencies": coordinates}, release_cache, fetch, lock["sha256"], cache)
        for version, keys in project["versions"].items():
            files[version] = [jars[k] for k in keys]
        source = HERE / (name + ".java")
        classes = work / name
        comparison.compile_java(jdk, classpath(files["fix"]), classes, [comparison.upgrade_replay.LAUNCHER, source])
        entry = {"sourceSha256": sha(source), "runtimeSha256": sha(folder / "runtime.json"),
                 "callerClasses": comparison.class_digests(classes), "deployments": {}}
        for version, cp in files.items():
            side = references[number].get(version, version)
            provider = {cls: cp[i] for cls, i in pins["providers"].items()}
            observed = {}
            for history in histories:
                with tempfile.TemporaryDirectory(dir=work) as trial:
                    actual = comparison.observe(jdk, classpath([classes, *cp]), Path(trial), name, [history],
                                                provider, label=f"{name} {version} {history}")
                if actual != expected(number, version, side, history):
                    raise ValueError(f"{name} {version} {history}: expected {expected(number, version, side, history)}, got {actual}")
                observed[history] = actual
            entry["deployments"][version] = observed
        results[number] = entry
    return results


def jackson_companions(work, cache, fetch):
    # The earlier campaign independently locked the public 3.3.0 release graph.
    inputs = HERE.parent / "upstream/inputs.json"
    lock = comparison.read(inputs)["sha256"]
    components = {"jackson-core": "tools.jackson.core:jackson-core:3.3.0",
                  "jackson-databind": "tools.jackson.core:jackson-databind:3.3.0",
                  "jackson-annotations": "com.fasterxml.jackson.core:jackson-annotations:2.23"}
    release_cache = Path.home() / ".cache/in-the-loop/merged-pr-links-followup"
    jars = jars_for({"modules": [], "dependencies": list(components.values())}, release_cache, fetch, lock, cache)
    results = {}
    for number in ("565", "566", "567"):
        folder, = (ROOT / "examples").glob(number + "-*")
        spec = comparison.read(folder / "comparison.json")
        runtime = comparison.read(folder / "runtime.json")
        original = comparison.read(folder / "observations.json")["deployments"]["pins"]
        jdk = Path.home() / ".sdkman/candidates/java" / runtime["jdk"]
        if sha(jdk / "release") != runtime["jdkReleaseSha256"]:
            raise ValueError(f"{number}: different JDK")
        pins = runtime["deployments"]["pins"]
        classes = work / number
        sources = sorted((folder / "caller").glob("*.java"))
        full = comparison.classpath(cache, runtime, pins, "fix", work)
        comparison.compile_java(jdk, full, classes, [comparison.upgrade_replay.LAUNCHER, *sources])
        if comparison.class_digests(classes) != original["callerClasses"]:
            raise ValueError(f"{number}: changed original application bytecode")
        result = {"runtimeSha256": sha(folder / "runtime.json"), "callerClasses": original["callerClasses"],
                  "sides": {}}
        for side in comparison.SIDES:
            cp = [Path(p) for p in comparison.classpath(cache, runtime, pins, side, work).split(":")]
            provider = {cls: cp[i] for cls, i in pins["providers"].items()}
            replacements = {}
            for i, key in enumerate(pins["classpath"][side]):
                if key.startswith("artifacts/snapshots-B/"):
                    artifact, = [a for a in components if Path(key).name.startswith(a + "-")]
                    coord = components[artifact]
                    cp[i] = jars[coord]
                    replacements[coord] = lock[coord]
                    if artifact == "jackson-core":
                        provider["tools.jackson.core.TokenStreamFactory"] = cp[i]
                    if artifact == "jackson-databind":
                        provider["tools.jackson.databind.ObjectMapper"] = cp[i]
            required = {"jackson-core", "jackson-annotations"}
            if number == "567":
                required.add("jackson-databind")
            if set(replacements) != {components[a] for a in required}:
                raise ValueError(f"{number}: incomplete release-companion comparison")
            measured = []
            for q in spec["questions"]:
                with tempfile.TemporaryDirectory(dir=work) as trial:
                    outcome = comparison.observe(jdk, classpath([classes, *cp]), Path(trial), "PublicCaller", q["args"],
                                                 provider, label=f"{number} released companions {side} {q['id']}")
                prior, = [r["outcome"] for r in original["observations"] if r["side"] == side and r["id"] == q["id"]]
                if outcome != prior:
                    raise ValueError(f"{number} {side} {q['id']}: release companions changed {prior} to {outcome}")
                measured.append({"question": q["id"], "outcome": outcome, "matchesOriginal": prior == outcome})
            result["sides"][side] = {"releasedCompanions": replacements, "observations": measured}
        results[number] = result
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fetch", action="store_true", help="retrieve missing hash-pinned public release jars")
    args = parser.parse_args()
    cache = Path.home() / ".cache/in-the-loop/merged-pr-links-r01-r50"
    with tempfile.TemporaryDirectory(prefix="r-series-followups-") as temporary:
        work = Path(temporary)
        result = {"releaseInputsSha256": sha(HERE / "release-inputs.json"),
                  "launcherSha256": sha(comparison.upgrade_replay.LAUNCHER),
                  "extraHistories": contracts(work, cache, cache, args.fetch),
                  "jacksonCompanions": jackson_companions(work, cache, args.fetch)}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    elif result != comparison.read(HERE / "followup-observations.json"):
        raise ValueError("different follow-up observations")
    print("Additional public histories and release-companion observations replayed.")


if __name__ == "__main__":
    main()

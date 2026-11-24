"""Pin and repeat the original 187 claims on their historical Java inputs."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "java-semantics-gap"))
from historical import FROZEN, FROZEN_SHA, ROOT, benchmark, digest, freeze

START = "837c9fb9a25f7931493a774d0c2c744f63260081"
ORIGINAL = "c9995ae17d82df1eceb185e55ccd55182b29a7f1"
PIN = HERE / "historical/manifest.json"
OUTPUT = ROOT / "verification/beyond-jbmc"
JDK = Path.home() / ".sdkman/candidates/java/25.0.5.0+8-tem"
MODELS = Path("/usr/lib/core-models.jar")
JBMC = Path("/usr/bin/jbmc")


def encoded(obj):
    return (json.dumps(obj, indent=1, ensure_ascii=False) + "\n").encode()


def git_bytes(rev, path):
    return subprocess.check_output(["git", "show", f"{rev}:{path}"], cwd=ROOT)


def relative(path):
    return Path(path).relative_to(ROOT).as_posix()


def statement(case):
    # nativeStrict is a test expectation about a checker, not an input to its claim.
    fields = ("target", "classes", "before", "after", "assume", "assert", "throws", "unchangedUnless", "modes")
    return {key: case[key] for key in fields if key in case}


def input_files(cases):
    sources = {"conformance": [benchmark.CONFORMANCE_SOURCE]}
    for version, tree in benchmark.versions().items():
        sources[version] = sorted((benchmark.HERE / tree).rglob("*.java"))
    for case in (case for case in cases if case["group"] == 4):
        paths = sorted((ROOT / case["app"] / "src/main/java").rglob("*.java"))
        sources[case["before"]] = paths
        sources[case["after"]] = [*paths, Path(case["patch"])]
    sources["jvm-oracles"] = [benchmark.RUNNER_SOURCE, benchmark.HERE / "Reference.java"]
    return sources


def population():
    scores = freeze()
    archive = json.loads(FROZEN.read_bytes())
    rows = archive["cases"]
    ids = [r["id"] for r in rows]
    current = benchmark.load_cases({1, 2, 3, 4})
    by_id = {c["id"]: c for c in current}
    if len(rows) != 187 or len(set(ids)) != 187 or len(current) != len(by_id):
        raise ValueError("duplicate IDs or wrong population size")
    cases = [by_id[i] for i in ids]
    for row, case in zip(rows, cases):
        if any(row[k] != case[k] for k in row):
            raise ValueError("archived claim identity drift: " + case["id"])
    return cases, [{**r, **statement(c), "archived": scores[c["id"]]["historical"]} for r, c in zip(rows, cases)]


def make_pin():
    cases, rows = population()
    old = {}
    for file in ("conformance.json", "corpus.json"):
        for row in json.loads(git_bytes(ORIGINAL, "lib/benchmark/" + file))["cases"]:
            old[row["id"]] = row
    for c in cases:
        if c["group"] == 4:
            folder = Path(c["patch"]).parent
            sidecar = ROOT / c["source"] / "example.json"
            if git_bytes(ORIGINAL, relative(sidecar)) != sidecar.read_bytes():
                raise ValueError("historical recorded example changed: " + str(folder))
            continue
        if statement(c) != statement(old[c["id"]]):
            raise ValueError("historical statement changed: " + c["id"])
    sources = input_files(cases)
    files = {relative(p): hashlib.sha256(git_bytes(ORIGINAL, relative(p))).hexdigest()
             for p in sorted({p for paths in sources.values() for p in paths})}
    java = JDK / "bin/java"
    checker = ROOT / "lib/target/release/jvmcontract"
    if subprocess.check_output(["git", "rev-parse", START + ":lib/src"], cwd=ROOT).strip() != b"61ade3dd4715d99f6fbc88223b50418d6a44ae8a":
        raise ValueError("unexpected opening checker tree")
    PIN.write_bytes(encoded({
        "format": "beyond-jbmc-historical/v1", "openingCommit": START, "historicalCommit": ORIGINAL,
        "archive": {"file": relative(FROZEN), "sha256": FROZEN_SHA},
        "openingBinaries": {p.name: digest(p) for p in (checker, java, JDK / "bin/javac", JDK / "lib/modules", JBMC, MODELS)},
        "settings": {"jdk": "Temurin 25.0.5+8", "jbmc": "6.11.0 ubuntu-24.04", "groups": [1, 2, 3, 4],
                     "engines": ["native", "jbmc"], "modes": ["strict"], "jbmcStaging": ["staged"],
                     "timeout": 120, "maxArrayLength": 8, "unwind": 16, "referenceSearch": 200000},
        "sourceGraphs": {k: [relative(p) for p in v] for k, v in sources.items()}, "filesSha256": files, "cases": rows,
    }))


def check_pin(folder):
    pin = json.loads(PIN.read_bytes())
    cases, rows = population()
    if rows != pin["cases"]:
        raise ValueError("the selected statements differ from the pin")
    if {k: [relative(p) for p in v] for k, v in input_files(cases).items()} != pin["sourceGraphs"]:
        raise ValueError("the source graphs differ from the pin")
    source = folder / "Conformance.java"
    shutil.copyfile(benchmark.CONFORMANCE_SOURCE, source)
    old_hash = pin["filesSha256"][relative(benchmark.CONFORMANCE_SOURCE)]
    if digest(source) != old_hash:
        subprocess.run(["patch", "--batch", "--fuzz=0", str(source), str(HERE / "historical/restore-source.patch")],
                       cwd=folder, check=True, stdout=subprocess.DEVNULL)
    for path, sha in pin["filesSha256"].items():
        actual = source if ROOT / path == benchmark.CONFORMANCE_SOURCE else ROOT / path
        if digest(actual) != sha:
            raise ValueError("historical program or oracle changed: " + path)
    for tool in (JDK / "bin/java", JDK / "bin/javac", JDK / "lib/modules", JBMC, MODELS):
        if digest(tool) != pin["openingBinaries"][tool.name]:
            raise ValueError("toolchain differs from the preregistered profile: " + tool.name)
    return pin, source


def run(phase, out):
    out.mkdir(parents=True, exist_ok=True)
    checker = Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")).resolve()
    os.environ.update(JAVA_HOME=str(JDK), JVMCONTRACT_JAR_RELEASE="25", PATH=str(JDK / "bin") + os.pathsep + os.environ["PATH"])
    with tempfile.TemporaryDirectory(prefix="beyond-jbmc-history-") as tmp:
        build = Path(tmp)
        pin, source = check_pin(build)
        ids = [r["id"] for r in pin["cases"]]
        options = argparse.Namespace(groups="1,2,3,4", cases=None, selection="beyond-jbmc/historical-187",
                                     engines="native,jbmc", modes="strict", jbmc_staging="staged", timeout=120,
                                     search=200000, build=build, jvmcontract=str(checker), jbmc=str(JBMC), quiet=False)
        with zipfile.ZipFile(out / "executions.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            def retain(case, engine, cmd, measured, work):
                key = case["id"] + "/" + engine + "/"
                archive.writestr(key + "argv.json", encoded(cmd))
                for stream in ("stdout", "stderr"):
                    archive.writestr(key + stream, measured[stream])
                harness = work / "harness"
                for path in sorted(harness.glob("*")):
                    if path.suffix in (".class", ".java"):
                        archive.write(path, key + "harness/" + path.name)
            result = benchmark.run(options, case_ids=ids, conformance_source=source, record_execution=retain)
    expected = [(cid, e) for cid in ids for e in ("native", "jbmc")]
    if [(r["case"], r["engine"]) for r in result["runs"]] != expected:
        raise ValueError("incomplete or duplicate result rows")
    for key, value in pin["settings"].items():
        if key not in ("jdk", "jbmc") and result["settings"].get(key) != value:
            raise ValueError("run drifted from profile: " + key)
    if any(not row["agrees"] for row in result["reference"].values()) or len(result["reference"]) != 25:
        raise ValueError("original JVM references disagreed or are incomplete")
    result["manifestSha256"] = digest(PIN)
    result["binaries"] = {**pin["openingBinaries"], "jvmcontract": digest(checker)}
    result["rawExecutionsSha256"] = digest(out / "executions.zip")
    (out / "results.json.gz").write_bytes(gzip.compress(encoded(result), mtime=0))
    print(phase, len(ids), dict(Counter((r["engine"], r["class"]) for r in result["runs"])), flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["pin", "check", "opening", "closing"])
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    if args.action == "pin":
        make_pin()
    elif args.action == "check":
        with tempfile.TemporaryDirectory() as tmp:
            pin, _ = check_pin(Path(tmp))
            print(len(pin["cases"]), "original statements;", len(pin["filesSha256"]), "original source and oracle files verified")
    else:
        run(args.action, args.output or OUTPUT / args.action / "historical")

"""Re-run the untouched first Parquet ranking and count physical index builds, native requests and JVM observations."""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def run_snapshot(work, checker, jdk):
    sys.path.insert(0, str(work / "examples/tools"))
    from targets import change_plan, class_binding, entry_binding, entry_discovery

    measured = Counter()
    def count(owner, name, key):
        original = getattr(owner, name)
        def wrapped(*args, **kwargs):
            measured[key] += 1
            return original(*args, **kwargs)
        setattr(owner, name, wrapped)
    count(entry_discovery.Artifact, "__init__", "archiveScans")
    count(class_binding, "ask", "checkerBatches")
    count(entry_binding, "observe", "jvmProbes")
    graphs = json.loads((ROOT / "verification/product-behaviour/cases/J08/bindings.json").read_bytes())
    args = []
    selectors = ("org.apache.parquet.column.values.fallback.FallbackValuesWriter#reset()V",
                 "org.apache.parquet.column.values.fallback.FallbackValuesWriter#resetDictionary()V",
                 "org.apache.parquet.column.values.dictionary.DictionaryValuesWriter#resetDictionary()V")
    for side, doc in graphs.items():
        for artifact in doc["classpath"]:
            artifact["file"] = str(Path.home()/".cache/in-the-loop/organic-pr-20"/artifact["file"])
        path = work / (side + ".json")
        path.write_text(json.dumps(doc))
        args.extend(["--before" if side == "old" else "--after", str(path)])
    out = work / "observed.json"
    change_plan.main(["application", *args, "--checker", str(checker), "--jdk", str(jdk), "--output", str(out),
                      *[arg for selector in selectors for arg in ("--changed-selector", selector)]])
    observed = json.loads(out.read_bytes())
    first = json.loads((HERE / "parquet-first.json").read_bytes())
    comparisons = {"candidates": first["candidates"] == observed["inventory"]["candidates"],
                   "bindings": first["bindings"] == observed["entryBindings"],
                   "changedDefinitions": first["changedDefinitions"] == observed["inventory"]["changedDefinitions"],
                   "coverage": first["coverage"] == observed["inventory"]["coverage"]}
    if not all(comparisons.values()) or dict(measured) != first["measurements"]:
        raise ValueError(f"frozen transfer differs: {comparisons}, {measured}")
    return {"measurements": dict(measured), "identicalToFirstTransfer": comparisons,
            "firstResultSha256": hashlib.sha256((HERE/"parquet-first.json").read_bytes()).hexdigest(),
            "frozenSourceSha256": hashlib.sha256((HERE/"transfer-source.zip").read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checker", type=Path, default=ROOT/"lib/target/release/jvmcontract")
    parser.add_argument("--jdk", type=Path, default=Path.home()/".sdkman/candidates/java/21.0.13.0+9-tem")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="frozen-entry-transfer-") as tmp:
        work = Path(tmp)
        with zipfile.ZipFile(HERE / "transfer-source.zip") as frozen:
            base = frozen.read("base-revision.txt").decode().strip()
            source = subprocess.check_output(["git", "archive", base, "examples/tools"], cwd=ROOT)
            with tarfile.open(fileobj=io.BytesIO(source)) as original:
                original.extractall(work, filter="data")
            pins = json.loads((HERE / "transfer-freeze.json").read_bytes())
            for name in frozen.namelist():
                if name == "base-revision.txt":
                    continue
                path = Path(name)
                if path.is_absolute() or ".." in path.parts or path.parts[:3] != ("examples", "tools", "targets"):
                    raise ValueError("file outside the frozen product sources")
                data = frozen.read(name)
                expected = pins.get(path.relative_to("examples/tools/targets").as_posix())
                if expected and hashlib.sha256(data).hexdigest() != expected:
                    raise ValueError(f"frozen source differs: {name}")
                (work/path).write_bytes(data)
        receipt = run_snapshot(work, args.checker.resolve(), args.jdk.resolve())
        args.output.write_text(json.dumps(receipt, indent=2) + "\n")
        print(receipt["measurements"])


if __name__ == "__main__":
    main()

"""Freeze the discoverer before the J08 transfer. The measurement reads only the deployment and changed declarations."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_evidence, change_inventory, upgrade_replay

OUT = ROOT / "verification/classpath-entry-discovery"
TOOLS = ROOT / "examples/tools/targets"
JDK = Path.home() / ".sdkman/candidates/java/21.0.13.0+9-tem"
J08 = ROOT / "verification/product-behaviour/cases/J08"
FALLBACK = "org.apache.parquet.column.values.fallback.FallbackValuesWriter"
DICT = "org.apache.parquet.column.values.dictionary.DictionaryValuesWriter"
CHANGED = [FALLBACK + "#reset()V", FALLBACK + "#resetDictionary()V", DICT + "#resetDictionary()V"]
FILES = ["change_plan.py", "change_inventory.py", "entry_binding.py", "entry_discovery.py", "deployment_graph.py",
         "runtime_jar.py", "class_binding.py", "java/UpgradeClassLookup.java"]


def freeze():
    return {name: upgrade_replay.sha(TOOLS / name) for name in FILES}


def transfer(destination, reverse=False):
    inputs = json.loads((J08 / "bindings.json").read_bytes())
    base = Path.home() / ".cache/in-the-loop/organic-pr-20"
    with tempfile.TemporaryDirectory(prefix="entry-transfer-") as tmp:
        work = Path(tmp)
        args = []
        for side, graph in inputs.items():
            for row in graph["classpath"]:
                row["file"] = str(base / row["file"])
            if reverse:
                graph["classpath"][0], graph["classpath"][2] = graph["classpath"][2], graph["classpath"][0]
            path = work / (side + ".json")
            change_evidence.write_json(path, graph)
            args.extend(["--before" if side == "old" else "--after", str(path)])
        plan = work / "plan.json"
        subprocess.run([sys.executable, ROOT / "examples/tools/build.py", "--change-plan", "application", *args,
                        "--jdk", JDK, "--checker", os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract"),
                        *[a for m in CHANGED for a in ("--changed-selector", m)], "--output", plan], check=True)
        report = json.loads(plan.read_text())
        inv = report["inventory"]
        value = {"schema": "java-entry-transfer/v1", "case": "J08", "inputMode": "changed selectors; nominated entry withheld",
                 "order": "reversed overlay control" if reverse else "original deployment", "implementation": freeze(),
                 "inputSha256": upgrade_replay.sha(J08 / "bindings.json"), "selectors": CHANGED,
                 "coverage": inv["coverage"], "candidateCount": inv["candidateCount"], "truncated": inv["truncated"],
                 "candidates": inv["candidates"], "changedDefinitions": inv["changedDefinitions"],
                 "deployments": {s: report["launches"][s]["production"] for s in ("old", "new")},
                 "bindings": report["entryBindings"], "manualProviderIndices": 0,
                 "measurements": {"archiveScans": inv["coverage"]["archiveScans"], "checkerBatches": report["discovery"]["checkerBatches"],
                                  "jvmProbes": report["discovery"]["jvmProbes"]}}
        with destination.open("x") as stream:
            json.dump(value, stream, separators=(",", ":"))
            stream.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--freeze", type=Path)
    args = parser.parse_args()
    if args.freeze:
        expected = json.loads(args.freeze.read_bytes())
        if expected != freeze():
            parser.error("implementation differs from the frozen first transfer")
    transfer(args.output, args.reverse)

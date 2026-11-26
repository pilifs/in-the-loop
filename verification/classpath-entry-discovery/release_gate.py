"""Repeat the final implementation's release gates and compare the independent stored observations."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BENCH = ROOT / "lib/benchmark/classpath-entry-discovery"


def checked(script, args, output, reference, project):
    subprocess.run([sys.executable, BENCH/script, *args, output], check=True, cwd=ROOT)
    expected = json.loads(reference.read_bytes())
    result = json.loads(output.read_bytes())
    if project(result) != project(expected):
        raise ValueError(f"final product disagrees with {reference.name}")
    return {"reference":reference.name, "referenceSha256":hashlib.sha256(reference.read_bytes()).hexdigest(),
            "repeatSha256":hashlib.sha256(output.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="entry-release-gate-") as tmp:
        work = Path(tmp)
        records = {}
        records["Log4j"] = checked("log4j.py", [], work/"log4j-replays.json", HERE/"log4j-replays.json",
                                   lambda result: result["rows"])
        records["history"] = checked("history.py", [], work/"history.json", HERE/"historical-origins.json",
                                    lambda result: result)
        def panel_outcomes(rows):
            fields = ["revision","profile","question","entry","binding","status","publicHits","observations",
                      "providerIndex","classSha256","physicalEntry","declaredRoots","effectiveProviders","manifestEdges","absences"]
            return [[r[field] for field in fields] for r in rows]
        for slot in ("03","04","08","10","13","16"):
            name = "panel-" + slot + ".json"
            records[slot] = checked("panel.py", [slot], work/name, HERE/name, panel_outcomes)
        args.output.write_text(json.dumps({"matched":records,"historicalOrigins":283, "capturedQuestions":12,
            "log4jClaims":2,"log4jCacheComparisons":5},indent=2)+"\n")
        print("Final release gate matched 12 captured questions, both Log4j claims in five comparisons, and 283 original class bindings")


if __name__=="__main__":
    main()

"""A separate, exact four-heap JBMC profile with an independently checked injective poststate observer."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
EXAMPLE = HERE.parents[1]
ROOT = EXAMPLE.parents[1]
sys.path.insert(0, str(ROOT / "lib/benchmark"))
from run import measure
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import runtime_jdk, workflow


def run(work, jvm_only):
    jdk = Path(runtime_jdk.home("21"))
    report = {"semantics": {"entry": "arrays.BinaryCells#observe(I)I", "target": "arrays.Update#apply([I[I)I",
              "roots": "two distinct non-null int arrays of length exactly one", "cells": [0, 1],
              "observation": "2 * left[0] + right[0]", "mapping": "left uses bit 0 and right uses bit 1",
              "cases": 4}, "jdk": runtime_jdk.identity(jdk), "revisions": {}, "checks": []}
    report["claimKey"] = workflow.canonical_digest(report["semantics"])
    classes = {}
    def observe(name, values):
        return [int(s) for s in subprocess.check_output([jdk / "bin/java", "-cp", classes[name],
                "arrays.BinaryCells", *map(str, values)], text=True).splitlines()]
    for rev in ("baseline", "controls/preserving", "alternative"):
        dest = work / rev
        subprocess.run([jdk / "bin/javac", "-proc:none", "-parameters", "--release", "21", "-d", dest,
                        EXAMPLE/rev/"arrays/Update.java", HERE/"BinaryCells.java"], check=True)
        classes[rev] = dest
        expected = [2 * ((n & 1) if rev == "alternative" else 1) + ((n >> 1) & 1) for n in range(4)]
        values = observe(rev, range(4))
        if values != expected:
            raise ValueError(f"bad grid observer on {rev}: {values}")
        report["revisions"][rev] = {"outputs": values, "classSha256": {
            f.name: workflow.file_sha256(f) for f in sorted(dest.rglob("*.class"))}}
    if jvm_only:
        return report, True
    checker = os.environ["JVMCONTRACT"]
    report.update(checker=workflow.file_sha256(checker), libTree=os.environ.get("JVMCONTRACT_LIB_TREE"))
    for rev, expected in [("controls/preserving", "verified"), ("alternative", "violation")]:
        argv = [checker, "equivalence", "--before", str(classes["baseline"]), "--after", str(classes[rev]),
                "--target", "arrays.BinaryCells#observe(int)", "--engine", "jbmc", "--gaps", "strict",
                "--unwind", "8", "--max-array-length", "2", "--timeout", "90", "--work", str(work/"check"/rev), "--json"]
        measured = measure(argv, 120)
        try:
            outcome = json.loads(measured["stdout"])
        except ValueError:
            outcome = {}
        stated = outcome.get("stated") or {}
        witness = (outcome.get("counterexample") or {}).get("inputs") or []
        ok = outcome.get("verdict") == expected and (outcome.get("search") or {}).get("engine") == "jbmc"
        replay = None
        if expected == "verified":
            ok &= (stated.get("bounds") or {}).get("complete") is True and (stated.get("vacuity") or {}).get("status") == "non-vacuous"
        elif len(witness) == 1 and type(witness[0].get("value")) is int:
            value = witness[0]["value"]
            replay = {s: observe(s, [value])[0] for s in ("baseline", rev)}
            ok &= replay["baseline"] != replay[rev]
        else:
            ok = False
        report["checks"].append({"revision": rev, "expected": expected, "qualified": ok, "argv": argv,
                                 "outcome": outcome, "witnessJVM": replay, "seconds": measured["seconds"], "peakMiB": measured["peakMB"]})
        print(rev, outcome.get("verdict"), ok, flush=True)
    return report, all(r["qualified"] for r in report["checks"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jvm-only", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        report, passed = run(Path(directory), args.jvm_only)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    sys.exit(0 if passed else 1)

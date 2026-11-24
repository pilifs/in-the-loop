"""Exercise the independent pilot through the public example command using its frozen consumer."""

import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

from challenge import isolation
from frozen_range import INT_BINARY, int_kernel
from prepare import HERE, digest
from replay import measured

ROOT = HERE.parents[2]
CASES = (
    ("336", "first-any-length", "established", "independently established"),
    ("346", "first-any-length", "established", "independently established"),
    ("337", "fill-any-length", "established", "independently established"),
    ("337", "caller-any-length", "established", "independently established"),
    ("337", "caller-extra-any-length", "unresolved", "checked counterexample"),
)


def standard(command, expected):
    run = measured([sys.executable, "-B", ROOT / "examples/tools/build.py", *command], ROOT)
    if run["exit"] != expected:
        raise ValueError(f"{command}: exit {run['exit']}: {run['stdout']}")
    return run


def pilot(out):
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        start = time.monotonic()
        kernel = int_kernel(work / "frozen")
        compilation = time.monotonic() - start
        denied = isolation(kernel)
        for number, claim, primary, independent in CASES:
            key = f"{number}/{claim}"
            args = [number, "--array-induction", claim]
            plain = standard([*args, "--compare"], 0)
            if "the same result" not in plain["stdout"]:
                raise ValueError(f"{key}: ordinary comparison changed")
            destination = out / (key.replace("/", "-") + ".json")
            checked = standard([*args, "--second-opinion", "--kernel", kernel, "--output", destination],
                               0 if independent == "independently established" else 1)
            receipt = json.loads(destination.read_bytes())
            if (receipt["ordinary"]["status"], receipt["assurance"]) != (primary, independent):
                raise ValueError(f"{key}: {receipt.get('reason', receipt['assurance'])}")
            rows.append({"key": key, "ordinary": primary, "independent": independent, "externalRequest": receipt["request"],
                         "classes": receipt["deployment"]["classes"], "sha256": digest(destination.read_bytes()),
                         "receipt": destination.name, "ordinaryCompareWallSeconds": plain["wallSeconds"],
                         "optInWallSeconds": checked["wallSeconds"], "ordinaryComparePeakKiB": plain["peakKiB"],
                         "optInPeakKiB": checked["peakKiB"]})
        cert = HERE / "evidence/range-proof/fill-any-length.cert"
        invalid = out / "callee-only-for-caller.json"
        standard(["337", "--array-induction", "caller-any-length", "--second-opinion", "--kernel", kernel,
                  "--certificate", cert, "--output", invalid], 1)
        rejected = json.loads(invalid.read_bytes())
        if (rejected["ordinary"]["status"], rejected["assurance"], rejected["independent"]["stdout"]) != (
                "established", "invalid evidence", "rejected certificate does not bind external request"):
            raise ValueError("callee-only evidence received caller credit")
        summary = {"schema": "array-second-opinion-pilot/v1", "checkerSha256": INT_BINARY,
                   "compilationSeconds": compilation, "isolationReadDenials": denied, "cases": rows,
                   "calleeOnly": {"key": "337/caller-any-length/callee-only", "receipt": invalid.name,
                                  "sha256": digest(invalid.read_bytes()), "outcome": rejected["assurance"]}}
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print([(r["key"], r["independent"]) for r in rows])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    pilot(parser.parse_args().output)

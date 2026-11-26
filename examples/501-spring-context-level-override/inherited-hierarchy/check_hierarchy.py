"""Replay both historical hierarchies and their five Spring 7.1.0 comparisons."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "verification/merged-pr-links/m01-m10"))
import releases


def check():
    comparison = releases.comparison
    pins = comparison.replay(HERE)["deployments"]["pins"]
    inputs = HERE / "release-inputs.json"
    lock = comparison.read(inputs)
    cache = Path.home() / ".cache/in-the-loop" / lock["cache"]
    number = "501"
    measured = releases.measure(number, lock["projects"][number], lock, cache, False, inputs)
    if [measured] != comparison.read(HERE / "release-observations.json"):
        raise ValueError("published-release outcomes or provenance differ")
    merged = [(r["id"], r["outcome"]) for r in pins["observations"] if r["side"] == "fix"]
    released = [(r["question"], r["outcome"]) for r in measured["versions"]["7.1.0"]["observations"]]
    if released != merged or len(released) != 5:
        raise ValueError("inherited and directly declared hierarchy histories differ from the landing")
    return [measured]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print("Ten historical comparisons and five published-release comparisons matched the recorded outcomes.")

"""Compare each published deployment with its named historical side and caller bytes."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "m01-m10"))
from releases import check_observations

# The published 2.1.0 result path stops silently. Both PR pins publish a retry event.
CHANGES = {("582", "2.1.0"): {"resilience4j/resilience4j#2067.3": {"return": "calls=1,retries=[],errors=0,again"}}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=HERE / "release-observations.json")
    args = parser.parse_args()
    reference = json.loads((HERE / "release-references.json").read_text())
    count = check_observations(HERE / "release-inputs.json", args.results, reference, CHANGES)
    print(f"{count} public release observations verified.")

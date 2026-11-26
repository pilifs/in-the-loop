"""Check the Q-series release comparisons and the changed reply-selector behavior."""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "m01-m10"))
from releases import check_observations

VERSIONS = {
    "513": {"7.1.0": "fix"},
    "514": {"6.2.13": "parent", "7.1.0": "fix"},
    "520": {"7.1.0": "fix"},
    "524": {"5.0.0.M3": "parent", "5.0.0.M4": "fix"},
    "531": {"7.0.4": "fix"},
    "534": {"7.0.9": "parent", "7.1.0": "fix"},
    "536": {"7.1.0": "fix"},
}
# The release selects correlated replies. The unchanged responder sends plain text.
CHANGES = {("531", "7.0.4"): {
    "spring-projects/spring-framework#36162.1": {"return": "replies:missing"},
    "spring-projects/spring-framework#36162.3": {"return": "replies:missing/replies:missing/ack-A"},
}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=HERE / "release-observations.json")
    args = parser.parse_args()
    count = check_observations(HERE / "release-inputs.json", args.results, VERSIONS, CHANGES)
    print(f"{count} release observations verified, including the two changed JMS reply histories.")

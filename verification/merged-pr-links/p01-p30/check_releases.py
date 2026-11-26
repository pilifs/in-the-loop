"""Bind each published-release result to its registered caller, classpath and measured historical side."""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "m01-m10"))
from releases import check_observations as check

# The last entry is the reported version of the eager listener's double delivery.
HISTORICAL = {
    "482": ("5.1.6.RELEASE", "5.2.0.M1"), "486": ("5.1.0.RC1", "5.1.0.RC2"),
    "488": ("5.0.0.RC4", "5.0.0.RELEASE"), "493": ("5.1.4.RELEASE", "5.1.5.RELEASE"),
    "495": ("5.2.7.RELEASE", "5.3.0-M1"), "496": ("5.2.0.RC2", "5.2.0.RELEASE"),
    "500": ("5.1.4.RELEASE", "5.1.5.RELEASE"), "503": ("5.3.18",),
}
CURRENT = ("481", "484", "489", "504")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical", type=Path, default=HERE / "historical-observations.json")
    parser.add_argument("--release", type=Path, default=HERE / "release-observations.json")
    args = parser.parse_args()
    versions = {n: dict(zip(v, ("parent", "fix"))) for n, v in HISTORICAL.items()}
    historical = check(HERE / "historical-inputs.json", args.historical, versions)
    current = check(HERE / "release-inputs.json", args.release, {n: {"7.1.0": "fix"} for n in CURRENT})
    print(f"{historical} historical-release and {current} Spring 7.1.0 histories match the corresponding original observations.")

"""Bind each published-release result to its registered caller, classpath and measured historical side."""
import argparse
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import public_comparison as comparison

# The last entry is the reported version of the eager listener's double delivery.
HISTORICAL = {
    "482": ("5.1.6.RELEASE", "5.2.0.M1"), "486": ("5.1.0.RC1", "5.1.0.RC2"),
    "488": ("5.0.0.RC4", "5.0.0.RELEASE"), "493": ("5.1.4.RELEASE", "5.1.5.RELEASE"),
    "495": ("5.2.7.RELEASE", "5.3.0-M1"), "496": ("5.2.0.RC2", "5.2.0.RELEASE"),
    "500": ("5.1.4.RELEASE", "5.1.5.RELEASE"), "503": ("5.3.18",),
}
CURRENT = ("481", "484", "489", "504")


def check(lock_file, result_file, references):
    lock = comparison.read(lock_file)
    results = comparison.read(result_file)
    if list(lock["projects"]) != list(references) or [r["example"] for r in results] != list(references):
        raise ValueError("release example missing, duplicated or reordered")
    total = 0
    for r in results:
        number = r["example"]
        folder, = (ROOT / "examples").glob(number + "-*")
        spec = comparison.read(folder / "comparison.json")
        physical = comparison.read(folder / "observations.json")["deployments"]["pins"]
        project = lock["projects"][number]
        roles = references[number]
        if (r["releaseInputsSha256"] != comparison.upgrade_replay.sha(lock_file)
                or r["historicalObservationsSha256"] != comparison.upgrade_replay.sha(folder / "observations.json")
                or r["jdkReleaseSha256"] != project["jdkReleaseSha256"] or r["callerClasses"] != physical["callerClasses"]
                or list(r["versions"]) != list(roles) or list(project["versions"]) != list(roles)):
            raise ValueError(f"{number}: different lock, caller or released version")
        for version, side in roles.items():
            measured = r["versions"][version]
            coordinates = project["versions"][version]
            classpath = [{"coordinate": k, "sha256": lock["sha256"][k]} for k in coordinates]
            if measured["classpath"] != classpath:
                raise ValueError(f"{number} {version}: altered classpath or digest")
            actual = [row for row in physical["observations"] if row["side"] == side]
            if [r["id"] for r in actual] != [q["id"] for q in spec["questions"]]:
                raise ValueError(f"{number}: reordered original histories")
            expected = [{"question": q["id"], "outcome": row["outcome"],
                         "matchesMergedPrediction": comparison.agrees(q["expected"]["fix"], row["outcome"])}
                        for q, row in zip(spec["questions"], actual, strict=True)]
            if measured["observations"] != expected:
                raise ValueError(f"{number} {version}: differs from the {side} observations")
            total += len(expected)
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical", type=Path, default=HERE / "historical-observations.json")
    parser.add_argument("--release", type=Path, default=HERE / "release-observations.json")
    args = parser.parse_args()
    versions = {n: dict(zip(v, ("parent", "fix"))) for n, v in HISTORICAL.items()}
    historical = check(HERE / "historical-inputs.json", args.historical, versions)
    current = check(HERE / "release-inputs.json", args.release, {n: {"7.1.0": "fix"} for n in CURRENT})
    print(f"{historical} historical-release and {current} Spring 7.1.0 histories match the corresponding original observations.")

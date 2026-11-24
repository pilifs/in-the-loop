"""Intersect only the named projects with the committed blind draw. Never print its other rows."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECTS = {
    "ThreeTen/threetenbp#77": ["threetenbp", "threeten", "threetenbp.org"],
    "apache/poi#1420": ["apache-poi", "poi.apache.org", "apache-poi4"],
    "google/libphonenumber#2272": ["libphonenumber", "google-libphonenumber"],
    "unicode-org/icu#3249": ["icu4j", "icu", "icu.unicode.org"],
    "apache/commons-io#520": ["commons-io"],
    "apache/commons-collections#628": ["commons-collections4", "commons-collections3", "commons-collections"],
    "apache/commons-collections#755": ["commons-collections4", "commons-collections3", "commons-collections"],
    "apache/logging-log4j2#1173": ["log4j2", "log4j2-java", "logging.apache.org"],
    "apache/commons-lang#1839": ["commons-lang3", "commons-lang"],
    "google/gson#3098": ["google-gson", "gson"],
}


def check():
    area = Path.home() / ".cache/in-the-loop/beyond-jbmc/panel"
    raw = (area / "sealed.json").read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    if checksum != (HERE.parent / "beyond-jbmc/panel.sha256").read_text().split()[0]:
        raise ValueError("blind commitment mismatch")
    pairs = json.loads(raw)["pairs"]
    if len(pairs) != 16:
        raise ValueError("blind population size mismatch")
    def names(pair):
        packages = {pair[key].lower().removesuffix("-java") for key in ("source", "artifact")}
        return {pair["project"].lower(), *packages, *(p.removeprefix("lib") for p in packages)}
    return {"commitment": checksum, "population": len(pairs), "projectOverlap": {
        pr: any(names(row) & ({'github.com/' + pr.split('#')[0].lower()} | set(aliases))
                for row in pairs) for pr, aliases in PROJECTS.items()},
        "priorDisclosedWork": "Example 310 uses ThreeTenBP at a different commit and public operation."}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))

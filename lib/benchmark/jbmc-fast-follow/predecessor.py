"""Repeat the predecessor at its original bounds and reject loss of a qualified decision."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "java-semantics-gap"))
from campaign import CLAIMS, ROOT, measure as measure_caller
from decimal_transfer import paired as measure_decimal
from historical import GROUPS, measure as measure_history

PRIOR = ROOT / "verification/java-semantics-gap/decimal-transfer"
DEST = ROOT / "verification/jbmc-fast-follow/regressions"


def load(path):
    return json.loads(path.read_bytes())


def callers():
    for key in CLAIMS:
        now = measure_caller(key, "callers", ["native", "jbmc"], DEST)
        previous = load(PRIOR / "callers" / key / "measurement.json")
        for field in ("classes", "classpath", "claimsSha256", "adapterSha256", "jvmSha256", "modulesSha256", "originalJvm"):
            if now[field] != previous[field]:
                raise ValueError(f"{key}: different {field}")
        old = {(r["method"], r["engine"]): r for r in previous["runs"]}
        if set(old) != {(r["method"], r["engine"]) for r in now["runs"]}:
            raise ValueError(f"{key}: incomplete repeat")
        for r in now["runs"]:
            earlier = old[r["method"], r["engine"]]
            if earlier["disposition"] == "correct" and (r["disposition"], r["verdict"]) != ("correct", earlier["verdict"]):
                raise ValueError(f"{key}/{r['method']}: lost {r['engine']} decision")
            if r["engine"] == "native" and r["verdict"] == "verified" and r["expected"] != "verified":
                raise ValueError(f"{key}/{r['method']}: native proof contradicted by the JVM")


def history():
    for group in GROUPS:
        measure_history("historical", group, output_root=DEST)
        current = load(DEST / "historical" / (group + ".json"))
        old = load(PRIOR / "historical" / (group + ".json"))
        if current["cases"] != old["cases"] or current["frozenResultSha256"] != old["frozenResultSha256"]:
            raise ValueError(f"{group}: historical statements changed")
        prior = {(r["case"], r["engine"]): r for r in old["runs"]}
        for r in current["runs"]:
            before = prior[r["case"], r["engine"]]
            if before["class"] == "correct" and (r["class"], r["verdict"]) != ("correct", before["verdict"]):
                raise ValueError(f"{group}/{r['case']}: lost {r['engine']} decision")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scope", choices=("callers", "historical", "decimal"))
    scope = parser.parse_args().scope
    if scope == "callers": callers()
    elif scope == "historical": history()
    else: measure_decimal(dest=DEST / "decimal")

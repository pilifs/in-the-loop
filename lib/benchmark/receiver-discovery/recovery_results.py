"""Recount the same receiver cohort and check the new claims against the collector's receipts."""

import argparse
from collections import Counter
from functools import cache
import hashlib
import json
from pathlib import Path
import sys

from callers import ROOT, read, sha

sys.path.insert(0, str(ROOT / "verification"))
import layout


CONFIGURATIONS = ("commons-configuration-565", "commons-configuration-601")
XZ = "commons-compress-767"
SIDES = ("old", "new")
MEASUREMENTS = Path("verification/receiver-discovery")


def build(root):
    evidence = {}

    @cache
    def source(job):
        folder = layout.find_result(root, job)
        if not folder:
            raise ValueError("missing collected job " + job)
        path = folder / "result.json"
        run = read(path)
        # A collector can be on a different line from the committing workspace until they land.
        spec = layout.find_job(root, job) or layout.find_job(ROOT, job)
        if (run["id"] != job or run["status"] != "passed" or spec is None
            or read(spec) != run["job"]["spec"]
            or hashlib.sha256(json.dumps(run["job"]["spec"], sort_keys=True).encode()).hexdigest() != run["job"]["sha256"]):
            raise ValueError("different or incomplete job " + job)
        if run["sourceCommit"] == "0bd3b57768a815b304241fae840abba78bb0cb76":
            raise ValueError("VF-060 conflicted source export: " + job)
        evidence[job] = {"source": run["sourceCommit"], "receipt": str(path.relative_to(root)), "sha256": sha(path),
                         "replay": [step["run"] for step in run["job"]["spec"]["steps"]]}
        return run

    def measured(relative):
        path = MEASUREMENTS / relative
        record = read(root / path)
        run = source(record["job"])
        digest = sha(root / path)
        matching = [item for item in run["outputs"] if item["path"] == str(path)]
        if record["source"] != run["sourceCommit"] or len(matching) != 1 or matching[0]["sha256"] != digest:
            raise ValueError("unbound measurement " + str(path))
        if "receiptPackSha256" in record:
            pack = path.with_name("receipts.tar.gz")
            actual = sha(root / pack)
            if actual != record["receiptPackSha256"] or not any(item["path"] == str(pack) and item["sha256"] == actual for item in run["outputs"]):
                raise ValueError("unbound raw receipt pack " + str(pack))
        return record

    frozen = read(root / MEASUREMENTS / "scope.json")
    cohort = {}
    for i in range(1, 8):
        group = measured(f"transfer/final-cohort/{i:02}/measurement.json")
        if not group["searchStartupWitness"] or cohort.keys() & group["cases"].keys():
            raise ValueError("inconsistent cohort")
        cohort.update(group["cases"])
    if cohort.keys() != frozen["originalOverloads"].keys() or any(
        set(row["overloads"]) != set(frozen["originalOverloads"][case]) for case, row in cohort.items()
    ):
        raise ValueError("original paired overload population changed")
    original = {(case, side): row["sides"][side]["verdict"] for case, row in cohort.items() for side in SIDES}
    native = original.copy()
    witnesses = {}
    live = measured("recovery/live-table.json")
    controls = measured("recovery/installed-properties/controls.json")
    after_removal = measured("recovery/removed-property/controls.json")
    configurations = {}
    for case in CONFIGURATIONS:
        pin = frozen["registeredCallers"][case]
        data = measured(f"recovery/{case}/measurement.json")
        before_split = measured(f"recovery/installed-properties/{case}.json")
        after_split = measured(f"recovery/parsed-property/{case}.json")
        if (data["cases"] != pin["cases"] or data["originalSourceReceiptSha256"] != pin["sha256"]
            or pin["sha256"] != sha(root / pin["reference"])):
            raise ValueError("different registered caller " + case)
        for side in SIDES:
            row = data["sides"][side]
            if row["classpath"] != pin["sides"][side]["orderedClasspathSha256"] or row["commit"] != pin["sides"][side]["commit"]:
                raise ValueError("different deployment " + case + "/" + side)
            profiles = row["profiles"]
            if (set(profiles) != {"default", "inherited-invalid", "own-invalid"}
                or any(len(profile) != len(data["cases"]) for profile in profiles.values())):
                raise ValueError("different profile selector census")
            for i, case_input in enumerate(data["cases"]):
                for label in ("default", "inherited-invalid"):
                    observed = profiles[label][i]
                    if observed != {"selector": i, "predicate": True, "originalCalls": [case_input["expected"]] * 2}:
                        raise ValueError("missing original normal outcome")
                invalid = profiles["own-invalid"][i]
                first, second = invalid["originalCalls"]
                if (invalid["selector"] != i or invalid["predicate"] is not False
                    or first["cause"][:2] != ["java.lang.ExceptionInInitializerError", "java.lang.IllegalArgumentException"]
                    or second["cause"][0] != "java.lang.NoClassDefFoundError"):
                    raise ValueError("missing erroneous-class witness")
            if set(row["trees"]["jvmBothReadOrders"].values()) != {"returned true"} or len(row["trees"]["jvmBothReadOrders"]) != 2:
                raise ValueError("missing two live-tree read orders")
            witness = row["ordinary"]["witness"]
            if (row["ordinary"]["status"] != "refuted" or witness["profile"] != "own-invalid"
                or witness["selector"] not in range(len(data["cases"]))):
                raise ValueError("reported ordinary witness differs from its replay")
            registered = data["registered"]["sides"][side]
            key = (case, side)
            native[key] = registered["verdict"]
            witnesses[key] = "own-invalid"
            configurations[case + "/" + side] = {
                "openingNative": original[key], "native": native[key], "nativeReason": registered["firstOutstanding"],
                "admittedOrdinary": "refuted", "selector": witness["selector"],
                "observations": [x["expected"]["return"] for x in data["cases"]],
                "source": row["commit"], "holder": row["property"], "classes": row["classBindings"], "job": data["job"],
                "installedBeforeSplit": {k: v["native"]["problem"] for k, v in before_split["rows"][side].items()},
                "installedJobs": [before_split["job"], after_split["job"]],
                "installedAfterSplit": {k: {"verdict": v["native"]["verdict"], "reason": v["native"]["problem"],
                                            "originalJvm": v["jvm"]} for k, v in after_split["rows"][side].items()},
            }

    prior_xz = measured("transfer/xz-ordinary-witnesses/measurement.json")
    original_with_witnesses = original.copy()
    xz_witness = measured("recovery/xz/clean-witnesses/measurement.json")
    xz_ordinary = measured("recovery/xz/clean-ordinary/measurement.json")
    xz_profiles = measured("recovery/xz/constructor-progress/measurement.json")
    xz = {}
    for side in SIDES:
        previous = prior_xz["sides"][side]["frame"]
        if previous["disposition"] == "refuted":
            original_with_witnesses[XZ, side] = "violation"
        row = xz_witness["sides"][side]["frame"]
        trial = row["attempts"][row["witnessPrestate"]]
        if row["disposition"] != "refuted" or trial["originalJvm"][-1] != "returned false" or trial["freshDefaultJvm"][-1] != "returned true":
            raise ValueError("missing XZ original prestate witness")
        native[XZ, side] = xz_ordinary["sides"][side]["frame"]["native"]["verdict"]
        witnesses[XZ, side] = row["witnessPrestate"]
        xz[side] = {
            "native": native[XZ, side], "admittedOrdinary": "refuted", "witnessSelector": trial["input"],
            "fixed": {k: {"verdict": v["native"]["verdict"], "firstOutstanding": v["native"]["problem"]}
                      for k, v in xz_profiles["sides"][side]["profiles"].items()},
        }
    parser = measured("recovery/javaparser/clean-ordinary/measurement.json")
    parser_profiles = measured("recovery/javaparser/clean-profiles/measurement.json")
    parsers = {}
    for side, roots in parser["sides"].items():
        profiles = parser_profiles["sides"][side]
        parsers[side] = {
            "ordinary": {k: v["native"]["verdict"] for k, v in roots.items()},
            "boundedNonNull": {k: v["verdict"] for k, v in profiles["boundedNonNullSeparator"].items()},
            "firstAndRepeatedFailure": profiles["profiles"]["erroneous"]["native"]["verdict"],
            "readPcs": profiles["propertyReadPcs"],
        }

    def decisions(rows):
        decided = {key for key, verdict in rows.items() if verdict in ("verified", "violation")}
        return {"sides": len(decided), "pairs": sum(all((case, side) in decided for side in SIDES) for case in cohort)}

    combined = native.copy()
    for key in witnesses:
        if combined[key] == "verified":
            raise ValueError("native proof contradicts JVM witness: " + "/".join(key))
        combined[key] = "violation"
    overloads = Counter(v["verdict"] for case in cohort.values() for v in case["overloads"].values())
    return {"schema": "receiver-recovery/v1", "configuration": configurations, "javaParser": parsers, "xz": xz,
            "table": {"physical": live["observations"], "openingJob": controls["job"], "closingJob": after_removal["job"],
                      "openingNative": {k: v["native"]["verdict"] for k, v in controls["rows"]["control"].items()},
                      "closingNative": {k: v["native"]["verdict"] for k, v in after_removal["rows"]["control"].items()}},
            "cohort": {"cases": len(cohort), "sides": len(original),
                       "bothReached": sum(all(s["jvmInputsReached"] == row["inputs"] for s in row["sides"].values()) for row in cohort.values()),
                       "openingNative": decisions(original), "closingNative": decisions(native),
                       "openingWithAdmittedStateWitnesses": decisions(original_with_witnesses),
                       "nativeOrAdmittedStateWitness": decisions(combined), "pairedOverloads": dict(overloads)},
            "evidence": evidence}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="checkout holding collected verification receipts")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build(args.root), indent=2) + "\n"
    if args.check:
        if rendered != (ROOT / MEASUREMENTS / "recovery/results.json").read_text():
            raise SystemExit("receiver recovery table differs from its collected evidence")
        print("checked receiver recovery results")
    else:
        sys.stdout.write(rendered)

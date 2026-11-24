"""Recount reached histories, registered claims and comparator matches from the job-bound receipts."""

import argparse
from collections import Counter, defaultdict
import json
from functools import cache
from hashlib import sha256
from pathlib import Path

from callers import ROOT, RESULTS, read, sha


def compact_native(row):
    result = {k: row[k] for k in ("verdict", "firstUnproved")}
    if row.get("originalReplay"):
        result["originalReplay"] = row["originalReplay"]
    return result


def matched(folder):
    pairs = defaultdict(dict)
    discrepancies = []
    for p in sorted(folder.glob("*/measurement.json")):
        record = read(p)
        for r in record["runs"]:
            key = (p.parent.name, r["method"])
            if r["engine"] in pairs[key]:
                raise ValueError(("duplicate engine", key))
            pairs[key][r["engine"]] = r["disposition"] == "correct"
            if r["disposition"] == "false-success":
                discrepancies.append(
                    {
                        "case": key[0],
                        "method": key[1],
                        "engine": r["engine"],
                        "expected": r["expected"],
                        "reported": r["verdict"],
                    }
                )
    if len(pairs) != 60 or any(set(v) != {"native", "jbmc"} for v in pairs.values()):
        raise ValueError("incomplete sixty-pair repeat")
    buckets = {"nativeOnly": [], "jbmcOnly": [], "shared": [], "unresolved": []}
    for (host, method), v in sorted(pairs.items()):
        k = (
            ("shared" if v["jbmc"] else "nativeOnly")
            if v["native"]
            else ("jbmcOnly" if v["jbmc"] else "unresolved")
        )
        buckets[k].append(host + "/" + method)
    return {
        "counts": {k: len(v) for k, v in buckets.items()},
        "pairs": buckets,
        "falseSuccess": discrepancies,
    }


def build():
    jobs = {}

    @cache
    def managed(job):
        date = job.split("-", 1)[0]
        folder = Path(date[:4]) / date[4:6] / date[6:8]
        receipt = ROOT / "verification/results" / folder / job / "result.json"
        record = read(receipt)
        submitted = ROOT / record["job"]["path"]
        if (
            record["id"] != job
            or submitted.stem != job
            or read(submitted) != record["job"]["spec"]
            or sha256(json.dumps(record["job"]["spec"], sort_keys=True).encode()).hexdigest()
            != record["job"]["sha256"]
        ):
            raise ValueError("different verification submission: " + job)
        jobs[job] = {
            "source": record["sourceCommit"],
            "status": record["status"],
            "result": receipt.relative_to(ROOT).as_posix(),
        }
        return record

    def verified(name):
        p = RESULTS / name / "measurement.json"
        doc = read(p)
        job = (
            "20261123-223108-compare-raw-and-factory-inputs-and-both"
            if name == "qualification/standalone"
            else doc["job"]
        )
        record = managed(job)
        if doc.get("source") and doc["source"] != record["sourceCommit"]:
            raise ValueError("measurement and verified source differ: " + name)
        if record["status"] != "passed" or not any(
            item["path"] == p.relative_to(ROOT).as_posix() and item["sha256"] == sha(p)
            for item in record["outputs"]
        ):
            raise ValueError("missing verified output for " + name)
        return doc

    scope = read(RESULTS / "scope.json")
    if sha(ROOT / scope["priorReceiverEvidence"]) != scope["priorReceiverSha256"]:
        raise ValueError("different opening receiver evidence")
    opening = {}
    for case in ["360", "366", "commons-configuration-565", "commons-configuration-601"]:
        d = verified("opening/" + case)
        if case.isdecimal():
            opening[case] = {
                env: dict(Counter(r["status"] for r in d["tasks"].values() if r["environment"] == env))
                for env in sorted({r["environment"] for r in d["tasks"].values()})
            }
        else:
            opening[case] = {k: v["verdict"] for k, v in d["sides"].items()}
    stock = verified("qualification/stock")["result"]
    sites = verified("qualification/sites")["result"]
    csv = verified("qualification/csv")["result"]
    standalone = verified("qualification/standalone")["cases"]
    training = {
        "stock": {
            k: {a: v[a]["verdict"] for a in ("automatic", "supplied") if a in v}
            for k, v in stock["claims"].items()
        },
        "replayedAliasBlind": stock["claims"]["unchanged"]["automaticWitness"],
        "sites": {k: {"disposition": v["actual"], "classSha256": v["binding"]} for k, v in sites.items()},
        "csv": {
            side: {
                k: {a: v[a] for a in ("pc", "disposition", "reachedSelectors", "violatingSelectors")}
                for k, v in d.items()
            }
            for side, d in csv.items()
        },
        "standalone": {
            k: {
                "user": [[a["property"], a["status"]] for a in d["userAssertions"]],
                "otherFailures": d["otherFailures"],
            }
            for k, d in standalone.items()
        },
    }
    conf = {}
    for case in ("commons-configuration-565", "commons-configuration-601"):
        d = verified("qualification/" + case)
        conf[case] = {
            side: {
                "registered": d["registered"]["sides"][side]["verdict"],
                "firstUnproved": d["registered"]["sides"][side]["firstOutstanding"],
                "lookupInputs": len(v["originalLookup"]),
                "selected": v["selected"],
                "isolation": {k: m["native"]["verdict"] for k, m in v["isolation"].items()},
                "producers": [p["producer"] for p in v["automatic"]["plans"]],
                "missed": v["automatic"]["missed"],
            }
            for side, v in d["sides"].items()
        }
    graph = verified("transfer/jgrapht")
    if graph["producerFreeze"] != sha(RESULTS / "generator-freeze.json") or graph["actionFreeze"] != sha(
        RESULTS / "action-freeze.json"
    ):
        raise ValueError("held-out graph used different frozen inputs")
    dg = {k: graph[k] for k in ("coveredGraphs", "coveredTransitions", "outcomes", "evaluatorJvm")}
    dg["producerSettings"] = [
        {
            "producer": c["producer"],
            "flags": c.get("flags"),
            "graphs": c["startingGraphs"],
            "transitions": len(c["transitions"]),
            "mismatches": len(c["mismatches"]),
            "missed": c["missed"],
        }
        for c in graph["automatic"]
    ]
    dg["strictIdentity"] = {
        "verdict": graph["strictIdentityControl"]["verdict"],
        "firstUnproved": graph["strictIdentityControl"]["problem"],
    }

    def replay_cohort(stage, searched):
        cases = {}
        for i in range(1, 8):
            group = verified(f"transfer/{stage}/{i:02}")
            if bool(group.get("searchStartupWitness")) != searched:
                raise ValueError("cohort selected a different search policy")
            for key, row in group["cases"].items():
                if key in cases:
                    raise ValueError("duplicate receiver case")
                cases[key] = row
        return cases

    earlier = replay_cohort("cohort", False)
    cohort = replay_cohort("final-cohort", True)
    if set(earlier) != set(cohort):
        raise ValueError("different final receiver population")
    if set(cohort) != set(scope["originalOverloads"]) or any(
        set(v["overloads"]) != set(scope["originalOverloads"][k]) for k, v in cohort.items()
    ):
        raise ValueError("different original receiver denominator")
    both = [
        k
        for k, v in cohort.items()
        if all(side["jvmInputsReached"] == v["inputs"] for side in v["sides"].values())
    ]
    proven = [
        k
        for k in both
        if cohort[k]["status"] == "preserved"
        and all(
            r["verdict"] == "verified" and not any(a["kind"] == "library" for a in r["assumptions"] or [])
            for r in cohort[k]["sides"].values()
        )
    ]
    prev = read(ROOT / scope["priorReceiverEvidence"])["receivers"]["cases"]
    old_reached = {k for k in cohort if all(prev[k]["current"]["allInputsEntered"].values())}
    counts = {
        "cases": len(cohort),
        "overloads": sum(len(v["overloads"]) for v in cohort.values()),
        "physical": dict(Counter(v["status"] for v in cohort.values())),
        "reachedBoth": sorted(both),
        "newlyReachedBoth": sorted(set(both) - old_reached),
        "newlyLostReach": sorted(old_reached - set(both)),
        "nativeBoth": sorted(proven),
        "newlyProvedBoth": sorted(set(proven) - set(scope["priorCounts"]["nativeFiniteCallerBoth"])),
        "bareOverloads": dict(
            Counter(row["verdict"] for v in cohort.values() for row in v["overloads"].values())
        ),
    }
    counts["ordinarySideVerdicts"] = dict(
        Counter(side["verdict"] for v in cohort.values() for side in v["sides"].values())
    )
    counts["changedOrdinaryVerdicts"] = {
        case + "/" + side: [earlier[case]["sides"][side]["verdict"], row["verdict"]]
        for case, v in cohort.items()
        for side, row in v["sides"].items()
        if earlier[case]["sides"][side]["verdict"] != row["verdict"]
    }
    counts["newNativeStartupSearches"] = [
        case + "/" + side
        for case, v in sorted(cohort.items())
        for side, row in v["sides"].items()
        if row.get("startupSearchRan")
    ]
    startup = {}
    for family in ("javaparser", "xz"):
        d = verified("transfer/" + family)
        w = verified("transfer/" + family + "-ordinary-witnesses")
        original = verified("transfer/" + family + "-ordinary-native")
        if set(original["sides"]) != set(d["sides"]):
            raise ValueError("different ordinary versions")
        startup[family] = {
            side: {
                "pcs": v["propertyReadPcs"],
                "ordinaryNative": {
                    label: {
                        "verdict": row["native"]["verdict"],
                        "firstUnproved": row["native"]["problem"],
                        "replay": row.get("ordinaryDefaultJvm"),
                        "searched": any(
                            a["purpose"] == "startup witness"
                            for a in (row["native"].get("search") or {}).get("runs", [])
                        ),
                    }
                    for label, row in original["sides"][side].items()
                },
                "ordinary": (d.get("ordinary") or {}).get("sides", {}).get(side, {}).get("verdict"),
                "fixedProfiles": {k: r["native"]["verdict"] for k, r in v["profiles"].items()},
                "boundedNonNull": {k: r["verdict"] for k, r in v["boundedNonNullSeparator"].items()},
                "publicWitnesses": {
                    k: {
                        "disposition": r["disposition"],
                        **(
                            {
                                "setting": r["attempts"][r["witnessPrestate"]]["value"],
                                "input": r["attempts"][r["witnessPrestate"]]["input"],
                                "defaultAlsoFails": r["reproducesOnFreshDefault"],
                                "libraryMethodReached": r["attempts"][r["witnessPrestate"]].get(
                                    "libraryMethodReached"
                                ),
                            }
                            if r["disposition"] == "refuted"
                            else {}
                        ),
                    }
                    for k, r in w["sides"][side].items()
                },
            }
            for side, v in d["sides"].items()
        }
    deeper = {}
    for case, stage in [("hex", "mandatory-cache"), ("float", "aligned"), ("schedule", "single-monitor")]:
        deep = {
            label: {
                k: compact_native(v) for k, v in verified(f"deeper/{phase}/{case}/native")["results"].items()
            }
            for label, phase in [("opening", "opening"), ("current", stage)]
        }
        compare = verified(
            f"deeper/{'nonnull' if case=='hex' else 'single-monitor' if case=='schedule' else 'opening'}/{case}/standalone"
        )
        deep["standalone"] = {
            k: {field: v.get(field) for field in ("user", "otherFailures", "status")}
            for k, v in compare["results"].items()
        }
        if case == "schedule":
            observed = verified("deeper/selected/schedule")["revisions"]
            deep["assertionSites"] = {
                version: {
                    "sha256": v["classSha256"],
                    "method": v["method"],
                    "pc": v["pc"],
                    "replays": {
                        k: {"order": r["order"], "hits": r["hits"]} for k, r in v["protocols"].items()
                    },
                }
                for version, v in observed.items()
            }
            measured = verified("deeper/single-monitor/schedule/schedules")["results"]
            deep["schedules"] = {
                k: {f: r[f] for f in ("orders", "zero", "nonzero", "witness")} for k, r in measured.items()
            }
        deeper[case] = deep
    for p in sorted((RESULTS / "final-predecessor/callers").glob("*/measurement.json")):
        verified(str(p.parent.relative_to(RESULTS)))
    # Intermediate controls and the recorded recovery have their own evidence even when the final score uses a successor.
    for phase in (
        "deeper/opening/schedule/schedules",
        "deeper/opening/schedule/standalone",
        "deeper/opening/hex/standalone",
        "deeper/byte-fill/hex/native",
    ):
        verified(phase)
    for p in sorted((RESULTS / "predecessor/callers").glob("*/measurement.json")):
        verified(str(p.parent.relative_to(RESULTS)))
    for job, status in {
        "20261123-223108-qualify-the-ordinary-stock-and-safety-si": "passed",
        "20261123-230231-check-xz-frame-bytes-and-cache-identity": "failed",
        "20261123-233644-check-both-conformance-suites-after-rece": "passed",
        "20261123-235734-confirm-native-and-jbmc-corpus-conforman": "passed",
    }.items():
        if managed(job)["status"] != status:
            raise ValueError("unexpected supporting job outcome: " + job)
    previous = matched(ROOT / "verification/jbmc-fast-follow/successor/regressions/callers")
    current = matched(RESULTS / "final-predecessor/callers")
    return {
        "schema": "receiver-property-results/v1",
        "opening": opening,
        "training": training,
        "configuration": conf,
        "jgrapht": dg,
        "receiverCohort": counts,
        "startup": startup,
        "deeper": deeper,
        "predecessor": {"opening": previous["counts"], "current": current},
        "jobs": jobs,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="compare the committed result with its managed output and source digests",
    )
    args = ap.parse_args()
    path = RESULTS / "results.json"
    output = json.dumps(build(), indent=2) + "\n"
    if args.check:
        if output != path.read_text():
            raise SystemExit("results differ from the verified receipts")
        print("verified receiver campaign results")
    else:
        path.write_text(output)

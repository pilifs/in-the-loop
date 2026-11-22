"""Recount the expansion from managed outputs on the three original populations."""
import argparse
from collections import Counter
import json
import sys
from pathlib import Path

from followup_results import comparison
from results import DATA, ROOT, Job, native, read, rel, sha
from startup import HERE
from buffer_fact import validate_producer
sys.path.insert(0, str(HERE.parent / "external-upgrades"))
from engineering_report import checked_finite

# Job identity pins each historical comparison and its original output digests.
IDS = {
    "buildMissingGuava": "20261122-035338-build-the-avro-198-encoder-and-run-its-m",
    "buildBeforeShading": "20261122-040311-build-the-original-avro-encoder-with-its",
    "first01": "20261122-040728-trace-and-check-original-upgrade-receive",
    "first02": "20261122-040740-group-02-original-upgrade-receivers-and",
    "first03": "20261122-040740-group-03-original-upgrade-receivers-and",
    "first04": "20261122-040740-group-04-original-upgrade-receivers-and",
    "first05": "20261122-040740-group-05-original-upgrade-receivers-and",
    "first06": "20261122-040740-group-06-original-upgrade-receivers-and",
    "first07": "20261122-040740-group-07-original-upgrade-receivers-and",
    "buildPackaged": "20261122-041348-qualify-avro-198-packaged-classes-after",
    "supersededBuild042449-exercise-javaparser-parent-traversals-wi": "20261122-042449-exercise-javaparser-parent-traversals-wi",
    "supersededBuild042449-trace-avro-355-ordinary-factory-and-sche": "20261122-042449-trace-avro-355-ordinary-factory-and-sche",
    "supersededBuild042449-trace-avro-361-ordinary-factory-and-sche": "20261122-042449-trace-avro-361-ordinary-factory-and-sche",
    "supersededBuild042450-avro-198-encoder-baseline-on-packaged-ar": "20261122-042450-avro-198-encoder-baseline-on-packaged-ar",
    "supersededBuild042450-avro-198-encoder-current-on-packaged-art": "20261122-042450-avro-198-encoder-current-on-packaged-art",
    "supersededBuild042450-exercise-javaparser-fix-traversals-with": "20261122-042450-exercise-javaparser-fix-traversals-with",
    "supersededBuild042450-repeat-original-frozen-startup-scopes-af": "20261122-042450-repeat-original-frozen-startup-scopes-af",
    "supersededBuild042802-measure-avro-198-reuse-at-its-actual-enc": "20261122-042802-measure-avro-198-reuse-at-its-actual-enc",
    "supersededBuild043152-check-original-spreadsheet-and-date-rece": "20261122-043152-check-original-spreadsheet-and-date-rece",
    "encoderbaseline": "20261122-044515-avro-198-encoder-baseline-on-packaged-ar",
    "encoderClock": "20261122-044515-avro-198-encoder-current-on-packaged-art",
    "priorSeparatorparent": "20261122-044515-exercise-javaparser-parent-traversals-wi",
    "firstLoader355": "20261122-044515-trace-avro-355-ordinary-factory-and-sche",
    "firstLoader361": "20261122-044515-trace-avro-361-ordinary-factory-and-sche",
    "decoded01": "20261122-044516-01-receiver-rescore-after-literal-decodi",
    "decoded02": "20261122-044516-02-receiver-rescore-after-literal-decodi",
    "decoded03": "20261122-044516-03-receiver-rescore-after-literal-decodi",
    "decoded04": "20261122-044516-04-receiver-rescore-after-literal-decodi",
    "firstProperties": "20261122-044516-check-original-spreadsheet-and-date-rece",
    "priorSeparatorfix": "20261122-044516-exercise-javaparser-fix-traversals-with",
    "priorAdoption": "20261122-044516-measure-avro-198-reuse-at-its-actual-enc",
    "clockFrozen": "20261122-044516-repeat-original-frozen-startup-scopes-af",
    "decoded05": "20261122-044517-05-receiver-rescore-after-literal-decodi",
    "decoded06": "20261122-044517-06-receiver-rescore-after-literal-decodi",
    "decoded07": "20261122-044517-07-receiver-rescore-after-literal-decodi",
    "firstSegments": "20261122-044517-prove-avro-encoder-paths-and-check-inter",
    "priorStartup355": "20261122-045304-complete-avro-355-startup-and-reducer-ev",
    "priorStartup361": "20261122-045304-complete-avro-361-startup-and-reducer-ev",
    "current01": "20261122-050023-01-verify-original-callers-with-complete",
    "current02": "20261122-050023-02-verify-original-callers-with-complete",
    "current03": "20261122-050023-03-verify-original-callers-with-complete",
    "current04": "20261122-050023-04-verify-original-callers-with-complete",
    "current05": "20261122-050023-05-verify-original-callers-with-complete",
    "current06": "20261122-050024-06-verify-original-callers-with-complete",
    "current07": "20261122-050024-07-verify-original-callers-with-complete",
    "encodercurrent": "20261122-050024-final-avro-198-caller-and-cursor-compari",
    "frozen": "20261122-050024-final-original-avro-and-javaparser-scope",
    "segments": "20261122-050024-finish-avro-encoder-path-and-interrupt-c",
    "properties": "20261122-050024-verify-original-receiver-getters-with-st",
    "startup355": "20261122-050207-final-355-jackson-and-fresh-configuratio",
    "startup361": "20261122-050207-final-361-jackson-and-fresh-configuratio",
    "adoption": "20261122-050534-confirm-avro-encoder-adoption-on-the-fin",
    "separatorfix": "20261122-050534-final-fixed-javaparser-separator-profile",
    "separatorparent": "20261122-050534-final-parent-javaparser-separator-profil"
}
SIDES = ("old", "new")
REVISIONS = ("parent", "fix")
INPUT_COUNTS = {"buffered": 14, "channel": 2}
RECEIVER_ROUTES = {"first": "receiver-callers", "decoded": "receiver-final", "current": "receiver-verified"}


def qualified_caller(job, group, directory, key, registered):
    report_path = Path("verification/domain-foundations") / directory / group / "callers" / (key + ".json")
    path = job.output(report_path)
    caller = read(path)
    physical = checked_finite(registered, caller)
    scope = read(HERE.parent / "external-upgrades/scenarios" / key / "scope.json")
    if caller["cases"] != scope["cases"]:
        raise ValueError("registered inputs changed for " + key)
    result = {
        "receipt": rel(path), "physical": physical, "registeredInputs": len(scope["cases"]),
        "checkerSha256": caller["nativeCaller"]["checkerSha256"],
        "native": {}, "constructorSignatures": {}, "allInputsEntered": {}, "originalCallerClass": {},
    }
    for side in SIDES:
        binding = caller["sides"][side]
        experiment = caller["nativeCaller"]
        check = experiment["sides"][side]
        if (check["commit"] != registered["revisions"][side] or check["commit"] != binding["commit"]
                or check["callerClassSha256"] != binding["callerClassSha256"]
                or check["orderedClasspathSha256"] != binding["classpath"]):
            raise ValueError("different original artifacts for " + key)
        if check.get("raw"):
            raw_path = job.output(report_path.parent / (key + "-receipts") / check["raw"])
            row, = read(raw_path)
            if (sha(raw_path) != check["rawSha256"] or row["target"] != experiment["target"]
                    or row["assume"] != experiment["assume"] or row["assert"] != "result"
                    or row["verdict"] != check["verdict"]):
                raise ValueError("different native caller statement for " + key)
            stated = row.get("stated")
            if stated and (stated["gap_mode"] != "strict" or stated["checker"]["engine"] != "native"
                    or any(a.get("id", "").startswith("observed-initializer:") for a in stated["assumptions"])):
                raise ValueError("unqualified caller scope for " + key)
        if check["verdict"] == "verified" and (not check.get("raw")
                or (check.get("vacuity") or {}).get("status") != "non-vacuous"
                or (check.get("bounds") or {}).get("complete") is not True):
            raise ValueError("incomplete affirmative result for " + key)
        result["native"][side] = {
            "verdict": check["verdict"], "firstOutstanding": check["firstOutstanding"],
            "libraryPremises": [a.get("id") or a["text"] for a in (check.get("assumptions") or [])
                                if a["kind"] == "library"],
        }
        trials = binding["trials"]
        result["allInputsEntered"][side] = len(trials) == len(scope["cases"]) and all(
            trial["qualifiedMethodEntries"] == 2 for trial in trials)
        result["constructorSignatures"][side] = sorted({
            ctor["descriptor"] for trial in trials for frame in trial.get("receiverAtEntry", [])
            for ctor in frame["observedConstructorEntries"]
        })
        result["originalCallerClass"][side] = binding["callerClassSha256"]
    return result


def proved_on_both_versions(row):
    return (all(row["allInputsEntered"].values()) and row["physical"] == "preserved"
            and all(v["verdict"] == "verified" and not v["libraryPremises"] for v in row["native"].values()))


def receiver_scores(jobs):
    cases = {c["id"]: c for c in read(HERE.parent / "external-upgrades/corpus.json")["cases"]}
    pilot = read(DATA / "results.json")["receivers"]
    rows = {}
    for key, previous in pilot["cases"].items():
        group = Path(previous["receipt"]).parts[-3]
        versions = {"family": previous["family"], "run6First": previous["previousBlocker"],
                    "pilotFirst": previous["currentBlocker"]}
        pilot_overloads = read(ROOT / previous["receipt"])
        for label, folder in RECEIVER_ROUTES.items():
            job = jobs[label + group]
            caller = qualified_caller(job, group, folder, key, cases[key])
            comparison = read(job.single("overloads/current/" + key + ".json"))
            for side in SIDES:
                if any(comparison["sides"][side].get(field) != pilot_overloads["sides"][side].get(field)
                       for field in ("commit", "callerClassSha256", "orderedSha256")):
                    raise ValueError("original overload inputs differ from the pilot for " + key)
            overloads = comparison.get("nativeOverloads") or [comparison["native"]]
            caller["overloads"] = {
                item["target"]: {"verdict": (item.get("outcome") or {}).get("verdict"),
                                 "firstOutstanding": item.get("firstBlocker")} for item in overloads
            }
            if set(caller["overloads"]) != set(previous["current"]):
                raise ValueError("changed overload domain for " + key)
            versions[label] = caller
        if versions["first"]["originalCallerClass"] != versions["current"]["originalCallerClass"]:
            raise ValueError("different caller class between runs for " + key)
        rows[key] = versions

    cohort = {k: row for k, row in rows.items() if row["run6First"] == "receiver construction"}
    if len(rows) != 32 or len(cohort) != 23:
        raise ValueError("changed receiver denominator")
    counts = {}
    for label in RECEIVER_ROUTES:
        run = {k: row[label] for k, row in cohort.items()}
        methods = [method for row in run.values() for method in row["overloads"].values()]
        decided = sorted(k for k, row in run.items() if proved_on_both_versions(row))
        counts[label] = {
            "physical": dict(Counter(row["physical"] for row in run.values())),
            "allOriginalInputsReachedBoth": sum(all(row["allInputsEntered"].values()) for row in run.values()),
            "nativeFiniteCallerBoth": decided,
            "archiveExactNativeCallerBoth": [
                k for k in decided if all(pilot["cases"][k]["bindings"][side]["orderedClasspath"] for side in SIDES)
            ],
            "all32NativeFiniteCallerBoth": sorted(k for k, row in rows.items() if proved_on_both_versions(row[label])),
            "bareOverloads": len(methods), "bareVerdicts": dict(Counter(str(m["verdict"]) for m in methods)),
        }
    literal_operations = ("java.util.Base64.getDecoder", "java.lang.Boolean.parseBoolean")
    def stops_at_literal(row):
        return any(op in (row["firstOutstanding"] or "") for op in literal_operations)
    originally_blocked = [k for k, row in cohort.items() if stops_at_literal(row["first"]["native"]["old"])]
    past_blocker = [k for k in originally_blocked if not any(stops_at_literal(v)
                    for v in cohort[k]["current"]["native"].values())]
    return {
        "population": len(rows), "run6Receiver": len(cohort), "pilotAdvanced": len(pilot["advancedPastSuperclassRefusal"]),
        "originalScopeThreshold": 4, "originalCallerSidesMatched": pilot["exactCallerSides"],
        "run6ClasspathSidesMatched": pilot["exactClasspathSides"], "literalBlockersBefore": sorted(originally_blocked),
        "pastLiteralBlockerOnBoth": sorted(past_blocker), "counts": counts, "cases": rows,
    }


def checked_outcome(job, folder, claim):
    path = job.output(folder / claim["raw"])
    outcome, = read(path)
    if sha(path) != claim["sha256"] or outcome["verdict"] != claim["verdict"]:
        raise ValueError(f"native result differs from its receipt at {path}")
    stated = outcome.get("stated")
    if stated and (stated["gap_mode"] != "strict" or stated["checker"]["engine"] != "native"):
        raise ValueError(f"unexpected native scope at {path}")
    if outcome["verdict"] == "verified" and (stated or {}).get("vacuity", {}).get("status") != "non-vacuous":
        raise ValueError(f"affirmative verdict lacks reachability at {path}")
    return outcome


def startup_scores(jobs):
    jackson, reducers, traversals = {}, {}, {}
    for number in ("355", "361"):
        job = jobs["startup" + number]
        for side in REVISIONS:
            folder = Path("verification/domain-foundations/startup-final") / number / side
            claims = read(job.output(folder / "jackson.json"))["claims"]
            for claim in claims.values():
                checked_outcome(job, folder, claim)
            factory = claims["512-firstFactory"]
            if factory["verdict"] != "verified" or factory["libraryPremises"]:
                raise ValueError("ordinary Jackson factory was not proved at the declared scope")
            jackson[number + "/" + side] = {
                name: {"verdict": row["verdict"], "firstOutstanding": row["firstUnknown"],
                       "libraryPremises": row["libraryPremises"]} for name, row in claims.items()
            }
            if number == "355":
                receipt = read(job.output(folder / "reducers.json"))
                for claim in receipt["claims"].values():
                    checked_outcome(job, folder, claim)
                fields = ("roots", "boundRoots", "verdict", "firstOutstanding", "premises")
                reducers[side] = {
                    "claims": {name: {k: value[k] for k in fields} for name, value in receipt["claims"].items()},
                    "physical": receipt["physical"], "resourceControls": receipt["physicalWithResource"],
                }
    for side in REVISIONS:
        job = jobs["separator" + side]
        folder = Path("verification/domain-foundations/complete-separator-final") / side
        claims = read(job.output(folder / "evidence.json"))["claims"]
        for method in ("text", "absent", "postorder", "preorder", "terminal", "nonempty"):
            claim = claims["current-" + method]
            if "raw" in claim:
                outcome = checked_outcome(job, folder, claim)
                if any((a.get("id") or "").startswith("observed-initializer") for a in outcome["stated"]["assumptions"]):
                    raise ValueError("supplied-separator proof used a captured initializer")
            traversals[side + "/" + method] = {
                "verdict": claim["verdict"], "firstOutstanding": claim.get("firstUnknown"),
                "replayedInputs": claim.get("replayedInputs"), "guard": claim["guard"], "seconds": claim["seconds"],
            }
    return {"jackson": jackson, "reducers": reducers, "explicitSeparator": traversals}


def buffer_adoption(job, samples):
    folder = Path("verification/domain-foundations/encoder-adoption-final")
    measurement = read(job.output(folder / "measurement.json"))
    path = job.output(folder / "sites.json")
    if sha(path) != measurement["sitesSha256"]:
        raise ValueError("invalid reuse measurements")
    sites = read(path)
    for side in REVISIONS:
        actual = sites["reuse"][side]["sites"]
        if actual != sites["disabled"][side]["sites"] or len(actual) != 2 * len(samples):
            raise ValueError("different original encoder sites across reuse routes")
        expected_calls = {(sample["id"], kind) for sample in samples for kind in ("wrap", "encoder")}
        if {(v["input"], v["call"]) for v in actual} != expected_calls:
            raise ValueError("missing original encoder calls")
        for call in actual:
            frozen = samples[call["input"]]["input"]
            if (call["capacity"], call["position"], call["length"]) != (frozen["capacity"], frozen["start"], frozen["width"]):
                raise ValueError("actual encoder caller did not discharge the heap-window guard")
    for name in ("wide-wrap", "read-only", "disabled-wrap"):
        certificate = read(job.output(folder / (name + ".json")))
        raw_path = job.output(folder / certificate["nativeReceipt"])
        outcome, = read(raw_path)
        if (sha(raw_path) != certificate["nativeSha256"] or outcome["verdict"] != "verified"
                or outcome["stated"]["vacuity"]["status"] != "non-vacuous" or outcome["stated"]["gap_mode"] != "strict"
                or certificate["dependencies"]["maxArrayLength"] != 20):
            raise ValueError("incorrect wide heap-buffer certificate")
    historical = Job("20261121-234701-qualify-bounded-heap-buffer-facts-across")
    old_path, = [p for p in historical.files if p.match("buffer-adoption/clean-wrap.json")]
    original = historical.output(old_path)
    trusted_sha = historical.files[old_path]["sha256"]
    dependencies = read(original)["dependencies"]
    validate_producer(original, trusted_sha, dependencies, "wrap")
    try:
        validate_producer(original, trusted_sha, {**dependencies, "maxArrayLength": 20}, "wrap")
    except ValueError as error:
        measurement["sixByteCertificateAtTwenty"] = {
            "bound": dependencies["maxArrayLength"], "requested": 20, "outcome": str(error),
        }
    else:
        raise ValueError("the historical six-byte result was accepted at twenty")
    return measurement


def encoder_scores(jobs):
    samples = read(next((ROOT / "examples").glob("362-*/controls/table.json")))["cases"]
    tasks = ["cursor-parent", "cursor-fix", "repeated-parent", "repeated-fix"]
    routes = {}
    for label, stage in (("baseline", "encoder-baseline"), ("current", "encoder-final")):
        job = jobs["encoder" + label]
        route = {}
        for task in tasks:
            row = native(job, stage, task)
            route[task] = {k: row[k] for k in ("status", "guard", "firstUnknown", "checker", "checkerSeconds", "receipt")}
        routes[label] = route

    finite = {}
    for task in tasks:
        path = jobs["encodercurrent"].single("encoder-final-finite/*/" + task + ".json")
        result = read(path)
        expected = "refuted" if task.endswith("parent") else "established"
        if result["inputs"] != len(samples) or result["status"] != expected:
            raise ValueError("finite encoder outcome differs from the original oracle")
        finite[task] = {"status": result["status"], "inputs": result["inputs"], "receipt": rel(path)}

    channel = [r["id"] for r in samples if r["input"]["readOnly"] and r["input"]["width"] > 16]
    groups = {"channel": channel, "buffered": [r["id"] for r in samples if r["id"] not in channel]}
    if channel != [11, 15] or {k: len(v) for k, v in groups.items()} != INPUT_COUNTS:
        raise ValueError("the bulk-write partition changed")
    segments = {}
    path_job = jobs["segments"]
    for side in REVISIONS:
        folder = Path("verification/domain-foundations/encoder-paths-final") / side
        receipt = read(path_job.output(folder / "evidence.json"))
        for name, claim in receipt["claims"].items():
            guard = "code == 11 || code == 15" if name.startswith("channel-") else "code >= 0 && code < 16 && code != 11 && code != 15"
            raw = checked_outcome(path_job, folder, claim)
            if claim["guard"] != guard or raw["assume"] != guard or raw["target"] != claim["target"]:
                raise ValueError("the native branch differs from the frozen selector partition")
        segments[side] = {"claims": receipt["claims"], "physical": receipt["physical"]}

    earlier = read(jobs["priorAdoption"].single("*/measurement.json"))["routes"]
    return {
        "priorAdoptionRoutes": earlier, "originalTargets": routes, "finite": finite,
        "adoption": buffer_adoption(jobs["adoption"], samples), "inputsByPath": groups, "segmented": segments,
    }


def receiver_properties(job):
    results = {}
    for path in job.files:
        if path.name != "result.json":
            continue
        receipt = read(job.output(path))
        claims = {}
        for label, claim in receipt["claims"].items():
            checked_outcome(job, path.parent, claim)
            claims[label] = {k: claim[k] for k in ("verdict", "firstOutstanding", "assertion")}
        results["/".join(path.parts[-3:-1])] = {
            "target": receipt["target"], "publicConstructor": receipt["publicConstructor"], "claims": claims,
        }
    return results


def score():
    jobs = {key: Job(id_) for key, id_ in IDS.items()}
    inventory = {}
    for key, job in jobs.items():
        for path in job.files:
            job.output(path)
        inventory[key] = {"id": job.record["id"], "status": job.record["status"], "sourceCommit": job.record["sourceCommit"],
                          "outputs": len(job.files), "receipt": rel(job.folder / "result.json")}
    pilot = read(DATA / "results.json")["decimalAdoption"]["tasks"]
    original = read(ROOT / "verification/organic-java-pr-campaign.json")
    final_revision = jobs["frozen"].record["sourceCommit"]
    final_jobs = ["frozen", "properties", "segments", "encodercurrent", "adoption", "startup355", "startup361",
                  "separatorparent", "separatorfix", *(f"current{i:02}" for i in range(1, 8))]
    if any(jobs[name].record["sourceCommit"] != final_revision for name in final_jobs):
        raise ValueError("the final comparison contains different verifier revisions")
    frozen = comparison(jobs["frozen"], "domain-final-common", "domain-final-decimal-startup", original, pilot)
    receivers = receiver_scores(jobs)
    encoder = encoder_scores(jobs)
    if (encoder["adoption"]["checkerSha256"] != frozen["executableSha256"] or any(
            case["current"]["checkerSha256"] != frozen["executableSha256"] for case in receivers["cases"].values())):
        raise ValueError("the final callers and frozen claims used different executables")
    return {
        "schema": "domain-foundations-expansion/v1", "jobs": inventory,
        "frozen": frozen,
        "priorFrozen": comparison(jobs["clockFrozen"], "domain-clock-common", "domain-clock-decimal-startup", original, pilot),
        "receivers": receivers, "startup": startup_scores(jobs), "encoder": encoder,
        "receiverProducers": receiver_properties(jobs["properties"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    calculated = score()
    scorecard = DATA / "expansion.json"
    if args.check:
        if read(scorecard) != calculated:
            raise SystemExit("domain expansion scorecard differs from the collected outputs")
        print("Expansion scorecard matches the collected outputs")
    else:
        scorecard.write_text(json.dumps(calculated, indent=2, ensure_ascii=False) + "\n")

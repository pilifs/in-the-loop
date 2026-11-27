"""Compare every frozen URL-only question against the N batch after a separate producer seal."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from eligibility_inventory import HERE, PR, ROOT, pr_key, read, write
from evaluate_arm import at, blob
from paired_score import canonical, correspondence, get_evidence, require, score_fields, verified_bindings
from reference_rows import check_semantics, reference
from url_intake import resolve, urls


OUTPUT = HERE.parent / "url-run"


def stopped(revision, output):
    """Account for stopped sessions using two committed inputs, without opening any producer workspace."""
    manifest = at(revision, OUTPUT / "producer-seal.json")
    audit_path = ROOT / "verification/merged-pr-links/n01-n05/audit.json"
    audit_bytes = blob(revision, audit_path)
    audit = json.loads(audit_bytes)
    prior = {r["case"].lower(): r for r in audit["cases"]}
    rows = []
    for item in manifest["cases"]:
        m = PR.fullmatch(item["url"])
        require(m and item.get("stop") and not item.get("measurement"), "stopped accounting requires explicit stops and no claimed measurement")
        original = prior[pr_key(*m.groups())]
        rows.append({"url": item["url"], "producerStop": item["stop"], "qualifiedNewMeasurement": False,
                     "unsealedStageAccounting": {k: item[k] for k in ("privateDraftStages", "upstreamTestAssistance", "buildAttempt") if k in item},
                     "comparison": "No sealed producer measurement to compare.",
                     "historicalOriginal": {"observationsSha256": original["observationsSha256"], "deployments": original["deployments"],
                                            "allHistoriesPaired": original["allHistoriesPaired"], "fixedRefutations": original["fixedRefutations"]}})
    require(len(rows) == len(prior) == len({r["url"] for r in rows}) == 5 and audit["totals"]["questions"] == 17,
            "stopped accounting lost a PR or historical question")
    value = {"schema": "url-only-stopped-comparison/v1", "producerSeal": revision, "workflow": manifest.get("workflow"),
             "producerRevision": manifest.get("producerRevision"), "newQualifiedDeployments": 0, "newQualifiedQuestions": 0,
             "unscoredQuestions": 17, "unscoredPRs": 5, "semanticParity": "unverified",
             "source": "Only the committed stop manifest and existing independent batch audit were consulted.",
             "historicalAudit": {"path": audit_path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(audit_bytes).hexdigest(),
                                 "totals": audit["totals"]}, "cases": rows}
    write(output, value)
    print("five committed producer stops, seventeen historical questions unscored")


def sealed(revision, description):
    name = Path(description["path"])
    require(not name.is_absolute() and ".." not in name.parts and (ROOT / name).is_relative_to(OUTPUT),
            "URL producer evidence must be inside the separately sealed URL run")
    raw = blob(revision, ROOT / name)
    require(hashlib.sha256(raw).hexdigest() == description["sha256"], "URL producer file differs from its seal")
    return json.loads(raw), ROOT / name


def question_summary(question):
    return {"id": question["id"], "role": question["role"], "history": question.get("registeredHistory"),
            "historicalCallerArgs": question.get("privateCallerArgs"), "requiredSides": question["requiredSides"],
            "registeredPrediction": question.get("registeredPrediction"), "expected": question.get("expected"),
            "originalObservations": question["variants"]}


def compare(revision, judgments, output):
    manifest = at(revision, OUTPUT / "producer-seal.json")
    require(manifest.get("producerRevision") and manifest.get("workflow"), "missing independent C producer workflow or revision")
    require([r["url"] for r in manifest["cases"]] == urls(), "URL producer seal is missing a requested URL or changed its order")
    intake = at(revision, OUTPUT / "upstream-intake.json")["cases"]
    require([r["url"] for r in intake] == urls(), "URL intake differs from the original five-line roster")
    rows = []
    historical_launches = fixed_matches = intended_changes = unchanged_controls = 0
    for index, (prod, original) in enumerate(zip(manifest["cases"], intake, strict=True), 1):
        url = prod["url"]
        _, _, metadata, pins = resolve(url)
        project = metadata["base"]["repo"]["full_name"]
        ref = reference({"number": 452+index, "canonicalPR": pr_key(project, metadata["number"]),
                         "url": url, "pins": pins}, metadata=metadata)
        qrows = []
        precision = bool(original["pins"] == pins and all(
            original["sides"][s]["orderedClasspathSha256"] == ref["variants"]["pins"]["bindings"][s]["classpathSha256"]
            for s in ("old", "new")) and original["jdkReleaseSha256"] == ref["variants"]["pins"]["jdkReleaseSha256"])
        experiment, measurements, directory = None, {}, None
        if not prod.get("stop"):
            experiment, _ = sealed(revision, prod["prediction"])
            measured, path = sealed(revision, prod["measurement"])
            directory = path.parent
            require(experiment["url"] == measured["url"] == url and measured["predictionSha256"] == prod["prediction"]["sha256"],
                    "URL measurement is detached from the per-PR prediction seal")
            variants = measured.get("deployments", [])
            require(len(variants) == 1 and variants[0]["name"] == "pins", "URL measurement deployment names differ")
            measurements = {m["candidateIndex"]: m for m in variants[0]["measurements"]}
        candidates = experiment["candidates"] if experiment else []
        actual_deployment = precision and any(verified_bindings(revision, "cold", index, m, ref, "pins", directory=directory)
                                               for m in measurements.values())
        if original.get("service"):
            sidecar_ref = prod.get("serviceEvidence")
            if sidecar_ref:
                sidecar, _ = sealed(revision, sidecar_ref)
                actual_deployment = bool(actual_deployment and sidecar.get("image") == original["service"]["image"]
                                         and sidecar.get("serverVersion") == "9.1.0" and sidecar.get("independentConnection"))
            else:
                actual_deployment = False
        local = judgments.get(ref["canonicalPR"], {})
        registered = local.get("questions", {})
        require(set(registered) == {q["id"] for q in ref["questions"]}, "all original questions need an independent presence or omission judgment")
        credited_candidates = set()
        for q_index, question in enumerate(ref["questions"]):
            result = question_summary(question)
            if "actual" in question["variants"]["pins"]:
                actual = question["variants"]["pins"]["actual"]
                historical_launches += len(actual)
                fixed_matches += actual.get("new") == question.get("expected", {}).get("new")
                if "old" in actual and "new" in actual:
                    intended_changes += question["role"] == "Intent" and actual["old"] != actual["new"]
                    unchanged_controls += question["role"] == "Control" and actual["old"] == actual["new"]
            match = registered[question["id"]]
            out = {"matched": False, "judgment": match.get("reason"), "coverage": "omitted"}
            result["producer"] = out
            qrows.append(result)
            if match.get("candidateIndex") is None:
                require(match.get("reason"), "omission needs a reason")
                continue
            rank = match["candidateIndex"]
            require(type(rank) is int and 0 <= rank < len(candidates), "comparison names a missing producer candidate")
            candidate = candidates[rank]
            out.update(candidateIndex=rank, entry=candidate["entry"], history=candidate["history"], inputs=candidate["inputs"],
                       fields=candidate["fields"], requiredSides=candidate["requiredSides"], coverage="nominated")
            m = measurements.get(rank)
            if not m:
                out["reason"] = "nominated claim lacks a sealed original measurement"
                continue
            out.update(actual=m.get("observations"), finiteDisposition=m.get("status"), evidence=m.get("evidence"))
            try:
                require(actual_deployment, "independent original deployment or required database is unavailable")
                require(candidate.get("role") == question["role"] or match.get("sealedRole") == question["role"]
                        and prod.get("roles", {}).get(str(rank)) == question["role"], "role missing or different in the sealed prediction")
                require(m["candidateSha256"] == canonical(candidate), "URL measurement identifies a different frozen candidate")
                qref = deepcopy(ref)
                qref.update(primaryIndex=q_index, semantics=match["semantics"])
                check_semantics(qref)
                require(correspondence(match, candidate, qref), "public history, scope or claim differs")
                require(verified_bindings(revision, "cold", index, m, qref, "pins", directory=directory), "missing bound original entry")
                evidence = get_evidence(revision, "cold", index, m["evidence"], directory=directory)
                _, agrees = score_fields(match, candidate, qref, m, evidence, "pins")
                require(agrees, "new finite disposition differs from the historical side scope")
                if question["variants"]["pins"].get("unpredictedSides"):
                    require(set(m.get("unpredictedSides", [])) == set(question["variants"]["pins"]["unpredictedSides"]),
                            "measured historical side without a registered prediction was lost")
                    observed_scope = deepcopy(qref)
                    observed_scope["questions"][q_index]["requiredSides"] = list(question["variants"]["pins"]["actual"])
                    score_fields(match, candidate, observed_scope, m, evidence, "pins")
                out.update(matched=True, coverage="independently matched", reason=match["reason"])
                credited_candidates.add(rank)
            except (ValueError, KeyError, TypeError, IndexError) as error:
                out["reason"] = str(error)
        other = [{"candidateIndex": i, "entry": c["entry"], "history": c["history"], "prediction": c["prediction"]}
                 for i, c in enumerate(candidates) if i not in credited_candidates]
        rows.append({"url": url, "cachedGraphMatchesReference": precision, "originalDeploymentMatch": bool(actual_deployment),
                     "producerStop": prod.get("stop"), "questions": qrows,
                     "unmatchedProducerClaims": other, "allQuestionsMatched": all(q["producer"]["matched"] for q in qrows)})
    denominator = sum(len(r["questions"]) for r in rows)
    matched = sum(q["producer"]["matched"] for r in rows for q in r["questions"])
    require(denominator == 17 and len(rows) == 5, "historical N denominator changed")
    result = {"schema": "url-only-independent-parity/v1", "producerSeal": revision, "producerRevision": manifest["producerRevision"],
              "workflow": manifest["workflow"], "originalDeploymentsMatched": sum(r["originalDeploymentMatch"] for r in rows),
              "newWholePRs": sum(r["allQuestionsMatched"] for r in rows), "newQuestionsMatched": matched,
              "questionDenominator": denominator, "historicalObservedSides": historical_launches, "historicalFixedMatches": fixed_matches,
              "historicalChangedIntents": intended_changes, "historicalUnchangedControls": unchanged_controls,
              "passed": matched == denominator and all(r["originalDeploymentMatch"] for r in rows), "cases": rows}
    write(output, result)
    print(f"{matched}/{denominator} historical questions and {result['newWholePRs']}/5 whole PRs matched the separately sealed producer")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer-seal", required=True)
    parser.add_argument("--judgments", type=Path)
    parser.add_argument("--stops-only", action="store_true", help="read the committed stops and existing independent audit only")
    parser.add_argument("--output", type=Path, default=OUTPUT / "parity.json")
    args = parser.parse_args()
    if args.stops_only:
        stopped(args.producer_seal, args.output)
    elif args.judgments:
        compare(args.producer_seal, read(args.judgments), args.output)
    else:
        parser.error("a measured comparison needs independent judgments")

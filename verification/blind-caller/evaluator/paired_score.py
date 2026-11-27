"""Score immutable primary predictions and traced field receipts against the independent reference."""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

from eligibility_inventory import HERE, ROOT, read, write
from evaluate_arm import at, blob, filename, verify_predictions
from packet_view import ARMS
from reference_rows import check_semantics

sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_evidence, change_plan


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def same_typed(a, b):
    return type(a) is type(b) and canonical(a) == canonical(b)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def member(raw, pointer):
    """A JSON key or array index at each step. Reject negative indices and type coercion."""
    for step in pointer:
        if type(step) is int and isinstance(raw, list) and 0 <= step < len(raw):
            raw = raw[step]
        elif isinstance(step, str) and isinstance(raw, dict) and step in raw:
            raw = raw[step]
        else:
            raise ValueError("readback path is absent from the original public projection")
    return raw


def get_evidence(revision, arm, index, desc, *, directory=None):
    content = {}
    for name in ("registration", "generation", "source", "bytecode", "plan", "receipt"):
        ref = desc.get(name, {})
        rel = Path(ref.get("path", ""))
        require(not rel.is_absolute() and ".." not in rel.parts and rel.parts, "invalid measurement evidence path")
        data = blob(revision, directory / rel if directory else filename(arm, index, "measure", rel))
        require(hashlib.sha256(data).hexdigest() == ref.get("sha256"), "measurement evidence digest mismatch")
        content[name] = data
    return content


def verified_bindings(revision, arm, index, measurement, ref, variant, *, directory=None):
    descriptor = measurement.get("evidence", {}).get("bindings")
    if not descriptor:
        return False
    path = Path(descriptor["path"])
    require(not path.is_absolute() and ".." not in path.parts, "binding receipt outside the case output")
    raw = blob(revision, directory / path if directory else filename(arm, index, "measure", path))
    require(hashlib.sha256(raw).hexdigest() == descriptor["sha256"], "binding file differs from its digest")
    plan = json.loads(raw)
    require(change_plan.saved_bindings(plan)["status"] == "recorded", "saved binding evidence has no independently checked graph")
    required_sides = ref["questions"][ref["primaryIndex"]]["requiredSides"]
    for side in required_sides:
        public = measurement["entryBindings"].get(side, {})
        actual = [v for v in plan["entryBindings"].values() if v["entry"] == measurement["entry"] and v["side"] == side]
        if len(actual) != 1 or actual[0].get("status") != "bound":
            return False
        b = actual[0]
        graph = ref["variants"][variant]["bindings"][side]
        idx = b["providerIndex"]
        require(public["revision"] == b["revision"] == graph["revision"] and type(idx) is int
                and 0 <= idx < len(graph["classpathSha256"]) and public["providerIndex"] == idx
                and public["artifactSha256"] == b["artifactSha256"] == graph["classpathSha256"][idx]
                and public["classSha256"] == b["classSha256"] == b["jvm"]["sha256"] == b["checker"]["sha256"],
                "JVM and checker binding differs from the original deployment")
    return True


def correspondence(judgment, candidate, ref):
    require(judgment.get("candidateSha256") == canonical(candidate) and
            judgment.get("referenceSha256") == canonical(ref), "equivalence review belongs to different frozen inputs")
    require(isinstance(judgment.get("reason"), str) and judgment["reason"].strip(), "missing independent equivalence reason")
    kind = judgment.get("kind")
    require(kind in ("equivalent", "different", "unresolved", "other useful claim"), "unexpected equivalence decision")
    if kind != "equivalent":
        return False
    sem = check_semantics(ref)
    require(isinstance(judgment.get("routeEvidence"), str) and judgment["routeEvidence"].strip(),
            "equivalent route needs a public entry and receiver explanation")
    require(isinstance(judgment.get("predicateEvidence"), str) and judgment["predicateEvidence"].strip()
            and "undecided" not in candidate["prediction"], "equivalent primary needs a falsifiable premeasurement predicate")
    require(len(judgment.get("orderedActions", [])) == len(sem["actions"]) and all(judgment["orderedActions"]),
            "equivalence review did not account for each ordered public action")
    require(set(judgment.get("inputCorrespondence", {})) == {x["name"] for x in sem["inputs"]},
            "equivalence review did not account for each typed input")
    require(set(judgment.get("fieldCorrespondence", {})) == {x["name"] for x in sem["fields"]},
            "equivalence review did not account for every required public projection")
    primary = ref["questions"][ref["primaryIndex"]]
    require(set(candidate["requiredSides"]) == set(primary["requiredSides"]), "scoped predictions differ")
    return True


def qualified_observations(candidate, measurement, evidence, ref, variant):
    registration, generation, plan, receipt = [json.loads(evidence[key]) for key in ("registration", "generation", "plan", "receipt")]
    caller, bindings = measurement["caller"], measurement["entryBindings"]
    measured_sides = ref["questions"][ref["primaryIndex"]]["requiredSides"]
    originals = ref["variants"][variant]
    receipt_sha = hashlib.sha256(evidence["receipt"]).hexdigest()
    nodes = [n for n in plan.get("claims", []) if n.get("receipt", {}).get("sha256") == receipt_sha]
    require(len(nodes) == 1, "expected one ordinary claim bound to this original JVM receipt")
    node = nodes[0]
    qs = [q for q in registration["questions"] if q["id"] == node["id"]]
    require(registration["entry"] == candidate["entry"] and registration["fields"] == candidate["fields"]
            and len(qs) == 1 and qs[0]["inputs"] == candidate["inputs"] and qs[0]["history"] == candidate["history"],
            "executed caller differs from the frozen candidate history, domain or fields")
    require(generation["registration"] == canonical(registration) and generation["status"] == "compiled"
            and generation["compilePolicy"] == "once against old" and caller["compileAgainst"] == "old",
            "caller lacks the original old-API compilation")
    require(hashlib.sha256(evidence["source"]).hexdigest() == caller["sourceSha256"] == generation["sourceSha256"]
            and hashlib.sha256(evidence["bytecode"]).hexdigest() == generation["archiveSha256"]
            and originals["jdkReleaseSha256"] == caller["jdkReleaseSha256"] == generation["jdkReleaseSha256"],
            "caller source, bytecode archive or compiling JDK differs")
    with zipfile.ZipFile(io.BytesIO(evidence["bytecode"])) as archive:
        compiled = {name: hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist() if name.endswith(".class")}
    require(bool(compiled) and compiled == caller["compiled"] == generation["compiled"] == receipt["generatedObserver"]["classes"],
            "executed bytecode differs from the old-API class archive")
    require(receipt["generatedObserver"]["bundle"] == hashlib.sha256(evidence["generation"]).hexdigest(),
            "receipt refers to different generated source or compiled classes")
    require(plan.get("executionState") == "complete"
            and change_plan.saved_bindings(plan)["status"] == "recorded", "saved ordinary plan has no verifiable bindings")
    require(node["domain"] == receipt["cases"], "receipt belongs to another predicate or domain")
    raw, diagnostic = {}, {}
    for side in measured_sides:
        original = originals["bindings"][side]
        b = bindings[side]
        executed = receipt["sides"][side]
        key = node["entryBindings"][side]
        declared = plan["entryBindings"][key]
        require(executed.get("entryBinding") == key and declared["status"] == "bound"
                and declared["revision"] == original["revision"] == b["revision"]
                and b["entry"] == candidate["entry"] and b["status"] == "bound"
                and b["jdkReleaseSha256"] == originals["jdkReleaseSha256"], "required side lacks an original public class binding")
        cp = original["classpathSha256"]
        idx = b["providerIndex"]
        require(type(idx) is int and 0 <= idx < len(cp) and cp == executed["classpath"] and
                cp[idx] == b["artifactSha256"] == declared["artifactSha256"] and b["classSha256"] == declared["classSha256"]
                and declared["jvm"]["sha256"] == declared["checker"]["sha256"] == b["classSha256"],
                "JVM, checker and original ordered deployment select different bytes")
        trials = executed["trials"]
        require(len(trials) == len(receipt["cases"]) == len(candidate["inputs"]) and
                sorted(t["input"] for t in trials) == list(range(len(trials))), "incomplete or repeated public input domain")
        values, projections = [], []
        for t in sorted(trials, key=lambda x: x["input"]):
            out = change_evidence.outcome(t, executed.get("resolvedEntry", receipt["entry"]),
                                          change_evidence.entry_artifact(executed), executed.get("requiredHelperProof"), True)
            require(out is not None, "required public readback lacks two qualified equal JVM observations")
            values.append(out)
            projections.append(t["publicProjections"][0])
        require(values == measurement["observations"][side], "published fields differ from the original repeated JVM observations")
        raw[side] = [json.loads(v["return"]) if "return" in v else v for v in values]
        diagnostic[side] = projections
    return raw, diagnostic, generation, node["status"]


def required_actions(projection, sem):
    required = sem.get("actionWitnesses", [])
    require(required, "retained identity or action order lacks a preregistered action witness")
    stream = iter(projection.get("publicActions", []))
    aliases = {}
    def retain(label, value):
        if not label:
            return
        identity = value.get("alias") if isinstance(value, dict) else None
        require(type(identity) is int and identity >= 0, "retained object identity was not observed")
        require(aliases.setdefault(label, identity) == identity, "a later action used a different retained object")
    for wanted in required:
        observed = next((event for event in stream if event["member"] == wanted["member"]
                         and event.get("role") == wanted["role"]), None)
        require(observed is not None and observed["member"] in projection.get("actionBindings", {}),
                "required ordered action lacks an original reached member binding")
        retain(wanted.get("receiverHandle"), observed.get("receiver"))
        retain(wanted.get("returnHandle"), observed.get("return"))
        for index, label in wanted.get("argumentHandles", {}).items():
            index = int(index)
            require(0 <= index < len(observed.get("args", [])), "required retained argument was not observed")
            retain(label, observed["args"][index])
    for first, second in sem.get("distinctHandles", []):
        require(first in aliases and second in aliases and aliases[first] != aliases[second], "two required object identities were conflated")


def score_fields(judgment, candidate, ref, measurement, evidence, variant):
    sem = ref["semantics"]
    raw, projections, generation, native_status = qualified_observations(candidate, measurement, evidence, ref, variant)
    fields = {entry["field"] for entry in generation["fieldSources"]}
    for side, observations in raw.items():
        for name, mapping in judgment["fieldCorrespondence"].items():
            require(mapping["candidateField"] in fields and mapping["candidateField"] in candidate["fields"],
                    "required projection has no validated generated public readback")
            i = mapping["input"]
            require(type(i) is int and 0 <= i < len(observations), "required readback has no matching finite input")
            actual = member(observations[i], mapping["path"])
            require(same_typed(actual, sem["observedFields"][variant][side][name]), "typed original readback differs from the reference")
            if sem.get("requiresActionWitness", False):
                required_actions(projections[side][i], sem)
    expected_status = ref["questions"][ref["primaryIndex"]]["variants"][variant]["finiteDisposition"]
    return native_status, native_status == expected_status == measurement.get("status")


def attempt_result(reference_revision, arm_revision, arm, index, draw, ref, decision):
    row = draw["cases"][index-1]
    pred = at(arm_revision, filename(arm, index, "predict", "attempt.json"))
    measured = at(arm_revision, filename(arm, index, "measure", "attempt.json"))
    require(pred["url"] == measured["url"] == ref["url"] and measured["referenceSeal"] == pred["referenceSeal"] == reference_revision
            and measured["producerRevision"] == draw["producerRevision"], "attempt lost its reference or producer seal")
    questions = ref["questions"]
    primary = questions[ref["primaryIndex"]]
    result = {"primaryQualified": False, "rankAtThreeEquivalent": False, "rankAtThreeQualified": False,
              "deployment": bool(pred.get("viewSha256")), "candidate": False, "boundPublicEntry": False,
              "compiledAgainstOld": False, "requiredSideReach": False, "allFieldsObserved": False,
              "candidateReviews": [], "stoppedAt": measured.get("stoppedAt", "candidate"),
              "reason": pred.get("reason", measured.get("reason")), "assistance": arm,
              "secondaryQuestions": [{"id": q["id"], "role": q["role"], "newAttempt": "unqualified", "historical": {
                  k: {"status": v["finiteDisposition"], "reason": v["reason"]} for k, v in q["variants"].items()}}
                                     for q in questions if q is not primary]}
    if pred["status"] != "sealed":
        return result
    raw_pred = blob(arm_revision, filename(arm, index, "predict", "prediction.json"))
    require(hashlib.sha256(raw_pred).hexdigest() == pred["predictionSha256"], "frozen prediction bytes changed")
    proposal = json.loads(raw_pred)
    candidates = proposal["candidates"]
    result.update(candidate=bool(candidates), candidateInspections=proposal.get("candidatesInspected"),
                  subjectLaunchesDuringPrediction=proposal.get("subjectLaunches"), testFilesInspected=proposal.get("testsInspected", 0))
    inspected = proposal.get("inspectedEntries")
    require(proposal["candidatesInspected"] <= 64 and (inspected is None or len(inspected) == proposal["candidatesInspected"])
            and proposal.get("subjectLaunches") == 0, "prediction exceeded its inspection or measurement boundary")
    operator = {}
    if measured["status"] in ("measured", "partial measurement"):
        measured_raw = blob(arm_revision, filename(arm, index, "measure", "measurement.json"))
        require(hashlib.sha256(measured_raw).hexdigest() == measured["measurementSha256"], "stored measurement bytes changed")
        output = json.loads(measured_raw)
        require(output["predictionSha256"] == pred["predictionSha256"] and measured["viewSha256"] == pred["viewSha256"],
                "measurement used a different prediction or public view")
        for variant in output["deployments"]:
            label = variant["name"]
            require(label in ref["variants"] and label not in operator, "unknown or duplicate measurement deployment")
            by_rank = {r["candidateIndex"]: r for r in variant["measurements"]}
            require(len(by_rank) == len(variant["measurements"]) and set(by_rank).issubset(range(len(candidates))), "measurement rank is ambiguous")
            operator[label] = {"ranks": by_rank, "reason": variant.get("reason"), "stoppedAt": variant.get("stoppedAt")}
    require(len(decision.get("candidates", [])) == len(candidates), "each ranked candidate needs its own independent review")
    for rank, (candidate, judgment) in enumerate(zip(candidates, decision.get("candidates", []), strict=True)):
        equivalent = correspondence(judgment, candidate, ref)
        audit = {"rank": rank + 1, "entry": candidate["entry"], "kind": judgment["kind"], "equivalent": equivalent,
                 "qualified": False, "review": judgment["reason"], "deployments": {},
                 "stoppedAt": result["stoppedAt"], "reason": result["reason"]}
        if equivalent and rank < 3:
            result["rankAtThreeEquivalent"] = True
        for label in ref["variants"]:
            operator_variant = operator.get(label, {})
            m = operator_variant.get("ranks", {}).get(rank, {})
            evidence_status = {"bound": False, "compiledAgainstOld": False, "reached": False, "allFieldsObserved": False, "qualified": False,
                               "stoppedAt": m.get("stoppedAt") or operator_variant.get("stoppedAt") or audit["stoppedAt"],
                               "reason": m.get("reason") or operator_variant.get("reason") or audit["reason"]}
            audit["deployments"][label] = evidence_status
            if not m:
                continue
            require(m["candidateSha256"] == canonical(candidate) and m["entry"] == candidate["entry"], "measurement belongs to a different ranked candidate")
            try:
                evidence_status["bound"] = verified_bindings(arm_revision, arm, index, m, ref, label)
                evidence_status["compiledAgainstOld"] = m.get("caller", {}).get("compileAgainst") == "old" and bool(m.get("caller", {}).get("compiled"))
                if not m.get("evidence", {}).get("receipt") or ref["safetyAbstention"]:
                    continue
                evidence = get_evidence(arm_revision, arm, index, m["evidence"])
                qualified_observations(candidate, m, evidence, ref, label)
                evidence_status["reached"] = evidence_status["bound"] = evidence_status["compiledAgainstOld"] = True
                if equivalent:
                    status, agrees = score_fields(judgment, candidate, ref, m, evidence, label)
                    evidence_status.update(qualified=agrees, allFieldsObserved=True, finiteDisposition=status,
                                           stoppedAt=("scored primary" if rank == 0 else "scored alternate") if agrees else "finite disposition",
                                           reason=judgment["reason"] if agrees else "finite disposition differs from the independent reference")
                else:
                    evidence_status["reason"] = judgment["reason"]
            except (ValueError, KeyError, TypeError, IndexError, zipfile.BadZipFile) as error:
                evidence_status["reason"] = str(error)
        variants = list(audit["deployments"].values())
        audit["qualified"] = bool(variants) and all(v["qualified"] for v in variants)
        first = next((v for v in variants if not v["qualified"]), variants[0])
        audit.update(stoppedAt=first["stoppedAt"], reason=first["reason"] or judgment["reason"])
        if audit["qualified"] and rank < 3:
            result["rankAtThreeQualified"] = True
        if rank == 0:
            result["boundPublicEntry"] = all(v["bound"] for v in variants)
            result["compiledAgainstOld"] = all(v["compiledAgainstOld"] for v in variants)
            result["requiredSideReach"] = all(v["reached"] for v in variants)
            result["allFieldsObserved"] = all(v["allFieldsObserved"] for v in variants)
            result["primaryQualified"] = audit["qualified"]
            result.update(stoppedAt=audit["stoppedAt"], reason=audit["reason"] or judgment["reason"])
        result["candidateReviews"].append(audit)
    return result


def score(reference_revision, seals, judgments, output):
    draw, refs = at(reference_revision, HERE / "draw.json"), at(reference_revision, HERE / "references.json")["references"]
    for arm, seal in seals.items():
        verify_predictions(seal, arm, draw)
    rows = []
    for index, (row, ref) in enumerate(zip(draw["cases"], refs, strict=True), 1):
        check_semantics(ref)
        key = ref["canonicalPR"]
        results = {arm: attempt_result(reference_revision, seals[arm], arm, index, draw, ref, judgments[key][arm])
                   for arm in ARMS}
        cold = int(results["cold"]["primaryQualified"])
        rows.append({"url": row["url"], "batch": row["batch"], "priorProjectSeen": row["priorProjectSeen"],
                     "sharedApiPackages": row["sharedApiPackages"], "arms": results, "repair": {"status": "not attempted"},
                     "pairedVsCold": {arm: int(results[arm]["primaryQualified"]) - cold for arm in ARMS[1:]}})
    counts = {}
    for arm in ARMS:
        counts[arm] = {batch: {"qualified": sum(r["arms"][arm]["primaryQualified"] for r in rows if batch == "all" or r["batch"] == batch),
                               "denominator": sum(batch == "all" or r["batch"] == batch for r in rows)}
                       for batch in ("all", "P", "Q", "R")}
    reasons = Counter(row["arms"]["cold"]["stoppedAt"] for row in rows if not row["arms"]["cold"]["primaryQualified"])
    write(output, {"schema": "blind-caller-paired-score/v1", "producerRevision": draw["producerRevision"],
                   "referenceSeal": reference_revision, "armSeals": seals, "counts": counts,
                   "coldMissStages": reasons.most_common(), "coldNumericalTargetsMet": counts["cold"]["all"]["qualified"] >= 8
                   and counts["cold"]["R"]["qualified"] >= 3, "plantedControls": "requires independent development falsifier evidence",
                   "rows": rows})
    print(json.dumps(counts))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-seal", required=True)
    for arm in ARMS:
        parser.add_argument("--" + arm + "-seal", required=True)
    parser.add_argument("--judgments", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "score.json")
    args = parser.parse_args()
    score(args.reference_seal, {arm: getattr(args, arm.replace("-", "_") + "_seal") for arm in ARMS},
          read(args.judgments), args.output)

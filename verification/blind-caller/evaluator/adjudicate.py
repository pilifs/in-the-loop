"""Audit the sealed three-arm draw, admitting a machine match only on a witnessed finite correspondence."""
import argparse
from collections import Counter
from pathlib import Path
import re

from eligibility_inventory import HERE, read, write
from evaluate_arm import at, filename, verify_predictions
from paired_score import canonical, require, same_typed
from packet_view import ARMS


def original_tuple(call):
    desc = call["member"].split("(", 1)[1].split(")", 1)[0]
    types = re.findall(r"\[*(?:[ZBCSIJFD]|L[^;]+;)", desc)
    literals = {arg["position"]: arg for arg in call.get("literalArguments", [])}
    if "".join(types) != desc or len(literals) != len(types):
        return None
    result = []
    for i, typ in enumerate(types):
        value = literals[i]["value"]
        if typ in ("I", "J", "S", "B") and re.fullmatch(r"-?\d+", value):
            result.append(int(value))
        elif typ == "Z" and value in ("true", "false"):
            result.append(value == "true")
        elif typ in ("C", "Ljava/lang/String;"):
            result.append(value if value != "null" else None)
        else:
            return None
    return result


def judgment(candidate, ref, measured):
    sem = ref["semantics"]
    q = ref["questions"][ref["primaryIndex"]]
    common = {"candidateSha256": canonical(candidate), "referenceSha256": canonical(ref)}
    def ruling(kind, reason, gap):
        return {**common, "kind": kind, "reason": reason, "gap": gap}
    pending = "other useful claim" if measured and measured.get("status") in ("established", "refuted") else "unresolved"
    if not candidate["inputs"]:
        return ruling(pending, "No concrete public input or receiver history was nominated for this entry.", "missing public input or receiver")
    if "undecided" in candidate["prediction"]:
        return ruling(pending, "The nominated history did not register a falsifiable side-scoped behavior.", "undecided behavior")
    if set(candidate["requiredSides"]) != set(q["requiredSides"]):
        return ruling("different", "The candidate predicts a different set of original revision sides.", "different side scope")
    exp = candidate["prediction"].get("expected")
    if not exp:
        return ruling(pending, "The candidate's paired relation does not specify the registered finite public outcomes on the required sides.", "weaker or different predicate")
    selected = [a for a in sem.get("publicSourceActions", []) if a["member"] == candidate["entry"] and a["branch"] == "on selected source branch"]
    if not selected:
        return ruling(pending, "The candidate entry has no witnessed correspondence to the primary's required public history.", "unresolved public route")
    if len(selected) != 1 or sem.get("requiresActionWitness") or candidate["fields"] != ["call.outcome", "return.scalar"]:
        return ruling(pending, "The nominated experiment needs evidence for the reference's ordered actions and readbacks beyond a direct scalar call.", "missing history or readback correspondence")
    if set(x["name"] for x in sem["fields"]) != {"public.outcome", "public.readback"}:
        return ruling(pending, "The registered observation includes additional typed fields that this return does not independently identify.", "missing field correspondence")
    args = original_tuple(selected[0])
    trials = [i for i, trial in enumerate(candidate["inputs"]) if args is not None and same_typed(trial.get("arguments"), args)]
    if not trials:
        return ruling(pending, "The sealed argument tuples do not demonstrate the independently registered input and prestate.", "different or unresolved input")
    i = trials[0]
    for side in q["requiredSides"]:
        historical = q["expected"][side]
        typed = exp.get(side)
        if not typed or i >= len(typed) or len(typed[i]) != 1 or len(historical) != 1:
            return ruling(pending, "The predicate has no exact value corresponding to this historical side and input.", "unresolved predicate")
        wire = typed[i][0]
        if not isinstance(wire, list) or len(wire) != 3 or wire[0] != "return" or historical[0]["field"] != "return":
            return ruling(pending, "The two projections use different outcome shapes and lack a qualified translation.", "unresolved return or exception")
        if not same_typed(wire[2], historical[0]["value"]):
            return ruling("different", "The fixed prediction and historical predicate assign different values to the same typed public input.", "different finite prediction")
    facts = {f["name"]: {"input": i, "arguments": args, "basis": "literal public argument positions in the selected historical source branch"}
             for f in sem["inputs"]}
    return {**ruling("equivalent", "The same public declaration, typed input and side-specific finite predicates describe the registered direct return.", "none"),
            "routeEvidence": candidate["entry"] + " occurs on the independently attributed source branch at its original public descriptor.",
            "predicateEvidence": "Both premeasurement predictions match the original registered public value at the corresponding typed trial.",
            "inputCorrespondence": facts, "orderedActions": sem["actions"],
            "fieldCorrespondence": {"public.outcome": {"candidateField": "call.outcome", "input": i, "path": [0, 0]},
                                    "public.readback": {"candidateField": "return.scalar", "input": i, "path": [0, 2]}}}


def require_all_arms(reference_seal, seals, draw):
    for arm in ARMS:
        records = verify_predictions(seals[arm], arm, draw)
        for index, p in enumerate(records, 1):
            m = at(seals[arm], filename(arm, index, "measure", "attempt.json"))
            require(m["arm"] == arm and m["phase"] == "measure" and m["referenceSeal"] == p["referenceSeal"] == reference_seal
                    and m["url"] == p["url"] and m["producerRevision"] == draw["producerRevision"]
                    and m["status"] in ("preparation stop", "operator stop", "measured", "partial measurement"),
                    "all three completed arm records must be present before adjudication")


def adjudicate(reference_seal, seals, output, overrides):
    draw = at(reference_seal, HERE / "draw.json")
    require_all_arms(reference_seal, seals, draw)
    refset = at(reference_seal, HERE / "references.json")["references"]
    decisions, totals = {}, Counter()
    for index, ref in enumerate(refset, 1):
        case = {}
        decisions[ref["canonicalPR"]] = case
        for arm in ARMS:
            rows = []
            case[arm] = {"candidates": rows}
            pred = at(seals[arm], filename(arm, index, "predict", "attempt.json"))
            if pred["status"] != "sealed":
                continue
            proposal = at(seals[arm], filename(arm, index, "predict", "prediction.json"))
            m = at(seals[arm], filename(arm, index, "measure", "attempt.json"))
            measured = {}
            if m["status"] in ("measured", "partial measurement"):
                runs = at(seals[arm], filename(arm, index, "measure", "measurement.json"))
                measured = {r["candidateIndex"]: r for r in runs["measurements"]}
            for rank, candidate in enumerate(proposal["candidates"]):
                value = judgment(candidate, ref, measured.get(rank))
                # A separate evaluator can register a witnessed equivalent route or another
                # interpretation against these exact candidate and reference digests.
                override = overrides.get(ref["canonicalPR"], {}).get(arm, {}).get(str(rank))
                if override:
                    require(value["candidateSha256"] == override["candidateSha256"] and value["referenceSha256"] == override["referenceSha256"],
                            "review override came from another frozen candidate or reference")
                    value = override
                rows.append(value)
                totals[value["kind"]] += 1
    write(output, decisions)
    print(dict(totals))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-seal", required=True)
    for arm in ARMS:
        parser.add_argument("--" + arm + "-seal", required=True)
    parser.add_argument("--overrides", type=Path)
    parser.add_argument("--output", type=Path, default=HERE / "judgments.json")
    args = parser.parse_args()
    adjudicate(args.reference_seal, {a: getattr(args, a.replace("-", "_")+"_seal") for a in ARMS},
               args.output, read(args.overrides) if args.overrides else {})

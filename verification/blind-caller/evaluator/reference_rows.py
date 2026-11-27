"""Capture the historical registrations and independently join their original observations."""
import argparse
from pathlib import Path

from eligibility_inventory import HERE, RESERVED, digest, example, read, write
from packet_view import HAZARD


SIDES = {"parent": "old", "fix": "new"}


def outcome(value):
    if not isinstance(value, dict) or not value:
        raise ValueError("empty historical public observation")
    return [{"field": field, "type": type(data).__name__, "value": data} for field, data in sorted(value.items())]


def disposition(expected, actual):
    matches = {side: (actual.get(side) == value if side in actual else None) for side, value in expected.items()}
    if not matches or None in matches.values():
        return "open", "missing required side"
    if matches.get("old") is False:
        return "open", "incorrect parent baseline"
    if matches.get("new") is False:
        return "refuted", "fixed prediction contradicted"
    return "established", "every required side matched"


def reference(row):
    if row["number"] in RESERVED:
        raise ValueError("reserved case")
    folder = example(row["number"])
    cp, rp, op = (folder / name for name in ("comparison.json", "runtime.json", "observations.json"))
    spec, runtime, physical = map(read, (cp, rp, op))
    if spec["revisions"] != row["pins"] or physical["comparisonSha256"] != digest(cp) or physical["runtimeSha256"] != digest(rp):
        raise ValueError("historical pin or registration digest differs")
    if set(runtime["deployments"]) != set(physical["deployments"]):
        raise ValueError("historical runtime and observed deployment sets differ")
    variants = {}
    for name, dep in runtime["deployments"].items():
        variants[name] = {"bindings": {side: {
            "revision": row["pins"][original],
            "classpathSha256": [runtime["sha256"][f] for f in dep["classpath"][original]],
            "providers": {owner: {"classpathIndex": index, "artifactSha256": runtime["sha256"][dep["classpath"][original][index]]}
                          for owner, index in dep["providers"].items()}}
            for original, side in SIDES.items()}, "jdkReleaseSha256": runtime["jdkReleaseSha256"]}
    questions = []
    for q in spec["questions"]:
        expected = {SIDES[s]: outcome(v) for s, v in q["expected"].items()}
        results = {}
        for label, dep in physical["deployments"].items():
            hits = [entry for entry in dep["observations"] if entry["id"] == q["id"]]
            actual = {SIDES[e["side"]]: outcome(e["outcome"]) for e in hits}
            if len(hits) != len(actual):
                raise ValueError("ambiguous original observation for a registered side")
            status, reason = disposition(expected, actual)
            results[label] = {"actual": actual, "unpredictedSides": sorted(set(actual) - set(expected)),
                              "finiteDisposition": status, "reason": reason}
        questions.append({"id": q["id"], "role": q["role"], "registeredHistory": q["history"],
                          "privateCallerArgs": q["args"], "registeredPrediction": q["prediction"],
                          "refutation": q["refutation"], "expected": expected,
                          "requiredSides": list(expected), "variants": results})
    primary = next((i for i, q in enumerate(questions) if q["role"] == "Intent"), None)
    if primary is None or len({q["id"] for q in questions}) != len(questions):
        raise ValueError("missing primary or duplicate historical question")
    return {"canonicalPR": row["canonicalPR"], "url": row["url"], "entry": spec["entry"], "variants": variants,
            "comparisonSha256": digest(cp), "runtimeSha256": digest(rp), "observationsSha256": digest(op),
            "primaryIndex": primary, "questions": questions,
            "safetyAbstention": any(HAZARD.search(q[field]) for q in questions for field in ("registeredHistory", "registeredPrediction", "refutation"))}


def check_semantics(record):
    """The evaluator supplies semantic rows before any prediction is inspected or measured."""
    sem = record.get("semantics")
    if not isinstance(sem, dict):
        raise ValueError("the primary needs evaluator-registered public semantics")
    for key in ("entry", "history"):
        if not isinstance(sem.get(key), str) or not sem[key].strip():
            raise ValueError("incomplete semantic entry or history")
    for key in ("inputs", "fields", "actions"):
        if not isinstance(sem.get(key), list) or not sem[key]:
            raise ValueError("missing typed semantic inputs, readbacks or ordered actions")
    for item in sem["inputs"]:
        if not all(isinstance(item.get(k), str) and item[k].strip() for k in ("name", "type")):
            raise ValueError("semantic input requires a named type")
        if "value" not in item and "constraint" not in item:
            raise ValueError("semantic input needs a value or finite constraint")
    for item in sem["fields"]:
        if not all(isinstance(item.get(k), str) and item[k].strip() for k in ("name", "type", "readback")):
            raise ValueError("semantic field requires its type and public readback")
    if len({x["name"] for x in sem["fields"]}) != len(sem["fields"]):
        raise ValueError("duplicate semantic field")
    if not all(isinstance(x, str) and x.strip() for x in sem["actions"]):
        raise ValueError("missing ordered action")
    if not isinstance(sem.get("bindings"), list) or not sem["bindings"]:
        raise ValueError("a primary needs a public entry or receiver binding obligation")
    return sem


def reviewed(record):
    sem = check_semantics(record)
    primary = record["questions"][record["primaryIndex"]]
    return {k: sem[k] for k in ("entry", "history", "inputs", "actions", "bindings")} | {
        "fields": [item["name"] for item in sem["fields"]], "fieldTypes": sem["fields"],
        "requiredSides": sorted(primary["requiredSides"], key=("old", "new").index)}


def capture(draw, semantics, destination):
    population = {r["number"]: r for r in read(HERE / "eligibility.json")["rows"]}
    records = []
    for item in draw["cases"]:
        row = population[item["number"]]
        if not row["eligible"] or row["url"] != item["url"] or row["pins"] != item["pins"]:
            raise ValueError("draw is inconsistent with sealed population")
        ref = reference(row)
        if semantics is not None:
            ref["semantics"] = semantics[row["canonicalPR"]]
            check_semantics(ref)
        records.append(ref)
    if semantics is not None and set(semantics) != {r["canonicalPR"] for r in records}:
        raise ValueError("semantic registration must cover exactly the draw")
    result = {"schema": "blind-caller-reference/v1", "producerRevision": draw["producerRevision"],
              "preregistration": draw["preregistration"], "references": records}
    if destination.exists() and read(destination) != result:
        raise ValueError("a different reference already exists at the destination")
    write(destination, result)
    print(f"{len(records)} primary references, {sum(len(r['questions']) for r in records)} questions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draw", type=Path, default=HERE / "draw.json")
    parser.add_argument("--semantics", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    capture(read(args.draw), read(args.semantics) if args.semantics else None, args.output)

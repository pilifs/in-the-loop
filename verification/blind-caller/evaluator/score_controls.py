"""Independently qualify the disclosed scalar fixture and alter its evidence one fact at a time."""
import argparse
from copy import deepcopy
from pathlib import Path

from eligibility_inventory import HERE, digest, read, write
from paired_score import qualified_observations, score_fields


def exercise(root, output):
    packet = read(root / "packet/packet.json")
    candidate = read(root / "sealed/prediction.json")["candidates"][0]
    measurement = read(root / "cold/measurement.json")["measurements"][0]
    if candidate["entry"] != "trial.PublicValue#sample(I)I":
        raise ValueError("controls require the public synthetic scalar fixture")
    evidence = {k: (root / "cold" / v["path"]).read_bytes() for k, v in measurement["evidence"].items()}
    ref = {"primaryIndex": 0, "questions": [{"requiredSides": ["old", "new"],
            "variants": {"pins": {"finiteDisposition": "established"}}}],
           "variants": {"pins": {"jdkReleaseSha256": packet["jdkReleaseSha256"], "bindings": {
               s: {"revision": packet[s + "Revision"], "classpathSha256": [x["sha256"] for x in packet[s]["classpath"]]}
               for s in ("old", "new")}}},
           "semantics": {"observedFields": {"pins": {"old": {"firstValue": "1"}, "new": {"firstValue": "2"}}}}}
    judgment = {"fieldCorrespondence": {"firstValue": {"candidateField": "return.scalar", "input": 0, "path": [0, 2]}}}
    observed, _, _, status = qualified_observations(candidate, measurement, evidence, ref, "pins")
    if (status != "established" or score_fields(judgment, candidate, ref, measurement, evidence, "pins") != ("established", True)
            or len(observed["old"]) != 4 or len(observed["new"]) != 4):
        raise ValueError("public positive scalar control lost its original observations")
    failures = {}
    for kind in ("swapped class", "wrong old compilation", "changed archive", "missing return",
                 "sorted equal totals", "different typed field", "missing action provenance"):
        m, e, r, j = deepcopy(measurement), evidence.copy(), deepcopy(ref), deepcopy(judgment)
        if kind == "swapped class":
            m["entryBindings"]["old"]["classSha256"] = m["entryBindings"]["new"]["classSha256"]
        elif kind == "wrong old compilation":
            m["caller"]["compileAgainst"] = "new"
        elif kind == "changed archive":
            e["bytecode"] += b"unregistered"
        elif kind == "missing return":
            m["observations"]["old"].pop()
        elif kind == "sorted equal totals":
            r["semantics"]["observedFields"]["pins"] = {"old": {"firstValue": "2"}, "new": {"firstValue": "1"}}
        elif kind == "different typed field":
            r["semantics"]["observedFields"]["pins"]["old"]["firstValue"] = 1
        else:
            r["semantics"]["requiresActionWitness"] = True
            r["semantics"]["actionWitnesses"] = [{"member": "trial.PublicValue#readAfter()I", "role": "return", "receiverHandle": "original"}]
        try:
            score_fields(j, candidate, r, m, e, "pins")
        except ValueError as error:
            failures[kind] = str(error)
        else:
            raise ValueError("a planted false qualification survived: " + kind)
    opposite = deepcopy(measurement)
    opposite["status"] = "refuted"
    finite, agrees = score_fields(judgment, candidate, ref, opposite, evidence, "pins")
    if agrees or finite != "established":
        raise ValueError("altered finite disposition was accepted")
    failures["wrong published disposition"] = "underlying ordinary plan retained its established disposition"
    write(output, {"schema": "blind-caller-evaluator-controls/v1", "positive": status,
                   "qualifiedOriginalInputSides": sum(map(len, observed.values())),
                   "predictionSha256": digest(root / "sealed/prediction.json"),
                   "measurementSha256": digest(root / "cold/measurement.json"), "rejected": failures})
    print(f"eight original input sides qualified, {len(failures)} independent false qualifications rejected")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--output", type=Path, default=HERE / "score-control-evidence.json")
    args = parser.parse_args()
    exercise(args.fixture, args.output)

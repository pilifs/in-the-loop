"""Take the separately labelled, post-reveal production-origin repair through the frozen workers."""
import argparse
from pathlib import Path

from adjudicate import judgment
from eligibility_inventory import HERE, read, write
from evaluate_arm import at, filename, run_one
from paired_score import attempt_result, require
from phase_job import pack


def context(score_seal):
    score = at(score_seal, HERE / "score.json")
    reference = score["referenceSeal"]
    draw = at(reference, HERE / "draw.json")
    choices = []
    for i in range(1, len(draw["cases"])+1):
        prior = at(score["armSeals"]["cold"], filename("cold", i, "predict", "attempt.json"))
        if prior.get("reason") == "a deployment embeds an original upstream test class":
            choices.append(i)
    require(len(choices) == 1, "expected the single documented original packaging stop")
    return choices[0], score, reference, draw


def score_repair(revision, original, output):
    index, first_score, reference, draw = context(original)
    ref = at(reference, HERE / "references.json")["references"][index-1]
    p = at(revision, filename("repaired", index, "predict", "attempt.json"))
    m = at(revision, filename("repaired", index, "measure", "attempt.json"))
    require(p["repairAfter"] == m["repairAfter"] == original and p["originSha256"] == m["originSha256"],
            "post-reveal prediction and measurement use different original production bytes")
    candidates = at(revision, filename("repaired", index, "predict", "prediction.json"))["candidates"] if p["status"] == "sealed" else []
    rows = at(revision, filename("repaired", index, "measure", "measurement.json"))["measurements"] if m["status"] in ("measured", "partial measurement") else []
    measured = {r["candidateIndex"]: r for r in rows}
    decisions = {"candidates": [judgment(c, ref, measured.get(i)) for i, c in enumerate(candidates)]}
    result = attempt_result(reference, revision, "repaired", index, draw, ref, decisions)
    result["assistance"] = "Post-reveal evaluator production-origin repair. Frozen generator and original artifacts."
    write(output, {"schema": "post-reveal-packaging-repair/v1", "originalScoreSeal": original, "repairSeal": revision,
                   "case": ref["url"], "caseIndex": index, "countedInOriginalColdScore": False,
                   "attempted": 1, "qualified": int(result["primaryQualified"]), "originalCounts": first_score["counts"], "repair": result})
    print("post-reveal repaired primaries:", int(result["primaryQualified"]), "of 1")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("predict", "measure", "score"))
    parser.add_argument("--original-score", required=True)
    parser.add_argument("--prediction-seal")
    parser.add_argument("--repair-seal")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.phase == "score":
        score_repair(args.repair_seal, args.original_score, args.output or HERE / "repair-score.json")
    else:
        index, _, reference, _ = context(args.original_score)
        status = run_one(index, args.phase, "cold", reference, None, args.prediction_seal, seconds=None, repair_after=args.original_score)
        if args.output:
            pack([filename("repaired", index, args.phase, "attempt.json").parent], args.output)
        print("post-reveal original-origin attempt:", status)

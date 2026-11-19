"""Independently enumerate the input domain and check the return, frame and cell rule."""

import itertools
import json


def driver_args():
    return ["--all"]


def problems(lines):
    remaining = {(scores, slot, score) for n in range(1, 4)
                 for scores in itertools.product(range(3), repeat=n)
                 for slot in range(n) for score in range(3)}
    errors = []
    for line in lines:
        row = json.loads(line)
        scores, slot, score = tuple(row["scores"]), row["slot"], row["score"]
        key = scores, slot, score
        remaining.remove(key)
        expected = [score if i == slot else mark for i, mark in enumerate(scores)]
        if row["result"] != scores[slot]:
            errors.append((key, "return-only"))
        if row["after"] != expected:
            errors.append((key, "full-state"))
            if slot + 1 < len(scores):
                errors.append((key, "interior-state"))
        if len(row["after"]) != len(scores) or any(
                row["after"][i] != mark for i, mark in enumerate(scores) if i != slot):
            errors.append((key, "untargeted-cells"))
    if remaining:
        raise ValueError(f"{len(remaining)} missing inputs")
    return errors

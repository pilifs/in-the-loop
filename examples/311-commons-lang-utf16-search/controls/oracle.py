"""Enumerate tokens and compute UTF-16 offsets independently of the Java adapter and StringUtils."""

from itertools import product
import json


def driver_args():
    return ["--all"]


def observations(lines):
    expected = {}
    for size in range(4):
        for tokens in product(range(3), repeat=size):
            code = sum((token + 1) * 3**i for i, token in enumerate(tokens))
            for needle in range(4):
                matches = [sum(2 if t == 2 else 1 for t in tokens[:i]) for i, t in enumerate(tokens) if t == needle]
                expected[code, needle] = matches[-1] if matches else -1
    rows = []
    for line in lines:
        row = json.loads(line)
        key = row["sequence"], row["needle"]
        answer = expected.pop(key)
        if row["expected"] != answer:
            raise ValueError(f"Java token oracle disagrees at {key}")
        rows.append((key, row["direct"], row["adapter"], answer))
    if expected:
        raise ValueError(f"{len(expected)} missing cases")
    return rows


def correspondence(lines):
    rows = observations(lines)
    return {"cases": len(rows), "disagreements": sum(d != a for _, d, a, _ in rows)}


def problems(lines):
    return [(key, f"expected {expected}, direct {direct}, adapter {adapter}")
            for key, direct, adapter, expected in observations(lines) if direct != expected or direct != adapter]

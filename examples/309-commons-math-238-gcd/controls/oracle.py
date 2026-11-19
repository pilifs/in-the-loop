"""Compute the expected GCD from exponents, and check the separate zero family."""

import json


def driver_args():
    return ["--all"]


def problems(lines):
    rows = [json.loads(line) for line in lines]
    if len(rows) != 22 or len(rows[-1]["zero"]) != 256:
        raise ValueError("missing GCD calibration cases")
    errors = []
    for i, row in enumerate(rows[:-1]):
        if row["i"] != i or len(row["powers"]) != 21:
            raise ValueError("missing exponent pair")
        for j, actual in enumerate(row["powers"]):
            if actual != 1 << min(i, j):
                errors.append(([1 << i, 1 << j], "powers"))
    for n, actual in enumerate(rows[-1]["zero"]):
        if actual != n:
            errors.append(([0, n], "zero"))
    if rows[-1]["apacheCase"] != 98304:
        errors.append(([3 << 20, 9 << 15], "Apache regression assertion"))
    return errors

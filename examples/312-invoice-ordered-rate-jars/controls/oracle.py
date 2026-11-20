"""An invoice has the rate identified by the loaded JAR and the signed quantity."""

import json


def driver_args():
    return ["--all"]


def problems(lines):
    pending = set(range(-2, 3))
    errors = []
    for line in lines:
        row = json.loads(line)
        q = row["q"]
        pending.remove(q)
        rate = {"two.jar": 2, "three.jar": 3}[row["rateJar"]]
        if row["total"] != q * rate:
            errors.append([q, "wrong amount for the loaded rate"])
    if pending:
        raise ValueError(f"missing quantities {sorted(pending)}")
    return errors

import json
from itertools import product


def driver_args():
    return ["--observations"]


def problems(lines):
    alphabet = (-(1 << 63), 7, (1 << 40) + 7, (1 << 63) - 1)
    missing = {(cells, target) for length in range(5) for cells in product(alphabet, repeat=length) for target in alphabet}
    differences = []
    for line in lines:
        row = json.loads(line)
        cells, target = tuple(row["before"]), row["target"]
        missing.remove((cells, target))
        expected = cells.index(target) if target in cells else -1
        if row["result"] != expected or row["after"] != list(cells):
            differences.append([row["id"], f"expected first index {expected} and the original array"])
    if missing:
        raise ValueError("the direct driver omitted array/target pairs")
    return differences

"""The reference poststate, independently specified for each input heap."""

from itertools import product
import json
import sys

CONTENTS = [list(c) for n in range(3) for c in product((0, 1), repeat=n)]


def driver_args():
    return ["--observations"]


def compare(lines):
    remaining = {(l, r, False) for l in range(-1, 7) for r in range(-1, 7)}
    remaining.update((i, i, True) for i in range(7))
    differences = {"return-only": [], "right-root": [], "both-roots": []}
    for line in lines:
        row = json.loads(line)
        l, r, shared = key = (row["l"], row["r"], row["shared"])
        if type(shared) is not bool or key not in remaining:
            raise ValueError(f"invalid or duplicated input {key}")
        remaining.remove(key)
        left = None if l < 0 else CONTENTS[l].copy()
        right = None if r < 0 else CONTENTS[r].copy()
        if left and right:
            left[0] = 1
            if shared:
                right[0] = 1
        if row["result"] != 0:
            differences["return-only"].append(key)
        if row["right"] != right:
            differences["right-root"].append(key)
        if row["left"] != left or row["right"] != right:
            differences["both-roots"].append(key)
    if remaining:
        raise ValueError(f"{len(remaining)} required heaps missing")
    return differences


def problems(lines):
    differences = compare(lines)
    return [(list(case), name) for name, cases in differences.items() for case in cases]


if __name__ == "__main__" and sys.argv[1:] == ["self-test"]:
    assert CONTENTS == [[], [0], [1], [0, 0], [0, 1], [1, 0], [1, 1]]

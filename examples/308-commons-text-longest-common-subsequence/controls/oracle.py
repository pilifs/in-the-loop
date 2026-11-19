"""Check the scores printed by the public-method driver on all ordered pairs."""

from itertools import combinations, product
import json
import sys


def driver_args():
    return ["--observations"]


def score(left, right):
    for length in range(len(left), 0, -1):
        for sequence in combinations(left, length):
            rest = iter(right)
            if all(unit in rest for unit in sequence):
                return length
    return 0


def problems(lines):
    words = {"".join(p) for n in range(4) for p in product("ab", repeat=n)}
    missing = set(product(words, repeat=2))
    differences = []
    for line in lines:
        observed = json.loads(line)
        pair = (observed["left"], observed["right"])
        if pair not in missing or type(observed["score"]) is not int:
            raise ValueError(f"invalid or duplicate observation for {pair}")
        missing.remove(pair)
        expected = score(*pair)
        if observed["score"] != expected:
            differences.append([list(pair), f"score {observed['score']}, expected {expected}"])
    if missing:
        raise ValueError(f"{len(missing)} pairs missing")
    return differences


if __name__ == "__main__" and sys.argv[1:] == ["self-test"]:
    assert [score(*p) for p in [("", "ab"), ("aa", "aaa"), ("ab", "aa"), ("aba", "bab")]] == [0, 2, 1, 2]

"""Independent CSV field encoder and completeness check for the calibration JVM."""

import itertools
import json
import sys


ALPHABET = (97, 44, 34, 13, 10)
SPECIAL = frozenset((44, 34, 13, 10))


def driver_args():
    return ["--all"]


def expected(field):
    if SPECIAL.isdisjoint(field):
        return list(field)
    result = [34]
    for unit in field:
        result.append(unit)
        if unit == 34:
            result.append(34)
    result.append(34)
    return result


def problems(lines):
    missing = {field for size in range(4) for field in itertools.product(ALPHABET, repeat=size)}
    differences = []
    for line in lines:
        row = json.loads(line)
        field = tuple(row["input"])
        if field not in missing or not all(type(unit) is int for unit in field):
            raise ValueError(f"invalid or duplicate input {field}")
        missing.remove(field)
        wanted = expected(field)
        actual = row.get("returned")
        if set(row) != {"input", "returned"} or not isinstance(actual, list) or (
            not all(type(unit) is int for unit in actual) or wanted != actual
        ):
            differences.append([list(field), {"expected": wanted, "observed": row}])
    if missing:
        raise ValueError(f"{len(missing)} fields missing from the JVM output")
    return differences


if __name__ == "__main__" and sys.argv[1:] == ["self-test"]:
    assert expected(()) == []
    assert expected((97,)) == [97]
    assert expected((34,)) == [34, 34, 34, 34]
    assert expected((13, 10)) == [34, 13, 10, 34]
    assert expected((97, 44, 34)) == [34, 97, 44, 34, 34, 34]

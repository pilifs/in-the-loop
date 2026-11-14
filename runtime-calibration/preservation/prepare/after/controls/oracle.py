"""The fixture's independent oracle: written from the statement, not from either revision's code.

Security property: a field named by the denied code, in either case ('A' = 65, 'a' = 97), is never allowed.
Legitimate behaviour: every other code in the probe set is allowed. Each revision's driver output (one JSON line per
input) is checked against it; the oracle never calls the implementation under test."""

import json

DENIED = {65, 97}
TRIGGER = [97]  # the spelling the vulnerable revision forgets
LEGITIMATE = [0, 64, 66, 96, 98, -1, 2147483647]
PROBES = sorted(set(TRIGGER) | {65} | set(LEGITIMATE))


def expected(code):
    return code not in DENIED


def check(lines):
    """[(input, problem)] for each observation the statement disagrees with, from the driver's stdout lines. An
    unreadable line or a missing probe is a replay problem: it raises, never counts as a violation."""
    seen = {}
    for line in lines:
        record = json.loads(line)
        seen[record["input"]] = record
    missing = [p for p in PROBES if p not in seen]
    if missing:
        raise ValueError(f"no observation for {missing}: an incomplete replay")
    problems = []
    for code in PROBES:
        record = seen[code]
        if record["outcome"] != "returned":
            problems.append((code, f"threw {record.get('exception')}"))
        elif record["value"] != expected(code):
            problems.append((code, f"returned {record['value']}, the statement says {expected(code)}"))
    return problems

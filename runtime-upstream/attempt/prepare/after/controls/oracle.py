"""The upstream-build check's independent oracle, written from `ArithmeticUtils.pow(int, int)`'s Javadoc at the pinned
commits (the same text before and after the fix), not from its code:

    Raise an int to an int power. Special cases: k^0 returns 1 (including k=0); k^1 returns k (including k=0); 0^0
    returns 1; 0^e returns 0; 1^e returns 1; (-1)^e returns -1 or 1 if e is odd or even.
    Returns: k^e. Throws: IllegalArgumentException if e < 0; ArithmeticException if the result would overflow.

Read as a statement: for e < 0, an IllegalArgumentException; otherwise the exact integer k^e when it is an int (from
-2^31 to 2^31 - 1, both included), and an ArithmeticException when it isn't. This is a conformance oracle for the
runtime's upstream-build route (llm-dlc/loops/example-targets-runtime.md, R2), not example 105's packet, which the
positive stream owns. Each revision's driver output (one JSON line per input) is checked against it; it never calls
the implementation under test. By the statement, `pow(-2, 31)` is -2^31, an int: the one probe the fix changes."""

import json

INT_MIN, INT_MAX = -2 ** 31, 2 ** 31 - 1

# [k, e] pairs, in the order the driver is given them.
PROBES = [
    # the documented special cases
    [0, 0], [5, 0], [-7, 0], [0, 1], [9, 1], [-9, 1], [0, 5], [1, 0], [1, 1000], [-1, 7], [-1, 8], [-1, 2 ** 31 - 1],
    # a negative exponent, also where a special case would otherwise answer
    [2, -1], [0, -1], [1, -1], [-1, -1], [3, INT_MIN],
    # ordinary powers, odd and even exponents, negative bases
    [2, 10], [3, 5], [-3, 3], [-3, 4], [10, 9], [7, 11],
    # the int range's edges: the largest powers that fit, and the first that don't
    [2, 30], [2, 31], [-2, 30], [-2, 31], [-2, 32], [46340, 2], [46341, 2], [-46341, 2], [1290, 3], [1291, 3],
    [-1290, 3], [-1291, 3], [3, 19], [3, 20], [10, 10],
    # the extreme bases
    [INT_MAX, 1], [INT_MIN, 1], [INT_MAX, 2], [INT_MIN, 2], [INT_MIN, 0], [2, 63], [2, INT_MAX],
]


def expected(k, e):
    """(outcome, value or exception class) by the statement."""
    if e < 0:
        return "threw", "java.lang.IllegalArgumentException"
    # |k| >= 2 and e > 64 is certainly beyond the int range: not computed. (Python's 0 ** 0 is 1.)
    exact = k ** e if k in (0, 1, -1) or e <= 64 else None
    if exact is not None and INT_MIN <= exact <= INT_MAX:
        return "returned", exact
    return "threw", "java.lang.ArithmeticException"


def key(value):
    return json.dumps(value)


def check(lines):
    """[(input, problem)] for each observation the statement disagrees with, from the driver's stdout lines. An
    unreadable line or a missing probe is a replay problem: it raises, never counts as a disagreement."""
    seen = {}
    for line in lines:
        record = json.loads(line)
        seen[key(record["input"])] = record
    missing = [p for p in PROBES if key(p) not in seen]
    if missing:
        raise ValueError(f"no observation for {missing}: an incomplete replay")
    problems = []
    for probe in PROBES:
        record, (outcome, what) = seen[key(probe)], expected(*probe)
        if record["outcome"] != outcome:
            problems.append((probe, f"{record['outcome']} {record.get('value', record.get('exception'))}, the "
                                    f"statement says {outcome} {what}"))
        elif outcome == "returned" and record["value"] != what:
            problems.append((probe, f"returned {record['value']}, the statement says {what}"))
        elif outcome == "threw" and record["exception"] != what:
            problems.append((probe, f"threw {record['exception']}, the statement says {what}"))
    return problems

"""The runtime slice's independent oracle, written from PatternMatchUtils.simpleMatch's Javadoc, not from its code:

    Match a String against the given pattern, supporting the following simple pattern styles: "xxx*", "*xxx", "*xxx*"
    and "xxx*yyy" matches (with an arbitrary number of pattern parts), as well as direct equality.
    Returns: whether the String matches the given pattern; false if either the pattern or the String is null.

Read as a statement: '*' matches any sequence of characters, the empty one and line breaks included; every other
character, regular-expression metacharacters included, matches only itself, case-sensitively; a null pattern or string
never matches. This is a conformance oracle for the runtime's vertical slice (llm-dlc/loops/example-targets-runtime.md,
R5), not a security property. Each revision's driver output (one JSON line per input) is checked against it; it never
calls the implementation under test."""

import json
import re

# [pattern, string] pairs, in the order the driver is given them. None is Java's null.
PROBES = [
    # direct equality
    ["abc", "abc"], ["abc", "abd"], ["", ""], ["", "a"], ["a", ""],
    # null on either side
    [None, "a"], ["a", None], [None, None],
    # "xxx*"
    ["ab*", "ab"], ["ab*", "abc"], ["ab*", "a"], ["ab*", "ba"],
    # "*xxx", "*" alone
    ["*bc", "abc"], ["*bc", "bcx"], ["*", ""], ["*", "anything"],
    # "*xxx*"
    ["*b*", "abc"], ["*b*", "ac"],
    # "xxx*yyy", several parts
    ["a*c", "abc"], ["a*c", "ac"], ["a*c", "ab"], ["a*c*e", "abcde"], ["a*c*e", "abced"],
    # adjacent stars, overlapping parts, and parts that need a later occurrence
    ["**", "x"], ["a**b", "ab"], ["*a*a*", "aa"], ["*a*a*", "a"], ["aa*a", "aa"], ["a*a", "a"],
    ["*ab*ab", "xabyab"], ["*aab", "aaab"], ["*a*b", "acab"], ["*a*b", "acba"],
    # case: the binder family's question, answered case-sensitively by the statement
    ["Name*", "name"], ["name*", "NAME"], ["name*", "name"],
    # a line break inside the starred part
    ["a*b", "a\nb"],
    # characters a regular expression would treat specially
    [".*", "ab"], [".*", ".ab"], ["a.c", "abc"], ["[a]*", "[a]x"], ["a+", "aa"],
    # beyond ASCII, one character outside the BMP included
    ["é*", "éa"], ["*\U0001F600", "x\U0001F600"], ["Straße*", "STRASSE"],
]


def expected(pattern, text):
    if pattern is None or text is None:
        return False
    parts = [".*" if c == "*" else re.escape(c) for c in pattern]
    return re.fullmatch("".join(parts), text, re.DOTALL) is not None


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
        record = seen[key(probe)]
        if record["outcome"] != "returned":
            problems.append((probe, f"threw {record.get('exception')}"))
        elif record["value"] != expected(*probe):
            problems.append((probe, f"returned {record['value']}, the statement says {expected(*probe)}"))
    return problems

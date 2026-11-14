"""305's independent oracle: written from the HTTP status-code classes, not from either revision's code.

The statement: WebMvcTags.outcome(response) returns a Tag whose key is "outcome". Its value is UNKNOWN for a null
response. Otherwise it names the class of the status the response reports: a status code is a three-digit integer
whose first digit defines its class (RFC 9110, section 15): 1 INFORMATIONAL, 2 SUCCESS, 3 REDIRECTION, 4 CLIENT_ERROR,
5 SERVER_ERROR, the names Boot documents for its `outcome` tag. Anything else (fewer or more than three digits, a sign,
a first digit 0 or 6 to 9) has no class: UNKNOWN. Nothing is thrown. This is the label both revisions must give
(claims/outcome-preservation.json) and the one the constructed mutant (controls/status-200.patch) must miss at 200.

The class is read from the status's decimal spelling, an algorithm unlike either revision's (before divides by 100 and
searches HttpStatus.Series; after compares against five ranges). Each revision's driver output (replay/driver, one JSON
line per probe) is checked against it, and the revisions' lines against each other; the oracle never calls the
implementation under test. It reads replay/probes.json; it parses nothing else and downloads nothing.

    python3 -I oracle.py argv            the driver's argument vector, one argument per line
    python3 -I oracle.py check FILE...   each file one revision's driver stdout; exit 1 if any disagrees
"""

import json
import sys
from pathlib import Path

PROBES_FILE = Path(__file__).resolve().parent.parent / "replay" / "probes.json"
KEY = "outcome"
CLASSES = {"1": "INFORMATIONAL", "2": "SUCCESS", "3": "REDIRECTION", "4": "CLIENT_ERROR", "5": "SERVER_ERROR"}
INT_MIN, INT_MAX = -(2 ** 31), 2 ** 31 - 1


def load_probes(path=PROBES_FILE):
    probes = json.loads(Path(path).read_text(encoding="utf-8"))["probes"]
    for p in probes:
        if p is not None and not (isinstance(p, int) and not isinstance(p, bool) and INT_MIN <= p <= INT_MAX):
            raise ValueError(f"a probe is null or a Java int: {p!r}")
    return probes


def token(probe):
    """The driver's spelling of one probe: `null` (a null response) or the status in decimal."""
    return "null" if probe is None else str(probe)


def expected(probe):
    """The statement's (key, value)."""
    if probe is None:
        return KEY, "UNKNOWN"
    digits = str(probe)
    if len(digits) == 3 and digits[0] in CLASSES:
        return KEY, CLASSES[digits[0]]
    return KEY, "UNKNOWN"


def argv(probes):
    return [token(p) for p in probes]


def read(lines, probes):
    """{probe token: record} from one revision's driver lines. An unreadable line or a missing probe is a replay
    problem: it raises, never counts as a disagreement."""
    seen = {}
    for line in lines:
        if line.strip():
            record = json.loads(line)
            seen[record["probe"]] = record
    missing = [token(p) for p in probes if token(p) not in seen]
    if missing:
        raise ValueError(f"no observation for {missing}: an incomplete replay")
    return seen


def observed(record):
    """What the claim observes: termination, the exception's class, or the tag's key and value. getStatusCalls is the
    carrier's annotation, never part of it."""
    return (record["outcome"], record.get("exception"), record.get("key"), record.get("value"))


def check(lines, probes):
    """[(probe, problem)] for each observation of one revision the statement disagrees with."""
    seen = read(lines, probes)
    problems = []
    for p in probes:
        record = seen[token(p)]
        if record["outcome"] != "returned":
            problems.append((token(p), f"threw {record.get('exception')}"))
        elif (record.get("key"), record.get("value")) != expected(p):
            problems.append((token(p), f"returned {record.get('key')}={record.get('value')}, the statement says "
                                       f"{'='.join(expected(p))}"))
    return problems


def differences(before_lines, after_lines, probes):
    """[(probe, before record, after record)] where two revisions' observations differ: the preservation side."""
    before, after = read(before_lines, probes), read(after_lines, probes)
    return [(token(p), before[token(p)], after[token(p)]) for p in probes
            if observed(before[token(p)]) != observed(after[token(p)])]


def coverage(probes):
    """The values the probes expect: the brief asks for every class, UNKNOWN included, and both sides of each
    boundary."""
    return sorted({expected(p)[1] for p in probes})


# The runner's interface (examples/tools/targets/runtime.py's docstring, "the oracle convention"): what
# runtime.run_controls passes the driver, and how workflow_ingest reads one revision's lines. An exception is a replay
# that can't be judged, never a violation.

def _checked_probes():
    probes = load_probes()
    if coverage(probes) != sorted(set(CLASSES.values()) | {"UNKNOWN"}):
        raise ValueError("the probes don't reach every outcome value")
    return probes


def driver_args():
    """The driver's whole argument vector."""
    return argv(_checked_probes())


def problems(lines):
    """[(probe, problem)] where one revision's lines disagree with the statement."""
    return check(lines, _checked_probes())


def main(args):
    probes = load_probes()
    if coverage(probes) != sorted(set(CLASSES.values()) | {"UNKNOWN"}):
        raise SystemExit("the probes don't reach every outcome value")
    if args[:1] == ["argv"]:
        print("\n".join(argv(probes)))
        return 0
    if args[:1] == ["check"] and len(args) > 1:
        outputs = [Path(f).read_text(encoding="utf-8").splitlines() for f in args[1:]]
        failed = False
        for name, lines in zip(args[1:], outputs):
            problems = check(lines, probes)
            failed = failed or bool(problems)
            print(json.dumps({"file": name, "probes": len(probes), "problems": problems}))
        for name, lines in zip(args[2:], outputs[1:]):
            diff = differences(outputs[0], lines, probes)
            failed = failed or bool(diff)
            print(json.dumps({"file": name, "against": args[1], "differences": [d[0] for d in diff]}))
        return 1 if failed else 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

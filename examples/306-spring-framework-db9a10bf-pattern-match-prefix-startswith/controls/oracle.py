"""306's independent oracle: written from the statement of a glob match, not from either revision's code.

The statement: simpleMatch(pattern, str) is false when either is null; otherwise it is true exactly when str is the
pattern with each '*' replaced by some sequence of code units, the empty one included, every other code unit matching
itself. Strings are sequences of UTF-16 code units, compared unit by unit: no case folding, locale or normalization.
This is the decision both revisions must give (claims/simple-match-preservation.json) and the one the constructed
mutant (controls/drop-prefix.patch) must miss.

The decision is computed by dynamic programming over the code units, an algorithm unlike either revision's (which
search for each star-free part and recurse). Each revision's driver output (replay/driver, one JSON line per probe) is
checked against it, and the two revisions' lines against each other; the oracle never calls the implementation under
test. It reads replay/probes.json; it parses nothing else and downloads nothing.

    python3 -I oracle.py argv            the driver's argument vector, one argument per line
    python3 -I oracle.py check FILE...   each file one revision's driver stdout; exit 1 if any disagrees
"""

import json
import sys
from pathlib import Path

PROBES_FILE = Path(__file__).resolve().parent.parent / "replay" / "probes.json"
STAR = 0x2A


def units(s):
    """The UTF-16 code units of a Python string (isolated surrogates kept), or None."""
    if s is None:
        return None
    raw = s.encode("utf-16-le", "surrogatepass")
    return tuple(int.from_bytes(raw[i:i + 2], "little") for i in range(0, len(raw), 2))


def token(u):
    """The driver's spelling of one argument: `null`, or `u` and the code units in hex, comma-separated."""
    return "null" if u is None else "u" + ",".join(f"{c:04x}" for c in u)


def load_probes(path=PROBES_FILE):
    probes = json.loads(Path(path).read_text(encoding="utf-8"))["probes"]
    return [(units(p), units(s)) for p, s in probes]


def expected(pattern, s):
    """The statement's decision, by dynamic programming: matched[j] says whether the pattern read so far matches the
    first j units of s."""
    if pattern is None or s is None:
        return False
    matched = [True] + [False] * len(s)
    for p in pattern:
        if p == STAR:
            for j in range(1, len(s) + 1):
                matched[j] = matched[j] or matched[j - 1]
        else:
            matched = [False] + [matched[j] and s[j] == p for j in range(len(s))]
    return matched[len(s)]


def reaches_prefix_check(pattern, s):
    """Whether a probe reaches the changed expression, by the patch's structure (the first star after position 0, and
    str at least that long): a coverage annotation for the brief's "a true and a false case reach the changed branch",
    never part of the verdict."""
    if pattern is None or s is None or STAR not in pattern:
        return False
    first = pattern.index(STAR)
    return first > 0 and len(s) >= first


def argv(probes):
    return [t for p, s in probes for t in (token(p), token(s))]


def read(lines, probes):
    """{(pattern token, str token): record} from one revision's driver lines. An unreadable line or a missing probe is
    a replay problem: it raises, never counts as a disagreement."""
    seen = {}
    for line in lines:
        if line.strip():
            record = json.loads(line)
            seen[(record["pattern"], record["str"])] = record
    missing = [k for k in ((token(p), token(s)) for p, s in probes) if k not in seen]
    if missing:
        raise ValueError(f"no observation for {missing}: an incomplete replay")
    return seen


def check(lines, probes):
    """[(probe, problem)] for each observation of one revision the statement disagrees with."""
    seen = read(lines, probes)
    problems = []
    for p, s in probes:
        record = seen[(token(p), token(s))]
        if record["outcome"] != "returned":
            problems.append(((token(p), token(s)), f"threw {record.get('exception')}"))
        elif record["value"] is not expected(p, s):
            problems.append(((token(p), token(s)), f"returned {record['value']}, the statement says {expected(p, s)}"))
    return problems


def differences(before_lines, after_lines, probes):
    """[(probe, before record, after record)] where two revisions' observations differ: the preservation side."""
    before, after = read(before_lines, probes), read(after_lines, probes)
    keys = [(token(p), token(s)) for p, s in probes]
    observed = lambda r: (r["outcome"], r.get("value"), r.get("exception"))
    return [(k, before[k], after[k]) for k in keys if observed(before[k]) != observed(after[k])]


def coverage(probes):
    """The values the probes that reach the changed expression expect: the brief asks for both."""
    return sorted({expected(p, s) for p, s in probes if reaches_prefix_check(p, s)})


# The runner's interface (examples/tools/targets/runtime.py's docstring, "the oracle convention"): what
# runtime.run_controls passes the driver, and how workflow_ingest reads one revision's lines. An exception is a replay
# that can't be judged, never a violation.

def _checked_probes():
    probes = load_probes()
    if coverage(probes) != [False, True]:
        raise ValueError("the probes don't reach the changed prefix check with both a true and a false case")
    return probes


def driver_args():
    """The driver's whole argument vector: a pattern and a string per probe."""
    return argv(_checked_probes())


def problems(lines):
    """[((pattern, string), problem)] where one revision's lines disagree with the statement."""
    return check(lines, _checked_probes())


def main(args):
    probes = load_probes()
    if coverage(probes) != [False, True]:
        raise SystemExit("the probes don't reach the changed prefix check with both a true and a false case")
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

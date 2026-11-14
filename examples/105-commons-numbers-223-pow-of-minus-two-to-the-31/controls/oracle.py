"""105's independent oracle: written from the Javadoc of ArithmeticUtils.pow(int k, int e), which is the same text at
both revisions, and from integer arithmetic, not from either revision's code. It never calls the method.

What it states, on the probes of replay/probes.json:

1. e < 0 is an IllegalArgumentException, whatever k ("@throws IllegalArgumentException if e < 0").
2. Otherwise the mathematical k^e, computed exactly with Python's unbounded integers (0^0 = 1, as the Javadoc's special
   cases say), is returned when it is an int, -2^31 <= k^e <= 2^31 - 1 ("@return k^e").
3. Otherwise it is an ArithmeticException ("@throws ArithmeticException if the result would overflow").
4. A revision may deviate from 1-3 only where replay/probes.json's contract_deviations says so, with the outcome it
   gives there. Those come from the upstream record of the change (NUMBERS-218, pull request #223), never from the
   code: the before revision reports overflow for (-2)^31, which is Integer.MIN_VALUE; the after revision deviates
   nowhere.

Exceptions are observed by class only: the driver records the class, never the message.

The selected obligation's concrete side (claims/pow-minus-two.json): for k == -2 and 0 <= e <= 31, the result is
(-2)^e. Every point of that domain must be a probe; the oracle reports, per revision, the points where it fails, and
expects them to be exactly the revision's deviations inside the domain (none at after; e = 31 at before, the witness
the refuted attempt on before is expected to give, here replayed in the JVM). Between the two revisions, the probes
whose outcomes differ must be exactly those where one revision deviates and the other doesn't.

    python3 -I oracle.py argv                                 the driver's argument vector, one argument per line
    python3 -I oracle.py table                                each probe and the contract's outcome
    python3 -I oracle.py check REVISION FILE [REVISION FILE]  each FILE one revision's driver stdout (REVISION is
                                                              before or after); with both, the pair is compared too;
                                                              exit 1 if anything disagrees
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBES = HERE.parent / "replay" / "probes.json"
INT_MIN, INT_MAX = -(2 ** 31), 2 ** 31 - 1
IAE, AE = "java.lang.IllegalArgumentException", "java.lang.ArithmeticException"


def power(k, e):
    """k^e exactly, for e >= 0; None when |k^e| > 2^63, which is an overflow without computing a huge number."""
    if k in (0, 1):
        return 1 if (k == 1 or e == 0) else 0
    if k == -1:
        return 1 if e % 2 == 0 else -1
    if e > 64:  # |k| >= 2, so |k^e| >= 2^65
        return None
    return k ** e


def contract(k, e):
    """The Javadoc's outcome: ("returned", value) or ("threw", exception class)."""
    if e < 0:
        return ("threw", IAE)
    value = power(k, e)
    if value is not None and INT_MIN <= value <= INT_MAX:
        return ("returned", value)
    return ("threw", AE)


def load(path=PROBES):
    data = json.loads(path.read_text(encoding="utf-8"))
    probes = [tuple(p) for p in data["probes"]]
    for k, e in probes:
        if not (INT_MIN <= k <= INT_MAX and INT_MIN <= e <= INT_MAX):
            raise SystemExit(f"not an int probe: {(k, e)}")
    if len(set(probes)) != len(probes):
        raise SystemExit("a probe is listed twice")
    deviations = {}
    for revision in ("before", "after"):
        deviations[revision] = {}
        for d in data["contract_deviations"][revision]:
            outcome = ("threw", d["exception"]) if d["outcome"] == "threw" else ("returned", d["value"])
            deviations[revision][(d["k"], d["e"])] = outcome
    prop = data["property"]
    domain = [(prop["k"], e) for e in range(prop["eFrom"], prop["eTo"] + 1)]
    return probes, deviations, domain


def expected(probe, revision, deviations):
    return deviations[revision].get(probe, contract(*probe))


def coverage(probes, deviations, domain):
    """What the probes must reach, by name; the missing ones."""
    outcomes = [contract(*p) for p in probes]
    wanted = {
        "every point of the property's domain": all(p in probes for p in domain),
        "the first overflow past the domain, (-2)^32": (-2, 32) in probes,
        "every declared deviation": all(p in probes for r in deviations.values() for p in r),
        "Integer.MIN_VALUE returned": ("returned", INT_MIN) in outcomes,
        "Integer.MAX_VALUE returned": ("returned", INT_MAX) in outcomes,
        "an IllegalArgumentException": ("threw", IAE) in outcomes,
        "an ArithmeticException": ("threw", AE) in outcomes,
        "e < 0 with k in {0, 1, -1}": all(any(k == kk and e < 0 for k, e in probes) for kk in (0, 1, -1)),
        "e == Integer.MAX_VALUE with k in {0, 1, -1, -2}": all((kk, INT_MAX) in probes for kk in (0, 1, -1, -2)),
        "e == Integer.MIN_VALUE": any(e == INT_MIN for _, e in probes),
    }
    return [name for name, ok in wanted.items() if not ok]


def argv(probes):
    return [str(x) for p in probes for x in p]


def read(lines, probes):
    """{probe: (outcome, value or exception)} from one revision's driver lines; refuses a missing or unknown probe."""
    seen = {}
    for line in lines:
        if not line.strip():
            continue
        record = json.loads(line)
        probe = (record["k"], record["e"])
        if probe not in probes or probe in seen:
            raise SystemExit(f"an unexpected or repeated line: {line}")
        if record["outcome"] == "returned":
            seen[probe] = ("returned", record["value"])
        elif record["outcome"] == "threw":
            seen[probe] = ("threw", record["exception"])
        else:
            raise SystemExit(f"an outcome that is neither returned nor threw: {line}")
    missing = [p for p in probes if p not in seen]
    if missing:
        raise SystemExit(f"the replay is incomplete, never a result: no line for {missing}")
    return seen


def check(seen, revision, probes, deviations, domain):
    """[(probe, problem)] for each observation of one revision the statement disagrees with, and the property's
    failing points."""
    problems = []
    for probe in probes:
        want = expected(probe, revision, deviations)
        if seen[probe] != want:
            problems.append((list(probe), f"{seen[probe][0]} {seen[probe][1]}, the statement says {want[0]} {want[1]}"))
    fails = [p for p in domain if seen[p] != ("returned", power(*p))]
    want_fails = [p for p in domain if p in deviations[revision]]
    if fails != want_fails:
        problems.append(([list(p) for p in fails], f"the property fails at these points, expected at {[list(p) for p in want_fails]}"))
    return problems, fails


def compare(before, after, probes, deviations):
    """The probes whose outcomes differ between the revisions, and whether they are the expected ones."""
    differ = [p for p in probes if before[p] != after[p]]
    want = [p for p in probes if expected(p, "before", deviations) != expected(p, "after", deviations)]
    return differ, want


def table(probes, deviations):
    for p in probes:
        line = {"k": p[0], "e": p[1], "contract": contract(*p)}
        for r in ("before", "after"):
            if p in deviations[r]:
                line[r] = deviations[r][p]
        print(json.dumps(line))


def main(args):
    probes, deviations, domain = load()
    missing = coverage(probes, deviations, domain)
    if missing:
        raise SystemExit(f"the probes don't reach: {', '.join(missing)}")
    if args[:1] == ["argv"]:
        print("\n".join(argv(probes)))
        return 0
    if args[:1] == ["table"]:
        table(probes, deviations)
        return 0
    rest = args[1:]
    if args[:1] == ["check"] and rest and len(rest) % 2 == 0 and len(rest) <= 4:
        failed, seen = False, {}
        for revision, name in zip(rest[::2], rest[1::2]):
            if revision not in ("before", "after") or revision in seen:
                raise SystemExit(__doc__)
            seen[revision] = read(Path(name).read_text(encoding="utf-8").splitlines(), probes)
            problems, fails = check(seen[revision], revision, probes, deviations, domain)
            failed = failed or bool(problems)
            print(json.dumps({"revision": revision, "file": name, "probes": len(probes), "problems": problems,
                              "propertyFailsAt": [list(p) for p in fails]}))
        if len(seen) == 2:
            differ, want = compare(seen["before"], seen["after"], probes, deviations)
            failed = failed or differ != want
            print(json.dumps({"pair": ["before", "after"], "differences": [list(p) for p in differ],
                              "expected": [list(p) for p in want]}))
        return 1 if failed else 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

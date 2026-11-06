#!/usr/bin/env python3
"""The gaps each recorded proof reaches, and what strict mode would make of it: a table over examples' result.json
files (result format 2), per obligation (a B11 example's properties are one each).

  python3 examples/tools/gap_table.py [--examples DIR] [--checker jbmc|native] [--json OUT] [ID ...]
  python3 examples/tools/gap_table.py --compare A.json B.json

DIR is the examples folder to read: a run's, such as a pipeline job's copy of `examples/`, whose results are format 2
with their gaps recorded. A result without them (the flat results the repository records predate gap records) is
counted as skipped. An obligation
counts as one strict would refuse when it is established and reaches a gap the checker approximates; a refuted one
stands under strict when its witness replays, so it is listed but not counted. Step 4c of
llm-dlc/loops/sound-verdicts.md; job 20261106-082917's inline script did this on format 1 and failed on format 2.

Each row also names the engine and checker that ran it, the example's `expectation` (whether its verdict is the one
the example expects: a difference is reported, the recorded verdict stands), and, for an obligation with no verdict,
the run's `problem`, which names a gap refused or a construct JBMC runs otherwise than the JVM (`jbmcDefect`, step 3
of llm-dlc/loops/engine-priorities.md). `--compare` lists the obligations whose status differs between two such
tables, such as one engine's and the other's on the same examples (step 4a).
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def find(value, key):
    """Every value under `key`, at any depth."""
    if isinstance(value, dict):
        for k, v in value.items():
            if k == key:
                yield v
            yield from find(v, key)
    elif isinstance(value, list):
        for v in value:
            yield from find(v, key)


def obligations(result):
    """(index, status, evidence) for each obligation of a result: its properties', or the result's own."""
    conclusion = result.get("conclusion") or {}
    listed = conclusion.get("obligations") or []
    if listed:
        return [(i, o.get("status"), o.get("evidence") or {}) for i, o in enumerate(listed)]
    return [(0, conclusion.get("status"), result.get("evidence") or {})]


# How jvmcontract's problem begins for a JBMC proof refused at a construct JBMC runs otherwise than the JVM
# (lib/src/jbmc_gaps.rs, `hold`): such a construct is no gap, so the problem is all a result records of it.
DEFECT_PROBLEM = "otherwise than the JVM"


def table(folder, checker=None, ids=None, skipped=None):
    """A row per obligation of each example with a result.json: its status, gap modes, the gaps it reaches (of
    `checker` when given, by id without the JDK suffix) and whether strict would refuse it; the engine and checker
    of its search, the example's expectation, and an unresolved obligation's problem."""
    rows = []
    for path in sorted(Path(folder).glob("*/result.json")):
        example = path.parent.name.split("-", 1)[0]
        if ids and example not in ids:
            continue
        result = json.loads(path.read_text())
        if result.get("format") != 2:
            if skipped is not None:
                skipped.append(example)
            continue
        expectation = (result.get("conclusion") or {}).get("expectation")
        for index, status, evidence in obligations(result):
            gaps = {}
            for listed in find(evidence, "gaps"):
                for g in listed if isinstance(listed, list) else []:
                    if isinstance(g, dict) and "id" in g and (checker is None or (g.get("checker") or "native") == checker):
                        gaps.setdefault(g["id"].split("@")[0], g.get("kind"))
            search = evidence.get("search") or {}
            modes = sorted({m for m in find(search, "gapMode") if m})
            problem = evidence.get("problem") if status not in ("established", "refuted") else None
            rows.append({"example": example, "obligation": index, "status": status, "gapModes": modes,
                         "gaps": sorted(gaps), "strictWouldRefuse": status == "established" and bool(gaps),
                         "engine": search.get("engine"), "checker": search.get("checker"), "expectation": expectation,
                         "problem": problem or None, "jbmcDefect": DEFECT_PROBLEM in (problem or "")})
    return rows


def compare(a, b):
    """The obligations whose status differs between two tables (rows as table() gives them, keyed by example and
    obligation), and those only one of them has: (key, row of a or None, row of b or None)."""
    left = {(r["example"], r["obligation"]): r for r in a}
    right = {(r["example"], r["obligation"]): r for r in b}
    return [(k, left.get(k), right.get(k)) for k in sorted(left.keys() | right.keys())
            if (left.get(k) or {}).get("status") != (right.get(k) or {}).get("status") or k not in left or k not in right]


def describe(row):
    if row is None:
        return "(no row)"
    why = f": {row['problem']}" if row.get("problem") else ""
    return f"{row['status']} on {row.get('engine')}{why}"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--compare", nargs=2, metavar=("A.json", "B.json"), help="list the obligations whose status differs")
    p.add_argument("--examples", default=str(REPO / "examples"))
    p.add_argument("--checker", choices=["jbmc", "native"], help="only this checker's gaps")
    p.add_argument("--json", help="write the rows here")
    p.add_argument("ids", nargs="*")
    args = p.parse_args(argv)
    if args.compare:
        a, b = (json.loads(Path(f).read_text()) for f in args.compare)
        differ = compare(a, b)
        for (example, index), x, y in differ:
            print(f"{example}#{index}: {describe(x)} | {describe(y)}")
        print(f"{len(differ)} of {len({(r['example'], r['obligation']) for r in a + b})} obligations differ in status "
              f"between {args.compare[0]} and {args.compare[1]}")
        return 0
    skipped = []
    rows = table(args.examples, args.checker, set(args.ids) or None, skipped)
    for r in rows:
        if r["gaps"]:
            note = " (strict: no verdict)" if r["strictWouldRefuse"] else ""
            print(f"{r['example']}#{r['obligation']} {r['status']}{note}: {', '.join(r['gaps'])}")
        elif r["jbmcDefect"]:
            print(f"{r['example']}#{r['obligation']} {r['status']} (a JBMC defect): {r['problem']}")
    unexpected = sorted({r["example"] for r in rows if r["expectation"] == "no"})
    defects = [f"{r['example']}#{r['obligation']}" for r in rows if r["jbmcDefect"]]
    # Under strict a proof at a gap is already refused: no verdict, with the gap named.
    held = [f"{r['example']}#{r['obligation']}" for r in rows if r["gaps"] and r["status"] == "unresolved"]
    examples = {r["example"] for r in rows}
    reaching = {r["example"] for r in rows if r["gaps"]}
    refused = [f"{r['example']}#{r['obligation']}" for r in rows if r["strictWouldRefuse"]]
    print(f"{len(examples)} examples, {len(rows)} obligations; {len(reaching)} examples reach a gap; "
          f"strict would refuse {len(refused)} obligation(s){': ' + ', '.join(refused) if refused else ''}"
          + (f"; {len(held)} with no verdict at a gap: {', '.join(held)}" if held else "")
          + (f"; {len(defects)} refused at a JBMC defect: {', '.join(defects)}" if defects else "")
          + (f"; {len(skipped)} result(s) skipped, not format 2 (no gaps recorded)" if skipped else ""))
    print(f"{len(unexpected)} example(s) differ from their expected verdict{': ' + ', '.join(unexpected) if unexpected else ''}")
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

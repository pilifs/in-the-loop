#!/usr/bin/env python3
"""The gaps each recorded proof reaches, and what strict mode would make of it: a table over examples' result.json
files (result format 2), per obligation (a B11 example's properties are one each).

  python3 examples/tools/gap_table.py [--examples DIR] [--checker jbmc|native] [--json OUT] [ID ...]

DIR is the examples folder to read: a run's, such as a pipeline job's copy of `examples/`, whose results are format 2
with their gaps recorded. A result without them (the flat results the repository records predate gap records) is
counted as skipped. An obligation
counts as one strict would refuse when it is established and reaches a gap the checker approximates; a refuted one
stands under strict when its witness replays, so it is listed but not counted. Step 4c of
llm-dlc/loops/sound-verdicts.md; job 20261106-082917's inline script did this on format 1 and failed on format 2.
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


def table(folder, checker=None, ids=None, skipped=None):
    """A row per obligation of each example with a result.json: its status, gap modes, the gaps it reaches (of
    `checker` when given, by id without the JDK suffix) and whether strict would refuse it."""
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
        for index, status, evidence in obligations(result):
            gaps = {}
            for listed in find(evidence, "gaps"):
                for g in listed if isinstance(listed, list) else []:
                    if isinstance(g, dict) and "id" in g and (checker is None or (g.get("checker") or "native") == checker):
                        gaps.setdefault(g["id"].split("@")[0], g.get("kind"))
            modes = sorted({m for m in find(evidence.get("search") or {}, "gapMode") if m})
            rows.append({"example": example, "obligation": index, "status": status, "gapModes": modes,
                         "gaps": sorted(gaps), "strictWouldRefuse": status == "established" and bool(gaps)})
    return rows


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--examples", default=str(REPO / "examples"))
    p.add_argument("--checker", choices=["jbmc", "native"], help="only this checker's gaps")
    p.add_argument("--json", help="write the rows here")
    p.add_argument("ids", nargs="*")
    args = p.parse_args(argv)
    skipped = []
    rows = table(args.examples, args.checker, set(args.ids) or None, skipped)
    for r in rows:
        if r["gaps"]:
            note = " (strict: no verdict)" if r["strictWouldRefuse"] else ""
            print(f"{r['example']}#{r['obligation']} {r['status']}{note}: {', '.join(r['gaps'])}")
    examples = {r["example"] for r in rows}
    reaching = {r["example"] for r in rows if r["gaps"]}
    refused = [f"{r['example']}#{r['obligation']}" for r in rows if r["strictWouldRefuse"]]
    print(f"{len(examples)} examples, {len(rows)} obligations; {len(reaching)} examples reach a gap; "
          f"strict would refuse {len(refused)} obligation(s){': ' + ', '.join(refused) if refused else ''}"
          + (f"; {len(skipped)} result(s) skipped, not format 2 (no gaps recorded)" if skipped else ""))
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

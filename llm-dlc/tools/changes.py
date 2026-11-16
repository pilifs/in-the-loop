#!/usr/bin/env python3
"""The changes a checkout holds as examples for /prove-java-change, and where each stands
(llm-dlc/runtime.md#many-changes-and-preparing-without-proving).

    changes.py [NNN ...]             a table, and the numbers still to prove
    changes.py --json [NNN ...]      the same as data
    changes.py --pending [NNN ...]   only the numbers still to prove, on one line, in order: prove-loop.sh's arguments

Without numbers it lists a runtime checkout's own examples, 900 to 999, in the order of their numbers, which is the
order their preparation decided to prove them in. With numbers it lists those, in the order given.

A row carries the example's `source` (the change on GitHub), its `revisions` (the commits its sidecar pins) and its
`provenance`, which for an example the skill prepared is the request it was prepared from: together they say
whether a change asked for again already has its example.

Each example is in one of four states, derived from its folder alone (its sidecar, its claims and its receipts, by
examples/tools/targets/workflow.py), so nothing has to be kept in step by hand:

    unprepared   its scaffold is incomplete: a revision that does not materialize, no oracle run, a claim not
                 frozen, or no proof task at all. `why` says which. Not ready for a proof loop.
    prepared     the scaffold is complete and at least one claim has no answer yet (none, or left open). This is
                 where `/prove-java-change --scaffold-only` leaves an example, and what a proof loop takes.
    decided      every claim is established or refuted by a current receipt. A proof loop has nothing to do.
    unknown      no target sidecar (a constructed example): its state is not derived, and it counts as still to
                 prove when it is named.

It only reads. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOLS = str(REPO / "examples" / "tools")  # targets/sidecar.py and targets/workflow.py: the code, whatever the root
LOCAL_NUMBERS = range(900, 1000)  # a runtime checkout's own examples (llm-dlc/runtime.md)
ANSWERS = ("established", "refuted")
TO_PROVE = ("prepared", "unknown")


def folders(root: Path, numbers: list[str]) -> list[tuple[str, Path | None]]:
    """(number, folder) for each example asked for; the folder is None when there is none."""
    examples = root / "examples"
    if numbers:
        return [(n, next(iter(sorted(examples.glob(f"{n}-*/example.json"))), None)) for n in numbers]
    found = sorted(p for p in examples.glob("9[0-9][0-9]-*/example.json"))
    return [(p.parent.name[:3], p) for p in found]


def row(root: Path, number: str, sidecar_file: Path | None) -> dict:
    """One example's row. A folder that can't be read is unprepared, with the reason: the list never fails on one."""
    if sidecar_file is None:
        return {"id": number, "state": "unprepared", "why": [f"there is no example {number}"]}
    folder = sidecar_file.parent
    r: dict = {"id": number, "path": str(folder.relative_to(root))}
    try:
        example = json.loads(sidecar_file.read_text())
    except (OSError, json.JSONDecodeError) as e:
        return {**r, "state": "unprepared", "why": [f"example.json can't be read: {e}"]}
    source = example.get("source") or {}
    r.update(title=example.get("title"), source=source.get("url"), repository=source.get("repository"),
             provenance=example.get("provenance"))
    sys.path.insert(0, TOOLS)
    try:
        from targets import sidecar, workflow
        target = sidecar.load(folder, example)
        if target is None:
            return {**r, "state": "unknown", "why": ["no target sidecar: its state is not derived"]}
        projected = workflow.project(folder, example, target)
        ready = workflow.readiness(folder, example, target)
    except Exception as e:  # a sidecar refused, a claim that does not load: the reason is the finding
        return {**r, "state": "unprepared", "why": [f"{type(e).__name__}: {e}"]}
    finally:
        sys.path.remove(TOOLS)
    revisions = (target.get("history") or {}).get("revisions") or {}
    r["revisions"] = {name: v["commit"] for name, v in revisions.items() if isinstance(v, dict) and v.get("commit")}
    r["readiness"] = ready["summary"]
    r["claims"] = {task: {"status": status, "expected": projected["expected"].get(task)}
                   for task, status in projected["claims"].items()}
    why = []
    for task, t in ready["tasks"].items():
        if t["summary"] in ("partial", "catalogued"):
            missing = [f"{name}: {m['evidence']}" for name, m in t["milestones"].items()
                       if name in workflow.SCAFFOLD and m["reached"] is False]
            observed = [b["summary"] for b in t["blockers"] if b.get("observed") and b["kind"] not in workflow.CAPABILITY_KINDS]
            why += [f"task {task}: {x}" for x in missing + observed] or [f"task {task}: {t['summary']}"]
    if not r["claims"]:
        why.append("no proof task: nothing here states a claim")
    if why:
        return {**r, "state": "unprepared", "why": why}
    decided = all(c["status"] in ANSWERS for c in r["claims"].values())
    return {**r, "state": "decided" if decided else "prepared"}


def listing(root: Path, numbers: list[str]) -> dict:
    rows = [row(root, n, f) for n, f in folders(root, numbers)]
    return {"examples": rows,
            "pending": [r["id"] for r in rows if r["state"] in TO_PROVE],
            "unprepared": [r["id"] for r in rows if r["state"] == "unprepared"]}


def claims_line(r: dict) -> str:
    claims = r.get("claims") or {}
    if not claims:
        return "; ".join(r.get("why", []))[:120]
    counts: dict[str, int] = {}
    for c in claims.values():
        name = c["status"] if c["status"] in ANSWERS else ("left open" if c["status"] else "no answer yet")
        counts[name] = counts.get(name, 0) + 1
    text = ", ".join(f"{n} {name}" for name, n in counts.items())
    return text if r["state"] != "unprepared" else f"{text}; {'; '.join(r['why'])}"[:160]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("examples", nargs="*", metavar="NNN", help="by default every example numbered 900 to 999")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--pending", action="store_true", help="only the numbers still to prove, on one line")
    ap.add_argument("--root", type=Path, default=REPO, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    bad = [n for n in args.examples if not (len(n) == 3 and n.isdigit())]
    if bad:
        ap.error(f"not an example's number: {' '.join(bad)}")
    found = listing(args.root.resolve(), args.examples)
    if args.pending:
        print(" ".join(found["pending"]))
    elif args.json:
        print(json.dumps(found, indent=1))
    elif not found["examples"]:
        print(f"no example numbered {LOCAL_NUMBERS.start} to {LOCAL_NUMBERS.stop - 1} in this checkout")
    else:
        for r in found["examples"]:
            print(f"{r['id']}  {r['state']:<10}  {claims_line(r)}")
            for label in ("title", "source", "provenance"):
                if r.get(label):
                    print(f"     {label}: {r[label]}")
        print("to prove, in order: " + (" ".join(found["pending"]) or "nothing"))
        if found["unprepared"]:
            print("not prepared: " + " ".join(found["unprepared"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

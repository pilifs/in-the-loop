#!/usr/bin/env python3
"""The changes a checkout holds as examples for /prove-java-change, and where each stands
(llm-dlc/runtime.md#many-changes-and-preparing-without-proving).

    changes.py [NNN ...]             a table, and the numbers still to prove
    changes.py --json [NNN ...]      the same as data
    changes.py --pending [NNN ...]   only the numbers still to prove, on one line, in order

Without numbers it lists a runtime checkout's own examples, 900 to 999, in the order of their numbers, which is the
order their preparation decided to prove them in. With numbers it lists those, in the order given.

A row carries the example's `source` (the change on GitHub), its `revisions` (the commits its sidecar pins) and its
`provenance`, which for an example the skill prepared is the request it was prepared from: together they say
whether a change asked for again already has its example.

Each example is in one of five states, derived from its folder alone (its sidecar, its claims and its receipts, by
examples/tools/targets/workflow.py) and from the verification results a sidecar cites, so nothing has to be kept in
step by hand:

    catalogued   a catalog entry: its revisions are pinned, and its sidecar has no task, so nothing is built and
                 nothing states a claim. Setting it up is stage 3's work (llm-dlc/runtime.md), not a repair.
    unprepared   its scaffold is incomplete: a revision that does not materialize, no oracle run, a claim not
                 frozen, or tasks and no proof task among them. `why` says which. Not ready for a proof loop.
    prepared     the scaffold is complete and at least one claim has no answer yet (none, or left open). This is
                 where `/prove-java-change --scaffold-only` leaves an example, and what a proof loop takes.
    decided      every claim is established or refuted. A proof loop has nothing to do.
    unknown      no target sidecar (a constructed example): its state is not derived, and it counts as still to
                 prove when it is named.

A claim's answer is the route's (build.py's), from a current receipt, or one given beside the route: by a script of
the example's own (286 and 287 have one, proofs/prove.py), run as a verification job, which leaves no receipt. The
sidecar records such an answer on its task (`besideRoute`: the answer, the job, how it was run), and it counts here
only while the acceptance check accepts it (examples/tools/accept.py: the job's result is in this checkout and
passed, the outcome its step wrote gives that very answer, about the claim as frozen, at its bound, on the entry the
task names, a refutation reproduced on a JVM, an establishment complete and not vacuous); otherwise the claim stays
open and `beside.why` says which check refuses it. A claim still open also carries `blocked`, the kinds of the observed
verifier gaps its task stops at, and each row the example's own words on its outcome, `verdict` (its verdictLabel)
and `next` (its hand-off): whether a loop has anything left to do on an example with open claims is a judgment, and
those are what it is made from.

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
# What an unprepared example lacks, by kind, for whoever checks one before a run takes it
# (examples/tools/preflight.py): an artifact that is not there (a revision that does not materialize, no oracle run, no lock), the
# example's form (a file that does not load or validate, a claim not frozen, no proof task), or the example itself.
ARTIFACTS, FORM, ABSENT, CATALOGUE = "artifacts", "form", "absent", "catalogue"
FORM_MILESTONES = ("claimFrozen",)
KINDS = (ARTIFACTS, FORM, ABSENT, CATALOGUE)


TO_PROVE = ("prepared", "unknown")


def gap(kind: str, what: str, task: str | None = None) -> dict:
    return {"kind": kind, "task": task, "what": what}


def beside(root: Path, number: str, task: str, record: dict, source=None) -> dict:
    """A task's `besideRoute` record with whether it counts: whether the acceptance check (examples/tools/accept.py)
    derives the same answer from what the job left. The record is the sidecar's word; that a job passed and names
    the example says only that a script exited 0, and would support either answer. `why` is the first check that
    refuses it, `actual` what the evidence gives, `limits` what an accepted answer rests on that no record shows."""
    sys.path.insert(0, TOOLS)
    try:
        import accept
        checked = accept.check(root, number, task, source)
    finally:
        sys.path.remove(TOOLS)
    out = {"answer": record.get("answer"), "job": record.get("job"), "by": record.get("by"), "confirmed": checked["accepted"]}
    if not checked["accepted"]:
        return {**out, "actual": checked.get("actual"), "why": checked.get("why") or f"the evidence gives {checked.get('actual')}"}
    return {**out, "limits": checked["limits"], "restsOn": checked.get("restsOn", [])}


def answer(claim: dict) -> str | None:
    """A claim's answer: the route's when it has one, else one given beside the route that its job confirms."""
    if claim["status"] in ANSWERS:
        return claim["status"]
    b = claim.get("beside") or {}
    return b["answer"] if b.get("confirmed") and b.get("answer") in ANSWERS else None


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
        return {"id": number, "state": "unprepared", "why": [f"there is no example {number}"],
                "gaps": [gap(ABSENT, f"there is no example {number}")]}
    folder = sidecar_file.parent
    r: dict = {"id": number, "path": str(folder.relative_to(root))}
    try:
        example = json.loads(sidecar_file.read_text())
    except (OSError, json.JSONDecodeError) as e:
        return {**r, "state": "unprepared", "why": [f"example.json can't be read: {e}"],
                "gaps": [gap(FORM, f"example.json can't be read: {e}")]}
    source = example.get("source") or {}
    r.update(title=example.get("title"), source=source.get("url"), repository=source.get("repository"),
             provenance=example.get("provenance"), verdict=example.get("verdictLabel"))
    sys.path.insert(0, TOOLS)
    try:
        from targets import sidecar, workflow
        target = sidecar.load(folder, example)
        if target is None:
            if example.get("publicComparison") and (folder/"records/public-observer/generation.json").is_file():
                from targets import observer_review
                answers = observer_review.finite_answers(folder)
                return {**r, "state": "decided" if all(a in ANSWERS for a in answers.values()) else "prepared",
                        "readiness": "frozen finite public observations",
                        "claims": {name: {"status": a, "kind": "finite public observation"} for name,a in answers.items()}}
            return {**r, "state": "unknown", "why": ["no target sidecar: its state is not derived"]}
        projected = workflow.project(folder, example, target)
        ready = workflow.readiness(folder, example, target)
    except Exception as e:  # a sidecar refused, a claim that does not load: the reason is the finding
        return {**r, "state": "unprepared", "why": [f"{type(e).__name__}: {e}"],
                "gaps": [gap(FORM, f"{type(e).__name__}: {e}")]}
    finally:
        sys.path.remove(TOOLS)
    r["next"] = (target.get("handoff") or {}).get("next")
    capability = workflow.CAPABILITY_KINDS
    revisions = (target.get("history") or {}).get("revisions") or {}
    r["revisions"] = {name: v["commit"] for name, v in revisions.items() if isinstance(v, dict) and v.get("commit")}
    r["readiness"] = ready["summary"]
    r["claims"] = {task: {"status": status, "expected": projected["expected"].get(task)}
                   for task, status in projected["claims"].items()}
    for t in target.get("tasks") or []:
        if t.get("besideRoute") and t["id"] in r["claims"]:
            r["claims"][t["id"]]["beside"] = beside(root, number, t["id"], t["besideRoute"])
    for task, c in r["claims"].items():
        stops = sorted({b["kind"] for b in ready["tasks"].get(task, {}).get("blockers", [])
                        if b.get("observed") and b["kind"] in capability})
        if stops and answer(c) is None:
            c["blocked"] = stops
    if not target.get("tasks"):
        what = "a catalog entry: its sidecar has no task, so nothing is built and nothing states a claim"
        return {**r, "state": "catalogued", "why": [what], "gaps": [gap(CATALOGUE, what)]}
    why, gaps = [], []
    for task, t in ready["tasks"].items():
        if t["summary"] in ("partial", "catalogued"):
            unreached = {name: m["evidence"] for name, m in t["milestones"].items()
                         if name in workflow.SCAFFOLD and m["reached"] is False}
            missing = [f"{name}: {evidence}" for name, evidence in unreached.items()]
            observed = [b["summary"] for b in t["blockers"] if b.get("observed") and b["kind"] not in workflow.CAPABILITY_KINDS]
            why += [f"task {task}: {x}" for x in missing + observed] or [f"task {task}: {t['summary']}"]
            gaps += [gap(FORM if name in FORM_MILESTONES else ARTIFACTS, f"{name}: {evidence}", task)
                     for name, evidence in unreached.items()]
            gaps += [gap(ARTIFACTS, x, task) for x in observed]
            if not unreached and not observed:
                gaps.append(gap(ARTIFACTS, t["summary"], task))
    if not r["claims"]:
        why.append("no proof task: nothing here states a claim")
        gaps.append(gap(FORM, "no proof task: nothing here states a claim"))
    if why:
        return {**r, "state": "unprepared", "why": why, "gaps": gaps}
    decided = all(answer(c) for c in r["claims"].values())
    return {**r, "state": "decided" if decided else "prepared"}


def listing(root: Path, numbers: list[str]) -> dict:
    rows = [row(root, n, f) for n, f in folders(root, numbers)]
    return {"examples": rows,
            "pending": [r["id"] for r in rows if r["state"] in TO_PROVE],
            "unprepared": [r["id"] for r in rows if r["state"] == "unprepared"],
            "catalogued": [r["id"] for r in rows if r["state"] == "catalogued"]}


def claims_line(r: dict) -> str:
    claims = r.get("claims") or {}
    if not claims:
        return "; ".join(r.get("why", []))[:120]
    counts: dict[str, int] = {}
    for c in claims.values():
        if c["status"] in ANSWERS:
            name = c["status"]
        elif answer(c):
            name = f"{answer(c)} beside the route"
        else:
            name = ("left open" if c["status"] else "no answer yet") + (", at an observed gap" if c.get("blocked") else "")
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
            for task, claim in r.get("claims", {}).items():
                evidence = claim.get("beside") or {}
                if evidence.get("confirmed"):
                    for assumption in evidence["restsOn"]:
                        print(f"     {task} assumes {assumption}")
                    for limit in evidence["limits"]:
                        print(f"     {task} evidence limit — {limit}")
            for label in ("title", "source", "provenance", "verdict"):
                if r.get(label):
                    print(f"     {label}: {r[label]}")
        print("to prove, in order: " + (" ".join(found["pending"]) or "nothing"))
        if found["unprepared"]:
            print("not prepared: " + " ".join(found["unprepared"]))
        if found["catalogued"]:
            print("catalog entries, to set up first: " + " ".join(found["catalogued"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

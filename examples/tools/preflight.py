#!/usr/bin/env python3
"""What each example named lacks before a run takes it: its form, its artifacts, and how its proofs are invoked.

    preflight.py [--root DIR] [--after-setup NNN,...] NNN ...

It prints, as JSON, each example with what it lacks, and the lists to act on:

    absent      an example that is not there at all: nothing can put that right
    toSetUp     catalog entries, whose revisions are pinned and which state no claim yet
    toRepair    prepared examples that lack artifacts, or have a fault in their form
    toClassify  examples with a proof task that does not record how its proof is invoked (route, adapter or gap)
    leftOut     entries named by --after-setup that still lack something once a setup has been run for them: the
                others go on without them
    toProve     the examples that lack nothing and still have a claim to decide, in the order given
    decided     the ones with nothing left to decide

Exit 0: nothing is lacking; 1: something a setup may put right; 2: an example that is not there.

An example's state is derived from its own folder (llm-dlc/tools/changes.py). This adds two checks on top:
example.json against its schema, which build.py checks only when it builds the example's page, and the record of
how each proof task is invoked. `validate_example.py` uses the first for its check of an example's form.

Until 2026-11-27 this was `watch.py preflight`, a command of the proof run's watcher, which is retired
(llm-dlc/retired.md). That command also said which examples' claims a person had already reviewed; the review
went with the proof run, and nothing here reports it.

Standard library only, and jsonschema when it is installed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "llm-dlc" / "tools"))
import changes  # noqa: E402  llm-dlc/tools/changes.py

INVOKED = ("route", "adapter", "gap")  # how a proof task's proof is invoked, as its sidecar records it


def schema_gaps(root: Path, row: dict) -> list[dict]:
    """example.json against its schema, which build.py checks only when it builds the example's page."""
    try:
        import jsonschema
        schema = json.loads((root / "examples/schema/example.schema.json").read_text())
        example = json.loads((root / row["path"] / "example.json").read_text())
    except (ImportError, OSError, ValueError, KeyError):
        return []  # nothing to check with, or a file changes.py has reported already
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(example), key=lambda e: list(e.absolute_path))
    return [changes.gap(changes.FORM, f"example.json, {'/'.join(map(str, e.absolute_path)) or 'the document'}: {e.message}"[:300])
            for e in errors[:5]]


def uninvoked(root: Path, row: dict) -> list[dict]:
    """The proof tasks of a set-up example whose sidecar doesn't say how the proof is invoked (`invocation`): through
    the route, through a validated adapter, or not until a named gap of the verifier is closed, which an observed
    blocker of the task records. It is the setup's deliverable; one missing doesn't stop a run."""
    try:
        target = json.loads((root / row["path"] / "target.json").read_text())
    except (OSError, ValueError, KeyError, TypeError):
        return []
    observed = {b.get("task") for b in (target.get("handoff") or {}).get("blockers") or [] if b.get("observed")}
    out = []
    for t in target.get("tasks") or []:
        if t.get("kind") == "replay":
            continue
        how = (t.get("invocation") or {}).get("how")
        if how not in INVOKED:
            out.append({"task": t["id"], "what": "how its proof is invoked is not recorded (route, adapter or gap)"})
        elif how == "gap" and t["id"] not in observed and None not in observed:
            out.append({"task": t["id"], "what": "invoked only once a gap is closed, and no observed blocker names it"})
    return out


def preflight(root: Path, numbers: list[str], set_up: list[str] | tuple = (), review=None) -> dict:
    """What each example named lacks. `set_up` names the catalog entries a setup has been run for: one that still
    lacks something is left out, and the others go on without it. `review`, when given, is asked for each example's
    row and its answer is kept as the example's `review`: a caller that keeps a record of reviewed claims adds its
    own lists from it."""
    numbers = list(dict.fromkeys(numbers))
    out = []
    for row in changes.listing(root, numbers)["examples"]:
        gaps = list(row.get("gaps") or [])
        if not any(g["kind"] == changes.ABSENT for g in gaps) and row.get("path"):
            gaps += schema_gaps(root, row)
        entry = {"id": row["id"], "path": row.get("path"), "state": row["state"], "ok": not gaps,
                 **{kind: [g for g in gaps if g["kind"] == kind] for kind in changes.KINDS}}
        if row.get("path") and row["state"] not in ("catalogued", "unknown"):
            entry["invocation"] = uninvoked(root, row)
        if row.get("path") and review is not None:
            entry["review"] = review(row)
        if row["state"] == "unknown":
            entry["note"] = "no target sidecar: only its example.json was checked, and its claims are whatever its page states"
        out.append(entry)
    left_out = [e["id"] for e in out if not e["ok"] and e["id"] in set_up and not e[changes.ABSENT]]
    counted = [e for e in out if e["id"] not in left_out]
    return {"examples": out, "ok": all(e["ok"] for e in counted),
            "absent": [e["id"] for e in out if e[changes.ABSENT]],
            "toSetUp": [e["id"] for e in counted if e[changes.CATALOGUE]],
            "toRepair": [e["id"] for e in counted if e[changes.ARTIFACTS] or e[changes.FORM]],
            "leftOut": left_out,
            "toProve": [e["id"] for e in out if e["ok"] and e["state"] != "decided"],
            "decided": [e["id"] for e in out if e["ok"] and e["state"] == "decided"],
            "toClassify": [e["id"] for e in counted if e.get("invocation")]}


def status(found: dict) -> int:
    return 0 if found["ok"] else 2 if found["absent"] else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=REPO, help="the checkout (default: this one)")
    ap.add_argument("--after-setup", default="", metavar="NNN,...", help="catalog entries a setup has been run for")
    ap.add_argument("examples", nargs="+", metavar="NNN")
    args = ap.parse_args(argv)
    found = preflight(args.root.resolve(), args.examples, [n for n in args.after_setup.split(",") if n])
    print(json.dumps(found, indent=1))
    return status(found)


if __name__ == "__main__":
    sys.exit(main())

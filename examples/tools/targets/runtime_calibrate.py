#!/usr/bin/env python3
"""The runtime stream's verifier calibration (R3 of llm-dlc/loops/example-targets-runtime.md): each proof task of
Phase 0's fixture (targets/fixtures/target.json) prepared by runtime.prepare() and checked by runtime.run_verifier()
with the real jvmcontract, native and strict, its raw records handed to workflow.ingest() as route.py hands them.

    python3 examples/tools/targets/runtime_calibrate.py ATTEMPT [--task ID ...] [--fixture-javac-flag=FLAG ...]

It runs proofs, so it runs as a pipeline job (one that requires jvmcontract, which gets $JVMCONTRACT), never inline.
ATTEMPT is a new directory, with one attempt per task laid out as route.py lays one out (prepare/<revision>,
verifier). The fixture is copied to ATTEMPT/fixture and planned from there, so each receipt goes where route.py puts
it, under the example's folder (ATTEMPT/fixture/receipts/<task>), never into the repository's fixture.

Exit 0 when every task's verifier record exited with a readable --json outcome whose verdict is the one the fixture's
task expects (verified for established, violation for refuted, unverifiable or a refusal for unresolved),
and java.util.regex is named in regex-probe's record (its refusal, or its capability probe: each is reported apart);
1 otherwise. ATTEMPT/calibration.json says what happened.

--fixture-javac-flag adds a javac flag to the fixture recipe both preparation and build_fixtures.py would use, and
says so in every preparation's recipe and in calibration.json. The recipe's own JAVAC_FLAGS have been `-parameters`
since the coordinator's Phase 5 (VF-024): without it the verifier calls `code` arg0, and the claims, which say `code`,
aren't well-formed for those bytes. A run with a further flag calibrates a recipe other than the fixture's.

Reading the verdict here is this script's check of R3's plumbing against the fixture's authored expectations, as
contract A5 reads it: no claim is decided here, and ingestion is what judges records in the route. Until the
workflow stream's work is merged, two stand-ins: the plan is built here from the sidecar, and each task's claim is
CLAIMS below, the property workflow's claim files state for these tasks (fixtures/claims/ on its branch, W1's
`wqsyopqlqlno`) in the keys its plan_task gives TaskPlan.claim; ingestion answers Phase 0's Unsupported until W2.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if __name__ == "__main__":
    sys.path.insert(0, str(HERE.parent))
from targets import interfaces, runtime, runtime_slice, workflow  # noqa: E402
from targets.interfaces import Unsupported  # noqa: E402

FOLDER = HERE / "fixtures"
EXAMPLE = "999"
BOUNDS = {"unwind": 16, "maxArrayLength": 8}  # workflow's DEFAULT_BOUNDS: the fixture's tasks state none
# The fixture tasks' properties, as workflow's claim files state them (gate-security.json, gate-preservation.json,
# regex-probe.json): the stand-in for plan_task's claim until the merge.
SECURITY = {"property": "gate-denies-both-cases", "claimKind": "property", "assert": "!result || (code != 65 && code != 97)"}
CLAIMS = {
    "vulnerable-security": SECURITY, "fixed-security": SECURITY, "mutant-security": SECURITY,
    "preservation": {"property": "gate-unchanged-outside-the-fixed-case", "claimKind": "preservation"},
    "regex-probe": {"property": "regex-gate-never-allows-null", "claimKind": "property", "assert": "!result || field != null"},
}
VERDICTS = {"established": ("verified",), "refuted": ("violation",), "unresolved": ("unverifiable", "refused", None)}
TRIGGERS = {"vulnerable-security": "97", "mutant-security": "65"}  # where the oracle says each revision fails


def plan(task, folder=FOLDER):
    """The TaskPlan of fixture task `task`, from the sidecar and CLAIMS."""
    folder = Path(folder)
    target = json.loads((folder / "target.json").read_text())
    t = next(x for x in target["tasks"] if x["id"] == task)
    history, prep = target["history"], target["preparation"]
    if t.get("pair"):
        pair = next(p for p in history["pairs"] if p["name"] == t["pair"])
        revisions = (pair["before"], pair["after"])
    else:
        revisions = (t["revision"],)
    artifacts = tuple({"revision": r, "route": prep["route"], "repository": history["repository"],
                       "fixture": history["revisions"][r]["fixture"], "adapters": list(prep.get("adapters", [])),
                       "jdks": list(prep.get("jdks", []))} for r in revisions)
    stated = CLAIMS[task]
    claim = {"task": task, "kind": t["kind"], "relation": t["relation"], "target": t["target"], **stated,
             "assume": stated.get("assume"), "assert": stated.get("assert"), "throws": [], "nullable": [], "mayAlias": [],
             "observations": ["result", "exception"], "assumptions": [], "allowedChange": t.get("allowedChange"),
             "bounds": dict(BOUNDS), "models": [], "plan": None, "contracts": None, "gaps": t.get("gaps"),
             "standIn": "runtime_calibrate.py's CLAIMS, until workflow's plan_task is merged"}
    return interfaces.TaskPlan(
        example=EXAMPLE, task=task, kind=t["kind"], relation=t["relation"], target=t["target"], revisions=revisions,
        claim=claim, prerequisites=(), artifacts=artifacts,
        tools={"required": ["java", "javac", "jvmcontract"], "optional": []}, engine=t.get("engine"),
        gaps=t.get("gaps"), expected=t.get("expected"), outputs={"receipts": f"receipts/{task}"}, folder=str(folder))


def verdict(record):
    """The outcome's verdict, read for this check only: the headline of prove's list, or equivalence's one."""
    if record.status != "exited" or not record.observations:
        return None
    found = [o.get("verdict") for o in record.observations]
    return next((v for v in ("violation", "unverifiable", "verified") if v in found), found[0])


def attempt(task, where, folder=FOLDER):
    p = plan(task, folder)
    entry = {"task": task, "kind": p.kind, "revisions": list(p.revisions), "expected": p.expected}
    prepared = {}
    for revision in p.revisions:
        r = runtime.prepare(p, revision, where / "prepare" / revision)
        if isinstance(r, Unsupported) or r.stage != "artifacts-ready":
            entry.setdefault("preparation", {})[revision] = r.describe() if isinstance(r, Unsupported) else \
                f"{r.stage}: {r.failedStage}: {r.diagnostic}"
            continue
        prepared[revision] = r
    record = runtime.run_verifier(p, prepared, where / "verifier")
    if isinstance(record, Unsupported):
        entry.update(unsupported=record.describe(), diagnostic=record.diagnostic, ok=False)
        return entry
    output = "".join(o.get("output", "") for o in record.observations or ())
    stderr = (where / record.stderr).read_text(errors="replace")
    found = verdict(record)
    scope = record.identities.get("scope", {})
    entry.update({"status": record.status, "exitCode": record.exitCode, "seconds": record.seconds,
                  "argv": list(record.argv), "verdict": found, "scope": scope.get("label"),
                  "parameters": {r: x.get("parameters") for r, x in scope.get("revisions", {}).items()},
                  "probe": {r: x.get("gaps") for r, x in record.identities.get("probe", {}).items()},
                  "output": output, "stderrTail": stderr[-2000:]})
    entry["ok"] = record.status == "exited" and record.observations is not None and found in VERDICTS[p.expected]
    if task == "regex-probe":
        # The refusal and the capability probe are told apart: a strict proof may stop before it reaches the regex
        # call (at a String parameter, say), while the probe's static scan names the calls the proof would need.
        entry["refusalNamesRegex"] = "java.util.regex" in output + stderr
        entry["probeNamesRegex"] = "java.util.regex" in json.dumps(entry["probe"])
        entry["namesRegex"] = entry["refusalNamesRegex"] or entry["probeNamesRegex"]
        entry["ok"] = entry["ok"] and entry["namesRegex"]
    if task in TRIGGERS:  # informational: whether the witness's text names the input the oracle fails on
        entry["witnessNamesTrigger"] = TRIGGERS[task] in output
    receipt = workflow.ingest(p, prepared, (record,), runtime_slice.receipts(p))
    entry["ingestion"] = receipt.describe() if isinstance(receipt, Unsupported) else interfaces.to_dict(receipt)
    return entry


def with_javac_flags(flags):
    """Add `flags` to the fixture recipe runtime.prepare() builds with (for the rest of this process); what the
    calibration is then of, in words."""
    if not flags:
        return "the fixture recipe, as build_fixtures.py defines it"
    recipe = runtime._fixture_recipe

    def flagged():
        r = recipe()
        return {**r, "flags": [*r.get("flags", []), *flags]}
    runtime._fixture_recipe = flagged
    return f"the fixture recipe plus javac {' '.join(flags)}: not the bytes build_fixtures.py builds"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("attempt", type=Path)
    parser.add_argument("--task", action="append", choices=sorted(CLAIMS))
    parser.add_argument("--fixture-javac-flag", action="append", default=[], dest="flags")
    args = parser.parse_args(argv)
    args.attempt.mkdir(parents=True, exist_ok=False)
    print(f"jvmcontract: {runtime.jvmcontract()}")
    variant = with_javac_flags(args.flags)
    if args.flags:
        print(f"variant: {variant}")
    entries = []
    folder = runtime_slice.case_copy(FOLDER, args.attempt / "fixture")
    for task in args.task or list(CLAIMS):
        entry = attempt(task, args.attempt / task, folder)
        entries.append(entry)
        print(f"{task}: expected {entry['expected']}, verifier {entry.get('status') or entry.get('unsupported')} "
              f"exit {entry.get('exitCode')}, verdict {entry.get('verdict')}, scope {entry.get('scope')}: "
              + ("as expected" if entry["ok"] else "NOT as expected"))
        if entry.get("output"):
            print("  " + entry["output"].strip().replace("\n", "\n  "))
    ok = all(e["ok"] for e in entries)
    (args.attempt / "calibration.json").write_text(json.dumps(
        {"calibration": "runtime R3: run_verifier on the fixture's proof tasks", "ok": ok,
         "jvmcontract": runtime.jvmcontract(), "variant": variant, "tasks": entries,
         "reading": "the verdicts are read here to check R3's plumbing against the fixture's authored expectations; "
                    "ingestion judges records in the route"}, indent=2, ensure_ascii=False) + "\n")
    print("ok" if ok else "NOT ok", f"({args.attempt / 'calibration.json'})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

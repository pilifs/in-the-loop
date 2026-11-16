#!/usr/bin/env python3
"""The checks a change to one example's own files needs, in place of the default test run before each commit of a
/prove-java-change run (CLAUDE.md, Tests): the default run takes about 16 minutes and checks the whole repository,
and comes once an example is done and before anything is published.

    python3 examples/tools/validate_example.py NNN [NNN ...]            the checks below, for these examples
    python3 examples/tools/validate_example.py --replay NNN [NNN ...]   and their replays on a JVM, run again
    python3 examples/tools/validate_example.py --json NNN ...           the same, as data

In this order, so that nothing reads a file an earlier step rewrites:

1. each example's form and artifacts, as `watch.py preflight` checks them: example.json against its schema, the
   sidecar, each revision's lock, each claim frozen, a proof task among the tasks;
2. each task's plan (`build.py --plan NNN`): every task plans offline, with its claim file loaded, of its kind and
   in step with the task's bounds;
3. the oracle's own test, `controls/oracle.py self-test`, where the oracle has one;
4. with --replay, the replay and mutant-replay tasks on a JVM (`build.py NNN --task T`), inline as the briefs allow;
5. the router (`build.py --index-only`), after anything that writes receipts and before the tests: they read
   examples/index.json, and a stale one fails them for no fault of the example;
6. the tests that read every example's files: the packets, the acceptance gates, the targets' contract and the gap
   inventory. They take seconds, and they discover a prepared example by itself: adding one edits none of them.

Exit 0 when every step passed, 1 otherwise. Standard library only (with jsonschema where it is installed, as
`watch.py preflight`).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "llm-dlc" / "tools"
TESTS = ("examples/tools/targets/test_packets.py", "examples/tools/targets/test_acceptance.py",
         "examples/tools/test_targets_contract.py", "examples/tools/targets/test_gap_inventory.py")
REPLAYS = ("replay", "mutant-replay")


def run(command: list[str], timeout: float = 900) -> tuple[bool, str, float]:
    start = time.monotonic()
    try:
        p = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout:.0f} s", time.monotonic() - start
    out = (p.stdout + p.stderr).strip()
    return p.returncode == 0, out, time.monotonic() - start


def tail(text: str, lines: int = 12) -> str:
    return "\n".join(text.splitlines()[-lines:])


def form(number: str) -> tuple[bool, str]:
    sys.path.insert(0, str(TOOLS))
    import changes  # noqa: E402  llm-dlc/tools/changes.py
    import watch    # noqa: E402  llm-dlc/tools/watch.py
    rows = changes.listing(REPO, [number])["examples"]
    if not rows or not rows[0].get("path"):
        return False, f"no example {number}"
    row = rows[0]
    gaps = list(row.get("gaps") or []) + watch.schema_gaps(REPO, row)
    if row["state"] == "catalogued":
        return False, "a catalog entry: nothing is set up yet"
    return not gaps, "; ".join(f"{g['kind']}: {g['what']}" for g in gaps) or f"{row['state']}"


def plans(number: str) -> tuple[bool, str, list[str]]:
    ok, out, _ = run([sys.executable, "examples/tools/build.py", "--plan", number])
    if not ok:
        return False, tail(out), []
    try:
        tasks = json.loads(out)[0]["tasks"]
    except (ValueError, LookupError, TypeError):
        return False, tail(out), []
    refused = [f"{t['task']}: {t['notExecuted']}" for t in tasks if not t.get("executable")]
    return not refused, "; ".join(refused) or f"{len(tasks)} tasks plan", [t["task"] for t in tasks]


def oracle(folder: Path) -> tuple[bool | None, str]:
    path = folder / "controls" / "oracle.py"
    if not path.exists() or "self-test" not in path.read_text():
        return None, "no oracle self-test"
    ok, out, _ = run([sys.executable, str(path.relative_to(REPO)), "self-test"], timeout=300)
    return ok, "passed" if ok else tail(out, 12)


def validate(numbers: list[str], replay: bool) -> dict:
    steps = []

    def step(name, ok, detail, example=None):
        steps.append({"example": example, "step": name, "ok": ok, "detail": detail})

    for number in numbers:
        folder = next(iter(sorted((REPO / "examples").glob(f"{number}-*"))), None)
        if folder is None:
            step("form", False, f"no example {number}", number)
            continue
        ok, detail = form(number)
        step("form", ok, detail, number)
        ok, detail, tasks = plans(number)
        step("plans", ok, detail, number)
        ok, detail = oracle(folder)
        if ok is not None:
            step("oracle self-test", ok, detail, number)
        if replay:
            for task in (t for t in REPLAYS if t in tasks):
                ok, out, took = run([sys.executable, "examples/tools/build.py", number, "--task", task], timeout=1800)
                step(f"{task} on a JVM", ok, f"{took:.0f} s; " + tail(out, 3), number)
    ok, out, _ = run([sys.executable, "examples/tools/build.py", "--index-only"])
    step("router", ok, "examples/index.json and examples/README.md regenerated" if ok else tail(out))
    for test in TESTS:
        ok, out, took = run([sys.executable, test])
        step(Path(test).name, ok, f"{took:.0f} s" if ok else tail(out, 20))
    return {"examples": numbers, "ok": all(s["ok"] for s in steps), "steps": steps}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("numbers", nargs="+")
    ap.add_argument("--replay", action="store_true", help="run the replay tasks on a JVM again")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    found = validate(a.numbers, a.replay)
    if a.json:
        print(json.dumps(found, indent=1))
    else:
        for s in found["steps"]:
            mark = "ok  " if s["ok"] else "FAIL"
            where = f"{s['example']} " if s["example"] else ""
            print(f"{mark} {where}{s['step']}: {s['detail']}")
        print("passed" if found["ok"] else "failed: fix the steps marked FAIL before committing")
    return 0 if found["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

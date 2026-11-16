#!/usr/bin/env python3
"""The conductor's side of a moonshot loop: a session outside the loop judges what a rule can't
(llm-dlc/runtime.md#the-conductor).

A moonshot has no acceptance criteria, so nothing but its context window measures it. feature-loop.sh compacts a
moonshot's session at a fixed size, and an automatic compaction with no commit since the cycle began, or since the
last one, is the point where the work is either hard and going well or stuck. The loop can't tell which: by itself
it only logs the compaction, and a rule that stopped there stopped good work (FEATURE_LOOP_STOP_ON_COMPACT=1 still
turns it on). With a conductor directory (LOOP_CONDUCTOR, which prove-loop.sh sets) it asks: it appends the event
to DIR/events.jsonl, lets the turn go on, and waits for a verdict until the event's deadline. `stop` ends the turn
and the loop. `continue` lets the turn run to the next compaction, and so does no verdict in time, noted in the
run's record, unless the rule is on. The conductor never talks to the loop's session, whose instruction stays the
one line.

    conductor.py wait DIR [--timeout SECONDS]
        block until the loop asks for a verdict or ends, then print that event as JSON with what to read to
        judge it. Exit 0 with an event, 3 when the timeout passes first (the loop is still running: wait again).
    conductor.py decide DIR N VERDICT --reason TEXT
        answer event N with one of the answers it takes. The reason goes into the run's record beside the event,
        for the person who reads it later.
    conductor.py events DIR
        every event so far, with its verdict
    conductor.py command DIR LINE
        a line for the loop, as if typed in its terminal (feature-loop.sh's HELP: +N, -N, =N, stop, inf, item),
        applied before its next cycle and while it waits

An event of type `withdrawn` takes a question back: the turn ended by itself before a verdict came.

The loop asks three questions, each an event with the answers it takes, and each with a default when no verdict
comes before its deadline, so a conductor that has gone away never stops the work:

    compaction  a compaction with no commit: `continue` (the default) or `stop`
    cycle       a cycle of an item has committed: is the item `finished`, does it `continue` with another cycle,
                or is it only `waiting` on queued verification jobs (the loop then takes another item and comes
                back when they are in)? Without a verdict a judge of the loop's own answers (feature-loop.sh).
    example     the loop is between two items: `continue` (the default), or `stop` here. It waits longer while
                DIR/merge-queue names a workspace the conductor is to merge first.

The loop's side, for feature-loop.sh:

    conductor.py ask DIR TYPE --answers A,B --wait SECONDS [KEY=VALUE ...]
        append the question, wait for its verdict, and print `VERDICT<TAB>REASON`, or `none` after the deadline
    conductor.py note DIR TYPE [KEY=VALUE ...]
        append an event that asks nothing: where the loop is, for whoever watches
    conductor.py unfinished ITEM ...
        of these examples, the ones with verification jobs still queued, running or not collected, one per line
    conductor.py commands DIR
        print the lines `command` left and forget them

The orchestrating session runs `wait` as a background task, so it is called back when there is something to judge,
decides, and waits again. To judge: read what the session did since the cycle began or the last compaction (the
transcript the event names, the commits and the working copy's diff, the test runs and jobs), and whether the same
failure or file keeps coming back. Lean towards `continue` while the work is moving: an item left unfinished is
fine, a later pass can return to it, and a stop costs a person's attention.

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EVENTS = "events.jsonl"
COMMANDS = "commands"
MERGE_QUEUE = "merge-queue"
VERDICTS = ("continue", "stop", "finished", "waiting")
DEFAULT_ANSWERS = ("continue", "stop")  # an event that names none: a compaction
JOB_ID = re.compile(r"\d{8}-\d{6}-[a-z0-9-]+")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_events(directory: Path) -> list[dict]:
    try:
        lines = (directory / EVENTS).read_text().splitlines()
    except FileNotFoundError:
        return []
    events = []
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue  # a line still being written
        if isinstance(e, dict):
            events.append(e)
    return events


def append_event(directory: Path, **event) -> dict:
    """Add an event, numbered after the last, in one write (O_APPEND: the loop's reader and the loop itself both
    write here). Returns it."""
    directory.mkdir(parents=True, exist_ok=True)
    event = {"n": len(read_events(directory)) + 1, "time": now(), **event}
    with open(directory / EVENTS, "a") as f:
        f.write(json.dumps(event) + "\n")
    return event


def verdict_path(directory: Path, n: int) -> Path:
    return directory / f"verdict-{n}.json"


def read_verdict(directory: Path, n: int) -> dict | None:
    try:
        v = json.loads(verdict_path(directory, n).read_text())
    except (FileNotFoundError, ValueError):
        return None
    return v if isinstance(v, dict) and v.get("verdict") in VERDICTS else None


def pending(directory: Path) -> dict | None:
    """The first event the conductor has to act on: one asking for a verdict that has none and whose deadline has
    not passed, or the loop's end if nobody has been told of it."""
    events = read_events(directory)
    withdrawn = {e.get("event") for e in events if e.get("type") == "withdrawn"}
    for e in events:
        if e.get("type") == "ended":
            return None if (directory / "ended.seen").exists() else e
        if (e.get("needsVerdict") and e["n"] not in withdrawn and read_verdict(directory, e["n"]) is None
                and e.get("deadline", 0) > time.time()):
            return e
    return None


def cmd_wait(directory: Path, timeout: float) -> int:
    until = time.monotonic() + timeout
    while True:
        e = pending(directory)
        if e is not None:
            if e.get("type") == "ended":
                (directory / "ended.seen").write_text(now() + "\n")
            else:
                e["secondsLeft"] = int(e["deadline"] - time.time())
                e["answer"] = (f"python3 llm-dlc/tools/conductor.py decide {directory} {e['n']} "
                               f"{'|'.join(answers(e))} --reason TEXT")
            print(json.dumps(e, indent=1))
            return 0
        if time.monotonic() >= until:
            print(json.dumps({"type": "timeout", "note": "nothing to judge yet and the loop has not ended: wait again"}))
            return 3
        time.sleep(2)


def answers(event: dict) -> tuple[str, ...]:
    return tuple(event.get("answers") or DEFAULT_ANSWERS)


def cmd_decide(directory: Path, n: int, verdict: str, reason: str) -> int:
    event = next((e for e in read_events(directory) if e.get("n") == n), None)
    if event is None or not event.get("needsVerdict"):
        print(f"event {n} asks for no verdict", file=sys.stderr)
        return 2
    if verdict not in answers(event):
        print(f"event {n} ({event.get('type')}) takes {' or '.join(answers(event))}, not {verdict}", file=sys.stderr)
        return 2
    if read_verdict(directory, n) is not None:
        print(f"event {n} already has its verdict: {read_verdict(directory, n)['verdict']}", file=sys.stderr)
        return 2
    late = event.get("deadline", 0) <= time.time()
    tmp = verdict_path(directory, n).with_suffix(".tmp")
    tmp.write_text(json.dumps({"verdict": verdict, "reason": " ".join(reason.split()), "time": now()}) + "\n")
    os.replace(tmp, verdict_path(directory, n))
    print(f"event {n}: {verdict}" + (" (after its deadline: the loop was no longer waiting for it)" if late else ""))
    return 0


COUNTS = ("cycle", "itemCycle")  # the fields that are numbers; an item such as 007 stays text


def fields(pairs: list[str]) -> dict:
    """KEY=VALUE arguments as an event's fields."""
    out = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        out[key] = int(value) if key in COUNTS and value.isdigit() else value
    return out


def cmd_ask(directory: Path, kind: str, takes: list[str], wait: float, pairs: list[str]) -> int:
    event = append_event(directory, type=kind, needsVerdict=True, answers=takes, deadline=time.time() + wait,
                         **fields(pairs))
    while time.time() < event["deadline"]:
        v = read_verdict(directory, event["n"])
        if v is not None and v["verdict"] in takes:
            print(f"{v['verdict']}\t{v.get('reason', '')}")
            return 0
        time.sleep(1)
    print("none")
    return 0


def cmd_command(directory: Path, line: str) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / COMMANDS, "a") as f:
        f.write(" ".join(line.split()) + "\n")
    return 0


def cmd_commands(directory: Path) -> int:
    """Hand the queued lines to the loop, once: the file is renamed before it is read, so a line written meanwhile
    is kept for the next call."""
    taken = directory / (COMMANDS + ".taken")
    try:
        os.replace(directory / COMMANDS, taken)
    except FileNotFoundError:
        return 0
    sys.stdout.write(taken.read_text())
    taken.unlink()
    return 0


def unfinished_jobs(root: Path = REPO) -> dict[str, list[str]]:
    """Example number -> its verification jobs that are queued, running or finished and not collected yet. A job is
    an example's when one of its outputs is in that example's folder (or, for a job whose file is not in this
    checkout, when its title names the example). A job this machine can't run never finishes here, so it does not
    count."""
    r = subprocess.run([sys.executable, str(root / "verification/pipeline.py"), "status", "--json"],
                       capture_output=True, text=True, cwd=root)
    try:
        status = json.loads(r.stdout)
    except ValueError:
        return {}
    rows = [row for key in ("pending", "running", "finished, not collected") for row in status.get(key, [])
            if "; cannot run here:" not in row]
    found: dict[str, list[str]] = {}
    for row in rows:
        m = JOB_ID.search(row)
        if not m:
            continue
        try:
            job = json.loads((root / "verification/jobs" / f"{m[0]}.json").read_text())
            examples = {o.split("/")[1][:3] for o in job.get("outputs") or []
                        if isinstance(o, str) and re.match(r"examples/\d{3}-", o)}
        except (OSError, ValueError):
            examples = set()  # a job committed in another workspace: its row's title has to do
        for example in sorted(examples or set(re.findall(r"\bexample[ -](\d{3})\b", row, re.I))):
            found.setdefault(example, []).append(m[0])
    return found


def cmd_unfinished(items: list[str]) -> int:
    jobs = unfinished_jobs()
    for item in items:
        if jobs.get(item):
            print(item)
    return 0


def cmd_events(directory: Path) -> int:
    for e in read_events(directory):
        v = read_verdict(directory, e["n"]) if e.get("needsVerdict") else None
        print(json.dumps({**e, **({"verdict": v} if v else {})}))
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="The conductor's side of a moonshot loop.")
    sub = p.add_subparsers(dest="command", required=True)
    w = sub.add_parser("wait", help="block until the loop asks for a verdict or ends")
    w.add_argument("directory", type=Path)
    w.add_argument("--timeout", type=float, default=3300, help="seconds (default 3300, under an hour)")
    d = sub.add_parser("decide", help="answer an event")
    d.add_argument("directory", type=Path)
    d.add_argument("n", type=int)
    d.add_argument("verdict", choices=VERDICTS)
    d.add_argument("--reason", required=True)
    e = sub.add_parser("events", help="every event so far")
    e.add_argument("directory", type=Path)
    c = sub.add_parser("command", help="a line for the loop, as if typed in its terminal")
    c.add_argument("directory", type=Path)
    c.add_argument("line", nargs="+")
    a = sub.add_parser("ask", help="the loop's side: ask a question and wait for its verdict")
    a.add_argument("directory", type=Path)
    a.add_argument("type")
    a.add_argument("--answers", required=True)
    a.add_argument("--wait", type=float, required=True)
    a.add_argument("fields", nargs="*", metavar="KEY=VALUE")
    n = sub.add_parser("note", help="the loop's side: an event that asks nothing")
    n.add_argument("directory", type=Path)
    n.add_argument("type")
    n.add_argument("fields", nargs="*", metavar="KEY=VALUE")
    u = sub.add_parser("unfinished", help="the examples, of those named, with verification jobs not in yet")
    u.add_argument("items", nargs="*")
    t = sub.add_parser("commands", help="the loop's side: take the queued command lines")
    t.add_argument("directory", type=Path)
    args = p.parse_args(argv)
    if args.command == "wait":
        return cmd_wait(args.directory, args.timeout)
    if args.command == "decide":
        return cmd_decide(args.directory, args.n, args.verdict, args.reason)
    if args.command == "command":
        return cmd_command(args.directory, " ".join(args.line))
    if args.command == "ask":
        return cmd_ask(args.directory, args.type, args.answers.split(","), args.wait, args.fields)
    if args.command == "note":
        append_event(args.directory, type=args.type, **fields(args.fields))
        return 0
    if args.command == "unfinished":
        return cmd_unfinished(args.items)
    if args.command == "commands":
        return cmd_commands(args.directory)
    return cmd_events(args.directory)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

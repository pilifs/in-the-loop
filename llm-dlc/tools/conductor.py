#!/usr/bin/env python3
"""The conductor's side of a moonshot loop: a session outside the loop judges what a rule can't
(llm-dlc/runtime.md#the-conductor).

A moonshot has no acceptance criteria, so nothing but its context window measures it. feature-loop.sh compacts a
moonshot's session at a fixed size, and an automatic compaction with no commit since the cycle began, or since the
last one, is the point where the work is either hard and going well or stuck. The loop can't tell which. With a
conductor directory (LOOP_CONDUCTOR, which prove-loop.sh sets) it asks instead of stopping: it appends the event
to DIR/events.jsonl, lets the turn go on, and waits for a verdict until the event's deadline. A verdict of
`continue` lets the turn run to the next compaction; `stop`, or no verdict in time, ends the turn and the loop as
the mechanical rule alone would have. The conductor never talks to the loop's session, whose instruction stays the
one line.

    conductor.py wait DIR [--timeout SECONDS]
        block until the loop asks for a verdict or ends, then print that event as JSON with what to read to
        judge it. Exit 0 with an event, 3 when the timeout passes first (the loop is still running: wait again).
    conductor.py decide DIR N continue|stop --reason TEXT
        answer event N. The reason goes into the run's record beside the event, for the person who reads it later.
    conductor.py events DIR
        every event so far, with its verdict

An event of type `withdrawn` takes a question back: the turn ended by itself before a verdict came.

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
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

EVENTS = "events.jsonl"
VERDICTS = ("continue", "stop")


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
                e["answer"] = f"python3 llm-dlc/tools/conductor.py decide {directory} {e['n']} continue|stop --reason TEXT"
            print(json.dumps(e, indent=1))
            return 0
        if time.monotonic() >= until:
            print(json.dumps({"type": "timeout", "note": "nothing to judge yet and the loop has not ended: wait again"}))
            return 3
        time.sleep(2)


def cmd_decide(directory: Path, n: int, verdict: str, reason: str) -> int:
    event = next((e for e in read_events(directory) if e.get("n") == n), None)
    if event is None or not event.get("needsVerdict"):
        print(f"event {n} asks for no verdict", file=sys.stderr)
        return 2
    if read_verdict(directory, n) is not None:
        print(f"event {n} already has its verdict: {read_verdict(directory, n)['verdict']}", file=sys.stderr)
        return 2
    late = event.get("deadline", 0) <= time.time()
    tmp = verdict_path(directory, n).with_suffix(".tmp")
    tmp.write_text(json.dumps({"verdict": verdict, "reason": " ".join(reason.split()), "time": now()}) + "\n")
    os.replace(tmp, verdict_path(directory, n))
    print(f"event {n}: {verdict}" + (" (after its deadline: the loop had already stopped by its own rule)" if late else ""))
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
    args = p.parse_args(argv)
    if args.command == "wait":
        return cmd_wait(args.directory, args.timeout)
    if args.command == "decide":
        return cmd_decide(args.directory, args.n, args.verdict, args.reason)
    return cmd_events(args.directory)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""How a run's loop and the session that watches it talk: the loop's questions and the watcher's verdicts.

A run has no acceptance criteria of its own, so a session outside it, the conductor (the run's watcher), judges
what a rule can't. feature-loop.sh is given a conductor directory (LOOP_CONDUCTOR, the run's directory:
llm-dlc/loop-summaries/single-NAME, which single_run.py sets). It appends each question to DIR/events.jsonl and
waits for a verdict until the question's deadline. The conductor never talks to the loop's session.

The loop asks two questions, each an event with the answers it takes, and each with a default when no verdict
comes before its deadline, so a conductor that has gone away never stops the work:

    run         a cycle has ended, with a commit or without: `continue` with another cycle, which takes the run's
                continue message as it stands then, or `stop` the run here. Without a verdict a cycle that committed
                is followed by another and one that did not ends the run, and three in a row without one end it.
    compaction  the session compacted itself with no commit since the cycle began, or since the last such
                compaction, which is where the work is either hard and going well or stuck: `continue` (the
                default) lets the turn run to the next compaction, `stop` ends the turn and the loop. The turn goes
                on while the conductor judges (FEATURE_LOOP_STOP_ON_COMPACT=1 ends it when no verdict comes).

An event of type `withdrawn` takes a question back: the turn ended by itself before a verdict came.

    conductor.py wait DIR [--timeout SECONDS]
        block until the loop asks for a verdict or ends, then print that event as JSON with what to read to
        judge it. Exit 0 with an event, 3 when the timeout passes first (the loop is still running: wait again).
    conductor.py decide DIR N VERDICT --reason TEXT
        answer event N with one of the answers it takes. The reason goes into the run's record beside the event,
        for the person who reads it later.
    conductor.py events DIR
        every event so far, with its verdict
    conductor.py command DIR LINE
        a line for the loop, as if typed in its terminal (feature-loop.sh's HELP: +N, -N, =N, stop, inf),
        applied before its next cycle

A watcher does not call these itself: single_run.py's `wait`, `answer`, `cycles` and `stop` do.

A verdict given in time is also a decision, and goes into the decision record beside the verdict's own file:
llm-dlc/decisions/NAME.jsonl (decisions.py), NAME the run directory's name (in a runtime checkout `local-NAME`, so a
user's record never meets the one a release carries). There the user reviews it afterwards with the rest
(`decisions.py list`, `review accept`, `review overturn --note`). The verdict's file stays what the loop reads, and
a record that can't be written never holds a verdict back. `decide --confidence medium` flags the decision for the
user's review; a verdict the conductor is not at least that sure of is not one to give: ask the user.

The loop's side, for feature-loop.sh:

    conductor.py ask DIR TYPE --answers A,B --wait SECONDS [KEY=VALUE ...]
        append the question, wait for its verdict, and print `VERDICT<TAB>REASON`, or `none` after the deadline
    conductor.py note DIR TYPE [KEY=VALUE ...]
        append an event that asks nothing: where the loop is, for whoever watches
    conductor.py commands DIR
        print the lines `command` left and forget them

To judge: read what the session did since the cycle began or the last compaction (the transcript the event names,
the commits and the working copy's diff, the test runs and jobs), and whether the same failure or file keeps
coming back. Lean towards `continue` while the work is moving, and a stop costs a person's attention.

The protocol is not tied to those two questions: a question is any event that needs a verdict and names its
answers, and one may name an `item` (an example's number), which its decision then cites. Until 2026-11-27 the
proof loop over examples asked two more that way (`cycle`, `example`) and a brief's streams two (`blocked`,
`merge`); both workflows are retired (llm-dlc/retired.md), and a decision record written then still holds their
answers.

Standard library only.
"""
from __future__ import annotations

import argparse
import fcntl
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
# finished and waiting answered the proof loop's questions, and rerun, leave and merged those of a brief's streams
# (both retired: llm-dlc/retired.md). They stay, so that the verdicts in a run directory written then are still
# read; no question asked now takes them.
VERDICTS = ("continue", "stop", "finished", "waiting", "rerun", "leave", "merged")
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
    write here), under a lock: two loops that share a directory and end at once each ask, and without it both
    took the number 1 and each other's verdict (two streams of one run, 2026-11-17). Returns it."""
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / f"{EVENTS}.lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
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


# What each question's answers mean and how one is taken back, for the decision record (decisions.py). All of
# them are cheap to take back: a loop's verdict costs a cycle or a restart, never work that is committed.
QUESTIONS = {
    "compaction": ("The session compacted with no commit{of}: does the turn go on?", {
        "continue": ("let the turn run to the next compaction", "the session keeps working without a commit, and spends tokens if it is stuck",
                     "answer stop at the next compaction"),
        "stop": ("end the turn and the loop", "what the turn has not committed stays in the working copy, and the loop has to be started again",
                 "start the run again (single_run.py start NAME): the session continues where it was")}),
    "run": ("A cycle of a single-agent run has ended: does the agent get another?", {
        "continue": ("another cycle, with the run's continue message", "a further cycle's time and tokens",
                     "answer stop after the next cycle, or stop the run (single_run.py stop)"),
        "stop": ("end the run here", "the session keeps what it did and nothing further is started",
                 "start the run again (single_run.py start NAME): it continues the same session")}),
}


def decision_record(directory: Path) -> tuple[str, Path] | None:
    """The decision record a run directory's verdicts go to, and where it is kept: for DIR =
    CHECKOUT/llm-dlc/loop-summaries/NAME, the record NAME under CHECKOUT/llm-dlc/decisions. None for a directory
    anywhere else, which has no checkout to keep a record in."""
    d = directory.resolve()
    if d.parent.name != "loop-summaries" or d.parent.parent.name != "llm-dlc" or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", d.name):
        return None
    checkout = d.parents[2]
    try:
        import mode
        local = mode.mode(checkout) == "runtime"
    except (Exception, SystemExit):  # a marker that can't be read: mode.py's own callers say so
        local = False
    return (f"local-{d.name}" if local else d.name), checkout / "llm-dlc" / "decisions"


def record_decision(directory: Path, event: dict, verdict: str, reason: str, confidence: str) -> str | None:
    """Add a verdict to the run's decision record. Returns the decision's id, or None when there is no record to add
    it to; raises what decisions.py raises when it refuses the line."""
    where = decision_record(directory)
    if where is None:
        return None
    import decisions
    name, root = where
    item = event.get("item")
    question, options = QUESTIONS.get(event.get("type"), ("The loop asks: {type}{of}", {}))
    known = {a: options.get(a, (a, "as the loop's question defines it", "ask the loop again")) for a in answers(event)}
    events = read_events(directory)
    patch = {
        "state": "decided",
        "asked": {"by": directory.resolve().name, "at": event["time"],
                  "question": question.format(of=f" on example {item}" if item else "", after=f", after {item}" if item else "",
                                              type=event.get("type"))},
        "context": {"files": sorted(str(p.relative_to(root.parents[1]))
                                    for p in (root.parents[1] / "examples").glob(f"{item}-*") if p.is_dir())} if item else {},
        "options": [{"id": a, "summary": text[0], "consequences": text[1]} for a, text in known.items()],
        "decision": {"option": verdict, "by": "conductor", "rationale": reason,
                     "confidence": {"level": confidence,
                                    "basis": f"the loop's event {event['n']} ({directory.name}/{EVENTS}), the example's state and the verification queue"},
                     "recovery": {"class": "cheap", "undo": known[verdict][2]}},
    }
    current, stamp = decisions.fold(decisions.read(name, root)), decisions.now()
    line = decisions.conductor_line(name, patch, current, events[0]["time"] if events else None, stamp, [])
    decisions.write(name, root, [line])
    return line["id"]


def cmd_decide(directory: Path, n: int, verdict: str, reason: str, confidence: str = "high") -> int:
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
    if not late:  # a verdict the loop no longer waited for decided nothing
        try:
            recorded = record_decision(directory, event, verdict, " ".join(reason.split()) or "no reason given", confidence)
            if recorded:
                print(f"recorded as {recorded}")
        except (Exception, SystemExit) as e:  # the verdict stands whatever the record says
            print(f"the verdict stands, but it is not in the decision record: {type(e).__name__}: {e}", file=sys.stderr)
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


def cmd_events(directory: Path) -> int:
    for e in read_events(directory):
        v = read_verdict(directory, e["n"]) if e.get("needsVerdict") else None
        print(json.dumps({**e, **({"verdict": v} if v else {})}))
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="How a run's loop and the session that watches it talk.")
    sub = p.add_subparsers(dest="command", required=True)
    w = sub.add_parser("wait", help="block until the loop asks for a verdict or ends")
    w.add_argument("directory", type=Path)
    w.add_argument("--timeout", type=float, default=3300, help="seconds (default 3300, under an hour)")
    d = sub.add_parser("decide", help="answer an event")
    d.add_argument("directory", type=Path)
    d.add_argument("n", type=int)
    d.add_argument("verdict", choices=VERDICTS)
    d.add_argument("--reason", required=True)
    d.add_argument("--confidence", choices=("high", "medium"), default="high",
                   help="medium flags the decision for the user's review")
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
    t = sub.add_parser("commands", help="the loop's side: take the queued command lines")
    t.add_argument("directory", type=Path)
    args = p.parse_args(argv)
    if args.command == "wait":
        return cmd_wait(args.directory, args.timeout)
    if args.command == "decide":
        return cmd_decide(args.directory, args.n, args.verdict, args.reason, args.confidence)
    if args.command == "command":
        return cmd_command(args.directory, " ".join(args.line))
    if args.command == "ask":
        return cmd_ask(args.directory, args.type, args.answers.split(","), args.wait, args.fields)
    if args.command == "note":
        append_event(args.directory, type=args.type, **fields(args.fields))
        return 0
    if args.command == "commands":
        return cmd_commands(args.directory)
    return cmd_events(args.directory)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

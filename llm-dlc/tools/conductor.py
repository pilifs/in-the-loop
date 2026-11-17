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

run-streams.sh asks two more of the watcher of a brief's run (RUN_STREAMS_WATCHER, llm-dlc/tools/brief_run.py):

    blocked     a stream's loop, or the brief's own, ended with a `blocked:` status: `rerun` it, once what blocked
                it is settled and its inbox says so, or `leave` it (the default) blocked.
    merge       a stream is finished, done or left blocked: the watcher merges its workspace's line into the default
                workspace's at once, while the other streams run (`brief_run.py merge`, which answers `merged`),
                or answers `leave` (the default), and the stream stays unmerged.

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
    conductor.py unfinished ITEM ...
        of these examples, the ones with verification jobs still queued, running or not collected, one per line;
        when the queue can't be read, every one of them, with exit status 1: a job is never taken to be in
        because its status could not be read
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
MERGE_QUEUE = "merge-queue"
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
    write here), under a lock: two streams of a brief's run that finish at once each ask, and without it both
    took the number 1 and each other's verdict. Returns it."""
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
                 "start the loop again on the same examples: the session continues where it was")}),
    "cycle": ("A cycle{of} has committed: is the example finished?", {
        "finished": ("the example is done", "the loop takes the next example and does not return to this one in this run",
                     "name the example in a later run of the loop"),
        "continue": ("another cycle on the example", "a further cycle's time and tokens",
                     "answer finished after the next cycle, or stop the loop after it"),
        "waiting": ("leave it until its verification jobs are in", "the loop takes another example meanwhile and returns when the jobs are in",
                    "nothing to undo: the loop returns to the example by itself")}),
    "example": ("The loop is between two examples{after}: does it take the next one?", {
        "continue": ("take the next example", "the run goes on", "stop the loop after the example under way"),
        "stop": ("end the loop here", "the examples left are not started", "start the loop again on the examples left")}),
    "blocked": ("A loop of a brief's run ended blocked: is it run again?", {
        "rerun": ("run the loop again", "what blocked it was settled and its inbox says so: it goes on, at a further cycle's cost",
                  "answer leave when it next ends blocked"),
        "leave": ("leave it blocked", "the run goes on without it; what it committed can still be merged, and its status says what it left for the user",
                  "set its status back to working and start the run again")}),
    "merge": ("A stream of a brief's run is finished: is it merged into the default line now?", {
        "merged": ("merge it into the default workspace's line now", "the line has the stream's commits while the other streams still run; "
                   "a conflict was resolved, or the merge was taken back",
                   "abandon the merge commit (jj abandon) before anything builds on it, or revert it after"),
        "leave": ("leave it unmerged", "its commits stay on its workspace's line, and the run ends without them",
                  "merge it later: brief_run.py merge BRIEF STREAM")}),
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


class QueueUnreadable(RuntimeError):
    """pipeline.py status gave nothing to read: the queue's state is unknown, which is not the same as empty."""


def queue_status(root: Path, tries: int = 3) -> dict:
    """pipeline.py status --json, read again a few times before giving up: under load, or while a commit or a runner
    holds the queue, it has once printed nothing, and an empty answer read as "no jobs" sends a loop back to an
    example whose proof is still running."""
    for attempt in range(tries):
        r = subprocess.run([sys.executable, str(root / "verification/pipeline.py"), "status", "--json"],
                           capture_output=True, text=True, cwd=root)
        try:
            status = json.loads(r.stdout)
            if r.returncode == 0 and isinstance(status, dict):
                return status
        except ValueError:
            pass
        if attempt + 1 < tries:
            time.sleep(2 * (attempt + 1))
    raise QueueUnreadable(f"pipeline.py status gave nothing to read (exit {r.returncode}): {r.stderr.strip()[-200:]}")


def unfinished_jobs(root: Path = REPO) -> dict[str, list[str]]:
    """Example number -> its verification jobs that are queued, running or finished and not collected yet. A job is
    an example's when one of its outputs is in that example's folder (or, for a job whose file is not in this
    checkout, when its title names the example). A job this machine can't run never finishes here, so it does not
    count. Raises QueueUnreadable when the queue can't be read."""
    status = queue_status(root)
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
    try:
        jobs = unfinished_jobs(REPO)
    except QueueUnreadable as e:
        print(f"conductor.py unfinished: {e}; counting every example named as unfinished", file=sys.stderr)
        for item in items:
            print(item)
        return 1
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
    u = sub.add_parser("unfinished", help="the examples, of those named, with verification jobs not in yet")
    u.add_argument("items", nargs="*")
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
    if args.command == "unfinished":
        return cmd_unfinished(args.items)
    if args.command == "commands":
        return cmd_commands(args.directory)
    return cmd_events(args.directory)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

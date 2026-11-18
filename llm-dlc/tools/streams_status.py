#!/usr/bin/env python3
"""The running state of run-streams.sh, for its status bar.

Two commands, both used by run-streams.sh:

  streams_status.py tag LABEL STATE_DIR
      Copies a loop's output from stdin to stdout, each line prefixed with
      [LABEL], as the script's sed did, and keeps the loop's state in STATE_DIR:
      LABEL.cost gets the dollar figure of every "turn done: ..., $X" line that
      show_progress (loop-common.sh) prints (the figure of a fork's first turn,
      the one after feature-loop.sh's "starting session ... as a fork of ..."
      line, written "=X"), LABEL.cycle the latest "cycle N" that
      feature-loop.sh logs, and LABEL.last the time of the loop's latest line. It
      ignores Ctrl-C and ends at end of input, so it never closes the pipe on the
      loop it reads.

  streams_status.py render --name NAME --state STATE_DIR --start EPOCH
                           [--integration REPORT] LABEL=WORKSPACE=BRIEF ...
      Prints one line: the run's age and total spend, then for each loop its
      current cycle, its commits (the "- cycle N," lines of its run records in
      WORKSPACE/llm-dlc/loop-summaries/, every run of that brief counted), its
      spend, its state (its brief's status while it runs, else what
      run-streams.sh wrote to LABEL.phase), and how long since its last line.
      The integration check's last result comes right after the totals, so a
      narrow pane cuts loops off, not it. BRIEF is relative to WORKSPACE.

The state survives a restart of run-streams.sh, so the spend is the brief's
whole run's, not only this invocation's.

A "turn done" figure is Claude Code's total_cost_usd, the session's cost so far,
not the turn's: each cycle of a loop resumes one session, and a resumed session
goes on from the total it had. So a loop's spend is what its figures rose by, and
a figure below the one before it starts a new session, counted whole. A forked
session's total starts at its parent's, which the fork didn't spend (the
planning session's, the same for every stream of a run): its first figure ("=X")
is only where its rises start. The fork turn's own cost, one turn without tools,
is lost in that, and only that.
"""
import argparse
import re
import signal
import sys
import time
from pathlib import Path

TURN_DONE = re.compile(r"turn done: .*\$([0-9]+(?:\.[0-9]+)?)\s*$")
# A turn of a client that reports tokens and no dollars (Codex, through agent_client.py): its cost is not known,
# and is shown as unknown beside the dollars that are, never as nought.
TURN_UNKNOWN = re.compile(r"turn done: .*cost unknown \(\w+: ([0-9]+) tokens in, ([0-9]+) out\)\s*$")
CYCLE = re.compile(r"\] cycle ([0-9]+)\b")
FORK = re.compile(r"\] starting session \S+ as a fork of \S+")
RECORD_CYCLE = re.compile(r"^- cycle [0-9]+,", re.M)
STATUS = re.compile(r"^[-*] +Status: *(.*)$")


def tag(label, state):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    state = Path(state)
    state.mkdir(parents=True, exist_ok=True)
    prefix = f"[{label}] ".encode()
    last_write = 0.0
    forking = False
    out = sys.stdout.buffer
    for raw in sys.stdin.buffer:
        try:
            out.write(prefix + raw)
            out.flush()
        except (BrokenPipeError, OSError):
            pass  # keep reading, so the loop never sees its pipe close
        line = raw.decode("utf-8", "replace")
        try:
            if FORK.search(line):
                forking = True
            m = TURN_DONE.search(line)
            if m:
                with open(state / f"{label}.cost", "a") as f:
                    f.write(("=" if forking else "") + m.group(1) + "\n")
                forking = False
            m = TURN_UNKNOWN.search(line)
            if m:
                with open(state / f"{label}.cost", "a") as f:
                    f.write(f"?{m.group(1)}:{m.group(2)}\n")  # not a figure: spend() passes over it
            m = CYCLE.search(line)
            if m:
                (state / f"{label}.cycle").write_text(m.group(1) + "\n")
            now = time.time()
            if now - last_write >= 5:
                (state / f"{label}.last").write_text(f"{now:.0f}\n")
                last_write = now
        except OSError:
            pass
    try:
        (state / f"{label}.last").write_text(f"{time.time():.0f}\n")
    except OSError:
        pass


def read(path, default=""):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return default


def unknown(state, label):
    """The turns of a loop whose cost is not known, with their tokens: (turns, tokens in, tokens out). A turn's
    count is that turn's alone (Codex reports each turn's), so they add up."""
    turns = tokens_in = tokens_out = 0
    for line in read(Path(state) / f"{label}.cost").split():
        m = re.fullmatch(r"\?([0-9]+):([0-9]+)", line)
        if m:
            turns, tokens_in, tokens_out = turns + 1, tokens_in + int(m.group(1)), tokens_out + int(m.group(2))
    return turns, tokens_in, tokens_out


def dollars(cost, turns):
    """A spend for display: the dollars known, and a mark when turns of unknown cost are not in them."""
    return (f"${cost:.2f}+?" if cost else "$?") if turns else f"${cost:.2f}"


def spend(state, label):
    """What a loop spent, from its sessions' running totals (see the header)."""
    total, before = 0.0, 0.0
    for line in read(Path(state) / f"{label}.cost").split():
        try:
            figure = float(line.lstrip("="))
        except ValueError:
            continue
        if line.startswith("="):
            pass  # a fork's parent's total: not this loop's
        elif figure >= before:
            total += figure - before
        else:
            total += figure  # a new session, from nothing
        before = figure
    return total


def commits(workspace, brief):
    prompt = Path(brief).stem
    return sum(len(RECORD_CYCLE.findall(read(p)))
               for p in (Path(workspace) / "llm-dlc" / "loop-summaries").glob(f"*-{prompt}.md"))


def brief_status(path):
    """The last "- Status:" line under the brief's "## Progress", as run-streams.sh's status_of reads it."""
    inside, status = False, ""
    for line in read(path).splitlines():
        if line.startswith("## "):
            inside = re.match(r"^## +Progress\s*$", line) is not None
            continue
        m = STATUS.match(line)
        if inside and m:
            status = m.group(1).replace("`", "")
    return status


def age(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h{seconds % 3600 // 60:02d}m"
    return f"{seconds // 86400}d{seconds % 86400 // 3600:02d}h"


def short(status, width=20):
    status = " ".join(status.split())
    return status if len(status) <= width else status[: width - 1] + "…"


def render(name, state, start, loops, integration=None, now=None):
    now = time.time() if now is None else now
    parts, total, unpriced = [], 0.0, 0
    for label, workspace, brief in loops:
        cost = spend(state, label)
        total += cost
        turns = unknown(state, label)[0]
        unpriced += turns
        phase = read(Path(state) / f"{label}.phase")
        if not phase:
            continue  # not started in this run, and nothing recorded: left out
        if phase == "running":
            phase = brief_status(Path(workspace) / brief) or "running"
        elif phase.startswith("finished: "):
            phase = phase[len("finished: "):] or "finished"
        cycle = read(Path(state) / f"{label}.cycle")
        last = read(Path(state) / f"{label}.last")
        idle = ""
        if last and read(Path(state) / f"{label}.phase") == "running":
            try:
                idle = " " + age(now - float(last))
            except ValueError:
                pass
        parts.append(f"{label} c{cycle or '-'} {commits(workspace, brief)}✓ {dollars(cost, turns)} {short(phase)}{idle}")
    head = [f"{name} {age(now - start)} {dollars(total, unpriced)}"]
    if integration:
        text = read(integration)
        m = re.search(r"^- Result: (\S+)", text, re.M)
        if m:
            try:
                when = age(now - Path(integration).stat().st_mtime)
            except OSError:
                when = "?"
            head.append(f"integration {m.group(1).rstrip(';,.')} {when} ago")
    return " │ ".join(head + parts)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    t = sub.add_parser("tag")
    t.add_argument("label")
    t.add_argument("state")
    r = sub.add_parser("render")
    r.add_argument("--name", required=True)
    r.add_argument("--state", required=True)
    r.add_argument("--start", type=float, required=True)
    r.add_argument("--integration")
    r.add_argument("loops", nargs="*", help="LABEL=WORKSPACE=BRIEF")
    args = p.parse_args(argv)
    if args.command == "tag":
        tag(args.label, args.state)
        return 0
    loops = []
    for spec in args.loops:
        label, workspace, brief = spec.split("=", 2)
        loops.append((label, workspace, brief))
    print(render(args.name, args.state, args.start, loops, args.integration))
    return 0


if __name__ == "__main__":
    sys.exit(main())

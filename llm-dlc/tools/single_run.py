#!/usr/bin/env python3
"""The watcher's tools for a single agent's run (.claude/skills/single-agent-run; llm-dlc/README.md, "A single
agent's run").

One agent works toward one outcome, and one watcher session stands outside it, as the watcher of a proof run or of
a brief's run does, with far less to keep: no examples, no streams, no foundation, no merge loop. The agent is
given a first text. When its turn ends (a cycle: the loop compacts the session after each, so a cycle is one
context window) the watcher is asked whether there is another, and every later cycle is given the run's continue
message, as it stands when that cycle starts. The user may have the watcher change that message between two
cycles, which is how a run is steered while it is under way. The loop is feature-loop.sh's `single-agent`, with
this run's directory as its conductor. NAME names the run.

    single_run.py start NAME [--prompt TEXT | --prompt-file FILE] [--continue TEXT | --continue-file FILE]
                        [--brief FILE] [--workspace WS] [--session ID | --fork ID] [--model ID] [--effort LEVEL]
                        [--memory SIZE] [--cycles N] [--verdict-wait SECONDS] [--summary-interval SECONDS]
                        [--no-verification]
        start the run, detached. A new run needs its first text (--prompt). Without --continue the message is
        DEFAULT_CONTINUE. --brief names a file the agent is pointed at in every cycle, in one sentence after the
        text; nothing else is added to either text. The agent works in this checkout, or with --workspace in the
        jj workspace WS, made beside it from this line's last commit when there is none: its commits then come
        in by `land`. Its session is new (Fable 5.2 at high effort, under the memory cap the doctor's budget
        gives a loop), or with --session one of that folder's that it continues, or with --fork a copy of any
        session of this machine, which carries on untouched. Run again on a run that has stopped, it continues the
        same session, and that leg's first cycle takes the continue message, or --prompt when one is given.
    single_run.py wait NAME [--interval SECONDS] [--timeout SECONDS]
        block until something needs the watcher, and print it: a `question` (a cycle has ended: another, or stop;
        or the session compacted with no commit), `results` and `verification` (the queue, kept as the watcher
        of a brief's run keeps it), a summary (every 30 minutes, or `interval`), or `ended`. Exit 3 with nothing
        after the timeout: wait again.
    single_run.py answer NAME continue|stop --reason TEXT [--message TEXT | --message-file FILE] [--confidence medium]
        answer the question that is open. --message also sets the continue message, before the answer, so the
        next cycle takes it. The answer is recorded as a decision (llm-dlc/decisions/single-NAME.jsonl).
    single_run.py message NAME [TEXT | --file FILE]
        the continue message: print it, or set it. A cycle under way is not interrupted: the message is read
        when a cycle starts.
    single_run.py status NAME           where the run stands, as data
    single_run.py summary NAME          a summary now
    single_run.py interval NAME SECONDS how often `wait` gives a summary from now on
    single_run.py cycles NAME LINE      change how many cycles are left, as typed in the loop's terminal: +N, -N, =N, inf
    single_run.py stop NAME [--now]     end the run after the cycle under way (it still compacts and summarizes);
                                        --now interrupts it mid-cycle instead. `start` continues it.
    single_run.py collect NAME          collect and commit the verification results that are back, as `wait` does
    single_run.py jobs NAME [--timeout SECONDS]
                                        block until no verification job is queued, running or back and not collected,
                                        keeping the queue meanwhile: for a run stopped only to wait on its jobs,
                                        which `start` then continues. Returns early with a result that did not pass.
    single_run.py land NAME             bring a workspace's commits to this checkout's line (brief_run.py's `land`)
    single_run.py list                  the runs this checkout knows, and which are under way

The run's directory is llm-dlc/loop-summaries/single-NAME/ (gitignored): watch.json (the run and the watcher's own
state), first.md and continue.md (the two texts), messages.jsonl (each continue message and when it was set),
loop.log (the loop's output), and the loop's questions (events.jsonl, conductor.py). The loop's record is
llm-dlc/loop-summaries/TIME-single-NAME.md in the folder the agent works in, as for every loop.

Standard library only.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import brief_run
import conductor
import doctor
import watch

REPO = Path(__file__).resolve().parents[2]
INTERVAL = 1800
MODEL, EFFORT = "claude-fable-5-2", "high"
VERDICT_WAIT = 900  # seconds the loop waits for the watcher after a cycle: time to read a report, or to ask the user
NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,47}")
# What a later cycle is told when the user gave no message of their own. It asks for the two things a watcher
# needs to see at the end of a turn: that the work is committed, and a plain word when there is nothing left.
DEFAULT_CONTINUE = ("Continue the work toward the outcome you were given. Take the next piece that is not done, "
                    "finish it, verify it, and commit it as CLAUDE.md describes. If the outcome is reached, or what "
                    "is left needs a decision from the user, don't start something new: say so plainly at the end "
                    "of your reply, with what is left.")
REPORT_LIMIT = 8000  # characters of a cycle's report a question carries: the watcher's context is the run's memory
OTHER_RUNS = ("run-streams.sh", "prove-loop.sh")  # runs whose own watcher keeps the verification queue


class Problem(Exception):
    pass


class Run(watch.Run):
    """A single agent's run: its directory in this checkout, and the watcher's state in it."""

    def __init__(self, root: Path, name: str):
        if not NAME.fullmatch(name):
            raise Problem(f"a run's name is lower-case letters, digits and dashes, 48 at most: {name!r}")
        self.root = root
        self.name = name
        self.loop = f"single-{name}"
        self.dir = root / "llm-dlc" / "loop-summaries" / self.loop
        self.path = self.dir / "watch.json"
        self.first = self.dir / "first.md"
        self.message = self.dir / "continue.md"
        self.history = self.dir / "messages.jsonl"

    @property
    def folder(self) -> Path:
        return Path(self.read().get("folder") or self.root)

    def running(self) -> bool:
        loop = self.read().get("loop") or {}
        return bool(loop.get("pid")) and not loop.get("ended") and watch.alive(loop["pid"])


def text_of(text: str | None, file: str | None, what: str) -> str | None:
    """A text given on the command line or in a file; None when neither is."""
    if text is not None and file is not None:
        raise Problem(f"{what}: give the text or a file, not both")
    if file is not None:
        try:
            text = Path(file).expanduser().read_text()
        except OSError as e:
            raise Problem(f"{what}: {file} can't be read ({e.strerror})")
    if text is not None and not text.strip():
        raise Problem(f"{what}: the text is empty")
    return text.strip() + "\n" if text is not None else None


def write(path: Path, text: str) -> None:
    """In one step: the loop reads the continue message whenever a cycle starts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def set_message(run: Run, text: str, why: str) -> bool:
    """Make TEXT the continue message, and keep when it was set. False when it is the message already."""
    if run.message.exists() and run.message.read_text() == text:
        return False
    write(run.message, text)
    with open(run.history, "a") as f:
        f.write(json.dumps({"time": conductor.now(), "set": why, "text": text.strip()}) + "\n")
    return True


def messages(run: Run) -> list[dict]:
    try:
        return [json.loads(line) for line in run.history.read_text().splitlines() if line.strip()]
    except (OSError, ValueError):
        return []


def is_default(root: Path) -> bool:
    default = brief_run.workspaces(root).get("default")
    return default is not None and default.resolve() == root.resolve()


def change_id(folder: Path) -> str | None:
    r = brief_run.jj(folder, "log", "--no-graph", "-r", "@-", "-T", "change_id", snapshot=False)
    return r.stdout.strip() or None if r.returncode == 0 else None


# -- starting

def workspace_folder(run: Run, name: str) -> tuple[Path, bool]:
    """The folder of the jj workspace NAME, made beside the default workspace's from this line's last commit when
    there is none. (the folder, whether it was made now)."""
    if not NAME.fullmatch(name):
        raise Problem(f"a workspace's name is lower-case letters, digits and dashes: {name!r}")
    known = brief_run.workspaces(run.root)
    if name in known:
        if known[name] is None or not known[name].is_dir():
            raise Problem(f"jj knows the workspace {name} but not its folder: `jj workspace forget {name}`, or give another name")
        return known[name], False
    base = known.get("default") or run.root
    folder = base.parent / f"{base.name}-{name}"
    if folder.exists():
        raise Problem(f"{folder} already exists, but no jj workspace is at it: delete it first, or give another name")
    r = brief_run.jj(run.root, "workspace", "add", "--name", name, "-r", "@-", str(folder))
    if r.returncode != 0:
        raise Problem(f"could not add the workspace {name}: {r.stderr.strip()}")
    # the session logs this checkout stores and has not uploaded: without them every commit's check in the new
    # workspace reports each as an error, which the agent would then try to fix
    brief_run.adopt_logs(folder)
    return folder, True


def brief_named(run: Run, file: str, workspace: str | None) -> str:
    """How the agent is told where the brief is: by its path in the checkout when it is inside this one (the same
    path in a workspace, where it must then be committed), else by its absolute path."""
    path = Path(file).expanduser()
    if not path.is_absolute():  # from where the command was typed, else from the checkout's root
        path = next((p for p in (Path.cwd() / path, run.root / path) if p.is_file()), path)
    path = path.resolve()
    if not path.is_file():
        raise Problem(f"no brief at {file}")
    try:
        rel = path.relative_to(run.root.resolve())
    except ValueError:
        return str(path)
    if workspace:
        known = brief_run.workspaces(run.root).get(workspace)
        if known is not None:
            if not (known / rel).is_file():
                raise Problem(f"the brief {rel} is not in the workspace {workspace} ({known}): bring it there, or give a "
                              f"file outside the checkout")
        elif (brief_run.jj(run.root, "file", "show", "-r", "@-", str(rel)).returncode != 0
              or brief_run.jj(run.root, "diff", "-r", "@", "--name-only", "--", str(rel)).stdout.strip()):
            raise Problem(f"the brief {rel} is not committed as it stands, and the workspace {workspace} is made from this "
                          f"line's last commit: commit it first (`sync.py commit --only {rel} -m ...`)")
    return str(rel)


def cmd_start(run: Run, a: argparse.Namespace) -> int:
    data = run.read()
    if run.running():
        print(f"the run {run.name} is already under way (pid {data['loop']['pid']}): `single_run.py wait {run.name}`")
        return 0
    new = not data.get("session")
    prompt = text_of(a.prompt, a.prompt_file, "--prompt")
    given = text_of(getattr(a, "continue"), a.continue_file, "--continue")
    if new and prompt is None:
        raise Problem("a new run needs its first text: --prompt TEXT or --prompt-file FILE")
    if not new and (a.session or a.fork):
        raise Problem(f"the run {run.name} has its session ({data['session']}), which `start` continues: a run of "
                      f"another name starts another session")
    if a.session and a.fork:
        raise Problem("--session continues a session and --fork starts from a copy of one: give one of them")
    for flag, value in (("--session", a.session), ("--fork", a.fork)):
        if value and not brief_run.SESSION.fullmatch(value):
            raise Problem(f"{flag}: not a session id: {value}")
    workspace = a.workspace or data.get("workspace")
    if not new and a.workspace and a.workspace != data.get("workspace"):
        raise Problem(f"the run {run.name} works in {data.get('workspace') or 'this checkout'}, where its session is: "
                      f"a run of another name works elsewhere")
    brief = brief_named(run, a.brief, workspace) if a.brief else data.get("brief")
    folder, made = workspace_folder(run, workspace) if workspace else (run.root, False)
    script = folder / "llm-dlc" / "tools" / "feature-loop.sh"
    try:
        knows = "single-agent)" in script.read_text()
    except OSError:
        knows = False
    if not knows:
        raise Problem(f"{script} has no single-agent loop: {folder} is on a line from before it was added")
    at_work = brief_run.loops_in(folder)
    if at_work:
        raise Problem(f"another loop is at work in {folder} (pid {at_work[0]}): two loops in one working copy commit over "
                      f"each other. --workspace NAME gives this run a folder of its own")
    if new:
        if a.session and not watch.transcript(folder, a.session).exists():
            raise Problem(f"no session {a.session} of {folder} to continue ({watch.transcript(folder, a.session).parent})")
        projects = watch.transcript(folder, "x").parents[1]
        if a.fork and not list(projects.glob(f"*/{a.fork}.jsonl")):
            raise Problem(f"no transcript of session {a.fork} to fork, under {projects}")
    session = data.get("session") or a.session or str(uuid.uuid4())
    memory = a.memory or data.get("memory") or doctor.budget(doctor.machine())["loopMemory"]
    cycles = a.cycles if a.cycles is not None else None
    queue = "off" if a.no_verification else "on" if is_default(run.root) else "off: this checkout is not the default workspace"

    run.dir.mkdir(parents=True, exist_ok=True)
    set_message(run, given or (run.message.read_text() if run.message.exists() else DEFAULT_CONTINUE + "\n"),
                "at the start" if new else "at a restart")
    write(run.first, prompt or run.message.read_text())
    for stale in ("events.jsonl", "ended.seen", "commands", "commands.taken", *[p.name for p in run.dir.glob("verdict-*.json")]):
        (run.dir / stale).unlink(missing_ok=True)
    base = change_id(folder)
    legs = list(data.get("legs") or []) + [{"started": conductor.now(), "first": "the prompt" if prompt else "the continue message",
                                            "base": base}]
    run.update(name=run.name, session=session, fork=a.fork if new else data.get("fork"), continued=bool(a.session) or data.get("continued", False),
               folder=str(folder), workspace=workspace, brief=brief, model=a.model or data.get("model") or MODEL,
               effort=a.effort or data.get("effort") or EFFORT, memory=memory, cycles=cycles,
               verdictWait=a.verdict_wait or data.get("verdictWait") or VERDICT_WAIT, verification=queue,
               base=data.get("base") or base, legs=legs, told=[], lastSummary=None, loop=None,
               **({"interval": a.summary_interval} if a.summary_interval else {}))
    pid = watch.detached([sys.executable, str(Path(__file__).resolve()), "--root", str(run.root), "loop", run.name],
                         run.root, run.dir / "loop.log")
    run.update(loop={"pid": pid, "started": legs[-1]["started"], "log": str(run.dir / "loop.log")})
    data = run.read()
    print(json.dumps({
        "started": run.name, "pid": pid, "session": session, "newSession": new and not a.session,
        "forkOf": data["fork"] if new else None, "folder": str(folder),
        "workspace": workspace, **({"workspaceMade": "now, from this line's last commit"} if made else {}),
        "model": data["model"], "effort": data["effort"], "memory": memory, "cycles": cycles or "no limit",
        "firstCycleTakes": legs[-1]["first"], "continueMessage": run.message.read_text().strip(), "brief": brief,
        "verificationQueue": queue, "output": str(run.dir / "loop.log"),
        "next": f"run `python3 llm-dlc/tools/single_run.py wait {run.name}` as a background task"}, indent=1))
    return 0


def cmd_loop(run: Run) -> int:
    """The detached process of a run: the loop itself, and afterwards the record of how it ended."""
    data = run.read()
    folder = Path(data["folder"])
    lock = open(run.dir / "lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(f"single_run.py: the run {run.name} is already under way ({run.dir / 'lock'} is held)", flush=True)
        return 1
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("FEATURE_LOOP_", "RUN_STREAMS_", "LOOP_WATCH_")) and k not in ("TMUX", "TMUX_PANE")}
    for key in ("FEATURE_LOOP_UNCAPPED", "FEATURE_LOOP_AUTOCOMPACT", "FEATURE_LOOP_UNWATCHED", "FEATURE_LOOP_CONDUCTOR_WAIT"):
        if key in os.environ:  # the caller's own word on these stands
            env[key] = os.environ[key]
    env.update(LOOP_CONDUCTOR=str(run.dir), FEATURE_LOOP_RECORD_AS=run.loop, FEATURE_LOOP_FIRST=str(run.first),
               FEATURE_LOOP_CONTINUE=str(run.message), FEATURE_LOOP_SESSION=data["session"],
               FEATURE_LOOP_MODEL=data["model"], FEATURE_LOOP_EFFORT=data["effort"],
               FEATURE_LOOP_JUDGE_WAIT=str(data["verdictWait"]))
    if data["memory"] == "none":
        env["FEATURE_LOOP_UNCAPPED"] = "1"
    else:
        env["FEATURE_LOOP_MEMORY_MAX"] = data["memory"]
    if data.get("brief"):
        env["FEATURE_LOOP_BRIEF"] = data["brief"]
    if data.get("fork") and not watch.transcript(folder, data["session"]).exists():
        env["FEATURE_LOOP_FORK"] = data["fork"]
    command = [str(folder / "llm-dlc" / "tools" / "feature-loop.sh"), "single-agent"] + ([str(data["cycles"])] if data.get("cycles") else [])
    # An interrupt (`stop --now`) goes to the whole group: the loop records it and ends, and this process outlives
    # it to record the end.
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: None)
    p = subprocess.Popen(command, cwd=folder, env=env, stdin=subprocess.DEVNULL)
    status = p.wait()
    records = sorted((folder / "llm-dlc" / "loop-summaries").glob(f"*-{run.loop}.md"))
    record = str(records[-1]) if records else None
    how = {0: "the run was ended by its watcher, by a stop, or its cycles ran out",
           1: "a cycle made no commit and no verdict came, the session compacted and was stopped, or the loop could not start",
           2: "the loop refused its arguments", 130: "interrupted"}.get(status, "see the loop's output")
    loop = {**(run.read().get("loop") or {}), "ended": conductor.now(), "status": status, "record": record}
    legs = list(run.read().get("legs") or [])
    if legs:
        legs[-1] = {**legs[-1], "ended": loop["ended"], "status": status, "record": record}
    run.update(loop=loop, legs=legs)
    conductor.append_event(run.dir, type="ended", status=status, record=record, session=data["session"], note=how)
    return status


# -- where the run stands

def last_result(path: str | None) -> dict | None:
    """The result event a turn's stream ends with."""
    try:
        lines = Path(path or "").read_text().splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get("type") == "result":
            return e
    return None


def uncommitted(folder: Path) -> list[str]:
    """The files the folder's working copy holds beyond its last commit, without the ones sync.py writes."""
    r = brief_run.jj(folder, "diff", "-r", "@", "--name-only")
    return [f for f in r.stdout.splitlines() if f.strip() and not brief_run.generated(f)] if r.returncode == 0 else []


def queue_counts(root: Path) -> dict:
    jobs = watch.jobs(root)
    return {k: len(jobs.get(k) or []) for k in ("pending", "running", "finished")}


def current_cycle(run: Run) -> dict | None:
    """The cycle under way, or the last one: its number, when it began, its turn's stream."""
    started = [e for e in conductor.read_events(run.dir) if e.get("type") == "cycle-start"]
    return started[-1] if started else None


def assessment(run: Run, event: dict) -> dict:
    """What the watcher needs beside a `run` question: what the cycle did, by its own report and by the repository."""
    data = run.read()
    folder = Path(data["folder"])
    result = last_result(event.get("turn")) or {}
    report = (result.get("result") or "").strip()
    key = f"{len(data.get('legs') or [])}.{event.get('cycle')}"
    costs = dict(data.get("cycleCosts") or {})
    if key not in costs:
        fresh = key == "1.1" and not data.get("continued") and not data.get("fork")
        cost = watch.turn_cost(run, result.get("session_id"), result.get("total_cost_usd"), fresh=fresh)
        if cost is not None:
            costs[key] = round(cost, 4)
            run.update(cycleCosts=costs)
    committed = watch.commits(folder, event.get("before"))
    left = uncommitted(folder)
    hint = ("Read the report against the outcome the run was given. `stop` when the outcome is reached, when what is "
            "left needs the user (a decision, credentials, a review), or when the cycle shows the agent going round "
            "the same failure. `continue` while the report shows work the agent can still do itself. ")
    hint += ("This cycle made no commit: `stop` unless the report says why and another cycle would end with one."
             if not committed else "")
    if left:
        hint += " It left files uncommitted: another cycle finishes and commits them, a stop leaves them where they are."
    return {"cycle": event.get("cycle"), "turn": {k: result.get(k) for k in ("subtype", "num_turns", "duration_ms")},
            "cost": costs.get(key), "commits": committed, "uncommitted": left[:20],
            "report": report[:REPORT_LIMIT] + (f"\n[... {len(report) - REPORT_LIMIT} more characters, in the session's "
                                                f"transcript: {watch.transcript(folder, data['session'])}]"
                                                if len(report) > REPORT_LIMIT else ""),
            "jobs": queue_counts(run.root), "nextCycleTakes": run.message.read_text().strip() if run.message.exists() else None,
            "hint": hint.strip()}


def state(run: Run) -> dict:
    data = run.read()
    if not data:
        raise Problem(f"no run {run.name} here ({run.dir}): `single_run.py list` names the ones there are")
    folder = Path(data["folder"])
    loop = data.get("loop") or {}
    running = run.running()
    cycle = current_cycle(run) if loop else None
    events = conductor.read_events(run.dir)
    asked = conductor.pending(run.dir)
    under_way = None
    if cycle:
        answered = any(e.get("type") == "run" and e.get("cycle") == cycle.get("cycle") for e in events)
        t = watch.turn(cycle.get("turn"))
        under_way = {"cycle": cycle.get("cycle"), "began": cycle.get("time"),
                     "state": "running" if running and not answered else "ended",
                     "toolCalls": t["toolCalls"],
                     "lastOutput": watch.span(watch.now() - t["lastOutput"]) + " ago" if t["lastOutput"] else None}
    first = watch.stamp((data.get("legs") or [{}])[0].get("started"))
    history = messages(run)
    return {"name": run.name, "running": running, "pid": loop.get("pid") if running else None,
            "session": data.get("session"), "folder": str(folder), "workspace": data.get("workspace"),
            "model": data.get("model"), "effort": data.get("effort"), "brief": data.get("brief"),
            "started": loop.get("started"), "ended": loop.get("ended"), "status": loop.get("status"),
            "elapsed": watch.span(watch.now() - first) if first else None, "legs": len(data.get("legs") or []),
            "cycle": under_way,
            "question": {k: asked.get(k) for k in ("n", "type", "cycle")} if asked and asked.get("needsVerdict") else None,
            "commits": watch.commits(folder, data.get("base")) if data.get("base") else [],
            "spent": round(sum((data.get("cycleCosts") or {}).values()), 2), "cycleCosts": data.get("cycleCosts") or {},
            "continueMessage": run.message.read_text().strip() if run.message.exists() else None,
            "messageSet": history[-1]["time"] if history else None, "messagesSet": len(history),
            "jobs": queue_counts(run.root), "verificationQueue": data.get("verification"),
            "record": loop.get("record"), "output": loop.get("log"),
            **({"landed": data["landed"]} if data.get("landed") else {})}


def summary(s: dict) -> str:
    now = time.strftime("%H:%M", time.gmtime())
    lines = [f"### {now} UTC · single-agent run {s['name']} · {s['elapsed'] or 'not started'}{'' if s['running'] else ' · not running'}"]
    c = s["cycle"]
    if c:
        began = watch.stamp(c["began"])
        took = f", {watch.span(watch.now() - began)} in" if began and c["state"] == "running" else ""
        lines.append(f"- cycle {c['cycle']} {c['state']}{took}: {c['toolCalls'] if c['toolCalls'] is not None else '?'} tool calls"
                     + (f", last output {c['lastOutput']}" if c["lastOutput"] else ""))
    if s["question"]:
        lines.append(f"- a question is open ({s['question']['type']}, event {s['question']['n']}): the loop waits for its answer")
    commits = s["commits"]
    lines.append(f"- commits this run: {len(commits)}" + (f", the last: {commits[-1]}" if commits else ""))
    if s["cycleCosts"]:
        lines.append(f"- spend: ${s['spent']:.2f} over {len(s['cycleCosts'])} cycle(s) that have ended")
    jobs = s["jobs"]
    if any(jobs.values()):
        lines.append(f"- verification queue: {jobs['pending']} pending, {jobs['running']} running, {jobs['finished']} back and not collected")
    if s["messagesSet"] > 1:
        lines.append(f"- the continue message was last set {s['messageSet']}: {' '.join((s['continueMessage'] or '').split())[:160]}")
    return "\n".join(lines)


# -- waiting for something to do

RESULTS_NOTE = ("say what came back in a line. Triage each one in `attention` as the run-verification skill's step 4 says, "
                "and record what needs a person in verification/findings.md (its step 5); a job out of time or memory is "
                "resubmitted (`pipeline.py resubmit ID ...`). Commit what you changed with `sync.py commit --only "
                "$(python3 verification/pipeline.py commit-paths)`. The agent reads the results itself, in its next cycle")


def keeps_queue(run: Run) -> bool:
    """Whether this watcher keeps the verification queue: when the run says so, and no other run's watcher does."""
    if run.read().get("verification") != "on":
        return False
    return not any(brief_run.running(run.root, script) for script in OTHER_RUNS)


def next_thing(run: Run, interval: float) -> dict | None:
    data = run.read()
    if not data:
        raise Problem(f"no run {run.name} here ({run.dir})")
    told = list(data.get("told") or [])

    def once(key: str) -> bool:
        if key in told:
            return False
        run.update(told=told + [key])
        return True

    event = conductor.pending(run.dir)
    if event is not None:
        if event.get("type") == "ended":
            (run.dir / "ended.seen").write_text(conductor.now() + "\n")
            return {"kind": "ended", "event": event, "state": state(run)}
        out = {"kind": "question", "event": {**event, "secondsLeft": int(event["deadline"] - time.time())},
               "answer": f"python3 llm-dlc/tools/single_run.py answer {run.name} {'|'.join(conductor.answers(event))} "
                         f"--reason TEXT [--confidence medium]"}
        if event.get("type") == "run":
            out["cycle"] = assessment(run, event)
            out["answer"] += " [--message TEXT: a new continue message, at the user's word only]"
        return out
    loop = data.get("loop") or {}
    if not loop.get("started"):
        return {"kind": "not-running", "note": f"the run {run.name} has not started a loop"}
    if not run.running():
        ended = any(e.get("type") == "ended" for e in conductor.read_events(run.dir))
        if not ended and once(f"gone:{loop['started']}"):
            return {"kind": "ended", "state": state(run),
                    "note": "the loop's process is gone and recorded no end: read the end of its output (`output`), "
                            "and `single_run.py start NAME` continues the run"}
        return {"kind": "not-running", "state": state(run), "note": "the run has ended: `start` continues it"}
    last = (data.get("lastSummary") or {}).get("time") or watch.stamp(loop.get("started")) or 0
    if watch.now() - last >= interval:
        return {"kind": "summary"}
    return None


def cmd_wait(run: Run, interval: float | None, timeout: float) -> int:
    interval = interval if interval is not None else run.read().get("interval", INTERVAL)
    until, looked = time.monotonic() + timeout, None
    while True:
        thing = next_thing(run, interval)
        if thing is None and (looked is None or time.monotonic() - looked >= watch.QUEUE_LOOK):
            looked = time.monotonic()
            if keeps_queue(run):
                thing = brief_run.tend(run)
        if thing is not None:
            if thing["kind"] == "results":
                thing["note"] = RESULTS_NOTE if thing.get("attention") else "say what came back in a line: every job passed"
            if thing["kind"] == "summary":
                print(summary(state(run)))
                run.update(lastSummary={"time": watch.now()})
                return 0
            print(json.dumps(thing, indent=1))
            return 0
        if time.monotonic() >= until:
            print(json.dumps({"kind": "nothing", "note": "nothing yet: wait again"}))
            return 3
        time.sleep(2)


# -- what the watcher does

def cmd_answer(run: Run, verdict: str, reason: str, message: str | None, confidence: str) -> int:
    event = conductor.pending(run.dir)
    if event is None or not event.get("needsVerdict"):
        raise Problem(f"no question of the run {run.name} is open (one that was is past its deadline: the loop went on without an answer)")
    if verdict not in conductor.answers(event):
        raise Problem(f"the open question ({event.get('type')}) takes {' or '.join(conductor.answers(event))}, not {verdict}")
    if message is not None and set_message(run, message, f"with the answer to cycle {event.get('cycle')}"):
        print("the continue message is set: the next cycle takes it" if verdict == "continue"
              else "the continue message is set, for when the run is started again")
    return conductor.cmd_decide(run.dir, event["n"], verdict, reason, confidence)


def cmd_message(run: Run, text: str | None) -> int:
    if not run.read():
        raise Problem(f"no run {run.name} here ({run.dir})")
    if text is None:
        print(json.dumps({"continueMessage": run.message.read_text().strip() if run.message.exists() else None,
                          "history": messages(run)}, indent=1))
        return 0
    changed = set_message(run, text, "by the watcher")
    cycle = current_cycle(run) if run.running() else None
    when = (f"cycle {cycle['cycle']} is under way and is not interrupted: the message is read when cycle {cycle['cycle'] + 1} starts"
            if cycle and isinstance(cycle.get("cycle"), int) and state(run)["cycle"]["state"] == "running"
            else "the next cycle to start takes it (the first of a run takes its prompt)" if run.running()
            else "the run is not under way: `start` continues it with this message")
    print(("the continue message is set" if changed else "that is the continue message already") + f"; {when}")
    return 0


def cmd_cycles(run: Run, line: str) -> int:
    if not re.fullmatch(r"[-+=]?\d+|[-+]|inf", line.replace(" ", "")):
        raise Problem(f"cycles takes +N, -N, =N or inf, as the loop's terminal does: {line!r}")
    if not run.running():
        raise Problem(f"the run {run.name} is not under way: `start --cycles N` sets its count")
    conductor.cmd_command(run.dir, line)
    print(f"left for the loop: {line} (applied when its cycle under way ends)")
    return 0


def cmd_stop(run: Run, now: bool) -> int:
    loop = run.read().get("loop") or {}
    if not run.running():
        print(f"the run {run.name} is not under way")
        return 0
    if now:
        os.killpg(int(loop["pid"]), signal.SIGINT)  # the loop records the interruption; its files stay as they are
        print(f"interrupted the run {run.name} (pid {loop['pid']}) mid-cycle: what it had not committed stays in the "
              f"working copy, and `single_run.py start {run.name}` continues the session")
        return 0
    conductor.cmd_command(run.dir, "stop")
    asked = conductor.pending(run.dir)
    print(f"the run {run.name} ends after its cycle under way, which still compacts and summarizes; `wait` returns "
          f"`ended` when it has" + (f". A question is open (event {asked['n']}): answer it `stop`, which ends the run now"
                                    if asked and asked.get("needsVerdict") else ""))
    return 0


def cmd_land(run: Run) -> int:
    data = run.read()
    workspace = data.get("workspace")
    if not workspace:
        raise Problem(f"the run {run.name} worked in this checkout: its commits are on this line already")
    if run.running():
        raise Problem(f"the run {run.name} is under way: stop it first, or wait for its end")
    left = uncommitted(Path(data["folder"]))
    if left:
        raise Problem(f"the workspace {workspace} has uncommitted files ({', '.join(left[:5])}): `single_run.py start "
                      f"{run.name}` gives the agent a cycle to finish and commit them")
    try:
        out = brief_run.land(run, workspace, (
            f"Merge the single-agent run {run.name} into the line",
            f"The single-agent run {run.name} (session {data.get('session')}) worked in the workspace {workspace} while "
            f"this line moved on, so its commits come in by a merge. Nothing but the generated trace files met; they "
            f"were regenerated from the session files."))
    except brief_run.Problem as e:
        raise Problem(str(e))
    run.update(landed=out.get("commit"))
    out["next"] = ("run the default test run inline (`python3 lib/tools/test_costs.py run`), as CLAUDE.md asks after a merge"
                   if out.get("landed", "").startswith("merged") else
                   "the line moved forward to the run's commits: nothing was merged, so nothing needs a test run for the merge's sake")
    print(json.dumps(out, indent=1))
    return 0


def cmd_collect(run: Run) -> int:
    try:
        got = brief_run.collect(run)
    except brief_run.Problem as e:
        raise Problem(str(e))
    print(json.dumps(got or {"collected": [], "note": "nothing is back"}, indent=1))
    return 0


def cmd_jobs(run: Run, timeout: float) -> int:
    """Wait for the verification queue to clear of what this machine can run, keeping it meanwhile as `wait` does."""
    if not run.read():
        raise Problem(f"no run {run.name} here ({run.dir})")
    until, came = time.monotonic() + timeout, []
    while True:
        thing = brief_run.tend(run) if keeps_queue(run) else None
        if thing is not None and thing["kind"] in ("results", "attention"):
            came.append({k: v for k, v in thing.items() if k != "note"})
        status = brief_run.queue(run.root)
        left = None if status is None else sum(
            "; cannot run here:" not in row for key in ("pending", "running", "finished, not collected") for row in status.get(key, []))
        flagged = [c for c in came if c.get("attention") or c["kind"] == "attention"]
        if left == 0 or flagged:
            print(json.dumps({"kind": "jobs", "left": left, "came": came,
                              "note": RESULTS_NOTE if flagged else
                              f"the queue is clear: `single_run.py start {run.name}` continues the run"}, indent=1))
            return 0
        if time.monotonic() >= until:
            print(json.dumps({"kind": "nothing", "left": left, "came": came, "note": "jobs are still out: wait again"}))
            return 3
        time.sleep(min(watch.QUEUE_LOOK, max(1, until - time.monotonic())))


def cmd_list(root: Path) -> int:
    rows = []
    for path in sorted((root / "llm-dlc" / "loop-summaries").glob("single-*/watch.json")):
        try:
            run = Run(root, path.parent.name.removeprefix("single-"))
        except Problem:
            continue
        data = run.read()
        loop = data.get("loop") or {}
        rows.append({"name": run.name, "running": run.running(), "started": loop.get("started"), "ended": loop.get("ended"),
                     "workspace": data.get("workspace"), "session": data.get("session")})
    print(json.dumps(rows, indent=1))
    return 0


def main(argv: list[str] | None = None, root: Path = REPO) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, help=argparse.SUPPRESS)  # the detached loop's, and the tests'
    sub = ap.add_subparsers(dest="command", required=True)

    def named(command: str, text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(command, help=text)
        p.add_argument("name", metavar="NAME")
        return p

    s = named("start", "start the run, or continue one that has stopped")
    s.add_argument("--prompt")
    s.add_argument("--prompt-file")
    s.add_argument("--continue")
    s.add_argument("--continue-file")
    s.add_argument("--brief")
    s.add_argument("--workspace")
    s.add_argument("--session")
    s.add_argument("--fork")
    s.add_argument("--model")
    s.add_argument("--effort")
    s.add_argument("--memory", help="the loop's memory cap, as 12G; `none` runs it uncapped")
    s.add_argument("--cycles", type=int)
    s.add_argument("--verdict-wait", type=int, help=f"seconds the loop waits for the watcher after a cycle ({VERDICT_WAIT})")
    s.add_argument("--no-verification", action="store_true", help="leave the verification queue alone")
    s.add_argument("--summary-interval", type=float, help=f"seconds between two summaries of `wait` ({INTERVAL})")
    w = named("wait", "block until something needs the watcher")
    w.add_argument("--interval", type=float)
    w.add_argument("--timeout", type=float, default=3300, help="seconds (default 3300, under an hour)")
    a = named("answer", "answer the open question")
    a.add_argument("verdict", choices=("continue", "stop"))
    a.add_argument("--reason", required=True)
    a.add_argument("--message")
    a.add_argument("--message-file")
    a.add_argument("--confidence", choices=("high", "medium"), default="high")
    m = named("message", "print the continue message, or set it")
    m.add_argument("text", nargs="?")
    m.add_argument("--file")
    named("status", "where the run stands, as data")
    named("summary", "a summary now")
    i = named("interval", "how often `wait` gives a summary")
    i.add_argument("seconds", type=float)
    c = named("cycles", "change how many cycles are left")
    c.add_argument("line")
    t = named("stop", "end the run after the cycle under way")
    t.add_argument("--now", action="store_true")
    named("collect", "collect and commit the verification results that are back")
    j = named("jobs", "block until the verification queue is clear, keeping it meanwhile")
    j.add_argument("--timeout", type=float, default=3300)
    named("land", "bring a workspace's commits to this checkout's line")
    sub.add_parser("loop").add_argument("name")  # the detached process of a run: `start` runs it
    sub.add_parser("list", help="the runs this checkout knows")
    args = ap.parse_args(argv)
    root = (args.root or root).resolve()
    try:
        if args.command == "list":
            return cmd_list(root)
        run = Run(root, args.name)
        if args.command == "start":
            if args.cycles is not None and args.cycles < 1:
                raise Problem("--cycles takes a count of 1 or more")
            return cmd_start(run, args)
        if args.command == "loop":
            return cmd_loop(run)
        if args.command == "wait":
            return cmd_wait(run, args.interval, args.timeout)
        if args.command == "answer":
            return cmd_answer(run, args.verdict, args.reason, text_of(args.message, args.message_file, "--message"), args.confidence)
        if args.command == "message":
            return cmd_message(run, text_of(args.text, args.file, "the message"))
        if args.command == "status":
            print(json.dumps(state(run), indent=1))
            return 0
        if args.command == "summary":
            print(summary(state(run)))
            run.update(lastSummary={"time": watch.now()})
            return 0
        if args.command == "interval":
            if not run.read():
                raise Problem(f"no run {run.name} here ({run.dir})")
            run.update(interval=args.seconds)
            print(f"`wait` gives a summary every {watch.span(args.seconds)} from now on")
            return 0
        if args.command == "cycles":
            return cmd_cycles(run, args.line)
        if args.command == "stop":
            return cmd_stop(run, args.now)
        if args.command == "collect":
            return cmd_collect(run)
        if args.command == "jobs":
            return cmd_jobs(run, args.timeout)
        return cmd_land(run)
    except Problem as e:
        print(f"single_run.py: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

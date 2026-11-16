#!/usr/bin/env python3
"""The watcher's tools: what the session that runs /prove-java-change uses to start the run's other sessions, watch
the proof loop, and act between its cycles and examples (llm-dlc/runtime.md#the-watcher).

The watcher is one session, on Opus 5.5. It does none of the work itself. It starts the sessions that do, in order,
keeps the user informed, and judges what a script can't:

    watch.py session [--new]               the id of the fixed session: the one that evaluates the changes and then
                                           proves them (made on first use, kept in the run's state)
    watch.py stage evaluate PROMPT         run the evaluation in the fixed session, on Fable 5.2 at medium effort
    watch.py stage setup PROMPT            run the examples' setup in a new session, on Opus 5.5 at high effort
                                           (both print the session's report; --model, --effort and --memory override)
    watch.py verification start|stop|status   the verification loop, on Sonnet 5.5, which runs the jobs the
                                           sessions queue; started once, before the examples are set up
    watch.py loop [OPTION ...] NNN ...     start the proof loop on these examples, continuing the fixed session at
                                           high effort; it runs detached, and the options are prove-loop.sh's
    watch.py wait [--interval SECONDS]     block until there is something for the watcher, and print it: a question
                                           of the loop's to answer, a proof that has come in, the loop's end, or,
                                           when the interval has passed since the last one, a summary
    watch.py summary                       a summary now, from llm-dlc/watch-summary-template.md: where the loop,
                                           the example under way and the verification jobs stand, with what changed
                                           since the last summary first
    watch.py status [--json]               everything the summary is made from, for a question about the run
    watch.py interval SECONDS              how often `wait` gives a summary (600 by default)
    watch.py merge add|done|list [NAME]    workspaces the user asked to have merged: the loop waits for the watcher
                                           between two examples while one is queued
    watch.py stop-after example|cycle|never   end the loop once the example, or the cycle, under way is done
    watch.py proof NNN                     block until the verification jobs of example NNN are in: the shell the
                                           watcher keeps on an example the loop has left to wait for its proof

The answers to the loop's questions go through conductor.py (`decide`), which `wait` names with each question.
The run's state is in llm-dlc/loop-summaries/prove-change/ (gitignored): watch.json beside the loop's own files.

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import changes        # llm-dlc/tools/changes.py
import claude_setup   # llm-dlc/tools/claude_setup.py
import conductor      # llm-dlc/tools/conductor.py
import mode           # llm-dlc/tools/mode.py

REPO = Path(__file__).resolve().parents[2]
RUN = "llm-dlc/loop-summaries/prove-change"
TEMPLATE = "llm-dlc/watch-summary-template.md"
INTERVAL = 600
STAGES = {"evaluate": {"model": "claude-fable-5-2", "effort": "medium", "fixed": True},
          "setup": {"model": "claude-opus-5-5", "effort": "high", "fixed": False}}
SILENT = 20 * 60  # a session that has written nothing for this long may be stuck: the summary says so
LEFT = ("finished", "capped")  # item states that end an example in this run


def now() -> float:
    return time.time()


def clock(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%H:%M")


def span(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{minutes // 60} h {minutes % 60:02d} min" if minutes >= 60 else f"{minutes} min"


def stamp(text: str | None) -> float | None:
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


class Run:
    """A run's directory and the watcher's own state in it."""

    def __init__(self, root: Path = REPO):
        self.root = root
        self.dir = root / RUN
        self.path = self.dir / "watch.json"

    def read(self) -> dict:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def update(self, **fields) -> dict:
        self.dir.mkdir(parents=True, exist_ok=True)
        data = {**self.read(), **fields}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1) + "\n")
        os.replace(tmp, self.path)
        return data

    def run_json(self) -> dict:
        try:
            return json.loads((self.dir / "run.json").read_text())
        except (OSError, ValueError):
            return {}


def alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except (TypeError, ValueError, ProcessLookupError):
        return False
    except PermissionError:
        return True
    return True


# -- the sessions the watcher starts

def transcript(root: Path, session: str) -> Path:
    """Where Claude Code keeps a session of this checkout (as feature-loop.sh's project_dir)."""
    projects = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    return projects / re.sub(r"[^A-Za-z0-9]", "-", str(root)) / f"{session}.jsonl"


def fixed_session(run: Run, new: bool = False) -> str:
    session = None if new else run.read().get("session")
    if not session:
        session = str(uuid.uuid4())
        run.update(session=session)
    return session


def stage_command(run: Run, name: str, prompt: str, model: str | None, effort: str | None, memory: str | None) -> list[str]:
    spec = STAGES[name]
    command = ["claude", "-p", prompt, "--model", model or spec["model"], "--effort", effort or spec["effort"]]
    if spec["fixed"]:
        session = fixed_session(run)
        command += ["--resume", session] if transcript(run.root, session).exists() else ["--session-id", session]
    if mode.mode(run.root) == "runtime":  # a user's own Claude Code setup is no part of the work
        command += claude_setup.clean_flags(run.root)
    command += ["--permission-mode", "auto", "--output-format", "stream-json", "--verbose"]
    if memory:
        command = ["systemd-run", "--user", "--scope", "--quiet", "--collect", "-p", f"MemoryMax={memory}",
                   "-p", "MemorySwapMax=0", *command]
    return command


def cmd_stage(run: Run, name: str, prompt: str, model: str | None, effort: str | None, memory: str | None) -> int:
    command = stage_command(run, name, prompt, model, effort, memory)
    run.dir.mkdir(parents=True, exist_ok=True)
    log = run.dir / f"stage-{name}.jsonl"
    env = {**os.environ, **(claude_setup.CLEAN_ENV if mode.mode(run.root) == "runtime" else {})}
    stages = run.read().get("stages") or {}
    stages[name] = {"started": conductor.now(), "log": str(log), "command": [c for c in command if c != prompt]}
    run.update(stages=stages)
    result = None
    with open(log, "a") as out:
        p = subprocess.Popen(command, cwd=run.root, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True)
        for line in p.stdout:
            out.write(line)
            out.flush()
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and event.get("type") == "result":
                result = event
        status = p.wait()
    ok = status == 0 and result is not None and result.get("subtype") == "success" and not result.get("is_error")
    stages[name].update(ended=conductor.now(), ok=ok, session=(result or {}).get("session_id"))
    run.update(stages=stages)
    print((result or {}).get("result") or f"the {name} session ended with status {status} and no report: see {log}")
    return 0 if ok else 1


# -- the verification loop and the proof loop

def store(directory: str | Path) -> str | None:
    """The jj repository a directory's workspace belongs to (as prove-loop.sh's store)."""
    repo = Path(directory) / ".jj" / "repo"
    try:
        if repo.is_dir():
            return str(repo.resolve())
        return str((repo.parent / repo.read_text().strip()).resolve())
    except OSError:
        return None


def verification_running(root: Path) -> int | None:
    mine = store(root)
    r = subprocess.run(["pgrep", "-u", str(os.getuid()), "-f", r"llm-dlc/tools/verification-loop\.sh"],
                       capture_output=True, text=True)
    for pid in r.stdout.split():
        try:
            theirs = store(os.readlink(f"/proc/{pid}/cwd"))
        except OSError:
            continue
        if mine and theirs == mine:
            return int(pid)
    return None


def detached(command: list[str], root: Path, log: Path) -> int:
    with open(log, "a") as out:
        p = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                             start_new_session=True)
    return p.pid


def cmd_verification(run: Run, action: str) -> int:
    running = verification_running(run.root)
    ours = (run.read().get("verification") or {}).get("pid")
    if action == "start":
        if running:
            print(f"a verification loop is already running for this repository (pid {running}): leaving the queue to it")
            return 0
        run.dir.mkdir(parents=True, exist_ok=True)
        pid = detached([str(run.root / "llm-dlc/tools/verification-loop.sh")], run.root, run.dir / "verification.log")
        run.update(verification={"pid": pid, "started": conductor.now()})
        print(f"started the verification loop (pid {pid}; its output: {run.dir / 'verification.log'})")
    elif action == "stop":
        if not ours or not alive(ours):
            print("this run started no verification loop that is still running")
            return 0
        os.kill(int(ours), signal.SIGUSR1)  # it ends after the job under way, as prove-loop.sh asks it to
        print(f"asked the verification loop (pid {ours}) to end after the job under way")
    else:
        print(f"running (pid {running})" + (", started by this run" if running == ours else "") if running else "not running")
    return 0


def cmd_loop(run: Run, arguments: list[str]) -> int:
    state = run.run_json()
    if state and not state.get("ended") and alive(state.get("pid")):
        print(f"a proof loop is already running here (pid {state['pid']}, examples {' '.join(state.get('examples', []))})",
              file=sys.stderr)
        return 1
    session = fixed_session(run)
    run.dir.mkdir(parents=True, exist_ok=True)
    command = [str(run.root / "llm-dlc/tools/prove-loop.sh"), "--session", session, *arguments]
    pid = detached(command, run.root, run.dir / "loop.log")
    run.update(loop={"pid": pid, "started": conductor.now(), "arguments": arguments}, lastSummary=None, announced=[])
    print(f"started the proof loop (pid {pid}) in session {session}; its output: {run.dir / 'loop.log'}")
    return 0


# -- where the run stands

def jobs(root: Path) -> dict:
    r = subprocess.run([sys.executable, str(root / "verification/pipeline.py"), "status", "--json"],
                       capture_output=True, text=True, cwd=root)
    try:
        status = json.loads(r.stdout)
    except ValueError:
        return {"pending": [], "running": [], "finished": [], "collected": {}}
    ids = lambda rows: [m[0] for row in rows if (m := conductor.JOB_ID.search(row))]
    collected = {}
    for row in status.get("collected", []):
        if m := conductor.JOB_ID.search(row):
            collected[m[0]] = (re.findall(r"\[([a-z -]+)\]\s*$", row) or ["?"])[0]
    return {"pending": ids(status.get("pending", [])), "running": ids(status.get("running", [])),
            "finished": ids(status.get("finished, not collected", [])), "collected": collected}


def commits(root: Path, since: str | None) -> list[str]:
    """The commits on the loop's line after change `since`, oldest first: `change summary`. All of the last five
    without one."""
    revset = f"{since}..@-" if since else "ancestors(@-, 5)"
    r = subprocess.run(["jj", "--quiet", "log", "--no-graph", "--reversed", "-r", revset, "-T",
                        'change_id.short(8) ++ " " ++ description.first_line() ++ "\n"'],
                       capture_output=True, text=True, cwd=root)
    return [line for line in r.stdout.splitlines() if line.strip()] if r.returncode == 0 else []


def turn(path: str | None) -> dict:
    """How far the session's turn has come: tool calls so far, and when it last wrote anything."""
    try:
        file = Path(path)
        calls = sum(line.count('"type":"tool_use"') + line.count('"type": "tool_use"') for line in file.open())
        return {"toolCalls": calls, "lastOutput": file.stat().st_mtime}
    except (TypeError, OSError):
        return {"toolCalls": None, "lastOutput": None}


def state(run: Run) -> dict:
    events = conductor.read_events(run.dir)
    loop = run.run_json()
    examples = loop.get("examples") or []
    started = [e for e in events if e.get("type") == "cycle-start"]
    current = started[-1] if started else {}
    items: dict[str, str] = {}
    for e in events:
        if e.get("type") == "cycle-start":
            items[e["item"]] = "under way"
        elif e.get("type") == "item" and e.get("state") != "resumed":
            items[e["item"]] = {"continue": "under way"}.get(e["state"], e["state"])
    ended = next((e for e in events if e.get("type") == "ended"), None)
    under_way = None if ended else current.get("item")
    rows = {r["id"]: r for r in changes.listing(run.root, examples)["examples"]} if examples else {}
    claims = {i: {t: c["status"] for t, c in (rows[i].get("claims") or {}).items()} for i in rows}
    head = commits(run.root, None)
    return {"time": now(), "started": stamp(loop.get("started")), "session": loop.get("session"),
            "examples": examples, "items": items, "item": under_way,
            "cycle": current.get("cycle"), "itemCycle": current.get("itemCycle"),
            "cycleStarted": stamp(current.get("time")), "turn": turn(current.get("turn")) if under_way else {},
            "claims": claims, "exampleState": {i: rows[i]["state"] for i in rows},
            "head": head[-1].split()[0] if head else None, "jobs": jobs(run.root),
            "unfinished": conductor.unfinished_jobs(run.root),
            "loopAlive": alive(loop.get("pid")) if loop else False, "ended": ended,
            "verification": verification_running(run.root),
            "mergeQueue": merge_queue(run), "asked": conductor.pending(run.dir)}


# -- the summary

def tally(statuses: dict) -> str:
    counts: dict[str, int] = {}
    for status in statuses.values():
        name = status if status in changes.ANSWERS else ("left open" if status else "no answer yet")
        counts[name] = counts.get(name, 0) + 1
    return ", ".join(f"{n} {name}" for name, n in counts.items()) or "no claim stated"


def changed(s: dict, last: dict | None, root: Path) -> list[str]:
    """What is different from the last summary, most telling first."""
    if not last:
        return ["this is the first summary of the run"]
    out = []
    for item, was in (last.get("items") or {}).items():
        if (is_now := s["items"].get(item)) != was:
            out.append(f"example {item}: {was} → {is_now}")
    out += [f"example {item} started" for item in s["items"] if item not in (last.get("items") or {})]
    for item, statuses in s["claims"].items():
        before = (last.get("claims") or {}).get(item) or {}
        out += [f"example {item}, claim {task}: {before.get(task) or 'no answer'} → {status or 'no answer'}"
                for task, status in statuses.items() if status != before.get(task)]
    new = commits(root, last.get("head")) if last.get("head") and last.get("head") != s["head"] else []
    out += [f"commit {line}" for line in new[-6:]]
    if len(new) > 6:
        out.insert(len(out) - 6, f"{len(new) - 6} more commits before these")
    was_collected = last.get("jobs", {}).get("collected") or {}
    for job, result in s["jobs"]["collected"].items():
        if job not in was_collected:
            out.append(f"job {job} is in: {result}")
    was_queued = set(last.get("jobs", {}).get("pending") or []) | set(last.get("jobs", {}).get("running") or [])
    queued = [j for j in s["jobs"]["pending"] + s["jobs"]["running"] if j not in was_queued and j not in s["jobs"]["collected"]]
    out += [f"job {job} was queued" for job in queued]
    if last.get("cycle") != s["cycle"] and s["cycle"]:
        out.append(f"the loop is on cycle {s['cycle']} (it was on {last.get('cycle') or 'none'})")
    return out or ["nothing"]


def attention(s: dict) -> list[str]:
    out = []
    if s["ended"]:
        out.append(f"the loop has ended (status {s['ended'].get('status')}): report, and stop the verification loop when the queue is clear")
    elif s["examples"] and not s["loopAlive"]:
        out.append("the loop's process is gone and it recorded no end: look at loop.log")
    if s["asked"]:
        out.append(f"the loop is waiting for an answer to its {s['asked'].get('type')} question (event {s['asked']['n']})")
    last_output = (s["turn"] or {}).get("lastOutput")
    if s["item"] and last_output and s["time"] - last_output > SILENT:
        out.append(f"the session has written nothing for {span(s['time'] - last_output)}: it may be waiting on a long command, or stuck")
    if (s["jobs"]["pending"] or s["jobs"]["running"]) and not s["verification"]:
        out.append("jobs are queued and no verification loop is running: `watch.py verification start`")
    out += [f"job {job} came back {result}" for job, result in s["jobs"]["collected"].items()
            if result not in ("passed", "?") and job in s.get("newlyCollected", ())]
    if s["mergeQueue"]:
        out.append(f"queued to merge at the next change of example: {', '.join(s['mergeQueue'])}")
    return out


def render(s: dict, last: dict | None, root: Path = REPO) -> str:
    s = {**s, "newlyCollected": [j for j in s["jobs"]["collected"] if j not in ((last or {}).get("jobs", {}).get("collected") or {})] if last else []}
    by_state = lambda *names: [i for i in s["examples"] if s["items"].get(i) in names]
    done, waiting = by_state(*LEFT), by_state("waiting")
    left = [i for i in s["examples"] if i not in s["items"]]
    examples = f"{len(done)} of {len(s['examples'])} done"
    examples += f" ({' '.join(done)})" if done else ""
    examples += f" · waiting on a proof: {' '.join(f'{i} ({len(s['unfinished'].get(i, []))} jobs out)' for i in waiting)}" if waiting else ""
    examples += f" · not started: {' '.join(left)}" if left else ""
    if s["item"]:
        t = s["turn"] or {}
        loop = (f"cycle {s['cycle']}, on example {s['item']}, its cycle {s['itemCycle']}, "
                f"{span(s['time'] - (s['cycleStarted'] or s['time']))} in")
        loop += f", {t['toolCalls']} tool calls so far" if t.get("toolCalls") is not None else ""
        loop += f", last output {span(s['time'] - t['lastOutput'])} ago" if t.get("lastOutput") else ""
        example = f"{s['exampleState'].get(s['item'], 'unknown')}: {tally(s['claims'].get(s['item']) or {})}"
        out = len(s["unfinished"].get(s["item"], []))
        example += f"; {out} of its verification jobs not in yet" if out else ""
    else:
        loop = "ended" if s["ended"] else ("between examples" if s["loopAlive"] else "not running")
        example = "none under way"
    j = s["jobs"]
    jobs_line = (f"{len(j['running'])} running, {len(j['pending'])} queued, {len(j['finished'])} finished and not "
                 f"collected, {len(j['collected'])} collected" + ("" if s["verification"] else " · no verification loop running"))
    since = f"{span(s['time'] - last['time'])} since the last summary" if last else "the first summary"
    values = {"time": clock(s["time"]), "elapsed": span(s["time"] - (s["started"] or s["time"])), "since": since,
              "changed": "\n".join(f"- {line}" for line in changed(s, last, root)),
              "loop": loop, "examples": examples, "item": s["item"] or "none", "example": example,
              "jobs": jobs_line, "attention": "\n".join(f"- {line}" for line in attention(s)) or "- nothing"}
    template = (root / TEMPLATE).read_text() if (root / TEMPLATE).exists() else DEFAULT_TEMPLATE
    body = template.split("<!-- template -->", 1)[-1].strip("\n")
    return body.format_map(values)


DEFAULT_TEMPLATE = """### {time} UTC · {elapsed} into the run · {since}

**Changed**
{changed}

**Loop:** {loop}
**Examples:** {examples}
**Example {item}:** {example}
**Verification jobs:** {jobs}

**Needs attention**
{attention}
"""


def snapshot(s: dict) -> dict:
    return {k: s[k] for k in ("time", "items", "claims", "head", "cycle", "jobs")}


def cmd_summary(run: Run) -> int:
    s = state(run)
    print(render(s, run.read().get("lastSummary"), run.root))
    run.update(lastSummary=snapshot(s))
    return 0


# -- waiting for something to do

def assessment(run: Run, event: dict) -> dict:
    """What the watcher needs beside a `cycle` question: where the example stands by its own folder and the queue."""
    item = event.get("item")
    rows = changes.listing(run.root, [item])["examples"] if item else []
    row = rows[0] if rows else {}
    out = len(conductor.unfinished_jobs(run.root).get(item, []))
    hint = ("every claim has its answer: finished, unless the report says work is left" if row.get("state") == "decided"
            else "its claims are not all answered, and jobs of it are queued: waiting if the session has nothing else to do, else continue" if out
            else "its claims are not all answered and nothing of it is queued: continue, unless what is left needs a person")
    return {"example": row.get("state"), "claims": {t: c["status"] for t, c in (row.get("claims") or {}).items()},
            "jobsNotIn": out, "hint": hint}


def next_thing(run: Run, interval: float) -> dict | None:
    event = conductor.pending(run.dir)
    if event is not None:
        if event.get("type") == "ended":
            (run.dir / "ended.seen").write_text(conductor.now() + "\n")
            return {"kind": "ended", "event": event}
        out = {"kind": "question", "event": {**event, "secondsLeft": int(event["deadline"] - time.time())},
               "answer": f"python3 llm-dlc/tools/conductor.py decide {RUN} {event['n']} {'|'.join(conductor.answers(event))} --reason TEXT"}
        if event.get("type") == "cycle":
            out["assessment"] = assessment(run, event)
        if event.get("type") == "example":
            out["mergeQueue"] = merge_queue(run)
        return out
    data = run.read()
    waiting = {e["item"] for e in conductor.read_events(run.dir) if e.get("type") == "item" and e.get("state") == "waiting"}
    announced = set(data.get("announced") or [])
    if waiting - announced:
        out_jobs = conductor.unfinished_jobs(run.root)
        for item in sorted(waiting - announced):
            if not out_jobs.get(item):
                run.update(announced=sorted(announced | {item}))
                return {"kind": "proof", "item": item,
                        "note": "its verification jobs are in: the loop takes it up again when it next changes example"}
    last = (data.get("lastSummary") or {}).get("time") or stamp((data.get("loop") or {}).get("started")) or 0
    if now() - last >= interval:
        return {"kind": "summary"}
    return None


def cmd_wait(run: Run, interval: float | None, timeout: float) -> int:
    interval = interval if interval is not None else run.read().get("interval", INTERVAL)
    until = time.monotonic() + timeout
    while True:
        thing = next_thing(run, interval)
        if thing is not None:
            if thing["kind"] == "summary":
                return cmd_summary(run)
            print(json.dumps(thing, indent=1))
            return 0
        if time.monotonic() >= until:
            print(json.dumps({"kind": "nothing", "note": "nothing yet: wait again"}))
            return 3
        time.sleep(2)


# -- what the user asks for between examples

def merge_queue(run: Run) -> list[str]:
    try:
        return [line.strip() for line in (run.dir / conductor.MERGE_QUEUE).read_text().splitlines() if line.strip()]
    except OSError:
        return []


def cmd_merge(run: Run, action: str, name: str | None) -> int:
    queue = merge_queue(run)
    if action == "add":
        workspaces = subprocess.run(["jj", "--quiet", "workspace", "list"], capture_output=True, text=True, cwd=run.root).stdout
        if not re.search(rf"^{re.escape(name)}( \(current\))?:", workspaces, re.M):
            print(f"no workspace {name} in this repository (jj workspace list)", file=sys.stderr)
            return 2
        queue = queue + [name] if name not in queue else queue
    elif action == "done":
        queue = [q for q in queue if q != name]
    run.dir.mkdir(parents=True, exist_ok=True)
    (run.dir / conductor.MERGE_QUEUE).write_text("".join(q + "\n" for q in queue))
    print("queued to merge between examples: " + (", ".join(queue) or "nothing"))
    return 0


def cmd_stop_after(run: Run, what: str) -> int:
    conductor.cmd_command(run.dir, {"example": "item", "cycle": "stop", "never": "inf"}[what])
    print({"example": "the loop ends once the example under way is done",
           "cycle": "the loop ends after the cycle under way",
           "never": "the loop runs until its examples are done"}[what])
    return 0


def cmd_proof(run: Run, item: str, timeout: float) -> int:
    until = time.monotonic() + timeout
    while True:
        out = conductor.unfinished_jobs(run.root).get(item, [])
        if not out:
            row = (changes.listing(run.root, [item])["examples"] or [{}])[0]
            print(json.dumps({"item": item, "jobs": "in", "example": row.get("state"),
                              "claims": {t: c["status"] for t, c in (row.get("claims") or {}).items()}}, indent=1))
            return 0
        if time.monotonic() >= until:
            print(json.dumps({"item": item, "jobs": "not in yet", "waitingFor": out}))
            return 3
        time.sleep(min(15, max(0.2, until - time.monotonic())))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=REPO, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("session").add_argument("--new", action="store_true")
    st = sub.add_parser("stage")
    st.add_argument("name", choices=sorted(STAGES))
    st.add_argument("prompt")
    st.add_argument("--model")
    st.add_argument("--effort")
    st.add_argument("--memory")
    sub.add_parser("verification").add_argument("action", choices=("start", "stop", "status"))
    sub.add_parser("loop").add_argument("arguments", nargs="*")
    w = sub.add_parser("wait")
    w.add_argument("--interval", type=float)
    w.add_argument("--timeout", type=float, default=3300)
    sub.add_parser("summary")
    sub.add_parser("status").add_argument("--json", action="store_true")
    sub.add_parser("interval").add_argument("seconds", type=int)
    m = sub.add_parser("merge")
    m.add_argument("action", choices=("add", "done", "list"))
    m.add_argument("name", nargs="?")
    sub.add_parser("stop-after").add_argument("what", choices=("example", "cycle", "never"))
    pr = sub.add_parser("proof")
    pr.add_argument("item")
    pr.add_argument("--timeout", type=float, default=3300)
    args, options = ap.parse_known_args(argv)
    if options and args.command != "loop":
        ap.error(f"unrecognized arguments: {' '.join(options)}")
    run = Run(args.root.resolve())
    if args.command == "session":
        print(fixed_session(run, args.new))
    elif args.command == "stage":
        return cmd_stage(run, args.name, args.prompt, args.model, args.effort, args.memory)
    elif args.command == "verification":
        return cmd_verification(run, args.action)
    elif args.command == "loop":
        return cmd_loop(run, options + args.arguments)  # prove-loop.sh's own options, then the examples
    elif args.command == "wait":
        return cmd_wait(run, args.interval, args.timeout)
    elif args.command == "summary":
        return cmd_summary(run)
    elif args.command == "status":
        s = state(run)
        print(json.dumps(s, indent=1) if args.json else render(s, run.read().get("lastSummary"), run.root))
    elif args.command == "interval":
        run.update(interval=args.seconds)
        print(f"a summary every {span(args.seconds)}")
    elif args.command == "merge":
        if args.action != "list" and not args.name:
            ap.error("merge add and merge done take a workspace's name")
        return cmd_merge(run, args.action, args.name)
    elif args.command == "stop-after":
        return cmd_stop_after(run, args.what)
    elif args.command == "proof":
        return cmd_proof(run, args.item, args.timeout)
    return 0


if __name__ == "__main__":
    sys.exit(main())

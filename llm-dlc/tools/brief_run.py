#!/usr/bin/env python3
"""The watcher's tools for the run of a brief (.claude/skills/multi-agent-brief, llm-dlc/README.md "A brief's run").

A brief (llm-dlc/loops/NAME.md) is run by one watcher session, as /prove-java-change runs a proof: the watcher
does none of the work, starts what does, is called back when something needs a judgement, and reports at
intervals. This is what it runs. BRIEF is a brief's name or file, as run-streams.sh takes it.

    brief_run.py preflight BRIEF
        what the run would start (the brief, its streams, their workspaces, sessions and statuses), what stands
        in its way (`blocking`), what to know (`notes`), and the verification runner's budget beside this many
        loops. Exit 1 while anything blocks.
    brief_run.py budget BRIEF [--apply | --restore]
        the runner's budget beside the run's loops, against the file the runner takes it from (this checkout's
        verification/pipeline.local.toml, else the machine's ~/.config/in-the-loop/pipeline.local.toml); --apply lowers the
        file's values to it and keeps the old ones, --restore puts them back when the run has ended.
    brief_run.py foundation BRIEF [--model ID] [--effort LEVEL] [--memory SIZE] [--prompt TEXT]
        the foundation stage: one session (Fable 5.2, high effort) that reads the brief before any stream
        starts, builds whatever all of them would otherwise build or wait for, and updates the plan. It works in
        a workspace of its own, NAME-foundation, so nothing else's uncommitted files meet its commits. Blocks
        until the session ends: run it as a background task. A second call continues the same session.
    brief_run.py land BRIEF
        bring the foundation's commits to the default workspace's line, where the streams start from: moved
        forward when the line has not moved, else a merge with the generated trace files regenerated, and the
        session logs it names (sync.py adopt-logs). A merge that conflicts in real work is taken back and reported.
        Trace output left uncommitted here (`dropped`) is nobody's work and is written again by the next sync.py
        run: it neither holds a merge back nor comes along. Another session's uncommitted files hold a merge back
        until it commits them, and come along on a move forward unless they conflict, which is then taken back.
    brief_run.py start BRIEF
        start run-streams.sh for the brief, detached, with this run's directory as its watcher.
    brief_run.py merge BRIEF STREAM
        merge a finished stream's line (its workspace's @-) into the default workspace's, as `land` does, the
        moment the stream is finished, while the others still run: there is no merge loop. Then it takes the
        stream's session logs (sync.py adopt-logs) and its inbox acknowledgements, answers run-streams.sh's
        `merge` question for it (`merged`), and records the merge in the brief's Progress, whose status it sets
        to `done` once every stream is merged and says done, and commits that. Run again after a merge made by
        hand, it records that merge. A merge that conflicts in real work is taken back and reported.
    brief_run.py start BRIEF [--agent claude|codex] [--stream-agent STREAM=CLIENT ...]
        who carries the streams' turns: Claude Code (the default) or Codex, for the run and for single streams
        (`--agent claude --stream-agent b=codex` is a mixed run, `--agent codex` Codex throughout). The briefs keep
        their models' names; agent_client.py resolves the Codex model for each by the operator's equivalences,
        and the effort is passed on. The choice is recorded with the run and a later `start` keeps it; `preflight`
        and `status` show each stream's client, the model it runs and its effort before a turn is spent, and
        refuse a model with no equivalent, a Codex stream that would fork a Claude Code conversation, and a Codex
        that is not given this checkout's CLAUDE.md. `foundation BRIEF --agent codex` runs the foundation with
        Codex (Astra 6.2 for Fable 5.2). A stream keeps the client its session began with.
    brief_run.py merge BRIEF STREAM --early
        the same merge for a stream that is still at work: its line as committed so far comes in, what its
        session has not committed stays where it is, no question is answered and the brief's status is left
        alone. For a stream whose line another's has to follow (`order`), and to shorten the end of a run.
    brief_run.py trial BRIEF
        merge every pair of the streams' lines, and each with the default line, on trial: nothing is committed
        and no working copy changes. Prints the files each pair conflicts in beyond the generated ones, which
        is what a merge order is decided from, early, while it is cheap.
    brief_run.py order BRIEF [STREAM ...] [--clear]
        the order the streams are merged in, when their lines conflict: `merge` then refuses a stream while one
        before it in the order has commits this line lacks, and names the merge to make first (`--early` for one
        still at work; `merge --out-of-order` overrides). Without streams, prints the order.
    brief_run.py rerun BRIEF STREAM
        run a stream's loop again inside the run: one whose loop has ended, however it ended (a session killed,
        two stops without a status, blocked). run-streams.sh takes the request once the stream's own process
        has ended, clears what the ended loop left in its scope, and looks after the loop as from the start; when
        the run itself has ended, this starts it again for that stream.
    brief_run.py helper BRIEF add NAME --at "tmux TARGET" [--role TEXT]
    brief_run.py helper BRIEF task NAME --title TEXT --file FILE [--no-send]
    brief_run.py helper BRIEF done TASK --report TEXT | --report-file FILE
    brief_run.py helper BRIEF merge TASK
    brief_run.py helper BRIEF list
        helpers: sessions the user has open (each in a tmux pane) that take work the run has no owner for. The
        first is for low-hanging work, small and well bounded; the user may add others for a harder problem (a
        specialist). `task` writes a narrow brief with a stream's standing rules (the watcher's FILE says what
        is asked), puts the helper's workspace, NAME-HELPER, at the default line's last commit (made on first
        use; never from a merge in progress), and types one line into the helper's pane that names the brief.
        The helper commits there and ends with `done`, run from the default workspace's copy of this script;
        `wait` then returns it, and `merge` brings its commits to the default line as `land` does.
    brief_run.py wait BRIEF [--interval SECONDS] [--timeout SECONDS]
        block until something needs the watcher, and print it as JSON: a `question` (a loop ended blocked: rerun
        or leave; a stream is finished: merge it), `attention` (the integration check stopped passing, or a decision is open for the user),
        `results` (results came back and were collected and committed; what is in `attention` is to triage),
        `verification` (jobs waited and no runner was at work: one was started), `helper` (a helper's task is
        done: read its report and merge it), `summary` (every 30 minutes, or `interval`), or `ended`. Exit 3 with nothing after the timeout: wait again. At each look at the queue it
        also records the inbox items the streams' committed Progress acknowledges (inbox.py collect).
    brief_run.py collect BRIEF
        collect the results that are back and commit them, with the paths a commit of results holds and nothing
        else, as `wait` does at each look while the run is under way: the watcher keeps the queue itself. A
        verification loop running here keeps it instead, as it did, and `wait` leaves the results to it.
    brief_run.py verification BRIEF start|stop|status|nudge
        a verification loop (Sonnet sessions that run, collect, triage and commit), as `watch.py verification`,
        recorded with this run: `start` leaves one that is running alone, and `stop` ends the one this run
        started, after its job under way. A run with a watcher needs none.
    brief_run.py interval BRIEF SECONDS
        how often `wait` returns a summary from now on.
    brief_run.py status BRIEF
        where the run stands, as data.
    brief_run.py stop BRIEF [--now]
        stop the run at a boundary: every loop ends after its cycle under way, a loop waiting on jobs stops
        waiting, and no stream is put to the watcher to merge, so nothing is cut off and nothing uncommitted is left. `start`
        continues the run. --now interrupts it instead, mid-cycle: each loop records the interruption.

The run's directory is llm-dlc/loop-summaries/run-streams-NAME/, which run-streams.sh keeps its own state in;
this adds watch.json, the run's output (streams.log), the foundation's stream (foundation.jsonl) and the
questions run-streams.sh asks (events.jsonl, conductor.py). Verdicts are decisions in
llm-dlc/decisions/run-streams-NAME.jsonl.

Standard library only.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import io
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import agent_client
import conductor
import decisions
import doctor
import inbox
import integration
import streams_status
import watch
import landing
import queue_keeping
import run_common
from landing import (INDEX_BEGIN, INDEX_END, TABLE_README, TRACE_FILES, _land, adopt_logs, commit_id, generated,  # noqa: F401
                     is_ancestor, land, merged_in, onto_line, outside_table, regenerable, sync_lock, sync_lock_path,
                     trial_merge, writer)
from queue_keeping import collect, layout, pipeline, queue, start_runner, tend  # noqa: F401
from run_common import SESSION, Problem, codex_ready, jj, loops_in, running, workspaces  # noqa: F401

REPO = Path(__file__).resolve().parents[2]


INTERVAL = 1800
FOUNDATION = {"model": "claude-fable-5-2", "effort": "high"}
# The user's words for the foundation stage (2026-11-17), after a sentence that names the brief.
FOUNDATION_PROMPT = ("This brief was designed for a group of agents, but I'd prefer for you to start work instead. Feel "
                     "free to implement whatever foundation you see fit, maximizing benefits and efficiency, then update "
                     "the brief accordingly for other agents to take over after.")
INTEGRATION_MEMORY, INTEGRATION_CPUS, LOOP_CPUS = 6, 2, 2  # verification/README.md: what a run's parts are given


def setting(path: Path, key: str) -> str:
    """`- key: value` under the brief's `## Loop settings`, with its spaces removed, as run-streams.sh reads it."""
    inside = False
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return ""
    for line in lines:
        if line.startswith("## "):
            inside = re.match(r"^## +Loop settings\s*$", line) is not None
            continue
        m = re.match(rf"^[-*] +{re.escape(key)}: *(.*)$", line)
        if inside and m:
            return re.sub(r"[`\s]", "", m.group(1))
    return ""


def plan(root: Path, brief: str) -> dict:
    """The brief and its streams, as run-streams.sh --plan names them: the one place that knows."""
    r = subprocess.run([str(root / "llm-dlc/tools/run-streams.sh"), "--plan", brief], capture_output=True, text=True, cwd=root)
    if r.returncode != 0:
        raise Problem((r.stderr or r.stdout).strip() or "run-streams.sh --plan failed")
    out = {"streams": []}
    for line in r.stdout.splitlines():
        key, _, value = line.partition(": ")
        if key == "stream":
            label, _, path = value.partition(" ")
            out["streams"].append({"label": label, "brief": path})
        else:
            out[key] = value
    return out


class Run(watch.Run):
    """A brief's run: the directory run-streams.sh keeps its state in, and the watcher's own state there."""

    def __init__(self, root: Path, brief: str):
        self.root = root
        self.plan = plan(root, brief)
        self.name = self.plan["name"]
        self.brief = self.plan["brief"]
        self.dir = root / "llm-dlc" / "loop-summaries" / f"run-streams-{self.name}"
        self.path = self.dir / "watch.json"
        self.stem = Path(self.brief).stem  # the brief file's name: engine-priorities for the run named engines

    @property
    def foundation_workspace(self) -> str:
        return f"{self.name}-foundation"

    @property
    def report(self) -> Path:
        return self.root / "llm-dlc" / "loop-summaries" / f"{self.stem}-integration.md"


# What a run hands the loops it starts, to find its watcher: a session that carries one was started inside a run.
RUN_VARIABLES = ("RUN_STREAMS_WATCHER", "LOOP_CONDUCTOR", "FEATURE_LOOP_RECORD_AS", "FEATURE_LOOP_FIRST", "FEATURE_LOOP_CONTINUE")

# -- before the run

def runner_budget(streams: int, with_integration: bool) -> dict:
    """What is left for the verification runner beside a run's loops (verification/README.md): the machine, less
    the reserve, a cap per loop running at once (each stream, or the brief's own loop when it has none) and the
    integration check's share."""
    m = doctor.machine()
    b = doctor.budget(m)
    loops = max(1, streams)
    total, reserve, loop = m["memory"] // doctor.GIB, float(b["reserve"].rstrip("G")), float(b["loopMemory"].rstrip("G"))
    memory = int(total - reserve - loops * loop - (INTEGRATION_MEMORY if with_integration and streams else 0))
    cpus = m["cpus"] - 2 - LOOP_CPUS * loops - (INTEGRATION_CPUS if with_integration and streams else 0)
    return {"loops": loops, "loopMemory": b["loopMemory"], "memory": f"{max(0, memory)}G", "cpus": max(1, cpus),
            "workers": max(1, min(max(1, cpus) // 2, max(0, memory) // 4))}


LOCAL = "verification/pipeline.local.toml"
BUDGET_KEYS = ("workers", "cpus", "memory")


def machine_config() -> Path | None:
    """The machine's runner settings, read by every workspace (verification/pipeline.py's machine_config)."""
    named = os.environ.get("VERIFY_MACHINE_CONFIG")
    if named is not None:
        return Path(named) if named else None
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "in-the-loop" / "pipeline.local.toml"


def file_budget(path: Path | None) -> dict:
    """The [runner] values a settings file sets, of the three the budget names."""
    out, section = {}, None
    try:
        lines = path.read_text().splitlines() if path else []
    except OSError:
        return out
    for line in lines:
        if m := re.match(r"^\[([^\]]+)\]", line):
            section = m[1]
        elif section == "runner" and (m := re.match(r'^(workers|cpus|memory)\s*=\s*"?([^"#\s]+)"?', line)):
            out[m[1]] = m[2]
    return out


def budget_file(root: Path) -> Path:
    """The file the runner takes its budget from: this checkout's verification/pipeline.local.toml when it sets one,
    which outranks the machine's, else the machine's file (pipeline.py reads both)."""
    own, machine = root / LOCAL, machine_config()
    if file_budget(own) or not (machine and machine.exists()):
        return own
    return machine


def local_budget(root: Path) -> dict:
    """The [runner] values the runner's budget file sets (budget_file), of the three the budget names."""
    return file_budget(budget_file(root))


def gib(text) -> float:
    m = re.fullmatch(r"([0-9.]+)\s*([GM]?)", str(text))
    return float(m[1]) / (1024 if m[2] == "M" else 1) if m else 0.0


def over_budget(have: dict, want: dict) -> list[str]:
    """The values the file sets higher than the budget, each as `key HAVE > WANT`."""
    out = []
    for key in BUDGET_KEYS:
        if key not in have:
            continue
        over = gib(have[key]) > gib(want[key]) if key == "memory" else int(have[key]) > int(want[key])
        if over:
            out.append(f"{key} {have[key]} > {want[key]}")
    return out


def write_budget(root: Path, values: dict) -> None:
    path = budget_file(root)
    lines, section, left = path.read_text().splitlines(), None, dict(values)
    for i, line in enumerate(lines):
        if m := re.match(r"^\[([^\]]+)\]", line):
            section = m[1]
        elif section == "runner" and (m := re.match(r"^(workers|cpus|memory)(\s*=\s*)", line)) and m[1] in left:
            value = left.pop(m[1])
            comment = re.search(r"\s+#.*$", line)
            lines[i] = f'{m[1]}{m[2]}{json.dumps(value) if m[1] == "memory" else int(value)}{comment[0] if comment else ""}'
    if left:
        raise Problem(f"{path} sets no [runner] {', '.join(left)}: add them by hand, as verification/README.md shows")
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines) + "\n")
    os.replace(tmp, path)


def cmd_budget(run: Run, apply: bool, restore: bool) -> int:
    want = runner_budget(len(run.plan["streams"]), bool(setting(run.root / run.brief, "integration")))
    have = local_budget(run.root)
    kept = run.read().get("budgetBefore")
    if restore:
        if not kept:
            print("this run changed no budget")
            return 0
        write_budget(run.root, kept)
        run.update(budgetBefore=None)
        print(f"{budget_file(run.root)} has its values of before the run again: {kept}. A runner at work keeps its budget until its run ends.")
        return 0
    over = over_budget(have, want)
    if apply and over:
        run.update(budgetBefore=kept or {k: have[k] for k in BUDGET_KEYS if k in have})
        write_budget(run.root, {k: want[k] for k in BUDGET_KEYS if k in have})
        print(f"lowered in {budget_file(run.root)}: {'; '.join(over)}. A runner at work keeps its budget until its run ends: "
              f"`brief_run.py budget {run.name} --restore` puts the old values back after the run.")
        return 0
    print(json.dumps({"beside": f"{want['loops']} loop(s) of {want['loopMemory']}", "runner": {k: want[k] for k in BUDGET_KEYS},
                      "file": have or None, "over": over}, indent=1))
    return 0


def preflight(run: Run) -> dict:
    root, blocking, notes = run.root, [], []
    known = workspaces(root)
    main = root / run.brief
    if known.get("default") is None or known["default"].resolve() != root.resolve():
        blocking.append(f"a brief is run from the default workspace, and {root} is not it")
    out = {"name": run.name, "brief": run.brief, "status": streams_status.brief_status(main) or None,
           "session": setting(main, "session") or None, "model": setting(main, "model") or None,
           "integration": setting(main, "integration") or None,
           "verification": setting(main, "verification") or "with the pipeline", "streams": []}
    if not out["status"]:
        blocking.append(f"{run.brief} has no `- Status:` line at the end of its Progress: run-streams.sh reads it to tell a finished loop from a stopped one")
    if out["integration"] and not os.access(root / out["integration"], os.X_OK):
        blocking.append(f"the brief's integration script {out['integration']} is not an executable file here")
    names, forks, sessions = {}, set(), {out["session"]: run.brief}
    if not SESSION.fullmatch(out["session"] or ""):
        blocking.append(f"{run.brief} has no `- session: UUID` in its Loop settings (a new one: `python3 -c 'import uuid; print(uuid.uuid4())'`)")
    for s in run.plan["streams"]:
        path = root / s["brief"]
        row = {**s, "workspace": setting(path, "workspace") or None, "session": setting(path, "session") or None,
               "model": setting(path, "model") or None, "fork": setting(path, "fork") or None}
        out["streams"].append(row)
        if not path.is_file():
            blocking.append(f"the stream {s['label']} has no brief: {s['brief']}")
            continue
        row["client"] = client_of(run, s["label"], path)
        row["effort"] = setting(path, "effort") or LOOP_DEFAULTS["effort"]
        try:
            row["runs"] = agent_client.plan(row["client"], row["model"] or LOOP_DEFAULTS["model"], row["effort"])["model"]
        except agent_client.Problem as e:
            blocking.append(f"the stream {s['label']} ({row['client']}): {e}")
        if row["client"] == "codex" and row["fork"]:
            blocking.append(f"the stream {s['label']} is Codex's and its brief says `- fork: {row['fork']}`: Codex cannot continue "
                            f"a Claude Code conversation. Take the fork out of {s['brief']} (the brief and its inbox are the "
                            f"handoff both clients read), or give the stream to Claude Code")
        forks.add(row["fork"])
        if not SESSION.fullmatch(row["session"] or ""):
            blocking.append(f"{s['brief']} has no `- session: UUID` in its Loop settings: without one it would share the loops' default session")
        elif row["session"] in sessions:
            blocking.append(f"{s['brief']} names the session of {sessions[row['session']]}: each loop has its own")
        else:
            sessions[row["session"]] = s["brief"]
        ws = row["workspace"]
        if not ws:
            blocking.append(f"{s['brief']} has no `- workspace:` in its Loop settings")
        elif ws in names or ws in ("default", f"{run.name}-integration", run.foundation_workspace):
            blocking.append(f"{s['brief']} names workspace {ws}, which {names.get(ws, 'the run')} has")
        else:
            names[ws] = s["label"]
            folder = known.get(ws) or root.parent / f"{root.name}-{ws}"
            row["folder"], row["exists"] = str(folder), ws in known
            if ws not in known and folder.exists():
                blocking.append(f"{folder} already exists, but no jj workspace is at it: delete it, or name another workspace in {s['brief']}")
            # its own copy's status once it has a workspace: the default workspace's copy is not the one it edits
            row["status"] = streams_status.brief_status((folder if ws in known else root) / s["brief"]) or None
            if not row["status"]:
                blocking.append(f"{s['brief']} has no `- Status:` line at the end of its Progress")
    if any(row.get("client") == "codex" for row in out["streams"]):
        blocking += codex_ready(root)
    out["agents"] = agents(run) or None
    if len(forks) > 1:
        blocking.append("the streams fork different sessions: all the same one, or none")
    for fork in forks - {None}:
        if not watch.transcript(root, fork).exists():
            blocking.append(f"the streams fork session {fork}, which has no transcript in this checkout")
    if pids := running(root, "run-streams.sh"):
        blocking.append(f"a run of streams is already under way for this repository (pid {pids[0]}): two would share the "
                        f"default workspace and the machine's budget")
    elif pids := loops_in(root):
        blocking.append(f"a loop is at work in the default workspace (pid {pids[0]}; a proof run's, or a brief's own): the "
                        f"brief's own loop would commit into its work. Start once it has ended")
    carried = sorted(k for k in os.environ if k in RUN_VARIABLES or k.startswith("LOOP_WATCH_"))
    if carried:
        blocking.append(f"this session's environment holds a run's own variables ({', '.join(carried[:6])}): it was started "
                        f"inside a loop or another run, and a run started from it would hand them on to its streams, "
                        f"whose tests of these scripts would then ask the real watcher their made-up questions. Watch "
                        f"from a session started outside any loop")
    dirty = jj(root, "diff", "-r", "@", "--name-only").stdout.split()
    if dirty:
        notes.append(f"the default workspace has uncommitted changes ({len(dirty)} files, {dirty[0]} first): another "
                     f"session's, or yours to commit before the run")
    budget = runner_budget(len(run.plan["streams"]), bool(out["integration"]))
    over = over_budget(local_budget(root), budget)
    if over:
        notes.append(f"{budget_file(run.root)} gives the runner more than is left beside {budget['loops']} loop(s): {'; '.join(over)}. "
                     f"`brief_run.py budget {run.name} --apply` lowers it for the run")
    foundation = run.read().get("foundation") or {}
    out.update(foundation={k: foundation.get(k) for k in ("session", "ended", "ok", "commit", "landed", "cost")} if foundation else None,
               budget=budget, blocking=blocking, notes=notes)
    return out


LOOP_DEFAULTS = {"model": "claude-fable-5-1", "effort": "high"}  # feature-loop.sh's, for a brief that names none


def agents(run: Run) -> dict:
    """The run's choice of client: {"default": CLIENT, "streams": {LABEL: CLIENT}}, as `start` recorded it."""
    return dict(run.read().get("agents") or {})


def client_of(run: Run, label: str, brief: Path | None = None) -> str:
    """Who carries a stream's turns: the run's word for the stream, else the run's for all, else the brief's own
    `- client:` setting, else Claude Code. feature-loop.sh takes them in the same order."""
    chosen = agents(run)
    return ((chosen.get("streams") or {}).get(label) or chosen.get("default")
            or (setting(brief, "client") if brief else "") or "claude")


def set_agents(run: Run, agent: str | None, stream_agents: list[str]) -> None:
    chosen = agents(run)
    streams = dict(chosen.get("streams") or {})
    known = [s["label"] for s in run.plan["streams"]] or ["brief"]
    for pair in stream_agents:
        label, _, client = pair.partition("=")
        if label not in known or client not in agent_client.CLIENTS:
            raise Problem(f"--stream-agent takes STREAM=CLIENT, a stream of {', '.join(known)} and one of "
                          f"{', '.join(agent_client.CLIENTS)}: {pair!r}")
        streams[label] = client
    if agent or stream_agents:
        run.update(agents={"default": agent or chosen.get("default") or "claude", "streams": streams})


def cmd_preflight(run: Run) -> int:
    out = preflight(run)
    print(json.dumps(out, indent=1))
    return 1 if out["blocking"] else 0


# -- the foundation stage

def foundation_prompt(run: Run, text: str | None) -> str:
    briefs = [s["brief"] for s in run.plan["streams"]]
    named = f"The brief is `{run.brief}`" + (
        f", with its streams' briefs beside it ({', '.join(f'`{b}`' for b in briefs)})." if briefs else ".")
    return (f"{named} {text or FOUNDATION_PROMPT} You are the only session at work on it until you end: the "
            f"streams start afterwards, each in a workspace of its own made from your last commit, so what you "
            f"commit is what they begin with. Commit as CLAUDE.md describes, queue what CLAUDE.md says is "
            f"queued, and end with a short report: what you built, what you changed in the plan, and what each "
            f"stream should know before its first cycle.")


def cmd_foundation(run: Run, model: str | None, effort: str | None, memory: str | None, prompt: str | None,
                   agent: str | None = None) -> int:
    if refusal := watch.nested_run_refusal(f"brief_run.py foundation {run.name}"):
        raise Problem(refusal)
    known = workspaces(run.root)
    ws = run.foundation_workspace
    folder = known.get(ws) or run.root.parent / f"{run.root.name}-{ws}"
    if ws not in known:
        if folder.exists():
            raise Problem(f"{folder} already exists, but no jj workspace is at it: delete it first")
        r = jj(run.root, "workspace", "add", "--name", ws, "-r", "@-", str(folder))
        if r.returncode != 0:
            raise Problem(f"could not add the workspace {ws}: {r.stderr.strip()}")
        # the session logs the default workspace stores and has not uploaded: without them every commit's check
        # in the new workspace reports each as an error, which the session would then try to fix
        subprocess.run([sys.executable, "llm-dlc/tools/sync.py", "adopt-logs"], cwd=folder, capture_output=True, text=True)
    before = run.read().get("foundation") or {}
    session = before.get("session") or str(uuid.uuid4())
    # The session keeps the client it began with; a new one takes the stage's word, else the run's.
    client = before.get("client") or agent or agents(run).get("default") or "claude"
    if agent and agent != client:
        raise Problem(f"the foundation session {session} is {client}'s: a session keeps its client")
    try:
        resolved = agent_client.plan(client, model or FOUNDATION["model"], effort or FOUNDATION["effort"])
    except agent_client.Problem as e:
        raise Problem(str(e))
    if client == "codex":
        for problem in codex_ready(folder):
            raise Problem(problem)
        command = [sys.executable, str(Path(agent_client.__file__).resolve()), "run", "--client", "codex", "--session", session,
                   "--model", resolved["model"], "--effort", resolved["effort"], "--cwd", str(folder), foundation_prompt(run, prompt)]
    else:
        command = ["claude", "-p", foundation_prompt(run, prompt), "--model", model or FOUNDATION["model"],
                   "--effort", effort or FOUNDATION["effort"],
                   *(["--resume", session] if watch.transcript(folder, session).exists() else ["--session-id", session]),
                   "--permission-mode", "auto", "--output-format", "stream-json", "--verbose"]
    memory = memory or doctor.budget(doctor.machine())["loopMemory"]
    if memory != "none":  # a scope named as a loop's, so whoever shares the machine out counts it as one
        command = ["systemd-run", "--user", "--scope", "--quiet", "--collect", f"--unit=feature-loop-{ws}",
                   "-p", f"MemoryMax={memory}", "-p", "MemorySwapMax=0", "-p", "OOMPolicy=continue", *command]
    run.dir.mkdir(parents=True, exist_ok=True)
    log = run.dir / "foundation.jsonl"
    started = conductor.now()
    base = watch.head_change(folder)
    run.update(foundation={"session": session, "client": client, "runs": resolved["model"], "effort": resolved["effort"],
                           "workspace": ws, "folder": str(folder), "started": started, "log": str(log),
                           "offset": log.stat().st_size if log.exists() else 0, "attempt": before.get("attempt", 0) + 1})
    result = None
    with open(log, "a") as out:
        p = subprocess.Popen(command, cwd=folder, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True)
        run.update(foundation={**run.read()["foundation"], "pid": p.pid})
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
    head = watch.head_change(folder)
    ok = status == 0 and bool(result) and result.get("subtype") == "success"
    dirty = jj(folder, "diff", "-r", "@", "--name-only").stdout.split()
    record = {**run.read()["foundation"], "ended": conductor.now(), "ok": ok, "exit": status, "commit": head,
              "committed": head != base, "uncommitted": dirty[:20],
              "cost": watch.turn_cost(run, session, (result or {}).get("total_cost_usd"), fresh=not before)}
    record.pop("pid", None)
    report = (result or {}).get("result") or before.get("report")
    run.update(foundation={**record, "report": report})
    print(json.dumps({**record, "report": report,
                      "next": ("it left uncommitted files in its workspace: run the stage again to have them finished and committed"
                               if dirty else f"`brief_run.py land {run.name}` brings its commits to the line the streams start from"
                               if head != base else "it committed nothing: read its report before going on")}, indent=1))
    return 0 if ok else 1


REPORT_LIMIT = 6000  # characters of the foundation's report an inbox item carries: an inbox is read every cycle


def hand_off(run: Run) -> list[str]:
    """Tell each stream what the foundation left, once, as an item in its inbox (inbox.py, kind `foundation`):
    the stage's own closing report and its commit. A stream reads its inbox every cycle and acknowledges the item
    in its Progress, so what was built for it is known to have reached it, where an edited brief alone is not."""
    foundation = run.read().get("foundation") or {}
    report, told = (foundation.get("report") or "").strip(), list(foundation.get("handedOff") or [])
    if not report or not foundation.get("committed"):
        return []
    if len(report) > REPORT_LIMIT:
        report = report[:REPORT_LIMIT].rstrip() + " […] (cut here: the whole report is in " + str(
            Path(foundation.get("log", "the run's foundation.jsonl")).name) + " of the run's directory)"
    change = (foundation.get("commit") or "").split(" ")[0]
    sent = []
    for s in run.plan["streams"]:
        name = Path(s["brief"]).stem
        if name in told or not (run.root / s["brief"]).is_file():
            continue
        inbox.send(name, "foundation",
                   "Before your first piece of work, read what the foundation stage built for this run and build on "
                   "it: use what it left, don't build it again, and say in Progress if something it left is wrong "
                   "or in your way.",
                   detail=report, commits=[change] if change else [], folder=run.root / inbox.FOLDER,
                   decisions_root=run.root / "llm-dlc" / "decisions", repo=run.root)
        sent.append(name)
    if sent:
        run.update(foundation={**run.read()["foundation"], "handedOff": told + sent})
    return sent


def cmd_land(run: Run) -> int:
    ws = run.foundation_workspace
    out = land(run, ws, (f"Merge the foundation of the {run.name} run into the line",
                         f"The foundation stage of the brief {run.brief} ran in the workspace {ws} while this line "
                         f"moved on, so its commits come in by a merge. Nothing but the generated trace files met; they "
                         f"were regenerated from the session files."))
    if run.read().get("foundation"):
        run.update(foundation={**run.read()["foundation"], "landed": out["commit"]})
        out["handedOff"] = hand_off(run)
    print(json.dumps(out, indent=1))
    return 0


# -- merging a finished stream

def stream_of(run: Run, label: str) -> dict:
    for s in preflight(run)["streams"]:
        if s["label"] == label:
            if not s.get("exists"):
                raise Problem(f"the stream {label} has no workspace yet ({s['workspace']}): nothing to merge")
            return s
    raise Problem(f"{run.brief} names no stream {label}: its streams are "
                  f"{', '.join(s['label'] for s in run.plan['streams']) or 'none'}")


STATUS_LINE = re.compile(r"^[-*] +Status: *(.*)$")


def record_merge(text: str, line: str, status: str) -> str:
    """The brief with LINE added to its Progress, before its last `- Status:` line, which becomes STATUS (one is
    added at the section's end when there is none)."""
    lines, start = text.split("\n"), None
    for i, raw in enumerate(lines):
        if raw.startswith("## "):
            if start is not None:
                end = i
                break
            if re.match(r"^## +Progress\s*$", raw):
                start = i
    else:
        end = len(lines)
    if start is None:
        raise Problem("the brief has no ## Progress section to record the merge in")
    at = next((i for i in range(end - 1, start, -1) if STATUS_LINE.match(lines[i])), None)
    if at is None:
        at = end
        while at - 1 > start and not lines[at - 1].strip():
            at -= 1
        lines[at:at] = [f"- Status: {status}"]
    else:
        lines[at] = f"- Status: {status}"
    lines[at:at] = [line]
    return "\n".join(lines)


def brief_status_after(run: Run, check: dict) -> str:
    """The brief's status once a stream is merged: done when every stream is merged and says done, blocked
    with what each blocked one says when every stream is merged, else working."""
    rows = []
    for s in check["streams"]:
        folder = Path(s["folder"])
        merged = s.get("exists") and merged_in(run.root, s["workspace"])
        rows.append((s["label"], merged, streams_status.brief_status(folder / s["brief"]) if s.get("exists") else None))
    if not all(m for _, m, _ in rows) or any((status or "").startswith(("working", "waiting")) for _, _, status in rows):
        return "working"  # a stream not merged, or one merged early that is still at work
    blocked = [f"stream {label}: {status}" for label, _, status in rows if not (status or "").startswith("done")]
    return "done" if not blocked else "blocked: " + "; ".join(blocked)


def commit_own_record(run: Run) -> None:
    """Commit the run's decision record when it has changed: the watcher's own answers (conductor.py decide writes
    them and commits nothing) and the user's (decisions.py answer, which another session may have run for them
    here). The watcher is the session that commits in this working copy while a run is under way, so it commits
    both, under a message that says so: until 2026-11-18 only a merge did, and a user's answer left uncommitted
    went into the next commit of results under that commit's message."""
    own = [f"llm-dlc/decisions/{run.dir.name}.jsonl", f"llm-dlc/decisions/{run.dir.name}.md"]
    dirty = jj(run.root, "diff", "-r", "@", "--name-only").stdout.split()
    mine = [f for f in dirty if f in own]
    if not mine:
        return
    r = subprocess.run([sys.executable, str(run.root / "llm-dlc" / "tools" / "sync.py"), "commit", "--only", *mine,
                        "-m", f"Record the decisions of the {run.name} run",
                        "-m", f"The run's decision record as it stands: what the watcher of the brief {run.brief} decided "
                              f"while it ran, and what the user answered (decisions.py answer). The watcher commits the "
                              f"record whenever it has changed, since it is the session that commits in this working copy "
                              f"during a run."],
                       cwd=run.root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise Problem(f"could not commit the run's decision record first: {(r.stderr or r.stdout).strip()[-600:]}")


def cmd_merge(run: Run, label: str, early: bool = False, out_of_order: bool = False) -> int:
    with writer(run.root):
        return merge(run, label, early, out_of_order)


def before_in_order(run: Run, label: str) -> list[dict]:
    """The streams the run's merge order puts before LABEL whose lines hold commits the default line lacks: each
    with whether its loop is finished, which says how it is merged first."""
    order = run.read().get("mergeOrder") or []
    if label not in order:
        return []
    rows = {s["label"]: s for s in preflight(run)["streams"]}
    out = []
    for other in order[:order.index(label)]:
        s = rows.get(other)
        if s and s.get("exists") and not merged_in(run.root, s["workspace"]):
            status = streams_status.brief_status(Path(s["folder"]) / s["brief"]) or ""
            finished = status.startswith(("done", "blocked"))
            out.append({"stream": other, "status": status or "no status",
                        "merge": f"python3 llm-dlc/tools/brief_run.py merge {run.name} {other}" + ("" if finished else " --early")})
    return out


def merge(run: Run, label: str, early: bool = False, out_of_order: bool = False) -> int:
    s = stream_of(run, label)
    workspace, root = s["workspace"], run.root
    head = jj(root, "log", "--no-graph", "-r", f"{workspace}@-", "-T", "change_id.short(12)", snapshot=False).stdout.strip()
    status = streams_status.brief_status(Path(s["folder"]) / s["brief"]) or "no status"
    first = before_in_order(run, label)
    if first and not out_of_order:
        raise Problem(f"the run's merge order ({', '.join(run.read()['mergeOrder'])}) puts {', '.join(f['stream'] for f in first)} "
                      f"before {label}, with commits this line lacks: first " + "; then ".join(f"`{f['merge']}`" for f in first)
                      + f". `merge {run.name} {label} --out-of-order` merges it anyway")
    if early and status.startswith(("done", "blocked")):
        early = False  # it is finished: the merge is its merge
    commit_own_record(run)
    if early:
        out = land(run, workspace, (f"Merge stream {label}'s line so far into the line, while it is still at work",
                                    f"The stream {label} of the brief {run.brief} is still at work ({status}). The run's watcher "
                                    f"merges what it has committed so far ({head}), so that the lines that have to follow it "
                                    f"can come in and the end of the run has less to merge; what its session has not committed "
                                    f"stays in its workspace {workspace}, and its later commits come in by its next merge. "
                                    f"Nothing but the generated trace files met; they were regenerated from the session files."),
                   at_work=True)
        line = f"merged stream {label}'s line so far ({head}), while it is still at work"
        text = (root / run.brief).read_text()
        if line not in text and not out["landed"].startswith("nothing"):
            brief = root / run.brief
            brief.write_text(record_merge(text, f"- {conductor.now()[:10]}, the watcher: {line}.",
                                          streams_status.brief_status(brief) or "working"))
            r = subprocess.run([sys.executable, str(root / "llm-dlc" / "tools" / "sync.py"), "commit", "--only", run.brief,
                                "-m", f"Record the early merge of stream {label} in the {run.name} brief's Progress",
                                "-m", f"The run's watcher merged stream {label}'s line so far ({head}) into the default line "
                                      f"while the stream is still at work; the brief's status is unchanged."],
                               cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
            if r.returncode != 0:
                raise Problem(f"the line is merged, but recording it reported: {(r.stderr or r.stdout).strip()[-600:]}")
        out.update(early=True, stream=label, head=head, commit=watch.head_change(root),
                   note="its later commits come in by its next merge, which it is put to you for when it is finished")
        print(json.dumps(out, indent=1))
        return 0
    out = land(run, workspace, (f"Merge stream {label} of the {run.name} run into the line",
                                f"The stream {label} of the brief {run.brief} is finished ({status}), and the run's watcher "
                                f"merges each stream the moment it is, while the others still run. Its workspace "
                                f"{workspace} branched from this line, which moved on, so its commits come in by a merge. "
                                f"Nothing but the generated trace files met; they were regenerated from the session files."))
    try:
        out["acknowledged"] = inbox.collect(Path(s["brief"]).stem, root / inbox.FOLDER, root)
    except inbox.InboxError as e:
        out["acknowledged"] = f"not read: {e}"
    event = next((e for e in reversed(conductor.read_events(run.dir)) if e.get("type") == "merge" and e.get("loop") == label
                  and e.get("needsVerdict") and conductor.read_verdict(run.dir, e["n"]) is None), None)
    if event is not None:
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            conductor.cmd_decide(run.dir, event["n"], "merged",
                                 f"The stream {label} is finished ({status}), and its line ({head}) is merged into the "
                                 f"default line: {out['landed']}.")
        out["answered"] = " ".join(said.getvalue().split())
    brief = root / run.brief
    text = brief.read_text()
    if f"merged stream {label} ({head})" not in text:
        new_status = brief_status_after(run, preflight(run))
        brief.write_text(record_merge(text, f"- {conductor.now()[:10]}, the watcher: merged stream {label} ({head}), which "
                                            f"says {status}.", new_status))
        sync = root / "llm-dlc" / "tools" / "sync.py"
        paths = [run.brief] + (["llm-dlc/decisions"] if (root / "llm-dlc" / "decisions").is_dir() else [])
        r = subprocess.run([sys.executable, str(sync), "commit", "--only", *paths,
                            "-m", f"Record the merge of stream {label} in the {run.name} brief's Progress",
                            "-m", f"The run's watcher merged stream {label} ({head}) into the default line; the brief's "
                                  f"status is now {new_status}."],
                           cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise Problem(f"the stream is merged, but recording it reported: {(r.stderr or r.stdout).strip()[-600:]}")
        out["briefStatus"] = new_status
    out["commit"] = watch.head_change(root)
    # what the order held back behind this stream and is finished: its turn has come
    order = run.read().get("mergeOrder") or []
    due = []
    for other in order[order.index(label) + 1:] if label in order else []:
        o = next((x for x in preflight(run)["streams"] if x["label"] == other), None)
        if (o and o.get("exists") and not merged_in(root, o["workspace"]) and not before_in_order(run, other)
                and (streams_status.brief_status(Path(o["folder"]) / o["brief"]) or "").startswith(("done", "blocked"))):
            due.append(f"python3 llm-dlc/tools/brief_run.py merge {run.name} {other}")
    if due:
        out["nowDue"] = due
    print(json.dumps(out, indent=1))
    return 0


# -- a trial merge, and the order it gives


INVENTORY = "lib/tests/costs.json"  # rewritten by every stream that adds a test: it is regenerated, not resolved


def trial(run: Run) -> dict:
    root = run.root
    lines = {"the default line": commit_id(root, "@-")}
    for s in preflight(run)["streams"]:
        if s.get("exists"):
            lines[s["label"]] = commit_id(root, f"{s['workspace']}@-")
    names, pairs = list(lines), []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if is_ancestor(root, lines[a], lines[b]) or is_ancestor(root, lines[b], lines[a]):
                pairs.append({"a": a, "b": b, "conflicts": [], "note": "one holds the other: nothing to merge"})
                continue
            files = trial_merge(root, lines[a], lines[b])
            real = [f for f in files if not generated(f) and f != INVENTORY]
            pairs.append({"a": a, "b": b, "conflicts": real,
                          **({"regenerated": sorted(set(files) - set(real))} if set(files) - set(real) else {})})
    meet = [p for p in pairs if p["conflicts"]]
    return {"lines": {k: v[:12] for k, v in lines.items()}, "pairs": pairs, "order": run.read().get("mergeOrder") or None,
            "note": ("no two lines conflict in real work: each stream is merged the moment it is finished, in any order"
                     if not meet else
                     f"{len(meet)} pair(s) conflict in real work. Tell the streams concerned through their inboxes, and "
                     f"propose a merge order to the user (`brief_run.py order {run.name} STREAM ...`): the stream whose "
                     f"change the other has to build on first, and each later one merges the default line into its own "
                     f"before it is finished. A stream ahead in the order is merged while it still runs (`merge ... --early`), "
                     f"so that nothing finished waits for it")}


def cmd_order(run: Run, streams: list[str], clear: bool) -> int:
    known = [s["label"] for s in run.plan["streams"]]
    if clear:
        run.update(mergeOrder=[])
    elif streams:
        unknown = [x for x in streams if x not in known]
        if unknown or len(set(streams)) != len(streams):
            raise Problem(f"a merge order names each stream once at most, of {', '.join(known) or 'none'}: {' '.join(streams)}")
        run.update(mergeOrder=streams)
    order = run.read().get("mergeOrder") or []
    print(json.dumps({"order": order or None, "unordered": [k for k in known if k not in order],
                      "note": "a stream is merged once every stream before it in the order has its commits on this line; "
                              "a stream the order does not name is merged whenever it is finished"}, indent=1))
    return 0


# -- a stream run again inside the run

def cmd_rerun(run: Run, label: str) -> int:
    if refusal := watch.nested_run_refusal(f"brief_run.py rerun {run.name}"):
        raise Problem(refusal)
    s = stream_of(run, label)
    folder = Path(s["folder"])
    at_work = loops_in(folder)
    if at_work:
        raise Problem(f"the stream {label}'s loop is at work (pid {at_work[0]}): there is nothing to run again")
    request = run.dir / "rerun" / label
    request.parent.mkdir(parents=True, exist_ok=True)
    request.write_text(conductor.now() + "\n")
    out = {"stream": label, "status": streams_status.brief_status(folder / s["brief"]) or "no status",
           "phase": streams_status.read(run.dir / f"{label}.phase") or None}
    if watch.alive((run.read().get("run") or {}).get("pid")):
        asked = conductor.pending(run.dir)
        asked = asked if asked and asked.get("loop") == label and asked.get("type") != "ended" else None
        out["next"] = ("run-streams.sh starts its loop again within seconds: it clears what the ended loop left in its "
                       "scope first, and puts the stream to you to merge when it is finished")
        if asked:
            out["next"] = (f"its {asked['type']} question (event {asked['n']}) is still open, and run-streams.sh starts the loop "
                           f"again once that is answered: `python3 llm-dlc/tools/conductor.py decide "
                           f"{run.dir.relative_to(run.root)} {asked['n']} {'|'.join(conductor.answers(asked))} --reason TEXT`")
        print(json.dumps(out, indent=1))
        return 0
    out["next"] = "the run itself had ended: started again, for this stream"
    print(json.dumps(out, indent=1))
    return cmd_start(run)


# -- helpers: sessions the user has open, for work the run has no owner for

SHELLS = ("bash", "zsh", "sh", "fish", "dash", "ksh")
FIRST_ROLE = "low-hanging work: small, well-bounded pieces that no stream of the run owns"
LATER_ROLE = "what the user added it for (a harder problem, a specialist): ask them when it is not clear"


def tmux(*args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["tmux", *args], capture_output=True, text=True)
    except OSError as e:
        return subprocess.CompletedProcess(args, 127, "", f"tmux: {e.strerror}")


def pane_of(at: str) -> dict:
    """The tmux pane a helper is in, from the user's word for it ("tmux 3": window 3 of this session)."""
    m = re.fullmatch(r"\s*tmux\s+(\S+)\s*", at)
    if not m:
        raise Problem(f'a helper is named by its tmux window or pane, as "tmux 3": {at!r}')
    r = tmux("display-message", "-p", "-t", m[1], "#{pane_id}\t#{session_name}:#{window_index}.#{pane_index}\t#{pane_current_command}")
    if r.returncode != 0 or r.stdout.count("\t") != 2:
        raise Problem(f"no tmux pane at {m[1]} ({(r.stderr or r.stdout).strip() or 'tmux said nothing'})")
    pane, where, command = r.stdout.rstrip("\n").split("\t")
    return {"pane": pane, "where": where, "command": command}


def done_file(run: Run, task_id: str) -> Path:
    return run.dir / "helpers" / f"{task_id}.done.json"


def helpers(run: Run) -> dict:
    """The run's helpers and their tasks. That a task is done is the helper's to say, from its own session, and it
    says it in a file of its own (`done`): the run's state file is rewritten whole by the watcher's `wait`, and a
    second writer's change could be lost between its read and its write."""
    out = dict(run.read().get("helpers") or {})
    for h in out.values():
        for task in h.get("tasks") or []:
            if "done" not in task:
                try:
                    task.update(json.loads(done_file(run, task["id"]).read_text()))
                except (OSError, ValueError):
                    pass
    return out


def helper_workspace(run: Run, name: str) -> str:
    return f"{run.name}-{name}"


def tasks_of(run: Run) -> dict[str, tuple[str, dict]]:
    return {t["id"]: (name, t) for name, h in helpers(run).items() for t in h.get("tasks") or []}


def save_task(run: Run, name: str, task: dict) -> None:
    all_ = helpers(run)
    h = all_[name]
    h["tasks"] = [t for t in h.get("tasks") or [] if t["id"] != task["id"]] + [task]
    h["tasks"].sort(key=lambda t: t["id"])
    run.update(helpers=all_)


def cmd_helper_add(run: Run, name: str, at: str, role: str | None) -> int:
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,23}", name):
        raise Problem(f"a helper's name is lower-case letters, digits and dashes: {name!r}")
    all_ = helpers(run)
    pane = pane_of(at)
    if pane["command"] in SHELLS:
        raise Problem(f"the pane {pane['where']} is at a shell prompt ({pane['command']}), not in a session: what is typed "
                      f"there would be run as a command. Open the helper's Claude Code session in it first")
    taken = next((n for n, h in all_.items() if h["pane"] == pane["pane"] and n != name), None)
    if taken:
        raise Problem(f"the pane {pane['where']} is the helper {taken}'s")
    before = all_.get(name) or {}
    all_[name] = {**before, "at": at.strip(), **pane, "role": role or before.get("role") or (FIRST_ROLE if not [n for n in all_ if n != name] else LATER_ROLE),
                  "workspace": helper_workspace(run, name), "added": before.get("added") or conductor.now(),
                  "tasks": before.get("tasks") or []}
    run.update(helpers=all_)
    print(json.dumps({"helper": name, **{k: all_[name][k] for k in ("at", "where", "command", "role", "workspace")},
                      "note": "it takes a task with `helper BRIEF task NAME --title ... --file ...`: one at a time, each merged "
                              "before the next"}, indent=1))
    return 0


def helper_folder(run: Run, name: str) -> Path:
    """The helper's workspace, at the default line's last commit: made on first use, and for a later task moved
    there once its last one is merged and nothing uncommitted is left in it."""
    root, ws = run.root, helper_workspace(run, name)
    heads = jj(root, "log", "--no-graph", "-r", "@-", "-T", 'commit_id ++ "\n"').stdout.split()
    if len(heads) != 1:
        raise Problem("the default workspace is in the middle of a merge (its working copy has two parents): commit the "
                      "merge first, so the helper starts from the line's one last commit")
    known = workspaces(root)
    if ws not in known:
        folder = root.parent / f"{root.name}-{ws}"
        if folder.exists():
            raise Problem(f"{folder} already exists, but no jj workspace is at it: delete it first")
        r = jj(root, "workspace", "add", "--name", ws, "-r", heads[0], str(folder))
        if r.returncode != 0:
            raise Problem(f"could not add the workspace {ws}: {r.stderr.strip()}")
        adopt_logs(folder)
        return folder
    folder = known[ws]
    if folder is None or not folder.is_dir():
        raise Problem(f"jj knows the workspace {ws} but not its folder")
    dirty = [f for f in jj(folder, "diff", "-r", "@", "--name-only").stdout.splitlines() if f.strip()]
    left = [f for f in dirty if not regenerable(folder, f)]
    if left:
        raise Problem(f"the helper's workspace {ws} has uncommitted files ({', '.join(left[:5])}): its last task is not "
                      f"finished, or they are to be committed or discarded by the helper first")
    if dirty:
        jj(folder, "restore", "--", *dirty)  # trace output only: sync.py writes it again
    if not merged_in(root, ws):
        raise Problem(f"the helper's workspace {ws} has commits this line lacks: merge its last task first "
                      f"(`brief_run.py helper {run.name} merge TASK`)")
    r = jj(folder, "new", heads[0])
    if r.returncode != 0:
        raise Problem(f"could not bring the workspace {ws} to the line's last commit: {r.stderr.strip()}")
    return folder


RULES = """You are asked to help the run of the brief `{brief}`, which its watcher keeps. This is one narrow piece of
work for that run. Do this and nothing else, by the rules a stream of the run works under:

- Work only in the jj workspace `{workspace}`, at `{folder}`. It is at the default line's last commit
  (`{base}`). Change no file in any other checkout: not the default workspace's, not a stream's.
- That folder's `CLAUDE.md` holds there as it does everywhere: commit from that folder with
  `python3 llm-dlc/tools/sync.py commit -m ... -m ...`, run the tests of what you changed, and queue proofs and
  model checks as jobs.
- Stay inside the task. If it turns out to need more than it says, a decision, or a change to something a stream
  is working on, stop and say so in your report: don't widen it.
- Don't merge, push, or land anything. The watcher merges what you commit, and tells the streams it concerns.
- When it is done, or you can't finish it, say so with a few lines in a file (what you changed, how you verified
  it, what is left and why) and run, as it is written here:
  `python3 {root}/llm-dlc/tools/brief_run.py helper {name} done {task} --report-file FILE`
"""


def cmd_helper_task(run: Run, name: str, title: str, file: str, send: bool) -> int:
    all_ = helpers(run)
    if name not in all_:
        raise Problem(f"the run has no helper {name}: its helpers are {', '.join(all_) or 'none'}. The user names one "
                      f'(`helper {run.name} add NAME --at "tmux 3"`)')
    h = all_[name]
    out_ = [t["id"] for t in h.get("tasks") or [] if not t.get("merged") and not t.get("dropped")]
    if out_:
        raise Problem(f"the helper {name} has a task that is not merged yet ({out_[0]}): one at a time")
    try:
        asked = Path(file).expanduser().read_text().strip()
    except OSError as e:
        raise Problem(f"the task's text, {file}, can't be read ({e.strerror})")
    if not asked or not " ".join(title.split()):
        raise Problem("a task has a title and a text that says what is asked")
    pane = h
    if send:  # before anything is made: a pane that is gone is looked up again by the user's word for it
        pane = pane_of(h["at"]) if tmux("display-message", "-p", "-t", h["pane"], "#{pane_id}").returncode != 0 else h
        if tmux("display-message", "-p", "-t", pane["pane"], "#{pane_current_command}").stdout.strip() in SHELLS:
            raise Problem(f"the helper's pane ({h['where']}) is at a shell prompt now: nothing was typed there, and no task "
                          f"was made. Ask the user where the helper's session is, and name its pane again "
                          f"(`helper {run.name} add {name} --at ...`)")
    folder = helper_folder(run, name)
    task_id = f"{name}-T{len(h.get('tasks') or []) + 1:03d}"
    base = watch.head_change(run.root) or ""
    path = run.dir / "helpers" / f"{task_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# Helper task {task_id} for the run of `{run.brief}`: {' '.join(title.split())}\n\n"
                    + RULES.format(brief=run.brief, workspace=h["workspace"], folder=folder, base=base, root=run.root,
                                   name=run.name, task=task_id)
                    + f"\n## The task\n\n{asked}\n")
    line = (f"Helper task {task_id} for the run of the brief {run.name}, from its watcher: read the file {path} in full "
            f"and do what it asks, in the workspace it names.")
    sent = None
    if send:
        typed = tmux("send-keys", "-t", pane["pane"], "-l", line)
        if typed.returncode == 0:
            typed = tmux("send-keys", "-t", pane["pane"], "Enter")
        if typed.returncode != 0:
            raise Problem(f"the task is written ({path}), but could not be typed into the helper's pane: "
                          f"{typed.stderr.strip()}. Give the helper this line yourself: {line}")
        sent = conductor.now()
    save_task(run, name, {"id": task_id, "title": " ".join(title.split()), "file": str(path), "folder": str(folder),
                          "base": change_of(folder), "sent": sent, "asked": conductor.now()})
    print(json.dumps({"task": task_id, "helper": name, "file": str(path), "workspace": h["workspace"], "folder": str(folder),
                      "sent": sent or "not typed into its pane", "line": line,
                      "next": "`wait` returns the task when the helper says it is done"}, indent=1))
    return 0


def change_of(folder: Path) -> str | None:
    r = jj(folder, "log", "--no-graph", "-r", "@-", "-T", "change_id", snapshot=False)
    return r.stdout.strip() or None if r.returncode == 0 else None


def cmd_helper_done(run: Run, task_id: str, report: str | None, report_file: str | None) -> int:
    found = tasks_of(run).get(task_id)
    if found is None:
        raise Problem(f"the run of {run.name} has no helper task {task_id}")
    name, task = found
    if report_file:
        try:
            report = Path(report_file).expanduser().read_text()
        except OSError as e:
            raise Problem(f"the report, {report_file}, can't be read ({e.strerror})")
    if not (report or "").strip():
        raise Problem("say in a few lines what you changed, how you verified it and what is left: --report TEXT or --report-file FILE")
    path = done_file(run, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps({"done": conductor.now(), "report": report.strip()[:REPORT_LIMIT]}, indent=1) + "\n")
    os.replace(tmp, path)
    print(f"recorded: the watcher of the {run.name} run is told that {task_id} is done, reads this report and merges "
          f"what you committed in {task['folder']}. Nothing more is asked of you for it")
    return 0


def helper_assessment(run: Run, name: str, task: dict) -> dict:
    folder = Path(task["folder"])
    left = [f for f in jj(folder, "diff", "-r", "@", "--name-only").stdout.splitlines() if f.strip() and not generated(f)]
    return {"task": task["id"], "helper": name, "title": task["title"], "report": task.get("report"),
            "commits": watch.commits(folder, task.get("base")), "uncommitted": left[:20],
            "merge": f"python3 llm-dlc/tools/brief_run.py helper {run.name} merge {task['id']}"}


def cmd_helper_merge(run: Run, task_id: str) -> int:
    found = tasks_of(run).get(task_id)
    if found is None:
        raise Problem(f"the run of {run.name} has no helper task {task_id}")
    name, task = found
    ws = helpers(run)[name]["workspace"]
    with writer(run.root):
        commit_own_record(run)
        out = land(run, ws, (f"Merge helper task {task_id} of the {run.name} run into the line",
                             f"{task['title']}: work the run of the brief {run.brief} had no owner for, done by the helper "
                             f"{name} (a session the user has open) in its workspace {ws} from a narrow brief of the watcher's, "
                             f"which merges it. The line had moved on since the task was given, so its commits come in by a "
                             f"merge. Nothing but the generated trace files met; they were regenerated from the session files."))
    save_task(run, name, {**task, "merged": conductor.now(), "commit": out.get("commit")})
    out.update(task=task_id, note="tell the streams it concerns through their inboxes (inbox.py send NAME-STREAM --kind "
                                  "delivered --do ... --commit CHANGE), each with what changed and where; the helper's "
                                  "workspace is kept for its next task")
    print(json.dumps(out, indent=1))
    return 0


def cmd_helper_list(run: Run) -> int:
    print(json.dumps({name: {**{k: h.get(k) for k in ("at", "where", "role", "workspace")},
                             "tasks": [{k: t.get(k) for k in ("id", "title", "sent", "done", "merged")} for t in h.get("tasks") or []]}
                      for name, h in helpers(run).items()}, indent=1))
    return 0


# -- the verification queue, which the watcher keeps itself


def collect_acknowledgements(run: Run) -> None:
    """Record the inbox items each stream's committed Progress acknowledges (inbox.py collect), so that what a
    stream has taken in shows while the run is under way, not only at its merge."""
    for s in run.plan["streams"]:
        try:
            inbox.collect(Path(s["brief"]).stem, run.root / inbox.FOLDER, run.root)
        except (inbox.InboxError, OSError, Problem):
            pass


# -- the run

def cmd_start(run: Run, agent: str | None = None, stream_agents: list[str] | tuple = ()) -> int:
    if refusal := watch.nested_run_refusal(f"brief_run.py start {run.name}"):
        raise Problem(refusal)
    data = run.read()
    if watch.alive((data.get("run") or {}).get("pid")):
        print(f"the run is already under way (pid {data['run']['pid']})")
        return 0
    set_agents(run, agent, list(stream_agents))
    check = preflight(run)
    if check["blocking"]:
        print(json.dumps({"blocking": check["blocking"]}, indent=1), file=sys.stderr)
        return 1
    run.dir.mkdir(parents=True, exist_ok=True)
    for name in ("ended.seen",):
        (run.dir / name).unlink(missing_ok=True)
    env = {**os.environ, "RUN_STREAMS_WATCHER": str(run.dir), "RUN_STREAMS_NEW_WINDOW": "no"}
    env.pop("LOOP_CONDUCTOR", None)  # another loop's, if this session carries one: each stream is given its own
    chosen = agents(run)
    env.pop("RUN_STREAMS_AGENT", None)
    env.pop("RUN_STREAMS_AGENTS", None)
    if chosen:  # the run's own word on who carries each loop; without one a brief's `- client:` setting stands
        env["RUN_STREAMS_AGENT"] = chosen.get("default") or "claude"
        env["RUN_STREAMS_AGENTS"] = ",".join(f"{k}={v}" for k, v in (chosen.get("streams") or {}).items())
    for key in ("TMUX", "TMUX_PANE"):  # the watcher's pane is not the run's: no status bar is drawn on it
        env.pop(key, None)
    with open(run.dir / "streams.log", "a") as out:
        p = subprocess.Popen([str(run.root / "llm-dlc/tools/run-streams.sh"), run.brief], cwd=run.root, env=env,
                             stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    run.update(run={"pid": p.pid, "started": conductor.now(), "log": str(run.dir / "streams.log")}, told=[], lastSummary=None)
    print(f"started the run of {run.brief} (pid {p.pid}); its output: {run.dir / 'streams.log'}")
    for row in check["streams"]:
        if row.get("client") and (row["client"] != "claude" or chosen):
            print(f"  {row['label']}: {row['client']}, {row.get('runs')} at {row.get('effort')} effort"
                  + (f" (for the brief's {row['model']})" if row.get("model") and row.get("runs") != row["model"] else ""))
    return 0


def loops(run: Run, check: dict | None = None) -> list[tuple[str, Path, str]]:
    """Each loop of the run as run-streams.sh labels it: (label, the workspace it runs in, its brief there)."""
    check = check or preflight(run)
    out = [(s["label"], Path(s["folder"]) if s.get("exists") else run.root, s["brief"]) for s in check["streams"]]
    return out or [("brief", run.root, run.brief)]  # a brief without streams is its own loop: there is no merge loop


KINDS_OF_TIME = ("working", "waiting on jobs", "blocked", "finished, others still running")


def times(run: Run, label: str, since: float, until: float, last_stream_end: float | None) -> dict[str, int]:
    """Seconds of this run a loop spent in each kind of time, from the phases run-streams.sh logs (LABEL.phases):
    working (a loop running), waiting on jobs, blocked (put to the watcher, or left blocked), and, for a stream,
    finished while another stream still ran, which is what merging a finished stream early would save."""
    out, marks = dict.fromkeys(KINDS_OF_TIME, 0), []
    for line in streams_status.read(run.dir / f"{label}.phases").splitlines():
        at, _, phase = line.partition("\t")
        try:
            marks.append((float(at), phase))
        except ValueError:
            continue
    marks = [(max(at, since), phase) for at, phase in marks if at >= since - 1]
    for (at, phase), (end, _) in zip(marks, marks[1:] + [(until, "")]):
        kind = ("working" if phase == "running" else "waiting on jobs" if phase.startswith("waiting") else
                "blocked" if phase.startswith(("blocked", "finished: blocked")) else
                "finished, others still running" if phase.startswith("finished") and label != "brief" else None)
        if kind == "finished, others still running":
            end = min(end, last_stream_end if last_stream_end is not None else until)
        if kind and end > at:
            out[kind] += int(end - at)
    return out


def last_stream_end(run: Run, labels: list[str], since: float) -> float | None:
    """When the last stream stopped running, or None while one still runs: after it, a finished stream waits for
    nobody."""
    ends = []
    for label in labels:
        marks = [line.partition("\t") for line in streams_status.read(run.dir / f"{label}.phases").splitlines()]
        marks = [(float(at), phase) for at, _, phase in marks if at.replace(".", "").isdigit() and float(at) >= since - 1]
        if not marks:
            continue
        if not marks[-1][1].startswith(("finished", "stopped")):
            return None
        ends.append(marks[-1][0])
    return max(ends) if ends else None


def state(run: Run) -> dict:
    data, check = run.read(), preflight(run)
    started = watch.stamp((data.get("run") or {}).get("started"))
    rows = []
    alive = watch.alive((data.get("run") or {}).get("pid"))
    try:
        until = watch.now() if alive else (run.dir / "streams.log").stat().st_mtime
    except OSError:
        until = watch.now()
    streams_end = last_stream_end(run, [s["label"] for s in check["streams"]], started or 0)
    for label, folder, brief in loops(run, check):
        phase = streams_status.read(run.dir / f"{label}.phase")
        rows.append({"loop": label, "time": times(run, label, started or 0, until, streams_end) if started else None, "status": streams_status.brief_status(folder / brief) or None, "phase": phase or "not started",
                     "cycle": streams_status.read(run.dir / f"{label}.cycle") or None,
                     "commits": streams_status.commits(folder, brief), "spent": round(streams_status.spend(run.dir, label), 2),
                     "unpriced": dict(zip(("turns", "tokensIn", "tokensOut"), streams_status.unknown(run.dir, label))),
                     "head": watch.head_change(folder) if folder.exists() else None,
                     **({"merged": merged_in(run.root, ws)} if (ws := workspace_of(check, label)) else {})})
    result = re.search(r"^- Result: (.+)$", streams_status.read(run.report), re.M)
    record = open_decisions(run)
    queue = watch.jobs(run.root)
    return {"name": run.name, "brief": run.brief, "running": watch.alive((data.get("run") or {}).get("pid")),
            "started": (data.get("run") or {}).get("started"), "stopping": (run.dir / "stop-after").exists(),
            "elapsed": watch.span(watch.now() - started) if started else None,
            "foundation": check["foundation"], "loops": rows,
            "spent": round(sum(r["spent"] for r in rows) + ((check["foundation"] or {}).get("cost") or 0), 2),
            "integration": result[1] if result else None,
            "openDecisions": record, "mergeOrder": data.get("mergeOrder") or None,
            "helpers": {name: {"at": h.get("at"), "role": h.get("role"),
                               "open": [t["id"] + (" (done, not merged)" if t.get("done") else "") for t in h.get("tasks") or []
                                        if not t.get("merged") and not t.get("dropped")]}
                        for name, h in helpers(run).items()},
            "jobs": {k: queue.get(k) or [] for k in ("pending", "running", "finished")}, "blocking": check["blocking"]}


def workspace_of(check: dict, label: str) -> str | None:
    """A stream's workspace, once it has one."""
    return next((s["workspace"] for s in check["streams"] if s["label"] == label and s.get("exists")), None)


def open_decisions(run: Run) -> list[str]:
    """The decisions waiting for the user in the run's records: the brief's (the integration line's triage, and
    what streams and the watcher record) and the one the watcher's verdicts go to."""
    out = []
    for name in (run.stem, run.dir.name):
        try:
            record = decisions.fold(decisions.read(name, run.root / "llm-dlc" / "decisions"))
        except (Exception, SystemExit):
            continue
        out += [i for i, d in record.items() if d.get("state") == "open"]
    return sorted(out)


def summary(run: Run, s: dict) -> str:
    last = (run.read().get("lastSummary") or {}).get("loops") or {}
    lines = [f"### {watch.clock(watch.now())} UTC · {s['elapsed'] or 'not started'} into the run of {s['brief']} · {streams_status.dollars(s['spent'], sum((r.get('unpriced') or {}).get('turns') or 0 for r in s['loops']))}"]
    f = s.get("foundation") or {}
    if f.get("ended"):
        lines.append(f"- **foundation**: {'ended' if f.get('ok') else 'ended with an error'}"
                     + (f", ${f['cost']:.2f}" if f.get("cost") is not None else ", cost not known")
                     + ("; landed" if f.get("landed") else "; not landed"))
    for r in s["loops"]:
        was = last.get(r["loop"]) or {}
        moved = r["commits"] - was.get("commits", 0)
        lines.append(f"- **{r['loop']}**: {r['status'] or r['phase']}"
                     + (f" ({r['phase']})" if r["phase"] not in ("running", "not started") and not r["phase"].startswith("finished") else "")
                     + ("; merged" if r.get("merged") else "")
                     + f"; cycle {r['cycle'] or '-'}, {r['commits']} commits" + (f" (+{moved})" if was and moved else "")
                     + f", {streams_status.dollars(r['spent'], (r.get('unpriced') or {}).get('turns'))}"
                     + (f" ({r['unpriced']['turns']} turn(s) of unknown cost: {r['unpriced']['tokensIn']} tokens in, {r['unpriced']['tokensOut']} out)"
                        if (r.get("unpriced") or {}).get("turns") else "")
                     + (f"; at {r['head']}" if r["head"] and (not was or was.get("head") != r["head"]) else ""))
        spans = [f"{watch.span(v)} {k}" for k, v in (r.get("time") or {}).items() if v >= 60]
        if spans:
            lines.append("  - time: " + ", ".join(spans))
    if s["integration"]:
        lines.append(f"- integration: {s['integration']}")
    for name, h in (s.get("helpers") or {}).items():
        if h["open"]:
            lines.append(f"- helper {name} ({h['at']}): {', '.join(h['open'])}")
    if s["openDecisions"]:
        lines.append(f"- open for the user: {', '.join(s['openDecisions'])} (`python3 llm-dlc/tools/decisions.py show ID`)")
    queue = s["jobs"]
    if any(queue.values()):
        lines.append("- verification queue: " + ", ".join(f"{len(v)} {k}" for k, v in queue.items() if v))
    return "\n".join(lines)


def foundation_progress(foundation: dict) -> dict:
    """Where the foundation session stands while it runs, from its stream and its workspace. What it has spent is
    known only when it ends: Claude Code reports a session's cost with its result."""
    act = watch.activity({"log": foundation.get("log"), "offset": foundation.get("offset") or 0})
    folder = Path(foundation.get("folder") or ".")
    started = watch.stamp(foundation.get("started"))
    return {"running": watch.span(watch.now() - started) if started else None, "toolCalls": act["toolCalls"],
            "lastOutput": f"{watch.span(watch.now() - act['lastOutput'])} ago" if act.get("lastOutput") else None,
            "command": act.get("command"), "lastCommit": watch.head_change(folder) if folder.exists() else None,
            "uncommitted": len(jj(folder, "diff", "-r", "@", "--name-only").stdout.split()) if folder.exists() else None,
            "note": "the foundation session is still at work: nothing to do. To end it early, interrupt its "
                    "background task; what it committed is kept, and the stage run again continues the session."}


def next_thing(run: Run, interval: float) -> dict | None:
    data = run.read()
    told = list(data.get("told") or [])

    def once(key: str) -> bool:
        if key in told:
            return False
        run.update(told=told + [key])
        return True

    event = conductor.pending(run.dir)
    if event is not None and event.get("type") == "merge":
        first = before_in_order(run, event.get("loop"))
        return {"kind": "question", "event": {**event, "secondsLeft": int(event["deadline"] - time.time())},
                **({"order": {"first": first, "note": "the run's merge order puts these before it, with commits this line "
                                                      "lacks: merge each first, with the command it names, then this one"}}
                   if first else {}),
                "merge": f"python3 llm-dlc/tools/brief_run.py merge {run.name} {event.get('loop')}",
                "leave": f"python3 llm-dlc/tools/conductor.py decide {run.dir.relative_to(run.root)} {event['n']} leave --reason TEXT"}
    if event is not None and event.get("type") != "ended":
        return {"kind": "question", "event": {**event, "secondsLeft": int(event["deadline"] - time.time())},
                "inbox": f"python3 llm-dlc/tools/inbox.py list {Path(event.get('brief', run.brief)).stem} --open",
                "answer": f"python3 llm-dlc/tools/conductor.py decide {run.dir.relative_to(run.root)} {event['n']} "
                          f"{'|'.join(conductor.answers(event))} --reason TEXT [--confidence medium]"}
    foundation = data.get("foundation") or {}
    if foundation.get("pid") and not foundation.get("ended") and watch.alive(foundation["pid"]):
        last = foundation.get("told") or watch.stamp(foundation.get("started")) or 0
        if watch.now() - last >= interval:
            run.update(foundation={**run.read()["foundation"], "told": watch.now()})
            return {"kind": "foundation", **foundation_progress(foundation)}
    for name, h in helpers(run).items():
        for task in h.get("tasks") or []:
            if task.get("done") and not task.get("merged") and once(f"helper:{task['id']}:{task['done']}"):
                return {"kind": "helper", **helper_assessment(run, name, task),
                        "note": "read the report against what the task asked, and the commits; merge it with the command "
                                "`merge` names, then tell the streams it concerns through their inboxes. What it left "
                                "undone, or widened, is yours to judge: a new task, the user, or a finding"}
    started = (data.get("run") or {}).get("started")
    if started and not watch.alive(data["run"].get("pid")) and once(f"ended:{started}"):
        return {"kind": "ended", "state": state(run)}
    if not started:
        return None
    result = re.search(r"^- Result: (\S+)", streams_status.read(run.report), re.M)
    if result and result[1].rstrip(";,.") not in ("passed", "unchanged") and once(f"integration:{run.report.stat().st_mtime_ns}"):
        return {"kind": "attention", "what": "the integration check did not pass", "read": str(run.report.relative_to(run.root)),
                "note": "it has triaged itself into the decision record and the streams' inboxes: read the report, decide "
                        "what is yours by the test of llm-dlc/loops/stream-conductor.md Design 3, and leave the rest to the user"}
    for i in open_decisions(run):
        if once(f"open:{i}"):
            return {"kind": "attention", "what": f"the decision {i} is open", "show": f"python3 llm-dlc/tools/decisions.py show {i}",
                    "note": "decide it if it is yours to decide (cheap to take back, and you are sure), record it, and tell "
                            "the stream it concerns through its inbox; else put it to the user"}
    last = (data.get("lastSummary") or {}).get("time") or watch.stamp(started) or 0
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
            if run.read().get("run"):
                with contextlib.suppress(Problem), writer(run.root):
                    commit_own_record(run)  # the watcher's answers and the user's, as they come
                collect_acknowledgements(run)
                if setting(run.root / run.brief, "verification") != "separate":
                    thing = tend(run)
        if thing is not None:
            if thing["kind"] == "summary":
                s = state(run)
                print(summary(run, s))
                run.update(lastSummary={"time": watch.now(), "loops": {r["loop"]: r for r in s["loops"]}})
                return 0
            print(json.dumps(thing, indent=1))
            return 0
        if time.monotonic() >= until:
            print(json.dumps({"kind": "nothing", "note": "nothing yet: wait again"}))
            return 3
        time.sleep(2)


def cmd_stop(run: Run, now: bool) -> int:
    pid = (run.read().get("run") or {}).get("pid")
    if not watch.alive(pid):
        print("the run is not under way")
        return 0
    if now:
        os.killpg(int(pid), signal.SIGINT)  # run-streams.sh passes it on to every loop, which records it
        print(f"interrupted the run (pid {pid}): each loop records it, and `brief_run.py start {run.name}` continues")
        return 0
    (run.dir / "stop-after").write_text(conductor.now() + "\n")  # run-streams.sh: run no loop again, ask no merge
    told = []
    for loop in sorted((run.dir / "loops").glob("*")) if (run.dir / "loops").is_dir() else []:
        if streams_status.read(run.dir / f"{loop.name}.phase") == "running":
            conductor.cmd_command(loop, "stop")  # feature-loop.sh: end after the cycle under way
            told.append(loop.name)
    print(f"the run stops at a boundary: {', '.join(told) or 'no loop'} told to end after the cycle under way, nothing "
          f"is run again and no stream is put to you to merge. `wait` returns `ended` when it has; `brief_run.py start "
          f"{run.name}` continues, and `stop --now` interrupts instead")
    return 0


def main(argv: list[str] | None = None, root: Path = REPO) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("preflight", "land", "status", "collect"):
        sub.add_parser(name).add_argument("brief")
    st = sub.add_parser("start")
    st.add_argument("brief")
    st.add_argument("--agent", choices=agent_client.CLIENTS, help="who carries the streams' turns (default: claude)")
    st.add_argument("--stream-agent", action="append", default=[], metavar="STREAM=CLIENT", help="one stream's client")
    m = sub.add_parser("merge")
    m.add_argument("brief")
    m.add_argument("stream")
    m.add_argument("--early", action="store_true", help="a stream still at work: its line as committed so far")
    m.add_argument("--out-of-order", action="store_true", help="before a stream the run's merge order puts first")
    sub.add_parser("trial").add_argument("brief")
    o = sub.add_parser("order")
    o.add_argument("brief")
    o.add_argument("streams", nargs="*")
    o.add_argument("--clear", action="store_true")
    r = sub.add_parser("rerun")
    r.add_argument("brief")
    r.add_argument("stream")
    h = sub.add_parser("helper")
    h.add_argument("brief")
    hs = h.add_subparsers(dest="action", required=True)
    ha = hs.add_parser("add")
    ha.add_argument("name")
    ha.add_argument("--at", required=True, help='where its session is: "tmux 3"')
    ha.add_argument("--role")
    ht = hs.add_parser("task")
    ht.add_argument("name")
    ht.add_argument("--title", required=True)
    ht.add_argument("--file", required=True, help="what is asked, in the watcher's words")
    ht.add_argument("--no-send", action="store_true", help="write the task and print the line, typing nothing")
    hd = hs.add_parser("done")
    hd.add_argument("task")
    hd.add_argument("--report")
    hd.add_argument("--report-file")
    hs.add_parser("merge").add_argument("task")
    hs.add_parser("list")
    x = sub.add_parser("stop")
    x.add_argument("brief")
    x.add_argument("--now", action="store_true", help="interrupt mid-cycle instead of stopping at a boundary")
    b = sub.add_parser("budget")
    b.add_argument("brief")
    b.add_argument("--apply", action="store_true")
    b.add_argument("--restore", action="store_true")
    f = sub.add_parser("foundation")
    f.add_argument("brief")
    f.add_argument("--model")
    f.add_argument("--effort")
    f.add_argument("--memory", help="the session's memory cap (default: a loop's, by doctor.py; `none` for no scope)")
    f.add_argument("--prompt", help="in place of the stage's own instruction")
    f.add_argument("--agent", choices=agent_client.CLIENTS, help="who carries the foundation session (default: the run's, else claude)")
    w = sub.add_parser("wait")
    w.add_argument("brief")
    w.add_argument("--interval", type=float)
    w.add_argument("--timeout", type=float, default=3300)
    v = sub.add_parser("verification")
    v.add_argument("brief")
    v.add_argument("action", choices=("start", "stop", "status", "nudge"))
    i = sub.add_parser("interval")
    i.add_argument("brief")
    i.add_argument("seconds", type=float)
    args = ap.parse_args(argv)
    try:
        run = Run(root, args.brief)
        if args.command == "preflight":
            return cmd_preflight(run)
        if args.command == "budget":
            return cmd_budget(run, args.apply, args.restore)
        if args.command == "foundation":
            return cmd_foundation(run, args.model, args.effort, args.memory, args.prompt, args.agent)
        if args.command == "land":
            return cmd_land(run)
        if args.command == "start":
            return cmd_start(run, args.agent, args.stream_agent)
        if args.command == "merge":
            return cmd_merge(run, args.stream, args.early, args.out_of_order)
        if args.command == "trial":
            print(json.dumps(trial(run), indent=1))
            return 0
        if args.command == "order":
            return cmd_order(run, args.streams, args.clear)
        if args.command == "rerun":
            return cmd_rerun(run, args.stream)
        if args.command == "helper":
            if args.action == "add":
                return cmd_helper_add(run, args.name, args.at, args.role)
            if args.action == "task":
                return cmd_helper_task(run, args.name, args.title, args.file, not args.no_send)
            if args.action == "done":
                return cmd_helper_done(run, args.task, args.report, args.report_file)
            if args.action == "merge":
                return cmd_helper_merge(run, args.task)
            return cmd_helper_list(run)
        if args.command == "wait":
            return cmd_wait(run, args.interval, args.timeout)
        if args.command == "verification":
            return watch.cmd_verification(run, args.action)
        if args.command == "collect":
            got = collect(run)
            print(json.dumps(got, indent=1) if got else "nothing to collect")
            return 0
        if args.command == "interval":
            run.update(interval=args.seconds)
            print(f"a summary every {watch.span(args.seconds)} from now on")
            return 0
        if args.command == "status":
            print(json.dumps(state(run), indent=1))
            return 0
        return cmd_stop(run, args.now)
    except (Problem, integration.IntegrationError) as e:
        print(f"brief_run.py: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

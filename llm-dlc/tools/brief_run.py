#!/usr/bin/env python3
"""The watcher's tools for the run of a brief (.claude/skills/run-brief, llm-dlc/README.md "A brief's run").

A brief (llm-dlc/loops/NAME.md) is run by one watcher session, as /prove-java-change runs a proof: the watcher
does none of the work, starts what does, is called back when something needs a judgement, and reports at
intervals. This is what it runs. BRIEF is a brief's name or file, as run-streams.sh takes it.

    brief_run.py preflight BRIEF
        what the run would start (the brief, its streams, their workspaces, sessions and statuses), what stands
        in its way (`blocking`), what to know (`notes`), and the verification runner's budget beside this many
        loops. Exit 1 while anything blocks.
    brief_run.py budget BRIEF [--apply | --restore]
        the runner's budget beside the run's loops, against verification/pipeline.local.toml; --apply lowers the
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
    brief_run.py wait BRIEF [--interval SECONDS] [--timeout SECONDS]
        block until something needs the watcher, and print it as JSON: a `question` (a loop ended blocked: rerun
        or leave; a stream is finished: merge it), `attention` (the integration check stopped passing, or a decision is open for the user),
        `results` (results came back and were collected and committed; what is in `attention` is to triage),
        `verification` (jobs waited and no runner was at work: one was started), `summary` (every 30 minutes, or
        `interval`), or `ended`. Exit 3 with nothing after the timeout: wait again. At each look at the queue it
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

import conductor
import decisions
import doctor
import inbox
import integration
import streams_status
import watch

REPO = Path(__file__).resolve().parents[2]
INTERVAL = 1800
FOUNDATION = {"model": "claude-fable-5-2", "effort": "high"}
# The user's words for the foundation stage (2026-11-17), after a sentence that names the brief.
FOUNDATION_PROMPT = ("This brief was designed for a group of agents, but I'd prefer for you to start work instead. Feel "
                     "free to implement whatever foundation you see fit, maximizing benefits and efficiency, then update "
                     "the brief accordingly for other agents to take over after.")
INTEGRATION_MEMORY, INTEGRATION_CPUS, LOOP_CPUS = 6, 2, 2  # verification/README.md: what a run's parts are given


class Problem(Exception):
    pass


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


def jj(where: Path, *args: str, snapshot: bool = True) -> subprocess.CompletedProcess:
    return integration.jj(where, *args, snapshot=snapshot)


def workspaces(root: Path) -> dict[str, Path | None]:
    """Each jj workspace of the repository, with its folder when jj knows it."""
    out = {}
    for m in re.finditer(r"^([^\s:]+)(?: \(current\))?:", jj(root, "workspace", "list", snapshot=False).stdout, re.M):
        r = jj(root, "workspace", "root", "--name", m[1], snapshot=False)
        out[m[1]] = Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None
    return out


def running(root: Path, script: str) -> list[int]:
    """The processes running SCRIPT (a file name) for this repository, whichever workspace they run in."""
    mine, out = watch.store(root), []
    r = subprocess.run(["pgrep", "-u", str(os.getuid()), "-f", re.escape(script)], capture_output=True, text=True)
    for pid in r.stdout.split():
        try:
            words = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            theirs = watch.store(os.readlink(f"/proc/{pid}/cwd"))
        except OSError:
            continue
        if mine and theirs == mine and any(w.endswith(script.encode()) for w in words):
            out.append(int(pid))
    return out


def loops_in(root: Path) -> list[int]:
    """The feature loops at work in this folder: feature-loop.sh runs from a private copy of itself
    (feature-loop.XXXXXX), whatever started it, a proof run's prove-loop.sh included."""
    out = []
    r = subprocess.run(["pgrep", "-u", str(os.getuid()), "-f", "feature-loop"], capture_output=True, text=True)
    for pid in r.stdout.split():
        try:
            words = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            cwd = Path(os.readlink(f"/proc/{pid}/cwd"))
        except OSError:
            continue
        if cwd == root.resolve() and any(Path(w.decode(errors="replace")).name.startswith("feature-loop.") for w in words[:3]):
            out.append(int(pid))
    return out


SESSION = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

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


def local_budget(root: Path) -> dict:
    """The [runner] values verification/pipeline.local.toml sets, of the three the budget names."""
    out, section = {}, None
    try:
        lines = (root / LOCAL).read_text().splitlines()
    except OSError:
        return out
    for line in lines:
        if m := re.match(r"^\[([^\]]+)\]", line):
            section = m[1]
        elif section == "runner" and (m := re.match(r'^(workers|cpus|memory)\s*=\s*"?([^"#\s]+)"?', line)):
            out[m[1]] = m[2]
    return out


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
    path = root / LOCAL
    lines, section, left = path.read_text().splitlines(), None, dict(values)
    for i, line in enumerate(lines):
        if m := re.match(r"^\[([^\]]+)\]", line):
            section = m[1]
        elif section == "runner" and (m := re.match(r"^(workers|cpus|memory)(\s*=\s*)", line)) and m[1] in left:
            value = left.pop(m[1])
            comment = re.search(r"\s+#.*$", line)
            lines[i] = f'{m[1]}{m[2]}{json.dumps(value) if m[1] == "memory" else int(value)}{comment[0] if comment else ""}'
    if left:
        raise Problem(f"{LOCAL} sets no [runner] {', '.join(left)}: add them by hand, as verification/README.md shows")
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
        print(f"{LOCAL} has its values of before the run again: {kept}. A runner at work keeps its budget until its run ends.")
        return 0
    over = over_budget(have, want)
    if apply and over:
        run.update(budgetBefore=kept or {k: have[k] for k in BUDGET_KEYS if k in have})
        write_budget(run.root, {k: want[k] for k in BUDGET_KEYS if k in have})
        print(f"lowered in {LOCAL}: {'; '.join(over)}. A runner at work keeps its budget until its run ends: "
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
    dirty = jj(root, "diff", "-r", "@", "--name-only").stdout.split()
    if dirty:
        notes.append(f"the default workspace has uncommitted changes ({len(dirty)} files, {dirty[0]} first): another "
                     f"session's, or yours to commit before the run")
    budget = runner_budget(len(run.plan["streams"]), bool(out["integration"]))
    over = over_budget(local_budget(root), budget)
    if over:
        notes.append(f"{LOCAL} gives the runner more than is left beside {budget['loops']} loop(s): {'; '.join(over)}. "
                     f"`brief_run.py budget {run.name} --apply` lowers it for the run")
    foundation = run.read().get("foundation") or {}
    out.update(foundation={k: foundation.get(k) for k in ("session", "ended", "ok", "commit", "landed", "cost")} if foundation else None,
               budget=budget, blocking=blocking, notes=notes)
    return out


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


def cmd_foundation(run: Run, model: str | None, effort: str | None, memory: str | None, prompt: str | None) -> int:
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
    run.update(foundation={"session": session, "workspace": ws, "folder": str(folder), "started": started, "log": str(log),
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


def commit_id(where: Path, rev: str) -> str:
    r = jj(where, "log", "--no-graph", "-r", rev, "-T", "commit_id", snapshot=False)
    if r.returncode != 0 or not r.stdout.strip():
        raise Problem(f"no revision {rev}: {r.stderr.strip()}")
    return r.stdout.strip()


def is_ancestor(where: Path, a: str, b: str) -> bool:
    return bool(jj(where, "log", "--no-graph", "-r", f"{a} & ::{b}", "-T", "commit_id", snapshot=False).stdout.strip())


# What sync.py regenerate writes from the per-session files, as sync.py commit does each time: the trace files, the
# index, llm-dlc/README.md's session table and the decision records' views. Left uncommitted in the default working
# copy (a sync.py run of any session there writes them), they are nobody's work: the next sync.py run writes them again.
TRACE_FILES = ("llm-dlc/traces/", "llm-dlc/index.json")
TABLE_README = "llm-dlc/README.md"
INDEX_BEGIN, INDEX_END = "<!-- index:begin (generated by llm-dlc/tools/sync.py) -->", "<!-- index:end -->"  # sync.py's


def generated(path: str) -> bool:
    """Whether sync.py regenerate writes this path."""
    return path.startswith(TRACE_FILES) or path == TABLE_README or (path.startswith("llm-dlc/decisions/") and path.endswith(".md"))


def outside_table(text: str) -> str:
    start, end = text.find(INDEX_BEGIN), text.rfind(INDEX_END)
    return text[:start] + text[end:] if 0 <= start < end else text


def regenerable(root: Path, path: str) -> bool:
    """Whether an uncommitted change to PATH in the working copy is only what sync.py writes: a generated file, and
    of llm-dlc/README.md, which people edit too, only its session table."""
    if not generated(path):
        return False
    if path != TABLE_README:
        return True
    before = jj(root, "file", "show", "-r", "@-", path, snapshot=False)
    try:
        now = (root / path).read_text()
    except OSError:
        return False
    return before.returncode == 0 and outside_table(before.stdout) == outside_table(now)


def sync_lock_path(root: Path) -> Path:
    """The lock sync.py takes on this repository for every command that writes (its Operation): keyed by the
    repository's path, under the local state."""
    state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "llm-traces"
    return state / "locks" / (hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:16] + ".lock")


@contextlib.contextmanager
def sync_lock(root: Path):
    """Hold sync.py's lock on the repository across jj steps that rewrite the default working copy, so that no
    sync.py commit (the watcher's own session's, a loop's) runs between them. Never across a call of sync.py,
    which takes the lock itself and would wait for this one."""
    path = sync_lock_path(root)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


@contextlib.contextmanager
def writer(root: Path):
    """The watcher's own writes to the default working copy (a merge, a collection of results) one at a time,
    whichever of its commands makes them."""
    path = root / "llm-dlc" / "loop-summaries" / "default-workspace.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def adopt_logs(root: Path) -> None:
    """Take the session logs the line now names and this workspace lacks, from the workspace storing them
    (sync.py adopt-logs): else every later check here reports each as an error."""
    sync = root / "llm-dlc" / "tools" / "sync.py"
    if sync.exists():
        subprocess.run([sys.executable, str(sync), "adopt-logs"], cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)


def land(run: Run, workspace: str, message: tuple[str, str] | None = None) -> dict:
    """Bring WORKSPACE's line to the default workspace's (see the header), and the session logs it names."""
    out = _land(run, workspace, message)
    adopt_logs(run.root)
    return out


def _land(run: Run, workspace: str, message: tuple[str, str] | None) -> dict:
    root = run.root
    with sync_lock(root):
        dirty = jj(root, "diff", "-r", "@", "--name-only").stdout.split()  # also snapshots the working copy
        theirs, ours = commit_id(root, f"{workspace}@-"), commit_id(root, "@-")
        left = jj(root, "diff", "-r", f"{workspace}@", "--name-only", snapshot=False).stdout.split()
        if left:
            raise Problem(f"the workspace {workspace} has uncommitted changes ({', '.join(left[:5])}): its session commits them first")
        if is_ancestor(root, theirs, ours):
            return {"landed": "nothing to land: the line already has it", "commit": watch.head_change(root)}
        # Uncommitted trace output is nobody's work, and the next sync.py run writes it again from the session
        # files: it neither waits for a session's commit nor comes along onto the other line, where it would meet
        # that line's own.
        dropped = [f for f in dirty if regenerable(root, f)]
        dirty = [f for f in dirty if f not in dropped]
        forward = is_ancestor(root, ours, theirs)
        if dirty and not forward:
            raise Problem(f"the default workspace has uncommitted changes ({', '.join(dirty[:5])}), and the line has moved, so "
                          f"landing takes a merge: wait for their session's commit, and land again")
        if dropped:
            jj(root, "restore", "--", *dropped)
        before = jj(root, "log", "--no-graph", "-r", "@", "-T", "change_id", snapshot=False).stdout.strip()
        if forward:
            r = jj(root, "rebase", "-s", "@", "-d", theirs)  # what is uncommitted here, another session's, comes along
            if r.returncode != 0:
                raise Problem(f"could not move the line forward: {r.stderr.strip()}")
            files = integration.conflicted(root)
            if files:
                jj(root, "rebase", "-s", "@", "-d", ours)
                raise Problem(f"another session's uncommitted files here conflict with {workspace}'s line in "
                              f"{', '.join(files[:8])}: the line is left where it was. Land again once that session has "
                              f"committed them")
            return {"landed": "moved forward: the line had not moved since the workspace was made",
                    "commit": watch.head_change(root), **({"dropped": dropped} if dropped else {})}
        r = jj(root, "new", ours, theirs)
        if r.returncode != 0:
            raise Problem(f"the merge could not be made: {r.stderr.strip()}")
        if jj(root, "log", "--no-graph", "-r", f"{before} & empty() & ~@", "-T", "change_id", snapshot=False).stdout.strip():
            jj(root, "abandon", before, snapshot=False)  # left empty, but described (sync.py's "Record session traces")
        merge = jj(root, "log", "--no-graph", "-r", "@", "-T", "change_id").stdout.strip()
    files = integration.conflicted(root)
    sync = root / "llm-dlc" / "tools" / "sync.py"
    if sync.exists():  # the generated trace files, which every line's commits rewrite
        subprocess.run([sys.executable, str(sync), "regenerate"], cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        files = integration.conflicted(root)
    if files:
        with sync_lock(root):
            jj(root, "new", ours)
            jj(root, "abandon", merge)
        raise Problem(f"the merge conflicts in {', '.join(files[:8])}: taken back. Resolve it by hand as llm-dlc/runtime.md's "
                      f"merge of a queued workspace shows (a merge of @- and {workspace}@-), or have the session that "
                      f"wrote it rebuild on the line as it is now")
    message = message or (f"Merge the foundation of the {run.name} run into the line",
                          f"The foundation stage of the brief {run.brief} ran in the workspace {workspace} while this line "
                          f"moved on, so its commits come in by a merge. Nothing but the generated trace files met; they "
                          f"were regenerated from the session files.")
    r = subprocess.run([sys.executable, str(sync), "commit", "-m", message[0], "-m", message[1]],
                       cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise Problem(f"the merge is made but its commit reported: {(r.stderr or r.stdout).strip()[-600:]}")
    # A clean merge changes nothing itself but the files regenerated from the session files. Anything else in it was
    # written into this working copy by another session while the merge was being made (the result collector's
    # results, say): it goes back to being uncommitted, on top, the files on disk as they are, for that session's
    # own commit.
    with sync_lock(root):
        foreign = [f for f in jj(root, "diff", "-r", "@-", "--name-only").stdout.splitlines() if not generated(f)]
        if foreign:
            jj(root, "squash", "--from", "@-", "--into", "@", "-u", "--", *foreign)
    return {"landed": "merged: the line had moved since the workspace was made", "commit": watch.head_change(root),
            **({"leftUncommitted": foreign} if foreign else {}), **({"dropped": dropped} if dropped else {})}


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
    out = land(run, run.foundation_workspace)
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


def merged_in(root: Path, workspace: str) -> bool:
    return is_ancestor(root, commit_id(root, f"{workspace}@-"), commit_id(root, "@-"))


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
    if not all(m for _, m, _ in rows):
        return "working"
    blocked = [f"stream {label}: {status}" for label, _, status in rows if not (status or "").startswith("done")]
    return "done" if not blocked else "blocked: " + "; ".join(blocked)


def commit_own_record(run: Run) -> None:
    """Commit the watcher's own answers (conductor.py decide writes them to the run's decision record and commits
    nothing), so they don't count as another session's uncommitted files that a merge must wait for."""
    own = [f"llm-dlc/decisions/{run.dir.name}.jsonl", f"llm-dlc/decisions/{run.dir.name}.md"]
    dirty = jj(run.root, "diff", "-r", "@", "--name-only").stdout.split()
    mine = [f for f in dirty if f in own]
    if not mine:
        return
    r = subprocess.run([sys.executable, str(run.root / "llm-dlc" / "tools" / "sync.py"), "commit", "--only", *mine,
                        "-m", f"Record the watcher's answers in the {run.name} run",
                        "-m", f"The decisions the watcher of the brief {run.brief} took while it ran, committed before it "
                              f"merges a stream."],
                       cwd=run.root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise Problem(f"could not commit the run's decision record first: {(r.stderr or r.stdout).strip()[-600:]}")


def cmd_merge(run: Run, label: str) -> int:
    with writer(run.root):
        return merge(run, label)


def merge(run: Run, label: str) -> int:
    s = stream_of(run, label)
    workspace, root = s["workspace"], run.root
    head = jj(root, "log", "--no-graph", "-r", f"{workspace}@-", "-T", "change_id.short(12)", snapshot=False).stdout.strip()
    status = streams_status.brief_status(Path(s["folder"]) / s["brief"]) or "no status"
    commit_own_record(run)
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
    print(json.dumps(out, indent=1))
    return 0


# -- the verification queue, which the watcher keeps itself

def pipeline(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(root / "verification" / "pipeline.py"), *args], cwd=root,
                          capture_output=True, text=True, stdin=subprocess.DEVNULL)


def queue(root: Path) -> dict | None:
    r = pipeline(root, "status", "--json")
    try:
        return json.loads(r.stdout) if r.returncode == 0 else None
    except ValueError:
        return None


def collect(run: Run) -> dict | None:
    """Collect the results that are back (verification/pipeline.py collect) and commit them with the paths a commit
    of results holds and nothing else (`sync.py commit --only $(pipeline.py commit-paths)`), as the verification
    loop's sessions did: the watcher is then the one session that commits in the default working copy while a
    run is under way, its merges and its collections one after the other. None when nothing waited. What is in
    `attention` (a job that did not pass, outputs not applied, anything a result flags) is for the watcher to
    triage."""
    root = run.root
    with writer(root):
        status = queue(root)
        if not status or not status.get("finished, not collected"):
            return None
        r = pipeline(root, "collect")
        if r.returncode != 0:
            raise Problem(f"pipeline.py collect failed: {(r.stderr or r.stdout).strip()[-600:]}")
        ids = re.findall(r"^(\S+): \w+: applied \d+", r.stdout, re.M)
        said = r.stdout.split("For the commit message", 1)[-1].splitlines()[1:]
        said = [line.strip() for line in said if line.strip()]
        title = said[0] if said else f"Record verification results for {len(ids)} job(s)"
        body = " ".join(said[1:]) or "Collected by the watcher."
        paths = pipeline(root, "commit-paths").stdout.split()
        c = subprocess.run([sys.executable, str(root / "llm-dlc" / "tools" / "sync.py"), "commit", "--only", *paths,
                            "-m", title, "-m", f"{body} Collected by the watcher of the {run.name} run, which keeps the "
                                               f"queue while the run is under way."],
                           cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    results, attention = [], []
    for job in ids:
        try:
            result = json.loads((root / "verification" / "results" / job / "result.json").read_text())
        except (OSError, ValueError):
            result = {}
        row = {"id": job, "status": result.get("status", "?"), "summary": result.get("summary")}
        flags = list(result.get("attention") or []) + [f"output not applied: {f}" for f in
                                                       (result.get("collected") or {}).get("conflicts") or []]
        if row["status"] != "passed" or flags:
            attention.append({**row, "attention": flags})
        results.append(row)
    out = {"collected": results, "attention": attention, "commit": watch.head_change(root)}
    if c.returncode != 0:
        out["commitReported"] = (c.stderr or c.stdout).strip()[-600:]
    return out


def start_runner(run: Run, status: dict) -> dict | None:
    """Start the runner (verification/pipeline.py run, no model) when jobs this machine can run wait and no runner
    is at work. It takes the budget verification/pipeline.local.toml gives (`budget --apply`), runs until the queue
    is empty and ends; the next look starts it again when more jobs come. A job committed while it runs is
    announced to it (nudge), once."""
    root = run.root
    waiting = [m[0] for row in status.get("pending", []) if "; cannot run here:" not in row
               and (m := conductor.JOB_ID.search(row))]
    data = run.read()
    if not waiting:
        if data.get("nudged"):
            run.update(nudged=[])
        return None
    ours = (data.get("runner") or {}).get("pid")
    at_work = (watch.alive(ours) or "no runner is at work" not in pipeline(root, "wait", "--timeout", "0").stdout)
    if at_work:
        if [j for j in waiting if j not in (data.get("nudged") or [])]:
            watch.nudge(root)
            run.update(nudged=waiting)
        return None
    run.dir.mkdir(parents=True, exist_ok=True)
    pid = watch.detached([sys.executable, str(root / "verification" / "pipeline.py"), "run"], root, run.dir / "runner.log")
    run.update(runner={"pid": pid, "started": conductor.now(), "jobs": waiting}, nudged=waiting)
    return {"kind": "verification", "pid": pid, "jobs": waiting,
            "note": f"{len(waiting)} job(s) waited and no runner was at work: started the runner (pipeline.py run, its "
                    f"output in {run.dir / 'runner.log'}). Say so in a line; its results are collected as they come."}


def collect_acknowledgements(run: Run) -> None:
    """Record the inbox items each stream's committed Progress acknowledges (inbox.py collect), so that what a
    stream has taken in shows while the run is under way, not only at its merge."""
    for s in run.plan["streams"]:
        try:
            inbox.collect(Path(s["brief"]).stem, run.root / inbox.FOLDER, run.root)
        except (inbox.InboxError, OSError, Problem):
            pass


def tend(run: Run) -> dict | None:
    """The watcher's part in the queue, at each look of `wait`. A verification loop running here keeps it as it
    did (it runs, collects and commits, in sessions of its own), and the watcher only announces jobs to it
    (watch.py's tend_queue). Otherwise the watcher keeps it: it collects and commits what is back, and starts the
    runner when jobs wait. Returns what to tell the watcher, if anything."""
    if watch.verification_running(run.root):
        return watch.tend_queue(run)
    try:
        got = collect(run)
    except Problem as e:
        if run.read().get("collectFailed") == str(e):
            return None  # said once; the next look tries again
        run.update(collectFailed=str(e))
        return {"kind": "attention", "what": f"the results that are back could not be collected: {e}",
                "note": "read why and put it right if it is small (the run-verification skill's step 3); else tell the user"}
    run.update(collectFailed=None)
    if got:
        return {"kind": "results", **got,
                "note": "say what came back in a line. Triage each one in `attention` as the run-verification skill's "
                        "step 4 says, and record what needs a person in verification/findings.md (its step 5): a "
                        "verdict goes to the stream it concerns too, through its inbox; a job out of time or memory "
                        "is resubmitted (`pipeline.py resubmit ID ...`). Commit what you changed with `sync.py commit "
                        "--only $(python3 verification/pipeline.py commit-paths)`"
                        if got["attention"] else "say what came back in a line: every job passed"}
    status = queue(run.root)
    return start_runner(run, status) if status else None


# -- the run

def cmd_start(run: Run) -> int:
    data = run.read()
    if watch.alive((data.get("run") or {}).get("pid")):
        print(f"the run is already under way (pid {data['run']['pid']})")
        return 0
    check = preflight(run)
    if check["blocking"]:
        print(json.dumps({"blocking": check["blocking"]}, indent=1), file=sys.stderr)
        return 1
    run.dir.mkdir(parents=True, exist_ok=True)
    for name in ("ended.seen",):
        (run.dir / name).unlink(missing_ok=True)
    env = {**os.environ, "RUN_STREAMS_WATCHER": str(run.dir), "RUN_STREAMS_NEW_WINDOW": "no"}
    for key in ("TMUX", "TMUX_PANE"):  # the watcher's pane is not the run's: no status bar is drawn on it
        env.pop(key, None)
    with open(run.dir / "streams.log", "a") as out:
        p = subprocess.Popen([str(run.root / "llm-dlc/tools/run-streams.sh"), run.brief], cwd=run.root, env=env,
                             stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
    run.update(run={"pid": p.pid, "started": conductor.now(), "log": str(run.dir / "streams.log")}, told=[], lastSummary=None)
    print(f"started the run of {run.brief} (pid {p.pid}); its output: {run.dir / 'streams.log'}")
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
            "openDecisions": record,
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
    lines = [f"### {watch.clock(watch.now())} UTC · {s['elapsed'] or 'not started'} into the run of {s['brief']} · ${s['spent']:.2f}"]
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
                     + f", ${r['spent']:.2f}" + (f"; at {r['head']}" if r["head"] and (not was or was.get("head") != r["head"]) else ""))
        spans = [f"{watch.span(v)} {k}" for k, v in (r.get("time") or {}).items() if v >= 60]
        if spans:
            lines.append("  - time: " + ", ".join(spans))
    if s["integration"]:
        lines.append(f"- integration: {s['integration']}")
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
        return {"kind": "question", "event": {**event, "secondsLeft": int(event["deadline"] - time.time())},
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
    for name in ("preflight", "land", "start", "status", "collect"):
        sub.add_parser(name).add_argument("brief")
    m = sub.add_parser("merge")
    m.add_argument("brief")
    m.add_argument("stream")
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
            return cmd_foundation(run, args.model, args.effort, args.memory, args.prompt)
        if args.command == "land":
            return cmd_land(run)
        if args.command == "start":
            return cmd_start(run)
        if args.command == "merge":
            return cmd_merge(run, args.stream)
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

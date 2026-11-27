"""What the tools of a run share (single_run.py, brief_queue.py, landing.py, queue_keeping.py).

A run is one agent's loop with a watcher outside it. The tools the watcher runs each need the same few things, and
none of them owns these: the clock as a summary prints it, a run's directory and the watcher's state in it, where a
client keeps a session and what a turn of it cost, jj as these tools call it, the workspaces and the loops at work
in a folder, the verification queue as a count, the commits a run made, and the refusal to start a run from
inside one (VF-045).

Until 2026-11-27 these lived in the two controllers that are being retired (llm-dlc/retired.md): the clock, the
state and the refusal in the proof run's, jj and the processes in the streams'. They are here unchanged.

Nothing in this file is a command. Standard library only, and agent_client.py for a Codex worker's readiness.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import agent_client
import conductor


class Problem(Exception):
    pass


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
    """A run's directory and the watcher's own state in it (watch.json). A tool's own Run says where the directory is."""

    def __init__(self, root: Path, directory: Path):
        self.root = root
        self.dir = directory
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


def transcript(root: Path, session: str) -> Path:
    """Where Claude Code keeps a session of this checkout (as feature-loop.sh's project_dir)."""
    projects = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    return projects / re.sub(r"[^A-Za-z0-9]", "-", str(root)) / f"{session}.jsonl"


def turn_cost(run: Run, session: str | None, total: float | None, fresh: bool) -> float | None:
    """What one turn cost. A result's total_cost_usd is the session's running total, so a resumed session's turn is
    its total less the total last seen for that session: None for the first turn seen of a session that was resumed,
    whose earlier total is not known here."""
    if session is None or total is None:
        return None
    totals = run.read().get("sessionTotals") or {}
    before = totals.get(session)
    run.update(sessionTotals={**totals, session: total})
    if before is not None:
        return max(0.0, total - before)
    return total if fresh else None


def head_change(where: Path) -> str | None:
    r = subprocess.run(["jj", "--quiet", "log", "--no-graph", "-r", "@-", "-T", 'change_id.short(8) ++ " " ++ description.first_line()'],
                       capture_output=True, text=True, cwd=where)
    return r.stdout.strip() or None if r.returncode == 0 else None


def store(directory: str | Path) -> str | None:
    """The jj repository a directory's workspace belongs to: every workspace of one repository gives the same."""
    repo = Path(directory) / ".jj" / "repo"
    try:
        if repo.is_dir():
            return str(repo.resolve())
        return str((repo.parent / repo.read_text().strip()).resolve())
    except OSError:
        return None


def detached(command: list[str], root: Path, log: Path) -> int:
    with open(log, "a") as out:
        p = subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                             start_new_session=True)
    return p.pid


def jj(where: Path, *args: str, snapshot: bool = True) -> subprocess.CompletedProcess:
    """jj as these tools call it. Without SNAPSHOT it reads the repository and leaves the working copy unread
    (--ignore-working-copy), which is how a watcher looks at a folder another session is at work in."""
    return subprocess.run(["jj", *([] if snapshot else ["--ignore-working-copy"]), *args], cwd=where,
                          capture_output=True, text=True)


def workspaces(root: Path) -> dict[str, Path | None]:
    """Each jj workspace of the repository, with its folder when jj knows it."""
    out = {}
    for m in re.finditer(r"^([^\s:]+)(?: \(current\))?:", jj(root, "workspace", "list", snapshot=False).stdout, re.M):
        r = jj(root, "workspace", "root", "--name", m[1], snapshot=False)
        out[m[1]] = Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None
    return out


def running(root: Path, script: str) -> list[int]:
    """The processes running SCRIPT (a file name) for this repository, whichever workspace they run in."""
    mine, out = store(root), []
    r = subprocess.run(["pgrep", "-u", str(os.getuid()), "-f", re.escape(script)], capture_output=True, text=True)
    for pid in r.stdout.split():
        try:
            words = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
            theirs = store(os.readlink(f"/proc/{pid}/cwd"))
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


def codex_ready(root: Path) -> list[str]:
    """What stands in the way of a Codex worker here: no client, or one that is not given this checkout's CLAUDE.md."""
    import shutil
    if not shutil.which(os.environ.get("AGENT_CLIENT_CODEX") or "codex"):
        return ["a stream is Codex's, and there is no `codex` on the PATH"]
    return [f"Codex would not be given this checkout's instructions: {p}" for p in agent_client.instructions(root)["problems"]]


def nudge(root: Path) -> str:
    """Say to the pipeline that its queue changed (verification/pipeline.py nudge). What it answers, or why not."""
    r = subprocess.run([sys.executable, str(root / "verification/pipeline.py"), "nudge"], capture_output=True, text=True, cwd=root)
    return r.stdout.strip() if r.returncode == 0 else f"the pipeline took no nudge: {(r.stderr or r.stdout).strip()[-200:]}"


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


NESTED_RUN_OK = "IN_THE_LOOP_NESTED_RUN"  # "allow": the tests' made-up loops, which start stand-in clients only


def enclosing_loop(cgroup: str = "/proc/self/cgroup") -> str | None:
    """The feature loop whose systemd scope this process runs in (feature-loop-NAME), or None. Every loop, single,
    stream or proof, runs its agent in such a scope, and everything the agent starts inherits it."""
    try:
        text = Path(cgroup).read_text()
    except OSError:
        return None
    m = re.search(r"/(feature-loop-[^/\s]+)\.scope(?:/|$)", text, re.M)
    return m.group(1) if m else None


def nested_run_refusal(what: str, cgroup: str = "/proc/self/cgroup") -> str | None:
    """Why WHAT may not start here, or None. A run started from inside a running loop is a new paid agent session
    that nobody asked for: on 2026-11-27 a queued run's agent started a single-agent run of its own for part of its
    brief, and another read the multi-agent skill to run its brief (VF-045). Starting a run is a person's decision,
    and a watcher's at a person's word, never a step of an agent's work."""
    loop = enclosing_loop(cgroup)
    if not loop or os.environ.get(NESTED_RUN_OK) == "allow":
        return None
    return (f"{what} refused: this process runs inside the loop {loop}, and a loop's agent does not start runs, which "
            f"are new paid sessions (VF-045). Say in your report what the work needs (an independent producer, more "
            f"parallel work) and the watcher puts it to the user. Parallel deterministic work goes to verification "
            f"jobs: python3 verification/pipeline.py submit.")


def since_revset(since: str) -> str:
    """A revset for `since` that still names one commit when it is a change id that has turned divergent (VF-049: a
    trace rewrite gave the base change a new commit, a bookmark kept the old one visible, and `BASE..@-` failed, so
    the run's commit list went empty). A change id (jj writes them in the letters k to z) is read as its version on
    this line; a commit id is taken as it is."""
    return f"heads(change_id({since}) & ::@-)" if re.fullmatch(r"[k-z]+", since) else since


def commits(root: Path, since: str | None) -> list[str]:
    """The commits on the loop's line after change `since`, oldest first: `change summary`. All of the last five
    without one."""
    revset = f"{since_revset(since)}..@-" if since else "ancestors(@-, 5)"
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

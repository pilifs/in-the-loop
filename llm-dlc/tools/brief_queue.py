#!/usr/bin/env python3
"""The brief queue: the briefs a watcher runs one after the other, each as a single-agent run (single_run.py), with
a setup phase before it by default (.claude/skills/single-agent-run, "A queue of briefs").

Until 2026-11-23 a watcher kept its queue as prose in its own memory, and the user sent the same message with each
brief: the path, copy it into llm-dlc/loops/, Astra at max effort in the same session, the two prompts, start it
after the current run. The queue is now data any session reads, the message is the defaults below, and the handover
between two briefs is one command.

  llm-dlc/loop-summaries/queue.json   the queue as it stands (gitignored: it changes too often to commit)
  llm-dlc/loops/queue.jsonl           every change to it, one JSON line each, committed with the queue's own commits
  ~/code/scripts/analysis/queue/      the inbox (BRIEF_QUEUE_INBOX overrides it): a brief copied or linked here is
                                      added by the next `inbox` or `next`, in the order the files were put there

Commands (python3 llm-dlc/tools/brief_queue.py COMMAND ...):

  add BRIEF [--name NAME] [--first | --after NAME | --before NAME] [--no-setup] [KEY=VALUE ...]
        put a brief on the queue: its copy goes into llm-dlc/loops/ unchanged and is committed. KEY=VALUE overrides a
        default for this brief alone (the keys of DEFAULTS), as does a front-matter block at the brief's top
        (`---`, `queue.KEY: VALUE` lines, `---`).
  inbox                         add every brief of the inbox that the queue does not have yet
  list | status                 the queue, the run under way, and what `next` would do; `status --json` as data
  move NAME (--first | --after NAME | --before NAME)
  remove NAME                   take a brief off the queue (not one whose run is under way)
  set NAME KEY=VALUE ...        change a brief's settings; `run=RUN` makes the queue follow another run (a fresh
                                session started by hand after a client refused the old one, say)
  defaults [KEY=VALUE ...] [--last-session ID]
                                print or change the queue's defaults; --last-session names the session `previous`
                                continues when the queue has started no domain run yet (the run before the queue's)
  next [--finished]             the handover. It does every step that is due, in order, and records each, so that it
        can be run again after a failure or a crash and carries on where it stopped: bring the inbox in; for the brief
        at the head, move the workspace onto the line and start its setup run; when that has finished, land it, put its
        notes into both copies of the brief and commit; move the workspace onto the line again and start the domain
        run; when that has finished, land it, checkpoint develop, clear what is safe to clear, and go on to the next
        brief. A run that has stopped is taken as finished only with --finished: one stopped to wait on its jobs is
        continued with `single_run.py jobs` and `start`, not handed over. It never promotes `main` and never runs the
        default tests: both are the user's to decide, and it says so when a brief is done.
  report [--json]               each brief with its runs, cycles, landing and state

Standard library only.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import brief_run
import conductor
import single_run

REPO = Path(__file__).resolve().parents[2]
QUEUE = "llm-dlc/loop-summaries/queue.json"
LOG = "llm-dlc/loops/queue.jsonl"
LOOPS = "llm-dlc/loops"
PROMPT_TEMPLATE = "llm-dlc/loops/domain-prompt-{}.md"  # a template's two texts, as the setup agent's template has
# What the user asked for with each brief from 2026-11-19 to 2026-11-23: an Opus 5.5 setup phase first (from
# 2026-11-22), then Codex Astra 6.2 at max effort, continuing the session of the domain run before it, in the
# workspace the domain runs share, with no limit on cycles and the two "aspirational" texts.
DEFAULTS = {
    "setup": single_run.SETUP_MODEL,   # the setup agent's model, or `none` for no setup phase
    "setupEffort": single_run.SETUP_EFFORT,
    "client": "codex",
    "model": "gpt-6.2-astra",
    "effort": "max",
    "session": "previous",             # previous (the last domain run's session), new, or a session id
    "workspace": "foundation-domain-streams",
    "memory": "20G",
    "cycles": "0",
    "prompt": "aspirational",          # PROMPT_TEMPLATE's name
}
STEPS_SETUP = ("setup-start", "setup-land", "notes")
STEPS_DOMAIN = ("domain-start", "domain-land", "checkpoint", "cleanup")
ORDER = ("first", "after", "before")


class Problem(Exception):
    pass


def inbox() -> Path:
    return Path(os.environ.get("BRIEF_QUEUE_INBOX") or "~/code/scripts/analysis/queue").expanduser()


def shown(path: Path) -> str:
    """A path as a person writes it: under the home folder with `~`."""
    try:
        return "~/" + str(path.resolve().relative_to(Path.home().resolve()))
    except ValueError:
        return str(path)


def now() -> str:
    return conductor.now()


@contextlib.contextmanager
def locked(root: Path):
    """The queue, read and written under one lock: two sessions changing it at once would lose a change."""
    path = root / QUEUE
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            data = {}
        data.setdefault("defaults", {})
        data.setdefault("entries", [])
        yield data
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1) + "\n")
        os.replace(tmp, path)


def read(root: Path) -> dict:
    try:
        data = json.loads((root / QUEUE).read_text())
    except (OSError, ValueError):
        data = {}
    data.setdefault("defaults", {})
    data.setdefault("entries", [])
    return data


def who() -> str:
    """Who changed the queue, for its log: a person at a terminal, or the session whose shell ran the command, named
    by the id its client gives it (sessions are published under those ids with their logs)."""
    if single_run.person_at_terminal():
        return "a person, at their terminal"
    if os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return f"Claude Code session {os.environ['CLAUDE_CODE_SESSION_ID']}"
    if os.environ.get("CODEX_THREAD_ID"):
        return f"Codex thread {os.environ['CODEX_THREAD_ID']}"
    return "a session"


def inbox_briefs(folder: Path) -> list[Path]:
    """The inbox's briefs in the order they were put there: by the time of the file itself (a link's own time, not
    its target's), then by name. Until 2026-11-24 they went by name alone, and a later brief whose name sorted first
    jumped ahead."""
    return sorted(folder.glob("*.md"), key=lambda p: (p.lstat().st_mtime, p.name))


def log(root: Path, action: str, name: str | None, **fields) -> None:
    path = root / LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps({"time": now(), "action": action, **({"name": name} if name else {}), "by": who(), **fields}) + "\n")


def changed(root: Path, paths: list[str]) -> list[str]:
    """Which of these files the working copy has changed."""
    return [p for p in paths if brief_run.jj(root, "diff", "-r", "@", "--name-only", "--", p).stdout.strip()]


def commit(root: Path, paths: list[str], title: str, body: str) -> None:
    """Commit these files alone, as CLAUDE.md says (`sync.py commit --only`); a failure that left them uncommitted
    stops the step. Files that did not change are left out."""
    paths = changed(root, paths)
    if not paths:
        return
    r = subprocess.run([sys.executable, str(root / "llm-dlc/tools/sync.py"), "commit", "--only", *paths, "-m", title,
                        "-m", body], cwd=root, capture_output=True, text=True)
    left = brief_run.jj(root, "diff", "-r", "@", "--name-only", "--", *paths).stdout.split()
    if left:
        raise Problem(f"could not commit {', '.join(left)}: {(r.stderr or r.stdout).strip()[-600:]}")


def checkpoint(root: Path) -> dict:
    """Put the line's last commit on develop (sync.py checkpoint): unattended, as the user decided on 2026-11-21."""
    r = subprocess.run([sys.executable, str(root / "llm-dlc/tools/sync.py"), "checkpoint", "--rev", "@-"], cwd=root,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise Problem(f"the develop checkpoint was refused (a refusal is reported, not worked round): "
                      f"{(r.stderr or r.stdout).strip()[-800:]}")
    return {"checkpoint": (r.stdout.strip().splitlines() or ["done"])[-1]}


def artifact_states(root: Path, job: str) -> list[str]:
    """The custody states of a job's sealed originals (artifacts.py), or none when they can't be read."""
    r = subprocess.run([sys.executable, str(root / "llm-dlc/tools/artifacts.py"), "list", "--job", job, "--json"],
                       cwd=root, capture_output=True, text=True)
    try:
        rows = json.loads(r.stdout) if r.returncode == 0 else []
    except ValueError:
        return []
    rows = rows.get("occurrences", rows) if isinstance(rows, dict) else rows
    return [row.get("state") for row in rows if isinstance(row, dict)]


def cleanup(root: Path) -> dict:
    """What is safe to clear between two briefs: the work folders the runner keeps for failed jobs (keep_workdirs =
    "failed"), once every original of the job is remote_verified in the archive. Nothing else is touched."""
    freed, cleared, kept = 0, [], 0
    home = (Path.home() / ".cache" / "in-the-loop").resolve()
    for result in sorted((root / "verification" / "results").glob("**/result.json")):
        try:
            data = json.loads(result.read_text())
        except (OSError, ValueError):
            continue
        work = Path(data.get("workdir") or "")
        if not data.get("workdir") or not work.is_dir():
            continue
        try:
            work.resolve().relative_to(home)
        except ValueError:
            kept += 1  # not where the runner keeps its folders: not this tool's to delete
            continue
        states = artifact_states(root, result.parent.name)
        if not states or any(s != "remote_verified" for s in states):
            kept += 1
            continue
        freed += sum(f.stat().st_size for f in work.rglob("*") if f.is_file() and not f.is_symlink())
        shutil.rmtree(work, ignore_errors=True)
        cleared.append(result.parent.name)
    return {"cleared": len(cleared), "freedGB": round(freed / 2**30, 2), "keptNotYetSealed": kept}


def front_matter(text: str) -> dict:
    """A brief's own settings: `queue.KEY: VALUE` lines in a `---` block at its very top."""
    m = re.match(r"---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        k = re.match(r"\s*queue\.([A-Za-z]+)\s*:\s*(.*?)\s*$", line)
        if k:
            out[k.group(1)] = k.group(2)
    return out


def settings(pairs: list[str]) -> dict:
    out = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise Problem(f"a setting is KEY=VALUE: {pair!r}")
        out[key.strip()] = value.strip()
    return out


def checked(over: dict, allow_run: bool = False) -> dict:
    keys = set(DEFAULTS) | ({"run"} if allow_run else set())
    unknown = sorted(set(over) - keys)
    if unknown:
        raise Problem(f"unknown setting(s) {', '.join(unknown)}: the keys are {', '.join(sorted(keys))}")
    if "cycles" in over and not str(over["cycles"]).isdigit():
        raise Problem("cycles is a count, 0 for no limit")
    return over


def effective(data: dict, entry: dict) -> dict:
    return {**DEFAULTS, **data["defaults"], **entry.get("settings", {})}


def name_for(path: Path, taken: set[str]) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
    stem = re.sub(r"-brief$", "", stem)[:40].strip("-") or "brief"
    name, n = stem, 2
    while name in taken:
        name, n = f"{stem}-{n}", n + 1
    return name


def placed(entries: list[dict], entry: dict, where: str | None, other: str | None) -> None:
    if where is None:
        entries.append(entry)
        return
    if where == "first":
        at = next((i for i, e in enumerate(entries) if e["state"] == "queued"), len(entries))
        entries.insert(at, entry)
        return
    i = next((i for i, e in enumerate(entries) if e["name"] == other), None)
    if i is None:
        raise Problem(f"no brief {other} on the queue")
    entries.insert(i + 1 if where == "after" else i, entry)


def position(a: argparse.Namespace) -> tuple[str | None, str | None]:
    if getattr(a, "first", False):
        return "first", None
    if getattr(a, "after", None):
        return "after", a.after
    if getattr(a, "before", None):
        return "before", a.before
    return None, None


def add(root: Path, source: Path, name: str | None = None, where: str | None = None, other: str | None = None,
        over: dict | None = None) -> dict:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise Problem(f"no brief at {source}")
    text = source.read_text()
    over = {**front_matter(text), **(over or {})}
    checked(over)
    copy = f"{LOOPS}/{source.name}"
    try:
        inside = source.relative_to(root.resolve())
    except ValueError:
        inside = None
    with locked(root) as data:
        for e in data["entries"]:
            if Path(e["source"]).expanduser().resolve() == source and e["state"] != "removed":
                raise Problem(f"{shown(source)} is on the queue already, as {e['name']}")
        taken = {e["name"] for e in data["entries"]}
        name = name or name_for(source, taken)
        if name in taken:
            raise Problem(f"a brief named {name} is on the queue already")
        single_run.Run(root, name + "-setup")  # the name must make valid run names
        target = root / copy
        if inside is None:
            if target.exists() and target.read_text() != text:
                raise Problem(f"{copy} exists and differs from {shown(source)}: name the brief's file differently")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        else:
            copy = str(inside)
        entry = {"name": name, "source": shown(source), "copy": copy, "settings": over, "state": "queued", "done": [],
                 "runs": {}, "added": now()}
        placed(data["entries"], entry, where, other)
    log(root, "add", name, source=shown(source), copy=copy, settings=over, **({"position": where, "other": other} if where else {}))
    commit(root, [copy, LOG], f"Queue the brief {name}",
           f"The brief {shown(source)} is copied unchanged to {copy} and put on the brief queue "
           f"(llm-dlc/tools/brief_queue.py), {'at the head' if where == 'first' else f'{where} {other}' if where else 'at the end'}"
           + (f", with its own settings {json.dumps(over)}" if over else "") + ".")
    return entry


def take_inbox(root: Path) -> list[str]:
    folder = inbox()
    if not folder.is_dir():
        return []
    known = {Path(e["source"]).expanduser().resolve() for e in read(root)["entries"] if e["state"] != "removed"}
    added = []
    for path in inbox_briefs(folder):
        if path.resolve() not in known:
            added.append(add(root, path)["name"])
    return added


def run_tool(root: Path, *args: str) -> dict:
    """A single_run.py command, in this process: what it printed, as data, or the problem it named."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = single_run.main([str(a) for a in args], root=root)
    if status != 0:
        raise Problem(f"single_run.py {' '.join(map(str, args[:2]))}: {(err.getvalue() or out.getvalue()).strip()}")
    try:
        return json.loads(out.getvalue())
    except ValueError:
        return {"output": out.getvalue().strip()}


def onto_line(root: Path, workspace: str) -> str:
    """The workspace, moved to the line's last commit so that a run starts from everything landed: refused while it
    holds uncommitted work or commits the line lacks. A workspace that does not exist yet is made by `start`."""
    known = brief_run.workspaces(root)
    if workspace not in known:
        return "made by the run's start"
    folder = known[workspace]
    if folder is None or not folder.is_dir():
        raise Problem(f"jj knows the workspace {workspace} but not its folder")
    heads = brief_run.jj(root, "log", "--no-graph", "-r", "@-", "-T", 'commit_id ++ "\n"').stdout.split()
    if len(heads) != 1:
        raise Problem("the default workspace is in the middle of a merge: commit it first")
    if brief_run.commit_id(root, f"{workspace}@-") == heads[0]:
        return "on the line already"
    dirty = [f for f in brief_run.jj(folder, "diff", "-r", "@", "--name-only").stdout.splitlines() if f.strip()]
    left = [f for f in dirty if not brief_run.regenerable(folder, f)]
    if left:
        raise Problem(f"the workspace {workspace} has uncommitted files ({', '.join(left[:5])}): land or finish them first")
    if not brief_run.merged_in(root, workspace):
        raise Problem(f"the workspace {workspace} has commits the line lacks: land its run first")
    if dirty:
        brief_run.jj(folder, "restore", "--", *dirty)  # generated trace output only: sync.py writes it again
    r = brief_run.jj(folder, "new", heads[0])
    if r.returncode != 0:
        raise Problem(f"could not move the workspace {workspace} onto the line: {r.stderr.strip()}")
    return f"moved onto {heads[0][:12]}"


def prompt_files(root: Path, entry: dict, s: dict) -> tuple[Path, Path]:
    template = root / PROMPT_TEMPLATE.format(s["prompt"])
    try:
        first, cont = single_run.setup_texts(template.read_text(), entry["source"], "")
    except OSError:
        raise Problem(f"no prompt template {template.relative_to(root)}")
    folder = Path.home() / ".cache" / "in-the-loop" / "prompts"
    folder.mkdir(parents=True, exist_ok=True)
    paths = folder / f"{entry['name']}-prompt.txt", folder / f"{entry['name']}-continue.txt"
    paths[0].write_text(first)
    paths[1].write_text(cont)
    return paths


def run_state(root: Path, name: str) -> str:
    run = single_run.Run(root, name)
    data = run.read()
    if not data.get("session"):
        return "none"
    return "running" if run.running() else "stopped"


def step(root: Path, data: dict, entry: dict, s: dict, name: str, finished: bool) -> dict | None:
    """Do one step. None means it is done; a dict means stop here (a run started, or one is under way or stopped)."""
    if name in ("setup-start", "domain-start"):
        kind = name.split("-")[0]
        run = entry["runs"].get(kind) or (entry["name"] + "-setup" if kind == "setup" else entry["name"])
        state = run_state(root, run)
        if state != "none":  # started by an earlier `next` that was cut off before it recorded the step
            entry["runs"][kind] = run
            return None
        moved = onto_line(root, s["workspace"])
        common = ["--workspace", s["workspace"], "--memory", s["memory"], "--cycles", s["cycles"]]
        if kind == "setup":
            out = run_tool(root, "setup", run, "--brief", entry["copy"], "--model", s["setup"], "--effort", s["setupEffort"], *common)
        else:
            first, cont = prompt_files(root, entry, s)
            session = data.get("lastSession") if s["session"] == "previous" else None if s["session"] == "new" else s["session"]
            out = run_tool(root, "start", run, "--prompt-file", first, "--continue-file", cont, "--brief", entry["copy"],
                           "--client", s["client"], "--model", s["model"], "--effort", s["effort"], *common,
                           *(["--session", session] if session else []))
            data["lastSession"] = out.get("session") or session
        entry["runs"][kind] = run
        entry["state"] = kind
        return {"started": run, "workspace": moved, "session": out.get("session"), "model": out.get("model"),
                "next": f"watch it (`single_run.py wait {run}` as a background task); when it has finished, "
                        f"`brief_queue.py next --finished`"}
    if name in ("setup-land", "domain-land"):
        run = entry["runs"][name.split("-")[0]]
        state = run_state(root, run)
        if state == "running":
            return {"underWay": run, "next": f"`single_run.py wait {run}`: nothing to hand over yet"}
        if not finished:
            return {"stopped": run, "next": f"if {run} has finished, `brief_queue.py next --finished`; if it only waits on "
                                            f"its jobs, `single_run.py jobs {run}` and then `single_run.py start {run}`"}
        landed = single_run.Run(root, run).read().get("landed")
        if not landed and single_run.Run(root, run).read().get("workspace"):
            # The watcher's verdicts on the run, and the queue's log, are committed first: a landing that needs a
            # merge refuses while the default workspace has uncommitted files.
            mine = [f"llm-dlc/decisions/single-{run}.jsonl", f"llm-dlc/decisions/single-{run}.md", LOG]
            commit(root, mine, f"Record the watcher's decisions on {run}",
                   f"The watcher's verdicts on the single-agent run {run} (llm-dlc/decisions/single-{run}.jsonl), committed "
                   f"before the run lands, with the brief queue's log.")
            out = run_tool(root, "land", run)
            entry.setdefault("landed", {})[run] = out.get("commit") or out.get("landed")
        return None
    if name == "notes":
        run = entry["runs"]["setup"]
        source = str(Path(entry["source"]).expanduser())
        out = run_tool(root, "notes", run, "--to", source)
        log(root, "notes", entry["name"], changed=out.get("changed", []))
        commit(root, [entry["copy"], LOG], f"Put the setup notes of {entry['name']} into its brief",
               f"The setup run {run} ended its record with a 'Setup Agent Notes' section, and brief_queue.py put it into "
               f"{entry['copy']} and {entry['source']}, for the domain agent.")
        return None
    if name == "checkpoint":
        entry["checkpoint"] = checkpoint(root)["checkpoint"]
        return None
    if name == "cleanup":
        entry["cleanup"] = cleanup(root)
        return None
    raise Problem(f"no step {name}")


def steps_of(s: dict) -> tuple[str, ...]:
    return (STEPS_SETUP if s["setup"] != "none" else ()) + STEPS_DOMAIN


def cmd_next(root: Path, finished: bool) -> dict:
    report = {"inbox": take_inbox(root), "done": [], "steps": []}
    while True:
        with locked(root) as data:
            entry = next((e for e in data["entries"] if e["state"] not in ("done", "removed")), None)
            if entry is None:
                report["next"] = "the queue is empty: nothing to start"
                break
            s = effective(data, entry)
            todo = [n for n in steps_of(s) if n not in entry["done"]]
            stop = None
            for name in todo:
                try:
                    stop = step(root, data, entry, s, name, finished)
                except Problem as e:
                    entry["problem"] = f"{name}: {e}"
                    report.update(brief=entry["name"], failedAt=name, problem=str(e),
                                  next="fix what it names, then run `brief_queue.py next` again: it carries on from this step")
                    stop = "failed"
                    break
                if stop is not None and name in ("setup-start", "domain-start"):
                    entry["done"].append(name)  # the start is the step; the run is what comes after it
                    entry.pop("problem", None)
                if stop is not None:
                    break
                entry["done"].append(name)
                entry.pop("problem", None)
                report["steps"].append(f"{entry['name']}: {name}")
                finished = finished and name not in ("setup-land",)  # --finished speaks for the run that had stopped
            name = entry["name"]
            if stop is None:
                entry["state"] = "done"
                entry["ended"] = now()
                report["done"].append(name)
        if stop == "failed":
            log(root, "failed", name, step=report["failedAt"], problem=report["problem"])
            break
        if stop is None:
            log(root, "done", name)
            report.setdefault("forTheUser", []).append(
                f"{name} is landed and on develop: promoting main and running the default tests are yours to decide")
            finished = False
            continue
        report.update(brief=name, **stop)
        if "started" in stop:
            log(root, "start", name, run=stop["started"], session=stop.get("session"))
        break
    try:  # what this call did is in the log: committed now, so that the default workspace is left clean
        commit(root, [LOG], "Record the brief queue's handover",
               "The brief queue's log (llm-dlc/loops/queue.jsonl) records what `brief_queue.py next` did: the steps it "
               "took, the runs it started, and the briefs it finished.")
    except Problem as e:
        report["logNotCommitted"] = str(e)
    return report


def describe(root: Path) -> dict:
    data = read(root)
    rows = []
    for e in data["entries"]:
        if e["state"] == "removed":
            continue
        s = effective(data, e)
        runs = {k: f"{v} ({run_state(root, v)})" for k, v in e.get("runs", {}).items()}
        due = next((n for n in steps_of(s) if n not in e["done"]), None)
        rows.append({"name": e["name"], "state": e["state"], "source": e["source"], "runs": runs, "nextStep": due,
                     **({"problem": e["problem"]} if e.get("problem") else {}),
                     "agent": f"{s['client']} {s['model']} {s['effort']}, session {s['session']}",
                     "setup": s["setup"]})
    folder = inbox()
    known = {Path(e["source"]).expanduser().resolve() for e in data["entries"] if e["state"] != "removed"}
    waiting = [shown(p) for p in inbox_briefs(folder)] if folder.is_dir() else []
    waiting = [w for w in waiting if Path(w).expanduser().resolve() not in known]
    return {"queue": rows, "inboxNotYetAdded": waiting, "lastSession": data.get("lastSession"),
            "defaults": {**DEFAULTS, **data["defaults"]}}


def cmd_report(root: Path) -> list[dict]:
    rows = []
    for e in read(root)["entries"]:
        if e["state"] == "removed":
            continue
        runs = []
        for kind, name in e.get("runs", {}).items():
            run = single_run.Run(root, name)
            cycles = sum(1 for ev in conductor.read_events(run.dir) if ev.get("type") == "cycle-start") if run.dir.exists() else 0
            legs = len(run.read().get("legs") or [])
            runs.append({"kind": kind, "run": name, "state": run_state(root, name), "legs": legs,
                         "cyclesThisLeg": cycles, "landed": run.read().get("landed")})
        rows.append({"name": e["name"], "state": e["state"], "added": e.get("added"), "ended": e.get("ended"),
                     "runs": runs, "checkpoint": e.get("checkpoint"), "cleanup": e.get("cleanup")})
    return rows


def main(argv: list[str] | None = None, root: Path = REPO) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="command", required=True)

    def where(p):
        g = p.add_mutually_exclusive_group()
        g.add_argument("--first", action="store_true")
        g.add_argument("--after")
        g.add_argument("--before")
        return p

    a = where(sub.add_parser("add", help="put a brief on the queue"))
    a.add_argument("brief")
    a.add_argument("--name")
    a.add_argument("--no-setup", action="store_true")
    a.add_argument("settings", nargs="*", metavar="KEY=VALUE")
    sub.add_parser("inbox", help="add the inbox's new briefs")
    for c in ("list", "status"):
        sub.add_parser(c, help="the queue and what `next` would do").add_argument("--json", action="store_true")
    m = where(sub.add_parser("move", help="move a brief"))
    m.add_argument("name")
    sub.add_parser("remove", help="take a brief off the queue").add_argument("name")
    s = sub.add_parser("set", help="change a brief's settings")
    s.add_argument("name")
    s.add_argument("settings", nargs="+", metavar="KEY=VALUE")
    d = sub.add_parser("defaults", help="print or change the defaults")
    d.add_argument("settings", nargs="*", metavar="KEY=VALUE")
    d.add_argument("--last-session")
    sub.add_parser("next", help="the handover: every step that is due").add_argument("--finished", action="store_true")
    sub.add_parser("report", help="each brief's runs and state").add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    root = (args.root or root).resolve()
    try:
        if args.command == "add":
            over = settings(args.settings)
            if args.no_setup:
                over["setup"] = "none"
            w, other = position(args)
            print(json.dumps(add(root, Path(args.brief), args.name, w, other, over), indent=1))
        elif args.command == "inbox":
            print(json.dumps({"added": take_inbox(root)}, indent=1))
        elif args.command in ("list", "status"):
            d = describe(root)
            if args.json:
                print(json.dumps(d, indent=1))
            else:
                for i, r in enumerate(d["queue"], 1):
                    runs = ", ".join(f"{k}: {v}" for k, v in r["runs"].items()) or "no run yet"
                    print(f"{i}. {r['name']} [{r['state']}] {r['source']}: {runs}; next step {r['nextStep'] or '-'}"
                          + (f"; PROBLEM {r['problem']}" if r.get("problem") else ""))
                if d["inboxNotYetAdded"]:
                    print("inbox, not yet added: " + ", ".join(d["inboxNotYetAdded"]))
                if not d["queue"] and not d["inboxNotYetAdded"]:
                    print("the queue is empty")
        elif args.command == "move":
            w, other = position(args)
            if w is None:
                raise Problem("say where: --first, --after NAME or --before NAME")
            with locked(root) as data:
                e = next((e for e in data["entries"] if e["name"] == args.name and e["state"] != "removed"), None)
                if e is None:
                    raise Problem(f"no brief {args.name} on the queue")
                if e["state"] != "queued":
                    raise Problem(f"{args.name} has started ({e['state']}): only a brief still waiting moves")
                data["entries"].remove(e)
                placed(data["entries"], e, w, other)
            log(root, "move", args.name, position=w, other=other)
            print(json.dumps(describe(root)["queue"], indent=1))
        elif args.command == "remove":
            with locked(root) as data:
                e = next((e for e in data["entries"] if e["name"] == args.name and e["state"] != "removed"), None)
                if e is None:
                    raise Problem(f"no brief {args.name} on the queue")
                if any(run_state(root, r) == "running" for r in e.get("runs", {}).values()):
                    raise Problem(f"a run of {args.name} is under way: stop it first (`single_run.py stop`)")
                e["state"] = "removed"
            log(root, "remove", args.name)
            print(json.dumps({"removed": args.name}, indent=1))
        elif args.command == "set":
            over = checked(settings(args.settings), allow_run=True)
            with locked(root) as data:
                e = next((e for e in data["entries"] if e["name"] == args.name and e["state"] != "removed"), None)
                if e is None:
                    raise Problem(f"no brief {args.name} on the queue")
                if "run" in over:
                    kind = "domain" if "domain-start" in e["done"] or e["state"] == "domain" else "setup"
                    single_run.Run(root, over["run"])
                    e["runs"][kind] = over.pop("run")
                e.setdefault("settings", {}).update(over)
            log(root, "set", args.name, settings=over)
            print(json.dumps(next(r for r in describe(root)["queue"] if r["name"] == args.name), indent=1))
        elif args.command == "defaults":
            over = checked(settings(args.settings))
            if args.last_session and not brief_run.SESSION.fullmatch(args.last_session):
                raise Problem(f"not a session id: {args.last_session}")
            if over or args.last_session:
                with locked(root) as data:
                    data["defaults"].update(over)
                    if args.last_session:
                        data["lastSession"] = args.last_session
                log(root, "defaults", None, settings=over, **({"lastSession": args.last_session} if args.last_session else {}))
            print(json.dumps({**DEFAULTS, **read(root)["defaults"], "lastSession": read(root).get("lastSession")}, indent=1))
        elif args.command == "next":
            print(json.dumps(cmd_next(root, args.finished), indent=1))
        elif args.command == "report":
            rows = cmd_report(root)
            if args.json:
                print(json.dumps(rows, indent=1))
            else:
                for r in rows:
                    runs = "; ".join(f"{x['kind']} {x['run']} {x['state']}, {x['legs']} leg(s)"
                                     + (f", landed {str(x['landed'])[:12]}" if x["landed"] else "") for x in r["runs"]) or "not started"
                    print(f"- {r['name']} [{r['state']}]: {runs}" + (f"; ended {r['ended']}" if r.get("ended") else ""))
    except (Problem, single_run.Problem) as e:
        print(f"brief_queue.py: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

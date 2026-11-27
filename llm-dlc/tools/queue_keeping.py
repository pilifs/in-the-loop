"""The verification queue, as the watcher of a run keeps it.

Agents queue proofs and model checks as jobs and go on (verification/README.md). While a run is under way its
watcher keeps the queue itself, at each look of `wait` (single_run.py wait, collect and jobs):

  - `collect` collects the results that are back (jobs/pipeline.py collect) and commits them with the paths
    a commit of results holds and nothing else, so that the watcher is the one session that commits in the default
    working copy;
  - `start_runner` starts the runner (pipeline.py run, no model) when jobs this machine can run wait and none is at
    work, and announces a job that came while one was;
  - `tend` does both, and returns only what the watcher has to hear of: results that came back, with the ones to
    triage, or a runner it started.

Until 2026-11-27 this was part of the controllers of two retired workflows, and a verification loop (a Sonnet
session for each run of the queue) could keep the queue in the watcher's place (llm-dlc/retired.md).

Nothing in this file is a command. Standard library only.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import conductor
from landing import writer
from run_common import CAN_START, OUTSTANDING, Problem, Run, alive, detached, head_change, in_state, nudge, pipeline_path
import run_common


QUEUE_LOOK = 30  # seconds between two looks of `wait` at the verification queue


def _verification_layout():
    """verification/layout.py: where a job and its result are kept, by id (flat, or under the day it was submitted)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("verification_layout", Path(__file__).resolve().parents[2] / "verification" / "layout.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


layout = _verification_layout()


def pipeline(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(pipeline_path(root)), *args], cwd=root,
                          capture_output=True, text=True, stdin=subprocess.DEVNULL)


def queue(root: Path) -> dict | None:
    """The pipeline's view of every job, or None when the queue could not be read (run_common.view)."""
    return run_common.view(root)


def left(view: dict | None) -> int | None:
    """How many jobs the queue still has work on here: None when it could not be read, which is not zero."""
    return None if view is None else len(in_state(view, *OUTSTANDING))


def collect(run: Run) -> dict | None:
    """Collect the results that are back (jobs/pipeline.py collect --json) and commit them with the paths a commit
    of results holds and nothing else (`sync.py commit --only $(pipeline.py commit-paths)`), as the verification
    loop's sessions did: the watcher is then the one session that commits in the default working copy while a
    run is under way, its merges and its collections one after the other. None when nothing waited. What is in
    `attention` (a job that did not pass, outputs not applied, anything a result flags) is for the watcher to
    triage."""
    root = run.root
    with writer(root):
        status = queue(root)
        if not status or not in_state(status, "finished"):
            return None
        r = pipeline(root, "collect", "--json")
        try:
            said = json.loads(r.stdout) if r.returncode == 0 else None
        except ValueError:
            said = None
        if said is None:
            raise Problem(f"pipeline.py collect failed: {(r.stderr or r.stdout).strip()[-600:]}")
        ids = [row["id"] for row in said["collected"]]
        if not ids:
            return None  # every result here was collected before (a collect that was stopped): nothing new to commit
        title, body = said["commit"]["summary"], said["commit"]["body"]
        hooks = [h for h in said.get("hooks") or [] if h.get("exitCode")]
        paths = pipeline(root, "commit-paths").stdout.split()
        c = subprocess.run([sys.executable, str(root / "llm-dlc" / "tools" / "sync.py"), "commit", "--only", *paths,
                            "-m", title, "-m", f"{body} Collected by the watcher of the {run.name} run, which keeps the "
                                               f"queue while the run is under way."],
                           cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    results, attention = [], []
    for job in ids:
        try:
            result = json.loads(((layout.find_result(root, job) or root / layout.result_rel(job)) / "result.json").read_text())
        except (OSError, ValueError):
            result = {}
        row = {"id": job, "status": result.get("status", "?"), "summary": result.get("summary")}
        flags = list(result.get("attention") or []) + [f"output not applied: {f}" for f in
                                                       (result.get("collected") or {}).get("conflicts") or []]
        if row["status"] != "passed" or flags:
            attention.append({**row, "attention": flags})
        results.append(row)
    for hook in hooks:  # the results are in; what regenerates from them did not run through, and that needs someone
        attention.append({"id": None, "status": "hook failed", "summary": f"after collect: {hook['command']}: exit {hook['exitCode']}",
                          "attention": [hook.get("output") or ""]})
    out = {"collected": results, "attention": attention, "commit": head_change(root)}
    if c.returncode != 0:
        out["commitReported"] = (c.stderr or c.stdout).strip()[-600:]
    return out


def start_runner(run: Run, status: dict) -> dict | None:
    """Start the runner (jobs/pipeline.py run, no model) when jobs this machine can run wait and no runner
    is at work. It takes the budget the runner's settings give (`budget --apply`), runs until the queue
    is empty and ends; the next look starts it again when more jobs come. A job committed while it runs is
    announced to it (nudge), once."""
    root = run.root
    waiting = in_state(status, *CAN_START)   # not the ones that are blocked, invalid, or more than this machine runs
    data = run.read()
    if not waiting:
        if data.get("nudged"):
            run.update(nudged=[])
        return None
    ours = (data.get("runner") or {}).get("pid")
    at_work = alive(ours) or status["runner"]["atWork"]
    if at_work:
        if [j for j in waiting if j not in (data.get("nudged") or [])]:
            nudge(root)
            run.update(nudged=waiting)
        return None
    run.dir.mkdir(parents=True, exist_ok=True)
    pid = detached([sys.executable, str(pipeline_path(root)), "run"], root, run.dir / "runner.log")
    run.update(runner={"pid": pid, "started": conductor.now(), "jobs": waiting}, nudged=waiting)
    return {"kind": "verification", "pid": pid, "jobs": waiting,
            "note": f"{len(waiting)} job(s) waited and no runner was at work: started the runner (pipeline.py run, its "
                    f"output in {run.dir / 'runner.log'}). Say so in a line; its results are collected as they come."}


def tend(run: Run) -> dict | None:
    """The watcher's part in the queue, at each look of `wait`. A verification loop running here keeps it as it
    did (it runs, collects and commits, in sessions of its own), and the watcher only announces jobs to it
    (tend_queue, below). Otherwise the watcher keeps it: it collects and commits what is back, and starts the
    runner when jobs wait. Returns what to tell the watcher, if anything."""
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
                        "job out of time or memory "
                        "is resubmitted (`pipeline.py resubmit ID ...`). Commit what you changed with `sync.py commit "
                        "--only $(python3 verification/pipeline.py commit-paths)`"
                        if got["attention"] else "say what came back in a line: every job passed"}
    status = queue(run.root)
    return start_runner(run, status) if status else None

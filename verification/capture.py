"""Hands what the pipeline produces to the private archive (llm-dlc/tools/artifacts.py) before the pipeline shortens,
replaces or deletes it. pipeline.py calls the five functions below at the points where an original would otherwise
be lost; everything else about the archive is in llm-dlc/specification.md, "Original outputs".

  begin          before a job's run directory is reused: seal what an attempt that never finished left there, then
                 number the new attempt
  sealed_run     after the steps, before the logs are cut to head and tail: the whole step logs, the outputs, the
                 whole diff, and, when the job did not pass, what its work directory holds beyond the commit
  sealed_result  the result as the runner wrote it, before the collector rewrites it
  before_collect a collected result about to be replaced, and a staged result no runner sealed
  after_collect  the result as collected, with what was applied, kept and in conflict

Shadow mode: the pipeline's own files are what they were, and no failure here fails a job or a collect. A capture
that fails is said on stderr and written to the state directory's capture.log, and the function says so to its
caller, which then keeps the source it was about to delete. Nothing is captured for a repository that does not
hold the archive tool (a test's throwaway repository), or when ITL_ORIGINALS_OFF is set.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

RESULTS = "verification/results"
MARKER = ".captured"  # in a run directory: the attempt that wrote it was sealed, with the occurrences it names
_lock = threading.Lock()
_module = None


def tool(root):
    """artifacts.py as a module, or None where there is none to use."""
    global _module
    if os.environ.get("ITL_ORIGINALS_OFF"):
        return None
    path = Path(os.environ.get("ITL_ARTIFACTS") or Path(root) / "llm-dlc/tools/artifacts.py")
    if not path.exists():
        return None
    with _lock:
        if _module is None or _module.__file__ != str(path):
            spec = importlib.util.spec_from_file_location("itl_artifacts", path)
            _module = importlib.util.module_from_spec(spec)
            sys.modules["itl_artifacts"] = _module
            spec.loader.exec_module(_module)
    return _module


def _said(state, job_id, what, error):
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {job_id}: {what}: {type(error).__name__}: {error}"
    print(f"warn  capture: {line}", file=sys.stderr, flush=True)
    try:
        with open(Path(state) / "capture.log", "a") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _marker(run_dir):
    try:
        return json.loads((Path(run_dir) / MARKER).read_text())
    except (OSError, ValueError):
        return None


def _git_blob(path):
    h = hashlib.sha1()
    h.update(b"blob %d\0" % path.stat().st_size)
    with open(path, "rb") as f:
        while data := f.read(1 << 20):
            h.update(data)
    return h.hexdigest()


def beyond_commit(root, work, source):
    """A rule for capture(): leave out of a work directory every file the source commit already holds, byte for
    byte (git has it), and the folders that are then empty. What is left is what the job made or changed."""
    listed = subprocess.run(["git", "ls-tree", "-r", "-z", source], cwd=root, capture_output=True)
    committed = {}
    for row in filter(None, listed.stdout.split(b"\0")) if listed.returncode == 0 else []:
        meta, _, path = row.partition(b"\t")
        committed[path.decode(errors="surrogateescape")] = meta.split()[2].decode()

    def exclude(rel, is_dir):
        if is_dir or rel not in committed:
            return False
        full = Path(work) / rel
        try:
            return not full.is_symlink() and _git_blob(full) == committed[rel]
        except OSError:
            return False
    return exclude


def _parts(arch, job, attempt, source, run_dir, work, result, root, status, why=None):
    """Seal a run directory's logs, outputs and diff, and the work directory of a job that did not pass."""
    job_id, run_dir = job["id"], Path(run_dir)
    meta = dict(job=job_id, attempt=attempt, run=(job.get("submitted") or {}).get("session"),
                source={"commit": source} if source else None)
    notes = {"why": why} if why else {}
    logical = f"{RESULTS}/{job_id}"
    made = {}
    steps = [s["log"]["path"].split("/", 1)[1] for s in (result or {}).get("steps", []) if s.get("log")]
    if (run_dir / "logs").is_dir() or steps:
        made["logs"] = arch.capture(run_dir / "logs", "job-logs", f"{logical}/logs", expected=steps, status=status,
                                    notes=notes, **meta)
    outputs = (result or {}).get("outputs") or []
    # A declared output the work directory does not hold never materialized; one it holds unchanged is in the commit.
    never = [spec for spec in job.get("outputs") or [] if work is not None and not (Path(work) / spec).exists()]
    if (run_dir / "outputs").is_dir() or outputs or never:
        made["outputs"] = arch.capture(run_dir / "outputs", "job-outputs", f"{logical}/outputs", status=status,
                                       expected=[o["path"] for o in outputs if o["change"] != "deleted"] + never,
                                       deleted=[o["path"] for o in outputs if o["change"] == "deleted"], notes=notes, **meta)
    if (run_dir / "changes.diff").exists():
        made["diff"] = arch.capture(run_dir / "changes.diff", "job-diff", f"{logical}/changes.diff", status=status,
                                    notes=notes, **meta)
    if work is not None and Path(work).is_dir() and (result or {}).get("status") != "passed" and source:
        made["workdir"] = arch.capture(
            work, "job-workdir", f"{logical}/workdir", status=status, sparse=True, exclude=beyond_commit(root, work, source),
            notes={**notes, "rule": "files identical to the source commit are left out, and folders that hold none "
                                    "of the rest: the commit and these members give the work directory back"}, **meta)
    return {k: v["id"] for k, v in made.items() if v}


def begin(root, state, job, source, run_dir, work):
    """Before execute() clears the job's run directory. Returns the new attempt's number, or None without capture."""
    arts = tool(root)
    if arts is None:
        return None
    try:
        arch = arts.Archive()
        try:
            run_dir = Path(run_dir)
            if run_dir.exists() and _marker(run_dir) is None and any(run_dir.iterdir()):
                # An attempt wrote here and was never sealed: its runner was killed, or it ran before capture did.
                last = arch.db.execute("SELECT MAX(attempt) FROM attempts WHERE job=?", (job["id"],)).fetchone()[0]
                _parts(arch, job, last or arch.begin_attempt(job["id"]), source, run_dir, work, None, root, "partial",
                       why="sealed before a retry reused its path: the attempt that wrote it did not finish")
            return arch.begin_attempt(job["id"])
        finally:
            arch.close()
    except Exception as e:
        _said(state, job["id"], "nothing sealed before the run directory was reused", e)
        return None


def sealed_run(root, state, job, attempt, source, run_dir, work, result):
    """After the steps and before anything is shortened or removed. Returns what goes into the result as
    `originals` (the attempt and each occurrence's id), or None."""
    arts = tool(root)
    if arts is None or attempt is None:
        return None
    try:
        arch = arts.Archive()
        try:
            made = _parts(arch, job, attempt, source, run_dir, work, result, root, "complete")
        finally:
            arch.close()
        (Path(run_dir) / MARKER).write_text(json.dumps({"attempt": attempt, "occurrences": made}))
        return {"attempt": attempt, "occurrences": made}
    except Exception as e:
        _said(state, job["id"], "the run was not sealed; its run directory stays on this machine", e)
        return None


def sealed_result(root, state, job, attempt, source, path):
    arts = tool(root)
    if arts is None or attempt is None:
        return None
    try:
        arch = arts.Archive()
        try:
            record = arch.capture(path, "job-result", f"{RESULTS}/{job['id']}/result.json", job=job["id"], attempt=attempt,
                                  run=(job.get("submitted") or {}).get("session"), source={"commit": source} if source else None,
                                  notes={"stage": "as the runner wrote it"})
        finally:
            arch.close()
        return record and record["id"]
    except Exception as e:
        _said(state, job["id"], "the runner's result was not sealed", e)
        return None


def before_collect(root, state, job_id, src, dest, result):
    """Before collect replaces `dest` and, later, removes `src`. Returns False when `src` holds bytes that nothing
    sealed and that could not be sealed now: the caller then sets it aside instead of deleting it."""
    arts = tool(root)
    if arts is None:
        return True
    try:
        arch = arts.Archive()
        try:
            attempt = (result.get("originals") or {}).get("attempt") or \
                arch.db.execute("SELECT MAX(attempt) FROM attempts WHERE job=?", (job_id,)).fetchone()[0]
            meta = dict(job=job_id, attempt=attempt, source={"commit": result.get("sourceCommit")})
            if Path(dest).exists():
                arch.capture(dest, "job-result", f"{RESULTS}/{job_id}", notes={"stage": "a collected result that a later collect replaced"}, **meta)
            if not result.get("originals"):  # staged by a runner that sealed nothing: seal what is here
                arch.capture(src, "job-result", f"{RESULTS}/{job_id}", status="partial", **meta, notes={
                    "stage": "staged by a runner without capture: logs longer than its limit are head and tail here"})
                run_dir = Path(state) / "runs" / job_id
                if run_dir.is_dir() and _marker(run_dir) is None:
                    _parts(arch, {"id": job_id}, attempt, result.get("sourceCommit"), run_dir, None, result, root, "complete",
                           why="sealed at collect: the runner that wrote it had no capture")
                    (run_dir / MARKER).write_text(json.dumps({"attempt": attempt, "at": "collect"}))
        finally:
            arch.close()
        return True
    except Exception as e:
        _said(state, job_id, "the staged result was not sealed; it is set aside, not deleted", e)
        return False


def after_collect(root, state, job_id, dest, result):
    arts = tool(root)
    if arts is None:
        return None
    try:
        arch = arts.Archive()
        try:
            collected = result.get("collected") or {}
            record = arch.capture(Path(dest) / "result.json", "job-result", f"{RESULTS}/{job_id}/result.json", job=job_id,
                                  attempt=(result.get("originals") or {}).get("attempt"),
                                  source={"commit": result.get("sourceCommit")}, conflicts=collected.get("conflicts") or [],
                                  notes={"stage": "as collected", "applied": len(collected.get("applied") or []),
                                         "kept": len(collected.get("kept") or [])})
        finally:
            arch.close()
        return record and record["id"]
    except Exception as e:
        _said(state, job_id, "the collected result was not sealed", e)
        return None

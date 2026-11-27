#!/usr/bin/env python3
"""The jobs pipeline: committed jobs, run asynchronously under resource limits.

An agent that needs a proof, a model check, a build, a test run or a dependency resolution does not run it in its
session. It describes the work as a job (verification/jobs/ID.json) and commits the job with the change, marked
"verification pending". A runner picks committed jobs up as resources permit, runs each one in a clean export of the
commit that holds it, and records what happened in verification/results/ID/. See jobs/README.md, and
verification/README.md for the verification workload.

This file is the one implementation of admission, claiming, execution, collection and reporting. It was
verification/pipeline.py until 2026-11-27, and that path is still an entry point: it runs this file. The records
are where they always were (verification/jobs, verification/results, the state in verification/.state).

Commands:
  submit    write a job file, from flags or a JSON file (--example ID fills in a demo example's job)
  status    the queue: pending (and whether they fit here), running, finished but not collected, collected
  run       run pending jobs under the configured budget, taking the jobs committed meanwhile as well, until
            none is left; --watch keeps it going after that
  nudge     say that the queue changed: a runner looks at once, and so does a loop waiting for work
  wait      block until a job has finished and waits to be collected, or no runner is left
  collect   move finished results into verification/results/, apply their outputs to the working copy
  report    a digest of collected results for a batch read, as Markdown or JSON
  resubmit  a new job from an old one, with other resources (after a timeout or out-of-memory, say)
  validate  check every job and result file against its schema

Configuration: verification/pipeline.toml, then the machine's file (~/.config/in-the-loop/pipeline.local.toml, or
$VERIFY_MACHINE_CONFIG; read by every checkout and workspace on the machine), then verification/pipeline.local.toml
(not committed, this checkout's own), then the file named by $VERIFY_CONFIG, then command-line flags.
"""

import argparse
import datetime as dt
import difflib
import fcntl
import gzip
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import tomllib
from pathlib import Path


def scope_id(job_id):
    """A job id as a systemd scope name: the first 30 characters and a hash of the whole id, since ids that share their
    first 40 characters (a pair of jobs submitted together) would otherwise name the same scope, and a step would stop
    the other's as a leftover of its own name."""
    return f"{job_id[:30]}-{hashlib.sha256(job_id.encode()).hexdigest()[:8]}"

CODE = Path(__file__).resolve().parents[1]    # the checkout this code is in
ROOT = Path(os.environ.get("VERIFY_REPO") or CODE)   # the repository it works for (a test's throwaway one, say)
_CAPTURE = []


def originals():
    """verification/capture.py, which hands the runner's and the collector's originals to the private archive before
    they are shortened, replaced or deleted (llm-dlc/specification.md, "Original outputs"), or None where it is not
    installed beside this file. It never fails a job or a collect."""
    if not _CAPTURE:
        path = CODE / "verification" / "capture.py"
        module = None
        if path.exists():
            spec = importlib.util.spec_from_file_location("verification_capture", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        _CAPTURE.append(module)
    return _CAPTURE[0]
HERE = "verification"
JOBS = f"{HERE}/jobs"
RESULTS = f"{HERE}/results"
# Where a job and its result are, by id: flat as every job until now, or under the day it was submitted
# (layout.py). Every path of a job or a result below comes from there.
_layout = importlib.util.spec_from_file_location("verification_layout", CODE / HERE / "layout.py")
layout = importlib.util.module_from_spec(_layout)
_layout.loader.exec_module(layout)
# The shared record readers (jobs/records.py): the result indexes are computed there, for `collect` to write and
# for the audit (jobs/audit.py) to compare the committed ones with.
_records = importlib.util.spec_from_file_location("jobs_records", Path(__file__).resolve().parent / "records.py")
records = importlib.util.module_from_spec(_records)
_records.loader.exec_module(records)
# Every execution of a job is an attempt with folders of its own (jobs/attempts.py): nothing is cleared for a rerun.
attempts = records.load("jobs_attempts", Path(__file__).resolve().parent / "attempts.py")
PRIORITIES = f"{HERE}/priorities.json"
SCHEMAS = ROOT / HERE / "schema"
JOB_SCHEMA = "verification-job/v1"
JOB_SCHEMA_V2 = "itl-job/v2"
RESULT_SCHEMA = "verification-result/v1"
ID_PATTERN = re.compile(r"^\d{8}-\d{6}-[a-z0-9][a-z0-9-]{0,60}$")

DEFAULTS = {
    "runner": {
        "backend": "local",
        "machine_name": "",           # the name results record for this machine; empty: its hostname
        "isolation": "auto",          # systemd: a scope per step with hard caps; none: timeouts only; auto: systemd if it works
        "workers": 2,                 # jobs at once
        "cpus": 6,                    # CPUs shared out among running jobs
        "memory": "5G",               # memory shared out among running jobs, by their limits
        "job_memory_max": "4G",       # no job's limit above this; a job that needs more waits for a bigger machine
        "max_timeout": "6h",          # the hard ceiling: no step runs longer, working or not
        # Past its timeout a step is stopped only once it has stalled: under 1% of a CPU and no new output for this
        # long. A step still working is left to finish, up to max_timeout, and its result says it overran.
        "stall_window": "10m",
        "build_memory": "3G",         # for building jvmcontract when a job needs it and it is not cached
        # What the machine keeps free. No job starts that would take available memory under it, and when the machine
        # falls under it anyway (an agent's build, a session growing), the runner stops its newest job, so the kernel
        # never has to choose: a job goes before a terminal, an agent or a watcher. 0: no floor.
        "memory_floor": "8G",
        # Every process of a job starts with this oom_score_adj (-1000 to 1000), so that if the machine runs out all
        # the same, the kernel's OOM killer takes a job's process before anything else's (those keep 0). An agent's
        # inline tests and probes take 500 (lib/tools/test_costs.py): after the jobs, before the agents.
        "job_oom_score_adj": 1000,
        "state_dir": f"{HERE}/.state",
        "keep_workdirs": "failed",    # always | failed | never
        "log_max_bytes": "2M",        # longer logs are kept in full locally and as head and tail in the result
        "poll_seconds": 30,
        "link": [],                   # paths outside git linked into every export (none by default)
        "after_collect": [],          # commands run at the repo root after outputs are applied
    },
    "defaults": {"cpus": 1, "memory": "2G", "duration": "10m"},
}

STATUS_ORDER = ["error", "out-of-memory", "timeout", "failed", "cancelled", "passed"]

MAX_SIGNALS = 100   # the verdict lines a step's record carries; every one is counted


# Workloads: what a kind of work means (jobs/workloads/NAME.py). The pipeline owns the rest.

FIRST_FORMAT_WORKLOAD = "verification"   # every job of verification-job/v1 is the verification workload's
_WORKLOADS = {}


def workload(name):
    """The adapter of that name, or None when this checkout has none: its job is then not run here."""
    if name not in _WORKLOADS:
        path = Path(__file__).resolve().parent / "workloads" / f"{name}.py"
        adapter = None
        if re.fullmatch(r"[a-z][a-z0-9_]*", name or "") and path.is_file():
            adapter = records.load(f"jobs_workload_{name}", path)
            adapter.core = sys.modules[__name__]
        _WORKLOADS[name] = adapter
    return _WORKLOADS[name]


def workload_name(job) -> str:
    """Which workload a job is: the one it names, `generic` for one of the second format that names none, and
    the verification workload for every job of the first format, which had no other."""
    if job.get("schema") == JOB_SCHEMA_V2:
        return job.get("workload") or "generic"
    return FIRST_FORMAT_WORKLOAD


def workload_of(job):
    return workload(workload_name(job))


def __getattr__(name):
    # The verdict patterns were a constant of this module while it was the verification pipeline's alone.
    if name == "SIGNALS":
        return workload("verification").SIGNALS
    raise AttributeError(name)


def example_job_parts(example_id, task=None):
    """The parts of a job that runs a numbered example (`submit --example`): the verification workload's."""
    return workload("verification").example_job_parts(example_id, task)


# Small helpers


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t):
    return t.isoformat() if t else None


def parse_bytes(value):
    """'512M', '2G', '1.5GiB' or a number of bytes."""
    if isinstance(value, (int, float)):
        return int(value)
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMGT]?)(?:i?B)?\s*", str(value), re.I)
    if not m:
        raise ValueError(f"not a size: {value!r} (use 512M, 2G, ...)")
    unit = m[2].upper()
    return int(float(m[1]) * 1024 ** ("KMGT".index(unit) + 1)) if unit else int(float(m[1]))


def parse_seconds(value):
    """'90s', '10m', '1h30m' or a number of seconds."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)
    parts = re.findall(r"(\d+(?:\.\d+)?)\s*([hms])", text)
    if not parts or re.sub(r"\s", "", text) != "".join(n + u for n, u in parts):
        raise ValueError(f"not a duration: {value!r} (use 90s, 10m, 1h30m, ...)")
    return sum(float(n) * {"h": 3600, "m": 60, "s": 1}[u] for n, u in parts)


def fmt_bytes(n):
    if n is None:
        return "?"
    for unit in ["B", "KiB", "MiB", "GiB", "TiB"]:
        if n < 1024 or unit == "TiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def fmt_seconds(s):
    if s is None:
        return "?"
    s = float(s)
    if s < 60:
        return f"{s:.1f}s"
    if s < 3600:
        return f"{int(s // 60)}m{int(s % 60):02d}s"
    return f"{int(s // 3600)}h{int(s % 3600 // 60):02d}m"


def slug(text, limit=40):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:limit].rstrip("-") or "job")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def run_quiet(cmd, **kw):
    return subprocess.run(cmd, text=True, capture_output=True, **kw)


def schema_ref(path, name):
    """What a job or a result at `path` gives as its "$schema": the schema file, relative to the file's own folder,
    which is three levels deeper in a day's shard than in the flat layout."""
    return os.path.relpath(ROOT / HERE / "schema" / name, Path(path).parent)


def write_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


# Configuration


def merge(base, extra):
    out = dict(base)
    for key, value in extra.items():
        out[key] = merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def machine_config():
    """The machine's own runner settings, which every checkout and jj workspace of the repository on it reads: a
    side workspace has no gitignored verification/pipeline.local.toml of its own, and without this judged a job
    against the committed defaults, which suit a laptop (4 GB a job). $VERIFY_MACHINE_CONFIG names another file, or
    none when empty (the tests)."""
    named = os.environ.get("VERIFY_MACHINE_CONFIG")
    if named is not None:
        return Path(named) if named else None
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "in-the-loop" / "pipeline.local.toml"


def load_config(args=None):
    config = DEFAULTS
    files = [ROOT / HERE / "pipeline.toml", machine_config(), ROOT / HERE / "pipeline.local.toml"]
    if os.environ.get("VERIFY_CONFIG"):
        files.append(Path(os.environ["VERIFY_CONFIG"]))
    read = []
    for f in files:
        if f is not None and f.exists():
            config = merge(config, tomllib.loads(f.read_text()))
            read.append(str(f))
    runner = dict(config["runner"])
    for flag in ["workers", "cpus", "memory", "job_memory_max", "memory_floor", "isolation", "max_timeout", "state_dir"]:
        value = getattr(args, flag, None) if args else None
        if value is not None:
            runner[flag] = value
    runner["memory"] = parse_bytes(runner["memory"])
    runner["job_memory_max"] = parse_bytes(runner["job_memory_max"])
    runner["build_memory"] = parse_bytes(runner["build_memory"])
    runner["memory_floor"] = parse_bytes(str(runner["memory_floor"]))
    runner["job_oom_score_adj"] = max(-1000, min(1000, int(runner["job_oom_score_adj"])))
    runner["log_max_bytes"] = parse_bytes(runner["log_max_bytes"])
    runner["max_timeout"] = parse_seconds(runner["max_timeout"])
    runner["stall_window"] = parse_seconds(runner["stall_window"])
    runner["cpus"] = float(runner["cpus"])
    runner["workers"] = int(runner["workers"])
    runner["machine_name"] = str(runner.get("machine_name") or "").strip() or socket.gethostname()
    state = Path(runner["state_dir"])
    runner["state_dir"] = state if state.is_absolute() else ROOT / state
    if runner["backend"] != "local":
        sys.exit(f"backend {runner['backend']!r}: only 'local' exists so far (verification/README.md, Backends)")
    return {"runner": runner, "defaults": config["defaults"], "files": read}


def systemd_works():
    probe = run_quiet(["systemd-run", "--user", "--scope", "--quiet", "--collect", "-p", "MemoryMax=64M",
                       "-p", "MemorySwapMax=0", "true"]) if shutil.which("systemd-run") else None
    return bool(probe) and probe.returncode == 0


def isolation_of(runner):
    mode = runner["isolation"]
    if mode == "auto":
        mode = "systemd" if systemd_works() else "none"
    if mode not in ("systemd", "none"):
        sys.exit(f"isolation {mode!r}: use systemd, none or auto")
    return mode


# Git and jj


def conflicted(source: str, root: Path | None = None) -> bool:
    """Whether a git commit is jj's representation of a conflicted change: its tree holds JJ-CONFLICT-README at the
    top, beside the .jjconflict-* copies of each side."""
    r = subprocess.run(["git", "cat-file", "-e", f"{source}:JJ-CONFLICT-README"], cwd=root or ROOT, capture_output=True)
    return r.returncode == 0


def git(*args, check=True, binary=False):
    proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=not binary)
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {proc.stderr.strip() if not binary else proc.stderr.decode().strip()}")
    return proc


def default_rev():
    """The latest commit: jj's @- in a jj repo (@ is the change being edited, and not committed), else HEAD."""
    if (ROOT / ".jj").exists() and shutil.which("jj"):
        proc = run_quiet(["jj", "log", "--no-graph", "--ignore-working-copy", "-r", "@-", "-T", 'commit_id ++ "\\n"'],
                         cwd=ROOT)
        ids = proc.stdout.split()
        if proc.returncode == 0 and len(ids) == 1:
            return ids[0]
    return git("rev-parse", "HEAD").stdout.strip()


def queue_revs():
    """The commits whose jobs make up the queue: the latest commit here (default_rev), then jj's @- in every other
    workspace of the repository, so a job committed on a branch that another workspace works on (one stream of a
    feature loop run in parallel, say) runs too, at its own commit. Outside jj, just HEAD."""
    revs = [default_rev()]
    if (ROOT / ".jj").exists() and shutil.which("jj"):
        proc = run_quiet(["jj", "log", "--no-graph", "--ignore-working-copy", "-r", "parents(working_copies())",
                          "-T", 'commit_id ++ "\\n"'], cwd=ROOT)
        if proc.returncode == 0:
            revs += [rev for rev in proc.stdout.split() if rev not in revs]
    return revs


_RECORDED = {}  # a commit's tree doesn't change: the results it records are read once


def recorded_on_heads():
    """The jobs whose result some head of the repository records, by job id, with that head's commit: jj's visible
    heads, or git's branches outside jj. A result is collected into this working copy and committed there, but the
    working copy can be moved off that commit before it is anyone's parent (on 2026-11-17 a `jj new` in a workspace
    two sessions shared left the commit recording a passed job as a side head, and the runner, seeing no result
    here, ran the job a second time). Such a job is done, and its result is one merge away."""
    if (ROOT / ".jj").exists() and shutil.which("jj"):
        proc = run_quiet(["jj", "log", "--no-graph", "--ignore-working-copy", "-r", "visible_heads()", "-T",
                          'commit_id ++ "\n"'], cwd=ROOT)
    else:
        proc = run_quiet(["git", "for-each-ref", "--format=%(objectname)", "refs/heads"], cwd=ROOT)
    found = {}
    for head in (proc.stdout.split() if proc.returncode == 0 else []):
        if head not in _RECORDED:
            listed = git("ls-tree", "-r", "--name-only", head, "--", f"{RESULTS}/", check=False)
            _RECORDED[head] = layout.recorded(listed.stdout.splitlines()) if listed.returncode == 0 else set()
        for job_id in _RECORDED[head]:
            found.setdefault(job_id, head)
    return found


def resolve(rev):
    return git("rev-parse", "--verify", f"{rev}^{{commit}}").stdout.strip()


def show(commit, path):
    """The file's bytes at the commit, or None if it is not there."""
    proc = git("show", f"{commit}:{path}", check=False, binary=True)
    return proc.stdout if proc.returncode == 0 else None


def show_many(commit, paths):
    """The bytes of several files at the commit, by path, from one git process (None for a file that is not there).
    A queue of a few hundred job files is read in a fraction of a second this way, where a `git show` each took
    seconds: the runner reads the queue again while it runs."""
    if not paths:
        return {}
    proc = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT, capture_output=True,
                          input="".join(f"{commit}:{p}\n" for p in paths).encode())
    out, at, found = proc.stdout, 0, {}
    for path in paths:
        end = out.find(b"\n", at)
        header = out[at:end].split() if end >= 0 else []
        if len(header) == 3 and header[1] == b"blob":
            size = int(header[2])
            found[path] = out[end + 1:end + 1 + size]
            at = end + 1 + size + 1
        else:  # "NAME missing", or output that stopped short
            found[path] = None
            at = end + 1 if end >= 0 else len(out)
    return found


def committed_jobs(rev, needs_source=None):
    """Every job file in the commit's tree, as (job, path, source commit). The source commit is the job's own
    revision if it names one, else the last commit that touched the file: the code the job was written for. It
    takes a git process for each job, so `needs_source(job id)` may say which jobs it is wanted for (a job that
    has run needs none); the others come with None."""
    listing = git("ls-tree", "-r", "--name-only", rev, "--", JOBS + "/").stdout.split()
    paths = sorted(p for p in listing if layout.job_id_of(p))
    blobs = show_many(rev, paths)
    jobs = []
    jj_workspace = (ROOT / ".jj").exists()
    for path in paths:
        try:
            job = json.loads(blobs[path])
        except (TypeError, ValueError) as e:
            print(f"warn  {path}: not JSON at {rev[:12]}: {e}", file=sys.stderr)
            continue
        if needs_source is not None and not needs_source(job.get("id") or Path(path).stem):
            jobs.append((job, path, None))
            continue
        change = git("log", "-1", "--format=%H%n%B", rev, "--", path).stdout
        commit, _, message = change.partition("\n")
        # sync.py set_aside() briefly places the files outside --only in an ancestor of @. They are still
        # uncommitted work, even when some other workspace polls the queue during that split.
        if jj_workspace and message.partition("\n")[0] == "wip: another session's files":
            continue
        jobs.append((job, path, resolve(job.get("revision") or commit)))
    return jobs


def queued_jobs(revs, needs_source=None):
    """committed_jobs over several commits, each job once, as the first commit that has it holds it."""
    seen, jobs = set(), []
    for rev in revs:
        for job, path, source in committed_jobs(rev, needs_source):
            job_id = job.get("id") or Path(path).stem
            if job_id not in seen:
                seen.add(job_id)
                jobs.append((job, path, source))
    return jobs


def load_priorities(rev=None):
    """The queue's priorities: {job id: {"priority": int, "reason": str}}, at the commit (as the jobs are read), or
    in the working copy when rev is None. They are kept apart from the job files, which are committed with the change
    they verify and not edited after, so a job can be moved up or down the queue later, with the reason recorded."""
    data = show(rev, PRIORITIES) if rev else ((ROOT / PRIORITIES).read_bytes() if (ROOT / PRIORITIES).exists() else None)
    if data is None:
        return {}
    try:
        document = json.loads(data)
    except ValueError as e:
        print(f"warn  {PRIORITIES}: not JSON{f' at {rev[:12]}' if rev else ''}: {e}", file=sys.stderr)
        return {}
    return {k: v for k, v in (document.get("jobs") or {}).items() if isinstance(v, dict) and isinstance(v.get("priority"), int)}


def priority_of(job, priorities):
    """The queue's priority for a job, if it sets one, else the job's own (0 by default). Higher runs first."""
    entry = priorities.get(job.get("id"))
    return entry["priority"] if entry else int(job.get("priority", 0))


def queue_order(priorities):
    return lambda t: (-priority_of(t[0], priorities), (t[0].get("submitted") or {}).get("at", ""), t[0].get("id", ""))


# Schemas


def validate(document, schema_name):
    """Problems with the document, as strings. Uses jsonschema when it is installed; the checks below always run."""
    problems = []
    try:
        import jsonschema
        schema = json.loads((SCHEMAS / schema_name).read_text())
        for error in jsonschema.Draft202012Validator(schema).iter_errors(document):
            where = "/".join(str(p) for p in error.absolute_path) or "(top)"
            problems.append(f"{where}: {error.message}")
    except ImportError:
        pass
    if schema_name == "job.schema.json":
        problems += job_problems(document)
    return problems


def job_problems(job):
    problems = []
    for key in ["id", "title", "description", "capabilities", "resources", "steps"]:
        if key not in job:
            problems.append(f"missing {key}")
    if "id" in job and not ID_PATTERN.match(str(job["id"])):
        problems.append(f"id {job['id']!r} is not YYYYMMDD-HHMMSS-slug")
    resources = job.get("resources") or {}
    for key in ["memory", "memoryLimit"]:
        if key in resources:
            try:
                parse_bytes(resources[key])
            except ValueError as e:
                problems.append(f"resources.{key}: {e}")
    for key in ["duration", "timeout"]:
        if key in resources:
            try:
                parse_seconds(resources[key])
            except ValueError as e:
                problems.append(f"resources.{key}: {e}")
    if not job.get("steps"):
        problems.append("no steps")
    for i, step in enumerate(job.get("steps") or []):
        if not str(step.get("run", "")).strip():
            problems.append(f"steps/{i}: nothing to run")
    return sorted(set(problems))


# Resources


def plan(job, config):
    """What the runner reserves for the job, and why it can never run here if it cannot."""
    runner, defaults = config["runner"], config["defaults"]
    resources = job.get("resources", {})
    cpus = float(resources.get("cpus", defaults["cpus"]))
    estimate = parse_bytes(resources.get("memory", defaults["memory"]))
    limit = parse_bytes(resources["memoryLimit"]) if "memoryLimit" in resources else \
        min(max(int(estimate * 1.5), estimate), runner["job_memory_max"])
    duration = parse_seconds(resources.get("duration", defaults["duration"]))
    timeout = parse_seconds(resources["timeout"]) if "timeout" in resources else max(4 * duration, 300)
    timeout = min(timeout, runner["max_timeout"])
    reasons = []
    if estimate > runner["job_memory_max"] or limit > runner["job_memory_max"]:
        reasons.append(f"needs {fmt_bytes(max(estimate, limit))}, and this runner allows {fmt_bytes(runner['job_memory_max'])} per job")
    if limit > runner["memory"]:
        reasons.append(f"needs {fmt_bytes(limit)}, more than the runner's whole budget of {fmt_bytes(runner['memory'])}")
    if cpus > runner["cpus"]:
        reasons.append(f"needs {cpus:g} CPUs, and the runner has {runner['cpus']:g}")
    return {"cpus": cpus, "memoryEstimate": estimate, "memoryLimit": limit, "durationEstimate": duration,
            "timeout": timeout, "cannotRun": reasons}


def mem_available():
    # A test stands in for the machine with a file holding a number of bytes (verification/test_pipeline.py).
    if os.environ.get("VERIFY_MEMAVAILABLE_FILE"):
        try:
            return int(Path(os.environ["VERIFY_MEMAVAILABLE_FILE"]).read_text().split()[0])
        except (OSError, ValueError, IndexError):
            pass
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    return None


# The environment a job ran in


_ENVIRONMENT = {}   # by workload: the tools are probed once for each


def first_line(cmd):
    try:
        proc = run_quiet(cmd, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (proc.stdout or proc.stderr).strip()
    return text.splitlines()[0] if proc.returncode == 0 and text else None


def environment(host, adapter=None):
    """The machine a job ran on, recorded under `host`: the runner's machine_name, else the hostname. The tools are
    the pipeline's own (what isolates and stops a step) and those of the job's workload: a build job's record does
    not list checkers, and a machine with none installed is not asked for them."""
    adapter = adapter or workload("generic")
    if adapter.NAME not in _ENVIRONMENT:
        cpu = next((l.split(":", 1)[1].strip() for l in Path("/proc/cpuinfo").read_text().splitlines()
                    if l.lower().startswith(("model name", "cpu part"))), None) if Path("/proc/cpuinfo").exists() else None
        total = next((int(l.split()[1]) * 1024 for l in Path("/proc/meminfo").read_text().splitlines()
                      if l.startswith("MemTotal:")), None)
        _ENVIRONMENT[adapter.NAME] = {
            "host": host,
            "os": platform.platform(),
            "machine": platform.machine(),
            "cpuModel": cpu,
            "cpuCount": os.cpu_count(),
            "memoryTotalBytes": total,
            "python": platform.python_version(),
            "tools": {
                **adapter.tools(),
                "systemd": first_line(["systemd-run", "--version"]),
                # GNU or uutils (Ubuntu 26.04's default): jobs see the difference, as in timeout's exit after -s KILL.
                "coreutils": first_line(["timeout", "--version"]),
                "git": first_line(["git", "--version"]),
            },
        }
    return _ENVIRONMENT[adapter.NAME]


def missing_tools(requires):
    """Which of these requirements this machine lacks, as the verification workload looks for them (the name every
    job of the first format was checked by; a job's own workload answers for it in `Runner.prepare`)."""
    return workload("verification").missing(requires)


# Logs


def scan_log(log_path, patterns):
    """The lines of a log that match a workload's patterns, (tool, kind, compiled pattern): the first MAX_SIGNALS
    of them with their line numbers, how often each kind appeared, and how many lines the log has."""
    signals, counts, lines = [], {}, 0
    with open(log_path, errors="replace") as f:
        for lines, line in enumerate(f, 1):
            line = line.rstrip("\n")
            for tool, kind, pattern in patterns:
                m = pattern.search(line)
                if m:
                    key = f"{tool}:{kind}"
                    counts[key] = counts.get(key, 0) + 1
                    if len(signals) < MAX_SIGNALS:
                        signals.append({"tool": tool, "kind": kind, "line": lines, "text": line[:300],
                                        "groups": [g for g in m.groups() if g is not None]})
    return signals, counts, lines


def scan_signals(log_path):
    """A log's verdict lines as the verification workload reads them."""
    return workload("verification").scan(log_path)


def signal_verdicts(steps, skip=()):
    """Each kind of signal the steps' logs gave with its count, for a summary line."""
    return [f"{key}×{n}" for s in steps for key, n in sorted((s.get("signalCounts") or {}).items()) if key not in skip]


def tail(log_path, n=40):
    with open(log_path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 64 * 1024))
        data = f.read().decode(errors="replace")
    return [l[:300] for l in data.splitlines()[-n:]]


def keep_log(full, dest, max_bytes, host):
    """Copies the log into the result: whole if it is short, else its head and tail around a note of what is left out."""
    data = full.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    info = {"bytes": len(data), "lines": data.count(b"\n"), "sha256": sha256(data), "truncated": False}
    if len(data) <= max_bytes:
        dest.write_bytes(data)
    else:
        head, rest = data[: max_bytes // 4], data[-(max_bytes * 3 // 4):]
        head = head[: head.rfind(b"\n") + 1] or head
        rest = rest[rest.find(b"\n") + 1:] or rest
        left = len(data) - len(head) - len(rest)
        note = (f"\n[... {left} bytes ({data.count(b'\n') - head.count(b'\n') - rest.count(b'\n')} lines) left out; "
                f"the whole log is {len(data)} bytes, sha256 {info['sha256']}, kept on {host} at "
                f"{full} ...]\n\n").encode()
        dest.write_bytes(head + note + rest)
        info["truncated"] = True
        info["fullLog"] = str(full)
    return info


# Running a step

WRAPPER = r"""#!/usr/bin/env bash
# Runs one step in the work directory and, when the step is in a scope of its own, writes the scope's memory and CPU
# counters before the scope goes away: memory.peak is lost once the last process in it exits. It first raises its own
# oom_score_adj, which everything the step starts inherits: the kernel kills a job before anything else on the machine.
# Raising needs no privilege; a value under the current one is refused, and the step runs as it is.
if [ -n "${VERIFY_STEP_OOM_SCORE_ADJ:-}" ]; then
  echo "$VERIFY_STEP_OOM_SCORE_ADJ" > /proc/self/oom_score_adj 2>/dev/null || true
fi
cd "$VERIFY_STEP_CWD" || exit 125
bash -c "$VERIFY_STEP_RUN"
rc=$?
if [ -n "${VERIFY_STEP_STATS:-}" ]; then
  cg=/sys/fs/cgroup$(sed -n 's/^0:://p' /proc/self/cgroup)
  {
    for f in memory.peak memory.events cpu.stat; do
      [ -r "$cg/$f" ] && sed "s/^/$f /" "$cg/$f"
    done
  } > "$VERIFY_STEP_STATS" 2>/dev/null
fi
exit $rc
"""


def read_stats(path):
    stats = {}
    try:
        for line in Path(path).read_text().splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0] == "memory.peak":
                stats["memory.peak"] = int(parts[1])
            elif len(parts) == 3:
                stats[f"{parts[0]}.{parts[1]}"] = int(parts[2])
    except (OSError, ValueError):
        pass
    return stats


def cgroup_of(pid):
    try:
        for line in Path(f"/proc/{pid}/cgroup").read_text().splitlines():
            if line.startswith("0::"):
                return Path("/sys/fs/cgroup" + line[3:])
    except OSError:
        pass
    return None


def session_cpu_seconds(sid):
    """CPU time of the live processes in session `sid` (a step without a cgroup), from /proc. Finished children whose
    parent reaped them count through the parent's cutime and cstime."""
    total, tick = 0, os.sysconf("SC_CLK_TCK")
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = stat.read_text().rsplit(")", 1)[1].split()
        except (OSError, IndexError):
            continue
        if int(fields[3]) == sid:          # field 6 of stat, after pid and comm: the session id
            total += sum(int(x) for x in fields[11:15])   # utime, stime, cutime, cstime
    return total / tick


class Step:
    """One step, run to its end or until it is stopped: past its timeout once it has stalled (no CPU, no output for
    the stall window), and at the hard ceiling whatever it is doing. The timeout is where a hang starts to be looked
    for, not a deadline: a long run that is still working is information, about the change and about the machine."""

    def __init__(self, unit, isolation, cpus, memory_limit, stall_window=600, ceiling=float("inf"), oom_score_adj=None):
        self.unit, self.isolation, self.cpus, self.memory_limit = unit, isolation, cpus, memory_limit
        self.stall_window, self.ceiling, self.oom_score_adj = stall_window, ceiling, oom_score_adj
        self.pid = None
        self.cancelled = False
        self.urgent = False      # cancelled for the machine's memory: killed at once, with no 15 s to wind down

    def command(self, wrapper):
        if self.isolation == "systemd":
            return ["systemd-run", "--user", "--scope", "--quiet", "--collect", f"--unit={self.unit}",
                    "-p", f"MemoryMax={self.memory_limit}", "-p", "MemorySwapMax=0", "-p", "OOMPolicy=continue",
                    "-p", f"CPUQuota={int(round(self.cpus * 100))}%", "--", "bash", str(wrapper)]
        return ["bash", str(wrapper)]

    def stop(self, sig=signal.SIGTERM):
        if self.isolation == "systemd":
            run_quiet(["systemctl", "--user", "kill", f"--signal={sig.name}", f"{self.unit}.scope"])
            if sig == signal.SIGKILL:
                run_quiet(["systemctl", "--user", "stop", f"{self.unit}.scope"])
        elif self.pid:
            try:
                os.killpg(self.pid, sig)
            except ProcessLookupError:
                pass

    def cpu_seconds(self, cgroup, pid):
        """The step's CPU time so far: its cgroup's when it has one, else its session's processes'."""
        if cgroup:
            try:
                for line in (cgroup / "cpu.stat").read_text().splitlines():
                    if line.startswith("usage_usec "):
                        return int(line.split()[1]) / 1e6
            except (OSError, ValueError):
                return None
        try:
            return session_cpu_seconds(pid)
        except OSError:
            return None

    def run(self, run, cwd, env, log_path, stats_path, wrapper, timeout):
        if self.isolation == "systemd":
            run_quiet(["systemctl", "--user", "stop", f"{self.unit}.scope"])  # a leftover of the same name
        env = dict(env, VERIFY_STEP_CWD=str(cwd), VERIFY_STEP_RUN=run,
                   VERIFY_STEP_STATS=str(stats_path) if self.isolation == "systemd" else "",
                   VERIFY_STEP_OOM_SCORE_ADJ="" if self.oom_score_adj is None else str(self.oom_score_adj))
        started = time.monotonic()
        polled = {}
        timed_out, terminating, kill_at = False, False, float("inf")
        stopped_for, overran = None, False
        progress = None          # (cpu seconds, log bytes, when) at the start of the current stall window
        checked = 0.0            # when progress was last looked at: every 30 s at most, since it reads /proc or a cgroup
        with open(log_path, "wb") as log:
            proc = subprocess.Popen(self.command(wrapper), stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    env=env, start_new_session=True)
            self.pid = proc.pid
            cgroup = None
            status, rusage = None, None
            while status is None:
                pid, status_, rusage_ = os.wait4(proc.pid, os.WNOHANG)
                if pid:
                    status, rusage = status_, rusage_
                    break
                if self.isolation == "systemd":
                    # Until systemd-run has moved itself into the scope, the pid is still in the runner's cgroup.
                    found = cgroup or cgroup_of(proc.pid)
                    cgroup = found if found and found.name == f"{self.unit}.scope" else None
                    if cgroup:
                        try:
                            polled["memory.peak"] = int((cgroup / "memory.peak").read_text())
                        except (OSError, ValueError):
                            pass
                now_ = time.monotonic()
                elapsed = now_ - started
                stop = None
                if not terminating and self.cancelled:
                    stop = "cancelled"
                elif not terminating and elapsed > self.ceiling:
                    stop = "ceiling"
                elif not terminating and elapsed > timeout:
                    overran = True
                    if progress is None or now_ - checked >= min(self.stall_window, 30):
                        checked = now_
                        cpu = self.cpu_seconds(cgroup, proc.pid)
                        size = log_path.stat().st_size if log_path.exists() else 0
                        if progress is None or cpu is None or cpu - progress[0] > 0.01 * (now_ - progress[2]) or size != progress[1]:
                            progress = (cpu or 0, size, now_)    # working: a new window starts
                        elif now_ - progress[2] >= self.stall_window:
                            stop = "stalled"
                if stop and self.urgent:
                    timed_out, terminating, stopped_for = False, True, stop
                    self.stop(signal.SIGKILL)
                    kill_at = float("inf")
                elif stop:
                    timed_out, terminating, stopped_for = stop != "cancelled", True, stop
                    self.stop(signal.SIGTERM)
                    kill_at = time.monotonic() + 15
                elif terminating and time.monotonic() > kill_at:
                    self.stop(signal.SIGKILL)
                    kill_at = float("inf")
                time.sleep(0.2)
            proc.returncode = os.waitstatus_to_exitcode(status)
        wall = time.monotonic() - started
        # Whatever the step left running (a Gradle daemon, say) goes with it.
        if self.isolation == "systemd":
            run_quiet(["systemctl", "--user", "stop", f"{self.unit}.scope"])
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        stats = dict(polled, **read_stats(stats_path))
        code = proc.returncode
        return {
            "exitCode": code if code >= 0 else None,
            "signal": signal.Signals(-code).name if code < 0 else None,
            "timedOut": timed_out,
            "stoppedFor": stopped_for if stopped_for != "cancelled" else None,
            "overranTimeout": overran,
            "timeoutSeconds": timeout,
            "cancelled": self.cancelled,
            "wallSeconds": round(wall, 3),
            "cpuSeconds": round(stats["cpu.stat.usage_usec"] / 1e6, 3) if "cpu.stat.usage_usec" in stats
            else round(rusage.ru_utime + rusage.ru_stime, 3),
            "cpuThrottledSeconds": round(stats["cpu.stat.throttled_usec"] / 1e6, 3) if "cpu.stat.throttled_usec" in stats else None,
            "peakMemoryBytes": stats.get("memory.peak") or (rusage.ru_maxrss * 1024 if rusage else None),
            "peakMemoryMeasure": "cgroup memory.peak" if "memory.peak" in stats else "largest process's peak RSS",
            "oomKills": stats.get("memory.events.oom_kill", 0),
            # Times the step's own limit ran out (memory.events oom). A kill with none of these came from the machine
            # running out, not from the step's limit.
            "limitOoms": stats.get("memory.events.oom", 0),
            "memoryHighEvents": stats.get("memory.events.max", 0),
        }


# Running a job


class Runner:
    def __init__(self, config, isolation):
        self.config, self.runner = config, config["runner"]
        self.isolation = isolation
        self.state = self.runner["state_dir"]
        for d in ["claims", "results", "attempts", "tools"]:
            (self.state / d).mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.running = {}      # id -> {"plan", "thread", "steps": [Step]}
        self.finished = []     # ids finished in this run
        self.stopping = False
        self.told_elsewhere = set()
        self.wrapper = self.state / "step-wrapper.sh"
        self.wrapper.write_text(WRAPPER)

    # Claims keep two runners on the same state directory from taking the same job.
    def claim(self, job_id):
        path = self.state / "claims" / job_id
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return False
        os.write(fd, json.dumps({"pid": os.getpid(), "host": socket.gethostname(), "at": iso(now())}).encode())
        os.close(fd)
        return True

    def release(self, job_id):
        (self.state / "claims" / job_id).unlink(missing_ok=True)

    def clear_stale_claims(self):
        for path in (self.state / "claims").iterdir():
            try:
                claim = json.loads(path.read_text())
                if claim.get("host") == socket.gethostname():
                    os.kill(claim["pid"], 0)
            except ProcessLookupError:
                print(f"note  {path.name}: claimed by a runner that is gone (pid {claim.get('pid')}); released")
                path.unlink(missing_ok=True)
            except (ValueError, OSError):
                pass

    def done_ids(self):
        # A job the runner was stopped in the middle of counts as not run, and runs again.
        done = {p.name for p in (self.state / "results").iterdir() if (p / "result.json").exists()
                and json.loads((p / "result.json").read_text()).get("status") != "cancelled"}
        done |= set(layout.results(ROOT))
        # A result committed on a head this working copy isn't on: done all the same, and said once, since it is
        # missing here until that commit is merged.
        for job_id, head in sorted(recorded_on_heads().items()):
            if job_id not in done and job_id not in self.told_elsewhere:
                self.told_elsewhere.add(job_id)
                print(f"note  {job_id}: its result is recorded in commit {head[:12]}, which this working copy is not "
                      f"on; not run again. Merge that commit to have the result here", flush=True)
            done.add(job_id)
        return done

    def pending(self, revs, wanted=None, min_priority=None):
        """The jobs to run from these commits (queue_revs), in priority order; the priorities are the first commit's."""
        done, claimed = self.done_ids(), {p.name for p in (self.state / "claims").iterdir()}
        priorities = load_priorities(revs[0])
        out = []
        settled = lambda job_id: job_id in done or job_id in claimed or job_id in self.running
        for job, path, source in queued_jobs(revs, lambda job_id: not settled(job_id)):
            job_id = job.get("id") or Path(path).stem
            if job_id in done or job_id in claimed or job_id in self.running:
                continue
            if wanted and job_id not in wanted:
                continue
            if min_priority is not None and priority_of(job, priorities) < min_priority:
                continue
            out.append((job, path, source))
        out.sort(key=queue_order(priorities))
        return out

    def reservation(self, job, job_plan, source):
        return workload_of(job).reservation(self, job, job_plan, source)

    def fits(self, cpus, memory):
        used_cpus = sum(r["cpus"] for r in self.running.values())
        used_memory = sum(r["memory"] for r in self.running.values())
        if len(self.running) >= self.runner["workers"]:
            return "all workers busy"
        if used_cpus + cpus > self.runner["cpus"] + 1e-9:
            return f"{used_cpus:g} of {self.runner['cpus']:g} CPUs in use"
        if used_memory + memory > self.runner["memory"]:
            return f"{fmt_bytes(used_memory)} of {fmt_bytes(self.runner['memory'])} reserved"
        available = mem_available()
        floor = self.runner["memory_floor"]
        if available is not None and available - floor < memory:
            return (f"only {fmt_bytes(available)} available on the machine" +
                    (f", which keeps {fmt_bytes(floor)} free" if floor else ""))
        return None

    # The machine's memory comes first: a job goes before an agent, a watcher or a terminal.

    def relieve(self, available):
        """The machine has fallen under the memory floor: stop the job started last, at once. One at a time: the next
        goes only once this one is gone and the machine is still short. Returns the id stopped, or None."""
        with self.lock:
            if not self.running or any(e.get("memoryStop") for e in self.running.values()):
                return None
            job_id, entry = max(self.running.items(), key=lambda kv: kv[1].get("started", 0))
            entry["memoryStop"] = {"at": iso(now()), "availableBytes": available, "floorBytes": self.runner["memory_floor"],
                                   "running": len(self.running)}
            for step in entry["steps"]:
                step.urgent = True
                step.cancelled = True
        print(f"{job_id}: stopped for the machine's memory: {fmt_bytes(available)} available, under the "
              f"{fmt_bytes(self.runner['memory_floor'])} floor; the newest of {len(self.running)} running job(s)", flush=True)
        return job_id

    def memory_stopped(self, job_id, result, stop):
        """The first time, the job is cancelled and runs again when there is room. The second time it is a result,
        out-of-memory, for its submitter to regroup: the machine cannot hold it beside the rest as it was asked."""
        try:  # the count goes on across runners: the last result of a job stopped this way says how often it was
            before = json.loads((self.state / "results" / job_id / "result.json").read_text())
        except (OSError, ValueError):
            before = {}
        n = ((before.get("memoryStop") or {}).get("count", 0) if before.get("status") == "cancelled" else 0) + 1
        stop = dict(stop, count=n)
        result["memoryStop"] = stop
        why = (f"the runner stopped it because the machine had {fmt_bytes(stop['availableBytes'])} available, under its "
               f"{fmt_bytes(stop['floorBytes'])} floor, with {stop['running']} job(s) running; not at the job's own limit")
        if n == 1:
            result["status"] = "cancelled"
            result["attention"].append(f"{why}. It runs again when there is room")
        else:
            result["status"] = "out-of-memory"
            result["attention"].append(f"{why}, {n} times now. Regroup: resubmit it with a higher --memory "
                                       f"estimate (so fewer jobs run beside it), run fewer workers, or split it")

    def start(self, job, path, source, job_plan, memory):
        job_id = job["id"]
        if not self.claim(job_id):
            return False
        entry = {"plan": job_plan, "cpus": job_plan["cpus"], "memory": memory, "steps": [], "job": job,
                 "started": time.monotonic()}
        self.running[job_id] = entry
        thread = threading.Thread(target=self.execute, args=(job, path, source, job_plan, entry), daemon=True)
        entry["thread"] = thread
        thread.start()
        return True

    def jvmcontract_cached(self, source):
        return workload("verification").jvmcontract_cached(self, source)

    def execute(self, job, path, source, job_plan, entry):
        job_id = job["id"]
        started = now()
        capture = originals()
        capturing = bool(capture and capture.available(ROOT))
        # The attempt has its number, its record and its folders before it writes anything, whether or not the
        # archive answers: its number is the archive's when that can be asked, else its own record's. A run
        # directory of before attempts had their own (STATE/runs/ID) is left as it is, for `recover` and `prune`.
        floor = max(attempts.next_number(self.state, job_id), legacy_attempt(self.state, job_id) + 1)
        number = capture.begin(ROOT, self.state, job_id, floor) if capturing else None
        attempt = attempts.begin(self.state, job_id, source, self.runner["machine_name"], at_least=number or floor)
        attempt.save(spec=job, path=path)
        entry["attempt"] = attempt
        run_dir, work = attempt.run_dir, attempt.work_dir
        result = {
            "$schema": "../../schema/result.schema.json",
            "schema": RESULT_SCHEMA,
            "id": job_id,
            "title": job.get("title"),
            "status": None,
            "summary": None,
            "attention": [],
            "job": {"path": path, "sha256": sha256(json.dumps(job, sort_keys=True).encode()), "spec": job},
            "sourceCommit": source,
            "startedAt": iso(started),
            "finishedAt": None,
            "wallSeconds": None,
            "runner": {"backend": self.runner["backend"], "isolation": self.isolation, "host": self.runner["machine_name"],
                       "pid": os.getpid(), "workers": self.runner["workers"], "cpus": self.runner["cpus"],
                       "memoryBudgetBytes": self.runner["memory"], "maxTimeoutSeconds": self.runner["max_timeout"],
                       "stallWindowSeconds": self.runner["stall_window"]},
            "limits": {"cpus": job_plan["cpus"], "memoryLimitBytes": job_plan["memoryLimit"],
                       "timeoutSeconds": job_plan["timeout"]},
            "estimate": {"cpus": job_plan["cpus"], "memoryBytes": job_plan["memoryEstimate"],
                         "durationSeconds": job_plan["durationEstimate"],
                         "notes": (job.get("resources") or {}).get("notes")},
            "usage": None,
            "environment": environment(self.runner["machine_name"], workload_of(job)),
            "steps": [],
            "outputs": [],
            "collected": None,
            "attempt": {"id": attempt.id, "number": attempt.number, "folder": str(attempt.folder),
                        "previous": [a.id for a in attempts.of(self.state, job_id) if a.id != attempt.id]},
        }
        try:
            self.prepare(job, source, work, result, entry)
            if result["status"] is None:
                self.run_steps(job, work, run_dir, result, entry)
                self.collect_outputs(job, work, source, run_dir, result)
        except Exception as e:  # anything the pipeline itself got wrong is an error, never a verdict
            result["status"] = "error"
            result["attention"].append(f"the pipeline failed: {type(e).__name__}: {e}")
        if entry.get("memoryStop"):
            self.memory_stopped(job_id, result, entry["memoryStop"])
        finished = now()
        result["finishedAt"] = iso(finished)
        result["wallSeconds"] = round((finished - started).total_seconds(), 1)
        self.finish(job, result, job_plan)
        # Sealed whole, before anything below cuts a log or removes the work directory; the result names what was.
        errors = []
        sealed = capture.sealed_run(ROOT, self.state, job, attempt.number, source, run_dir, work, result,
                                    attempt_id=attempt.id, errors=errors) if capturing else None
        if sealed:
            result["originals"] = sealed
            attempt.captured("sealed", sealed["occurrences"], number=sealed["attempt"])
        elif capturing:  # kept, and said: `recover` seals it when the archive answers again
            attempt.captured("failed", error=errors[-1] if errors else "see capture.log")
        else:
            attempt.captured("off")
        # The attempt's run folder keeps the whole logs on this machine; the result gets them whole if short, else cut.
        out = self.state / "results" / job_id
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        for s in result["steps"]:
            if s.get("log"):
                s["log"].update(keep_log(run_dir / s["log"]["path"], out / s["log"]["path"], self.runner["log_max_bytes"],
                                            self.runner["machine_name"]))
        if (run_dir / "outputs").exists():
            shutil.copytree(run_dir / "outputs", out / "outputs")
        if (run_dir / "changes.diff").exists():
            shutil.copy2(run_dir / "changes.diff", out / "changes.diff")
        # A work directory goes when the job ends only by a rule that makes it nobody's last copy: a passed job's
        # is not an original, and another's goes with `keep_workdirs = "never"` once what it held beyond the commit
        # is sealed (or nothing captures here). Any other stays in the attempt's folder, for `prune`.
        keep = self.runner["keep_workdirs"]
        if not work.exists():
            pass
        elif result["status"] == "passed" and keep != "always":
            attempt.release("work", "the job passed, and a passed job's work directory is not an original")
        elif keep == "never" and (not capturing or (sealed and "workdir" in sealed["occurrences"])):
            attempt.release("work", "keep_workdirs is never" + (", and what it held beyond the commit is sealed" if sealed else
                                                                ", and nothing captures originals here"))
        else:
            result["workdir"] = str(work)
        write_json(out / "result.json", result)
        shutil.copy2(out / "result.json", attempt.folder / "result.json")  # the attempt's own, whatever is staged next
        attempt.finished(result["status"])
        if capturing:
            capture.sealed_result(ROOT, self.state, job, attempt.number, source, out / "result.json")
        with self.lock:
            self.running.pop(job_id, None)
            self.finished.append(job_id)
        self.release(job_id)
        print(f"{job_id}: {result['summary']}", flush=True)

    def prepare(self, job, source, work, result, entry):
        work.mkdir(parents=True)  # the attempt's own: nothing was here
        entry["attempt"].save(prepared=True)
        if conflicted(source):
            # jj writes a conflicted commit to git as its conflict layout: the README and a whole-tree copy of the
            # base and of each side. A job exported from one ran on that, three or four trees at once (VF-060).
            result["status"] = "error"
            result["attention"].append(f"its source revision {source[:12]} is a conflicted jj commit, so its tree is jj's "
                                       f"conflict layout, not the sources: resolve the conflict and submit the job again")
            return
        archive = subprocess.run(["git", "archive", "--format=tar", source], cwd=ROOT, capture_output=True)
        if archive.returncode != 0:
            raise RuntimeError(f"git archive {source}: {archive.stderr.decode().strip()}")
        subprocess.run(["tar", "-x", "-C", str(work)], input=archive.stdout, check=True)
        for link in self.runner["link"]:
            src, dst = ROOT / link, work / link
            if src.exists() and not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.symlink_to(src)
        adapter = workload_of(job)
        missing = adapter.missing(job.get("requires", []))
        if missing:
            result["status"] = "error"
            result["attention"].append("missing on this machine: " + ", ".join(missing))
            return
        adapter.prepare(self, job, source, work, result, entry)

    def step_env(self, job, result, work):
        limit_mb = result["limits"]["memoryLimitBytes"] // (1024 * 1024)
        env = dict(os.environ)
        workload_of(job).step_env(self, job, result, work, env)   # what the job's kind of work needs in every step
        env.update({"VERIFY_JOB_ID": job["id"], "VERIFY_CPUS": f"{result['limits']['cpus']:g}",
                    "VERIFY_MEMORY_LIMIT_MB": str(limit_mb), "VERIFY_WORKDIR": str(work),
                    "VERIFY_SOURCE_COMMIT": result["sourceCommit"],
                    # The repository the runner works for, outside the export: a step that asks the queue reads
                    # it there.
                    "VERIFY_RUNNER_ROOT": str(ROOT)})
        # The export is a plain tree inside this repository's own (under .state/work): git run in a job must not take
        # this repository for the job's. Inside it, `git apply` takes a git-format patch's paths from its top level
        # and skips every file, exiting 0, so an example's patch went unapplied in every job of build.py at a commit
        # before its own guard.
        env["GIT_CEILING_DIRECTORIES"] = str(Path(work).resolve().parent)
        env.update({k: str(v) for k, v in (job.get("env") or {}).items()})
        return env

    def run_steps(self, job, work, run_dir, result, entry):
        env = self.step_env(job, result, work)
        failed = False
        for i, spec in enumerate(job["steps"], 1):
            name = spec.get("name") or f"step {i}"
            log = run_dir / "logs" / f"{i}-{slug(name, 30)}.log"
            if (failed and job.get("stopOnFailure", True)) or self.stopping or entry.get("memoryStop"):
                why = ("the runner stopped the job for the machine's memory" if entry.get("memoryStop") else
                       "an earlier step failed" if failed else "the runner was stopped")
                result["steps"].append({"index": i, "name": name, "run": spec["run"], "cwd": spec.get("cwd", "."),
                                        "status": "skipped", "why": why})
                continue
            timeout = min(parse_seconds(spec["timeout"]) if spec.get("timeout") else result["limits"]["timeoutSeconds"],
                          result["limits"]["timeoutSeconds"])
            step = Step(f"vjob-{scope_id(job['id'])}-{i}", self.isolation, result["limits"]["cpus"],
                        result["limits"]["memoryLimitBytes"], self.runner["stall_window"], self.runner["max_timeout"],
                        self.runner["job_oom_score_adj"])
            entry["steps"].append(step)
            if entry.get("memoryStop"):  # stopped between the check above and now
                step.urgent = step.cancelled = True
            outcome = step.run(spec["run"], work / spec.get("cwd", "."), env, log, log.with_suffix(".stats"),
                               self.wrapper, timeout)
            record = self.step_record(spec, i, outcome, log, workload_of(job))
            expected = spec.get("expectExit", 0)
            expected = expected if isinstance(expected, list) else [expected]
            record["expectExit"] = expected
            if outcome["cancelled"]:
                record["status"] = "cancelled"
            elif outcome["timedOut"]:
                record["status"] = "timeout"
            elif outcome["exitCode"] in expected:
                record["status"] = "passed"
            elif outcome["oomKills"]:
                record["status"] = "out-of-memory"
            else:
                record["status"] = "failed"
            result["steps"].append(record)
            failed = failed or record["status"] != "passed"

    def step_record(self, spec, index, outcome, log, adapter=None):
        signals, counts, lines = (adapter or workload(FIRST_FORMAT_WORKLOAD)).scan(log)
        return {"index": index, "name": spec.get("name") or f"step {index}", "run": spec["run"],
                "cwd": spec.get("cwd", "."), "status": None, **outcome,
                "log": {"path": f"logs/{log.name}", "lines": lines}, "signalCounts": counts, "signals": signals,
                "tail": tail(log)}

    def collect_outputs(self, job, work, source, run_dir, result):
        """The files the job produced or changed among its declared outputs, kept with a diff against the commit."""
        diffs = []
        for spec in job.get("outputs") or []:
            base = work / spec
            files = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file()) if base.is_dir() else []
            committed = set(git("ls-tree", "-r", "--name-only", source, "--", spec).stdout.split())
            for f in files:
                rel = f.relative_to(work).as_posix()
                committed.discard(rel)
                new, old = f.read_bytes(), show(source, rel)
                if new == old:
                    continue
                dest = run_dir / "outputs" / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(new)
                result["outputs"].append({"path": rel, "change": "added" if old is None else "modified",
                                          "bytes": len(new), "sha256": sha256(new),
                                          "sourceSha256": sha256(old) if old is not None else None})
                diffs.append(text_diff(rel, old, new))
            for rel in sorted(committed):
                if not (work / rel).exists():
                    result["outputs"].append({"path": rel, "change": "deleted", "bytes": 0, "sha256": None,
                                              "sourceSha256": sha256(show(source, rel) or b"")})
            if not files and not base.exists():
                result["attention"].append(f"declared output {spec} was not produced")
        if diffs:
            (run_dir / "changes.diff").write_text("".join(diffs))
            result["changesDiff"] = "changes.diff"

    def finish(self, job, result, job_plan):
        adapter = workload_of(job)
        steps = [s for s in result["steps"] if s.get("index", 0) > 0]
        if result["status"] is None:
            statuses = [s["status"] for s in steps if s["status"] != "skipped"]
            result["status"] = min(statuses or ["error"], key=STATUS_ORDER.index)
        measured = [s for s in steps if s.get("wallSeconds") is not None]
        peak = max((s["peakMemoryBytes"] or 0 for s in measured), default=None) if measured else None
        wall = sum(s["wallSeconds"] for s in measured)
        cpu = sum(s["cpuSeconds"] or 0 for s in measured)
        result["usage"] = {"peakMemoryBytes": peak, "wallSeconds": round(wall, 1), "cpuSeconds": round(cpu, 1),
                           "memoryOfEstimate": round(peak / job_plan["memoryEstimate"], 2) if peak else None,
                           "durationOfEstimate": round(wall / job_plan["durationEstimate"], 2) if wall else None}
        attention = result["attention"]
        for s in steps:
            where = f"step {s['index']} ({s['name']})"
            if s["status"] == "failed":
                attention.append(f"{where} exited {s['exitCode'] if s['exitCode'] is not None else s['signal']}, expected {', '.join(map(str, s['expectExit']))}")
            elif s["status"] == "timeout" and s.get("stoppedFor") == "ceiling":
                attention.append(f"{where} was still working at the runner's {fmt_seconds(result['runner'].get('maxTimeoutSeconds') or s['wallSeconds'])} "
                                 f"ceiling and was stopped there, with no verdict")
            elif s["status"] == "timeout" and s.get("stoppedFor") == "stalled":
                attention.append(f"{where} stalled past its {fmt_seconds(s.get('timeoutSeconds') or result['limits']['timeoutSeconds'])} timeout "
                                 f"(no CPU and no output for {fmt_seconds(result['runner'].get('stallWindowSeconds') or 0)}) and was stopped")
            elif s["status"] == "timeout":
                attention.append(f"{where} hit its {fmt_seconds(result['limits']['timeoutSeconds'])} timeout")
            if s["status"] not in ("timeout", "cancelled") and s.get("overranTimeout"):
                attention.append(f"{where} ran past its {fmt_seconds(s.get('timeoutSeconds') or result['limits']['timeoutSeconds'])} timeout "
                                 f"while still working and was left to finish, in {fmt_seconds(s['wallSeconds'])}: the estimate is far off")
            elif s["status"] == "out-of-memory" and s.get("oomKills") and not s.get("limitOoms", 1):
                attention.append(f"{where} was killed by the kernel when the machine ran out of memory, under its own "
                                 f"{fmt_bytes(result['limits']['memoryLimitBytes'])} limit: a job goes first. Rerun it when "
                                 f"there is room, or with fewer workers; resubmitting with more memory does not help")
            elif s["status"] == "out-of-memory":
                attention.append(f"{where} was killed at its {fmt_bytes(result['limits']['memoryLimitBytes'])} memory limit")
            counts = s.get("signalCounts", {})
            if (s.get("cpuThrottledSeconds") or 0) > 0.5 * max(s.get("wallSeconds") or 0, 1):
                attention.append(f"{where} was held back {fmt_seconds(s['cpuThrottledSeconds'])} by its {result['limits']['cpus']:g}-CPU quota "
                                 f"in {fmt_seconds(s['wallSeconds'])}: it would run faster with more CPUs (a JVM needs 2)")
            if s["status"] == "passed" and s.get("oomKills"):
                attention.append(f"{where} passed, but the kernel killed {s['oomKills']} process(es) in it at the memory limit")
            if s["status"] == "passed":
                for key, what in adapter.SUSPICIOUS:
                    if counts.get(key):
                        attention.append(f"{where} passed, but {what} ({counts[key]}×)")
        usage = result["usage"]
        if usage["memoryOfEstimate"] and usage["memoryOfEstimate"] > 1.5:
            attention.append(f"peak memory {fmt_bytes(peak)} is {usage['memoryOfEstimate']}× the estimate")
        if usage["durationOfEstimate"] and usage["durationOfEstimate"] > 2:
            attention.append(f"took {fmt_seconds(wall)}, {usage['durationOfEstimate']}× the estimate")
        result["attention"] = list(dict.fromkeys(attention))
        verdicts = adapter.verdicts(steps)
        counts = {}
        for s in steps:
            counts[s["status"]] = counts.get(s["status"], 0) + 1
        result["summary"] = (f"{result['status']}: " + ", ".join(f"{n} {k}" for k, n in counts.items()) +
                             (f" step(s) in {fmt_seconds(wall)}, peak {fmt_bytes(peak)} (estimated {fmt_seconds(job_plan['durationEstimate'])}, "
                              f"{fmt_bytes(job_plan['memoryEstimate'])})" if measured else "") +
                             (f"; {len(result['outputs'])} output file(s) changed" if result["outputs"] else "") +
                             (f"; signals: {'; '.join(dict.fromkeys(verdicts))}" if verdicts else ""))[:600]

    def stop_all(self):
        self.stopping = True
        for entry in list(self.running.values()):
            for step in entry["steps"]:
                step.cancelled = True


# jj's default snapshot.max-new-file-size: a new file larger than this is left out of every commit (VF-020), so
# collect keeps a changes.diff over it gzipped, or, when even that is too large, as a summary of what it changes.
DIFF_MAX_BYTES = 1 << 20


def diff_stat(diff):
    """Each file a unified diff changes, with its added and removed lines, like `git diff --stat`."""
    files, current = [], None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = [line[4:].removeprefix("b/"), 0, 0]
            files.append(current)
        elif line.startswith(("Binary file ", "File ")):
            files.append([line, None, None])
            current = None
        elif current and line.startswith("+"):
            current[1] += 1
        elif current and line.startswith("-") and not line.startswith("--- "):
            current[2] += 1
    return "".join(f"{f[0]} | +{f[1]} -{f[2]}\n" if f[1] is not None else f"{f[0]}\n" for f in files)


def keep_diff(src, dest, result):
    """Copies a run's changes.diff into its collected result, so that a commit can hold it: as it is when it fits
    under DIFF_MAX_BYTES, else gzipped, else as diff_stat()'s summary. result.json names the file kept."""
    data = src.read_bytes()
    if len(data) <= DIFF_MAX_BYTES:
        shutil.copy2(src, dest / "changes.diff")
        result["changesDiff"] = "changes.diff"
        return None
    packed = gzip.compress(data, mtime=0)
    if len(packed) <= DIFF_MAX_BYTES:
        kept, how = "changes.diff.gz", "gzipped"
        (dest / kept).write_bytes(packed)
    else:
        kept, how = "changes.stat", "summarized"
        text = data.decode(errors="replace")
        (dest / kept).write_text(f"changes.diff, {len(data):,} bytes ({len(packed):,} gzipped), is over the "
                                 f"{DIFF_MAX_BYTES:,} a commit takes: the files it changes, with lines added and "
                                 f"removed. The outputs themselves are in the working copy, or under outputs/ if "
                                 f"not applied.\n\n" + diff_stat(text))
    result["changesDiff"] = kept
    return {"bytes": len(data), "kept": kept, "how": how}


def text_diff(path, old, new):
    try:
        a = old.decode().splitlines(keepends=True) if old is not None else []
        b = new.decode().splitlines(keepends=True)
    except UnicodeDecodeError:
        return f"Binary file {path} changed\n"
    if len(a) + len(b) > 20000:
        return f"File {path} changed: {len(a)} -> {len(b)} lines, too long to diff here\n"
    lines = list(difflib.unified_diff(a, b, f"a/{path}" if old is not None else "/dev/null", f"b/{path}"))
    return "".join(l if l.endswith("\n") else l + "\n\\ No newline at end of file\n" for l in lines)


# Commands


NUDGE = "nudge"  # in the state directory: its time says when the queue last changed, as far as anyone said


def nudge_time(state):
    try:
        return (state / NUDGE).stat().st_mtime_ns
    except OSError:
        return 0


def runner_pid(state):
    """The pid of the runner at work on this state directory, or None. Read from what the runner wrote into its lock
    file, not by trying the lock: a lock taken to look would turn away a runner starting at that moment."""
    try:
        pid = int((state / "runner.lock").read_text().strip() or 0)
        if pid and b"pipeline.py" in Path(f"/proc/{pid}/cmdline").read_bytes():
            return pid
    except (OSError, ValueError):
        pass
    return None


def uncollected(state):
    """The jobs that have finished and wait for `collect` (a cancelled one runs again, so it does not)."""
    results = state / "results"
    out = []
    for p in sorted(results.iterdir()) if results.exists() else []:
        try:
            if json.loads((p / "result.json").read_text()).get("status") != "cancelled":
                out.append(p.name)
        except (OSError, ValueError):
            pass  # not written yet
    return out


def cmd_nudge(args):
    """Say that the queue changed, so nobody waits out an interval to find out: a job was committed, or priorities
    were. sync.py commit does it for a commit that touches the queue, and the watcher of a proof loop for a job it
    sees waiting. The intervals stay, for a change nobody announced."""
    state = load_config(args)["runner"]["state_dir"]
    if args.where:
        print(state / NUDGE)
        return 0
    state.mkdir(parents=True, exist_ok=True)
    (state / NUDGE).write_text(iso(now()) + "\n")
    pid = runner_pid(state)
    print(f"the runner (pid {pid}) reads the queue again now" if pid else
          "no runner is at work: a verification loop waiting for work looks at the queue now")
    return 0


def cmd_wait(args):
    """Block until there is something to do about a run under way: a job has finished and waits to be collected
    (exit 0, naming them), or no runner is at work and nothing waits (exit 0). Exit 3 when neither happened in
    --timeout seconds: the caller waits again. With it, whoever manages a run collects each result as it comes,
    where waiting for the runner to end holds a short job's result back behind the longest one."""
    state = load_config(args)["runner"]["state_dir"]
    start = time.monotonic()
    while True:
        ready, pid = uncollected(state), runner_pid(state)
        claims = len(list((state / "claims").iterdir())) if (state / "claims").exists() else 0
        at_work = f"the runner (pid {pid}) is at work, {claims} job(s) running" if pid else "no runner is at work"
        if ready:
            print(f"finished, not collected: {' '.join(ready)}\n{at_work}")
            return 0
        # A runner started a moment ago may not have written its pid yet.
        if not pid and time.monotonic() - start >= min(5, args.timeout):
            print(f"{at_work}, and nothing waits to be collected")
            return 0
        if time.monotonic() - start >= args.timeout:
            print(f"nothing has finished yet: {at_work}; wait again")
            return 3
        time.sleep(1)


def repo_store(root: Path = None) -> Path | None:
    """jj's store of this repository, which all of its workspaces share (.jj/repo in the default workspace, and a file
    naming it, relative to .jj, in each other one); None outside jj."""
    j = (root or ROOT) / ".jj" / "repo"
    try:
        if j.is_dir():
            return j.resolve()
        if j.is_file():
            store = (j.parent / j.read_text().strip()).resolve()
            return store if store.is_dir() else None
    except OSError:
        pass
    return None


def take_repo_lock(state: Path):
    """The runner's lock across every workspace of this repository (VF-051). Each workspace has its own .state and so
    its own runner.lock; on 2026-11-21 a run's agent started a second runner in its workspace, which started the jobs
    the watcher's runner was running, under the same scope names, so systemd stopped the first ones. Returns the open
    lock (kept for the runner's life), or exits naming the workspace whose runner holds it."""
    store = repo_store()
    if store is None:
        return None
    lock = open(store / "verification-runner.lock", "a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.seek(0)
        holder = lock.read().strip() or "another workspace"
        sys.exit(f"another workspace's runner is at work in this repository ({holder}): run the queue from there, "
                 f"or stop that runner first; a runner per repository, since two run the same jobs")
    lock.truncate(0)
    lock.write(f"pid {os.getpid()}, {ROOT}\n")
    lock.flush()
    return lock


def cmd_run(args):
    config = load_config(args)
    isolation = isolation_of(config["runner"])
    runner = Runner(config, isolation)
    lock = open(runner.state / "runner.lock", "a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(f"another runner is using {runner.state}")
    shared = take_repo_lock(runner.state)  # noqa: F841  (held until the runner exits)
    lock.truncate(0)
    lock.write(f"{os.getpid()}\n")  # for runner_pid: who is at work here
    lock.flush()
    runner.clear_stale_claims()
    try:  # what an earlier runner left unsealed (it was killed, or its capture failed) is sealed now, where it is
        for row in recover(runner.state):
            print(f"note  {row['what']} {row['id']}: nothing had sealed it; " + ("sealed now" if row["sealed"] else
                  f"still only on this machine ({row.get('error') or 'see capture.log'}): `pipeline.py recover` tries again"), flush=True)
    except Exception as e:  # never keeps a runner from starting
        print(f"note  recover: {type(e).__name__}: {e}", file=sys.stderr, flush=True)

    def interrupted(signum, _frame):
        print(f"stopping on {signal.Signals(signum).name}: running steps are cancelled, their jobs recorded", flush=True)
        runner.stop_all()
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)

    r = config["runner"]
    print(f"runner: {r['workers']} worker(s), {r['cpus']:g} CPUs, {fmt_bytes(r['memory'])} "
          f"(at most {fmt_bytes(r['job_memory_max'])} a job), isolation {isolation}, keeping {fmt_bytes(r['memory_floor'])} "
          f"of the machine free, jobs at oom_score_adj {r['job_oom_score_adj']}, state {runner.state}", flush=True)
    wanted = set(args.ids) if args.ids else None
    told = set()
    # The queue is read at the start, at once after a nudge, and every poll_seconds for a change nobody announced:
    # a job committed while another runs starts beside it, within the budget, and does not wait for this run to end.
    last_scan, queue, blocked, nudged, last_look = None, [], None, nudge_time(runner.state), False
    while not runner.stopping:
        if r["memory_floor"] and runner.running:
            available = mem_available()
            if available is not None and available < r["memory_floor"]:
                runner.relieve(available)
        if last_scan is None or nudge_time(runner.state) != nudged or time.monotonic() - last_scan > r["poll_seconds"]:
            nudged = nudge_time(runner.state)
            revs = [resolve(args.rev)] if args.rev else queue_revs()
            with runner.lock:
                queue = runner.pending(revs, wanted, args.min_priority)
            last_scan = time.monotonic()
        for job, path, source in list(queue):
            job_plan = plan(job, config)
            if job_plan["cannotRun"]:
                if job["id"] not in told:
                    print(f"{job['id']}: deferred: {'; '.join(job_plan['cannotRun'])}", flush=True)
                    told.add(job["id"])
                queue.remove((job, path, source))
                continue
            problems = validate(job, "job.schema.json")
            if problems:
                if job["id"] not in told:
                    print(f"{job['id']}: invalid, not run: {'; '.join(problems[:5])}", flush=True)
                    told.add(job["id"])
                queue.remove((job, path, source))
                continue
            with runner.lock:
                memory = runner.reservation(job, job_plan, source)
                why = runner.fits(job_plan["cpus"], memory)
                if why and not runner.running and not args.watch:
                    # Nothing of ours holds the room it waits for: only the rest of the machine does.
                    if job["id"] not in told:
                        print(f"{job['id']}: not started: {why}; rerun when there is room, or use --watch to wait", flush=True)
                        told.add(job["id"])
                    queue.clear()
                    break
                if why and why != blocked and not runner.running:
                    print(f"{job['id']}: waiting: {why}", flush=True)
                blocked = why
                if why is None and runner.start(job, path, source, job_plan, memory):
                    last_look = False
                    print(f"{job['id']}: started at {source[:12]} ({job_plan['cpus']:g} CPU, limit {fmt_bytes(job_plan['memoryLimit'])}, "
                          f"timeout {fmt_seconds(job_plan['timeout'])})", flush=True)
                    queue.remove((job, path, source))
                elif why:
                    break  # in priority order: a later job does not overtake one that is waiting for room
        if not runner.running and not queue and not args.watch:
            if last_look:
                break
            last_scan, last_look = None, True  # one more look: a job may have come in since the last one
            continue
        time.sleep(1)
    for entry in list(runner.running.values()):
        entry["thread"].join()
    lock.truncate(0)
    finished = runner.finished
    print(f"finished {len(finished)} job(s)" + (f": {', '.join(finished)}" if finished else "") +
          ("; collect them with: python3 verification/pipeline.py collect" if finished else ""))
    return 0


def cmd_status(args):
    config = load_config(args)
    state = config["runner"]["state_dir"]
    revs = [resolve(args.rev)] if args.rev else queue_revs()
    rev = revs[0]
    claims = {p.name: json.loads(p.read_text() or "{}") for p in (state / "claims").iterdir()} if (state / "claims").exists() else {}
    finished = sorted(p.name for p in (state / "results").iterdir() if (p / "result.json").exists()
                      and json.loads((p / "result.json").read_text()).get("status") != "cancelled") if (state / "results").exists() else []
    collected = sorted(layout.results(ROOT))
    elsewhere = {i: head for i, head in recorded_on_heads().items() if i not in collected and i not in finished}
    rows = {"pending": [], "running": [], "finished, not collected": [], "recorded on another head": [], "collected": []}
    seen = set()
    priorities = load_priorities(rev)
    waiting = lambda job_id: job_id not in collected and job_id not in finished and job_id not in claims and job_id not in elsewhere
    for job, path, source in sorted(queued_jobs(revs, waiting), key=queue_order(priorities)):
        job_id = job.get("id")
        seen.add(job_id)
        p = plan(job, config)
        line = f"{job_id}  {job.get('title', '')}"
        if job_id in elsewhere:
            rows["recorded on another head"].append(f"{line}  (in commit {elsewhere[job_id][:12]}, which this working copy "
                                                    f"is not on: merge it; the job is not run again)")
        elif job_id in collected:
            res = json.loads((layout.find_result(ROOT, job_id) / "result.json").read_text())
            rows["collected"].append(f"{line}  [{res['status']}]")
        elif job_id in finished:
            res = json.loads((state / "results" / job_id / "result.json").read_text())
            rows["finished, not collected"].append(f"{line}  [{res['status']}]")
        elif job_id in claims:
            rows["running"].append(f"{line}  (since {claims[job_id].get('at')}, pid {claims[job_id].get('pid')})")
        else:
            fit = "; cannot run here: " + "; ".join(p["cannotRun"]) if p["cannotRun"] else ""
            level = priority_of(job, priorities)
            why = (priorities.get(job_id) or {}).get("reason")
            mark = f"[priority {level}{': ' + why if why else ''}]  " if level else ""
            rows["pending"].append(f"{mark}{line}  ({p['cpus']:g} CPU, {fmt_bytes(p['memoryEstimate'])}, ~{fmt_seconds(p['durationEstimate'])}"
                                   f" at {source[:12]}){fit}")
    for job_id in finished:
        if job_id not in seen:
            rows["finished, not collected"].append(f"{job_id}  (job file no longer in {rev[:12]})")
    uncommitted = sorted(layout.jobs(ROOT))
    not_committed = [j for j in uncommitted if j not in seen]
    if args.json:
        print(json.dumps({**rows, "not committed": not_committed}, indent=2))
        return 0
    for name, lines in rows.items():
        if name == "collected" and not args.all:
            print(f"{name}: {len(lines)}" + ("  (--all lists them)" if lines else ""))
            continue
        print(f"{name}: {len(lines)}")
        for l in lines:
            print("  " + l)
    if not_committed:
        print(f"not committed, so not runnable yet: {', '.join(not_committed)}")
    if load_priorities() != priorities:
        print(f"{PRIORITIES} has uncommitted changes: the runner reads it from {rev[:12]}, so commit them first")
    return 0


def cmd_prioritize(args):
    """Set, clear or list the queue's priorities in verification/priorities.json (committed, read by the runner at
    the same commit as the jobs). A priority set here overrides the job's own."""
    path = ROOT / PRIORITIES
    document = json.loads(path.read_text()) if path.exists() else {}
    jobs = document.setdefault("jobs", {})
    if not args.ids:
        for job_id, entry in sorted(jobs.items(), key=lambda kv: (-kv[1]["priority"], kv[0])):
            print(f"{entry['priority']:>4}  {job_id}  {entry.get('reason', '')}")
        return 0
    known = {j.get("id") for j, _, _ in committed_jobs(default_rev(), lambda _: False)} | set(layout.jobs(ROOT))
    unknown = [i for i in args.ids if i not in known]
    if unknown and not args.clear:
        sys.exit(f"no such job: {', '.join(unknown)}")
    for job_id in args.ids:
        if args.clear:
            jobs.pop(job_id, None)
        else:
            if args.priority is None or not args.reason:
                sys.exit("give --priority N and --reason TEXT, or --clear")
            jobs[job_id] = {"priority": args.priority, "reason": args.reason, "at": iso(now())}
    document["jobs"] = dict(sorted(jobs.items()))
    write_json(path, {"description": "The verification queue's priorities, by job id; higher runs first, and a "
                      "priority here overrides the job's own. Set with: python3 verification/pipeline.py prioritize",
                      "jobs": document["jobs"]})
    print(f"{'cleared' if args.clear else 'set'} {len(args.ids)} job(s) in {PRIORITIES}; commit it so the runner sees it")
    return 0


def collectors_own():
    """What a commit of collected results holds besides the outputs applied: the records' folder, and what the
    workloads' hooks after a collect regenerate (the verification workload's examples table)."""
    return (HERE, *workload("verification").COLLECTORS_OWN)


def cmd_commit_paths(args):
    """What a commit of collected results holds, one path a line, for `sync.py commit --only`: this folder (the
    results, the findings, a resubmitted job), the examples table that collecting regenerates, and the outputs
    applied for each result that is not committed yet. Anything else changed in the working copy is another
    session's, and a commit of these paths alone leaves it where it is."""
    paths = list(collectors_own())
    proc = run_quiet(["jj", "diff", "--name-only", RESULTS], cwd=ROOT) if (ROOT / ".jj").exists() and shutil.which("jj") \
        else run_quiet(["git", "status", "--porcelain", "--untracked-files=all", RESULTS], cwd=ROOT)
    changed = {Path(line.split()[-1]).parent for line in proc.stdout.splitlines()
               if (layout.result_id_of(line.split()[-1]) or ("", ""))[1] == "result.json"}
    for folder in sorted(changed):
        try:
            applied = (json.loads((ROOT / folder / "result.json").read_text()).get("collected") or {}).get("applied") or []
        except (OSError, ValueError):
            continue
        paths += [a for a in applied if a not in paths and not a.startswith(HERE + "/")]
    print("\n".join(paths))
    return 0


def legacy_attempt(state_dir: Path, job_id: str) -> int:
    """The attempt that a run directory of before 2026-11-27 (STATE/runs/ID, shared by every run of a job) was
    sealed as, by the marker its sealing left; 0 when it has none."""
    try:
        return int(json.loads((Path(state_dir) / "runs" / job_id / ".captured").read_text()).get("attempt") or 0)
    except (OSError, ValueError, TypeError):
        return 0


def open_archive():
    """The archive's journal on this machine (llm-dlc/tools/artifacts.py), or None where nothing captures."""
    capture = originals()
    arts = capture.tool(ROOT) if capture else None
    try:
        return arts.Archive() if arts else None
    except Exception:
        return None


def collected_receipt(job_id: str) -> dict | None:
    folder = layout.find_result(ROOT, job_id)
    try:
        return json.loads((folder / "result.json").read_text()) if folder else None
    except (OSError, ValueError):
        return None


def staged_attempt(state_dir: Path, job_id: str):
    """The attempt whose result is staged and not collected: its id, or its number for a runner of before attempts
    had ids, or None when nothing is staged."""
    try:
        staged = json.loads((Path(state_dir) / "results" / job_id / "result.json").read_text())
    except (OSError, ValueError):
        return None
    return (staged.get("attempt") or {}).get("id") or (staged.get("originals") or {}).get("attempt") or "unnumbered"


def verified(states: dict, occurrences: dict, job_id: str, number: int | None) -> str | None:
    """Why these sealed originals do not let their source go, or None when every one is this job's, this attempt's
    and read back from the store."""
    for name, occurrence in sorted(occurrences.items()):
        known = states.get(occurrence)
        if known is None:
            return f"the archive here does not know its {name} original ({occurrence})"
        if known["job"] != job_id or (known["attempt"] is not None and number is not None and known["attempt"] != number):
            return f"its {name} original ({occurrence}) is recorded for another job or attempt"
        if known["state"] != "remote_verified":
            return f"its {name} original is {known['state'] if known['state'] != 'locally_sealed' else 'sealed here'}, not yet verified in the store"
    return None


def attempt_refusal(attempt, receipt, staged, states, unarchived=False) -> str | None:
    """Why an attempt's work directory stays, or None when `prune` may remove it: the job's result is collected,
    the collected receipt is of this attempt or of a later one, the original sealed from *this* attempt's work
    directory is verified in the store with the attempt's other originals, and the folder is still what was
    sealed. The latest original of the job's work directory being verified says nothing of a later attempt whose
    capture failed, which is what was asked until 2026-11-27."""
    record = attempt.record
    if attempt.state() == "running":
        return "its runner is at work"
    if receipt is None:
        return "its job's result is not collected"
    if staged is not None and staged in (attempt.id, attempt.number):
        return "its result is staged and not collected yet"
    of_receipt = receipt.get("attempt") or {}
    number = of_receipt.get("number") or (receipt.get("originals") or {}).get("attempt")
    if of_receipt.get("id") != attempt.id and (number is None or attempt.number >= number):
        return "the collected receipt is of another attempt, and not of a later one"
    capture = record.get("capture") or {}
    if record.get("status") == "passed":
        return None  # not an original: the logs, the outputs and the diff are what a passed job's attempt keeps
    if capture.get("state") == "off":
        return None if unarchived else "nothing captured originals when it ran: `prune --unarchived` removes it all the same"
    if capture.get("state") not in ("sealed", "recovered"):
        return f"its originals are not sealed ({capture.get('state') or 'no record'}): `recover` seals them"
    occurrences = capture.get("occurrences") or {}
    if "workdir" not in occurrences:
        return "no original of its work directory was sealed"
    if of_receipt.get("id") == attempt.id and ((receipt.get("originals") or {}).get("occurrences") or {}).get("workdir") not in (None, occurrences["workdir"]):
        return "the collected receipt names another original of the work directory"
    refused = verified(states, occurrences, attempt.job, attempt.number)
    if refused:
        return refused
    was = (capture.get("fingerprints") or {}).get("work")
    now_ = attempts.fingerprint(attempt.work_dir)
    if not was or not now_ or was["sha256"] != now_["sha256"]:
        return "its work directory is not what was sealed: it changed since"
    return None


def legacy_refusal(state_dir: Path, job_id: str, receipt, staged, states) -> str | None:
    """The same for a work directory of before attempts had folders (STATE/work/ID, reused by every run of its job):
    the bytes on disk are tied to the collected receipt's attempt by the marker its sealing left in the job's run
    directory, which a later run would have cleared."""
    if (state_dir / "claims" / job_id).exists():
        return "a runner holds its job"
    if receipt is None:
        return "its job's result is not collected"
    if staged is not None:
        return "a result of its job is staged and not collected yet"
    originals_ = receipt.get("originals") or {}
    occurrence = (originals_.get("occurrences") or {}).get("workdir")
    if not occurrence:
        return "the collected receipt names no original of the work directory"
    if legacy_attempt(state_dir, job_id) != originals_.get("attempt"):
        return "nothing ties the folder to the attempt the receipt names (its run directory's seal is of another attempt, or gone)"
    return verified(states, {"workdir": occurrence}, job_id, originals_.get("attempt"))


def prune_workdirs(state_dir: Path, archive=None, dry_run: bool = False, unarchived: bool = False, kept: list | None = None) -> list[tuple[str, int]]:
    """Remove the work directories kept for jobs that did not pass once they are of no more use here. One goes only
    when the job's result is collected and the original sealed from that very attempt's work directory is verified
    in the store, so that `artifacts.py fetch` restores it (`attempt_refusal`, `legacy_refusal`). (attempt or job
    id, bytes) for each, removed unless DRY_RUN; `kept` takes (id, why) for each that stays. Without an archive
    nothing sealed is known to be verified, and only what was never an original goes. A failed setup batch kept
    ~2 GB a job (about 80 GB for one 49-job batch on 2026-11-27)."""
    state_dir = Path(state_dir)
    archive = archive if archive is not None else open_archive()
    gone, receipts = [], {}

    def receipt_of(job_id):
        if job_id not in receipts:
            receipts[job_id] = collected_receipt(job_id)
        return receipts[job_id]

    def states_of(occurrences):
        try:
            return archive.occurrence_states(list(occurrences)) if archive is not None and occurrences else {}
        except Exception:
            return {}

    for attempt in attempts.every(state_dir):
        if not attempt.work_dir.is_dir():
            continue
        receipt = receipt_of(attempt.job)
        occurrences = ((attempt.record.get("capture") or {}).get("occurrences") or {}).values()
        why = attempt_refusal(attempt, receipt, staged_attempt(state_dir, attempt.job), states_of(occurrences), unarchived)
        if why:
            if kept is not None:
                kept.append((attempt.id, why))
            continue
        size = (attempts.fingerprint(attempt.work_dir) or {}).get("bytes", 0)
        if not dry_run:
            attempt.release("work", "pruned: its job's result is collected, and "
                            + ("its originals are verified in the store" if attempt.record.get("status") != "passed"
                               and (attempt.record.get("capture") or {}).get("state") != "off" else "it holds no original"))
        gone.append((attempt.id, size))
    work = state_dir / "work"
    for folder in sorted(p for p in work.iterdir() if p.is_dir()) if work.is_dir() else []:
        job_id = folder.name
        receipt = receipt_of(job_id)
        occurrence = (((receipt or {}).get("originals") or {}).get("occurrences") or {}).get("workdir")
        why = legacy_refusal(state_dir, job_id, receipt, staged_attempt(state_dir, job_id), states_of([occurrence] if occurrence else []))
        if why:
            if kept is not None:
                kept.append((job_id, why))
            continue
        size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file() and not f.is_symlink())
        if not dry_run:
            shutil.rmtree(folder, ignore_errors=True)
        gone.append((job_id, size))
    return gone


def cmd_prune(args):
    config = load_config(args)
    kept = []
    gone = prune_workdirs(config["runner"]["state_dir"], dry_run=args.dry_run, unarchived=args.unarchived, kept=kept)
    total = sum(n for _, n in gone)
    if args.json:
        print(json.dumps({"schema": "itl-job-prune/v1", "dryRun": args.dry_run, "bytes": total,
                          "removed": [{"id": name, "bytes": n} for name, n in gone],
                          "kept": [{"id": name, "why": why} for name, why in kept]}, indent=2))
        return 0
    for name, n in gone:
        print(f"{'would remove' if args.dry_run else 'removed'} {name}: {n / 2**30:.1f} GiB")
    if args.why:
        for name, why in kept:
            print(f"kept {name}: {why}")
    print(f"{len(gone)} kept work director{'y' if len(gone) == 1 else 'ies'}, {total / 2**30:.1f} GiB"
          + (" (dry run)" if args.dry_run else " freed")
          + (f"; {len(kept)} stay" + ("" if args.why else " (--why says why each)") if kept else "")
          + ("" if gone else ": none is both collected and verified in the store yet"))
    return 0


def recover(state_dir: Path, dry_run: bool = False) -> list[dict]:
    """Seal what an attempt left that nothing sealed: an attempt whose runner died, one whose capture failed, a run
    directory of before attempts had folders, a staged result that a collect set aside. Each is sealed where it is
    and stays there (`prune` releases it later, by its own rule). One row for each thing looked at that needed it:
    what, and whether it is sealed now. Does nothing where nothing captures originals."""
    capture, state_dir = originals(), Path(state_dir)
    if not capture or not capture.available(ROOT):
        return []
    done = []
    for attempt in attempts.every(state_dir):
        state, held = attempt.state(), (attempt.record.get("capture") or {}).get("state")
        if state not in ("interrupted", "finished") or held not in ("pending", "failed"):
            continue
        row = {"what": "attempt", "id": attempt.id, "job": attempt.job, "state": state, "sealed": False}
        done.append(row)
        if dry_run:
            continue
        try:
            result = json.loads((attempt.folder / "result.json").read_text())
        except (OSError, ValueError):
            result = None
        errors = []
        sealed = capture.sealed_run(
            ROOT, state_dir, attempt.record.get("spec") or {"id": attempt.job}, attempt.number, attempt.record.get("source"),
            attempt.run_dir, attempt.work_dir if attempt.work_dir.is_dir() else None, result, attempt_id=attempt.id, errors=errors,
            status="complete" if state == "finished" else "partial",
            why="sealed by recover: " + ("its capture failed when it ran" if state == "finished" else
                                         "the attempt did not finish, and its runner sealed nothing"))
        if state == "interrupted" and attempt.record.get("state") == "running":
            attempt.save(state="interrupted", interruptedSeenAt=attempts.now())
        if sealed:
            attempt.captured("recovered", sealed["occurrences"], number=sealed["attempt"])
            row.update(sealed=True, occurrences=sealed["occurrences"])
        else:
            attempt.captured("failed", error=errors[-1] if errors else "see capture.log")
            row["error"] = errors[-1] if errors else None
    runs = state_dir / "runs"
    for run_dir in sorted(p for p in runs.iterdir() if p.is_dir()) if runs.is_dir() else []:
        job_id = run_dir.name
        if (state_dir / "claims" / job_id).exists() or (run_dir / ".captured").exists() or not any(run_dir.iterdir()):
            continue
        row = {"what": "run directory", "id": job_id, "job": job_id, "sealed": False}
        done.append(row)
        if dry_run:
            continue
        source = (collected_receipt(job_id) or {}).get("sourceCommit")
        work, errors = state_dir / "work" / job_id, []
        made = capture.rescue_legacy(ROOT, state_dir, job_id, source, run_dir, work if work.is_dir() else None, errors)
        row.update(sealed=made is not None, occurrences=made or {}, **({"error": errors[-1]} if errors else {}))
    aside = state_dir / "uncaptured"
    for folder in sorted(p for p in aside.iterdir() if p.is_dir()) if aside.is_dir() else []:
        if (folder / ".captured").exists():
            continue
        job_id = folder.name.rsplit("-", 1)[0]
        row = {"what": "result set aside", "id": folder.name, "job": job_id, "sealed": False}
        done.append(row)
        if dry_run:
            continue
        errors = []
        occurrence = capture.set_aside(ROOT, state_dir, folder, job_id, errors)
        row.update(sealed=occurrence is not None, occurrences={"result": occurrence} if occurrence else {},
                   **({"error": errors[-1]} if errors else {}))
    return done


def recover_kept_outputs(state_dir: Path, dry_run: bool = False) -> list[dict]:
    """Seal the outputs that receipts say were kept and that this working copy holds while no commit does (their
    paths are ignored, or they are over the commit's limit: VF-080). One row a job."""
    capture = originals()
    if not capture or not capture.available(ROOT):
        return []
    audit = records.load("jobs_audit", Path(__file__).resolve().parent / "audit.py")
    check = audit.Audit(ROOT, default_rev())
    check.read_specs()
    check.read_receipts()
    check.check_artifacts()
    jobs, done = {}, []
    for gap in check.gaps:
        if gap["kind"] == "artifact-not-committed" and gap["what"] == "kept output" and not gap.get("occurrence") \
                and (ROOT / gap["path"]).is_file():
            jobs.setdefault(gap["id"], []).append(gap["path"])
    for job_id, paths in sorted(jobs.items()):
        folder = layout.find_result(ROOT, job_id)
        marker = Path(state_dir) / "recovered-outputs" / job_id
        if folder is None or marker.exists():
            continue
        row = {"what": "kept outputs", "id": job_id, "job": job_id, "files": len(paths), "sealed": False}
        done.append(row)
        if dry_run:
            continue
        receipt, errors = check.receipts[job_id][1], []
        occurrence = capture.kept_outputs(ROOT, state_dir, job_id, folder, receipt.get("sourceCommit"),
                                          (receipt.get("originals") or {}).get("attempt"), errors)
        if occurrence:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({"occurrence": occurrence, "files": len(paths), "at": iso(now())}) + "\n")
        row.update(sealed=bool(occurrence), occurrences={"outputs": occurrence} if occurrence else {},
                   **({"error": errors[-1]} if errors else {}))
    return done


def cmd_recover(args):
    config = load_config(args)
    state = config["runner"]["state_dir"]
    capture = originals()
    if not capture or not capture.available(ROOT):
        print("nothing captures originals here (no archive tool, or ITL_ORIGINALS_OFF): nothing to recover into")
        return 0
    done = recover(state, args.dry_run) + (recover_kept_outputs(state, args.dry_run) if args.kept_outputs else [])
    if args.json:
        print(json.dumps({"schema": "itl-job-recovery/v1", "dryRun": args.dry_run, "recovered": done}, indent=2))
        return 0 if args.dry_run or all(r["sealed"] for r in done) else 1
    for row in done:
        said = "would seal" if args.dry_run else "sealed" if row["sealed"] else "NOT sealed"
        print(f"{said}: {row['what']} {row['id']}" + (f" ({row['files']} file(s))" if row.get("files") else "")
              + (f": {row['error']}" if row.get("error") else ""))
    left = [r for r in done if not r["sealed"]] if not args.dry_run else []
    print(f"{len(done)} thing(s) that nothing had sealed" + (" (dry run)" if args.dry_run else
          f"; {len(done) - len(left)} sealed now" + (f", {len(left)} still only on this machine (the state directory's capture.log says why)" if left else "")))
    return 1 if left else 0


def cmd_collect(args):
    config = load_config(args)
    state = config["runner"]["state_dir"] / "results"
    ids = sorted(p.name for p in state.iterdir() if (p / "result.json").exists()) if state.exists() else []
    if args.ids:
        ids = [i for i in ids if i in set(args.ids)]
    else:  # a cancelled job runs again; collect it only by name
        ids = [i for i in ids if json.loads((state / i / "result.json").read_text()).get("status") != "cancelled"]
    if not ids:
        print("nothing to collect")
        return 0
    applied_any, lines, fresh = False, [], []
    tally = {"applied": 0, "none": 0, "kept": 0, "conflicts": 0}
    for job_id in ids:
        src = state / job_id
        result = json.loads((src / "result.json").read_text())
        dest = layout.new_result(ROOT, job_id)  # beside its job: flat for a flat job, in the day's shard for a sharded one
        capture = originals()
        staged_digest = sha256((src / "result.json").read_bytes())
        if already_collected(dest, staged_digest):
            # An earlier collect wrote this very result and was stopped before it released the staged one (after
            # its files were written, or after they were committed). The tree keeps what it has, to the byte, so
            # nothing is published a second time; only the release is left to do.
            kept_result = json.loads((dest / "result.json").read_text())
            if capture and not (src / COLLECTED_MARK).exists():  # stopped between writing the result and sealing it
                capture.after_collect(ROOT, config["runner"]["state_dir"], job_id, dest, kept_result)
            if release_staged(capture, config, job_id, src, dest, kept_result, result):
                print(f"{job_id}: {kept_result['status']}: was collected before; its staged result is released now")
            else:
                print(f"{job_id}: {kept_result['status']}: was collected before; its staged result is set aside, not sealed")
            continue
        run_dir = Path(result["attempt"]["folder"]) / "run" if (result.get("attempt") or {}).get("folder") else None
        sealed = capture.before_collect(ROOT, config["runner"]["state_dir"], job_id, src, dest, result, run_dir) if capture else True
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        if (src / "logs").is_dir():
            shutil.copytree(src / "logs", dest / "logs")
        diff_kept = keep_diff(src / "changes.diff", dest, result) if (src / "changes.diff").exists() else None
        applied, conflicts, kept = [], [], []
        apply = result["status"] == "passed" or args.apply_failed
        for out in result["outputs"]:
            rel = out["path"]
            if out["change"] == "deleted":
                kept.append(rel)
                continue
            new = (src / "outputs" / rel).read_bytes()
            current_path = ROOT / rel
            current = current_path.read_bytes() if current_path.exists() else None
            source = show(result["sourceCommit"], rel)
            if not apply:
                kept.append(rel)
            elif current == new:
                applied.append(rel)
            elif current == source:
                current_path.parent.mkdir(parents=True, exist_ok=True)
                current_path.write_bytes(new)
                applied.append(rel)
            else:
                conflicts.append(rel)
            if rel in kept or rel in conflicts:
                keep = dest / "outputs" / rel
                keep.parent.mkdir(parents=True, exist_ok=True)
                keep.write_bytes(new)
        result["collected"] = {"at": iso(now()), "applied": applied, "conflicts": conflicts, "kept": kept,
                               "why": None if apply else f"not applied: the job {result['status']}",
                               # The staged result this was collected from: a collect run again on the same
                               # bytes finds its work done (already_collected).
                               "staged": staged_digest}
        if diff_kept:
            result["collected"]["changesDiff"] = diff_kept
        if conflicts:
            result["attention"].append(f"{len(conflicts)} output(s) changed in the working copy since the job's commit and were "
                                       f"not applied (kept under outputs/): rerun the job on the newer commit")
        if "$schema" in result:
            result["$schema"] = schema_ref(dest / "result.json", "result.schema.json")
        write_json(dest / "result.json", result)
        if capture:
            capture.after_collect(ROOT, config["runner"]["state_dir"], job_id, dest, result)
        (src / COLLECTED_MARK).write_text(iso(now()) + "\n")  # written and sealed: only the release is left
        release_staged(None, config, job_id, src, dest, result, result, sealed)
        fresh.append(job_id)
        applied_any = applied_any or bool(applied)
        tally["applied"] += bool(applied)
        tally["none"] += not result["outputs"]
        tally["kept"] += bool(result["outputs"]) and not apply
        tally["conflicts"] += bool(conflicts)
        lines.append(f"{job_id}: {result['summary']}" + (f" Applied {len(applied)} output(s)." if applied else "") +
                     (f" {len(conflicts)} output(s) not applied: changed since the job's commit." if conflicts else ""))
        print(f"{job_id}: {result['status']}: applied {len(applied)}, conflicts {len(conflicts)}, kept {len(kept)}")
    write_index()
    if applied_any:
        for command in config["runner"]["after_collect"]:
            proc = subprocess.run(command, shell=True, cwd=ROOT, text=True, capture_output=True)
            print(f"after collect: {command}: exit {proc.returncode}")
            if proc.returncode:
                print((proc.stdout + proc.stderr)[-2000:])
    if fresh:
        print("\nFor the commit message (python3 llm-dlc/tools/sync.py commit -m ... -m ...):")
        print(f"  Record verification results for {len(fresh)} job(s)")
        print("  " + collect_totals(tally, len(fresh)) + " " + " ".join(lines))
    else:
        print("\nNo result is new: every one here was collected before, by a collect that was stopped before it "
              "released them. What it wrote is in the working copy as it left it.")
    try:  # earlier failures' kept work directories whose originals have since been read back from the store
        pruned = prune_workdirs(config["runner"]["state_dir"])
    except Exception as e:  # never fails a collect
        pruned = []
        print(f"(kept work directories not pruned: {e})", file=sys.stderr)
    if pruned:
        print(f"\nremoved {len(pruned)} kept work director{'y' if len(pruned) == 1 else 'ies'} of failed jobs, "
              f"{sum(n for _, n in pruned) / 2**30:.1f} GiB: collected, and their originals remote_verified")
    return 0


COLLECTED_MARK = ".collected"  # in a staged result: its collected form is written and sealed, and it only waits to go


def already_collected(dest: Path, staged_digest: str) -> bool:
    """Whether the result folder in the tree is the collected form of exactly this staged result."""
    try:
        kept = json.loads((dest / "result.json").read_text())
    except (OSError, ValueError):
        return False
    return ((kept.get("collected") or {}).get("staged")) == staged_digest


def release_staged(capture, config, job_id, src, dest, collected, staged, sealed=None) -> bool:
    """The last step of a collect: the staged result goes once it is sealed, and is set aside when it could not
    be. With `capture`, it is sealed here first (a collect that was stopped before this step). Whether it went."""
    state_dir = config["runner"]["state_dir"]
    if sealed is None:
        run_dir = Path(staged["attempt"]["folder"]) / "run" if (staged.get("attempt") or {}).get("folder") else None
        sealed = True
        if capture and not staged.get("originals"):  # nothing sealed it when it ran: what before_collect would do
            sealed = capture.before_collect(ROOT, state_dir, job_id, src, state_dir / "none", staged, run_dir)
    if sealed:
        shutil.rmtree(src)
        return True
    aside = state_dir / "uncaptured" / f"{job_id}-{now().strftime('%Y%m%dT%H%M%SZ')}"
    aside.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(src, aside)
    return False


def collect_totals(tally, jobs):
    """The counts a collect's commit message states, from the lists each result's `collected` records, so that no
    one adds up the per-job lines by hand (kqpykqpp's message said 18 jobs had outputs applied where 19 had)."""
    parts = [f"Outputs applied for {tally['applied']} of the {jobs} job(s)"]
    if tally["none"]:
        parts.append(f"{tally['none']} declared or produced none")
    if tally["kept"]:
        parts.append(f"{tally['kept']} kept under outputs/, not applied (the job didn't pass)")
    if tally["conflicts"]:
        parts.append(f"{tally['conflicts']} with outputs not applied because they changed since the job's commit")
    return "; ".join(parts) + "."


def write_index():
    """One line a result, newest first: results/index.json for the results kept flat, and an index.json in each
    day's folder for the ones kept there, which the first names under "shards". So the complete index stops growing
    when new results go by day, and a day's index is rewritten only on that day's collects. The lines are computed
    from the receipts alone (jobs/records.py), which is how the audit tells a stale index."""
    receipts = {job_id: ((p / "result.json").relative_to(ROOT).as_posix(), json.loads((p / "result.json").read_text()))
                for job_id, p in layout.results(ROOT).items()}
    if not receipts and not (ROOT / RESULTS).exists():
        return
    for path, document in records.index_documents(receipts).items():
        write_json(ROOT / path, document)


def result_rel(job_id):
    """A result's folder as a repository path, wherever it is kept; the flat path for one that is not here."""
    found = layout.find_result(ROOT, job_id)
    return found.relative_to(ROOT).as_posix() if found else layout.result_rel(job_id)


def load_results(args):
    results = []
    for p in layout.results(ROOT).values():
        r = json.loads((p / "result.json").read_text())
        if args.ids and r["id"] not in args.ids:
            continue
        if args.status and r["status"] not in args.status:
            continue
        if args.since and (r["finishedAt"] or "") < args.since:
            continue
        if args.capability and not set(args.capability) & set(r["job"]["spec"].get("capabilities", [])):
            continue
        results.append(r)
    results.sort(key=lambda r: (STATUS_ORDER.index(r["status"]) if r["status"] in STATUS_ORDER else 0, r["finishedAt"] or ""))
    return results


def machine_label(r):
    """Which machine ran a result, for a reader: its host, architecture, WSL when it was, and CPUs. Estimates and
    timings are only comparable within one machine (until 2026-11-06 every result came from one 8-core WSL laptop)."""
    e = r.get("environment") or {}
    host = (r.get("runner") or {}).get("host") or e.get("host") or "?"
    wsl = " WSL2" if "microsoft" in (e.get("os") or "").lower() else ""
    cpus = f", {e['cpuCount']} CPUs" if e.get("cpuCount") else ""
    return f"{host} ({e.get('machine') or '?'}{wsl}{cpus})"


def calibration_by_host(results):
    """calibration() for each machine on its own: a ratio pooled over a laptop and a server says little of either."""
    hosts = {}
    for r in results:
        hosts.setdefault(machine_label(r), []).append(r)
    return {host: calibration(rs) for host, rs in sorted(hosts.items())}


def calibration(results):
    groups = {}
    for r in results:
        u = r.get("usage") or {}
        for cap in r["job"]["spec"].get("capabilities", []) or ["(none)"]:
            g = groups.setdefault(cap, {"jobs": 0, "duration": [], "memory": []})
            g["jobs"] += 1
            if u.get("durationOfEstimate"):
                g["duration"].append(u["durationOfEstimate"])
            if u.get("memoryOfEstimate"):
                g["memory"].append(u["memoryOfEstimate"])
    median = lambda xs: sorted(xs)[len(xs) // 2] if xs else None
    return {cap: {"jobs": g["jobs"], "medianDurationOfEstimate": median(g["duration"]),
                  "medianMemoryOfEstimate": median(g["memory"])} for cap, g in sorted(groups.items())}


def cmd_report(args):
    results = load_results(args)
    if args.format == "json":
        print(json.dumps({"schema": "verification-report/v1", "results": [{
            "id": r["id"], "title": r.get("title"), "status": r["status"], "summary": r["summary"],
            "machine": machine_label(r), "attention": r["attention"], "capabilities": r["job"]["spec"].get("capabilities", []),
            "links": r["job"]["spec"].get("links", {}), "description": r["job"]["spec"].get("description"),
            "expected": r["job"]["spec"].get("expected"), "sourceCommit": r["sourceCommit"],
            "finishedAt": r["finishedAt"], "usage": r.get("usage"), "estimate": r.get("estimate"),
            "steps": [{"name": s["name"], "status": s["status"], "exitCode": s.get("exitCode"),
                       "wallSeconds": s.get("wallSeconds"), "peakMemoryBytes": s.get("peakMemoryBytes"),
                       "signalCounts": s.get("signalCounts"), "tail": (s.get("tail") or [])[-args.tail:],
                       "log": f"{result_rel(r['id'])}/{s['log']['path']}" if s.get("log") else None} for s in r["steps"]],
            "outputs": r["outputs"], "collected": r.get("collected"),
            "result": f"{result_rel(r['id'])}/result.json"} for r in results],
            "calibration": calibration(results), "calibrationByHost": calibration_by_host(results)}, indent=2, ensure_ascii=False))
        return 0
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"# Verification results: {len(results)} job(s)" + (" (" + ", ".join(f"{n} {s}" for s, n in counts.items()) + ")" if results else ""))
    needs = [r for r in results if r["status"] != "passed" or r["attention"]]
    clean = [r for r in results if r not in needs]
    if needs:
        print("\n## Needs attention\n")
        for r in needs:
            spec = r["job"]["spec"]
            print(f"### {r['id']}: {r.get('title')}\n")
            print(f"- **{r['status']}** at `{r['sourceCommit'][:12]}`, capabilities {', '.join(spec.get('capabilities', []))}, on {machine_label(r)}")
            print(f"- {r['summary']}")
            for a in r["attention"]:
                print(f"- attention: {a}")
            if spec.get("expected"):
                print(f"- expected: {spec['expected']}")
            for s in r["steps"]:
                if s["status"] not in ("passed", "skipped"):
                    print(f"- step {s['index']} `{s['name']}` {s['status']}; last lines of `{result_rel(r['id'])}/{s['log']['path']}`:")
                    print("\n```\n" + "\n".join((s.get("tail") or [])[-args.tail:]) + "\n```")
            print(f"- result: `{result_rel(r['id'])}/result.json`\n")
    if clean:
        print("\n## Passed\n")
        for r in clean:
            print(f"- `{r['id']}` {r.get('title')}: {r['summary']} (on {machine_label(r)})")
    for host, cal in calibration_by_host(results).items():
        print(f"\n## Estimates against use on {host} (median ratio of used to estimated)\n")
        print("| capability | jobs | duration | memory |\n|---|---|---|---|")
        for cap, c in cal.items():
            print(f"| {cap} | {c['jobs']} | {c['medianDurationOfEstimate'] or '?'} | {c['medianMemoryOfEstimate'] or '?'} |")
    return 0


def new_id(title, at=None):
    at = at or now()
    return f"{at.astimezone(dt.timezone.utc):%Y%m%d-%H%M%S}-{slug(title)}"


def cmd_submit(args):
    if args.from_file:
        job = json.loads(Path(args.from_file).read_text())
    else:
        job = {}
    title = args.title or job.get("title")
    if not title:
        sys.exit("a job needs --title")
    at = now()
    job.setdefault("$schema", "../schema/job.schema.json")
    job["schema"] = JOB_SCHEMA
    job["id"] = job.get("id") or new_id(title, at)
    job["title"] = title
    if args.description:
        job["description"] = args.description
    if args.kind:
        job["kind"] = args.kind
    job["capabilities"] = list(dict.fromkeys(job.get("capabilities", []) + (args.capability or [])))
    links = job.setdefault("links", {})
    for link in args.link or []:
        key, _, value = link.partition(":")
        if not value:
            sys.exit(f"--link {link!r}: use KIND:VALUE, such as example:104 or path:lib/src/tla.rs")
        links.setdefault(key + "s" if not key.endswith("s") else key, []).append(value)
    job["submitted"] = {**job.get("submitted", {}), "at": iso(at)}
    # Without --session, the session Claude Code says is running this command: the loop statistics
    # (llm-dlc/tools/loop_stats.py) tie a job to the loop cycle that submitted it by this id.
    # The session that submits: Codex marks its commands with its thread, and one started from a Claude Code session
    # may still carry that session's id beside it, so its own comes first.
    if session := args.session or os.environ.get("CODEX_THREAD_ID") or os.environ.get("CLAUDE_CODE_SESSION_ID"):
        job["submitted"]["session"] = session
    if args.by:
        job["submitted"]["by"] = args.by
    if args.revision:
        job["revision"] = args.revision
    if args.priority is not None:
        job["priority"] = args.priority
    resources = job.setdefault("resources", {})
    for flag, key in [("cpus", "cpus"), ("memory", "memory"), ("duration", "duration"), ("memory_limit", "memoryLimit"),
                      ("timeout", "timeout"), ("estimate_notes", "notes")]:
        value = getattr(args, flag)
        if value is not None:
            resources[key] = float(value) if key == "cpus" else value
    steps = job.setdefault("steps", [])
    outputs = job.setdefault("outputs", [])
    requires = job.setdefault("requires", [])
    expected = [job["expected"]] if job.get("expected") else []
    if args.task and len(args.example or []) != 1:
        sys.exit("--task goes with exactly one --example")
    for example_id in args.example or []:
        parts = example_job_parts(example_id, args.task)
        steps.append(parts["step"])
        outputs.append(parts["output"])
        requires.extend(parts["requires"])
        job["capabilities"].append(parts["capability"])
        links.setdefault("examples", []).append(example_id)
        expected.append(parts["expected"])
        job.setdefault("kind", "example")
    for name, run in args.step or []:
        steps.append({"name": name, "run": run, "cwd": args.cwd or "."})
    for run in args.run or []:
        steps.append({"name": " ".join(run.split())[:60], "run": run, "cwd": args.cwd or "."})
    if args.expect_exit is not None:
        for s in steps:
            s["expectExit"] = args.expect_exit
    outputs.extend(args.output or [])
    requires.extend(args.requires or [])
    job["outputs"] = list(dict.fromkeys(outputs))
    job["requires"] = list(dict.fromkeys(requires))
    job["capabilities"] = list(dict.fromkeys(job["capabilities"]))
    for key in ("links",):
        job[key] = {k: list(dict.fromkeys(v)) for k, v in job[key].items()}
    if args.expected:
        expected = [args.expected]
    if expected:
        job["expected"] = "; ".join(expected)
    if args.stop_on_failure is not None:
        job["stopOnFailure"] = args.stop_on_failure == "yes"
    job.setdefault("kind", "other")
    order = ["$schema", "schema", "id", "title", "description", "kind", "capabilities", "links", "expected", "submitted",
             "revision", "priority", "requires", "resources", "env", "steps", "stopOnFailure", "outputs", "supersedes"]
    job = {k: job[k] for k in order if k in job} | {k: v for k, v in job.items() if k not in order}
    problems = validate(job, "job.schema.json")
    if problems:
        sys.exit("not a valid job:\n  " + "\n  ".join(problems))
    path = layout.new_job(ROOT, job["id"])
    job["$schema"] = schema_ref(path, "job.schema.json")
    if path.exists() and not args.force:
        sys.exit(f"{path.relative_to(ROOT)} exists")
    if args.dry_run:
        print(json.dumps(job, indent=2, ensure_ascii=False))
        return 0
    write_json(path, job)
    config = load_config()
    p = plan(job, config)
    print(f"wrote {path.relative_to(ROOT)}: {len(job['steps'])} step(s), {p['cpus']:g} CPU, {fmt_bytes(p['memoryEstimate'])}, "
          f"~{fmt_seconds(p['durationEstimate'])} (limit {fmt_bytes(p['memoryLimit'])}, timeout {fmt_seconds(p['timeout'])})")
    if p["cannotRun"]:
        local = [f for f in config["files"] if not f.endswith("/pipeline.toml")]
        print("note: the local runner cannot run it: " + "; ".join(p["cannotRun"]) + ". It waits for a bigger runner. "
              + (f"(This runner's settings: {', '.join(local)}.)" if local else
                 "(Judged by the committed defaults alone, which suit a laptop: no machine file "
                 f"({machine_config() or 'none'}) and no verification/pipeline.local.toml was found, so the runner here "
                 "may well allow more.)"))
    print("Commit it with the change, marked verification pending (verification/README.md).")
    return 0


def cmd_resubmit(args):
    old_path = layout.find_job(ROOT, args.id)
    if old_path is None:
        sys.exit(f"{layout.job_rel(args.id)} not found (nor in its day's shard)")
    job = json.loads(old_path.read_text())
    at = now()
    job["id"] = new_id(job["title"], at)
    job["supersedes"] = args.id
    job["submitted"] = {**job.get("submitted", {}), "at": iso(at)}
    job.pop("revision", None)
    if args.revision:
        job["revision"] = args.revision
    resources = job.setdefault("resources", {})
    for flag, key in [("cpus", "cpus"), ("memory", "memory"), ("duration", "duration"), ("memory_limit", "memoryLimit"),
                      ("timeout", "timeout"), ("estimate_notes", "notes")]:
        value = getattr(args, flag)
        if value is not None:
            resources[key] = float(value) if key == "cpus" else value
    problems = validate(job, "job.schema.json")
    if problems:
        sys.exit("not a valid job:\n  " + "\n  ".join(problems))
    path = layout.new_job(ROOT, job["id"])
    if "$schema" in job:
        job["$schema"] = schema_ref(path, "job.schema.json")
    write_json(path, job)
    print(f"wrote {path.relative_to(ROOT)}, superseding {args.id}. Commit it to queue it.")
    return 0


def cmd_validate(args):
    bad = 0
    for problem in layout.conflicts(ROOT):  # one id recorded twice, differently
        print(problem)
        bad += 1
    for path in layout.jobs(ROOT).values():
        job = json.loads(path.read_text())
        problems = validate(job, "job.schema.json")
        if job.get("id") != path.stem:
            problems.append(f"id {job.get('id')!r} does not match the file name")
        for p in problems:
            print(f"{path.relative_to(ROOT)}: {p}")
        bad += bool(problems)
    for path in (folder / "result.json" for folder in layout.results(ROOT).values()):
        problems = validate(json.loads(path.read_text()), "result.schema.json")
        for p in problems:
            print(f"{path.relative_to(ROOT)}: {p}")
        bad += bool(problems)
    print(f"{bad} file(s) with problems")
    return 1 if bad else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pipeline.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def budget(p):
        p.add_argument("--workers", type=int, help="jobs at once")
        p.add_argument("--cpus", help="CPUs shared out among running jobs")
        p.add_argument("--memory", help="memory shared out among running jobs, such as 5G")
        p.add_argument("--job-memory-max", help="the most any one job may have, such as 4G")
        p.add_argument("--memory-floor", help="what the machine keeps free: no job starts that would go under it, and "
                       "under it the newest job is stopped, such as 8G (0: none)")
        p.add_argument("--isolation", choices=["auto", "systemd", "none"])
        p.add_argument("--max-timeout", help="no job runs longer, such as 6h")
        p.add_argument("--state-dir", help="where runs, logs and work directories live (default verification/.state)")

    p = sub.add_parser("run", help="run pending jobs")
    budget(p)
    p.add_argument("--rev", help="the commit whose jobs to run (default: jj's @- here and in every other workspace, else HEAD)")
    p.add_argument("--watch", action="store_true", help="keep going when the queue is empty, for jobs committed later")
    p.add_argument("--min-priority", type=int, help="only jobs at this priority or above (verification/priorities.json, else the job's own)")
    p.add_argument("ids", nargs="*", help="only these jobs")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("prioritize", help="move jobs up or down the queue (verification/priorities.json); no ids lists it")
    p.add_argument("ids", nargs="*")
    p.add_argument("--priority", type=int, help="higher runs first; the default for every job is 0")
    p.add_argument("--reason", help="why: what waits on these jobs, or why they can wait")
    p.add_argument("--clear", action="store_true", help="drop these jobs' entries, back to their own priority")
    p.set_defaults(func=cmd_prioritize)

    p = sub.add_parser("nudge", help="say that the queue changed: a runner, or a loop waiting for work, looks at once")
    p.add_argument("--state-dir")
    p.add_argument("--where", action="store_true", help="print the file a nudge touches, and touch nothing")
    p.set_defaults(func=cmd_nudge)

    p = sub.add_parser("wait", help="block until a job has finished and waits to be collected, or no runner is at work")
    p.add_argument("--state-dir")
    p.add_argument("--timeout", type=float, default=540, help="seconds (default 540); exit 3 when nothing happened")
    p.set_defaults(func=cmd_wait)

    p = sub.add_parser("status", help="the queue")
    budget(p)
    p.add_argument("--rev")
    p.add_argument("--all", action="store_true", help="list collected jobs too")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("collect", help="move finished results into verification/results and apply their outputs")
    p.add_argument("--state-dir")
    p.add_argument("--apply-failed", action="store_true", help="apply the outputs of jobs that did not pass too")
    p.add_argument("ids", nargs="*")
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("prune", help="remove failed jobs' kept work directories that are collected and whose originals "
                                     "are remote_verified (collect does this too)")
    p.add_argument("--state-dir")
    p.add_argument("--dry-run", action="store_true", help="name them and their sizes, remove nothing")
    p.add_argument("--why", action="store_true", help="say why each work directory that stays does")
    p.add_argument("--json", action="store_true", help="what was removed and what stays with its reason, as JSON")
    p.add_argument("--unarchived", action="store_true", help="also remove collected attempts' work directories that "
                   "ran while nothing captured originals (they are in no archive)")
    p.set_defaults(func=cmd_prune)

    p = sub.add_parser("recover", help="seal into the archive what an attempt left that nothing sealed: a killed runner's "
                                       "attempt, a capture that failed, a result set aside (the runner does this when it starts)")
    p.add_argument("--state-dir")
    p.add_argument("--dry-run", action="store_true", help="name them, seal nothing")
    p.add_argument("--kept-outputs", action="store_true", help="also seal the outputs receipts say were kept and that this "
                   "working copy holds while no commit does (VF-080)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_recover)

    p = sub.add_parser("commit-paths", help="the paths a commit of collected results holds, for sync.py commit --only")
    p.set_defaults(func=cmd_commit_paths)

    p = sub.add_parser("report", help="a digest of collected results")
    p.add_argument("--format", choices=["md", "json"], default="md")
    p.add_argument("--status", action="append", help="only results with this status (repeatable)")
    p.add_argument("--capability", action="append", help="only jobs linked to this capability (repeatable)")
    p.add_argument("--since", help="only results finished at or after this ISO time")
    p.add_argument("--tail", type=int, default=20, help="log lines to show for a step that did not pass")
    p.add_argument("ids", nargs="*")
    p.set_defaults(func=cmd_report)

    def resources(p):
        p.add_argument("--cpus", help="CPUs the job needs (default 1)")
        p.add_argument("--memory", help="rough peak memory, such as 2G (default 2G)")
        p.add_argument("--duration", help="rough wall time, such as 10m (default 10m)")
        p.add_argument("--memory-limit", help="hard cap (default 1.5x the estimate, within the runner's per-job maximum)")
        p.add_argument("--timeout", help="hard stop (default 4x the duration, at least 5m)")
        p.add_argument("--estimate-notes", help="what the estimate rests on")

    p = sub.add_parser("submit", help="write a job file")
    p.add_argument("--title", help="one line: what is verified")
    p.add_argument("--description", help="what the job checks, why, and what the change was")
    p.add_argument("--kind", choices=["example", "library", "model", "real-world", "other"])
    p.add_argument("--capability", action="append", help="a capability the job exercises: an approach id (B8 B9 B10 B11 D1) or "
                   "a jvmcontract command (jvmcontract:prove, jvmcontract:tlc, ...); repeatable")
    p.add_argument("--link", action="append", help="KIND:VALUE, such as example:104, path:lib/src/tla.rs, commit:abc123; repeatable")
    p.add_argument("--expected", help="what a pass looks like, in words")
    p.add_argument("--example", action="append", help="run this demo example through build.py (fills in step, outputs, requirements)")
    p.add_argument("--task", help="with one --example of a real-world example with a target sidecar: the task to run "
                   "(build.py ID --task T, from the same plan build.py --plan ID --task T prints)")
    p.add_argument("--step", nargs=2, action="append", metavar=("NAME", "COMMAND"), help="a bash step; repeatable")
    p.add_argument("--run", action="append", metavar="COMMAND", help="a bash step named after its command; repeatable")
    p.add_argument("--cwd", help="the steps' directory, relative to the repo root")
    p.add_argument("--expect-exit", type=int, help="the exit code that counts as a pass (default 0)")
    p.add_argument("--output", action="append", help="a file or directory the job writes that should come back; repeatable")
    p.add_argument("--requires", action="append", help="java javac jbmc tlc cargo jvmcontract gradle maven, or any command; repeatable")
    p.add_argument("--priority", type=int, help="higher runs first (default 0)")
    p.add_argument("--revision", help="run at this commit instead of the one that commits the job file")
    p.add_argument("--session", help="the submitting session's id (default: the Claude Code session running this, if any)")
    p.add_argument("--by", help="who submitted it: an agent or a person")
    p.add_argument("--stop-on-failure", choices=["yes", "no"], help="skip later steps after a failure (default yes)")
    p.add_argument("--from-file", help="start from this JSON file")
    p.add_argument("--dry-run", action="store_true", help="print the job instead of writing it")
    p.add_argument("--force", action="store_true")
    resources(p)
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("resubmit", help="a new job from an old one, with other resources")
    p.add_argument("id")
    p.add_argument("--revision")
    resources(p)
    p.set_defaults(func=cmd_resubmit)

    p = sub.add_parser("validate", help="check job and result files")
    p.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

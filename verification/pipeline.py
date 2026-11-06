#!/usr/bin/env python3
"""The verification pipeline: committed verification jobs, run asynchronously under resource limits.

A development agent that makes a change needing a proof or a model check does not run it. It describes the work as
a job (verification/jobs/ID.json, schema in verification/schema/job.schema.json) and commits the job with the change,
marked "verification pending". A runner picks committed jobs up as resources permit, runs each one in a clean export
of the commit that holds it, and records what happened in verification/results/ID/. See verification/README.md.

Commands:
  submit    write a job file, from flags or a JSON file (--example ID fills in a demo example's job)
  status    the queue: pending (and whether they fit here), running, finished but not collected, collected
  run       run pending jobs under the configured budget; --watch keeps polling for new ones
  collect   move finished results into verification/results/, apply their outputs to the working copy
  report    a digest of collected results for a batch read, as Markdown or JSON
  resubmit  a new job from an old one, with other resources (after a timeout or out-of-memory, say)
  validate  check every job and result file against its schema

Configuration: verification/pipeline.toml, then verification/pipeline.local.toml (not committed), then the file
named by $VERIFY_CONFIG, then command-line flags.
"""

import argparse
import datetime as dt
import difflib
import fcntl
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
import zipfile
from pathlib import Path

ROOT = Path(os.environ.get("VERIFY_REPO") or Path(__file__).resolve().parents[1])
HERE = "verification"
JOBS = f"{HERE}/jobs"
RESULTS = f"{HERE}/results"
PRIORITIES = f"{HERE}/priorities.json"
SCHEMAS = ROOT / HERE / "schema"
JOB_SCHEMA = "verification-job/v1"
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

# Lines worth lifting out of a log, so a reader need not open it: (tool, kind, pattern).
SIGNALS = [
    ("jbmc", "proved", r"^VERIFICATION SUCCESSFUL\s*$"),
    ("jbmc", "refuted", r"^VERIFICATION FAILED\s*$"),
    ("jbmc", "no-verdict", r"^VERIFICATION ERROR\s*$"),
    ("tlc", "no-error", r"Model checking completed\. No error has been found\."),
    ("tlc", "invariant-violated", r"Error: Invariant (\S+) is violated"),
    ("tlc", "property-violated", r"Error: (?:Temporal properties were violated|Action property (\S+) is violated)"),
    ("tlc", "deadlock", r"Error: Deadlock reached"),
    ("tlc", "states", r"([\d,]+) distinct states found"),
    ("jvmcontract", "holds", r"^✓ (.*)"),
    ("jvmcontract", "fails", r"^✗ (.*)"),
    ("jvmcontract", "unverifiable", r"^⚠ (.*)"),
    ("example", "as-expected", r"^(\d{3})-\S+: (verified|violation|unverifiable) \(as expected\)"),
    ("example", "unexpected", r"^(\d{3})-\S+: (\w+) \((EXPECTED[^)]*)\)"),
    ("example", "differ", r"^Verdicts differ from expectations: (.*)"),
    ("example", "not-executed", r"^(\d{3})-\S+: not-executed \((.*)\)$"),
    ("cargo", "tests", r"^test result: (ok|FAILED)\. (\d+) passed; (\d+) failed"),
    ("memory", "out-of-memory", r"java\.lang\.OutOfMemoryError|ran out of memory|std::bad_alloc|Cannot allocate memory"),
]
SIGNALS = [(tool, kind, re.compile(p)) for tool, kind, p in SIGNALS]
MAX_SIGNALS = 100


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


def load_config(args=None):
    config = DEFAULTS
    files = [ROOT / HERE / "pipeline.toml", ROOT / HERE / "pipeline.local.toml"]
    if os.environ.get("VERIFY_CONFIG"):
        files.append(Path(os.environ["VERIFY_CONFIG"]))
    for f in files:
        if f.exists():
            config = merge(config, tomllib.loads(f.read_text()))
    runner = dict(config["runner"])
    for flag in ["workers", "cpus", "memory", "job_memory_max", "isolation", "max_timeout", "state_dir"]:
        value = getattr(args, flag, None) if args else None
        if value is not None:
            runner[flag] = value
    runner["memory"] = parse_bytes(runner["memory"])
    runner["job_memory_max"] = parse_bytes(runner["job_memory_max"])
    runner["build_memory"] = parse_bytes(runner["build_memory"])
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
    return {"runner": runner, "defaults": config["defaults"]}


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


def resolve(rev):
    return git("rev-parse", "--verify", f"{rev}^{{commit}}").stdout.strip()


def show(commit, path):
    """The file's bytes at the commit, or None if it is not there."""
    proc = git("show", f"{commit}:{path}", check=False, binary=True)
    return proc.stdout if proc.returncode == 0 else None


def committed_jobs(rev):
    """Every job file in the commit's tree, as (job, path, source commit). The source commit is the job's own
    revision if it names one, else the last commit that touched the file: the code the job was written for."""
    listing = git("ls-tree", "-r", "--name-only", rev, "--", JOBS + "/").stdout.split()
    jobs = []
    for path in sorted(p for p in listing if p.endswith(".json")):
        try:
            job = json.loads(show(rev, path))
        except (TypeError, ValueError) as e:
            print(f"warn  {path}: not JSON at {rev[:12]}: {e}", file=sys.stderr)
            continue
        source = job.get("revision") or git("log", "-1", "--format=%H", rev, "--", path).stdout.strip()
        jobs.append((job, path, resolve(source)))
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
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) * 1024
    return None


# The environment a job ran in


_ENVIRONMENT = None


def first_line(cmd):
    try:
        proc = run_quiet(cmd, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (proc.stdout or proc.stderr).strip()
    return text.splitlines()[0] if proc.returncode == 0 and text else None


def tla2tools():
    jar = Path(os.environ.get("TLA2TOOLS_JAR") or Path.home() / "tools/tla2tools.jar")
    return jar if jar.exists() else None


def tlc_version(jar):
    try:
        with zipfile.ZipFile(jar) as z:
            manifest = z.read("META-INF/MANIFEST.MF").decode(errors="replace")
        m = re.search(r"^Implementation-Version:\s*(.+)$", manifest, re.M)
        return m[1].strip() if m else "unknown"
    except (OSError, KeyError, zipfile.BadZipFile):
        return None


def environment(host):
    """The machine a job ran on, recorded under `host`: the runner's machine_name, else the hostname."""
    global _ENVIRONMENT
    if _ENVIRONMENT is None:
        cpu = next((l.split(":", 1)[1].strip() for l in Path("/proc/cpuinfo").read_text().splitlines()
                    if l.lower().startswith(("model name", "cpu part"))), None) if Path("/proc/cpuinfo").exists() else None
        total = next((int(l.split()[1]) * 1024 for l in Path("/proc/meminfo").read_text().splitlines()
                      if l.startswith("MemTotal:")), None)
        jar = tla2tools()
        cargo = shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo")
        _ENVIRONMENT = {
            "host": host,
            "os": platform.platform(),
            "machine": platform.machine(),
            "cpuModel": cpu,
            "cpuCount": os.cpu_count(),
            "memoryTotalBytes": total,
            "python": platform.python_version(),
            "tools": {
                "java": first_line(["java", "-version"]) or first_line(["bash", "-c", "java -version 2>&1"]),
                "javac": first_line(["javac", "-version"]),
                "jbmc": first_line(["jbmc", "--version"]),
                "tlc": tlc_version(jar) if jar else None,
                "tla2toolsJar": str(jar) if jar else None,
                "cargo": first_line([cargo, "--version"]),
                "rustc": first_line(["rustc", "--version"]) or first_line([str(Path(cargo).parent / "rustc"), "--version"]),
                "systemd": first_line(["systemd-run", "--version"]),
                # GNU or uutils (Ubuntu 26.04's default): jobs see the difference, as in timeout's exit after -s KILL.
                "coreutils": first_line(["timeout", "--version"]),
            },
        }
    return _ENVIRONMENT


def missing_tools(requires):
    checks = {
        "java": lambda: shutil.which("java") or os.environ.get("JAVA_HOME"),
        "javac": lambda: shutil.which("javac") or os.environ.get("JAVA_HOME"),
        "jbmc": lambda: shutil.which("jbmc"),
        "tlc": tla2tools,
        "cargo": lambda: shutil.which("cargo") or (Path.home() / ".cargo/bin/cargo").exists(),
        "jvmcontract": lambda: shutil.which("cargo") or (Path.home() / ".cargo/bin/cargo").exists(),
        "gradle": lambda: shutil.which("java") or os.environ.get("JAVA_HOME"),
    }
    return [r for r in requires if not (checks.get(r) or (lambda r=r: shutil.which(r)))()]


# Logs


def scan_signals(log_path):
    signals, counts, lines = [], {}, 0
    with open(log_path, errors="replace") as f:
        for lines, line in enumerate(f, 1):
            line = line.rstrip("\n")
            for tool, kind, pattern in SIGNALS:
                m = pattern.search(line)
                if m:
                    key = f"{tool}:{kind}"
                    counts[key] = counts.get(key, 0) + 1
                    if len(signals) < MAX_SIGNALS:
                        signals.append({"tool": tool, "kind": kind, "line": lines, "text": line[:300],
                                        "groups": [g for g in m.groups() if g is not None]})
    return signals, counts, lines


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
# counters before the scope goes away: memory.peak is lost once the last process in it exits.
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

    def __init__(self, unit, isolation, cpus, memory_limit, stall_window=600, ceiling=float("inf")):
        self.unit, self.isolation, self.cpus, self.memory_limit = unit, isolation, cpus, memory_limit
        self.stall_window, self.ceiling = stall_window, ceiling
        self.pid = None
        self.cancelled = False

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
                   VERIFY_STEP_STATS=str(stats_path) if self.isolation == "systemd" else "")
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
                if stop:
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
            "memoryHighEvents": stats.get("memory.events.max", 0),
        }


# Running a job


class Runner:
    def __init__(self, config, isolation):
        self.config, self.runner = config, config["runner"]
        self.isolation = isolation
        self.state = self.runner["state_dir"]
        for d in ["claims", "results", "runs", "work", "tools"]:
            (self.state / d).mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.running = {}      # id -> {"plan", "thread", "steps": [Step]}
        self.finished = []     # ids finished in this run
        self.stopping = False
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
        tree = ROOT / RESULTS
        if tree.exists():
            done |= {p.name for p in tree.iterdir() if (p / "result.json").exists()}
        return done

    def pending(self, rev, wanted=None, min_priority=None):
        done, claimed = self.done_ids(), {p.name for p in (self.state / "claims").iterdir()}
        priorities = load_priorities(rev)
        out = []
        for job, path, source in committed_jobs(rev):
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
        memory = job_plan["memoryLimit"]
        if "jvmcontract" in job.get("requires", []) and not self.jvmcontract_cached(source):
            memory = max(memory, self.runner["build_memory"])
        return memory

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
        if available is not None and available < memory:
            return f"only {fmt_bytes(available)} available on the machine"
        return None

    def start(self, job, path, source, job_plan, memory):
        job_id = job["id"]
        if not self.claim(job_id):
            return False
        entry = {"plan": job_plan, "cpus": job_plan["cpus"], "memory": memory, "steps": [], "job": job}
        self.running[job_id] = entry
        thread = threading.Thread(target=self.execute, args=(job, path, source, job_plan, entry), daemon=True)
        entry["thread"] = thread
        thread.start()
        return True

    # jvmcontract, built once per tree of lib/
    def lib_tree(self, source):
        proc = git("rev-parse", f"{source}:lib", check=False)
        return proc.stdout.strip() if proc.returncode == 0 else None

    def jvmcontract_cached(self, source):
        tree = self.lib_tree(source)
        return bool(tree) and (self.state / "tools" / "jvmcontract" / tree / "jvmcontract").exists()

    def execute(self, job, path, source, job_plan, entry):
        job_id = job["id"]
        started = now()
        run_dir = self.state / "runs" / job_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        (run_dir / "logs").mkdir(parents=True)
        work = self.state / "work" / job_id
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
            "environment": environment(self.runner["machine_name"]),
            "steps": [],
            "outputs": [],
            "collected": None,
        }
        try:
            self.prepare(job, source, work, result, entry)
            if result["status"] is None:
                self.run_steps(job, work, run_dir, result, entry)
                self.collect_outputs(job, work, source, run_dir, result)
        except Exception as e:  # anything the pipeline itself got wrong is an error, never a verdict
            result["status"] = "error"
            result["attention"].append(f"the pipeline failed: {type(e).__name__}: {e}")
        finished = now()
        result["finishedAt"] = iso(finished)
        result["wallSeconds"] = round((finished - started).total_seconds(), 1)
        self.finish(job, result, job_plan)
        # The run directory keeps the whole logs on this machine; the result gets them whole if short, else cut.
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
        write_json(out / "result.json", result)
        keep = self.runner["keep_workdirs"]
        if keep == "never" or (keep == "failed" and result["status"] == "passed"):
            shutil.rmtree(work, ignore_errors=True)
        else:
            result["workdir"] = str(work)
            write_json(out / "result.json", result)
        with self.lock:
            self.running.pop(job_id, None)
            self.finished.append(job_id)
        self.release(job_id)
        print(f"{job_id}: {result['summary']}", flush=True)

    def prepare(self, job, source, work, result, entry):
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        archive = subprocess.run(["git", "archive", "--format=tar", source], cwd=ROOT, capture_output=True)
        if archive.returncode != 0:
            raise RuntimeError(f"git archive {source}: {archive.stderr.decode().strip()}")
        subprocess.run(["tar", "-x", "-C", str(work)], input=archive.stdout, check=True)
        for link in self.runner["link"]:
            src, dst = ROOT / link, work / link
            if src.exists() and not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.symlink_to(src)
        missing = missing_tools(job.get("requires", []))
        if missing:
            result["status"] = "error"
            result["attention"].append("missing on this machine: " + ", ".join(missing))
            return
        if "jvmcontract" in job.get("requires", []):
            self.build_jvmcontract(source, work, result, entry)

    def build_jvmcontract(self, source, work, result, entry):
        tree = self.lib_tree(source)
        if not tree:
            raise RuntimeError(f"no lib/ at {source[:12]}, and the job requires jvmcontract")
        exe = self.state / "tools" / "jvmcontract" / tree / "jvmcontract"
        with open(self.state / "tools" / "jvmcontract.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if exe.exists():
                result["jvmcontract"] = {"libTree": tree, "path": str(exe), "built": False}
                return
            # The target directory is shared between jobs, and cargo rebuilds a crate only when a source is newer than
            # its last build. `git archive` dates every file at its commit, which is older than a binary built since
            # from any other commit, so without this every job ran whichever jvmcontract was built last (Nov 4 2026:
            # 13 lib/ trees, one binary). Dating lib/ now makes cargo rebuild it; the dependencies are not affected.
            started = time.time()
            for path in (work / "lib").rglob("*"):
                os.utime(path, (started, started), follow_symlinks=False)
            cargo = shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo")
            run = f"{cargo} build --release --manifest-path lib/Cargo.toml"
            env = dict(os.environ, CARGO_TARGET_DIR=str(self.state / "cargo-target"))
            log = self.state / "runs" / result["id"] / "logs" / "0-build-jvmcontract.log"
            step = Step(f"vjob-{result['id'][:40]}-build", self.isolation, max(entry["cpus"], 1),
                        max(entry["memory"], self.runner["build_memory"]), self.runner["stall_window"],
                        self.runner["max_timeout"])
            entry["steps"].append(step)
            outcome = step.run(run, work, env, log, log.with_suffix(".stats"), self.wrapper, 3600)
            record = self.step_record({"name": "build jvmcontract", "run": run, "cwd": "."}, 0, outcome, log)
            record["status"] = "passed" if outcome["exitCode"] == 0 else ("out-of-memory" if outcome["oomKills"] else "failed")
            result["steps"].append(record)
            built = self.state / "cargo-target" / "release" / "jvmcontract"
            if outcome["exitCode"] != 0 or not built.exists():
                result["status"] = "error"
                result["attention"].append("jvmcontract did not build at this commit; see the build step's log")
                return
            if built.stat().st_mtime < started:
                result["status"] = "error"
                result["attention"].append("cargo reused a jvmcontract built before this job instead of building lib/ "
                                           "at this commit; nothing ran on it")
                return
            exe.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(built, exe)
            result["jvmcontract"] = {"libTree": tree, "path": str(exe), "built": True}

    def step_env(self, job, result, work):
        limit_mb = result["limits"]["memoryLimitBytes"] // (1024 * 1024)
        env = dict(os.environ)
        # Inside the cap, JBMC should stop by itself with "out of memory" rather than be killed, and TLC's heap
        # should fit: Java's default heap is a quarter of the machine, not of the cap.
        env["JVMCONTRACT_JBMC_MEMORY_MB"] = str(max(256, limit_mb - 512))
        env["JVMCONTRACT_JAVA_OPTS"] = f"-Xmx{max(256, int(limit_mb * 0.6))}m"
        if result.get("jvmcontract"):
            exe = Path(result["jvmcontract"]["path"])
            env["JVMCONTRACT"] = str(exe)
            env["PATH"] = f"{exe.parent}:{env.get('PATH', '')}"
        # build.py keeps each TLC configuration's result under the fingerprint of its inputs, so a job run again after
        # a timeout or a failure picks up the configurations already done; a result is reused only on identical inputs.
        env.setdefault("BUILD_CHECKPOINTS", str(self.state / "checkpoints"))
        env.update({"VERIFY_JOB_ID": job["id"], "VERIFY_CPUS": f"{result['limits']['cpus']:g}",
                    "VERIFY_MEMORY_LIMIT_MB": str(limit_mb), "VERIFY_WORKDIR": str(work),
                    "VERIFY_SOURCE_COMMIT": result["sourceCommit"]})
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
            if (failed and job.get("stopOnFailure", True)) or self.stopping:
                result["steps"].append({"index": i, "name": name, "run": spec["run"], "cwd": spec.get("cwd", "."),
                                        "status": "skipped", "why": "an earlier step failed" if failed else "the runner was stopped"})
                continue
            timeout = min(parse_seconds(spec["timeout"]) if spec.get("timeout") else result["limits"]["timeoutSeconds"],
                          result["limits"]["timeoutSeconds"])
            step = Step(f"vjob-{job['id'][:40]}-{i}", self.isolation, result["limits"]["cpus"],
                        result["limits"]["memoryLimitBytes"], self.runner["stall_window"], self.runner["max_timeout"])
            entry["steps"].append(step)
            outcome = step.run(spec["run"], work / spec.get("cwd", "."), env, log, log.with_suffix(".stats"),
                               self.wrapper, timeout)
            record = self.step_record(spec, i, outcome, log)
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

    def step_record(self, spec, index, outcome, log):
        signals, counts, lines = scan_signals(log)
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
            elif s["status"] == "out-of-memory":
                attention.append(f"{where} was killed at its {fmt_bytes(result['limits']['memoryLimitBytes'])} memory limit")
            counts = s.get("signalCounts", {})
            if (s.get("cpuThrottledSeconds") or 0) > 0.5 * max(s.get("wallSeconds") or 0, 1):
                attention.append(f"{where} was held back {fmt_seconds(s['cpuThrottledSeconds'])} by its {result['limits']['cpus']:g}-CPU quota "
                                 f"in {fmt_seconds(s['wallSeconds'])}: it would run faster with more CPUs (a JVM needs 2)")
            if s["status"] == "passed" and s.get("oomKills"):
                attention.append(f"{where} passed, but the kernel killed {s['oomKills']} process(es) in it at the memory limit")
            if s["status"] == "passed":
                for key, what in [("jbmc:no-verdict", "JBMC gave no verdict"), ("memory:out-of-memory", "the log mentions running out of memory"),
                                  ("jvmcontract:unverifiable", "jvmcontract reports something unverifiable"),
                                  ("example:unexpected", "an example's verdict differs from its expectation")]:
                    if counts.get(key):
                        attention.append(f"{where} passed, but {what} ({counts[key]}×)")
        usage = result["usage"]
        if usage["memoryOfEstimate"] and usage["memoryOfEstimate"] > 1.5:
            attention.append(f"peak memory {fmt_bytes(peak)} is {usage['memoryOfEstimate']}× the estimate")
        if usage["durationOfEstimate"] and usage["durationOfEstimate"] > 2:
            attention.append(f"took {fmt_seconds(wall)}, {usage['durationOfEstimate']}× the estimate")
        result["attention"] = list(dict.fromkeys(attention))
        verdicts = []
        for s in steps:
            for key, n in sorted((s.get("signalCounts") or {}).items()):
                if key not in ("tlc:states",):
                    verdicts.append(f"{key}×{n}")
            states = [g["groups"][0] for g in s.get("signals", []) if g["tool"] == "tlc" and g["kind"] == "states" and g["groups"]]
            if states:
                verdicts.append(f"tlc states {', '.join(states[:4])}{'…' if len(states) > 4 else ''}")
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


def cmd_run(args):
    config = load_config(args)
    isolation = isolation_of(config["runner"])
    runner = Runner(config, isolation)
    lock = open(runner.state / "runner.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit(f"another runner is using {runner.state}")
    runner.clear_stale_claims()

    def interrupted(signum, _frame):
        print(f"stopping on {signal.Signals(signum).name}: running steps are cancelled, their jobs recorded", flush=True)
        runner.stop_all()
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)

    r = config["runner"]
    print(f"runner: {r['workers']} worker(s), {r['cpus']:g} CPUs, {fmt_bytes(r['memory'])} "
          f"(at most {fmt_bytes(r['job_memory_max'])} a job), isolation {isolation}, state {runner.state}", flush=True)
    wanted = set(args.ids) if args.ids else None
    told = set()
    last_scan, queue, blocked = None, [], None
    while not runner.stopping:
        if last_scan is None or (args.watch and time.monotonic() - last_scan > r["poll_seconds"]):
            rev = resolve(args.rev) if args.rev else default_rev()
            with runner.lock:
                queue = runner.pending(rev, wanted, args.min_priority)
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
                    print(f"{job['id']}: not started: {why}; rerun when there is room, or use --watch to wait", flush=True)
                    queue.clear()
                    break
                if why and why != blocked and not runner.running:
                    print(f"{job['id']}: waiting: {why}", flush=True)
                blocked = why
                if why is None and runner.start(job, path, source, job_plan, memory):
                    print(f"{job['id']}: started at {source[:12]} ({job_plan['cpus']:g} CPU, limit {fmt_bytes(job_plan['memoryLimit'])}, "
                          f"timeout {fmt_seconds(job_plan['timeout'])})", flush=True)
                    queue.remove((job, path, source))
                elif why:
                    break  # in priority order: a later job does not overtake one that is waiting for room
        if not runner.running and not queue and not args.watch:
            break
        time.sleep(1)
    for entry in list(runner.running.values()):
        entry["thread"].join()
    finished = runner.finished
    print(f"finished {len(finished)} job(s)" + (f": {', '.join(finished)}" if finished else "") +
          ("; collect them with: python3 verification/pipeline.py collect" if finished else ""))
    return 0


def cmd_status(args):
    config = load_config(args)
    state = config["runner"]["state_dir"]
    rev = resolve(args.rev) if args.rev else default_rev()
    claims = {p.name: json.loads(p.read_text() or "{}") for p in (state / "claims").iterdir()} if (state / "claims").exists() else {}
    finished = sorted(p.name for p in (state / "results").iterdir() if (p / "result.json").exists()
                      and json.loads((p / "result.json").read_text()).get("status") != "cancelled") if (state / "results").exists() else []
    collected = sorted(p.name for p in (ROOT / RESULTS).iterdir() if (p / "result.json").exists()) if (ROOT / RESULTS).exists() else []
    rows = {"pending": [], "running": [], "finished, not collected": [], "collected": []}
    seen = set()
    priorities = load_priorities(rev)
    for job, path, source in sorted(committed_jobs(rev), key=queue_order(priorities)):
        job_id = job.get("id")
        seen.add(job_id)
        p = plan(job, config)
        line = f"{job_id}  {job.get('title', '')}"
        if job_id in collected:
            res = json.loads((ROOT / RESULTS / job_id / "result.json").read_text())
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
    uncommitted = sorted(p.stem for p in (ROOT / JOBS).glob("*.json")) if (ROOT / JOBS).exists() else []
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
    known = {j.get("id") for j, _, _ in committed_jobs(default_rev())} | {p.stem for p in (ROOT / JOBS).glob("*.json")}
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
    applied_any, lines = False, []
    for job_id in ids:
        src = state / job_id
        result = json.loads((src / "result.json").read_text())
        dest = ROOT / RESULTS / job_id
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        for name in ["logs", "changes.diff"]:
            if (src / name).is_dir():
                shutil.copytree(src / name, dest / name)
            elif (src / name).exists():
                shutil.copy2(src / name, dest / name)
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
                               "why": None if apply else f"not applied: the job {result['status']}"}
        if conflicts:
            result["attention"].append(f"{len(conflicts)} output(s) changed in the working copy since the job's commit and were "
                                       f"not applied (kept under outputs/): rerun the job on the newer commit")
        write_json(dest / "result.json", result)
        shutil.rmtree(src)
        applied_any = applied_any or bool(applied)
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
    print("\nFor the commit message (python3 llm-dlc/tools/sync.py commit -m ... -m ...):")
    print(f"  Record verification results for {len(ids)} job(s)")
    print("  " + " ".join(lines))
    return 0


def write_index():
    tree = ROOT / RESULTS
    entries = []
    for p in sorted(tree.iterdir()) if tree.exists() else []:
        f = p / "result.json"
        if not f.exists():
            continue
        r = json.loads(f.read_text())
        spec = r["job"]["spec"]
        entries.append({"id": r["id"], "title": r.get("title"), "status": r["status"], "summary": r["summary"],
                        "attention": r["attention"], "capabilities": spec.get("capabilities", []),
                        "links": spec.get("links", {}), "sourceCommit": r["sourceCommit"], "finishedAt": r["finishedAt"],
                        "wallSeconds": (r.get("usage") or {}).get("wallSeconds"),
                        "peakMemoryBytes": (r.get("usage") or {}).get("peakMemoryBytes"),
                        "estimate": r.get("estimate"), "host": r["runner"]["host"], "result": f"{p.name}/result.json"})
    entries.sort(key=lambda e: e["finishedAt"] or "", reverse=True)
    if entries or tree.exists():
        write_json(tree / "index.json", {"schema": "verification-results-index/v1", "results": entries})


def load_results(args):
    tree = ROOT / RESULTS
    results = []
    for p in sorted(tree.iterdir()) if tree.exists() else []:
        if (p / "result.json").exists():
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
                       "log": f"{RESULTS}/{r['id']}/{s['log']['path']}" if s.get("log") else None} for s in r["steps"]],
            "outputs": r["outputs"], "collected": r.get("collected"),
            "result": f"{RESULTS}/{r['id']}/result.json"} for r in results],
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
                    print(f"- step {s['index']} `{s['name']}` {s['status']}; last lines of `{RESULTS}/{r['id']}/{s['log']['path']}`:")
                    print("\n```\n" + "\n".join((s.get("tail") or [])[-args.tail:]) + "\n```")
            print(f"- result: `{RESULTS}/{r['id']}/result.json`\n")
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


def example_plan(example):
    """build.py's plan() of an example (examples/tools/build.py, imported without running anything): what the run
    builds and which tools it calls. The pipeline asks build.py rather than guessing from the approach, so a job
    requires what its run uses: no JBMC for a proof by the tool's own checker, jvmcontract (and its build memory) for
    a B12 run on the Gradle app."""
    path = ROOT / "examples/tools/build.py"
    if not path.exists():
        sys.exit(f"example {example['id']}: {path.relative_to(ROOT)} is missing, and the plan of a run comes from it")
    spec = importlib.util.spec_from_file_location("examples_build", path)
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    return build.plan(example)


def example_job_parts(example_id):
    """The step, outputs, requirements and capability of a job that runs one demo example through build.py. The
    requirements are the tools build.py's plan says the run calls, its optional ones included: a job that may need a
    tool runs where the tool is."""
    folders = sorted((ROOT / "examples").glob(f"{example_id}-*"))
    if len(folders) != 1:
        sys.exit(f"example {example_id}: expected one folder examples/{example_id}-*, found {len(folders)}")
    folder = folders[0]
    example = json.loads((folder / "example.json").read_text())
    if example.get("origin") != "constructed":
        sys.exit(f"example {example_id} is {example.get('origin')}: build.py does not run it (its report is its README.md); "
                 "describe its proof with --step and --kind real-world instead")
    plan = example_plan(example)
    if not plan["executable"]:
        sys.exit(f"example {example_id}: build.py does not run it ({plan['notExecuted']})")
    approach = plan["approach"]
    requires = list(dict.fromkeys(plan["tools"]["required"] + plan["tools"]["optional"]))
    rel = folder.relative_to(ROOT).as_posix()
    return {"step": {"name": f"example {example_id} ({approach})", "run": f"python3 examples/tools/build.py {example_id}",
                     "cwd": "."},
            "output": rel, "requires": requires, "capability": approach,
            "expected": f"example {example_id} gives its expected verdict, {example['expected']['verdict']}"
                        f"{' (vacuously)' if example['expected'].get('vacuous') else ''}: build.py prints 'as expected' and exits 0"}


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
    if args.session:
        job["submitted"]["session"] = args.session
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
    for example_id in args.example or []:
        parts = example_job_parts(example_id)
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
    path = ROOT / JOBS / f"{job['id']}.json"
    if path.exists() and not args.force:
        sys.exit(f"{path.relative_to(ROOT)} exists")
    if args.dry_run:
        print(json.dumps(job, indent=2, ensure_ascii=False))
        return 0
    write_json(path, job)
    p = plan(job, load_config())
    print(f"wrote {path.relative_to(ROOT)}: {len(job['steps'])} step(s), {p['cpus']:g} CPU, {fmt_bytes(p['memoryEstimate'])}, "
          f"~{fmt_seconds(p['durationEstimate'])} (limit {fmt_bytes(p['memoryLimit'])}, timeout {fmt_seconds(p['timeout'])})")
    if p["cannotRun"]:
        print("note: the local runner cannot run it: " + "; ".join(p["cannotRun"]) + ". It waits for a bigger runner.")
    print("Commit it with the change, marked verification pending (verification/README.md).")
    return 0


def cmd_resubmit(args):
    old_path = ROOT / JOBS / f"{args.id}.json"
    if not old_path.exists():
        sys.exit(f"{old_path.relative_to(ROOT)} not found")
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
    path = ROOT / JOBS / f"{job['id']}.json"
    write_json(path, job)
    print(f"wrote {path.relative_to(ROOT)}, superseding {args.id}. Commit it to queue it.")
    return 0


def cmd_validate(args):
    bad = 0
    for path in sorted((ROOT / JOBS).glob("*.json")) if (ROOT / JOBS).exists() else []:
        job = json.loads(path.read_text())
        problems = validate(job, "job.schema.json")
        if job.get("id") != path.stem:
            problems.append(f"id {job.get('id')!r} does not match the file name")
        for p in problems:
            print(f"{path.relative_to(ROOT)}: {p}")
        bad += bool(problems)
    for path in sorted((ROOT / RESULTS).glob("*/result.json")) if (ROOT / RESULTS).exists() else []:
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
        p.add_argument("--isolation", choices=["auto", "systemd", "none"])
        p.add_argument("--max-timeout", help="no job runs longer, such as 6h")
        p.add_argument("--state-dir", help="where runs, logs and work directories live (default verification/.state)")

    p = sub.add_parser("run", help="run pending jobs")
    budget(p)
    p.add_argument("--rev", help="the commit whose jobs to run (default: jj's @-, else HEAD)")
    p.add_argument("--watch", action="store_true", help="keep polling for newly committed jobs")
    p.add_argument("--min-priority", type=int, help="only jobs at this priority or above (verification/priorities.json, else the job's own)")
    p.add_argument("ids", nargs="*", help="only these jobs")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("prioritize", help="move jobs up or down the queue (verification/priorities.json); no ids lists it")
    p.add_argument("ids", nargs="*")
    p.add_argument("--priority", type=int, help="higher runs first; the default for every job is 0")
    p.add_argument("--reason", help="why: what waits on these jobs, or why they can wait")
    p.add_argument("--clear", action="store_true", help="drop these jobs' entries, back to their own priority")
    p.set_defaults(func=cmd_prioritize)

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
    p.add_argument("--step", nargs=2, action="append", metavar=("NAME", "COMMAND"), help="a bash step; repeatable")
    p.add_argument("--run", action="append", metavar="COMMAND", help="a bash step named after its command; repeatable")
    p.add_argument("--cwd", help="the steps' directory, relative to the repo root")
    p.add_argument("--expect-exit", type=int, help="the exit code that counts as a pass (default 0)")
    p.add_argument("--output", action="append", help="a file or directory the job writes that should come back; repeatable")
    p.add_argument("--requires", action="append", help="java javac jbmc tlc cargo jvmcontract gradle, or any command; repeatable")
    p.add_argument("--priority", type=int, help="higher runs first (default 0)")
    p.add_argument("--revision", help="run at this commit instead of the one that commits the job file")
    p.add_argument("--session", help="the submitting session's id")
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

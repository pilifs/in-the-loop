#!/usr/bin/env python3
"""What each test costs: its time, CPU, peak memory, and the tools it spawns.

`measure` runs the whole Rust suite, ignored tests included, and every Python suite: past jobs put that at about
3 hours, so it is queued as a pipeline job (lib/README.md's Tests section has the command), never run inline.

    python3 lib/tools/test_costs.py measure --out DIR      # everything; writes DIR's raw files and lib/tests/costs.json
    python3 lib/tools/test_costs.py inventory DIR          # rewrite lib/tests/costs.json from DIR's raw files
    python3 lib/tools/test_costs.py estimate               # write lib/tests/costs.json from past runs, running nothing
    python3 lib/tools/test_costs.py watch -- CMD ...       # nextest's wrapper: run one test, record what it cost
    python3 lib/tools/test_costs.py python FILE --out F    # run one Python test file, recording each test

How it measures:
- Rust, under cargo-nextest (lib/tools/install-nextest.sh), one process per test. The tests without `#[ignore]` run in
  the debug profile, as a plain `cargo test` does; the ignored ones in release, as their pipeline jobs do. Each test's
  time and outcome come from nextest's JUnit output. The wrapper (`watch`, set in lib/.config/nextest.toml) adds its
  CPU time and peak memory from wait4, and the processes it spawned, sampled from /proc every 20 ms, so a process that
  lives less than that may be missed. Tests of one binary run one at a time, because several share a fixture
  directory under target/tmp; binaries run side by side. A test's time therefore includes its fixtures' setup, which
  a plain `cargo test` pays once per binary.
- A plain `cargo test`, debug, after `cargo test --no-run`: the default run's wall time and each binary's time, the
  baseline for the default run's budget.
- Python: each `test_*.py` file in its own process, as `python3 FILE` runs it (a file in a package is imported as part
  of it), one test at a time, timing each test the way `unittest --durations` does and sampling its processes the
  same way.

Tiers (decision 1 of the brief): unit has no subprocess and runs under 1 s; tool runs under 10 s and 1 GB; proof
spawns JBMC or TLC, or goes over the tool tier's limits.
"""
import argparse
import importlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "lib"
INVENTORY = LIB / "tests" / "costs.json"
POLL_S = 0.02
UNIT_S, TOOL_S, TOOL_MB = 1.0, 10.0, 1024
PROOF_TOOLS = {"jbmc", "tlc", "cbmc"}
INTERPRETERS = re.compile(r"^(?:sh|bash|dash|python3?(?:\.\d+)?|perl)$")
SKIP_DIRS = {"target", ".state", "traces", "node_modules", ".git", ".jj"}


# --- sampling a process tree --------------------------------------------------------------------------------------

def _ppid(pid):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    return int(stat[stat.rindex(")") + 2:].split()[1])


def _rss_mb(pid):
    try:
        return int(Path(f"/proc/{pid}/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2**20
    except (OSError, IndexError, ValueError):
        return 0.0


def tool_name(exe, argv):
    """What a spawned process is, by its executable and arguments: `jbmc`, `javac`, `java`, `tlc`, `jvmcontract`, or
    an interpreter with its script (`sh jbmc-stand-in`)."""
    # argv[0] before the executable: /proc/PID/exe resolves links (Ubuntu's `sleep` is `gnusleep`), and a script's
    # exe is its interpreter, which argv[0] names too.
    name = os.path.basename(argv[0] if argv else exe or "") or "?"
    if name.startswith("java") and name not in ("javac",) and any("tla2tools" in a or a.startswith("tlc2.") for a in argv):
        return "tlc"
    if INTERPRETERS.match(name):
        script = next((a for a in argv[1:] if not a.startswith("-")), None)
        if script and os.path.basename(script) == "tlc":
            return "tlc"
        return f"{name} {os.path.basename(script)}" if script else name
    return name


def _describe(pid):
    try:
        exe = os.readlink(f"/proc/{pid}/exe")
    except OSError:
        exe = None
    try:
        argv = [a.decode(errors="replace") for a in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") if a]
    except OSError:
        argv = []
    return tool_name(exe, argv)


class Tree:
    """The descendants of a root process, sampled: each new one's name, and the peak of their summed RSS."""

    def __init__(self, root, include_root):
        self.root, self.include_root = root, include_root
        self.members = {root}
        self.seen = set()
        self.spawned = {}
        self.peak_mb = 0.0

    def poll(self):
        try:
            pids = {int(p) for p in os.listdir("/proc") if p.isdigit()}
        except OSError:
            return
        new = sorted(pids - self.seen)
        self.seen = pids
        self.members &= pids | {self.root}
        added = True
        while added and new:
            added = False
            for pid in list(new):
                if _ppid(pid) in self.members:
                    self.members.add(pid)
                    new.remove(pid)
                    added = True
                    name = _describe(pid)
                    self.spawned[name] = self.spawned.get(name, 0) + 1
        rss = sum(_rss_mb(p) for p in self.members if p != self.root or self.include_root)
        self.peak_mb = max(self.peak_mb, rss)

    def take(self):
        """What was spawned and the peak since the last take, then start again."""
        out = (dict(sorted(self.spawned.items())), round(self.peak_mb, 1))
        self.spawned, self.peak_mb = {}, 0.0
        return out


# --- watch: nextest's wrapper ---------------------------------------------------------------------------------------

def watch(argv, out_dir=None):
    """Run one test's command, wait for it with wait4, and write what it cost to $TEST_COSTS_DIR/PID.json."""
    out_dir = out_dir or os.environ.get("TEST_COSTS_DIR")
    start = time.monotonic()
    pid = os.posix_spawnp(argv[0], argv, os.environ)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, lambda s, _f: os.kill(pid, s))
    tree = Tree(pid, include_root=True)
    while True:
        done, status, usage = os.wait4(pid, os.WNOHANG)
        if done:
            break
        tree.poll()
        time.sleep(POLL_S)
    wall = time.monotonic() - start
    spawned, peak = tree.take()
    if out_dir:
        record = {"binary": os.environ.get("NEXTEST_BINARY_ID"), "name": os.environ.get("NEXTEST_TEST_NAME"),
                  "profile": os.environ.get("NEXTEST_PROFILE"), "attempt": os.environ.get("NEXTEST_ATTEMPT"),
                  "wall_s": round(wall, 3), "cpu_s": round(usage.ru_utime + usage.ru_stime, 3),
                  "max_rss_mb": round(usage.ru_maxrss / 1024, 1), "tree_peak_mb": peak, "spawned": spawned,
                  "exit": os.waitstatus_to_exitcode(status)}
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        (Path(out_dir) / f"{os.getpid()}.json").write_text(json.dumps(record) + "\n")
    code = os.waitstatus_to_exitcode(status)
    if code < 0:
        signal.signal(-code, signal.SIG_DFL)
        os.kill(os.getpid(), -code)
    return code


# --- python: one test file, test by test -------------------------------------------------------------------------

def _module_for(path):
    """The directory to put on sys.path and the module name, as `python3 FILE` or `unittest discover -t` would."""
    path = path.resolve()
    parts, top = [path.stem], path.parent
    while (top / "__init__.py").exists():
        parts.insert(0, top.name)
        top = top.parent
    return top, path.parent, ".".join(parts)


class _Sampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.tree, self.lock, self.stop = Tree(os.getpid(), include_root=False), threading.Lock(), threading.Event()

    def run(self):
        while not self.stop.is_set():
            with self.lock:
                self.tree.poll()
            time.sleep(POLL_S)

    def take(self):
        with self.lock:
            self.tree.poll()
            return self.tree.take()


class _Recorder(unittest.TextTestResult):
    def __init__(self, *args, sampler, records, **kwargs):
        super().__init__(*args, **kwargs)
        self.sampler, self.records, self.outcome = sampler, records, {}

    def startTest(self, test):
        self.sampler.take()
        self.outcome[test.id()] = "passed"
        self._t = (time.perf_counter(), time.process_time(), os.times())
        super().startTest(test)

    def _mark(self, test, outcome):
        self.outcome[test.id()] = outcome

    def addFailure(self, test, err):
        self._mark(test, "failed")
        super().addFailure(test, err)

    def addError(self, test, err):
        self._mark(test, "failed")
        super().addError(test, err)

    def addSkip(self, test, reason):
        self._mark(test, "skipped")
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self._mark(test, "passed")
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self._mark(test, "failed")
        super().addUnexpectedSuccess(test)

    def stopTest(self, test):
        super().stopTest(test)
        wall0, cpu0, times0 = self._t
        times1 = os.times()
        children = (times1.children_user - times0.children_user) + (times1.children_system - times0.children_system)
        spawned, peak = self.sampler.take()
        self.records.append({"name": test.id(), "wall_s": round(time.perf_counter() - wall0, 3),
                             "cpu_s": round(time.process_time() - cpu0 + children, 3), "tree_peak_mb": peak,
                             "spawned": spawned, "status": self.outcome.get(test.id(), "passed")})


def run_python_file(path, out):
    """Run one Python test file as `python3 FILE` would, recording each test as a JSON line in OUT."""
    path = Path(path)
    top, here, module = _module_for(path)
    sys.path[:0] = [str(here)] if top == here else [str(top), str(here)]
    records, sampler = [], _Sampler()
    sampler.start()
    load_error = None
    try:
        suite = unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(module))
    except Exception as e:  # noqa: BLE001: a file that fails to import is recorded, not fatal
        suite, load_error = unittest.TestSuite(), f"{type(e).__name__}: {e}"
    runner = unittest.TextTestRunner(verbosity=1, resultclass=lambda *a, **k: _Recorder(*a, sampler=sampler,
                                                                                         records=records, **k))
    result = runner.run(suite)
    sampler.stop.set()
    file = str(path.resolve().relative_to(ROOT)) if path.resolve().is_relative_to(ROOT) else str(path)
    with open(out, "a") as f:
        if load_error:
            f.write(json.dumps({"file": file, "name": None, "status": "failed", "error": load_error}) + "\n")
        for r in records:
            f.write(json.dumps({"file": file, **r}) + "\n")
    return 0 if result.wasSuccessful() and not load_error else 1


def python_test_files(root=ROOT):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        rel = Path(dirpath).relative_to(root)
        if rel.parts[:1] == ("examples",) and len(rel.parts) > 1 and rel.parts[1][:1].isdigit():
            continue
        files += [Path(dirpath) / f for f in sorted(filenames) if re.fullmatch(r"test_\w+\.py", f)]
    return files


# --- the inventory ------------------------------------------------------------------------------------------------

def tier(wall_s, peak_mb, spawned):
    """The tier a test measures into, and why."""
    proof = sorted(PROOF_TOOLS & set(spawned))
    if proof:
        return "proof", "spawns " + ", ".join(proof)
    if wall_s is not None and wall_s >= TOOL_S:
        return "proof", f"{wall_s:.1f} s, over the tool tier's {TOOL_S:.0f} s"
    if peak_mb is not None and peak_mb >= TOOL_MB:
        return "proof", f"{peak_mb:.0f} MB, over the tool tier's {TOOL_MB} MB"
    if spawned:
        return "tool", "spawns " + ", ".join(sorted(spawned))
    if wall_s is not None and wall_s >= UNIT_S:
        return "tool", f"{wall_s:.1f} s, over the unit tier's {UNIT_S:.0f} s"
    return "unit", "in process, under 1 s"


def read_junit(path, profile):
    """Each test case in a nextest JUnit file: binary, name, time and outcome."""
    out = {}
    if not Path(path).exists():
        return out
    for suite in ET.parse(path).getroot().iter("testsuite"):
        for case in suite.iter("testcase"):
            status = "passed"
            if case.find("failure") is not None or case.find("error") is not None:
                status = "failed"
            elif case.find("skipped") is not None:
                status = "skipped"
            out[(suite.get("name"), case.get("name"))] = {"time_s": float(case.get("time") or 0), "status": status,
                                                            "profile": profile}
    return out


def read_watch(directory):
    """The wrapper's records by (binary, name), the last attempt's when a test was retried."""
    out = {}
    for p in sorted(Path(directory).glob("*.json")) if Path(directory).is_dir() else []:
        r = json.loads(p.read_text())
        key = (r["binary"], r["name"])
        if key not in out or int(r.get("attempt") or 1) >= int(out[key].get("attempt") or 1):
            out[key] = r
    return out


CARGO_RUNNING = re.compile(r"^\s*Running (?:unittests )?(\S+)")
CARGO_RESULT = re.compile(r"^test result: (\w+)\. (\d+) passed; (\d+) failed; (\d+) ignored; .*finished in ([\d.]+)s")


def read_cargo_test(path):
    """The plain `cargo test` run: each binary's time and counts, from its console output."""
    binaries, current = [], None
    if not Path(path).exists():
        return binaries
    for line in Path(path).read_text(errors="replace").splitlines():
        if m := CARGO_RUNNING.match(line):
            current = m.group(1)
        elif line.strip().startswith("Doc-tests "):
            current = "doc-tests " + line.split()[-1]
        elif (m := CARGO_RESULT.match(line)) and current:
            binaries.append({"binary": current, "passed": int(m.group(2)), "failed": int(m.group(3)),
                             "ignored": int(m.group(4)), "time_s": float(m.group(5))})
            current = None
    return binaries


def inventory(raw, source):
    """costs.json's content from the raw files in RAW: every test with its measured time, cost and tier."""
    raw = Path(raw)
    meta = json.loads((raw / "run.json").read_text()) if (raw / "run.json").exists() else {}
    junit = {**read_junit(raw / "junit-debug.xml", "debug"), **read_junit(raw / "junit-release.xml", "release")}
    watched = read_watch(raw / "watch")
    rust = []
    for (binary, name), j in sorted(junit.items()):
        w = watched.get((binary, name), {})
        peak = max(w.get("max_rss_mb") or 0, w.get("tree_peak_mb") or 0) if w else None
        spawned = w.get("spawned", {})
        measured, why = tier(j["time_s"], peak, spawned) if j["status"] != "skipped" else (None, "not run")
        declared = "ignored" if j["profile"] == "release" else "default"
        rust.append({"binary": binary, "name": name, "declared": declared, "profile": j["profile"],
                     "status": j["status"], "time_s": j["time_s"], "cpu_s": w.get("cpu_s"), "peak_mb": peak,
                     "spawned": spawned, "tier": measured, "why": why, "source": source})
    python = []
    if (raw / "python.jsonl").exists():
        for line in (raw / "python.jsonl").read_text().splitlines():
            r = json.loads(line)
            if r.get("name") is None:
                python.append({**r, "tier": None, "why": "the file failed to load", "source": source})
                continue
            measured, why = tier(r["wall_s"], r.get("tree_peak_mb"), r.get("spawned", {})) \
                if r["status"] != "skipped" else (None, "skipped")
            python.append({"file": r["file"], "name": r["name"], "status": r["status"], "time_s": r["wall_s"],
                           "cpu_s": r.get("cpu_s"), "peak_mb": r.get("tree_peak_mb"), "spawned": r.get("spawned", {}),
                           "tier": measured, "why": why, "source": source})

    def counts(rows, key):
        out = {}
        for r in rows:
            out.setdefault(r[key], {}).setdefault(r["tier"] or "not measured", 0)
            out[r[key]][r["tier"] or "not measured"] += 1
        return out

    default = [r for r in rust if r["declared"] == "default"]
    return {
        "generated": f"by lib/tools/test_costs.py from {source}; regenerate, never edit by hand",
        "thresholds": {"unit": f"no subprocess, under {UNIT_S:.0f} s", "tool": f"under {TOOL_S:.0f} s and {TOOL_MB} MB",
                       "proof": "spawns " + ", ".join(sorted(PROOF_TOOLS)) + ", or over the tool tier's limits"},
        "run": meta,
        "default_cargo_test": meta.get("default_cargo_test"),
        "summary": {
            "rust": {"tests": len(rust), "by_declared": counts(rust, "declared"),
                     "failed": sum(r["status"] == "failed" for r in rust),
                     "default_proof_tier": sum(r["tier"] == "proof" for r in default),
                     "ignored_below_proof": sum(r["declared"] == "ignored" and r["tier"] in ("unit", "tool")
                                                for r in rust)},
            "python": {"tests": len(python), "by_file": counts(python, "file"),
                       "failed": sum(r["status"] == "failed" for r in python)},
        },
        "rust": rust,
        "python": python,
    }


def write_inventory(raw, source, path=INVENTORY):
    doc = inventory(raw, source)
    Path(path).write_text(json.dumps(doc, indent=1) + "\n")
    return doc


# --- estimate: the inventory from past runs and what each test calls --------------------------------------------

TIERS = ("unit", "tool", "proof")
PROOF_CALLS = {"jbmc": "JBMC", "tlc": "TLC"}


def _by_time(seconds):
    return "proof" if seconds >= TOOL_S else "tool" if seconds >= UNIT_S else "unit"


def _source_text(sources):
    return ", ".join(sources) if sources else "no past run"


def estimate_tier(calls, cost, ignore=None):
    """A test's tier from what it calls (cost_inventory's `calls`) and what past runs say (its `cost`): the higher of
    the two. Returns the tier, why (what decided it, besides the cost), and, when no past run settles it, why it is
    an estimate."""
    proof = [PROOF_CALLS[c] for c in calls if c in PROOF_CALLS]
    spawns = [c for c in calls if c not in PROOF_CALLS]
    static = "proof" if proof else "tool" if spawns else "unit"
    why = ["calls " + " and ".join(proof) if proof else "spawns " + ", ".join(spawns) if spawns
           else "nothing outside the process"]
    s, kind = cost["seconds"], cost["kind"]
    timed = _by_time(s) if kind == "run alone" else "proof" if kind == "over 60 s" else None
    tier = max(static, timed or "unit", "proof" if ignore is not None else "unit", key=TIERS.index)
    if timed and TIERS.index(timed) > TIERS.index(static):
        why.append(f"over the {static} tier's {UNIT_S if static == 'unit' else TOOL_S:g} s")
    elif ignore is not None and static != "proof" and timed != "proof":
        why.append("ignored as expensive")
    if static == "proof" and s is not None and s < UNIT_S and kind in ("run alone", "at most"):
        return tier, "; ".join(why), (f"took {'' if kind == 'run alone' else 'at most '}{s:g} s, too quick for "
                                      f"{' or '.join(proof)}: it may stop before running it")
    if static == "proof" or timed is not None:
        return tier, "; ".join(why), None
    if kind == "at most" and s < (UNIT_S if tier == "unit" else TOOL_S):
        return tier, "; ".join(why), None
    if kind == "estimated":
        return tier, "; ".join(why), "no past run names it: the tier is from what it calls"
    return tier, "; ".join(why), f"past runs bound it only at {s:g} s: the tier is from what it calls"


def _row(key, test, cost, ignore=None):
    tier_, why, estimated = estimate_tier(test["calls"], cost, ignore)
    row = {**key, "tier": tier_, "calls": test["calls"], "cost": {**cost, "estimated": estimated} if estimated else cost,
           "why": why}
    if ignore is not None:
        row["ignored"] = ignore
    return row


def estimate(root=ROOT, fetch=False, exclude=("test-cost",)):
    """costs.json's content, from the tests' sources, past sessions' logs and past jobs: nothing is run."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import cost_inventory as ci
    rust_tests = ci.rust_tests(root)
    py_tests = ci.python_tests(root)
    cargo, py_runs, missing = ci.session_evidence(root, fetch, exclude)
    jobs = ci.job_evidence(root)
    rust_ev = ci.rust_evidence(rust_tests, cargo + jobs)
    py_ev = ci.python_evidence(py_tests, py_runs)
    rust = []
    for t in rust_tests:
        row = _row({"file": t["file"], "name": t["name"]}, t, ci.cost(rust_ev[(t["binary"], t["name"])]), t["ignore"])
        if row["tier"] == "proof" and t["ignore"] is None:
            row["retier"] = "pending"
        rust.append(row)
    python = []
    for t in py_tests:
        row = _row({"file": t["file"], "name": t["name"]}, t, ci.cost(py_ev[(t["file"], t["name"])]))
        if row["tier"] == "proof":
            row["retier"] = "pending"
        python.append(row)

    def counts(rows, key):
        out = {}
        for r in rows:
            c = out.setdefault(r[key], {"unit": 0, "tool": 0, "proof": 0, "estimated": 0, "retier pending": 0})
            c[r["tier"]] += 1
            c["estimated"] += "estimated" in r["cost"]
            c["retier pending"] += r.get("retier") == "pending"
        return out

    used = sorted({src for r in rust + python for src in r["cost"]["sources"] if src.startswith("log:")})
    short = {src: src[:4 + 16] for src in used}
    if len(set(short.values())) < len(short):
        short = {src: src for src in used}
    for r in rust + python:
        r["cost"]["sources"] = [short.get(src, src) for src in r["cost"]["sources"]]
    return {
        "generated": "by `python3 lib/tools/test_costs.py estimate`, from what each test calls and past runs; regenerate, "
                     "never edit by hand. A test's tier is the higher of what it calls (JBMC or TLC: proof; javac, "
                     "java, the jvmcontract binary, a stand-in script or another process: tool; nothing: unit) and "
                     "what a past run took (cost.kind `run alone` or `over 60 s`). `at most` is a bound from runs "
                     "with other tests. A source is a past job (`job:ID`) or a session's redacted log (`log:` and the "
                     "start of its sha256, in full under sources.logs); `estimated` says why no past run settles the tier. `retier: pending` marks "
                     "a proof-tier test that runs by default, for the next loop. A later `measure` run replaces it.",
        "thresholds": {"unit": f"no subprocess, under {UNIT_S:g} s", "tool": f"under {TOOL_S:g} s and {TOOL_MB} MB",
                       "proof": "JBMC, TLC, or over the tool tier's limits"},
        "sources": {"read": {"session_logs": len({e["source"] for e in cargo + py_runs}),
                             "jobs": len({e["source"] for e in jobs}),
                             "sessions_without_a_log_here": len(missing), "left_out_loops": list(exclude)},
                    "logs": {short[src]: src for src in used}},
        "summary": {"rust": counts(rust, "file"), "python": counts(python, "file")},
        "rust": rust,
        "python": python,
    }


def dumps(doc):
    """The inventory as JSON with one test per line, so that a regeneration's diff shows the tests that changed."""
    head = {k: v for k, v in doc.items() if k not in ("rust", "python", "summary")}
    text = json.dumps(head, indent=1)[:-2] + ',\n "summary": {'
    for i, key in enumerate(("rust", "python")):
        rows = ",\n".join(f"   {json.dumps(f)}: {json.dumps(c)}" for f, c in doc["summary"][key].items())
        text += f'{"," if i else ""}\n  "{key}": {{\n{rows}\n  }}'
    text += "\n }"
    for key in ("rust", "python"):
        rows = ",\n".join("  " + json.dumps(r, separators=(", ", ": ")) for r in doc[key])
        text += f',\n "{key}": [\n{rows}\n ]'
    return text + "\n}\n"


# --- measure: the job's step ---------------------------------------------------------------------------------------

def _run(cmd, log, env=None, cwd=LIB):
    print(f"$ {' '.join(cmd)}", flush=True)
    start = time.monotonic()
    with open(log, "w") as f:
        code = subprocess.run(cmd, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT).returncode
    elapsed = time.monotonic() - start
    print(f"  exit {code} in {elapsed:.0f} s; output in {log}", flush=True)
    return code, round(elapsed, 1)


def _group_config(path, binaries):
    """A nextest tool config putting each test binary in a group of its own, one test at a time."""
    lines = ["[test-groups]"]
    names = {b: re.sub(r"[^A-Za-z0-9_-]", "-", b) for b in binaries}
    lines += [f'{n} = {{ max-threads = 1 }}' for n in names.values()]
    for b, n in names.items():
        lines += ["", "[[profile.measure.overrides]]", f"filter = 'binary_id(={b})'", f'test-group = "{n}"']
    Path(path).write_text("\n".join(lines) + "\n")


def _binaries(env, flags, ignored):
    """The test binaries a nextest run with these flags would run, from `cargo nextest list`."""
    out = subprocess.run(["cargo", "nextest", "list", *flags, "--message-format", "json", "--run-ignored", ignored],
                         cwd=LIB, env=env, capture_output=True, text=True, check=True).stdout
    return sorted(json.loads(out)["rust-suites"])


def measure(out, threads, source):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "TEST_COSTS_DIR": str(out / "watch")}
    env.pop("JVMCONTRACT_SKIP_MISSING_TOOLS", None)
    meta = {"started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "cpus": os.cpu_count(), "test_threads": threads,
            "nextest": subprocess.run(["cargo", "nextest", "--version"], cwd=LIB, capture_output=True,
                                      text=True).stdout.split("\n")[0], "steps": {}}

    code, t = _run(["cargo", "test", "--no-run"], out / "cargo-test-build.log", env)
    code, t = _run(["cargo", "test"], out / "cargo-test.log", env)
    meta["default_cargo_test"] = {"exit": code, "wall_s": t, "binaries": read_cargo_test(out / "cargo-test.log")}

    for profile, flags, ignored in (("debug", [], "default"), ("release", ["--release"], "only")):
        _run(["cargo", "nextest", "run", *flags, "--no-run"], out / f"nextest-{profile}-build.log", env)
        groups = out / f"groups-{profile}.toml"
        _group_config(groups, _binaries(env, flags, ignored))
        code, t = _run(["cargo", "nextest", "run", *flags, "--profile", "measure", "--run-ignored", ignored,
                        "--no-fail-fast", "--test-threads", str(threads), "--tool-config-file",
                        f"test-costs:{groups}"], out / f"nextest-{profile}.log", env)
        meta["steps"][f"nextest-{profile}"] = {"exit": code, "wall_s": t}
        junit = LIB / "target" / "nextest" / "measure" / "junit.xml"
        if junit.exists():
            (out / f"junit-{profile}.xml").write_bytes(junit.read_bytes())

    (out / "python.jsonl").unlink(missing_ok=True)
    py_start = time.monotonic()
    meta["python_files"] = {}
    for f in python_test_files():
        rel = str(f.relative_to(ROOT))
        code, t = _run([sys.executable, str(Path(__file__).resolve()), "python", str(f), "--out",
                        str(out / "python.jsonl")], out / f"python-{rel.replace('/', '-')}.log", env, cwd=ROOT)
        meta["python_files"][rel] = {"exit": code, "wall_s": t}
    meta["steps"]["python"] = {"wall_s": round(time.monotonic() - py_start, 1)}
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "run.json").write_text(json.dumps(meta, indent=1) + "\n")
    doc = write_inventory(out, source)
    s = doc["summary"]
    print(json.dumps(s["rust"], indent=1))
    print(f"python: {s['python']['tests']} tests, {s['python']['failed']} failed")
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["watch"]:
        rest = argv[1:]
        return watch(rest[1:] if rest[:1] == ["--"] else rest)
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="command", required=True)
    m = sub.add_parser("measure", help="run everything and write the raw files and the inventory")
    m.add_argument("--out", required=True)
    m.add_argument("--test-threads", type=int,
                   default=int(float(os.environ.get("VERIFY_CPUS") or max(1, (os.cpu_count() or 2) // 2))),
                   help="tests at once (default: the job's CPUs, $VERIFY_CPUS)")
    m.add_argument("--source", default=os.environ.get("VERIFY_JOB_ID") or "a run of `measure`")
    i = sub.add_parser("inventory", help="rewrite the inventory from a measure run's raw files")
    i.add_argument("raw")
    i.add_argument("--source", default="a run of `measure`")
    i.add_argument("--path", default=str(INVENTORY))
    e = sub.add_parser("estimate", help="write the inventory from past runs and what each test calls, running nothing")
    e.add_argument("--path", default=str(INVENTORY))
    e.add_argument("--fetch", action="store_true", help="download published session logs not stored here")
    e.add_argument("--exclude", action="append", default=None, metavar="LOOP",
                   help="leave a loop's sessions out (default: test-cost, whose log changes with every commit)")
    py = sub.add_parser("python", help="run one Python test file, test by test")
    py.add_argument("file")
    py.add_argument("--out", required=True)
    a = p.parse_args(argv)
    if a.command == "measure":
        return measure(a.out, a.test_threads, a.source)
    if a.command == "inventory":
        write_inventory(a.raw, a.source, a.path)
        return 0
    if a.command == "estimate":
        doc = estimate(ROOT, a.fetch, tuple(a.exclude) if a.exclude is not None else ("test-cost",))
        Path(a.path).write_text(dumps(doc))
        for key in ("rust", "python"):
            rows = doc[key]
            tiers = {t: sum(r["tier"] == t for r in rows) for t in TIERS}
            print(f"{key}: {len(rows)} tests, {tiers}, {sum('estimated' in r['cost'] for r in rows)} estimated, "
                  f"{sum(r.get('retier') == 'pending' for r in rows)} retier pending")
        return 0
    return run_python_file(a.file, a.out)


if __name__ == "__main__":
    sys.exit(main())

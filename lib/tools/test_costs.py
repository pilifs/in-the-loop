#!/usr/bin/env python3
"""What each test costs: its time, CPU, peak memory, and the tools it spawns.

`measure` runs the whole Rust suite, ignored tests included, and every Python suite: past jobs put that at about
3 hours, so it is queued as a pipeline job (lib/README.md's Tests section has the command), never run inline.

    python3 lib/tools/test_costs.py measure --out DIR      # everything; writes DIR's raw files and lib/tests/costs.json
    python3 lib/tools/test_costs.py inventory DIR          # rewrite lib/tests/costs.json from DIR's raw files
    python3 lib/tools/test_costs.py estimate               # write lib/tests/costs.json from past runs, running nothing
    python3 lib/tools/test_costs.py tag FILE ...           # give FILE's tests the tier tag their row asks for
    python3 lib/tools/test_costs.py run [--tier unit]      # the default run (or the unit tier alone), Rust and Python
    python3 lib/tools/test_costs.py run --tier proof       # the proof tier: a pipeline job, never inline
    python3 lib/tools/test_costs.py lint                   # the tier tags, the sources and the inventory agree
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


NONE_YET = "proxy: none yet"


def _listed(rows, previous, listed):
    """Mark the rows that join the `retier: pending` or `proxy: none yet` list without a person's say. Joining is
    for a person to decide: a row is on a list if PREVIOUS (the inventory before, None for none) had it there, or
    LISTED (`FILE::NAME`s, from `estimate --list`) names it. A proof-tier test that calls JBMC or TLC and runs by
    default, or a proof tag with no proxy, that is on neither gets `unlisted`, which the lint refuses. A test that is
    proof tier only by a past run's time joins `retier: pending` freely: the tier is an estimate."""
    if previous is None:
        return
    before = {(r["file"], r["name"]): r for r in previous}
    for r in rows:
        key = (r["file"], r["name"])
        old = before.get(key, {})
        named = f"{r['file']}::{r['name']}" in listed
        unlisted = []
        if r.get("retier") == "pending" and PROOF_CALLS.keys() & set(r["calls"]):
            if not (named or old.get("retier") == "pending"):
                del r["retier"]
                unlisted.append("retier: pending")
        if NONE_YET in (r.get("ignored") or ""):
            if not (named or (NONE_YET in (old.get("ignored") or "") and "unlisted" not in old)):
                unlisted.append(NONE_YET)
        if unlisted:
            r["unlisted"] = ", ".join(unlisted) + ": for a person to decide (estimate --list), or tag it"


def estimate(root=ROOT, fetch=False, exclude=("test-cost",), previous=None, listed=()):
    """costs.json's content, from the tests' sources, past sessions' logs and past jobs: nothing is run. PREVIOUS is
    the inventory it replaces, whose `retier: pending` and `proxy: none yet` lists only LISTED tests may join."""
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
        # Python's counterpart of an ignore reason
        skipped = (t["reason"] or '@cost("proof")') if t["cost"] == "proof" else None
        row = _row({"file": t["file"], "name": t["name"]}, t, ci.cost(py_ev[(t["file"], t["name"])]), skipped)
        if row["tier"] == "proof" and skipped is None:
            row["retier"] = "pending"
        python.append(row)
    listed = set(listed)
    _listed(rust, (previous or {}).get("rust") if previous is not None else None, listed)
    _listed(python, (previous or {}).get("python") if previous is not None else None, listed)

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
                     "a proof-tier test that runs by default, for the next loop. A test that calls JBMC or TLC joins "
                     "that list, and a proof tag joins the `proxy: none yet` list, only when a person names it "
                     "(`estimate --list FILE::NAME`); until then its row is `unlisted`, which `test_costs.py lint` "
                     "refuses. A later `measure` run replaces the estimates.",
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


# --- running a tier -----------------------------------------------------------------------------------------------

RUN_TIERS = ("default", "unit", "proof")
PY_RAN_LINE = re.compile(r"^Ran \d+ tests? in [\d.]+s$", re.M)
PY_OUTCOME_LINE = re.compile(r"^(?:OK|FAILED|NO TESTS RAN)\b.*$", re.M)


def tier_runs(tier, doc, root=ROOT, only=None, tests=(), test_threads=None):
    """The commands that run TIER, as (label, argv, env, cwd): `cargo test` in lib/, then each Python test file the
    inventory DOC lists, in its own process. `default` is what runs inline: the unit and tool tiers and the
    `retier: pending` tests. `unit` is the unit tier alone. `proof` is the ignored Rust tests in release and the
    Python tests tagged `@cost("proof")`: a pipeline job, never run inline. ONLY ("rust" or "python") keeps one
    language; TESTS keeps those Rust test binaries (`--test NAME`)."""
    if tier not in RUN_TIERS:
        raise ValueError(f"tier {tier!r}: the tiers to run are {', '.join(RUN_TIERS)}")
    value = {"default": "tool", "unit": "unit", "proof": "proof"}[tier]
    env = {"JVMCONTRACT_TEST_TIER": value, "TEST_COST": value}
    runs = []
    if only in (None, "rust"):
        argv = ["cargo", "test", "--manifest-path", "lib/Cargo.toml"] + (["--release"] if tier == "proof" else [])
        argv += [a for t in tests for a in ("--test", t)]
        after = (["--ignored"] if tier == "proof" else []) + (["--test-threads", str(test_threads)] if test_threads else [])
        runs.append(("cargo test", argv + (["--"] + after if after else []), env, root))
    if only in (None, "python"):
        rows = {}
        for r in doc["python"]:
            if tier != "proof" or (r["tier"] == "proof" and r.get("retier") != "pending"):
                rows.setdefault(r["file"], []).append(r["name"])
        for rel in sorted(rows):
            top, here, module = _module_for(root / rel)
            paths = [os.path.relpath(d, root) for d in ([top] if top == here else [top, here])]
            argv = [sys.executable, "-m", "unittest", module]
            if tier == "proof":
                argv += [a for name in rows[rel] for a in ("-k", name)]
            runs.append((rel, argv, {**env, "PYTHONPATH": os.pathsep.join(paths)}, root))
    return runs


def _shown(argv, env):
    return " ".join([f"{k}={v}" for k, v in env.items()] + [Path(a).name if a == sys.executable else a for a in argv])


# --- choosing the tests of what changed --------------------------------------------------------------------------

# What makes `cargo test` worth running: lib/ but its Python tools and pages, and the two Python files tests/tiers.rs
# reads for its lint.
RUST_INPUTS = re.compile(r"^lib/(?!tools/|README\.md$|.*\.md$)|^lib/tools/(test_costs|cost_tier)\.py$")
SKIP_DIRS = {".git", ".jj", "target", "node_modules", "__pycache__", ".state"}
# Files a test is not taken to read by naming them: records and generated files that every few modules name (the
# trace index, the decision records, job results), and the test inventory, which every test file names through the
# shared cost decorator. A test of them is chosen as any other, by changing or importing what changed.
NOT_BY_NAME = re.compile(r"^(llm-dlc/traces/|llm-dlc/index\.json$|llm-dlc/README\.md$|llm-dlc/decisions/|verification/results/|"
                         r"verification/jobs/|lib/tests/costs\.json$|examples/index\.json$|examples/README\.md$)")
SHARED = {"cost_tier.py"}  # imported by every test file: what it names says nothing of one test


def changed_paths(root, since=None):
    """The files changed in @ (`jj diff`), or since revision SINCE."""
    argv = ["jj", "--quiet", "diff", "--name-only"] + (["--from", since, "--to", "@"] if since else [])
    r = subprocess.run(argv, cwd=root, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"jj diff: {r.stderr.strip()}")
    return sorted(set(r.stdout.split()))


def _python_modules(root):
    """Every Python file of the repository by its module name's last part: an import names a module, not a path, and
    the tests put several folders on sys.path, so a name is taken to mean every file of that name (more is chosen,
    never less)."""
    out = {}
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            if f.endswith(".py"):
                path = Path(dirpath) / f
                out.setdefault(path.stem if f != "__init__.py" else path.parent.name, []).append(path)
    return out


def _imports(path):
    import ast
    try:
        tree = ast.parse(Path(path).read_text())
    except (OSError, SyntaxError, ValueError):
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {part for a in node.names for part in a.name.split(".")}
        elif isinstance(node, ast.ImportFrom):
            names |= set((node.module or "").split(".")) | {a.name for a in node.names}
    return names - {""}


def _strings(path, cache={}):
    """The string literals of a Python file's code, its docstrings left out: where a test names a file it reads or
    runs, as opposed to a page its prose points at."""
    import ast
    path = Path(path)
    if path not in cache:
        try:
            tree = ast.parse(path.read_text())
        except (OSError, SyntaxError, ValueError):
            cache[path] = ""
            return ""
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        cache[path] = "\n".join(n.value for n in ast.walk(tree)
                                if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs)
    return cache[path]


def closure(path, modules, cache):
    """The repository's Python files a test file imports, itself included, transitively."""
    seen, todo = set(), [Path(path).resolve()]
    while todo:
        p = todo.pop()
        if p in seen:
            continue
        seen.add(p)
        if p not in cache:
            cache[p] = _imports(p)
        todo += [m.resolve() for name in cache[p] for m in modules.get(name, [])]
    return seen


def changed_selection(root, doc, changed):
    """What the change in CHANGED (repository paths) asks to run: (`cargo test` arguments or None, the Python test
    files with why each). A Python file is chosen when it changed, when a module it imports (transitively) changed,
    or when its source or that of a module it imports names a changed file by its path or, for a distinctive name,
    by its file name: a test that reads a schema, a sidecar or a script it runs. Naming counts in the test file and
    the modules it imports directly, and not for the files NOT_BY_NAME lists. Rust runs when lib/ changed beyond
    its Python tools and pages; only the test binaries that changed, when nothing else of lib/ did."""
    root = Path(root)
    rust_changed = [c for c in changed if RUST_INPUTS.search(c)]
    rust = None
    if rust_changed:
        only_tests = all(re.fullmatch(r"lib/tests/[^/]+\.rs", c) for c in rust_changed)
        rust = [Path(c).stem for c in rust_changed] if only_tests else []
    modules, cache, chosen = _python_modules(root), {}, {}
    changed_abs = {(root / c).resolve(): c for c in changed}
    names = [(c, Path(c).name) for c in changed]
    for rel in sorted({r["file"] for r in doc["python"]}):
        test = (root / rel).resolve()
        if not test.exists():
            continue
        files = closure(test, modules, cache)
        why = None
        if test in changed_abs:
            why = "it changed"
        elif hit := next((changed_abs[f] for f in files if f in changed_abs), None):
            why = f"it imports {hit}"
        else:
            direct = [test] + [m.resolve() for n in cache.get(test, set()) for m in modules.get(n, [])
                               if m.name not in SHARED]
            text = "\n".join(_strings(f) for f in dict.fromkeys(direct))
            for c, name in names:
                if NOT_BY_NAME.search(c):
                    continue
                if c in text or (len(name) >= 10 and name != "README.md" and name in text):
                    why = f"it names {c}"
                    break
        if why:
            chosen[rel] = why
    return rust, chosen


RUST_FAILED = re.compile(r"^test (\S+) \.\.\. FAILED$", re.M)


def _python_file(label, argv, env, cwd):
    """Run one Python test file: (exit code, the line for it, its output)."""
    p = subprocess.run(argv, env={**os.environ, **env}, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    ran, outcome = PY_RAN_LINE.findall(p.stdout), PY_OUTCOME_LINE.findall(p.stdout)
    line = f"{label}: {ran[-1] if ran else 'no tests ran'}{', ' + outcome[-1] if outcome else ''}"
    return p.returncode, line, p.stdout


def run_tier(tier, path=INVENTORY, root=ROOT, only=None, tests=(), test_threads=None, dry_run=False,
             serial=False, retry=True, changed=None):
    """Run TIER's commands: cargo's, and one line per Python file (its output in full when it fails). `cargo test`
    runs beside the Python files unless SERIAL (its output, kept in a file meanwhile, is printed when it ends), which
    takes the wall time from Rust's plus Python's to the longer of the two. With RETRY, what fails is run once more,
    a Python file whole and Rust's failed tests by name, and what passes then is reported as flaky (`FLAKY ...`) and
    counted as passed: a run then stops failing on noise, and the flaky tests are named to be fixed. Returns 0 if
    every command passed."""
    doc = json.loads(Path(path).read_text())
    runs = tier_runs(tier, doc, root, only, tests, test_threads)
    if changed is not None:  # only the tests of what changed (CHANGED: repository paths)
        rust, chosen = changed_selection(root, doc, changed)
        print(f"{len(changed)} changed file(s): " + (f"cargo test{' --test ' + ' --test '.join(rust) if rust else ''}"
              if rust is not None else "no cargo test") + f", {len(chosen)} Python test file(s)")
        for rel, why in chosen.items():
            print(f"  {rel}: {why}")
        if rust:
            runs = [r for r in runs if r[0] != "cargo test"] + tier_runs(tier, doc, root, "rust", rust, test_threads)
        runs = [r for r in runs if (r[0] == "cargo test" and rust is not None) or r[0] in chosen]
        if not runs:
            print(f"{tier} tier: nothing to run for what changed")
            return 0
    if tier == "proof" and not any(label != "cargo test" for label, *_ in runs) and only != "rust":
        print("python: no proof-tier tests")
    if dry_run:
        for label, argv, env, cwd in runs:
            print(_shown(argv, env))
        return 0
    failed, flaky = [], []
    cargo = next((r for r in runs if r[0] == "cargo test"), None)
    background = None
    if cargo and not serial and len(runs) > 1:
        import tempfile
        log = tempfile.NamedTemporaryFile("w+", prefix="cargo-test-", suffix=".log", delete=False)
        print(f"$ {_shown(cargo[1], cargo[2])} (beside the Python files; its output when it ends)", flush=True)
        background = (subprocess.Popen(cargo[1], env={**os.environ, **cargo[2]}, cwd=cargo[3], stdout=log,
                                       stderr=subprocess.STDOUT), log)
    elif cargo:
        print(f"$ {_shown(cargo[1], cargo[2])}", flush=True)
    for label, argv, env, cwd in runs:
        if label == "cargo test":
            continue
        code, line, output = _python_file(label, argv, env, cwd)
        if code and retry:
            again, line_again, _ = _python_file(label, argv, env, cwd)
            if again == 0:
                print(f"FLAKY {line} (failed, then passed on a second run)", flush=True)
                flaky.append(label)
                continue
        print(f"{'ok  ' if code == 0 else 'FAIL'} {line}", flush=True)
        if code:
            print(output)
            failed.append(label)
    if cargo:
        if background:
            proc, log = background
            code = proc.wait()
            log.seek(0)
            output = log.read()
            log.close()
            os.unlink(log.name)
            sys.stdout.write(output if code else "\n".join(output.splitlines()[-3:]) + "\n")
        else:
            p = subprocess.run(cargo[1], env={**os.environ, **cargo[2]}, cwd=cargo[3], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
            code, output = p.returncode, p.stdout
            sys.stdout.write(output)
        names = sorted(set(RUST_FAILED.findall(output)))
        if code and retry and names:
            argv = cargo[1][:cargo[1].index("--")] if "--" in cargo[1] else list(cargo[1])
            after = cargo[1][cargo[1].index("--") + 1:] if "--" in cargo[1] else []
            again = subprocess.run(argv + ["--", *after, "--exact", *names], env={**os.environ, **cargo[2]},
                                   cwd=cargo[3], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if again.returncode == 0:
                print(f"FLAKY cargo test: {', '.join(names)} (failed, then passed on a second run)", flush=True)
                flaky.append("cargo test")
                code = 0
            else:
                print(f"cargo test: {', '.join(names)} failed again on a second run", flush=True)
        if code:
            failed.insert(0, "cargo test")
    print(f"{tier} tier: {len(runs) - len(failed)} of {len(runs)} passed"
          + (f"; failed: {', '.join(failed)}" if failed else "") + (f"; flaky: {', '.join(flaky)}" if flaky else ""))
    return 1 if failed else 0


# --- the lint: the tags, the sources and the inventory agree ----------------------------------------------------

PROXY = re.compile(r";\s*proxy:\s*(.+?)\s*$", re.S)
PROOF_PREFIX = "cost:proof: "


def _proof_reason(test, lang):
    """A test's proof tag as the inventory records it: Rust's ignore reason, or Python's `@cost("proof", ...)`
    reason (`@cost("proof")` without one), or None."""
    if lang == "rust":
        return test["ignore"]
    return (test["reason"] or '@cost("proof")') if test["cost"] == "proof" else None


def _lint_language(rows, tests, lang, root):
    import cost_inventory as ci
    problems = []
    inv = {(r["file"], r["name"]): r for r in rows}
    src = {(t["file"], t["name"]): t for t in tests}
    fix = "run `python3 lib/tools/test_costs.py estimate`"
    for f, n in sorted(src.keys() - inv.keys()):
        problems.append(f"{f}::{n}: not in the inventory: {fix}")
    for f, n in sorted(inv.keys() - src.keys()):
        problems.append(f"{f}::{n}: in the inventory, but no such test: {fix}")
    # A proxy is any test of the same language that runs by default, named in full or (Rust) by its last segment.
    runs, proof_tests = set(), set()
    for (f, n), t in src.items():
        names = {n, n.rsplit("::", 1)[-1]}
        (runs if _proof_reason(t, lang) is None else proof_tests).update(names)
    for key in sorted(src.keys() & inv.keys()):
        t, r = src[key], inv[key]
        where = f"{key[0]}::{key[1]}"
        reason = _proof_reason(t, lang)
        if r.get("ignored") != reason or r["calls"] != t["calls"]:
            problems.append(f"{where}: the inventory is out of date (what it calls, or its proof tag): {fix}")
        if "unlisted" in r:
            problems.append(f"{where}: {r['unlisted']}")
        if lang == "python" and t["skip"] is not None:
            problems.append(f"{where}: skipped unconditionally ({t['skip']!r}): a test set aside for its cost is "
                            f"@cost(\"proof\", \"WHAT IT RUNS, ~TIME; proxy: TEST\")")
        if reason is not None:
            if lang == "rust" and not reason.startswith(PROOF_PREFIX):
                problems.append(f"{where}: its ignore reason doesn't start with {PROOF_PREFIX!r}: {reason!r}")
            if lang == "python" and t["reason"] is None:
                problems.append(f"{where}: @cost(\"proof\") without a reason: give what it runs, about how long, and "
                                f"its proxy")
            m = PROXY.search(reason)
            if not m:
                problems.append(f"{where}: its proof tag names no proxy (`; proxy: TEST`, or `; {NONE_YET}`)")
            elif m[1] != "none yet":
                for proxy in (x.strip() for x in m[1].split(",")):
                    if proxy in runs:
                        continue
                    problems.append(f"{where}: its proxy {proxy} is " + ("itself proof tier: a proxy runs by default"
                                                                       if proxy in proof_tests else "no test"))
        if reason is None and PROOF_CALLS.keys() & set(t["calls"]) and r.get("retier") != "pending":
            tools = " and ".join(PROOF_CALLS[c] for c in t["calls"] if c in PROOF_CALLS)
            problems.append(f"{where}: calls {tools} but isn't proof tier: tag it "
                            + ("#[ignore = \"cost:proof: …; proxy: TEST\"]" if lang == "rust"
                               else "@cost(\"proof\", \"…; proxy: TEST\")")
                            + " and queue it, or a person lists it as retier: pending")
    by_file = {}
    for (f, n), r in inv.items():
        by_file.setdefault(f, {})[n] = r
    for f in sorted({k[0] for k in src}):
        text, rows_of = (root / f).read_text(), by_file.get(f, {})
        _, changed = ci.cost_decorators(text, f, rows_of, root) if lang == "python" else ci.tier_calls(text, f, rows_of)
        if changed:
            problems.append(f"{f}: {changed} tests' tier tags aren't what the inventory asks for: run "
                            f"`python3 lib/tools/test_costs.py tag {f}`")
    return problems


def lint(path=INVENTORY, root=ROOT, only=None):
    """What is wrong with the tests' tier tags, as a list of problems (empty when all is well). Read from the sources,
    against the inventory at PATH:
    - every test is in the inventory, every test it names exists, and what it records of each (what the test calls,
      its proof tag) is current;
    - every proof tag is `cost:proof: WHAT IT RUNS, ~TIME; proxy: TEST` (in Python, `@cost("proof", "...; proxy:
      TEST")`, and no unconditional `@unittest.skip`), and its proxy is a test that runs by default, or `none yet`
      for a test on the inventory's list;
    - no test outside the proof tier calls JBMC or TLC, except the inventory's `retier: pending` tests;
    - every test's tier tag (`tool_tier!`, `@cost`) is the one its row asks for;
    - no row joined the `retier: pending` or `proxy: none yet` list without a person (`unlisted`)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import cost_inventory as ci
    doc = json.loads(Path(path).read_text())
    problems = []
    if only != "python":
        problems += _lint_language(doc["rust"], ci.rust_tests(root), "rust", root)
    if only != "rust":
        problems += _lint_language(doc["python"], ci.python_tests(root), "python", root)
    return problems


def tag(files, path=INVENTORY, root=ROOT):
    """Give each test in FILES the tier tag its row in the inventory asks for, and take it away from a unit-tier
    test. In Rust the first statement: `tool_tier!()` for the tool tier, `tool_tier!(pending)` for `retier: pending`,
    none for an ignored test. In Python the decorator: `@cost("tool")`, `@cost("pending")`, or `@cost("proof")` for a
    test the default run already skips, with the import of `cost` while one is left. Returns {file: tests changed}."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import cost_inventory as ci
    doc = json.loads(Path(path).read_text())
    rows = {}
    for r in doc["rust"] + doc["python"]:
        rows.setdefault(r["file"], {})[r["name"]] = r
    out = {}
    for f in files:
        p = Path(f).resolve()
        rel = str(p.relative_to(root))
        if rel not in rows:
            raise SystemExit(f"{rel}: no tests of it in {path}")
        retag = ci.cost_decorators if rel.endswith(".py") else ci.tier_calls
        src, n = retag(p.read_text(), rel, rows[rel])
        if src != p.read_text():
            p.write_text(src)
        out[rel] = n
    return out


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
    e.add_argument("--list", action="append", default=[], metavar="FILE::NAME",
                   help="put a test on the retier-pending or proxy-none-yet list: for a person to decide, or for a "
                        "listed test that was renamed")
    t = sub.add_parser("tag", help="give a test file's tests the tier tag their row asks for (tool_tier! in Rust, "
                                   "@cost in Python)")
    t.add_argument("files", nargs="+")
    t.add_argument("--path", default=str(INVENTORY))
    r = sub.add_parser("run", help="run one tier: default (what runs inline), unit (the unit tier alone) or proof "
                                   "(a pipeline job, never inline)")
    r.add_argument("--tier", choices=RUN_TIERS, default="default")
    r.add_argument("--only", choices=("rust", "python"), help="one language")
    r.add_argument("--test", action="append", default=[], metavar="NAME", help="a Rust test binary (repeatable)")
    r.add_argument("--test-threads", type=int, help="Rust tests at once")
    r.add_argument("--dry-run", action="store_true", help="print the commands, run nothing")
    r.add_argument("--serial", action="store_true", help="cargo test after the Python files, not beside them")
    r.add_argument("--no-retry", action="store_true", help="what fails is not run a second time")
    r.add_argument("--changed", action="store_true", help="only the tests of what changed in @ (jj diff): the files that "
                   "changed, import what changed, or name a changed file; cargo test when lib/ changed")
    r.add_argument("--from", dest="since", metavar="REV", help="with --changed: what changed since REV, not only in @")
    r.add_argument("--path", default=str(INVENTORY))
    lt = sub.add_parser("lint", help="check that the tests' tier tags, their sources and the inventory agree")
    lt.add_argument("--only", choices=("rust", "python"), help="one language")
    lt.add_argument("--path", default=str(INVENTORY))
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
        previous = json.loads(Path(a.path).read_text()) if Path(a.path).exists() else None
        doc = estimate(ROOT, a.fetch, tuple(a.exclude) if a.exclude is not None else ("test-cost",), previous, a.list)
        Path(a.path).write_text(dumps(doc))
        for key in ("rust", "python"):
            rows = doc[key]
            tiers = {t: sum(r["tier"] == t for r in rows) for t in TIERS}
            print(f"{key}: {len(rows)} tests, {tiers}, {sum('estimated' in r['cost'] for r in rows)} estimated, "
                  f"{sum(r.get('retier') == 'pending' for r in rows)} retier pending")
            for r in rows:
                if "unlisted" in r:
                    print(f"  unlisted: {r['file']}::{r['name']}: {r['unlisted']}")
        return 0
    if a.command == "run":
        changed = changed_paths(ROOT, a.since) if a.changed or a.since else None
        return run_tier(a.tier, a.path, ROOT, a.only, a.test, a.test_threads, a.dry_run, a.serial, not a.no_retry, changed)
    if a.command == "lint":
        problems = lint(a.path, ROOT, a.only)
        for line in problems:
            print(line)
        print(f"{len(problems)} problems" if problems else "the tier tags, the sources and the inventory agree")
        return 1 if problems else 0
    if a.command == "tag":
        for f, n in tag(a.files, a.path).items():
            print(f"{f}: {n} tests changed")
        return 0
    return run_python_file(a.file, a.out)


if __name__ == "__main__":
    sys.exit(main())

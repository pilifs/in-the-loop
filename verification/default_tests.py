#!/usr/bin/env python3
"""The default test run as a verification job: queued at a commit, run by the pipeline in a clean export of it, and
waited on by nobody. The run takes about 16 minutes and a run of /prove-java-change merges and finishes examples
often, so it no longer runs inline there (CLAUDE.md, Tests): it is queued, the work goes on, the watcher reads the
result when it comes in, and a push is where it is required.

    default_tests.py queue [--rev REV] [--why TEXT]   write the job for commit REV (default @-); commit the job file,
                                                      from any workspace, as for any job
    default_tests.py step                             the job's own step, in the export: the default run, unless a
                                                      newer default-run job is queued, which makes this one moot
    default_tests.py last [--rev REV] [--json]        the latest run that covers REV: a passed or failed run at REV or
                                                      at an ancestor that differs from it only in files no test reads
                                                      (the UNTESTED records, and the files the run itself left unread)
    default_tests.py gate [--rev REV]                 exit 0 when such a run passed (sync.py push asks this), 1 with
                                                      what to do otherwise
    default_tests.py failures JOB                     the files a collected run failed at, one per line
    default_tests.py unread JOB                       what a collected run left unread, one path per line (a folder,
                                                      `name/`, stands for everything under it)
    default_tests.py flaky [--json]                   the tests that failed and then passed on their second run, over
                                                      every collected run: how often each, and in which runs

Superseding: of default-run jobs waiting together, only the newest is worth running. The pipeline can't withdraw a
committed job, so each run's step asks the queue first, and one with a newer default-run job pending or running
says so and exits at once (its log says `default tests: superseded by ID`).

What a run read: the step runs in a fresh export of its commit, so afterwards a file's access time says whether
anything in the run (a test, a script or a JVM it started) opened it, and a folder's whether anything listed it. The
step prints the files and whole folders nothing touched (`default tests: unread zlib:...`, the list packed; `default_tests.py unread JOB` prints it), and a run then also covers a
later commit that only modifies such files, or adds and removes files inside such folders: a page no test reads no
longer costs a push another run. lib/ always counts as read (cargo's warm build looks at dates, not contents), and
a filesystem that doesn't keep access times records nothing, which leaves the UNTESTED list alone.

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TITLE = "Default test run at "
CAPABILITY = "tests:default"
MARK = "default tests:"  # the step's verdict line, which `last` reads from a result's log
# Paths whose changes no test reads: a run at an ancestor still covers a commit that differs from it only here.
UNTESTED = ("llm-dlc/traces/", "llm-dlc/index.json", "llm-dlc/decisions/", "verification/results/",
            "verification/jobs/", "verification/findings.md", "llm-dlc/loop-summaries/")
ALWAYS_READ = ("lib/",)  # cargo's warm build decides from dates what to rebuild, without opening an unchanged source
CARGO_TARGET = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "in-the-loop" / "default-tests-target"


def jj(*args: str, cwd: Path = ROOT) -> str:
    r = subprocess.run(["jj", "--quiet", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"jj {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def commit_of(rev: str) -> tuple[str, str, str]:
    """(commit id, change id, first line) of a jj revision."""
    out = jj("log", "--no-graph", "-r", rev, "-T", 'commit_id ++ " " ++ change_id.short(12) ++ " " ++ description.first_line() ++ "\\n"')
    line = out.strip().splitlines()[0] if out.strip() else ""
    if not line:
        raise SystemExit(f"no revision {rev}")
    commit, change, *rest = line.split(" ", 2)
    return commit, change, (rest[0] if rest else "")


def cmd_queue(rev: str, why: str | None) -> int:
    commit, change, line = commit_of(rev)
    description = ("The default test run (python3 lib/tools/test_costs.py run: cargo test and every Python suite, the "
                   f"unit and tool tiers) at change {change}, \"{line[:120]}\""
                   + (f", queued {why}" if why else "") + ". Nobody waits for it: the watcher or the next session reads "
                   "the result, and sync.py push requires a passed run that covers the commit it pushes "
                   "(verification/default_tests.py).")
    argv = [sys.executable, str(ROOT / "verification/pipeline.py"), "submit", "--title", f"{TITLE}{change}",
            "--description", description, "--kind", "other", "--capability", CAPABILITY, "--revision", commit,
            "--link", f"commit:{change}", "--expected", "exits 0: every test of the default run passes",
            "--cpus", "6", "--memory", "4G", "--duration", "25m", "--timeout", "1h", "--requires", "cargo",
            "--estimate-notes", "the default run took about 16 minutes inline in 2026-11 (11 Rust, 5 Python), longer "
                                "beside proof jobs; its cargo target directory is kept warm between runs",
            "--step", "default tests", "nice -n 10 python3 verification/default_tests.py step"]
    return subprocess.run(argv, cwd=ROOT).returncode


def queue_status(root: Path) -> dict:
    r = subprocess.run([sys.executable, str(root / "verification/pipeline.py"), "status", "--json"],
                       cwd=root, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {}


def job_id(row: str) -> str | None:
    m = re.match(r"\s*(\d{8}-\d{6}-\S+)", row)
    return m[1] if m else None


def cmd_step() -> int:
    me = os.environ.get("VERIFY_JOB_ID", "")
    runner_root = Path(os.environ.get("VERIFY_RUNNER_ROOT") or ROOT)
    status = queue_status(runner_root)
    newer = sorted(i for key in ("pending", "running") for row in status.get(key, [])
                   if (i := job_id(row)) and i > me and "-default-test-run-at-" in i)
    if newer:
        print(f"{MARK} superseded by {newer[-1]}: only the newest of the default runs waiting together runs", flush=True)
        return 0
    env = {**os.environ, "CARGO_TARGET_DIR": str(CARGO_TARGET)}
    CARGO_TARGET.mkdir(parents=True, exist_ok=True)
    # Streamed, so the log shows where the run is and the runner sees it is not stalled; kept, to read the verdict.
    p = subprocess.Popen([sys.executable, "lib/tools/test_costs.py", "run"], env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    lines = []
    for line in p.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        lines.append(line)
    code, output = p.wait(), "".join(lines)
    tally = re.findall(r"^default tier: .*$", output, re.M)
    if code == 0 and os.environ.get("VERIFY_SOURCE_COMMIT"):  # in the pipeline's export: what the run left unread
        left = unread(Path.cwd())
        if left is not None:
            print(f"{MARK} unread {pack(left)}", flush=True)
    print(f"{MARK} {'passed' if code == 0 else 'failed'}: {tally[-1] if tally else 'no tally'}", flush=True)
    if code and os.environ.get("VERIFY_SOURCE_COMMIT"):
        bisect(runner_root, os.environ["VERIFY_SOURCE_COMMIT"], output, env)
    return code


# -- what the run read

def _touched(st) -> bool:
    """Whether a file or folder was read (or changed) since it was written: its access time is past its change
    time (relatime moves the access time on the first read after a write), or it was written again."""
    return st.st_atime_ns > st.st_ctime_ns or st.st_mtime_ns >= st.st_ctime_ns


def unread(root: Path) -> list[str] | None:
    """The files of the export ROOT no process opened and the folders (`name/`) no process listed or opened
    anything in, as repository paths: a folder stands for everything under it. None when access times say nothing
    here: this very file, which the step has just run, does not show as read."""
    root = Path(root)
    try:
        if not _touched((root / "verification/default_tests.py").stat()):
            return None
    except OSError:
        return None

    def walk(folder: Path, rel: str) -> tuple[bool, list[str]]:
        """(whether FOLDER is wholly untouched, what is untouched in it when it is not)."""
        try:
            whole = not _touched(folder.stat()) if rel else False  # before listing it, which is itself a read
            entries = sorted(os.scandir(folder), key=lambda e: e.name)
        except OSError:
            return False, []
        left = []
        for e in entries:
            path = f"{rel}{e.name}"
            if any((path + "/").startswith(a) for a in ALWAYS_READ) or e.name in (".git", ".jj", ".state"):
                whole = False
                continue
            if any((path + "/").startswith(u) or path == u for u in UNTESTED):
                continue  # covered whatever the run read: not worth a place in the list
            try:
                if e.is_dir(follow_symlinks=False):
                    sub_whole, sub_left = walk(Path(e.path), path + "/")
                    whole = whole and sub_whole
                    left += [path + "/"] if sub_whole else sub_left
                elif _touched(e.stat(follow_symlinks=False)):
                    whole = False
                else:
                    left.append(path)
            except OSError:
                whole = False
        return whole, left

    # Listing a folder here moves its access time too, but each folder is judged (stat) before it is listed.
    return walk(root, "")[1]


def pack(paths: list[str]) -> str:
    """A list of paths as one short word for a log line: a real run leaves some 500 unread, 40 kB as they stand and
    a quarter of that so. `default_tests.py unread JOB` prints them."""
    import base64
    import zlib
    return "zlib:" + base64.b64encode(zlib.compress(json.dumps(paths).encode(), 9)).decode()


def unpack(word: str) -> list[str]:
    """The paths `pack` wrote; nothing from anything else."""
    import base64
    import binascii
    import zlib
    if not word.startswith("zlib:"):
        return []
    try:
        paths = json.loads(zlib.decompress(base64.b64decode(word[5:], validate=True)))
    except (ValueError, zlib.error, binascii.Error):
        return []
    return [p for p in paths if isinstance(p, str)] if isinstance(paths, list) else []


def left_unread(unread_paths: list[str], status: str, path: str) -> bool:
    """Whether a change to PATH (STATUS: M, A or D, as `jj diff --summary` says) is one the run could not have seen:
    a modified file it left unread, or a file added or removed inside a folder it never listed."""
    if any(path.startswith(a) for a in ALWAYS_READ):
        return False
    inside = any(u.endswith("/") and path.startswith(u) for u in unread_paths)
    return inside or (status == "M" and path in unread_paths)


# -- which commit broke it

BISECT_SECONDS = 20 * 60  # within the job's hour: what a failure's culprit is worth waiting for


def failing(output: str) -> tuple[list[str], list[str]]:
    """(the Python test files, the Rust tests by name) a default run's output says failed, flaky ones apart."""
    failed = failures_in(output)
    files = [f for f in failed if f != "cargo test"]
    rust = sorted(set(re.findall(r"^test (\S+) \.\.\. FAILED$", output, re.M))) if "cargo test" in failed else []
    return files, rust


def fails_at(runner_root: Path, commit: str, files: list[str], rust: list[str], env: dict) -> set[str]:
    """Which of these failing tests fail at COMMIT, run in an export of it: a Python file whole, the Rust tests by
    name (with the warm cargo target directory, so a commit builds only what changed)."""
    import tarfile
    import tempfile
    failed = set()
    with tempfile.TemporaryDirectory(prefix="bisect-") as tmp:
        archive = subprocess.run(["git", "-C", str(runner_root), "archive", "--format=tar", commit], capture_output=True)
        if archive.returncode:
            return set(files) | ({"cargo test"} if rust else set())  # can't look: counts as failing, so it says less
        import io
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as t:
            t.extractall(tmp, filter="data")
        root = Path(tmp)
        sys.path.insert(0, str(root / "lib/tools"))
        try:
            import importlib
            import test_costs
            importlib.reload(test_costs)
            doc = json.loads((root / "lib/tests/costs.json").read_text())
            for label, argv, run_env, cwd in test_costs.tier_runs("default", doc, root):
                if label in files:
                    if subprocess.run(argv, env={**env, **run_env}, cwd=cwd, capture_output=True).returncode:
                        failed.add(label)
                elif label == "cargo test" and rust:
                    cut = argv.index("--") if "--" in argv else len(argv)
                    r = subprocess.run(argv[:cut] + ["--", *argv[cut + 1:], "--exact", *rust], env={**env, **run_env},
                                       cwd=cwd, capture_output=True)
                    if r.returncode:
                        failed.add("cargo test")
        except (OSError, ValueError, ImportError):
            return set(files) | ({"cargo test"} if rust else set())
        finally:
            sys.path.remove(str(root / "lib/tools"))
    return failed


def bisect(runner_root: Path, commit: str, output: str, env: dict) -> None:
    """For each test that failed at COMMIT, the first commit it fails at since the last passed default run: the
    first-parent commits between, halved until one is left or the time is up. Each finding is a line,
    `default tests: culprit TEST: COMMIT` or `default tests: culprit TEST: between A and B`, for the watcher."""
    import time
    files, rust = failing(output)
    tests = files + (["cargo test"] if rust else [])
    passed = next((r["commit"] for r in runs(runner_root) if r["verdict"] == "passed" and r["commit"]), None)
    if not tests or not passed:
        print(f"{MARK} no culprit sought: {'no passed run to start from' if tests else 'no failing test named'}", flush=True)
        return
    listed = subprocess.run(["git", "-C", str(runner_root), "rev-list", "--first-parent", "--reverse", f"{passed}..{commit}"],
                            capture_output=True, text=True)
    commits = listed.stdout.split() if listed.returncode == 0 else []
    if commit not in commits:
        print(f"{MARK} no culprit sought: the last passed run ({passed[:12]}) is not on {commit[:12]}'s first-parent line",
              flush=True)
        return
    until = time.monotonic() + BISECT_SECONDS
    for test in tests:
        low, high = -1, len(commits) - 1  # passes at low (the passed run), fails at high
        while high - low > 1 and time.monotonic() < until:
            mid = (low + high) // 2
            if test in fails_at(runner_root, commits[mid], [t for t in files if t == test],
                                rust if test == "cargo test" else [], env):
                high = mid
            else:
                low = mid
        where = commits[high][:12] if high - low == 1 else f"between {(commits[low] if low >= 0 else passed)[:12]} and {commits[high][:12]}"
        print(f"{MARK} culprit {test}: {where}", flush=True)


# -- reading the runs that have come in

def runs(root: Path = ROOT) -> list[dict]:
    """Every collected default run, newest first: its job, the commit it ran at, and its verdict from its log."""
    out = []
    results = root / "verification/results"
    for d in sorted(results.glob("*-default-test-run-at-*"), reverse=True):
        try:
            result = json.loads((d / "result.json").read_text())
        except (OSError, ValueError):
            continue
        logs = sorted((d / "logs").glob("*.log")) if (d / "logs").exists() else []
        text = "".join(p.read_text(errors="replace") for p in logs)
        marks = re.findall(rf"^{re.escape(MARK)} (\w+)(.*)$", text, re.M)
        marks = [m for m in marks if m[0] in ("passed", "failed", "superseded")]
        verdict = marks[-1][0] if marks else ("failed" if result.get("status") != "passed" else "unknown")
        out.append({"job": d.name, "commit": result.get("sourceCommit"), "status": result.get("status"),
                    "verdict": verdict, "tally": marks[-1][1].strip(": ") if marks else None,
                    "failed": failures_in(text),
                    "flaky": flaky_in(text),
                    "flakyTests": flaky_tests_in(text),
                    "unread": unread_in(text),
                    "culprits": dict(re.findall(rf"^{re.escape(MARK)} culprit (.+?): (.+)$", text, re.M))})
    return out


def unread_in(text: str) -> list[str]:
    """What a run's step said it left unread; nothing when it said nothing, or nothing `unpack` reads."""
    found = re.findall(rf"^{re.escape(MARK)} unread (\S+)$", text, re.M)
    return unpack(found[-1]) if found else []


def flaky_in(text: str) -> list[str]:
    """What failed and then passed on its second run, from the tally line."""
    tally = re.findall(r"^default tier: \d+ of \d+ passed(.*)$", text, re.M)
    m = re.search(r"; flaky: ([^;]+)", tally[-1]) if tally else None
    return [f.strip() for f in m[1].split(",")] if m else []


def flaky_tests_in(text: str) -> list[str]:
    """The tests a run's FLAKY lines name: a Python test file, or each Rust test by name (`cargo test: a::b`)."""
    out = []
    for what in re.findall(r"^FLAKY (.+?) \(failed, then passed on a second run\)$", text, re.M):
        if what.startswith("cargo test: "):
            out += [f"cargo test: {name.strip()}" for name in what[len("cargo test: "):].split(",")]
        else:
            out.append(what.split(": ")[0])
    return list(dict.fromkeys(out))


def flaky_record(all_runs: list[dict]) -> list[dict]:
    """Over the runs that ran (not the superseded): each flaky test, the runs it was flaky in, and of how many;
    the most often first. A test here twice is no longer noise: it is worth a fix, or a mark for a person to give."""
    ran = [r for r in all_runs if r["verdict"] in ("passed", "failed")]
    seen: dict[str, list[str]] = {}
    for r in ran:
        for test in r.get("flakyTests", []):
            seen.setdefault(test, []).append(r["job"])
    return sorted(({"test": t, "runs": sorted(jobs), "of": len(ran)} for t, jobs in seen.items()),
                  key=lambda e: (-len(e["runs"]), e["test"]))


def cmd_flaky(as_json: bool) -> int:
    record = flaky_record(runs())
    if as_json:
        print(json.dumps(record, indent=1))
        return 0
    for e in record:
        print(f"{e['test']}: flaky in {len(e['runs'])} of {e['of']} runs"
              + (" (repeats: fix it, or ask for a mark)" if len(e["runs"]) > 1 else "") + f"; last in {e['runs'][-1]}")
    if not record:
        print("no test was flaky in a collected run")
    return 0


def failures_in(text: str) -> list[str]:
    """What a run failed at, from its tally line (`... passed; failed: A, B; flaky: C`), which counts a test that
    passed on its second run as passed; from the FAIL lines and cargo's summary when there is no tally."""
    tally = re.findall(r"^default tier: \d+ of \d+ passed(.*)$", text, re.M)
    if tally:
        m = re.search(r"; failed: ([^;]+)", tally[-1])
        return [f.strip() for f in m[1].split(",")] if m else []
    files = re.findall(r"^FAIL (\S+?):", text, re.M)
    if re.search(r"^test result: FAILED", text, re.M) or re.search(r"^error: test failed", text, re.M):
        files.insert(0, "cargo test")
    return list(dict.fromkeys(files))


def covers(run_commit: str, target: str, unread_paths: list[str] | tuple = ()) -> bool:
    """A run at RUN_COMMIT covers TARGET when it is TARGET, or an ancestor that differs from it only in UNTESTED and
    in what the run left unread (UNREAD_PATHS, from its log): modified files it never opened, and files added or
    removed in folders it never listed."""
    if not run_commit:
        return False
    if run_commit == target:
        return True
    r = subprocess.run(["jj", "--quiet", "log", "--no-graph", "-r", f"{run_commit} & ::{target}", "-T", "commit_id"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode or not r.stdout.strip():
        return False
    for line in jj("diff", "--from", run_commit, "--to", target, "--summary").splitlines():
        status, _, path = line.partition(" ")
        if not path:
            continue
        if any(p.startswith(u) or p == u.rstrip("/") for p in [path] for u in UNTESTED):
            continue
        # A rename or a copy is written `R {old => new}`: two paths, and nothing here reads that form, so it is not
        # covered (a record that moves is rare, and another run is the safe answer).
        if status not in ("M", "A", "D") or not left_unread(list(unread_paths), status, path):
            return False
    return True


def last(rev: str) -> dict | None:
    target, _, _ = commit_of(rev)
    for r in runs():
        if r["verdict"] in ("passed", "failed") and covers(r["commit"], target, r["unread"]):
            return r
    return None


def cmd_last(rev: str, as_json: bool) -> int:
    r = last(rev)
    if as_json:  # the unread paths as their count: `unread JOB` lists them
        print(json.dumps(r and {**r, "unread": len(r["unread"])}, indent=1))
    elif r is None:
        print(f"no default run covers {rev}")
    else:
        print(f"{r['job']}: {r['verdict']} at {r['commit'][:12]} ({r['tally']})"
              + (f"; failed: {', '.join(r['failed'])}" if r["failed"] else ""))
    return 0 if r else 1


def cmd_gate(rev: str) -> int:
    r = last(rev)
    if r and r["verdict"] == "passed":
        print(f"the default run passed for {rev}: {r['job']} at {r['commit'][:12]}")
        return 0
    if r:
        print(f"the latest default run covering {rev} failed ({r['job']}: {', '.join(r['failed']) or r['tally']}): "
              "fix it, and queue another (python3 verification/default_tests.py queue)", file=sys.stderr)
    else:
        print(f"no passed default run covers {rev}: queue one (python3 verification/default_tests.py queue, commit "
              "the job) and push once it has passed, or run python3 lib/tools/test_costs.py run here first",
              file=sys.stderr)
    return 1


def cmd_failures(job: str, what: str = "failed") -> int:
    for r in runs():
        if r["job"] == job:
            print("\n".join(r[what]))
            return 0
    print(f"no collected default run {job}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    q = sub.add_parser("queue")
    q.add_argument("--rev", default="@-")
    q.add_argument("--why")
    sub.add_parser("step")
    la = sub.add_parser("last")
    la.add_argument("--rev", default="@-")
    la.add_argument("--json", action="store_true")
    g = sub.add_parser("gate")
    g.add_argument("--rev", default="@-")
    f = sub.add_parser("failures")
    f.add_argument("job")
    un = sub.add_parser("unread")
    un.add_argument("job")
    fl = sub.add_parser("flaky")
    fl.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.command == "queue":
        return cmd_queue(a.rev, a.why)
    if a.command == "step":
        return cmd_step()
    if a.command == "last":
        return cmd_last(a.rev, a.json)
    if a.command == "gate":
        return cmd_gate(a.rev)
    if a.command == "flaky":
        return cmd_flaky(a.json)
    return cmd_failures(a.job, "unread" if a.command == "unread" else "failed")


if __name__ == "__main__":
    sys.exit(main())

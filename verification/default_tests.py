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
    default_tests.py gate [--rev REV]                 exit 0 when such a run passed (sync.py push asks this), 1 with
                                                      what to do otherwise
    default_tests.py failures JOB                     the files a collected run failed at, one per line

Superseding: of default-run jobs waiting together, only the newest is worth running. The pipeline can't withdraw a
committed job, so each run's step asks the queue first, and one with a newer default-run job pending or running
says so and exits at once (its log says `default tests: superseded by ID`).

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
    p = subprocess.run([sys.executable, "lib/tools/test_costs.py", "run"], env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True)
    sys.stdout.write(p.stdout)
    tally = re.findall(r"^default tier: .*$", p.stdout, re.M)
    print(f"{MARK} {'passed' if p.returncode == 0 else 'failed'}: {tally[-1] if tally else 'no tally'}", flush=True)
    return p.returncode


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
        verdict = marks[-1][0] if marks else ("failed" if result.get("status") != "passed" else "unknown")
        out.append({"job": d.name, "commit": result.get("sourceCommit"), "status": result.get("status"),
                    "verdict": verdict, "tally": marks[-1][1].strip(": ") if marks else None,
                    "failed": failures_in(text)})
    return out


def failures_in(text: str) -> list[str]:
    files = re.findall(r"^FAIL (\S+?):", text, re.M)
    if re.search(r"^test result: FAILED", text, re.M) or re.search(r"^error: test failed", text, re.M):
        files.insert(0, "cargo test")
    return list(dict.fromkeys(files))


def covers(run_commit: str, target: str) -> bool:
    """A run at RUN_COMMIT covers TARGET when it is TARGET, or an ancestor that differs from it only in UNTESTED."""
    if not run_commit:
        return False
    if run_commit == target:
        return True
    r = subprocess.run(["jj", "--quiet", "log", "--no-graph", "-r", f"{run_commit} & ::{target}", "-T", "commit_id"],
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode or not r.stdout.strip():
        return False
    changed = jj("diff", "--from", run_commit, "--to", target, "--name-only").split()
    return all(any(p.startswith(u) or p == u.rstrip("/") for u in UNTESTED) for p in changed)


def last(rev: str) -> dict | None:
    target, _, _ = commit_of(rev)
    for r in runs():
        if r["verdict"] in ("passed", "failed") and covers(r["commit"], target):
            return r
    return None


def cmd_last(rev: str, as_json: bool) -> int:
    r = last(rev)
    if as_json:
        print(json.dumps(r, indent=1))
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


def cmd_failures(job: str) -> int:
    for r in runs():
        if r["job"] == job:
            print("\n".join(r["failed"]))
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
    a = ap.parse_args(argv)
    if a.command == "queue":
        return cmd_queue(a.rev, a.why)
    if a.command == "step":
        return cmd_step()
    if a.command == "last":
        return cmd_last(a.rev, a.json)
    if a.command == "gate":
        return cmd_gate(a.rev)
    return cmd_failures(a.job)


if __name__ == "__main__":
    sys.exit(main())

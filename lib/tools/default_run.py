#!/usr/bin/env python3
"""The default test run's record, and the gate a push and a release ask.

The default run (`python3 lib/tools/test_costs.py run`, the unit and tool tiers) runs inline, in the working copy
(CLAUDE.md, Tests). When it passes, `test_costs.py run` writes the tree it tested to RECORD, outside the repository:
the git tree of `@` as jj snapshots it when the run starts, written only when the tree is the same when it ends, so
an edit made during the run leaves no record. A record covers a commit whose tree is the same, or differs from it
only in UNTESTED, files no test reads (traces, decisions, job results). The record is shared by the workspaces of
one machine: a run in one workspace covers the same tree in another.

    default_run.py last [--rev REV]          the latest passed run that covers REV (default @-)
    default_run.py gate [--rev REV] [--run]  exit 0 when one does (sync.py push and release.py cut ask this); with
                                             --run, a default run is started here when none does, and asked again

One at a time: two runs in one workspace share cargo's target directory and the tests' work folders under it, and
overwrite what the other is reading (VF-034: two at once failed Rust tests that pass alone). `test_costs.py run`
holds `lock()` while it runs, and a second run waits for it.

Standard library only.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "in-the-loop"
RECORD = CACHE / "default-runs.jsonl"
KEPT = 200  # records kept, the newest
MARK = "default run:"
# Paths whose changes no test reads: a record still covers a commit that differs from its tree only here.
UNTESTED = ("llm-dlc/traces/", "llm-dlc/index.json", "llm-dlc/decisions/", "verification/results/",
            "verification/jobs/", "verification/findings.md", "llm-dlc/loop-summaries/")


def _out(cmd: list[str], cwd: Path) -> str | None:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    except OSError:
        return None
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def tree_of(rev: str, root: Path = ROOT) -> tuple[str, str] | None:
    """(the git tree of REV, its commit), or None outside a jj checkout. `@` is snapshotted first, as any jj command
    does, so its tree holds the working copy's files. Only at a workspace's own root: a tree exported inside one (a
    job's, under verification/.state) must not snapshot the workspace around it."""
    if not (root / ".jj").exists():
        return None
    commit =_out(["jj", "--quiet", "log", "--no-graph", "-r", rev, "-T", "commit_id"], root)
    tree = commit and _out(["git", "rev-parse", f"{commit}^{{tree}}"], root)
    return (tree, commit) if tree else None


def untested(path: str) -> bool:
    """Whether PATH is in UNTESTED: under one of its folders (`name/`), or one of its files exactly."""
    return any(path.startswith(u) if u.endswith("/") else path == u for u in UNTESTED)


def covers(run_tree: str, target_tree: str, root: Path = ROOT) -> bool:
    """A run of RUN_TREE covers TARGET_TREE when they are the same, or differ only in UNTESTED."""
    if run_tree == target_tree:
        return True
    names = _out(["git", "diff", "--name-only", "--no-renames", run_tree, target_tree], root)
    return names is not None and all(untested(p) for p in names.splitlines())


def records(path: Path = RECORD) -> list[dict]:
    """The passed runs recorded, newest last."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def record(tree: str, commit: str, tally: str, root: Path = ROOT, path: Path = RECORD) -> None:
    entry = {"tree": tree, "commit": commit, "root": str(root), "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
             "tally": tally}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        kept = records(path)[-(KEPT - 1):] + [entry]
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text("".join(json.dumps(e) + "\n" for e in kept))
        tmp.replace(path)
    except OSError as e:
        print(f"{MARK} the record could not be written ({e})", flush=True)


def last(rev: str = "@-", root: Path = ROOT, path: Path = RECORD) -> dict | None:
    target = tree_of(rev, root)
    if target is None:
        return None
    for r in reversed(records(path)):
        if covers(r["tree"], target[0], root):
            return r
    return None


class Started:
    """What `started()` saw: the tree a run began on, checked again when it ends."""

    def __init__(self, root: Path = ROOT):
        self.root = root
        self.at = tree_of("@", root)

    def passed(self, tally: str, path: Path = RECORD) -> None:
        if self.at is None:
            return
        now = tree_of("@", self.root)
        if now is None or now[0] != self.at[0]:
            print(f"{MARK} not recorded: the working copy changed during the run", flush=True)
            return
        record(self.at[0], self.at[1], tally, self.root, path)
        print(f"{MARK} recorded as passed for tree {self.at[0][:12]}", flush=True)


def lock(root: Path = ROOT):
    """An exclusive lock a run holds while it runs, in cargo's target directory; a second run waits for it. The lock
    is the open file: it goes when the run ends, however it ends."""
    target = Path(os.environ.get("CARGO_TARGET_DIR") or root / "lib" / "target")
    target.mkdir(parents=True, exist_ok=True)
    held = open(target / "test-run.lock", "w")
    try:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(f"{MARK} waiting: another test run holds {held.name}; one runs at a time", flush=True)
        fcntl.flock(held, fcntl.LOCK_EX)
    return held


def gate(rev: str = "@-", run: bool = False, root: Path = ROOT) -> tuple[bool, str]:
    """(whether a passed default run covers REV, what to say). With RUN, one is started when none does."""
    r = last(rev, root)
    if r is None and run:
        print(f"no passed default run covers {rev}: running it now (python3 lib/tools/test_costs.py run)",
              file=sys.stderr, flush=True)
        subprocess.run([sys.executable, str(root / "lib/tools/test_costs.py"), "run"], cwd=root)
        r = last(rev, root)
    if r:
        return True, f"the default run passed for {rev}: tree {r['tree'][:12]}, {r['when']} ({r['tally']})"
    return False, (f"no passed default run covers {rev}: run python3 lib/tools/test_costs.py run with nothing "
                   "uncommitted, and fix what fails")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    la = sub.add_parser("last")
    la.add_argument("--rev", default="@-")
    g = sub.add_parser("gate")
    g.add_argument("--rev", default="@-")
    g.add_argument("--run", action="store_true", help="start a default run here when none covers REV")
    a = ap.parse_args(argv)
    if a.command == "last":
        r = last(a.rev)
        print(json.dumps(r, indent=1) if r else f"no passed default run covers {a.rev}")
        return 0 if r else 1
    ok, said = gate(a.rev, a.run)
    print(said, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Put a jj workspace right after another session's operation met its own (CLAUDE.md).

Several sessions share one repository, each in a workspace of its own or two in one, and each runs jj. When two
operations happen at once, jj joins them, and a workspace can come out of it in one of two states:

  stale      every jj command there refuses: "The working copy is stale". `jj workspace update-stale` cures it, but
             it sets the files on disk to the commit jj has, and what was edited and not yet committed is then only
             in a second copy of the working-copy change that jj leaves beside it (a divergent change).
  divergent  nothing refuses, the files on disk are whole, but the working-copy change has such a second copy, an
             older snapshot of the same edits, and every later command that names the change by its id trips on it.

    unstale.py [--check]

From the workspace's root. It says which state it found. For a stale one it first saves every file changed since
jj last looked (a tar in the scratch directory it names), runs `jj workspace update-stale`, and takes the edits
back from the second copy, file by file: only the files that copy had changed, so nothing the new parent brought
is undone. Then, in either state, it abandons the second copy. --check only says what it found (exit 1 if
anything is to do). A workspace that is neither is left alone.

Two copies that each hold edits the other lacks can't be told apart by a script: it then stops and says so.

Standard library only.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

SKIP = {".jj", ".git", "target", "__pycache__", "node_modules", ".state"}  # never part of an edit worth saving
LIMIT = 200 << 20  # bytes of files a backup takes


def jj(where: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["jj", *args], cwd=where, capture_output=True, text=True)


def is_stale(where: Path) -> bool:
    return "working copy is stale" in jj(where, "status").stderr


def siblings(where: Path) -> list[str]:
    """The other visible commits of the working-copy change: its divergent copies."""
    r = jj(where, "log", "--no-graph", "-r", "@", "-T", 'change_id ++ " " ++ commit_id')
    if r.returncode != 0 or not r.stdout.strip():
        return []
    change, mine = r.stdout.split()
    listed = jj(where, "log", "--no-graph", "-r", f"change_id({change})", "-T", 'commit_id ++ "\\n"').stdout.split()
    return [c for c in listed if c != mine]


def changed(where: Path, rev: str) -> set[str]:
    return set(jj(where, "diff", "-r", rev, "--name-only").stdout.splitlines())


def backup(where: Path) -> Path | None:
    """The files written since jj last recorded the working copy, as a tar outside the repository."""
    try:
        since = (where / ".jj" / "working_copy" / "tree_state").stat().st_mtime
    except OSError:
        return None
    found, size = [], 0
    for folder, dirs, files in os.walk(where):
        dirs[:] = [d for d in dirs if d not in SKIP]
        for name in files:
            path = Path(folder) / name
            try:
                st = path.stat()
            except OSError:
                continue
            if st.st_mtime >= since - 1 and size + st.st_size <= LIMIT:
                found.append(path)
                size += st.st_size
    if not found:
        return None
    out = Path(tempfile.mkdtemp(prefix="unstale-")) / f"{where.name}-{time.strftime('%Y%m%d-%H%M%S')}.tar"
    with tarfile.open(out, "w") as tar:
        for path in found:
            tar.add(path, arcname=str(path.relative_to(where)))
    return out


def recover(where: Path, check: bool = False) -> tuple[int, list[str]]:
    said = []
    stale = is_stale(where)
    if not stale and not siblings(where):
        return 0, ["the working copy is neither stale nor divergent: nothing to do"]
    if check:
        return 1, ["stale: jj refuses until `jj workspace update-stale`, which resets the files on disk" if stale else
                   "divergent: the working-copy change has a second copy"]
    if stale:
        saved = backup(where)
        said.append(f"saved the files changed since jj last looked: {saved}" if saved else "no file changed since jj last looked")
        r = jj(where, "workspace", "update-stale")
        if r.returncode != 0:
            return 1, said + [f"jj workspace update-stale failed: {r.stderr.strip()}"]
        said.append("ran jj workspace update-stale")
    others = siblings(where)
    if len(others) > 1:
        return 1, said + [f"the working-copy change has {len(others) + 1} copies: compare them by hand (jj log -r 'change_id(@)')"]
    for other in others:
        theirs, mine = changed(where, other), changed(where, "@")
        if stale:
            if theirs:
                r = jj(where, "restore", "--from", other, "--", *sorted(theirs))
                if r.returncode != 0:
                    return 1, said + [f"could not take the edits back from {other[:12]}: {r.stderr.strip()}"]
                said.append(f"took {len(theirs)} edited file(s) back from the copy jj kept: {' '.join(sorted(theirs)[:12])}")
        elif not theirs <= mine:
            return 1, said + [f"the copy {other[:12]} changes files the working copy doesn't ({' '.join(sorted(theirs - mine)[:8])}): "
                              f"compare them by hand before abandoning either"]
        jj(where, "abandon", other)
        said.append(f"abandoned the second copy {other[:12]}")
    return 0, said


def main(argv: list[str]) -> int:
    if argv not in ([], ["--check"]):
        print("usage: unstale.py [--check]", file=sys.stderr)
        return 2
    code, said = recover(Path.cwd(), check=bool(argv))
    print("\n".join(said))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""The /prove-java-change skill's bootstrap: the release of in-the-loop this copy of the skill is pinned to, on
this machine (llm-dlc/runtime.md in the repository has the whole picture).

    bootstrap.py status           where things stand, as JSON; exits 0 whatever it finds
    bootstrap.py install          clone the repository into the home and stand on the pinned release
    bootstrap.py update           fetch, find the pinned release, and move the local work on top of it
    bootstrap.py digest [REV]     the digest of a revision's tree in the home (what a release records)

The pin is release.json beside this file: a version and the sha256 digest of the release's tree. The skill and the
repository are released together, in one commit, so the pin can't name that commit's id. It names its content
instead: the digest covers every file of the commit except the pin itself and the trace files the repository
regenerates on each of its own commits (the pin lists what is left out). A release is found by looking through
the history of the pin for the commit that carries this version and digest, and it is accepted only when that
commit's tree hashes to the digest again here. A runtime checkout is then also held to this copy of the skill:
the skill's files in the release must be the bytes that are running.

Two modes:
  development  this file is inside a development checkout of the repository (reached through
               .claude/skills/prove-java-change). There is nothing to install: the checkout is the home.
  runtime      this file is an installed plugin. The home is $IN_THE_LOOP_HOME, by default
               ~/.local/share/in-the-loop: a jj checkout (colocated with git) standing on the pinned release, marked
               as a runtime checkout by .in-the-loop-runtime.json at its root, with the user's examples and any
               change to the library as commits on top.

Settings: IN_THE_LOOP_HOME (the checkout), IN_THE_LOOP_REPOSITORY (default the pin's repository) and IN_THE_LOOP_REF
(default the pin's ref, `main`): a release cut on another branch, or in a local clone, is installed by naming it.

Standard library only; it needs git and jj on PATH.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIN = HERE / "release.json"
PIN_SCHEMA = "in-the-loop-release/v1"
PIN_PATH = "plugins/in-the-loop/skills/prove-java-change/release.json"  # the pin's place in the repository
SKILL_PATH = "plugins/in-the-loop/skills/prove-java-change"
MARKER = ".in-the-loop-runtime.json"
MARKER_SCHEMA = "in-the-loop-runtime/v1"
# Left out of a digest: the pin, which can't hold its own hash, and what sync.py rewrites on every commit of a
# development checkout (its trace_owned()), which would otherwise change the tree after the digest was taken.
EXCLUDED = (PIN_PATH, "llm-dlc/traces/", "llm-dlc/index.json", "llm-dlc/README.md")


class Problem(Exception):
    """What stops the bootstrap, with what it needs. Printed as JSON; never a traceback for a missing tool."""

    def __init__(self, what: str, needs: str) -> None:
        super().__init__(what)
        self.what, self.needs = what, needs


def run(*argv: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise Problem(f"`{' '.join(argv)}` exited {r.returncode}: {(r.stderr or r.stdout).strip()[-600:]}",
                      "read the message; nothing after this step was done")
    return r


def git(repo: Path, *args: str, check: bool = True) -> str:
    return run("git", "-C", str(repo), *args, check=check).stdout


def jj(repo: Path, *args: str, check: bool = True) -> str:
    return run("jj", "--quiet", "-R", str(repo), *args, check=check).stdout


def load_pin(path: Path = PIN) -> dict:
    try:
        pin = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise Problem(f"the skill's pin {path} can't be read ({e})", "reinstall the plugin: the skill ships with its pin")
    if pin.get("schema") != PIN_SCHEMA or not all(isinstance(pin.get(k), str) for k in ("version", "digest")):
        raise Problem(f"{path} is not a {PIN_SCHEMA} pin", "reinstall the plugin")
    return pin


def left_out(path: str, excluded) -> bool:
    return any(path == e or (e.endswith("/") and path.startswith(e)) for e in excluded)


def tree_digest(repo: Path, rev: str, excluded=EXCLUDED) -> tuple[str, int]:
    """(digest, files) of a revision's tree: the sha256 over one line per file, `MODE SHA256 PATH`, in path
    order, each file's sha256 taken over its bytes as git stores them (a link's target; a submodule's commit).
    Content only: a commit's message, author and parents don't enter it, so the trace lines sync.py adds to a
    message later leave a release's digest as it was."""
    entries = []
    for record in git(repo, "ls-tree", "-r", "-z", "--full-tree", rev).split("\0"):
        if not record:
            continue
        meta, path = record.split("\t", 1)
        mode, kind, oid = meta.split()
        if not left_out(path, excluded):
            entries.append((path, mode, kind, oid))
    blobs = [e for e in entries if e[2] == "blob"]
    hashes: dict[str, str] = {}
    proc = subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def feed() -> None:  # in a thread: git answers while it is still being asked, and a full pipe would stop both
        for oid in dict.fromkeys(e[3] for e in blobs):
            proc.stdin.write(oid.encode() + b"\n")
        proc.stdin.close()

    feeder = threading.Thread(target=feed, daemon=True)
    feeder.start()
    for _ in range(len({e[3] for e in blobs})):
        header = proc.stdout.readline().split()
        if len(header) != 3 or header[1] != b"blob":
            proc.kill()
            raise Problem(f"git could not read an object of {rev} ({b' '.join(header).decode(errors='replace')})",
                          "a complete clone of the repository")
        h, left = hashlib.sha256(), int(header[2])
        while left:
            chunk = proc.stdout.read(min(left, 1 << 20))
            if not chunk:
                proc.kill()
                raise Problem(f"git stopped while reading {header[0].decode()}", "a complete clone of the repository")
            h.update(chunk)
            left -= len(chunk)
        proc.stdout.read(1)  # the newline after each object
        hashes[header[0].decode()] = h.hexdigest()
    feeder.join()
    proc.stdout.close()
    proc.wait()
    total = hashlib.sha256()
    for path, mode, kind, oid in sorted(entries):
        total.update(f"{mode} {hashes[oid] if kind == 'blob' else f'{kind}:{oid}'} {path}\n".encode())
    return total.hexdigest(), len(entries)


def find_release(repo: Path, pin: dict, tip: str) -> tuple[str | None, list[str]]:
    """(commit, why not) for the pinned release in the history of `tip`: the commit that carries this pin, whose
    tree hashes to its digest here. Only commits that changed the pin are looked at, newest first."""
    seen = []
    for commit in git(repo, "log", "--format=%H", tip, "--", PIN_PATH).split():
        try:
            there = json.loads(git(repo, "show", f"{commit}:{PIN_PATH}"))
        except (Problem, ValueError):
            continue
        if there.get("version") != pin["version"] or there.get("digest") != pin["digest"]:
            seen.append(f"{commit[:12]} is release {there.get('version')}")
            continue
        digest, _ = tree_digest(repo, commit, pin.get("excluded", EXCLUDED))
        if digest == pin["digest"]:
            return commit, seen
        seen.append(f"{commit[:12]} carries the pin of {pin['version']} but its tree hashes to {digest[:16]}…, not "
                    f"{pin['digest'][:16]}…: something changed in the commit after the release was cut")
    return None, seen


def development_root() -> Path | None:
    """The checkout this file is part of, when it is one (SKILL_PATH under its root)."""
    depth = len(Path(SKILL_PATH).parts)
    if len(HERE.parents) < depth:
        return None
    root = HERE.parents[depth - 1]
    return root if (root / "llm-dlc" / "tools" / "sync.py").is_file() and (root / SKILL_PATH) == HERE else None


def home() -> Path:
    if os.environ.get("IN_THE_LOOP_HOME"):
        return Path(os.environ["IN_THE_LOOP_HOME"]).expanduser().resolve()
    data = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return data / "in-the-loop"


def read_marker(root: Path) -> dict | None:
    try:
        m = json.loads((root / MARKER).read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {"schema": "unreadable"}
    return m if isinstance(m, dict) else {"schema": "unreadable"}


def skill_differences(repo: Path, commit: str) -> list[str]:
    """The files of this copy of the skill that are not the release's, and the release's that are missing here."""
    theirs = {}
    for record in git(repo, "ls-tree", "-r", "-z", "--full-tree", commit, "--", SKILL_PATH).split("\0"):
        if record:
            meta, path = record.split("\t", 1)
            theirs[path[len(SKILL_PATH) + 1:]] = meta.split()[2]
    mine = {str(p.relative_to(HERE)): p for p in HERE.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.name != ".DS_Store"}
    different = [f"{name}: not in the release" for name in sorted(set(mine) - set(theirs))]
    different += [f"{name}: missing here" for name in sorted(set(theirs) - set(mine))]
    for name in sorted(set(mine) & set(theirs)):
        blob = hashlib.sha1(b"blob %d\0" % mine[name].stat().st_size + mine[name].read_bytes()).hexdigest()
        if blob != theirs[name]:
            different.append(f"{name}: differs from the release's")
    return different


def status() -> dict:
    """Where things stand. `state` is one of: development (nothing to install), absent, current, outdated (another
    release is installed: update), or broken, with `blockers` saying what is wrong; `needs` lists missing tools."""
    needs = [t for t in ("git", "jj") if not shutil.which(t)]
    dev = development_root()
    if dev is not None and read_marker(dev) is None:
        try:  # a development checkout has a pin only once a release has been cut in its history
            pin = load_pin()
            skill = {"version": pin["version"], "digest": pin["digest"], "path": str(HERE)}
        except Problem:
            skill = None
        return {"skill": skill, "needs": needs, "blockers": [], "mode": "development", "home": str(dev),
                "state": "development",
                "note": "a development checkout: stage 1 of the skill doesn't apply; work in this checkout"}
    pin = load_pin()
    out = {"skill": {"version": pin["version"], "digest": pin["digest"], "path": str(HERE)}, "needs": needs,
           "blockers": []}
    root = dev if dev is not None else home()
    out.update(mode="runtime", home=str(root))
    marker = read_marker(root)
    if marker is None:
        if root.exists() and any(root.iterdir()):
            return {**out, "state": "broken",
                    "blockers": [f"{root} exists, is not empty and has no {MARKER}: not a checkout this bootstrap made"]}
        return {**out, "state": "absent"}
    out["installed"] = {k: marker.get(k) for k in ("version", "digest", "commit", "repository", "ref", "installed")}
    if marker.get("schema") != MARKER_SCHEMA or out["needs"]:
        blockers = [f"{root / MARKER} is not a {MARKER_SCHEMA} marker"] if marker.get("schema") != MARKER_SCHEMA else []
        return {**out, "state": "broken", "blockers": blockers + [f"{t} is not on PATH" for t in out["needs"]]}
    if (marker.get("version"), marker.get("digest")) != (pin["version"], pin["digest"]):
        return {**out, "state": "outdated"}
    blockers = []
    commit = marker.get("commit") or ""
    if git(root, "cat-file", "-t", commit, check=False).strip() != "commit":
        blockers.append(f"the release commit {commit[:12]} is not in the checkout")
    else:
        digest, files = tree_digest(root, commit, pin.get("excluded", EXCLUDED))
        out["installed"]["files"] = files
        if digest != pin["digest"]:
            blockers.append(f"the release commit {commit[:12]} hashes to {digest}, not the pin's {pin['digest']}")
        at = jj(root, "log", "--no-graph", "-r", "@", "-T", "commit_id", check=False).strip()
        if not at or run("git", "-C", str(root), "merge-base", "--is-ancestor", commit, at, check=False).returncode:
            blockers.append("the working copy does not descend from the release commit: it was moved off the release")
        else:
            local = jj(root, "log", "--no-graph", "-r", f"{commit}..@ ~ (empty() & description(exact:''))", "-T",
                       'change_id.short() ++ " " ++ description.first_line() ++ "\n"', check=False)
            out["localCommits"] = [line for line in local.splitlines() if line.strip()]
        if dev is None:
            blockers += [f"the running skill is not the release's ({d})" for d in skill_differences(root, commit)]
    return {**out, "state": "broken" if blockers else "current", "blockers": blockers}


def source(pin: dict) -> tuple[str, str]:
    return (os.environ.get("IN_THE_LOOP_REPOSITORY") or pin.get("repository") or "https://github.com/pilifs/in-the-loop",
            os.environ.get("IN_THE_LOOP_REF") or pin.get("ref") or "main")


def write_marker(root: Path, pin: dict, commit: str, repository: str, ref: str) -> None:
    marker = {"schema": MARKER_SCHEMA, "version": pin["version"], "digest": pin["digest"], "commit": commit,
              "repository": repository, "ref": ref,
              "installed": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
    (root / MARKER).write_text(json.dumps(marker, indent=1) + "\n")


def release_commit(root: Path, pin: dict, ref: str) -> str:
    tip = git(root, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{ref}^{{commit}}", check=False).strip()
    if not tip:
        raise Problem(f"the repository has no branch {ref}", "IN_THE_LOOP_REF naming the branch the release was cut on")
    commit, seen = find_release(root, pin, tip)
    if commit is None:
        raise Problem(f"release {pin['version']} (sha256 {pin['digest'][:16]}…) is not in {ref}"
                      + (": " + "; ".join(seen[:5]) if seen else ""),
                      "the release pushed to that branch, or a copy of the skill whose release is there (update the "
                      "plugin); nothing was changed")
    return commit


def install() -> dict:
    pin, root = load_pin(), home()
    for tool in ("git", "jj"):
        if not shutil.which(tool):
            raise Problem(f"{tool} is not on PATH", f"{tool} installed (the repository's examples/setup/ubuntu/install.sh "
                                                     f"devtools component installs jj)")
    if development_root() is not None and read_marker(development_root()) is None:
        raise Problem("this is a development checkout", "nothing: the checkout is the home")
    if root.exists() and any(root.iterdir()):
        raise Problem(f"{root} is not empty", "`bootstrap.py update` for a checkout this bootstrap made, or another "
                                              "IN_THE_LOOP_HOME")
    repository, ref = source(pin)
    root.parent.mkdir(parents=True, exist_ok=True)
    run("jj", "--quiet", "git", "clone", "--colocate", repository, str(root))
    try:
        commit = release_commit(root, pin, ref)
    except Problem:
        shutil.rmtree(root)  # nothing of the user's is in a clone made a moment ago
        raise
    # The limit sync.py's own init sets: a proof's evidence can be larger than jj's default for a new file.
    jj(root, "config", "set", "--repo", "snapshot.max-new-file-size", "100MiB")
    jj(root, "new", commit)
    write_marker(root, pin, commit, repository, ref)
    return status()


def update() -> dict:
    pin, root = load_pin(), home()
    marker = read_marker(root)
    if marker is None or marker.get("schema") != MARKER_SCHEMA:
        raise Problem(f"{root} is not a checkout this bootstrap made", "`bootstrap.py install`")
    repository, ref = source(pin)
    jj(root, "git", "fetch")
    commit = release_commit(root, pin, ref)
    old = marker.get("commit")
    moved = []
    if commit != old:
        # The user's line: everything between the old release and the working copy, the working copy included.
        jj(root, "rebase", "-b", "@", "-d", commit)
        moved = jj(root, "log", "--no-graph", "-r", f"{commit}..@", "-T",
                   'change_id.short() ++ (if(conflict, " CONFLICT ", " ")) ++ description.first_line() ++ "\n"').splitlines()
    write_marker(root, pin, commit, repository, ref)
    out = status()
    out["updated"] = {"from": marker.get("version"), "to": pin["version"], "moved": moved,
                      "conflicts": [m for m in moved if " CONFLICT " in m]}
    return out


def main(argv: list[str]) -> int:
    command = argv[0] if argv else ""
    try:
        if command == "status" and len(argv) == 1:
            print(json.dumps(status(), indent=1))
        elif command == "install" and len(argv) == 1:
            print(json.dumps(install(), indent=1))
        elif command == "update" and len(argv) == 1:
            print(json.dumps(update(), indent=1))
        elif command == "digest" and len(argv) <= 2:
            root = development_root() or home()
            rev = argv[1] if len(argv) == 2 else jj(root, "log", "--no-graph", "-r", "@", "-T", "commit_id").strip()
            digest, files = tree_digest(root, rev)
            print(json.dumps({"digest": digest, "files": files, "revision": rev}, indent=1))
        else:
            print(__doc__.split("\n\n")[1], file=sys.stderr)
            return 2
    except Problem as p:
        print(json.dumps({"state": "failed", "problem": p.what, "needs": p.needs}, indent=1))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

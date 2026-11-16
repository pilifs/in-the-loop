#!/usr/bin/env python3
"""A runtime checkout's work, as a contribution to the repository it was released from
(llm-dlc/runtime.md#contributing-back).

    contribute.py status        the local commits since the release, and for each path they change whether it
                                travels, stays, or is an example with what its travelling needs
    contribute.py check [REV]   a prepared contribution, the commits BASE..REV (REV by default @-, BASE the
                                upstream main, or --base): exit 1 with each problem, else 0 with a pull request body

What travels is the part worth more to the next user than to this one: the library, the tools, the schemas, their
tests and their documentation, and an example whose every source is public. What stays is the user's machine's own
record (the verification queue and its results, which upstream runs again), an example built from local sources,
and anything that names the user: `check` looks through the added lines for the home directory, the user name and
the host name, and never prints the line it found one in.

It only reads. Preparing the branch and opening the pull request are the agent's, once the user agrees; the page
above has the steps. Standard library only.
"""
from __future__ import annotations

import argparse
import getpass
import json
import re
import socket
import subprocess
import sys
from pathlib import Path

import mode  # llm-dlc/tools/mode.py

REPO = Path(__file__).resolve().parents[2]
UPSTREAM = "pilifs/in-the-loop"
# The user's machine's own record, and what a development checkout generates for itself.
STAYS = ("verification/jobs/", "verification/results/", "verification/findings.md", "verification/priorities.json",
         "llm-dlc/traces/", "llm-dlc/index.json", "llm-dlc/loop-summaries/", "llm-dlc/session-notes/")
EXAMPLE = re.compile(r"^examples/(\d{3})-[^/]+/")
LOCAL_NUMBERS = range(900, 1000)  # a runtime checkout's own examples (llm-dlc/runtime.md)
LOCAL_SOURCE = re.compile(r"file://|\"(?:/home/|/Users/|/root/|/mnt/|/tmp/|[A-Za-z]:\\\\)")


def jj(*args: str) -> str:
    r = subprocess.run(["jj", "--quiet", *args], cwd=REPO, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"jj {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def classify(path: str) -> str:
    """travels, stays, or example NNN."""
    if any(path == s or (s.endswith("/") and path.startswith(s)) for s in STAYS):
        return "stays"
    m = EXAMPLE.match(path)
    return f"example {m[1]}" if m else "travels"


def identifying() -> dict[str, str]:
    """What names the user on this machine, by kind. A name too short to tell from ordinary text is left out."""
    found = {"the home directory": str(Path.home())}
    for kind, value in (("the user name", getpass.getuser()), ("the host name", socket.gethostname().split(".")[0])):
        if len(value) >= 4 and value.lower() not in ("root", "user", "ubuntu", "admin", "localhost"):
            found[kind] = value
    return found


def added_lines(diff: str):
    """(path, line number in the new file, text) for each line a git-format diff adds."""
    path, number = None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", line)
            number = int(m[1]) - 1 if m else 0
        elif path and line.startswith("+"):
            number += 1
            yield path, number, line[1:]
        elif path and not line.startswith("-"):
            number += 1


def personal(diff: str, names: dict[str, str]) -> list[str]:
    """Where an added line names the user: the path, the line and the kind, never the text."""
    found = []
    for path, number, text in added_lines(diff):
        for kind, value in names.items():
            if value in text:
                found.append(f"{path}:{number} names {kind}")
    return found


def local_sources(diff: str) -> list[str]:
    """Example files whose added lines point at this machine: a file:// repository or an absolute local path."""
    return sorted({f"{path}:{number} points at a local path" for path, number, text in added_lines(diff)
                   if EXAMPLE.match(path) and path.endswith(".json") and LOCAL_SOURCE.search(text)})


def problems(commits: list[dict], paths: list[str], diff: str, names: dict[str, str]) -> list[str]:
    """Everything that stops a contribution, in words. `commits` are {change, summary, description, conflict}."""
    found = []
    for c in commits:
        if c["conflict"]:
            found.append(f"change {c['change']} ({c['summary']}) has conflicts: resolve them first")
        if f"\n{mode.RUNTIME_TRAILER}: " not in "\n" + c["description"]:
            found.append(f"change {c['change']} ({c['summary']}) has no {mode.RUNTIME_TRAILER} trailer: upstream tells "
                         f"a contributed commit by it")
        if "LLM-Trace" in c["description"]:
            found.append(f"change {c['change']} ({c['summary']}) carries a trace trailer: a runtime commit has none")
    for path in paths:
        kind = classify(path)
        if kind == "stays":
            found.append(f"{path} stays on this machine: restore it to upstream's in the contribution")
        elif kind.startswith("example ") and int(kind.split()[1]) in LOCAL_NUMBERS:
            found.append(f"{path} is under a runtime number ({kind.split()[1]}): renumber the example to the next free "
                         f"number upstream")
    found += local_sources(diff)
    found += personal(diff, names)
    return list(dict.fromkeys(found))


def read_commits(revset: str) -> list[dict]:
    out = jj("log", "--no-graph", "-r", f"({revset}) ~ (empty() & description(exact:''))", "-T",
             'json(change_id.short()) ++ "\\t" ++ json(description) ++ "\\t" ++ if(conflict, "1", "0") ++ "\\n"')
    commits = []
    for line in reversed(out.splitlines()):
        change, description, conflict = line.split("\t")
        description = json.loads(description)
        commits.append({"change": json.loads(change), "description": description, "conflict": conflict == "1",
                        "summary": description.strip().split("\n", 1)[0] or "(no description)"})
    return commits


def status() -> int:
    marker = mode.marker()
    if marker is None:
        raise SystemExit("contribute.py status reads a runtime checkout's line since its release; this is a "
                         "development checkout")
    base = marker["commit"]
    commits = read_commits(f"{base}..@")
    print(f"release {marker['version']}: {len(commits)} local commit(s) since")
    for c in commits:
        print(f"  {c['change']} {c['summary']}")
    by_kind: dict[str, list[str]] = {}
    for path in jj("diff", "--from", base, "--to", "@", "--name-only").splitlines():
        by_kind.setdefault(classify(path), []).append(path)
    diff = jj("diff", "--from", base, "--to", "@", "--git")
    local = {m[1] for line in local_sources(diff) if (m := EXAMPLE.match(line))}
    for kind in sorted(by_kind, key=lambda k: (k != "travels", k)):
        note = ""
        if kind.startswith("example "):
            number = kind.split()[1]
            note = (": built from local sources, so it stays" if number in local else
                    ": travels once renumbered" if int(number) in LOCAL_NUMBERS else ": travels")
        print(f"{kind}{note} ({len(by_kind[kind])} file(s))")
        for path in by_kind[kind][:12]:
            print(f"  {path}")
        if len(by_kind[kind]) > 12:
            print(f"  ... and {len(by_kind[kind]) - 12} more")
    return 0


def check(rev: str, base: str) -> int:
    commits = read_commits(f"{base}..{rev}")
    if not commits:
        raise SystemExit(f"no commits in {base}..{rev}: prepare the contribution on top of the upstream main first")
    paths = jj("diff", "--from", base, "--to", rev, "--name-only").splitlines()
    found = problems(commits, paths, jj("diff", "--from", base, "--to", rev, "--git"), identifying())
    if found:
        for problem in found:
            print("ERROR", problem)
        print(f"{len(found)} problem(s): nothing to push yet")
        return 1
    releases = sorted({m[1] for c in commits for m in re.finditer(rf"^{mode.RUNTIME_TRAILER}: (\S+)", c["description"], re.M)})
    examples = sorted({k.split()[1] for k in map(classify, paths) if k.startswith("example ")})
    print(f"{len(commits)} commit(s), {len(paths)} file(s): nothing stops this contribution. A pull request body:\n")
    print("\n".join([
        f"Made in a runtime checkout of release {', '.join(releases)} by `/prove-java-change`. The commits carry no "
        f"session trace, by design (`llm-dlc/runtime.md`).", "",
        "## What it adds", "", *[f"- {c['summary']}" for c in commits], "",
        "## What was verified, and where", "",
        ("- Examples " + ", ".join(examples) + ": each task's receipts are in its `receipts/` folder." if examples else
         "- No example travels with it: the change it was proved on is built from local sources."),
        "- TODO: the default test run's result on the contributor's machine, and what was not run.", "",
        "The contributor's verification jobs and results stayed on their machine: the proofs are to be queued again here."]))
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="A runtime checkout's work, as a contribution.")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="the local commits since the release, and what of them can travel")
    c = sub.add_parser("check", help="a prepared contribution, checked before it is pushed")
    c.add_argument("rev", nargs="?", default="@-")
    c.add_argument("--base", default="main@origin", help="what the contribution is on top of (default main@origin)")
    args = p.parse_args(argv)
    return status() if args.command == "status" else check(args.rev, args.base)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

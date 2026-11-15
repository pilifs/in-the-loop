#!/usr/bin/env python3
"""Releases of this repository for /prove-java-change (llm-dlc/runtime.md#releases).

A release is one commit: the skill at a version, and the repository it runs on, pinned to each other by the
sha256 digest of the commit's tree, which the skill carries in plugins/in-the-loop/skills/prove-java-change/release.json. The skill's
bootstrap accepts a checkout only when the commit carrying that pin hashes to it (bootstrap.py, which holds the
digest and is the one implementation of it: this module calls it).

    release.py cut [VERSION] [--note TEXT]
                         make @ a release and commit it: the version (given, or the last one's patch number
                         plus one) written into the plugin and the marketplace, the pin written from @'s tree,
                         the commit made with `sync.py commit`, and the result verified. Refuses while @ holds
                         uncommitted work: commit that first, so a release commit is only the release.
    release.py verify    the pin in @'s history: the commit that carries it, and that its tree hashes to it
    release.py status    the last release, the commits since, and whether it is on the remote main yet

Cutting changes nothing outside this repository. A release reaches users once its commit is pushed
(`sync.py push --bookmark main`, when the user asks), and a copy of the skill installed before then keeps its own
pin. To try a release before pushing it, install it from this clone: IN_THE_LOOP_REPOSITORY and IN_THE_LOOP_REF
(bootstrap.py) name the clone and a bookmark on the release commit.

Development mode only: a runtime checkout cuts no releases.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import mode  # llm-dlc/tools/mode.py

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "plugins" / "in-the-loop" / "skills" / "prove-java-change"
PLUGIN = REPO / "plugins" / "in-the-loop" / ".claude-plugin" / "plugin.json"
MARKETPLACE = REPO / ".claude-plugin" / "marketplace.json"
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def bootstrap():
    """plugins/in-the-loop/skills/prove-java-change/bootstrap.py as a module: the digest, the pin's format and the search for a release."""
    spec = importlib.util.spec_from_file_location("prove_java_change_bootstrap", SKILL / "bootstrap.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def jj(*args: str) -> str:
    r = subprocess.run(["jj", "--quiet", *args], cwd=REPO, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"jj {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout


def commit_id(rev: str) -> str:
    return jj("log", "--no-graph", "-r", rev, "-T", "commit_id").strip()


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def next_version(current: str) -> str:
    m = VERSION.match(current)
    if not m:
        raise SystemExit(f"{PLUGIN.relative_to(REPO)}'s version {current!r} is not MAJOR.MINOR.PATCH")
    return f"{m[1]}.{m[2]}.{int(m[3]) + 1}"


def uncommitted() -> list[str]:
    """Paths changed in @ that a release may not sweep in: everything but the trace files sync.py writes."""
    b = bootstrap()
    return [p for p in jj("diff", "--name-only").splitlines() if not b.left_out(p, b.EXCLUDED[1:])]


def cut(version: str | None, note: str | None) -> int:
    if mode.mode() != "development":
        raise SystemExit("a release is cut in a development checkout; this is a runtime one")
    if work := uncommitted():
        raise SystemExit("uncommitted work in @; commit it first, so the release commit holds only the release:\n  "
                         + "\n  ".join(work))
    b = bootstrap()
    plugin = json.loads(PLUGIN.read_text())
    version = version or next_version(plugin["version"])
    if not VERSION.match(version):
        raise SystemExit(f"{version!r} is not MAJOR.MINOR.PATCH")
    plugin["version"] = version
    write_json(PLUGIN, plugin)
    market = json.loads(MARKETPLACE.read_text())
    market.setdefault("metadata", {})["version"] = version
    for entry in market["plugins"]:
        if entry["name"] == plugin["name"]:
            entry["version"] = version
    write_json(MARKETPLACE, market)
    # The pin last: everything else of the release is in @'s tree by now, and the pin is left out of its own digest.
    digest, files = b.tree_digest(REPO, commit_id("@"))
    old = json.loads(b.PIN.read_text()) if b.PIN.exists() else {}
    write_json(b.PIN, {
        "schema": b.PIN_SCHEMA, "version": version, "digest": digest, "files": files, "excluded": list(b.EXCLUDED),
        "repository": old.get("repository", "https://github.com/pilifs/in-the-loop"), "ref": old.get("ref", "main"),
        "cut": datetime.now(timezone.utc).strftime("%Y-%m-%d"), **({"note": note} if note else {})})
    message = ["-m", f"Release {version} of /prove-java-change",
               "-m", f"The skill at {version} and the repository it runs on, pinned to each other: "
                     f"plugins/in-the-loop/skills/prove-java-change/release.json records the sha256 digest of this commit's tree "
                     f"({digest}, {files} files; the pin and the generated trace files are left out), and the skill's "
                     f"bootstrap accepts only a commit that hashes to it. Cut with llm-dlc/tools/release.py cut, which "
                     f"verified the commit afterwards." + (f" {note}" if note else "")]
    r = subprocess.run([sys.executable, str(REPO / "llm-dlc" / "tools" / "sync.py"), "commit", *message], cwd=REPO)
    if r.returncode:
        print("the commit's check reported errors; the release commit stands, so fix them in a later commit and cut "
              "again", file=sys.stderr)
    failed = verify(quiet=True)
    if not failed:
        print(f"release {version}: change {jj('log', '--no-graph', '-r', '@-', '-T', 'change_id.short()').strip()}, "
              f"sha256 {digest}\nit reaches users once main is pushed with it (python3 llm-dlc/tools/sync.py push "
              f"--bookmark main), when you decide to")
    return failed or r.returncode


def find() -> tuple[dict, str | None, list[str]]:
    b = bootstrap()
    pin = b.load_pin()
    commit, seen = b.find_release(REPO, pin, commit_id("@"))
    return pin, commit, seen


def verify(quiet: bool = False) -> int:
    pin, commit, seen = find()
    if commit is None:
        print(f"ERROR release {pin['version']}: no commit in @'s history carries this pin and hashes to it"
              + ("".join(f"\n  {s}" for s in seen)), file=sys.stderr)
        return 1
    if not quiet:
        print(f"release {pin['version']}: commit {commit[:12]} hashes to the pin ({pin['digest']})")
    return 0


def status() -> int:
    pin, commit, seen = find()
    print(f"pinned release: {pin['version']} (cut {pin.get('cut', '?')}), sha256 {pin['digest']}")
    if commit is None:
        print("  no commit in @'s history is that release" + "".join(f"\n  {s}" for s in seen))
        return 1
    since = jj("log", "--no-graph", "-r", f"{commit}..@ ~ (empty() & description(exact:''))", "-T",
               'change_id.short() ++ " " ++ description.first_line() ++ "\n"').splitlines()
    pushed = subprocess.run(["jj", "--quiet", "log", "--no-graph", "-r", f"{commit} & ::remote_bookmarks(exact:main)",
                             "-T", "commit_id"], cwd=REPO, capture_output=True, text=True).stdout.strip()
    print(f"  commit {commit[:12]}, {'on the remote main' if pushed else 'not pushed: no user can install it yet'}")
    print(f"  {len(since)} commit(s) since, in no release" + "".join(f"\n    {s}" for s in since[:20]))
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Releases of this repository for /prove-java-change.")
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("cut", help="make @ a release and commit it")
    c.add_argument("version", nargs="?", help="MAJOR.MINOR.PATCH; by default the last version's patch number plus one")
    c.add_argument("--note", help="a sentence for the pin and the commit message: what this release is for")
    sub.add_parser("verify", help="check the pin against the commit that carries it")
    sub.add_parser("status", help="the last release and the commits since")
    args = p.parse_args(argv)
    if args.command == "cut":
        return cut(args.version, args.note)
    return verify() if args.command == "verify" else status()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

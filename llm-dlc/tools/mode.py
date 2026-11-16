#!/usr/bin/env python3
"""Which mode this checkout runs in (llm-dlc/runtime.md).

  development  the repository as its authors work in it: every commit carries its session's trace, transcripts are
               redacted and published, and a push uploads them (llm-dlc/README.md).
  runtime      a released copy on a user's machine, set up by /prove-java-change: commits are plain, and nothing
               is traced, redacted, uploaded or pushed. The same commands work in both, so an agent follows one
               procedure: sync.py decides by this module what `commit`, `check` and the hooks do.

A checkout is a runtime one when its root holds MARKER, which the skill's bootstrap writes when it installs a
release (plugins/in-the-loop/skills/prove-java-change/bootstrap.py) and which is gitignored: it is a fact about one copy, never
committed. Anything else is a development checkout, so the repository behaves as it always has until a bootstrap
says otherwise. IN_THE_LOOP_MODE (development or runtime) overrides the marker, for tests.

    python3 llm-dlc/tools/mode.py          prints development or runtime
    python3 llm-dlc/tools/mode.py --json   the mode with the marker's release, as JSON

Standard library only: sync.py's hooks import it on every tool call.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MARKER = ".in-the-loop-runtime.json"
MARKER_SCHEMA = "in-the-loop-runtime/v1"
MODES = ("development", "runtime")
# The trailer of a commit made in a runtime checkout: the release it was made on. A development checkout reads it
# to tell such a commit from its own (sync.py never stamps a session's trace on one).
RUNTIME_TRAILER = "In-The-Loop-Runtime"


def marker(repo: Path = REPO) -> dict | None:
    """The runtime marker of a checkout, or None without one. A marker that can't be read, or of another schema,
    is an error, never a development checkout: tracing a user's sessions by mistake would publish them."""
    path = repo / MARKER
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        raise SystemExit(f"{path}: unreadable runtime marker ({e}); reinstall with the skill's bootstrap, or remove it "
                         f"in a development checkout")
    if not isinstance(data, dict) or data.get("schema") != MARKER_SCHEMA:
        raise SystemExit(f"{path}: not a {MARKER_SCHEMA} marker")
    return data


def mode(repo: Path = REPO) -> str:
    forced = os.environ.get("IN_THE_LOOP_MODE")
    if forced:
        if forced not in MODES:
            raise SystemExit(f"IN_THE_LOOP_MODE={forced!r}: expected one of {', '.join(MODES)}")
        return forced
    return "runtime" if marker(repo) is not None else "development"


def release(repo: Path = REPO) -> str:
    """The release a runtime checkout was installed from, as its commits' trailer names it: VERSION sha256:DIGEST."""
    m = marker(repo) or {}
    return f"{m.get('version', 'unknown')} sha256:{m.get('digest', 'unknown')}"


def main(argv: list[str]) -> int:
    if argv not in ([], ["--json"]):
        print("usage: mode.py [--json]", file=sys.stderr)
        return 2
    if argv:
        print(json.dumps({"mode": mode(), "root": str(REPO), "marker": marker()}, indent=1))
    else:
        print(mode())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

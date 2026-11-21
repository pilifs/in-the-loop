#!/usr/bin/env python3
"""Tests for `sync.py commit --only`: what is set aside before the commit and put back after it, on a real jj
repository in a temporary directory, and what `pipeline.py commit-paths` names for the result collector.
Run: python3 llm-dlc/tools/test_commit_only.py"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sync

sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402


class CommitOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "root"
        self.root.mkdir()
        (Path(self.tmp.name) / "jj-config.toml").write_text("")
        self.env = mock.patch.dict(os.environ, {"JJ_USER": "Made Up", "JJ_EMAIL": "made-up@example.com",
                                                "JJ_CONFIG": str(Path(self.tmp.name) / "jj-config.toml")})
        self.env.start()
        self.patch = mock.patch.object(sync, "jj", lambda *args: subprocess.run(["jj", "--quiet", *args], cwd=self.root,
                                                                                capture_output=True, text=True))
        self.patch.start()
        self.write("verification/results/old/result.json", "{}\n")
        self.write("lib/a.txt", "one\n")
        self.jj("git", "init", "--colocate")
        self.jj("commit", "-m", "base")

    def tearDown(self):
        self.patch.stop()
        self.env.stop()
        self.tmp.cleanup()

    def jj(self, *args: str) -> str:
        r = subprocess.run(["jj", *args], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def write(self, path: str, text: str) -> None:
        (self.root / path).parent.mkdir(parents=True, exist_ok=True)
        (self.root / path).write_text(text)

    def commit(self, only: list[str], message: str) -> list[str]:
        """What cmd_commit does around its own steps: set aside, describe and start a new change, put back."""
        other, theirs = sync.set_aside(only)
        self.jj("describe", "-m", message)
        committed = self.jj("log", "--no-graph", "-r", "@", "-T", "change_id").strip()
        self.jj("new")
        sync.put_back(other, committed)
        return theirs

    @cost("tool")
    def test_the_commit_takes_the_named_paths_and_leaves_the_rest_uncommitted_as_it_was(self):
        self.write("verification/results/new/result.json", '{"status": "passed"}\n')  # the collector's
        self.write("examples/README.md", "table\n")
        self.write("lib/a.txt", "two\n")  # another session's: modified, added, and a file in a folder not named
        self.write("lib/b.txt", "new\n")
        self.write("examples/123/notes.md", "theirs\n")
        theirs = self.commit(["verification", "examples/README.md"], "Record verification results")
        self.assertEqual(sorted(theirs), ["examples/123/notes.md", "lib/a.txt", "lib/b.txt"])
        self.assertEqual(sorted(self.jj("diff", "-r", "@-", "--name-only").split()),
                         ["examples/README.md", "verification/results/new/result.json"])
        self.assertEqual(self.jj("log", "--no-graph", "-r", "@-", "-T", "description").strip(), "Record verification results")
        self.assertEqual(sorted(self.jj("diff", "-r", "@", "--name-only").split()), ["examples/123/notes.md", "lib/a.txt", "lib/b.txt"])
        self.assertEqual(((self.root / "lib/a.txt").read_text(), (self.root / "lib/b.txt").read_text()), ("two\n", "new\n"))
        self.assertEqual(self.jj("log", "--no-graph", "-r", "@", "-T", "description"), "")  # still nobody's commit
        self.assertNotIn("wip", self.jj("log", "--no-graph", "-r", "all()", "-T", 'description ++ "\\n"'))

    @cost("tool")
    def test_thousands_of_other_files_are_set_aside_by_one_short_command(self):
        for i in range(600):  # as an example's records are, added by one session while another commits its own
            self.write(f"examples/901-made-up/records/calls/abc/cases/p{i}/native.json", "[]\n")
        self.write('lib/odd "name" here.txt', "theirs too\n")
        self.write("verification/findings.md", "VF-1\n")
        calls, real = [], sync.jj
        with mock.patch.object(sync, "jj", lambda *args: calls.append(args) or real(*args)):
            theirs = self.commit(["verification"], "Record a finding")
        self.assertEqual(len(theirs), 601)
        split = next(args for args in calls if args[0] == "split")
        self.assertLess(sum(len(a) for a in split), 200)  # it names what stays; the paths that go are not on the line
        self.assertEqual(self.jj("diff", "-r", "@-", "--name-only").split(), ["verification/findings.md"])
        self.assertEqual(len(self.jj("diff", "-r", "@", "--name-only").splitlines()), 601)
        self.assertEqual(sync.listed(theirs, most=2).split(" and ")[1], "599 more")
        self.assertEqual(sync.listed(["a", "b"]), "a b")

    @cost("tool")
    def test_with_nothing_else_changed_nothing_is_set_aside(self):
        self.write("verification/findings.md", "VF-1\n")
        self.assertEqual(self.commit(["verification"], "Record a finding"), [])
        self.assertEqual(self.jj("diff", "-r", "@-", "--name-only").split(), ["verification/findings.md"])
        self.assertEqual(self.jj("diff", "-r", "@", "--name-only"), "")

    @cost("tool")
    def test_only_takes_its_paths_up_to_the_message(self):
        self.assertEqual(sync.only_paths(["--only", "verification/", "examples/README.md", "-m", "S", "-m", "P"]),
                         (["verification", "examples/README.md"], ["-m", "S", "-m", "P"]))
        self.assertEqual(sync.only_paths(["-m", "S"]), (None, ["-m", "S"]))
        self.assertEqual(sync.only_paths(["--only", "-m", "S"])[0], [])  # no path named: cmd_commit refuses it


if __name__ == "__main__":
    unittest.main()

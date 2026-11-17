#!/usr/bin/env python3
"""Tests for unstale.py on a real jj repository in a temporary directory with two workspaces, where one
workspace's operation is made to meet the other's (jj --at-op, which is what two sessions at once amount to).
Run: python3 llm-dlc/tools/test_unstale.py
A truly stale working copy could not be produced on demand with this jj (it joined every pair of operations tried
without refusing), so that path is tested from the state update-stale leaves: the files on disk reset, and the
edits in the second copy of the change."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import unstale

sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402


class Unstale(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        (base / "jj-config.toml").write_text("")
        self.env = mock.patch.dict(os.environ, {"JJ_USER": "Made Up", "JJ_EMAIL": "made-up@example.com",
                                                "JJ_CONFIG": str(base / "jj-config.toml")})
        self.env.start()
        self.root, self.b = base / "root", base / "b"
        self.root.mkdir()
        (self.root / "a.txt").write_text("one\n")
        self.jj(self.root, "git", "init", "--colocate")
        self.jj(self.root, "commit", "-m", "base")
        self.jj(self.root, "workspace", "add", "--name", "b", "-r", "@-", str(self.b))
        (self.b / "c.txt").write_text("c\n")
        self.jj(self.b, "commit", "-m", "b's commit")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def jj(self, where: Path, *args: str) -> str:
        r = subprocess.run(["jj", *args], cwd=where, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def meet(self) -> None:
        """b snapshots some edits, edits more, and the other workspace rewrites b's parent from the operation
        before: jj joins the two, and b's working-copy change comes out with a second, older copy."""
        (self.b / "a.txt").write_text("one\ntwo\n")
        self.jj(self.b, "status")
        op = self.jj(self.b, "op", "log", "--no-graph", "-n", "1", "-T", "id.short(16)")
        (self.b / "d.txt").write_text("after the last snapshot\n")
        self.jj(self.b, "status")
        self.jj(self.root, f"--at-op={op}", "describe", "-r", "b@-", "-m", "b's commit, reworded at the same moment")
        self.jj(self.b, "status")

    @cost("tool")
    def test_a_workspace_that_is_whole_is_left_alone(self):
        (self.b / "a.txt").write_text("one\ntwo\n")
        code, said = unstale.recover(self.b)
        self.assertEqual((code, said), (0, ["the working copy is neither stale nor divergent: nothing to do"]))
        self.assertEqual((self.b / "a.txt").read_text(), "one\ntwo\n")

    @cost("tool")
    def test_a_second_copy_left_by_two_operations_at_once_is_abandoned_and_the_files_stay(self):
        self.meet()
        self.assertEqual(len(unstale.siblings(self.b)), 1)
        self.assertEqual(unstale.recover(self.b, check=True)[0], 1)
        code, said = unstale.recover(self.b)
        self.assertEqual(code, 0, said)
        self.assertIn("abandoned the second copy", said[-1])
        self.assertEqual(unstale.siblings(self.b), [])
        self.assertEqual(((self.b / "a.txt").read_text(), (self.b / "d.txt").read_text()), ("one\ntwo\n", "after the last snapshot\n"))
        self.assertEqual(sorted(self.jj(self.b, "diff", "--name-only").split()), ["a.txt", "d.txt"])

    @cost("tool")
    def test_a_copy_with_edits_the_working_copy_lacks_is_not_abandoned(self):
        self.meet()
        self.jj(self.b, "restore", "a.txt")  # the working copy loses an edit the second copy still has
        code, said = unstale.recover(self.b)
        self.assertEqual(code, 1)
        self.assertIn("changes files the working copy doesn't (a.txt)", said[-1])
        self.assertEqual(len(unstale.siblings(self.b)), 1)

    @cost("tool")
    def test_after_update_stale_the_edits_come_back_from_the_copy_jj_kept_and_only_those_files(self):
        self.meet()
        self.jj(self.b, "restore")  # as update-stale leaves it: the files on disk at the commit, the edits in the copy
        self.assertFalse((self.b / "d.txt").exists())
        with mock.patch.object(unstale, "is_stale", lambda where: True), \
                mock.patch.object(unstale, "jj", lambda where, *args: subprocess.CompletedProcess(args, 0, "", "")
                                  if args[:2] == ("workspace", "update-stale") else
                                  subprocess.run(["jj", *args], cwd=where, capture_output=True, text=True)):
            code, said = unstale.recover(self.b)
        self.assertEqual(code, 0, said)
        self.assertEqual((self.b / "a.txt").read_text(), "one\ntwo\n")  # the edit the copy held
        self.assertIn("took 1 edited file(s) back from the copy jj kept: a.txt", said)
        self.assertEqual(unstale.siblings(self.b), [])

    @cost("tool")
    def test_the_backup_holds_what_was_written_since_jj_last_looked(self):
        self.jj(self.b, "status")
        (self.b / "late.txt").write_text("written after\n")
        saved = unstale.backup(self.b)
        import tarfile
        with tarfile.open(saved) as tar:
            self.assertIn("late.txt", tar.getnames())
            self.assertFalse(any(n.startswith(".jj") for n in tar.getnames()))


if __name__ == "__main__":
    unittest.main()

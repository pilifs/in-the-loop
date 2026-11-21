#!/usr/bin/env python3
"""Tests of prune_workspaces.py, each on a throwaway colocated jj repository with a second
workspace. Run: python3 llm-dlc/tools/test_prune_workspaces.py"""

import contextlib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

SCRIPT = Path(__file__).resolve().with_name("prune_workspaces.py")
# The machine's own private archive is no part of these tests: off, except in the one test that gives it a home.
ENV = {**os.environ, "JJ_USER": "Test", "JJ_EMAIL": "test@example.invalid", "JJ_CONFIG": "/dev/null", "ITL_ORIGINALS_OFF": "1"}
spec = importlib.util.spec_from_file_location("prune_workspaces", SCRIPT)
prune_workspaces = importlib.util.module_from_spec(spec)
sys.modules["prune_workspaces"] = prune_workspaces  # its dataclasses look their module up there
spec.loader.exec_module(prune_workspaces)


def sh(cwd, *cmd):
    return subprocess.run(cmd, cwd=cwd, env=ENV, check=True, capture_output=True, text=True).stdout


class PruneTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / "repo"
        self.root.mkdir()
        sh(self.root, "jj", "git", "init", "--colocate")
        (self.root / ".gitignore").write_text("target/\n.env\nrecords/\n")
        (self.root / "a.txt").write_text("first\n")
        (self.root / "build").mkdir()
        (self.root / "build" / "tracked.txt").write_text("tracked in a dir named build\n")
        sh(self.root, "jj", "commit", "-m", "base")
        self.ws = base / "repo-side"
        sh(self.root, "jj", "workspace", "add", "--name", "side", "-r", "@-", str(self.ws))

    def tearDown(self):
        self.tmp.cleanup()

    def prune(self, *args):
        r = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.root, env=ENV, capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr

    def delete(self, *args, answer="delete"):
        """--delete as a person runs it: at a terminal, typing answer at the prompt."""
        out = io.StringIO()
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            with mock.patch.dict(os.environ, ENV), mock.patch.object(prune_workspaces, "person_at_terminal", return_value=True), \
                    mock.patch("builtins.input", return_value=answer), contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                code = prune_workspaces.main(["--delete", *args])
        finally:
            os.chdir(cwd)
        return code, out.getvalue()

    def merge_side(self):
        """Merge the side workspace's commits into the default line, as a reconcile does."""
        sh(self.root, "jj", "new", "@-", "side@-", "-m", "merge")
        sh(self.root, "jj", "new")

    @cost("tool")
    def test_a_merged_workspace_is_clear_and_deleted(self):
        (self.ws / "b.txt").write_text("side work\n")
        sh(self.ws, "jj", "commit", "-m", "side work")
        self.merge_side()
        code, out = self.prune()
        self.assertEqual(code, 0, out)
        self.assertIn("safe to delete", out)
        self.assertIn("python3 llm-dlc/tools/prune_workspaces.py --delete side", out)
        self.assertTrue(self.ws.exists())  # the report deletes nothing
        code, out = self.delete("side")
        self.assertEqual(code, 0, out)
        self.assertFalse(self.ws.exists())
        self.assertNotIn("side", sh(self.root, "jj", "workspace", "list"))
        self.assertNotIn("repo-side", sh(self.root, "git", "worktree", "list"))

    @cost("tool")
    def test_an_unmerged_commit_blocks(self):
        (self.ws / "b.txt").write_text("side work\n")
        sh(self.ws, "jj", "commit", "-m", "side work")
        code, out = self.delete("side")
        self.assertEqual(code, 1, out)
        self.assertIn("not in ::@-", out)
        self.assertTrue(self.ws.exists())

    @cost("tool")
    def test_an_edit_jj_never_snapshotted_blocks(self):
        self.merge_side()
        (self.ws / "a.txt").write_text("edited, never snapshotted\n")
        code, out = self.delete("side")
        self.assertEqual(code, 1, out)
        self.assertIn("a.txt", out)
        self.assertTrue((self.ws / "a.txt").exists())

    @cost("tool")
    def test_a_gitignored_file_found_nowhere_blocks_and_archive_keeps_it(self):
        (self.ws / ".env").write_text("TOKEN=made-up-value\n")
        code, out = self.prune("side")
        self.assertEqual(code, 1, out)
        self.assertIn(".env", out)
        self.assertIn("gitignored", out)
        archive = Path(self.tmp.name) / "archive"
        code, out = self.prune("--archive", str(archive), "side")
        self.assertEqual(code, 2, out)  # it writes, so only with --delete
        self.assertIn("--delete --archive DIR side", self.prune()[1])
        code, out = self.delete("--archive", str(archive), "side")
        self.assertEqual(code, 0, out)
        self.assertEqual((archive / "side" / ".env").read_text(), "TOKEN=made-up-value\n")
        self.assertFalse(self.ws.exists())

    @cost("tool")
    def test_a_file_the_private_archive_holds_verified_in_the_store_is_recoverable_and_a_pending_one_is_not(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import artifacts
        base = Path(self.tmp.name)
        env = {"ITL_ORIGINALS_HOME": str(base / "originals"), "ITL_ORIGINALS_CACHE": str(base / "cache"), "ITL_ORIGINALS_OFF": "",
               "ITL_ORIGINALS_STORE": f"dir:{base / 'store'}", "ITL_ORIGINALS_RESERVE": "0", "ITL_ORIGINALS_UPLOAD": "manual"}
        work = self.ws / "records" / "run-1"   # gitignored, and nowhere else: a run's output left in its workspace
        work.mkdir(parents=True)
        (work / "prove.log").write_text("a made-up log\n" * 100)
        (work / "result.json").write_text('{"made-up": true}\n')
        with mock.patch.dict(os.environ, env), mock.patch.dict(ENV, env):
            archive = artifacts.Archive()
            self.addCleanup(archive.close)
            archive.capture(work, "job-run", "records/run-1", job="made-up")
            code, out = self.prune("side")
            self.assertEqual(code, 1, out)       # sealed on this machine only: its disk is still the last copy
            self.assertIn("2 file(s) recoverable from nowhere", out)
            archive.upload()
            (work / "later.txt").write_text("written after the capture\n")
            code, out = self.prune("side")
            self.assertEqual(code, 1, out)
            self.assertIn("1 file(s) recoverable from nowhere", out)
            self.assertIn("records/run-1/later.txt", out)
            self.assertNotIn("prove.log", out)
            (work / "later.txt").unlink()
            (work / "result.json").write_text('{"made-up": false}\n')   # the same length, other bytes
            self.assertIn("records/run-1/result.json", self.prune("side")[1])
            (work / "result.json").write_text('{"made-up": true}\n')
            code, out = self.prune("side")
            self.assertEqual(code, 0, out)
            self.assertIn("2 of them are kept by the private archive alone, verified in the store", out)
        code, out = self.prune("side")           # and with no archive to ask, they block as before
        self.assertEqual(code, 1, out)

    @cost("tool")
    def test_a_gitignored_file_copied_into_the_default_workspace_is_clear(self):
        (self.ws / "records").mkdir()
        (self.ws / "records" / "run.md").write_text("a run record\n")
        (self.root / "records").mkdir()
        (self.root / "records" / "side-run.md").write_text("a run record\n")  # copied in, another name
        code, out = self.prune("side")
        self.assertEqual(code, 0, out)

    @cost("tool")
    def test_ignored_build_output_is_regenerable(self):
        (self.ws / "target" / "debug").mkdir(parents=True)
        (self.ws / "target" / "debug" / "bin").write_bytes(os.urandom(4096))
        code, out = self.prune("side")
        self.assertEqual(code, 0, out)
        self.assertIn("build output not checked", out)

    @cost("tool")
    def test_a_tracked_directory_named_like_build_output_is_checked(self):
        self.merge_side()
        (self.ws / "build" / "new.txt").write_text("not ignored, not committed\n")
        code, out = self.prune("side")
        self.assertEqual(code, 1, out)
        self.assertIn("build/new.txt", out)

    @cost("tool")
    def test_a_forgotten_workspace_directory_is_found_and_checked(self):
        sh(self.root, "jj", "workspace", "forget", "side")
        code, out = self.prune()
        self.assertEqual(code, 0, out)
        self.assertIn("side (forgotten", out)
        (self.ws / "only-here.txt").write_text("nowhere else\n")
        code, out = self.delete("side")
        self.assertEqual(code, 1, out)
        self.assertIn("only-here.txt", out)
        self.assertTrue(self.ws.exists())

    @cost("tool")
    def test_a_workspace_in_use_blocks(self):
        proc = subprocess.Popen(["sleep", "30"], cwd=self.ws)
        try:
            code, out = self.delete("side")
        finally:
            proc.kill()
            proc.wait()
        self.assertEqual(code, 1, out)
        self.assertIn("in use by", out)
        self.assertTrue(self.ws.exists())

    @cost("tool")
    def test_a_git_directory_of_its_own_blocks(self):
        (self.ws / ".git").unlink(missing_ok=True)
        sh(self.ws, "git", "init", "-q")
        code, out = self.prune("side")
        self.assertEqual(code, 1, out)
        self.assertIn(".git directory", out)

    @cost("tool")
    def test_a_workspace_of_an_unfinished_loop_is_kept(self):
        sh(self.root, "jj", "workspace", "forget", "side")
        loops = self.root / "llm-dlc" / "loops"
        loops.mkdir(parents=True)
        brief = loops / "repo.md"  # the workspace "side" is repo-side: a stream of a brief "repo"
        sh(self.root, "jj", "workspace", "add", "--name", "repo-side", "-r", "@-", str(self.ws) + "2")
        brief.write_text("## Progress\n\n- Status: working\n")
        code, out = self.prune("repo-side")
        self.assertEqual(code, 1, out)
        self.assertIn("its loop is unfinished: llm-dlc/loops/repo.md (status: working)", out)
        brief.write_text("## Progress\n\n- Status: waiting on jobs 20261107-000000-x\n- Status: done\n")
        code, out = self.prune("repo-side")
        self.assertEqual(code, 0, out)

    @cost("tool")
    def test_delete_is_refused_in_an_agents_shell(self):
        code, out = self.prune("--delete", "side")  # no terminal, and CLAUDECODE when an agent runs the tests
        self.assertEqual(code, 1, out)
        self.assertIn("refused: a person must delete workspaces", out)
        self.assertTrue(self.ws.exists())

    @cost("tool")
    def test_delete_needs_names_and_the_typed_confirmation(self):
        self.assertEqual(self.delete()[0], 2)
        code, out = self.delete("side", answer="yes")
        self.assertEqual(code, 1, out)
        self.assertIn("nothing deleted", out)
        self.assertTrue(self.ws.exists())

    @cost("tool")
    def test_it_runs_only_from_the_default_workspace(self):
        r = subprocess.run([sys.executable, str(SCRIPT)], cwd=self.ws, env=ENV, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()

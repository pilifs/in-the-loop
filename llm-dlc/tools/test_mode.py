#!/usr/bin/env python3
"""Tests for the two modes of a checkout (mode.py) and what sync.py does in a runtime one: a plain commit with the
release's trailer, hooks that do nothing, and every publishing command refused; and that a development checkout
never stamps a session's trace on a commit made in a runtime one.
Run: python3 llm-dlc/tools/test_mode.py
Every value is made up. No jj runs: sync's calls to it are replaced."""
import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import mode
import sync

DIGEST = "ab" * 32
MARKER = {"schema": mode.MARKER_SCHEMA, "version": "1.2.3", "digest": DIGEST, "commit": "c0ffee" * 6 + "c0ff"}
TRAILER = f"{mode.RUNTIME_TRAILER}: 1.2.3 sha256:{DIGEST}"


class ModeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        patch = mock.patch.dict(os.environ)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("IN_THE_LOOP_MODE", None)

    def mark(self, content=None):
        (self.repo / mode.MARKER).write_text(json.dumps(MARKER) if content is None else content)

    def test_a_checkout_without_a_marker_is_a_development_one(self):
        self.assertEqual(mode.mode(self.repo), "development")
        self.assertIsNone(mode.marker(self.repo))

    def test_the_marker_makes_it_a_runtime_one_and_names_the_release(self):
        self.mark()
        self.assertEqual(mode.mode(self.repo), "runtime")
        self.assertEqual(mode.release(self.repo), f"1.2.3 sha256:{DIGEST}")

    def test_a_marker_that_cannot_be_read_is_an_error_never_a_development_checkout(self):
        for content in ("{not json", json.dumps({"schema": "something-else/v1"}), json.dumps([1])):
            self.mark(content)
            with self.assertRaises(SystemExit):
                mode.mode(self.repo)

    def test_the_variable_overrides_the_marker_and_a_misspelt_one_is_refused(self):
        os.environ["IN_THE_LOOP_MODE"] = "runtime"
        self.assertEqual(mode.mode(self.repo), "runtime")
        self.mark()
        os.environ["IN_THE_LOOP_MODE"] = "development"
        self.assertEqual(mode.mode(self.repo), "development")
        os.environ["IN_THE_LOOP_MODE"] = "production"
        with self.assertRaises(SystemExit):
            mode.mode(self.repo)

    def test_this_checkout_s_marker_is_ignored_by_git(self):
        ignored = (mode.REPO / ".gitignore").read_text().splitlines()
        self.assertIn("/" + mode.MARKER, ignored)


class RuntimeSyncTest(unittest.TestCase):
    """sync.py in a runtime checkout."""

    def setUp(self):
        self.calls = []
        ok = subprocess.CompletedProcess([], 0, "", "")
        for target, replacement in (("jj", lambda *args: self.calls.append(args) or ok),
                                    ("jj_commits", lambda revset: [{"change_id": "k" * 32, "commit_id": "1" * 40,
                                                                    "immutable": False, "description": ""}])):
            patch = mock.patch.object(sync, target, replacement)
            patch.start()
            self.addCleanup(patch.stop)
        patch = mock.patch.object(mode, "marker", lambda repo=None: MARKER)
        patch.start()
        self.addCleanup(patch.stop)

    def run_runtime(self, cmd, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = sync.runtime_run(cmd, list(args))
        return status, out.getvalue(), err.getvalue()

    def test_a_commit_is_the_message_with_the_release_s_trailer_and_a_new_change(self):
        status, out, _ = self.run_runtime("commit", "-m", "Add example 901", "-m", "What changed and how it was verified.")
        self.assertEqual(status, 0)
        self.assertEqual(self.calls, [("describe", "-r", "@", "-m", "Add example 901\n\nWhat changed and how it was "
                                       f"verified.\n\n{TRAILER}"), ("new",)])
        self.assertIn("0 error(s)", out)

    def test_a_trailer_already_there_is_not_added_twice_and_another_release_s_is_replaced(self):
        self.run_runtime("commit", "-m", "Summary", "-m", TRAILER)
        self.assertEqual(self.calls[0][-1].count(mode.RUNTIME_TRAILER), 1)
        self.calls.clear()
        self.run_runtime("commit", "-m", "Summary", "-m", f"Co-Authored-By: Someone <s@example.invalid>\n{mode.RUNTIME_TRAILER}: 0.0.1 sha256:{'cd' * 32}")
        self.assertEqual(self.calls[0][-1], f"Summary\n\nCo-Authored-By: Someone <s@example.invalid>\n{TRAILER}")

    def test_a_commit_without_a_message_changes_nothing(self):
        for args in ([], ["-m"], ["-m", "  "], ["--message", "x"]):
            self.assertEqual(self.run_runtime("commit", *args)[0], 2)
        self.assertEqual(self.calls, [])

    def test_the_hooks_do_nothing_and_say_nothing(self):
        for hook in ("hook", "hook-commit"):
            self.assertEqual(self.run_runtime(hook), (0, "", ""))
        self.assertEqual(self.calls, [])

    def test_check_passes_with_nothing_to_check(self):
        status, out, _ = self.run_runtime("check")
        self.assertEqual(status, 0)
        self.assertIn("0 error(s)", out)
        self.assertIn("1.2.3", out)

    def test_every_publishing_command_is_refused_with_where_to_read_why(self):
        for cmd in ("push", "upload", "scan", "sync", "review", "allow", "stamp", "langfuse", "unpublish", "regenerate"):
            status, _, err = self.run_runtime(cmd)
            self.assertEqual(status, 2, cmd)
            self.assertIn("llm-dlc/runtime.md", err)
        self.assertEqual(self.calls, [])

    def test_main_goes_to_the_runtime_commands_without_the_lock_or_the_state_folder(self):
        with mock.patch.object(mode, "mode", lambda repo=None: "runtime"), \
                mock.patch.object(sync, "Operation", side_effect=AssertionError("a runtime command took the lock")), \
                mock.patch.object(sync, "save_perf", side_effect=AssertionError("a runtime command wrote its timings")), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sync.main(["check"]), 0)
            self.assertEqual(sync.main(["push", "--bookmark", "main"]), 2)


class ContributedCommitTest(unittest.TestCase):
    """A development checkout and a commit that came from a runtime one."""

    def test_a_session_s_trace_is_never_stamped_on_a_commit_with_the_runtime_trailer(self):
        sid, sha = "0f0f0f0f-1111-4222-8333-444455556666", "ef" * 32
        commits = [{"change_id": "a" * 32, "commit_id": "1" * 40, "immutable": False, "description": "Our own change\n"},
                   {"change_id": "b" * 32, "commit_id": "2" * 40, "immutable": False,
                    "description": f"A contributed model\n\nWhat it adds.\n\n{TRAILER}\n"}]
        described = []

        def jj_commits(revset):
            if revset == "@":
                return [{"change_id": "z" * 32, "commit_id": "9" * 40, "immutable": False, "description": ""}]
            return commits if revset.startswith("mutable()") else []

        m = {"started": "2026-11-15T10:00:00Z", "ended": "2026-11-15T11:00:00Z", "log": {"sha256": sha}}
        with mock.patch.object(sync, "jj_commits", jj_commits), \
                mock.patch.object(sync, "jj", lambda *args: described.append(args)), \
                mock.patch.object(sync, "save_manifest", lambda sid, m: None), \
                mock.patch.object(sync, "repo_web_url", lambda: None):
            sync.link_commits(sid, m, current=False)
        self.assertEqual([args[2] for args in described], ["a" * 32])  # ours stamped, the contributed one left alone
        self.assertIn(f"LLM-Trace: {sid} sha256:{sha}", described[0][-1])


if __name__ == "__main__":
    unittest.main()

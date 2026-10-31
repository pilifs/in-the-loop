#!/usr/bin/env python3
"""Tests for reviewed false positives in sync.py. Run: python3 llm-dlc/tools/test_review.py
Values are split in the source so that this file's own transcript raises no finding."""
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sync

HOME_A, HOME_B = "/ho" + "me/alpha", "/ho" + "me/bravo"


def line(text):
    return json.dumps({"text": text})


class Review(unittest.TestCase):
    def setUp(self):
        self.r = sync.Redactor()
        self.r.reviewed = {}

    def test_a_reviewed_value_is_left_out_and_counted(self):
        self.assertIn("other-home-dir", self.r.review_hits(line(HOME_A)))
        self.r.reviewed = {sync.finding_id("other-home-dir", HOME_A): {}}
        self.assertEqual(self.r.review(line(HOME_A)), [])
        self.assertEqual(self.r.skipped["other-home-dir"], 1)

    def test_a_different_value_still_warns(self):
        self.r.reviewed = {sync.finding_id("other-home-dir", HOME_A): {}}
        self.assertEqual(list(self.r.review_hits(line(HOME_B))), ["other-home-dir"])

    def test_a_review_covers_one_kind_only(self):
        self.r.reviewed = {sync.finding_id("public-ip", HOME_A): {}}
        self.assertIn("other-home-dir", self.r.review_hits(line(HOME_A)))

    def test_an_error_can_be_reviewed_too(self):
        address = "someone" + "@" + "corp.test"
        self.assertIn("email", self.r.leaks(line(address)))
        self.r.reviewed = {sync.finding_id("email", address): {}}
        self.assertNotIn("email", self.r.leaks(line(address)))

    def test_a_local_secret_can_never_be_waived(self):
        secret = "made-up-" + "value"
        self.r.literals = [("local-secret", re.compile(secret), "x")]
        self.r.reviewed = {sync.finding_id("local-secret", secret): {}}
        self.assertEqual(self.r.leaks(line(secret)), ["local-secret"])


class Authorization(unittest.TestCase):
    def accept(self):
        err = io.StringIO()
        with mock.patch("sys.stderr", err):
            return sync.cmd_review(["accept", "abcd1234", "--reason", "test"]), err.getvalue()

    def test_a_shell_with_no_terminal_is_refused(self):
        with mock.patch("sys.stdin.isatty", return_value=False), mock.patch("sys.stdout.isatty", return_value=False):
            code, err = self.accept()
        self.assertEqual(code, 1)
        self.assertIn("refused", err)

    def test_an_agent_with_a_terminal_is_refused(self):
        with mock.patch("sys.stdin.isatty", return_value=True), mock.patch("sys.stdout.isatty", return_value=True), \
                mock.patch.dict("os.environ", {"CLAUDECODE": "1"}):
            code, err = self.accept()
        self.assertEqual(code, 1)
        self.assertIn("refused", err)

    def test_a_person_is_asked_and_can_decline(self):
        fid = sync.finding_id("other-home-dir", HOME_A)
        open_now = {fid: {"level": "warn", "kind": "other-home-dir", "value": HOME_A, "count": 1, "where": {"s"}}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviewed.json"
            with mock.patch.object(sync, "REVIEWED", path), mock.patch.object(sync, "REPO", Path(tmp)), \
                    mock.patch.object(sync, "person_at_terminal", return_value=True), \
                    mock.patch.object(sync, "open_findings", return_value=open_now), \
                    mock.patch("sys.stdout", io.StringIO()):
                with mock.patch("builtins.input", return_value="no"):
                    self.assertEqual(sync.cmd_review(["accept", fid[:8], "--reason", "test"]), 1)
                self.assertFalse(path.exists())
                with mock.patch("builtins.input", return_value=sync.CONFIRMATION):
                    self.assertEqual(sync.cmd_review(["accept", fid[:8], "--reason", "test"]), 0)
                entry = sync.load_reviewed()[fid]
                self.assertNotIn(HOME_A, path.read_text())
                self.assertEqual((entry["kind"], entry["reason"]), ("other-home-dir", "test"))
                self.assertEqual(sync.reviewed_problems(), [])


class Problems(unittest.TestCase):
    def problems(self, findings):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviewed.json"
            with mock.patch.object(sync, "REVIEWED", path):
                sync.save_reviewed(findings)
                return sync.reviewed_problems()

    def test_each_entry_must_say_who_decided_and_why(self):
        self.assertTrue(any("no reason" in p for p in self.problems(
            {"a" * 32: {"kind": "public-ip", "authorized_by": "x", "date": "2000-01-01"}})))

    def test_a_list_cannot_waive_a_secret(self):
        self.assertTrue(any("no review can" in p for p in self.problems(
            {"a" * 32: {"kind": "local-secret", "reason": "r", "authorized_by": "x", "date": "2000-01-01"}})))


if __name__ == "__main__":
    unittest.main()

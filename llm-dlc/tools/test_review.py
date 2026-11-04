#!/usr/bin/env python3
"""Tests for reviewed false positives and the allow list in sync.py. Run: python3 llm-dlc/tools/test_review.py
Values are split in the source so that this file's own transcript raises no finding."""
import io
import json
import os
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import redaction_rules
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
        open_now = {fid: {"level": "warn", "kind": "other-home-dir", "masked": sync._mask(HOME_A), "value": HOME_A,
                          "count": 1, "where": {"s"}}}
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


class Allowlist(unittest.TestCase):
    """The allow list: an agent proposes by id, a person approves, and neither needs a scan."""
    IP = "203.0." + "113.7"  # documentation range, which the rules do not treat as reserved

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.path, self.fid = tmp / "allowlist.json", sync.finding_id("public-ip", self.IP)
        self.cache = {self.fid: {"level": "warn", "kind": "public-ip", "value": self.IP, "count": 2, "where": ["s"]}}
        (tmp / "cache.json").write_text(json.dumps(self.cache))
        self.patches = [mock.patch.object(sync, "ALLOWLIST", self.path), mock.patch.object(sync, "REPO", tmp),
                        mock.patch.object(sync, "REVIEWED", tmp / "reviewed.json"),
                        mock.patch.object(sync, "FINDINGS_CACHE", tmp / "cache.json"),
                        mock.patch.object(sync, "open_findings", side_effect=AssertionError("scanned")),
                        mock.patch("sys.stdout", io.StringIO()), mock.patch("sys.stderr", io.StringIO())]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def as_person(self, answer=sync.CONFIRMATION):
        return mock.patch.object(sync, "person_at_terminal", return_value=True), \
            mock.patch("builtins.input", return_value=answer)

    def test_a_proposal_holds_no_value_and_does_not_hide_the_finding(self):
        self.assertEqual(sync.cmd_allow(["propose", self.fid[:8], "--reason", "a version"]), 0)
        self.assertNotIn(self.IP, self.path.read_text())
        self.assertEqual(sync.load_allowlist()[self.fid]["status"], "proposed")
        self.assertIn("public-ip", sync.Redactor().review_hits(line(self.IP)))
        errors, warnings = sync.allowlist_problems(sync.Redactor())
        self.assertEqual(errors, [])
        self.assertTrue(any("allow approve" in w for w in warnings))

    def test_an_agent_cannot_approve(self):
        sync.cmd_allow(["propose", self.fid[:8], "--reason", "a version"])
        with mock.patch.dict("os.environ", {"CLAUDECODE": "1"}):
            self.assertEqual(sync.cmd_allow(["approve"]), 1)
        self.assertEqual(sync.load_allowlist()[self.fid]["status"], "proposed")

    def test_a_person_approves_without_a_scan_and_the_value_is_left_out(self):
        sync.cmd_allow(["propose", self.fid[:8], "--reason", "a version"])
        terminal, answer = self.as_person("no")
        with terminal, answer:
            self.assertEqual(sync.cmd_allow(["approve"]), 1)
        terminal, answer = self.as_person()
        with terminal, answer:
            self.assertEqual(sync.cmd_allow(["approve"]), 0)
        entry = sync.load_allowlist()[self.fid]
        self.assertEqual((entry["status"], entry["value"]), ("approved", self.IP))
        r = sync.Redactor()
        self.assertEqual(r.review(line(self.IP)), [])
        self.assertEqual(r.skipped["public-ip"], 1)
        self.assertEqual(sync.allowlist_problems(r), ([], []))

    def test_a_person_can_add_a_value_before_it_is_found(self):
        terminal, answer = self.as_person()
        with terminal, answer:
            self.assertEqual(sync.cmd_allow(["add", self.IP, "--kind", "public-ip", "--reason", "a version"]), 0)
            self.assertEqual(sync.cmd_allow(["add", HOME_A, "--kind", "public-ip", "--reason", "x"]), 1)
        self.assertEqual(list(sync.load_allowlist()), [self.fid])

    def test_a_kind_the_redactor_removes_cannot_be_listed(self):
        address = "someone" + "@" + "corp.test"
        fid = sync.finding_id("email", address)
        sync.FINDINGS_CACHE.write_text(json.dumps({fid: {"level": "ERROR", "kind": "email", "value": address,
                                                         "count": 1, "where": ["s"]}}))
        self.assertEqual(sync.cmd_allow(["propose", fid[:8], "--reason", "x"]), 1)
        self.assertFalse(self.path.exists())

    def test_an_unknown_id_scans_once(self):
        with mock.patch.object(sync, "open_findings", return_value={}) as scan:
            self.assertEqual(sync.cmd_allow(["propose", "ffffffff", "--reason", "x"]), 1)
        scan.assert_called_once()

    def test_a_proposal_with_its_value_or_an_entry_with_the_wrong_id_is_an_error(self):
        base = {"kind": "public-ip", "reason": "r", "proposed_by": "a", "proposed_on": "2000-01-01"}
        sync.save_allowlist({self.fid: {**base, "status": "proposed", "value": self.IP},
                             "b" * 32: {**base, "status": "approved", "value": self.IP, "authorized_by": "p",
                                        "approved_on": "2000-01-01"}})
        errors, _ = sync.allowlist_problems(sync.Redactor())
        self.assertTrue(any("nobody has judged" in e for e in errors))
        self.assertTrue(any("does not match" in e for e in errors))


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


class Stamp(unittest.TestCase):
    current = redaction_rules.source_hash()

    def old_and_new_files(self, directory):
        old, new = Path(directory) / "old", Path(directory) / "new"
        old.write_text("x")
        new.write_text("x")
        os.utime(old, (1000, 1000))
        os.utime(new, (3000, 3000))
        return old, new

    def stamped(self, rules_hash):
        generated = datetime.fromtimestamp(2000, timezone.utc).isoformat()
        return (mock.patch.object(redaction_rules, "RULES_HASH", rules_hash),
                mock.patch.object(redaction_rules, "RULES_GENERATED", generated))

    def test_a_file_older_than_the_stamp_counts_as_checked(self):
        with tempfile.TemporaryDirectory() as d:
            old, new = self.old_and_new_files(d)
            hash_patch, date_patch = self.stamped(self.current)
            with hash_patch, date_patch:
                self.assertTrue(redaction_rules.older_than_stamp(old))
                self.assertFalse(redaction_rules.older_than_stamp(new))

    def test_rules_edited_since_the_stamp_void_its_date(self):
        with tempfile.TemporaryDirectory() as d:
            old, _ = self.old_and_new_files(d)
            hash_patch, date_patch = self.stamped("0" * 64)
            with hash_patch, date_patch:
                self.assertFalse(redaction_rules.older_than_stamp(old))

    def test_a_stamp_replaces_the_last_one_and_is_not_hashed(self):
        with tempfile.TemporaryDirectory() as d:
            copy = Path(d) / "rules.py"
            copy.write_text(Path(redaction_rules.__file__).read_text())
            with mock.patch.object(redaction_rules, "__file__", str(copy)):
                redaction_rules.write_stamp()
                redaction_rules.write_stamp()
                self.assertEqual(redaction_rules.source_hash(), self.current)
            text = copy.read_text()
            self.assertEqual(len(re.findall(r'^RULES_GENERATED = "\d', text, re.M)), 1)
            self.assertIn(f'RULES_HASH = "{self.current}"', text)

    def test_an_edit_above_the_stamp_changes_the_hash(self):
        with tempfile.TemporaryDirectory() as d:
            copy = Path(d) / "rules.py"
            text = Path(redaction_rules.__file__).read_text()
            copy.write_text(text.replace("REDACTION_POLICY = 4", "REDACTION_POLICY = 5"))
            with mock.patch.object(redaction_rules, "__file__", str(copy)):
                self.assertNotEqual(redaction_rules.source_hash(), self.current)


class Excerpts(unittest.TestCase):
    def setUp(self):
        self.r = sync.Redactor()

    def test_a_finding_and_its_neighbours_are_masked(self):
        text = f"before {HOME_A}/x and {HOME_B}/y after"
        excerpt = sync.masked_excerpt(self.r, text, text.index(HOME_A), len(HOME_A))
        self.assertNotIn(HOME_A, excerpt)
        self.assertNotIn(HOME_B, excerpt)
        self.assertIn("before", excerpt)

    def test_a_value_after_a_json_escape_is_masked_too(self):
        for escape in ("\\n", "\\\\n", "\\\\\\n"):
            text = "first" + escape + HOME_A + ": 0" + escape + HOME_B + ": 1"
            excerpt = sync.masked_excerpt(self.r, text, text.index(HOME_A), len(HOME_A))
            self.assertNotIn(HOME_A, excerpt)
            self.assertNotIn(HOME_B, excerpt)

    def test_a_word_cut_by_the_edge_is_dropped(self):
        text = "x" * 100 + " kept " + HOME_A + " kept " + "y" * 100
        excerpt = sync.masked_excerpt(self.r, text, text.index(HOME_A), len(HOME_A), reach=20)
        self.assertNotIn("xx", excerpt)
        self.assertNotIn("yy", excerpt)
        self.assertIn("kept", excerpt)

    def test_a_repeated_line_is_counted_each_time(self):
        _, reviewable = self.r.hits_of_text(line(HOME_A) + "\n" + line(HOME_A) + "\n")
        self.assertEqual(reviewable["other-home-dir"][HOME_A], 2)


if __name__ == "__main__":
    unittest.main()

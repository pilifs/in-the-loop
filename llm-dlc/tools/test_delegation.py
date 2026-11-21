#!/usr/bin/env python3
"""Tests for delegated redaction decisions (delegation.py): who the watcher is, what it may decide, and what makes
a decision stop counting. jj and the process table are stood in for; every value is made up, and split in the source
where the redactor would find it. Run: python3 llm-dlc/tools/test_delegation.py"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import artifacts
import delegation
import sync

IP = "203.0." + "113.21"                                              # public-ip: a documentation address
LONG = "single-twenty-example-fast-follow-Dq4Zx7" + "Kp2Lm9Nb"        # long-token: the shape of a key, made up
SESSION = "11111111-2222-4333-8444-555555555555"
WATCHER = {"pid": 4001, "start": 111, "comm": "claude", "boot": "boot-1"}
WORKER = {"pid": 4002, "start": 222, "comm": "claude", "boot": "boot-1"}


def line(text):
    return json.dumps({"text": text})


class Case(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = self.dir = Path(self.tmp.name)
        self.ids = {v: sync.finding_id(k, v) for k, v in (("public-ip", IP), ("long-token", LONG))}
        self.cache = {self.ids[IP]: {"level": "warn", "kind": "public-ip", "value": IP, "count": 1, "where": [SESSION[:8]]},
                      self.ids[LONG]: {"level": "warn", "kind": "long-token", "value": LONG, "count": 1, "where": [SESSION[:8]]}}
        (tmp / "cache.json").write_text(json.dumps(self.cache))
        self.published, self.files, self.me, self.out, self.err = {}, {}, WORKER, io.StringIO(), io.StringIO()

        def jj(*args):
            rev = args[args.index("-r") + 1]
            doc = self.published.get(Path(args[-1]).name) if rev == "base" else self.files.get((rev, args[-1]))
            text = doc if isinstance(doc, str) else json.dumps(doc) if doc is not None else ""
            return mock.Mock(returncode=0 if doc is not None else 1, stdout=text)
        self.patches = [mock.patch.object(sync, name, value) for name, value in {
            "ALLOWLIST": tmp / "llm-dlc" / "allowlist.json", "REPO": tmp, "REVIEWED": tmp / "llm-dlc" / "reviewed-findings.json",
            "STATE": tmp / "state", "FINDINGS_CACHE": tmp / "cache.json", "EXTRA_REDACTIONS": tmp / "redact.txt",
            "TRACES": tmp / "llm-dlc" / "traces"}.items()]
        self.patches += [mock.patch.object(sync, "has_jj", return_value=True), mock.patch.object(sync, "jj", side_effect=jj),
                         mock.patch.object(sync, "jj_commits", return_value=[{"commit_id": "base"}]),
                         mock.patch.object(sync, "commit_allowlist", return_value=0),
                         mock.patch.object(sync, "open_findings", side_effect=AssertionError("scanned")),
                         mock.patch.object(delegation, "client_process", side_effect=lambda pid=None: self.me),
                         mock.patch.object(delegation, "process", side_effect=lambda pid: {"pid": pid, "start": 111 if pid == 4001 else 222, "comm": "claude", "ppid": 1}),
                         mock.patch.object(delegation, "boot", return_value="boot-1"),
                         mock.patch.dict(os.environ, {"ITL_DELEGATION_KEY": str(tmp / "key"), "ITL_ORIGINALS_OFF": "1"}),
                         mock.patch("sys.stdout", self.out), mock.patch("sys.stderr", self.err)]
        for p in self.patches:
            p.start()
        (tmp / "llm-dlc").mkdir()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def as_person(self, answer=delegation.CONFIRM):
        return mock.patch.object(sync, "person_at_terminal", return_value=True), mock.patch("builtins.input", return_value=answer)

    def said(self) -> str:
        return self.out.getvalue() + self.err.getvalue()

    def grant(self, *extra, run="made-up-run"):
        """The watcher asks, and a person grants it."""
        self.me = WATCHER
        self.assertEqual(delegation.cmd_delegate(sync, ["request", "--run", run]), 0)
        code = re.findall(r"request ([0-9a-f]{6}):", self.out.getvalue())[-1]
        terminal, answer = self.as_person()
        with terminal, answer:
            self.assertEqual(delegation.cmd_delegate(sync, ["on", code, *extra]), 0)

    def propose(self, value, reason="a made-up origin"):
        self.assertEqual(sync.cmd_allow(["propose", self.ids[value][:8], "--reason", reason]), 0)

    def approve(self, value, evidence, reason="a fixture of the tests"):
        return delegation.cmd_delegate(sync, ["approve", self.ids[value][:8], "--evidence", evidence, "--reason", reason])

    def ledger(self) -> list[dict]:
        return [json.loads(row) for row in delegation.ledger_path(sync).read_text().splitlines()]


class Who(Case):
    def test_off_by_default_the_watcher_form_is_refused_and_a_decision_stays_a_persons(self):
        self.propose(IP)
        self.me = WATCHER
        self.assertEqual(self.approve(IP, "tracked-file:lib/fixture.txt"), 1)
        self.assertIn("delegation is off", self.err.getvalue())
        self.assertEqual(sync.load_allowlist()[self.ids[IP]]["status"], "proposed")
        self.assertEqual(delegation.cmd_delegate(sync, ["status"]), 0)
        self.assertIn("delegation is off: redaction decisions are a person's", self.out.getvalue())

    def test_a_person_grants_one_request_and_only_that_client_process_is_the_watcher(self):
        self.me = WATCHER
        delegation.cmd_delegate(sync, ["request", "--run", "made-up-run"])
        code = re.findall(r"request ([0-9a-f]{6}):", self.out.getvalue())[-1]
        self.assertEqual(delegation.cmd_delegate(sync, ["on", code]), 1)  # an agent's shell: no terminal, no person
        self.assertIsNone(delegation.actor(sync))
        terminal, declined = self.as_person("yes")
        with terminal, declined:
            self.assertEqual(delegation.cmd_delegate(sync, ["on", code]), 1)
        self.assertFalse(delegation.enabled(sync))
        terminal, answer = self.as_person()
        with terminal, answer:
            self.assertEqual(delegation.cmd_delegate(sync, ["on", "000000"]), 1)  # no such request
            self.assertEqual(delegation.cmd_delegate(sync, ["on", code]), 0)
        self.assertEqual(delegation.actor(sync)["run"], "made-up-run")
        # Another session is not the watcher, whatever its environment says, and neither is a later process that
        # got the same pid.
        self.me = WORKER
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "the-watchers-session", "ITL_WATCHER": "1"}):
            self.assertIsNone(delegation.actor(sync))
        self.assertIn("not started by the designated watcher", delegation.why_not(sync))
        self.me = {**WATCHER, "start": 999}
        self.assertIsNone(delegation.actor(sync))
        self.me = {**WATCHER, "boot": "boot-2"}
        self.assertIsNone(delegation.actor(sync))
        self.me = None  # no client session at all: a person's own shell, a cron job
        self.assertIsNone(delegation.actor(sync))
        self.assertEqual(delegation.cmd_delegate(sync, ["request", "--run", "x"]), 1)
        self.me = WATCHER
        self.assertEqual(delegation.cmd_delegate(sync, ["off"]), 0)
        self.assertIsNone(delegation.actor(sync))

    def test_a_request_whose_client_process_ended_cannot_be_granted(self):
        self.me = {**WATCHER, "pid": 4777}  # the stand-in says pid 4777 started at 222, not 111: another process now
        delegation.cmd_delegate(sync, ["request", "--run", "made-up-run"])
        code = re.findall(r"request ([0-9a-f]{6}):", self.out.getvalue())[-1]
        terminal, answer = self.as_person()
        with terminal, answer:
            self.assertEqual(delegation.cmd_delegate(sync, ["on", code]), 1)
        self.assertIn("has ended", self.err.getvalue())


class Decide(Case):
    def test_the_watcher_approves_a_proposal_with_checked_evidence_and_no_value_is_printed(self):
        self.grant()
        self.propose(IP)
        self.propose(LONG)
        self.files[("@-", "lib/fixture.txt")] = f"address {IP}\nkey {LONG}\n"
        self.assertEqual(delegation.cmd_delegate(sync, ["approve", self.ids[IP][:8], self.ids[LONG][:8], "--evidence",
                                                        "tracked-file:lib/fixture.txt", "--reason", "fixtures", "of", "the", "tests"]), 0, self.err.getvalue())
        entries = sync.load_allowlist()
        entry = entries[self.ids[IP]]
        self.assertEqual((entry["status"], entry["actor"], entry["authorized_by"], entry["reason"], entry["evidence"]["verified"]),
                         ("approved", "watcher", "the watcher of made-up-run", "fixtures of the tests", True))
        self.assertEqual(entries[self.ids[LONG]]["status"], "approved")
        self.assertEqual(sync.decision_problems(), [])
        self.assertEqual(sync.allowlist_problems(sync.Redactor())[0], [])
        self.assertEqual(sync.Redactor().review(line(IP + " " + LONG)), [])  # the watcher's decision: the values are left in
        rows = self.ledger()
        self.assertEqual([(r["action"], r["actor"], r["run"], r["finding"], r["policy"]) for r in rows],
                         [("allow", "watcher", "made-up-run", self.ids[v], sync.REDACTION_POLICY) for v in (IP, LONG)])
        self.assertEqual(rows[0]["entry"], sync._decision_digest(entry))
        for text in (delegation.ledger_path(sync).read_text(), self.said()):
            self.assertNotIn(IP, text)
            self.assertNotIn(LONG, text)
        # A worker's command, the same minute: refused, though the delegation is on.
        self.me = WORKER
        self.assertEqual(self.approve(IP, "tracked-file:lib/fixture.txt"), 1)
        self.assertIn("not started by the designated watcher", self.err.getvalue())

    def test_a_long_token_needs_an_origin_that_is_checked_and_what_the_redactor_removes_stays_refused(self):
        self.grant()
        self.propose(LONG)
        self.propose(IP)
        self.assertEqual(self.approve(LONG, "public:https://example.org/where-it-is-published"), 1)
        self.assertIn("not enough for a long-token", self.err.getvalue())
        self.assertEqual(self.approve(LONG, "it-looks-harmless"), 1)
        self.assertIn("evidence is one of", self.err.getvalue())
        self.files[("@-", "lib/fixture.txt")] = "nothing of the kind\n"
        self.assertEqual(self.approve(LONG, "tracked-file:lib/fixture.txt"), 1)
        self.assertIn("the value is not in lib/fixture.txt", self.err.getvalue())
        self.assertEqual(self.approve(LONG, "main-file:lib/absent.txt"), 1)
        self.assertEqual(sync.load_allowlist()[self.ids[LONG]]["status"], "proposed")
        self.assertFalse(delegation.ledger_path(sync).exists())
        # Another kind may rest on a stated public origin, and the record says it was not checked here.
        self.assertEqual(self.approve(IP, "public:https://example.org/documentation-range"), 0, self.err.getvalue())
        self.assertFalse(self.ledger()[0]["evidence"]["verified"])
        # A kind the redactor removes cannot be on the allow list, whoever asks.
        address = "someone" + "@" + "corp.test"
        fid = sync.finding_id("email", address)
        entries = sync.load_allowlist()
        entries[fid] = {"kind": "email", "masked": "x", "status": "proposed", "reason": "r", "proposed_by": "agent", "proposed_on": "2000-01-01"}
        sync.save_allowlist(entries)
        (self.dir / "cache.json").write_text(json.dumps({**self.cache, fid: {"level": "ERROR", "kind": "email", "value": address, "count": 1, "where": []}}))
        self.files[("@-", "lib/fixture.txt")] = address
        self.assertEqual(delegation.cmd_delegate(sync, ["approve", fid[:8], "--evidence", "tracked-file:lib/fixture.txt", "--reason", "r"]), 1)
        self.assertIn("is not a kind the allow list takes", self.err.getvalue())

    def test_a_forged_entry_an_edited_record_changed_bytes_a_stale_policy_and_delegation_off_all_fail(self):
        self.grant()
        # An entry written into the file by hand, dressed as the watcher's: no line of the record names it.
        forged = {"kind": "public-ip", "masked": sync._mask(IP), "status": "approved", "reason": "made up", "proposed_by": "agent",
                  "proposed_on": "2000-01-01", "value": IP, "authorized_by": "the watcher of made-up-run", "approved_on": "2000-01-01", "actor": "watcher"}
        sync.save_allowlist({self.ids[IP]: forged})
        self.assertEqual(len(sync.decision_problems()), 1)
        self.assertIn("public-ip", sync.Redactor().review_hits(line(IP)))  # and it waives nothing
        sync.save_allowlist({})
        self.propose(IP)
        self.files[("@-", "lib/fixture.txt")] = IP
        self.assertEqual(self.approve(IP, "tracked-file:lib/fixture.txt"), 0, self.err.getvalue())
        good = sync.load_allowlist()
        self.assertEqual(sync.decision_problems(), [])
        # The entry's bytes changed after the decision.
        sync.save_allowlist({self.ids[IP]: {**good[self.ids[IP]], "reason": "widened afterwards"}})
        self.assertEqual(len(sync.decision_problems()), 1)
        sync.save_allowlist(good)
        self.assertEqual(sync.decision_problems(), [])
        # A line added to the record by something other than the command: named, and it counts for nothing.
        path = delegation.ledger_path(sync)
        record = path.read_text()
        other = sync.finding_id("public-ip", "203.0." + "113.99")
        path.write_text(record + json.dumps({**self.ledger()[0], "seq": 2, "finding": other, "mac": "0" * 64}) + "\n")
        (problem,) = sync.decision_problems()
        self.assertIn("does not verify from line 2 of 2", problem)
        self.assertNotIn(other, delegation.recorded(sync).get("allowlist.json", {}))
        # A recorded line edited: nothing from it on can be shown to follow, so the decision it held lapses.
        path.write_text(record.replace("a fixture of the tests", "a different reason"))
        self.assertEqual(len(sync.decision_problems()), 2)
        path.write_text(record)
        self.assertEqual(sync.decision_problems(), [])
        # The redaction policy moved on: a decision taken under the old one is evaluated again by whoever decides now.
        with mock.patch.object(sync, "REDACTION_POLICY", sync.REDACTION_POLICY + 1):
            self.assertEqual(len(sync.decision_problems()), 1)
        self.assertEqual(sync.decision_problems(), [])
        # Delegation off: what is not yet on main stops counting at once; what main holds stands.
        self.assertEqual(delegation.cmd_delegate(sync, ["off"]), 0)
        self.assertEqual(len(sync.decision_problems()), 1)
        self.published["allowlist.json"] = {"schema": sync.ALLOWLIST_SCHEMA, "entries": good}
        self.assertEqual(sync.decision_problems(), [])
        self.published.clear()
        self.grant("--fresh")  # a new grant that clears trust: earlier decisions are not carried over
        self.assertEqual(len(sync.decision_problems()), 1)
        terminal, answer = self.as_person(sync.CONFIRMATION)
        with terminal, answer:  # a person vouches, as for any decision with no record
            self.assertEqual(sync.cmd_allow(["vouch"]), 0)
        self.assertEqual(sync.decision_problems(), [])


class Contain(Case):
    def log(self, text: str, url: str | None = None) -> str:
        data = line(text).encode() + b"\n"
        sha = hashlib.sha256(data).hexdigest()
        path = sync.log_path(SESSION, sha)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(data, mtime=0))
        m = sync.load_manifest(SESSION) or {"schema": sync.SCHEMA, "session_id": SESSION, "logs": {}}
        m["logs"][sha] = {"bytes": len(data), "url": url}
        sync.save_manifest(SESSION, m)
        return sha

    def test_a_log_is_withheld_before_publication_and_sealed_in_restricted_custody(self):
        self.grant()
        private, public = self.log("an ambiguous value"), self.log("already out", url="https://cdn.example/x")
        env = {"ITL_ORIGINALS_HOME": str(self.dir / "originals"), "ITL_ORIGINALS_RESERVE": "0", "ITL_ORIGINALS_UPLOAD": "manual"}
        with mock.patch.dict(os.environ, env):
            os.environ.pop("ITL_ORIGINALS_OFF")
            self.me = WORKER
            self.assertEqual(delegation.cmd_delegate(sync, ["withhold", SESSION, private, "--reason", "r"]), 1)
            self.assertEqual(sync.cmd_review(["withhold", SESSION, private, "--reason", "r"]), 1)  # the person's form, from an agent
            self.assertTrue(sync.log_path(SESSION, private).exists())
            self.me = WATCHER
            self.assertEqual(delegation.cmd_delegate(sync, ["withhold", SESSION, private, "--reason", "it may name a customer"]), 0, self.err.getvalue())
            archive = artifacts.Archive()
            (sealed,) = archive.rows(kind="withheld-log")
            archive.close()
        self.assertEqual((sealed["access"], sealed["session"]), ("restricted", SESSION))
        self.assertFalse(sync.log_path(SESSION, private).exists())
        withdrawn = sync.load_manifest(SESSION)["logs"][private]["withdrawn"]
        self.assertEqual(withdrawn, "withheld before publication by the watcher of made-up-run: it may name a customer")
        self.assertEqual([(r["action"], r["finding"]) for r in self.ledger()], [("private-only", f"{SESSION}/{private}")])
        # A published log is not the watcher's to take down.
        self.assertEqual(delegation.cmd_delegate(sync, ["withhold", SESSION, public, "--reason", "r"]), 1)
        self.assertIn("taking it down is a person's", self.err.getvalue())
        self.assertTrue(sync.log_path(SESSION, public).exists())

    def test_a_masked_value_is_out_of_later_logs_unpublished_logs_are_withheld_and_published_ones_are_one_escalation(self):
        self.grant()
        waiting, out, clean = self.log(f"key {LONG}"), self.log(f"earlier {LONG}", url="https://cdn.example/y"), self.log("nothing")
        self.assertEqual(delegation.cmd_delegate(sync, ["mask", self.ids[LONG][:8], "--reason", "origin unknown"]), 0, self.err.getvalue())
        self.assertEqual(oct(sync.EXTRA_REDACTIONS.stat().st_mode & 0o777), "0o600")
        redact = sync.Redactor()
        self.assertNotIn(LONG, redact.string(f"key {LONG}"))
        self.assertTrue(redact.leaks(line(LONG)))  # in a stored log it is now something the redactor would change
        logs = sync.load_manifest(SESSION)["logs"]
        self.assertIn("withheld before publication", logs[waiting]["withdrawn"])
        self.assertFalse(sync.log_path(SESSION, waiting).exists())
        self.assertNotIn("withdrawn", logs[clean])
        self.assertTrue(sync.log_path(SESSION, out).exists())  # published: a person's call
        (escalation,) = delegation.open_escalations(sync)
        self.assertIn("1 published log(s) hold a value that was masked", escalation)
        self.assertIn(f"{SESSION[:8]}/{out[:12]}", escalation)
        self.assertIn("the watcher of made-up-run", escalation)
        self.assertEqual({r["action"] for r in self.ledger()}, {"private-only", "mask"})
        for text in (escalation, self.said(), delegation.ledger_path(sync).read_text(), delegation.escalations_path(sync).read_text()):
            self.assertNotIn(LONG, text)
        ident = re.search(r"escalation ([0-9a-f]{6})", escalation)[1]
        self.assertEqual(sync.cmd_review(["close", ident, "--reason", "left as it is"]), 1)  # an agent cannot close it
        terminal, answer = self.as_person()
        with terminal, answer:
            self.assertEqual(sync.cmd_review(["close", ident, "--reason", "left as it is"]), 0)
        self.assertEqual(delegation.open_escalations(sync), [])

    def test_anyone_escalates_with_masked_ids_only(self):
        self.me = WORKER
        self.assertEqual(sync.cmd_review(["escalate", self.ids[LONG][:8], "--reason", "looks like a live key", "--contained", "nothing yet"]), 0)
        (escalation,) = delegation.open_escalations(sync)
        self.assertIn("looks like a live key", escalation)
        self.assertIn(self.ids[LONG][:8], escalation)
        self.assertNotIn(LONG, escalation + delegation.escalations_path(sync).read_text())


if __name__ == "__main__":
    unittest.main()

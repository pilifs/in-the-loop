#!/usr/bin/env python3
"""Tests for the loops' run records in sync.py: feature-loop.sh's records in llm-dlc/loop-summaries/
published, redacted, beside the session each belongs to, linked from its summary and checked.
Run: python3 llm-dlc/tools/test_runs.py
Every value here is made up, and those that look like secrets are assembled at run time, so that
this file's own transcript raises no finding."""
import io
import json
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import redactor
import sync

# No test reaches R2: the real token file, if this machine has one, is never read.
sync.R2_CREDENTIALS = Path(tempfile.gettempdir()) / "llm-traces-tests-no-r2-credentials"

USER = "qzuser"
HOME = "/ho" + "me/" + USER
SECRET = "made" + "up" + "-local-" + "value-0002"
PAIRS = [(HOME, "~", 0, "home"), (SECRET, "[REDACTED:local-secret]", 0, "local-secret")]
SID = "0f0f0f0f-1111-4222-8333-444455556666"
OTHER = "0e0e0e0e-1111-4222-8333-444455556666"
NAME = "2026-11-01-100000-made-up-loop.md"
PUBLISHES_RUNS = sync.publishes_runs  # the real one: setUp replaces it


class MadeUpRedactor(sync.Redactor):
    """sync's Redactor with these tests' made-up literals instead of this machine's."""

    def __init__(self, reviewed=None):
        redactor.Redactor.__init__(self, (PAIRS, USER), reviewed or {})


def record(sid: str = SID, ended: bool = True, cycles: int = 2) -> str:
    """A record as feature-loop.sh writes one, with a made-up home in the brief's path and a made-up
    secret in the session's closing summary."""
    lines = ["# Feature loop: made-up-loop", "",
             f"Started 2026-11-01 10:00:00 UTC, no limit on cycles, session {sid}, made-up-model at high effort, "
             "after change kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk.", "",
             f"> Work on the brief in `{HOME}/code/repo/llm-dlc/loops/made-up.md`. Read it in full now.", "",
             f"Brief `{HOME}/code/repo/llm-dlc/loops/made-up.md` at sha256 {'ab' * 32}.", "",
             "## Commits", ""]
    for n in range(1, cycles + 1):
        lines += [f"- cycle {n}, 2026-11-01 10:0{n}:00, `kkkkkkkkkkk{n}`: Made-up change {n}",
                  "  - decided to continue: more to do", ""]
    if ended:
        lines += ["## Summary", "", f"Made up, with a value that must not be published: {SECRET}.", "",
                  f"Ended 2026-11-01 11:00:00 after {cycles} cycle(s): the session decided the work was done."]
    return "\n".join(lines) + "\n"


class Runs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.src = root / "projects"
        self.src.mkdir()
        repo = root / "repo"
        self.summaries = repo / "llm-dlc" / "loop-summaries"
        self.summaries.mkdir(parents=True)
        state = root / "state"
        self.patches = [mock.patch.object(sync, "REPO", repo),
                        mock.patch.object(sync, "TRACES", repo / "llm-dlc" / "traces"),
                        mock.patch.object(sync, "SESSION_NOTES", repo / "llm-dlc" / "session-notes"),
                        mock.patch.object(sync, "INDEX", repo / "llm-dlc" / "index.json"),
                        mock.patch.object(sync, "TRACES_README", repo / "llm-dlc" / "traces" / "README.md"),
                        mock.patch.object(sync, "METRICS_ROLLUP", repo / "llm-dlc" / "traces" / "metrics.json"),
                        mock.patch.object(sync, "REVIEWED", repo / "llm-dlc" / "reviewed.json"),
                        mock.patch.object(sync, "ALLOWLIST", repo / "llm-dlc" / "allowlist.json"),
                        mock.patch.object(sync, "LOOP_SUMMARIES", self.summaries),
                        mock.patch.object(sync, "publishes_runs", return_value=True),
                        mock.patch.object(sync, "claude_project_dir", return_value=self.src),
                        mock.patch.object(sync, "Redactor", MadeUpRedactor),
                        mock.patch.object(sync, "has_jj", return_value=False),
                        mock.patch.object(sync, "write_index"),
                        mock.patch.dict(sync.os.environ, {"CLAUDE_CODE_SESSION_ID": ""}),
                        mock.patch("sys.stdout", io.StringIO())]
        for name in ("STATE", "TRANSCRIPT_CACHE", "SCAN_CACHE", "CHECK_CACHE", "SYNC_CACHE", "PERF_LOG", "UPLOADS"):
            self.patches.append(mock.patch.object(sync, name, state / name.lower()))
        for p in self.patches:
            p.start()
        self.transcript(SID)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def transcript(self, sid: str):
        path = self.src / f"{sid}.jsonl"
        path.write_text(json.dumps({"type": "user", "timestamp": "2026-11-01T10:00:00Z",
                                    "message": {"role": "user", "content": "made-up prompt"}}) + "\n")
        old = time.time() - 2 * sync.LIVE_SECONDS
        sync.os.utime(path, (old, old))

    def copy(self, sid: str = SID, name: str = NAME) -> Path:
        return sync.TRACES / sid / "runs" / name

    def summary(self, sid: str = SID) -> str:
        return sync.summary_path(sid).read_text()

    def test_a_record_is_published_redacted_beside_its_session_and_linked_from_its_summary(self):
        (self.summaries / NAME).write_text(record())
        sync.cmd_sync([])
        self.assertTrue(self.copy().exists(), "the record is not published")
        text = self.copy().read_text()
        self.assertNotIn(HOME, text)
        self.assertNotIn(SECRET, text)
        self.assertIn("`~/code/repo/llm-dlc/loops/made-up.md`", text)
        self.assertIn("[REDACTED:local-secret]", text)
        self.assertEqual(text, "\n".join(MadeUpRedactor().string(ln) for ln in record().split("\n")),
                         "the copy is the record, redacted line by line, and nothing else")
        summary = self.summary()
        self.assertIn(f"](runs/{NAME})", summary)
        line = next(ln for ln in summary.splitlines() if f"runs/{NAME}" in ln)
        for part in ("2026-11-01 10:00:00 UTC", "2026-11-01 11:00:00", "2 cycles",
                     "the session decided the work was done"):
            self.assertIn(part, line)
        self.assertNotIn(SECRET, summary)

    def test_a_record_still_being_written_is_republished_as_it_grows(self):
        (self.summaries / NAME).write_text(record(ended=False, cycles=1))
        sync.cmd_sync([])
        self.assertIn("Made-up change 1", self.copy().read_text())
        line = next(ln for ln in self.summary().splitlines() if f"runs/{NAME}" in ln)
        self.assertIn("1 cycle", line)
        self.assertIn("No end recorded", line)
        (self.summaries / NAME).write_text(record(ended=True, cycles=2))
        sync.cmd_sync([])
        self.assertIn("Made-up change 2", self.copy().read_text())
        line = next(ln for ln in self.summary().splitlines() if f"runs/{NAME}" in ln)
        self.assertIn("2 cycles", line)
        self.assertNotIn("No end recorded", line)
        self.assertEqual(self.summary().count(f"runs/{NAME}"), 1)

    def test_a_session_whose_transcript_is_elsewhere_is_linked_too(self):
        """A stream's session, merged in: its trace is here, its transcript in its workspace's project."""
        sync.cmd_sync([])
        d = sync.session_dir(OTHER)
        d.mkdir(parents=True)
        sync.manifest_path(OTHER).write_text(sync.manifest_path(SID).read_text().replace(SID, OTHER))
        merged = self.summary().replace(SID, OTHER)
        sync.summary_path(OTHER).write_text(merged)
        (self.summaries / NAME).write_text(record(sid=OTHER))
        sync.cmd_sync([])
        self.assertTrue(self.copy(OTHER).exists())
        self.assertIn(f"](runs/{NAME})", self.summary(OTHER))
        self.assertIn("## Changes", self.summary(OTHER))
        sync.cmd_sync([])
        self.assertEqual(self.summary(OTHER).count(f"runs/{NAME}"), 1, "splicing again changes nothing")
        self.assertNotIn(f"runs/{NAME}", self.summary(SID))

    def test_check_scans_the_copies_and_a_finding_in_one_is_an_error(self):
        (self.summaries / NAME).write_text(record())
        sync.cmd_sync([])
        errors, warnings, _, _ = sync.check_sessions(sync.all_manifests(), MadeUpRedactor(), False)
        self.assertEqual([e for e in errors + warnings if "runs/" in e], [])
        self.copy().write_text(record())  # as if published raw
        errors, _, _, _ = sync.check_sessions(sync.all_manifests(), MadeUpRedactor(), False)
        self.assertTrue([e for e in errors if f"runs/{NAME}" in e and "local-secret" in e], errors)
        self.assertIn(str(self.copy().relative_to(sync.REPO)), sync.checked_files(sync.all_manifests()))
        scanned = [where for where, _, _, content, _ in sync.scan_targets(MadeUpRedactor(), True, None)
                   if SECRET.encode() in (content if isinstance(content, bytes) else content())]
        self.assertTrue(scanned, "scan does not see the copies")

    def test_only_records_of_sessions_traced_here_are_published_and_the_rest_noted(self):
        (self.summaries / NAME).write_text(record(sid=OTHER))
        (self.summaries / "made-up-integration.md").write_text("# Integration check of made-up.md\n\nsession " + SID + "\n")
        (self.summaries / "2026-11-01-110000-no-session.md").write_text("# Feature loop: x\n\nStarted somewhere.\n")
        sync.cmd_sync([])
        self.assertFalse(sync.TRACES.joinpath(OTHER).exists())
        self.assertEqual(list(sync.session_dir(SID).glob("runs/*")), [])
        notes = sync.run_notes()
        self.assertTrue(any(OTHER in n and NAME in n for n in notes), notes)
        self.assertTrue(any("no-session" in n for n in notes), notes)
        self.assertFalse(any("integration" in n for n in notes), notes)

    def test_a_stream_workspace_publishes_no_record(self):
        (self.summaries / NAME).write_text(record())
        with mock.patch.object(sync, "publishes_runs", return_value=False):
            sync.cmd_sync([])
            self.assertFalse(self.copy().exists())
            self.assertNotIn("runs/", self.summary())
            self.assertTrue(any("default workspace" in n for n in sync.run_notes()))

    def test_the_default_workspace_is_told_by_its_store_without_running_jj(self):
        jjdir = sync.REPO / ".jj"
        self.assertTrue(PUBLISHES_RUNS(), "a checkout without jj publishes")
        jjdir.mkdir()
        (jjdir / "repo").mkdir()
        with mock.patch.object(sync.subprocess, "run", side_effect=AssertionError("ran a process")):
            self.assertTrue(PUBLISHES_RUNS(), "the workspace that holds the repository publishes")
            (jjdir / "repo").rmdir()
            (jjdir / "repo").write_text("../../made-up-default/.jj/repo")
            self.assertFalse(PUBLISHES_RUNS(), "a workspace added to it does not")

    def test_a_copy_left_behind_by_a_changed_record_is_noted_until_the_next_sync(self):
        (self.summaries / NAME).write_text(record(ended=False))
        sync.cmd_sync([])
        self.assertEqual(sync.run_notes(), [])
        (self.summaries / NAME).write_text(record())
        self.assertTrue(any(NAME in n and "changed since" in n for n in sync.run_notes()))
        sync.cmd_sync([])
        self.assertEqual(sync.run_notes(), [])



class Collect(unittest.TestCase):
    """run_records.collect: a stream's records copied into the default workspace, which alone publishes
    them, as run-streams.sh does after each of a stream's runs and before the merge."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.stream, self.default = root / "repo-stream", root / "repo"
        self.src, self.dest = (d / "llm-dlc" / "loop-summaries" for d in (self.stream, self.default))
        self.src.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def collect(self):
        import run_records
        with mock.patch("sys.stdout", io.StringIO()) as out:
            copied = run_records.collect(self.stream, self.default)
        return copied, out.getvalue()

    def test_a_streams_records_are_copied_in_and_nothing_else(self):
        (self.src / NAME).write_text(record(ended=False))
        (self.src / "made-up-integration.md").write_text("# Integration check of a made-up brief\n")
        copied, _ = self.collect()
        self.assertEqual(copied, [NAME])
        self.assertEqual((self.dest / NAME).read_text(), record(ended=False))
        self.assertFalse((self.dest / "made-up-integration.md").exists())
        self.assertEqual(self.collect()[0], [], "a copy that is current is left as it is")

    def test_a_record_that_grew_replaces_its_copy(self):
        (self.src / NAME).write_text(record(ended=False, cycles=1))
        self.collect()
        (self.src / NAME).write_text(record(ended=True, cycles=1))
        self.assertEqual(self.collect()[0], [NAME])
        self.assertEqual((self.dest / NAME).read_text(), record(ended=True, cycles=1))
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), [NAME], "no temporary file is left")

    def test_a_copy_that_is_not_a_start_of_the_record_is_left_and_reported(self):
        (self.src / NAME).write_text(record(cycles=2))
        self.dest.mkdir(parents=True)
        (self.dest / NAME).write_text(record(cycles=1) + "edited here\n")
        copied, out = self.collect()
        self.assertEqual(copied, [])
        self.assertEqual((self.dest / NAME).read_text(), record(cycles=1) + "edited here\n")
        self.assertIn(f"{NAME}: not copied", out)

    def test_the_default_workspace_collects_nothing_from_itself(self):
        (self.src / NAME).write_text(record())
        import run_records
        self.assertEqual(run_records.collect(self.stream, self.stream), [])

    def test_the_copies_are_what_sync_publishes(self):
        (self.src / NAME).write_text(record())
        self.collect()
        with mock.patch.object(sync, "LOOP_SUMMARIES", self.dest):
            self.assertEqual(sync.run_records(), [(self.dest / NAME, SID)])

if __name__ == "__main__":
    unittest.main()

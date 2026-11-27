#!/usr/bin/env python3
"""The status and grouping of sessions in llm-dlc/README.md's table (VF-074): a session that ran in another
workspace's folder and went idle is shown ended, and a standing session is listed under its role, apart from the
ordinary rows. On a made-up repository folder and home, with made-up sessions."""

import contextlib
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import sync

README = f"# Made-up repo\n\nIntro line.\n\n{sync.INDEX_BEGIN}\n{sync.INDEX_END}\n\nClosing line.\n"
A, B, C, D = (f"{n}" * 8 + "-0000-4000-8000-" + f"{n}" * 12 for n in "abcd")


class SessionStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        root, self.home = base / "repo", base / "home"
        llm = root / "llm-dlc"
        values = {"REPO": root, "CHANGES": llm, "TRACES": llm / "traces", "INDEX": llm / "index.json",
                  "CHANGES_README": llm / "README.md", "TRACES_README": llm / "traces" / "README.md",
                  "METRICS_ROLLUP": llm / "traces" / "metrics.json", "STANDING": llm / "standing-sessions.json",
                  "DECISIONS": llm / "decisions",
                  "STATE": base / "state"}
        for name, value in values.items():
            p = mock.patch.object(sync, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = mock.patch.dict(os.environ, {"HOME": str(self.home), "CODEX_HOME": str(self.home / ".codex"),
                                         "CLAUDE_CODE_SESSION_ID": ""})
        p.start()
        self.addCleanup(p.stop)
        sync.TRACES.mkdir(parents=True)
        sync.CHANGES_README.write_text(README)
        for p in (mock.patch.object(sync, "render_traces_readme", lambda manifests: ""),
                  mock.patch.object(sync, "metrics_files", lambda manifests: {}),
                  mock.patch.object(sync, "render_rollup", lambda found: ""),
                  mock.patch.object(sync, "render_loops", lambda found: ("", "")),
                  mock.patch.object(sync.decisions, "render_all", lambda folder: None)):
            p.start()
            self.addCleanup(p.stop)

    def session(self, sid, status, ended="2026-01-01T01:00:00Z", title="Made-up"):
        sync.session_dir(sid).mkdir(parents=True, exist_ok=True)
        sync.manifest_path(sid).write_text(json.dumps({
            "schema": sync.SCHEMA, "session_id": sid, "title": title, "status": status,
            "started": "2026-01-01T00:00:00Z", "ended": ended, "stats": {"turns": 1}, "log": {"sha256": "a" * 64},
            "commits": []}) + "\n")

    def transcript(self, sid, folder, age):
        path = self.home / ".claude" / "projects" / folder / f"{sid}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n")
        os.utime(path, (time.time() - age, time.time() - age))

    def test_an_idle_session_from_another_workspace_is_ended_and_a_live_one_kept(self):
        self.session(A, "open")                               # idle, its transcript in another workspace's folder
        self.transcript(A, "-made-up-other-workspace", 3600)
        self.session(B, "open")                               # still writing in another workspace
        self.transcript(B, "-made-up-other-workspace", 10)
        self.session(C, "open")                               # no transcript here: its manifest's last activity
        self.session(D, "open")                               # this checkout's own: the sync loop's to judge
        self.assertEqual(sync.end_idle_elsewhere({D}), [A, C])
        status = {sid: m["status"] for sid, m in sync.all_manifests().items()}
        self.assertEqual(status, {A: "ended", B: "open", C: "ended", D: "open"})
        self.session(C, "open", ended=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        self.assertEqual(sync.end_idle_elsewhere({D}), [], "a session with no transcript here, active just now")

    def test_a_session_from_another_workspace_is_found_and_keeps_its_workspace(self):
        # 2026-11-27: `sync.py sync SESSION` could not re-render the Fable session's manifest after a merge left it in
        # conflict, because its transcript was in another workspace's project folder.
        self.transcript(A, "-made-up-other-workspace", 0)
        p = mock.patch.object(sync, "asked_threads", lambda: frozenset())  # which would ask jj
        p.start()
        self.addCleanup(p.stop)
        found = sync.transcript_of(A)
        self.assertEqual(found.parent.name, "-made-up-other-workspace")
        with mock.patch.object(sync, "codex_transcripts", lambda: []):
            self.assertFalse(sync.own_transcript(found))
            here = sync.claude_project_dir() / f"{B}.jsonl"
            self.assertTrue(sync.own_transcript(here))
            self.assertEqual(sync.transcript_of(B), here, "none anywhere: this checkout's own name, as before")

    def test_a_standing_session_is_listed_under_its_role_and_returns_when_it_ends(self):
        self.session(A, "open", title="Its first topic")
        self.session(B, "ended", title="An ordinary session")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(sync.cmd_standing([A, "the", "advisor"]), 0)
            self.assertEqual(sync.cmd_standing(["not-a-session", "x"]), 2)
        table = sync.CHANGES_README.read_text()
        standing, ordinary = table.split("**Every other session:**")
        self.assertIn(f"| the advisor | {sync._when('2026-01-01T00:00:00Z')} | [{A[:8]}]", standing)
        self.assertEqual(sync.standing_sessions()[A]["role"], "the advisor")
        self.assertNotIn("Its first topic", table, "a standing session is not an ordinary row")
        self.assertIn("An ordinary session", ordinary)
        self.assertEqual(json.loads(sync.INDEX.read_text())["sessions"][0]["role"], "the advisor")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(sync.cmd_standing(["--end", A]), 0)
        table = sync.CHANGES_README.read_text()
        self.assertNotIn("Standing sessions", table)
        self.assertIn("Its first topic", table)


if __name__ == "__main__":
    unittest.main()

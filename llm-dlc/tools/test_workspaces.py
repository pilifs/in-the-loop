#!/usr/bin/env python3
"""sync.py across jj workspaces: what one workspace's `check` makes of commits only another holds, and
`sync.py regenerate` settling the conflicts that two lines' generated trace files make when merged.

Each test builds a real colocated jj repository in a temporary folder, with made-up sessions: the
behaviour under test is jj's (which commits a revset reaches, what a merge leaves in conflict)."""

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import decisions
import metrics
import sync

PRICING = sync.PRICING  # the real price list, read only
README = f"# Made-up repo\n\nIntro line.\n\n{sync.INDEX_BEGIN}\n{sync.INDEX_END}\n\nClosing line.\n"


@unittest.skipUnless(shutil.which("jj"), "needs jj")
class Workspaces(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {"JJ_USER": "Made Up", "JJ_EMAIL": "made-up@example.com",
                                                "JJ_CONFIG": str(self.base_dir / "jj-config.toml")})
        self.env.start()
        (self.base_dir / "jj-config.toml").write_text('[ui]\nconflict-marker-style = "diff"\n')
        self.a = self.base_dir / "a"
        self.a.mkdir()
        with self.at(self.a):
            self.run_jj("git", "init", "--colocate")
            sync.CHANGES_README.parent.mkdir(parents=True)
            sync.CHANGES_README.write_text(README)
            sync.TRACES.mkdir(parents=True)
            sync.write_index()
            self.base = self.commit("base")

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    @contextlib.contextmanager
    def at(self, root: Path):
        """sync.py's paths pointed at one workspace, as when its own copy of sync.py runs there."""
        llm = root / "llm-dlc"
        values = {"REPO": root, "CHANGES": llm, "TRACES": llm / "traces", "INDEX": llm / "index.json",
                  "CHANGES_README": llm / "README.md", "TRACES_README": llm / "traces" / "README.md",
                  "METRICS_ROLLUP": llm / "traces" / "metrics.json", "SESSION_NOTES": llm / "session-notes",
                  "DECISIONS": llm / "decisions", "PRICING": PRICING}
        with contextlib.ExitStack() as stack:
            for name, value in values.items():
                stack.enter_context(mock.patch.object(sync, name, value))
            yield

    def run_jj(self, *args: str) -> str:
        r = sync.jj(*args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def commit(self, message: str) -> str:
        """Commit @ with `message` and return its change id."""
        self.run_jj("commit", "-m", message)
        return self.run_jj("log", "--no-graph", "-r", "@-", "-T", "change_id").strip()

    def add_session(self, sid: str, sha: str, title: str):
        """A made-up session: its manifest and metrics.json, then the generated files, as `sync` leaves them."""
        m = {"schema": sync.SCHEMA, "session_id": sid, "title": title, "status": "done",
             "started": "2026-01-01T00:00:00Z", "ended": "2026-01-01T01:00:00Z", "duration_seconds": 3600,
             "models": ["made-up-model"], "tools": {}, "commits": [],
             "log": {"sha256": sha}, "logs": {sha: {"bytes": 1, "lines": 1, "gzip_bytes": 1, "url": None}},
             "stats": {"turns": 1, "api_calls": 1, "tool_calls": 0, "tool_errors": 0, "compactions": 0,
                       "peak_context_tokens": 1,
                       "usage": {"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 0,
                                 "cache_creation_input_tokens": 0}}}
        sync.session_dir(sid).mkdir(parents=True, exist_ok=True)
        sync.manifest_path(sid).write_text(json.dumps(m, indent=2) + "\n")
        sync.summary_path(sid).write_text(f"# {title}\n")
        doc = metrics.session(m, [], [], json.loads(PRICING.read_text()), lambda s: s)
        sync.metrics_path(sid).write_text(metrics.dumps(doc))
        sync.write_index()

    def traced(self, message: str, sid: str, sha: str) -> str:
        return self.commit(f"{message}\n\n{sync.TRAILER}: {sid} sha256:{sha}\n")

    def two_lines(self) -> Path:
        """Session A committed in workspace a, session B in workspace b, both from the base commit."""
        with self.at(self.a):
            self.add_session("session-a", "a" * 64, "Made-up A")
            self.line_a = self.traced("A's change", "session-a", "a" * 64)
        b = self.base_dir / "b"
        with self.at(self.a):
            self.run_jj("workspace", "add", "--name", "b", "-r", self.base, str(b))
        with self.at(b):
            self.add_session("session-b", "b" * 64, "Made-up B")
            self.line_b = self.traced("B's change", "session-b", "b" * 64)
        return b

    def regenerate(self) -> tuple[int, str, str]:
        with mock.patch("sys.stdout", io.StringIO()) as out, mock.patch("sys.stderr", io.StringIO()) as err:
            code = sync.cmd_regenerate([])
        return code, out.getvalue(), err.getvalue()

    # check: only the history of @

    def test_another_workspaces_commits_are_not_this_ones_to_check(self):
        b = self.two_lines()
        with self.at(self.a):
            errors, _ = sync.check_trailers(sync.all_manifests())
            self.assertEqual(errors, [])  # session-b's manifest is only in b's tree
        with self.at(b):
            errors, _ = sync.check_trailers(sync.all_manifests())
            self.assertEqual(errors, [])

    def test_a_trailer_in_this_history_is_still_checked(self):
        self.two_lines()
        with self.at(self.a):
            change = self.traced("A trailer naming no session here", "no-such-session", "c" * 64)
            errors, _ = sync.check_trailers(sync.all_manifests())
        self.assertEqual(errors, [f"change {change[:12]}: session no-such-session has no manifest"])

    def test_regenerating_after_a_merge_takes_the_merged_sessions_logs_from_their_workspace_checked(self):
        import gzip
        import hashlib
        good, bad = b'{"made": "up"}\n', b'{"made": "up, but other"}\n'
        sha_good, sha_bad = hashlib.sha256(good).hexdigest(), hashlib.sha256(bad).hexdigest()
        with self.at(self.a):
            self.add_session("session-a", "a" * 64, "Made-up A")
            self.line_a = self.traced("A's change", "session-a", "a" * 64)
        b = self.base_dir / "b"
        with self.at(self.a):
            self.run_jj("workspace", "add", "--name", "b", "-r", self.base, str(b))
        with self.at(b):
            (b / ".gitignore").write_text("llm-dlc/traces/*/logs/\n")  # as the repository's: a log is stored, not committed
            self.add_session("session-b", sha_good, "Made-up B")
            self.add_session("session-c", sha_bad, "Made-up C")
            for sid, sha, data in (("session-b", sha_good, good), ("session-c", sha_bad, good)):  # c's copy is not its log
                sync.log_path(sid, sha).parent.mkdir(parents=True, exist_ok=True)
                sync.log_path(sid, sha).write_bytes(gzip.compress(data))
            self.line_b = self.traced("B's change", "session-b", sha_good)
        with self.at(self.a):
            self.run_jj("new", self.line_a, self.line_b)
            code, out, _ = self.regenerate()
            self.assertEqual(code, 0)
            self.assertIn(f"took session-b: log {sha_good[:12]}", out)
            self.assertEqual(gzip.decompress(sync.log_path("session-b", sha_good).read_bytes()), good)
            self.assertFalse(sync.log_path("session-c", sha_bad).exists(), "a copy that isn't the log its name says is left")
            self.assertTrue(sync.log_path("session-b", sha_good).samefile(b / sync.log_path("session-b", sha_good).relative_to(sync.REPO)),
                            "taken as a hard link: one file under two names, no second copy on the disk")
        with self.at(b):  # an uploaded log is still an input of its session's metrics: b takes a's too
            sync.log_path("session-a", "a" * 64).parent.mkdir(parents=True, exist_ok=True)
        with self.at(self.a):
            m = sync.load_manifest("session-b")
            m["logs"][sha_good]["url"] = sync.log_url("session-b", sha_good)
            sync.manifest_path("session-b").write_text(json.dumps(m, indent=2) + "\n")
            sync.log_path("session-b", sha_good).unlink()
            self.assertEqual(sync.adopt_logs(), [f"session-b: log {sha_good[:12]}, from {b}"])

    def test_after_the_merge_both_lines_are_checked(self):
        self.two_lines()
        with self.at(self.a):
            self.run_jj("new", self.line_a, self.line_b)
            self.assertEqual(self.regenerate()[0], 0)
            errors, _ = sync.check_trailers(sync.all_manifests())
            self.assertEqual(errors, [])
            shutil.rmtree(sync.session_dir("session-b"))  # a merge that lost B's manifest
            errors, _ = sync.check_trailers(sync.all_manifests())
        self.assertEqual(len(errors), 1)
        self.assertIn("session session-b has no manifest", errors[0])

    def restamped_under_b(self, listed_in_a: bool) -> tuple[list, list]:
        """A's change, shared by b's line, stamped again in a with a newer log of session-a (as a session
        still at work there does), with a's manifest listing that log or not: what b's check makes of it."""
        with self.at(self.a):
            self.add_session("session-a", "a" * 64, "Made-up A")
            self.line_a = self.traced("A's change", "session-a", "a" * 64)
        b = self.base_dir / "b"
        with self.at(self.a):
            self.run_jj("workspace", "add", "--name", "b", "-r", self.line_a, str(b))
            if listed_in_a:
                m = sync.load_manifest("session-a")
                m["logs"]["e" * 64] = {"bytes": 1, "lines": 1, "gzip_bytes": 1, "url": None}
                sync.manifest_path("session-a").write_text(json.dumps(m, indent=2) + "\n")
            self.run_jj("describe", "-r", self.line_a, "-m", f"A's change\n\n{sync.TRAILER}: session-a sha256:{'e' * 64}\n")
        with self.at(b):
            self.run_jj("workspace", "update-stale")
            return sync.check_trailers(sync.all_manifests())

    def test_a_shared_change_stamped_in_another_workspace_is_a_note_while_its_manifest_there_lists_the_log(self):
        errors, notes = self.restamped_under_b(listed_in_a=True)
        self.assertEqual(errors, [])
        self.assertEqual(len([n for n in notes if "workspace default's copy of it lists the log" in n]), 1, notes)

    def test_a_shared_change_stamped_with_a_log_no_manifest_lists_is_still_an_error(self):
        errors, _ = self.restamped_under_b(listed_in_a=False)
        self.assertEqual(len(errors), 1)
        self.assertIn("points at log eeeeeeeeeeee that the manifest does not list", errors[0])

    # regenerate: the generated files after a merge

    def test_the_four_generated_files_conflict_and_regenerating_settles_them(self):
        self.two_lines()
        with self.at(self.a):
            self.run_jj("new", self.line_a, self.line_b)
            conflicted = set(sync.conflicted_paths())
            # traces/metrics.json may merge cleanly as text, and regenerating rewrites it either way
            self.assertLessEqual({"llm-dlc/README.md", "llm-dlc/index.json", "llm-dlc/traces/README.md"}, conflicted)
            self.assertLessEqual(conflicted, {"llm-dlc/README.md", "llm-dlc/index.json", "llm-dlc/traces/README.md",
                                              "llm-dlc/traces/metrics.json"})
            code, out, err = self.regenerate()
            self.assertEqual((code, err), (0, ""))
            self.assertEqual({line.removeprefix("regenerated: ") for line in out.splitlines()
                              if line.startswith("regenerated: ")}, conflicted)
            self.assertEqual(sync.conflicted_paths(), [])
            index = json.loads(sync.INDEX.read_text())
            self.assertEqual([r["session_id"] for r in index["sessions"]], ["session-a", "session-b"])
            readme = sync.CHANGES_README.read_text()
            self.assertIn("Made-up A", readme)
            self.assertIn("Made-up B", readme)
            self.assertTrue(readme.startswith("# Made-up repo\n\nIntro line.\n") and readme.endswith("Closing line.\n"))
            manifests = sync.all_manifests()  # what `check` compares them with
            self.assertEqual(sync.TRACES_README.read_text(), sync.render_traces_readme(manifests))
            self.assertEqual(sync.METRICS_ROLLUP.read_text(), sync.render_rollup(manifests))

    def test_a_readme_conflict_outside_the_index_table_is_left_and_reported(self):
        b = self.two_lines()
        for root, intro in ((self.a, "A's intro."), (b, "B's intro.")):
            with self.at(root):
                sync.CHANGES_README.write_text(sync.CHANGES_README.read_text().replace("Intro line.", intro))
                setattr(self, "line_a" if root == self.a else "line_b", self.commit("intro"))
        with self.at(self.a):
            self.run_jj("new", self.line_a, self.line_b)
            code, _, err = self.regenerate()
            self.assertEqual(code, 1)
            self.assertIn("llm-dlc/README.md", err)
            self.assertEqual(sync.conflicted_paths(), ["llm-dlc/README.md"])  # the other three are settled

    def test_a_conflicting_session_file_stops_it_before_anything_is_written(self):
        b = self.two_lines()
        for root, title in ((self.a, "A's title"), (b, "B's title")):
            with self.at(root):
                self.add_session("session-shared", "d" * 64, title)
                setattr(self, "line_a" if root == self.a else "line_b", self.commit("shared"))
        with self.at(self.a):
            self.run_jj("new", self.line_a, self.line_b)
            before = sync.INDEX.read_text()
            code, _, err = self.regenerate()
            self.assertEqual(code, 1)
            self.assertIn("llm-dlc/traces/session-shared/manifest.json", err)
            self.assertEqual(sync.INDEX.read_text(), before)

    def record_decision(self, question: str):
        """A made-up decision in the record made-up, written as the conductor writes it."""
        data = {"asked": {"by": "runtime", "question": question}, "state": "decided",
                "options": [{"id": "a", "summary": "This way", "consequences": "None."}],
                "decision": {"option": "a", "by": "conductor", "rationale": "The only option.",
                             "confidence": {"level": "high", "basis": "the brief"},
                             "recovery": {"class": "cheap", "undo": "Revert it."}}}
        with mock.patch("sys.stdout", io.StringIO()):
            self.assertEqual(decisions.main(["record", "made-up"], root=sync.DECISIONS,
                                            stdin=io.StringIO(json.dumps(data))), 0)

    def test_a_decision_record_in_conflict_is_listed_and_the_trace_files_still_settled(self):
        b = self.two_lines()
        for root, question in ((self.a, "A's question?"), (b, "B's question?")):
            with self.at(root):
                self.record_decision(question)
                setattr(self, "line_a" if root == self.a else "line_b", self.commit("decision"))
        with self.at(self.a):
            self.run_jj("new", self.line_a, self.line_b)
            code, out, err = self.regenerate()
            self.assertEqual(code, 1)
            self.assertIn("regenerated: llm-dlc/index.json", out)
            self.assertEqual(sorted(sync.conflicted_paths()),
                             ["llm-dlc/decisions/made-up.jsonl", "llm-dlc/decisions/made-up.md"])
            self.assertIn("llm-dlc/decisions/made-up.jsonl", err)

    def test_the_decision_views_are_written_with_the_other_generated_files(self):
        with self.at(self.a):
            self.record_decision("A question?")
            view = sync.DECISIONS / "made-up.md"
            view.unlink()
            sync.write_index()
            self.assertIn("### made-up-D001: A question?", view.read_text())
            self.assertEqual(decisions.problems(sync.DECISIONS), [])

    def test_without_a_conflict_it_rewrites_stale_files(self):
        with self.at(self.a):
            self.add_session("session-a", "a" * 64, "Made-up A")
            sync.INDEX.write_text("{}\n")  # stale, as a clean textual merge of two lines' rows can leave it
            code, out, _ = self.regenerate()
            self.assertEqual(code, 0)
            self.assertIn("there was no conflict", out)
            self.assertEqual([r["session_id"] for r in json.loads(sync.INDEX.read_text())["sessions"]], ["session-a"])


if __name__ == "__main__":
    unittest.main()

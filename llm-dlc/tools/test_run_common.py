#!/usr/bin/env python3
"""Tests for run_common.py, what the tools of a run share: a run's state, the clock, what a turn cost, the commits a
run made, the queue as a count, and the refusal to start a run from inside one.
Run: python3 llm-dlc/tools/test_run_common.py"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run_common

sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402


class ARunsState(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.run = run_common.Run(self.root, self.root / "llm-dlc" / "loop-summaries" / "single-made-up")

    def test_the_watchers_state_is_one_file_in_the_runs_directory_written_whole(self):
        self.assertEqual((self.run.read(), self.run.run_json()), ({}, {}))  # before anything is written
        self.run.update(session="s", cycles=3)
        self.assertEqual(self.run.update(cycles=4), {"session": "s", "cycles": 4})
        self.assertEqual(json.loads((self.run.dir / "watch.json").read_text()), {"session": "s", "cycles": 4})
        self.assertFalse((self.run.dir / "watch.tmp").exists())
        (self.run.dir / "watch.json").write_text("not JSON")
        self.assertEqual(self.run.read(), {})  # a file that cannot be read is no state, never an error

    def test_a_resumed_sessions_turn_costs_its_total_less_the_total_seen_before(self):
        self.assertEqual(run_common.turn_cost(self.run, "s", 12.5, fresh=True), 12.5, "a new session's first turn is its total")
        self.assertEqual(run_common.turn_cost(self.run, "s", 15.0, fresh=True), 2.5)
        self.assertIsNone(run_common.turn_cost(self.run, "old", 211.0, fresh=False), "a resumed session's earlier total is unknown")
        self.assertAlmostEqual(run_common.turn_cost(self.run, "old", 213.5, fresh=False), 2.5)
        self.assertIsNone(run_common.turn_cost(self.run, None, 1.0, fresh=True))

    def test_times_are_printed_as_a_summary_reads_them_and_a_process_is_alive_or_not(self):
        self.assertEqual((run_common.span(59), run_common.span(600), run_common.span(3 * 3600 + 5 * 60)), ("0 min", "10 min", "3 h 05 min"))
        self.assertEqual(run_common.clock(0), "00:00")
        self.assertEqual(run_common.stamp("2026-01-01T00:00:00Z"), 1767225600.0)
        self.assertIsNone(run_common.stamp(None))
        self.assertIsNone(run_common.stamp("yesterday"))
        self.assertTrue(run_common.alive(os.getpid()))
        self.assertFalse(run_common.alive(None))

    def test_a_session_is_looked_for_where_the_client_files_it_under_the_folder_it_ran_in(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.root / "config")}):
            path = run_common.transcript(Path("/home/made-up/code/a-checkout"), "0000")
        self.assertEqual(path, self.root / "config" / "projects" / "-home-made-up-code-a-checkout" / "0000.jsonl")

    def test_how_far_a_turn_has_come_is_read_from_what_the_client_wrote(self):
        self.assertEqual(run_common.turn(None), {"toolCalls": None, "lastOutput": None})
        log = self.root / "turn.jsonl"
        log.write_text('{"type":"tool_use"}\n{"type": "tool_use"} {"type":"text"}\n')
        self.assertEqual(run_common.turn(str(log))["toolCalls"], 2)

    def test_the_queue_is_counted_by_job_and_an_answer_that_is_not_the_view_is_an_unknown_queue_not_an_empty_one(self):
        (self.root / "jobs").mkdir()
        rows = [("20260101-000000-a", "queued", None), ("20260101-000001-b", "finished", {"status": "failed"}),
                ("20260101-000002-c", "collected", {"status": "passed"}), ("20260101-000003-d", "blocked", None),
                ("20260101-000004-e", "waiting", None)]
        view = {"schema": "itl-job-lifecycle/v1", "idle": False, "jobs": [{"id": i, "state": s, "result": r} for i, s, r in rows]}
        (self.root / "jobs/pipeline.py").write_text(f"import json\nprint(json.dumps({view!r}))\n")
        self.assertEqual(run_common.jobs(self.root), {"pending": ["20260101-000000-a", "20260101-000004-e"], "running": [],
                                                      "finished": ["20260101-000001-b"], "collected": {"20260101-000002-c": "passed"}})
        (self.root / "jobs/pipeline.py").write_text("print('not JSON')\n")
        self.assertIsNone(run_common.jobs(self.root))
        (self.root / "jobs/pipeline.py").write_text(f"import json\nprint(json.dumps({dict(view, idle=None)!r}))\n")
        self.assertIsNone(run_common.jobs(self.root))    # the pipeline itself could not read the queue


class NestedRuns(unittest.TestCase):
    """VF-045: a process inside a running loop's scope may not start a run; anywhere else, or in the tests, it may."""

    def cgroup(self, text):
        f = Path(tempfile.mkdtemp()) / "cgroup"
        self.addCleanup(lambda: f.unlink(missing_ok=True))
        f.write_text(text)
        return str(f)

    def test_a_run_started_from_inside_a_loop_is_refused_and_elsewhere_it_is_not(self):
        inside = self.cgroup("0::/user.slice/user-1001.slice/user@1001.service/app.slice/"
                             "feature-loop-single-made-up-brief.scope\n")
        watcher = self.cgroup("0::/user.slice/user-1001.slice/user@1001.service/app.slice/tmux-spawn-1.scope\n")
        self.assertEqual(run_common.enclosing_loop(inside), "feature-loop-single-made-up-brief")
        self.assertIsNone(run_common.enclosing_loop(watcher))
        self.assertIsNone(run_common.enclosing_loop("/no/such/file"))
        with mock.patch.dict(os.environ, {run_common.NESTED_RUN_OK: ""}):
            refusal = run_common.nested_run_refusal("single_run.py start other", inside)
            self.assertIn("feature-loop-single-made-up-brief", refusal)
            self.assertIn("VF-045", refusal)
            self.assertIsNone(run_common.nested_run_refusal("single_run.py start other", watcher))
        with mock.patch.dict(os.environ, {run_common.NESTED_RUN_OK: "allow"}):  # the tests' made-up loops
            self.assertIsNone(run_common.nested_run_refusal("single_run.py start other", inside))


@cost("tool")
class ARepository(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "root"
        self.root.mkdir()
        self.env = {**os.environ, "JJ_USER": "Made Up", "JJ_EMAIL": "made@up.invalid", "JJ_CONFIG": os.devnull}
        patch = mock.patch.dict(os.environ, self.env)
        patch.start()
        self.addCleanup(patch.stop)

    def jj(self, *args: str) -> str:
        return subprocess.run(["jj", "--quiet", *args], cwd=self.root, env=self.env, check=True, capture_output=True,
                              text=True).stdout.strip()

    @cost("tool")
    def test_the_commits_after_a_base_that_turned_divergent_are_still_listed(self):
        """VF-049: a run's base is a change id; once a rewrite gives it a new commit and a bookmark keeps the old one,
        the change is divergent, and its commits must still be listed."""
        self.jj("git", "init", str(self.root))
        self.jj("describe", "-m", "The base")
        base = self.jj("log", "--no-graph", "-r", "@", "-T", "change_id")
        old = self.jj("log", "--no-graph", "-r", "@", "-T", "commit_id")
        self.jj("new", "-m", "The run's work")
        self.jj("new")
        self.jj("describe", "-r", base, "-m", "The base, its trace lines rewritten")  # as sync.py commit does
        self.jj("bookmark", "create", "-r", old, "run-v0")  # the agent's bookmark on the old version
        self.assertIn("divergent", self.jj("log", "--no-graph", "-r", "all()", "-T", 'if(divergent, "divergent ", "")'))
        self.assertEqual([c.split(" ", 1)[1] for c in run_common.commits(self.root, base)], ["The run's work"])
        self.assertEqual(run_common.since_revset(old), old, "a commit id is taken as it is")
        self.assertEqual(run_common.head_change(self.root).split(" ", 1)[1], "The run's work")

    @cost("tool")
    def test_the_workspaces_of_a_repository_are_listed_with_their_folders_and_share_one_store(self):
        self.jj("git", "init", "--colocate", str(self.root))
        (self.root / "a.txt").write_text("one\n")
        self.jj("describe", "-m", "base")
        side = self.root.parent / "side"
        self.jj("workspace", "add", "--name", "side", str(side))
        found = run_common.workspaces(self.root)
        self.assertEqual((sorted(found), found["side"]), (["default", "side"], side))
        self.assertEqual(run_common.store(side), run_common.store(self.root))
        self.assertIsNone(run_common.store(self.root.parent / "nowhere"))
        (side / "new.txt").write_text("not yet seen by jj\n")
        self.assertNotIn("new.txt", run_common.jj(side, "diff", "--name-only", snapshot=False).stdout)  # the working copy is left unread
        self.assertIn("new.txt", run_common.jj(side, "diff", "--name-only").stdout)
        self.assertEqual(run_common.loops_in(self.root), [])  # no loop is at work in a made-up folder
        self.assertTrue(run_common.SESSION.fullmatch("00000000-0000-4000-8000-000000000001"))


if __name__ == "__main__":
    unittest.main()

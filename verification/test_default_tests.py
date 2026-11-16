#!/usr/bin/env python3
"""Tests for default_tests.py, the default test run as a job nobody waits for: a run that a newer one makes moot,
what a collected run says, which run covers a commit, and the push's gate. Run: python3 verification/test_default_tests.py
Nothing is run: the queue, the results and jj are made up or stood in for."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "llm-dlc/tools"))
import default_tests  # noqa: E402
import sync  # noqa: E402

MINE = "20261116-230000-default-test-run-at-aaaa"
NEWER = "20261116-231500-default-test-run-at-bbbb"


def result(root, job, commit, log, status="passed"):
    d = root / "verification/results" / job
    (d / "logs").mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({"id": job, "status": status, "sourceCommit": commit}))
    (d / "logs/1-default-tests.log").write_text(log)


class StepTest(unittest.TestCase):
    def step(self, status):
        out = io.StringIO()
        with mock.patch.dict("os.environ", {"VERIFY_JOB_ID": MINE}), \
                mock.patch.object(default_tests, "queue_status", return_value=status), \
                mock.patch.object(default_tests.subprocess, "run") as run, contextlib.redirect_stdout(out):
            run.return_value = mock.Mock(returncode=0, stdout="ok   a.py: Ran 1 test\ndefault tier: 48 of 48 passed\n")
            code = default_tests.cmd_step()
        return code, out.getvalue(), run

    def test_a_newer_default_run_waiting_makes_this_one_moot(self):
        code, out, run = self.step({"pending": [f"{NEWER}  Default test run at bbbb"], "running": [f"{MINE}  mine"]})
        self.assertEqual(code, 0)
        self.assertIn(f"default tests: superseded by {NEWER}", out)
        run.assert_not_called()

    def test_with_none_newer_it_runs_the_default_run_and_says_its_verdict(self):
        code, out, run = self.step({"pending": ["20261116-220000-default-test-run-at-cccc  older"], "running": [f"{MINE}  mine"]})
        self.assertEqual(code, 0)
        self.assertIn("default tests: passed: default tier: 48 of 48 passed", out)
        self.assertIn("test_costs.py", " ".join(run.call_args.args[0]))
        self.assertIn("CARGO_TARGET_DIR", run.call_args.kwargs["env"])


class ResultsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def test_a_collected_run_says_its_verdict_and_the_files_it_failed_at(self):
        result(self.root, MINE, "c1", "FAIL llm-dlc/tools/test_watch.py: Ran 40 tests\ntest result: FAILED. 1 failed\n"
                                      "default tests: failed: default tier: 46 of 48 passed\n", status="failed")
        result(self.root, NEWER, "c2", "default tests: superseded by 20261116-232000-default-test-run-at-dddd\n")
        newest, oldest = default_tests.runs(self.root)
        self.assertEqual((newest["job"], newest["verdict"]), (NEWER, "superseded"))
        self.assertEqual((oldest["verdict"], oldest["failed"]), ("failed", ["cargo test", "llm-dlc/tools/test_watch.py"]))

    def test_a_run_covers_its_commit_and_a_descendant_that_changes_only_files_no_test_reads(self):
        with mock.patch.object(default_tests.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="c1")), \
                mock.patch.object(default_tests, "jj") as jj:
            jj.return_value = "llm-dlc/traces/x/summary.md\nverification/results/j/result.json\n"
            self.assertTrue(default_tests.covers("c1", "c2"))
            jj.return_value = "llm-dlc/traces/x/summary.md\nlib/src/bmc/mod.rs\n"
            self.assertFalse(default_tests.covers("c1", "c2"), "a code change after the run is what the suite catches")
        self.assertTrue(default_tests.covers("c2", "c2"))
        self.assertFalse(default_tests.covers(None, "c2"))

    def test_the_gate_lets_a_push_through_only_on_a_passed_run(self):
        for found, code in (({"verdict": "passed", "job": MINE, "commit": "c1" * 6}, 0),
                            ({"verdict": "failed", "job": MINE, "commit": "c1" * 6, "failed": ["x.py"], "tally": ""}, 1),
                            (None, 1)):
            with mock.patch.object(default_tests, "last", return_value=found), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(default_tests.cmd_gate("@-"), code, found)

    def test_push_refuses_without_a_passed_run_unless_the_user_skips_it(self):
        (self.root / "verification").mkdir(parents=True)
        tool = self.root / "verification/default_tests.py"
        with mock.patch.object(sync, "REPO", self.root), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertTrue(sync.tests_gate(None), "a checkout without the tool has no gate")
            tool.write_text("import sys\nprint('no passed default run covers @-', file=sys.stderr)\nsys.exit(1)\n")
            self.assertFalse(sync.tests_gate(None))
            self.assertTrue(sync.tests_gate("the user's call"))
            tool.write_text("print('the default run passed for @-')\n")
            self.assertTrue(sync.tests_gate(None))
        self.assertIn("for the user alone", err.getvalue())

    def test_skip_tests_is_taken_out_of_the_push_arguments_with_its_reason(self):
        self.assertEqual(sync.without_skip_tests(["--bookmark", "main", "--skip-tests", "the user's call"]),
                         (["--bookmark", "main"], "the user's call"))
        self.assertEqual(sync.without_skip_tests(["--bookmark", "main"]), (["--bookmark", "main"], None))


if __name__ == "__main__":
    unittest.main()

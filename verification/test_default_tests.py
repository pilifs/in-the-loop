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
                mock.patch.object(default_tests.subprocess, "Popen") as run, contextlib.redirect_stdout(out):
            run.return_value = mock.Mock(stdout=iter(["ok   a.py: Ran 1 test\n", "default tier: 48 of 48 passed\n"]))
            run.return_value.wait.return_value = 0
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

    def test_a_test_that_passed_on_its_second_run_is_flaky_not_failed(self):
        result(self.root, MINE, "c1", "test a::b ... FAILED\ntest result: FAILED. 1 failed\nFLAKY cargo test: a::b (failed, "
                                      "then passed on a second run)\ndefault tier: 48 of 48 passed; flaky: cargo test\n"
                                      "default tests: passed: default tier: 48 of 48 passed; flaky: cargo test\n")
        [run] = default_tests.runs(self.root)
        self.assertEqual((run["verdict"], run["failed"], run["flaky"]), ("passed", [], ["cargo test"]))

    def test_a_failure_is_traced_to_the_first_commit_it_fails_at_since_the_last_pass(self):
        result(self.root, NEWER, "p0", "default tests: passed: default tier: 48 of 48 passed\n")
        line = [f"c{i}" for i in range(1, 9)]  # first-parent commits after p0; the test breaks at c5
        output = ("FAIL tools/test_x.py: Ran 3 tests\ntest m::t ... FAILED\n"
                  "default tier: 46 of 48 passed; failed: cargo test, tools/test_x.py\n")
        asked = []

        def fails_at(root, commit, files, rust, env):
            asked.append(commit)
            broken = {"tools/test_x.py": "c5", "cargo test": "c2"}
            return {t for t in files + (["cargo test"] if rust else []) if line.index(commit) >= line.index(broken[t])}

        out = io.StringIO()
        with mock.patch.object(default_tests.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="\n".join(line))), \
                mock.patch.object(default_tests, "fails_at", side_effect=fails_at), contextlib.redirect_stdout(out):
            default_tests.bisect(self.root, "c8", output, {})
        self.assertIn("default tests: culprit tools/test_x.py: c5", out.getvalue())
        self.assertIn("default tests: culprit cargo test: c2", out.getvalue())
        self.assertLessEqual(len(asked), 6, "halved, not walked: about log2(8) runs each")

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

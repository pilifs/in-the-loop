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
            jj.return_value = "M llm-dlc/traces/x/summary.md\nA verification/results/j/result.json\n"
            self.assertTrue(default_tests.covers("c1", "c2"))
            jj.return_value = "M llm-dlc/traces/x/summary.md\nM lib/src/bmc/mod.rs\n"
            self.assertFalse(default_tests.covers("c1", "c2"), "a code change after the run is what the suite catches")
        self.assertTrue(default_tests.covers("c2", "c2"))
        self.assertFalse(default_tests.covers(None, "c2"))

    def test_a_run_also_covers_changes_to_what_it_left_unread(self):
        unread = ["docs/notes.md", "papers/", "lib/benchmark/old/"]
        cases = (("M docs/notes.md", True, "a file nothing in the run opened"),
                 ("M docs/guide.md", False, "a file the run read, or may have"),
                 ("A docs/new.md", False, "a new file in a folder the run listed: a test that walks it would see it"),
                 ("D docs/notes.md", False, "a file removed from a folder the run listed"),
                 ("A papers/2026/draft.md", True, "a new file in a folder nothing listed"),
                 ("D papers/old.md", True, "and one removed there"),
                 ("M papers/a.md\nM llm-dlc/traces/x/summary.md", True, "with the records no test reads"),
                 ("M lib/benchmark/old/run.py", False, "lib/ always counts as read: cargo's warm build opens nothing"),
                 ("R docs/{notes.md => notes2.md}", False, "a rename is two paths: not covered"),
                 ("M papers/a.md\nM CLAUDE.md", False, "one read file among them is enough"))
        with mock.patch.object(default_tests.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="c1")), \
                mock.patch.object(default_tests, "jj") as jj:
            for summary, covered, why in cases:
                jj.return_value = summary + "\n"
                self.assertEqual(default_tests.covers("c1", "c2", unread), covered, why)
            jj.return_value = "M docs/notes.md\n"
            self.assertFalse(default_tests.covers("c1", "c2"), "a run that recorded nothing covers only the records")

    def test_what_a_run_left_unread_is_told_by_access_times_folders_whole_when_nothing_in_them_was_touched(self):
        import os
        import time
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = ["verification/default_tests.py", "docs/read.md", "docs/unread.md", "papers/a.md", "papers/deep/b.md",
                     "listed/c.md", "lib/src/x.rs", "lib/README.md", "verification/results/j/result.json"]
            for rel in files:
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text("x")
            # As a fresh export: everything written a while ago and not read since (the change time is now).
            old = time.time_ns() - 3600 * 10**9
            for path in [root / f for f in files] + [d for d in root.rglob("*") if d.is_dir()]:
                os.utime(path, ns=(old, old))
            self.assertIsNone(default_tests.unread(root), "the step's own file unread: access times say nothing here")
            later = time.time_ns() + 10**9
            for rel in ("verification/default_tests.py", "verification", "docs/read.md", "listed"):  # opened, or listed
                os.utime(root / rel, ns=(later, old))
            self.assertEqual(default_tests.unread(root), ["docs/unread.md", "listed/c.md", "papers/"])

    def test_a_collected_run_says_what_it_left_unread_and_then_covers_a_change_to_it(self):
        passed = "default tests: unread 2 paths (verification/default-tests-unread.txt)\ndefault tests: passed: default tier: 49 of 49 passed\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            older = "20261116-220000-default-test-run-at-cccc"
            for job in (older, MINE, NEWER):
                result(root, job, "c1", passed)
            # The newest run's list was applied to the working copy; MINE's came in late and was kept with its result.
            (root / default_tests.UNREAD_FILE).write_text(f"{NEWER}\ndocs/notes.md\npapers/\n")
            kept = root / "verification/results" / MINE / "outputs" / default_tests.UNREAD_FILE
            kept.parent.mkdir(parents=True)
            kept.write_text(f"{MINE}\ndocs/other.md\n")
            unread = {r["job"]: r["unread"] for r in default_tests.runs(root)}
        self.assertEqual(unread, {NEWER: ["docs/notes.md", "papers/"], MINE: ["docs/other.md"], older: []})
        self.assertIn(default_tests.UNREAD_FILE, default_tests.UNTESTED, "the list itself changes with every collected run")

    def test_the_step_writes_what_it_left_unread_as_the_jobs_output_and_its_log_says_only_how_many(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "verification").mkdir()
            out, here = io.StringIO(), os.getcwd()
            run = mock.Mock(stdout=iter(["default tier: 49 of 49 passed\n"]), wait=mock.Mock(return_value=0))
            os.chdir(tmp)
            try:
                with mock.patch.dict(os.environ, {"VERIFY_JOB_ID": MINE, "VERIFY_SOURCE_COMMIT": "c1"}), \
                        mock.patch.object(default_tests, "queue_status", return_value={}), \
                        mock.patch.object(default_tests.subprocess, "Popen", return_value=run), \
                        mock.patch.object(default_tests, "unread", return_value=["docs/notes.md", "papers/"]), \
                        mock.patch.object(default_tests, "CARGO_TARGET", Path(tmp) / "target"), \
                        contextlib.redirect_stdout(out):
                    self.assertEqual(default_tests.cmd_step(), 0)
                written = Path(default_tests.UNREAD_FILE).read_text()
            finally:
                os.chdir(here)
        self.assertEqual(written, f"{MINE}\ndocs/notes.md\npapers/\n")
        self.assertIn("default tests: unread 2 paths (verification/default-tests-unread.txt)\n", out.getvalue())
        self.assertNotIn("docs/notes.md", out.getvalue())

    def test_the_flaky_tests_are_counted_over_the_runs_that_ran(self):
        flaky_x = ("FLAKY tools/test_x.py: Ran 3 tests in 1.0s, FAILED (failures=1) (failed, then passed on a second run)\n"
                   "FLAKY cargo test: heap::a_made_up_test, values::another (failed, then passed on a second run)\n"
                   "default tier: 49 of 49 passed; flaky: tools/test_x.py, cargo test\ndefault tests: passed: x\n")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result(root, "20261116-220000-default-test-run-at-cccc", "c0", flaky_x)
            result(root, MINE, "c1", "FLAKY tools/test_x.py: Ran 3 tests in 1.0s, FAILED (errors=1) (failed, then passed on a second run)\n"
                                     "default tests: failed: default tier: 48 of 49 passed; failed: tools/test_y.py; flaky: tools/test_x.py\n")
            result(root, NEWER, "c2", "default tests: superseded by 20261116-233000-default-test-run-at-dddd\n")
            record = default_tests.flaky_record(default_tests.runs(root))
        self.assertEqual([(e["test"], len(e["runs"]), e["of"]) for e in record],
                         [("tools/test_x.py", 2, 2), ("cargo test: heap::a_made_up_test", 1, 2), ("cargo test: values::another", 1, 2)])
        self.assertEqual(record[0]["runs"][-1], MINE)

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

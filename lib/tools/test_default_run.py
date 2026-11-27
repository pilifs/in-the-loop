#!/usr/bin/env python3
"""Tests for default_run.py: the record of passed default runs, what it covers, the gate and the lock.
Run: python3 lib/tools/test_default_run.py"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import default_run as dr  # noqa: E402
from cost_tier import cost  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402


class Records(unittest.TestCase):
    """The record file, with jj and git stood in for."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "runs.jsonl"
        self.root = Path(self.tmp.name) / "repo"
        (self.root / ".jj").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_record_is_kept_newest_last_and_bounded(self):
        with mock.patch.object(dr, "KEPT", 3):
            for i in range(5):
                dr.record(f"t{i}", f"c{i}", "default tier: 1 of 1 passed", self.root, self.path)
        self.assertEqual([r["tree"] for r in dr.records(self.path)], ["t2", "t3", "t4"])

    def test_a_broken_line_is_skipped(self):
        self.path.write_text('{"tree": "a"}\nnot json\n{"tree": "b"}\n')
        self.assertEqual([r["tree"] for r in dr.records(self.path)], ["a", "b"])

    def test_untested_paths_are_the_records_and_nothing_else(self):
        self.assertTrue(dr.untested("llm-dlc/traces/x/summary.md"))
        self.assertTrue(dr.untested("llm-dlc/index.json"))
        self.assertFalse(dr.untested("llm-dlc/tools/sync.py"))
        self.assertFalse(dr.untested("llm-dlc/index.json.bak"))

    def test_a_run_covers_its_own_tree_and_one_that_differs_only_in_untested_files(self):
        diffs = {("t1", "t2"): "llm-dlc/traces/a.md\nverification/results/x/result.json",
                 ("t1", "t3"): "llm-dlc/traces/a.md\nlib/src/lib.rs"}
        with mock.patch.object(dr, "_out", side_effect=lambda cmd, cwd: diffs.get((cmd[-2], cmd[-1]))):
            self.assertTrue(dr.covers("t1", "t1", self.root))
            self.assertTrue(dr.covers("t1", "t2", self.root))
            self.assertFalse(dr.covers("t1", "t3", self.root))

    def test_the_generated_table_of_the_dlc_readme_is_untested_and_the_rest_of_the_file_is_not(self):
        page = lambda table, tail="Written by people.": f"# Changes\n\n{dr.TABLE_BEGIN}\n{table}\n{dr.TABLE_END}\n\n{tail}\n"
        files = {"t1": page("| one session |"), "t2": page("| one session |\n| another |"), "t3": page("| one session |", "Edited."),
                 "t4": page("| x |").replace(dr.TABLE_END, ""), "t5": page("| x |") + dr.TABLE_BEGIN}
        self.assertEqual(dr.outside_table(files["t1"]), dr.outside_table(files["t2"]))
        self.assertIsNone(dr.outside_table(files["t4"]))
        self.assertIsNone(dr.outside_table(files["t5"]))
        shown = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0 if cmd[2].split(":")[0] in files else 128, files.get(cmd[2].split(":")[0], ""), "")
        with mock.patch.object(dr, "_out", return_value="llm-dlc/README.md\nllm-dlc/artifacts/2026/11/21/promotion-x.json"), \
                mock.patch.object(dr.subprocess, "run", side_effect=shown):
            self.assertTrue(dr.covers("t1", "t2", self.root))    # the table alone
            self.assertFalse(dr.covers("t1", "t3", self.root))   # the page's own text
            self.assertFalse(dr.covers("t1", "t4", self.root))   # a mark is gone: compared whole
            self.assertFalse(dr.covers("t1", "t9", self.root))   # no such file on one side

    def test_last_takes_the_newest_record_that_covers(self):
        dr.record("old", "c0", "passed", self.root, self.path)
        dr.record("other", "c1", "passed", self.root, self.path)
        with mock.patch.object(dr, "tree_of", return_value=("old", "c9")), \
                mock.patch.object(dr, "covers", side_effect=lambda a, b, root: a == b):
            self.assertEqual(dr.last("@-", self.root, self.path)["commit"], "c0")
        with mock.patch.object(dr, "tree_of", return_value=None):
            self.assertIsNone(dr.last("@-", self.root, self.path))

    def test_a_run_is_recorded_only_when_the_tree_did_not_change_during_it(self):
        trees = iter([("t1", "c1"), ("t1", "c1"), ("t1", "c1"), ("t2", "c2")])
        with mock.patch.object(dr, "tree_of", side_effect=lambda rev, root: next(trees)), \
                mock.patch.object(dr, "covers", side_effect=lambda a, b, root: a == b), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            dr.Started(self.root).passed("passed", self.path)
            dr.Started(self.root).passed("passed", self.path)
        self.assertEqual([r["tree"] for r in dr.records(self.path)], ["t1"])
        self.assertIn("not recorded: the working copy changed during the run", out.getvalue())

    def test_a_change_during_the_run_in_files_no_test_reads_keeps_the_record(self):
        # 2026-11-27: a finding committed while the run went on threw away a passed run.
        trees = iter([("t1", "c1"), ("t1-plus-finding", "c2")])
        with mock.patch.object(dr, "tree_of", side_effect=lambda rev, root: next(trees)), \
                mock.patch.object(dr, "covers", side_effect=lambda a, b, root: (a, b) == ("t1", "t1-plus-finding")), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            dr.Started(self.root).passed("passed", self.path)
        self.assertEqual([(r["tree"], r["commit"]) for r in dr.records(self.path)], [("t1", "c1")])
        self.assertIn("changed meanwhile in files no test reads", out.getvalue())

    def test_no_tree_outside_a_workspace_root(self):
        with mock.patch.object(dr, "_out") as out:
            self.assertIsNone(dr.tree_of("@", Path(self.tmp.name)))
        out.assert_not_called()

    def test_the_gate_runs_the_default_run_when_nothing_covers_and_asks_again(self):
        answers = iter([None, {"tree": "t1abc", "when": "now", "tally": "passed"}])
        with mock.patch.object(dr, "last", side_effect=lambda rev, root: next(answers)), \
                mock.patch.object(dr.subprocess, "run") as run, contextlib.redirect_stderr(io.StringIO()):
            ok, said = dr.gate("@-", run=True, root=self.root)
        self.assertTrue(ok, said)
        self.assertEqual(run.call_args.args[0][-1], "run")

    def test_the_gate_without_run_only_says_what_to_do(self):
        with mock.patch.object(dr, "last", return_value=None), mock.patch.object(dr.subprocess, "run") as run:
            ok, said = dr.gate("@-", run=False, root=self.root)
        self.assertFalse(ok)
        self.assertIn("test_costs.py run", said)
        run.assert_not_called()


class AfterAMerge(unittest.TestCase):
    """Whether a default run is due after a merge: the last one here failed, or none passed here within the hour."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "attempts.json"
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def due(self, covered=None, **kw):
        with mock.patch.object(dr, "last", return_value=covered):
            return dr.due(self.root, path=self.path, now=10_000, **kw)

    def test_a_merge_within_the_hour_of_a_passed_run_runs_none_and_a_later_one_does(self):
        self.assertEqual(self.due()[0], True, "nothing is known of this checkout")
        dr.attempted(self.root, True, self.path, now=10_000 - 600)
        run, why = self.due()
        self.assertFalse(run)
        self.assertIn("10 min ago", why)
        dr.attempted(self.root, True, self.path, now=10_000 - 3700)
        self.assertTrue(self.due()[0])
        self.assertFalse(self.due(within=7200)[0])

    def test_a_run_that_failed_is_due_again_at_once(self):
        dr.attempted(self.root, False, self.path, now=10_000 - 60)
        run, why = self.due()
        self.assertTrue(run)
        self.assertIn("failed", why)

    def test_the_last_merge_runs_it_unless_a_passed_run_covers_the_commit(self):
        dr.attempted(self.root, True, self.path, now=10_000 - 60)
        self.assertTrue(self.due(final=True)[0])
        self.assertFalse(self.due(final=True, covered={"tree": "t1"})[0])
        self.assertFalse(self.due(covered={"tree": "t1"})[0])

    def test_another_checkouts_run_says_nothing_of_this_one(self):
        dr.attempted(Path(self.tmp.name) / "other", True, self.path, now=10_000 - 60)
        self.assertTrue(self.due()[0])

    def test_a_due_run_is_capped_and_limited_and_one_not_due_runs_nothing(self):
        with mock.patch.object(dr, "due", return_value=(True, "made up")), mock.patch.object(dr.subprocess, "run") as run, \
                mock.patch("shutil.which", return_value="/usr/bin/systemd-run"), contextlib.redirect_stdout(io.StringIO()):
            run.return_value.returncode = 3
            self.assertEqual(dr.after_merge(self.root), 3)
        argv = run.call_args.args[0]
        self.assertEqual(argv[:2], ["systemd-run", "--user"])
        self.assertIn("MemoryMax=8G", argv)
        self.assertEqual(argv[-3:], ["run", "--rust-jobs", "2"])
        with mock.patch.object(dr, "due", return_value=(False, "made up")), mock.patch.object(dr.subprocess, "run") as run, \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(dr.after_merge(self.root), 0)
        run.assert_not_called()
        self.assertIn("not run: made up", out.getvalue())


@cost("tool")
class Locking(unittest.TestCase):
    @cost("tool")
    def test_a_second_run_waits_for_the_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "CARGO_TARGET_DIR": tmp}
            with mock.patch.dict(os.environ, {"CARGO_TARGET_DIR": tmp}):
                held = dr.lock(Path(tmp))
            code = ("import sys; sys.path.insert(0, %r); import default_run as d, pathlib; d.lock(pathlib.Path(%r))"
                    % (str(Path(dr.__file__).parent), tmp))
            second = subprocess.Popen([sys.executable, "-c", code], env=env, stdout=subprocess.PIPE, text=True)
            first_line = second.stdout.readline()
            self.assertIn("waiting: another test run holds", first_line)
            self.assertIsNone(second.poll(), "it waits while the lock is held")
            held.close()
            self.assertEqual(second.wait(timeout=10), 0)
            second.stdout.close()


@cost("tool")
class RealTrees(unittest.TestCase):
    """covers() against a real git repository: a records-only change is covered, a source change is not."""

    @cost("tool")
    def test_covers_by_git_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git = lambda *a: subprocess.run(["git", *a], cwd=root, capture_output=True, text=True, check=True).stdout
            git("init", "-q")
            (root / "lib").mkdir()
            (root / "lib/a.rs").write_text("fn a() {}\n")
            git("add", "-A")
            t1 = git("write-tree").strip()
            (root / "llm-dlc/traces").mkdir(parents=True)
            (root / "llm-dlc/traces/s.md").write_text("summary\n")
            git("add", "-A")
            t2 = git("write-tree").strip()
            (root / "lib/a.rs").write_text("fn a() { 1; }\n")
            git("add", "-A")
            t3 = git("write-tree").strip()
            self.assertTrue(dr.covers(t1, t2, root))
            self.assertFalse(dr.covers(t1, t3, root))
            self.assertFalse(dr.covers(t2, t3, root))


@cost("tool")
class PushGate(unittest.TestCase):
    """sync.py push asks the gate, run inline, and only the user's stated reason skips it."""

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "llm-dlc/tools"))
        import sync
        self.sync = sync
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_push_refuses_without_a_passed_run_unless_the_user_skips_it(self):
        sync = self.sync
        (self.root / "lib/tools").mkdir(parents=True)
        tool = self.root / "lib/tools/default_run.py"
        with mock.patch.object(sync, "REPO", self.root), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertTrue(sync.tests_gate(None), "a checkout without the tool has no gate")
            tool.write_text("import sys\nassert sys.argv[1:] == ['gate', '--rev', '@-', '--run'], sys.argv\n"
                            "sys.exit(1)\n")
            self.assertFalse(sync.tests_gate(None))
            self.assertTrue(sync.tests_gate("the user's call"))
            tool.write_text("import sys\nassert sys.argv[1:] == ['gate', '--rev', '@-', '--run'], sys.argv\n")
            self.assertTrue(sync.tests_gate(None))
        self.assertIn("for the user alone", err.getvalue())

    def test_skip_tests_is_taken_out_of_the_push_arguments_with_its_reason(self):
        sync = self.sync
        self.assertEqual(sync.without_skip_tests(["--bookmark", "main", "--skip-tests", "the user's call"]),
                         (["--bookmark", "main"], "the user's call"))
        self.assertEqual(sync.without_skip_tests(["--bookmark", "main"]), (["--bookmark", "main"], None))


if __name__ == "__main__":
    unittest.main()

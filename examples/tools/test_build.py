#!/usr/bin/env python3
"""Tests of examples/tools/build.py, the runner of the examples, with the verifier's processes mocked: nothing here
builds an app or runs a proof, so the tests run in seconds.

  python3 examples/tools/test_build.py      (python3 -m unittest examples/tools/test_build.py)

They are about the runner's part of a result: how a run ended, what it concluded, and whether that matches the
example's expectation. A verifier that was killed, timed out, failed or printed what the runner cannot read must
never count as a verdict, an expected violation least of all.
"""

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402

EQUIVALENCE_VIOLATION = """\
✗ Behaviour of a.B#m changed:
  m(x=1)
    before: 1
    after:  2
  (found by JBMC 6.11.0 in 1.0 s, replayed in the interpreter; domain x: int)
"""
PROPERTY_VIOLATION = """\
✗ a.B#m violated: `result >= 0`:
  m(x=-1)
    outcome: returns -1
"""


def proc(returncode, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def example(approach="B9", symbol="net.terminalvalue.crosscut.retry.Backoff#delayMillis", verdict="violation", **expected):
    return {"id": "999", "approach": {"id": approach}, "change": {"behaviourChangeIntended": False},
            "subject": {"file": "examples/apps/crosscut/src/main/java/net/terminalvalue/crosscut/retry/Backoff.java",
                        "symbol": symbol},
            "expected": {"verdict": verdict, **expected}}


def empty_result():
    return {"verdict": None, "verdictLabel": None, "execution": None, "matchesExpected": None, "expectation": None,
            "counterexamples": [], "coverage": None, "statement": None, "sarif": "result.sarif",
            "output": "verifier-output.txt", "after": {"startLine": 1}}


class ExecutionStatusTest(unittest.TestCase):
    def test_a_signal_is_a_kill_whatever_the_output(self):
        for code in (-9, 137):
            with self.subTest(code=code):
                execution, verdict = build.conclude(code, "", [])
                self.assertEqual(execution["status"], "killed")
                self.assertIn("signal 9", execution["reason"])
                self.assertIsNone(verdict)

    def test_an_exit_code_the_tool_does_not_use_for_a_verdict_is_a_tool_error(self):
        for code in (2, 101, 3):
            with self.subTest(code=code):
                execution, verdict = build.conclude(code, "thread 'main' panicked", [])
                self.assertEqual(execution["status"], "tool-error")
                self.assertIn(f"exit code {code}", execution["reason"])
                self.assertIsNone(verdict)

    def test_a_timeout_is_not_a_verdict(self):
        execution, verdict = build.conclude(None, "", [], timed_out=60)
        self.assertEqual((execution["status"], verdict), ("timed-out", None))

    def test_no_output_is_invalid_even_with_exit_code_0(self):
        execution, verdict = build.conclude(0, "  \n", [])
        self.assertEqual((execution["status"], verdict), ("invalid-output", None))

    def test_a_violation_needs_its_evidence_and_the_report(self):
        execution, verdict = build.conclude(1, "something went wrong\n", [])
        self.assertEqual((execution["status"], verdict), ("invalid-output", None))
        execution, verdict = build.conclude(1, EQUIVALENCE_VIOLATION, [{"input": "m(x=1)"}], reported=False)
        self.assertEqual((execution["status"], verdict), ("invalid-output", None))
        self.assertIn("SARIF", execution["reason"])
        execution, verdict = build.conclude(1, EQUIVALENCE_VIOLATION, [{"input": "m(x=1)"}])
        self.assertEqual((execution["status"], verdict), ("completed", "violation"))

    def test_cannot_be_verified_and_verified_are_completed_verdicts(self):
        self.assertEqual(build.conclude(1, "✗ a.B#m cannot be verified: it reads the clock\n", [])[1], "unverifiable")
        self.assertEqual(build.conclude(0, "✓ verified\n", [])[1], "verified")


class ExpectationTest(unittest.TestCase):
    def test_a_killed_run_never_matches_an_expected_violation(self):
        result = empty_result()
        result["execution"] = build.execution_status(-9, "")
        build.finish(result, example(verdict="violation"))
        self.assertIsNone(result["verdict"])
        self.assertEqual(result["expectation"], "not-evaluable")
        self.assertFalse(result["matchesExpected"])
        self.assertTrue(result["verdictLabel"].startswith("⚠ No verdict: "))

    def test_an_unverifiable_expectation_is_not_met_by_a_tool_error(self):
        result = empty_result()
        result["execution"], result["verdict"] = build.conclude(2, "jvmcontract: cannot read classes", [])
        build.finish(result, example(verdict="unverifiable"))
        self.assertEqual(result["expectation"], "not-evaluable")

    def test_a_runner_that_recorded_no_run_has_no_verdict(self):
        result = empty_result()
        result["verdict"] = "violation"
        build.finish(result, example(verdict="violation"))
        self.assertEqual((result["verdict"], result["execution"]["status"], result["matchesExpected"]), (None, "tool-error", False))

    def test_a_completed_verdict_is_compared_with_its_vacuity(self):
        result = empty_result()
        result["execution"], result["verdict"] = build.conclude(0, "✓ verified\n", [])
        result["verdictLabel"] = "✓ Verified"
        result["coverage"] = {"vacuous": True, "reason": "no input reaches the calls"}
        build.finish(result, example(verdict="verified"))
        self.assertEqual(result["expectation"], "no")
        build.finish(result, example(verdict="verified", vacuous=True))
        self.assertEqual(result["expectation"], "yes")
        self.assertTrue(result["matchesExpected"])

    def test_the_recorded_results_keep_their_expectation_under_the_new_rule(self):
        """Every committed result completed (none had a verdict from a crash: each violation has its evidence), so
        recomputing whether it matches its expectation gives what was recorded."""
        checked = 0
        for folder in sorted(build.EXAMPLES.glob("[0-9][0-9][0-9]-*")):
            if not (folder / "result.json").exists():
                continue
            recorded = json.loads((folder / "result.json").read_text())
            ex = json.loads((folder / "example.json").read_text())
            result = {**recorded, "execution": recorded.get("execution") or {"status": "completed", "exitCode": None, "reason": None}}
            label = result["verdictLabel"]
            build.finish(result, ex)
            self.assertEqual(result["matchesExpected"], recorded["matchesExpected"], folder.name)
            self.assertEqual(result["verdictLabel"], label, folder.name)
            if recorded["verdict"] == "violation":
                self.assertTrue(recorded["counterexamples"] or recorded.get("trace") or recorded.get("newProblems"), folder.name)
            checked += 1
        self.assertGreater(checked, 100)


class RunnerTest(unittest.TestCase):
    """A runner given the verifier's process: what it records, and what it leaves in the example's folder."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="build-test-"))
        self.folder = self.dir / "example"
        self.folder.mkdir()
        self.root = self.dir / "root"
        self.build = self.root / build.TOOL_APPS["crosscut"]["root"]
        (self.build / "build/reports").mkdir(parents=True)
        # An earlier run's report, which a run that writes none must not leave behind as its own.
        (self.folder / "result.sarif").write_text("{}")
        (self.folder / "statement.java").write_text("class EquivalenceHarness {}")
        self.patches = [mock.patch.object(build, "jvmcontract", return_value="jvmcontract"),
                        mock.patch.object(build, "tool_before_classes", return_value=self.dir / "before")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.dir)

    def run_runner(self, runner, process, ex, report=None):
        def fake(command, **kwargs):
            if report:
                (self.build / "build/reports" / report).write_text(json.dumps({"version": "2.1.0", "runs": []}))
            return process
        result = empty_result()
        with mock.patch.object(build.subprocess, "run", side_effect=fake):
            runner(self.folder, ex, self.root, "crosscut", result)
        build.finish(result, ex)
        return result

    def test_equivalence_killed_by_a_signal_with_empty_output_is_no_counterexample(self):
        result = self.run_runner(build.run_tool_equivalence, proc(-9), example())
        self.assertEqual(result["execution"]["status"], "killed")
        self.assertIsNone(result["verdict"])
        self.assertFalse(result["matchesExpected"])
        self.assertEqual(result["counterexamples"], [])
        self.assertNotIn("Violation", result["verdictLabel"])
        self.assertFalse((self.folder / "result.sarif").exists())
        self.assertIsNone(result["sarif"])
        self.assertFalse((self.folder / "statement.java").exists())

    def test_equivalence_exit_code_1_with_output_the_runner_cannot_read(self):
        result = self.run_runner(build.run_tool_equivalence, proc(1, "garbage\n"), example(), report="equivalence.sarif")
        self.assertEqual((result["execution"]["status"], result["verdict"]), ("invalid-output", None))

    def test_equivalence_tool_error_is_recorded_not_a_crash_of_the_runner(self):
        result = self.run_runner(build.run_tool_equivalence, proc(2, "", "jvmcontract: no class a.B\n"), example())
        self.assertEqual(result["execution"]["status"], "tool-error")
        self.assertIn("no class a.B", result["execution"]["reason"])

    def test_equivalence_violation_with_its_witness_and_report(self):
        result = self.run_runner(build.run_tool_equivalence, proc(1, EQUIVALENCE_VIOLATION), example(), report="equivalence.sarif")
        self.assertEqual((result["execution"]["status"], result["verdict"]), ("completed", "violation"))
        self.assertEqual(result["counterexamples"], [{"input": "m(x=1)", "contract": "1", "actual": "2"}])
        self.assertTrue(result["matchesExpected"])
        self.assertTrue((self.folder / "result.sarif").exists())

    def test_property_killed_and_violated(self):
        ex = example(approach="B11")
        result = self.run_runner(build.run_tool_property, proc(-9), ex)
        self.assertEqual((result["execution"]["status"], result["verdict"], result["matchesExpected"]), ("killed", None, False))
        result = self.run_runner(build.run_tool_property, proc(1, PROPERTY_VIOLATION), ex, report="property.sarif")
        self.assertEqual((result["verdict"], result["matchesExpected"]), ("violation", True))

    def test_verify_with_an_unknown_exit_code(self):
        ex = example(approach="B8", verdict="violation")
        result = self.run_runner(build.run_tool_contracts, proc(134, "fatal runtime error\n"), ex)
        self.assertEqual(result["execution"]["status"], "killed")  # 134 = 128 + SIGABRT
        result = self.run_runner(build.run_tool_contracts, proc(3, "fatal runtime error\n"), ex)
        self.assertEqual(result["execution"]["status"], "tool-error")
        self.assertFalse(result["matchesExpected"])

    def test_a_run_without_a_verdict_renders(self):
        source = next(build.EXAMPLES.glob("126-*"))
        shutil.copy(source / "change.patch", self.folder / "change.patch")
        ex = json.loads((source / "example.json").read_text())
        result = {**json.loads((source / "result.json").read_text()), "sarif": None, "statement": None}
        result["execution"] = build.execution_status(-9, "")
        (self.folder / "verifier-output.txt").write_text("")
        build.finish(result, ex)
        page = build.render_example(self.folder, ex, result)
        self.assertIn("⚠ No verdict: the verifier was killed by signal 9", page)
        self.assertIn("did not complete (`killed`)", page)
        self.assertNotIn("SARIF report", page)
        self.assertNotIn("**missed**", build.tests_cell(result))


class TlcTest(unittest.TestCase):
    def tlc_json(self, **fields):
        return json.dumps({"verdict": "verified", "output": "Model checking completed. No error has been found.",
                           "trace": [], "version": "TLC 2.19", **fields})

    def test_a_killed_tool_gives_a_run_without_a_verdict(self):
        run = build.tlc_run_result(proc(-9))
        self.assertEqual((run["verdict"], run["execution"]["status"]), ("unverifiable", "killed"))
        self.assertTrue(build.tlc_label(run).startswith("⚠ No verdict"))

    def test_malformed_json_is_invalid_output(self):
        for stdout in ("{not json", "[]", json.dumps({"verdict": "maybe", "output": ""})):
            with self.subTest(stdout=stdout):
                self.assertEqual(build.tlc_run_result(proc(0, stdout))["execution"]["status"], "invalid-output")

    def test_tlc_killed_or_late_inside_the_tool(self):
        killed = build.tlc_run_result(proc(1, self.tlc_json(verdict="unverifiable", output="Error: java was killed by signal 9")))
        self.assertEqual(killed["execution"]["status"], "killed")
        late = build.tlc_run_result(proc(1, self.tlc_json(verdict="unverifiable", output="Error: java did not finish within 1800 s")))
        self.assertEqual(late["execution"]["status"], "timed-out")
        failed = build.tlc_run_result(proc(1, self.tlc_json(verdict="unverifiable", output="Error: parse error in Foo.tla")))
        self.assertEqual(failed["execution"]["status"], "tool-error")

    def test_a_violation_needs_a_trace(self):
        run = build.tlc_run_result(proc(1, self.tlc_json(verdict="violation", invariant="Safe", output="Error: Invariant Safe is violated.")))
        self.assertEqual((run["verdict"], run["execution"]["status"]), ("unverifiable", "invalid-output"))
        steps = [{"step": 1, "action": "Initial predicate", "changes": {"x": "0"}}]
        run = build.tlc_run_result(proc(1, self.tlc_json(verdict="violation", invariant="Safe", trace=steps,
                                                         output="Error: Invariant Safe is violated.")))
        self.assertEqual((run["verdict"], run["execution"]["status"]), ("violation", "completed"))

    def test_box_office_tlc_timeout_and_no_verdict(self):
        self.assertEqual(build.tlc_conclusion(None, "", 1800, False, None, None)[0]["status"], "timed-out")
        self.assertEqual(build.tlc_conclusion(-9, "", None, False, None, None)[0]["status"], "killed")
        execution, verdict = build.tlc_conclusion(255, "Error: TLC threw an unexpected exception.", None, False, None, None)
        self.assertEqual((execution["status"], verdict), ("tool-error", None))
        self.assertEqual(build.tlc_conclusion(0, "No error has been found", None, True, None, None)[1], "verified")


class MainTest(unittest.TestCase):
    def test_a_run_without_a_verdict_fails_and_the_pipeline_sees_it(self):
        """build.py exits 1 and prints a line the pipeline's `example:unexpected` signal reads."""
        sys.path.insert(0, str(build.REPO / "verification"))
        import pipeline
        unexpected = next(pattern for source, key, pattern in pipeline.SIGNALS if (source, key) == ("example", "unexpected"))
        folder = next(build.EXAMPLES.glob("126-*"))
        dir = Path(tempfile.mkdtemp(prefix="build-test-"))
        self.addCleanup(shutil.rmtree, dir)

        def run(f, ex):
            result = empty_result()
            result["execution"] = build.execution_status(-9, "")
            build.finish(result, ex)
            return result

        out = io.StringIO()
        with mock.patch.object(build, "run", side_effect=run), mock.patch.object(build, "EXAMPLES", dir), \
                mock.patch.object(build, "render_example", return_value=""), mock.patch.object(build, "render_index"), \
                mock.patch.object(build, "validate"), mock.patch.object(build, "load_example", side_effect=lambda f: json.loads((f / "example.json").read_text())), \
                contextlib.redirect_stdout(out):
            shutil.copytree(folder, dir / folder.name)
            self.assertEqual(build.main([folder.name[:3]]), 1)
        self.assertTrue(any(unexpected.search(line) for line in out.getvalue().splitlines()), out.getvalue())
        self.assertIn("killed by signal 9", out.getvalue())


class SchemaTest(unittest.TestCase):
    def test_a_result_without_a_verdict_validates(self):
        import jsonschema
        schema = json.loads((build.EXAMPLES / "schema/result.schema.json").read_text())
        source = next(build.EXAMPLES.glob("126-*"))
        result = {**json.loads((source / "result.json").read_text()), "sarif": None}
        result["execution"] = build.execution_status(-9, "")
        build.finish(result, json.loads((source / "example.json").read_text()))
        jsonschema.validate(result, schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({**result, "expectation": "maybe"}, schema)


if __name__ == "__main__":
    unittest.main()

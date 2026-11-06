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
import re
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


def equivalence_json(root, verdict="violation", **fields):
    """What `jvmcontract equivalence --json` prints: the library's Outcome, its paths under the patched copy `root`."""
    work = f"{root}/examples/apps/crosscut/build/equivalence"
    outcome = {"verdict": verdict, "target": "a.B#m", "domain": "x: int", "counterexample": None, "proof": None,
               "problem": None, "statement": f"{work}/harness/EquivalenceHarness.java", "findings": [],
               "output": EQUIVALENCE_VIOLATION if verdict == "violation" else "✓ a.B#m is equivalent\n", "work": work,
               "search": {"engine": "jbmc", "checker": "JBMC 6.11.0", "seconds": 1.04, "properties": 3, "unwind": 16,
                          "max_array_length": 8, "stage": "[0:20]" if verdict == "violation" else None}}
    if verdict == "violation":
        outcome.update({
            "counterexample": {"input": "m(x=1)", "before": "1", "after": "2", "values": ["1"], "found": "m(x=17)", "shrink_runs": 4},
            "proof": f"found by JBMC 6.11.0 in 1.0 s searching inputs in [0:20] as m(x=17), shrunk to the input above in 4 "
                     f"interpreter runs, replayed in the interpreter; domain x: int",
            "replay": {"by": "interpreter", "reproduced": True}})
    elif verdict == "verified":
        outcome["proof"] = "JBMC 6.11.0: 3 properties proved over x: int in 1.0 s; loops unwound 16 times with unwinding assertions"
    outcome.update(fields)
    return json.dumps(outcome)


PROPERTY_VIOLATION = """\
✗ a.B#m violated: `result >= 0`:
  m(x=-1)
    outcome: returns -1
"""


def property_outcome(root, n=None, verdict="violation", assume=None, assert_="result >= 0", **fields):
    """One element of what `jvmcontract prove --json` prints: the library's property Outcome, its paths under the
    patched copy `root`, in the work directory `property-N` when the target has several properties (`n`)."""
    work = f"{root}/examples/apps/crosscut/build/property" + (f"/property-{n}" if n else "")
    where = f" where {assume}" if assume else ""
    outcome = {"verdict": verdict, "target": "a.B#m", "domain": "x: int", "assume": assume, "assert": assert_, "throws": [],
               "throws_checked": [], "counterexample": None, "proof": None, "problem": None,
               "statement": f"{work}/harness/PropertyHarness.java", "findings": [], "work": work,
               "search": {"engine": "jbmc", "checker": "JBMC 6.11.0", "seconds": 0.6, "properties": 2, "unwind": 16,
                          "max_array_length": 8, "stage": None}}
    if verdict == "violation":
        outcome.update({
            "counterexample": {"input": "m(x=-1)", "outcome": "-1", "values": ["-1"], "found": "m(x=-17)", "shrink_runs": 9},
            "proof": "found by JBMC 6.11.0 in 0.2 s searching inputs in [0:20] as m(x=-17), shrunk to the input above in 9 "
                     "interpreter runs, replayed in the interpreter; domain x: int",
            "output": f"✗ Property of a.B#m violated: `{assert_}`{where}:\n  m(x=-1)\n    outcome: -1\n  (found by JBMC)\n",
            "replay": {"by": "interpreter", "reproduced": True}})
        outcome["search"]["stage"] = "[0:20]"
    elif verdict == "verified":
        outcome.update({"proof": "JBMC 6.11.0: 2 properties proved over x: int in 0.6 s; loops unwound 16 times with unwinding assertions",
                        "output": f"✓ a.B#m satisfies `{assert_}` on every input{where} (JBMC 6.11.0)\n"})
    else:
        outcome.update({"problem": "JBMC gave no verdict within 60 s", "search": None,
                        "output": "✗ a.B#m cannot be verified: JBMC gave no verdict within 60 s\n"})
    outcome.update(fields)
    return outcome


def property_json(*outcomes):
    return json.dumps(list(outcomes))


def proc(returncode, stdout="", stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


def example(approach="B9", symbol="net.terminalvalue.crosscut.retry.Backoff#delayMillis", verdict="violation", **expected):
    return {"id": "999", "origin": "constructed", "approach": {"id": approach}, "change": {"behaviourChangeIntended": False},
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


def with_blocks(result, out):
    """The claim, attempt, conclusion and bundle run() ends a result with, for a run the test made up."""
    claim = {"id": "0123456789abcdef", "format": build.CLAIM_FORMAT, "example": "999", "statement": {}, "scope": {}, "inputs": {}}
    attempt = {"id": "20261106T000000Z-00000000", "claim": claim["id"], "startedAt": "2026-11-06T00:00:00+00:00",
               "seconds": 0.0, "engine": None, "options": [], "tools": {}, "bytecode": {"before": None, "after": None},
               "pipeline": None, "execution": result["execution"]}
    result.update({"claim": claim, "attempt": attempt, "conclusion": build.conclusion_record(claim, attempt, result),
                   "bundle": build.bundle_record(out)})
    return result


def stores_whole(test, result, out):
    """A runner's result stores as format 2 and reads back as itself, with the blocks run() would add."""
    import copy
    complete = with_blocks(copy.deepcopy(result), out)
    test.assertEqual(build.result_format.round_trip_problems(complete), [])
    build.validate(build.result_format.pack(complete), "stored-result.schema.json", out)
    return result


def left_evidence(result, out, output="the verifier's output\n"):
    """What a runner leaves in the attempt's directory, and the blocks run() lists of it: its console output, no
    report."""
    (Path(out) / "verifier-output.txt").write_text(output)
    result["sarif"] = None
    return with_blocks(result, out)


class RunnerCase(unittest.TestCase):
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
        for stale in (self.build / "build/reports").glob("*"):  # a report an earlier call in the test wrote
            stale.unlink()
        def fake(command, **kwargs):
            if report:
                (self.build / "build/reports" / report).write_text(json.dumps({"version": "2.1.0", "runs": []}))
            return process
        result = empty_result()
        with mock.patch.object(build.subprocess, "run", side_effect=fake):
            runner(self.folder, ex, self.root, "crosscut", result)
        build.finish(result, ex)
        return stores_whole(self, result, self.folder)


class RunnerTest(RunnerCase):
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

    def harness(self):
        """The statement the library writes, which the runner copies into the example's folder."""
        harness = self.build / "build/equivalence/harness"
        harness.mkdir(parents=True, exist_ok=True)
        (harness / "EquivalenceHarness.java").write_text("class EquivalenceHarness { /* this run's */ }")

    def test_equivalence_violation_with_its_witness_and_report(self):
        self.harness()
        result = self.run_runner(build.run_tool_equivalence, proc(1, equivalence_json(self.root)), example(), report="equivalence.sarif")
        self.assertEqual((result["execution"]["status"], result["verdict"]), ("completed", "violation"))
        self.assertEqual(result["counterexamples"], [{"input": "m(x=1)", "contract": "1", "actual": "2", "found": "m(x=17)", "shrinkRuns": 4}])
        self.assertTrue(result["matchesExpected"])
        self.assertTrue((self.folder / "result.sarif").exists())
        self.assertEqual(result["replay"], {"by": "interpreter", "reproduced": True})
        self.assertEqual(result["search"], {"engine": "jbmc", "checker": "JBMC 6.11.0", "seconds": 1.04, "properties": 3,
                                            "unwind": 16, "maxArrayLength": 8, "stage": "[0:20]"})
        self.assertEqual((result["domain"], result["problem"]), ("x: int", None))
        self.assertTrue(result["proof"].startswith("found by JBMC 6.11.0 in 1.0 s searching inputs in [0:20]"))
        self.assertIn("this run's", (self.folder / "statement.java").read_text())
        # The console output is the outcome's text, as without --json, and not the JSON.
        self.assertEqual((self.folder / "verifier-output.txt").read_text(), EQUIVALENCE_VIOLATION)

    def test_equivalence_is_asked_for_its_json_outcome(self):
        commands = []
        def fake(command, **kwargs):
            commands.append(command)
            return proc(0, equivalence_json(self.root, "verified"))
        with mock.patch.object(build.subprocess, "run", side_effect=fake):
            build.run_tool_equivalence(self.folder, example(verdict="verified"), self.root, "crosscut", empty_result())
        self.assertIn("--json", commands[0])

    def test_text_output_is_not_an_outcome(self):
        """The text the tool prints without --json is no longer read as a verdict: the runner asked for JSON."""
        result = self.run_runner(build.run_tool_equivalence, proc(1, EQUIVALENCE_VIOLATION), example(), report="equivalence.sarif")
        self.assertEqual((result["execution"]["status"], result["verdict"], result["counterexamples"]), ("invalid-output", None, []))
        self.assertIn("--json output is not an outcome", result["execution"]["reason"])
        self.assertIsNone(result["search"])

    def test_an_exit_code_that_disagrees_with_the_outcome_is_invalid(self):
        for code, verdict in ((0, "violation"), (1, "verified"), (0, "unverifiable"), (1, "maybe")):
            result = self.run_runner(build.run_tool_equivalence, proc(code, equivalence_json(self.root, verdict)), example(),
                                     report="equivalence.sarif")
            self.assertEqual((result["execution"]["status"], result["verdict"]), ("invalid-output", None), (code, verdict))
            self.assertIsNone(result["replay"])

    def test_a_violation_without_its_witness_or_report_is_invalid(self):
        result = self.run_runner(build.run_tool_equivalence, proc(1, equivalence_json(self.root, counterexample=None)), example(),
                                 report="equivalence.sarif")
        self.assertEqual((result["execution"]["status"], result["verdict"]), ("invalid-output", None))
        (self.build / "build/reports/equivalence.sarif").unlink()
        result = self.run_runner(build.run_tool_equivalence, proc(1, equivalence_json(self.root)), example())
        self.assertEqual((result["execution"]["status"], result["verdict"]), ("invalid-output", None))
        self.assertIn("no SARIF report", result["execution"]["reason"])

    def test_a_vacuous_proof_from_the_outcome(self):
        reason = "no input in the domain reaches the calls, every one being among the intended inputs (--unchanged-unless)"
        out = equivalence_json(self.root, "verified", vacuous=reason)
        result = self.run_runner(build.run_tool_equivalence, proc(0, out), example(verdict="verified", vacuous=True), report="equivalence.sarif")
        self.assertEqual(result["coverage"], {"vacuous": True, "reason": reason})
        self.assertEqual(result["verdictLabel"], "✓ Verified, vacuously: no input in the domain reaches the calls")
        self.assertTrue(result["matchesExpected"])
        self.assertIsNone(result["replay"])
        self.assertIsNone(result["search"]["stage"])

    def test_the_own_checkers_numbers_and_a_fallback(self):
        native = {"paths": 733, "merges": 219, "solver_calls": 1204, "solving_seconds": 5.1, "gates_evaluated": 9,
                  "evaluating_seconds": 0.2, "divisions": 0, "divisions_built": 0, "multiplications": 2,
                  "multiplications_built": 1, "variables": 5000, "clauses": 20000, "seconds": 7.0}
        out = equivalence_json(self.root, "verified", shared=["a.C.f"], search={
            "engine": "native", "checker": "jvmcontract's own checker (CaDiCaL)", "seconds": 7.0, "properties": 1, "unwind": 8,
            "max_array_length": 8, "stage": None, "native": native})
        search = self.run_runner(build.run_tool_equivalence, proc(0, out), example(verdict="verified"), report="equivalence.sarif")["search"]
        self.assertEqual((search["engine"], search["native"]["paths"], search["native"]["solverCalls"], search["native"]["multiplicationsBuilt"]),
                         ("native", 733, 1204, 1))
        self.assertEqual(search["sharedCallees"], ["a.C.f"])
        out = equivalence_json(self.root, "verified", search={**json.loads(equivalence_json(self.root, "verified"))["search"],
                                                               "fallback": "a float parameter"})
        search = self.run_runner(build.run_tool_equivalence, proc(0, out), example(verdict="verified"), report="equivalence.sarif")["search"]
        self.assertEqual((search["engine"], search["fallback"]), ("jbmc", "a float parameter"))
        self.assertNotIn("native", search)

    def test_a_witness_that_does_not_reproduce_is_unverifiable(self):
        problem = "JBMC's counterexample m(x=3) does not reproduce: both versions give 1 in the interpreter. ..."
        out = equivalence_json(self.root, "unverifiable", problem=problem, replay={"by": "interpreter", "reproduced": False},
                               output=f"✗ a.B#m cannot be verified: {problem}\n")
        result = self.run_runner(build.run_tool_equivalence, proc(1, out), example(verdict="violation"), report="equivalence.sarif")
        self.assertEqual((result["verdict"], result["problem"], result["matchesExpected"]), ("unverifiable", problem, False))
        self.assertEqual(result["replay"], {"by": "interpreter", "reproduced": False})
        self.assertEqual(result["counterexamples"], [])

    def test_the_patched_copys_root_is_taken_out_of_the_outcome(self):
        out = equivalence_json(self.root, "verified", output=f"note: wrote {self.root}/examples/apps/crosscut/build/x\n✓ a.B#m\n",
                               proof=f"JBMC 6.11.0: 3 properties proved over x: int in 1.0 s (see {self.root}/log)")
        result = self.run_runner(build.run_tool_equivalence, proc(0, out, f"warning: {self.root}/y\n"), example(verdict="verified"),
                                 report="equivalence.sarif")
        self.assertNotIn(str(self.root), (self.folder / "verifier-output.txt").read_text())
        self.assertIn("warning: y", (self.folder / "verifier-output.txt").read_text())
        self.assertNotIn(str(self.root), result["proof"])


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


class PropertyRunnerTest(RunnerCase):
    """`prove --json`: every property of the target keeps its own outcome, and the verdict is computed over them."""

    def harnesses(self, *ns):
        """The statements the library writes, one per property's work directory (none for a single property)."""
        for n in ns:
            harness = self.build / "build/property" / (f"property-{n}" if n else "") / "harness"
            harness.mkdir(parents=True, exist_ok=True)
            (harness / "PropertyHarness.java").write_text(f"class PropertyHarness {{ /* property {n} */ }}")

    def prove(self, returncode, *outcomes, report="property.sarif", **expected):
        return self.run_runner(build.run_tool_property, proc(returncode, property_json(*outcomes)),
                               example(approach="B11", **expected), report=report)

    def test_a_killed_run_and_text_output_have_no_verdict(self):
        ex = example(approach="B11")
        result = self.run_runner(build.run_tool_property, proc(-9), ex)
        self.assertEqual((result["execution"]["status"], result["verdict"], result["matchesExpected"]), ("killed", None, False))
        self.assertIsNone(result.get("properties"))
        result = self.run_runner(build.run_tool_property, proc(1, PROPERTY_VIOLATION), ex, report="property.sarif")
        self.assertEqual((result["execution"]["status"], result["verdict"], result["counterexamples"]), ("invalid-output", None, []))
        result = self.run_runner(build.run_tool_property, proc(1, "[]"), ex, report="property.sarif")
        self.assertEqual(result["execution"]["status"], "invalid-output")

    def test_prove_is_asked_for_its_json_outcomes(self):
        commands = []
        def fake(command, **kwargs):
            commands.append(command)
            return proc(0, property_json(property_outcome(self.root, verdict="verified")))
        with mock.patch.object(build.subprocess, "run", side_effect=fake):
            build.run_tool_property(self.folder, example(approach="B11", verdict="verified"), self.root, "crosscut", empty_result())
        self.assertIn("--json", commands[0])

    def test_one_property_is_recorded_as_before(self):
        self.harnesses(None)
        result = self.prove(1, property_outcome(self.root))
        self.assertEqual((result["execution"]["status"], result["verdict"], result["matchesExpected"]), ("completed", "violation", True))
        self.assertEqual(result["verdictLabel"], "✗ Violation: counterexample found")
        self.assertEqual(result["property"], {"assert": "result >= 0", "assume": None})
        self.assertEqual(result["counterexamples"], [{"input": "m(x=-1)", "contract": "result >= 0", "actual": "-1",
                                                      "found": "m(x=-17)", "shrinkRuns": 9}])
        self.assertEqual(result["statement"], "statement.java")
        self.assertIn("property None", (self.folder / "statement.java").read_text())
        [record] = result["properties"]
        self.assertEqual((record["harness"], record["statement"], record["verdict"]), (None, None, "violation"))
        self.assertEqual(record["replay"], {"by": "interpreter", "reproduced": True})
        self.assertEqual(record["search"]["stage"], "[0:20]")
        self.assertTrue(result["proof"].startswith("found by JBMC 6.11.0"))
        self.assertEqual((self.folder / "verifier-output.txt").read_text(), property_outcome(self.root)["output"])

    def test_three_properties_one_refuted_like_071(self):
        """071's shape: two properties hold and the third, the election restriction, is refuted."""
        self.harnesses(1, 2, 3)
        (self.folder / "statement-4.java").write_text("an earlier run's")
        outcomes = [property_outcome(self.root, 1, "verified", assume="a == b"),
                    property_outcome(self.root, 2, "verified", assume="a < b"),
                    property_outcome(self.root, 3, "violation", assume="c < d || (c == d && e < f)", assert_="!result")]
        result = self.prove(1, *outcomes)
        self.assertEqual((result["verdict"], result["matchesExpected"]), ("violation", True))
        self.assertEqual(result["verdictLabel"], "✗ Violation: counterexample found to 1 of 3 properties")
        self.assertEqual([r["harness"] for r in result["properties"]], ["property-1", "property-2", "property-3"])
        self.assertEqual([r["verdict"] for r in result["properties"]], ["verified", "verified", "violation"])
        self.assertEqual([r["assume"] for r in result["properties"]], ["a == b", "a < b", "c < d || (c == d && e < f)"])
        # The headline property is the refuted one, and its statement is the result's.
        self.assertEqual(result["property"], {"assert": "!result", "assume": "c < d || (c == d && e < f)"})
        self.assertEqual(result["statement"], "statement-3.java")
        for n in (1, 2, 3):
            self.assertIn(f"property {n}", (self.folder / f"statement-{n}.java").read_text())
        self.assertFalse((self.folder / "statement.java").exists())
        self.assertFalse((self.folder / "statement-4.java").exists())
        self.assertEqual([c["contract"] for c in result["counterexamples"]], ["!result"])
        self.assertEqual((self.folder / "verifier-output.txt").read_text(), "".join(o["output"] for o in outcomes))
        # Each property's proof is its own, not the first one's.
        self.assertTrue(result["properties"][0]["proof"].startswith("JBMC 6.11.0: 2 properties proved"))
        self.assertTrue(result["proof"].startswith("found by"))
        page = "\n".join(build.findings_property(example(approach="B11", symbol="a.B#m"), result))
        self.assertIn("| 3 | That `!result` holds where `c < d \\|\\| (c == d && e < f)` | ✗ refuted |", page)
        self.assertIn("| 1 | That `result >= 0` holds where `a == b` | ✓ holds |", page)
        self.assertIn("| 3 | `m(x=-1)` | `-1` |", page)
        self.assertIn("replayed it on the method in jvmcontract's bytecode interpreter to show", page)

    def test_the_headline_over_mixed_outcomes(self):
        cases = [(["verified", "verified"], "verified"), (["verified", "violation"], "violation"),
                 (["violation", "unverifiable", "verified"], "violation"), (["verified", "unverifiable"], "unverifiable"),
                 (["unverifiable"], "unverifiable"), (["verified", "maybe"], None), ([], None)]
        for verdicts, headline in cases:
            self.assertEqual(build.property_headline(verdicts), headline, verdicts)

    def test_an_unresolved_property_stays_visible_beside_a_refuted_one(self):
        result = self.prove(1, property_outcome(self.root, 1, "unverifiable"), property_outcome(self.root, 2, "violation"),
                            property_outcome(self.root, 3, "verified"))
        self.assertEqual(result["verdict"], "violation")
        self.assertEqual(result["verdictLabel"], "✗ Violation: counterexample found to 1 of 3 properties, 1 unresolved")
        self.assertEqual(result["properties"][0]["problem"], "JBMC gave no verdict within 60 s")
        self.assertEqual(result["problem"], None)  # the headline property's, the refuted one
        page = "\n".join(build.findings_property(example(approach="B11", symbol="a.B#m"), result))
        self.assertIn("⚠ unresolved", page)
        self.assertIn("- Property 1: `JBMC gave no verdict within 60 s`", page)

    def test_one_unresolved_property_leaves_the_change_unverified(self):
        result = self.prove(1, property_outcome(self.root, 1, "verified"), property_outcome(self.root, 2, "unverifiable"),
                            verdict="verified")
        self.assertEqual((result["verdict"], result["matchesExpected"]), ("unverifiable", False))
        self.assertEqual(result["verdictLabel"], "⚠ Unverifiable: 1 of 2 properties unresolved")
        self.assertEqual(result["problem"], "JBMC gave no verdict within 60 s")

    def test_every_property_proved(self):
        result = self.prove(0, property_outcome(self.root, 1, "verified"), property_outcome(self.root, 2, "verified"),
                            verdict="verified")
        self.assertEqual((result["verdict"], result["matchesExpected"]), ("verified", True))
        self.assertEqual(result["verdictLabel"], "✓ Verified: all 2 properties hold on every input")
        self.assertEqual(result["counterexamples"], [])

    def test_an_exit_code_that_disagrees_with_the_headline_is_invalid(self):
        result = self.prove(0, property_outcome(self.root, 1, "verified"), property_outcome(self.root, 2, "violation"))
        self.assertEqual((result["execution"]["status"], result["verdict"]), ("invalid-output", None))
        self.harnesses(1, 2)
        result = self.prove(1, property_outcome(self.root, 1, "verified"), property_outcome(self.root, 2, "verified"))
        self.assertEqual(result["execution"]["status"], "invalid-output")
        self.assertIsNone(result["properties"])
        self.assertEqual(list(self.folder.glob("statement*.java")), [])

    def test_a_refuted_property_needs_its_witness_and_the_report(self):
        result = self.prove(1, property_outcome(self.root, 1, "violation"), property_outcome(self.root, 2, "violation", counterexample=None))
        self.assertEqual((result["execution"]["status"], result["verdict"]), ("invalid-output", None))
        result = self.prove(1, property_outcome(self.root), report=None)
        self.assertEqual(result["execution"]["status"], "invalid-output")
        self.assertIn("no SARIF report", result["execution"]["reason"])

    def test_an_unknown_verdict_among_the_properties_is_invalid(self):
        result = self.prove(1, property_outcome(self.root, 1, "violation"), property_outcome(self.root, 2, "maybe"))
        self.assertEqual((result["execution"]["status"], result["verdict"]), ("invalid-output", None))

    def test_a_vacuous_property_makes_a_verified_headline_vacuous(self):
        reason = "no input in the domain reaches the calls, every one failing the assumption (--assume)"
        outcomes = [property_outcome(self.root, 1, "verified"), property_outcome(self.root, 2, "verified", vacuous=reason)]
        result = self.prove(0, *outcomes, verdict="verified")
        self.assertEqual(result["coverage"], {"vacuous": True, "reason": f"property 2: {reason}"})
        self.assertFalse(result["matchesExpected"])
        self.assertEqual(result["verdictLabel"], "✓ Verified, vacuously for 1 of 2 properties: no input in the domain reaches the calls")
        self.assertTrue(self.prove(0, *outcomes, verdict="verified", vacuous=True)["matchesExpected"])
        # A refuted headline is not vacuous: the vacuous property is in its record.
        result = self.prove(1, property_outcome(self.root, 1, "violation"), outcomes[1])
        self.assertIsNone(result["coverage"])
        self.assertEqual(result["properties"][1]["vacuous"], reason)

    def test_throws_clauses_as_checked(self):
        outcome = property_outcome(self.root, verdict="verified", assert_="true", throws=["ArithmeticException when b == 0"],
                                   throws_checked=["java.lang.ArithmeticException when b == 0"])
        result = self.prove(0, outcome, verdict="verified")
        self.assertEqual(result["property"], {"assert": None, "assume": None, "throws": ["java.lang.ArithmeticException when b == 0"]})

    def test_a_multi_property_result_validates(self):
        import jsonschema
        schema = json.loads((build.EXAMPLES / "schema/result.schema.json").read_text())
        self.harnesses(1, 2)
        result = self.prove(1, property_outcome(self.root, 1, "verified"), property_outcome(self.root, 2, "violation"))
        source = next(build.EXAMPLES.glob("071-*"))
        recorded = json.loads((source / "result.json").read_text())
        merged = {**recorded, **{k: v for k, v in result.items() if k != "after"}}
        jsonschema.validate(merged, schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({**merged, "properties": [{**merged["properties"][0], "verdict": "maybe"}]}, schema)


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


BREAKER_SYMBOL = "net.terminalvalue.crosscut.resilience.CircuitBreaker#decide"
BREAKER_ROW = "decide(OPEN, CallRequested[waitElapsed=false])"


def changed_row(contract, case, outcome):
    """The contract with one case's outcome replaced: a kernel the patch changed."""
    lines = contract.splitlines(True)
    for i, line in enumerate(lines):
        if line.startswith(case + " "):
            lines[i] = line.split("=> ")[0] + "=> " + outcome + "\n"
            return "".join(lines)
    raise AssertionError(f"no case {case}")


class BreakerCase(unittest.TestCase):
    """run_tool_tlc on the circuit breaker's model (two configurations), with the tool mocked."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="build-test-"))
        self.folder = self.dir / "example"
        self.folder.mkdir()
        self.root = self.dir / "root"
        part = build.TOOL_APPS["crosscut"]["root"]
        self.build = self.root / part
        (self.build / "build/main").mkdir(parents=True)  # where the compiled classes would be
        for f in ("src/contract/CircuitBreaker.decide.contract", "spec/CircuitBreaker.cfg", "spec/CircuitBreakerLive.cfg"):
            (self.build / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(build.REPO / part / f, self.build / f)
        self.committed = (self.build / "src/contract/CircuitBreaker.decide.contract").read_text()
        self.patches = [mock.patch.object(build, "jvmcontract", return_value="jvmcontract"),
                        mock.patch.dict(build.os.environ, {"BUILD_CHECKPOINTS": str(self.dir / "checkpoints")}),
                        mock.patch.object(build, "tool_identity", return_value={"jvmcontract": "j", "tla2tools": "t", "java": "v"})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.dir)

    def run_tlc(self, candidate, intended=False, tlc=None, derive=0):
        """run_tool_tlc with the tool mocked: `derive` prints the candidate contract, `update` writes it, TLC answers
        `tlc` (verified, by default; a callable is given the command and returns the process). Records the contract
        each `tla` call saw, every command, and the configurations TLC ran."""
        self.calls, self.generated_from, self.tlc_runs = [], [], []
        contract = self.build / "src/contract/CircuitBreaker.decide.contract"
        contract.write_text(self.committed)  # each run starts from the committed contract, as a fresh copy does
        tlc = tlc or json.dumps({"verdict": "verified", "output": "Model checking completed. No error has been found.",
                                 "trace": [], "version": "TLC 2.19", "distinct_states": 102, "depth": 9, "seconds": 1,
                                 "coverage": [{"symbol": BREAKER_SYMBOL, "listed": True, "rows": [
                                     {"case": BREAKER_ROW, "outcome": "x", "taken": True}]}]})
        def fake(command, **kwargs):
            self.calls.append(command[1] if len(command) > 1 else command[0])
            if command[1] == "derive":
                return proc(derive, candidate if derive == 0 else "", "" if derive == 0 else "error: no method decide\n")
            if command[1] == "update":
                contract.write_text(candidate)
                return proc(1, "updated 1 contract\n")
            if command[1] == "tla":
                self.generated_from.append(contract.read_text())
                return proc(0)
            if command[1] == "tlc":
                self.tlc_runs.append(command[command.index("--config") + 1] if "--config" in command else "primary")
                return tlc(command) if callable(tlc) else proc(0, tlc)
            return proc(0, "stateDiagram-v2\n")
        ex = example("D1", BREAKER_SYMBOL)
        ex["change"]["behaviourChangeIntended"] = intended
        result = empty_result()
        result["contractDiff"] = None
        with mock.patch.object(build.subprocess, "run", side_effect=fake):
            build.run_tool_tlc(self.folder, ex, self.root, "crosscut", result)
        build.finish(result, ex)
        return stores_whole(self, result, self.folder)


class ModelContractTest(BreakerCase):
    """D1 always connects the model's generated operators to the patched bytecode. A kernel the patch changed is checked
    as it was built, whether or not the change was meant to alter behaviour; the flag decides only whether the
    difference is allowed. The review's gap: a change not meant to alter behaviour, whose kernel changed anyway, used to
    be checked against the committed contract and could pass."""

    def test_an_unchanged_kernel_is_the_committed_contract_verified(self):
        result = self.run_tlc(self.committed)
        self.assertEqual(result["modelContracts"], [{
            "symbol": BREAKER_SYMBOL, "contract": "src/contract/CircuitBreaker.decide.contract",
            "operator": "spec/CircuitBreakerContract.tla", "connection": "verified", "rowsChanged": 0, "allowed": True}])
        self.assertNotIn("update", self.calls)  # nothing is regenerated for a change not meant to alter behaviour
        self.assertEqual((result["verdict"], result["modelVerdict"], result["contractDiff"]), ("verified", "verified", None))
        self.assertEqual(result["verdictLabel"], result["modelSummary"])

    def test_a_kernel_changed_without_an_intended_change_is_checked_as_built_and_fails(self):
        candidate = changed_row(self.committed, BREAKER_ROW, "Transition[next=HALF_OPEN, effects=[RESET_METRICS, PERMIT]]")
        result = self.run_tlc(candidate)
        # The model is generated from the rule that was built, not the committed one...
        self.assertEqual(self.generated_from, [candidate])
        self.assertEqual(result["coverage"]["changedRows"][0]["case"], BREAKER_ROW)
        # ...and the difference nobody approved is a violation, though TLC found the model to hold on it.
        (connection,) = result["modelContracts"]
        self.assertEqual((connection["connection"], connection["rowsChanged"], connection["allowed"]), ("derived", 1, False))
        self.assertEqual((result["verdict"], result["modelVerdict"], result["execution"]["status"]), ("violation", "verified", "completed"))
        self.assertIn("no behaviour change intended", result["verdictLabel"])
        self.assertRegex(result["contractDiff"], r"(?m)^\+" + re.escape(BREAKER_ROW) + r" +=> Transition\[next=HALF_OPEN")
        sarif = json.loads((self.folder / "result.sarif").read_text())
        self.assertEqual([r["ruleId"] for r in sarif["runs"][0]["results"]], ["contract-changed"])
        self.assertEqual(result["expectation"], "yes")  # the example expects a violation

    def test_an_intended_change_regenerates_the_contracts_and_is_allowed(self):
        candidate = changed_row(self.committed, BREAKER_ROW, "Transition[next=HALF_OPEN, effects=[RESET_METRICS, PERMIT]]")
        result = self.run_tlc(candidate, intended=True)
        self.assertIn("update", self.calls)
        (connection,) = result["modelContracts"]
        self.assertEqual((connection["connection"], connection["rowsChanged"], connection["allowed"]), ("derived", 1, True))
        self.assertEqual(result["verdict"], "verified")
        self.assertEqual(self.generated_from[0], candidate)

    def test_a_reason_alone_is_a_change_of_the_contract(self):
        candidate = changed_row(self.committed, BREAKER_ROW, 'Rejected[reason="open"]')
        result = self.run_tlc(candidate)
        self.assertEqual(result["modelContracts"][0]["rowsChanged"], 1)
        self.assertEqual(result["verdict"], "violation")
        self.assertEqual(result["coverage"]["changedRows"], [])  # the model reads no reason: no row of it changed

    def test_a_kernel_that_cannot_be_derived_gives_no_verdict_and_no_model_check(self):
        result = self.run_tlc(self.committed, derive=1)
        self.assertIsNone(result["verdict"])
        self.assertEqual(result["execution"]["status"], "tool-error")
        self.assertIn("could not derive the contract of " + BREAKER_SYMBOL, result["execution"]["reason"])
        self.assertNotIn("tla", self.calls)
        self.assertNotIn("tlc", self.calls)
        self.assertFalse((self.folder / "result.sarif").exists())

    def test_tlcs_violation_stays_the_headline_beside_a_changed_contract(self):
        steps = [{"step": 1, "action": "Initial predicate", "changes": {"x": "0"}},
                 {"step": 2, "action": "Request", "changes": {"x": "1"}}]
        tlc = json.dumps({"verdict": "violation", "invariant": "NoCallBeforeTheWait", "kind": "invariant", "trace": steps,
                          "output": "Error: Invariant NoCallBeforeTheWait is violated.", "version": "TLC 2.19",
                          "distinct_states": 12, "coverage": None})
        candidate = changed_row(self.committed, BREAKER_ROW, "Transition[next=OPEN, effects=[PERMIT]]")
        result = self.run_tlc(candidate, tlc=tlc)
        self.assertEqual((result["verdict"], result["modelVerdict"], result["invariant"]), ("violation", "violation", "NoCallBeforeTheWait"))
        self.assertEqual(len(result["trace"]), 2)
        self.assertIn("NoCallBeforeTheWait", result["verdictLabel"])
        sarif = json.loads((self.folder / "result.sarif").read_text())
        self.assertEqual(sorted(r["ruleId"] for r in sarif["runs"][0]["results"]), ["contract-changed", "invariant-violated", "invariant-violated"])

    def test_the_page_leads_with_the_unapproved_change_and_the_result_validates(self):
        import jsonschema
        candidate = changed_row(self.committed, BREAKER_ROW, "Transition[next=HALF_OPEN, effects=[RESET_METRICS, PERMIT]]")
        result = self.run_tlc(candidate)
        source = next(build.EXAMPLES.glob("076-*"))
        recorded = json.loads((source / "result.json").read_text())
        merged = {**recorded, **{k: v for k, v in result.items() if k not in ("after",)}}
        jsonschema.validate(merged, json.loads((build.EXAMPLES / "schema/result.schema.json").read_text()))
        ex = {**json.loads((source / "example.json").read_text()), "change": {**json.loads((source / "example.json").read_text())["change"], "behaviourChangeIntended": False}}
        text = "\n".join(build.findings_tlc(ex, merged))
        self.assertLess(text.index("| fairness"), text.index("alters a rule it is not meant to"))
        self.assertLess(text.index("alters a rule it is not meant to"), text.index("Every invariant holds"))
        self.assertIn("TLC's verdict on the patched rule: ✓ Verified", text)
        verified = self.run_tlc(self.committed)
        text = "\n".join(build.findings_tlc(ex, {**recorded, **{k: v for k, v in verified.items() if k != "after"}}))
        self.assertIn("the committed contract, which the patched classes still match", text)

    def test_a_result_recorded_before_the_connection_renders_as_before(self):
        source = next(build.EXAMPLES.glob("076-*"))
        recorded = json.loads((source / "result.json").read_text())
        self.assertNotIn("modelContracts", recorded)
        self.assertNotIn("rules come from", "\n".join(build.findings_tlc(json.loads((source / "example.json").read_text()), recorded)))


def tlc_verified(*coverage, states=102):
    return json.dumps({"verdict": "verified", "output": "Model checking completed. No error has been found.", "trace": [],
                       "version": "TLC 2.19", "distinct_states": states, "depth": 9, "seconds": 1, "coverage": list(coverage)})


def breaker_coverage(taken, listed=True):
    return {"symbol": BREAKER_SYMBOL, "listed": listed, "rows": [{"case": BREAKER_ROW, "outcome": "x", "taken": taken},
                                                                 {"case": "decide(CLOSED, X[])", "outcome": "y", "taken": 3}]}


class CoverageStatusTest(unittest.TestCase):
    """TLC coverage that was not read is unknown, not zero: only complete coverage can make a verdict vacuous, and the
    page says what is missing. The review found a verified run with no coverage read as no row taken, so vacuous."""

    configurations = [{"label": "the model"}, {"label": "fairness"}]
    before = {"c": {BREAKER_ROW: "Rejected"}}
    after = {"c": {BREAKER_ROW: "Transition[next=HALF_OPEN, effects=[PERMIT]]"}}

    def coverage(self, *runs):
        return build.tlc_coverage(self.configurations[:len(runs)], list(runs), self.before, self.after, {"c": BREAKER_SYMBOL})

    def verified(self, *operators):
        return {"verdict": "verified", "execution": {"status": "completed", "reason": None}, "coverage": list(operators) or None}

    def test_no_coverage_read_is_unavailable_and_not_vacuous(self):
        cov = self.coverage(self.verified())
        self.assertEqual((cov["status"], cov["vacuous"]), ("unavailable", False))
        self.assertEqual(cov["changedRows"][0]["unknownUnder"], ["the model"])
        self.assertEqual(cov["configurations"][0]["coverageStatus"], "unavailable")
        text = "\n".join(build.coverage_lines({"coverage": cov}))
        self.assertIn("What the verdict rests on is not known", text)
        self.assertIn("not called vacuous", text)
        self.assertIn("Whether a run takes the 1 row the change alters is not known", text)

    def test_an_operator_the_statistics_do_not_list_is_not_counted(self):
        # The library reads zero for every row of an operator its statistics do not list; zero means nothing then.
        cov = self.coverage(self.verified(breaker_coverage(0)), self.verified(breaker_coverage(0, listed=False)))
        self.assertEqual((cov["status"], cov["vacuous"]), ("partial", False))
        self.assertEqual(cov["configurations"][1]["coverageStatus"], "unavailable")  # its one operator is not listed
        self.assertEqual(cov["changedRows"][0]["unknownUnder"], ["fairness"])
        text = "\n".join(build.coverage_lines({"coverage": cov}))
        self.assertIn("| fairness | not counted |", text)
        self.assertIn("not counted under fairness", text)
        self.assertIn("**Some of it is not known.**", text)
        self.assertNotIn("No run of the model takes any of them", text)

    def test_complete_coverage_that_takes_no_altered_row_is_vacuous(self):
        cov = self.coverage(self.verified(breaker_coverage(0)), self.verified(breaker_coverage(0)))
        self.assertEqual((cov["status"], cov["vacuous"]), ("complete", True))
        self.assertIn("No run of the model takes any of them", "\n".join(build.coverage_lines({"coverage": cov})))
        taken = self.coverage(self.verified(breaker_coverage(4)), self.verified(breaker_coverage(0)))
        self.assertEqual((taken["status"], taken["vacuous"], taken["changedRows"][0]["takenUnder"]), ("complete", False, ["the model"]))

    def test_a_tool_without_the_listed_flag_gives_no_vacuous_verdict(self):
        # A jvmcontract from before the flag cannot tell an operator it did not find from one no step took.
        old = breaker_coverage(0)
        del old["listed"]
        self.assertEqual(self.coverage(self.verified(old))["status"], "unavailable")

    def test_a_run_without_a_verdict_is_not_said_to_stop_at_a_counterexample(self):
        late = {"verdict": "unverifiable", "execution": {"status": "timed-out", "reason": "TLC did not finish within 1800 s"},
                "coverage": None}
        cov = self.coverage(self.verified(breaker_coverage(0)), late)
        fairness = cov["configurations"][1]
        self.assertEqual((fairness["verdict"], fairness["status"], fairness["reason"]), (None, "timed-out", "TLC did not finish within 1800 s"))
        self.assertEqual((cov["status"], cov["vacuous"]), ("partial", False))
        text = "\n".join(build.coverage_lines({"coverage": cov}))
        self.assertIn("| fairness | no verdict: timed out |", text)
        self.assertNotIn("counterexample", text)
        self.assertIn("ended without a verdict (TLC did not finish within 1800 s)", text)
        violated = {"verdict": "violation", "execution": {"status": "completed", "reason": None}, "coverage": None}
        text = "\n".join(build.coverage_lines({"coverage": self.coverage(self.verified(breaker_coverage(0)), violated)}))
        self.assertIn("| fairness | stopped at the counterexample |", text)
        self.assertIn("The run under fairness stopped at its counterexample", text)

    def test_results_recorded_before_the_status_render_as_they_did(self):
        # Every recorded D1 result renders, and those whose coverage has no status say nothing of missing coverage.
        for path in sorted(build.EXAMPLES.glob("*/result.json")):
            res = json.loads(path.read_text())
            if res.get("coverage") and "changedRows" in res["coverage"] and "status" not in res["coverage"]:
                text = "\n".join(build.coverage_lines(res))
                self.assertNotIn("not known", text, path.parent.name)
                self.assertNotIn("not counted", text, path.parent.name)


class CheckpointTest(BreakerCase):
    """Each configuration's TLC result is kept as soon as it completes and reused only when every input matches; an
    error in a later configuration keeps the earlier ones. The review found the runs held in memory until the last."""

    def setUp(self):
        super().setUp()
        self.store = self.dir / "checkpoints"

    def test_a_later_configuration_that_fails_keeps_the_earlier_one(self):
        def tlc(command):
            if "--config" in command:
                raise OSError("the tool could not be started")
            return proc(0, tlc_verified(breaker_coverage(2)))
        result = self.run_tlc(self.committed, tlc=tlc)
        model, fairness = result["configurations"]
        self.assertEqual((model["verdict"], model["status"]), ("verified", "completed"))
        self.assertEqual((fairness["verdict"], fairness["status"]), ("unverifiable", "tool-error"))
        self.assertIn("the tool could not be started", fairness["reason"])
        self.assertIsNone(result["verdict"])  # the run as a whole has no verdict...
        self.assertEqual(result["expectation"], "not-evaluable")
        kept = list(self.store.glob("*.json"))  # ...but the configuration that completed is kept
        self.assertEqual(len(kept), 1)
        self.assertEqual(json.loads(kept[0].read_text())["label"], "two calls in flight")
        self.assertEqual([c["reused"] for c in result["checkpoints"]], [False, False])
        # Run again with the fault gone: the kept configuration is reused, the other runs.
        again = self.run_tlc(self.committed, tlc=lambda command: proc(0, tlc_verified(breaker_coverage(2))))
        self.assertEqual(self.tlc_runs, ["spec/CircuitBreakerLive.cfg"])
        self.assertEqual([c["reused"] for c in again["checkpoints"]], [True, False])
        self.assertEqual(again["checkpoints"][0]["fingerprint"], result["checkpoints"][0]["fingerprint"])
        self.assertEqual(again["verdict"], "verified")
        self.assertEqual(len(list(self.store.glob("*.json"))), 2)
        source = next(build.EXAMPLES.glob("076-*"))
        recorded = json.loads((source / "result.json").read_text())
        text = "\n".join(build.findings_tlc(json.loads((source / "example.json").read_text()),
                                            {**recorded, **{k: v for k, v in again.items() if k != "after"}}))
        self.assertIn("Under two calls in flight, TLC was not run again", text)
        self.assertNotIn("Under fairness, TLC was not run again", text)
        self.assertNotIn("Results reused", "\n".join(build.findings_tlc(json.loads((source / "example.json").read_text()), recorded)))

    def test_a_run_without_a_verdict_is_not_kept(self):
        late = json.dumps({"verdict": "unverifiable", "output": "Error: java did not finish within 1800 s", "trace": [],
                           "version": "TLC 2.19", "coverage": []})
        result = self.run_tlc(self.committed, tlc=late)
        self.assertEqual(result["execution"]["status"], "timed-out")
        self.assertEqual(list(self.store.glob("*.json")), [])
        self.run_tlc(self.committed, tlc=late)
        self.assertEqual(len(self.tlc_runs), 2)  # both configurations ran again

    def test_any_changed_input_runs_again(self):
        self.run_tlc(self.committed, tlc=tlc_verified(breaker_coverage(2)))
        # The patched rule: the generated operator differs, so neither configuration's result is reused.
        candidate = changed_row(self.committed, BREAKER_ROW, "Transition[next=HALF_OPEN, effects=[PERMIT]]")
        def tla(command):
            return proc(0, tlc_verified(breaker_coverage(2)))
        original = build.tool
        def tool(app, root, *args, **kwargs):
            if args[0] == "tla":
                (self.build / args[2]).write_text(f"---- generated from ----\n{(self.build / args[1]).read_text()}")
            return original(app, root, *args, **kwargs)
        with mock.patch.object(build, "tool", side_effect=tool):
            result = self.run_tlc(candidate, tlc=tla)
        self.assertEqual(len(self.tlc_runs), 2)
        self.assertEqual([c["reused"] for c in result["checkpoints"]], [False, False])
        # The same inputs and another tool: run again too.
        with mock.patch.object(build, "tool_identity", return_value={"jvmcontract": "other", "tla2tools": "t", "java": "v"}), \
                mock.patch.object(build, "tool", side_effect=tool):
            self.run_tlc(candidate, tlc=tla)
        self.assertEqual(len(self.tlc_runs), 2)

    def test_a_kept_result_whose_inputs_differ_is_not_reused(self):
        self.run_tlc(self.committed, tlc=tlc_verified(breaker_coverage(2)))
        for path in self.store.glob("*.json"):  # a file whose name matches but whose inputs do not
            kept = json.loads(path.read_text())
            kept["inputs"]["cfg"] = "elsewhere.cfg"
            path.write_text(json.dumps(kept))
        self.run_tlc(self.committed, tlc=tlc_verified(breaker_coverage(2)))
        self.assertEqual(len(self.tlc_runs), 2)

    def test_checkpoints_off_keeps_nothing(self):
        with mock.patch.dict(build.os.environ, {"BUILD_CHECKPOINTS": "off"}):
            result = self.run_tlc(self.committed, tlc=tlc_verified(breaker_coverage(2)))
        self.assertFalse(self.store.exists())
        self.assertEqual(result["verdict"], "verified")


class BoxOfficeModelContractTest(unittest.TestCase):
    """The Box Office model, whose order state machine is generated by the Gradle build's verifier: the contract is
    regenerated on every run, and a change of it not meant is a violation."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="build-test-"))
        self.folder = self.dir / "example"
        self.folder.mkdir()
        self.tmp = self.dir / "tmp"
        root = self.tmp / build.BUILD_ROOT
        for f in (build.CONTRACT_FILE, f"{build.SPEC}/BoxOffice.cfg"):
            (root / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(build.REPO / build.BUILD_ROOT / f, root / f)
        self.contract = root / build.CONTRACT_FILE
        self.committed = self.contract.read_text()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def run_tlc(self, candidate, intended=False):
        def gradle(build_dir, task, *extra, **kwargs):
            self.assertEqual(task, ":ticketing-domain:updateContracts")
            self.contract.write_text(candidate)
            return proc(0)
        def run(command, **kwargs):
            if "contract_to_tla.py" in str(command[1]):
                self.generated_from = self.contract.read_text()
                return proc(0)
            return proc(0, "TLC2 Version 2.19\nModel checking completed. No error has been found.\n"
                           "1,234 states generated, 610 distinct states found, 0 states left on queue.\n")
        ex = example("D1", "net.terminalvalue.boxoffice.ticketing.app.HoldService#releaseExpiredHolds", verdict="verified")
        ex["subject"]["file"] = f"{build.BUILD_ROOT}/ticketing-service/src/main/java/HoldService.java"
        ex["change"]["behaviourChangeIntended"] = intended
        result = empty_result()
        result["contractDiff"] = None
        with mock.patch.object(build, "gradle", side_effect=gradle), \
                mock.patch.object(build.subprocess, "run", side_effect=run), \
                mock.patch.object(build, "tlc", return_value=["tlc"]):
            build.run_tlc(self.folder, ex, self.tmp, "ticketing-service", result)
        build.finish(result, ex)
        return result

    def test_an_unchanged_order_machine_is_verified_against_the_patched_build(self):
        result = self.run_tlc(self.committed)
        self.assertEqual(result["modelContracts"][0]["connection"], "verified")
        self.assertEqual((result["verdict"], result["contractDiff"], result["expectation"]), ("verified", None, "yes"))

    def test_an_order_machine_changed_unasked_is_checked_as_built_and_fails(self):
        row = "decide(PENDING_PAYMENT, PaymentDeclined[])"
        candidate = changed_row(self.committed, row, "Unchanged[reason=\"declined\"]")
        result = self.run_tlc(candidate)
        self.assertEqual(self.generated_from, candidate)
        self.assertEqual((result["modelContracts"][0]["allowed"], result["verdict"], result["modelVerdict"]), (False, "violation", "verified"))
        self.assertIn(row, result["contractDiff"])
        self.assertEqual(result["expectation"], "no")  # the example expects the model to hold


class MainTest(unittest.TestCase):
    def test_a_run_without_a_verdict_fails_and_the_pipeline_sees_it(self):
        """build.py exits 1 and prints a line the pipeline's `example:unexpected` signal reads."""
        sys.path.insert(0, str(build.REPO / "verification"))
        import pipeline
        unexpected = next(pattern for source, key, pattern in pipeline.SIGNALS if (source, key) == ("example", "unexpected"))
        folder = next(build.EXAMPLES.glob("126-*"))
        dir = Path(tempfile.mkdtemp(prefix="build-test-"))
        self.addCleanup(shutil.rmtree, dir)

        def run(f, ex, out):
            result = empty_result()
            result["execution"] = build.execution_status(-9, "")
            build.finish(result, ex)
            return left_evidence(result, out)

        out = io.StringIO()
        with mock.patch.object(build, "run", side_effect=run), mock.patch.object(build, "EXAMPLES", dir), \
                mock.patch.object(build, "render_example", return_value=""), mock.patch.object(build, "render_index"), \
                mock.patch.object(build, "validate"), mock.patch.object(build, "load_example", side_effect=lambda f: json.loads((f / "example.json").read_text())), \
                contextlib.redirect_stdout(out):
            shutil.copytree(folder, dir / folder.name)
            self.assertEqual(build.main([folder.name[:3]]), 1)
        self.assertTrue(any(unexpected.search(line) for line in out.getvalue().splitlines()), out.getvalue())
        self.assertIn("killed by signal 9", out.getvalue())


class SelectionTest(unittest.TestCase):
    """What build.py does with the ids it is given: run them, or say why not, and never exit 0 for nothing run."""

    def setUp(self):
        sys.path.insert(0, str(build.REPO / "verification"))
        import pipeline
        self.signals = {(source, key): pattern for source, key, pattern in pipeline.SIGNALS}
        self.dir = Path(tempfile.mkdtemp(prefix="build-test-"))
        self.addCleanup(shutil.rmtree, self.dir)
        shutil.copy(build.EXAMPLES / "tags.json", self.dir / "tags.json")
        for prefix in ("126-", "108-"):  # a constructed example and a real-world one
            folder = next(build.EXAMPLES.glob(prefix + "*"))
            shutil.copytree(folder, self.dir / folder.name)
        self.ran = []

    def main(self, *argv):
        def run(folder, ex, out):
            self.ran.append(folder.name[:3])
            result = empty_result()
            result["execution"] = build.execution_status(0, "VERIFICATION FAILED")
            result["verdict"] = ex["expected"]["verdict"]
            build.finish(result, ex)
            return left_evidence(result, out)

        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(build, "run", side_effect=run), mock.patch.object(build, "EXAMPLES", self.dir), \
                mock.patch.object(build, "render_example", return_value=""), mock.patch.object(build, "render_index"), \
                mock.patch.object(build, "validate"), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = build.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_an_unknown_id_exits_2_and_runs_nothing(self):
        code, out, err = self.main("126", "999")
        self.assertEqual((code, self.ran), (2, []))
        self.assertIn("no example with id 999", err)

    def test_an_argument_that_is_not_an_id_exits_2(self):
        for argv in (["126-backoff"], ["--fast", "126"], ["--index-only", "126"], ["--render-only", "12"]):
            with self.subTest(argv=argv):
                code, out, err = self.main(*argv)
                self.assertEqual((code, self.ran), (2, []))

    def test_a_requested_real_world_example_is_not_executed_and_fails_the_run(self):
        code, out, err = self.main("108")
        self.assertEqual((code, self.ran), (1, []))
        lines = out.splitlines()
        self.assertTrue(any(self.signals[("example", "not-executed")].search(line) for line in lines), out)
        self.assertFalse(any(self.signals[("example", "as-expected")].search(line) for line in lines), out)
        self.assertIn("real-world", out)

    def test_a_real_world_example_beside_a_constructed_one_still_fails_the_run(self):
        code, out, err = self.main("126", "108")
        self.assertEqual((code, self.ran), (1, ["126"]))
        self.assertIn("Not executed: 108-", out)

    def test_every_example_means_every_constructed_one(self):
        code, out, err = self.main()
        self.assertEqual((code, self.ran), (0, ["126"]))
        self.assertNotIn("not-executed", out)

    def test_an_example_no_app_builds_is_not_executed_and_its_result_is_left(self):
        folder = next(self.dir.glob("126-*"))
        before = (folder / "result.json").read_text()
        ex = json.loads((folder / "example.json").read_text())
        ex["subject"]["file"] = "examples/apps/nowhere/src/Backoff.java"
        (folder / "example.json").write_text(json.dumps(ex))
        code, out, err = self.main("126")
        self.assertEqual((code, self.ran), (1, []))
        self.assertIn("not-executed (its subject file examples/apps/nowhere/src/Backoff.java", out)
        self.assertEqual((folder / "result.json").read_text(), before)

    def test_reasons_for_not_executing(self):
        self.assertIsNone(build.not_executable(example()))
        self.assertIn("no runner for approach B12", build.not_executable(example(approach="B12")))
        self.assertIn("no TLA+ model of crosscut", build.not_executable(example(approach="D1")))
        self.assertIn("real-world", build.not_executable({**example(), "origin": "real-world"}))

    def test_render_only_of_an_example_it_cannot_render_fails(self):
        code, out, err = self.main("--render-only", "108")
        self.assertEqual(code, 1)
        self.assertIn("not rendered (a real-world example", out)
        self.assertEqual(self.main("--render-only", "126")[0], 0)


class ReplayWordingTest(unittest.TestCase):
    """The page says where a witness was replayed from what the result records, never from the approach."""

    def page(self, **res):
        ex = example()
        return "\n".join(build.findings_equivalence(ex, {"verdict": "violation", "domain": "x: int", "proof": None,
                                                         "counterexamples": [{"input": "m(x=1)", "contract": "1", "actual": "2"}], **res}))

    def test_jvmcontract_replays_in_its_interpreter(self):
        page = self.page(replay={"by": "interpreter", "reproduced": True})
        self.assertIn("replayed it in jvmcontract's bytecode interpreter against both versions", page)
        self.assertNotIn("JVM", page)

    def test_a_result_recorded_before_the_replay_record_reads_its_proof_line(self):
        page = self.page(proof="found by JBMC 6.11.0 in 1.0 s, replayed in the interpreter; domain x: int")
        self.assertIn("in jvmcontract's bytecode interpreter", page)
        page = self.page(proof="found by JBMC 6.11.0 in 0.2 s searching inputs in [0:20], replayed on the JVM; domain x: int")
        self.assertIn("replayed it on the JVM", page)

    def test_nothing_recorded_claims_no_replay(self):
        page = self.page()
        self.assertNotIn("replayed", page)
        self.assertIn("on which the two versions do this:", page)

    def test_no_recorded_tool_example_is_said_to_be_replayed_on_the_jvm(self):
        for folder in sorted(build.EXAMPLES.glob("[0-9][0-9][0-9]-*")):
            ex = json.loads((folder / "example.json").read_text())
            if ex.get("origin") != "constructed" or ex["approach"]["id"] != "B9" or (folder / "result.json").exists() is False:
                continue
            res = json.loads((folder / "result.json").read_text())
            if res.get("verdict") != "violation":
                continue
            page = "\n".join(build.findings_equivalence(ex, res))
            self.assertEqual("on the JVM" in page, build.app_of(ex) == "boxoffice", folder.name)


class PlanTest(unittest.TestCase):
    """plan(): what a run takes, resolved from example.json with no side effect, and the same for build.py and the
    pipeline."""

    def recorded(self):
        for folder in sorted(build.EXAMPLES.glob("[0-9][0-9][0-9]-*")):
            ex = json.loads((folder / "example.json").read_text())
            if ex["origin"] == "constructed":
                yield folder, ex

    def test_planning_every_example_builds_copies_runs_and_makes_nothing(self):
        def refuse(*args, **kwargs):
            raise AssertionError(f"plan() had a side effect: {args!r}")
        with mock.patch.object(build.subprocess, "run", side_effect=refuse), \
                mock.patch.object(build.shutil, "copytree", side_effect=refuse), \
                mock.patch.object(build.tempfile, "mkdtemp", side_effect=refuse), \
                mock.patch.object(build.tempfile, "TemporaryDirectory", side_effect=refuse), \
                mock.patch.object(build, "scratch", side_effect=refuse):
            plans = [build.plan(ex) for _, ex in self.recorded()]
        self.assertTrue(plans)
        for q in plans:
            self.assertTrue(q["executable"], q)
            self.assertIn(q["approach"], build.RUNNERS[q["app"]])
            self.assertEqual(q["runner"], build.RUNNERS[q["app"]][q["approach"]].__name__)

    def test_importing_build_py_makes_no_directory(self):
        code = (f"import sys, tempfile\n"
                f"made = []\n"
                f"real = tempfile.mkdtemp\n"
                f"tempfile.mkdtemp = lambda *a, **k: made.append(a) or real(*a, **k)\n"
                f"sys.path.insert(0, {str(HERE)!r})\n"
                f"import build\n"
                f"build.plan(build.load_example(next(build.EXAMPLES.glob('124-*'))))\n"
                f"print(len(made))\n")
        out = subprocess.run([sys.executable, "-c", code], text=True, capture_output=True, check=True).stdout
        self.assertEqual(out.strip(), "0")

    def test_the_tool_s_own_checker_needs_no_jbmc_and_auto_may(self):
        ex = example()
        self.assertEqual(build.plan(ex)["engine"], "jbmc")
        self.assertEqual(build.plan(ex)["tools"], {"required": ["java", "javac", "jvmcontract", "jbmc"], "optional": []})
        ex["approach"]["engine"] = "native"
        q = build.plan(ex)
        self.assertEqual((q["engine"], q["options"]), ("native", ["--engine", "native"]))
        self.assertEqual(q["tools"], {"required": ["java", "javac", "jvmcontract"], "optional": []})
        ex["approach"]["engine"] = "auto"
        self.assertEqual(build.plan(ex)["tools"], {"required": ["java", "javac", "jvmcontract"], "optional": ["jbmc"]})
        prop = example(approach="B11")
        prop["approach"]["engine"] = "native"
        self.assertNotIn("jbmc", build.plan(prop)["tools"]["required"])

    def test_box_office_b12_calls_jvmcontract_and_b8_does_not(self):
        b12 = next(ex for _, ex in self.recorded() if ex["approach"]["id"] == "B12")
        self.assertEqual(build.plan(b12)["tools"]["required"], ["java", "javac", "gradle", "jvmcontract"])
        b8 = next(ex for _, ex in self.recorded() if ex["approach"]["id"] == "B8" and build.app_of(ex) == "boxoffice")
        self.assertEqual(build.plan(b8)["tools"]["required"], ["java", "javac", "gradle"])
        b9 = next(ex for _, ex in self.recorded() if ex["approach"]["id"] == "B9" and build.app_of(ex) == "boxoffice")
        q = build.plan(b9)
        self.assertEqual((q["engine"], q["tools"]["required"]), ("jbmc", ["java", "javac", "gradle", "jbmc"]))

    def test_every_recorded_native_example_plans_without_jbmc(self):
        native = [build.plan(ex) for _, ex in self.recorded() if ex["approach"].get("engine") == "native"]
        self.assertGreaterEqual(len(native), 15)
        for q in native:
            self.assertNotIn("jbmc", q["tools"]["required"] + q["tools"]["optional"], q["example"])

    def test_a_d1_plan_names_the_model_and_every_configuration(self):
        for folder, ex in self.recorded():
            if ex["approach"]["id"] != "D1":
                continue
            q = build.plan(ex)
            self.assertIn("tlc", q["tools"]["required"])
            self.assertTrue((build.REPO / q["model"]["spec"]).exists(), q["model"]["spec"])
            for c in q["model"]["configurations"]:
                self.assertTrue((build.REPO / c["cfg"]).exists(), c["cfg"])
            if q["app"] != "boxoffice":
                files = build.find_model(ex)
                self.assertEqual(len(q["model"]["configurations"]), len(build.tlc_configurations(files)))
                self.assertIn(files["symbol"], q["model"]["operators"])

    def test_the_runner_passes_the_plan_s_options(self):
        ex = example(verdict="verified")
        ex["approach"].update({"engine": "native", "unwind": 32, "maxArrayLength": 12})
        options = build.plan(ex)["options"]
        self.assertEqual(options, ["--engine", "native", "--unwind", "32", "--max-array-length", "12"])
        root = Path(tempfile.mkdtemp(prefix="build-test-"))
        self.addCleanup(shutil.rmtree, root)
        commands = []
        def fake(command, **kwargs):
            commands.append(command)
            return proc(0, equivalence_json(root, "verified"))
        with mock.patch.object(build, "jvmcontract", return_value="jvmcontract"), \
                mock.patch.object(build, "tool_before_classes", return_value=root / "before"), \
                mock.patch.object(build.subprocess, "run", side_effect=fake):
            build.run_tool_equivalence(root, ex, root, "crosscut", empty_result())
        at = commands[0].index("--engine")
        self.assertEqual(commands[0][at:at + len(options)], options)

    def test_an_example_build_py_does_not_run_has_a_plan_that_says_why(self):
        ex = example()
        ex["subject"]["file"] = "src/main/java/A.java"
        q = build.plan(ex)
        self.assertFalse(q["executable"])
        self.assertIn("no app builds it", q["notExecuted"])
        self.assertNotIn("tools", q)

    def test_plan_mode_prints_json_and_runs_nothing(self):
        out = io.StringIO()
        with mock.patch.object(build, "run", side_effect=AssertionError("ran")), mock.patch.object(build, "render_index"), \
                contextlib.redirect_stdout(out):
            code = build.main(["--plan", "124", "110"])
        self.assertEqual(code, 0)
        plans = json.loads(out.getvalue())
        self.assertEqual([q["example"] for q in plans], ["110", "124"])
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(build.main(["--plan", "12x"]), 2)

    def test_the_pipeline_requires_what_the_plan_says(self):
        sys.path.insert(0, str(build.REPO / "verification"))
        import pipeline
        for _, ex in self.recorded():
            parts = pipeline.example_job_parts(ex["id"])
            q = build.plan(ex)
            self.assertEqual(parts["requires"], q["tools"]["required"] + q["tools"]["optional"], ex["id"])
            self.assertEqual(parts["capability"], q["approach"])


class EvidenceTest(unittest.TestCase):
    """Step 3b: the claim is fingerprinted and frozen before the run, the run is an attempt in its own directory, and
    what is published is one checked bundle, so a report names its inputs and cannot mix runs."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="build-test-"))
        self.addCleanup(shutil.rmtree, self.dir)
        self.source = next(build.EXAMPLES.glob("126-*"))
        self.example = json.loads((self.source / "example.json").read_text())
        self.patch = (self.source / "change.patch").read_text()

    def tree(self, name, files):
        root = self.dir / name
        for path, text in files.items():
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_text(text)
        return root

    def claim(self, example=None, patch=None, after=None):
        example = example or self.example
        q = build.plan(example)
        part = q["build"]["copies"][0]
        before = self.tree("before", {f"{part}/src/A.java": "class A {}"})
        after = after or self.tree("after", {f"{part}/src/A.java": "class A { int x; }"})
        return build.claim_record(example, q, patch or self.patch, before, after)

    def test_the_sources_are_fingerprinted_without_build_output(self):
        a = self.tree("a", {"app/src/A.java": "class A {}"})
        b = self.tree("b", {"app/src/A.java": "class A {}", "app/build/main/A.class": "\xca\xfe", "app/src/A.class": "x"})
        c = self.tree("c", {"app/src/A.java": "class A { }"})
        self.assertEqual(build.tree_digest(a, ["app"]), build.tree_digest(b, ["app"]))
        self.assertNotEqual(build.tree_digest(a, ["app"]), build.tree_digest(c, ["app"]))
        self.assertEqual(build.tree_digest(a, ["app"])["files"], 1)
        self.assertIsNone(build.tree_digest(a, ["missing"]))

    def test_another_input_or_scope_is_another_claim_and_another_engine_is_not(self):
        claim = self.claim()
        self.assertRegex(claim["id"], r"^[0-9a-f]{16}$")
        self.assertEqual(claim["id"], self.claim()["id"])
        self.assertNotEqual(claim["inputs"]["before"], claim["inputs"]["after"])
        bound = {**self.example, "approach": {**self.example["approach"], "maxArrayLength": 12}}
        scoped = {**self.example, "change": {**self.example["change"], "intendedInputs": "attempt < 0"}}
        native = {**self.example, "approach": {**self.example["approach"], "engine": "native"}}
        self.assertNotEqual(self.claim(bound)["id"], claim["id"])
        self.assertNotEqual(self.claim(scoped)["id"], claim["id"])
        self.assertNotEqual(self.claim(patch=self.patch + "\n")["id"], claim["id"])
        part = build.plan(self.example)["build"]["copies"][0]
        other = self.tree("other", {f"{part}/src/A.java": "class A { long x; }"})
        self.assertNotEqual(self.claim(after=other)["id"], claim["id"])
        self.assertEqual(self.claim(native)["id"], claim["id"])  # the engine belongs to the attempt
        self.assertEqual(claim["scope"], {"maxArrayLength": None, "intendedInputs": None})

    def test_a_d1_claim_fingerprints_its_model(self):
        ex = json.loads(next(build.EXAMPLES.glob("072-*")).joinpath("example.json").read_text())
        q = build.plan(ex)
        files = {q["model"]["spec"]: "---- MODULE M ----\n====", **{c["cfg"]: "INIT Init" for c in q["model"]["configurations"]}}
        after = self.tree("model", files)
        claim = build.claim_record(ex, q, "patch", after, after)
        self.assertEqual(set(claim["inputs"]["model"]), set(files))
        self.assertTrue(all(claim["inputs"]["model"].values()))
        self.assertEqual(claim["scope"], {})

    def bundle(self, files, **result):
        out = self.dir / "attempt"
        out.mkdir(exist_ok=True)
        for name, text in files.items():
            (out / name).write_text(text)
        result = {"sarif": "result.sarif" if "result.sarif" in files else None, "output": "verifier-output.txt",
                  "statement": "statement.java" if "statement.java" in files else None, **result}
        if "verdict" in result:
            return out, with_blocks(result, out)
        result["bundle"] = build.bundle_record(out)
        return out, result

    def test_a_bundle_lists_the_evidence_and_shows_what_is_not_its(self):
        out, result = self.bundle({"verifier-output.txt": "✗", "result.sarif": "{}", "statement.java": "class H {}", "claim.json": "{}"})
        self.assertEqual([a["path"] for a in result["bundle"]["artifacts"]], ["result.sarif", "statement.java", "verifier-output.txt"])
        self.assertEqual(build.bundle_problems(out, result), [])
        (out / "statement.java").write_text("class Other {}")
        (out / "statement-2.java").write_text("class FromAnotherRun {}")
        problems = build.bundle_problems(out, result)
        self.assertIn("statement.java is not the file the run left (its SHA-256 differs)", problems)
        self.assertIn("statement-2.java is not in the bundle: it comes from another run", problems)
        (out / "result.sarif").unlink()
        self.assertIn("result.sarif is missing", build.bundle_problems(out, result))
        self.assertEqual(build.bundle_problems(out, {"sarif": None}), ["the result lists no bundle"])

    def test_a_file_the_result_names_must_be_in_the_bundle(self):
        out, result = self.bundle({"verifier-output.txt": "✓"}, properties=[{"statement": "statement-1.java"}])
        self.assertEqual(build.bundle_problems(out, result), ["statement-1.java is named by the result but not in its bundle"])
        with self.assertRaises(SystemExit), mock.patch.object(build, "validate"):
            build.check_result(out, result)

    def test_publishing_replaces_every_earlier_evidence_file(self):
        folder = self.tree("example", {"example.json": "{}", "change.patch": "", "README.md": "page",
                                       "result.sarif": "old", "statement-3.java": "old", "verifier-output.txt": "old"})
        made = {**empty_result(), "execution": build.execution_status(0, "✓"), "verdict": "verified", "verdictLabel": "✓ Verified",
                "expectation": "yes", "matchesExpected": True, "sarif": None, "statement": "statement.java"}
        out, result = self.bundle({"verifier-output.txt": "new", "statement.java": "class H {}"}, **made)
        build.publish(folder, out, result)
        self.assertEqual(sorted(f.name for f in folder.iterdir()),
                         ["README.md", "change.patch", "example.json", "result.json", "statement.java", "verifier-output.txt"])
        self.assertEqual((folder / "verifier-output.txt").read_text(), "new")
        self.assertEqual(build.bundle_problems(folder, build.result_format.load(folder / "result.json")), [])

    def test_a_result_is_not_published_without_jsonschema(self):
        with mock.patch.dict(sys.modules, {"jsonschema": None}), self.assertRaises(SystemExit) as stop:
            build.validate({}, "result.schema.json", Path("result.json"))
        self.assertIn("jsonschema is not installed", str(stop.exception))

    def test_main_publishes_nothing_from_a_run_whose_evidence_is_not_its_bundle(self):
        dir = self.dir / "examples"
        shutil.copytree(self.source, dir / self.source.name)
        shutil.copy(build.EXAMPLES / "tags.json", dir / "tags.json")
        folder = dir / self.source.name
        before = {f.name: f.read_bytes() for f in folder.iterdir()}

        def run(f, ex, out):
            result = empty_result()
            build.finish(result, ex)
            left_evidence(result, out)
            (out / "statement.java").write_text("written after the bundle was listed")
            return result

        with mock.patch.object(build, "run", side_effect=run), mock.patch.object(build, "EXAMPLES", dir), \
                mock.patch.object(build, "render_index"), mock.patch.object(build, "validate"), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as stop:
            build.main(["126"])
        self.assertIn("statement.java is not in the bundle", str(stop.exception))
        self.assertEqual({f.name: f.read_bytes() for f in folder.iterdir()}, before)

    def test_main_publishes_the_bundle_and_removes_an_earlier_runs_statements(self):
        dir = self.dir / "examples"
        shutil.copytree(self.source, dir / self.source.name)
        shutil.copy(build.EXAMPLES / "tags.json", dir / "tags.json")
        folder = dir / self.source.name
        (folder / "statement-2.java").write_text("class FromAnEarlierRun {}")
        ran = []

        def run(f, ex, out):
            ran.append(out)
            result = empty_result()
            result["execution"] = build.execution_status(0, "VERIFICATION FAILED")
            result["verdict"] = "violation"
            build.finish(result, ex)
            return left_evidence(result, out, "this run's output\n")

        with mock.patch.object(build, "run", side_effect=run), mock.patch.object(build, "EXAMPLES", dir), \
                mock.patch.object(build, "render_example", return_value="page"), mock.patch.object(build, "render_index"), \
                mock.patch.object(build, "validate"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(build.main(["126"]), 0)
        self.assertNotEqual(ran[0], folder)
        self.assertFalse((folder / "statement-2.java").exists())
        self.assertFalse((folder / "statement.java").exists())  # this run left none
        self.assertFalse((folder / "result.sarif").exists())
        self.assertEqual((folder / "verifier-output.txt").read_text(), "this run's output\n")
        self.assertEqual(build.bundle_problems(folder, build.result_format.load(folder / "result.json")), [])

    def test_a_run_freezes_its_claim_before_the_runner_and_records_the_attempt(self):
        """run() itself, on 126's real patch and Crosscut's real sources, with the tests and the runner mocked."""
        out = self.dir / "attempt"
        out.mkdir()
        seen = {}

        def runner(folder, ex, root, module, result):
            seen["folder"] = folder
            seen["claim"] = json.loads((folder / "claim.json").read_text())
            (root / build.TOOL_APPS["crosscut"]["root"] / "build/main/a").mkdir(parents=True)
            (root / build.TOOL_APPS["crosscut"]["root"] / "build/main/a/B.class").write_bytes(b"\xca\xfe\xba\xbe")
            (folder / "verifier-output.txt").write_text("✓\n")
            (folder / "statement.java").write_text("class EquivalenceHarness {}\n")
            result.update({"execution": build.execution_status(0, "✓"), "verdict": "verified", "verdictLabel": "✓ Verified",
                           "sarif": None, "statement": "statement.java",
                           "proof": "JBMC 6.11.0: 3 properties proved over x: int in 1.0 s; loops unwound 32 times with unwinding assertions",
                           "search": {"engine": "jbmc", "checker": "JBMC 6.11.0", "seconds": 1.0, "properties": 3, "unwind": 32,
                                      "maxArrayLength": 8, "stage": None}})

        env = {"VERIFY_JOB_ID": "job-1", "VERIFY_SOURCE_COMMIT": "abc", "VERIFY_WORKDIR": "/w"}
        with mock.patch.dict(build.RUNNERS["crosscut"], {"B9": runner}), \
                mock.patch.object(build, "tool_tests", return_value={"task": "t", "passed": True, "failures": []}), \
                mock.patch.object(build, "attempt_tools", return_value={"java": "openjdk 25"}), \
                mock.patch.dict(build.os.environ, env):
            result = build.run(self.source, self.example, out)
        self.assertEqual(seen["folder"], out)
        self.assertEqual(seen["claim"], result["claim"])
        self.assertEqual(result["claim"]["statement"]["target"], self.example["subject"]["symbol"])
        self.assertNotEqual(result["claim"]["inputs"]["before"], result["claim"]["inputs"]["after"])
        attempt = result["attempt"]
        self.assertEqual((attempt["claim"], attempt["pipeline"]), (result["claim"]["id"], {"jobId": "job-1", "sourceCommit": "abc", "workdir": "/w"}))
        self.assertEqual(attempt["exploration"], {"unwind": 32, "maxArrayLength": 8, "complete": True})
        self.assertEqual(attempt["bytecode"]["after"]["files"], 1)
        self.assertEqual(attempt["options"], ["--unwind", "32"])
        self.assertEqual(result["conclusion"], {"claim": result["claim"]["id"], "attempt": attempt["id"], "status": "established",
                                                "vacuous": False, "expectation": "no", "obligations": []})
        self.assertEqual([a["path"] for a in result["bundle"]["artifacts"]], ["statement.java", "verifier-output.txt"])
        import jsonschema
        jsonschema.validate(result, json.loads((build.EXAMPLES / "schema/result.schema.json").read_text()))
        self.assertEqual(build.bundle_problems(out, result), [])

    def test_a_conclusion_keeps_each_obligation(self):
        claim, attempt = {"id": "c"}, {"id": "a"}
        b11 = {"verdict": "violation", "expectation": "yes", "coverage": None, "properties": [
            {"harness": "property-1", "assert": "result >= 0", "verdict": "verified"},
            {"harness": "property-2", "assert": "result < 10", "verdict": "violation"},
            {"harness": "property-3", "assert": "result != 3", "verdict": "unverifiable"}]}
        conclusion = build.conclusion_record(claim, attempt, b11)
        self.assertEqual(conclusion["status"], "refuted")
        self.assertEqual([o["status"] for o in conclusion["obligations"]], ["established", "refuted", "unresolved"])
        d1 = {"verdict": None, "expectation": "not-evaluable", "coverage": {"vacuous": False},
              "configurations": [{"label": "the model", "cfg": "M.cfg", "verdict": "verified", "status": "completed"},
                                 {"label": "inductive", "cfg": "I.cfg", "verdict": "unverifiable", "status": "timed-out"}],
              "modelContracts": [{"symbol": "a.B#decide", "connection": "derived", "allowed": False}]}
        conclusion = build.conclusion_record(claim, attempt, d1)
        self.assertIsNone(conclusion["status"])
        self.assertEqual([o["status"] for o in conclusion["obligations"]], ["established", None, "refuted"])

    def test_exploration_is_complete_only_for_a_proof_with_unwinding_assertions(self):
        proved = "JBMC 6.11.0: 3 properties proved over x: int in 1.0 s; loops unwound 16 times with unwinding assertions"
        search = {"unwind": 16, "maxArrayLength": 8}
        self.assertTrue(build.exploration_record({"verdict": "verified", "proof": proved, "search": search})["complete"])
        self.assertIsNone(build.exploration_record({"verdict": "violation", "proof": "found by JBMC", "search": search})["complete"])
        self.assertIsNone(build.exploration_record({"verdict": "unverifiable", "proof": None, "search": None})["complete"])
        several = {"verdict": "verified", "proof": proved, "search": None,
                   "properties": [{"proof": proved, "search": search}, {"proof": "proved somehow", "search": search}]}
        self.assertEqual(build.exploration_record(several), {"unwind": 16, "maxArrayLength": 8, "complete": None})


def typed(name, type_, value=None, from_=None, components=None):
    """A typed witness value as the library writes it."""
    return {"name": name, "type": type_, **({"value": value} if components is None else {"components": components}),
            **({"from": from_} if from_ else {})}


def typed_call(class_internal, method, descriptor, static, classes, arguments, receiver=None):
    """A typed call as the library writes it."""
    return {"class": class_internal.replace("/", "."), "class_file": f"{class_internal}.class", "classes": classes,
            "method": method, "descriptor": descriptor, "static": static,
            **({"receiver": receiver} if receiver else {}), "arguments": arguments}


# 128's shape: a record's method whose previous version was static, called by expressions over the components.
BATCH_WITNESS = {
    "input": "offsetToCommit(this=Batch[start=0, size=1], failedIndex=1), previously offsetToCommit(batchStart=0, batchSize=1, failedIndex=1)",
    "before": "throws IllegalArgumentException", "after": "1", "values": ["0", "1", "1"], "shrink_runs": 0,
    "inputs": [typed("this.start", "long", "0"), typed("this.size", "int", 1), typed("failedIndex", "int", 1)],
    "call": typed_call("a/Batch", "offsetToCommit", "(I)J", False, "after",
                       [typed("failedIndex", "int", 1, "failedIndex")],
                       receiver=typed("this", "a.Batch", components=[typed("start", "long", "0", "this.start"),
                                                                     typed("size", "int", 1, "this.size")])),
    "previous_call": typed_call("a/BatchCommit", "offsetToCommit", "(JII)J", True, "before",
                                [typed("batchStart", "long", "0", "this.start"), typed("batchSize", "int", 1, "this.size"),
                                 typed("failedIndex", "int", 1, "failedIndex")]),
}


class WitnessTest(RunnerCase):
    """A counterexample keeps its witness as data: typed inputs, the calls of both versions with their descriptors
    and argument mappings, and the class files' identities as built."""

    def classes(self):
        """The class files the run built: the patched one, and the previous version's."""
        after = self.build / "build/main/a/Batch.class"
        before = self.dir / "before/a/BatchCommit.class"
        for f, content in ((after, b"\xca\xfe\xba\xbe after"), (before, b"\xca\xfe\xba\xbe before")):
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(content)
        return after, before

    def test_a_regression_witness_keeps_both_calls_typed_with_their_class_files(self):
        after, before = self.classes()
        out = equivalence_json(self.root, counterexample=BATCH_WITNESS)
        result = self.run_runner(build.run_tool_equivalence, proc(1, out), example(), report="equivalence.sarif")
        self.assertEqual(result["verdict"], "violation")
        [c] = result["counterexamples"]
        self.assertEqual(c["input"], BATCH_WITNESS["input"])  # the text stays as it was
        w = c["witness"]
        self.assertEqual([i["name"] for i in w["inputs"]], ["this.start", "this.size", "failedIndex"])
        self.assertEqual(w["inputs"][0], {"name": "this.start", "type": "long", "value": "0"})
        self.assertEqual((w["call"]["class"], w["call"]["classFile"], w["call"]["descriptor"], w["call"]["static"]),
                         ("a.Batch", "a/Batch.class", "(I)J", False))
        self.assertEqual(w["call"]["classFileSha256"], build.file_digest(after))
        self.assertEqual([x["from"] for x in w["call"]["receiver"]["components"]], ["this.start", "this.size"])
        previous = w["previousCall"]
        self.assertEqual((previous["classes"], previous["descriptor"], previous["static"]), ("before", "(JII)J", True))
        self.assertEqual(previous["classFileSha256"], build.file_digest(before))
        self.assertEqual([(a["name"], a["from"]) for a in previous["arguments"]],
                         [("batchStart", "this.start"), ("batchSize", "this.size"), ("failedIndex", "failedIndex")])
        self.assertNotIn("foundInputs", w)

    def test_a_class_file_the_run_did_not_build_has_no_digest(self):
        out = equivalence_json(self.root, counterexample=BATCH_WITNESS)
        result = self.run_runner(build.run_tool_equivalence, proc(1, out), example(), report="equivalence.sarif")
        w = result["counterexamples"][0]["witness"]
        self.assertEqual((w["call"]["classFileSha256"], w["previousCall"]["classFileSha256"]), (None, None))

    def test_shrunk_inputs_keep_the_found_ones_and_an_untyped_tool_gives_no_witness(self):
        shrunk = {**BATCH_WITNESS, "found": "offsetToCommit(...)", "found_inputs": [typed("this.start", "long", "9007199254740993")]}
        result = self.run_runner(build.run_tool_equivalence, proc(1, equivalence_json(self.root, counterexample=shrunk)),
                                 example(), report="equivalence.sarif")
        self.assertEqual(result["counterexamples"][0]["witness"]["foundInputs"][0]["value"], "9007199254740993")
        # A tool from before typed witnesses: the counterexample as it was, with no witness made up.
        result = self.run_runner(build.run_tool_equivalence, proc(1, equivalence_json(self.root)), example(), report="equivalence.sarif")
        self.assertNotIn("witness", result["counterexamples"][0])

    def test_a_property_witness_keeps_its_call(self):
        c = {"input": "m(x=-1)", "outcome": "-1", "values": ["-1"], "shrink_runs": 0,
             "inputs": [typed("x", "int", -1)], "call": typed_call("a/B", "m", "(I)I", True, "after", [typed("x", "int", -1, "x")])}
        out = property_outcome(self.root, counterexample=c)
        result = self.run_runner(build.run_tool_property, proc(1, property_json(out)), example(approach="B11"), report="property.sarif")
        w = result["properties"][0]["counterexample"]["witness"]
        self.assertEqual((w["call"]["descriptor"], w["call"]["classes"], w["inputs"]), ("(I)I", "after", [typed("x", "int", -1)]))
        self.assertNotIn("previousCall", w)
        self.assertEqual(result["counterexamples"][0]["witness"], w)

    def test_witnesses_validate_against_the_schema(self):
        import jsonschema
        self.classes()
        schema = json.loads((build.EXAMPLES / "schema/result.schema.json").read_text())
        source = next(build.EXAMPLES.glob("128-*"))
        recorded = json.loads((source / "result.json").read_text())
        out = equivalence_json(self.root, counterexample={**BATCH_WITNESS, "found_inputs": BATCH_WITNESS["inputs"]})
        result = self.run_runner(build.run_tool_equivalence, proc(1, out), example(), report="equivalence.sarif")
        recorded["counterexamples"] = result["counterexamples"]
        jsonschema.validate(recorded, schema)
        bad = json.loads(json.dumps(recorded))
        bad["counterexamples"][0]["witness"]["call"]["classes"] = "patched"
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)
        bad = json.loads(json.dumps(recorded))
        del bad["counterexamples"][0]["witness"]["call"]["descriptor"]
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, schema)


class SnapshotTest(unittest.TestCase):
    """Step 3c: a page renders the result as recorded and says whether it is still the current files' result: a stale
    one is shown as stale, and an explanation is not printed as the reason for a result it does not explain."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="build-test-"))
        self.addCleanup(shutil.rmtree, self.dir)
        self.addCleanup(build.SOURCES.clear)
        source = next(build.EXAMPLES.glob("126-*"))
        self.examples = self.dir / "examples"
        self.folder = self.examples / source.name
        shutil.copytree(source, self.folder)
        for name in ("tags.json", "README.md"):
            shutil.copy(build.EXAMPLES / name, self.examples / name)
        shutil.copytree(build.EXAMPLES / "schema", self.examples / "schema")
        self.example = json.loads((self.folder / "example.json").read_text())
        self.result = self.fingerprinted(self.example)

    def fingerprinted(self, ex, before=None):
        """The recorded result with a claim frozen over the repository's current files (or `before`), and the bundle
        of the evidence beside it."""
        result = json.loads((self.folder / "result.json").read_text())
        patch = (self.folder / "change.patch").read_text()
        result["claim"] = build.claim_record(ex, build.plan(ex), patch, before or build.REPO, before or build.REPO)
        result["attempt"] = {"id": "20261105T000000Z-0a1b2c3d", "pipeline": {"jobId": "20261105-000000-example-126"}}
        result["bundle"] = build.bundle_record(self.folder)
        return result

    def test_a_result_of_the_current_files_is_current(self):
        snap = build.snapshot(self.folder, self.example, self.result)
        self.assertEqual(snap, {"state": "current", "reasons": [], "evidence": []})
        page = build.render_example(self.folder, self.example, self.result)
        self.assertNotIn("Stale result", page)
        self.assertIn("This page renders attempt `20261105T000000Z-0a1b2c3d` at claim "
                      f"`{self.result['claim']['id']}`, in pipeline job `20261105-000000-example-126`. Its claim is still", page)
        self.assertIn("The files below are the run's bundle.", page)

    def test_a_changed_patch_makes_the_result_stale(self):
        (self.folder / "change.patch").write_text((self.folder / "change.patch").read_text() + "\n")
        snap = build.snapshot(self.folder, self.example, self.result)
        self.assertEqual((snap["state"], snap["reasons"]), ("stale", ["the patch changed"]))
        page = build.render_example(self.folder, self.example, self.result, snap)
        self.assertIn("> ⚠ **Stale result:** the patch changed since this run. The verdict on this page is that run's", page)
        self.assertLess(page.index("Stale result"), page.index("## The change"))
        self.assertIn("which is stale: the patch changed.", page)

    def test_a_changed_scope_or_statement_makes_the_result_stale(self):
        bound = {**self.example, "approach": {**self.example["approach"], "maxArrayLength": 12}}
        self.assertEqual(build.claim_changes(self.folder, bound, self.result["claim"]), ["the scope changed (`maxArrayLength`)"])
        scoped = {**self.example, "change": {**self.example["change"], "intendedInputs": "attempt < 0"}}
        self.assertEqual(build.claim_changes(self.folder, scoped, self.result["claim"]),
                         ["what is checked changed (`intendedInputs`)", "the scope changed (`intendedInputs`)"])
        native = {**self.example, "approach": {**self.example["approach"], "engine": "native"}}
        self.assertEqual(build.claim_changes(self.folder, native, self.result["claim"]), [])  # another attempt, same claim
        old = {**self.result["claim"], "format": 0}
        self.assertIn("the claim is in format 0", build.claim_changes(self.folder, self.example, old)[0])

    def test_changed_sources_make_the_result_stale(self):
        part = build.plan(self.example)["build"]["copies"][0]
        before = self.dir / "before"
        (before / part / "src").mkdir(parents=True)
        (before / part / "src/A.java").write_text("class A {}")
        claim = self.fingerprinted(self.example, before)["claim"]
        self.assertEqual(build.claim_changes(self.folder, self.example, claim, base=before), [])
        (before / part / "src/A.java").write_text("class A { int x; }")
        self.assertEqual(build.claim_changes(self.folder, self.example, claim, base=before),
                         [f"the sources the patch applies to changed (`{part}`)"])
        (before / part / "build").mkdir()
        (before / part / "build/A.class").write_text("built")
        (before / part / "src/A.java").write_text("class A {}")
        self.assertEqual(build.claim_changes(self.folder, self.example, claim, base=before), [])  # build output is not a source

    def test_evidence_that_is_not_the_bundle_is_shown(self):
        (self.folder / "verifier-output.txt").write_text("another run's output\n")
        snap = build.snapshot(self.folder, self.example, self.result)
        self.assertEqual(snap["state"], "current")
        self.assertEqual(snap["evidence"], ["verifier-output.txt is not the file the run left (its SHA-256 differs)"])
        page = build.render_example(self.folder, self.example, self.result, snap)
        self.assertIn("> ⚠ **The evidence is not the run's:** verifier-output.txt is not the file the run left", page)
        self.assertIn("The files below are not all the run's bundle.", page)

    def test_a_result_recorded_before_claims_is_unknown(self):
        old = json.loads((self.folder / "result.json").read_text())
        self.assertEqual(build.snapshot(self.folder, self.example, old), {"state": "unknown", "reasons": [], "evidence": []})
        page = build.render_example(self.folder, self.example, old)
        self.assertIn("recorded before runs fingerprinted their inputs, so whether it still matches", page)
        self.assertNotIn("⚠", page.split("## The change")[0])

    def test_render_only_shows_a_stale_fixture_as_stale(self):
        (self.folder / "result.json").write_text(json.dumps(self.result))
        (self.folder / "change.patch").write_text((self.folder / "change.patch").read_text() + "\n")
        with mock.patch.object(build, "EXAMPLES", self.examples), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(build.main(["--render-only", "126"]), 0)
        self.assertIn(f"{self.folder.name}: stale (the patch changed)", out.getvalue())
        self.assertIn("⚠ **Stale result:** the patch changed", (self.folder / "README.md").read_text())
        row = next(line for line in (self.examples / "README.md").read_text().splitlines() if line.startswith("| 126 |"))
        self.assertIn("(⚠ stale)", row)
        entry = next(e for e in json.loads((self.examples / "index.json").read_text())["examples"] if e["id"] == "126")
        self.assertEqual(entry["snapshot"], "stale")
        self.assertEqual(json.loads((self.folder / "result.json").read_text()), self.result)  # rendering rewrites no result

    def test_the_authors_explanation_is_the_reason_only_for_the_expected_result(self):
        page = build.render_example(self.folder, self.example, self.result)
        self.assertIn("## Why the verdict is right\n\n" + self.example["explanation"], page)
        missed = {**self.result, "verdict": "verified", "verdictLabel": "✓ Verified", "expectation": "no", "matchesExpected": False}
        page = build.render_example(self.folder, self.example, missed)
        self.assertNotIn("## Why the verdict is right", page)
        self.assertIn("## What the example expected\n\nThe example expects **✗ Violation**, and the run's result is "
                      "**✓ Verified**. The author's explanation below is of the expected result, so it is not a reason", page)
        self.assertIn("> " + self.example["explanation"].split("\n")[0], page)
        none = {**missed, "verdict": None, "verdictLabel": "⚠ No verdict", "expectation": "not-evaluable",
                "execution": {"status": "killed", "exitCode": -9, "reason": "killed by signal 9"}}
        self.assertIn("and the run has no verdict.", build.render_example(self.folder, self.example, none))
        old = {k: v for k, v in missed.items() if k != "expectation"}  # recorded before `expectation`
        self.assertIn("## What the example expected", build.render_example(self.folder, self.example, old))


class StagesTest(unittest.TestCase):
    """Step 3d: every command of a run is a stage whose output streams into the attempt's logs as it runs, and a run
    in a pipeline job keeps its workspace, so an interrupted job leaves its stage logs and workspace behind."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="build-test-"))
        self.addCleanup(shutil.rmtree, self.dir)
        self.source = next(build.EXAMPLES.glob("126-*"))
        self.example = json.loads((self.source / "example.json").read_text())
        self.addCleanup(build._SCRATCH.clear)

    def python(self, code):
        return [sys.executable, "-c", code]

    def records(self, out):
        return [json.loads(line) for line in (out / "logs/stages.jsonl").read_text().splitlines()]

    def test_a_stage_streams_its_output_into_the_attempts_logs(self):
        out = self.dir / "attempt"
        with contextlib.redirect_stdout(io.StringIO()) as printed, build.stages(out) as ran:
            proc = build.stage("say hello", self.python("import sys; print('out'); print('err', file=sys.stderr)"))
            failed = build.stage("fail", self.python("raise SystemExit(3)"))
            with self.assertRaises(subprocess.CalledProcessError):
                build.stage("fail and check", self.python("raise SystemExit(4)"), check=True)
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "out\n", "err\n"))
        self.assertEqual(failed.returncode, 3)
        self.assertEqual((out / "logs/01-say-hello.stdout").read_text(), "out\n")
        self.assertEqual((out / "logs/01-say-hello.stderr").read_text(), "err\n")
        self.assertEqual([(r["name"], r["status"], r["exitCode"]) for r in ran],
                         [("say hello", "exited", 0), ("fail", "exited", 3), ("fail and check", "exited", 4)])
        self.assertEqual([r["status"] for r in self.records(out)], ["running", "exited"] * 3)  # a line as it starts, one as it ends
        self.assertIn("  · say hello\n  · say hello: exited 0,", printed.getvalue())
        self.assertNotIn(str(self.dir), printed.getvalue())  # progress lines name stages, not paths
        self.assertIsNone(build._STAGES["dir"])

    def test_a_stage_that_times_out_leaves_what_it_wrote(self):
        out = self.dir / "attempt"
        with contextlib.redirect_stdout(io.StringIO()), build.stages(out) as ran:
            with self.assertRaises(subprocess.TimeoutExpired) as stop:
                build.stage("slow", self.python("import time; print('started', flush=True); time.sleep(30)"), timeout=1)
        self.assertEqual(stop.exception.stdout, "started\n")
        self.assertEqual((out / "logs/01-slow.stdout").read_text(), "started\n")
        self.assertEqual((ran[0]["status"], ran[0]["exitCode"]), ("timed-out", None))

    def test_a_signal_is_a_killed_stage(self):
        out = self.dir / "attempt"
        with contextlib.redirect_stdout(io.StringIO()), build.stages(out) as ran:
            proc = build.stage("killed", self.python("import os, signal; os.kill(os.getpid(), signal.SIGKILL)"))
        self.assertEqual((proc.returncode, ran[0]["status"]), (-9, "killed"))

    def test_outside_an_attempt_the_output_is_captured_as_before(self):
        proc = build.stage("anything", self.python("print('x')"))
        self.assertEqual(proc.stdout, "x\n")
        self.assertEqual(list(self.dir.iterdir()), [])

    def run_126(self, runner, workdir=None):
        """run() on 126's real patch and Crosscut's real sources in an attempt directory of the scratch directory
        (under the kept workspace when `workdir` is the pipeline's), with the tests and tools mocked."""
        env = {"VERIFY_WORKDIR": str(workdir)} if workdir else {}
        with mock.patch.dict(build.RUNNERS["crosscut"], {"B9": runner}), \
                mock.patch.object(build, "tool_tests", return_value={"task": "t", "passed": True, "failures": []}), \
                mock.patch.object(build, "attempt_tools", return_value={"java": "openjdk 25"}), \
                mock.patch.dict(build.os.environ, env, clear=False), mock.patch.object(build, "_SCRATCH", []), \
                contextlib.redirect_stdout(io.StringIO()):
            if not workdir:
                build.os.environ.pop("VERIFY_WORKDIR", None)
            out = build.attempt_directory(self.source)
            self.addCleanup(shutil.rmtree, build.scratch(), True)
            return out, build.run(self.source, self.example, out)

    def test_an_interrupted_job_leaves_its_stage_logs_and_workspace_behind(self):
        # The work directory is a repository, as a job's could be: the patch still applies to the copy inside it.
        work = self.dir / "work"
        work.mkdir()
        subprocess.run(["git", "init", "-q", str(work)], check=True)
        def runner(folder, ex, root, module, result):
            build.stage("the verifier", self.python("print('half a proof', flush=True)"))
            raise KeyboardInterrupt  # the job is stopped here, as by its timeout
        with self.assertRaises(KeyboardInterrupt):
            self.run_126(runner, work)
        self.addCleanup(build._STAGES.update, {"dir": None})
        attempt = next((work / ".build-py").glob("examples-*/attempts/126/attempt-*"))
        self.assertTrue((attempt / "claim.json").exists())
        patched = attempt / "copy" / self.example["subject"]["file"]
        self.assertNotEqual(patched.read_text(), (build.REPO / self.example["subject"]["file"]).read_text())  # patched
        records = self.records(attempt)
        self.assertEqual([(r["name"], r["status"]) for r in records],
                         [("apply the patch", "running"), ("apply the patch", "exited"),
                          ("the verifier", "running"), ("the verifier", "exited")])
        self.assertEqual((attempt / "logs/02-the-verifier.stdout").read_text(), "half a proof\n")

    def test_a_pipeline_attempt_records_its_stages_and_workspace(self):
        work = self.dir / "work"
        work.mkdir()
        def runner(folder, ex, root, module, result):
            build.stage("the verifier", self.python("print('✓')"))
            (folder / "verifier-output.txt").write_text("✓\n")
            result.update({"execution": build.execution_status(0, "✓"), "verdict": "verified", "sarif": None})
        out, result = self.run_126(runner, work)
        attempt = result["attempt"]
        self.assertEqual(attempt["workspace"], out.relative_to(work).as_posix())
        self.assertTrue(attempt["workspace"].startswith(".build-py/examples-"))
        self.assertEqual([s["name"] for s in attempt["stages"]], ["apply the patch", "the verifier"])
        self.assertEqual(attempt["stages"][1]["stdout"], "logs/02-the-verifier.stdout")
        self.assertTrue((out / "copy").is_dir())
        self.assertEqual([a["path"] for a in result["bundle"]["artifacts"]], ["verifier-output.txt"])  # logs are not evidence

    def test_outside_the_pipeline_the_copy_goes_when_the_run_ends(self):
        def runner(folder, ex, root, module, result):
            (folder / "verifier-output.txt").write_text("✓\n")
            result.update({"execution": build.execution_status(0, "✓"), "verdict": "verified", "sarif": None})
        out, result = self.run_126(runner)
        self.assertIsNone(result["attempt"]["workspace"])
        self.assertFalse((out / "copy").exists())
        self.assertTrue((out / "logs/01-apply-the-patch.stdout").exists())

    def test_the_unpatched_baseline_compiles_no_tests(self):
        names = []
        with mock.patch.object(build, "javac", side_effect=lambda out, sources, classpath=None, name="": names.append(name)), \
                mock.patch.object(build, "scratch", return_value=self.dir), mock.patch.dict(build.BEFORE_CLASSES, clear=True):
            build.tool_before_classes("crosscut")
            build.tool_compile("crosscut", self.dir / "before-crosscut")
        self.assertEqual(names, ["javac unpatched crosscut main", "javac patched crosscut main", "javac patched crosscut tests"])


class StoredFormatTest(unittest.TestCase):
    """Option B of the brief's open question 1: result.json stores format 2, each fact once, and everything reads it
    through the flat view, so no page or check changes; format 1 results read as they are."""

    def complete(self, folder):
        """A committed result (format 1) as a run would end it now: with the blocks run() adds, and the execution and
        expectation a result recorded before them did not have."""
        r = json.loads((folder / "result.json").read_text())
        if r.get("execution") is None:
            r["execution"] = {"status": "completed", "exitCode": 1 if r["verdict"] == "violation" else 0, "reason": "made up"}
        r.setdefault("expectation", "yes" if r["matchesExpected"] else "no")
        return with_blocks(r, folder)

    def test_every_committed_results_shape_stores_whole(self):
        folders = sorted(f for f in build.EXAMPLES.glob("[0-9][0-9][0-9]-*") if (f / "result.json").exists())
        self.assertGreater(len(folders), 100)
        for folder in folders:
            with self.subTest(folder.name):
                r = self.complete(folder)
                self.assertEqual(build.result_format.round_trip_problems(r), [])
                build.validate(build.result_format.pack(r), "stored-result.schema.json", folder)

    def test_format_two_stores_each_fact_once(self):
        folder = next(build.EXAMPLES.glob("072-*"))  # D1: configurations, coverage, a vacuous verdict
        r = self.complete(folder)
        doc = build.result_format.pack(r)
        self.assertEqual(list(doc), ["format", "claim", "attempt", "conclusion", "evidence", "bundle"])
        for derived in ("verdict", "verdictLabel", "execution", "expectation", "matchesExpected", "configurations"):
            self.assertNotIn(derived, doc["evidence"])
        self.assertEqual(doc["conclusion"]["obligationKeys"], {"configuration": "configurations"})
        self.assertEqual([o["evidence"] for o in doc["conclusion"]["obligations"]], r["configurations"])
        self.assertEqual((doc["conclusion"]["status"], doc["conclusion"]["label"]), ("established", r["verdictLabel"]))
        self.assertEqual(build.result_format.view(doc), r)

    def test_a_null_or_empty_obligation_list_reads_back_as_it_was(self):
        out = Path(tempfile.mkdtemp(prefix="build-test-"))
        self.addCleanup(shutil.rmtree, out)
        for value in (None, []):
            r = with_blocks({**empty_result(), "execution": {"status": "killed", "exitCode": -9, "reason": "signal 9"},
                             "verdictLabel": "⚠ No verdict", "expectation": "not-evaluable", "matchesExpected": False,
                             "properties": value}, out)
            self.assertEqual(build.result_format.round_trip_problems(r), [])
        r = with_blocks({**empty_result(), "execution": {"status": "killed", "exitCode": -9, "reason": "signal 9"},
                         "verdictLabel": "⚠ No verdict", "expectation": "not-evaluable", "matchesExpected": False}, out)
        self.assertNotIn("properties", build.result_format.view(build.result_format.pack(r)))

    def test_a_result_that_would_not_store_whole_is_refused(self):
        r = self.complete(next(build.EXAMPLES.glob("126-*")))
        self.assertEqual(build.result_format.round_trip_problems({**r, "verdict": "verified"}),
                         ["the result's verdict and its conclusion disagree"])
        self.assertIn("without claim", build.result_format.round_trip_problems({**r, "claim": None})[0])
        self.assertEqual(build.result_format.round_trip_problems({**r, "matchesExpected": not r["matchesExpected"]}),
                         [f"`matchesExpected` would be stored as {json.dumps(r['matchesExpected'])} for {json.dumps(not r['matchesExpected'])}"])

    def test_format_one_reads_as_it_is_and_an_unknown_format_is_refused(self):
        folder = next(build.EXAMPLES.glob("126-*"))
        self.assertEqual(build.result_format.load(folder / "result.json"), json.loads((folder / "result.json").read_text()))
        with self.assertRaises(ValueError) as stop:
            build.result_format.view({"format": 99})
        self.assertIn("result format 99 is not one build.py reads (it reads 1, 2)", str(stop.exception))

    def test_a_published_result_is_format_two_and_its_page_is_the_same(self):
        source = next(build.EXAMPLES.glob("126-*"))
        dir = Path(tempfile.mkdtemp(prefix="build-test-"))
        self.addCleanup(shutil.rmtree, dir)
        folder = dir / source.name
        shutil.copytree(source, folder)
        ex = json.loads((folder / "example.json").read_text())
        r = self.complete(folder)
        page = build.render_example(folder, ex, r, {"state": "current", "reasons": [], "evidence": []})
        build.publish(folder, folder, r)
        stored = json.loads((folder / "result.json").read_text())
        self.assertEqual(stored["format"], 2)
        self.assertEqual(build.render_example(folder, ex, build.result_format.load(folder / "result.json"),
                                              {"state": "current", "reasons": [], "evidence": []}), page)


class GapScanTest(unittest.TestCase):
    """Step 1a of llm-dlc/loops/sound-verdicts.md: the gap scan's note says what strict mode would cost an example,
    and replaces an earlier note rather than adding another."""

    def scan(self, gaps=(), refused=None, methods=3):
        return {"roots": ["a.B#m"], "methods": methods, "jdk": "25.0.4.1", "gaps": list(gaps), "exact": {},
                "refused": refused or {}}

    def example(self, approach="B9", engine=None):
        return {"id": "200", "origin": "constructed", "subject": {"file": "examples/apps/crosscut/src/main/java/a/B.java"},
                "approach": {"id": approach, **({"engine": engine} if engine else {})}}

    def test_which_examples_are_scanned(self):
        self.assertIsNone(build.gap_scan_problem(self.example()))
        self.assertIsNone(build.gap_scan_problem(self.example("B11")))
        self.assertIn("not a proof over bytecode", build.gap_scan_problem(self.example("D1")))
        boxoffice = {**self.example(), "subject": {"file": build.BUILD_ROOT + "/x/A.java"}}
        self.assertIn("Gradle", build.gap_scan_problem(boxoffice))
        self.assertIn("real-world", build.gap_scan_problem({**self.example(), "origin": "real-world"}))

    def test_no_gap_means_the_verdict_does_not_move(self):
        note = build.gap_note(self.example(engine="native"), {"after": self.scan(), "before": self.scan()},
                              today=build.datetime.date(2026, 11, 5))
        self.assertTrue(note.startswith("Gap scan (step 1a of `llm-dlc/loops/sound-verdicts.md`, 5 November 2026, "
                                        "JDK 25.0.4.1"), note)
        self.assertIn("meets no gap in the 3 methods the proof reaches in either version, so strict mode does not "
                      "move this verdict.", note)
        self.assertNotIn("JBMC", note)

    def test_gaps_are_named_by_id_with_the_versions_that_meet_them(self):
        gap = {"id": "monitor:a.B", "kind": "monitor", "call": "a.B", "sites": ["a.B.m:7", "a.B.m:9"]}
        other = {"id": "jdk-constructor:java.util.ArrayList.<init>(I)V@jdk-25.0.4.1", "kind": "jdk-constructor",
                 "call": "java.util.ArrayList.<init>(int)", "sites": ["a.B.m:3"]}
        refused = {"floating point": {"first": "floating-point arithmetic", "at": "a.B.m:4", "sites": 3}}
        scans = {"after": self.scan([gap, other], refused), "before": self.scan([gap])}
        gaps, why = build.gap_summary(scans)
        self.assertEqual([(g["id"], g["versions"]) for g in gaps],
                         [("monitor:a.B", ["after", "before"]), (other["id"], ["after"])])
        self.assertEqual(why, ["floating point (floating-point arithmetic, and 2 more)"])
        note = build.gap_note(self.example(), scans)
        self.assertIn("meets 2 gaps in what the proof reaches: `monitor:a.B` (both versions, first at a.B.m:7); "
                      f"`{other['id']}` (the after version only, first at a.B.m:3). Under strict mode each is "
                      "refused by name", note)
        self.assertIn("runs in `assume` until the user decides", note)
        self.assertIn("The recorded proof is JBMC's", note)
        self.assertIn("refuses part of it in any mode (floating point (floating-point arithmetic, and 2 more))", note)

    def test_the_note_replaces_an_earlier_one(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / "example.json").write_text(json.dumps({"id": "200", "notes": ["kept", "Gap scan (old)"]}))
            build.record_gap_note(folder, "Gap scan (new)")
            build.record_gap_note(folder, "Gap scan (newer)")
            self.assertEqual(json.loads((folder / "example.json").read_text())["notes"], ["kept", "Gap scan (newer)"])


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

    def test_the_search_and_replay_records_validate(self):
        import jsonschema
        schema = json.loads((build.EXAMPLES / "schema/result.schema.json").read_text())
        source = next(build.EXAMPLES.glob("126-*"))
        result = json.loads((source / "result.json").read_text())
        result["search"] = {"engine": "native", "checker": "jvmcontract's own checker (CaDiCaL)", "seconds": 0.5, "properties": 1,
                            "unwind": 32, "maxArrayLength": 8, "stage": None, "sharedCallees": ["a.C.f"], "native": {"paths": 3, "solverCalls": 4}}
        result["replay"] = {"by": "interpreter", "reproduced": True}
        result["counterexamples"][0].update({"found": "m(x=17)", "shrinkRuns": 120})
        jsonschema.validate(result, schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({**result, "replay": {"by": "the JVM", "reproduced": True}}, schema)


if __name__ == "__main__":
    unittest.main()

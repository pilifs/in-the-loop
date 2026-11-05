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
        return result


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


class ModelContractTest(unittest.TestCase):
    """D1 always connects the model's generated operators to the patched bytecode. A kernel the patch changed is checked
    as it was built, whether or not the change was meant to alter behaviour; the flag decides only whether the
    difference is allowed. The review's gap: a change not meant to alter behaviour, whose kernel changed anyway, used to
    be checked against the committed contract and could pass."""

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
        self.patch = mock.patch.object(build, "jvmcontract", return_value="jvmcontract")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        shutil.rmtree(self.dir)

    def run_tlc(self, candidate, intended=False, tlc=None, derive=0):
        """run_tool_tlc with the tool mocked: `derive` prints the candidate contract, `update` writes it, TLC answers
        `tlc` (verified, by default). Records the contract each `tla` call saw and every command."""
        self.calls, self.generated_from = [], []
        contract = self.build / "src/contract/CircuitBreaker.decide.contract"
        contract.write_text(self.committed)  # each run starts from the committed contract, as a fresh copy does
        tlc = tlc or json.dumps({"verdict": "verified", "output": "Model checking completed. No error has been found.",
                                 "trace": [], "version": "TLC 2.19", "distinct_states": 102, "depth": 9, "seconds": 1,
                                 "coverage": [{"symbol": BREAKER_SYMBOL, "rows": [
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
                return proc(0, tlc)
            return proc(0, "stateDiagram-v2\n")
        ex = example("D1", BREAKER_SYMBOL)
        ex["change"]["behaviourChangeIntended"] = intended
        result = empty_result()
        result["contractDiff"] = None
        with mock.patch.object(build.subprocess, "run", side_effect=fake):
            build.run_tool_tlc(self.folder, ex, self.root, "crosscut", result)
        build.finish(result, ex)
        return result

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
        def run(folder, ex):
            self.ran.append(folder.name[:3])
            result = empty_result()
            result["execution"] = build.execution_status(0, "VERIFICATION FAILED")
            result["verdict"] = ex["expected"]["verdict"]
            build.finish(result, ex)
            return result

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

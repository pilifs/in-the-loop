"""Tests of the benchmark's runner and corpus: python3 -m unittest lib/benchmark/test_run.py (from the repo root), or
python3 -m unittest test_run in lib/benchmark. The corpus test runs Reference.java's `list` on a JVM when there is one;
nothing here runs a proof."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run  # noqa: E402

HERE = Path(__file__).resolve().parent


def measured(**kw):
    base = {"exit": 0, "killed": False, "stdout": "", "stderr": "", "seconds": 0.1, "cpuSeconds": 0.1, "peakMB": 20.0}
    base.update(kw)
    return base


class ClassifyTest(unittest.TestCase):
    case_v = {"id": "x", "expected": "verified"}
    case_x = {"id": "y", "expected": "violation"}

    def test_a_verdict_is_held_to_the_expected_answer(self):
        self.assertEqual(run.classify(self.case_v, {"verdict": "verified"}, measured())["class"], "correct")
        self.assertEqual(run.classify(self.case_x, {"verdict": "violation"}, measured())["class"], "correct")
        self.assertEqual(run.classify(self.case_x, {"verdict": "verified"}, measured())["class"], "false-success")
        self.assertEqual(run.classify(self.case_v, {"verdict": "violation"}, measured())["class"], "false-alarm")

    def test_a_verified_that_assumed_a_gap_says_so_whichever_way_it_falls(self):
        data = {"verdict": "verified", "search": {"gaps": [{"id": "jdk-constructor:A", "treatment": "assumed"}, {"id": "B", "treatment": "contract"}]}}
        right = run.classify(self.case_v, data, measured())
        self.assertEqual((right["class"], right["assumed"], right["contracts"]), ("correct-assuming", ["jdk-constructor:A"], ["B"]))
        self.assertEqual(run.classify(self.case_x, data, measured())["class"], "false-success-assuming")

    def test_no_verdict_is_unsupported_with_the_reason(self):
        cases = [
            ({"verdict": "unverifiable", "advice": {"gaps": []}}, measured(), "needs contracts"),
            ({"verdict": "unverifiable", "problem": "the solver did not finish within the time limit"}, measured(), "out of time"),
            ({"verdict": "unverifiable", "search": {"runs": [{"ending": "timeout"}]}}, measured(), "out of time"),
            ({"verdict": "unverifiable", "search": {"runs": [{"ending": "memory-exhausted"}]}}, measured(), "out of memory"),
            ({"verdict": "unverifiable", "search": {"gaps": [{"id": "g", "treatment": "refused"}]}}, measured(), "gap"),
            ({"verdict": "unverifiable", "problem": "the engines disagree"}, measured(), "engines disagree"),
            ({"verdict": "unverifiable", "problem": "invokedynamic is outside the fragment"}, measured(), "refused"),
            (None, measured(killed=True), "out of time"),
            (None, measured(stderr="panicked"), "no output"),
        ]
        for data, m, reason in cases:
            record = run.classify(self.case_x, data, m)
            self.assertEqual((record["class"], record["reason"]), ("unsupported", reason), data)


class CommandTest(unittest.TestCase):
    class Options:
        timeout = 120
        jvmcontract = "jvmcontract"
        jbmc = "jbmc"

    classes = {"broken": Path("/b/broken"), "fixed": Path("/b/fixed"), "conformance": Path("/b/conformance")}

    def test_both_engines_get_the_same_statement_bounds_and_deadline(self):
        case = {"kind": "regression", "before": "broken", "after": "fixed", "target": "p.C#m", "unchangedUnless": "x < 0"}
        native = run.command(case, "native", "strict", self.classes, Path("/w"), self.Options)
        jbmc = run.command(case, "jbmc", "strict", self.classes, Path("/w"), self.Options)
        engine = native.index("--engine") + 1
        self.assertEqual((native[engine], jbmc[engine]), ("native", "jbmc"))
        self.assertEqual(native[:engine] + native[engine + 1:], jbmc[:engine] + jbmc[engine + 1:])
        for flag, value in (("--timeout", "120"), ("--unwind", "16"), ("--max-array-length", "8"), ("--unchanged-unless", "x < 0"), ("--before", "/b/broken")):
            self.assertEqual(native[native.index(flag) + 1], value)

    def test_advised_runs_the_protocol_on_the_library_with_no_trusted_contract(self):
        case = {"kind": "property", "target": "conformance.Conformance#m", "assert": "result", "throws": ["E when x"], "assume": None}
        cmd = run.command(case, "jbmc", "advised", self.classes, Path("/w"), self.Options)
        self.assertEqual(cmd[1:4], ["prove", "--classes", "/b/conformance"])
        self.assertIn("--max-trust", cmd)
        self.assertNotIn("--assume", cmd)
        self.assertEqual(cmd[cmd.index("--throws") + 1], "E when x")


class WitnessTest(unittest.TestCase):
    def test_a_witness_is_flattened_as_the_jvm_runners_read_arguments(self):
        data = {"counterexample": {"inputs": [{"value": [1, -2]}, {"value": True}, {"value": "a"}, {"value": None}, {"value": -7}]}}
        self.assertEqual(run.witness_arguments(data), "[1,-2];true;97;null;-7")
        self.assertIsNone(run.witness_arguments({"counterexample": None}))


class MeasureTest(unittest.TestCase):
    def test_peak_memory_counts_the_processes_a_run_waits_for(self):
        child = "import subprocess, sys; subprocess.run([sys.executable, '-c', 'x = bytearray(64 * 1024 * 1024)\\nfor i in range(0, len(x), 4096): x[i] = 1'])"
        m = run.measure([sys.executable, "-c", child], 60)
        self.assertEqual(m["exit"], 0)
        self.assertGreater(m["peakMB"], 64)

    def test_a_run_past_its_limit_is_killed(self):
        m = run.measure([sys.executable, "-c", "import time; time.sleep(30)"], 0.3)
        self.assertTrue(m["killed"])
        self.assertLess(m["seconds"], 10)


def results():
    cases = [{"id": "conformance/a/1", "group": 1, "workload": "semantics", "kind": "property", "expected": "violation"},
             {"id": "real/b", "group": 2, "workload": "div-rem", "kind": "property", "expected": "verified"}]
    def r(case, engine, mode, verdict, cls, seconds, **kw):
        return {"case": case, "engine": engine, "mode": mode, "verdict": verdict, "class": cls, "seconds": seconds, "peakMB": 30.0, "assumed": [], **kw}
    runs = [r("conformance/a/1", "native", "strict", "unverifiable", "unsupported", 0.1, reason="gap"),
            r("conformance/a/1", "native", "assume", "verified", "false-success-assuming", 0.1, assumed=["g"]),
            r("conformance/a/1", "jbmc", "strict", "violation", "correct", 0.5),
            r("conformance/a/1", "jbmc", "assume", "violation", "correct", 0.6),
            r("real/b", "native", "strict", "verified", "correct", 0.2),
            r("real/b", "native", "assume", "verified", "correct", 0.3),
            r("real/b", "jbmc", "strict", "unverifiable", "unsupported", 120.0, reason="out of time"),
            r("real/b", "jbmc", "assume", "unverifiable", "unsupported", 120.0, reason="out of time")]
    return {"environment": {"date": "d", "cpus": 8, "cpu": "c", "machine": "m", "jvmcontract": "j", "jbmc": "6.11.0", "java": "25"},
            "settings": {"timeout": 120, "unwind": 16, "maxArrayLength": 8, "engines": ["native", "jbmc"], "modes": ["strict", "assume"], "groups": [1, 2]},
            "cases": cases, "reference": {"real/b": {"agrees": True, "said": "held 1000", "inputs": 1000}}, "runs": runs}


class TablesTest(unittest.TestCase):
    def test_correct_unsupported_and_wrong_are_counted_apart(self):
        rows = {(r["group"], r["engine"], r["mode"]): r for r in run.summarize(results())}
        self.assertEqual(rows[(1, "native", "strict")]["unsupported"], 1)
        self.assertEqual(rows[(1, "native", "assume")]["falseSuccess"], 1)
        self.assertEqual(rows[(1, "native", "assume")]["falseSuccessAssuming"], 1)
        self.assertEqual(rows[(2, "jbmc", "strict")]["reasons"], {"out of time": 1})
        self.assertEqual(rows[(2, "native", "strict")]["correct"], 1)

    def test_a_workload_median_is_over_decided_runs_only(self):
        rows = {(r["workload"], r["engine"]): r for r in run.by_workload(results())}
        self.assertIsNone(rows[("div-rem", "jbmc")]["medianSeconds"])
        self.assertEqual(rows[("div-rem", "jbmc")]["maxSeconds"], 120.0)
        self.assertEqual(rows[("semantics", "jbmc")]["correct"], 1)

    def test_the_page_names_every_case_and_says_what_the_jvm_said(self):
        page = run.render(results())
        self.assertIn("| 2 real regressions | jbmc | strict | 1 | 0 | 0 | 1 |", page)
        self.assertIn("1 (1 naming a gap)", page)
        self.assertIn("| `real/b` | verified | held 1000 | ✓ verified 0.20 s |", page)
        self.assertIn("– out of time 120.0 s", page)
        self.assertIn("Every expected answer of groups 2 and 3 is borne out on the JVM.", page)


class SatTest(unittest.TestCase):
    """Phase 1b: the SAT solver each run was solved on, from the result's evidence, gathered into the environment."""

    native = {"solver": "CaDiCaL", "version": "1.9.5", "source": "bundled by the Rust crate cadical 0.1.16", "configuration": ["CaDiCaL's default options"]}
    jbmc = {"solver": "CaDiCaL", "version": "3.0.0", "source": "linked into JBMC (/usr/bin/jbmc)", "configuration": ["--sat-solver", "cadical"]}

    def test_a_run_names_the_solver_its_verdict_was_solved_on(self):
        self.assertEqual(run.sat_of({"stated": {"checker": {"engine": "native", "sat": self.native}}}), self.native)
        self.assertIsNone(run.sat_of({"stated": {"checker": {"engine": "none", "name": "gap scan"}}}))
        self.assertIsNone(run.sat_of(None))

    def test_the_environment_names_each_engines_solvers_once(self):
        runs = [{"engine": "native", "sat": self.native}, {"engine": "native", "sat": dict(self.native)},
                {"engine": "jbmc", "sat": self.jbmc}, {"engine": "jbmc", "sat": None}, {"engine": "jbmc", "sat": {**self.jbmc, "version": None}}]
        self.assertEqual(run.sat_solvers(runs), {"native": [self.native], "jbmc": [self.jbmc, {**self.jbmc, "version": None}]})
        self.assertEqual(run.sat_solvers([{"engine": "jbmc", "sat": None}]), {})

    def test_the_page_names_the_solvers_and_an_older_job_without_them_reads_as_before(self):
        before = run.render(results())
        self.assertNotIn("SAT solvers", before)
        r = results()
        r["environment"]["sat"] = {"native": [self.native], "jbmc": [self.jbmc]}
        page = run.render(r)
        self.assertIn("SAT solvers: the own checker on CaDiCaL 1.9.5, bundled by the Rust crate cadical 0.1.16; "
                      "JBMC on CaDiCaL 3.0.0, linked into JBMC (/usr/bin/jbmc).", page)
        self.assertEqual(page.replace(page[page.index("\n\nSAT solvers"):page.index("`results.json`.") + len("`results.json`.")], ""), before)


class PhasesTest(unittest.TestCase):
    """Step 5b: a run's seconds by phase, from the checker runs' phases and the driver's steps."""

    data = {"search": {"runs": [
        {"checker": "jbmc", "seconds": 0.1, "phases": {"loading": 0.01, "lowering": 0.01, "symbolic": 0.02, "encoding": 0.01, "solving": 0.03, "trace": 0.0, "other": 0.02},
         "formula": {"steps": 116, "conditions": 1, "variables": 1804, "clauses": 3952}},
        {"checker": "jbmc", "seconds": 0.2, "phases": {"loading": 0.01, "lowering": 0.0, "symbolic": 0.04, "encoding": 0.05, "solving": 0.08, "trace": 0.01, "other": 0.01},
         "formula": {"steps": 114, "variables": 1674, "clauses": 9000}},
        {"checker": "jbmc", "seconds": 0.5, "phases": None, "formula": {"variables": None, "clauses": None}}],
        "phases": {"seconds": 0.9, "setup": 0.02, "harness": 0.0, "gaps": 0.05, "contracts": 0.0, "runs": 0.8, "replay": 0.01, "jvm": 0.0, "other": 0.02}}}

    def test_a_run_is_its_checker_runs_phases_and_the_drivers_steps(self):
        p = run.phases_of(self.data, 1.0)
        self.assertEqual(set(p), set(run.PHASES))
        self.assertEqual((p["solving"], p["encoding"], p["checker-other"]), (0.11, 0.06, 0.03))
        self.assertEqual((p["gaps"], p["setup"], p["replay"]), (0.05, 0.02, 0.01))
        self.assertAlmostEqual(sum(p.values()), 1.0, places=2, msg="the rest of the process, an untimed run's seconds among it, is the driver's")
        self.assertAlmostEqual(p["driver"], 0.62, places=3)
        self.assertEqual(run.formula_of(self.data), {"steps": 116, "conditions": 1, "variables": 1804, "clauses": 9000})
        nothing = run.phases_of(None, 2.0)
        self.assertEqual((nothing["driver"], nothing["solving"]), (2.0, 0.0))
        self.assertIsNone(run.phases_excess(self.data, p, 1.0))

    def test_phases_past_their_time_are_flagged_not_scaled(self):
        flagged = {"search": {"runs": [{**self.data["search"]["runs"][0], "phases_excess": 0.4}]}}
        self.assertEqual(run.phases_excess(flagged, run.phases_of(flagged, 1.0), 1.0), 0.4, "a checker run's own flag")
        self.assertEqual(run.stats_of(flagged)["runs"][0]["phasesExcess"], 0.4)
        p = run.phases_of(self.data, 0.3)
        self.assertEqual(run.phases_excess(self.data, p, 0.3), 0.08, "0.38 s of phases in a 0.3 s run")
        self.assertIsNone(run.phases_excess(self.data, p, 0.375), "within 1% and 5 ms")

    def test_the_table_names_the_dominant_phase_per_workload_and_engine(self):
        results = results_with_phases()
        rows = {(r["workload"], r["engine"]): r for r in run.by_phase(results)}
        self.assertEqual(rows[("div-rem", "jbmc")]["dominant"], "solving")
        self.assertEqual(rows[("div-rem", "jbmc")]["undecided"], 1, "a run out of time counts, its time spent")
        self.assertEqual(rows[("div-rem", "native")]["dominant"], "encoding")
        self.assertNotIn(("semantics", "native"), rows, "group 1's native runs had no phases")
        page = run.render(results)
        self.assertIn("## Where the time goes, by workload, under strict", page)
        self.assertIn("| div-rem | jbmc | 1 (1 undecided) | 120.0 |", page)
        self.assertIn("**solving** 90%", page)
        self.assertIn("### The recorded examples", page)
        self.assertIn("| example/142 | native | 1 | 7.0 |", page)
        self.assertNotIn("Left out of these tables", page)

    def test_a_run_whose_phases_add_up_past_its_time_is_left_out_of_the_table_and_named(self):
        results = results_with_phases()
        by = {(x["case"], x["engine"], x["mode"]): x for x in results["runs"]}
        by[("real/b", "jbmc", "strict")]["phasesExcess"] = 6.1
        rows = {(r["workload"], r["engine"]): r for r in run.by_phase(results)}
        self.assertNotIn(("div-rem", "jbmc"), rows)
        self.assertIn("Left out of these tables, because their phases add up to more than their time (beyond 1% and 5 ms): "
                      "`real/b` on jbmc (by 6.1 s).", run.render(results))


def results_with_phases():
    r = results()
    phases = lambda **kw: {**dict.fromkeys(run.PHASES, 0.0), **kw}
    by = {(x["case"], x["engine"], x["mode"]): x for x in r["runs"]}
    by[("real/b", "jbmc", "strict")]["phases"] = phases(solving=108.0, encoding=6.0, symbolic=6.0)
    by[("real/b", "native", "strict")]["phases"] = phases(encoding=0.15, solving=0.05)
    by[("conformance/a/1", "jbmc", "strict")]["phases"] = phases(**{"checker-other": 0.3, "gaps": 0.2})
    r["cases"].append({"id": "example/142", "group": 4, "workload": "utf8", "kind": "regression", "expected": "verified"})
    r["settings"]["groups"].append(4)
    r["runs"].append({"case": "example/142", "engine": "native", "mode": "strict", "verdict": "verified", "class": "correct", "seconds": 7.0,
                      "peakMB": 74.0, "assumed": [], "phases": phases(solving=6.4, encoding=0.3), "formula": {"clauses": 161165}})
    return r


class StagingTest(unittest.TestCase):
    """Step 2b: JBMC's runs under each staging policy, compared with the first, proofs and counterexamples apart."""

    class Options(CommandTest.Options):
        pass

    def test_a_policy_is_passed_to_jvmcontract_and_none_without_one(self):
        case = {"kind": "regression", "before": "broken", "after": "fixed", "target": "p.C#m"}
        cmd = run.command(case, "jbmc", "strict", CommandTest.classes, Path("/w"), self.Options, "tight")
        self.assertEqual(cmd[cmd.index("--jbmc-staging") + 1], "tight")
        self.assertNotIn("--jbmc-staging", run.command(case, "native", "strict", CommandTest.classes, Path("/w"), self.Options))

    def test_a_witness_is_measured_as_reported_and_as_found(self):
        self.assertEqual(run.witness_size([{"value": [3, -70000, 2]}, {"value": True}, {"value": "-9000000000"}, {"value": "NaN"}, {"value": None}]),
                         {"elements": 3, "largest": 9000000000})
        self.assertEqual(run.witness_size([{"name": "r", "components": [{"value": -5}, {"value": [0]}]}]), {"elements": 1, "largest": 5})
        self.assertIsNone(run.witness_size(None))
        data = {"verdict": "violation", "search": {"staging": "staged"},
                "counterexample": {"inputs": [{"value": [99]}], "found_inputs": [{"value": [1000000, 7, 7]}], "shrink_runs": 12}}
        record = run.record_of({"id": "y", "expected": "violation"}, "jbmc", "strict", "staged", data, measured(), Path("/w"))
        self.assertEqual((record["staging"], record["witness"], record["witnessSize"], record["foundSize"], record["shrinkRuns"]),
                         ("staged", "[99]", {"elements": 1, "largest": 99}, {"elements": 3, "largest": 1000000}, 12))
        native = run.record_of({"id": "y", "expected": "violation"}, "native", "strict", None,
                               {"verdict": "violation", "counterexample": {"inputs": [{"value": 1}]}}, measured(), Path("/w"))
        self.assertNotIn("staging", native)
        self.assertNotIn("foundSize", native, "a witness that was not shrunk has no found size")

    def test_auto_runs_the_other_policies_only_where_it_fell_back(self):
        calls = []
        fell_back = {"x": True, "y": False}

        def fake(case, engine, mode, staging, classes, build, options):
            calls.append((case["id"], engine, staging))
            record = {"case": case["id"], "engine": engine, "mode": mode, "verdict": "verified", "class": "correct", "seconds": 0.1, "peakMB": 1.0}
            if engine == "auto":
                record["fallback"] = fell_back[case["id"]]
            return record

        cases = [{"id": i, "group": 2, "workload": "w", "kind": "property", "expected": "verified"} for i in ("x", "y")]
        original = (run.run_one, run.load_cases, run.compile_sources, run.compile_examples, run.reference, run.check_witnesses, run.environment)
        try:
            run.run_one = fake
            run.load_cases = lambda groups, pattern=None: cases
            run.compile_sources = lambda build: {}
            run.compile_examples = lambda build, cases: {}
            run.reference = lambda *a: {}
            run.check_witnesses = lambda *a: None
            run.environment = lambda options: {}
            with tempfile.TemporaryDirectory() as build:
                options = run.main.__globals__["argparse"].Namespace(groups="2", engines="native,jbmc,auto", modes="strict", cases=None,
                                                                     jbmc_staging="staged,full-range,tight", build=build, search=1,
                                                                     timeout=120, quiet=True)
                results = run.run(options)
        finally:
            (run.run_one, run.load_cases, run.compile_sources, run.compile_examples, run.reference, run.check_witnesses, run.environment) = original
        self.assertEqual(calls, [("x", "native", None), ("x", "jbmc", "staged"), ("x", "jbmc", "full-range"), ("x", "jbmc", "tight"),
                                 ("x", "auto", "staged"), ("x", "auto", "full-range"), ("x", "auto", "tight"),
                                 ("y", "native", None), ("y", "jbmc", "staged"), ("y", "jbmc", "full-range"), ("y", "jbmc", "tight"),
                                 ("y", "auto", "staged")])
        self.assertEqual(results["settings"]["jbmcStaging"], ["staged", "full-range", "tight"])
        with self.assertRaises(SystemExit):
            run.run(run.main.__globals__["argparse"].Namespace(**{**vars(options), "jbmc_staging": "staged,full"}))

    def test_the_corpus_tables_are_over_the_first_policy_and_the_others_are_compared_with_it(self):
        r = staged_results()
        before = run.render(results())
        page = run.render(r)
        self.assertIn("The tables of the corpus are over `staged`", page)
        self.assertIn("| 2 real regressions | jbmc | strict | 1 | 0 | 0 | 1 |", page, "the staged run alone, as before")
        self.assertEqual(page.count("| 1 semantic conformance | jbmc | strict | 1 |"), 1)
        rows = {(x["engine"], x["mode"], x["side"], x["staging"]): x for x in run.by_staging(r)}
        proofs = rows[("jbmc", "strict", "proofs", "full-range")]
        self.assertEqual((proofs["correct"], proofs["unsupported"], proofs["seconds"], proofs["changed"]), (1, 0, 30.0, 1))
        self.assertEqual(rows[("jbmc", "strict", "proofs", "staged")]["starved"], 0, "out of time on its full range, not starved")
        counter = rows[("jbmc", "strict", "counterexamples", "tight")]
        self.assertEqual((counter["correct"], counter["largerWitnesses"], counter["shrunk"]), (1, 1, 0))
        self.assertEqual(rows[("jbmc", "strict", "counterexamples", "full-range")]["largerWitnesses"], 0)
        self.assertNotIn(("auto", "strict", "proofs", "staged"), rows, "auto's own checker decided real/b")
        auto = rows[("auto", "strict", "counterexamples", "staged")]
        self.assertEqual((auto["cases"], auto["unsupported"], auto["starved"]), (1, 1, 1))
        self.assertEqual(rows[("auto", "strict", "counterexamples", "full-range")]["correct"], 1)
        self.assertIn("## JBMC's staging policies", page)
        self.assertIn("| jbmc | strict | proofs | `full-range` | 1 of 1 | 0 | 0 | 30.0 | 30.0 | 1 | · | · | 0 |  |", page)
        self.assertIn("Cases whose class differs between the policies, jbmc under strict: `real/b`.", page)
        self.assertIn("| `conformance/a/1` | ✓ violation 0.50 s, `[1]` (1 el., max 1) | ✓ violation 0.40 s, `[1]` (1 el., max 1; found 8 el., max 99999) | "
                      "✓ violation 0.30 s, `[2,5]` (2 el., max 5) |", page)
        self.assertIn("<summary>Counterexamples, auto under strict, 1 case: each case where JBMC's fallback ran, per policy</summary>", page)
        self.assertIn("– out of time 30.0 s, full range starved", page)
        self.assertNotIn("JBMC's staging policies", before)
        decided = staged_results()
        decided["runs"] = [x for x in decided["runs"] if x["engine"] != "jbmc" and x["case"] != "conformance/a/1"]
        self.assertIn("No run of `jbmc` was made, and no run of `auto` fell back to JBMC.", run.render(decided))


def staged_results():
    """results() with each JBMC run under three policies, and auto: its own checker deciding one case, falling back
    on the other, where staged's stages leave the full range nothing."""
    r = results()
    r["settings"]["engines"].append("auto")
    r["settings"]["jbmcStaging"] = ["staged", "full-range", "tight"]
    runs = []
    for x in r["runs"]:
        if x["engine"] == "jbmc":
            x["staging"] = "staged"
            x["witnessSize"] = {"elements": 1, "largest": 1} if x["verdict"] == "violation" else None
            if x["verdict"] == "violation":
                x["witness"] = "[1]"
            x["solver"] = {"runs": [{"checker": "jbmc", "stage": None, "budget": 105.0, "ended": "out-of-time"}]} if x["class"] == "unsupported" else {}
        runs.append(x)
    def jbmc(case, mode, staging, verdict, cls, seconds, **kw):
        return {"case": case, "engine": "jbmc", "mode": mode, "staging": staging, "verdict": verdict, "class": cls, "seconds": seconds, "peakMB": 30.0, "assumed": [], **kw}
    for mode in ("strict", "assume"):
        runs += [jbmc("conformance/a/1", mode, "full-range", "violation", "correct", 0.4, witness="[1]", witnessSize={"elements": 1, "largest": 1},
                      foundSize={"elements": 8, "largest": 99999}, shrinkRuns=20),
                 jbmc("conformance/a/1", mode, "tight", "violation", "correct", 0.3, witness="[2,5]", witnessSize={"elements": 2, "largest": 5}),
                 jbmc("real/b", mode, "full-range", "verified", "correct", 30.0),
                 jbmc("real/b", mode, "tight", "unverifiable", "unsupported", 120.0, reason="out of time")]
    starving = {"runs": [{"checker": "native", "stage": None}, {"checker": "jbmc", "stage": "[0:20]", "budget": 15.0, "ended": "out-of-time"},
                         {"checker": "jbmc", "stage": "[-100000:100000]", "budget": 15.0, "ended": "out-of-time"}]}
    runs += [{"case": "real/b", "engine": "auto", "mode": "strict", "staging": "staged", "fallback": False, "verdict": "verified", "class": "correct", "seconds": 0.2, "peakMB": 30.0, "assumed": []},
             {"case": "conformance/a/1", "engine": "auto", "mode": "strict", "staging": "staged", "fallback": True, "verdict": "unverifiable", "class": "unsupported",
              "reason": "out of time", "seconds": 30.0, "peakMB": 30.0, "assumed": [], "solver": starving},
             {"case": "conformance/a/1", "engine": "auto", "mode": "strict", "staging": "full-range", "fallback": True, "verdict": "violation", "class": "correct",
              "seconds": 1.0, "peakMB": 30.0, "assumed": [], "witness": "[1]", "witnessSize": {"elements": 1, "largest": 1}}]
    r["runs"] = runs
    return r


class CorpusTest(unittest.TestCase):
    def test_every_case_is_complete_and_names_classes_that_exist(self):
        corpus = json.loads((HERE / "corpus.json").read_text())
        ids = set()
        for case in corpus["cases"]:
            self.assertNotIn(case["id"], ids)
            ids.add(case["id"])
            self.assertIn(case["group"], (2, 3))
            self.assertIn(case["expected"], ("verified", "violation"))
            for key in ("workload", "source", "why", "target"):
                self.assertTrue(case.get(key), (case["id"], key))
            if case["expected"] == "violation":
                self.assertIn("witness", case, case["id"])
            versions = [case["classes"]] if case["kind"] == "property" else [case["before"], case["after"]]
            class_name = case["target"].split("#")[0]
            for version in versions:
                source = HERE / corpus["versions"][version] / (class_name.replace(".", "/") + ".java")
                self.assertTrue(source.exists(), source)

    def test_the_first_group_is_the_conformance_corpus(self):
        group = json.loads((HERE / "conformance.json").read_text())["cases"]
        self.assertGreater(len(group), 50)
        self.assertTrue(all(c["group"] == 1 and c["expected"] in ("verified", "violation") for c in group))

    def test_the_recorded_examples_are_read_from_their_example_files(self):
        cases = {c["id"]: c for c in run.recorded_cases()}
        self.assertEqual(set(cases), {"example/141", "example/142"})
        self.assertEqual(cases["example/141"]["target"], "net.terminalvalue.mica.interp.LookupSwitch#find")
        self.assertIn("\\forall", cases["example/141"]["unchangedUnless"])
        self.assertIsNone(cases["example/142"]["unchangedUnless"])
        for c in cases.values():
            self.assertEqual((c["group"], c["modes"], c["expected"]), (4, ["strict"], "verified"))
            self.assertTrue(Path(c["patch"]).exists() and (run.REPO / c["app"] / "src/main/java").is_dir(), c)
        cmd = run.command(cases["example/141"], "jbmc", "strict", {"example-141-before": Path("/b"), "example-141-after": Path("/a")}, Path("/w"), CommandTest.Options)
        self.assertEqual(cmd[cmd.index("--unchanged-unless") + 1], cases["example/141"]["unchangedUnless"])

    @unittest.skipUnless(shutil.which("java") and shutil.which("javac"), "needs a JDK")
    def test_the_reference_has_exactly_the_corpus_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            requests = Path(tmp) / "requests"
            requests.write_text("list\n")
            listed = subprocess.run(["java", str(HERE / "Reference.java"), tmp, str(requests)], capture_output=True, text=True, check=True).stdout
        corpus = json.loads((HERE / "corpus.json").read_text())
        self.assertEqual(sorted(line.split("\t")[0] for line in listed.splitlines()), sorted(c["id"] for c in corpus["cases"]))


if __name__ == "__main__":
    unittest.main()

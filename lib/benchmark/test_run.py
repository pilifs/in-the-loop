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

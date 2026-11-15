#!/usr/bin/env python3
"""Tests for cost_inventory.py and test_costs.py's `estimate`, on made-up sources, logs and results; nothing is run
but the parsing. Run: python3 lib/tools/test_cost_inventory.py"""
import json
import tempfile
import textwrap
import unittest
from pathlib import Path

import cost_inventory as ci
import test_costs as tc

RUST = r'''
use std::process::Command;

const JAVA: &str = r#"class A { void f() { if (x) { } } }"#;  // braces in a raw string: { {
/* a comment with a fn not_a_test() { and a nested /* comment */ } */

fn helper<'a>(x: &'a str) -> char {
    let c = '{';
    let _ = Command::new("javac");
    c
}

fn proves() {
    let _ = jvmcontract::equivalence::run(todo!());
}

#[test]
fn calls_the_helper() {
    let s = "a } string";
    helper(s);
}

#[test]
#[ignore = "runs JBMC: \
            a pipeline job"]
fn ignored_one() {
    proves();
}

mod inner {
    #[test]
    fn nested() {
        let options = Options { engine: Engine::Native, ..Default::default() };
        super::proves();
    }

    mod deeper {
        #[test]
        fn pure() { assert_eq!(1 + 1, 2); }
    }
}

#[test]
fn a_stand_in() {
    std::fs::write("jbmc", "#!/bin/sh\necho VERIFICATION SUCCESSFUL\n").unwrap();
    let _ = Engine::Jbmc;
}

#[test]
fn uses_the_fixture() {
    fixture::build();
}

mod fixture;
'''

FIXTURE = '''
pub fn build() {
    let _ = std::process::Command::new(env!("CARGO_BIN_EXE_jvmcontract"));
}
'''

UNIT = '''
pub fn spawn_tlc() { let _ = run_tlc(&opts); }

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn models_the_spec() {
        spawn_tlc();
    }
}
'''

PYTHON = '''
import subprocess
import unittest


def run_git():
    return subprocess.run(["git", "status"])


class Base(unittest.TestCase):
    def test_inherited(self):
        self.assertTrue(True)


class Spawning(Base):
    def setUp(self):
        self.x = 1

    def test_through_a_function(self):
        run_git()

    def test_pure(self):
        self.assertEqual(self.x, 1)


class NotACase:
    def test_ignored(self):
        pass
'''

CARGO = """
     Running tests/heap.rs (target/debug/deps/heap-0123)

running 1 test
test the_field_relations_agree ... ok

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 57 filtered out; finished in 243.97s

     Running unittests src/lib.rs (target/debug/deps/jvmcontract-4567)

running 3 tests
test values::tests::a ... ok
test values::tests::b ... ok
test values::tests::slow has been running for over 60 seconds
test values::tests::slow ... ok

test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 70.50s
"""


class ReadingRust(unittest.TestCase):
    def test_blanking_keeps_positions_and_hides_braces(self):
        code = ci.blank(RUST)
        self.assertEqual(len(code), len(RUST))
        self.assertEqual(code.count("\n"), RUST.count("\n"))
        self.assertNotIn("not_a_test", code)
        self.assertNotIn("a } string", code)
        self.assertEqual(code.count("{"), code.count("}"))
        self.assertIn('"javac"', ci.blank(RUST, strings=False))

    def test_items_have_their_module_path_attributes_and_ignore_reason(self):
        items = {it["name"]: it for it in ci.rust_items(RUST) if "fn" in it}
        self.assertEqual(sorted(n for n, it in items.items() if it["test"]),
                         ["a_stand_in", "calls_the_helper", "ignored_one", "inner::deeper::pure", "inner::nested",
                          "uses_the_fixture"])
        self.assertEqual(items["ignored_one"]["ignore"], "runs JBMC: a pipeline job")
        self.assertIsNone(items["calls_the_helper"]["ignore"])
        self.assertFalse(items["helper"]["test"])
        self.assertEqual([m["mod"] for m in ci.rust_items(RUST) if "mod" in m], ["fixture"])
        self.assertEqual(ci.rust_items(UNIT, ("tla",))[1]["name"], "tla::tests::models_the_spec")


class Calls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.root = Path(self.tmp.name)
        (root / "lib" / "tests" / "fixture").mkdir(parents=True)
        (root / "lib" / "src").mkdir(parents=True)
        (root / "lib" / "tests" / "made_up.rs").write_text(RUST)
        (root / "lib" / "tests" / "fixture" / "mod.rs").write_text(FIXTURE)
        (root / "lib" / "src" / "lib.rs").write_text("pub mod tla;\n")
        (root / "lib" / "src" / "main.rs").write_text("fn main() {}\n")
        (root / "lib" / "src" / "tla.rs").write_text(UNIT)
        (root / "examples" / "tools").mkdir(parents=True)
        (root / "examples" / "tools" / "test_made_up.py").write_text(PYTHON)

    def tearDown(self):
        self.tmp.cleanup()

    def test_what_each_rust_test_calls(self):
        tests = {t["name"]: t for t in ci.rust_tests(self.root)}
        self.assertEqual(tests["tla::tests::models_the_spec"]["binary"], "src/lib.rs")
        self.assertEqual(tests["tla::tests::models_the_spec"]["calls"], ["tlc"])
        self.assertEqual(tests["calls_the_helper"]["calls"], ["javac", "process"])
        self.assertEqual(tests["ignored_one"]["calls"], ["jbmc"])  # equivalence::run defaults to JBMC
        self.assertEqual(tests["ignored_one"]["ignore"], "runs JBMC: a pipeline job")
        self.assertEqual(tests["inner::nested"]["calls"], [])  # ... unless the native engine is named
        self.assertEqual(tests["inner::deeper::pure"]["calls"], [])
        self.assertEqual(tests["a_stand_in"]["calls"], ["stand-in"])  # the JBMC it names is the stand-in
        self.assertEqual(tests["uses_the_fixture"]["calls"], ["jvmcontract", "process"])
        self.assertEqual(tests["uses_the_fixture"]["binary"], "tests/made_up.rs")

    def test_what_each_python_test_calls(self):
        tests = {t["name"]: t for t in ci.python_tests(self.root, [self.root / "examples/tools/test_made_up.py"])}
        self.assertEqual(sorted(tests), ["Base.test_inherited", "Spawning.test_inherited",
                                         "Spawning.test_pure", "Spawning.test_through_a_function"])
        self.assertEqual(tests["Spawning.test_through_a_function"]["calls"], ["process"])
        self.assertEqual(tests["Spawning.test_pure"]["calls"], [])


class PastRuns(unittest.TestCase):
    def test_cargo_sections(self):
        s = ci.cargo_sections(CARGO)
        self.assertEqual([(x["binary"], x["ran"], x["seconds"]) for x in s],
                         [("tests/heap.rs", 1, 243.97), ("src/lib.rs", 3, 70.5)])
        self.assertEqual(s[0]["names"], ["the_field_relations_agree"])
        self.assertEqual(s[1]["over_60"], ["values::tests::slow"])
        cut = "test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 3 filtered out; finished in 1.50s"
        self.assertEqual(ci.cargo_sections(cut, "cargo test --test heap x")[0]["binary"], "tests/heap.rs")
        self.assertEqual(ci.cargo_sections(cut, "cargo test x"), [])

    def test_evidence_and_cost(self):
        tests = [{"binary": "tests/heap.rs", "name": "the_field_relations_agree", "ignore": "JBMC"},
                 {"binary": "src/lib.rs", "name": "values::tests::a", "ignore": None},
                 {"binary": "src/lib.rs", "name": "values::tests::slow", "ignore": None},
                 {"binary": "src/lib.rs", "name": "values::tests::new", "ignore": None}]
        sections = [{**s, "source": "job:J1"} for s in ci.cargo_sections(CARGO)]
        whole = "Running unittests src/lib.rs (x)\ntest result: ok. 9 passed; 0 failed; 0 ignored; 0 measured; " \
                "0 filtered out; finished in 0.40s"
        sections += [{**s, "source": "log:" + "ab" * 32} for s in ci.cargo_sections(whole)]
        ev = ci.rust_evidence(tests, sections)
        self.assertEqual(ci.cost(ev[("tests/heap.rs", "the_field_relations_agree")]),
                         {"seconds": 243.97, "kind": "run alone", "runs": 1, "max_seconds": 243.97,
                          "sources": ["job:J1"]})
        self.assertEqual(ci.cost(ev[("src/lib.rs", "values::tests::slow")])["kind"], "over 60 s")
        # a whole-binary run with no names bounds every test of the binary, the new one too
        self.assertEqual(ci.cost(ev[("src/lib.rs", "values::tests::a")]),
                         {"seconds": 0.4, "kind": "at most", "sources": ["log:" + "ab" * 32]})
        self.assertEqual(ci.cost(ev[("src/lib.rs", "values::tests::new")])["seconds"], 0.4)
        self.assertEqual(ci.cost({"single": [], "over_60": [], "bound": None})["kind"], "estimated")

    def test_python_runs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "llm-dlc" / "tools").mkdir(parents=True)
            (root / "llm-dlc" / "tools" / "test_made_up.py").write_text("")
            known = {"test_made_up.py": ["llm-dlc/tools/test_made_up.py"]}
            out = "....\n------\nRan 4 tests in 0.250s\n\nOK\n"
            self.assertEqual(ci.python_runs("python3 llm-dlc/tools/test_made_up.py 2>&1 | tail -3", out, root),
                             [{"file": "llm-dlc/tools/test_made_up.py", "test": None, "ran": 4, "seconds": 0.25}])
            # run from another directory: the one test file of that name
            self.assertEqual(ci.python_runs("python3 test_made_up.py", out, root, known)[0]["file"],
                             "llm-dlc/tools/test_made_up.py")
            one = ci.python_runs("cd llm-dlc/tools && python3 -m unittest test_made_up.Case.test_x",
                                 "Ran 1 test in 3.100s", root)
            self.assertEqual(one[0]["test"], "Case.test_x")
            self.assertEqual(ci.python_runs("python3 a.py", out, root), [])
            self.assertEqual(len(ci.python_runs("python3 llm-dlc/tools/test_made_up.py > l 2>&1; grep Ran l", out, root)), 1)
            self.assertEqual(ci.python_runs("for t in llm-dlc/tools/test_made_up.py x/test_b.py; do python3 $t; done",
                                            out, root), [])
            self.assertEqual(ci.python_runs("python3 llm-dlc/tools/test_made_up.py", out + out, root), [])
            tests = [{"file": "llm-dlc/tools/test_made_up.py", "name": n} for n in ("Case.test_x", "Case.test_y")]
            ev = ci.python_evidence(tests, [{**one[0], "source": "log:s"},
                                            {**ci.python_runs("python3 llm-dlc/tools/test_made_up.py", out, root)[0],
                                             "source": "log:t"}])
            self.assertEqual(ci.cost(ev[("llm-dlc/tools/test_made_up.py", "Case.test_x")])["kind"], "run alone")
            self.assertEqual(ci.cost(ev[("llm-dlc/tools/test_made_up.py", "Case.test_y")])["seconds"], 0.25)

    def test_job_logs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            job = root / "verification" / "results" / "20261101-000000-made-up"
            (job / "logs").mkdir(parents=True)
            (job / "logs" / "1-tests.log").write_text(CARGO)
            (job / "result.json").write_text(json.dumps({
                "id": "20261101-000000-made-up",
                "steps": [{"run": "cd lib && cargo test", "log": {"path": "logs/1-tests.log"}},
                          {"run": "true", "log": {"path": "logs/missing.log"}}]}))
            sections = ci.job_evidence(root)
            self.assertEqual([s["source"] for s in sections], ["job:20261101-000000-made-up"] * 2)


class Estimating(unittest.TestCase):
    def tier(self, calls, seconds=None, kind="estimated", ignore=None, runs=1):
        return tc.estimate_tier(calls, {"seconds": seconds, "kind": kind, "runs": runs, "sources": []}, ignore)

    def test_what_it_calls_and_what_it_took(self):
        self.assertEqual(self.tier(["jbmc"], 650.8, "run alone")[:2], ("proof", "calls JBMC"))
        self.assertEqual(self.tier(["javac", "process"], 0.3, "at most"), ("tool", "spawns javac, process", None))
        self.assertEqual(self.tier([], 0.02, "at most"), ("unit", "nothing outside the process", None))
        self.assertEqual(self.tier(["java"], 43.8, "run alone"), ("proof", "spawns java; over the tool tier's 10 s", None))
        self.assertEqual(self.tier([], 1.5, "run alone")[:2], ("tool", "nothing outside the process; over the unit tier's 1 s"))
        self.assertEqual(self.tier(["stand-in"], 60, "over 60 s")[0], "proof")
        self.assertEqual(self.tier(["javac"], 46.7, "run alone", ignore="a benchmark")[0], "proof")
        self.assertEqual(self.tier([], 0.1, "at most", ignore="slow")[:2], ("proof", "nothing outside the process; ignored as expensive"))

    def test_what_is_an_estimate(self):
        self.assertEqual(self.tier([])[2], "no past run names it: the tier is from what it calls")
        self.assertEqual(self.tier([], 5.9, "at most")[2], "past runs bound it only at 5.9 s: the tier is from what it calls")
        self.assertIsNone(self.tier(["javac"], 5.9, "at most")[2])  # under the tool tier's 10 s
        self.assertEqual(self.tier(["tlc"], 0.4, "run alone"),
                         ("proof", "calls TLC", "took 0.4 s, too quick for TLC: it may stop before running it"))
        self.assertIsNone(self.tier(["jbmc"], 52.0, "at most")[2])  # calling JBMC is proof, whatever it took

    def test_the_file_is_one_test_per_line_and_reads_back(self):
        doc = {"generated": "g", "summary": {"rust": {"lib/tests/a.rs": {"unit": 1}}, "python": {}},
               "rust": [{"file": "lib/tests/a.rs", "name": "t", "tier": "unit"}],
               "python": [{"file": "x/test_a.py", "name": "A.test_b", "tier": "tool"},
                          {"file": "x/test_a.py", "name": "A.test_c", "tier": "unit"}]}
        text = tc.dumps(doc)
        self.assertEqual(json.loads(text), doc)
        self.assertIn('\n  {"file": "x/test_a.py", "name": "A.test_c", "tier": "unit"}\n', text)


if __name__ == "__main__":
    unittest.main()

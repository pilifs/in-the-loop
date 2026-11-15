#!/usr/bin/env python3
"""The lint of the tests' cost tiers (step 7 of llm-dlc/loops/test-cost.md): `test_costs.py lint` on this repository,
for the Rust and the Python tests, and on made-up sources. In process, at the unit tier. Run:
python3 lib/tools/test_tier_lint.py"""
import json
import tempfile
import textwrap
import unittest
from pathlib import Path

import cost_inventory as ci
import test_costs as tc


class ThisRepository(unittest.TestCase):
    """What `lib/README.md`'s Tests section says to do about a problem: `estimate` for a test the inventory lacks or
    records out of date, `tag FILE` for a tier tag, and a proof tag with a proxy for a test that runs JBMC or TLC.
    Joining the `retier: pending` or `proxy: none yet` list is for a person to decide."""

    def test_the_rust_tests_tier_tags_agree_with_their_sources_and_the_inventory(self):
        problems = tc.lint(only="rust")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_the_python_tests_tier_tags_agree_with_their_sources_and_the_inventory(self):
        problems = tc.lint(only="python")
        self.assertEqual(problems, [], "\n".join(problems))


RUST = '''\
use std::process::Command;

#[test]
fn quick() {}

#[test]
fn spawns() {
    jvmcontract::tool_tier!();
    let _ = Command::new("javac");
}

#[test]
#[ignore = "cost:proof: JBMC on one case, ~1 min; \\
    proxy: quick"]
fn slow() {
    let _ = has_jbmc();
}

#[test]
fn runs_jbmc_by_default() {
    jvmcontract::tool_tier!(pending);
    let _ = has_jbmc();
}

#[test]
#[ignore = "cost:proof: a benchmark, ~1 min; proxy: none yet"]
fn benchmark() {}
'''

PYTHON = '''\
import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402


class B(unittest.TestCase):
    def test_quick(self):
        pass

    @cost("proof", "TLC on one model, ~2 min; proxy: B.test_quick")
    def test_slow(self):
        pass
'''


class MadeUp(unittest.TestCase):
    """Made-up sources. A made-up call that would spawn a process is split across strings, so that the inventory
    doesn't read it as one of this file's own."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="tier-lint-"))
        self.addCleanup(__import__("shutil").rmtree, self.root, True)
        for rel, text in {"lib/src/main.rs": "", "lib/src/lib.rs": "", "lib/tests/a.rs": RUST,
                          "tools/test_b.py": PYTHON}.items():
            (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.root / rel).write_text(text)
        self.inventory = self.root / "costs.json"
        self.estimate()

    def estimate(self, listed=()):
        previous = json.loads(self.inventory.read_text()) if self.inventory.exists() else None
        self.inventory.write_text(tc.dumps(tc.estimate(self.root, previous=previous, listed=listed)))

    def edit(self, rel, old, new):
        p = self.root / rel
        self.assertIn(old, p.read_text())
        p.write_text(p.read_text().replace(old, new))

    def lint(self):
        return tc.lint(self.inventory, self.root)

    def test_tags_that_agree_with_the_sources_and_the_inventory_pass(self):
        self.assertEqual(self.lint(), [])
        rows = {r["name"]: r for r in json.loads(self.inventory.read_text())["rust"]}
        self.assertEqual(rows["runs_jbmc_by_default"]["retier"], "pending")
        self.assertNotIn("unlisted", rows["benchmark"])

    def test_a_test_the_inventory_lacks_or_names_wrongly(self):
        self.edit("lib/tests/a.rs", "fn quick() {}", "fn quick() {}\n\n#[test]\nfn added() {}")
        self.edit("tools/test_b.py", "def test_quick", "def test_renamed")
        problems = "\n".join(self.lint())
        self.assertIn("lib/tests/a.rs::added: not in the inventory", problems)
        self.assertIn("tools/test_b.py::B.test_renamed: not in the inventory", problems)
        self.assertIn("tools/test_b.py::B.test_quick: in the inventory, but no such test", problems)
        self.assertIn("its proxy B.test_quick is no test", problems)

    def test_an_ignore_reason_that_is_no_proof_tag_or_names_no_proxy(self):
        self.edit("lib/tests/a.rs", "cost:proof: JBMC on one case, ~1 min; \\\n    proxy: quick", "runs JBMC")
        self.estimate()
        problems = self.lint()
        self.assertIn("lib/tests/a.rs::slow: its ignore reason doesn't start with 'cost:proof: ': 'runs JBMC'",
                      problems)
        self.assertIn("lib/tests/a.rs::slow: its proof tag names no proxy (`; proxy: TEST`, or `; proxy: none yet`)",
                      problems)

    def test_a_proxy_that_is_no_test_or_is_itself_proof_tier(self):
        self.edit("lib/tests/a.rs", "proxy: quick", "proxy: quick, nothing_by_this_name, benchmark")
        self.estimate()
        self.assertEqual(self.lint(), ["lib/tests/a.rs::slow: its proxy nothing_by_this_name is no test",
                                       "lib/tests/a.rs::slow: its proxy benchmark is itself proof tier: a proxy runs "
                                       "by default"])

    def test_a_test_that_starts_calling_jbmc_is_out_of_date_and_then_needs_a_tag_or_a_person(self):
        self.edit("lib/tests/a.rs", "fn quick() {}", "fn quick() {\n    let _ = has_jbmc();\n}")
        self.assertIn("lib/tests/a.rs::quick: the inventory is out of date (what it calls, or its proof tag): run "
                      "`python3 lib/tools/test_costs.py estimate`", self.lint())
        self.estimate()
        problems = self.lint()
        self.assertIn("lib/tests/a.rs::quick: retier: pending: for a person to decide (estimate --list), or tag it",
                      problems)
        self.assertIn("lib/tests/a.rs::quick: calls JBMC but isn't proof tier: tag it #[ignore = \"cost:proof: …; "
                      "proxy: TEST\"] and queue it, or a person lists it as retier: pending", problems)
        self.estimate(listed=["lib/tests/a.rs::quick"])  # a person's decision
        tc.tag([self.root / "lib/tests/a.rs"], self.inventory, self.root)
        self.assertEqual(self.lint(), [])
        self.estimate()  # once listed, it stays listed
        self.assertEqual(self.lint(), [])

    def test_a_new_proof_tag_without_a_proxy_needs_a_person(self):
        self.edit("lib/tests/a.rs", "proxy: quick", "proxy: none yet")
        self.estimate()
        self.assertEqual(self.lint(), ["lib/tests/a.rs::slow: proxy: none yet: for a person to decide (estimate "
                                       "--list), or tag it"])

    def test_a_tier_tag_that_isnt_the_one_the_row_asks_for(self):
        self.edit("lib/tests/a.rs", "    jvmcontract::tool_tier!();\n", "")
        self.edit("tools/test_b.py", '    @cost("proof", "TLC on one model, ~2 min; proxy: B.test_quick")\n', "")
        self.estimate()
        self.edit("lib/tests/a.rs", "fn quick() {}", "fn quick() {\n    jvmcontract::tool_tier!();\n}")
        self.assertEqual(self.lint(), ["lib/tests/a.rs: 2 tests' tier tags aren't what the inventory asks for: run "
                                       "`python3 lib/tools/test_costs.py tag lib/tests/a.rs`"])

    def test_python_proof_tags_need_a_reason_and_no_test_is_skipped_unconditionally(self):
        self.edit("tools/test_b.py", '@cost("proof", "TLC on one model, ~2 min; proxy: B.test_quick")',
                  '@cost("proof")')
        self.edit("tools/test_b.py", "    def test_quick", '    @unittest.skip("slow")\n    def test_quick')
        self.estimate()
        problems = self.lint()
        self.assertIn("tools/test_b.py::B.test_slow: @cost(\"proof\") without a reason: give what it runs, about how "
                      "long, and its proxy", problems)
        self.assertIn("tools/test_b.py::B.test_quick: skipped unconditionally ('slow'): a test set aside for its "
                      "cost is @cost(\"proof\", \"WHAT IT RUNS, ~TIME; proxy: TEST\")", problems)

    def test_a_python_test_that_runs_tlc_by_default_is_caught(self):
        self.edit("tools/test_b.py", "import sys\n", "import subprocess\nimport sys\n")
        self.edit("tools/test_b.py", "    def test_quick(self):\n        pass",
                  "    def test_quick(self):\n        pass\n\n    def test_model(self):\n"
                  "        subprocess" ".run(['java', '-cp', 'tla2tools" ".jar', 'tlc2" ".TLC', 'M'])")
        self.estimate()
        self.assertIn("tools/test_b.py::B.test_model: calls TLC but isn't proof tier: tag it @cost(\"proof\", \"…; "
                      "proxy: TEST\") and queue it, or a person lists it as retier: pending", self.lint())


class ImportedBases(unittest.TestCase):
    def test_a_testcase_imported_from_another_file_of_the_repository_is_followed(self):
        root = Path(tempfile.mkdtemp(prefix="tier-lint-"))
        self.addCleanup(__import__("shutil").rmtree, root, True)
        pkg = root / "tools" / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "__init__.py").write_text("")
        (pkg / "test_base.py").write_text(textwrap.dedent('''\
            import subprocess
            import unittest


            class Fixture(unittest.TestCase):
                def setUp(self):
                    subprocess.SPAWN(["git", "init"])
            ''').replace("SPAWN", "run"))
        (pkg / "test_more.py").write_text(textwrap.dedent('''\
            from pkg import test_base as base
            from pkg.test_base import Fixture


            class ByModule(base.Fixture):
                def test_one(self):
                    pass


            class ByName(Fixture):
                def test_two(self):
                    pass
            '''))
        rows = {r["name"]: r for r in ci.python_tests(root, [pkg / "test_more.py"])}
        self.assertEqual(sorted(rows), ["ByModule.test_one", "ByName.test_two"])
        self.assertEqual(rows["ByModule.test_one"]["calls"], ["process"], "the base's setUp is followed")


if __name__ == "__main__":
    unittest.main()

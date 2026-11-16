#!/usr/bin/env python3
"""Tests for scaffold_example.py: a designed example's claims and tasks written from stage 2's plan, checked before
anything is built, and what it refuses. Run: python3 examples/tools/test_scaffold_example.py
The example is a copy of the made-up target fixture (examples/tools/targets/fixtures) made into a catalog entry, and
the plan carries the fixture's own claims and tasks; nothing is built or run."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scaffold_example  # noqa: E402
from targets import sidecar  # noqa: E402

FIXTURE = HERE / "targets" / "fixtures"


class ScaffoldTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.folder = self.root / "examples" / "290-made-up-entry"
        shutil.copytree(FIXTURE, self.folder, ignore=shutil.ignore_patterns("__pycache__"))
        example = json.loads((self.folder / "example.json").read_text())
        target = json.loads((self.folder / "target.json").read_text())
        self.tasks = target["tasks"]
        self.claims = {f"claims/{p.name}": json.loads(p.read_text()) for p in sorted((self.folder / "claims").glob("*.json"))}
        shutil.rmtree(self.folder / "claims")
        target["tasks"] = []
        target["handoff"]["blockers"] = [b for b in target["handoff"]["blockers"] if "task" not in b]
        (self.folder / "target.json").write_text(json.dumps(target, indent=2))
        self.target_path = sidecar.path_of(self.folder, example)
        self.plan = self.root / "plan.json"
        self.write_plan()

    def write_plan(self, **changes):
        entry = {"id": "290", "review": "designed", "claimFiles": self.claims, "tasks": self.tasks, **changes}
        self.plan.write_text(json.dumps({"schema": "prove-plan/v1", "request": "290", "order": ["290"], "examples": [entry]}))

    def scaffold(self, write=True):
        return scaffold_example.scaffold("290", self.plan, write, root=self.root)

    def test_the_designed_claims_and_tasks_are_written_and_the_sidecar_checks(self):
        found = self.scaffold(write=False)
        self.assertEqual((found["refused"], sorted(found["wrote"])), ([], sorted(self.claims)))
        self.assertFalse((self.folder / "claims").exists(), "--check writes nothing")
        found = self.scaffold()
        self.assertEqual([t for t in found["added"]], [t["id"] for t in self.tasks])
        for name, doc in self.claims.items():
            self.assertEqual(json.loads((self.folder / name).read_text()), doc)
        example = json.loads((self.folder / "example.json").read_text())
        target = sidecar.load(self.folder, example)
        self.assertEqual([t["id"] for t in target["tasks"]], [t["id"] for t in self.tasks])
        self.assertEqual(self.scaffold()["added"], [], "a second run adds nothing it added already")

    def test_what_the_setup_has_not_made_yet_is_left_for_it_and_doesnt_stop_the_scaffold(self):
        target = json.loads(self.target_path.read_text())
        del target["history"]["revisions"]["mutant"]  # the setup makes the mutant from the plan
        target["history"]["pairs"] = [p for p in target["history"]["pairs"] if "mutant" not in (p["before"], p["after"])]
        target["controls"] = [c for c in target["controls"] if c.get("revision") != "mutant"]
        self.target_path.write_text(json.dumps(target, indent=2))
        found = self.scaffold()
        self.assertEqual(found["refused"], [])
        self.assertTrue(any("mutant" in line for line in found["leftForSetup"]), found)
        self.assertEqual(len(json.loads(self.target_path.read_text())["tasks"]), len(self.tasks))

    def test_a_frozen_claim_with_other_content_is_refused_and_nothing_is_written(self):
        name = next(iter(self.claims))
        (self.folder / "claims").mkdir()
        (self.folder / name).write_text(json.dumps({**self.claims[name], "statement": "Another claim."}))
        found = self.scaffold()
        self.assertTrue(any("a frozen claim changes only by a new review" in r for r in found["refused"]), found)
        self.assertEqual(json.loads(self.target_path.read_text())["tasks"], [])

    def test_a_claim_against_its_schema_a_task_without_its_claim_and_a_plan_that_designed_nothing_are_refused(self):
        name = next(iter(self.claims))
        self.write_plan(claimFiles={**self.claims, name: {"statement": "no kind, no property"}})
        self.assertTrue(any(r.startswith(name) for r in self.scaffold()["refused"]))
        self.write_plan(claimFiles={})
        self.assertTrue(any("neither in the plan nor in the example" in r for r in self.scaffold()["refused"]))
        self.write_plan(review="reused")
        self.assertIn("not designed: nothing to write", self.scaffold()["refused"][0])


if __name__ == "__main__":
    unittest.main()

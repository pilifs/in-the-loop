#!/usr/bin/env python3
"""Tests of workflow.py, owned by the workflow stream with it. Phase 0 left plan_task(), ingest() and handoff() as stubs that fail closed with the
named Unsupported result; these tests say so, and the stream rewrites them as it replaces each stub.

  python3 examples/tools/targets/test_workflow.py
"""

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from targets import interfaces, workflow  # noqa: E402
from test_interfaces import plan  # noqa: E402


class StubsFailClosedTest(unittest.TestCase):
    def check(self, value, interface, owner):
        self.assertTrue(interfaces.unsupported(value))
        self.assertEqual((value.interface, value.owner), (interface, owner))
        self.assertIn(owner, value.describe())

    def test_planning(self):
        self.check(workflow.plan_task(Path("."), {}, {}, "t"), "task-plan", interfaces.WORKFLOW)

    def test_ingestion(self):
        self.check(workflow.ingest(plan(), {}, (), Path(".")), "ingest", interfaces.WORKFLOW)

    def test_handoff(self):
        self.check(workflow.handoff(Path("."), {}, {}, "t"), "handoff", interfaces.WORKFLOW)

    def test_the_projection_states_only_what_the_sidecar_says(self):
        target = {"identity": {"case": "c", "family": "f", "role": "negative"}, "tasks": [{"id": "t"}],
                  "handoff": {"blockers": [{"kind": "java-semantics", "observed": False, "summary": "regex"}]}}
        row = workflow.project(Path("."), {}, target)
        self.assertEqual((row["family"], row["role"], row["readiness"], row["gaps"], row["predictedGaps"]),
                         ("f", "negative", None, [], ["java-semantics"]))


if __name__ == "__main__":
    unittest.main()

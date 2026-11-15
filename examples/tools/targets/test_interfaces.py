#!/usr/bin/env python3
"""Tests of the frozen interfaces (examples/tools/targets/interfaces.py): their signatures and fields don't change
under the streams. Coordinator-owned: a stream keeps it passing and never edits it. Phase 0's stubs are tested in
test_workflow.py and test_runtime.py, which their streams own and rewrite as they replace the stubs.

  python3 examples/tools/targets/test_interfaces.py
"""

import dataclasses
import inspect
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from targets import interfaces, runtime, workflow  # noqa: E402


# The frozen signatures: (module, function) -> parameter names.
SIGNATURES = {
    (workflow, "plan_task"): ["folder", "example", "target", "task"],
    (workflow, "ingest"): ["plan", "prepared", "records", "out"],
    (workflow, "project"): ["folder", "example", "target"],
    (workflow, "handoff"): ["folder", "example", "target", "task"],
    (runtime, "prepare"): ["plan", "revision", "workdir"],
    (runtime, "run_controls"): ["plan", "prepared", "workdir"],
    (runtime, "run_verifier"): ["plan", "prepared", "workdir"],
}

# The frozen fields of each type, in order: an owner may append a field with a default, never change these.
FIELDS = {
    interfaces.Unsupported: ["interface", "owner", "reason", "stage", "diagnostic"],
    interfaces.TaskPlan: ["example", "task", "kind", "relation", "target", "revisions", "claim", "prerequisites",
                          "artifacts", "tools", "engine", "gaps", "expected", "outputs", "folder", "network"],
    interfaces.Artifact: ["path", "sha256", "role", "coordinates", "origin"],
    interfaces.PreparedTarget: ["example", "task", "revision", "commit", "stage", "source", "artifacts", "classpath",
                                "toolchain", "failedStage", "diagnostic", "logs", "workdir", "blocker"],
    interfaces.ExecutionRecord: ["kind", "revision", "argv", "status", "exitCode", "seconds", "stdout", "stderr",
                                 "identities", "observations", "control", "directory", "record", "reason"],
    interfaces.Receipt: ["path", "claim", "attempt", "status", "execution"],
}


def plan():
    return interfaces.TaskPlan(
        example="999", task="fixed-security", kind="prove", relation="security", target="fixture.Gate#allowed",
        revisions=("fixed",), claim={"task": "fixed-security"}, prerequisites=(), artifacts=(),
        tools={"required": ["java"], "optional": []}, engine="native", gaps="strict", expected="established",
        outputs={"receipts": "receipts/fixed-security"}, folder="/nonexistent/999-fixture")


class InterfacesTest(unittest.TestCase):
    def test_signatures(self):
        for (module, name), params in SIGNATURES.items():
            self.assertEqual(list(inspect.signature(getattr(module, name)).parameters), params, f"{module.__name__}.{name}")

    def test_fields(self):
        for cls, names in FIELDS.items():
            actual = [f.name for f in dataclasses.fields(cls)]
            self.assertEqual(actual[: len(names)], names, cls.__name__)
            for extra in dataclasses.fields(cls)[len(names):]:
                self.assertFalse(extra.default is dataclasses.MISSING and extra.default_factory is dataclasses.MISSING,
                                 f"{cls.__name__}.{extra.name}: a field added after Phase 0 needs a default")

    def test_the_types_are_frozen_and_serialisable(self):
        p = plan()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            p.task = "other"
        json.dumps(p.as_dict())
        record = interfaces.ExecutionRecord(kind="jvm-control", revision="fixed", argv=("java", "-cp", "a.jar", "Driver"),
                                            status="killed", exitCode=None, seconds=1.5, stdout="out.txt",
                                            stderr="err.txt", identities={"jdk": "21"})
        self.assertIsNone(record.observations)  # raw: nothing was read from a killed process
        json.dumps(record.as_dict())

    def test_a_preparations_directory_and_blocker_are_fields_of_their_own(self):
        """Phase 5 step 1's request 7: the work directory and a failed preparation's blocker were carried by
        route.py's layout and by `source`, which claims are bound to; both are optional fields, None by default."""
        prepared = interfaces.PreparedTarget(example="999", task="fixed-security", revision="fixed",
                                             commit="fixture:gate/fixed", stage="source-locked", source={})
        self.assertEqual((prepared.workdir, prepared.blocker), (None, None))
        json.dumps(prepared.as_dict())


if __name__ == "__main__":
    unittest.main()

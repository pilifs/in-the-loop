#!/usr/bin/env python3
"""The case packets' constructed mutants, planned by the merged code (Phase 5 step 1's request 3 of
llm-dlc/loops/example-targets.md): each of the six deep packets declares its mutation control as workflow's W1
`mutant` revision, the `after` of a `mutation` pair over its base, with a replay task and a claim task of its own, and
runtime's simplematch slice keeps its mutant in its target.json. Offline: nothing is prepared or run."""

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))
from targets import interfaces, sidecar, workflow  # noqa: E402

# Each packet: the mutant's base, its patch, the task whose claim the mutant is meant to fail, and the mutant's own
# claim task. A CVE packet's mutant fails the fixed release's security property; a positive's fails its preservation
# (gate A4: "its nearby constructed mutation fails the same claim and control").
PACKETS = {
    "285": ("fixed-release", "controls/raw-method-fallback.patch", "fixed-security", "mutant-security"),
    "286": ("fixed-release", "controls/pattern-side-unnormalized.patch", "fixed-security", "mutant-security"),
    "287": ("fixed-release", "controls/char-count-guard.patch", "fixed-security", "mutant-security"),
    "305": ("after", "controls/status-200.patch", "preservation", "mutant-preservation"),
    "306": ("release-after", "controls/drop-prefix.patch", "preservation", "mutant-preservation"),
    "307": ("after", "controls/us-ascii.patch", "preservation", "mutant-preservation"),
}


def packet(number):
    folder = next(EXAMPLES.glob(f"{number}-*"))
    example = json.loads((folder / "example.json").read_text())
    return folder, example, sidecar.load(folder, example)


class PacketMutantTest(unittest.TestCase):
    def test_each_packet_declares_its_mutant_as_a_revision_in_a_mutation_pair(self):
        for number, (base, patch, _, _) in PACKETS.items():
            with self.subTest(number):
                folder, _, target = packet(number)
                m = target["history"]["revisions"]["mutant"]["mutant"]
                self.assertEqual((m["base"], m["patch"]), (base, patch))
                self.assertEqual(m["sha256"], workflow.file_sha256(folder / patch))
                self.assertIn({"name": "mutation", "kind": "mutation", "before": base, "after": "mutant"},
                              target["history"]["pairs"])
                mutations = [c for c in target["controls"] if c["kind"] == "mutation"]
                self.assertEqual([(c["path"], c.get("revision")) for c in mutations], [(patch, "mutant")])

    def test_each_packet_plans_its_mutant_replay(self):
        for number, (base, patch, _, _) in PACKETS.items():
            with self.subTest(number):
                folder, example, target = packet(number)
                p = workflow.plan_task(folder, example, target, "mutant-replay")
                self.assertIsInstance(p, interfaces.TaskPlan, p)
                self.assertEqual(p.revisions, (base, "mutant"))
                entry = p.artifacts[1]
                self.assertEqual(entry["mutant"]["base"]["revision"], base)
                self.assertEqual(entry["mutant"]["patch"]["path"], patch)
                self.assertNotIn("commit", entry)
                self.assertIn(patch, [c["path"] for c in p.claim["controls"]])
                replay = workflow.plan_task(folder, example, target, "replay")
                self.assertNotEqual(p.claim["key"], replay.claim["key"])

    def test_each_mutant_claim_task_states_its_reference_claim_on_the_mutants_artifact(self):
        for number, (_, _, reference, task) in PACKETS.items():
            with self.subTest(number):
                folder, example, target = packet(number)
                p = workflow.plan_task(folder, example, target, task)
                self.assertIsInstance(p, interfaces.TaskPlan, p)
                ref = workflow.plan_task(folder, example, target, reference)
                self.assertEqual(p.expected, "refuted")
                self.assertEqual(p.claim["file"], ref.claim["file"])
                self.assertEqual((p.kind, p.relation, p.target, p.engine, p.gaps),
                                 (ref.kind, ref.relation, ref.target, ref.engine, ref.gaps))
                self.assertIn("mutant", p.revisions)
                self.assertTrue(all("mutant" in a for a in p.artifacts if a["revision"] == "mutant"))
                # one property, so one source-level key; the claim is the mutant's own once bound to its artifact,
                # and an attempt's inputs already differ
                self.assertEqual(p.claim["key"], ref.claim["key"])
                self.assertNotEqual(workflow.inputs_key(p), workflow.inputs_key(ref))
                self.assertIn("mutant-replay", p.prerequisites)


class SimpleMatchMutantTest(unittest.TestCase):
    def test_the_simplematch_slice_keeps_its_mutant_in_its_sidecar(self):
        folder = HERE / "runtime_simplematch"
        self.assertFalse((folder / "mutation.json").exists())
        target = json.loads((folder / "target.json").read_text())
        sidecar.check(target, folder)
        p = workflow.plan_task(folder, {"id": "315"}, target, "mutant-replay")
        self.assertIsInstance(p, interfaces.TaskPlan, p)
        self.assertEqual(p.revisions, ("r5-3-19", "mutant"))
        self.assertEqual(p.artifacts[1]["mutant"]["patch"]["path"], "mutant/suffix-anywhere.patch")


if __name__ == "__main__":
    unittest.main()

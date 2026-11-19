"""Semantic translation and execution identity checks that do not need a checker process."""

from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
import checker_output
from targets import executions, interfaces, qualification, recipes, replay_candidate, workflow


class RecipesTest(unittest.TestCase):
    def plan(self, number, task):
        folder = next(TOOLS.parent.glob(number + "-*"))
        return workflow.plan_task(folder, json.loads((folder / "example.json").read_text()),
                                  json.loads((folder / "target.json").read_text()), task)

    def test_frozen_gradebook_claims_have_different_arguments_on_the_same_bytes(self):
        plans = [self.plan("198", name) for name in ("return-only", "full-state", "interior-state")]
        self.assertEqual(len({p.claim["key"] for p in plans}), 3)
        self.assertTrue(all(p.artifacts == plans[0].artifacts for p in plans))
        argv = [dict((a.flag, a.value) for a in recipes.translate(p).arguments) for p in plans]
        self.assertEqual(argv[0]["--assume"], argv[1]["--assume"])
        self.assertNotEqual(argv[1]["--assume"], argv[2]["--assume"])
        self.assertNotEqual(argv[0]["--observe"], argv[1]["--observe"])
        self.assertEqual(argv[1]["--observe"], argv[2]["--observe"])
        for part, value in [("models", [{"path": "m", "sha256": "a" * 64}]), ("observations", ["state"])]:
            failed = recipes.translate(replace(plans[0], claim={**plans[0].claim, part: value}))
            self.assertIsInstance(failed, interfaces.Unsupported)
            self.assertIn(part, failed.reason)

    def test_wire_versions_preserve_mixed_outcomes_and_refuse_unknown_formats(self):
        outcomes = [{"output": "a", "verdict": "verified"}, {"wire_version": 1, "output": "b", "verdict": "violation"}]
        self.assertEqual(checker_output.decode(json.dumps(outcomes), "prove"), (tuple(outcomes), None))
        for value in (False, 2, "1"):
            bad, why = checker_output.decode(json.dumps([{**outcomes[0], "wire_version": value}]), "prove")
            self.assertIsNone(bad)
            self.assertIn("wire version", why)

    def test_retry_links_budgets_and_refuses_another_source_claim(self):
        plan = self.plan("198", "full-state")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            first = executions.Execution.start(out, plan, 1)
            retry = executions.Execution.start(out, plan, 600, first.state["id"])
            self.assertNotEqual(first.state["id"], retry.state["id"])
            self.assertEqual(retry.state["retryOf"], first.state["id"])
            self.assertEqual(first.state["claimKey"], retry.state["claimKey"])
            self.assertEqual((first.state["budget"]["checkerSeconds"], retry.state["budget"]["checkerSeconds"]), (1, 600))
            other = executions.Execution.start(out, self.plan("198", "interior-state"), 600, first.state["id"])
            self.assertIsInstance(other, interfaces.Unsupported)

    def test_scalar_inputs_cannot_claim_the_identity_of_an_array(self):
        params = [{"name": "scores", "type": "int[]"}, {"name": "slot", "type": "int"}]
        inputs = [{**params[0], "value": [1]}, {**params[1], "value": {"same": 0}}]
        self.assertIn("alias", qualification.witness_problem(inputs, params, set(), [["scores", "slot"]], 3))
        expression, snapshot = replay_candidate.snapshot_assertion(r"result == \old(scores[slot])", inputs, ["scores", "slot"])
        self.assertEqual(expression, "result == originalArray0[slot]")
        self.assertIn("scores.clone()", snapshot[0])


if __name__ == "__main__":
    unittest.main()

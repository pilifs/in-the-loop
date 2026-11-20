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
from targets import executions, interfaces, qualification, recipes, replay_candidate, route, workflow


class RecipesTest(unittest.TestCase):
    def test_finite_observations_require_complete_inputs_and_the_selected_projection(self):
        from targets.finite_oracle import Table
        from targets.finite_check import envelope, read_rows
        self.assertEqual(envelope("n > -3 && (n == 0 || n == 1) && n <= 2", "n"), (-2, 2))
        self.assertEqual(envelope("n == -7", "n"), (-7, -7))
        for guard in ("n >= 0 && n < 5 || n == 9", "n >= 0 && (n < 3 || n == 7)", "n <= 2",
                      "n >= 5 && n < 2", "n >= 0 && n < 5000", "n >= 0 && n < 4 /*x*/"):
            with self.assertRaises(ValueError):
                envelope(guard, "n")
        with self.assertRaises(ValueError):
            read_rows("case 0\noutside\ncase 0\noutside\n", 0, 1, [], False)
        table = Table(next(TOOLS.parent.glob("314-*/controls/table.json")))
        rows = []
        for case in table.cases.values():
            state = 0
            for cell in case["expected"]["state"]:
                state = state * 3 + ["x", None, "A"].index(cell)
            rows.append({**case, "direct": case["expected"],
                         "adapter": {"state": state, "exception": int(case["expected"]["exception"] is not None)}})
        self.assertFalse(table.problems(rows))
        rows[11]["adapter"]["state"] += 1
        self.assertEqual(table.correspondence(rows, "copy.Projection#state(I)I"), {"cases": 40, "disagreements": 1})
        self.assertEqual(table.correspondence(rows, "copy.Projection#thrown(I)I")["disagreements"], 0)
        for malformed in (rows[:-1], rows + rows[:1], [{**rows[0], "id": False}, *rows[1:]],
                          [{**rows[0], "input": {"source": []}}, *rows[1:]]):
            with self.assertRaises(ValueError):
                table.problems(malformed)

    def test_invoice_preparation_rejects_the_other_order_with_identical_client_bytes(self):
        from targets import runtime, workflow_ingest
        plan = self.plan("312", "invoice-values")
        prepared = {}
        for rev, entry in zip(plan.revisions, plan.artifacts):
            lock = runtime.lock(plan, rev)
            paths = ["client.jar", *[f"lib/{root}.jar" for root in entry["fixtureClasspath"]]]
            artifacts = tuple(interfaces.Artifact(path, workflow.canonical_digest(path),
                              "original" if path == "client.jar" else "dependency") for path in paths)
            prepared[rev] = replace(lock, stage="artifacts-ready", artifacts=artifacts, classpath=tuple(paths))
        workflow_ingest.bound_revisions(plan, prepared)
        before, after = plan.revisions
        prepared[before] = replace(prepared[after], revision=before)
        with self.assertRaisesRegex(workflow_ingest.Refused, "different dependency order"):
            workflow_ingest.bound_revisions(plan, prepared)

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
        inputs = [{"name": "q", "type": "int", "value": 1}]
        pair = {"verdict": "violation", "target": "RegressionPair#agree", "assert": "result", "counterexample": {"inputs": inputs}}
        outcome = {"verdict": "violation", "pair": pair}
        self.assertEqual(checker_output.solver_candidate(outcome)["inputs"], inputs)
        self.assertFalse(checker_output.equivalence_counterexamples(outcome))
        replay = {"inputs": inputs, "reproduced": True, "sides": {"two": {"values": [2, None]}, "three": {"values": [3, None]}}}
        result = checker_output.equivalence_counterexamples(outcome, replay=[replay], revisions=["two", "three"])
        self.assertEqual((result[0]["contract"], result[0]["actual"]), ("[2, null]", "[3, null]"))
        self.assertIsNone(checker_output.solver_candidate({**outcome, "pair": {**pair, "target": "Other#check"}}))

    def test_observed_states_bind_each_revision_and_the_executed_model(self):
        plan = self.plan("310", "same-day-observed")
        original = self.plan("310", "same-day")
        self.assertNotEqual(original.claim["key"], plan.claim["key"])
        self.assertEqual(original.artifacts, plan.artifacts)
        recipe = recipes.translate(plan)
        name, state = next(iter(plan.claim["observedInitializers"].items()))
        model, = plan.claim["namedModels"]
        flags = {(a.flag, a.value) for a in recipe.arguments}
        self.assertTrue({("--model", model), ("--observed-initializer", name)} <= flags)
        self.assertEqual(recipe.describe()["observedInitializerStates"], {name: state})
        self.assertIsInstance(recipes.translate(replace(plan, engine="jbmc")), interfaces.Unsupported)
        classes = {"parent": {name: "a" * 64}, "fix": {name: "b" * 64}}
        ids = ["jdk-model:" + model, f"observed-initializer:before.{name}:{'a' * 64}:{state}",
               f"observed-initializer:{name}:{'b' * 64}:{state}"]
        def problem(actual):
            outcome = {"stated": {"assumptions": [{"id": i, "kind": "library", "basis": "engine"} for i in actual]}}
            return qualification.library_bindings_problem(plan, outcome, classes)
        self.assertIsNone(problem(ids))
        for changed in [ids[1:], ids[:-1], ids + ["jdk-model:other.Model"],
                        [*ids[:2], ids[2].replace("b" * 64, "c" * 64)],
                        [*ids[:2], ids[2].replace(state, "0" * 64)]]:
            self.assertIsNotNone(problem(changed))

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

            # A collector on another checkout can leave the only copy in its job's outputs.
            folder = out / "examples/198-gradebook"
            fresh = replace(plan, folder=str(folder))
            receipt_dir = Path(fresh.outputs["receipts"])
            first.stage("artifacts-ready", bindingId="same-original-bytes")
            journal = Path("examples") / folder.name / receipt_dir / "executions" / first.state["id"] / "attempt.json"
            job = out / "verification/results/failed-job"
            archive = job / "outputs" / journal
            archive.parent.mkdir(parents=True)
            archive.write_bytes((first.directory / "attempt.json").read_bytes())
            (job / "result.json").write_text(json.dumps({"outputs": [{"path": journal.as_posix(), "sha256": workflow.file_sha256(archive)}]}))
            linked = executions.Execution.start(folder / receipt_dir, fresh, 90, first.state["id"])
            self.assertEqual((linked.state["retryOf"], linked.state["retryBinding"]), (first.state["id"], "same-original-bytes"))
            self.assertFalse((out / journal).exists())
            archive.write_bytes(archive.read_bytes() + b" ")
            self.assertIsInstance(executions.Execution.start(folder / receipt_dir, fresh, 90, first.state["id"]), interfaces.Unsupported)

            ids = [first.state["id"], retry.state["id"]]
            self.assertEqual(route.batch_tasks(["198", "--tasks", "a,b", "--retry-of", ",".join(ids)]), list(zip(["a", "b"], ids)))
            from unittest.mock import patch
            import build
            with patch.object(build, "run_task", side_effect=[0, 1]) as run:
                self.assertEqual(build.main(["198", "--tasks", "return-only,full-state", "--checker-seconds", "120",
                                             "--retry-of", ",".join(ids)]), 1)
            self.assertEqual([(c.kwargs["retry_of"], c.kwargs["checker_seconds"]) for c in run.call_args_list],
                             [(execution_id, 120) for execution_id in ids])
            self.assertIs(run.call_args_list[0].kwargs["shared"], run.call_args_list[1].kwargs["shared"])
            for invalid in [ids[0], ids[0] + ",bad"]:
                with self.assertRaises(ValueError):
                    route.batch_tasks(["198", "--tasks", "a,b", "--retry-of", invalid])

    def test_scalar_inputs_cannot_claim_the_identity_of_an_array(self):
        params = [{"name": "scores", "type": "int[]"}, {"name": "slot", "type": "int"}]
        inputs = [{**params[0], "value": [1]}, {**params[1], "value": {"same": 0}}]
        self.assertIn("alias", qualification.witness_problem(inputs, params, set(), [["scores", "slot"]], 3))
        expression, snapshot = replay_candidate.snapshot_assertion(r"result == \old(scores[slot])", inputs, ["scores", "slot"])
        self.assertEqual(expression, "result == originalArray0[slot]")
        self.assertIn("scores.clone()", snapshot[0])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests for examples/tools/preflight.py, what each example named lacks before a run takes it, and for
examples/tools/observe.py's two reports. Run: python3 llm-dlc/tools/test_preflight.py
The examples are copies of the made-up target fixture that test_changes.py builds in a temporary checkout, which is
why these tests are here beside it and not beside the two tools."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "examples" / "tools"))
import changes  # noqa: E402
import observe  # noqa: E402  examples/tools/observe.py
import preflight  # noqa: E402  examples/tools/preflight.py
from test_changes import PROOFS, Checkout  # noqa: E402


class Preflight(Checkout):
    """Examples that are already prepared, checked before a run takes them."""

    def check(self, *arguments):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            status = preflight.main(["--root", str(self.root), *arguments])
        found = json.loads(out.getvalue())
        return status, found, {e["id"]: e for e in found["examples"]}

    def test_prepared_examples_pass_in_the_order_given_and_a_decided_one_is_left_out_of_what_is_to_prove(self):
        self.example("901")
        self.example("900", answers={**PROOFS, "regex-probe": "refuted"})
        self.example("902", answers=PROOFS)
        status, found, _ = self.check("902", "900", "901", "902")
        self.assertEqual((status, found["ok"], found["toProve"], found["decided"]), (0, True, ["902", "901"], ["900"]))
        self.assertNotIn("toReview", found)  # the review of claims went with the proof run: nothing here reports one

    def test_a_missing_artifact_and_a_fault_in_the_form_are_told_apart(self):
        self.example("900", replays=False)
        (self.example("901") / "target.json").write_text("{ not JSON")
        self.example("902")
        status, found, by = self.check("900", "901", "902")
        self.assertEqual((status, found["ok"], found["toProve"]), (1, False, ["902"]))
        self.assertTrue(by["900"]["artifacts"] and not by["900"]["form"], by["900"])
        self.assertTrue(by["901"]["form"] and not by["901"]["artifacts"], by["901"])
        self.assertTrue(by["902"]["ok"])

    def test_an_example_that_is_not_there_is_said_apart_since_nothing_can_put_it_right(self):
        self.example("900")
        status, found, by = self.check("900", "950")
        self.assertEqual((status, found["absent"], by["950"]["ok"]), (2, ["950"], False))

    def test_a_catalog_entry_is_to_set_up_and_one_still_lacking_after_its_setup_is_left_out(self):
        self.example("900")
        self.catalog_entry("901")
        self.example("902", replays=False)
        status, found, by = self.check("900", "901")
        self.assertEqual((status, found["toSetUp"], found["toRepair"], found["toProve"]), (1, ["901"], [], ["900"]))
        self.assertEqual([g["kind"] for g in by["901"]["catalogue"]], [changes.CATALOGUE])
        status, found, _ = self.check("--after-setup", "901", "900", "901")
        self.assertEqual((status, found["ok"], found["leftOut"], found["toSetUp"], found["toProve"]),
                         (0, True, ["901"], [], ["900"]), "the others go on without it")
        status, found, _ = self.check("--after-setup", "901", "900", "901", "902")
        self.assertEqual((status, found["leftOut"], found["toRepair"]), (1, ["901"], ["902"]),
                         "an example that was prepared and lacks something still stops the run")
        self.assertEqual(self.check("--after-setup", "950", "900", "950")[0], 2, "one that is not there is never left out")

    def test_a_proof_task_that_doesnt_record_how_it_is_invoked_is_to_classify_without_stopping_the_run(self):
        folder = self.example("900")
        self.example("901")
        status, found, by = self.check("900", "901")
        self.assertEqual((status, found["ok"], found["toClassify"]), (0, True, ["900", "901"]))
        self.assertIn("fixed-security", [g["task"] for g in by["900"]["invocation"]])
        target = json.loads((folder / "target.json").read_text())
        for t in target["tasks"]:
            if t["kind"] != "replay":
                t["invocation"] = {"how": "route", "checked": "2026-11-16", "evidence": "build.py --plan: it plans"}
        last = next(t for t in target["tasks"] if t["id"] == "fixed-security")
        last["invocation"]["how"] = "gap"
        (folder / "target.json").write_text(json.dumps(target))
        status, found, by = self.check("900", "901")
        self.assertEqual([g["task"] for g in by["900"]["invocation"]], [last["id"]],
                         "a gap is recorded as an observed blocker of the task")
        target["handoff"]["blockers"].append({"kind": "verifier-interface", "observed": True, "task": last["id"],
                                              "summary": "made up: the verifier can't be given it"})
        (folder / "target.json").write_text(json.dumps(target))
        status, found, by = self.check("900", "901")
        self.assertEqual((by["900"]["invocation"], found["toClassify"]), ([], ["901"]))

    def test_an_example_json_that_breaks_its_schema_is_a_fault_in_the_form(self):
        folder = self.example("900")
        (self.root / "examples/schema").mkdir()
        (self.root / "examples/schema/example.schema.json").write_text((REPO / "examples/schema/example.schema.json").read_text())
        self.assertEqual(self.check("900")[0], 0, "the fixture's example.json is valid")
        example = json.loads((folder / "example.json").read_text())
        del example["title"]
        (folder / "example.json").write_text(json.dumps(example))
        status, _, by = self.check("900")
        self.assertEqual(status, 1)
        self.assertTrue(any("title" in g["what"] for g in by["900"]["form"]), by["900"])

    def test_an_example_without_a_sidecar_passes_with_a_note(self):
        folder = self.example("900")
        (folder / "target.json").unlink()
        example = json.loads((folder / "example.json").read_text())
        example.pop("target", None)
        (folder / "example.json").write_text(json.dumps(example))
        status, found, by = self.check("900")
        self.assertEqual((status, found["toProve"], by["900"]["state"]), (0, ["900"], "unknown"))
        self.assertIn("no target sidecar", by["900"]["note"])

    def test_a_caller_that_keeps_a_record_of_reviews_has_each_examples_answer_kept_with_it(self):
        self.example("900")
        self.catalog_entry("901")
        found = preflight.preflight(self.root, ["900", "901"], review=lambda row: f"asked of {row['id']}")
        self.assertEqual([e["review"] for e in found["examples"]], ["asked of 900", "asked of 901"])
        self.assertNotIn("review", preflight.preflight(self.root, ["900"])["examples"][0])


class TheReports(unittest.TestCase):
    def test_a_file_that_is_no_startup_claim_report_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = Path(tmp) / "report.json"
            record.write_text(json.dumps({"schema": "something-else/v1"}))
            said = io.StringIO()
            with self.assertRaises(SystemExit) as stopped, contextlib.redirect_stderr(said):
                observe.main(["startup-facts", str(record)])
        self.assertEqual(stopped.exception.code, 2)
        self.assertIn("expected a startup claim report", said.getvalue())


if __name__ == "__main__":
    unittest.main()

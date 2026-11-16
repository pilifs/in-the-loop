#!/usr/bin/env python3
"""Tests for changes.py: the state it derives for each example a checkout holds for /prove-java-change, the order
it lists them in, and what it leaves for a proof loop. Run: python3 llm-dlc/tools/test_changes.py
The examples are copies of the made-up target fixture (examples/tools/targets/fixtures), with receipts written by
hand in the shape ingestion leaves; nothing is run and nothing of this checkout's own examples is read."""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import changes

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "examples/tools/targets/fixtures"
sys.path.insert(0, changes.TOOLS)
from targets import sidecar, workflow  # noqa: E402

PROOFS = {"vulnerable-security": "refuted", "fixed-security": "established", "preservation": "established",
          "mutant-security": "refuted", "regex-probe": "unresolved"}


class Checkout(unittest.TestCase):
    """A made-up checkout: a root with examples/, and copies of the fixture under the numbers a test asks for."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        (self.root / "examples").mkdir()

    def example(self, number, replays=True, answers=None, provenance=None):
        folder = self.root / "examples" / f"{number}-made-up-change"
        shutil.copytree(FIXTURES, folder, ignore=shutil.ignore_patterns("__pycache__"))
        example = json.loads((folder / "example.json").read_text())
        example["id"] = number
        if provenance:
            example["provenance"] = provenance
        (folder / "example.json").write_text(json.dumps(example))
        if replays:
            for task in ("replay", "mutant-replay"):
                self.record(folder, task)
        for task, status in (answers or {}).items():
            self.record(folder, task, status=status)
        return folder

    def record(self, folder, task, status=None, attempt="1"):
        example = json.loads((folder / "example.json").read_text())
        plan = workflow.plan_task(folder, example, sidecar.load(folder, example), task)
        where = folder / "receipts" / task / attempt
        where.mkdir(parents=True)
        (where / "result.json").write_text(json.dumps({
            "format": 2,
            "claim": {"id": "0" * 16, "target": {"task": task, "dependencies": [
                {"revision": r, "position": 0, "role": "original", "sha256": "0" * 64} for r in plan.revisions]}},
            "attempt": {"id": attempt, "execution": {"status": "completed", "exitCode": 0, "reason": None}},
            "conclusion": {"status": status, "expectation": "yes"}}))
        (where / "plan.json").write_text(json.dumps(workflow.plan_record(plan)))

    def rows(self, *numbers):
        return {r["id"]: r for r in changes.listing(self.root, list(numbers))["examples"]}

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = changes.main(["--root", str(self.root), *argv])
        return status, out.getvalue()


class StateTest(Checkout):
    def test_an_example_whose_scaffold_is_incomplete_is_unprepared_and_says_why(self):
        self.example("900", replays=False)
        row = self.rows()["900"]
        self.assertEqual(row["state"], "unprepared")
        self.assertTrue(any("oracleValidated" in w for w in row["why"]), row["why"])
        self.assertEqual(changes.listing(self.root, [])["pending"], [])

    def test_a_complete_scaffold_with_no_answer_is_prepared(self):
        self.example("900")
        row = self.rows()["900"]
        self.assertEqual(row["state"], "prepared", row.get("why"))
        self.assertEqual(set(row["claims"]), set(PROOFS), "one entry per proof task, none for a replay")
        self.assertEqual({c["status"] for c in row["claims"].values()}, {None})
        self.assertEqual(row["claims"]["fixed-security"]["expected"], "established")

    def test_every_claim_established_or_refuted_is_decided(self):
        self.example("900", answers={**PROOFS, "regex-probe": "refuted"})
        self.assertEqual(self.rows()["900"]["state"], "decided")
        self.assertEqual(changes.listing(self.root, [])["pending"], [])

    def test_a_claim_left_open_keeps_the_example_to_prove(self):
        self.example("900", answers=PROOFS)  # regex-probe: unresolved
        row = self.rows()["900"]
        self.assertEqual(row["state"], "prepared")
        self.assertEqual(row["claims"]["regex-probe"]["status"], "unresolved")
        self.assertEqual(changes.listing(self.root, [])["pending"], ["900"])

    def test_an_answer_other_than_the_expected_one_still_decides(self):
        self.example("900", answers={task: "refuted" for task in PROOFS})
        self.assertEqual(self.rows()["900"]["state"], "decided", "a refuted claim is a finding, not something left")

    def test_an_example_without_a_sidecar_is_unknown_and_counts_as_to_prove(self):
        folder = self.example("900")
        example = json.loads((folder / "example.json").read_text())
        del example["target"]
        (folder / "example.json").write_text(json.dumps(example))
        self.assertEqual(self.rows()["900"]["state"], "unknown")
        self.assertEqual(changes.listing(self.root, [])["pending"], ["900"])

    def test_a_folder_that_cant_be_read_is_unprepared_and_the_list_goes_on(self):
        broken = self.example("900")
        (broken / "target.json").write_text("{not json")
        unreadable = self.example("901")
        (unreadable / "example.json").write_text("{not json")
        self.example("902")
        rows = self.rows()
        self.assertEqual([rows[n]["state"] for n in ("900", "901", "902")], ["unprepared", "unprepared", "prepared"])
        self.assertIn("SidecarError", rows["900"]["why"][0])

    def test_a_row_says_where_the_change_is_and_what_asked_for_it(self):
        self.example("900", provenance="/prove-java-change on 2026-01-02: made-up/repo#12, the gate still denies")
        row = self.rows()["900"]
        self.assertEqual(row["repository"], "https://github.com/pilifs/in-the-loop")
        self.assertTrue(row["source"].startswith("https://github.com/"))
        self.assertIn("made-up/repo#12", row["provenance"])
        self.assertEqual(row["revisions"], {}, "the fixture's revisions are local sources, with no commit to report")

    def test_it_only_reads(self):
        folder = self.example("900", answers=PROOFS)
        before = {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in folder.rglob("*") if p.is_file()}
        self.rows()
        self.assertEqual({p: (p.stat().st_size, p.stat().st_mtime_ns) for p in folder.rglob("*") if p.is_file()}, before)


class OrderTest(Checkout):
    def test_without_numbers_it_lists_900_to_999_by_number(self):
        for number in ("902", "900", "950"):
            self.example(number)
        self.example("285")
        found = changes.listing(self.root, [])
        self.assertEqual([r["id"] for r in found["examples"]], ["900", "902", "950"])
        self.assertEqual(found["pending"], ["900", "902", "950"])

    def test_named_examples_keep_the_order_given_and_a_missing_one_is_unprepared(self):
        self.example("901")
        self.example("285")
        found = changes.listing(self.root, ["901", "777", "285"])
        self.assertEqual([r["id"] for r in found["examples"]], ["901", "777", "285"])
        self.assertEqual((found["pending"], found["unprepared"]), (["901", "285"], ["777"]))
        self.assertIn("no example 777", found["examples"][1]["why"][0])

    def test_pending_leaves_out_what_is_decided_or_not_prepared(self):
        self.example("900", answers={**PROOFS, "regex-probe": "refuted"})
        self.example("901")
        self.example("902", replays=False)
        self.example("903", answers=PROOFS)
        self.assertEqual(self.run_main("--pending"), (0, "901 903\n"))


class CommandTest(Checkout):
    def test_the_table_ends_with_what_is_left_to_prove(self):
        self.example("900")
        self.example("901", replays=False)
        status, out = self.run_main()
        self.assertEqual(status, 0)
        self.assertIn("900  prepared", out)
        self.assertIn("to prove, in order: 900", out)
        self.assertIn("not prepared: 901", out)

    def test_an_empty_checkout_says_so_and_pending_prints_an_empty_line(self):
        self.assertIn("no example numbered 900 to 999", self.run_main()[1])
        self.assertEqual(self.run_main("--pending"), (0, "\n"))
        self.assertEqual(json.loads(self.run_main("--json")[1]), {"examples": [], "pending": [], "unprepared": []})

    def test_something_that_is_not_a_number_is_refused(self):
        with self.assertRaises(SystemExit) as refused, contextlib.redirect_stderr(io.StringIO()):
            changes.main(["--root", str(self.root), "90x"])
        self.assertEqual(refused.exception.code, 2)


if __name__ == "__main__":
    unittest.main()

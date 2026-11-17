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
import test_accept  # noqa: E402  (the fixture of an answer beside the route)

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

    def catalog_entry(self, number):
        """The fixture as a catalog entry: its sidecar with no task, and nothing that names one."""
        folder = self.example(number, replays=False)
        target = json.loads((folder / "target.json").read_text())
        target["tasks"] = []
        target["handoff"]["blockers"] = [b for b in target["handoff"]["blockers"] if "task" not in b]
        (folder / "target.json").write_text(json.dumps(target))
        return folder

    def beside(self, folder, task, answer, job, **how):
        """An answer given beside the route, as a sidecar records it, with what the pipeline and the example's
        driver leave: the job, its result and the collected outcome of that answer (examples/tools/test_accept.py's
        `beside`, where `how` is described: no result, a failed job, another example's, another outcome)."""
        return test_accept.beside(self.root, folder, task, answer, job, **how)

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

    def test_what_an_unprepared_example_lacks_is_told_by_kind(self):
        self.example("900", replays=False)                      # no oracle run: an artifact
        broken = self.example("901")
        (broken / "target.json").write_text("{ not JSON")       # a sidecar that does not load: its form
        rows = self.rows("900", "901", "902")
        self.assertEqual({g["kind"] for g in rows["900"]["gaps"]}, {changes.ARTIFACTS})
        self.assertTrue(all(g["task"] for g in rows["900"]["gaps"]), rows["900"]["gaps"])
        self.assertTrue(any("oracleValidated" in g["what"] for g in rows["900"]["gaps"]), rows["900"]["gaps"])
        self.assertEqual([g["kind"] for g in rows["901"]["gaps"]], [changes.FORM])
        self.assertEqual([g["kind"] for g in rows["902"]["gaps"]], [changes.ABSENT])
        self.example("903")
        self.assertNotIn("gaps", self.rows("903")["903"], "a prepared example lacks nothing")

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

    def test_a_claim_proved_beside_the_route_stays_open_and_the_row_carries_the_examples_own_word(self):
        folder = self.example("900", answers=PROOFS)  # regex-probe: unresolved by the route
        example = json.loads((folder / "example.json").read_text())
        example["verdictLabel"] = "made-up: the probe claim decided through an adapter entry, beside the route"
        (folder / "example.json").write_text(json.dumps(example))
        row = self.rows()["900"]
        self.assertEqual((row["state"], row["claims"]["regex-probe"]["status"]), ("prepared", "unresolved"))
        self.assertIn("beside the route", row["verdict"])
        self.assertIn("next", row, "the hand-off's next step, when the sidecar has one")
        self.assertIn("verdict: made-up: the probe claim decided", self.run_main()[1])

    def test_an_answer_given_beside_the_route_counts_while_its_job_passed_and_names_the_example(self):
        folder = self.example("900", answers=PROOFS)  # regex-probe: unresolved by the route
        self.assertEqual(self.rows()["900"]["claims"]["regex-probe"]["blocked"], ["java-semantics"],
                         "an open claim says which observed gaps of the verifier its task stops at")
        self.beside(folder, "regex-probe", "refuted", "20260102-000001-example-900-the-probe-beside")
        row = self.rows()["900"]
        claim = row["claims"]["regex-probe"]
        self.assertEqual((row["state"], claim["status"], claim["beside"]["confirmed"]), ("decided", "unresolved", True))
        self.assertNotIn("blocked", claim, "a claim with its answer stops nowhere")
        self.assertEqual(changes.listing(self.root, [])["pending"], [])
        self.assertIn("1 refuted beside the route", self.run_main()[1])

    def test_an_answer_beside_the_route_does_not_count_when_the_jobs_outcome_gives_another(self):
        """A passed job that names the example once supported either answer. Now the outcome decides."""
        folder = self.example("900", answers=PROOFS)
        self.beside(folder, "regex-probe", "established", "20260102-000001-example-900-the-probe-beside", outcome="refuted")
        row = self.rows()["900"]
        claim = row["claims"]["regex-probe"]
        self.assertEqual((row["state"], claim["beside"]["confirmed"], claim["beside"]["actual"]), ("prepared", False, "refuted"))
        self.assertIn("conclusion: the outcome's verdict is violation (refuted), and the answer recorded is established", claim["beside"]["why"])
        self.assertIsNone(changes.answer(claim))
        self.assertEqual(changes.listing(self.root, [])["pending"], ["900"])

    def test_an_answer_beside_the_route_does_not_count_without_a_passed_job_of_this_example(self):
        cases = {"900": ({"status": "failed"}, "ended failed"), "901": ({"status": None}, "no result of job"),
                 "902": ({"names": ["950"]}, "does not name example 902")}
        for number, (how, why) in cases.items():
            self.beside(self.example(number, answers=PROOFS), "regex-probe", "refuted",
                        f"20260102-00000{number[2]}-example-{number}-the-probe", **how)
        rows = self.rows()
        for number, (_, why) in cases.items():
            claim = rows[number]["claims"]["regex-probe"]
            self.assertEqual((rows[number]["state"], claim["beside"]["confirmed"]), ("prepared", False), number)
            self.assertIn(why, claim["beside"]["why"])
            self.assertEqual(claim["blocked"], ["java-semantics"])
        self.assertEqual(changes.listing(self.root, [])["pending"], ["900", "901", "902"])

    def test_the_routes_answer_outranks_one_given_beside_it(self):
        folder = self.example("900", answers={**PROOFS, "regex-probe": "established"})
        self.beside(folder, "regex-probe", "refuted", "20260102-000001-example-900-the-probe-beside")
        self.assertEqual(changes.answer(self.rows()["900"]["claims"]["regex-probe"]), "established")

    def test_a_catalog_entry_is_told_apart_from_an_example_that_lacks_something(self):
        self.catalog_entry("900")
        self.example("901", replays=False)
        found = changes.listing(self.root, [])
        row = found["examples"][0]
        self.assertEqual((row["state"], [g["kind"] for g in row["gaps"]]), ("catalogued", [changes.CATALOGUE]))
        self.assertEqual((found["pending"], found["unprepared"], found["catalogued"]), ([], ["901"], ["900"]))
        self.assertIn("catalog entries, to set up first: 900", self.run_main()[1])

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
        self.assertEqual(json.loads(self.run_main("--json")[1]), {"examples": [], "pending": [], "unprepared": [], "catalogued": []})

    def test_something_that_is_not_a_number_is_refused(self):
        with self.assertRaises(SystemExit) as refused, contextlib.redirect_stderr(io.StringIO()):
            changes.main(["--root", str(self.root), "90x"])
        self.assertEqual(refused.exception.code, 2)


if __name__ == "__main__":
    unittest.main()

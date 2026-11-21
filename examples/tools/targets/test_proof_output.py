#!/usr/bin/env python3
"""One archived checker row, and three copies of it changed in one place each, through every reader of proof output
as it is called in use: the ordinary decoder and ingestion, the live native-selector check, the validation of an
archived selector record, the benchmark's run and the solver comparison (llm-dlc/loops/lib-architecture-fast-follow.md,
part 1).

The row is the first established case of example 359's `contents-fix` selector record: wire version 1, exit 0, one
of 2,865 admitted and checked cases. Before the readers shared one (lib/python/jvmcontract_io.py), three of them
answered differently for the same bytes: the ordinary decoder refused wire version 999 where the selector and the
benchmark read it as established and correct; a `complete` of the string "false" was established through Python's
truthiness; and a process that exited with 2 beside a verified payload was scored correct by the benchmark.

    python3 examples/tools/targets/test_proof_output.py
"""

import copy
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1]
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
import checker_output  # noqa: E402
from targets import case_pack, interfaces, native_selectors, runtime, workflow, workflow_ingest  # noqa: E402

RECEIPT = "records/native-selectors/fix/20261121T110735Z-f1bc304b"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def changed(answer, **how):
    """The row with one thing changed: `version`, or `complete`."""
    row = copy.deepcopy(answer)
    if "version" in how:
        row["wire_version"] = how["version"]
    if "complete" in how:
        row["stated"]["bounds"]["complete"] = how["complete"]
    return row


class Table(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = next(TOOLS.parent.glob("359-*"))
        cls.plan = workflow.plan_task(cls.folder, json.loads((cls.folder / "example.json").read_text()),
                                      json.loads((cls.folder / "target.json").read_text()), "contents-fix")
        cls.receipt = cls.folder / RECEIPT
        cls.doc = json.loads((cls.receipt / "tasks/contents-fix/result.json").read_text())
        cls.row = next(r for r in cls.doc["checked"] if r["status"] == "established")
        cls.raw = case_pack.read(cls.receipt, cls.row["raw"])
        (cls.answer,) = json.loads(cls.raw)
        # The table: (label, the row as printed, the process's exit).
        cls.rows = (
            ("the original v1 row, exit 0", cls.answer, 0),
            ("only wire_version changed to 999", changed(cls.answer, version=999), 0),
            ('only stated.bounds.complete changed from true to "false"', changed(cls.answer, complete="false"), 0),
            ("the original row, process exit changed to 2", cls.answer, 2),
        )

    def test_the_row_is_what_the_table_says_it_starts_from(self):
        self.assertEqual((self.answer["wire_version"], self.row["exit"], self.answer["verdict"]), (1, 0, "verified"))
        self.assertIs(self.answer["stated"]["bounds"]["complete"], True)
        self.assertEqual((len(self.doc["admitted"]), len(self.doc["checked"])), (2865, 2865))

    def test_the_ordinary_decoder_and_ingestion(self):
        expected = (
            ("completed", "verified", None),
            ("invalid-output", None, "unsupported checker wire version 999"),
            ("invalid-output", None, "stated.bounds.complete of another type"),
            ("tool-error", None, "exit code 2"),
        )
        for (label, answer, code), (status, verdict, reason) in zip(self.rows, expected):
            with self.subTest(label), tempfile.TemporaryDirectory() as scratch:
                text = json.dumps([answer])
                (Path(scratch) / "stdout").write_text(text)
                # The run decodes what the process printed (runtime.run_verifier), and ingestion reads the record.
                observations, problem = runtime._outcomes(text, runtime.VERIFIER_KINDS[self.plan.kind])
                if "999" in label:
                    self.assertEqual((observations, problem), (None, "unsupported checker wire version 999"))
                else:
                    self.assertEqual(len(observations), 1)
                record = interfaces.ExecutionRecord(kind="verifier", revision=None, argv=("jvmcontract", "prove"), status="exited",
                                                    exitCode=code, seconds=0.1, stdout="stdout", stderr="stderr", identities={},
                                                    observations=observations, directory=scratch)
                fields, _, _ = workflow_ingest.verifier_outcome(self.plan, {}, [record])
                self.assertEqual((fields["execution"]["status"], fields["verdict"]), (status, verdict), fields["execution"])
                if reason:
                    self.assertIn(reason, fields["execution"]["reason"])

    def test_the_live_native_selector_check(self):
        expected = (
            ("established", None, 1),
            ("open", "unsupported checker wire version 999", None),
            ("open", "stated.bounds.complete of another type", None),
            ("open", "exit code 2", None),
        )
        for (label, answer, code), (status, blocker, version) in zip(self.rows, expected):
            with self.subTest(label), tempfile.TemporaryDirectory() as scratch:
                def ran(argv, cwd, out, err, timeout, env=None, usage=None):
                    Path(out).write_text(json.dumps([answer]))
                    return "exited", code, 0.01
                with mock.patch.object(runtime, "_run_one", ran), mock.patch.object(runtime, "_verifier_env", lambda jdk: {}):
                    row = native_selectors.native_case("jvmcontract", {}, [], Path(scratch) / "compiled", self.row["selector"],
                                                       self.doc["bounds"], 30, Path(scratch) / "work/case", Path(scratch) / "case")
                self.assertEqual((row["status"], row.get("wireVersion")), (status, version), row)
                if blocker:
                    self.assertIn(blocker, row["firstBlocker"])
                else:
                    self.assertNotIn("firstBlocker", row)
                    self.assertEqual(row["assumptions"], self.row["assumptions"])

    def archived(self, scratch, answer, code):
        """The record copied whole into `scratch`, with the first established case's retained output and exit as
        given (and the digest the record keeps of that output, so that only what the output says is in question)."""
        target = Path(scratch)
        for name in ("calls", "tasks/contents-fix"):
            shutil.copytree(self.receipt / name, target / name)
        doc = copy.deepcopy(self.doc)
        row = next(r for r in doc["checked"] if r["selector"] == self.row["selector"])
        loose = target / row["raw"]   # read before the pack its siblings are in (case_pack.read)
        loose.parent.mkdir(parents=True)
        loose.write_bytes(self.raw if answer is self.answer else json.dumps([answer]).encode())
        row.update(exit=code, rawSha256=hashlib.sha256(loose.read_bytes()).hexdigest())
        result = target / "tasks/contents-fix/result.json"
        result.write_text(json.dumps(doc))
        return result

    def test_the_validation_of_an_archived_selector_record(self):
        expected = (None, "unsupported checker wire version 999", "does not follow from the retained checker record",
                    "does not follow from the retained checker record")
        for (label, answer, code), refusal in zip(self.rows, expected):
            with self.subTest(label), tempfile.TemporaryDirectory() as scratch:
                result = self.archived(scratch, answer, code)
                if refusal:
                    with self.assertRaisesRegex(ValueError, refusal):
                        native_selectors.validate_result(self.folder, self.plan, result)
                else:
                    validated = native_selectors.validate_result(self.folder, self.plan, result)
                    self.assertEqual((validated["status"], validated["admitted"], validated["checked"]), ("established", 2865, 2865))

    def test_the_record_as_it_is_kept_still_qualifies_every_case(self):
        kept = native_selectors.validate_result(self.folder, self.plan, self.receipt / "tasks/contents-fix/result.json")
        self.assertEqual((kept["status"], kept["admitted"], kept["checked"], kept["firstBlocker"]), ("established", 2865, 2865, None))

    def measured(self, answer, code):
        return {"exit": code, "killed": False, "stdout": json.dumps([answer]), "stderr": "", "seconds": 0.1, "cpuSeconds": 0.1, "peakMB": 20.0}

    BENCHMARK = (("correct", None, "verified"), ("unsupported", "unsupported wire version", "none"),
                 ("unsupported", "malformed outcome", "none"), ("unsupported", "tool failure", "none"))

    def test_the_benchmark_run_with_expected_verified(self):
        run = module("benchmark_run_table", REPO / "lib/benchmark/run.py")
        case = {"id": "table/selector-row", "kind": "property", "target": self.answer["target"], "assert": "result == 1", "expected": "verified"}
        options = SimpleNamespace(jvmcontract="jvmcontract", jbmc="jbmc", timeout=30)
        for (label, answer, code), (scored, reason, verdict) in zip(self.rows, self.BENCHMARK):
            with self.subTest(label), tempfile.TemporaryDirectory() as scratch:
                with mock.patch.object(run, "measure", lambda cmd, limit: self.measured(answer, code)):
                    record = run.run_one(case, "native", "strict", None, {"conformance": Path(scratch)}, Path(scratch), options)
                self.assertEqual((record["class"], record.get("reason"), record["verdict"], record["exit"]), (scored, reason, verdict, code))
                self.assertIsNone(record["witness"])
                if scored == "unsupported" and "999" not in label:   # what was printed stays, for diagnosis, as no verdict
                    self.assertEqual(record["printed"], {"verdict": "verified", "wireVersion": 1})

    def test_the_solver_comparison_reads_through_the_benchmark(self):
        compare = module("solver_compare_table", REPO / "lib/solvers/compare.py")
        run = compare.benchmark()
        case = {"id": "table/selector-row", "kind": "property", "target": self.answer["target"], "assert": "result == 1", "expected": "verified"}
        options = SimpleNamespace(jvmcontract="jvmcontract", timeout=30)
        for (label, answer, code), (scored, reason, verdict) in zip(self.rows, self.BENCHMARK):
            with self.subTest(label), tempfile.TemporaryDirectory() as scratch:
                with mock.patch.object(run, "measure", lambda cmd, limit: self.measured(answer, code)):
                    record = compare.check(run, case, "cadical", {"conformance": Path(scratch)}, Path(scratch) / "work", None, options)
                self.assertEqual((record["class"], record.get("reason"), record["verdict"]), (scored, reason, verdict))


class Distinctions(unittest.TestCase):
    """What the readers must keep apart once they share one (the brief's acceptance): the same reading whichever
    consumer asks."""

    METHOD = "verificationselectors.Calls#p6()"
    BOUNDS = {"unwind": 96, "maxArrayLength": 96}

    def row(self, **fields):
        row = {"wire_version": 1, "target": self.METHOD, "assert": "result == 1", "verdict": "verified", "proof": "all paths", "output": "",
               "stated": {"gap_mode": "strict", "checker": {"engine": "native"}, "bounds": {"unwind": 96, "complete": True},
                          "domain": {"parameters": []}, "observations": {"exceptions": "none may be thrown"},
                          "vacuity": {"status": "non-vacuous"}},
               "search": {"properties": 1, "max_array_length": 96}}
        row.update(fields)
        return row

    def status(self, row, code):
        return native_selectors.disposition(row, self.METHOD, self.BOUNDS, code)[0]

    def test_a_selector_row_is_established_only_by_fields_of_the_contracts_types(self):
        self.assertEqual(self.status(self.row(), 0), "established")
        untagged = self.row()
        del untagged["wire_version"]   # version 0, from before the field: the same fields, read the same
        self.assertEqual(self.status(untagged, 0), "established")
        for change in ({"wire_version": 2}, {"wire_version": "1"}, {"proof": None}, {"proof": ""}, {"verdict": "Verified"}):
            self.assertEqual(self.status(self.row(**change), 0), "open", change)
        for path, value in ((("stated", "bounds", "complete"), "true"), (("stated", "bounds", "complete"), 1), (("stated", "bounds", "complete"), None),
                            (("stated", "vacuity", "status"), "unknown"), (("stated", "vacuity"), None), (("stated", "bounds", "unwind"), "96"),
                            (("search", "properties"), True), (("search", "max_array_length"), 96.0)):
            row = self.row()
            at = row
            for key in path[:-1]:
                at = at[key]
            at[path[-1]] = value
            self.assertEqual(self.status(row, 0), "open", (path, value))
        self.assertEqual(self.status(self.row(), 1), "open")   # verified at exit 1: no status follows

    def test_a_refutation_needs_a_replay_whose_reproduced_is_the_boolean_true(self):
        refuted = self.row(verdict="violation", proof=None, counterexample={"inputs": []}, replay={"by": "jvm", "reproduced": True})
        self.assertEqual(self.status(refuted, 1), "refuted")
        self.assertEqual(self.status({**refuted, "replay": {"by": "interpreter", "reproduced": True}}, 1), "needs-jvm-replay")
        for reproduced in ("true", 1, False, None):
            self.assertEqual(self.status({**refuted, "replay": {"by": "jvm", "reproduced": reproduced}}, 1), "open", reproduced)
        self.assertEqual(self.status(refuted, 0), "open")

    def test_a_mixed_properties_run_keeps_each_rows_result_in_order_at_exit_1(self):
        rows = [{"wire_version": 1, "verdict": v, "output": f"{n}\n"} for n, v in enumerate(("verified", "violation", "verified", "unverifiable"))]
        decoded, ended = checker_output.wire.read(json.dumps(rows), "prove", 1)
        self.assertTrue(ended.ok)
        self.assertEqual([o["verdict"] for o in decoded.outcomes], ["verified", "violation", "verified", "unverifiable"])
        self.assertEqual(checker_output.property_headline([o["verdict"] for o in decoded.outcomes]), "violation")
        self.assertEqual(checker_output.wire.read(json.dumps(rows), "prove", 0)[1].status, "contradictory-exit")

    def test_the_benchmark_scores_a_valid_refutation_at_exit_1_and_nothing_beside_a_wrong_exit_or_a_kill(self):
        run = module("benchmark_run_scores", REPO / "lib/benchmark/run.py")
        case = {"id": "c", "kind": "property", "expected": "violation"}

        def scored(rows, code, killed=False):
            stdout = json.dumps(rows)
            measured = {"exit": code, "killed": killed, "stdout": stdout, "stderr": "", "seconds": 0.1, "cpuSeconds": 0.1, "peakMB": 1.0}
            record = run.classify(case, run.outcome_of(case, stdout), measured)
            return record["class"], record.get("reason")

        violation = {"wire_version": 1, "verdict": "violation", "output": ""}
        verified = {"wire_version": 1, "verdict": "verified", "output": ""}
        self.assertEqual(scored([violation], 1), ("correct", None))
        self.assertEqual(scored([{"verdict": "violation", "output": ""}], 1), ("correct", None))   # untagged, version 0
        self.assertEqual(scored([verified], 0), ("false-success", None))
        self.assertEqual(scored([violation], 0), ("unsupported", "contradictory exit"))
        self.assertEqual(scored([verified], 1), ("unsupported", "contradictory exit"))
        self.assertEqual(scored([violation], 2), ("unsupported", "tool failure"))
        self.assertEqual(scored([violation], -9, killed=True), ("unsupported", "out of time"))
        self.assertEqual(scored([violation, verified], 1), ("unsupported", "not one outcome"))   # one property, its one row
        assuming = {**verified, "search": {"gaps": [{"id": "jdk:A", "treatment": "assumed"}]}}
        self.assertEqual(scored([assuming], 0), ("false-success-assuming", None))
        hit = {**violation, "reuse": {"kind": "exact", "key": "sha256:ab", "from": "x"}}   # a cache hit, with no fresh search
        self.assertEqual(scored([hit], 1), ("correct", None))
        self.assertIs(checker_output.wire.facts(hit)["fresh"], False)


if __name__ == "__main__":
    unittest.main()

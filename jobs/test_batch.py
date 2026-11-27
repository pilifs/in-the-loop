#!/usr/bin/env python3
"""Tests of jobs/batch.py: a manifest's rows as ordinary jobs, and the map from rows to jobs.

  python3 jobs/test_batch.py

In process, against the pipeline's own functions and a folder of its own for the repository. The fixture is the
49 rows of jobs/fixtures/batch-49.json: one row that needs another, one expected to fail by assertion, and one
that is resubmitted (jobs/test_fanout.py runs them).
"""

import copy
import hashlib
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["VERIFY_MACHINE_CONFIG"] = ""
os.environ.setdefault("ITL_ORIGINALS_OFF", "1")
import batch  # noqa: E402
import pipeline  # noqa: E402

FIXTURE = json.loads((HERE / "fixtures/batch-49.json").read_text())


class Batches(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(mock.patch.object(pipeline, "ROOT", self.root))
        self.manifest = copy.deepcopy(FIXTURE)

    def files(self):
        """Every file under the repository's folder with the digest of its bytes (but the locks)."""
        return {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.root.rglob("*")) if p.is_file() and not p.name.endswith(".lock")}

    def job_files(self):
        return [name for name in self.files() if name.startswith("verification/jobs/")]

    def row(self, name):
        return next(r for r in self.manifest["rows"] if r["row"] == name)


class AManifestBecomesOrdinaryJobs(Batches):
    def test_forty_nine_rows_are_forty_nine_valid_jobs_with_ids_the_manifest_alone_decides(self):
        jobs = batch.expand(self.manifest, pipeline)
        self.assertEqual(len({job["id"] for job in jobs}), 49)
        self.assertEqual([job["id"] for job in jobs], [job["id"] for job in batch.expand(copy.deepcopy(FIXTURE), pipeline)])
        by_row = {job["batch"]["row"]: job for job in jobs}
        self.assertTrue(all(pipeline.validate(job, "job.schema.json") == [] for job in jobs))
        self.assertTrue(by_row["R01"]["id"].startswith("20261128-090000-fixture-49-r01-"))
        self.assertEqual(by_row["R01"]["id"].rsplit("-", 1)[1], by_row["R01"]["batch"]["work"][:8])
        self.assertEqual((by_row["R01"]["case"], by_row["R01"]["steps"][0]["run"], by_row["R01"]["outputs"]),
                         ("R01", "python3 tools/case.py R01 plain", ["out/R01.txt"]))
        self.assertEqual(by_row["R14"]["needs"], [{"job": by_row["R13"]["id"]}])       # a row named, a job id written
        self.assertEqual(by_row["R20"]["steps"][0]["promises"]["tests"]["failing"], ["fails_before_the_fix"])
        # Who submits is what the manifest says, and nothing of the process that happens to run it.
        self.assertEqual(by_row["R01"]["submitted"], {"by": "the fan-out tests", "at": "2026-11-28T09:00:00+00:00"})

    def test_everything_wrong_with_a_batch_is_said_at_once_and_nothing_is_written(self):
        self.manifest["rows"] += [{"row": "R01"}, {"row": "R50", "override": {"needs": [{"row": "R99"}]}},
                                  {"row": "R51", "override": {"needs": [{"row": "R52"}]}}, {"row": "R52", "override": {"needs": [{"row": "R51"}]}},
                                  {"row": "R53", "override": {"purpose": "celebrate"}}]
        self.manifest["template"]["steps"][0]["run"] += " {flavour}"
        with self.assertRaises(batch.Problem) as raised:
            batch.submit(self.manifest, pipeline)
        said = " | ".join(raised.exception.problems)
        for expected in ("row 'R01' is there 2 times", "row R50: needs row 'R99', which the batch does not have",
                         "its prerequisites come back to itself (R51 -> R52 -> R51)", "row R02: no variable 'flavour'",
                         "row R53: purpose: 'celebrate' is not one of"):
            self.assertIn(expected, said)
        self.assertEqual(self.files(), {})
        del self.manifest["created"]
        with self.assertRaises(batch.Problem) as raised:
            batch.submit(self.manifest, pipeline)
        self.assertIn("no `created` time", str(raised.exception))


class SubmittingItAgain(Batches):
    def test_a_submission_killed_half_way_and_then_run_twice_more_gives_exactly_49_jobs(self):
        written, real = [], pipeline.write_json

        def killed_after_twenty(path, document):
            if len(written) == 20:
                raise KeyboardInterrupt("the submission is killed here")
            written.append(path)
            real(path, document)

        with mock.patch.object(pipeline, "write_json", killed_after_twenty), self.assertRaises(KeyboardInterrupt):
            batch.submit(self.manifest, pipeline)
        self.assertEqual(len(self.job_files()), 20)
        self.assertIsNone(batch.read_map(self.root, "fixture-49"))            # the map is written last
        said = batch.submit(self.manifest, pipeline)
        self.assertEqual(([r["did"] for r in said["rows"]].count("there"), [r["did"] for r in said["rows"]].count("written")), (20, 29))
        after = self.files()
        self.assertEqual((len(self.job_files()), len(set(said["jobs"]))), (49, 49))
        again = batch.submit(self.manifest, pipeline)
        self.assertEqual({r["did"] for r in again["rows"]}, {"there"})
        self.assertEqual(self.files(), after)                                 # to the byte
        document = batch.read_map(self.root, "fixture-49")
        self.assertEqual((len(document["rows"]), document["rows"]["R07"]["history"]),
                         (49, [{"job": document["rows"]["R07"]["current"], "work": document["rows"]["R07"]["work"], "why": "submitted"}]))

    def test_two_submissions_at_once_end_with_the_same_files_as_one(self):
        alone = Path(self.enterContext(tempfile.TemporaryDirectory()))
        with mock.patch.object(pipeline, "ROOT", alone):
            batch.submit(copy.deepcopy(FIXTURE), pipeline)
        expected = {p.relative_to(alone).as_posix(): p.read_bytes() for p in alone.rglob("*.json")}
        errors = []

        def one():
            try:
                batch.submit(copy.deepcopy(FIXTURE), pipeline)
            except Exception as e:  # noqa: BLE001
                errors.append(e)
        threads = [threading.Thread(target=one) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual({p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*.json")}, expected)

    def test_a_manifest_with_the_batchs_name_and_another_time_is_another_batch_and_is_refused(self):
        batch.submit(self.manifest, pipeline)
        self.manifest["created"] = "2026-11-29T09:00:00+00:00"
        with self.assertRaises(batch.Problem) as raised:
            batch.submit(self.manifest, pipeline)
        self.assertIn("batch fixture-49 was created 2026-11-28T09:00:00+00:00", str(raised.exception))
        self.assertEqual(len(self.job_files()), 49)


class WorkThatChangedAndWorkThatWasTriedAgain(Batches):
    def test_other_inputs_or_another_revision_are_other_work_and_an_estimate_is_not(self):
        first = batch.submit(self.manifest, pipeline)
        old = dict(zip([r["row"] for r in first["rows"]], first["jobs"]))
        self.manifest["template"]["resources"]["memory"] = "512M"             # an estimate: the same work
        self.manifest["template"]["title"] = "Case {row}, retitled"
        self.assertEqual({r["did"] for r in batch.submit(self.manifest, pipeline)["rows"]}, {"there"})
        self.row("R40")["vars"]["kind"] = "other-input"                       # another input
        self.row("R41")["override"] = {"source": {"revision": "0123abcd"}}    # another revision
        said = {r["row"]: r for r in batch.submit(self.manifest, pipeline)["rows"]}
        self.assertEqual(sorted(r for r, did in said.items() if did["did"] != "there"), ["R40", "R41"])
        self.assertEqual((said["R40"]["did"], said["R40"]["supersedes"]), ("superseded", old["R40"]))
        self.assertNotEqual(said["R40"]["job"], old["R40"])
        self.assertEqual(len(self.job_files()), 51)                           # the two old jobs stay, as they were committed
        new = json.loads((pipeline.layout.find_job(self.root, said["R40"]["job"])).read_text())
        self.assertEqual((new["supersedes"], new["steps"][0]["run"]), (old["R40"], "python3 tools/case.py R40 other-input"))
        history = batch.read_map(self.root, "fixture-49")["rows"]["R40"]["history"]
        self.assertEqual([(h["job"], h["why"]) for h in history], [(old["R40"], "submitted"), (said["R40"]["job"], "the row's work changed")])
        self.assertNotEqual(history[0]["work"], history[1]["work"])

    def test_a_resubmission_with_other_resources_is_the_same_work_and_the_map_follows_it(self):
        first = batch.submit(self.manifest, pipeline)
        old_id = first["jobs"][12]
        old = json.loads(pipeline.layout.find_job(self.root, old_id).read_text())
        self.assertEqual(old["batch"]["row"], "R13")
        new_id = "20261128-100000-case-r13-of-the-fixture"
        self.assertTrue(batch.follow(self.root, pipeline, old, new_id, "resubmitted with other resources"))
        entry = batch.read_map(self.root, "fixture-49")["rows"]["R13"]
        self.assertEqual((entry["current"], [h["why"] for h in entry["history"]], len({h["work"] for h in entry["history"]})),
                         (new_id, ["submitted", "resubmitted with other resources"], 1))
        # Submitting the manifest again leaves the row with the job it was resubmitted as.
        said = {r["row"]: r for r in batch.submit(self.manifest, pipeline)["rows"]}
        self.assertEqual((said["R13"]["did"], said["R13"]["job"]), ("there", new_id))
        self.assertFalse(batch.follow(self.root, pipeline, old, "20261128-110000-again", "a second time, from the old job"))   # it is not the row's current job any more
        self.assertFalse(batch.follow(self.root, pipeline, {"id": "20261128-120000-not-a-batchs"}, "x", "y"))

    def test_a_row_the_manifest_no_longer_has_keeps_its_job_and_is_named(self):
        batch.submit(self.manifest, pipeline)
        self.manifest["rows"] = [r for r in self.manifest["rows"] if r["row"] != "R49"]
        said = batch.submit(self.manifest, pipeline)
        document = batch.read_map(self.root, "fixture-49")
        self.assertEqual((said["withdrawn"], document["withdrawn"], len(document["rows"]), len(said["jobs"]), len(self.job_files())),
                         (["R49"], ["R49"], 49, 48, 49))


class WhatBecameOfEveryRow(Batches):
    def test_a_row_is_its_current_job_with_the_jobs_it_had_and_one_nobody_can_find_is_missing(self):
        first = batch.submit(self.manifest, pipeline)
        document = batch.read_map(self.root, "fixture-49")
        jobs = {job_id: {"id": job_id, "state": "collected", "why": None, "attempts": [{}], "result": {"status": "passed", "fulfillment": None}}
                for job_id in first["jobs"]}
        jobs[first["jobs"][12]].update(state="finished", result={"status": "failed", "fulfillment": {"state": "unfulfilled"}})
        jobs[first["jobs"][13]].update(state="blocked", why="its prerequisite failed", result=None, attempts=[])
        jobs[first["jobs"][14]].update(state="running", result=None)
        del jobs[first["jobs"][48]]
        seen = batch.view(document, jobs)
        by_row = {row["row"]: row for row in seen["rows"]}
        self.assertEqual((seen["schema"], seen["totals"]["unit"], seen["totals"]["of"]), ("itl-job-batch-view/v1", "rows", 49))
        self.assertEqual(seen["totals"]["byState"], {"collected": 45, "finished": 1, "blocked": 1, "running": 1, "missing": 1})
        self.assertEqual((seen["totals"]["byStatus"], seen["totals"]["withResult"]), ({"passed": 45, "failed": 1}, 46))
        self.assertEqual((seen["settled"], seen["unsettled"]), (False, ["R15", "R49"]))
        self.assertEqual((by_row["R13"]["status"], by_row["R13"]["fulfillment"], by_row["R14"]["why"], by_row["R14"]["attempts"]),
                         ("failed", "unfulfilled", "its prerequisite failed", 0))
        self.assertEqual(by_row["R49"]["state"], "missing")
        jobs[first["jobs"][14]].update(state="finished", result={"status": "passed"})
        jobs[first["jobs"][48]] = {"id": first["jobs"][48], "state": "unschedulable", "why": "needs 64 GiB", "result": None}
        self.assertTrue(batch.view(document, jobs)["settled"])               # nothing is left that waiting would change


if __name__ == "__main__":
    unittest.main()

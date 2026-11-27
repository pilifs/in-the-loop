#!/usr/bin/env python3
"""The 49-row batch end to end, through `jobs/pipeline.py`: submitted, interrupted and submitted again, run,
watched as a batch, collected, reported, and one row resubmitted.

  python3 jobs/test_fanout.py

The fixture (jobs/fixtures/batch-49.json) has one row that needs another (R14 needs R13), one that fails until it
is given more room and is resubmitted (R13), and one whose test is expected to fail by assertion (R20).
jobs/test_batch.py tests the map's rules in process.
"""

import json
import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["VERIFY_MACHINE_CONFIG"] = ""
os.environ.setdefault("ITL_ORIGINALS_OFF", "1")
import test_formats  # noqa: E402
from test_formats import Repo  # noqa: E402

del test_formats   # its tests are its own: only the helper is used here

CASE = '''\
import os, pathlib, sys
row, kind = sys.argv[1:3]
if kind == "needs-room" and int(os.environ["VERIFY_MEMORY_LIMIT_MB"]) < 500:
    sys.exit("not enough room for this case")
pathlib.Path("out").mkdir(exist_ok=True)
pathlib.Path(f"out/{row}.txt").write_text(row + "\\n")
if kind == "regression":   # the test this case is about fails by assertion on this revision, as it should
    pathlib.Path("reports").mkdir(exist_ok=True)
    pathlib.Path(f"reports/{row}.xml").write_text(
        '<testsuite name="Regression" tests="2"><testcase classname="Regression" name="holds"/>'
        '<testcase classname="Regression" name="fails_before_the_fix"><failure message="expected 2, was 1"/></testcase></testsuite>')
    sys.exit(1)
'''


class FortyNineRows(unittest.TestCase):
    def setUp(self):
        # Room for every row at once: the test is of the batch, not of the budget.
        self.repo = Repo(workers=49, cpus=49, memory="24G", memory_floor="0")
        self.addCleanup(self.repo.close)
        (self.repo.dir / "tools").mkdir()
        (self.repo.dir / "tools/case.py").write_text(CASE)
        (self.repo.dir / "batch.json").write_text((HERE / "fixtures/batch-49.json").read_text())
        self.repo.commit("the cases' tool and the manifest")

    def job_files(self):
        return sorted(p.stem for p in (self.repo.dir / "verification/jobs").rglob("*.json"))

    def batch(self, *args):
        return json.loads(self.repo.pipeline("batch", "fixture-49", "--json", "--rev", "HEAD", *args).stdout)

    def test_interrupted_submitted_twice_run_watched_collected_reported_and_one_row_resubmitted(self):
        repo = self.repo
        first = json.loads(repo.pipeline("submit", "--manifest", "batch.json", "--json").stdout)
        ids = first["jobs"]
        self.assertEqual((len(ids), len(set(ids)), self.job_files()), (49, 49, sorted(ids)))
        # As a submission killed half way leaves it: some of the jobs' files, and no map.
        for job_id in ids[20:]:
            repo.job_path(job_id).unlink()
        (repo.dir / "verification/batches/fixture-49.json").unlink()
        second = repo.pipeline("submit", "--manifest", "batch.json").stdout
        self.assertIn("batch fixture-49: 49 row(s), 49 job(s)", second)
        self.assertIn("29 written", second)
        self.assertIn("20 already there with the same work", second)
        third = json.loads(repo.pipeline("submit", "--manifest", "batch.json", "--json").stdout)
        self.assertEqual(({row["did"] for row in third["rows"]}, third["jobs"], self.job_files()), ({"there"}, ids, sorted(ids)))
        by_row = dict(zip([row["row"] for row in third["rows"]], ids))
        repo.commit("the batch")

        # Run. The batch is watched by name, and the queue-wide wait goes on working beside it.
        repo.pipeline("run", "--rev", "HEAD")
        watched = json.loads(repo.pipeline("wait", "--batch", "fixture-49", "--json", "--rev", "HEAD", "--timeout", "0").stdout)
        self.assertEqual((watched["schema"], watched["outcome"], watched["totals"]["of"]), ("itl-job-batch-wait/v1", "settled", 49))
        self.assertEqual((watched["totals"]["byState"], watched["totals"]["byStatus"]),
                         ({"finished": 48, "blocked": 1}, {"passed": 47, "failed": 1}))
        self.assertEqual(json.loads(repo.pipeline("wait", "--json", "--timeout", "0").stdout)["outcome"], "finished")
        rows = {row["row"]: row for row in watched["rows"]}
        self.assertEqual((rows["R13"]["status"], rows["R14"]["state"]), ("failed", "blocked"))
        self.assertIn(f"{by_row['R13']} ended failed: resubmit it", rows["R14"]["why"])
        self.assertEqual(rows["R20"]["status"], "passed")      # its test failed by assertion, as the job said it would

        # Collected and reported: every independent row is there, and the one that never ran is in the batch's view.
        collected = json.loads(repo.pipeline("collect", "--json").stdout)
        self.assertEqual(len(collected["collected"]), 48)
        report = json.loads(repo.pipeline("report", "--format", "json").stdout)
        reported = {r["id"]: r["status"] for r in report["results"]}
        self.assertEqual(sum(1 for i in ids if reported.get(i) == "passed"), 47)
        self.assertEqual(reported[by_row["R13"]], "failed")
        self.assertNotIn(by_row["R14"], reported)
        regression, = json.loads(repo.pipeline("view", "--rev", "HEAD", by_row["R20"]).stdout)["jobs"]
        self.assertEqual((regression["result"]["fulfillment"]["state"], regression["result"]["execution"]["status"]), ("fulfilled", "passed"))
        repo.commit("results")
        seen = self.batch()
        self.assertEqual((seen["totals"]["byState"], seen["settled"]), ({"collected": 48, "blocked": 1}, True))

        # The row that failed is resubmitted with more room: the same work, another job, and the map follows it.
        said = repo.pipeline("resubmit", by_row["R13"], "--memory", "512M").stdout
        self.assertIn("Row R13 of batch fixture-49 is this job now", said)
        retry = said.split("verification/jobs/")[1].split(".json")[0].rsplit("/", 1)[-1]
        repo.commit("the resubmission")
        waiting = json.loads(repo.pipeline("wait", "--batch", "fixture-49", "--json", "--rev", "HEAD", "--timeout", "0", check=False).stdout)
        self.assertEqual((waiting["outcome"], waiting["unsettled"]), ("timeout", ["R13", "R14"]))
        repo.pipeline("run", "--rev", "HEAD")
        repo.pipeline("collect")
        repo.commit("the rest")
        seen = self.batch()
        rows = {row["row"]: row for row in seen["rows"]}
        self.assertEqual((seen["totals"]["byState"], seen["totals"]["byStatus"], seen["settled"]), ({"collected": 49}, {"passed": 49}, True))
        # A resubmission is a second job of the row with the same work; a rerun would have been a second attempt of one job.
        history = rows["R13"]["history"]
        self.assertEqual(([(h["job"], h["status"]) for h in history], len({h["work"] for h in history}), rows["R13"]["attempts"]),
                         ([(by_row["R13"], "failed"), (retry, "passed")], 1, 1))
        self.assertEqual((rows["R14"]["job"], rows["R14"]["status"]), (by_row["R14"], "passed"))   # its own file never changed
        self.assertEqual(len(self.job_files()), 50)
        # Submitting the manifest once more changes nothing: the row stays with the job it was resubmitted as.
        again = json.loads(repo.pipeline("submit", "--manifest", "batch.json", "--json").stdout)
        self.assertEqual(({row["did"] for row in again["rows"]}, again["jobs"][12], len(self.job_files())), ({"there"}, retry, 50))

    def test_a_batch_that_is_not_valid_writes_nothing_and_says_everything(self):
        manifest = json.loads((self.repo.dir / "batch.json").read_text())
        manifest["rows"][3]["override"] = {"needs": [{"row": "R77"}]}
        manifest["rows"][5]["override"] = {"purpose": "celebrate"}
        (self.repo.dir / "batch.json").write_text(json.dumps(manifest))
        refused = self.repo.pipeline("submit", "--manifest", "batch.json", check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("not a valid batch, and nothing of it was written", refused.stderr)
        self.assertIn("row R06: purpose", refused.stderr)
        self.assertIn("row R04: needs row 'R77'", refused.stderr)
        self.assertEqual(self.job_files(), [])
        self.assertFalse((self.repo.dir / "verification/batches/fixture-49.json").exists())


if __name__ == "__main__":
    unittest.main()

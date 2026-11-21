#!/usr/bin/env python3
"""Tests of verification/capture.py: what the runner and the collector hand to the private archive, and that the
pipeline's own files and verdicts are what they were. Each test runs the pipeline in a throwaway git repository
(test_pipeline.Repo) with a spool and a store on disk of its own.

  python3 verification/test_capture.py
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pipeline  # noqa: E402
import capture  # noqa: E402
from test_pipeline import Repo  # noqa: E402
sys.path.append(str(HERE.parent / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.insert(0, str(HERE.parent / "llm-dlc/tools"))
import artifacts  # noqa: E402


class CaptureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="capture-test-"))
        self.env = {"ITL_ARTIFACTS": str(HERE.parent / "llm-dlc/tools/artifacts.py"), "ITL_ORIGINALS_HOME": str(self.tmp / "home"),
                    "ITL_ORIGINALS_CACHE": str(self.tmp / "cache"), "ITL_ORIGINALS_STORE": f"dir:{self.tmp / 'store'}",
                    "ITL_ORIGINALS_RESERVE": "0", "ITL_ORIGINALS_OFF": ""}
        self.old = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        os.environ.pop("ITL_ORIGINALS_OFF")  # test_pipeline and the test runner switch capture off: here it is on
        self.repo = self.new_repo()

    def new_repo(self, **runner):
        repo = Repo(**runner)
        shutil.copy(HERE / "capture.py", repo.dir / "verification/capture.py")
        repo.commit("with capture")
        return repo

    def tearDown(self):
        for k, v in self.old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.repo.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def archive(self):
        archive = artifacts.Archive(self.tmp / "home")
        self.addCleanup(archive.close)
        return archive

    def restored(self, occurrence, name="out"):
        """An occurrence's files as a machine with only the store reads them."""
        archive = self.archive()
        archive.upload()
        out = self.tmp / name
        artifacts.Reader(cache=self.tmp / f"cache-{name}").fetch(occurrence, out, flat=True)
        return {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()} if out.is_dir() else out.read_bytes()

    def test_the_whole_log_is_sealed_before_it_is_cut_and_the_result_names_it(self):
        self.repo.close()
        self.repo = self.new_repo(log_max_bytes="4K")
        job_id = self.repo.submit("Talk a lot", "--run", "seq 1 20000; echo VERIFICATION SUCCESSFUL")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, False)
        self.assertEqual(pipeline.validate(r, "result.schema.json"), [])
        log = r["steps"][0]["log"]
        self.assertTrue(log["truncated"])  # the pipeline's own copy is cut, as before
        self.assertEqual(r["originals"]["attempt"], 1)
        logs = self.restored(r["originals"]["occurrences"]["logs"])
        whole = logs[log["path"].split("/", 1)[1]]
        self.assertEqual((len(whole), pipeline.sha256(whole)), (log["bytes"], log["sha256"]))
        self.assertIn(b"\n10000\n", whole)  # the middle the result left out
        self.assertNotIn("\n10000\n", (self.repo.dir / "verification/.state/results" / job_id / log["path"]).read_text())
        listed = {d["kind"]: d for d in artifacts.Reader(cache=self.tmp / "c2").find(job=job_id)}
        self.assertEqual(sorted(listed), ["job-logs", "job-result"])
        self.assertEqual(listed["job-logs"]["source"]["commit"], r["sourceCommit"])
        self.assertEqual(json.loads(self.restored(listed["job-result"]["id"], "result")), r)

    def test_a_failed_job_keeps_its_outputs_its_diff_and_what_its_work_directory_gained(self):
        (self.repo.dir / "tracked.txt").write_text("committed\n")
        (self.repo.dir / "changed.txt").write_text("before\n")
        job_id = self.repo.submit("Fail after writing", "--output", "out", "--output", "never-made.txt", "--run",
                                  "mkdir -p out/cases/p0 scratch; echo x > out/cases/p0/native.json; : > out/cases/p0/stderr; "
                                  "echo after > changed.txt; head -c 3000 /dev/urandom > scratch/core.bin; exit 3")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, False)
        self.assertEqual(r["status"], "failed")
        made = r["originals"]["occurrences"]
        self.assertEqual(sorted(made), ["diff", "logs", "outputs", "workdir"])
        self.assertEqual(self.restored(made["outputs"], "outputs"), {"out/cases/p0/native.json": b"x\n", "out/cases/p0/stderr": b""})
        work = self.restored(made["workdir"], "work")
        self.assertEqual(sorted(work), ["changed.txt", "out/cases/p0/native.json", "out/cases/p0/stderr", "scratch/core.bin"])
        self.assertEqual(work["changed.txt"], b"after\n")  # tracked.txt and the rest of the commit are in git already
        self.assertEqual(len(work["scratch/core.bin"]), 3000)
        outputs = self.archive().rows(id=made["outputs"])[0]
        self.assertEqual((outputs["status"], outputs["absent"]), ("partial", ["never-made.txt"]))
        self.assertIn(b"native.json", self.restored(made["diff"], "diff"))

    def test_collect_seals_the_result_it_writes_and_the_one_it_replaces(self):
        (self.repo.dir / "o.txt").write_text("before\n")
        job_id = self.repo.submit("Conflict", "--output", "o.txt", "--run", "echo after > o.txt")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        (self.repo.dir / "o.txt").write_text("someone else's edit\n")
        old = self.repo.dir / "verification/results" / job_id
        old.mkdir(parents=True)
        (old / "result.json").write_text('{"earlier": "collect"}\n')
        self.repo.pipeline("collect")
        r = self.repo.result(job_id)
        self.assertEqual(r["collected"]["conflicts"], ["o.txt"])
        self.assertFalse((self.repo.dir / "verification/.state/results" / job_id).exists())  # sealed, so released
        rows = [x for x in self.archive().rows(job=job_id) if x["kind"] == "job-result"]
        stages = {x["notes"]["stage"]: x for x in rows}
        self.assertEqual(sorted(stages), ["a collected result that a later collect replaced", "as collected", "as the runner wrote it"])
        self.assertEqual(stages["as collected"]["conflicts"], ["o.txt"])
        self.assertEqual(self.restored(stages["a collected result that a later collect replaced"]["id"], "old"),
                         {"result.json": b'{"earlier": "collect"}\n'})
        self.assertEqual(json.loads(self.restored(stages["as collected"]["id"], "new")), r)

    def test_a_result_staged_by_a_runner_without_capture_is_sealed_at_collect(self):
        job_id = self.repo.submit("Old runner", "--output", "a.txt", "--run", "echo a > a.txt; seq 1 5")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD", env={"ITL_ORIGINALS_OFF": "1"})
        self.assertNotIn("originals", self.repo.result(job_id, False))
        self.repo.pipeline("collect")
        kinds = sorted((x["kind"], x["notes"].get("stage") or x["notes"].get("why")) for x in self.archive().rows(job=job_id))
        self.assertEqual([k for k, _ in kinds], ["job-diff", "job-logs", "job-outputs", "job-result", "job-result"])
        self.assertTrue(any("sealed at collect" in (why or "") for _, why in kinds))

    def test_a_capture_that_fails_fails_no_job_and_no_collect_and_deletes_nothing_unsealed(self):
        job_id = self.repo.submit("Disk full", "--output", "a.txt", "--run", "echo a > a.txt")
        self.repo.commit("job")
        full = {"ITL_ORIGINALS_RESERVE": str(1 << 60)}
        ran = self.repo.pipeline("run", "--rev", "HEAD", env=full)
        r = self.repo.result(job_id, False)
        self.assertEqual(r["status"], "passed")
        self.assertNotIn("originals", r)
        self.assertIn("warn  capture:", ran.stderr)
        collected = self.repo.pipeline("collect", env=full)
        self.assertEqual(self.repo.result(job_id)["collected"]["applied"], ["a.txt"])
        self.assertIn("set aside, not deleted", collected.stderr)
        aside = list((self.repo.dir / "verification/.state/uncaptured").iterdir())
        self.assertEqual(len(aside), 1)
        self.assertTrue((aside[0] / "outputs/a.txt").exists())
        self.assertIn("nothing to collect", self.repo.pipeline("collect").stdout)
        self.assertIn("SpoolFull", (self.repo.dir / "verification/.state/capture.log").read_text())
        self.assertEqual(self.archive().rows(), [])

    def test_an_attempt_that_never_finished_is_sealed_before_its_run_directory_is_reused(self):
        state, job = self.repo.dir / "verification/.state", {"id": "20261121-000000-made-up"}
        run_dir = state / "runs" / job["id"]
        (run_dir / "logs").mkdir(parents=True)
        (run_dir / "logs/1-prove.log").write_text("killed half way\n")
        attempt = capture.begin(self.repo.dir, state, job, self.repo.git("rev-parse", "HEAD"), run_dir, state / "work" / job["id"])
        self.assertEqual(attempt, 2)  # the first was the one that never finished
        rows = self.archive().rows(job=job["id"])
        self.assertEqual([(x["kind"], x["status"], x["attempt"]) for x in rows], [("job-logs", "partial", 1)])
        self.assertIn("did not finish", rows[0]["notes"]["why"])
        self.assertEqual(self.restored(rows[0]["id"]), {"1-prove.log": b"killed half way\n"})
        (run_dir / capture.MARKER).write_text("{}")  # a sealed run directory is not sealed twice
        self.assertEqual(capture.begin(self.repo.dir, state, job, None, run_dir, state / "work" / job["id"]), 3)
        self.assertEqual(len(self.archive().rows(job=job["id"])), 1)

    def test_no_archive_tool_no_capture(self):
        os.environ.pop("ITL_ARTIFACTS")
        self.assertIsNone(capture.tool(self.repo.dir))
        self.assertIsNone(capture.begin(self.repo.dir, self.repo.dir, {"id": "j"}, None, self.repo.dir / "none", self.repo.dir / "none"))
        self.assertTrue(capture.before_collect(self.repo.dir, self.repo.dir, "j", self.repo.dir, self.repo.dir, {}))


if __name__ == "__main__":
    unittest.main()

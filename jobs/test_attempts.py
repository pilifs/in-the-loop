#!/usr/bin/env python3
"""Tests of jobs/attempts.py: the record and the folders every execution of a job gets before its first byte.
What the runner, `prune` and `recover` do with them is tested in verification/test_capture.py, on a real spool.

  python3 jobs/test_attempts.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import attempts  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402

JOB = "20261127-101010-made-up"


class ALedger(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name)

    def test_an_attempt_is_on_disk_with_its_identity_before_anything_is_written_into_it(self):
        attempt = attempts.begin(self.state, JOB, "c" * 40, "vm-1")
        record = json.loads((attempt.folder / "attempt.json").read_text())
        self.assertEqual((record["schema"], record["job"], record["number"], record["state"], record["source"], record["host"]),
                         ("itl-job-attempt/v1", JOB, 1, "running", "c" * 40, "vm-1"))
        self.assertEqual(record["id"], f"{JOB}.001.{record['token']}")
        self.assertEqual((record["capture"], record["previous"], record["pid"]), ({"state": "pending"}, None, os.getpid()))
        self.assertTrue((attempt.run_dir / "logs").is_dir())
        self.assertFalse(attempt.work_dir.exists())             # the export makes it
        self.assertEqual(attempts.find(self.state, attempt.id).folder, attempt.folder)

    def test_every_attempt_has_folders_of_its_own_and_a_number_no_less_than_the_archives(self):
        first = attempts.begin(self.state, JOB, None, "h")
        (first.run_dir / "logs/1-step.log").write_text("the first attempt's\n")
        second = attempts.begin(self.state, JOB, None, "h")
        self.assertEqual((second.number, second.record["previous"]), (2, first.id))
        self.assertNotEqual(first.folder, second.folder)
        self.assertEqual((first.run_dir / "logs/1-step.log").read_text(), "the first attempt's\n")   # nothing was cleared
        self.assertEqual(attempts.next_number(self.state, JOB), 3)
        ahead = attempts.begin(self.state, JOB, None, "h", at_least=7)        # the archive had numbered six more elsewhere
        self.assertEqual((ahead.number, attempts.next_number(self.state, JOB)), (7, 8))
        self.assertEqual([a.number for a in attempts.of(self.state, JOB)], [1, 2, 7])
        self.assertEqual(attempts.begin(self.state, "20261127-101010-another", None, "h").number, 1)
        self.assertEqual(len(attempts.every(self.state)), 4)

    @cost("tool")
    def test_an_attempt_whose_runner_is_gone_is_interrupted_and_said_until_it_is_sealed(self):
        attempt = attempts.begin(self.state, JOB, None, "h")
        self.assertEqual((attempt.state(), attempts.problems(attempt)), ("running", []))
        gone = subprocess.Popen(["true"])
        gone.wait()
        attempt.save(pid=gone.pid)
        self.assertEqual(attempt.state(), "interrupted")
        (problem,) = attempts.problems(attempt)
        self.assertEqual((problem["kind"], problem["level"]), ("attempt-interrupted-unsealed", "gap"))
        self.assertIn(str(attempt.folder), problem["detail"])
        attempt.captured("recovered", {"logs": "occ-1"}, number=1)
        self.assertEqual(attempts.problems(attempt), [])

    def test_a_capture_that_failed_is_a_gap_and_a_folder_that_went_with_no_release_a_discrepancy(self):
        attempt = attempts.begin(self.state, JOB, None, "h")
        attempt.work_dir.mkdir()
        attempt.save(prepared=True)
        attempt.captured("failed", error="SpoolFull: no room")
        attempt.finished("failed")
        self.assertEqual([(p["kind"], p["level"]) for p in attempts.problems(attempt)], [("attempt-capture-failed", "gap")])
        self.assertIn("SpoolFull", attempts.problems(attempt)[0]["detail"])
        attempt.captured("sealed", {"workdir": "occ-2"}, number=1)
        self.assertEqual(attempts.problems(attempt), [])
        freed = attempt.release("work", "pruned: verified")
        self.assertEqual((freed, attempt.work_dir.exists(), attempts.problems(attempt)), (0, False, []))
        self.assertEqual([(r["what"], r["why"]) for r in attempt.record["released"]], [("work", "pruned: verified")])
        import shutil
        shutil.rmtree(attempt.run_dir)                          # by hand, and nobody said so
        self.assertEqual([(p["kind"], p["level"]) for p in attempts.problems(attempt)], [("attempt-folder-gone", "discrepancy")])

    def test_a_fingerprint_tells_a_folder_that_changed_from_the_one_that_was_sealed(self):
        attempt = attempts.begin(self.state, JOB, None, "h")
        attempt.work_dir.mkdir()
        (attempt.work_dir / "a.txt").write_text("a\n")
        (attempt.work_dir / "sub").mkdir()
        (attempt.work_dir / "sub/link").symlink_to("../a.txt")
        attempt.captured("sealed", {"workdir": "occ"}, number=1)
        sealed = attempt.record["capture"]["fingerprints"]["work"]
        self.assertEqual((sealed["files"], sealed["bytes"]), (1, 2))
        self.assertEqual(attempts.fingerprint(attempt.work_dir), sealed)           # reading changes nothing
        (attempt.work_dir / "a.txt").read_text()
        self.assertEqual(attempts.fingerprint(attempt.work_dir), sealed)
        (attempt.work_dir / "b.txt").write_text("")
        self.assertNotEqual(attempts.fingerprint(attempt.work_dir)["sha256"], sealed["sha256"])
        (attempt.work_dir / "b.txt").unlink()
        self.assertEqual(attempts.fingerprint(attempt.work_dir), sealed)
        (attempt.work_dir / "a.txt").write_text("b\n")                             # the same size, written again
        self.assertNotEqual(attempts.fingerprint(attempt.work_dir)["sha256"], sealed["sha256"])
        self.assertIsNone(attempts.fingerprint(attempt.folder / "nowhere"))

    def test_a_record_that_cannot_be_read_is_still_an_attempt_with_its_folders(self):
        attempt = attempts.begin(self.state, JOB, None, "h")
        (attempt.folder / "attempt.json").write_text("{ cut off")
        (found,) = attempts.of(self.state, JOB)
        self.assertEqual((found.number, found.state(), found.folder), (1, "unknown", attempt.folder))
        self.assertEqual([p["kind"] for p in attempts.problems(found)], ["attempt-record-unreadable"])
        self.assertEqual(attempts.next_number(self.state, JOB), 2)                 # its number is not given out again


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests of jobs/lifecycle.py: what became of a job, each question apart, read off results as they are committed.

  python3 jobs/test_lifecycle.py
"""

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import lifecycle  # noqa: E402

RESULTS = ROOT / "verification/results/2026/11/27"


def committed(job_id):
    result = json.loads((RESULTS / job_id / "result.json").read_text())
    return result["job"]["spec"], result


class ResultsOfBeforeTheBlocksWereKept(unittest.TestCase):
    def test_a_job_that_failed_in_preparation_took_41_seconds_and_its_requested_steps_took_none(self):
        """The brief's timing fixture: its receipt says 41 s elapsed, and its index entry 0 s, the requested steps'.
        Both are true once each has its scope, and neither is a measured zero of the other."""
        job, result = committed("20261127-054106-trace-individually-approved-ordinary-ups")
        timing = lifecycle.timing(job, result)
        self.assertEqual(timing["elapsed"], {"seconds": 41.0, "state": "measured"})
        self.assertEqual(timing["requestedSteps"], {"seconds": 0, "state": "not-run", "ran": 0, "planned": len(job["steps"])})
        self.assertEqual(timing["preparation"], {"seconds": 41.0, "state": "derived"})
        self.assertEqual(timing["queueWait"]["state"], "measured")
        execution = lifecycle.execution(result)
        self.assertEqual((execution["status"], execution["steps"]["ran"], execution["steps"]["preparation"]), ("error", 0, 1))
        self.assertEqual((execution["stopped"]["step"], execution["stopped"]["reason"]), (0, "preparation"))
        delivered = lifecycle.fulfillment(job, result)
        self.assertEqual((delivered["state"], [u["kind"] for u in delivered["unmet"]]), ("unfulfilled", ["preparation"]))
        self.assertTrue(all(block["derived"] for block in lifecycle.facets(job, result, derived=True).values()))

    def test_a_passed_job_of_the_first_format_is_fulfilled_and_its_steps_are_measured(self):
        job, result = committed("20261127-145103-read-both-original-maven-wars-with-a-pin")
        blocks = lifecycle.facets(job, result, derived=True)
        self.assertEqual((blocks["execution"]["status"], blocks["execution"]["stopped"], blocks["fulfillment"]["state"]), ("passed", None, "fulfilled"))
        self.assertEqual(blocks["timing"]["requestedSteps"]["state"], "measured")
        self.assertEqual(blocks["timing"]["requestedSteps"]["seconds"], round(result["usage"]["wallSeconds"], 1))


class WhatIsNotThere(unittest.TestCase):
    def result(self, **over):
        return {"status": "passed", "startedAt": "2026-11-28T10:00:10+00:00", "finishedAt": "2026-11-28T10:00:40+00:00", "wallSeconds": 30.0,
                "attention": [], "steps": [], "runner": {"isolation": "none"}, **over}

    def step(self, index, status="passed", **over):
        return {"index": index, "name": f"s{index}", "status": status, "exitCode": 0, "expectExit": [0], "wallSeconds": 2.0, "cpuSeconds": 1.0, **over}

    def test_a_cancelled_job_is_undetermined_and_a_wait_nobody_recorded_is_unknown(self):
        result = self.result(status="cancelled", steps=[self.step(1, "cancelled", exitCode=None, signal="SIGTERM")])
        self.assertEqual(lifecycle.fulfillment({}, result)["state"], "undetermined")
        self.assertEqual(lifecycle.execution(result)["stopped"]["reason"], "cancelled")
        self.assertEqual(lifecycle.timing({}, result)["queueWait"], {"seconds": None, "state": "unknown"})
        self.assertEqual(lifecycle.timing({"submitted": {"at": "2026-11-28T10:00:00+00:00"}}, result)["queueWait"], {"seconds": 10.0, "state": "measured"})

    def test_a_submission_time_written_without_its_zone_is_measured_as_utc_and_does_not_raise(self):
        job, result = committed("20261127-145103-read-both-original-maven-wars-with-a-pin")
        by_hand = {**job, "submitted": {**job["submitted"], "at": job["submitted"]["at"][:19]}}      # 2026-11-27T14:51:03, no offset
        self.assertEqual(lifecycle.timing(by_hand, result)["queueWait"], lifecycle.timing(job, result)["queueWait"])
        self.assertEqual(lifecycle.timing({**job, "submitted": {"at": 5}}, result)["queueWait"]["state"], "unknown")

    def test_steps_that_were_skipped_leave_the_requested_time_partial_and_a_measured_zero_stays_one(self):
        job = {"steps": [{"run": "a"}, {"run": "b"}, {"run": "c"}]}
        result = self.result(status="failed", steps=[self.step(1, wallSeconds=0.0, phase="build"), self.step(2, "failed", exitCode=2, phase="test"),
                                                     {"index": 3, "name": "s3", "status": "skipped", "why": "an earlier step failed"}])
        timing = lifecycle.timing(job, result)
        self.assertEqual(timing["requestedSteps"], {"seconds": 2.0, "state": "partial", "ran": 2, "planned": 3})
        self.assertEqual(timing["byPhase"], {"build": 0.0, "test": 2.0})
        execution = lifecycle.execution(result)
        self.assertEqual((execution["status"], execution["stopped"]), ("failed", {"step": 2, "name": "s2", "reason": "exit", "exitCode": 2}))

    def test_stops_at_a_limit_are_told_apart(self):
        reason = lambda **step: lifecycle.execution(self.result(status=step["status"], steps=[self.step(1, **step)]))["stopped"]["reason"]
        self.assertEqual(reason(status="timeout", stoppedFor="stalled"), "stalled")
        self.assertEqual(reason(status="timeout", stoppedFor="ceiling"), "ceiling")
        self.assertEqual(reason(status="timeout"), "timeout")
        self.assertEqual(reason(status="out-of-memory", limitOoms=1), "memory-limit")
        self.assertEqual(reason(status="out-of-memory", limitOoms=0, oomKills=1), "machine-memory")
        self.assertEqual(reason(status="failed", exitCode=None, signal="SIGKILL"), "signal")


class TheTwoResultSchemas(unittest.TestCase):
    def test_everything_a_result_of_the_first_format_may_say_a_result_of_the_second_may_say_the_same_way(self):
        first = json.loads((ROOT / "verification/schema/result.schema.json").read_text())
        second = json.loads((HERE / "schema/result.schema.json").read_text())
        blocks = {"preparationSeconds", "declared", "execution", "fulfillment", "timing", "conclusion", "readiness"}   # named in the first, described in the second
        differ = {k for k, d in first["properties"].items() if second["properties"].get(k) != d}
        self.assertEqual(differ, {"schema", "status", "steps"} | blocks)
        steps = lambda schema: schema["properties"]["steps"]["items"]["properties"]
        self.assertEqual({k for k, d in steps(first).items() if steps(second).get(k) != d}, set())
        self.assertEqual(set(steps(second)) - set(steps(first)), {"phase", "network", "evidence", "unmet"})
        self.assertEqual(set(second["required"]) - set(first["required"]), {"execution", "fulfillment", "timing"})


if __name__ == "__main__":
    unittest.main()

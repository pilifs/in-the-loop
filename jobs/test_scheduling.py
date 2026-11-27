#!/usr/bin/env python3
"""Tests of jobs/scheduling.py: why a committed job has not started.

  python3 jobs/test_scheduling.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import scheduling  # noqa: E402
from scheduling import Known, decide, prerequisites  # noqa: E402

A, B, C, D = (f"20261128-10000{n}-job-{n}" for n in range(4))


def needing(*ids, **more):
    return {"needs": [{"job": i} for i in ids], **more}


class WhatBecameOfAPrerequisite(unittest.TestCase):
    def test_it_is_fulfilled_by_its_own_passed_result_or_by_one_of_a_job_that_supersedes_it(self):
        known = Known({A: {}, B: {"supersedes": A}, C: {"supersedes": B}}, {A: "failed", B: "timeout", C: "passed"})
        self.assertEqual(known.outcome(A), {"state": "fulfilled", "by": C})
        self.assertEqual(known.line(A), [A, B, C])
        need, = prerequisites(needing(A), known)
        self.assertEqual((need["state"], need["by"]), ("satisfied", C))
        self.assertIn(f"{C} (which supersedes {A}) passed", need["why"])

    def test_a_failed_one_that_is_being_tried_again_is_waited_for_and_one_that_is_not_blocks(self):
        retried = Known({A: {}, B: {"supersedes": A}}, {A: "failed"})
        self.assertEqual(retried.outcome(A), {"state": "pending", "by": B})
        self.assertEqual(decide(needing(A), [], [], prerequisites(needing(A), retried))[0], "waiting")
        ended = Known({A: {}}, {A: "out-of-memory"})
        state, why = decide(needing(A), [], [], prerequisites(needing(A), ended))
        self.assertEqual(state, "blocked")
        self.assertIn(f"{A} ended out-of-memory: resubmit it", why)

    def test_a_cancelled_job_runs_again_so_it_has_not_finished_and_a_running_one_has_not_either(self):
        self.assertEqual(Known({A: {}}, {A: "cancelled"}).outcome(A)["state"], "pending")
        self.assertEqual(Known({A: {}}, {}, running=[A]).outcome(A)["state"], "pending")
        self.assertEqual(Known({A: {}}, {}).outcome(A)["state"], "pending")      # committed, not started

    def test_a_job_nobody_submitted_is_unknown_and_blocks_and_a_result_alone_is_enough_to_know_one(self):
        nothing = Known({}, {})
        state, why = decide(needing(A), [], [], prerequisites(needing(A), nothing))
        self.assertEqual((state, why), ("blocked", f"{A} is not a job in the queue, and no result of it is recorded"))
        self.assertEqual(Known({}, {A: "passed"}).outcome(A)["state"], "fulfilled")   # collected long ago; its file is elsewhere

    def test_superseding_in_a_circle_ends(self):
        known = Known({A: {"supersedes": B}, B: {"supersedes": A}}, {})
        self.assertEqual(sorted(known.line(A)), [A, B])


class TheStateOfAJobThatHasNotStarted(unittest.TestCase):
    def test_the_first_thing_in_its_way_names_the_state(self):
        known = Known({A: {}, B: {}}, {A: "passed"})
        needs = prerequisites(needing(A, B), known)
        self.assertEqual(decide({}, ["not JSON"], ["needs 64 GiB"], needs), ("invalid", "not JSON"))
        self.assertEqual(decide({}, [], ["needs 64 GiB", "no adapter"], needs), ("unschedulable", "needs 64 GiB; no adapter"))
        self.assertEqual(decide({}, [], [], needs), ("waiting", f"{B} has not finished"))
        self.assertEqual(decide({}, [], [], prerequisites(needing(A), known)), ("queued", None))
        self.assertEqual(decide({}, [], [], []), ("queued", None))
        self.assertEqual(set(scheduling.STATES), {"invalid", "unschedulable", "blocked", "waiting", "deferred", "queued"})

    def test_a_failed_prerequisite_outranks_one_still_running(self):
        known = Known({A: {}, B: {}}, {A: "failed"})
        self.assertEqual(decide({}, [], [], prerequisites(needing(A, B), known))[0], "blocked")

    def test_a_readiness_prerequisite_is_answered_by_whoever_reads_receipts(self):
        key = "ab" * 32
        job = {"needs": [{"readiness": key}]}
        self.assertEqual(prerequisites(job, Known({}, {}))[0]["state"], "unknown")
        ready = lambda k: {"state": "satisfied", "why": f"receipt {k[:12]} is valid"}
        self.assertEqual(decide(job, [], [], prerequisites(job, Known({}, {}), ready)), ("queued", None))
        absent = lambda k: {"state": "waiting", "why": f"no receipt for {k[:12]} yet"}
        self.assertEqual(decide(job, [], [], prerequisites(job, Known({}, {}), absent)), ("waiting", f"no receipt for {key[:12]} yet"))


if __name__ == "__main__":
    unittest.main()

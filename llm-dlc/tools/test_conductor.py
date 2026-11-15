#!/usr/bin/env python3
"""Tests for conductor.py: the events a moonshot loop asks its conductor about, and the verdicts that answer them.
Run: python3 llm-dlc/tools/test_conductor.py"""
import contextlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path

import conductor


def call(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        status = conductor.main([str(a) for a in argv])
    return status, out.getvalue(), err.getvalue()


class ConductorTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "run"

    def ask(self, seconds=600, **more):
        return conductor.append_event(self.dir, type="compaction", cycle=1, item="901", needsVerdict=True,
                                      deadline=time.time() + seconds, **more)

    def test_events_are_numbered_in_the_order_they_were_added(self):
        self.assertEqual([self.ask()["n"], self.ask()["n"]], [1, 2])
        self.assertEqual([e["n"] for e in conductor.read_events(self.dir)], [1, 2])

    def test_wait_returns_the_event_that_needs_a_verdict_with_how_to_answer_it(self):
        self.ask(tokens=600000)
        status, out, _ = call("wait", self.dir, "--timeout", 0)
        event = json.loads(out)
        self.assertEqual((status, event["n"], event["tokens"]), (0, 1, 600000))
        self.assertIn(f"decide {self.dir} 1", event["answer"])
        self.assertGreater(event["secondsLeft"], 0)

    def test_wait_times_out_while_nothing_needs_judging(self):
        conductor.append_event(self.dir, type="compaction", cycle=1, needsVerdict=False)
        status, out, _ = call("wait", self.dir, "--timeout", 0)
        self.assertEqual((status, json.loads(out)["type"]), (3, "timeout"))

    def test_a_verdict_answers_its_event_once(self):
        self.ask()
        self.assertEqual(call("decide", self.dir, 1, "continue", "--reason", "three  commits\nsince the cycle began")[0], 0)
        self.assertEqual(conductor.read_verdict(self.dir, 1)["reason"], "three commits since the cycle began")
        self.assertEqual(call("decide", self.dir, 1, "stop", "--reason", "changed my mind")[0], 2)
        self.assertEqual(conductor.read_verdict(self.dir, 1)["verdict"], "continue")
        self.assertEqual(call("wait", self.dir, "--timeout", 0)[0], 3)  # answered: nothing left to judge

    def test_an_event_that_asks_for_nothing_takes_no_verdict(self):
        conductor.append_event(self.dir, type="compaction", cycle=1, needsVerdict=False)
        self.assertEqual(call("decide", self.dir, 1, "stop", "--reason", "x")[0], 2)
        self.assertEqual(call("decide", self.dir, 7, "stop", "--reason", "x")[0], 2)

    def test_a_question_taken_back_is_no_longer_waited_for(self):
        self.ask()
        conductor.append_event(self.dir, type="withdrawn", event=1)
        self.assertEqual(call("wait", self.dir, "--timeout", 0)[0], 3)

    def test_an_event_past_its_deadline_is_no_longer_waited_for_and_a_late_verdict_says_so(self):
        self.ask(seconds=-1)
        self.assertEqual(call("wait", self.dir, "--timeout", 0)[0], 3)
        status, out, _ = call("decide", self.dir, 1, "continue", "--reason", "late")
        self.assertEqual(status, 0)
        self.assertIn("after its deadline", out)

    def test_the_loop_s_end_is_reported_once(self):
        conductor.append_event(self.dir, type="ended", status=1, record="llm-dlc/loop-summaries/made-up.md")
        status, out, _ = call("wait", self.dir, "--timeout", 0)
        self.assertEqual((status, json.loads(out)["type"], json.loads(out)["status"]), (0, "ended", 1))
        self.assertEqual(call("wait", self.dir, "--timeout", 0)[0], 3)

    def test_a_half_written_line_is_skipped(self):
        self.ask()
        with open(self.dir / conductor.EVENTS, "a") as f:
            f.write('{"n": 2, "type": "compac')
        self.assertEqual(len(conductor.read_events(self.dir)), 1)

    def test_events_lists_each_with_its_verdict(self):
        self.ask()
        call("decide", self.dir, 1, "stop", "--reason", "the same test has failed since the cycle began")
        _, out, _ = call("events", self.dir)
        self.assertEqual(json.loads(out.splitlines()[0])["verdict"]["verdict"], "stop")


if __name__ == "__main__":
    unittest.main()

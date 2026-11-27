#!/usr/bin/env python3
"""Tests for conductor.py: the events a moonshot loop asks its conductor about, and the verdicts that answer them.
Run: python3 llm-dlc/tools/test_conductor.py"""
import contextlib
import io
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import conductor
import decisions


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

    def test_events_added_at_once_each_get_a_number_of_their_own(self):
        # two loops that share a directory and end together each ask their watcher
        import threading
        read, start = conductor.read_events, threading.Barrier(8)

        def slow(directory):  # the gap between counting the events and writing one, made wide
            events = read(directory)
            time.sleep(0.02)
            return events

        def add():
            start.wait()
            self.ask()
        threads = [threading.Thread(target=add) for _ in range(8)]
        with mock.patch.object(conductor, "read_events", slow):
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(sorted(e["n"] for e in conductor.read_events(self.dir)), list(range(1, 9)))

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

    def test_a_question_takes_only_its_own_answers(self):
        conductor.append_event(self.dir, type="cycle", item="007", needsVerdict=True, deadline=time.time() + 600,
                               answers=["finished", "continue", "waiting"])
        status, out, _ = call("wait", self.dir, "--timeout", 0)
        self.assertIn("finished|continue|waiting", json.loads(out)["answer"])
        status, _, err = call("decide", self.dir, 1, "stop", "--reason", "made up")
        self.assertEqual(status, 2)
        self.assertIn("takes finished or continue or waiting, not stop", err)
        self.assertEqual(call("decide", self.dir, 1, "waiting", "--reason", "its last proof is queued")[0], 0)
        self.ask()  # a compaction names no answers: continue or stop
        self.assertEqual(call("decide", self.dir, 2, "finished", "--reason", "made up")[0], 2)

    def test_ask_prints_the_verdict_and_its_reason_or_none_after_the_deadline(self):
        import threading
        answer = threading.Timer(0.5, lambda: conductor.cmd_decide(self.dir, 1, "waiting", "its last proof  is queued"))
        answer.start()
        status, out, _ = call("ask", self.dir, "cycle", "--answers", "finished,continue,waiting", "--wait", 30,
                              "cycle=3", "item=007", "itemCycle=2")
        answer.join()
        self.assertEqual((status, out.splitlines()[-1]), (0, "waiting\tits last proof is queued"))  # decide printed too
        asked = conductor.read_events(self.dir)[0]
        self.assertEqual((asked["cycle"], asked["item"], asked["itemCycle"]), (3, "007", 2), "an item stays text")
        self.assertEqual(call("ask", self.dir, "example", "--answers", "continue,stop", "--wait", 0.2)[1], "none\n")

    def test_a_note_asks_nothing(self):
        call("note", self.dir, "cycle-start", "cycle=1", "item=901", "itemCycle=1")
        self.assertEqual(call("wait", self.dir, "--timeout", 0)[0], 3)
        self.assertEqual(conductor.read_events(self.dir)[0]["type"], "cycle-start")

    def test_command_lines_are_handed_to_the_loop_once(self):
        call("command", self.dir, "stop")
        call("command", self.dir, "+", "2")
        self.assertEqual(call("commands", self.dir)[1], "stop\n+ 2\n")
        self.assertEqual(call("commands", self.dir)[1], "")


class DecisionRecordTest(unittest.TestCase):
    """A verdict is also a decision: in a checkout, it goes into the run's decision record (decisions.py)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.checkout = Path(tmp.name).resolve() / "checkout"
        self.dir = self.checkout / "llm-dlc/loop-summaries/prove-change"
        self.records = self.checkout / "llm-dlc/decisions"
        (self.checkout / "examples/901-made-up").mkdir(parents=True)
        self.start = conductor.append_event(self.dir, type="cycle-start", cycle=1, item="901")

    def ask(self, seconds=600):
        return conductor.append_event(self.dir, type="cycle", cycle=1, item="901", needsVerdict=True,
                                      answers=["finished", "continue", "waiting"], deadline=time.time() + seconds)["n"]

    def test_a_verdict_in_time_is_a_decision_the_user_can_review_afterwards(self):
        status, out, err = call("decide", self.dir, self.ask(), "finished", "--reason", "every claim has its answer")
        self.assertEqual((status, err), (0, ""))
        self.assertIn("recorded as prove-change-D001", out)
        d = decisions.fold(decisions.read("prove-change", self.records))["prove-change-D001"]
        self.assertEqual((d["state"], d["decision"]["option"], d["decision"]["by"], d["review"]["state"]),
                         ("decided", "finished", "conductor", "unreviewed"))
        self.assertEqual((d["run"], d["context"]["files"], [o["id"] for o in d["options"]]),
                         (self.start["time"], ["examples/901-made-up"], ["finished", "continue", "waiting"]))
        self.assertIn("example 901", d["asked"]["question"])
        self.assertEqual(decisions.problems(self.records), [])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(decisions.main(["review", "overturn", "prove-change-D001", "--note", "one claim is still open"],
                                            root=self.records), 0)
        self.assertEqual(decisions.problems(self.records), [])
        self.assertEqual(conductor.read_verdict(self.dir, 2)["verdict"], "finished", "the verdict's file is as it was")

    def test_a_verdict_of_medium_confidence_is_flagged_and_each_verdict_gets_its_own_number(self):
        call("decide", self.dir, self.ask(), "continue", "--reason", "a claim is open")
        self.assertIn("recorded as prove-change-D002",
                      call("decide", self.dir, self.ask(), "waiting", "--reason", "its proof is queued", "--confidence", "medium")[1])
        d = decisions.fold(decisions.read("prove-change", self.records))["prove-change-D002"]
        self.assertEqual(d["review"], {"state": "flagged", "why": "medium-confidence"})

    def test_a_late_verdict_decided_nothing_and_is_not_recorded(self):
        self.assertEqual(call("decide", self.dir, self.ask(seconds=-1), "finished", "--reason", "too late")[0], 0)
        self.assertEqual(decisions.record_names(self.records), [])

    def test_a_record_that_cant_be_written_does_not_hold_the_verdict_back(self):
        self.records.parent.mkdir(parents=True, exist_ok=True)
        self.records.write_text("a file where the records' folder would be")
        status, _, err = call("decide", self.dir, self.ask(), "finished", "--reason", "done")
        self.assertEqual(status, 0)
        self.assertIn("the verdict stands", err)
        self.assertEqual(conductor.read_verdict(self.dir, 2)["verdict"], "finished")

    def test_a_run_directory_outside_a_checkout_has_no_record(self):
        self.assertIsNone(conductor.decision_record(self.checkout / "run"))


if __name__ == "__main__":
    unittest.main()

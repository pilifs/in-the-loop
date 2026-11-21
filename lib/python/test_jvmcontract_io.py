#!/usr/bin/env python3
"""The proof output reader (jvmcontract_io.py): what decodes, how a process must have ended, and that a field is read
as the type the contract gives it. No process is started; the rows are made here.

    python3 lib/python/test_jvmcontract_io.py
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jvmcontract_io as wire  # noqa: E402


def row(verdict="verified", **fields):
    return {"wire_version": 1, "verdict": verdict, "output": "", **fields}


def printed(*rows):
    return json.dumps(list(rows))


class Decode(unittest.TestCase):
    def test_untagged_and_tagged_rows_decode_in_the_order_printed_and_keep_their_versions(self):
        untagged = {"verdict": "verified", "output": "a"}
        rows = [untagged, row("violation"), row("unverifiable")]
        decoded = wire.decode(printed(*rows), "prove")
        self.assertTrue(decoded.ok)
        self.assertEqual(decoded.outcomes, tuple(rows))
        self.assertEqual(decoded.versions, (0, 1, 1))
        self.assertEqual(decoded.raw, printed(*rows))
        one = wire.decode(json.dumps(row()), "equivalence")
        self.assertEqual((one.status, one.outcomes), ("decoded", (row(),)))

    def test_a_version_the_reader_does_not_know_is_its_own_outcome_whatever_the_rest_says(self):
        for value in (999, 2, "1", True, 1.0, None):
            with self.subTest(value=value):
                decoded = wire.decode(printed(row(wire_version=value)), "prove")
                self.assertEqual((decoded.status, decoded.outcomes, decoded.versions), ("unsupported-version", (), (value,)))
                self.assertIn("wire version", decoded.reason)
                self.assertFalse(wire.supported_version(row(wire_version=value)))
        # One row of a newer version refuses the whole output: its siblings are not read as if they stood alone.
        self.assertEqual(wire.decode(printed(row(), row(wire_version=2)), "prove").status, "unsupported-version")

    def test_output_that_is_not_the_commands_shape_is_refused_with_which(self):
        self.assertEqual(wire.decode("panicked at", "prove").status, "not-json")
        self.assertEqual(wire.decode(None, "prove").status, "not-json")
        self.assertEqual(wire.decode("[]", "prove").status, "not-outcome")
        self.assertEqual(wire.decode(json.dumps(row()), "prove").status, "not-outcome")            # an object where prove prints a list
        self.assertEqual(wire.decode(printed(row()), "equivalence").status, "not-outcome")          # a list where equivalence prints an object
        self.assertEqual(wire.decode(printed({"wire_version": 1, "verdict": "verified"}), "prove").status, "not-outcome")  # no output text
        with self.assertRaises(ValueError):
            wire.decode("[]", "transcript")


class Completion(unittest.TestCase):
    def completed(self, outcomes, exit_code, command="prove", **kw):
        text = printed(*outcomes) if command == "prove" else json.dumps(outcomes[0])
        return wire.completion(command, wire.decode(text, command), exit_code, **kw)

    def test_a_run_exits_with_the_worst_of_its_rows_and_each_row_keeps_its_own_result(self):
        self.assertEqual(wire.exit_of(["verified", "verified"]), 0)
        self.assertEqual(wire.exit_of(["verified", "violation", "verified"]), 1)
        self.assertEqual(wire.exit_of(["verified", "unverifiable"]), 1)
        mixed = [row(), row("violation"), row()]
        ended = self.completed(mixed, 1)
        self.assertTrue(ended.ok, ended)
        decoded = wire.decode(printed(*mixed), "prove")
        self.assertEqual([o["verdict"] for o in decoded.outcomes], ["verified", "violation", "verified"])
        # A valid refutation ends with 1: completed, and for the consumer to score or qualify.
        self.assertTrue(self.completed([row("violation")], 1, rows=1).ok)
        self.assertTrue(self.completed([row("unverifiable")], 1, rows=1).ok)
        self.assertTrue(self.completed([row()], 0, command="equivalence").ok)

    def test_an_exit_that_contradicts_the_rows_completes_nothing(self):
        for outcomes, exit_code in (([row()], 1), ([row("violation")], 0), ([row("unverifiable")], 0), ([row(), row("violation")], 0)):
            with self.subTest(rows=[r["verdict"] for r in outcomes], exit=exit_code):
                ended = self.completed(outcomes, exit_code)
                self.assertEqual(ended.status, "contradictory-exit")
                self.assertIn(f"code {exit_code}", ended.reason)

    def test_exit_2_a_signal_and_a_timeout_are_never_a_completed_run_whatever_was_printed(self):
        decisive = [row()]
        self.assertEqual(self.completed(decisive, 2).status, "tool-error")
        self.assertEqual(self.completed(decisive, 137).status, "tool-error")
        self.assertEqual(self.completed(decisive, -9).status, "killed")
        self.assertEqual(self.completed(decisive, 0, killed=True).status, "killed")
        self.assertEqual(self.completed(decisive, 0, timed_out=30).status, "timed-out")
        self.assertEqual(self.completed(decisive, None).status, "tool-error")
        self.assertEqual(self.completed(decisive, True).status, "tool-error")   # True is not exit code 1

    def test_an_unknown_version_and_unreadable_output_are_told_apart(self):
        unknown = wire.completion("prove", wire.decode(printed(row(wire_version=999)), "prove"), 0)
        self.assertEqual((unknown.status, unknown.exit), ("unsupported-version", 0))
        self.assertEqual(wire.completion("prove", wire.decode("", "prove"), 0).status, "invalid-output")
        self.assertEqual(unknown.as_execution(), {"status": "unsupported-version", "exitCode": 0, "reason": "unsupported checker wire version 999"})

    def test_a_single_property_must_print_its_one_row(self):
        self.assertTrue(self.completed([row()], 0, rows=1).ok)
        two = self.completed([row(), row()], 0, rows=1)
        self.assertEqual(two.status, "invalid-output")
        self.assertIn("2 outcomes", two.reason)
        self.assertTrue(self.completed([row(), row()], 0).ok)   # a properties file: the caller counts

    def test_a_verdict_that_is_not_one_of_the_three_is_no_row(self):
        self.assertEqual(self.completed([row("proved")], 0).status, "invalid-output")
        self.assertEqual(self.completed([row(None)], 1).status, "invalid-output")

    def test_a_decision_field_of_another_type_completes_nothing(self):
        stated = {"bounds": {"unwind": 5, "complete": "false"}}
        ended = self.completed([row(stated=stated)], 0)
        self.assertEqual(ended.status, "invalid-output")
        self.assertIn("stated.bounds.complete", ended.reason)
        decoded, ended = wire.read(printed(row(stated={"bounds": {"complete": True}})), "prove", 0, rows=1)
        self.assertTrue(decoded.ok and ended.ok)


class Fields(unittest.TestCase):
    def test_a_string_is_never_a_boolean_and_true_is_never_an_integer(self):
        self.assertIs(wire.boolean(True), True)
        self.assertIs(wire.boolean(False), False)
        for value in ("false", "true", 1, 0, None, [], {}):
            self.assertIsNone(wire.boolean(value), value)
        self.assertEqual(wire.integer(3), 3)
        self.assertIsNone(wire.integer(True))
        self.assertIsNone(wire.text(3))
        self.assertIsNone(wire.at({"stated": "x"}, "stated", "bounds", "complete"))
        self.assertIsNone(wire.at({"stated": None}, "stated", "bounds"))

    def test_mistyped_names_each_field_and_the_pairs_and_leaves_an_absent_one_alone(self):
        self.assertEqual(wire.mistyped(row()), [])
        self.assertEqual(wire.mistyped({**row(), "proof": None, "problem": None, "replay": None, "stated": None}), [])
        wrong = {**row(), "stated": {"bounds": {"complete": 1}, "vacuity": {"status": True}}, "replay": {"reproduced": "true", "by": 3},
                 "pair": {"verdict": 0, "stated": {"bounds": {"complete": "true"}}}}
        self.assertEqual(wire.mistyped(wrong), ["stated.bounds.complete", "stated.vacuity.status", "replay.reproduced", "replay.by",
                                               "pair.verdict", "pair.stated.bounds.complete"])

    def test_facts_keep_apart_what_a_reader_must_not_confuse(self):
        fresh = row(proof="all paths", search={"engine": "native", "gaps": []},
                    stated={"bounds": {"complete": True}, "vacuity": {"status": "non-vacuous"}})
        self.assertEqual(wire.facts(fresh), {
            "version": 1, "verdict": "verified", "complete": True, "vacuity": "non-vacuous", "proof": "all paths", "fresh": True,
            "reproduced": None, "replayedBy": None, "assumedGaps": [], "contractGaps": []})
        # Untagged output from before the version: version 0, and what it does not say is unknown, not false.
        legacy = {"verdict": "verified", "output": "", "proof": "all paths", "search": {"engine": "native"}}
        facts = wire.facts(legacy)
        self.assertEqual((facts["version"], facts["complete"], facts["vacuity"]), (0, None, None))
        # An exact hit of the proof cache: a verdict with no checker run of its own.
        hit = row(proof="reused", reuse={"kind": "exact", "key": "sha256:ab", "from": "x"}, stated={"bounds": {"complete": True}})
        self.assertIs(wire.facts(hit)["fresh"], False)
        self.assertIsNone(wire.facts(row())["fresh"])
        # Vacuity said to be unknown is not non-vacuous, and neither is a status of another type.
        self.assertEqual(wire.facts(row(stated={"vacuity": {"status": "unknown"}}))["vacuity"], "unknown")
        self.assertIsNone(wire.facts(row(stated={"vacuity": {"status": True}}))["vacuity"])
        # A gap the checker assumed is named; one a contract answered is named apart.
        gaps = row(search={"gaps": [{"id": "jdk:A", "treatment": "assumed"}, {"id": "B", "treatment": "contract"}, {"id": "C", "treatment": "refused"}]})
        self.assertEqual((wire.facts(gaps)["assumedGaps"], wire.facts(gaps)["contractGaps"]), (["jdk:A"], ["B"]))
        # A replayed refutation, and one whose `reproduced` is a string.
        replayed = row("violation", replay={"by": "jvm", "reproduced": True})
        self.assertEqual((wire.facts(replayed)["reproduced"], wire.facts(replayed)["replayedBy"]), (True, "jvm"))
        self.assertIsNone(wire.facts(row("violation", replay={"by": "jvm", "reproduced": "true"}))["reproduced"])
        self.assertIsNone(wire.facts(row("proved"))["verdict"])


class Helpers(unittest.TestCase):
    CALLEE = {"class": "quotes.Outer$Tariff", "method": "fee", "descriptor": "(I)J"}

    def test_an_outcome_from_before_the_field_has_no_typed_decisions_and_an_empty_list_is_not_that(self):
        self.assertIsNone(wire.helper_decisions(row()))
        self.assertEqual(wire.helper_decisions(row(helpers=[])), [])

    def test_a_decision_is_read_as_data_with_its_callee_named_as_results_name_it(self):
        shared = {"callee": self.CALLEE, "action": "shared", "key": "sha256:ab", "source": "cache", "seconds": 0.25}
        applied = {"callee": self.CALLEE, "action": "summary-applied", "key": "sha256:cd", "source": "proved-now",
                   "summary": {"reads": ["this.feeCents"], "facts": ["this.feeCents >= 0"]}}
        kept = {"callee": self.CALLEE, "action": "keeps-body", "reason": {"code": "no-summary", "text": "its two versions differ"}}
        got = wire.helper_decisions(row(helpers=[shared, applied, kept]))
        self.assertEqual([d["callee"] for d in got], ["Outer$Tariff.fee"] * 3)
        self.assertEqual([(d["action"], d["key"], d["source"], d["reason"]) for d in got],
                         [("shared", "sha256:ab", "cache", None), ("summary-applied", "sha256:cd", "proved-now", None), ("keeps-body", None, None, "no-summary")])
        self.assertEqual(got[1]["summary"], {"reads": ["this.feeCents"], "facts": ["this.feeCents >= 0"]})
        self.assertEqual((got[0]["seconds"], got[2]["reasonText"]), (0.25, "its two versions differ"))

    def test_a_decision_the_contract_does_not_write_is_refused_and_never_guessed(self):
        for bad in ({"callee": self.CALLEE, "action": "inlined"}, {"callee": {"class": "a.B"}, "action": "shared"}, "note: B.m, changed"):
            with self.assertRaises(ValueError):
                wire.helper_decisions(row(helpers=[bad]))
        with self.assertRaises(ValueError):
            wire.helper_decisions(row(helpers="none"))


if __name__ == "__main__":
    unittest.main()

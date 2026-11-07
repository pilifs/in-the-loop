#!/usr/bin/env python3
"""Tests for alignment.py, the ground truth of alignment inference. Run: python3 examples/tools/test_alignment.py"""
import copy
import unittest

import alignment as A

# A made-up entry: a static method moved into a record's instance method, its first parameter gathered into the
# receiver, its result changed.
ENTRY = {
    "example": "900",
    "verdict": "verified",
    "before": {"symbol": "p.Old#f", "static": True, "parameters": [["base", "long"], ["n", "int"]], "returns": "boolean"},
    "after": {"symbol": "p.New#f", "static": False, "parameters": [["n", "int"]], "returns": "long", "receiver": [["base", "long"]]},
    "parts": [
        {"kind": "method", "old": "p.Old#f", "new": "p.New#f", "how": "moved", "decide": "infer", "why": "moved"},
        {"kind": "input", "old": "base", "new": "this.base", "anchor": "internal", "decide": "infer", "why": "into the receiver"},
        {"kind": "input", "old": "n", "new": "n", "anchor": "anchored", "decide": "infer", "why": "the same parameter"},
        {"kind": "result", "relation": "changed", "holds": "previous == (result > 0)", "decide": "person", "why": "changed"},
    ],
}
EXAMPLE = {
    "subject": {"symbol": "p.New#f"},
    "expected": {"verdict": "verified"},
    "change": {"previousSymbol": "p.Old#f", "previousArguments": "this.base, n", "resultsAgreeWhen": "previous == (result > 0)"},
}


class Flags(unittest.TestCase):
    def test_the_parts_amount_to_the_flags(self):
        self.assertEqual(A.flags_from_parts(ENTRY), A.flags_of(EXAMPLE))
        self.assertEqual(A.problems(ENTRY, EXAMPLE), [])

    def test_the_defaults_are_left_out(self):
        same = {
            "example": "901", "verdict": "verified",
            "before": {"symbol": "p.C#g", "static": False, "parameters": [["a", "int"]], "returns": "int"},
            "after": {"symbol": "p.C#g", "static": False, "parameters": [["a", "int"]], "returns": "int"},
            "parts": [
                {"kind": "input", "old": "this", "new": "this", "anchor": "anchored", "decide": "infer", "why": "w"},
                {"kind": "input", "old": "a", "new": "a", "anchor": "anchored", "decide": "infer", "why": "w"},
                {"kind": "result", "relation": "equal", "decide": "infer", "why": "w"},
            ],
        }
        self.assertEqual(A.flags_from_parts(same), {})

    def test_a_reordering_is_written_out(self):
        e = copy.deepcopy(ENTRY)
        e["before"] = {"symbol": "p.New#f", "static": True, "parameters": [["a", "long"], ["b", "int"]], "returns": "long"}
        e["after"] = {"symbol": "p.New#f", "static": True, "parameters": [["b", "int"], ["a", "long"]], "returns": "long"}
        e["parts"] = [
            {"kind": "input", "old": "a", "new": "a", "anchor": "anchored", "decide": "infer", "why": "w"},
            {"kind": "input", "old": "b", "new": "b", "anchor": "anchored", "decide": "infer", "why": "w"},
            {"kind": "result", "relation": "equal", "decide": "infer", "why": "w"},
        ]
        self.assertEqual(A.flags_from_parts(e), {"previousArguments": "a, b"})


class Problems(unittest.TestCase):
    def test_an_anchored_input_maps_to_itself(self):
        e = copy.deepcopy(ENTRY)
        e["parts"][2]["new"] = "n + 1"
        self.assertTrue(any("is anchored" in p for p in A.problems(e, EXAMPLE)))

    def test_a_changed_result_is_a_persons_decision(self):
        e = copy.deepcopy(ENTRY)
        e["parts"][3]["decide"] = "infer"
        self.assertTrue(any("person's decision" in p for p in A.problems(e, EXAMPLE)))

    def test_parts_that_differ_from_the_flags(self):
        e = copy.deepcopy(ENTRY)
        e["parts"][1]["new"] = "this.start"
        self.assertTrue(any("amount to" in p for p in A.problems(e, EXAMPLE)))

    def test_the_inputs_are_the_old_ones_in_order(self):
        e = copy.deepcopy(ENTRY)
        e["parts"][1], e["parts"][2] = e["parts"][2], e["parts"][1]
        self.assertTrue(any("in order" in p for p in A.problems(e, EXAMPLE)))

    def test_a_scope_is_recorded(self):
        example = copy.deepcopy(EXAMPLE)
        example["change"]["intendedInputs"] = "n > 0"
        self.assertTrue(any("scope" in p for p in A.problems(ENTRY, example)))


class TheTable(unittest.TestCase):
    def test_every_entry_agrees_with_its_example(self):
        truth = A.load()
        self.assertEqual(len(truth["examples"]), 19)
        for entry in truth["examples"]:
            self.assertEqual(A.problems(entry, A.example_json(entry["example"])), [], entry["example"])

    def test_the_page_is_current(self):
        self.assertEqual(A.PAGE.read_text(), A.render(A.load()))

    def test_an_unchanged_parameter_is_anchored(self):
        # Every example whose method kept its parameters has every input anchored: none may be shifted.
        for entry in A.load()["examples"]:
            if entry["before"]["parameters"] == entry["after"]["parameters"] and entry["before"]["static"] == entry["after"]["static"]:
                anchors = {p["anchor"] for p in entry["parts"] if p["kind"] == "input" and p["old"] != "this"}
                self.assertEqual(anchors, {"anchored"} if anchors else set(), entry["example"])


class ScoringMethods(unittest.TestCase):
    """Step A2's score from a made-up `align --json` report."""

    RENAMED = {"example": "900", "before": {"symbol": "p.A#f"}, "after": {"symbol": "p.A#g"},
               "parts": [{"kind": "method", "old": "p.A#f", "new": "p.A#g", "how": "renamed", "decide": "infer", "why": "x"}]}
    KEPT = {"example": "901", "before": {"symbol": "p.A#f"}, "after": {"symbol": "p.A#f"}, "parts": []}

    @staticmethod
    def report(before, candidates, leads, change="vanished"):
        return {"methods": [{"before": before, "change": change, "leads": leads,
                             "candidates": [{"after": c, "score": 5, "basis": []} for c in candidates]}]}

    def outcome(self, entry, report):
        return A.score_method(entry, report)[1]

    def test_the_leading_candidate_is_found_or_wrong(self):
        self.assertEqual(self.outcome(self.RENAMED, self.report("p.A#f", ["p.A#g", "p.A#h"], True)), "found")
        self.assertEqual(self.outcome(self.RENAMED, self.report("p.A#f", ["p.A#h", "p.A#g"], True)), "wrong")

    def test_without_a_lead_it_is_asked_if_the_table_is_among_them(self):
        self.assertEqual(self.outcome(self.RENAMED, self.report("p.A#f", ["p.A#h", "p.A#g"], False)), "asked")
        self.assertEqual(self.outcome(self.RENAMED, self.report("p.A#f", ["p.A#h"], False)), "wrong")

    def test_no_candidate_or_no_entry_is_missed(self):
        self.assertEqual(self.outcome(self.RENAMED, self.report("p.A#f", [], False)), "missed")
        self.assertEqual(self.outcome(self.RENAMED, {"methods": []}), "missed")

    def test_a_kept_name_is_found_as_itself_or_with_no_hint(self):
        self.assertEqual(self.outcome(self.KEPT, self.report("p.A#f", ["p.A#f"], True, "changed")), "found")
        self.assertEqual(self.outcome(self.KEPT, {"methods": []}), "found")
        self.assertEqual(self.outcome(self.KEPT, self.report("p.A#f(int)", ["p.A#f(long)"], True)), "found")
        self.assertEqual(self.outcome(self.KEPT, self.report("p.A#f", ["p.B#f"], True)), "wrong")


class ScoringMappings(unittest.TestCase):
    """Step A3's score of input, new-input and result parts from a made-up mapping."""

    @staticmethod
    def mapping(inputs, result=("equal", [], True), free=(), unsupported=()):
        kind, exprs, inferred = result
        return {"inputs": [{"old": old, "anchor": anchor, "leads": leads, "candidates": [{"expression": e} for e in exprs]}
                           for old, anchor, exprs, leads in inputs],
                "result": {"kind": kind, "inferred": inferred, "candidates": [{"expression": e} for e in exprs]},
                "free": list(free), "unsupported": list(unsupported), "proposals": []}

    def outcome(self, part, mapping):
        return A.score_part(part, mapping)[2]

    def test_an_input_is_found_when_its_lead_is_the_table_s(self):
        part = {"kind": "input", "old": "a", "new": "this.start", "anchor": "internal", "decide": "infer"}
        self.assertEqual(self.outcome(part, self.mapping([("a", "internal", ["this . start"], True)])), "found")
        self.assertEqual(self.outcome(part, self.mapping([("a", "internal", ["this.size"], True)])), "wrong")
        self.assertEqual(self.outcome(part, self.mapping([("a", "internal", ["this.size", "this.start"], False)])), "asked")
        self.assertEqual(self.outcome(part, self.mapping([("a", "internal", [], False)])), "missed")
        self.assertEqual(self.outcome(part, None), "missed")

    def test_a_new_input_is_found_when_left_free(self):
        part = {"kind": "new-input", "new": "this.m", "anchor": "new", "decide": "infer"}
        self.assertEqual(self.outcome(part, self.mapping([], free=["this.m"])), "found")
        self.assertEqual(self.outcome(part, self.mapping([])), "wrong")
        self.assertEqual(self.outcome(part, self.mapping([], unsupported=["A4"])), "missed")

    def test_a_person_s_result_can_only_be_asked(self):
        part = {"kind": "result", "relation": "changed", "decide": "person", "holds": "previous == (result <= 0)"}
        question = ("changed", ["previous == (result < 0)", "previous == (result <= 0)"], False)
        self.assertEqual(self.outcome(part, self.mapping([], result=question)), "asked")
        self.assertEqual(self.outcome(part, self.mapping([], result=("changed", ["previous == (result <= 0)"], True))), "wrong")
        self.assertEqual(self.outcome(part, self.mapping([], result=("changed", [], False))), "missed")

    def test_components_compare_as_a_set_of_conjuncts(self):
        part = {"kind": "result", "relation": "components", "decide": "infer", "holds": "previous.a == result.a && previous.b == result.b"}
        self.assertEqual(self.outcome(part, self.mapping([], result=("components", ["previous.b == result.b && previous.a == result.a"], True))), "found")
        self.assertEqual(self.outcome({"kind": "result", "relation": "equal", "decide": "infer"}, self.mapping([], result=("widened", ["previous == result"], True))), "wrong")


class ScoringProofs(unittest.TestCase):
    """Step A3's second half: what the proofs settled for an example's pair, against its verdict."""

    TABLE = {"before_target": "p.Old#f", "before_arguments": "this.base, n", "results_agree_when": "previous == (result > 0)"}
    OTHER = {"before_target": "p.Old#f", "before_arguments": "n, this.base", "results_agree_when": "previous == (result > 0)"}

    def report(self, settled, proposals=(TABLE, OTHER)):
        return {"mappings": [{"before": "p.Old#f", "after": "p.New#f", "proposals": [{"flags": f} for f in proposals]}],
                "proofs": [{"before": "p.Old#f", "after": "p.New#f", "attempts": [{}] * len(proposals), "settled": settled, "summary": ""}]}

    def score(self, settled, verdict="verified", proposals=(TABLE, OTHER)):
        entry = dict(ENTRY, verdict=verdict)
        outcome, _, accepted = A.score_proof(entry, EXAMPLE, self.report(settled, proposals))
        return outcome, accepted

    def test_the_table_s_mapping_proved_is_found(self):
        self.assertEqual(self.score({"outcome": "proved", "proposal": 0, "equivalent": []}), ("found", False))
        self.assertEqual(self.score({"outcome": "proved", "proposal": 1, "equivalent": [0]}), ("found", False), "collapsed with the table's")

    def test_another_mapping_proved_is_wrong_and_accepted(self):
        self.assertEqual(self.score({"outcome": "proved", "proposal": 1, "equivalent": []}), ("wrong", True))

    def test_a_violation_is_found_only_when_nothing_proves(self):
        self.assertEqual(self.score({"outcome": "none-proved"}, verdict="violation"), ("found", False))
        self.assertEqual(self.score({"outcome": "proved", "proposal": 0, "equivalent": []}, verdict="violation"), ("wrong", True))
        self.assertEqual(self.score({"outcome": "asked", "proved": [0, 1]}, verdict="violation"), ("wrong", True))

    def test_a_verified_example_with_nothing_proved_is_missed_and_a_question_asked(self):
        self.assertEqual(self.score({"outcome": "none-proved"}), ("missed", False))
        self.assertEqual(self.score({"outcome": "asked", "proved": [0, 1]}), ("asked", False))
        self.assertEqual(A.score_proof(ENTRY, EXAMPLE, {"mappings": [], "proofs": []})[0], "missed")


if __name__ == "__main__":
    unittest.main()

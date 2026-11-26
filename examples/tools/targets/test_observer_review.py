"""A numbered history must preserve every input, in its registered order."""
import json
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from targets import observer_recipes, observer_review


class NumberedHistoryTest(unittest.TestCase):
    def test_numeric_text_can_be_malformed_empty_or_contain_the_fixture_marker(self):
        texts = ["500", "", "oops", "x using the registered NumberFormat"]
        history = "Parse " + ", ".join("`" + t + "`" for t in texts) + " as Byte and Integer."
        data = observer_review.numeric_history(history)
        self.assertEqual(data["conversions"], [{"text": t, "type": k} for t in texts for k in ("Byte", "Integer")])
        history = "Parse `1,5` as BigDecimal using the registered NumberFormat."
        with self.assertRaisesRegex(observer_recipes.Unsupported, "which NumberFormat"):
            observer_review.numeric_history(history)
        call, = observer_review.numeric_history(history, {"numberFormat": None})["conversions"]
        self.assertEqual(call, {"text": "1,5", "type": "BigDecimal", "format": None})
        for extra in (" then clear the formatter", ", then read its old value", " and Widget"):
            with self.assertRaises(observer_recipes.Unsupported):
                observer_review.numeric_history("Parse `2` as Byte" + extra)

    def test_selection_predicates_follow_the_history_including_empty_sequences(self):
        history = "Use [] twice, first selecting odd values, then selecting values >5."
        data = observer_review.selection_history(history, {"fallback": 0})
        self.assertEqual(data["selections"], [{"values": [], "predicate": {"odd": True}},
                                              {"values": [], "predicate": {"greaterThan": 5}}])
        for history in ("Use [1] twice, first selecting odd values, then selecting primes.",
                        "Use [1] twice, first selecting odd values.",
                        "Use [2147483648] selecting odd values."):
            with self.assertRaises(observer_recipes.Unsupported):
                observer_review.selection_history(history, {"fallback": 99})

    def test_registered_histories_keep_all_six_original_input_domains(self):
        for number in ("445", "458"):
            folder = next(TOOLS.parent.glob(number + "-*"))
            source = json.loads((folder / "comparison.json").read_bytes())["questions"]
            packet = TOOLS.parents[1] / "verification/generated-observers/registrations" / (number + ".json")
            for q, original in zip(source, json.loads(packet.read_bytes())["questions"], strict=True):
                actual = (observer_review.numeric_history(q["history"]) if number == "458"
                          else observer_review.selection_history(q["history"], {"fallback": 99}))
                self.assertEqual([actual], original["inputs"])


if __name__ == "__main__":
    unittest.main()

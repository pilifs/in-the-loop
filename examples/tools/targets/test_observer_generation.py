"""Controls for the reviewed inputs and evidence of generated public observers."""
import base64
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from targets import observer_generation, observer_recipes, observer_rescore


class NumericInputsTest(unittest.TestCase):
    def test_numeric_entry_arguments_keep_null_absence_and_java_text_distinct(self):
        text = "\t\x00\ud800"
        encoded = base64.b64encode(text.encode("utf-16-be", "surrogatepass")).decode()
        fields = encoded + "\tjava.math.BigDecimal"
        plain = {"text": text, "type": "BigDecimal"}
        self.assertEqual(observer_generation.numeric_input(fields), plain)
        self.assertEqual(observer_generation.numeric_input(fields + "\tnull"), {**plain, "format": None})
        with self.assertRaisesRegex(ValueError, "construction"):
            observer_generation.numeric_input(fields + "\tunobserved")
        with self.assertRaisesRegex(ValueError, "numeric class"):
            observer_generation.numeric_input(fields.replace("java.math", "example"))

    def test_format_belongs_to_the_reviewed_overload_and_requires_a_complete_fixture(self):
        from unittest.mock import Mock
        api = Mock()
        owner = "example.Parser#parse"
        fields = ["call.outcome", "return.type", "return.value"]
        entry = owner + observer_recipes.FORMATTED_NUMBER_ENTRY
        api.used = {entry: "bound"}
        call = {"text": "1,5", "type": "BigDecimal"}
        select = lambda entry, call: observer_recipes.select(entry, fields, [{"conversions": [call]}], api)
        with self.assertRaisesRegex(observer_recipes.Unsupported, "text, type, format"):
            select(entry, call)
        fmt = {"locale": "de-DE", "pattern": "0.0", "parseBigDecimal": True}
        recipe = select(entry, {**call, "format": fmt})
        self.assertIn("target, format)", observer_recipes.source(recipe))
        with self.assertRaisesRegex(observer_recipes.Unsupported, "parsing flag"):
            select(entry, {**call, "format": {**fmt, "parseBigDecimal": 1}})
        with self.assertRaisesRegex(observer_recipes.Unsupported, "exactly text, type"):
            select(owner + observer_recipes.NUMBER_ENTRY, {**call, "format": fmt})
        retained = [{**call, "format": fmt, "readAfterReturn": "isParseBigDecimal"}]
        marks = ["UPGRADE-FORMAT-ARG 0\t3", "UPGRADE-NUMBER java.math.BigDecimal\t1.5",
                 "UPGRADE-FORMAT-READ 0\t3\ttrue"]
        def observe(events):
            rows = [["return", "java.math.BigDecimal", "1.5"]]
            observer_generation.formatter_reads(retained, events, rows)
            return rows[0][-1]
        self.assertIs(observe(marks), True)
        for changed in ([marks[0], marks[2], marks[1]], [*marks[:2], marks[2].replace("3", "4")],
                        [*marks[:2], marks[2].replace("0", "1")], [*marks, marks[2]]):
            with self.assertRaises(ValueError):
                observe(changed)


class RescoreTest(unittest.TestCase):
    def test_publication_guard_applies_to_originally_open_claims_and_legacy_receipts(self):
        registration = {"deterministicUnderAssumptions": True, "assumptions": ["fixed inputs"]}
        question = {"status": "open", "entryBindings": {"old": "before", "new": "after"}}
        plan = {"claims": [question]}
        stable = observer_rescore.stable_domain
        self.assertFalse(stable(question, plan, registration))
        self.assertTrue(stable({**question, "rescoreDomainClosed": True}, plan, registration))
        plan["claims"].append({**question, "status": "established", "entryBindings": {"new": "other"}})
        self.assertFalse(stable(question, plan, registration))
        plan["claims"].append({**question, "status": "refuted"})
        self.assertTrue(stable(question, plan, registration))
        self.assertFalse(stable({**question, "rescoreDomainClosed": False}, plan, registration))
        self.assertFalse(stable(question, plan, {**registration, "deterministicUnderAssumptions": False}))


if __name__ == "__main__":
    unittest.main()

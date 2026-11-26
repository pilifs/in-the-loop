"""Controls for the reviewed inputs and evidence of generated public observers."""
import base64
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from targets import observer_generation, observer_recipes


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


if __name__ == "__main__":
    unittest.main()

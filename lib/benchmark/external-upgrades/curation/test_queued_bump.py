import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import queued_bump


class PrivateReproductionTest(unittest.TestCase):
    def test_public_output_contains_only_counts_from_the_original_four_trials(self):
        expected = {"completed": 4, "fresh_exact_named_testcases": 4, "input_verified": True}
        self.assertEqual(queued_bump.coverage(json.dumps(expected), 0), expected)
        missing = {**expected, "fresh_exact_named_testcases": 2}
        self.assertEqual(queued_bump.coverage(json.dumps(missing), 3), missing)
        for value, code in [({**missing, "case": "private-subject"}, 3), (missing, 0), (expected, 3),
                            ({**missing, "fresh_exact_named_testcases": True}, 3),
                            ({**missing, "input_verified": False}, 3), ({**missing, "completed": 3}, 3)]:
            with self.subTest(code=code), self.assertRaises(ValueError):
                queued_bump.coverage(json.dumps(value), code)


if __name__ == "__main__":
    unittest.main()

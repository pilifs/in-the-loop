import json
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import queued_bump
import private_output


class PrivateReproductionTest(unittest.TestCase):
    def test_private_capture_withholds_paths_and_errors_and_releases_only_fixed_scalars(self):
        marker = "unpublished/example-module/pom.xml"
        valid = {"schema": private_output.SCHEMA, "status": "ok", "counts": [2], "flags": [True], "digests": []}
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "captures"
            for tail in ({"schema": private_output.SCHEMA, marker: 3}, {**valid, "counts": [{marker: 7}]},
                         {**valid, "status": marker}, {**valid, "digests": [marker]}):
                stream = b"Traceback: " + marker.encode() + b"\n" + json.dumps(tail).encode() + b"\n"
                result = private_output.capture(io.BytesIO(stream), folder)
                self.assertNotIn(marker, json.dumps(result))
                self.assertNotIn("progress", result)
                retained = folder / (result["capture_id"] + ".log")
                self.assertEqual(retained.read_bytes(), stream)
                self.assertEqual(result["stream_sha256"], hashlib.sha256(stream).hexdigest())
                self.assertEqual(retained.stat().st_mode & 0o777, 0o600)
            long_private_output = (marker.encode() + b" ") * 8000
            stream = long_private_output + b"\n" + json.dumps(valid).encode() + b"\n"
            safe = private_output.capture(io.BytesIO(stream), folder)
            self.assertEqual(safe["progress"], {"status": "ok", "counts": [2], "flags": [True], "digests": []})
            self.assertNotIn(marker, json.dumps(safe))

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

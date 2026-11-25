"""A saved JVM qualification must identify the registered caller, input and invocation."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "merged-pr-links"))
import qualify


class QualifiedHistoryTest(unittest.TestCase):
    def test_checks_compressed_history_against_both_physical_runs(self):
        name = "429-pins.json"
        original = json.loads((HERE / "merged-pr-links/entry-receipts" / name).read_text())
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            receipt = folder / (name + ".gz")
            qualify.write(receipt, original)
            with contextlib.redirect_stdout(io.StringIO()):
                qualify.qualify("429", folder, ["Challenge"], check_only=True, compressed=True)
            # A count of two hits can survive replacing their arguments, live site, or result.
            trial = ("sides", "new", "trials", 0)
            changes = [
                (("entry",), "Unrelated#call()V"),
                (("cases", 0, "args"), ["one"]),
                (("probeClasses", "PublicCaller"), "0" * 64),
                (trial + ("entryInvocations", 0, "observerCodeIndex"), -1),
                (trial + ("observations", 0), {"return": "different"}),
                (trial + ("loadedUpgradeOnEachReplay",), False),
            ]
            for path, replacement in changes:
                with self.subTest(path=path):
                    changed = copy.deepcopy(original)
                    target = changed
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = replacement
                    qualify.write(receipt, changed)
                    with self.assertRaises(ValueError):
                        qualify.qualify("429", folder, ["Challenge"], check_only=True, compressed=True)


if __name__ == "__main__":
    unittest.main()

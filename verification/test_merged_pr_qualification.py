"""A saved JVM qualification must identify the registered caller, input and invocation."""
import contextlib
import copy
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "merged-pr-links"))
import qualify
import audit


class QualifiedHistoryTest(unittest.TestCase):
    def test_spring_overload_and_source_slice_evidence_is_revision_specific(self):
        setup = (HERE.parent / "llm-dlc/loops/spring-framework-pr-links-o01-o20-brief-setup.md").read_text()
        for number in (3, 11, 14):
            with self.subTest(number=number):
                folder, = (HERE.parent / "examples").glob(f"{457 + number}-*")
                deployment, = json.loads((folder / "runtime.json").read_text())["deployments"].values()
                recorded, = json.loads((folder / "observations.json").read_text())["deployments"].values()
                audit.check_spring_deployment(number, deployment, recorded, setup)
                if number == 3:
                    recorded["callerInvocations"]["parent"] = recorded["callerInvocations"]["fix"]
                elif number == 11:
                    recorded["postgresVersionNumber"] = 160004
                else:
                    deployment["sourceSlice"]["blobs"]["parent"] = deployment["sourceSlice"]["blobs"]["fix"]
                with self.assertRaises(ValueError):
                    audit.check_spring_deployment(number, deployment, recorded, setup)

        setup = (HERE.parent / "llm-dlc/loops/spring-framework-pr-links-p01-p30-brief-setup.md").read_text()
        for number in (4, 11, 16, 19):
            with self.subTest(campaign="P", number=number):
                folder, = (HERE.parent / "examples").glob(f"{477 + number}-*")
                deployment = json.loads((folder / "runtime.json").read_text())["deployments"]["pins"]
                recorded = json.loads((folder / "observations.json").read_text())["deployments"]["pins"]
                audit.check_prepared_spring_pair(number, deployment, recorded, setup)
                if number == 4:
                    recorded["callerClassesBySide"]["parent"] = recorded["callerClassesBySide"]["fix"]
                elif number == 11:
                    recorded["preparedSliceClasses"]["fix"] = recorded["preparedSliceClasses"]["parent"]
                elif number == 16:
                    deployment["compileAgainst"] = "fix"
                else:
                    deployment["classpath"]["fix"][1] = deployment["classpath"]["fix"][0]
                with self.assertRaises(ValueError):
                    audit.check_prepared_spring_pair(number, deployment, recorded, setup)

    def test_original_zip_fixture_is_bound_to_the_method_entry(self):
        receipt = HERE / "merged-pr-links/m01-m10/intent/446-pins.json.gz"
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            path = folder / receipt.name
            path.write_bytes(receipt.read_bytes())
            with contextlib.redirect_stdout(io.StringIO()):
                qualify.qualify("446", folder, ["Intent"], check_only=True, compressed=True)
            saved = json.loads(gzip.decompress(path.read_bytes()))
            fixture, = (f for f in saved["originalFixtures"] if f["kind"] == "resource")
            self.assertEqual("COMPRESS-621.zip", fixture["file"])
            fixture["sha256"] = "0" * 64
            qualify.write(path, saved)
            with self.assertRaisesRegex(ValueError, "fixture"):
                qualify.qualify("446", folder, ["Intent"], check_only=True, compressed=True)

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

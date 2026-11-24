"""Controls for finite composition, deployment impact and reuse of original-entry observations."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from targets import change_evidence, change_inventory


class ChangePlanTest(unittest.TestCase):
    def setUp(self):
        self.entry = "a.Client#read(I)I"
        self.cases = [{"args": [str(i)], "expected": {"return": str(i)}} for i in range(2)]
        self.scope = {"entry": self.entry, "cases": self.cases}
        self.trials = [{"input": i, "qualifiedMethodEntries": 2, "observations": [c["expected"]] * 2,
                        "entryInvocations": [{"observerCodeIndex": 4, "dispatchedTo": self.entry}] * 2,
                        "loadedUpgradeOnEachReplay": True} for i, c in enumerate(self.cases)]
        self.binding = {"classpath": ["app", "dep"], "loadedDependencyClasses": ["a.Api"], "trials": self.trials}
        self.report = {**self.scope, "sides": {s: copy.deepcopy(self.binding) for s in ("old", "new")}}

    def test_missing_partition_and_before_entry_stay_open_but_one_original_witness_refutes(self):
        result = change_evidence.compose(self.scope, self.report)
        self.assertEqual((result["status"], result["covered"]), ("established", 2))
        new = self.report["sides"]["new"]["trials"]
        new[0]["beforeEntry"] = [{"throws": "java.lang.LinkageError"}]
        self.assertEqual(change_evidence.compose(self.scope, self.report)["status"], "open")
        new[1]["observations"] = [{"return": "9"}] * 2
        result = change_evidence.compose(self.scope, self.report)
        self.assertEqual((result["status"], result["witness"], result["firstOpenDependency"]), ("refuted", 1, 0))
        self.assertEqual(result["children"][0]["beforeEntry"]["new"], new[0]["beforeEntry"])
        new.append(copy.deepcopy(new[1]))
        with self.assertRaisesRegex(ValueError, "duplicate trial"):
            change_evidence.compose(self.scope, self.report)

    def test_exception_needs_two_escaping_frames_on_the_declared_client(self):
        trial = self.report["sides"]["new"]["trials"][0]
        trial["observations"] = [{"throws": "java.lang.LinkageError"}] * 2
        frame = {"entry": self.entry, "jarSha256": "app", "throws": "java.lang.LinkageError"}
        trial["escapingExceptions"] = [frame, {**frame, "jarSha256": "other"}]
        self.assertEqual(change_evidence.compose(self.scope, self.report)["status"], "open")
        trial["escapingExceptions"][1] = frame
        self.assertEqual(change_evidence.compose(self.scope, self.report)["status"], "refuted")

    def test_approved_difference_applies_only_to_its_input(self):
        changed = {"return": "9"}
        intent = {"allowedChanges": [{"input": 1, "expectedNew": changed}]}
        new = self.report["sides"]["new"]["trials"]
        new[1]["observations"] = [changed] * 2
        self.assertEqual(change_evidence.compose(self.scope, self.report, intent)["status"], "established")
        self.assertEqual(change_evidence.compose(self.scope, self.report, "undecided")["status"], "open")
        new[0]["observations"] = [changed] * 2
        result = change_evidence.compose(self.scope, self.report, intent)
        self.assertEqual((result["status"], result["witness"]), ("refuted", 0))

    def test_exact_reuse_binds_order_jdk_observer_and_checked_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = change_evidence.SideCache(Path(tmp), {"assumptions": ["fixed inputs"]}, {"old": "image", "new": "image2"})
            info = {**self.report, "probeClasses": {"Observer": "bytecode"}, "observerInvocation": {"codeIndices": [4]}}
            files = [Path("application"), Path("provider")]
            self.assertIsNone(cache.lookup("old", files, self.binding, info))
            cache.remember("old", self.binding, info, {0: {"a.Api"}, 1: {"a.Api"}})
            self.assertIsNotNone(cache.lookup("old", files, self.binding, info))
            self.assertIsNone(cache.lookup("new", files, self.binding, info))
            self.assertIsNone(cache.lookup("old", files[::-1], self.binding, info))
            self.assertIsNone(cache.lookup("old", files, self.binding, {**info, "probeClasses": {"Observer": "other"}}))
            stored, = Path(tmp).glob("*.json")
            damaged = json.loads(stored.read_text())
            damaged["evidence"]["trials"].pop()
            stored.write_text(json.dumps(damaged))
            self.assertIsNone(cache.lookup("old", files, self.binding, info))

    def test_added_removed_and_unknown_designated_methods_are_accounted_for(self):
        common = ("a/Client", "call", "()I")
        private = ("a/Client", "unused", "()I")
        removed = ("a/Client", "gone", "()I")
        added = ("a/Client", "added", "()I")
        data = {"public": True, "calls": [], "classSha256": "app"}
        old = ({"a/Client": "app"}, {"META-INF/services/X": ["old"]}, {common: data, removed: data, private: {**data, "public": False}}, [])
        new = (old[0], {"META-INF/services/X": ["new"]}, {common: data, added: data, private: {**data, "public": False}}, [])
        result = change_inventory.inventory(old, new, {"a.Client#unused()I", "missing.C#entry()I"})
        self.assertEqual(result["discoveryMisses"], ["a.Client#unused()I", "missing.C#entry()I"])
        self.assertEqual(result["changedResources"], ["META-INF/services/X"])
        self.assertEqual({r["entry"] for r in result["candidates"] if len(r["sides"]) == 1}, {"a.Client#added()I", "a.Client#gone()I"})


if __name__ == "__main__":
    unittest.main()

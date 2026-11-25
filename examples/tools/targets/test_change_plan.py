"""Controls for finite composition, deployment impact and reuse of original-entry observations."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from targets import change_evidence, change_helpers, change_inventory, integer_codecs, resource_workflows


class ChangePlanTest(unittest.TestCase):
    def test_signed_codec_candidates_respect_instruction_boundaries_and_exception_handlers(self):
        encode = bytes.fromhex("1a 04 78 1a 10 1f 7a 82 ac")
        decode = bytes.fromhex("1a 04 7c 1a 04 7e 74 82 ac")
        self.assertEqual(integer_codecs.roles(encode, 0), {"encoder"})
        self.assertEqual(integer_codecs.roles(decode, 0), {"decoder"})
        self.assertEqual(integer_codecs.roles(decode, 1), set())
        # The byte value for ixor is an operand of bipush rather than an instruction.
        self.assertEqual(integer_codecs.roles(bytes.fromhex("1a 04 7a 10 82 7e ac"), 0), set())

    def setUp(self):
        self.entry = "a.Client#read(I)I"
        self.cases = [{"args": [str(i)], "expected": {"return": str(i)}} for i in range(2)]
        self.scope = {"entry": self.entry, "cases": self.cases}
        self.trials = [{"input": i, "qualifiedMethodEntries": 2, "observations": [c["expected"]] * 2,
                        "entryInvocations": [{"observerCodeIndex": 4, "dispatchedTo": self.entry}] * 2,
                        "loadedUpgradeOnEachReplay": True} for i, c in enumerate(self.cases)]
        self.binding = {"classpath": ["app", "dep"], "loadedDependencyClasses": ["a.Api"], "trials": self.trials}
        self.report = {**self.scope, "sides": {s: copy.deepcopy(self.binding) for s in ("old", "new")}}

    def test_resource_workflow_oracle_distinguishes_prefixes_roots_and_an_unrelated_marker(self):
        names = ["META-INF/first/java.lang.Deprecated", "META-INF/second/java.lang.Deprecated"]
        expect = resource_workflows.expectation
        union = expect("annotation names", names, names, ["primary", "3", "single"])
        self.assertEqual(union.split("=")[1], "UpgradeProbe$First,UpgradeProbe$Last,UpgradeProbe$Shared")
        first = expect("annotation names", names[:1], names, ["primary", "3", "reverse"])
        self.assertEqual(first.split("=")[1], "UpgradeProbe$First,UpgradeProbe$Shared")
        untouched = expect("annotation names", names, names, ["control", "3", "forward"])
        self.assertEqual(untouched, "META-INF/first/java.lang.Override|META-INF/second/java.lang.Override=")
        spi = ["META-INF/services/UpgradeProbe$Marker"]
        one = expect("service instances", spi, spi, ["primary", "1", "single"])
        two = expect("service instances", spi, spi, ["primary", "1", "forward"])
        self.assertIn("UpgradeProbe$Last", two)
        self.assertNotIn("UpgradeProbe$Last", one)

    def test_absent_manifest_providers_bind_the_launch_and_appearance_stops_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            jar, extra = base / "caller.jar", base / "extra.jar"
            def manifest(declaration, indexed=False):
                with zipfile.ZipFile(jar, "w") as archive:
                    archive.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\r\n" + declaration + "\r\n\r\n")
                    if indexed:
                        archive.writestr("META-INF/INDEX.LIST", "JarIndex-Version: 1.0\n")
            manifest("Class-Path: ext\r\n ra.jar " + str(extra), indexed=True)
            found = change_inventory.manifest_classpath([jar], 21)
            self.assertEqual(found["absent"], [str(extra)])
            self.assertEqual(found["declarations"][0]["entries"], ["extra.jar", str(extra)])
            self.assertEqual(found["unresolved"], [])
            self.assertTrue(change_inventory.absences_hold(found["absent"]))
            self.assertTrue(change_inventory.manifest_classpath([jar], 17)["unresolved"])
            with zipfile.ZipFile(extra, "w") as archive:
                archive.writestr("marker.txt", "local provider")
            self.assertFalse(change_inventory.absences_hold(found["absent"]))
            self.assertEqual(change_inventory.manifest_classpath([jar], 21)["unresolved"][0]["reason"], "present implicit provider")
            paired = change_inventory.manifest_classpath([jar, extra], 21)
            self.assertEqual(paired["unresolved"], [])
            self.assertEqual([r["classpathIndex"] for r in paired["bound"]], [1, 1])
            gap = base / "other.jar"
            gap.write_bytes(extra.read_bytes())
            reordered = change_inventory.manifest_classpath([jar, gap, extra], 21)
            self.assertEqual(reordered["unresolved"][0]["reason"], "manifest can change declared search order")
            manifest("Class-Path: https://example.invalid/extra.jar a%20b.jar //host/share.jar")
            self.assertEqual(len(change_inventory.manifest_classpath([jar], 21)["unresolved"]), 3)
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("META-INF/manifest.mf", "Manifest-Version: 1.0\nClass-Path: extra.jar\n\n")
            self.assertEqual(change_inventory.manifest_classpath([jar], 21)["unresolved"][0]["reason"], "present implicit provider")
            with zipfile.ZipFile(jar, "a") as archive:
                archive.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n\n")
            self.assertEqual(change_inventory.manifest_classpath([jar], 21)["unresolved"][0]["reason"], "ambiguous manifest member")
            manifest("Class-Path: extra.jar\x1cother.jar")
            self.assertTrue(change_inventory.manifest_classpath([jar], 21)["unresolved"])

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

    def test_checked_replay_requires_the_proof_on_each_side_and_repetition(self):
        trial = self.report["sides"]["old"]["trials"][0]
        self.report["sides"]["old"]["requiredHelperProof"] = "old-class"
        self.assertEqual(change_evidence.compose(self.scope, self.report)["status"], "open")
        evidence = {"proofKey": "old-class", "applications": [{"args": [4], "result": 4}],
                    "startupArguments": ["entered"]}
        for row in self.report["sides"]["old"]["trials"]:
            row["checkedApplications"] = [copy.deepcopy(evidence), copy.deepcopy(evidence)]
        self.assertEqual(change_evidence.compose(self.scope, self.report)["status"], "established")
        trial["checkedApplications"][1]["proofKey"] = "different-class"
        self.assertEqual(change_evidence.compose(self.scope, self.report)["status"], "open")

    def test_closed_finite_helper_excludes_state_and_decodes_switch_alignment(self):
        # An iconst, a tableswitch with one case at 20, and a return.
        table = bytes.fromhex("03aa0000 00000013 00000000 00000000 00000013 ac")
        self.assertEqual(list(change_inventory.instructions(table)), [(0, 3), (1, 170), (20, 172)])
        self.assertTrue(change_helpers.local_integral_body(table))
        self.assertFalse(change_helpers.local_integral_body(bytes.fromhex("b20001ac")))
        self.assertFalse(change_helpers.local_integral_body(bytes.fromhex("b80001ac")))
        self.assertTrue(change_helpers.local_integral_body(bytes.fromhex("1201ac"), {1: (3, 42)}))
        self.assertFalse(change_helpers.local_integral_body(bytes.fromhex("1201ac"), {1: (17, 42)}))
        with self.assertRaises(ValueError):
            list(change_inventory.instructions(bytes.fromhex("11ff")))

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
            cache = change_evidence.SideCache(Path(tmp), {"assumptions": ["fixed inputs"]},
                                              {"old": "image", "new": "image2"}, defer_writes=True)
            info = {**self.report, "probeClasses": {"Observer": "bytecode"}, "observerInvocation": {"codeIndices": [4]}}
            files = [Path("application"), Path("provider")]
            self.assertIsNone(cache.lookup("old", files, self.binding, info))
            cache.remember("old", self.binding, info, {0: {"a.Api"}, 1: {"a.Api"}})
            self.assertIsNone(cache.lookup("old", files, self.binding, info))
            cache.publish_pending()
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

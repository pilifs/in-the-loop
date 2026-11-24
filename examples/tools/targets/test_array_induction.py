#!/usr/bin/env python3
"""The examples' adapter to array induction (array_induction.py): what it keeps of the method's names for its other
clients, how it reads the rule identity of a record of either format, and what makes a second run the same result.
The method's own tests are lib/python/test_jvm_array_induction.py; the five declared contracts are proved again by
`build.py NNN --array-induction CONTRACT --compare`, as a verification job.

    python3 examples/tools/targets/test_array_induction.py
"""

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
from targets import array_induction, monitor_histories, schedule_reduction, second_opinion, synchronized_map  # noqa: E402
import jvm_array_induction  # noqa: E402
import jvm_disassembly  # noqa: E402

STORED = REPO / "examples/337-jdk-range-fill-alias/records/array-induction/caller-extra-any-length/98d5d5ae53cf2d12ce0c/result.json"


class Adapter(unittest.TestCase):
    def test_the_method_is_the_librarys_and_the_adapter_only_passes_its_names_on(self):
        self.assertTrue(Path(jvm_array_induction.__file__).is_relative_to(REPO / "lib/python"))
        for name in ("Induction", "Instruction", "State", "methods", "range_caller", "solve"):
            self.assertIs(getattr(array_induction, name), getattr(jvm_array_induction, name), name)
        self.assertIs(array_induction.methods, jvm_disassembly.methods)
        # The other readers of a disassembly take it from the library, not from one proof method's adapter.
        for client in (monitor_histories, schedule_reduction, synchronized_map):
            self.assertIs(client.jvm_disassembly, jvm_disassembly, client.__name__)
            self.assertFalse(hasattr(client, "array_induction"), client.__name__)

    def test_second_opinion_distinguishes_bad_hints_from_semantic_evidence(self):
        classify = lambda code, line: second_opinion.classify({"exit": code, "stdout": line}, "", {})
        self.assertEqual(classify(2, "rejected invalid range cut PC"), "invalid evidence")
        self.assertEqual(classify(2, "rejected missing written-prefix cut"), "invalid evidence")
        self.assertEqual(classify(3, "unsupported cut point or cursor local"), "invalid evidence")
        self.assertEqual(classify(3, "unsupported range-fill descriptors"), "unsupported scope")
        self.assertEqual(classify(2, "rejected checked witness [] target 7: returned 0"), "checked counterexample")
        self.assertEqual(classify(127, "checker not found"), "checker unavailable")
        self.assertEqual(second_opinion.conclusion("established", "checked counterexample"), "contradicted")
        self.assertEqual(second_opinion.conclusion("refuted", "independently established"), "contradicted")

    def test_a_record_of_either_format_names_its_rule_implementation(self):
        old = json.loads(STORED.read_text())
        self.assertEqual(old["schema"], "java-array-induction-result/v1")
        # The old digest keeps its meaning: the one file that then held the method and the adapter. No combined
        # digest is made up for it.
        self.assertEqual(array_induction.rules_of(old), {"files": {"examples/tools/targets/array_induction.py": old["rulesSha256"]}, "sha256": None})
        made = jvm_array_induction.implementation(extra=[array_induction.__file__], root=REPO)
        self.assertEqual(sorted(made["files"]), ["examples/tools/targets/array_induction.py", "lib/python/jvm_array_induction.py",
                                                 "lib/python/jvm_disassembly.py"])
        self.assertEqual(array_induction.rules_of({"schema": "java-array-induction-result/v2", "rules": made}), made)
        self.assertNotEqual(made["files"]["examples/tools/targets/array_induction.py"], old["rulesSha256"], "the file is no longer what it was")
        self.assertIsNone(array_induction.rules_of({"schema": "java-array-induction-result/v2"}))

    def test_a_second_run_is_the_same_result_by_its_obligations_and_classes_not_by_its_machine(self):
        stored = json.loads(STORED.read_text())
        again = copy.deepcopy(stored)
        del again["rulesSha256"]
        again.update(schema="java-array-induction-result/v2", rules={"files": {}, "sha256": "0" * 64})
        self.assertEqual(array_induction.differences(again, stored), ([], []), "the rule identity and the schema are not the result")
        self.assertEqual(stored["status"], "unresolved")
        unmet = [o for o in stored["obligations"] if o["expected"] != o["obtained"]]
        self.assertEqual([(o["name"], o["expected"], o["obtained"]) for o in unmet], [("caller read follows from the proved frame", "unsat", "sat")])
        # A negative control that came out proved is another result, and so is another class or another width.
        proved = copy.deepcopy(again)
        next(o for o in proved["obligations"] if o["expected"] != o["obtained"])["obtained"] = "unsat"
        self.assertEqual(array_induction.differences(proved, stored), (["obligations"], []))
        other_class = copy.deepcopy(again)
        next(iter(other_class["classes"].values()))["sha256"] = "f" * 64
        other_class["heapCellBits"] = 64
        self.assertEqual(array_induction.differences(other_class, stored), (["classes", "heapCellBits"], []))
        renamed = copy.deepcopy(again)
        renamed["obligations"][0]["name"] += " (reworded)"
        self.assertEqual(array_induction.differences(renamed, stored)[0], ["obligations"])
        # Another solver build or JDK is said, and is not a different result.
        elsewhere = copy.deepcopy(again)
        elsewhere["solver"] = {**stored["solver"], "version": "Z3 version 9.9.9"}
        elsewhere["javapSha256"] = "1" * 64
        self.assertEqual(array_induction.differences(elsewhere, stored), ([], ["javapSha256", "solver"]))
        # A record from before the widths were recorded cannot stand for one that has them.
        before = {k: v for k, v in stored.items() if k not in ("heapCellBits", "indexBits")}
        self.assertEqual(array_induction.differences(again, before)[0], ["heapCellBits", "indexBits"])


if __name__ == "__main__":
    unittest.main()

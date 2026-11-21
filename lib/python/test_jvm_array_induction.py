#!/usr/bin/env python3
"""Array induction as a library capability (jvm_array_induction.py): the method called on a bound method and a
declared rule, with no example, no target sidecar and no prepared revision anywhere. The classes are compiled here.

The examples that led to it (336, 337, 346) reach the same code through their adapter
(examples/tools/targets/array_induction.py); what is shown here is that a new caller needs none of that. The solver
runs, on formulas of a few hundred terms: `javac`, `javap` and `z3` must be on the PATH, or the tests that need them
are skipped.

    python3 lib/python/test_jvm_array_induction.py
"""

import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jvm_array_induction as induction  # noqa: E402
import jvm_disassembly  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

SEARCH = """public final class Search {
  public static int indexOf(%(cell)s[] array, %(cell)s target) { return indexOf(array, target, 0, array.length); }
  private static int indexOf(%(cell)s[] array, %(cell)s target, int start, int end) {
    for (int i = start; i %(bound)s end; i++) { if (array[i] == target) { return i; } }
    return -1;
  }
}
"""


class Proves(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = all(shutil.which(t) for t in ("javac", "javap", "z3"))
        cls.scratch = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.scratch.name)

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def setUp(self):
        if not self.tools:
            self.skipTest("javac, javap and z3 are not all on the PATH")

    def compiled(self, name, cell="int", bound="<"):
        out = self.dir / name
        (out / "src").mkdir(parents=True)
        (out / "src/Search.java").write_text(SEARCH % {"cell": cell, "bound": bound})
        subprocess.run(["javac", "-d", str(out), str(out / "src/Search.java")], check=True, capture_output=True)
        return out, out / "Search.class"

    @cost("tool")
    def test_a_first_match_search_is_established_for_every_array_length_from_its_class_file_alone(self):
        work, class_file = self.compiled("int")
        proof = induction.prove("javap", class_file, "indexOf", "([II)I", "first-index", work, 60)
        self.assertTrue(proof.passed, [o for o in proof.obligations if o["expected"] != o["obtained"]])
        self.assertEqual((proof.cell_bits, proof.index_bits, proof.rule), (32, 32, "first-index"))
        names = [o["name"] for o in proof.obligations]
        for needed in ("nonempty input domain", "maximal signed length admitted", "entry establishes invariant",
                       "iteration preserves invariant", "nonnegative strictly decreasing Java-int variant",
                       "return the earliest match or minus one", "preserve the input heap"):
            self.assertIn(needed, names)
        self.assertTrue(any(n.startswith("safe array access at ") for n in names))
        self.assertEqual({o["expected"] for o in proof.obligations[:2]}, {"sat"}, "the domain is not empty, and admits the longest array")
        # The certificate is what the solver was given, one check an obligation, and is kept where the caller said.
        self.assertEqual(proof.smt.count("(check-sat)"), len(proof.obligations))
        self.assertEqual((work / "obligations.smt2").read_text(), proof.smt)
        self.assertIn("Z3", proof.solver["version"])
        self.assertIn("indexOf", proof.disassembly)
        self.assertEqual([i["op"] for i in proof.trace][-2:], ["iconst_m1", "ireturn"])

    @cost("tool")
    def test_long_cells_and_int_indices_are_told_apart_by_the_descriptor_alone(self):
        work, class_file = self.compiled("long", cell="long")
        proof = induction.prove("javap", class_file, "indexOf", "([JJ)I", "first-index", work, 60)
        self.assertTrue(proof.passed, [o for o in proof.obligations if o["expected"] != o["obtained"]])
        self.assertEqual((proof.cell_bits, proof.index_bits), (64, 32))
        self.assertIn("distinct elements can have identical low 32 bits", [o["name"] for o in proof.obligations])
        self.assertIn("(_ BitVec 64)", proof.smt)
        # The int search's class file under the long descriptor is refused, not read as the other width.
        _, ints = self.compiled("int-again")
        with self.assertRaises((ValueError, KeyError)):
            induction.prove("javap", ints, "indexOf", "([JJ)I", "first-index", work, 60)

    @cost("tool")
    def test_a_search_that_reads_one_cell_past_the_end_is_not_established_and_says_which_obligation_fails(self):
        work, class_file = self.compiled("past-the-end", bound="<=")
        proof = induction.prove("javap", class_file, "indexOf", "([II)I", "first-index", work, 60)
        self.assertFalse(proof.passed)
        unmet = [(o["name"], o["expected"], o["obtained"]) for o in proof.obligations if o["expected"] != o["obtained"]]
        self.assertTrue(any(name.startswith("safe array access at ") and (want, got) == ("unsat", "sat") for name, want, got in unmet), unmet)

    @cost("tool")
    def test_bytecode_or_a_rule_the_method_does_not_represent_certifies_nothing(self):
        work, class_file = self.compiled("refused")
        with self.assertRaises(ValueError):
            induction.prove("javap", class_file, "indexOf", "([II)I", "range-fill", work, 60)
        with self.assertRaises(ValueError):
            induction.prove("javap", class_file, "indexOf", "([II)I", "no-such-rule", work, 60)
        with self.assertRaises(KeyError):
            induction.prove("javap", class_file, "absent", "([II)I", "first-index", work, 60)

    @cost("tool")
    def test_the_disassembly_is_read_from_the_exact_class_file(self):
        _, class_file = self.compiled("read")
        code, text = jvm_disassembly.methods("javap", class_file)
        self.assertEqual(sorted(k for k in code if k[0] == "indexOf"), [("indexOf", "([II)I"), ("indexOf", "([IIII)I")])
        call = next(i for i in code["indexOf", "([II)I"]["code"] if i.op == "invokestatic")
        self.assertEqual(jvm_disassembly.member_call(call), (None, "indexOf", "([IIII)I"))
        self.assertIs(induction.methods, jvm_disassembly.methods)
        self.assertEqual(induction.Induction.call(call), (None, "indexOf", "([IIII)I"))
        self.assertIn("Compiled from", text)


class Implementation(unittest.TestCase):
    @cost("tool")
    def test_a_result_names_the_files_that_are_the_rule_and_a_change_to_one_changes_the_digest(self):
        said = induction.implementation(root=HERE.parents[1])
        self.assertEqual(sorted(said["files"]), ["lib/python/jvm_array_induction.py", "lib/python/jvm_disassembly.py"])
        self.assertEqual(said["files"]["lib/python/jvm_array_induction.py"], hashlib.sha256((HERE / "jvm_array_induction.py").read_bytes()).hexdigest())
        with tempfile.TemporaryDirectory() as scratch:
            copy = Path(scratch) / "lib/python"
            copy.mkdir(parents=True)
            for name in ("jvm_array_induction.py", "jvm_disassembly.py"):
                shutil.copy(HERE / name, copy / name)
            adapter = Path(scratch) / "adapter.py"
            adapter.write_text("# a caller that decides part of the result\n")
            probe = ("import sys, json; sys.path.insert(0, %r); import jvm_array_induction as i; "
                     "print(json.dumps(i.implementation(extra=[%r], root=%r)))" % (str(copy), str(adapter), scratch))
            import json
            read = lambda: json.loads(subprocess.run([sys.executable, "-I", "-c", probe], capture_output=True, text=True, check=True).stdout)
            before = read()
            self.assertEqual(sorted(before["files"]), ["adapter.py", "lib/python/jvm_array_induction.py", "lib/python/jvm_disassembly.py"])
            self.assertEqual(before["files"]["lib/python/jvm_array_induction.py"], said["files"]["lib/python/jvm_array_induction.py"])
            # Only the rule's own module changes: its digest and the combined one change, and nothing else does.
            with (copy / "jvm_array_induction.py").open("a") as f:
                f.write("\n# one more line of the proof rule\n")
            after = read()
            self.assertNotEqual(after["sha256"], before["sha256"])
            self.assertEqual([k for k in before["files"] if before["files"][k] != after["files"][k]], ["lib/python/jvm_array_induction.py"])
            # And the caller's own file is part of what a result was made by.
            adapter.write_text("# a caller that decides something else\n")
            self.assertNotEqual(read()["files"]["adapter.py"], before["files"]["adapter.py"])


if __name__ == "__main__":
    unittest.main()

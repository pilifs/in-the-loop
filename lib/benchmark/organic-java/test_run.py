#!/usr/bin/env python3
"""The organic benchmark's baseline inputs (run.py): what a baseline's fingerprint covers and a frozen run exports,
by inventory, so that an old pin is read as it always was and a new one covers the modules that moved to lib/python.

    python3 lib/benchmark/organic-java/test_run.py
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.append(str(REPO / "lib/tools"))
from cost_tier import cost  # noqa: E402


def runner():
    spec = importlib.util.spec_from_file_location("organic_java_run", HERE / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tree(root):
    """A small tree with a file of each kind the inventories name."""
    files = {"lib/src/lib.rs": "pub mod a;\n", "lib/models/M.java": "class M {}\n", "lib/python/jvm_array_induction.py": "RULE = 1\n",
             "lib/python/jvmcontract_io.py": "SUPPORTED = (0, 1)\n", "lib/python/test_jvmcontract_io.py": "# a test: never an input\n",
             "examples/tools/targets/array_induction.py": "import jvm_array_induction\n", "examples/tools/build.py": "\n",
             "examples/tools/checker_output.py": "\n", "lib/Cargo.lock": "\n", "lib/Cargo.toml": "\n", "verification/layout.py": "\n"}
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    return root


class Inventories(unittest.TestCase):
    def setUp(self):
        self.run = runner()

    def test_a_pin_without_the_key_is_the_first_inventory_and_an_unknown_one_is_refused(self):
        pin = json.loads((HERE / "baseline.json").read_text())
        self.assertNotIn("inputs", pin, "the pin of 2026-11 was made before the key")
        self.assertIs(self.run.inventory_of(pin), self.run.INVENTORIES[1])
        self.assertNotIn("lib/python", self.run.INVENTORIES[1]["trees"] + self.run.INVENTORIES[1]["export"])
        self.assertIs(self.run.inventory_of({"inputs": 2}), self.run.INVENTORIES[2])
        self.assertEqual(self.run.CURRENT_INVENTORY, 2)
        with self.assertRaises(ValueError):
            self.run.inventory_of({"inputs": 3})

    def test_the_new_inventory_covers_the_extracted_modules_and_changes_when_only_one_of_them_does(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = tree(Path(scratch))
            old, new = self.run.baseline_inputs(1, root), self.run.baseline_inputs(2, root)
            self.assertEqual((old[0], new[0]), (7, 10), "the reader, the rule and layout.py; a test file is never an input")
            with (root / "lib/python/jvm_array_induction.py").open("a") as f:
                f.write("RULE = 2\n")
            self.assertEqual(self.run.baseline_inputs(1, root), old, "the first inventory never saw lib/python: its pins are untouched")
            changed = self.run.baseline_inputs(2, root)
            self.assertEqual(changed[0], new[0])
            self.assertNotEqual(changed[1], new[1], "a changed proof rule is a changed baseline")
            (root / "lib/python/test_jvmcontract_io.py").write_text("# edited\n")
            self.assertEqual(self.run.baseline_inputs(2, root), changed)

    @cost("tool")
    def test_the_pinned_revision_exported_as_its_inventory_says_has_the_pins_fingerprint(self):
        pin = json.loads((HERE / "baseline.json").read_text())
        if subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", pin["revision"] + "^{commit}"], capture_output=True).returncode:
            self.skipTest("the pinned revision is not in this repository")
        with tempfile.TemporaryDirectory() as scratch:
            archive = subprocess.run(["git", "-C", str(REPO), "archive", pin["revision"], *self.run.inventory_of(pin)["export"]],
                                     capture_output=True, check=True)
            subprocess.run(["tar", "-x", "-C", scratch], input=archive.stdout, check=True)
            self.assertEqual(self.run.baseline_inputs(pin.get("inputs", 1), scratch),
                             (pin["engineAndWorkflowFiles"], pin["engineAndWorkflowSha256"]))
            self.assertFalse((Path(scratch) / "lib/python").exists(), "the old revision had no lib/python, and its export asks for none")

    @cost("tool")
    def test_a_frozen_export_loads_its_own_reader_and_rules_with_no_ambient_packages(self):
        probe = ("import sys, json\n"
                 "sys.path.insert(0, 'examples/tools')\n"
                 "import checker_output\n"
                 "from targets import array_induction\n"
                 "import jvm_disassembly\n"
                 "print(json.dumps({'reader': checker_output.wire.__file__, 'rules': array_induction.core.__file__,\n"
                 "                  'disassembly': jvm_disassembly.__file__, 'implementation': array_induction.core.implementation(\n"
                 "                      extra=[array_induction.__file__], root='.')}))\n")
        with tempfile.TemporaryDirectory() as scratch:
            frozen = Path(scratch).resolve()
            for name in self.run.INVENTORIES[2]["export"]:
                source, dest = REPO / name, frozen / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if source.is_dir():
                    shutil.copytree(source, dest, ignore=shutil.ignore_patterns("__pycache__", "target"))
                else:
                    shutil.copyfile(source, dest)
            # -I: no PYTHONPATH, no user site, no current directory on the path. Only the export can answer.
            ran = subprocess.run([sys.executable, "-I", "-c", probe], cwd=frozen, capture_output=True, text=True)
            self.assertEqual(ran.returncode, 0, ran.stderr[-600:])
            loaded = json.loads(ran.stdout)
            for part, file in (("reader", "lib/python/jvmcontract_io.py"), ("rules", "lib/python/jvm_array_induction.py"),
                               ("disassembly", "lib/python/jvm_disassembly.py")):
                self.assertEqual(Path(loaded[part]), frozen / file, "the export's own module, not this checkout's")
            self.assertEqual(sorted(loaded["implementation"]["files"]), ["examples/tools/targets/array_induction.py",
                                                                        "lib/python/jvm_array_induction.py", "lib/python/jvm_disassembly.py"])
            # The first inventory's export of this tree would not start: nothing under examples/ holds the reader.
            shutil.rmtree(frozen / "lib/python")
            without = subprocess.run([sys.executable, "-I", "-c", probe], cwd=frozen, capture_output=True, text=True)
            self.assertNotEqual(without.returncode, 0)
            self.assertIn("jvmcontract_io", without.stderr)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests of runtime.py, owned by the runtime stream with it. Phase 0 left prepare(), run_controls() and run_verifier() as stubs that fail closed with the
named Unsupported result; these tests say so, and the stream rewrites them as it replaces each stub.

  python3 examples/tools/targets/test_runtime.py
"""

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from targets import interfaces, runtime  # noqa: E402
from test_interfaces import plan  # noqa: E402


class StubsFailClosedTest(unittest.TestCase):
    def check(self, value, interface, owner):
        self.assertTrue(interfaces.unsupported(value))
        self.assertEqual((value.interface, value.owner), (interface, owner))
        self.assertIn(owner, value.describe())

    def test_preparation_and_execution(self):
        self.check(runtime.prepare(plan(), "fixed", Path(".")), "prepare", interfaces.RUNTIME)
        self.check(runtime.run_controls(plan(), {}, Path(".")), "run-controls", interfaces.RUNTIME)
        self.check(runtime.run_verifier(plan(), {}, Path(".")), "run-verifier", interfaces.RUNTIME)


if __name__ == "__main__":
    unittest.main()

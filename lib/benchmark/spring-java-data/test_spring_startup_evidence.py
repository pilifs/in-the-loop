"""Counterexamples to consuming a fluent proof on the wrong branch or with a wider int result."""
import unittest

import fluent_launch as launch
import fluent_lines as lines
from targets import runtime_jar


def replace_instruction(data, method, descriptor, at, opcode):
    _, methods, _ = runtime_jar._declarations(data, with_code=True)
    original = methods[method, descriptor][1]
    assert data.count(original) == 1
    changed = bytearray(original)
    changed[at] = opcode
    return data.replace(original, changed)


class FluentLaunchEvidence(unittest.TestCase):
    def test_guard_preserves_both_comparisons_targets_and_conjunction(self):
        caller = (lines.DEST / "FluentLines.jvm-bytecode").read_bytes()
        launch.guard(caller)
        # Invert the first test, branch into a different instruction, change the
        # skipped return, dispatch virtually, or use OR in place of AND.
        for offset, opcode in [(10, 0x99), (21, 4), (22, 3), (25, 0xb6), (32, 0x80)]:
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                launch.guard(replace_instruction(caller, "check", "(I)I", offset, opcode))

    def test_both_original_int_observers_must_be_boolean_valued(self):
        caller = (launch.DEST / "RoleChecks.jvm-bytecode").read_bytes()
        launch.observers(caller)
        for method, descriptor in [("names", "(IZ)I"), ("fluentDecision", "(I)I")]:
            with self.subTest(method=method), self.assertRaisesRegex(ValueError, "outside zero and one"):
                launch.observers(replace_instruction(caller, method, descriptor, -2, 0x05))


if __name__ == "__main__":
    unittest.main()

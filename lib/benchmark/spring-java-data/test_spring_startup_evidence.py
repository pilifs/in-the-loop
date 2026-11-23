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


    def test_pipe_witness_needs_the_original_zero_and_a_replay_that_reports_it(self):
        import fluent_witness as witness
        caller = (witness.DEST / "FluentWitness.jvm-bytecode").read_bytes()
        for method in witness.METHODS:
            witness.qualify_caller(caller)
            for offset, opcode in [(8, 0x99), (10, 4), (11, 3), (14, 5), (15, 0xb6), (18, 0x60)]:
                with self.subTest(method=method, offset=offset), self.assertRaises(ValueError):
                    witness.qualify_caller(replace_instruction(caller, method, "()I", offset, opcode))
            replay = (witness.DEST / (witness.replay_name(method) + ".jvm-bytecode")).read_bytes()
            witness.qualify_replay(replay, method)
            for offset, opcode in [(0, 3), (8, 3), (23, 0xa1), (46, 2), (50, 0xe3), (59, 0xac)]:
                with self.subTest(method=method, offset=offset), self.assertRaises(ValueError):
                    witness.qualify_replay(replace_instruction(replay, "main", "([Ljava/lang/String;)V", offset, opcode), method)


if __name__ == "__main__":
    unittest.main()

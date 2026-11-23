"""The declaring class mirror can block a static call even when the instance is free."""
import unittest

from monitor_schedules import CALLER, WORKER, MIRROR, Program, State, frame
from jvm_disassembly import Instruction


class MonitorSchedulesTest(unittest.TestCase):
    def test_static_call_waits_for_the_class_mirror_and_releases_it_on_return(self):
        program = Program.__new__(Program)
        run = (WORKER, "run", "()V")
        write = (WORKER, "write", "()V")
        program.synchronized = {write}
        program.code = {
            run: {0: (Instruction(0, "invokestatic", "#1", "Method write:()V"), 3)},
            write: {0: (Instruction(0, "return", "", ""), -1)},
        }
        threads = ((frame((CALLER, "observe", "(ZZ)Z"), [0, 1]),), (frame(run, []),))
        held = State(threads, monitors=((-1, 0), (0, 1)), started=True)
        self.assertIsNone(program.step(held, 1, False))
        ignored, _ = program.step(held, 1, True)
        self.assertIsNone(ignored.threads[1][-1].lock)
        free = State(threads, monitors=((0, 1), (-1, 0)), started=True)
        inside, _ = program.step(free, 1, False)
        self.assertEqual(inside.threads[1][-1].lock, MIRROR)
        after, _ = program.step(inside, 1, False)
        self.assertEqual(after.monitors, free.monitors)
        self.assertEqual(after.threads[1][-1].pc, 3)


if __name__ == "__main__":
    unittest.main()

"""without_jbmc.sh, the wrapper gate A8's no-JBMC job runs the native tasks in: inside it no jbmc can be run or found,
the command's own exit code comes back, and it refuses to run anything when its check finds jbmc after all."""

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
WRAPPER = HERE / "without_jbmc.sh"
WHICH = "import shutil, sys; print(shutil.which('jbmc')); sys.exit(7)"


@unittest.skipUnless(shutil.which("bwrap"), "bwrap is not installed")
class WithoutJbmcTest(unittest.TestCase):
    def run_wrapped(self, *command, env=None):
        return subprocess.run([str(WRAPPER), *command], capture_output=True, text=True, env=env, timeout=60)

    def test_no_jbmc_is_found_or_runs_and_the_commands_exit_code_comes_back(self):
        out = self.run_wrapped(sys.executable, "-c", WHICH)
        self.assertEqual(out.returncode, 7, out.stderr)
        self.assertIn("JBMC absent", out.stdout)
        self.assertEqual(out.stdout.splitlines()[-1], "None")
        if shutil.which("jbmc"):
            ran = self.run_wrapped("bash", "-c", "jbmc --version")
            self.assertNotEqual(ran.returncode, 0, "a jbmc on PATH still ran inside the wrapper")

    def test_it_refuses_to_run_the_command_when_jbmc_is_still_there(self):
        if not shutil.which("jbmc"):
            self.skipTest("no jbmc here to find")
        out = self.run_wrapped(sys.executable, "-c", WHICH, env={**os.environ, "WITHOUT_JBMC_INSIDE": "1"})
        self.assertEqual(out.returncode, 2)
        self.assertNotIn("None", out.stdout)

    def test_no_command_is_a_usage_error(self):
        self.assertEqual(self.run_wrapped().returncode, 2)


if __name__ == "__main__":
    unittest.main()

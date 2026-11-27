#!/usr/bin/env python3
"""Tests of jobs/sandbox.py: a command run where the network is off, and the record of how that was shown.

  python3 jobs/test_sandbox.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sandbox  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402

ENFORCES = sandbox.probe()["enforced"]   # whether this machine has bubblewrap and lets it make a network namespace
REACH = ("import socket\ns = socket.socket()\ns.settimeout(3)\n"
         "try:\n    s.connect(('1.1.1.1', 443)); print('connected')\nexcept OSError as e:\n    print('refused:', e.strerror)\n")


class NoNetwork(unittest.TestCase):
    def run_in(self, *args, env=None):
        return subprocess.run([sys.executable, str(HERE / "sandbox.py"), *args], capture_output=True, text=True, env=env)

    @cost("tool")
    @unittest.skipUnless(ENFORCES, "this machine cannot take the network away (no bwrap, or user namespaces refused)")
    def test_a_command_in_the_sandbox_has_a_loopback_interface_and_reaches_nothing(self):
        seen = sandbox.probe()
        self.assertEqual((seen["mode"], seen["enforced"], seen["probe"]["interfaces"]), ("none", True, ["lo"]))
        self.assertNotEqual(seen["probe"]["connect"], "connected")
        self.assertNotEqual(seen["probe"]["lookup"], "resolved")
        with tempfile.TemporaryDirectory() as d:
            evidence = Path(d) / "offline.json"
            ran = self.run_in("run", "--evidence", str(evidence), "--", sys.executable, "-c", REACH)
            self.assertEqual((ran.returncode, ran.stdout.strip()), (0, "refused: Network is unreachable"))
            self.assertEqual(json.loads(evidence.read_text())["probe"]["interfaces"], ["lo"])   # written before the command ran
            # A nested command is in the same namespace: a script that ignores a tool's offline flag has no way out.
            nested = self.run_in("run", "--", "bash", "-c", f"{sys.executable} -c \"{REACH}\"")
            self.assertEqual(nested.stdout.strip(), "refused: Network is unreachable")
            self.assertEqual(self.run_in("run", "--", "bash", "-c", "exit 7").returncode, 7)   # the command's own exit

    @cost("tool")
    @unittest.skipUnless(ENFORCES, "this machine cannot take the network away (no bwrap, or user namespaces refused)")
    def test_a_home_of_its_own_hides_the_real_one_and_keeps_what_the_command_caches(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d) / "home"
            home.mkdir()
            ran = self.run_in("run", "--home", str(home), "--", "bash", "-c", "ls -A ~ | wc -l; mkdir -p ~/.m2 && echo cached > ~/.m2/marker")
            self.assertEqual((ran.returncode, ran.stdout.strip()), (0, "0"))        # nothing of the real home is there
            self.assertEqual((home / ".m2/marker").read_text(), "cached\n")          # and what it wrote is in the folder given

    @cost("tool")
    def test_where_the_network_cannot_be_taken_away_nothing_is_run_and_the_record_says_why(self):
        with tempfile.TemporaryDirectory() as bare:
            for tool in ("bash", "sh"):
                os.symlink(shutil.which(tool), Path(bare) / tool)
            with mock.patch.dict(os.environ, {"PATH": bare}):
                seen = sandbox.probe()
                self.assertEqual((seen["enforced"], "bwrap" in seen["why"]), (False, True))
            marker = Path(bare) / "ran"
            ran = self.run_in("run", "--", "bash", "-c", f"touch {marker}", env={**os.environ, "PATH": bare})
            self.assertEqual((ran.returncode, marker.exists()), (sandbox.REFUSED, False))
            self.assertIn("nothing was run", ran.stderr)
            self.assertEqual(self.run_in("probe", env={**os.environ, "PATH": bare}).returncode, 1)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests of verification-loop.sh with a stand-in pipeline and a stand-in claude: when it looks at the queue."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.append(str(TOOLS.parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

# The queue is a file; a nudge is the file `nudge --where` names, as the pipeline's own is.
PIPELINE = r'''import json, os, sys
queue = os.environ["STANDIN_QUEUE"]
if sys.argv[1:] == ["nudge", "--where"]:
    print(queue + ".nudge")
elif sys.argv[1] == "status":
    print(open(queue).read() if os.path.exists(queue) else
          json.dumps({"pending": [], "running": [], "finished, not collected": [], "collected": []}))
'''
# A run of the verification agent: it empties the queue, as a run that ran everything does.
CLAUDE = r'''#!/usr/bin/env python3
import json, os
open(os.environ["STANDIN_QUEUE"] + ".runs", "a").write("run\n")
os.remove(os.environ["STANDIN_QUEUE"])
print(json.dumps({"type": "result", "subtype": "success", "session_id": "made-up", "result": "The queue is clear."}))
'''
JOB = "20260101-000000-made-up-job  A job  (1 CPU, 1G, ~1m at abc)"


@cost("tool")
class VerificationLoopTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "checkout"
        (self.root / "llm-dlc/tools").mkdir(parents=True)
        (self.root / "verification").mkdir()
        for name in ("verification-loop.sh", "loop-common.sh"):
            shutil.copy(TOOLS / name, self.root / "llm-dlc/tools" / name)
        (self.root / "verification/pipeline.py").write_text(PIPELINE)
        bin = self.root.parent / "bin"
        bin.mkdir()
        (bin / "claude").write_text(CLAUDE)
        (bin / "claude").chmod(0o755)
        self.queue = self.root.parent / "queue.json"
        self.env = {**os.environ, "PATH": f"{bin}:{os.environ['PATH']}", "STANDIN_QUEUE": str(self.queue),
                    "LOOP_ISOLATION": "0", "XDG_RUNTIME_DIR": str(self.root.parent)}

    def start(self, poll):
        self.out = open(self.root.parent / "loop.log", "w+")
        self.addCleanup(self.out.close)
        loop = subprocess.Popen([str(self.root / "llm-dlc/tools/verification-loop.sh")], cwd=self.root, stdin=subprocess.DEVNULL,
                                env={**self.env, "VERIFICATION_LOOP_POLL": str(poll)}, stdout=self.out, stderr=subprocess.STDOUT)
        self.addCleanup(loop.wait)
        self.addCleanup(lambda: loop.poll() is None and loop.kill())
        return loop

    def log(self):
        return (self.root.parent / "loop.log").read_text()

    def until(self, text, seconds):
        end = time.monotonic() + seconds
        while text not in self.log() and time.monotonic() < end:
            time.sleep(0.1)
        return text in self.log()

    def runs(self):
        runs = Path(str(self.queue) + ".runs")
        return len(runs.read_text().splitlines()) if runs.exists() else 0

    def queue_a_job(self):
        self.queue.write_text(json.dumps({"pending": [JOB], "running": [], "finished, not collected": [], "collected": []}))

    @cost("tool")
    def test_a_loop_waiting_for_work_starts_a_run_at_a_nudge_long_before_its_interval(self):
        loop = self.start(poll=300)
        self.assertTrue(self.until("queue clear; checking at a nudge and every 300s", 10), self.log())
        self.queue_a_job()
        time.sleep(3)
        self.assertEqual(self.runs(), 0, "nobody said the queue changed, and the interval is far off")
        Path(str(self.queue) + ".nudge").write_text("now\n")
        self.assertTrue(self.until("run 1: queue clear", 10), self.log())
        self.assertEqual(self.runs(), 1)
        time.sleep(3)
        self.assertEqual(self.runs(), 1, "one nudge, one look")
        loop.send_signal(signal.SIGUSR1)
        self.assertEqual(loop.wait(timeout=10), 0)

    @cost("tool")
    def test_without_a_nudge_the_interval_finds_the_job(self):
        loop = self.start(poll=2)
        self.assertTrue(self.until("queue clear", 10), self.log())
        self.queue_a_job()
        self.assertTrue(self.until("run 1: queue clear", 10), self.log())
        loop.send_signal(signal.SIGUSR1)
        self.assertEqual(loop.wait(timeout=10), 0)


if __name__ == "__main__":
    unittest.main()

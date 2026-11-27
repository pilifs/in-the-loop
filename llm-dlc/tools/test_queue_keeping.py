#!/usr/bin/env python3
"""Tests for queue_keeping.py: the verification queue as the watcher of a run keeps it. It collects what is back and
commits it alone, starts the runner when jobs wait, and says only what the watcher has to hear of.
Run: python3 llm-dlc/tools/test_queue_keeping.py
Everything is made up: test_landing.py's checkout, with a stand-in for verification/pipeline.py whose state is a
folder (a finished job is a folder of results, the jobs waiting are the lines of a file)."""
from __future__ import annotations

import json
import os
import sys
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

import queue_keeping
import run_common
import test_landing

sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

# verification/pipeline.py's stand-in: the runner's state is STATUSES/pipeline, a finished job a folder of results/
# with its result.json, and the jobs waiting the lines of pending; `run` only says it ran.
FAKE_PIPELINE = textwrap.dedent('''\
    import json, os, shutil, sys
    from pathlib import Path
    state = Path(os.environ["STATUSES"]) / "pipeline"
    results = state / "results"
    done = sorted(p.name for p in results.iterdir()) if results.exists() else []
    cmd = sys.argv[1]
    if cmd == "status":
        pending = (state / "pending").read_text().splitlines() if (state / "pending").exists() else []
        print(json.dumps({"pending": pending, "running": [], "finished, not collected": [f"{d} made up" for d in done]}))
    elif cmd == "collect":
        if os.environ.get("STANDIN_COLLECT_FAILS"):
            sys.exit("the collector could not read a result")
        for name in done:
            r = json.loads((results / name / "result.json").read_text())
            dest = Path("verification/results") / name
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "result.json").write_text(json.dumps({**r, "collected": {"conflicts": []}}))
            shutil.rmtree(results / name)
            print(f"{name}: {r['status']}: applied 0, conflicts 0, kept 0")
        print("\\nFor the commit message (python3 llm-dlc/tools/sync.py commit -m ... -m ...):")
        print(f"  Record verification results for {len(done)} job(s)")
        print(f"  Outputs applied for 0 of the {len(done)} job(s).")
    elif cmd == "commit-paths":
        print("verification")
    elif cmd == "wait":
        print("no runner is at work, and nothing waits to be collected")
    elif cmd == "run":
        (state / "ran").write_text("ran\\n")
    elif cmd == "nudge":
        open(state / "nudges", "a").write("nudged\\n")
        print("nudged")
''')


@cost("tool")
class KeepingTheQueue(test_landing.Fixture):
    FILES = {"verification/pipeline.py": FAKE_PIPELINE}
    JOB, OTHER = "20260101-000000-made-up", "20260101-000001-made-up"

    def setUp(self):
        super().setUp()
        self.state = self.statuses / "pipeline"
        self.state.mkdir()
        os.environ.pop("STANDIN_COLLECT_FAILS", None)

    def back(self, job: str, status: str, attention: list[str] = ()) -> None:
        folder = self.state / "results" / job
        folder.mkdir(parents=True)
        (folder / "result.json").write_text(json.dumps({"status": status, "summary": f"{job} {status}",
                                                        "attention": list(attention)}))

    def waiting(self, *rows: str) -> None:
        (self.state / "pending").write_text("".join(f"{row}\n" for row in rows))

    @cost("tool")
    def test_the_watcher_collects_what_is_back_commits_it_alone_and_names_what_needs_triage(self):
        self.back(self.JOB, "passed")
        self.back(self.OTHER, "failed", ["out of memory at 2G"])
        (self.root / "theirs.txt").write_text("another session's, uncommitted\n")
        out = queue_keeping.collect(self.run)
        self.assertEqual([r["id"] for r in out["collected"]], [self.JOB, self.OTHER])
        self.assertEqual([(r["id"], r["attention"]) for r in out["attention"]], [(self.OTHER, ["out of memory at 2G"])])
        committed = self.jj(self.root, "diff", "-r", "@-", "--name-only").split()
        self.assertEqual(committed, [f"verification/results/{self.JOB}/result.json", f"verification/results/{self.OTHER}/result.json"])
        self.assertIn("Record verification results for 2 job(s)", self.head("description"))
        self.assertEqual(self.jj(self.root, "diff", "-r", "@", "--name-only").split(), ["theirs.txt"])  # left where it was
        self.assertIsNone(queue_keeping.collect(self.run))  # nothing waits any more

    def test_a_look_at_the_queue_says_what_came_back_and_which_results_to_triage(self):
        self.back(self.JOB, "passed")
        thing = queue_keeping.tend(self.run)
        self.assertEqual((thing["kind"], [r["id"] for r in thing["collected"]], thing["attention"]), ("results", [self.JOB], []))
        self.assertIn("every job passed", thing["note"])
        self.back(self.OTHER, "failed", ["JBMC gave no verdict"])
        thing = queue_keeping.tend(self.run)
        self.assertEqual([r["id"] for r in thing["attention"]], [self.OTHER])
        self.assertIn("Triage each one in `attention`", thing["note"])
        self.assertIsNone(queue_keeping.tend(self.run))  # a quiet queue is nothing to tell

    def test_results_that_cannot_be_collected_are_told_once_and_tried_again(self):
        self.back(self.JOB, "passed")
        with mock.patch.dict(os.environ, {"STANDIN_COLLECT_FAILS": "1"}):
            thing = queue_keeping.tend(self.run)
            self.assertEqual(thing["kind"], "attention")
            self.assertIn("could not be collected", thing["what"])
            self.assertIn("the collector could not read a result", thing["what"])
            self.assertIsNone(queue_keeping.tend(self.run))  # said once
        self.assertEqual(queue_keeping.tend(self.run)["kind"], "results")  # the next look collects it
        self.assertIsNone(self.run.read()["collectFailed"])

    def test_jobs_waiting_with_no_runner_start_one_and_a_job_that_comes_while_it_runs_is_announced_once(self):
        self.waiting(f"{self.JOB} made up, est. 1 min", "20260101-000009-too-big made up; cannot run here: needs 64G")
        thing = queue_keeping.tend(self.run)
        self.assertEqual((thing["kind"], thing["jobs"]), ("verification", [self.JOB]))  # not the one this machine cannot run
        self.assertIn("started the runner", thing["note"])
        end = time.time() + 20
        while not (self.state / "ran").exists():
            self.assertLess(time.time(), end, "the runner was not started")
            time.sleep(0.1)
        self.run.update(runner={"pid": os.getpid()})  # a runner still at work
        self.waiting(f"{self.JOB} made up, est. 1 min", f"{self.OTHER} made up, est. 1 min")
        status = queue_keeping.queue(self.root)
        self.assertIsNone(queue_keeping.start_runner(self.run, status))
        self.assertIsNone(queue_keeping.start_runner(self.run, status))
        self.assertEqual((self.state / "nudges").read_text(), "nudged\n")  # once
        self.assertEqual(self.run.read()["nudged"], [self.JOB, self.OTHER])
        self.waiting()
        self.assertIsNone(queue_keeping.start_runner(self.run, queue_keeping.queue(self.root)))
        self.assertEqual(self.run.read()["nudged"], [])  # forgotten once nothing waits

    def test_the_queue_is_read_as_data_and_an_answer_that_is_not_json_is_no_queue(self):
        self.waiting(f"{self.JOB} made up")
        self.assertEqual(queue_keeping.queue(self.root)["pending"], [f"{self.JOB} made up"])
        (self.root / "verification/pipeline.py").write_text("print('not JSON')\n")
        self.assertIsNone(queue_keeping.queue(self.root))
        self.assertIsInstance(self.run, run_common.Run)


if __name__ == "__main__":
    unittest.main()

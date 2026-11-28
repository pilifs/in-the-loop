#!/usr/bin/env python3
"""Tests for queue_keeping.py: the verification queue as the watcher of a run keeps it. It collects what is back and
commits it alone, starts the runner when jobs wait, and says only what the watcher has to hear of.
Run: python3 llm-dlc/tools/test_queue_keeping.py
Everything is made up: test_landing.py's checkout, with a stand-in for jobs/pipeline.py whose state is a
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

# jobs/pipeline.py's stand-in: the runner's state is STATUSES/pipeline, a finished job a folder of results/ with its
# result.json, and the jobs not started the lines of pending, each an id and its state; `run` only says it ran.
FAKE_PIPELINE = textwrap.dedent('''\
    import json, os, shutil, sys
    from pathlib import Path
    state = Path(os.environ["STATUSES"]) / "pipeline"
    results = state / "results"
    done = sorted(p.name for p in results.iterdir()) if results.exists() else []
    cmd = sys.argv[1]
    if cmd == "view":
        pending = [line.split(None, 1) for line in (state / "pending").read_text().splitlines()] if (state / "pending").exists() else []
        jobs = [{"id": i, "state": s, "why": None} for i, s in pending] + [{"id": d, "state": "finished", "why": None} for d in done]
        asked = json.loads((state / "requests").read_text()) if (state / "requests").exists() else []
        print(json.dumps({"schema": "itl-job-lifecycle/v1", "idle": not jobs, "runner": {"pid": None, "atWork": False}, "jobs": jobs,
                          "readiness": asked}))
    elif cmd == "resolve":
        asked = json.loads((state / "requests").read_text())
        written, skipped = [], []
        for request in asked:
            if request["unanswered"] and request.get("sourcesNotAllowed"):      # a source the machine has not allowed: no job
                skipped.append({"key": request["key"], "sources": request["sourcesNotAllowed"],
                                "why": "it asks for a source this machine has not been allowed to fetch from"})
            elif request["unanswered"]:
                job = "20260101-000100-resolve-" + request["key"][:12]
                Path("verification/jobs").mkdir(parents=True, exist_ok=True)
                Path(f"verification/jobs/{job}.json").write_text("{}\\n")
                written.append({"key": request["key"], "job": job, "wantedBy": request["wantedBy"]})
                request["unanswered"], request["resolvers"] = False, [job]
        (state / "requests").write_text(json.dumps(asked))
        (state / "pending").write_text("".join(f"{row['job']} queued\\n" for row in written))
        print(json.dumps({"schema": "itl-job-resolve/v1", "written": written, "skipped": skipped}))
    elif cmd == "collect":
        if os.environ.get("STANDIN_COLLECT_FAILS"):
            sys.exit("the collector could not read a result")
        collected = []
        for name in done:
            r = json.loads((results / name / "result.json").read_text())
            dest = Path("verification/results") / name
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "result.json").write_text(json.dumps({**r, "collected": {"conflicts": []}}))
            shutil.rmtree(results / name)
            collected.append({"id": name, "status": r["status"], "applied": [], "conflicts": [], "kept": []})
        hooks = [{"command": "regenerate the table", "exitCode": 3, "output": "the table's source is missing"}] if os.environ.get("STANDIN_HOOK_FAILS") else []
        print(json.dumps({"schema": "itl-job-collect/v1", "collected": collected, "already": [], "hooks": hooks,
                          "commit": {"summary": f"Record verification results for {len(done)} job(s)",
                                     "body": f"Outputs applied for 0 of the {len(done)} job(s)."}}))
    elif cmd == "commit-paths":
        print("verification")
    elif cmd == "run":
        (state / "ran").write_text("ran\\n")
    elif cmd == "nudge":
        open(state / "nudges", "a").write("nudged\\n")
        print("nudged")
''')


@cost("tool")
class KeepingTheQueue(test_landing.Fixture):
    FILES = {"jobs/pipeline.py": FAKE_PIPELINE}
    JOB, OTHER = "20260101-000000-made-up", "20260101-000001-made-up"

    def setUp(self):
        super().setUp()
        self.state = self.statuses / "pipeline"
        self.state.mkdir()
        os.environ.pop("STANDIN_COLLECT_FAILS", None)
        os.environ.pop("STANDIN_HOOK_FAILS", None)

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
        self.waiting(f"{self.JOB} queued", "20260101-000009-too-big unschedulable", "20260101-000010-behind-it blocked")
        thing = queue_keeping.tend(self.run)
        # Not the one this machine cannot run, nor the one that waits for it: nobody starts a runner for those.
        self.assertEqual((thing["kind"], thing["jobs"]), ("verification", [self.JOB]))
        self.assertIn("started the runner", thing["note"])
        end = time.time() + 20
        while not (self.state / "ran").exists():
            self.assertLess(time.time(), end, "the runner was not started")
            time.sleep(0.1)
        self.run.update(runner={"pid": os.getpid()})  # a runner still at work
        self.waiting(f"{self.JOB} queued", f"{self.OTHER} deferred")
        status = queue_keeping.queue(self.root)
        self.assertIsNone(queue_keeping.start_runner(self.run, status))
        self.assertIsNone(queue_keeping.start_runner(self.run, status))
        self.assertEqual((self.state / "nudges").read_text(), "nudged\n")  # once
        self.assertEqual(self.run.read()["nudged"], [self.JOB, self.OTHER])
        self.waiting()
        self.assertIsNone(queue_keeping.start_runner(self.run, queue_keeping.queue(self.root)))
        self.assertEqual(self.run.read()["nudged"], [])  # forgotten once nothing waits

    def test_the_queue_is_read_as_data_and_a_queue_nobody_could_read_is_unknown_not_empty(self):
        self.waiting(f"{self.JOB} queued", f"{self.OTHER} blocked")
        view = queue_keeping.queue(self.root)
        self.assertEqual(([j["id"] for j in view["jobs"]], queue_keeping.left(view)), ([self.JOB, self.OTHER], 1))
        self.waiting()
        self.assertEqual(queue_keeping.left(queue_keeping.queue(self.root)), 0)
        for answer in ("print('not JSON')\n",                                      # the pipeline said something else
                       "import json\nprint(json.dumps({'schema': 'itl-job-lifecycle/v1', 'idle': None, 'jobs': []}))\n"):  # it could not read the queue
            (self.root / "jobs/pipeline.py").write_text(answer)
            self.assertIsNone(queue_keeping.queue(self.root))
            self.assertIsNone(queue_keeping.left(queue_keeping.queue(self.root)))   # unknown: never zero

    @cost("tool")
    def test_a_readiness_request_nothing_answers_is_admitted_once_by_a_commit_and_then_run(self):
        key = "ab" * 32
        (self.state / "requests").write_text(json.dumps([{"key": key, "unanswered": True, "resolvers": [], "wantedBy": [self.JOB]}]))
        self.waiting(f"{self.JOB} waiting")
        thing = queue_keeping.tend(self.run)
        job = "20260101-000100-resolve-" + key[:12]
        self.assertEqual((thing["kind"], thing["jobs"]), ("resolution", [job]))
        self.assertIn("Queue the resolution of 1 readiness request(s) (verification pending)", self.head("description"))
        self.assertEqual(self.jj(self.root, "diff", "-r", "@-", "--name-only").split(), [f"verification/jobs/{job}.json"])
        # It is on its way now: the next look admits nothing more, and starts the runner for it.
        thing = queue_keeping.tend(self.run)
        self.assertEqual((thing["kind"], thing["jobs"]), ("verification", [job]))

    @cost("tool")
    def test_a_request_for_a_source_the_machine_has_not_allowed_is_relayed_to_the_user_and_nothing_is_admitted(self):
        key, source = "cd" * 32, "https://repo.example.org/maven2/"
        (self.state / "requests").write_text(json.dumps([{"key": key, "unanswered": True, "resolvers": [], "wantedBy": [self.JOB],
                                                          "sourcesNotAllowed": [source]}]))
        self.waiting(f"{self.JOB} waiting")
        before = self.head("description")
        thing = queue_keeping.tend(self.run)
        self.assertEqual(thing["kind"], "attention", thing)
        self.assertIn(f"a waiting job asks for a source this machine may not fetch from ({source}): tell the user", thing["note"])
        self.assertIn("never add one to the settings yourself", thing["note"])
        self.assertEqual((self.head("description"), list((self.root / "verification").glob("jobs/*resolve*"))), (before, []))   # nothing written, nothing committed

    def test_a_hook_that_failed_after_the_results_were_collected_is_for_someone_to_look_at(self):
        self.back(self.JOB, "passed")
        with mock.patch.dict(os.environ, {"STANDIN_HOOK_FAILS": "1"}):
            thing = queue_keeping.tend(self.run)
        self.assertEqual([r["status"] for r in thing["collected"]], ["passed"])     # the job passed, and
        self.assertEqual([(a["status"], a["attention"]) for a in thing["attention"]], [("hook failed", ["the table's source is missing"])])
        self.assertIn("Triage each one in `attention`", thing["note"])
        self.assertIsInstance(self.run, run_common.Run)


if __name__ == "__main__":
    unittest.main()

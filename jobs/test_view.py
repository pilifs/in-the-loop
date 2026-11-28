#!/usr/bin/env python3
"""Tests of the lifecycle view (`jobs/pipeline.py view`, itl-job-lifecycle/v1): every job with one state and its
reason, read by the keepers in place of lines of text. Each in a throwaway repository.

  python3 jobs/test_view.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["VERIFY_MACHINE_CONFIG"] = ""
os.environ.setdefault("ITL_ORIGINALS_OFF", "1")
import test_formats  # noqa: E402
from test_formats import DESCRIPTION, Repo  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402

del test_formats   # its tests are its own: only the helper is used here


class View(unittest.TestCase):
    def repo(self, **runner):
        repo = Repo(**runner)
        self.addCleanup(repo.close)
        return repo

    def view(self, repo, *args, check=True):
        proc = repo.pipeline("view", "--rev", "HEAD", *args, check=check)
        return json.loads(proc.stdout), proc.returncode


class EveryJobHasOneStateAndItsReason(View):
    def test_from_a_file_nobody_committed_to_a_collected_result(self):
        repo = self.repo()
        passes = repo.submit2("Passes", "build", "--case", "C1", "--run", "true")
        big = repo.submit2("Asks for more than the runner allows a job", "build", "--memory", "64G", "--run", "true")
        behind = repo.submit2("Needs the big one", "build", "--needs", big, "--run", "true")
        nobody = repo.submit2("Needs a job nobody submitted", "build", "--needs", "20200101-000000-never-submitted", "--run", "true")
        corrupt = repo.dir / "verification/jobs" / "20200102-000000-not-json.json"
        corrupt.write_text("{ this is not JSON")
        repo.commit("jobs")
        later = repo.submit2("Written and not committed", "build", "--run", "true")
        view, code = self.view(repo)
        states = {job["id"]: (job["state"], job["why"]) for job in view["jobs"]}
        self.assertEqual(code, 0)
        self.assertEqual(states[passes], ("queued", None))
        self.assertEqual(states[big][0], "unschedulable")
        # It waits for a job that cannot run here, so it is not going to start either, and the reason goes back to why.
        self.assertEqual(states[behind][0], "blocked")
        self.assertIn(f"{big} cannot run here (unschedulable: needs 64.0 GiB", states[behind][1])
        self.assertEqual(states[nobody][0], "blocked")
        self.assertEqual(states[later][0], "uncommitted")
        head = repo.git("rev-parse", "HEAD")
        self.assertEqual(states["20200102-000000-not-json"][0], "invalid")
        self.assertIn(f"verification/jobs/20200102-000000-not-json.json at {head[:12]}: not JSON", states["20200102-000000-not-json"][1])
        # Every aggregate has its denominator, and the states add up to it.
        totals = view["totals"]
        self.assertEqual((totals["unit"], totals["of"], sum(totals["byState"].values())), ("jobs", len(view["jobs"]), len(view["jobs"])))
        self.assertEqual(view["snapshot"]["revision"], head)
        self.assertEqual(view["snapshot"]["views"]["queue"], "available")
        self.assertIs(view["idle"], False)                    # one job could start
        # Asking for some rows keeps the whole queue's totals, and says how many rows are shown of how many.
        some, _ = self.view(repo, "--state", "blocked", "--state", "invalid")
        self.assertEqual((sorted(j["state"] for j in some["jobs"]), some["shown"], some["totals"]["of"]),
                         (["blocked", "blocked", "invalid"], {"of": totals["of"], "rows": 3}, totals["of"]))
        self.assertEqual([j["id"] for j in self.view(repo, "--case", "C1")[0]["jobs"]], [passes])
        # The lines of before, for whoever reads them: what will not start says so, as an unrunnable job always did.
        legacy = json.loads(repo.pipeline("status", "--rev", "HEAD", "--json").stdout)
        self.assertEqual(sum("; cannot run here:" in row for row in legacy["pending"]), 3)
        self.assertEqual(legacy["not committed"], [later])
        self.assertIn("not a job: verification/jobs/20200102-000000-not-json.json", repo.pipeline("status", "--rev", "HEAD").stdout)
        # Run and collected: finished, then collected, each with its result's questions apart; then nothing is left to do.
        repo.pipeline("run", "--rev", "HEAD")
        job, = self.view(repo, passes)[0]["jobs"]
        self.assertEqual((job["state"], job["result"]["where"], job["result"]["fulfillment"]["state"], len(job["attempts"])),
                         ("finished", "staged", "fulfilled", 1))
        self.assertEqual((job["attempts"][0]["state"], job["attempts"][0]["capture"]), ("finished", "off"))
        repo.pipeline("collect")
        view, _ = self.view(repo)
        job = next(j for j in view["jobs"] if j["id"] == passes)
        self.assertEqual((job["state"], job["result"]["where"], job["result"]["status"]), ("collected", "collected", "passed"))
        self.assertNotIn("execution", job["result"])           # from the index: the receipt is opened when the job is asked for
        self.assertIs(view["idle"], True)                      # what is left cannot start: nobody waits for it

    def test_a_receipt_of_before_the_blocks_were_kept_gets_them_derived(self):
        repo = self.repo()
        job_id = repo.submit("An old receipt", "--run", "true")
        repo.commit("job")
        repo.pipeline("run", "--rev", "HEAD")
        repo.pipeline("collect")
        receipt = repo.collected(job_id) / "result.json"
        old = {k: v for k, v in json.loads(receipt.read_text()).items() if k not in ("execution", "fulfillment", "timing", "declared", "preparationSeconds")}
        receipt.write_text(json.dumps(old))
        job, = self.view(repo, job_id)[0]["jobs"]
        result = job["result"]
        self.assertEqual((result["execution"]["derived"], result["fulfillment"]["state"], result["timing"]["preparation"]["state"]),
                         (True, "fulfilled", "derived"))

    def test_what_a_runner_at_work_holds_back_is_deferred_with_its_reason(self):
        repo = self.repo(workers=1)
        looks = repo.submit2("Looks at the queue from inside the run", "build", "--output", "seen.json", "--priority", "5",
                             "--run", "sleep 2; python3 \"$VERIFY_RUNNER_ROOT/jobs/pipeline.py\" view --rev HEAD > seen.json")
        held = repo.submit2("Has to wait for a worker", "build", "--run", "true")
        repo.commit("jobs")
        repo.pipeline("run", "--rev", "HEAD")
        seen = json.loads((repo.dir / "verification/.state/results" / looks / "outputs/seen.json").read_text())
        states = {job["id"]: job for job in seen["jobs"]}
        self.assertEqual((states[looks]["state"], states[looks]["claim"]["alive"]), ("running", True))
        self.assertEqual((states[held]["state"], states[held]["why"]), ("deferred", "all workers busy"))
        self.assertEqual((seen["runner"]["atWork"], seen["idle"]), (True, False))
        after, _ = self.view(repo)
        self.assertEqual((after["runner"]["atWork"], {j["id"]: j["state"] for j in after["jobs"]}[held]), (False, "finished"))


class ARunnerInAnotherWorkspace(View):
    """A repository has one runner (VF-051), and an agent that submits from a workspace is not where it is: the
    watcher's runner, in the default workspace, runs its jobs. The lock all workspaces share names that runner."""

    def another_workspace(self, claimed=()):
        d = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="another-workspace-")))
        store, root = d / "store", d / "default"
        (root / "verification/.state/claims").mkdir(parents=True)
        store.mkdir()
        for job_id in claimed:
            (root / "verification/.state/claims" / job_id).write_text("{}")
        # A process that reads as a runner: the name of the pipeline's file is in its command line.
        runner = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)", "pipeline.py", "run"])
        self.addCleanup(lambda: (runner.kill(), runner.wait()))
        (store / "verification-runner.lock").write_text(f"pid {runner.pid}, {root}\n")
        return {"VERIFY_REPO_STORE": str(store)}, runner, root

    @cost("tool")
    def test_a_job_its_runner_claimed_is_running_and_one_it_has_not_is_queued_with_the_runner_named(self):
        repo = self.repo()
        claimed = repo.submit2("Claimed by the runner of the default workspace", "build", "--run", "true")
        not_yet = repo.submit2("Committed a moment ago", "build", "--run", "true")
        needs = repo.submit2("Needs the one that is running there", "build", "--needs", claimed, "--run", "true")
        repo.commit("jobs")
        env, runner, root = self.another_workspace(claimed=[claimed])
        view = json.loads(repo.pipeline("view", "--rev", "HEAD", env=env).stdout)
        jobs = {job["id"]: job for job in view["jobs"]}
        self.assertEqual(view["runner"], {"pid": None, "atWork": False, "elsewhere": {"pid": runner.pid, "root": str(root), "running": [claimed]}})
        self.assertEqual((jobs[claimed]["state"], jobs[claimed]["claim"]["where"], jobs[claimed]["claim"]["root"]), ("running", "another-workspace", str(root)))
        self.assertIn(f"claimed by the runner of {root} (pid {runner.pid})", jobs[claimed]["why"])
        self.assertEqual(jobs[not_yet]["state"], "queued")
        self.assertIn("has not claimed it", jobs[not_yet]["why"])
        self.assertEqual(jobs[needs]["state"], "waiting")                 # on a job that is running, wherever it runs
        self.assertIs(view["idle"], False)
        self.assertIn(f"{claimed}  Claimed by the runner of the default workspace  (in the runner of {root}, pid {runner.pid})",
                      repo.pipeline("status", "--rev", "HEAD", env=env).stdout)
        waited = json.loads(repo.pipeline("wait", "--json", "--timeout", "0", env=env).stdout)
        self.assertEqual((waited["outcome"], waited["runner"]["elsewhere"]["pid"]), ("no-runner", runner.pid))
        self.assertIn(f"no runner is at work here (the runner of {root}, pid {runner.pid}, is", repo.pipeline("wait", "--timeout", "0", env=env).stdout)

    @cost("tool")
    def test_a_lock_nobody_holds_any_more_or_this_workspaces_own_names_no_runner_elsewhere(self):
        repo = self.repo()
        job = repo.submit2("Waits for a runner", "build", "--run", "true")
        repo.commit("job")
        env, runner, root = self.another_workspace(claimed=[job])
        runner.kill()
        runner.wait()
        view = json.loads(repo.pipeline("view", "--rev", "HEAD", env=env).stdout)
        self.assertEqual((view["runner"]["elsewhere"], view["jobs"][0]["state"], view["jobs"][0]["why"]), (None, "queued", None))
        # The lock names this workspace: its runner is the one `runner.pid` is about, not one elsewhere.
        mine = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)", "pipeline.py", "run"])
        self.addCleanup(lambda: (mine.kill(), mine.wait()))
        Path(env["VERIFY_REPO_STORE"], "verification-runner.lock").write_text(f"pid {mine.pid}, {repo.dir}\n")
        self.assertIsNone(json.loads(repo.pipeline("view", "--rev", "HEAD", env=env).stdout)["runner"]["elsewhere"])


class WhatTheKeepersRead(View):
    def test_wait_and_collect_say_what_happened_as_data_and_a_hook_that_failed_stays_visible(self):
        repo = self.repo(after_collect=["echo regenerating; exit 3"])
        self.assertEqual(json.loads(repo.pipeline("collect", "--json").stdout)["collected"], [])     # nothing to collect, as data too
        waited = repo.pipeline("wait", "--json", "--timeout", "0")
        self.assertEqual((json.loads(waited.stdout)["outcome"], waited.returncode), ("no-runner", 0))
        wrote = repo.submit2("Writes a file", "build", "--output", "made.txt", "--run", "echo made > made.txt")
        failed = repo.submit2("Fails", "build", "--run", "exit 2")
        repo.commit("jobs")
        repo.pipeline("run", "--rev", "HEAD")
        waited = json.loads(repo.pipeline("wait", "--json", "--timeout", "0").stdout)
        self.assertEqual((waited["schema"], waited["outcome"], sorted(waited["finished"])), ("itl-job-wait/v1", "finished", sorted([wrote, failed])))
        said = json.loads(repo.pipeline("collect", "--json").stdout)
        rows = {row["id"]: row for row in said["collected"]}
        self.assertEqual((said["schema"], rows[wrote]["status"], rows[wrote]["applied"], rows[wrote]["fulfillment"]),
                         ("itl-job-collect/v1", "passed", ["made.txt"], "fulfilled"))
        self.assertEqual((rows[failed]["status"], rows[failed]["fulfillment"]), ("failed", "unfulfilled"))
        self.assertEqual(said["commit"]["summary"], "Record verification results for 2 job(s)")
        self.assertIn("Outputs applied for 1 of the 2 job(s)", said["commit"]["body"])
        # The job passed and its output is applied; the hook after it failed, and that is a fact of its own.
        hook, = said["hooks"]
        self.assertEqual((hook["command"], hook["exitCode"]), ("echo regenerating; exit 3", 3))
        self.assertIn("regenerating", hook["output"])
        view, _ = self.view(repo)
        self.assertEqual(view["lastCollect"]["hooks"][0]["exitCode"], 3)
        self.assertIn("the last collect's hook failed, and nothing has run it since: echo regenerating; exit 3: exit 3",
                      repo.pipeline("status", "--rev", "HEAD").stdout)
        # The text of before is still what a collect prints without --json.
        again = repo.submit2("Another", "build", "--run", "true")
        repo.commit("job")
        repo.pipeline("run", "--rev", "HEAD")
        text = repo.pipeline("collect").stdout
        self.assertIn(f"{again}: passed: applied 0, conflicts 0, kept 0", text)
        self.assertIn("For the commit message", text)


class AQueueThatCouldNotBeRead(View):
    def test_is_unknown_and_never_idle(self):
        repo = self.repo()
        repo.submit2("Waits to run", "build", "--run", "true")
        repo.commit("job")
        (repo.dir / ".git/HEAD").write_text("not a ref\n")       # git can no longer say what the queue's commit is
        proc = repo.pipeline("view", check=False)
        view = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 4)
        self.assertIsNone(view["idle"])
        self.assertTrue(view["snapshot"]["views"]["queue"].startswith("unavailable: "))
        self.assertEqual(view["jobs"], [])
        status = repo.pipeline("status", check=False)
        self.assertIn("NOT READ, so what follows is not the whole queue: queue: unavailable", status.stdout)
        self.assertEqual(json.loads(repo.pipeline("status", "--json", check=False).stdout)["unknown"][0][:18], "queue: unavailable")


if __name__ == "__main__":
    unittest.main()

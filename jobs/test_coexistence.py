#!/usr/bin/env python3
"""The pipeline of before the move and this one, on one repository: the code of the pinned revision
(`b52a084f5d11`, read from git) beside the checkout's, in a throwaway repository.

  python3 jobs/test_coexistence.py

A runner of before is still at work when this code lands, and a rollback puts it back. So: it does not run a job
of the second format, and says so; the two share one exclusion (a state directory has one runner, a repository
has one, whichever code each is, and each sees the other at work); and a job in flight when the runners are
swapped is run again by the other, with nothing of the first attempt lost.
"""

import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
os.environ["VERIFY_MACHINE_CONFIG"] = ""
os.environ.setdefault("ITL_ORIGINALS_OFF", "1")
import pipeline  # noqa: E402
import test_formats  # noqa: E402
from test_formats import Repo  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402

del test_formats   # its tests are its own: only the helper is used here

PINNED = "b52a084f5d11fbf34f82d7a8cce1ea39938afdd3"
OLD_FILES = ("verification/pipeline.py", "verification/layout.py", "verification/capture.py")


class OldAndNew(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(poll_seconds=1)
        self.addCleanup(self.repo.close)
        self.old_code = Path(self.enterContext(tempfile.TemporaryDirectory(prefix="pinned-pipeline-")))
        for name in OLD_FILES:
            (self.old_code / name).parent.mkdir(parents=True, exist_ok=True)
            (self.old_code / name).write_bytes(subprocess.run(["git", "show", f"{PINNED}:{name}"], cwd=ROOT, check=True, capture_output=True).stdout)
        self.state = self.repo.dir / "verification/.state"
        self.started = []
        self.addCleanup(self.stop_all)

    def env(self):
        return dict(os.environ, VERIFY_REPO=str(self.repo.dir))

    def old(self, *args, check=True):
        proc = subprocess.run([sys.executable, str(self.old_code / "verification/pipeline.py"), *args], cwd=self.repo.dir, text=True,
                              capture_output=True, env=self.env(), timeout=120)
        if check and proc.returncode != 0:
            raise AssertionError(f"the pipeline of before {args} exited {proc.returncode}:\n{proc.stdout}\n{proc.stderr}")
        return proc

    def start(self, entry, *args):
        """A runner in the background, in a process group of its own, once it has written its pid into its lock."""
        proc = subprocess.Popen([sys.executable, str(entry), "run", *args], cwd=self.repo.dir, env=self.env(), text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        self.started.append(proc)
        until = time.monotonic() + 30
        while time.monotonic() < until:
            try:
                if int((self.state / "runner.lock").read_text().strip() or 0) == proc.pid:
                    return proc
            except (OSError, ValueError):
                pass
            time.sleep(0.05)
        raise AssertionError("the runner did not start")

    def stop(self, proc, how=signal.SIGTERM):
        if proc.poll() is None:
            os.killpg(proc.pid, how)
        proc.wait(timeout=30)
        proc.stdout.close()

    def stop_all(self):
        for proc in self.started:
            try:
                self.stop(proc, signal.SIGKILL)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass

    def until(self, condition, what, seconds=30):
        end = time.monotonic() + seconds
        while not condition():
            self.assertLess(time.monotonic(), end, what)
            time.sleep(0.1)


class ARunnerOfBefore(OldAndNew):
    @cost("tool")
    def test_does_not_run_a_job_of_the_second_format_and_says_so_and_runs_the_first_format_as_ever(self):
        second = self.repo.submit2("A job only this pipeline reads", "build", "--output", "made.txt", "--run", "echo made > made.txt")
        first = self.repo.submit("A job both read", "--run", "true")
        self.repo.commit("jobs")
        out = self.old("run", "--rev", "HEAD").stdout
        self.assertIn(f"{second}: invalid, not run:", out)
        self.assertIn(f"{first}: passed", out)
        self.assertFalse((self.state / "results" / second).exists())          # nothing of it ran
        self.assertEqual(self.old("status", "--rev", "HEAD").returncode, 0)   # and it reads the queue with such a job in it
        # What this runner wrote for the first-format job, the collector of before takes too.
        self.assertIn(f"{first}: passed", self.old("collect").stdout)
        out = self.repo.pipeline("run", "--rev", "HEAD").stdout
        self.assertIn(f"{second}: passed", out)
        self.assertNotIn(f"{first}: started", out)                            # collected by the other: done


class OneExclusionForBoth(OldAndNew):
    @cost("tool")
    def test_a_state_directory_has_one_runner_whichever_code_it_is_and_each_sees_the_other_at_work(self):
        new_entry, old_entry = self.repo.dir / "jobs/pipeline.py", self.old_code / "verification/pipeline.py"
        before = self.start(old_entry, "--watch", "--rev", "HEAD")
        refused = self.repo.pipeline("run", "--rev", "HEAD", check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("another runner is using", refused.stderr)
        waited = json.loads(self.repo.pipeline("wait", "--json", "--timeout", "0", check=False).stdout)
        self.assertEqual(waited["runner"], {"pid": before.pid, "atWork": True, "elsewhere": None})
        self.assertEqual(json.loads(self.repo.pipeline("view", "--rev", "HEAD").stdout)["runner"]["atWork"], True)
        self.stop(before)
        ours = self.start(new_entry, "--watch", "--rev", "HEAD")
        refused = self.old("run", "--rev", "HEAD", check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("another runner is using", refused.stderr)
        self.assertIn(f"the runner (pid {ours.pid}) is at work", self.old("wait", "--timeout", "0", check=False).stdout)
        self.stop(ours)

    @cost("tool")
    def test_a_repository_has_one_runner_across_its_workspaces_whichever_code_each_runs(self):
        """VF-051's lock, by the name both use: the pipeline of before in one workspace, this one in another."""
        spec = importlib.util.spec_from_file_location("pipeline_of_before", self.old_code / "verification/pipeline.py")
        before = importlib.util.module_from_spec(spec)
        with mock.patch.dict(os.environ, {"VERIFY_REPO": str(self.repo.dir)}):
            spec.loader.exec_module(before)
        with tempfile.TemporaryDirectory() as d:
            default, other = Path(d) / "default", Path(d) / "other"
            (default / ".jj" / "repo").mkdir(parents=True)
            (other / ".jj").mkdir(parents=True)
            (other / ".jj" / "repo").write_text("../../default/.jj/repo")     # as jj writes it in a second workspace
            for first, second in ((before, pipeline), (pipeline, before)):
                with mock.patch.object(first, "ROOT", default):
                    held = first.take_repo_lock(default / "verification" / ".state")
                with mock.patch.object(second, "ROOT", other), self.assertRaises(SystemExit) as refused:
                    second.take_repo_lock(other / "verification" / ".state")
                self.assertIn("another workspace's runner is at work", str(refused.exception))
                held.close()


class ARollbackWithAJobInFlight(OldAndNew):
    @cost("tool")
    def test_the_runner_of_before_runs_the_job_again_and_the_first_attempt_is_still_there(self):
        go = self.state / "go"
        job_id = self.repo.submit("Goes on until it is told", "--output", "made.txt",
                                  "--run", f"echo begun; if [ -f {go} ]; then echo made > made.txt; else sleep 120; fi")
        self.repo.commit("job")
        ours = self.start(self.repo.dir / "jobs/pipeline.py", "--rev", "HEAD")
        attempt_log = lambda: next(iter((self.state / "attempts" / job_id).glob("*/run/logs/*.log")), None)
        self.until(lambda: attempt_log() and "begun" in attempt_log().read_text(), "the job did not begin")
        first_log = attempt_log()
        self.stop(ours, signal.SIGKILL)                                       # the rollback: this runner is gone, mid-job
        go.write_text("go\n")
        # The pipeline of before takes the queue as it finds it: a claim of a runner that is gone, and no result.
        out = self.old("run", "--rev", "HEAD").stdout
        self.assertIn(f"{job_id}: passed", out)
        self.assertIn(f"{job_id}: passed", self.old("collect").stdout)
        self.assertEqual((self.repo.dir / "made.txt").read_text(), "made\n")
        self.assertEqual(self.repo.result(job_id)["status"], "passed")
        # Nothing of the attempt this runner was killed in is gone: its log is where it was, and the view and the
        # audit of this code name it as an attempt that never ended.
        self.assertEqual(first_log.read_text(), "begun\n")
        job, = json.loads(self.repo.pipeline("view", "--rev", "HEAD", job_id).stdout)["jobs"]
        self.assertEqual((job["state"], [a["state"] for a in job["attempts"]]), ("collected", ["interrupted"]))
        audit = subprocess.run([sys.executable, str(HERE / "audit.py"), "--json", "--root", str(self.repo.dir), "--state-dir", str(self.state)],
                               capture_output=True, text=True)
        report = json.loads(audit.stdout)
        self.assertEqual([d for d in report["discrepancies"]], [])
        self.assertIn(job_id, json.dumps(report["live"]))
        # Forward again: this runner starts, finds nothing to run, and leaves the old attempt's bytes alone.
        out = self.repo.pipeline("run", "--rev", "HEAD").stdout
        self.assertNotIn(f"{job_id}: started", out)
        self.assertEqual(first_log.read_text(), "begun\n")


if __name__ == "__main__":
    unittest.main()

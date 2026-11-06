#!/usr/bin/env python3
"""Tests of verification/pipeline.py, each in a throwaway git repository with stub jobs.

  python3 verification/test_pipeline.py      (python3 -m unittest verification/test_pipeline.py)

The systemd tests (hard memory cap, cgroup measurements) run only where `systemd-run --user --scope` works.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pipeline  # noqa: E402

SYSTEMD = pipeline.systemd_works()


class Repo:
    """A git repository with the pipeline in it, committed with plumbing."""

    def __init__(self, **runner):
        self.dir = Path(tempfile.mkdtemp(prefix="pipeline-test-"))
        (self.dir / "verification").mkdir()
        shutil.copy(HERE / "pipeline.py", self.dir / "verification/pipeline.py")
        shutil.copytree(HERE / "schema", self.dir / "verification/schema")
        settings = {"isolation": "none", "workers": 2, "cpus": 4, "memory": "2G", "job_memory_max": "1G", "link": [],
                    "after_collect": [], "keep_workdirs": "never", **runner}
        (self.dir / "verification/pipeline.toml").write_text(
            "[runner]\n" + "".join(f"{k} = {json.dumps(v)}\n" for k, v in settings.items()) +
            '[defaults]\nmemory = "256M"\nduration = "1m"\n')
        (self.dir / ".gitignore").write_text("verification/.state/\n")
        self.git("init", "-q", "-b", "main")
        self.commit("start")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.dir, check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, message):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")
        self.git("add", "-A")
        tree = self.git("write-tree")
        parent = subprocess.run(["git", "rev-parse", "-q", "--verify", "HEAD"], cwd=self.dir, capture_output=True, text=True).stdout.strip()
        commit = subprocess.run(["git", "commit-tree", tree, *(["-p", parent] if parent else []), "-m", message],
                                cwd=self.dir, env=env, check=True, capture_output=True, text=True).stdout.strip()
        self.git("update-ref", "HEAD", commit)
        return commit

    def pipeline(self, *args, check=True):
        proc = subprocess.run([sys.executable, "verification/pipeline.py", *args], cwd=self.dir, text=True,
                              capture_output=True, env=dict(os.environ, VERIFY_REPO=str(self.dir)), timeout=300)
        if check and proc.returncode != 0:
            raise AssertionError(f"pipeline {args} exited {proc.returncode}:\n{proc.stdout}\n{proc.stderr}")
        return proc

    def submit(self, title, *args):
        out = self.pipeline("submit", "--title", title, "--description", "A stub job, for testing the pipeline itself.",
                            "--capability", "test", *args).stdout
        return out.split("verification/jobs/")[1].split(".json")[0]

    def result(self, job_id, collected=True):
        base = self.dir / ("verification/results" if collected else "verification/.state/results")
        return json.loads((base / job_id / "result.json").read_text())

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.close()

    def test_submit_writes_a_valid_job_and_rejects_a_bad_size(self):
        job_id = self.repo.submit("Check the stub", "--run", "true", "--memory", "512M", "--duration", "30s")
        job = json.loads((self.repo.dir / f"verification/jobs/{job_id}.json").read_text())
        self.assertEqual(pipeline.validate(job, "job.schema.json"), [])
        self.assertEqual(job["resources"], {"memory": "512M", "duration": "30s"})
        bad = self.repo.pipeline("submit", "--title", "Bad size", "--description", "A stub job with a size that is not one.",
                                 "--capability", "test", "--run", "true", "--memory", "lots", check=False)
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("not a size", bad.stderr)

    def test_an_uncommitted_job_is_not_run(self):
        job_id = self.repo.submit("Not committed yet", "--run", "true")
        self.repo.pipeline("run", "--rev", "HEAD")
        self.assertFalse((self.repo.dir / "verification/.state/results" / job_id).exists())
        self.assertIn("not committed", self.repo.pipeline("status", "--rev", "HEAD").stdout)

    def test_a_passing_job_brings_its_outputs_back_with_its_verdicts(self):
        (self.repo.dir / "out").mkdir()
        (self.repo.dir / "out/result.txt").write_text("old\n")
        (self.repo.dir / "out/same.txt").write_text("same\n")
        job_id = self.repo.submit(
            "Model check the stub", "--output", "out",
            "--step", "model", "echo 'Model checking completed. No error has been found.'; echo '1,234 distinct states found'; "
                               "echo new > out/result.txt; echo made > out/new.txt")
        source = self.repo.commit("job (verification pending)")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, collected=False)
        self.assertEqual(r["status"], "passed", r["attention"])
        self.assertEqual(r["sourceCommit"], source)
        self.assertEqual(r["attention"], [])
        self.assertEqual(r["steps"][0]["signalCounts"], {"tlc:no-error": 1, "tlc:states": 1})
        self.assertIn("tlc states 1,234", r["summary"])
        self.assertEqual({o["path"]: o["change"] for o in r["outputs"]}, {"out/result.txt": "modified", "out/new.txt": "added"})
        self.assertEqual((self.repo.dir / "out/result.txt").read_text(), "old\n", "nothing is applied before collect")
        self.repo.pipeline("collect")
        self.assertEqual((self.repo.dir / "out/result.txt").read_text(), "new\n")
        self.assertEqual((self.repo.dir / "out/new.txt").read_text(), "made\n")
        r = self.repo.result(job_id)
        self.assertEqual(sorted(r["collected"]["applied"]), ["out/new.txt", "out/result.txt"])
        self.assertIn("+new", (self.repo.dir / f"verification/results/{job_id}/changes.diff").read_text())
        index = json.loads((self.repo.dir / "verification/results/index.json").read_text())
        self.assertEqual([e["id"] for e in index["results"]], [job_id])
        self.assertEqual(self.repo.pipeline("validate").returncode, 0)
        report = json.loads(self.repo.pipeline("report", "--format", "json").stdout)
        self.assertEqual(report["results"][0]["status"], "passed")
        self.assertIn("test", report["calibration"])
        machine = report["results"][0]["machine"]
        self.assertTrue(machine.startswith(socket.gethostname() + " ("), machine)
        self.assertEqual(list(report["calibrationByHost"]), [machine])
        self.assertIn("test", report["calibrationByHost"][machine])
        self.assertIn(f"on {machine})", self.repo.pipeline("report").stdout)
        self.assertIn(f"## Estimates against use on {machine}", self.repo.pipeline("report").stdout)
        self.assertIn("## Passed", self.repo.pipeline("report").stdout)
        self.assertIn("collected: 1", self.repo.pipeline("status", "--rev", "HEAD").stdout)

    def test_build_py_keeps_its_tlc_checkpoints_in_the_pipelines_state(self):
        # build.py reuses a TLC configuration's result only on identical inputs; across jobs they live in the state.
        job_id = self.repo.submit("Show the checkpoint directory", "--output", "where.txt",
                                  "--step", "show", 'echo "$BUILD_CHECKPOINTS" > where.txt')
        self.repo.commit("job")
        outer = os.environ.pop("BUILD_CHECKPOINTS", None)
        try:
            self.repo.pipeline("run", "--rev", "HEAD")
        finally:
            if outer is not None:
                os.environ["BUILD_CHECKPOINTS"] = outer
        self.repo.pipeline("collect")
        self.assertEqual(self.repo.result(job_id)["status"], "passed")
        self.assertEqual(Path((self.repo.dir / "where.txt").read_text().strip()), self.repo.dir / "verification/.state/checkpoints")

    def test_a_failing_step_skips_the_rest_and_its_outputs_are_kept_not_applied(self):
        (self.repo.dir / "o.txt").write_text("before\n")
        job_id = self.repo.submit("Fail the stub", "--output", "o.txt",
                                  "--step", "prove", "echo after > o.txt; echo VERIFICATION FAILED; exit 10",
                                  "--step", "never", "echo should not run")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, collected=False)
        self.assertEqual(r["status"], "failed")
        self.assertEqual([s["status"] for s in r["steps"]], ["failed", "skipped"])
        self.assertEqual(r["steps"][0]["exitCode"], 10)
        self.assertIn("jbmc:refuted×1", r["summary"])
        self.assertTrue(any("exited 10, expected 0" in a for a in r["attention"]))
        self.repo.pipeline("collect")
        self.assertEqual((self.repo.dir / "o.txt").read_text(), "before\n")
        self.assertEqual((self.repo.dir / f"verification/results/{job_id}/outputs/o.txt").read_text(), "after\n")
        report = self.repo.pipeline("report").stdout
        self.assertIn("## Needs attention", report)
        self.assertIn("VERIFICATION FAILED", report)

    def test_an_expected_failure_code_passes(self):
        job_id = self.repo.submit("Expect a violation", "--run", "echo 'Error: Invariant Safe is violated.'; exit 12",
                                  "--expect-exit", "12")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, collected=False)
        self.assertEqual(r["status"], "passed")
        self.assertEqual(r["steps"][0]["signals"][0]["groups"], ["Safe"])

    def test_a_job_past_its_timeout_is_stopped(self):
        job_id = self.repo.submit("Run too long", "--run", "sleep 60", "--timeout", "2s")
        self.repo.commit("job")
        started = time.monotonic()
        self.repo.pipeline("run", "--rev", "HEAD")
        self.assertLess(time.monotonic() - started, 30)
        r = self.repo.result(job_id, collected=False)
        self.assertEqual(r["status"], "timeout")
        self.assertTrue(r["steps"][0]["timedOut"])

    def test_a_job_bigger_than_the_runner_is_deferred_and_stays_pending(self):
        job_id = self.repo.submit("Needs a big machine", "--run", "true", "--memory", "1G", "--memory-limit", "1600M")
        self.repo.commit("job")
        out = self.repo.pipeline("run", "--rev", "HEAD").stdout
        self.assertIn(f"{job_id}: deferred", out)
        self.assertFalse((self.repo.dir / "verification/.state/results" / job_id).exists())
        self.assertIn("cannot run here", self.repo.pipeline("status", "--rev", "HEAD").stdout)
        bigger = self.repo.pipeline("run", "--rev", "HEAD", "--memory", "3G", "--job-memory-max", "2G")
        self.assertIn(f"{job_id}: started", bigger.stdout)

    def test_jobs_run_side_by_side_within_the_budget_and_one_by_one_beyond_it(self):
        a = self.repo.submit("Sleep a", "--run", "sleep 2", "--memory", "512M")
        b = self.repo.submit("Sleep b", "--run", "sleep 2", "--memory", "512M")
        self.repo.commit("jobs")
        self.repo.pipeline("run", "--rev", "HEAD")
        ra, rb = self.repo.result(a, False), self.repo.result(b, False)
        self.assertLess(max(ra["startedAt"], rb["startedAt"]), min(ra["finishedAt"], rb["finishedAt"]), "they overlapped")
        self.repo.pipeline("collect")
        c = self.repo.submit("Sleep c", "--run", "sleep 2", "--memory", "512M")
        d = self.repo.submit("Sleep d", "--run", "sleep 2", "--memory", "512M")
        self.repo.commit("more jobs")
        self.repo.pipeline("run", "--rev", "HEAD", "--workers", "1")
        rc, rd = self.repo.result(c, False), self.repo.result(d, False)
        first, second = sorted([rc, rd], key=lambda r: r["startedAt"])
        self.assertGreaterEqual(second["startedAt"], first["finishedAt"], "one at a time")

    def test_priorities_set_later_reorder_the_queue_and_min_priority_runs_only_those(self):
        a = self.repo.submit("First submitted", "--run", "true")
        b = self.repo.submit("Second submitted", "--run", "true")
        c = self.repo.submit("Third submitted", "--run", "true", "--priority", "1")
        self.repo.commit("jobs")
        self.repo.pipeline("prioritize", b, "--priority", "5", "--reason", "the parser's removal waits on it")
        self.repo.pipeline("prioritize", a, "--priority", "-1", "--reason", "superseded")
        self.assertIn("uncommitted changes", self.repo.pipeline("status", "--rev", "HEAD").stdout)
        self.assertNotEqual(self.repo.pipeline("prioritize", "no-such-job", "--priority", "1", "--reason", "x",
                                               check=False).returncode, 0)
        self.repo.commit("priorities")
        status = self.repo.pipeline("status", "--rev", "HEAD").stdout
        self.assertNotIn("uncommitted changes", status)
        order = [line for line in status.splitlines() if "submitted" in line]
        self.assertEqual([next(i for i in (a, b, c) if i in line) for line in order], [b, c, a])  # file over job's own
        self.assertIn("[priority 5: the parser's removal waits on it]", order[0])
        out = self.repo.pipeline("run", "--rev", "HEAD", "--min-priority", "1", "--workers", "1").stdout
        self.assertLess(out.index(f"{b}: started"), out.index(f"{c}: started"))
        self.assertNotIn(a, out)
        self.assertFalse((self.repo.dir / "verification/.state/results" / a).exists())
        self.assertIn(f"{a}  ", self.repo.pipeline("status", "--rev", "HEAD").stdout.split("running:")[0])  # still pending
        self.repo.pipeline("prioritize", b, "--clear")
        self.assertNotIn(b, self.repo.pipeline("prioritize").stdout)

    def test_a_jobs_steps_do_not_see_the_repository_its_export_is_inside(self):
        # The export lives under .state/work, inside the repository; git there took it for the job's own, and
        # `git apply` skipped every file of a git-format patch (job 20261106-073804).
        job_id = self.repo.submit("No enclosing repository", "--run", "! git rev-parse --git-dir")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        self.assertEqual(self.repo.result(job_id, False)["status"], "passed")

    def test_an_output_changed_since_the_jobs_commit_is_not_overwritten(self):
        (self.repo.dir / "o.txt").write_text("committed\n")
        job_id = self.repo.submit("Write o", "--output", "o.txt", "--run", "echo from-job > o.txt")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        (self.repo.dir / "o.txt").write_text("edited since\n")
        self.repo.pipeline("collect")
        self.assertEqual((self.repo.dir / "o.txt").read_text(), "edited since\n")
        r = self.repo.result(job_id)
        self.assertEqual(r["collected"]["conflicts"], ["o.txt"])
        self.assertTrue(any("rerun the job" in a for a in r["attention"]))

    def test_a_long_log_is_cut_to_its_head_and_tail(self):
        self.repo.close()
        self.repo = Repo(log_max_bytes="4K")
        job_id = self.repo.submit("Talk a lot", "--run", "seq 1 20000; echo VERIFICATION SUCCESSFUL")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, False)
        log = r["steps"][0]["log"]
        self.assertTrue(log["truncated"])
        self.assertGreater(log["bytes"], 100000)
        kept = (self.repo.dir / "verification/.state/results" / job_id / log["path"]).read_text()
        self.assertLess(len(kept), 6000)
        self.assertTrue(kept.startswith("1\n2\n"))
        self.assertIn("VERIFICATION SUCCESSFUL", kept)
        self.assertEqual(r["steps"][0]["signalCounts"], {"jbmc:proved": 1}, "signals come from the whole log")
        self.assertTrue(Path(log["fullLog"]).exists())

    def test_resubmit_keeps_the_job_and_changes_its_resources(self):
        job_id = self.repo.submit("Rerun me", "--run", "true", "--memory", "1G")
        again = self.repo.pipeline("resubmit", job_id, "--memory", "8G").stdout
        new_id = again.split("verification/jobs/")[1].split(".json")[0]
        job = json.loads((self.repo.dir / f"verification/jobs/{new_id}.json").read_text())
        self.assertEqual(job["supersedes"], job_id)
        self.assertEqual(job["resources"]["memory"], "8G")

    def test_a_stopped_runner_cancels_its_job_and_the_next_run_takes_it_again(self):
        job_id = self.repo.submit("Interrupt me", "--run", "sleep 60")
        self.repo.commit("job")
        proc = subprocess.Popen([sys.executable, "verification/pipeline.py", "run", "--rev", "HEAD"], cwd=self.repo.dir,
                                env=dict(os.environ, VERIFY_REPO=str(self.repo.dir)), stdout=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 20
        while not (self.repo.dir / "verification/.state/claims" / job_id).exists() and time.monotonic() < deadline:
            time.sleep(0.2)
        time.sleep(1)
        proc.send_signal(subprocess.signal.SIGINT)
        proc.communicate(timeout=60)
        self.assertEqual(self.repo.result(job_id, False)["status"], "cancelled")
        self.assertFalse((self.repo.dir / "verification/.state/claims" / job_id).exists())
        self.assertIn(job_id, self.repo.pipeline("status", "--rev", "HEAD").stdout.split("running:")[0])
        self.assertIn("nothing to collect", self.repo.pipeline("collect").stdout)

    def test_a_missing_tool_is_an_error_not_a_verdict(self):
        job_id = self.repo.submit("Needs a tool", "--run", "true", "--requires", "no-such-tool-anywhere")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, False)
        self.assertEqual(r["status"], "error")
        self.assertIn("no-such-tool-anywhere", r["attention"][0])


    def test_a_real_world_example_is_not_submitted_as_a_build_py_run(self):
        folder = self.repo.dir / "examples/108-a-real-world-change"
        folder.mkdir(parents=True)
        (folder / "example.json").write_text(json.dumps({"id": "108", "origin": "real-world",
                                                         "approach": {"id": "B9"}, "subject": {"file": "src/A.java"}}))
        proc = self.repo.pipeline("submit", "--title", "A real-world one", "--description", "Should be refused.",
                                  "--capability", "B9", "--example", "108", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("build.py does not run it", proc.stderr)
        self.assertEqual(list((self.repo.dir / "verification/jobs").glob("*.json")) if (self.repo.dir / "verification/jobs").exists() else [], [])


    def add_example(self, example_id, approach, subject, **approach_fields):
        """A constructed example in the stub repo, with build.py beside it to plan its run."""
        tools = self.repo.dir / "examples/tools"
        tools.mkdir(parents=True, exist_ok=True)
        for module in ("build.py", "result_format.py"):  # build.py and the module it imports
            shutil.copy(HERE.parent / "examples/tools" / module, tools / module)
        folder = self.repo.dir / f"examples/{example_id}-a-constructed-change"
        folder.mkdir(parents=True)
        (folder / "example.json").write_text(json.dumps({
            "id": example_id, "origin": "constructed", "approach": {"id": approach, **approach_fields},
            "subject": {"file": subject, "symbol": "a.B#m"}, "change": {"behaviourChangeIntended": False},
            "expected": {"verdict": "verified"}}))

    def submitted(self, example_id, approach):
        job_id = self.repo.submit(f"Example {example_id}", "--capability", approach, "--example", example_id)
        return json.loads(next((self.repo.dir / "verification/jobs").glob(f"{job_id}.json")).read_text())

    def test_a_proof_by_the_tools_own_checker_does_not_require_jbmc(self):
        crosscut = "examples/apps/crosscut/src/main/java/a/B.java"
        self.add_example("124", "B9", crosscut, engine="native")
        self.add_example("128", "B9", crosscut)
        self.add_example("130", "B11", crosscut, engine="auto")
        self.assertEqual(self.submitted("124", "B9")["requires"], ["java", "javac", "jvmcontract"])
        self.assertEqual(self.submitted("128", "B9")["requires"], ["java", "javac", "jvmcontract", "jbmc"])
        # Under auto, JBMC is called when the tool's own checker has no verdict: the job runs where JBMC is.
        self.assertEqual(self.submitted("130", "B11")["requires"], ["java", "javac", "jvmcontract", "jbmc"])

    def test_a_box_office_b12_job_requires_jvmcontract_and_its_build(self):
        self.add_example("110", "B12", "examples/apps/boxoffice/ticketing-service/src/main/java/a/B.java")
        job = self.submitted("110", "B12")
        self.assertEqual(job["requires"], ["java", "javac", "gradle", "jvmcontract"])
        runner = pipeline.Runner.__new__(pipeline.Runner)
        runner.runner = {"build_memory": 6 * 1024 ** 3}
        runner.jvmcontract_cached = lambda source: False
        self.assertEqual(runner.reservation(job, {"memoryLimit": 1024 ** 3}, "HEAD"), 6 * 1024 ** 3)

    def test_an_example_build_py_cannot_run_is_refused_with_the_reason(self):
        self.add_example("150", "B9", "src/main/java/a/B.java")
        proc = self.repo.pipeline("submit", "--title", "No app", "--description", "Should be refused.",
                                  "--capability", "B9", "--example", "150", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("no app builds it", proc.stderr)


@unittest.skipUnless(SYSTEMD, "systemd-run --user --scope is not available here")
class SystemdTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(isolation="systemd")

    def tearDown(self):
        self.repo.close()

    def test_a_step_over_its_memory_limit_is_killed_and_measured(self):
        hog = "python3 -c 'b = bytearray(400 * 1024 * 1024); import time; time.sleep(1)'"
        job_id = self.repo.submit("Use too much memory", "--run", hog, "--memory", "64M", "--memory-limit", "100M")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, False)
        step = r["steps"][0]
        self.assertEqual(r["status"], "out-of-memory", r["summary"])
        self.assertGreaterEqual(step["oomKills"], 1)
        self.assertEqual(step["peakMemoryMeasure"], "cgroup memory.peak")
        self.assertLessEqual(step["peakMemoryBytes"], 100 * 1024 * 1024)

    def test_a_step_in_a_scope_reports_its_cgroup_use(self):
        job_id = self.repo.submit("Use some memory", "--run", "python3 -c 'b = bytearray(50 * 1024 * 1024)'", "--memory", "256M")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, False)
        step = r["steps"][0]
        self.assertEqual(r["status"], "passed", r["attention"])
        self.assertEqual(step["peakMemoryMeasure"], "cgroup memory.peak")
        self.assertGreater(step["peakMemoryBytes"], 50 * 1024 * 1024)
        self.assertIsNotNone(step["cpuThrottledSeconds"])


if __name__ == "__main__":
    unittest.main()

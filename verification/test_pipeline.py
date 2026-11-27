#!/usr/bin/env python3
"""Tests of verification/pipeline.py, each in a throwaway git repository with stub jobs.

  python3 verification/test_pipeline.py      (python3 -m unittest verification/test_pipeline.py)

The systemd tests (hard memory cap, cgroup measurements) run only where `systemd-run --user --scope` works.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import layout  # noqa: E402
import pipeline  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402

SYSTEMD = pipeline.systemd_works()
os.environ["VERIFY_MACHINE_CONFIG"] = ""  # this machine's runner settings are not the test repositories'
os.environ.setdefault("ITL_ORIGINALS_OFF", "1")  # nor is this machine's private archive (verification/capture.py)


class Repo:
    """A git repository with the pipeline in it, committed with plumbing."""

    ENTRY = "verification/pipeline.py"   # the entry point every command here goes through (jobs/test_formats.py: the other)

    def __init__(self, **runner):
        self.dir = Path(tempfile.mkdtemp(prefix="pipeline-test-"))
        (self.dir / "verification").mkdir()
        shutil.copy(HERE / "pipeline.py", self.dir / "verification/pipeline.py")
        shutil.copy(HERE / "layout.py", self.dir / "verification/layout.py")  # where jobs and results are, by id
        shutil.copytree(HERE / "schema", self.dir / "verification/schema")
        # The pipeline itself (jobs/), which verification/pipeline.py is an entry point of: the code and the
        # schemas, not the tests or their fixtures.
        shutil.copytree(HERE.parent / "jobs", self.dir / "jobs", ignore=lambda folder, names: [
            n for n in names if n.startswith("test_") or n in ("fixtures", "__pycache__", "README.md")])
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

    def pipeline(self, *args, check=True, env=None):
        proc = subprocess.run([sys.executable, self.ENTRY, *args], cwd=self.dir, text=True,
                              capture_output=True, env=dict(os.environ, VERIFY_REPO=str(self.dir), **(env or {})), timeout=300)
        if check and proc.returncode != 0:
            raise AssertionError(f"pipeline {args} exited {proc.returncode}:\n{proc.stdout}\n{proc.stderr}")
        return proc

    def submit(self, title, *args, env=None):
        out = self.pipeline("submit", "--title", title, "--description", "A stub job, for testing the pipeline itself.",
                            "--capability", "test", *args, env=env).stdout
        # The job's id, wherever its file went: verification/jobs/ID.json, or under its day with layout.WRITE "shards".
        return out.split("verification/jobs/")[1].split(".json")[0].rsplit("/", 1)[-1]

    def result(self, job_id, collected=True):
        # A collected result is flat or under its day, as its job is (layout.find_result); staged ones are always flat.
        folder = layout.find_result(self.dir, job_id) if collected else self.dir / "verification/.state/results" / job_id
        return json.loads(((folder or self.dir / "verification/results" / job_id) / "result.json").read_text())

    def job_path(self, job_id):
        """A job's file, flat or under its day (layout.find_job), or where a new one would go."""
        return layout.find_job(self.dir, job_id) or layout.new_job(self.dir, job_id)

    def job_rel(self, job_id):
        return self.job_path(job_id).relative_to(self.dir).as_posix()

    def indexed(self):
        """The ids of every collected result in the results index: the flat ones and those of each day."""
        base = self.dir / "verification/results"
        index = json.loads((base / "index.json").read_text())
        ids = [e["id"] for e in index["results"]]
        for day in index.get("shards", []):
            ids += [e["id"] for e in json.loads((base / day / "index.json").read_text())["results"]]
        return ids

    def collected(self, job_id):
        """The folder a collected result is (or would be) in, whichever layout its job took."""
        return layout.find_result(self.dir, job_id) or layout.new_result(self.dir, job_id)

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.close()

    def test_submit_writes_a_valid_job_and_rejects_a_bad_size(self):
        job_id = self.repo.submit("Check the stub", "--run", "true", "--memory", "512M", "--duration", "30s")
        job = json.loads(self.repo.job_path(job_id).read_text())
        self.assertEqual(pipeline.validate(job, "job.schema.json"), [])
        self.assertEqual(job["resources"], {"memory": "512M", "duration": "30s"})
        bad = self.repo.pipeline("submit", "--title", "Bad size", "--description", "A stub job with a size that is not one.",
                                 "--capability", "test", "--run", "true", "--memory", "lots", check=False)
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("not a size", bad.stderr)

    def test_the_machines_settings_are_read_by_every_checkout_and_a_checkouts_own_outrank_them(self):
        """A jj side workspace has no gitignored pipeline.local.toml: the machine's file is what tells it this runner
        allows 24 GB a job, where the committed defaults (here 1 GB) would call a 2 GB job one it cannot run."""
        submit = lambda title: ("submit", "--title", title, "--description", "A stub job, for testing the pipeline itself.",
                                "--capability", "test", "--run", "true", "--memory", "2G")
        alone = self.repo.pipeline(*submit("Two gigabytes, by the defaults")).stdout
        self.assertIn("cannot run it", alone)
        self.assertIn("Judged by the committed defaults alone", alone)
        machine = self.repo.dir.parent / f"{self.repo.dir.name}-machine.toml"
        self.addCleanup(machine.unlink, missing_ok=True)
        machine.write_text('[runner]\nmemory = "48G"\njob_memory_max = "24G"\n')
        with_machine = self.repo.pipeline(*submit("Two gigabytes, by the machine"), env={"VERIFY_MACHINE_CONFIG": str(machine)}).stdout
        self.assertNotIn("cannot run it", with_machine)
        (self.repo.dir / "verification/pipeline.local.toml").write_text('[runner]\njob_memory_max = "1G"\n')
        own = self.repo.pipeline(*submit("Two gigabytes, by the checkout"), env={"VERIFY_MACHINE_CONFIG": str(machine)}).stdout
        self.assertIn("cannot run it", own)  # the checkout's own file outranks the machine's
        self.assertIn(f"This runner's settings: {machine}, {self.repo.dir}/verification/pipeline.local.toml", own)

    def test_a_job_names_the_session_that_submitted_it(self):
        """The loop statistics tie a job to the loop cycle that submitted it by the session it names, so a
        submit without --session names the session Claude Code says is running it."""
        def submitted(title, *args, session, thread=None):
            env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")}
            if session:
                env["CLAUDE_CODE_SESSION_ID"] = session
            if thread:
                env["CODEX_THREAD_ID"] = thread
            with mock.patch.dict(os.environ, env, clear=True):
                job_id = self.repo.submit(title, "--run", "true", *args)
            return json.loads(self.repo.job_path(job_id).read_text())["submitted"]

        self.assertEqual(submitted("From a session", session="made-up-session").get("session"), "made-up-session")
        self.assertEqual(submitted("From a Codex worker", session="parent-session", thread="worker-thread")["session"], "worker-thread")
        self.assertEqual(submitted("Named outright", "--session", "another-made-up", session="made-up-session").get("session"),
                         "another-made-up")
        self.assertNotIn("session", submitted("From a terminal", session=None))

    def test_a_job_whose_result_is_recorded_on_another_head_is_not_run_again(self):
        # As on 2026-11-17: a passed job's result is committed, and the working copy is then moved off that commit
        # (here: the branch goes back, and the result with it), so no result is in sight where the runner looks.
        marks = self.repo.dir.parent / f"{self.repo.dir.name}-ran"
        job_id = self.repo.submit("Run once", "--run", f"echo ran >> {marks}")
        self.repo.commit("job (verification pending)")
        before = self.repo.git("rev-parse", "HEAD")
        self.repo.pipeline("run", "--rev", "HEAD")
        self.repo.pipeline("collect")
        self.repo.commit("Record verification results")
        self.repo.git("branch", "results-left-behind", "HEAD")
        self.repo.git("update-ref", "HEAD", before)
        self.repo.git("reset", "-q", "--hard", before)
        self.addCleanup(lambda: marks.unlink(missing_ok=True))
        self.assertIsNone(layout.find_result(self.repo.dir, job_id))
        out = self.repo.pipeline("run", "--rev", "HEAD").stdout
        self.assertEqual(marks.read_text(), "ran\n", "the job ran once: its result exists, on the other branch")
        self.assertIn(f"note  {job_id}: its result is recorded in commit", out)
        status = self.repo.pipeline("status", "--rev", "HEAD").stdout
        self.assertIn("recorded on another head: 1", status)
        self.assertIn("pending: 0", status)

    def test_a_flat_job_and_a_sharded_job_run_collect_and_report_side_by_side(self):
        shards = {"VERIFY_LAYOUT": "shards"}
        flat = self.repo.submit("Kept flat", "--output", "a.txt", "--run", "echo a > a.txt", env={"VERIFY_LAYOUT": "flat"})
        out = self.repo.pipeline("submit", "--title", "Kept by its day", "--description", "A stub job, for testing the pipeline itself.",
                                 "--capability", "test", "--output", "b.txt", "--run", "echo b > b.txt", env=shards).stdout
        sharded = re.search(r"verification/jobs/\d{4}/\d{2}/\d{2}/([^/\s]+)\.json", out)[1]
        day = f"{sharded[:4]}/{sharded[4:6]}/{sharded[6:8]}"
        job_file = self.repo.dir / f"verification/jobs/{day}/{sharded}.json"
        job = json.loads(job_file.read_text())
        self.assertEqual(pipeline.validate(job, "job.schema.json"), [])
        self.assertTrue((job_file.parent / job["$schema"]).resolve().samefile(self.repo.dir / "verification/schema/job.schema.json"))
        source = self.repo.commit("two jobs (verification pending)")
        self.repo.pipeline("run", "--rev", "HEAD")          # the runner finds both, whatever new jobs take now
        self.assertIn("applied", self.repo.pipeline("collect").stdout)
        self.assertEqual((self.repo.dir / "a.txt").read_text() + (self.repo.dir / "b.txt").read_text(), "a\nb\n")
        kept = self.repo.dir / f"verification/results/{day}/{sharded}"
        result = json.loads((kept / "result.json").read_text())   # beside its job, with the schema at that depth
        self.assertEqual((result["status"], result["sourceCommit"]), ("passed", source))
        self.assertTrue((kept / result["$schema"]).resolve().samefile(self.repo.dir / "verification/schema/result.schema.json"))
        self.assertEqual(self.repo.result(flat)["status"], "passed")
        self.assertFalse((self.repo.dir / "verification/results" / sharded).exists())
        index = json.loads((self.repo.dir / "verification/results/index.json").read_text())  # the flat ones, and where the rest are
        self.assertEqual(({e["id"]: e["result"] for e in index["results"]}, index["shards"]), ({flat: f"{flat}/result.json"}, [day]))
        of_day = json.loads((self.repo.dir / "verification/results" / day / "index.json").read_text())
        self.assertEqual((of_day["shard"], {e["id"]: e["result"] for e in of_day["results"]}), (day, {sharded: f"{day}/{sharded}/result.json"}))
        status = self.repo.pipeline("status", "--rev", "HEAD").stdout
        self.assertIn("collected: 2", status)
        self.assertIn("pending: 0", status)
        self.assertIn(f"verification/results/{day}/{sharded}/result.json", self.repo.pipeline("report", "--format", "json", sharded).stdout)
        paths = self.repo.pipeline("commit-paths").stdout.split()
        self.assertTrue({"a.txt", "b.txt"} <= set(paths), paths)
        self.assertIn("0 file(s) with problems", self.repo.pipeline("validate").stdout)
        # A result recorded on another head is recognised in its shard too: neither job runs a second time.
        self.repo.commit("Record verification results")
        self.repo.git("branch", "results-left-behind", "HEAD")
        self.repo.git("update-ref", "HEAD", source)
        self.repo.git("reset", "-q", "--hard", source)
        self.assertFalse(kept.exists())
        out = self.repo.pipeline("run", "--rev", "HEAD").stdout
        for job_id in (flat, sharded):
            self.assertIn(f"note  {job_id}: its result is recorded in commit", out)
        self.assertIn("recorded on another head: 2", self.repo.pipeline("status", "--rev", "HEAD").stdout)
        # A resubmitted job is a new job: it goes where new jobs go, and the one it supersedes stays where it is.
        again = self.repo.pipeline("resubmit", sharded).stdout.split("wrote ")[1].split(",")[0]
        self.assertEqual(again, layout.job_rel(again.rsplit("/", 1)[-1][:-len(".json")], layout.writes()))
        self.assertTrue(job_file.exists())
        # One id recorded twice and differently is a problem `validate` names.
        (self.repo.dir / f"verification/jobs/{sharded}.json").write_text(json.dumps({**job, "title": "Another job by the same id"}))
        clash = self.repo.pipeline("validate", check=False)
        self.assertIn(f"job {sharded}:", clash.stdout)
        self.assertIn("differ", clash.stdout)

    def test_an_uncommitted_job_is_not_run(self):
        job_id = self.repo.submit("Not committed yet", "--run", "true")
        self.repo.pipeline("run", "--rev", "HEAD")
        self.assertFalse((self.repo.dir / "verification/.state/results" / job_id).exists())
        self.assertIn("not committed", self.repo.pipeline("status", "--rev", "HEAD").stdout)

    def test_a_result_records_the_runners_machine_name_in_place_of_the_hostname(self):
        # A machine named in pipeline.local.toml is recorded under that name, and its hostname nowhere in the result.
        (self.repo.dir / "verification/pipeline.local.toml").write_text('[runner]\nmachine_name = "test-box"\nlog_max_bytes = "1K"\n')
        job_id = self.repo.submit("Name the machine", "--step", "long", "seq 1 2000")
        self.repo.commit("job (verification pending)")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, collected=False)
        self.assertEqual((r["runner"]["host"], r["environment"]["host"]), ("test-box", "test-box"))
        self.assertIn("kept on test-box at", (self.repo.dir / "verification/.state/results" / job_id / "logs/1-long.log").read_text())
        self.assertNotIn(socket.gethostname(), (self.repo.dir / "verification/.state/results" / job_id / "result.json").read_text())
        self.assertTrue(pipeline.machine_label(r).startswith("test-box ("))

    def test_a_diff_over_the_commit_limit_is_kept_gzipped_or_as_a_summary(self):
        # VF-020: jj leaves a new file over 1 MiB out of every commit, so a collected changes.diff must fit under it.
        import gzip
        lines = "mkdir -p out; for i in $(seq 1 60); do seq 1 5000 > out/n$i.txt; done"
        random = "mkdir -p out; for i in $(seq 1 20); do head -c 57000 /dev/urandom | base64 > out/r$i.txt; done"
        for name, script, kept in (("compressible", lines, "changes.diff.gz"), ("random", random, "changes.stat")):
            with self.subTest(name):
                (self.repo.dir / "out").mkdir(exist_ok=True)
                job_id = self.repo.submit(f"A large diff, {name}", "--output", "out", "--step", "make", script)
                self.repo.commit(f"{name} job (verification pending)")
                self.repo.pipeline("run", "--rev", "HEAD")
                raw = (self.repo.dir / "verification/.state/results" / job_id / "changes.diff").stat().st_size
                self.assertGreater(raw, pipeline.DIFF_MAX_BYTES)
                self.repo.pipeline("collect")
                dest = self.repo.collected(job_id)
                r = self.repo.result(job_id)
                self.assertEqual(r["status"], "passed", r["attention"])
                self.assertFalse((dest / "changes.diff").exists())
                self.assertEqual(r["changesDiff"], kept)
                self.assertEqual(r["collected"]["changesDiff"]["bytes"], raw)
                self.assertEqual(r["collected"]["changesDiff"]["kept"], kept)
                self.assertLessEqual((dest / kept).stat().st_size, pipeline.DIFF_MAX_BYTES)
                if kept == "changes.diff.gz":
                    text = gzip.decompress((dest / kept).read_bytes()).decode()
                    self.assertEqual(len(text.encode()), raw)
                    self.assertIn("+++ b/out/n60.txt", text)
                else:
                    stat = (dest / kept).read_text()
                    self.assertIn("out/r20.txt | +", stat)
                    self.assertIn(f"{raw:,} bytes", stat)
                self.assertEqual(self.repo.pipeline("validate").returncode, 0)

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
        self.assertIn("+new", (self.repo.collected(job_id) / "changes.diff").read_text())
        self.assertEqual(self.repo.indexed(), [job_id])
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
        self.assertEqual((self.repo.collected(job_id) / "outputs/o.txt").read_text(), "after\n")
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

    def test_a_job_that_stalls_past_its_timeout_is_stopped(self):
        # Silent and idle past its timeout for the whole stall window: a hang, stopped long before the sleep would end.
        (self.repo.dir / "verification/pipeline.local.toml").write_text('[runner]\nstall_window = "3s"\n')
        job_id = self.repo.submit("Hang", "--run", "sleep 120", "--timeout", "2s")
        self.repo.commit("job")
        started = time.monotonic()
        self.repo.pipeline("run", "--rev", "HEAD")
        self.assertLess(time.monotonic() - started, 40)
        r = self.repo.result(job_id, collected=False)
        self.assertEqual(r["status"], "timeout")
        step = r["steps"][0]
        self.assertTrue(step["timedOut"])
        self.assertEqual(step["stoppedFor"], "stalled")
        self.assertTrue(any("stalled past its 2" in a for a in r["attention"]), r["attention"])

    def test_a_job_still_working_past_its_timeout_is_left_to_finish(self):
        # Output keeps coming past the timeout and past several stall windows: the step finishes and passes.
        (self.repo.dir / "verification/pipeline.local.toml").write_text('[runner]\nstall_window = "2s"\n')
        job_id = self.repo.submit("Slow but working", "--run", "for i in $(seq 1 8); do echo $i; sleep 1; done", "--timeout", "1s")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, collected=False)
        self.assertEqual(r["status"], "passed", r["attention"])
        step = r["steps"][0]
        self.assertTrue(step["overranTimeout"])
        self.assertIsNone(step["stoppedFor"])
        self.assertGreater(step["wallSeconds"], 7)
        self.assertTrue(any("was left to finish" in a for a in r["attention"]), r["attention"])

    def test_a_silent_job_using_cpu_past_its_timeout_is_left_to_finish(self):
        # No output, but CPU in use: a solver at work, not a hang.
        (self.repo.dir / "verification/pipeline.local.toml").write_text('[runner]\nstall_window = "2s"\n')
        job_id = self.repo.submit("Busy and silent", "--run", "end=$((SECONDS+7)); while [ $SECONDS -lt $end ]; do :; done",
                                  "--timeout", "1s")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, collected=False)
        self.assertEqual(r["status"], "passed", r["attention"])
        self.assertTrue(r["steps"][0]["overranTimeout"])

    def test_a_job_still_working_at_the_ceiling_is_stopped(self):
        (self.repo.dir / "verification/pipeline.local.toml").write_text('[runner]\nstall_window = "2s"\nmax_timeout = "4s"\n')
        job_id = self.repo.submit("Never ends", "--run", "while true; do echo .; sleep 0.5; done", "--timeout", "1s")
        self.repo.commit("job")
        started = time.monotonic()
        self.repo.pipeline("run", "--rev", "HEAD")
        self.assertLess(time.monotonic() - started, 30)
        r = self.repo.result(job_id, collected=False)
        self.assertEqual(r["status"], "timeout")
        self.assertEqual(r["steps"][0]["stoppedFor"], "ceiling")
        self.assertEqual(r["runner"]["maxTimeoutSeconds"], 4)
        self.assertTrue(any("ceiling" in a for a in r["attention"]), r["attention"])

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

    @cost("tool")
    @unittest.skipUnless(shutil.which("jj"), "needs jj")
    def test_a_job_committed_in_another_jj_workspace_is_queued_and_run_at_its_commit(self):
        # A feature loop's streams each work in their own workspace on their own branch; the runner, in the
        # default one, runs their jobs too, without anything being merged.
        config = self.repo.dir.parent / f"{self.repo.dir.name}-jj.toml"
        config.write_text('[user]\nname = "t"\nemail = "t@example.invalid"\n')
        self.addCleanup(config.unlink)
        env = dict(os.environ, JJ_CONFIG=str(config))
        jj = lambda cwd, *args: subprocess.run(["jj", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True)
        jj(self.repo.dir, "git", "init", "--colocate")
        jj(self.repo.dir, "new", "main")
        other = Path(tempfile.mkdtemp(prefix="pipeline-test-ws-")) / "stream"
        self.addCleanup(shutil.rmtree, other.parent, ignore_errors=True)
        jj(self.repo.dir, "workspace", "add", "--name", "stream", "-r", "main", str(other))
        submitted = subprocess.run(
            [sys.executable, "verification/pipeline.py", "submit", "--title", "From the stream", "--description",
             "A stub job, for testing the pipeline itself.", "--capability", "test", "--run", "true"],
            cwd=other, env=dict(env, VERIFY_REPO=str(other)), check=True, capture_output=True, text=True).stdout
        job_id = submitted.split("verification/jobs/")[1].split(".json")[0].rsplit("/", 1)[-1]
        jj(other, "commit", "-m", "job (verification pending)")
        source = jj(other, "log", "--no-graph", "-r", "@-", "-T", "commit_id").stdout
        self.assertIsNone(layout.find_job(self.repo.dir, job_id), "nothing was merged")
        self.assertIn(job_id, self.repo.pipeline("status").stdout.split("running:")[0])
        self.assertNotIn(job_id, self.repo.pipeline("status", "--rev", "HEAD").stdout)
        self.repo.pipeline("run")
        self.assertEqual(self.repo.result(job_id, collected=False)["sourceCommit"], source)

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

    def test_collect_counts_the_jobs_whose_outputs_it_applied_for_the_commit_message(self):
        # kqpykqpp's commit message said 18 jobs had outputs applied where 19 had: collect printed one line per job
        # and the agent added them up. collect now gives the totals itself, from the same lists it records.
        (self.repo.dir / "o.txt").write_text("before\n")
        applies = self.repo.submit("Apply one", "--output", "a.txt", "--run", "echo a > a.txt")
        nothing = self.repo.submit("Declare none", "--run", "true")
        fails = self.repo.submit("Fail one", "--output", "o.txt", "--run", "echo after > o.txt; exit 3")
        self.repo.commit("jobs")
        self.repo.pipeline("run", "--rev", "HEAD")
        out = self.repo.pipeline("collect").stdout
        self.assertEqual([len(self.repo.result(j)["collected"]["applied"]) for j in (applies, nothing, fails)], [1, 0, 0])
        message = out.split("For the commit message")[1]
        self.assertIn("Record verification results for 3 job(s)", message)
        self.assertIn("Outputs applied for 1 of the 3 job(s); 1 declared or produced none; "
                      "1 kept under outputs/, not applied (the job didn't pass)", message)

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
        new_id = again.split("verification/jobs/")[1].split(".json")[0].rsplit("/", 1)[-1]
        job = json.loads(self.repo.job_path(new_id).read_text())
        self.assertEqual(job["supersedes"], job_id)
        self.assertEqual(job["resources"]["memory"], "8G")

    @cost("tool")
    def start_runner(self, repo, job_id):
        """A runner in the background, once it has taken the job."""
        proc = subprocess.Popen([sys.executable, "verification/pipeline.py", "run", "--rev", "HEAD"], cwd=repo.dir,
                                env=dict(os.environ, VERIFY_REPO=str(repo.dir)), stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        deadline = time.monotonic() + 20
        while not (repo.dir / "verification/.state/claims" / job_id).exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        return proc

    @cost("tool")
    def test_a_job_committed_during_a_run_starts_at_a_nudge_and_its_result_can_be_collected_before_the_run_ends(self):
        long = self.repo.submit("A long one", "--run", "sleep 6", "--memory", "512M")
        self.repo.commit("job")
        self.assertIn("no runner is at work, and nothing waits", self.repo.pipeline("wait", "--timeout", "0").stdout)
        proc = self.start_runner(self.repo, long)
        self.assertEqual(self.repo.pipeline("wait", "--timeout", "1", check=False).returncode, 3, "nothing has finished yet")
        short = self.repo.submit("A short one", "--run", "true", "--memory", "512M")
        self.repo.commit("another job")
        self.assertIn("reads the queue again now", self.repo.pipeline("nudge").stdout)
        waited = self.repo.pipeline("wait", "--timeout", "20").stdout
        self.assertIn(f"finished, not collected: {short}", waited)
        self.assertIn("is at work, 1 job(s) running", waited, "the long one is still running")
        self.assertIn(f"{short}: passed", self.repo.pipeline("collect").stdout)
        self.assertEqual(self.repo.result(short)["status"], "passed")
        out = proc.communicate(timeout=60)[0]
        self.assertIn(f"finished 2 job(s)", out)
        self.assertLess(self.repo.result(short)["finishedAt"], self.repo.result(long, False)["finishedAt"])
        self.assertIn(f"finished, not collected: {long}\nno runner is at work", self.repo.pipeline("wait", "--timeout", "5").stdout)
        self.assertEqual(self.repo.pipeline("run", "--rev", "HEAD").stdout.count("started at"), 0, "neither runs twice")

    @cost("tool")
    def test_without_a_nudge_a_job_committed_during_a_run_is_found_at_the_next_interval(self):
        repo = Repo(poll_seconds=1)
        self.addCleanup(repo.close)
        long = repo.submit("A long one", "--run", "sleep 5", "--memory", "512M")
        repo.commit("job")
        proc = self.start_runner(repo, long)
        short = repo.submit("A short one", "--run", "true", "--memory", "512M")
        repo.commit("another job")
        self.assertIn(short, repo.pipeline("wait", "--timeout", "20").stdout)
        proc.communicate(timeout=60)
        self.assertLess(repo.result(short, False)["finishedAt"], repo.result(long, False)["finishedAt"])

    def test_the_queue_is_read_in_one_git_call_and_a_missing_file_is_none(self):
        job_id = self.repo.submit("Read me", "--run", "true")
        head = self.repo.commit("job")
        with mock.patch.object(pipeline, "ROOT", self.repo.dir):
            rel = self.repo.job_rel(job_id)
            found = pipeline.show_many(head, [rel, "verification/jobs/not-there.json", ".gitignore"])
            self.assertEqual(json.loads(found[rel])["id"], job_id)
            self.assertIsNone(found["verification/jobs/not-there.json"])
            self.assertEqual(found[".gitignore"], b"verification/.state/\n", "the file after a missing one is still its own")
            jobs = pipeline.committed_jobs(head, lambda _: False)
            self.assertEqual([(j["id"], source) for j, _, source in jobs], [(job_id, None)], "no source looked up for a job that has run")
            self.assertEqual(pipeline.committed_jobs(head)[0][2], head)

            queued = self.repo.submit("Written during the split", "--run", "true")
            pinned = self.repo.submit("A pinned job during the split", "--run", "true", "--revision", head)
            temporary = self.repo.commit("wip: another session's files\nmetadata after the first line")
            (self.repo.dir / ".jj").mkdir()
            self.assertEqual([job["id"] for job, _, _ in pipeline.committed_jobs(temporary)], [job_id])
            # put_back() leaves those same files above the completed change for their author to commit.
            self.repo.git("update-ref", "HEAD", head)
            final = self.repo.commit("Commit both jobs")
            sources = {job["id"]: source for job, _, source in pipeline.queued_jobs([temporary, final])}
            self.assertEqual(sources, {job_id: head, queued: final, pinned: head})

    @cost("tool")
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

    def test_a_job_from_a_conflicted_jj_commit_is_an_error_and_runs_nothing(self):
        # VF-060: jj writes a conflicted change to git as JJ-CONFLICT-README beside a whole-tree copy of each side.
        marks = self.repo.dir.parent / f"{self.repo.dir.name}-conflicted-ran"
        self.addCleanup(lambda: marks.unlink(missing_ok=True))
        job_id = self.repo.submit("From a conflict", "--run", f"echo ran >> {marks}")
        (self.repo.dir / "JJ-CONFLICT-README").write_text("made-up conflict layout\n")
        self.repo.commit("job, in a conflicted change")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, False)
        self.assertEqual(r["status"], "error")
        self.assertIn("conflicted jj commit", r["attention"][0])
        self.assertFalse(marks.exists(), "no step ran")


    def test_a_real_world_example_is_not_submitted_as_a_build_py_run(self):
        folder = self.repo.dir / "examples/108-a-real-world-change"
        folder.mkdir(parents=True)
        (folder / "example.json").write_text(json.dumps({"id": "108", "origin": "real-world",
                                                         "approach": {"id": "B9"}, "subject": {"file": "src/A.java"}}))
        proc = self.repo.pipeline("submit", "--title", "A real-world one", "--description", "Should be refused.",
                                  "--capability", "B9", "--example", "108", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("build.py does not run it", proc.stderr)
        self.assertEqual(list((self.repo.dir / "verification/jobs").rglob("*.json")) if (self.repo.dir / "verification/jobs").exists() else [], [])


    def add_target_example(self, example_id):
        """A real-world example with a target sidecar in the stub repo, with build.py, the schemas and the tags it
        is checked against."""
        self.add_example("100", "B9", "examples/apps/crosscut/src/main/java/a/B.java")  # copies build.py and targets/
        shutil.copytree(HERE.parent / "examples/schema", self.repo.dir / "examples/schema", dirs_exist_ok=True)
        (self.repo.dir / "examples/tags.json").write_text(json.dumps({"domain": {"open-source-libraries": "d"}}))
        folder = self.repo.dir / f"examples/{example_id}-a-target"
        folder.mkdir(parents=True)
        (folder / "example.json").write_text(json.dumps({
            "id": example_id, "title": "t", "summary": "s", "origin": "real-world", "categories": ["security"],
            "tags": ["open-source-libraries"], "severity": "low", "subject": {"system": "S", "symbol": "a.B#m"},
            "approach": {"id": "B11", "name": "Property proofs", "tool": "lib"}, "change": {"kind": "bug-fix"},
            "source": {"kind": "commit", "repository": "https://github.com/a/b", "url": "https://github.com/a/b/commit/x"},
            "verdictLabel": "not run", "target": "target.json"}))
        (folder / "target.json").write_text(json.dumps({
            "schema": "example-target/v1", "identity": {"case": "c", "family": "f", "role": "negative"},
            "history": {"repository": "https://github.com/a/b", "revisions": {"fixed": {"commit": "a" * 40}}},
            "tasks": [{"id": "fixed-security", "kind": "prove", "relation": "security", "revision": "fixed",
                       "target": "a.B#m", "expected": "established", "engine": "native"}]}))

    def test_a_target_task_is_submitted_only_from_an_executable_plan(self):
        self.add_target_example("285")
        submit = lambda *extra: self.repo.pipeline("submit", "--title", "A target task", "--description", "d",
                                                   "--capability", "B11", "--example", "285", *extra, check=False)
        proc = submit()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("name one of its tasks with --task", proc.stderr)
        proc = submit("--task", "no-such-task")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("has no task 'no-such-task'", proc.stderr)
        # Workflow's planner can't resolve this minimal sidecar's task (Unsupported at task-plan), and a plan that isn't
        # executable queues nothing.
        proc = submit("--task", "fixed-security")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unsupported: task-plan (example-targets-workflow)", proc.stderr)
        self.assertFalse((self.repo.dir / "verification/jobs").exists() and list((self.repo.dir / "verification/jobs").rglob("*.json")))

    def add_example(self, example_id, approach, subject, **approach_fields):
        """A constructed example in the stub repo, with build.py beside it to plan its run."""
        tools = self.repo.dir / "examples/tools"
        tools.mkdir(parents=True, exist_ok=True)
        for module in ("build.py", "checker_output.py", "result_format.py"):  # build.py and the modules it imports
            shutil.copy(HERE.parent / "examples/tools" / module, tools / module)
        reader = self.repo.dir / "lib/python/jvmcontract_io.py"  # the proof output reader checker_output.py reads through
        reader.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(HERE.parent / "lib/python/jvmcontract_io.py", reader)
        if not (tools / "targets").exists():
            shutil.copytree(HERE.parent / "examples/tools/targets", tools / "targets",
                            ignore=shutil.ignore_patterns("__pycache__", "test_*.py"))
        folder = self.repo.dir / f"examples/{example_id}-a-constructed-change"
        folder.mkdir(parents=True)
        (folder / "example.json").write_text(json.dumps({
            "id": example_id, "origin": "constructed", "approach": {"id": approach, **approach_fields},
            "subject": {"file": subject, "symbol": "a.B#m"}, "change": {"behaviourChangeIntended": False},
            "expected": {"verdict": "verified"}}))

    def submitted(self, example_id, approach):
        job_id = self.repo.submit(f"Example {example_id}", "--capability", approach, "--example", example_id)
        return json.loads(next((self.repo.dir / "verification/jobs").rglob(f"{job_id}.json")).read_text())

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

    def test_a_jobs_own_jvmcontract_is_named_by_the_lib_tree_it_was_built_from(self):
        """A job that requires jvmcontract gets $JVMCONTRACT and $JVMCONTRACT_LIB_TREE (the git tree id of the lib/ it
        was built from, which $VERIFY_SOURCE_COMMIT's lib/ is), so a record can name the binary's source; a job
        without one gets neither."""
        runner = pipeline.Runner.__new__(pipeline.Runner)
        runner.state = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, runner.state, True)
        exe = runner.state / "tools" / "jvmcontract" / ("a" * 40) / "jvmcontract"
        result = {"limits": {"memoryLimitBytes": 4 * 1024 ** 3, "cpus": 2}, "sourceCommit": "b" * 40,
                  "jvmcontract": {"libTree": "a" * 40, "path": str(exe), "built": True}}
        env = runner.step_env({"id": "job"}, result, runner.state / "work")
        self.assertEqual((env["JVMCONTRACT"], env["JVMCONTRACT_LIB_TREE"], env["VERIFY_SOURCE_COMMIT"]),
                         (str(exe), "a" * 40, "b" * 40))
        del result["jvmcontract"]
        with mock.patch.dict(os.environ, {"JVMCONTRACT_LIB_TREE": "c" * 40}):
            env = runner.step_env({"id": "job"}, result, runner.state / "work")
        self.assertNotIn("JVMCONTRACT_LIB_TREE", env, "an inherited tree would name a binary the job didn't build")

    def test_an_example_build_py_cannot_run_is_refused_with_the_reason(self):
        self.add_example("150", "B9", "src/main/java/a/B.java")
        proc = self.repo.pipeline("submit", "--title", "No app", "--description", "Should be refused.",
                                  "--capability", "B9", "--example", "150", check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("no app builds it", proc.stderr)


class PruneWorkdirsTest(unittest.TestCase):
    """A kept work directory goes once its job is collected and the original sealed from that very attempt is
    verified in the store, not before; verification/test_capture.py runs the rule on a real spool and store."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state"
        self.receipts, self.states = {}, {}
        patch = mock.patch.object(pipeline, "collected_receipt", lambda job_id: self.receipts.get(job_id))
        patch.start()
        self.addCleanup(patch.stop)
        self.archive = mock.Mock(occurrence_states=lambda ids: {i: self.states[i] for i in ids if i in self.states})

    def attempt(self, job_id, status="failed", capture="sealed", custody="remote_verified", collected=True, number=None):
        """An attempt as the runner leaves one: a work directory, its record, and (by default) a sealed original
        that the store has read back and a collected receipt that names it."""
        attempt = pipeline.attempts.begin(self.state, job_id, "0" * 40, "made-up", at_least=number or 0)
        attempt.work_dir.mkdir()
        (attempt.work_dir / "big.bin").write_bytes(b"x" * 1000)
        attempt.save(prepared=True)
        occurrence = f"occ-{attempt.id}"
        if capture in ("sealed", "recovered"):
            attempt.captured(capture, {"workdir": occurrence}, number=attempt.number)
            self.states[occurrence] = {"state": custody, "kind": "job-workdir", "job": job_id, "attempt": attempt.number, "status": "complete"}
        else:
            attempt.captured(capture)
        attempt.finished(status)
        if collected:
            self.receipts[job_id] = {"attempt": {"id": attempt.id, "number": attempt.number},
                                     "originals": {"attempt": attempt.number, "occurrences": {"workdir": occurrence}}}
        return attempt

    def pruned(self, **kw):
        kept = []
        gone = pipeline.prune_workdirs(self.state, self.archive, kept=kept, **kw)
        return [name for name, _ in gone], dict(kept)

    def test_only_a_collected_attempt_whose_own_original_is_verified_is_removed(self):
        done = self.attempt("j-done")
        unverified = self.attempt("j-unverified", custody="locally_sealed")
        uncollected = self.attempt("j-uncollected", collected=False)
        staged = self.attempt("j-staged")
        (self.state / "results/j-staged").mkdir(parents=True)
        (self.state / "results/j-staged/result.json").write_text(json.dumps({"attempt": {"id": staged.id}}))
        failed_capture = self.attempt("j-capture-failed", capture="failed")
        self.assertEqual(pipeline.prune_workdirs(self.state, self.archive, dry_run=True), [(done.id, 1000)])
        self.assertTrue(done.work_dir.exists())
        gone, kept = self.pruned()
        self.assertEqual(gone, [done.id])
        self.assertFalse(done.work_dir.exists())
        self.assertEqual(kept, {unverified.id: "its workdir original is sealed here, not yet verified in the store",
                                uncollected.id: "its job's result is not collected",
                                staged.id: "its result is staged and not collected yet",
                                failed_capture.id: "its originals are not sealed (failed): `recover` seals them"})
        self.assertTrue(all(a.work_dir.exists() for a in (unverified, uncollected, staged, failed_capture)))
        self.assertEqual(pipeline.prune_workdirs(self.state, None), [])        # no archive to ask: nothing sealed is known verified

    def test_an_older_attempts_verified_original_does_not_release_a_later_attempt(self):
        """The rule until 2026-11-27 asked whether the job's latest *captured* work directory was verified."""
        first = self.attempt("j", status="cancelled", collected=False)
        second = self.attempt("j", capture="failed")                       # collected, and never sealed
        gone, kept = self.pruned()
        self.assertEqual((gone, kept), ([first.id], {second.id: "its originals are not sealed (failed): `recover` seals them"}))
        # And the other way round: an attempt that ran after the collected one is not the collected one's to release.
        earlier = self.attempt("k")
        later = self.attempt("k", collected=False)
        gone, kept = self.pruned()
        self.assertEqual(gone, [earlier.id])
        self.assertEqual(kept[later.id], "the collected receipt is of another attempt, and not of a later one")

    def test_an_original_recorded_for_another_attempt_or_unknown_to_the_archive_releases_nothing(self):
        other = self.attempt("j-other")
        self.states[f"occ-{other.id}"]["attempt"] = other.number + 1
        unknown = self.attempt("j-unknown")
        del self.states[f"occ-{unknown.id}"]
        named_otherwise = self.attempt("j-receipt")
        self.receipts["j-receipt"]["originals"]["occurrences"]["workdir"] = "occ-of-something-else"
        gone, kept = self.pruned()
        self.assertEqual(gone, [])
        self.assertIn("recorded for another job or attempt", kept[other.id])
        self.assertIn("does not know", kept[unknown.id])
        self.assertEqual(kept[named_otherwise.id], "the collected receipt names another original of the work directory")

    def test_what_was_never_an_original_goes_once_collected_and_an_uncaptured_one_only_when_asked(self):
        passed = self.attempt("j-passed", status="passed", capture="sealed")       # keep_workdirs = "always" kept it
        del self.states[f"occ-{passed.id}"]                                         # a passed job's work directory is not sealed
        off = self.attempt("j-off", capture="off")
        gone, kept = self.pruned()
        self.assertEqual(gone, [passed.id])
        self.assertIn("prune --unarchived", kept[off.id])
        self.assertEqual(self.pruned(unarchived=True)[0], [off.id])
        self.assertEqual(pipeline.attempts.find(self.state, off.id).record["released"][0]["why"],
                         "pruned: its job's result is collected, and it holds no original")

    def test_a_work_directory_of_before_attempts_had_folders_goes_only_by_the_seal_of_the_receipts_attempt(self):
        for job in ("old-done", "old-rerun", "old-unsealed", "old-unverified"):
            (self.state / "work" / job).mkdir(parents=True)
            (self.state / "work" / job / "big.bin").write_bytes(b"x" * 1000)
            (self.state / "runs" / job).mkdir(parents=True)
            self.receipts[job] = {"originals": {"attempt": 2, "occurrences": {"workdir": f"occ-{job}"}}}
            self.states[f"occ-{job}"] = {"state": "remote_verified", "kind": "job-workdir", "job": job, "attempt": 2, "status": "complete"}
        (self.state / "runs/old-done/.captured").write_text('{"attempt": 2}')
        (self.state / "runs/old-rerun/.captured").write_text('{"attempt": 3}')       # a later run sealed over it
        (self.state / "runs/old-unverified/.captured").write_text('{"attempt": 2}')
        self.states["occ-old-unverified"]["state"] = "transferring"
        gone, kept = self.pruned()
        self.assertEqual(gone, ["old-done"])
        self.assertEqual(sorted(p.name for p in (self.state / "work").iterdir()), ["old-rerun", "old-unsealed", "old-unverified"])
        self.assertIn("nothing ties the folder to the attempt the receipt names", kept["old-rerun"])
        self.assertIn("nothing ties the folder to the attempt the receipt names", kept["old-unsealed"])
        self.assertIn("transferring", kept["old-unverified"])


class OneRunnerPerRepositoryTest(unittest.TestCase):
    """VF-051: a runner in one jj workspace turns away a runner in another workspace of the same repository."""

    def test_a_second_workspaces_runner_is_refused_while_the_first_holds_the_repositorys_lock(self):
        with tempfile.TemporaryDirectory() as d:
            default, other = Path(d) / "default", Path(d) / "other"
            (default / ".jj" / "repo").mkdir(parents=True)
            (other / ".jj").mkdir(parents=True)
            (other / ".jj" / "repo").write_text("../../default/.jj/repo")  # as jj writes it in a second workspace
            with mock.patch.object(pipeline, "ROOT", default):
                self.assertEqual(pipeline.repo_store(), (default / ".jj" / "repo").resolve())
                held = pipeline.take_repo_lock(default / "verification" / ".state")
            self.addCleanup(held.close)
            with mock.patch.object(pipeline, "ROOT", other), self.assertRaises(SystemExit) as refused:
                pipeline.take_repo_lock(other / "verification" / ".state")
            self.assertIn("another workspace's runner is at work", str(refused.exception))
            self.assertIn(str(default), str(refused.exception))
            held.close()
            with mock.patch.object(pipeline, "ROOT", other):
                pipeline.take_repo_lock(other / "verification" / ".state").close()  # free again once the first ends
            with mock.patch.object(pipeline, "ROOT", Path(d) / "no-jj-here"):
                self.assertIsNone(pipeline.take_repo_lock(Path(d)))


class SignalsTest(unittest.TestCase):
    def test_a_target_tasks_line_from_build_py_is_a_signal(self):
        # build.py NNN --task T prints one line per attempt (examples/tools/build.py's run_task); a job's signals
        # carry it, as they do a constructed example's verdict line.
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "step.log"
            log.write_text(
                "306-spring-framework-db9a10bf-pattern-match-prefix-startswith: running task replay (target route)\n"
                "306-spring-framework-db9a10bf-pattern-match-prefix-startswith: task replay: none (completed; as expected), "
                "receipt receipts/replay/a1/result.json\n"
                "285-spring-boot-cve-2023-34055-unbounded-http-method-labels: task fixed-security: unresolved (completed; "
                "NOT AS EXPECTED (established)), receipt receipts/fixed-security/a1/result.json\n"
                "287-spring-security-cve-2025-22228-bcrypt-ignores-bytes-past-72: not-executed (task replay: unsupported: "
                "prepare (example-targets-runtime): revision fixed-release is failed, not artifacts-ready)\n")
            signals, counts, _ = pipeline.scan_signals(log)
        self.assertEqual(counts, {"example:task-as-expected": 1, "example:task-unexpected": 1, "example:not-executed": 1})
        self.assertEqual([s["groups"] for s in signals],
                         [["306", "replay", "none"], ["285", "fixed-security", "unresolved", "established"],
                          ["287", "task replay: unsupported: prepare (example-targets-runtime): revision fixed-release "
                                  "is failed, not artifacts-ready"]])

    def test_a_predicted_refusals_verdict_line_is_a_signal_and_build_pys_indented_lines_are_not(self):
        # examples/tools/targets/workflow_refusal.py indents build.py's output, so its NOT AS EXPECTED line (the
        # refusal it predicts) is no task-unexpected signal; its own line is the step's verdict.
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "step.log"
            log.write_text(
                "  build.py | 286-spring-framework-cve-2022-22968-case-sensitive-disallowed-fields: task "
                "vulnerable-security: unresolved (completed; NOT AS EXPECTED (refuted)), receipt receipts/v/a1/result.json\n"
                "286-spring-framework-cve-2022-22968-case-sensitive-disallowed-fields: task vulnerable-security: refused "
                "as predicted (VF-027; verifier; records/refusals/vulnerable-security.json): unresolved at the recorded "
                "refusal, receipt receipts/v/a1\n"
                "285-spring-boot-cve-2023-34055-unbounded-http-method-labels: task preservation: NOT AS PREDICTED: "
                "build.py exited 0, not 1 (VF-027; run-verifier; records/refusals/preservation.json)\n")
            signals, counts, _ = pipeline.scan_signals(log)
        self.assertEqual(counts, {"example:task-refused-as-predicted": 1, "example:task-not-as-predicted": 1})
        self.assertEqual([s["groups"] for s in signals][0], ["286", "vulnerable-security", "VF-027", "verifier"])


class MissingToolsTest(unittest.TestCase):
    def test_maven_is_the_install_runtime_builds_with_not_an_executable_named_maven(self):
        # build.py --plan 105 --task fix-property requires "maven" (workflow.BUILD_TOOLS), and runtime_upstream.py runs
        # the highest Maven under $TARGETS_MAVEN_CANDIDATES (sdkman's candidates) by full path. No executable is named
        # maven, so a lookup on PATH would end every upstream-build task's job as "missing on this machine: maven".
        with tempfile.TemporaryDirectory() as d:
            installed, empty = Path(d) / "maven", Path(d) / "none"
            (installed / "3.10.0/bin").mkdir(parents=True)
            (installed / "3.10.0/bin/mvn").write_text("#!/bin/sh\n")
            (installed / "current").symlink_to(installed / "3.10.0")
            empty.mkdir()
            env = {"PATH": d}
            with mock.patch.dict(os.environ, {**env, "TARGETS_MAVEN_CANDIDATES": str(installed)}, clear=True):
                self.assertEqual(pipeline.missing_tools(["maven"]), [])
            with mock.patch.dict(os.environ, {**env, "TARGETS_MAVEN_CANDIDATES": str(empty)}, clear=True):
                self.assertEqual(pipeline.missing_tools(["maven"]), ["maven"])
            # `current` alone, as runtime ignores it, is no install.
            (empty / "current").symlink_to(installed / "3.10.0")
            with mock.patch.dict(os.environ, {**env, "TARGETS_MAVEN_CANDIDATES": str(empty)}, clear=True):
                self.assertEqual(pipeline.missing_tools(["maven"]), ["maven"])


@unittest.skipUnless(SYSTEMD, "systemd-run --user --scope is not available here")
class MemoryOrderTest(unittest.TestCase):
    """Should the machine run short of memory, a verification job goes first: before an agent, a watcher or a
    terminal. Its processes are first in the kernel's kill order, and under the runner's memory floor the runner
    stops its newest job itself."""

    def setUp(self):
        self.mem = Path(tempfile.mkdtemp(prefix="pipeline-mem-"))
        self.addCleanup(shutil.rmtree, self.mem, True)
        self.available = self.mem / "available"
        self.set_available(100 << 30)
        self.env = {"VERIFY_MEMAVAILABLE_FILE": str(self.available)}

    def set_available(self, n):
        tmp = self.available.with_suffix(".new")
        tmp.write_text(f"{n}\n")
        tmp.replace(self.available)

    def test_every_process_of_a_job_starts_first_in_the_kernels_kill_order(self):
        repo = Repo()
        self.addCleanup(repo.close)
        seen = self.mem / "adj"
        job_id = repo.submit("Read its own oom score", "--run", f"bash -c 'cat /proc/self/oom_score_adj' > {seen}",
                             "--memory", "64M")
        repo.commit("job")
        repo.pipeline("run", "--rev", "HEAD")
        self.assertEqual(repo.result(job_id, False)["status"], "passed")
        self.assertEqual(seen.read_text().strip(), "1000", "a child of the step inherits the job's place")

    def test_no_job_starts_that_would_take_the_machine_under_its_floor(self):
        repo = Repo(memory_floor="1G")
        self.addCleanup(repo.close)
        job_id = repo.submit("Wait for room", "--run", "true", "--memory", "256M")
        repo.commit("job")
        self.set_available((1 << 30) + (100 << 20))  # 1.1G: room for the floor, not for the job's 384M limit too
        out = repo.pipeline("run", "--rev", "HEAD", env=self.env).stdout
        self.assertIn(f"{job_id}: not started: only", out)
        self.assertIn("which keeps 1.0 GiB free", out)
        self.set_available(4 << 30)
        self.assertIn(f"{job_id}: passed", repo.pipeline("run", "--rev", "HEAD", env=self.env).stdout)

    def runner(self, repo):
        proc = subprocess.Popen([sys.executable, "verification/pipeline.py", "run", "--rev", "HEAD"], cwd=repo.dir,
                                env=dict(os.environ, VERIFY_REPO=str(repo.dir), **self.env), stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        return proc

    def wait_for(self, what, test, seconds=30):
        deadline = time.monotonic() + seconds
        while not test():
            if time.monotonic() > deadline:
                self.fail(f"waited {seconds} s for {what}")
            time.sleep(0.1)

    @cost("tool")
    def test_under_the_floor_the_newest_job_is_stopped_runs_again_and_the_second_time_is_a_result_to_regroup(self):
        repo = Repo(memory_floor="1G", poll_seconds=1)
        self.addCleanup(repo.close)
        starts = self.mem / "starts"
        older = repo.submit("An older job", "--run", "sleep 8", "--memory", "128M")
        repo.commit("job")
        proc = self.runner(repo)
        claims = repo.dir / "verification/.state/claims"
        self.wait_for("the older job to start", lambda: (claims / older).exists())
        newer = repo.submit("A newer job", "--run", f"echo start >> {starts}; sleep 60", "--memory", "128M")
        repo.commit("another job")
        repo.pipeline("nudge")
        self.wait_for("the newer job to start", lambda: starts.exists())
        self.set_available(512 << 20)  # an agent's build takes the machine under the floor
        stopped = repo.dir / "verification/.state/results" / newer / "result.json"
        self.wait_for("the newer job to be stopped", stopped.exists)
        # Freed, but not enough to start it again beside the older one: that one is left alone, and finishes.
        self.set_available((1 << 30) + (100 << 20))
        out = proc.communicate(timeout=60)[0]
        self.assertIn(f"{newer}: stopped for the machine's memory: 512.0 MiB available, under the 1.0 GiB floor; "
                      f"the newest of 2 running job(s)", out)
        self.assertEqual(repo.result(older, False)["status"], "passed", "the older job was left to finish")
        first = repo.result(newer, False)
        self.assertEqual(first["status"], "cancelled", "the first time it is not run, and runs again")
        self.assertEqual(first["memoryStop"]["count"], 1)
        self.assertEqual(first["steps"][0]["status"], "cancelled")
        self.assertLess(first["steps"][0]["wallSeconds"], 20, "killed at once, not left to wind down")
        self.assertIn("not at the job's own limit. It runs again when there is room", " ".join(first["attention"]))
        self.assertIn(f"{newer}: not started: only 1.1 GiB available", out, "and no job starts under the floor")

        self.set_available(100 << 30)  # the room is back: it runs again
        proc = self.runner(repo)
        self.wait_for("the newer job to start again", lambda: starts.read_text().count("start") == 2)
        self.set_available(512 << 20)
        proc.communicate(timeout=60)
        second = repo.result(newer, False)
        self.assertEqual(second["status"], "out-of-memory", "the second time it is a result for its submitter")
        self.assertEqual(second["memoryStop"]["count"], 2)
        self.assertIn("2 times now. Regroup: resubmit it with a higher --memory", " ".join(second["attention"]))
        self.assertNotIn("started at", repo.pipeline("run", "--rev", "HEAD", env=self.env).stdout, "it is done")

    def test_a_kill_at_the_machines_end_is_told_apart_from_one_at_the_jobs_own_limit(self):
        def attention(limit_ooms):
            step = {"index": 1, "name": "prove", "status": "out-of-memory", "exitCode": None, "signal": "SIGKILL",
                    "expectExit": [0], "wallSeconds": 3.0, "cpuSeconds": 2.0, "peakMemoryBytes": 1 << 30,
                    "oomKills": 1, "limitOoms": limit_ooms, "signalCounts": {}, "signals": []}
            result = {"status": None, "attention": [], "steps": [step], "outputs": [],
                      "limits": {"cpus": 1, "memoryLimitBytes": 2 << 30, "timeoutSeconds": 600}, "runner": {}}
            pipeline.Runner.finish(None, {}, result, {"memoryEstimate": 1 << 30, "durationEstimate": 60})
            return " ".join(result["attention"])
        self.assertIn("killed by the kernel when the machine ran out of memory, under its own 2.0 GiB limit", attention(0))
        self.assertIn("resubmitting with more memory does not help", attention(0))
        self.assertIn("was killed at its 2.0 GiB memory limit", attention(1))


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

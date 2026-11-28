#!/usr/bin/env python3
"""Tests of verification/capture.py: what the runner and the collector hand to the private archive, and that the
pipeline's own files and verdicts are what they were. Each test runs the pipeline in a throwaway git repository
(test_pipeline.Repo) with a spool and a store on disk of its own.

  python3 verification/test_capture.py
"""

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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pipeline  # noqa: E402
import capture  # noqa: E402
from test_pipeline import Repo  # noqa: E402
sys.path.append(str(HERE.parent / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.insert(0, str(HERE.parent / "llm-dlc/tools"))
import artifacts  # noqa: E402
sys.path.insert(0, str(HERE.parent / "jobs"))
import attempts  # noqa: E402
import audit  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402


class Captured(unittest.TestCase):
    """A throwaway repository whose pipeline captures into a spool and a store on disk of its own."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="capture-test-"))
        self.env = {"ITL_ARTIFACTS": str(HERE.parent / "llm-dlc/tools/artifacts.py"), "ITL_ORIGINALS_HOME": str(self.tmp / "home"),
                    "ITL_ORIGINALS_CACHE": str(self.tmp / "cache"), "ITL_ORIGINALS_STORE": f"dir:{self.tmp / 'store'}",
                    "ITL_ORIGINALS_RESERVE": "0", "ITL_ORIGINALS_OFF": "", "ITL_ORIGINALS_UPLOAD": "manual"}
        self.old = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        os.environ.pop("ITL_ORIGINALS_OFF")  # test_pipeline and the test runner switch capture off: here it is on
        self.repo = self.new_repo()

    def new_repo(self, **runner):
        repo = Repo(**runner)
        shutil.copy(HERE / "capture.py", repo.dir / "verification/capture.py")
        repo.commit("with capture")
        return repo

    def tearDown(self):
        for k, v in self.old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        self.repo.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def archive(self):
        archive = artifacts.Archive(self.tmp / "home")
        self.addCleanup(archive.close)
        return archive

    def restored(self, occurrence, name="out"):
        """An occurrence's files as a machine with only the store reads them."""
        archive = self.archive()
        archive.upload()
        out = self.tmp / name
        artifacts.Reader(cache=self.tmp / f"cache-{name}").fetch(occurrence, out, flat=True)
        return {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()} if out.is_dir() else out.read_bytes()



class CaptureTest(Captured):
    def test_the_whole_log_is_sealed_before_it_is_cut_and_the_result_names_it(self):
        self.repo.close()
        self.repo = self.new_repo(log_max_bytes="4K")
        job_id = self.repo.submit("Talk a lot", "--run", "seq 1 20000; echo VERIFICATION SUCCESSFUL")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, False)
        self.assertEqual(pipeline.validate(r, "result.schema.json"), [])
        log = r["steps"][0]["log"]
        self.assertTrue(log["truncated"])  # the pipeline's own copy is cut, as before
        self.assertEqual(r["originals"]["attempt"], 1)
        logs = self.restored(r["originals"]["occurrences"]["logs"])
        whole = logs[log["path"].split("/", 1)[1]]
        self.assertEqual((len(whole), pipeline.sha256(whole)), (log["bytes"], log["sha256"]))
        self.assertIn(b"\n10000\n", whole)  # the middle the result left out
        self.assertNotIn("\n10000\n", (self.repo.dir / "verification/.state/results" / job_id / log["path"]).read_text())
        listed = {d["kind"]: d for d in artifacts.Reader(cache=self.tmp / "c2").find(job=job_id)}
        self.assertEqual(sorted(listed), ["job-logs", "job-result"])
        self.assertEqual(listed["job-logs"]["source"]["commit"], r["sourceCommit"])
        self.assertEqual(json.loads(self.restored(listed["job-result"]["id"], "result")), r)

    def test_a_failed_job_keeps_its_outputs_its_diff_and_what_its_work_directory_gained(self):
        (self.repo.dir / "tracked.txt").write_text("committed\n")
        (self.repo.dir / "changed.txt").write_text("before\n")
        job_id = self.repo.submit("Fail after writing", "--output", "out", "--output", "never-made.txt", "--run",
                                  "mkdir -p out/cases/p0 scratch; echo x > out/cases/p0/native.json; : > out/cases/p0/stderr; "
                                  "echo after > changed.txt; head -c 3000 /dev/urandom > scratch/core.bin; exit 3")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        r = self.repo.result(job_id, False)
        self.assertEqual(r["status"], "failed")
        made = r["originals"]["occurrences"]
        self.assertEqual(sorted(made), ["diff", "logs", "outputs", "workdir"])
        self.assertEqual(self.restored(made["outputs"], "outputs"), {"out/cases/p0/native.json": b"x\n", "out/cases/p0/stderr": b""})
        work = self.restored(made["workdir"], "work")
        self.assertEqual(sorted(work), ["changed.txt", "out/cases/p0/native.json", "out/cases/p0/stderr", "scratch/core.bin"])
        self.assertEqual(work["changed.txt"], b"after\n")  # tracked.txt and the rest of the commit are in git already
        self.assertEqual(len(work["scratch/core.bin"]), 3000)
        outputs = self.archive().rows(id=made["outputs"])[0]
        self.assertEqual((outputs["status"], outputs["absent"]), ("partial", ["never-made.txt"]))
        self.assertIn(b"native.json", self.restored(made["diff"], "diff"))

    def test_collect_seals_the_result_it_writes_and_the_one_it_replaces(self):
        (self.repo.dir / "o.txt").write_text("before\n")
        job_id = self.repo.submit("Conflict", "--output", "o.txt", "--run", "echo after > o.txt")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        (self.repo.dir / "o.txt").write_text("someone else's edit\n")
        old = self.repo.collected(job_id)
        old.mkdir(parents=True)
        (old / "result.json").write_text('{"earlier": "collect"}\n')
        self.repo.pipeline("collect")
        r = self.repo.result(job_id)
        self.assertEqual(r["collected"]["conflicts"], ["o.txt"])
        self.assertFalse((self.repo.dir / "verification/.state/results" / job_id).exists())  # sealed, so released
        rows = [x for x in self.archive().rows(job=job_id) if x["kind"] == "job-result"]
        stages = {x["notes"]["stage"]: x for x in rows}
        self.assertEqual(sorted(stages), ["a collected result that a later collect replaced", "as collected", "as the runner wrote it"])
        self.assertEqual(stages["as collected"]["conflicts"], ["o.txt"])
        self.assertEqual(self.restored(stages["a collected result that a later collect replaced"]["id"], "old"),
                         {"result.json": b'{"earlier": "collect"}\n'})
        self.assertEqual(json.loads(self.restored(stages["as collected"]["id"], "new")), r)

    def test_a_result_staged_by_a_runner_without_capture_is_sealed_at_collect(self):
        job_id = self.repo.submit("Old runner", "--output", "a.txt", "--run", "echo a > a.txt; seq 1 5")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD", env={"ITL_ORIGINALS_OFF": "1"})
        self.assertNotIn("originals", self.repo.result(job_id, False))
        self.repo.pipeline("collect")
        kinds = sorted((x["kind"], x["notes"].get("stage") or x["notes"].get("why")) for x in self.archive().rows(job=job_id))
        self.assertEqual([k for k, _ in kinds], ["job-diff", "job-logs", "job-outputs", "job-result", "job-result"])
        self.assertTrue(any("sealed at collect" in (why or "") for _, why in kinds))

    def test_a_capture_that_fails_fails_no_job_and_no_collect_and_deletes_nothing_unsealed(self):
        job_id = self.repo.submit("Disk full", "--output", "a.txt", "--run", "echo a > a.txt")
        self.repo.commit("job")
        full = {"ITL_ORIGINALS_RESERVE": str(1 << 60)}
        ran = self.repo.pipeline("run", "--rev", "HEAD", env=full)
        r = self.repo.result(job_id, False)
        self.assertEqual(r["status"], "passed")
        self.assertNotIn("originals", r)
        self.assertIn("warn  capture:", ran.stderr)
        collected = self.repo.pipeline("collect", env=full)
        self.assertEqual(self.repo.result(job_id)["collected"]["applied"], ["a.txt"])
        self.assertIn("set aside, not deleted", collected.stderr)
        aside = list((self.repo.dir / "verification/.state/uncaptured").iterdir())
        self.assertEqual(len(aside), 1)
        self.assertTrue((aside[0] / "outputs/a.txt").exists())
        self.assertIn("nothing to collect", self.repo.pipeline("collect").stdout)
        self.assertIn("SpoolFull", (self.repo.dir / "verification/.state/capture.log").read_text())
        self.assertEqual(self.archive().rows(), [])

    def test_a_run_directory_of_before_attempts_had_folders_is_sealed_by_recover_and_never_cleared(self):
        """Until 2026-11-27 every run of a job wrote into STATE/runs/ID, and a rerun cleared it after asking the
        archive to keep what was there. A rerun no longer touches it: `recover` seals it where it is, once."""
        state, job_id = self.repo.dir / "verification/.state", "20261121-000000-made-up"
        run_dir = state / "runs" / job_id
        (run_dir / "logs").mkdir(parents=True)
        (run_dir / "logs/1-prove.log").write_text("killed half way\n")
        said = json.loads(self.repo.pipeline("recover", "--json").stdout)
        self.assertEqual([(r["what"], r["id"], r["sealed"]) for r in said["recovered"]], [("run directory", job_id, True)])
        rows = self.archive().rows(job=job_id)
        self.assertEqual([(x["kind"], x["status"], x["attempt"]) for x in rows], [("job-logs", "partial", 1)])
        self.assertIn("did not finish", rows[0]["notes"]["why"])
        self.assertEqual(self.restored(rows[0]["id"]), {"1-prove.log": b"killed half way\n"})
        self.assertEqual((run_dir / "logs/1-prove.log").read_text(), "killed half way\n")   # sealed where it is, and kept
        self.assertEqual(json.loads(self.repo.pipeline("recover", "--json").stdout)["recovered"], [])  # sealed once
        self.assertEqual(len(self.archive().rows(job=job_id)), 1)
        self.assertEqual(pipeline.legacy_attempt(state, job_id), 1)   # the next attempt of the job is numbered after it

    def killed_at(self, point):
        """The repository's capture.py for one command: the real one, and a kill of the collecting process itself at
        `point`, with no handler run: "copy", when the result's folder in the tree is wiped and not yet written, or
        "sealed", when the collected result is written and sealed and the staged one is still there."""
        real = (HERE / "capture.py").read_text()
        (self.repo.dir / "verification/capture.py").write_text(real + f'''

_before, _after, _point = before_collect, after_collect, {point!r}


def before_collect(*args, **kwargs):
    said = _before(*args, **kwargs)
    if _point == "copy":
        import shutil, signal
        shutil.copytree = lambda *a, **k: os.kill(os.getpid(), signal.SIGKILL)
    return said


def after_collect(*args, **kwargs):
    said = _after(*args, **kwargs)
    if _point == "sealed":
        import signal
        os.kill(os.getpid(), signal.SIGKILL)
    return said
''')

    def test_a_collect_killed_half_way_is_finished_by_the_next_one_and_nothing_unsealed_is_lost(self):
        (self.repo.dir / "o.txt").write_text("before\n")
        job_id = self.repo.submit("Killed", "--output", "o.txt", "--run", "echo after > o.txt")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        staged, kept = self.repo.dir / "verification/.state/results" / job_id, self.repo.collected(job_id)  # beside its job, flat or by day
        earlier = b'{"earlier": "collect"}\n'
        kept.mkdir(parents=True)
        (kept / "result.json").write_bytes(earlier)
        self.killed_at("copy")
        self.assertEqual(self.repo.pipeline("collect", check=False).returncode, -9)
        self.assertTrue((staged / "result.json").exists())           # the staged result is all there
        self.assertFalse((kept / "result.json").exists())            # and the tree's copy is wiped: the earlier one is gone from disk
        self.assertEqual((self.repo.dir / "o.txt").read_text(), "before\n")
        replaced = [x for x in self.archive().rows(job=job_id) if x["notes"].get("stage") == "a collected result that a later collect replaced"]
        self.assertEqual(self.restored(replaced[0]["id"], "replaced"), {"result.json": earlier})  # sealed before it was wiped
        self.killed_at("sealed")
        self.assertEqual(self.repo.pipeline("collect", check=False).returncode, -9)
        self.assertEqual(self.repo.result(job_id)["collected"]["applied"], ["o.txt"])
        self.assertTrue((staged / "result.json").exists())           # written and sealed, the staged one not yet released
        shutil.copy(HERE / "capture.py", self.repo.dir / "verification/capture.py")
        self.assertIn(job_id, self.repo.pipeline("collect").stdout)   # the next collect finds it and finishes
        final = self.repo.result(job_id)
        self.assertEqual((final["status"], final["collected"]["applied"], (self.repo.dir / "o.txt").read_text()), ("passed", ["o.txt"], "after\n"))
        self.assertFalse(staged.exists())
        self.assertIn("nothing to collect", self.repo.pipeline("collect").stdout)
        archive = self.archive()
        rows = [x for x in archive.rows(job=job_id) if x["kind"] == "job-result"]
        self.assertTrue(all(x["status"] in ("complete", "partial") for x in rows))
        collected = [x for x in rows if x["notes"].get("stage") == "as collected"]
        self.assertEqual(json.loads(self.restored(collected[-1]["id"], "final")), final)   # what the tree holds is what the store holds
        # One record for each thing a collect did, none of them a false success: the earlier result it wiped, the
        # folder the kill left empty (replaced by the second collect), and the collected result, sealed by the collect
        # that wrote it and again by the one that found it written (the kill came before the first could say so).
        # The third collect replaced nothing: what the second wrote is what the tree keeps.
        stages = [(x["notes"].get("stage"), x["status"], (x.get("inventory") or {}).get("members")) for x in rows]
        replaced = "a collected result that a later collect replaced"
        self.assertEqual(sorted(s for s in stages if s[0] != "as the runner wrote it"),
                         [(replaced, "complete", 0), (replaced, "complete", 1),
                          ("as collected", "complete", 1), ("as collected", "complete", 1)])

    def test_a_collect_stopped_after_its_result_was_committed_publishes_nothing_twice(self):
        """The collect wrote and sealed the result and was killed before it released the staged one; the tree was
        committed as it stood. The next collect finds its work done: the tree stays what the commit holds, to the
        byte, the staged result goes, and there is nothing new to commit."""
        (self.repo.dir / "o.txt").write_text("before\n")
        job_id = self.repo.submit("Committed", "--output", "o.txt", "--run", "echo after > o.txt")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        staged = self.repo.dir / "verification/.state/results" / job_id
        self.killed_at("sealed")
        self.assertEqual(self.repo.pipeline("collect", check=False).returncode, -9)
        shutil.copy(HERE / "capture.py", self.repo.dir / "verification/capture.py")
        self.repo.commit("the results, as the stopped collect left them")
        receipt = (self.repo.collected(job_id) / "result.json").read_bytes()
        again = self.repo.pipeline("collect").stdout
        self.assertIn("was collected before", again)
        self.assertIn("No result is new", again)
        self.assertNotIn("For the commit message", again)
        self.assertEqual((self.repo.collected(job_id) / "result.json").read_bytes(), receipt)
        changed = [line.split()[-1] for line in self.repo.git("status", "--porcelain", "--untracked-files=all", "verification/results").splitlines()]
        self.assertTrue(changed and all(path.endswith("index.json") for path in changed), changed)   # the indexes the stopped collect never wrote
        self.assertFalse(staged.exists())                                                 # sealed when it ran, so released
        self.assertIn("nothing to collect", self.repo.pipeline("collect").stdout)
        self.assertEqual((self.repo.dir / "o.txt").read_text(), "after\n")

    def test_no_archive_tool_no_capture(self):
        os.environ.pop("ITL_ARTIFACTS")
        self.assertIsNone(capture.tool(self.repo.dir))
        self.assertFalse(capture.available(self.repo.dir))
        self.assertIsNone(capture.begin(self.repo.dir, self.repo.dir, "j"))
        self.assertIsNone(capture.sealed_run(self.repo.dir, self.repo.dir, {"id": "j"}, 1, None, self.repo.dir / "none", None, None))
        self.assertTrue(capture.before_collect(self.repo.dir, self.repo.dir, "j", self.repo.dir, self.repo.dir, {}))


class AttemptsTest(Captured):
    """Every execution of a job keeps its own bytes until a rule releases them (jobs/attempts.py): a rerun clears
    nothing, a prune removes only what the archive holds of that very attempt, and what a capture missed is sealed
    later, where it is."""

    FULL = {"ITL_ORIGINALS_RESERVE": str(1 << 60)}   # a spool with no room: every capture fails

    def state(self):
        return self.repo.dir / "verification/.state"

    def started(self, job_id, text, env=None):
        """A runner on the queue, once the job's step has written `text` to its log: (the runner, the step's pid)."""
        runner = subprocess.Popen([sys.executable, "verification/pipeline.py", "run", "--rev", "HEAD"], cwd=self.repo.dir,
                                  env=dict(os.environ, VERIFY_REPO=str(self.repo.dir), **(env or {})),
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.addCleanup(lambda: (runner.poll() is None and runner.kill(), runner.stdout.close()))
        deadline = time.time() + 60
        while time.time() < deadline:
            logs = list((self.state() / "attempts" / job_id).glob("*/run/logs/1-*.log"))
            if any(text in log.read_text() for log in logs):
                step = subprocess.run(["pgrep", "-P", str(runner.pid)], capture_output=True, text=True).stdout.split()
                return runner, [int(pid) for pid in step]
            time.sleep(0.1)
        self.fail(f"the step never wrote {text!r}")

    def killed_mid_step(self, job_id):
        """The runner killed with no handler run, and its step with it: an attempt nobody finished or sealed."""
        runner, steps = self.started(job_id, "half way")
        runner.kill()
        runner.wait()
        for pid in steps:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    @cost("tool")
    def test_a_rerun_clears_nothing_of_a_killed_attempt_when_the_spool_is_full_and_recover_seals_it_later(self):
        flag = self.tmp / "second-time"
        job_id = self.repo.submit("Killed, then rerun", "--output", "made.txt", "--run",
                                  f"echo half way; echo first > made.txt; test -e {flag} || sleep 60; echo done")
        self.repo.commit("job")
        self.killed_mid_step(job_id)
        (first,) = attempts.of(self.state(), job_id)
        self.assertEqual((first.number, first.state(), first.record["capture"]["state"]), (1, "interrupted", "pending"))
        log = next((first.run_dir / "logs").glob("1-*.log"))
        kept = {"log": log.read_bytes(), "made": (first.work_dir / "made.txt").read_bytes()}
        self.assertIn(b"half way", kept["log"])
        # The rerun, with a spool that takes nothing: the first attempt cannot be sealed, and is not cleared for it.
        flag.write_text("")
        ran = self.repo.pipeline("run", "--rev", "HEAD", env=self.FULL)
        self.assertIn("still only on this machine", ran.stdout)
        first, second = attempts.of(self.state(), job_id)
        self.assertEqual((log.read_bytes(), (first.work_dir / "made.txt").read_bytes()), (kept["log"], kept["made"]))
        self.assertEqual((first.state(), first.record["capture"]["state"]), ("interrupted", "failed"))
        self.assertIn("SpoolFull", first.record["capture"]["error"])
        result = self.repo.result(job_id, False)
        self.assertEqual((result["status"], result["attempt"]["number"], result["attempt"]["previous"]), ("passed", 2, [first.id]))
        self.assertEqual((second.number, second.record["status"], second.record["capture"]["state"]), (2, "passed", "failed"))
        self.assertNotEqual(first.folder, second.folder)
        # Visible until it is put right: the audit of this checkout lists both attempts' bytes as only here.
        gaps = audit.Audit(self.repo.dir).run(self.state())["gaps"]
        self.assertEqual(sorted((g["kind"], g["attempt"]) for g in gaps if g["kind"].startswith("attempt-")),
                         sorted([("attempt-interrupted-unsealed", first.id), ("attempt-capture-failed", second.id)]))
        # The archive answers again: both are sealed where they are, and the store gives the killed attempt's bytes back.
        said = json.loads(self.repo.pipeline("recover", "--json").stdout)["recovered"]
        self.assertEqual(sorted((r["id"], r["sealed"]) for r in said), sorted([(first.id, True), (second.id, True)]))
        first, second = attempts.of(self.state(), job_id)
        self.assertEqual((first.record["capture"]["state"], second.record["capture"]["state"]), ("recovered", "recovered"))
        rows = {x["id"]: x for x in self.archive().rows(job=job_id)}
        logs = rows[first.record["capture"]["occurrences"]["logs"]]
        self.assertEqual((logs["status"], logs["attempt"], logs["notes"]["attemptId"]), ("partial", 1, first.id))
        self.assertEqual(self.restored(logs["id"], "killed-logs"), {log.name: kept["log"]})
        work = self.restored(first.record["capture"]["occurrences"]["workdir"], "killed-work")
        self.assertEqual(work["made.txt"], kept["made"])
        self.assertEqual([g for g in audit.Audit(self.repo.dir).run(self.state())["gaps"] if g["kind"].startswith("attempt-")], [])
        self.assertEqual(json.loads(self.repo.pipeline("recover", "--json").stdout)["recovered"], [])

    @cost("tool")
    def test_prune_keeps_a_later_attempt_whose_capture_failed_though_an_earlier_ones_original_is_verified(self):
        """What was asked until 2026-11-27 was whether the job's *latest captured* work directory was verified. Here
        that is the first attempt's, and the folder on disk that matters is the second's, which nothing sealed."""
        self.repo.close()
        self.repo = self.new_repo(keep_workdirs="failed")
        flag = self.tmp / "second-time"
        job_id = self.repo.submit("Stopped, then failed", "--run",
                                  f"echo half way; echo $RANDOM$RANDOM > scratch.txt; test -e {flag} || sleep 60; exit 3")
        self.repo.commit("job")
        runner, _ = self.started(job_id, "half way")
        runner.send_signal(signal.SIGTERM)                       # stopped by its handler: cancelled, and sealed
        runner.wait(timeout=60)
        (first,) = attempts.of(self.state(), job_id)
        self.assertEqual((first.record["status"], first.record["capture"]["state"]), ("cancelled", "sealed"))
        self.archive().upload()                                  # read back from the store: remote_verified
        flag.write_text("")
        self.repo.pipeline("run", "--rev", "HEAD", env=self.FULL)   # the second attempt fails, and nothing seals it
        unsealed = (attempts.of(self.state(), job_id)[1].work_dir / "scratch.txt").read_bytes()
        collected = self.repo.pipeline("collect", env=self.FULL).stdout   # a collect prunes when it is done
        first, second = attempts.of(self.state(), job_id)
        self.assertEqual((second.record["status"], second.record["capture"]["state"]), ("failed", "failed"))
        self.assertEqual(self.repo.result(job_id)["attempt"]["id"], second.id)
        # The first attempt's folder went: its own original is verified, and the collected receipt is of a later
        # attempt. The second's stays, with the bytes nothing sealed.
        self.assertIn("removed 1 kept work directory", collected)
        self.assertFalse(first.work_dir.exists())
        self.assertEqual((second.work_dir / "scratch.txt").read_bytes(), unsealed)
        said = json.loads(self.repo.pipeline("prune", "--json").stdout)
        self.assertEqual((said["removed"], [(k["id"], k["why"]) for k in said["kept"]]),
                         ([], [(second.id, "its originals are not sealed (failed): `recover` seals them")]))
        first = attempts.find(self.state(), first.id)
        self.assertEqual([(r["what"], "verified in the store" in r["why"]) for r in first.record["released"]], [("work", True)])
        # Sealed later, and not removed until the store has read it back; then it goes, and the store gives it back.
        self.repo.pipeline("recover")
        self.assertIn("not yet verified in the store", json.loads(self.repo.pipeline("prune", "--json").stdout)["kept"][0]["why"])
        self.archive().upload()
        self.assertEqual([r["id"] for r in json.loads(self.repo.pipeline("prune", "--json").stdout)["removed"]], [second.id])
        second = attempts.find(self.state(), second.id)
        self.assertFalse(second.work_dir.exists())
        self.assertEqual(self.restored(second.record["capture"]["occurrences"]["workdir"], "second-work")["scratch.txt"], unsealed)

    def test_prune_keeps_a_work_directory_that_changed_since_it_was_sealed(self):
        self.repo.close()
        self.repo = self.new_repo(keep_workdirs="failed")
        job_id = self.repo.submit("Failed", "--run", "echo x > scratch.txt; exit 3")
        self.repo.commit("job")
        self.repo.pipeline("run", "--rev", "HEAD")
        self.repo.pipeline("collect")
        self.archive().upload()
        (attempt,) = attempts.of(self.state(), job_id)
        (attempt.work_dir / "added-after.txt").write_text("someone looked into it, and left this\n")
        said = json.loads(self.repo.pipeline("prune", "--json").stdout)
        self.assertEqual((said["removed"], [k["why"] for k in said["kept"]]),
                         ([], ["its work directory is not what was sealed: it changed since"]))
        (attempt.work_dir / "added-after.txt").unlink()
        os.utime(attempt.work_dir / "scratch.txt")   # touched: its time is no longer the sealed one
        self.assertEqual(json.loads(self.repo.pipeline("prune", "--json").stdout)["removed"], [])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests of the second job format (itl-job/v2) through the pipeline's own entry point, jobs/pipeline.py: each in a
throwaway git repository, as verification/test_pipeline.py's are, and with the same helper.

  python3 jobs/test_formats.py

What they show is the brief's test of generality: a job that has nothing to do with Java or a checker uses the same
submission, scheduling, artifact, reporting and retry services, on a PATH with no checker on it; a job that says it
runs tests is held to evidence of them; a required output that is missing leaves a job unfulfilled whatever it
exited with; and a verification job that ran exactly as expected may have refuted its claim.
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "verification"))
os.environ["VERIFY_MACHINE_CONFIG"] = ""        # this machine's runner settings are not a test's
os.environ.setdefault("ITL_ORIGINALS_OFF", "1")
import pipeline  # noqa: E402
import test_pipeline  # noqa: E402

sandbox = pipeline.sandbox
DESCRIPTION = "A stub job of the second format, for testing the pipeline itself."
# What a machine with no checker still has: a shell, git, and the few commands the steps here call.
BARE = ["bash", "env", "sed", "git", "tar", "python3", "mkdir", "sha256sum", "cat", "sleep", "true", "false", "timeout"]


class Repo(test_pipeline.Repo):
    ENTRY = "jobs/pipeline.py"

    def submit2(self, title, purpose, *args, env=None):
        out = self.pipeline("submit", "--title", title, "--description", DESCRIPTION, "--purpose", purpose, *args, env=env).stdout
        return out.split("verification/jobs/")[1].split(".json")[0].rsplit("/", 1)[-1]

    def job(self, job_id):
        return json.loads(self.job_path(job_id).read_text())


class SecondFormat(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.close)

    def bare_path(self):
        """A PATH with a shell, git and coreutils on it and nothing else: no java, no jbmc, no cargo, no bwrap."""
        bare = Path(tempfile.mkdtemp(prefix="bare-path-"))
        self.addCleanup(shutil.rmtree, bare, True)
        for name in BARE:
            (bare / name).symlink_to(shutil.which(name))
        return {"PATH": str(bare), "JAVA_HOME": "", "JBMC": "", "TLA2TOOLS": ""}

    def run_all(self, env=None):
        self.repo.commit("jobs")
        return self.repo.pipeline("run", "--rev", "HEAD", env=env).stdout


class AJobThatIsNotVerification(SecondFormat):
    def test_a_non_java_job_is_submitted_scheduled_kept_reported_and_retried_where_no_checker_is_installed(self):
        bare = self.bare_path()
        (self.repo.dir / "README.md").write_text("what the artifact is made from\n")
        job_id = self.repo.submit2("Pack the manifest", "build", "--label", "project:docs", "--capability", "packing",
                                   "--case", "D01", "--phase", "build", "--output", "out/manifest.txt",
                                   "--run", "mkdir -p out && sha256sum README.md > out/manifest.txt", env=bare)
        job = self.repo.job(job_id)
        self.assertEqual((job["schema"], job["purpose"], job["case"], job["labels"]),
                         ("itl-job/v2", "build", "D01", {"project": ["docs"], "capability": ["packing"]}))
        self.assertEqual((self.repo.job_path(job_id).parent / job["$schema"]).resolve(), self.repo.dir.resolve() / "jobs/schema/job.schema.json")
        self.assertNotIn("capabilities", job)       # what the first format requires: a runner of before does not run this
        self.assertEqual(pipeline.workload_name(job), "generic")
        old_id = self.repo.submit("A job of the first format beside it", "--run", "true", env=bare)
        out = self.run_all(env=bare)
        self.assertIn(f"{job_id}: passed", out)
        self.assertIn(f"{old_id}: passed", out)
        result = self.repo.result(job_id, collected=False)
        self.assertEqual(result["schema"], "itl-job-result/v2")
        # The record of the machine asks for no checker, and the job's own requirements were looked for on PATH alone.
        self.assertEqual(sorted(result["environment"]["tools"]), ["coreutils", "git", "systemd"])
        self.assertEqual((result["status"], result["execution"]["status"], result["fulfillment"]), ("passed", "passed", {"state": "fulfilled", "unmet": []}))
        self.assertNotIn("conclusion", result)      # the generic workload concludes nothing
        declared, = result["declared"]
        self.assertEqual((declared["path"], declared["required"], declared["state"], declared["producer"]),
                         ("out/manifest.txt", True, "added", result["attempt"]["id"]))
        self.assertEqual(result["outputs"][0]["sha256"], pipeline.sha256((self.repo.dir / "verification/.state/results" / job_id / "outputs/out/manifest.txt").read_bytes()))
        step, = result["steps"]
        self.assertEqual((step["phase"], step["network"]["mode"]), ("build", "host"))
        timing = result["timing"]
        self.assertEqual((timing["requestedSteps"]["state"], timing["requestedSteps"]["ran"], timing["elapsed"]["state"], timing["preparation"]["state"]),
                         ("measured", 1, "measured", "measured"))
        self.assertEqual(list(timing["byPhase"]), ["build"])
        self.assertEqual(self.repo.result(old_id, collected=False)["schema"], "verification-result/v1")
        # Collected, reported and checked like any other.
        self.assertIn(f"{job_id}: passed: applied 1", self.repo.pipeline("collect", env=bare).stdout)
        self.assertTrue((self.repo.dir / "out/manifest.txt").exists())
        collected = self.repo.result(job_id)
        self.assertEqual((self.repo.collected(job_id) / collected["$schema"]).resolve(), self.repo.dir.resolve() / "jobs/schema/result.schema.json")
        self.assertEqual(pipeline.validate(collected, "result.schema.json"), [])
        self.assertEqual(self.repo.pipeline("validate", env=bare).returncode, 0)
        self.assertIn("packing", self.repo.pipeline("report", "--capability", "packing", env=bare).stdout)
        # A retry with other resources is a new job that names the old one; it is a job of the same format.
        again = self.repo.pipeline("resubmit", job_id, "--memory", "300M", env=bare).stdout
        new = self.repo.job(again.split("verification/jobs/")[1].split(".json")[0])
        self.assertEqual((new["schema"], new["supersedes"], new["resources"]["memory"], new["purpose"]), ("itl-job/v2", job_id, "300M", "build"))

    def test_a_required_output_that_is_missing_leaves_the_job_unfulfilled_though_every_step_exited_zero(self):
        missing = self.repo.submit2("Say it wrote a file", "build", "--output", "out/a.txt", "--run", "true")
        optional = self.repo.submit2("May write a file", "build", "--optional-output", "out/b.txt", "--run", "true")
        stopped = self.repo.submit2("Stops before it writes", "build", "--output", "out/c.txt",
                                    "--step", "fail", "exit 3", "--step", "write", "mkdir -p out && echo c > out/c.txt")
        self.run_all()
        result = self.repo.result(missing, collected=False)
        self.assertEqual((result["status"], result["execution"]["status"], result["execution"]["stopped"]), ("failed", "passed", None))
        self.assertEqual(result["fulfillment"]["state"], "unfulfilled")
        self.assertEqual([(u["kind"], u["path"], u["state"]) for u in result["fulfillment"]["unmet"]], [("output", "out/a.txt", "missing")])
        self.assertIn("not fulfilled: required output out/a.txt is not there (missing)", result["summary"])
        self.assertTrue(any("the job is not fulfilled without it" in a for a in result["attention"]))
        result = self.repo.result(optional, collected=False)
        self.assertEqual((result["status"], result["fulfillment"]["state"], result["declared"][0]["state"]), ("passed", "fulfilled", "missing"))
        result = self.repo.result(stopped, collected=False)
        self.assertEqual((result["status"], result["declared"][0]["state"]), ("failed", "never-reached"))
        self.assertEqual(result["execution"]["stopped"], {"step": 1, "name": "fail", "reason": "exit", "exitCode": 3})
        self.assertEqual(result["execution"]["skipped"], [{"step": 2, "why": "an earlier step failed"}])
        self.assertEqual([u["kind"] for u in result["fulfillment"]["unmet"]], ["step", "skipped", "output"])


class AJobThatSaysItRunsTests(SecondFormat):
    def test_real_tests_are_counted_and_a_step_that_ran_none_has_not_kept_its_promise(self):
        (self.repo.dir / "test_sums.py").write_text(
            "import unittest\n\nclass Sums(unittest.TestCase):\n    def test_one(self):\n        self.assertEqual(1 + 1, 2)\n"
            "    def test_two(self):\n        self.assertEqual(2 + 2, 4)\n\nif __name__ == '__main__':\n    unittest.main()\n")
        real = self.repo.submit2("Run the sums' tests", "test", "--phase", "test", "--tests", "2", "--run", "python3 test_sums.py")
        none = self.repo.submit2("Says it runs tests and compiles only", "test", "--phase", "test", "--tests", "1",
                                 "--step", "compile", "python3 -m py_compile test_sums.py", "--step", "after", "true")
        compile_only = self.repo.submit2("Compiles, and promises nothing", "build", "--run", "python3 -m py_compile test_sums.py")
        self.run_all()
        result = self.repo.result(real, collected=False)
        tests, = result["steps"][0]["evidence"]
        self.assertEqual((result["status"], tests["type"], tests["source"], tests["executed"], tests["unmet"]), ("passed", "tests", "log: unittest", 2, []))
        result = self.repo.result(none, collected=False)
        step = result["steps"][0]
        # The step's process went as expected (VF-070: three builds stopped at a test compile and their job passed).
        self.assertEqual((result["status"], step["status"], step["exitCode"], step["evidence"][0]["source"]), ("failed", "failed", 0, "none"))
        self.assertEqual(result["execution"]["stopped"]["reason"], "unmet-promise")
        self.assertEqual([u["kind"] for u in result["fulfillment"]["unmet"]], ["promise", "skipped"])
        self.assertIn("exited as expected and did not keep what it promised: 0 test(s) executed", " ".join(result["attention"]))
        self.assertNotIn("exited 0, expected 0", " ".join(result["attention"]))
        result = self.repo.result(compile_only, collected=False)
        self.assertEqual((result["status"], "evidence" in result["steps"][0]), ("passed", False))

    def test_an_expected_failing_assertion_is_a_fulfilled_job_and_not_a_build_failure(self):
        report = ('<testsuite name="Regression" tests="2"><testcase classname="Regression" name="holds"/>'
                  '<testcase classname="Regression" name="fails_before_the_fix"><failure message="expected 2, was 1"/></testcase></testsuite>')
        (self.repo.dir / "run_tests.sh").write_text(f"mkdir -p reports && cat > reports/TEST-Regression.xml <<'XML'\n{report}\nXML\nexit 1\n")
        expected = self.repo.submit2("The regression test fails on the revision before its fix", "test", "--expect-exit", "1",
                                     "--tests", "2", "--test-reports", "reports/*.xml", "--expect-failing", "fails_before_the_fix",
                                     "--run", "bash run_tests.sh")
        broke = self.repo.submit2("The build breaks before any test", "test", "--expect-exit", "1", "--tests", "1",
                                  "--test-reports", "reports/*.xml", "--expect-failing", "fails_before_the_fix", "--run", "exit 1")
        self.run_all()
        result = self.repo.result(expected, collected=False)
        tests, = result["steps"][0]["evidence"]
        self.assertEqual((result["status"], result["fulfillment"]["state"], tests["source"], tests["executed"], tests["failing"]),
                         ("passed", "fulfilled", "junit-xml", 2, ["Regression.fails_before_the_fix"]))
        result = self.repo.result(broke, collected=False)
        self.assertEqual((result["status"], result["execution"]["status"], result["fulfillment"]["state"]), ("failed", "passed", "unfulfilled"))


class AVerificationJobOfTheSecondFormat(SecondFormat):
    def test_a_job_that_ran_as_expected_may_have_refuted_its_claim_and_the_result_keeps_the_two_apart(self):
        # A stand-in for the checker: the line JBMC ends a refutation with, and its exit code for one.
        refuting = "echo '** 1 of 3 failed (2 iterations)'; echo 'VERIFICATION FAILED'; exit 10"
        second = self.repo.submit2("The checker refutes the claim", "verify", "--workload", "verification", "--expect-exit", "10",
                                   "--phase", "proof", "--run", refuting)
        first = self.repo.submit("The same, as a job of the first format", "--expect-exit", "10", "--run", refuting)
        self.run_all()
        for job_id in (second, first):
            result = self.repo.result(job_id, collected=False)
            self.assertEqual((result["status"], result["execution"]["status"], result["fulfillment"]["state"]), ("passed", "passed", "fulfilled"), job_id)
            self.assertEqual((result["conclusion"]["verdict"], result["conclusion"]["counts"]["refuted"]), ("refuted", 1), job_id)
        self.assertEqual(self.repo.result(second, collected=False)["timing"]["byPhase"].keys(), {"proof"})

    def test_a_workload_this_checkout_does_not_have_is_said_and_nothing_of_the_job_runs(self):
        job_id = self.repo.submit2("Asks for an adapter nobody wrote", "build", "--workload", "no_such_adapter",
                                   "--run", "echo ran > ran.txt", "--output", "ran.txt")
        beside = self.repo.submit2("A job this checkout can run", "build", "--run", "true")
        out = self.run_all()
        self.assertIn(f"{beside}: passed", out)
        self.assertNotIn(f"{job_id}: started", out)
        self.assertFalse((self.repo.dir / "verification/.state/results" / job_id).exists())
        status = self.repo.pipeline("status", "--rev", "HEAD").stdout
        self.assertIn("its workload 'no_such_adapter' has no adapter in this checkout", status)


class Prerequisites(SecondFormat):
    def state_file(self):
        return self.repo.dir / "verification/.state/scheduling.json"

    def test_a_dependent_starts_once_its_prerequisite_passed_and_what_a_failed_one_blocks_consumes_no_attempt(self):
        first = self.repo.submit2("Runs first, and looks at what the runner says of the rest", "build", "--output", "seen.json",
                                  "--run", "sleep 2; cat \"$VERIFY_RUNNER_ROOT/verification/.state/scheduling.json\" > seen.json")
        after = self.repo.submit2("Runs once the first passed", "build", "--needs", first, "--run", "true")
        fails = self.repo.submit2("Fails until the file is there", "build", "--run", "test -f there.txt")
        blocked = self.repo.submit2("Needs the one that fails", "build", "--needs", fails, "--run", "true")
        out = self.run_all()
        self.assertIn(f"{after}: waiting: {first} has not finished", out)
        self.assertIn(f"{blocked}: blocked: {fails} ended failed: resubmit it", out)
        done, later = self.repo.result(first, collected=False), self.repo.result(after, collected=False)
        self.assertEqual((done["status"], later["status"]), ("passed", "passed"))
        self.assertGreaterEqual(later["startedAt"], done["finishedAt"])
        # Nothing of the blocked job ran: no result, and no attempt of it on this machine.
        state = self.repo.dir / "verification/.state"
        self.assertFalse((state / "results" / blocked).exists())
        self.assertFalse((state / "attempts" / blocked).exists())
        # What the runner published while it was at work, as the first job's step read it; gone when the runner ended.
        seen = json.loads((state / "results" / first / "outputs/seen.json").read_text())
        self.assertEqual(seen["schema"], "itl-job-scheduling/v1")
        self.assertEqual(seen["jobs"][after], {"state": "waiting", "why": f"{first} has not finished"})
        self.assertFalse(self.state_file().exists())
        status = self.repo.pipeline("status", "--rev", "HEAD").stdout
        self.assertIn(f"blocked: {fails} ended failed", status)
        # The failed prerequisite is resubmitted at a commit where it passes: the job it blocked runs, its own file unchanged.
        (self.repo.dir / "there.txt").write_text("now\n")
        again = self.repo.pipeline("resubmit", fails).stdout.split("verification/jobs/")[1].split(".json")[0].rsplit("/", 1)[-1]
        out = self.run_all()
        self.assertIn(f"{again}: passed", out)
        self.assertIn(f"{blocked}: waiting: {again} (which supersedes {fails}) has not finished", out)
        self.assertEqual(self.repo.result(blocked, collected=False)["status"], "passed")

    def test_a_job_whose_prerequisite_nobody_can_finish_here_is_left_waiting_and_the_runner_ends(self):
        big = self.repo.submit2("Asks for more than the runner allows a job", "build", "--memory", "64G", "--run", "true")
        waits = self.repo.submit2("Needs the big one", "build", "--needs", big, "--run", "true")
        nobody = self.repo.submit2("Needs a job nobody submitted", "build", "--needs", "20200101-000000-never-submitted", "--run", "true")
        beside = self.repo.submit2("Needs nothing", "build", "--run", "true")
        out = self.run_all()
        self.assertIn(f"{big}: unschedulable: needs 64.0 GiB", out)
        self.assertIn(f"{waits}: left waiting: {big} has not finished", out)
        self.assertIn(f"{nobody}: blocked: 20200101-000000-never-submitted is not a job in the queue, and no result of it is recorded", out)
        self.assertIn(f"{beside}: passed", out)
        self.assertFalse((self.repo.dir / "verification/.state/results" / waits).exists())

    def test_a_readiness_prerequisite_blocks_until_receipts_are_read(self):
        (self.repo.dir / "job.json").write_text(json.dumps({
            "schema": "itl-job/v2", "purpose": "test", "title": "Needs a prepared bundle", "description": DESCRIPTION,
            "resources": {}, "steps": [{"run": "true"}], "needs": [{"readiness": "ab" * 32}]}))
        job_id = self.repo.submit2("Needs a prepared bundle", "test", "--from-file", "job.json")
        (self.repo.dir / "job.json").unlink()
        out = self.run_all()
        self.assertIn(f"{job_id}: blocked: readiness abababababab is asked for", out)


class TheNetworkAStepHas(SecondFormat):
    @unittest.skipUnless(sandbox.probe()["enforced"], "this host cannot take a step's network away (bubblewrap)")
    def test_a_step_with_no_network_runs_in_a_namespace_with_loopback_alone_and_the_result_keeps_what_was_seen(self):
        job_id = self.repo.submit2("Look at the interfaces", "test", "--network", "none", "--output", "seen.txt",
                                   "--run", "python3 -c \"import socket; print(sorted(n for _, n in socket.if_nameindex()))\" > seen.txt")
        self.run_all()
        result = self.repo.result(job_id, collected=False)
        network = result["steps"][0]["network"]
        self.assertEqual((result["status"], network["mode"], network["enforced"], network["probe"]["interfaces"]), ("passed", "none", True, ["lo"]))
        self.assertNotEqual(network["probe"]["connect"], "connected")
        self.assertEqual((self.repo.dir / "verification/.state/results" / job_id / "outputs/seen.txt").read_text(), "['lo']\n")

    def test_where_the_network_cannot_be_taken_away_the_job_is_not_started_and_the_queue_says_why(self):
        bare = self.bare_path()      # no bubblewrap on it
        job_id = self.repo.submit2("Would have run offline", "test", "--network", "none", "--run", "echo ran > ran.txt", "--output", "ran.txt", env=bare)
        beside = self.repo.submit2("Asks for no such thing", "test", "--run", "true", env=bare)
        out = self.run_all(env=bare)
        self.assertIn(f"{beside}: passed", out)
        self.assertNotIn(f"{job_id}: started", out)
        self.assertFalse((self.repo.dir / "verification/.state/results" / job_id).exists())
        self.assertIn("this machine cannot take the network away (bubblewrap (bwrap) is not installed",
                      self.repo.pipeline("status", "--rev", "HEAD", env=bare).stdout)

    def test_only_a_resolve_job_may_fetch(self):
        refused = self.repo.pipeline("submit", "--title", "A build that fetches", "--description", DESCRIPTION, "--purpose", "build",
                                     "--network", "fetch", "--run", "true", check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("only a resolve job has a fetch step", refused.stderr)


class WhoSubmitted(SecondFormat):
    def cgroup(self, text):
        path = Path(tempfile.mkdtemp(prefix="cgroup-")) / "cgroup"
        path.write_text(text)
        self.addCleanup(shutil.rmtree, path.parent, True)
        return {"VERIFY_CGROUP_FILE": str(path)}

    def test_a_job_carries_the_run_its_submitter_works_in_read_from_the_loops_scope(self):
        inside = self.cgroup("0::/user.slice/user-1000.slice/user@1000.service/app.slice/feature-loop-single-made-up-run.scope/sub\n")
        new = self.repo.job(self.repo.submit2("Submitted in a run", "build", "--run", "true", "--run-phase", "domain", env=inside))
        self.assertEqual((new["submitted"]["run"], new["submitted"]["phase"]), ("single-made-up-run", "domain"))
        old = self.repo.job(self.repo.submit("Submitted in a run, first format", "--run", "true", env=inside))
        self.assertEqual(old["submitted"]["run"], "single-made-up-run")
        self.assertEqual(pipeline.validate(old, "job.schema.json"), [])
        alone = self.cgroup("0::/user.slice/user-1000.slice/session-3.scope\n")
        job = self.repo.job(self.repo.submit2("Submitted by hand", "build", "--run", "true", env=alone))
        self.assertNotIn("run", job["submitted"])
        # A resubmission is its own submitter's: the run of the job it was made from is not carried over.
        again = self.repo.pipeline("resubmit", new["id"], env=alone).stdout
        self.assertNotIn("run", self.repo.job(again.split("verification/jobs/")[1].split(".json")[0])["submitted"])

    def test_what_only_the_second_format_says_is_refused_for_a_job_of_the_first(self):
        refused = self.repo.pipeline("submit", "--title", "Promises tests", "--description", DESCRIPTION, "--capability", "test",
                                     "--run", "true", "--tests", "1", "--network", "none", check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("--network, --tests: only a job of the second format says that; give it a --purpose", refused.stderr)
        self.assertEqual(list((self.repo.dir / "verification").glob("jobs/*.json")), [])


if __name__ == "__main__":
    unittest.main()

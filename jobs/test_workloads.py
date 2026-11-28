#!/usr/bin/env python3
"""Tests of the workload adapters (jobs/workloads/) and of how the pipeline chooses one for a job.

  python3 jobs/test_workloads.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["VERIFY_MACHINE_CONFIG"] = ""        # this machine's runner settings are not a test's
os.environ.setdefault("ITL_ORIGINALS_OFF", "1")
import pipeline  # noqa: E402


class WhichWorkload(unittest.TestCase):
    def test_a_job_of_the_first_format_is_the_verification_workloads_and_a_second_format_job_names_its_own(self):
        self.assertEqual(pipeline.workload_name({"schema": "verification-job/v1"}), "verification")
        self.assertEqual(pipeline.workload_name({}), "verification")                 # as every job was until 2026-11-27
        self.assertEqual(pipeline.workload_name({"schema": "itl-job/v2"}), "generic")
        self.assertEqual(pipeline.workload_name({"schema": "itl-job/v2", "workload": "verification"}), "verification")
        self.assertIs(pipeline.workload_of({"schema": "itl-job/v2"}), pipeline.workload("generic"))
        self.assertIsNone(pipeline.workload("no_such_adapter"))
        self.assertIsNone(pipeline.workload("../pipeline"))                          # a name, never a path

    def test_both_adapters_answer_everything_the_pipeline_asks(self):
        generic, verification = pipeline.workload("generic"), pipeline.workload("verification")
        asked = ["NAME", "SIGNALS", "SUSPICIOUS", "COLLECTORS_OWN", "tools", "missing", "reservation", "prepare", "step_env",
                 "scan", "verdicts", "conclusion"]
        for adapter in (generic, verification):
            self.assertEqual([name for name in asked if not hasattr(adapter, name)], [], adapter.NAME)
            self.assertIs(adapter.core, pipeline)

    def test_the_names_the_pipeline_had_while_it_was_verifications_alone_still_answer(self):
        verification = pipeline.workload("verification")
        self.assertIs(pipeline.SIGNALS, verification.SIGNALS)
        self.assertEqual(pipeline.missing_tools(["no-such-tool-anywhere"]), ["no-such-tool-anywhere"])
        self.assertEqual(pipeline.collectors_own(), ("verification", "examples/README.md", "examples/index.json"))


class TheGenericWorkload(unittest.TestCase):
    """What makes the pipeline usable where no checker is installed: it asks the machine for nothing but the job's
    own requirements, on PATH."""

    def setUp(self):
        self.generic = pipeline.workload("generic")

    def test_it_looks_for_a_requirement_on_the_path_and_knows_no_checker(self):
        with tempfile.TemporaryDirectory() as bare, mock.patch.dict(os.environ, {"PATH": bare, "JAVA_HOME": "/somewhere/else"}):
            tool = Path(bare) / "packer"
            tool.write_text("#!/bin/sh\n")
            tool.chmod(0o755)
            self.assertEqual(self.generic.missing(["packer", "java", "jbmc"]), ["java", "jbmc"])
            # The verification workload takes a JDK from JAVA_HOME; this one does not know what a JDK is.
            self.assertEqual(pipeline.workload("verification").missing(["java"]), [])

    def test_a_record_of_the_machine_lists_no_checker_and_probes_for_none(self):
        with mock.patch.object(pipeline, "_ENVIRONMENT", {}), mock.patch.object(pipeline, "first_line", lambda cmd: f"{cmd[0]} here") as _:
            tools = pipeline.environment("made-up", self.generic)["tools"]
            self.assertEqual(sorted(tools), ["coreutils", "git", "systemd"])
            verifying = pipeline.environment("made-up", pipeline.workload("verification"))["tools"]
            self.assertTrue({"java", "javac", "jbmc", "tlc", "cargo", "rustc"} <= set(verifying))

    def test_it_reserves_the_jobs_limit_adds_nothing_to_a_step_and_concludes_nothing(self):
        self.assertEqual(self.generic.reservation(None, {"requires": ["jvmcontract"]}, {"memoryLimit": 123}, "HEAD"), 123)
        env = {"PATH": "/bin"}
        self.generic.step_env(None, {}, {"limits": {"memoryLimitBytes": 1 << 30}}, Path("/nowhere"), env)
        self.assertEqual(env, {"PATH": "/bin"})
        self.assertIsNone(self.generic.conclusion({}, {"status": "passed", "steps": []}))

    def test_it_reads_one_thing_out_of_a_log(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "log"
            log.write_text("VERIFICATION SUCCESSFUL\nfatal: Cannot allocate memory\ntest result: ok. 3 passed; 0 failed\n")
            signals, counts, lines = self.generic.scan(log)
            self.assertEqual((counts, lines, [s["line"] for s in signals]), ({"memory:out-of-memory": 1}, 3, [2]))
            _, verifying, _ = pipeline.workload("verification").scan(log)
            self.assertEqual(verifying, {"jbmc:proved": 1, "memory:out-of-memory": 1, "cargo:tests": 1})


class WhatACheckerSaid(unittest.TestCase):
    """A job that ran as expected and a claim that held are two things."""

    def conclude(self, status, *steps):
        result = {"status": status, "steps": [{"index": i, "status": "passed", "signalCounts": counts, "signals": signals}
                                              for i, (counts, signals) in enumerate(steps, 1)]}
        return pipeline.workload("verification").conclusion({}, result)

    def example(self, verdict):
        return {"tool": "example", "kind": "as-expected", "line": 9, "text": "", "groups": ["146", verdict]}

    def test_a_job_that_passed_may_have_refuted_its_claim(self):
        refuted = self.conclude("passed", ({"tlc:invariant-violated": 1, "example:as-expected": 1}, [self.example("violation")]))
        self.assertEqual((refuted["verdict"], refuted["counts"]["refuted"], refuted["asExpected"]), ("refuted", 2, {"examples": 1, "unexpected": 0}))
        self.assertIn("at the bounds and the source revision of the job", refuted["scope"])
        proved = self.conclude("passed", ({"jbmc:proved": 2}, []))
        self.assertEqual((proved["verdict"], proved["counts"]), ("established", {"established": 2, "refuted": 0, "open": 0}))

    def test_no_checkers_line_is_never_established_and_steps_that_disagree_are_mixed(self):
        self.assertEqual(self.conclude("passed", ({"cargo:tests": 1}, []))["verdict"], "none")
        self.assertEqual(self.conclude("passed", ({}, []))["verdict"], "none")
        self.assertEqual(self.conclude("passed", ({"jbmc:proved": 1}, []), ({"jbmc:refuted": 1}, []))["verdict"], "mixed")
        self.assertEqual(self.conclude("passed", ({"jbmc:proved": 1, "jbmc:no-verdict": 1}, []))["verdict"], "open")
        # A job stopped at a limit gave no verdict, whatever its log held before it was stopped.
        self.assertEqual(self.conclude("timeout", ({"jbmc:proved": 1}, []))["verdict"], "none")


if __name__ == "__main__":
    unittest.main()

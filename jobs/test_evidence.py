#!/usr/bin/env python3
"""Tests of jobs/evidence.py: which tests a step executed, where that was read, and whether it keeps a promise.

  python3 jobs/test_evidence.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evidence  # noqa: E402

SUITE = """<?xml version="1.0"?>
<testsuite name="org.example.SbomTest" tests="4">
  <testcase classname="org.example.SbomTest" name="readsManifest"/>
  <testcase classname="org.example.SbomTest" name="findsPayload"><failure message="expected CycloneDX">at ...</failure></testcase>
  <testcase classname="org.example.SbomTest" name="opensArchive"{error}
  <testcase classname="org.example.SbomTest" name="onWindows"><skipped/></testcase>
</testsuite>
"""


class WhichTestsExecuted(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.log = self.work / "step.log"
        self.log.write_text("BUILD SUCCESSFUL in 4s\n")

    def report(self, error=False, name="build/test-results/test/TEST-org.example.SbomTest.xml"):
        path = self.work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(SUITE.replace("{error}", "><error>java.io.IOException</error></testcase>" if error else "/>"))

    def test_a_report_gives_the_suite_the_count_and_the_names(self):
        self.report()
        record = evidence.tests({"reports": ["build/test-results/**/*.xml"]}, self.work, self.log)
        self.assertEqual((record["type"], record["source"], record["reports"], record["suites"]),
                         ("tests", "junit-xml", 1, ["org.example.SbomTest"]))
        self.assertEqual((record["executed"], record["failed"], record["errors"], record["skipped"]), (3, 1, 0, 1))
        self.assertEqual(record["failing"], ["org.example.SbomTest.findsPayload"])
        self.assertEqual(record["unmet"], ["1 test(s) failed and 0 ended in an error"])

    def test_a_report_that_was_there_before_the_step_began_is_not_tests_the_step_ran(self):
        self.report()
        written = (self.work / "build/test-results").rglob("*.xml").__next__().stat().st_mtime
        stale = evidence.tests({"reports": ["build/test-results/**/*.xml"]}, self.work, self.log, since=written + 60)
        self.assertEqual((stale["source"], stale["executed"]), ("none", 0))          # an earlier step's, or one committed with the source
        self.assertEqual(evidence.tests({"reports": ["build/test-results/**/*.xml"]}, self.work, self.log, since=written - 60)["executed"], 3)

    def test_a_step_that_ran_no_test_has_not_kept_its_promise_whatever_it_exited_with(self):
        """VF-070, item 11: the build stopped at the test compile and the script around it exited 0."""
        self.log.write_text("> Task :compileTestGroovy FAILED\nBUILD FAILED in 9s\n")
        record = evidence.tests({"reports": ["build/test-results/**/*.xml"]}, self.work, self.log)
        self.assertEqual((record["source"], record["executed"]), ("none", 0))
        self.assertIn("0 test(s) executed, and the step promised at least 1", record["unmet"][0])
        self.assertIn("no file matches build/test-results/**/*.xml", record["unmet"][0])
        self.assertEqual(evidence.tests({"min": 0}, self.work, self.log)["unmet"], [])   # a step may promise that none need run

    def test_a_log_summary_is_read_when_no_report_is_named(self):
        cases = {
            "cargo test": ("running 3 tests\ntest result: ok. 3 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out; finished in 0.1s\n"
                           "test result: FAILED. 4 passed; 2 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.2s\n", (9, 2, 0, 1)),
            "unittest": ("......\n----------------------------------------------------------------------\nRan 6 tests in 0.268s\n\nOK\n", (6, 0, 0, 0)),
            "pytest": ("============ 5 passed, 1 failed, 2 skipped in 0.43s ============\n", (6, 1, 0, 2)),
            "maven surefire": ("[INFO] Tests run: 12, Failures: 1, Errors: 2, Skipped: 3\n", (9, 1, 2, 3)),
            "gradle": ("7 tests completed, 1 failed, 2 skipped\n", (5, 1, 0, 2)),
        }
        for source, (text, counts) in cases.items():
            self.log.write_text(text)
            record = evidence.tests({}, self.work, self.log)
            self.assertEqual((record["source"], record["executed"], record["failed"], record["errors"], record["skipped"]),
                             (f"log: {source}", *counts), source)
        self.log.write_text("Ran 3 tests in 0.1s\n\nFAILED (failures=1, errors=1, skipped=1)\n")
        record = evidence.tests({}, self.work, self.log)
        self.assertEqual((record["executed"], record["failed"], record["errors"], record["skipped"]), (2, 1, 1, 1))

    def test_an_expected_failing_assertion_keeps_the_promise_and_a_broken_build_does_not(self):
        """The regression test on the revision before its fix: the step's tool exits with its failure code, as the
        job expects, and what makes that the expected failure is the named test failing in a test."""
        promise = {"reports": ["build/test-results/**/*.xml"], "failing": ["findsPayload"]}
        self.report()
        self.assertEqual(evidence.tests(promise, self.work, self.log)["unmet"], [])
        self.assertEqual(evidence.tests({**promise, "failing": ["org.example.SbomTest.findsPayload"]}, self.work, self.log)["unmet"], [])
        # Another test failed instead, or as well: not the failure that was to be shown.
        said = evidence.tests({**promise, "failing": ["readsManifest"]}, self.work, self.log)["unmet"]
        self.assertEqual(said, ["expected to fail by assertion, and did not: readsManifest",
                                "failed, and was not expected to: org.example.SbomTest.findsPayload"])
        # An error is not an assertion.
        self.report(error=True)
        self.assertIn("1 test(s) ended in an error, not an assertion: org.example.SbomTest.opensArchive",
                      evidence.tests(promise, self.work, self.log)["unmet"])
        # The build broke before any test ran: the exit code is the expected one, and nothing was shown.
        (self.work / "build/test-results/test/TEST-org.example.SbomTest.xml").unlink()
        said = evidence.tests(promise, self.work, self.log)["unmet"]
        self.assertIn("0 test(s) executed", said[0])
        self.assertIn("only a report names the tests that did", said[1])

    def test_a_report_that_cannot_be_read_is_not_evidence_of_nothing(self):
        self.report()
        (self.work / "build/test-results/test/TEST-cut.xml").write_text("<testsuite name='cut'><testcase")
        record = evidence.tests({"reports": ["build/test-results/**/*.xml"], "failing": ["findsPayload"]}, self.work, self.log)
        self.assertEqual((record["executed"], len(record["unreadable"])), (3, 1))
        self.assertTrue(any("could not be read: TEST-cut.xml" in u for u in record["unmet"]))


if __name__ == "__main__":
    unittest.main()

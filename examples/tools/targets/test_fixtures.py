#!/usr/bin/env python3
"""Tests of the Phase 0 fixtures (examples/tools/targets/fixtures/): they build deterministically, the recorded runs
are what the builder and the oracle say, and the constructed bad runs and receipts are the kinds the checks must
reject. Offline; it compiles the fixture sources (a few seconds) and runs no proof.

  python3 examples/tools/targets/test_fixtures.py
"""

import dataclasses
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(FIXTURES))
import build  # noqa: E402
import build_fixtures  # noqa: E402
import result_format  # noqa: E402
from targets import interfaces, sidecar  # noqa: E402

RECORD_FIELDS = {f.name for f in dataclasses.fields(interfaces.ExecutionRecord)}


def oracle():
    spec = importlib.util.spec_from_file_location("fixture_oracle", FIXTURES / "gate/oracle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(name):
    return json.loads((FIXTURES / "records" / name).read_text())


class FixturesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        cls.manifest = build_fixtures.build(cls.dir.name)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_the_jars_build_deterministically_and_match_the_recorded_runs(self):
        with tempfile.TemporaryDirectory() as again:
            self.assertEqual(build_fixtures.build(again)["jars"], self.manifest["jars"])
        if self.manifest["javac"] == read("controls.json")["fixtures"]["javac"]:
            self.assertEqual(self.manifest["jars"], read("controls.json")["fixtures"]["jars"],
                             "the fixture JARs differ from the ones the records were made with: rerun make_records.py")

    def test_the_sidecar_is_valid(self):
        example = json.loads((FIXTURES / "example.json").read_text())
        target = sidecar.load(FIXTURES, example)
        self.assertEqual(target["identity"]["role"], "control")
        self.assertEqual({t["id"]: t.get("expected") for t in target["tasks"]},
                         {"vulnerable-security": "refuted", "fixed-security": "established", "preservation": "established",
                          "mutant-security": "refuted", "regex-probe": "unresolved", "replay": None,
                          "mutant-replay": None})

    def test_the_recorded_controls_are_execution_records_the_oracle_reads(self):
        o = oracle()
        records = read("controls.json")["records"]
        self.assertEqual({(r["revision"], r["identities"]["jdk"].split('"')[1].split(".")[0]) for r in records},
                         {(rev, jdk) for rev in ("before", "after", "mutant") for jdk in ("21", "25")})
        for r in records:
            interfaces.ExecutionRecord(**{k: v for k, v in r.items() if k in RECORD_FIELDS})
            lines = (FIXTURES / "records" / r["stdout"]).read_text().splitlines()
            problems = [code for code, _ in o.check(lines)]
            self.assertEqual(problems, {"before": [97], "after": [], "mutant": [65]}[r["revision"]], r["stdout"])
            self.assertEqual([list(p) for p in o.check(lines)], r["oracleProblems"])

    def test_the_capability_refusal_names_the_regex_calls(self):
        record = read("regex-gate-gaps.json")["record"]
        interfaces.ExecutionRecord(**record)
        scan = json.loads((FIXTURES / "records" / record["stdout"]).read_text())
        self.assertEqual(sorted(g["call"] for g in scan["gaps"]),
                         ["java.util.regex.Matcher.matches()", "java.util.regex.Pattern.compile(java.lang.String)",
                          "java.util.regex.Pattern.matcher(java.lang.CharSequence)"])

    def test_the_bad_runs_are_records_whose_output_is_not_a_result(self):
        o = oracle()
        bad = read("bad-runs.json")["records"]
        for name in ("killed-control", "malformed-control", "exit-one-verifier"):
            r = interfaces.ExecutionRecord(**bad[name])
            self.assertIsNone(r.observations, name)
        for r in bad["one-sided-replay"]:
            interfaces.ExecutionRecord(**r)
        self.assertEqual([r["status"] for r in bad["one-sided-replay"]], ["exited", "not-started"])
        with self.assertRaises(ValueError):  # a killed control's partial output: an incomplete replay
            o.check((FIXTURES / "records/killed.stdout").read_text().splitlines())
        with self.assertRaises(ValueError):  # malformed output is unreadable, never a violation
            o.check((FIXTURES / "records/malformed.stdout").read_text().splitlines())

    def test_the_bad_receipts_are_refused(self):
        import jsonschema
        stored = json.loads((build.EXAMPLES / "schema/stored-result.schema.json").read_text())
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(json.loads((FIXTURES / "results/incomplete/result.json").read_text()), stored)
        mismatch = FIXTURES / "results/bundle-mismatch"
        result = result_format.load(mismatch / "result.json")
        self.assertEqual(build.bundle_problems(mismatch, result),
                         ["verifier-output.txt is not the file the run left (its SHA-256 differs)"])


if __name__ == "__main__":
    unittest.main()

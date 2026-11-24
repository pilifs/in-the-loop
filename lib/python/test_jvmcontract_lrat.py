"""Small in-process controls for the ordinary native verdict's SAT evidence."""

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import jvmcontract_lrat as lrat


class CallBoundary(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory()
        self.addCleanup(area.cleanup)
        self.root = Path(area.name)
        self.request = {"schema": "native-sat-request/v1", "run": "fixture"}
        self.ordinary = {"status": "established", "execution": "fixture"}

    def capture(self, body, clauses, calls, verdict="Verified", ending="verified"):
        folder = self.root / "solver-traces"
        folder.mkdir(exist_ok=True)
        trace = folder / "one.icnf"
        count = len(calls) - calls.count("F")
        trace.write_text(f"p inccnf\n{body}c end: {clauses} clauses, {count} calls; {verdict}\n")
        (self.root / "bmc.log").write_text(
            f"{verdict}: 1 paths, 0 merged at joins, {len(calls)} solver calls (0.00 s), "
            f"1 variables, {clauses} clauses, 0.00 s; solver boundary [{calls}]; solver calls written to {trace}\n"
        )
        runs = [{"checker": "native", "ended": ending, "purpose": "proof", "formula": {"clauses": clauses}}]
        return lrat.capture(self.request, self.ordinary, self.root, folder, runs)

    def test_actual_sat_assignments_satisfy_the_prefix_and_assumption_at_their_own_call(self):
        body = "1 2 0\na -1 0\nc answer sat\nc model 1 01\n2 0\na 1 0\nc answer sat\nc model 2 11\n"
        boundary, streams = self.capture(body, 2, "SFS")
        first, folded, second = list(lrat.trace_events(streams[0].read_bytes(), boundary["passes"][0]))
        self.assertEqual((first[0]["attempt"], first[0]["clausePrefix"], first[0]["assumptionUnits"]), (1, 1, [-1]))
        self.assertEqual((folded[0]["status"], folded[1]), ("constant-false", None))
        self.assertEqual((second[0]["attempt"], second[0]["call"], second[0]["clausePrefix"]), (3, 2, 2))
        self.assertEqual(second[1], b"p cnf 2 3\n1 2 0\n2 0\n1 0\n")
        good = self.root / "original.zip"
        lrat.issue(self.request, boundary, streams, good)
        changed = self.root / "mistyped.zip"
        with zipfile.ZipFile(good) as original, zipfile.ZipFile(changed, "w") as output:
            manifest = json.loads(original.read("manifest.json"))
            manifest["events"][0]["call"] = True
            for name in original.namelist():
                output.writestr(name, json.dumps(manifest) if name == "manifest.json" else original.read(name))
        with self.assertRaisesRegex(ValueError, "1-proof/1: call differs from the native call"):
            lrat.verify(self.request, boundary, changed)
        for bits in ("01", "10"):
            with self.subTest(second_assignment=bits):
                bad, inputs = self.capture(body.replace("c model 2 11", f"c model 2 {bits}"), 2, "SFS")
                with self.assertRaisesRegex(ValueError, "1-proof/3: original SAT assignment violates"):
                    list(lrat.trace_events(inputs[0].read_bytes(), bad["passes"][0]))

    def test_zero_call_pass_rejects_each_surplus_event_including_null(self):
        boundary, streams = self.capture("", 0, "")
        archive = self.root / "evidence.zip"
        lrat.issue(self.request, boundary, streams, archive)
        verdict = lrat.verify(self.request, boundary, archive)
        self.assertEqual(verdict["unsatCoverage"], "no UNSAT calls")
        self.assertEqual(verdict["passes"], [{"id": "1-proof", "solverFree": True, "attempts": 0, "answers": {}}])
        with zipfile.ZipFile(archive) as original:
            manifest = json.loads(original.read("manifest.json"))
            for extra in (None, {"key": "1-proof/1"}):
                with self.subTest(extra=extra):
                    changed = self.root / "extra.zip"
                    with zipfile.ZipFile(changed, "w") as output:
                        for name in original.namelist():
                            data = json.dumps({**manifest, "events": [extra]}) if name == "manifest.json" else original.read(name)
                            output.writestr(name, data)
                    with self.assertRaisesRegex(ValueError, "unmatched event after the final native pass"):
                        lrat.verify(self.request, boundary, changed)

    def test_an_interrupted_pass_preserves_the_first_undecided_call(self):
        for ending in ("no-verdict", "out-of-time"):
            with self.subTest(ending=ending):
                boundary, streams = self.capture("a 0\nc answer unknown\n", 0, "F?", "Unverifiable", ending)
                with self.assertRaisesRegex(ValueError, "1-proof/2: solver returned unknown or interrupted"):
                    list(lrat.trace_events(streams[0].read_bytes(), boundary["passes"][0]))
        incomplete, streams = self.capture("", 0, "", "Unverifiable", "no-verdict")
        with self.assertRaisesRegex(ValueError, "1-proof: native pass ended without a verdict"):
            list(lrat.trace_events(streams[0].read_bytes(), incomplete["passes"][0]))


if __name__ == "__main__":
    unittest.main()

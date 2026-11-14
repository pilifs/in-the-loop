#!/usr/bin/env python3
"""Tests of the hooks Phase 0 of llm-dlc/loops/example-targets.md adds: build.py's --task (plan and run), its
real-world gate opened only for a sidecar example, route.py's chain of the interfaces, the index projection and
find.py's target filters. Offline, on a stub examples/ directory; nothing is built or proved.

  python3 examples/tools/targets/test_route.py
"""

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent
sys.path.insert(0, str(TOOLS))
import build  # noqa: E402
import find  # noqa: E402
from targets import interfaces, route, runtime, workflow  # noqa: E402

A, B = "a" * 40, "b" * 40
EXAMPLE = {
    "id": "285", "title": "t", "summary": "s", "origin": "real-world", "categories": ["security"],
    "tags": ["open-source-libraries"], "severity": "low", "subject": {"system": "S", "symbol": "fixture.Gate#allowed"},
    "approach": {"id": "B11", "name": "Property proofs", "tool": "lib"}, "change": {"kind": "bug-fix"},
    "source": {"kind": "commit", "repository": "https://github.com/a/b", "url": "https://github.com/a/b/commit/x"},
    "verdictLabel": "not run", "target": "target.json"}
TARGET = {
    "schema": "example-target/v1", "identity": {"case": "c", "family": "fixture", "role": "negative"},
    "history": {"repository": "https://github.com/a/b",
                "revisions": {"vulnerable": {"commit": A}, "fixed": {"commit": B, "parent": A}},
                "pairs": [{"name": "fix", "kind": "exact-fix", "before": "vulnerable", "after": "fixed"}]},
    "tasks": [{"id": "fixed-security", "kind": "prove", "relation": "security", "revision": "fixed",
               "target": "fixture.Gate#allowed", "expected": "established", "engine": "native", "gaps": "strict"},
              {"id": "preservation", "kind": "equivalence", "relation": "preservation", "pair": "fix",
               "target": "fixture.Gate#allowed", "expected": "established"}],
    "handoff": {"blockers": [{"kind": "java-semantics", "observed": True, "task": "fixed-security", "summary": "regex"}]}}


class StubExamples(unittest.TestCase):
    """A temporary examples/ with the real schemas, a tag vocabulary, one sidecar example (285) and one handwritten
    real-world example without a sidecar (105)."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        root = Path(self.dir.name)
        shutil.copytree(build.EXAMPLES / "schema", root / "schema")
        (root / "tags.json").write_text(json.dumps({"domain": {"open-source-libraries": "d"}}))
        (root / "README.md").write_text("<!-- examples:begin --><!-- examples:end -->\n<!-- tags:begin --><!-- tags:end -->\n")
        self.folder = root / "285-a-target"
        self.folder.mkdir()
        (self.folder / "example.json").write_text(json.dumps(EXAMPLE))
        (self.folder / "target.json").write_text(json.dumps(TARGET))
        legacy = root / "105-handwritten"
        legacy.mkdir()
        (legacy / "example.json").write_text(json.dumps({**{k: v for k, v in EXAMPLE.items() if k != "target"}, "id": "105"}))
        self.root = root
        for patch in (mock.patch.object(build, "EXAMPLES", root), mock.patch.object(find, "EXAMPLES", root),
                      mock.patch.dict(build._TAGS, clear=True)):
            patch.start()
            self.addCleanup(patch.stop)

    def tearDown(self):
        self.dir.cleanup()

    def build(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = build.main(list(argv))
        return code, out.getvalue(), err.getvalue()


class BuildHooksTest(StubExamples):
    def test_the_plan_of_a_task_names_the_unsupported_result(self):
        code, out, _ = self.build("--plan", "285", "--task", "fixed-security")
        self.assertEqual(code, 0)
        [p] = json.loads(out)
        self.assertEqual((p["task"], p["executable"], p["unsupported"]["owner"]),
                         ("fixed-security", False, interfaces.WORKFLOW))
        self.assertIn("unsupported: task-plan", p["notExecuted"])

    def test_the_plan_of_a_sidecar_example_lists_its_tasks(self):
        code, out, _ = self.build("--plan", "285")
        [p] = json.loads(out)
        self.assertFalse(p["executable"])
        self.assertIn("--task", p["notExecuted"])
        self.assertEqual([t["task"] for t in p["tasks"]], ["fixed-security", "preservation"])

    def test_running_a_task_stops_at_the_first_unsupported_result(self):
        code, out, _ = self.build("285", "--task", "fixed-security")
        self.assertEqual(code, 1)
        self.assertIn("285-a-target: not-executed (task fixed-security: unsupported: task-plan (example-targets-workflow)", out)

    def test_the_gate_opens_only_with_a_task_and_a_sidecar(self):
        code, out, _ = self.build("285")
        self.assertEqual(code, 1)
        self.assertIn("run one task at a time, with --task", out)
        code, out, _ = self.build("105")
        self.assertEqual(code, 1)
        self.assertIn("its report is its README.md", out)
        code, _, err = self.build("105", "--task", "fixed-security")
        self.assertEqual(code, 2)
        self.assertIn("has no target sidecar", err)

    def test_a_bad_task_argument_runs_nothing(self):
        for argv, fragment in [(("285", "--task", "nothing"), "has no task 'nothing'"),
                               (("285", "105", "--task", "fixed-security"), "exactly one example id"),
                               (("--render-only", "285", "--task", "fixed-security"), "not --render-only"),
                               (("285", "--task"), "not an example id")]:
            code, _, err = self.build(*argv)
            self.assertEqual(code, 2, argv)
            self.assertIn(fragment, err, argv)

    def test_an_invalid_sidecar_stops_the_example_being_read(self):
        (self.folder / "target.json").write_text(json.dumps({**TARGET, "extra": 1}))
        with self.assertRaises(SystemExit) as stop:
            build.load_example(self.folder)
        self.assertIn("Additional properties", str(stop.exception))


class IndexAndFindTest(StubExamples):
    def test_the_index_carries_the_projection_beside_the_historical_label(self):
        build.render_index(sorted(p for p in self.root.iterdir() if p.is_dir() and p.name[:3].isdigit()))
        index = {e["id"]: e for e in json.loads((self.root / "index.json").read_text())["examples"]}
        self.assertIsNone(index["105"]["target"])
        t = index["285"]["target"]
        self.assertEqual((t["family"], t["role"], t["readiness"], t["gaps"]), ("fixture", "negative", "catalogued", ["java-semantics"]))
        self.assertEqual(index["285"]["verdictLabel"], "not run")  # the authored label, never a receipt's
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(find.main(["--role", "negative"]), 0)
            self.assertEqual(find.main(["--gap", "java-semantics", "--family", "fixture"]), 0)
            self.assertEqual(find.main(["--readiness", "catalogued"]), 0)
            self.assertEqual(find.main(["--readiness", "blocked"]), 1)
            self.assertEqual(find.main(["--gap", "replay"]), 1)
            self.assertEqual(find.main(["--claim-status", "established"]), 1)
        self.assertIn("285", out.getvalue())
        self.assertNotIn("105  ", out.getvalue())


def a_plan():
    return interfaces.TaskPlan(example="285", task="preservation", kind="equivalence", relation="preservation",
                               target="fixture.Gate#allowed", revisions=("vulnerable", "fixed"), claim={}, prerequisites=(),
                               artifacts=(), tools={"required": [], "optional": []}, engine="native", gaps="strict",
                               expected="established", outputs={"receipts": "receipts/preservation"},
                               folder="/nonexistent/285-a-target")


def prepared(revision, stage="artifacts-ready", **fields):
    return interfaces.PreparedTarget(example="285", task="preservation", revision=revision, commit=A, stage=stage,
                                     source={}, **fields)


class RouteChainTest(unittest.TestCase):
    """route.run with implementations patched in: the chain's order, and where it stops."""

    def setUp(self):
        self.calls = []
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def patched(self, **impl):
        defaults = {
            (workflow, "plan_task"): lambda *a: self.log("plan") or a_plan(),
            (runtime, "prepare"): lambda p, revision, w: self.log(f"prepare {revision}") or prepared(revision),
            (runtime, "run_controls"): lambda p, prep, w: self.log("controls " + ",".join(prep)) or (),
            (runtime, "run_verifier"): lambda p, prep, w: self.log("verifier") or interfaces.ExecutionRecord(
                kind="verifier", revision=None, argv=("jvmcontract",), status="exited", exitCode=0, seconds=1.0,
                stdout="o", stderr="e", identities={}),
            (workflow, "ingest"): lambda p, prep, records, out: self.log(f"ingest {len(records)}") or interfaces.Receipt(
                path="receipts/preservation/x/result.json", claim="c" * 16, attempt="x", status="established", execution="completed"),
        }
        for (module, name), fn in defaults.items():
            patch = mock.patch.object(module, name, impl.get(name, fn))
            patch.start()
            self.addCleanup(patch.stop)

    def log(self, what):
        self.calls.append(what)

    def run_route(self):
        return route.run(self.dir.name, EXAMPLE, TARGET, "preservation", Path(self.dir.name) / "work")

    def test_the_whole_chain_gives_the_receipt(self):
        self.patched()
        receipt = self.run_route()
        self.assertEqual(receipt.status, "established")
        self.assertEqual(self.calls, ["plan", "prepare vulnerable", "prepare fixed", "controls vulnerable,fixed", "verifier", "ingest 1"])

    def test_a_failed_preparation_is_returned_with_its_stage_and_nothing_runs_after_it(self):
        self.patched(prepare=lambda p, revision, w: self.log(f"prepare {revision}") or prepared(
            revision, stage="failed", failedStage="build", diagnostic="gradlew: exit 1"))
        result = self.run_route()
        self.assertTrue(interfaces.unsupported(result))
        self.assertEqual((result.interface, result.stage, result.diagnostic), ("prepare", "build", "gradlew: exit 1"))
        self.assertEqual(self.calls, ["plan", "prepare vulnerable"])

    def test_a_source_locked_preparation_is_not_enough_to_run(self):
        self.patched(prepare=lambda p, revision, w: prepared(revision, stage="source-locked"))
        result = self.run_route()
        self.assertTrue(interfaces.unsupported(result))
        self.assertIn("not artifacts-ready", result.reason)

    def test_an_unknown_task_is_an_error_not_an_unsupported_result(self):
        with self.assertRaises(route.UnknownTask):
            route.run(self.dir.name, EXAMPLE, TARGET, "nothing", Path(self.dir.name))

    def test_an_implementation_that_returns_something_else_is_an_error(self):
        self.patched(plan_task=lambda *a: {"executable": True})
        with self.assertRaises(TypeError):
            self.run_route()


if __name__ == "__main__":
    unittest.main()

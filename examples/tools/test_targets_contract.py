#!/usr/bin/env python3
"""The integration contract of llm-dlc/loops/example-targets.md, written in Phase 0 before the streams fork: one test
per Tier A row (llm-dlc/loops/example-targets-acceptance.md) that the streams' work can reach on Phase 0's fixtures
(examples/tools/targets/fixtures/). Each test either reaches the row's final outcome or stops at the named
Unsupported result of a Phase 0 stub its stream hasn't replaced yet, which it reports as a skip naming the stub. Any
other Unsupported, a wrong type, or a wrong outcome fails.

  python3 examples/tools/test_targets_contract.py -v      (the -v lists which rows reached and which stopped where)

Runtime's tests use a TaskPlan built here from the sidecar and workflow's use PreparedTargets and records built here
from the fixtures, so each stream's rows move as soon as its own work lands, without waiting for the other. The
real-world halves of A3-A5 (Spring packets, example 105) are Phase 5's, on the merged revision; here they run on the
fixture's revisions. A5 here runs the tool's own checker on a one-line int method, only where a built jvmcontract is
found. Rows not reachable on fixtures: A8's queued acceptance jobs (Phase 5).

This file was the coordinator's while the example-targets brief ran as streams (2026-11-14): the streams made it
pass and never edited it, and that run's integration check reported a failure here as CONTRACT FAILED.
"""

import contextlib
import dataclasses
import importlib.util
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "targets/fixtures"))
import build  # noqa: E402
import build_fixtures  # noqa: E402
import result_format  # noqa: E402
from targets import interfaces, route, runtime, sidecar, workflow  # noqa: E402
from targets.interfaces import RUNTIME, WORKFLOW, Unsupported  # noqa: E402

FIXTURES = HERE / "targets/fixtures"
STUB = "Phase 0's stub"  # every Phase 0 stub's reason says so; nothing else may
FIXTURE_ID = "999"


def oracle():
    spec = importlib.util.spec_from_file_location("fixture_oracle", FIXTURES / "gate/oracle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def jvmcontract():
    found = os.environ.get("JVMCONTRACT") or str(build.REPO / "lib/target/release/jvmcontract")
    return found if Path(found).is_file() and os.access(found, os.X_OK) else None


def tree(folder):
    """Every file under `folder` with its size and mtime: what a pure operation must leave as it was."""
    return {p.relative_to(folder).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(Path(folder).rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


@contextlib.contextmanager
def offline():
    """No network and no subprocess: planning, discovery and handoff inspection run inside this."""
    def refuse(*a, **k):
        raise AssertionError("an offline operation opened a connection or started a process")
    with mock.patch.object(socket.socket, "connect", refuse), mock.patch.object(socket, "create_connection", refuse), \
            mock.patch.object(subprocess, "Popen", refuse), mock.patch.object(os, "system", refuse):
        yield


_MANIFEST = []


def fixture_manifest():
    """build_fixtures.py's manifest of the fixture JARs, built once per run."""
    if not _MANIFEST:
        directory = tempfile.mkdtemp(prefix="targets-contract-")
        _MANIFEST.append(build_fixtures.build(directory))
        import atexit
        atexit.register(shutil.rmtree, directory, True)
    return _MANIFEST[0]


class Contract(unittest.TestCase):
    """A temporary examples/ holding a copy of the fixture as example 999, with the real schemas."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = fixture_manifest()

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        root = Path(self.dir.name) / "examples"
        shutil.copytree(build.EXAMPLES / "schema", root / "schema")
        (root / "tags.json").write_text(json.dumps({"domain": {"open-source-libraries": "d"}}))
        (root / "README.md").write_text("<!-- examples:begin --><!-- examples:end -->\n<!-- tags:begin --><!-- tags:end -->\n")
        self.folder = root / f"{FIXTURE_ID}-phase0-fixture"
        shutil.copytree(FIXTURES, self.folder, ignore=shutil.ignore_patterns("__pycache__"))
        for patch in (mock.patch.object(build, "EXAMPLES", root), mock.patch.dict(build._TAGS, clear=True)):
            patch.start()
            self.addCleanup(patch.stop)
        self.example = build.load_example(self.folder)
        self.target = sidecar.load(self.folder, self.example)
        self.work = Path(self.dir.name) / "work"

    # -- reaching a row, or stopping at a stub

    def reach(self, value, interface, owner):
        """`value` if it is not Unsupported. A Phase 0 stub of `interface` by `owner` ends the test as a skip that
        names it; any other Unsupported fails."""
        if isinstance(value, Unsupported):
            if value.interface == interface and value.owner == owner and STUB in value.reason:
                self.skipTest(f"stops at {value.describe()}")
            self.fail(f"expected {interface} to reach its outcome or stop at its Phase 0 stub, got {value.describe()} "
                      f"(stage {value.stage}, diagnostic {value.diagnostic})")
        return value

    def task(self, task_id):
        return next(t for t in self.target["tasks"] if t["id"] == task_id)

    def revisions_of(self, t):
        if "pair" in t:
            pair = next(p for p in self.target["history"]["pairs"] if p["name"] == t["pair"])
            return (pair["before"], pair["after"])
        return (t["revision"],)

    def fixture_plan(self, task_id):
        """The TaskPlan of a fixture task built here, from the sidecar, for runtime's and workflow's rows: so neither
        waits for the other's implementation."""
        t = self.task(task_id)
        revisions = self.revisions_of(t)
        prep = self.target["preparation"]
        artifacts = tuple({"revision": r, "route": prep["route"], "repository": self.target["history"]["repository"],
                           "fixture": self.target["history"]["revisions"][r]["fixture"],
                           "adapters": prep.get("adapters", []), "jdks": prep.get("jdks", [])} for r in revisions)
        return interfaces.TaskPlan(
            example=FIXTURE_ID, task=task_id, kind=t["kind"], relation=t["relation"], target=t["target"],
            revisions=revisions, claim={"task": task_id, "allowedChange": t.get("allowedChange"), "bounds": t.get("bounds", {})},
            prerequisites=tuple(t.get("requires", [])), artifacts=artifacts,
            tools={"required": ["java", "javac"] + (["jvmcontract"] if t["kind"] != "replay" else []), "optional": []},
            engine=t.get("engine"), gaps=t.get("gaps"), expected=t.get("expected"),
            outputs={"receipts": f"receipts/{task_id}"}, folder=str(self.folder))

    def fixture_prepared(self, revision, task="replay"):
        """A PreparedTarget built here from the fixture JARs, for workflow's rows."""
        jars = self.manifest["jars"]
        return interfaces.PreparedTarget(
            example=FIXTURE_ID, task=task, revision=revision, commit=f"fixture:gate/{revision}", stage="artifacts-ready",
            source={"fixture": f"gate/{revision}"},
            artifacts=(interfaces.Artifact(f"{revision}.jar", jars[revision]["sha256"], "original"),
                       interfaces.Artifact(f"adapter-{revision}.jar", jars[f"adapter-{revision}"]["sha256"], "adapter"),
                       interfaces.Artifact("driver.jar", jars["driver"]["sha256"], "driver")),
            classpath=("driver.jar", f"adapter-{revision}.jar", f"{revision}.jar"),
            toolchain={"jdk": {"feature": "25", "version": self.manifest["java"]}})

    def recorded(self, revisions=("before", "after")):
        """The recorded controls (records/controls.json) of these revisions, as ExecutionRecords."""
        fields = {f.name for f in dataclasses.fields(interfaces.ExecutionRecord)}
        records = json.loads((self.folder / "records/controls.json").read_text())["records"]
        return tuple(interfaces.ExecutionRecord(**{k: (tuple(v) if isinstance(v, list) and k in ("argv", "observations") else v)
                                                   for k, v in r.items() if k in fields})
                     for r in records if r["revision"] in revisions)

    def bad(self, name):
        fields = {f.name for f in dataclasses.fields(interfaces.ExecutionRecord)}
        value = json.loads((self.folder / "records/bad-runs.json").read_text())["records"][name]
        make = lambda r: interfaces.ExecutionRecord(**{k: v for k, v in r.items() if k in fields})
        return tuple(make(r) for r in value) if isinstance(value, list) else (make(value),)

    def stored(self, folder, receipt):
        """The receipt's stored document, checked: format 2, valid against both result schemas."""
        import jsonschema
        path = Path(folder) / receipt.path
        self.assertTrue(path.is_file(), f"the receipt {receipt.path} is not where it says")
        document = json.loads(path.read_text())
        self.assertEqual(result_format.stored_format(document), 2)
        jsonschema.validate(document, json.loads((build.EXAMPLES / "schema/stored-result.schema.json").read_text()))
        jsonschema.validate(result_format.view(document), json.loads((build.EXAMPLES / "schema/result.schema.json").read_text()))
        return document


class A0SharedContract(Contract):
    """A0: the sidecar, the interfaces, the hooks and the fixtures are there, and the route answers through them."""

    def test_the_fixture_is_a_valid_sidecar_example_and_the_route_names_each_stub(self):
        self.assertEqual(self.target["schema"], "example-target/v1")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(build.main(["--plan", FIXTURE_ID, "--task", "fixed-security"]), 0)
        [p] = json.loads(out.getvalue())
        self.assertEqual((p["route"], p["task"]), ("target", "fixed-security"))
        if not p["executable"]:
            self.assertIn("unsupported: task-plan", p["notExecuted"])
        with self.assertRaises(route.UnknownTask):
            route.plan(self.folder, self.example, self.target, "no-such-task")

    def test_the_numbers_are_reserved(self):
        readme = (HERE.parent / "README.md").read_text()
        self.assertIn("Numbers 280–329 are reserved", readme)

    def test_constructed_and_handwritten_examples_keep_their_route(self):
        for folder in sorted(HERE.parent.glob("[0-9][0-9][0-9]-*")):
            example = json.loads((folder / "example.json").read_text())
            p = build.plan(example) if example["origin"] == "constructed" and not example.get("target") else None
            if p is not None:
                self.assertNotIn("route", p, folder.name)
            elif not example.get("target"):
                self.assertIn("its report is its README.md", build.not_executable(example), folder.name)


class A1OfflinePlanning(Contract):
    """A1: planning (workflow's W1) runs with no network, process or write, and resolves each task as the sidecar
    states it; a native task never requires JBMC."""

    def test_every_task_plans_offline_as_the_sidecar_states_it(self):
        before = tree(self.folder)
        for t in self.target["tasks"]:
            with offline():
                value = workflow.plan_task(self.folder, self.example, self.target, t["id"])
            plan = self.reach(value, "task-plan", WORKFLOW)
            self.assertIsInstance(plan, interfaces.TaskPlan)
            self.assertEqual((plan.example, plan.task, plan.kind, plan.relation, plan.target),
                             (FIXTURE_ID, t["id"], t["kind"], t["relation"], t["target"]))
            self.assertEqual(plan.revisions, self.revisions_of(t))
            self.assertEqual((plan.engine, plan.gaps, plan.expected), (t.get("engine"), t.get("gaps"), t.get("expected")))
            self.assertEqual(plan.prerequisites, tuple(t.get("requires", [])))
            self.assertEqual(Path(plan.folder).resolve(), self.folder.resolve())
            self.assertEqual([a["revision"] for a in plan.artifacts], list(plan.revisions))
            self.assertFalse(plan.network, "a fixture task needs no acquisition")
            if plan.engine == "native":
                self.assertNotIn("jbmc", plan.tools["required"] + plan.tools["optional"])
            if t.get("allowedChange"):
                self.assertIn(t["allowedChange"], json.dumps(plan.claim))
        self.assertEqual(tree(self.folder), before, "planning wrote into the example's folder")

    def test_the_handoff_reads_offline_and_keeps_observed_and_predicted_gaps_apart(self):
        before = tree(self.folder)
        with offline():
            value = workflow.handoff(self.folder, self.example, self.target, "regex-probe")
        packet = self.reach(value, "handoff", WORKFLOW)
        self.assertEqual(tree(self.folder), before, "the handoff wrote into the example's folder")
        self.assertTrue({"inputs", "commands", "receipts", "next", "gaps"} <= set(packet), sorted(packet))
        observed = [g for g in packet["gaps"] if g.get("observed")]
        self.assertTrue(any(g["kind"] == "java-semantics" for g in observed))
        self.assertFalse(any(g.get("observed") is None for g in packet["gaps"]), "every gap says whether it was observed")


class A2PreparationIntegrity(Contract):
    """A2: preparation (runtime's R1, R2) records the original's identity, its classpath in order and its JDK, is
    reproducible, follows the bytes, and refuses a shadowed target class."""

    def prepare(self, revision, folder=None, workdir="prepare"):
        plan = self.fixture_plan("fixed-security")
        if folder is not None:
            plan = dataclasses.replace(plan, folder=str(folder))
        plan = dataclasses.replace(plan, revisions=(revision,), artifacts=tuple(
            {**a, "revision": revision, "fixture": f"gate/{revision}"} for a in plan.artifacts))
        return self.reach(runtime.prepare(plan, revision, self.work / workdir / revision), "prepare", RUNTIME)

    def test_a_fixture_revision_is_prepared_with_its_identities(self):
        prepared = self.prepare("after")
        self.assertIsInstance(prepared, interfaces.PreparedTarget)
        self.assertEqual((prepared.stage, prepared.revision), ("artifacts-ready", "after"))
        originals = [a for a in prepared.artifacts if a.role == "original"]
        self.assertEqual([a.sha256 for a in originals], [self.manifest["jars"]["after"]["sha256"]],
                         "the fixture route builds with build_fixtures.py, so the original is its after.jar")
        self.assertTrue(any(a.role == "adapter" for a in prepared.artifacts))
        self.assertTrue(prepared.classpath, "the classpath is recorded, in order")
        self.assertIn("version", prepared.toolchain.get("jdk", {}))
        again = self.prepare("after", workdir="again")
        self.assertEqual(sorted((a.role, a.sha256) for a in again.artifacts), sorted((a.role, a.sha256) for a in prepared.artifacts))

    def test_the_identity_follows_the_bytes(self):
        changed = Path(self.dir.name) / "changed"
        shutil.copytree(self.folder, changed)
        source = changed / "gate/after/fixture/Gate.java"
        source.write_text(source.read_text().replace("DENIED + 32", "DENIED + 33"))
        prepared = self.prepare("after", folder=changed, workdir="changed")
        original = [a.sha256 for a in prepared.artifacts if a.role == "original"]
        self.assertNotEqual(original, [self.manifest["jars"]["after"]["sha256"]], "stale bytes kept their old identity")

    def test_an_adapter_that_shadows_the_target_class_is_refused(self):
        shadowed = Path(self.dir.name) / "shadowed"
        shutil.copytree(self.folder, shadowed)
        (shadowed / "gate/adapter/fixture/Gate.java").write_text(
            "package fixture;\npublic final class Gate { public static boolean allowed(int code) { return false; } }\n")
        prepared = self.prepare("after", folder=shadowed, workdir="shadowed")
        self.assertEqual(prepared.stage, "failed", "a classpath on which the adapter shadows fixture.Gate was accepted")
        self.assertTrue(prepared.failedStage and prepared.diagnostic)


class A3A4FixtureReplay(Contract):
    """A3 and A4 on the fixture's revisions (runtime's R4): each revision's driver in its own JVM, on each JDK the
    sidecar names; the independent oracle sees the vulnerable violation, the fix's response on the same trigger,
    retained legitimate behaviour, and the mutant failing the control the fix passes."""

    def controls(self, task_id):
        plan = self.fixture_plan(task_id)
        prepared = {}
        for revision in plan.revisions:
            r = self.reach(runtime.prepare(plan, revision, self.work / "prepare" / revision), "prepare", RUNTIME)
            self.assertEqual(r.stage, "artifacts-ready")
            prepared[revision] = r
        records = self.reach(runtime.run_controls(plan, prepared, self.work / "controls"), "run-controls", RUNTIME)
        return plan, records

    def problems_by_revision(self, records):
        o = oracle()
        out = {}
        for r in records:
            self.assertIsInstance(r, interfaces.ExecutionRecord)
            self.assertEqual((r.kind, r.status, r.exitCode), ("jvm-control", "exited", 0), r)
            self.assertIsNotNone(r.observations, "a complete control has structured observations")
            lines = [json.dumps(o_) for o_ in r.observations]
            out.setdefault(r.revision, set()).add(tuple(code for code, _ in o.check(lines)))
        return out

    def test_a3_the_vulnerable_violation_and_the_fix_on_the_same_trigger(self):
        plan, records = self.controls("replay")
        jdks = {r.identities.get("jdk") for r in records}
        self.assertEqual(len(jdks), 2, "the controls run on JDK 21 and 25, as two identities")
        self.assertEqual(self.problems_by_revision(records), {"before": {(97,)}, "after": {()}})

    def test_a4_the_mutant_fails_the_control_the_fix_passes(self):
        plan, records = self.controls("mutant-replay")
        self.assertEqual(self.problems_by_revision(records), {"after": {()}, "mutant": {(65,)}})


class A5FixtureCalibration(Contract):
    """A5 on the fixture (runtime's R3, workflow's W2): the tool's own checker, strict, on the prepared fixture gives
    the authored conclusion through the whole route; the capability probe is refused by name, never established."""

    def setUp(self):
        super().setUp()
        if jvmcontract() is None:
            self.skipTest("no built jvmcontract (lib/target/release/jvmcontract or JVMCONTRACT)")

    def attempt(self, task_id):
        value = route.run(self.folder, self.example, self.target, task_id, self.work / task_id)
        if isinstance(value, Unsupported):
            owner = WORKFLOW if value.interface in ("task-plan", "ingest") else RUNTIME
            return self.reach(value, value.interface, owner)
        return value

    def test_the_fix_is_established_and_the_vulnerable_revision_and_mutant_refuted(self):
        for task_id, expected in (("fixed-security", "established"), ("vulnerable-security", "refuted"),
                                  ("mutant-security", "refuted"), ("preservation", "established")):
            receipt = self.attempt(task_id)
            self.assertEqual((receipt.status, receipt.execution), (expected, "completed"), task_id)
            self.stored(self.folder, receipt)

    def test_the_capability_probe_is_refused_by_name(self):
        receipt = self.attempt("regex-probe")
        self.assertNotIn(receipt.status, ("established", "refuted"), "a strict proof through java.util.regex got a verdict")
        document = json.loads((self.folder / receipt.path).read_text())
        self.assertIn("java.util.regex", json.dumps(document))


class A6ReceiptIntegrity(Contract):
    """A6 (workflow's W2): one format-2 receipt per task and attempt, earlier attempts kept; execution, conclusion,
    expectation, scope and replay stay apart; a kill, malformed output, an exit code alone and a one-sided replay
    never become a result."""

    def ingest(self, task_id, records, prepared_revisions=None):
        plan = self.fixture_plan(task_id)
        prepared = {r: self.fixture_prepared(r, task_id) for r in (prepared_revisions or plan.revisions)}
        out = self.folder / plan.outputs["receipts"]
        return self.reach(workflow.ingest(plan, prepared, records, out), "ingest", WORKFLOW)

    def test_attempts_and_tasks_keep_distinct_receipts(self):
        first = self.ingest("replay", self.recorded())
        second = self.ingest("replay", self.recorded())
        other = self.ingest("mutant-replay", self.recorded(("after", "mutant")))
        for r in (first, second, other):
            self.assertIsInstance(r, interfaces.Receipt)
        self.assertNotEqual(first.path, second.path)
        self.assertEqual(first.claim, second.claim, "a second attempt at the same claim keeps its claim id")
        self.assertNotEqual(first.attempt, second.attempt)
        self.assertNotEqual(first.claim, other.claim)
        docs = [self.stored(self.folder, r) for r in (first, second, other)]  # the earlier attempt is still there
        self.assertEqual(docs[0]["claim"]["target"]["task"], "replay")
        self.assertEqual(set(docs[0]["claim"]["target"]["revisions"]), {"before", "after"})
        self.assertEqual(docs[0]["claim"]["inputs"]["dependencies"], "pinned in target.dependencies")

    def test_a_kill_malformed_output_and_a_one_sided_replay_are_not_results(self):
        for name, records in (("killed-control", self.recorded(("before",)) + self.bad("killed-control")),
                              ("malformed-control", self.recorded(("before",)) + self.bad("malformed-control")),
                              ("one-sided-replay", self.bad("one-sided-replay"))):
            value = workflow.ingest(self.fixture_plan("replay"), {r: self.fixture_prepared(r) for r in ("before", "after")},
                                    records, self.folder / "receipts" / name)
            if isinstance(value, Unsupported):
                if STUB in value.reason:
                    self.reach(value, "ingest", WORKFLOW)
                continue  # refused outright: not a result
            self.assertNotEqual(value.execution, "completed", name)
            self.assertNotIn(value.status, ("established", "refuted"), name)

    def test_an_exit_code_alone_is_no_violation(self):
        value = workflow.ingest(self.fixture_plan("vulnerable-security"), {"before": self.fixture_prepared("before", "vulnerable-security")},
                                self.bad("exit-one-verifier"), self.folder / "receipts" / "exit-one")
        if isinstance(value, Unsupported):
            if STUB in value.reason:
                self.reach(value, "ingest", WORKFLOW)
            return
        self.assertNotEqual(value.status, "refuted", "an exit code of 1 with no witness was read as a violation")


class A7AgentContinuation(Contract):
    """A7 on the fixture (workflow's W3): the handoff of an observed blocker carries what an agent needs to reproduce
    it from the packet's referenced inputs alone: each input hashed, the exact commands, one next action, and the gap
    packet. Phase 5 runs it with a fresh agent on a real packet."""

    def test_the_regex_probe_handoff_reproduces_from_its_inputs(self):
        packet = self.reach(workflow.handoff(self.folder, self.example, self.target, "regex-probe"), "handoff", WORKFLOW)
        self.assertTrue(packet["inputs"], "the packet names its inputs")
        for item in packet["inputs"]:
            self.assertRegex(item.get("sha256", ""), r"^[0-9a-f]{64}$", item)
        self.assertTrue(packet["commands"] and all(isinstance(c, (str, list)) for c in packet["commands"]))
        self.assertIsInstance(packet["next"], str)
        self.assertIn("--task", packet["next"])
        gap = next(g for g in packet["gaps"] if g["kind"] == "java-semantics")
        self.assertTrue(gap["observed"])
        self.assertIn("records/regex-gate-gaps.json", json.dumps(gap))


if __name__ == "__main__":
    unittest.main()

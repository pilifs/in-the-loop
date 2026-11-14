#!/usr/bin/env python3
"""Tests of workflow.py, owned by the workflow stream with it: task planning (W1) on a copy of Phase 0's fixture and on
sidecars changed from it. ingest() and handoff() are still Phase 0's stubs, which fail closed with the named
Unsupported result; their tests are rewritten as each stub is replaced.

  python3 examples/tools/targets/test_workflow.py
"""

import contextlib
import copy
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
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from targets import interfaces, route, sidecar, workflow  # noqa: E402
from test_interfaces import plan  # noqa: E402

FIXTURES = HERE / "fixtures"
SHA = "0123456789abcdef0123456789abcdef01234567"
SHA2 = "89abcdef0123456789abcdef0123456789abcdef"


@contextlib.contextmanager
def offline():
    def refuse(*a, **k):
        raise AssertionError("planning opened a connection or started a process")
    with mock.patch.object(socket.socket, "connect", refuse), mock.patch.object(socket, "create_connection", refuse), \
            mock.patch.object(subprocess, "Popen", refuse), mock.patch.object(os, "system", refuse):
        yield


def tree(folder):
    return {p.relative_to(folder).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(Path(folder).rglob("*")) if p.is_file()}


class Fixture(unittest.TestCase):
    """A copy of the fixture's folder, its example.json and its checked sidecar."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.folder = Path(self.dir.name) / "999-fixture"
        shutil.copytree(FIXTURES, self.folder, ignore=shutil.ignore_patterns("__pycache__"))
        self.example = json.loads((self.folder / "example.json").read_text())
        self.target = sidecar.load(self.folder, self.example)

    def task(self, target, task_id):
        return next(t for t in target["tasks"] if t["id"] == task_id)

    def plan(self, task_id, target=None):
        target = target or self.target
        sidecar.check(target, self.folder)  # every sidecar here is one sidecar.py accepts
        return workflow.plan_task(self.folder, self.example, target, task_id)

    def planned(self, task_id, target=None):
        value = self.plan(task_id, target)
        self.assertIsInstance(value, interfaces.TaskPlan, getattr(value, "reason", value))
        return value

    def refused(self, task_id, target=None, stage=None, says=""):
        value = self.plan(task_id, target)
        self.assertTrue(interfaces.unsupported(value), f"{task_id} was planned")
        self.assertEqual((value.interface, value.owner), ("task-plan", interfaces.WORKFLOW))
        self.assertNotIn("Phase 0's stub", value.reason)
        if stage:
            self.assertEqual(value.stage, stage, value.reason)
        self.assertIn(says, value.reason)
        return value

    def changed(self, task_id=None, **fields):
        target = copy.deepcopy(self.target)
        if task_id:
            self.task(target, task_id).update(fields)
        return target

    def write_claim(self, name, **fields):
        claim = json.loads((self.folder / "claims/gate-security.json").read_text())
        claim.update(fields)
        claim = {k: v for k, v in claim.items() if v is not None}
        (self.folder / "claims" / name).write_text(json.dumps(claim))
        return f"claims/{name}"


class PlanningTest(Fixture):
    def test_every_fixture_task_plans_offline_without_writing(self):
        before = tree(self.folder)
        for t in self.target["tasks"]:
            with offline():
                p = self.planned(t["id"])
            self.assertEqual((p.example, p.task, p.kind, p.relation, p.target), ("999", t["id"], t["kind"], t["relation"], t["target"]))
            self.assertEqual((p.engine, p.gaps, p.expected), (t.get("engine"), t.get("gaps"), t.get("expected")))
            self.assertEqual(p.prerequisites, tuple(t.get("requires", [])))
            self.assertEqual([a["revision"] for a in p.artifacts], list(p.revisions))
            self.assertEqual({a["route"] for a in p.artifacts}, {"fixture"})
            self.assertFalse(p.network)
            self.assertEqual(p.outputs, {"receipts": f"receipts/{t['id']}"})
            self.assertEqual(Path(p.folder), self.folder.resolve())
            json.dumps(route.plan(self.folder, self.example, self.target, t["id"]))  # the --plan output is JSON
        self.assertEqual(tree(self.folder), before)

    def test_revisions_and_artifacts_follow_the_task(self):
        self.assertEqual(self.planned("fixed-security").revisions, ("after",))
        p = self.planned("preservation")
        self.assertEqual(p.revisions, ("before", "after"))
        self.assertEqual([a["fixture"] for a in p.artifacts], ["gate/before", "gate/after"])
        self.assertEqual(p.artifacts[0]["jdks"], ["21", "25"])
        self.assertEqual(p.artifacts[0]["adapters"], ["gate/adapter/fixture/adapter/GateAdapter.java"])
        self.assertTrue(set(p.artifacts[0]) <= set(interfaces.ARTIFACT_SOURCE) | {"parent", "published"})

    def test_the_claim_states_the_property_with_its_file_hashed(self):
        p = self.planned("fixed-security")
        c = p.claim
        self.assertEqual((c["file"], c["property"], c["claimKind"]), ("claims/gate-security.json", "gate-denies-both-cases", "property"))
        self.assertEqual(c["assert"], "!result || (code != 65 && code != 97)")
        self.assertIsNone(c["assume"], "the domain is every int")
        self.assertEqual(c["observations"], ["result", "exception"])
        self.assertRegex(c["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(self.planned("preservation").claim["allowedChange"], "code == 97")

    def test_default_bounds_are_resolved_and_marked(self):
        c = self.planned("fixed-security").claim
        self.assertEqual(c["bounds"], workflow.DEFAULT_BOUNDS)
        self.assertEqual(c["defaultBounds"], ["maxArrayLength", "unwind"])
        c = self.planned("fixed-security", self.changed("fixed-security", bounds={"unwind": 4})).claim
        self.assertEqual(c["bounds"], {"unwind": 4, "maxArrayLength": 8})
        self.assertEqual((c["explicitBounds"], c["defaultBounds"]), ({"unwind": 4}, ["maxArrayLength"]))
        self.assertEqual(self.planned("replay").claim["bounds"], {}, "a replay runs no verifier, and has no bounds")

    def test_one_property_on_several_revisions_shares_its_key(self):
        keys = {t: self.planned(t).claim["key"] for t in ("vulnerable-security", "fixed-security", "mutant-security")}
        self.assertEqual(len(set(keys.values())), 1, keys)
        others = {self.planned(t).claim["key"] for t in ("preservation", "regex-probe", "replay", "mutant-replay")}
        self.assertEqual(len(others), 4)
        self.assertNotIn(keys["fixed-security"], others)

    def test_the_key_follows_the_semantics_not_the_strategy(self):
        key = self.planned("fixed-security").claim["key"]
        same = {"engine": "auto", "notes": ["another note"]}
        self.assertEqual(self.planned("fixed-security", self.changed("fixed-security", **same)).claim["key"], key)
        for change in ({"gaps": "assume"}, {"bounds": {"unwind": 4}}, {"target": "fixture.Gate#allowed"},
                       {"relation": "diagnostic"}, {"claim": self.write_claim("narrower.json", assume="code >= 0")},
                       {"claim": self.write_claim("fewer.json", observations=["result"])},
                       {"claim": self.write_claim("weaker.json", **{"assert": "!result || code != 65"})}):
            self.assertNotEqual(self.planned("fixed-security", self.changed("fixed-security", **change)).claim["key"], key, change)
        key = self.planned("preservation").claim["key"]
        self.assertNotEqual(self.planned("preservation", self.changed("preservation", allowedChange="code == 97 || code == 98")).claim["key"], key)

    def test_a_replay_key_follows_its_controls(self):
        key = self.planned("replay").claim["key"]
        oracle = self.folder / "gate/oracle.py"
        oracle.write_text(oracle.read_text() + "\n# changed\n")
        self.assertNotEqual(self.planned("replay").claim["key"], key)

    def test_a_native_task_never_needs_jbmc(self):
        p = self.planned("fixed-security")
        self.assertIn("jvmcontract", p.tools["required"])
        self.assertNotIn("jbmc", p.tools["required"] + p.tools["optional"])
        self.assertIn("jbmc", self.planned("fixed-security", self.changed("fixed-security", engine="jbmc")).tools["required"])
        auto = self.planned("fixed-security", self.changed("fixed-security", engine="auto")).tools
        self.assertEqual(("jbmc" in auto["required"], "jbmc" in auto["optional"]), (False, True))
        replay = self.planned("replay").tools
        self.assertNotIn("jvmcontract", replay["required"])
        self.assertIn("python3", replay["required"], "the oracle is a Python file")

    def test_the_canonical_digest_is_build_pys(self):
        import build
        for value in ({"b": [1, "é"], "a": None}, [], "x"):
            self.assertEqual(workflow.canonical_digest(value), build.canonical_digest(value))


class RefusalTest(Fixture):
    def test_a_proof_task_names_its_engine_and_gap_mode(self):
        for missing in ("engine", "gaps"):
            target = self.changed()
            del self.task(target, "fixed-security")[missing]
            self.refused("fixed-security", target, stage="plan", says=missing)

    def test_a_prove_task_without_a_claim_file_is_not_frozen(self):
        target = self.changed()
        del self.task(target, "fixed-security")["claim"]
        self.refused("fixed-security", target, stage="claim", says="isn't frozen")
        target = self.changed()
        del self.task(target, "preservation")["claim"]
        p = self.planned("preservation", target)  # an equivalence's claim is its target, pair and allowed change
        self.assertIsNone(p.claim["file"])
        self.assertEqual(p.claim["observations"], ["result", "exception"])

    def test_a_claim_file_that_is_not_a_v1_claim_is_refused(self):
        for fields, says in (({"domain": "every int"}, "Additional properties"),
                             ({"schema": "example-target-claim/v2"}, "example-target-claim/v1"),
                             ({"assert": None}, "'assert' is a required property"),
                             ({"observations": []}, "observations"),
                             ({"models": ["models/missing.json"]}, "does not exist")):
            name = self.write_claim("bad.json", **fields)
            self.refused("fixed-security", self.changed("fixed-security", claim=name), stage="claim", says=says)
        (self.folder / "claims/bad.json").write_text("{not json")
        self.refused("fixed-security", self.changed("fixed-security", claim="claims/bad.json"), stage="claim", says="not JSON")
        self.refused("fixed-security", self.changed("fixed-security", claim="claims/none.json"), stage="claim", says="does not exist")

    def test_a_claim_of_the_wrong_kind_is_refused(self):
        self.refused("fixed-security", self.changed("fixed-security", claim="claims/gate-preservation.json"),
                     stage="claim", says="preservation claim")
        self.refused("preservation", self.changed("preservation", claim="claims/gate-security.json"), stage="claim",
                     says="property claim")
        self.refused("replay", self.changed("replay", claim="claims/gate-security.json"), stage="claim", says="concrete controls only")

    def test_a_claim_file_linked_out_of_the_folder_is_refused(self):
        outside = Path(self.dir.name) / "outside.json"
        shutil.copyfile(self.folder / "claims/gate-security.json", outside)
        (self.folder / "claims/linked.json").symlink_to(outside)
        value = workflow.plan_task(self.folder, self.example, self.changed("fixed-security", claim="claims/linked.json"),
                                   "fixed-security")
        self.assertTrue(interfaces.unsupported(value))
        self.assertIn("outside the example's folder", value.reason)

    def test_bounds_at_odds_with_the_claim_file_are_refused(self):
        name = self.write_claim("bounded.json", bounds={"unwind": 8})
        self.assertEqual(self.planned("fixed-security", self.changed("fixed-security", claim=name)).claim["bounds"]["unwind"], 8)
        self.assertEqual(self.planned("fixed-security", self.changed("fixed-security", claim=name, bounds={"unwind": 8, "maxArrayLength": 2}))
                         .claim["bounds"], {"unwind": 8, "maxArrayLength": 2})
        self.refused("fixed-security", self.changed("fixed-security", claim=name, bounds={"unwind": 4}), stage="claim", says="unwind")

    def test_a_replay_needs_an_oracle_and_a_driver(self):
        target = self.changed()
        target["controls"] = [c for c in target["controls"] if c["kind"] != "oracle"]
        self.refused("replay", target, stage="plan", says="oracle")

    def test_an_introduction_task_waits_for_ancestry_and_an_oracle(self):
        target = self.changed("preservation", relation="introduction")
        self.refused("preservation", target, says="introduction unknown")
        target["history"]["introduction"] = {"status": "candidate", "commit": SHA}
        self.refused("preservation", target, says="introduction candidate")
        target["history"]["introduction"] = {"status": "established", "commit": SHA, "evidence": "replayed"}
        self.assertEqual(self.planned("preservation", target).relation, "introduction")
        target["controls"] = [c for c in target["controls"] if c["kind"] != "oracle"]
        self.refused("preservation", target, says="0 oracle controls")


class RouteTest(Fixture):
    """The upstream routes, on a negative case built from the fixture's tasks: the sidecar says what preparation
    starts from; planning resolves it, offline, and asks for acquisition."""

    def negative(self, route_name, **prep):
        target = self.changed()
        target["identity"] = {"case": "c", "family": "f", "role": "negative"}
        target["history"]["revisions"] = {"before": {"commit": SHA, "parent": SHA2}, "after": {"commit": SHA2}}
        target["history"]["pairs"] = [{"name": "fix", "kind": "exact-fix", "before": "before", "after": "after"}]
        target["tasks"] = [t for t in target["tasks"] if t["id"] in ("vulnerable-security", "fixed-security", "preservation", "replay")]
        target["controls"] = [c for c in target["controls"] if c["kind"] != "mutation"]
        target["handoff"] = {}
        target["preparation"] = {"route": route_name, "jdks": ["21", "25"], **prep}
        return target

    def test_a_published_artifact_is_located_per_revision(self):
        url = "https://repo.maven.apache.org/maven2/org/example/gate/"
        target = self.negative("published-artifact", artifacts=[
            {"revision": "before", "coordinates": "org.example:gate:1.0.0", "url": url + "1.0.0/gate-1.0.0.jar"},
            {"revision": "after", "coordinates": "org.example:gate:1.0.1", "url": url + "1.0.1/gate-1.0.1.jar", "sha256": "a" * 64},
            {"revision": "after", "coordinates": "org.example:dep:2.0.0"}])
        with offline():
            p = self.planned("preservation", target)
        self.assertTrue(p.network)
        before, after = p.artifacts
        self.assertEqual((before["commit"], before["parent"], before["coordinates"]), (SHA, SHA2, "org.example:gate:1.0.0"))
        self.assertNotIn("sha256", before, "a published JAR's sha256 is recorded the first time it is fetched")
        self.assertNotIn("coordinates", after, "two artifacts for one revision are listed, never one picked")
        self.assertEqual([a["coordinates"] for a in after["published"]], ["org.example:gate:1.0.1", "org.example:dep:2.0.0"])
        target["preparation"]["artifacts"] = target["preparation"]["artifacts"][1:]
        self.refused("preservation", target, stage="prepare", says="revision before")

    def test_an_upstream_build_needs_its_build_and_tools(self):
        build_ = {"tool": "maven", "argv": ["mvn", "-q", "package"], "jdk": "17"}
        p = self.planned("fixed-security", self.negative("upstream-build", build=build_))
        self.assertEqual(p.artifacts[0]["build"], build_)
        self.assertTrue({"git", "maven", "java"} <= set(p.tools["required"]))
        self.assertTrue(p.network)
        wrapper = self.planned("fixed-security", self.negative("upstream-build", build={**build_, "tool": "gradle-wrapper"}))
        self.assertNotIn("gradle", wrapper.tools["required"])
        self.refused("fixed-security", self.negative("upstream-build"), stage="prepare", says="names no build")

    def test_a_catalogued_case_is_not_prepared(self):
        target = self.negative("published-artifact")
        del target["preparation"]
        self.refused("fixed-security", target, stage="prepare", says="catalogued")

    def test_the_route_shows_why_a_task_is_not_executable(self):
        target = self.changed()
        del self.task(target, "fixed-security")["claim"]
        p = route.plan(self.folder, self.example, target, "fixed-security")
        self.assertFalse(p["executable"])
        self.assertIn("unsupported: task-plan (example-targets-workflow): its claim isn't frozen", p["notExecuted"])
        p = route.plan(self.folder, self.example, self.target, "fixed-security")
        self.assertTrue(p["executable"])
        self.assertEqual(p["claim"]["property"], "gate-denies-both-cases")


class StubsFailClosedTest(unittest.TestCase):
    def check(self, value, interface, owner):
        self.assertTrue(interfaces.unsupported(value))
        self.assertEqual((value.interface, value.owner), (interface, owner))
        self.assertIn(owner, value.describe())

    def test_ingestion(self):
        self.check(workflow.ingest(plan(), {}, (), Path(".")), "ingest", interfaces.WORKFLOW)

    def test_handoff(self):
        self.check(workflow.handoff(Path("."), {}, {}, "t"), "handoff", interfaces.WORKFLOW)

    def test_the_projection_states_only_what_the_sidecar_says(self):
        target = {"identity": {"case": "c", "family": "f", "role": "negative"}, "tasks": [{"id": "t"}],
                  "handoff": {"blockers": [{"kind": "java-semantics", "observed": False, "summary": "regex"}]}}
        row = workflow.project(Path("."), {}, target)
        self.assertEqual((row["family"], row["role"], row["readiness"], row["gaps"], row["predictedGaps"]),
                         ("f", "negative", None, [], ["java-semantics"]))


if __name__ == "__main__":
    unittest.main()

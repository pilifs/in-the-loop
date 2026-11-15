#!/usr/bin/env python3
"""Tests of workflow.py, owned by the workflow stream with it: task planning and the readiness milestones (W1), on a
copy of Phase 0's fixture and on sidecars changed from it, and attempt ingestion (W2) on the fixture's JARs, its
recorded controls and constructed verifier outcomes, the handoff packet and gap inventory (W3) on the fixture and
copies of it, and the index projection that find.py reads (W4), through build.py's render_index() and find.py.

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


def workflow_discovery_hold():
    from targets import workflow_discovery
    return workflow_discovery.HOLD


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


class MutantTest(Fixture):
    """A constructed mutant on an upstream route: one patch from a revision, planned on the path a revision takes,
    with its own provenance (base, patch sha256), and never prepared as its base."""

    PATCH = "--- a/fixture/Gate.java\n+++ b/fixture/Gate.java\n@@ -1 +1 @@\n-        return code != 65 && code != 97;\n+        return code != 97;\n"

    def positive(self, route_name, **prep):
        (self.folder / "controls").mkdir(exist_ok=True)
        (self.folder / "controls/mutant.patch").write_text(self.PATCH)
        target = self.changed()
        target["identity"] = {"case": "c", "family": "f", "role": "positive"}
        target["history"]["revisions"] = {
            "before": {"commit": SHA}, "after": {"commit": SHA2, "parent": SHA},
            "mutant": {"mutant": {"base": "after", "patch": "controls/mutant.patch",
                                  "sha256": workflow.file_sha256(self.folder / "controls/mutant.patch"),
                                  "description": "drop the check of 65"}}}
        target["history"]["pairs"] = [{"name": "positive", "kind": "positive", "before": "before", "after": "after"},
                                      {"name": "mutation", "kind": "mutation", "before": "after", "after": "mutant"}]
        target["tasks"] = [t for t in target["tasks"] if t["id"] in ("fixed-security", "mutant-security", "mutant-replay")]
        for t in target["tasks"]:
            t.pop("requires", None)
        target["handoff"] = {}
        target["preparation"] = {"route": route_name, "jdks": ["21", "25"], **prep}
        return target

    BUILD = {"tool": "gradle-wrapper", "argv": ["./gradlew", "jar"], "jdk": "17"}

    def test_a_mutant_is_planned_from_its_base_and_its_patch(self):
        target = self.positive("upstream-build", build=self.BUILD)
        with offline():
            p = self.planned("mutant-security", target)
        (entry,) = p.artifacts
        self.assertNotIn("commit", entry, "a mutant is never prepared as its base")
        self.assertNotIn("fixture", entry)
        self.assertEqual(entry["mutant"]["base"], {"revision": "after", "commit": SHA2})
        self.assertEqual(entry["mutant"]["patch"]["path"], "controls/mutant.patch")
        self.assertEqual(entry["mutant"]["patch"]["sha256"], target["history"]["revisions"]["mutant"]["mutant"]["sha256"])
        self.assertEqual(entry["mutant"]["description"], "drop the check of 65")
        self.assertEqual(entry["build"], self.BUILD)
        self.assertIn("git", p.tools["required"])
        fixed = self.planned("fixed-security", target)
        self.assertEqual(p.claim["key"], fixed.claim["key"], "one property and domain; artifacts bind them apart")
        self.assertNotEqual(p.artifacts, fixed.artifacts)

    def test_the_mutation_pair_prepares_the_base_and_the_mutant(self):
        p = self.planned("mutant-replay", self.positive("upstream-build", build=self.BUILD))
        self.assertEqual(p.revisions, ("after", "mutant"))
        base, mutant = p.artifacts
        self.assertEqual(base["commit"], SHA2)
        self.assertEqual(mutant["mutant"]["base"]["commit"], SHA2)

    def test_a_published_base_gives_its_artifacts_and_the_mutant_is_built(self):
        url = "https://repo.maven.apache.org/maven2/org/example/gate/"
        target = self.positive("published-artifact", artifacts=[
            {"revision": "before", "coordinates": "org.example:gate:1.0.0", "url": url + "1.0.0/gate-1.0.0.jar"},
            {"revision": "after", "coordinates": "org.example:gate:1.0.1", "url": url + "1.0.1/gate-1.0.1.jar"}])
        p = self.planned("mutant-security", target)
        (entry,) = p.artifacts
        self.assertNotIn("coordinates", entry, "nothing publishes a mutant")
        self.assertEqual([a["coordinates"] for a in entry["mutant"]["base"]["published"]], ["org.example:gate:1.0.1"])
        self.assertTrue({"git", "javac"} <= set(p.tools["required"]))
        target["preparation"]["artifacts"] = target["preparation"]["artifacts"][:1]
        self.refused("mutant-security", target, stage="prepare", says="revision after")

    def test_a_changed_or_missing_patch_is_refused_before_preparation(self):
        target = self.positive("upstream-build", build=self.BUILD)
        (self.folder / "controls/mutant.patch").write_text(self.PATCH.replace("97", "98"))
        with offline():
            self.refused("mutant-security", target, stage="prepare", says="a changed mutant is a different control")
        (self.folder / "controls/mutant.patch").unlink()
        self.refused("mutant-security", target, stage="prepare", says="does not exist")
        self.planned("fixed-security", target)

    def test_a_mutant_of_a_fixture_takes_the_fixture_route(self):
        target = self.changed()
        (self.folder / "controls").mkdir(exist_ok=True)
        (self.folder / "controls/mutant.patch").write_text(self.PATCH)
        target["history"]["revisions"]["mutant"] = {"mutant": {
            "base": "after", "patch": "controls/mutant.patch",
            "sha256": workflow.file_sha256(self.folder / "controls/mutant.patch"), "description": "drop the check of 65"}}
        (entry,) = self.planned("mutant-security", target).artifacts
        self.assertEqual(entry["mutant"]["base"], {"revision": "after", "fixture": "gate/after"})
        target["preparation"]["route"] = "upstream-build"
        target["preparation"]["build"] = self.BUILD
        target["identity"]["role"] = "control"
        self.refused("mutant-security", target, stage="prepare", says="(the base of a mutant)")


class ReadinessTest(Fixture):
    """W1's readiness: independent milestones per task, from the sidecar, its files and the folder's receipts, and
    the summaries derived from them. Receipts here are written by hand in the shape ingestion leaves (a format-2
    result.json and plan.json beside it); W2's tests read readiness over receipts it publishes."""

    def record(self, task_id, attempt="1", execution="completed", expectation="yes", status=None, filed=None):
        plan = workflow.plan_task(self.folder, self.example, self.target, task_id)
        where = self.folder / "receipts" / (filed or task_id) / attempt
        where.mkdir(parents=True)
        document = {"format": 2, "claim": {"id": "0" * 16, "target": {
            "task": task_id, "dependencies": [{"revision": r, "position": 0, "role": "original", "sha256": "0" * 64}
                                              for r in plan.revisions]}},
            "attempt": {"id": attempt, "execution": {"status": execution, "exitCode": 0, "reason": None}},
            "conclusion": {"status": status, "expectation": expectation}}
        (where / "result.json").write_text(json.dumps(document))
        (where / "plan.json").write_text(json.dumps(workflow.plan_record(plan)))
        return where

    def readiness(self, target=None):
        with offline():
            return workflow.readiness(self.folder, self.example, target or self.target)

    def reached(self, value, task_id):
        return {k: v["reached"] for k, v in value["tasks"][task_id]["milestones"].items()}

    def test_without_receipts_every_task_is_partial_and_says_why(self):
        before = tree(self.folder)
        value = self.readiness()
        self.assertEqual(tree(self.folder), before, "readiness wrote into the example's folder")
        self.assertEqual(value["summary"], "partial")
        self.assertEqual({r["summary"] for r in value["tasks"].values()}, {"partial"})
        fixed = self.reached(value, "fixed-security")
        self.assertEqual(fixed, {"provenanceLocked": True, "artifactsPrepared": False, "oracleValidated": False,
                                 "claimFrozen": True, "capabilityProbed": False, "attemptRecorded": False})
        self.assertEqual(tuple(fixed), workflow.MILESTONES)
        # The recorded gap scan is an observed probe; a replay has no claim to freeze and no verifier to probe.
        self.assertTrue(self.reached(value, "regex-probe")["capabilityProbed"])
        replay = self.reached(value, "replay")
        self.assertEqual((replay["claimFrozen"], replay["capabilityProbed"]), (None, None))
        self.assertIn("no current validated replay", value["tasks"]["fixed-security"]["milestones"]["oracleValidated"]["evidence"])

    def test_replays_and_attempts_raise_the_milestones_and_a_capability_gap_blocks(self):
        self.record("replay")
        self.record("mutant-replay")
        value = self.readiness()
        self.assertEqual(value["tasks"]["replay"]["summary"], "scaffolded")
        self.assertEqual(value["tasks"]["fixed-security"]["summary"], "scaffolded", "not probed yet")
        self.assertEqual(value["tasks"]["regex-probe"]["summary"], "blocked")
        self.assertEqual(value["summary"], "blocked")
        self.record("fixed-security", status="established")
        value = self.readiness()
        fixed = value["tasks"]["fixed-security"]
        self.assertEqual(fixed["summary"], "executable")
        self.assertEqual(fixed["receipts"], ["receipts/fixed-security/1/result.json"])
        self.assertTrue(all(self.reached(value, "fixed-security").values()))
        # A refuted expectation is no milestone: readiness never reads the conclusion as a verdict.
        self.record("vulnerable-security", status="refuted", expectation="no")
        self.assertEqual(self.readiness()["tasks"]["vulnerable-security"]["summary"], "executable")

    def test_a_replay_that_didnt_complete_or_match_validates_nothing(self):
        self.record("replay", execution="timed-out", expectation="not-evaluable")
        self.record("replay", attempt="2", expectation="no")
        value = self.readiness()
        self.assertFalse(self.reached(value, "fixed-security")["oracleValidated"])
        self.assertTrue(self.reached(value, "fixed-security")["artifactsPrepared"])
        self.assertEqual(value["tasks"]["replay"]["summary"], "partial")
        self.assertEqual(len(value["tasks"]["replay"]["receipts"]), 2, "both attempts kept and listed")

    def test_a_changed_claim_adapter_or_patch_leaves_old_receipts_stale(self):
        self.record("replay")
        self.record("mutant-replay")
        self.record("fixed-security")
        self.assertEqual(self.readiness()["tasks"]["fixed-security"]["summary"], "executable")
        claim = self.folder / "claims/gate-security.json"
        claim.write_text(claim.read_text() + "\n")
        fixed = self.readiness()["tasks"]["fixed-security"]
        self.assertEqual(fixed["summary"], "scaffolded")
        self.assertIn("stale or unreadable: receipts/fixed-security/1/result.json",
                      fixed["milestones"]["attemptRecorded"]["evidence"])
        adapter = self.folder / self.target["preparation"]["adapters"][0]
        adapter.write_text(adapter.read_text() + "\n")
        value = self.readiness()
        self.assertFalse(self.reached(value, "fixed-security")["artifactsPrepared"])
        self.assertFalse(self.reached(value, "replay")["attemptRecorded"])

    def test_a_changed_mutant_patch_unlocks_its_provenance(self):
        target = copy.deepcopy(self.target)
        (self.folder / "controls").mkdir()
        (self.folder / "controls/mutant.patch").write_text("--- a\n+++ b\n")
        target["history"]["revisions"]["mutant"] = {"mutant": {
            "base": "after", "patch": "controls/mutant.patch", "sha256": "0" * 64, "description": "drop the check"}}
        value = self.readiness(target)
        mutant = value["tasks"]["mutant-security"]["milestones"]["provenanceLocked"]
        self.assertFalse(mutant["reached"])
        self.assertIn("a changed mutant is a different control", mutant["evidence"])
        self.assertTrue(self.reached(value, "fixed-security")["provenanceLocked"])

    def test_an_unreadable_or_misfiled_receipt_never_counts(self):
        self.record("replay", filed="mutant-replay")
        broken = self.folder / "receipts/replay/2"
        broken.mkdir(parents=True)
        (broken / "result.json").write_text("{")
        old = self.folder / "receipts/replay/3"
        old.mkdir(parents=True)
        (old / "result.json").write_text(json.dumps({"verdict": "verified"}))
        bare = self.record("replay", attempt="4")
        (bare / "plan.json").unlink()
        value = self.readiness()
        self.assertFalse(self.reached(value, "replay")["attemptRecorded"])
        self.assertFalse(self.reached(value, "replay")["artifactsPrepared"])
        problems = {u["path"]: u["problem"] for u in value["unreadable"]}
        self.assertEqual(len(problems), 4)
        self.assertIn("filed under 'mutant-replay'", problems["receipts/mutant-replay/1/result.json"])
        self.assertIn("not a format-2 receipt", problems["receipts/replay/3/result.json"])
        self.assertIn("no plan.json", problems["receipts/replay/4/result.json"])

    def test_predicted_build_and_provenance_blockers_never_block_a_proof(self):
        self.record("replay")
        self.record("mutant-replay")
        target = copy.deepcopy(self.target)
        target["handoff"]["blockers"][0]["observed"] = False
        regex = workflow.readiness(self.folder, self.example, target)["tasks"]["regex-probe"]
        self.assertEqual(regex["summary"], "scaffolded", "a predicted gap is a hypothesis until a probe reaches it")
        self.assertIn("predicted only", regex["milestones"]["capabilityProbed"]["evidence"])
        target["handoff"]["blockers"][0].update(observed=True, kind="build-or-dependency")
        self.assertEqual(workflow.readiness(self.folder, self.example, target)["tasks"]["regex-probe"]["summary"],
                         "partial", "a build blocker leaves the scaffold partial")
        target["handoff"]["blockers"][0].update(kind="java-semantics", packet="records/missing.json")
        regex = workflow.readiness(self.folder, self.example, target)["tasks"]["regex-probe"]
        self.assertEqual(regex["summary"], "scaffolded", "an observed gap whose packet is missing is not evidence")
        self.assertFalse(regex["blockers"][0]["packetPresent"])

    def test_researched_revisions_and_a_catalogued_case(self):
        target = copy.deepcopy(self.target)
        target["identity"]["sourceConfidence"] = "researched"
        value = self.readiness(target)
        self.assertEqual(value["summary"], "partial")
        self.assertIn("not checked against upstream",
                      value["tasks"]["fixed-security"]["milestones"]["provenanceLocked"]["evidence"])
        del target["preparation"]
        value = self.readiness(target)
        self.assertEqual(value["summary"], "catalogued")
        self.assertEqual({r["summary"] for r in value["tasks"].values()}, {"catalogued"})
        self.assertIn("catalogued", value["tasks"]["fixed-security"]["milestones"]["claimFrozen"]["evidence"])


_MANIFEST = []


def fixture_manifest():
    """build_fixtures.py's manifest of the fixture JARs (javac, a few seconds), built once per run."""
    if not _MANIFEST:
        sys.path.insert(0, str(FIXTURES))
        import atexit
        import build_fixtures
        directory = tempfile.mkdtemp(prefix="workflow-ingest-")
        atexit.register(shutil.rmtree, directory, True)
        _MANIFEST.append(build_fixtures.build(directory))
    return _MANIFEST[0]


def outcome(verdict, counterexample=None, output="jvmcontract prove: ...\n", **fields):
    """One property's outcome as `jvmcontract prove --json` prints it, reduced to what ingestion reads."""
    return {"verdict": verdict, "output": output, "assert": "!result || (code != 65 && code != 97)", "assume": None,
            "counterexample": counterexample, "domain": "code: int", "proof": fields.pop("proof", None),
            "problem": fields.pop("problem", None), "vacuous": fields.pop("vacuous", None), **fields}


class IngestTest(Fixture):
    """W2's ingestion: one format-2 receipt per task and attempt from the fixture's prepared JARs and its recorded
    controls (records/controls.json) or a constructed verifier outcome, checked by build.py's check_result()."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = fixture_manifest()

    def setUp(self):
        super().setUp()
        self.controls = json.loads((self.folder / "records/controls.json").read_text())["records"]

    def prepared(self, revision, task="replay", **changes):
        jars = self.manifest["jars"]
        fields = dict(example="999", task=task, revision=revision, commit=f"fixture:gate/{revision}", stage="artifacts-ready",
                      source={"fixture": f"gate/{revision}"},
                      artifacts=(interfaces.Artifact(f"{revision}.jar", jars[revision]["sha256"], "original"),
                                 interfaces.Artifact(f"adapter-{revision}.jar", jars[f"adapter-{revision}"]["sha256"], "adapter"),
                                 interfaces.Artifact("driver.jar", jars["driver"]["sha256"], "driver")),
                      classpath=("driver.jar", f"adapter-{revision}.jar", f"{revision}.jar"),
                      toolchain={"jdk": {"feature": "25", "version": self.manifest["java"]}})
        fields.update(changes)
        return interfaces.PreparedTarget(**fields)

    def recorded(self, revisions, change=None):
        """The recorded controls of these revisions as ExecutionRecords; `change(record dict)` edits each first."""
        names = {f.name for f in __import__("dataclasses").fields(interfaces.ExecutionRecord)}
        out = []
        for r in copy.deepcopy(self.controls):
            if r["revision"] in revisions:
                if change:
                    change(r)
                out.append(interfaces.ExecutionRecord(**{k: (tuple(v) if k in ("argv", "observations") and v is not None else v)
                                                         for k, v in r.items() if k in names}))
        return tuple(out)

    def verifier(self, outcomes, exit_code=1, status="exited", revision="before"):
        return interfaces.ExecutionRecord(
            kind="verifier", revision=revision, argv=("jvmcontract", "prove", "fixture.Gate#allowed", "--engine", "native",
                                                      "--gaps", "strict", "--json"),
            status=status, exitCode=exit_code, seconds=1.5, stdout="verifier/out", stderr="verifier/err",
            identities={"jvmcontract": "0" * 64, "jdk": self.manifest["java"]},
            observations=None if outcomes is None else tuple(outcomes))

    def ingest(self, task_id, records, prepared=None, plan=None):
        plan = plan or self.planned(task_id)
        prepared = prepared if prepared is not None else {r: self.prepared(r, task_id) for r in plan.revisions}
        return workflow.ingest(plan, prepared, records, self.folder / plan.outputs["receipts"])

    def receipt(self, value):
        import jsonschema
        import result_format
        self.assertIsInstance(value, interfaces.Receipt, getattr(value, "reason", value))
        document = json.loads((self.folder / value.path).read_text())
        schemas = HERE.parents[1] / "schema"
        jsonschema.validate(document, json.loads((schemas / "stored-result.schema.json").read_text()))
        jsonschema.validate(result_format.view(document), json.loads((schemas / "result.schema.json").read_text()))
        return document

    def refused(self, value, stage, says):
        self.assertTrue(interfaces.unsupported(value), f"published {value}")
        self.assertEqual((value.interface, value.owner, value.stage), ("ingest", interfaces.WORKFLOW, stage), value.reason)
        self.assertNotIn("Phase 0's stub", value.reason)
        self.assertIn(says, value.reason)

    def test_a_replay_is_bound_to_its_artifacts_and_reproduced(self):
        receipt = self.ingest("replay", self.recorded(("before", "after")))
        document = self.receipt(receipt)
        self.assertEqual((receipt.status, receipt.execution), (None, "completed"), "a replay decides no claim")
        self.assertEqual(receipt.path, f"receipts/replay/{receipt.attempt}/result.json")
        conclusion, evidence = document["conclusion"], document["evidence"]
        self.assertEqual((conclusion["status"], conclusion["expectation"]), (None, "yes"))
        self.assertEqual(evidence["replay"], {"by": "jvm", "reproduced": True})
        self.assertEqual([c["input"] for c in evidence["counterexamples"]], ["97", "97"], "before violates on JDK 21 and 25")
        target = document["claim"]["target"]
        from targets import workflow_ingest
        self.assertEqual(target["revisions"], {r: workflow_ingest.git_tree_id(self.folder / f"gate/{r}") for r in ("before", "after")})
        self.assertEqual([(d["revision"], d["position"], d["role"]) for d in target["dependencies"]],
                         [(r, i, role) for r in ("before", "after") for i, role in enumerate(("driver", "adapter", "original"))])
        self.assertEqual(len(target["jdks"]), 2)
        self.assertIn("gate/oracle.py", target["files"])
        self.assertIn("gate/adapter/fixture/adapter/GateAdapter.java", target["files"])
        self.assertEqual(document["claim"]["inputs"]["dependencies"], "pinned in target.dependencies")
        where = self.folder / receipt.path
        self.assertEqual(json.loads((where.parent / "plan.json").read_text())["key"], workflow.inputs_key(self.planned("replay")))
        self.assertEqual(sorted(a["path"] for a in document["bundle"]["artifacts"]),
                         ["records/execution.json", "records/streams.json", "records/summary.txt"])
        # Recorded controls name no attempt directory, so no stream is bundled, and streams.json says why for each
        # (test_receipt_streams.py has the runs that do).
        streams = json.loads((self.folder / receipt.path).parent.joinpath("records/streams.json").read_text())["streams"]
        self.assertEqual({(s["kept"], s["why"]) for s in streams}, {(None, workflow_ingest.NO_DIRECTORY)})
        self.assertEqual(len(streams), 2 * len(document["attempt"]["stages"]))

    def test_the_fixture_revisions_identity_is_its_git_tree(self):
        from targets import workflow_ingest
        repo = HERE.parents[2]
        try:
            git = subprocess.run(["git", "rev-parse", "HEAD:examples/tools/targets/fixtures/gate/before"], cwd=repo,
                                 capture_output=True, text=True, timeout=30)
        except OSError:
            self.skipTest("no git")
        if git.returncode != 0 or subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "fixtures/gate/before"],
                                                 cwd=HERE, timeout=30).returncode != 0:
            self.skipTest("the fixture isn't committed unchanged at HEAD")
        self.assertEqual(workflow_ingest.git_tree_id(FIXTURES / "gate/before"), git.stdout.strip())

    def test_attempts_are_kept_and_the_claim_follows_the_inputs(self):
        first = self.ingest("replay", self.recorded(("before", "after")))
        second = self.ingest("replay", self.recorded(("before", "after")))
        self.assertEqual(first.claim, second.claim, "another attempt at the same claim")
        self.assertNotEqual(first.path, second.path)
        self.receipt(first)
        self.assertNotEqual(self.ingest("mutant-replay", self.recorded(("after", "mutant"))).claim, first.claim)
        adapter = self.folder / "gate/adapter/fixture/adapter/GateAdapter.java"
        adapter.write_text(adapter.read_text() + "\n")
        self.assertNotEqual(self.ingest("replay", self.recorded(("before", "after"))).claim, first.claim, "a changed adapter")
        changed = self.prepared("after", artifacts=(interfaces.Artifact("after.jar", "1" * 64, "original"),
                                                    *self.prepared("after").artifacts[1:]))
        other = self.ingest("replay", self.recorded(("before", "after")), {"before": self.prepared("before"), "after": changed})
        self.assertNotEqual(other.claim, first.claim, "other bytes are another claim")
        self.assertEqual(other.execution, "invalid-output", "the controls ran on bytes other than the prepared ones")

    def test_a_kill_a_timeout_malformed_output_or_one_side_is_no_result(self):
        def edit(field, value, revision="after"):
            return lambda r: r.update({field: value} if r["revision"] == revision else {})
        cases = {"killed": (self.recorded(("before", "after"), edit("status", "killed")), "killed"),
                 "timed out": (self.recorded(("before", "after"), edit("status", "timed-out")), "timed-out"),
                 "malformed": (self.recorded(("before", "after"), edit("observations", None)), "invalid-output"),
                 "exit 1": (self.recorded(("before", "after"), edit("exitCode", 1)), "tool-error"),
                 "incomplete": (self.recorded(("before", "after"), lambda r: r.update(observations=r["observations"][:-1])),
                                "invalid-output"),
                 "one side": (self.recorded(("before",)), "invalid-output"),
                 "one JDK": (self.recorded(("before", "after"), lambda r: r.update(
                     identities={**r["identities"], "jdk": 'openjdk version "25.0.5" 2026-10-20 LTS'})), "invalid-output")}
        for name, (records, execution) in cases.items():
            with self.subTest(name):
                receipt = self.ingest("replay", records)
                document = self.receipt(receipt)
                self.assertEqual((receipt.execution, receipt.status), (execution, None))
                self.assertEqual(document["conclusion"]["expectation"], "not-evaluable")
                self.assertFalse(document["evidence"]["replay"]["reproduced"], "an incomplete replay is never reproduced")
                self.assertTrue(document["attempt"]["execution"]["reason"])

    def test_a_replay_that_shows_the_wrong_outcome_completes_and_does_not_match(self):
        def flip(r):
            if r["revision"] == "after":
                for o in r["observations"]:
                    if o["input"] == 97:
                        o["value"] = True
        receipt = self.ingest("replay", self.recorded(("before", "after"), flip))
        document = self.receipt(receipt)
        self.assertEqual((receipt.execution, document["conclusion"]["expectation"]), ("completed", "no"))
        self.assertFalse(document["evidence"]["replay"]["reproduced"])

    def test_what_cant_be_bound_is_refused_and_nothing_is_published(self):
        plan = self.planned("replay")
        records = self.recorded(("before", "after"))
        self.refused(self.ingest("replay", records, {"before": self.prepared("before")}), "bind", "after was not prepared")
        failed = self.prepared("after", stage="failed", failedStage="build", diagnostic="javac: error")
        self.refused(self.ingest("replay", records, {"before": self.prepared("before"), "after": failed}), "prepare",
                     "a preparation failure")
        self.refused(self.ingest("replay", records, {"before": self.prepared("before"),
                                                     "after": self.prepared("after", commit="fixture:gate/mutant")}),
                     "bind", "fixture:gate/mutant")
        self.refused(self.ingest("replay", records + (self.verifier(None),)), "records", "runs no verifier")
        oracle = self.folder / "gate/oracle.py"
        oracle.write_text(oracle.read_text() + "\n")
        self.refused(self.ingest("replay", records, plan=plan), "oracle", "changed since the task was planned")
        self.refused(self.ingest("vulnerable-security", records), "records", "0 verifier records")
        self.assertFalse((self.folder / "receipts").exists() and any((self.folder / "receipts").rglob("result.json")))

    def test_an_exit_code_alone_is_no_violation_and_a_witness_is_needed(self):
        witness = {"input": "code=97", "outcome": "returned true"}
        cases = {"exit 1, no outcome": (None, 1, "invalid-output", None),
                 "exit 1, unreadable": ([{"verdict": "violation"}], 1, "invalid-output", None),
                 "a violation with no witness": ([outcome("violation")], 1, "invalid-output", None),
                 "exit 0 for a violation": ([outcome("violation", witness)], 0, "invalid-output", None),
                 "a violation with its witness": ([outcome("violation", witness)], 1, "completed", "refuted")}
        for name, (outcomes, code, execution, status) in cases.items():
            with self.subTest(name):
                receipt = self.ingest("vulnerable-security", (self.verifier(outcomes, code),))
                document = self.receipt(receipt)
                self.assertEqual((receipt.execution, receipt.status), (execution, status))
                self.assertEqual(document["conclusion"]["expectation"], "yes" if status else "not-evaluable")
        killed = self.ingest("vulnerable-security", (self.verifier(None, None, "killed"),))
        self.assertEqual((killed.execution, killed.status), ("killed", None))
        timed_out = self.ingest("vulnerable-security", (self.verifier(None, None, "timed-out"),))
        self.assertEqual((timed_out.execution, timed_out.status), ("timed-out", None))

    def test_one_property_on_two_revisions_gets_two_claims_and_its_own_verdicts(self):
        fixed = self.ingest("fixed-security", (self.verifier([outcome("verified", proof="the own checker, with unwinding assertions")], 0, revision="after"),))
        vulnerable = self.ingest("vulnerable-security", (self.verifier([outcome("verified")], 0),))
        self.assertNotEqual(fixed.claim, vulnerable.claim, "one property, two artifact-bound identities")
        import dataclasses
        strategy = dataclasses.replace(self.planned("fixed-security"), engine="auto")
        again = self.ingest("fixed-security", (self.verifier([outcome("verified")], 0, revision="after"),), plan=strategy)
        self.assertEqual(again.claim, fixed.claim, "another engine is another attempt at the same claim")
        self.assertEqual((fixed.status, self.receipt(fixed)["conclusion"]["expectation"]), ("established", "yes"))
        document = self.receipt(vulnerable)
        self.assertEqual((vulnerable.status, document["conclusion"]["expectation"]), ("established", "no"),
                         "an unexpected verdict is kept, never rewritten")
        self.assertEqual(self.receipt(fixed)["attempt"]["exploration"]["complete"], True)
        refusal = self.ingest("regex-probe", (self.verifier([outcome("unverifiable", problem="java.util.regex.Pattern#compile is outside the checker")], 1, revision="after"),))
        self.assertEqual((refusal.execution, refusal.status), ("completed", "unresolved"))
        self.assertEqual(self.receipt(refusal)["conclusion"]["expectation"], "yes", "a refusal is unresolved, as expected")
        vacuous = self.ingest("fixed-security", (self.verifier([outcome("verified", vacuous="no input reaches the call")], 0, revision="after"),))
        self.assertEqual(self.receipt(vacuous)["conclusion"]["expectation"], "no", "a vacuous proof isn't the expected one")

    def witness(self, code=97, classes="after", previous=False, replay=None):
        """A refuted property's counterexample as jvmcontract's --json gives it (105's job, reduced to the fixture)."""
        def call(side):
            return {"class": "fixture.Gate", "class_file": "fixture/Gate.class", "classes": side, "method": "allowed",
                    "descriptor": "(I)Z", "static": True,
                    "arguments": [{"name": "code", "type": "int", "value": code, "from": "code"}]}
        c = {"input": f"allowed(code={code})", "outcome": "returned true", "shrink_runs": 0,
             "inputs": [{"name": "code", "type": "int", "value": code}], "call": call(classes)}
        if previous:
            c["previous_call"] = call("before")
        return c

    def test_a_property_checks_receipt_says_how_its_witness_was_replayed(self):
        """The user's review item 6 (2026-11-15), A7's first observation: a refuted property check's receipt gave
        `evidence.replay: null`, its replay stated only in the proof text, though each property's own was kept."""
        interpreter = {"by": "interpreter", "reproduced": True}
        refuted = self.receipt(self.ingest("vulnerable-security", (self.verifier(
            [outcome("violation", self.witness(), replay=interpreter)], 1),)))
        self.assertEqual(refuted["conclusion"]["obligations"][0]["evidence"]["replay"], interpreter)
        self.assertEqual(refuted["evidence"]["replay"], interpreter, "the headline property's replay")
        two = self.receipt(self.ingest("vulnerable-security", (self.verifier(
            [outcome("violation", self.witness(), replay=interpreter),
             outcome("violation", self.witness(65), replay={"by": "interpreter", "reproduced": False})], 1),)))
        self.assertEqual(two["evidence"]["replay"], {"by": "interpreter", "reproduced": False},
                         "reproduced only when every refuted property's witness was")
        unstated = self.receipt(self.ingest("vulnerable-security", (self.verifier(
            [outcome("violation", self.witness(), replay=interpreter), outcome("violation", self.witness(65))], 1),)))
        self.assertIsNone(unstated["evidence"]["replay"], "a refuted property with no replay leaves it unstated")
        holds = self.receipt(self.ingest("fixed-security", (self.verifier([outcome("verified")], 0, revision="after"),)))
        self.assertIsNone(holds["evidence"]["replay"], "no witness, nothing replayed")

    def test_a_witness_names_the_revision_its_classes_are(self):
        """Item 6, A7's second observation: jvmcontract's prove runs on one set of classes and calls it `after`, so a
        one-revision task's witness named `after` whatever its revision (105's `before`, 287's `fixed-release`)."""
        vulnerable = self.receipt(self.ingest("vulnerable-security", (self.verifier(
            [outcome("violation", self.witness())], 1),)))
        call = vulnerable["evidence"]["counterexamples"][0]["witness"]["call"]
        self.assertEqual((call["classes"], call["revision"]), ("after", "before"), "the tool's label, and the revision")
        obligation = vulnerable["conclusion"]["obligations"][0]["evidence"]["counterexample"]["witness"]["call"]
        self.assertEqual(obligation["revision"], "before")
        mutant = self.receipt(self.ingest("mutant-security", (self.verifier(
            [outcome("violation", self.witness(65))], 1, revision="mutant"),)))
        self.assertEqual(mutant["evidence"]["counterexamples"][0]["witness"]["call"]["revision"], "mutant")
        pair = self.receipt(self.ingest("preservation", (self.verifier([{
            "verdict": "violation", "output": "jvmcontract equivalence: ...\n", "domain": "code: int",
            "counterexample": {**self.witness(previous=True), "before": "returned false", "after": "returned true"},
            "replay": {"by": "interpreter", "reproduced": True}}], 1, revision=None),)))
        witness = pair["evidence"]["counterexamples"][0]["witness"]
        self.assertEqual((witness["call"]["revision"], witness["previousCall"]["revision"]), ("after", "before"),
                         "a pair's sides, by the plan's revisions")

    def test_a_receipt_records_the_frozen_claim_key_beside_its_claim_id(self):
        """Item 6, A7's third observation: the receipt's `claim.id` is the executed claim's, bound to the prepared
        bytes, not the frozen source-level key a packet, plan or refusal names, and nothing said which one a reader
        compares. claim.target.claimKey is the frozen key; the schema says what each is compared for."""
        fixed = self.receipt(self.ingest("fixed-security", (self.verifier([outcome("verified")], 0, revision="after"),)))
        vulnerable = self.receipt(self.ingest("vulnerable-security", (self.verifier(
            [outcome("violation", self.witness())], 1),)))
        key = self.planned("fixed-security").claim["key"]
        self.assertEqual(self.planned("vulnerable-security").claim["key"], key, "one property, one frozen key")
        for document in (fixed, vulnerable):
            self.assertEqual(document["claim"]["target"]["claimKey"], key)
            self.assertEqual(document["claim"]["statement"]["claim"]["key"], key)
        self.assertNotEqual(fixed["claim"]["id"], vulnerable["claim"]["id"], "two artifact-bound identities")
        schema = json.loads((HERE.parents[1] / "schema" / "result.schema.json").read_text())["properties"]["claim"]
        said = schema["properties"]["target"]["properties"]["claimKey"]["description"]
        for words in ("frozen", "claim.id", "compare"):
            self.assertIn(words, said)
        self.assertIn("claimKey", schema["properties"]["id"]["description"])

    def test_a_target_receipt_runs_no_module_tests_and_has_no_patch_excerpt(self):
        """Phase 5's request 8: a target task's attempt runs no module tests, so its receipt says none (null) rather
        than a test run that didn't pass; one revision has no `before`. Only a target claim may leave them null."""
        import jsonschema
        import result_format
        replay = self.receipt(self.ingest("replay", self.recorded(("before", "after"))))
        flat = result_format.view(replay)
        self.assertIsNone(flat["existingTests"], "no module test ran, and none failed")
        self.assertEqual((flat["before"]["file"], flat["after"]["file"]), ("target.json", "target.json"),
                         "a pair's two revisions, where target.json names them")
        self.assertNotEqual(flat["before"]["startLine"], flat["after"]["startLine"])
        single = result_format.view(self.receipt(self.ingest(
            "fixed-security", (self.verifier([outcome("verified")], 0, revision="after"),))))
        self.assertIsNone(single["before"], "a task on one revision has no before")
        self.assertEqual(single["after"]["file"], "target.json")
        schema = json.loads((HERE.parents[1] / "schema" / "result.schema.json").read_text())
        description = schema["properties"]["claim"]["properties"]["target"]["properties"]["revisions"]["description"]
        self.assertIn("git tree id", description)
        self.assertIn("mutant", description)
        constructed = copy.deepcopy(flat)
        del constructed["claim"]["target"]
        constructed["claim"]["inputs"]["patch"] = "0" * 64
        constructed.update(existingTests={"task": "gradle test", "passed": True, "failures": []},
                           before=flat["after"], after=flat["after"])
        jsonschema.validate(constructed, schema)
        for field in ("existingTests", "before", "after"):
            with self.subTest(field):
                with self.assertRaises(jsonschema.ValidationError, msg=f"{field}: null only with claim.target"):
                    jsonschema.validate({**constructed, field: None}, schema)
        no_claim = {k: v for k, v in constructed.items() if k not in ("claim", "attempt", "conclusion", "bundle")}
        with self.assertRaises(jsonschema.ValidationError, msg="a format-1 result has no claim, so no null"):
            jsonschema.validate({**no_claim, "existingTests": None}, schema)

    def test_readiness_reads_the_receipts_ingestion_publishes(self):
        def readiness():
            with offline():
                return workflow.readiness(self.folder, self.example, self.target)
        self.ingest("replay", self.recorded(("before", "after")))
        self.ingest("mutant-replay", self.recorded(("after", "mutant")))
        value = readiness()
        fixed = value["tasks"]["fixed-security"]["milestones"]
        self.assertTrue(fixed["artifactsPrepared"]["reached"] and fixed["oracleValidated"]["reached"], fixed)
        self.assertEqual(value["tasks"]["fixed-security"]["summary"], "scaffolded")
        self.assertEqual(value["tasks"]["regex-probe"]["summary"], "blocked")
        self.ingest("fixed-security", (self.verifier([outcome("verified")], 0, revision="after"),))
        value = readiness()
        self.assertEqual(value["tasks"]["fixed-security"]["summary"], "executable")
        self.assertEqual(value["unreadable"], [])
        adapter = self.folder / "gate/adapter/fixture/adapter/GateAdapter.java"
        adapter.write_text(adapter.read_text() + "\n")
        value = readiness()
        self.assertFalse(value["tasks"]["fixed-security"]["milestones"]["oracleValidated"]["reached"], "stale after a change")
        self.assertEqual(value["tasks"]["fixed-security"]["summary"], "partial")


class HandoffTest(Fixture):
    """W3's handoff: a task's packet, offline and read-only, from the sidecar, its files and the folder's receipts;
    an isolated copy of its referenced inputs resumes it; and the gap inventory across families."""

    prepared, recorded, verifier, ingest = IngestTest.prepared, IngestTest.recorded, IngestTest.verifier, IngestTest.ingest

    @classmethod
    def setUpClass(cls):
        cls.manifest = fixture_manifest()

    def setUp(self):
        super().setUp()
        self.controls = json.loads((self.folder / "records/controls.json").read_text())["records"]

    def handoff(self, task_id, target=None, folder=None):
        folder = folder or self.folder
        before = tree(folder)
        with offline():
            value = workflow.handoff(folder, self.example, target or self.target, task_id)
        self.assertEqual(tree(folder), before, "the handoff wrote into the example's folder")
        self.assertIsInstance(value, dict, getattr(value, "reason", value))
        return value

    def blocked(self, *blockers, target=None):
        target = copy.deepcopy(target or self.target)
        target["handoff"]["blockers"] += [dict(b) for b in blockers]
        return target

    def test_the_inputs_list_the_files_a_claim_cites(self):
        """Item 6, A7's fourth observation: 105's claim cites records/pow-gaps.json in an assumption's basis, and the
        handoff didn't list it, so an isolated session had a cited file with no sha256. A path the claim file names
        that is a file in the example's folder is an input; a repository path or a missing file is not."""
        claim = self.folder / "claims/gate-security.json"
        stated = json.loads(claim.read_text())
        stated["assumptions"] = [{"text": "allowed(int) has no loop.", "basis": "records/regex-gate-gaps.json lists "
                                  "the classes read; see also lib/README.md and records/missing.json."}]
        claim.write_text(json.dumps(stated, indent=2) + "\n")
        roles = {i["path"]: (i["role"], i["sha256"]) for i in self.handoff("fixed-security")["inputs"]}
        self.assertEqual(roles["records/regex-gate-gaps.json"],
                         ("cited by the claim", workflow.file_sha256(self.folder / "records/regex-gate-gaps.json")))
        self.assertEqual(roles["gate/oracle.py"][0], "control: oracle", "a cited control keeps its role")
        self.assertNotIn("lib/README.md", roles)
        self.assertNotIn("records/missing.json", roles)
        real = HERE.parents[1] / "105-commons-numbers-223-pow-of-minus-two-to-the-31"
        example = json.loads((real / "example.json").read_text())
        with offline():
            packet = workflow.handoff(real, example, sidecar.load(real, example), "fix-property-before")
        inputs = {i["path"]: i for i in packet["inputs"]}
        self.assertEqual(inputs["records/pow-gaps.json"]["sha256"], workflow.file_sha256(real / "records/pow-gaps.json"))

    def test_the_regex_probe_packet_carries_its_observed_gap_packet(self):
        from targets import workflow_handoff
        value = self.handoff("regex-probe")
        key = self.planned("regex-probe").claim["key"]
        for item in value["inputs"]:
            path = self.folder / item["path"]
            digest = workflow_handoff.tree_sha256(path) if path.is_dir() else workflow.file_sha256(path)
            self.assertEqual(item["sha256"], digest, item)
        roles = {i["path"]: i["role"] for i in value["inputs"]}
        self.assertEqual((roles["target.json"], roles["claims/regex-probe.json"], roles["records/regex-gate-gaps.json"],
                          roles["records/regex-gate-gaps.stdout"], roles["gate/after"]),
                         ("sidecar", "claim", "gap packet", "gap record (stdout)", "fixture sources"))
        self.assertEqual(value["commands"][0], "python3 examples/tools/build.py --plan 999 --task regex-probe")
        self.assertTrue(value["commands"][1].startswith("python3 verification/pipeline.py submit --example 999 "
                                                        "--task regex-probe --title "), value["commands"][1])
        self.assertEqual(value["next"], value["commands"][1], "a proof is queued, never run inline")
        self.assertIn("reproduce the observed java-semantics blocker", value["nextReason"])
        self.assertEqual((value["receipts"], value["prerequisites"], value["nextPrerequisite"]), ([], [], None))
        self.assertEqual(value["plan"]["claim"]["key"], key)
        self.assertTrue(any(key in r for r in value["rules"]))
        [gap] = value["gaps"]
        self.assertEqual((gap["kind"], gap["observed"], gap["class"]), ("java-semantics", True, "capability"))
        packet = gap["packet"]
        self.assertEqual((packet["file"], packet["present"], packet["task"], packet["claim"]["key"]),
                         ("records/regex-gate-gaps.json", True, "regex-probe", key))
        self.assertEqual(packet["command"][:2], ["jvmcontract", "gaps"])
        scan = json.loads((self.folder / "records/regex-gate-gaps.stdout").read_text())
        self.assertEqual([d["id"] for d in packet["diagnostic"]], [g["id"] for g in scan["gaps"]])
        self.assertIn("java.util.regex.Pattern.compile(java.lang.String)", [s["call"] for s in packet["semantics"]])
        self.assertNotIn("@jdk-", json.dumps([s["gap"] for s in packet["semantics"]]))
        self.assertEqual(packet["reproducer"]["revision"], "after")
        self.assertIn("fixture.RegexGate.<clinit>:8", packet["reproducer"]["callPath"])
        self.assertEqual(packet["module"]["likely"], ["lib/src/models.rs"])
        self.assertEqual(packet["closure"]["command"], value["next"])
        self.assertIn(key, packet["closure"]["check"])
        self.assertEqual(packet["needs"]["observations"], ["result", "exception"])
        self.assertEqual(packet["verifier"]["jvmcontract"], json.loads(
            (self.folder / "records/regex-gate-gaps.json").read_text())["record"]["identities"]["jvmcontract"])
        self.assertEqual(packet["missing"], ["verifier.commit"], "the record names the binary, not its commit")

    def test_a_verifier_record_that_names_its_lib_commit_completes_the_packets_verifier(self):
        """run_verifier's identities.commit and libTree (a pipeline job's own build) go to the packet's verifier, not
        its artifacts, and verifier.commit stops being missing; a null commit stays missing."""
        from targets import workflow_handoff
        folder = Path(self.dir.name) / "scan"
        folder.mkdir()
        identities = {"jvmcontract": "c" * 64, "commit": "b" * 40, "libTree": "a" * 40, "jdk": "25.0.5"}
        document = {"record": {"kind": "verifier", "argv": ["jvmcontract", "gaps"], "identities": identities}}
        scan = workflow_handoff.recorded_scan(folder / "record.json", document)
        self.assertEqual(scan["verifier"], {"jvmcontract": "c" * 64, "commit": "b" * 40, "libTree": "a" * 40})
        self.assertEqual(scan["artifacts"], {"jdk": "25.0.5"})
        unbuilt = copy.deepcopy(document)
        unbuilt["record"]["identities"].update(commit=None, libTree=None)
        scan = workflow_handoff.recorded_scan(folder / "record.json", unbuilt)
        self.assertEqual(scan["verifier"], {"jvmcontract": "c" * 64, "commit": None, "libTree": None})
        self.assertNotIn("libTree", scan.get("artifacts", {}))

    def test_an_isolated_copy_of_the_referenced_inputs_resumes_the_task(self):
        for task_id in ("regex-probe", "preservation"):
            value = self.handoff(task_id)
            copy_ = Path(self.dir.name) / f"isolated-{task_id}" / "999-fixture"
            for item in value["inputs"]:
                source, dest = self.folder / item["path"], copy_ / item["path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                (shutil.copytree if source.is_dir() else shutil.copy2)(source, dest)
            target = sidecar.load(copy_, self.example)
            with offline():
                resumed = workflow.handoff(copy_, self.example, target, task_id)
                plan = workflow.plan_task(copy_, self.example, target, task_id)
            self.assertEqual(resumed, value, f"{task_id}: the copy gives another packet")
            self.assertEqual(plan.claim["key"], self.planned(task_id).claim["key"])

    def test_observed_predicted_scaffold_and_unevidenced_gaps_stay_apart(self):
        from targets import workflow_handoff
        (self.folder / "records/build-failure.json").write_text(json.dumps({"stage": "build", "log": "javac: error"}))
        target = self.blocked(
            {"kind": "input-construction", "observed": False, "task": "fixed-security", "summary": "a predicted one"},
            {"kind": "build-or-dependency", "observed": True, "task": "fixed-security", "summary": "the build failed",
             "packet": "records/build-failure.json"},
            {"kind": "java-semantics", "observed": True, "task": "mutant-security", "summary": "no evidence",
             "packet": "records/absent.json"})
        value = self.handoff("fixed-security", target)
        predicted, build = value["gaps"]
        self.assertEqual((predicted["observed"], predicted["class"], predicted["packet"]), (False, "capability", None))
        self.assertIn("hypothesis", predicted["evidence"])
        self.assertEqual((build["observed"], build["class"]), (True, "scaffold"))
        self.assertIn("runtime.py", build["packet"]["module"]["likely"][0])
        self.assertIn("command", build["packet"]["missing"], "a packet that records no command says so")
        self.assertEqual(value["next"], "python3 examples/tools/build.py 999 --task fixed-security")
        self.assertIn("leaves the scaffold partial", value["nextReason"])
        value = self.handoff("mutant-security", target)
        [unevidenced] = value["gaps"]
        self.assertTrue(unevidenced["observed"])
        self.assertIn("missing", unevidenced["evidence"])
        self.assertFalse(unevidenced["packet"]["present"])
        self.assertNotIn("reproduce", value["nextReason"], "an observed gap without its packet is not reproduced")
        groups = {g["gap"]: g for g in workflow_handoff.inventory([(self.folder, self.example, target)])["gaps"]}
        self.assertEqual((groups["java-semantics: no evidence"]["observed"],
                          groups["java-semantics: no evidence"]["blockedObligations"]), (False, 0))
        self.assertEqual((groups["build-or-dependency: the build failed"]["observed"],
                          groups["build-or-dependency: the build failed"]["class"]), (True, "scaffold"))
        self.assertFalse(groups["input-construction: a predicted one"]["observed"])

    def test_prerequisites_come_first_and_a_stale_receipt_is_apart(self):
        value = self.handoff("preservation")
        self.assertEqual(value["nextPrerequisite"], "replay")
        self.assertEqual(value["next"], "python3 examples/tools/build.py 999 --task replay", "a replay runs inline")
        receipt = self.ingest("replay", self.recorded(("before", "after")))
        value = self.handoff("preservation")
        self.assertEqual((value["nextPrerequisite"], value["prerequisites"][0]["satisfied"]), (None, True))
        self.assertTrue(value["next"].startswith("python3 verification/pipeline.py submit --example 999 --task "
                                                 "preservation "), value["next"])
        replay = self.handoff("replay")
        [current] = replay["receipts"]
        self.assertEqual((current["path"], current["execution"], current["expectation"]),
                         (receipt.path, "completed", "yes"))
        self.assertEqual(current["sha256"], workflow.file_sha256(self.folder / receipt.path))
        self.assertEqual(replay["next"], "python3 examples/tools/build.py --plan 999 --task vulnerable-security")
        oracle = self.folder / "gate/oracle.py"
        oracle.write_text(oracle.read_text() + "\n")
        replay = self.handoff("replay")
        self.assertEqual(replay["receipts"], [])
        self.assertEqual([s["path"] for s in replay["staleReceipts"]], [receipt.path])
        self.assertEqual(self.handoff("preservation")["nextPrerequisite"], "replay")

    def test_a_task_that_doesnt_plan_says_so_and_keeps_its_gaps(self):
        target = self.changed("regex-probe", engine=None)
        self.task(target, "regex-probe").pop("engine")
        value = self.handoff("regex-probe", target)
        self.assertFalse(value["plan"]["executable"])
        self.assertEqual(value["next"], "python3 examples/tools/build.py --plan 999 --task regex-probe")
        self.assertIn("engine", value["nextReason"])
        self.assertIn("claims/regex-probe.json", [i["path"] for i in value["inputs"]])
        [gap] = value["gaps"]
        self.assertIn("refused", gap["packet"]["claim"])
        self.assertTrue(interfaces.unsupported(workflow.handoff(self.folder, self.example, self.target, "no-such")))

    def test_the_inventory_groups_gaps_across_families_by_blocked_obligations(self):
        from targets import workflow_handoff
        rows = [(self.folder, self.example, self.blocked(
            {"kind": "input-construction", "observed": False, "task": "fixed-security", "summary": "predicted"}))]
        for name, family, role in (("two", "f-two", "negative"), ("three", "f-two", "positive")):
            folder = Path(self.dir.name) / name
            shutil.copytree(self.folder, folder)
            target = copy.deepcopy(self.target)
            target["identity"].update(family=family, role=role, case=f"case-{name}")
            rows.append((folder, {**self.example, "id": f"99{len(rows)}"}, target))
        with offline():
            value = workflow_handoff.inventory(rows)
        self.assertEqual(value["schema"], "example-target-gap-inventory/v1")
        regex = value["gaps"][:3]
        self.assertTrue(all(g["observed"] and g["families"] == ["f-two", "phase0-fixture"]
                            and g["blockedObligations"] == 3 and g["negativeAndPositive"] for g in regex), regex)
        self.assertEqual({g["gap"] for g in regex}, {workflow_handoff.strip_jdk(g["id"]) for g in json.loads(
            (self.folder / "records/regex-gate-gaps.stdout").read_text())["gaps"]})
        self.assertEqual(regex[0]["modules"], ["lib/src/models.rs"])
        predicted = value["gaps"][-1]
        self.assertEqual((predicted["observed"], predicted["blockedObligations"], predicted["predictedObligations"]),
                         (False, 0, 1))

    def test_a_blocker_naming_no_task_is_the_targets(self):
        """A blocker without a task is the whole target's, as discovery reads it: every task's handoff shows it, a
        capability one only on the tasks that run the verifier, and the inventory counts it. Phase 5's A1 found 307's
        predicted build blocker in no task's handoff, and 305's and 307's predicted gaps outside the inventory."""
        from targets import workflow_handoff
        target = self.blocked({"kind": "build-or-dependency", "observed": False, "summary": "the build"},
                              {"kind": "input-construction", "observed": False, "summary": "the receiver"})
        replay = self.handoff("replay", target)
        self.assertEqual([(g["kind"], g["observed"], g["class"]) for g in replay["gaps"]],
                         [("build-or-dependency", False, "scaffold")], "a replay runs no verifier")
        self.assertEqual(replay["next"], self.handoff("replay")["next"], "a prediction blocks nothing")
        self.assertEqual([g["kind"] for g in self.handoff("preservation", target)["gaps"]],
                         ["build-or-dependency", "input-construction"])
        regex = self.handoff("regex-probe", target)
        self.assertEqual([(g["kind"], g["observed"]) for g in regex["gaps"]],
                         [("java-semantics", True), ("build-or-dependency", False), ("input-construction", False)])
        with offline():
            value = workflow_handoff.inventory([(self.folder, self.example, target)])
        counts = {g["gap"].split(":")[0]: g["predictedObligations"] for g in value["gaps"] if not g["observed"]}
        proofs = sum(t["kind"] != "replay" for t in target["tasks"])
        self.assertEqual((counts["build-or-dependency"], counts["input-construction"]), (len(target["tasks"]), proofs))
        observed = target["handoff"]["blockers"][0]
        target["handoff"]["blockers"] += [{**observed, "kind": "build-or-dependency", "packet": None}]
        del target["handoff"]["blockers"][-1]["task"], target["handoff"]["blockers"][-1]["packet"]
        self.assertEqual(workflow.readiness(self.folder, self.example, target)["tasks"]["fixed-security"]["summary"],
                         "partial", "an observed build blocker of the target leaves every task partial")

    def test_the_command_line_prints_the_packet(self):
        import contextlib as context
        import io
        import build
        from targets import workflow_handoff
        root = Path(self.dir.name)
        shutil.copytree(build.EXAMPLES / "schema", root / "schema")
        (root / "tags.json").write_text(json.dumps({"domain": {"open-source-libraries": "d"}}))
        out = io.StringIO()
        with mock.patch.object(build, "EXAMPLES", root), mock.patch.dict(build._TAGS, clear=True), \
                context.redirect_stdout(out):
            workflow_handoff.main(["handoff", "999", "regex-probe"])
        self.assertEqual(json.loads(out.getvalue()), json.loads(json.dumps(self.handoff("regex-probe"))))


class DiscoveryTest(Fixture):
    """W4's projection, the index's `target` row that find.py's target filters read: derived readiness, claim
    statuses from current receipts only, observed, unevidenced and predicted gaps, and the authored label kept apart
    as historical context; through build.py's render_index() and find.py on a temporary examples/."""

    prepared, recorded, verifier, ingest = IngestTest.prepared, IngestTest.recorded, IngestTest.verifier, IngestTest.ingest

    @classmethod
    def setUpClass(cls):
        cls.manifest = fixture_manifest()

    def setUp(self):
        super().setUp()
        self.controls = json.loads((self.folder / "records/controls.json").read_text())["records"]

    def project(self, folder=None, example=None, target=None):
        folder = folder or self.folder
        before = tree(folder)
        with offline():
            row = workflow.project(folder, example or self.example, target or self.target)
        self.assertEqual(tree(folder), before, "the projection wrote into the example's folder")
        json.dumps(row)  # it goes into index.json
        return row

    def another(self, name, example_id, change):
        """A copy of the fixture as example `example_id` in the same temporary examples/, its sidecar changed."""
        folder = Path(self.dir.name) / name
        shutil.copytree(self.folder, folder)
        example = {**self.example, "id": example_id}
        (folder / "example.json").write_text(json.dumps(example))
        target = json.loads((folder / "target.json").read_text())
        change(target, folder)
        (folder / "target.json").write_text(json.dumps(target))
        return folder

    def find(self, *folders, readiness=True):
        """The index rendered by build.py over these folders, and a function running find.py on it."""
        import contextlib as context
        import io
        import build
        import find
        from targets import workflow_discovery
        root = Path(self.dir.name)
        if not (root / "schema").exists():
            shutil.copytree(build.EXAMPLES / "schema", root / "schema")
            (root / "tags.json").write_text(json.dumps({"domain": {"open-source-libraries": "d"}}))
            (root / "README.md").write_text("<!-- examples:begin --><!-- examples:end -->\n"
                                            "<!-- tags:begin --><!-- tags:end -->\n")
        patches = (mock.patch.object(build, "EXAMPLES", root), mock.patch.object(find, "EXAMPLES", root),
                   mock.patch.dict(build._TAGS, clear=True),
                   mock.patch.object(workflow_discovery, "READINESS_IN_INDEX", readiness))
        with context.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            with offline():
                build.render_index(sorted(folders))
        index = {e["id"]: e for e in json.loads((root / "index.json").read_text())["examples"]}

        def run(*argv):
            out = io.StringIO()
            with mock.patch.object(find, "EXAMPLES", root), context.redirect_stdout(out):
                code = find.main(["--json", *argv])
            return sorted(e["id"] for e in json.loads(out.getvalue())) if code == 0 else []
        return index, run

    def test_the_fixture_projects_its_readiness_and_no_claim_without_a_receipt(self):
        row = self.project()
        tasks = [t["id"] for t in self.target["tasks"]]
        self.assertEqual((row["family"], row["role"], row["case"], row["tasks"]),
                         ("phase0-fixture", "control", "phase0-fixture-gate", tasks))
        self.assertEqual(row["taskReadiness"], {t: "partial" for t in tasks}, "nothing is prepared yet")
        self.assertEqual(row["readiness"], workflow.readiness(self.folder, self.example, self.target)["summary"])
        self.assertNotIn("unsupported", row)
        self.assertEqual(row["expected"], {t["id"]: t.get("expected") for t in self.target["tasks"]})
        proofs = [t["id"] for t in self.target["tasks"] if t["kind"] != "replay"]
        self.assertEqual(row["claims"], {t: None for t in proofs}, "an expectation is not a claim status")
        self.assertEqual((row["receipts"], row["staleReceipts"], row["unreadable"]), ({}, [], []))
        scan = json.loads((self.folder / "records/regex-gate-gaps.stdout").read_text())
        self.assertEqual((row["gaps"], row["gapIds"], row["unevidencedGaps"], row["predictedGaps"]),
                         (["java-semantics"], sorted(g["id"] for g in scan["gaps"]), [], []))
        self.assertEqual(row["historical"]["verdictLabel"], self.example["verdictLabel"])
        self.assertEqual(row["handoff"], "python3 examples/tools/targets/workflow_handoff.py handoff 999 TASK")
        from targets import workflow_discovery
        with mock.patch.object(workflow_discovery, "READINESS_IN_INDEX", False):
            row = self.project()
        self.assertEqual((row["readiness"], row["unsupported"]), (None, workflow_discovery_hold()))

    def test_claim_statuses_come_from_the_latest_current_receipt_and_stale_ones_are_apart(self):
        witness = {"input": "code=97", "outcome": "returned true"}
        replay = self.ingest("replay", self.recorded(("before", "after")))
        first = self.ingest("fixed-security", (self.verifier([outcome("verified")], 0, revision="after"),))
        latest = self.ingest("fixed-security", (self.verifier(
            [outcome("unverifiable", problem="the solver gave up")], 1, revision="after"),))
        refuted = self.ingest("vulnerable-security", (self.verifier([outcome("violation", witness)], 1),))
        row = self.project()
        self.assertEqual({k: v for k, v in row["claims"].items() if v}, {"fixed-security": "unresolved",
                                                                         "vulnerable-security": "refuted"})
        self.assertNotIn("replay", row["claims"], "a replay decides no claim")
        fixed = row["receipts"]["fixed-security"]
        self.assertEqual((fixed["path"], fixed["attempts"], fixed["execution"], fixed["status"]),
                         (latest.path, 2, "completed", "unresolved"), "the latest attempt, the earlier one kept")
        self.assertTrue((self.folder / first.path).is_file())
        self.assertEqual((row["receipts"]["replay"]["status"], row["receipts"]["replay"]["expectation"]), (None, "yes"))
        self.assertEqual(row["receipts"]["vulnerable-security"]["expectation"], "yes")
        claim = self.folder / "claims/gate-security.json"
        claim.write_text(json.dumps({**json.loads(claim.read_text()), "statement": "another statement"}))
        row = self.project()
        self.assertEqual((row["claims"]["fixed-security"], row["claims"]["vulnerable-security"]), (None, None),
                         "a changed claim makes its receipts stale, never silently reused")
        self.assertEqual(sorted(row["staleReceipts"]), sorted([first.path, latest.path, refuted.path]))
        self.assertEqual(row["receipts"]["replay"]["path"], replay.path, "the replay's inputs didn't change")
        (self.folder / "receipts/fixed-security/broken").mkdir()
        (self.folder / "receipts/fixed-security/broken/result.json").write_text("{")
        self.assertEqual(self.project()["unreadable"], ["receipts/fixed-security/broken/result.json"])

    def test_a_historical_label_never_becomes_a_claim_status(self):
        example = {**self.example, "verdictLabel": "\u2713 established on after; \u2717 refuted on before (JBMC, 2026-11-01)"}
        (self.folder / "example.json").write_text(json.dumps(example))
        self.example = example
        row = self.project()
        self.assertEqual(row["historical"]["verdictLabel"], example["verdictLabel"])
        self.assertTrue(all(v is None for v in row["claims"].values()))
        index, find = self.find(self.folder)
        self.assertEqual(index["999"]["verdictLabel"], example["verdictLabel"], "the authored label, beside the row")
        self.assertEqual(index["999"]["target"]["historical"]["verdictLabel"], example["verdictLabel"])
        for status in ("established", "refuted", "unresolved"):
            self.assertEqual(find("--claim-status", status), [], status)
        self.ingest("fixed-security", (self.verifier([outcome("verified")], 0, revision="after"),))
        index, find = self.find(self.folder)
        self.assertEqual((find("--claim-status", "established"), find("--claim-status", "refuted")), (["999"], []))
        self.assertEqual(index["999"]["verdictLabel"], example["verdictLabel"], "a receipt never replaces the label")

    def test_find_reaches_catalogued_and_gap_blocked_targets_and_keeps_predictions_apart(self):
        def catalogued(target, folder):
            target.pop("preparation")
            target["identity"]["family"] = "f-catalogued"
            target["handoff"]["blockers"] = [{"kind": "input-construction", "observed": False, "summary": "predicted"}]

        def unevidenced(target, folder):
            target["identity"]["family"] = "f-unevidenced"
            (folder / "records/regex-gate-gaps.json").unlink()
        folders = [self.folder, self.another("998-catalogued", "998", catalogued),
                   self.another("997-unevidenced", "997", unevidenced)]
        index, find = self.find(*folders, readiness=True)
        self.assertEqual({i: index[i]["target"]["readiness"] for i in ("997", "998", "999")},
                         {"997": "partial", "998": "catalogued", "999": "partial"})
        self.assertEqual(index["997"]["target"]["unevidencedGaps"], ["java-semantics"])
        self.assertEqual(index["998"]["target"]["predictedGaps"], ["input-construction"])
        self.assertEqual(find("--readiness", "catalogued"), ["998"])
        self.assertEqual(find("--family", "f-catalogued", "--role", "control"), ["998"])
        self.assertEqual(find("--readiness", "partial", "--family", "phase0-fixture"), ["999"])
        self.assertEqual(find("--gap", "java-semantics"), ["999"], "observed with its packet; a missing one doesn't count")
        self.assertEqual(find("--gap", "input-construction"), [], "a prediction is no observed gap")
        self.assertEqual(find("--readiness", "blocked"), [])
        index, find = self.find(*folders, readiness=False)
        self.assertEqual(find("--readiness", "catalogued"), [], "held while READINESS_IN_INDEX is off")
        self.assertEqual(index["998"]["target"]["taskReadiness"]["fixed-security"], "catalogued")

    def test_a_blocked_target_is_found_by_its_readiness_and_its_gap(self):
        self.ingest("replay", self.recorded(("before", "after")))
        self.ingest("mutant-replay", self.recorded(("after", "mutant")))
        target = copy.deepcopy(self.target)
        target["tasks"] = [t for t in target["tasks"] if t["id"] in ("regex-probe", "replay")]
        (self.folder / "target.json").write_text(json.dumps(target))
        index, find = self.find(self.folder, readiness=True)
        row = index["999"]["target"]
        self.assertEqual((row["readiness"], row["taskReadiness"]), ("blocked", {"regex-probe": "blocked",
                                                                                "replay": "scaffolded"}))
        self.assertEqual(find("--readiness", "blocked", "--gap", "java-semantics"), ["999"])
        self.assertEqual(row["claims"], {"regex-probe": None}, "blocked is readiness, not a claim status")


class StubsFailClosedTest(unittest.TestCase):
    def check(self, value, interface, owner):
        self.assertTrue(interfaces.unsupported(value))
        self.assertEqual((value.interface, value.owner), (interface, owner))
        self.assertIn(owner, value.describe())

    def test_ingestion_without_a_sidecar_is_refused(self):
        value = workflow.ingest(plan(), {}, (), Path("."))
        self.check(value, "ingest", interfaces.WORKFLOW)
        self.assertNotIn("Phase 0's stub", value.reason)

    def test_a_handoff_of_an_unknown_task_is_refused(self):
        value = workflow.handoff(Path("."), {}, {}, "t")
        self.check(value, "handoff", interfaces.WORKFLOW)
        self.assertNotIn("Phase 0's stub", value.reason)


if __name__ == "__main__":
    unittest.main()

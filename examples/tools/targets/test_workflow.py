#!/usr/bin/env python3
"""Tests of workflow.py, owned by the workflow stream with it: task planning and the readiness milestones (W1), on a
copy of Phase 0's fixture and on sidecars changed from it. ingest() and handoff() are still Phase 0's stubs, which fail
closed with the named Unsupported result; their tests are rewritten as each stub is replaced.

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
            "attempt": {"id": attempt, "execution": execution},
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

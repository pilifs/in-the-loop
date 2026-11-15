#!/usr/bin/env python3
"""Tier A on the merged packets (Phase 5 step 3 of llm-dlc/loops/example-targets.md): rows A1, A2 and A6 of
llm-dlc/loops/example-targets-acceptance.md, checked on the real sidecars and on the receipts that the pipeline's jobs
left in the tree, where test_targets_contract.py checks the same rows on Phase 0's fixture. Offline and read-only: it
reads files, imports the route's modules, and runs nothing.

  A1  every task of every sidecar example plans, and hands off, with no network, process or write; a native task
      needs no JBMC; a task that acquires says so; a blocker the sidecar records is in the handoff of each task it
      blocks, and in discovery.
  A2  every receipt records its revisions' commits, each JDK's release file, and the classpath in order with each
      entry's role and sha256, the same in the claim and in each JVM's record; a published revision ran its pinned
      bytes. The refusals (wrong bytes, a shadowed class, an escaping path) are runtime's and the sidecar's unit tests,
      named in A2's last test so a renamed one is noticed.
  A6  every receipt is a valid format-2 receipt whose bundle is the files beside it; tasks and attempts keep distinct
      receipts; a replay concludes nothing; a proof is native, not vacuous, and a refutation carries its witness (an
      equivalence's with its interpreter replay; a property check's replay is stated only in its proof text);
      execution, conclusion, expectation, scope and replay are separate fields; each is its task's current receipt.
"""

import contextlib
import json
import os
import re
import socket
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))
import build  # noqa: E402
import result_format  # noqa: E402
from targets import interfaces, sidecar, workflow, workflow_discovery  # noqa: E402
from targets.interfaces import Unsupported  # noqa: E402

SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
# The deep packets and the calibration: the examples whose receipts this file reads.
PACKETS = ("105", "285", "286", "287", "305", "306", "307")


def sidecar_examples():
    """(folder, example, target) of every example with a target.json, in number order."""
    out = []
    for path in sorted(EXAMPLES.glob("[0-9][0-9][0-9]-*/target.json")):
        example = build.load_example(path.parent)
        out.append((path.parent, example, sidecar.load(path.parent, example)))
    return out


def receipts():
    """Every receipt in the tree: (folder, task, attempt directory, stored document)."""
    out = []
    for path in sorted(EXAMPLES.glob("[0-9][0-9][0-9]-*/receipts/*/*/result.json")):
        out.append((path.parents[3], path.parent.parent.name, path.parent, json.loads(path.read_text())))
    return out


def tree(folder):
    return {p.relative_to(folder).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in sorted(Path(folder).rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


@contextlib.contextmanager
def offline():
    """No network and no subprocess, as test_targets_contract.py's A1 has it."""
    def refuse(*a, **k):
        raise AssertionError("an offline operation opened a connection or started a process")
    with mock.patch.object(socket.socket, "connect", refuse), mock.patch.object(socket, "create_connection", refuse), \
            mock.patch.object(subprocess, "Popen", refuse), mock.patch.object(os, "system", refuse):
        yield


def base_of(target, revision):
    """A mutant's base revision, else the revision itself."""
    r = target["history"]["revisions"][revision]
    return r["mutant"]["base"] if "mutant" in r else revision


def run_identity(target, revision):
    """What a JVM record names as the revision it ran: its commit, or for a mutant `mutant:<base commit>+<patch
    sha256>` (runtime binds a mutant's claim to its base and its patch)."""
    r = target["history"]["revisions"][revision]
    if "mutant" in r:
        base = target["history"]["revisions"][r["mutant"]["base"]]["commit"]
        return f"mutant:{base}+{r['mutant']['sha256']}"
    return r["commit"]


class A1OfflinePlanningOnThePackets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples = sidecar_examples()

    def test_the_tree_has_the_twenty_sidecar_examples(self):
        self.assertEqual([e["id"] for _, e, _ in self.examples],
                         ["105", *map(str, range(285, 301)), "305", "306", "307"])

    def test_every_task_plans_and_hands_off_offline_without_writing(self):
        for folder, example, target in self.examples:
            before = tree(folder)
            for t in target["tasks"]:
                with self.subTest(example=example["id"], task=t["id"]):
                    with offline():
                        plan = workflow.plan_task(folder, example, target, t["id"])
                        packet = workflow.handoff(folder, example, target, t["id"])
                    self.assertIsInstance(plan, (interfaces.TaskPlan, Unsupported))
                    if isinstance(plan, Unsupported):
                        self.assertTrue(plan.reason, "a refusal says why")
                        self.assertFalse(packet["plan"]["executable"])
                        continue
                    self.assertEqual((plan.task, plan.kind, plan.expected), (t["id"], t["kind"], t.get("expected")))
                    if plan.engine == "native":
                        self.assertNotIn("jbmc", plan.tools["required"] + plan.tools["optional"])
                    routes = {a["route"] for a in plan.artifacts}
                    self.assertEqual(plan.network, bool(routes - {"fixture"}),
                                     f"routes {sorted(routes)}: a task that acquires says so")
                    self.assertTrue(all(isinstance(g["observed"], bool) for g in packet["gaps"]))
                    self.assertEqual(packet["commands"][0], f"python3 examples/tools/build.py --plan {example['id']} "
                                                            f"--task {t['id']}")
            self.assertEqual(tree(folder), before, f"{folder.name}: planning or the handoff wrote into the folder")

    def test_each_recorded_blocker_is_in_the_handoff_of_every_task_it_blocks(self):
        """A target's blocker (one naming no task) is in each task's handoff, a capability one only where the
        verifier runs. Before Phase 5's A1, 307's predicted build blocker showed in none of its four handoffs, whose
        next action said to run the replay with no word of the build."""
        for folder, example, target in self.examples:
            for b in target.get("handoff", {}).get("blockers", []):
                for t in target["tasks"]:
                    if b.get("task") not in (None, t["id"]):
                        continue
                    if b.get("task") is None and t["kind"] == "replay" and b["kind"] in workflow.CAPABILITY_KINDS:
                        continue
                    with self.subTest(example=example["id"], task=t["id"], kind=b["kind"]):
                        with offline():
                            gaps = workflow.handoff(folder, example, target, t["id"])["gaps"]
                        self.assertIn((b["kind"], b["observed"], b["summary"]),
                                      [(g["kind"], g["observed"], g["summary"]) for g in gaps])
        _, example, target = next(x for x in self.examples if x[1]["id"] == "307")
        folder = next(EXAMPLES.glob("307-*"))
        self.assertIn("build-or-dependency", [g["kind"] for g in workflow.handoff(folder, example, target, "replay")["gaps"]])

    def test_discovery_projects_each_target_offline_and_keeps_predictions_apart(self):
        index = {e["id"]: e for e in json.loads((EXAMPLES / "index.json").read_text())["examples"]}
        for folder, example, target in self.examples:
            with self.subTest(example["id"]):
                with offline():
                    projected = workflow.project(folder, example, target)
                self.assertNotIsInstance(projected, Unsupported)
                gaps = workflow_discovery.gaps(folder, target)
                self.assertEqual(projected["predictedGaps"], gaps["predictedGaps"])
                self.assertEqual(set(projected["gaps"]) & set(projected["predictedGaps"]) - set(gaps["gaps"]), set())
                committed = index[example["id"]]["target"]
                self.assertEqual((committed["readiness"], committed["predictedGaps"], committed["gaps"]),
                                 (projected["readiness"], projected["predictedGaps"], projected["gaps"]),
                                 "the committed index is the projection: rerun build.py --index-only")


class A2PreparationIntegrityOnTheReceipts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipts = receipts()
        cls.targets = {str(f.name[:3]): (f, e, t) for f, e, t in sidecar_examples()}

    def test_the_packets_have_receipts(self):
        self.assertGreaterEqual(len(self.receipts), 14)
        self.assertEqual({f.name[:3] for f, _, _, _ in self.receipts}, set(PACKETS) - {"307"})

    def test_each_receipt_names_its_commits_jdks_and_ordered_classpath(self):
        for folder, task, directory, doc in self.receipts:
            _, _, target = self.targets[folder.name[:3]]
            t = doc["claim"]["target"]
            with self.subTest(str(directory.relative_to(EXAMPLES))):
                self.assertEqual(t["task"], task)
                self.assertRegex(t["sidecar"], SHA256)
                for revision, commit in t["revisions"].items():
                    self.assertRegex(commit, COMMIT)
                    self.assertEqual(commit, target["history"]["revisions"][base_of(target, revision)]["commit"])
                self.assertTrue(t["jdks"] and all("version" in j for j in t["jdks"]))
                for revision in t["revisions"]:
                    entries = sorted((d for d in t["dependencies"] if d["revision"] == revision),
                                     key=lambda d: d["position"])
                    self.assertEqual([d["position"] for d in entries], list(range(len(entries))))
                    self.assertTrue(all(SHA256.match(d["sha256"]) for d in entries))
                    self.assertEqual(sum(d["role"] == "original" for d in entries), 1, revision)
                    self.assertIn("driver", [d["role"] for d in entries])
                for name, digest in t["files"].items():
                    self.assertRegex(digest, SHA256, name)

    def test_each_jvm_record_ran_the_classpath_its_claim_names_on_a_recorded_jdk(self):
        for folder, task, directory, doc in self.receipts:
            _, _, target = self.targets[folder.name[:3]]
            t = doc["claim"]["target"]
            records = json.loads((directory / "records/execution.json").read_text())["records"]
            jvms = [r for r in records if r["kind"] == "jvm-control"]
            with self.subTest(str(directory.relative_to(EXAMPLES))):
                self.assertTrue(jvms, "every receipt here ran its concrete controls")
                for r in jvms:
                    ids = r["identities"]
                    self.assertEqual(ids["commit"], run_identity(target, r["revision"]))
                    self.assertTrue(ids["commit"].startswith(t["revisions"][r["revision"]]) or
                                    ids["commit"].startswith(f"mutant:{t['revisions'][r['revision']]}+"))
                    self.assertTrue({"JAVA_VERSION", "IMPLEMENTOR"} <= set(ids["jdkRelease"]), ids["jdkRelease"])
                    self.assertIn(ids["jdk"], t["jdks"])
                    claimed = [(d["role"], d["sha256"]) for d in sorted(
                        (d for d in t["dependencies"] if d["revision"] == r["revision"]), key=lambda d: d["position"])]
                    self.assertEqual([(c["role"], c["sha256"]) for c in ids["classpath"]], claimed)
                    self.assertEqual(ids["inputs"]["oracleSha256"], t["files"][ids["inputs"]["oracle"]])
                    self.assertEqual(ids["replay"], "original-jvm")
                features = {(r["revision"], r["identities"]["jdkFeature"]) for r in jvms}
                self.assertEqual(features, {(rev, f) for rev in t["revisions"] for f in ("21", "25")},
                                 "each revision on JDK 21 and 25 (decision 3)")

    def test_a_published_revision_ran_its_pinned_bytes(self):
        """Each library JAR of a published revision, and its original unless the revision is a mutant (rebuilt from
        its base), is one the sidecar pins for that revision (or the mutant's base)."""
        for folder, task, directory, doc in self.receipts:
            _, _, target = self.targets[folder.name[:3]]
            prep = target["preparation"]
            t = doc["claim"]["target"]
            for revision in t["revisions"]:
                base = base_of(target, revision)
                route = target["history"]["revisions"][base].get("route", prep["route"])
                pinned = {a["sha256"] for a in prep.get("artifacts", []) if a["revision"] == base}
                pinned |= {a["sha256"] for a in prep.get("slice", {}).get("published", {}).get(base, [])
                           if isinstance(a, dict) and "sha256" in a}
                with self.subTest(str(directory.relative_to(EXAMPLES)), revision=revision, route=route):
                    for d in t["dependencies"]:
                        if d["revision"] != revision:
                            continue
                        if d["role"] == "dependency" or (d["role"] == "original" and route == "published-artifact"
                                                         and base == revision):
                            self.assertIn(d["sha256"], pinned, d)

    def test_the_refusals_are_runtimes_and_the_sidecars_unit_tests(self):
        from targets import test_runtime, test_runtime_upstream, test_sidecar
        named = {
            test_runtime.PublishedTest: ["test_bytes_that_differ_from_the_lock_are_refused_never_cached_or_used",
                                         "test_a_dependency_that_repeats_a_class_is_refused_as_shadowing"],
            test_runtime.ControlsTest: ["test_bytes_changed_since_preparation_are_not_run"],
            test_runtime.PrepareTest: ["test_a_shadowing_adapter_fails_at_the_classpath_with_what_exists"],
            test_runtime.LockTest: ["test_a_path_out_of_the_folder_is_refused", "test_a_link_out_of_the_folder_is_refused"],
        }
        for cls, names in named.items():
            for name in names:
                self.assertTrue(callable(getattr(cls, name, None)), f"{cls.__name__}.{name}")
        found = {n for m in (test_runtime_upstream, test_sidecar) for c in vars(m).values()
                 if isinstance(c, type) and issubclass(c, unittest.TestCase) for n in dir(c)}
        for name in ("test_a_dependency_that_repeats_the_targets_class_is_refused_as_shadowing",
                     "test_a_zip_entry_outside_its_root_is_never_unpacked", "test_a_path_escape_is_refused"):
            self.assertIn(name, found)


class A6ReceiptIntegrityOnTheReceipts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipts = receipts()
        cls.targets = {str(f.name[:3]): (f, e, t) for f, e, t in sidecar_examples()}

    def test_each_receipt_is_a_valid_format_2_receipt_whose_bundle_is_beside_it(self):
        for folder, task, directory, doc in self.receipts:
            with self.subTest(str(directory.relative_to(EXAMPLES))):
                self.assertEqual(result_format.stored_format(doc), 2)
                self.assertTrue((directory / workflow.PLAN_RECORD).is_file())
                try:
                    build.check_result(directory, result_format.view(doc))
                except SystemExit as e:
                    self.fail(str(e))

    def test_tasks_and_attempts_keep_distinct_receipts(self):
        attempts = [d["attempt"]["id"] for _, _, _, d in self.receipts]
        self.assertEqual(len(attempts), len(set(attempts)))
        claims = {}
        for folder, task, directory, doc in self.receipts:
            self.assertEqual(doc["attempt"]["claim"], doc["claim"]["id"])
            self.assertEqual(doc["conclusion"]["claim"], doc["claim"]["id"])
            self.assertEqual(doc["conclusion"]["attempt"], doc["attempt"]["id"])
            claims.setdefault(doc["claim"]["id"], set()).add((folder.name[:3], task))
        self.assertTrue(all(len(v) == 1 for v in claims.values()), "one claim id, one example's task")
        self.assertEqual(len(claims), len({(f.name[:3], t) for f, t, _, _ in self.receipts}))

    def test_execution_conclusion_expectation_scope_and_replay_stay_apart(self):
        for folder, task, directory, doc in self.receipts:
            _, _, target = self.targets[folder.name[:3]]
            kind = next(t for t in target["tasks"] if t["id"] == task)["kind"]
            c, e = doc["conclusion"], doc["evidence"]
            with self.subTest(str(directory.relative_to(EXAMPLES)), kind=kind):
                self.assertEqual(doc["attempt"]["execution"]["status"], "completed")
                self.assertEqual(c["expectation"], "yes")
                if kind == "replay":
                    self.assertIsNone(c["status"], "a replay decides no claim")
                    self.assertEqual(c["obligations"], [])
                    self.assertEqual(e["replay"], {"by": "jvm", "reproduced": True})
                    self.assertIsNone(doc["attempt"]["engine"])
                else:
                    self.assertIn(c["status"], ("established", "refuted"))
                    self.assertEqual(doc["attempt"]["engine"], "native")
                    if kind == "prove":
                        self.assertTrue(c["obligations"], "a property check lists its obligations")
                    self.assertFalse(c["vacuous"])
                    if c["status"] == "refuted":
                        self.assertTrue(e["counterexamples"])
                        if kind == "equivalence":
                            self.assertEqual(e["replay"], {"by": "interpreter", "reproduced": True})
                slices = {r for r, a in target["history"]["revisions"].items()
                          if (a.get("route") or target["preparation"]["route"]) == "source-slice"}
                if target["preparation"]["route"] == "source-slice":
                    self.assertEqual(set(doc["claim"]["target"]["scopes"]), set(doc["claim"]["target"]["revisions"]))
                    self.assertTrue(slices)
                else:
                    self.assertNotIn("scopes", doc["claim"]["target"])

    def test_each_receipt_is_its_tasks_current_receipt(self):
        for folder, task, directory, doc in self.receipts:
            _, example, target = self.targets[folder.name[:3]]
            with self.subTest(str(directory.relative_to(EXAMPLES))):
                with offline():
                    packet = workflow.handoff(folder, example, target, task)
                self.assertIn(directory.name, [r["attempt"] for r in packet["receipts"]])
                self.assertEqual(packet["staleReceipts"], [])


if __name__ == "__main__":
    unittest.main()

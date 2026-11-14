#!/usr/bin/env python3
"""Tests of runtime.py and its modules (runtime_jdk.py, runtime_jar.py, runtime_maven.py), owned by the runtime stream
with them: the source lock and the fixture route's preparation (R1), the published-artifact route's hash-pinned
acquisition and cache (R2, against a local stand-in for Maven Central: nothing here uses the network) and the
separate-JVM controls (R4), on a copy of Phase 0's fixtures; and R5's slice (runtime_slice.py on runtime_simplematch/,
the published spring-core JARs, run from a private copy of their acquisition cache entries, skipped when the cache
doesn't hold them); and run_verifier (R3), against a stand-in jvmcontract that records how it was called:
the real verifier runs proofs, so runtime_calibrate.py runs it as a pipeline job.

  python3 examples/tools/targets/test_runtime.py
"""

import dataclasses
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "fixtures"))
import build_fixtures  # noqa: E402
from targets import interfaces, runtime, runtime_jar, runtime_jdk, runtime_maven  # noqa: E402

FIXTURES = HERE / "fixtures"
STUB = "Phase 0's stub"
_MANIFEST = {}


def manifest():
    """build_fixtures.py's own JARs, built once: the fixture route must give the same bytes."""
    if not _MANIFEST:
        out = tempfile.mkdtemp(prefix="test-runtime-")
        import atexit
        atexit.register(shutil.rmtree, out, True)
        _MANIFEST.update(build_fixtures.build(out), dir=out)
    return _MANIFEST


def fixture_plan(folder, revision="after", task="fixed-security", target="fixture.Gate#allowed(I)Z", **entry):
    artifact = {"revision": revision, "route": "fixture", "repository": "https://github.com/pilifs/in-the-loop",
                "fixture": f"gate/{revision}", "adapters": ["gate/adapter/fixture/adapter/GateAdapter.java"],
                "jdks": ["21", "25"], **entry}
    return interfaces.TaskPlan(
        example="999", task=task, kind="prove", relation="security", target=target, revisions=(revision,),
        claim={"task": task}, prerequisites=(), artifacts=(artifact,), tools={"required": ["java", "javac"], "optional": []},
        engine="native", gaps="strict", expected="established", outputs={"receipts": f"receipts/{task}"}, folder=str(folder))


class FixtureCopy(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="test-runtime-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.folder = self.dir / "999-fixture"
        shutil.copytree(FIXTURES, self.folder, ignore=shutil.ignore_patterns("__pycache__", "records", "results"))
        self.work = self.dir / "work"

    def prepare(self, revision="after", workdir=None, **kw):
        return runtime.prepare(fixture_plan(self.folder, revision, **kw), revision, workdir or self.work / revision)


class LockTest(FixtureCopy):
    def test_a_source_lock_hashes_the_selected_sources_and_runs_nothing(self):
        before = sorted(p for p in self.dir.rglob("*"))
        with mock.patch.object(subprocess, "Popen", side_effect=AssertionError("a source lock started a process")):
            locked = runtime.lock(fixture_plan(self.folder), "after")
        self.assertEqual(sorted(p for p in self.dir.rglob("*")), before, "a source lock wrote a file")
        self.assertEqual((locked.stage, locked.commit), ("source-locked", "fixture:gate/after"))
        self.assertEqual(locked.artifacts, ())
        self.assertEqual(locked.classpath, ())
        files = {f["path"]: f["sha256"] for f in locked.source["original"]["files"]}
        self.assertEqual(set(files), {"gate/after/fixture/Gate.java", "gate/both/fixture/RegexGate.java"})
        self.assertEqual(files["gate/after/fixture/Gate.java"], runtime.sha256(self.folder / "gate/after/fixture/Gate.java"))
        self.assertEqual(locked.source["adapter"]["roots"], ["gate/adapter"])
        self.assertEqual(locked.source["driver"]["control"], "gate-driver")
        self.assertEqual(locked.source["driver"]["main"], "fixture.driver.GateDriver")
        self.assertEqual(locked.source["oracle"]["path"], "gate/oracle.py")

    def test_a_path_out_of_the_folder_is_refused(self):
        for entry in ({"fixture": "../outside"}, {"adapters": ["../../etc/passwd"]}, {"fixture": "/tmp"}):
            locked = runtime.lock(fixture_plan(self.folder, **entry), "after")
            self.assertEqual((locked.stage, locked.failedStage), ("failed", "lock"), entry)
            self.assertTrue(locked.diagnostic)

    def test_a_link_out_of_the_folder_is_refused(self):
        outside = self.dir / "outside.java"
        outside.write_text("package fixture; class Outside {}\n")
        os.symlink(outside, self.folder / "gate/after/fixture/Outside.java")
        locked = runtime.lock(fixture_plan(self.folder), "after")
        self.assertEqual(locked.failedStage, "lock")
        self.assertIn("outside the example's folder", locked.diagnostic)

    def test_a_revision_the_task_does_not_prepare_is_refused(self):
        locked = runtime.lock(fixture_plan(self.folder), "before")
        self.assertEqual(locked.failedStage, "lock")

    def test_the_routes_to_come_are_unsupported_not_stubs(self):
        for route in ("upstream-build",):
            value = runtime.prepare(fixture_plan(self.folder, route=route), "after", self.work)
            self.assertTrue(interfaces.unsupported(value), route)
            self.assertEqual((value.interface, value.owner), ("prepare", interfaces.RUNTIME))
            self.assertNotIn(STUB, value.reason, "only Phase 0's stubs may say so")
        self.assertFalse(self.work.exists(), "an unsupported route made its work directory")


class PrepareTest(FixtureCopy):
    def test_artifacts_ready_records_bytes_classpath_jdk_and_the_target_origin(self):
        prepared = self.prepare()
        self.assertEqual(prepared.stage, "artifacts-ready", prepared.diagnostic)
        jars = manifest()["jars"]
        by_role = {a.role: a for a in prepared.artifacts}
        self.assertEqual(by_role["original"].sha256, jars["after"]["sha256"], "not build_fixtures.py's bytes")
        self.assertEqual(by_role["adapter"].sha256, jars["adapter-after"]["sha256"])
        self.assertEqual(by_role["driver"].sha256, jars["driver"]["sha256"])
        self.assertEqual(by_role["oracle"].sha256, runtime.sha256(FIXTURES / "gate/oracle.py"))
        self.assertEqual(prepared.classpath, ("driver.jar", "adapter-after.jar", "after.jar"))
        for a in prepared.artifacts:
            self.assertEqual(runtime.sha256(self.work / "after" / a.path), a.sha256, a.path)
        jdk = prepared.toolchain["jdk"]
        self.assertTrue(Path(jdk["home"]).is_absolute() and "current" not in Path(jdk["home"]).parts, jdk)
        self.assertTrue(jdk["version"] and jdk["release"].get("JAVA_VERSION"), jdk)
        self.assertEqual(prepared.source["target"]["loadedFrom"], "after.jar")
        self.assertEqual(prepared.source["target"]["descriptor"], "(I)Z")
        record = json.loads((self.work / "after" / runtime.RECORD).read_text())
        self.assertEqual(record["stage"], "artifacts-ready")
        self.assertEqual(record["classpath"], list(prepared.classpath))
        self.assertTrue(all((self.work / "after" / log).is_file() for log in prepared.logs))
        self.assertFalse((self.work / "after" / "classes").exists(), "intermediate classes left behind")

    def test_revisions_get_their_own_bytes_and_the_same_adapter_source(self):
        before, after = self.prepare("before"), self.prepare("after")
        original = lambda p: next(a.sha256 for a in p.artifacts if a.role == "original")
        self.assertNotEqual(original(before), original(after))
        self.assertEqual(before.source["adapter"], after.source["adapter"])

    def test_a_second_preparation_in_the_same_directory_starts_clean(self):
        first = self.prepare()
        (self.work / "after" / "stale.jar").write_bytes(b"stale")
        second = self.prepare()
        self.assertEqual(first.artifacts, second.artifacts)
        self.assertFalse((self.work / "after" / "stale.jar").exists())

    def test_a_directory_that_is_not_a_preparation_is_left_alone(self):
        self.work.mkdir()
        (self.work / "notes.txt").write_text("mine")
        prepared = self.prepare(workdir=self.work)
        self.assertEqual((prepared.stage, prepared.failedStage), ("failed", "workdir"))
        self.assertEqual((self.work / "notes.txt").read_text(), "mine")

    def test_a_shadowing_adapter_fails_at_the_classpath_with_what_exists(self):
        (self.folder / "gate/adapter/fixture/Gate.java").write_text(
            "package fixture;\npublic final class Gate { public static boolean allowed(int code) { return false; } }\n")
        prepared = self.prepare()
        self.assertEqual((prepared.stage, prepared.failedStage), ("failed", "classpath"))
        self.assertIn("fixture.Gate in adapter-after.jar, after.jar", prepared.diagnostic)
        self.assertEqual({a.role for a in prepared.artifacts}, {"original", "adapter", "driver", "oracle"},
                         "a partial preparation returns the artifacts that exist")
        self.assertEqual(json.loads((self.work / "after" / runtime.RECORD).read_text())["failedStage"], "classpath")

    def test_an_adapter_that_does_not_call_the_target_is_refused_for_a_replay_and_its_controls_never_run(self):
        source = self.folder / "gate/adapter/fixture/adapter/GateAdapter.java"
        source.write_text(source.read_text().replace("return Gate.allowed(code);", "return code != 65 && code != 97;")
                          .replace("import fixture.Gate;\n", ""))
        replay = dataclasses.replace(fixture_plan(self.folder), kind="replay", engine=None, gaps=None)
        prepared = runtime.prepare(replay, "after", self.work / "after")
        self.assertEqual((prepared.stage, prepared.failedStage), ("failed", "adapter"), prepared.diagnostic)
        # A proof task's verifier never goes through the adapter: there it is recorded, and its controls don't run.
        attempt = self.work / "attempt"
        prove = fixture_plan(self.folder)
        prepared = runtime.prepare(prove, "after", attempt / "prepare/after")
        self.assertEqual(prepared.stage, "artifacts-ready", prepared.diagnostic)
        self.assertEqual((prepared.source["target"]["adapterCallsTarget"], prepared.source["target"]["adapterCalls"]),
                         (False, []))
        [record, *_] = runtime.run_controls(prove, {"after": prepared}, attempt / "controls")
        self.assertEqual((record.status, record.observations), ("not-started", None))
        self.assertIn("not this task's evidence", (attempt / record.stderr).read_text())

    def test_a_proof_tasks_adapter_records_the_original_methods_it_calls(self):
        prepared = self.prepare()
        self.assertEqual(prepared.source["target"]["adapterCalls"], ["fixture.Gate#allowed(I)Z"])
        self.assertTrue(prepared.source["target"]["adapterCallsTarget"])
        probe = self.prepare(target="fixture.RegexGate#allowed(Ljava/lang/String;)Z", workdir=self.work / "probe")
        self.assertEqual(probe.stage, "artifacts-ready", "the fixture's regex probe is prepared for its verifier")
        self.assertFalse(probe.source["target"]["adapterCallsTarget"])

    def test_a_target_the_original_does_not_declare_is_refused(self):
        for target in ("fixture.Gate#allowed(J)Z", "fixture.Gate#denied(I)Z", "fixture.Missing#allowed(I)Z"):
            prepared = self.prepare(target=target)
            self.assertEqual((prepared.stage, prepared.failedStage), ("failed", "target"), target)

    def test_a_compile_failure_is_the_build_stage_with_its_diagnostic(self):
        (self.folder / "gate/after/fixture/Gate.java").write_text("package fixture; public final class Gate { oops }\n")
        prepared = self.prepare()
        self.assertEqual((prepared.stage, prepared.failedStage), ("failed", "build"))
        self.assertIn("javac-original failed", prepared.diagnostic)
        self.assertEqual(prepared.artifacts, ())
        self.assertTrue(prepared.logs and (self.work / "after" / prepared.logs[0]).is_file())


class JarTest(unittest.TestCase):
    def test_the_class_reader_sees_declarations_and_calls(self):
        out = Path(manifest()["dir"])
        gate = runtime_jar.read_class(out / "after.jar", "fixture/Gate")
        self.assertEqual(runtime_jar.this_class(gate), "fixture/Gate")
        self.assertIn(("allowed", "(I)Z"), runtime_jar.methods(gate))
        adapter = runtime_jar.read_class(out / "adapter-after.jar", "fixture/adapter/GateAdapter")
        self.assertIn(("fixture/Gate", "allowed", "(I)Z"), runtime_jar.references(adapter))
        regex = runtime_jar.read_class(out / "after.jar", "fixture/RegexGate")
        self.assertTrue(any(o == "java/util/regex/Pattern" for o, _, _ in runtime_jar.references(regex)))

    def test_duplicates_follow_classpath_order(self):
        out = Path(manifest()["dir"])
        self.assertEqual(runtime_jar.duplicates(["driver.jar", "adapter-after.jar", "after.jar"], out), [])
        dups = dict(runtime_jar.duplicates(["after.jar", "before.jar"], out))
        self.assertEqual(dups["fixture/Gate"], ["after.jar", "before.jar"])

    def test_targets_parse(self):
        self.assertEqual(runtime_jar.parse_target("a.B#m(I)Z"), ("a.B", "m", "(I)Z"))
        self.assertEqual(runtime_jar.parse_target("a.B#m"), ("a.B", "m", None))
        with self.assertRaises(ValueError):
            runtime_jar.parse_target("a.B")


class JdkTest(unittest.TestCase):
    def test_installed_jdks_are_found_by_full_path(self):
        homes = runtime_jdk.homes()
        if not {"21", "25"} <= set(homes):
            self.skipTest(f"JDKs 21 and 25 are not both under {runtime_jdk.CANDIDATES}")
        for f in ("21", "25"):
            identity = runtime_jdk.identity(homes[f])
            self.assertEqual(identity["feature"], f)
            self.assertNotIn("current", Path(identity["home"]).parts)
            self.assertIn(f'"{identity["release"]["JAVA_VERSION"]}"', identity["version"])

    def test_features(self):
        self.assertEqual(runtime_jdk.feature("1.8.0_512"), "8")
        self.assertEqual(runtime_jdk.feature("21.0.13"), "21")


DRIVER = """package fixture.driver;

import fixture.adapter.GateAdapter;

public final class GateDriver {
    static String line(String arg) {
        int code = Integer.parseInt(arg);
        return "{\\"input\\":" + code + ",\\"outcome\\":\\"returned\\",\\"value\\":" + GateAdapter.allowed(code) + "}";
    }

    public static void main(String[] args) throws Exception {
        %s
    }
}
"""
# Drivers that go wrong in each way a control can: none of them may give observations.
COMMIT = "0123456789abcdef0123456789abcdef01234567"


class Repository:
    """A local stand-in for Maven Central: {url: file}, served by runtime_maven.FETCH, every request counted."""

    def __init__(self, test, root):
        self.root, self.files, self.requests = Path(root), {}, []
        test.addCleanup(mock.patch.stopall)
        mock.patch.object(runtime_maven, "FETCH", self.fetch).start()
        mock.patch.object(runtime_maven, "CACHE", self.root / "cache").start()

    def publish(self, coords, source):
        url = runtime_maven.central_url(coords)
        self.files[url] = Path(source)
        return {"coordinates": coords, "url": url, "sha256": runtime.sha256(source)}

    def fetch(self, url, dest):
        self.requests.append(url)
        if url not in self.files:
            raise runtime_maven.Blocked("acquire", f"GET {url} failed: HTTP Error 404")
        shutil.copyfile(self.files[url], dest)


def dependency_jar(path, entries):
    """A JAR holding real class bytes under the given names (never loaded: only listed and hashed)."""
    import zipfile
    data = runtime_jar.read_class(Path(manifest()["dir"]) / "after.jar", "fixture/Gate")
    with zipfile.ZipFile(path, "w") as z:
        for name in entries:
            z.writestr(name + ".class", data)
    return path


def published_jars(original, dependencies, shape="published"):
    """A revision entry's JAR keys: workflow's W1 shape (`published`, in classpath order, a lone item's keys copied
    up), or the original's keys with `dependencies` beside them."""
    if shape == "published":
        return {"published": [original, *dependencies], **(original if not dependencies else {})}
    return {**original, "dependencies": list(dependencies)}


def published_plan(folder, revisions, items, task="replay", network=True, jdks=("21", "25"), shape="published"):
    """items: {revision: (original item, [dependency items])}."""
    artifacts = tuple({"revision": r, "route": "published-artifact", "repository": "https://github.com/pilifs/in-the-loop",
                       "commit": COMMIT, "tag": f"v-{r}", **published_jars(*items[r], shape=shape),
                       "adapters": ["gate/adapter/fixture/adapter/GateAdapter.java"], "jdks": list(jdks)}
                      for r in revisions)
    return interfaces.TaskPlan(
        example="999", task=task, kind="replay", relation="security", target="fixture.Gate#allowed(I)Z",
        revisions=tuple(revisions), claim={"task": task}, prerequisites=(), artifacts=artifacts,
        tools={"required": ["java", "javac"], "optional": []}, engine=None, gaps=None, expected=None,
        outputs={"receipts": f"receipts/{task}"}, folder=str(folder), network=network)


class PublishedTest(FixtureCopy):
    """R2's published-artifact route: build_fixtures.py's JARs published as fixture.example:gate:1.0 (before) and 1.1
    (after), with a dependency that holds a class of its own."""

    def setUp(self):
        super().setUp()
        self.repo = Repository(self, self.dir / "repo")
        jars = Path(manifest()["dir"])
        self.dep = self.repo.publish("fixture.example:gate-util:2.0",
                                     dependency_jar(self.dir / "util.jar", ["fixture/util/Helper"]))
        self.items = {"before": (self.repo.publish("fixture.example:gate:1.0", jars / "before.jar"), [self.dep]),
                      "after": (self.repo.publish("fixture.example:gate:1.1", jars / "after.jar"), [self.dep])}

    def plan(self, revisions=("after",), **kw):
        return published_plan(self.folder, revisions, self.items, **kw)

    def prepare(self, revision="after", workdir=None, plan=None):
        return runtime.prepare(plan or self.plan((revision,)), revision, workdir or self.work / revision)

    def test_a_published_lock_fetches_nothing_and_keeps_the_release_linkage_apart(self):
        with mock.patch.object(runtime_maven, "FETCH", side_effect=AssertionError("a source lock fetched")):
            locked = runtime.lock(self.plan(), "after")
        self.assertEqual((locked.stage, locked.commit), ("source-locked", COMMIT), locked.diagnostic)
        self.assertEqual([(i["coordinates"], i["role"]) for i in locked.source["published"]],
                         [("fixture.example:gate:1.1", "original"), ("fixture.example:gate-util:2.0", "dependency")])
        self.assertEqual(locked.source["linkage"]["tag"], "v-after")
        self.assertIn("not checked against the published bytes", locked.source["linkage"]["status"])
        self.assertEqual(locked.source["driver"]["main"], "fixture.driver.GateDriver")
        self.assertFalse((self.dir / "repo/cache").exists())

    def test_both_entry_shapes_lock_alike_and_a_mix_or_a_disagreement_is_refused(self):
        """W1's `published` list and the original-plus-`dependencies` shape give the same lock; one with a lone item
        copied up does too. Both lists at once, an empty list, or a copied-up key that isn't the list's first item's
        is refused at `lock`, never one of them silently preferred."""
        locked = {shape: runtime.lock(self.plan(shape=shape), "after") for shape in ("published", "dependencies")}
        self.assertEqual(locked["published"].stage, "source-locked", locked["published"].diagnostic)
        self.assertEqual(locked["published"], locked["dependencies"])
        lone = {"after": (self.items["after"][0], [])}
        self.assertEqual(runtime.lock(published_plan(self.folder, ("after",), lone), "after").stage, "source-locked")

        def refused(**change):
            entry = {**self.plan().artifacts[0], **change}
            return runtime.lock(dataclasses.replace(self.plan(), artifacts=(entry,)), "after")
        dep = self.items["after"][1]
        for change, says in (({"dependencies": dep}, "both `published` and `dependencies`"),
                             ({"published": []}, "not a non-empty list"),
                             ({"published": "gate.jar"}, "not a non-empty list"),
                             ({"sha256": self.dep["sha256"]}, "is not its first published JAR's")):
            with self.subTest(change=sorted(change)):
                r = refused(**change)
                self.assertEqual((r.stage, r.failedStage), ("failed", "lock"))
                self.assertIn(says, r.diagnostic)

    def test_artifacts_ready_records_each_jar_in_classpath_order_with_its_origin(self):
        prepared = self.prepare()
        self.assertEqual(prepared.stage, "artifacts-ready", prepared.diagnostic)
        self.assertEqual(prepared.classpath, ("driver.jar", "adapter-after.jar", "lib/fixture.example/gate-1.1.jar",
                                              "lib/fixture.example/gate-util-2.0.jar"))
        by_path = {a.path: a for a in prepared.artifacts}
        original = by_path["lib/fixture.example/gate-1.1.jar"]
        self.assertEqual((original.role, original.coordinates, original.sha256, original.origin),
                         ("original", "fixture.example:gate:1.1", manifest()["jars"]["after"]["sha256"],
                          self.items["after"][0]["url"]))
        self.assertEqual(by_path["lib/fixture.example/gate-util-2.0.jar"].role, "dependency")
        self.assertEqual(by_path["adapter-after.jar"].sha256, manifest()["jars"]["adapter-after"]["sha256"],
                         "the adapter compiled against the published JAR is not build_fixtures.py's")
        self.assertEqual(prepared.source["target"]["loadedFrom"], "lib/fixture.example/gate-1.1.jar")
        for a in prepared.artifacts:
            self.assertEqual(runtime.sha256(self.work / "after" / a.path), a.sha256, a.path)
        self.assertEqual(sorted(self.repo.requests), sorted([self.items["after"][0]["url"], self.dep["url"]]))
        self.assertIn("logs/acquire.log", prepared.logs)

    def test_a_second_preparation_is_a_rechecked_cache_hit_and_the_same_preparation(self):
        first = self.prepare(workdir=self.work / "one")
        self.repo.requests.clear()
        second = self.prepare(workdir=self.work / "two")
        self.assertEqual(self.repo.requests, [], "a cached artifact was fetched again")
        self.assertEqual(first, second, "a cache hit changed the preparation: reuse is not part of any identity")
        self.assertIn("cache hit", (self.work / "two/logs/acquire.log").read_text())

    def test_a_corrupt_cache_entry_is_moved_aside_and_fetched_again(self):
        self.prepare(workdir=self.work / "one")
        cached = runtime_maven.Cache().path(self.items["after"][0]["sha256"])
        cached.write_bytes(b"not the jar")
        self.repo.requests.clear()
        prepared = self.prepare(workdir=self.work / "two")
        self.assertEqual(prepared.stage, "artifacts-ready", prepared.diagnostic)
        self.assertEqual(self.repo.requests, [self.items["after"][0]["url"]])
        self.assertIn("moved aside", (self.work / "two/logs/acquire.log").read_text())
        self.assertEqual(runtime.sha256(cached), self.items["after"][0]["sha256"])

    def test_bytes_that_differ_from_the_lock_are_refused_never_cached_or_used(self):
        self.repo.files[self.items["after"][0]["url"]] = Path(manifest()["dir"]) / "before.jar"
        prepared = self.prepare()
        self.assertEqual((prepared.stage, prepared.failedStage), ("failed", "acquire"))
        self.assertIn("not the recorded", prepared.diagnostic)
        self.assertEqual(prepared.artifacts, ())
        self.assertFalse(runtime_maven.Cache().path(manifest()["jars"]["before"]["sha256"]).exists())
        blocker = prepared.source["blocker"]
        self.assertEqual(blocker["command"], f"GET {self.items['after'][0]['url']}")
        self.assertTrue(blocker["needs"] and blocker["next"] and blocker["diagnostic"] == prepared.diagnostic)

    def test_a_missing_hash_or_a_dynamic_version_blocks_the_lock_with_the_command_that_pins_it(self):
        original = dict(self.items["after"][0])
        cases = {"missing": dict(original, sha256=None),
                 "snapshot": dict(original, coordinates="fixture.example:gate:1.1-SNAPSHOT", url=None),
                 "range": dict(original, coordinates="fixture.example:gate:[1.0,2.0)", url=None),
                 "plus": dict(original, coordinates="fixture.example:gate:1.+", url=None),
                 "latest": dict(original, coordinates="fixture.example:gate:LATEST", url=None),
                 "elsewhere": dict(original, url="https://example.com/maven2/gate-1.1.jar"),
                 "http": dict(original, url=original["url"].replace("https:", "http:")),
                 "other-file": dict(original, url=runtime_maven.central_url("fixture.example:gate:1.0"))}
        for name, item in cases.items():
            self.items["after"] = (item, [self.dep])
            prepared = self.prepare()
            self.assertEqual((prepared.stage, prepared.failedStage), ("failed", "lock"), name)
            self.assertEqual(self.repo.requests, [], name)
            self.assertTrue(set(prepared.source["blocker"]) >= {"command", "diagnostic", "needs", "next"}, name)
        self.items["after"] = (dict(original, sha256=None), [self.dep])
        blocker = self.prepare().source["blocker"]
        self.assertEqual(blocker["command"], runtime_maven.pin_command("fixture.example:gate:1.1"))
        self.assertIn("no recorded sha256", blocker["diagnostic"])

    def test_a_dependency_that_repeats_a_class_is_refused_as_shadowing(self):
        clash = self.repo.publish("fixture.example:gate-copy:1.0",
                                  dependency_jar(self.dir / "copy.jar", ["fixture/Gate"]))
        self.items["after"] = (self.items["after"][0], [self.dep, clash])
        prepared = self.prepare()
        self.assertEqual((prepared.stage, prepared.failedStage), ("failed", "classpath"))
        self.assertIn("fixture.Gate in lib/fixture.example/gate-1.1.jar, lib/fixture.example/gate-copy-1.0.jar",
                      prepared.diagnostic)
        self.assertTrue({a.role for a in prepared.artifacts} >= {"original", "dependency", "adapter"})

    def test_without_acquisition_in_the_plan_only_the_cache_is_used(self):
        refused = self.prepare(plan=self.plan(network=False))
        self.assertEqual((refused.failedStage, self.repo.requests), ("acquire", []))
        self.assertIn("network: false", refused.diagnostic)
        self.prepare(workdir=self.work / "fetched")
        self.repo.requests.clear()
        cached = self.prepare(workdir=self.work / "cached", plan=self.plan(network=False))
        self.assertEqual((cached.stage, self.repo.requests), ("artifacts-ready", []), cached.diagnostic)

    def test_each_published_revision_runs_in_its_own_jvm(self):
        if not {"21", "25"} <= set(runtime_jdk.homes()):
            self.skipTest(f"JDKs 21 and 25 are not both under {runtime_jdk.CANDIDATES}")
        plan = self.plan(("before", "after"))
        attempt = self.work / "attempt"
        prepared = {r: runtime.prepare(plan, r, attempt / "prepare" / r) for r in plan.revisions}
        records = runtime.run_controls(plan, prepared, attempt / "controls")
        self.assertEqual([(r.revision, r.identities["jdkFeature"], r.status, r.exitCode) for r in records],
                         [("before", "21", "exited", 0), ("before", "25", "exited", 0),
                          ("after", "21", "exited", 0), ("after", "25", "exited", 0)])
        problems = {}
        for r in records:
            self.assertIsNotNone(r.observations, r)
            self.assertEqual(r.identities["replay"], "original-jvm")
            self.assertIn({"path": "lib/fixture.example/gate-util-2.0.jar", "sha256": self.dep["sha256"],
                           "role": "dependency"}, r.identities["classpath"])
            problems.setdefault(r.revision, set()).add(
                tuple(c for c, _ in oracle().check([json.dumps(o) for o in r.observations])))
        self.assertEqual(problems, {"before": {(97,)}, "after": {()}}, "the published JARs replay as the fixture's")


class MavenTest(unittest.TestCase):
    def test_coordinates_and_urls(self):
        self.assertEqual(runtime_maven.central_url("org.springframework:spring-core:5.3.18"),
                         "https://repo.maven.apache.org/maven2/org/springframework/spring-core/5.3.18/"
                         "spring-core-5.3.18.jar")
        for bad in ("a:b", "a:b:c:d", "a:b:1.0-SNAPSHOT", "a:b:[1,2)", "a:b:1.+", "a:b:LATEST", "a:b:RELEASE", None):
            with self.assertRaises(runtime_maven.Blocked, msg=bad):
                runtime_maven.coordinates(bad)
        for url in ("https://repo.maven.apache.org/maven2/x", "https://github.com/o/r/releases/download/v1/x.jar"):
            self.assertTrue(runtime_maven.allowed(url), url)
        for url in ("http://repo.maven.apache.org/maven2/x", "https://repo1.maven.org/maven2/x",
                    "https://user@github.com/x", "https://github.com:8443/x", "file:///etc/passwd"):
            self.assertFalse(runtime_maven.allowed(url), url)
        self.assertFalse(runtime_maven.allowed("https://objects.githubusercontent.com/x"))
        self.assertTrue(runtime_maven.allowed("https://objects.githubusercontent.com/x", runtime_maven.REDIRECT_HOSTS))

    def test_pin_checks_centrals_sha1_and_caches_the_bytes(self):
        root = Path(tempfile.mkdtemp(prefix="test-runtime-"))
        self.addCleanup(shutil.rmtree, root, True)
        jar = Path(manifest()["dir"]) / "after.jar"
        import hashlib
        files = {runtime_maven.central_url("g.x:a:1.0"): jar.read_bytes(),
                 runtime_maven.central_url("g.x:a:1.0") + ".sha1": hashlib.sha1(jar.read_bytes()).hexdigest().encode()}
        fetch = lambda url, dest: Path(dest).write_bytes(files[url])
        cache = runtime_maven.Cache(root)
        entry = runtime_maven.pin("g.x:a:1.0", cache, fetch)
        self.assertEqual(entry["sha256"], runtime.sha256(jar))
        self.assertTrue(cache.path(entry["sha256"]).is_file())
        files[runtime_maven.central_url("g.x:a:1.0") + ".sha1"] = b"0" * 40
        with self.assertRaises(runtime_maven.Blocked):
            runtime_maven.pin("g.x:a:1.0", runtime_maven.Cache(root / "other"), fetch)
        self.assertEqual(list((root / "tmp").iterdir()), [], "a scratch directory was left behind")


BAD_DRIVERS = {
    "killed": 'System.out.println(line(args[0])); System.out.flush(); new ProcessBuilder("/bin/kill", "-KILL", '
              'String.valueOf(ProcessHandle.current().pid())).start().waitFor(); Thread.sleep(60000);',
    "timed-out": "System.out.println(line(args[0])); System.out.flush(); Thread.sleep(60000);",
    "malformed": 'for (String a : args) System.out.println(line(a)); System.out.println("{\\"input\\":");',
    "incomplete": "for (int i = 0; i + 1 < args.length; i++) System.out.println(line(args[i]));",
    "exit-one": "for (String a : args) System.out.println(line(a)); System.exit(1);",
}


def pair_plan(folder, revisions=("before", "after"), task="replay", jdks=("21", "25")):
    artifacts = tuple({"revision": r, "route": "fixture", "repository": "https://github.com/pilifs/in-the-loop",
                       "fixture": f"gate/{r}", "adapters": ["gate/adapter/fixture/adapter/GateAdapter.java"],
                       "jdks": list(jdks)} for r in revisions)
    return interfaces.TaskPlan(
        example="999", task=task, kind="replay", relation="security", target="fixture.Gate#allowed(I)Z",
        revisions=tuple(revisions), claim={"task": task}, prerequisites=(), artifacts=artifacts,
        tools={"required": ["java", "javac"], "optional": []}, engine=None, gaps=None, expected=None,
        outputs={"receipts": f"receipts/{task}"}, folder=str(folder))


def oracle():
    import importlib.util
    spec = importlib.util.spec_from_file_location("fixture_oracle", FIXTURES / "gate/oracle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ControlsTest(FixtureCopy):
    """R4: the attempt directory is route.py's, <attempt>/prepare/<revision> and <attempt>/controls."""

    def setUp(self):
        super().setUp()
        if not {"21", "25"} <= set(runtime_jdk.homes()):
            self.skipTest(f"JDKs 21 and 25 are not both under {runtime_jdk.CANDIDATES}")
        self.attempt = self.work / "attempt"

    def controls(self, plan=None, prepared=None, revisions=("before", "after")):
        plan = plan or pair_plan(self.folder, revisions)
        if prepared is None:
            prepared = {r: runtime.prepare(plan, r, self.attempt / "prepare" / r) for r in revisions}
            for r, p in prepared.items():
                self.assertEqual(p.stage, "artifacts-ready", p.diagnostic)
        return plan, prepared, runtime.run_controls(plan, prepared, self.attempt / "controls")

    def stderr(self, record):
        return (self.attempt / record.stderr).read_text()

    def test_each_revision_runs_in_its_own_jvm_on_each_jdk_with_its_identities(self):
        plan, prepared, records = self.controls()
        self.assertEqual([(r.revision, r.identities["jdkFeature"]) for r in records],
                         [("before", "21"), ("before", "25"), ("after", "21"), ("after", "25")])
        recorded = {}
        for r in json.loads((FIXTURES / "records/controls.json").read_text())["records"]:
            recorded.setdefault(r["revision"], r["observations"])
        jars = manifest()["jars"]
        problems = {}
        for r in records:
            self.assertEqual((r.kind, r.status, r.exitCode, r.control), ("jvm-control", "exited", 0, "gate-driver"), r)
            self.assertEqual(r.argv[0], str(Path(runtime_jdk.home(r.identities["jdkFeature"])) / "bin/java"))
            self.assertNotIn("current", Path(r.identities["jdkHome"]).parts)
            self.assertEqual(r.argv[r.argv.index("-cp") + 1], f"driver.jar:adapter-{r.revision}.jar:{r.revision}.jar")
            self.assertEqual([c["sha256"] for c in r.identities["classpath"]],
                             [jars["driver"]["sha256"], jars[f"adapter-{r.revision}"]["sha256"], jars[r.revision]["sha256"]])
            self.assertEqual(r.identities["replay"], "original-jvm")
            self.assertEqual(r.identities["environment"], runtime.CONTROL_ENV)
            self.assertEqual(list(r.observations), recorded[r.revision], "not the outcomes Phase 0 recorded")
            self.assertEqual((self.attempt / r.stdout).read_text().count("\n"), len(oracle().PROBES))
            self.assertTrue(r.stdout.startswith("controls/"), r.stdout)
            problems.setdefault(r.revision, set()).add(
                tuple(c for c, _ in oracle().check([json.dumps(o) for o in r.observations])))
        self.assertEqual(len({r.identities["jdk"] for r in records}), 2)
        self.assertEqual(problems, {"before": {(97,)}, "after": {()}})
        written = json.loads((self.attempt / "controls" / runtime.CONTROLS).read_text())
        self.assertEqual([w["status"] for w in written["records"]], ["exited"] * 4)

    def test_the_jvm_inherits_no_options_from_the_caller(self):
        with mock.patch.dict(os.environ, {"JAVA_TOOL_OPTIONS": "-Dinjected=1", "CLASSPATH": "/nowhere"}):
            _, _, records = self.controls(revisions=("after",))
        for r in records:
            self.assertEqual((r.status, r.exitCode), ("exited", 0))
            self.assertNotIn("Picked up", self.stderr(r))

    def test_a_revision_not_prepared_is_a_not_started_record_never_skipped(self):
        plan = pair_plan(self.folder)
        before = runtime.prepare(plan, "before", self.attempt / "prepare" / "before")
        _, _, records = self.controls(plan, {"before": before})
        after = [r for r in records if r.revision == "after"]
        self.assertEqual([r.status for r in after], ["not-started"] * 2)
        self.assertTrue(all(r.observations is None for r in after))
        self.assertIn("one-sided", self.stderr(after[0]))
        self.assertEqual([r.status for r in records if r.revision == "before"], ["exited"] * 2)

    def test_a_failed_preparation_is_not_run(self):
        (self.folder / "gate/after/fixture/Gate.java").write_text("package fixture; public final class Gate { oops }\n")
        plan = pair_plan(self.folder, ("after",))
        failed = runtime.prepare(plan, "after", self.attempt / "prepare" / "after")
        self.assertEqual(failed.stage, "failed")
        _, _, records = self.controls(plan, {"after": failed}, ("after",))
        self.assertEqual({r.status for r in records}, {"not-started"})
        self.assertIn("not artifacts-ready", self.stderr(records[0]))

    def test_bytes_changed_since_preparation_are_not_run(self):
        plan = pair_plan(self.folder, ("after",))
        prepared = {"after": runtime.prepare(plan, "after", self.attempt / "prepare" / "after")}
        shutil.copyfile(Path(manifest()["dir"]) / "before.jar", self.attempt / "prepare/after/after.jar")  # the vulnerable bytes
        _, _, records = self.controls(plan, prepared, ("after",))
        self.assertEqual({r.status for r in records}, {"not-started"})
        self.assertIn("stale or changed bytes", self.stderr(records[0]))

    def test_a_preparation_other_than_the_one_given_is_not_run(self):
        plan = pair_plan(self.folder, ("after",))
        prepared = runtime.prepare(plan, "after", self.attempt / "prepare" / "after")
        _, _, records = self.controls(plan, {"after": dataclasses.replace(prepared, commit="fixture:gate/elsewhere")}, ("after",))
        self.assertEqual({r.status for r in records}, {"not-started"})
        self.assertIn("is not the preparation given", self.stderr(records[0]))

    def test_a_missing_jdk_or_one_too_old_for_the_classes_is_not_started(self):
        jdks = ("99",) + (("17",) if runtime_jdk.home("17") else ())
        plan = pair_plan(self.folder, ("after",), jdks=jdks)
        _, _, records = self.controls(plan, revisions=("after",))
        self.assertEqual([r.status for r in records], ["not-started"] * len(jdks))
        self.assertIn("no JDK 99", self.stderr(records[0]))
        if len(jdks) > 1:
            self.assertIn("need Java 21", self.stderr(records[1]))
            self.assertEqual(records[1].identities["jdkFeature"], "17")

    def test_a_kill_a_timeout_and_unreadable_output_give_no_observations(self):
        expected = {"killed": ("killed", -9), "timed-out": ("timed-out", None), "malformed": ("exited", 0),
                    "incomplete": ("exited", 0), "exit-one": ("exited", 1)}
        for name, body in BAD_DRIVERS.items():
            with self.subTest(name):
                (self.folder / "gate/driver/fixture/driver/GateDriver.java").write_text(DRIVER % body)
                self.attempt = self.work / name
                plan = pair_plan(self.folder, ("after",), jdks=("25",))
                with mock.patch.object(runtime, "CONTROL_TIMEOUT", 3):
                    _, _, [record] = self.controls(plan, revisions=("after",))
                self.assertEqual((record.status, record.exitCode), expected[name], self.stderr(record))
                if name == "exit-one":  # complete output: raw, with its exit code; ingestion decides
                    self.assertEqual(len(record.observations), len(oracle().PROBES))
                else:
                    self.assertIsNone(record.observations, name)
                    self.assertTrue((self.attempt / record.stdout).read_text(), "the partial output is kept")
                log = json.loads((self.attempt / "controls" / runtime.CONTROLS).read_text())["records"][0]["log"]
                self.assertEqual(bool(log.get("problem")), name != "exit-one", log)

    def test_a_work_directory_that_is_not_ours_is_unsupported_not_a_stub(self):
        (self.attempt / "controls").mkdir(parents=True)
        (self.attempt / "controls/notes.txt").write_text("mine")
        value = runtime.run_controls(pair_plan(self.folder), {}, self.attempt / "controls")
        self.assertTrue(interfaces.unsupported(value))
        self.assertEqual((value.interface, value.stage), ("run-controls", "workdir"))
        self.assertNotIn(STUB, value.reason)
        self.assertEqual((self.attempt / "controls/notes.txt").read_text(), "mine")


class SliceTest(unittest.TestCase):
    """R5's slice, runtime_slice.py on runtime_simplematch/: PatternMatchUtils.simpleMatch from the published
    spring-core 5.3.18 and 5.3.19 JARs. Nothing here fetches: the end-to-end test runs from a private copy of the four
    JARs' cache entries, and is skipped when the acquisition cache doesn't hold them (`runtime_slice.py ATTEMPT`, with
    the network, fills it)."""

    def setUp(self):
        import runtime_slice
        self.slice = runtime_slice
        self.dir = Path(tempfile.mkdtemp(prefix="test-runtime-slice-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(runtime_maven, "FETCH", side_effect=AssertionError("the slice's tests fetched")).start()
        self.target = json.loads((runtime_slice.FOLDER / "target.json").read_text())

    def private_cache(self):
        """The four JARs' entries copied from the acquisition cache into one of the test's own, or a skip."""
        real, cache = runtime_maven.Cache(), self.dir / "cache"
        for a in self.target["preparation"]["artifacts"]:
            if not real.path(a["sha256"]).is_file():
                self.skipTest(f"the acquisition cache holds no {a['coordinates']} (run runtime_slice.py with the network)")
            runtime_maven.Cache(cache).store(real.path(a["sha256"]), a["sha256"])
        mock.patch.object(runtime_maven, "CACHE", cache).start()
        return cache

    def test_the_sidecar_is_valid_and_its_plan_locks_both_releases_offline(self):
        from targets import sidecar
        sidecar.check(self.target, self.slice.FOLDER)
        p = self.slice.plan(network=False)
        self.assertEqual((p.example, p.kind, p.revisions), ("315", "replay", ("r5-3-18", "r5-3-19")))
        for revision, version, commit in (("r5-3-18", "5.3.18", "707a24c48b21fc35e8be715afc80f020a24a9714"),
                                          ("r5-3-19", "5.3.19", "cedb5874b72c3311c8c6e2f03a53537590f2e0dc")):
            locked = runtime.lock(p, revision)
            self.assertEqual((locked.stage, locked.commit), ("source-locked", commit), locked.diagnostic)
            self.assertEqual([(i["coordinates"], i["role"]) for i in locked.source["published"]],
                             [(f"org.springframework:spring-core:{version}", "original"),
                              (f"org.springframework:spring-jcl:{version}", "dependency")])
            self.assertEqual(locked.source["linkage"]["tag"], f"v{version}")
            self.assertEqual(locked.source["driver"]["main"], "slice.driver.SimpleMatchDriver")

    def test_offline_with_nothing_cached_is_a_blocker_at_acquire_with_its_next_action(self):
        mock.patch.object(runtime_maven, "CACHE", self.dir / "empty").start()
        p = self.slice.plan(network=False)
        prepared = runtime.prepare(p, "r5-3-18", self.dir / "attempt/prepare/r5-3-18")
        self.assertEqual((prepared.stage, prepared.failedStage), ("failed", "acquire"))
        blocker = prepared.source["blocker"]
        self.assertIn("network", blocker["diagnostic"])
        self.assertTrue(blocker["command"] and blocker["needs"] and blocker["next"], blocker)

    def test_the_oracle_is_not_vacuous(self):
        """The statement disagrees with plausible wrong implementations on some probe, and a missing probe is a replay
        problem, never a pass."""
        oracle = self.slice._oracle(self.slice.FOLDER / "oracle.py")
        import re as _re

        def lines(decide):
            return [json.dumps({"input": p, "outcome": "returned", "value": decide(*p)}) for p in oracle.PROBES]

        def glob(pattern, text, flags=_re.DOTALL):
            if pattern is None or text is None:
                return False
            return _re.fullmatch("".join(".*" if c == "*" else _re.escape(c) for c in pattern), text, flags) is not None
        wrong = {
            "case-insensitive": lambda p, t: glob(p, t, _re.DOTALL | _re.IGNORECASE),
            "no line breaks under *": lambda p, t: glob(p, t, 0),
            "null matches null": lambda p, t: (p is None and t is None) or glob(p, t),
            "the pattern as a regex": lambda p, t: p is not None and t is not None
            and _re.fullmatch(p.replace("*", ".*"), t, _re.DOTALL) is not None,
            "prefix only": lambda p, t: p is not None and t is not None and t.startswith(p.split("*")[0]),
        }
        self.assertEqual(oracle.check(lines(oracle.expected)), [])
        for name, decide in wrong.items():
            self.assertTrue(oracle.check(lines(decide)), f"the oracle accepts the {name} implementation")
        with self.assertRaises(ValueError):
            oracle.check(lines(oracle.expected)[:-1])

    def test_the_slice_runs_both_published_releases_end_to_end_from_the_cache(self):
        self.private_cache()
        summary = self.slice.run(self.dir / "attempt", network=False)
        self.assertTrue(summary["ok"], json.dumps(summary, indent=1)[:3000])
        for p in summary["preparations"]:
            self.assertEqual(p["stage"], "artifacts-ready", p)
            self.assertEqual(p["target"]["loadedFrom"], f"lib/org.springframework/spring-core-{p['revision'][1:].replace('-', '.')}.jar")
            self.assertEqual(sorted(c["role"] for c in p["classpath"]), ["adapter", "dependency", "driver", "original"])
            self.assertTrue(all(c["origin"].startswith("https://repo.maven.apache.org/") for c in p["classpath"]
                                if c["role"] in ("original", "dependency")))
        oracle = self.slice._oracle(self.slice.FOLDER / "oracle.py")
        self.assertEqual([(r["revision"], r["jdk"], r["status"], r["observations"], r["problems"], r["replay"])
                          for r in summary["records"]],
                         [(rev, jdk, "exited", len(oracle.PROBES), [], "original-jvm")
                          for rev in ("r5-3-18", "r5-3-19") for jdk in ("21", "25")])
        self.assertEqual(summary["jdksAgree"], {"r5-3-18": True, "r5-3-19": True})
        # the records reach workflow's ingestion interface, which is Phase 0's stub until W2
        self.assertEqual(summary["ingestion"]["records"], 4)
        self.assertIn("ingest (example-targets-workflow)", summary["ingestion"]["result"])
        record = json.loads((self.dir / "attempt/controls/controls.json").read_text())["records"][0]
        self.assertEqual(list(record)[:len(interfaces.ExecutionRecord.__dataclass_fields__)],
                         list(interfaces.ExecutionRecord.__dataclass_fields__))


class ParameterNamesTest(unittest.TestCase):
    """runtime_jar.parameter_names reads what jvmcontract reads: MethodParameters, else the LocalVariableTable (with
    long and double taking two slots, and an instance method's receiver in slot 0), else arg0, arg1, ..."""

    SOURCE = ("package p; public class A { public static boolean f(int code, long w, String s, int[][] a) "
              "{ return code > 0; } public boolean g(double d, int x) { return x > 0; } }")

    def test_each_way_a_class_records_names_or_none(self):
        home = runtime_jdk.homes().get("25") or next(iter(runtime_jdk.homes().values()), None)
        if home is None:
            self.skipTest("no JDK")
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "A.java").write_text(self.SOURCE)
            for flag, f, g in (([], (["arg0", "arg1", "arg2", "arg3"], None), (["arg0", "arg1"], None)),
                               (["-g"], (["code", "w", "s", "a"], "LocalVariableTable"), (["d", "x"], "LocalVariableTable")),
                               (["-parameters"], (["code", "w", "s", "a"], "MethodParameters"), (["d", "x"], "MethodParameters"))):
                out = Path(d) / f"out{len(flag)}{flag[:1]}"
                subprocess.run([str(Path(home) / "bin/javac"), *flag, "-d", str(out), str(Path(d) / "A.java")], check=True)
                data = (out / "p/A.class").read_bytes()
                self.assertEqual(runtime_jar.parameter_names(data, "f", "(IJLjava/lang/String;[[I)Z"), f, flag)
                self.assertEqual(runtime_jar.parameter_names(data, "g", "(DI)Z"), g, flag)
                self.assertIsNone(runtime_jar.parameter_names(data, "h", "()V"), "a method the class doesn't declare")


FAKE_JVMCONTRACT = """#!{python}
# A stand-in for jvmcontract in these tests: it records its argv, cwd and environment, then answers as mode.json says
# for its subcommand. It proves nothing; the real verifier runs as a pipeline job (runtime_calibrate.py).
import json, os, sys, time
from pathlib import Path
here = Path(__file__).resolve().parent
with open(here / "calls.jsonl", "a") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd(), "env": dict(os.environ)}}) + "\\n")
answer = json.loads((here / "mode.json").read_text()).get(sys.argv[1], {{}})
sys.stdout.write(answer.get("stdout", ""))
sys.stderr.write(answer.get("stderr", ""))
sys.stdout.flush()
if answer.get("sleep"):
    time.sleep(answer["sleep"])
if answer.get("kill"):
    os.kill(os.getpid(), 9)
sys.exit(answer.get("exit", 0))
"""
PROVE_OUT = [{"verdict": "violation", "output": "✗ Violation: allowed(97) is true\n", "counterexample": {"code": 97}}]
EQUIVALENCE_OUT = {"verdict": "verified", "output": "✓ Verified\n"}
GAPS_OUT = {"roots": ["fixture.Gate#allowed(int)"], "gaps": [
    {"id": "jdk-method:x", "kind": "jdk-method", "call": "java.util.regex.Pattern.matcher(java.lang.CharSequence)",
     "sites": ["fixture.Gate.allowed:3"], "approximation": "dropped from the record"}]}
SECURITY_CLAIM = {"assert": "!result || (code != 65 && code != 97)", "throws": [], "nullable": [], "mayAlias": [],
                  "bounds": {"unwind": 16, "maxArrayLength": 8}, "models": [], "plan": None, "contracts": None,
                  "assumptions": ["stated for the test"]}


def verifier_plan(folder, kind="prove", revisions=("after",), engine="native", gaps="strict", **claim):
    artifacts = tuple({"revision": r, "route": "fixture", "repository": "https://github.com/pilifs/in-the-loop",
                       "fixture": f"gate/{r}", "adapters": ["gate/adapter/fixture/adapter/GateAdapter.java"],
                       "jdks": ["21", "25"]} for r in revisions)
    task = "fixed-security" if kind == "prove" else "preservation"
    return interfaces.TaskPlan(
        example="999", task=task, kind=kind, relation="security", target="fixture.Gate#allowed(I)Z",
        revisions=tuple(revisions), claim={"task": task, **SECURITY_CLAIM, **claim}, prerequisites=(),
        artifacts=artifacts, tools={"required": ["java", "javac", "jvmcontract"], "optional": []}, engine=engine,
        gaps=gaps, expected="established", outputs={"receipts": f"receipts/{task}"}, folder=str(folder))


class VerifierTest(FixtureCopy):
    """R3: run_verifier on route.py's attempt layout, with a stand-in jvmcontract (no proof runs inline)."""

    def setUp(self):
        super().setUp()
        if "25" not in runtime_jdk.homes():
            self.skipTest(f"JDK 25 is not under {runtime_jdk.CANDIDATES}")
        self.attempt = self.work / "attempt"
        self.tool = self.dir / "tool"
        self.tool.mkdir()
        exe = self.tool / "jvmcontract"
        exe.write_text(FAKE_JVMCONTRACT.format(python=sys.executable))
        exe.chmod(0o755)
        self.answer(prove={"stdout": json.dumps(PROVE_OUT), "exit": 1})
        patch = mock.patch.dict(os.environ, {"JVMCONTRACT": str(exe), "JAVA_TOOL_OPTIONS": "-Dinherited=yes",
                                             "JVMCONTRACT_JAVA_OPTS": "-Xmx300m"})
        patch.start()
        self.addCleanup(patch.stop)

    def answer(self, **commands):
        commands.setdefault("gaps", {"stdout": json.dumps(GAPS_OUT)})
        commands.setdefault("equivalence", {"stdout": json.dumps(EQUIVALENCE_OUT)})
        (self.tool / "mode.json").write_text(json.dumps(commands))

    def calls(self):
        f = self.tool / "calls.jsonl"
        return [json.loads(line) for line in f.read_text().splitlines()] if f.is_file() else []

    def verify(self, plan, prepared=None, prepare=None):
        if prepared is None:
            prepared = {r: runtime.prepare(plan, r, self.attempt / "prepare" / r) for r in (prepare or plan.revisions)}
            for r, p in prepared.items():
                self.assertEqual(p.stage, "artifacts-ready", p.diagnostic)
        return prepared, runtime.run_verifier(plan, prepared, self.attempt / "verifier")

    def test_a_property_runs_on_the_original_artifact_alone_with_the_plans_engine_gaps_and_bounds(self):
        prepared, record = self.verify(verifier_plan(self.folder))
        self.assertIsInstance(record, interfaces.ExecutionRecord)
        self.assertEqual((record.kind, record.revision, record.status, record.exitCode), ("verifier", "after", "exited", 1))
        self.assertEqual(record.observations, tuple(PROVE_OUT), "the --json outcome is the observation, kept raw")
        argv = list(record.argv)
        self.assertEqual(argv[1:5], ["prove", "fixture.Gate#allowed(int)", "--classes", "prepare/after/after.jar"])
        self.assertEqual(argv[argv.index("--assert") + 1], "!result || (code != 65 && code != 97)")
        for flag, value in (("--engine", "native"), ("--gaps", "strict"), ("--unwind", "16"), ("--max-array-length", "8"),
                            ("--timeout", str(runtime.VERIFIER_TIMEOUT)), ("--work", "verifier/work")):
            self.assertEqual(argv[argv.index(flag) + 1], value, flag)
        self.assertEqual(argv[-1], "--json")
        self.assertFalse([a for a in argv if "adapter" in a or "driver" in a], "the adapter or driver reached the verifier")
        self.assertNotIn("--classpath", argv, "the fixture has no dependencies")
        [probe, prove] = self.calls()
        self.assertEqual(probe["argv"][:2], ["gaps", "--target"])
        self.assertEqual(prove["argv"], argv[1:])
        self.assertEqual(Path(prove["cwd"]), self.attempt.resolve(), "paths are relative to the attempt directory")
        jdk = runtime_jdk.identity(runtime_jdk.home("25"))
        self.assertEqual(set(prove["env"]) - {"LC_CTYPE"},  # LC_CTYPE: Python's own locale coercion, if any
                         {"LANG", "LC_ALL", "TZ", "JAVA_HOME", "PATH", "JVMCONTRACT_JAVA_OPTS"})
        self.assertNotIn("JAVA_TOOL_OPTIONS", prove["env"], "the verifier inherited the caller's JVM options")
        self.assertEqual(prove["env"]["JAVA_HOME"], jdk["home"])
        self.assertEqual(prove["env"]["JVMCONTRACT_JAVA_OPTS"], "-Xmx300m", "the runner's memory setting passes through")
        ids = record.identities
        self.assertEqual(ids["jvmcontract"], runtime.sha256(self.tool / "jvmcontract"))
        self.assertEqual((ids["jdkFeature"], ids["engine"], ids["gaps"]), ("25", "native", "strict"))
        after = prepared["after"]
        self.assertEqual(ids["classpath"]["after"], [{"path": "after.jar", "role": "original",
                                                      "sha256": next(a.sha256 for a in after.artifacts if a.path == "after.jar")}])
        scope = ids["scope"]
        self.assertEqual(scope["label"], "constructed-fixture")
        self.assertEqual(scope["revisions"]["after"]["loadedFrom"], "after.jar")
        self.assertEqual(scope["revisions"]["after"]["classSha256"], after.source["target"]["classSha256"])
        self.assertEqual(scope["assumptions"], ["stated for the test"])
        self.assertIn("not on the verifier's classpath", scope["adapter"])
        names = scope["revisions"]["after"]["parameters"]
        self.assertEqual(names["names"], ["arg0"], "Phase 0's recipe records no parameter names")
        self.assertIn("records no parameter names", names["recordedIn"])
        self.assertEqual(ids["probe"]["after"]["gaps"][0]["call"], GAPS_OUT["gaps"][0]["call"])
        self.assertEqual(ids["probe"]["after"]["argv"][-1], "--json")
        stored = json.loads((self.attempt / "verifier" / runtime.VERIFIER).read_text())
        self.assertEqual(stored["record"], json.loads(json.dumps(record.as_dict())))
        self.assertEqual((self.attempt / record.stdout).read_text(), json.dumps(PROVE_OUT))

    def test_a_preservation_task_runs_equivalence_between_the_pairs_originals(self):
        plan = verifier_plan(self.folder, kind="equivalence", revisions=("before", "after"), allowedChange="code == 97",
                             **{"assert": None})
        _, record = self.verify(plan)
        self.assertEqual((record.revision, record.status, record.exitCode), (None, "exited", 0))
        self.assertEqual(record.observations, (EQUIVALENCE_OUT,), "equivalence's one outcome")
        argv = list(record.argv)
        self.assertEqual(argv[1:8], ["equivalence", "--before", "verifier/classes/before", "--after",
                                     "verifier/classes/after", "--target", "fixture.Gate#allowed(int)"],
                         "equivalence takes directories of classes, not JARs (VF-024)")
        self.assertEqual(argv[argv.index("--unchanged-unless") + 1], "code == 97")
        self.assertNotIn("--assert", argv)
        for r in ("before", "after"):
            extracted = record.identities["classes"][r]
            jar = self.attempt / "prepare" / r / f"{r}.jar"
            self.assertEqual((extracted["dir"], extracted["from"], extracted["sha256"]),
                             (f"verifier/classes/{r}", f"prepare/{r}/{r}.jar", runtime.sha256(jar)))
            self.assertEqual(runtime_jar.classes(jar), {
                f.relative_to(self.attempt / extracted["dir"]).as_posix()[:-6]: runtime.sha256(f)
                for f in (self.attempt / extracted["dir"]).rglob("*.class")}, "the directory is the JAR's classes, byte for byte")
        self.assertEqual(set(record.identities["probe"]), {"before", "after"})
        self.assertEqual(set(record.identities["commits"]), {"before", "after"})

    def test_a_one_sided_stale_or_failed_preparation_is_a_not_started_record_and_runs_nothing(self):
        pair = verifier_plan(self.folder, kind="equivalence", revisions=("before", "after"))
        _, one_sided = self.verify(pair, prepare=("after",))
        self.assertEqual((one_sided.status, one_sided.exitCode, one_sided.observations), ("not-started", None, None))
        self.assertIn("one-sided", (self.attempt / one_sided.stderr).read_text())
        prepared, _ = self.verify(verifier_plan(self.folder))
        (self.attempt / "prepare/after/after.jar").write_bytes(b"changed")
        stale = runtime.run_verifier(verifier_plan(self.folder), prepared, self.attempt / "verifier")
        self.assertEqual(stale.status, "not-started")
        self.assertIn("stale or changed bytes", (self.attempt / stale.stderr).read_text())
        failed = dataclasses.replace(prepared["after"], stage="failed", failedStage="build", diagnostic="no")
        record = runtime.run_verifier(verifier_plan(self.folder), {"after": failed}, self.attempt / "verifier")
        self.assertEqual(record.status, "not-started")
        self.assertEqual([c["argv"][0] for c in self.calls()], ["gaps", "prove"], "only the first, sound run started")

    def test_a_kill_a_timeout_and_output_that_is_not_the_outcome_give_no_observations(self):
        plan = verifier_plan(self.folder)
        prepared, _ = self.verify(plan)
        cases = {"killed": {"kill": True, "stdout": json.dumps(PROVE_OUT)},
                 "exited": {"stdout": "✗ Violation (no --json)\n", "exit": 1},
                 "timed-out": {"sleep": 30, "stdout": json.dumps(PROVE_OUT)}}
        for status, answer in cases.items():
            self.answer(prove=answer)
            with mock.patch.object(runtime, "VERIFIER_TIMEOUT", 0), mock.patch.object(runtime, "VERIFIER_GRACE", 2):
                record = runtime.run_verifier(plan, prepared, self.attempt / "verifier")
            self.assertEqual((record.status, record.observations), (status, None), status)
            self.assertNotEqual(record.exitCode, 0, status)
        self.answer(prove={"stdout": json.dumps(PROVE_OUT[0]), "exit": 1})  # prove prints a list, not one outcome
        self.assertIsNone(runtime.run_verifier(plan, prepared, self.attempt / "verifier").observations)

    def test_what_cant_be_attempted_as_stated_is_unsupported_not_a_stub(self):
        prepared, _ = self.verify(verifier_plan(self.folder))
        claim_file = self.folder / "claims/plan.json"
        claim_file.parent.mkdir()
        claim_file.write_text("{}")
        frozen = {"path": "claims/plan.json", "sha256": runtime.sha256(claim_file)}
        cases = {
            "replay": dataclasses.replace(verifier_plan(self.folder), kind="replay"),
            "default engine": verifier_plan(self.folder, engine=None),
            "unknown gap mode": verifier_plan(self.folder, gaps="lenient"),
            "models": verifier_plan(self.folder, models=[{"path": "m.json", "sha256": "0" * 64}]),
            "bound with no option": verifier_plan(self.folder, bounds={"unwind": 4, "depth": 3}),
            "changed plan file": verifier_plan(self.folder, plan={**frozen, "sha256": "1" * 64}),
        }
        for name, plan in cases.items():
            value = runtime.run_verifier(plan, prepared, self.attempt / "verifier")
            self.assertIsInstance(value, interfaces.Unsupported, name)
            self.assertEqual((value.interface, value.owner), ("run-verifier", interfaces.RUNTIME), name)
            self.assertNotIn(STUB, value.reason, name)
        good = runtime.run_verifier(verifier_plan(self.folder, plan=frozen), prepared, self.attempt / "verifier")
        self.assertEqual(good.argv[list(good.argv).index("--plan") + 1], str(claim_file.resolve()))
        with mock.patch.object(runtime, "jvmcontract", return_value=None):
            missing = runtime.run_verifier(verifier_plan(self.folder), prepared, self.attempt / "verifier")
        self.assertEqual(missing.stage, "toolchain")
        self.assertIn("cargo build --release", missing.diagnostic)
        (self.dir / "theirs").mkdir()
        (self.dir / "theirs/file").write_text("x")
        busy = runtime.run_verifier(verifier_plan(self.folder), prepared, self.dir / "theirs")
        self.assertEqual(busy.stage, "workdir")
        self.assertTrue((self.dir / "theirs/file").is_file())

    def test_an_original_jar_entry_outside_its_root_is_never_extracted(self):
        import zipfile
        where = self.dir / "escape"
        where.mkdir()
        with zipfile.ZipFile(where / "x.jar", "w") as z:
            z.writestr("fixture/Gate.class", b"\xca\xfe\xba\xbe")
            z.writestr("../outside.class", b"\xca\xfe\xba\xbe")
        prepared = mock.Mock(source={"target": {"loadedFrom": "x.jar"}})
        jar = interfaces.Artifact("x.jar", runtime.sha256(where / "x.jar"), "original")
        workdir = self.attempt / "verifier"
        workdir.mkdir(parents=True)
        with self.assertRaises(runtime.Refused) as caught:
            runtime._class_dirs({"after": (where, prepared, (jar,))}, workdir, self.attempt)
        self.assertIn("outside its root", caught.exception.diagnostic)
        self.assertFalse((workdir / "classes/outside.class").exists())
        self.assertFalse((self.attempt / "outside.class").exists())

    def test_the_recipes_javac_flags_reach_the_build_and_the_scope_records_the_names_the_class_has(self):
        """A recipe that records parameter names (javac -parameters, asked of Phase 0's recipe for VF-024) builds
        other bytes, a different identity, and the verifier's scope shows the names a claim may use."""
        plain = runtime.prepare(verifier_plan(self.folder), "after", self.work / "plain")
        recipe = runtime._fixture_recipe()
        with mock.patch.object(runtime, "_fixture_recipe", return_value={**recipe, "flags": ["-parameters"]}):
            prepared, record = self.verify(verifier_plan(self.folder))
        self.assertIn("-parameters", (self.attempt / "prepare/after/logs/javac-original.log").read_text().splitlines()[0])
        self.assertEqual(prepared["after"].source["recipe"]["flags"], ["-parameters"])
        self.assertNotEqual(prepared["after"].source["target"]["classSha256"], plain.source["target"]["classSha256"])
        self.assertEqual(record.identities["scope"]["revisions"]["after"]["parameters"],
                         {"names": ["code"], "recordedIn": "MethodParameters"})

    def test_a_mutant_entry_is_never_prepared_as_its_base(self):
        plan = dataclasses.replace(verifier_plan(self.folder), artifacts=({
            **verifier_plan(self.folder).artifacts[0], "mutant": {"base": {"revision": "after"}, "patch": {}}},))
        value = runtime.prepare(plan, "after", self.work / "mutant")
        self.assertIsInstance(value, interfaces.Unsupported)
        self.assertIn("constructed mutant", value.reason)

    def test_the_calibration_job_reads_each_verdict_against_the_fixtures_expectation(self):
        import runtime_calibrate
        cases = (("fixed-security", [{"verdict": "verified", "output": "✓\n"}], 0, True),
                 ("fixed-security", [{"verdict": "violation", "output": "✗ code = 97\n"}], 1, False),
                 ("vulnerable-security", [{"verdict": "violation", "output": "✗ code = 97\n"}], 1, True),
                 ("regex-probe", [{"verdict": "unverifiable", "output": "⚠ refused: a String parameter\n"}], 1, False),
                 ("regex-probe", [{"verdict": "unverifiable", "output": "⚠ java.util.regex.Pattern.matcher\n"}], 1, True),
                 ("regex-probe", [{"verdict": "verified", "output": "✓\n"}], 0, False))
        no_regex = {"stdout": json.dumps({**GAPS_OUT, "gaps": []})}
        for n, (task, outcome, code, ok) in enumerate(cases):
            self.answer(prove={"stdout": json.dumps(outcome), "exit": code}, gaps=no_regex)
            entry = runtime_calibrate.attempt(task, self.work / f"calibrate-{n}", self.folder)
            self.assertEqual(entry["ok"], ok, (task, outcome, entry.get("unsupported"), entry.get("preparation")))
            if n == 4:
                self.assertEqual((entry["refusalNamesRegex"], entry["probeNamesRegex"]), (True, False))
        # VF-024's case: the strict proof stops at the String parameter; the capability probe names the regex calls
        self.answer(prove={"stdout": json.dumps(cases[3][1]), "exit": 1})
        entry = runtime_calibrate.attempt("regex-probe", self.work / "calibrate-probe", self.folder)
        self.assertEqual((entry["ok"], entry["refusalNamesRegex"], entry["probeNamesRegex"]), (True, False, True))
        self.assertEqual(runtime_calibrate.plan("preservation", self.folder).claim["allowedChange"], "code == 97")

    def test_descriptors_become_jvmcontracts_target_spelling(self):
        for target, expected in (("fixture.Gate#allowed(I)Z", "fixture.Gate#allowed(int)"),
                                 ("a.B#m([[ILjava/lang/String;J[La/B$C;)V", "a.B#m(int[][], java.lang.String, long, a.B$C[])"),
                                 ("a.B#m()I", "a.B#m()"), ("a.B#m", "a.B#m")):
            self.assertEqual(runtime.java_target(target), expected)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests of runtime.py and its modules (runtime_jdk.py, runtime_jar.py), owned by the runtime stream with them: the
source lock and the fixture route's preparation (R1), on a copy of Phase 0's fixtures. run_controls() and
run_verifier() are still Phase 0's stubs, and fail closed.

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
from targets import interfaces, runtime, runtime_jar, runtime_jdk  # noqa: E402
from test_interfaces import plan  # noqa: E402

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
        for route in ("published-artifact", "upstream-build"):
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

    def test_an_adapter_that_does_not_call_the_target_is_refused(self):
        source = self.folder / "gate/adapter/fixture/adapter/GateAdapter.java"
        source.write_text(source.read_text().replace("return Gate.allowed(code);", "return code != 65 && code != 97;")
                          .replace("import fixture.Gate;\n", ""))
        prepared = self.prepare()
        self.assertEqual((prepared.stage, prepared.failedStage), ("failed", "adapter"), prepared.diagnostic)

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


class StubsFailClosedTest(unittest.TestCase):
    def check(self, value, interface, owner):
        self.assertTrue(interfaces.unsupported(value))
        self.assertEqual((value.interface, value.owner), (interface, owner))
        self.assertIn(owner, value.describe())

    def test_execution_is_still_phase0s_stub(self):
        self.check(runtime.run_controls(plan(), {}, Path(".")), "run-controls", interfaces.RUNTIME)
        self.check(runtime.run_verifier(plan(), {}, Path(".")), "run-verifier", interfaces.RUNTIME)


if __name__ == "__main__":
    unittest.main()

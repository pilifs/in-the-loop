#!/usr/bin/env python3
"""Tests of runtime.py and its modules (runtime_jdk.py, runtime_jar.py), owned by the runtime stream with them: the
source lock and the fixture route's preparation (R1) and the separate-JVM controls (R4), on a copy of Phase 0's
fixtures. run_verifier() is still Phase 0's stub, and fails closed.

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


class StubsFailClosedTest(unittest.TestCase):
    def test_the_verifier_is_still_phase0s_stub(self):
        value = runtime.run_verifier(plan(), {}, Path("."))
        self.assertTrue(interfaces.unsupported(value))
        self.assertEqual((value.interface, value.owner), ("run-verifier", interfaces.RUNTIME))
        self.assertIn(STUB, value.reason)


if __name__ == "__main__":
    unittest.main()

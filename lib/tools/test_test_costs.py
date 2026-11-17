#!/usr/bin/env python3
"""Tests for test_costs.py, on made-up inputs; `measure` itself is never run here.
Run: python3 lib/tools/test_test_costs.py"""
import json
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

import test_costs as tc
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

HERE = Path(__file__).resolve().parent

JUNIT_DEBUG = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="nextest-run" tests="4">
  <testsuite name="jvmcontract" tests="1">
    <testcase name="spec::tests::parses" classname="jvmcontract" time="0.012"/>
  </testsuite>
  <testsuite name="jvmcontract::conformance" tests="3">
    <testcase name="the_runner_compiles" classname="jvmcontract::conformance" time="4.500"/>
    <testcase name="the_corpus_agrees" classname="jvmcontract::conformance" time="61.000">
      <failure type="test failure">assertion failed</failure>
    </testcase>
    <testcase name="a_slow_pure_test" classname="jvmcontract::conformance" time="2.000"/>
  </testsuite>
</testsuites>
"""

JUNIT_RELEASE = """<?xml version="1.0" encoding="UTF-8"?>
<testsuites name="nextest-run" tests="1">
  <testsuite name="jvmcontract::heap" tests="1">
    <testcase name="the_object_properties_under_jbmc" classname="jvmcontract::heap" time="120.000"/>
  </testsuite>
</testsuites>
"""

CARGO_TEST = """\
    Finished `test` profile [unoptimized + debuginfo] target(s) in 0.40s
     Running unittests src/lib.rs (target/debug/deps/jvmcontract-0123456789abcdef)
test result: ok. 258 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 3.00s
     Running tests/conformance.rs (target/debug/deps/conformance-0123456789abcdef)
test result: FAILED. 10 passed; 1 failed; 2 ignored; 0 measured; 0 filtered out; finished in 60.50s
   Doc-tests jvmcontract
test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.10s
"""


def watched(binary, name, attempt=1, **extra):
    return {"binary": binary, "name": name, "profile": "measure", "attempt": str(attempt), "wall_s": 1.0,
            "cpu_s": 0.5, "max_rss_mb": 50.0, "tree_peak_mb": 40.0, "spawned": {}, "exit": 0, **extra}


class Names(unittest.TestCase):
    def test_tool_names(self):
        jdk = "/opt/jdk/bin"
        cases = [
            (("/usr/bin/jbmc", ["jbmc", "Foo.class"]), "jbmc"),
            ((f"{jdk}/javac", ["javac", "-d", "out", "A.java"]), "javac"),
            ((f"{jdk}/java", ["java", "-cp", "out", "Runner"]), "java"),
            ((f"{jdk}/java", ["java", "-cp", "/x/tla2tools.jar", "tlc2.TLC", "M"]), "tlc"),
            (("/usr/bin/bash", ["bash", "/opt/tools/bin/tlc", "M.tla"]), "tlc"),
            (("/usr/bin/dash", ["sh", "/tmp/t/jbmc-stand-in", "--version"]), "sh jbmc-stand-in"),
            (("/usr/bin/python3.14", ["python3", "-I", "fake_jbmc.py"]), "python3 fake_jbmc.py"),
            (("/repo/lib/target/debug/jvmcontract", ["jvmcontract", "prove"]), "jvmcontract"),
            (("/usr/bin/gnusleep", ["sleep", "1"]), "sleep"),
            (("/usr/bin/jbmc", []), "jbmc"),
            ((None, []), "?"),
        ]
        for (exe, argv), name in cases:
            self.assertEqual(tc.tool_name(exe, argv), name, argv)


class Tiers(unittest.TestCase):
    def test_tiers_by_tool_time_and_memory(self):
        self.assertEqual(tc.tier(0.2, 30, {}), ("unit", "in process, under 1 s"))
        self.assertEqual(tc.tier(1.5, 30, {})[0], "tool")
        self.assertEqual(tc.tier(0.5, 30, {"javac": 1}), ("tool", "spawns javac"))
        self.assertEqual(tc.tier(0.5, 30, {"jbmc": 2, "javac": 1}), ("proof", "spawns jbmc"))
        self.assertEqual(tc.tier(3.0, 30, {"tlc": 1})[0], "proof")
        self.assertEqual(tc.tier(10.0, 30, {"javac": 1}), ("proof", "10.0 s, over the tool tier's 10 s"))
        self.assertEqual(tc.tier(2.0, 1500, {"java": 1}), ("proof", "1500 MB, over the tool tier's 1024 MB"))


class Parsing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_junit(self):
        (self.dir / "j.xml").write_text(JUNIT_DEBUG)
        cases = tc.read_junit(self.dir / "j.xml", "debug")
        self.assertEqual(cases[("jvmcontract::conformance", "the_corpus_agrees")],
                         {"time_s": 61.0, "status": "failed", "profile": "debug"})
        self.assertEqual(cases[("jvmcontract", "spec::tests::parses")]["status"], "passed")
        self.assertEqual(tc.read_junit(self.dir / "missing.xml", "debug"), {})

    def test_watch_records_keep_the_last_attempt(self):
        w = self.dir / "watch"
        w.mkdir()
        (w / "1.json").write_text(json.dumps(watched("b", "t", attempt=2, cpu_s=9.0)))
        (w / "2.json").write_text(json.dumps(watched("b", "t", attempt=1)))
        (w / "3.json").write_text(json.dumps(watched("b", "u")))
        records = tc.read_watch(w)
        self.assertEqual(records[("b", "t")]["cpu_s"], 9.0)
        self.assertEqual(set(records), {("b", "t"), ("b", "u")})
        self.assertEqual(tc.read_watch(self.dir / "none"), {})

    def test_cargo_test_output(self):
        (self.dir / "c.log").write_text(CARGO_TEST)
        self.assertEqual(tc.read_cargo_test(self.dir / "c.log"), [
            {"binary": "src/lib.rs", "passed": 258, "failed": 0, "ignored": 0, "time_s": 3.0},
            {"binary": "tests/conformance.rs", "passed": 10, "failed": 1, "ignored": 2, "time_s": 60.5},
            {"binary": "doc-tests jvmcontract", "passed": 0, "failed": 0, "ignored": 0, "time_s": 0.1}])

    def test_group_config_puts_each_binary_alone(self):
        tc._group_config(self.dir / "g.toml", ["jvmcontract", "jvmcontract::bin/jvmcontract", "jvmcontract::heap"])
        doc = tomllib.loads((self.dir / "g.toml").read_text())
        self.assertEqual(doc["test-groups"], {"jvmcontract": {"max-threads": 1},
                                              "jvmcontract--bin-jvmcontract": {"max-threads": 1},
                                              "jvmcontract--heap": {"max-threads": 1}})
        self.assertEqual(doc["profile"]["measure"]["overrides"][2],
                         {"filter": "binary_id(=jvmcontract::heap)", "test-group": "jvmcontract--heap"})

    def test_inventory_from_raw_files(self):
        raw = self.dir / "raw"
        (raw / "watch").mkdir(parents=True)
        (raw / "junit-debug.xml").write_text(JUNIT_DEBUG)
        (raw / "junit-release.xml").write_text(JUNIT_RELEASE)
        records = [watched("jvmcontract", "spec::tests::parses", wall_s=0.01, max_rss_mb=20.0, tree_peak_mb=20.0),
                   watched("jvmcontract::conformance", "the_runner_compiles", spawned={"javac": 1, "java": 3}),
                   watched("jvmcontract::conformance", "the_corpus_agrees", spawned={"jbmc": 12}),
                   watched("jvmcontract::heap", "the_object_properties_under_jbmc", max_rss_mb=1300.0,
                           spawned={"jbmc": 4})]
        for i, r in enumerate(records):
            (raw / "watch" / f"{i}.json").write_text(json.dumps(r))
        (raw / "python.jsonl").write_text("".join(json.dumps(r) + "\n" for r in [
            {"file": "a/test_a.py", "name": "test_a.T.test_fast", "wall_s": 0.01, "cpu_s": 0.01, "tree_peak_mb": 0,
             "spawned": {}, "status": "passed"},
            {"file": "a/test_a.py", "name": "test_a.T.test_build", "wall_s": 3.0, "cpu_s": 2.0, "tree_peak_mb": 200,
             "spawned": {"javac": 2}, "status": "passed"},
            {"file": "a/test_a.py", "name": "test_a.T.test_skip", "wall_s": 0.0, "status": "skipped"},
            {"file": "b/test_b.py", "name": None, "status": "failed", "error": "ImportError: x"}]))
        (raw / "run.json").write_text(json.dumps({"cpus": 8, "default_cargo_test": {"wall_s": 70.0}}))
        path = self.dir / "costs.json"
        doc = tc.write_inventory(raw, "job 20000101-000000-x", path)
        self.assertEqual(json.loads(path.read_text()), doc)
        rust = {(r["binary"], r["name"]): r for r in doc["rust"]}
        self.assertEqual(rust[("jvmcontract", "spec::tests::parses")]["tier"], "unit")
        self.assertEqual(rust[("jvmcontract::conformance", "the_runner_compiles")]["why"], "spawns java, javac")
        self.assertEqual(rust[("jvmcontract::conformance", "the_corpus_agrees")]["tier"], "proof")
        slow = rust[("jvmcontract::conformance", "a_slow_pure_test")]
        self.assertEqual((slow["tier"], slow["cpu_s"], slow["peak_mb"]), ("tool", None, None))
        heap = rust[("jvmcontract::heap", "the_object_properties_under_jbmc")]
        self.assertEqual((heap["declared"], heap["profile"], heap["peak_mb"], heap["source"]),
                         ("ignored", "release", 1300.0, "job 20000101-000000-x"))
        summary = doc["summary"]["rust"]
        self.assertEqual((summary["tests"], summary["failed"], summary["default_proof_tier"],
                          summary["ignored_below_proof"]), (5, 1, 1, 0))
        self.assertEqual(summary["by_declared"]["default"], {"unit": 1, "tool": 2, "proof": 1})
        python = {r["name"]: r for r in doc["python"]}
        self.assertEqual(python["test_a.T.test_build"]["tier"], "tool")
        self.assertEqual(python["test_a.T.test_skip"]["tier"], None)
        self.assertEqual(python[None]["why"], "the file failed to load")
        self.assertEqual(doc["summary"]["python"]["by_file"]["a/test_a.py"], {"unit": 1, "tool": 1, "not measured": 1})
        self.assertEqual(doc["default_cargo_test"], {"wall_s": 70.0})


class Files(unittest.TestCase):
    def test_module_for_a_file_in_a_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "tools" / "targets"
            pkg.mkdir(parents=True)
            (pkg / "__init__.py").write_text("")
            (pkg / "test_x.py").write_text("")
            (Path(tmp) / "tools" / "test_y.py").write_text("")
            top, here, module = tc._module_for(pkg / "test_x.py")
            self.assertEqual((top, here, module), (pkg.parent.resolve(), pkg.resolve(), "targets.test_x"))
            self.assertEqual(tc._module_for(Path(tmp) / "tools" / "test_y.py")[2], "test_y")

    def test_python_test_files_leave_out_examples_and_build_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ["examples/tools/test_build.py", "examples/052-x/test_inner.py", "lib/target/test_gen.py",
                        "verification/test_pipeline.py", "verification/helper.py", ".jj/test_no.py"]:
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text("")
            found = [str(p.relative_to(root)) for p in tc.python_test_files(root)]
            self.assertEqual(found, ["examples/tools/test_build.py", "verification/test_pipeline.py"])


class RunningATier(unittest.TestCase):
    """`run`'s commands for each tier, from a made-up inventory; the one test that runs them runs made-up files."""
    DOC = {"python": [
        {"file": "tools/targets/test_x.py", "name": "X.test_unit", "tier": "unit"},
        {"file": "tools/targets/test_x.py", "name": "X.test_proof", "tier": "proof"},
        {"file": "tools/test_y.py", "name": "Y.test_pending", "tier": "proof", "retier": "pending"},
        {"file": "tools/test_y.py", "name": "Y.test_tool", "tier": "tool"},
    ]}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "tools/targets").mkdir(parents=True)
        (self.root / "tools/targets/__init__.py").write_text("")

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_default_and_unit_tiers_run_cargo_and_every_python_file_with_both_variables_set(self):
        for tier, value in (("default", "tool"), ("unit", "unit")):
            runs = tc.tier_runs(tier, self.DOC, self.root)
            self.assertEqual([r[0] for r in runs], ["cargo test", "tools/targets/test_x.py", "tools/test_y.py"])
            label, argv, env, cwd = runs[0]
            self.assertEqual(argv, ["cargo", "test", "--manifest-path", "lib/Cargo.toml", "--profile", "test-fast"])
            self.assertEqual((env, cwd), ({"JVMCONTRACT_TEST_TIER": value, "TEST_COST": value, "VERIFY_MACHINE_CONFIG": ""}, self.root))
            _, argv, env, _ = runs[1]
            self.assertEqual(argv[1:], ["-m", "unittest", "targets.test_x"])
            self.assertEqual(env["PYTHONPATH"], os.pathsep.join(["tools", "tools/targets"]))
            self.assertEqual(runs[2][2]["PYTHONPATH"], "tools")

    def test_the_proof_tier_runs_the_ignored_rust_tests_in_release_and_only_the_python_proof_tests(self):
        runs = tc.tier_runs("proof", self.DOC, self.root, tests=["heap"], test_threads=4)
        self.assertEqual(runs[0][1], ["cargo", "test", "--manifest-path", "lib/Cargo.toml", "--release",
                                      "--test", "heap", "--", "--ignored", "--test-threads", "4"])
        self.assertEqual([r[0] for r in runs[1:]], ["tools/targets/test_x.py"])
        self.assertEqual(runs[1][1][-2:], ["-k", "X.test_proof"])
        self.assertEqual(runs[1][2]["TEST_COST"], "proof")

    def test_one_language_and_a_misspelt_tier(self):
        self.assertEqual([r[0] for r in tc.tier_runs("unit", self.DOC, self.root, only="rust")], ["cargo test"])
        self.assertNotIn("cargo test", [r[0] for r in tc.tier_runs("unit", self.DOC, self.root, only="python")])
        with self.assertRaises(ValueError):
            tc.tier_runs("tool", self.DOC, self.root)

    @cost("tool")
    def test_running_a_tier_reports_each_python_file_and_fails_if_one_does(self):
        cases = "import os, unittest\nclass {c}(unittest.TestCase):\n    def test_{t}(self):\n        {body}\n"
        (self.root / "tools/targets/test_x.py").write_text(
            cases.format(c="X", t="unit", body="self.assertEqual(os.environ['TEST_COST'], 'unit')"))
        (self.root / "tools/test_y.py").write_text(cases.format(c="Y", t="tool", body="self.fail('made up')"))
        inventory = self.root / "costs.json"
        inventory.write_text(json.dumps(self.DOC))
        out = subprocess.run([sys.executable, "-c", "import sys, test_costs as tc; sys.exit(tc.run_tier("
                              f"'unit', {str(inventory)!r}, __import__('pathlib').Path({str(self.root)!r}), "
                              "'python'))"], cwd=HERE, capture_output=True, text=True)
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        lines = out.stdout.splitlines()
        self.assertTrue(lines[0].startswith("ok   tools/targets/test_x.py: Ran 1 test in"), lines)
        self.assertTrue(lines[0].endswith(", OK"), lines)
        self.assertTrue(lines[1].startswith("FAIL tools/test_y.py: Ran 1 test in"), lines)
        self.assertIn("AssertionError: made up", out.stdout)
        self.assertEqual(lines[-1], "unit tier: 1 of 2 passed; failed: tools/test_y.py")


    def run_both(self, cargo_body, *flags):
        """run_tier over a stand-in cargo on PATH (cargo_body is its Python) and the two files the test writes."""
        bin = self.root / "bin"
        bin.mkdir(exist_ok=True)
        (bin / "cargo").write_text("#!" + sys.executable + "\nimport os, sys, time\n" + cargo_body)
        (bin / "cargo").chmod(0o755)
        inventory = self.root / "costs.json"
        inventory.write_text(json.dumps(self.DOC))
        env = {**os.environ, "PATH": f"{bin}:{os.environ['PATH']}", "MARKS": str(self.root)}
        only = dict(flags).get("only", "None")
        call = (f"'unit', {str(inventory)!r}, __import__('pathlib').Path({str(self.root)!r}), {only}"
                + "".join(f", {f}={v}" for f, v in flags if f != "only"))
        return subprocess.run([sys.executable, "-c", f"import sys, test_costs as tc; sys.exit(tc.run_tier({call}))"],
                              cwd=HERE, capture_output=True, text=True, env=env)

    @cost("tool")
    def test_cargo_runs_beside_the_python_files_and_what_passes_on_a_second_run_is_flaky(self):
        body = "import os, unittest\nclass {c}(unittest.TestCase):\n    def test_{t}(self):\n        {b}\n"
        flaky = ("import pathlib, time; m = pathlib.Path(os.environ['MARKS']) / 'x-ran'; first = not m.exists(); "
                 "m.write_text(''); time.sleep(0.5); self.assertFalse(first, 'made-up flake')")
        (self.root / "tools/targets/test_x.py").write_text(body.format(c="X", t="unit", b=flaky))
        (self.root / "tools/test_y.py").write_text(body.format(c="Y", t="tool", b="pass"))
        cargo = ("m = os.path.join(os.environ['MARKS'], 'cargo-ran')\nfirst = not os.path.exists(m)\nopen(m, 'a').write(str(time.time()) + '\\n')\n"
                 "if first:\n    print('test a::b ... FAILED'); sys.exit(101)\nprint('test a::b ... ok'); sys.exit(0)\n")
        out = self.run_both(cargo)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("FLAKY tools/targets/test_x.py", out.stdout)
        self.assertIn("FLAKY cargo test: a::b", out.stdout)
        self.assertEqual(out.stdout.splitlines()[-1], "unit tier: 3 of 3 passed; flaky: tools/targets/test_x.py, cargo test")
        started = float((self.root / "cargo-ran").read_text().split()[0])
        self.assertLess(started, (self.root / "x-ran").stat().st_mtime, "cargo started before the first Python file ended")
        (self.root / "cargo-ran").unlink()
        (self.root / "x-ran").unlink()
        out = self.run_both(cargo, ("retry", "False"), ("serial", "True"))
        self.assertEqual(out.returncode, 1)
        self.assertEqual(out.stdout.splitlines()[-1], "unit tier: 1 of 3 passed; failed: cargo test, tools/targets/test_x.py")


    @cost("tool")
    def test_rust_test_binaries_run_several_at_a_time_the_longest_first_and_a_failing_one_is_shown_whole(self):
        # A stand-in cargo: --no-run names three binaries as cargo's JSON does, --doc runs the doctests, and each
        # binary is a script that notes when it started and ended.
        binary = ("#!" + sys.executable + "\nimport os, sys, time\nname = os.path.basename(sys.argv[0])\n"
                  "open(os.path.join(os.environ['MARKS'], name + '.began'), 'w').write(str(time.time()))\n"
                  "time.sleep(0.6)\nopen(os.path.join(os.environ['MARKS'], name + '.cwd'), 'w').write(os.getcwd() + ' ' + ' '.join(sys.argv[1:]))\n"
                  "bad = name == 'slow' and not os.path.exists(os.path.join(os.environ['MARKS'], 'again'))\n"
                  "print('test t::of_' + name + ' ... ' + ('FAILED' if bad else 'ok'))\n"
                  "print('test result: ' + ('FAILED' if bad else 'ok') + '. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.60s')\n"
                  "sys.exit(101 if bad else 0)\n")
        (self.root / "lib/tests").mkdir(parents=True)
        deps = self.root / "target/debug/deps"  # where cargo puts them: the target directory is two folders up
        deps.mkdir(parents=True)
        for name in ("quick", "slow", "other"):
            (deps / name).write_text(binary)
            (deps / name).chmod(0o755)
        cargo = ("import json\nroot = os.environ['MARKS']\n"
                 "if '--no-run' in sys.argv:\n"
                 "    print('   Compiling made-up', file=sys.stderr)\n"
                 "    for name in ('quick', 'slow', 'other'):\n"
                 "        print(json.dumps({'reason': 'compiler-artifact', 'profile': {'test': True}, 'executable': os.path.join(root, 'target', 'debug', 'deps', name),\n"
                 "                          'manifest_path': os.path.join(root, 'lib', 'Cargo.toml'),\n"
                 "                          'target': {'src_path': os.path.join(root, 'lib', 'tests', name + '.rs')}}))\n"
                 "    print(json.dumps({'reason': 'compiler-artifact', 'profile': {'test': False}, 'executable': os.path.join(root, 'main'), 'target': {'src_path': 'x'}}))\n"
                 "elif '--doc' in sys.argv:\n    print('test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.00s')\n"
                 "else:\n    open(os.path.join(root, 'again'), 'w').write(' '.join(sys.argv[1:]))\n"
                 "    print('test t::of_slow ... ok')\n")
        doc = dict(self.DOC, rust=[{"file": "lib/tests/slow.rs", "name": "t::of_slow", "cost": {"seconds": 9}},
                                   {"file": "lib/tests/other.rs", "name": "t::of_other", "cost": {"seconds": 2}}])
        self.DOC, kept_doc = doc, self.DOC
        try:
            for name in ("test_x.py", "test_y.py"):
                where = self.root / ("tools/targets" if name == "test_x.py" else "tools") / name
                where.write_text("import unittest\nclass T(unittest.TestCase):\n    def test_it(self):\n        pass\n")
            out = self.run_both(cargo, ("rust_jobs", "2"), ("test_threads", "3"))
        finally:
            self.DOC = kept_doc
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        began = {n: float((self.root / f"{n}.began").read_text()) for n in ("quick", "slow", "other")}
        self.assertLess(began["slow"], began["quick"], "the longest by the inventory starts first")
        self.assertLess(began["other"] - began["slow"], 0.5, "two at a time: the second starts while the first runs")
        self.assertGreater(began["quick"] - began["slow"], 0.5, "and the third waits for a place")
        self.assertEqual((self.root / "slow.cwd").read_text(), f"{self.root / 'lib'} --test-threads 3",
                         "a binary runs in its package's folder with the arguments after --, as under cargo")
        self.assertIn("     Running lib/tests/slow.rs (", out.stdout)
        self.assertIn("test t::of_slow ... FAILED", out.stdout, "a failing binary's output is shown whole")
        self.assertIn("error: test failed, to rerun pass `--test slow`", out.stdout)
        self.assertNotIn("test t::of_quick ... ok", out.stdout, "a passing binary is its result line alone")
        self.assertRegex(out.stdout, r"test result: ok\. 1 passed; .* \[\d+s with the others\]")
        self.assertIn("cargo test: 4 test binaries, 2 at a time", out.stdout)
        self.assertIn("--exact t::of_slow", (self.root / "again").read_text(), "what failed is retried by name, through cargo")
        self.assertIn("FLAKY cargo test: t::of_slow", out.stdout)
        self.assertEqual(out.stdout.splitlines()[-1], "unit tier: 3 of 3 passed; flaky: cargo test")
        # What each took is kept where the binaries are, and orders the next run, whatever the inventory says.
        kept = self.root / "target" / tc.BINARY_SECONDS
        self.assertEqual(sorted(json.loads(kept.read_text())), ["lib/tests/other.rs", "lib/tests/quick.rs", "lib/tests/slow.rs"])
        kept.write_text(json.dumps({"lib/tests/quick.rs": 99, "lib/tests/slow.rs": 1, "lib/tests/other.rs": 2}))
        self.DOC = doc
        try:
            out = self.run_both(cargo, ("rust_jobs", "2"))
        finally:
            self.DOC = kept_doc
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        began = {n: float((self.root / f"{n}.began").read_text()) for n in ("quick", "slow", "other")}
        self.assertEqual(max(began, key=began.get), "slow", "the shortest by the last run starts last")

    def test_binaries_at_a_time_are_half_the_cpus_at_most_four_and_one_per_gigabyte_and_a_half_of_a_jobs_memory(self):
        self.assertEqual(tc._rust_jobs({}, cpus=30), 4)
        self.assertEqual(tc._rust_jobs({}, cpus=2), 1)
        self.assertEqual(tc._rust_jobs({"VERIFY_CPUS": "6"}), 3)
        self.assertEqual(tc._rust_jobs({"VERIFY_CPUS": "6", "VERIFY_MEMORY_LIMIT_MB": "4096"}), 2)
        self.assertEqual(tc._rust_jobs({"VERIFY_CPUS": "6", "VERIFY_MEMORY_LIMIT_MB": "1024"}), 1)

    @cost("tool")
    def test_python_files_run_several_at_a_time_and_a_failed_ones_second_run_is_alone_after_the_others(self):
        body = ("import os, pathlib, time, unittest\nclass T(unittest.TestCase):\n    def test_it(self):\n"
                "        marks = pathlib.Path(os.environ['MARKS'])\n"
                "        runs = len(list(marks.glob('{n}.began*')))\n"
                "        (marks / ('{n}.began' + str(runs))).write_text(str(time.time()))\n"
                "        time.sleep(0.6)\n"
                "        (marks / ('{n}.ended' + str(runs))).write_text(str(time.time()))\n"
                "        {more}\n")
        (self.root / "tools/targets/test_x.py").write_text(body.format(n="x", more="self.assertTrue(runs, 'made-up clash')"))
        (self.root / "tools/test_y.py").write_text(body.format(n="y", more="pass"))
        out = self.run_both("print('test result: ok.')\n", ("python_jobs", "2"), ("only", "'python'"))
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        at = {p.name: float(p.read_text()) for p in self.root.glob("*.*[0-9]")}
        self.assertLess(at["y.began0"], at["x.ended0"], "two at a time: the second starts while the first runs")
        self.assertLess(at["x.began0"], at["y.ended0"])
        self.assertGreater(at["x.began1"], at["y.ended0"], "the second run of the one that failed waits for the others")
        self.assertIn("FLAKY tools/targets/test_x.py", out.stdout)
        self.assertEqual(out.stdout.splitlines()[-1], "unit tier: 2 of 2 passed; flaky: tools/targets/test_x.py")

    @cost("tool")
    def test_a_build_that_fails_is_cargos_own_words_and_a_failure(self):
        cargo = ("import json\nprint(json.dumps({'reason': 'compiler-message', 'message': {'rendered': 'error[E0425]: made up'}}))\n"
                 "print('error: could not compile', file=sys.stderr)\nsys.exit(101)\n")
        for name in ("tools/targets/test_x.py", "tools/test_y.py"):
            (self.root / name).write_text("import unittest\nclass T(unittest.TestCase):\n    def test_it(self):\n        pass\n")
        out = self.run_both(cargo, ("rust_jobs", "2"))
        self.assertEqual(out.returncode, 1, out.stdout + out.stderr)
        self.assertIn("error[E0425]: made up", out.stdout)
        self.assertIn("error: could not compile", out.stdout)
        self.assertEqual(out.stdout.splitlines()[-1], "unit tier: 2 of 3 passed; failed: cargo test")


class Changed(unittest.TestCase):
    """run --changed: the tests a change asks for, chosen statically from the files alone."""

    def test_a_test_is_chosen_by_changing_by_importing_what_changed_or_by_naming_it_in_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                "tools/helper.py": "def f():\n    return 1\n",
                "tools/test_imports.py": "import helper\n",
                "tools/test_reads.py": '"""It reads schema/thing.schema.json, says the docstring."""\nPATH = "data/thing.json"\n',
                "tools/test_docstring_only.py": '"""See schema/thing.schema.json and pages/guide.md."""\n',
                "tools/test_other.py": "x = 1\n",
                "tools/test_edited.py": "y = 2\n",
                "tools/cost_tier.py": 'INVENTORY = "lib/tests/costs.json"\n',
                "tools/test_with_costs.py": "import cost_tier\n",
            }
            for rel, text in files.items():
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text(text)
            doc = {"python": [{"file": rel, "name": "T.test", "tier": "unit"} for rel in files if "/test_" in rel]}
            rust, chosen = tc.changed_selection(root, doc, ["tools/helper.py", "data/thing.json", "tools/test_edited.py",
                                                            "schema/thing.schema.json", "lib/tests/costs.json"])
            self.assertEqual(chosen, {"tools/test_edited.py": "it changed", "tools/test_imports.py": "it imports tools/helper.py",
                                      "tools/test_reads.py": "it names data/thing.json"})
            self.assertEqual(rust, [], "the inventory is read by the Rust tier test: all of cargo test")
            self.assertEqual(tc.changed_selection(root, doc, ["lib/tests/pairing.rs"])[0], ["pairing"])
            self.assertIsNone(tc.changed_selection(root, doc, ["lib/README.md", "tools/helper.py"])[0])


class Watching(unittest.TestCase):
    """The process sampling, on made-up commands of well under a second."""

    @cost("tool")
    def test_watch_records_a_spawned_process_and_passes_the_exit_on(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {**os.environ, "TEST_COSTS_DIR": tmp, "NEXTEST_BINARY_ID": "demo::bin", "NEXTEST_TEST_NAME": "t"}
            code = subprocess.run([sys.executable, str(HERE / "test_costs.py"), "watch", "--", "sh", "-c",
                                   "sleep 0.2; exit 3"], env=env).returncode
            self.assertEqual(code, 3)
            [record] = [json.loads(p.read_text()) for p in Path(tmp).glob("*.json")]
            self.assertEqual((record["binary"], record["name"], record["exit"]), ("demo::bin", "t", 3))
            self.assertEqual(record["spawned"], {"sleep": 1})
            self.assertGreaterEqual(record["wall_s"], 0.2)
            self.assertGreater(record["max_rss_mb"], 0)

    @cost("tool")
    def test_watch_without_a_directory_only_runs_the_command(self):
        env = {k: v for k, v in os.environ.items() if k != "TEST_COSTS_DIR"}
        self.assertEqual(subprocess.run([sys.executable, str(HERE / "test_costs.py"), "watch", "true"],
                                        env=env).returncode, 0)

    @cost("tool")
    def test_python_file_test_by_test(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "test_demo.py"
            f.write_text(
                "import subprocess, unittest\n"
                "class T(unittest.TestCase):\n"
                "    def test_spawns(self):\n"
                "        subprocess.run(['sleep', '0.2'], check=True)\n"
                "    def test_fails(self):\n"
                "        self.fail('made up')\n"
                "    @unittest.skip('made up')\n"
                "    def test_skipped(self):\n"
                "        pass\n")
            out = Path(tmp) / "out.jsonl"
            code = subprocess.run([sys.executable, str(HERE / "test_costs.py"), "python", str(f), "--out", str(out)],
                                  capture_output=True).returncode
            self.assertEqual(code, 1)
            records = {r["name"]: r for r in map(json.loads, out.read_text().splitlines())}
            self.assertEqual({n: r["status"] for n, r in records.items()},
                             {"test_demo.T.test_spawns": "passed", "test_demo.T.test_fails": "failed",
                              "test_demo.T.test_skipped": "skipped"})
            spawns = records["test_demo.T.test_spawns"]
            self.assertEqual(spawns["spawned"], {"sleep": 1})
            self.assertGreaterEqual(spawns["wall_s"], 0.2)
            self.assertEqual(records["test_demo.T.test_fails"]["spawned"], {})


if __name__ == "__main__":
    unittest.main()

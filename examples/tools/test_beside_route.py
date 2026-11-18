#!/usr/bin/env python3
"""Tests for beside_route.py, what every example's proof driver does the same way: a run at another bound or unwinding
is a trial; a constructed mutant whose JAR is not the one the mutant replay ran ends the run; the record
(evidence.json) holds the identities of what ran. And every driver of an example uses it.
Run: python3 examples/tools/test_beside_route.py

The tool-tier test builds a made-up example in a temporary folder: a library of one class compiled into a JAR, its
sources JAR, a patch, the sources lock, a mutant replay's receipt, and a script standing in for the verifier."""
from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

import beside_route

REPO = Path(__file__).resolve().parents[2]
sys.path.append(str(REPO / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib/tools"))
from cost_tier import cost  # noqa: E402

SOURCE = "lib/src/main/java/fx/Gate.java"
MEMBER = "fx/Gate.java"
ORIGINAL = """package fx;

public final class Gate {
    public static boolean open(int level) {
        return level > 3;
    }
}
"""
PATCH = """--- a/lib/src/main/java/fx/Gate.java
+++ b/lib/src/main/java/fx/Gate.java
@@ -2,6 +2,6 @@

 public final class Gate {
     public static boolean open(int level) {
-        return level > 3;
+        return level >= 3;
     }
 }
"""
# The verifier's stand-in: it prints the outcome `jvmcontract prove --json` would, a refutation.
VERIFIER = """#!/usr/bin/env python3
import json
print(json.dumps([{"verdict": "violation", "output": "made up: a violation", "search": {"native": {"paths": 1}}}]))
"""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def library(root: Path):
    """The library's one class, compiled as a release would be (root/classes/fx/Gate.class)."""
    (root / "src/fx").mkdir(parents=True)
    (root / "src/fx/Gate.java").write_text(ORIGINAL)
    subprocess.run(["javac", "--release", "8", "-g", "-parameters", "-nowarn", "-Xlint:-options", "-d", str(root / "classes"),
                    str(root / "src/fx/Gate.java")], check=True, capture_output=True)


class Fixture:
    """A made-up example with a constructed mutant, in `root`, and its pinned JARs in `root/jars` (the library
    compiled first, by `library`)."""

    def __init__(self, root: Path):
        self.root, self.here, self.jars = root, root / "examples/900-fixture", root / "jars"
        for d in (self.here / "claims", self.here / "controls", self.jars):
            d.mkdir(parents=True)
        jar = self.jars / "gate-1.0.jar"
        with zipfile.ZipFile(jar, "w") as z:
            z.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
            z.writestr("fx/Gate.class", (root / "classes/fx/Gate.class").read_bytes())
        with zipfile.ZipFile(self.jars / "gate-1.0-sources.jar", "w") as z:
            z.writestr(MEMBER, ORIGINAL)
        (self.here / "controls/m.patch").write_text(PATCH)
        (self.here / "claims/c.json").write_text(json.dumps({
            "assume": "true", "assert": "fx.Gate.open(level) == level > 3",
            "assumptions": [{"text": "the entry fx.adapter.GateAdapter#check"}], "bounds": {"maxArrayLength": 4}}))
        (self.here / "replay/adapter").mkdir(parents=True)
        (self.here / "replay/adapter/GateAdapter.java").write_text(
            "package fx.adapter;\n\npublic final class GateAdapter {\n"
            "    public static boolean check(int level) { return fx.Gate.open(level); }\n}\n")
        (self.here / "sources.lock.json").write_text(json.dumps({"revisions": {"fixed-release": {"files": {
            SOURCE: hashlib.sha1(b"blob %d\0" % len(ORIGINAL) + ORIGINAL.encode()).hexdigest()}}}}))
        (self.here / "target.json").write_text(json.dumps({
            "preparation": {"artifacts": [{"revision": "fixed-release", "url": "https://example.invalid/gate-1.0.jar",
                                           "sha256": sha(jar.read_bytes())}],
                            "adapters": ["replay/adapter/GateAdapter.java"]},
            "history": {"revisions": {"fixed-release": {}, "mutant": {"mutant": {
                "base": "fixed-release", "patch": "controls/m.patch", "sha256": sha(PATCH.encode())}}}},
            "tasks": [{"id": "mutant-security", "kind": "prove", "revision": "mutant", "claim": "claims/c.json",
                       "expected": "refuted", "engine": "native", "gaps": "strict"},
                      {"id": "fixed-security", "kind": "prove", "revision": "fixed-release", "claim": "claims/c.json",
                       "expected": "established", "engine": "native", "gaps": "strict"}]}))
        self.verifier = root / "jvmcontract"
        self.verifier.write_text(VERIFIER)
        self.verifier.chmod(0o755)

    def replayed(self, digest: str):
        """The mutant replay's receipt, recording `digest` for the mutant's own JAR."""
        folder = self.here / "receipts/mutant-replay/20261117T000000Z-0"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "result.json").write_text(json.dumps({"artifacts": [{"revision": "mutant", "role": "original", "sha256": digest}]}))

    def run(self, task="mutant-security") -> beside_route.Run:
        return beside_route.Run(self.here, "fx.adapter.GateAdapter#check", task, jars=self.jars, work=self.root / "work")


class TheBound(unittest.TestCase):
    """A run at another bound or unwinding than the claim's is a trial."""

    def run_with(self, bounds):
        r = beside_route.Run.__new__(beside_route.Run)
        r.claim = {"bounds": bounds}
        return r

    def test_the_claims_bound_is_no_trial(self):
        self.assertEqual(self.run_with({"maxArrayLength": 8}).bound(), {"maxArrayLength": 8, "unwind": None, "trial": False})
        self.assertEqual(self.run_with({"maxArrayLength": 8}).bound(8, None, 26), {"maxArrayLength": 8, "unwind": 26, "trial": False})
        self.assertEqual(self.run_with({"maxArrayLength": 8, "unwind": 30}).bound(None, 30, 26)["trial"], False)

    def test_another_length_or_unwinding_is_a_trial(self):
        self.assertTrue(self.run_with({"maxArrayLength": 8}).bound(4)["trial"])
        self.assertTrue(self.run_with({"maxArrayLength": 8}).bound(None, 10)["trial"])
        self.assertTrue(self.run_with({"maxArrayLength": 8}).bound(None, 10, 26)["trial"])
        self.assertTrue(self.run_with({}).bound(4)["trial"])

    def test_the_arguments_name_what_is_set(self):
        r = self.run_with({})
        self.assertEqual(r.bound_args({"maxArrayLength": None, "unwind": None}), [])
        self.assertEqual(r.bound_args({"maxArrayLength": 8, "unwind": 26}), ["--unwind", "26", "--max-array-length", "8"])


class EveryDriver(unittest.TestCase):
    def test_every_examples_driver_runs_through_the_shared_properties(self):
        drivers = sorted(REPO.glob("examples/*/proofs/prove.py"))
        self.assertTrue(drivers)
        for driver in drivers:
            text = driver.read_text()
            with self.subTest(driver=driver.parent.parent.name):
                self.assertIn("import beside_route", text)
                self.assertIn("run.finish(", text)
                self.assertNotIn("def mutant(", text, "a driver builds its mutant by beside_route's recipe")


class TheMutantAndTheRecord(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        library(Path(self.tmp.name))
        self.fx = Fixture(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def built(self, run) -> tuple[list, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            jars = run.mutant("mutant")
        return jars, out.getvalue()

    @cost("tool")
    def test_a_mutant_that_is_not_the_replays_ends_the_run(self):
        with self.assertRaises(SystemExit) as e, redirect_stdout(io.StringIO()):
            self.fx.run().mutant("mutant")
        self.assertIn("run the mutant replay first", str(e.exception))
        self.fx.replayed("0" * 64)
        with self.assertRaises(SystemExit) as e, redirect_stdout(io.StringIO()):
            self.fx.run().mutant("mutant")
        self.assertIn("is not the one the mutant replay ran (" + "0" * 64, str(e.exception))

    @cost("tool")
    def test_the_replays_mutant_is_recorded_as_constructed_and_its_run_leaves_the_identities(self):
        self.fx.replayed("0" * 64)
        with self.assertRaises(SystemExit) as e, redirect_stdout(io.StringIO()):
            self.fx.run().mutant("mutant")
        digest = re.search(r"sha256 ([0-9a-f]{64})", str(e.exception)).group(1)
        self.fx.replayed(digest)
        run = self.fx.run()
        jars, said = self.built(run)
        self.assertIn("the JAR the mutant replay ran", said)
        with zipfile.ZipFile(jars[0]) as z:
            self.assertNotEqual(z.read("fx/Gate.class"), (self.fx.root / "classes/fx/Gate.class").read_bytes())
            self.assertEqual(z.namelist(), ["META-INF/MANIFEST.MF", "fx/Gate.class"])
        self.assertEqual(run.used, [{"revision": "mutant", "name": "gate-1.0.jar", "sha256": digest, "constructed": True}])

        run = self.fx.run()
        with redirect_stdout(io.StringIO()):
            jars, adapter = run.prepared("mutant")
        bound = run.bound(2)
        argv = [str(self.fx.verifier), "prove", "--classes", str(adapter), "--json"]
        with self.assertRaises(SystemExit) as e, redirect_stdout(io.StringIO()) as out:
            run.finish(argv, bound, str(self.fx.verifier), self.fx.here / "target.json")
        self.assertEqual(e.exception.code, 0)  # the stand-in refutes, as the task expects
        self.assertIn("a trial at bound 2", out.getvalue())
        record = json.loads((run.work / "evidence.json").read_text())
        self.assertEqual(record["bound"], {"maxArrayLength": 2, "unwind": None, "trial": True})
        self.assertEqual(record["mutant"]["sha256"], digest)
        self.assertEqual(record["mutant"]["replayed"], digest)
        self.assertEqual([a["name"] for a in record["artifacts"]], ["gate-1.0.jar"])
        self.assertEqual(len(record["adapter"]["classes"]), 1)
        self.assertEqual(json.loads((run.work / "outcome.json").read_text())[0]["verdict"], "violation")

    @cost("tool")
    def test_a_pinned_jar_that_changed_ends_the_run(self):
        with zipfile.ZipFile(self.fx.jars / "gate-1.0.jar", "a") as z:
            z.writestr("extra.txt", "changed")
        with self.assertRaises(SystemExit) as e:
            self.fx.run("fixed-security").artifacts("fixed-release")
        self.assertIn("pinned to", str(e.exception))


if __name__ == "__main__":
    unittest.main()

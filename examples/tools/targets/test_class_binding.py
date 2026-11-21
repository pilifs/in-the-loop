#!/usr/bin/env python3
"""The selected class binding (class_binding.py, runtime.py's preparation and launch guard; lib/src/classpath.rs):
one answer to which class file stands for a class name, held to what a JVM loads
(llm-dlc/loops/lib-architecture-fast-follow.md, part 2).

The fixture is the design review's: a JAR with two implementations of `fixture.Gate.marker()I`, the base returning 1
and the Java 17 entry returning 17, built twice with manifests that differ only in how `Multi-Release`'s value is
spelled. On JDK 21 the first loads the versioned class and the second, its value folded over two lines, the base one.
Before, the preparation took the base class of both, and the launch guard and the checker the versioned class of both.

    python3 examples/tools/targets/test_class_binding.py
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

TOOLS = Path(__file__).resolve().parents[1]
REPO = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
from targets import class_binding, runtime, runtime_jar, runtime_jdk  # noqa: E402
sys.path.append(str(REPO / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[3] / "lib/tools"))
from cost_tier import cost  # noqa: E402

HEAD = b"Manifest-Version: 1.0\r\n"
ONE_LINE = HEAD + b"Multi-Release: true\r\n\r\n"
FOLDED = HEAD + b"Multi-Release: tr\r\n ue\r\n\r\n"
GATE = "fixture/Gate"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def jar(path, manifest, base, versioned=None, extra=()):
    with zipfile.ZipFile(path, "w") as z:
        entries = [("META-INF/MANIFEST.MF", manifest), ("fixture/Gate.class", base), *extra]
        if versioned is not None:
            entries.append(("META-INF/versions/17/fixture/Gate.class", versioned))
        for name, data in entries:
            if data is not None:
                z.writestr(zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0)), data)
    return path


class Inventory(unittest.TestCase):
    """What these tools do on their own: list a class's class files, and hand out bytes only where there is one."""

    def setUp(self):
        self.dir = Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_an_ordinary_class_has_one_class_file_and_is_read_as_it_always_was(self):
        path = jar(self.dir / "plain.jar", HEAD + b"\r\n", b"only")
        self.assertEqual(class_binding.candidates(path, GATE), [{"entry": "fixture/Gate.class", "sha256": sha(b"only"), "release": None}])
        self.assertEqual(class_binding.read(path, GATE), b"only")
        self.assertEqual(class_binding.read(path, GATE), runtime_jar.read_class(path, GATE))
        self.assertIsNone(class_binding.read(path, "fixture/Absent"))
        self.assertEqual(class_binding.candidates(path, "fixture/Absent"), [])
        classes = self.dir / "classes/fixture"
        classes.mkdir(parents=True)
        (classes / "Gate.class").write_bytes(b"in a directory")
        self.assertEqual(class_binding.read(self.dir / "classes", GATE), b"in a directory")

    def test_a_class_with_several_class_files_is_listed_whatever_the_manifest_says_and_not_read_unbound(self):
        for manifest in (ONE_LINE, FOLDED, HEAD + b"\r\n"):
            path = jar(self.dir / "mr.jar", manifest, b"base", b"for 17")
            self.assertEqual(class_binding.candidates(path, GATE), [
                {"entry": "fixture/Gate.class", "sha256": sha(b"base"), "release": None},
                {"entry": "META-INF/versions/17/fixture/Gate.class", "sha256": sha(b"for 17"), "release": 17}])
            with self.assertRaises(class_binding.Unbound) as refused:
                class_binding.read(path, GATE)
            self.assertEqual(refused.exception.refusal["code"], "unbound-class")
            self.assertEqual([c["sha256"] for c in refused.exception.refusal["candidates"]], [sha(b"base"), sha(b"for 17")])
            self.assertIn(sha(b"base"), str(refused.exception))
            self.assertIn(sha(b"for 17"), str(refused.exception))
            # With the entry a binding names, the bytes are that entry's.
            self.assertEqual(class_binding.read(path, GATE, "META-INF/versions/17/fixture/Gate.class"), b"for 17")
        only_versioned = jar(self.dir / "only.jar", ONE_LINE, None, b"for 17")
        with self.assertRaises(class_binding.Unbound):
            class_binding.read(only_versioned, GATE)

    def test_an_observation_binds_the_class_file_every_jdk_loaded_and_refuses_with_both_digests_otherwise(self):
        held = class_binding.candidates(jar(self.dir / "mr.jar", ONE_LINE, b"base", b"for 17"), GATE)
        bound = class_binding.observed("fixture.Gate", "mr.jar", held, {"21": ("mr.jar", sha(b"for 17")), "25": ("mr.jar", sha(b"for 17"))})
        self.assertEqual((bound["entry"], bound["sha256"], bound["release"], bound["jdks"]),
                         ("META-INF/versions/17/fixture/Gate.class", sha(b"for 17"), 17, ["21", "25"]))
        cases = (
            ({"8": ("mr.jar", sha(b"base")), "21": ("mr.jar", sha(b"for 17"))}, "observation-differs-by-jdk"),
            ({"21": ("other.jar", sha(b"for 17"))}, "observation-differs"),
            ({"21": ("mr.jar", sha(b"neither"))}, "observation-unmatched"),
            ({}, "unobserved-class"),
        )
        for seen, code in cases:
            with self.assertRaises(class_binding.Unbound) as refused:
                class_binding.observed("fixture.Gate", "mr.jar", held, seen)
            self.assertEqual(refused.exception.refusal["code"], code)
            self.assertEqual([(c["provider"], c["sha256"]) for c in refused.exception.refusal["candidates"]],
                             [("mr.jar", sha(b"base")), ("mr.jar", sha(b"for 17"))], "both digests, and where each is")

    def test_a_disagreement_names_both_digests_and_their_origins(self):
        binding = {"class": "fixture.Gate", "provider": "/w/mr.jar", "entry": "META-INF/versions/17/fixture/Gate.class",
                   "sha256": sha(b"for 17"), "selected_by": "rule"}
        self.assertIsNone(class_binding.disagreement("fixture.Gate", binding, "/w/mr.jar", sha(b"for 17")))
        said = class_binding.disagreement("fixture.Gate", binding, "/w/mr.jar", sha(b"base"))
        for part in (sha(b"for 17"), sha(b"base"), "/w/mr.jar!META-INF/versions/17/fixture/Gate.class", "the preparation bound /w/mr.jar"):
            self.assertIn(part, said)
        self.assertIn("/w/other.jar", class_binding.disagreement("fixture.Gate", binding, "/w/other.jar", sha(b"for 17")))
        refused = {"class": "fixture.Gate", "refused": {"code": "ambiguous-manifest", "reason": "readers differ",
                                                        "candidates": [{"entry": "fixture/Gate.class", "sha256": sha(b"base")}]}}
        said = class_binding.disagreement("fixture.Gate", refused, "/w/mr.jar", sha(b"base"))
        self.assertIn("ambiguous-manifest", said)
        self.assertIn(sha(b"base"), said)


def tool(home, name):
    return str(Path(home) / "bin" / name)


class Bound(unittest.TestCase):
    """The table, through the preparation, the JVMs and the checker as they are used."""

    @classmethod
    def setUpClass(cls):
        cls.homes = {f: runtime_jdk.home(f) for f in ("8", "21", "25")}
        cls.exe = runtime.jvmcontract()
        cls.scratch = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.scratch.name)
        if not cls.homes["21"]:
            return
        compiled = {}
        for value, release in ((1, "8"), (17, "17")):
            src = cls.dir / f"src-{value}/fixture"
            src.mkdir(parents=True)
            (src / "Gate.java").write_text("package fixture;\npublic class Gate { public static int marker() { return %d; } "
                                           "public static int marker(int by) { return %d * by; } }\n" % (value, value))
            subprocess.run([tool(cls.homes["21"], "javac"), "--release", release, "-d", str(cls.dir / f"classes-{value}"),
                            str(src / "Gate.java")], check=True, capture_output=True)
            compiled[value] = (cls.dir / f"classes-{value}/fixture/Gate.class").read_bytes()
        cls.base, cls.versioned = compiled[1], compiled[17]

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def setUp(self):
        if not self.homes["21"]:
            self.skipTest("no JDK 21 under " + str(runtime_jdk.CANDIDATES))

    def prepared(self, name, manifest, jdks, target="fixture.Gate#marker()I", versioned=True):
        """runtime._check_classpath on a work directory holding the JAR, with the preparation's own observer."""
        work = self.dir / name
        work.mkdir()
        jar(work / "gate.jar", manifest, self.base, self.versioned if versioned else None)
        build = runtime._Build(work, self.homes["21"], {})
        source = {"jdks": list(jdks)}
        plan = SimpleNamespace(target=target, kind="prove")
        return work, runtime._check_classpath(plan, work, ["gate.jar"], "gate.jar", None,
                                              observe=runtime._observer(build, source, work, ["gate.jar"]))

    def marker(self, work, feature):
        """What a JVM returns from an ordinary call of the gate: the cross-check on the observation."""
        probe = work / "call"
        probe.mkdir(exist_ok=True)
        (probe / "Call.java").write_text("public class Call { public static void main(String[] a) { System.out.println(fixture.Gate.marker()); } }\n")
        subprocess.run([tool(self.homes["21"], "javac"), "--release", "8", "-cp", str(work / "gate.jar"), "-d", str(probe),
                        str(probe / "Call.java")], check=True, capture_output=True)
        return subprocess.run([tool(self.homes[feature], "java"), "-cp", f"{work / 'gate.jar'}{os.pathsep}{probe}", "Call"],
                              capture_output=True, text=True, check=True).stdout.strip()

    @cost("tool")
    def test_the_preparation_binds_the_class_a_jvm_loads_for_both_spellings(self):
        table = (("one-line", ONE_LINE, self.versioned, "META-INF/versions/17/fixture/Gate.class", "17"),
                 ("folded", FOLDED, self.base, "fixture/Gate.class", "1"))
        for name, manifest, loaded, entry, returned in table:
            with self.subTest(name):
                work, target = self.prepared(name, manifest, ["21", "25"] if self.homes["25"] else ["21"])
                self.assertEqual((target["classSha256"], target["jarEntry"]), (sha(loaded), entry))
                self.assertEqual(target["classObservation"]["sha256"], sha(loaded))
                self.assertEqual([c["sha256"] for c in target["classObservation"]["candidates"]], [sha(self.base), sha(self.versioned)])
                self.assertEqual(self.marker(work, "21"), returned, "an ordinary call on that JVM runs the class that was bound")
                # Parameter names and every later reader take the bound entry, not the base one.
                bound = SimpleNamespace(source={"target": target})
                self.assertEqual(runtime.bound_class(work, bound, "gate.jar", "fixture.Gate"), loaded)
                self.assertEqual(runtime._parameters(SimpleNamespace(target="fixture.Gate#marker(I)I"), work, bound)["names"],
                                 runtime_jar.parameter_names(loaded, "marker", "(I)I")[0])

    @cost("tool")
    def test_an_ordinary_jar_is_prepared_exactly_as_before_and_runs_no_jvm(self):
        work, target = self.prepared("ordinary", HEAD + b"\r\n", ["21"], versioned=False)
        self.assertEqual(target, {"class": "fixture.Gate", "method": "marker", "descriptor": "()I", "loadedFrom": "gate.jar",
                                  "classSha256": sha(self.base)})
        self.assertFalse((work / "logs").exists(), "no probe was compiled or run")

    @cost("tool")
    def test_a_class_that_differs_by_jdk_a_missing_descriptor_and_a_route_with_no_observer_are_refused(self):
        if self.homes["8"]:
            with self.assertRaises(runtime.Refused) as refused:
                self.prepared("by-jdk", ONE_LINE, ["8", "21"])
            said = refused.exception.diagnostic
            self.assertEqual(refused.exception.stage, "classpath")
            for part in ("observation-differs-by-jdk", f"JDK 8 loaded sha256 {sha(self.base)}", f"JDK 21 loaded sha256 {sha(self.versioned)}",
                         "gate.jar!fixture/Gate.class", "gate.jar!META-INF/versions/17/fixture/Gate.class"):
                self.assertIn(part, said)
        with self.assertRaises(runtime.Refused) as refused:
            self.prepared("missing", ONE_LINE, ["21"], target="fixture.Gate#marker(J)I")
        self.assertEqual(refused.exception.stage, "target")
        self.assertIn("declares no method marker(J)I (it declares marker()I, (I)I)", refused.exception.diagnostic)
        work = self.dir / "no-observer"
        work.mkdir()
        jar(work / "gate.jar", ONE_LINE, self.base, self.versioned)
        with self.assertRaises(runtime.Refused) as refused:
            runtime._check_classpath(SimpleNamespace(target="fixture.Gate#marker()I", kind="prove"), work, ["gate.jar"], "gate.jar", None)
        self.assertIn("unobserved-class", refused.exception.diagnostic)

    def checker(self, work, observed=None, release="21", classpath=("gate.jar",), descriptor="()I"):
        env = {"PATH": f"{self.homes['21']}/bin:/usr/bin:/bin", "JAVA_HOME": self.homes["21"]}
        if release:
            env["JVMCONTRACT_JAR_RELEASE"] = release
        if observed:
            (work / "class-observations.json").write_text(json.dumps({"feature": 21, "classes": {"fixture.Gate": observed}}))
            env["JVMCONTRACT_CLASS_OBSERVATIONS"] = "class-observations.json"
        sides, bound = class_binding.ask(self.exe, env, work, {"side": {
            "classpath": [str(work / c) for c in classpath], "classes": [{"class": "fixture.Gate", "method": "marker", "descriptor": descriptor}]}})
        return sides["side"]["bindings"][0], bound

    @cost("tool")
    def test_the_checkers_binding_is_the_prepared_one_or_a_refusal_with_both_digests(self):
        if not self.exe:
            self.skipTest("no built jvmcontract (lib/target/release/jvmcontract)")
        one, one_target = self.prepared("guard-one-line", ONE_LINE, ["21"])
        folded, folded_target = self.prepared("guard-folded", FOLDED, ["21"])
        base, versioned = sha(self.base), sha(self.versioned)
        # Each JAR with the observation its preparation made: the checker binds the same bytes, and says how.
        binding, release = self.checker(one, one_target["classSha256"])
        self.assertEqual((binding["sha256"], binding["entry"], binding["selected_by"], release),
                         (versioned, "META-INF/versions/17/fixture/Gate.class", "rule-and-observation", 21))
        self.assertIsNone(class_binding.disagreement("fixture.Gate", binding, str(one / "gate.jar"), one_target["classSha256"]))
        self.assertEqual(binding["method"]["declared"], True)
        binding, _ = self.checker(folded, folded_target["classSha256"])
        self.assertEqual((binding["sha256"], binding["entry"], binding["selected_by"], binding["manifest"]),
                         (base, "fixture/Gate.class", "observation", "ambiguous"))
        self.assertIsNone(class_binding.disagreement("fixture.Gate", binding, str(folded / "gate.jar"), folded_target["classSha256"]))
        # The folded JAR with no observation: where the checker read the versioned class before, it now refuses.
        binding, _ = self.checker(folded)
        self.assertEqual(binding["refused"]["code"], "ambiguous-manifest")
        said = class_binding.disagreement("fixture.Gate", binding, str(folded / "gate.jar"), base)
        self.assertIn(base, said)
        self.assertIn(versioned, said)
        # The one-line JAR held to the digest the preparation used to record, the base class's: a refusal naming both.
        binding, _ = self.checker(one)
        said = class_binding.disagreement("fixture.Gate", binding, str(one / "gate.jar"), base)
        self.assertIn(f"gate.jar!META-INF/versions/17/fixture/Gate.class (sha256 {versioned}", said)
        self.assertIn(f"the preparation bound {one / 'gate.jar'} (sha256 {base})", said)
        # An observation of other bytes than the rule's, and no bound release, are the checker's own refusals.
        self.assertEqual(self.checker(one, base)[0]["refused"]["code"], "observation-differs")
        self.assertEqual(self.checker(one, release=None)[0]["refused"]["code"], "unbound-release")
        # A descriptor the bound class file does not declare is said, with the overloads it has.
        method = self.checker(one, versioned, descriptor="(J)I")[0]["method"]
        self.assertEqual((method["declared"], method["overloads"]), (False, ["()I", "(I)I"]))

    @cost("tool")
    def test_the_first_entry_on_the_class_path_provides_the_class_in_either_order(self):
        if not self.exe:
            self.skipTest("no built jvmcontract (lib/target/release/jvmcontract)")
        work = self.dir / "order"
        work.mkdir()
        jar(work / "one.jar", HEAD + b"\r\n", self.base)
        jar(work / "two.jar", HEAD + b"\r\n", self.versioned)
        for order, expected in ((("one.jar", "two.jar"), self.base), (("two.jar", "one.jar"), self.versioned)):
            binding, _ = self.checker(work, classpath=order)
            self.assertEqual((binding["sha256"], Path(binding["provider"]).name, binding["index"]), (sha(expected), order[0], 0))
            self.assertEqual([Path(c["provider"]).name for c in binding["shadowed"]], [order[1]])
            # The preparation's own policy is unchanged: a class two entries hold is refused there unless declared.
            self.assertEqual(runtime_jar.duplicates(list(order), work), [(GATE, list(order))])


class RealTarget(unittest.TestCase):
    """An existing target, not made for this test: Guava 33.4.8's `Ints`, the subject of example 336, from the
    artifact cache. Its recorded class digest is what the inventory, the old reader and the checker all bind."""

    JAR = Path.home() / ".cache/in-the-loop/targets/sha256/f3/f3d7f57f67fd622f4d468dfdd692b3a5e3909246c28017ac3263405f0fe617ed"

    def test_guavas_ints_binds_to_the_digest_example_336_recorded(self):
        records = sorted((TOOLS.parent / "336-guava-first-array-match/records/array-induction/first-any-length").glob("*/result.json"))
        recorded = json.loads(records[0].read_text())["classes"]["com/google/common/primitives/Ints"]["sha256"]
        if not self.JAR.is_file():
            self.skipTest("Guava 33.4.8 is not in the artifact cache")
        name = "com/google/common/primitives/Ints"
        self.assertEqual(class_binding.candidates(self.JAR, name), [{"entry": name + ".class", "sha256": recorded, "release": None}])
        self.assertEqual(sha(class_binding.read(self.JAR, name)), recorded)
        exe, home = runtime.jvmcontract(), runtime_jdk.home("21")
        if not exe or not home:
            self.skipTest("no built jvmcontract, or no JDK 21")
        for release in ("21", None):
            env = {"PATH": f"{home}/bin:/usr/bin:/bin", "JAVA_HOME": home, **({"JVMCONTRACT_JAR_RELEASE": release} if release else {})}
            sides, _ = class_binding.ask(exe, env, Path.cwd(), {"336": {"classpath": [str(self.JAR)], "classes": [
                {"class": "com.google.common.primitives.Ints", "method": "indexOf", "descriptor": "([II)I"}]}})
            binding = sides["336"]["bindings"][0]
            self.assertEqual((binding["sha256"], binding["entry"], binding["selected_by"], binding["method"]["declared"]),
                             (recorded, name + ".class", "rule", True))
            self.assertIsNone(class_binding.disagreement("com.google.common.primitives.Ints", binding, str(self.JAR), recorded))


if __name__ == "__main__":
    unittest.main()

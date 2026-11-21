"""Class-file and observed-return checks used by the public dependency-upgrade review."""
import base64
import sys
import json
import subprocess
import tempfile
import zipfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from targets import runtime_jar, runtime_jdk, upgrade_claims, upgrade_replay
sys.path.append(str(Path(__file__).resolve().parents[3] / "lib/tools"))
from cost_tier import cost
sys.path.append(str(Path(__file__).resolve().parents[3] / "lib/tools"))
from cost_tier import cost  # noqa: E402


class UpgradeReviewTest(unittest.TestCase):
    def prepared_pair(self, root, jdk, client, versions):
        client_source = root / "Real.java"
        client_source.write_text("package app; public class Real { " + client + " }")
        prepared, dependencies = [], []
        for side, methods in versions.items():
            classes = root / side
            classes.mkdir()
            source = root / "Number.java"
            source.write_text("package dep; public class Number { " + methods + " }")
            subprocess.run([str(jdk / "bin/javac"), "-J-Djava.io.tmpdir=" + str(root), "-d", str(classes),
                            str(client_source), str(source)], check=True, capture_output=True)
            rows = []
            for owner in ("app/Real", "dep/Number"):
                jar = classes / (owner.split("/")[-1] + ".jar")
                with zipfile.ZipFile(jar, "w") as archive:
                    archive.write(classes / (owner + ".class"), owner + ".class")
                    for member in classes.glob(owner + "$*.class"):
                        archive.write(member, member.relative_to(classes).as_posix())
                rows.append({"file": str(jar), "sha256": upgrade_replay.sha(jar)})
            path = classes / "prepared.json"
            path.write_text(json.dumps({"commit": side, "sourceSha256": upgrade_replay.sha(client_source), "classpath": rows}))
            prepared.append(path)
            dependencies.append(rows[1]["sha256"])
        return prepared, dependencies

    @cost("tool")
    def test_loading_a_caller_and_referencing_an_unexecuted_call_cannot_qualify_an_input(self):
        jdk = runtime_jdk.home("21")
        if not jdk:
            self.skipTest("requires JDK 21")
        jdk = Path(jdk)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared, dependencies = self.prepared_pair(root, jdk,
                "public static int call() { return dep.Number.value(); } public static int wrapper() { return call(); }",
                {side: "public static int value() { return " + n + "; }" for side, n in (("old", "7"), ("new", "8"))})
            probe = root / "UpgradeProbe.java"
            probe.write_text("public class UpgradeProbe { public static String observe(String[] x) { "
                             "if (x.length == 1) return app.Real.class.getName(); "
                             "return Integer.toString(app.Real.call()); } }")
            spec = root / "scope.json"
            spec.write_text(json.dumps({"entry": "app.Real#call()I", "observer": "returned text", "basis": "control",
                                       "probeClass": "UpgradeProbe", "cases": [{"args": ["skip"], "expected": {"return": "app.Real"}}]}))
            with self.assertRaisesRegex(ValueError, "original caller method was never entered"):
                upgrade_replay.evaluate(spec, *prepared, probe, jdk, dependencies, 30)

            # The genuine wrapper reaches call() on the same stack. An earlier independent
            # call cannot qualify a wrapper that was only referenced in a dormant branch.
            scope = json.loads(spec.read_text())
            scope["invocationVia"] = "app.Real#wrapper()I"
            scope["cases"] = [{"args": ["run"], "expected": {"return": "7"}}]
            spec.write_text(json.dumps(scope))
            probe.write_text("public class UpgradeProbe { public static String observe(String[] x) { "
                             "System.out.println(\"UPGRADE-OBSERVATION return invalid!\"); "
                             "System.err.println(\"UPGRADE-DETAIL invalid!\"); "
                             "return Integer.toString(app.Real.wrapper()); } }")
            result = upgrade_replay.evaluate(spec, *prepared, probe, jdk, dependencies, 30)
            self.assertEqual((result["status"], result["differences"]), ("changed", [0]))
            probe.write_text("public class UpgradeProbe { public static String observe(String[] x) { "
                             "return Integer.toString(x.length == 1 ? app.Real.call() : app.Real.wrapper()); } }")
            with self.assertRaisesRegex(ValueError, "original caller method was never entered"):
                upgrade_replay.evaluate(spec, *prepared, probe, jdk, dependencies, 30)

    @cost("tool")
    def test_failure_before_entry_is_bound_to_the_escaping_object_and_original_jars(self):
        home = runtime_jdk.home("21")
        if not home:
            self.skipTest("requires JDK 21")
        jdk = Path(home)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared, dependencies = self.prepared_pair(root, jdk,
                "public static void prepare() { dep.Number.prepare(); } public static int call() { return 7; }",
                {"old": "public static void prepare() {}",
                 "new": "public static void prepare() { IllegalStateException problem = new IllegalStateException(); "
                        "problem.setStackTrace(new StackTraceElement[0]); throw problem; }"})
            probe = root / "UpgradeProbe.java"
            probe.write_text("""public class UpgradeProbe {
                public static String observe(String[] input) {
                    if (input[0].equals("replace")) {
                        try { app.Real.prepare(); }
                        catch (IllegalStateException original) { throw new IllegalStateException("observer"); }
                    } else {
                        try { app.Real.prepare(); } finally { System.nanoTime(); }
                    }
                    return Integer.toString(app.Real.call());
                }
            }""")
            spec = root / "scope.json"
            spec.write_text(json.dumps({"entry": "app.Real#call()I", "observer": "return", "basis": "fixture",
                "probeClass": "UpgradeProbe", "cases": [{"args": [value], "expected": {"return": "7"}}
                                                       for value in ("original", "replace")]}))
            result = upgrade_replay.evaluate(spec, *prepared, probe, jdk, dependencies, 30)
            self.assertEqual(result["status"], "open")
            primary, replaced = result["sides"]["new"]["trials"]
            self.assertEqual(primary["qualifiedMethodEntries"], 0)
            self.assertEqual(primary["observations"], [])
            self.assertTrue(primary["repeatableBeforeEntry"])
            self.assertEqual([(f["entry"], f["artifact"]) for f in primary["beforeEntry"][0]["frames"]],
                             [("dep.Number#prepare()V", "upgrade"), ("app.Real#prepare()V", "client")])
            self.assertEqual(primary["beforeEntry"][0]["subsequentRethrows"][-1]["frames"], [])
            self.assertEqual(replaced["beforeEntry"][0]["frames"], [])
            self.assertEqual([c["status"] for c in result["beforeEntryComparison"]],
                             ["reproduced earlier failure", "unqualified"])
            scope = json.loads(spec.read_text())
            scope["operandScope"] = "provided"
            spec.write_text(json.dumps(scope))
            with self.assertRaisesRegex(ValueError, "declared provided dependency environment"):
                upgrade_replay.evaluate(spec, *prepared, probe, jdk, dependencies, 30)

    def test_only_instructions_from_the_selected_overload_supply_call_evidence(self):
        text = """public class app.Client {
  public java.lang.String read(int);
    descriptor: (I)Ljava/lang/String;
    Code:
       0: invokestatic  #17   // Method dep/Store.read:(I)Ljava/lang/String;
       3: areturn

  public java.lang.String read();
    descriptor: ()Ljava/lang/String;
    Code:
       0: invokevirtual #3    // Method fallback:()Ljava/lang/String;
       3: areturn
}
"""
        edges = upgrade_claims.calls_in_methods(text, "app/Client")
        self.assertEqual(edges["read", "(I)Ljava/lang/String;"], [("dep/Store", "read", "(I)Ljava/lang/String;")])
        self.assertEqual(edges["read", "()Ljava/lang/String;"], [("app/Client", "fallback", "()Ljava/lang/String;")])

    @cost("tool")
    def test_old_loaded_type_is_absent_on_the_new_jvm_and_a_string_is_not_a_type_reference(self):
        home = runtime_jdk.home("21")
        if not home:
            self.skipTest("requires JDK 21")
        jdk = Path(home)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            method = "public static int value() { return 7; }"
            prepared, dependencies = self.prepared_pair(root, jdk, "public static int call() { return dep.Number.value(); }", {
                "old": method + " public static class Gone {} public static Gone[] items() { return null; }",
                "new": method + ' public static String name() { return "dep/Number$Gone"; }'})
            for side, expected in (("old", True), ("new", False)):
                data = (root / side / "dep/Number.class").read_bytes()
                refs = runtime_jar.type_references(data, "dep/Number$Gone")
                kinds = refs["kinds"]
                self.assertEqual(refs["methods"], ["items()[Ldep/Number$Gone;"] if expected else [])
                self.assertEqual("method declaration" in kinds, expected)
                self.assertEqual(bool(kinds), expected)
            probe = root / "UpgradeProbe.java"
            probe.write_text('public class UpgradeProbe { public static String observe(String[] args) { '
                             'return dep.Number.Gone.class.getSimpleName() + "/" + app.Real.call(); } }')
            spec = root / "scope.json"
            spec.write_text(json.dumps({"entry": "app.Real#call()I", "observer": "return", "basis": "fixture",
                "probeClass": "UpgradeProbe", "cases": [{"args": [], "expected": {"return": "Gone/7"}}]}))
            report = upgrade_replay.evaluate(spec, *prepared, probe, jdk, dependencies, 30)
            self.assertEqual(report["status"], "open")
            row = report["beforeEntryComparison"][0]
            self.assertIn("missingClass", row, report.get("missingClassEvidence"))
            self.assertEqual(row["missingClass"]["relationship"], "old upgraded artifact supplied the missing class")
            evidence = report["missingClassEvidence"]["dep.Number$Gone"]
            self.assertEqual(evidence["old"]["lookup"]["jarSha256"], dependencies[0])
            self.assertEqual(evidence["new"]["lookup"], {"outcome": "missing"})
            self.assertEqual(evidence["new"]["providers"], [])

    def test_observations_require_the_original_caller_and_preserve_utf16_and_null(self):
        client, library = Path("/original/client.jar"), Path("/original/library.jar")
        entry = "app.Client#read()Ljava/lang/String;"
        origins = "[Loaded app.Client from file:/original/client.jar]\n[0.01s][info][class,load] dep.Reader source: file:/original/library.jar\n"
        value = "\ud800\0"
        raw = base64.b64encode(value.encode("utf-16-be", "surrogatepass")).decode()
        self.assertEqual(upgrade_replay.parse_output(origins + "UPGRADE-OBSERVATION return " + raw,
                                                     entry, client, library), ({"return": value}, ["dep.Reader"]))
        self.assertEqual(upgrade_replay.parse_output(origins + "UPGRADE-OBSERVATION return -", entry, client, library)[0],
                         {"return": None})
        with self.assertRaisesRegex(ValueError, "original client"):
            upgrade_replay.parse_output(origins.replace("client.jar", "shadow.jar"), entry, client, library)
        failed = origins + "UPGRADE-OBSERVATION throw java.lang.IllegalStateException\n"
        with self.assertRaisesRegex(ValueError, "outside"):
            upgrade_replay.parse_output(failed, entry, client, library)
        self.assertEqual(upgrade_replay.parse_output(failed + "UPGRADE-FRAME app.Client#read", entry, client, library)[0],
                         {"throws": "java.lang.IllegalStateException"})


if __name__ == "__main__":
    unittest.main()

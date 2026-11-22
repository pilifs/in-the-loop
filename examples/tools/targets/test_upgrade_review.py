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
from targets import runtime_jar, runtime_jdk, upgrade_claims, upgrade_jdbc, upgrade_replay
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
    def test_interface_call_site_and_escaping_throwable_are_observed_in_the_live_jvm(self):
        home = runtime_jdk.home("21")
        if not home:
            self.skipTest("requires JDK 21")
        jdk = Path(home)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = """public interface Service { int read(); }
                public static class Proxy implements Service { public int read() { return new Real().call(); } }
                private final Object alias = this;
                private Object empty;
                public int call() { return dep.Number.value(); }"""
            prepared, dependencies = self.prepared_pair(root, jdk, client, {
                "old": "public static int value() { return 7; }",
                "new": """public static int value() { IllegalStateException failure = new IllegalStateException();
                    failure.setStackTrace(new StackTraceElement[0]); throw failure; }"""})
            probe = root / "UpgradeProbe.java"
            probe.write_text("""public class UpgradeProbe { public static String observe(String[] x) {
                app.Real.Service service = new app.Real.Proxy();
                return Integer.toString(service.read());
            } }""")
            spec = root / "scope.json"
            spec.write_text(json.dumps({"entry": "app.Real#call()I", "invocationVia": "app.Real$Service#read()I",
                "probeClass": "UpgradeProbe", "observer": "service response", "basis": "control",
                "cases": [{"args": [], "expected": {"return": "7"}}]}))
            result = upgrade_replay.evaluate(spec, *prepared, probe, jdk, dependencies, 30, inspect_receiver=True)
            self.assertEqual(result["status"], "changed")
            for side in result["sides"].values():
                first, again = side["trials"][0]["receiverAtEntry"]
                self.assertEqual(first, again)
                self.assertEqual(first["entry"]["this"], "Lapp/Real;@0")
                self.assertEqual(first["entry"]["fields"], {"app.Real#alias:Ljava/lang/Object;": "Lapp/Real;@0",
                                                          "app.Real#empty:Ljava/lang/Object;": "null"})
                ctor, = first["observedConstructorEntries"]
                self.assertEqual((ctor["descriptor"], ctor["calledBy"]), ("()V", "app.Real$Proxy#read()I"))
                entries = side["trials"][0]["entryInvocations"]
                self.assertEqual([e["dispatchedTo"] for e in entries], ["app.Real$Proxy#read()I"] * 2)
                self.assertEqual({e["observerCodeIndex"] for e in entries}, set(result["observerInvocation"]["codeIndices"]))
            escapes = result["sides"]["new"]["trials"][0]["escapingExceptions"]
            self.assertEqual([e["entry"] for e in escapes], ["app.Real#call()I"] * 2)
            probe.write_text("""public class UpgradeProbe { public static String observe(String[] x) {
                app.Real.Service service = new app.Real.Proxy();
                service.read();
                RuntimeException fake = new IllegalStateException();
                fake.setStackTrace(new StackTraceElement[]{new StackTraceElement("app.Real", "call", "Real.java", 1)});
                throw fake;
            } }""")
            with self.assertRaisesRegex(ValueError, "outside the declared original caller"):
                upgrade_replay.evaluate(spec, *prepared, probe, jdk, dependencies, 30)
            # A fixture JAR that supplies the upgrade on its own cannot qualify as a runtime operand.
            fixture = json.loads(prepared[0].read_text())
            fixture.update(operandScope="runtime", modulePomSha256="pom",
                           frameworkFixtures={"runtimeCount": 1, "testClassesSha256": dependencies[0]})
            prepared[0].write_text(json.dumps(fixture))
            with self.assertRaisesRegex(ValueError, "original production runtime"):
                upgrade_replay.check_input(prepared[0], "app.Real#call()I", dependencies[0])

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
    def test_wrapped_field_error_uses_the_live_instruction_and_both_jvm_lookups(self):
        home = runtime_jdk.home("21")
        if not home:
            self.skipTest("requires JDK 21")
        jdk = Path(home)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = """public static int call() { return 7; }
                public static int prepare() {
                    try { return (int) dep.Number.flag; }
                    catch (LinkageError e) { e.setStackTrace(new StackTraceElement[0]); throw new IllegalStateException(e); }
                }"""
            prepared, dependencies = self.prepared_pair(root, jdk, client, {
                "old": "public static int flag = 4;", "new": "public static long flag = 4;"})
            # Deploy the same precompiled consumer on both dependency versions.
            new = json.loads(prepared[1].read_text())
            new["classpath"][0] = json.loads(prepared[0].read_text())["classpath"][0]
            prepared[1].write_text(json.dumps(new))
            probe = root / "UpgradeProbe.java"
            probe.write_text("public class UpgradeProbe { public static String observe(String[] x) { "
                             "app.Real.prepare(); return Integer.toString(app.Real.call()); } }")
            spec = root / "scope.json"
            spec.write_text(json.dumps({"entry": "app.Real#call()I", "observer": "service response", "basis": "control",
                "probeClass": "UpgradeProbe", "cases": [{"args": [], "expected": {"return": "7"}}]}))
            result = upgrade_replay.evaluate(spec, *prepared, probe, jdk, dependencies, 30)
            self.assertEqual(result["status"], "open")
            link = result["beforeEntryComparison"][0]["memberLinkage"]
            instruction = link["instruction"]
            self.assertEqual((instruction["opcode"], instruction["name"], instruction["descriptor"]), ("getstatic", "flag", "I"))
            self.assertEqual((link["sides"]["old"]["lookup"], link["sides"]["new"]["lookup"]), ("found", "missing"))
            self.assertEqual(instruction["ownerJarSha256"], dependencies[1])
            loc = instruction["location"]
            raw = (root / "old/app/Real.class").read_bytes()
            self.assertIsNone(runtime_jar.member_at_code_index(raw, "prepare", "()I", loc["codeIndex"],
                              code_sha256=loc["methodCodeSha256"], pool_sha256="different pool"))
            # A changed runtime may appear deeper in a stack whose throwing instruction belongs to the client.
            for attempt in result["sides"]["new"]["trials"][0]["beforeEntry"]:
                attempt["rootThrow"]["frames"].append({"entry": "dep.Number#dispatch()V", "classpathIndex": 1,
                                                       "jarSha256": dependencies[1], "artifact": "upgrade"})
            compared = upgrade_replay.compare_before_entry(result["sides"], result["cases"])
            self.assertNotIn("changedRuntimeCause", compared[0])

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
        with self.assertRaisesRegex(ValueError, "outside"):
            upgrade_replay.parse_output(failed + "UPGRADE-FRAME app.Client#read", entry, client, library)

    def test_driver_message_from_application_code_cannot_diagnose_a_jdk_connection_failure(self):
        self.assertEqual(upgrade_replay.exception_types("app.Failure", ["app.Failure", "java.lang.ClassNotFoundException"]), "app.Failure")
        self.assertEqual(upgrade_replay.exception_types("app.Failure", ["app.Failure", "java.sql.SQLException"]),
                         "app.Failure,java.sql.SQLException")
        expected = {"return": "row"}
        failed = {"causes": ["java.sql.SQLException"], "lastCauseMessage": "No suitable driver found for jdbc:sample:test",
                  "throwLocation": {"entry": "app.Store#getConnection()V"}}
        old = {"qualifiedMethodEntries": 2, "observations": [expected, expected], "loadedUpgradeOnEachReplay": True}
        new = {"repeatableBeforeEntry": True, "beforeEntry": [failed, failed]}
        report = {"cases": [{"expected": expected}], "beforeEntryComparison": [{"input": 0}],
                  "sides": {"old": {"trials": [old]}, "new": {"trials": [new]}}}
        upgrade_jdbc.diagnose(report, {}, {}, 8, None, None, None, {}, 0)
        self.assertNotIn("jdbcDriverEvidence", report)


if __name__ == "__main__":
    unittest.main()

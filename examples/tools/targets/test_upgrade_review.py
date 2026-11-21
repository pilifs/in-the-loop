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
from targets import runtime_jdk, upgrade_claims, upgrade_replay
sys.path.append(str(Path(__file__).resolve().parents[3] / "lib/tools"))
from cost_tier import cost
sys.path.append(str(Path(__file__).resolve().parents[3] / "lib/tools"))
from cost_tier import cost  # noqa: E402


class UpgradeReviewTest(unittest.TestCase):
    @cost("tool")
    def test_loading_a_caller_and_referencing_an_unexecuted_call_cannot_qualify_an_input(self):
        jdk = runtime_jdk.home("21")
        if not jdk:
            self.skipTest("requires JDK 21")
        jdk = Path(jdk)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            client_source = root / "Real.java"
            client_source.write_text("package app; public class Real { public static int call() { return dep.Number.value(); } }")
            prepared, dependencies = [], []
            for side, number in (("old", "7"), ("new", "8")):
                classes = root / side
                classes.mkdir()
                source = root / "Number.java"
                source.write_text("package dep; public class Number { public static int value() { return " + number + "; } }")
                subprocess.run([str(jdk / "bin/javac"), "-J-Djava.io.tmpdir=" + tmp, "-d", str(classes),
                                str(client_source), str(source)], check=True, capture_output=True)
                rows = []
                for owner in ("app/Real", "dep/Number"):
                    jar = classes / (owner.split("/")[-1] + ".jar")
                    with zipfile.ZipFile(jar, "w") as archive:
                        archive.write(classes / (owner + ".class"), owner + ".class")
                    rows.append({"file": str(jar), "sha256": upgrade_replay.sha(jar)})
                path = classes / "prepared.json"
                path.write_text(json.dumps({"commit": side, "sourceSha256": upgrade_replay.sha(client_source),
                                            "classpath": rows}))
                prepared.append(path)
                dependencies.append(rows[1]["sha256"])
            probe = root / "UpgradeProbe.java"
            probe.write_text("public class UpgradeProbe { public static String observe(String[] x) { "
                             "if (x.length == 1) return app.Real.class.getName(); "
                             "return Integer.toString(app.Real.call()); } }")
            spec = root / "scope.json"
            spec.write_text(json.dumps({"entry": "app.Real#call()I", "observer": "returned text", "basis": "control",
                                       "probeClass": "UpgradeProbe", "cases": [{"args": ["skip"], "expected": {"return": "app.Real"}}]}))
            with self.assertRaisesRegex(ValueError, "original caller method was never entered"):
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

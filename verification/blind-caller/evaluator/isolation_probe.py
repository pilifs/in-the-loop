"""Exercise both phase boundaries on a synthetic public caller and a real private file."""
import argparse
import hashlib
from pathlib import Path
import tempfile

from eligibility_inventory import HERE, JDKS, write
from packet_view import clean_description, clean_production, is_production
from sandbox_runner import launch


STATIC = """import json, pathlib, sys
packet, out = map(pathlib.Path, sys.argv[1:])
info = json.loads((packet / "packet.json").read_bytes())
(out / "seen").write_text(info["title"])
"""
MEASURE = """import json, pathlib, subprocess, sys
packet, sealed, out = map(pathlib.Path, sys.argv[1:])
jdk = pathlib.Path(json.loads((packet / "packet.json").read_bytes())["jdk"])
(out / "Observation.java").write_text('public class Observation { public static void main(String[] args) { System.out.print(17); } }')
(out / "TraceCheck.java").write_text('''
import com.sun.jdi.Bootstrap;
public class TraceCheck {
  public static void main(String[] args) throws Exception {
    var connector = Bootstrap.virtualMachineManager().defaultConnector();
    var configuration = connector.defaultArguments();
    configuration.get("main").setValue("Observation");
    configuration.get("options").setValue("-cp " + args[0]);
    var vm = connector.launch(configuration);
    vm.resume();
    System.out.write(vm.process().getInputStream().readAllBytes());
    if (vm.process().waitFor() != 0) throw new IllegalStateException("child failed");
  }
}
''')
subprocess.run([jdk / "bin/javac", "-proc:none", "--add-modules", "jdk.jdi", out / "TraceCheck.java", out / "Observation.java"], check=True)
value = subprocess.check_output([jdk / "bin/java", "-cp", out, "Observation"])
traced = subprocess.check_output([jdk / "bin/java", "--add-modules", "jdk.jdi", "-cp", out, "TraceCheck", out])
if traced != value:
    raise ValueError("plain and JDI child outputs differ")
(out / "seen").write_bytes((sealed / "seen").read_bytes() + value)
"""


def probe(output):
    jdk = JDKS / "17.0.21.0+9-tem"
    with tempfile.TemporaryDirectory(prefix="caller-boundary-probe-") as temporary:
        scratch = Path(temporary)
        packet, product = scratch / "packet", scratch / "product"
        packet.mkdir()
        product.mkdir()
        marker = scratch / "evaluator-only"
        marker.write_text("private synthetic sentinel")
        token = "visible prose"
        disguised = token + "\n\n```java\n@Test void planted() {}\n```"
        source = "/* @Test void planted() {} */ class Public {}"
        if (clean_description(disguised) != token or "planted" in clean_production(source)
                or is_production("upstream/src/test/java/fixture/UserHistory.java")):
            raise ValueError("an embedded test survived view construction")
        write(packet / "packet.json", {"title": clean_description(disguised), "jdk": str(jdk)})
        policies = []
        sealed = None
        for phase, code, wanted in (("predict", STATIC, token), ("measure", MEASURE, token + "17")):
            worker = product / f"{phase}.py"
            worker.write_text(code)
            diagnostic = scratch / "synthetic-stderr"
            out, policy = launch(phase, product, packet, scratch / phase, jdk, marker,
                                 worker_path=worker, sealed=sealed, diagnostic_path=diagnostic)
            if not (policy["landlockSentinelDenied"] and policy["networkDenied"] and policy["exitCode"] == 0
                    and (out / "seen").read_text() == wanted):
                raise ValueError(f"synthetic {phase} failed: {diagnostic.read_text(errors='replace')[-1200:]}")
            if phase == "predict" and not (policy["predictionSubprocessDenied"] and policy["predictionExecutableMappingDenied"]):
                raise ValueError("prediction retained executable access")
            policies.append({k: v for k, v in policy.items() if k not in ("stderrSha256", "stderrBytes")})
            sealed = out
        record = {"schema": "caller-isolation-probe/v1", "prediction": policies[0], "measurement": policies[1],
                  "privateSentinelExisted": True, "embeddedListingOmitted": True, "plainEqualsJdiChild": True,
                  "unchangedSyntheticOutput": token + "17", "jdkReleaseSha256": hashlib.sha256((jdk / "release").read_bytes()).hexdigest()}
        write(output, record)
        print("two isolated phases, two sentinel denials, private tracer loopback, one observed Java output")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "isolation-evidence.json")
    probe(parser.parse_args().output)

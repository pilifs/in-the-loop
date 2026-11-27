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
subprocess.run([jdk / "bin/javac", "-proc:none", out / "Observation.java"], check=True)
value = subprocess.check_output([jdk / "bin/java", "-cp", out, "Observation"])
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
            out, policy = launch(phase, product, packet, scratch / phase, jdk, marker,
                                 worker_path=worker, sealed=sealed)
            if not (policy["landlockSentinelDenied"] and policy["networkDenied"] and policy["exitCode"] == 0
                    and (out / "seen").read_text() == wanted):
                raise ValueError(f"boundary or public observation failed in {phase}: {policy}")
            if phase == "predict" and not (policy["predictionSubprocessDenied"] and policy["predictionExecutableMappingDenied"]):
                raise ValueError("prediction retained executable access")
            policies.append({k: v for k, v in policy.items() if k not in ("stderrSha256", "stderrBytes")})
            sealed = out
        record = {"schema": "caller-isolation-probe/v1", "prediction": policies[0], "measurement": policies[1],
                  "privateSentinelExisted": True, "embeddedListingOmitted": True,
                  "unchangedSyntheticOutput": token + "17", "jdkReleaseSha256": hashlib.sha256((jdk / "release").read_bytes()).hexdigest()}
        write(output, record)
        print("two isolated phases, two sentinel denials, two socket denials, one observed Java output")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "isolation-evidence.json")
    probe(parser.parse_args().output)

"""Prove all bytes and the end of the binder's factory stream on both deployment graphs."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from binding_resources import ENTRY, FOLDER
from historical_companion import prepare_graph
from measure import ROOT, digest, read, write
from targets import runtime

sys.path.insert(0, str(ROOT / "lib/benchmark/java-domain-proof"))
from companions import proof

SOURCE = FOLDER / "companions/FactoryStream.java"
DEST = FOLDER / "records/factory-stream"
TARGET = "springwork.FactoryStreamWitness#check()"
BOUNDS = (256, 16384)


def witness(data):
    if not 1 <= len(data) <= BOUNDS[0]:
        raise ValueError("factory resource is missing or larger than the stream bound")
    values = ", ".join(str(i if i < 128 else i - 256) for i in data)
    return '''package springwork;

public final class FactoryStreamWitness {
    public static int check() throws java.io.IOException {
        byte[] expected = new byte[]{''' + values + '''};
        if (!FactoryStream.matches(expected)) return 0;
        expected[expected.length - 1] ^= 1;
        return FactoryStream.matches(expected) ? 0 : 1;
    }
    public static void main(String[] args) throws Exception {
        System.out.println(check());
    }
}
'''


def measure(side, replay):
    with tempfile.TemporaryDirectory(prefix="factory-stream-") as scratch:
        work = Path(scratch)
        jdk, graph, paths, bound = prepare_graph(FOLDER, side, "beans-" + side, work)
        resources = read(FOLDER / "records/factory-resources" / side / "measurement.json")
        if resources["classpath"] != bound[1:] or len(resources["resources"]) != 1:
            raise ValueError("different factory resources or deployment")
        item, = resources["resources"]
        jar, = [p for p, b in zip(paths, bound, strict=True) if b["sha256"] == item["jarSha256"]]
        with zipfile.ZipFile(jar) as archive:
            data = archive.read(ENTRY)
        if hashlib.sha256(data).hexdigest() != item["entrySha256"]:
            raise ValueError("resource bytes differ from the independent JVM enumeration")
        classes = work / "classes"
        classes.mkdir()
        entry = work / "FactoryStreamWitness.java"
        entry.write_text(witness(data))
        cp = os.pathsep.join(map(str, paths[1:]))
        subprocess.run([jdk / "bin/javac", "--release", "21", "-proc:none", "-cp", cp, "-d", classes, SOURCE, entry], check=True)
        env = runtime._verifier_env({"home": str(jdk)})
        env["JVMCONTRACT_JAR_RELEASE"] = "21"
        raw = subprocess.check_output([jdk / "bin/java", "-cp", str(classes) + os.pathsep + cp, TARGET.split("#")[0]], env=env)
        if raw != b"1\n":
            raise ValueError("JVM stream or last-byte control disagrees with archive")
        print(side, len(data), "bytes and a one-bit difference in the final byte", flush=True)
        if replay:
            return
        scope = DEST / side
        scope.mkdir(parents=True, exist_ok=True)
        (scope / "FactoryStreamWitness.java").write_bytes(entry.read_bytes())
        for name in ["FactoryStream", "FactoryStreamWitness"]:
            (scope / (name + ".jvm-bytecode")).write_bytes((classes / "springwork" / (name + ".class")).read_bytes())
        (scope / "entry.bin").write_bytes(data)
        (scope / "jvm.stdout").write_bytes(raw)
        checker = Path(os.environ["JVMCONTRACT"])
        result = proof(checker, classes, paths[1:], work, env, scope, TARGET, "stream", bounds=BOUNDS)
        if result["verdict"] != "verified" or result["observedRoots"] or result["states"]:
            raise ValueError(f"ordinary factory-stream proof: {result['blocker']}")
        write(scope / "measurement.json", {"job": os.environ["VERIFY_JOB_ID"], "source": os.environ["VERIFY_SOURCE_COMMIT"],
              "checkerSha256": digest(checker), "libTree": os.environ["JVMCONTRACT_LIB_TREE"], "classpath": bound[1:],
              "jdk": graph["jdk"], "provider": item, "bytes": len(data), "sourceSha256": digest(SOURCE),
              "callerSha256": digest(scope / "FactoryStream.jvm-bytecode"), "entryClassSha256": digest(scope / "FactoryStreamWitness.jvm-bytecode"),
              "jvmSha256": digest(scope / "jvm.stdout"), "result": result})


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--replay", action="store_true")
    args = cli.parse_args()
    for side in ("release", "combined"):
        measure(side, args.replay)

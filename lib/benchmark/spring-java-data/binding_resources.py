"""Replay the binder's factory resource lookup and bind each URL's bytes to its ordered input JAR."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

from historical_companion import prepare_graph
from measure import ROOT, digest, write
from targets import runtime

FOLDER = ROOT / "examples/368-spring-binding-history"
SOURCE = FOLDER / "companions/FactoryResources.java"
ENTRY = "META-INF/spring.factories"


def measure(side, replay):
    with tempfile.TemporaryDirectory(prefix="binding-resources-") as scratch:
        work = Path(scratch)
        jdk, graph, paths, bound = prepare_graph(FOLDER, side, "beans-" + side, work)
        jars = paths[1:]
        cp = os.pathsep.join(map(str, jars))
        classes = work / "classes"
        classes.mkdir()
        subprocess.run([jdk / "bin/javac", "--release", "21", "-proc:none", "-cp", cp, "-d", classes, SOURCE], check=True)
        raw = subprocess.check_output([jdk / "bin/java", "-cp", str(classes) + os.pathsep + cp, "springwork.FactoryResources"],
                                      env=runtime._verifier_env({"home": str(jdk)}))
        expected = []
        for jar, stamp in zip(jars, bound[1:], strict=True):
            with zipfile.ZipFile(jar) as archive:
                if ENTRY in archive.namelist():
                    expected.append({"jar": jar.name, "jarSha256": stamp["sha256"], "entry": ENTRY,
                                     "entrySha256": hashlib.sha256(archive.read(ENTRY)).hexdigest()})
        rows = [row.split("\t") for row in raw.decode().splitlines()]
        if [[a["jar"], a["entrySha256"]] for a in expected] != [row[:2] for row in rows]:
            raise ValueError("the JVM's ordered URLs differ from the resource bytes in the frozen JARs")
        for item, (_, _, factories) in zip(expected, rows, strict=True):
            item["beanInfoFactory"] = factories
        print(side, [(i["jar"], i["beanInfoFactory"]) for i in expected], flush=True)
        if replay:
            return
        dest = FOLDER / "records/factory-resources" / side
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "jvm.stdout").write_bytes(raw)
        write(dest / "measurement.json", {"job": os.environ["VERIFY_JOB_ID"], "source": os.environ["VERIFY_SOURCE_COMMIT"],
              "sourceSha256": digest(SOURCE), "jdk": graph["jdk"], "classpath": bound[1:],
              "jvmSha256": digest(dest / "jvm.stdout"), "resources": expected})


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--replay", action="store_true")
    args = cli.parse_args()
    for side in ("release", "combined"):
        measure(side, args.replay)

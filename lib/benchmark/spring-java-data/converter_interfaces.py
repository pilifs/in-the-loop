"""Bind the formatter's first generic reflection input to actual registration on each JVM graph."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile
from urllib.parse import unquote, urlparse

from historical_companion import prepare_graph
from measure import ROOT, SETUP, digest, write
from targets import runtime

FOLDER = ROOT / "examples/374-spring-formatter-binding"
SOURCE = FOLDER / "companions/ConverterInterfaces.java"
DEST = FOLDER / "records/converter-interfaces"
PKG = "org.springframework.core.convert"
FACTORY = PKG + ".support.NumberToNumberConverterFactory"
CLASSES = [FACTORY, PKG + ".support.GenericConversionService", PKG + ".support.DefaultConversionService",
           "org.springframework.core.ResolvableType"]
ROWS = [FACTORY, PKG + ".converter.ConverterFactory<java.lang.Number, java.lang.Number>",
        PKG + ".converter.ConditionalConverter", "java.lang.Number java.lang.Number registered"]


def measure(side, replay):
    os.environ.setdefault("TARGETS_LOCAL_GIT_ROOT", str(SETUP / "src"))
    with tempfile.TemporaryDirectory(prefix="conversion-type-") as scratch:
        work = Path(scratch)
        jdk, graph, paths, bound = prepare_graph(FOLDER, side, "annotated-" + side, work)
        classes = work / "classes"
        classes.mkdir()
        cp = os.pathsep.join(map(str, paths[1:]))
        subprocess.run([jdk / "bin/javac", "--release", "21", "-proc:none", "-cp", cp, "-d", classes, SOURCE], check=True)
        trace = work / "classes.log"
        raw = subprocess.check_output([jdk / "bin/java", "-Xlog:class+load=info:file=" + str(trace) + ":none", "-cp", str(classes) + os.pathsep + cp, "springwork.ConverterInterfaces"],
                                      env=runtime._verifier_env({"home": str(jdk)}))
        if raw.decode().splitlines() != ROWS:
            raise ValueError("different instantiated factory, generic arguments or registration on " + side)
        print(side, *ROWS, sep="\n", flush=True)
        if replay:
            return
        dest = DEST / side
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "jvm.stdout").write_bytes(raw)
        definitions = {}
        loads = trace.read_text().splitlines()
        for name in CLASSES:
            prefix = name + " source: "
            uri, = [line[len(prefix):] for line in loads if line.startswith(prefix)]
            if urlparse(uri).scheme != "file":
                raise ValueError("unexpected provider for " + name)
            loaded = Path(unquote(urlparse(uri).path)).resolve()
            stamp, = [b for p, b in zip(paths[1:], bound[1:], strict=True) if p.resolve() == loaded]
            entry = name.replace(".", "/") + ".class"
            with zipfile.ZipFile(loaded) as jar:
                definitions[name] = {"entry": entry, "provider": stamp["path"], "jarSha256": stamp["sha256"],
                                     "classSha256": hashlib.sha256(jar.read(entry)).hexdigest()}
        write(dest / "measurement.json", {"job": os.environ["VERIFY_JOB_ID"], "source": os.environ["VERIFY_SOURCE_COMMIT"],
              "sourceSha256": digest(SOURCE), "classpath": bound[1:], "jdk": graph["jdk"],
              "jvmSha256": digest(dest / "jvm.stdout"), "definitions": definitions})


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--replay", action="store_true")
    args = cli.parse_args()
    for side in ("parent", "landed"):
        measure(side, args.replay)

"""Check the unchanged Spring Property callers with one recorded ClassUtils lookup table."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from historical_companion import bind, prepare_graph
from measure import ROOT, digest, read, write
from targets import native_selectors, runtime

sys.path.insert(0, str(ROOT / "lib/benchmark/java-domain-proof"))
from companions import PROFILE, hash_bytes, proof, selected_class

FOLDER = ROOT / "examples/372-spring-property-accessors"
OBSERVER = FOLDER / "companions/MetadataNames.java"
DEST = FOLDER / "records/class-utils-lookup"
ROOT_CLASS = "org.springframework.util.ClassUtils"
SETTINGS = {**PROFILE, "captureObjects": ["java.util.HashMap"]}
BOUNDS = (256, 16384)


def physical_rows(side):
    names = ["", "sue", "widget"] if side == "parent" else ["budget", "issue", "getWidget"]
    return [f"{i}\t{name}\t{int(i >= 3 or side == 'landed')}" for i, name in enumerate(names + ["name", "name", "widget"])]


def measure(side, replay):
    with tempfile.TemporaryDirectory(prefix="property-lookup-") as scratch:
        work = Path(scratch)
        jdk, graph, paths, bound = prepare_graph(FOLDER, side, "components-" + side, work)
        jars = paths[1:]
        jcp = os.pathsep.join(map(str, jars))
        classes = work / "classes"
        classes.mkdir()
        subprocess.run([jdk / "bin/javac", "--release", "21", "-proc:none", "-cp", jcp, "-d", classes, OBSERVER], check=True)
        env = runtime._verifier_env({"home": str(jdk)})
        env["JVMCONTRACT_JAR_RELEASE"] = "21"
        raw = subprocess.check_output([jdk / "bin/java", "-cp", str(classes) + os.pathsep + jcp, "springwork.MetadataNames"], env=env)
        if raw.decode().splitlines() != physical_rows(side):
            raise ValueError(f"different unmodified public names or original entry outcomes on {side}")
        print(side, repr(raw.decode().splitlines()), flush=True)
        if replay:
            return
        dest = DEST / side
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "jvm.stdout").write_bytes(raw)
        checker = Path(os.environ["JVMCONTRACT"])
        bindings = []
        for name, info in graph["classes"].items():
            jar = next(j for j, stamp in zip(paths, bound, strict=True) if stamp["sha256"] == info["jarSha256"])
            methods = ["components", "getters"] if name == "springwork.Accessors" else [None]
            for method in methods:
                bindings.append((name, method, "(I)I" if method else None, jar, info["classSha256"]))
        index, _, bytecode = selected_class(jars, ROOT_CLASS.replace(".", "/") + ".class")
        bindings.append((ROOT_CLASS, None, None, jars[index], hash_bytes(bytecode)))
        report = {"job": os.environ["VERIFY_JOB_ID"], "source": os.environ["VERIFY_SOURCE_COMMIT"],
                  "libTree": os.environ["JVMCONTRACT_LIB_TREE"], "checkerSha256": digest(checker),
                  "classpath": bound[1:], "jdk": graph["jdk"], "sourceSha256": digest(OBSERVER),
                  "profile": SETTINGS, "observedRoot": ROOT_CLASS, "jvmSha256": digest(dest / "jvm.stdout"),
                  "bindings": bind(checker, env, work, side, bindings, classpath=[classes,*jars]), "tasks": {}}
        for method in ("components", "getters"):
            scope = dest / method
            scope.mkdir()
            wrappers = native_selectors.compiled_calls(jdk, work / method, "springwork.Accessors", method, 0, 2, jars, classes)
            (scope / "Calls.jvm-bytecode").write_bytes(wrappers.read_bytes())
            task = report["tasks"][method] = {"callsSha256": digest(wrappers), "selectors": {}}
            for i in range(3):
                target = f"{native_selectors.PACKAGE}.Calls#{native_selectors.case_name(i)}()"
                result = proof(checker, classes, jars, work / method, env, scope, target, str(i),
                               roots=[ROOT_CLASS], bounds=BOUNDS, profile=SETTINGS)
                task["selectors"][str(i)] = result
                actual = int(physical_rows(side)[i + (3 if method == "getters" else 0)].split("\t")[-1])
                if result["verdict"] in ("verified", "violation") and (result["verdict"] == "verified") != bool(actual):
                    raise ValueError("the original JVM disagrees with a scoped native outcome")
        write(dest / "measurement.json", report)


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--replay", action="store_true")
    args = cli.parse_args()
    for side in ("parent", "landed"):
        measure(side, args.replay)

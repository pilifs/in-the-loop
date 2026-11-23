"""Check the factory filename and the first converter's interface types on both original graphs."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import binding_resources as resources
import converter_interfaces as converters
from historical_companion import bind, prepare_graph
from measure import ROOT, SETUP, digest, read, write
from targets import native_selectors, runtime

sys.path.insert(0, str(ROOT / "lib/benchmark/java-domain-proof"))
from companions import proof

BOUNDS = {"unwind": 256, "maxArrayLength": 16384}


def subject(kind):
    if kind == "filename":
        return resources.FOLDER, "FactoryFilename", "beans-", ("release", "combined")
    return converters.FOLDER, "FirstSignature", "annotated-", ("parent", "landed")


def native(raw, target, assumptions):
    outcome = native_selectors.checker_output.wire.decode(raw.decode(), "prove")
    if not outcome.ok or len(outcome.outcomes) != 1:
        raise ValueError("expected one native factory proof")
    row, = outcome.outcomes
    if (native_selectors.disposition(row, target, BOUNDS, 0) != ("established", None)
            or row.get("problem") or row.get("counterexample") or row["throws"]
            or row["stated"]["checker"]["fallback"] is not None or row["stated"]["assumptions"] != assumptions
            or any(a["basis"] != "engine" or a.get("id", "").startswith("observed-initializer:") for a in assumptions)):
        raise ValueError("incomplete factory proof or different startup")


def measure(kind, side, replay):
    folder, simple, task, _ = subject(kind)
    source = folder / "companions" / (simple + ".java")
    name = "springwork." + simple
    os.environ.setdefault("TARGETS_LOCAL_GIT_ROOT", str(SETUP / "src"))
    with tempfile.TemporaryDirectory(prefix="factory-startup-") as scratch:
        work = Path(scratch)
        jdk, graph, paths, bound = prepare_graph(folder, side, task + side, work)
        jars = paths[1:]
        classes = work / "classes"
        classes.mkdir()
        cp = os.pathsep.join(map(str, [classes, *jars]))
        env = runtime._verifier_env({"home": str(jdk)})
        env["JVMCONTRACT_JAR_RELEASE"] = "21"
        subprocess.run([jdk / "bin/javac", "-proc:none", "-g:none", "-cp", cp, "-d", classes, source], env=env, check=True)
        physical = subprocess.check_output([jdk / "bin/java", "-cp", cp, name], env=env)
        path_hash = None
        if kind == "filename":
            old, = read(folder / "records/factory-resources" / side / "measurement.json")["resources"]
            provider, = [p for p, b in zip(jars, bound[1:], strict=True) if b["sha256"] == old["jarSha256"]]
            path_hash = hashlib.sha256(f"file:{provider.resolve()}!/{resources.ENTRY}".encode()).hexdigest()
            expected = f"1 161 161 {path_hash}\n".encode()
        else:
            expected = b"1\n"
        if physical != expected:
            raise ValueError(f"{kind}/{side}: different JVM filename, resource bytes or first factory signature")
        print(kind, side, physical.decode().strip(), flush=True)
        if replay:
            return

        checker = Path(os.environ["JVMCONTRACT"])
        entry = classes / "springwork" / (simple + ".class")
        requested = [(name, "check", "()I", classes, digest(entry))]
        # Bind every original public application class and the private converter directly.
        providers = dict(graph["classes"])
        if kind == "signature":
            providers.update(read(converters.DEST / side / "measurement.json")["definitions"])
        for binary, info in providers.items():
            jar, = [p for p, b in zip(paths, bound, strict=True) if b["sha256"] == info["jarSha256"]]
            requested.append((binary, None, None, jar, info["classSha256"]))
        bindings = bind(checker, env, work, side, requested, classpath=[classes, *jars])
        dest = folder / "records/factory-startup" / side
        dest.mkdir(parents=True, exist_ok=True)
        bytecode = {}
        for generated in sorted(entry.parent.glob("*.class")):
            saved = dest / (generated.stem + ".jvm-bytecode")
            saved.write_bytes(generated.read_bytes())
            bytecode[generated.stem] = digest(saved)
        (dest / "jvm.stdout").write_bytes(physical)
        result = proof(checker, classes, jars, work, env, dest, name + "#check()", "native", bounds=(256, 16384))
        native((dest / result["stdout"]).read_bytes(), name + "#check()", result["assumptions"])
        if path_hash and not any(path_hash in a["text"] for a in result["assumptions"]):
            raise ValueError("the native filename and original JVM used different JAR paths")
        write(dest / "measurement.json", {"job": os.environ["VERIFY_JOB_ID"], "source": os.environ["VERIFY_SOURCE_COMMIT"],
              "libTree": os.environ["JVMCONTRACT_LIB_TREE"], "checkerSha256": digest(checker), "classpath": bound[1:],
              "bindings": bindings, "jdk": graph["jdk"], "sourceSha256": digest(source), "callerClasses": bytecode,
              "jvmSha256": digest(dest / "jvm.stdout"), "canonicalURLPathSha256": path_hash, "result": result})


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("kind", choices=("filename", "signature"))
    cli.add_argument("--replay", action="store_true")
    args = cli.parse_args()
    for side in subject(args.kind)[3]:
        measure(args.kind, side, args.replay)

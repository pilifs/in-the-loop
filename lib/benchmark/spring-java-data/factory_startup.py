"""Check factory discovery and converter registration on the original Spring graphs."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

import binding_resources as resources
import converter_interfaces as converters
from historical_companion import bind, prepare_graph
from measure import ROOT, SETUP, digest, read, write
from targets import native_selectors, runtime

sys.path.insert(0, str(ROOT / "lib/benchmark/java-domain-proof"))
from companions import proof

BOUNDS = {"unwind": 256, "maxArrayLength": 16384}
OBSERVERS = {
    "properties": ("FactoryProperties", b"1 161 12881\n", ("org.springframework.core.io.support.PropertiesLoaderUtils",)),
    "purge": ("SoftCache", b"1 retained=1 released=0\n", ("org.springframework.util.ConcurrentReferenceHashMap",)),
    "scalars": ("ScalarPrefix", b"1 1\n", ("org.springframework.core.convert.support.DefaultConversionService",
                                       "org.springframework.core.convert.support.GenericConversionService")),
}


def subject(kind):
    if kind in ("filename", "properties"):
        return resources.FOLDER, ("FactoryFilename" if kind == "filename" else OBSERVERS[kind][0]), "beans-", ("release", "combined")
    return converters.FOLDER, ("FirstSignature" if kind == "signature" else OBSERVERS[kind][0]), "annotated-", ("parent", "landed")


def native(raw, target, assumptions, *, exit_code=0, timed_prefix=False):
    outcome = native_selectors.checker_output.wire.decode(raw.decode(), "prove")
    if not outcome.ok or len(outcome.outcomes) != 1:
        raise ValueError("expected one native factory proof")
    row, = outcome.outcomes
    status, reason = native_selectors.disposition(row, target, BOUNDS, exit_code)
    if (row.get("counterexample") or row["throws"] or row["stated"]["checker"]["fallback"] is not None
            or row["stated"]["assumptions"] != assumptions
            or any(a["basis"] != "engine" or a.get("id", "").startswith("observed-initializer:") for a in assumptions)):
        raise ValueError("different factory claim or startup")
    if status == "established" and reason is None and not row.get("problem"):
        return status
    if (timed_prefix and status == "open" and exit_code == 1 and row["verdict"] == "unverifiable"
            and reason == row["problem"] and reason == "the engine did not finish within the time limit"
            and row["search"]["deadline_seconds"] == 60 and row["search"]["runs"][-1]["ending"] == "timeout"):
        return status
    raise ValueError(f"incomplete factory proof: {reason}")


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
        physical = subprocess.check_output([jdk / "bin/java", "-Xmx128m", "-cp", cp, name], env=env)
        path_hash = None
        if kind in ("filename", "properties"):
            old, = read(folder / "records/factory-resources" / side / "measurement.json")["resources"]
            provider, = [p for p, b in zip(jars, bound[1:], strict=True) if b["sha256"] == old["jarSha256"]]
            path_hash = hashlib.sha256(f"file:{provider.resolve()}!/{resources.ENTRY}".encode()).hexdigest()
            counts = b"1 161 161" if kind == "filename" else OBSERVERS[kind][1].strip()
            expected = counts + b" " + path_hash.encode() + b"\n"
        elif kind in OBSERVERS:
            expected = OBSERVERS[kind][1]
        else:
            expected = b"1\n"
        if physical != expected:
            raise ValueError(f"{kind}/{side}: original JVM returned {physical!r}, expected {expected!r}")
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
        if kind in OBSERVERS:
            for binary in OBSERVERS[kind][2]:
                entry_name = binary.replace(".", "/") + ".class"
                for jar in jars:
                    with zipfile.ZipFile(jar) as archive:
                        if entry_name in archive.namelist():
                            requested.append((binary, None, None, jar, hashlib.sha256(archive.read(entry_name)).hexdigest()))
                            break
                else:
                    raise ValueError(f"missing {binary} on the frozen graph")
        bindings = bind(checker, env, work, side, requested, classpath=[classes, *jars])
        dest = folder / "records" / (kind if kind in OBSERVERS else "factory-startup") / side
        dest.mkdir(parents=True, exist_ok=True)
        bytecode = {}
        for generated in sorted(entry.parent.glob("*.class")):
            saved = dest / (generated.stem + ".jvm-bytecode")
            saved.write_bytes(generated.read_bytes())
            bytecode[generated.stem] = digest(saved)
        (dest / "jvm.stdout").write_bytes(physical)
        result = proof(checker, classes, jars, work, env, dest, name + "#check()", "native", bounds=(256, 16384))
        native((dest / result["stdout"]).read_bytes(), name + "#check()", result["assumptions"],
               exit_code=result["exit"], timed_prefix=kind == "scalars")
        if path_hash and not any(path_hash in a["text"] for a in result["assumptions"]):
            raise ValueError("the native filename and original JVM used different JAR paths")
        write(dest / "measurement.json", {"job": os.environ["VERIFY_JOB_ID"], "source": os.environ["VERIFY_SOURCE_COMMIT"],
              "libTree": os.environ["JVMCONTRACT_LIB_TREE"], "checkerSha256": digest(checker), "classpath": bound[1:],
              "bindings": bindings, "jdk": graph["jdk"], "sourceSha256": digest(source), "callerClasses": bytecode,
              "jvmSha256": digest(dest / "jvm.stdout"), "canonicalURLPathSha256": path_hash, "result": result})


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("kind", choices=("filename", "signature", *OBSERVERS))
    cli.add_argument("--replay", action="store_true")
    args = cli.parse_args()
    for side in subject(args.kind)[3]:
        measure(args.kind, side, args.replay)

"""Certify a realizable startup counterexample to each unrestricted landed fluent claim."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import fluent_launch as launch
import fluent_lines as lines
from historical_companion import bind, prepare_graph
from measure import ROOT, digest, read, write
from targets import native_selectors, runtime, runtime_jar

sys.path.insert(0, str(ROOT / "lib/benchmark/java-domain-proof"))
from companions import proof

CALLER = "springwork.FluentWitness"
SOURCE = lines.FOLDER / "companions/FluentWitness.java"
DEST = lines.FOLDER / "records/fluent-counterexample"
METHODS = {"names": "fluentNames", "decision": "fluentDecision"}


def replay_name(method):
    return METHODS[method][0].upper() + METHODS[method][1:] + "Replay"


def fresh_replay(method):
    return """package springwork;
public final class %s {
    public static void main(String[] args) {
        int value = RoleChecks.%s(1);
        System.out.print(value);
        String separator = System.lineSeparator();
        for (int i = 0; i < separator.length(); i++) {
            System.out.print(" ");
            System.out.print((int) separator.charAt(i));
        }
        System.out.print("\\n");
    }
}
""" % (replay_name(method), METHODS[method])


def qualify_replay(data, method):
    pool, methods, _ = runtime_jar._declarations(data, with_code=True)
    flags, code, handlers = methods["main", "([Ljava/lang/String;)V"]
    shape = bytearray.fromhex("04 b8 0000 3c b2 0000 1b b6 0000 b8 0000 4d 03 3e 1d 2c b6 0000 "
                              "a2 001c b2 0000 12 00 b6 0000 b2 0000 2c 1d b6 0000 b6 0000 84 03 01 "
                              "a7 ffe2 b2 0000 12 00 b6 0000 b1")
    launch.require(runtime_jar.this_class(data) == "springwork/" + replay_name(method)
                   and runtime_jar.super_class(data) == "java/lang/Object" and not runtime_jar.interfaces(data)
                   and ("<clinit>", "()V") not in methods and flags == 9 and not handlers and len(code) == len(shape),
                   "fresh JVM replay must start with the original observer at selector 1")
    printer = "java/io/PrintStream"
    for at, expected in [(1, (launch.CHECKS, METHODS[method], "(I)I")), (9, (printer, "print", "(I)V")),
                         (12, ("java/lang/System", "lineSeparator", "()Ljava/lang/String;")),
                         (20, ("java/lang/String", "length", "()I")), (31, (printer, "print", "(Ljava/lang/String;)V")),
                         (39, ("java/lang/String", "charAt", "(I)C")), (42, (printer, "print", "(I)V")),
                         (56, (printer, "print", "(Ljava/lang/String;)V"))]:
        launch.require(launch.ref(pool, code, at) == expected, "different fresh replay entry or observer")
        shape[at + 1:at + 3] = code[at + 1:at + 3]
    for at in (5, 26, 34, 51):
        tag, (owner, pair) = pool[int.from_bytes(code[at + 1:at + 3], "big")]
        kind, (name, desc) = pool[pair]
        launch.require(tag == 9 and kind == 12 and runtime_jar._class_name(pool, owner) == "java/lang/System"
                       and runtime_jar._utf8(pool, name) == "out" and runtime_jar._utf8(pool, desc) == "Ljava/io/PrintStream;",
                       "different JVM output stream")
        shape[at + 1:at + 3] = code[at + 1:at + 3]
    for at, literal in [(29, " "), (54, "\n")]:
        tag, index = pool[code[at + 1]]
        launch.require(tag == 8 and runtime_jar._utf8(pool, index) == literal, "different replay output delimiter")
        shape[at + 1] = code[at + 1]
    launch.require(code == shape, "different reported result or startup separator")


def qualify_caller(data):
    """The active arm returns one exactly when the unchanged observer returns zero at selector 1."""
    pool, methods, _ = runtime_jar._declarations(data, with_code=True)
    launch.require(runtime_jar.this_class(data) == CALLER.replace(".", "/")
                   and runtime_jar.super_class(data) == "java/lang/Object" and not runtime_jar.interfaces(data)
                   and ("<clinit>", "()V") not in methods, "different witness class or initializer")
    for method, original in METHODS.items():
        flags, code, handlers = methods[method, "()I"]
        shape = bytearray.fromhex("12 00 b8 0000 b6 0000 9a 0005 04 ac 04 04 b8 0000 64 ac")
        launch.require(flags == 9 and not handlers and len(code) == len(shape), "different witness method")
        tag, index = pool[code[1]]
        launch.require(tag == 8 and runtime_jar._utf8(pool, index) == "|", "different separator premise")
        shape[1] = code[1]
        for at, expected in [(2, ("java/lang/System", "lineSeparator", "()Ljava/lang/String;")),
                             (5, ("java/lang/String", "equals", "(Ljava/lang/Object;)Z")),
                             (15, (launch.CHECKS, original, "(I)I"))]:
            launch.require(launch.ref(pool, code, at) == expected, "different startup query or original observer")
            shape[at + 1:at + 3] = code[at + 1:at + 3]
        launch.require(code == shape, "different witness branch, selector or returned proposition")


def rows(separator):
    pipe = separator == "|"
    names = ["ROLE_A", "ROLE_B|ROLE_B", "ROLE_C|ROLE_B", "ROLE_D|"] if pipe else ["ROLE_" + ch for ch in "ABCD"]
    return ["separator " + " ".join(str(ord(c)) for c in separator), *["name " + name for name in names],
            "granted " + ("false" if pipe else "true"), "original " + ("0 0" if pipe else "1 1"), "witness 1 1"]


def qualify_proof(raw, method, assumptions):
    target = f"{CALLER}#{method}()"
    decoded = native_selectors.checker_output.wire.decode(raw.decode(), "prove")
    launch.require(decoded.ok and len(decoded.outcomes) == 1, "missing witness proof")
    row, = decoded.outcomes
    launch.require(native_selectors.disposition(row, target, lines.BOUNDS, 0) == ("established", None)
                   and not row["throws"] and not row["counterexample"] and not row["problem"]
                   and row["stated"]["checker"]["fallback"] is None
                   and row["stated"]["assumptions"] == assumptions, "incomplete or differently scoped witness proof")


def measure(replay=False):
    with tempfile.TemporaryDirectory(prefix="fluent-witness-") as scratch:
        work = Path(scratch)
        jdk, graph, paths, bound = prepare_graph(lines.FOLDER, "landed", "fluent-names-landed", work)
        prior = read(lines.DEST / "measurement.json")
        launch.require(prior["jdk"] == graph["jdk"] and prior["classpath"] == bound[1:], "different landed role graph")
        jars = paths[1:]
        classes = work / "classes"
        classes.mkdir()
        cp = os.pathsep.join(map(str, [classes, *jars]))
        sources = []
        for method in METHODS:
            src = work / (replay_name(method) + ".java")
            src.write_text(fresh_replay(method))
            sources.append(src)
        subprocess.run([jdk / "bin/javac", "-g:none", "-proc:none", "-cp", cp, "-d", classes, SOURCE, *sources],
                       env=launch.ENV, check=True)
        caller = classes / "springwork/FluentWitness.class"
        qualify_caller(caller.read_bytes())
        outputs = {}
        independent = {}
        for method in METHODS:
            qualify_replay((caller.parent / (replay_name(method) + ".class")).read_bytes(), method)
        for profile, sep in lines.PROFILES.items():
            opts = [] if profile == "default" else ["-Dline.separator=" + sep]
            raw = subprocess.check_output([jdk / "bin/java", *opts, "-cp", cp, CALLER], env=launch.ENV)
            launch.require(raw == ("\n".join(rows(sep)) + "\n").encode("ascii"), "different original JVM observation")
            outputs[profile] = raw
            for method in METHODS:
                binary = "springwork." + replay_name(method)
                raw = subprocess.check_output([jdk / "bin/java", *opts, "-cp", cp, binary], env=launch.ENV)
                expected = [int(sep != "|"), *map(ord, sep)]
                launch.require(raw == (" ".join(map(str, expected)) + "\n").encode(), "different fresh JVM counterexample")
                independent[f"{profile}-{method}"] = raw
        print("A alone grants on LF and CRLF. On pipe the reachable names contain three pipe-suffixed or joined terms and D is denied.")
        if replay:
            return
        checker = Path(os.environ["JVMCONTRACT"])
        env = runtime._verifier_env({"home": str(jdk)})
        env["JVMCONTRACT_JAR_RELEASE"] = "21"
        inputs = [(CALLER, m, "()I", classes, digest(caller)) for m in METHODS]
        for b in prior["bindings"]:
            if b["class"] != lines.CALLER:
                jar, = [p for p in jars if p.name == b["provider"]]
                inputs.append((b["class"], b["method"], b["descriptor"], jar, b["sha256"]))
        providers = bind(checker, env, work, "landed", inputs, classpath=[classes, *jars])
        DEST.mkdir(parents=True, exist_ok=True)
        (DEST / "FluentWitness.jvm-bytecode").write_bytes(caller.read_bytes())
        for method, src in zip(METHODS, sources, strict=True):
            (DEST / src.name).write_bytes(src.read_bytes())
            (DEST / (replay_name(method) + ".jvm-bytecode")).write_bytes((caller.parent / (replay_name(method) + ".class")).read_bytes())
        for name, raw in {**outputs, **independent}.items():
            (DEST / (name + ".stdout")).write_bytes(raw)
        claims = {}
        for method in METHODS:
            p = proof(checker, classes, jars, work, env, DEST, f"{CALLER}#{method}()", method, bounds=(256, 16384))
            qualify_proof((DEST / p["stdout"]).read_bytes(), method, prior["proofs"][1]["assumptions"])
            claims[method] = p
        write(DEST / "measurement.json", {"job": os.environ["VERIFY_JOB_ID"], "source": os.environ["VERIFY_SOURCE_COMMIT"],
              "checkerSha256": digest(checker), "libTree": os.environ["JVMCONTRACT_LIB_TREE"],
              "classpath": bound[1:], "bindings": providers, "jdk": graph["jdk"], "sourceSha256": digest(SOURCE),
              "environment": launch.ENV, "runtimeSha256": {name: digest(jdk / name) for name in launch.VM_FILES},
              "selector": 1, "startupUnits": [124], "profiles": {k: hashlib.sha256(v).hexdigest() for k, v in outputs.items()},
              "independentReplays": {k: hashlib.sha256(v).hexdigest() for k, v in independent.items()},
              "claims": claims})


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--replay", action="store_true")
    measure(cli.parse_args().replay)

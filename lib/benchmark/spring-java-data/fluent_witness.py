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


def qualify_caller(data):
    """The active arm returns one exactly when the unchanged observer returns zero at selector 1."""
    pool, methods, _ = runtime_jar._declarations(data, with_code=True)
    launch.require(runtime_jar.this_class(data) == CALLER.replace(".", "/")
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
        subprocess.run([jdk / "bin/javac", "-g:none", "-proc:none", "-cp", cp, "-d", classes, SOURCE],
                       env=launch.ENV, check=True)
        caller = classes / "springwork/FluentWitness.class"
        qualify_caller(caller.read_bytes())
        outputs = {}
        for profile, sep in lines.PROFILES.items():
            opts = [] if profile == "default" else ["-Dline.separator=" + sep]
            raw = subprocess.check_output([jdk / "bin/java", *opts, "-cp", cp, CALLER], env=launch.ENV)
            launch.require(raw == ("\n".join(rows(sep)) + "\n").encode("ascii"), "different original JVM observation")
            outputs[profile] = raw
        print("A alone grants on LF and CRLF. On pipe the reachable names contain three pipe-suffixed or joined terms and D is denied.")
        if replay:
            return
        checker = Path(os.environ["JVMCONTRACT"])
        env = runtime._verifier_env({"home": str(jdk)})
        inputs = [(CALLER, m, "()I", classes, digest(caller)) for m in METHODS]
        for b in prior["bindings"]:
            if b["class"] != lines.CALLER:
                jar, = [p for p in jars if p.name == b["provider"]]
                inputs.append((b["class"], b["method"], b["descriptor"], jar, b["sha256"]))
        providers = bind(checker, env, work, "landed", inputs, classpath=[classes, *jars])
        DEST.mkdir(parents=True, exist_ok=True)
        (DEST / "FluentWitness.jvm-bytecode").write_bytes(caller.read_bytes())
        for name, raw in outputs.items():
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
              "claims": claims})


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--replay", action="store_true")
    measure(cli.parse_args().replay)

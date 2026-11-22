"""Check Jackson's original character tables and the next JsonFactory dependency on each Avro classpath."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

from schema_sets import fresh_schema_calls, native
from startup import HERE, ROOT, compile_java, document, materialize, pilot_checker, runtime_jdk, runtime_maven, selected_class

GUARD = "unit >= 0 && unit < 128"
ENTRY = "com/fasterxml/jackson/core/io/CharTypes.class"


def one(number, side, subject, work, output, current, pilot):
    case, = (ROOT/"examples").glob(number+"-*")
    jars, binding = materialize(case, side, work)
    index, entry, body = selected_class(jars, ENTRY)
    classes = work/"classes"
    for src in ("JacksonHex.java", "BytesSchema.java"):
        compile_java(subject, work, classes, HERE/src, jars)
    upper = 10 if number == "355" else -1
    cp = os.pathsep.join(map(str, [classes, *jars]))
    java = [subject/"bin/java", "-Djava.io.tmpdir="+str(work), "-XX:ActiveProcessorCount=2", "-cp", cp]
    observed = subprocess.check_output([*java, "foundation.JacksonHex", str(upper)], cwd="/", env={}, text=True, timeout=30)
    digest = hashlib.sha256(body).hexdigest()
    if observed.strip() != digest: raise ValueError("the JVM selected a different CharTypes class")
    fresh = fresh_schema_calls(subject, work, classes, jars)
    out = output/number/side
    out.mkdir(parents=True, exist_ok=True)
    record = {"schema":"jackson-character-table/v1", "example":number, "side":side, "inputs":binding,
              "jdkModules":runtime_maven.sha256_of(subject/"lib/modules"), "jarIndex":index,
              "entry":entry, "classSha256":digest, "adapterSha256":runtime_maven.sha256_of(classes/"foundation/JacksonHex.class"),
              "originalJvmAsciiInputs":128, "originalJvmInput0x141":upper, "freshJvmCalls":fresh, "claims":{}}
    document(out/"evidence.json", record)
    if not current: return True
    plans = []
    if pilot: plans.append(("pilot", pilot, "JacksonHex#ascii", "unverifiable", 512, GUARD, None))
    plans.extend([
        ("frozen", current, "JacksonHex#ascii", None, 64, GUARD, None),
        ("table", current, "JacksonHex#ascii", "verified", 512, GUARD, None),
        ("table", current, "JacksonHex#upperByte", "violation" if upper == 10 else "verified", 512, None, "result == -1"),
        ("frozen", current, "BytesSchema#firstFactory", None, 64, None, None),
        ("table", current, "BytesSchema#firstFactory", None, 512, None, None),
    ])
    for label, exe, target, expected, unwind, guard, assertion in plans:
        row = native(exe, subject, work, classes, out, label, target, expected, jars,
                     unwind=unwind, guard=guard, assertion=assertion)
        record["claims"][label+"-"+target.split("#")[1]] = row
        document(out/"evidence.json", record)
        print(number, side, label, target, row["verdict"], row["firstUnknown"], flush=True)
    return all(c["matchedExpectation"] for c in record["claims"].values())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--jvm-only", action="store_true")
    ap.add_argument("--pilot", nargs="?", const="cached", help="also check with the pinned pilot executable")
    args = ap.parse_args()
    subject = Path(runtime_jdk.home("21"))
    if runtime_jdk.release(subject)["JAVA_VERSION"] != "21.0.13": raise ValueError("expected the frozen subject JDK")
    current = None if args.jvm_only else Path(os.environ["JVMCONTRACT"]).resolve()
    pilot = pilot_checker(current, args.pilot) if current and args.pilot else None
    ok = True
    for number in ("355","361"):
        for side in ("parent","fix"):
            with tempfile.TemporaryDirectory(prefix="jackson-tables-") as temp:
                ok &= one(number, side, subject, Path(temp), args.output.resolve(), current, pilot)
    if not ok: raise SystemExit(1)


if __name__ == "__main__":
    main()

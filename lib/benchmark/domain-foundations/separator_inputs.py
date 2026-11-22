"""Check explicit separator inputs, failed initialization and original JavaParser traversal without a heap capture."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from startup import HERE, ROOT, compile_java, document, materialize, pilot_checker, runtime_jdk, runtime_maven

GUARD = "code >= 0 && code < 2 && length >= 0 && length <= 2"
PROPERTY = "system properties use the standard JVM Properties table and the running JVM permits this property access"


def physical(jdk, work, cp, args):
    command = [jdk/"bin/java", "-XX:ActiveProcessorCount=2", "-Djava.io.tmpdir="+str(work),
               "-cp", cp, "foundation.SeparatorInputs", *map(str, args)]
    subprocess.run(command, env={}, cwd="/", check=True, timeout=30)


def check(exe, jdk, work, classes, jars, label, method, out):
    target = "foundation.SeparatorInputs#"+method
    bound = 3 if method == "text" else 64
    guard = {"text": "value != null", "postorder": GUARD}.get(method)
    budget = 180 if method == "postorder" else 60
    cmd = [exe, "prove", target, "--engine", "native", "--gaps", "strict", "--classes", classes,
           "--classpath", os.pathsep.join(map(str, jars)), "--unwind", "96", "--max-array-length", str(bound),
           "--work", work/(label+"-"+method), "--json"]
    if guard: cmd.extend(["--assume", guard])
    if method == "postorder": cmd.extend(["--assert", "result == 1"])
    env = dict(os.environ, JAVA_HOME=str(jdk), JVMCONTRACT_JAR_RELEASE="21", PATH=str(jdk/"bin")+os.pathsep+os.defpath)
    summary = {"target": target, "checkerSha256": runtime_maven.sha256_of(exe), "guard": guard,
               "unwind": 96, "maxArrayLength": bound, "budgetSeconds": budget}
    start = time.monotonic()
    try:
        run = subprocess.run(cmd, env=env, capture_output=True, timeout=budget)
    except subprocess.TimeoutExpired:
        return {**summary, "verdict": "timeout", "seconds": round(time.monotonic()-start, 3)}
    seconds = round(time.monotonic()-start, 3)
    if not run.stdout: raise ValueError(run.stderr.decode(errors="replace")[-900:])
    path = out/(label+"-"+method+".native.json")
    path.write_bytes(run.stdout)
    row, = json.loads(run.stdout)
    stated = row["stated"]
    if row["target"] != target or stated["gap_mode"] != "strict" or row["assume"] != guard:
        raise ValueError("checker did not run the declared property")
    premises = [a["text"] for a in stated["assumptions"] if a["kind"] == "library"]
    if premises != [PROPERTY] or (row["verdict"] == "verified" and stated["vacuity"]["status"] != "non-vacuous"):
        raise ValueError("unexpected startup premises or vacuous proof")
    if method == "text" and stated["domain"]["parameters"] != [
            {"name":"value", "type":"java.lang.String", "kind":"value", "null":False, "max_length":3}]:
        raise ValueError("wrong UTF-16 input domain")
    if row["verdict"] == "violation" and method == "postorder":
        inputs = row["counterexample"]["inputs"]
        if [(x["name"], x["type"]) for x in inputs] != [("code","int"), ("first","char"), ("second","char"), ("length","int")]:
            raise ValueError("incomplete traversal witness")
        values = [x["value"] for x in inputs]
        if not (values[0] in (0,1) and 0 <= values[1] <= 65535 and 0 <= values[2] <= 65535 and 0 <= values[3] <= 2):
            raise ValueError("witness outside the registered inputs")
        physical(jdk, work, os.pathsep.join(map(str, [classes, *jars])), ["replay", *values])
        summary["replayedInputs"] = inputs
    return {**summary, "verdict": row["verdict"], "firstUnknown": row["problem"], "raw": path.name,
            "sha256": runtime_maven.sha256_of(path), "libraryPremises": premises, "seconds": seconds}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--side", choices=("parent","fix"), required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--pilot", nargs="?", const="cached", help="compare to the pinned pilot checker")
    ap.add_argument("--jvm-only", action="store_true")
    args = ap.parse_args()
    case, = (ROOT/"examples").glob("360-*")
    jdk = Path(runtime_jdk.home("21"))
    if runtime_jdk.release(jdk)["JAVA_VERSION"] != "21.0.13": raise ValueError("expected the frozen subject JDK")
    out = args.output.resolve()/args.side
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="separator-inputs-") as tmp:
        work = Path(tmp)
        jars, binding = materialize(case, args.side, work)
        classes = work/"classes"
        compile_java(jdk, work, classes, case/"adapter/organic/TreeOrder.java", jars)
        compile_java(jdk, work, classes, HERE/"SeparatorInputs.java", [classes, *jars])
        cp = os.pathsep.join(map(str, [classes, *jars]))
        controls = [["text", i] for i in range(8)] + [["absent"], ["tree", 0, int(args.side == "fix")], ["tree", 1, 1]]
        for control in controls: physical(jdk, work, cp, control)
        record = {"schema":"javaparser-explicit-separator/v1", "inputs":binding, "jdkModules":runtime_maven.sha256_of(jdk/"lib/modules"),
                  "traversalAdapter": runtime_maven.sha256_of(classes/"organic/TreeOrder.class"),
                  "propertyAdapter": runtime_maven.sha256_of(classes/"foundation/SeparatorInputs.class"),
                  "freshJvmControls": controls, "claims": {}}
        document(out/"evidence.json", record)
        if args.jvm_only: return
        current = Path(os.environ["JVMCONTRACT"]).resolve()
        plans = []
        if args.pilot:
            plans.append(("pilot", pilot_checker(current, args.pilot), "text", "unverifiable"))
        plans.extend(("current", current, m, v) for m,v in
                     (("text","verified"), ("absent","verified"), ("postorder","verified" if args.side == "fix" else "violation")))
        ok = True
        for label, exe, method, expected in plans:
            row = check(exe, jdk, work, classes, jars, label, method, out)
            record["claims"][label+"-"+method] = row
            document(out/"evidence.json", record)
            print(args.side, label, method, row["verdict"], row.get("firstUnknown"), flush=True)
            ok &= row["verdict"] == expected
            if label == "pilot": ok &= "java.lang.String.replace" in (row.get("firstUnknown") or "")
        if not ok: raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Verify the reserved-name set producer shared by the two original Avro Schema classes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

from producers import PROFILE
from startup import HERE, ROOT, compile_java, document, materialize, pilot_checker, runtime_jar, runtime_jdk, runtime_maven

SHA = runtime_maven.sha256_of
ENTRY = "org/apache/avro/Schema.class"
PROOF = Path("foundation/ReservedNames.class")


def sites(work, subject, inspector, classes, output, checker):
    tools = work/"tools"
    compile_java(inspector, work, tools, HERE/"ReservedNameSite.java")
    bad = work/"wrong"
    bad.mkdir()
    source = bad/"ReservedNames.java"
    original = (HERE/"ReservedNames.java").read_text()
    mutated = original.replace('"aliases"', '"alias"', 1)
    if mutated == original:
        raise ValueError("could not alter the proof fixture")
    source.write_text(mutated)
    compile_java(subject, work, bad, source)
    records = []
    for number in ("355", "361"):
        case, = (ROOT/"examples").glob(number+"-*")
        for side in ("parent", "fix"):
            leg = work/(number+"-"+side)
            leg.mkdir()
            jars, binding = materialize(case, side, leg)
            selected = leg/"Schema.class"
            for index, jar in enumerate(jars):
                with zipfile.ZipFile(jar) as z:
                    entry = runtime_jar.effective_entries(z, 21).get(ENTRY)
                    if entry is not None:
                        selected.write_bytes(z.read(entry))
                        break
            else:
                raise ValueError("pinned classpath has no Schema")
            compare = [inspector/"bin/java", "-Djava.io.tmpdir="+str(work), "-cp", tools, "foundation.ReservedNameSite"]
            match = subprocess.check_output([*compare, classes/PROOF, selected], text=True, timeout=30)
            mismatch = subprocess.run([*compare, bad/PROOF, selected], capture_output=True, text=True, timeout=30)
            if not mismatch.returncode or "instruction mismatch at " not in mismatch.stderr:
                raise ValueError("changed producer literal was not rejected at its instruction")
            physical = subprocess.check_output([subject/"bin/java", "-Djava.io.tmpdir="+str(work), "-XX:ActiveProcessorCount=2",
                  "-cp", os.pathsep.join(map(str, [classes, *jars])), "foundation.ReservedNames"], cwd="/", env={}, text=True, timeout=40)
            if physical.strip() != SHA(selected):
                raise ValueError("ordinary JVM read a different Schema class")
            begin, end, count = map(int, match.split())
            calls = leg/"classes"
            compile_java(subject, work, calls, HERE/"BytesSchema.java", jars)
            subprocess.run([subject/"bin/java", "-Djava.io.tmpdir="+str(work), "-XX:ActiveProcessorCount=2",
                "-cp", os.pathsep.join(map(str, [calls, *jars])), "foundation.BytesSchema"], cwd="/", env={}, check=True, timeout=40)
            claims = []
            if checker:
                dest = output/number/side
                dest.mkdir(parents=True, exist_ok=True)
                for label, method, expected in (("ordinary", "firstFactory", None), ("ordinary", "typed", None), ("schema", "typed", "verified"),
                                                 ("schema", "rejectsRecord", "verified")):
                    claims.append(native(checker, subject, leg, calls, dest, label, "BytesSchema#"+method,
                        expected, jars, SHA(selected) if label == "schema" else None))
            records.append({"example": number, "side": side, "revision": binding["revision"],
                "buildReceipt": binding["build"], "buildSha256": binding["buildSha256"],
                "jarIndex": index, "jarSha256": binding["orderedJars"][index], "entry": entry.filename,
                "classSha256": SHA(selected), "method": "org.apache.avro.Schema.<clinit>()V",
                "startBci": begin, "endBciExclusive": end, "instructions": count,
                "changedLiteral": "refused", "ordinaryJvmContents": "held", "originalJvmConstruction": "held",
                "constructorAdapterSha256": SHA(calls/"foundation/BytesSchema.class"), "constructorClaims": claims})
    return records


def native(executable, subject, work, classes, output, label, entry, expected, jars=(), observed_schema=None):
    target = "foundation."+entry
    method = entry.split("#")[1]
    env = dict(os.environ, JAVA_HOME=str(subject), JVMCONTRACT_JAR_RELEASE="21", PATH=str(subject/"bin")+os.pathsep+os.defpath)
    cmd = [executable, "prove", target, "--classes", classes, "--engine", "native", "--gaps", "strict",
        "--unwind", "64", "--max-array-length", "128", "--work", work/(label+"-"+method), "--json"]
    if jars: cmd.extend(["--classpath", os.pathsep.join(map(str, jars))])
    if observed_schema: cmd.extend(["--observed-initializer", "org.apache.avro.Schema", "--observed-runtime", json.dumps(PROFILE)])
    checked = subprocess.run(cmd, capture_output=True, env=env, timeout=60)
    if not checked.stdout:
        raise ValueError(checked.stderr.decode(errors="replace")[-900:])
    path = output/(label+"-"+method+".native.json")
    path.write_bytes(checked.stdout)
    row, = json.loads(checked.stdout)
    stated = row["stated"]
    assumptions = [a["id"] for a in stated["assumptions"] if a["kind"] == "library"]
    if row["target"] != target or stated["gap_mode"] != "strict":
        raise ValueError("unexpected producer or startup scope")
    if observed_schema:
        if len(assumptions) != 1 or not assumptions[0].startswith("observed-initializer:org.apache.avro.Schema:"+observed_schema+":"):
            raise ValueError("construction used a different Schema or another library premise")
    elif assumptions:
        raise ValueError("unexpected startup assumption")
    allowed = {expected} if expected else {"verified", "unverifiable"}
    matched = row["verdict"] in allowed
    if row["verdict"] == "verified": matched &= stated["vacuity"]["status"] == "non-vacuous"
    if label == "pilot": matched &= "java.util.HashSet.<init>(Ljava/util/Collection;)V" in (row["problem"] or "")
    if row["verdict"] == "violation": matched &= row.get("counterexample") is not None
    return {"target": target, "verdict": row["verdict"], "checkerSha256": SHA(executable),
            "raw": path.name, "sha256": SHA(path), "firstUnknown": row["problem"], "libraryPremises": assumptions,
            "matchedExpectation": matched}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--sites-only", action="store_true")
    ap.add_argument("--pilot", nargs="?", const="cached", help="compare with the pinned pilot binary, in the same verification cache or at the given path")
    args = ap.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    subject, inspector = (Path(runtime_jdk.home(v)) for v in ("21", "25"))
    if runtime_jdk.release(subject)["JAVA_VERSION"] != "21.0.13":
        raise ValueError("the frozen subjects require Temurin 21.0.13")
    with tempfile.TemporaryDirectory(prefix="avro-schema-sets-") as tmp:
        work = Path(tmp)
        classes = work/"classes"
        compile_java(subject, work, classes, HERE/"ReservedNames.java")
        exe = None if args.sites_only else Path(os.environ["JVMCONTRACT"]).resolve()
        result = {"schema": "avro-reserved-name-producer/v1", "subjectJdkModules": SHA(subject/"lib/modules"),
                  "producerSha256": SHA(classes/PROOF), "sites": sites(work, subject, inspector, classes, output, exe), "claims": []}
        if not args.sites_only:
            if args.pilot:
                previous = pilot_checker(exe, args.pilot)
                result["claims"].append(native(previous, subject, work, classes, output, "pilot", "ReservedNames#reserved", "unverifiable"))
            for method, expected in (("reserved","verified"), ("defaultLeaks","violation")):
                result["claims"].append(native(exe, subject, work, classes, output, "current", "ReservedNames#"+method, expected))
        document(output/"evidence.json", result)
        for row in result["sites"]:
            print(row["example"], row["side"], row["startBci"], row["endBciExclusive"], row["instructions"])
        claims = result["claims"] + [r for site in result["sites"] for r in site["constructorClaims"]]
        for row in claims:
            print(row["target"], row["verdict"], row["firstUnknown"])
        if not all(r["matchedExpectation"] for r in claims): raise SystemExit(1)


if __name__ == "__main__":
    main()

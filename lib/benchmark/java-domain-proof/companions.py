"""Measure the smaller public Avro producers and record the actual calls made by both readers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "domain-foundations"))
from startup import document, materialize, runtime_jdk, runtime_maven, selected_class
from producers import PROFILE
from public_run import measure

SHA = runtime_maven.sha256_of
DECODER = "org.apache.avro.io.BinaryDecoder"
RECORD = "org.apache.avro.generic.GenericData$Record"
ROOTS = ["org.apache.avro.Schema", "org.apache.avro.generic.GenericData", "org.apache.avro.generic.GenericDatumReader"]


def invocation(args, name, out, work, env):
    stdout, stderr = out / (name + ".stdout"), out / (name + ".stderr")
    cost = measure(args, stdout, stderr=stderr, cwd=work, env=env)
    # The temporary classpath is recorded by provider hash and order in binding.
    cost.pop("command")
    cost.update(stdout=stdout.name, stderr=stderr.name, stdoutSha256=SHA(stdout), stderrSha256=SHA(stderr))
    return cost


def proof(checker, classes, jars, work, env, out, method, label, guard=None, assertion="result == 1", roots=(), bounds=(512, 16384), profile=PROFILE):
    args = [checker, "prove", method, "--classes", classes, "--classpath", os.pathsep.join(map(str, jars)),
            "--engine", "native", "--gaps", "strict", "--unwind", str(bounds[0]), "--max-array-length", str(bounds[1]),
            "--timeout", "60", "--work", work / label, "--assert", assertion, "--json"]
    if guard:
        args += ["--assume", guard]
    for root in roots:
        args += ["--observed-initializer", root]
    if roots:
        args += ["--observed-runtime", json.dumps(profile)]
    row = invocation(args, label, out, work, env)
    row.update(target=method, guard=guard, assertion=assertion, observedRoots=list(roots), bounds=list(bounds))
    try:
        outcome, = json.loads((out / row["stdout"]).read_bytes())
    except (ValueError, TypeError):
        diagnostic = (out / row["stderr"]).read_text(errors="replace").strip()
        if not row["exit"] or not diagnostic:
            raise ValueError(f"{label}: checker produced no outcome or diagnostic")
        return {**row, "verdict": "unavailable", "blocker": diagnostic[-2400:]}
    stated = outcome["stated"]
    if (outcome["target"] != method or outcome["assume"] != guard or outcome["assert"] != assertion
            or stated["gap_mode"] != "strict" or stated["checker"]["engine"] != "native"):
        raise ValueError(f"{label}: different claim or engine")
    row.update(verdict=outcome["verdict"], blocker=outcome["problem"], assumptions=stated["assumptions"])
    if row["verdict"] == "verified":
        array_input = any(p["type"].endswith("[]") for p in stated["domain"]["parameters"])
        # The statement bounds input arrays. The search receipt separately records
        # the engine's configured array limit even when every argument is scalar.
        if (row["exit"] or row["blocker"] or stated["vacuity"]["status"] != "non-vacuous"
                or outcome["search"]["max_array_length"] != bounds[1]
                or stated["bounds"] != {"complete": True, "unwind": bounds[0],
                                        "max_array_length": bounds[1] if array_input else None}):
            raise ValueError(f"{label}: incomplete proof")
    states = {}
    for assumption in stated["assumptions"]:
        identity = assumption.get("id", "")
        if identity.startswith("observed-initializer:"):
            _, name, provider, state = identity.split(":")
            if name not in roots:
                raise ValueError(f"{label}: unexpected observed class")
            resource = name.replace(".", "/") + ".class"
            local = classes / resource
            actual = SHA(local) if local.is_file() else hash_bytes(selected_class(jars, resource)[2])
            if actual != provider:
                raise ValueError(f"{label}: different observed class")
            states[name] = state
    if row["verdict"] == "verified" and set(states) != set(roots):
        raise ValueError(f"{label}: missing initializer dependency")
    row["states"] = states
    return row


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def public_sites(out, work, env, java, cp, number, side):
    base = [java, "-XX:ActiveProcessorCount=2", "-Xmx384m", "-Djava.io.tmpdir="+str(work),
            "-cp", cp, "campaign.AvroSites"]
    plain = invocation([*base, "calls", number], "ordinary-jvm", out, work, env)
    traced = invocation([*base, "trace", number, cp, work], "traced-jvm", out, work, env)
    if plain["exit"] or traced["exit"]:
        raise ValueError(f"{number}/{side}: public call-site trace failed, see {out}")
    rows = (out / plain["stdout"]).read_text().splitlines()
    lines = (out / traced["stdout"]).read_text().splitlines()
    actual = [line for line in lines if line.startswith("ROW\t")]
    if actual != rows:
        raise ValueError("the observed JVM changed the public results")
    expected = {}
    for code in range(4):
        for mode in range(3 if number == "364" else 2):
            if number == "364":
                success = mode == 1 or (mode == 0 and side == "fix")
                value = ("A","B")[code % 2] if success else "org.apache.avro.AvroTypeException"
            else:
                value = str(int(mode == 1 or side == "fix"))
            expected[(code,mode)] = value
    parsed = {}
    hits = {key: [] for key in expected}
    for line in lines:
        tag, i, m, *values = line.split("\t")
        key = (int(i), int(m))
        if tag == "ROW" and len(values) == 1 and key not in parsed:
            parsed[key] = values[0]
        elif tag == "SITE" and len(values) == 5:
            owner, argument, answer, caller, hashes = values
            if owner not in (DECODER, RECORD) or len(hashes.split("/")) != 2:
                raise ValueError("unexpected producer")
            hits[key].append(dict(owner=owner, argument=argument, result=answer, caller=caller, codeAndPool=hashes))
        else:
            raise ValueError("unexpected or duplicate trace row")
    if parsed != expected:
        raise ValueError("original Java caller differs from the independent schema or marker oracle")
    for (code, mode), value in expected.items():
        sites = hits[code,mode]
        if number == "364" and value not in ("A","B") or number == "367" and value == "0":
            continue
        fields = (["field"] if number == "364" else ["fieldA", "marker"] if code else ["fieldA"])
        if [s["argument"] for s in sites if s["owner"] == RECORD] != fields:
            raise ValueError(f"missing record lookup at selector {code}, mode {mode}")
        if number == "364" or code:
            wire, decoded = ((2*(code % 2), code % 2) if number == "364" else ([1,0,2][code-1], code-2))
            if not any(s["owner"] == DECODER and (s["argument"], s["result"]) == (str(wire), str(decoded)) for s in sites):
                raise ValueError(f"missing binary read for selector {code}, mode {mode}")
    return {"ordinary":plain, "traced":traced, "rows":[{"input":i,"mode":m,"value":v,"sites":hits[i,m]}
                                                       for (i,m),v in parsed.items()]}


def avro(number, side, target):
    folder, = (ROOT / "examples").glob(number+"-*")
    checker = Path(os.environ["JVMCONTRACT"]).resolve()
    jdk = Path(runtime_jdk.home("21"))
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="avro-reader-facts-") as tmp:
        work=Path(tmp)
        jars, binding = materialize(folder, side, work)
        classes=work/"classes"; classes.mkdir()
        env={**os.environ, "JAVA_HOME":str(jdk), "PATH":str(jdk/"bin")+os.pathsep+os.defpath,"JVMCONTRACT_JAR_RELEASE":"21"}
        cp=os.pathsep.join(map(str,[classes,*jars]))
        src=[*sorted((folder/"adapter").rglob("*.java")), HERE/"ReaderFacts.java", HERE/"AvroSites.java",
             HERE.parent/"domain-foundations/BytesSchema.java"]
        compiled=invocation([jdk/"bin/javac","-J-Djava.io.tmpdir="+tmp,"-parameters","-g","-cp",cp,"-d",classes,*src],
                            "compile",target,work,env)
        if compiled["exit"]:
            raise ValueError(f"original-classpath compilation failed, see {target}")
        providers = {}
        for name in (DECODER, RECORD, *ROOTS):
            index, entry, body = selected_class(jars, name.replace(".","/")+".class")
            providers[name] = {"jar": binding["orderedJars"][index],"entry":entry,"class":hash_bytes(body)}
        report={"schema":"java-domain-reader-facts/v1","example":number,"side":side,"binding":binding,
                "source":os.environ["VERIFY_SOURCE_COMMIT"],"checker":SHA(checker),"jdkModules":SHA(jdk/"lib/modules"),
                "producerClass":SHA(classes/"campaign/ReaderFacts.class"),"providers":providers,"proofs":{}}
        # Each completed query is retained if a later experiment refuses or times out.
        for label, method, guard, assertion, roots in (
            ("one-byte","campaign.ReaderFacts#oneByte","wire >= 0 && wire <= 2","result == 1",()),
            ("configured-byte","campaign.ReaderFacts#configuredByte","wire >= 0 && wire <= 2","result == 1",()),
            ("fields","campaign.ReaderFacts#fields","code >= 0 && code < 4","result == 1",()),
            ("bytes-schema","foundation.BytesSchema#typed",None,"result",()),
            ("factory","foundation.BytesSchema#firstFactory",None,"result",()),
            ("fields-recorded","campaign.ReaderFacts#fields","code >= 0 && code < 4","result == 1",ROOTS)):
            report["proofs"][label] = proof(checker,classes,jars,work,env,target,method,label,guard,assertion,roots)
            document(target/"measurement.json",report)
        # Schema, GenericData, and the reader are the captured roots. Construction of user schemas,
        # namespace resolution, decoder calls and materialization of a default still run in the adapter.
        methods = ("EnumReader", ("renamed","preserved")) if number == "364" else ("DefaultReader", ("union","direct"))
        for method in methods[1]:
            spec=json.loads((folder/"claims"/(method+".json")).read_bytes())
            result=proof(checker,classes,jars,work,env,target,"campaign."+methods[0]+"#"+method,method+"-recorded",
                         spec["assume"],spec["assert"],ROOTS,(spec["bounds"]["unwind"],spec["bounds"]["maxArrayLength"]))
            report["proofs"][method+"-recorded"]=result
            document(target/"measurement.json",report)
        report["callSites"]=public_sites(target,work,env,jdk/"bin/java",cp,number,side)
        document(target/"measurement.json",report)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example",choices=("364","367"))
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    for side in ("parent","fix"):
        avro(args.example,side,args.output.resolve()/side)

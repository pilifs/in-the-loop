"""Check the next ordinary Jackson initializers and the public reducer lookup on a newly constructed JobConf."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from schema_sets import native
from startup import HERE, ROOT, compile_java, document, materialize, runtime_jdk, runtime_maven

SHA = runtime_maven.sha256_of
JOB = "org.apache.hadoop.mapred.JobConf"
CONFIG = "org.apache.hadoop.conf.Configuration"
CREDS = "org.apache.hadoop.security.Credentials"


def hadoop(exe, jdk, work, out, classes, jars, binding, profile):
    cp = os.pathsep.join(map(str, jars))
    xml = "<configuration><property><name>mapreduce.job.reduces</name><value>7</value></property></configuration>\n"
    resources = work/"resource-controls"
    resources.mkdir()
    for name in ("mapred-site.xml", "reducers-explicit.xml"):
        (resources/name).write_text(xml)
    java = [jdk/"bin/java", "-Djava.io.tmpdir="+str(work), "-XX:ActiveProcessorCount=2", "-cp",
            os.pathsep.join([str(classes), cp]), "foundation.FreshReducers"]
    controls = ("fresh", "isolated", "malformed", "resource")
    for method in controls[:3]:
        subprocess.run([*java, method], cwd="/", env={}, check=True, capture_output=True, timeout=30)
    with_resources = java.copy()
    with_resources[-2] = str(resources)+os.pathsep+java[-2]
    for method in ("fresh", "resource"):
        subprocess.run([*with_resources, method], cwd="/", env={}, check=True, capture_output=True, timeout=30)
    env = dict(os.environ, JAVA_HOME=str(jdk), JVMCONTRACT_JAR_RELEASE="21", PATH=str(jdk/"bin")+os.pathsep+os.defpath)
    record = {"source":binding, "checkerSha256":SHA(exe), "jdkModulesSha256":SHA(jdk/"lib/modules"),
              "adapterSha256":SHA(classes/"foundation/FreshReducers.class"), "xmlSha256":SHA(resources/"mapred-site.xml"),
              "physical":list(controls[:3]), "physicalWithResource":["fresh","resource"], "claims":{}}
    scopes = {"ordinary":[], "configuration":[CONFIG], "job":[JOB], "job-credentials":[JOB,CREDS]}
    for scope, roots in scopes.items():
        for method in (("fresh", "isolated", "malformed", "wrong") if scope == "job-credentials" else ("fresh",)):
            target = "foundation.FreshReducers#" + ("fresh" if method == "wrong" else method)
            assertion = "!result" if method == "wrong" else "result"
            key = scope+"-"+method
            cmd = [exe,"prove",target,"--classes",classes,"--classpath",cp,"--engine","native","--gaps","strict",
                   "--assert",assertion,"--unwind","64","--max-array-length","128","--work",work/key,"--json"]
            for root in roots: cmd.extend(["--observed-initializer",root])
            if roots: cmd.extend(["--observed-runtime",json.dumps(profile)])
            start = time.monotonic()
            raw = subprocess.run(cmd, env=env, capture_output=True, timeout=90)
            if not raw.stdout: raise ValueError(raw.stderr.decode(errors="replace")[-600:])
            row, = json.loads(raw.stdout)
            stated = row["stated"]
            premises = [x["id"] for x in stated["assumptions"] if x["kind"] == "library"]
            named = {x.split(":")[1] for x in premises if x.startswith("observed-initializer:")}
            if row["target"] != target or row["assert"] != assertion or stated["gap_mode"] != "strict" or named != set(roots):
                raise ValueError("different Hadoop public entry or startup assumptions")
            if not roots and premises: raise ValueError("unexpected ordinary Hadoop premise")
            if row["verdict"] == "verified" and stated["vacuity"]["status"] != "non-vacuous": raise ValueError("vacuous Hadoop result")
            if row["verdict"] == "violation" and method not in ("wrong",):
                raise ValueError("public lookup contradicted its original physical oracle")
            p = out/(key+".native.json"); p.write_bytes(raw.stdout)
            record["claims"][key] = {"roots":roots, "verdict":row["verdict"], "firstOutstanding":row["problem"],
                "premises":premises,"raw":p.name,"sha256":SHA(p),"seconds":round(time.monotonic()-start,3)}
            print(key,row["verdict"],row["problem"],flush=True)
            document(out/"reducers.json",record)


def run(number, side, output):
    case, = (ROOT/"examples").glob(number+"-*")
    jdk = Path(runtime_jdk.home("21"))
    if runtime_jdk.release(jdk)["JAVA_VERSION"] != "21.0.13": raise ValueError("wrong subject JDK")
    exe = Path(os.environ["JVMCONTRACT"]).resolve()
    out = output/number/side
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="startup-producers-") as td:
        work=Path(td)
        jars,binding=materialize(case,side,work)
        classes=work/"classes"
        compile_java(jdk,work,classes,HERE/"BytesSchema.java",jars)
        java=[jdk/"bin/java","-XX:ActiveProcessorCount=2","-Djava.io.tmpdir="+td,"-cp",os.pathsep.join(map(str,[classes,*jars])),"foundation.BytesSchema"]
        controls=["firstFactory","mapper","typed"]+(["logger"] if number=="355" else [])
        for method in controls:
            subprocess.run([*java,method],cwd="/",env={},check=True,capture_output=True,timeout=30)
        record={"source":binding,"jdkModulesSha256":SHA(jdk/"lib/modules"),"checkerSha256":SHA(exe),
                "adapterSha256":SHA(classes/"foundation/BytesSchema.class"),"physical":controls,"claims":{}}
        for limit in (64,512):
            for method in (controls if limit==512 else ["firstFactory","typed"]):
                row=native(exe,jdk,work,classes,out,"unwind-"+str(limit),"BytesSchema#"+method,
                           "verified" if limit==512 and method=="firstFactory" else None,jars,unwind=limit)
                record["claims"][str(limit)+"-"+method]=row
                document(out/"jackson.json",record)
                print(number,side,limit,method,row["verdict"],row["firstUnknown"],flush=True)
        if number=="355":
            compile_java(jdk,work,classes,HERE/"FreshReducers.java",jars)
            profile=json.loads((case/"claims/bounds-lookup-startup.json").read_bytes())["observedRuntime"]
            hadoop(exe,jdk,work,out,classes,jars,binding,profile)
        if any(not row["matchedExpectation"] for row in record["claims"].values()):
            raise ValueError("a Jackson result differs from its expectation")


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--example",choices=("355","361"),required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    for side in ("parent","fix"): run(a.example,side,a.output)

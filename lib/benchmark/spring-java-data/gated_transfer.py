"""Price reusing the released binder-prefix evidence on a real authorization-gated edit."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

from measure import HERE, ROOT, SETUP, digest, read, run_cmd, write
from targets import finite_check, route, runtime_jdk, sidecar
sys.path.insert(0,str(HERE.parent / "domain-foundations"))
from results import Job

BINDER = ROOT / "examples/368-spring-binding-history"
ROLES = ROOT / "examples/370-spring-role-hierarchy"
PRODUCER = "20261122-161543-spring-binder-edits-and-the-persistent-f"

def binder_receipts(job, identities):
    base = BINDER.relative_to(ROOT)
    run = read(job.output(base / "records/opening/run.json"))
    packet = {}
    example = read(BINDER / "example.json")
    spec = sidecar.load(BINDER,example)
    for task in ("beans-combined","ledger-combined"):
        plan = route.resolve(BINDER,example,spec,task)
        p = job.output(base / run["finite"]["directory"] / (task+".json"))
        record = read(p)
        finite_check.validate_record(plan,record)
        if (record["status"] != "established" or record["inputs"] != 12
                or record["jdkRelease"]["JAVA_RUNTIME_VERSION"] != identities["jdkRelease"]["JAVA_RUNTIME_VERSION"]
                or record["sides"]["combined"]["classpath"] != [c for c in identities["classpath"] if c["role"] != "driver"]):
            raise ValueError("different binder dependency graph, scope or result")
        packet[task] = {"sha256":digest(p),"claimKey":record["sourceClaim"],"inputs":12,"originalFiniteSeconds":record["wallSeconds"]}
    return packet


def producer_replay(job, folder, task, side, jars):
    # A job can archive earlier attempts. Bind the producing attempt and original classpath.
    candidates = []
    for p in job.files:
        if p.match(f"receipts/{task}/*/result.json"):
            r = read(job.output(p))
            pipeline = r["attempt"].get("pipeline") or {}
            if (pipeline.get("jobId") == job.record["id"]
                    and pipeline.get("sourceCommit") == job.record["sourceCommit"]
                    and r["conclusion"]["expectation"] == "yes"
                    and folder.relative_to(ROOT) in p.parents):
                candidates.append(p.parent)
    replay, = candidates
    controls = read(job.output(replay/"records/controls.json"))["records"]
    observed, = [c for c in controls if c["revision"] == side]
    cp = observed["identities"]["classpath"]
    if job.record["status"] != "passed" or observed["exitCode"] or [c["sha256"] for c in cp if c["role"] == "dependency"] != list(jars):
        raise ValueError("different producer result or ordered dependency graph")
    log = job.output(replay / "records" / Path(observed["stdout"]).name)
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    if rows != observed["observations"]:
        raise ValueError("producer rows differ from its replay receipt")
    return rows, observed["identities"], log


def load_producer(jars, actual_classes):
    started = time.perf_counter()
    job = Job(PRODUCER)
    rows, identities, log = producer_replay(job, BINDER, "replay", "combined", jars)
    original, = [c for c in identities["classpath"] if c["role"] == "original"]
    packet = binder_receipts(job, identities)
    # Recreate the producer fixture JAR under the standard recipe. Compare its bytecode and all inner classes.
    from targets import runtime
    example = read(BINDER / "example.json")
    spec = sidecar.load(BINDER, example)
    with tempfile.TemporaryDirectory(prefix="rebind-binder-") as tmp:
        p = runtime.prepare(route.resolve(BINDER,example,spec,"beans-combined"),"combined",Path(tmp)/"prepare")
        if p.stage != "artifacts-ready": raise ValueError(p.diagnostic)
        jar = Path(p.workdir) / original["path"]
        if digest(jar) != original["sha256"]: raise ValueError("different binder application artifact")
        with zipfile.ZipFile(jar) as archive:
            import hashlib
            captured = {n:hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist() if n.endswith(".class")}
        if captured != actual_classes: raise ValueError("different application bytecode at the consuming call")
    prefix = {}
    for r in rows:
        if r["input"]["order"] == [0,1,2]:
            val=r["direct"]
            prefix[r["input"]["shared"]] = list(zip(val["beans"],val["ledger"],strict=True))
    if set(prefix)!={True,False}: raise ValueError("incomplete producer prefix evidence")
    return prefix,{"job":PRODUCER,"receipts":packet,"physicalSha256":digest(log),"originalJar":original["sha256"],
                   "requalificationSeconds":time.perf_counter()-started}

def expected(shared, grants, primary, prefix=None):
    accepted=0;name=False;bad=False;good=False;rows=[]
    for step,grant in enumerate(grants):
        if grant or (primary and step<2):
            accepted+=1
            if step==0:name=True
            if step==1:bad=True
            if step==2:good=True
        if prefix is not None:
            # The combined primary visits the first, second and possibly third A1 prefixes in order.
            bean,error=prefix[shared][accepted-1]
        else:
            count=7 if good else 1
            bean=["Kim" if name else "initial",count,"Kim" if shared and name else "initial",count if shared else 1,shared,True]
            error=[int(bad),"backup.count" if bad else None,"oops" if bad else None,count,count if shared else 1]
        rows.append([grant,accepted,bean,error])
    return rows

def check(path, prefix=None):
    granted=0
    rows=[json.loads(s) for s in path.read_text().splitlines()]
    if len(rows)!=72:raise ValueError("missing combined histories")
    for i,r in enumerate(rows):
        if i<64:
            shared,custom,mask=i>=32,bool(i&16),i&15
            request={"shared":shared,"prefix":"CUSTOM_PREFIX_" if custom else "ROLE_","mask":mask}
            grants=[True,True,bool(mask&11)]
            granted+=grants[-1]
        else:
            s=i-64;shared=s>=4
            request={"shared":shared,"prefix":"CUSTOM_PREFIX_" if s&2 else "ROLE_","history":1+(s&1)}
            grants=[True,bool(s&1),True]
        wanted=expected(shared,grants,i<64,prefix if i<64 else None)
        if (r["id"]!=i or r["input"]!=request or r["direct"]!=wanted):
            raise ValueError(f"decision, applied edit, receiver identity or ledger differs at history {i}")
    return {"primary":64,"grantedThird":granted,"declinedThird":64-granted,"withEarlierError":64,"additional":8}

def run(out, physical_only=False):
    out.mkdir(parents=True,exist_ok=True)
    # Use the exact ordered graph already frozen on both applications.
    paths=[Path(s) for s in (SETUP/"releases/spring-security-6.3.0-framework-6.1.7/classpath.txt").read_text().strip().split(os.pathsep)]
    graph=[digest(p) for p in paths]
    for folder,side in [(BINDER,"combined"),(ROLES,"release")]:
        spec=read(folder/"target.json");libs=read(folder/spec["preparation"]["libraryCatalog"])
        if [libs[n]["sha256"] for n in spec["history"]["revisions"][side]["runtimeLibraries"]]!=graph:
            raise ValueError("different consumer runtime classpath")
    jdk=Path(runtime_jdk.home("21"))
    sources=[*sorted((BINDER/"application").rglob("*.java")),*sorted((ROLES/"application").rglob("*.java")),
             HERE/"GatedBinding.java",ROOT/"examples/tools/targets/java/org/intheloop/controls/Grid.java"]
    with tempfile.TemporaryDirectory(prefix="gated-bind-") as tmp:
        cls=Path(tmp);cp=os.pathsep.join(map(str,[cls,*paths]))
        compiling=time.perf_counter()
        subprocess.run([jdk/"bin/javac","--release","21","-parameters","-cp",cp,"-d",cls,*sources],check=True)
        compiled_seconds=time.perf_counter()-compiling
        binder_classes={p.relative_to(cls).as_posix():digest(p) for p in (cls/"springwork").glob("BindingHistory*.class")}
        report={"commonCompileSeconds":compiled_seconds,"runtimeJars":graph,"jdk":runtime_jdk.release(jdk),"consumerClass":digest(cls/"springwork/GatedBinding.class"),
                "binderClasses":binder_classes,"sources":{p.name:digest(p) for p in sources},"routes":{}}
        for name in ("fresh","reuse"):
            started=time.perf_counter()
            prefix=None
            if name=="reuse":prefix,report["producer"]=load_producer(graph,binder_classes)
            path=out/(name+".jsonl")
            java=run_cmd([jdk/"bin/java","-Xmx256m","-Duser.timezone=UTC","-cp",cp,"springwork.GatedBinding"],path)
            if java["exit"]:raise ValueError("combined caller failed")
            before=time.perf_counter();counts=check(path,prefix);validation=time.perf_counter()-before
            report["routes"][name]={"publicCaller":java,"counts":counts,"checkSeconds":validation,
                                    "wholeSeconds":time.perf_counter()-started,"sha256":digest(path)}
        if report["routes"]["fresh"]["sha256"]!=report["routes"]["reuse"]["sha256"]:
            raise ValueError("paired routes observed different public histories")
        if physical_only:
            write(out/"measurement.json",report)
            return
        checker=Path(os.environ["JVMCONTRACT"])
        report["ordinaryNative"]={}
        env=dict(os.environ,JAVA_HOME=str(jdk),JVMCONTRACT_JAR_RELEASE="21",PATH=str(jdk/"bin")+os.pathsep+os.defpath)
        for label,guard in (("all","code >= 0 && code < 64"),("declined","code == 0")):
            cmd=[checker,"prove","springwork.GatedBinding#primary","--classes",cls,"--classpath",os.pathsep.join(map(str,paths)),
                 "--engine","native","--gaps","strict","--assume",guard,"--assert","result == 1","--unwind","256",
                 "--max-array-length","16384","--timeout","60","--work",cls/label,"--json"]
            raw=out/(label+".json")
            cost=run_cmd(cmd,raw,env)
            outcome,=read(raw)
            if outcome["assume"]!=guard or outcome["stated"]["gap_mode"]!="strict":raise ValueError("different native scope")
            report["ordinaryNative"][label]={"receipt":raw.name,"sha256":digest(raw),"cost":cost,"guard":guard,
                                             "verdict":outcome["verdict"],"firstBlocker":outcome["problem"]}
        report["checkerSha256"]=digest(checker)
        write(out/"measurement.json",report)

if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output",type=Path,required=True)
    cli.add_argument("--physical-only",action="store_true")
    args=cli.parse_args()
    run(args.output,args.physical_only)

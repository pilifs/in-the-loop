"""Run the original public valid-assert programs and keep finite-choice replays separate."""
import argparse
import bz2
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from history import HERE, OUTPUT, ROOT, JBMC, MODELS, digest, encoded, scratch, benchmark
from stock_history import classpath
from release_cases import JDK, javaenv, compile_java

CACHE = Path.home()/".cache/in-the-loop/beyond-jbmc"
TREE = CACHE/"src/sv-benchmarks-7efe28dd"
REV = "7efe28dd29576b46927b7a34e8f742bd90966a75"
XML = CACHE/"svcomp/results.xml.bz2"
TASKS = [
    ("jbmc-regression/StringBuilderCapLen01",""),("jbmc-regression/StringBuilderCapLen02","s"),
    ("jbmc-regression/StringBuilderInsertDelete01",""),("jbmc-regression/StringBuilderInsertDelete02","s,s"),
    ("jayhorn-recursive/SatFibonacci02",""),("jayhorn-recursive/UnsatFibonacci02","i8"),
    ("jayhorn-recursive/SatEvenOdd01","i7"),("jayhorn-recursive/UnsatEvenOdd01","i0"),
    ("algorithms/BinaryTreeSearch-FunSat01","i3,i0,i5,i-1"),("algorithms/BinaryTreeSearch-FunUnsat01","i2,i0"),
    ("algorithms/InsertionSort-FunSat01","i5"),("algorithms/InsertionSort-FunUnsat01","i2,i0,i0"),
]


def check_source(path):
    rel=path.relative_to(TREE).as_posix()
    if subprocess.check_output(["git","-C",TREE,"show",REV+":"+rel]) != path.read_bytes():
        raise ValueError("source differs from the pinned public task: "+rel)
    return digest(path)


def competition():
    if digest(XML)!="f3e17836d3863f21c912a6bdd0ce187580b89382187488940e0715abdeed0f35": raise ValueError("official results differ")
    root=ET.fromstring(bz2.decompress(XML.read_bytes()))
    return {r.attrib["name"].split("/java/")[-1].removesuffix(".yml"):
            {"expected":r.attrib["expectedVerdict"],**{c.get("title"):c.get("value") for c in r.findall("column")
             if c.get("title") in ("status","cputime","walltime","category")}}
            for r in root.findall("run") if r.get("properties")=="valid-assert"}


def outputs(measured,archive,key,cmd):
    archive.writestr(key+"/argv.json",encoded(cmd))
    for channel in ("stdout","stderr"): archive.writestr(key+"/"+channel,measured[channel])
    return {k:v for k,v in measured.items() if k not in ("stdout","stderr")}


def direct(main, method, cp, work, archive):
    cmd=[str(JBMC),main,"--classpath",classpath(cp),"--function",method,"--throw-runtime-exceptions",
         "--unwind","16","--unwinding-assertions","--max-nondet-array-length","8","--sat-solver","cadical","--trace","--json-ui"]
    m=benchmark.measure(cmd,120)
    record=outputs(m,archive,"stock/"+main,cmd)
    if m["killed"]: return dict(record,status="timeout",targets=[])
    try: doc=json.loads(m["stdout"])
    except (ValueError,TypeError): return dict(record,status="missing property report",targets=[])
    props=[p for block in doc for p in block.get("result",[])]
    orig=[p for p in props if p.get("sourceLocation",{}).get("propertyClass")=="assertion" and
          p["property"].startswith(f"java::{main}.")]
    failed=[p["property"] for p in props if p["status"]!="SUCCESS" and p not in orig]
    return dict(record,status=next((b["cProverStatus"] for b in reversed(doc) if "cProverStatus" in b),"incomplete"),
                targets=[{k:p.get(k) for k in ("property","status","sourceLocation")} for p in orig],
                otherFailures=failed,unwinding=[x for x in failed if "unwind" in x])


def task(i,official,phase,out,check_only):
    name,choices=TASKS[i]
    key=f"B{i+1:02d}"
    yml=TREE/"java"/(name+".yml")
    java=TREE/"java"/name/"Main.java"
    prop=TREE/"java/properties/valid-assert.prp"
    files={p.relative_to(TREE).as_posix():check_source(p) for p in (java,yml,prop,*sorted((TREE/"java/common").rglob("*.java")))}
    expected=official[name]["expected"]=="true"
    if expected!=(i%2==0) or not re.search(r'valid-assert\.prp\s+expected_verdict: '+str(expected).lower(),yml.read_text()):
        raise ValueError("wrong public property")
    env=javaenv()
    os.environ.update({k:env[k] for k in ("JAVA_HOME","PATH","JVMCONTRACT_JAR_RELEASE")})
    checker=str(Path(os.environ.get("JVMCONTRACT",ROOT/"lib/target/release/jvmcontract")).resolve())
    with scratch(prefix="sv-public-") as tmp:
        work=Path(tmp);classes=work/"original";local=HERE/"sv";package="org/sosy_lab/sv_benchmarks/Verifier.class"
        # Stock supplies the competition nondeterminism interface. No Random body from the corpus's JVM approximator is compiled.
        compile_java([java,local/"PublicAssertion.java",local/"SVReach.java"],classes,[MODELS],env)
        if (classes/package).exists(): raise ValueError("classes would shadow the stock nondeterminism implementation")
        shim=work/"nondeterminism"
        with zipfile.ZipFile(MODELS) as z:
            path=shim/package;path.parent.mkdir(parents=True);path.write_bytes(z.read(package))
        source=work/"Verifier.java";shutil.copyfile(local/"ReplayChoices.java.txt",source)
        replay=work/"replay"
        compile_java([source,TREE/"java/common/org/sosy_lab/sv_benchmarks/ObjectFactory.java"],replay,[],env)
        cmd=[str(JDK/"bin/java"),"-Xint","-ea","-Dsv.choices="+choices,"-cp",classpath([replay,classes]),"Main"]
        sample=subprocess.run(cmd,text=True,capture_output=True,env=env,timeout=15)
        named=re.search(r"java\.lang\.AssertionError.*?\n\s*at (Main(?:\$[\w$]+)?\.\w+\(Main\.java:\d+\))",sample.stderr,re.S)
        if expected and sample.returncode or not expected and (sample.returncode!=1 or not named):
            raise ValueError("original JVM control mismatch: "+key)
        record={"case":key,"task":name,"expected":expected,"competition":official[name],"sourceSha256":files,"revision":REV,
                "mainSha256":digest(classes/"Main.class"),"nondeterminismClassSha256":digest(shim/package),
                "jvm":{"argv":cmd,"exit":sample.returncode,"stdout":sample.stdout,"stderr":sample.stderr,"topOriginalSite":named.group(1) if named else None},
                "jdkModulesSha256":digest(JDK/"lib/modules"),"jbmcSha256":digest(JBMC),"coreModelsSha256":digest(MODELS),
                "nativeSha256":digest(Path(checker)), "job":os.environ.get("VERIFY_JOB_ID"),"sourceCommit":os.environ.get("VERIFY_SOURCE_COMMIT")}
        if check_only:
            print(key,"valid-assert",expected,record["jvm"]["topOriginalSite"],flush=True)
            return
        caseout=out/key;caseout.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(caseout/"executions.zip","w",zipfile.ZIP_DEFLATED) as archive:
            record["stock"]=direct("Main","Main.main:([Ljava/lang/String;)V",[classes,MODELS],work,archive)
            record["stockReach"]=direct("SVReach","SVReach.afterMain:()V",[classes,MODELS],work,archive)
            for engine in ("native","jbmc"):
                cmd=[checker,"prove","PublicAssertion#holds","--classes",str(classes),"--classpath",str(shim),"--engine",engine,
                     "--assert","result","--gaps","strict","--unwind","16","--max-array-length","8","--timeout","120",
                     "--jbmc",str(JBMC),"--jbmc-staging","staged","--json","--work",str(work/engine)]
                m=benchmark.measure(cmd,240);r=outputs(m,archive,engine,cmd);data=benchmark.outcome_of({"kind":"property"},m["stdout"])
                if data:r.update({k:data.get(k) for k in ("verdict","problem","counterexample","stated")})
                record[engine]=r
        record["traceArchiveSha256"]=digest(caseout/"executions.zip")
        (caseout/"result.json.gz").write_bytes(gzip.compress(encoded(record),mtime=0))
        print(key,name,record["native"].get("verdict"),record["jbmc"].get("verdict"),record["stock"]["status"],flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--physical-only",action="store_true")
    p.add_argument("--phase",default="closing",choices=("opening","closing"))
    p.add_argument("cases", nargs="*", help="exact B IDs, all twelve by default")
    args=p.parse_args()
    official=competition()
    ids = [f"B{i+1:02d}" for i in range(len(TASKS))]
    selected = args.cases or ids
    if len(set(selected)) != len(selected) or not set(selected) <= set(ids): p.error("unknown or repeated B task")
    for key in selected: task(ids.index(key),official,args.phase,OUTPUT/args.phase/"svcomp",args.physical_only)

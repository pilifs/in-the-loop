"""Compare Mexico City transition endpoints and an independently selected unaffected resource."""
import argparse
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
from history import ROOT,HERE,OUTPUT,encoded,digest,benchmark,scratch
from release_cases import Claim,Subject,jars_for,jvm_controls,measure_subject,compile_java,javaenv,JDK
from stock_history import classpath
from zone_select import selection,PIN

BORDER=tuple((str(t)+"L",) for t in (1672531200000,1680422399999,1680422400000,1698562799999,1698562800000,1704067199999))
SUMMER=(("1681560000000L",),)
OLD="joda-time-2.12.0";NEW="joda-time-2.12.1"

def measure(checker,cmd,archive,name):
    r=benchmark.measure(cmd,180)
    for field in ("stdout","stderr"):archive.writestr(name+"/"+field,r[field])
    kind="property" if cmd[1]=="prove" else "regression"
    data=benchmark.outcome_of({"kind":kind},r["stdout"]) or {}
    return {"argv":list(map(str,cmd)),"cost":{k:r[k] for k in ("seconds","cpuSeconds","peakMB","exit","killed")},
            "verdict":data.get("verdict"),"stated":data.get("stated"),"problem":data.get("problem"),"counterexample":data.get("counterexample")}

def main(physical_only):
    pin=selection()
    if pin!=json.loads(PIN.read_bytes()) or pin["selected"]!="Etc/GMT+7":raise ValueError("zone differs from the pre-solver draw")
    env=javaenv()
    os.environ.update({k:env[k] for k in ("JAVA_HOME","PATH","JVMCONTRACT_JAR_RELEASE")})
    output=OUTPUT/"qualified/C06-C07"
    checker=Path(os.environ.get("JVMCONTRACT",ROOT/"lib/target/release/jvmcontract")).resolve()
    with scratch(prefix="zone-reuse-") as tmp:
        work=Path(tmp); classes=work/"classes"
        compile_java([HERE/"extended/ZoneChecks.java"],classes,jars_for(OLD),env)
        scans={}
        for old,graph in ((True,OLD),(False,NEW)):
            jars=jars_for(graph);folder=work/graph;folder.mkdir()
            cp=[classes,*jars]
            cmd=[JDK/"bin/java","-Duser.timezone=UTC","-ea","-cp",classpath(cp),"ZoneChecks"]
            lines=subprocess.check_output(cmd,env=env,text=True).splitlines()
            expected=["America/Mexico_City at-start -21600000"]
            if old:expected+=["America/Mexico_City transition 1680422400000 -21600000 -18000000","America/Mexico_City transition 1698562800000 -18000000 -21600000"]
            expected+=["Etc/GMT+7 at-start -25200000"]
            if lines!=expected:raise ValueError((lines,expected))
            scans[graph]={"argv":list(map(str,cmd)),"observations":lines}
            claims=(Claim("oldSchedule","long instant",holds=BORDER if old else BORDER[:2],fails=() if old else SUMMER),
                    Claim("newSchedule","long instant",holds=BORDER[:2] if old else BORDER,fails=SUMMER if old else ()),
                    Claim("unaffected","long instant",holds=BORDER))
            subject=Subject(0,"ZoneChecks",graph,claims)
            record={"jvm":jvm_controls(subject,folder,cp,env),"rows":[],"scope":"all milliseconds in UTC calendar 2023",
                    "classpathSha256":[digest(j) for j in jars],"zoneSelection":pin,"jvmcontractSha256":digest(checker),
                    "job":os.environ.get("VERIFY_JOB_ID")}
            measure_subject(graph,subject,"qualified",folder,env,cp,record,output/graph,physical_only)
        if physical_only:return
        rows=[];output.mkdir(parents=True,exist_ok=True)
        oldj,newj=jars_for(OLD),jars_for(NEW)
        with zipfile.ZipFile(output/"reuse.zip","w",zipfile.ZIP_DEFLATED) as archive:
            for m in ("oldSchedule","unaffected"):
                for phase,dep,cache in (("old",oldj,"shared"),("new-warm",newj,"shared"),("new-clean",newj,"clean")):
                    key=m+"-"+phase
                    cmd=[str(checker),"prove","ZoneChecks#"+m,"--classes",str(classes),"--classpath",classpath(dep),
                         "--assert","result","--engine","native","--gaps","strict","--cache",str(work/(m+cache)),
                         "--work",str(work/key),"--unwind","16","--max-array-length","8","--timeout","120","--json"]
                    rows.append(dict(measure(checker,cmd,archive,key),method=m,phase=phase,jar=digest(dep[0])))
            oldroot=work/"old-caller";shutil.copytree(classes,oldroot)
            for m in ("offsetMexico","offsetControl"):
                cmd=[str(checker),"equivalence","--before",str(oldroot),"--after",str(classes),"--target","ZoneChecks#"+m,
                     "--before-classpath",classpath(oldj),"--classpath",classpath(newj),"--engine","native","--gaps","strict",
                     "--assume","t >= 1672531200000L && t < 1704067200000L","--unwind","16","--max-array-length","8",
                     "--work",str(work/m),"--timeout","120","--json"]
                rows.append(dict(measure(checker,cmd,archive,m),method=m,phase="two-version original classpaths"))
        (output/"reuse.json.gz").write_bytes(gzip.compress(encoded({"job":os.environ.get("VERIFY_JOB_ID"),"selection":pin,
                    "originalTransitionScan":scans,"cacheAndEquivalence":rows}),mtime=0))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--physical-only",action="store_true")
    main(p.parse_args().physical_only)

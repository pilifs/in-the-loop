"""Compare a direct array construction plan and replay a worker-first schedule on the original JVM."""
import argparse
import gzip
import os
from pathlib import Path
import subprocess
import tempfile

from campaign import CACHE, HERE, JDK, ROOT, command, compile_java, digest, java_source, javaenv, write
from standalone import decode


def schedules(work):
    folder=ROOT/"examples/391-class-monitor-identity"
    source=folder/"adapter/MonitorIdentity.java"
    line, = (n for n,s in enumerate(source.read_text().splitlines(),1) if "protectedRead = shared == 5;" in s)
    cp=work/"caller"
    compile_java([source,folder/"controls/MonitorLaunch.java"],cp,[],javaenv())
    observer=folder/"controls/ObserveSchedule.java"
    subprocess.run([JDK/"bin/javac","--add-modules","jdk.jdi","-d",work,observer],check=True)
    rows={}
    for mode in ("matched","mixed","synchronizedMethod"):
        code,out,err,secs=command([JDK/"bin/java","--add-modules","jdk.jdi","-cp",work,"ObserveSchedule",mode,cp,str(line)],javaenv(),35)
        if code!=0: raise ValueError(f"JVM scheduling control {mode}: {err.decode()}")
        rows[mode]={"observations":out.decode().splitlines(),"seconds":secs}
    return {"classes":{p.name:digest(p) for p in cp.glob("*.class")},"observerSha256":digest(observer),
            "breakpoint":{"class":"MonitorIdentity","method":"observe","line":line},"runs":rows}


def direct_threads(work,dest):
    source=ROOT/"examples/391-class-monitor-identity/controls/MonitorProfiles.java"
    package=CACHE/"releases/cbmc-6.11.0/ubuntu-22.04"
    binary=package/"bin/jbmc"; core=package/"lib/core-models.jar"
    flags=["--java-threading","--unwind","16","--unwinding-assertions","--throw-runtime-exceptions",
           "--sat-solver","cadical","--trace","--json-ui"]
    rows={}
    for layout in ("target","reached"):
        variant=work/layout;variant.mkdir()
        text=source.read_text()
        if layout=="reached":
            if text.count("assert shared == 5;")!=3: raise ValueError("changed monitor assertion")
            text=text.replace("assert shared == 5;","int observed = shared; assert observed != observed;")
        java=java_source(variant/"MonitorProfiles.java",text)
        classes=variant/"classes"
        compile_java([java],classes,[],javaenv())
        for method in ("matched","mixed","staticMethod"):
            code,out,err,secs=command([binary,"MonitorProfiles","-cp",str(classes)+os.pathsep+str(core),
                                      "--function","MonitorProfiles."+method,*flags],javaenv())
            name=layout+"-"+method+".json.gz"
            (dest/name).write_bytes(gzip.compress(out,mtime=0))
            rows.setdefault(method,{})[layout]=dict(decode(out,err,code,method,"MonitorProfiles"),
                   seconds=secs,raw=name,sha256=digest(dest/name),classSha256=digest(classes/"MonitorProfiles.class"))
    return {"runs":rows,"flags":flags,"binarySha256":digest(binary),"modelsSha256":digest(core)}


def array_plan(work,dest):
    source=ROOT/"examples/379-nullable-reference-arrays/adapter/ReferenceCells/ReferenceCells.java"
    classes=work/"array";compile_java([source],classes,[],javaenv())
    plan={"nodes":[],"roots":[{"name":"values","value":{"kind":"array","path":"values","element":"ReferenceCells$Item",
          "max_length":2,"nullable":True}}],"bounds":{"nodes":0,"max_array_length":2,"setup_calls":0}}
    file=dest/"reference-array-plan.json";write(file,{"before":plan,"after":plan})
    exe=Path(os.environ["JVMCONTRACT"]).resolve()
    code,out,err,secs=command([exe,"prove","--classes",classes,"ReferenceCells#categories","--plan",file,
          "--assert","result","--engine","native","--gaps","strict","--max-array-length","2","--unwind","16",
          "--timeout","120","--work",work/"planned","--json"],javaenv())
    (dest/"planned.json").write_bytes(out);(dest/"planned.stderr").write_bytes(err)
    from campaign import wire
    r=wire.decode(out.decode(errors="replace"),"prove")
    if not r.ok or len(r.outcomes)!=1:
        if not err.strip(): raise ValueError("missing construction-plan diagnostic")
        why=err.decode(errors="replace")
        verdict="frontend refusal"
    else:
        value,=r.outcomes;verdict=value["verdict"];why=value.get("problem")
    return {"checkerSha256":digest(exe),"classSha256":digest(classes/"ReferenceCells.class"),"seconds":secs,
            "planSha256":digest(file),"exit":code,"verdict":verdict,"diagnostic":why}


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--jvm-only",action="store_true")
    p.add_argument("--output",type=Path,default=ROOT/"verification/java-semantics-gap/heap-and-monitors")
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="semantics-schedules-") as tmp:
        w=Path(tmp); report={"job":os.environ.get("VERIFY_JOB_ID"),"source":os.environ.get("VERIFY_SOURCE_COMMIT"),
                              "jvmSha256":digest(JDK/"bin/java"),"jvm":schedules(w)}
        if not a.jvm_only:
            report["standalone"]=direct_threads(w,a.output); report["arrayPlan"]=array_plan(w,a.output)
        write(a.output/"measurement.json",report)
        print(report["jvm"]["runs"])

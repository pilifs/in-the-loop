"""Qualify each side of the real encoder's bulk-write branch and challenge its thread prestate."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from startup import HERE, ROOT, compile_java, document, materialize, runtime_jdk, runtime_maven

GUARDS = {"buffered":"code >= 0 && code < 16 && code != 11 && code != 15","channel":"code == 11 || code == 15"}
SHA=runtime_maven.sha256_of


def run(output):
    case,=(ROOT/"examples").glob("362-*")
    jdk=Path(runtime_jdk.home("21")); exe=Path(os.environ["JVMCONTRACT"]).resolve()
    env=dict(os.environ,JAVA_HOME=str(jdk),JVMCONTRACT_JAR_RELEASE="21",PATH=str(jdk/"bin")+os.pathsep+os.defpath)
    for side in ("parent","fix"):
        with tempfile.TemporaryDirectory(prefix="encoder-paths-") as tmp:
            work=Path(tmp);classes=work/"classes";jars,binding=materialize(case,side,work)
            compile_java(jdk,work,classes,case/"adapter/organic/EncoderWindow.java",jars)
            compile_java(jdk,work,classes,HERE/"EncoderInterrupt.java",[classes,*jars])
            cp=os.pathsep.join(map(str,[classes,*jars]));out=output/side;out.mkdir(parents=True,exist_ok=True)
            record={"build":binding,"checkerSha256":SHA(exe),"jdkModulesSha256":SHA(jdk/"lib/modules"),"physical":[],"claims":{}}
            for code in (3,10,11,15):
                for interrupted in ("false","true"):
                    stdout=subprocess.check_output([jdk/"bin/java","-Djava.io.tmpdir="+tmp,"-cp",cp,"organic.EncoderInterrupt",str(code),interrupted],cwd="/",env={},text=True,timeout=25)
                    outcome,pos,limit,count,remaining_flag=stdout.split()
                    bulk=code in (11,15); start=2 if code==15 else 0; length=16 if code==10 else 17
                    expected="java.nio.channels.ClosedByInterruptException" if bulk and interrupted=="true" else "returned"
                    if (outcome!=expected or int(pos)!=start+(length if side=="parent" and bulk else 0)
                        or int(limit)!=start+length or remaining_flag!=interrupted):
                        raise ValueError("original JVM control disagrees: "+str((code,interrupted,stdout)))
                    record["physical"].append({"code":code,"initiallyInterrupted":interrupted=="true","exit":outcome,
                        "position":int(pos),"limit":int(limit),"outputBytes":int(count),"finalInterruptFlag":remaining_flag=="true"})
            for label,guard in GUARDS.items():
                for method in ("cursor","repeated"):
                    key=label+"-"+method; target="organic.EncoderWindow#"+method
                    proc=subprocess.run([exe,"prove",target,"--classes",classes,"--classpath",os.pathsep.join(map(str,jars)),
                            "--engine","native","--gaps","strict","--unwind","64","--max-array-length","128",
                            "--work",work/key,"--assume",guard,"--assert","result == 1","--json"],
                            env=env,capture_output=True,timeout=85)
                    row,=json.loads(proc.stdout);p=out/(key+".native.json");p.write_bytes(proc.stdout)
                    if row["assume"]!=guard or row["target"]!=target or row["assert"]!="result == 1" or row["stated"]["gap_mode"]!="strict":
                        raise ValueError("wrong encoder scope")
                    record["claims"][key]={"target":target,"guard":guard,"verdict":row["verdict"],"firstOutstanding":row["problem"],
                        "vacuity":row["stated"]["vacuity"],"raw":p.name,"sha256":SHA(p)}
            document(out/"evidence.json",record)
            if any(v["verdict"]!="verified" or v["vacuity"]["status"]!="non-vacuous" for k,v in record["claims"].items() if k.startswith("buffered")):
                raise ValueError("unqualified buffered encoding")
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,required=True);run(p.parse_args().output)

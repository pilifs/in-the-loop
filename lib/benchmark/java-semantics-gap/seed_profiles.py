"""Keep the direct floating-point entry and the two default-method classfile layouts distinguishable."""
import argparse
import gzip
import os
import re
from pathlib import Path
import subprocess
import tempfile

from campaign import CACHE, GRAPHS, JDK, ROOT, command, digest, javaenv, write
from standalone import decode


def numeric_replay(work, cp, entry, inputs, env):
    if entry in ("floorOnly","fraction"):
        value = int(inputs["n"]["binary"], 2)
        if value >= 1 << 31: value -= 1 << 32
        arg = str(value)
    else:
        value = int(inputs["x"]["binary"],2)
        arg = f"Double.longBitsToDouble(0x{value:016x}L)"
    f = work/"SeedWitness.java"
    f.write_text(f'public class SeedWitness {{ public static void main(String[] a) {{ try {{ Semantics.{entry}({arg}); '
                 'System.out.println("held"); } catch (AssertionError e) { System.out.println("refuted"); } } }\n')
    p = subprocess.run([JDK/"bin/java","-ea","-cp",cp,f],check=True,capture_output=True,text=True,env=env)
    return {"argument":arg,"outcome":p.stdout.strip(),"sourceSha256":digest(f)}


def measure(out):
    env = javaenv()
    source = (ROOT/"llm-dlc/loops/jbmc-java-semantics-gap-brief.md").read_text()
    numeric, extra = [s+"\n" for s in re.findall(r"^```java\n(.*?)\n```$",source,re.M|re.S)]
    stem = CACHE/"releases/cbmc-6.11.0/ubuntu-22.04"
    binaries = {"installed":Path("/usr/bin/jbmc"),"preflight":stem/"bin/jbmc"}
    models = {"installed":Path("/usr/lib/core-models.jar"),"preflight":stem/"lib/core-models.jar"}
    original = "\n}\n\nclass ExtraOpenersReplay extends ExtraOpeners {"
    if extra.count(original)!=1: raise ValueError("the original replay layout changed")
    dest = out/"seed-profiles"
    dest.mkdir(parents=True,exist_ok=True)
    report = {"job":os.environ.get("VERIFY_JOB_ID"),"source":os.environ.get("VERIFY_SOURCE_COMMIT"),"variants":{}}
    for variant in ("numeric","separate","combined"):
        with tempfile.TemporaryDirectory(prefix="semantics-seed-") as tmp:
            work = Path(tmp)
            number = variant=="numeric"
            owner = "Semantics" if number else "ExtraOpeners"
            graph = GRAPHS["lang-historical" if number else "io"]
            jar, = [CACHE/r["path"] for r in graph]
            if digest(jar)!=graph[0]["sha256"]: raise ValueError("different original subject")
            src = work/(owner+".java")
            src.write_text(numeric if number else extra if variant=="separate" else extra.replace(original,""))
            subprocess.run([JDK/"bin/javac","-source","8","-target","8","-Xlint:-options","-g","-proc:none",
                            "-cp",jar,"-d",work,src],env=env,check=True)
            cp = os.pathsep.join(map(str,[work,jar]))
            main = "ExtraOpenersReplay" if variant=="separate" else owner
            replay = subprocess.run([JDK/"bin/java","-ea","-cp",cp,main],env=env,check=True,capture_output=True,text=True)
            block = {"sourceSha256":digest(src), "classes":{p.name:digest(p) for p in sorted(work.glob("*.class"))},
                     "classpath":["compiled",graph[0]["path"],"core-models.jar"],"originalJvm":{"main":main,"exit":0,"stdout":replay.stdout.strip()},"runs":[]}
            for bin_id,binary in binaries.items():
                for core_id,core in models.items():
                    if number and bin_id!=core_id: continue
                    for entry in (("fraction","floorOnly","narrow","wraps") if number else ("dispatch","firstDeclared")):
                        flags=["--unwind","8" if number else "16","--unwinding-assertions","--throw-runtime-exceptions",
                               "--sat-solver","cadical","--trace","--json-ui"]
                        if number: flags+=["--max-nondet-array-length","2","--max-nondet-tree-depth","4"]
                        code,raw,err,secs=command([binary,owner,"-cp",cp+os.pathsep+str(core),"--function",owner+"."+entry,*flags],env)
                        r=decode(raw,err,code,entry,owner)
                        name=f"{variant}-{bin_id}-{core_id}-{entry}.json.gz"
                        (dest/name).write_bytes(gzip.compress(raw,mtime=0))
                        row=dict(r,entry=entry,binary=bin_id,binarySha256=digest(binary),models=core_id,
                                 modelsSha256=digest(core),flags=flags,seconds=secs,raw=name,sha256=digest(dest/name))
                        if r["status"]=="FAILURE" and number and r.get("inputs"):
                            row["jvmReplay"]=numeric_replay(work,cp,entry,r["inputs"],env)
                        block["runs"].append(row)
            report["variants"][variant]=block
            write(dest/"measurement.json",report)


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output",type=Path,default=ROOT/"verification/java-semantics-gap")
    measure(cli.parse_args().output)

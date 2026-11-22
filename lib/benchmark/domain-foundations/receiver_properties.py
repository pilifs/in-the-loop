"""Prove constructor-domain properties on original receiver classes that have external reference fields."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from startup import HERE, ROOT, document, runtime_jdk, runtime_maven

sys.path.insert(0,str(HERE.parent/"external-upgrades"))
from engineering import preparation_root

CASES = {
    "compsuite-i-70": ("com.monitorjbl.xlsx.impl.StreamingCell", "getCellStyle", "new com.monitorjbl.xlsx.impl.StreamingCell(2,3,false)"),
    "compsuite-i-94": ("com.alibaba.citrus.service.form.impl.validation.DateValidator", "getMinDate", "new com.alibaba.citrus.service.form.impl.validation.DateValidator()"),
}
SHA=runtime_maven.sha256_of


def run(area, output):
    now=Path(os.environ["JVMCONTRACT"]).resolve()
    before_tree="5f16739e2a3796d20fe4150398cdb6305cf959c3"
    before=now.parent.parent/before_tree/"jvmcontract"
    historical=json.loads((ROOT/"verification/domain-foundations/followup.json").read_bytes())
    if SHA(before)!=historical["final"]["executableSha256"]: raise ValueError("wrong baseline checker")
    jdk=Path(runtime_jdk.home("21"))
    env=dict(os.environ,JAVA_HOME=str(jdk),JVMCONTRACT_JAR_RELEASE="21",PATH=str(jdk/"bin")+os.pathsep+os.defpath)
    for key,(owner,method,construction) in CASES.items():
        observed,=(ROOT/"verification/domain-foundations/receiver-confirmation").glob("*/current/"+key+".json")
        pinned=json.loads(observed.read_bytes())
        prep=preparation_root(area/"slices",[area/"modules"],key)
        for side in ("old","new"):
            doc=prep/key/side/"prepared.json"
            info=json.loads(doc.read_bytes())
            jars=[(doc.parent/x["file"]).resolve() for x in info["classpath"]]
            hashes=[SHA(j) for j in jars]
            if hashes!=pinned["sides"][side]["orderedSha256"] or info["commit"]!=pinned["sides"][side]["commit"]:
                raise ValueError("receiver classpath differs from its pilot")
            out=output/key/side
            out.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="receiver-property-") as tmp:
                work=Path(tmp); cp=os.pathsep.join(map(str,jars))
                src=work/"ReceiverControl.java"
                src.write_text("public class ReceiverControl { public static void main(String[] args) throws Exception { "+
                    "if (("+construction+")."+method+"() != null) throw new AssertionError(); } }\n")
                subprocess.run([jdk/"bin/javac","-J-Djava.io.tmpdir="+tmp,"-proc:none","-cp",cp,"-d",work,src],check=True)
                subprocess.run([jdk/"bin/java","-Djava.io.tmpdir="+tmp,"-cp",str(work)+os.pathsep+cp,"ReceiverControl"],check=True)
                evidence={"commit":info["commit"],"orderedClasspathSha256":hashes,"nativeSubjectJdk":runtime_jdk.release(jdk)["JAVA_VERSION"],
                          "originalControlSourceSha256":SHA(src),"publicConstructor":construction,"target":owner+"#"+method,"claims":{}}
                for label,exe,assertion in (("baseline",before,"result == null"),("current",now,"result == null"),
                                             ("negative",now,"result != null")):
                    cmd=[exe,"prove",owner+"#"+method,"--classes",jars[0],"--classpath",os.pathsep.join(map(str,jars[1:])),
                         "--assert",assertion,"--engine","native","--gaps","strict","--unwind","64","--max-array-length","8",
                         "--work",work/label,"--json"]
                    r=subprocess.run(cmd,env=env,capture_output=True,timeout=65)
                    row,=json.loads(r.stdout);receipt=out/(label+".native.json");receipt.write_bytes(r.stdout)
                    if row["assert"]!=assertion or row["target"]!=owner+"#"+method: raise ValueError("wrong receiver property")
                    if row["verdict"]=="verified" and row["stated"]["vacuity"]["status"]!="non-vacuous":
                        raise ValueError("vacuous receiver property")
                    evidence["claims"][label]={"checkerSha256":SHA(exe),"assertion":assertion,"verdict":row["verdict"],
                            "firstOutstanding":row["problem"],"raw":receipt.name,"sha256":SHA(receipt)}
                document(out/"result.json",evidence)
                print(key,side,[r["verdict"] for r in evidence["claims"].values()],flush=True)
                if key=="compsuite-i-70" and [r["verdict"] for r in evidence["claims"].values()]!=["unverifiable","verified","violation"]:
                    raise ValueError("the original style getter or its negative control failed")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--area",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();run(a.area,a.output)

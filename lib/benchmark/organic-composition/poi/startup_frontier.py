"""Record the actual pre-verifier refusal for POI's full system-properties enumeration."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

CASE=Path(__file__).resolve().parent
sys.path.insert(0,str(CASE.parent))
from plan_run import JDK, ROOT, OUTPUT
from freeze import verify

def main():
    verify()
    records={}
    checker=os.environ.get("JVMCONTRACT",str(ROOT/"lib/target/release/jvmcontract"))
    owner="org.apache.poi.ss.usermodel.DataFormatter"
    for side in ("old","new"):
        manifest=json.loads((CASE/side/"prepared.json").read_bytes())
        jars=os.pathsep.join(c["file"] for c in manifest["classpath"])
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([JDK/"bin/javac","-g","-parameters","-encoding","UTF-8","-proc:none","-cp",jars,
                            "-d",tmp,CASE/"UpgradeProbe.java",CASE/"StartupHistory.java"],check=True)
            physical=[]
            for w in json.loads((CASE/"workflows.json").read_bytes())["workflows"]:
                spec=json.loads((CASE/w["scope"]).read_bytes())
                changes={} if w["intent"]=="preserve" else {v["input"]:v["expectedNew"] for v in w["intent"]["allowedChanges"]}
                for i,c in enumerate(spec["cases"]):
                    language,country=c["args"][1].split("-")
                    start=[JDK/"bin/java","-Duser.timezone=UTC","-Duser.language="+language,"-Duser.country="+country,
                           "-cp",tmp+os.pathsep+jars,"StartupHistory",*c["args"]]
                    result=subprocess.run(start,check=True,capture_output=True,text=True,timeout=15)
                    value,=[v.removeprefix("ORIGINAL-VALUE ") for v in result.stdout.splitlines() if v.startswith("ORIGINAL-VALUE ")]
                    expected=changes.get(i,c["expected"]) if side=="new" else c["expected"]
                    if {"return":value}!=expected: raise ValueError("process-locale history differs from registered input")
                    physical.append({"input":c["args"],"actual":value,"argv":list(map(str,start))})
            records[side]={"physical":physical}
            controlled={"emptyEnvironment":True,"processors":2,"rootWorkingDirectory":True}
            for name,target,observe,profile in [("original-observer","UpgradeProbe",True,None),
                                                ("constructor-first","StartupHistory",False,None),
                                                ("constructor-first-observed","StartupHistory",True,None),
                                                ("controlled-process","StartupHistory",True,controlled)]:
                argv=[checker,"prove","--classes",tmp,"--classpath",jars,target+"#currency","--assert","result == true",
                      "--engine","native","--unwind","16","--timeout","90","--json"]
                if observe: argv.extend(["--observed-initializer",owner])
                if profile: argv.extend(["--observed-runtime",json.dumps(profile,separators=(",",":"))])
                p=subprocess.run(argv,env={**os.environ,"JAVA_HOME":str(JDK),"PATH":str(JDK/"bin")+":"+os.environ["PATH"]},
                                 capture_output=True,text=True,timeout=115)
                if p.stdout.strip():
                    verdict=json.loads(p.stdout)[0]["verdict"]
                elif (p.returncode and p.stderr.startswith("jvmcontract: --observed-initializer "+owner+":")
                      and "read the system properties as a whole" in p.stderr):
                    verdict="startup refuses whole system-properties enumeration"
                else:raise ValueError("unexpected startup outcome: "+p.stderr[:500])
                records[side][name]={"argv":argv,"exit":p.returncode,"stdout":p.stdout,"stderr":p.stderr,
                                     "verdict":verdict,"jdk":str(JDK),"classpath":manifest["classpath"]}
    dest=ROOT/OUTPUT/"poi/observed-frontier.json";dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(records,indent=2)+"\n")

if __name__=="__main__": main()

"""Change only the new deployment's actual JDK and compare the resumed and clean POI histories."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

CASE=Path(__file__).resolve().parent
sys.path.insert(0,str(CASE.parent))
from freeze import verify
from matrix import semantic, write
from plan_run import JDK, ROOT, OUTPUT


def main():
    verify()
    newer=Path.home()/".sdkman/candidates/java/25.0.5.0+8-tem"
    target=ROOT/OUTPUT/"poi/jdk-profile"
    target.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="organic-poi-jdk-") as name:
        work=Path(name)
        document=json.loads((CASE/"new/prepared.json").read_bytes())
        document["jdkReleaseSha256"]=hashlib.sha256((newer/"release").read_bytes()).hexdigest()
        write(work/"new25.json",document)
        reports={}
        evidence={}
        for mode in ("baseline","changed-warm","changed-clean"):
            same=mode=="baseline"
            cmd=[sys.executable,ROOT/"examples/tools/build.py","--change-plan","application","--before",CASE/"old/prepared.json",
                 "--after",CASE/"new/prepared.json" if same else work/"new25.json","--jdk",JDK,
                 "--after-jdk",JDK if same else newer,"--workflows",CASE/"checked-workflows.json",
                 "--checker",os.environ.get("JVMCONTRACT",ROOT/"lib/target/release/jvmcontract"),
                 "--seconds","180","--run","--cache",work/("independent" if mode=="changed-clean" else "cache"),
                 "--output",work/(mode+".json")]
            if mode=="changed-warm":
                cmd.extend(["--previous",work/"baseline.json"])
            subprocess.run(cmd,cwd=ROOT,check=True)
            plan=json.loads((work/(mode+".json")).read_bytes())
            reports[mode]=semantic(plan)
            evidence[mode]={"jdk":{s:plan["launches"][s]["production"]["jdk"] for s in ("old","new")},
                            "claims":[{k:n.get(k) for k in ("id","execution","helperProofs","status","firstOpenDependency","receipt")}
                                      for n in plan["claims"]]}
        if reports["changed-warm"]!=reports["changed-clean"]:
            raise ValueError("changed JDK warm outcomes disagree with clean")
        if evidence["baseline"]["jdk"]["new"]==evidence["changed-warm"]["jdk"]["new"]:
            raise ValueError("new JDK image was not changed")
        if any(c.get("execution",{}).get("new",{}).get("action")=="exact reuse" for c in evidence["changed-warm"]["claims"]):
            raise ValueError("public result reused across JDK image change")
        with zipfile.ZipFile(target/"plans.zip","w",zipfile.ZIP_DEFLATED) as z:
            for mode in reports:
                z.write(work/(mode+".json"),mode+".json")
            for p in sorted((work/"receipts").glob("*.json")):
                z.write(p,"receipts/"+p.name)
        write(target/"report.json",evidence)

if __name__=="__main__":
    main()

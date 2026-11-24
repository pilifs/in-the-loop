"""Compare the two actual PRs and the four endpoints, with the upstream depth-150 workload."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from freeze import verify
from plan_run import JDK, ROOT, OUTPUT
sys.path.insert(0,str(ROOT/"examples/tools"))
from targets import runtime_jar, change_helpers


def main():
    verify()
    snapshots={};depths={};frames={}
    for number in ("628","755"):
        case=HERE.parent/("collections-"+number)
        with zipfile.ZipFile(ROOT/OUTPUT/case.name/"first/plans.zip") as z:
            plan=json.loads(z.read("cold.json"))
            for side in ("old","new"):
                label=number+"-"+side
                outcomes={}
                for node in plan["claims"]:
                    if node["status"]!="established":raise ValueError("missing original iterator history")
                    for child in node["children"]:outcomes[child["arguments"][0]]=child[side]
                snapshots[label]=outcomes
                doc=json.loads((case/side/"prepared.json").read_bytes())
                paths=[Path(row["file"]) for row in doc["classpath"]]
                if any(hashlib.sha256(f.read_bytes()).hexdigest()!=rec["sha256"] for f,rec in zip(paths,doc["classpath"],strict=True)):
                    raise ValueError("unexpected runtime JAR")
                data=runtime_jar.read_class(paths[0],"org/apache/commons/collections4/iterators/IteratorChain")
                flags,body,_=runtime_jar._declarations(data,with_code=True)[1]["updateCurrentIterator","()V"]
                try:
                    change_helpers.declaration({"entry":"org.apache.commons.collections4.iterators.IteratorChain#updateCurrentIterator()V","rows":[]},data)
                except ValueError as exc: refusal=str(exc)
                else: raise ValueError("pure primitive route accepted a state-mutating instance method")
                frames[label]={"classSha256":hashlib.sha256(data).hexdigest(),"codeSha256":hashlib.sha256(body).hexdigest(),
                               "accessFlags":flags,"descriptor":"()V","checkedSubstitution":"open","reason":refusal}
                cp=os.pathsep.join(map(str,paths));runs=[]
                with tempfile.TemporaryDirectory(prefix="collections-depth-") as t:
                    subprocess.run([JDK/"bin/javac","-proc:none","-cp",cp,"-d",t,HERE/"Depth.java"],check=True)
                    for _ in range(3):
                        start=time.monotonic()
                        try:
                            p=subprocess.run([JDK/"bin/java","-Xmx128m","-cp",t+os.pathsep+cp,"Depth"],capture_output=True,
                                             text=True,timeout=4)
                        except subprocess.TimeoutExpired:
                            runs.append({"outcome":"censored at four seconds process wall","processSeconds":round(time.monotonic()-start,5)})
                            continue
                        if p.returncode:
                            runs.append({"outcome":"failed workload","stderr":p.stderr[-800:],"exit":p.returncode});continue
                        nanos,values,backing=p.stdout.strip().split("\t")
                        if values!="[One, Two, Three, Four, Five, Six]" or backing!="[]/[Four]/[]":
                            raise ValueError("wrong bounded-depth history")
                        runs.append({"outcome":"all values, removes, exhaustion and backing lists matched",
                                     "timedNanos":int(nanos),"underUpstreamSecond":int(nanos)<1_000_000_000,
                                     "processSeconds":round(time.monotonic()-start,5),"values":values,"backing":backing})
                depths[label]={"depth":150,"upstreamTimedLimitSeconds":1,"freshJvms":runs,"commit":doc["commit"]}
    if snapshots["628-old"]!=snapshots["755-new"] or snapshots["628-new"]!=snapshots["755-old"]:
        raise ValueError("measured long-range state was not restored")
    out=ROOT/OUTPUT/"collections/history.json";out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"publicEndpoints":snapshots,"boundedDepth":depths,"heapSummary":frames,
        "observerSha256":hashlib.sha256((HERE/"UpgradeProbe.java").read_bytes()).hexdigest(),
        "depthSourceSha256":hashlib.sha256((HERE/"Depth.java").read_bytes()).hexdigest()},indent=2)+"\n")

if __name__=="__main__":main()

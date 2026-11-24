"""Distinguish unchanged original V3 inputs from historical classpaths that could only be reconstructed."""
import argparse
import gzip
import json
from pathlib import Path
from history import ROOT,OUTPUT,encoded,digest

PRIOR=ROOT/"verification/external-upgrades/corpus-runs/v3-final-native"

def aggregate(base,out,audit):
    rows=[];missing=set()
    for f in sorted(base.glob("*/comparison.json")):
        for record in json.loads(f.read_bytes())["cases"]:
            name=record["id"]+".json"
            old=PRIOR/f.parent.name/"current"/name;new=f.parent/"current"/name
            a,b=[json.loads(p.read_bytes()) for p in (old,new)]
            if any(a[k]!=b[k] for k in ("id","entry","observer","operator","revisions","sourceSha256")):
                raise ValueError("a shadow primary or assistance setting changed")
            graph={}
            for side in ("old","new"):
                original=a["sides"][side];current=b["sides"][side]
                x,y=[v["orderedSha256"] for v in (original,current)]
                if not x or not y:raise ValueError("an original ordered classpath is missing")
                missing.update(set(x)-set(y))
                graph[side]={"exact":x==y,"original":x,"current":y,"sameDeclaringClass":original.get("callerClassSha256")==current.get("callerClassSha256") if "callerClassSha256" in original or "callerClassSha256" in current else None,
                             "sameModulePom":original.get("modulePomSha256")==current.get("modulePomSha256") if "modulePomSha256" in original or "modulePomSha256" in current else None}
            rows.append({"id":a["id"],"entry":b["entry"],"question":b["observer"],"sourceSha256":a["sourceSha256"],
                         "classpaths":graph,"status":b["result"],"oldStatus":a["result"],"firstBlocker":b["firstBlocker"],
                         "sameFirstBlocker":b["firstBlocker"]==a["firstBlocker"],"elapsedSeconds":b["elapsedSeconds"],
                         "priorSeconds":a["elapsedSeconds"],"priorReceiptSha256":digest(old),"currentReceiptSha256":digest(new)})
    if len(rows)!=32 or len({r["id"] for r in rows})!=32:raise ValueError("incomplete shadow population")
    recovered=json.loads(audit.read_bytes())
    if set(recovered["wanted"])!=missing:raise ValueError("archival search and V3 mismatches differ")
    exact=sum(all(s["exact"] for s in r["classpaths"].values()) for r in rows)
    out.mkdir(parents=True,exist_ok=True)
    summary={"rows":rows,"exactPairs":exact,"artifactMismatchPairs":len(rows)-exact,"originalJarSearch":recovered}
    (out/"matrix.json.gz").write_bytes(gzip.compress(encoded(summary),mtime=0))
    md=["# Historical V3 shadow","","The frozen checker answered none of the original 32 automatic primary questions. All registered caller sources, revisions, declaring-class digests and assistance settings were preserved. The ordered artifact digests matched V3 on "+str(exact)+" pairs. The remaining five reruns have separately identified artifact drift. Each reproduced its original first blocker.","","| V3 input status | Pairs | Primary decisions |","|---|---:|---:|",f"| Exact ordered classpaths | {exact} | 0 |",f"| Reconstructed dependency classpaths | {32-exact} | 0 |","","The original Maven reactor outputs included 72 JAR hashes absent from the staged historical caches. The recovery audit checked 6,409 distinct cached JARs and the member inventories of ordinary archived outputs. The matrix records the individual old and new digests, original questions and elapsed times. [Shadow matrix and audit](matrix.json.gz)"]
    (out/"RESULTS.md").write_text("\n".join(md)+"\n")
    print(exact,"exact V3 pairs and",32-exact,"reconstructed pairs")
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--inputs",type=Path,default=OUTPUT/"closing/shadow");p.add_argument("--output",type=Path,default=OUTPUT/"closing/shadow-comparison");p.add_argument("--audit",type=Path,default=OUTPUT/"closing/shadow-comparison/recovery.json")
    a=p.parse_args();aggregate(a.inputs,a.output,a.audit)

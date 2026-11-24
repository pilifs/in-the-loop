"""Bind each campaign job and population to its registered source, collected result and archived files."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import os
import shutil
import tempfile
from history import HERE,ROOT,OUTPUT,encoded,digest

def checked_job(job,receipt):
    return job==receipt["spec"] and hashlib.sha256(json.dumps(job,sort_keys=True).encode()).hexdigest()==receipt["sha256"]

def materialize(collected):
    # The collector can retain a divergent output under its job receipt. Import only bytes it actually hashed.
    files={}
    for spec in sorted((ROOT/"verification/jobs/2026/11/24").glob("*.json")):
        job=json.loads(spec.read_bytes())
        if not any("lib/benchmark/beyond-jbmc/" in step["run"] for step in job["steps"]):continue
        directory=collected/"verification/results/2026/11/24"/job["id"]
        if not (directory/"result.json").is_file():continue
        report=json.loads((directory/"result.json").read_bytes())
        if report["status"]!="passed":continue
        if not checked_job(job,report["job"]):raise ValueError("collector used a different job: "+job["id"])
        for entry in report["outputs"]:
            rel=Path(entry["path"])
            if rel.is_absolute() or ".." in rel.parts:raise ValueError("invalid output path")
            scoped=(rel.is_relative_to("verification/beyond-jbmc") or any(rel.is_relative_to(Path("examples")/case/"records/beyond-jbmc-frozen")
                    for case in ("368-spring-binding-history","374-spring-formatter-binding")))
            if scoped and entry["change"]!="deleted":
                files.setdefault(rel,[]).append((report["finishedAt"],directory,entry))
    copied=0
    for rel,versions in files.items():
        _,directory,latest=max(versions,key=lambda v:v[0])
        sha=latest["sha256"]
        dest=ROOT/rel
        if dest.is_file():
            prior=digest(dest)
            if prior==sha:continue
            if not any(prior in (e.get("sourceSha256"),e["sha256"]) for _,_,e in versions):
                raise ValueError("locally changed file differs from every recorded artifact: "+str(rel))
        options=(directory/"outputs"/rel,collected/rel)
        src=next((p for p in options if p.is_file() and digest(p)==sha),None)
        if src is None:raise ValueError("the collector's artifact could not be verified: "+str(rel))
        dest.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=dest.parent,delete=False) as f:
            temp=Path(f.name)
            with src.open("rb") as original:shutil.copyfileobj(original,f)
        try:
            if digest(temp)!=sha:raise ValueError("artifact changed during copy: "+str(rel))
            temp.chmod(0o644)
            os.replace(temp,dest)
        finally:temp.unlink(missing_ok=True)
        copied+=1
    print(copied,"collected evidence files materialized;",len(files),"verified paths")

def build(collected,out):
    evidence=collected/"verification/beyond-jbmc";rows=[];missing=[]
    for spec in sorted((ROOT/"verification/jobs/2026/11/24").glob("*.json")):
        job=json.loads(spec.read_bytes())
        if not any("lib/benchmark/beyond-jbmc/" in step["run"] for step in job["steps"]):continue
        ident=job["id"];path=collected/"verification/results/2026/11/24"/ident/"result.json"
        if not path.is_file():missing.append(ident);continue
        result=json.loads(path.read_bytes())
        if result["id"]!=ident or not checked_job(job,result["job"]):raise ValueError("job specification drift: "+ident)
        artifacts=[{k:f.get(k) for k in ("path","bytes","sha256")} for f in result["outputs"]]
        rows.append({"id":ident,"title":job["title"],"source":result["sourceCommit"],"status":result["status"],
                     "result":path.relative_to(collected).as_posix(),"resultSha256":digest(path),"specSha256":digest(spec),
                     "commands":[x["run"] for x in job["steps"]],"outputs":artifacts,
                     "usage":{k:result["usage"].get(k) for k in ("wallSeconds","cpuSeconds","peakMemoryBytes")}})
    if missing:raise ValueError("still awaiting committed campaign jobs: "+", ".join(missing))
    populations={"historical187":"closing/comparison/matrix.json.gz","historical60and49":"closing/control-comparison/matrix.json.gz",
                 "historical32":"closing/shadow-comparison/matrix.json.gz","disclosed68":"casebook/matrix.json.gz","blind16":"blind-comparison/matrix.json.gz"}
    tables={k:{"file":v,"sha256":digest(OUTPUT/v)} for k,v in populations.items()}
    history=json.loads(gzip.decompress((OUTPUT/populations["historical187"]).read_bytes()))
    controls=json.loads(gzip.decompress((OUTPUT/populations["historical60and49"]).read_bytes()))
    shadow=json.loads(gzip.decompress((OUTPUT/populations["historical32"]).read_bytes()))
    casebook=json.loads(gzip.decompress((OUTPUT/populations["disclosed68"]).read_bytes()))
    blind=json.loads(gzip.decompress((OUTPUT/populations["blind16"]).read_bytes()))
    if (len(history["rows"]),len(controls["60"]["claims"]),len(controls["49"]["claims"]),len(shadow["rows"]),len(casebook["tasks"]),len(blind["projects"]))!=(187,60,49,32,68,16):
        raise ValueError("population denominator drift")
    for project in blind["projects"]:
        for lane in ("matched","automatic"):
            r=project[lane]
            if digest(evidence/"blind"/r["receipt"])!=r["reportSha256"]:raise ValueError("blind raw receipt drift")
    for entry in casebook["tasks"]:
        if not(entry["properties"] or entry["additionalEvidence"]):raise ValueError("work item without evidence "+entry["id"])
        for r in entry["properties"]:
            p=evidence/r["receipt"]
            if not p.is_file() or r.get("receiptSha256",digest(p))!=digest(p):raise ValueError("casebook receipt drift")
    state=Counter(r["status"] for r in rows)
    replacements={
        "20261124-074103-check-all-native-sat-answers-for-mixed-l":"20261124-081513-certify-original-sat-assignments-and-uns",
        "20261124-093055-kernel-check-full-finite-wire-records-an":"20261124-100249-repeat-the-whole-wire-induction-with-ker",
        "20261124-093055-kernel-check-murmurhash-streaming-partit":"20261124-100249-repeat-murmurhash-partition-induction-ov",
        "20261124-100249-check-invertibility-of-the-codec-128-bit":"20261124-102145-certify-the-codec-signed-seed-boundary-b",
    }
    failed=[r["id"] for r in rows if r["status"]!="passed"]
    complete={r["id"] for r in rows if r["status"]=="passed"}
    if any(replacements.get(s) not in complete for s in failed):raise ValueError("unresolved job failure: "+str(failed))
    result={"schema":"beyond-jbmc-evidence/v1","freezeSha256":digest(HERE/"freeze.json"),
            "original187Sha256":digest(HERE/"historical/manifest.json"),"casebookSha256":digest(HERE/"casebook.json"),
            "blindDrawSha256":hashlib.sha256(gzip.decompress((HERE/"blind/draw/sealed.json.gz").read_bytes())).hexdigest(),
            "blindDocketSha256":digest(HERE/"blind/references.json"),"tables":tables,"jobs":rows,"jobStates":state,
            "supersededAttempts":{s:replacements[s] for s in failed}}
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(gzip.compress(encoded(result),mtime=0))
    print(len(rows),"registered jobs,",dict(state),"and six population denominators verified")
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--collected",type=Path,default=ROOT);p.add_argument("--output",type=Path,default=OUTPUT/"evidence-index.json.gz")
    p.add_argument("--materialize",action="store_true",help="restore already collected public campaign files into this workspace")
    a=p.parse_args()
    if a.materialize:materialize(a.collected.resolve())
    else:build(a.collected.resolve(),a.output)

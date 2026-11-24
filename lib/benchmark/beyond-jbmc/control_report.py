"""Publish the matched native/integrated control counts and the original source-bound dispositions."""
import argparse
from collections import Counter,defaultdict
import gzip
import json
from pathlib import Path
import zipfile
from history import OUTPUT,digest,encoded
from scores import partition,median

def read(path):
    return json.loads(gzip.decompress(path.read_bytes()))

def raw_control_profiles(archive,first,n):
    index=read(archive)
    bundle=archive.parent/"executions.zip"
    if index["archiveSha256"]!=digest(bundle):raise ValueError("raw control archive differs")
    repeat={(r["family"],r["method"],r["engine"]):r["current"] for r in index["originalProfiles"]}
    changed=[]
    for r in first:
        other=repeat.pop((r["family"],r["method"],r["engine"]))
        if any(other[k]!=r["current"][k] for k in ("verdict","disposition")):
            changed.append({"family":r["family"],"method":r["method"],"engine":r["engine"],"repeat":other})
    if repeat:raise ValueError("raw repeat contains a different claim")
    named=Counter();reach=Counter();rows=[];profiles=set()
    with zipfile.ZipFile(bundle) as z:
        for name in z.namelist():
            if not (name.endswith("/installed-packaged/measurement.json") or name.endswith("/packaged/measurement.json")):continue
            d=json.loads(z.read(name));profiles.add((d["binarySha256"],d["coreModelsSha256"]) if "binarySha256" in d else (d["jbmcSha256"],d["coreModelsSha256"]))
            for row in d.get("runs") or d.get("rows",[]):
                r=row.get("packaged",row)
                target,control=r["target"],r["reached"]
                named[target["status"]]+=1;reach[control["status"]]+=1
                rows.append({"report":name,"method":row.get("method") or row["task"],"target":target["status"],
                             "reach":control["status"],"otherFailedTargetProperties":target.get("otherFailures"),
                             "seconds":target.get("seconds"),"replay":row.get("jvmReplay") or target.get("jvmReplay")})
    if len(rows)!=n:raise ValueError("missing packaged stock controls")
    return {"archiveSha256":index["archiveSha256"],"files":len(index["files"]),"familyStatus":index["additionalPackagedProfiles"],
        "originalProfileChangesOnRepeat":changed,"standaloneProfiles":sorted(profiles),"stockTargetCounts":named,"stockReachedCounts":reach,"packagedRows":rows}

def build(root,out):
    summaries={}
    for n in (60,49):
        path=root/"regressions"/(str(n)+".json.gz");data=read(path);pairs=defaultdict(dict)
        for row in data["rows"]:pairs[row["family"],row["method"]][row["engine"]]=row
        if len(pairs)!=n:raise ValueError("original control denominator differs")
        final={};change=[];counter=Counter();solved=[]
        outcomes={"native":Counter(),"jbmc":Counter()}
        for key,c in pairs.items():
            if set(c)!={"native","jbmc"}:raise ValueError("incomplete original comparator pair")
            for eng,row in c.items():
                now=row["current"];status=now["disposition"];verdict=now["verdict"]
                decision=("proved" if verdict=="verified" else "refuted") if status=="correct" else status
                if decision=="refuted" and now.get("jvmReplay",{}).get("outcome")!="refuted":decision="unconfirmed witness"
                outcomes[eng][decision]+=1
                if (status,verdict)!=(row["prior"],row["priorVerdict"]):change.append([*key,eng,row["prior"],status])
                final.setdefault("/".join(key),{})[eng]={"disposition":decision,"current":now}
            a,b=[c[e]["current"] for e in ("native","jbmc")]
            state=partition(a["disposition"]=="correct",b["disposition"]=="correct");counter[state]+=1
            if state=="both":solved.append((a["seconds"],b["seconds"]))
        archive=root/"control-evidence"/str(n)/"index.json.gz"
        summaries[str(n)]={"population":n,"checkerSha256":data["checkerSha256"],"inputReportSha256":digest(path),
            "paired":counter,"dispositions":outcomes,"changedHistoricalRows":change,"claims":final,
            "jointlySolvedMedianWallSeconds":[median([p[i] for p in solved]) for i in (0,1)],
            "supplementalRawIndexSha256":digest(archive) if archive.is_file() else None,
            "rawControls":raw_control_profiles(archive,data["rows"],n) if archive.is_file() else None}
    out.mkdir(parents=True,exist_ok=True)
    (out/"matrix.json.gz").write_bytes(gzip.compress(encoded(summaries),mtime=0))
    md=["# Existing Java controls","","Both historical control populations were measured on the same frozen executable and their original two checker profiles. [Full statements, bounds, witnesses and dispositions](matrix.json.gz)","","| Population | Both | Native only | Integrated only | Neither | Native proofs / JVM refutations | Integrated proofs / JVM refutations |","|---|---:|---:|---:|---:|---|---|"]
    for num,s in summaries.items():
        c=s["paired"];stats=s["dispositions"]
        md.append(f"| {num} | "+" | ".join(str(c[k]) for k in ("both","native-only","comparator-only","neither"))+" | "+" | ".join(f"{stats[e]['proved']} / {stats[e]['refuted']}" for e in ("native","jbmc"))+" |")
    md+=["","The three ordinary monitor/thread claims are still deferred. The two integrated false-success rows on the 60-claim panel retain their original disposition. The original drivers report per-claim wall time, with full-process resource use in the job receipts. Additional packaged-stock runs retain their own harnesses and object-factory domains."]
    if all(s["rawControls"] for s in summaries.values()):
        md+=["","| Packaged stock target status | 60 claims | 49 claims |","|---|---:|---:|"]
        for state in sorted(set.union(*(set(s["rawControls"]["stockTargetCounts"]) for s in summaries.values()))):
            md.append(f"| {state} | "+" | ".join(str(s["rawControls"]["stockTargetCounts"].get(state,0)) for s in summaries.values())+" |")
        md+=["","These are literal named assertion statuses. The attached tables also retain each stock reach outcome, additional failing properties and the exact solver/model pair. Each 60-claim packaged reach wrapper catches exceptions before its false assertion. A failure there alone does not establish normal return. [Full 60-claim raw archive](../control-evidence/60/executions.zip) · [Full 49-claim raw archive](../control-evidence/49/executions.zip)"]
    (out/"RESULTS.md").write_text("\n".join(md)+"\n")
    print({k:dict(v["paired"]) for k,v in summaries.items()})
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--inputs",type=Path,default=OUTPUT/"closing");p.add_argument("--output",type=Path,default=OUTPUT/"closing/control-comparison")
    a=p.parse_args();build(a.inputs,a.output)

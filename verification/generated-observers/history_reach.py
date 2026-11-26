"""Check changed bodies seen later in the same public history against the original registered caller."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

import campaign
from targets import entry_discovery, runtime_jar

HERE=campaign.HERE


def changed_sort_methods(work):
    """Inventory actual differences in the sort field's production package, independently of the observed hits."""
    docs=[campaign.read(work/"bundle"/(s+".json")) for s in ("old","new")]
    jars=[Path(d["classpath"][0]["file"]) for d in docs]
    selected=set()
    with zipfile.ZipFile(jars[0]) as old, zipfile.ZipFile(jars[1]) as new:
        for name in sorted(set(old.namelist()) | set(new.namelist())):
            if not name.startswith("org/apache/lucene/search/join/") or not name.endswith(".class"):
                continue
            pair=[z.read(name) if name in z.namelist() else None for z in (old,new)]
            if pair[0]==pair[1]: continue
            fps=[entry_discovery.fingerprints(entry_discovery.Definition(name,"",0,data)) if data else {} for data in pair]
            for method,desc in fps[0].keys() | fps[1].keys():
                if method in {"getComparator","getSortedDocValues","advanceExact","hasChildWithMissingValue","ordValue","wrap"} and fps[0].get((method,desc))!=fps[1].get((method,desc)):
                    selected.add(name[:-6].replace("/",".")+"#"+method+desc)
    return sorted(selected)


def measure(number,which,archive,work):
    work.mkdir()
    with zipfile.ZipFile(archive) as z:
        for member in z.namelist():
            if member.startswith("bundle/"):z.extract(member,work)
    bundle=work/"bundle"
    reg=campaign.read(bundle/"registration.json")
    workflows=campaign.read(bundle/"workflows.json")
    workflows["workflows"]=[next(q for q in workflows["workflows"] if q["id"]==which)]
    campaign.write(bundle/"focused.json",workflows)
    selectors=changed_sort_methods(work) if number=="J14" else reg["changed"]
    jdk=campaign.prepare(number,work)
    args=[sys.executable,campaign.ROOT/"examples/tools/build.py","--change-plan","application","--before",bundle/"old.json",
          "--after",bundle/"new.json","--jdk",jdk,"--workflows",bundle/"focused.json","--supplied-only",
          "--run","--seconds","150","--output",work/"replay.json"]
    for selector in selectors: args+=["--changed-selector",selector]
    campaign.run(args)
    node,=campaign.read(work/"replay.json")["claims"]
    expected={"io":"established","J14":"refuted","466":"open"}[number]
    if node["status"]!=expected:raise ValueError("original adjudication differs on the unchanged public history")
    evidence=campaign.read(work/node["receipt"]["path"])
    sides={}
    for side,d in evidence["sides"].items():
        histories=[]
        for t in d["trials"]:
            reps=t["changedWithinHistory"]
            if len(reps)!=2 or reps[0]!=reps[1]:
                raise ValueError("changed-body observations did not repeat")
            for hit in reps[0]:
                if hit["artifactSha256"]!=d["classpath"][hit["providerIndex"]] or hit["stack"][0] not in selectors:
                    raise ValueError("unbound changed-body event")
            histories.append({"input":t["input"], "withinPublicHistory":reps[0],"underSelectedEntry":t["changedBodyChains"][0]})
        sides[side]=histories
    if number in {"io","J14"} and not all(any(t["withinPublicHistory"] for t in v) for v in sides.values()):
        raise ValueError("missing marked stream reset or changed sort readback on an original release")
    return {"question":which,"originalArchiveSha256":campaign.upgrade_replay.sha(archive),"sourceSha256":evidence["probeSha256"],
            "selectors":selectors,"status":node["status"],"receipt":node["receipt"],"sides":sides}


if __name__=="__main__":
    with tempfile.TemporaryDirectory(prefix="registered-history-reach-") as tmp:
        root=Path(tmp)
        rows={}
        for n,q,suffix in [("io","rewinds",""),("J14","filtered-child-hypothesis","-clean"),
                            ("466","spring-projects/spring-framework#37193.1","-clean")]:
            rows[n]=measure(n,q,HERE/"receipts"/(n+suffix+".zip"),root/n)
        campaign.write(root/"reach.json",rows)
        campaign.pack(root,[root/"reach.json",*(p for n in rows for p in (root/n/"receipts").glob("*.json")),
                           *(root/n/"replay.json" for n in rows)],HERE/"receipts/history-reach.zip")

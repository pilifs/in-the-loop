"""Open the committed draw and bind independent references before any held-out checker report is inspected."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time
import urllib.request
import urllib.parse

from packets import AREA, BASE, HERE, PORTABLE, unseal, sha, encoded, fetch
from freeze_product import verify
from seal_panel import POOL

REFS=HERE/"references"
DOCKET=HERE/"references.json"


def committed(rev):
    target,_=verify()
    here=HERE.parents[3]
    binding="lib/benchmark/beyond-jbmc/freeze.json"
    if subprocess.check_output(["git","show",rev+":"+binding],cwd=here)!=(here/binding).read_bytes():
        raise ValueError("recorded freeze differs from the committed bytes")
    return unseal()


def reveal(rev):
    draw=committed(rev)
    PORTABLE.mkdir(exist_ok=True)
    for name in ("population","screening","sealed"):
        data=(AREA/(name+".json")).read_bytes()
        (PORTABLE/(name+".json.gz")).write_bytes(gzip.compress(data,mtime=0))
    write={"freezeCommit":rev,"drawSha256":sha((AREA/"sealed.json").read_bytes()),"pairs":[]}
    for i,r in enumerate(draw["pairs"],1):
        write["pairs"].append({k:r[k] for k in ("artifact","versions","project","source","stratum","suites","adjacentNumeric")}|{
            "slot":f"{i:02}","documented":r["eligibility"]["changeNotes"],"old":r["eligibility"]["oldSha256"],"new":r["eligibility"]["newSha256"]})
    (PORTABLE/"roster.json").write_bytes(encoded(write))


def fetch_origin(path, relative, size, expected):
    if size<=32*1024*1024:
        fetch(AREA,relative,path,expected)
        return
    def checked(file):
        with file.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()==expected
    if path.exists():
        if path.stat().st_size!=size or not checked(path):raise ValueError("large source archive binding differs")
        return
    timer=AREA/"last-request"
    last=float(timer.read_text()) if timer.exists() else 0.0
    time.sleep(max(0,1.1-(time.time()-last)))
    timer.write_text(str(time.time()))
    if not relative.startswith("pool/") or ".." in relative.split("/"):raise ValueError("invalid signed source archive path")
    with tempfile.NamedTemporaryFile(dir=AREA,delete=False) as f:
        temp=Path(f.name)
        try:
            with urllib.request.urlopen(urllib.parse.urljoin(POOL,relative),timeout=75) as r:
                count=0
                while buf:=r.read(1024*1024):
                    count+=len(buf)
                    if count>size:raise ValueError("source archive exceeded its signed length")
                    f.write(buf)
            f.flush()
            if count!=size or not checked(temp):raise ValueError("source archive binding differs")
            os.replace(temp,path)
        finally:
            temp.unlink(missing_ok=True)


def origins(indices):
    draw=unseal()
    for i in indices:
        row=draw["pairs"][i-1];folder=BASE/f"{i:02}";folder.mkdir(parents=True,exist_ok=True)
        result={}
        for kind in ("before","after"):
            source=row[kind]["sourceEntry"]
            tarballs=[f for f in source["files"] if ".orig." in f[2] and ".tar." in f[2]]
            if not tarballs: raise ValueError("no source archive for "+str(i))
            # The main orig archive contains the upstream source. Supplemental orig components retain their own bindings.
            items=[]
            for digest,size,name in tarballs:
                item={"sha256":digest,"size":int(size),"archive":name,"published":source["directory"]+"/"+name}
                path=AREA/(digest+".orig")
                try:
                    fetch_origin(path,item["published"],int(size),digest)
                except Exception as e:
                    item["sourceStatus"]=str(e);items.append(item);continue
                index=[]
                with tarfile.open(path,mode="r|*") as tar:
                    for m in tar:
                        if m.isfile() and m.size<=2*1024*1024:
                            index.append(m.name)
                item["fileIndex"]=sorted(index)
                items.append(item)
            result[kind]=items
        (folder/"source-index.json.gz").write_bytes(gzip.compress(encoded(result),mtime=0))
        print(f"{i:02}",*[sum(len(x.get("fileIndex",[])) for x in result[k]) for k in ("before","after")],flush=True)


def read_member(slot,side,name):
    data=json.loads(gzip.decompress((BASE/slot/"source-index.json.gz").read_bytes()))
    matched=[s for s in data[side] if name in s.get("fileIndex",[])]
    if len(matched)!=1:raise ValueError("source evidence must identify exactly one upstream member")
    src=matched[0]
    with tarfile.open(AREA/(src["sha256"]+".orig"),"r:*") as tar:
        value=tar.extractfile(name).read()
    return {"sourceArchive":src["published"],"archiveSha256":src["sha256"],"member":name,
            "sha256":sha(value)},value


def docket():
    if DOCKET.exists():raise ValueError("reference docket is already closed")
    freeze,lock=verify();doc=unseal()
    rows=[]
    for i,r in enumerate(doc["pairs"],1):
        slot=f"{i:02}"
        folder=REFS/slot
        spec=json.loads((folder/"reference.json").read_bytes())
        if not all(spec.get(k) for k in ("question","control","domain","entries","basis","expected","seeds")):
            raise ValueError("missing reference field "+slot)
        evidence=[]
        for b in spec["basis"]:
            source,value=read_member(slot,b["side"],b["member"])
            if b["text"].encode() not in value:raise ValueError("upstream evidence does not contain the registered excerpt "+slot)
            evidence.append({**source,"side":b["side"],"text":b["text"]})
        packet=BASE/slot/"packet/inputs.json"
        bindings={p.name:sha(p.read_bytes()) for p in folder.glob("*.java")}
        if set(bindings)!={"ReferenceAPI.java","ReferencePair.java"}:raise ValueError("missing paired caller "+slot)
        jvm=folder/"original-jvm.json"
        physical=json.loads(jvm.read_bytes())
        if physical["packetSha256"]!=sha(packet.read_bytes()) or bindings!=physical["sourceSha256"]:
            raise ValueError("reference JVM observations were made against different inputs: "+slot)
        rows.append({"slot":slot,"artifact":r["artifact"],"stratum":r["stratum"],"reference":spec,
                     "evidence":evidence,"sources":bindings,"packetSha256":sha(packet.read_bytes()),
                     "graphSha256":sha((BASE/slot/"graphs.json").read_bytes()),
                     "physicalSha256":sha(jvm.read_bytes()),"physicalStatus":physical["status"],
                     "referenceSha256":sha((folder/"reference.json").read_bytes())})
    result={"schema":"beyond-jbmc-independent-questions/v1","freezeSha256":sha((HERE.parent/"freeze.json").read_bytes()),
            "sealedSha256":sha((AREA/"sealed.json").read_bytes()),"pairs":rows}
    with DOCKET.open("xb") as f:f.write(encoded(result))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest="action",required=True)
    r=sub.add_parser("reveal");r.add_argument("freeze_commit")
    r=sub.add_parser("sources");r.add_argument("indices",nargs="*",type=int,choices=range(1,17))
    sub.add_parser("lock")
    a=p.parse_args()
    if a.action=="reveal":reveal(a.freeze_commit)
    elif a.action=="sources":origins(a.indices or range(1,17))
    else:docket()

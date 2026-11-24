"""Reproduce the first operator's false identity witness on every input of its generated Boolean caller."""
import gzip,json,os
from pathlib import Path
from evaluate_panel import PUBLIC,bindings,matched_namespace,scratch,encoded,digest

def main():
    checker,lock,ref,packet=bindings("03")
    first=packet.parent/("automatic-"+lock["checkerSha256"])/"report.json.gz"
    r=json.loads(gzip.decompress(first.read_bytes()))
    row,=[a for a in r["runs"] if a["candidate"]["id"]=="org.codehaus.plexus.component.repository.ComponentDescriptor#setIsolatedRealm(Z)V"]
    if row["verdict"]!="violation" or row["originalReplayChanged"] is not False:raise ValueError("first finding differs")
    original={}
    for i,label in enumerate(("old","new")):
        observations={}
        for pair in row["physical"]:
            item=pair[i]
            if not item["namedEntryReached"]:raise ValueError("original public entry missing")
            args,val,*_=item["fields"]
            text=bytes.fromhex(val.removeprefix("return u")).decode("utf-16-be")
            if args in observations and observations[args]!=text:raise ValueError("nondeterministic original result")
            observations[args]=text
        original[label]=[observations[k] for k in ("[false]","[true]")]
    out=PUBLIC/"03/identity-diagnostic";out.mkdir(exist_ok=True,parents=True)
    with scratch(prefix="class-name-diagnostic-") as tmp:
        folder=Path(tmp);(folder/"PublicCaller.java").write_text(row["source"])
        (folder/"witness.json").write_bytes(encoded({"firstReportSha256":digest(first),"original":original,
            "callerSha256":row["callerSha256"],"alleged":row["counterexample"],"job":os.environ.get("VERIFY_JOB_ID")}))
        rc=matched_namespace(packet,folder,out,checker,False,"identity_worker.py")
        if rc or not (out/"report.json").is_file():raise ValueError("isolated assisted replay failed")
if __name__=="__main__":main()

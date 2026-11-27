"""Recheck conditional Avro obligations, keeping a different startup order or subset separate."""
import json
import os
from pathlib import Path
import subprocess

from charset import CHECKER, JDK, ROOT, ENV
from transfers import compile_java, digest, foundation


def avro(work):
    folder=next((ROOT/"examples").glob("355-*"))
    spec=json.loads((folder/"target.json").read_bytes())
    rows=[]
    artifacts={}
    variants=[]
    for side in ("parent","fix"):
        area=work/side;area.mkdir()
        jars,provenance=foundation.materialize(folder,side,area)
        assert len(jars)==124
        artifacts[side]=provenance
        classes=work/(side+"-adapter")
        compile_java(JDK,classes,[folder/"adapter/organic/WritableBuffer.java"],jars)
        selected=[t for t in spec["tasks"] if t["id"].endswith("-lookup-startup") and ("-"+side+"-") in t["id"]]
        if side=="fix":selected+=[t for t in spec["tasks"] if t["id"]=="direct-limit-fix-writable-startup"]
        def attempt(t,label,roots,profile,claim):
            run=work/(side+"-"+label);run.mkdir()
            cmd=[CHECKER,"prove",claim["adapter"]["entry"],"--classes",str(classes),"--classpath",os.pathsep.join(map(str,jars)),
                 "--engine","native","--gaps","strict","--assume",claim["assume"],"--assert",claim["assert"],
                 "--unwind",str(claim["bounds"]["unwind"]),"--max-array-length",str(claim["bounds"]["maxArrayLength"]),
                 "--observed-runtime",json.dumps({**profile,"recordJointStartup":True,"startupRevision":provenance["revision"]}),"--work",run,"--json"]
            for root in roots:cmd.extend(["--observed-initializer",root])
            proc=subprocess.run(cmd,env=ENV,capture_output=True,text=True,timeout=450)
            obj=json.loads(proc.stdout)[0] if proc.stdout.strip() else {}
            records=[json.loads(p.read_bytes()) for p in (run/"startup-receipts").glob("*.json")]
            assert len(records)<=1
            rec=records[0] if records else None
            if rec:
                assert rec["requestedRoots"]==roots and rec["startupJvms"]==1
            return {"task":t["id"],"revision":provenance["revision"],"side":side,"requestedRoots":roots,
                    "verdict":obj.get("verdict","refused"),"remaining":obj.get("problem") if obj else proc.stderr.strip(),
                    "scope":"conditional on the registered startup and bounds","consumed":[a["id"] for a in (obj.get("stated") or {}).get("assumptions",[]) if a.get("id")],
                    "record":({k:rec[k] for k in ["id","stateSha256","classes","objects","startupJvms","observationBytes","rawSha256","actualApplicationOrder","effectCoverage"]} if rec else None),
                    "verdictReused":False,"captureReused":False}
        for t in selected:
            claim=json.loads((folder/t["claim"]).read_bytes())
            order=list(claim["observedInitializers"])
            receipt=sorted((folder/"receipts"/t["id"]).glob("*/result.json"))[-1]
            historical=json.loads(receipt.read_bytes())["conclusion"]["status"]
            row=attempt(t,t["id"],order,claim["observedRuntime"],claim)
            row.update(historical=historical,historicalReceiptSha256=digest(receipt),
                       sameRegisteredState=row["record"] is not None and row["record"]["stateSha256"] in claim["observedInitializers"].values())
            rows.append(row)
            print(t["id"],row["verdict"],str(row.get("remaining"))[:175],flush=True)
        if side=="fix":
            t=next(t for t in selected if t["id"].startswith("bounds-"))
            claim=json.loads((folder/t["claim"]).read_bytes());roots=list(claim["observedInitializers"])
            for label,order in [("repeat",roots),("reorder",[roots[1],roots[0],*roots[2:]]),("withhold",roots[:-1])]:
                row=attempt(t,label,order,claim["observedRuntime"],claim)
                row["variation"]=label
                row["matchesRegisteredState"]=bool(row["record"] and row["record"]["stateSha256"] in claim["observedInitializers"].values())
                variants.append(row)
    return {"rows":rows,"variations":variants,"orderedDeployments":artifacts,
            "historicalConditionalObligations":sum(r["historical"]=="established" for r in rows),
            "unrestrictedDecision":"open; these ordered original snapshots leave unrepresented external state and aliases as assumptions"}

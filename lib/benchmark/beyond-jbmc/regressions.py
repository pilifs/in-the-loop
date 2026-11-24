"""Repeat the disclosed 60 and 49 without removing the deferred or lost original rows."""
import argparse
from collections import Counter
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys

from history import ROOT, OUTPUT, HERE, scratch, digest, encoded
from campaign import CLAIMS, measure
from freeze_product import verify


def read(p):return json.loads(p.read_bytes())


def core60(work):
    baseline=ROOT/"verification/java-semantics-gap/decimal-transfer/callers"
    rows=[]
    for name in CLAIMS:
        now=measure(name,"callers",["native","jbmc"],work)
        prior=read(baseline/name/"measurement.json")
        for key in ("classes","classpath","claimsSha256","adapterSha256","jvmSha256","modulesSha256","originalJvm"):
            if now[key]!=prior[key]:raise ValueError("60-claim input drift: "+name+"/"+key)
        old={(r["method"],r["engine"]):r for r in prior["runs"]}
        for r in now["runs"]:
            p=old.pop((r["method"],r["engine"]))
            rows.append({"family":name,"method":r["method"],"engine":r["engine"],"prior":p["disposition"],
                         "priorVerdict":p["verdict"],"current":r})
        if old:raise ValueError("lost required rows in "+name)
    return rows


def follow49(work):
    rows=[]
    driver=HERE.parent/"jbmc-fast-follow/measure.py"
    for name in ("callbacks","numeric","rows","strings","queue"):
        subprocess.run([sys.executable,"-B",driver,"successor",name,"paired","--output",work],check=True)
        now=read(work/"successor"/name/"paired/measurement.json")
        earlier=read(ROOT/"verification/jbmc-fast-follow/successor"/name/"paired/measurement.json")
        old={r["task"]:r for r in earlier["rows"]}
        for r in now["rows"]:
            p=old.pop(r["task"])
            for key in ("descriptor","specSha256","bounds","target"):
                if r[key]!=p[key]:raise ValueError("49-claim input drift: "+name+"/"+r["task"])
            for engine in ("native","jbmc"):
                rows.append({"family":name,"method":r["task"],"engine":engine,"prior":p[engine]["disposition"],
                             "priorVerdict":p[engine]["verdict"],"current":r[engine]})
        if old:raise ValueError("lost public follow-up rows")
    return rows


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("population",choices=("60","49"))
    args=parser.parse_args()
    checker,lock=verify()
    os.environ["JVMCONTRACT"]=str(checker)
    with scratch(prefix="beyond-regressions-") as tmp:
        rows=(core60 if args.population=="60" else follow49)(Path(tmp))
    if len(rows)!=2*int(args.population):raise ValueError("wrong historical control denominator")
    data={"population":args.population,"checkerSha256":digest(checker),"job":os.environ.get("VERIFY_JOB_ID"),"rows":rows}
    out=OUTPUT/"closing/regressions";out.mkdir(parents=True,exist_ok=True)
    (out/(args.population+".json.gz")).write_bytes(gzip.compress(encoded(data),mtime=0))
    print(args.population,Counter((r["engine"],r["current"]["disposition"]) for r in rows),flush=True)

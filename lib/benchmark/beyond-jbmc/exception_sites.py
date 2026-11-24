"""Separate propagating Java exceptions, stock null-check IDs and selected original bytecode sites."""
import argparse
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from history import ROOT,HERE,OUTPUT,JBMC,MODELS,encoded,digest,benchmark,scratch
from release_cases import compile_java,javaenv,JDK
from stock_history import classpath,stock_run
sys.path.insert(0,str(HERE.parent/"receiver-discovery"))
from investigate import inventory,compiler,investigate


def run(physical_only):
    target=OUTPUT/"qualified/E-sites"
    env=javaenv(); checker=Path(os.environ["JVMCONTRACT"]).resolve()
    with scratch(prefix="throw-occurrences-") as tmp:
        work=Path(tmp);src=HERE/"extended";cp=work/"classes"
        compile_java([src/"ThrowSites.java",src/"ExceptionAssertions.java"],cp,[],env)
        jcmd=[JDK/"bin/java","-XX:-OmitStackTraceInFastThrow","-ea","-cp",cp,"ThrowSites"]
        physical=subprocess.check_output(jcmd,text=True,env=env).splitlines()
        if len(physical)!=15:raise ValueError("missing original exception-site runs")
        # Check each variant at every mode. Keep the original line and thrown identity in the raw table.
        for line in physical:
            mode,variant=map(int,line.split()[:2])
            if mode==2:
                if not line.endswith("return 1"):raise ValueError(line)
                continue
            expected="ThrowSites$Reader.read" if mode==1 or variant==1 else "ThrowSites.original" if variant==0 else "ThrowSites.helper"
            outer="ThrowSites.inner" if variant==4 else expected
            if "java.lang.NullPointerException "+outer+"(" not in line:raise ValueError(line)
            if variant>=3 and ("caught "+expected+"(" not in line or line.endswith("same true")!=(variant==3)):raise ValueError(line)
        entries={"original":("original","ThrowSites$Reader#read"),"repaired":("repaired","ThrowSites$Reader#read"),
                 "withHelper":("withHelper","helper","ThrowSites$Reader#read")}
        if physical_only:
            inventories={k:inventory(checker,[cp],k) for k in ("ThrowSites#original","ThrowSites#repaired","ThrowSites#helper","ThrowSites$Reader#read")}
            print(len(physical),"original physical observations;",sum(s["kind"]=="null" for v in inventories.values() for s in v["sites"]),"null sites")
            return
        target.mkdir(parents=True,exist_ok=True)
        tools=compiler(work); result={}
        for entry,targets in entries.items():
            for member in targets:
                subject=member if "#" in member else "ThrowSites#"+member
                inv=inventory(checker,[cp],subject)
                for site in inv["sites"]:
                    if site["kind"]!="null": continue
                    op=site["opcode"]
                    if op not in ("invokevirtual","arraylength",182,190):continue
                    for policy in ("occurrence","escape"):
                        key=f"{entry}-{member}-{site['pc']}-{policy}"
                        row={"entry":entry,"subject":subject,"classSha256":inv["binding"]["sha256"],"site":site,"policy":policy}
                        if site["selection"]=="supported":
                            local=work/key;local.mkdir()
                            r=investigate(checker,[cp],"ThrowSites#"+entry,subject,row["classSha256"],site["pc"],"null",policy,
                                          "arg0 >= 0 && arg0 <= 2",12,3,120,target/key,local,tools)
                            row["disposition"]=r["disposition"]
                        else:row["disposition"]=site["selection"]
                        result[key]=row
        with zipfile.ZipFile(target/"stock.zip","w",zipfile.ZIP_DEFLATED) as z:
            stock={}
            for m in ("original","repaired","helper"):
                cmd=[str(JBMC),"ExceptionAssertions","--function","ExceptionAssertions."+m,"--classpath",classpath([cp,MODELS]),
                     "--unwind","16","--unwinding-assertions","--trace","--json-ui"]
                # This profile reports property IDs at implicit exceptions. The separate propagating profile is used in E01-E03.
                raw=benchmark.measure(cmd,120)
                for field in ("stdout","stderr"):z.writestr(m+"/"+field,raw[field])
                try: messages=json.loads(raw["stdout"])
                except ValueError:messages=[]
                checked=[{k:r.get(k) for k in ("property","status","description","sourceLocation")}
                         for part in messages for r in part.get("result",[]) if "null" in (r["property"]+" "+r["description"]).lower()]
                stock[m]={"argv":cmd,"exit":raw["exit"],"checks":checked}
            stock["postCall"]=stock_run("ExceptionAssertions","returned",[cp],[("int","mode")],z,"reach",bound=3)
        data={"job":os.environ.get("VERIFY_JOB_ID"),"checkerSha256":digest(checker),"physical":physical,
              "stock":stock,"native":result,"javaSha256":digest(src/"ThrowSites.java")}
        (target/"sites.json.gz").write_bytes(gzip.compress(encoded(data),mtime=0))
        print(len(physical),"original observations,",len(result),"selected native site/policy configurations")
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--physical-only",action="store_true")
    run(p.parse_args().physical_only)

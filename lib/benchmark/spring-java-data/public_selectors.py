"""Check the original frozen public guard through the repository's bytecode-qualified constant calls."""
import argparse
import os
from pathlib import Path
import sys
from measure import ROOT, SETUP, digest, read, run_cmd, seed, write
from targets import native_selectors, route, sidecar

def run(number, first, only, stage):
    folder, = (ROOT / "examples").glob(number+"-*")
    spec=read(folder/"target.json")
    seed(folder)
    if spec["history"]["repository"].startswith("local-git:"):
        os.environ.setdefault("TARGETS_LOCAL_GIT_ROOT",str(SETUP/"src"))
    example=read(folder/"example.json")
    target=sidecar.load(folder, example)
    out=folder/"records"/stage
    out.mkdir(parents=True, exist_ok=True)
    report={"job":os.environ["VERIFY_JOB_ID"],"source":os.environ["VERIFY_SOURCE_COMMIT"],
            "checkerSha256":digest(Path(os.environ["JVMCONTRACT"])),"libTree":os.environ["JVMCONTRACT_LIB_TREE"],
            "targetSha256":digest(folder/"target.json"),"tasks":{},"batches":{}}
    selected=[t for t in spec["tasks"] if t["kind"]=="prove" and (not only or t["id"] in only)]
    if only and {t["id"] for t in selected}!=set(only): raise ValueError("unknown task")
    for side in dict.fromkeys(t["revision"] for t in selected):
        tasks=[t["id"] for t in selected if t["revision"]==side]
        parent=folder/"records/native-selectors"/side
        previous=set(parent.glob("*"))
        cmd=[sys.executable,"examples/tools/build.py",number,"--native-selectors",",".join(tasks),
             "--checker-seconds","60","--first",str(first)]
        report["batches"][side]=run_cmd(cmd,out/(side+".log"))
        batch,=set(parent.glob("*"))-previous
        for name in tasks:
            p=batch/"tasks"/name/"result.json"
            checked=native_selectors.validate_result(folder,route.resolve(folder,example,target,name),p)
            report["tasks"][name]={"status":checked["status"],"firstBlocker":checked["firstBlocker"],
                                   "receipt":p.relative_to(folder).as_posix(),"sha256":digest(p)}
        write(out/"run.json",report)
    print({k:v["status"] for k,v in report["tasks"].items()})

if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("number")
    cli.add_argument("--first",type=int,default=0)
    cli.add_argument("--only",nargs="+")
    cli.add_argument("--stage",choices=["native-final","native-qualified","spring-startup"],default="native-final")
    args=cli.parse_args()
    run(args.number,args.first,args.only,args.stage)

"""Run the artifact-only operator or the matched explicit caller under the committed experimental docket."""
import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from history import OUTPUT,ROOT,encoded,digest,scratch
from freeze_product import verify
from packets import BASE
from references import DOCKET,REFS
from run_operator import launch,JDK

PUBLIC=OUTPUT/"blind"


def bindings(slot):
    checker,lock=verify()
    docket=json.loads(DOCKET.read_bytes())
    if docket["freezeSha256"]!=digest(HERE.parent/"freeze.json"):raise ValueError("reference docket uses a different freeze")
    row=next(x for x in docket["pairs"] if x["slot"]==slot)
    ref=REFS/slot;pair=BASE/slot/"packet"
    for f,h in row["sources"].items():
        if digest(ref/f)!=h:raise ValueError("changed frozen reference code")
    if digest(pair/"inputs.json")!=row["packetSha256"] or digest(ref/"reference.json")!=row["referenceSha256"]:
        raise ValueError("changed reference inputs")
    if digest(BASE/slot/"graphs.json")!=row["graphSha256"] or digest(ref/"original-jvm.json")!=row["physicalSha256"]:
        raise ValueError("changed original JVM or dependency receipt")
    return checker,lock,row,pair


def automatic(slot):
    checker,lock,ref,pair=bindings(slot)
    out=PUBLIC/slot/"automatic";out.mkdir(parents=True,exist_ok=True)
    store=BASE/slot/("automatic-"+lock["checkerSha256"])
    store.mkdir(exist_ok=True)
    with (store/"first-run.lock").open("a") as guard:
        fcntl.flock(guard,fcntl.LOCK_EX)
        fixed=store/"report.json.gz"
        if fixed.exists():
            bound=json.loads(gzip.decompress(fixed.read_bytes()))
            if (bound["rawSha256"]!=digest(store/"executions.zip") or bound["docketSha256"]!=digest(DOCKET)
                    or bound["packetSha256"]!=ref["packetSha256"]):
                raise ValueError("first automatic attempt has different bindings")
            for name in ("report.json.gz","executions.zip"):shutil.copyfile(store/name,out/name)
            return
        work=store/"isolated"
        try:
            if work.exists():
                raise ValueError("previous first attempt stopped before its receipt was finalized")
            report=launch(pair,work,checker,lock)
        except (OSError,ValueError) as e:
            partial=work/"output/first/report.json"
            if not partial.is_file():partial=work/"output/first/selection.json"
            report=json.loads(partial.read_bytes()) if partial.is_file() else {"runs":[],"selected":[]}
            report.update(status="operator failure",problem=str(e))
        raw=work/"output/first"
        with zipfile.ZipFile(out/"executions.zip","w",zipfile.ZIP_DEFLATED) as z:
            if raw.is_dir():
                for path in sorted(raw.rglob("*")):
                    if path.is_file():z.write(path,path.relative_to(raw))
            if (work/"operator.log").is_file():z.write(work/"operator.log","operator.log")
        for i,r in enumerate(report["runs"]):
            folder=raw/f"case{i}"
            for label,name in (("cold","native"),("warm","warm")):
                f=folder/(name+".json.cost.json")
                if f.exists():r[label+"Cost"]=json.loads(f.read_bytes())
        warm=raw/"warm.json"
        if warm.is_file():report["warmAgreement"]=json.loads(warm.read_bytes())
        report.update(slot=slot,packetSha256=ref["packetSha256"],docketSha256=digest(DOCKET),
                      checkerSha256=digest(checker),rawSha256=digest(out/"executions.zip"),job=os.environ.get("VERIFY_JOB_ID"))
        (out/"report.json.gz").write_bytes(gzip.compress(encoded(report),mtime=0))
        shutil.copyfile(out/"executions.zip",store/"executions.zip")
        temporary=store/"report.partial"
        shutil.copyfile(out/"report.json.gz",temporary)
        temporary.replace(fixed)
        print(slot,len(report["selected"]),"automatic candidates",flush=True)


def matched_namespace(pair,ref,out,checker,physical,worker="matched_worker.py", *, native_only=False):
    # The measured libraries and checker can only see the pinned public modules, their own caller and writable scratch.
    fake_home="/guest"
    jpath=fake_home+"/.sdkman/candidates/java/21.0.13.0+9-tem"
    with scratch(prefix="blind-matched-") as tmp:
        work=Path(tmp);temp=work/"scratch";temp.mkdir()
        cmd=["bwrap","--die-with-parent","--new-session","--unshare-user","--unshare-pid","--unshare-net","--unshare-ipc",
            "--unshare-uts","--clearenv","--ro-bind","/usr","/usr","--symlink","usr/bin","/bin","--symlink","usr/lib","/lib",
            "--symlink","usr/lib64","/lib64","--dev","/dev","--proc","/proc","--remount-ro","/proc","--tmpfs","/tmp",
            "--dir","/etc","--ro-bind","/etc/ld.so.cache","/etc/ld.so.cache","--ro-bind",str(JDK),jpath,
            "--ro-bind",str(checker),"/opt/checker","--ro-bind",str(pair),"/inputs","--ro-bind",str(ref),"/reference",
            "--bind",str(temp),fake_home+"/.cache/in-the-loop/tmp","--bind",str(out),"/output",
            "--setenv","HOME",fake_home,"--setenv","TMPDIR",fake_home+"/.cache/in-the-loop/tmp","--setenv","JVMCONTRACT","/opt/checker",
            "--setenv","JAVA_HOME",jpath,"--setenv","JVMCONTRACT_JAR_RELEASE","21","--setenv","PATH",jpath+"/bin:/usr/bin:/bin",
            "--setenv","TZ","UTC","--setenv","LANG","C.UTF-8","--chdir",fake_home+"/.cache/in-the-loop/tmp"]
        for rel in ("lib/benchmark","lib/python","lib/tools","examples/tools"):
            cmd+=["--ro-bind",str(ROOT/rel),"/tool/"+rel]
        if worker not in ("matched_worker.py","assisted_worker.py","identity_worker.py"):raise ValueError("unknown matched worker")
        cmd+=["/usr/bin/python3","-B","/tool/lib/benchmark/beyond-jbmc/blind/"+worker]
        if physical:cmd.append("--physical-only")
        if native_only:cmd.append("--native-only")
        with (out/"process.log").open("wb") as f:
            proc=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
        return proc.returncode


def matched(slot,assisted=False):
    checker,lock,row,pair=bindings(slot)
    out=PUBLIC/slot/("assisted" if assisted else "matched");out.mkdir(parents=True,exist_ok=True)
    code=matched_namespace(pair,REFS/slot,out,checker,False,"assisted_worker.py" if assisted else "matched_worker.py")
    file=out/"worker.json"
    receipt=json.loads(file.read_bytes()) if file.exists() else {"status":"worker failure","problem":"isolated caller job exited "+str(code)}
    receipt.update(slot=slot,workerExit=code,docketSha256=digest(DOCKET),packetSha256=row["packetSha256"],
                   checkerSha256=digest(checker),job=os.environ.get("VERIFY_JOB_ID"))
    (out/"report.json").write_bytes(encoded(receipt))
    print(slot,receipt["status"],flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("lane",choices=("automatic","matched","assisted"));p.add_argument("slots",nargs="+")
    a=p.parse_args()
    for slot in a.slots:
        if slot not in [f"{n:02}" for n in range(1,17)]:p.error("unknown blind slot")
        if a.lane=="automatic":automatic(slot)
        else:matched(slot,assisted=a.lane=="assisted")

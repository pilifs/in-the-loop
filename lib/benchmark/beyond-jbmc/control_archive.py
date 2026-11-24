"""Preserve the original per-engine command output alongside the frozen 60- and 49-claim control matrices."""
import argparse,gzip,json,os
from pathlib import Path
import subprocess,sys,zipfile
from history import HERE,ROOT,OUTPUT,digest,encoded,scratch
from freeze_product import verify
from regressions import core60,follow49
from campaign import CLAIMS

def run(which):
    checker,lock=verify(); os.environ["JVMCONTRACT"]=str(checker)
    out=OUTPUT/"closing/control-evidence"/which;out.mkdir(parents=True,exist_ok=True)
    with scratch(prefix="control-raw-") as tmp:
        work=Path(tmp);allrows=(core60 if which=="60" else follow49)(work)
        stock_status={}
        if which=="60":
            sys.path.insert(0,str(HERE.parent/"java-semantics-gap"))
            from standalone import measure as stock
            for name in CLAIMS:
                try:
                    stock(name,"packaged","installed",work/"standalone")
                    stock_status[name]="measured"
                except (OSError,ValueError,subprocess.SubprocessError) as exc:
                    stock_status[name]=repr(exc)
        else:
            driver=HERE.parent/"jbmc-fast-follow/measure.py"
            for fam in ("callbacks","numeric","rows","strings","queue"):
                proc=subprocess.run([sys.executable,"-B",driver,"successor",fam,"packaged","--output",work])
                stock_status[fam]="measured" if proc.returncode==0 else "producer exit "+str(proc.returncode)
        if len(allrows)!=2*int(which):raise ValueError("incomplete historical control measurements")
        files=[]
        with zipfile.ZipFile(out/"executions.zip","w",zipfile.ZIP_DEFLATED) as z:
            for p in sorted(work.rglob("*")):
                if p.is_file():
                    rel=p.relative_to(work).as_posix();z.write(p,rel);files.append({"file":rel,"sha256":digest(p)})
        (out/"index.json.gz").write_bytes(gzip.compress(encoded({"population":which,"originalProfiles":allrows,"files":files,
            "additionalPackagedProfiles":stock_status,
            "archiveSha256":digest(out/"executions.zip"),"checkerSha256":digest(checker),"job":os.environ.get("VERIFY_JOB_ID")}),mtime=0))
        print(which,len(files),"original evidence files retained")
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("which",choices=("60","49"));run(p.parse_args().which)

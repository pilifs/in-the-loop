"""Disclosed false-oracle checks for Jackson and a held-out Lucene payload-before-header layout."""
import argparse,os
from pathlib import Path
from history import HERE,ROOT,OUTPUT,digest,scratch
from release_cases import Claim,Subject,jars_for,jvm_controls,measure_subject
from more_wire import prepare_pair,RECORDS

def run(key,physical):
    with scratch(prefix="stronger-disclosed-control-") as tmp:
        w=Path(tmp)
        if key=="N11-identity":
            o,n=(jars_for("jackson-"+v) for v in ("2.17.1","2.17.2"))
            a=[HERE/"text/JacksonNumbers.java"];b=HERE/"text/JacksonIdentity.java"
            claims=(Claim("unchanged","int ordinal",holds=(("1",),),fails=(("516",),)),Claim("fixed",holds=(),fails=((),)))
        else:
            o,n=(jars_for("lucene-core-"+v) for v in ("8.11.0","9.0.0"))
            a=[HERE/"wire-more/PayloadFirst.java"];b=HERE/"wire-more/PayloadFirstClaims.java"
            claims=tuple(Claim(s,"int header, int payload",holds=RECORDS) for s in ("oldNew","newOld"))
        s=Subject(0,b.stem,key,claims,24 if key=="N11-identity" else 16,32 if key=="N11-identity" else 16)
        cp,orig,env,identity=prepare_pair(w,a,o,n,[b])
        params=w/"controls";params.mkdir()
        original=jvm_controls(s,params,orig,env)
        if jvm_controls(s,params,cp,env)!=original:raise ValueError("different isolated and original controls")
        base={**identity,"jvm":original,"rows":[],"job":os.environ.get("VERIFY_JOB_ID"),"checkerSha256":digest(Path(os.environ.get("JVMCONTRACT",ROOT/"lib/target/release/jvmcontract")))}
        measure_subject(key,s,"qualified",w,env,cp,base,OUTPUT/"qualified"/key,physical,original_cp=orig)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("cases",nargs="+",choices=("N11-identity","W09-reordered"));p.add_argument("--physical-only",action="store_true")
    a=p.parse_args()
    for name in a.cases:run(name,a.physical_only)

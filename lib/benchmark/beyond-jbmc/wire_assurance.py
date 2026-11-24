"""Bind the independent SAT checker to each completed original wire caller, from the request through every solver call."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import uuid

from history import OUTPUT, ROOT, digest, scratch
from wire_campaign import CASES, prepare, physical, classpath
import jvmcontract_io
import jvmcontract_lrat as lrat


def content(path):
    if path.is_file(): return digest(path)
    return lrat.identity({p.relative_to(path).as_posix(): digest(p) for p in sorted(path.rglob("*.class"))})


def certify(target, case, domain, out, work, env, cp, identities):
    out.mkdir(parents=True,exist_ok=True)
    work.mkdir()
    bindings=[{"path":str(s),"content":content(s)} for s in cp]
    solver_dir=work/"solver-traces"
    solver_dir.mkdir()
    checker=Path(os.environ["JVMCONTRACT"]).resolve()
    cmd=[str(checker),"prove",target,"--classes",str(cp[0]),"--classpath",classpath(cp[1:]),
         "--engine","native","--gaps","strict","--assert","result","--unwind","16","--max-array-length","8",
         "--timeout","120","--work",str(work),"--json"]
    request={"schema":"native-sat-request/v1","run":str(uuid.uuid4()),"case":case,"target":target,"argv":cmd,
             "claim":{"observation":"boolean result; no exception","domain":domain,"unwind":16,"arrayBound":8},
             "beforeLaunch":identities,"bindings":bindings,"checkerSha256":digest(checker),
             "sourceCommit":os.environ.get("VERIFY_SOURCE_COMMIT"),"job":os.environ.get("VERIFY_JOB_ID")}
    lrat.save(out/"request.json",request)
    result=subprocess.run(cmd,env=dict(env,JVMCONTRACT_TRANSCRIPTS=str(solver_dir),JVMCONTRACT_LRAT_MODELS="1"),
                          capture_output=True,timeout=175)
    (out/"ordinary.json").write_bytes(result.stdout)
    decoded=jvmcontract_io.decode(result.stdout.decode(),"prove")
    if result.returncode!=0 or not decoded.ok or len(decoded.outcomes)!=1:
        raise ValueError(target+" did not produce a completed ordinary proof")
    row=decoded.outcomes[0]
    stated=row["stated"]
    if row["target"] != request["target"] or row["verdict"]!="verified" or stated["vacuity"]["status"]!="non-vacuous":
        raise ValueError(target+" did not establish the bound non-vacuous request")
    if [content(p) for p in cp] != [v["content"] for v in bindings] or digest(checker)!=request["checkerSha256"]:
        raise ValueError("program or checker changed after request")
    anchor={"status":"established","execution":request["run"],"receiptSha256":digest(out/"ordinary.json"),
            "conclusion":{"status":"established","vacuous":False,"stated":stated},"jvmReplay":[]}
    boundary,streams=lrat.capture(request,anchor,work,solver_dir,row["search"]["runs"])
    checked=lrat.complete(out,request,boundary,streams)
    other=copy.deepcopy(request);other["claim"]["observation"]="always false after the public calls"
    try: lrat.verify(other,boundary,out/"evidence.zip")
    except ValueError: pass
    else: raise ValueError("bundle accepted against another public observation")
    lrat.save(out/"negative-control.json",{"wrongObservationRejected":True,"originalRequest":lrat.identity(request),
                                         "alteredRequest":lrat.identity(other)})
    print(target,checked["status"],checked["answers"],flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("methods",nargs="+",choices=("oldNew","newOld","writeFrame","readFrame","varOldNew","varNewOld"))
    a=p.parse_args()
    with scratch(prefix="wire-assurance-") as tmp:
        setup=Path(tmp);env,jars,cp,ids=prepare(setup)
        ids["originalJvm"]=physical(setup,env,jars,cp)
        for name in a.methods:
            certify("WireClaims#"+name,*CASES[name],OUTPUT/"assurance/wire"/name,setup/("evidence-"+name),env,cp,ids)

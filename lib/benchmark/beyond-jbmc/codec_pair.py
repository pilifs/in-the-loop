"""Compare all three Codec 128-bit wrappers, transfer their unaffected 32-bit observation, and test proof reuse."""
import argparse
import json
import os
from pathlib import Path
import zipfile
from history import HERE,ROOT,OUTPUT,encoded,digest,benchmark,scratch
from release_cases import Claim,Subject,jars_for,jvm_controls,measure_subject
from more_wire import prepare_pair
from stock_history import classpath

VERSIONS=("1.13","1.14","1.15")
POS=(("new byte[]{1,-1,2}","1","1","0"),("new byte[]{2,3,4,5}","0","4","7"))
NEG=(("new byte[0]","0","0","-1"),("new byte[]{1,-1}","0","2","Integer.MIN_VALUE"))
PARAMS="byte[] text, int off, int len, int seed"


def main(old,new,physical_only):
    key="C01-C05-"+old+"-"+new
    with scratch(prefix="codec-versions-") as tmp:
        work=Path(tmp);src=HERE/"extended"
        cp,orig,env,pin=prepare_pair(work,[src/"CodecPublic.java"],jars_for("commons-codec-"+old),jars_for("commons-codec-"+new),[src/"CodecChanges.java"])
        same=(old,new)==("1.13","1.15")
        claims=[Claim("historicalIdentity",PARAMS,holds=POS+NEG if same else POS,fails=() if same else NEG),
                Claim("unchanged32",PARAMS,holds=POS+NEG)]
        if not same:claims.append(Claim("seedBoundary",PARAMS,holds=POS+NEG))
        subject=Subject(0,"CodecChanges",key,tuple(claims))
        checks=jvm_controls(subject,work,orig,env)
        if checks!=jvm_controls(subject,work,cp,env):raise ValueError("relocation changed original controls")
        record={**pin,"jvm":checks,"rows":[],"job":os.environ.get("VERIFY_JOB_ID"),"phase":"qualified"}
        out=OUTPUT/"qualified"/key
        measure_subject(key,subject,"qualified",work,env,cp,record,out,physical_only,original_cp=orig)
        if (old,new)!=("1.14","1.15") or physical_only:return
        # The property compares the selected release's public wrapper with itself across two methods.
        # A second bound, with seed -1 and an independently observed output, must invalidate old evidence.
        code=src/"CachedCodec.java";compiled=work/"cached"
        from release_cases import compile_java
        oldj=jars_for("commons-codec-"+old);newj=jars_for("commons-codec-"+new)
        compile_java([code],compiled,oldj,env)
        checker=Path(os.environ["JVMCONTRACT"]).resolve()
        results=[]
        controls={}
        for phase,jars in (("old",oldj),("new",newj)):
            ctrl=work/("cache-controls-"+phase)
            ctrl.mkdir()
            empty=Claim("empty128") if phase=="old" else Claim("empty128",holds=(),fails=((),))
            subject=Subject(0,"CachedCodec",phase,(Claim("tail","byte value, int seed",
                holds=(("(byte)-1","-1"),("(byte)0","0"),("(byte)127","42"))),empty))
            controls[phase]=jvm_controls(subject,ctrl,[compiled,*jars],env)
        with zipfile.ZipFile(out/"warm-cold.zip","w",zipfile.ZIP_DEFLATED) as z:
            for method in ("tail","empty128"):
                for phase,jars,cache in (("old",oldj,"shared"),("new-warm",newj,"shared"),("new-clean",newj,"clean")):
                    unique=method+"-"+phase
                    cmd=[str(checker),"prove","CachedCodec#"+method,"--classes",str(compiled),"--classpath",classpath(jars),
                         "--assert","result","--engine","native","--gaps","strict","--cache",str(work/(method+cache)),
                         "--work",str(work/unique),"--unwind","16","--max-array-length","8","--timeout","120","--json"]
                    r=benchmark.measure(cmd,180)
                    for f in ("stdout","stderr"):z.writestr(unique+"/"+f,r[f])
                    row=benchmark.outcome_of({"kind":"property"},r["stdout"]) or {}
                    results.append({"phase":phase,"method":method,"argv":cmd,"classpath":[digest(p) for p in jars],
                                    "verdict":row.get("verdict"),"search":row.get("search"),"problem":row.get("problem"),
                                    "counterexample":row.get("counterexample"),"cost":{k:r[k] for k in ("seconds","cpuSeconds","peakMB","exit")}})
            z.writestr("calls.json",encoded(results))
        (out/"cache.json").write_bytes(encoded({"physical":controls,"runs":results}))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("old",choices=VERSIONS);p.add_argument("new",choices=VERSIONS)
    p.add_argument("--physical-only",action="store_true");a=p.parse_args();main(a.old,a.new,a.physical_only)

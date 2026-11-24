"""Check the complete wire-record and streaming-hash algebra against their deliberately incorrect controls."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import zipfile

from history import HERE,OUTPUT,digest,encoded,scratch
from release_cases import jars_for
from wire_calculus import LEAN

MODELS={
    "wire":("wire/FrameInduction.lean",("full_word","parse_suffix","word_suffix","record_suffix","entire_sequence","record_progress","prefix_capacity"),
            "example : FrameInduction.reverseWord (0x01020304 : FrameInduction.Word) = 0x01020304 := by decide",
            ("lucene-core-8.11.0","lucene-core-9.0.0"),
            ("org/apache/lucene/store/DataInput","org/apache/lucene/store/DataOutput","org/apache/lucene/store/ByteArrayDataInput","org/apache/lucene/store/ByteArrayDataOutput"),
            ("wire/WireAPI.java","wire-more/WireMore.java","wire-more/PayloadFirst.java","wire-more/PayloadFirstClaims.java")),
    "codec":("extended/StreamHash.lean",("fold_blocks","all_partitions","arbitrary_stream","reset_stream","empty_negative_byte"),
             "example : StreamHash.oneShot [0xff] 0 = 0x79a8e694 := by decide",("commons-codec-1.15",),
             ("org/apache/commons/codec/digest/MurmurHash3","org/apache/commons/codec/digest/MurmurHash3$IncrementalHash32x86"),
             ("extended/Incremental.java",)),
}


def run(name):
    source,claims,wrong,graphs,classes,callers=MODELS[name]
    file=HERE/source
    out=OUTPUT/"assurance"/(name+"-sequence");out.mkdir(parents=True,exist_ok=True)
    with scratch(prefix="campaign-sequence-") as tmp:
        work=Path(tmp)
        cmd=[str(LEAN),str(file)]
        proof=subprocess.run(cmd,cwd=work,capture_output=True,text=True,timeout=150)
        (out/"kernel.log").write_text(proof.stdout+proof.stderr)
        if proof.returncode or "sorry" in proof.stdout or not all(file.stem+"."+c in proof.stdout for c in claims):
            print((proof.stdout+proof.stderr)[-6000:],flush=True)
            raise ValueError("independent kernel did not establish every named claim")
        negative=work/("False"+file.name);negative.write_text(file.read_text()+"\n"+wrong+"\n")
        control=subprocess.run([LEAN,negative],cwd=work,capture_output=True,text=True,timeout=150)
        if control.returncode==0 or "error:" not in control.stdout:raise ValueError("the rejected control was not exercised")
        identity=[]
        import hashlib
        for graph in graphs:
            jar,=jars_for(graph)
            with zipfile.ZipFile(jar) as z:
                identity.append({"artifact":jar.name,"sha256":digest(jar),"members":{c:hashlib.sha256(z.read(c+".class")).hexdigest() for c in classes}})
        reductions=sorted(set(re.findall(r"[\w.]+\._native\.bv_decide\.ax_[\w]+",proof.stdout)))
        report={"prover":subprocess.check_output([LEAN,"--version"],text=True).strip(),"proverSha256":digest(LEAN),
                "model":source,"modelSha256":digest(file),"claims":claims,"kernelOutput":proof.stdout,
                "compiledBooleanCertificateReductions":reductions,
                "originalClasses":identity,"callersSha256":{c:digest(HERE/c) for c in callers},
                "job":os.environ.get("VERIFY_JOB_ID"),"argv":cmd,"negative":wrong,"rejection":control.stdout,
                "scope":"Executable algebra over fixed-width bit vectors and finite byte lists. Original Java correspondence is measured separately on the released caller and its bounds."}
        (out/"receipt.json").write_bytes(encoded(report))
        print(name,len(claims),"theorems checked and incorrect control rejected",flush=True)


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("models",nargs="+",choices=MODELS)
    for name in ap.parse_args().models:run(name)

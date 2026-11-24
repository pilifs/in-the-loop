"""Check the complete wire-record and streaming-hash algebra against their deliberately incorrect controls."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import zipfile

from history import HERE,OUTPUT,digest,encoded,scratch
from release_cases import JDK,jars_for
from wire_calculus import LEAN
from jvm_disassembly import methods

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
    "seed":("extended/Seed128.lean",("step_inj","avalanche_inj","output_inj","signed_seed_boundary"),
            "example : Seed128.output [] (0,0) 0 (0xffffffffffffffff) = Seed128.output [] (0,0) 0 (0xffffffff) := by decide",
            ("commons-codec-1.13","commons-codec-1.14","commons-codec-1.15"),("org/apache/commons/codec/digest/MurmurHash3",),
            ("extended/CodecPublic.java","extended/CodecChanges.java")),
}

def seed_bindings(work):
    from hashlib import sha256
    bodies={};wrappers={}
    for version in ("1.13","1.14","1.15"):
        jar,=jars_for("commons-codec-"+version)
        target=work/"MurmurHash3.class"
        with zipfile.ZipFile(jar) as z:target.write_bytes(z.read("org/apache/commons/codec/digest/MurmurHash3.class"))
        listing,_=methods(JDK/"bin/javap",target)
        def body(method,desc):
            return [[i.pc,i.op,re.sub(r"#\d+","#",i.arg),i.member] for i in listing[method,desc]["code"]]
        head=body("hash128","([BIII)[J")
        wrappers[version]={"classSha256":digest(target),"wrapper":head[:9],"wrapperInstructions":len(head)}
        if version=="1.13":
            if [i[1] for i in head[:6]]!=["iload_3","i2l","lstore","iload_3","i2l","lstore"]:
                raise ValueError("1.13 seed initialization differs")
            continue
        named="hash128x64" if version=="1.14" else "hash128x64Internal"
        unsigned=body("hash128x64","([BIII)[J")
        if [i[1] for i in unsigned[4:7]]!=["i2l","ldc2_w","land"] or unsigned[5][3]!="long 4294967295l":
            raise ValueError("canonical 32-bit seed is no longer zero-extended")
        if version=="1.14" and head[-2][3]!="Method hash128x64:([BIII)[J":
            raise ValueError("middle wrapper no longer selects the unsigned overload")
        if version=="1.15" and (head[4][1]!="i2l" or head[-2][3]!="Method hash128x64Internal:([BIIJ)[J"):
            raise ValueError("last wrapper no longer sign-extends the caller seed")
        wrappers[version]["unsignedWrapper"]=unsigned
        bodies[version]={n:body(m,d) for n,m,d in (("body",named,"([BIIJ)[J"),("avalanche","fmix64","(J)J"),("readWord","getLittleEndianLong","([BI)J"))}
    if bodies["1.14"]!=bodies["1.15"]:raise ValueError("hash bodies or dependencies differ in normalized bytecode")
    return {"releaseWrappers":wrappers,"common14And15":{k:{"instructions":len(v),"sha256":sha256(encoded(v)).hexdigest()}
                                                        for k,v in bodies["1.14"].items()},"normalization":"constant-pool numeric references only"}


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
        if (control.returncode==0 or "Tactic `decide` proved that the proposition" not in control.stdout
                or not control.stdout.rstrip().endswith("is false")):
            raise ValueError("the independent negative control did not evaluate to false")
        identity=[]
        import hashlib
        for graph in graphs:
            jar,=jars_for(graph)
            with zipfile.ZipFile(jar) as z:
                identity.append({"artifact":jar.name,"sha256":digest(jar),"members":{c:hashlib.sha256(z.read(c+".class")).hexdigest() for c in classes}})
        reductions=sorted(set(re.findall(r"[\w.]+\._native\.bv_decide\.ax_[\w]+",proof.stdout)))
        if reductions:raise ValueError("a compiled Boolean reduction still needs independent discharge")
        report={"prover":subprocess.check_output([LEAN,"--version"],text=True).strip(),"proverSha256":digest(LEAN),
                "model":source,"modelSha256":digest(file),"claims":claims,"kernelOutput":proof.stdout,
                "compiledBooleanCertificateReductions":reductions,
                "originalClasses":identity,"callersSha256":{c:digest(HERE/c) for c in callers},
                "job":os.environ.get("VERIFY_JOB_ID"),"argv":cmd,"negative":wrong,"rejection":control.stdout,
                "scope":"Executable algebra over fixed-width bit vectors and finite byte lists. Original Java correspondence is measured separately on the released caller and its bounds."}
        if name=="seed":report["bytecode"]=seed_bindings(work)
        (out/"receipt.json").write_bytes(encoded(report))
        print(name,len(claims),"theorems checked and incorrect control rejected",flush=True)


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("models",nargs="+",choices=MODELS)
    for name in ap.parse_args().models:run(name)

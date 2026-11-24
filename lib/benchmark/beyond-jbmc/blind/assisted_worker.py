"""Evaluate each conjunct on its original resource graph when relocation changes a reference observation."""
import json
import os
from pathlib import Path
from matched_worker import INPUTS,SRC,OUT,graph,write
from release_cases import Claim,Subject,compile_java,javaenv,jvm_controls,measure_subject
from history import digest


def main():
    work=Path.cwd()
    spec=json.loads((SRC/"reference.json").read_bytes());packet=json.loads((INPUTS/"inputs.json").read_bytes())
    old,new=[graph(k,packet) for k in ("old","new")]
    env=javaenv();api=work/"caller";compile_java([SRC/"ReferenceAPI.java"],api,old,env)
    methods=[l for l in (SRC/"ReferencePair.java").read_text().splitlines() if any(
        (" "+m+"(int n)") in l for m in ("admitted","oldExpected","newExpected","controlExpected"))]
    if len(methods)!=4:raise ValueError("reference oracle method set has changed")
    seeds=tuple((str(v),) for v in spec["seeds"])
    subject=Subject(0,"SideReference","unmodified release",(
        Claim("primary","int n",holds=seeds),Claim("control","int n",holds=seeds),
        Claim("inverse","int n",holds=(),fails=seeds)),8,16)
    receipt={"status":"preparing","scope":"separate original-release conjuncts of the same frozen primary and control",
             "assistance":"measurement harness changed after the blind first pass","sides":{}}
    write(receipt)
    for side,graphfiles,expected in (("old",old,"oldExpected"),("new",new,"newExpected")):
        folder=work/side;folder.mkdir();classes=folder/"claims"
        src=folder/"SideReference.java"
        src.write_text("public final class SideReference {\n"+"\n".join(methods)+"""
    public static boolean primary(int n) throws Exception {
        if (!admitted(n)) return true;
        return ReferenceAPI.primary(n)==EXPECTED(n);
    }
    public static boolean control(int n) throws Exception {
        if (!admitted(n)) return true;
        return ReferenceAPI.control(n)==controlExpected(n);
    }
    public static boolean inverse(int n) throws Exception {return !admitted(n) || !primary(n);}
}
""".replace("EXPECTED",expected))
        compile_java([src],classes,[api,*old],env)
        cp=[classes,api,*graphfiles]
        controls=jvm_controls(subject,folder,cp,env)
        record={"jvm":controls,"rows":[],"sourceSha256":digest(src),"primaryApiSha256":digest(api/"ReferenceAPI.class"),
                "referenceSha256":digest(SRC/"ReferencePair.java"),"classpath":packet[side],"scope":spec["domain"],
                "checkerSha256":digest(Path(os.environ["JVMCONTRACT"]))}
        measure_subject(side,subject,"assisted",folder,env,cp,record,OUT/side,False)
        receipt["sides"][side]={"rows":len(record["rows"]),"original":controls}
        write(receipt)
    receipt["status"]="measured";write(receipt)

if __name__=="__main__":main()

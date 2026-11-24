"""Disclosed false-oracle checks for Jackson and a held-out Lucene payload-before-header layout."""
import argparse,os,subprocess
from pathlib import Path
from history import HERE,ROOT,OUTPUT,digest,encoded,scratch
from release_cases import Claim,Subject,JDK,compile_java,jars_for,jvm_controls,measure_subject
from more_wire import prepare_pair,RECORDS
from stock_history import classpath

def run(key,physical):
    with scratch(prefix="stronger-disclosed-control-") as tmp:
        w=Path(tmp)
        if key.startswith("N11"):
            o,n=(jars_for("jackson-"+v) for v in ("2.17.1","2.17.2"))
            a=[HERE/"text/JacksonNumbers.java"];b=HERE/"text/JacksonIdentity.java"
            claims=(Claim("unchanged","int ordinal",holds=(("1",),),fails=(("516",),)),Claim("fixed",holds=(),fails=((),)))
            if key=="N11-extended":
                b=HERE/"text/JacksonExtended.java"
                claims=(Claim("fifthLength","int ordinal",holds=(("11111",),("11116",),("111110",))),Claim("exerciseNegative"))
        else:
            o,n=(jars_for("lucene-core-"+v) for v in ("8.11.0","9.0.0"))
            a=[HERE/"wire-more/PayloadFirst.java"];b=HERE/"wire-more/PayloadFirstClaims.java"
            claims=tuple(Claim(s,"int header, int payload",holds=RECORDS) for s in ("oldNew","newOld"))
        s=Subject(0,b.stem,key,claims,24 if key.startswith("N11") else 16,32 if key.startswith("N11") else 16)
        cp,orig,env,identity=prepare_pair(w,a,o,n,[b])
        params=w/"controls";params.mkdir()
        original=jvm_controls(s,params,orig,env)
        if jvm_controls(s,params,cp,env)!=original:raise ValueError("different isolated and original controls")
        base={**identity,"jvm":original,"rows":[],"job":os.environ.get("VERIFY_JOB_ID"),"checkerSha256":digest(Path(os.environ.get("JVMCONTRACT",ROOT/"lib/target/release/jvmcontract")))}
        measure_subject(key,s,"qualified",w,env,cp,base,OUTPUT/"qualified"/key,physical,original_cp=orig)
        if key=="N11-extended" and not physical:
            java=w/"FifthGrid.java"
            java.write_text("""public class FifthGrid {public static void main(String[] args){
                int flips=0;for(int i=11111;i<=111110;i++){
                    if(!JacksonExtended.fifthLength(i))throw new AssertionError(i);
                    String s=JacksonNumbers.input(i);if(before.JacksonNumbers.looks(s)!=JacksonNumbers.looks(s))flips++;
                }
                if(flips!=135)throw new AssertionError(flips);System.out.println("135 changed and 99865 preserved");
            }}""")
            dest=w/"fifth-grid";compile_java([java],dest,orig,env)
            cmd=[JDK/"bin/java","-ea","-Xmx512m","-cp",classpath([dest,*orig]),"FifthGrid"]
            raw=subprocess.check_output(cmd,env=env,text=True,timeout=120)
            (OUTPUT/"qualified"/key/"grid.json").write_bytes(encoded({"argv":list(map(str,cmd)),"observations":raw.strip(),"sourceSha256":digest(java)}))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("cases",nargs="+",choices=("N11-identity","N11-extended","W09-reordered"));p.add_argument("--physical-only",action="store_true")
    a=p.parse_args()
    for name in a.cases:run(name,a.physical_only)

"""N11 predicate and quoted-token consumer, with each physical release in its own class loader."""
import argparse
import os
from pathlib import Path
import subprocess

from history import HERE,ROOT,OUTPUT,JBMC,MODELS,encoded,digest,scratch
from release_cases import Subject,Claim,jars_for,jvm_controls,measure_subject,JDK,compile_java
from more_wire import prepare_pair
from stock_history import classpath


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--physical-only",action="store_true");p.add_argument("--grid",action="store_true")
    a=p.parse_args();src=HERE/"text"
    with scratch(prefix="jackson-partition-") as tmp:
        work=Path(tmp)
        old=jars_for("jackson-2.17.1");new=jars_for("jackson-2.17.2")
        cp,original,env,pin=prepare_pair(work,[src/"JacksonNumbers.java",src/"DatabindAPI.java"],old,new,
                                       [src/"JacksonPartition.java",src/"QuotedPartition.java"])
        both=(("0",),("1",),("29",),("83",),("516",),("11110",))
        for key,subject in (("N11-core",Subject(0,"JacksonPartition","paired Jackson",(
                Claim("changed","int ordinal",holds=both),Claim("nullControl")),24,32)),
                ("N11-quoted",Subject(0,"QuotedPartition","paired Jackson",(
                Claim("partition","int ordinal, int kind",holds=tuple((n[0],str(k)) for n in both for k in range(4))),),24,32))):
            d=work/key;d.mkdir()
            physical=jvm_controls(subject,d,original,env)
            paired=jvm_controls(subject,d,cp,env)
            if physical!=paired:raise ValueError("relocation disagrees on the original controls")
            record={**pin,"jvm":physical,"rows":[],"input":"the 11,111 strings in the committed ordinal bijection",
                    "jvmcontractSha256":digest(Path(os.environ.get("JVMCONTRACT",ROOT/"lib/target/release/jvmcontract"))),
                    "job":os.environ.get("VERIFY_JOB_ID"),"sourceCommit":os.environ.get("VERIFY_SOURCE_COMMIT")}
            measure_subject(key,subject,"qualified",d,env,cp,record,OUTPUT/"qualified"/key,a.physical_only,original_cp=original)
        if a.grid:
            code=work/"OriginalGrid.java"
            code.write_text("""public class OriginalGrid { public static void main(String[] args) throws Exception {
                int flips=0; int[] consumer=new int[4];
                for(int i=0;i<=11110;i++){
                    String s=JacksonNumbers.input(i);
                    if(!JacksonPartition.changed(i)) throw new AssertionError(i);
                    if(before.JacksonNumbers.looks(s)!=JacksonNumbers.looks(s)) ++flips;
                    for(int k=0;k<4;k++) {
                        if(!QuotedPartition.partition(i,k)) throw new AssertionError(i);
                        if(before.DatabindAPI.read(s,k)[0]!=DatabindAPI.read(s,k)[0]) consumer[k]++;
                    }
                }
                for(int n:consumer)if(n!=63)throw new AssertionError(n);
                if(flips!=63 || !JacksonPartition.nullControl())throw new AssertionError(flips);
                System.out.println("63 changed, 11048 preserved; 63 changed independently for each of four consumers");
            }}""")
            mixed=src/"MixedJackson.java"
            dest=work/"grid";compile_java([code,mixed],dest,original,env)
            cmd=[str(JDK/"bin/java"),"-Xmx768m","-XX:-UsePerfData","-ea","-cp",classpath([dest,*original]),"OriginalGrid"]
            measured=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=150,check=True)
            experiments=[]
            for core,others in ((old,new),(new,old)):
                control,mixture=[work/"caller",*core],[work/"caller",core[0],*others[1:]]
                setting=dict(env,WIRE_ORIGINAL_BEFORE=classpath(control),WIRE_ORIGINAL_AFTER=classpath(mixture))
                invocation=[*cmd[:-1],"MixedJackson"]
                tested=subprocess.run(invocation,env=setting,capture_output=True,text=True,timeout=30,check=True)
                experiments.append({"control":[p.name for p in control[1:]],"mixed":[p.name for p in mixture[1:]],
                                    "argv":invocation,"stdout":tested.stdout.strip()})
            path=OUTPUT/"qualified/N11-grid.json";path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(encoded({**pin,"sourceSha256":digest(code),"argv":cmd,"stdout":measured.stdout.strip(),
                                     "mixSourceSha256":digest(mixed),"mixtures":experiments,"job":os.environ.get("VERIFY_JOB_ID")}))
            print(measured.stdout,flush=True)


if __name__=="__main__":main()

"""Measure one previously locked blind public caller under the two original releases and matching proof profiles."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from history import encoded,digest
from more_wire import bridges,prepare_pair
from release_cases import compile_java,javaenv,jvm_controls,measure_subject,Claim,Subject,JDK
from stock_history import classpath

SRC=Path("/reference")
OUT=Path("/output")
INPUTS=Path("/inputs")


def write(record):
    path=OUT/"worker.json"
    path.write_bytes(encoded(record))


def graph(label,packet):
    values=[]
    for k,entry in enumerate(packet[label]):
        name=f"{label}/{k:03d}.jar"
        path=INPUTS/name
        if entry!={"path":name,"sha256":digest(path)}:raise ValueError("unbound classpath input")
        values.append(path)
    return values


def physical(work,old,new,seeds):
    src=SRC/"ReferenceAPI.java";claim=SRC/"ReferencePair.java";env=javaenv()
    target=work/"caller"
    compile_java([src],target,old,env)
    harness=work/"physical"
    original=work/"OriginalTable.java"
    original.write_text('''public class OriginalTable {
        public static void main(String[] args) throws Exception {
            for (String word:args) {
                int n=Integer.parseInt(word);
                try {
                    long old=before.ReferenceAPI.primary(n),now=ReferenceAPI.primary(n);
                    long a=before.ReferenceAPI.control(n),b=ReferenceAPI.control(n);
                    System.out.println("BOUND "+word+" "+old+" "+now+" "+a+" "+b+" "+ReferencePair.primary(n)+" "+ReferencePair.control(n)+" "+ReferencePair.inverse(n));
                } catch (Throwable t) {
                    System.out.println("THREW "+word+" "+t.getClass().getName());
                }
            }
        }
    }''')
    env.update(WIRE_ORIGINAL_BEFORE=classpath([target,*old]),WIRE_ORIGINAL_AFTER=classpath([target,*new]))
    compile_java([*bridges(work,[src]),HERE.parent/"wire-more/OriginalGraph.java",claim,original],harness,[],env)
    cmd=[JDK/"bin/java","-Xmx512m","-XX:-UsePerfData","-ea","-cp",harness,"OriginalTable",*map(str,seeds)]
    proc=subprocess.run(cmd,capture_output=True,env=env,text=True,timeout=45)
    (OUT/"physical.stdout").write_text(proc.stdout);(OUT/"physical.stderr").write_text(proc.stderr)
    data=[]
    for line in proc.stdout.splitlines():
        parts=line.split()
        if len(parts)==9 and parts[0]=="BOUND":
            data.append({"n":int(parts[1]),"old":int(parts[2]),"new":int(parts[3]),"oldControl":int(parts[4]),"newControl":int(parts[5]),
                "primary":parts[6]=="true","control":parts[7]=="true","inverse":parts[8]=="true"})
        if len(parts)==3 and parts[0]=="THREW":data.append({"n":int(parts[1]),"exception":parts[2]})
    return {"rows":data,"exit":proc.returncode,"argv":list(map(str,cmd)),"callerSha256":digest(target/"ReferenceAPI.class"),
            "accepted":proc.returncode==0 and [r['n'] for r in data]==seeds and all(r.get("primary")==True and r.get("control")==True and r.get("inverse")==False for r in data)}


def main(physical_only, *, native_only=False):
    spec=json.loads((SRC/"reference.json").read_bytes())
    packet=json.loads((INPUTS/"inputs.json").read_bytes())
    old,new=[graph(s,packet) for s in ("old","new")]
    work=Path.cwd();p=work/"original";p.mkdir()
    record={"status":"preparing","inputPacket":packet,"specSha256":digest(SRC/"reference.json")}
    write(record)
    try:
        record["originalJvm"]=physical(p,old,new,spec["seeds"])
        record["status"]="original JVM control passed" if record["originalJvm"]["accepted"] else "original JVM control mismatch"
        write(record)
        if physical_only or not record["originalJvm"]["accepted"]:return
        data=work/"pair";data.mkdir()
        cp,original,env,pin=prepare_pair(data,[SRC/"ReferenceAPI.java"],old,new,[SRC/"ReferencePair.java"],ordered=True)
        if pin["thinCallers"]["ReferenceAPI.class"]!=record["originalJvm"]["callerSha256"]:
            raise ValueError("two-copy caller differs from original")
        seeds=tuple((str(v),) for v in spec["seeds"])
        subject=Subject(0,"ReferencePair","two independent distribution classpaths",
            (Claim("primary","int n",holds=seeds),Claim("control","int n",holds=seeds),Claim("inverse","int n",holds=(),fails=seeds)),
            bound=8,unwind=16)
        a=data/"original-controls";b=data/"paired-controls";a.mkdir();b.mkdir()
        raw=jvm_controls(subject,a,original,env)
        if raw!=jvm_controls(subject,b,cp,env):raise ValueError("relocation disagrees on original controls")
        record.update(status="matched original and two-copy controls passed",twoCopy=pin)
        write(record)
        base={"jvm":raw,"rows":[],"inputPacket":packet,"scope":spec["domain"],"twoCopy":pin,"checkerSha256":digest(Path(os.environ["JVMCONTRACT"]))}
        measure_subject("blind",subject,"blind",data,env,cp,base,OUT/"comparison",False,original_cp=original,native_only=native_only)
        record["status"]="measured";write(record)
    except (subprocess.SubprocessError,ValueError,OSError,RuntimeError) as e:
        record.update(status="preparation or measurement incomplete",failure=repr(e))
        if getattr(e,"stderr",None):record["diagnostic"]=str(e.stderr)[-1500:]
        write(record)


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--physical-only",action="store_true")
    ap.add_argument("--native-only", action="store_true")
    args = ap.parse_args()
    main(args.physical_only, native_only=args.native_only)

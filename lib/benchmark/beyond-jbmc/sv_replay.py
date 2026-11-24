"""Replay the current stock public-program counterexamples on the unmodified corpus classes."""
import argparse,gzip,json,shutil
from pathlib import Path
import subprocess,zipfile,sys
from history import OUTPUT,HERE,encoded,digest,scratch
from sv_public import TREE,TASKS,check_source
from release_cases import JDK,javaenv,compile_java
from stock_history import classpath

def replay(base,out):
    records=[]
    for i,key in ((0,"B01"),(1,"B02"),(7,"B08")):
        directory=base/"opening/svcomp"/key
        record=json.loads(gzip.decompress((directory/"result.json.gz").read_bytes()))
        with zipfile.ZipFile(directory/"executions.zip") as z: raw=json.loads(z.read("stock/Main/stdout"))
        task=TASKS[i][0];src=TREE/"java"/task/"Main.java"
        with scratch(prefix="sv-stock-replay-") as tmp:
            work=Path(tmp);env=javaenv();dest=work/"classes"
            shim=work/"Verifier.java";shutil.copyfile(HERE/"sv/ReplayChoices.java.txt",shim)
            files=[src,shim,TREE/"java/common/org/sosy_lab/sv_benchmarks/ObjectFactory.java"]
            compile_java(files,dest,[],env)
            for block in raw:
                for prop in block.get("result",[]):
                    if prop.get("status")!="FAILURE" or not prop["property"].startswith("java::Main.main:") or ".assertion." not in prop["property"]:continue
                    trace=prop["trace"]
                    row={"case":key,"property":prop["property"],"assertionLine":prop["sourceLocation"].get("line"),
                         "sourceSha256":check_source(src),"traceInputSourceSha256":record["traceArchiveSha256"]}
                    choice=None
                    if key=="B01":choice="" # Main does not consume args or a nondeterministic value.
                    if key=="B02":
                        # The input String can be a distinct heap object. Decode only a trace that binds its complete contents.
                        refs=[s for s in trace if s.get("stepType")=="assignment"
                              and s.get("lhs") in ("s","str","input") and "String" in str(s.get("value",{}).get("type",""))]
                        if refs:
                            ptr=refs[0]["value"].get("data","")
                            cells={s["lhs"]:s.get("value",{}) for s in trace if s.get("stepType")=="assignment" and "lhs" in s}
                            value=cells.get(ptr+".length",{}).get("data")
                            if value=="0":choice="s"
                    if key=="B08":
                        declared=[s for s in trace if s.get("stepType")=="assignment" and s.get("lhs")=="n"
                                   and s.get("sourceLocation",{}).get("function","").startswith("java::Main.main:")]
                        if declared:choice="i"+str(int(declared[0]["value"]["data"]))
                    if choice is None:
                        row["disposition"]="stock witness not reconstructed"
                    else:
                        cmd=[JDK/"bin/java","-ea","-Xint","-Dsv.choices="+choice,"-cp",dest,"Main"]
                        p=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=25)
                        row.update(choices=choice,argv=list(map(str,cmd)),exit=p.returncode,stderr=p.stderr.strip())
                        loc="Main.main(Main.java:"+str(row["assertionLine"])+")"
                        row["disposition"]="stock counterexample confirmed" if p.returncode==1 and loc in p.stderr else "stock counterexample did not reproduce" if p.returncode==0 else "different original assertion"
                    records.append(row)
    out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(encoded(records))
    print([(r["case"],r["disposition"]) for r in records])

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--inputs",type=Path,default=OUTPUT)
    p.add_argument("--output",type=Path,default=OUTPUT/"opening/svcomp-stock-replays.json");a=p.parse_args();replay(a.inputs,a.output)

"""Adjudicate the frozen Sisu class-name witness and exercise the existing guarded pair route separately."""
import json
import os
from pathlib import Path
import subprocess
from matched_worker import SRC,OUT,INPUTS,graph
from release_cases import JDK,javaenv
from history import digest,encoded,benchmark
from stock_history import classpath
from auto_upgrade import extract

def main():
    work=Path.cwd();env=javaenv();pkt=json.loads((INPUTS/"inputs.json").read_bytes())
    graphs=[graph(k,pkt) for k in ("old","new")];receipt=json.loads((SRC/"witness.json").read_bytes())
    source=SRC/"PublicCaller.java"
    caller=work/"caller";caller.mkdir()
    subprocess.run([JDK/"bin/javac","-proc:none","-parameters","-g","-cp",classpath(graphs[0]),"-d",caller,source],env=env,check=True)
    if digest(caller/"PublicCaller.class")!=receipt["callerSha256"]:raise ValueError("assistant diagnostic changed the generated caller")
    runner=work/"BothInputs.java";runner.write_text("""public class BothInputs { public static void main(String[] a) throws Throwable {
        for(boolean b:new boolean[]{false,true}) System.out.println(PublicCaller.observe(b));
    }}""")
    helpers=work/"physical";helpers.mkdir()
    subprocess.run([JDK/"bin/javac","-proc:none","-d",helpers,"-cp",classpath([caller,*graphs[0]]),runner],env=env,check=True)
    actual=[];roots=[]
    for label,jars in zip(("old","new"),graphs):
        cmd=[JDK/"bin/java","-ea","-cp",classpath([helpers,caller,*jars]),"BothInputs"]
        original=subprocess.check_output(cmd,env=env,text=True).splitlines()
        if original!=receipt["original"][label]:raise ValueError("original Boolean domain disagrees")
        actual.append(original)
        root=work/label;extract(jars[0],root)
        (root/"PublicCaller.class").write_bytes((caller/"PublicCaller.class").read_bytes())
        roots.append(root)
    if actual[0]!=actual[1]:raise ValueError("frozen alleged change genuinely affects the JVMs")
    checker=os.environ["JVMCONTRACT"];after=work/"paired-guard"
    cmd=[checker,"equivalence","--before",str(roots[0]),"--after",str(roots[1]),"--before-classpath",classpath(graphs[0][1:]),
         "--classpath",classpath(graphs[1][1:]),"--target","PublicCaller#observe","--assume","true","--engine","native",
         "--gaps","strict","--unwind","16","--max-array-length","8","--timeout","120","--json","--work",str(after)]
    result=benchmark.measure(cmd,180);row=benchmark.outcome_of({"kind":"regression"},result["stdout"]) or {}
    (OUT/"guarded.stdout").write_text(result["stdout"]);(OUT/"guarded.stderr").write_text(result["stderr"])
    (OUT/"report.json").write_bytes(encoded({"phase":"assisted after locked first pass","originalJvm":actual,"sourceSha256":digest(source),
        "callerSha256":receipt["callerSha256"],"originalWitness":receipt,"guardedArgv":cmd,"verdict":row.get("verdict"),
        "problem":row.get("problem"),"counterexample":row.get("counterexample"),"stated":row.get("stated"),
        "cost":{k:result[k] for k in ("seconds","cpuSeconds","peakMB","exit","killed")}}))
    print(row.get("verdict"),"for the unchanged reference on the guarded route")

if __name__=="__main__":main()

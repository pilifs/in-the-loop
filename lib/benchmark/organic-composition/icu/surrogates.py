"""Measure the original surrogate helper over all UTF-16 units on both production graphs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
CASE=Path(__file__).resolve().parent
sys.path.insert(0,str(CASE.parent))
from plan_run import ROOT, JDK, OUTPUT
sys.path.insert(0,str(ROOT/"examples/tools"))
from targets import change_helpers, runtime_jar

def main():
    outputs={}
    for side in ("old","new"):
        m=json.loads((CASE/side/"prepared.json").read_bytes());jar=Path(m["classpath"][0]["file"])
        if hashlib.sha256(jar.read_bytes()).hexdigest()!=m["classpath"][0]["sha256"]:raise ValueError("wrong production JAR")
        data=runtime_jar.read_class(jar,"com/ibm/icu/text/UTF16");pool,methods,_=runtime_jar._declarations(data,with_code=True)
        flags,code,handlers=methods["isTrailSurrogate","(I)Z"]
        if flags!=9 or handlers or not change_helpers.local_integral_body(code,pool):raise ValueError("helper uses external state")
        parameter=runtime_jar.parameter_names(data,"isTrailSurrogate","(I)Z")[0][0]
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);source=p/"Units.java"
            source.write_text("import com.ibm.icu.text.UTF16; public class Units { public static void main(String[] a) {"
                    "int yes=0; for(int c=0;c<65536;c++){boolean b=UTF16.isTrailSurrogate(c);"
                    "if(b!=(c>=0xdc00 && c<=0xdfff))throw new AssertionError(c); if(b)yes++;} System.out.println(yes);}}")
            subprocess.run([JDK/"bin/javac","-proc:none","-cp",jar,"-d",p,source],check=True)
            count=int(subprocess.check_output([JDK/"bin/java","-cp",str(p)+os.pathsep+str(jar),"Units"],text=True).strip())
            if count!=1024:raise ValueError("incorrect trail-surrogate extent")
        cmd=[os.environ.get("JVMCONTRACT",str(ROOT/"lib/target/release/jvmcontract")),"prove","--classes",str(jar),
             "com.ibm.icu.text.UTF16#isTrailSurrogate","--assume",f"{parameter} >= 0 && {parameter} <= 65535",
             "--assert",f"result == ({parameter} >= 56320 && {parameter} <= 57343)","--engine","native","--timeout","90","--json"]
        q=subprocess.run(cmd,capture_output=True,text=True,timeout=115,env={**os.environ,"JAVA_HOME":str(JDK),"PATH":str(JDK/"bin")+os.pathsep+os.environ["PATH"]})
        if not q.stdout.strip():raise ValueError("no native helper report: "+q.stderr[:300])
        outputs[side]={"jar":m["classpath"][0]["sha256"],"class":hashlib.sha256(data).hexdigest(),"code":code.hex(),
                       "normalReturns":65536,"trueCount":count,"argv":cmd,"exit":q.returncode,"native":json.loads(q.stdout)}
    path=ROOT/OUTPUT/"icu"/"surrogates.json";path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(outputs,indent=2)+"\n")
if __name__=="__main__":main()

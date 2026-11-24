"""Replay the same resource observation with a noncolliding parameter and an equivalent source-level year guard."""
import gzip
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
from history import HERE,ROOT,OUTPUT,encoded,digest,scratch
from release_cases import JDK,compile_java,javaenv,jars_for
from stock_history import classpath
from zone_reuse import measure,OLD,NEW

if __name__=="__main__":
    with scratch(prefix="zone-equality-") as tmp:
        w=Path(tmp);classes=w/"new";old=w/"old"
        env=javaenv();os.environ.update({k:env[k] for k in ("JAVA_HOME","PATH","JVMCONTRACT_JAR_RELEASE")})
        source=HERE/"extended/ZoneResourceEquality.java";a,b=jars_for(OLD),jars_for(NEW)
        compile_java([source],classes,a,env);shutil.copytree(classes,old)
        driver=w/"OffsetWitness.java"
        driver.write_text("""public class OffsetWitness { public static void main(String[] args) {
            long t=Long.parseLong(args[0]);System.out.println(ZoneResourceEquality.mexico(t)+" "+ZoneResourceEquality.control(t)+" "+
                ZoneResourceEquality.boundedMexico(t)+" "+ZoneResourceEquality.boundedControl(t));
        }}""");helper=w/"witness";compile_java([driver],helper,[classes,*a],env)
        t="1681560000000"
        controls=[]
        for jars in (a,b):
            cmd=[JDK/"bin/java","-ea","-Duser.timezone=UTC","-cp",classpath([helper,classes,*jars]),"OffsetWitness",t]
            controls.append(subprocess.check_output(cmd,text=True,env=env).strip())
        if controls!=["-18000000 -25200000 -18000000 -25200000","-21600000 -25200000 -21600000 -25200000"]:
            raise ValueError("original offset discrimination differs")
        checker=Path(os.environ["JVMCONTRACT"]).resolve()
        out=OUTPUT/"qualified/C06-C07-equality";out.mkdir(parents=True,exist_ok=True)
        results=[]
        with zipfile.ZipFile(out/"executions.zip","w",zipfile.ZIP_DEFLATED) as z:
            for m in ("mexico","control","boundedMexico","boundedControl"):
                cmd=[str(checker),"equivalence","--before",str(old),"--after",str(classes),
                     "--before-classpath",classpath(a),"--classpath",classpath(b),"--target","ZoneResourceEquality#"+m,
                     "--engine","native","--gaps","strict","--unwind","16","--max-array-length","8","--timeout","120","--work",str(w/m),"--json"]
                if not m.startswith("bounded"):cmd+=["--assume","instant >= 1672531200000L && instant < 1704067200000L"]
                results.append(dict(measure(checker,cmd,z,m),method=m))
        (out/"result.json.gz").write_bytes(gzip.compress(encoded({"job":os.environ.get("VERIFY_JOB_ID"),"sourceSha256":digest(source),
            "classpathSha256":[digest(a[0]),digest(b[0])],"input":t,"originalOffsets":controls,"rows":results}),mtime=0))
        print([(r["method"],r["verdict"]) for r in results],flush=True)

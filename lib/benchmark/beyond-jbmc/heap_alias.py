"""Repeat the two supplied-array questions on native's explicitly admitted a==b branch."""
import gzip,json,os,subprocess
from pathlib import Path
import zipfile
from history import HERE,ROOT,OUTPUT,scratch,benchmark,digest,encoded
from release_cases import jars_for,compile_java,javaenv,JDK
from stock_history import classpath

if __name__=="__main__":
    with scratch(prefix="declared-array-alias-") as tmp:
        work=Path(tmp);env=javaenv();os.environ.update({k:env[k] for k in ("JAVA_HOME","PATH","JVMCONTRACT_JAR_RELEASE")})
        classes=work/"classes";jars=jars_for("commons-lang3-3.17.0")
        source=HERE/"extended/SuppliedRoots.java"
        compile_java([source],classes,jars,env)
        check=work/"SharedCheck.java"
        check.write_text("""public class SharedCheck { public static void main(String[] args) {
            SuppliedRoots.Flat[] a={new SuppliedRoots.Flat(),new SuppliedRoots.Flat()};
            if(!SuppliedRoots.conditional(a,a) || SuppliedRoots.unconditional(a,a))throw new AssertionError();
            System.out.println("same array: conditional held and unconditional frame refuted");
        }}""")
        helper=work/"original";compile_java([check],helper,[classes,*jars],env)
        witness=subprocess.check_output([JDK/"bin/java","-ea","-cp",classpath([helper,classes,*jars]),"SharedCheck"],env=env,text=True).strip()
        out=OUTPUT/"qualified/H11-may-alias";out.mkdir(parents=True,exist_ok=True)
        results=[];checker=Path(os.environ["JVMCONTRACT"]).resolve()
        with zipfile.ZipFile(out/"executions.zip","w",zipfile.ZIP_DEFLATED) as z:
            for m in ("conditional","unconditional"):
                cmd=[str(checker),"prove","SuppliedRoots#"+m,"--classes",str(classes),"--classpath",classpath(jars),
                     "--assert","result","--may-alias","a,b","--gaps","strict","--engine","native","--unwind","16",
                     "--max-array-length","3","--timeout","120","--work",str(work/m),"--json"]
                q=benchmark.measure(cmd,180);row=benchmark.outcome_of({"kind":"property"},q["stdout"]) or {}
                for s in ("stdout","stderr"):z.writestr(m+"/"+s,q[s])
                results.append({"method":m,"argv":cmd,"verdict":row.get("verdict"),"counterexample":row.get("counterexample"),
                                "stated":row.get("stated"),"problem":row.get("problem")})
        (out/"results.json").write_bytes(encoded({"job":os.environ.get("VERIFY_JOB_ID"),"sourceSha256":digest(source),
             "arrays":"explicitly permitted to be the same array on native","originalJvm":witness,"runs":results}))
        print(witness,[(r["method"],r["verdict"]) for r in results],flush=True)

"""Run the unmodified upstream JUnit methods after sealing the URL-only case and its first result."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

CASE=Path(__file__).resolve().parent
sys.path.insert(0,str(CASE.parent))
from plan_run import JDK, ROOT, OUTPUT
JDK8=Path.home()/".sdkman/candidates/java/8.0.512.0+9-tem"
METHODS={"JSONArrayTest":{"testObjectConstructor":"new","testJSONArrayConstructor":"new","testJSONArrayPutAll":"new",
                         "write":"existing, rearranged in PR","verifyPutAll":"pre-existing collection/array control"},
         "JSONObjectTest":{"testIssue548ObjectWithEmptyJsonArray":"new"}}
RUNNER="""import org.junit.runner.*;
import org.junit.runner.notification.Failure;
public final class OriginalJUnitMethods {
  public static void main(String[] args) throws Exception {
    for (String spec : args) {
      String[] parts = spec.split("#");
      Result result = new JUnitCore().run(Request.method(Class.forName("org.json.junit."+parts[0]),parts[1]));
      String kind = result.wasSuccessful() ? "passed" : result.getFailures().get(0).getException().getClass().getName();
      System.out.println("ORIGINAL-JUNIT " + spec + "\\t" + result.getRunCount() + "\\t" + result.getFailureCount() + "\\t" + kind);
    }
  }
}
"""

def sha(data):return hashlib.sha256(data).hexdigest()

def main():
    source=json.loads((CASE/"sources.json").read_bytes());pre=json.loads((CASE/"before-reference.json").read_bytes())
    for name,h in pre["evidence"].items():
        if sha((ROOT/name).read_bytes())!=h:raise ValueError("preregistered case differs before upstream comparison")
    m=json.loads((CASE/"test-prepared.json").read_bytes());deps=[]
    for d in m["classpath"]:
        f=Path(d["file"])
        if sha(f.read_bytes())!=d["sha256"]:raise ValueError("changed test-only dependency")
        deps.append(str(f))
    mirror=Path(source["sides"]["new"]["jar"]["file"]).parent/"source.git"
    def git(*args):return subprocess.check_output(["git","-C",mirror,*args])
    rev=source["merge"]; names=git("ls-tree","-r","--name-only","-z",rev,"src/test/java","src/test/resources").split(b"\0")
    hashes={};records={};methods=[k+"#"+method for k,group in METHODS.items() for method in group]
    with tempfile.TemporaryDirectory(prefix="original-junit-") as t:
        root=Path(t);classes=root/"classes";classes.mkdir();java_files=[]
        for raw in names:
            if not raw:continue
            name=raw.decode();data=git("show",rev+":"+name)
            if name.startswith("src/test/java/") and name.endswith(".java"):
                dest=root/name;java_files.append(str(dest));hashes[name]=sha(data)
            elif name.startswith("src/test/resources/"):dest=classes/name.removeprefix("src/test/resources/")
            else:continue
            dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        runner=root/"OriginalJUnitMethods.java";runner.write_text(RUNNER)
        fixed=source["sides"]["new"]["jar"]["file"]
        compile_cmd=[str(JDK8/"bin/javac"),"-source","1.6","-target","1.6","-g","-proc:none","-encoding","UTF-8",
                     "-classpath",os.pathsep.join([fixed,*deps]),"-d",str(classes),*java_files,str(runner)]
        build=subprocess.run(compile_cmd,capture_output=True,text=True,timeout=60)
        if build.returncode:raise ValueError("original test compilation failed: "+build.stderr[-1100:])
        for side in ("old","new"):
            jar=source["sides"][side]["jar"]
            if sha(Path(jar["file"]).read_bytes())!=jar["sha256"]:raise ValueError("changed production JAR")
            for jdk in (JDK8,JDK):
                cmd=[str(jdk/"bin/java"),"-Xmx192m","-Duser.timezone=UTC","-Duser.language=en","-Duser.country=US",
                     "-cp",os.pathsep.join([str(classes),jar["file"],*deps]),"OriginalJUnitMethods",*methods]
                p=subprocess.run(cmd,capture_output=True,text=True,timeout=60,check=True)
                got={}
                for line in p.stdout.splitlines():
                    if not line.startswith("ORIGINAL-JUNIT "):continue
                    name,count,fail,kind=line.removeprefix("ORIGINAL-JUNIT ").split("\t")
                    if count!="1":raise ValueError("not exactly one original test method")
                    got[name]={"failures":int(fail),"outcome":kind}
                if set(got)!=set(methods):raise ValueError("incomplete upstream test outcomes")
                records[side+"/"+jdk.name]=got
    out=ROOT/OUTPUT/"url-only/upstream-reference.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    stored={}
    with zipfile.ZipFile(out.parent/"original-production.zip","w",zipfile.ZIP_DEFLATED) as z:
        for side,ref in source["sides"].items():
            artifact=Path(ref["jar"]["file"]).read_bytes()
            if sha(artifact)!=ref["jar"]["sha256"]:raise ValueError("changed production artifact")
            license_text=git("show",ref["commit"]+":LICENSE")
            for name,data in [(side+"/production.jar",artifact),(side+"/LICENSE",license_text)]:
                info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
                z.writestr(info,data);stored[name]=sha(data)
    out.write_text(json.dumps({"preReferenceSnapshot":pre,"upstream":source["url"],"testSource":rev,"unchangedTestSourceHashes":hashes,
             "originalMethods":METHODS,"retainedProductionAndLicenses":stored,"sourceAndTarget":"1.6","testOnlyDependencies":m["classpath"],"results":records,
             "referenceGrade":"Tests and discussion did not supply the preregistered query or first result. Added upstream tests exercise object-array construction, a new JSONArray copy constructor and overload, and an empty-array parse. The two-stage nested alias and partial non-finite batch with post-failure recovery are separate public histories."},indent=2)+"\n")
    new_overloads={"JSONArrayTest#testJSONArrayConstructor","JSONArrayTest#testJSONArrayPutAll"}
    for profile,methods_run in records.items():
        for name,observed in methods_run.items():
            expected="java.lang.NoSuchMethodError" if profile.startswith("old/") and name in new_overloads else "passed"
            if observed["outcome"]!=expected or observed["failures"]!=int(expected!="passed"):
                raise ValueError("unexpected upstream comparison: "+profile+"/"+name)
    print({k:sum(r["outcome"]=="passed" for r in v.values()) for k,v in records.items()})
if __name__=="__main__":main()

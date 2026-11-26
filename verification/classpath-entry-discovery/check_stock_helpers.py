"""Check the raw stock command on an active versioned helper and on its unchanged earlier shadow."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"lib/benchmark/classpath-entry-discovery"))
from controls import CHECKER, JDK, compile_sources, jar, java
from targets import change_evidence


def run(output):
    rows = []
    with tempfile.TemporaryDirectory(prefix="stock-helper-") as tmp:
        work = Path(tmp)
        def helper(value):
            return compile_sources(work/("value-"+str(value)), {"Helper":f"public class Helper {{public static int value() {{return {value};}}}}"})
        base, high, ordinary = (helper(i) for i in (3, 5, 7))
        versioned = jar(work/"variants.jar", {**base,"META-INF/versions/21/Helper.class":high["Helper.class"]},"Multi-Release: true")
        shadow = jar(work/"shadow.jar", ordinary)
        main = {"Caller":"public class Caller {public static int read(){return Helper.value();} public static void main(String[] args){System.out.print(read());}}"}
        build = work/"caller"
        classes = compile_sources(build,main,[versioned])
        caller = jar(work/"caller.jar",classes)
        env = {**os.environ,"JAVA_HOME":str(JDK),"JVMCONTRACT_JAR_RELEASE":"21"}
        for mode, files, original in (("active",[caller,versioned],5),("shadowed",[caller,shadow,versioned],7)):
            if int(java(files,"Caller")) != original:
                raise ValueError("original helper observation differs")
            for engine in ("native","jbmc"):
                for asserted in (original, 3):
                    cmd = [CHECKER,"prove","Caller#read()I","--engine",engine,"--gaps","strict","--classes",files[0],
                           "--classpath",os.pathsep.join(map(str,files[1:])),"--assert",f"result == {asserted}","--json"]
                    result = subprocess.run(cmd,cwd=work,env=env,text=True,capture_output=True,timeout=60)
                    trial, = json.loads(result.stdout)
                    expected = ("unverifiable" if engine=="jbmc" and mode=="active" else
                                "verified" if asserted == original else "violation")
                    if trial["verdict"]!=expected or (expected=="unverifiable" and "Helper.class" not in result.stdout):
                        raise ValueError(f"{mode}/{engine}: expected {expected} for {asserted}: {result.stdout[-800:]}")
                    rows.append({"profile":mode,"engine":engine,"target":"Caller#read()I","originalJvm":original,
                                 "asserted":asserted,"verdict":trial["verdict"],"exit":result.returncode})
        other = work/"other"
        compile_sources(other,main,[versioned])
        cmd = [CHECKER,"equivalence","--before",build/"classes","--after",other/"classes","--target","Caller#read()I",
               "--classpath",versioned,"--engine","jbmc","--gaps","strict","--json"]
        proc = subprocess.run(cmd,cwd=work,env=env,text=True,capture_output=True,timeout=60)
        result, = json.loads(proc.stdout)
        if result["verdict"]!="unverifiable" or "Helper.class" not in proc.stdout:
            raise ValueError("paired stock launch bypassed the active helper guard")
        rows.append({"profile":"two revisions","engine":"jbmc","target":"Caller#read()I","verdict":result["verdict"],
                     "firstOpenDependency":"versioned Helper.class in the ordered library"})
    change_evidence.write_json(output,rows)
    print("Active stock property and equivalence routes refused; native and earlier-shadow controls matched the JVM")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output",type=Path)
    run(parser.parse_args().output)

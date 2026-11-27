"""Exercise physically qualified stock proofs with original multi-release subjects, helpers and an earlier winner."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT/"lib/benchmark/classpath-entry-discovery"))
from controls import CHECKER, compile_sources, jar
from targets import runtime_jdk, stock_projection, upgrade_replay


def fixture(work):
    def program(value):
        return {c:"public class "+c+" {public static int value(){return "+str(value)+";}}" for c in ("Gate","Helper")}
    base=compile_sources(work/"base",program(3))
    high=compile_sources(work/"high",program(5))
    versioned=jar(work/"versions.jar",{**base,**{"META-INF/versions/21/"+n:v for n,v in high.items()}},"Multi-Release: true")
    caller=compile_sources(work/"caller",{"Caller":"public class Caller { public static int read(){return Helper.value();}"
                          " public static void main(String[] a){System.out.print(Gate.value()+\"/\"+read());}}"},[versioned])
    application=jar(work/"caller.jar",caller)
    shadow=jar(work/"shadow.jar",compile_sources(work/"shadow",{"Helper":"public class Helper {public static int value(){return 7;}}"}))
    return application,versioned,shadow


def original(checker,stock,work):
    client,versioned,shadow=fixture(work)
    jdk21=Path(runtime_jdk.home(21))
    profiles=[("base-8",Path(runtime_jdk.home(8)),[client,versioned],3,3),("base-17",Path(runtime_jdk.home(17)),[client,versioned],3,3),
              ("active-21",jdk21,[client,versioned],5,5),("earlier-shadow",jdk21,[client,shadow,versioned],5,7)]
    evidence={}
    for label,jdk,files,gate,helper in profiles:
        cp=os.pathsep.join(map(str,files))
        observed=subprocess.check_output([jdk/"bin/java","-cp",cp,"Caller"],text=True)
        if observed!=f"{gate}/{helper}":raise ValueError("unexpected original release selection")
        proofs=[]
        for entry,actual in (("Gate#value()I",gate),("Caller#read()I",helper)):
            for expected in (actual,5 if actual==3 else 3):
                folder=work/f"{label}-{entry.partition('#')[0]}-{expected}"
                folder.mkdir()
                row=stock_projection.check(files,jdk,entry,expected,checker,stock,folder)
                if row["verdict"]!=("verified" if actual==expected else "violation"):raise ValueError("unexpected bound stock verdict")
                proofs.append(row)
        evidence[label]={"originalJvm":observed,"proofs":proofs}
    selected=evidence["active-21"]["proofs"][2]
    if selected["members"]["Helper#value()I"]["physicalEntry"]!="META-INF/versions/21/Helper.class":
        raise ValueError("wrong active helper binding")
    if evidence["earlier-shadow"]["proofs"][2]["members"]["Helper#value()I"]["providerIndex"]!=1:
        raise ValueError("earlier helper failed to win")
    corrupted=copy.deepcopy(selected["executions"])
    for call in corrupted:
        call["classAccess"]["Helper"]["read"]=False
    try:
        stock_projection.deciding_calls(corrupted,selected["verdict"],{"Caller","Helper"})
    except ValueError as err:
        no_read=str(err)
    else:
        raise ValueError("absence of physical helper consumption was accepted")
    wrong=work/"wrong-binding";wrong.mkdir()
    expected={m.split("#")[0]:r["classSha256"] for m,r in selected["members"].items()}
    expected["Helper"]="0"*64
    try:
        stock_projection.check([client,versioned],jdk21,"Caller#read()I",5,checker,stock,wrong,expected=expected)
    except ValueError as err:
        wrong_binding=str(err)
    else:
        raise ValueError("a different physical helper obtained stock credit")
    other = work/"paired-caller"
    compile_sources(other, {"Caller":(work/"caller/Caller.java").read_text()}, [versioned])
    env={**os.environ,"JAVA_HOME":str(jdk21),"JVMCONTRACT_JAR_RELEASE":"21"}
    raw_checks={"raw direct":[checker,"prove","Gate#value()I","--classes",versioned,"--assert","result == 5"],
                "raw paired":[checker,"equivalence","--before",work/"caller/classes","--after",other/"classes","--target","Caller#read()I","--classpath",versioned]}
    refusals={}
    for label,cmd in raw_checks.items():
        proc=subprocess.run([*cmd,"--engine","jbmc","--gaps","strict","--json"],env=env,capture_output=True,text=True,timeout=80)
        row,=json.loads(proc.stdout)
        if row["verdict"]!="unverifiable" or "multi-release" not in proc.stdout:
            raise ValueError("an unqualified raw or paired classpath bypassed its binding refusal: "+proc.stdout[-550:])
        refusals[label]=row.get("problem") or row.get("output")
    return {"schema":"qualified-stock-multi-release/v1","profiles":evidence,
            "negative":{"missingRead":no_read,"wrongBinding":wrong_binding,**refusals}}


if __name__=="__main__":
    import shutil
    with tempfile.TemporaryDirectory(prefix="qualified-stock-mr-") as scratch:
        data=original(Path(os.environ.get("JVMCONTRACT",CHECKER)),Path(shutil.which("jbmc")),Path(scratch))
        with zipfile.ZipFile(HERE/"stock-profiles.zip","w",zipfile.ZIP_DEFLATED) as z:
            z.writestr("profiles.json",json.dumps(data,indent=2)+"\n")
        print("Sixteen stock property checks, original JVM parity, subject/helper byte reads and paired refusal verified")


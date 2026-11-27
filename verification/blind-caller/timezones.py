"""Check process-default copy semantics, profile rejection and the original Log4j scheduling queries."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/"examples/tools"))
from targets import change_evidence,upgrade_replay

JDK=Path.home()/".sdkman/candidates/java/21.0.13.0+9-tem"
CHECKER=Path(os.environ.get("JVMCONTRACT",ROOT/"lib/target/release/jvmcontract"))
CASE=ROOT/"lib/benchmark/organic-composition/log4j"
ZONES=("GMT+10:00","GMT-10:00")


def proof(folder, classes, entry, wanted, *, jars=(), zone=None, expect=None, revision=None):
    folder.mkdir()
    cmd=[CHECKER,"prove",entry,"--classes",classes,"--engine","native","--gaps","strict","--assert",wanted,
         "--unwind","16","--timeout","60","--work",folder,"--json"]
    if jars:
        cmd.extend(["--classpath",os.pathsep.join(map(str,jars))])
    if zone:
        profile={"fixedZone":zone}
        if expect:profile["expectedZoneReceipt"]=expect
        if revision:profile["startupRevision"]=revision
        cmd.extend(["--observed-initializer",entry.partition("#")[0],"--observed-runtime",json.dumps(profile)])
    env={"JAVA_HOME":str(JDK),"PATH":str(JDK/"bin")+":/usr/bin:/bin","LC_ALL":"C.UTF-8","JVMCONTRACT_JAR_RELEASE":"21"}
    proc=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=120)
    if not proc.stdout.strip():
        return {"verdict":"unverifiable","problem":proc.stderr.strip(),"receipts":[],"consumed":[]}
    row,=json.loads(proc.stdout)
    row["receipts"]=[json.loads(p.read_bytes()) for p in (folder/"startup-receipts").glob("*.json")]
    row["consumed"]=[a["id"] for a in (row.get("stated") or {}).get("assumptions",[]) if a.get("id")]
    return row


def qualify(work):
    classes=work/"fixture"
    classes.mkdir()
    subprocess.run([JDK/"bin/javac","-proc:none","-g","-d",classes,HERE/"timezone/ProcessZone.java"],check=True)
    result={"schema":"process-zone-qualification/v1","jdkReleaseSha256":upgrade_replay.sha(JDK/"release"),
            "fixtureClassSha256":upgrade_replay.sha(classes/"ProcessZone.class"),"fixture":{},"log4j":{}}
    for i,zone in enumerate(ZONES):
        plain=subprocess.check_output([JDK/"bin/java","-Duser.timezone="+zone,"-cp",classes,"ProcessZone"],text=True).strip()
        offset=36000000 if i==0 else -36000000
        if plain != f"{zone} {offset} true {offset}":raise ValueError("original default clone or restoration differs")
        measured=proof(work/f"offset-{i}",classes,"ProcessZone#offset()I","result == 36000000",zone=zone)
        isolation=proof(work/f"copies-{i}",classes,"ProcessZone#isolateAndRestore()Z","result == true",zone=zone)
        if measured["verdict"] != ("verified" if i==0 else "violation") or isolation["verdict"]!="verified":
            raise ValueError(str([measured.get("problem"),isolation.get("problem")]))
        if not any(v.startswith("process-zone:") for v in isolation["consumed"]):
            raise ValueError("original default evidence was not consumed")
        result["fixture"][zone]={"original":plain,"offset":measured,"copies":isolation}
    plus=result["fixture"][ZONES[0]]["offset"]["receipts"][0]["id"]
    replaced=proof(work/"replace-first",classes,"ProcessZone#replaceBeforeRead()Z","result == true",zone=ZONES[1])
    if replaced["verdict"]!="verified" or any(v.startswith("process-zone:") for v in replaced["consumed"]):
        raise ValueError("an overwritten initial default was credited")
    swapped=proof(work/"crossed",classes,"ProcessZone#offset()I","result == 36000000",zone=ZONES[1],expect=plus)
    if swapped["verdict"]!="unverifiable" or "receipt differs" not in str(swapped.get("problem")):
        raise ValueError("a swapped process profile was admitted")
    reset=proof(work/"reset",classes,"ProcessZone#resetToHost()I","result == 0",zone=ZONES[0])
    if reset["verdict"]!="unverifiable":raise ValueError("unqualified host reset produced a verdict")
    result.update(replacedBeforeRead=replaced,swappedProfile=swapped,resetToHost=reset)
    archived=json.loads((ROOT/"verification/organic-composition/log4j/processes.json").read_bytes())
    registration=json.loads((CASE/"registration.json").read_bytes())
    if any(upgrade_replay.sha(CASE/file)!=pin for file,pin in registration["inputs"].items()):
        raise ValueError("historical Log4j registration differs")
    launcher=work/"ZoneSchedule.java"
    launcher.write_text("""import java.util.TimeZone; public class ZoneSchedule { public static void main(String[] args) {
      if (!TimeZone.getDefault().getID().equals(args[0])) throw new AssertionError();
      System.out.println("SCHEDULE " + UpgradeProbe.observe(args));
      if (!TimeZone.getDefault().getID().equals(args[0])) throw new AssertionError();
    }}""")
    actual={}
    for side in ("old","new"):
        graph=json.loads((CASE/side/"prepared.json").read_bytes())
        jars=[Path(r["file"]) for r in graph["classpath"]]
        if [upgrade_replay.sha(p) for p in jars] != [r["sha256"] for r in graph["classpath"]]:
            raise ValueError("the original API/core order or bytes changed")
        adapter=work/side
        adapter.mkdir()
        cp=os.pathsep.join(map(str,jars))
        subprocess.run([JDK/"bin/javac","-proc:none","-d",adapter,"-cp",cp,CASE/"UpgradeProbe.java"],check=True)
        runner=work/(side+"-plain")
        runner.mkdir()
        subprocess.run([JDK/"bin/javac","-proc:none","-d",runner,"-cp",str(adapter)+os.pathsep+cp,launcher],check=True)
        cp=os.pathsep.join(map(str,[runner,adapter,*jars]))
        histories=[]
        for row in [r for r in archived if r["side"]==side]:
            cmd=[JDK/"bin/java","-Xmx256m","-Duser.timezone="+row["processDefault"],"-Duser.language=en",
                 "-Duser.country=US","-verbose:class","-cp",cp,"ZoneSchedule",*row["args"]]
            outputs=[]
            for _ in range(2):
                text=subprocess.check_output(cmd,text=True,stderr=subprocess.STDOUT,timeout=20)
                origins=upgrade_replay.class_origins(text)
                if any(origins.get(owner)!={jars[1]} for owner in row["loadedFromCore"]):
                    raise ValueError("an executed Log4j class came from a different provider")
                outputs.append(next(l.removeprefix("SCHEDULE ") for l in text.splitlines() if l.startswith("SCHEDULE ")))
            if outputs!=row["observations"]:raise ValueError("original scheduling history differs")
            histories.append({"input":row["args"],"original":outputs})
            actual.setdefault(tuple(row["args"]),{})[side]=outputs[0]
        base=proof(work/(side+"-strict"),adapter,"UpgradeProbe#schedule()Z","result == true",jars=jars)
        if base["verdict"]!="unverifiable" or "TimeZone.getDefault" not in str(base.get("problem")):
            raise ValueError("unprofiled first stop changed")
        conditional=proof(work/(side+"-fixed"),adapter,"UpgradeProbe#schedule()Z","result == true",jars=jars,zone=ZONES[0],revision=graph["commit"])
        if conditional["verdict"]=="unverifiable" and ("TimeZone.getDefault" in str(conditional.get("problem"))
                or not conditional["receipts"]):
            raise ValueError("the original schedule did not pass its registered timezone refusal: "+str(conditional.get("problem")))
        result["log4j"][side]={"orderedClasspath":graph["classpath"],"revision":graph["commit"],"original":histories,
                               "unprofiled":base,"fixedProfile":conditional,"callerSha256":upgrade_replay.sha(adapter/"UpgradeProbe.class")}
    dispositions=[{"input":list(k),"preservation":"established" if v["old"]==v["new"] else "refuted"} for k,v in actual.items()]
    if len(dispositions)!=8 or any((r["input"][1]=="explicit")!=(r["preservation"]=="refuted") for r in dispositions):
        raise ValueError("the four explicit counterexamples or omitted-zone controls changed")
    result["finite"]=dispositions
    with zipfile.ZipFile(HERE/"process-zones.zip","w",zipfile.ZIP_DEFLATED) as out:
        out.writestr("qualification.json",json.dumps(result,indent=2)+"\n")
    print("Both original defaults, isolation, change and restore, crossed-profile refusal and eight original Log4j histories qualified")


if __name__=="__main__":
    with tempfile.TemporaryDirectory(prefix="original-process-zone-") as temp:
        qualify(Path(temp))

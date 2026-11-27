"""Trace a reviewed, ordinary upstream unit method on a frozen, closed data operation."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from targets import blind_prediction as prediction, change_inventory, entry_discovery, observer_scalar, public_histories, runtime_jdk, upgrade_replay

HERE = Path(__file__).resolve().parent
PLATFORM = """import org.junit.platform.engine.TestExecutionResult;
import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.junit.platform.launcher.*;
import org.junit.platform.launcher.core.*;
public class OriginalUnit {
 public static void main(String[] args) {
  LauncherDiscoveryRequest req=LauncherDiscoveryRequestBuilder.request().selectors(DiscoverySelectors.selectMethod(args[0],args[1])).build();
  Launcher runner=LauncherFactory.create();
  runner.registerTestExecutionListeners(new TestExecutionListener() {
   public void executionFinished(TestIdentifier test, TestExecutionResult result) {
    if (test.isTest()) System.out.println("ORIGINAL-UNIT "+test.getUniqueId()+" "+result.getStatus()+" "+
       result.getThrowable().map(t -> t.getClass().getName()).orElse("-"));
   }});
  runner.execute(req);
 }
}"""
JUNIT4 = """import org.junit.runner.*;
import org.junit.runner.notification.Failure;
public class OriginalUnit {
 public static void main(String[] args) throws Exception {
  Result result=new JUnitCore().run(Request.method(Class.forName(args[0]),args[1]));
  if (result.getRunCount()!=1) throw new IllegalStateException("expected one original test method");
  System.out.println("ORIGINAL-UNIT "+args[0]+"#"+args[1]+" "+result.wasSuccessful());
  for (Failure f : result.getFailures()) System.out.println("ORIGINAL-UNIT "+f.getException().getClass().getName());
 }
}"""


def safe_changed(root, packet, feature):
    sources = prediction.visible_sources(root,packet)
    sides = {s:prediction.definitions(root,packet[s]["classpath"],sources,feature) for s in ("old","new")}
    targets = []
    for owner in sorted(sides["old"].keys() & sides["new"].keys()):
        old,new = (sides[s][owner][0] for s in ("old","new"))
        before,after = (entry_discovery.fingerprints(d) for d in (old,new))
        for method,desc in sorted(before.keys() & after.keys()):
            args,returned = observer_scalar.parts(desc)
            if (method not in {"<init>","<clinit>"} and returned in observer_scalar.TYPES
                    and all(t in observer_scalar.TYPES for t in args) and before[method,desc]!=after[method,desc]
                    and all(observer_scalar.closed_data_operation(d.data,method,desc) for d in (old,new))):
                targets.append(owner.replace(".","/")+"#"+method+desc)
    return targets[:prediction.LIMIT]


def checked_files(root, rows):
    files = []
    for row in rows:
        path = prediction.read_local(root,row["file"])
        if change_inventory.file_digest(path) != row["sha256"]:
            raise ValueError("original test or production dependency digest differs")
        files.append(path)
    return files


def has(files, member):
    for file in files:
        if file.is_dir():
            if (file/member).is_file():
                return True
        else:
            with zipfile.ZipFile(file) as z:
                if member in z.namelist():
                    return True
    return False


def attempt(root, packet, row, targets, jdk, feature, agent, work):
    side = row["side"]
    name, method = row["class"], row["method"]
    if side not in ("old","new") or not re.fullmatch(r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*",name) or not re.fullmatch(r"[A-Za-z_$][\w$]*",method):
        raise ValueError("incomplete original upstream method identity")
    source = prediction.read_local(root,row["source"])
    if source.suffix != ".java" or upgrade_replay.sha(source) != row["sha256"]:
        raise ValueError("original Java test bytes differ from the reviewed method")
    original = checked_files(root,packet[side]["classpath"])
    tests = checked_files(root,row["classpath"])
    cp = list(dict.fromkeys([*original,*tests]))
    if has(tests,"org/junit/platform/launcher/core/LauncherFactory.class"):
        launch_source = PLATFORM
    elif has(tests,"org/junit/runner/JUnitCore.class"):
        launch_source = JUNIT4
    else:
        raise ValueError("no original runnable JUnit launcher in the pinned test graph")
    work.mkdir()
    classes = work/"classes"
    classes.mkdir()
    launcher = work/"OriginalUnit.java"
    launcher.write_text(launch_source)
    build = subprocess.run([jdk/"bin/javac","-proc:none","-g","-encoding","UTF-8","-cp",os.pathsep.join(map(str,cp)),
                            "-d",classes,source,launcher],text=True,capture_output=True,timeout=30)
    if build.returncode:
        first = next((line.split("error:",1)[1].strip() for line in build.stderr.splitlines() if "error:" in line),"compiler error")
        raise ValueError("original unit test compilation: "+first)
    trace = work/"events"
    trace.mkdir()
    prefixes = {entry.split("#")[0] for entry in targets}
    config = work/"coverage.tsv"
    config.write_text("directory\t"+str(trace)+"\nlimit\t8192\ntest\t"+name.replace(".","/")+"\n"+
                      "".join("changed\t"+s+"\n" for s in targets)+"".join("prefix\t"+s+"\n" for s in sorted(prefixes))+
                      "".join("public\t"+s.partition("#")[2]+"\n" for s in targets))
    cp_text = os.pathsep.join(map(str,[classes,*cp]))
    command = [jdk/"bin/java","-Xmx384m","-Duser.timezone=UTC","-Duser.language=en","-Duser.country=US","-cp",cp_text,"OriginalUnit",name,method]
    env = {**os.environ,"PATH":str(jdk/"bin")+":/usr/bin:/bin"}
    scopes = {}
    for mode in ("plain","traced"):
        trial = work/mode
        trial.mkdir()
        opts = "-Djava.io.tmpdir="+str(trial)
        if mode=="traced":
            opts += " -agentpath:"+str(agent)+"="+str(config)+" -Xlog:class+load=info:file="+str(trace/"%p.loads")
        result = subprocess.run(command,cwd=trial,env={**env,"JAVA_TOOL_OPTIONS":opts},
                                capture_output=True,text=True,timeout=30)
        scopes[mode] = [l for l in result.stdout.splitlines() if l.startswith("ORIGINAL-UNIT ")]
        if result.returncode or not scopes[mode]:
            raise ValueError("original JUnit method did not produce an attributable test outcome on "+mode)
    if scopes["plain"] != scopes["traced"]:
        raise ValueError("the original traced and plain upstream tests differ")
    graph = [{"file":str(p),"sha256":r["sha256"]} for p,r in zip(original,packet[side]["classpath"],strict=True)]
    witnesses = []
    forks = []
    for path in sorted(trace.glob("*.events")):
        fork = public_histories.read_fork(path,graph,classes,"upstream unit",packet[side+"Revision"],upgrade_replay.sha(jdk/"release"),feature)
        if fork["stop"] is not None:
            raise ValueError(fork["stop"])
        for hit in public_histories.witnesses(fork):
            owner,_,member = hit["entry"].partition("#")
            frame = hit.get("frame") or hit.get("publicCall") or {}
            bind = fork["classes"].get(str(frame.get("loader"))+":"+owner,{})
            if hit["changed"] in targets and bind.get("originalProvider"):
                witnesses.append({"entry":owner.replace("/",".")+"#"+member,"changed":hit["changed"],"side":side,
                            "test":name+"#"+method,"relationship":hit["relationship"],"hitEvent":hit["hitEvent"],
                            "loader":frame["loader"],"classSha256":bind["classSha256"],**bind["originalProvider"]})
        fork["events"] = len(fork.pop("sequence"))
        forks.append(fork)
    if not forks:
        raise ValueError("the reviewed upstream test emitted no trace")
    return {"side":side,"sourceSha256":row["sha256"],"test":name+"#"+method,"compiledTestSet":
            {p.relative_to(classes).as_posix():upgrade_replay.sha(p) for p in classes.rglob("*.class")},
            "plainParity":True,"outcomes":scopes,"forks":forks,"witnesses":witnesses}


def run(root, dest):
    packet=json.loads((root/"packet.json").read_bytes())
    if (packet["arm"]!="test-assisted" or (packet.get("functionalReview") or {}).get("classification")!="ordinary product behavior"
            or prediction.sensitive_scope(packet.get("title","")+" "+packet.get("description",""))):
        raise ValueError("a reviewed ordinary upstream test-assisted view is required")
    dest.mkdir(parents=True,exist_ok=True)
    out={"schema":"approved-original-unit-trace/v1","url":packet["url"],"runs":[],"stops":[],
         "artifacts":{s:[r["sha256"] for r in packet[s]["classpath"]] for s in ("old","new")},
         "jdkReleaseSha256":upgrade_replay.sha(Path(packet["jdk"])/"release")}
    jdk=Path(packet["jdk"])
    feature=int(runtime_jdk.feature(runtime_jdk.release(jdk)["JAVA_VERSION"]))
    launches=packet.get("approvedTestLaunches") or []
    targets=safe_changed(root,packet,feature) if launches and feature>=11 else []
    if not targets:
        out["stops"].append("no reviewed original test launch over a changed closed scalar declaration on a supported JDK")
    else:
        with tempfile.TemporaryDirectory(prefix="approved-unit-") as temp:
            scratch=Path(temp)
            agent=scratch/"history.so"
            subprocess.run(["g++","-std=c++17","-shared","-fPIC","-O2","-I"+str(jdk/"include"),"-I"+str(jdk/"include/linux"),
                            HERE/"java/PublicHistoryAgent.cpp","-o",agent],check=True,capture_output=True,timeout=30)
            seen=set()
            for row in launches:
                if row["side"] in seen:
                    continue
                seen.add(row["side"])
                work=scratch/row["side"]
                try:
                    out["runs"].append(attempt(root,packet,row,targets,jdk,feature,agent,work))
                    with zipfile.ZipFile(dest/(row["side"]+"-original-test.zip"),"w",zipfile.ZIP_DEFLATED) as z:
                        for p in (work/"events").iterdir():
                            z.write(p,p.name)
                except (ValueError,OSError,subprocess.SubprocessError) as error:
                    out["stops"].append({"side":row["side"],"reason":str(error)})
    prediction.publish(dest/"trace.json",out)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("packet",type=Path)
    p.add_argument("output",type=Path)
    a=p.parse_args()
    run(a.packet.resolve(),a.output.resolve())

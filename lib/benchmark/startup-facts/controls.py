"""Check the two-profile quantifier, existing setting countermodels and joint startup boundaries."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from types import SimpleNamespace
from zipfile import ZipFile, ZIP_DEFLATED

from charset import compile_to, command, ENV, JDK, ROOT, SMALL, startup_facts
from targets import qualification, runtime_jar

JOINT="oc.JointStartup"
JOINT_SOURCE=ROOT / "lib/tests/fixtures/observed-countermodels/app/oc/JointStartup.java"


def evaluate(work,classes,entry,predicate,extra=(),env=ENV):
    return startup_facts.run_step(command(entry,predicate,classes),extra,work,env)


def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="startup-bounds-") as tmp:
        w=Path(tmp);classes=w/"classes"
        compile_to(classes,[*sorted(SMALL.glob("*.java")),JOINT_SOURCE,Path(__file__).with_name("StartupControls.java")])
        symbolic=[]
        names,_=runtime_jar.parameter_names((classes/"StartupControls.class").read_bytes(),"selected","(Z)I")
        choice,=names
        for name,predicate in [("explicit","result == 2"),("selected",f"({choice} && result == 1) || (!{choice} && result == 2)")]:
            code,out,why=evaluate(w/name,classes,"StartupControls#"+name+"(Z)I",predicate)
            assert code==0 and out["verdict"]=="verified" and out["stated"]["bounds"]["complete"],(out,why)
            ids=[a.get("id") for a in out["stated"]["assumptions"] if a.get("id")]
            assert not any(i.startswith("startup-") or i.startswith("observed-initializer:") for i in ids)
            symbolic.append({"entry":out["target"],"quantifiedSet":["UTF-8","US-ASCII"],"assertion":predicate,"domain":out["domain"],
                             "verdict":out["verdict"],"startupPremises":[]})
        settings=[]
        code,actual,why=evaluate(w/"typed",classes,"sc.M#encoded()I","result == 1",
                ["--observed-initializer","sc.Encoded","--observed-runtime",'{"charsetLocale":"C","expectedCharsetName":"US-ASCII"}'])
        assert code==0 and actual["verdict"]=="verified", (actual,why)
        fact,=actual["startup_evidence"]
        typed = SimpleNamespace(kind="prove",revisions=["original"],claim={"observedRuntime":{"charsetLocale":"C"},
                              "startupPremises":["startup-charset:"+fact["receipt"]],"observedInitializers":{"sc.Encoded":fact["stateSha256"]}})
        prepared={"original":{"sc.Encoded":fact["classSha256"]}}
        assert qualification.library_bindings_problem(typed,actual,prepared) is None
        assert qualification.library_bindings_problem(typed,actual,{"original":{"sc.Encoded":"0"*64}})
        typed.claim["startupPremises"]=[]
        assert qualification.library_bindings_problem(typed,actual,prepared)
        for name,profiles,stop in [
            ("mapped",[("-Dsc.value=xyz",{},3),("",{},6)],"method handle"),
            ("kept",[("-Dsc.value=xyz",{},3),("",{},6)],"map update"),
            ("looked",[("",{"SC_VALUE":"xyz"},3),("",{},6)],"dynamically looked-up member"),
            ("counted",[("-XX:ActiveProcessorCount=3",{},3),("-XX:ActiveProcessorCount=5",{},5)],"resource configuration"),
            ("rooted",[("-Duser.dir=/abc",{},4),("-Duser.dir=/abcdef",{},7)],"working directory"),
            ("encoded",[("-Dfile.encoding=COMPAT",{"LC_ALL":"C"},1),("",{"LC_ALL":"C"},2)],"default charset")]:
            ordinary=[]
            for flag,vals,value in profiles:
                env={k:v for k,v in ENV.items() if k not in ("SC_VALUE","JAVA_TOOL_OPTIONS","JDK_JAVA_OPTIONS","_JAVA_OPTIONS")}
                env.update(vals)
                out=subprocess.check_output([JDK/"bin/java","-XX:-UsePerfData",*([flag] if flag else []),"-cp",classes,"sc.M",name],env=env,text=True).strip()
                assert out==f"{name}={value}",out
                ordinary.append(out)
            first=profiles[0];env=dict(ENV,**first[1])
            # Count and directory binding use a different specific opt-in; withhold any such pin here.
            flag="" if name=="counted" else first[0]
            env["JAVA_TOOL_OPTIONS"]=flag
            code,out,why=evaluate(w/(name+"-strict"),classes,"sc.M#"+name,"result == "+str(first[2]),
                                   ["--observed-initializer","sc."+name.capitalize()],env)
            assert code and out is None and stop in why,(name,out,why)
            settings.append({"setting":name,"originalJvms":ordinary,"withoutPremise":stop})
        orders=[]
        for first,second,value in [("Root","Reader",7),("Reader","Root",0)]:
            roots=[JOINT+"$"+first,JOINT+"$"+second]
            flags=["--observed-runtime",'{"preinitializeTogether":true,"recordJointStartup":true}',"--observed-initializer",roots[0],"--observed-initializer",roots[1]]
            code,out,why=evaluate(w/first,classes,JOINT+"#recorded()I",f"result == {value}",flags)
            assert code==0 and out["verdict"]=="verified",(out,why)
            ids=[a["id"] for a in out["stated"]["assumptions"] if a.get("id","").startswith("observed-initializer:")]
            raw=json.loads(next((w/first/"startup-receipts").glob("*.json")).read_bytes())
            orders.append({"roots":roots,"expected":value,"verdict":out["verdict"],"premises":ids,
                           "objects":raw["objects"],"classes":raw["classes"],"actualOrder":raw["actualApplicationOrder"],"receipt":raw["id"]})
        assert {s.rsplit(":",1)[1] for s in orders[0]["premises"]}.isdisjoint({s.rsplit(":",1)[1] for s in orders[1]["premises"]})
        base=["--observed-runtime",'{"preinitializeTogether":true,"recordJointStartup":true}',"--observed-initializer",JOINT+"$Root"]
        code,out,why=evaluate(w/"opaque",classes,JOINT+"#readsOpaque()Z","result",base)
        assert code and out["verdict"]=="unverifiable" and "StringBuilder" in out["problem"],(out,why)
        opaque=out["problem"]
        code,out,why=evaluate(w/"parallel",classes,"StartupControls#threaded()I","result == 9",
                               ["--observed-runtime",'{"preinitializeTogether":true}',"--observed-initializer","StartupControls$Threaded"])
        assert code and "overlapping application initialization" in why,(out,why)
        ready=w/"second-root-entered"
        attempt=w/"interrupted"
        cmd=[*command(JOINT+"#recorded()I","result == 7",classes),*base,"--observed-initializer","StartupControls$Hold","--work",attempt]
        p=subprocess.Popen(cmd,env=dict(ENV,JAVA_TOOL_OPTIONS="-Dstartup.fixture.ready="+str(ready)),start_new_session=True,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+30
            while not ready.exists() and p.poll() is None and time.monotonic()<deadline: time.sleep(.05)
            assert ready.exists(), "second root never entered"
        finally:
            if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
            p.communicate(timeout=10)
        assert not list(attempt.rglob("startup-receipts/*.json"))
        assert not any("@observed " in p.read_text() for p in attempt.rglob("*.stdout"))
        retry=[*base,"--observed-initializer",JOINT+"$Reader"]
        # Reuse the exact interrupted work location with an independently complete capture.
        proc=subprocess.run([*command(JOINT+"#recorded()I","result == 7",classes),*retry,"--work",attempt],capture_output=True,text=True,env=ENV)
        assert proc.returncode==0 and json.loads(proc.stdout)[0]["verdict"]=="verified",proc.stderr
        doc={"symbolic":symbolic,"preparedCharset":fact,"settings":settings,"joint":orders,"opaque":opaque,"concurrent":"refused overlapping application initialization",
             "interrupted":{"completedRoots":1,"successfulRecordings":0,"retry":"fresh, verified"}}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(args.output,"w",compression=ZIP_DEFLATED) as archive:archive.writestr("scorecard.json",json.dumps(doc,indent=2)+"\n")
        print("two quantified profile checks, six setting countermodels, both orders, opaque, concurrent and interrupted startup")


if __name__=="__main__":main()

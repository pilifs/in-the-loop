"""Qualify exact live-table use on the registered POI histories and countermodels."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from charset import command, compile_to, ENV, IO, JDK, OBSERVER, ROOT, sha, startup_facts


def run_java(args, *, success=True):
    p = subprocess.run([JDK / "bin/java", "-XX:-UsePerfData", *map(str, args)], env={}, capture_output=True, timeout=80, cwd="/")
    if success and p.returncode:
        raise ValueError(p.stderr.decode(errors="replace")[-1600:])
    return p


def run_trace(tools, output, boundary, options, main, *, success=True):
    return run_java(["-cp",tools,"StartupTrace",output,boundary,"--live-table",*options,"--main",*main],success=success)


def poi(work, tools):
    original = json.loads((ROOT / "verification/organic-composition/poi/observed-frontier.json").read_bytes())
    case = IO.parent / "poi"
    rows = []
    for side in ("old","new"):
        prepared = json.loads((case/side/"prepared.json").read_bytes())
        for item in prepared["classpath"]:
            assert sha(Path(item["file"]).read_bytes()) == item["sha256"]
        jars = os.pathsep.join(item["file"] for item in prepared["classpath"])
        classes = work / (side+"-classes")
        compile_to(classes,[case/"StartupHistory.java"],jars)
        cp=os.pathsep.join((str(classes),jars))
        cmd=command("StartupHistory#currency","result == true",classes,jars)
        retry=startup_facts.recover(cmd,work/(side+"-retry"),receipts=work/"receipts",env=ENV,
            properties={"user.country":"US","user.language":"en","user.timezone":"UTC"})
        assert retry.get("table") and retry["ordinaryInitializerParity"], retry
        bulk=[e for e in retry["executed"] if e["operation"].startswith("forEach(")]
        assert any("StatusLogger$PropertiesUtilsDouble#normalizeProperties" in e["caller"] for e in bulk),bulk
        assert "StackLocator" in retry["remaining"] and "multi-release" in retry["remaining"],retry
        public=[]
        for i, historic in enumerate(original[side]["physical"]):
            case_args=historic["input"]
            language,country=case_args[1].split("-")
            opts=["-XX:-UsePerfData","-XX:ActiveProcessorCount=2","-Dstdout.encoding=UTF-8","-Duser.timezone=UTC","-Duser.language="+language,"-Duser.country="+country,"-cp",cp]
            main=["StartupHistory",*case_args]
            plain=run_java([*opts,*main]).stdout
            assert plain.decode().strip() == "ORIGINAL-VALUE "+historic["actual"], (side,case_args,plain.decode(),historic["actual"])
            projected=[]
            for label, extra in [("original",[]),("added",["-Dstartup.fixture.selected=present"]),("restored",[])] if i==0 else [("original",[])]:
                bound=[*extra,*opts]
                untouched=run_java([*bound,*main]).stdout if extra else plain
                path=work/(side+str(i)+label+".json")
                traced=run_trace(tools,path,"org.apache.poi.ss.usermodel.DataFormatter#<clinit>()V",bound,main)
                assert traced.stdout==untouched==plain
                events=json.loads(path.read_bytes())["events"]
                calls=[e for e in events if e["operation"].startswith("forEach(")]
                assert calls and "normalizeProperties" in calls[0]["caller"]
                projection=events[-1]["projection"]
                for e in calls:
                    assert (e["count"],e["orderSha256"],e["entriesSha256"]) == (projection["count"],projection["orderSha256"],projection["entriesSha256"])
                projected.append({"profile":label,"consumer":calls[0],"projection":projection})
            if i==0:
                a,b,c=[r["projection"] for r in projected]
                assert a==c and a["entriesSha256"]!=b["entriesSha256"] and a["count"]+1==b["count"]
            public.append({"input":case_args,"public":historic["actual"],"ordinaryParity":True,"projections":projected})
        rows.append({"revision":prepared["commit"],"side":side,"record":retry,"histories":public})
    return rows


def controls(work, tools):
    classes=work/"controls"
    compile_to(classes,[Path(__file__).with_name("TableControls.java")],str(tools))
    cp=os.pathsep.join(map(str,[classes,tools]))
    opts=["-XX:-UsePerfData","-Duser.timezone=UTC","-cp",cp]
    boundary="TableControls#sample()I"
    rows=[]
    for mode, reason in [("defaults","inherited defaults"),("custom","custom live"),("nonstring","non-string"),("view","keySet"),
                         ("save","escaped"),("replace","replaced"),("mutate","unrepresented")]:
        path=work/(mode+".json")
        result=run_trace(tools,path,boundary,opts,["TableControls",mode],success=False)
        assert result.returncode and reason in result.stderr.decode() and not path.exists(),(mode,result.stderr.decode()[-800:])
        rows.append({"fixture":mode,"refused":reason})
    hashes=[]
    for i,flags in enumerate(([],["-Dstartup.fixture.selected=present"],[])):
        options=[*flags,*opts]
        main=["TableControls","plain"]
        raw=run_java([*options,*main]).stdout
        path=work/("plain"+str(i)+".json")
        observed=run_trace(tools,path,boundary,options,main)
        assert observed.stdout==raw
        lines=raw.decode().splitlines()
        table=json.loads(lines[1])
        ops=json.loads(path.read_bytes())["events"]
        assert ops[0]["hashCode"]==table["hashCode"]==int(lines[0].split("=")[1]) and table==ops[-1]["projection"]
        hashes.append(table)
    assert hashes[0]==hashes[2] and hashes[0]["hashCode"]!=hashes[1]["hashCode"] and hashes[0]["entriesSha256"]!=hashes[1]["entriesSha256"]
    rows.append({"fixture":"bulk hash on added and removed own key","profiles":hashes})
    # A real, smaller property whose result depends on the supplied launch setting.
    cmd=command("TableControls$Startup#present()Z","result",classes,tools)
    env=dict(ENV)
    for i,props in enumerate([{},{"startup.fixture.selected":"present"}]):
        runtime={"liveProperties":True,"emptyEnvironment":True,"rootWorkingDirectory":True,"processors":2,"startupProperties":props}
        code,answer,diagnostic=startup_facts.run_step(cmd,["--observed-initializer","TableControls$Startup","--observed-runtime",json.dumps(runtime)],work/("native"+str(i)),env)
        if props:
            assert code==0 and answer["verdict"]=="verified" and any(a.get("id","").startswith("startup-table:") for a in answer["stated"]["assumptions"]), (answer,diagnostic)
        else:
            assert code and "counterexample requires replay" in diagnostic, diagnostic
        rows.append({"fixture":"native retained presence","keyPresent":bool(props),"verdict":answer["verdict"] if answer else "original-table witness required"})
    return rows


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="qualify-tables-") as tmp:
        work=Path(tmp); tools=work/"recorder"
        compile_to(tools,sorted(OBSERVER.glob("*.java")))
        result={"cases":poi(work,tools),"controls":controls(work,tools),"caseSpecificStartupProbes":0}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(args.output,"w",compression=ZIP_DEFLATED) as archive:
            archive.writestr("scorecard.json",json.dumps(result,indent=2)+"\n")
            for path in (work/"receipts").glob("*.json"): archive.write(path,"receipts/"+path.name)
    print("both POI deployments, twelve original histories and controlled live table tests qualified")


if __name__ == "__main__":
    main()

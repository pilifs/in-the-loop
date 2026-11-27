"""First frozen transfers. The historical callers and expectations are evaluator inputs."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from charset import CHECKER, ENV, JDK, OBSERVER, ROOT, startup_facts
from freeze import check as check_freeze

HERE=Path(__file__).resolve().parent
DOMAIN=ROOT/"lib/benchmark/domain-foundations"
RECEIVER=ROOT/"lib/benchmark/receiver-discovery"
sys.path.extend([str(DOMAIN),str(RECEIVER)])
import startup as foundation
import configuration as config
import recovery


def digest(path):
    with Path(path).open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()


def compile_java(jdk,classes,sources,cp=()):
    classes.mkdir(exist_ok=True)
    subprocess.run([jdk/"bin/javac","-J-XX:-UsePerfData","-encoding","UTF-8","-proc:none","-g","-parameters",
                    *(["-cp",os.pathsep.join(map(str,cp))] if cp else []),"-d",classes,*sources],check=True)


def jvm(jdk,args):
    return subprocess.run([jdk/"bin/java","-XX:-UsePerfData",*map(str,args)],env={},capture_output=True,timeout=120)


def paired(jdk,tools,work,label,cp,main,boundary,mode,flags=()):
    opts=["-XX:-UsePerfData","-Dstdout.encoding=UTF-8",*flags,"-cp",os.pathsep.join(map(str,cp))]
    plain=jvm(jdk,[*opts,*main])
    assert plain.returncode==0,(label,plain.stderr[-700:])
    path=work/(label+".trace.json")
    traced=jvm(jdk,["-cp",tools,"StartupTrace",path,boundary,mode,*opts,"--main",*main])
    if traced.returncode:
        assert not path.exists(),"failed recording published evidence"
        reason=next((line for line in traced.stderr.decode(errors="replace").splitlines() if line.startswith("Exception in thread")),"trace failed")
        result={"ordinary":plain.stdout.decode().splitlines(),"status":"refused","reason":reason,"reusable":False}
        failure=path.with_name(path.name+".failed.json")
        if failure.exists():
            diagnostic=json.loads(failure.read_bytes())
            assert diagnostic["schema"]=="jvm-startup-failure/v1" and diagnostic["boundary"]==boundary and diagnostic["normalReturn"] is False
            result.update(failure=diagnostic,ordinaryParity=traced.stdout==plain.stdout)
        return result
    assert traced.stdout==plain.stdout,(label,"tracer changed the public history")
    doc=json.loads(path.read_bytes())
    assert doc["boundary"]==boundary
    return {"ordinary":plain.stdout.decode().splitlines(),"status":"observed","boundary":boundary,"events":doc["events"],"ordinaryParity":True}


def configuration(work):
    tools=work/"tools";compile_java(JDK,tools,sorted(OBSERVER.glob("*.java")))
    scope=json.loads((recovery.RESULTS/"scope.json").read_bytes())
    result=[]
    for key in ("commons-configuration-565","commons-configuration-601"):
        measured=json.loads((recovery.OUT/key/"measurement.json").read_bytes())
        for side in ("old","new"):
            tmp=work/(key+side);tmp.mkdir()
            cp,_=config.prepare(key,side,tmp,scope)
            src=recovery.EXTERNAL/"scenarios"/key/"UpgradeProbe.java"
            recovery.compile_to(cp[0],cp,src,RECEIVER/"history/ConfigurationPrestate.java")
            frozen=measured["sides"][side]
            property_name=frozen["property"]["key"]
            pins=frozen["classBindings"]
            profiles=[]
            for profile in ("default","own-invalid","inherited-invalid"):
                calls=[]
                for i,item in enumerate(scope["registeredCallers"][key]["cases"]):
                    matched=recovery.observed(cp,pins,property_name,profile,"predicate",str(i))
                    observed=recovery.observed(cp,pins,property_name,profile,"observe",*item["args"])
                    reference=frozen["profiles"][profile][i]
                    assert reference["predicate"]==matched and reference["originalCalls"]==observed,(key,side,profile,i)
                    calls.append({"selector":i,"predicate":matched,"firstAndRepeated":observed})
                item=scope["registeredCallers"][key]["cases"][0]
                traced=paired(JDK,tools,tmp,profile,cp,["ConfigurationPrestate",profile,property_name,"observe",recovery.HOLDER,*item["args"]],
                              recovery.HOLDER+"#<clinit>()V","--live-table",["-ea","-Xverify:all"])
                profiles.append({"launch":profile,"startup":traced,"cases":calls})
            result.append({"case":key,"side":side,"revision":frozen["commit"],"orderedClasspath":list(frozen["classpath"]),
                           "key":property_name,"profiles":profiles,"originalScope":"the own invalid setting refutes the registered wider guarantee"})
    classes=work/"live";compile_java(JDK,classes,[RECEIVER/"history/LiveProperties.java"])
    history=paired(JDK,tools,work,"retained-table",[classes],["LiveProperties"],"LiveProperties#main([Ljava/lang/String;)V","--live-table")
    assert len(history["ordinary"])==15 and history["status"]=="refused",history
    return {"rows":result,"retainReplaceRemove":history,"assistance":"historical public caller and prestate fixture"}


def timing(work):
    tools=work/"tools";compile_java(JDK,tools,sorted(OBSERVER.glob("*.java")))
    classes=work/"caller";compile_java(JDK,classes,[DOMAIN/"StartupProfile.java"])
    rows=[]
    for side in ("parent","fix"):
        area=work/side;area.mkdir()
        jars,deploy=foundation.materialize(next((ROOT/"examples").glob("360-*")),side,area)
        for mode,flag in [("LF","\n"),("CRLF","\r\n"),("absent","\n")]:
            main=["foundation.StartupProfile","plain","separator","absent" if mode=="absent" else "ordinary"]
            sample=paired(JDK,tools,work,"parser-"+side+mode,[classes,*jars],main,"com.github.javaparser.utils.LineSeparator#<clinit>()V","--live-table",["-Dline.separator="+flag])
            text="\n".join(sample["ordinary"])
            if mode=="absent":
                for kind in ["ExceptionInInitializerError","NullPointerException","NoClassDefFoundError"]: assert kind in text,(mode,text)
                assert sample["status"]=="refused",sample
            else:
                assert sample["ordinary"] == ["separatorUnits\t" + ("13,10" if mode == "CRLF" else "10")], (mode,text)
            rows.append({"case":"JavaParser","revision":deploy["revision"],"profile":mode,**sample})
    base=ROOT/"examples/332-paper-initialization"
    for variant in ("cached","live"):
        dest=work/variant
        compile_java(JDK,dest,[base/variant/"paper/Paper.java",base/"both/paper/Scenario.java",base/"driver/paper/PaperCases.java",
                                ROOT/"examples/tools/targets/java/org/intheloop/controls/Grid.java",HERE/"PaperTiming.java"])
        for i in range(9):
            stock=jvm(JDK,["-cp",dest,"paper.PaperCases","child",str(i)])
            assert stock.returncode==0,stock.stderr
            registered=json.loads(stock.stdout)
            expected=registered["direct"]
            main=["paper.PaperTiming",str(i)]
            init=paired(JDK,tools,work,variant+str(i)+"-init",[dest],main,"paper.Paper#<clinit>()V","--live-table")
            second=paired(JDK,tools,work,variant+str(i)+"-second",[dest],main,"paper.PaperTiming#second()Ljava/lang/String;","--live-table")
            actual=f'{expected["first"]}|{expected["second"]}|{expected["count"]}'
            assert init["ordinary"]==second["ordinary"]==[actual] and expected["count"]==1,(registered,init,second)
            key=hashlib.sha256(b"print.paper").hexdigest()
            def reads(r): return [e for e in r.get("events",[]) if e.get("keySha256")==key]
            assert bool(reads(init))==(variant=="cached") and bool(reads(second))==(variant=="live"),(init,second)
            rows.append({"case":"paper 332","revision":variant,"input":registered["input"],"actual":expected,
                         "startupReads":reads(init),"secondCallReads":reads(second),"ordinaryParity":True})
    return {"rows":rows,"assistance":"original paper and JavaParser callers plus a labelled marker around the second public paper call"}


def spring(work):
    base=ROOT/"examples/480-spring-nested-return-type"
    runtime=json.loads((base/"runtime.json").read_bytes())
    jdk=Path.home()/".sdkman/candidates/java"/runtime["jdk"]
    assert digest(jdk/"release")==runtime["jdkReleaseSha256"]
    tools=work/"tools";compile_java(jdk,tools,sorted(OBSERVER.glob("*.java")))
    root=Path.home()/".cache/in-the-loop"/runtime["cache"]
    comparison=json.loads((base/"comparison.json").read_bytes())
    original=(base/"caller/PublicCaller.java").read_text()
    selection='Arrays.stream(Text.class.getDeclaredMethods()).filter(m -> m.getName().equals("get") && !m.isBridge())\n                .findFirst().orElseThrow()'
    assert original.count(selection)==1
    changed=work/"PublicCaller.java";changed.write_text(original.replace(selection,"CachedSpringMethod.METHOD"))
    result=[]
    for side in ("parent","fix"):
        cp=[root/n for n in runtime["deployments"]["pins"]["classpath"][side]]
        assert all(digest(f)==runtime["sha256"][f.relative_to(root).as_posix()] for f in cp)
        outputs={}
        for variant,source in [("original",base/"caller/PublicCaller.java"),("cached",changed)]:
            classes=work/(side+"-"+variant)
            compile_java(jdk,classes,[source,HERE/"CachedSpringMethod.java",ROOT/"examples/tools/targets/java/UpgradeObservation.java"],cp)
            values=[]
            for i,q in enumerate(comparison["questions"]):
                output=work/(side+variant+str(i)+".out")
                args=[base64.b64encode(a.encode("utf-16-be")).decode() for a in q["args"]]
                result_jvm=jvm(jdk,["-Dupgrade.observation.file="+str(output),"-cp",os.pathsep.join(map(str,[classes,*cp])),"UpgradeObservation","PublicCaller",*args])
                assert result_jvm.returncode==0,result_jvm.stderr
                value=base64.b64decode(output.read_text().strip().removeprefix("UPGRADE-OBSERVATION return "),validate=True).decode("utf-16-be")
                if side in q["expected"]:assert value==q["expected"][side]["return"],(side,value)
                values.append(value)
            outputs[variant]=values
        assert outputs["original"]==outputs["cached"]
        cmd=[CHECKER,"prove","CachedSpringMethod#count()I","--assert","result == 0","--classes",str(classes),"--classpath",os.pathsep.join(map(str,cp)),
             "--engine","native","--gaps","strict","--json"]
        _,native,why=startup_facts.run_step(cmd,["--observed-initializer","CachedSpringMethod","--observed-runtime",'{"reflectiveMembers":true}'],work/(side+"-retry"),dict(ENV,JAVA_HOME=str(jdk)))
        receipts=list((work/(side+"-retry")/"startup-receipts").glob("*.json"))
        capture=json.loads(receipts[0].read_bytes()) if len(receipts)==1 else None
        result.append({"revision":comparison["revisions"][side],"side":side,"public":outputs,"callerSha256":digest(changed),
                       "observedDeclaringClassSha256":digest(classes/"PublicCaller$Text.class"),"erasedDescriptor":"()Ljava/util/Collection;",
                       "metadataRetry":native["verdict"] if native else "refused","gap":native.get("problem") if native else why.strip(),
                       "genericTypeSource":"original getGenericReturnType and GenericTypeResolver.resolveType",
                       "memberCapture":capture,"consumed":[a["id"] for a in (native or {}).get("stated",{}).get("assumptions",[]) if a.get("id")]})
    return {"rows":result,"assistance":"explicit labelled cache of the non-bridge override in the registered caller"}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("case",choices=("configuration","timing","spring","avro"))
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    frozen=check_freeze()
    if args.case == "avro":
        from transfer_avro import avro
        measure = avro
    else:
        measure = {"configuration": configuration, "timing": timing, "spring": spring}[args.case]
    scratch = Path(os.environ.get("TMPDIR") or Path.home()/".cache/in-the-loop/agent-tmp")
    if scratch == Path("/tmp") or Path("/tmp") in scratch.parents:
        scratch = Path.home()/".cache/in-the-loop/agent-tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="frozen-startup-", dir=scratch) as tmp:
        result = measure(Path(tmp))
        assert check_freeze()==frozen
        result.update(frozenProducer=frozen,attempt="first frozen transfer")
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with ZipFile(args.output,"w",compression=ZIP_DEFLATED) as archive:archive.writestr("scorecard.json",json.dumps(result,indent=2)+"\n")
    print(args.case,"first transfer archived",flush=True)


if __name__=="__main__": main()

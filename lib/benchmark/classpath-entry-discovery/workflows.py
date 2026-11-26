"""Exercise public discovery, an unchanged client's warm cache, and resolved resource lookups."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from controls import CHECKER, compile_sources, jar, java, launch, manifest
from transfer import ROOT, JDK
from targets import change_evidence, entry_binding, entry_discovery, runtime_jdk, upgrade_replay

WRITE = change_evidence.write_json


def plan(work,before,after,mode,workflows=None,previous=None,run=False,cache=None):
    dest=work/(mode+".json")
    args=[sys.executable,ROOT/"examples/tools/build.py","--change-plan","application","--before",before,"--after",after,
          "--jdk",JDK,"--checker",CHECKER,"--output",dest]
    if workflows: args.extend(["--workflows",workflows])
    if previous: args.extend(["--previous",previous])
    if cache: args.extend(["--cache",cache])
    if run: args.append("--run")
    subprocess.run(args,check=True)
    return dest,json.loads(dest.read_bytes())


def register(work,entry,case,expected,probe,after=None):
    spec={"entry":entry,"probeClass":"UpgradeProbe","observer":"original public return","basis":"one specified fresh caller",
          "cases":[{"args":[],"expected":{"return":str(expected)}}]}
    (work/"UpgradeProbe.java").write_text(probe)
    WRITE(work/"scope.json",spec)
    path=work/"workflows.json"
    WRITE(path,{"schema":"caller-workflows/v1","change":case,"workflows":[{"id":"public","cohort":"registered",
        "scope":"scope.json","probe":"UpgradeProbe.java","intent":"preserve" if after is None else
        {"allowedChanges":[{"input":0,"expectedNew":{"return":str(after)}}]},"assumptions":["Fresh fixed JVM, closed local deployment and fixed caller."],
        "deterministicUnderAssumptions":True}]})
    return path


def optional(work):
    sources={"Read":'''public class Read { public static int value() throws Exception {
        try(java.io.InputStream in=Read.class.getClassLoader().getResourceAsStream("demo/palette.txt")) {
        return in==null ? 0 : in.read(); } } public static void main(String[] a) throws Exception {System.out.print(value());} }'''}
    classes=compile_sources(work/"compile",sources)
    docs={}
    for side in ("old","new"):
        caller=jar(work/side/"read.jar",classes,"Class-Path: optional.jar")
        docs[side]=manifest([caller])
        WRITE(work/(side+".json"),docs[side])
    workflow=register(work,"Read#value()I","Optional local provider",0,
        'public class UpgradeProbe {public static String observe(String[] a) throws Exception {return Integer.toString(Read.value());}}')
    provider=work/"new/optional.jar"
    previous=None; rows=[]
    for mode in ("absent","repeat","appeared","pinned","pinned-clean","replaced","replaced-clean","restored"):
        if mode=="appeared":
            jar(provider,{"demo/palette.txt":"R"})
        if mode=="replaced":
            jar(provider,{"demo/palette.txt":"S"})
        if mode in ("pinned","replaced"):
            docs["new"]["manifestProviders"]=manifest([provider])["classpath"]
        if mode=="restored":
            provider.unlink()
            docs["new"].pop("manifestProviders")
        WRITE(work/"new.json",docs["new"])
        wanted=83 if mode.startswith("replaced") else 82 if mode in ("appeared","pinned","pinned-clean") else 0
        physical=int(java([work/"new/read.jar"],"Read"))
        previous,report=plan(work,work/"old.json",work/"new.json",mode,workflow,previous,True,work/("clean-"+mode if mode.endswith("clean") else "cache"))
        claim=report["claims"][0]
        status="open" if mode=="appeared" else "refuted" if wanted else "established"
        if physical!=wanted or claim["status"]!=status:
            raise ValueError(f"{mode}: expected {wanted}, {status}, got {physical} {claim}")
        actions={s:r["action"] for s,r in claim.get("execution",{}).items()}
        if mode in ("repeat","restored") and set(actions.values())!={"exact reuse"}:
            raise ValueError(f"{mode} original cache keys were lost")
        if mode in ("pinned","replaced") and actions!={"old":"exact reuse","new":"executed"}:
            raise ValueError(f"{mode} invalidated the wrong sides")
        rows.append({"case":4,"profile":mode,"question":"Read#value()I","originalJvm":physical,
                     "claimStatus":status,"execution":actions,"bindings":{s:report["entryBindings"][ref]["status"]
                     for s,ref in claim["entryBindings"].items()},"firstOpenDependency":claim.get("firstOpenDependency")})
    return rows


def facade(work):
    code={"Facade":'''package demo; public class Facade {private Facade() {} public static Facade create() {return new Facade();}
              public int view(){return Engine.run();} public int twice(){return 2*Engine.run();}}''',
          "Noise":"package demo; public class Noise {public static int measure(){return 100;}}"}
    for side,n in (("old",1),("new",2)):
        compiled=compile_sources(work/side,{**code,"Engine":f"package demo; class Engine {{static int run(){{return measure();}} private static int measure(){{return {n};}}}}"})
        roots=[jar(work/side/"one.jar",{k:v for k,v in compiled.items() if k.endswith("Engine.class")}),
               jar(work/side/"two.jar",{k:v for k,v in compiled.items() if not k.endswith("Engine.class")})]
        WRITE(work/(side+".json"),manifest(roots))
    _,cold=plan(work,work/"old.json",work/"new.json","blind")
    candidates=cold["inventory"]["candidates"]
    expected={"demo.Facade#twice()I","demo.Facade#view()I"}
    if {c["entry"] for c in candidates}!=expected or not cold["inventory"]["intentQuestion"]:
        raise ValueError("lost the competing observation or selected the name-only decoy")
    factory = "demo.Facade#create()Ldemo/Facade;"
    if any(factory not in side["construction"]["publicFactories"] for c in candidates for side in c["sides"].values()):
        raise ValueError("discovery lost the public factory for the private constructor")
    rows=[]
    for name in sorted(expected):
        operation=name.split("#")[1].split("(")[0]
        factor=2 if operation=="twice" else 1
        workflow=register(work,name,"Public factory and private helper",factor,
            "public class UpgradeProbe {public static String observe(String[] a){return Integer.toString(demo.Facade.create()."+operation+"());}}",factor*2)
        _,report=plan(work,work/"old.json",work/"new.json","witness-"+operation,workflow,run=True)
        claim=report["claims"][0]
        for side,ref in claim["entryBindings"].items():
            witness=report["bindingWitnesses"][ref][0]
            expected_chain=["demo.Engine#measure()I","demo.Engine#run()I",name]
            if claim["status"]!="established" or witness["changedBodyChains"]!=[expected_chain]:
                raise ValueError("actual private frame or factory caller differs: "+str(witness))
            rows.append({"case":7,"revision":side,"question":name,"inputMode":"binary-only then witnessed",
                         "factory":"demo.Facade#create()Ldemo/Facade;","candidates":[c["entry"] for c in candidates],
                         "ambiguousIntent":cold["inventory"]["intentQuestion"],"chain":list(reversed(expected_chain)),
                         "publicHits":witness["qualifiedMethodEntries"],"claimStatus":claim["status"],"manualProviderIndices":0})
    return rows


def original_client(work):
    library = "public class Library {public static int read(){return Helper.value();}}"
    probe = "public class UpgradeProbe {public static String observe(String[] a){return Integer.toString(Client.run());}}"
    for side, rate, offset in (("old", 1, 10), ("new", 2, 100)):
        classes = compile_sources(work/side, {
            "Helper": "public class Helper {public static int value(){return " + str(rate) + ";}}",
            "Client": "public class Client {public static int run(){return " + str(offset) + "+Library.read();}}",
            "Library": library})
        files = [jar(work/side/(name + ".jar"), {name + ".class": classes[name + ".class"]})
                 for name in ("Helper", "Client", "Library")]
        doc = manifest(files)
        doc["commit"] = side
        doc["classpath"][1]["role"] = "client"
        WRITE(work/(side + ".json"), doc)
    entry = "Library#read()I"
    workflow = register(work, entry, "Original client on a new deployment", 11, probe, after=102)
    spec = json.loads((work/"scope.json").read_bytes())
    spec["invocationVia"] = "Client#run()I"
    WRITE(work/"scope.json", spec)
    _, result = plan(work,work/"old.json",work/"new.json","comparison",workflow,run=True)
    adapted = result["claims"][0]
    original = result["deploymentQuestions"]["originalBinary"]["claims"][0]
    expected = [("adapted",adapted,102),("original-client",original,12)]
    rows = []
    for profile, claim, value in expected:
        outcome = claim["children"][0]
        if outcome["old"] != {"return":"11"} or outcome["new"] != {"return":str(value)}:
            raise ValueError("the wrong artifact was swapped for the original-client comparison")
        ref = claim["entryBindings"]["new"]
        bound = result["entryBindings"][ref]
        graph = result["graphs"][bound["graph"]]
        if bound["providerIndex"] != 2 or graph["clientIndex"] != 1:
            raise ValueError("client, helper and entry roles were conflated")
        rows.append({"case":6,"revision":"new","profile":profile,"entry":entry,"clientIndex":1,"providerIndex":2,
                     "orderedHashes":[r["sha256"] for r in graph["classpath"]],"actual":value,
                     "originalReturn":11,"binding":ref,"observedClaimStatus":claim["status"]})
    if sum(a != b for a,b in zip(rows[0]["orderedHashes"],rows[1]["orderedHashes"],strict=True)) != 1:
        raise ValueError("original-client comparison changed another provider")
    return rows


def inherited(work):
    cls = compile_sources(work/"compile", {
        "Base": "public class Base {public int value(){return 6;}}",
        "Child": "public class Child extends Base {}"})
    base = jar(work/"base.jar", {"Base.class":cls["Base.class"]})
    child = jar(work/"client.jar", {"Child.class":cls["Child.class"]})
    for side in ("old","new"):
        WRITE(work/(side+".json"),manifest([child,base]))
    workflow=register(work,"Child#value()I","Inherited public entry",6,
        'public class UpgradeProbe {public static String observe(String[] a){return Integer.toString(new Child().value());}}')
    _,report=plan(work,work/"old.json",work/"new.json","inherited",workflow,run=True)
    claim=report["claims"][0]
    if claim["status"]!="established":raise ValueError(claim)
    rows=[]
    for side,ref in claim["entryBindings"].items():
        b=report["entryBindings"][ref]
        if b["resolvedEntry"]!="Base#value()I" or b["providerIndex"]!=1 or b["symbolicOwner"]["checker"]["index"]!=0:
            raise ValueError("inherited implementation or symbolic owner was rebound")
        rows.append({"case":6,"revision":side,"profile":"inherited","entry":claim["entry"],"resolvedEntry":b["resolvedEntry"],
                     "providerIndex":1,"binding":b,"status":claim["status"],"witness":report["bindingWitnesses"][ref]})
    return rows


def resources(work,slot,second):
    # The discoverer receives neutral filenames only. Its registered answers are opened after it saves the proposals.
    packet=Path.home()/".cache/in-the-loop/beyond-jbmc/panel/evaluation"/slot/"packet"
    inputs=json.loads((packet/"inputs.json").read_bytes()); jdk=Path(runtime_jdk.home("25"))
    for side in ("old","new"):
        roots=[]
        if second:
            roots.append(jar(work/side/"000.jar",{"control":"unrelated"}))
        for i,record in enumerate(inputs[side],start=len(roots)):
            original=packet/record["path"]
            if upgrade_replay.sha(original)!=record["sha256"]:
                raise ValueError("changed blinded input")
            file=work/side/f"{i:03d}.jar";file.parent.mkdir(exist_ok=True);shutil.copyfile(original,file);roots.append(file)
        WRITE(work/(side+".json"),manifest(roots))
    dest=work/"discovery"
    subprocess.run([sys.executable,ROOT/"examples/tools/build.py","--discover-resource-workflows","--before",work/"old.json",
                    "--after",work/"new.json","--jdk",jdk,"--output",dest],check=True)
    seen=json.loads((dest/"discovery.json").read_bytes())
    registered=json.loads((ROOT/"lib/benchmark/beyond-jbmc/blind/public-entries.json").read_bytes())[slot]
    rows=[]
    for candidate in seen["candidates"]:
        if candidate["stage"]!="original JVM controls passed":
            raise ValueError(f"unqualified resource workflow: {candidate['stage']} {candidate.get('firstScaffoldStop')}")
        observed=json.loads((dest/candidate["directory"]/"scaffold.json").read_bytes())
        for side,trials in observed["physical"].items():
            origins=candidate["origins"][side]
            pos=next(r["index"] for r in origins if r["selected"])
            populated = [t for t in trials if t["args"][0] == "primary" and int(t["args"][1]) and t["actual"].partition("=")[2]]
            if not populated or not any(any(e[0] == "RESOURCE-ORIGIN" for e in t["lookupTrace"]) for t in populated):
                raise ValueError("no consumed populated resource origin")
            evidence = max(populated, key=lambda t: len(t["lookupTrace"]))
            rows.append({"case":9,"slot":slot,"revision":side,"profile":"entry in second provider" if second else "original order",
                         "entry":candidate["entry"],"providerIndex":pos,"registeredQuestionRecovered":candidate["entry"] in registered,
                         "registeredResourceKeys":observed["resources"],"originalTrials":len(trials),"exampleTrial":evidence,
                         "wrongExpectationRejected":all(t["actual"] != t["expected"].partition("=")[0] + "=" for t in populated),
                         "manualProviderIndices":0})
    if not rows or any(r["registeredQuestionRecovered"]!=(slot=="15") or (second and r["providerIndex"]!=1) for r in rows):
        raise ValueError(f"public entry scoring failed: {rows}")
    return rows


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=["optional","facade","original-client","inherited","index","index-second","batik"])
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="entry-workflows-") as tmp:
        if args.mode in ("optional","facade","original-client","inherited"):
            result={"optional":optional,"facade":facade,"original-client":original_client,"inherited":inherited}[args.mode](Path(tmp))
        else:
            result=resources(Path(tmp),"04" if args.mode=="batik" else "15",args.mode=="index-second")
        WRITE(args.output,result)
        print(args.mode,len(result),"rows")

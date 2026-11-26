"""Small ordered deployments with independently observable selection, resource, linkage and reachability controls."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import zipfile

from transfer import ROOT, JDK
from targets import change_evidence, change_inventory, class_binding, deployment_graph, entry_binding, entry_discovery
from targets import interfaces, recipes, runtime, runtime_jdk, upgrade_replay

CHECKER = Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")).resolve()


def compile_sources(work, sources, cp=(), release="8"):
    work.mkdir(parents=True, exist_ok=True)
    files = []
    for name, source in sources.items():
        file = work / (name + ".java")
        file.write_text(source)
        files.append(file)
    out = work / "classes"
    out.mkdir()
    subprocess.run([JDK / "bin/javac", "--release",release,"-proc:none","-g","-d",out,"-cp",
                    os.pathsep.join(map(str,cp)) or str(work),*files],check=True,capture_output=True)
    return {p.relative_to(out).as_posix():p.read_bytes() for p in out.rglob("*.class")}


def jar(path, contents, manifest=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name,data in sorted(contents.items()):
            archive.writestr(zipfile.ZipInfo(name),data)
        if manifest is not None:
            archive.writestr(zipfile.ZipInfo("META-INF/MANIFEST.MF"),"Manifest-Version: 1.0\r\n" + manifest + "\r\n\r\n")
    return path


def java(cp, main, *args, jdk=JDK):
    return subprocess.check_output([jdk/"bin/java","-Xmx128m","-cp",os.pathsep.join(map(str,cp)),main,*args],text=True).strip()


def manifest(files):
    return {"classpath":[{"file":str(f),"sha256":upgrade_replay.sha(f)} for f in files]}


def launch(files, feature="21", additional=None):
    jdk = Path(runtime_jdk.home(feature))
    document = {**manifest(files), **(additional or {})}
    paths, entries, info = deployment_graph.resolve(document,files[0].parent,int(feature),change_inventory.file_digest)
    graph = {"kind":"production","jdk":runtime_jdk.identity(jdk)["release"],"classpath":entries,**info}
    graph["key"] = change_inventory.digest(graph)
    return paths,graph,jdk


def ordered(work, prove=False):
    helper = "public class Helper { public static int value() { return %d; } }"
    a = jar(work/"A.jar",{**compile_sources(work/"ah",{"Helper":helper % 11}),"mark.txt":"A"})
    b = jar(work/"B.jar",{**compile_sources(work/"bh",{"Helper":helper % 22,
        "OrderEntry":"public class OrderEntry { public static int read() { return Helper.value(); } }"}),"mark.txt":"B"})
    reader = jar(work/"reader.jar",compile_sources(work/"read",{"Inspect":'''import java.net.*; import java.util.*;
        public class Inspect { public static void main(String[] args) throws Exception {
          System.out.print(OrderEntry.read()); Enumeration<URL> all=OrderEntry.class.getClassLoader().getResources("mark.txt");
          while(all.hasMoreElements()) { URL u=all.nextElement(); try(java.io.InputStream in=u.openStream()) {
             System.out.print(" "+(char)in.read()); }} } }'''},[a,b]))
    graphs = {key:launch(files) for key, files in (("A,B",[a,b]),("B,A",[b,a]),("B",[b]))}
    name = "OrderEntry#read()I"
    bound = entry_binding.qualify(CHECKER,graphs,{key:[name,"Helper#value()I"] for key in graphs})
    rows = []
    for key,(files,_,_) in graphs.items():
        expected = {"A,B":"11 A B","B,A":"22 B A","B":"22 B"}[key]
        physical = java([*files,reader],"Inspect")
        if physical != expected or not all(r["status"]=="bound" for r in bound[key].values()):
            raise ValueError(f"{key}: order or origin differs")
        row = {"case":2,"profile":key,"question":name,"jvm":physical,"entryProvider":bound[key][name]["providerIndex"],
               "helperProvider":bound[key]["Helper#value()I"]["providerIndex"],"resourceLookup":"defining ClassLoader.getResources(mark.txt)",
               "resourceOrder":physical.split()[1:],"manualProviderIndices":0}
        if prove:
            scaffold = work / ("scaffold-" + key)
            (scaffold / "records").mkdir(parents=True)
            commit = "ordered-fixture-" + key
            prepared_manifest = scaffold / "prepared.json"
            change_evidence.write_json(prepared_manifest, {**manifest(files), "commit": commit})
            record_path = scaffold / "records/entry-bindings.json"
            subprocess.run([sys.executable, ROOT/"examples/tools/scaffold_example.py", "bind", "--before",prepared_manifest,
                            "--after",prepared_manifest,"--jdk",JDK,"--entry",name,"--checker",CHECKER,"--output",record_path],check=True)
            row["engines"] = {}
            for engine in ("native","jbmc"):
                attempt = work / (key.replace(",","-") + engine)
                where = attempt/"prepare/after"
                where.mkdir(parents=True)
                artifacts = []
                for f in files:
                    (where/f.name).symlink_to(f)
                    artifacts.append(interfaces.Artifact(f.name, upgrade_replay.sha(f),"original" if f==a else "dependency"))
                selected = bound[key][name]
                target = {"loadedFrom":b.name,"classSha256":selected["classSha256"],"class":"OrderEntry"}
                prepared = SimpleNamespace(source={"target":target}, commit=commit)
                sides = {"after":(where,prepared,artifacts)}
                plan = SimpleNamespace(revisions=["after"],engine=engine,kind="prove",target=name,folder=str(scaffold))
                reports = []
                for n, prediction in enumerate((int(expected.split()[0]),99)):
                    recipe = recipes.ProofRecipe("direct-method","prove",name,name,tuple(
                        recipes.Argument(k,flag,v) for k,flag,v in (("assert","--assert",f"result == {prediction}"),
                        ("engine","--engine",engine),("gaps","--gaps","strict"))),{})
                    invocation = recipe.bind(plan,str(CHECKER),sides,f"run-{n}",60)
                    if not invocation.entries["after"].get("scaffoldBindingRefs"):
                        raise ValueError("actual proof recipe lost the frozen scaffold binding")
                    env = {**os.environ,"JAVA_HOME":str(JDK),"JVMCONTRACT_JAR_RELEASE":"21"}
                    if engine == "native":
                        runtime._launch_guard(plan,CHECKER,env,sides,invocation,runtime_jdk.identity(JDK),attempt,attempt)
                    result = subprocess.run(invocation.argv,cwd=attempt,env=env,text=True,capture_output=True,timeout=90)
                    outputs = json.loads(result.stdout)
                    verdict = outputs[0]["verdict"]
                    reports.append({"assert":f"result == {prediction}","verdict":verdict,"exit":result.returncode,"argv":list(invocation.argv),
                                    "reason":outputs[0].get("reason"),"classpath":invocation.classpaths, "scaffoldBindingRefs":invocation.entries["after"]["scaffoldBindingRefs"]})
                if [r["verdict"] for r in reports] != ["verified","violation"]:
                    raise ValueError(f"{engine} {key}: ordered helper controls {reports}")
                row["engines"][engine] = reports
        rows.append(row)
    return rows


def layouts(work):
    one = jar(work/"a/lib.jar",{"marker":"L"})
    two = jar(work/"b/lib.jar",{"marker":"R"})
    files = compile_sources(work/"fixture",{"Main":'''import java.net.*; import java.util.*;
        public class Main { public static void main(String[] a) throws Exception { Enumeration<URL> es=Main.class.getClassLoader().getResources("marker");
        while(es.hasMoreElements()) try(java.io.InputStream in=es.nextElement().openStream()){System.out.print((char)in.read());} }}'''})
    a = jar(work/"A.jar",{**files,"marker":"A"},"Class-Path: B.zip a/lib.jar")
    b = jar(work/"B.zip",{"marker":"B"},"Class-Path: A.jar b/lib.jar")
    rows = []
    for label,roots in (("A first",[a,one,two,b]),("B first",[b,one,two,a])):
        fs,graph,_ = launch(roots)
        actual = java(roots,"Main")
        if actual != ("ABRL" if roots[0]==a else "BALR") or java(fs,"Main") != actual or len(fs)!=4:
            raise ValueError(f"manifest recursion differs: {label} {actual}")
        rows.append({"case":5,"profile":label,"resourceOrder":actual,"order":[str(f.relative_to(work)) for f in fs],
                     "edges":graph["manifestClassPath"]["edges"]})
    return rows


def linkage(work):
    good = jar(work/"valid.jar",compile_sources(work/"good",{"Lookup":'public class Lookup { public static int get(String s){return 42;} }'}))
    wrong = jar(work/"prior.jar",compile_sources(work/"wrong",{"Lookup":'public class Lookup { public static int get(int n){return n;} }'}))
    moved = jar(work/"new-place.jar",{"Lookup.class":class_binding.entry_bytes(good,"Lookup.class")})
    client = jar(work/"client.jar",compile_sources(work/"client",{"App":'''public class App {public static void main(String[] args){
              try{System.out.print(Lookup.get("k"));}catch(NoSuchMethodError e){System.out.print(e.getClass().getName());}}}'''},[good]))
    store = entry_discovery.Index()
    graphs = {k:launch(files) for k,files in (("wrong first",[client,wrong,good]),("valid first",[client,good,wrong]),
                                              ("moved",[client,moved,wrong]))}
    name = "Lookup#get(Ljava/lang/String;)I"
    result = entry_binding.qualify(CHECKER,graphs,{s:[name] for s in graphs})
    rows = []
    for k,(files,graph,_) in graphs.items():
        outcome = java(files,"App")
        bound = result[k][name]
        view = store.view(files,[r["sha256"] for r in graph["classpath"]],21)
        if (outcome,bound["status"]) != (("java.lang.NoSuchMethodError","open") if k=="wrong first" else ("42","bound")):
            raise ValueError(f"{k}: missing member was supplied by a shadow")
        rows.append({"case":6,"profile":k,"question":name,"observed":outcome,"binding":bound,
                     "origins":view.origins("Lookup"),"originalClientSha256":upgrade_replay.sha(client)})
    return rows


def multirelease(work):
    a = jar(work/"empty.jar",{"unused":"A"})
    jarfiles = {}
    for mark in (3,5,7):
        jarfiles[mark] = compile_sources(work/str(mark),{"Gate":f"public class Gate {{public static int marker(){{return {mark};}}}}"})
    reader = jar(work/"driver.jar",compile_sources(work/"driver",{"Read":"public class Read {public static void main(String[] a){System.out.print(Gate.marker());}}"},
                         [jar(work/"api.jar",jarfiles[3])]))
    graphs = {}; expected = {}
    for mode,header in (("normal","Multi-Release: true"),("folded","Multi-Release: tr\r\n ue")):
        for side,version in (("old",5),("new",7)):
            carrier = jar(work/(mode+side+".jar"),{**jarfiles[3],"META-INF/versions/21/Gate.class":jarfiles[version]["Gate.class"]},header)
            for feature in ("17","21"):
                key = f"{mode}/{side}/{feature}"
                graphs[key]=launch([a,carrier,reader],feature)
                expected[key]=version if mode=="normal" and feature=="21" else 3
    entry = "Gate#marker()I"
    selected = entry_binding.qualify(CHECKER,graphs,{s:[entry] for s in graphs})
    rows=[]
    for key,(files,_,jdk) in graphs.items():
        record=selected[key][entry]
        actual=int(java(files,"Read",jdk=jdk))
        if record["status"]!="bound" or record["providerIndex"]!=1 or actual!=expected[key]:
            raise ValueError(f"{key}: alternate release mismatch {record.get('firstOpenDependency')} {actual}")
        mismatch = class_binding.disagreement("Gate",record["checker"],files[1],"0"*64)
        if not mismatch:
            raise ValueError("a different physical class digest was accepted")
        rows.append({"case":8,"profile":key,"actual":actual,"binding":record,"negativeDigestRefusal":mismatch})
    return rows


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=["order","backend","layouts","linkage","multi-release"])
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="entry-controls-") as d:
        fn={"order":ordered,"backend":lambda w:ordered(w,True),"layouts":layouts,"linkage":linkage,"multi-release":multirelease}[args.mode]
        result=fn(Path(d))
        change_evidence.write_json(args.output,result)
        print(f"{args.mode}: {len(result)} qualified deployment controls")

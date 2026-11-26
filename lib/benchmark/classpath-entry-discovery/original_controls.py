"""Recompile the original invoice, erased bridge and context-loader callers and compare their saved observations."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from controls import CHECKER, compile_sources, java, jar, launch
from transfer import ROOT, JDK
from targets import change_evidence, entry_binding, runtime_jar, upgrade_replay

BLIND=ROOT/"lib/benchmark/beyond-jbmc/blind"
sys.path[:0]=[str(BLIND),str(BLIND.parent)]
from native_resources import build as build_resource


def source(directory):
    return {p.stem:p.read_text() for p in directory.rglob("*.java")}


def invoice(work):
    folder,=(ROOT/"examples").glob("312-*")
    rates={name:jar(work/(name+".jar"),compile_sources(work/name,source(folder/"rates"/name),release="21"))
           for name in ("two","three")}
    client=jar(work/"invoice.jar",compile_sources(work/"client",{**source(folder/"client"),**source(folder/"driver")},[rates["two"]],"21"))
    reference=json.loads((folder/"records/ordered-origins.json").read_bytes())
    rows=[]
    for label,order in (("two-first",["two","three"]),("three-first",["three","two"])):
        results=[json.loads(line) for line in java([client,*[rates[n] for n in order]],"invoice.Invoices").splitlines()]
        totals=[r["total"] for r in results]
        if totals!=reference["sides"][label]["totals"] or any(r["rateJar"]!=order[0]+".jar" for r in results):
            raise ValueError("invoice values or defining provider differ")
        rows.append({"case":2,"example":312,"profile":label,"question":"Invoice.total","totals":totals,
                     "rateClass":results[0]["rateClass"],"clientClass":results[0]["invoiceClass"]})
    if sum(a!=b for a,b in zip(rows[0]["totals"],rows[1]["totals"],strict=True))!=4:
        raise ValueError("invoice reversal failed the four-change control")
    return rows


def bridges(work):
    folder,=(ROOT/"examples").glob("323-*")
    grid=ROOT/"examples/tools/targets/java/org/intheloop/controls/Grid.java"
    shared={**source(folder/"both"),**source(folder/"adapter"),**source(folder/"driver"),"Grid":grid.read_text()}
    qs=["bridgegrid.Plus#map(Ljava/lang/Object;)Ljava/lang/Object;", "bridgegrid.Plus#map(Ljava/lang/Integer;)Ljava/lang/Integer;"]
    graphs={}; rows=[]
    recorded=json.loads((folder/"records/finite-grid.json").read_bytes())
    for side in ("original","changed"):
        artifact=jar(work/(side+".jar"),compile_sources(work/side,{**shared,**source(folder/side)},release="21"))
        graphs[side]=launch([artifact])
        raw=java([artifact],"bridgegrid.Cases")+"\n"
        expected=next(r for r in recorded["runs"] if r["revision"]==side)
        if hashlib.sha256(raw.encode()).hexdigest()!=expected["stdoutSha256"]:
            raise ValueError(f"{side}: original bridge histories changed")
        wrong=json.loads(raw.splitlines()[-1])
        declaration=runtime_jar.read_class(artifact,"bridgegrid/Plus")
        flags=[runtime_jar.method_flags(declaration,*runtime_jar.parse_target(q)[1:]) for q in qs]
        if flags[0] & 0x1040 != 0x1040 or flags[1] & 0x1040 or "ClassCastException" not in str(wrong):
            raise ValueError("erased bridge or negative control differs")
        rows.append({"case":7,"example":323,"revision":side,"selectors":qs,"accessFlags":flags,"wrongType":wrong,"originalHistories":5})
    records=entry_binding.qualify(CHECKER,graphs,{s:qs for s in graphs})
    for row in rows:
        selected=records[row["revision"]]
        if any(r["status"]!="bound" for r in selected.values()):raise ValueError("bridge member differs")
        row["bindings"]=selected
    return rows


def loaders(work):
    folder,=(ROOT/"examples").glob("333-*")
    recorded=json.loads((folder/"records/loaders.json").read_bytes());rows=[]
    for side in ("default","explicit","app"):
        artifact=jar(work/(side+".jar"),compile_sources(work/side,{**source(folder/"both"),**source(folder/"driver"),**source(folder/side)},release="21"))
        raw=java([artifact],"styles.LoaderCases")+"\n"
        digest=hashlib.sha256(raw.encode()).hexdigest()
        if digest!=recorded["revisions"][side]["stdoutSha256"]:raise ValueError("context switching observations changed")
        files,graph,jdk=launch([artifact],additional={"loader":{"scope":"context children","delegation":"custom"}})
        refusal=entry_binding.qualify(CHECKER,{side:(files,graph,jdk)},{side:["styles.Lookup#inspect()[Ljava/lang/String;"]})[side]
        if any(r["status"]!="open" for r in refusal.values()):raise ValueError("unobserved custom dispatch entered flat native route")
        rows.append({"case":10,"example":333,"revision":side,"question":"Lookup.inspect","profile":"two successive thread contexts",
                     "originalHistories":16,"stdoutSha256":digest,"apiDefiningLoader":recorded["common"],
                     "applicationLoader":recorded["application"],"contextLoaderProfiles":recorded["contexts"],
                     "observations":[json.loads(line) for line in raw.splitlines()],"nativeBinding":refusal})
    for case in ("plain","compensating"):
        directory=work/case;directory.mkdir()
        _,scope=build_resource(directory,case)
        rows.append({"case":10,"profile":case,"question":"original scoped resource read","observations":scope})
    return rows


def openjdk(work):
    base=Path.home()/".cache/in-the-loop/classpath-entry-discovery"
    source=base/"src/openjdk-jdk-21+35-paths/test/langtools/tools/javac/Paths/ClassPath.java"
    data=source.read_bytes()
    if hashlib.sha1(f"blob {len(data)}\0".encode()+data).hexdigest()!="5b6bb5fe5bc058a9a0d6196e5463b35cb5f55306":raise ValueError("different upstream fixture")
    result=subprocess.check_output([base/"scripts/openjdk_classpath_fixture.sh",JDK/"bin",work],text=True)
    lines=result.splitlines()
    if len(lines)!=6 or any(not line.startswith("OK\t") for line in lines):raise ValueError(result)
    rows=[{"case":5,"profile":"pinned OpenJDK original","measurements":lines}]
    for label,files in (("A.jar",[work/"A.jar",work/"B.zip"]),("B.zip",[work/"B.zip",work/"A.jar"])):
        _,graph,_=launch(files)
        rows.append({"case":5,"profile":label,"edges":graph["manifestClassPath"]["edges"]})
    broken=work/"B.zip";broken.rename(work/"unavailable.zip")
    _,graph,_=launch([work/"A.jar"])
    proc=subprocess.run([JDK/"bin/java","-cp",str(work/"A.jar")+":"+str(work),"Main"],text=True,capture_output=True)
    if proc.returncode==0 or str(broken) not in graph["manifestClassPath"]["absent"]:raise ValueError("broken manifest edge still loaded B")
    rows.append({"case":5,"profile":"broken original edge","absent":str(broken),"exit":proc.returncode,
                 "firstOpenDependency":proc.stderr.splitlines()[0]})
    return rows


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode",choices=["invoice","bridge","loaders","openjdk"]);parser.add_argument("output",type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="original-entry-controls-") as d:
        rows={"invoice":invoice,"bridge":bridges,"loaders":loaders,"openjdk":openjdk}[args.mode](Path(d))
        change_evidence.write_json(args.output,rows)
        print(args.mode,len(rows),"checked original profiles")

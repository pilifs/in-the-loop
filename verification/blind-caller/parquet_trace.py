"""Rank public histories from original upstream test launches without historical entry names or callers."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT/"examples/tools"))
from targets import change_evidence, entry_discovery, public_histories, runtime_jar, upgrade_replay

SETUP = Path.home()/".cache/in-the-loop/blind-caller-pr-verification"
PRODUCT = Path.home()/".cache/in-the-loop/organic-pr-20"
JDK = Path.home()/".sdkman/candidates/java/21.0.13.0+9-tem"
AGENT = ROOT/"examples/tools/targets/java/PublicHistoryAgent.cpp"
POLICY = HERE/"trace-policy.json"


def graph(side):
    data = json.loads((ROOT/"verification/product-behaviour/cases/J08/bindings.json").read_bytes())[side]
    original = [{"file":str(PRODUCT/r["file"]),"sha256":r["sha256"]} for r in data["classpath"]]
    if len(original) != 113 or any(upgrade_replay.sha(Path(r["file"])) != r["sha256"] for r in original):
        raise ValueError("original Parquet deployment differs from the pinned graph")
    return data["commit"], original


def changed_methods(old, new):
    candidates = set()
    for a,b in zip(old,new,strict=True):
        if a["sha256"] != b["sha256"]:
            for row in (a,b):
                with zipfile.ZipFile(row["file"]) as z:
                    candidates.update(n[:-6] for n in runtime_jar.effective_entries(z,21) if n.endswith(".class"))
    output = []
    for owner in sorted(candidates):
        sides = []
        for cp in (old,new):
            for row in cp:
                data = runtime_jar.effective_class(row["file"],owner,21)
                if data:
                    sides.append(entry_discovery.fingerprints(entry_discovery.Definition(owner,"",0,data)))
                    break
            else:
                sides.append({})
        before,after = sides
        output.extend(owner+"#"+n+d for n,d in before.keys()|after.keys() if before.get((n,d)) != after.get((n,d)))
    return sorted(output)


def calls(classes, name):
    path = classes/(name.replace(".","/")+".class")
    if not path.exists():
        return {}
    return entry_discovery.Definition(name,"",0,path.read_bytes()).methods()


def selection(classes, tree, old, new):
    changed = subprocess.check_output(["git","-C",tree,"diff","--name-only",old,new],text=True).splitlines()
    changed_tests = {p.split("/src/test/java/",1)[1][:-5].replace("/",".") for p in changed if "/src/test/java/" in p and p.endswith(".java")}
    reports = SETUP/"upstream-tests/J08/reports/fix-on-fix"
    result = {}
    for inventory in sorted(reports.glob("*.classes.txt")):
        module = inventory.name.removesuffix(".classes.txt")
        pool = inventory.read_text().splitlines()
        direct = sorted(set(pool)&changed_tests)
        scores = {}
        for owner in pool:
            simple = re.sub(r"^Test(?=[A-Z])|(?:Tests?|TestCase)$","",owner.rsplit(".",1)[-1])
            scores[owner] = sum(any(t[0].rsplit("/",1)[-1] == simple for t in targets)
                                for flags,targets in calls(classes,owner).values())
        chosen = direct or sorted((owner for owner,n in scores.items() if n),key=lambda owner:(-scores[owner],owner))[:4]
        result[module] = {"selected":chosen,"changedTests":direct,"scores":scores,
                          "excluded":sorted(set(pool)-set(chosen))}
    if not result or any(not d["selected"] for d in result.values()):
        raise ValueError("original upstream module selected no runnable tests")
    return result


def test_rows(folder):
    result = []
    for report in sorted(folder.glob("*.xml")):
        for tc in ET.parse(report).getroot().iter("testcase"):
            result.append([tc.get("classname"),tc.get("name"),
                           [[child.tag,child.get("type")] for child in tc if child.tag in ("failure","error","skipped")]])
    if not result:
        raise ValueError("upstream JUnit launcher did not produce test identities")
    return sorted(result,key=lambda r:json.dumps(r))


def launch(base, module, tests, cp, tree, agent, config, *, isolated=False):
    base.mkdir()
    reports = base/"junit"
    tmp = base/"tmp"
    tmp.mkdir()
    cwd = tree/module
    if isolated:
        # Upstream tests use target/ relative to the module as well as java.io.tmpdir.
        # Each plain run and each traced fork gets the same tracked tree and an empty target.
        checkout = base/"checkout"
        checkout.mkdir()
        with subprocess.Popen(["git","-C",tree,"archive","HEAD",module],stdout=subprocess.PIPE) as export:
            with tarfile.open(fileobj=export.stdout,mode="r|") as source:
                source.extractall(checkout,filter="data")
            if export.wait():
                raise ValueError("could not hydrate the pinned module for an isolated upstream test")
        cwd = checkout/module
    args = [JDK/"bin/java","-Xmx1536m","-XX:MaxJavaStackTraceDepth=8","-XX:+IgnoreUnrecognizedVMOptions",
            *re.findall(r"--add-[a-z]+=[^ <\r\n]+",(tree/"pom.xml").read_text()),
            "-Dorg.slf4j.simpleLogger.defaultLogLevel=ERROR","-Dhadoop.logLevel=ERROR","-DenableResourceIntensiveTests=true",
            "-Djava.io.tmpdir="+str(tmp),"-cp",cp,"org.junit.platform.console.ConsoleLauncher","execute",
            "--disable-banner","--disable-ansi-colors","--details=summary","--reports-dir="+str(reports)]
    for name in tests:
        args.extend(["--select-class",name])
    env = {**os.environ,"TMPDIR":str(tmp)}
    env.pop("JAVA_TOOL_OPTIONS",None)
    if agent:
        env["JAVA_TOOL_OPTIONS"] = "-agentpath:"+str(agent)+"="+str(config)+" -Xlog:class+load=info:file="+str(base/"%p.loads")
    with (base/"launcher.log").open("w") as log:
        proc = subprocess.run(args,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=600)
    if proc.returncode not in (0,1):
        raise ValueError("test launch failed: "+(base/"launcher.log").read_text()[-600:])
    return test_rows(reports)


def run(side,reverse,root,*,separate=False):
    revold,old = graph("old")
    revnew,new = graph("new")
    targets = changed_methods(old,new)
    graph_rows = list(old if side=="old" else new)
    if reverse:
        if separate:
            member = targets[0].partition("#")[0]
            shadow = next(i for i,row in enumerate(graph_rows) if i and runtime_jar.effective_class(row["file"],member,21))
            graph_rows[0],graph_rows[shadow] = graph_rows[shadow],graph_rows[0]
        else:
            graph_rows.append(graph_rows.pop(0))
    rev = revold if side=="old" else revnew
    tree = PRODUCT/"worktrees/J08-parquet-java-fix"
    classes = SETUP/"upstream-tests/J08/fix/classes"
    resource = classes.parent/"resources"
    selection_rows = selection(classes,tree,revold,revnew)
    namespace = ET.parse(tree/"pom.xml").getroot().findtext("{*}groupId").replace(".","/")+"/"
    all_tests = {p.relative_to(classes).as_posix()[:-6] for p in classes.rglob("*.class")}
    deps = [(SETUP/("releases/j08-"+m+"-testdeps/classpath.txt")).read_text().strip() for m in ("hadoop","column")]
    cp = os.pathsep.join([str(classes),str(resource),*(r["file"] for r in graph_rows),*deps])
    agent = root/"history.so"
    subprocess.run(["g++","-std=c++17","-O2","-fPIC","-shared","-I"+str(JDK/"include"),"-I"+str(JDK/"include/linux"),
                    AGENT,"-o",agent],check=True)
    summary = {"schema":"original-upstream-history/v1","side":side,"revision":rev,"reversedOverlay":reverse,
               "orderedDeployment":graph_rows,"jdkReleaseSha256":upgrade_replay.sha(JDK/"release"),
               "policySha256":upgrade_replay.sha(POLICY),"agentSourceSha256":upgrade_replay.sha(AGENT),
               "changedSelectors":targets,"selection":selection_rows,"runs":[]}
    groups = [(module,[name],module+"-"+str(i)) for module,s in selection_rows.items()
              for i,name in enumerate(s["selected"])] if separate else [(module,s["selected"],module) for module,s in selection_rows.items()]
    for module,names,group in groups:
        shapes = {n+d for test in names for _,targets_in_method in calls(classes,test).values()
                  for owner,n,d in targets_in_method if owner.startswith(namespace) and n not in ("<init>","<clinit>")}
        plain = launch(root/(group+"-plain"),module,names,cp,tree,None,None,isolated=separate)
        dest = root/(group+"-traced")
        config = root/(group+".tsv")
        values = {"directory":[str(dest)],"limit":["262144"],"changed":targets,"public":sorted(shapes),
                  "test":sorted(all_tests),"prefix":[namespace]}
        config.write_text("".join(k+"\t"+v+"\n" for k,items in values.items() for v in items))
        traced = launch(dest,module,names,cp,tree,agent,config,isolated=separate)
        forks = []
        for path in sorted(dest.glob("*.events")):
            fork = public_histories.read_fork(path,graph_rows,classes,module,rev,summary["jdkReleaseSha256"],21)
            fork["rawDirectory"] = dest.name
            rows = public_histories.witnesses(fork)
            counts = Counter((r["test"],r["entry"],r["changed"],r["relationship"]) for r in rows)
            examples = {}
            for r in rows:
                key = (r["test"],r["entry"],r["changed"],r["relationship"])
                if key not in examples:
                    examples[key] = {**r,"eventCount":counts[key]}
            fork["events"] = len(fork.pop("sequence"))
            forks.append({"plainParity":plain==traced,"fork":fork,"witnesses":list(examples.values())})
        if not forks:
            raise ValueError("original traced launch produced no VM events")
        summary["runs"].append({"module":module,"selected":names,"plain":plain,"traced":traced,"forks":forks})
    change_evidence.write_json(root/"summary.json",summary)
    out = HERE/("parquet-"+side+("-reversed" if reverse else "")+("-separate" if separate else "")+".zip")
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for p in [root/"summary.json",*root.glob("*.tsv"),*root.glob("*-traced/*.events"),*root.glob("*-traced/*.classes"),
                  *root.glob("*-traced/*.loads"),*root.glob("*/launcher.log")]:
            z.write(p,p.relative_to(root))
    print(side,"reversed" if reverse else "original", [(r["module"],len(r["plain"]),r["plain"]==r["traced"],
        sum(len(f["witnesses"]) for f in r["forks"])) for r in summary["runs"]])


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("side",choices=("old","new"))
    parser.add_argument("--reverse",action="store_true")
    parser.add_argument("--separate",action="store_true",help="same selection, one original test class and private module tree per JVM")
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="upstream-history-") as temp:
        run(args.side,args.reverse,Path(temp),separate=args.separate)

"""Open the J08 registrations after its first candidate list was frozen and score both public observations."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from controls import CHECKER, java
from transfer import ROOT, JDK, J08, OUT, FALLBACK
from targets import change_evidence, change_inventory, entry_binding, upgrade_replay

WRITER = "org.apache.parquet.hadoop.ParquetWriter#write(Ljava/lang/Object;)V"


def score(destination):
    first = json.loads((OUT / "parquet-first.json").read_bytes())
    if first["implementation"] != json.loads((OUT / "transfer-freeze.json").read_bytes()):
        raise ValueError("cannot score a different first transfer")
    ranked = [r["entry"] for r in first["candidates"]]
    nominated = json.loads((J08 / "case.json").read_bytes())["entry"]
    original = json.loads((J08 / "physical.json").read_bytes())["observations"]
    graphs, rows = {}, []
    with tempfile.TemporaryDirectory(prefix="score-parquet-") as tmp:
        work = Path(tmp)
        main = work / "ReadOriginal.java"
        main.write_text('public class ReadOriginal {public static void main(String[] a) throws Exception {System.out.println("RESULT "+UpgradeProbe.observe(a));}}')
        locked = json.loads((J08 / "bindings.json").read_bytes())
        for side,g in locked.items():
            for row in g["classpath"]:
                row["file"] = str(Path.home() / ".cache/in-the-loop/organic-pr-20" / row["file"])
            for order in ("original","reversed"):
                doc = {**g,"classpath":list(g["classpath"])}
                if order == "reversed":
                    doc["classpath"][0],doc["classpath"][2]=doc["classpath"][2],doc["classpath"][0]
                tag = side + "-" + order
                source = work / (tag+".json")
                change_evidence.write_json(source,doc)
                paths,graph=change_inventory.resolve(source,JDK,first["deployments"][side]["jdk"],{},kind="production")
                graphs[tag]=paths,graph,JDK
        selected=entry_binding.qualify(CHECKER,graphs,{k:[nominated,WRITER] for k in graphs})
        for key,(files,_,_) in graphs.items():
            side,order=key.split("-")
            out=work/key;out.mkdir()
            cp=os.pathsep.join(map(str,files))
            subprocess.run([JDK/"bin/javac","-proc:none","-d",out,"-cp",cp,J08/"UpgradeProbe.java",main],
                           cwd=out,check=True,capture_output=True)
            for observation in original:
                if observation["side"]!=side:continue
                trial=out/("-".join(observation["args"]));trial.mkdir()
                printed=subprocess.check_output([JDK/"bin/java","-Xmx384m","-cp",str(out)+os.pathsep+cp,
                    "ReadOriginal",*observation["args"]],cwd=trial,text=True,stderr=subprocess.DEVNULL,timeout=40)
                result,=[line.removeprefix("RESULT ") for line in printed.splitlines() if line.startswith("RESULT ")]
                if order=="original" and result!=observation["return"]:raise ValueError("independent Parquet history differs")
                entry=nominated if observation["args"][0]=="page" else WRITER
                record=selected[key][entry]
                if record["status"]!="bound":raise ValueError(f"{key} {entry}: {record['firstOpenDependency']}")
                rows.append({"case":11,"revision":side,"profile":order,"question":observation["question"],"entry":entry,
                             "firstUnaidedRank":ranked.index(entry)+1 if entry in ranked else None,
                             "provider":record["providerIndex"],"classSha256":record["classSha256"],
                             "physicalEntry":record["physicalEntry"],"shadowed":record["checker"]["shadowed"],
                             "originalJvm":result,"matchesRegisteredOrder":result==observation["return"],
                             "bindingEvidence":"fresh original JVM and native resolver","manualProviderIndices":0})
    change_evidence.write_json(destination,rows)
    print("J08: 10 original outcomes matched; 10 reversed-order outcomes recorded")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("output",type=Path);score(p.parse_args().output)

"""Compare the exact PR pair and the two disclosed releases with the same registered public caller."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from register import HERE, SETUP, jdk, manifests, read, upgrade_replay, write


RELEASES = {"J09": ("sqlite-jdbc-3.8.11.2","sqlite-jdbc-3.14.2"),
            "J12": ("calcite-core-1.18.0","calcite-core-1.19.0")}


def bind(case):
    graphs = {}
    for side, coordinate in zip(("old","new"),RELEASES[case],strict=True):
        cp = (SETUP/"releases"/coordinate/"classpath.txt").read_text().strip().split(os.pathsep)
        graphs[side] = {"release":coordinate,"classpath":[{"file":str(Path(f).relative_to(SETUP)),"sha256":upgrade_replay.sha(Path(f))} for f in cp]}
    write(HERE/"cases"/case/"releases.json",graphs)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def accumulator(code, query, side):
    fields = re.findall(r"\bacc\.f(\d+)\.add\(", code)
    # A single-projection plan can use the List accumulator itself.
    adds = code.count(".add(org.apache.calcite.runtime.SqlFunctions.toInt(")
    factory, = re.findall(r"new org\.apache\.calcite\.adapter\.enumerable\.(\w+AggregateLambdaFactory)\(",code)
    ordered = query != "unordered"
    expected = (("Ordered" if side == "old" else "Lazy") if ordered else ("SequencedAdder" if side == "old" else "Basic")) + "AggregateLambdaFactory"
    require(factory == expected and "lambdaFactory.accumulatorAdder()" in code and "lambdaFactory.resultSelector(" in code, "different grouping factory or result wiring")
    if query == "mixed":
        require(fields == (["1"] if side == "old" else ["0","1"]) and adds == len(fields), "wrong field accumulator binding")
        require(re.search(r"acc\.f0,\s*acc\.f1\}",code) and code.count("new org.apache.calcite.adapter.enumerable.SourceSorter(") == 1,
                "the two projected slots or their sorter differ")
        require(code.count("new org.apache.calcite.adapter.enumerable.BasicLazyAccumulator(") == int(side == "new"),
                "missing or extra unordered lazy accumulator")
    return {"factory":factory,"fieldsWithListAdds":fields,"listAdds":adds,
            "basicLazyAccumulators":code.count("new org.apache.calcite.adapter.enumerable.BasicLazyAccumulator("),
            "sourceSorters":code.count("new org.apache.calcite.adapter.enumerable.SourceSorter("),
            "sha256":hashlib.sha256(code.encode()).hexdigest(),"java":code}


def run(case):
    folder = HERE/"cases"/case
    config = read(folder/"case.json")
    graphs = read(folder/"releases.json")
    for graph in graphs.values():
        for entry in graph["classpath"]:
            path = SETUP/entry["file"]
            require(upgrade_replay.sha(path) == entry["sha256"], "different release artifact")
            entry["file"] = str(path)
    tool = "NativeReadback" if case == "J09" else "GeneratedAccumulator"
    record = {"case":case, "registeredCaseSha256":upgrade_replay.sha(folder/"case.json"),
              "releaseGraphSha256":upgrade_replay.sha(folder/"releases.json"),
              "originalGraphSha256":upgrade_replay.sha(folder/"bindings.json"),"graphs":{}}
    with tempfile.TemporaryDirectory(prefix="published-and-pinned-") as stage:
        work = Path(stage)
        for kind, pair in (("release",graphs),("pr",manifests(folder))):
            for side, graph in pair.items():
                name = kind+"-"+side
                classes = work/(name+"-classes")
                classes.mkdir()
                cp = os.pathsep.join(e["file"] for e in graph["classpath"])
                java = jdk(config)/"bin"
                subprocess.run([java/"javac","-proc:none","-cp",cp,"-d",classes,folder/"UpgradeProbe.java",folder/(tool+".java")],check=True)
                result = {"productionJar":graph["classpath"][0]["sha256"],"inputs":[]}
                for question in config["questions"]:
                    for item in question["inputs"]:
                        trial = work/(name+"-"+str(len(result["inputs"])))
                        trial.mkdir()
                        env = {"HOME":str(trial),"LANG":"C.UTF-8","LC_ALL":"C.UTF-8","TZ":"UTC","TMPDIR":str(trial),"PATH":str(java)+":/usr/bin:/bin"}
                        subprocess.run([java/"java","-Xmx96m","-Djava.io.tmpdir="+str(trial),"-cp",str(classes)+os.pathsep+cp,tool,*item["args"]],
                                       cwd=trial,env=env,check=True,timeout=35)
                        value = (trial/"observation.txt").read_text()
                        expected = item.get("after",item["before"]) if side == "new" else item["before"]
                        require(value == expected, f"{name} {item['args']}: {value!r}")
                        row = {"args":item["args"],"observation":value}
                        if case == "J12":
                            row["generatedAccumulator"] = accumulator((trial/"program.java").read_text(),item["args"][0],side)
                        else:
                            with zipfile.ZipFile(graph["classpath"][0]["file"]) as jar:
                                packaged = hashlib.sha256(jar.read("org/sqlite/native/Linux/x86_64/libsqlitejdbc.so")).hexdigest()
                            require((trial/"native.sha256").read_text() == packaged, "different mapped native image")
                            row["mappedNativeSha256"] = packaged
                        result["inputs"].append(row)
                record["graphs"][name] = result
    out = HERE/"results"/case/"release-and-pr.json.gz"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_bytes(gzip.compress(json.dumps(record,sort_keys=True).encode(),mtime=0))
    print(case,sum(len(g["inputs"]) for g in record["graphs"].values()),"observed histories on both release and PR pairs")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case",choices=RELEASES)
    parser.add_argument("--bind",action="store_true")
    args = parser.parse_args()
    (bind if args.bind else run)(args.case)

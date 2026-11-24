"""Check finite Maven comparator returns and consume them in range construction and selection."""
import contextlib
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from register import HERE, ROOT, jdk, manifests, read, upgrade_replay
from predicate_proof import method, require
sys.path.insert(0,str(ROOT/"lib/benchmark/organic-composition"))
from live import compile_tracer, frozen_cold, member_site, observe

BASE = "org.apache.maven.artifact.versioning."
METHOD = BASE + "ComparableVersion"
SIG = "(Lorg/apache/maven/artifact/versioning/ComparableVersion;)I"


def checked_table(side, graph, folder, work, java):
    jar = Path(graph["classpath"][0]["file"])
    lefts = ("0-alpha","0","x")
    cycle = [[0,-5,1],[5,0,-2],[-1,2,0]] if side == "old" else [[0,-5,-7],[5,0,-2],[7,2,0]]
    expected = {(l,r):cycle[i][j] for i,l in enumerate(lefts) for j,r in enumerate(lefts)}
    normal = ("1-alpha","1-beta")
    expected.update({(l,r):i-j for i,l in enumerate(normal) for j,r in enumerate(normal)})
    shapes = {"0-alpha": "L[L[Salpha]]" if side == "old" else "L[Salpha]", "0":"L[]","x":"L[Sx]",
              "1-alpha":"L[I1,L[Salpha]]", "1-beta":"L[I1,L[Sbeta]]"}
    subprocess.run([java/"javac","-proc:none","-cp",jar,"-d",work,folder/"OrderTable.java"],check=True)
    command = [java/"java","-Xmx96m","-cp",str(work)+os.pathsep+str(jar),"OrderTable"]
    first = subprocess.check_output(command,text=True)
    require(first == subprocess.check_output(command,text=True),"two independent finite tables differ")
    measured = {}
    for row in first.splitlines():
        l,ls,r,rs,v = row.split("\t")
        require(shapes[l] == ls and shapes[r] == rs and (l,r) not in measured,"wrong or repeated parsed operand")
        measured[l,r] = int(v)
    require(measured == expected, "incorrect full finite comparator table")
    identity, _, ops, refs, _ = method(jar,METHOD,"compareTo",SIG)
    items = "org/apache/maven/artifact/versioning/ComparableVersion$ListItem"
    require(list(ops.values()) == [0x2a,0xb4,0x2b,0xb4,0xb6,0xac] and refs[1] == refs[5]
            and refs[1] == (METHOD.replace(".","/"),"items","L"+items+";") and refs[8][0:2] == (items,"compareTo"),
            "different original comparison dispatch")
    return {"method":identity,"jar":upgrade_replay.sha(jar),"shapes":shapes,
            "returns":{l+"/"+r:v for (l,r),v in measured.items()},"checkedReference":upgrade_replay.sha(folder/"OrderTable.java")}


def main(probe=False):
    folder = HERE/"cases/J13"
    doc = read(folder/"case.json")
    archive = HERE/"results/J13/first/plans.zip"
    cold = frozen_cold(archive)
    expected = {(tuple(c["arguments"]),s):c[s] for n in cold["claims"] for c in n["children"] for s in ("old","new")}
    result = {"originalPlans":upgrade_replay.sha(archive),"proofs":{},"trials":[],"controls":[]}
    with tempfile.TemporaryDirectory(prefix="maven-compare-") as temporary:
        for side,graph in manifests(folder).items():
            if probe and side == "old": continue
            jars = [Path(item["file"]) for item in graph["classpath"]]
            build = Path(temporary)/side
            build.mkdir()
            table = checked_table(side,graph,folder,build,jdk(doc)/"bin")
            result["proofs"][side] = table
            classes, sources = compile_tracer(folder,build,jars)
            result["tracer"] = sources

            def replay(args, mode, stale=False):
                with tempfile.TemporaryDirectory(dir=temporary) as trial:
                    work = Path(trial)
                    props = {k:table["method"][k] for k in ("code","pool")}
                    props.update({"shape."+k:v for k,v in table["shapes"].items()})
                    props.update({"return."+k:str(v) for k,v in table["returns"].items()})
                    props["mode"] = mode
                    if stale: props["shape.0-alpha"] = "wrong-tree"
                    cfg = work/"config"
                    cfg.write_text("".join(f"{k}={v}\n" for k,v in props.items()))
                    with contextlib.chdir(work):
                        value,events,site,origins = observe(classes,jars,doc["entry"],args,work/"vm",cfg)
                    require(value == expected[tuple(args),side] and all(origins.get(BASE+n) == {jars[0]}
                            for n in ("ComparableVersion","VersionRange","DefaultArtifactVersion")), "wrong product outcome or provider")
                    matches = [e for e in events if e[0] == "public-match"]
                    comparisons = [e for e in events if e[0] == "compare"]
                    rejected = side == "old" and args == ["qualifiers"]
                    require(len(matches) == (0 if rejected else 6), "original range selection count differs")
                    phases = {e[1] for e in comparisons}
                    require(phases == ({"construction"} if rejected else {"construction","selection"}), "required product comparator use missing")
                    for e in comparisons:
                        require(table["returns"][e[2]+"/"+e[4]] == int(e[6]) and
                                table["shapes"][e[2]] == e[3] and table["shapes"][e[4]] == e[5], "missing finite premise")
                        ref = member_site(jars[0],e[-4:])
                        require(ref["owner"] == METHOD and ref["name"] == "compareTo" and ref["descriptor"] == SIG,"wrong product consumer")
                    return {"value":value,"events":events,"publicInvocation":site}
            for query in ("qualifiers","ordinary"):
                args = [query]
                if probe:
                    observed = replay(args,"apply")
                    print(side,args,len(observed["events"]),"bound events")
                    return
                refs = [replay(args,"original") for _ in range(2)]
                subs = [replay(args,"apply") for _ in range(2)]
                require(refs[0] == refs[1] == subs[0] == subs[1],"original and substituted range histories differ")
                result["trials"].append({"side":side,"args":args,"originals":refs,"substitutions":subs})
            try: replay(["qualifiers"],"apply",stale=True)
            except ValueError as e:
                require("stale parsed-version shape" in str(e),"unexpected refusal")
                result["controls"].append({"side":side,"wrongOperandShape":str(e)})
            else: raise ValueError("accepted a stale parsed operand")
    path = HERE/"results/J13/checked-order.json.gz"
    path.write_bytes(gzip.compress(json.dumps(result,sort_keys=True).encode(),mtime=0))
    print("All 26 original comparisons, 8 substituted public histories and both stale parsed operands checked")


if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe",action="store_true")
    main(parser.parse_args().probe)

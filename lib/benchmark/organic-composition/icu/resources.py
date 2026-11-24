"""Follow the genuine six-resource change at one deployment path and verify selected rule bytes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

CASE=Path(__file__).resolve().parent
sys.path.insert(0,str(CASE.parent))
from freeze import verify
from matrix import semantic, write
from plan_run import JDK, ROOT, OUTPUT

BASE="com/ibm/icu/impl/data/icudata/brkitr/"


def entries(path):
    with zipfile.ZipFile(path) as jar:
        return {n:hashlib.sha256(jar.read(n)).hexdigest() for n in jar.namelist() if not n.endswith("/")}


def selection(archive, name, maps):
    """Qualify each live URL at the actual legacy or successor path, including Nordic fallback."""
    result={}
    with zipfile.ZipFile(archive) as z:
        plan=json.loads(z.read(name+".json"))
        for node in plan["claims"]:
            if not node.get("derivation"):
                continue
            raw=z.read(node["receipt"]["path"])
            if hashlib.sha256(raw).hexdigest()!=node["receipt"]["sha256"]:
                raise ValueError("unbound application receipt")
            r=json.loads(raw)
            for side,binding in r["sides"].items():
                for t in binding.get("trials",[]):
                    loc=node["domain"][t["input"]]["args"][0]
                    key="/".join((node["id"],side,loc))
                    observed=[]
                    for invocation in t.get("checkedApplications",[]):
                        resources={url.split("!/",1)[1] for url in invocation["startupArguments"] if "!/" in url}
                        actual=sorted(path for path in resources if path.startswith(BASE) and path.endswith(".brk"))
                        needed=("word_POSIX.brk" if loc=="en_US_POSIX" else "word_fi_sv.brk" if side=="old" and loc in ("fi","sv") else "word.brk")
                        if actual!=[BASE+needed]:
                            raise ValueError(f"{key}: actual rule selection differs: {actual}")
                        observed.append({"rule":actual[0],"sha256":maps[side][actual[0]],
                                         "localeBundles":{n:maps[side][n] for n in sorted(resources)
                                                          if n.startswith(BASE) and n.endswith(".res")}})
                    result[key]={"status":node["status"],"replays":observed,"firstOpen":node["firstOpenDependency"]}
        return result


def main():
    verify()
    folder=ROOT/OUTPUT/"icu"; target=folder/"resource-transfer"; target.mkdir(parents=True,exist_ok=True)
    docs={side:json.loads((CASE/side/"prepared.json").read_bytes()) for side in ("old","new")}
    jars={s:Path(d["classpath"][0]["file"]) for s,d in docs.items()}
    maps={s:entries(p) for s,p in jars.items()}
    delta={k:{"old":maps["old"].get(k),"new":maps["new"].get(k)} for k in sorted(maps["old"].keys()|maps["new"].keys())
           if maps["old"].get(k)!=maps["new"].get(k)}
    expected={BASE+n for n in ("fi.res","sv.res","word.brk","word_POSIX.brk","word_fi_sv.brk","res_index.res")}
    if set(delta)!=expected:
        raise ValueError("the two original deployments differ beyond the six registered resources")
    trace=selection(folder/"first/plans.zip","cold",maps)
    with tempfile.TemporaryDirectory(prefix="icu-actual-change-") as t:
        w=Path(t); jar=w/"selected.jar";manifest=w/"prepared.json"; results={};short={}
        for name,side,cache in (("before","old","cache"),("changed-warm","new","cache"),("changed-clean","new","clean-cache")):
            if name!="changed-clean":
                shutil.copyfile(jars[side],jar)
            doc=dict(docs[side]);doc["classpath"]=[{"file":str(jar),"sha256":docs[side]["classpath"][0]["sha256"]}]
            write(manifest,doc)
            cmd=[sys.executable,ROOT/"examples/tools/build.py","--change-plan","application","--before",CASE/"old/prepared.json",
                 "--after",manifest,"--jdk",JDK,"--workflows",CASE/"checked-workflows.json","--checker",
                 os.environ.get("JVMCONTRACT",ROOT/"lib/target/release/jvmcontract"),"--run","--seconds","180",
                 "--cache",w/cache,"--output",w/(name+".json")]
            if name=="changed-warm":cmd.extend(["--previous",w/"before.json"])
            subprocess.run(cmd,cwd=ROOT,check=True)
            d=json.loads((w/(name+".json")).read_bytes());results[name]=semantic(d)
            short[name]=[{k:n.get(k) for k in ("id","execution","status","firstOpenDependency","helperProofs")} for n in d["claims"]]
        if results["changed-warm"]!=results["changed-clean"]:
            raise ValueError("resource-only incremental and clean original histories differ")
        if any(n["execution"].get("new",{}).get("action")=="exact reuse" for n in short["changed-warm"]):
            raise ValueError("stale result crossed the changed selected JAR")
        with zipfile.ZipFile(target/"plans.zip","w",zipfile.ZIP_DEFLATED) as z:
            for name in results:z.write(w/(name+".json"),name+".json")
            for f in sorted((w/"receipts").glob("*.json")):z.write(f,"receipts/"+f.name)
        write(target/"report.json",{"identicalClassFiles":sum(n.endswith(".class") for n in maps["old"]),
              "changedResources":delta,"liveSelection":trace,"comparisons":short})

if __name__=="__main__":
    main()

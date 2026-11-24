"""Compare the public change plan with exact reuse, clean recomputation and changed premises."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

from plan_run import HERE, JDK, OUTPUT, ROOT


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False)+"\n")


def semantic(plan):
    return [{key: node.get(key) for key in ("id", "claimKey", "executionKey", "status", "witness", "children")}
            for node in plan["claims"]]


def run(case, label, controls):
    folder = HERE / case
    target = ROOT / OUTPUT / case / label
    target.mkdir(parents=True, exist_ok=True)
    checker = Path(os.environ.get("JVMCONTRACT", ROOT/"lib/target/release/jvmcontract")).resolve()
    with tempfile.TemporaryDirectory(prefix="organic-matrix-") as temp:
        work = Path(temp)
        result_zip = target/"plans.zip"
        with zipfile.ZipFile(result_zip,"w"):
            pass
        packed = set()
        plans = {}
        summary = {}
        def measure(name, workflows, cache, *, new=None, previous=None, execute=True):
            out = work/(name+".json")
            cmd = [sys.executable, ROOT/"examples/tools/build.py", "--change-plan", "application",
                   "--before", folder/"old/prepared.json", "--after", new or folder/"new/prepared.json",
                   "--workflows", workflows, "--jdk", JDK, "--checker", checker, "--seconds", "180", "--output", out]
            if execute:
                cmd.extend(["--run","--cache",work/cache])
            if previous:
                cmd.extend(["--previous",work/(previous+".json")])
            start, cpu = time.monotonic(), os.times()
            subprocess.run(cmd, cwd=ROOT, check=True)
            end = os.times()
            plan = json.loads(out.read_bytes())
            if not plan["claims"] or (execute and plan["executionState"] != "complete"):
                raise ValueError(name+" has no complete plan")
            nodes = []
            for node in plan["claims"]:
                row = {k:node.get(k) for k in ("id","claimKey","executionKey","status","covered","inputs",
                                               "witness","execution","firstOpenDependency","helperProofs","receipt")}
                if node.get("receipt"):
                    receipt = work/node["receipt"]["path"]
                    assert hashlib.sha256(receipt.read_bytes()).hexdigest() == node["receipt"]["sha256"]
                    evidence = json.loads(receipt.read_bytes())
                    row["proofBasis"] = {s:p.get("basis",p["action"]) for s,p in evidence.get("helperProofs",{}).items()}
                    row["substitutions"] = {s:sum(len(a["applications"]) for t in b.get("trials",[])
                                                   for a in t.get("checkedApplications",[]))
                                            for s,b in evidence.get("sides",{}).items()}
                nodes.append(row)
            summary[name] = {"wallSeconds":round(time.monotonic()-start,3),
                             "childCpuSeconds":round(end.children_user+end.children_system-cpu.children_user-cpu.children_system,3),
                             "claims":nodes}
            with zipfile.ZipFile(result_zip,"a",zipfile.ZIP_DEFLATED) as pack:
                pack.write(out,out.name)
                for receipt_file in sorted((work/"receipts").glob("*.json")):
                    if receipt_file.name not in packed:
                        pack.write(receipt_file,"receipts/"+receipt_file.name)
                        packed.add(receipt_file.name)
            write(target/"summary.json",{"sha256":hashlib.sha256(result_zip.read_bytes()).hexdigest(),"runs":summary})
            plans[name] = {"claims": [
                {key: node.get(key) for key in ("id", "claimKey", "executionKey", "status", "witness",
                                                "children", "execution", "derivation")}
                for node in plan["claims"]]}

        specs = folder/"checked-workflows.json"
        measure("planned",specs,None,execute=False)
        measure("cold",specs,"cache")
        measure("warm",specs,"cache",previous="cold")
        measure("clean",specs,"clean-cache")
        if not semantic(plans["cold"]) == semantic(plans["warm"]) == semantic(plans["clean"]):
            raise ValueError("exact rerun disagrees with clean public observations")
        if controls:
            (work/"unselected.txt").write_text("An unrelated file outside both ordered classpaths.\n")
            measure("unrelated-warm",specs,"cache",previous="warm")
            measure("unrelated-clean",specs,"unrelated-clean-cache")
            if not semantic(plans["cold"]) == semantic(plans["unrelated-warm"]) == semantic(plans["unrelated-clean"]):
                raise ValueError("unrelated file changed a public conclusion")
            doc = json.loads(specs.read_bytes())
            for row in doc["workflows"]:
                for key in ("probe","scope"):
                    row[key] = str(folder/row[key])
                if "checkedHelper" in row:
                    h = json.loads((folder/row["checkedHelper"]).read_bytes())
                    # A legitimate int/char/bool literal with a deliberately wrong answer.
                    h["rows"][0]["result"] = int(h["rows"][0]["result"] == 0)
                    write(work/"wrong-helper.json",h)
                    row["checkedHelper"] = "wrong-helper.json"
            write(work/"wrong-workflows.json",doc)
            for mode,cache in (("wrong-warm","cache"),("wrong-clean","wrong-clean-cache")):
                measure(mode,work/"wrong-workflows.json",cache)
            if semantic(plans["wrong-warm"]) != semantic(plans["wrong-clean"]):
                raise ValueError("changed helper disagrees with clean recomputation")
            if any(n["status"] != "open" for n in plans["wrong-warm"]["claims"] if n.get("derivation")):
                raise ValueError("incorrect checked helper established a public derivation")
            if resource := json.loads((folder/"helper.json").read_bytes()).get("resource"):
                new = json.loads((folder/"new/prepared.json").read_bytes())
                jar = work/"resource-control.jar"
                shutil.copyfile(new["classpath"][0]["file"],jar)
                new["classpath"][0]["file"] = str(jar)
                new_path = work/"resource-manifest.json"
                write(new_path,new)
                measure("resource-before",specs,"resource-cache",new=new_path)
                if not all(n["status"] == "established" for n in plans["resource-before"]["claims"]):
                    raise ValueError("relocated intact resource control did not establish the original claims")
                altered = work/"altered.jar"
                with zipfile.ZipFile(jar) as src, zipfile.ZipFile(altered,"w") as dest:
                    if resource not in src.namelist():
                        raise ValueError("selected resource missing from control")
                    for item in src.infolist():
                        data = src.read(item)
                        if item.filename == resource:
                            data = b"\0"
                        dest.writestr(item,data)
                altered.replace(jar)
                new["classpath"][0]["sha256"] = hashlib.sha256(jar.read_bytes()).hexdigest()
                write(new_path,new)
                measure("resource-warm",specs,"resource-cache",new=new_path,previous="resource-before")
                measure("resource-clean",specs,"resource-clean-cache",new=new_path)
                if semantic(plans["resource-warm"]) != semantic(plans["resource-clean"]):
                    raise ValueError("changed resource disagrees with clean recomputation")
                if any(n.get("execution",{}).get("new",{}).get("action") == "exact reuse" for n in plans["resource-warm"]["claims"]):
                    raise ValueError("changed resource reused an old public outcome")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case")
    parser.add_argument("label")
    parser.add_argument("--controls",action="store_true")
    args=parser.parse_args()
    run(args.case,args.label,args.controls)

"""Exercise the scaffold-only boundary and the ordinary numbered resume in a caller-free checkout."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import jsonschema

import campaign

HERE, ROOT = campaign.HERE, campaign.ROOT


def handoff(root, numbers, scaffold_only=False):
    example_root = root/"examples"
    example_root.mkdir()
    shutil.copytree(ROOT/"examples/tools",example_root/"tools",ignore=shutil.ignore_patterns("test_*.py","__pycache__"))
    shutil.copytree(ROOT/"examples/schema",example_root/"schema")
    shutil.copyfile(ROOT/"examples/tags.json",example_root/"tags.json")
    (root/"lib").mkdir()
    (root/"lib/python").symlink_to(ROOT/"lib/python",target_is_directory=True)
    tools = example_root/"tools"
    env = {**os.environ,"JVMCONTRACT":str(os.environ.get("JVMCONTRACT",ROOT/"lib/target/release/jvmcontract"))}
    def command(argv):
        result = subprocess.run(list(map(str,argv)),cwd=root,env=env,capture_output=True,text=True,timeout=240)
        if result.returncode: raise ValueError((result.stderr+result.stdout)[-2000:])
        return result.stdout

    plan={"schema":"prove-plan/v1","request":"Reproduce the reviewed finite public predictions from the two numbered registrations.",
          "order":numbers,"examples":[]}
    folders={}
    for number in numbers:
        original=next((ROOT/"examples").glob(number+"-*"))
        folder=example_root/original.name
        folder.mkdir()
        for name in ("example.json","runtime.json","comparison.json"):
            shutil.copyfile(original/name,folder/name)
        folders[number]=folder
        spec=campaign.read(folder/"comparison.json")
        plan["examples"].append({"id":number,"review":"designed","publicComparison":{
            "deployment":"pins","inputDefaults":{"fallback":99} if number=="445" else {}},
            "entry":{"target":spec["entry"],"inputs":"The semantic histories in the numbered registration.","invocation":"adapter"},
            "controls":{"positive":["The registered unchanged input"],"negative":["An altered evaluator prediction"],
                        "mutation":["Retain the same compiled measurement on a changed subject."]},
            "validation":["Run the numbered public comparison."],"done":["All registered public observations are measured."]})
    path=root/"plan.json"
    campaign.write(path,plan)
    jsonschema.Draft202012Validator(campaign.read(ROOT/"llm-dlc/prove-plan.schema.json")).validate(plan)
    for n in numbers:
        command([sys.executable,tools/"scaffold_example.py",n,"--plan",path])
    pre=json.loads(command([sys.executable,ROOT/"llm-dlc/tools/watch.py","--root",root,"preflight","--after-setup",",".join(numbers),*numbers]))
    if pre["toClassify"] or pre["toRepair"] or pre["leftOut"] or [e["state"] for e in pre["examples"]]!=["prepared"]*len(numbers):
        raise ValueError(str(pre))
    if scaffold_only:
        campaign.write(root/"scaffold-only.json",pre)
        print("Prepared " + ", ".join(numbers) + " in " + str(root))
        return
    result={"schema":"generated-numbered-handoff/v1","preflight":pre,"examples":{}}
    packages=[path]
    for n,folder in folders.items():
        records=folder/"records"
        bundle=records/"public-observer"
        files=[bundle/"UpgradeProbe.java",bundle/"caller.zip",bundle/"generation.json"]
        before={p.name:(campaign.upgrade_replay.sha(p),p.stat().st_mtime_ns) for p in files}
        command([sys.executable,tools/"build.py",n])
        after={p.name:(campaign.upgrade_replay.sha(p),p.stat().st_mtime_ns) for p in files}
        report=campaign.read(records/"public-replay.json")
        if before!=after or len(report["claims"])!=3 or any(c["status"]!="established" for c in report["claims"]):
            raise ValueError("resume changed frozen bytes or left a registered question unsettled")
        result["examples"][n]={"inputs":["example.json","runtime.json","comparison.json"],"unchangedFiles":{k:v[0] for k,v in before.items()},
            "scaffoldState":campaign.read(records/"entry-bindings.json")["executionState"],
            "resumeState":report["executionState"],"claimStatuses":{c["id"]:c["status"] for c in report["claims"]}}
        packages.extend([p for p in records.rglob("*") if p.is_file() and "deployment-layouts" not in p.parts])
    after_run=json.loads(command([sys.executable,ROOT/"llm-dlc/tools/watch.py","--root",root,"preflight",*numbers]))
    if after_run["decided"] != numbers:
        raise ValueError("the watcher did not recover the scoped finite results from their receipts")
    result["afterResume"]=after_run
    campaign.write(root/"handoff.json",result)
    campaign.pack(root,[*packages,root/"handoff.json"],HERE/"receipts/numbered-handoff.zip")


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("numbers",nargs="*",default=["458","445"])
    ap.add_argument("--scaffold-only",action="store_true")
    ap.add_argument("--work",type=Path,help="keep the prepared checkout for a later numbered resume")
    opts=ap.parse_args()
    with tempfile.TemporaryDirectory(prefix="public-numbered-") as temp:
        root = opts.work or Path(temp)
        root.mkdir(parents=True,exist_ok=True)
        handoff(root,opts.numbers,opts.scaffold_only)

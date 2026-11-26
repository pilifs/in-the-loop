"""An intentionally wrong empty-result prediction must fail at a populated original resource call."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"examples/tools"))
from targets import change_evidence, runtime_jdk, upgrade_replay


def check(work, slot):
    saved = ROOT/"verification/beyond-jbmc/scaffold-first/resource-discovery"/slot/"candidate-1"
    histories = json.loads((saved/"scaffold.json").read_bytes())["physical"]
    packet = Path.home()/".cache/in-the-loop/beyond-jbmc/panel/evaluation"/slot/"packet"
    inputs = json.loads((packet/"inputs.json").read_bytes())
    neutral = work/"000.jar"
    with zipfile.ZipFile(neutral, "w") as archive:
        archive.writestr(zipfile.ZipInfo("control.txt"), "unrelated")
    for side, rows in inputs.items():
        roots = [{"file":str(packet/r["path"]), "sha256":r["sha256"]} for r in rows]
        if slot == "15":
            roots.insert(0, {"file":str(neutral),"sha256":upgrade_replay.sha(neutral)})
        change_evidence.write_json(work/(side+".json"), {"classpath":roots,"commit":side,"layoutKnown":True})
    document = json.loads((saved/"workflows.json").read_bytes())
    for channel in document["workflows"]:
        name = channel["id"]
        originals = {s:[r for r in trials if r["args"][0]==name and r["args"][2]=="forward"] for s,trials in histories.items()}
        chosen = max(originals["new"], key=lambda r:int(r["args"][1]))
        old, = [r for r in originals["old"] if r["args"]==chosen["args"]]
        value = chosen["actual"]
        predicted = value.partition("=")[0]+"=" if name=="primary" else value
        if name=="primary" and predicted==value:
            raise ValueError("the original input did not consume any fixture entries")
        spec = json.loads((saved/channel["scope"]).read_bytes())
        spec["cases"] = [{"args":chosen["args"],"expected":{"return":old["actual"]}}]
        change_evidence.write_json(work/channel["scope"], spec)
        channel.update(probe=str(saved/channel["probe"]), intent={"allowedChanges":[{"input":0,"expectedNew":{"return":predicted}}]})
    workflows = work/"workflows.json"
    change_evidence.write_json(workflows, document)
    output = work/"report.json"
    cmd = [sys.executable,ROOT/"examples/tools/build.py","--change-plan","application","--before",work/"old.json",
           "--after",work/"new.json","--jdk",runtime_jdk.home("25"),"--workflows",workflows,"--output",output,
           "--checker",os.environ.get("JVMCONTRACT",ROOT/"lib/target/release/jvmcontract"),"--run","--supplied-only",
           "--old-dependency",inputs["old"][0]["sha256"],"--new-dependency",inputs["new"][0]["sha256"]]
    subprocess.run(cmd,check=True)
    plan=json.loads(output.read_bytes())
    rows=[]
    for claim in plan["claims"]:
        expected = "refuted" if claim["id"]=="primary" else "established"
        if claim["status"]!=expected:
            raise ValueError(f"{slot}/{claim['id']}: {claim.get('reason') or claim.get('firstOpenDependency')}")
        for side,ref in claim["entryBindings"].items():
            binding=plan["entryBindings"][ref]
            rows.append({"case":9,"slot":slot,"revision":side,"question":claim["id"],"entry":claim["entry"],
                         "providerIndex":binding["providerIndex"],"status":expected,
                         "actual":claim["children"][0][side],"predictedNew":claim["children"][0]["intendedChange"]})
    return rows


if __name__=="__main__":
    with tempfile.TemporaryDirectory(prefix="resource-intent-") as temp:
        rows=[]
        for slot in ("04","15"):
            work=Path(temp)/slot
            work.mkdir()
            rows.extend(check(work,slot))
        change_evidence.write_json(Path(sys.argv[1]),rows)
        print("Both false populated predictions refuted and both unrelated-marker controls established on the public path")

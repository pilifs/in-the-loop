"""Replay each disclosed release question on its signed deployment layout and with that layout withheld."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from transfer import ROOT
from targets import change_evidence, upgrade_replay

BLIND = ROOT / "lib/benchmark/beyond-jbmc/blind"
sys.path[:0] = [str(BLIND), str(BLIND.parent)]
import original_plans as original

CACHE = Path.home() / ".cache/in-the-loop"
PANELS = CACHE / "beyond-jbmc/panel/evaluation"
LAYOUT = CACHE / "classpath-entry-discovery/layouts"


def run(slot, destination):
    with tempfile.TemporaryDirectory(prefix="qualified-release-" + slot + "-") as tmp:
        work = Path(tmp)
        record = original.prepare(slot, work)
        if record != json.loads((original.DEST / "registrations" / (slot + ".json")).read_bytes()):
            raise ValueError("upstream finite registration changed")
        workflows = original.materialize(work, record)
        captured = json.loads((PANELS / slot / "graphs.json").read_bytes())
        operands = {}
        for side in ("old", "new"):
            file = work / (side + ".json")
            data = json.loads(file.read_bytes())
            data["deploymentRoot"] = str(LAYOUT / slot / side / "root")
            library = data["classpath"][:-1]
            data["classpath"][-1]["role"] = "client"
            operands[side] = library[0]["sha256"]
            for artifact, measured in zip(library, captured[side]["classpath"], strict=True):
                if artifact["sha256"] != measured["sha256"]:
                    raise ValueError("different deployment from signed-package capture")
                artifact["deploymentPath"] = "/" + measured["source"]
            change_evidence.write_json(file, data)
            withheld = {k: v for k, v in data.items() if k != "deploymentRoot"}
            withheld["classpath"] = [{k: v for k,v in item.items() if k != "deploymentPath"} for item in data["classpath"]]
            change_evidence.write_json(work / (side + "-unknown.json"), {**withheld, "layoutKnown": False})
        answers = []
        for mode in ("captured", "withheld"):
            suffix = "" if mode == "captured" else "-unknown"
            plan = work / (mode + ".json")
            args = [sys.executable, ROOT / "examples/tools/build.py", "--change-plan", "application",
                    "--before", work / ("old" + suffix + ".json"), "--after", work / ("new" + suffix + ".json"),
                    "--workflows", workflows, "--supplied-only", "--jdk", original.JDK, "--output", plan,
                    "--checker", os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract"),
                    "--old-dependency", operands["old"], "--new-dependency", operands["new"], "--seconds", "360"]
            if mode == "captured":
                args.append("--run")
            subprocess.run(args, check=True)
            result = json.loads(plan.read_bytes())
            for claim in result["claims"]:
                for side, ref in claim["entryBindings"].items():
                    binding = result["entryBindings"][ref]
                    launch = result["launches"][side]["production"]
                    row = {"case": slot, "revision": side, "profile": mode, "question": claim["id"],
                           "inputMode": "supplied caller", "providerIndex": binding.get("providerIndex"),
                           "entry": claim["entry"], "binding": binding["status"], "classSha256": binding.get("classSha256"),
                           "physicalEntry": binding.get("physicalEntry"), "jvm": binding.get("jvm"),
                           "graph": launch["key"], "declaredRoots": len(launch["orderedRoots"]), "effectiveProviders": len(launch["classpath"]),
                           "manifestEdges": len(launch["manifestClassPath"]["edges"]), "absences": len(launch["manifestClassPath"]["absent"]),
                           "status": claim["status"], "firstOpenDependency": claim.get("reason") or claim.get("firstOpenDependency"),
                           "manualProviderIndices": 0, "publicHits": sum(w["qualifiedMethodEntries"] for w in result["bindingWitnesses"].get(ref, []) if w["claim"] == claim["id"]),
                           "observations": [c.get(side) for c in claim.get("children", [])]}
                    answers.append(row)
        change_evidence.write_json(destination, answers)
        if any(r["status"] != "established" or not r["publicHits"] for r in answers if r["profile"] == "captured"):
            raise ValueError("captured public result disagrees: " + str([(r["question"], r["revision"], r["firstOpenDependency"]) for r in answers if r["profile"] == "captured" and r["status"] != "established"])[:1200])
        if slot != "16" and any(r["binding"] != "open" for r in answers if r["profile"] == "withheld"):
            raise ValueError("withheld layout admitted a binding")
        print(slot, "both captured questions checked on both releases")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slot", choices=["03","04","08","10","13","16"])
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run(args.slot, args.output)

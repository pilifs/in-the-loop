"""Stage-3 scaffold, resume both frozen questions, then substitute the fixed core at its original pathname."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from transfer import ROOT, JDK
from targets import change_evidence, upgrade_replay

CASE = ROOT / "lib/benchmark/organic-composition/log4j"
ORACLE = ROOT / "verification/organic-composition/log4j"
QUESTIONS = ("explicit", "omitted")


def run(destination):
    reference = {(r["side"],tuple(r["args"])): r["observations"] for r in json.loads((ORACLE/"processes.json").read_bytes())}
    strict = json.loads((ORACLE/"first-native.json").read_bytes())
    with tempfile.TemporaryDirectory(prefix="entry-log4j-") as tmp:
        work = Path(tmp)
        sides = {}
        for side in ("old", "new"):
            doc = json.loads((CASE / side / "prepared.json").read_bytes())
            (work / side).mkdir()
            for row in doc["classpath"]:
                original = Path(row["file"])
                if upgrade_replay.sha(original) != row["sha256"]:
                    raise ValueError("original build digest differs")
                placed = work / side / original.name
                shutil.copyfile(original, placed)
                row["file"] = str(placed)
            sides[side] = doc
            change_evidence.write_json(work / (side + ".json"), doc)
        args = ["--before",work/"old.json","--after",work/"new.json","--jdk",JDK,"--workflows",CASE/"workflows.json",
                "--checker",os.environ.get("JVMCONTRACT", ROOT/"lib/target/release/jvmcontract")]
        stages, rows = {}, []
        previous = work / "scaffold.json"
        subprocess.run([sys.executable,ROOT/"examples/tools/scaffold_example.py","bind",*args,"--output",previous],check=True)
        scaffold = json.loads(previous.read_bytes())
        keys = {n["id"]: n["claimKey"] for n in scaffold["claims"]}
        for mode in ("cold","warm","clean","replacement-warm","replacement-clean"):
            if mode == "replacement-warm":
                old, new = (sides[s]["classpath"][1] for s in ("old","new"))
                shutil.copyfile(old["file"], new["file"])
                new["sha256"] = old["sha256"]
                change_evidence.write_json(work/"new.json", sides["new"])
            plan = work / (mode + ".json")
            cache = work / (mode if mode.endswith("clean") else "cache")
            subprocess.run([sys.executable,ROOT/"examples/tools/build.py","--change-plan","application",*args,
                            "--previous",previous,"--cache",cache,"--output",plan,"--run","--seconds","180"],check=True)
            report = json.loads(plan.read_bytes())
            previous = plan
            offline = work / (mode + "-bindings.json")
            subprocess.run([sys.executable,ROOT/"examples/tools/build.py","--change-plan","bindings",plan,"--verify-receipts","--output",offline],check=True)
            if len(json.loads(offline.read_bytes())["claims"]) != 4:
                raise ValueError("saved report lost a claim or revision")
            for claim in report["claims"]:
                name = claim["id"]
                expected_status = "refuted" if name == "explicit" and mode.startswith("replacement") else "established"
                if keys[name] != claim["claimKey"] or claim["status"] != expected_status or len(claim["children"]) != 4:
                    raise ValueError(f"{mode} {name}: {claim.get('reason') or claim.get('firstOpenDependency')}")
                for side, ref in claim["entryBindings"].items():
                    binding = report["entryBindings"][ref]
                    matched = report["bindingWitnesses"][ref]
                    hits = next(w["qualifiedMethodEntries"] for w in matched if w["claim"] == name)
                    if binding["providerIndex"] != 1 or hits != 8 or binding["jvm"]["physicalEntry"] != binding["checker"]["entry"]:
                        raise ValueError("missing independent provider or original invocation")
                    actual = [c[side] for c in claim["children"]]
                    expected_side = "old" if mode.startswith("replacement") else side
                    if any(reference[expected_side,tuple(child["arguments"])] != [child[side]] * 2 for child in claim["children"]):
                        raise ValueError("original finite observations disagree with the independent campaign")
                    action = claim["execution"][side]["action"]
                    if mode == "replacement-warm" and action != ("exact reuse" if side == "old" else "executed"):
                        raise ValueError("same-path replacement reused the wrong side")
                    rows.append({"case":"Log4j #1173","revision":side,"profile":mode,"question":name,"claimKey":keys[name],
                                 "inputMode":"supplied public question","classPath":[p["name"] for p in report["graphs"][binding["graph"]]["classpath"]],
                                 "entry":claim["entry"],"providerIndex":1,"artifactSha256":binding["artifactSha256"],
                                 "classSha256":binding["classSha256"],"physicalEntry":binding["physicalEntry"],
                                 "definingLoader":binding["jvm"]["definingLoader"],"jvmCheckerAgreement":True,
                                 "publicHits":hits,"observations":actual,"children":[c["status"] for c in claim["children"]],
                                 "claimStatus":claim["status"],"cacheAction":action,"manualProviderIndices":0})
                stages.setdefault(mode,{})[name] = [c["status"] for c in claim["children"]]
        if stages["cold"] != stages["warm"] or stages["cold"] != stages["clean"] or stages["replacement-warm"] != stages["replacement-clean"]:
            raise ValueError("warm and clean predictions disagree")
        if stages["replacement-warm"]["explicit"] != ["refuted"] * 4:
            raise ValueError("same-path substitution missed one of the four zone predictions")
        archive = destination.with_name("log4j-plans.zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
            for file in sorted([work/"scaffold.json", *(work/(mode+".json") for mode in stages),
                                *work.glob("*-bindings.json"), *(work/"receipts").glob("*.json")]):
                zipped.write(file, file.relative_to(work).as_posix())
        change_evidence.write_json(destination,{"rows":rows,"plansSha256":upgrade_replay.sha(archive),"strictEngine":{s:strict[s]["disposition"] for s in ("old","new")},
                                                "strictReceiptSha256":upgrade_replay.sha(ORACLE/"first-native.json")})
        print("Two scaffold bindings, eight frozen cases, five cache comparisons; all independent histories matched")


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("output",type=Path)
    run(p.parse_args().output)

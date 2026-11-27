"""Reproduce the sealed public nominations through ordinary Stage 2 and compare the original traces."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_evidence, change_plan, runtime_jdk, upgrade_replay


def read_summary(archive):
    with zipfile.ZipFile(archive) as source:
        return json.loads(source.read("summary.json"))


def observation_members(entries, document):
    selected = {}
    for run in document["runs"]:
        if run["plain"] != run["traced"]:
            continue
        for record in run["forks"]:
            fork = record["fork"]
            if fork["stop"]:
                continue
            for witness in record["witnesses"]:
                owner, _, method = witness["entry"].partition("#")
                name = owner.replace("/", ".") + "#" + method
                relation = witness["relationship"]
                if name not in entries or relation in selected.get(name, {}):
                    continue
                changed = witness["actualFrames"][0]
                definition = fork["classes"][str(changed["loader"]) + ":" + changed["member"].partition("#")[0]]
                if not definition["originalProvider"]:
                    raise ValueError("missing observed original dispatch target")
                if relation == "later on retained receiver":
                    call = witness["publicCall"]
                    receivers = {(frame["loader"], frame["receiver"]) for frame in witness["actualFrames"]}
                    if call["returned"] >= witness["hitEvent"] or (call["loader"], call["receiver"]) not in receivers:
                        raise ValueError("later changed body lost its retained receiver")
                selected.setdefault(name, {})[relation] = {
                    "sourceTrace": fork["rawSha256"], "test": witness["test"],
                    "thread": witness["thread"], "actualStack": witness["actualFrames"],
                    "body": changed, "bodyDefinition": definition, "event": witness["hitEvent"],
                    "publicBoundary": witness.get("publicCall", witness.get("frame"))
                }
    if set(selected) != entries:
        raise ValueError("original test witnesses omit a nominated public history")
    return selected


def run(work, *, require_choices=False):
    archives = {s: HERE / ("parquet-" + s + "-separate.zip") for s in ("old", "new")}
    jdk = runtime_jdk.home(21)
    selector = ["application", "--jdk", str(jdk), "--probe-limit", "5"]
    docs = {}
    for side, flag in (("old", "--before"), ("new", "--after")):
        doc = docs[side] = read_summary(archives[side])
        if len(doc["orderedDeployment"]) != 113:
            raise ValueError("incomplete original deployment")
        manifest = work / (side + ".json")
        change_evidence.write_json(manifest, {"commit": doc["revision"], "classpath": doc["orderedDeployment"],
                                             "jdkReleaseSha256": doc["jdkReleaseSha256"]})
        selector.extend([flag, str(manifest), "--upstream-history", str(archives[side])])
    path = work / "stage2.json"
    change_plan.main([*selector, "--output", str(path)])
    plan = json.loads(path.read_bytes())
    ranks = plan["inventory"]["upstreamHistory"]
    expected = json.loads((HERE / "separate-nominations.json").read_bytes())
    if ranks["ranked"] != expected["candidates"]:
        raise ValueError("ordinary discovery failed to reproduce the sealed nominations")
    top_five = {r["entry"] for r in ranks["ranked"][:5]}
    discovery = plan["discovery"]
    if set(discovery["probed"]) != top_five or discovery["selectedEntries"]:
        raise ValueError("competing public alternatives were dropped or selected as customer intent")
    with zipfile.ZipFile(HERE / "parquet-physical.zip") as physical:
        receipts = json.loads(physical.read("original-and-reversed.json"))
    histories = {r["entry"] for r in receipts}
    if not histories.issubset(top_five & set(discovery["boundOnBothRevisions"])):
        raise ValueError("a historical entry lacks an independent Stage 2 binding")
    choices = plan["inventory"].get("intentOptions", [])
    if require_choices and (not histories.issubset({row["entry"] for row in choices}) or any(
            name not in plan["inventory"]["intentQuestion"] for name in histories)):
        raise ValueError("the owner cannot see both distinct original public alternatives")
    reversed_doc = read_summary(HERE / "parquet-new-reversed-separate.zip")
    graph = docs["new"]["orderedDeployment"].copy()
    graph[0], graph[2] = graph[2], graph[0]
    if reversed_doc["orderedDeployment"] != graph:
        raise ValueError("reversed deployment did not exchange the two physical providers")
    details = {s: observation_members(histories, docs[s]) for s in docs}
    changed = {}
    for side, doc in (("new", docs["new"]), ("reversed", reversed_doc)):
        observed = {}
        for run in doc["runs"]:
            for record in run["forks"]:
                if not record["plainParity"] or record["fork"]["stop"]:
                    continue
                for definition in record["fork"]["classes"].values():
                    binding = definition["originalProvider"]
                    if binding and any(x.startswith(definition["owner"] + "#") for x in doc["changedSelectors"]):
                        observed[definition["owner"]] = {"classSha256": definition["classSha256"], **binding}
        changed[side] = observed
    if not any(row["classSha256"] != changed["reversed"].get(owner, {}).get("classSha256") and
               owner in changed["reversed"] for owner, row in changed["new"].items()):
        raise ValueError("reversal never changed a loaded definition")
    result = {"stage2Sha256": upgrade_replay.sha(path), "normalDiscovery": discovery, "qualifiedChoices": choices,
              "originalTestRanking": ranks, "intentQuestion": plan["inventory"]["intentQuestion"],
              "historicalPublicEntries": sorted(histories), "perSideWitnesses": details,
              "changedDefinitions": changed}
    name = "stage2-histories-reviewed.zip" if require_choices else "stage2-histories.zip"
    with zipfile.ZipFile(HERE / name, "w", zipfile.ZIP_DEFLATED) as output:
        output.write(path, "stage2.json")
        output.writestr("qualification.json", json.dumps(result, indent=2) + "\n")
    print("Stage 2 bound the historical file and page entries among five unhinted alternatives")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qualified-choices", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="stage2-original-histories-") as scratch:
        run(Path(scratch), require_choices=args.qualified_choices)

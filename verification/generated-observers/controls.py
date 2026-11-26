"""Independent qualification controls against frozen product bundles and original deployments."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

import campaign
from targets import change_inventory, observer_generation, runtime_jar, upgrade_claims, upgrade_replay

HERE = campaign.HERE
read, write = campaign.read, campaign.write


def app(work, bundle, jdk, workflows, dest, *, after=None):
    command = [campaign.sys.executable, campaign.ROOT / "examples/tools/build.py", "--change-plan", "application",
               "--before", bundle / "old.json", "--after", after or bundle / "new.json", "--jdk", jdk,
               "--workflows", workflows, "--supplied-only", "--run", "--seconds", "120",
               "--cache", work / "cache", "--output", dest]
    campaign.run(command)
    return read(dest)


def helper(work, bundle, jdk):
    generated = observer_generation.helper_table(work / "cold.json", bundle, jdk)
    if len(generated["rows"]) != 6:
        raise ValueError("registered public histories did not yield all six live minimum tuples")
    workflows = read(bundle / "workflows.json")
    variants = {"complete": generated, "missing-row": {**generated, "rows": generated["rows"][1:]},
                "wrong-result": {**generated, "rows": [{**generated["rows"][0], "result": -17}, *generated["rows"][1:]]},
                "wrong-binding": {**generated, "boundClassSha256": "0"*64},
                "no-consumption": {**generated, "callFrom": generated["callFrom"].split("#")[0] + "#read()I"}}
    states = {}
    for label, table in variants.items():
        # The ordinary source, archive, registration and predictions remain byte-identical in every challenge.
        write(bundle / (label + "-table.json"), table)
        rows = [{**row, "checkedHelper": label + "-table.json"} for row in workflows["workflows"]]
        path = bundle / (label + "-workflows.json")
        write(path, {**workflows, "workflows": rows})
        plan = app(work, bundle, jdk, path, work / (label + "-helper.json"))
        states[label] = {row["id"]: {"status": row["status"], "reason": row["firstOpenDependency"]} for row in plan["claims"]}
    if ({r["status"] for r in states["complete"].values()} != {"established"} or
            not any(r["status"] == "open" for r in states["missing-row"].values()) or
            any(r["status"] != "open" for k in ("wrong-result","wrong-binding","no-consumption") for r in states[k].values())):
        raise ValueError("helper falsifier or complete positive control disagrees: " + str(states))
    ordinary = app(work, bundle, jdk, bundle / "workflows.json", work / "ordinary-after-helper.json")
    if any(n["status"] != "established" for n in ordinary["claims"]):
        raise ValueError("ordinary public observation lost when helper evidence was withheld")
    write(work / "helper-controls.json", {"derived": generated, "variants": states,
          "independentPublicClaims": {n["id"]: n["status"] for n in ordinary["claims"]}})


def map_oracle(work, jdk):
    reg = read(HERE / "registrations/J17.json")
    node, = read(work / "cold.json")["claims"]
    source = HERE / "JdkMapOracle.java"
    subprocess.run([jdk / "bin/javac", "-d", work, source], check=True)
    summaries = []
    for item, child in zip(reg["questions"][0]["inputs"], node["children"], strict=True):
        lines = subprocess.check_output([jdk / "bin/java", "-cp", work, "JdkMapOracle", str(item["maximumSize"]),
            str(item["reverse"]).lower(), str(item["nullValue"])], text=True).splitlines()
        histories = {}
        for line in lines:
            size, mask, step, flag, mappings, keys, count, present, value = line.split("/")
            rows = histories.setdefault((int(size),int(mask)), [])
            rows.append([flag == "true", [list(map(int,p.split("="))) for p in mappings.split(",") if p],
                         [int(k) for k in keys.split(",") if k], int(count), present == "true", int(value)])
        direct = [[size,mask,steps] for (size,mask), steps in histories.items()]
        if any(json.loads(child[side]["return"]) != direct for side in ("old","new")):
            raise ValueError("JDK maps disagree with an original retained map view")
        summary = [len(direct), sum(s[2][0][0] for s in direct), sum(s[2][1][0] for s in direct),
                   sum(len(s[2][1][1]) for s in direct), sum(s[2][1][4] for s in direct)]
        if summary != [127,120,0,321,127]:
            raise ValueError("JDK scope differs from the historical bounded domain")
        summaries.append({"input":item,"fullHistorySha256":change_inventory.digest(direct),"summary":summary})
    write(work / "jdk-reference.json", {"sourceSha256":upgrade_replay.sha(source), "comparisons":summaries})

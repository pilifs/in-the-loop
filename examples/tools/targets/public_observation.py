"""Watcher's review and resume of a public PR prediction and its original-JVM evidence."""
import hashlib
import json
import os
from pathlib import Path
import re

from targets import blind_measure, blind_prediction, change_evidence, deployment_graph


def canonical_url(url):
    match = re.fullmatch(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/pull/([1-9]\d*)/?", url)
    if not match:
        raise ValueError("a public GitHub pull request URL is required")
    owner, repo, number = match.groups()
    return f"https://github.com/{owner.lower()}/{repo.lower()}/pull/{number}"


def intent_decision(choices):
    qualified = []
    for row in choices:
        observed = row.get("originalObservations", {})
        sides = row.get("requiredSides") or list(observed)
        if (row.get("disposition") in ("established", "refuted", "preserved", "changed") and row.get("evidence")
                and sides and all(observed.get(side) and all(value is not None for value in observed[side]) for side in sides)):
            qualified.append(row)
    if len(qualified) > 1:
        labels = []
        for row in qualified:
            names = [f["name"] if isinstance(f, dict) else f for f in row["observationFields"]]
            labels.append(row["entry"] + " (" + ", ".join(names) + ")")
        return "Which measured public observation matters to your caller, " + " or ".join(labels) + "?"
    if qualified:
        return None
    return next((row["reason"] for row in choices if row.get("reason")), None)


def report(prediction, measurement=None):
    choices = []
    measured = {r["candidateIndex"]:r for r in (measurement or {}).get("measurements",[])}
    for index, candidate in enumerate(prediction["candidates"]):
        row = measured.get(index,{})
        choices.append({"rank":index+1,"entry":candidate["entry"],"history":candidate["history"],
                        "prediction":candidate["prediction"],"observationFields":candidate["fields"],
                        "originalObservations":row.get("observations",{}),"requiredSides":row.get("requiredSides",[]),
                        "disposition":row.get("status","unmeasured"),
                        "scope":"registered finite public history","stoppedAt":row.get("stoppedAt","frozen prediction"),
                        "reason":row.get("reason"),"evidence":row.get("evidence",{})})
    if not choices:
        decision = prediction["firstOpenDependency"]
    else:
        decision = intent_decision(choices)
        if not decision and len(choices) > 1 and not measurement:
            decision = "Which proposed public history should be measured first?"
    return {"schema":"public-observation-review/v1","url":prediction["url"],"assistance":prediction["assistance"],
            "primary":prediction["primary"],"candidates":choices,"ownerDecision":decision}


def watch(url, packet, work, execute=False):
    url = canonical_url(url)
    if packet is None:
        cache = Path(os.environ.get("PUBLIC_PR_PACKETS",Path.home()/".cache/in-the-loop/public-pr-inputs"))
        packet = cache / hashlib.sha256(url.encode()).hexdigest()
    packet = packet.resolve()
    if not (packet/"packet.json").is_file():
        return {"schema":"public-observation-review/v1","url":url,"stoppedAt":"original deployment",
                "ownerDecision":"Which pinned parent and landing artifacts, in launch order and with which JDK, form the public deployment?",
                "packet":str(packet)}
    metadata = json.loads((packet/"packet.json").read_bytes())
    if canonical_url(metadata["url"]) != url:
        raise ValueError("the prepared deployment belongs to a different public PR")
    deployments = metadata.get("deployments") or [metadata]
    for deployment in deployments:
        for side in ("old", "new"):
            decision = deployment_graph.loader_decision(deployment[side])
            if decision:
                result = {"schema": "public-observation-review/v1", "url": url,
                          "deployment": deployment.get("name", "original"), "side": side,
                          "stoppedAt": "original loader binding", "ownerDecision": decision,
                          "loader": deployment[side].get("loader"), "packet": str(packet)}
                change_evidence.write_json(work / "review.json", result)
                return result
    sealed = work/"prediction"
    blind_prediction.main([str(packet),str(sealed)])
    prediction = json.loads((sealed/"prediction.json").read_bytes())
    output = work/"measured"
    measured = None
    if (output/"measurement.json").is_file():
        measured = blind_measure.verified_review(packet,sealed,output)
        if execute and measured.get("executionState") == "partial":
            measured = blind_measure.measure(packet,sealed,output)
    elif execute:
        measured = blind_measure.measure(packet,sealed,output)
    result = report(prediction,measured)
    change_evidence.write_json(work/"review.json",result)
    return result

"""Resume checked decimal-key continuations using the frozen side cache and public comparator."""
import gzip
import json
import os
from pathlib import Path
import tempfile
import time
import zipfile

from key_proof import certificate, digest, require
from key_replay import TARGET, check, deployment, replay
from register import CASE, CALLERS, ENTRIES, sha
from live import compile_tracer, frozen_cold
from plan_run import HERE
from targets import change_evidence, change_inventory

ARTIFACT = TARGET / "checked-cache.json.gz"


def public_evidence(archive, node):
    ref = node["receipt"]
    raw = archive.read(ref["path"])
    require(digest(raw) == ref["sha256"], "unbound original public receipt")
    return json.loads(raw)


def checked_side(work, classes, cache, report, proof, node, receipt, side):
    manifest, jars = deployment(side)
    original = receipt["sides"][side]
    binding = {"commit": manifest["commit"], "classpath": original["classpath"], "callerClassSha256": original["callerClassSha256"],
               "requiredHelperProof": proof["key"], "readerConsumer": CALLERS[report["cases"][0]["args"][0]]}
    saved = cache.lookup(side, jars, binding, report)
    if saved is None:
        trials = []
        for c in node["children"]:
            args = c["arguments"]
            reps = []
            for _ in range(2):
                with tempfile.TemporaryDirectory(dir=work) as tmp:
                    rep = replay(Path(tmp), classes, proof, side, args, "apply")
                rep["claimKey"] = node["claimKey"]
                reps.append(rep)
            require(reps[0] == reps[1], "fresh checked reader trials differ")
            apps = [{"proofKey": proof["key"], "startupArguments": [r["events"][0]],
                     "applications": [e for e in r["events"] if e[0] == "parse"]} for r in reps]
            trials.append({"input": c["input"], "observations": [r["observation"] for r in reps],
                           "entryInvocations": [r["entrySite"] for r in reps], "checkedApplications": apps,
                           "qualifiedMethodEntries": 2, "loadedUpgradeOnEachReplay": True, "repetitions": reps})
        loaded = {c["input"]: [ENTRIES[c["arguments"][0]].split("#")[0], CALLERS[c["arguments"][0]].split("#")[0]]
                  for c in node["children"]}
        binding.update(trials=trials, loadedDependencyClasses=sorted(loaded[0]))
    else:
        binding.update(trials=saved["trials"], loadedDependencyClasses=saved["loadedDependencyClasses"])
    for trial, child in zip(binding["trials"], node["children"], strict=True):
        for rep in trial["repetitions"]:
            check(rep, proof, receipt, node, child, side, "apply")
    if saved is None:
        cache.remember(side, binding, report, loaded)
    return binding


def run():
    archive = TARGET / "first/plans.zip"
    first = frozen_cold(archive)
    pin = json.loads((HERE / "freeze.json").read_bytes())
    proof = certificate()
    result = {"opening": sha(archive), "checkedProof": proof["key"], "runs": {}, "receipts": {}, "controls": {}}
    with zipfile.ZipFile(archive) as z, tempfile.TemporaryDirectory(prefix="resume-gson-keys-") as directory:
        work = Path(directory)
        classes, result["tracer"] = compile_tracer(CASE, work, deployment("old")[1])
        compiled = {p.stem: sha(p) for p in classes.glob("*.class")}
        for label, directory in (("cold", "cache"), ("warm", "cache"), ("clean", "fresh")):
            started, cpu = time.monotonic(), os.times()
            claims = {}
            for node in first["claims"]:
                if node["cohort"] != "registered":
                    continue
                public = public_evidence(z, node)
                name, route = node["id"], node["domain"][0]["args"][0]
                report = {"entry": ENTRIES[route], "cases": node["domain"], "probeClasses": compiled,
                          "observerInvocation": public["observerInvocation"]}
                basis = {"claim": node["claimKey"], "consumer": CALLERS[route], "proof": proof["key"], "tracer": result["tracer"],
                         "qualifiers": {p.name: sha(p) for p in (CASE / "key_replay.py", Path(__file__), HERE / "live.py")}}
                images = {s: pin["jdk"] for s in ("old", "new")}
                cache = change_evidence.SideCache(work / directory, basis, images)
                evidence = {"entry": report["entry"], "cases": report["cases"], "sides": {}}
                for side in images:
                    evidence["sides"][side] = checked_side(work, classes, cache, report, proof, node, public, side)
                scope = json.loads((CASE / (name + ".json")).read_bytes())
                decision = change_evidence.compose(scope, evidence, node["intent"])
                require(decision["status"] == "established", "checked original claim did not hold")
                for side, action in cache.actions.items():
                    hit = label == "warm" and (side == "old" or name.endswith("-values"))
                    require(action["action"] == ("exact reuse" if hit else "executed"), "incorrect checked-cache admission")
                checksum = change_inventory.digest(evidence)
                result["receipts"][checksum] = evidence
                claims[name] = {"claimKey": node["claimKey"], "receipt": checksum, "actions": cache.actions, "decision": decision}
                if name == "tree-values" and label in ("warm", "clean"):
                    # These positive sides had checked, reusable trials. Change just the proposed consumer.
                    stale = change_evidence.SideCache(work / directory, basis | {"consumer": CALLERS["stream"]}, images)
                    for side in images:
                        b = evidence["sides"][side] | {"readerConsumer": CALLERS["stream"]}
                        seen = stale.lookup(side, deployment(side)[1], b, report)
                        require(seen is None and stale.actions[side]["key"] != cache.actions[side]["key"], "cross-reader cache hit")
                        try:
                            with tempfile.TemporaryDirectory(dir=work) as temp:
                                replay(Path(temp), classes, proof, side, ["tree", "mixed", "values"], "apply", "route")
                        except ValueError as error:
                            require("wrong reader-specific parse consumer" in str(error), "wrong live refusal")
                        else: raise ValueError("an unqualified reader consumed the result")
                        result["controls"][label + "-" + side] = {"original": cache.actions[side], "changed": stale.actions[side],
                                                                 "result": "open at wrong reader-specific parse consumer"}
            end = os.times()
            result["runs"][label] = {"claims": claims, "wallSeconds": round(time.monotonic()-started, 3),
                                     "childCpuSeconds": round(end.children_user + end.children_system - cpu.children_user - cpu.children_system, 3)}
    ARTIFACT.write_bytes(gzip.compress(json.dumps(result, separators=(",", ":")).encode(), mtime=0))
    audit()


def audit():
    archive = TARGET / "first/plans.zip"
    original = frozen_cold(archive)
    result = json.loads(gzip.decompress(ARTIFACT.read_bytes()))
    proof = certificate()
    require(result["opening"] == sha(archive) and result["checkedProof"] == proof["key"], "different public plan or proof")
    with zipfile.ZipFile(archive) as z:
        for node in original["claims"]:
            if node["cohort"] != "registered":
                continue
            name = node["id"]
            cold, warm, clean = [result["runs"][label]["claims"][name] for label in ("cold", "warm", "clean")]
            require(cold["receipt"] == warm["receipt"] == clean["receipt"] and cold["decision"] == warm["decision"] == clean["decision"],
                    "cached public observations or checked evidence differ from fresh execution")
            ev = result["receipts"][cold["receipt"]]
            require(change_inventory.digest(ev) == cold["receipt"], "incorrect checked-side receipt")
            public = public_evidence(z, node)
            for side in ("old", "new"):
                trials = ev["sides"][side]["trials"]
                for trial, child in zip(trials, node["children"], strict=True):
                    require(len(trial["repetitions"]) == 2, "missing checked original repetitions")
                    for rep in trial["repetitions"]:
                        check(rep, proof, public, node, child, side, "apply")
                control = result["controls"]["warm-" + side]
                require(control["original"]["action"] == "exact reuse" and control["changed"]["action"] == "executed"
                        and control["result"] == result["controls"]["clean-" + side]["result"], "different original and clean refusal")
    print("All four checked reader claims matched cold, warm and clean. Both wrong-reader positive sides reopened.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true")
    if parser.parse_args().audit: audit()
    else: run()

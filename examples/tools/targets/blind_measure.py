"""Measure a previously sealed public prediction using original Stage 3 bindings and change-plan receipts."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from targets import blind_prediction, change_evidence, change_inventory, change_plan, observer_generation, observer_recipes, observer_scalar, runtime_jar, runtime_jdk, upgrade_replay


def read(path):
    return json.loads(path.read_bytes())


def reference(path, root):
    return {"path":path.relative_to(root).as_posix(), "sha256":upgrade_replay.sha(path)}


def check_saved(root, row):
    paths = {}
    for key, ref in row["evidence"].items():
        path = (root/ref["path"]).resolve()
        if not path.is_relative_to(root.resolve()) or upgrade_replay.sha(path) != ref["sha256"]:
            raise ValueError("saved public evidence changed at " + key)
        paths[key] = path
    if "plan" in paths:
        plan = read(paths["plan"])
        change_plan.saved_bindings(plan,paths["plan"].parent)
        node, = plan["claims"]
        if node["status"] != row["status"] or row["observations"] != {
                s:[c.get(s) for c in node.get("children",[])] for s in row["observations"]}:
            raise ValueError("published status or fields differ from the saved claim")
        if "receipt" in paths:
            bundle = paths["generation"].parent
            _, workflows = change_plan.frozen_workflows(bundle/"workflows.json")
            workflow, _, _, spec = workflows[node["id"]]
            result = change_evidence.compose(spec,read(paths["receipt"]),workflow["intent"])
            if row["status"] in ("established","refuted") and result["status"] != row["status"]:
                raise ValueError("saved fields do not establish the published finite disposition")


def original_manifests(root, packet, deployment, output, jdk_pin):
    manifests = {}
    for side in ("old","new"):
        data = deployment[side]
        cp = []
        for row in data["classpath"]:
            path = blind_prediction.read_local(root,row["file"])
            if change_inventory.file_digest(path) != row["sha256"]:
                raise ValueError("changed original deployment artifact on " + side)
            cp.append({"file":str(path), "sha256":row["sha256"]})
        if not cp:
            raise ValueError("missing original classpath on " + side)
        manifests[side] = output/(side+".json")
        change_evidence.write_json(manifests[side],{"classpath":cp,"jdkReleaseSha256":jdk_pin,
                                   "commit":data.get("revision") or packet[side+"Revision"],
                                   "scope":"original public PR deployment"})
    return manifests


def bound_entries(plan, entry, jdk_pin):
    return {b["side"]:{**{k:b[k] for k in ("status","entry","revision","providerIndex","artifactSha256","classSha256",
                 "graph","jvm","firstOpenDependency") if k in b}, "jdkReleaseSha256":jdk_pin}
            for b in plan["entryBindings"].values() if b["entry"] == entry and b["side"] in ("old","new")}


def side_names(candidate):
    mapping = {"parent":"old","fix":"new","old":"old","new":"new"}
    requested = {mapping.get(s) for s in candidate["requiredSides"]}
    if None in requested or not requested:
        raise ValueError("unknown required side")
    return [s for s in ("old","new") if s in requested]


def measure_candidate(index, candidate, root, directory, manifests, jdk, jdk_pin, base_args, bindings, functional_review):
    directory.mkdir()
    entry = candidate["entry"]
    sides = side_names(candidate)
    evidence = {"bindings":reference(bindings,root)}
    row = {"candidateIndex":index,"candidateSha256":change_inventory.digest(candidate),"entry":entry,
           "status":"open","requiredSides":sides,"evidence":evidence,"observations":{},
           "entryBindings":bound_entries(read(bindings),entry,jdk_pin)}
    missing = [s for s in ("old","new") if row["entryBindings"].get(s,{}).get("status") != "bound"]
    if missing:
        row.update(stoppedAt="bound public entry", reason={s:row["entryBindings"].get(s,{}).get("firstOpenDependency","unbound") for s in missing})
        return row
    if not candidate["inputs"]:
        row.update(stoppedAt="public caller inputs", reason="Which public construction, inputs and readback expose " + entry + "?")
        return row
    if candidate["fields"] == observer_scalar.FIELDS:
        owner, method, desc = runtime_jar.parse_target(entry)
        feature = int(runtime_jdk.feature(runtime_jdk.release(jdk)["JAVA_VERSION"]))
        for side,bound in row["entryBindings"].items():
            provider = Path(read(manifests[side])["classpath"][bound["providerIndex"]]["file"])
            name = runtime_jar.internal(owner)
            data = (provider/(name+".class")).read_bytes() if provider.is_dir() else runtime_jar.effective_class(provider,name,feature)
            if (not data or not observer_scalar.closed_data_operation(data,method,desc)
                    or any(not blind_prediction.ordinary_text(v) for item in candidate["inputs"]
                           for v in (item.get("arguments",[]) if isinstance(item,dict) else []))):
                row.update(stoppedAt="reviewed functional scope",reason="the selected original method needs a reviewed public fixture on "+side)
                return row
    elif (functional_review.get("classification") != "ordinary product behavior" or not functional_review.get("decisionSha256")
          or candidate["fields"] not in (observer_recipes.NUMBER_FIELDS,[*observer_recipes.NUMBER_FIELDS,observer_recipes.FORMAT_FIELD],
                                          ["peek.outcome","peek.value"],["peek.outcome","peek.value","pop.afterPeek"])):
        row.update(stoppedAt="reviewed functional scope",reason="register the side-scoped public inputs and readback before execution")
        return row
    predicate = candidate["prediction"]
    expected = predicate.get("expected") if isinstance(predicate,dict) else None
    if isinstance(predicate,dict) and set(sides) == set(predicate):
        expected = predicate
    relation = predicate.get("relation") if isinstance(predicate,dict) else None
    if expected is None:
        relation = {"different on at least one registered input":"different-on-any-input",
                    "equal on all registered inputs":"equal-on-all-inputs"}.get(relation,"observe-only")
    scoped_sides = sides if expected is not None else ["old","new"]
    name = "public-observation"
    reg = {"schema":"reviewed-public-observations/v1","change":entry,"entry":entry,"changed":[entry],
           "fields":candidate["fields"],"questions":[{"id":name,"history":candidate["history"],"cohort":"registered",
                    "sides":scoped_sides,"inputs":candidate["inputs"]}],
           "assumptions":["Original ordered artifacts and registered JDK. Fresh synchronous JVM per finite input."]}
    registration, predictions = directory/"registration.json", directory/"predictions.json"
    change_evidence.write_json(registration, reg)
    change_evidence.write_json(predictions, {name:expected if expected is not None else {"pairedObservation":relation}})
    evidence.update(registration=reference(registration,root), predictions=reference(predictions,root))
    bundle = directory/"bundle"
    row["stoppedAt"] = "generated and old-API compiled caller"
    try:
        generated = observer_generation.materialize(registration,predictions,manifests["old"],manifests["new"],jdk,bundle)
        evidence["generation"] = reference(bundle/"generation.json", root)
        if generated["status"] != "compiled":
            row["reason"] = generated["firstOpenDependency"]
            return row
        row["caller"] = {"sourceSha256":generated["sourceSha256"],"compiled":generated["compiled"],
                         "jdkReleaseSha256":jdk_pin,"compileAgainst":"old"}
        evidence.update(source=reference(bundle/"UpgradeProbe.java",root), bytecode=reference(bundle/"caller.zip",root))
        scaffold = directory/"scaffold.json"
        args = [*base_args, "--workflows",str(bundle/"workflows.json")]
        if change_plan.main([*args,"--output",str(scaffold)]):
            raise ValueError("stage 3 could not bind the frozen public scope")
        evidence["scaffold"] = reference(scaffold,root)
        plan = directory/"plan.json"
        row["stoppedAt"] = "required-side reach"
        if change_plan.main([*args,"--previous",str(scaffold),"--run","--output",str(plan)]):
            raise ValueError("original JVM replay stopped before publishing its receipt")
        report = read(plan)
        node, = report["claims"]
        evidence["plan"] = reference(plan,root)
        if "receipt" not in node:
            raise ValueError(str(node.get("firstOpenDependency", "missing original JVM receipt")))
        receipt = (directory/node["receipt"]["path"]).resolve()
        if not receipt.is_relative_to(directory.resolve()) or upgrade_replay.sha(receipt) != node["receipt"]["sha256"]:
            raise ValueError("original replay receipt differs from the plan")
        evidence["receipt"] = reference(receipt,root)
        change_plan.saved_bindings(report,directory)
        row["observations"] = {s:[child.get(s) for child in node.get("children",[])] for s in scoped_sides}
        both = all(len(row["observations"][s]) == len(reg["questions"][0]["inputs"]) and
                   all(v is not None for v in row["observations"][s]) for s in sides)
        row.update(status=node["status"], reason=node.get("reason") or node.get("firstOpenDependency"),
                   stoppedAt="scored candidate" if both and node["status"] in ("established","refuted")
                            else "finite disposition" if both else "qualified fields on required sides",
                   witness=node.get("witness"), inputsCovered=node.get("covered",0))
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        row["reason"] = str(error)
    return row


def measure(packet_dir, sealed, output):
    packet = read(packet_dir/"packet.json")
    path = sealed/"prediction.json"
    prediction = read(path)
    if (prediction.get("schema") != "blind-public-prediction/v1" or prediction["url"] != packet["url"]
            or prediction.get("packetSha256") != upgrade_replay.sha(packet_dir/"packet.json")
            or prediction["arm"] != packet["arm"] or prediction["productionDiffSha256"] !=
            upgrade_replay.sha(blind_prediction.read_local(packet_dir,packet["productionDiff"]))):
        raise ValueError("the sealed public prediction belongs to a different view")
    jdk = Path(packet["jdk"])
    jdk_pin = upgrade_replay.sha(jdk/"release")
    if packet.get("jdkReleaseSha256",jdk_pin) != jdk_pin:
        raise ValueError("registered JVM differs from the current deployment")
    output.mkdir(parents=True,exist_ok=True)
    previous = read(output/"measurement.json") if (output/"measurement.json").exists() else None
    if previous and previous["predictionSha256"] != upgrade_replay.sha(path):
        raise ValueError("the previous measurements belong to another sealed prediction")
    out = {"schema":"blind-public-measurement/v1","url":packet["url"],"arm":packet["arm"],
           "predictionSha256":upgrade_replay.sha(path),"measurements":[],"deployments":[]}
    selected = prediction["candidates"]
    deployments = packet.get("deployments") or [{"name":"original","old":packet["old"],"new":packet["new"]}]
    for index, deployment in enumerate(deployments):
        target = output/("deployment-"+str(index+1))
        target.mkdir(exist_ok=True)
        item = {"name":deployment["name"],"measurements":[]}
        out["deployments"].append(item)
        if index == 0:
            out["measurements"] = item["measurements"]
        out["executionState"] = "partial"
        change_evidence.write_json(output/"measurement.json",out)
        try:
            manifests = original_manifests(packet_dir,packet,deployment,target,jdk_pin)
            if not selected:
                item["stoppedAt"] = "candidate"
                continue
            base = ["application","--before",str(manifests["old"]),"--after",str(manifests["new"]),"--jdk",str(jdk),
                    "--supplied-only","--seconds","90","--cache",str(target/"cache")]
            checker = os.environ.get("JVMCONTRACT")
            if checker:
                base.extend(["--checker",checker])
            bindings = target/"bindings.json"
            entries = [x for c in selected for x in ("--entry",c["entry"])]
            if not bindings.is_file() and change_plan.main([*base,*entries,"--output",str(bindings)]):
                raise ValueError("Stage 3 failed to publish entry bindings")
            for i,candidate in enumerate(selected):
                attempt = target/("candidate-"+str(i+1))
                saved = target/("completed-"+str(i+1)+".json")
                if saved.exists():
                    row = read(saved)
                    if row["candidateSha256"] != change_inventory.digest(candidate):
                        raise ValueError("saved attempt belongs to a different candidate")
                    check_saved(output,row)
                else:
                    counter = 0
                    while attempt.exists():
                        counter += 1
                        attempt = target/f"candidate-{i+1}-retry-{counter}"
                    row = measure_candidate(i,candidate,output,attempt,manifests,jdk,jdk_pin,base,bindings,
                                            packet.get("functionalReview") or {})
                    change_evidence.write_json(saved,row)
                item["measurements"].append(row)
                change_evidence.write_json(output/"measurement.json",out)
        except (ValueError,OSError,KeyError,subprocess.SubprocessError) as error:
            item.update(stoppedAt="deployment or public binding",reason=str(error))
        change_evidence.write_json(output/"measurement.json",out)
    out["executionState"] = "complete"
    change_evidence.write_json(output/"measurement.json",out)
    return out


def verified_review(packet_dir, sealed, measured):
    """An offline review checks every published reference, the predicate, and the original deployment hashes."""
    record = read(measured/"measurement.json")
    packet = read(packet_dir/"packet.json")
    if (record["predictionSha256"] != upgrade_replay.sha(sealed/"prediction.json")
            or read(sealed/"prediction.json")["packetSha256"] != upgrade_replay.sha(packet_dir/"packet.json")):
        raise ValueError("this saved measurement belongs to a different prediction or deployment view")
    for deployment in packet.get("deployments") or [packet]:
        for side in ("old","new"):
            for artifact in deployment[side]["classpath"]:
                if change_inventory.file_digest(blind_prediction.read_local(packet_dir,artifact["file"])) != artifact["sha256"]:
                    raise ValueError("a prepared artifact changed after measurement on " + side)
    for deployment in record["deployments"]:
        for row in deployment["measurements"]:
            check_saved(measured,row)
    if record["measurements"] != record["deployments"][0]["measurements"]:
        raise ValueError("primary deployment summary differs from the underlying attempts")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("packet","sealed","output"):
        parser.add_argument(name,type=Path)
    args = parser.parse_args(argv)
    measure(args.packet.resolve(),args.sealed.resolve(),args.output.resolve())


if __name__ == "__main__":
    main()

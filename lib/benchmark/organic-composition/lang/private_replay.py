"""Resume each registered fixed-side public history with the proved private weekday conversion."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from private_proof import BRIDGE, CONVERT, calendar_consumers, compare_strategies, hash_bytes, identity, number_strategy, prove, require, translate
from register import CASE, ENTRY, PARSER, sha
from freeze import verify
from plan_run import JDK, ROOT, OUTPUT
from targets import change_helpers, runtime_jar, upgrade_replay

TARGET = ROOT / OUTPUT / "lang"


def refuse(operation, expected):
    try:
        operation()
    except ValueError as e:
        require(str(e) == expected, "unexpected refusal: " + str(e))
        return expected
    raise ValueError("invalid private derivation was accepted")


def expected_sites(args, public_value):
    wanted = []
    for step in public_value["return"].split("/"):
        day, _, cursor, *_ = step.split(",")
        if day == "x":
            continue
        iso = int(day)
        wanted.append(("parse-digit", iso, int(cursor)))
        if args[1] == "lenient" and not 1 <= iso <= 7:
            wanted.append(("normalize", (iso - 1) % 7 + 1, int(cursor)))
    return wanted


def check(trial, ordinary, receipt, proof):
    require(proof and trial["proof"] == proof["key"] and receipt["sides"]["new"]["commit"] == proof["commit"]
            and receipt["sides"]["new"]["classpath"] == [r["sha256"] for r in proof["orderedClasspath"]],
            "missing or stale private proof")
    require(trial["observation"] == ordinary["observations"][0] == ordinary["observations"][1]
            and ordinary["qualifiedMethodEntries"] == 2 and trial["publicSite"] in ordinary["entryInvocations"]
            and trial["publicSite"]["dispatchedTo"] == ENTRY, "different original public continuation")
    require(trial.get("initializedTimeZones") and trial["initializedTimeZones"]["parserZone"] == "UTC",
            "missing live timezone initialization")
    app = trial["application"]
    require(app["proofKey"] == proof["key"] and proof["declaredSpec"]["startupEntry"] == app["startupEntry"]
            and app["startupArguments"] == ["YYYY-'W'ww-u"], "missing parser construction or proof identity")
    witnessed = []
    calls = proof["bodies"]["".join(BRIDGE)]["calls"]
    table = {tuple(row["args"]): row["result"] for row in proof["rows"]}
    for site, hit in zip(trial["frames"], app["applications"], strict=True):
        key = tuple(hit["args"])
        require(hit["caller"] == PARSER + "#" + "".join(BRIDGE) and calls.get(str(hit["bci"])) == "".join(CONVERT)
                and len(key) == 1 and key[0] == site["argument"] and hit["result"] == table.get(key),
                "substitution outside the proved original bridge")
        witnessed.append((site["role"], site["argument"], site["cursor"]))
    require(witnessed == expected_sites(trial["args"], trial["observation"]), "missing or displaced original conversion")


def verify_frame(jar, site):
    owner, method, descriptor = runtime_jar.parse_target(site["caller"])
    if site["role"] == "normalize":
        require((owner, method, descriptor) == (PARSER + "$WeekDateRecorder", "applyWeekDate", "()V"), "wrong normalization caller")
    else:
        require(site["role"] == "parse-digit" and owner.startswith(PARSER + "$") and method == "modify"
                and descriptor == "(Lorg/apache/commons/lang3/time/FastDateParser;I)I", "wrong number strategy")
    data = runtime_jar.read_class(jar, owner.replace(".", "/"))
    require(hash_bytes(data) == site["classSha256"], "original strategy or recorder class differs")
    call = runtime_jar.member_at_code_index(data, method, descriptor, site["bci"],
                                            code_sha256=site["codeSha256"], pool_sha256=site["poolSha256"])
    require(call and (call["opcode"], call["owner"], call["name"], call["descriptor"]) == ("invokestatic", PARSER, *BRIDGE),
            "strategy or recorder did not call the original bridge")


def launch(directory, classes, jar, scope, table, args):
    directory.mkdir()
    encoded = [base64.b64encode(a.encode("utf-16-be")).decode() for a in args]
    config = ["-Dupgrade.checked.table=" + str(table)] if table else []
    cmd = [JDK / "bin/java", *config, "-cp", classes, "UpgradeTrace", ENTRY, JDK,
           directory, os.pathsep.join(map(str, (classes, jar))), str(scope), "UpgradeProbe", "", *encoded]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=40)


def zone_profile(marks, origins, jar):
    name = "org.apache.commons.lang3.time.TimeZones"
    require(origins.get(name) == {jar}, "unbound initialized timezone provider")
    encoded, = [m.split()[1] for m in marks if m.startswith("WEEK-ZONES ")]
    gmt, delegate, selected, j25, count, ids, code, pool = base64.b64decode(encoded, validate=True).decode().split("\t")
    data = runtime_jar.read_class(jar, name.replace(".", "/"))
    require(gmt == "org.apache.commons.lang3.time.ImmutableTimeZone" and (delegate, selected, j25) == ("GMT", "UTC", "false")
            and int(count) > 0 and len(ids) == 64 and pool == hash_bytes(data[10:runtime_jar._pool(data)[1]])
            and code == hash_bytes(runtime_jar._declarations(data, with_code=True)[1]["<clinit>", "()V"][1]),
            "different initialized timezone state or provider")
    return {"class": name, "classSha256": hash_bytes(data), "initializerCode": code, "pool": pool,
            "gmtObject": gmt, "gmtDelegate": delegate, "parserZone": selected, "java25": False,
            "availableIds": int(count), "sortedJdkIdsSha256": ids}


def parse_trial(proc, work, jar, proof, spec, args):
    require(proc.returncode == 0, proc.stderr[-700:])
    marks = proc.stderr.splitlines()
    origins = upgrade_replay.class_origins(proc.stdout)
    for owner in (ENTRY.split("#")[0], PARSER, PARSER + "$WeekDateRecorder"):
        require(origins.get(owner) == {jar}, "unbound original provider: " + owner)
    app = change_helpers.applications(marks, origins, spec, proof, [jar], args)
    frames = []
    for line in marks:
        if not line.startswith("WEEK-CONVERSION "):
            continue
        role, value, cursor, caller, pc, code, pool = base64.b64decode(line.split()[1], validate=True).decode().split("\t")
        owner, _, _ = runtime_jar.parse_target(caller)
        require(origins.get(owner) == {jar}, "unbound strategy or recorder")
        data = runtime_jar.read_class(jar, owner.replace(".", "/"))
        frame = {"role": role, "argument": int(value), "cursor": int(cursor), "caller": caller,
                 "bci": int(pc), "codeSha256": code, "poolSha256": pool, "classSha256": hash_bytes(data)}
        verify_frame(jar, frame)
        frames.append(frame)
    public, = [s.removeprefix("UPGRADE-CALL-SITE ") for s in marks if s.startswith("UPGRADE-CALL-SITE ")]
    pc, dispatched = public.split("\t")
    return {"args": args, "proof": proof["key"], "application": app, "frames": frames,
            "initializedTimeZones": zone_profile(marks, origins, jar),
            "publicSite": {"observerCodeIndex": int(pc), "dispatchedTo": dispatched},
            "observation": upgrade_replay.typed_outcome((work / "observation.txt").read_text().splitlines())}


def main():
    verify()
    spec = json.loads((CASE / "helper.json").read_bytes())
    old, new = [json.loads((CASE / side / "prepared.json").read_bytes()) for side in ("old", "new")]
    proof = prove(new, spec)
    corrupt = spec | {"rows": [dict(r, result=1) if r["args"] == [0] else r for r in spec["rows"]]}
    controls = {"parent": refuse(lambda: prove(old, spec), "private weekday conversion absent"),
                "wrongTable": refuse(lambda: prove(new, corrupt), "private bytecode contradicts the declared weekday result")}
    result = {"proof": proof, "strategyComparison": compare_strategies(old, new, proof), "controls": controls,
              "corruptTableControl": {"arguments": [0], "declaredResult": 1, "provedResult": 0, "counterexample": "sat"},
              "ordinaryStartup": {}, "trials": []}
    artifact, = new["classpath"]
    jar = Path(artifact["file"])
    result["calendarConsumers"] = calendar_consumers(jar)
    with tempfile.TemporaryDirectory(prefix="private-weekday-") as temp, zipfile.ZipFile(TARGET / "first/plans.zip") as archive:
        w = Path(temp)
        tracer = w / "UpgradeTrace.java"
        untouched = upgrade_replay.TRACER.read_text()
        anchor = "            hit.thread().forceEarlyReturn(returned);"
        first = "                            if (site != null) {"
        require(untouched.count(anchor) == 1 and untouched.count(first) == 1, "frozen observation or substitution point changed")
        tracer.write_text(untouched.replace(anchor, "            WeekFrames.record(frames, key);\n" + anchor)
                          .replace(first, first + "\n                                if (entryInvocation == null) WeekFrames.initialized(point.thread().frame(0));"))
        result["tracer"] = {"frozen": sha(upgrade_replay.TRACER), "withFrameObserver": sha(tracer), "frameObserver": sha(CASE / "WeekFrames.java")}
        classes = w / "classes"
        classes.mkdir()
        subprocess.run([JDK / "bin/javac", "-proc:none", "-g", "-encoding", "UTF-8", "-cp", old["classpath"][0]["file"],
                        "-d", classes, tracer, upgrade_replay.LAUNCHER, upgrade_replay.LOOKUP,
                        CASE / "WeekFrames.java", CASE / "UpgradeProbe.java"], check=True)
        table = change_helpers.trace_config(w / "valid", spec, proof)
        nodes = json.loads(archive.read("cold.json"))["claims"]
        for node in nodes:
            if node["id"] not in ("mixed", "preserved"):
                continue
            require(node["status"] == "established", "missing original finite claim")
            ref = node["receipt"]
            payload = archive.read(ref["path"])
            require(hash_bytes(payload) == ref["sha256"], "unbound frozen cold receipt")
            receipt = json.loads(payload)
            require(receipt["probeClasses"]["UpgradeProbe"] == sha(classes / "UpgradeProbe.class")
                    and receipt["probeClasses"]["UpgradeObservation"] == sha(classes / "UpgradeObservation.class"),
                    "observer differs from the frozen plan")
            for child, ordinary in zip(node["children"], receipt["sides"]["new"]["trials"], strict=True):
                args = child["arguments"]
                require(ordinary["input"] == child["input"] and ordinary["observations"] == [child["new"]] * 2,
                        "wrong original child")
                site, = {x["observerCodeIndex"] for x in ordinary["entryInvocations"]}
                if args == ["US", "lenient", "mixed"]:
                    for side, deployment in (("old", old), ("new", new)):
                        source = Path(deployment["classpath"][0]["file"])
                        rows = []
                        for repeat in (1, 2):
                            place = w / f"startup-{side}-{repeat}"
                            process = launch(place, classes, source, site, None, args)
                            require(process.returncode == 0 and "UPGRADE-SUBSTITUTED " not in process.stderr
                                    and upgrade_replay.typed_outcome((place / "observation.txt").read_text().splitlines()) == child[side],
                                    "ordinary startup continuation differs: " + process.stderr[-500:])
                            rows.append(zone_profile(process.stderr.splitlines(), upgrade_replay.class_origins(process.stdout), source))
                        require(rows[0] == rows[1], "ordinary timezone initialization differs")
                        result["ordinaryStartup"][side] = {"commit": deployment["commit"], "repetitions": rows,
                                                            "args": args, "observation": child[side], "coldReceipt": ref}
                for repetition in (1, 2):
                    directory = w / f"{node['id']}-{child['input']}-{repetition}"
                    proc = launch(directory, classes, jar, site, table, args)
                    trial = parse_trial(proc, directory, jar, proof, spec, args)
                    check(trial, ordinary, receipt, proof)
                    result["trials"].append(trial | {"coldClaim": node["claimKey"], "coldReceipt": ref,
                                                     "input": child["id"], "repetition": repetition})
            if node["id"] == "mixed":
                controls["withheldProof"] = refuse(lambda: check(trial, ordinary, receipt, None), "missing or stale private proof")
                controls["withheldInitialization"] = refuse(lambda: check(trial | {"initializedTimeZones": None}, ordinary, receipt, proof),
                                                           "missing live timezone initialization")
                false_app = trial["application"] | {"applications": []}
                omitted = trial | {"frames": [], "application": false_app}
                controls["withheldApplications"] = refuse(lambda: check(omitted, ordinary, receipt, proof), "missing or displaced original conversion")
                keep = [i for i, f in enumerate(trial["frames"]) if f["role"] == "parse-digit"]
                require(len(keep) < len(trial["frames"]), "missing original normalization control")
                partial = trial | {"frames": [trial["frames"][i] for i in keep], "application": trial["application"] | {
                    "applications": [trial["application"]["applications"][i] for i in keep]}}
                controls["withheldNormalizationOnly"] = refuse(lambda: check(partial, ordinary, receipt, proof), "missing or displaced original conversion")
                stale_side = receipt | {"sides": receipt["sides"] | {"new": receipt["sides"]["old"]}}
                controls["fixedProofOnParent"] = refuse(lambda: check(trial, ordinary, stale_side, proof), "missing or stale private proof")
                stale = change_helpers.trace_config(w / "wrong-body", spec, proof | {"codeSha256": "00" * 32})
                failed = launch(w / "refusal", classes, jar, site, stale, args)
                require(failed.returncode != 0 and "loaded helper differs from the proved static body" in failed.stderr
                        and "UPGRADE-SUBSTITUTED " not in failed.stderr, "stale live method bytes accepted")
                controls["wrongLiveBody"] = "loaded helper differs from the proved static body"
    require(len(result["trials"]) == 16, "two independent fixed continuations required per input")
    result["derivationSha256"] = identity(result["trials"])
    (TARGET / "private-conversion.json").write_text(json.dumps(result, indent=2) + "\n")
    print(len(result["trials"]), "fixed public continuations with", sum(len(t["frames"]) for t in result["trials"]),
          "private conversions")


def audit():
    verify()
    report = json.loads((TARGET / "private-conversion.json").read_bytes())
    proof = report["proof"]
    registration = json.loads((CASE / "registration.json").read_bytes())
    require(all(sha(CASE / p) == digest for p, digest in registration["inputs"].items()), "original registration differs")
    require(identity({k: v for k, v in proof.items() if k != "key"}) == proof["key"]
            and proof["declaredSpec"] == json.loads((CASE / "helper.json").read_bytes())
            and identity(report["trials"]) == report["derivationSha256"], "stored proof or trials differ")
    require(proof["jdk"] == json.loads((CASE.parent / "freeze.json").read_bytes())["jdk"]
            and proof["qualificationSha256"] == sha(CASE / "private_proof.py")
            and report["tracer"]["frozen"] == sha(upgrade_replay.TRACER)
            and report["tracer"]["frameObserver"] == sha(CASE / "WeekFrames.java"), "different proof or execution tools")
    require(report["controls"] == {
        "parent": "private weekday conversion absent", "wrongTable": "private bytecode contradicts the declared weekday result",
        "withheldProof": "missing or stale private proof", "withheldInitialization": "missing live timezone initialization",
        "withheldApplications": "missing or displaced original conversion",
        "withheldNormalizationOnly": "missing or displaced original conversion", "fixedProofOnParent": "missing or stale private proof",
        "wrongLiveBody": "loaded helper differs from the proved static body"}, "missing negative control")
    require(report["corruptTableControl"] == {"arguments": [0], "declaredResult": 1, "provedResult": 0, "counterexample": "sat"}
            and {"args": [0], "result": 0} in proof["rows"], "missing invalid weekday witness")
    manifest = json.loads((CASE / "new/prepared.json").read_bytes())
    jar = Path(manifest["classpath"][0]["file"])
    data = runtime_jar.read_class(jar, PARSER.replace(".", "/"))
    require(identity(report["calendarConsumers"]) == identity(calendar_consumers(jar)), "different calendar write instructions")
    comparison = report["strategyComparison"]
    require(comparison["bindings"]["new"] == number_strategy(manifest, True) and
            comparison["bindings"]["old"] == number_strategy(json.loads((CASE / "old/prepared.json").read_bytes()), False)
            and comparison["counterexample"] == "unsat", "weekday strategy correspondence differs")
    require(proof["commit"] == manifest["commit"] and proof["orderedClasspath"] == manifest["classpath"]
            and sha(jar) == manifest["classpath"][0]["sha256"] and proof["classSha256"] == hash_bytes(data)
            and proof["bodies"] == {name + desc: value for (name, desc), value in translate(data).items()}
            and proof["counterexample"] == "unsat", "different original proof subject")
    seen = set()
    with zipfile.ZipFile(TARGET / "first/plans.zip") as archive:
        nodes = {n["claimKey"]: n for n in json.loads(archive.read("cold.json"))["claims"] if n["id"] in ("mixed", "preserved")}
        mixed, = [n for n in nodes.values() if n["id"] == "mixed"]
        for side in ("old", "new"):
            row = report["ordinaryStartup"][side]
            deployed = json.loads((CASE / side / "prepared.json").read_bytes())
            source = runtime_jar.read_class(Path(deployed["classpath"][0]["file"]), "org/apache/commons/lang3/time/TimeZones")
            child, = [c for c in mixed["children"] if c["arguments"] == ["US", "lenient", "mixed"]]
            require(row["commit"] == deployed["commit"] and row["coldReceipt"] == mixed["receipt"]
                    and row["args"] == child["arguments"] and row["observation"] == child[side]
                    and len(row["repetitions"]) == 2 and row["repetitions"][0] == row["repetitions"][1]
                    and row["repetitions"][0]["classSha256"] == hash_bytes(source), "unbound ordinary startup evidence")
        for trial in report["trials"]:
            node = nodes[trial["coldClaim"]]
            require(node["receipt"] == trial["coldReceipt"], "different original claim receipt")
            raw = archive.read(node["receipt"]["path"])
            require(hash_bytes(raw) == node["receipt"]["sha256"], "changed original receipt")
            receipt = json.loads(raw)
            child, = (c for c in node["children"] if c["id"] == trial["input"])
            require(trial["args"] == child["arguments"] and trial["observation"] == child["new"], "different original input")
            ordinary, = (t for t in receipt["sides"]["new"]["trials"] if t["input"] == child["input"])
            check(trial, ordinary, receipt, proof)
            require(trial["initializedTimeZones"] == report["ordinaryStartup"]["new"]["repetitions"][0], "different startup profile")
            for frame in trial["frames"]:
                verify_frame(jar, frame)
                if frame["role"] == "parse-digit":
                    require(frame["caller"].split("#")[0].replace(".", "/") == comparison["bindings"]["new"]["selected"],
                            "different installed weekday strategy")
            seen.add((child["id"], trial["repetition"]))
        require(len(seen) == len(report["trials"]) == 16 and
                seen == {(c["id"], r) for n in nodes.values() for c in n["children"] for r in (1, 2)}, "incomplete private public trials")
    print("All 16 fixed continuations match their bound public receipts and original conversion sites.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true")
    if parser.parse_args().audit:
        audit()
    else:
        main()

"""Qualify the original Log4j schedule in API/core order using the frozen evidence composer and side cache."""
import argparse
import gzip
import json
import os
from pathlib import Path
import shutil
import tempfile
import time

from register import CASE, ENTRY, PLUGIN, PROCESSOR, expected, sha
from update_proof import digest, plugin, prove, require
from live import compile_tracer, frozen_cold, member_site, observe
from plan_run import HERE, OUTPUT, ROOT
from targets import change_evidence, change_inventory

TARGET = ROOT / OUTPUT / "log4j"
FACTORY = "org.apache.logging.log4j.core.pattern.FileDatePatternConverter"
CONVERTER = "org.apache.logging.log4j.core.pattern.DatePatternConverter"


def deployment(side):
    doc = json.loads((CASE / side / "prepared.json").read_bytes())
    jars = [Path(r["file"]) for r in doc["classpath"]]
    require([sha(j) for j in jars] == [r["sha256"] for r in doc["classpath"]], "different original graph")
    return doc, jars


def config(path, core, side, args, mode, proof, control=None):
    explicit = args[1] == "explicit"
    zone = "GMT-06:00" if side == "new" and explicit else args[0]
    props = {"pluginUrl": "file:" + str(core) + "!/" + PLUGIN, "options": "yyyy-MM-dd" + (",GMT-6" if explicit else ""),
             "usedZone": zone, "side": side, "mode": mode, "code": proof["code"], "pool": proof["pool"],
             "return": proof["partitions"][0]["offsets"][-1]}
    if control == "stale":
        props["code"] = "00" * 32
    if control == "plugin":
        props["pluginUrl"] += ".unselected"
    path.write_text("".join(f"{k}={v}\n" for k, v in props.items()))


def check(rep, side, args, jar, actual_path, proof, metadata, *, mode):
    require(proof and rep["proof"] == proof["key"], "missing scheduling effect proof")
    require(metadata and metadata["sha256"] == rep["metadata"], "missing original plugin metadata")
    explicit, flag = args[1] == "explicit", args[2] == "time-based"
    offset = -6 if side == "new" and explicit else int(args[0][3:6])
    oracle = expected(offset, flag)
    require(rep["public"] == oracle and rep["site"]["dispatchedTo"] == ENTRY, "different public scheduling history")
    steps = oracle["return"].split("/")
    expected_zone = "GMT-06:00" if side == "new" and explicit else args[0]
    events = rep["events"]
    kinds = ["default", "resource", "converter", "update", "post"] + ["calendar", "calendar", "update", "post"] * 3 + ["default"]
    require([e[0] for e in events] == kinds, "missing startup, receiver effect or scheduling call")
    for row, phase in ((events[0], "enter"), (events[-1], "restore")):
        require(row[:4] == ["default", phase, args[0], args[0]] and row[4].startswith("UpgradeProbe#observe("),
                "missing original JVM default or final restoration")
    resource, converter = events[1:3]
    require(resource[1] == "file:" + str(actual_path) + "!/" + PLUGIN and member_site(jar, resource[2:])["name"] == "openStream",
            "different selected plugin resource")
    factory = member_site(jar, converter[2:])
    require(converter[1] == ("yyyy-MM-dd,GMT-6" if explicit else "yyyy-MM-dd") and converter[2].startswith(FACTORY + "#newInstance(")
            and (factory["owner"], factory["name"]) == (CONVERTER, "newInstance"), "different selected original converter")
    before = [(0, 13, 17)]
    for row in steps[1:]:
        _, saved, prev, cur, _, _ = map(int, row.split(","))
        before.append((saved, prev, cur))
    for i, (start, post) in enumerate(zip([e for e in events if e[0] == "update"], [e for e in events if e[0] == "post"], strict=True)):
        next_value, prev, cur = before[i]
        require(start[1:6] == [str(next_value), str(prev), str(cur), str(flag).lower(), str(mode == "apply").lower()]
                and start[6] == "UpgradeProbe#observe([Ljava/lang/String;)Ljava/lang/String;", "different update caller or input state")
        writes = next(p["writes"] for p in proof["partitions"] if p["timeBased"] == flag and p["nextSign"] == ((next_value > 0) - (next_value < 0)))
        require(post[1:3] == [str(next_value if writes else prev), str(0 if writes else cur)] and int(post[3]) > 6,
                "receiver frame disagrees with the original bytecode")
    for c in (e for e in events if e[0] == "calendar"):
        target = member_site(jar, c[2:])
        desc = "(Ljava/util/TimeZone;)Ljava/util/Calendar;" if side == "new" else "()Ljava/util/Calendar;"
        require(c[1] == expected_zone and c[2] == ENTRY and (target["owner"], target["name"], target["descriptor"]) ==
                ("java.util.Calendar", "getInstance", desc), "different original calendar source")


def capture(classes, work, side, args, jars, proof, meta, mode, control=None):
    config(work / "config", jars[1], side, args, mode, proof, control)
    with tempfile.TemporaryDirectory(dir=work) as stage:
        out, events, call, origins = observe(classes, jars, ENTRY, args, Path(stage) / "vm", work / "config", zone=args[0])
    require(all(origins.get(owner) == {jars[1]} for owner in (PROCESSOR, CONVERTER, FACTORY))
            and origins.get("org.apache.logging.log4j.Logger") == {jars[0]}, "different loaded API or core")
    pc, member = call.split("\t")
    return {"public": out, "site": {"observerCodeIndex": int(pc), "dispatchedTo": member}, "events": events,
            "proof": proof["key"], "metadata": meta["sha256"]}


def measured_side(classes, w, cache, deploy, side, jars, proof, meta, manifest, report, baselines):
    binding = {"orderedFiles": list(map(str, jars)), "classpath": [sha(j) for j in jars],
               "callerClassSha256": proof["class"], "requiredHelperProof": proof["key"],
               "resource": meta, "publicProviderIndex": 1, "commit": manifest["commit"]}
    payload = cache.lookup(deploy, jars, binding, report)
    if payload is None:
        trials = []
        loaded = {}
        for i, c in enumerate(report["cases"]):
            args = c["args"]
            reps, apps = [], []
            for _ in range(2):
                rep = capture(classes, w, side, args, jars, proof, meta, "apply")
                require(baselines[side, tuple(args)]["observations"] == [rep["public"]["return"]]*2, "different untouched JVM result")
                reps.append(rep)
                apps.append({"proofKey": proof["key"], "startupArguments": [rep["events"][0][2], rep["events"][1][1]],
                             "applications": [e for e in rep["events"] if e[0] == "update"]})
            require(reps[0] == reps[1], "two substituted public trials disagree")
            trials.append({"input": i, "qualifiedMethodEntries": 2, "loadedUpgradeOnEachReplay": True,
                           "entryInvocations": [r["site"] for r in reps], "observations": [r["public"] for r in reps],
                           "checkedApplications": apps, "repetitions": reps})
            loaded[i] = [PROCESSOR, CONVERTER, FACTORY]
        binding.update(trials=trials, loadedDependencyClasses=sorted(loaded[0]))
    else:
        binding.update(trials=payload["trials"], loadedDependencyClasses=payload["loadedDependencyClasses"])
    for c, t in zip(report["cases"], binding["trials"], strict=True):
        for rep in t["repetitions"]:
            check(rep, side, c["args"], jars[1], jars[1], proof, meta, mode="apply")
    if payload is None:
        cache.remember(deploy, binding, report, loaded)
    return binding


def run():
    base = json.loads((CASE / "workflows.json").read_bytes())
    archive = TARGET / "canonical/plans.zip"
    frozen = frozen_cold(archive)
    require(all(n["status"] == "open" and all("the checker would inspect" in m for m in n["firstOpenDependency"])
                for n in frozen["claims"]), "first API/core provider frontier differs")
    manifests, sources = {}, {}
    for side in ("old", "new"):
        manifests[side], sources[side] = deployment(side)
    records = {"frozenPlan": sha(archive), "publicControls": sha(TARGET / "processes.json"), "proofs": {}, "plugins": {}, "runs": {}, "evidence": {}, "controls": {}}
    for side in sources:
        records["proofs"][side] = prove(sources[side][1])
        records["plugins"][side] = plugin(sources[side][1])
        require(records["plugins"][side]["sha256"] == manifests[side]["resources"][PLUGIN], "different registered plugin bytes")
    image = json.loads((HERE / "freeze.json").read_bytes())["jdk"]
    with tempfile.TemporaryDirectory(prefix="original-rollover-") as temp:
        w = Path(temp)
        classes, records["tracer"] = compile_tracer(CASE, w, sources["old"])
        tools = {p.name: sha(p) for p in (CASE / "update_proof.py", Path(__file__), HERE / "live.py", Path(change_evidence.__file__))}
        compiled = {p.stem: sha(p) for p in classes.glob("*.class")}
        baselines = {(r["side"], tuple(r["args"])): r for r in json.loads((TARGET / "processes.json").read_bytes())}
        # Keep the new core at a stable disposable pathname from the first measurement.
        path = w / "log4j-core.jar"
        for label, new_side, directory in (("cold", "new", "cache"), ("warm", "new", "cache"), ("clean", "new", "clean"),
                                           ("unrelated-warm", "new", "cache"), ("unrelated-clean", "new", "clean2"),
                                           ("replacement-warm", "old", "cache"), ("replacement-clean", "old", "clean3")):
            start, cpu = time.monotonic(), os.times()
            shutil.copyfile(sources[new_side][1], path)
            if label == "unrelated-warm":
                (w / "unselected.txt").write_text("outside both URL classpaths\n")
            claims = {}
            for workflow in base["workflows"]:
                scope = json.loads((CASE / workflow["scope"]).read_bytes())
                node, name = {"cases": scope["cases"], "entry": ENTRY, "sides": {}}, workflow["id"]
                public_key = next(n["claimKey"] for n in frozen["claims"] if n["id"] == name)
                cache = change_evidence.SideCache(w / directory, {"publicClaim": public_key, "tools": tools, "tracer": records["tracer"]},
                                                  {s:image for s in sources})
                report = {"entry": ENTRY, "cases": scope["cases"], "probeClasses": compiled,
                          "observerInvocation": {"declaration": ENTRY, "probe": sha(CASE / "UpgradeProbe.java")}}
                for deploy, side in (("old", "old"), ("new", new_side)):
                    jars = sources[side] if deploy == "old" else [sources["new"][0], path]
                    proof, meta = records["proofs"][side], records["plugins"][side]
                    node["sides"][deploy] = measured_side(classes, w, cache, deploy, side, jars, proof, meta,
                                                           manifests[side], report, baselines)
                decision = change_evidence.compose(scope, node, workflow["intent"])
                wanted = "refuted" if new_side == "old" and name == "explicit" else "established"
                require(decision["status"] == wanted and all(c["status"] == wanted for c in decision["children"]), "wrong public scheduling result")
                require(all(cache.actions[s]["action"] == ("exact reuse" if label.endswith("warm") and
                        (s == "old" or (name == "omitted" and new_side == "new")) else "executed") for s in sources), "unexpected cache action")
                receipt = change_inventory.digest(node)
                records["evidence"][receipt] = node
                claims[name] = {"claimKey": public_key, "receipt": receipt, "actions": cache.actions, "decision": decision}
            end = os.times()
            records["runs"][label] = {"claims": claims, "wallSeconds": round(time.monotonic() - start, 3),
                                      "childCpuSeconds": round(end.children_user + end.children_system - cpu.children_user - cpu.children_system, 3)}
        # On both genuine deployments, leave the real method untouched and compare every field at normal return.
        observations = []
        for side, jars in sources.items():
            for args in (c["args"] for mode in ("explicit", "omitted") for c in json.loads((CASE / (mode + ".json")).read_bytes())["cases"]):
                p, meta = records["proofs"][side], records["plugins"][side]
                rep = capture(classes, w, side, args, jars, p, meta, "reference")
                check(rep, side, args, jars[1], jars[1], p, meta, mode="reference")
                observations.append({"side": side, "args": args, "reference": rep})
            for control, reason in (("stale", "stale updateTime proof"), ("plugin", "different plugin metadata URL")):
                try: capture(classes, w, side, args, jars, p, meta, "apply", control)
                except ValueError as e: require(reason in str(e), "unexpected refusal: " + str(e))
                else: raise ValueError("invalid scheduling dependency accepted")
                records["controls"][side + "-" + control] = reason
        records["originalUpdates"] = observations
        # Hold the public observation fixed while withholding a premise of the supplemented derivation.
        for side in sources:
            p, meta = records["proofs"][side], records["plugins"][side]
            c = records["runs"]["cold"]["claims"]["explicit"]
            ev = records["evidence"][c["receipt"]]
            r = ev["sides"][side]["trials"][0]["repetitions"][0]
            args = ev["cases"][0]["args"]
            real = sources[side][1]
            used = Path(ev["sides"][side]["orderedFiles"][1])
            for reason, changed, required in (("missing proof", r, None),
                    ("missing second calendar", r | {"events": r["events"][:6] + r["events"][7:]}, p),
                    ("missing final update", r | {"events": r["events"][:-3] + r["events"][-1:]}, p)):
                try: check(changed, side, args, real, used, required, meta, mode="apply")
                except ValueError as refusal: records["controls"][side + "-" + reason] = str(refusal)
                else: raise ValueError("withheld scheduling premise was accepted")
    destination = TARGET / "checked-scheduling.json.gz"
    destination.write_bytes(gzip.compress(json.dumps(records, separators=(",", ":")).encode(), mtime=0))
    audit()


def audit():
    frozen_cold(TARGET / "canonical/plans.zip")
    doc = json.loads(gzip.decompress((TARGET / "checked-scheduling.json.gz").read_bytes()))
    require(doc["frozenPlan"] == sha(TARGET / "canonical/plans.zip") and doc["publicControls"] == sha(TARGET / "processes.json"), "different opening")
    require(doc["tracer"]["frozenTrace"] == sha(ROOT / "examples/tools/targets/java/UpgradeTrace.java")
            and doc["tracer"]["frameValues"] == sha(HERE / "FrameValues.java")
            and doc["tracer"]["caseFrames"] == sha(CASE / "CaseFrames.java"), "different execution tools")
    registered = json.loads((CASE / "registration.json").read_bytes())
    require(all(sha(CASE / path) == value for path, value in registered["inputs"].items()), "different registration")
    for side in ("old", "new"):
        _, jars = deployment(side)
        require(doc["proofs"][side] == prove(jars[1]) and doc["plugins"][side] == plugin(jars[1]), "different effect or metadata")
        originals = [r for r in doc["originalUpdates"] if r["side"] == side]
        expected_inputs = {tuple(c["args"]) for m in ("explicit", "omitted") for c in json.loads((CASE / (m + ".json")).read_bytes())["cases"]}
        require(len(originals) == len(expected_inputs) and {tuple(r["args"]) for r in originals} == expected_inputs,
                "missing original update frames")
        for r in originals:
            check(r["reference"], side, r["args"], jars[1], jars[1], doc["proofs"][side], doc["plugins"][side], mode="reference")
        require(doc["controls"].get(side+"-stale") == "stale updateTime proof" and doc["controls"].get(side+"-plugin") == "different plugin metadata URL",
                "missing live negative control")
        require(doc["controls"].get(side+"-missing proof") == "missing scheduling effect proof"
                and all(doc["controls"].get(side+"-"+why) == "missing startup, receiver effect or scheduling call"
                        for why in ("missing second calendar", "missing final update")), "missing withheld-premise control")
    for left, right in (("cold","warm"), ("warm","clean"), ("cold","unrelated-warm"), ("unrelated-warm","unrelated-clean"),
                        ("replacement-warm","replacement-clean")):
        def outcomes(label):
            return {k:(c["receipt"], c["decision"], c["claimKey"]) for k,c in doc["runs"][label]["claims"].items()}
        require(outcomes(left) == outcomes(right), "resumed and independent evidence differ")
    for label, run in doc["runs"].items():
        for name, c in run["claims"].items():
            ev = doc["evidence"][c["receipt"]]
            require(change_inventory.digest(ev) == c["receipt"], "wrong application receipt digest")
            require(len(ev["cases"]) == 4, "incomplete scheduling domain")
            scope = json.loads((CASE / (name + ".json")).read_bytes())
            intent = next(n["intent"] for n in json.loads((CASE / "workflows.json").read_bytes())["workflows"] if n["id"] == name)
            require(change_evidence.compose(scope, ev, intent) == c["decision"], "different public composition")
            for deploy in ("old", "new"):
                side = "old" if deploy == "old" or label.startswith("replacement") else "new"
                _, jars = deployment(side)
                binding = ev["sides"][deploy]
                expected_cp = [r["sha256"] for r in deployment(side)[0]["classpath"]]
                require(binding["classpath"] == expected_cp and binding["publicProviderIndex"] == 1
                        and binding["callerClassSha256"] == doc["proofs"][side]["class"], "different ordered public provider")
                original_path = Path(binding["orderedFiles"][1])
                for item, trial in zip(ev["cases"], binding["trials"], strict=True):
                    require(len(trial["repetitions"]) == 2 and trial["observations"] == [r["public"] for r in trial["repetitions"]]
                            and trial["entryInvocations"] == [r["site"] for r in trial["repetitions"]], "different original repetitions")
                    for rep in trial["repetitions"]:
                        check(rep, side, item["args"], jars[1], original_path, doc["proofs"][side], doc["plugins"][side], mode="apply")
    print("Two original API-first claims, seven configurations, six effect partitions per deployment and sixteen untouched receiver frames verified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true")
    if parser.parse_args().audit: audit()
    else: run()

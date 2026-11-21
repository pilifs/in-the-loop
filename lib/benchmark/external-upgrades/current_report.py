"""Compare the 32 pinned caller questions against their V0 through V3 receipts."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from engineering_report import DATA, HERE, ROOT, RUNS, checked_finite, check_locked_observer, read, relative, short_value


def single(directory, pattern):
    paths = sorted(directory.glob(pattern))
    if len(paths) != 1:
        raise ValueError(f"expected one {pattern} under {directory}, found {len(paths)}")
    return paths[0]


def first_native_blocker(native):
    reason = native.get("native", {}).get("firstBlocker", "")
    if "receiver is outside the objects" in reason:
        return "receiver construction"
    if reason.startswith("parameter "):
        return "parameter construction"
    if "checker met" in reason and "--gaps strict" in reason:
        return "unsupported JVM or library operation"
    return reason or native.get("firstBlocker") or "unclassified"


def check_early(case, result):
    findings = []
    for comparison in result.get("beforeEntryComparison", []):
        if comparison["status"] != "reproduced earlier failure":
            continue
        i = comparison["input"]
        if result["status"] != "open" or comparison["before"] != result["cases"][i]["expected"]:
            raise ValueError("earlier failure reported as a downstream result")
        for side in ("old", "new"):
            binding = result["sides"][side]
            if (binding["commit"] != case["revisions"][side] or binding["sourceSha256"] != case["sourceSha256"]
                    or binding["dependency"] not in binding["classpath"]):
                raise ValueError("early observation has a different original input")
            trial = binding["trials"][i]
            if trial["input"] != i or not trial["loadedUpgradeOnEachReplay"]:
                raise ValueError("operand missing from a repeat")
            if side == "old":
                if trial["qualifiedMethodEntries"] != 2 or trial["observations"] != [comparison["before"]]*2:
                    raise ValueError("earlier failure has no independently matched old caller")
                continue
            pair = trial["beforeEntry"]
            if (trial["qualifiedMethodEntries"] or trial["observations"] or len(pair) != 2 or pair[0] != pair[1]
                    or comparison["after"] != {"throws": pair[0]["throws"]} or pair[0]["observerCodeIndex"] is None):
                raise ValueError("earlier failure lacks repeated pre-entry evidence")
            frames = pair[0]["frames"]
            for frame in frames:
                pos = frame["classpathIndex"]
                if not 0 <= pos < len(binding["classpath"]) or frame["jarSha256"] != binding["classpath"][pos]:
                    raise ValueError("throw frame refers to another artifact")
                role = "client" if pos == 0 else "upgrade" if binding["classpath"][pos] == binding["dependency"] else "classpath"
                if role != frame["artifact"]:
                    raise ValueError("throw frame has the wrong source")
            bound = [frame for frame in frames if frame["artifact"] in ("client", "upgrade")]
            if not bound:
                raise ValueError("throw stack has no original client or upgraded artifact")
            findings.append({**comparison, "firstOriginalFrame": bound[0], "causes": pair[0]["causes"],
                             "lastCauseMessage": pair[0].get("lastCauseMessage"), "rethrows": len(pair[0]["subsequentRethrows"])})
    return findings


def original_ci(case, directory):
    result = {}
    if directory.is_dir():
        for side in ("old", "new"):
            path = directory / side / "summary.json"
            doc = read(path)
            if doc["revision"] != case["revisions"][side]:
                raise ValueError("original CI revision mismatch")
            fresh = doc.get("freshReports", {})
            result[side] = {"status": doc["disposition"], "tests": fresh.get("tests", 0), "named": fresh.get("named", []),
                            "seconds": doc.get("seconds"), "receipt": relative(path)}
    return result


def validate_calls(case, finite, native):
    scope = read(HERE/"scenarios"/case["id"]/"scope.json")
    declared = scope.get("invocationVia", scope["entry"])
    evidence = finite.get("observerInvocation")
    if (finite.get("entry") != scope["entry"] or not evidence or evidence["declaration"] != declared
            or not evidence["codeIndices"] or any(type(pc) is not int or pc < 0 for pc in evidence["codeIndices"])):
        raise ValueError("missing compiled observer call sites for " + case["id"])
    for side, bound in finite["sides"].items():
        original = native["sides"][side]
        fixture = bound.get("frameworkFixtures")
        native_hashes = original.get("orderedSha256", [])
        if (bound["commit"] != case["revisions"][side] or bound["sourceSha256"] != case["sourceSha256"]
                or bound["callerClassSha256"] != original.get("callerClassSha256")
                or bound["classpath"][:len(native_hashes)] != native_hashes or not native_hashes
                or bool(fixture) != scope.get("withTestFixtures", False) or fixture != original.get("frameworkFixtures")):
            raise ValueError("caller, classpath or fixture binding differs for " + case["id"])
        if fixture:
            n = fixture["runtimeCount"]
            if not 1 < n < len(native_hashes) or native_hashes[n] != fixture["testClassesSha256"] or bound["dependency"] not in native_hashes[1:n]:
                raise ValueError("fixture supplies a required production operand")
        for trial in bound.get("trials", []):
            calls = trial.get("entryInvocations", [])
            if (len(calls) != trial["qualifiedMethodEntries"] or any(
                    c["observerCodeIndex"] not in evidence["codeIndices"] or "#" not in c["dispatchedTo"] for c in calls)):
                raise ValueError("missing live dispatch evidence")
            thrown = [r["throws"] for r in trial["observations"] if "throws" in r]
            escapes = trial.get("escapingExceptions", [])
            if ([e["throws"] for e in escapes] != thrown or any(e["entry"] != scope["entry"]
                    or e["jarSha256"] != bound["classpath"][0] or e["observerCodeIndex"] not in evidence["codeIndices"]
                    or e["codeIndex"] < 0 for e in escapes)):
                raise ValueError("an exception did not cross the selected original invocation")


def validate_diagnoses(finite):
    causes, members, drivers = [], [], []
    for comparison in finite.get("beforeEntryComparison", []):
        if not any(k in comparison for k in ("changedRuntimeCause", "memberLinkage", "jdbcDriver")):
            continue
        i = comparison["input"]
        old, new = (finite["sides"][s] for s in ("old", "new"))
        before, after = old["trials"][i], new["trials"][i]
        pair = after.get("beforeEntry", [])
        if (before["observations"] != [finite["cases"][i]["expected"]] * 2 or before["qualifiedMethodEntries"] != 2
                or len(pair) != 2 or pair[0] != pair[1] or after["qualifiedMethodEntries"] or finite["status"] != "open"):
            raise ValueError("a startup diagnosis lacks two original observations on both sides")
        failure = pair[0]
        root = failure.get("rootThrow", {}) if len(failure["causes"]) > 1 else failure
        if cause := comparison.get("changedRuntimeCause"):
            frame = cause["frame"]
            if (cause["type"] != failure["causes"][-1] or frame != root.get("throwLocation")
                    or cause["observerCodeIndex"] != root["observerCodeIndex"]
                    or not 0 < frame["classpathIndex"] < new.get("frameworkFixtures", {}).get("runtimeCount", len(new["classpath"]))
                    or frame["jarSha256"] != new["classpath"][frame["classpathIndex"]] or frame["jarSha256"] in old["classpath"]):
                raise ValueError("root cause does not bind to a changed runtime dependency")
            causes.append({"input": i, **cause})
        if link := comparison.get("memberLinkage"):
            inst = link["instruction"]
            site = inst["location"]
            old_lookup, new_lookup = (link["sides"][s] for s in ("old", "new"))
            if (inst != failure["memberInstruction"] or site != root["throwLocation"] or site["codeIndex"] < 0
                    or any(len(site[k]) != 64 for k in ("methodCodeSha256", "constantPoolSha256"))
                    or inst["executingClassSha256"] != new_lookup["executingClassSha256"]
                    or inst["referenceKind"] not in new_lookup["referenceKinds"]
                    or inst["ownerJarSha256"] != new_lookup["jarSha256"]
                    or new_lookup["jarSha256"] != new["classpath"][new_lookup["classpathIndex"]]
                    or old_lookup["jarSha256"] != old["classpath"][old_lookup["classpathIndex"]]):
                raise ValueError("member diagnosis differs from the exact loaded inputs")
            if new_lookup["lookup"] != "missing" and not (inst["opcode"] == "invokeinterface" and new_lookup["ownerKind"] == "class"):
                raise ValueError("the independently resolved operand does not explain the failure")
            members.append({"input": i, **link})
        if driver := comparison.get("jdbcDriver"):
            url = failure["lastCauseMessage"].removeprefix("No suitable driver found for ")
            checked = finite["jdbcDriverEvidence"][driver["urlSha256"]]
            selected = checked["old"]["selection"]
            blocked = [p for p in checked["new"]["providers"] if p["name"] in driver["incompatibleProviders"]]
            if (hashlib.sha256(url.encode()).hexdigest() != driver["urlSha256"] or failure["causes"][-1] != "java.sql.SQLException"
                    or driver["throwLocation"] != root["runtimeThrowLocation"] or not root["runtimeThrowLocation"]["entry"].startswith("java.sql.DriverManager#")
                    or selected["name"] != driver["selectedBefore"] or selected["jarSha256"] != old["dependency"]
                    or selected["name"] not in old["loadedDependencyClasses"] or checked["new"]["selection"] != {"outcome": "none", "sqlState": "08001"}
                    or not blocked or any(p["jarSha256"] != new["dependency"] or p.get("error") != "java.lang.UnsupportedClassVersionError"
                                          or p["classMajor"] <= checked["new"]["maxClassMajor"] for p in blocked)):
                raise ValueError("incomplete evidence for JDBC provider incompatibility")
            drivers.append({"input": i, **driver, "classMajor": blocked[0]["classMajor"], "maxClassMajor": checked["new"]["maxClassMajor"]})
    return {"changedRuntimeCauses": causes, "memberLinkages": members, "jdbcDrivers": drivers}


def archived_ci(case, batch):
    paths = list((RUNS/batch).glob("*/"+case["id"]+"/old/summary.json"))
    if len(paths) > 1:
        raise ValueError("ambiguous original CI for " + case["id"])
    return original_ci(case, paths[0].parents[1]) if paths else {}


def engineering_passes(cases, product_revision):
    passes = {}
    for phase in ("prep", "dispatch", "cause", "final"):
        files = sorted((ROOT/"verification/results").glob(f"*-v3-{phase}-group-*/result.json"))
        jobs = [read(f) for f in files]
        revisions = {job["sourceCommit"] for job in jobs}
        if len(jobs) != 7 or len(revisions) != 1 or any(j["status"] != "passed" or j["collected"]["conflicts"] for j in jobs):
            raise ValueError("incomplete engineering pass " + phase)
        revision, = revisions
        if phase == "final" and revision != product_revision:
            raise ValueError("final pass differs from the product pin")
        hashes = {r["path"]: r["sha256"] for job in jobs for r in job["outputs"]}
        record = {"revision": revision, "jobs": [j["id"] for j in jobs], "originalPairsReady": 0, "oldDomainsMatched": 0,
                  "historicalChanges": 0, "routinePreservations": 0, "transferDecisions": 0, "timeouts": []}
        for case in cases:
            key = case["id"]
            paths = [single(RUNS/f"v3-{phase}-finite", "*/"+key+".json"),
                     single(RUNS/f"v3-{phase}-native", "*/current/"+key+".json")]
            for path in paths:
                if hashes.get(relative(path)) != hashlib.sha256(path.read_bytes()).hexdigest():
                    raise ValueError("engineering pass output differs from its job: " + relative(path))
            finite, native = map(read, paths)
            record["originalPairsReady"] += all(s.get("stage") == "artifacts ready" for s in native["sides"].values())
            expected = "changed" if case["stratum"] == "reported-change" else "preserved"
            decision = checked_finite(case, finite)
            if decision == expected and finite.get("operandScope") != "test":
                field = "transferDecisions" if case["set"] == "transfer" else "historicalChanges" if decision == "changed" else "routinePreservations"
                record[field] += 1
            trials = finite.get("sides", {}).get("old", {}).get("trials", [])
            domain = finite.get("cases", [])
            record["oldDomainsMatched"] += int(bool(domain) and len(trials) == len(domain) and all(
                t["observations"] == [c["expected"]] * 2 and t["qualifiedMethodEntries"] == 2 for t,c in zip(trials, domain)))
            if "timed out" in (finite.get("reason") or "").lower():
                record["timeouts"].append(key)
        passes[phase] = record
    return passes


def h2_controls(revision):
    result_path = single(ROOT/"verification/results", "*-v3-h2-original-jdbc-driver-selection-and/result.json")
    job = read(result_path)
    if job["status"] != "passed" or job["sourceCommit"] != revision or job["collected"]["conflicts"]:
        raise ValueError("the H2 control did not pass at the pinned product")
    outputs = {r["path"]: r["sha256"] for r in job["outputs"]}
    target = read(ROOT/"examples/348-rxjava-jdbc-generated-keys/target.json")
    for side in ("old", "new"):
        artifacts = [a for a in target["preparation"]["artifacts"] if a["revision"] == side]
        h2, = [a["sha256"] for a in artifacts if a["coordinates"].startswith("com.h2database:h2:")]
        for name, url in (("original", "jdbc:h2:mem:calibration;DB_CLOSE_DELAY=-1"), ("unmatched", "jdbc:unregistered:control")):
            path = RUNS/"v3-h2-driver"/side/(name+".json")
            doc = read(path)
            if (outputs.get(relative(path)) != hashlib.sha256(path.read_bytes()).hexdigest()
                    or doc["classpath"] != [a["sha256"] for a in artifacts] or doc["status"] != "checked"
                    or doc["dependency"] != h2 or doc["urlSha256"] != hashlib.sha256(url.encode()).hexdigest()):
                raise ValueError("H2 control differs from its original artifacts and URL")
            found = doc["driver"]["selection"]
            if name == "original" and (found.get("name") != "org.h2.Driver" or found.get("jarSha256") != h2):
                raise ValueError("H2 did not select its original driver")
            if name == "unmatched" and found != {"outcome": "none", "sqlState": "08001"}:
                raise ValueError("unmatched URL unexpectedly selected a driver")
    return {"job": job["id"], "receipt": relative(result_path), "scope": "driver selection on two URLs and two original classpaths"}


def summarize():
    cases = read(HERE / "corpus.json")["cases"]
    baseline = read(DATA / "v2-scorecard.json")
    lock = read(HERE / "v3.json")
    jobs = []
    outputs = {}
    for file in sorted((ROOT/"verification/results").glob("*-v3-final-group-*/result.json")):
        job = read(file)
        if job["sourceCommit"] == lock["revision"]:
            if job["status"] != "passed" or job["collected"]["conflicts"]:
                raise ValueError("the pinned workload did not finish cleanly")
            jobs.append(job["id"])
            for item in job["outputs"]:
                if item["path"] in outputs:
                    raise ValueError("two jobs claim the same V3 output")
                outputs[item["path"]] = item["sha256"]
    if len(jobs) != 7:
        raise ValueError("expected seven completed caller groups at the pinned product revision")
    current = {}
    for case in cases:
        key = case["id"]
        previous = baseline["cases"][key]
        f = single(RUNS/"v3-final-finite", "*/"+key+".json")
        n = single(RUNS/"v3-final-native", "*/current/"+key+".json")
        for path in (f, n):
            if outputs.get(relative(path)) != hashlib.sha256(path.read_bytes()).hexdigest():
                raise ValueError("evidence differs from the pinned job: " + relative(path))
        finite, native = read(f), read(n)
        if native["revisions"] != case["revisions"] or native["checkerSha256"] != lock["sha256"]["jvmcontract"]:
            raise ValueError("native report differs from the registered pair or checker")
        if "specSha256" in finite:
            check_locked_observer(HERE/"scenarios"/key, finite)
        if "tracerSha256" in finite:
            for name, field in (("UpgradeObservation.java","launcherSha256"), ("UpgradeTrace.java","tracerSha256"),
                                ("UpgradeClassLookup.java", "lookupSha256")):
                if hashlib.sha256((ROOT/"examples/tools/targets/java"/name).read_bytes()).hexdigest() != finite[field]:
                    raise ValueError("the measured Java workflow has changed")
        validate_calls(case, finite, native)
        new_diagnoses = validate_diagnoses(finite)
        state = checked_finite(case, finite)
        expected = "changed" if case["stratum"] == "reported-change" else "preserved"
        scope = (read(HERE/"scenarios"/key/"scope.json").get("operandScope", "runtime")
                 if (HERE/"scenarios"/key/"scope.json").is_file() else "runtime")
        if "operandScope" in finite and finite["operandScope"] != scope:
            raise ValueError("replay used a different dependency environment")
        relevant = state == expected and scope != "test"
        old, new = (finite.get("sides", {}).get(s, {}).get("trials", []) for s in ("old", "new"))
        stopped = finite.get("stoppedAt", {})
        failed_trials = finite.get("sides", {}).get(stopped.get("side"), {}).get("trials", [])
        failed = (failed_trials[stopped["input"]].get("beforeEntry", []) if
                  "input" in stopped and stopped["input"] < len(failed_trials) else [])
        differences = [{"input": i, "before": old[i]["observations"][0], "after": new[i]["observations"][0]}
                       for i in finite.get("differences", [])]
        missing = []
        for comparison in finite.get("beforeEntryComparison", []):
            if "missingClass" not in comparison:
                continue
            proof = comparison["missingClass"]
            name, i = proof["name"], comparison["input"]
            old_side, new_side = (finite["missingClassEvidence"][name][side] for side in ("old", "new"))
            before, after = old[i], new[i]
            if (new_side["lookup"] != {"outcome": "missing"} or new_side["providers"] or
                    before["observations"] != [finite["cases"][i]["expected"]] * 2 or
                    before["qualifiedMethodEntries"] != 2 or after["qualifiedMethodEntries"] or
                    not after["repeatableBeforeEntry"] or
                    any(t["lastCauseMessage"].replace("/", ".") != name for t in after["beforeEntry"])):
                raise ValueError("missing-class diagnosis lacks the paired JVM observations")
            if old_side["lookup"]["outcome"] == "found":
                if (not proof["loadedFromOldUpgradeOnBothCallerReplays"] or
                        old_side["lookup"]["jarSha256"] != finite["sides"]["old"]["dependency"] or
                        not any(p["jarSha256"] == old_side["lookup"]["jarSha256"] for p in old_side["providers"])):
                    raise ValueError("the claimed old class provider differs from the loaded operand")
            elif (old_side["lookup"]["outcome"] != "missing" or old_side["providers"] or
                  old_side["referringClassesInUpgrade"] or not new_side["referringClassesInUpgrade"]):
                raise ValueError("missing-class reference change is unsubstantiated")
            missing.append({"input": i, **proof})
        current[key] = {"set": case["set"], "stratum": case["stratum"], "familyRelation": case.get("familyRelation"),
            "v0": previous["v0"], "v1": previous["v1"], "v2": previous["v2"], "v2Relevant": previous["v2Relevant"],
            "v3": state, "v3Relevant": relevant, "operandScope": scope, "inputs": len(finite.get("cases", [])),
            "domainBasis": finite.get("domainBasis"), "frameworkFixtures": "frameworkFixtures" in finite.get("sides", {}).get("old", {}),
            "oldDomainMatched": bool(old) and len(old) == len(finite["cases"]) and
                all(t["observations"] == [c["expected"]] * 2 and t["qualifiedMethodEntries"] == 2
                    for t, c in zip(old, finite["cases"])), **new_diagnoses,
            "oldFixtureObservations": [t["observations"][0] for t in old if t["observations"]]
                if "frameworkFixtures" in finite["sides"]["old"] else [],
            "differences": differences, "missingClasses": missing, "earlierFailures": check_early(case, finite),
            "beforeEntry": finite.get("beforeEntryComparison", []), "finiteReason": finite.get("reason"),
            "firstEarlyException": ({"side": stopped["side"], "throws": failed[0]["throws"],
                                     "cause": failed[0]["causes"][-1], "message": failed[0].get("lastCauseMessage")}
                                    if failed and failed[0]["causes"] else None),
            "finite": relative(f), "finiteSeconds": finite["elapsedSeconds"], "native": relative(n),
            "nativeSeconds": native["elapsedSeconds"], "nativeStop": native.get("firstBlocker"),
            "firstNativeBlocker": first_native_blocker(native),
            "preparedOnBothSides": all(native["sides"][s].get("stage") == "artifacts ready" for s in ("old","new")),
            "originalCiRecovery": previous["originalCiRecovery"] or archived_ci(case, "original-ci"),
            "focusedCiRecovery": previous["focusedCiRecovery"] or archived_ci(case, "focused-ci")}
    if len(current) != 32:
        raise ValueError("incomplete upgrade corpus")
    groups = {}
    for name in ("main", "transfer"):
        group = [row for row in current.values() if row["set"] == name]
        groups[name] = {"total": len(group), "relevantChanges": sum(r["v3Relevant"] and r["v3"] == "changed" for r in group),
                        "relevantPreservations": sum(r["v3Relevant"] and r["v3"] == "preserved" for r in group),
                        "changedRoutineClaims": sum(r["stratum"] == "routine" and r["v3"] == "changed" for r in group),
                        "earlierFailures": sum(bool(r["earlierFailures"]) for r in group),
                        "missingClassDiagnoses": sum(bool(r["missingClasses"]) for r in group),
                        "operationalDiagnoses": sum(bool(r["missingClasses"] or r["earlierFailures"] or r["changedRuntimeCauses"] or r["memberLinkages"] or r["jdbcDrivers"]) for r in group),
                        "preparedOnBothSides": sum(r["preparedOnBothSides"] for r in group),
                        "matchedOldDomain": sum(r["oldDomainMatched"] for r in group),
                        "firstNativeBlockers": dict(Counter(r["firstNativeBlocker"] for r in group)),
                        "frameworkFixturePairs": sum(r["frameworkFixtures"] for r in group),
                        "memberLinkages": sum(bool(r["memberLinkages"]) for r in group),
                        "jdbcDriverDiagnoses": sum(bool(r["jdbcDrivers"]) for r in group),
                        "v2Relevant": sum(r["v2Relevant"] for r in group),
                        "regressions": [k for k,r in current.items() if r["set"] == name and r["v2Relevant"] and not r["v3Relevant"]]}
    paired_names = {(True, True): "both", (True, False): "v0Only", (False, True): "v3Only", (False, False): "neither"}
    paired = dict.fromkeys(paired_names.values(), 0)
    by_family = {}
    for row in (r for r in current.values() if r["set"] == "transfer"):
        target = "changed" if row["stratum"] == "reported-change" else "preserved"
        earlier, now = row["v0"] == target, row["v3Relevant"]
        paired[paired_names[earlier, now]] += 1
        family = by_family.setdefault(row["familyRelation"], {"relevant": 0, "total": 0})
        family["total"] += 1
        family["relevant"] += now
    return {"productRevision": lock["revision"], "engineeringPasses": engineering_passes(cases, lock["revision"]),
            "h2DriverControl": h2_controls(lock["revision"]), "jobs": jobs, "pairedTransfer": paired, "transferByFamily": by_family,
            "operatorPin": lock["plannerAndProver"],
            "watcherSession": {"model": "gpt-6.2-astra", "effort": "max", "separateModelInvocations": 0},
            "pilot": {"teams": 0, "reviewed": 0, "target": 15}, "route": "reviewed finite JVM observers",
            "humanMinutesPerCase": None, "inferenceCostPerCase": None, "v0Revision": read(HERE/"v0.json")["revision"],
            "v1Revision": read(HERE/"v1.json")["revision"], "v2Revision": baseline["productRevision"], "groups": groups, "cases": current}, cases


def render(data, cases):
    lines = ["# Current Java upgrade decisions", "", "These reports cover all 32 registered callers. Each finite result applies to its stated inputs. The Derby comparison uses the original test environment.", ""]
    for case in cases:
        key = case["id"]
        row = data["cases"][key]
        link = "../../" + row["finite"]
        result = row["v3"]
        if row["differences"]:
            first = row["differences"][0]
            outcome = (f"{len(row['differences'])} of {row['inputs']} inputs changed. Input {first['input']} produced "
                       f"{short_value(first['before'])} before and {short_value(first['after'])} after.")
        elif result == "preserved":
            outcome = f"Both versions matched the independent expectations on all {row['inputs']} inputs."
        else:
            outcome = (row["finiteReason"] or row["nativeStop"] or "The selected operation remains open.").split("\n")[0]
            if not row["inputs"]:
                outcome = str(row["nativeStop"] or outcome).split("\n")[0]
                link = "../../" + row["native"]
            outcome = outcome.replace(str(Path.home()), "~")[:450]
        if row["beforeEntry"] and row["firstEarlyException"]:
            e = row["firstEarlyException"]
            if all(t["status"] == "stopped before entry on both revisions" for t in row["beforeEntry"]):
                outcome = f"Both revisions stopped before the selected method on {len(row['beforeEntry'])} inputs."
            else:
                which = "old" if e["side"] == "old" else "upgraded"
                outcome = f"The {which} JVM stopped before the selected method. Its escaping exception was `{e['throws']}`."
            if e["message"]:
                outcome += f" The innermost recorded cause was `{e['cause']}` ({e['message'][:220]})."
        if row["earlierFailures"]:
            finding = row["earlierFailures"][0]
            frame = finding["firstOriginalFrame"]
            position = f"line {frame['sourceLine']}" if frame['sourceLine'] > 0 else f"bytecode offset {frame['codeIndex']}"
            outcome = (f"The old observer produced {short_value(finding['before'])}. On the upgrade it stopped before the selected method. "
                       f"The JVM traced the escaping {finding['after']['throws']} to `{frame['entry']}` at {position}. "
                       f"The recorded cause ends in `{finding['causes'][-1]}`.")
        if row["missingClasses"]:
            missing = row["missingClasses"][0]
            outcome += (f" Fresh JVM lookups found `{missing['name']}` in the old upgraded JAR and absent from every new input JAR."
                        if missing["relationship"].startswith("old upgraded") else
                        f" Both JVMs lacked `{missing['name']}`. The upgraded JAR introduced a symbolic reference to it.")
        action = ("Review the changed return or exception before adopting the new pin." if row["v3Relevant"] and result == "changed"
                  else "Retain this specific caller expectation when reviewing the upgrade." if row["v3Relevant"]
                  else "Review this as a developer-test dependency. A production decision requires a production use."
                  if row["operandScope"] == "test" else "Resolve the earlier failure and rerun the downstream operation."
                  if row["earlierFailures"] or row["missingClasses"] else "Keep the historical change open on this input domain." if result=="preserved"
                  else "Use the recorded original CI and address the first unresolved step.")
        if row["missingClasses"]:
            name = row["missingClasses"][0]["name"]
            action = f"Review the dependency providing `{name}` and rerun the caller with compatible versions."
        if row["changedRuntimeCauses"]:
            cause = row["changedRuntimeCauses"][0]
            outcome += (f" The debugger matched the escaping root `{cause['type']}` to "
                        f"`{cause['frame']['entry']}` in a production JAR introduced by the upgrade.")
            action = "Restore a compatible runtime closure and repeat the original business operation."
        if row["memberLinkages"]:
            link_evidence = row["memberLinkages"][0]
            inst = link_evidence["instruction"]
            member = inst["owner"] + "#" + inst["name"] + inst["descriptor"]
            if link_evidence["reason"] == "interface invocation resolved to a class":
                outcome += (f" The upgraded `{inst['opcode']}` instruction requires `{inst['owner']}` to be an "
                            f"interface. Both JVMs resolved it as a class.")
            else:
                old_status = link_evidence["sides"]["old"]["lookup"]
                where = "on both original classpaths" if old_status == "missing" else "on the upgraded classpath"
                outcome += f" Fresh JVM lookups found the `{inst['opcode']}` operand `{member}` missing {where}."
            action = f"Align the dependency supplying `{inst['owner']}` with the calling library and replay the original input."
        if row["jdbcDrivers"]:
            driver = row["jdbcDrivers"][0]
            outcome += (f" The old JVM selected `{driver['selectedBefore']}`. The new service provider requires classfile "
                        f"version {driver['classMajor']}. The subject JVM supports through {driver['maxClassMajor']}.")
            action = "Use a driver compatible with the subject JDK or rerun on a supported JDK and check the stored rows."
        if row["oldFixtureObservations"] and row["oldDomainMatched"]:
            values = ", ".join(short_value(value) for value in row["oldFixtureObservations"])
            outcome += f" The old framework returned {values} in input order."
        ci = row["focusedCiRecovery"] or row["originalCiRecovery"]
        ci_text = ""
        if ci:
            def ci_label(side):
                item = ci[side]
                return ", ".join(r["outcome"] for r in item["named"]) or item["status"]
            ci_text = f" Original CI recorded `{ci_label('old')}` before and `{ci_label('new')}` after. [Original CI](../../{ci['new']['receipt']})"
        basis = row["domainBasis"] or "The native attempt used the registered original module and caller."
        environment = {"runtime": "The check uses the original runtime dependencies.",
                       "provided": "The host supplies the original declared API.",
                       "test": "The check uses Maven's original test classpath."}[row["operandScope"]]
        if row["frameworkFixtures"]:
            environment += " The original Maven test classes and resources follow the production classpath."
        versions_link = case["repository"] + "/compare/" + case["revisions"]["old"] + "..." + case["revisions"]["new"]
        v = case["versions"]
        client = case["repository"].rsplit("/", 1)[-1]
        lines += [f"## {client} · {key}", "", f"**Upgrade** {case['dependency']} `{v['old']}` → `{v['new']}`. [Original revisions]({versions_link})",
                  "", f"**Caller-visible behavior** `{case['entry']}`. {case['observer']}", "",
                  f"**Result** {result.capitalize()}. {outcome} [Receipt]({link})", "",
                  f"**Scope** {basis} {environment} V0 was {row['v0']} and V2 was {row['v2']}.{ci_text}",
                  "", f"**Review action** {action}", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data, cases = summarize()
    for path, content in ((DATA/"v3-scorecard.json", json.dumps(data, indent=2)+"\n"),
                          (ROOT/"llm-dlc/loops/external-upgrade-current-cases.md", render(data, cases))):
        if args.check:
            if path.read_text() != content:
                raise SystemExit("report differs: " + relative(path))
        else:
            path.write_text(content)
    print(json.dumps(data["groups"]))

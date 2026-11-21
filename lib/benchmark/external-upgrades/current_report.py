"""Compare the 32 pinned caller questions against their V0, V1 and V2 receipts."""
import argparse
import hashlib
import json
from pathlib import Path

from engineering_report import DATA, HERE, ROOT, RUNS, checked_finite, check_locked_observer, read, relative, short_value


def single(directory, pattern):
    paths = sorted(directory.glob(pattern))
    if len(paths) != 1:
        raise ValueError(f"expected one {pattern} under {directory}, found {len(paths)}")
    return paths[0]


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


def summarize():
    cases = read(HERE / "corpus.json")["cases"]
    baseline = read(DATA / "scorecard.json")
    lock = read(HERE / "v2.json")
    jobs = []
    outputs = {}
    for file in sorted((ROOT/"verification/results").glob("*-final-v2-group-*/result.json")):
        job = read(file)
        if job["sourceCommit"] == lock["revision"]:
            if job["status"] != "passed" or job["collected"]["conflicts"]:
                raise ValueError("the pinned workload did not finish cleanly")
            jobs.append(job["id"])
            for item in job["outputs"]:
                if item["path"] in outputs:
                    raise ValueError("two jobs claim the same V2 output")
                outputs[item["path"]] = item["sha256"]
    if len(jobs) != 7:
        raise ValueError("expected seven completed caller groups at the pinned product revision")
    current = {}
    for case in cases:
        key = case["id"]
        previous = baseline["cases"][key]
        f = single(RUNS/"v2-final-finite", "*/"+key+".json")
        n = single(RUNS/"v2-final-native", "*/current/"+key+".json")
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
            "v0": previous["v0"], "v1": previous["current"], "v1Relevant": previous["relevant"],
            "v2": state, "v2Relevant": relevant, "operandScope": scope, "inputs": len(finite.get("cases", [])),
            "domainBasis": finite.get("domainBasis"),
            "differences": differences, "missingClasses": missing, "earlierFailures": check_early(case, finite),
            "beforeEntry": finite.get("beforeEntryComparison", []), "finiteReason": finite.get("reason"),
            "firstEarlyException": ({"side": stopped["side"], "throws": failed[0]["throws"],
                                     "cause": failed[0]["causes"][-1], "message": failed[0].get("lastCauseMessage")}
                                    if failed and failed[0]["causes"] else None),
            "finite": relative(f), "finiteSeconds": finite["elapsedSeconds"], "native": relative(n),
            "nativeSeconds": native["elapsedSeconds"], "nativeStop": native.get("firstBlocker"),
            "preparedOnBothSides": all(native["sides"][s].get("stage") == "artifacts ready" for s in ("old","new")),
            "originalCiRecovery": original_ci(case, RUNS/"v2-final-original-ci"/key/key) or original_ci(case, RUNS/"v2-original-ci"/key/key),
            "focusedCiRecovery": original_ci(case, RUNS/"v2-final-focused-ci"/key) or original_ci(case, RUNS/"v2-focused-ci"/key) or
                original_ci(case, RUNS/"restored-legacy-maven"/key/"original-test"/key)}
    if len(current) != 32:
        raise ValueError("incomplete upgrade corpus")
    groups = {}
    for name in ("main", "transfer"):
        group = [row for row in current.values() if row["set"] == name]
        groups[name] = {"total": len(group), "relevantChanges": sum(r["v2Relevant"] and r["v2"] == "changed" for r in group),
                        "relevantPreservations": sum(r["v2Relevant"] and r["v2"] == "preserved" for r in group),
                        "changedRoutineClaims": sum(r["stratum"] == "routine" and r["v2"] == "changed" for r in group),
                        "earlierFailures": sum(bool(r["earlierFailures"]) for r in group),
                        "missingClassDiagnoses": sum(bool(r["missingClasses"]) for r in group),
                        "operationalDiagnoses": sum(bool(r["missingClasses"] or r["earlierFailures"]) for r in group),
                        "preparedOnBothSides": sum(r["preparedOnBothSides"] for r in group),
                        "v1Relevant": sum(r["v1Relevant"] for r in group),
                        "regressions": [k for k,r in current.items() if r["set"] == name and r["v1Relevant"] and not r["v2Relevant"]]}
    paired_names = {(True, True): "both", (True, False): "v0Only", (False, True): "v2Only", (False, False): "neither"}
    paired = dict.fromkeys(paired_names.values(), 0)
    by_family = {}
    for row in (r for r in current.values() if r["set"] == "transfer"):
        target = "changed" if row["stratum"] == "reported-change" else "preserved"
        earlier, now = row["v0"] == target, row["v2Relevant"]
        paired[paired_names[earlier, now]] += 1
        family = by_family.setdefault(row["familyRelation"], {"relevant": 0, "total": 0})
        family["total"] += 1
        family["relevant"] += now
    return {"productRevision": lock["revision"], "jobs": jobs, "pairedTransfer": paired, "transferByFamily": by_family,
            "operatorPin": lock["plannerAndProver"],
            "watcherSession": {"model": "gpt-6.2-astra", "effort": "max", "separateModelInvocations": 0},
            "pilot": {"teams": 0, "reviewed": 0, "target": 15}, "route": "reviewed finite JVM observers",
            "humanMinutesPerCase": None, "inferenceCostPerCase": None, "v0Revision": read(HERE/"v0.json")["revision"],
            "v1Revision": read(HERE/"v1.json")["revision"], "groups": groups, "cases": current}, cases


def render(data, cases):
    lines = ["# Current Java upgrade decisions", "", "These reports cover all 32 registered callers. Each finite result applies to its stated inputs. The Derby comparison uses the original test environment.", ""]
    for case in cases:
        key = case["id"]
        row = data["cases"][key]
        link = "../../" + row["finite"]
        result = row["v2"]
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
        action = ("Review the changed return or exception before adopting the new pin." if row["v2Relevant"] and result == "changed"
                  else "Retain this specific caller expectation when reviewing the upgrade." if row["v2Relevant"]
                  else "Review this as a developer-test dependency. A production decision requires a production use."
                  if row["operandScope"] == "test" else "Resolve the earlier failure and rerun the downstream operation."
                  if row["earlierFailures"] or row["missingClasses"] else "Keep the historical change open on this input domain." if result=="preserved"
                  else "Use the recorded original CI and address the first unresolved step.")
        if row["missingClasses"]:
            name = row["missingClasses"][0]["name"]
            action = f"Review the dependency providing `{name}` and rerun the caller with compatible versions."
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
        versions_link = case["repository"] + "/compare/" + case["revisions"]["old"] + "..." + case["revisions"]["new"]
        v = case["versions"]
        client = case["repository"].rsplit("/", 1)[-1]
        lines += [f"## {client} · {key}", "", f"**Upgrade** {case['dependency']} `{v['old']}` → `{v['new']}`. [Original revisions]({versions_link})",
                  "", f"**Caller-visible behavior** `{case['entry']}`. {case['observer']}", "",
                  f"**Result** {result.capitalize()}. {outcome} [Receipt]({link})", "",
                  f"**Scope** {basis} {environment} V0 was {row['v0']} and V1 was {row['v1']}.{ci_text}",
                  "", f"**Review action** {action}", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data, cases = summarize()
    for path, content in ((DATA/"v2-scorecard.json", json.dumps(data, indent=2)+"\n"),
                          (ROOT/"llm-dlc/loops/external-upgrade-current-cases.md", render(data, cases))):
        if args.check:
            if path.read_text() != content:
                raise SystemExit("report differs: " + relative(path))
        else:
            path.write_text(content)
    print(json.dumps(data["groups"]))

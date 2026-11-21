"""Summarize actual first attempts and qualified recovery evidence for each original upgrade."""

from collections import Counter
import hashlib
import json
from pathlib import Path

from pin import ROOT


HERE = Path(__file__).resolve().parent
DATA = ROOT / "verification/external-upgrades"
RUNS = DATA / "corpus-runs"
REPORTS = ROOT / "llm-dlc/loops/external-upgrade-case-reports.md"


def read(path):
    return json.loads(path.read_text())


def find(epoch, case, build=""):
    files = list((RUNS/epoch).glob("*/" + (build+"/" if build else "") + case + ".json"))
    if len(files)>1:
        raise ValueError("duplicate result for "+case+" in "+epoch)
    return files[0] if files else None


def relative(path):
    return path.relative_to(ROOT).as_posix()


def checked_finite(case, document):
    if document.get("status") not in ("changed","preserved"):
        return "open"
    if document["entry"].split("(")[0] != case["entry"]:
        raise ValueError("reviewed finite entry differs from the corpus subject: "+case["id"])
    cases=document["cases"]
    if not cases or len({tuple(r["args"]) for r in cases})!=len(cases):
        raise ValueError("missing or duplicated finite inputs")
    if set(document["sides"])!={"old","new"}:
        raise ValueError("one-sided finite report")
    answers={}
    for side,row in document["sides"].items():
        if (row["commit"]!=case["revisions"][side] or row["sourceSha256"]!=case["sourceSha256"]
                or row["dependency"] not in row["classpath"] or not row["loadedDependencyClasses"] or not row["callerClassSha256"]):
            raise ValueError("original input binding missing for "+case["id"])
        if [t["input"] for t in row["trials"]]!=list(range(len(cases))):
            raise ValueError("incomplete or reordered observations")
        values=[]
        for trial in row["trials"]:
            pair=trial["observations"]
            if trial["qualifiedMethodEntries"]!=2 or len(pair)!=2 or pair[0]!=pair[1]:
                raise ValueError("unrepeated or unqualified observation")
            values.append(pair[0])
        answers[side]=values
    if answers["old"]!=[r["expected"] for r in cases] or document["oldOracleDisagreements"]:
        raise ValueError("the old expected observation is contradicted")
    differences=[i for i,(a,b) in enumerate(zip(answers["old"],answers["new"])) if a!=b]
    state="changed" if differences else "preserved"
    if differences!=document["differences"] or state!=document["status"]:
        raise ValueError("finite disposition differs from the observations")
    return state


def short_value(x):
    text=json.dumps(x,ensure_ascii=True)
    return text if len(text)<=120 else text[:117]+"..."


def original_ci(epoch, case):
    roots = list((RUNS / epoch).glob("*/" + case["id"] + "/old/summary.json"))
    if len(roots) > 1:
        raise ValueError("duplicate original CI result for " + case["id"])
    result = {}
    for root in roots:
        for side in ("old", "new"):
            path = root.parents[1] / side / "summary.json"
            if not path.is_file():
                continue
            document = read(path)
            if document["revision"] != case["revisions"][side]:
                raise ValueError("CI revision differs for " + case["id"])
            fresh = document.get("freshReports", {})
            result[side] = {"file": relative(path), "status": document["disposition"],
                            "tests": fresh.get("tests", 0), "seconds": document.get("seconds"),
                            "namedTestExecuted": document.get("namedTestExecuted"), "named": fresh.get("named", [])}
    return result


def compcheck(case):
    file = DATA / "compcheck-runs" / case["id"] / "treatments.json"
    if not file.is_file():
        return None
    records = read(file)
    if not all(item["revision"] == case["revisions"]["old"] for item in records):
        raise ValueError("CompCheck original source revision differs")
    return {"file": relative(file), "sites": sorted({item["site"] for item in records}),
            "treatments": len(records), "withMatchingStockContext": sum(
                item["treatment"] == "stock full knowledge" and item["matched"] is True for item in records),
            "sameIncidentRemoved": any(item["treatment"] == "leave original incident out" for item in records)}


def check_locked_observer(directory, document):
    for name, field in (("scope.json", "specSha256"), ("UpgradeProbe.java", "probeSha256")):
        actual = document.get(field)
        if actual and hashlib.sha256((directory / name).read_bytes()).hexdigest() != actual:
            raise ValueError("the observer differs from the version in its receipt: " + directory.name)


def preparations(cid):
    attempts = []
    for epoch in ("complete-modules", "transfer-modules", "declared-modules", "module-retry"):
        file = find(epoch, cid)
        if file is None:
            continue
        result = read(file)
        sides = {side: {"stage": row["stage"], "seconds": row.get("seconds"),
                        "diagnostic": row.get("diagnostic", []), "compiledClasses": row.get("compiledClasses"),
                        "resources": row.get("resources")}
                 for side, row in result.items() if side in ("old", "new")}
        attempts.append({"epoch": epoch, "file": relative(file), "sides": sides})
    return attempts


def complete_old_trials(document):
    trials = document.get("sides", {}).get("old", {}).get("trials", [])
    cases = document.get("cases", [])
    return sum(t.get("qualifiedMethodEntries") == 2 and t.get("observations") == [c["expected"]] * 2
               for t, c in zip(trials, cases))


def additional_observation(case):
    receipt = find("operational", case["id"])
    if receipt is None:
        return None
    directory = HERE / "scenarios" / case["id"] / "operational"
    spec = read(directory / "scope.json")
    checked = read(receipt)
    check_locked_observer(directory, checked)
    if checked.get("status") in ("changed", "preserved") and checked.get("originalCallerSource") != spec["originalCallerSource"]:
        raise ValueError("source mismatch for the additional original caller")
    original = dict(case, entry=spec["entry"].split("(")[0])
    state = checked_finite(original, checked)
    item = {"file": relative(receipt), "entry": spec["entry"], "state": state, "observer": spec["observer"],
            "inputs": len(spec["cases"]), "differences": checked.get("differences"), "reason": checked.get("reason")}
    if state == "changed":
        i = checked["differences"][0]
        item["old"] = checked["sides"]["old"]["trials"][i]["observations"][0]
        item["new"] = checked["sides"]["new"]["trials"][i]["observations"][0]
    return item


def produce():
    cases=read(HERE/"corpus.json")["cases"]
    result={}
    lines=["# Dependency-upgrade reports for maintainers","",
           "Each report names the original consumer, the scope actually checked and the next review action. "
           "A finite decision covers the stated inputs and environment. Costs are measured by stage. "
           "Per-case model-token and dollar attribution is unavailable because all operator work used the same session.",""]
    for case in cases:
        cid=case["id"]
        epochs={}
        for name,sub in (("intake-1","V0"),("multi-release","current"),("overloads","current"),("v1","current"),("v1-complete","current")):
            file=find(name,cid,sub)
            if file: epochs[name]={"file":relative(file),"report":read(file)}
        first=epochs["intake-1"]["report"]
        if first["build"] != "V0" or first["result"] != "open":
            raise ValueError("the first V0 disposition needs separate adjudication for " + cid)
        native=list(epochs.values())[-1]["report"]
        # Later recovery batches preserve the original attempt and replace its grade only with fresh evidence.
        finite=None
        attempts=[]
        for epoch in ("finite-callers","finite-recovery","finite-recovery-2","finite-recovery-3","v1-finite"):
            file=find(epoch,cid)
            if file:
                finite = (file, read(file))
                attempts.append({"epoch": epoch, "file": relative(file), "state": checked_finite(case, finite[1]),
                                 "reason": finite[1].get("reason"), "seconds": finite[1].get("elapsedSeconds")})
        state=checked_finite(case,finite[1]) if finite else "open"
        ci = original_ci("original-ci", case)
        focused = original_ci("focused-ci", case)
        comp = compcheck(case)
        accepted=(case["stratum"]=="reported-change" and state=="changed" or case["stratum"]=="routine" and state=="preserved")
        row={"set":case["set"],"stratum":case["stratum"],"family":case["family"],"familyRelation":case.get("familyRelation"),
             "v0":"open","current":state,"relevant":accepted,"epochs":{k:{"file":v["file"],"seconds":v["report"]["elapsedSeconds"],
             "firstBlocker":v["report"].get("firstBlocker")} for k,v in epochs.items()},"originalCi":ci, "focusedCi": focused,
             "compcheck": comp, "finiteAttempts": attempts}
        supplemental = additional_observation(case)
        if supplemental:
            row["additionalObservation"] = supplemental
        row["originalModuleAttempts"] = preparations(cid)
        if finite and attempts[-1]["epoch"] == "v1-finite":
            check_locked_observer(HERE / "scenarios" / cid, finite[1])
        row["focusedCiRecovery"] = original_ci("focused-recovery", case)
        reason=native.get("firstBlocker","the caller has no qualified outcome")
        if reason in ("original Maven classpath", "original classpath", "original source compilation", "source preparation", "original caller declaration"):
            for side, value in native["sides"].items():
                diagnostic = next((d for d in value.get("diagnostic", []) if d and d != "[ERROR]"), "")
                if diagnostic:
                    reason = f"{side} {reason}: {diagnostic}"
                    break
        if reason == "native checker" and native.get("native", {}).get("diagnostic"):
            reason = native["native"]["diagnostic"][0]
        if native.get("nativeOverloads"):
            reasons=[r.get("firstBlocker","") for r in native["nativeOverloads"]]
            reason=next((x for x in reasons if x and x!="review native outcome and original observer"),reason)
        if finite:
            f,d=finite
            row["finite"]={"file":relative(f),"seconds":d.get("elapsedSeconds"),"inputs":len(d.get("cases",[])),
                           "oracleDisagreements":d.get("oldOracleDisagreements"),"differences":d.get("differences"),
                           "runtimeCompanions": d.get("runtimeCompanions", []), "originalFixtures": d.get("originalFixtures", []),
                           "stoppedAt": d.get("stoppedAt"), "reason": d.get("reason"),
                           "invocationVia": d.get("invocationVia"), "assistance": "reviewed case-specific observer and receiver on original inputs"}
            if state=="open":
                reason=d.get("reason") or "the original expectation disagreed on input IDs "+str(d.get("oldOracleDisagreements"))
                if "prepared.json" in reason and row["originalModuleAttempts"]:
                    last = row["originalModuleAttempts"][-1]
                    for side, attempt in last["sides"].items():
                        if attempt["stage"] != "artifacts ready":
                            diagnostics = [line for line in attempt["diagnostic"] if line.startswith("[ERROR]") and len(line) > 10]
                            reason = side + " " + attempt["stage"] + (". " + diagnostics[0].removeprefix("[ERROR] ") if diagnostics else "")
                            if "bundlor" in reason:
                                reason = side + " Maven build could not load the original Bundlor packaging plugin. Its SpringSource ASM 3.1.0, SLF4J and Maven plugin API JARs were unavailable in the recorded release repositories"
                            break
                row["openStep"] = reason
        if not accepted:
            if state in ("changed", "preserved"):
                row["missCategory"] = "historical difference absent from the admitted observation"
            elif finite and "never entered" in finite[1].get("reason", ""):
                row["missCategory"] = "application stopped before the selected entry"
            elif ("Maven" in reason or "classpath" in reason or "artifact" in reason
                  or "prepared.json" in reason or "source preparation" in reason):
                row["missCategory"] = "original build or dependency unavailable"
            else:
                row["missCategory"] = "native caller has no qualified observer"
        result[cid]=row
        label=case["repository"].split("/")[-1]
        lines.extend([f"## {label} · {cid}", "",
                      f"**Upgrade** {case['dependency']} `{case['versions']['old']}` → `{case['versions']['new']}`. "
                      f"[Original revision pair]({case['repository']}/compare/{case['revisions']['old']}...{case['revisions']['new']})","",
                      f"**Caller-visible behavior** `{case['entry']}`. {case['observer']}",""])
        if state in ("changed", "preserved"):
            d=finite[1]
            if state=="changed":
                n=d["differences"][0]
                summary=f"Changed on {len(d['differences'])} of {len(d['cases'])} inputs. Input {n} produced {short_value(d['sides']['old']['trials'][n]['observations'][0])} before and {short_value(d['sides']['new']['trials'][n]['observations'][0])} after."
                action="Check whether the new caller behavior is acceptable before moving the pin. The recorded input supplies a regression test."
            else:
                summary=f"Preserved the original expected observation on all {len(d['cases'])} admitted inputs."
                action="Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior."
            if not accepted:
                if state == "preserved":
                    summary += " The reported historical change was not reproduced on this observer."
                    action = "Keep the scoped result. The historical change still needs a reproducing input before it can inform this decision."
                else:
                    action = "Inspect the witnessed difference before adopting the dependency. The registered routine expectation did not hold."
            scope=d["domainBasis"]+" Each input ran twice per revision on fresh JVMs."
        else:
            first_step = reason.split("\n")[0][:300].rstrip(".")
            summary = "Open. " + first_step[:1].upper() + first_step[1:] + "."
            scope = "The original pair and caller source were checked. "
            old_inputs = complete_old_trials(finite[1]) if finite else 0
            if old_inputs:
                scope += f"The old runtime independently matched the expected result twice on {old_inputs} input(s). The paired claim remains open."
            elif finite:
                scope += "The finite attempt did not qualify both original executions."
            else:
                scope += "Native checking has yet to establish the specified caller observation."
            action="Use the existing CI evidence for this review. The named open step still needs a qualified caller result."
        if ci:
            scope += " Original module CI " + ", ".join(f"{side} {item['status']} ({item['tests']} tests)"
                                                        for side, item in ci.items()) + "."
        if focused:
            outcomes = []
            for side, item in focused.items():
                if item["named"]:
                    outcome = ", ".join(test["outcome"] + (" (" + test["type"] + ")" if test.get("type") else "")
                                        for test in item["named"])
                else:
                    outcome = item["status"] + ", no matching testcase"
                outcomes.append(side + " " + outcome)
            scope += " The original developer test recorded " + ", ".join(outcomes) + "."
        scope += f" V0 took {first['elapsedSeconds']:.1f} s on this prepared workflow."
        if "v1" in epochs:
            scope += f" The matched V1 native stage took {epochs['v1']['report']['elapsedSeconds']:.1f} s."
        if "v1-complete" in epochs:
            scope += f" Native checking also ran on both complete original modules in {native['elapsedSeconds']:.1f} s."
        if finite and finite[1].get("elapsedSeconds") is not None:
            scope += f" The finite caller stage took {finite[1]['elapsedSeconds']:.1f} s."
        if row["focusedCiRecovery"]:
            diagnostics = []
            for side, item in row["focusedCiRecovery"].items():
                diag = ", ".join(t["outcome"] for t in item["named"]) or item["status"]
                diagnostics.append(side + " " + diag)
            scope += " With restored upstream inputs, the named test recorded " + ", ".join(diagnostics) + "."
        evidence=relative(finite[0]) if finite else list(epochs.values())[-1]["file"]
        if supplemental:
            extra = supplemental["state"].capitalize() + " for " + supplemental["observer"][0].lower() + supplemental["observer"][1:]
            if supplemental["state"] == "changed":
                extra = (supplemental["observer"] + " The old result was " + short_value(supplemental["old"])
                         + " and the new result was " + short_value(supplemental["new"]) + ".")
            elif supplemental["reason"]:
                extra += " " + supplemental["reason"].split("\n")[0][:200] + "."
            action += " " + extra + " [Additional original caller](../../" + supplemental["file"] + ")"
        lines.extend([f"**Result** {summary} [Evidence](../../{evidence})","",f"**Scope** {scope}","",
                      f"**Review action** {action}",""])
    groups={}
    for group in ("main","transfer"):
        selected=[r for r in result.values() if r["set"]==group]
        groups[group]={"attempted":len(selected),"changes":sum(r["relevant"] and r["current"]=="changed" for r in selected),
                       "preservations":sum(r["relevant"] and r["current"]=="preserved" for r in selected),
                       "open":sum(not r["relevant"] for r in selected),"v0Relevant":0,
                       "unresolvedContradictedAssurances":0}
    by_family={relationship:dict(Counter(r["current"] if r["relevant"] else "open" for r in result.values()
                                if r["familyRelation"]==relationship)) for relationship in ("represented","new")}
    document={"protocol":"identified engineering corpus, one gpt-6.2-astra session","groups":groups,"transferByFamily":by_family,
              "scope":"The recovery route admits explicitly reviewed finite observations on original JVMs. Relevance is evaluated against the declared engineering observer. Original CI is measured separately.",
              "pilot":{"decisions":0,"teams":0},"cases":result}
    if (HERE / "v1.json").is_file():
        lock = read(HERE / "v1.json")
        document["evaluatedBuild"] = {"revision": lock["revision"], "checkerSha256": lock["sha256"]["jvmcontract"]}
        for case in cases:
            attempt = find("v1", case["id"], "current")
            if attempt and read(attempt)["checkerSha256"] != lock["sha256"]["jvmcontract"]:
                raise ValueError("V1 result uses a different binary: " + case["id"])
    document["measurement"] = {
        "finiteRoute": "reviewed finite domains and exact repeated original JVM entry",
        "assistance": "one identified engineering session with case-specific receivers, fixtures and independent expected values",
        "humanReviewMinutes": None, "perCaseModelTokens": None, "perCaseCost": None,
        "availability": "native preparation, native checking, JVM observation and original CI are separately timed",
        "exposure": "engineering had access to all 32 cases"
    }
    document["unansweredByReason"] = {group: dict(Counter(
        row["missCategory"] for row in result.values() if row["set"] == group and not row["relevant"]
    )) for group in ("main", "transfer")}
    transfer = [row for row in result.values() if row["set"] == "transfer"]
    document["pairedTransfer"] = {"both": 0, "v0Only": 0, "v1Only": sum(r["relevant"] for r in transfer),
                                  "neither": sum(not r["relevant"] for r in transfer)}
    (DATA/"scorecard.json").write_text(json.dumps(document,indent=2)+"\n")
    REPORTS.write_text("\n".join(lines)+"\n")
    return groups,by_family


if __name__=="__main__":
    print(json.dumps(produce(),indent=2))

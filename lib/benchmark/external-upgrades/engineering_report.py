"""Summarize actual first attempts and qualified recovery evidence for each original upgrade."""

from collections import Counter
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
        for name,sub in (("intake-1","V0"),("multi-release","current"),("overloads","current")):
            file=find(name,cid,sub)
            if file: epochs[name]={"file":relative(file),"report":read(file)}
        first=epochs["intake-1"]["report"]
        native=list(epochs.values())[-1]["report"]
        # Later recovery batches preserve the original attempt and replace its grade only with fresh evidence.
        finite=None
        for epoch in ("finite-callers","finite-recovery","finite-recovery-2"):
            file=find(epoch,cid)
            if file:finite=(file,read(file))
        state=checked_finite(case,finite[1]) if finite else "open"
        ci_paths=list((RUNS/"original-ci").glob("*/"+cid+"/old/summary.json"))
        ci={}
        if ci_paths:
            for side in ("old","new"):
                f=ci_paths[0].parents[1]/side/"summary.json"
                if f.is_file():
                    d=read(f);ci[side]={"file":relative(f),"status":d["disposition"],"tests":d.get("freshReports",{}).get("tests",0),
                                      "namedTestExecuted":d.get("namedTestExecuted"),"named":d.get("freshReports",{}).get("named",[])}
        accepted=(case["stratum"]=="reported-change" and state=="changed" or case["stratum"]=="routine" and state=="preserved")
        row={"set":case["set"],"stratum":case["stratum"],"family":case["family"],"familyRelation":case.get("familyRelation"),
             "v0":"open","current":state,"relevant":accepted,"epochs":{k:{"file":v["file"],"seconds":v["report"]["elapsedSeconds"],
             "firstBlocker":v["report"].get("firstBlocker")} for k,v in epochs.items()},"originalCi":ci}
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
                           "oracleDisagreements":d.get("oldOracleDisagreements"),"differences":d.get("differences")}
            if state=="open":reason=d.get("reason") or "the original expectation disagreed on input IDs "+str(d.get("oldOracleDisagreements"))
        result[cid]=row
        label=case["repository"].split("/")[-1]
        lines.extend([f"## {label} · {cid}", "",
                      f"**Upgrade** {case['dependency']} `{case['versions']['old']}` → `{case['versions']['new']}`. "
                      f"[Original revision pair]({case['repository']}/compare/{case['revisions']['old']}...{case['revisions']['new']})","",
                      f"**Caller-visible behavior** `{case['entry']}`. {case['observer']}",""])
        if accepted:
            d=finite[1]
            if state=="changed":
                n=d["differences"][0]
                summary=f"Changed on {len(d['differences'])} of {len(d['cases'])} inputs. Input {n} produced {short_value(d['sides']['old']['trials'][n]['observations'][0])} before and {short_value(d['sides']['new']['trials'][n]['observations'][0])} after."
                action="Check whether the new caller behavior is acceptable before moving the pin. The recorded input supplies a regression test."
            else:
                summary=f"Preserved the original expected observation on all {len(d['cases'])} admitted inputs."
                action="Retain this caller expectation for the scoped dependency review. Use the ordinary test suite for the remaining application behavior."
            scope=d["domainBasis"]+" Each input ran twice per revision on fresh JVMs."
        else:
            summary="Open. "+reason.split("\n")[0][:300]+"."
            scope="The original pair and caller source were checked. "+("The finite observer lacks a qualified original expectation." if finite else "Native checking has yet to establish the specified caller observation.")
            action="Use the existing CI evidence for this review. The named open step still needs a qualified caller result."
        if ci:
            scope += " Original module CI " + ", ".join(f"{side} {item['status']} ({item['tests']} tests)"
                                                        for side, item in ci.items()) + "."
        scope += f" V0 took {first['elapsedSeconds']:.1f} s on this prepared workflow."
        evidence=relative(finite[0]) if finite else list(epochs.values())[-1]["file"]
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
    (DATA/"scorecard.json").write_text(json.dumps(document,indent=2)+"\n")
    REPORTS.write_text("\n".join(lines)+"\n")
    return groups,by_family


if __name__=="__main__":
    print(json.dumps(produce(),indent=2))

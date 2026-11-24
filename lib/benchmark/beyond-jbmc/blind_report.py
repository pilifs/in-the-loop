"""Score the first unfamiliar-upgrade attempts against the previously committed questions."""
import argparse
from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path

from history import HERE,OUTPUT,digest,encoded
from scores import DECISIONS,qualified,partition,median,costs,replay_state

DOCKET=HERE/"blind/references.json"
# Judgments compare the actual first selections with the preregistered public setup, observation and domain.
# Relevant public declarations are recognized separately from a generated, executable observation.
ADJUDICATION={
 "01":("multi-step mutation and identity","The graph toString and vertex/iterator accessors do not construct the remove/reinsert history or observe insertion order."),
 "02":("grammar and representation inputs","Pattern.quote and Matcher.quoteReplacement do not match either literal through the regex engine."),
 "03":("typed metadata and environment","Container and descriptor operations do not compare a reconstructed Component with an actual runtime annotation."),
 "04":("whole reader or writer and its output","Font/language, CSS removal and character decoding do not transcode the gradient or observe PNG output."),
 "05":("multi-step mutation and identity","ProcessingUnit.consumeQueue and configuration setters do not perform descriptor insertion and removal or inspect processor identity."),
 "06":("grammar and representation inputs","Stack, Base64, matcher-label and file helpers do not map offsets in the multiline DefaultInputBuffer."),
 "07":("typed metadata and environment","The type and processor metadata candidates do not obtain default and explicit annotation member values from javac."),
 "08":("grammar and representation inputs","Font registration and TrueType fields do not parse an AFM glyph record or observe its code and width."),
 "09":("multi-step mutation and identity","The generated reader and byte-access calls do not evaluate a sticky scalar repeatedly or count origin invocations."),
 "10":("whole reader or writer and its output","Cleaner configuration and token helpers do not clean the document or inspect the SVG's parent."),
 "11":("typed metadata and environment","The integer reloadValue candidate and formatting candidates do not construct the BooleanOption or establish the property history."),
 "12":("whole reader or writer and its output","The JSON-writer feature and type-binding candidates do not serialize either enum constant or observe its JSON representation."),
 "13":("multi-step mutation and identity","Trace ID, Span ID, duration and clock methods do not create a TimeSeries and retain its predecessors."),
 "14":("grammar and representation inputs","Recursive conversion and customization candidates do not supply the input and output source files or inspect the transformed Java."),
 "15":("typed metadata and environment","The operator selected Index.listClassNames but could not supply the annotation Class and two-prefix resource ClassLoader."),
 "16":("whole reader or writer and its output","Document and attribute removal and tree-child counts do not write and reparse the escaped element text."),
}

def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix==".gz" else p.read_bytes())

def wilson(k,n):
    if not n:return None
    z=1.95996398454;p=k/n;den=1+z*z/n
    c=(p+z*z/(2*n))/den;w=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [round(max(0.,c-w),4),round(min(1.,c+w),4)]

def real_inputs(run):
    return [a for a in run.get("physical",[]) if len(a)==2 and all(s["namedEntryReached"] for s in a)
            and a[0]["fields"][0]==a[1]["fields"][0]]

def automatic(slot,root,reference):
    f=root/slot/"automatic/report.json.gz";r=read(f)
    if (r["docketSha256"]!=digest(DOCKET) or r["packetSha256"]!=reference["packetSha256"]
            or r["rawSha256"]!=digest(f.parent/"executions.zip")):raise ValueError("unbound first attempt "+slot)
    names={x["owner"]+"#"+x["method"] for x in r["selected"]}
    candidates=[];wrong=[]
    for a in r["runs"]:
        physical=real_inputs(a);c=a["candidate"];v=a.get("verdict")
        diffs=[{"old":s[0]["fields"][:3],"new":s[1]["fields"][:3]} for s in physical if s[0]["fields"][1:3]!=s[1]["fields"][1:3]]
        if v=="verified" and any(x["old"][1]!=x["new"][1] for x in diffs):
            wrong.append(c["id"]+" differs on an original return or exception")
        if v=="violation" and a.get("originalReplayChanged") is False and all(z["namedEntryReached"] for z in a.get("witnessReplay",[])):
            wrong.append(c["id"]+" witness did not reproduce")
        candidates.append({"entry":c["id"],"status":a["status"],"verdict":v,"bothReached":bool(physical),
                           "seedsReached":len(physical),"observedSampleDifferences":diffs,"replayed":a.get("originalReplayChanged"),
                           "cold":a.get("coldCost"),"warm":a.get("warmCost"),"problem":a.get("problem"),
                           "originalEntry":c["owner"]+"#"+c["method"] in reference["reference"]["entries"]})
    named=sorted(names&set(reference["reference"]["entries"]))
    if bool(named)!=(slot=="15") or any(c["originalEntry"] and c["bothReached"] for c in candidates):
        raise ValueError("first selections no longer match the reviewed observation on "+slot)
    cls,reason=ADJUDICATION[slot]
    return {"reportSha256":digest(f),"receipt":slot+"/automatic/report.json.gz","selected":len(r["selected"]),
            "anyPublicReach":any(c["bothReached"] for c in candidates),"topPublicReach":bool(candidates and candidates[0]["bothReached"]),
            "namedEntriesSelected":named,"primaryObservationDiscovered":False,"referenceReached":False,"primaryDecided":False,
            "reason":reason,"missingCallerCapability":cls,"candidates":candidates,"wrongDecisions":wrong,
            "warmAgreement":r.get("warmAgreement",[]),"coldPortfolioAndWarmSeconds":r.get("seconds")}

def matched(slot,root,reference):
    f=root/slot/"matched/report.json";r=read(f)
    if r["docketSha256"]!=digest(DOCKET) or r["packetSha256"]!=reference["packetSha256"]:raise ValueError("reference binding differs")
    data={"status":r["status"],"receipt":slot+"/matched/report.json","reportSha256":digest(f),"primary":{},"control":{}}
    p=f.parent/"comparison/results.json.gz"
    if not p.is_file():
        data["firstProblem"]=r.get("diagnostic") or r.get("failure") or r.get("problem")
        for metric in ("primary","control"):data[metric]={e:"two-copy preparation incomplete" for e in ("native","integrated","stock")}
        return data
    ds=[qualified(row) for row in read(p)["rows"]];indexed={d["method"]:d for d in ds}
    if set(indexed)!={"primary","control","inverse"}:raise ValueError("incomplete matched reference rows")
    for method in ("primary","control"):
        for e in ("native","integrated","stock"):
            status=indexed[method][e]["disposition"]
            if e=="stock" and status=="proved" and indexed["inverse"][e]["disposition"]!="refuted":
                status="inverse control not qualified"
            if e!="stock" and status=="proved" and indexed["inverse"][e]["disposition"]=="incorrect proof":
                status="contradicted inverse control"
            data[method][e]=status
    data["rows"]=ds
    data["firstProblem"]=indexed["primary"]["native"]["firstProblem"] or None
    return data

def family(problem,status):
    s=problem or ""
    if status!="measured":return "old XML resources or providers changed under relocation"
    if not s:return "no reported instruction"
    if "time limit" in s.lower() or "timed out" in s.lower():return "checker time limit"
    if "symbolic" in s.lower() and "string" in s.lower():return "symbolic String operation"
    if "strict): " in s:s=s.split("strict): ",1)[1]
    return (s.split(" (")[0].split("@jdk")[0].split("\n")[0])[:140]

def build(root,out):
    refs=read(DOCKET)["pairs"]
    if len(refs)!=16:raise ValueError("wrong denominator")
    rows=[];classes=defaultdict(list);blockers=defaultdict(list)
    for ref in refs:
        slot=ref["slot"];a=automatic(slot,root,ref);m=matched(slot,root,ref)
        n=m["primary"]["native"] in DECISIONS;j=any(m["primary"][e] in DECISIONS for e in ("integrated","stock"))
        rows.append({"slot":slot,"artifact":ref["artifact"],"stratum":ref["stratum"],"question":ref["reference"]["question"],
                     "scope":ref["reference"]["domain"],"automatic":a,"matched":m,"correctPartition":partition(n,j)})
        classes[a["missingCallerCapability"]].append(slot)
        if not n:blockers[family(m.get("firstProblem"),m["status"])].append(slot)
    auto=[x["automatic"] for x in rows];cand=[c for a in auto for c in a["candidates"]];costed=[c for c in cand if c["cold"] and c["warm"]]
    pairing=Counter(x["correctPartition"] for x in rows)
    wins=pairing["native-only"];loss=pairing["comparator-only"];dis=won=0
    for a in auto:dis+=a["primaryObservationDiscovered"];won+=a["primaryDecided"]
    n=len(rows);d=wins+loss
    exact=min(1.,2*sum(math.comb(d,k) for k in range(min(wins,loss)+1))/2**d) if d else 1.
    metrics={"projects":n,"positiveReferenceJvms":sum(r["physicalStatus"]=="original JVM control passed" for r in refs),
        "automaticTopReached":sum(a["topPublicReach"] for a in auto),"automaticAnyReached":sum(a["anyPublicReach"] for a in auto),
        "namedDeclarationSelected":sum(bool(a["namedEntriesSelected"]) for a in auto),"observationDiscovered":dis,"automaticPrimaryDecided":won,
        "automaticDecisionWilson95":wilson(won,n),"matchedCorrect":dict(pairing),"nativeMatchedWilson95":wilson(wins+pairing["both"],n),
        "comparatorMatchedWilson95":wilson(loss+pairing["both"],n),"pairedExactTwoSidedP":exact,
        "candidateAttempts":len(cand),"attemptDispositions":dict(Counter(c["verdict"] or
            ("timeout" if c["cold"] and c["cold"]["timedOut"] else "missing checker verdict" if c["status"]=="measured" else c["status"]) for c in cand)),
        "knownIncorrectAutomatic":sum(len(a["wrongDecisions"]) for a in auto),"bothReachedCandidateAttempts":sum(c["bothReached"] for c in cand),
        "warmSameVerdicts":sum(w["sameVerdict"] for a in auto for w in a["warmAgreement"]),
        "warmComparisons":sum(len(a["warmAgreement"]) for a in auto),"costedAttempts":len(costed),
        "automaticColdWarm":{k:[median([c[side][k] for c in costed]) for side in ("cold","warm")] for k in ("wallSeconds","cpuSeconds","peakMiB")},
        "automaticCensored":sum(c["cold"]["timedOut"] for c in costed),"samePrimaryMatchedCosts":costs([r["matched"]["rows"][0] for r in rows if r["matched"].get("rows")]),
        "primaryDispositions":{e:dict(Counter(r["matched"]["primary"][e] for r in rows)) for e in ("native","integrated","stock")},
        "controlDispositions":{e:dict(Counter(r["matched"]["control"][e] for r in rows)) for e in ("native","integrated","stock")},
        "callerCapabilitiesByProject":dict(classes),"nativePrimaryBlockersByProject":dict(sorted(blockers.items(),key=lambda x:-len(x[1])))}
    out.mkdir(parents=True,exist_ok=True)
    (out/"matrix.json.gz").write_bytes(gzip.compress(encoded({"docketSha256":digest(DOCKET),"metrics":metrics,"projects":rows}),mtime=0))
    def percent(x):return f"{100*x:.1f}%"
    md=["# Frozen unfamiliar upgrades","",f"All 16 reference callers reached both original releases. The automatic workflow discovered {dis}/16 original observations and decided {won}/16. It selected {metrics['namedDeclarationSelected']} registered primary declaration and reached some selected public path on both releases in {metrics['automaticAnyReached']}/16 projects. The matched native/comparator partition was {pairing['both']} both, {wins} native only, {loss} comparator only and {pairing['neither']} neither. [Complete decisions, witnesses, costs and first blockers](matrix.json.gz)","",
        "| Slot | Distribution package | Both-JVM reach of any automatic candidate | Matched primary, native | Integrated | Stock |","|---|---|---|---|---|---|"]
    for row in rows:
        a=row["automatic"];m=row["matched"]["primary"]
        md.append("| "+" | ".join([row["slot"],row["artifact"],"yes" if a["anyPublicReach"] else "no",*[m[e] for e in ("native","integrated","stock")]])+" |")
    md+=["","## Scope and uncertainty","",f"Each pair is from a distinct selected project. The descriptive 95% Wilson interval for the automatic primary rate is {percent(metrics['automaticDecisionWilson95'][0])}–{percent(metrics['automaticDecisionWilson95'][1])}. Native and comparator intervals for matched decisions are {percent(metrics['nativeMatchedWilson95'][0])}–{percent(metrics['nativeMatchedWilson95'][1])} and {percent(metrics['comparatorMatchedWilson95'][0])}–{percent(metrics['comparatorMatchedWilson95'][1])}. The exact two-sided paired sign test on discordant projects gives p = {exact:.3f}. The stratified Ubuntu Universe draw and its source/packaging qualifications define the population.","","## Automatic cost","",
        f"The operator tried {len(cand)} candidates. {len(costed)} had a measured cold/warm checker pair, with {metrics['warmSameVerdicts']}/{metrics['warmComparisons']} identical literal verdicts. The other attempts stopped before both runs. Across measured pairs the median cold/warm wall time was {metrics['automaticColdWarm']['wallSeconds'][0]} / {metrics['automaticColdWarm']['wallSeconds'][1]} seconds, CPU time was {metrics['automaticColdWarm']['cpuSeconds'][0]} / {metrics['automaticColdWarm']['cpuSeconds'][1]} seconds, and peak RSS was {metrics['automaticColdWarm']['peakMiB'][0]} / {metrics['automaticColdWarm']['peakMiB'][1]} MiB. Physical JVMs, impact selection, class preparation and witness replay incur additional costs recorded per portfolio.","",
        "## Next investments by independent project","","The observed misses were upstream of the checker in every automatic primary. The following groupings are a review of the public setup and observation each first selection needed. The underlying table retains the actual selections and refusals for each project.","","| Capability needed for the original observation | Independent projects | Slots |","|---|---:|---|"]
    for c,slots in sorted(classes.items(),key=lambda t:(-len(t[1]),t[0])):md.append(f"| {c} | {len(slots)} | {', '.join(slots)} |")
    md+=["","| Repeated first blocker on the supplied caller | Independent projects | Slots |","|---|---:|---|"]
    for blocker,slots in metrics["nativePrimaryBlockersByProject"].items():
        if len(slots)>=2:md.append(f"| {blocker} | {len(slots)} | {', '.join(slots)} |")
    md+=["","The first pass also reported one incorrect native counterexample on Sisu Plexus. The previous class's diagnostic string contained the checker's synthetic `before.` package. The original JVMs returned identical strings for both Boolean values. No matched primary was solved by both engines, so there is no paired median on jointly solved primaries. All individual times and capped runs remain in the matrix. The suggested 8/16 original automatic decisions threshold was missed."]
    (out/"RESULTS.md").write_text("\n".join(md)+"\n")
    print(json.dumps({k:metrics[k] for k in ("automaticAnyReached","automaticPrimaryDecided","matchedCorrect","knownIncorrectAutomatic","automaticColdWarm")}))
if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--inputs",type=Path,default=OUTPUT/"blind");ap.add_argument("--output",type=Path,default=OUTPUT/"blind-comparison");a=ap.parse_args();build(a.inputs,a.output)

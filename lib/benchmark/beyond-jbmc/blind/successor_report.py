"""Audit and summarize the two frozen workflows on the second release panel."""
import argparse
from collections import Counter
import json
from pathlib import Path
import zipfile

from successor import OUT, REFS, SLOTS, compressed, digest, draw, read, save
from blind_report import real_inputs
from history import ROOT
from scaffold_audit import collect, require, source_digest
from scores import qualified

ENGINES = ("native","integrated","stock")


def auto(slot, docket, registered, study=OUT):
    folder=study/"automatic"/slot
    m=read(folder/"measurement.json")
    d=compressed(folder/"report.json.gz")
    require(d["rawSha256"]==digest(folder/"executions.zip") and d["docketSha256"]==m["scaffoldSha256"]==digest(docket)
            and m["packetSha256"]==d["packetSha256"] and m["checkerSha256"]==d["toolSha256"],"different automatic first pass")
    archive=folder/"resource-discovery.zip"
    require(digest(archive)==m["resourceArchiveSha256"],"resource selector output changed")
    with zipfile.ZipFile(archive) as z:
        discovery=json.loads(z.read("discovery.json"))
    require(discovery["inputPacketSha256"]==m["packetSha256"] and discovery["candidates"]==m["resourceCandidates"],
            "inconsistent resource selector")
    rows=[]
    for r in d["runs"]:
        c=r["candidate"]
        physical=real_inputs(r)
        wrong = r.get("verdict")=="verified" and any(a[0]["fields"][1:3]!=a[1]["fields"][1:3] for a in physical)
        if r.get("verdict")=="violation" and r.get("originalReplayChanged") is False:
            wrong |= bool(r.get("witnessReplay")) and all(v["namedEntryReached"] for v in r["witnessReplay"])
        rows.append({"entry":c["id"],"candidate":c["owner"]+"#"+c["method"],"status":r["status"],"verdict":r.get("verdict"),
                     "callerSha256":r.get("callerSha256"),"bothOriginals":len(physical),"firstProblem":r.get("problem"),
                     "changedSamples":sum(a[0]["fields"][1:3]!=a[1]["fields"][1:3] for a in physical),
                     "incorrectNativeDecision":wrong,"cold":r.get("coldCost"),"warm":r.get("warmCost")})
    require([r["entry"] for r in rows]==[x["id"] for x in d["selected"]],"selected candidate missing from report")
    review=read(study/"automatic-review.json")[slot]
    require(review["reportSha256"]==digest(folder/"report.json.gz"),"new first pass needs adjudication")
    require(not discovery["candidates"],"a new resource claim needs adjudication")
    names=set(registered["entries"])
    warm=d["warmAgreement"]
    require(len(warm)==sum(r["status"]=="measured" for r in rows),"missing warm attempt")
    return {"rows":rows,"resourceCandidates":len(discovery["candidates"]),"relatedDirectNames":[r["entry"] for r in rows if r["candidate"] in names],
            "anyOriginalReach":any(r["bothOriginals"] for r in rows),"firstCandidateReach":bool(rows and rows[0]["bothOriginals"]),
            "primaryDecided":review["primaryDecision"],"scaffoldStop":review["basis"],"capability":review["category"],
            "warmAgreed":sum(w["sameVerdict"] for w in warm),"warmComparisons":len(warm)}


def matched(slot, docket, study=OUT):
    folder=study/"matched"/slot
    m=read(folder/"measurement.json")
    require(m["scaffoldSha256"]==digest(docket),"measurement used a different scaffold")
    original=compressed(docket)
    caller=original.get("callerSha256") or original["callerClasses"]["ReferenceAPI.class"]
    report={}
    for side in ("old","new"):
        r=compressed(folder/side/"results.json.gz")
        require(digest(folder/side/"executions.zip")==r["executionsSha256"] and
                r["primaryApiSha256"]==caller and
                r["checkerSha256"]==m["checkerSha256"],"different binary or executions")
        rows={row["method"]:qualified(row) for row in r["rows"]}
        require(set(rows)=={"primary","control","inverse"},"missing comparator control")
        report[side]=rows
    results={}
    for question in ("primary","control"):
        results[question]={}
        for engine in ENGINES:
            sides=[]
            for side in ("old","new"):
                v=report[side][question][engine]["disposition"]
                inverse=report[side]["inverse"][engine]["disposition"]
                if v=="proved" and ((engine=="stock" and inverse!="refuted") or inverse=="incorrect proof"):
                    v="inverse control not qualified"
                sides.append(v)
            results[question][engine]="refuted" if "refuted" in sides else "proved" if sides==["proved","proved"] else "open"
    return {"originalConjuncts":report,"pair":results}


def build():
    ledger=read(OUT/"receipts.json")
    require({j["id"] for j in ledger}==set(read(OUT/"jobs.json")),"job and receipt populations differ")
    for j in ledger:
        for row in j.get("outputs",[]):
            require(digest(ROOT/row["path"])==row["sha256"],"collected report bytes changed")
    passed={j["id"]:j for j in ledger if j["status"]=="passed"}
    results=[]
    for slot,pair in zip(SLOTS,draw(),strict=True):
        docket=OUT/"scaffolds"/(slot+".json.gz")
        physical=compressed(docket)
        spec=read(REFS/slot/"reference.json")
        require(digest(REFS/slot/"reference.json")==physical["question"] and
                digest(REFS/slot/"ReferenceAPI.java")==physical["callerSource"],"registration changed")
        row={"slot":slot,"artifact":pair["artifact"],"scaffoldStop":physical["firstScaffoldStop"],
             "registeredDomain":spec["domain"],"samples":physical["expectedRows"]}
        for lane in ("automatic","matched"):
            file=OUT/lane/slot/"measurement.json"
            if not file.is_file():continue
            m=read(file)
            require(m["job"] in passed and source_digest(passed[m["job"]]["source"],docket)==m["scaffoldSha256"] and
                    m["checkerSha256"]==read(OUT/"selection.json")["checkerSha256"],"measurement has no source-bound receipt")
            row[lane]=auto(slot,docket,spec) if lane=="automatic" else matched(slot,docket)
        alt = OUT / "alternative" / (slot + ".json.gz")
        extra = OUT / "alternative-measurements"
        if alt.is_file():
            row["alternative"] = {}
            for lane in ("automatic", "matched"):
                marker = extra / lane / slot / "measurement.json"
                if not marker.is_file(): continue
                m = read(marker)
                require(m["job"] in passed and source_digest(passed[m["job"]]["source"],alt)==m["scaffoldSha256"]
                        and m["checkerSha256"]==read(OUT/"selection.json")["checkerSha256"],"unbound alternative result")
                row["alternative"][lane] = auto(slot,alt,spec,extra) if lane=="automatic" else matched(slot,alt,extra)
        results.append(row)
    save(OUT/"matrix.json.gz",results)
    render(results, ledger)
    return results


def render(rows, ledger):
    automatic=[r["automatic"] for r in rows if "automatic" in r]
    measured=[r for r in rows if "matched" in r]
    solved=sum(r["primaryDecided"] for r in automatic)
    candidates=[c for a in automatic for c in a["rows"]]
    full={e:sum(r["matched"]["pair"]["primary"][e] in ("proved","refuted") for r in measured) for e in ENGINES}
    populations=Counter()
    for r in measured:
        p=r["matched"]["pair"]["primary"]
        native=p["native"] in ("proved","refuted")
        jbmc=any(p[e] in ("proved","refuted") for e in ENGINES[1:])
        populations["both" if native and jbmc else "native only" if native else "JBMC only" if jbmc else "neither"]+=1
    lines=["# Frozen successor measurements","",
           f"The artifact-only operators decided {solved} of the {len(automatic)} primary questions run. "
           f"{len(rows)-len(automatic)} other selected projects have no first pass. With the 16-project denominator, "
           f"the eventual automatic total lies between {solved} and {solved+len(rows)-len(automatic)}.",
           "",f"The impact selector tried {len(candidates)} callers and reached a selected public operation on both originals in "
           f"{sum(a['anyOriginalReach'] for a in automatic)} projects. The resource selector nominated "
           f"{sum(a['resourceCandidates'] for a in automatic)} workflows. Cold and warm verdicts agreed on "
           f"{sum(a['warmAgreed'] for a in automatic)}/{sum(a['warmComparisons'] for a in automatic)} measured callers. "
           f"The original JVM checks contradicted {sum(c['incorrectNativeDecision'] for c in candidates)} of those native decisions.",
           "",f"On {len(measured)} supplied primary questions, strict native decided {full['native']}, integrated JBMC "
           f"{full['integrated']} and stock JBMC {full['stock']}. Against the union of the qualified JBMC profiles the "
           f"partition is {populations['both']} both, {populations['native only']} native only, {populations['JBMC only']} JBMC only "
           f"and {populations['neither']} neither. Each proof of the pair requires proofs on both original deployments. A "
           "refutation requires a physically reproduced violation of at least one conjunct. The inverse and stock reach controls are included in qualification.",
           "","| Slot | Project | Frozen automatic attempt | Supplied primary, native / integrated / stock |",
           "|---|---|---|---|"]
    for r in rows:
        auto=r.get("automatic")
        reason=auto["scaffoldStop"] if auto else r["scaffoldStop"] or "Awaiting measurement."
        values=r.get("matched",{}).get("pair",{}).get("primary",{})
        states=" / ".join(values[e] for e in ENGINES) if values else "Awaiting measurement" if not r["scaffoldStop"] else "Scaffolding incomplete"
        lines.append(f'| {r["slot"]} | {r["artifact"]} | {reason} | {states} |')
    extra=[r for r in rows if r.get("alternative")]
    if extra:
        lines+=["","### Separately pinned Maven providers","",
                "These original application JARs use the explicitly registered alternative dependencies. Each case has its own first-attempt and comparator receipts.",
                "","| Slot | Frozen automatic workflow on the alternative | Supplied primary, native / integrated / stock |",
                "|---|---|---|"]
        for r in extra:
            a=r["alternative"].get("automatic")
            m=r["alternative"].get("matched")
            status=a["scaffoldStop"] if a else "Awaiting measurement"
            scores=" / ".join(m["pair"]["primary"][e] for e in ENGINES) if m else "Awaiting measurement"
            lines.append(f'| {r["slot"]} | {status} | {scores} |')
    mistakes=Counter()
    contradicted_stock_successes=0
    for r in measured:
        for side in r["matched"]["originalConjuncts"].values():
            for q in side.values():
                contradicted_stock_successes+=int(bool(q["stock"].get("targetSuccessContradictedOnOriginalCaller")))
                for e in ENGINES:
                    if q[e]["disposition"].startswith("incorrect"):
                        mistakes[e]+=1
    lines+=["",f"Across primary, control and inverse rows on the measured distribution launches, adjudication recorded "
            f"{mistakes['native']} incorrect native decisions, {mistakes['integrated']} incorrect integrated decisions and "
            f"{mistakes['stock']} incorrect stock decisions. Stock reported literal target success on {contradicted_stock_successes} "
            "statements contradicted on the original caller, including runs already ineligible on a reach or unwinding check. All dispositions are recorded per row."]
    counts=Counter(a["capability"] for a in automatic if not a["primaryDecided"])
    lines+=["","| First missing capability | Independent projects |","|---|---:|"]
    for key,num in counts.most_common():lines.append(f"| {key} | {num} |")
    costs=Counter()
    for j in ledger:
        for k in ("cpuSeconds","wallSeconds"):
            costs[k]+=(j.get("usage") or {}).get(k) or 0
    states=Counter(j["status"] for j in ledger)
    lines+=["",f"Job receipts currently record {states['passed']} passed and {states['failed']} failed, using "
            f"{costs['cpuSeconds']:,.1f} CPU-seconds and {costs['wallSeconds']:,.1f} summed wall-seconds. "
            "The first directory-creation failures were retained with their replacements. "
            "[Job receipts](receipts.json) · [Per-candidate costs, comparator outcomes, JVM replays and first solver blockers](matrix.json.gz)"]
    (OUT/"SCORES.md").write_text("\n".join(lines)+"\n")


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--collector",type=Path)
    opt=cli.parse_args()
    if opt.collector:collect(opt.collector,OUT,"receipts.json")
    rows=build()
    print("completed automatic/matched",sum("automatic" in r for r in rows),sum("matched" in r for r in rows))
    print("native / integrated / stock decided primaries",
          [sum(r.get("matched",{}).get("pair",{}).get("primary",{}).get(e) in ("proved","refuted") for r in rows) for e in ENGINES])

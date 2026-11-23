"""Recount the unchanged Java statements from the collector's hash-bound outputs."""
import argparse
from collections import Counter
from dataclasses import asdict
from functools import lru_cache
import gzip
import hashlib
import json
import os
from pathlib import Path
import tarfile

from campaign import CLAIMS, GRAPHS, ROOT, wire
from historical import FROZEN_SHA, GROUPS, digest, freeze, selected

BASE = ROOT/"verification/java-semantics-gap"
PAGE = ROOT/"llm-dlc/loops/jbmc-java-semantics-gap-results.md"


def require(ok, why):
    if not ok: raise ValueError(why)


def read(path):
    return json.loads(path.read_bytes())


@lru_cache(maxsize=None)
def job_outputs(job):
    day = job[:8]
    p = ROOT/"verification/results"/day[:4]/day[4:6]/day[6:]/job/"result.json"
    r = read(p)
    require(r["id"] == job and r["status"] == "passed",f"unpassed job {job}")
    return r["sourceCommit"], {o["path"]:o for o in r["outputs"]}


def collected(path, job, source=None):
    commit, outputs = job_outputs(job)
    name = path.relative_to(ROOT).as_posix()
    item = outputs.get(name)
    require((source is None or commit == source) and item and path.stat().st_size == item["bytes"]
            and digest(path) == item["sha256"], f"collector does not bind {name} to {job}")


def location(path):
    return path.relative_to(ROOT).as_posix()


def short_problem(text):
    if not text: return ""
    if "(--gaps strict): " in text:
        text = text.split("(--gaps strict): ",1)[1]
        text = text.split(". It has no approximation",1)[0].split(". With --gaps",1)[0]
    return text.splitlines()[0]


def state(verdict, expected, disposition, replay):
    if verdict == "verified" and disposition == "correct" and expected == verdict: return "proved"
    if verdict == "violation" and disposition == "correct" and expected == verdict and replay == "refuted":
        return "refuted"
    if verdict == "verified" and expected == "violation": return "JVM-contradicted proof"
    if verdict == "violation" and replay == "held": return "JVM-contradicted violation"
    return "open"


def historic(phase):
    rows = freeze()
    results = {}
    for group in GROUPS:
        p = BASE/phase/(group+".json")
        d = read(p)
        collected(p,d["environment"]["job"],d["environment"]["commit"])
        ids = selected(rows,group)
        require(d["frozenResultSha256"] == FROZEN_SHA and d["historical"] == {i:rows[i] for i in ids}
                and [c["id"] for c in d["cases"]] == ids, f"changed historical selection {group}")
        settings = d["settings"]
        require((settings["engines"],settings["modes"],settings["jbmcStaging"],settings["timeout"],
                 settings["unwind"],settings["maxArrayLength"]) == (["native","jbmc"],["strict"],["staged"],120,16,8),
                "unmatched historical engine settings")
        seen = set()
        for r in d["runs"]:
            cid,engine = r["case"],r["engine"]
            require(cid in ids and engine in ("native","jbmc") and (cid,engine) not in seen and r["mode"]=="strict"
                    and r.get("staging")==("staged" if engine=="jbmc" else None), "duplicate or mismatched benchmark row")
            seen.add((cid,engine))
            physical = r.get("witnessOnTheJvm","")
            replay = "refuted" if "refuted" in physical.split() else physical
            require(not r["assumed"] and not r["contracts"], f"{cid} assumes a gap")
            expected = rows[cid]["expected"]
            results.setdefault(cid,{"historical":rows[cid]["historical"],"expected":expected,"source":d["environment"]["commit"],
                          "evidence":location(p),"inputClasses":settings["classesSha256"],"oracles":settings["oraclesSha256"]})[engine] = {
                "status":state(r["verdict"],expected,r["class"],replay),"verdict":r["verdict"],"seconds":r["seconds"],
                "firstUnproved":short_problem(r.get("problem","")),"replay":physical,"witness":r.get("witness")}
        require(len(seen)==2*len(ids),"missing historical engine outcome")
    return results


def subject_rows(phase):
    result = {}
    for key,subject in CLAIMS.items():
        p = BASE/phase/key/"measurement.json"
        d = read(p)
        collected(p,d["job"],d["source"])
        raw = p.parent/"raw.tar.gz"
        collected(raw,d["job"],d["source"])
        require(d["scope"] == json.loads(json.dumps(asdict(subject))) and d["subject"]==key and d["phase"]==phase
                and d["classpath"]==["adapter",*GRAPHS[subject.graph]] and digest(raw)==d["rawSha256"],
                f"{key}: mismatched scope or raw responses")
        require(d["originalJvm"]["checks"] == sum(len(c.holds)+len(c.fails) for c in subject.claims)
                + (key=="monitors"), f"{key}: missing physical controls")
        folder, = (ROOT/"examples").glob(f"{subject.example}-*")
        src, = (folder/"adapter").rglob(subject.owner+".java")
        require(digest(src)==d["adapterSha256"],"original adapter changed")
        target=read(folder/"target.json")
        specs={t["target"]:t for t in target["tasks"] if t.get("revision")==key and t["kind"]=="prove"}
        claims={c.method:c for c in subject.claims}
        with tarfile.open(raw) as arc:
            seen=set()
            for r in d["runs"]:
                m,e=r["method"],r["engine"]
                require(m in claims and e in ("native","jbmc") and (m,e) not in seen,"unexpected or duplicate result")
                seen.add((m,e))
                cid=key+"/"+m
                t=specs[subject.owner+"#"+m]
                require(d["claimsSha256"][m]==digest(folder/t["claim"]),cid+" changed property")
                expected={"refuted":"violation","established":"verified"}[t["expected"]]
                require(r["expected"]==expected,cid+" changed expectation")
                decoder=wire.decode(arc.extractfile(f"raw/{m}-{e}/stdout.json").read().decode(errors="replace"),"prove")
                if decoder.ok and len(decoder.outcomes)==1:
                    row,=decoder.outcomes
                    require(row["target"]==subject.owner+"#"+m and row["assert"]=="result" and (row.get("assume") or "")==claims[m].guard,
                            cid+" has a different raw statement")
                    require(row["verdict"]==r["verdict"] and not wire.exit_problem([row["verdict"]],r["exit"]),cid+" has a contradictory exit")
                else:
                    require(r["disposition"] in ("frontend refusal","timeout"),cid+" has no raw outcome")
                replay = r.get("jvmReplay",{}).get("outcome")
                outcome = state(r["verdict"],expected,r["disposition"],replay)
                if outcome in ("proved","refuted"):
                    stated=row["stated"]
                    require(stated==r["stated"] and stated["gap_mode"]=="strict" and row["search"]["engine"]==e
                            and not stated["checker"].get("fallback")
                            and row["search"]["max_array_length"]==subject.bound and row["search"]["unwind"]==subject.unwind,
                            cid+" has a different checked domain")
                    if outcome=="proved":
                        require(stated["bounds"]["complete"] and stated.get("vacuity",{}).get("status")=="non-vacuous",
                                cid+" lacks a complete nonvacuous proof")
                    else:
                        require(row["counterexample"]["inputs"]==r["jvmReplay"]["inputs"],cid+" replayed a different witness")
                result.setdefault(cid,{"expected":expected,"family":subject.example,"evidence":location(p),
                    "source":d["source"],"graph":key,"method":m,"checks":d["originalJvm"]["checks"],
                    "signature":claims[m].parameters,"guard":claims[m].guard,"bound":subject.bound,
                    "classes":d["classes"],"jvm":d["jvmSha256"],"claim":location(folder/t["claim"]),
                    "statement":read(folder/t["claim"])["statement"]})[e] = {
                    "status":outcome,"verdict":r["verdict"],"seconds":r["seconds"],
                    "firstUnproved":short_problem(r["firstUnproved"]),"jvmReplay":r.get("jvmReplay")}
            require(len(seen)==2*len(claims),key+" missing engine rows")
    return result


def standalone_rows():
    result={}
    directories=[BASE/"standalone",BASE/"standalone-qualified",BASE/"standalone-recheck"]
    for directory in directories:
        for p in sorted(directory.glob("*/*/measurement.json")):
            d=read(p)
            collected(p,d["job"])
            for r in d["runs"]:
                for method in ("target","reached"):
                    run=r[method]
                    raw=p.parent/run["raw"]
                    collected(raw,d["job"])
                    require(run["sha256"]==digest(raw),"different standalone property bytes")
                    if run.get("target"):
                        props=[q for msg in json.loads(gzip.decompress(raw.read_bytes())) for q in msg.get("result",[])]
                        actual=[q for q in props if q["property"]==run["target"]["property"]]
                        require(len(actual)==1 and actual[0]["status"]==run["status"] and len(props)==run["totalProperties"],
                                "mismatched standalone assertion ID or status")
                actual=r["target"]
                result.setdefault(d["key"]+"/"+r["method"],{})[p.parent.name]={
                    "target":actual["status"],"id":(actual.get("target") or {}).get("property"),
                    "reach":r["reached"]["status"],"otherFailures":len(actual.get("otherFailures",[])),
                    "warnings":actual.get("warnings",[]),"jvm":actual.get("jvmReplay"),"evidence":location(p)}
    return result


def compare(phase):
    old,new=historic("opening"),historic(phase)
    before,after=subject_rows("opening"),subject_rows(phase)
    for a,b in [(old,new),(before,after)]:
        require(a.keys()==b.keys(),"changed denominator")
        for key in a:
            for field in ("classes","jvm","inputClasses","oracles","expected","claim"):
                require(a[key].get(field)==b[key].get(field),f"{key}: before and after differ in {field}")
    return {"historical":{k:{"opening":old[k],"final":new[k]} for k in old},
            "subjects":{k:{"opening":before[k],"final":after[k]} for k in before},"standalone":standalone_rows()}


def link(path,text):
    return f"[{text}]({os.path.relpath(ROOT/path,PAGE.parent)})"


def cell(s):
    return str(s).replace("\n"," ").replace("|","\\|")


def engine(r):
    return f"{r['status']} ({r['seconds']:.2f} s)"


DECIDED={"proved","refuted"}


def totals(rows,cohort=None):
    names = [k for k,v in rows.items() if not cohort or v["final"].get("historical")==cohort]
    return {stage:dict(Counter(rows[k][stage]["native"]["status"] for k in names)) for stage in ("opening","final")}


def render(card):
    historical,sub,stock=card["historical"],card["subjects"],card["standalone"]
    leads=totals(historical,"jbmc-only");controls=totals(historical,"native-only");scores=totals(sub)
    def count(group,stage):return sum(group[stage].get(k,0) for k in DECIDED)
    gains=[v for v in sub.values() if v["opening"]["native"]["status"] not in DECIDED and v["final"]["native"]["status"] in DECIDED]
    lost=[k for part in (historical,sub) for k,v in part.items() if v["opening"]["native"]["status"] in DECIDED and v["final"]["native"]["status"] not in DECIDED]
    wrong=[k for part in (historical,sub) for k,v in part.items() if v["final"]["native"]["status"].startswith("JVM-contradicted")]
    lines=["# Java semantics on the native checker and JBMC","",
           f"The opening checker decided **{count(leads,'opening')}/13** historical JBMC-only claims and the final checker decided **{count(leads,'final')}/13**. The {count(controls,'opening')} native-only regression controls held at **{count(controls,'final')}/24**. The historical denominator remains 187, with 133 shared successes, 24 native-only, 13 staged-JBMC-only and 17 decided by neither engine.","",
           f"On the **60** independently registered campaign statements, direct native decisions moved from **{count(scores,'opening')}/60** to **{count(scores,'final')}/60**. The final total includes **{scores['final'].get('proved',0)} proofs** and **{scores['final'].get('refuted',0)} original-JVM-replayed refutations**. There were {len(gains)} newly decided statements across {len({v['final']['family'] for v in gains})} numbered examples, {len(lost)} native regressions and {len(wrong)} remaining JVM-contradicted native verdicts.","",
           "Historical runs used the original benchmark’s JDK 25 harness, 120-second deadline, unwind 16, array bound 8 and staged integrated JBMC. New public callers used Temurin 21.0.13, explicit strict engines and the same 120-second deadline. Every linked measurement records the original classpath order, binary and model identity, input bounds and costs. The additional registered positive list-search control sits outside the 13.","",
           "## Historical differential","",
           "| Frozen claim | Historical cohort | Expected | Opening native | Final native | Integrated JBMC, opening → final | Original JVM witness or first open native step |",
           "|---|---|---|---|---|---|---|"]
    for key,pair in historical.items():
        a,b=pair["opening"],pair["final"];n=b["native"]
        detail=(f"{n['witness']} → {n['replay']}" if n["replay"] else n["firstUnproved"] or "Registered JVM controls")
        lines.append("| "+" | ".join(map(cell,[key,b["historical"],b["expected"],link(a["evidence"],engine(a["native"])),link(b["evidence"],engine(n)),
            engine(a["jbmc"])+" → "+engine(b["jbmc"]),detail]))+" |")
    lines+=["","## Original callers","",
            "A refutation earns credit when the actual checker input fails on a fresh original JVM. A named refusal, an incomplete bound or a witness that holds on replay stays open. Standalone columns identify the target status, reachability assertion status and any accompanying failing properties. A reachable assertion has a failing deliberately false reachability control.","",
            "| Example and claim | Input scope | Expected | Opening native | Final native | Integrated JBMC, opening → final | Standalone target / reach / other failures | JVM evidence or first open native step |",
            "|---|---|---|---|---|---|---|---|"]
    for key,pair in sub.items():
        a,b=pair["opening"],pair["final"];n=b["native"]
        scope=b["signature"] or "no arguments"
        if b["guard"]:scope+=" where "+b["guard"]
        if "String" in scope or "[]" in scope:scope+=" (length ≤ "+str(b["bound"])+")"
        ss=[link(v["evidence"],f"{p.removeprefix('preflight-')} {v['target']} / {v['reach']} / {v['otherFailures']}")
            for p,v in stock.get(key,{}).items()]
        replay=n["jvmReplay"]
        detail=n["firstUnproved"] or (str(replay["inputs"])+" → "+replay["outcome"] if replay else "Original JVM controls passed")
        lines.append("| "+" | ".join(map(cell,[link(b["claim"],f"{b['family']} {key}"),scope,b["expected"],
            link(a["evidence"],engine(a["native"])),link(b["evidence"],engine(n)),engine(a["jbmc"])+" → "+engine(b["jbmc"]),
            ", ".join(ss) or "Separate seed or upstream control",detail]))+" |")
    return "\n".join(lines)+"\n"


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase",choices=("final","qualified"),default="qualified")
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    card=compare(args.phase)
    outputs={BASE/"scorecard.json":json.dumps(card,indent=1)+"\n",PAGE:render(card)}
    for path,contents in outputs.items():
        if args.check: require(path.read_text()==contents,f"stale {path.name}")
        else: path.write_text(contents)
    print("38 historical and 60 original statements, with raw evidence checked")

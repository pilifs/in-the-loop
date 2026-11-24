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
import re
import tarfile

from campaign import CLAIMS, GRAPHS, ROOT, wire
from historical import FROZEN_SHA, GROUPS, benchmark, digest, freeze, selected
from standalone import LISTS
from direct_arrays import PHASE, HISTORIES, check_cells, check_run

BASE = ROOT/"verification/java-semantics-gap"
PAGE = ROOT/"llm-dlc/loops/jbmc-java-semantics-gap-results.md"
DECIMAL_PHASE = "decimal-transfer"


def require(ok, why):
    if not ok: raise ValueError(why)


def read(path):
    return json.loads(path.read_bytes())


def receipt_path(job):
    day = job[:8]
    return ROOT/"verification/results"/day[:4]/day[4:6]/day[6:]/job/"result.json"


@lru_cache(maxsize=None)
def job_receipt(job):
    return read(receipt_path(job))


def job_outputs(job):
    r = job_receipt(job)
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
    if verdict == "verified" and expected == "violation" and disposition=="false-success": return "JVM-contradicted proof"
    if verdict == "violation" and replay == "held": return "JVM-contradicted violation"
    return "open"


def native_scope(row,claim,bound,key):
    s=row["stated"]
    parameters=s["domain"]["parameters"]
    source=[param.strip().split() for param in claim.parameters.split(",") if param.strip()]
    require(len(parameters)==len(source) and not s["domain"]["shared_arrays"],key+" changed root domain")
    for (typ,name),p in zip(source,parameters):
        expected="java.lang.String" if typ=="String" else typ.replace(".Item","$Item")
        require(p["name"]==name and p["type"]==expected and p["null"]==(claim.nullable==name),
                key+" changed nullability or parameter")
        if typ=="String" or typ.endswith("[]"):
            require(p["max_length"]==bound,key+" changed input length")
            if typ.endswith(".Item[]"):
                require(p["kind"]=="array" and "arbitrary int fields" in s["domain"]["text"]
                        and "any cells may share an instance" in s["domain"]["text"],key+" narrowed the heap")
        else: require(p["kind"]=="primitive",key+" constructed a different scalar domain")
    environment=[{"kind":"initialization","basis":"engine","text":
                  "every JDK class is initialized already, its static initializer having run and thrown nothing"}]
    if key.startswith(("locals/", "gson-parent/", "gson-fix/")):
        environment.append({"kind":"library","basis":"engine","text":"fresh ThreadLocal keys are used on the one executing platform thread of the check"})
    actual=[a for a in s["assumptions"] if a["kind"]!="precondition"]
    require(environment[0] in actual and all(a in environment for a in actual),key+" added an environment assumption")
    require([a["text"] for a in s["assumptions"] if a["kind"]=="precondition"]==([claim.guard] if claim.guard else []),
            key+" narrowed the precondition")
    require(not row.get("throws") and not any(g.get("treatment") in ("assumed","contract") for g in row["search"].get("gaps",[])),
            key+" admitted an exception or an assumed gap")


def historical_statements(report, ids, definitions):
    native = {run["case"]: run["verdict"] for run in report["runs"] if run["engine"] == "native"}
    job = report["environment"]["job"]
    workspace = Path(job_receipt(job)["jvmcontract"]["path"]).parents[3]/"work"/job
    cases = []
    scopes = {}
    for cid in ids:
        case = definitions[cid].copy()
        # The benchmark digest includes the registered native expectation and the runner's absolute patch path.
        # Neither is part of the asserted statement, but both must match before borrowing the original scope.
        if "nativeStrict" in case:
            case["nativeStrict"] = native[cid]
        if "patch" in case:
            case["patch"] = str(workspace/Path(case["patch"]).relative_to(ROOT))
        cases.append(case)
        if case["kind"] == "property":
            scope = case["assert"]
            if case.get("assume"):
                scope = case["assume"] + " ⇒ " + scope
            if case.get("throws"):
                scope += " or throws " + ", ".join(case["throws"])
        else:
            scope = "equivalence of " + case["target"]
            if case.get("unchangedUnless"):
                scope += " unless " + case["unchangedUnless"]
        scopes[cid] = scope
    checksum = hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()
    require(checksum == report["settings"]["caseSpecificationsSha256"], "historical statement differs from its run")
    return scopes


def historic(phase):
    rows = freeze()
    results = {}
    definitions = {case["id"]: case for case in benchmark.load_cases({1, 2, 3, 4})}
    for group in GROUPS:
        p = BASE/phase/(group+".json")
        d = read(p)
        collected(p,d["environment"]["job"],d["environment"]["commit"])
        ids = selected(rows,group)
        scopes = historical_statements(d, ids, definitions)
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
            results.setdefault(cid,{"historical":rows[cid]["historical"],"expected":expected,"statement":scopes[cid],"source":d["environment"]["commit"],
                          "evidence":location(p),"inputClasses":hashlib.sha256(json.dumps(settings["classesSha256"],
                                    sort_keys=True).encode()).hexdigest(),"oracles":settings["oraclesSha256"]})[engine] = {
                "status":state(r["verdict"],expected,r["class"],replay),"verdict":r["verdict"],"seconds":r["seconds"],
                "firstUnproved":short_problem(r.get("problem","")),"replay":physical,"witness":r.get("witness")}
        require(len(seen)==2*len(ids),"missing historical engine outcome")
    return results


def subject_rows(phase, keys=None, recorded_phase=None, required_engines=None, *, directory=None):
    result = {}
    for key,subject in CLAIMS.items():
        if keys is not None and key not in keys:
            continue
        p = (directory if directory is not None else BASE/phase)/key/"measurement.json"
        d = read(p)
        collected(p,d["job"],d["source"])
        raw = p.parent/"raw.tar.gz"
        collected(raw,d["job"],d["source"])
        require(d["scope"] == json.loads(json.dumps(asdict(subject))) and d["subject"]==key and d["phase"]==(recorded_phase or phase)
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
                    if e=="native": native_scope(row,claims[m],subject.bound,cid)
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
            engines = ("native",) if phase == PHASE and key not in ("arrays", "gson-parent", "gson-fix") else ("native", "jbmc")
            require(seen == {(m,e) for m in claims for e in (required_engines or engines)},key+" missing engine rows")
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
                        other={(q["property"],q["status"]) for q in props if q["property"]!=run["target"]["property"]
                               and q["status"]!="SUCCESS"}
                        require(len(actual)==1 and actual[0]["status"]==run["status"] and len(props)==run["totalProperties"],
                                "mismatched standalone assertion ID or status")
                        require(other=={(q["property"],q["status"]) for q in run["otherFailures"]},
                                "standalone accompanying properties changed")
                actual=r["target"]
                result.setdefault(d["key"]+"/"+r["method"],{})[p.parent.name]={
                    "target":actual["status"],"id":(actual.get("target") or {}).get("property"),
                    "reach":r["reached"]["status"],"otherFailures":len(actual.get("otherFailures",[])),
                    "reachOtherFailures":len(r["reached"].get("otherFailures",[])),
                    "warnings":actual.get("warnings",[]),"jvm":actual.get("jvmReplay"),"evidence":location(p)}
    return result


def compare(phase):
    old,new=historic("opening"),historic(phase)
    before,after=subject_rows("opening"),subject_rows(phase)
    previous = subject_rows("qualified") if phase == PHASE else {}
    if previous:
        separate={s["graph"] for s in after.values() if "jbmc" not in s}
        comparator_phase=f"{PHASE}/integrated/qualified"
        for key in separate:
            native=read(BASE/phase/key/"measurement.json")
            jbmc=read(BASE/comparator_phase/key/"measurement.json")
            require(all(native[field]==jbmc[field] for field in ("scope","claimsSha256","source","libTree","adapterSha256","classes",
                "classpath","originalJvm","checkerSha256","jbmcSha256","packagedModelsSha256","jvmSha256","modulesSha256")),
                key+" comparator ran a different checker, original caller or scope")
        for cid,row in subject_rows(comparator_phase,separate,"qualified",("jbmc",)).items():
            after[cid]["jbmc"] = row["jbmc"]
            after[cid]["jbmcEvidence"] = row["evidence"]
        require(all("jbmc" in s for s in after.values()), "missing final integrated result")
    for a,b in [(old,new),(before,after)]:
        require(a.keys()==b.keys(),"changed denominator")
        for key in a:
            for field in ("classes","jvm","inputClasses","oracles","expected","claim","statement"):
                require(a[key].get(field)==b[key].get(field),f"{key}: before and after differ in {field}")
    environments={}
    for stage in (("opening","qualified",phase) if previous else ("opening",phase)):
        h=read(BASE/stage/"listOfArray.json")
        c=read(BASE/stage/"numbers/measurement.json")
        list_models={name+".class":h["repositoryModels"][name+".class"] for name in LISTS}
        require(len(list_models)==6,"different six-class list comparator layer")
        environments[stage]={"historicalSource":h["environment"]["commit"],"historicalJdk":h["environment"]["java"],
            "benchmarkBinaries":h["binaries"],"callerSource":c["source"],"callerChecker":c["checkerSha256"],
            "callerJdk":c["jdk"],"callerModules":c["modulesSha256"],"callerJbmc":c["jbmcSha256"],
            "callerCoreModels":c["packagedModelsSha256"],"listModels":list_models}
    card = {"phase":phase,"environments":environments,"historical":{k:{"opening":old[k],"final":new[k]} for k in old},
            "subjects":{k:{"opening":before[k],"final":after[k]} for k in before},"standalone":standalone_rows(),
            "transfers":transfers(phase)}
    if previous:
        card["previousNative"] = {key:{"status":r["native"]["status"],"evidence":r["evidence"]} for key,r in previous.items()}
        outcomes=Counter((r["native"]["status"] in DECIDED, r["jbmc"]["status"] in DECIDED) for r in after.values())
        card["pairedFinal"]={"both":outcomes[True,True],"nativeOnly":outcomes[True,False],
                             "integratedJbmcOnly":outcomes[False,True],"neither":outcomes[False,False],
                             "integratedByStatus":dict(Counter(r["jbmc"]["status"] for r in after.values()))}
    return card


def transfers(phase):
    rows=[]
    for num in (375,374):
        folder,=(ROOT/"examples").glob(f"{num}-*")
        passes=[]
        for tag in ("opening",phase):
            p=folder/"records"/("semantics-"+tag)/"run.json"
            d=read(p);collected(p,d["job"],d["source"])
            require(d["targetSha256"]==digest(folder/"target.json"),"transfer target changed")
            for task,v in d["tasks"].items():
                result=folder/v["receipt"]
                collected(result,d["job"],d["source"])
                require(digest(result)==v["sha256"],"original transfer receipt changed")
            passes.append(d)
        a,b=passes
        require(a["tasks"].keys()==b["tasks"].keys() and len(a["tasks"])==(4 if num==375 else 1),"missing transfer claim")
        for task,r in a["tasks"].items():
            final=b["tasks"][task]
            rows.append({"example":num,"task":task,"opening":short_problem(r["firstBlocker"] or ""),
                "final":short_problem(final["firstBlocker"] or ""),"status":final["status"],
                "source":b["source"],"checker":b["checkerSha256"],"job":b["job"],
                "evidence":location(folder/final["receipt"])})
    return rows


def link(path,text):
    return f"[{text}]({os.path.relpath(ROOT/path,PAGE.parent)})"


def cell(s):
    return str(s).replace("\n"," ").replace("|","\\|")


def engine(r):
    return f"{r['status']} ({r['seconds']:.2f} s)"


DECIDED={"proved","refuted"}
SECTIONS={n: (n-375 if n<=380 else n-376) for n in range(376,392)}


def totals(rows,cohort=None):
    names = [k for k,v in rows.items() if not cohort or v["final"].get("historical")==cohort]
    return {stage:dict(Counter(rows[k][stage]["native"]["status"] for k in names)) for stage in ("opening","final")}


CONFORMANCE = "20261123-104845-recheck-conformance-on-the-qualified-jav"
DECIMAL_CONFORMANCE = "20261123-135311-recheck-proof-tier-conformance-after-dec"
FAILED_LAUNCHER = "20261123-101413-qualify-standalone-ordinary-string-and-j"
FIXED_LAUNCHER = "20261123-104830-replay-corrected-standalone-string-unico"
HEAP_CONFORMANCE = "20261123-121039-run-both-proof-tier-conformance-tests-af"


def campaign_jobs(card):
    first = read(BASE/"opening/listOfArray.json")["environment"]["job"]
    jobs_dir = (ROOT/job_receipt(first)["job"]["path"]).parent
    session = job_receipt(first)["job"]["spec"]["submitted"]["session"]
    jobs = {}
    for spec in sorted(jobs_dir.glob("*.json")):
        if not first <= spec.stem <= CONFORMANCE:
            continue
        job = read(spec)
        if job["submitted"]["session"] != session:
            continue
        result = job_receipt(job["id"])
        spec_hash = hashlib.sha256(json.dumps(job, sort_keys=True).encode()).hexdigest()
        require(result["job"]["sha256"] == spec_hash and result["job"]["spec"] == job,
                "collector has a different job specification for " + spec.stem)
        require(result["status"] == ("failed" if spec.stem == FAILED_LAUNCHER else "passed"),
                "unresolved verification job " + spec.stem)
        jobs[spec.stem] = {"status":result["status"], "source":result["sourceCommit"],
                           "receipt":location(receipt_path(spec.stem))}
    require({first, CONFORMANCE, FAILED_LAUNCHER, FIXED_LAUNCHER} <= jobs.keys()
            and jobs[CONFORMANCE]["source"] == jobs[FIXED_LAUNCHER]["source"] == card["environments"]["qualified"]["callerSource"],
            "missing final conformance or original-witness retry on the measured source")
    return jobs


def qualify_companions(card):
    seedfile=BASE/"seed-profiles/measurement.json"; seed=read(seedfile); collected(seedfile,seed["job"],seed["source"])
    for layout,variant in seed["variants"].items():
        require(len(variant["runs"])==8 and variant["originalJvm"]["exit"]==0,layout+" incomplete seed comparison")
        for r in variant["runs"]:
            f=seedfile.parent/r["raw"];collected(f,seed["job"],seed["source"])
            require(digest(f)==r["sha256"] and r["target"],layout+" missing target assertion")
            if layout=="numeric":
                expected="FAILURE" if r["entry"] in ("floorOnly","wraps") else "SUCCESS"
                require(r["status"]==expected and not r["otherFailures"] and
                        (expected=="SUCCESS" or r["jvmReplay"]["outcome"]=="refuted"),"direct numeric seed disagreement")
    heapfile=BASE/"heap-and-monitors/measurement.json"; trace=read(heapfile);collected(heapfile,trace["job"],trace["source"])
    for name in ("matched","mixed","synchronizedMethod"):
        value=6 if name=="mixed" else 5
        require(trace["jvm"]["runs"][name]["observations"]==[
            f"{name} before the original read={value} workerBlockedOnClass={'false' if name=='mixed' else 'true'}",
            "original result="+("exposed" if name=="mixed" else "protected")],"wrong original monitor schedule")
    for row in trace["standalone"]["runs"].values():
        for r in row.values():
            f=heapfile.parent/r["raw"];collected(f,trace["job"],trace["source"])
            require(digest(f)==r["sha256"],"wrong class monitor property")
    origin_file = BASE/card["phase"]/"origins.json" if card["phase"] == PHASE else BASE/"origins.json"
    origins=read(origin_file)
    require(origins["graphs"].keys()==CLAIMS.keys(),"the class-origin audit must cover every graph")
    repeated=extra_repeated=0
    def witnesses(d):
        return {r["method"]:r["jvmReplay"]["sourceSha256"] for r in d["runs"]
                if r["engine"]=="native" and r["verdict"]=="violation"}
    for key,g in origins["graphs"].items():
        measured=read(BASE/card["phase"]/key/"measurement.json")
        require(g["checkerSha256"]==measured["checkerSha256"] and g["source"]==measured["source"]
                and g["jdkSha256"]==measured["modulesSha256"] and g["classpath"]==measured["classpath"]
                and g["jvmChecks"]==measured["originalJvm"]["checks"]
                and g["classes"][CLAIMS[key].owner]["sha256"]==measured["classes"][CLAIMS[key].owner+".class"],
                key+" mismatched selected class evidence")
        if card["phase"]==PHASE:
            require(g["nativeRefutations"]==witnesses(measured),key+" did not repeat every native refutation")
            repeated+=len(g["nativeRefutations"])
            if key in ("arrays","gson-parent","gson-fix"):
                control="histories" if key=="arrays" else key+"/exception-control"
                require(g["companionRefutations"]==witnesses(read(BASE/PHASE/control/"measurement.json")),
                        key+" did not repeat the companion witnesses")
                extra_repeated+=len(g["companionRefutations"])
    require(origins["arrayWitnesses"]["noNullCell"]["cells"][0]=="null"
            and origins["arrayWitnesses"]["noItemCell"]["cells"][0]!="null"
            and all(v["jvm"]=="refuted" for v in origins["arrayWitnesses"].values()),"both actual array witnesses must replay")
    require(len(origins["defaultWitnesses"])==8,"missing default-method witness replay")
    card["qualifications"]={"seeds":location(seedfile),"schedule":location(heapfile),"origins":location(origin_file),
                          "classBindings":sum(len(g["classes"]) for g in origins["graphs"].values()),
                          "plannedArray":trace["arrayPlan"]["diagnostic"],"monitorComparator":trace["standalone"]["runs"],
                          "arrayWitnesses":origins["arrayWitnesses"],"defaultWitnesses":origins["defaultWitnesses"]}
    if card["phase"]==PHASE:
        card["qualifications"].update(repeatedNativeRefutations=repeated,repeatedCompanionRefutations=extra_repeated)


def qualify_direct_controls(current):
    controls={}
    for name,key,source in (("histories","arrays","DirectArrayHistories"),
                            ("gson-parent/exception-control","gson-parent","GsonExceptionKind"),
                            ("gson-fix/exception-control","gson-fix","GsonExceptionKind")):
        file=BASE/PHASE/name/"measurement.json"
        d=read(file)
        raw=file.parent/"raw.tar.gz"
        collected(file,d["job"],current)
        collected(raw,d["job"],current)
        ordinary=read(BASE/PHASE/key/"measurement.json")
        require(all(d[k]==ordinary[k] for k in ("source","job","checkerSha256","jvmSha256","modulesSha256","classpath"))
                and digest(raw)==d["rawSha256"] and all(d["classes"][n]==v for n,v in ordinary["classes"].items())
                and digest(ROOT/"examples/379-nullable-reference-arrays/controls"/(source+".java"))==d["sourceSha256"],
                name+" changed companion or original bytes")
        if key=="arrays":
            require(d["scope"]==json.loads(json.dumps(asdict(HISTORIES))),"changed direct mutation scope")
            check_cells(d["runs"])
            claims={c.method:c for c in HISTORIES.claims}
        else:
            claim=next(c for c in CLAIMS[key].claims if c.method=="syntax")
            claims={"casts":claim}
        require({r["method"] for r in d["runs"]}==claims.keys() and len(d["runs"])==len(claims),name+" missing direct control")
        require(d["originalJvm"]["checks"]==(sum(len(c.holds)+len(c.fails) for c in HISTORIES.claims) if key=="arrays" else 4),
                name+" missing original JVM controls")
        with tarfile.open(raw) as archive:
            for r in d["runs"]:
                m=r["method"]
                check_run(r)
                if key.startswith("gson-"):
                    require(r["verdict"]==("verified" if key=="gson-parent" else "violation"),"wrong exact exception on "+key)
                decoder=wire.decode(archive.extractfile("raw/"+m+"/stdout.json").read().decode(),"prove")
                require(decoder.ok and len(decoder.outcomes)==1,name+" missing ordinary output")
                row,=decoder.outcomes
                require(row["target"]==source+"#"+m and row["assert"]=="result" and row["verdict"]==r["verdict"]
                        and (row.get("assume") or "")==claims[m].guard and r["stated"]==row["stated"]
                        and row["search"]["engine"]=="native" and row["stated"]["gap_mode"]=="strict"
                        and not row["stated"]["checker"].get("fallback") and row["search"]["unwind"]==16
                        and row["search"]["max_array_length"]==CLAIMS[key].bound
                        and not wire.exit_problem([r["verdict"]],r["exit"]),name+" mismatched native result")
                native_scope(row,claims[m],CLAIMS[key].bound,key+"/"+m)
                if r["verdict"]=="violation":
                    require(row["counterexample"]["inputs"]==r["jvmReplay"]["inputs"],name+" wrong replay inputs")
        controls[name]=location(file)
    return controls


def qualify_monitor_schedule(card):
    file = BASE / "monitor-schedules/measurement.json"
    d = read(file)
    collected(file, d["job"], d["source"])
    monitor = read(BASE/PHASE/"monitors/measurement.json")
    require(d["classes"]==monitor["classes"] and d["jdkModulesSha256"]==monitor["modulesSha256"]
            and d["adapterSha256"]==monitor["adapterSha256"] and d["modelSha256"]==digest(ROOT/"lib/benchmark/java-semantics-gap/monitor_schedules.py")
            and d["monitorRulesSha256"]==digest(ROOT/"examples/tools/targets/monitor_histories.py"),
            "schedule checker, caller or original JVM differs")
    jvm=d["originalJvm"]
    require(all(jvm["classes"].get(k)==sha for k,sha in d["classes"].items())
            and jvm["observerSha256"]==digest(ROOT/"examples/391-class-monitor-identity/controls/ObserveSchedule.java"),
            "physical schedule ran different classes")
    for listing in d["listings"].values():
        path=file.parent/listing["file"]
        collected(path,d["job"],d["source"])
        require(digest(path)==listing["sha256"],"monitor disassembly changed")
    protected={(5,6,True)}
    mixed=protected|{(6,6,False)}
    summaries={}
    for mode,r in {**d["runs"],"ignored static modifier":d["ignoringStaticSynchronized"]}.items():
        require({(o["read"],o["joinedValue"],o["returned"]) for o in r["outcomes"]}==
                (mixed if mode in ("mixed","ignored static modifier") else protected)
                and r["transitions"]>=r["states"]-1 and all(o["instructionSchedules"]>0 and o["witness"] for o in r["outcomes"]),
                "wrong schedule outcomes for "+mode)
        summaries[mode]={"states":r["states"],"outcomes":[{k:v for k,v in o.items() if k!="witness"} for o in r["outcomes"]]}
    require(set(summaries)=={"mixed","matched","synchronizedMethod","ignored static modifier"},"missing monitor scope")
    for mode,value in (("matched",5),("synchronizedMethod",5),("mixed",6)):
        require(jvm["runs"][mode]["observations"]==[
               f"{mode} before the original read={value} workerBlockedOnClass={'false' if mode=='mixed' else 'true'}",
               "original result="+("exposed" if mode=="mixed" else "protected")],"invalid physical monitor observation")
    require(jvm["runs"]["mixed-reader-first"]["observations"]==["mixed after the original read=5 saved=true","original result=protected"],
            "missing reader-first JVM replay")
    card["qualifications"]["boundedSchedules"]={"evidence":location(file),"scope":d["scope"],"runs":summaries}
    card["verification"][d["job"]]={"status":"passed","source":d["source"],"receipt":location(receipt_path(d["job"]))}


def qualify_followup(card):
    env=card["environments"][PHASE]
    current=env["callerSource"]
    gained=[]
    for key,old in card["previousNative"].items():
        now=card["subjects"][key]["final"]["native"]["status"]
        if old["status"] in DECIDED:
            require(now==old["status"],key+" lost its preceding qualified verdict")
        elif now in DECIDED:
            gained.append(key)
    expected={"arrays/categories","arrays/noNullCell","arrays/noItemCell",
              "gson-parent/compatible","gson-parent/syntax","gson-fix/compatible","gson-fix/syntax"}
    require(set(gained)==expected and len(card["subjects"])==60,"follow-up counts no longer match the reported changes")
    card["gainedSinceQualification"]=gained
    require(env["historicalSource"]==current and env["benchmarkBinaries"]["jvmcontract"]==env["callerChecker"],
            "historical and public entries need the same final checker")
    jobs={HEAP_CONFORMANCE,read(BASE/PHASE/"integrated/qualified/numbers/measurement.json")["job"]}
    for transfer in card["transfers"]:
        require(transfer["source"]==current and transfer["checker"]==env["callerChecker"],
                transfer["task"]+" transfer ran a different final checker")
        jobs.add(transfer["job"])
    for key in CLAIMS:
        d=read(BASE/PHASE/key/"measurement.json")
        require((d["source"],d["checkerSha256"],d["modulesSha256"],d["jbmcSha256"],d["packagedModelsSha256"])
                == (current,env["callerChecker"],env["callerModules"],env["callerJbmc"],env["callerCoreModels"]),
                key+" used a different checker, JDK or comparator")
        jobs.add(d["job"])
    for group in GROUPS:
        h=read(BASE/PHASE/(group+".json"))
        require(h["binaries"]==env["benchmarkBinaries"] and h["environment"]["commit"]==current,
                group+" used a different historical environment")
        jobs.add(h["environment"]["job"])
    card["qualifications"]["directControls"]=qualify_direct_controls(current)
    retries={}
    for job in sorted(jobs):
        result=job_receipt(job)
        spec=read(ROOT/result["job"]["path"])
        require(result["status"]=="passed" and result["sourceCommit"]==current and result["job"]["spec"]==spec,
                "unqualified final job "+job)
        if "supersedes" in spec:
            retries[spec["supersedes"]]=job
        card["verification"][job]={"status":"passed","source":current,"receipt":location(receipt_path(job))}
    initial=read(BASE/"direct-arrays/listOfArray.json")["environment"]["job"]
    card["scopeRetries"]=retries
    for job in sorted(retries.keys()|{initial}):
        result=job_receipt(job)
        require(result["status"]==("passed" if job==initial else "failed"),"wrong intermediate status "+job)
        card["verification"][job]={"status":result["status"],"source":result["sourceCommit"],"receipt":location(receipt_path(job))}
    qualify_monitor_schedule(card)


def decimal_comparison(mode, plan, paired, directory, finite):
    """Check the named engine reply and tie a reported counterexample to the original JVM input."""
    task = plan.task
    pair = paired["tasks"][task]
    expected_verdict = "violation" if plan.expected == "refuted" else "verified"
    row = pair["runs"][mode]
    raw = directory/task/mode/"stdout.json"
    err = raw.with_name("stderr.txt")
    for item, key in ((raw,"stdoutSha256"),(err,"stderrSha256")):
        collected(item, paired["job"], paired["source"])
        require(row[key] == digest(item), task+" different raw comparison")
    decoded = wire.decode(raw.read_text(errors="replace"), "prove")
    outcome = state(row["verdict"], expected_verdict, row["disposition"], row.get("jvmReplay",{}).get("outcome"))
    require(row["engine"] == mode and row["expected"] == expected_verdict, task+" different backend or expectation")
    if decoded.ok and len(decoded.outcomes) == 1:
        answer, = decoded.outcomes
        require(answer["target"] == "datawork.Decimals#"+plan.claim["property"] and answer["assume"] == pair["assume"]
                and answer["assert"] == pair["assert"] and answer["verdict"] == row["verdict"]
                and not wire.exit_problem([answer["verdict"]], row["exit"]), task+" different comparison statement")
        if outcome in DECIDED:
            require(answer["stated"] == row["stated"] and answer["search"]["engine"] == mode
                    and answer["stated"]["gap_mode"] == "strict" and not answer["stated"]["checker"].get("fallback")
                    and answer["search"]["unwind"] == pair["bounds"]["unwind"]
                    and answer["search"]["max_array_length"] == pair["bounds"]["maxArrayLength"], task+" unmatched decimal bounds")
            if mode == "native":
                from subjects import Claim
                native_scope(answer, Claim(plan.claim["property"], "int code", pair["assume"]), pair["bounds"]["maxArrayLength"], task)
            if outcome == "proved":
                require(answer["stated"]["bounds"]["complete"] and answer["stated"]["vacuity"]["status"] == "non-vacuous",
                        task+" incomplete decimal proof")
            else:
                require(answer["counterexample"]["inputs"] == row["jvmReplay"]["inputs"]
                        and row["jvmReplay"]["exit"] == 0, task+" different decimal witness")
    else:
        require(outcome == "open" and row["disposition"] in ("frontend refusal", "timeout"), task+" missing checker response")
    result = {"status":outcome, "seconds":row["seconds"], "evidence":location(raw),
                      "firstUnproved":short_problem(row["firstUnproved"]), "jvmReplay":row.get("jvmReplay")}
    if mode == "jbmc" and outcome == "open":
        pattern = re.escape(plan.claim["property"]) + r"\(code=(-?\d+)\) does not reproduce"
        candidate = re.search(pattern, row["firstUnproved"])
        if candidate:
            value = int(candidate[1])
            physical = read(ROOT/finite["receipt"])["sides"][plan.revisions[0]]["rows"]
            observed, = [r for r in physical if r["value"] == value]
            require(observed["admitted"] and observed["satisfies"] and observed["observations"] == [1,None],
                    task+" lacks the original JVM observation at JBMC's candidate")
            result["rejectedCandidate"] = {"code":value, "result":1, "jvmReceipt":finite["receipt"]}
    return result


def qualify_decimal_transfer(card):
    """Bind both decimal routes, all four paired comparisons and the unchanged controls."""
    import importlib.util
    from decimal_transfer import DEST, EXPECTED, FOLDER, PHASE as DECIMAL
    from targets import native_selectors, route, sidecar

    # This is the same original pair, selector and public receipt format as the Spring/data workstream.
    spec = importlib.util.spec_from_file_location("spring_data_scorecard", ROOT/"lib/benchmark/spring-java-data/scorecard.py")
    public = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(public)
    report_path = FOLDER/"records"/DECIMAL/"run.json"
    ordinary_job = public.managed(read(report_path)["job"])
    ordinary = public.run_report(ordinary_job, FOLDER, DECIMAL)
    selectors = public.run_report(ordinary_job, FOLDER, DECIMAL+"-selectors")
    path = DEST/"paired/measurement.json"
    paired = read(path)
    source = ordinary["source"]
    collected(path, paired["job"], source)
    checker = ordinary["checkerSha256"]
    require(ordinary["job"] == selectors["job"] and source == selectors["source"] == paired["source"]
            and checker == selectors["checkerSha256"] == paired["checkerSha256"]
            and ordinary["libTree"] == selectors["libTree"] == paired["libTree"], "different decimal checker")
    require(set(ordinary["tasks"]) == set(selectors["tasks"]) == set(paired["tasks"]) == EXPECTED.keys(),
            "missing original decimal task")
    require(paired["staging"] == "staged" and paired["secondsPerClaim"] == 120, "different decimal comparator profile")
    example = read(FOLDER/"example.json")
    target = sidecar.load(FOLDER, example)
    authored = {t["id"]: t for t in read(FOLDER/"target.json")["tasks"]}
    cases = {}
    for task, expected in EXPECTED.items():
        plan = route.resolve(FOLDER, example, target, task)
        finite, native = public.public(ordinary_job, FOLDER, plan, authored[task], ordinary)
        selector = selectors["tasks"][task]
        receipt = FOLDER/selector["receipt"]
        collected(receipt, selectors["job"], source)
        checked = native_selectors.validate_result(FOLDER, plan, receipt)
        special = read(receipt)
        require(native["status"] == finite["status"] == checked["status"] == expected
                and selector["sha256"] == digest(receipt) and checked["admitted"] == 3,
                task+" incorrect original or selector outcome")
        require(finite["inputs"] == 3 and finite["differences"] == (3 if expected == "refuted" else 0),
                task+" incomplete original JVM observations")
        pair = paired["tasks"][task]
        require(pair["claimKey"] == plan.claim["key"] and pair["assume"] == plan.claim["assume"]
                and pair["assert"] == plan.claim["assert"] and pair["bounds"] == plan.claim["bounds"]
                and pair["entry"] == native["binding"]["entry"] and pair["classpath"] == special["classpath"]
                and native["classpath"] == [a["sha256"] for a in pair["classpath"]], task+" changed decimal inputs")
        compared = {mode:decimal_comparison(mode, plan, paired, path.parent, finite) for mode in ("native","jbmc")}
        require(compared["native"]["status"] == ("refuted" if expected == "refuted" else "proved"), task+" missing paired native decision")
        cases[task] = {"ordinary":native, "finite":finite, "selectors":location(receipt), "checkedSelectors":checked["checked"], "paired":compared}
    require(all(row["sourceSha256"] == digest(FOLDER/"controls/DecimalRuntime.java") and len(row["rows"]) == 3
                for row in paired["originalJvm"].values()) and set(paired["originalJvm"]) == {"parent","landed"}, "missing exact runtime class controls")
    current = subject_rows(DECIMAL+"/callers", recorded_phase="callers")
    historic_rows = historic(DECIMAL+"/historical")
    for group, earlier in ((current,card["subjects"]), (historic_rows,card["historical"])):
        require(set(group) == set(earlier), "different regression cohort")
        for key, row in group.items():
            prior = earlier[key]["final"]
            require(row["source"] == source and row["native"]["status"] == prior["native"]["status"]
                    and row["jbmc"]["status"] == prior["jbmc"]["status"]
                    and row["expected"] == prior["expected"], key+" changed matched outcomes")
            for field in ("inputClasses","oracles","signature","guard","bound","classes","jvm","claim"):
                if field in prior: require(prior[field] == row[field], key+" changed "+field)
            earlier[key][PHASE] = {"source":prior["source"], "evidence":prior["evidence"],
                                   "jbmcEvidence":prior.get("jbmcEvidence",prior["evidence"])}
            earlier[key]["final"] = row
    entry = read(DEST/"callers/numbers/measurement.json")
    bench = read(DEST/"historical/listOfArray.json")
    require(entry["checkerSha256"] == bench["binaries"]["jvmcontract"] == checker
            and entry["jvmSha256"] == paired["javaSha256"] and entry["modulesSha256"] == paired["jdkModulesSha256"]
            and entry["jbmcSha256"] == paired["jbmcSha256"] and entry["packagedModelsSha256"] == paired["coreModelsSha256"],
            "different engine or JDK in the matched regressions")
    startup_path = BASE/"monitor-startup/measurement.json"
    startup = read(startup_path)
    require(startup["originalClasses"] == current["monitors/matched"]["classes"]
            and startup["jdkModulesSha256"] == entry["modulesSha256"]
            and startup["observerSha256"] == digest(ROOT/"examples/391-class-monitor-identity/controls/WorkerStartup.java"),
            "different monitor startup classes or runtime")
    observed = {(r["entry"],r["parentBinding"]):(r["result"],r["childValueCalls"],r["finalShared"]) for r in startup["jvmRuns"]}
    expected_startup = {("constructor",b):("NEW",int(b in ("present","null")),41) for b in ("absent","removed","null","present")}
    expected_startup.update({(m,"throw"):("original exception",1,41) for m in ("matched","mixed","synchronizedMethod")})
    expected_startup["matched","present"] = ("true",1,6)
    require(observed == expected_startup and len(startup["jvmRuns"]) == len(observed), "incomplete original worker startup controls")
    jobs = {ordinary["job"],paired["job"],entry["job"],bench["environment"]["job"],DECIMAL_CONFORMANCE}
    for job in sorted(jobs):
        checked_source, _ = job_outputs(job)
        require(checked_source == source, job+" ran another decimal source")
        card["verification"][job] = {"status":"passed","source":source,"receipt":location(receipt_path(job))}
    proof_step, = job_receipt(DECIMAL_CONFORMANCE)["steps"]
    for test in ("the_corpus_agrees_with_the_jvm_under_jbmc_and_auto","the_corpus_agrees_with_the_jvm_under_auto_confirm"):
        require("test "+test+" ... ok" in proof_step["tail"], "missing proof-tier conformance result for "+test)
    card["environments"][DECIMAL] = {**card["environments"][PHASE], "historicalSource":source, "callerSource":source,
                                     "benchmarkBinaries":bench["binaries"], "callerChecker":checker,
                                     "callerJdk":entry["jdk"], "historicalJdk":bench["environment"]["java"]}
    outcomes = Counter((r["native"]["status"] in DECIDED, r["jbmc"]["status"] in DECIDED) for r in current.values())
    card["pairedFinal"] = {"both":outcomes[True,True],"nativeOnly":outcomes[True,False],
                           "integratedJbmcOnly":outcomes[False,True],"neither":outcomes[False,False],
                           "integratedByStatus":dict(Counter(r["jbmc"]["status"] for r in current.values()))}
    for t in card["transfers"]:
        if t["example"] == 375:
            before = {k:t[k] for k in ("final","status","source","checker","job","evidence")}
            native = cases[t["task"]]["ordinary"]
            t.update({PHASE:before}, final="", status=native["status"], source=source, checker=checker,
                     job=ordinary["job"], evidence=native["receipt"])
    card["decimalTransfer"] = {"source":source,"checkerSha256":checker,"job":ordinary["job"],"paired":location(path),
                               "tasks":cases,"originalJvm":paired["originalJvm"],"monitorStartup":location(startup_path)}
    card["phase"] = DECIMAL


def decimal_findings(study):
    rows = study["tasks"]
    paired = link(study["paired"], "Original JVM values and matched checker runs")
    lines = ["## Commons Lang decimal parser", "",
             "All four ordinary claims on Commons Lang #1635 previously stopped at `Float.valueOf(String)`. "
             "The follow-up checked the original parent and fix on the whole guard `0 ≤ code < 3`, then repeated the checks through the admitted constant calls. "
             "Both routes yielded three proofs and a parent refutation. These four transfer claims have their own denominator. "+paired, "",
             "| Claim | Ordinary native, full guard | Native selector check | Integrated JBMC |",
             "|---|---|---|---|"]
    for task in ("precise-parent","precise-landed","preserved-parent","preserved-landed"):
        case = rows[task]
        native = case["ordinary"]
        comp = case["paired"]["jbmc"]
        lines.append("| "+" | ".join([task,link(native["receipt"],native["status"]),link(case["selectors"],native["status"]),
                     link(comp["evidence"],engine(comp))])+" |")
    candidates = [(task,case["paired"]["jbmc"]["rejectedCandidate"]) for task,case in rows.items()
                  if "rejectedCandidate" in case["paired"]["jbmc"]]
    if candidates:
        lines.extend(["","Integrated JBMC also refuted the parent precision claim. Its other candidate counterexamples "
                      "returned 1 on the original JVM, leaving those comparisons open. "
                      +" · ".join(link(r["jvmReceipt"],f"{task}, selector {r['code']}") for task,r in candidates)])
    lines += ["",
             "The positive literals `0.100000001490116121` and `0.100000001490116122` collapse to the same Float on the parent. "
             "The negative literal also returns a Float there. The fix returns three exact BigDecimals with signed coefficients "
             "`100000001490116121`, `100000001490116122`, and `-100000001490116121`, all at scale 18. "
             "Both revisions retain the raw Float bits for `0.1` and `0.5`, the Integer value 17, and the exact NumberFormatException for `1eE`. "
             +link(rows["precise-parent"]["ordinary"]["replay"],"Original parent witness")+" · "+paired, "",
             "After floating-point parsing and formatting, the long decimal first reached `BigDecimal(String)` and then the `BigInteger.bitsPerDigit` table. "
             "The integer control reached `Objects.checkFromToIndex` inside `Integer.parseInt`. The checker now executes those JDK paths and decodes five arithmetic tables from the pinned Temurin 21 initializers. "
             "An independent test covers a decimal just above a binary32 midpoint that produces a different word if rounded through binary64. "
             +link("lib/tests/fixtures/claims/claims/DecimalText.java","Rounding, scale, identity and initializer controls"), ""]
    return lines


def findings(card):
    phase=PHASE if "decimalTransfer" in card else card["phase"]
    def reported(key):return read(BASE/phase/key/"measurement.json")
    def ref(key,caption):return link(location(BASE/phase/key/"measurement.json"),caption)
    f=card["subjects"]
    grids={k:reported(k)["jvmGrid"] for k in ("numbers","endian","surrogates")}
    for key,counts in {"numbers":("16777216","4194304"),"endian":("65536","5 boundaries"),"surrogates":("1048576","589824","zero writer units")}.items():
        require(all(s in grids[key]["observations"] for s in counts),key+" incomplete independent JVM grid")
    ordered=[
        "## What the public callers showed","",
        "The four original frozen list statements separate null varargs, slot isolation, first and last matches, and duplicate element references. On the transfer, the caller replaces an array slot and changes the retained object. The JDK-specific empty-list identity is confined to the registered statement. "
        + ref("lists","Array and collection histories"),"",
        "The historical Fraction method rounds numerator / 2 to binary32 and the caller widens it. The full native statement covers all 16,777,216 numerators. The independent JVM loop found 4,194,304 failures of the floor rule, including 33,554,431 rounding to 16,777,216. The MutableDouble caller covers all 2⁵² mantissas in the exponent-31 binade. On the original JVM the endpoint 0x41e0000000000000 narrowed to MAX_VALUE and, after negation and mutation, to MIN_VALUE. Narrowing through long instead returned MIN_VALUE on the positive value. "
        +ref("numbers","Full scopes, opcode twins, replays and costs"),"",
        "The released Commons IO byte swaps were checked on all 32 or 64 input bits. The independent JVM ran 65,536 patterned inputs and five boundaries per width. The Commons Text translator took a custom CharSequence and recording writer. Its JVM checked all 1,048,576 valid pairs and both offsets on 589,824 additional pairs. The additional grid crosses twelve disjoint 64-unit windows per axis around BMP and surrogate boundaries. "
        +ref("endian","Word identities")+" · "+ref("surrogates","UTF-16 observations"),"",
        "On the two original Guava builds the typed and untyped arrays contain the very same three Integer references. The parent throws ArrayStoreException before changing the typed array and writes the formatted strings into Object[]. The fix returns “5 + 6 = 11” and retains the three references on both. The Commons Collections iterator independently exercises the compatible, null and incompatible single-element stores and the pre-next exception. "
        +ref("guava-parent","Guava parent")+" · "+ref("guava-fix","Guava fix")+" · "+ref("store-iterator","Twelve iterator histories"),"",
    ]
    if "qualifications" in card:
        q=card["qualifications"];heap=q["arrayWitnesses"];m=q["monitorComparator"]
        ordered+=["## Independent comparator checks","",
            f"The original JVM and the measured checker selected the same bytes for {q['classBindings']} loaded application and library classes across 21 classpaths. Each graph also reran its original controls with class loading traced. "
            +(f"A second JVM pass reconstructed all {q['repeatedNativeRefutations']} frozen native counterexamples and {q['repeatedCompanionRefutations']} separate heap or Gson counterexamples from their saved inputs. " if phase==PHASE else "")
            +link(q["origins"],"Providers, JAR entries and SHA-256 digests"),"",
            "Both packaged binary/model pairs decided the four direct numeric seed assertions, including the original double-typed MutableDouble entry. The long-bits wrapper is recorded independently. Its standalone disagreement does not change either the direct comparator result or the qualified native result. "
            +link(q["seeds"],"Direct seeds and exact numeric witnesses"),"",
            "On a fresh JVM the default-method answers are invariant under moving the replay helpers. The Ubuntu 22.04 models give the correct pair with the helpers separate and reverse both answers with them combined. The installed Ubuntu 24.04 models reverse that pattern. Crossing the two binaries with the model JARs preserves the model-dependent outcomes. The audit replayed the actual arguments of all eight failing named assertions on their original classfiles. The cause inside JBMC remains open. "
            +link(q["seeds"],"Four package pairings and two layouts")+" · "+link(q["origins"],"Original default-method replays"),"",
            f"Stock JBMC's two opposite false reference-array assertions produced a {heap['noNullCell']['length']}-cell array with a null first element and a {heap['noItemCell']['length']}-cell array with a populated first element. The original JVM reconstructed the trace cells, field values and identities and refuted both assertions. "
            + ("The follow-up checks nullable Item[] directly. The separately requested construction plan still has its own array-leaf limit. " if phase==PHASE else
               "The native constructed alias control covers equal-valued distinct objects and one shared object over every initial int. The direct frontend rejects the Item[] root. Its explicit two-cell construction plan also stops because array leaves admit integral and boolean elements. ")
            +ref("arrays","Direct native and constructed heaps")+" · "+link(q["schedule"],"Explicit construction plan"),"",
            f"At the unchanged read, the debugger observed 5 with the worker blocked on the very class mirror held by the caller, for both explicit and static synchronization. Holding the instance allowed the worker to write 6 before that read. JBMC's in-lock assertions returned **{m['matched']['target']['status']}** for the explicit shared class monitor, **{m['mixed']['target']['status']}** for mixed monitors and **{m['staticMethod']['target']['status']}** for the static method. The trace records JBMC's warning about the static synchronized modifier. The original joined caller has a separate row in the table. "
            +link(q["schedule"],"Actual JVM schedules, target assertion IDs and warnings"),"",
            "The packaged single-store model accepted the deliberately false incompatible-write assertion. On the original JVM the store throws ArrayStoreException and preserves the typed cell. The portable enum models also have their own standalone lookup and ordinal results. These model disagreements are distinct from the thirteen historical JBMC leads. "
            +ref("stores","Covariant-store caller")+" · "+ref("enum","Constant and exception identities"),""]
    if phase == PHASE:
        controls = card["qualifications"]["directControls"]
        ordered[2:2]=[
            "At the preceding qualification, 50 of the 60 native statements had decisions. The direct array entry now establishes the classifier range and refutes both opposite first-cell claims. The array may be null or have zero, one or two cells. Populated cells hold fresh exact components with arbitrary signed int fields, including shared and equal-valued distinct objects. The component factory supports final flat classes with a trivial constructor and writable int fields. The separate mutation proof covers every initial int. Its negative controls replayed two distinct objects at Integer.MAX_VALUE and one object referenced twice at the same value. "
            +ref("arrays","Five frozen array entries")+" · "+link(controls["histories"],"Direct mutation proofs and both JVM heaps"),"",
            "Both unmodified Gson #719 builds return the expected concrete class for all five compatible selections. On all four incompatible selections the parent throws ClassCastException and the fix throws JsonSyntaxException. A separate public-entry assertion establishes the parent's exact exception and is refuted on the fix. The preceding checker stopped at Collections.synchronizedMap in Gson's constructor at line 116. Capped probes of the compatible fix entry next reached List.addAll at constructor line 205 and Map.getClass() in the selected JDK's Collections.unmodifiableMap at line 1631. The final checker runs the collection bytecode and resolves that class from the allocation. Each Gson statement uses a single calling platform thread for its ThreadLocal cache. "
            +ref("gson-parent","Parent")+" · "+ref("gson-fix","Fix")+" · "+link(controls["gson-parent/exception-control"],"Parent exception proof")+" · "+link(controls["gson-fix/exception-control"],"Fix counterexample"),""]
        schedule=card["qualifications"]["boundedSchedules"]
        ordered+=["## All completed schedules in the two-thread model","",
                  "The checker executes the original caller and worker instructions under sequential consistency. Platform-thread construction, start and uninterrupted join succeed. Each lifecycle call is one transition. The counts include each ordering of runnable application instructions and exclude idle steps. A debugger replay on the original JVM observed each return value. "+link(schedule["evidence"],"Disassembly, instruction witnesses and JVM observations"),"",
                  "| Caller and worker lock | Reachable states | Read 5, returned true | Read 6, returned false |",
                  "|---|---:|---:|---:|"]
        for mode,label in (("matched","Class / class"),("mixed","Instance / class"),("synchronizedMethod","Class / static synchronized method"),
                           ("ignored static modifier","Same classfiles with the static modifier ignored in the model")):
            r=schedule["runs"][mode]
            counts={v["read"]:v["instructionSchedules"] for v in r["outcomes"]}
            ordered.append(f"| {label} | {r['states']:,} | {counts.get(5,0):,} | {counts.get(6,0):,} |")
        ordered+=["","All completed schedules leave the shared field at 6. The ordinary native entry first needs the platform-thread constructor. The three schedule results have their own scope and denominator.",""]
        if "decimalTransfer" in card:
            ordered+=["Eight fresh JVM controls followed the original Worker constructor into the platform thread's inherited map. "
                      "A present parent binding, including a stored null, invoked the application's childValue on the parent before the worker started. "
                      "An absent or removed binding made zero callbacks. A throwing callback escaped all three original monitor callers before their first shared-field write. "
                      +link(card["decimalTransfer"]["monitorStartup"],"Original constructor bytecode and callback outcomes"),""]
    ordered+=["## Remaining direct native claims","",
              "| Original caller | First unproved step | Open statements |","|---|---|---:|"]
    grouped={}
    for key,v in f.items():
        b=v["final"]
        if b["native"]["status"] not in DECIDED:
            barrier=b["native"]["firstUnproved"] or b["native"]["status"]
            grouped.setdefault((b["family"],barrier),[]).append(key)
    for (number,problem),keys in grouped.items():
        ordered.append("| "+" | ".join(map(cell,[link(f[keys[0]]["final"]["evidence"],str(number)+" "+", ".join(keys)),
                                                problem,str(len(keys))]))+" |")
    total=lambda stage: sum(r[stage]["native"]["seconds"] for r in f.values())
    ordered+=["",f"The sum of native checker times on the sixty statements was {total('opening'):.3f} s at opening and {total('final'):.3f} s at qualification. Compilation, class binding and original-JVM replays are charged separately in the job receipts. All native results use initialized JDK classes. The statements that use ThreadLocal also record their one-platform-thread scope."]
    return ordered+[""]


def render(card):
    decimal = card.get("decimalTransfer")
    historical,sub,stock=card["historical"],card["subjects"],card["standalone"]
    leads=totals(historical,"jbmc-only");controls=totals(historical,"native-only");scores=totals(sub)
    def count(group,stage):return sum(group[stage].get(k,0) for k in DECIDED)
    gains=[v for v in sub.values() if v["opening"]["native"]["status"] not in DECIDED and v["final"]["native"]["status"] in DECIDED]
    lost=[k for part in (historical,sub) for k,v in part.items() if v["opening"]["native"]["status"] in DECIDED and v["final"]["native"]["status"] not in DECIDED]
    wrong={s:[k for part in (historical,sub) for k,v in part.items() if v[s]["native"]["status"].startswith("JVM-contradicted")]
           for s in ("opening","final")}
    lines=["# Java semantics on the native checker and JBMC","",
           f"The opening checker decided **{count(leads,'opening')}/13** historical JBMC-only claims and the final checker decided **{count(leads,'final')}/13**, a gain of **{count(leads,'final')-count(leads,'opening')}** at unchanged scope. The final decisions were {leads['final'].get('proved',0)} proofs and {leads['final'].get('refuted',0)} refutations replayed on the JVM. The native-only regression controls held at **{count(controls,'final')}/24**, with {controls['final'].get('proved',0)} proofs and {controls['final'].get('refuted',0)} replayed refutations. The historical denominator remains 187, with 133 shared successes, 24 native-only, 13 staged-JBMC-only and 17 decided by neither engine.","",
           f"On the **60** independently registered campaign statements, direct native decisions moved from **{count(scores,'opening')}/60** to **{count(scores,'final')}/60**. The final total includes **{scores['final'].get('proved',0)} proofs** and **{scores['final'].get('refuted',0)} original-JVM-replayed refutations**. **{len(gains)} statements** gained a decision at their original scope across **{len({SECTIONS[v['final']['family']] for v in gains})} of the 15 semantic families**. There were {len(lost)} native regressions. JVM-contradicted native verdicts went from {len(wrong['opening'])} to {len(wrong['final'])}.","",
           "Historical runs used the original benchmark’s JDK 25 harness, 120-second deadline, unwind 16, array bound 8 and staged integrated JBMC. New public callers used Temurin 21.0.13, explicit strict engines and the same 120-second deadline. Every linked measurement records the original classpath order, binary and model identity, input bounds and costs. The additional registered positive list-search control sits outside the 13.","",
           "## Historical differential","",
           "| Frozen claim | Assertion and guard, or equivalence scope | Historical cohort | Expected | Opening native | Final native | Integrated JBMC, opening → final | Standalone target with six list models / packaged models | Original JVM witness or first open native step |",
           "|---|---|---|---|---|---|---|---|---|"]
    position = lines.index("## Historical differential")
    lines[position:position] = (decimal_findings(decimal) if decimal else []) + findings(card)
    for key,pair in historical.items():
        a,b=pair["opening"],pair["final"];n=b["native"]
        detail=(f"{n['witness']} → {n['replay']}" if n["replay"] else n["firstUnproved"] or "Registered JVM controls")
        separate={"listOfArray/1":"guardedArray","listOfArray/2":"allArrays","listSearch/1":"guardedSearch","listSearch/2":"allSearch"}.get(key.removeprefix("conformance/"))
        paired="—"
        if separate:
            ss=stock["registered-lists/"+separate]
            paired=" / ".join(link(ss["preflight-"+p]["evidence"],ss["preflight-"+p]["target"]) for p in ("six-lists","packaged"))
        lines.append("| "+" | ".join(map(cell,[key,"`"+b["statement"]+"`",b["historical"],b["expected"],link(a["evidence"],engine(a["native"])),link(b["evidence"],engine(n)),
            engine(a["jbmc"])+" → "+engine(b["jbmc"]),paired,detail]))+" |")
    lines+=["","## Original callers","",
            "A refutation earns credit when the actual checker input fails on a fresh original JVM. A named refusal, an incomplete bound or a witness that holds on replay stays open. Standalone columns identify the target status, reachability assertion status and accompanying failing properties. Credit requires a failing deliberately false reachability control and successful accompanying properties.",""]
    if "pairedFinal" in card:
        p=card["pairedFinal"]
        j=p["integratedByStatus"]
        lines+=[f"All 60 final native and integrated JBMC entries used the same checker build, JDK, original class files and 120-second budgets. Both profiles qualified {p['both']} statements, native alone qualified {p['nativeOnly']}, integrated JBMC alone qualified {p['integratedJbmcOnly']}, and {p['neither']} remained open in both. The integrated profile produced {j.get('proved',0)} qualified proofs and {j.get('refuted',0)} replayed refutations. The original JVM contradicted {j.get('JVM-contradicted proof',0)} further integrated proofs. Each comparator result links to its measurement.",""]
    lines+=["| Example and claim | Input scope | Expected | Opening native | Final native | Integrated JBMC, opening → final | Standalone target / reach / other failures | JVM evidence or first open native step |",
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
            link(a["evidence"],engine(a["native"])),link(b["evidence"],engine(n)),engine(a["jbmc"])+" → "+link(b.get("jbmcEvidence", b["evidence"]),engine(b["jbmc"])),
            ", ".join(ss) or "Separate seed or upstream control",detail]))+" |")
    lines+=["","## Transfer to existing ordinary callers",""]
    if decimal:
        formatter, = (t for t in card["transfers"] if t["example"] == 374)
        lines += [f"The decimal rows were rechecked at `{decimal['source'][:12]}`. "
                  f"The formatter's latest ordinary receipt is from `{formatter['source'][:12]}`.",""]
    column = "Last measured first unproved step" if decimal else "Final first unproved step"
    lines+=[f"| Example | Frozen claim | Opening first unproved step | {column} | Ordinary result |",
            "|---|---|---|---|---|"]
    for t in card["transfers"]:
        lines.append("| "+" | ".join(map(cell,[str(t["example"]),t["task"],t["opening"] or "Decided",
                           t["final"] or "Decided",link(t["evidence"],t["status"])]))+" |")
    lines+=["","## Recount and replay","",
            "| Measurement | Historical source / checker SHA-256 prefix | Public caller source / checker SHA-256 prefix | Integrated JBMC / packaged core-model SHA-256 prefixes |",
            "|---|---|---|---|"]
    for phase in card["environments"]:
        env=card["environments"][phase]
        lines.append(f"| {phase} | `{env['historicalSource'][:12]}` / `{env['benchmarkBinaries']['jvmcontract'][:16]}` | "
                     f"`{env['callerSource'][:12]}` / `{env['callerChecker'][:16]}` | "
                     f"`{env['callerJbmc'][:16]}` / `{env['callerCoreModels'][:16]}` |")
    if "verification" in card:
        jobs=card["verification"]
        conformance = HEAP_CONFORMANCE if card["phase"]==PHASE else CONFORMANCE
        if decimal:
            conformance = DECIMAL_CONFORMANCE
        passed=sum(r["status"]=="passed" for r in jobs.values())
        lines+=["", f"Of {len(jobs)} campaign jobs, {passed} passed. Both proof-tier conformance tests passed on the final measured source. "
                "One intermediate Unicode witness launcher failed to compile because its parameter and a local variable shared a name. "
                "The corrected launcher replayed the original witness and completed the string and deque checks. "
                +link(jobs[conformance]["receipt"],"Final conformance")+" · "
                +link(jobs[FAILED_LAUNCHER]["receipt"],"Initial launcher failure")+" · "
                +link(jobs[FIXED_LAUNCHER]["receipt"],"Passing replacement")]
        if "scopeRetries" in card:
            links=[link(jobs[old]["receipt"],"Initial "+("array" if "array-heaps" in new else "caller")+" check")+" · "+
                   link(jobs[new]["receipt"],"Passing replacement") for old,new in card["scopeRetries"].items()]
            lines+=["","Two follow-up jobs stopped at the scope comparison because tuples in memory and arrays in the saved JSON compared differently. The bytecode, claims, JVM and serialized scopes matched. Both replacement jobs passed after the comparison used the serialized scope for both inputs. "+" · ".join(links)]
    lines+=["",
            "Run `python3 -B lib/benchmark/java-semantics-gap/scorecard.py --check` to validate the source-bound receipt digests, per-engine rows and reported totals. Run `python3 -B lib/benchmark/java-semantics-gap/origins.py --check` to repeat the original-JVM class bindings. Each numbered example also exposes its original tasks through `examples/tools/build.py --plan NUMBER`. The campaign's `seed` command imports its checksum-verified setup JARs into the normal example cache. "
            +link(location(BASE/"scorecard.json"),"Machine-readable comparison")+" · "
            +link("llm-dlc/loops/jbmc-java-semantics-gap-brief-setup.md","Pinned artifacts and setup recipes")]
    return "\n".join(lines)+"\n"


def decimal_example(study):
    folder, = (ROOT/"examples").glob("375-*")
    ep = folder/"example.json"
    example = read(ep)
    note = ("The Java semantics follow-up decided all four ordinary native claims on both original Commons Lang builds. "
            "The parent returned Float for all three precision inputs. The fix returned the exact BigDecimal coefficients at scale 18. "
            "Both revisions preserved the two short Floats, the Integer, and the malformed-input exception.")
    example["verdictLabel"] = "Ordinary native 4/4, finite JVM 4/4"
    example["notes"] = [s for s in example["notes"] if not s.startswith("The Java semantics follow-up ")] + [note]
    page = folder/"README.md"
    opening = re.sub(r"\n## Ordinary native follow-up\n.*?(?=\n## |\Z)", "\n", page.read_text(), flags=re.S)
    heading = "## Earlier Spring/data results"
    opening = opening.replace("## Recorded results", heading)
    opening = opening.replace("4 ordinary native obligations remain open.", "All four ordinary native obligations were open at that measurement.")
    table = ["## Ordinary native follow-up", "", note, "",
             "The strict checker took the unchanged public entry with `0 ≤ code < 3`, unwind 256, maximum array length 16,384 and a 120-second deadline. A separate run covered every admitted constant call required for each proof and replayed the parent witness on a fresh JVM.", "",
             "| Claim | Whole guard | Selector checks |", "|---|---|---|"]
    for name in ("precise-parent","precise-landed","preserved-parent","preserved-landed"):
        case = study["tasks"][name]
        result = case["ordinary"]
        guarded = os.path.relpath(ROOT/result["workflow"], folder)
        selected = os.path.relpath(ROOT/case["selectors"], folder)
        table.append(f"| {name} | [{result['status']}]({guarded}) | [{case['checkedSelectors']} checked]({selected}) |")
    table += ["","[Exact runtime classes, raw values and integrated JBMC](../../" +study["paired"]+") · "
              "[Campaign results](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md#commons-lang-decimal-parser)"]
    intro, history = opening.split(heading, 1)
    return {ep:json.dumps(example,indent=2)+"\n", page:intro.rstrip()+"\n\n"+"\n".join(table)+"\n\n"+heading+history}


def example_outputs(card):
    files={}
    for number in sorted({s.example for s in CLAIMS.values()}):
        selected_rows={k:v for k,v in card["subjects"].items() if v["final"]["family"]==number}
        counts=totals(selected_rows)
        final=counts["final"]
        proved,refuted=final.get("proved",0),final.get("refuted",0)
        count=len(selected_rows)
        opening=sum(counts["opening"].get(s,0) for s in DECIDED)
        label=f"Ordinary native {proved+refuted}/{count}"
        note=(f"The campaign's ordinary native checker decided {opening}/{count} at opening and {proved+refuted}/{count} at qualification, "
              f"with {proved} established and {refuted} refuted on original-JVM replays.")
        folder,=(ROOT/"examples").glob(f"{number}-*")
        ep=folder/"example.json";example=read(ep)
        example["verdictLabel"]=label
        example["notes"]=[n for n in example.get("notes",[]) if not n.startswith(("The campaign's ordinary native checker decided ", "The direct mutation controls ", "The separate schedule checker "))]
        example["notes"].append(note)
        extra=None
        if "gainedSinceQualification" in card and number==379:
            extra=("The direct mutation controls reconstructed a shared object and two distinct objects with equal maximal int fields. "
                   "On every incompatible public Gson call the parent threw ClassCastException and the fix threw JsonSyntaxException. "
                   "The native checker also verified all five compatible selections on both builds.")
        if "gainedSinceQualification" in card and number==391:
            extra=("The separate schedule checker enumerated every completed sequentially consistent application-bytecode interleaving of the frozen two-thread callers, with successful start and join. "
                   "Both class-matched callers returned true. The mixed caller returned both false and true, each reproduced on an original JVM.")
        if extra: example["notes"].append(extra)
        files[ep]=json.dumps(example,indent=2)+"\n"
        rp=folder/"README.md";base=rp.read_text().split("\n## Measured results\n",1)[0].rstrip()
        table=["","## Measured results","",note,"","| Entry | Opening native | Qualified native |","|---|---|---|"]
        for name,row in selected_rows.items():
            table.append("| "+" | ".join([name,*["["+engine(row[s]["native"])+"]("+os.path.relpath(ROOT/row[s]["evidence"],folder)+")" for s in ("opening","final")]])+" |")
        if extra:
            table+=["",extra]
            if number==391:
                table+=["","[Instruction schedules and original JVM controls](../../verification/java-semantics-gap/monitor-schedules/measurement.json)"]
            else:
                table+=["","[Direct mutation controls](../../verification/java-semantics-gap/heap-and-gson/histories/measurement.json) · [Parent exception proof](../../verification/java-semantics-gap/heap-and-gson/gson-parent/exception-control/measurement.json) · [Fix counterexample](../../verification/java-semantics-gap/heap-and-gson/gson-fix/exception-control/measurement.json)"]
        table+=["","[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)"]
        files[rp]=base+"\n"+"\n".join(table)+"\n"
    return files


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase",choices=("final","qualified",PHASE,DECIMAL_PHASE),default=DECIMAL_PHASE)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    baseline = PHASE if args.phase == DECIMAL_PHASE else args.phase
    card=compare(baseline)
    if baseline in ("qualified", PHASE):
        qualify_companions(card)
        card["verification"]=campaign_jobs(card)
    if baseline==PHASE:
        qualify_followup(card)
    if args.phase==DECIMAL_PHASE:
        qualify_decimal_transfer(card)
    outputs={BASE/"scorecard.json":json.dumps(card,indent=1)+"\n",PAGE:render(card)}
    if baseline in ("qualified", PHASE): outputs.update(example_outputs(card))
    if "decimalTransfer" in card: outputs.update(decimal_example(card["decimalTransfer"]))
    for path,contents in outputs.items():
        if args.check: require(path.read_text()==contents,f"stale {path.name}")
        else: path.write_text(contents)
    print("38 historical and 60 original statements, with raw evidence checked")

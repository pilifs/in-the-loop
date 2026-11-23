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
from historical import FROZEN_SHA, GROUPS, benchmark, digest, freeze, selected
from standalone import LISTS

BASE = ROOT/"verification/java-semantics-gap"
PAGE = ROOT/"llm-dlc/loops/jbmc-java-semantics-gap-results.md"


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
        else: require(p["kind"]=="primitive",key+" constructed a different scalar domain")
    environment=[{"kind":"initialization","basis":"engine","text":
                  "every JDK class is initialized already, its static initializer having run and thrown nothing"}]
    if key.startswith("locals/"):
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
    for a,b in [(old,new),(before,after)]:
        require(a.keys()==b.keys(),"changed denominator")
        for key in a:
            for field in ("classes","jvm","inputClasses","oracles","expected","claim","statement"):
                require(a[key].get(field)==b[key].get(field),f"{key}: before and after differ in {field}")
    environments={}
    for stage in ("opening",phase):
        h=read(BASE/stage/"listOfArray.json")
        c=read(BASE/stage/"numbers/measurement.json")
        list_models={name+".class":h["repositoryModels"][name+".class"] for name in LISTS}
        require(len(list_models)==6,"different six-class list comparator layer")
        environments[stage]={"historicalSource":h["environment"]["commit"],"historicalJdk":h["environment"]["java"],
            "benchmarkBinaries":h["binaries"],"callerSource":c["source"],"callerChecker":c["checkerSha256"],
            "callerJdk":c["jdk"],"callerModules":c["modulesSha256"],"callerJbmc":c["jbmcSha256"],
            "callerCoreModels":c["packagedModelsSha256"],"listModels":list_models}
    return {"phase":phase,"environments":environments,"historical":{k:{"opening":old[k],"final":new[k]} for k in old},
            "subjects":{k:{"opening":before[k],"final":after[k]} for k in before},"standalone":standalone_rows(),
            "transfers":transfers(phase)}


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
FAILED_LAUNCHER = "20261123-101413-qualify-standalone-ordinary-string-and-j"
FIXED_LAUNCHER = "20261123-104830-replay-corrected-standalone-string-unico"


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
    origins=read(BASE/"origins.json")
    require(origins["graphs"].keys()==CLAIMS.keys(),"the class-origin audit must cover every graph")
    for key,g in origins["graphs"].items():
        measured=read(BASE/card["phase"]/key/"measurement.json")
        require(g["checkerSha256"]==measured["checkerSha256"] and g["source"]==measured["source"]
                and g["jdkSha256"]==measured["modulesSha256"] and g["classpath"]==measured["classpath"]
                and g["jvmChecks"]==measured["originalJvm"]["checks"]
                and g["classes"][CLAIMS[key].owner]["sha256"]==measured["classes"][CLAIMS[key].owner+".class"],
                key+" mismatched selected class evidence")
    require(origins["arrayWitnesses"]["noNullCell"]["cells"][0]=="null"
            and origins["arrayWitnesses"]["noItemCell"]["cells"][0]!="null"
            and all(v["jvm"]=="refuted" for v in origins["arrayWitnesses"].values()),"both actual array witnesses must replay")
    require(len(origins["defaultWitnesses"])==8,"missing default-method witness replay")
    card["qualifications"]={"seeds":location(seedfile),"schedule":location(heapfile),"origins":location(BASE/"origins.json"),
                          "classBindings":sum(len(g["classes"]) for g in origins["graphs"].values()),
                          "plannedArray":trace["arrayPlan"]["diagnostic"],"monitorComparator":trace["standalone"]["runs"],
                          "arrayWitnesses":origins["arrayWitnesses"],"defaultWitnesses":origins["defaultWitnesses"]}


def findings(card):
    phase=card["phase"]
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
            +link(q["origins"],"Providers, JAR entries and SHA-256 digests"),"",
            "Both packaged binary/model pairs decided the four direct numeric seed assertions, including the original double-typed MutableDouble entry. The long-bits wrapper is recorded independently. Its standalone disagreement does not change either the direct comparator result or the qualified native result. "
            +link(q["seeds"],"Direct seeds and exact numeric witnesses"),"",
            "On a fresh JVM the default-method answers are invariant under moving the replay helpers. The Ubuntu 22.04 models give the correct pair with the helpers separate and reverse both answers with them combined. The installed Ubuntu 24.04 models reverse that pattern. Crossing the two binaries with the model JARs preserves the model-dependent outcomes. The audit replayed the actual arguments of all eight failing named assertions on their original classfiles. The cause inside JBMC remains open. "
            +link(q["seeds"],"Four package pairings and two layouts")+" · "+link(q["origins"],"Original default-method replays"),"",
            f"Stock JBMC's two opposite false reference-array assertions produced a {heap['noNullCell']['length']}-cell array with a null first element and a {heap['noItemCell']['length']}-cell array with a populated first element. The original JVM reconstructed the trace cells, field values and identities and refuted both assertions. The native constructed alias control covers equal-valued distinct objects and one shared object over every initial int. The direct frontend rejects the Item[] root. Its explicit two-cell construction plan also stops because array leaves admit integral and boolean elements. "
            +ref("arrays","Direct native and constructed heaps")+" · "+link(q["schedule"],"Explicit construction plan"),"",
            f"At the unchanged read, the debugger observed 5 with the worker blocked on the very class mirror held by the caller, for both explicit and static synchronization. Holding the instance allowed the worker to write 6 before that read. JBMC's in-lock assertions returned **{m['matched']['target']['status']}** for the explicit shared class monitor, **{m['mixed']['target']['status']}** for mixed monitors and **{m['staticMethod']['target']['status']}** for the static method. The trace records JBMC's warning about the static synchronized modifier. The original joined caller has a separate row in the table. "
            +link(q["schedule"],"Actual JVM schedules, target assertion IDs and warnings"),"",
            "The packaged single-store model accepted the deliberately false incompatible-write assertion. On the original JVM the store throws ArrayStoreException and preserves the typed cell. The portable enum models also have their own standalone lookup and ordinal results. These model disagreements are distinct from the thirteen historical JBMC leads. "
            +ref("stores","Covariant-store caller")+" · "+ref("enum","Constant and exception identities"),""]
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
    ordered+=["",f"The sum of native checker times on the sixty statements was {total('opening'):.3f} s at opening and {total('final'):.3f} s at qualification. Compilation, class binding and original-JVM replays are charged separately in the job receipts. All native results use initialized JDK classes. The thread-local proofs additionally state their one-platform-thread scope."]
    return ordered+[""]


def render(card):
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
    lines[lines.index("## Historical differential"):lines.index("## Historical differential")]=findings(card)
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
            "A refutation earns credit when the actual checker input fails on a fresh original JVM. A named refusal, an incomplete bound or a witness that holds on replay stays open. Standalone columns identify the target status, reachability assertion status and accompanying failing properties. Credit requires a failing deliberately false reachability control and successful accompanying properties.","",
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
    lines+=["","## Transfer to existing ordinary callers","",
            "| Example | Frozen claim | Opening first unproved step | Final first unproved step | Ordinary result |",
            "|---|---|---|---|---|"]
    for t in card["transfers"]:
        lines.append("| "+" | ".join(map(cell,[str(t["example"]),t["task"],t["opening"] or "Decided",
                           t["final"] or "Decided",link(t["evidence"],t["status"])]))+" |")
    lines+=["","## Recount and replay","",
            "| Measurement | Historical source / checker SHA-256 prefix | Public caller source / checker SHA-256 prefix | Integrated JBMC / packaged core-model SHA-256 prefixes |",
            "|---|---|---|---|"]
    for phase in ("opening",card["phase"]):
        env=card["environments"][phase]
        lines.append(f"| {phase} | `{env['historicalSource'][:12]}` / `{env['benchmarkBinaries']['jvmcontract'][:16]}` | "
                     f"`{env['callerSource'][:12]}` / `{env['callerChecker'][:16]}` | "
                     f"`{env['callerJbmc'][:16]}` / `{env['callerCoreModels'][:16]}` |")
    if "verification" in card:
        jobs=card["verification"]
        passed=sum(r["status"]=="passed" for r in jobs.values())
        lines+=["", f"Of {len(jobs)} campaign jobs, {passed} passed. Both proof-tier conformance tests passed on the final measured source. "
                "One intermediate Unicode witness launcher failed to compile because its parameter and a local variable shared a name. "
                "The corrected launcher replayed the original witness and completed the string and deque checks. "
                +link(jobs[CONFORMANCE]["receipt"],"Final conformance")+" · "
                +link(jobs[FAILED_LAUNCHER]["receipt"],"Initial launcher failure")+" · "
                +link(jobs[FIXED_LAUNCHER]["receipt"],"Passing replacement")]
    lines+=["",
            "Run `python3 -B lib/benchmark/java-semantics-gap/scorecard.py --check` to validate the source-bound receipt digests, per-engine rows and reported totals. Each numbered example also exposes its original tasks through `examples/tools/build.py --plan NUMBER`. The campaign's `seed` command imports its checksum-verified setup JARs into the normal example cache. "
            +link(location(BASE/"scorecard.json"),"Machine-readable comparison")+" · "
            +link("llm-dlc/loops/jbmc-java-semantics-gap-brief-setup.md","Pinned artifacts and setup recipes")]
    return "\n".join(lines)+"\n"


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
        example["notes"]=[n for n in example.get("notes",[]) if not n.startswith("The campaign's ordinary native checker decided ")]
        example["notes"].append(note)
        files[ep]=json.dumps(example,indent=2)+"\n"
        rp=folder/"README.md";base=rp.read_text().split("\n## Measured results\n",1)[0].rstrip()
        table=["","## Measured results","",note,"","| Entry | Opening native | Qualified native |","|---|---|---|"]
        for name,row in selected_rows.items():
            table.append("| "+" | ".join([name,*["["+engine(row[s]["native"])+"]("+os.path.relpath(ROOT/row[s]["evidence"],folder)+")" for s in ("opening","final")]])+" |")
        table+=["","[All families and first unproved operations](../../llm-dlc/loops/jbmc-java-semantics-gap-results.md)"]
        files[rp]=base+"\n"+"\n".join(table)+"\n"
    return files


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase",choices=("final","qualified"),default="qualified")
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    card=compare(args.phase)
    if args.phase=="qualified":
        qualify_companions(card)
        card["verification"]=campaign_jobs(card)
    outputs={BASE/"scorecard.json":json.dumps(card,indent=1)+"\n",PAGE:render(card)}
    if args.phase=="qualified": outputs.update(example_outputs(card))
    for path,contents in outputs.items():
        if args.check: require(path.read_text()==contents,f"stale {path.name}")
        else: path.write_text(contents)
    print("38 historical and 60 original statements, with raw evidence checked")

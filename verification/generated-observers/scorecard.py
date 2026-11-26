"""Offline evaluator. Reconcile typed raw JVM observations with the independent historical callers."""
import argparse
from collections import Counter
from functools import cache
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEVELOPMENT = ["458","445","J16","J19","io","J06","J10","J17"]
TRANSFER = ["J14","09","06","466","484"]
EXCEPTIONS = {"earlier-change":"open","filtered-child-hypothesis":"refuted",
              "spring-projects/spring-framework#37193.1":"open","spring-projects/spring-framework#37193.3":"refuted",
              "spring-projects/spring-framework#36626.3":"refuted"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def wire(case, value, inputs):
    """Re-encode on the evaluator side only, preserving every field in the historical comparison."""
    if case=="458":
        return " ".join(v[1].split(".")[-1] if v[0]=="throws" else v[1].split(".")[-1]+"="+v[2] for v in value)
    if case=="445":
        return ",".join(f"{str(defined).lower()}/{fallback if fallback is not None else 'null'}/{calls}" for defined,fallback,calls in value)
    if case=="484":
        return " ".join("/".join("null" if x is None else str(x) for x in row) for row in value)
    if case=="466":
        samples=[]
        for rows,term,outer,cause in value:
            envelopes=", ".join(f"{text}@{ms if ms is not None else 'null'}" for text,ms in rows)
            terminal="complete" if term=="complete" else "error="+outer.rsplit(".",1)[-1]+(" cause="+cause.rsplit(".",1)[-1] if cause else "")
            samples.append("["+envelopes+"] "+terminal)
        return " / ".join(samples)
    if case=="J06":
        return "|".join(",".join(f"{name}={'dir' if directory else 'file'}:{payload}" for name,directory,payload in rows) for rows in value)
    if case=="J10":
        row,=value
        if row[0]=="write":
            require(type(row[3])==int and row[3]>=0,"missing partial writer cursor")
            return "/".join(["write",str(row[1]),row[2],row[4].rsplit(".",1)[-1]])
        require(all(exact is True for _,exact in row[1]) and row[4]==(row[2]==row[3]),"class identity or consumption differs")
        return "read/"+",".join(name for name,_ in row[1])+"/fully-consumed="+str(row[4]).lower()
    if case=="J14":
        def hits(row):
            if row==["overload-absent"]: return row[0]
            return str(row[0])+"="+",".join(k+":"+("null" if v is None else v) for k,v in row[1])
        return "|".join(map(hits,value))
    if case=="J16":
        return "|".join("/".join(map(str,row)) for row in value)
    if case=="J19":
        *states,events=value
        return "|".join("/".join(["ok" if r=="returned" else r,s,str(n)]) for r,s,n in states)+"@"+",".join(events)
    if case=="J17":
        return "/".join(map(str,[len(value),sum(r[2][0][0] for r in value),sum(r[2][1][0] for r in value),
            sum(len(r[2][1][1]) for r in value),sum(r[2][1][4] for r in value)]))
    if case=="io":
        return "/".join(str(r[1]) if r[0]=="prefix" else "R" if r[0]=="reset" else str(r[1])+"="+r[2] for r in value)
    if case=="06":
        text=inputs["text"]
        return int(value==[[text,5 if text.endswith("px") else 18,17.0]])
    if case=="09":
        row,=value
        if row[0]=="throws":
            require(row[1] in ("java.lang.ArrayIndexOutOfBoundsException","java.lang.IndexOutOfBoundsException"),"other empty-stack exception")
            return -1
        return 0 if row[1] is None else row[1]
    raise ValueError(case)


@cache
def historical(case):
    rows={}
    if case.startswith("J"):
        path=ROOT/"verification/product-behaviour/cases"/case/"physical.json"
        for row in json.loads(path.read_bytes())["observations"]:
            group=rows.setdefault((row["question"],row["side"]),[])
            group.append(row["return"])
    elif case=="io":
        path=ROOT/"verification/organic-composition/io/first/plans.zip"
        with zipfile.ZipFile(path) as z:
            for n in json.loads(z.read("cold.json"))["claims"]:
                name="preservation" if n["id"]=="preservation-ordinary" else n["id"]
                if name in ("preservation","rewinds"):
                    for side in ("old","new"):
                        rows[name,side]=[r[side]["return"] for r in n["children"]]
    elif case in ("09","06"):
        path=ROOT/"verification/beyond-jbmc/successor/scaffolds"/(case+".json.gz")
        d=json.loads(gzip.decompress(path.read_bytes()))
        for side,s in d["sides"].items():
            measured=s["direct"]["rows"]
            if case=="06":
                rows["viewport",side]=rows["earlier-change",side]=[r[1] for r in measured]
                rows["pixel",side]=[measured[0][2]]
            else:
                rows["empty",side]=[r[1] for r in measured]
                rows["populated",side]=[measured[0][2]]
    else:
        path=next((ROOT/"examples").glob(case+"-*/observations.json"))
        for row in json.loads(path.read_bytes())["deployments"]["pins"]["observations"]:
            side={"parent":"old","fix":"new"}[row["side"]]
            rows[row["id"],side]=[row["outcome"]["return"]]
    return str(path.relative_to(ROOT)),sha(path.read_bytes()),rows


def read_attempt(case, attempt, path):
    output=[]
    ref_path,ref_hash,reference=historical(case)
    with zipfile.ZipFile(path) as archive:
        @cache
        def load(member):
            return json.loads(archive.read(member))
        record=load("bundle/generation.json")
        registration=load("bundle/registration.json")
        plan=load("cold.json") if "cold.json" in archive.namelist() else {}
        nodes={n["id"]:n for n in plan.get("claims",[])}
        if record["status"]=="compiled":
            require(sha(archive.read("bundle/UpgradeProbe.java"))==record["sourceSha256"],"caller source mismatch")
            require(sha(archive.read("bundle/caller.zip"))==record["archiveSha256"],"compiled archive mismatch")
            with zipfile.ZipFile(io.BytesIO(archive.read("bundle/caller.zip"))) as classes:
                require({name:sha(classes.read(name)) for name in classes.namelist()}==record["compiled"],"wrong class members")
        seal=load("operator-policy.json")
        require(seal["excludedMarkerRead"]=="PermissionError" and not seal["predictionsVisible"] and not seal["historicalCallerVisible"], "unsealed operator")
        for q in registration["questions"]:
            name=q["id"]
            row={"case":case,"attempt":attempt,"question":name,"sideScope":q["sides"],"cohort":q["cohort"],"history":q["history"],
                 "permittedInput":"reviewed semantic history and pinned public API", "archive":str(path.relative_to(HERE)),
                 "registrationSha256":record["registration"],"generator":record["generator"],
                 "registeredCases":len(q["inputs"]), "changedSelectors":registration["changed"],
                 "reviewedEntry":registration["entry"],"boundPublicEntry":None,"requestedFields":registration["fields"],
                 "fieldMapping":record.get("fieldSources",[]),
                 "historicalReference":{"file":ref_path,"sha256":ref_hash},
                 "generated":bool(record.get("sourceSha256")),"compiled":record["status"]=="compiled",
                 "provenance":{"caller":"maintained deterministic generator", "manifests":"prepared original ordered artifacts",
                               "scopes":"materialized by product", "fixtures":record.get("fixtures",[]),
                               "compiledClasses":record.get("compiled",{}),"compilePolicy":record["compilePolicy"],
                               "callerSourceSha256":record.get("sourceSha256"),"helper":"generated from live sites" if case=="io" else "not requested"},
                 "reachedBoth":False,"fullyObserved":False,"correctlyAdjudicated":False,"finite":"open",
                 "symbolicPublicProof":"not attempted","caseAuthoredCallerLines":0,"userInterventions":0}
            row["authorship"]={"stage2":"semantic input meanings curated from the registration and the disclosed experiment",
                "recipeEngineering":("campaign-authored Java emitter in the maintained product" if record.get("recipe")
                                     else "no supported emitter in this attempt"),
                "operatorEdits":{"caller":0,"scopes":0,"manifests":0},
                "postFreezeRecipeRepair":case in {"J14","466","484"} and attempt=="final",
                "inputDefaults":{"fallback":99} if case=="445" else {},
                "modelSynthesis":False}
            if record.get("sourceSha256"):
                row["authorship"]["generatedJavaLines"]=len(archive.read("bundle/UpgradeProbe.java").splitlines())
            node=nodes.get(name)
            if node is None:
                row["firstOpenDependency"]=record.get("firstOpenDependency","original JVM runs")
                output.append(row)
                continue
            row["boundPublicEntry"]=node["entry"]
            row["finite"]=node["status"]
            row["entryBindings"]=node["entryBindings"]
            row["independentVerifier"]=plan["tools"]
            ref=node["receipt"]
            raw=archive.read(ref["path"])
            require(sha(raw)==ref["sha256"],"wrong archived JVM receipt")
            evidence=json.loads(raw)
            require(evidence.get("generatedObserver",{}).get("classes")==record["compiled"],"JVM used different caller classes")
            require(all(evidence["probeClasses"].get(member[:-6])==h for member,h in record["compiled"].items()),
                    "measured class bytes differ from the stored class archive")
            for phase in ("warm","empty"):
                if phase+".json" in archive.namelist():
                    repeat=next(n for n in load(phase+".json")["claims"] if n["id"]==name)
                    require(repeat["status"]==node["status"] and repeat["children"]==node["children"],"resumed history differs")
            row["jvmReceipt"]=ref
            row["sides"]={}
            for side in ["old","new"]:
                obs=evidence["sides"][side]
                trials=obs.get("trials",[])
                raw_values=[]
                chains=set()
                calls=[]
                for i,t in enumerate(trials):
                    values=t.get("observations",[])
                    require(len(values)==2 and values[0]==values[1] and t["qualifiedMethodEntries"]==2, "incomplete or unstable public entry")
                    value=json.loads(values[0]["return"])
                    require(wire(case,value,q["inputs"][i])==reference[name,side][i],
                            f"{case} {name} {side} {i}: differs from independent authored observation")
                    views=t["publicProjections"]
                    require(len(views)==2 and views[0]==views[1],"unstable public projection")
                    calls.append(views[0]["entryCalls"])
                    raw_values.append(views[0]["observationSha256"])
                    chains.update(tuple(c) for rep in t.get("changedBodyChains",[]) for c in rep)
                row["sides"][side]={"qualifiedHistories":len(trials),"entryCallsPerHistory":calls,
                      "rawObservationDigests":raw_values,"changedBodyChains":[list(c) for c in sorted(chains)
                         if c and c[0] in registration["changed"]], "binding":node["entryBindings"][side],
                      "dispatch":obs.get("dispatchBinding"),"profile":plan["launches"][side]["production"]["jdk"]["release"],
                      "classpath":obs["classpath"],"cache":{phase:load(phase+".json")["claims"][
                           list(nodes).index(name)]["execution"].get(side,{}).get("action")
                           for phase in ("cold","warm","empty") if phase+".json" in archive.namelist()}}
            row["reachedBoth"]=all(s["qualifiedHistories"]==len(q["inputs"]) for s in row["sides"].values())
            row["fullyObserved"]=row["reachedBoth"]
            row["correctlyAdjudicated"]=row["fullyObserved"] and row["finite"]==EXCEPTIONS.get(name,"established")
            require(row["correctlyAdjudicated"],"unexpected finite adjudication: "+name)
            if row["finite"]!="established":
                index=node["witness"] if node["witness"] is not None else node["firstOpenDependency"]
                child=node["children"][index]
                row["discrepancy"]={"input":index,"expected":json.loads(child.get("intendedChange",child["expected"])["return"]),
                    "old":json.loads(child["old"]["return"]),"new":json.loads(child["new"]["return"]),
                    "reason":"old baseline differs" if row["finite"]=="open" else "qualified fixed-side contradiction"}
            if case=="466":
                row["changedBodyLimit"]="deferred event decoding has no synchronous stack to the selected bodyToFlux call"
            output.append(row)
    return output


def totals(rows):
    stages=["generated","compiled","reachedBoth","fullyObserved","correctlyAdjudicated"]
    groups={r["case"] for r in rows}
    return {"questions":len(rows),"cases":len(groups),"fullyObservedCases":sum(
        all(r["fullyObserved"] for r in rows if r["case"]==group) for group in groups),
        **{k:sum(r[k] for r in rows) for k in stages},"finite":dict(Counter(r["finite"] for r in rows))}


def intern_identities(rows):
    """Keep the large, repeated classpath and field records once, addressed by their canonical content."""
    tables = {}
    def reference(table, value):
        key=sha(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode())
        tables.setdefault(table,{})[key]=value
        return key
    for row in rows:
        row["generatorRef"]=reference("generators",row.pop("generator"))
        row["fieldsRef"]=reference("fieldMappings",row.pop("fieldMapping"))
        provenance=row["provenance"]
        provenance["classesRef"]=reference("compiledClasses",provenance.pop("compiledClasses"))
        if "independentVerifier" in row:
            row["verifierRef"]=reference("verifiers",row.pop("independentVerifier"))
        for side in row.get("sides",{}).values():
            side["profileRef"]=reference("deploymentProfiles",
                {"profile":side.pop("profile"),"orderedClasspath":side.pop("classpath")})
    return tables


def score():
    rows=[]
    for attempt, cases, suffix in [("development",DEVELOPMENT,""),("frozen transfer",TRANSFER,"-first"),
                                   ("final",DEVELOPMENT+TRANSFER,"-clean")]:
        for case in cases:
            rows+=read_attempt(case,attempt,HERE/"receipts"/(case+suffix+".zip"))
    counts={phase:totals([r for r in rows if r["attempt"]==phase]) for phase in ("development","frozen transfer","final")}
    with zipfile.ZipFile(HERE/"receipts/io-helper.zip") as archive:
        helper=json.loads(archive.read("helper-controls.json"))
        checked=json.loads(archive.read("complete-helper.json"))
        uses={}
        for node in checked["claims"]:
            ref=node["receipt"]
            raw=archive.read(ref["path"])
            require(sha(raw)==ref["sha256"],"helper evidence changed")
            result=json.loads(raw)
            uses[node["id"]]={side:{"basis":result["helperProofs"][side]["basis"],
                    "proofDigest":result["helperProofs"][side]["proofDigest"],
                    "applications":sum(len(a["applications"]) for t in result["sides"][side]["trials"]
                                       for a in t["checkedApplications"])} for side in ("old","new")}
    with zipfile.ZipFile(HERE/"receipts/history-reach.zip") as archive:
        reach=json.loads(archive.read("reach.json"))
        for case,record in reach.items():
            row=next(r for r in rows if r["attempt"]=="final" and r["case"]==case and r["question"]==record["question"])
            raw=archive.read(case+"/"+record["receipt"]["path"])
            require(sha(raw)==record["receipt"]["sha256"],"supplemental changed-method witness differs")
            row["laterCallsInHistory"]={"archive":"receipts/history-reach.zip","receipt":record["receipt"],
                "methods":{s:sorted({hit["stack"][0] for t in trials for hit in t["withinPublicHistory"]})
                           for s,trials in record["sides"].items()}}
            if case=="466":
                row["changedBodyLimit"]="subscription-stack evidence applies to the measured invocation; independent asynchronous scheduling remains unqualified"
    def control(archive_name, member):
        with zipfile.ZipFile(HERE/"receipts"/archive_name) as archive:
            return json.loads(archive.read(member))
    spring=control("458-controls.zip","qualification-controls.json")
    graph=control("J16-controls.zip","qualification-controls.json")
    seeded=control("458-wrong-at-setup.zip","control.json")
    handoff=control("numbered-handoff.zip","handoff.json")
    require(spring["beforeEntry"]["raw"]==spring["genuine"]["raw"] and "refusal" in spring["beforeEntry"],
            "the equal-valued startup impostor acquired entry evidence")
    require(graph["freshReceiver"]["raw"]==graph["genuine"]["raw"] and "refusal" in graph["freshReceiver"],
            "the equal-valued wrong receiver acquired identity evidence")
    require("refusal" in spring["canned"] and spring["oracleOnly"]["sameRaw"] and seeded["sameRegistrationSourceAndClasses"]
            and seeded["status"]=="refuted" and seeded["fixed"]!=seeded["intendedFixed"], "numeric falsifier failed")
    require(spring["subjectMutation"]["compiled"]==spring["compiled"] and spring["subjectMutation"]["actual"]==seeded["intendedFixed"],
            "subject control did not change the independent public readback")
    require(handoff["preflight"]["toProve"]==handoff["afterResume"]["decided"]==["458","445"],"numbered handoff differs")
    identities=intern_identities(rows)
    return {"schema":"public-observer-campaign/v1","counts":counts,"identities":identities,
            "mechanismControls":{"falseQualifications":0,"plantedCallersRejected":3,
                "canned":spring["canned"]["refusal"],"beforeEntry":spring["beforeEntry"]["refusal"],
                "separateReceiver":graph["freshReceiver"]["refusal"],"oracleOnly":spring["oracleOnly"],
                "alreadyWrongAtSetup":{"status":seeded["status"],"intended":seeded["intendedFixed"],"actual":seeded["fixed"]},
                "subjectMutation":spring["subjectMutation"]["actual"],"pinnedFixture":spring["pinnedFixture"],
                "numberedHandoff":"receipts/numbered-handoff.zip"},
            "additionalSetupAttempts":[{"case":"J10","step":"older-API scaffold","status":"open",
                "missing":"original JDK 8 JAR-index closure","repair":"qualify the canonical self-only index at its original name",
                "archive":"receipts/J10-initial-index.zip"},
                {"case":"466","step":"qualify concrete response by name","status":"open",
                 "missing":"accessible public binding","repair":"bind the public interface and measure the original implementation",
                 "archive":"receipts/466-interface-lookup.zip"}],
            "coldDiscovery":{"firstDraw":{"projects":16,"publicEntryOnBoth":12,"registeredPrimariesRecovered":0},
                "secondDraw":{"projects":13,"candidateCallers":44,"registeredPrimariesRecovered":0},
                "newColdDrawPerformed":False},
            "helpers":{"eligiblePublicCases":1,"eligibleQuestions":2,"qualifiedQuestions":2,"admittedRows":helper["derived"]["rows"],
                       "qualification":uses,"falsifiers":helper["variants"],"archive":"receipts/io-helper.zip"},
            "rows":rows}


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check",action="store_true")
    ap.add_argument("--question",help="print the matching question records with source and deployment identities expanded")
    args=ap.parse_args()
    result=score()
    if args.question:
        rows=[row for row in result["rows"] if row["question"]==args.question]
        require(rows,"unknown registered question")
        for row in rows:
            tables=result["identities"]
            row["generator"]=tables["generators"][row["generatorRef"]]
            row["fieldMapping"]=tables["fieldMappings"][row["fieldsRef"]]
            row["provenance"]["compiledClasses"]=tables["compiledClasses"][row["provenance"]["classesRef"]]
            if "verifierRef" in row:
                row["verifier"]=tables["verifiers"][row["verifierRef"]]
            for side in row.get("sides",{}).values():
                side.update(tables["deploymentProfiles"][side["profileRef"]])
        print(json.dumps(rows,indent=2,ensure_ascii=False))
        raise SystemExit(0)
    data=json.dumps(result,ensure_ascii=False,indent=2)+"\n"
    p=HERE/"scorecard.json"
    if args.check:
        require(p.read_text()==data,"scorecard differs")
    else:
        p.write_text(data)
    print(json.dumps(result["counts"]))

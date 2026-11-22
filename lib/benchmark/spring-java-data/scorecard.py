"""Recount both workstreams from their hash-verified managed outputs and frozen example inputs."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "domain-foundations"))
from results import Job, layout, read, rel, sha
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import finite_check, native_selectors, route, sidecar

DEST = ROOT / "verification/spring-java-data"
OPEN = {368:"20261122-161543-spring-binder-edits-and-the-persistent-f",369:"20261122-161543-boxed-parser-values-and-independent-resu",
        370:"20261122-164312-spring-security-reachable-roles-and-publ",371:"20261122-162530-vavr-matrix-coordinates-and-ragged-rejec",
        372:"20261122-162530-spring-accessor-names-on-paired-method-m",373:"20261122-162530-first-nan-and-preserved-numbers-at-zero",
        374:"20261122-162530-spring-formatter-precedence-and-repeated",375:"20261122-162530-decimal-result-class-coefficient-scale-a"}
FINAL = {368:"20261122-164436-recheck-spring-binder-prefixes-from-ordi",
         369:"20261122-165838-qualified-prove-boxed-row-values-and-mut",
         370:"20261122-165838-qualified-check-literal-authority-subset",
         371:"20261122-165838-qualified-check-rectangular-and-ragged-i",
         372:"20261122-165839-qualified-check-record-metadata-at-the-p",
         373:"20261122-164436-check-nan-searches-with-the-historical-a",
         374:"20261122-165839-qualified-check-both-original-formatter",
         375:"20261122-165839-qualified-check-exact-decimal-runtime-ty"}
PROVIDERS = "20261122-165839-bind-the-loaded-spring-and-data-classes"
JUNIT = "20261122-162530-run-spring-s-original-formatter-preceden"
ALL_ROWS = "20261122-164436-check-every-realizable-bounded-boxed-row"
TRANSFER = "20261122-164436-price-binder-prefix-reuse-in-the-public"
TOLERANCE = "20261122-182432-prove-inclusive-positive-tolerance-on-bo"

def require(ok,what):
    if not ok: raise ValueError(what)

def managed(identifier):
    if not identifier or not layout.find_result(ROOT,identifier): return None
    job=Job(identifier)
    for p,summary in job.files.items():
        actual=job.output(p)
        require(actual.stat().st_size == summary["bytes"], f"different size for {p}")
    return job

def job_info(job):
    return {"id":job.record["id"],"status":job.record["status"],"source":job.record["sourceCommit"],"result":rel(job.folder/"result.json")}

def run_report(job,folder,stage):
    if not job:return {}
    relative=folder.relative_to(ROOT)/"records"/stage/"run.json"
    if relative not in job.files:return {}
    run=read(job.output(relative))
    require(run["job"]==job.record["id"] and run["source"]==job.record["sourceCommit"]
        and run["targetSha256"]==sha(folder/"target.json") and run.get("oracleSha256",sha(folder/"controls/table.json"))==sha(folder/"controls/table.json")
        and run["libTree"]==job.record["jvmcontract"]["libTree"] and len(run["checkerSha256"])==64,f"{folder.name}: different frozen inputs")
    return run

def public(job,folder,plan,task,run):
    root=folder.relative_to(ROOT)
    row=run["tasks"][task["id"]]
    result_path=job.output(root/row["receipt"])
    require(sha(result_path)==row["sha256"],"different ordinary receipt")
    r=read(result_path);side=task["revision"]
    execution=root/"receipts"/task["id"]/"executions"/r["attempt"]["id"]
    packet=read(job.output(execution/"attempt.json"))
    c=packet.get("checker")
    finpath=job.output(root/run["finite"]["directory"]/(task["id"]+".json"))
    finite=read(finpath);finite_check.validate_record(plan,finite)
    fin={"status":finite["status"],"receipt":rel(finpath),"inputs":finite.get("inputs"),"differences":finite.get("differences"),"reason":finite.get("reason")}
    if not c: return fin,{"status":"unresolved","workflow":rel(result_path),"firstBlocker":r["execution"].get("reason",r["conclusion"]["label"])}
    binding=c["entryBindings"][side]
    rawfile=job.output(execution/"checker.json")
    decoded=read(rawfile)["outcomes"]
    raw=decoded[0] if decoded else {}
    claim=read(folder/task["claim"])
    key=r["claim"]["statement"]["claim"]["key"]
    require(r["attempt"]["pipeline"]["jobId"]==job.record["id"] and c["commit"]==run["source"]
            and c["engine"]=="native" and c["gaps"]=="strict" and c["jvmcontract"]==run["checkerSha256"]
            and binding["subject"]==task["target"] and binding["entry"]==claim["adapter"]["entry"]
            and c["bounds"]==claim["bounds"] and c["jdkRelease"]["JAVA_RUNTIME_VERSION"]=="21.0.13+9-LTS",
            "different public native entry, runtime or checker")
    if finite["status"] != "open":
        require(finite["sourceClaim"]==key and finite["entry"]==binding["entry"] and finite["inputs"]==claim["adapter"]["cases"]
                and [a["sha256"] for a in c["classpath"][side]]==[a["sha256"] for a in finite["sides"][side]["classpath"]],"native/finite graph differs")
    status=row["status"]
    require(status==r["conclusion"]["status"] and status in ("unresolved","refuted","established"),"different workflow outcome")
    if raw:
        require(raw["stated"]["gap_mode"]=="strict" and raw["assume"]==claim["assume"] and raw["assert"]==claim["assert"],"different raw assertion")
    evidence={"status":status,"claimKey":key,"workflow":rel(result_path),"receipt":rel(rawfile),"binding":binding,
              "checkerSha256":c["jvmcontract"],"classpath":[a["sha256"] for a in c["classpath"][side]],"jdk":c["jdkRelease"]["JAVA_RUNTIME_VERSION"],
              "seconds":row["seconds"],"peakRssBytes":row["peakRssBytes"],"firstBlocker":raw.get("problem") if raw else r["conclusion"]["label"]}
    if status=="unresolved" and raw and raw["verdict"]=="unverifiable" and not packet.get("budgetExhausted"):
        from targets import workflow_refusal
        observed=workflow_refusal.measured_refusal(folder,task["id"],folder/Path(row["receipt"]).parent,r)
        require(observed and observed["job"]==job.record["id"] and observed["text"]==raw["problem"],
                "the archived native refusal does not belong to this task")
    if status=="established":
        require(raw["verdict"]=="verified" and raw["stated"]["bounds"]["complete"] and raw["stated"]["vacuity"]["status"]=="non-vacuous","incomplete establishment")
    if status=="refuted":
        rp=job.output(execution/"replay.json")
        replays=read(rp)
        replay,=replays;value=replay["sides"][side]
        require(raw["verdict"]=="violation" and replay["reproduced"] and replay["by"]=="jvm" and replay["entry"]==binding["entry"]
                and replay["claimKey"]==key and value["admitted"] and value["satisfies"] is False and value["classpath"]==evidence["classpath"]
                and value["entryClassSha256"]==binding["classSha256"] and replay["inputs"]==raw["counterexample"]["inputs"],"unqualified parent counterexample")
        evidence.update(replay=rel(rp),inputs=replay["inputs"])
    return fin,evidence

def case(n):
    folder,=(ROOT/"examples").glob(f"{n}-*")
    from domains import GRIDS, table
    entry, grid=GRIDS[n]
    table(folder,entry,grid(),check=True)
    example=read(folder/"example.json");spec=sidecar.load(folder,example)
    opening=managed(OPEN[n]);final=managed(FINAL.get(n))
    base=run_report(opening,folder,"opening");end=run_report(final,folder,"native-final" if n in (368,373) else "native-qualified")
    stages={k:job_info(j) for k,j in (("opening",opening),("nativeFinal",final)) if j}
    rows={}
    for task in spec["tasks"]:
        if task["kind"]!="prove":continue
        name=task["id"];plan=route.resolve(folder,example,spec,name);claim=read(folder/task["claim"])
        row=rows[name]={"entry":claim["adapter"]["entry"],"revision":task["revision"],"guard":claim["assume"],"bounds":claim["bounds"],
                        "statement":claim["statement"],"frozenInputs":claim["adapter"]["cases"],
                        "primary":(n!=368 or task["revision"]=="release") and (n!=369 or task["revision"]=="landed")}
        if name in base.get("tasks",{}):
            row["finite"],row["opening"]=public(opening,folder,plan,task,base)
            row["ordinary"]={k:row["opening"][k] for k in ("status","receipt","firstBlocker") if k in row["opening"]}
        if name in end.get("tasks",{}):
            item=end["tasks"][name];path=final.output(folder.relative_to(ROOT)/item["receipt"])
            checked=native_selectors.validate_result(folder,plan,path)
            require(checked["status"]==item["status"] and sha(path)==item["sha256"],"different native selector report")
            proof=read(path)
            require(proof["checker"]["sha256"]==end["checkerSha256"] and proof["checker"]["libTree"]==end["libTree"]
                    and proof["guard"]==claim["assume"] and proof["assertion"]==claim["assert"] and proof["bounds"]==claim["bounds"]
                    and [item["sha256"] for item in proof["classpath"]]==row["opening"]["classpath"],"different selector checker, graph or scope")
            row["nativeSelectors"]={**checked,"receipt":rel(path),"checkerSha256":end["checkerSha256"],"cost":end["batches"][task["revision"]]}
            if checked["status"]=="refuted":
                replay=proof["originalJVMReplay"]
                require(replay["entry"]==claim["adapter"]["entry"] and replay["claimKey"]==row["opening"]["claimKey"],
                        "selector counterexample belongs to another public entry")
                row["nativeSelectors"]["witness"]={"inputs":replay["inputs"],"values":replay["sides"][task["revision"]]["values"]}
            if row.get("ordinary",{}).get("status") not in ("refuted","established"):
                row["ordinary"]={**checked,"status":"unresolved" if checked["status"]=="open" else checked["status"],"receipt":rel(path)}
    result={"example":n,"folder":rel(folder),"stages":stages,"claims":rows}
    if n == 369:
        earlier = managed("20261122-164436-prove-boxed-row-values-and-mutation-isol")
        if earlier:
            result["superseded"] = {**job_info(earlier), "reason": "The cached return arm used a bitwise complement in place of the SAT literal's negation. The corrected paired native reference choice is measured separately."}
    if n == 370:
        infrastructure = managed("20261122-162529-spring-security-reachable-roles-and-publ")
        if infrastructure:
            result["superseded"] = {**job_info(infrastructure), "reason": "The interrupted conflicted-tree export ran no verifier. The opening job is pinned to the repaired original checker."}
    reg=folder/"records/setup/upstream-tests.json"
    if reg.is_file():result["namedUpstream"]={"record":rel(reg),"sides":{k:{field:v[field] for field in ("source","jarSha256","tests","failures","errors","skipped")} for k,v in read(reg).items()}}
    if n==371:
        path=folder/"records/setup/named-matrices.json"
        named=read(path)
        require(set(named["sides"])=={"parent","landed"} and named["sourceSha256"]==sha(folder/"controls/NamedMatrices.java") and named["jdk"]=="21.0.13+9-LTS",
                "different named Vavr controls")
        inputs=["List(List(1, 2, 3), List(4, 5, 6))","List(List(1, 2), List(3))","List(List(), List(1))","List(List(), List())"]
        for side,run in named["sides"].items():
            ragged=["List(List(1, 3), List(2))","List(List(1))"] if side=="parent" else ["java.lang.IllegalArgumentException"]*2
            expected=["List(List(1, 4), List(2, 5), List(3, 6))",*ragged,"List()"]
            require(run["rows"]==[[str(i),record,value] for i,(record,value) in enumerate(zip(inputs,expected,strict=True))]
                    and run["jarSha256"]==result["namedUpstream"]["sides"][side]["jarSha256"]
                    and run["revision"]==result["namedUpstream"]["sides"][side]["source"],"different original transpose witness")
        result["namedJVM"]={"record":rel(path),"inputs":len(inputs)}
    return result

def supplement(key, job_name, relative):
    job=managed(job_name)
    if not job:return {"job":job_name,"state":"pending"}
    path=job.output(Path(relative)/"measurement.json");data=read(path)
    out={**job_info(job),"measurement":rel(path)}
    if key=="formatter":
        import xml.etree.ElementTree as ET
        for side,value in data["sides"].items():
            xml=job.output(Path(relative)/value["xml"]);row=ET.parse(xml).getroot()
            require(sha(xml)==value["xmlSha256"] and row.get("name")=="testBindDateAnnotatedPatternWithGlobalFormat()"
                    and (row.find("failure") is not None)==(side=="parent"),"wrong upstream formatter outcome")
        out["sides"]={s:v["result"] for s,v in data["sides"].items()}
    elif key=="allRows":
        from all_rows import check
        packed=job.output(Path(relative)/"observations.jsonl.gz")
        with gzip.open(packed,"rt") as rows:groups=check(rows)
        require(data["partitions"]==groups and data["cases"]==sum(groups.values()) and sha(packed)==data["observationsSha256"],"different exhaustive row grid")
        out.update(cases=data["cases"],partitions=groups)
    else:
        from gated_transfer import check
        for name,r in data["routes"].items():
            physical=job.output(Path(relative)/(name+".jsonl"))
            require(sha(physical)==r["sha256"] and check(physical)==r["counts"],"different gated edit history")
        source=managed(data["producer"]["job"])
        binder=Path("examples/368-spring-binding-history")
        opening=read(source.output(binder/"records/opening/run.json"))
        for task,packet in data["producer"]["receipts"].items():
            p=source.output(binder/opening["finite"]["directory"]/(task+".json"))
            r=read(p)
            require(sha(p)==packet["sha256"] and r["sourceClaim"]==packet["claimKey"]
                    and r["inputs"]==packet["inputs"]==12 and r["status"]=="established",
                    "different A1 finite prefix producer")
        require(set(data["producer"]["receipts"])=={"beans-combined","ledger-combined"},"missing prefix producer")
        out.update(routes=data["routes"],producer=data["producer"],ordinaryNative=data["ordinaryNative"])
    return out

def registrar_callbacks(cases):
    """Bind the scoped theorem to the registrar class that the historical binder actually loaded."""
    job=managed("20261122-172803-check-the-original-spring-formatter-regi")
    if not job:
        return {"state":"pending"}
    folder=ROOT/cases["374"]["folder"]
    report={**job_info(job),"sides":{}}
    roots=["org.springframework.format.datetime.DateFormatter",
           "org.springframework.format.datetime.DateTimeFormatAnnotationFormatterFactory"]
    for side,sequence in (("parent",978),("landed",789)):
        base=folder.relative_to(ROOT)/"records/registrar-callbacks"/side
        path=job.output(base/"measurement.json")
        data=read(path)
        primary=cases["374"]["claims"]["annotated-"+side]["opening"]
        registrar=data["target"]["class"]
        public_graph=read(DEST/"exact-classpaths/classes.json")["374"][side]["orderedJars"]
        require(public_graph[0]["path"]=="driver.jar"
                and [item["sha256"] for item in public_graph[1:]]==primary["classpath"],
                "different original binder classpath")
        require(registrar=="org.springframework.format.datetime.DateFormatterRegistrar" and
                data["sequence"]==[9,sequence] and data["boundRelease"]==21 and data["source"]==job.record["sourceCommit"] and
                data["sourceSha256"]==sha(folder/"companions/RegistrationTrace.java") and
                data["nativeClassBindings"]=={"springwork.RegistrationTrace":data["observerClass"],
                                              registrar:primary["binding"]["subjectClassSha256"]} and
                data["runtimeJars"]==[item["sha256"] for item in public_graph] and data["jdk"]["JAVA_RUNTIME_VERSION"]==primary["jdk"],
                "different registrar or observing registry")
        log=job.output(base/data["jvm"]["stdout"])
        require(log.read_text().splitlines()==["9",str(sequence)] and not data["jvm"]["exit"],"different public registration order")
        recorded={"measurement":rel(path),"checkerSha256":data["checkerSha256"],"sequence":data["sequence"],"queries":{}}
        for label,expected_roots in (("ordinary",[]),("recorded",roots)):
            item=data["queries"][label]
            rawfile=job.output(base/item["stdout"]);raw,=read(rawfile)
            require(sha(rawfile)==item["stdoutSha256"] and item["observedRoots"]==expected_roots
                    and raw["stated"]["gap_mode"]=="strict" and raw["stated"]["checker"]["engine"]=="native"
                    and raw["target"]=="springwork.RegistrationTrace#sequence" and raw["assume"]=="code >= 0 && code <= 1"
                    and raw["assert"]==f"(code == 0 && result == 9) || (code == 1 && result == {sequence})"
                    and raw["verdict"]==item["verdict"] and raw["problem"]==item["blocker"],"different native callback claim")
            states={}
            for fact in raw["stated"]["assumptions"]:
                if fact.get("id","").startswith("observed-initializer:"):
                    _,cls,provider,state=fact["id"].split(":")
                    states[cls]=state
            require(states==item.get("states",{}),"different captured initializer states")
            if raw["verdict"]=="verified":
                require(not item["exit"] and not raw["problem"] and raw["stated"]["bounds"]["complete"]
                        and raw["stated"]["vacuity"]["status"]=="non-vacuous" and set(states)==set(expected_roots),
                        "incomplete callback establishment")
            recorded["queries"][label]={"verdict":raw["verdict"],"blocker":item["blocker"],"states":states,"receipt":rel(rawfile)}
        report["sides"][side]=recorded
    return report


def tolerance_search(cases):
    import positive_tolerance as tolerance

    job = managed(TOLERANCE)
    if not job:
        return {"state": "pending"}
    folder = tolerance.FOLDER
    report = {**job_info(job), "tolerance": 0.25, "centers": [-0.5, 0.0, 0.5],
              "cells": "Two independent binary64 words. Signaling input encodings are quieted before the public call.",
              "start": "Every signed 32-bit Java int", "sides": {}}
    for side in ("parent", "landed"):
        base = folder.relative_to(ROOT) / "records/positive-tolerance" / side
        measurement = job.output(base / "measurement.json")
        data = read(measurement)
        opening = cases["373"]["claims"]["numbers-" + side]["opening"]
        build = read(folder / f"records/setup/build-{side}.json")
        original, = build["artifacts"]
        observer = data["classes"][tolerance.ENTRY]
        bindings = {tolerance.ENTRY: observer, tolerance.SUBJECT: opening["binding"]["subjectClassSha256"]}
        sources = [tolerance.SOURCES / "ToleranceSearch.java", tolerance.SOURCES / "ToleranceReplay.java", tolerance.LOADED]
        require(data["source"] == job.record["sourceCommit"] and data["job"] == TOLERANCE
                and data["libTree"] == job.record["jvmcontract"]["libTree"]
                and data["commit"] == build["recipe"]["commit"] and data["jdk"] == opening["jdk"]
                and data["jarSha256"] == original["sha256"] == opening["classpath"][-1]
                and data["classpath"] == tolerance.CLASSPATH and data["classes"] == bindings
                and data["sources"] == {p.name: sha(p) for p in sources}
                and data["words"] == [f"{w:016x}" for w in tolerance.words()] and data["starts"] == list(tolerance.STARTS),
                "different historical tolerance subject, observer or grid")
        jvm = job.output(base / data["jvm"]["stdout"])
        require(not data["jvm"]["exit"] and sha(jvm) == data["jvm"]["stdoutSha256"]
                and jvm.read_text().splitlines() == [f"{name}\t{provider}\t{digest}" for (name, digest), provider
                                                     in zip(bindings.items(), tolerance.CLASSPATH, strict=True)],
                "different public tolerance class bindings")
        packed = job.output(base / "observations.bin.gz")
        grid = tolerance.check_grid(packed)
        require(sha(packed) == data["observationsSha256"] and grid == data["grid"], "different tolerance observations")
        query = data["native"]
        raw = job.output(base / query["stdout"])
        outcome, = read(raw)
        tolerance.check_native(outcome)
        require(sha(raw) == query["stdoutSha256"] and query["verdict"] == outcome["verdict"] and not query["exit"]
                and not query["observedRoots"] and not query["states"], "different positive-tolerance proof")
        report["sides"][side] = {"commit": data["commit"], "measurement": rel(measurement), "verdict": query["verdict"],
                                 "proof": rel(raw), "checkerSha256": data["checkerSha256"], "nativeSeconds": query["seconds"],
                                 "observations": rel(packed), "finiteGrid": grid}
    parent, landed = report["sides"].values()
    require(parent["finiteGrid"] == landed["finiteGrid"] and parent["checkerSha256"] == landed["checkerSha256"],
            "the positive-tolerance revisions have different physical outcomes or checkers")
    return report


def recount(complete):
    out={}
    for track,numbers in [("spring",(368,370,372,374)),("data",(369,371,373,375))]:
        cases={str(n):case(n) for n in numbers}
        totals={}
        rows=[r for c in cases.values() for r in c["claims"].values() if r["primary"]]
        for field in ("opening","ordinary","finite"):
            totals[field]=dict(Counter(r.get(field,{}).get("status","pending") for r in rows))
        require(len(rows)==(16 if track=="spring" else 14),"different primary denominator")
        companions=({"formatter":supplement("formatter",JUNIT,"examples/374-spring-formatter-binding/records/upstream-junit"),
                     "gatedBinding":supplement("transfer",TRANSFER,"verification/spring-java-data/gated-binding")} if track=="spring"
                    else {"allRows":supplement("allRows",ALL_ROWS,"examples/369-boxed-ragged-rows/records/all-rows")})
        if track == "spring":
            companions["registrarCallbacks"]=registrar_callbacks(cases)
        else:
            companions["positiveTolerance"]=tolerance_search(cases)
        bound=managed(PROVIDERS)
        if bound:
            source=bound.output(Path("verification/spring-java-data/public-providers/classes.json"))
            traced=read(source)
            exact=DEST/"exact-classpaths/classes.json"
            observed=read(exact)
            for n in numbers:
                folder,=(ROOT/"examples").glob(str(n)+"-*")
                from providers import CLASSES
                require(set(observed[str(n)])==set(read(folder/"target.json")["history"]["revisions"]),
                        "incomplete public classpath graphs")
                for side,graph in observed[str(n)].items():
                    prior=traced[str(n)][side]
                    ordered=graph["orderedJars"]
                    require(ordered and ordered[0]["path"]=="driver.jar" and prior["orderedJars"]==[ordered[0], *ordered]
                            and prior["ordinarySha256"]==graph["ordinarySha256"] and prior["ordinaryRows"]==graph["ordinaryRows"]
                            and set(prior["classes"])==set(graph["classes"])==set(CLASSES[n]),"different public provider traces")
                    for name,item in graph["classes"].items():
                        before=prior["classes"][name]
                        require(all(before[k]==item[k] for k in ("entry","jarSha256","classSha256"))
                                and before["jarIndex"]==item["jarIndex"]+1,"different defining classpath entry")
                    ordinary=ROOT/graph["ordinary"]
                    canonical,=[r for r in read(ordinary.parent/"execution.json")["records"] if r["revision"]==side]
                    require(ordered==[{k:item[k] for k in ("path","sha256")} for item in canonical["identities"]["classpath"]]
                            and sha(ordinary)==graph["ordinarySha256"],"different physical driver or classpath")
                    if n==370:
                        availability="absent" if side=="before" else "present"
                        observations=[json.loads(line) for line in ordinary.read_text().splitlines()]
                        require(len(observations)==32 and all(row["direct"]["api"]==availability for row in observations),
                                "the historical builder availability differs")
                    for cls,item in graph["classes"].items():
                        require(item["jarSha256"]==graph["orderedJars"][item["jarIndex"]]["sha256"]
                                and len(item["classSha256"])==64, f"wrong provider for {cls}")
                result=cases[str(n)]
                result["loadedClasses"]={"record":rel(exact),"managedComparison":rel(source),"revisions":observed[str(n)]}
            a=observed["369"]["landed"]["classes"]["org.apache.commons.lang3.math.NumberUtils"]
            b=observed["375"]["landed"]["classes"]["org.apache.commons.lang3.math.NumberUtils"]
            require((a["jarSha256"],a["classSha256"])==(b["jarSha256"],b["classSha256"]),"B1/B4 parser artifacts differ")
        if complete:
            require(bound and bound.record["status"]=="passed" and all("nativeFinal" in c["stages"] for c in cases.values()),"outstanding native or loaded-class jobs")
            for n in numbers:
                require(cases[str(n)]["stages"]["nativeFinal"]["status"]=="passed"
                        and all("nativeSelectors" in row or n==371 and row["revision"]=="landed"
                                for row in cases[str(n)]["claims"].values()),"missing qualified native comparison")
            require(all(r.get("finite",{}).get("status") in ("refuted","established") and "ordinary" in r for r in rows),"outstanding primary evidence")
            require(all(j.get("status")=="passed" for j in companions.values()),"outstanding companion evidence")
        out[track]={"schema":"spring-java-data-workstream/v1","workstream":track,"primary":len(rows),"totals":totals,"examples":cases,"companions":companions}
    return out

if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--check",action="store_true");cli.add_argument("--require-complete",action="store_true")
    args=cli.parse_args();DEST.mkdir(exist_ok=True,parents=True)
    for name,record in recount(args.require_complete).items():
        path=DEST/(name+".json");body=json.dumps(record,indent=2)+"\n"
        if args.check:require(path.read_text()==body,f"stale {name} scorecard")
        else:path.write_text(body)
        print(name,record["primary"],record["totals"])

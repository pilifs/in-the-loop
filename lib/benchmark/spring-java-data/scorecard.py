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
        out.update(routes=data["routes"],producer=data["producer"],ordinaryNative=data["ordinaryNative"])
    return out

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
        bound=managed(PROVIDERS)
        if bound:
            source=bound.output(Path("verification/spring-java-data/public-providers/classes.json"))
            observed=read(source)
            for n in numbers:
                folder,=(ROOT/"examples").glob(str(n)+"-*")
                for side,graph in observed[str(n)].items():
                    require(sha(ROOT/graph["ordinary"])==graph["ordinarySha256"],"different physical driver")
                    for cls,item in graph["classes"].items():
                        require(item["jarSha256"]==graph["orderedJars"][item["jarIndex"]]["sha256"]
                                and len(item["classSha256"])==64, f"wrong provider for {cls}")
                result=cases[str(n)]
                result["loadedClasses"]={"record":rel(source),"revisions":observed[str(n)]}
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

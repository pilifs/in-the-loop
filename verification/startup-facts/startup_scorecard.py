"""Render the campaign scorecard from the independent collector archives."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile

HERE=Path(__file__).resolve().parent


def resource_controls():
    sys.path.insert(0,str(HERE.parents[1]/"examples/tools"))
    from targets.property_reads import check_reads
    with ZipFile(HERE/"batik-resource.zip") as archive:
        rows=json.loads(archive.read("scorecard.json"))["rows"]
    tests=[]
    for row in rows:
        if row["history"]!="ordinary":
            continue
        rec=row["receipt"]
        providers=[Path(p) for p in rec["launch"]["resourceClasspath"]]
        events=rec["events"]
        check_reads(events,providers,[],Path(rec["launch"]["cwd"]))
        duplicate=next(p for p in providers[1:] if _contains(p,events[0]["entry"]))
        for name in ("later identical provider","changed loader","wrong bytes","wrong parser"):
            changed=deepcopy(events)
            if name=="later identical provider":
                changed[0]["archive"]=changed[1]["source"]["archive"]=str(duplicate)
            elif name=="changed loader":
                changed[0]["loaderClass"]="fixture.OtherLoader"
            elif name=="wrong bytes":
                changed[1]["consumedSha256"]="0"*64
            else:
                changed[1]["decoder"]="UTF-8"
            try:
                check_reads(changed,providers,[],Path(rec["launch"]["cwd"]))
            except ValueError as error:
                tests.append({"revision":row["revision"],"substitution":name,"refusal":str(error)})
            else:
                raise ValueError("accepted substituted Batik receipt: "+name)
    return tests


def _contains(path,entry):
    with ZipFile(path) as jar:
        return entry in jar.namelist()


def build():
    report={"schema":"startup-facts-campaign/v1","scope":"Original finite JVM histories and separately scoped strict native properties.",
            "development":[],"firstFrozenTransfers":[],"controls":[]}
    assistance = {
        "sc.Encoded": "registered countermodel, two requested COMPAT locale profiles",
        "Commons IO #520": "registered rewind predicate and original historical caller; CharsetPositions is the independent evaluator",
        "ThreeTenBP #77": "registered overlap predicate, historical public caller and six histories per release",
        "POI #1420": "original DataFormatter-first control, registered locale launches and six histories per release",
        "Batik lazy parser": "labelled getter, setter and retained/fresh loader fixture, with one disposable JAR replacement",
        "File and Reader decoding": "constructed file inputs, decoder and readback keys",
        "commons-configuration-565": "registered original caller and own, inherited or absent prestate",
        "commons-configuration-601": "registered original caller and own, inherited or absent prestate",
        "JavaParser": "original separator history and three registered launch settings",
        "paper 332": "original nine-case grid and a labelled boundary around the second call",
        "Spring 480": "registered caller and an explicitly authored control caching its original non-bridge override",
        "Avro 3878": "registered property, adapter, bounds, ordered runtime and pinned captured Maven build",
    }
    def load(file):
        with ZipFile(HERE/file) as archive:
            if archive.testzip() is not None: raise ValueError("corrupt archive: "+file)
            return json.loads(archive.read("scorecard.json"))
    def row(file,idx,case,revision,profile,claim,observed,admission,consumed,retry,remaining,parity,**extra):
        record = dict(case=case,revision=revision,profile=profile,claim=claim,observed=observed,admission=admission,
                      consumed=consumed,retry=retry,remaining=remaining,ordinaryJvmParity=parity,evidence=file+"#"+idx,
                      assistance=assistance[case],handEnteredStartupFacts=0,**extra)
        record.setdefault("cache","fresh original processes")
        return record
    for file,case in [("charset-small.zip","sc.Encoded"),("charset-io.zip","Commons IO #520"),("threeten-members.zip","ThreeTenBP #77")]:
        doc=load(file)
        for i,r in enumerate(doc["rows"]):
            item=r.get("record") or r["claim"]
            profile=r.get("locale") or "original JDK 21"
            if case=="sc.Encoded":
                fact=item["profile"]["canonical"]; parity=r["untouched"]
                cache={"cold":item["recording"],"warm":r["resumed"],"empty":r["emptyCache"]}
            elif case.startswith("Commons"):
                fact={"effective":item["profile"]["canonical"],"initializerReads":len(item["executed"]),
                      "constructor":r["constructor"],"encoder":r["encoder"],"publicDefaultCalls":len(r["defaultCallsInConstructor"]),"mark":r["initialMark"]}
                parity=r["instrumentedParity"];cache={"cold":item["recording"]}
            else:
                fact=item["reflectiveFields"]
                parity={"histories":len(r["publicHistories"]),"callsToCapturedMethod":sum(s["memberInvocations"] for s in r["publicHistories"])}
                cache={"cold":item["recording"]}
            report["development"].append(row(file,f"/rows/{i}",case,r["revision"],profile,item["original"]["target"],fact,
                "completed startup receipt",item["consumed"],item["retry"],item["remaining"],parity,
                initialStop=item["original"]["reason"],recordingRequest=item["initializerStop"],receipt=item["receiptId"],cache=cache))
        for c in doc.get("controls",[]): report["controls"].append({"case":case,"control":c,"evidence":file+"#/controls"})
    file="poi-tables.zip";doc=load(file)
    for i,r in enumerate(doc["cases"]):
        item=r["record"]
        for j,s in enumerate(r["histories"]):
            report["development"].append(row(file,f"/cases/{i}/histories/{j}","POI #1420",r["revision"],s["input"],item["original"]["target"],
                {"operation":s["projections"][0]["consumer"],"source":item.get("table")},item["recording"],item["consumed"],item["retry"] or "open",
                item["remaining"],s["ordinaryParity"],initialStop=item["initializerStop"],receipt=item.get("receiptId") or item.get("diagnosticId"),cache="fresh"))
    report["controls"].extend({"case":"live properties","control":c,"evidence":file+"#/controls"} for c in doc["controls"])
    for file,case in [("batik-resource.zip","Batik lazy parser"),("properties-file.zip","File and Reader decoding")]:
        doc=load(file)
        for i,r in enumerate(doc["rows"]):
            receipt=r["receipt"]
            report["development"].append(row(file,f"/rows/{i}",case,r.get("revision","fixture"),r.get("history",r.get("case")),receipt["boundary"],
                {"selected":receipt["selected"],"operations":[e["operation"] for e in receipt["events"]],"public":r["public"]},"paired finite JVM history",
                [],"finite observation",None,receipt["ordinaryParity"],receipt=receipt["id"],cache="fresh JVM"))
    file="startup-controls.zip";doc=load(file)
    report["controls"].append({"case":"scope, order and interruption","evidence":file+"#/",**doc})
    file="deployment-bindings.zip";doc=load(file)
    report["controls"].append({"case":"revision and loader admission","evidence":file+"#/",**doc})
    file="reuse-profiles.zip";doc=load(file)
    report["controls"].append({"case":"same-path replacement and restoration","evidence":file+"#/",**doc})
    for file,case in [("transfer-configuration.zip","Commons Configuration"),("transfer-timing.zip","JavaParser and 332"),
                      ("transfer-spring.zip","Spring 480"),("transfer-avro.zip","Avro 3878")]:
        doc=load(file)
        for i,r in enumerate(doc["rows"]):
            where=f"/rows/{i}"
            if "profiles" in r:
                for j,s in enumerate(r["profiles"]):
                    report["firstFrozenTransfers"].append(row(file,where+f"/profiles/{j}",r["case"],r["revision"],s["launch"],"original selector histories",
                        {"selectors":len(s["cases"]),"startupEvents":s["startup"].get("events",[])},s["startup"]["status"],[],"finite original replay",
                        s["startup"].get("reason"),s["startup"].get("ordinaryParity",False),frozenProducer=doc["frozenProducer"]))
            elif "metadataRetry" in r:
                declaration=json.loads((HERE/"spring-declaration.json").read_bytes())
                measured=next(d for d in declaration["rows"] if d["side"]==r["side"])
                if (measured["originalClassSha256"] != r["observedDeclaringClassSha256"]
                        or measured["member"]["descriptor"] != r["erasedDescriptor"]):
                    raise ValueError("cached override differs from the independently observed declaration")
                report["firstFrozenTransfers"].append(row(file,where,case,r["revision"],"cached override","registered generic return histories",
                    {"public":r["public"],"erasedDeclaration":measured["member"]},r["metadataRetry"],[],r["metadataRetry"],r["gap"],
                    r["public"]["original"]==r["public"]["cached"],frozenProducer=doc["frozenProducer"]))
            elif "task" in r:
                compact = {k:v for k,v in (r.get("record") or {}).items() if k!="actualApplicationOrder"}
                report["firstFrozenTransfers"].append(row(file,where,case,r["revision"],r["requestedRoots"],r["task"],
                    compact,"fresh capture" if r["record"] else "refused",r["consumed"],r["verdict"],r["remaining"],None,
                    historical=r["historical"],frozenProducer=doc["frozenProducer"],cache="fresh"))
            else:
                report["firstFrozenTransfers"].append(row(file,where,r["case"],r["revision"],r.get("profile",r.get("input")),"public setting and read timing",
                    r.get("actual",r.get("ordinary")),r.get("status","observed"),[],"finite original replay",r.get("reason"),r.get("ordinaryParity",False),
                    frozenProducer=doc["frozenProducer"]))
        if "retainReplaceRemove" in doc: report["controls"].append({"case":case,"evidence":file+"#/retainReplaceRemove","control":doc["retainReplaceRemove"]})
        if "variations" in doc: report["controls"].append({"case":case,"evidence":file+"#/variations","control":doc["variations"]})
    report["controls"].append({"case":"Batik source substitutions","evidence":"resource-controls.json",
                               "control":json.loads((HERE/"resource-controls.json").read_bytes())})
    report["artifacts"]={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob("*.zip"))}
    manifest=json.loads((HERE/"collector.json").read_bytes())
    collected={Path(o["path"]).name:o["sha256"] for job in manifest["jobs"] if job["status"]=="passed" for o in job["outputs"]}
    if report["artifacts"]!=collected:
        raise ValueError("campaign archives differ from the independent collector manifest")
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--check",action="store_true")
    ap.add_argument("--original-resource-controls",action="store_true")
    args=ap.parse_args()
    if args.original_resource_controls:
        print(json.dumps(resource_controls(),indent=2))
        return
    text=json.dumps(build(),ensure_ascii=True,indent=2)+"\n"
    path=HERE/"scorecard.json"
    if args.check:
        if text!=path.read_text():raise SystemExit("scorecard differs from the collector archives")
    else:path.write_text(text)
    print("startup scorecard",len(json.loads(text)["development"]),"development rows,",len(json.loads(text)["firstFrozenTransfers"]),"transfer rows")


if __name__=="__main__":main()

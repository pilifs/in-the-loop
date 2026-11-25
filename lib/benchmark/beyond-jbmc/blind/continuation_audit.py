"""Audit the original-graph resource regressions and the three-engine signed integer transfer."""
import argparse
from collections import Counter
from pathlib import Path

from successor import OUT as PANEL, compressed, digest, read, save
from scaffold_audit import collect, require, source_digest
from scores import qualified

RESOURCE=PANEL.parent/"resource-postconditions"
CODECS=PANEL.parent/"integer-codecs"
ENGINES=("native","integrated","stock")


def receipts(base,collector):
    if collector:
        collect(collector,base,"receipts.json")
    rows=read(base/"receipts.json")
    require({r["id"] for r in rows}==set(read(base/"jobs.json")) and all(r["status"]=="passed" for r in rows),"jobs incomplete")
    from history import ROOT
    for job in rows:
        for item in job["outputs"]:
            require(digest(ROOT/item["path"])==item["sha256"],"unbound collector output")
    return {j["id"]:j["source"] for j in rows}


def resources(collector):
    jobs=receipts(RESOURCE,collector)
    hist=compressed(RESOURCE/"historical-native/results.json.gz")
    require(len(hist["cases"])==len({c["id"] for c in hist["cases"]})==187 and not hist["followup"]["changed"] and
            len(hist["reference"])==25 and all(r["agrees"] for r in hist["reference"].values()) and
            digest(RESOURCE/"historical-native/executions.zip")==hist["rawExecutionsSha256"],"historical cohort differs")
    totals=Counter()
    for case in ("plain","compensating","context","index","dom4j"):
        path=RESOURCE/"measured"/case
        d=read(path/"summary.json")
        reg=RESOURCE/"registrations"/(case+".json")
        require(d["source"]==jobs[d["job"]] and digest(reg)==d["registrationSha256"]==source_digest(d["source"],reg) and
                d["checkerSha256"]==hist["binaries"]["jvmcontract"] and d["archiveSha256"]==digest(path/"executions.zip"),"resource identity differs")
        claims=read(reg)["claims"]
        require(len(claims)==6,"six registered statements expected")
        for c,r in zip(claims,d["rows"],strict=True):
            bad=[v for v in c["rows"] if v["admitted"] and not v["relation"]]
            expect="violation" if bad else "verified"
            require(c["name"]==r["name"] and r["verdict"]==expect,"different registered truth value")
            if bad:
                witness=r["counterexample"]
                require(r["replay"]=={"by":"jvm","reproduced":True} and
                        any(witness["before"]==str(v["old"]) and witness["after"]==str(v["new"])
                            and witness["inputs"][0]["value"] is v["selected"] for v in bad),"unqualified original witness")
            totals[expect]+=1
    print("resource original predicates",dict(totals),"historical",hist["followup"]["dispositions"])


def codecs(collector):
    jobs=receipts(CODECS,collector)
    comparisons=[]
    for case in ("02","lucene","protobuf"):
        child=CODECS/"discovery"/case/"candidate-1"
        reg=read(child/"registration.json")
        scaffold=read(child/"scaffold.json")
        require(scaffold["firstScaffoldStop"] is None and digest(child/"IntegerCodec.java")==reg["callerSha256"],"failed registered caller")
        loaders=compressed(CODECS/"original-loaders"/(case+".json.gz"))
        require(loaders["callerClassSha256"]==scaffold["callerClassSha256"] and
                loaders["registrationSha256"]==digest(child/"registration.json"),"different loader experiment")
        for side in ("old","new"):
            trials=loaders["sides"][side]
            require(all(trials[mode]["exit"]==0 and trials[mode]["rows"]==scaffold["sides"][side]["rows"]
                        for mode in ("direct","record")) and
                    all(trials["record"]["classProviders"].get(reg[k][0])==1 for k in ("encoder","decoder")),
                    "original defining class or observation differs")
            directory=CODECS/"matched"/case/side/"candidate-1"
            data=compressed(directory/"results.json.gz")
            require(data["source"]==jobs[data["job"]] and digest(child/"registration.json")==data["registrationSha256"]==
                    source_digest(data["source"],child/"registration.json") and digest(child/"scaffold.json")==data["originalScaffoldSha256"] and
                    data["callerSha256"]==scaffold["callerClassSha256"] and data["orderedJars"]==reg["inputs"][side] and
                    digest(directory/"executions.zip")==data["executionsSha256"],"different registered input or run")
            rows={r["method"]:qualified(r) for r in data["rows"]}
            require(set(rows)=={"primary","control","inverse","unsigned"},"missing codec predicate")
            for e in ENGINES:
                for name in ("primary","control","unsigned"):
                    verdict=rows[name][e]["disposition"]
                    inverse=rows["inverse"][e]["disposition"]
                    if verdict=="proved" and ((e=="stock" and inverse!="refuted") or inverse=="incorrect proof"):
                        rows[name][e]["disposition"]="inverse control not qualified"
            comparisons.append({"case":case,"side":side,"checker":data["checkerSha256"],"claims":rows})
    wrong=read(CODECS/"discovery/wrong/candidate-1/scaffold.json")
    require(wrong["firstScaffoldStop"] and wrong["sides"]["old"]["rows"][0]==[0,0,0] and wrong["sides"]["new"]["rows"][0]==[0,0,1],"lost false control")
    require(len({r["checker"] for r in comparisons})==1,"different numeric checker binaries")
    earlier=read(CODECS/"startup/registration.json")
    for filename, entry in (("probe.json","PublishedWidths#roundTrip"),("size32-probe.json","PublishedWidths#size32")):
        probe=read(CODECS/"startup"/filename)
        require(probe["registrationSha256"]==digest(CODECS/"startup/registration.json") and probe["entry"]==entry and
                not probe["stdout"] and "whose field UNSAFE holds" in probe["stderr"],"different startup probe")
    require(all("com/google/protobuf/CodedOutputStream" in side["initializers"]
            and len(side["observations"])==11 and all(v.endswith(" true true true false") for v in side["observations"])
            for side in earlier["sides"].values()),"Protobuf startup evidence differs")
    save(CODECS/"comparison.json.gz",comparisons)
    md=["# Signed integer codec comparison","",
        "Each release received the generated consumer qualified on both original JVMs. Every nonnegative Java int is admitted by the primary and round-trip control. The full-bit hypothesis admits every Java int. The inverse and the stock post-call false assertion were used to qualify the results.","",
        "| Deployment | Signed decode, native / integrated / stock | Round trip, native / integrated / stock | All raw bits, native / integrated / stock |",
        "|---|---|---|---|"]
    for r in comparisons:
        cells=[" / ".join(r["claims"][q][e]["disposition"] for e in ENGINES) for q in ("primary","control","unsigned")]
        md.append("| "+ " | ".join([("DSI Utilities" if r["case"]=="02" else r["case"].title())+" "+r["side"],*cells])+" |")
    md+=["","[All literal results, costs, control status and original witnesses](comparison.json.gz) · [Collected jobs](receipts.json)"]
    (CODECS/"COMPARISON.md").write_text("\n".join(md)+"\n")
    print("matched release rows",len(comparisons))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("campaign",choices=("resources","codecs"))
    p.add_argument("--collector",type=Path)
    args=p.parse_args()
    (resources if args.campaign=="resources" else codecs)(args.collector)

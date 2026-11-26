"""Assemble a per-profile scorecard from saved measurements. This reader never launches a checker or a JVM."""
from collections import Counter
import json
from pathlib import Path
import zipfile

from transfer import ROOT, OUT
from targets import change_evidence, upgrade_replay


def read(name):
    return json.loads((OUT / (name + ".json")).read_bytes())


def archived_panel():
    base = ROOT / "verification/beyond-jbmc/scaffold-first/original-plans"
    snapshots = {}
    for phase in ("first", "manifest-bound"):
        snapshot = {} if not snapshots else dict(snapshots["first"])
        for folder in sorted((base/phase).iterdir()):
            if not folder.is_dir():
                continue
            archive = folder/"plans.zip"
            metadata = json.loads((folder/"summary.json").read_bytes())
            if upgrade_replay.sha(archive) != metadata["archiveSha256"]:
                raise ValueError("historical finite baseline digest differs")
            with zipfile.ZipFile(archive) as z:
                plan = json.loads(z.read("cold.json"))
                for claim in plan["claims"]:
                    snapshot[folder.name + "/" + claim["id"]] = claim["status"]
        snapshots[phase] = snapshot
    counts = {name:dict(Counter(rows.values())) for name,rows in snapshots.items()}
    if (counts["first"].get("established"), counts["manifest-bound"].get("established")) != (22,32):
        raise ValueError("historical 32-question baseline differs")
    return counts


def main():
    rows = []
    def add(exercise,case,revision,profile,question,mode,entry=None,*,proposed=None,coverage=None,
            agreement=None,public=None,body=None,first=None,status="observed",cache="fresh",evidence=None):
        rows.append({"exercise":exercise,"case":case,"revision":revision,"profile":profile,"question":question,
                     "inputMode":mode,"inventoryCoverage":coverage,"proposedEntries":proposed,"selectedEntry":entry,
                     "jvmCheckerAgreement":agreement,"publicCallReached":public,"changedBodyReached":body,
                     "firstOpenDependency":first,"claimStatus":status,"cacheAction":cache,
                     "manualBindingInterventions":0,"evidence":evidence})
    ranking = read("log4j-first-ranking")
    inv = ranking["inventory"]
    names = [r["entry"] for r in inv["candidates"]]
    for side in ("old","new"):
        refs = [b for b in ranking["entryBindings"].values() if b["side"] == side]
        for b in refs:
            add(1,"Log4j #1173",side,"cold shortlist",b["entry"],"binary-only",b["entry"],
                proposed=[b["entry"]],coverage={"rank":names.index(b["entry"])+1,"candidates":inv["candidateCount"],
                "archiveScans":inv["coverage"]["archiveScans"]},agreement=b["status"]=="bound",status=b["status"],
                first=b.get("firstOpenDependency"),evidence="log4j-first-ranking.json")
    for r in read("log4j-replays")["rows"]:
        add(1,"Log4j #1173",r["revision"],r["profile"],r["question"],r["inputMode"],r["entry"],
            coverage={"registeredInputs":4,"qualifiedEntries":r["publicHits"],"providerIndex":r["providerIndex"]},
            agreement=True,public=True,body=True,status=r["claimStatus"],cache=r["cacheAction"],evidence="log4j-replays.json")
    for r in read("log4j-strict"):
        add(1,"Log4j #1173",r["revision"],"strict native","scheduling adapter","supplied caller",r["entry"],
            first=r["firstOpenDependency"],status="open",evidence="log4j-strict.json")
    for r in read("staged-backend"):
        for engine,trials in r["engines"].items():
            for t in trials:
                add(2,"Entry in B","fixture",r["profile"]+"/"+engine,t["assert"],"supplied entry",r["question"],
                    coverage={"providerIndex":r["entryProvider"],"resourceOrder":r["resourceOrder"]},
                    agreement=True,public=True,status=t["verdict"],evidence="staged-backend.json")
    for r in read("invoice"):
        add(2,"Invoice 312","original",r["profile"],r["question"],"supplied caller",r["question"],
            public=True,coverage={"originalTotals":r["totals"]},evidence="invoice.json")
    panel = {}
    for slot in ("03","04","08","10","13","16"):
        for r in read("panel-"+slot):
            if r["profile"]=="captured":
                panel[slot + "/" + r["question"]] = r["status"]
            add(3,"release panel "+slot,r["revision"],r["profile"],r["question"],"supplied caller",r["entry"],
                coverage={k:r[k] for k in ("declaredRoots","effectiveProviders","manifestEdges","absences")},
                agreement=r["binding"]=="bound" if r["binding"] == "bound" else None,public=bool(r["publicHits"]),
                first=r["firstOpenDependency"],status=r["status"] if r["profile"]=="captured" else r["binding"],
                cache="executed" if r["profile"]=="captured" else "binding only",evidence="panel-"+slot+".json")
    for r in read("optional"):
        for s in ("old","new"):
            add(4,"Optional manifest",s,r["profile"],r["question"],"supplied caller",r["question"],
                agreement=r["bindings"][s]=="bound",public=s in r["execution"],first=r["firstOpenDependency"],
                status=r["claimStatus"],cache=r["execution"].get(s,"open"),evidence="optional.json")
    for file in ("layouts","openjdk"):
        for r in read(file):
            add(5,"Manifest closure","fixture",r["profile"],"class and resource order","captured layout",
                coverage={k:r[k] for k in ("resourceOrder","measurements","order","edges") if k in r},
                public=True,first=r.get("firstOpenDependency"),status="observed expected refusal" if r.get("exit") else "observed",
                evidence=file+".json")
    for r in read("linkage"):
        add(6,"Lookup", "moved" if r["profile"]=="moved" else "original",r["profile"],r["question"],"supplied original client",r["question"],
            coverage={"physicalOrigins":r["origins"],"clientSha256":r["originalClientSha256"]},agreement=r["binding"]["status"]=="bound",
            public=r["observed"]=="42",first=r["binding"].get("firstOpenDependency"),status=r["observed"],evidence="linkage.json")
    for r in read("original-client"):
        add(6,"Original client",r["revision"],r["profile"],r["entry"],"supplied caller",r["entry"],
            coverage={"clientIndex":r["clientIndex"],"entryProvider":r["providerIndex"],"actual":r["actual"]},
            agreement=True,public=True,status=r["observedClaimStatus"],evidence="original-client.json")
    for r in read("inherited"):
        add(6,"Inherited declaration",r["revision"],r["profile"],r["entry"],"supplied symbolic owner",r["resolvedEntry"],
            coverage={"symbolicOwnerIndex":0,"declaringProvider":r["providerIndex"]},agreement=True,public=True,status=r["status"],
            evidence="inherited.json")
    for r in read("facade"):
        add(7,"Factory and private helper",r["revision"],"original",r["question"],r["inputMode"],r["question"],
            proposed=r["candidates"],coverage={"chain":r["chain"],"publicFactory":r["factory"]},agreement=True,public=True,body=True,
            first=r["ambiguousIntent"],status=r["claimStatus"],evidence="facade.json")
    for r in read("bridge"):
        for i,entry in enumerate(r["selectors"]):
            add(7,"Erased bridge 323",r["revision"],"wrong-type input",entry,"supplied caller",entry,
                coverage={"accessFlags":r["accessFlags"][i]},agreement=True,public=i==0,body=i==0,
                status="bridge entered" if i==0 else "cast failed before typed body",evidence="bridge.json")
    for r in read("multi-release"):
        mode,side,feature=r["profile"].split("/")
        add(8,"Gate",side,mode+"/JDK "+feature,r["binding"]["entry"],"supplied entry",r["binding"]["entry"],
            coverage={"entry":r["binding"]["physicalEntry"],"sha256":r["binding"]["classSha256"]},
            agreement=r["binding"]["status"]=="bound",public=True,status=r["binding"]["status"],first=r["binding"].get("firstOpenDependency"),
            evidence="multi-release.json")
    for filename in ("mr-proofs", "mr-guard"):
        if not (OUT/(filename+".json")).is_file():
            continue
        for r in read(filename):
            for engine, trials in r.get("actualProofs", {}).items():
                for t in trials:
                    add(8,"Gate",r["profile"].split("/")[1],r["profile"]+"/"+engine+"/"+filename,
                        "result == "+str(t["asserted"]),"supplied original member",r["binding"]["entry"],
                        coverage={"originalReturn":r["actual"],"physicalEntry":r["binding"]["physicalEntry"]},
                        public=True,status=t["verdict"],first=r["stockRoute"] if engine=="jbmc" and t["verdict"]=="unverifiable" else None,
                        evidence=filename+".json")
    if (OUT/"stock-helper-guard.json").is_file():
        for r in read("stock-helper-guard"):
            add(8,"Versioned helper","fixture",r["profile"]+"/"+r["engine"],"result == "+str(r["asserted"]) if "asserted" in r else "equivalence",
                "supplied entry",r["target"],coverage={"originalReturn":r.get("originalJvm")},public=True,
                first=r.get("firstOpenDependency"),status=r["verdict"],evidence="stock-helper-guard.json")
    for file in ("index","index-second","batik"):
        for r in read(file):
            add(9,r["slot"],r["revision"],r["profile"],"registered resource observation","binary-only",r["entry"],
                proposed=[r["entry"]],coverage={"providerIndex":r["providerIndex"],"originalTrials":r["originalTrials"],
                "actualKeys":r["registeredResourceKeys"]},public=True,status="recovered" if r["registeredQuestionRecovered"] else "alternate observation",
                first=None if r["registeredQuestionRecovered"] else "service enumeration does not reach the nominated PNG observation",evidence=file+".json")
    for r in read("resource-descriptor"):
        for side, declarations in r["declarationsBySide"].items():
            add(9,"Changed resource descriptor",side,"neutral","resource lookup","binary-only",r["entry"],
                coverage={"declarations":declarations},first=r["firstScaffoldStop"],status="open",evidence="resource-descriptor.json")
    for r in read("loaders"):
        for revision in ([r["revision"]] if "revision" in r else ["old","new"]):
            add(10,"Context loaders",revision,r["profile"],r["question"],"supplied caller",r["question"],
                coverage={"originalHistories":r.get("originalHistories"),"separateContextResources":bool(r.get("contextLoaderProfiles"))},
                public=True,first="custom child loader delegation is observed only on this invocation" if "nativeBinding" in r else None,
                evidence="loaders.json")
    held = read("parquet-first")
    shortlist=[r["entry"] for r in held["candidates"]]
    histories = {}
    for r in read("parquet-observations"):
        key = r["revision"], r["profile"], r["question"]
        histories.setdefault(key, []).append(r)
    for (revision, profile, question), group in histories.items():
        r = group[0]
        add(11,"Parquet #3638",revision,profile,question,"frozen transfer then supplied-caller qualification",r["entry"],
            proposed=shortlist,coverage={"firstScan":held["measurements"],"roots":113,"provider":r["provider"],
            "firstUnaidedRank":r["firstUnaidedRank"],"inputs":[t["input"] for t in group],
            "registeredOrderMatches":sum(t["matchesRegisteredOrder"] for t in group)},agreement=True,public=True,
            first="no supported static path from this observation to the changed reset methods" if r["firstUnaidedRank"] is None else None,
            status="original outcome matched" if all(t["matchesRegisteredOrder"] for t in group) else "order control changed the outcome",
            evidence="parquet-observations.json")
    history=read("historical-origins")
    for graph in sorted({r["graph"] for r in history["bindings"]}):
        bindings=[r for r in history["bindings"] if r["graph"]==graph]
        add(12,"Historical origins","historical",graph,"loaded application and library classes","saved original class list",
            coverage={"requested":len(bindings),"matched":sum(r["agreement"] for r in bindings)},agreement=all(r["agreement"] for r in bindings),
            status="class origins matched",evidence="historical-origins.json")
    if sum(v=="established" for v in panel.values())!=12 or set(r["exercise"] for r in rows)!=set(range(1,13)):
        raise ValueError("incomplete qualification panel")
    summary={"historicalFiniteQuestions":archived_panel(),"capturedFiniteQuestions":dict(Counter(panel.values())),
             "historicalBindings":{"graphs":history["graphs"],"matched":history["matched"],"requested":len(history["bindings"])},
             "frozenTransfer":held["measurements"],"rowsByExercise":dict(sorted(Counter(r["exercise"] for r in rows).items())),
             "statuses":dict(Counter(r["claimStatus"] for r in rows)),"rows":len(rows),
             "publicCalls":{"observedRows":sum(r["publicCallReached"] is True for r in rows),
                            "unreachedRows":sum(r["publicCallReached"] is False for r in rows),
                            "notMeasuredRows":sum(r["publicCallReached"] is None for r in rows)},
             "manualProviderIndices":sum(r["manualBindingInterventions"] for r in rows)}
    change_evidence.write_json(OUT/"scorecard.json",{"schema":"entry-discovery-scorecard/v1","counts":summary,"rows":rows})
    print(json.dumps(summary,sort_keys=True))


if __name__=="__main__":
    main()

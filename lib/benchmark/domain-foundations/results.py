"""Recount the original-claim, startup, adoption and receiver evidence without running a verifier."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "verification/domain-foundations"
sys.path.insert(0, str(ROOT / "verification"))
import layout
sys.path.insert(0, str(ROOT / "lib/benchmark/external-upgrades"))
from current_report import first_native_blocker

AVRO = "20261121-232059-domain-foundations-355-ordinary-and-obse"
PARSER = "20261121-232059-domain-foundations-360-ordinary-and-obse"
PERFORMANCE = {"354": ("truncate-fix", "20261121-232059-domain-foundations-354-larger-unsplit-di"),
               "359": ("contents-fix", "20261121-232059-domain-foundations-359-larger-unsplit-di")}
FINAL_STARTUP = {"355":"20261122-003850-confirm-final-startup-scopes-for-origina",
                 "360":"20261122-003911-confirm-javaparser-ordinary-and-observed"}
PLANNED = "20261122-003204-check-actual-no-argument-json-and-yaml-c"
BASE = "20261121-233929-check-the-prepared-avro-729-baseline-on"
DEC = "20261122-001142-prove-avro-729-decimals-and-replay-its-o"
AMBIENT = "20261122-001142-confirm-the-ordinary-avro-729-native-and"
FACT = "20261121-234701-qualify-bounded-heap-buffer-facts-across"
PRODUCERS = "20261122-001607-prove-real-avro-registration-and-writabl"


def read(p):
    return json.loads(p.read_bytes())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p):
    return p.relative_to(ROOT).as_posix()


class Job:
    def __init__(self, name):
        self.folder = layout.find_result(ROOT, name)
        if self.folder is None:
            raise ValueError(f"missing collected job {name}")
        self.record = read(self.folder / "result.json")
        if self.record["id"] != name:
            raise ValueError("wrong job identity")
        self.files = {Path(row["path"]): row for row in self.record["outputs"]}

    def output(self, path):
        p = Path(path)
        row = self.files[p]
        archive = self.folder/"outputs"/p
        found = archive if archive.is_file() else ROOT/p
        if sha(found) != row["sha256"]:
            raise ValueError(f"{found} differs from {self.record['id']}")
        return found

    def single(self, pattern):
        result, = [p for p in self.files if p.match(pattern)]
        return self.output(result)


def native(job, stage, task):
    path = job.single(f"{stage}-native/{task}/*/result.json")
    r = read(path)
    a, c, e = r["attempt"], r["conclusion"], r["evidence"]
    j = read(job.single(f"{stage}-native/{task}/executions/{a['id']}/attempt.json"))
    log = read(job.single(f"{stage}-native/{task}/executions/{a['id']}/checker.json"))
    if j["preparedClaim"] != r["claim"]["id"] or j["checker"]["engine"] != "native" or j["checker"]["gaps"] != "strict":
        raise ValueError("mismatched native evidence")
    raw, = log["outcomes"]
    if c["status"] in ("refuted", "established") and (c["vacuous"] or c["expectation"] != "yes"):
        raise ValueError("unqualified decision")
    if c["status"] == "established" and raw["stated"]["vacuity"]["status"] != "non-vacuous":
        raise ValueError("unqualified establishment")
    if c["status"] == "refuted" and (not e["counterexamples"] or e["replay"] != {"by": "jvm", "reproduced": True}):
        raise ValueError("unconfirmed counterexample")
    spec = r["claim"]["statement"]["claim"]
    folder, = (ROOT/"examples").glob(str(r["claim"]["example"])+"-*")
    if any(sha(folder/f) != lock for f,lock in r["claim"]["target"]["files"].items()):
        raise ValueError("source inputs differ from the receipt")
    return {"status": c["status"], "guard": spec["assume"], "observations": spec["observations"], "bounds": spec["bounds"],
            "startup": spec.get("observedInitializers", {}), "firstUnknown": e.get("problem"),
            "claimKey": j["claimKey"], "checker": {k:j["checker"][k] for k in ("commit","jvmcontract","jdk","libTree")},
            "checkerSeconds": j["checkerSeconds"], "receiptSeconds": a["seconds"], "budget": j["budget"],
            "satSeconds": (raw.get("search") or {}).get("native",{}).get("solving_seconds",0),
            "peakRssBytes": j["usage"]["peakRssBytes"], "receipt": rel(path)}


def finite(job, stage):
    found = {}
    for task in ("cursor-parent","cursor-fix","decimals-parent","decimals-fix"):
        path = job.single(f"{stage}-finite/*/{task}.json")
        r = read(path)
        if r["status"] != ("refuted" if task.endswith("parent") else "established") or r["inputs"] != 12:
            raise ValueError("incomplete finite adoption evidence")
        found[task] = {"status":r["status"], "inputs":r["inputs"], "sourceClaim":r["sourceClaim"], "receipt":rel(path)}
    return found


def profiles(number):
    folder, = (ROOT/"examples").glob(number+"-*")
    out = {}
    for side in ("parent","fix"):
        d = folder/"records/foundation-profiles"/side
        index = read(d/"profiles.json")
        for row in index["tables"].values():
            if sha(d / row["file"]) != row["sha256"]:
                raise ValueError("profile table changed")
        raw = DATA/"dependencies"/(number+"-"+side+".json.gz")
        dep = json.loads(gzip.decompress(raw.read_bytes()))
        if any(not p["instrumentedMatched"] or not p["matchedExpectation"] for p in index["profiles"].values()):
            raise ValueError("unconfirmed field profile")
        writes = dep["observedStaticWriters"]
        out[side] = {"profile": rel(d/"profiles.json"), "fieldInventory": rel(raw), "inventorySha256": sha(raw),
            "subject": index["provenance"]["subject"], "processProfiles": len(index["profiles"]),
            "selectedApplicationClasses": index["selectedClasses"], "declaredStatics":len(dep["staticDeclarations"]),
            "writtenStatics":len(writes), "opaqueWriteSites":sum("opaque" in s["origin"] for hits in writes.values() for s in hits),
            "wallSeconds": index["wallSeconds"]}
    return out


def startup():
    obligations = {"355": ["direct-limit-fix","full-length-fix","full-length-parent","prefix-parent","prefix-fix","bounds-fix","rejected-fix"],
                   "360": ["postorder-fix","terminal-fix","preorder-parent","preorder-fix","nonempty-parent","nonempty-fix"]}
    out = {}
    for number, jobid, conditional in [("355", AVRO, ["direct-limit-fix-writable-startup","direct-limit-parent-writable-startup","bounds-fix-lookup-startup"]),
                                      ("360", PARSER, ["postorder-fix-node-startup","postorder-parent-node-startup","postorder-fix-observed"])]:
        job = Job(jobid)
        out[number] = {"ordinary":{t:native(job,"foundation-baseline",t) for t in obligations[number]},
                       "conditional":{t:native(job,"foundation-baseline-observed",t) for t in conditional},
                       "profiles":profiles(number)}
        final = Job(FINAL_STARTUP[number])
        out[number]["finalOrdinary"] = {t:native(final,"foundation-final",t) for t in obligations[number]}
        companions = (["direct-limit-"+side+"-writable-startup" for side in ("parent","fix")] +
                      [kind+"-"+side+"-lookup-startup" for kind in ("full-length","prefix","bounds","rejected")
                       for side in ("parent","fix")] if number == "355" else
                      [kind+"-"+side+"-node-startup" for kind in ("postorder","terminal","preorder","nonempty")
                       for side in ("parent","fix")])
        out[number]["finalCompanions"] = {t:native(final,"foundation-final-observed",t) for t in companions}
        folder, = (ROOT/"examples").glob(number+"-*")
        target = read(folder/"target.json")
        for name, result in out[number]["ordinary"].items():
            task = next(t for t in target["tasks"] if t["id"] == name)
            claim = read(folder/task["claim"])
            method = claim["adapter"]["entry"].split("#")[1].split("(")[0]
            side = task["revision"]
            profile = "node-lf" if number=="360" else ("direct" if name.startswith("direct-") else "factory")
            info = read(folder/"records/foundation-profiles"/side/"profiles.json")["profiles"][profile]
            values = [int(x) for x in dict(info["observations"])[method].split(",")]
            guard = re.fullmatch(r"code >= (\d+) && code < (\d+)", result["guard"])
            if not guard:
                raise ValueError("unrecognized frozen selector bounds")
            low, high = map(int, guard.groups())
            result["publicExecution"] = {"profile":profile, "entry":claim["adapter"]["entry"],
                    "firstSelector":low, "endExclusive":high, "returned":values[low:high],
                    "bytecodeTable":out[number]["profiles"][side]["fieldInventory"]}
            if len(result["publicExecution"]["returned"]) != high - low:
                raise ValueError("incomplete entry coverage")
    return out


def repeated_decimal():
    condition, ordinary, baseline = Job(DEC), Job(AMBIENT), Job(BASE)
    rows = {}
    for name in ("cursor","decimals"):
        for side in ("parent","fix"):
            task = name+"-"+side
            current = native(condition, "decimal-startup", task+"-startup")
            rows[task] = {"baseline": native(baseline,"adoption-baseline",task),
                          "ordinary": native(ordinary,"decimal-confirmation",task), "conditional":current}
            if side == "parent":
                path = condition.single(f"records/original-witnesses/{task}/*.json")
                w = read(path)
                replay = condition.output(Path("examples/361-avro-decimal-buffer-cursor")/w["original"]["replay"])
                r = read(replay)
                if (w["original"]["observedInitializers"] or sha(replay) != w["original"]["sha256"]
                        or w["nativeSource"]["checkerSha256"] != current["checker"]["jvmcontract"]
                        or not r["reproduced"] or r["inputs"] != w["inputs"] or r["sides"]["parent"]["satisfies"] is not False
                        or r["sides"]["parent"]["admitted"] is not True):
                    raise ValueError("counterexample does not reach the original caller")
                rows[task]["original"] = {"status":"refuted","inputs":r["inputs"],"receipt":rel(path),"replay":rel(replay)}
            else:
                rows[task]["original"] = {"status":rows[task]["ordinary"]["status"]}
    return {"tasks":rows,"finiteBaseline":finite(baseline,"adoption-baseline"),"finiteCurrent":finite(ordinary,"decimal-confirmation")}


def receivers():
    historic = read(ROOT/"verification/external-upgrades/v3-scorecard.json")
    cases = {c["id"]:c for c in read(ROOT/"lib/benchmark/external-upgrades/corpus.json")["cases"]}
    results = {}
    callers = {}
    for group in range(1, 8):
        stamp = "20261122-001933" if group <= 2 else "20261122-001934"
        job = Job(f"{stamp}-confirm-receiver-targets-{group:02}-using-the-se")
        for path in job.files:
            if path.suffix != ".json":
                continue
            p = job.output(path)
            if "caller-confirmation" in path.parts:
                f = read(p)
                callers[path.stem] = {"status":f["status"],"entry":f.get("entry"),"reason":f.get("reason"),
                    "physicalInputs":len(f.get("cases",[])), "receipt":rel(p)}
                continue
            f = read(p)
            k = f["id"]
            if k in results or k not in cases:
                raise ValueError("receiver cohort identity changed")
            prev = historic["cases"][k]
            old = read(ROOT/prev["native"])
            same = {}
            for side in ("old","new"):
                a,b = old["sides"][side],f["sides"][side]
                same[side] = {"originalCommit":a.get("commit")==b.get("commit")==cases[k]["revisions"][side],
                              "callerClass":bool(a.get("callerClassSha256")) and a.get("callerClassSha256")==b.get("callerClassSha256"),
                              "orderedClasspath":bool(a.get("orderedSha256")) and a.get("orderedSha256")==b.get("orderedSha256")}
            if any(not x["originalCommit"] for x in same.values()):
                raise ValueError("different receiver source commit")
            before = old.get("nativeOverloads") or [old.get("native",{})]
            after = f.get("nativeOverloads") or [f.get("native",{})]
            results[k] = {"family":cases[k]["family"], "previousBlocker":prev["firstNativeBlocker"],
                           "currentBlocker":first_native_blocker(f), "bindings":same,
                           "before":{x.get("target",""):x.get("firstBlocker") for x in before},
                           "current":{x.get("target",""):{"reason":x.get("firstBlocker"),"verdict":(x.get("outcome") or {}).get("verdict")} for x in after},
                           "receipt":rel(p)}
    if results.keys()!=cases.keys() or set(callers)!=set(read(DATA/"baseline.json")["preselectedReceiverCases"]):
        raise ValueError("incomplete receiver cohort")
    first = [v for v in results.values() if v["previousBlocker"]=="receiver construction"]
    changed = [k for k,v in results.items() if v["previousBlocker"]=="receiver construction"
        and any(reason and "must extend Object directly" in reason and reason!=v["current"].get(t,{}).get("reason")
                for t,reason in v["before"].items())]
    left = [k for k,v in results.items() if v["previousBlocker"]=="receiver construction"
            and v["currentBlocker"] in ("parameter construction","unsupported JVM or library operation")]
    all_overloads = [entry for v in first for entry in v["current"].values()]
    # This pilot's negative count is justified only while all native overloads still stop
    # before checking a call. A newly decided or later-stage result needs scope review.
    if any(x["verdict"] not in ("unverifiable",None) or
           not (("receiver is outside the objects" in (x["reason"] or "")) or
                (x["reason"] or "").startswith("parameter ")) for x in all_overloads):
        raise ValueError("review reachability and verdict for a receiver overload that advanced")
    chosen = Job(PLANNED)
    plans = {}
    for k in ("commons-configuration-565","commons-configuration-601"):
        file = ROOT/"lib/benchmark/domain-foundations/receiver-plans"/(k+".json")
        native_path=chosen.single("planned-receivers/native/current/"+k+".json")
        physical=chosen.single("planned-receivers/jvm/"+k+".json")
        record=read(native_path)
        if record.get("constructionPlanSha256") != sha(file):
            raise ValueError("explicit constructor plan was not bound")
        plans[k] = {"choice":read(file)["before"]["nodes"][0]["maker"],"plan":rel(file),
            "native":[{"target":v["target"],"verdict":v.get("outcome",{}).get("verdict"),"reason":v.get("firstBlocker")}
                      for v in record.get("nativeOverloads") or [record["native"]]],
            "callerStatus":read(physical)["status"],"receipt":rel(native_path),"callerReceipt":rel(physical)}
    return {"population":len(results),"historicallyReceiver":len(first),"explicitPlans":plans,
            "advancedPastSuperclassRefusal":changed, "leftReceiverStage":len(left), "leftReceiverCases":left,
            "nativeReachedChangedOperation":0, "newOriginalScopeNativeVerdicts":0,
            "exactClasspathSides":sum(b["orderedClasspath"] for v in results.values() for b in v["bindings"].values()),
            "exactCallerSides":sum(b["callerClass"] for v in results.values() for b in v["bindings"].values()),
            "preselectedCallers":callers,"cases":results}


def original_scope(frozen, final):
    statuses = []
    for name, task in frozen["tasks"].items():
        if name in final:
            statuses.append(final[name]["status"])
        else:
            previous = task["current"]
            statuses.append(previous["status"] if previous["qualified"] else "unresolved")
    return dict(Counter(statuses))


def compile_report():
    historical = read(ROOT / "verification/organic-java-pr-campaign.json")
    performance = {}
    for number, (task, job_id) in PERFORMANCE.items():
        section = "cases" if number == "354" else "reserves"
        previous = historical[section][number]["tasks"][task]["current"]
        job = Job(job_id)
        performance[number] = {
            "query": native(job, "foundation-180s", task), "originalSingleQuery": previous["unsplit"],
            "workflowSeconds": read(job.single("foundation-180s-native/run.json"))["seconds"],
            "selectorCoverage": [previous["checked"], previous["admitted"]],
            "selectorCosts": previous["cost"], "selectorSatSeconds": previous["solverSeconds"],
        }
    buffer_job = Job(FACT)
    measurement = buffer_job.single("buffer-adoption/measurement.json")
    costs = read(measurement)
    if sha(buffer_job.single("buffer-adoption/sites.json")) != costs["siteEvidenceSha256"]:
        raise ValueError("changed site evidence")

    producer_job = Job(PRODUCERS)
    producers = {}
    for number in ("355", "361"):
        producers[number] = {}
        for side in ("parent", "fix"):
            evidence = producer_job.single(f"producers/{number}/{side}/evidence.json")
            claims = read(evidence)["claims"]
            for claim in claims:
                raw = producer_job.single(f"producers/{number}/{side}/" + claim["raw"])
                if sha(raw) != claim["sha256"] or read(raw)[0]["verdict"] != claim["verdict"]:
                    raise ValueError("changed producer outcome")
            producers[number][side] = {"claims": claims, "receipt": rel(evidence)}

    initialization = startup()
    adoption = repeated_decimal()
    checker_ids = {item["conditional"]["checker"]["jvmcontract"] for item in adoption["tasks"].values()}
    for number, section in (("355", "cases"), ("360", "reserves")):
        result = initialization[number]
        for scope in ("finalOrdinary", "finalCompanions"):
            checker_ids.update(row["checker"]["jvmcontract"] for row in result[scope].values())
        result["originalScope"] = original_scope(historical[section][number], result["finalOrdinary"])
    if len(checker_ids) != 1:
        raise ValueError("the final startup and adoption checks used different verifier builds")
    return {
        "schema": "domain-foundations-pilot/v1", "frozenCampaign": historical["summary"]["current"],
        "finalExecutableSha256": checker_ids.pop(), "startup": initialization, "performance": performance,
        "bufferAdoption": {"receipt": rel(measurement), **costs}, "producers": producers,
        "decimalAdoption": adoption, "receivers": receivers(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(compile_report(), indent=2, ensure_ascii=False) + "\n"
    path = DATA / "results.json"
    if args.check:
        if path.read_text() != text:
            raise SystemExit("domain foundations scorecard differs from the receipts")
        print("Domain foundations scorecard matches the original receipts")
    else:
        path.write_text(text)

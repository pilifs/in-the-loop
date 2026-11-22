"""Recount the twenty frozen obligations from the managed jobs' hash-checked outputs."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "domain-foundations"))
from results import Job, layout, read, rel, sha
sys.path.insert(0, str(HERE.parent / "organic-java"))
import upstream
from targets import finite_check, native_selectors, route, sidecar

OUTPUT = ROOT / "verification/java-domain-proof/scorecard.json"
PINS = read(HERE / "cases.json")["cases"]
OPENING_SHA = read(HERE / "opening.json")["priorProduct"]["executableSha256"]
# The named tests can qualify even when a separate artifact or public workflow failed.
JOBS = {
    "363": ("20261122-063655-qualify-363-original-artifacts-and-compl", "20261122-121129-measure-the-original-parquet-opening-cla"),
    "364": ("20261122-062459-build-and-check-364-avro-enum-namespace", "20261122-063655-qualify-364-original-artifacts-and-compl"),
    "365": ("20261122-063655-qualify-365-original-artifacts-and-compl", "20261122-121129-measure-the-original-jackson-opening-cla"),
    "366": ("20261122-062500-build-and-check-366-commons-csv-delimite", "20261122-063655-qualify-366-original-artifacts-and-compl"),
    "367": ("20261122-121129-measure-the-original-avro-fast-reader-op", "20261122-122655-bind-the-four-avro-default-opening-rows"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def upstream_tests(job, case):
    sides = {}
    for side in ("parent", "fix"):
        path = job.single(f"*-build/{side}-upstream.json")
        report = read(path)
        named = report["upstreamTest"]["named"]
        require(report["revision"] == case[side] and upstream.qualified_tests(case, side, named),
                f"{job.record['id']}: named tests differ from the pinned revision or parameters")
        archives = [job.output(p) for p in job.files if p.match(f"*-build/{side}-TEST-*.xml.gz")]
        xml = {hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest() for p in archives}
        for rows in named.values():
            require(all(r["xmlSha256"] in xml for r in rows), "missing original JUnit XML")
        sides[side] = {"revision": report["revision"], "packagingExit": report["build"]["exit"],
                       "packagingErrors": report["build"]["errors"] if report["build"]["exit"] else [],
                       "named": named, "record": rel(path), "job": job.record["id"]}
    return sides


def default_controls():
    job = Job("20261122-121129-measure-the-original-avro-fast-reader-op")
    controls = {}
    for side in ("parent", "fix"):
        path = job.single(f"replay/*/records/control-{side}-jdk21.stdout")
        expected = []
        for code, marker in enumerate(("null", "-1", "0", "1")):
            record = "{size=0, marker=" + marker + "}"
            for fast in ("false", "true"):
                for is_json in ("false", "true"):
                    union = "org.apache.avro.AvroRuntimeException" if side == "parent" and fast == "true" else record
                    expected.append(f"{code} {fast} {is_json} {union} {record} org.apache.avro.AvroTypeException")
        require(path.read_text().splitlines() == expected, "wrong fast, standard, JSON or missing-field control")
        controls[side] = {"vectors":len(expected), "observationsPerVector":["union", "direct", "required"],
                          "markers":[None,-1,0,1], "encodings":["binary","JSON"], "readers":["standard","fast"],
                          "missingRequiredField":"org.apache.avro.AvroTypeException","receipt":rel(path)}
    return controls


def public_result(job, base, run, folder, task, claim):
    name, side = task["id"], task["revision"]
    workflow = run["claims"][name]
    path = job.output(base / workflow["receipt"])
    result = read(path)
    execution = base / name / "executions" / result["attempt"]["id"]
    journal = read(job.output(execution / "attempt.json"))
    raw, = read(job.output(execution / "checker.json"))["outcomes"]
    proof = journal["checker"]
    statement = result["claim"]["statement"]["claim"]
    concluded, evidence = result["conclusion"], result["evidence"]
    entry = proof["entryBindings"][side]
    require(result["attempt"]["pipeline"]["jobId"] == job.record["id"] and
            journal["preparedClaim"] == result["claim"]["id"] and
            statement["key"] == journal["claimKey"] and
            all(sha(folder / p) == h for p, h in result["claim"]["target"]["files"].items()),
            f"{name}: execution or frozen claim inputs differ")
    require(proof["engine"] == "native" and proof["gaps"] == raw["stated"]["gap_mode"] == "strict"
            and entry["subject"] == task["target"] and entry["entry"] == claim["adapter"]["entry"]
            and proof["commit"] == job.record["sourceCommit"] == run["sourceCommit"]
            and proof["jvmcontract"] == run["checkerSha256"] and proof["libTree"] == run["libTree"]
            and proof["jdkRelease"]["JAVA_RUNTIME_VERSION"] == "21.0.13+9-LTS"
            and statement["observations"] == claim["observations"] and raw["assume"] == claim["assume"]
            and raw["assert"] == claim["assert"] and proof["bounds"] == claim["bounds"]
            and not (statement.get("observedInitializers") or statement.get("boundEnvironment")),
            f"{name}: different engine, artifact, startup, or public statement")
    status = concluded["status"]
    witness = None
    require(workflow["status"] == status and status in ("established", "refuted", "unresolved"), name)
    if status != "unresolved":
        require(not concluded["vacuous"] and concluded["expectation"] == "yes" and
                status == task["expected"], f"{name}: unqualified native decision")
    if status == "established":
        require(raw["verdict"] == "verified" and raw["stated"]["bounds"]["complete"] and
                raw["stated"]["vacuity"]["status"] == "non-vacuous", "incomplete establishment")
    if status == "refuted":
        replay, = read(job.output(execution / "replay.json"))
        observed = replay["sides"][side]
        require(evidence["counterexamples"] and evidence["replay"] == {"by": "jvm", "reproduced": True}
                and replay["claimKey"] == journal["claimKey"] and replay["entry"] == entry["entry"]
                and replay["jdkRelease"] == proof["jdkRelease"] and observed["admitted"]
                and observed["satisfies"] is False and observed["entryClassSha256"] == entry["classSha256"]
                and observed["classpath"] == [c["sha256"] for c in proof["classpath"][side]],
                f"{name}: missing admitted original-JVM counterexample")
        witness = {"input": replay["inputs"], "values": observed["values"], "receipt": rel(job.output(execution / "replay.json"))}
    finite_path = job.output(base / "finite" / (name + ".json"))
    finite = read(finite_path)
    example = read(folder / "example.json")
    plan = route.resolve(folder, example, sidecar.load(folder, example), name)
    finite_check.validate_record(plan, finite)
    require(finite["sourceClaim"] == journal["claimKey"] and finite["entry"] == entry["entry"] and
            finite["inputs"] == claim["adapter"]["cases"] and finite["status"] == task["expected"] and
            finite["sides"][side]["commit"] == PINS[run["example"]][side] and
            finite["jdkRelease"] == proof["jdkRelease"], f"{name}: different finite claim")
    decision = status
    decision_receipt = rel(path) if status in ("established", "refuted") else None
    partition = None
    selected = run.get("selectors", {}).get(name)
    if selected:
        result_path = job.output(base / selected["receipt"])
        checked = native_selectors.validate_result(folder, plan, result_path)
        data = read(result_path)
        require(status == "unresolved" and checked["status"] == selected["status"] and
                data["checker"]["sha256"] == run["checkerSha256"] and data["JDK"] == proof["jdkRelease"]
                and [v["sha256"] for v in data["classpath"]] == [v["sha256"] for v in proof["classpath"][side]],
                f"{name}: the partition changed the checker, artifacts or public scope")
        if checked["status"] in ("established", "refuted"):
            decision = checked["status"]
            decision_receipt = rel(result_path)
            if decision == "refuted":
                replay = data["originalJVMReplay"]
                witness = {"input": replay["inputs"], "values": replay["sides"][side]["values"], "receipt": decision_receipt}
        partition = {**checked, "record":rel(result_path), "cost":data["cost"], "wallSeconds":data["wallSeconds"],
                     "witness":(data.get("originalJVMReplay") or {}).get("inputs")}
    return {"status": decision, "symbolicStatus":status, "nativePartition":partition,
            "firstBlocker": evidence["problem"] if decision == "unresolved" else None,
            **({"symbolicBlocker": evidence["problem"]} if decision != status else {}),
            "decisionReceipt": decision_receipt, "gapSites": (raw.get("search") or {}).get("gaps", []),
            "binding": entry, "engineAssumptions": raw["stated"]["assumptions"], "claimKey": journal["claimKey"],
            "wallSeconds": workflow["seconds"], "peakRssBytes": workflow["peakRssBytes"],
            "checkerSeconds": journal["checkerSeconds"], "checkerPeakRssBytes": journal["usage"]["peakRssBytes"],
            "checkerBudgetSeconds": journal["budget"]["checkerSeconds"], "witness": witness, "receipt": rel(path),
            "finite": {"status": finite["status"], "inputs": finite["inputs"], "differences": finite["differences"],
                       "seconds": finite["wallSeconds"], "receipt": rel(finite_path)}}


def stage(job_id, folder, tasks, stage_name):
    if not job_id or layout.find_result(ROOT, job_id) is None:
        return {"state": "pending", "job": job_id, "claims": {}}
    job = Job(job_id)
    spec = read(ROOT / job.record["job"]["path"])
    require(spec == job.record["job"]["spec"] and
            hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest() == job.record["job"]["sha256"],
            "different managed job definition")
    paths = [p for p in job.files if p.parent.name.startswith(stage_name) and p.name == "run.json"]
    if not paths:
        return {"state": "blocked", "job": job_id, "jobResult": rel(job.folder / "result.json"),
                "reason": job.record["summary"], "claims": {}}
    path, = paths
    run = read(job.output(path))
    number = folder.name[:3]
    require(run["example"] == number and run["stage"] == path.parent.name and run["inventory"] == 2,
            f"{job_id}: wrong measurement")
    if stage_name == "opening":
        require(run["checkerSha256"] == OPENING_SHA and
                run["fingerprint"] == read(HERE / "opening.json")["engineAndWorkflowSha256"], "opening verifier drift")
    claims = {t["id"]: public_result(job, path.parent, run, folder, t, read(folder / t["claim"]))
              for t in tasks if t["id"] in run["claims"]}
    return {"state": "measured" if len(claims) == len(tasks) else "partial", "job": job_id,
            "jobResult": rel(job.folder / "result.json"), "source": run["sourceCommit"],
            "checkerSha256": run["checkerSha256"], "fingerprint": run["fingerprint"], "builds": run["artifacts"],
            "record": rel(job.output(path)), "claims": claims}


READER_JOBS = {"364":"20261122-124846-trace-and-check-the-original-avro-reader",
               "367":"20261122-124847-check-367-fast-reader-producers-and-call"}
TRANSFER_JOB = "20261122-123429-price-the-avro-buffer-fact-at-the-parque"


def reader_evidence(number, primary):
    job = Job(READER_JOBS[number])
    out = {"job":job.record["id"], "result":rel(job.folder/"result.json"), "sides":{}}
    for side in ("parent","fix"):
        found = [p for p in job.files if p.match(f"reader-foundations/{side}/measurement.json")]
        if not found:
            out["sides"][side] = {"blocker":job.record["summary"],"proofs":{}}
            continue
        base = found[0].parent
        path = job.output(found[0])
        data = read(path)
        binding = data["binding"]
        build = ROOT / binding["build"]
        require(data["checker"] == primary["checkerSha256"] and binding["revision"] == PINS[number][side]
                and sha(build) == binding["buildSha256"] == primary["builds"][side]
                and binding["orderedJars"] == [a["sha256"] for a in read(build)["artifacts"]],
                "reader producer changed verifier, revision or ordered build artifacts")
        proofs = {}
        for name, p in data["proofs"].items():
            body = job.output(base / p["stdout"])
            require(sha(body) == p["stdoutSha256"], "different producer outcome")
            stderr = job.output(base / p["stderr"])
            require(sha(stderr) == p["stderrSha256"], "different producer diagnostic")
            if p["verdict"] != "unavailable":
                raw, = read(body)
                require(raw["verdict"] == p["verdict"] and raw["target"] == p["target"]
                        and raw["problem"] == p["blocker"] and raw["assume"] == p["guard"]
                        and raw["assert"] == p["assertion"] and raw["stated"]["gap_mode"] == "strict"
                        and raw["stated"]["checker"]["engine"] == "native", "different reader proof")
                if raw["verdict"] == "verified":
                    require(raw["stated"]["vacuity"]["status"] == "non-vacuous" and raw["stated"]["bounds"]["complete"]
                            and set(p["states"]) == set(p["observedRoots"]), "unqualified producer")
            proofs[name] = {k:p[k] for k in ("target", "guard", "assertion", "verdict", "blocker", "bounds",
                                               "observedRoots", "seconds", "peakRssBytes")}
            proofs[name].update(states=p.get("states",{}), premises=p.get("assumptions",[]), receipt=rel(body))
        traces = data.get("callSites")
        targets = {}
        if traces:
            for route in ("ordinary","traced"):
                require(sha(job.output(base/traces[route]["stdout"])) == traces[route]["stdoutSha256"],
                        "different traced reader events")
            for row in traces["rows"]:
                selector = row["input"]
                if number == "364" and row["value"] in ("A","B"):
                    required = (str(2*(selector%2)), str(selector%2), "org.apache.avro.io.BinaryDecoder#readEnum()I")
                elif number == "367" and row["value"] == "1" and selector:
                    # A union tag of zero can precede a zero marker in a different
                    # decoder. The marker must be read by the fast integer reader.
                    required = (str((1,0,2)[selector-1]), str(selector-2),
                                "org.apache.avro.io.FastReaderBuilder#lambda$getReaderForBaseType")
                else:
                    required = None
                if required:
                    wire, value, caller = required
                    require(any(s["owner"] == "org.apache.avro.io.BinaryDecoder" and s["argument"] == wire and
                                s["result"] == value and s["caller"].startswith(caller) for s in row["sites"]),
                            "missing enum ordinal or integer marker at the original call site")
                for site in row["sites"]:
                    code, pool = site["codeAndPool"].split("/")
                    target = targets.setdefault(site["owner"], {"codeSha256":code, "poolSha256":pool, "callers":[]})
                    require((code,pool) == (target["codeSha256"],target["poolSha256"]), "ambiguous reader producer")
                    if site["caller"] not in target["callers"]:
                        target["callers"].append(site["caller"])
        out["sides"][side] = {"binding":data["binding"],"providers":data["providers"],"jdkModules":data["jdkModules"],
                              "producerClass":data["producerClass"],"callSiteRows":len(traces["rows"]) if traces else 0,
                              "proofs":proofs,"tracedTargets":targets,"measurement":rel(path)}
    return out


def transfer_evidence(primary):
    job = Job(TRANSFER_JOB)
    out = {"job":job.record["id"],"result":rel(job.folder/"result.json"),"experimentStatus":job.record["status"]}
    docs = [p for p in job.files if p.match("parquet-transfer/measurement.json")]
    if not docs:
        out["blocker"] = job.record["summary"]
        return out
    path = job.output(docs[0])
    data = read(path)
    require(data["checkerSha256"] == primary["checkerSha256"], "different downstream checker")
    for name in ("disabled","reuse"):
        route = data["routes"][name]
        actual = job.output(docs[0].parent / name / route["publicWorkflow"]["receipt"])
        public = read(actual)
        require(public["claim"]["statement"]["task"] == "extent-fix" and
                public["attempt"]["tools"]["jvmcontract"] == data["checkerSha256"],"wrong downstream public claim")
    routes = {}
    for name,r in data["routes"].items():
        routes[name] = {k:r[k] for k in ("seconds","smallProofOrValidationSeconds","siteSeconds","peakRssBytes")}
        if name != "clean":
            routes[name].update(wideProofSeconds=r["wideProof"]["seconds"], publicSeconds=r["publicWorkflow"]["seconds"],
                                publicStatus=r["publicWorkflow"]["status"], endToEndSeconds=r["endToEndSeconds"])
    out.update(measurement=rel(path), routes=routes, maximumBacking=data["maximumBacking"],
               valueWrapsWithinTwenty=len(data["valueWrapsWithinTwenty"]),
               metadataWrapsWithinTwenty=len(data["metadataWrapsWithinTwenty"]),
               historicalCertificate=data["historicalCertificate"],usedCertificate=data["usedCertificate"],
               directHistoricalReuse=data["directHistoricalReuse"],invalidations=data["invalidations"],
               readOnlyChild=data["readOnlyChild"]["verdict"],readOnlyBlocker=data["readOnlyChild"]["firstBlocker"],
               checkerImportsCertificate=data["checkerImportsCertificate"])
    raw_child=job.output(docs[0].parent/"read-only-child.native.json")
    require(sha(raw_child)==data["readOnlyChild"]["proofSha256"],"different read-only proof")
    out["readOnlyReceipt"]=rel(raw_child)
    out["serialized"]={}
    for side in ("parent","fix"):
        paths=[p for p in job.files if p.match(f"serialized-{side}/measurement.json")]
        if paths:
            d=read(job.output(paths[0]))
            out["serialized"][side]={}
            for name,r in d["proofs"].items():
                raw=job.output(paths[0].parent/r["stdout"])
                require(sha(raw)==r["stdoutSha256"],"different serialized companion result")
                out["serialized"][side][name]={"verdict":r["verdict"],"blocker":r["blocker"],"receipt":rel(raw)}
    return out


def input_segments(number, job_id, primary):
    job = Job(job_id)
    results = {}
    for p in job.files:
        if p.name != "experiment.json" or "input-segmentation" not in p.parts:
            continue
        path = job.output(p)
        data = read(path)
        side = data["side"]
        require(data["checker"] == primary["checkerSha256"] and data["binding"]["revision"] == PINS[number][side],
                "different verifier or JAR for parser companion")
        rows = [json.loads(line) for line in job.output(p.parent/"controls.stdout").read_text().splitlines()]
        table = read(ROOT/"examples"/PINS[number]["folder"]/"controls/table.json")["cases"]
        require(len(rows) == len(table), "incomplete parser control grid")
        require(sha(ROOT/data["ordinaryReceipt"]) == data["ordinarySha256"], "changed primary control stream")
        original = [json.loads(line) for line in (ROOT/data["ordinaryReceipt"]).read_text().splitlines()]
        for field in table[0]["expected"]:
            require([r["id"] for r,t in zip(rows,table,strict=True) if r["direct"][field] != t["expected"][field]]
                    == data["differencesFromOracle"][field], "incorrect parser oracle comparison")
            require([r["id"] for r,o in zip(rows,original,strict=True) if r["direct"][field] != o["direct"][field]]
                    == data["differencesFromOriginalCaller"][field], "incorrect input-source comparison")
        proofs={}
        for name,r in data["proofs"].items():
            raw_path=job.output(p.parent/r["stdout"])
            require(sha(raw_path)==r["stdoutSha256"], "different parser companion proof")
            raw,=read(raw_path)
            require(raw["verdict"]==r["verdict"],"different parser verdict")
            witness = None
            if raw["verdict"]=="violation" and name in data["differencesFromOracle"]:
                inputs = raw["counterexample"]["inputs"]
                if len(inputs)==1 and inputs[0]["value"] in data["differencesFromOracle"][name]:
                    witness=inputs
            proofs[name]={"verdict":r["verdict"],"blocker":r["blocker"],"receipt":rel(raw_path),
                          "matchingPhysicalRow":witness,"seconds":r["seconds"],"peakRssBytes":r["peakRssBytes"]}
        results.setdefault(side,{})[str(data["cap"]) if data["cap"] else "explicit-context"] = {
            "rows":data["rows"],"differencesFromOracle":data["differencesFromOracle"],
            "differencesFromOriginalCaller":data["differencesFromOriginalCaller"],"proofs":proofs,"measurement":rel(path)}
    return {"job":job_id,"result":rel(job.folder/"result.json"),"sides":results}


def selector_price(primary):
    name="20261122-125536-price-checked-avro-reuse-on-the-decided"
    if layout.find_result(ROOT,name) is None:
        return {"job":name,"state":"pending"}
    job=Job(name)
    paths=[p for p in job.files if p.match("parquet-selector-transfer/measurement.json")]
    if not paths:
        return {"job":name,"state":job.record["status"],"blocker":job.record["summary"],"result":rel(job.folder/"result.json")}
    path=paths[0]; info=read(job.output(path))
    require(info["checkerSha256"]==primary["checkerSha256"],"different checker on priced public claim")
    folder=ROOT/"examples"/PINS["363"]["folder"]
    ex=read(folder/"example.json")
    plan=route.resolve(folder,ex,sidecar.load(folder,ex),"extent-fix")
    priced={}
    for label in ("disabled","reuse"):
        r=info["routes"][label]; public=r["publicWorkflow"]
        receipt=job.output(path.parent/label/public["receipt"])
        checked=native_selectors.validate_result(folder,plan,receipt)
        require(checked["status"]=="established" and checked["checked"]==64 and
                public["checker"]==info["checkerSha256"],"unqualified downstream transfer")
        priced[label]={"publicStatus":checked["status"],"admitted":checked["admitted"],
                       "endToEndSeconds":r["endToEndSeconds"],"callSiteSeconds":r["siteSeconds"],
                       "validationSeconds":r["smallProofOrValidationSeconds"],"wideProofSeconds":r["wideProof"]["seconds"],
                       "publicWorkflowSeconds":public["seconds"],"publicCheckerSeconds":public["checkerWallSeconds"],
                       "peakRssBytes":max(public["peakRssBytes"],r["peakRssBytes"]),"receipt":rel(receipt)}
    return {"job":name,"state":"measured","result":rel(job.folder/"result.json"),"measurement":rel(job.output(path)),
            "routes":priced,"cleanProducerSeconds":info["routes"]["clean"]["seconds"],
            "recertificationSeconds":info["routes"]["clean"]["smallProofOrValidationSeconds"],
            "directHistoricalReuse":info["directHistoricalReuse"],"checkerImportsCertificate":False}


def enum_foundations(primary):
    name="20261122-125537-qualify-avro-enum-actions-and-the-utf8-d"
    if layout.find_result(ROOT,name) is None:
        return {"job":name,"state":"pending"}
    job=Job(name); sides={}
    for p in job.files:
        if not p.match("enum-producers/*/measurement.json"):
            continue
        data=read(job.output(p))
        require(data["checker"]==primary["checkerSha256"] and data["revision"]==PINS["364"][p.parent.name],
                "different enum checker or original revision")
        results={}
        for label,v in data["proofs"].items():
            raw_path=job.output(p.parent/v["stdout"])
            require(sha(raw_path)==v["stdoutSha256"],"different enum proof")
            results[label]={k:v.get(k) for k in ("verdict","blocker","states","observedRoots","guard","seconds","peakRssBytes")}
            results[label]["receipt"]=rel(raw_path)
        sides[p.parent.name]=results
    return {"job":name,"state":job.record["status"],"result":rel(job.folder/"result.json"),"sides":sides}


def foundation_results(result):
    readers = {}
    for n, job in READER_JOBS.items():
        primary = result["cases"][n]["finalRun"]
        if primary.get("checkerSha256") and layout.find_result(ROOT, job):
            readers[n] = reader_evidence(n, primary)
    public = result["cases"]["363"]["finalRun"]
    transfer = (transfer_evidence(public) if public.get("checkerSha256") and layout.find_result(ROOT, TRANSFER_JOB)
                else {"job":TRANSFER_JOB,"experimentStatus":"pending"})
    comparison = {}
    if len(readers) == 2:
        for side in ("parent","fix"):
            first, later = [readers[n]["sides"][side] for n in ("364","367")]
            if "providers" not in first or "providers" not in later:
                continue
            comparison[side] = {"sameProducerClass":first["producerClass"] == later["producerClass"],
                                "sameJdkModules":first["jdkModules"] == later["jdkModules"],
                                "sameOrderedJars":first["binding"]["orderedJars"] == later["binding"]["orderedJars"],
                                "sameProviderClass":{n:c["class"] == later["providers"][n]["class"]
                                                     for n,c in first["providers"].items()},
                                "tracedMethods":{n:{"sameCode":v["codeSha256"] == later["tracedTargets"][n]["codeSha256"],
                                                     "sameConstantPool":v["poolSha256"] == later["tracedTargets"][n]["poolSha256"]}
                                                 for n,v in first["tracedTargets"].items() if n in later["tracedTargets"]},
                                "checkedAgain":sorted(first["proofs"].keys() & later["proofs"].keys())}
    segments={}
    for number,job in (("365","20261122-124440-jackson-logical-offsets-with-an-explicit"),
                       ("366","20261122-124440-csv-short-reads-at-three-reader-caps")):
        primary=result["cases"][number]["finalRun"]
        if primary.get("checkerSha256") and layout.find_result(ROOT,job):
            segments[number]=input_segments(number,job,primary)
    return {"readers":readers,"avroClasspathComparison":comparison,"parquet":transfer,
            "selectorTransfer":selector_price(public),"enumActions":enum_foundations(result["cases"]["364"]["finalRun"]),
            "inputSegmentation":segments}


NAME_JOB = "20261122-133607-prove-the-name-validation-consumer-on-fo"


def name_checks(job, base, results, number):
    from name_validation import QUERIES

    expected = set(QUERIES) if number == "367" else {"names", "twoAscii"}
    require(set(results) == expected, "incomplete name-validation queries")
    checked = {}
    for label, item in results.items():
        target, guard, (unwind, array_limit) = QUERIES[label]
        path = job.output(base / item["stdout"])
        raw, = read(path)
        stated = raw["stated"]
        require(sha(path) == item["stdoutSha256"] and raw["target"] == item["target"] == target
                and raw["assume"] == item["guard"] == guard and raw["assert"] == item["assertion"] == "result == 1"
                and stated["checker"]["engine"] == "native" and stated["checker"]["fallback"] is None
                and stated["gap_mode"] == "strict" and not item["observedRoots"]
                and item["verdict"] == raw["verdict"] and item["blocker"] == raw["problem"]
                and item["bounds"] == [unwind, array_limit]
                and stated["bounds"]["unwind"] == unwind and raw["search"]["max_array_length"] == array_limit,
                f"{number}/{label}: different name-validation evidence")
        if raw["verdict"] == "verified":
            require(item["exit"] == 0 and stated["bounds"]["complete"] and stated["vacuity"]["status"] == "non-vacuous"
                    and not raw["problem"] and {(a["basis"], a["kind"], a["text"]) for a in stated["assumptions"]} ==
                    {("stated", "precondition", guard), ("engine", "initialization",
                     "every JDK class is initialized already, its static initializer having run and thrown nothing")},
                    "name validation needs an additional assumption or a complete proof")
        checked[label] = {"target": target, "guard": guard, "verdict": raw["verdict"], "firstBlocker": raw["problem"],
                          "seconds": item["seconds"], "peakRssBytes": item["peakRssBytes"], "receipt": rel(path)}
    return checked


def name_validation_evidence(cases, readers):
    from name_validation import FIELDS, policy_sites

    if not layout.find_result(ROOT, NAME_JOB):
        return {"job": NAME_JOB, "state": "pending"}
    job = Job(NAME_JOB)
    result = {"job": NAME_JOB, "state": job.record["status"], "result": rel(job.folder / "result.json"),
              "source": job.record["sourceCommit"], "cases": {}}
    for number in FIELDS:
        case = cases[number]
        legs = result["cases"][number] = {}
        for side in ("parent", "fix"):
            base = Path("verification/java-domain-proof/name-validation") / number / side
            if base / "measurement.json" not in job.files:
                continue
            path = job.output(base / "measurement.json")
            report = read(path)
            original = readers[number]["sides"][side]
            provider = original["providers"]["org.apache.avro.Schema"]
            cut = report["qualification"]
            policy = "java.lang.Boolean" if number == "364" else "org.apache.avro.NameValidator$2"
            require(report["example"] == number and report["side"] == side and report["source"] == result["source"]
                    and report["binding"] == original["binding"] and report["jdkModules"] == original["jdkModules"]
                    and report["schemaProvider"] == {"entry": provider["entry"], "jar": provider["jar"]}
                    and cut["schemaClassSha256"] == provider["class"] and cut["field"] == FIELDS[number]
                    and cut["rejectedChanges"] == ["field", "instruction", "pool"] and report["defaultPolicyClass"] == policy
                    and report["baseline"]["checker"] == case["finalRun"]["checkerSha256"]
                    and report["baseline"]["source"] == case["finalRun"]["source"]
                    and report["checker"] == result.setdefault("checkerSha256", report["checker"])
                    and report["checker"] != report["baseline"]["checker"], "different Avro name-validation binding")
            expected = ("publicCalls=8 names=18 accepted=14 rejected=4 asciiPairs=16384 overrides=4 "
                        f"publicUtf={18 if number == '367' else 0} policy={policy}")
            logs = {}
            for key in ("physical", "trace"):
                stream = report[key]
                log = job.output(base / stream["stdout"])
                require(stream["exit"] == 0 and sha(log) == stream["stdoutSha256"], "different original JVM run")
                logs[key] = log
            require(logs["physical"].read_text().splitlines() == [expected], "incomplete original-JVM name controls")
            rows = policy_sites(logs["trace"].read_text().splitlines(), number, side, cut, policy)
            require(rows == report["callSites"], "public name-policy lookups differ from the original debugger stream")
            legs[side] = {"revision": report["binding"]["revision"], "defaultPolicyClass": policy,
                          "qualifiedConsumer": cut, "threadLocalFactory": report["threadLocalFactory"],
                          "observedGets": sum(len(r["names"]) for r in rows), "publicCalls": len(rows),
                          "namesAtPublicSite": sorted({name for r in rows for name in r["names"]}),
                          "originalJvm": rel(logs["physical"]), "siteTrace": rel(logs["trace"]), "measurement": rel(path),
                          "baseline": name_checks(job, base, report["baseline"]["proofs"], number),
                          "followup": name_checks(job, base, report["proofs"], number)}
    if result["state"] == "passed":
        require(all(set(legs) == {"parent", "fix"} for legs in result["cases"].values()), "missing name-validation side")
    sides = [leg for legs in result["cases"].values() for leg in legs.values()]
    result["totals"] = {stage: dict(Counter(query["verdict"] for leg in sides for query in leg[stage].values()))
                        for stage in ("baseline", "followup")}
    result["totals"].update(publicCalls=sum(leg["publicCalls"] for leg in sides), observedGets=sum(leg["observedGets"] for leg in sides))
    return result


READY_JOB = "20261122-142310-check-every-jackson-feed-from-the-unused"


def ready_query(job, base, item, expected, root_digest):
    from ready_parser import RUNTIME, START

    path = job.output(base / item["stdout"])
    raw, = read(path)
    stated = raw["stated"]
    target, guard, assertion = expected
    require(sha(path) == item["stdoutSha256"] and sha(job.output(base / item["stderr"])) == item["stderrSha256"]
            and raw["target"] == item["target"] == target and raw["assume"] == item["guard"] == guard
            and raw["assert"] == item["assertion"] == assertion and item["observedRoots"] == [START]
            and raw["verdict"] == item["verdict"] and raw["problem"] == item["blocker"]
            and stated["checker"]["engine"] == "native" and stated["checker"]["fallback"] is None
            and stated["gap_mode"] == "strict" and item["bounds"] == [512, 16384]
            and stated["domain"]["parameters"] == [{"name": "code", "type": "int", "kind": "primitive", "null": False}]
            and stated["observations"]["exceptions"] == "none may be thrown"
            and stated["bounds"]["unwind"] == 512 and raw["search"]["max_array_length"] == 16384,
            "different Jackson native scope or result")
    assumptions = stated["assumptions"]
    captured = [a for a in assumptions if a.get("id", "").startswith("observed-initializer:")]
    if raw["verdict"] in ("verified", "violation"):
        require(len(captured) == 1 and set(item["states"]) == {START}
                and captured[0]["id"] == f"observed-initializer:{START}:{root_digest}:{item['states'][START]}"
                and all(name in captured[0]["text"] for name in RUNTIME["captureObjects"])
                and "JDK 21.0.13, Eclipse Adoptium" in captured[0]["text"]
                and {a["text"] for a in assumptions if a not in captured} == {guard,
                     "every JDK class is initialized already, its static initializer having run and thrown nothing"},
                "Jackson result has an unbound parser, runtime or assumption")
    if raw["verdict"] == "verified":
        require(not item["exit"] and not raw["problem"] and stated["bounds"]["complete"]
                and stated["vacuity"]["status"] == "non-vacuous", "incomplete or vacuous Jackson establishment")
    if raw["verdict"] == "violation":
        require(raw["counterexample"] and raw["counterexample"]["inputs"], "missing Jackson counterexample")
    return {"entry": target, "guard": guard, "assertion": assertion, "verdict": raw["verdict"],
            "firstBlocker": raw["problem"], "stateSha256": item["states"].get(START), "receipt": rel(path),
            "seconds": item["seconds"], "checkerSeconds": raw["search"]["seconds"], "peakRssBytes": item["peakRssBytes"]}


def ready_parser_evidence(case, foundations):
    from ready_parser import FOLDER, SOURCE, RUNTIME, correspondence, qualify_schedule, queries, ready_source

    if not layout.find_result(ROOT, READY_JOB):
        return {"job": READY_JOB, "state": "pending"}
    job = Job(READY_JOB)
    result = {"job": READY_JOB, "source": job.record["sourceCommit"], "state": job.record["status"],
              "result": rel(job.folder / "result.json"), "sides": {}}
    folder = FOLDER.relative_to(ROOT)
    table = FOLDER / "controls/table.json"
    prior = foundations["nameValidation"]
    for side in ("parent", "fix"):
        base = folder / "records/ready-parser" / side
        if base / "measurement.json" not in job.files:
            continue
        path = job.output(base / "measurement.json")
        report = read(path)
        row = case["obligations"]["offsets-" + side]
        original = row["final"]
        finite = read(ROOT / original["finite"]["receipt"])
        cp = [a["sha256"] for a in finite["sides"][side]["classpath"]]
        binding = report["binding"]
        build = ROOT / binding["build"]
        require(report["side"] == side and report["runtime"] == RUNTIME and binding["revision"] == row["revision"]
                and sha(build) == binding["buildSha256"] == case["finalRun"]["builds"][side]
                and cp[1:] == binding["orderedJars"] == [a["sha256"] for a in read(build)["artifacts"]]
                and report["target"]["jar"] == cp[1] and report["target"]["classSha256"] == original["binding"]["subjectClassSha256"]
                and report["jdkModules"] == foundations["readers"]["367"]["sides"][side]["jdkModules"]
                and sha(table) == report["oracleSha256"] and sha(SOURCE) == report["originalAdapterSha256"]
                and report["baseline"]["checker"] == prior["checkerSha256"] and report["baseline"]["source"] == prior["source"]
                and report["followup"]["source"] == result["source"], "different historical Jackson or verifier inputs")
        checker = report["followup"]["checker"]
        require(len(checker) == 64 and checker != prior["checkerSha256"]
                and result.setdefault("checkerSha256", checker) == checker, "different Jackson follow-up checkers")
        tokens = job.output(base / "ReadyTokens.java")
        dispatch = job.output(base / "WindowSchedules.jvm-bytecode")
        require(tokens.read_text() == ready_source() and sha(tokens) == report["companionSourceSha256"]
                and sha(dispatch) == report["classHashes"]["WindowSchedules"]
                and qualify_schedule(dispatch.read_bytes()) == report["selectorCodeSha256"], "different parser or selector dispatch")
        reference = ROOT / report["ordinary"]
        historical = Job(JOBS["365"][1]).single(f"replay/*/records/control-{side}-jdk21.stdout")
        require(sha(historical) == sha(reference) == report["ordinarySha256"], "different ordinary Jackson controls")
        ordinary = [json.loads(line) for line in reference.read_text().splitlines()]
        runs = report["physical"]
        log = job.output(base / runs["stdout"])
        require(not runs["exit"] and sha(log) == runs["stdoutSha256"], "different JVM parser correspondence")
        counts = correspondence(log.read_text().splitlines(), ordinary, read(table)["cases"], side)
        require(counts == report["counts"], "wrong schedule counts")
        leg = result["sides"][side] = {"revision": binding["revision"], "measurement": rel(path), "physical": rel(log),
                                       "counts": counts}
        for stage in ("baseline", "followup"):
            proofs = report[stage]["proofs"]
            require(set(proofs) == set(queries(side)), "incomplete Jackson measurements")
            leg[stage] = {k: ready_query(job, base, proofs[k], spec, report["classHashes"]["ReadyParser"])
                          for k, spec in queries(side).items()}
        if side == "parent" and leg["followup"]["padded"]["verdict"] == "violation":
            source = ROOT / leg["followup"]["padded"]["receipt"]
            candidate = read(job.output(base / "candidate.json"))
            packet = report["originalWitness"]
            replay_path = job.output(folder / packet["file"])
            replay = read(replay_path)
            value = replay["sides"]["parent"]
            evidence = replay["finiteObservation"]
            require(candidate["sourceReceiptSha256"] == sha(source) and packet["sha256"] == sha(replay_path)
                    and candidate["inputs"] == read(source)[0]["counterexample"]["inputs"] == replay["inputs"]
                    == [{"name": "code", "type": "int", "value": 32}]
                    and packet["claimKey"] == replay["claimKey"] == original["claimKey"]
                    and replay["by"] == "jvm" and replay["reproduced"] and replay["entry"] == row["entry"]
                    and replay["observations"] == row["observations"] and replay["jdkRelease"] == finite["jdkRelease"]
                    and set(replay["sides"]) == {"parent"} and value["entryClassSha256"] == original["binding"]["classSha256"]
                    and value["classpath"] == cp and value["admitted"] and value["satisfies"] is False and value["values"] == [0, None]
                    and evidence == {"id": 32, "input": ordinary[32]["input"], "field": "offsets",
                                     "direct": {"parent": ordinary[32]["direct"]}, "tableSha256": sha(table)},
                    "native candidate did not reproduce on the original Jackson factory")
            leg["originalWitness"] = {"status": "refuted", "entry": row["entry"], "inputs": candidate["inputs"],
                                      "nativeReceipt": rel(source), "ordinaryReplay": rel(replay_path),
                                      "trace": ordinary[32]["direct"]["offsets"]["trace"]}
    if result["state"] == "passed":
        require(set(result["sides"]) == {"parent", "fix"}, "missing Jackson revision")
    return result


def compile_scorecard():
    result = {"schema": "java-domain-scorecard/v1", "planned": 20, "cases": {},
              "earlierPopulations": {"sixPRs": {"ordinary": [39, 46], "finite": [46, 46]},
                                     "avro729": {"ordinary": [2, 4], "recordedStartup": [4, 4], "finite": [4, 4]}}}
    counts = {key: Counter() for key in ("opening", "final", "finite")}
    verifiers = set()
    for number, case in PINS.items():
        folder = ROOT / "examples" / case["folder"]
        tasks = [t for t in read(folder / "target.json")["tasks"] if t["kind"] == "prove"
                 and not read(folder / t["claim"]).get("observedInitializers")]
        require(len(tasks) == 4, "changed primary denominator")
        test_job, opening_job = JOBS[number]
        final_specs = [p for p in (ROOT / "verification/jobs").glob("*-final-java-domain-"+number+"-*.json")]
        require(len(final_specs) <= 1, "ambiguous final measurement")
        final_job = final_specs[0].stem if final_specs else None
        opening = stage(opening_job, folder, tasks, "opening")
        final = stage(final_job, folder, tasks, "final")
        if opening["claims"] and final["claims"]:
            require(opening["builds"] == final["builds"], "the historical artifacts changed between measurements")
            for name in opening["claims"].keys() & final["claims"].keys():
                before, after = opening["claims"][name], final["claims"][name]
                require(all(before[k] == after[k] for k in ("claimKey","binding","checkerBudgetSeconds")) and
                        all(before["finite"][k] == after["finite"][k] for k in ("inputs","differences","status")),
                        f"{name}: the two measurements differ in scope, inputs or JVM behavior")
        if final["claims"]:
            verifiers.add((final["source"], final["checkerSha256"], final["fingerprint"]))
        rows = {}
        for task in tasks:
            name = task["id"]
            spec = read(folder / task["claim"])
            rows[name] = {"revision": case[task["revision"]], "target": task["target"], "entry": spec["adapter"]["entry"],
                          "statement": spec["statement"], "inputRows": spec["adapter"]["cases"], "guard": spec["assume"],
                          "bounds": spec["bounds"], "observations": spec["observations"], "startup": "ordinary"}
            for label, data in (("opening", opening), ("final", final)):
                observed = data["claims"].get(name)
                rows[name][label] = observed
                counts[label][observed["status"] if observed else "unmeasured"] += 1
            latest = final["claims"].get(name) or opening["claims"].get(name)
            counts["finite"][latest["finite"]["status"] if latest else "unmeasured"] += 1
        result["cases"][number] = {"pullRequest": case["pullRequest"], "namedTests": upstream_tests(Job(test_job), case),
                                   "openingRun": {k:v for k,v in opening.items() if k != "claims"},
                                   "finalRun": {k:v for k,v in final.items() if k != "claims"}, "obligations": rows}
    require(len(verifiers) <= 1, "final claims were measured on different verifiers")
    require(all(sum(c.values()) == result["planned"] for c in counts.values()), "wrong campaign denominator")
    result["cases"]["367"]["jvmControls"] = default_controls()
    result["foundations"] = foundation_results(result)
    result["foundations"]["nameValidation"] = name_validation_evidence(result["cases"], result["foundations"]["readers"])
    for number, reader in result["foundations"]["readers"].items():
        for name, row in result["cases"][number]["obligations"].items():
            method, side = name.rsplit("-", 1)
            proof = reader["sides"][side]["proofs"].get(method + "-recorded")
            if proof is None:
                continue
            roots = ["org.apache.avro.Schema", "org.apache.avro.generic.GenericData", "org.apache.avro.generic.GenericDatumReader"]
            spec = read(ROOT / "examples" / PINS[number]["folder"] / "claims" / (method + ".json"))
            require(proof["target"] + "(I)I" == row["entry"] and proof["guard"] == row["guard"]
                    and proof["assertion"] == spec["assert"] and proof["observedRoots"] == roots
                    and proof["bounds"] == [row["bounds"]["unwind"], row["bounds"]["maxArrayLength"]],
                    f"{number}/{name}: recorded-startup companion differs from the frozen public entry")
            row["recordedStartup"] = {k: proof[k] for k in ("verdict", "blocker", "observedRoots", "states", "receipt")}
    ready = ready_parser_evidence(result["cases"]["365"], result["foundations"])
    result["foundations"]["jacksonReadyParser"] = ready
    ordinary = counts["final"].copy()
    for side, evidence in ready.get("sides", {}).items():
        rows = result["cases"]["365"]["obligations"]
        grid = evidence["followup"]["grid"]
        if grid["verdict"] == "verified":
            for method in ("offsets", "tokens"):
                rejects = side == "parent" and method == "offsets"
                decision = evidence["followup"]["padded"] if rejects else grid
                if rejects and (decision["verdict"] != "violation" or "originalWitness" not in evidence):
                    continue
                rows[method + "-" + side]["afterFactoryReturn"] = {
                    "status": "refuted" if rejects else "established", "receipt": decision["receipt"],
                    "stateSha256": decision["stateSha256"], "traceLawReceipt": grid["receipt"], "schedules": 128,
                    "offsetLaw": "5 + padding" if side == "parent" else "5"}
        if witness := evidence.get("originalWitness"):
            row = rows["offsets-parent"]
            require(row["final"]["status"] in ("unresolved", "refuted"), "Jackson witness contradicts a public establishment")
            if row["final"]["status"] == "unresolved":
                ordinary["unresolved"] -= 1
                ordinary["refuted"] += 1
            row["ordinaryFollowup"] = witness
    counts["ordinaryIncludingFollowups"] = ordinary
    result["totals"] = counts
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-complete", action="store_true",
                        help="require both measurements of all public claims and the collected companion experiments")
    args = parser.parse_args()
    data = compile_scorecard()
    if args.require_complete:
        require(all(c[s]["state"] == "measured" for c in data["cases"].values() for s in ("openingRun","finalRun")),
                "public measures are still outstanding")
        extra = data["foundations"]
        require(extra["parquet"]["experimentStatus"] == "passed" and extra["selectorTransfer"]["state"] == "measured"
                and extra["nameValidation"]["state"] == "passed" and extra["jacksonReadyParser"]["state"] == "passed"
                and extra["enumActions"]["state"] == "passed" and set(extra["readers"]) == {"364","367"}
                and set(extra["inputSegmentation"]) == {"365","366"}
                and all(leg["callSiteRows"] for reader in extra["readers"].values() for leg in reader["sides"].values())
                and all("recordedStartup" in row for n in READER_JOBS for row in data["cases"][n]["obligations"].values()),
                "companion measures are still outstanding")
    rendered = json.dumps(data, indent=2) + "\n"
    if args.check:
        require(OUTPUT.read_text() == rendered, "scorecard differs from the recorded jobs")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(rendered)
    print(json.dumps(data["totals"]))

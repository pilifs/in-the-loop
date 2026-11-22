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
        partition = {**checked, "record":rel(result_path), "cost":data["cost"], "wallSeconds":data["wallSeconds"],
                     "witness":(data.get("originalJVMReplay") or {}).get("inputs")}
    return {"status": decision, "symbolicStatus":status, "nativePartition":partition,
            "firstBlocker": evidence["problem"], "gapSites": (raw.get("search") or {}).get("gaps", []),
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
    result["totals"] = counts
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = compile_scorecard()
    rendered = json.dumps(data, indent=2) + "\n"
    if args.check:
        require(OUTPUT.read_text() == rendered, "scorecard differs from the recorded jobs")
    else:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(rendered)
    print(json.dumps(data["totals"]))

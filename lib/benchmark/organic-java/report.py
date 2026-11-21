"""Recount the original JVM observations, finite proofs and strict native claims for the organic PRs."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
import build
from targets import finite_check, finite_oracle, native_selectors, route, sidecar
from domains import check_controls, wrong_results
from public_observations import complete_stream
from upstream import named_failure

PRIMARY = {
    "353": ["lookup", "entries"], "354": ["truncate", "abbreviate"], "355": ["bounds", "rejected"],
    "356": ["token", "lexeme"], "357": ["chunked"], "358": ["bytes", "ten"],
    "359": ["returns", "contents", "ordinary-outcomes"], "360": ["postorder", "terminal"],
}
WITNESS = {"353": (32, "lookup"), "354": (2, "fixedCut"), "355": (18, "rejected"),
           "356": (0, "lexeme"), "357": (7, "chunked"), "358": (2048, "bytes"),
           "359": (940, "returns"), "360": (0, "postorder")}
PRESERVED = {"353": "live", "354": "width-five", "355": "prefix", "356": "controls", "357": "plain", "358": "controls",
             "359": "ordinary-contents", "360": "preorder"}


def read(path):
    return json.loads(path.read_text())


def rel(path):
    return path.relative_to(ROOT).as_posix()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original_observations(folder, table):
    for receipt in sorted((folder / "receipts/replay").glob("*/result.json")):
        d = read(receipt)
        if d["conclusion"]["expectation"] != "yes" or d["evidence"]["replay"] != {"by": "jvm", "reproduced": True}:
            continue
        if any(digest(folder / f) != checksum for f, checksum in d["claim"]["target"]["files"].items()):
            continue
        sources, rows = {}, {}
        for side in ("parent", "fix"):
            raw, files = complete_stream(folder, receipt, side)
            records = [json.loads(s) for s in raw.splitlines() if s.startswith(b"{")]
            problems = table.problems(records)
            if side == "fix" and problems:
                raise ValueError(f"{folder.name} fixed observations disagree with the oracle")
            sources[side] = {"files": [rel(f) for f in files], "sha256": hashlib.sha256(raw).hexdigest(), "rows": len(records),
                             "disagreements": dict(Counter(field for _, field in problems))}
            rows[side] = {r["id"]: r for r in records}
        i, field = WITNESS[folder.name[:3]]
        witness_input = rows["parent"][i]["input"]
        if field == "fixedCut":
            witness_input = {"units": [97, 0xd83d, 0xde00, 98], "start": i % 36 // 6, "width": i % 6}
        return {"receipt": rel(receipt), "observations": sources, "witness": {
            "index": i, "field": field, "input": witness_input, "parent": rows["parent"][i]["direct"],
            "fix": rows["fix"][i]["direct"]}}
    return {"status": "original JVM replay pending"}


def native(folder, task, stages, plan):
    for stage in stages:
        base = folder / "records" / (stage + "-native") / task["id"]
        for path in sorted(base.glob("*/result.json"), reverse=True):
            d = read(path)
            c, e, a = d["conclusion"], d["evidence"], d["attempt"]
            if d["claim"]["target"].get("claimKey") != plan.claim["key"]:
                raise ValueError(f"native result for a different claim in {path}")
            stated = e.get("stated") or {}
            result = {"status": c["status"], "receipt": rel(path), "seconds": a.get("seconds"),
                      "stage": stage, "problem": e.get("problem"), "qualified": False}
            journal = base / "executions" / a["id"] / "attempt.json"
            if journal.exists():
                execution = read(journal)
                if execution["preparedClaim"] != d["claim"]["id"]:
                    raise ValueError("the native execution is bound to another artifact")
                checker_id = execution.get("checker") or {}
                result.update(usage=execution.get("usage"), execution=rel(journal),
                              checker={k: checker_id[k] for k in ("commit", "libTree", "jvmcontract", "jdk", "engine", "gaps", "bounds") if k in checker_id},
                              checkerSeconds=execution.get("checkerSeconds"), budget=execution["budget"])
                checker = journal.with_name("checker.json")
                if checker.exists():
                    timings = [o.get("search") or {} for o in read(checker).get("outcomes", [])]
                    result["solverSeconds"] = sum((t.get("native") or {}).get("solving_seconds", 0) for t in timings)
            if c["status"] not in ("established", "refuted"):
                return result
            source = d["claim"]["target"]
            if any(digest(folder / f) != checksum for f, checksum in source["files"].items()):
                result.update(status="superseded", recordedStatus=c["status"], problem="the recorded adapter or claim inputs have changed")
                return result
            assert a["engine"] == "native" and stated["gapMode"] == "strict" and not c["vacuous"]
            if c["status"] == "established":
                assert stated["vacuity"]["status"] == "non-vacuous"
            else:
                assert e["replay"] == {"by": "jvm", "reproduced": True} and e["counterexamples"]
            result["qualified"] = c["status"] == task["expected"] and c["expectation"] == "yes"
            return result
        journals = sorted((base / "executions").glob("*/attempt.json"), reverse=True)
        if journals:
            path = journals[0]
            a = read(path)
            refusal = a.get("firstBlocker") or a.get("refusal") or {}
            return {"status": "open", "qualified": False, "stage": stage, "receipt": rel(path),
                    "problem": refusal, "lastCompletedStage": a.get("lastCompletedStage")}
    return {"status": "open", "qualified": False, "problem": "no completed native receipt"}


def finite(folder, task, plan, stages):
    paths = (p for stage in stages for p in sorted((folder / "records" / (stage + "-finite")).glob("*/" + task["id"] + ".json"), reverse=True))
    for path in paths:
        record = read(path)
        if record["status"] != "open" and any(record.get(k) != v for k, v in finite_check.claim_identity(plan).items()):
            return {"status": "superseded", "qualified": False, "receipt": rel(path), "reason": "the current adapter or source binding differs"}
        finite_check.validate_record(plan, record)
        return {key: record.get(key) for key in ("status", "inputs", "differences", "reason", "prepareSeconds", "controlSeconds", "wallSeconds")} | {
            "qualified": record["status"] == task["expected"], "receipt": rel(path),
            "peakRssBytes": max((s.get("peakRssBytes", 0) for s in record.get("sides", {}).values()), default=0)}
    return {"status": "open", "qualified": False, "reason": "no complete finite record"}


def score(number, case, stages):
    folder = ROOT / "examples" / case["folder"]
    ex = build.load_example(folder)
    target = sidecar.load(folder, ex)
    results = {}
    product_runs = (folder / "records" / (stage + "-native") / "run.json"
                    for stage in stages if stage in ("confirmation", "final", "reserve"))
    pinned = next((read(path) for path in product_runs if path.is_file()), None)
    frozen_tasks = read(folder / "records/baseline-native/run.json")["tasks"]
    registered = {task["id"]: task for task in target["tasks"]}
    for name in frozen_tasks:
        task = registered[name]
        if task["kind"] == "replay":
            continue
        plan = route.resolve(folder, ex, target, task["id"])
        original = native(folder, task, ["baseline"], plan)
        current = native(folder, task, stages, plan)
        if not current["qualified"]:
            for proof in native_selectors.evidence(folder, plan):
                if proof.get("status") == task["expected"]:
                    file = (folder / proof["record"]).resolve()
                    report = read(file)
                    if pinned and (report["checker"]["sha256"], report["checker"]["commit"]) != (pinned["checkerSha256"], pinned["verifierCommit"]):
                        continue
                    solving = sum((read(file.parents[2] / r["raw"])[0].get("search") or {})
                                  .get("native", {}).get("solving_seconds", 0) for r in report["checked"])
                    current = {"status": proof["status"], "qualified": True, "route": "strict native selectors",
                               "receipt": rel(file), "checker": report["checker"], "admitted": proof["admitted"],
                               "checked": proof["checked"], "cost": report["cost"], "solverSeconds": solving, "unsplit": current}
                    break
        results[task["id"]] = {"expected": task["expected"], "guard": plan.claim["assume"], "claimKey": plan.claim["key"],
                               "baseline": original, "current": current, "finiteBaseline": finite(folder, task, plan, ["baseline"]),
                               "finite": finite(folder, task, plan, stages)}
    table = finite_oracle.Table(folder / "controls/table.json")
    check_controls(number, folder / "controls/table.json")
    formal = {version: all(results[field + "-" + side][version]["qualified"]
                           for field in [*PRIMARY[number], PRESERVED[number]] for side in ("parent", "fix"))
              for version in ("baseline", "current", "finiteBaseline", "finite")}
    upstream = {}
    for directory in sorted((folder / "records").glob("*"), reverse=True):
        if not all((directory / (side + "-upstream.json")).is_file() for side in ("parent", "fix")):
            continue
        pair = {}
        for rev in ("parent", "fix"):
            f = directory / (rev + "-upstream.json")
            r = read(f)
            named = r["upstreamTest"]["named"]
            if r["revision"] != case[rev] or set(named) != set(case["tests"]):
                raise ValueError("the upstream testcase record belongs to a different revision or test")
            tests = {}
            for selector, records in named.items():
                if len(records) != 1:
                    break
                row, = records
                xml = directory / (rev + "-TEST-" + row["class"] + ".xml.gz")
                content = gzip.decompress(xml.read_bytes())
                if hashlib.sha256(content).hexdigest() != row["xmlSha256"]:
                    raise ValueError("upstream XML digest mismatch")
                matching = [t for t in ET.fromstring(content).iter("testcase")
                            if t.get("name") == row["method"] and t.get("classname") == row["class"]]
                if len(matching) != 1:
                    break
                t, = matching
                status = next((key for key in ("failure", "error", "skipped") if t.find(key) is not None), "passed")
                if status != row["status"] or ((rev == "fix") != (status == "passed")) or status == "skipped":
                    break
                location = named_failure(t, t.find(status), r["upstreamTest"]["execution"]) if rev == "parent" else None
                if rev == "parent" and not location:
                    break
                tests[selector] = {**row, "xml": rel(xml), "failureLocationEvidence": location}
            if set(tests) != set(case["tests"]):
                break
            pair[rev] = {"receipt": rel(f), "revision": r["revision"], "named": tests,
                         "buildSeconds": r["build"]["seconds"], "testSeconds": r["upstreamTest"]["execution"]["seconds"]}
        if len(pair) == 2:
            upstream = pair
            break
    builds = {}
    for rev, name in target["preparation"].get("capturedBuilds", {}).items():
        f = folder / name
        r = read(f)
        output = r["build"]["outputs"]
        assert r["recipe"]["commit"] == case[rev]
        builds[rev] = {"receipt": rel(f), "originalJarSha256": r["artifacts"][0]["sha256"],
                       "productionClass": output["selectedClass"], "classSha256": output["selectedClassSha256"],
                       "classpathEntries": len(r["artifacts"]), "buildAndClasspathSeconds": sum(s.get("seconds", 0) for s in r["build"]["steps"])}
    adapters = {name: {"sha256": digest(folder / name), "sourceLines": len((folder / name).read_text().splitlines())}
                for name in target["preparation"]["adapters"]}
    runs = {}
    for group in ("baseline", *stages):
        for kind in ("native", "finite"):
            f = folder / "records" / (group + "-" + kind) / "run.json"
            if f.is_file():
                r = read(f)
                runs[group + "-" + kind] = {k: r[k] for k in ("seconds", "verifierCommit", "checkerSha256", "workflowExit")} | {"record": rel(f)}
    original_replays = []
    for path in sorted((folder / "records/native-selectors").glob("*/*/tasks/*/result.json")):
        doc = read(path)
        if doc["status"] != "refuted" or doc["checked"][-1]["status"] != "needs-jvm-replay":
            continue
        plan = route.resolve(folder, ex, target, doc["task"])
        result = native_selectors.validate_result(folder, plan, path)
        replay = doc["originalJVMReplay"]
        original_replays.append({"task": plan.task, "status": result["status"], "inputs": replay["inputs"],
                                 "publicEntry": replay["entry"], "jdk": replay["jdkRelease"], "checker": doc["checker"], "receipt": rel(path)})
    return {"handwrittenAdapters": adapters, "wrongResultControlsRejected": len(wrong_results(number)), "nativeSelectorJVMReplays": original_replays,
            "runs": runs, "upstream": case["repository"] + "/pull/" + str(case["pullRequest"]), "history": target["history"]["revisions"],
            "inputs": len(table.cases), "builds": builds, "originals": original_observations(folder, table), "upstreamTests": upstream,
            "primary": PRIMARY[number], "preservation": PRESERVED[number], "caseDecided": formal, "tasks": results}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stages", default="confirmation,final,reserve,ordered,streams,utf16,baseline", help="most recent first")
    ap.add_argument("--output", type=Path, default=ROOT / "verification/organic-java-pr-campaign.json")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    corpus = read(HERE / "cases.json")
    rows = {n: score(n, c, args.stages.split(",")) for n, c in corpus["cases"].items()}
    reserves = {n: score(n, c, args.stages.split(",")) for n, c in corpus.get("reserves", {}).items()
                if (ROOT / "examples" / c["folder"] / "target.json").is_file()}
    summary = {}
    for v in ("baseline", "current", "finiteBaseline", "finite"):
        obligations = [t[v] for c in rows.values() for t in c["tasks"].values()]
        outcomes = Counter(t["status"] for t in obligations if t["qualified"])
        summary[v] = {"completeCases": sum(c["caseDecided"][v] for c in rows.values()),
                      "qualifiedObligations": sum(outcomes.values()), "established": outcomes["established"],
                      "refuted": outcomes["refuted"], "open": len(obligations) - sum(outcomes.values())}
    stage = next((s for s in args.stages.split(",") if s in ("confirmation", "final") and
                  all(all(s + "-" + route in r["runs"] for route in ("native", "finite")) for r in rows.values())), None)
    pins = {(run["verifierCommit"], run["checkerSha256"]) for r in rows.values() for name, run in r["runs"].items()
            if stage and name in (stage + "-native", stage + "-finite")}
    if len(pins) > 1:
        raise ValueError("the final primary runs used different verifier builds")
    pin = next(iter(pins), None)
    result = {"baselinePin": read(HERE / "baseline.json"), "finalVerifier": None if pin is None else {"stage": stage, "commit": pin[0], "executableSha256": pin[1]},
              "summary": summary, "cases": rows, "reserves": reserves}
    raw = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
    if args.check:
        if args.output.read_text() != raw:
            raise ValueError("stored scorecard differs from its receipts")
    else:
        args.output.write_text(raw)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()

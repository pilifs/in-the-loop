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

PRIMARY = {
    "353": ["lookup", "entries"], "354": ["truncate", "abbreviate"], "355": ["bounds", "rejected"],
    "356": ["token", "lexeme"], "357": ["chunked"], "358": ["bytes", "ten"],
}
WITNESS = {"353": (32, "lookup"), "354": (2, "fixedCut"), "355": (18, "rejected"),
           "356": (0, "lexeme"), "357": (7, "chunked"), "358": (2048, "bytes")}
PRESERVED = {"353": "live", "354": "width-five", "355": "prefix", "356": "controls", "357": "plain", "358": "controls"}


def read(path):
    return json.loads(path.read_text())


def rel(path):
    return path.relative_to(ROOT).as_posix()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def original_observations(folder, table):
    for receipt in sorted((folder / "receipts/replay").glob("*/result.json"), reverse=True):
        d = read(receipt)
        if d["conclusion"]["expectation"] != "yes" or d["evidence"]["replay"] != {"by": "jvm", "reproduced": True}:
            continue
        sources, rows = {}, {}
        for side in ("parent", "fix"):
            f = receipt.parent / "records" / ("control-" + side + "-jdk21.stdout")
            records = [json.loads(s) for s in f.read_text().splitlines() if s.startswith("{")]
            problems = table.problems(records)
            if side == "fix" and problems:
                raise ValueError(f"{folder.name} fixed observations disagree with the oracle")
            sources[side] = {"path": rel(f), "sha256": digest(f), "rows": len(records),
                             "disagreements": dict(Counter(field for _, field in problems))}
            rows[side] = {r["id"]: r for r in records}
        i, field = WITNESS[folder.name[:3]]
        return {"receipt": rel(receipt), "observations": sources, "witness": {
            "index": i, "field": field, "input": rows["parent"][i]["input"], "parent": rows["parent"][i]["direct"],
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
                result.update(usage=execution.get("usage"), checker=execution.get("checker"),
                              checkerSeconds=execution.get("checkerSeconds"), budget=execution["budget"])
            if c["status"] not in ("established", "refuted"):
                return result
            assert a["engine"] == "native" and stated["gapMode"] == "strict" and not c["vacuous"]
            if c["status"] == "established":
                assert stated["vacuity"]["status"] == "non-vacuous"
            else:
                assert e["replay"] == {"by": "jvm", "reproduced": True} and e["counterexamples"]
            result["qualified"] = c["status"] == task["expected"] and c["expectation"] == "yes"
            return result
    return {"status": "open", "qualified": False, "problem": "no completed native receipt"}


def finite(folder, task, plan):
    for path in sorted((folder / "records/baseline-finite").glob("*/" + task["id"] + ".json"), reverse=True):
        record = read(path)
        finite_check.validate_record(plan, record)
        return {key: record.get(key) for key in ("status", "inputs", "differences", "reason", "prepareSeconds", "controlSeconds")} | {
            "qualified": record["status"] == task["expected"], "receipt": rel(path),
            "peakRssBytes": max((s.get("peakRssBytes", 0) for s in record.get("sides", {}).values()), default=0)}
    return {"status": "open", "qualified": False, "reason": "no complete finite record"}


def score(number, case, stages):
    folder = ROOT / "examples" / case["folder"]
    ex = build.load_example(folder)
    target = sidecar.load(folder, ex)
    results = {}
    for task in target["tasks"]:
        if task["kind"] == "replay":
            continue
        plan = route.resolve(folder, ex, target, task["id"])
        original = native(folder, task, ["baseline"], plan)
        current = native(folder, task, stages, plan)
        if not current["qualified"]:
            for proof in reversed(native_selectors.evidence(folder, plan)):
                if proof.get("status") == task["expected"]:
                    current = {"status": proof["status"], "qualified": True, "route": "strict native selectors",
                               "receipt": str(folder.relative_to(ROOT) / proof["record"]),
                               "unsplit": current}
                    break
        results[task["id"]] = {"expected": task["expected"], "guard": plan.claim["assume"], "claimKey": plan.claim["key"],
                               "baseline": original, "current": current, "finite": finite(folder, task, plan)}
    table = finite_oracle.Table(folder / "controls/table.json")
    formal = {version: all(results[field + "-" + side][version]["qualified"]
                           for field in [*PRIMARY[number], PRESERVED[number]] for side in ("parent", "fix"))
              for version in ("baseline", "current", "finite")}
    upstream = {}
    for directory in sorted((folder / "records").iterdir(), reverse=True):
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
                if rev == "parent" and row["class"] + "." + row["method"] + "(" not in (t.find(status).text or ""):
                    break
                tests[selector] = {**row, "xml": rel(xml)}
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
                       "classpathEntries": len(r["artifacts"])}
    return {"upstream": case["repository"] + "/pull/" + str(case["pullRequest"]), "history": target["history"]["revisions"],
            "inputs": len(table.cases), "builds": builds, "originals": original_observations(folder, table), "upstreamTests": upstream,
            "primary": PRIMARY[number], "preservation": PRESERVED[number], "caseDecided": formal, "tasks": results}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stages", default="final,streams,utf16,baseline", help="most recent first")
    ap.add_argument("--output", type=Path, default=ROOT / "verification/organic-java-pr-campaign.json")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    cases = read(HERE / "cases.json")["cases"]
    rows = {n: score(n, c, args.stages.split(",")) for n, c in cases.items()}
    summary = {}
    for v in ("baseline", "current", "finite"):
        summary[v] = {"completeCases": sum(c["caseDecided"][v] for c in rows.values()),
                      "qualifiedObligations": sum(t[v]["qualified"] for c in rows.values() for t in c["tasks"].values())}
    result = {"baselinePin": read(HERE / "baseline.json"), "summary": summary, "cases": rows}
    raw = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
    if args.check:
        if args.output.read_text() != raw:
            raise ValueError("stored scorecard differs from its receipts")
    else:
        args.output.write_text(raw)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()

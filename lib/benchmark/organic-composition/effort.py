"""Summarize measured job costs and the inference interval from published aggregate counters."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

from plan_run import HERE, OUTPUT, ROOT

START="27e6cca94c80ea8ac7ad83971e0efa05a3d601b9"


def archive_receipts():
    def references(value):
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and value["path"].startswith("receipts/"):
                yield value
            for child in value.values():
                yield from references(child)
        elif isinstance(value, list):
            for child in value:
                yield from references(child)

    rows = {}
    for archive in sorted((ROOT / OUTPUT).rglob("plans.zip")):
        plans = references_checked = direct = 0
        digests = {}
        with zipfile.ZipFile(archive) as packed:
            names = packed.namelist()
            if len(set(names)) != len(names):
                raise ValueError("ambiguous member in " + str(archive))
            for name in names:
                if "/" in name or not name.endswith(".json"):
                    continue
                plan = json.loads(packed.read(name))
                direct += sum(bool(claim.get("receipt")) for claim in plan["claims"])
                plans += 1
                for ref in references(plan):
                    path = ref["path"]
                    if path not in digests:
                        digests[path] = hashlib.sha256(packed.read(path)).hexdigest()
                    if digests[path] != ref.get("sha256"):
                        raise ValueError(f"{archive}:{name} has an unbound receipt {path}")
                    references_checked += 1
        if not plans:
            raise ValueError("empty plan archive: " + str(archive))
        rows[str(archive.relative_to(ROOT / OUTPUT))] = {
            "plans": plans, "receiptReferences": references_checked, "directClaimReceipts": direct}
    return {"archives": len(rows), **{k: sum(r[k] for r in rows.values()) for k in
            ("plans", "receiptReferences", "directClaimReceipts")}, "byArchive": rows}


def main(end, cycles=1, cycle_start=None):
    if cycles < 1:
        raise ValueError("at least one domain cycle is required")
    jobs=json.loads((ROOT/OUTPUT/"jobs.json").read_bytes())
    specs={j["id"]:json.loads(next((ROOT/"verification/jobs").rglob(j["id"]+".json")).read_bytes()) for j in jobs}
    session=specs[jobs[0]["id"]]["submitted"]["session"]
    def counters(rev):
        path="llm-dlc/traces/"+session+"/manifest.json"
        manifest=json.loads(subprocess.check_output(["git","show",rev+":"+path],cwd=ROOT))
        return manifest["stats"]["usage"]
    before,after=counters(START),counters(end)
    totals={key:after[key]-before.get(key,0) for key in after if isinstance(after[key],int)}
    first=min(datetime.fromisoformat(d["submitted"]["at"]) for d in specs.values())
    last=max(datetime.fromisoformat(j["finishedAt"]) for j in jobs)
    per_job={j["id"]:{"source":j["source"],"status":j["status"],
                      "wallSeconds":j["usage"].get("wallSeconds"),"cpuSeconds":j["usage"].get("cpuSeconds"),
                      "peakMemoryBytes":j["usage"].get("peakMemoryBytes")} for j in jobs}
    replacements={"20261124-150013-retry-the-threeten-public-caller-after-o":
                  "20261124-152629-retain-the-original-threeten-startup-obs",
                  "20261124-153512-locate-the-ordinary-and-observed-poi-for":
                  "20261124-155203-retain-the-poi-startup-frontier-on-ordin",
                  "20261124-172139-identify-the-original-commons-io-rewind":
                  "20261124-173601-capture-the-original-commons-io-default",
                  "20261124-175912-check-the-unmodifiable-iterator-effect-a":
                  "20261124-181646-resolve-the-decorator-cache-field-and-re"}
    superseded={job:success for job,success in replacements.items()
                if job in per_job and per_job[job]["status"]=="failed" and per_job.get(success,{}).get("status")=="passed"}
    unresolved=[job for job,row in per_job.items() if row["status"]!="passed" and job not in superseded]
    profiles={}
    for case in ("threeten","poi","phone","icu","collections-628","collections-755","url-only","io","lang"):
        folder=HERE/case
        if not (folder/"effort.json").is_file():continue
        row=json.loads((folder/"effort.json").read_bytes())
        label="transfer-baseline" if case=="threeten" else "first"
        report=ROOT/OUTPUT/case/label/"summary.json"
        if report.is_file():
            runs=json.loads(report.read_bytes())["runs"]
            row["measuredPlanSeconds"]={name:{k:runs[name][k] for k in ("wallSeconds","childCpuSeconds")} for name in ("cold","warm","clean") if name in runs}
        profiles[case]=row
    builds = [j["checkerBuild"] for j in jobs if j["checkerBuild"] is not None]
    record={"domainCyclesObserved":cycles,"setup":"Separate upstream setup run, outside the job and inference intervals below.",
            "aggregateInference":{"session":session,"startSnapshot":START,"endSnapshot":end,"startCounters":before,"endCounters":after,"delta":totals,
            "scope":"Published aggregate counters between the initial checkout and the named source checkpoint. Includes work between trace syncs; per-case inference and post-checkpoint reporting cannot be isolated."},
            "jobs":{"firstSubmitted":first.isoformat(),"lastFinished":last.isoformat(),"elapsedSeconds":(last-first).total_seconds(),
                    "sumWallSeconds":round(sum(x["wallSeconds"] or 0 for x in per_job.values()),3),
                    "sumCpuSeconds":round(sum(x["cpuSeconds"] or 0 for x in per_job.values()),3),
                    "jobsMissingCpu":sum(x["cpuSeconds"] is None for x in per_job.values()),
                    "supersededAttempts":superseded,"unresolvedAttempts":unresolved,"costs":per_job,
                    "additionalCheckerBuilds":{"count":len(builds),
                        "sumWallSeconds":round(sum(b["wallSeconds"] for b in builds if b["wallSeconds"] is not None),3),
                        "sumCpuSeconds":round(sum(b["cpuSeconds"] for b in builds if b["cpuSeconds"] is not None),3),
                        "missingWall":sum(b["wallSeconds"] is None for b in builds),
                        "missingCpu":sum(b["cpuSeconds"] is None for b in builds),
                        "scope":"Measured pipeline preparation steps, excluded from the submitted-step CPU and wall sums above."}},
            "archiveIntegrity":archive_receipts(), "cases":profiles,
            "caseHelpRequests":sum(p.get("requestsForCaseInput",0) for p in profiles.values())}
    if cycle_start:
        prior = json.loads(subprocess.check_output(["git", "show", cycle_start + ":" + str(OUTPUT / "jobs.json")], cwd=ROOT))
        previous_ids = {j["id"] for j in prior}
        if not previous_ids.issubset(per_job):
            raise ValueError("earlier job records are missing")
        added = [j for j in jobs if j["id"] not in previous_ids]
        start_usage = counters(cycle_start)
        record["latestCycle"] = {
            "number": cycles, "startSnapshot": cycle_start, "endCounterSnapshot": end,
            "aggregateInferenceDelta": {k: after[k] - start_usage.get(k, 0) for k in totals},
            "submittedJobs": [j["id"] for j in added], "passed": sum(j["status"] == "passed" for j in added),
            "sumWallSeconds": round(sum(j["usage"]["wallSeconds"] or 0 for j in added), 3),
            "sumCpuSeconds": round(sum(j["usage"]["cpuSeconds"] or 0 for j in added), 3),
            "checkerBuildWallSeconds": round(sum((j["checkerBuild"] or {}).get("wallSeconds") or 0 for j in added), 3),
            "checkerBuildCpuSeconds": round(sum((j["checkerBuild"] or {}).get("cpuSeconds") or 0 for j in added), 3)}
    (ROOT/OUTPUT/"effort.json").write_text(json.dumps(record,indent=2)+"\n")
    print(len(per_job),"jobs;",len(profiles),"case records")

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("end_revision")
    ap.add_argument("--cycles", type=int, default=1)
    ap.add_argument("--cycle-start", help="committed job ledger and published counters at the start of the latest cycle")
    args=ap.parse_args()
    main(args.end_revision, args.cycles, args.cycle_start)

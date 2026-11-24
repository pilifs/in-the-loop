"""Summarize measured job costs and the inference interval from published aggregate counters."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess

from plan_run import HERE, OUTPUT, ROOT

START="27e6cca94c80ea8ac7ad83971e0efa05a3d601b9"


def main(end):
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
                  "20261124-155203-retain-the-poi-startup-frontier-on-ordin"}
    superseded={job:success for job,success in replacements.items()
                if job in per_job and per_job[job]["status"]=="failed" and per_job.get(success,{}).get("status")=="passed"}
    unresolved=[job for job,row in per_job.items() if row["status"]!="passed" and job not in superseded]
    profiles={}
    for case in ("threeten","poi","phone","icu","collections-628","collections-755","url-only"):
        folder=HERE/case
        if not (folder/"effort.json").is_file():continue
        row=json.loads((folder/"effort.json").read_bytes())
        label="transfer-baseline" if case=="threeten" else "first"
        report=ROOT/OUTPUT/case/label/"summary.json"
        if report.is_file():
            runs=json.loads(report.read_bytes())["runs"]
            row["measuredPlanSeconds"]={name:{k:runs[name][k] for k in ("wallSeconds","childCpuSeconds")} for name in ("cold","warm","clean") if name in runs}
        profiles[case]=row
    record={"domainCyclesObserved":1,"setup":"Separate setup run, outside the job and inference intervals below.",
            "aggregateInference":{"session":session,"startSnapshot":START,"endSnapshot":end,"startCounters":before,"endCounters":after,"delta":totals,
            "scope":"Published aggregate counters between the initial checkout and the named source checkpoint. Includes work between trace syncs; per-case inference and post-checkpoint reporting cannot be isolated."},
            "jobs":{"firstSubmitted":first.isoformat(),"lastFinished":last.isoformat(),"elapsedSeconds":(last-first).total_seconds(),
                    "sumWallSeconds":round(sum(x["wallSeconds"] or 0 for x in per_job.values()),3),
                    "sumCpuSeconds":round(sum(x["cpuSeconds"] or 0 for x in per_job.values()),3),
                    "jobsMissingCpu":sum(x["cpuSeconds"] is None for x in per_job.values()),
                    "supersededAttempts":superseded,"unresolvedAttempts":unresolved,"costs":per_job},
            "cases":profiles,"caseHelpRequests":sum(p.get("requestsForCaseInput",0) for p in profiles.values())}
    (ROOT/OUTPUT/"effort.json").write_text(json.dumps(record,indent=2)+"\n")
    print(len(per_job),"jobs;",len(profiles),"case records")

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("end_revision");main(ap.parse_args().end_revision)

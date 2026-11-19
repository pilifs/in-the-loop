"""A read-only view of source claims, their subjects, and the evidence each route recorded."""

from collections import defaultdict
from pathlib import Path

import accept
from targets import workflow
from targets.interfaces import Unsupported
from targets.workflow_handoff import read_json


def job_history(root, folder, number):
    """Associate plain task steps with their actual job results. An unrecognized step decides nothing."""
    tasks = defaultdict(list)
    others = []
    for path in sorted((root / "verification/jobs").glob("*.json")):
        job = read_json(path) or {}
        if number not in (job.get("links") or {}).get("examples", []):
            continue
        result_path = root / "verification/results" / path.stem / "result.json"
        result = read_json(result_path) or {}
        job_ref = {"job": path.stem, "jobFile": str(path.relative_to(root)), "budget": job.get("resources"),
                   "jobResult": str(result_path.relative_to(root)) if result else None,
                   "jobStatus": result.get("status"), "jobStartedAt": result.get("startedAt"),
                   "jobFinishedAt": result.get("finishedAt"), "sourceCommit": result.get("sourceCommit"),
                   "checkerTree": (result.get("jvmcontract") or {}).get("libTree")}
        matched = False
        actual = {s["index"]: s for s in result.get("steps", [])}
        for index, spec in enumerate(job.get("steps", []), 1):
            command = spec.get("run", "")
            args = command.split()
            parsed = accept.driver_run(command)
            if len(args) == 5 and args[:4] == ["python3", "examples/tools/build.py", number, "--task"]:
                task, route = args[4], "ordinary"
            elif isinstance(parsed, dict) and parsed["folder"] == folder.relative_to(root).as_posix():
                task, route = parsed["task"], "beside"
            else:
                continue
            step = actual.get(index, {})
            tasks[task].append({**job_ref, "route": route, "step": index,
                                "status": step.get("status"), "seconds": step.get("wallSeconds"),
                                "peakBytes": step.get("peakMemoryBytes"), "log": step.get("log")})
            matched = True
        if not matched:
            others.append(job_ref)
    return tasks, others


def receipt_history(folder, plan, entries):
    current = set() if isinstance(plan, Unsupported) else {
        a["path"] for a in workflow.current_attempts(plan, entries)}
    receipts = []
    for a in entries:
        path = folder / a["path"]
        document = read_json(path) or {}
        plan_record = read_json(path.parent / workflow.PLAN_RECORD) or {}
        recorded_key = ((plan_record.get("inputs") or {}).get("claim") or {}).get("key")
        claim = document.get("claim") or {}
        attempt = document.get("attempt") or {}
        conclusion = document.get("conclusion") or {}
        evidence = document.get("evidence") or {}
        statements = [evidence.get("stated") or {}]
        statements.extend((o.get("evidence") or {}).get("stated") or {} for o in conclusion.get("obligations", []))
        rests = list(dict.fromkeys(a["text"] for statement in statements for a in statement.get("assumptions", [])
                                   if a.get("basis") != "stated" and a.get("text")))
        limits = []
        if a["status"] == "refuted" and (evidence.get("replay") or {}).get("by") != "jvm":
            limits.append("This receipt lacks an independently qualified JVM replay of the violation.")
        for revision, scope in ((claim.get("target") or {}).get("scopes") or {}).items():
            limits.append(f"{revision} was checked as {scope}.")
        transfer = (claim.get("statement", {}).get("claim") or {}).get("adapter")
        if transfer:
            limits.append(transfer["mapping"])
        receipts.append({
            "restsOn": rests, "limits": limits, "id": a["attempt"], "path": a["path"], "claimKey": (claim.get("target") or {}).get("claimKey") or recorded_key,
            "preparedClaim": claim.get("id"), "taskInputsCurrent": a["path"] in current,
            "problem": a["problem"], "execution": a["execution"], "conclusion": a["status"],
            "vacuous": conclusion.get("vacuous"), "engine": attempt.get("engine"),
            "ingestedAt": attempt.get("startedAt"), "seconds": attempt.get("seconds"),
            "pipeline": attempt.get("pipeline"), "replay": (document.get("evidence") or {}).get("replay"),
        })
    return receipts


def inventory(folder, example, target, claim_filter=None, revision=None):
    folder = Path(folder).resolve()
    root = folder.parent.parent
    claims, replays = {}, []
    receipts = workflow.attempts(folder)
    jobs, other_jobs = job_history(root, folder, example["id"])
    history = [read_json(path) for path in sorted((folder / "history").glob("*.json"))]
    source = accept.Source(root)
    if revision and revision not in target["history"]["revisions"]:
        raise ValueError(f"unknown revision {revision!r} for {example['id']}")

    for task in target["tasks"]:
        name = task["id"]
        revisions = list(workflow.revisions_of(target, task))
        if revision and revision not in revisions:
            continue
        plan = workflow.plan_task(folder, example, target, name)
        key = None if isinstance(plan, Unsupported) else plan.claim["key"]
        file = task.get("claim")
        if claim_filter and claim_filter not in (file, key):
            continue
        entries = receipt_history(folder, plan, [a for a in receipts if a["task"] == name])
        linked = jobs.get(name, [])
        dated_jobs = [j for j in linked if j["jobFinishedAt"]]
        previous = [entry for entry in history if entry and entry.get("task") == name
                    and entry.get("claimKey") == key and entry.get("revisions") == revisions]
        executions = []
        for path in sorted((folder / "receipts" / name / "executions").glob("*/attempt.json")):
            data = read_json(path)
            if not data or data.get("schema") != "target-execution/v1" or data.get("id") != path.parent.name:
                continue
            executions.append({**{k: data.get(k) for k in ("id", "claimKey", "revisions", "preparedClaim", "bindingId", "status",
                               "startedAt", "retryOf", "lastCompletedStage", "missing", "refusal", "injected",
                               "job", "budget", "strategy", "receipt")}, "path": path.relative_to(folder).as_posix()})
        known = {e["id"] for e in executions}
        for r in entries:
            if r["id"] not in known:
                executions.append({"id": r["id"], "claimKey": r["claimKey"], "revisions": revisions,
                                   "preparedClaim": r["preparedClaim"], "status": r["execution"], "path": r["path"],
                                   "startedAt": r["ingestedAt"], "lastCompletedStage": "receipt-published"})
        executions.sort(key=lambda e: e["id"])
        row = {
            "task": name, "kind": task["kind"], "revisions": revisions,
            "expected": task.get("expected"), "parent": task.get("parent"), "requires": task.get("requires", []),
            "executions": executions,
            "latestAttempt": next((e for e in reversed(executions) if e["claimKey"] == key), None),
            "receipts": entries, "jobs": linked, "historicalProbes": previous,
            "latestReceipt": entries[-1]["id"] if entries else None,
            "latestCollectedStep": max(dated_jobs, key=lambda j: (j["jobFinishedAt"], j["step"])) if dated_jobs else None,
            "gapPackets": [b["packet"] for b in target.get("handoff", {}).get("blockers", [])
                           if b.get("task") in (None, name) and b.get("packet")],
        }
        if task["kind"] == "replay":
            replays.append(row)
            continue
        row["evidence"] = []
        for r in entries:
            if not r["taskInputsCurrent"] or r["execution"] != "completed" or r["vacuous"] is not False:
                continue
            answer = r["conclusion"]
            if answer == "established" or (answer == "refuted" and r["replay"]
                                            and r["replay"].get("by") == "jvm" and r["replay"].get("reproduced") is True):
                row["evidence"].append({"route": "ordinary", "answer": answer, "receipt": r["path"],
                                        "preparedClaim": r["preparedClaim"], "restsOn": r["restsOn"], "limits": r["limits"]})
        if task.get("besideRoute"):
            checked = accept.check(root, example["id"], name, source)
            row["besideAcceptance"] = {k: checked.get(k) for k in
                                       ("accepted", "job", "actual", "why", "bound", "limits", "restsOn", "identity")}
            if checked["accepted"]:
                row["evidence"].append({"route": "beside", "answer": checked["actual"], "job": checked["job"],
                                        "restsOn": checked.get("restsOn", []), "limits": checked["limits"]})
        row["latestEligible"] = row["evidence"][-1] if row["evidence"] else None
        answers = {e["answer"] for e in row["evidence"]}
        row["conclusion"] = "disputed" if len(answers) > 1 else next(iter(answers), "open")
        # Unplannable tasks cannot share a key by virtue of both missing it.
        group = claims.setdefault(key or (file, name), {"claimKey": key, "file": file, "subjects": []})
        if isinstance(plan, Unsupported):
            row["planningProblem"] = plan.describe()
        group["subjects"].append(row)
    if claim_filter and not claims and not replays:
        raise ValueError(f"no claim {claim_filter!r} matches the selected revision of {example['id']}")
    return {"schema": "example-claim-history/v1", "example": example["id"], "claims": list(claims.values()),
            "replays": replays, "otherExampleJobs": other_jobs}

def markdown(value):
    lines = [f"# Example {value['example']} claim history", ""]
    for group in value["claims"]:
        for subject in group["subjects"]:
            last = subject["latestAttempt"]
            lines.extend([f"## {subject['task']}", "", f"Source claim `{group['claimKey']}` on "
                          + ", ".join(subject["revisions"]) + f". Eligible conclusion: {subject['conclusion']}.", ""])
            if last:
                lines.append(f"Latest execution [{last['id']}]({last['path']}) reached {last['lastCompletedStage']}.")
                if last.get("missing"):
                    lines.append("Missing evidence: " + ", ".join(last["missing"]) + ".")
            lines.append("")
            for record in subject["evidence"]:
                link = record.get("receipt") or record.get("job")
                lines.append(f"- {record['answer']} ([evidence]({link}))")
                lines.extend("  - Rests on " + reason for reason in record.get("restsOn", []) if reason)
                lines.extend("  - Limit: " + reason for reason in record.get("limits", []) if reason)
            for attempt in subject["executions"][:-1]:
                lines.append(f"- Earlier [{attempt['id']}]({attempt['path']}) reached {attempt['lastCompletedStage']}.")
            lines.append("")
    return "\n".join(lines) + "\n"

"""A read-only view of source claims, their subjects, and the evidence each route recorded."""

from collections import defaultdict
import os
from pathlib import Path

import accept
from targets import route, workflow
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
            if args[:4] == ["python3", "examples/tools/build.py", number, "--tasks"]:
                try:
                    names = [name for name, _ in route.batch_tasks(args[2:])]
                except ValueError:
                    continue
                source_route = "ordinary"
            elif len(args) == 5 and args[:4] == ["python3", "examples/tools/build.py", number, "--task"]:
                names, source_route = [args[4]], "ordinary"
            elif isinstance(parsed, dict) and parsed["folder"] == folder.relative_to(root).as_posix():
                names, source_route = [parsed["task"]], "beside"
            else:
                continue
            step = actual.get(index, {})
            for name in names:
                tasks[name].append({**job_ref, "route": source_route, "step": index, "sharedStep": len(names) > 1,
                                    "status": step.get("status"), "seconds": step.get("wallSeconds"),
                                    "peakBytes": step.get("peakMemoryBytes"), "log": step.get("log")})
            matched = True
        if not matched:
            others.append(job_ref)
    return tasks, others


def evidence_folders(root, folder):
    """A failed or mixed job can retain its receipts in its outputs instead of applying them to the example."""
    yield folder, None
    relative = folder.relative_to(root).as_posix()
    for archive in sorted((root / "verification/results").glob(f"*/outputs/{relative}")):
        result = read_json(archive.parents[2] / "result.json") or {}
        manifest = {o["path"]: o.get("sha256") for o in result.get("outputs", [])}
        yield archive, manifest


def has_evidence(directory, manifest, relative, path):
    """Live receipts use their existing reader. Archived files must match the collector's manifest."""
    if manifest is None:
        return True
    name = (relative / path.relative_to(directory)).as_posix()
    return path.is_file() and manifest.get(name) == workflow.file_sha256(path)


def read_execution(path, task, ident):
    data = read_json(path)
    if isinstance(data, dict) and data.get("schema") == "target-execution/v1" and data.get("id") == ident and data.get("task") == task:
        return data
    return None


def archived_execution(folder, task, ident):
    """Look up the collector's journal for one execution on a fresh checkout."""
    root = folder.parent.parent
    relative = folder.relative_to(root)
    for directory, manifest in evidence_folders(root, folder):
        path = directory / "receipts" / task / "executions" / ident / "attempt.json"
        if manifest is not None and has_evidence(directory, manifest, relative, path):
            record = read_execution(path, task, ident)
            if record is not None:
                return record
    return None


def recorded_evidence(root, folder):
    receipts, journals = {}, defaultdict(dict)
    relative = folder.relative_to(root)
    for directory, manifest in evidence_folders(root, folder):
        for record in workflow.attempts(directory):
            path = directory / record["path"]
            key = record["task"], record["attempt"]
            if key not in receipts and all(has_evidence(directory, manifest, relative, p)
                                           for p in (path, path.parent / workflow.PLAN_RECORD)):
                receipts[key] = {**record, "path": os.path.relpath(path, folder)}
        for path in sorted((directory / "receipts").glob("*/executions/*/attempt.json")):
            task, ident = path.parents[2].name, path.parent.name
            if ident not in journals[task] and has_evidence(directory, manifest, relative, path):
                data = read_execution(path, task, ident)
                if data is not None:
                    journals[task][ident] = (data, os.path.relpath(path, folder))
    return [receipts[k] for k in sorted(receipts)], journals


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
            "firstBlocker": evidence.get("problem") or (attempt.get("execution") or {}).get("reason"),
            "restsOn": rests, "limits": limits, "id": a["attempt"], "path": a["path"], "claimKey": (claim.get("target") or {}).get("claimKey") or recorded_key,
            "sourceFile": (claim.get("statement", {}).get("claim") or {}).get("file"),
            "revisions": claim.get("statement", {}).get("revisions", []), "preparedClaim": claim.get("id"), "taskInputsCurrent": a["path"] in current,
            "problem": a["problem"], "execution": a["execution"], "conclusion": a["status"],
            "vacuous": conclusion.get("vacuous"), "engine": attempt.get("engine"),
            "ingestedAt": attempt.get("startedAt"), "seconds": attempt.get("seconds"),
            "pipeline": attempt.get("pipeline"), "replay": (document.get("evidence") or {}).get("replay"),
        })
    return receipts


def binding_groups(executions, evidence):
    groups = {}
    for run in executions:
        identity = run.get("bindingId") or run.get("preparedClaim")
        group = groups.setdefault(identity, {"binding": identity, "executions": [], "preparedClaims": [], "evidence": []})
        group["executions"].append(run["id"])
        claim = run.get("preparedClaim")
        if claim and claim not in group["preparedClaims"]:
            group["preparedClaims"].append(claim)
        group["latestAttempt"] = run["id"]
    for group in groups.values():
        group["evidence"] = [e for e in evidence if e.get("preparedClaim") in group["preparedClaims"]]
    return list(groups.values())


def inventory(folder, example, target, claim_filter=None, revision=None):
    folder = Path(folder).resolve()
    root = folder.parent.parent
    claims, replays = {}, []
    receipts, journals = recorded_evidence(root, folder)
    from targets import finite_check, native_selectors
    finite_batches = finite_check.recorded_batches(folder)
    selector_roots = native_selectors.evidence_roots(folder)
    jobs, other_jobs = job_history(root, folder, example["id"])
    history = [read_json(path) for path in sorted((folder / "history").glob("*.json"))]
    source = accept.Source(root)
    if revision and revision not in target["history"]["revisions"]:
        raise ValueError(f"unknown revision {revision!r} for {example['id']}")

    declared = {task["id"]: task for task in target["tasks"]}
    for name in dict.fromkeys([*declared, *(r["task"] for r in receipts), *journals]):
        task = declared.get(name, {"id": name, "kind": "historical"})
        revisions = list(workflow.revisions_of(target, task)) if name in declared else []
        plan = workflow.plan_task(folder, example, target, name) if name in declared else Unsupported(
            "task-plan", "history", "this task was removed from the sidecar")
        key = None if isinstance(plan, Unsupported) else plan.claim["key"]
        file = task.get("claim")
        entries = receipt_history(folder, plan, [a for a in receipts if a["task"] == name])
        linked = jobs.get(name, [])
        dated_jobs = [j for j in linked if j["jobFinishedAt"]]
        previous = [entry for entry in history if entry and entry.get("task") == name
                    and entry.get("claimKey") == key and entry.get("revisions") == revisions]
        executions = []
        for data, path in journals.get(name, {}).values():
            executions.append({**{k: data.get(k) for k in ("id", "claimKey", "revisions", "preparedClaim", "bindingId", "status",
                               "startedAt", "retryOf", "lastCompletedStage", "firstBlocker", "missing", "refusal", "injected",
                               "job", "budget", "budgetExhausted", "usage", "strategy", "receipt")}, "path": path})
        by_id = {r["id"]: r for r in entries}
        for e in executions:
            if not e.get("firstBlocker") and e["id"] in by_id:
                e["firstBlocker"] = by_id[e["id"]]["firstBlocker"]
        known = {e["id"] for e in executions}
        for r in entries:
            if r["id"] not in known:
                executions.append({"id": r["id"], "claimKey": r["claimKey"], "revisions": r["revisions"] or revisions,
                                   "preparedClaim": r["preparedClaim"], "status": r["execution"], "path": r["path"],
                                   "startedAt": r["ingestedAt"], "firstBlocker": r["firstBlocker"], "lastCompletedStage": "receipt-published"})
        executions.sort(key=lambda e: e["id"])
        scopes = defaultdict(list)
        for execution in executions:
            scopes[execution["claimKey"], tuple(execution["revisions"])].append(execution)
        for (old_key, old_revisions), runs in scopes.items():
            if not old_key or (key, tuple(revisions)) == (old_key, old_revisions):
                continue
            historic = [r for r in entries if r["claimKey"] == old_key and tuple(r["revisions"]) == old_revisions]
            old_file = next((r["sourceFile"] for r in historic if r["sourceFile"]), file)
            if (claim_filter and claim_filter not in (old_key, old_file)) or (revision and revision not in old_revisions):
                continue
            group = claims.setdefault(old_key, {"claimKey": old_key, "file": old_file, "subjects": []})
            group["subjects"].append({"task": name, "revisions": list(old_revisions), "historical": True,
                                      "conclusion": "archived", "latestEligible": None, "evidence": [],
                                      "receipts": historic, "executions": runs, "latestAttempt": runs[-1],
                                      "bindings": binding_groups(runs, [])})
        if (name not in declared or (revision and revision not in revisions)
                or (claim_filter and claim_filter not in (file, key))):
            continue
        row = {
            "task": name, "kind": task["kind"], "revisions": revisions,
            "expected": task.get("expected"), "parent": task.get("parent"), "requires": task.get("requires", []),
            "executions": executions,
            "latestAttempt": next((e for e in reversed(executions) if e["claimKey"] == key), None),
            "receipts": [r for r in entries if not r["path"].startswith("../")],
            "archivedReceipts": [r for r in entries if r["path"].startswith("../")],
            "jobs": linked, "historicalProbes": previous,
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
        row["bindings"] = binding_groups(scopes.get((key, tuple(revisions)), []), row["evidence"])
        row["latestEligible"] = row["evidence"][-1] if row["evidence"] else None
        answers = {e["answer"] for e in row["evidence"]}
        row["conclusion"] = "disputed" if len(answers) > 1 else next(iter(answers), "open")
        if finite_batches and not isinstance(plan, Unsupported):
            row["finiteJvm"] = finite_check.evidence(folder, plan, finite_batches)
            finite_answers = {r["status"] for r in row["finiteJvm"]}
            row["overallConclusion"] = disposition(answers | finite_answers)
        if selector_roots and not isinstance(plan, Unsupported):
            if checked := native_selectors.evidence(folder, plan, selector_roots):
                row["nativeSelectors"] = checked
                row["overallConclusion"] = disposition(answers | {r["status"] for r in row.get("finiteJvm", [])}
                                                        | {r["status"] for r in checked})
        if not isinstance(plan, Unsupported) and (folder / "records/original-witnesses" / name).is_dir():
            from targets import original_witness
            if lifted := original_witness.evidence(folder, plan):
                row["originalWitnesses"] = lifted
                row["overallConclusion"] = disposition({row.get("overallConclusion", row["conclusion"]), "refuted"})
        # Unplannable tasks cannot share a key by virtue of both missing it.
        group = claims.setdefault(key or (file, name), {"claimKey": key, "file": file, "subjects": []})
        if isinstance(plan, Unsupported):
            row["planningProblem"] = plan.describe()
        group["subjects"].append(row)
    if claim_filter and not claims and not replays:
        raise ValueError(f"no claim {claim_filter!r} matches the selected revision of {example['id']}")
    required = {}
    finite = defaultdict(set)
    additional = defaultdict(set)
    for group in claims.values():
        for subject in group["subjects"]:
            if subject.get("expected") and group["claimKey"]:
                pair = group["claimKey"], tuple(subject["revisions"])
                required.setdefault(pair, set()).add(subject["conclusion"])
                finite[pair].update(r["status"] for r in subject.get("finiteJvm", []))
                for key in ("nativeSelectors", "originalWitnesses"):
                    additional[pair].update(r["status"] for r in subject.get(key, []))
    coverage = {"requiredClaimSubjects": len(required), "decidedClaimSubjects": sum(
        len(answers) == 1 and bool(answers & {"established", "refuted"}) for answers in required.values())}
    if finite_batches:
        coverage["exhaustiveJvm"] = disposition_counts(finite.values())
    if finite_batches or any(additional.values()):
        coverage["allRoutes"] = disposition_counts(required[pair] | finite[pair] | additional[pair] for pair in required)
    return {"schema": "example-claim-history/v1", "example": example["id"], "claims": list(claims.values()),
            "coverage": coverage,
            "replays": replays, "otherExampleJobs": other_jobs}


def disposition(answers):
    decided = answers & {"established", "refuted"}
    if "disputed" in answers or len(decided) > 1:
        return "disputed"
    return next(iter(decided), "open")


def disposition_counts(groups):
    counts = dict.fromkeys(("established", "refuted", "open", "disputed"), 0)
    for group in groups:
        counts[disposition(group)] += 1
    return counts


def markdown(value):
    lines = [f"# Example {value['example']} claim history", ""]
    for group in value["claims"]:
        for subject in group["subjects"]:
            last = subject["latestAttempt"]
            lines.extend([f"## {subject['task']}", "", f"Source claim `{group['claimKey']}` on "
                          + ", ".join(subject["revisions"]) + f". Eligible conclusion: {subject['conclusion']}.", ""])
            if last:
                lines.append(f"Latest execution [{last['id']}]({last['path']}) reached {last['lastCompletedStage']}.")
                if last.get("firstBlocker"):
                    lines.append("First blocker: " + last["firstBlocker"])
                if last.get("missing"):
                    lines.append("Missing evidence: " + ", ".join(last["missing"]) + ".")
            lines.append("")
            if "overallConclusion" in subject:
                lines.extend([f"Across the checked routes this claim is **{subject['overallConclusion']}**.", ""])
            for proof in subject.get("finiteJvm", []):
                lines.append(f"- Exhaustive JVM {proof['status']} on {proof.get('inputs') or 0} admitted inputs "
                             f"([finite evidence]({proof['receipt']})).")
            for proof in subject.get("nativeSelectors", []):
                lines.append(f"- Native case analysis {proof['status']}, with {proof.get('checked', 0)} of "
                             f"{proof.get('admitted', 0)} admitted selectors checked. [Native evidence]({proof['record']})")
            for proof in subject.get("originalWitnesses", []):
                lines.append(f"- Original startup refuted by a native candidate replayed on the unmodified JVM. "
                             f"[Original witness]({proof['file']})")
            for record in subject["evidence"]:
                link = record.get("receipt") or record.get("job")
                lines.append(f"- {record['answer']} ([evidence]({link}))")
                lines.extend("  - Rests on " + reason for reason in record.get("restsOn", []) if reason)
                lines.extend("  - Limit: " + reason for reason in record.get("limits", []) if reason)
            earlier = [e for e in subject["executions"] if last and e["id"] != last["id"]
                       and e["claimKey"] == group["claimKey"] and e["revisions"] == subject["revisions"]]
            if earlier:
                lines.extend(["", "Earlier executions", ""])
                for e in reversed(earlier):
                    flags = [label for key, label in (("injected", "injected stop"), ("budgetExhausted", "budget exhausted")) if e.get(key)]
                    if e["id"] == last.get("retryOf"):
                        flags.append("retried by the latest execution")
                    detail = ", ".join([e["status"] or "recorded", *flags])
                    lines.append(f"- [{e['id']}]({e['path']}) reached {e['lastCompletedStage']} ({detail}).")
            lines.append("")
    return "\n".join(lines) + "\n"

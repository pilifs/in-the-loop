"""Write-ahead execution history beside target receipts. A retry owns a new directory."""

import hashlib
import json
import os
import platform
import re
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from targets import workflow
from checker_output import solver_candidate
from targets.interfaces import RUNTIME, Unsupported

ID = re.compile(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}")


def now():
    return datetime.now(timezone.utc)


def new_id(start):
    return f"{start:%Y%m%dT%H%M%SZ}-{start.microsecond:05x}{os.urandom(2).hex()[:3]}"


def save(path, value):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    os.replace(stream.name, path)


def completion_problem(directory, journal, verifier):
    """Check a delivered result against the invocation and raw candidate saved before qualification."""
    if verifier is None:
        return None
    recorded = directory / "checker.json"
    if not recorded.is_file():
        return "the original execution has no checker record"
    raw = json.loads(recorded.read_text())
    if (raw.get("argv") != list(verifier.argv) or raw.get("status") != verifier.status
            or raw.get("exitCode") != verifier.exitCode or raw.get("outcomes") != list(verifier.observations or [])):
        return "the delivered result differs from the original checker record"
    if verifier.status == "exited":
        bound = journal.get("checker") or {}
        if journal.get("argv") != list(verifier.argv) or not bound.get("jvmcontract") or any(
                bound.get(k) != verifier.identities.get(k) for k in ("jvmcontract", "jdkRelease", "classpath", "recipe", "checkedEntry")):
            return "the delivered verifier or classpath differs from the bound invocation"
    review = directory / "replay.json"
    if review.is_file() and json.loads(review.read_text()) != verifier.identities.get("independentReplay"):
        return "the delivered replay differs from the recorded JVM qualification"
    return None


class Execution:
    def __init__(self, directory, state):
        self.directory = directory
        self.state = state
        self.started = time.monotonic()

    @classmethod
    def start(cls, out, plan, timeout, retry_of=None):
        history = out / "executions"
        previous = {}
        if retry_of:
            from targets.claim_history import archived_execution, read_execution
            if not ID.fullmatch(retry_of):
                return Unsupported("run-verifier", RUNTIME, "invalid retry execution ID", stage="retry")
            prior = history / retry_of / "attempt.json"
            folder = Path(plan.folder).resolve()
            previous = read_execution(prior, plan.task, retry_of)
            if not prior.exists() and out.resolve() == folder / plan.outputs["receipts"]:
                previous = archived_execution(folder, plan.task, retry_of)
            if previous is None:
                return Unsupported("run-verifier", RUNTIME, "retry execution is absent from this task or its journal is invalid", stage="retry")
            if previous.get("claimKey") != plan.claim.get("key") or previous.get("revisions") != list(plan.revisions):
                return Unsupported("run-verifier", RUNTIME, "retry execution belongs to a different claim or revision", stage="retry")
        history.mkdir(parents=True, exist_ok=True)
        while True:
            start = now()
            execution = new_id(start)
            directory = history / execution
            try:
                directory.mkdir()
                break
            except FileExistsError:
                continue
        state = {"schema": "target-execution/v1", "id": execution, "task": plan.task, "claimKey": plan.claim.get("key"),
                 "revisions": list(plan.revisions), "startedAt": start.isoformat(), "retryOf": retry_of,
                 "retryBinding": previous.get("bindingId"), "budget": {"checkerSeconds": timeout}, "strategy": {"engine": plan.engine, "gaps": plan.gaps},
                 "host": {"machine": platform.machine(), "kernel": platform.release(), "node": platform.node()},
                 "job": os.getenv("VERIFY_JOB_ID"), "sourceCommit": os.getenv("VERIFY_SOURCE_COMMIT"),
                 "cache": "fresh verifier work directory", "stages": [], "status": "running"}
        run = cls(directory, state)
        run.stage("planned")
        return run

    def stage(self, name, **fields):
        self.state["stages"].append({"stage": name, "elapsedSeconds": round(time.monotonic() - self.started, 4)})
        self.state.update(lastCompletedStage=name, **fields)
        save(self.directory / "attempt.json", self.state)

    def prepared(self, prepared, complete=True):
        bindings = {}
        for rev, p in prepared.items():
            by_path = {a.path: a for a in p.artifacts}
            bindings[rev] = {"revision": p.commit, "target": p.source.get("target"), "jdk": p.toolchain.get("jdk"),
                             "classpath": [asdict(by_path[path]) for path in p.classpath]}
            if "originalCompiler" in p.toolchain:
                bindings[rev]["originalCompiler"] = p.toolchain["originalCompiler"]
        identity = [{"revision": name, "commit": item["revision"], "target": item["target"],
                     "jdkRelease": (item["jdk"] or {}).get("release"),
                     "classpath": [(a["role"], a["sha256"]) for a in item["classpath"]],
                     **({"originalCompiler": item["originalCompiler"]} if "originalCompiler" in item else {})}
                    for name, item in bindings.items()]
        self.stage("artifacts-ready" if complete else "revision-prepared", bindings=bindings,
                   bindingId=workflow.canonical_digest([self.state["claimKey"], identity]) if complete else None)

    def launching(self, argv, identities):
        self.stage("invocation-bound", argv=list(argv), checker=identities)

    def checked(self, record):
        outcomes = list(record.observations or [])
        snapshot = {"argv": list(record.argv), "status": record.status, "exitCode": record.exitCode,
                    "seconds": record.seconds, "reason": record.reason, "outcomes": outcomes}
        if record.directory:
            for name in ("stdout", "stderr"):
                path = Path(record.directory) / getattr(record, name)
                if path.is_file():
                    with path.open("rb") as stream:
                        snapshot[name] = {"bytes": path.stat().st_size, "sha256": hashlib.file_digest(stream, "sha256").hexdigest()}
                        if name == "stderr" or not outcomes:
                            stream.seek(0)
                            snapshot[name]["excerpt"] = stream.read(4096).decode(errors="replace")
        save(self.directory / "checker.json", snapshot)
        candidate = any(solver_candidate(o) for o in outcomes)
        exhausted = record.status == "timed-out" or any(
            o.get("verdict") == "unverifiable" and ((o.get("search") or {}).get("runs") or [{}])[-1].get("ending") == "timeout"
            for o in outcomes)
        self.stage("candidate-recorded" if candidate else "checker-returned", budgetExhausted=exhausted,
                   usage=record.identities.get("usage"), checkerEvidence="checker.json",
                   checkerStatus=record.status, checkerSeconds=record.seconds,
                   missing=["independent witness qualification", "receipt"] if candidate else ["receipt"])
        return candidate

    def refuse(self, result, injected=False):
        self.state.update(status="interrupted" if injected else "refused", refusal=asdict(result),
                          injected=injected, endedAt=now().isoformat())
        save(self.directory / "attempt.json", self.state)
        return result

    def finish(self, receipt):
        result = self.directory.parents[1] / receipt.attempt / "result.json"
        stored = json.loads(result.read_text()) if result.is_file() else {}
        problem = (stored.get("evidence") or {}).get("problem") or (
            ((stored.get("attempt") or {}).get("execution") or {}).get("reason"))
        self.stage("receipt-published", status=receipt.execution, receipt=receipt.path,
                   preparedClaim=receipt.claim, firstBlocker=problem, missing=["eligible conclusion"] if problem else [],
                   endedAt=now().isoformat())

"""Whether a committed job may start, and why not: one decision, for the runner that makes it and for every view
that reports it.

A job that is in the queue and has not started is in one of these states, each with its reason:

  - `invalid`: its file is not a job (not JSON, or not as its schema says). It is never run, and the diagnostic
    carries its path and the revision it was read at.
  - `unschedulable`: this machine cannot run it as it is written, and waiting does not change that: it asks for
    more than the runner allows a job, for an adapter this checkout does not have, or for a step with no network
    where the network cannot be taken away. Resubmit it, or run it elsewhere.
  - `blocked`: a prerequisite ended without being fulfilled, or is not a job anyone submitted. Nothing of the job
    runs and no attempt is consumed. It stays blocked until the prerequisite is superseded by a job that passes.
  - `waiting`: a prerequisite has not finished, or a readiness receipt it needs is not there yet.
  - `deferred`: it could run, and the runner is holding it back for now: no room, a priority under the runner's
    minimum, every fetch slot taken. Only a runner at work says this.
  - `queued`: nothing stands in its way.

A prerequisite on a job is satisfied by a passed result of that job or of any job that supersedes it, so a
resubmission of a failed prerequisite releases its dependents without their files being edited (a job file is
not changed after it is committed). A cancelled job runs again, and so counts as not finished.

Standard library only.
"""
from __future__ import annotations

STATES = ("invalid", "unschedulable", "blocked", "waiting", "deferred", "queued")
TERMINAL = ("passed", "failed", "timeout", "out-of-memory", "error")   # `cancelled` runs again


class Known:
    """What is known of every job, to decide about the ones that have not started: each job's file, the status of
    each result (staged on this machine, collected, or recorded on another head) and the jobs running now."""

    def __init__(self, specs: dict, statuses: dict, running=()):
        self.specs, self.statuses, self.running = specs, statuses, set(running)
        self.superseders = {}
        for job_id, job in specs.items():
            if isinstance(job, dict) and job.get("supersedes"):
                self.superseders.setdefault(job["supersedes"], []).append(job_id)

    def line(self, job_id: str) -> list[str]:
        """The job and every job that supersedes it, directly or through another, oldest first."""
        seen, todo = [], [job_id]
        while todo:
            current = todo.pop(0)
            if current in seen:
                continue
            seen.append(current)
            todo += sorted(self.superseders.get(current, []))
        return seen

    def ring(self, job_id: str) -> list[str] | None:
        """The jobs from `job_id` back to itself through what each needs, when its needs lead back to it: none of
        them can ever start. Only jobs that have not finished are followed."""
        def walk(current: str, path: list[str]) -> list[str] | None:
            for need in (self.specs.get(current) or {}).get("needs") or []:
                other = need.get("job") if isinstance(need, dict) else None
                found = self.outcome(other) if other else None
                if not found or found["state"] != "pending":
                    continue
                if found["by"] == job_id:
                    return [*path, job_id]
                if found["by"] not in path:
                    back = walk(found["by"], [*path, found["by"]])
                    if back:
                        return back
            return None
        return walk(job_id, [job_id])

    def outcome(self, job_id: str) -> dict:
        """What became of the work a job id stands for: `fulfilled` (it, or a job that supersedes it, passed),
        `pending` (one of them has not finished), `unfulfilled` (every one of them ended, none passed) or
        `unknown` (no such job, and no result of one)."""
        line = self.line(job_id)
        for candidate in line:
            if self.statuses.get(candidate) == "passed":
                return {"state": "fulfilled", "by": candidate}
        for candidate in line:
            if candidate in self.running or (candidate in self.specs and self.statuses.get(candidate) not in TERMINAL):
                return {"state": "pending", "by": candidate}
        ended = [c for c in line if self.statuses.get(c) in TERMINAL]
        if ended:
            return {"state": "unfulfilled", "by": ended[-1], "status": self.statuses.get(ended[-1])}
        return {"state": "unknown", "by": job_id}


def prerequisites(job: dict, known: Known, readiness=None) -> list[dict]:
    """Each prerequisite of a job with its state: `satisfied`, `waiting`, `failed` or `unknown`. `readiness(key)`
    answers for a readiness receipt with the same four words and a reason (jobs/readiness.py); without it a
    readiness prerequisite is `unknown`."""
    out = []
    ring = known.ring(job["id"]) if job.get("id") and any("job" in need for need in job.get("needs") or []) else None
    for need in job.get("needs") or []:
        if "job" in need:
            found = known.outcome(need["job"])
            other = found["by"]
            via = f" (which supersedes {need['job']})" if other != need["job"] else ""
            if ring and found["state"] == "pending" and other == ring[1 % len(ring)]:
                out.append({"job": need["job"], "state": "failed", "by": other,
                            "why": f"its needs lead back to itself ({' needs '.join(ring)}): none of them can start; resubmit one without the need"})
                continue
            state, why = {
                "fulfilled": ("satisfied", f"{other}{via} passed"),
                "pending": ("waiting", f"{other}{via} has not finished"),
                "unfulfilled": ("failed", f"{other}{via} ended {found.get('status')}: resubmit it, and this job runs once that one passes"),
                "unknown": ("unknown", f"{need['job']} is not a job in the queue, and no result of it is recorded"),
            }[found["state"]]
            out.append({"job": need["job"], "state": state, "by": other, "why": why})
        elif "readiness" in need:
            answer = readiness(need["readiness"]) if readiness else {"state": "unknown", "why": "nothing here reads readiness receipts"}
            out.append({"readiness": need["readiness"], **answer})
        else:
            out.append({**need, "state": "unknown", "why": "not a prerequisite the pipeline knows"})
    return out


def decide(job: dict, problems: list, cannot_run: list, needs: list[dict]) -> tuple[str, str | None]:
    """The state of a job that has not started, and the reason, from what is true whoever looks: the problems of
    its file, why this machine can never run it, and its prerequisites. A runner adds `deferred` to this."""
    if problems:
        return "invalid", "; ".join(problems[:5])
    if cannot_run:
        return "unschedulable", "; ".join(cannot_run)
    stuck = [n for n in needs if n["state"] in ("failed", "unknown")]
    if stuck:
        return "blocked", "; ".join(n["why"] for n in stuck)
    waiting = [n for n in needs if n["state"] == "waiting"]
    if waiting:
        return "waiting", "; ".join(n["why"] for n in waiting)
    return "queued", None

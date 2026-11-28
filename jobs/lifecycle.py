"""What became of a job, read off its records, with each question kept apart from the others.

A result's `status` is one word, and one word answered several questions at once: a job whose every step exited
0 `passed` with a required file missing, with zero tests run (VF-070), or while its checker refuted the claim it
was about. Here they are separate, and each is computed by one function, for the runner that writes a result
today and for a reader of a result written before these blocks were kept (`derived: true` then):

  - `execution(result)`: what the processes did. Planned, run and skipped steps, and where and why it stopped.
  - `fulfillment(job, result)`: whether the job delivered what it declared. Steps that exited as expected, promises
    kept (jobs/evidence.py), every required output there. A job is `fulfilled`, `unfulfilled` with each reason, or
    `undetermined` (it was cancelled and runs again).
  - `timing(job, result)`: what it cost, by scope. Queue wait, the attempt's elapsed time, preparation, the
    requested steps, and their phases, each with its state: `measured` (a measured zero is one), `derived`,
    `partial`, `not-run`, `unknown`.

The domain conclusion (a checker's verdict) is the workload's (`conclusion` in jobs/workloads/), and capture,
collection, application and hooks are recorded by the steps that do them (`originals`, `collected`).

Standard library only.
"""
from __future__ import annotations

import datetime as dt

SCHEMA = "itl-job-lifecycle/v1"   # the one view of every job (pipeline.lifecycle_view), which every report renders
# The state a job is in, in a view. Not started: uncommitted, or one of jobs/scheduling.py's. Started: running,
# finished (a result on this machine, not collected), collected, or recorded on a head this working copy is not on.
STATES = ("uncommitted", "invalid", "unschedulable", "blocked", "waiting", "deferred", "queued", "running", "finished",
          "collected", "recorded-elsewhere")
PHASES = ("resolve", "fetch", "prepare", "build", "test", "proof", "other")


def _requested(result: dict) -> list[dict]:
    return [s for s in result.get("steps") or [] if s.get("index", 0) > 0]


def _exit_went_as_expected(step: dict) -> bool:
    """Whether the step's process ended as the job expected, whatever became of what the step promised."""
    if step.get("status") == "passed":
        return True
    return bool(step.get("unmet")) and step.get("exitCode") in (step.get("expectExit") or [0])


def _stop(step: dict) -> dict:
    """Why a step that did not go as expected ended as it did, in the pipeline's words."""
    status = step.get("status")
    if step.get("unmet") and _exit_went_as_expected(step):
        reason = "unmet-promise"
    elif status == "timeout":
        reason = {"stalled": "stalled", "ceiling": "ceiling"}.get(step.get("stoppedFor"), "timeout")
    elif status == "out-of-memory":
        reason = "memory-limit" if step.get("limitOoms", 1) else "machine-memory"
    elif status == "cancelled":
        reason = "cancelled"
    elif step.get("index", 0) == 0:
        reason = "preparation"
    elif step.get("signal"):
        reason = "signal"
    else:
        reason = "exit"
    return {"step": step.get("index"), "name": step.get("name"), "reason": reason,
            **({"exitCode": step["exitCode"]} if step.get("exitCode") is not None else {}),
            **({"signal": step["signal"]} if step.get("signal") else {})}


def execution(result: dict) -> dict:
    """What the processes did: `status` is the result's own unless the result failed only for what it did not
    deliver, in which case every process went as expected and this says `passed`."""
    steps = result.get("steps") or []
    asked = _requested(result)
    ran = [s for s in asked if s.get("status") != "skipped" and s.get("wallSeconds") is not None]
    went = [s for s in ran if _exit_went_as_expected(s)]
    skipped = [s for s in asked if s.get("status") == "skipped"]
    status = result.get("status")
    stopped = None
    if status == "failed" and ran and len(went) == len(ran) and not skipped:
        status = "passed"   # every step ran, and every process ended as expected: what is missing is not execution's
    else:
        stopped = next((_stop(s) for s in steps if s.get("status") not in ("passed", "skipped")), None)
    if stopped is None and status not in ("passed", None):
        # No step says why: the pipeline did not get to run one (a tool missing here, a conflicted source, its own failure).
        why = next(iter(result.get("attention") or []), None)
        stopped = {"step": None, "reason": "machine-memory" if result.get("memoryStop") else "not-run", **({"why": why} if why else {})}
    planned = len((result.get("job") or {}).get("spec", {}).get("steps") or asked)
    return {"status": status,
            "steps": {"planned": planned, "preparation": len(steps) - len(asked), "ran": len(ran),
                      "asExpected": len(went), "skipped": len(skipped)},
            "skipped": [{"step": s.get("index"), "why": s.get("why")} for s in skipped],
            "stopped": stopped}


def fulfillment(job: dict, result: dict) -> dict:
    """Whether the job delivered what it declared, and everything it did not."""
    status = result.get("status")
    if status == "cancelled":
        return {"state": "undetermined", "unmet": [], "why": "the job was stopped before it ended, and runs again"}
    unmet = []
    for s in result.get("steps") or []:
        if s.get("status") in ("passed", "skipped"):
            continue
        if s.get("unmet"):
            unmet += [{"kind": "promise", "step": s.get("index"), "why": why} for why in s["unmet"]]
        elif s.get("index", 0) == 0:
            unmet.append({"kind": "preparation", "step": 0, "why": f"{s.get('name')}: {s.get('status')}"})
        else:
            stop = _stop(s)
            unmet.append({"kind": "step", "step": s.get("index"),
                          "why": f"{stop['reason']}" + (f" {s['exitCode']}, expected {', '.join(map(str, s.get('expectExit') or [0]))}"
                                                        if stop["reason"] == "exit" and s.get("exitCode") is not None else "")})
    skipped = [s for s in _requested(result) if s.get("status") == "skipped"]
    if skipped:
        unmet.append({"kind": "skipped", "steps": [s.get("index") for s in skipped], "why": skipped[0].get("why")})
    for output in result.get("declared") or []:
        if output.get("required") and output.get("state") in ("missing", "never-reached"):
            unmet.append({"kind": "output", "path": output["path"], "state": output["state"],
                          "why": f"required output {output['path']} is not there ({output['state']})"})
    if not unmet and status != "passed":
        why = next(iter(result.get("attention") or []), None) or f"the job ended {status}"
        unmet.append({"kind": "not-run", "why": why})
    return {"state": "unfulfilled" if unmet else "fulfilled", "unmet": unmet}


def _when(text):
    """A time, with its zone: one written without (a job file made by hand) is taken as UTC, so that it can be
    measured against the runner's own."""
    try:
        when = dt.datetime.fromisoformat(text) if text else None
    except (ValueError, TypeError):
        return None
    return when.replace(tzinfo=dt.timezone.utc) if when and when.tzinfo is None else when


def _measure(seconds, state):
    return {"seconds": None if seconds is None else round(seconds, 1), "state": state}


def timing(job: dict, result: dict) -> dict:
    """What the attempt cost, by scope. `elapsed` is the attempt, start to end; `requestedSteps` the steps the job
    asked for; `preparation` what came before them (the export, and what the workload built for the job). A job
    that failed in preparation has an elapsed time, a preparation time and requested steps that were `not-run`:
    41 seconds and 0 seconds are both true of it (20261127-054106), each of its own scope."""
    started, finished = _when(result.get("startedAt")), _when(result.get("finishedAt"))
    elapsed = result.get("wallSeconds")
    if elapsed is None and started and finished:
        elapsed = (finished - started).total_seconds()
    asked = _requested(result)
    ran = [s for s in asked if s.get("wallSeconds") is not None]
    planned = len((job or {}).get("steps") or asked)
    requested = sum(s["wallSeconds"] for s in ran)
    steps_state = "not-run" if not ran else "measured" if len(ran) >= planned else "partial"
    if result.get("preparationSeconds") is not None:
        preparation = _measure(result["preparationSeconds"], "measured")
    elif elapsed is not None:
        # Not measured in a result that did not keep it: what the attempt took beyond its requested steps, which
        # is preparation and the runner's own work around the steps together.
        preparation = _measure(max(elapsed - requested, 0.0), "derived")
    else:
        preparation = _measure(None, "unknown")
    submitted = _when(((job or {}).get("submitted") or {}).get("at"))
    wait = (started - submitted).total_seconds() if started and submitted else None
    block = {
        # From submission to this attempt's start: the wait for a commit, for a runner, for room, for a
        # prerequisite, and any earlier attempt, together.
        "queueWait": _measure(wait, "measured") if wait is not None and wait >= 0 else _measure(None, "unknown"),
        "elapsed": _measure(elapsed, "measured" if elapsed is not None else "unknown"),
        "preparation": preparation,
        "requestedSteps": {**_measure(requested, steps_state), "ran": len(ran), "planned": planned},
        "cpuSeconds": round(sum(s.get("cpuSeconds") or 0 for s in ran), 1) if ran and all(s.get("cpuSeconds") is not None for s in ran) else None,
        "source": "the runner's clock; CPU and peak memory from each step's "
                  + ("systemd scope (cgroup)" if (result.get("runner") or {}).get("isolation") == "systemd" else "process, as the kernel accounts it"),
    }
    phases = {}
    for s in ran:
        if s.get("phase"):
            phases[s["phase"]] = round(phases.get(s["phase"], 0.0) + s["wallSeconds"], 1)
    if phases:
        block["byPhase"] = {p: phases[p] for p in PHASES if p in phases}
    return block


def facets(job: dict, result: dict, derived: bool = False) -> dict:
    """The three blocks for one result. `derived`: computed by a reader from a result that did not keep them."""
    blocks = {"execution": execution(result), "fulfillment": fulfillment(job, result), "timing": timing(job, result)}
    if derived:
        for block in blocks.values():
            block["derived"] = True
    return blocks

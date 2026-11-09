"""What build.py and the verification pipeline call for a task of a real-world example with a target sidecar: the
interfaces (interfaces.py) chained, stopping at the first Unsupported. Coordinator-owned (Phase 0 of
llm-dlc/loops/example-targets.md): the streams implement behind it, in workflow.py and runtime.py.

    plan(folder, example, target, task)  the task's plan as JSON, for `build.py --plan NNN --task T` and the pipeline
    run(folder, example, target, task, workdir)  plan, prepare each revision, controls, verifier, ingest: a Receipt
                                         or the first Unsupported
"""

from pathlib import Path

from targets import interfaces, runtime, workflow
from targets.interfaces import Unsupported


class UnknownTask(ValueError):
    """A task id the sidecar doesn't define."""


def task_ids(target):
    return [t["id"] for t in target["tasks"]]


def resolve(folder, example, target, task):
    """The TaskPlan, or Unsupported. Raises UnknownTask for an id the sidecar doesn't define."""
    if task not in task_ids(target):
        raise UnknownTask(f"example {example['id']} has no task {task!r} (its tasks: {', '.join(task_ids(target)) or 'none'})")
    result = workflow.plan_task(Path(folder), example, target, task)
    if not isinstance(result, (interfaces.TaskPlan, Unsupported)):
        raise TypeError(f"workflow.plan_task returned {type(result).__name__}, not a TaskPlan or Unsupported")
    return result


def plan(folder, example, target, task):
    """The task's plan in build.py's --plan shape: `executable`, and `notExecuted` naming the Unsupported result when
    planning can't resolve it. Pure, like build.py's plan()."""
    result = resolve(folder, example, target, task)
    head = {"example": example["id"], "task": task, "route": "target"}
    if isinstance(result, Unsupported):
        return {**head, "executable": False, "notExecuted": result.describe(), "unsupported": interfaces.to_dict(result)}
    return {**head, "executable": True, "notExecuted": None, **result.as_dict()}


def run(folder, example, target, task, workdir):
    """One attempt at the task: plan, prepare each revision, run the controls and the verifier, ingest. Returns the
    Receipt, or the first Unsupported (a preparation that fails is returned as one, with its stage and diagnostic)."""
    result = resolve(folder, example, target, task)
    if isinstance(result, Unsupported):
        return result
    p = result
    workdir = Path(workdir)
    prepared = {}
    for revision in p.revisions:
        r = runtime.prepare(p, revision, workdir / "prepare" / revision)
        if isinstance(r, Unsupported):
            return r
        if r.stage != "artifacts-ready":
            return Unsupported("prepare", interfaces.RUNTIME, f"revision {revision} is {r.stage}, not artifacts-ready",
                               stage=r.failedStage or r.stage, diagnostic=r.diagnostic)
        prepared[revision] = r
    records = []
    controls = runtime.run_controls(p, prepared, workdir / "controls")
    if isinstance(controls, Unsupported):
        return controls
    records.extend(controls)
    if p.kind != "replay":
        verifier = runtime.run_verifier(p, prepared, workdir / "verifier")
        if isinstance(verifier, Unsupported):
            return verifier
        records.append(verifier)
    receipt = workflow.ingest(p, prepared, tuple(records), Path(folder) / p.outputs.get("receipts", f"receipts/{task}"))
    if not isinstance(receipt, (interfaces.Receipt, Unsupported)):
        raise TypeError(f"workflow.ingest returned {type(receipt).__name__}, not a Receipt or Unsupported")
    return receipt

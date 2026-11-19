"""What build.py and the verification pipeline call for a task of a real-world example with a target sidecar: the
interfaces (interfaces.py) chained, stopping at the first Unsupported. Coordinator-owned (Phase 0 of
llm-dlc/loops/example-targets.md): the streams implement behind it, in workflow.py and runtime.py.

    plan(folder, example, target, task)  the task's plan as JSON, for `build.py --plan NNN --task T` and the pipeline
    run(folder, example, target, task, workdir)  plan, prepare each revision, controls, verifier, ingest: a Receipt
                                         or the first Unsupported
"""

from dataclasses import replace
from pathlib import Path

from targets import executions, interfaces, recipes, runtime, workflow
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
    view = {**head, "executable": True, "notExecuted": None, **result.as_dict()}
    if result.kind != "replay":
        recipe = recipes.translate(result)
        if isinstance(recipe, Unsupported):
            view.update(executable=False, notExecuted=recipe.describe(), unsupported=interfaces.to_dict(recipe))
        else:
            view["proofRecipe"] = recipe.describe()
    return view


def prepare_revision(plan, revision, directory, shared):
    """Reuse only identical source locks in this batch. Each invocation keeps its own relative classpath."""
    if shared is None:
        return runtime.prepare(plan, revision, directory)
    lock = runtime.lock(plan, revision)
    if isinstance(lock, Unsupported) or lock.stage != "source-locked":
        return lock
    key = workflow.canonical_digest([plan.example, plan.target, revision, lock.commit, lock.source])
    prepared = shared.get(key)
    if prepared is None:
        prepared = runtime.prepare(plan, revision, directory)
        if not isinstance(prepared, Unsupported) and prepared.stage == "artifacts-ready":
            shared[key] = prepared
    else:
        if plan.kind == "replay" and prepared.source["target"].get("adapterCallsTarget") is False:
            return Unsupported("prepare", interfaces.RUNTIME, "the shared adapter does not call the replay target", stage="adapter")
        directory.parent.mkdir(parents=True, exist_ok=True)
        directory.symlink_to(Path(prepared.workdir).resolve(), target_is_directory=True)
    return prepared


def run(folder, example, target, task, workdir, *, retry_of=None, interrupt_after_candidate=False, shared=None, checker_seconds=None):
    """One attempt at the task: plan, prepare each revision, run the controls and the verifier, ingest. Returns the
    Receipt, or the first Unsupported (a preparation that fails is returned as one, with its stage and diagnostic)."""
    result = resolve(folder, example, target, task)
    if isinstance(result, Unsupported):
        return result
    p = result
    out = Path(folder) / p.outputs.get("receipts", f"receipts/{task}")
    timeout = runtime.VERIFIER_TIMEOUT if checker_seconds is None else checker_seconds
    if not isinstance(timeout, int) or timeout <= 0:
        return Unsupported("run-verifier", interfaces.RUNTIME, "the checker budget must be a positive number of seconds", stage="budget")
    execution = executions.Execution.start(out, p, timeout, retry_of)
    if isinstance(execution, Unsupported):
        return execution
    workdir = Path(workdir) / execution.state["id"]
    prepared = {}
    for revision in p.revisions:
        r = prepare_revision(p, revision, workdir / "prepare" / revision, shared)
        if isinstance(r, Unsupported):
            return execution.refuse(r)
        if r.stage != "artifacts-ready":
            return execution.refuse(Unsupported("prepare", interfaces.RUNTIME, f"revision {revision} is {r.stage}, not artifacts-ready",
                               stage=r.failedStage or r.stage, diagnostic=r.diagnostic))
        prepared[revision] = r
        execution.prepared(prepared, complete=len(prepared) == len(p.revisions))
    if execution.state.get("retryBinding") and execution.state["bindingId"] != execution.state["retryBinding"]:
        return execution.refuse(Unsupported("prepare", interfaces.RUNTIME, "retry prepared different artifacts or a different JDK",
                                            stage="retry-binding"))
    records = []
    controls = runtime.run_controls(p, prepared, workdir / "controls")
    if isinstance(controls, Unsupported):
        return execution.refuse(controls)
    records.extend(controls)
    execution.stage("controls-returned")
    if p.claim.get("adapter"):
        from targets import qualification
        comparisons, problem = qualification.correspondence(p, prepared, controls)
        executions.save(execution.directory / "correspondence.json", comparisons)
        if problem:
            return execution.refuse(Unsupported("run-controls", interfaces.RUNTIME, problem, stage="adapter-correspondence"))
        execution.stage("adapter-correspondence", correspondenceEvidence="correspondence.json")
    if p.kind != "replay":
        verifier = runtime.run_verifier(p, prepared, workdir / "verifier", before_launch=execution.launching, timeout=timeout)
        if isinstance(verifier, Unsupported):
            return execution.refuse(verifier)
        candidate = execution.checked(verifier)
        if candidate and interrupt_after_candidate:
            return execution.refuse(Unsupported("ingest", interfaces.WORKFLOW,
                                    "injected stop after the checker candidate and before independent qualification",
                                    stage="candidate-recorded", diagnostic=execution.state["id"]), injected=True)
        if candidate:
            from targets import replay_candidate
            entry = verifier.identities.get("checkedEntry") or p.target
            if replay_candidate.supported(entry, p.claim):
                qualified = [replay_candidate.check(p, prepared, o["counterexample"].get("inputs"),
                                                    workdir / "qualification" / str(i), entry)
                             for i, o in enumerate(verifier.observations) if o.get("counterexample")]
                verifier = replace(verifier, identities={**verifier.identities, "independentReplay": qualified})
                executions.save(execution.directory / "replay.json", qualified)
                execution.stage("witness-qualification", replayEvidence="replay.json", missing=["receipt"])
        records.append(verifier)
    records = tuple(replace(r, identities={**r.identities, "executionId": execution.state["id"],
                                           "startedAt": execution.state["startedAt"]}) for r in records)
    receipt = workflow.ingest(p, prepared, records, out)
    if not isinstance(receipt, (interfaces.Receipt, Unsupported)):
        raise TypeError(f"workflow.ingest returned {type(receipt).__name__}, not a Receipt or Unsupported")
    if isinstance(receipt, Unsupported):
        return execution.refuse(receipt)
    execution.finish(receipt)
    return receipt

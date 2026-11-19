"""Public target route shared by build.py and the verification pipeline.

Planning freezes a claim and explains its recipe. Execution binds the revisions, runs independent
controls and the checker, qualifies candidates, and publishes each receipt under its execution ID.
"""

from dataclasses import replace
from pathlib import Path

from targets import executions, interfaces, recipes, runtime, workflow
from targets.interfaces import Unsupported


class UnknownTask(ValueError):
    """A task id the sidecar doesn't define."""


def task_ids(target):
    return [t["id"] for t in target["tasks"]]


def batch_tasks(args):
    """Read the ordered tasks and optional per-task execution IDs from the public batch command."""
    if len(args) not in (3, 5) or args[1] != "--tasks" or len(args) == 5 and args[3] != "--retry-of":
        raise ValueError("usage: build.py ID --tasks TASK,TASK [--retry-of EXECUTION,EXECUTION]")
    tasks = args[2].split(",")
    if len(args) == 3:
        return [(task, None) for task in tasks]
    retries = args[4].split(",")
    if len(retries) != len(tasks) or not all(executions.ID.fullmatch(value) for value in retries):
        raise ValueError("--retry-of needs one execution ID for each task, in the same order")
    return list(zip(tasks, retries))


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
    if p.kind != "replay":
        recipe = recipes.translate(p)
        if isinstance(recipe, Unsupported):
            return execution.refuse(recipe)
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


def review_witness(folder, example, target, task, witness, workdir):
    """Replay a supplied concrete input on a frozen proof claim and retain even a late rejection."""
    import json
    from targets import replay_candidate
    plan = resolve(folder, example, target, task)
    if isinstance(plan, Unsupported):
        return plan
    recipe = recipes.translate(plan)
    if isinstance(recipe, Unsupported):
        return recipe
    try:
        supplied = json.loads(Path(witness).read_text())
        inputs = supplied["inputs"]
        if not isinstance(inputs, list):
            raise ValueError("inputs must be a list of typed arguments")
    except (KeyError, TypeError, ValueError, OSError) as error:
        return Unsupported("replay-witness", interfaces.RUNTIME, str(error), stage="read-witness")
    out = Path(folder) / plan.outputs["receipts"]
    run = executions.Execution.start(out, plan, None)
    run.stage("witness-supplied", strategy={"engine": "jvm", "operation": "review-witness"},
              budget={"jvmSecondsPerRevision": 30}, witnessFile=Path(witness).name,
              witnessSha256=workflow.file_sha256(witness))
    executions.save(run.directory / "candidate.json", supplied)
    work = Path(workdir) / run.state["id"]
    prepared = {}
    for revision in plan.revisions:
        p = runtime.prepare(plan, revision, work / "prepare" / revision)
        if isinstance(p, Unsupported):
            return run.refuse(p)
        if p.stage != "artifacts-ready":
            return run.refuse(Unsupported("prepare", interfaces.RUNTIME, p.diagnostic or p.stage, stage=p.failedStage))
        prepared[revision] = p
        run.prepared(prepared, complete=len(prepared) == len(plan.revisions))
    if recipe.correspondence:
        from targets import qualification
        controls = runtime.run_controls(plan, prepared, work / "controls")
        if isinstance(controls, Unsupported):
            return run.refuse(controls)
        comparisons, problem = qualification.correspondence(plan, prepared, controls)
        executions.save(run.directory / "correspondence.json", comparisons)
        if problem:
            return run.refuse(Unsupported("replay-witness", interfaces.RUNTIME, problem, stage="adapter-correspondence"))
    report = replay_candidate.check(plan, prepared, inputs, work / "replay", recipe.entry)
    executions.save(run.directory / "replay.json", report)
    run.stage("witness-replayed", status="witness-reproduced" if report["reproduced"] else "replay-rejected",
              firstBlocker=report.get("reason"), replayEvidence="replay.json", endedAt=executions.now().isoformat(),
              missing=[] if report["reproduced"] else ["an admitted witness differing on a selected observation"])
    return {"execution": run.state["id"], "claimKey": plan.claim["key"], "status": run.state["status"],
            "reason": report.get("reason"), "path": (run.directory / "replay.json").relative_to(folder).as_posix()}

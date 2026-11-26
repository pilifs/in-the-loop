#!/usr/bin/env python3
"""Write an example's designed claims and tasks from stage 2's plan, and check them before anything is built
(llm-dlc/runtime.md, stage 3): the first step of a setup, so that the session spends its time on the artifacts and
the evidence the plan asks for, not on the files' shapes.

    python3 examples/tools/scaffold_example.py NNN                 from llm-dlc/loop-summaries/prove-change/plan.json
    python3 examples/tools/scaffold_example.py NNN --plan PATH     from another plan
    python3 examples/tools/scaffold_example.py NNN --check         write nothing: say what writing would do

It takes the plan's entry for NNN, which must be one whose claims stage 2 designed (`"review": "designed"`), and:

1. writes each of its `claimFiles` into the example's folder, after checking it against
   examples/schema/target-claim.schema.json. A claim file that is there already with other content is refused: a
   frozen claim changes only by a new review;
2. adds each of its `tasks` to the sidecar, refusing a task id that is there already as another task;
3. checks the sidecar against its schema and its own consistency (examples/tools/targets/sidecar.py). What fails
   there because the setup has not made it yet (the mutant's revision and patch, a driver, an oracle) is printed
   as what is left for the setup, and doesn't stop the scaffold.

It decides nothing: the claims are the plan's, and the semantic work (the oracle, the drivers, the adapter, the
replays) stays the setup session's. Exit 0 when it wrote (or would write) everything, 1 when it refused.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from targets import sidecar  # noqa: E402

PLAN = REPO / "llm-dlc/loop-summaries/prove-change/plan.json"


def claim_problems(doc: dict) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["cannot be checked: the Python module jsonschema is not installed"]
    schema = json.loads((REPO / "examples/schema/target-claim.schema.json").read_text())
    return [f"{'/'.join(map(str, e.absolute_path)) or '(top level)'}: {e.message}"[:300]
            for e in jsonschema.Draft202012Validator(schema).iter_errors(doc)]


def scaffold(number: str, plan_path: Path, write: bool, root: Path = REPO) -> dict:
    out = {"example": number, "wrote": [], "added": [], "refused": [], "leftForSetup": []}
    try:
        plan = json.loads(plan_path.read_text())
    except (OSError, ValueError) as e:
        out["refused"].append(f"no plan to read at {plan_path}: {e}")
        return out
    entry = next((e for e in plan.get("examples") or [] if e.get("id") == number), None)
    folder = next(iter(sorted((root / "examples").glob(f"{number}-*"))), None)
    if entry is None:
        out["refused"].append(f"the plan has no entry for {number}")
    elif entry.get("review") != "designed":
        out["refused"].append(f"{number}'s claims were {entry.get('review')} in the plan, not designed: nothing to write")
    if folder is None:
        out["refused"].append(f"no example {number} under examples/")
    if out["refused"]:
        return out
    example = json.loads((folder / "example.json").read_text())
    target_path = sidecar.path_of(folder, example) or folder / "target.json"
    deployments = entry.get("preparedDeployments") or {}
    numbered = entry.get("publicComparison")
    if numbered is not None and deployments:
        out["refused"].append("choose either the numbered public comparison or prepared manifests")
        return out
    public_bundle_only = (bool(deployments.get("registration")) or numbered is not None) and not target_path.exists() and not entry.get("tasks")
    target = {} if public_bundle_only else json.loads(target_path.read_text())
    claims = entry.get("claimFiles") or {}
    for name, doc in claims.items():
        if not name.startswith("claims/") or ".." in name or not name.endswith(".json"):
            out["refused"].append(f"{name}: a claim file is claims/NAME.json in the example's folder")
            continue
        problems = claim_problems(doc)
        if problems:
            out["refused"].append(f"{name}: " + "; ".join(problems[:3]))
            continue
        path = folder / name
        if path.exists():
            try:
                same = json.loads(path.read_text()) == doc
            except ValueError:
                same = False
            if not same:
                out["refused"].append(f"{name} is there already with other content: a frozen claim changes only by a new review")
            continue
        out["wrote"].append(name)
    tasks = list(target.get("tasks") or [])
    have = {t["id"]: t for t in tasks}
    for task in entry.get("tasks") or []:
        if task.get("claim") and task["claim"] not in claims and not (folder / task["claim"]).exists():
            out["refused"].append(f"task {task.get('id')}: its claim {task['claim']} is neither in the plan nor in the example")
        elif task.get("id") in have:
            if have[task["id"]] != task:
                out["refused"].append(f"task {task['id']} is in the sidecar already as another task")
        else:
            tasks.append(task)
            out["added"].append(task["id"])
    if out["refused"]:
        out["wrote"], out["added"] = [], []
        return out
    candidate = {**target, "tasks": tasks}
    if not public_bundle_only:
        try:
            sidecar.check(candidate, folder, target_path)
        except sidecar.SidecarError as e:
            out["leftForSetup"].append(str(e).split(": ", 1)[-1])
    if write:
        for name in out["wrote"]:
            (folder / name).parent.mkdir(parents=True, exist_ok=True)
            (folder / name).write_text(json.dumps(claims[name], indent=1, ensure_ascii=False) + "\n")
        if out["added"]:
            target_path.write_text(json.dumps(candidate, indent=2, ensure_ascii=False) + "\n")
    if deployments or numbered is not None:
        record = folder / "records" / "entry-bindings.json"
        out["entryBindings"] = str(record)
        if write:
            if numbered is not None:
                from targets import observer_review, observer_recipes
                try:
                    paths = observer_review.prepare(folder, numbered, folder/"records/reviewed-public-inputs")
                except observer_recipes.Unsupported as error:
                    from targets import change_evidence, upgrade_replay
                    change_evidence.write_json(folder/"records/reviewed-public-inputs/review.json",
                        {"status":"open","firstOpenDependency":str(error),
                         "comparisonSha256":upgrade_replay.sha(folder/"comparison.json"),
                         "runtimeSha256":upgrade_replay.sha(folder/"runtime.json")})
                    out["leftForSetup"].append(str(error))
                    return out
            else:
                paths = {k: plan_path.parent / value for k, value in deployments.items()}
            if "registration" in paths:
                from targets import observer_generation
                bundle = folder / "records" / "public-observer"
                if "predictions" not in paths or "workflows" in paths:
                    raise ValueError("a reviewed registration requires its predictions and generates its own workflows")
                try:
                    generation = observer_generation.materialize(paths["registration"], paths["predictions"],
                        paths["before"], paths["after"], paths["jdk"], bundle)
                except ValueError as error:
                    if numbered is None:
                        raise
                    from targets import change_evidence
                    review = folder/"records/reviewed-public-inputs/review.json"
                    detail = json.loads(review.read_bytes())
                    change_evidence.write_json(review, {**detail, "status": "open", "firstOpenDependency": str(error)})
                    out["refused"].append(str(error))
                    return out
                out["generatedObserver"] = str(bundle / "generation.json")
                if generation["status"] != "compiled":
                    out["leftForSetup"].append(generation["firstOpenDependency"])
                    return out
                paths["workflows"] = bundle / "workflows.json"
            status = bind_deployments(paths["before"], paths["after"], paths["jdk"], record,
                             workflows=paths.get("workflows"),
                             entries=[t["target"] for t in tasks if "#" in t.get("target", "")])
            if status:
                out["refused"].append("the prepared deployment binding failed")
                return out
            report = json.loads(record.read_text())
            if numbered is not None:
                from targets import change_evidence, upgrade_replay
                report["numberedReviewSha256"] = upgrade_replay.sha(folder/"records/reviewed-public-inputs/review.json")
                change_evidence.write_json(record, report)
            for binding in report["entryBindings"].values():
                if binding["status"] != "bound":
                    out["leftForSetup"].append(f"{binding['side']} {binding['entry']}: {binding['firstOpenDependency']}")
    return out


def bind_deployments(before, after, jdk, output, *, workflows=None, entries=(), checker=None):
    """Stage 3 accepts the prepared manifests. The shared planner owns byte selection and the receipt."""
    from targets import change_plan
    arguments = ["application", "--before", str(before), "--after", str(after), "--jdk", str(jdk), "--output", str(output)]
    if workflows:
        arguments.extend(["--workflows", str(workflows)])
    if checker:
        arguments.extend(["--checker", str(checker)])
    for entry in entries:
        arguments.extend(["--entry", entry])
    return change_plan.main(arguments)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in {"generate", "emit"}:
        from targets import observer_generation
        parser = argparse.ArgumentParser(description="Materialize a reviewed public observation on its prepared deployments")
        for name in ("registration", "before", "after", "jdk", "output"):
            parser.add_argument("--" + name, type=Path, required=True)
        if argv[0] == "generate":
            parser.add_argument("--predictions", type=Path, required=True)
        args = parser.parse_args(argv[1:])
        try:
            if argv[0] == "emit":
                args.output.mkdir(parents=True)
                record = observer_generation.generate(json.loads(args.registration.read_bytes()), args.before,
                                                      args.after, args.jdk, args.output, fixture_root=args.registration.parent)
            else:
                record = observer_generation.materialize(**vars(args))
        except (ValueError, OSError) as error:
            print(str(error), file=sys.stderr)
            return 1
        print(record.get("firstOpenDependency", str(args.output / "generation.json")))
        return int(record["status"] != "compiled")
    if argv and argv[0] == "bind":
        parser = argparse.ArgumentParser(description="Bind approved public entries on the two prepared deployments")
        for name in ("before", "after", "jdk", "output"):
            parser.add_argument("--" + name, type=Path, required=True)
        parser.add_argument("--workflows", type=Path)
        parser.add_argument("--checker", type=Path)
        parser.add_argument("--entry", action="append", default=[])
        args = parser.parse_args(argv[1:])
        return bind_deployments(args.before, args.after, args.jdk, args.output, workflows=args.workflows,
                                entries=args.entry, checker=args.checker)
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("number")
    ap.add_argument("--plan", type=Path, default=PLAN)
    ap.add_argument("--check", action="store_true", help="write nothing")
    a = ap.parse_args(argv)
    found = scaffold(a.number, a.plan, not a.check)
    verb = "would write" if a.check else "wrote"
    for line in found["refused"]:
        print(f"refused: {line}")
    if not found["refused"]:
        print(f"{verb} {len(found['wrote'])} claim file(s): {' '.join(found['wrote']) or '-'}")
        print(f"{'would add' if a.check else 'added'} {len(found['added'])} task(s): {' '.join(found['added']) or '-'}")
        for line in found["leftForSetup"]:
            print(f"left for the setup: {line}")
    return 1 if found["refused"] else 0


if __name__ == "__main__":
    sys.exit(main())

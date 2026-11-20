"""Check a native counterexample found under startup assumptions against the original JVM claim."""

import argparse
import json
from pathlib import Path
import tempfile

from targets import interfaces, recipes, route, sidecar, workflow


def original_plan(folder, example, target, name):
    plan = route.resolve(folder, example, target, name)
    if (
        not isinstance(plan, interfaces.TaskPlan)
        or plan.kind != "prove"
        or plan.engine != "native"
        or plan.gaps != "strict"
    ):
        raise ValueError(f"{name} is not a strict native property")
    return plan


def select_receipt(folder, plan):
    for path in sorted((folder / "receipts" / plan.task).glob("*/result.json"), reverse=True):
        doc = json.loads(path.read_text())
        recorded = json.loads((path.parent / "plan.json").read_text())
        if (
            recorded.get("key") != workflow.inputs_key(plan)
            or doc["conclusion"]["status"] != "refuted"
            or doc["conclusion"]["expectation"] != "yes"
        ):
            continue
        records = json.loads((path.parent / "records/execution.json").read_text())["records"]
        (verifier,) = [r for r in records if r["kind"] == "verifier"]
        ids = verifier["identities"]
        witnesses = [r for r in ids.get("independentReplay", []) if r["by"] == "jvm" and r["reproduced"]]
        if ids["engine"] == "native" and ids["gaps"] == "strict" and witnesses:
            return path, ids, witnesses[0]
    raise ValueError(f"{plan.task} has no matching strict native refutation with an independent JVM replay")


def check(folder, example, target, task, scoped):
    original = original_plan(folder, example, target, task)
    companion = original_plan(folder, example, target, scoped)
    if (
        original.revisions != companion.revisions
        or original.target != companion.target
        or original.artifacts != companion.artifacts
    ):
        raise ValueError("the original and companion have different subjects or prepared recipes")
    for field in (
        "assume",
        "assert",
        "throws",
        "nullable",
        "mayAlias",
        "observations",
        "adapter",
        "allowedChange",
    ):
        if original.claim.get(field) != companion.claim.get(field):
            raise ValueError(f"the frozen {field} differs")
    # Unwinding controls the search that found the candidate. The original replay enforces the original input domain.
    input_bounds = lambda p: {k: v for k, v in p.claim["bounds"].items() if k != "unwind"}
    if input_bounds(original) != input_bounds(companion):
        raise ValueError("the frozen input bounds differ")
    if original.claim.get("observedInitializers") or original.claim.get("boundEnvironment"):
        raise ValueError("the original itself requests observed startup")
    if not companion.claim.get("observedInitializers"):
        raise ValueError("the source claim has no recorded startup observation")
    receipt, ids, candidate = select_receipt(folder, companion)
    if candidate["entry"] != recipes.translate(original).entry or set(candidate["sides"]) != set(
        original.revisions
    ):
        raise ValueError("candidate entry or revisions differ from the original")
    with tempfile.TemporaryDirectory(prefix="original-witness-") as directory:
        work = Path(directory)
        supplied = work / "native-candidate.json"
        supplied.write_text(
            json.dumps({"inputs": candidate["inputs"], "sourceReceiptSha256": workflow.file_sha256(receipt)})
            + "\n"
        )
        reviewed = route.review_witness(folder, example, target, task, supplied, work)
        if not isinstance(reviewed, dict) or reviewed["status"] != "witness-reproduced":
            raise ValueError(f"the fresh original JVM rejected the witness: {reviewed}")
    path = folder / reviewed["path"]
    replay = json.loads(path.read_text())
    if (
        replay["inputs"] != candidate["inputs"]
        or replay["claimKey"] != original.claim["key"]
        or replay["observations"] != candidate["observations"]
        or replay.get("jdkRelease") != candidate.get("jdkRelease")
    ):
        raise ValueError("the independent replay changed the input, observation or JDK")
    for rev in original.revisions:
        found, previous = replay["sides"][rev], candidate["sides"][rev]
        if (
            found["classpath"] != previous["classpath"]
            or found["entryClassSha256"] != ids["entryBindings"][rev]["classSha256"]
            or found["values"] != previous["values"]
            or not found["admitted"]
            or found["satisfies"] is not False
        ):
            raise ValueError("original bytecode, ordered classpath, admission or observed violation differs")
    record = {
        "schema": "original-jvm-counterexample/v1",
        "status": "refuted",
        "task": task,
        "sourceKey": original.claim["key"],
        "planKey": workflow.inputs_key(original),
        "subject": original.target,
        "revisions": list(original.revisions),
        "entry": candidate["entry"],
        "inputs": candidate["inputs"],
        "observations": candidate["observations"],
        "nativeSource": {
            "task": scoped,
            "sourceKey": companion.claim["key"],
            "receipt": receipt.relative_to(folder).as_posix(),
            "receiptSha256": workflow.file_sha256(receipt),
            "checkerSha256": ids["jvmcontract"],
            "observedInitializers": companion.claim["observedInitializers"],
            "bounds": companion.claim["bounds"],
        },
        "original": {
            "replay": reviewed["path"],
            "sha256": workflow.file_sha256(path),
            "execution": reviewed["execution"],
            "observedInitializers": [],
            "bounds": original.claim["bounds"],
            "values": {r: s["values"] for r, s in replay["sides"].items()},
        },
        "derivation": "An admitted input violates the original assertion on original JVM bytecode. The native companion supplied the candidate. Its startup assumptions are unnecessary for this existential refutation.",
    }
    out = folder / "records/original-witnesses" / task / (reviewed["execution"] + ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n")
    return record


def evidence(folder, plan):
    accepted = []
    for path in sorted((folder / "records/original-witnesses" / plan.task).glob("*.json")):
        r = json.loads(path.read_text())
        if r["planKey"] != workflow.inputs_key(plan) or r["sourceKey"] != plan.claim["key"]:
            continue
        source, original = r["nativeSource"], r["original"]
        if (
            workflow.file_sha256(workflow.inside(folder, source["receipt"])) != source["receiptSha256"]
            or workflow.file_sha256(workflow.inside(folder, original["replay"])) != original["sha256"]
        ):
            continue
        accepted.append(
            {
                "status": "refuted",
                "route": "original JVM witness",
                "file": path.relative_to(folder).as_posix(),
                "inputs": r["inputs"],
                "nativeSource": source["task"],
            }
        )
    return accepted


def main(argv):
    import build

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example")
    parser.add_argument("task")
    parser.add_argument("--from-task", required=True)
    a = parser.parse_args(argv)
    (folder,) = build.EXAMPLES.glob(a.example + "-*")
    example = build.load_example(folder)
    try:
        result = check(folder, example, sidecar.load(folder, example), a.task, a.from_task)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"{a.task}: {error}\n")
    print(result["task"], result["status"], result["inputs"], result["original"]["replay"])
    return 0

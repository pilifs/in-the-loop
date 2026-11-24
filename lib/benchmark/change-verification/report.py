"""Recount the frozen change evaluation from original observations and collector-bound receipts."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESULTS = ROOT / "verification/change-verification"
sys.path.insert(0, str(ROOT / "examples/tools"))
sys.path.insert(0, str(ROOT / "lib/benchmark/java-semantics-gap"))
import scorecard
from targets import change_evidence, change_inventory, upgrade_replay

JOBS = {
    "wire": "20261124-015038-compare-six-wire-change-plans-against-in",
    "petclinic": "20261124-020655-evaluate-the-registered-petclinic-2-7-to",
    "fullCost": "20261124-022228-measure-petclinic-cold-and-exact-reruns",
    "semantics": "20261124-020146-retry-java-semantics-callers-before-rece",
    "kernel": "20261124-014943-replay-the-guava-change-plan-nodes-and-i",
    "solvers": "20261124-021637-compare-bounded-solvers-on-eclipse-inser",
}


def read(path):
    return json.loads(path.read_bytes())


def pin(path):
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": upgrade_replay.sha(path)}


def checked(path, job):
    scorecard.collected(path, JOBS[job])
    return read(path)


def wire():
    directory = RESULTS / "wire"
    matrix = checked(directory / "summary.json", "wire")
    cases = {}
    for workflow in read(HERE / "wire-workflows.json")["workflows"]:
        name = workflow["id"]
        scope = read(HERE / workflow["scope"])
        raw = checked(directory / matrix["receipts"][name]["path"], "wire")
        history = matrix["grading"][name]
        original = ROOT / history["record"]
        if pin(original)["sha256"] != history["sha256"] or not history["independentlyDiscovered"]:
            raise ValueError(f"{name}: historical grading receipt changed or the operation was missed")
        grade = read(original)
        result = change_evidence.compose(scope, raw)
        if (raw["originalInvocation"] != grade["entry"] or raw["observerInvocation"]["declaration"] != scope["invocationVia"]
                or not all(grade["sides"][s]["trials"][c["input"]]["observations"] == [c[s], c[s]]
                           for c in result["children"] for s in ("old", "new"))
                or result["covered"] != len(grade["cases"]) or grade["cases"] != scope["cases"]):
            raise ValueError(f"{name}: different original invocation, typed outcome or domain")
        cases[name] = {"cohort": workflow["cohort"], "inputs": result["inputs"], "status": result["status"],
                       "outcomes": [{s: c[s] for s in ("old", "new")} for c in result["children"]]}
    runs = {r["scenario"]: r for r in matrix["matrix"]}
    if len(runs) != 6 or not all(r["cleanEquivalent"] for r in runs.values()):
        raise ValueError("incomplete Wire matrix")
    return {"claims": cases, "configurations": len(runs), "exact": runs["exact"]["incremental"],
            "clean": runs["exact"]["clean"], "sideActions": runs["exact"]["actions"]}


def importer():
    data = read(RESULTS / "importer.json")
    for claim in data["claims"]:
        for proof in claim["receipts"]:
            if pin(ROOT / proof["path"])["sha256"] != proof["sha256"]:
                raise ValueError(f"{claim['id']}: a graded receipt changed")
    for name, cell in data["configurations"].items():
        original = ROOT / "examples/345-paged-importer-upgrades/records/matrix" / (name + ".jsonl")
        if upgrade_replay.sha(original) != cell["stdoutSha256"] or cell["inputs"] != 96:
            raise ValueError(f"{name}: different original JVM observations")
    return {cohort: {s: sum(c["cohort"] == cohort and c["status"] == s for c in data["claims"])
                     for s in ("established", "refuted")} for cohort in ("primary", "control")}


def report():
    portfolio = read(RESULTS / "portfolio.json")
    enough = checked(RESULTS / "petclinic-cost.json", "fullCost")
    registrations = read(HERE / "petclinic.json")
    deployment = enough["measurement"]
    if (not enough["cleanEquivalent"] or deployment["registrationSha256"] != pin(HERE / "petclinic.json")["sha256"]
            or [deployment["builds"][s]["compile"]["classMajor"] for s in ("before", "after")] != [52, 61]):
        raise ValueError("the held-back cost comparison lacks its registered build or original target bytecode")
    ids = {r["id"] for r in registrations["productionWorkflows"]}
    if any(set(d["claims"]) != ids for d in deployment["deployments"].values()):
        raise ValueError("the held-back workflow denominator changed")
    application_plan = read(RESULTS / "petclinic-plan.json")
    if application_plan["measurementSha256"] != pin(RESULTS / "petclinic-cost.json")["sha256"]:
        raise ValueError("application entry inventory comes from another migration run")
    solvers = checked(RESULTS / "solvers/summary.json", "solvers")
    times = []
    for row in solvers["runs"]:
        costs = {}
        for solver, run in row["routes"].items():
            path = RESULTS / "solvers" / run["receipt"]
            scorecard.collected(path, JOBS["solvers"])
            raw = gzip.decompress(path.read_bytes())
            if hashlib.sha256(raw).hexdigest() != run["receiptSha256"]:
                raise ValueError("different native solver receipt")
            costs[solver] = {"status": run["status"], "checkerSeconds": run["checkerSeconds"], "wallSeconds": run["wallSeconds"]}
        times.append({"task": row["task"], "claimKey": row["claimKey"], "routes": costs, "disputed": row["disputed"]})
    pins = [pin(RESULTS / x) for x in ("importer.json", "wire/summary.json", "portfolio.json", "petclinic-cost.json",
                                        "petclinic-plan.json", "solvers/summary.json")]
    for job in JOBS.values():
        p = scorecard.receipt_path(job)
        if read(p)["status"] != "passed":
            raise ValueError(f"evaluation job {job} did not pass")
        pins.append(pin(p))
    return {"schema": "change-verification-evaluation/v1", "receipts": pins,
            "importer": importer(), "wire": wire(), "semanticFamilies": portfolio["semantics"]["families"],
            "native": portfolio["semantics"]["native"], "jbmc": portfolio["semantics"]["jbmc"],
            "receiverSites": len(portfolio["receivers"]["sites"]), "sharedSpringBlockers": portfolio["spring"]["sharedBlockers"],
            "petclinic": {"sourceBuild": deployment["unchangedSourceBuild"], "denominator": sorted(ids),
                          "deployments": {k: v["claims"] for k, v in deployment["deployments"].items()},
                          "discoveryMisses": application_plan["discoveryMisses"], "fullCost": enough["passes"]},
            "solverComparison": times}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    value = report()
    output = RESULTS / "evaluation.json"
    if args.check:
        if read(output) != value:
            raise SystemExit("evaluation differs from its graded receipts")
    else:
        change_evidence.write_json(output, value)
    print("change evaluation", change_inventory.digest(value))

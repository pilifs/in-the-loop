"""Recover the committed interruption in a fresh pipeline checkout and retry its frozen claim twice."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile

FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parent.parent
sys.path.insert(0, str(FOLDER.parent / "tools"))
from targets import claim_history, interfaces, replay_candidate, route, runtime, sidecar, workflow


def run(prior, work):
    example = json.loads((FOLDER / "example.json").read_text())
    target = sidecar.load(FOLDER, example)
    def history():
        return claim_history.inventory(FOLDER, example, target)
    def subject(view, task):
        return next(s for group in view["claims"] for s in group["subjects"] if s["task"] == task)
    old = subject(history(), "full-state")
    interrupted = next(e for e in old["executions"] if e["id"] == prior)
    candidate_file = FOLDER / interrupted["path"]
    candidate = json.loads((candidate_file.parent / "checker.json").read_text())["outcomes"][0]["counterexample"]
    if not candidate or not interrupted["injected"] or interrupted["lastCompletedStage"] != "candidate-recorded":
        raise ValueError("cannot recover an injected post-checker interruption")
    if (candidate_file.parent / "replay.json").exists():
        raise ValueError("an independently qualified replay was already recorded for the interrupted execution")

    def retry(_):
        subprocess.run([sys.executable, "examples/tools/build.py", "198", "--task", "full-state", "--retry-of", prior],
                       cwd=ROOT, check=True)
    with ThreadPoolExecutor(max_workers=2) as threads:
        list(threads.map(retry, range(2)))
    view = history()
    full = subject(view, "full-state")
    retries = [e for e in full["executions"] if e.get("retryOf") == prior and e["id"] not in {x["id"] for x in old["executions"]}]
    if (len(retries) != 2 or len({e["id"] for e in retries}) != 2 or full["conclusion"] != "refuted"
            or subject(view, "return-only")["conclusion"] != "established"):
        raise ValueError("the two retries or the independently established sibling were lost")
    plan = route.resolve(FOLDER, example, target, "full-state")
    prepared = {r: runtime.prepare(plan, r, work / "prepare" / r) for r in plan.revisions}
    receipt = FOLDER / retries[0]["receipt"]
    stored = json.loads((receipt.parent / "records/execution.json").read_text())["records"]
    records = tuple(interfaces.ExecutionRecord(**r) for r in stored)
    out = FOLDER / plan.outputs["receipts"]
    repeated = workflow.ingest(plan, prepared, records, out)
    if not isinstance(repeated, interfaces.Receipt) or repeated.attempt != retries[0]["id"]:
        raise ValueError(f"duplicate completion did not recover its receipt: {repeated}")
    if len(subject(history(), "full-state")["executions"]) != len(full["executions"]):
        raise ValueError("idempotent ingestion produced a new execution")
    inputs = [{"name": "scores", "type": "int[]", "value": [0]}, {"name": "slot", "type": "int", "value": 0},
              {"name": "score", "type": "int", "value": 1}]
    reviews = {}
    for task in ("return-only", "full-state", "interior-state"):
        p = route.resolve(FOLDER, example, target, task)
        reviews[task] = replay_candidate.check(p, prepared, inputs, work / task)
    if not reviews["full-state"]["reproduced"] or reviews["return-only"]["reproduced"]:
        raise ValueError("the selected observation did not decide original-artifact replay")
    if "domain mismatch" not in reviews["interior-state"].get("reason", ""):
        raise ValueError("the interior claim admitted a last-slot candidate")
    return {"interrupted": interrupted, "candidateInputs": candidate["inputs"], "retries": retries,
            "duplicateCompletionReceipt": repeated.path, "siblingConclusion": subject(view, "return-only")["conclusion"],
            "witnessReviews": reviews}


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        report = run(sys.argv[1], Path(directory))
    (FOLDER / "records/retry-drill.json").write_text(json.dumps(report, indent=2) + "\n")

"""A predicted refusal, checked: the job step that reruns a task an observed capability gap blocks, unchanged, and
passes only when the attempt stops at the refusal the gap packet recorded (the user's decision of 2026-11-15 on
VF-027, in llm-dlc/loops/example-targets.md's Progress).

build.py ID --task T exits 1 both when the verifier refuses the task and when it gives a verdict the task doesn't
expect, so an expected exit code of 1 can't tell a known gap from a counterexample to the claim. This step tells them
apart. It reads the task's observed blockers in the sidecar whose packet states a `refusal`:

  {"refusal": {"stage": "verifier" | "run-verifier", "text": "the refusal, as recorded"},
   "claimKey": "the frozen source-level claim key the refusal was observed under", ...}

runs `build.py ID --task T` once, its output shown indented (so the pipeline reads this step's verdict line, not
build.py's NOT AS EXPECTED), and passes (exit 0) only when:
- the task still plans, under the same claim key (a changed claim is a different claim, never this prediction);
- build.py exited 1;
- stage `verifier`: it wrote exactly one new receipt for the task, which completed with the claim unresolved (no
  verdict: neither established nor refuted) and whose problem contains the recorded text;
- stage `run-verifier`: it wrote no receipt, and its not-executed line contains the recorded text.

Anything else fails, with what differed: a verdict, another refusal, a crash. When the gap's closure lands the step
fails too, which is the point: the task then needs its ordinary attempt, its claim unchanged. The claim's `expected`
conclusion is never touched, and a refusal is never a verdict.

Run as `python3 examples/tools/targets/workflow_refusal.py ID TASK` from the repository root.
"""

import json
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # examples/tools, for `targets` and build.py

from targets import workflow  # noqa: E402
from targets.interfaces import Unsupported  # noqa: E402

STAGES = ("verifier", "run-verifier")
RECEIPTS = workflow.RECEIPTS
INDENT = "  build.py | "


class PredictionError(Exception):
    """The sidecar states no usable prediction for the task."""


def predictions(folder, target, task_id):
    """The task's predicted refusals: each observed blocker naming the task whose packet states a refusal. A blocker
    with no packet, or a packet without `refusal`, predicts nothing; a malformed one is an error."""
    out = []
    for b in target.get("handoff", {}).get("blockers", []):
        if b.get("task") != task_id or not b.get("observed") or not b.get("packet"):
            continue
        path = workflow.inside(Path(folder), b["packet"])
        document = json.loads(path.read_text())
        refusal = document.get("refusal")
        if refusal is None:
            continue
        if not isinstance(refusal, dict) or refusal.get("stage") not in STAGES or not refusal.get("text"):
            raise PredictionError(f"{b['packet']}: refusal needs a stage ({' or '.join(STAGES)}) and a text")
        if not document.get("claimKey"):
            raise PredictionError(f"{b['packet']}: a predicted refusal names the claim key it was observed under")
        out.append({"packet": b["packet"], "kind": b["kind"], "finding": b.get("finding"),
                    "stage": refusal["stage"], "text": refusal["text"], "claimKey": document["claimKey"]})
    return out


def receipt_dirs(folder, task_id):
    """The task's receipt directories (those with a result.json), by name."""
    root = Path(folder) / RECEIPTS / task_id
    return {p.parent.name for p in root.glob("*/result.json")} if root.is_dir() else set()


def read_receipt(folder, task_id, name):
    """What the judgement reads of one receipt: execution, conclusion status and problem."""
    raw = json.loads((Path(folder) / RECEIPTS / task_id / name / "result.json").read_text())
    conclusion = raw.get("conclusion") or {}
    evidence = raw.get("evidence") or {}
    attempt = raw.get("attempt") or {}
    return {"path": f"{RECEIPTS}/{task_id}/{name}", "status": conclusion.get("status"),
            "execution": (attempt.get("execution") or {}).get("status"), "problem": evidence.get("problem") or "",
            "claim": attempt.get("claim")}


def judge(prediction, plan_key, code, output, receipts):
    """(True, how) when the run is the predicted refusal, else (False, what differed). `output` is build.py's lines,
    `receipts` the new receipts read by read_receipt()."""
    if plan_key != prediction["claimKey"]:
        return False, (f"the task's claim key is {plan_key}, not {prediction['claimKey']}, the one the refusal was "
                       "observed under: a changed claim needs its own attempt")
    if code != 1:
        return False, f"build.py exited {code}, not 1"
    if prediction["stage"] == "run-verifier":
        if receipts:
            return False, f"a receipt was written ({receipts[0]['path']}), so the verifier ran"
        line = next((l for l in output if ": not-executed (" in l), None)
        if line is None:
            return False, "build.py printed no not-executed line"
        if prediction["text"] not in line:
            return False, f"not executed for another reason: {line}"
        return True, "not executed, at the recorded refusal"
    if len(receipts) != 1:
        return False, f"{len(receipts)} new receipts, not one"
    r = receipts[0]
    if r["status"] != "unresolved":
        return False, f"the receipt {r['path']} concludes {r['status']}, not unresolved: a verdict, not the refusal"
    if r["execution"] != "completed":
        return False, f"the attempt {r['path']} is {r['execution']}, not completed"
    if prediction["text"] not in r["problem"]:
        return False, f"another refusal in {r['path']}: {r['problem'] or 'none recorded'}"
    return True, f"unresolved at the recorded refusal, receipt {r['path']}"


def check(folder, example, target, task_id, run):
    """Runs the task once through `run` (a callable returning (exit code, output lines)) and judges it against each
    predicted refusal: (ok, line). The task must have exactly one prediction."""
    folder = Path(folder)
    found = predictions(folder, target, task_id)
    if len(found) != 1:
        raise PredictionError(f"task {task_id} has {len(found)} predicted refusals, not one")
    [prediction] = found
    plan = workflow.plan_task(folder, example, target, task_id)
    if isinstance(plan, Unsupported):
        return False, f"the task no longer plans ({plan.describe()})"
    before = receipt_dirs(folder, task_id)
    code, output = run()
    new = sorted(receipt_dirs(folder, task_id) - before)
    receipts = [read_receipt(folder, task_id, name) for name in new]
    ok, how = judge(prediction, plan.claim.get("key"), code, output, receipts)
    tag = f"{prediction['finding'] or prediction['kind']}; {prediction['stage']}; {prediction['packet']}"
    return ok, (f"{folder.name}: task {task_id}: refused as predicted ({tag}): {how}" if ok else
                f"{folder.name}: task {task_id}: NOT AS PREDICTED: {how} ({tag})")


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Rerun a task and check it stops at its recorded refusal.")
    parser.add_argument("example")
    parser.add_argument("task")
    args = parser.parse_args(argv)
    import build
    from targets import sidecar
    folders = sorted(build.EXAMPLES.glob(f"{args.example}-*"))
    if len(folders) != 1:
        sys.exit(f"example {args.example}: expected one folder examples/{args.example}-*, found {len(folders)}")
    folder = folders[0]
    example = build.load_example(folder)
    target = sidecar.load(folder, example)
    if target is None or args.task not in [t["id"] for t in target["tasks"]]:
        sys.exit(f"example {args.example} has no task {args.task!r}")
    root = build.EXAMPLES.parent

    def run():
        p = subprocess.run([sys.executable, str(root / "examples/tools/build.py"), args.example, "--task", args.task],
                           cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        lines = p.stdout.splitlines()
        for line in lines:
            print(INDENT + line, flush=True)
        return p.returncode, lines

    try:
        ok, line = check(folder, example, target, args.task, run)
    except PredictionError as e:
        sys.exit(str(e))
    print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

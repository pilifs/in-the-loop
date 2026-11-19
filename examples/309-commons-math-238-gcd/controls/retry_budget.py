"""Measure a real native deadline and its linked retry on one preparation of the fixed GCD class."""

import json
from pathlib import Path
import sys
import tempfile

FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER.parent / "tools"))
from targets import interfaces, route, sidecar


def run(work):
    example = json.loads((FOLDER / "example.json").read_text())
    target = sidecar.load(FOLDER, example)
    task = "powers-fix"
    shared, attempts = {}, []
    prior = None
    for seconds in (1, 600):
        receipt = route.run(FOLDER, example, target, task, work, shared=shared, retry_of=prior, checker_seconds=seconds)
        if not isinstance(receipt, interfaces.Receipt):
            raise ValueError(receipt)
        journal_path = FOLDER / "receipts" / task / "executions" / receipt.attempt / "attempt.json"
        journal = json.loads(journal_path.read_text())
        attempts.append({"execution": receipt.attempt, "receipt": receipt.path, "journal": str(journal_path.relative_to(FOLDER)),
                         "claimKey": journal["claimKey"], "binding": journal["bindingId"], "retryOf": journal["retryOf"],
                         "status": receipt.status, "budget": journal["budget"], "budgetExhausted": journal["budgetExhausted"],
                         "usage": journal["usage"], "checkerSeconds": journal["checkerSeconds"], "host": journal["host"],
                         "cache": journal["cache"], "stages": journal["stages"]})
        prior = receipt.attempt
    short, full = attempts
    if (not short["budgetExhausted"] or short["status"] != "unresolved" or full["status"] != "established"
            or short["binding"] != full["binding"] or full["retryOf"] != short["execution"]):
        raise ValueError(f"the observed attempts did not establish a comparable deadline and retry: {attempts}")
    return attempts


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        rows = run(Path(directory))
    (FOLDER / "records/budget-comparison.json").write_text(json.dumps(rows, indent=2) + "\n")

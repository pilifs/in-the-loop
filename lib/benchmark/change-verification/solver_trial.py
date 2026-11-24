"""Compare two native encodings on frozen caller claims, with shared preparation and fresh proof attempts."""
import argparse
import gzip
import json
import os
from pathlib import Path
import resource
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "examples/tools"))
sys.path.insert(0, str(ROOT / "lib/solvers"))
import build
from compare import bitwuzla_library
from targets import change_evidence, route, runtime, sidecar
from targets.interfaces import Unsupported

SUBJECTS = ((359, "returns-fix"), (359, "contents-parent"), (345, "page-fix-fix"))
SOLVERS = ("cadical", "bitwuzla-words:preprocess=0")


def measure(number, task, out, work, library):
    folder, = build.EXAMPLES.glob(f"{number:03d}-*")
    example = build.load_example(folder)
    manifest = sidecar.load(folder, example)
    plan = route.resolve(folder, example, manifest, task)
    start = time.monotonic()
    shared = {}
    for revision in plan.revisions:
        prepared = route.prepare_revision(plan, revision, work / task / "prepare" / revision, shared)
        if isinstance(prepared, Unsupported) or prepared.stage != "artifacts-ready":
            raise ValueError(f"{number}/{task}: could not prepare the pinned revision")
    result = {"example": number, "task": task, "claimKey": plan.claim["key"], "bounds": plan.claim["bounds"],
              "budgetSeconds": 60, "preparationSeconds": round(time.monotonic() - start, 4), "routes": {}}
    for solver in SOLVERS:
        started = time.monotonic()
        old = resource.getrusage(resource.RUSAGE_CHILDREN)
        os.environ.update(JVMCONTRACT_SOLVER=solver, JVMCONTRACT_BITWUZLA=library["path"])
        got = route.run(folder, example, manifest, task, work / task, shared=shared, checker_seconds=60)
        if isinstance(got, Unsupported):
            raise ValueError(f"{task}/{solver}: {got.describe()}")
        receipt = folder / got.path
        journal = receipt.parents[1] / "executions" / got.attempt
        attempt = json.loads((journal / "attempt.json").read_text())
        checked = json.loads((journal / "checker.json").read_text())
        finished = resource.getrusage(resource.RUSAGE_CHILDREN)
        if attempt["claimKey"] != plan.claim["key"] or not attempt["bindings"] or checked["status"] == "not-started":
            raise ValueError(f"{task}/{solver}: the frozen claim did not reach its checker")
        data = json.loads(receipt.read_text())
        stated = data["evidence"].get("stated") or {}
        identity = (stated.get("checker") or {}).get("sat") or {}
        if got.status in ("established", "refuted"):
            if (stated.get("gapMode") != "strict" or data["conclusion"].get("vacuous") is not False
                    or ("bitwuzla" in str(identity).lower()) != solver.startswith("bitwuzla")):
                raise ValueError(f"{task}: unqualified or different solver")
            if got.status == "refuted" and (data["evidence"].get("replay") or {}).get("reproduced") is not True:
                raise ValueError("counterexample lacks original JVM replay")
        dest = out / str(number) / task / solver.partition(":")[0]
        dest.mkdir(parents=True, exist_ok=True)
        for path in (receipt, journal / "attempt.json", journal / "checker.json", journal / "replay.json"):
            if path.is_file():
                (dest / (path.name + ".gz")).write_bytes(gzip.compress(path.read_bytes(), mtime=0))
        result["routes"][solver] = {
            "status": got.status or "open", "execution": got.execution, "bindingId": attempt["bindingId"],
            "receipt": str((dest / "result.json.gz").relative_to(out)), "receiptSha256": runtime.sha256(receipt),
            "wallSeconds": round(time.monotonic() - started, 4), "checkerSeconds": checked["seconds"],
            "cpuSeconds": round(finished.ru_utime + finished.ru_stime - old.ru_utime - old.ru_stime, 4),
            "checkerUsage": attempt.get("usage"), "solver": identity, "firstBlocker": attempt.get("firstBlocker"),
            "search": [r.get("search") for r in checked["outcomes"]], "replay": data["evidence"].get("replay")}
    rows = list(result["routes"].values())
    if rows[0]["bindingId"] != rows[1]["bindingId"]:
        raise ValueError("the two routes used different application inputs")
    result["disputed"] = {r["status"] for r in rows} == {"refuted", "established"}
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    library = bitwuzla_library(runtime.jvmcontract())
    if not library.get("sha256"):
        sys.exit("pinned Bitwuzla shared library unavailable")
    with tempfile.TemporaryDirectory(prefix="change-solvers-") as temp:
        runs = [measure(n, t, args.output.parent, Path(temp), library) for n, t in SUBJECTS]
    change_evidence.write_json(args.output, {"schema": "caller-solver-trial/v1", "checkerSha256": runtime.sha256(runtime.jvmcontract()),
        "bitwuzlaSha256": library["sha256"], "machine": os.uname().machine, "runs": runs})
    print([(r["task"], [v["status"] for v in r["routes"].values()]) for r in runs])

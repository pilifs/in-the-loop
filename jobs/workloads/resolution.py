"""The workload of a resolution job: one that makes a readiness operation ready (jobs/readiness.py).

Its steps are ordinary commands (`python3 jobs/readiness.py resolve OPERATION`). What this adapter adds is the
two things only a resolution job has: the runner's authorisation to fetch, handed to its steps and to no other
job's (the store's place, and the sources the runner's settings allow), and the reading of its result: whether
readiness was established or withheld, at which stage and with which named outcome, from the receipt it left.
Everything else is the generic workload's.
"""
import json

NAME = "resolution"
core = None


def _generic():
    return core.workload("generic")


def __getattr__(name):
    # SIGNALS, SUSPICIOUS, COLLECTORS_OWN, tools, missing, reservation, prepare, scan, verdicts: the generic ones.
    return getattr(_generic(), name)


def step_env(runner, job, result, work, env) -> None:
    env["ITL_READINESS_STORE"] = str(runner.runner["readiness_dir"])
    env["ITL_FETCH_ALLOW"] = json.dumps(runner.runner["fetch_allow"])


def keys(job) -> list:
    return list((job.get("labels") or {}).get("readiness") or [])


def conclusion(job, result):
    """Ready or withheld, for each operation the job resolves, as its receipt in the runner's store says: a job
    that exited 0 established readiness, and one that exited 1 withheld it for a reason with a name."""
    store = core.readiness.Store(result.get("readinessStore") or core.DEFAULTS["runner"]["readiness_dir"])
    said = []
    for key in keys(job):
        receipt = store.receipt(key)
        if receipt is None:
            said.append({"key": key, "verdict": "none", "why": "the job left no receipt"})
            continue
        said.append({"key": key, "verdict": "ready" if receipt["state"] == "ready" else "withheld", "stage": receipt.get("stage"),
                     "outcome": receipt.get("outcome"), "why": receipt.get("why"), "level": receipt.get("level"),
                     "rounds": len(receipt.get("rounds") or []), "fetch": receipt.get("fetch"),
                     "reused": bool(receipt.get("reused")), "bundleDigest": (receipt.get("bundle") or {}).get("digest")})
    verdicts = {row["verdict"] for row in said}
    return {"verdict": "ready" if verdicts == {"ready"} else "withheld" if "withheld" in verdicts else "none",
            "scope": "the operation as its file describes it, on this runner, with the base as the receipt records it",
            "readiness": said}

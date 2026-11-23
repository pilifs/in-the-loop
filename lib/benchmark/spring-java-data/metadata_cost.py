"""Compare complete ordinary and recorded lookup workflows on the same checker, JVMs and selectors."""
import os
from pathlib import Path
import tarfile
import tempfile
import time

import metadata_lookup as metadata
from measure import digest, read, write

DEST = metadata.FOLDER / "records/class-table-cost"
ORDERS = (("ordinary", "recorded"), ("recorded", "ordinary"))
SIDES = ("parent", "landed")


def outputs(root, side):
    base = root / side
    yield base / "measurement.json"
    yield base / "jvm.stdout"
    for method in ("components", "getters"):
        yield base / method / "Calls.jvm-bytecode"
        for i in range(3):
            yield base / method / f"{i}.stdout"


def qualified_calls(report, side, mode):
    ordinary = mode == "ordinary"
    roots = [] if ordinary else [metadata.ROOT_CLASS]
    if report["observedRoot"] != (None if ordinary else metadata.ROOT_CLASS) or set(report["tasks"]) != {"components", "getters"}:
        raise ValueError("different startup mode or metadata entries")
    calls = []
    for method, task in report["tasks"].items():
        if set(task["selectors"]) != {"0", "1", "2"}:
            raise ValueError("different selector coverage")
        for row in task["selectors"].values():
            verdict = "violation" if side == "parent" and method == "components" else "verified"
            if row["verdict"] != verdict or row["observedRoots"] != roots or set(row["states"]) != set(roots):
                raise ValueError(f"incomplete {side}/{method} in the {mode} timing trial")
            calls.append(row)
    return calls


def compare():
    checker = Path(os.environ["JVMCONTRACT"])
    result = {"job": os.environ["VERIFY_JOB_ID"], "source": os.environ["VERIFY_SOURCE_COMMIT"],
              "libTree": os.environ["JVMCONTRACT_LIB_TREE"], "checkerSha256": digest(checker), "trials": {}}
    DEST.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="property-cost-") as scratch, tarfile.open(DEST / "cases.tar.gz", "w:gz") as archive:
        work = Path(scratch)
        for pair, order in enumerate(ORDERS, 1):
            for mode in order:
                label = f"pair-{pair}/{mode}"
                out = work / label
                sides = {}
                for side in SIDES:
                    start = time.perf_counter()
                    metadata.measure(side, False, mode == "ordinary", destination=out)
                    elapsed = time.perf_counter() - start
                    report = read(out / side / "measurement.json")
                    calls = qualified_calls(report, side, mode)
                    sides[side] = {"wholeSeconds": round(elapsed, 6), "checkerSeconds": round(sum(r["seconds"] for r in calls), 6)}
                    for path in outputs(out, side):
                        archive.add(path, arcname=path.relative_to(work).as_posix())
                result["trials"][label] = sides
                print(label, sides, flush=True)
    result["casesSha256"] = digest(DEST / "cases.tar.gz")
    write(DEST / "measurement.json", result)


if __name__ == "__main__":
    compare()

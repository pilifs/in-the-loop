"""Acquire original tool receipts through the namespace while no model process is running."""

import base64
import hashlib
import json
from pathlib import Path
import runner_core as core

INSPECT = """import hashlib,json,pathlib,sys
root=pathlib.Path('/opt/product/examples/001-case/receipts')/sys.argv[1]
rows=[]
for file in sorted(root.glob('*/result.json')):
 if file.is_symlink() or not file.resolve().is_relative_to(root.resolve()): continue
 rows.append([str(file.relative_to(root)),hashlib.sha256(file.read_bytes()).hexdigest()])
print(json.dumps(rows))"""


def initial(product, case, task, ledger):
    result = core.case_run(product, case, ["python3", "-c", INSPECT, task], ledger)
    if result["exit"]:
        raise core.Stopped("evidence", "The task receipt inventory could not be read.")
    return set(tuple(r) for r in json.loads(result["output"]))


def save(product, case, task, rows, before, ledger):
    for row in rows:
        sub = Path(row["receipt"])
        relative = sub.relative_to("receipts", task)
        if (relative.as_posix(), row["sha256"]) in before:
            continue
        attempt = sub.parent
        base = "/opt/product/examples/001-case/" + attempt.as_posix()
        index_script = """import hashlib,json,pathlib,sys
folder=pathlib.Path(sys.argv[1]);records=[]
for f in sorted(folder.rglob('*')):
 if f.is_file() and not f.is_symlink() and f.resolve().is_relative_to(folder.resolve()): records.append([str(f.relative_to(folder)),f.stat().st_size,hashlib.sha256(f.read_bytes()).hexdigest()])
print(json.dumps(records))"""
        listed = core.case_run(product, case, ["python3", "-c", index_script, base], ledger)
        if listed["exit"]:
            raise core.Stopped("evidence", "The fresh receipt inventory could not be archived.")
        for name, size, expected in json.loads(listed["output"]):
            part = Path(name)
            if part.is_absolute() or ".." in part.parts or size < 0:
                raise core.Stopped("evidence", "Invalid receipt member path.")
            dest = ledger.root / "evidence-files" / attempt / part
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                if core.isolation.digest(dest) != expected:
                    raise core.Stopped("evidence", "An earlier archived receipt has different bytes.")
                continue
            read = "import base64,pathlib,sys;f=pathlib.Path(sys.argv[1]).open('rb');f.seek(int(sys.argv[2]));print(base64.b64encode(f.read(64000)).decode())"
            with dest.open("xb") as file:
                for offset in range(0, size, 64000):
                    chunk = core.case_run(
                        product, case, ["python3", "-c", read, base + "/" + name, str(offset)], ledger
                    )
                    if chunk["exit"]:
                        raise core.Stopped(
                            "evidence", "A receipt member could not be read from the case."
                        )
                    file.write(base64.b64decode(chunk["output"].strip(), validate=True))
            if core.isolation.digest(dest) != expected:
                raise core.Stopped("evidence", "A receipt member changed while being archived.")
        local = ledger.root / "evidence-files" / attempt / "records/controls.json"
        if local.is_file():
            controls = json.loads(local.read_bytes()).get("records", [])
            observed = {
                r["revision"]: r.get("observations", [])
                for r in controls
                if r.get("status") == "exited"
                and r.get("exitCode") == 0
                and r.get("kind") == "jvm-control"
                and r.get("observations")
            }
            row["observationsPerRevision"] = {key: len(value) for key, value in observed.items()}
            row["jvmTwoSided"] = len(observed) >= 2
            row["jvmObservationsDiffer"] = (
                len(
                    {
                        hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()
                        for v in observed.values()
                    }
                )
                > 1
            )
        row["archived"] = True
    return [row for row in rows if row.get("archived")]

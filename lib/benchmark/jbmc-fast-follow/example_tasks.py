"""Run the registered ordinary native tasks through the numbered-example entry point."""
import os
from pathlib import Path
import subprocess
import sys

from measure import EVIDENCE, FAMILIES, ROOT, digest, javaenv, load, write


def main():
    result = {"job": os.environ["VERIFY_JOB_ID"], "source": os.environ["VERIFY_SOURCE_COMMIT"],
              "checkerSha256": digest(os.environ["JVMCONTRACT"]), "examples": {}}
    dest = EVIDENCE / "successor/example-tasks"
    dest.mkdir(parents=True, exist_ok=True)
    failures = []
    for family, number in FAMILIES.items():
        folder, = (ROOT / "examples").glob(f"{number}-*")
        tasks = {t["id"]: t["expected"] for t in load(folder / "target.json")["tasks"] if t["kind"] == "prove"}
        def receipts(task):
            return set((folder / "receipts" / task).glob("20*/result.json"))
        before = {key: receipts(key) for key in tasks}
        argv = [sys.executable, "-B", "examples/tools/build.py", str(number), "--tasks", ",".join(tasks), "--checker-seconds", "120"]
        run = subprocess.run(argv, cwd=ROOT, env=javaenv(), capture_output=True, text=True)
        (dest / (family + ".log")).write_text(run.stdout + run.stderr)
        measured = {}
        for key, expected in tasks.items():
            new = receipts(key) - before[key]
            if len(new) != 1:
                failures.append(f"{number}/{key}: {len(new)} fresh receipts")
                continue
            path, = new
            receipt = load(path)
            status = receipt["conclusion"]["status"]
            measured[key] = {"status":status, "receipt":path.relative_to(ROOT).as_posix(), "sha256":digest(path)}
            if status != expected: failures.append(f"{number}/{key}: {status}, expected {expected}")
        result["examples"][str(number)] = measured
        print(number, {k:v["status"] for k,v in measured.items()}, flush=True)
        if run.returncode: failures.append(f"{number}: runner exited {run.returncode}")
    write(dest / "measurement.json",result)
    if failures: raise ValueError("\n".join(failures))


if __name__ == "__main__":
    main()

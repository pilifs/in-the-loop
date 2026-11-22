"""Run the normal example entries and bind their evidence to this job, verifier and input graph."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SETUP = Path.home() / ".cache/in-the-loop/spring-java-data"
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import runtime_maven

def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()

def read(path):
    return json.loads(path.read_bytes())

def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")

def seed(folder):
    """Restore the setup session's products by the example's independently frozen hashes."""
    prep = read(folder / "target.json")["preparation"]
    entries = read(folder / prep["libraryCatalog"]) if "libraryCatalog" in prep else {}
    entries.update({item["coordinates"]:item for item in prep.get("artifacts", [])})
    for record in prep.get("capturedBuilds", {}).values():
        for item in read(folder / record)["artifacts"]:
            entries[item["sha256"]] = item
    cache = runtime_maven.Cache()
    for name, item in entries.items():
        expected = item["sha256"]
        if cache.path(expected).is_file() and digest(cache.path(expected)) == expected:
            continue
        if coords := item.get("coordinates"):
            group, artifact, version = coords.split(":")
            src = SETUP / "m2" / group.replace(".", "/") / artifact / version / f"{artifact}-{version}.jar"
        else:
            candidates = [p for p in (SETUP / "artifacts").glob("*.jar") if digest(p) == expected]
            if not candidates:
                continue
            src, = candidates
        if src.is_file() and digest(src) == expected:
            cache.store(src, expected)

def run_cmd(argv, path, env=None):
    started = time.monotonic()
    with path.open("wb") as log:
        proc = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        _, status, use = os.wait4(proc.pid, 0)
        proc.returncode = os.waitstatus_to_exitcode(status)
    return dict(exit=proc.returncode, seconds=round(time.monotonic()-started, 4),
                peakRssBytes=use.ru_maxrss*1024, log=path.name, logSha256=digest(path))

def measure(number, stage, budget, only):
    folder, = (ROOT / "examples").glob(f"{number}-*")
    spec = read(folder / "target.json")
    seed(folder)
    out = folder / "records" / stage
    out.mkdir(parents=True, exist_ok=True)
    tasks = [t for t in spec["tasks"] if t["kind"] == "prove" and (not only or t["id"] in only)]
    if only and set(only) != {t["id"] for t in tasks}:
        raise ValueError("unknown proof task")
    argv = [sys.executable, "examples/tools/build.py", number]
    report = {"job":os.environ["VERIFY_JOB_ID"], "source":os.environ["VERIFY_SOURCE_COMMIT"],
              "checkerSha256":digest(Path(os.environ["JVMCONTRACT"])), "libTree":os.environ["JVMCONTRACT_LIB_TREE"],
              "secondsPerCheck":budget, "targetSha256":digest(folder / "target.json"),
              "oracleSha256":digest(folder / "controls/table.json"), "tasks":{}}
    def save():
        write(out / "run.json", report)
    failures = []
    for task_id in dict.fromkeys(t for task in tasks for t in task["requires"]):
        measured = run_cmd([*argv, "--task",task_id], out / f"{task_id}.log")
        report.setdefault("replays", {})[task_id] = measured
        if measured["exit"]:
            failures.append(task_id)
        save()
    before = set((folder / "records/finite-proofs").glob("*"))
    report["finite"] = run_cmd([*argv, "--finite-domain", "--tasks", ",".join(t["id"] for t in tasks),
                                "--checker-seconds", str(max(90, budget))], out / "finite.log")
    batches = set((folder / "records/finite-proofs").glob("*")) - before
    if len(batches) == 1:
        batch, = batches
        report["finite"]["directory"] = batch.relative_to(folder).as_posix()
    if report["finite"]["exit"] or len(batches) != 1:
        failures.append("finite")
    save()
    for task in tasks:
        name = task["id"]
        dest = folder / "receipts" / name
        previous = set(dest.glob("*/result.json"))
        run = run_cmd([*argv, "--task", name, "--checker-seconds", str(budget)], out / (name+".log"))
        fresh = set(dest.glob("*/result.json")) - previous
        if len(fresh) == 1:
            path, = fresh
            result = read(path)
            run.update(status=result["conclusion"]["status"], receipt=path.relative_to(folder).as_posix(),
                       sha256=digest(path))
        else:
            failures.append(name)
        report["tasks"][name] = run
        save()
    print(json.dumps({k:r.get("status") for k,r in report["tasks"].items()}))
    if failures:
        raise ValueError("incomplete example workflows: "+", ".join(failures))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number")
    parser.add_argument("--stage", default="opening")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--only", nargs="+")
    parser.add_argument("--seed-only", action="store_true")
    args = parser.parse_args()
    if args.seed_only:
        folder, = (ROOT / "examples").glob(args.number+"-*")
        seed(folder)
    else:
        measure(args.number, args.stage, args.seconds, args.only)

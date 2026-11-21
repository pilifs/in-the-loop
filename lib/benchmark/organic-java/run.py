"""Run the public task plan on one original PR. Keep the first native attempts and finite receipts separately."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def read(path):
    return json.loads(path.read_text())


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def baseline_inputs():
    selected = []
    for name in ("lib/src", "lib/models", "examples/tools/targets"):
        selected.extend(f for f in Path(name).rglob("*") if f.is_file() and "__pycache__" not in f.parts
                        and f.suffix in (".rs", ".java", ".py", ".contract", ".json") and not f.name.startswith("test_"))
    selected.extend(map(Path, ("lib/Cargo.lock", "lib/Cargo.toml", "examples/tools/build.py", "examples/tools/checker_output.py")))
    h = hashlib.sha256()
    for file in sorted(selected):
        h.update(file.as_posix().encode() + b"\0" + bytes.fromhex(digest(file)))
    return len(selected), h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", choices=read(HERE / "cases.json")["cases"])
    parser.add_argument("--stage", default="baseline")
    parser.add_argument("--route", choices=("native", "finite"), required=True)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--tasks", help="explicit comma-separated list of tasks for a repeat")
    args = parser.parse_args()
    case = read(HERE / "cases.json")["cases"][args.example]
    folder = ROOT / "examples" / case["folder"]
    archive = folder / "records" / (args.stage + "-" + args.route)
    archive.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    pin = read(HERE / "baseline.json")
    if args.stage == "baseline":
        if baseline_inputs() != (pin["engineAndWorkflowFiles"], pin["engineAndWorkflowSha256"]):
            parser.error("the actual selected engine and workflow sources differ from the common baseline")
        exe = Path(env.get("ORGANIC_BASELINE_BINARY", Path.home() / ".cache/in-the-loop/external-upgrades" /
                           pin["executableSha256"] / "jvmcontract"))
        if digest(exe) != pin["executableSha256"]:
            parser.error("the original native executable differs from the baseline")
        env.update(JVMCONTRACT=str(exe), JVMCONTRACT_LIB_TREE=pin["libTree"], VERIFY_SOURCE_COMMIT=pin["revision"])
    tasks = args.tasks or ",".join(t["id"] for t in read(folder / "target.json")["tasks"]
                                  if args.route == "native" or t["kind"] != "replay")
    argv = [sys.executable, "examples/tools/build.py", args.example]
    if args.route == "finite":
        argv += ["--finite-domain", "--tasks", tasks, "--checker-seconds", str(args.seconds)]
        outputs = folder / "records/finite-proofs"
    else:
        argv += ["--tasks", tasks, "--checker-seconds", str(args.seconds)]
        outputs = folder / "receipts"
    before = set(outputs.glob("*/*")) if outputs.exists() else set()
    before_journals = set(outputs.glob("*/executions/*"))
    start = time.monotonic()
    with (archive / "workflow.log").open("w") as stream:
        result = subprocess.run(argv, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    if args.route == "finite":
        for batch in sorted({f.parent for f in set(outputs.glob("*/*")) - before}):
            shutil.copytree(batch, archive / batch.name)
    else:
        fresh = [f for f in set(outputs.glob("*/*")) - before if f.name != "executions"]
        fresh.extend(set(outputs.glob("*/executions/*")) - before_journals)
        for path in sorted(fresh):
            dest = archive / path.relative_to(outputs)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(path, dest)
    record = {"example": args.example, "route": args.route, "stage": args.stage, "workflowExit": result.returncode,
              "seconds": round(time.monotonic() - start, 3), "checkerSeconds": args.seconds, "tasks": tasks.split(","),
              "verifierCommit": env.get("VERIFY_SOURCE_COMMIT"), "checkerSha256": digest(Path(env["JVMCONTRACT"])),
              "artifactRecords": {side: digest(folder / path) for side, path in
                                  read(folder / "target.json")["preparation"].get("capturedBuilds", {}).items()}}
    (archive / "run.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())

"""Run the public task plan on one original PR. Keep the first native attempts and finite receipts separately."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
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


def frozen_run(case, pin, route):
    """Use the original Git tree when a later corpus preparation needs a fresh baseline."""
    source = Path(os.environ.get("ORGANIC_SOURCE_REPOSITORY", ROOT))
    original = ROOT / "examples" / case["folder"]
    with tempfile.TemporaryDirectory(prefix="organic-baseline-tree-") as work:
        frozen = Path(work)
        paths = ["examples/tools", "examples/schema", "examples/tags.json", "lib/src", "lib/models",
                 "lib/Cargo.toml", "lib/Cargo.lock", "lib/tools"]
        with subprocess.Popen(["git", "-C", source, "archive", pin["revision"], *paths], stdout=subprocess.PIPE) as proc:
            with tarfile.open(fileobj=proc.stdout, mode="r|") as archive:
                archive.extractall(frozen, filter="data")
            if proc.wait():
                raise ValueError("unable to export the pinned baseline sources")
        target = frozen / "examples" / case["folder"]
        shutil.copytree(original, target, ignore=shutil.ignore_patterns("records", "receipts", "__pycache__"))
        for name in read(original / "target.json")["preparation"].get("capturedBuilds", {}).values():
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original / name, target / name)
        runner = frozen / "lib/benchmark/organic-java"
        runner.mkdir(parents=True)
        for name in ("cases.json", "baseline.json", "run.py"):
            shutil.copyfile(HERE / name, runner / name)
        env = dict(os.environ, ORGANIC_FROZEN_BASELINE="1")
        proc = subprocess.run([sys.executable, runner / "run.py", *sys.argv[1:]], cwd=frozen, env=env)
        receipt = Path("records") / ("baseline-" + route)
        if (target / receipt).is_dir():
            shutil.copytree(target / receipt, original / receipt)
        return proc.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    corpus = read(HERE / "cases.json")
    cases = {**corpus["cases"], **corpus.get("reserves", {})}
    parser.add_argument("example", choices=cases)
    parser.add_argument("--stage", default="baseline")
    parser.add_argument("--route", choices=("native", "finite"), required=True)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--tasks", help="explicit comma-separated list of tasks for a repeat")
    args = parser.parse_args()
    case = cases[args.example]
    folder = ROOT / "examples" / case["folder"]
    archive = folder / "records" / (args.stage + "-" + args.route)
    env = dict(os.environ)
    pin = read(HERE / "baseline.json")
    if args.stage == "baseline":
        if baseline_inputs() != (pin["engineAndWorkflowFiles"], pin["engineAndWorkflowSha256"]):
            if env.get("ORGANIC_FROZEN_BASELINE"):
                parser.error("the exported Git sources differ from the frozen baseline fingerprint")
            return frozen_run(case, pin, args.route)
        exe = Path(env.get("ORGANIC_BASELINE_BINARY", Path.home() / ".cache/in-the-loop/external-upgrades" /
                           pin["executableSha256"] / "jvmcontract"))
        if digest(exe) != pin["executableSha256"]:
            parser.error("the original native executable differs from the baseline")
        env.update(JVMCONTRACT=str(exe), JVMCONTRACT_LIB_TREE=pin["libTree"], VERIFY_SOURCE_COMMIT=pin["revision"])
    archive.mkdir(parents=True, exist_ok=False)
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

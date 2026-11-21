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


# What a baseline is made by, by inventory: the trees and files its fingerprint covers, and the paths a frozen run
# exports. A pin names its inventory (`inputs` in baseline.json); a pin from before the key is inventory 1, and its
# fingerprint and export are computed exactly as they were, so an old revision still exports and still matches.
# Inventory 2 adds lib/python: the proof output reader and the proof methods that moved there
# (jvmcontract_io.py, jvm_array_induction.py), which the tools under examples/ import and a fingerprint of
# examples/ alone would miss. It also adds verification/layout.py, which examples/tools/accept.py loads at import
# since results may be kept by day: an export without it does not start.
INVENTORIES = {
    1: {"trees": ("lib/src", "lib/models", "examples/tools/targets"),
        "files": ("lib/Cargo.lock", "lib/Cargo.toml", "examples/tools/build.py", "examples/tools/checker_output.py"),
        "export": ("examples/tools", "examples/schema", "examples/tags.json", "lib/src", "lib/models",
                   "lib/Cargo.toml", "lib/Cargo.lock", "lib/tools")},
    2: {"trees": ("lib/src", "lib/models", "lib/python", "examples/tools/targets"),
        "files": ("lib/Cargo.lock", "lib/Cargo.toml", "examples/tools/build.py", "examples/tools/checker_output.py",
                  "verification/layout.py"),
        "export": ("examples/tools", "examples/schema", "examples/tags.json", "lib/src", "lib/models", "lib/python",
                   "lib/Cargo.toml", "lib/Cargo.lock", "lib/tools", "verification/layout.py")},
}
CURRENT_INVENTORY = 2  # what a new baseline is pinned with


def inventory_of(pin):
    version = pin.get("inputs", 1)
    if version not in INVENTORIES:
        raise ValueError(f"the baseline names input inventory {version!r}, which this runner does not know")
    return INVENTORIES[version]


def baseline_inputs(version=1, root=Path(".")):
    """(number of files, fingerprint) of the baseline's inputs under `root`, as inventory `version` lists them."""
    inventory = INVENTORIES[version]
    root = Path(root)
    selected = []
    for name in inventory["trees"]:
        selected.extend(f.relative_to(root) for f in (root / name).rglob("*") if f.is_file() and "__pycache__" not in f.parts
                        and f.suffix in (".rs", ".java", ".py", ".contract", ".json") and not f.name.startswith("test_"))
    selected.extend(map(Path, inventory["files"]))
    h = hashlib.sha256()
    for file in sorted(selected):
        h.update(file.as_posix().encode() + b"\0" + bytes.fromhex(digest(root / file)))
    return len(selected), h.hexdigest()


def frozen_run(case, pin, route):
    """Use the original Git tree when a later corpus preparation needs a fresh baseline."""
    source = Path(os.environ.get("ORGANIC_SOURCE_REPOSITORY", ROOT))
    original = ROOT / "examples" / case["folder"]
    with tempfile.TemporaryDirectory(prefix="organic-baseline-tree-") as work:
        frozen = Path(work)
        paths = inventory_of(pin)["export"]
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
    cases = {**corpus["cases"], **corpus.get("reserves", {}), **corpus.get("adoptions", {})}
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
        inventory_of(pin)
        if baseline_inputs(pin.get("inputs", 1)) != (pin["engineAndWorkflowFiles"], pin["engineAndWorkflowSha256"]):
            if env.get("ORGANIC_FROZEN_BASELINE"):
                parser.error("the exported Git sources differ from the frozen baseline fingerprint")
            return frozen_run(case, pin, args.route)
        exe = Path(env.get("ORGANIC_BASELINE_BINARY", Path.home() / ".cache/in-the-loop/external-upgrades" /
                           pin["executableSha256"] / "jvmcontract"))
        if digest(exe) != pin["executableSha256"]:
            parser.error("the original native executable differs from the baseline")
        env.update(JVMCONTRACT=str(exe), JVMCONTRACT_LIB_TREE=pin["libTree"], VERIFY_SOURCE_COMMIT=pin["revision"])
    archive.mkdir(parents=True, exist_ok=False)
    target = read(folder / "target.json")
    original = [t for t in target["tasks"] if t["kind"] == "replay" or not read(folder / t["claim"]).get("observedInitializers")]
    tasks = args.tasks or ",".join(t["id"] for t in original if args.route == "native" or t["kind"] != "replay")
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

#!/usr/bin/env python3
"""The frozen claim, unchanged, proved or refuted on the slices the replays ran: preservation and its mutation control.

    python3 proofs/prove.py preservation | mutant-preservation
        [--jvmcontract PATH] [--work DIR] [--timeout SECONDS] [--max-array-length N] [--unwind N]

Each task is target.json's: the pair (`positive`: before against after; `mutation`: after against the constructed
mutant), the claim file, the engine and the gap mode. The claim's assumption, nullable parameters and bounds are
passed to `jvmcontract equivalence` as they are written, on the target itself, `BCrypt.hashpw(String, String)` (no
adapter: the method is static and takes Strings). The verifier makes the check a property of the pair of versions
(lib/src/pairing.rs), since the claim has an assumption and nullable Strings.

Why beside the route (examples/tools/targets/runtime.py), which runs the same command on the same classes: the
route gives the verifier ten minutes (`VERIFIER_TIMEOUT`, a timeout change being another attempt), and this check
is given the job's. Nothing else differs, and the classes are the route's own:

- each revision is prepared by the route (`runtime.prepare`): the exact commit's BCrypt.java fetched from github.com,
  for the mutant patched with controls/us-ascii.patch, compiled alone by JDK 8 with the slice's flags
  (`preparation.slice`), before's class compared byte for byte with Spring Security 5.2.0.M4's published one; the
  slice's JAR is then extracted into a folder of classes, as the route does for `jvmcontract equivalence`;
- each slice's JAR must be the one its replay ran: the newest receipt under receipts/replay (before, after) or
  receipts/mutant-replay (after, mutant) records it, and a JAR of another hash ends the run. So nothing proved here
  is about a JAR the controls did not run.

The three properties a driver has (examples/tools/beside_route.py): it records identities (evidence.json, through
`accept.record`: the claim file's hash, the bound, each slice JAR with its revision and hash, marked constructed
since each is built from source, the verifier's binary and this script); it ends the run when the constructed
mutant's JAR is not the one the mutant replay ran (and so for every slice, above); and a run with
--max-array-length or --unwind is a trial, which its record and its last line say. Exit 0 when the verdict is the
task's expected one.

The checker takes the unchanged callee `hashpw(byte[], String)` as one function of both versions (lib/src/bmc/ties.rs):
its outcome is a function of the password's bytes, the salt and BCrypt's static tables, so the two conversions'
bytes are what the proof compares, and no cipher is computed or substituted. A counterexample is run on a JVM, with
the real cipher, before it is believed.
"""
import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE.parent / "tools"))
import beside_route  # noqa: E402  (what every driver does the same way: the bound, the trial, the record)
from targets import runtime, workflow  # noqa: E402  (the route's own preparation of a slice)

TARGET = "org.springframework.security.crypto.bcrypt.BCrypt#hashpw(java.lang.String, java.lang.String)"


def replayed(here: Path, task: str, revision: str) -> str | None:
    """The hash the newest receipt of `task` records for `revision`'s original JAR."""
    for receipt in sorted((here / "receipts" / task).glob("*/result.json"), reverse=True):
        result = json.loads(receipt.read_text())
        for d in ((result.get("claim") or {}).get("target") or {}).get("dependencies") or []:
            if d.get("revision") == revision and d.get("role") == "original":
                return d.get("sha256")
    return None


class SliceRun(beside_route.Run):
    """A run on the slices: beside_route.Run's bound, record and finish, with the route's preparation in place of
    pinned JARs and an adapter."""

    def __init__(self, here: Path, task_id: str, work: Path):
        self.here, self.entry, self.jars = here, TARGET, None
        self.target = json.loads((here / "target.json").read_text())
        self.task = next((t for t in self.target["tasks"] if t["id"] == task_id and t["kind"] == "equivalence"), None)
        if self.task is None:
            sys.exit(f"{task_id} is no equivalence task in target.json")
        self.claim_file = here / self.task["claim"]
        self.claim = json.loads(self.claim_file.read_text())
        self.work = work / task_id
        self.work.mkdir(parents=True, exist_ok=True)
        self.sources, self.used, self.compiled, self.mutant_record = [], [], [], {}

    def sliced(self, revision: str) -> Path:
        """The revision's slice, prepared by the route and checked against the JAR its replay ran, as a folder of
        classes."""
        example = json.loads((self.here / "example.json").read_text())
        plan = workflow.plan_task(self.here, example, self.target, self.task["id"])
        if not hasattr(plan, "revisions"):
            sys.exit(f"the route does not plan {self.task['id']}: {plan}")
        where = self.work / "prepare" / revision
        if where.exists():
            shutil.rmtree(where)
        prepared = runtime.prepare(plan, revision, where)
        if getattr(prepared, "stage", None) != "artifacts-ready":
            sys.exit(f"revision {revision} was not prepared: {getattr(prepared, 'diagnostic', prepared)}")
        jar = next(a for a in prepared.artifacts if a.role == "original")
        path = Path(prepared.workdir) / jar.path
        replay = "mutant-replay" if self.constructed(revision) else "replay"
        recorded = replayed(self.here, replay, revision)
        print(f"{revision}: {jar.path}, sha256 {jar.sha256}: " + ("the JAR the " + replay + " ran" if jar.sha256 == recorded else f"the {replay}'s receipt records {recorded}"))
        if jar.sha256 != recorded:
            sys.exit(f"the slice of {revision} (sha256 {jar.sha256}) is not the JAR the {replay} ran ({recorded}): "
                     + ("run the replay first" if recorded is None else "the recipe, the commit or the compiler changed since"))
        self.used.append({"revision": revision, "name": path.name, "sha256": jar.sha256, "constructed": True})
        if self.constructed(revision):
            recipe = self.target["history"]["revisions"][revision]["mutant"]
            self.mutant_record.update(sha256=jar.sha256, replayed=recorded, patch=recipe["patch"])
            print(f"mutant: {path.name} built from {recipe['patch']}, sha256 {jar.sha256}")
        classes = self.work / "classes" / revision
        if classes.exists():
            shutil.rmtree(classes)
        classes.mkdir(parents=True)
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.is_dir() or info.filename.startswith("/") or ".." in Path(info.filename).parts:
                    continue
                (classes / info.filename).parent.mkdir(parents=True, exist_ok=True)
                (classes / info.filename).write_bytes(z.read(info))
        return classes


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("task")
    p.add_argument("--jvmcontract", default=shutil.which("jvmcontract") or str(HERE.parent.parent / "lib/target/release/jvmcontract"),
                   help="the verifier: the one on the PATH, or else this repository's release build")
    p.add_argument("--work", type=Path, default=Path("/tmp/example-307-proofs"))
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--max-array-length", type=int, help="a smaller bound than the claim's, for a trial run only")
    p.add_argument("--unwind", type=int, help="another unwinding than the claim's, for a trial run only")
    args = p.parse_args()

    run = SliceRun(HERE, args.task, args.work)
    task, claim = run.task, run.claim
    bound = run.bound(args.max_array_length, args.unwind)
    pair = next(x for x in run.target["history"]["pairs"] if x["name"] == task["pair"])
    before, after = run.sliced(pair["before"]), run.sliced(pair["after"])
    argv = [args.jvmcontract, "equivalence", "--before", str(before), "--after", str(after), "--target", TARGET]
    if claim.get("assume"):
        argv += ["--assume", claim["assume"]]
    if task.get("allowedChange"):
        argv += ["--unchanged-unless", task["allowedChange"]]
    argv += [x for n in claim.get("nullable") or [] for x in ("--nullable", n)]
    argv += ["--engine", task["engine"], "--gaps", task["gaps"]]
    argv += run.bound_args(bound)
    argv += ["--timeout", str(args.timeout), "--work", str(run.work / "work"), "--json"]
    run.finish(argv, bound, args.jvmcontract, Path(__file__),
               summary=lambda native: f"calls taken as one function {native.get('calls_as_one_function', 0)}, related {native.get('calls_related', 0)}")


if __name__ == "__main__":
    main()

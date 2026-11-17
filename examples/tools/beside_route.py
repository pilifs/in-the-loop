"""What every example's proof driver (examples/NNN-*/proofs/prove.py) does the same way: an answer given beside the
route, run so that the acceptance check (accept.py) can believe it from what the job left.

    run = beside_route.Run(HERE, ENTRY, args.task, jars=args.jars, work=args.work)
    jars, adapter = run.prepared(revision)        the revision's class path, and the adapter compiled against it
    bound = run.bound(args.max_array_length, args.unwind, default_unwind)
    run.finish(argv, bound, args.jvmcontract)     runs the verifier, writes outcome.json and evidence.json, exits

The three properties a driver has (examples/289's first):

- it records identities: beside outcome.json, evidence.json (accept.record) holds the claim file's hash, the bound,
  each JAR on the class path with its revision and hash, the adapter's sources and compiled classes, the verifier's
  binary and the driver;
- it ends the run when a constructed mutant's JAR is not the one the mutant replay ran (the newest receipt under
  receipts/mutant-replay): nothing proved of another JAR is the task's answer;
- a run at another bound or unwinding than the claim's (--max-array-length, --unwind) is marked a trial, in its record
  and on its last line: it answers nothing about the claim.

The mutant is built by the published route's recipe (examples/tools/targets/runtime.py, `_published_mutant`): the
base release's source file from its sources JAR, checked against the blob sources.lock.json records, patched with the
control's patch, compiled against the base's JARs with the --release and debugging flags the base's own class shows,
and its classes put in place of the base JAR's own in a copy of it (entries in order, with their dates). That is what
makes its hash comparable with the replay's.

Each example keeps its own entry, its lemmas, models, observed initializers and the verifier's arguments.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "targets"))
import accept  # noqa: E402  (the acceptance check: a driver writes the record it reads, evidence.json)
import runtime_jar  # noqa: E402  (the route's reader of class files: the flags a class was compiled with)

EXPECTED = {"established": "verified", "refuted": "violation"}
SOURCE_ROOT = "/src/main/java/"


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def blob(data: bytes) -> str:
    """A file's git blob id (git hash-object), which sources.lock.json records for each source file."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def fetched(url: str, pinned: str | None, jars: Path | None, into: Path) -> Path:
    """The file at a pinned URL, from `jars` by its name or fetched, with the hash it is pinned to (any, for None)."""
    name = url.rsplit("/", 1)[1]
    path = (jars / name) if jars else None
    if path is None or not path.is_file():
        path = into / name
        if not path.is_file():
            with urllib.request.urlopen(url, timeout=120) as r:
                path.write_bytes(r.read())
    digest = sha256(path)
    if pinned is not None and digest != pinned:
        sys.exit(f"{path}: sha256 {digest}, pinned to {pinned}")
    return path


class Run:
    """One run of an example's driver on one task of its target.json."""

    def __init__(self, here: Path, entry: str, task_id: str, *, jars: Path | None, work: Path, kinds=("prove", "equivalence")):
        self.here, self.entry, self.jars = here, entry, jars
        self.target = json.loads((here / "target.json").read_text())
        self.task = next((t for t in self.target["tasks"] if t["id"] == task_id and t["kind"] in kinds), None)
        if self.task is None:
            sys.exit(f"{task_id} is no {' or '.join(kinds)} task in target.json")
        self.claim_file = here / self.task["claim"]
        self.claim = json.loads(self.claim_file.read_text())
        if entry not in " ".join(a.get("text", "") for a in self.claim.get("assumptions", [])):
            sys.exit(f"{self.task['claim']} does not name the adapter entry {entry}")
        self.work = work / task_id
        (self.work / "jars").mkdir(parents=True, exist_ok=True)
        self.sources = [here / s for s in self.target["preparation"]["adapters"]]
        self.used: list[dict] = []  # each JAR put on a class path, with its revision and hash
        self.compiled: list[Path] = []  # each folder the adapter was compiled into
        self.mutant_record: dict = {}  # the constructed mutant's JAR, and the one the mutant replay ran

    # -- the class path

    def artifacts(self, revision: str) -> list[Path]:
        """The revision's pinned JARs, in target.json's order, each with the hash it is pinned to."""
        out = [fetched(a["url"], a["sha256"], self.jars, self.work / "jars")
               for a in self.target["preparation"]["artifacts"] if a["revision"] == revision]
        if not out:
            sys.exit(f"target.json has no artifacts for revision {revision}")
        self.used.extend({"revision": revision, "name": j.name, "sha256": sha256(j)} for j in out)
        return out

    def constructed(self, revision: str) -> bool:
        return "mutant" in self.target["history"]["revisions"][revision]

    def prepared(self, revision: str, release: str = "21") -> tuple[list[Path], Path]:
        """The revision's class path (a mutant's built), and the adapter compiled against it."""
        jars = self.mutant(revision) if self.constructed(revision) else self.artifacts(revision)
        adapter = self.work / f"adapter-{revision}"
        if adapter.exists():
            shutil.rmtree(adapter)
        adapter.mkdir()
        subprocess.run(["javac", "--release", release, "-g", "-proc:none", "-cp", ":".join(map(str, jars)), "-d", str(adapter),
                        *map(str, self.sources)], check=True)
        self.compiled.append(adapter)
        return jars, adapter

    def mutant(self, revision: str) -> list[Path]:
        """The constructed mutant's class path: its base's, with the patched classes in a copy of the base's first JAR.
        Ends the run when the copy is not the JAR the mutant replay ran."""
        recipe = self.target["history"]["revisions"][revision]["mutant"]
        base, patch = recipe["base"], self.here / recipe["patch"]
        if sha256(patch) != recipe["sha256"]:
            sys.exit(f"{recipe['patch']} is not the patch target.json pins")
        lock = json.loads((self.here / "sources.lock.json").read_text())
        [source] = [line.split(" b/", 1)[1].strip() for line in patch.read_text().splitlines() if line.startswith("+++ b/")]
        member = source.split(SOURCE_ROOT, 1)[1]
        into = self.work / "jars"
        base_jars = self.artifacts(base)
        original = base_jars[0]
        url = next(a["url"] for a in self.target["preparation"]["artifacts"] if a["revision"] == base)
        # The sources JAR is pinned where the lock's correspondence records it; the one file taken from it always is,
        # by its git blob.
        correspondence = lock.get("correspondence")
        pinned = next((a.get("sha256") for c in (correspondence if isinstance(correspondence, list) else [])
                       if isinstance(c, dict) and c.get("revision") == base
                       for k, a in (c.get("artifacts") or {}).items() if k.endswith(":sources")), None)
        with zipfile.ZipFile(fetched(url[: -len(".jar")] + "-sources.jar", pinned, self.jars, into)) as z:
            text = z.read(member)
        if blob(text) != lock["revisions"][base]["files"][source]:
            sys.exit(f"{member} in the sources JAR is not the file locked for {base}")
        tree = into / "mutant-src"
        if tree.exists():
            shutil.rmtree(tree)
        (tree / member).parent.mkdir(parents=True)
        (tree / member).write_bytes(text)
        # The patch names the file from the repository's root: the sources JAR has it from the source root.
        strip = 1 + source.split(SOURCE_ROOT, 1)[0].count("/") + SOURCE_ROOT.count("/")
        subprocess.run(["patch", "-s", f"-p{strip}", "-d", str(tree), "-i", str(patch)], check=True)
        patched = (lock.get("mutant") or {}).get("patchedBlob")
        if patched and blob((tree / member).read_bytes()) != patched:
            sys.exit(f"{member}, patched, is not the mutant's locked source")
        name = member[: -len(".java")]
        # The class and the classes nested in it, as the base's JAR holds them: all are recompiled and replaced.
        with zipfile.ZipFile(original) as z:
            own = {n: z.read(n) for n in z.namelist() if n == name + ".class" or n.startswith(name + "$")}
        if not own:
            sys.exit(f"{original.name} holds no {name}.class: the patched file is not one of its sources")
        debug = set().union(*(runtime_jar.debug_attributes(b) for b in own.values()))
        flags = (["-g"] if "LocalVariableTable" in debug else [] if "LineNumberTable" in debug else ["-g:none"]) \
            + (["-parameters"] if "MethodParameters" in debug else [])
        release = max(int.from_bytes(b[6:8], "big") for b in own.values()) - 44
        classes, empty = into / "mutant-classes", into / "no-sources"
        for d in (classes, empty):
            if d.exists():
                shutil.rmtree(d)
            d.mkdir()
        subprocess.run(["javac", "--release", str(release), "-encoding", "UTF-8", "-implicit:none", "-proc:none", "-nowarn",
                        "-Xlint:-options", "-sourcepath", str(empty), *flags, "-d", str(classes),
                        "-cp", ":".join(map(str, base_jars)), str(tree / member)], check=True)
        built = {c.relative_to(classes).as_posix(): c.read_bytes() for c in classes.rglob("*.class")}
        if sorted(built) != sorted(own):
            sys.exit(f"the patched source compiles to {sorted(built)}, and the base's JAR holds {sorted(own)}")
        (into / "mutant").mkdir(exist_ok=True)
        out = into / "mutant" / original.name
        with zipfile.ZipFile(original) as z, zipfile.ZipFile(out, "w") as w:
            for item in z.infolist():
                w.writestr(item, built.get(item.filename) or z.read(item))
        digest, replayed = sha256(out), accept.replayed_mutant(self.here)
        print(f"mutant: {out.name} with {len(built)} class(es) of {name.rsplit('/', 1)[1]} recompiled (--release {release} "
              f"{' '.join(flags)}), sha256 {digest}: "
              + ("the JAR the mutant replay ran" if digest == replayed else f"the mutant replay's receipt records {replayed}"))
        # A mutant that is not the one the replay ran is another artifact: nothing proved of it is the task's answer.
        if digest != replayed:
            sys.exit(f"the mutant's JAR (sha256 {digest}) is not the one the mutant replay ran ({replayed}): "
                     + ("run the mutant replay first" if replayed is None else "the recipe, the base or the compiler changed since"))
        # The base's JARs were recorded under the base; on this class path they are the mutant's, its own JAR constructed.
        del self.used[-len(base_jars):]
        self.used.extend({"revision": revision, "name": j.name, "sha256": sha256(out if j == original else j),
                          **({"constructed": True} if j == original else {})} for j in base_jars)
        self.mutant_record.update(sha256=digest, replayed=replayed, patch=recipe["patch"])
        return [out if j == original else j for j in base_jars]

    # -- the bound, and the run

    def bound(self, max_array_length: int | None = None, unwind: int | None = None, default_unwind: int | None = None) -> dict:
        """The bound the run is at: the claim's, unless --max-array-length or --unwind overrides it, which makes the run
        a trial. `unwind` is None where neither the claim, the driver nor the command line sets one."""
        claimed = self.claim.get("bounds") or {}
        length = claimed.get("maxArrayLength") if max_array_length is None else max_array_length
        own_unwind = claimed.get("unwind", default_unwind)
        ran_unwind = own_unwind if unwind is None else unwind
        trial = length != claimed.get("maxArrayLength") or ran_unwind != own_unwind
        return {"maxArrayLength": length, "unwind": ran_unwind, "trial": trial}

    def bound_args(self, bound: dict) -> list[str]:
        out = []
        if bound["unwind"] is not None:
            out += ["--unwind", str(bound["unwind"])]
        if bound["maxArrayLength"] is not None:
            out += ["--max-array-length", str(bound["maxArrayLength"])]
        return out

    def finish(self, argv: list[str], bound: dict, jvmcontract: str, driver: Path, summary=None):
        """Runs the verifier (`argv`, which ends with --json), writes outcome.json, stderr.txt and evidence.json beside
        each other, prints the verdict, and exits 0 when it is the task's expected one."""
        run = subprocess.run(argv, capture_output=True, text=True)
        (self.work / "outcome.json").write_text(run.stdout)
        (self.work / "stderr.txt").write_text(run.stderr)
        accept.record(self.work, example=self.here.name[:3], task=self.task["id"], claim_file=self.claim_file, bound=bound,
                      artifacts=self.used, adapter_sources=self.sources, adapter_classes=self.compiled,
                      jvmcontract=jvmcontract, driver=Path(driver).resolve(), mutant=self.mutant_record or None)
        try:
            outcome = json.loads(run.stdout)
            # `prove` prints a list of one outcome, `equivalence` the outcome.
            [outcome] = outcome if isinstance(outcome, list) else [outcome]
        except (ValueError, TypeError):
            sys.exit(f"jvmcontract gave no outcome (exit {run.returncode}): {run.stderr.strip()[-2000:]}")
        print(outcome["output"])
        native = ((outcome.get("search") or {}).get("native")) or {}
        expected = EXPECTED[self.task["expected"]]
        print(f"verdict: {outcome['verdict']} (expected {expected}); paths {native.get('paths')}, "
              f"solver calls {native.get('solver_calls')}, variables {native.get('variables')}"
              + (f", {summary(native)}" if summary else "") + f"; outcome in {self.work / 'outcome.json'}")
        if bound["trial"]:
            claimed = self.claim.get("bounds") or {}
            print(f"a trial at bound {bound['maxArrayLength']} and unwinding {bound['unwind']}, not the claim's "
                  f"({claimed.get('maxArrayLength')}): it is no answer to the claim, and {accept.EVIDENCE} says so")
        sys.exit(0 if outcome["verdict"] == expected else 1)

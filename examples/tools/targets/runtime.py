"""Preparation and separate-JVM execution: the runtime stream's side of the interfaces (interfaces.py), for
llm-dlc/loops/example-targets.md (R1-R4). Signatures are frozen. Acquisition follows the brief's downloads policy:
github.com and Maven Central only, every file's sha256 recorded and rechecked.

    lock(plan, revision)                   source-locked: immutable paths, revisions and recipe, hashed; offline, pure
    prepare(plan, revision, workdir)       artifacts-ready: built or fetched, every byte hashed and the classpath
                                           checked; or failed, with its stage, diagnostic and what exists
    run_controls(plan, prepared, workdir)  Phase 0's stub (R4)
    run_verifier(plan, prepared, workdir)  Phase 0's stub (R3)

The two milestones stay apart (R1): a source lock fetches and builds nothing and supplies no proof identity; only an
artifacts-ready preparation does. A preparation never decides a claim, and a partial one is returned as failed with
its stage, never as an empty success.

Routes: `fixture` (a control's fixture revisions, built locally with build_fixtures.py's recipe) is implemented;
`published-artifact` and `upstream-build` (R2) return Unsupported until they are.

On the classpath a preparation refuses: a class held by more than one entry (an adapter or driver shadowing the
target, or two dependencies with one class), a target method missing from the original artifact, and an adapter that
never references the target method (R3's "calls the selected upstream method"). The loaded target's origin, the
ordered classpath, the JDK (by full path, `release` file and `java -version`) and every artifact's sha256 are
recorded in the PreparedTarget and in `prepared.json` in the work directory.
"""

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from targets import runtime_jar, runtime_jdk
from targets.interfaces import RUNTIME, Artifact, PreparedTarget, Unsupported

HERE = Path(__file__).resolve().parent
RECORD = "prepared.json"  # the preparation record a work directory holds; a directory without one is not ours
COMPILE_TIMEOUT = 300


def _fixture_recipe():
    """build_fixtures.py's recipe constants (the fixture route builds with it): its --release and fixed JAR date."""
    spec = importlib.util.spec_from_file_location("targets_build_fixtures", HERE / "fixtures/build_fixtures.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {"release": module.RELEASE, "date": module.DATE}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Refused(Exception):
    """A preparation stops: `stage` is where (lock, workdir, toolchain, build, target, classpath, adapter)."""

    def __init__(self, stage, diagnostic):
        super().__init__(diagnostic)
        self.stage, self.diagnostic = stage, diagnostic


# -- the source lock (offline)

def _entry(plan, revision):
    if revision not in plan.revisions:
        raise Refused("lock", f"revision {revision!r} is not one of the task's ({', '.join(plan.revisions)})")
    entries = [a for a in plan.artifacts if a.get("revision") == revision]
    if len(entries) != 1:
        raise Refused("lock", f"the plan has {len(entries)} artifact entries for revision {revision!r}, not one")
    return entries[0]


def _inside(folder, relative, what):
    """The path `relative` names in `folder`, refused if it (or a link on the way) leads outside it."""
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise Refused("lock", f"{what}: {relative!r} is not a path relative to the example's folder")
    path = (folder / relative).resolve()
    try:
        path.relative_to(folder)
    except ValueError:
        raise Refused("lock", f"{what}: {relative} leads outside the example's folder (to {path})") from None
    if not path.exists():
        raise Refused("lock", f"{what}: {relative} does not exist")
    return path


def _hashed(folder, files):
    return [{"path": p.relative_to(folder).as_posix(), "sha256": sha256(p)} for p in files]


def _java_files(folder, top):
    files = sorted(p for p in top.rglob("*.java"))
    for p in files:  # a link inside the tree can still lead out of it
        if not p.resolve().is_relative_to(folder):
            raise Refused("lock", f"source: {p.relative_to(folder)} leads outside the example's folder (to {p.resolve()})")
    return files


PACKAGE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.M)


def _source_root(folder, file_):
    """The source root a Java file sits under, from its package declaration: gate/adapter for
    gate/adapter/fixture/adapter/GateAdapter.java (package fixture.adapter)."""
    match = PACKAGE.search(file_.read_text(errors="replace"))
    depth = len(match.group(1).split(".")) if match else 0
    root = file_.parent
    for _ in range(depth):
        root = root.parent
    return _inside(folder, root.relative_to(folder).as_posix() if root != folder else ".", "source root")


def _sidecar(folder):
    path = folder / "target.json"
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise Refused("lock", f"cannot read the sidecar {path}: {e}") from None


def _component(folder, files, what):
    """Java sources compiled as one unit: each file's source root, and every .java under those roots, hashed."""
    roots = sorted({_source_root(folder, _inside(folder, f, what)) for f in files})
    sources = sorted({s for r in roots for s in _java_files(folder, r)})
    return {"roots": [r.relative_to(folder).as_posix() for r in roots], "files": _hashed(folder, sources)}


def _lock_fixture(plan, revision, entry, folder):
    top = _inside(folder, entry.get("fixture"), f"revision {revision}'s fixture")
    if not top.is_dir():
        raise Refused("lock", f"revision {revision}'s fixture {entry.get('fixture')} is not a directory")
    shared = top.parent / "both"  # build_fixtures.py's convention: sources every fixture revision shares
    original = sorted(_java_files(folder, top) + (_java_files(folder, shared) if shared.is_dir() else []))
    if not original:
        raise Refused("lock", f"revision {revision}'s fixture {entry['fixture']} holds no Java sources")
    controls = {c["kind"]: c for c in _sidecar(folder).get("controls", []) if c["kind"] in ("driver", "oracle")}
    source = {
        "route": "fixture", "repository": entry.get("repository"), "revision": revision, "fixture": entry["fixture"],
        "provenance": "fixture sources in the example's folder, never an upstream commit",
        "original": {"roots": sorted({top.relative_to(folder).as_posix()}
                                     | ({shared.relative_to(folder).as_posix()} if shared.is_dir() else set())),
                     "files": _hashed(folder, original)},
        "adapter": _component(folder, entry.get("adapters") or [], "adapter") if entry.get("adapters") else None,
        "driver": dict(_component(folder, [controls["driver"]["path"]], "driver"), control=controls["driver"]["id"])
        if "driver" in controls else None,
        "oracle": {"control": controls["oracle"]["id"], **_hashed(folder, [_inside(folder, controls["oracle"]["path"], "oracle")])[0]}
        if "oracle" in controls else None,
        "jdks": list(entry.get("jdks") or []),
        "recipe": {"tool": "javac", "by": "examples/tools/targets/fixtures/build_fixtures.py's recipe", **_fixture_recipe()},
    }
    return f"fixture:{entry['fixture']}", source


ROUTES_TO_COME = {"published-artifact": "R2's published-artifact route", "upstream-build": "R2's pinned upstream build"}


def lock(plan, revision):
    """The source lock of one revision: a PreparedTarget at source-locked (nothing fetched or built, every selected
    path inside the folder and hashed), failed at stage `lock`, or Unsupported for a route not implemented yet."""
    route = None
    try:
        entry = _entry(plan, revision)
        route = entry.get("route")
        if route in ROUTES_TO_COME:
            return Unsupported("prepare", RUNTIME, f"{ROUTES_TO_COME[route]} is not implemented yet", stage="lock",
                               diagnostic=f"revision {revision}: route {route}")
        if route != "fixture":
            raise Refused("lock", f"revision {revision} has no known route ({route!r})")
        folder = Path(plan.folder).resolve()
        commit, source = _lock_fixture(plan, revision, entry, folder)
    except Refused as e:
        return _failed(plan, revision, None, {"route": route}, e, (), ())
    return PreparedTarget(example=plan.example, task=plan.task, revision=revision, commit=commit, stage="source-locked",
                          source=source)


def _failed(plan, revision, commit, source, refused, artifacts, logs, toolchain=None):
    return PreparedTarget(example=plan.example, task=plan.task, revision=revision, commit=commit or "", stage="failed",
                          source=source, artifacts=tuple(artifacts), toolchain=toolchain or {},
                          failedStage=refused.stage, diagnostic=refused.diagnostic, logs=tuple(logs))


# -- artifacts ready

def _workdir(workdir):
    """A fresh work directory: made if missing, emptied if it holds an earlier preparation's record, refused if it
    holds anything else (it isn't ours to delete)."""
    workdir = Path(workdir)
    if workdir.exists():
        if not workdir.is_dir():
            raise Refused("workdir", f"{workdir} is not a directory")
        entries = list(workdir.iterdir())
        if entries and not (workdir / RECORD).is_file():
            raise Refused("workdir", f"{workdir} holds files and no {RECORD}: not an earlier preparation's, left alone")
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    return workdir.resolve()


class _Build:
    """The compile and JAR steps of one preparation, logged under workdir/logs."""

    def __init__(self, workdir, home, recipe):
        self.workdir, self.home, self.recipe = workdir, Path(home), recipe
        self.logs, self.artifacts = [], []

    def run(self, step, argv):
        started = time.monotonic()
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=COMPILE_TIMEOUT)
            out, code = proc.stdout + proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as e:
            out, code = f"timed out after {COMPILE_TIMEOUT}s: {e}", None
        log = Path("logs") / f"{step}.log"
        (self.workdir / log).parent.mkdir(exist_ok=True)
        (self.workdir / log).write_text(f"$ {' '.join(argv)}\n{out}\nexit {code} after {time.monotonic() - started:.3f}s\n")
        self.logs.append(log.as_posix())
        if code != 0:
            tail = "\n".join(out.strip().splitlines()[-15:])
            raise Refused("build", f"{step} failed (exit {code}): {' '.join(argv)}\n{tail}")

    def compile(self, step, sources, classpath):
        classes = self.workdir / "classes" / step
        classes.mkdir(parents=True)
        argv = [str(self.home / "bin/javac"), "--release", self.recipe["release"], "-encoding", "UTF-8",
                "-implicit:none", "-d", str(classes)]
        if classpath:
            argv += ["-cp", ":".join(str(self.workdir / c) for c in classpath)]
        self.run(f"javac-{step}", argv + [str(s) for s in sorted(sources)])
        return classes

    def jar(self, step, classes, name, role, origin):
        entries = sorted(p.relative_to(classes).as_posix() for p in classes.rglob("*.class"))
        args = [a for e in entries for a in ("-C", str(classes), e)]  # -C applies to the one file after it
        self.run(f"jar-{step}", [str(self.home / "bin/jar"), "--create", "--file", str(self.workdir / name),
                                 f"--date={self.recipe['date']}", "--no-manifest", *args])
        self.artifacts.append(Artifact(name, sha256(self.workdir / name), role, origin=origin))
        return name


def _check_classpath(plan, workdir, classpath, original, adapter):
    """The loaded target's origin, after refusing shadowed classes, a missing target method and an adapter that
    doesn't call it."""
    shadowed = runtime_jar.duplicates(classpath, workdir)
    if shadowed:
        listed = "; ".join(f"{name.replace('/', '.')} in {', '.join(holders)}" for name, holders in shadowed[:10])
        raise Refused("classpath", f"{len(shadowed)} class(es) held by more than one classpath entry, so the class loaded "
                                   f"depends on order: {listed}")
    cls, method, descriptor = runtime_jar.parse_target(plan.target)
    name = runtime_jar.internal(cls)
    data = runtime_jar.read_class(workdir / original, name)
    if data is None:
        raise Refused("target", f"the original artifact {original} holds no class {cls}")
    declared = runtime_jar.methods(data)
    if not any(n == method and (descriptor is None or d == descriptor) for n, d in declared):
        raise Refused("target", f"{cls} in {original} declares no method {method}{descriptor or ''}")
    if adapter:
        calls = [(c, n, d) for c in runtime_jar.classes(workdir / adapter)
                 for (o, n, d) in runtime_jar.references(runtime_jar.read_class(workdir / adapter, c))
                 if o == name and n == method and (descriptor is None or d == descriptor)]
        if not calls:
            raise Refused("adapter", f"the adapter {adapter} never references {plan.target}: it does not call the "
                                     f"selected original method")
    return {"class": cls, "method": method, "descriptor": descriptor, "loadedFrom": original,
            "classSha256": hashlib.sha256(data).hexdigest()}


def _prepare_fixture(plan, revision, locked, workdir):
    source = dict(locked.source)
    folder = Path(plan.folder).resolve()
    home = runtime_jdk.build_home()
    if home is None:
        raise Refused("toolchain", "no JDK to build with: JAVA_HOME is unset and no javac is on PATH")
    build = _Build(workdir, home, source["recipe"])
    toolchain = {"jdk": runtime_jdk.identity(home),
                 "build": {"tool": "javac", "release": source["recipe"]["release"], "date": source["recipe"]["date"],
                           "flags": ["--release", source["recipe"]["release"], "-encoding", "UTF-8", "-implicit:none"],
                           "jar": f"jar --date={source['recipe']['date']} --no-manifest, entries sorted"}}
    try:
        files = lambda part: [folder / f["path"] for f in part["files"]]
        original = build.jar("original", build.compile("original", files(source["original"]), ()), f"{revision}.jar",
                             "original", f"built from {source['fixture']} by the fixture recipe")
        classpath = [original]
        adapter = None
        if source.get("adapter"):
            adapter = build.jar("adapter", build.compile("adapter", files(source["adapter"]), (original,)),
                                f"adapter-{revision}.jar", "adapter", "built from " + ", ".join(source["adapter"]["roots"]))
            classpath.insert(0, adapter)
        if source.get("driver"):
            driver = build.jar("driver", build.compile("driver", files(source["driver"]), tuple(classpath)),
                               "driver.jar", "driver", "built from " + ", ".join(source["driver"]["roots"]))
            classpath.insert(0, driver)
        if source.get("oracle"):
            copied = Path("controls") / Path(source["oracle"]["path"]).name
            (workdir / copied).parent.mkdir(exist_ok=True)
            shutil.copyfile(folder / source["oracle"]["path"], workdir / copied)
            if sha256(workdir / copied) != source["oracle"]["sha256"]:
                raise Refused("lock", f"the oracle {source['oracle']['path']} changed since it was locked")
            build.artifacts.append(Artifact(copied.as_posix(), source["oracle"]["sha256"], "oracle",
                                            origin=source["oracle"]["path"]))
        for part in ("original", "adapter", "driver"):  # the sources compiled are still the ones locked
            for f in (source.get(part) or {}).get("files", []):
                if sha256(folder / f["path"]) != f["sha256"]:
                    raise Refused("lock", f"{f['path']} changed between its lock and its build: stale bytes")
        source["target"] = _check_classpath(plan, workdir, classpath, original, adapter)
    except Refused as e:
        return _failed(plan, revision, locked.commit, source, e, build.artifacts, build.logs, toolchain)
    shutil.rmtree(workdir / "classes", ignore_errors=True)
    return PreparedTarget(example=plan.example, task=plan.task, revision=revision, commit=locked.commit,
                          stage="artifacts-ready", source=source, artifacts=tuple(build.artifacts),
                          classpath=tuple(classpath), toolchain=toolchain, logs=tuple(build.logs))


def prepare(plan, revision, workdir):
    """One revision (a name in target.json) of `plan` made callable under `workdir`: a PreparedTarget at
    artifacts-ready, or failed with its stage and diagnostic and whatever artifacts exist; or Unsupported for a route
    not implemented yet. The record is also written to workdir/prepared.json."""
    locked = lock(plan, revision)
    if isinstance(locked, Unsupported) or locked.stage == "failed":
        return locked
    try:
        workdir = _workdir(workdir)
    except Refused as e:
        return _failed(plan, revision, locked.commit, locked.source, e, (), ())
    prepared = _prepare_fixture(plan, revision, locked, workdir)
    (workdir / RECORD).write_text(json.dumps(prepared.as_dict(), indent=2, ensure_ascii=False) + "\n")
    return prepared


def run_controls(plan, prepared, workdir):
    """The task's concrete controls, each revision in its own JVM on its own classpath (`prepared`, by revision
    name): a tuple of raw ExecutionRecords, or Unsupported."""
    return Unsupported("run-controls", RUNTIME, "separate-JVM replay is Phase 0's stub until the runtime stream's R4 replaces it",
                       stage="controls")


def run_verifier(plan, prepared, workdir):
    """The verifier on the prepared artifacts, with the plan's engine, gaps and bounds: one raw ExecutionRecord, or
    Unsupported."""
    return Unsupported("run-verifier", RUNTIME, "the verifier on prepared artifacts is Phase 0's stub until the runtime stream's R3 replaces it",
                       stage="verifier")

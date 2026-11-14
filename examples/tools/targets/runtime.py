"""Preparation and separate-JVM execution: the runtime stream's side of the interfaces (interfaces.py), for
llm-dlc/loops/example-targets.md (R1-R4). Signatures are frozen. Acquisition follows the brief's downloads policy:
github.com and Maven Central only, every file's sha256 recorded and rechecked.

    lock(plan, revision)                   source-locked: immutable paths, revisions and recipe, hashed; offline, pure
    prepare(plan, revision, workdir)       artifacts-ready: built or fetched, every byte hashed and the classpath
                                           checked; or failed, with its stage, diagnostic and what exists
    run_controls(plan, prepared, workdir)  each revision's driver in its own JVM, per JDK: raw ExecutionRecords
    run_verifier(plan, prepared, workdir)  jvmcontract on the prepared original artifacts, with the plan's engine,
                                           gaps and bounds: one raw ExecutionRecord (R3)

The two milestones stay apart (R1): a source lock fetches and builds nothing and supplies no proof identity; only an
artifacts-ready preparation does. A preparation never decides a claim, and a partial one is returned as failed with
its stage, never as an empty success.

Routes: `fixture` (a control's fixture revisions, built locally with build_fixtures.py's recipe) and
`published-artifact` (the revision's JAR and its declared dependencies from Maven Central, each by its recorded sha256,
through runtime_maven.py's checked cache) are implemented; `upstream-build` (R2) returns Unsupported until it is. The
adapter and driver are compiled separately, with the fixture recipe's --release and JAR date, on either route.

On the classpath a preparation refuses: a class held by more than one entry (an adapter or driver shadowing the
target, or two dependencies with one class), a target method missing from the original artifact, and an adapter that
never references the target method (R3's "calls the selected upstream method"). The loaded target's origin, the
ordered classpath, the JDK (by full path, `release` file and `java -version`) and every artifact's sha256 are
recorded in the PreparedTarget and in `prepared.json` in the work directory.

A failed preparation's `source` also carries a `blocker` for the handoff: the stage, the command that failed (or the
one that runs the preparation), the diagnostic, the semantics it needs and the next action. An artifact entry naming
a constructed `mutant` (workflow's W1) is Unsupported until its preparation is implemented: never its base unpatched.

The verifier (R3) runs jvmcontract on the prepared original artifacts only, never the adapter or driver, and records
what its result is about: a scope label (original bytecode, original bytecode under models, a constructed mutation, a
constructed fixture), the loaded class and its origin, the models and assumptions, and a capability probe (the static
gap scan). Proofs run as pipeline jobs (runtime_calibrate.py on the fixture), never inline.
"""

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from targets import interfaces, runtime_jar, runtime_jdk, runtime_maven
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
    """A preparation stops: `stage` is where (lock, workdir, acquire, toolchain, build, target, classpath, adapter),
    and, for the handoff, the command that failed, the semantics needed and the next action, where known."""

    def __init__(self, stage, diagnostic, command=None, needs=None, next=None):
        super().__init__(diagnostic)
        self.stage, self.diagnostic, self.command, self.needs, self.next = stage, diagnostic, command, needs, next

    @classmethod
    def blocked(cls, b):
        return cls(b.stage, b.diagnostic, b.command, b.needs, b.next)


# What each stage of a blocked preparation needs, and what to do next, unless the refusal says more precisely.
NEEDS = {
    "lock": ("an immutable, hash-pinned source lock: fixed coordinates or a full commit, every selected path inside "
             "the example's folder, every published file's sha256", "correct the revision's entry in target.json, then "
             "plan and prepare again"),
    "workdir": ("a work directory that is empty or holds an earlier preparation", "give the preparation a fresh work "
                "directory; the files there are not the runtime's to delete"),
    "acquire": ("the recorded bytes from Maven Central or github.com", "check the network and the recorded sha256"),
    "toolchain": ("a JDK to compile the adapter and driver with", "install the JDK under ~/.sdkman/candidates/java or "
                  "set JAVA_HOME"),
    "build": ("sources that compile with the recipe", "fix the adapter or driver source named in the diagnostic"),
    "classpath": ("each class on the classpath held by exactly one entry, so the class loaded doesn't depend on order",
                  "remove the duplicate: rename the adapter's class, or drop the dependency that repeats it"),
    "target": ("the selected method, by name and descriptor, in the original artifact", "check the task's target "
               "against the artifact's classes (javap -cp ARTIFACT CLASS)"),
    "adapter": ("an adapter that invokes the selected original method", "make the adapter call the target method"),
}


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


def _main_class(folder, relative):
    """The class a driver's source file declares, by its path under its source root: fixture.driver.GateDriver."""
    path = _inside(folder, relative, "driver")
    return ".".join(path.relative_to(_source_root(folder, path)).with_suffix("").parts)


def _controls_source(folder, entry):
    """The parts a preparation compiles or copies besides the original, from the example's folder: the adapter (the
    entry's `adapters`), the driver and oracle (the sidecar's controls), and the JDKs the controls run on."""
    controls = {c["kind"]: c for c in _sidecar(folder).get("controls", []) if c["kind"] in ("driver", "oracle")}
    return {
        "adapter": _component(folder, entry.get("adapters") or [], "adapter") if entry.get("adapters") else None,
        "driver": dict(_component(folder, [controls["driver"]["path"]], "driver"), control=controls["driver"]["id"],
                       main=_main_class(folder, controls["driver"]["path"]))
        if "driver" in controls else None,
        "oracle": {"control": controls["oracle"]["id"], **_hashed(folder, [_inside(folder, controls["oracle"]["path"], "oracle")])[0]}
        if "oracle" in controls else None,
        "jdks": list(entry.get("jdks") or []),
    }


def _lock_fixture(plan, revision, entry, folder):
    top = _inside(folder, entry.get("fixture"), f"revision {revision}'s fixture")
    if not top.is_dir():
        raise Refused("lock", f"revision {revision}'s fixture {entry.get('fixture')} is not a directory")
    shared = top.parent / "both"  # build_fixtures.py's convention: sources every fixture revision shares
    original = sorted(_java_files(folder, top) + (_java_files(folder, shared) if shared.is_dir() else []))
    if not original:
        raise Refused("lock", f"revision {revision}'s fixture {entry['fixture']} holds no Java sources")
    source = {
        "route": "fixture", "repository": entry.get("repository"), "revision": revision, "fixture": entry["fixture"],
        "provenance": "fixture sources in the example's folder, never an upstream commit",
        "original": {"roots": sorted({top.relative_to(folder).as_posix()}
                                     | ({shared.relative_to(folder).as_posix()} if shared.is_dir() else set())),
                     "files": _hashed(folder, original)},
        **_controls_source(folder, entry),
        "recipe": {"tool": "javac", "by": "examples/tools/targets/fixtures/build_fixtures.py's recipe", **_fixture_recipe()},
    }
    return f"fixture:{entry['fixture']}", source


FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _lock_published(plan, revision, entry, folder):
    """A published revision's lock, offline: its JAR and each declared dependency, in classpath order, by fixed
    coordinates, an allowed URL and a recorded sha256; the commit and release it is linked to, as recorded. The JARs
    are workflow's W1 `published` list (the original first, then the dependencies, as the sidecar lists them), or the
    original's keys on the entry itself with `dependencies` beside them."""
    commit = entry.get("commit")
    if not isinstance(commit, str) or not FULL_SHA.match(commit):
        raise Refused("lock", f"revision {revision} names no full commit ({commit!r}): a published artifact is linked "
                              f"to the source revision it was released from")
    original, dependencies = _published_items(revision, entry)
    try:
        items = [runtime_maven.check_item(original, "original")]
        items += [runtime_maven.check_item(d, "dependency") for d in dependencies]
    except runtime_maven.Blocked as b:
        raise Refused.blocked(b) from None
    seen = {}
    for item in items:
        if item["coordinates"] in seen:
            raise Refused("lock", f"{item['coordinates']} is listed twice on revision {revision}'s classpath")
        seen[item["coordinates"]] = item
    source = {
        "route": "published-artifact", "repository": entry.get("repository"), "revision": revision,
        "provenance": "published JARs, each by its recorded sha256: the bytes are the identity, the URL only where they "
                      "are fetched from",
        "linkage": {"commit": commit, **{k: entry[k] for k in ("tag", "release") if entry.get(k)},
                    "status": "recorded, not checked against the published bytes: a release label supports no source "
                              "rebuild or introducing-commit experiment"},
        "published": items,
        **_controls_source(folder, entry),
        "recipe": {"tool": "javac", "by": "the fixture recipe's --release and JAR date, for the adapter and driver only; "
                                          "the published JARs are used as fetched", **_fixture_recipe()},
    }
    return commit, source


JAR_KEYS = ("coordinates", "url", "sha256")


def _published_items(revision, entry):
    """The original JAR's item and the dependencies' items, in classpath order, from either shape; never a mix of
    the two, and never a copied-up key that disagrees with the list it was copied from."""
    if "published" not in entry:
        dependencies = entry.get("dependencies") or []
        if not isinstance(dependencies, list):
            raise Refused("lock", f"revision {revision}'s dependencies are not a list")
        return {k: entry.get(k) for k in JAR_KEYS}, dependencies
    published = entry["published"]
    if not isinstance(published, list) or not published or not all(isinstance(i, dict) for i in published):
        raise Refused("lock", f"revision {revision}'s published JARs are not a non-empty list of items")
    if entry.get("dependencies"):
        raise Refused("lock", f"revision {revision} names both `published` and `dependencies`: one ordered list says "
                              f"what is on the classpath, and in which order")
    for k in JAR_KEYS:
        if k in entry and entry[k] != published[0].get(k):
            raise Refused("lock", f"revision {revision}'s {k} {entry[k]!r} is not its first published JAR's "
                                  f"({published[0].get(k)!r})")
    return published[0], published[1:]


LOCKS = {"fixture": _lock_fixture, "published-artifact": _lock_published}
ROUTES_TO_COME = {"upstream-build": "R2's pinned upstream build"}


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
        if route not in LOCKS:
            raise Refused("lock", f"revision {revision} has no known route ({route!r})")
        if "mutant" in entry:  # never the base prepared unpatched
            return Unsupported("prepare", RUNTIME, "a constructed mutant's preparation (its base patched, then built) "
                               "is not implemented yet", stage="lock", diagnostic=f"revision {revision}: {entry['mutant']}")
        folder = Path(plan.folder).resolve()
        commit, source = LOCKS[route](plan, revision, entry, folder)
    except Refused as e:
        return _failed(plan, revision, None, {"route": route}, e, (), ())
    return PreparedTarget(example=plan.example, task=plan.task, revision=revision, commit=commit, stage="source-locked",
                          source=source)


def _failed(plan, revision, commit, source, refused, artifacts, logs, toolchain=None):
    needs, next_ = NEEDS.get(refused.stage, (None, None))
    blocker = {"stage": refused.stage,
               "command": refused.command or f"python3 examples/tools/build.py {plan.example} --task {plan.task}",
               "diagnostic": refused.diagnostic, "needs": refused.needs or needs, "next": refused.next or next_}
    return PreparedTarget(example=plan.example, task=plan.task, revision=revision, commit=commit or "", stage="failed",
                          source={**(source or {}), "blocker": blocker}, artifacts=tuple(artifacts), toolchain=toolchain or {},
                          failedStage=refused.stage, diagnostic=refused.diagnostic, logs=tuple(logs))


# -- artifacts ready

def _workdir(workdir, marker=RECORD):
    """A fresh work directory: made if missing, emptied if it holds an earlier run's record (`marker`), refused if it
    holds anything else (it isn't ours to delete)."""
    workdir = Path(workdir)
    if workdir.exists():
        if not workdir.is_dir():
            raise Refused("workdir", f"{workdir} is not a directory")
        entries = list(workdir.iterdir())
        if entries and not (workdir / marker).is_file():
            raise Refused("workdir", f"{workdir} holds files and no {marker}: not an earlier run's, left alone")
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
            raise Refused("build", f"{step} failed (exit {code}): {' '.join(argv)}\n{tail}", command=" ".join(argv))

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
    """The loaded target's origin, after refusing shadowed classes and a missing target method; and the original
    methods the adapter calls. A replay task's adapter must call the target (its controls are the task's evidence); a
    proof task's verifier never goes through the adapter, so there it is recorded (`adapterCallsTarget`), and
    run_controls doesn't run controls whose adapter doesn't call the task's target."""
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
    found = {"class": cls, "method": method, "descriptor": descriptor, "loadedFrom": original,
             "classSha256": hashlib.sha256(data).hexdigest()}
    if adapter:
        originals = set(runtime_jar.classes(workdir / original))
        refs = {(o, n, d) for c in runtime_jar.classes(workdir / adapter)
                for (o, n, d) in runtime_jar.references(runtime_jar.read_class(workdir / adapter, c))
                if o in originals}
        calls_target = any(o == name and n == method and (descriptor is None or d == descriptor) for o, n, d in refs)
        if not calls_target and plan.kind == "replay":
            raise Refused("adapter", f"the adapter {adapter} never references {plan.target}: it does not call the "
                                     f"selected original method")
        found.update(adapterCalls=sorted(f"{o.replace('/', '.')}#{n}{d}" for o, n, d in refs),
                     adapterCallsTarget=calls_target)
    return found


def _builder(source, workdir):
    home = runtime_jdk.build_home()
    if home is None:
        raise Refused("toolchain", "no JDK to build with: JAVA_HOME is unset and no javac is on PATH")
    recipe = source["recipe"]
    toolchain = {"jdk": runtime_jdk.identity(home),
                 "build": {"tool": "javac", "release": recipe["release"], "date": recipe["date"],
                           "flags": ["--release", recipe["release"], "-encoding", "UTF-8", "-implicit:none"],
                           "jar": f"jar --date={recipe['date']} --no-manifest, entries sorted"}}
    return _Build(workdir, home, recipe), toolchain


def _files(folder, part):
    return [folder / f["path"] for f in part["files"]]


def _add_controls(build, source, folder, workdir, revision, below):
    """The adapter and driver compiled against the classpath `below` them (the original, then its dependencies), and
    the oracle copied, each hashed; the sources rechecked against the lock. (classpath, adapter JAR or None)."""
    classpath = list(below)
    adapter = None
    if source.get("adapter"):
        adapter = build.jar("adapter", build.compile("adapter", _files(folder, source["adapter"]), tuple(classpath)),
                            f"adapter-{revision}.jar", "adapter", "built from " + ", ".join(source["adapter"]["roots"]))
        classpath.insert(0, adapter)
    if source.get("driver"):
        driver = build.jar("driver", build.compile("driver", _files(folder, source["driver"]), tuple(classpath)),
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
    return classpath, adapter


def _prepare_fixture(plan, revision, locked, workdir):
    source = dict(locked.source)
    folder = Path(plan.folder).resolve()
    build, toolchain = _builder(source, workdir)
    try:
        original = build.jar("original", build.compile("original", _files(folder, source["original"]), ()),
                             f"{revision}.jar", "original", f"built from {source['fixture']} by the fixture recipe")
        classpath, adapter = _add_controls(build, source, folder, workdir, revision, [original])
        source["target"] = _check_classpath(plan, workdir, classpath, original, adapter)
    except Refused as e:
        return _failed(plan, revision, locked.commit, source, e, build.artifacts, build.logs, toolchain)
    return _ready(plan, revision, locked, workdir, source, build, classpath, toolchain)


def _ready(plan, revision, locked, workdir, source, build, classpath, toolchain):
    shutil.rmtree(workdir / "classes", ignore_errors=True)
    return PreparedTarget(example=plan.example, task=plan.task, revision=revision, commit=locked.commit,
                          stage="artifacts-ready", source=source, artifacts=tuple(build.artifacts),
                          classpath=tuple(classpath), toolchain=toolchain, logs=tuple(build.logs))


def _jar_path(coords):
    group, artifact, version = runtime_maven.coordinates(coords)
    return f"lib/{group}/{artifact}-{version}.jar"


def _prepare_published(plan, revision, locked, workdir):
    """Each published JAR acquired by its recorded sha256 (from the cache, rechecked, or fetched and checked), in the
    lock's order (the original, then its dependencies); then the adapter and driver compiled against them. The cache
    and fetch log is in logs/acquire.log: a cache hit is reuse, so it is not part of the source or any identity."""
    source = dict(locked.source)
    folder = Path(plan.folder).resolve()
    build, toolchain = _builder(source, workdir)
    acquired, log = [], []
    cache = runtime_maven.Cache()
    try:
        for item in source["published"]:
            path = _jar_path(item["coordinates"])
            (workdir / path).parent.mkdir(parents=True, exist_ok=True)
            try:
                log += runtime_maven.acquire(item, workdir / path, cache, network=plan.network)
            except runtime_maven.Blocked as b:
                raise Refused.blocked(b) from None
            finally:
                (workdir / "logs").mkdir(exist_ok=True)
                (workdir / "logs/acquire.log").write_text("\n".join(log) + "\n")
                if "logs/acquire.log" not in build.logs:
                    build.logs.append("logs/acquire.log")
            build.artifacts.append(Artifact(path, item["sha256"], item["role"], coordinates=item["coordinates"],
                                            origin=item["url"]))
            acquired.append(path)
        classpath, adapter = _add_controls(build, source, folder, workdir, revision, acquired)
        source["target"] = _check_classpath(plan, workdir, classpath, acquired[0], adapter)
    except Refused as e:
        return _failed(plan, revision, locked.commit, source, e, build.artifacts, build.logs, toolchain)
    return _ready(plan, revision, locked, workdir, source, build, classpath, toolchain)


PREPARES = {"fixture": _prepare_fixture, "published-artifact": _prepare_published}


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
    try:
        prepared = PREPARES[locked.source["route"]](plan, revision, locked, workdir)
    except Refused as e:  # before any build step: no toolchain
        prepared = _failed(plan, revision, locked.commit, locked.source, e, (), ())
    (workdir / RECORD).write_text(json.dumps(prepared.as_dict(), indent=2, ensure_ascii=False) + "\n")
    return prepared


# -- concrete controls, each revision in its own JVM (R4)

CONTROLS = "controls.json"  # the record a controls work directory holds
CONTROL_TIMEOUT = 120  # seconds one control's JVM may run before it is killed as timed out
# What each control's JVM is given and nothing else: no inherited JAVA_TOOL_OPTIONS, CLASSPATH or locale, so two runs
# of one revision differ only in what their identities say. Locale, charset and time zone matter to a driver's
# output (String.format, toLowerCase, dates), so they are fixed and recorded.
CONTROL_ENV = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC"}
CONTROL_FLAGS = ("-Xmx512m", "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8",
                 "-Duser.language=en", "-Duser.country=US", "-Duser.timezone=UTC")


def _preparation_dir(prepared, workdir):
    """Where `prepared`'s files are: route.py's layout, <attempt>/prepare/<revision> beside <attempt>/controls (the
    PreparedTarget doesn't carry its directory; an interface request under the brief's Progress). The directory
    counts only if its prepared.json is this PreparedTarget."""
    where = Path(workdir).resolve().parent / "prepare" / prepared.revision
    try:
        recorded = json.loads((where / RECORD).read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise Refused("controls", f"no readable {RECORD} for revision {prepared.revision} at {where}: {e}") from None
    if recorded != json.loads(json.dumps(prepared.as_dict())):
        raise Refused("controls", f"{where / RECORD} is not the preparation given for revision {prepared.revision}")
    return where


def _oracle_probes(where, prepared):
    """The inputs every control is run on: the case's oracle's PROBES, from the prepared copy, its hash rechecked."""
    oracle = next((a for a in prepared.artifacts if a.role == "oracle"), None)
    if oracle is None:
        raise Refused("controls", f"revision {prepared.revision}'s preparation has no oracle, so no inputs to run on")
    spec = importlib.util.spec_from_file_location(f"targets_oracle_{oracle.sha256[:16]}", where / oracle.path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    probes = getattr(module, "PROBES", None)
    if not probes:
        raise Refused("controls", f"the oracle {oracle.path} names no PROBES")
    return [p if isinstance(p, str) else json.dumps(p) for p in probes], oracle


def _checked(where, prepared):
    """The classpath's artifacts, each rechecked against the preparation's sha256 (stale or changed bytes refuse)."""
    if prepared.stage != "artifacts-ready":
        raise Refused("controls", f"revision {prepared.revision} is {prepared.stage}, not artifacts-ready"
                                  + (f" ({prepared.failedStage}: {prepared.diagnostic})" if prepared.failedStage else ""))
    by_path = {a.path: a for a in prepared.artifacts}
    for entry in prepared.classpath:
        a = by_path.get(entry)
        if a is None:
            raise Refused("controls", f"classpath entry {entry} is no artifact of the preparation")
        found = sha256(where / entry) if (where / entry).is_file() else "missing"
        if found != a.sha256:
            raise Refused("controls", f"{entry} is {found}, not the prepared {a.sha256}: stale or changed bytes")
    return [by_path[e] for e in prepared.classpath]


def _observations(stdout, inputs):
    """The driver's structured output, one JSON object per input in order, or None (with why) when it can't be
    read: a line that isn't a JSON object, or inputs missing, extra or out of order. Raw: nothing is judged here."""
    lines = [line for line in stdout.splitlines() if line.strip()]
    try:
        observed = [json.loads(line) for line in lines]
    except json.JSONDecodeError as e:
        return None, f"a line of the driver's output is not JSON: {e}"
    if not all(isinstance(o, dict) for o in observed):
        return None, "a line of the driver's output is not a JSON object"
    seen = [o.get("input") for o in observed]
    if [x if isinstance(x, str) else json.dumps(x) for x in seen] != inputs:
        return None, f"the driver observed inputs {seen}, not the {len(inputs)} it was given: an incomplete replay"
    return tuple(observed), None


def _run_one(argv, cwd, out, err, timeout, env=None):
    """(status, exitCode, seconds) of one process, its streams written to `out` and `err`, in the fixed environment
    `env` (the controls' by default) and nothing inherited."""
    started = time.monotonic()
    with open(out, "w") as o, open(err, "w") as e:
        try:
            proc = subprocess.run(argv, cwd=cwd, env=dict(env or CONTROL_ENV), stdin=subprocess.DEVNULL, stdout=o, stderr=e,
                                  timeout=timeout)
        except subprocess.TimeoutExpired:
            return "timed-out", None, round(time.monotonic() - started, 3)
        except OSError as x:
            e.write(f"runtime: not started: {x}\n")
            return "not-started", None, round(time.monotonic() - started, 3)
    return ("exited" if proc.returncode >= 0 else "killed"), proc.returncode, round(time.monotonic() - started, 3)


def _control(plan, revision, prepared, feature, workdir, attempt):
    """One revision's driver on one JDK, in its own JVM: an ExecutionRecord, and its log entry."""
    name = f"control-{revision}-jdk{feature}"
    out, err = workdir / f"{name}.stdout", workdir / f"{name}.stderr"
    rel = lambda p: p.relative_to(attempt).as_posix()
    identities, argv, log = {"feature": str(feature)}, (), {}
    try:
        if prepared is None:
            raise Refused("controls", f"revision {revision} was not prepared: a one-sided replay")
        where = _preparation_dir(prepared, workdir)
        artifacts = _checked(where, prepared)
        driver = (prepared.source.get("driver") or {})
        if not driver.get("main"):
            raise Refused("controls", f"revision {revision}'s preparation has no driver to run")
        if (prepared.source.get("target") or {}).get("adapterCallsTarget") is False:
            raise Refused("controls", f"revision {revision}'s adapter doesn't call the task's target {plan.target}: "
                                      "its controls are not this task's evidence")
        inputs, oracle = _oracle_probes(where, prepared)
        home = runtime_jdk.home(feature)
        if home is None:
            raise Refused("controls", f"no JDK {feature} under {runtime_jdk.CANDIDATES}")
        jdk = runtime_jdk.identity(home)
        needed = max((runtime_jar.feature_needed(where / a.path) or 0) for a in artifacts)
        identities = {"jdk": jdk["version"], "jdkFeature": jdk["feature"], "jdkHome": jdk["home"],
                      "jdkRelease": jdk["release"], "commit": prepared.commit,
                      "classpath": [{"path": a.path, "sha256": a.sha256, "role": a.role} for a in artifacts],
                      "driver": {"control": driver.get("control"), "main": driver["main"]},
                      "inputs": {"from": "PROBES", "oracle": oracle.path, "oracleSha256": oracle.sha256},
                      "environment": dict(CONTROL_ENV), "flags": list(CONTROL_FLAGS),
                      "replay": "model" if any(a.role == "stub" for a in artifacts) else "original-jvm"}
        argv = (str(Path(home) / "bin/java"), *CONTROL_FLAGS, "-cp", ":".join(prepared.classpath), driver["main"], *inputs)
        if needed > int(jdk["feature"]):
            raise Refused("controls", f"the prepared classes need Java {needed}; JDK {jdk['feature']} can't load them")
    except Refused as e:
        out.write_text("")
        err.write_text(f"runtime: not started: {e.diagnostic}\n")
        log = {"problem": e.diagnostic}
        return interfaces.ExecutionRecord(
            kind="jvm-control", revision=revision, argv=argv, status="not-started", exitCode=None, seconds=0.0,
            stdout=rel(out), stderr=rel(err), identities=identities, observations=None,
            control=(prepared.source.get("driver") or {}).get("control") if prepared else None), log
    status, code, seconds = _run_one(argv, where, out, err, CONTROL_TIMEOUT)
    observations, problem = (None, f"the JVM {status}" + (f" (signal {-code})" if status == "killed" else "")) \
        if status != "exited" else _observations(out.read_text(errors="replace"), inputs)
    log = {"cwd": str(where), "problem": problem} if problem else {"cwd": str(where)}
    return interfaces.ExecutionRecord(
        kind="jvm-control", revision=revision, argv=argv, status=status, exitCode=code, seconds=seconds,
        stdout=rel(out), stderr=rel(err), identities=identities, observations=observations,
        control=driver.get("control")), log


def _jdks(plan, revision, prepared):
    entry = next((a for a in plan.artifacts if a.get("revision") == revision), {})
    if entry.get("jdks"):
        return [str(j) for j in entry["jdks"]]
    built = ((prepared.toolchain if prepared else {}) or {}).get("jdk", {}).get("feature")
    return [str(built)] if built else []


def run_controls(plan, prepared, workdir):
    """The task's concrete controls: each revision's driver in its own JVM, on its own prepared classpath, on each JDK
    its artifact entry names (else the one it was built with), run on the oracle's PROBES. A tuple of raw
    ExecutionRecords, one per revision and JDK, in the plan's order: a revision that wasn't prepared or is not
    artifacts-ready, bytes that changed since preparation, a missing JDK or one too old for the classes gives a
    not-started record, never a skipped one; a kill, a timeout, or output that can't be read gives a record with no
    observations. Nothing here applies the oracle or decides a claim. Unsupported only when the work directory is not
    ours. The records are also written to workdir/controls.json, with why each that has no observations has none."""
    try:
        workdir = _workdir(workdir, CONTROLS)
    except Refused as e:
        return Unsupported("run-controls", RUNTIME, "the controls' work directory can't be used", stage=e.stage,
                           diagnostic=e.diagnostic)
    attempt = workdir.parent
    records, logs = [], []
    for revision in plan.revisions:
        p = prepared.get(revision)
        for feature in _jdks(plan, revision, p) or ["none"]:
            record, log = _control(plan, revision, p, feature, workdir, attempt)
            records.append(record)
            logs.append({**record.as_dict(), "log": log})
    (workdir / CONTROLS).write_text(json.dumps({"task": plan.task, "records": logs}, indent=2, ensure_ascii=False) + "\n")
    return tuple(records)


# -- the verifier on prepared artifacts (R3)

VERIFIER = "verifier.json"  # the record a verifier work directory holds
VERIFIER_TIMEOUT = 600  # seconds, jvmcontract's own --timeout (its default): a timeout change is another attempt
VERIFIER_GRACE = 120  # seconds more before the process is killed as timed out, past its own deadline
VERIFIER_KINDS = {"prove": "prove", "equivalence": "equivalence"}  # task kind: jvmcontract command
ENGINES, GAP_MODES = ("native", "jbmc", "auto"), ("strict", "assume", "advised")
# The verifier's environment is fixed and recorded as the controls' is, with its JDK on PATH and in JAVA_HOME (its
# replay of a witness and the JDK it reads models for); only the runner's own memory settings pass through.
VERIFIER_PASS = ("JVMCONTRACT_JBMC_MEMORY_MB", "JVMCONTRACT_JAVA_OPTS")
DESCRIPTOR_TYPES = {"Z": "boolean", "B": "byte", "C": "char", "S": "short", "I": "int", "J": "long", "F": "float",
                    "D": "double"}
# What a verifier run's result is about (the brief's R3 and scope labels), from what its preparation holds.
SCOPES = {
    "original-bytecode": "the selected method's original bytecode, as published or built from the pinned source, "
                         "called directly; the adapter and driver are not on the verifier's classpath",
    "original-bytecode-under-models": "the original bytecode, with stated models of what it calls (a model boundary)",
    "constructed-mutation": "a constructed mutation of a base revision: sensitivity evidence, never an upstream result",
    "constructed-fixture": "a fixture revision: constructed control code built locally, never an upstream result",
}
# Refusals that are the claim's or the task's, not the attempt's: Unsupported, before any process (a not-started
# record is an attempt that couldn't start; these can't be attempted as stated).
CLAIM_STAGES = ("claim", "classpath")


def jvmcontract():
    """The jvmcontract executable: $JVMCONTRACT (a pipeline job's own build), else lib/target/release/jvmcontract."""
    import os
    found = os.environ.get("JVMCONTRACT") or str(HERE.parents[2] / "lib/target/release/jvmcontract")
    return found if Path(found).is_file() and os.access(found, os.X_OK) else None


def java_target(target):
    """`pkg.Class#method(int, java.lang.String)`, jvmcontract's spelling of the plan's `pkg.Class#method(I...)Z`."""
    cls, method, descriptor = runtime_jar.parse_target(target)
    if descriptor is None:
        return f"{cls}#{method}"
    inside, params, i = descriptor[1:descriptor.index(")")], [], 0
    while i < len(inside):
        dims = 0
        while inside[i] == "[":
            dims, i = dims + 1, i + 1
        if inside[i] == "L":
            end = inside.index(";", i)
            name, i = inside[i + 1:end].replace("/", "."), end + 1
        elif inside[i] in DESCRIPTOR_TYPES:
            name, i = DESCRIPTOR_TYPES[inside[i]], i + 1
        else:
            raise ValueError(f"not a method descriptor: {descriptor!r}")
        params.append(name + "[]" * dims)
    return f"{cls}#{method}({', '.join(params)})"


def _claim_file(plan, part):
    """A claim's referenced file ({path, sha256}), rechecked: a changed file is a different claim."""
    ref = plan.claim.get(part)
    if not ref:
        return None
    folder = Path(plan.folder).resolve()
    path = _inside(folder, ref.get("path"), f"the claim's {part}")
    if sha256(path) != ref.get("sha256"):
        raise Refused("claim", f"the claim's {part} {ref.get('path')} is {sha256(path)}, not the frozen "
                               f"{ref.get('sha256')}: a changed file is a different claim")
    return path


def _verifier_jdk(plan, prepared):
    """The JDK the verifier runs with: 25 where every revision's artifacts run on it, else the newest they all name."""
    named = [set(_jdks(plan, r, prepared.get(r))) for r in plan.revisions]
    common = set.intersection(*named) if named and all(named) else set()
    feature = "25" if "25" in common else (max(common, key=int) if common else None)
    if feature is None:
        raise Refused("verifier", "the revisions name no JDK in common to run the verifier with")
    home = runtime_jdk.home(feature)
    if home is None:
        raise Refused("verifier", f"no JDK {feature} under {runtime_jdk.CANDIDATES}")
    return runtime_jdk.identity(home)


def _scope(plan, sides):
    """The verifier run's scope label and its boundary, from each revision's preparation."""
    entries = {a.get("revision"): a for a in plan.artifacts}
    models = [m.get("path") for m in plan.claim.get("models") or []]
    stubs = [f"{r}:{a.path}" for r, (_, p, _) in sides.items() for a in p.artifacts if a.role == "stub"]
    if any("mutant" in entries.get(r, {}) for r in sides):
        label = "constructed-mutation"
    elif any(entries.get(r, {}).get("route") == "fixture" for r in sides):
        label = "constructed-fixture"
    elif models or stubs:
        label = "original-bytecode-under-models"
    else:
        label = "original-bytecode"
    return {"label": label, "meaning": SCOPES[label], "method": plan.target,
            "revisions": {r: {"commit": p.commit, "loadedFrom": p.source.get("target", {}).get("loadedFrom"),
                              "classSha256": p.source.get("target", {}).get("classSha256"),
                              "origin": next((a.origin for a in p.artifacts if a.role == "original"), None)}
                          for r, (_, p, _) in sides.items()},
            "adapter": "not on the verifier's classpath: the verifier calls the selected original method itself; the "
                       "adapter serves the concrete controls",
            "models": models + stubs, "assumptions": list(plan.claim.get("assumptions") or [])}


def _verifier_argv(plan, exe, sides, work):
    """jvmcontract's argv for the task, with paths relative to the attempt directory (the verifier's cwd)."""
    claim, bounds = plan.claim, dict(plan.claim.get("bounds") or {})
    command = VERIFIER_KINDS[plan.kind]
    unknown = sorted(set(bounds) - {"unwind", "maxArrayLength"})
    if unknown:
        raise Refused("claim", f"the claim's bounds {', '.join(unknown)} have no jvmcontract option here")
    if claim.get("models"):
        raise Refused("claim", "the claim states models, and no route passes models to the verifier yet",
                      needs="a way to give jvmcontract the claim's environment models",
                      next="run the task without models, as a narrower linked claim, or add the models route")
    deps = {r: [a for a in arts if a.role == "dependency"] for r, (_, _, arts) in sides.items()}
    original = {r: next(a for a in arts if a.path == p.source["target"]["loadedFrom"])
                for r, (_, p, arts) in sides.items()}
    rel = lambda r, a: f"prepare/{r}/{a.path}"
    target = java_target(plan.target)
    if command == "prove":
        [r] = sides
        argv = [exe, "prove", target, "--classes", rel(r, original[r])]
        argv += [x for a in deps[r] for x in ("--classpath", rel(r, a))]
        for key, flag in (("assume", "--assume"), ("assert", "--assert")):
            if claim.get(key):
                argv += [flag, claim[key]]
        argv += [x for t in claim.get("throws") or [] for x in ("--throws", t)]
    else:
        before, after = plan.revisions
        if [a.sha256 for a in deps[before]] != [a.sha256 for a in deps[after]]:
            raise Refused("classpath", "before and after have different dependency closures, and jvmcontract's "
                                      "equivalence takes one classpath for both",
                          needs="one dependency closure both revisions use, by the same bytes",
                          next="state the pair's shared dependencies, or check each revision as a property task")
        argv = [exe, "equivalence", "--before", rel(before, original[before]), "--after", rel(after, original[after]),
                "--target", target]
        argv += [x for a in deps[after] for x in ("--classpath", rel(after, a))]
        if claim.get("allowedChange"):
            argv += ["--unchanged-unless", claim["allowedChange"]]
    argv += [x for n in claim.get("nullable") or [] for x in ("--nullable", n)]
    argv += [x for pair in claim.get("mayAlias") or [] for x in ("--may-alias", pair)]
    for part, flag in (("plan", "--plan"), ("contracts", "--contracts")):
        path = _claim_file(plan, part)
        if path is not None:
            argv += [flag, str(path)]
    argv += ["--engine", plan.engine, "--gaps", plan.gaps]
    if "unwind" in bounds:
        argv += ["--unwind", str(bounds["unwind"])]
    if "maxArrayLength" in bounds:
        argv += ["--max-array-length", str(bounds["maxArrayLength"])]
    return argv + ["--timeout", str(VERIFIER_TIMEOUT), "--work", f"{work}/work", "--report", f"{work}/report", "--json"]


def _verifier_env(jdk):
    import os
    env = {**CONTROL_ENV, "JAVA_HOME": jdk["home"], "PATH": f"{jdk['home']}/bin:/usr/local/bin:/usr/bin:/bin"}
    env.update({k: os.environ[k] for k in VERIFIER_PASS if k in os.environ})
    return env


def _outcomes(stdout, command):
    """The verifier's --json outcome as observations: the list `prove` prints, or `equivalence`'s one outcome; None
    (with why) when the output is not one. Raw: nothing is judged here."""
    try:
        value = json.loads(stdout)
    except json.JSONDecodeError as e:
        return None, f"the verifier's standard output is not JSON: {e}"
    outcomes = value if command == "prove" else [value]
    if not isinstance(outcomes, list) or not outcomes or not all(
            isinstance(o, dict) and isinstance(o.get("output"), str) for o in outcomes):
        return None, f"the verifier's standard output is not {command}'s --json outcome"
    return tuple(outcomes), None


def _probe(exe, sides, target, env, workdir, attempt):
    """The capability probe beside the proof: jvmcontract's static gap scan of the target in each revision (it proves
    nothing; a strict proof that reaches a gap is refused by name). Its argv, exit and the gaps it lists."""
    probes = {}
    for r, (_, p, arts) in sides.items():
        original = next(a for a in arts if a.path == p.source["target"]["loadedFrom"])
        argv = [exe, "gaps", "--target", target, "--classes", f"prepare/{r}/{original.path}"]
        argv += [x for a in arts if a.role == "dependency" for x in ("--classpath", f"prepare/{r}/{a.path}")]
        argv.append("--json")
        out, err = workdir / f"probe-{r}.stdout", workdir / f"probe-{r}.stderr"
        status, code, seconds = _run_one(argv, attempt, out, err, CONTROL_TIMEOUT, env)
        try:
            gaps = [{k: g.get(k) for k in ("id", "kind", "call", "sites")}
                    for g in json.loads(out.read_text()).get("gaps", [])] if status == "exited" and code == 0 else None
        except (json.JSONDecodeError, AttributeError):
            gaps = None
        probes[r] = {"argv": argv, "status": status, "exitCode": code, "seconds": seconds,
                     "stdout": out.relative_to(attempt).as_posix(), "stderr": err.relative_to(attempt).as_posix(),
                     "gaps": gaps}
    return probes


def run_verifier(plan, prepared, workdir):
    """The verifier on the prepared artifacts, with the plan's engine, gaps and bounds: one raw ExecutionRecord
    (kind `verifier`; revision None for a pair), or Unsupported.

    A prove task runs `jvmcontract prove` on its revision's original artifact (`--classes`), its dependencies on the
    classpath in order, with the claim's assume, assert, throws, nullable and may-alias; an equivalence task runs
    `jvmcontract equivalence` between the pair's original artifacts, `--unchanged-unless` the task's allowed change.
    Both get the plan's `--engine` and `--gaps` (never a default), the claim's bounds, its construction plan and gap
    contracts (each rechecked against the claim's sha256), `--json`, and a work and report directory here. The
    adapter and driver are never on its classpath: they serve the controls, and the verifier calls the selected
    original method itself. Its scope label and boundary (`identities.scope`), the capability probe (`jvmcontract
    gaps` on each revision: static, it proves nothing), the jvmcontract digest, the JDK and the environment are
    recorded.

    As for the controls, a revision with no preparation (one-sided), one not artifacts-ready, bytes changed since
    preparation, or no JDK gives a not-started record; a kill or a timeout gives no observations; output that isn't
    the --json outcome gives none either. The exit code is raw: ingestion decides what the outcome means. Unsupported
    when the task kind, engine or gap mode isn't one this runs, the claim needs what no route gives (models,
    bounds with no option) or names a file that changed since it was frozen, an equivalence pair's dependency closures
    differ (jvmcontract takes one classpath for both), jvmcontract isn't built, or the work directory isn't ours. The
    record is also written to workdir/verifier.json."""
    stop = lambda why, stage="verifier", **kw: Unsupported("run-verifier", RUNTIME, why, stage=stage, **kw)
    if plan.kind not in VERIFIER_KINDS:
        return stop(f"a {plan.kind} task runs no verifier here (it runs {', '.join(VERIFIER_KINDS)})", "plan")
    if plan.engine not in ENGINES or plan.gaps not in GAP_MODES:
        return stop(f"the plan's engine {plan.engine!r} and gap mode {plan.gaps!r} must each be explicit and one of "
                    f"{ENGINES} and {GAP_MODES}: a proof never rests on the CLI's defaults", "plan")
    if len(plan.revisions) != (1 if plan.kind == "prove" else 2):
        return stop(f"a {plan.kind} task over {len(plan.revisions)} revisions", "plan")
    exe = jvmcontract()
    if exe is None:
        return stop("no built jvmcontract ($JVMCONTRACT or lib/target/release/jvmcontract)", "toolchain",
                    diagnostic="cd lib && cargo build --release, or run the task as a pipeline job that requires "
                               "jvmcontract (it gets one built from lib/)")
    try:
        workdir = _workdir(workdir, VERIFIER)
    except Refused as e:
        return stop("the verifier's work directory can't be used", e.stage, diagnostic=e.diagnostic)
    attempt = workdir.parent
    rel = lambda p: p.relative_to(attempt).as_posix()
    out, err = workdir / "verifier.stdout", workdir / "verifier.stderr"
    revision = plan.revisions[0] if plan.kind == "prove" else None
    identities, argv, log = {"jvmcontract": sha256(exe), "command": VERIFIER_KINDS[plan.kind]}, (), {}
    try:
        sides = {}
        for r in plan.revisions:
            p = prepared.get(r)
            if p is None:
                raise Refused("verifier", f"revision {r} was not prepared: a one-sided {plan.kind}")
            where = _preparation_dir(p, workdir)
            arts = _checked(where, p)
            if not (p.source.get("target") or {}).get("loadedFrom"):
                raise Refused("verifier", f"revision {r}'s preparation records no loaded target")
            sides[r] = (where, p, arts)
        jdk = _verifier_jdk(plan, prepared)
        argv = tuple(_verifier_argv(plan, exe, sides, rel(workdir)))
        env = _verifier_env(jdk)
        identities.update({
            "jdk": jdk["version"], "jdkFeature": jdk["feature"], "jdkHome": jdk["home"], "jdkRelease": jdk["release"],
            "engine": plan.engine, "gaps": plan.gaps, "bounds": dict(plan.claim.get("bounds") or {}),
            "timeout": VERIFIER_TIMEOUT, "scope": _scope(plan, sides),
            "classpath": {r: [{"path": a.path, "sha256": a.sha256, "role": a.role} for a in arts
                              if a.role in ("original", "dependency", "stub")] for r, (_, _, arts) in sides.items()},
            "commits": {r: p.commit for r, (_, p, _) in sides.items()},
            "environment": {k: v for k, v in env.items() if k != "PATH"}, "cwd": "the attempt directory"})
        identities["probe"] = _probe(exe, sides, java_target(plan.target), env, workdir, attempt)
    except Refused as e:
        if e.stage in CLAIM_STAGES:
            shutil.rmtree(workdir, ignore_errors=True)
            return stop(f"the task can't be attempted as stated: {e.diagnostic}", e.stage, diagnostic=e.next or e.needs)
        out.write_text("")
        err.write_text(f"runtime: not started: {e.diagnostic}\n")
        record = interfaces.ExecutionRecord(kind="verifier", revision=revision, argv=argv, status="not-started",
                                            exitCode=None, seconds=0.0, stdout=rel(out), stderr=rel(err),
                                            identities=identities, observations=None)
        (workdir / VERIFIER).write_text(json.dumps({"task": plan.task, "record": record.as_dict(),
                                                    "log": {"problem": e.diagnostic}}, indent=2) + "\n")
        return record
    status, code, seconds = _run_one(argv, attempt, out, err, VERIFIER_TIMEOUT + VERIFIER_GRACE, env)
    observations, problem = (None, f"the verifier {status}" + (f" (signal {-code})" if status == "killed" else "")) \
        if status != "exited" else _outcomes(out.read_text(errors="replace"), VERIFIER_KINDS[plan.kind])
    record = interfaces.ExecutionRecord(kind="verifier", revision=revision, argv=argv, status=status, exitCode=code,
                                        seconds=seconds, stdout=rel(out), stderr=rel(err), identities=identities,
                                        observations=observations)
    log = {"cwd": str(attempt), **({"problem": problem} if problem else {})}
    (workdir / VERIFIER).write_text(json.dumps({"task": plan.task, "record": record.as_dict(), "log": log}, indent=2,
                                               ensure_ascii=False) + "\n")
    return record

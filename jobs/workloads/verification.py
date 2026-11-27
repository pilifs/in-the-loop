"""The verification workload: what a proof, a model check or a numbered example's run means to the pipeline.

Until 2026-11-27 this was part of the pipeline itself, which was then only the verification pipeline. The
pipeline (jobs/pipeline.py) now owns what every job has (identity, attempts, scheduling, budget, outputs, the
record) and asks this module, for a job of the first format or one that names `workload: verification`, for what
is particular to proving:

  tools, missing       the checkers' versions, for a result's record of its machine, and which of a job's
                       requirements this machine lacks: Java, JBMC, TLC's jar, cargo, a Maven that the target
                       runtime builds with
  reservation, prepare the jvmcontract a job requires, built once for each tree of lib/ at the job's commit, with
                       the memory that build takes set aside
  step_env             the memory JBMC and TLC may take inside the job's cap, the job's own jvmcontract, and
                       where build.py keeps TLC's checkpoints
  scan, SUSPICIOUS     the verdict lines of JBMC, TLC, jvmcontract, build.py and cargo test, lifted out of a log
  verdicts, conclusion what those lines say of the claim: a job that ran as expected may have refuted it
  example_job_parts    the step, outputs and requirements of a job that runs a numbered example (`submit --example`)

`core` is the pipeline module, set when it loads this adapter. The other workloads define the same names
(`generic.py` says what each is for).
"""
import fcntl
import importlib.util
import json
import os
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

NAME = "verification"
core = None

# Lines worth lifting out of a log, so a reader need not open it: (tool, kind, pattern).
SIGNALS = [
    ("jbmc", "proved", r"^VERIFICATION SUCCESSFUL\s*$"),
    ("jbmc", "refuted", r"^VERIFICATION FAILED\s*$"),
    ("jbmc", "no-verdict", r"^VERIFICATION ERROR\s*$"),
    ("tlc", "no-error", r"Model checking completed\. No error has been found\."),
    ("tlc", "invariant-violated", r"Error: Invariant (\S+) is violated"),
    ("tlc", "property-violated", r"Error: (?:Temporal properties were violated|Action property (\S+) is violated)"),
    ("tlc", "deadlock", r"Error: Deadlock reached"),
    ("tlc", "states", r"([\d,]+) distinct states found"),
    ("jvmcontract", "holds", r"^✓ (.*)"),
    ("jvmcontract", "fails", r"^✗ (.*)"),
    ("jvmcontract", "unverifiable", r"^⚠ (.*)"),
    ("example", "as-expected", r"^(\d{3})-\S+: (verified|violation|unverifiable) \(as expected\)"),
    ("example", "unexpected", r"^(\d{3})-\S+: (\w+) \((EXPECTED[^)]*)\)"),
    ("example", "task-as-expected", r"^(\d{3})-\S+: task (\S+): (\w+) \([\w-]+; as expected\)"),
    ("example", "task-unexpected", r"^(\d{3})-\S+: task (\S+): (\w+) \([\w-]+; NOT AS EXPECTED \((.*)\)\), receipt "),
    # examples/tools/targets/workflow_refusal.py: a rerun of a task an observed gap blocks, at its recorded refusal or not.
    ("example", "task-refused-as-predicted", r"^(\d{3})-\S+: task (\S+): refused as predicted \(([^;]+); ([\w-]+); "),
    ("example", "task-not-as-predicted", r"^(\d{3})-\S+: task (\S+): NOT AS PREDICTED: (.*)"),
    ("example", "differ", r"^Verdicts differ from expectations: (.*)"),
    ("example", "not-executed", r"^(\d{3})-\S+: not-executed \((.*)\)$"),
    ("cargo", "tests", r"^test result: (ok|FAILED)\. (\d+) passed; (\d+) failed"),
    ("memory", "out-of-memory", r"java\.lang\.OutOfMemoryError|ran out of memory|std::bad_alloc|Cannot allocate memory"),
]
SIGNALS = [(tool, kind, re.compile(p)) for tool, kind, p in SIGNALS]

# In a step that passed: a signal that makes the pass worth a look, with what to say of it.
SUSPICIOUS = [("jbmc:no-verdict", "JBMC gave no verdict"), ("memory:out-of-memory", "the log mentions running out of memory"),
              ("jvmcontract:unverifiable", "jvmcontract reports something unverifiable"),
              ("example:unexpected", "an example's verdict differs from its expectation")]
# What a commit of collected results holds besides the results and the outputs applied: the examples table that
# the hook after a collect regenerates.
COLLECTORS_OWN = ("examples/README.md", "examples/index.json")


# The machine: which checkers are here


def tla2tools():
    jar = Path(os.environ.get("TLA2TOOLS_JAR") or Path.home() / "tools/tla2tools.jar")
    return jar if jar.exists() else None


def tlc_version(jar):
    try:
        with zipfile.ZipFile(jar) as z:
            manifest = z.read("META-INF/MANIFEST.MF").decode(errors="replace")
        m = re.search(r"^Implementation-Version:\s*(.+)$", manifest, re.M)
        return m[1].strip() if m else "unknown"
    except (OSError, KeyError, zipfile.BadZipFile):
        return None


def tools() -> dict:
    """The versions of the checkers and the toolchains they run on, for a result's record of its machine."""
    jar = tla2tools()
    cargo = shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo")
    first_line = core.first_line
    return {
        "java": first_line(["java", "-version"]) or first_line(["bash", "-c", "java -version 2>&1"]),
        "javac": first_line(["javac", "-version"]),
        "jbmc": first_line(["jbmc", "--version"]),
        "tlc": tlc_version(jar) if jar else None,
        "tla2toolsJar": str(jar) if jar else None,
        "cargo": first_line([cargo, "--version"]),
        "rustc": first_line(["rustc", "--version"]) or first_line([str(Path(cargo).parent / "rustc"), "--version"]),
    }


def installed_maven():
    """Whether examples/tools/targets/runtime_upstream.py has a Maven to build with: it runs the highest install under
    $TARGETS_MAVEN_CANDIDATES (default sdkman's candidates) by full path, never `current` or a link, and no `mvn` on
    PATH. A target task's plan requires it as "maven" (workflow.BUILD_TOOLS), which no executable is named."""
    root = Path(os.environ.get("TARGETS_MAVEN_CANDIDATES", Path.home() / ".sdkman/candidates/maven"))
    return root.is_dir() and any(e.name != "current" and not e.is_symlink() and (e / "bin/mvn").is_file()
                                 for e in root.iterdir())


def missing(requires) -> list:
    checks = {
        "maven": installed_maven,
        "java": lambda: shutil.which("java") or os.environ.get("JAVA_HOME"),
        "javac": lambda: shutil.which("javac") or os.environ.get("JAVA_HOME"),
        "jbmc": lambda: shutil.which("jbmc"),
        "tlc": tla2tools,
        "cargo": lambda: shutil.which("cargo") or (Path.home() / ".cargo/bin/cargo").exists(),
        "jvmcontract": lambda: shutil.which("cargo") or (Path.home() / ".cargo/bin/cargo").exists(),
        "gradle": lambda: shutil.which("java") or os.environ.get("JAVA_HOME"),
    }
    return [r for r in requires if not (checks.get(r) or (lambda r=r: shutil.which(r)))()]


# jvmcontract, built once per tree of lib/


def lib_tree(source):
    proc = core.git("rev-parse", f"{source}:lib", check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


def jvmcontract_cached(runner, source):
    tree = lib_tree(source)
    return bool(tree) and (runner.state / "tools" / "jvmcontract" / tree / "jvmcontract").exists()


def reservation(runner, job, job_plan, source) -> int:
    memory = job_plan["memoryLimit"]
    if "jvmcontract" in job.get("requires", []) and not runner.jvmcontract_cached(source):
        memory = max(memory, runner.runner["build_memory"])
    return memory


def prepare(runner, job, source, work, result, entry) -> None:
    if "jvmcontract" in job.get("requires", []):
        build_jvmcontract(runner, source, work, result, entry)


def build_jvmcontract(runner, source, work, result, entry):
    tree = lib_tree(source)
    if not tree:
        raise RuntimeError(f"no lib/ at {source[:12]}, and the job requires jvmcontract")
    exe = runner.state / "tools" / "jvmcontract" / tree / "jvmcontract"
    with open(runner.state / "tools" / "jvmcontract.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if exe.exists():
            result["jvmcontract"] = {"libTree": tree, "path": str(exe), "built": False}
            return
        # The target directory is shared between jobs, and cargo rebuilds a crate only when a source is newer than
        # its last build. `git archive` dates every file at its commit, which is older than a binary built since
        # from any other commit, so without this every job ran whichever jvmcontract was built last (Nov 4 2026:
        # 13 lib/ trees, one binary). Dating lib/ now makes cargo rebuild it; the dependencies are not affected.
        started = time.time()
        for path in (work / "lib").rglob("*"):
            os.utime(path, (started, started), follow_symlinks=False)
        cargo = shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo")
        run = f"{cargo} build --release --manifest-path lib/Cargo.toml"
        env = dict(os.environ, CARGO_TARGET_DIR=str(runner.state / "cargo-target"))
        log = entry["attempt"].run_dir / "logs" / "0-build-jvmcontract.log"
        step = core.Step(f"vjob-{core.scope_id(result['id'])}-build", runner.isolation, max(entry["cpus"], 1),
                    max(entry["memory"], runner.runner["build_memory"]), runner.runner["stall_window"],
                    runner.runner["max_timeout"], runner.runner["job_oom_score_adj"])
        entry["steps"].append(step)
        outcome = step.run(run, work, env, log, log.with_suffix(".stats"), runner.wrapper, 3600)
        record = runner.step_record({"name": "build jvmcontract", "run": run, "cwd": "."}, 0, outcome, log)
        record["status"] = "passed" if outcome["exitCode"] == 0 else ("out-of-memory" if outcome["oomKills"] else "failed")
        result["steps"].append(record)
        built = runner.state / "cargo-target" / "release" / "jvmcontract"
        if outcome["exitCode"] != 0 or not built.exists():
            result["status"] = "error"
            result["attention"].append("jvmcontract did not build at this commit; see the build step's log")
            return
        if built.stat().st_mtime < started:
            result["status"] = "error"
            result["attention"].append("cargo reused a jvmcontract built before this job instead of building lib/ "
                                       "at this commit; nothing ran on it")
            return
        exe.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(built, exe)
        result["jvmcontract"] = {"libTree": tree, "path": str(exe), "built": True}


def step_env(runner, job, result, work, env) -> None:
    limit_mb = result["limits"]["memoryLimitBytes"] // (1024 * 1024)
    # Inside the cap, JBMC should stop by itself with "out of memory" rather than be killed, and TLC's heap
    # should fit: Java's default heap is a quarter of the machine, not of the cap.
    env["JVMCONTRACT_JBMC_MEMORY_MB"] = str(max(256, limit_mb - 512))
    env["JVMCONTRACT_JAVA_OPTS"] = f"-Xmx{max(256, int(limit_mb * 0.6))}m"
    env.pop("JVMCONTRACT_LIB_TREE", None)  # only ever the job's own build's, never the runner's environment
    if result.get("jvmcontract"):
        exe = Path(result["jvmcontract"]["path"])
        env["JVMCONTRACT"] = str(exe)
        # The git tree id of the lib/ it was built from (VERIFY_SOURCE_COMMIT's lib/), for a record to name.
        env["JVMCONTRACT_LIB_TREE"] = result["jvmcontract"]["libTree"]
        env["PATH"] = f"{exe.parent}:{env.get('PATH', '')}"
    # build.py keeps each TLC configuration's result under the fingerprint of its inputs, so a job run again after
    # a timeout or a failure picks up the configurations already done; a result is reused only on identical inputs.
    env.setdefault("BUILD_CHECKPOINTS", str(runner.state / "checkpoints"))


# Reading a log


def scan(log_path):
    return core.scan_log(log_path, SIGNALS)


def verdicts(steps) -> list:
    """What the summary line says of the signals: each kind with its count, and TLC's state counts by themselves."""
    found = []
    for s in steps:
        for key, n in sorted((s.get("signalCounts") or {}).items()):
            if key not in ("tlc:states",):
                found.append(f"{key}×{n}")
        states = [g["groups"][0] for g in s.get("signals", []) if g["tool"] == "tlc" and g["kind"] == "states" and g["groups"]]
        if states:
            found.append(f"tlc states {', '.join(states[:4])}{'…' if len(states) > 4 else ''}")
    return found


# What settles a claim one way, and what the other, among the signals of the steps that went as expected. Only
# these are a checker's answer: an exit code is not, and neither is a pass with no verdict line at all.
ESTABLISHES = ("jbmc:proved", "tlc:no-error", "jvmcontract:holds")
REFUTES = ("jbmc:refuted", "tlc:invariant-violated", "tlc:property-violated", "tlc:deadlock", "jvmcontract:fails")
OPEN = ("jbmc:no-verdict", "jvmcontract:unverifiable", "example:not-executed")


def conclusion(job, result):
    """What the checkers said, apart from whether the job ran as expected: a job whose every step exited as its
    specification expects has *succeeded*, and its claim may be established, refuted or left open all the same (an
    example whose expected verdict is a violation passes by refuting). The scope is the job's own: the claims its
    steps put to a checker. `verdict` is `mixed` when the steps disagree, and `none` when no checker's line was
    found, which is never read as established."""
    counts = {}
    for step in result.get("steps") or []:
        if step.get("status") == "skipped":
            continue
        for key, n in (step.get("signalCounts") or {}).items():
            counts[key] = counts.get(key, 0) + n
    established = sum(counts.get(k, 0) for k in ESTABLISHES)
    refuted = sum(counts.get(k, 0) for k in REFUTES)
    left_open = sum(counts.get(k, 0) for k in OPEN)
    # build.py's own line for a numbered example says which verdict it got and whether that was the expected one.
    examples = [(g["groups"], s["index"]) for s in result.get("steps") or [] for g in s.get("signals", [])
                if g["tool"] == "example" and g["kind"] in ("as-expected", "unexpected") and len(g.get("groups") or []) >= 2]
    for groups, _ in examples:
        if groups[1] == "verified":
            established += 1
        elif groups[1] == "violation":
            refuted += 1
        elif groups[1] == "unverifiable":
            left_open += 1
    if result.get("status") in ("timeout", "out-of-memory", "error", "cancelled"):
        verdict = "none"
    elif refuted and established:
        verdict = "mixed"
    elif refuted:
        verdict = "refuted"
    elif left_open:
        verdict = "open"
    elif established:
        verdict = "established"
    else:
        verdict = "none"
    return {"workload": NAME, "verdict": verdict,
            "scope": "the claims this job's steps put to a checker, at the bounds and the source revision of the job",
            "counts": {"established": established, "refuted": refuted, "open": left_open},
            "asExpected": {"examples": len([1 for s in result.get("steps") or [] for g in s.get("signals", [])
                                            if g["tool"] == "example" and g["kind"] in ("as-expected", "task-as-expected", "task-refused-as-predicted")]),
                           "unexpected": counts.get("example:unexpected", 0) + counts.get("example:task-unexpected", 0)
                           + counts.get("example:task-not-as-predicted", 0)},
            "evidence": "the verdict lines in each step's `signals`, with their line numbers in its log"}


# Submitting a numbered example


def example_plan(example):
    """build.py's plan() of an example (examples/tools/build.py, imported without running anything): what the run
    builds and which tools it calls. The pipeline asks build.py rather than guessing from the approach, so a job
    requires what its run uses: no JBMC for a proof by the tool's own checker, jvmcontract (and its build memory) for
    a B12 run on the Gradle app."""
    return build_module(example["id"]).plan(example)


def build_module(example_id):
    """examples/tools/build.py, imported without running anything."""
    path = core.ROOT / "examples/tools/build.py"
    if not path.exists():
        sys.exit(f"example {example_id}: {path.relative_to(core.ROOT)} is missing, and the plan of a run comes from it")
    spec = importlib.util.spec_from_file_location("examples_build", path)
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    return build


def example_task_job_parts(example_id, folder, task):
    """The job parts of one task of a real-world example with a target sidecar (llm-dlc/loops/example-targets.md):
    the same plan `build.py --plan ID --task T` prints (examples/tools/targets/route.py), and its step runs
    `build.py ID --task T`. A task whose plan is not executable (Phase 0's stubs answer Unsupported) is refused."""
    build = build_module(example_id)
    example = build.load_example(folder)
    target = build.sidecar.load(folder, example)
    if target is None:
        sys.exit(f"example {example_id} has no target sidecar (target.json), so it has no task {task!r}")
    try:
        plan = build.target_route.plan(folder, example, target, task)
    except build.target_route.UnknownTask as e:
        sys.exit(str(e))
    if not plan["executable"]:
        sys.exit(f"example {example_id} task {task}: not executable ({plan['notExecuted']})")
    rel = folder.relative_to(core.ROOT).as_posix()
    requires = list(dict.fromkeys(plan["tools"]["required"] + plan["tools"]["optional"]))
    expected = plan.get("expected")
    if expected:
        outcome = f"gives its expected conclusion, {expected}"
    elif plan["kind"] == "replay":  # a replay decides no claim; its receipt's expectation is its pair's kind's
        outcome = ("replays every revision on every JDK it names, each with the outcome its pair's kind expects "
                   f"({', '.join(plan['revisions'])})")
    else:
        outcome = "gives a conclusion, though it states no expected one (so build.py exits 1)"
    return {"step": {"name": f"example {example_id} task {task} ({plan['kind']})",
                     "run": f"python3 examples/tools/build.py {example_id} --task {task}", "cwd": "."},
            "output": f"{rel}/{plan['outputs'].get('receipts', 'receipts/' + task)}", "requires": requires,
            "capability": f"target:{plan['kind']}",
            "expected": f"example {example_id} task {task} {outcome}: build.py prints 'as expected' and exits 0"}


def example_job_parts(example_id, task=None):
    """The step, outputs, requirements and capability of a job that runs one demo example through build.py. The
    requirements are the tools build.py's plan says the run calls, its optional ones included: a job that may need a
    tool runs where the tool is."""
    folders = sorted((core.ROOT / "examples").glob(f"{example_id}-*"))
    if len(folders) != 1:
        sys.exit(f"example {example_id}: expected one folder examples/{example_id}-*, found {len(folders)}")
    folder = folders[0]
    example = json.loads((folder / "example.json").read_text())
    if task is not None:
        return example_task_job_parts(example_id, folder, task)
    if example.get("target"):
        sys.exit(f"example {example_id} has a target sidecar: name one of its tasks with --task "
                 "(python3 examples/tools/build.py --plan ID lists them)")
    if example.get("origin") != "constructed":
        sys.exit(f"example {example_id} is {example.get('origin')}: build.py does not run it (its report is its README.md); "
                 "describe its proof with --step and --kind real-world instead")
    plan = example_plan(example)
    if not plan["executable"]:
        sys.exit(f"example {example_id}: build.py does not run it ({plan['notExecuted']})")
    approach = plan["approach"]
    requires = list(dict.fromkeys(plan["tools"]["required"] + plan["tools"]["optional"]))
    rel = folder.relative_to(core.ROOT).as_posix()
    return {"step": {"name": f"example {example_id} ({approach})", "run": f"python3 examples/tools/build.py {example_id}",
                     "cwd": "."},
            "output": rel, "requires": requires, "capability": approach,
            "expected": f"example {example_id} gives its expected verdict, {example['expected']['verdict']}"
                        f"{' (vacuously)' if example['expected'].get('vacuous') else ''}: build.py prints 'as expected' and exits 0"}

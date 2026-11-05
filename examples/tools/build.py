#!/usr/bin/env python3
"""Run the formal verification examples in examples/ and render them.

Each example folder holds what a person writes: example.json (the change, its risk, the expected verdict) and
change.patch. This script applies the patch to a temporary copy of the repo, runs the real verifier named by the
example's approach, and writes what it produced next to them:

  result.json          verdict, counterexamples, before/after excerpts, contract diff (examples/schema/result.schema.json)
  result.sarif         the verifier's SARIF report, with repo-relative paths
  verifier-output.txt  the verifier's console output
  statement.java       for symbolic proofs: the generated statement the prover checked
  README.md            the example, rendered for reading

and then examples/README.md (the table of contents) and examples/index.json.
It exits 1 if any verdict differs from the example's expected verdict, so the examples also test the verifiers, or if
a requested example was not executed (a real-world one, or one no app or runner takes: a `not-executed` line says
why). It exits 2, running nothing, on an argument that is not the id of an example.

The runner writes its evidence into a directory of its own, one per attempt; the claim it checks (what, over which
scope, against which inputs, fingerprinted) is written there as claim.json before anything is built. result.json
records the claim, the attempt, the conclusion and the bundle of evidence files with their hashes (see claim_record()
and below), and nothing is published into the example's folder until the result validates against the schema and
the bundle against the files; evidence of an earlier run that the bundle does not list is then removed.

Approaches (the ids are those of examples/approaches.md):
  B8   behavioural contracts: every input of a finite domain, executed      (verify)
  B9   regression verification: old and new bytecode compared symbolically  (equivalence; JBMC)
  B10  capability contracts: what a module's bytecode can reach             (verify)
  B11  property proofs: a stated property of one method, on every input     (prove; JBMC)
  B12  boundary contracts: a Spring Boot module's routes, listeners, schedules, advice, wire types and the places advice does not apply (verify)
  D1   protocol model checking: the system in TLA+, driven by a contract    (spec; TLC)

Four subject applications. Box Office (examples/apps/boxoffice, examples 001 to 012) is a Gradle build verified
by the Java proof of concept in examples/tools/contracts. Quorum (examples/apps/quorum, examples 013 to 022),
Crosscut (examples/apps/crosscut, examples 023 to 033) and Mica (examples/apps/mica, examples 034 onwards) are
plain javac, verified by the Rust tool in lib/ (jvmcontract). The app is chosen by the example's subject file.

Usage: python3 examples/tools/build.py [ID ...]          run constructed examples (all of them by default)
       python3 examples/tools/build.py --render-only [ID ...]  rewrite their pages from result.json, running nothing
       python3 examples/tools/build.py --plan [ID ...]     print what each run would take (plan()), as JSON, running nothing
       python3 examples/tools/build.py --index-only        the router: examples/README.md's tables and examples/index.json

A real-world example (origin "real-world") is not run, and naming one is a failure: its report is its README.md, and its example.json is what the
router knows of it. Every example's tags must come from examples/tags.json.
Needs Java 25 on PATH or JAVA_HOME; JBMC for B9 and B11; TLC (tla2tools.jar in ~/tools, or TLA2TOOLS_JAR) for D1;
cargo (or a built lib/target/release/jvmcontract, or JVMCONTRACT pointing at one) for the javac apps; the Python
module jsonschema, without which no result is published. No Docker.
"""

import atexit
import contextlib
import datetime
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"
BUILD_ROOT = "examples/apps/boxoffice"  # the Gradle build the Box Office examples patch
VERIFIER = "examples/tools/contracts"
COPY = [BUILD_ROOT, VERIFIER]
# The javac builds verified by the Rust tool in lib/: the app's root, the main class that runs its tests, and its
# TLA+ model for D1 (defined below).
TOOL_APPS = {
    "quorum": {"root": "examples/apps/quorum", "tests": "net.terminalvalue.quorum.Tests"},
    "crosscut": {"root": "examples/apps/crosscut", "tests": "net.terminalvalue.crosscut.Tests"},
    "mica": {"root": "examples/apps/mica", "tests": "net.terminalvalue.mica.Tests"},
}
IGNORE = shutil.ignore_patterns("build", ".gradle", ".kotlin", "*.class")

VERDICT_LABEL = {
    "violation": "✗ Violation",
    "verified": "✓ Verified",
    "unverifiable": "⚠ Unverifiable",
}

# Per-approach caches, filled on first use. The scratch directory they live in belongs to the execution, not to the
# module: it is made on first use and removed at exit, so importing build.py (as the pipeline does, for plan()) makes
# nothing.
BEFORE_CLASSES = {}
_SCRATCH = []


def kept_workspace():
    """Where a run keeps its attempts, or None. In a pipeline job it is `$VERIFY_WORKDIR/.build-py`, inside the job's
    work directory, which the pipeline keeps when the job fails (or is killed, or times out) and removes when it passes.
    Each attempt there keeps its patched copy, with the harnesses and the tools' work directories, and its stage logs.
    Outside the pipeline the scratch directory is removed at exit, and each patched copy as soon as its run ends."""
    work = os.environ.get("VERIFY_WORKDIR")
    return Path(work) / ".build-py" if work else None


def scratch():
    """The run's scratch directory, made on first use: under the kept workspace, or a temporary one removed at exit."""
    if not _SCRATCH:
        kept = kept_workspace()
        if kept:
            kept.mkdir(parents=True, exist_ok=True)
            _SCRATCH.append(Path(tempfile.mkdtemp(prefix="examples-", dir=kept)))
        else:
            _SCRATCH.append(Path(tempfile.mkdtemp(prefix="examples-")))
            atexit.register(shutil.rmtree, _SCRATCH[0], True)
    return _SCRATCH[0]


# Stages. Every command a run makes goes through stage(). While run() runs an attempt, each command's stdout and
# stderr stream into the attempt's logs/ directory as it runs (NN-name.stdout, NN-name.stderr), logs/stages.jsonl
# gets a line when the stage starts and another when it ends, and a short progress line is printed for each. So a
# job interrupted at any point leaves every stage's output so far, and the pipeline's log shows which one was running.
# Outside an attempt (the tests, tool identities asked before one) the output is captured as before.
_STAGES = {"dir": None, "n": 0, "records": []}


def stage_log(record):
    with open(_STAGES["dir"] / "stages.jsonl", "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def stage(name, command, *, cwd=None, input=None, timeout=None, env=None, check=False):
    """Runs one command of the run as the stage `name` and returns its CompletedProcess, with stdout and stderr as
    text. `timeout` raises TimeoutExpired with the output so far, and `check` CalledProcessError, as subprocess.run."""
    logs = _STAGES["dir"]
    if logs is None:
        proc = subprocess.run(command, cwd=cwd, input=input, timeout=timeout, env=env, text=True, capture_output=True)
        if check and proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, command, proc.stdout, proc.stderr)
        return proc
    _STAGES["n"] += 1
    base = f"{_STAGES['n']:02d}-" + (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "stage")
    record = {"n": _STAGES["n"], "name": name, "command": [str(c) for c in command], "cwd": str(cwd) if cwd else None,
              "stdout": f"logs/{base}.stdout", "stderr": f"logs/{base}.stderr",
              "startedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "status": "running"}
    stage_log(record)
    print(f"  · {name}", flush=True)
    clock, raised = time.monotonic(), None
    with open(logs / f"{base}.stdout", "w") as out, open(logs / f"{base}.stderr", "w") as err:
        try:
            proc = subprocess.run(command, cwd=cwd, input=input, timeout=timeout, env=env, text=True, stdout=out, stderr=err)
        except (subprocess.TimeoutExpired, OSError) as e:
            proc, raised = None, e
        if proc is not None and isinstance(proc.stdout, str):  # a process the tests made up: its output is the log
            out.write(proc.stdout)
            err.write(proc.stderr or "")
    stdout, stderr = ((logs / f"{base}.{k}").read_text(errors="replace") for k in ("stdout", "stderr"))
    seconds = round(time.monotonic() - clock, 1)
    status = ("timed-out" if isinstance(raised, subprocess.TimeoutExpired) else "not-started" if raised
              else "exited" if proc.returncode >= 0 else "killed")
    record.update({"status": status, "exitCode": proc.returncode if proc else None, "seconds": seconds})
    stage_log(record)
    _STAGES["records"].append({k: record[k] for k in ("name", "status", "exitCode", "seconds", "stdout", "stderr")})
    print(f"  · {name}: {status}{f' {proc.returncode}' if proc else ''}, {seconds} s", flush=True)
    if isinstance(raised, subprocess.TimeoutExpired):
        raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
    if raised:
        raise raised
    proc = subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(proc.returncode, command, stdout, stderr)
    return proc


@contextlib.contextmanager
def stages(out):
    """The stages of one attempt, logged under `out`/logs."""
    (Path(out) / "logs").mkdir(parents=True, exist_ok=True)
    _STAGES.update({"dir": Path(out) / "logs", "n": 0, "records": []})
    try:
        yield _STAGES["records"]
    finally:
        _STAGES["dir"] = None


def main(argv):
    folders = sorted(p for p in EXAMPLES.iterdir() if p.is_dir() and re.match(r"^\d{3}-", p.name))
    mode = argv[0] if argv[:1] in (["--index-only"], ["--render-only"], ["--plan"]) else None
    ids = argv[1:] if mode else argv
    problem = selection_problem(mode, ids, folders)
    if problem:
        print(f"build.py: {problem}", file=sys.stderr)
        print("usage: build.py [ID ...] | --render-only [ID ...] | --plan [ID ...] | --index-only", file=sys.stderr)
        return 2  # nothing has run
    wanted = set(ids)
    if mode == "--plan":
        # What each run would take, as JSON, running nothing: every constructed example's by default.
        plans = [plan(load_example(f)) for f in folders if (f.name[:3] in wanted if wanted else True)]
        print(json.dumps([q for q in plans if wanted or q["executable"] or "real-world" not in (q["notExecuted"] or "")],
                         indent=2, ensure_ascii=False))
        return 0
    if mode == "--index-only":
        render_index(folders)  # after the verification pipeline has brought results back (verification/README.md)
        return 0
    if mode == "--render-only":
        unrendered = []
        for folder in folders:
            if wanted and folder.name[:3] not in wanted:
                continue
            example = load_example(folder)
            if example["origin"] != "constructed":
                if wanted:
                    print(f"{folder.name}: not rendered (a real-world example: its page is written by hand)")
                    unrendered.append(folder.name)
                continue
            if not (folder / "result.json").exists():
                print(f"{folder.name}: not run yet, no page")
                if wanted:
                    unrendered.append(folder.name)
                continue
            res = json.loads((folder / "result.json").read_text())
            snap = snapshot(folder, example, res)
            if snap["state"] == "stale":
                print(f"{folder.name}: stale ({'; '.join(snap['reasons'])})")
            if snap["evidence"]:
                print(f"{folder.name}: evidence not the run's ({'; '.join(snap['evidence'])})")
            (folder / "README.md").write_text(render_example(folder, example, res, snap))
        render_index(folders)
        if unrendered:
            print("Not rendered: " + ", ".join(unrendered))
            return 1
        return 0
    failures, unexecuted = [], []
    for folder in folders:
        if wanted and folder.name[:3] not in wanted:
            continue
        example = load_example(folder)
        if example["origin"] != "constructed" and not wanted:
            continue  # running every example means every constructed one
        reason = not_executable(example)
        if reason:
            # Nothing ran, so nothing is written: an earlier result.json stays the record of its own run.
            print(f"{folder.name}: not-executed ({reason})")
            unexecuted.append(folder.name)
            continue
        print(f"{folder.name}: running ({example['approach']['id']})", flush=True)
        out = attempt_directory(folder)
        result = run(folder, example, out)
        check_result(out, result)  # nothing is published from a run whose result or bundle does not check
        publish(folder, out, result)
        (folder / "README.md").write_text(render_example(folder, example, result))
        expected = f"EXPECTED {example['expected']['verdict'].upper()}{' VACUOUSLY' if example['expected'].get('vacuous') else ''}"
        if result["verdict"] is None:
            # In the shape of an unexpected verdict, which the pipeline's `example:unexpected` signal reads.
            print(f"{folder.name}: none ({expected}; the run did not complete, {result['execution']['status']}: "
                  f"{result['execution']['reason']})")
        else:
            print(f"{folder.name}: {result['verdict']} ({'as expected' if result['matchesExpected'] else expected})")
        if not result["matchesExpected"]:
            failures.append(folder.name)
    render_index(folders)
    if failures:
        print("Verdicts differ from expectations: " + ", ".join(failures))
    if unexecuted:
        print("Not executed: " + ", ".join(unexecuted))
    return 1 if failures or unexecuted else 0


def selection_problem(mode, ids, folders):
    """Why the command line selects nothing it can act on, or None. An id is an example's three digits."""
    if mode == "--index-only" and ids:
        return f"--index-only takes no ids: {' '.join(ids)}"
    bad = [a for a in ids if not re.fullmatch(r"\d{3}", a)]
    if bad:
        return f"not an example id (three digits, such as 017): {' '.join(bad)}"
    known = {f.name[:3] for f in folders}
    unknown = sorted(set(ids) - known)
    if unknown:
        return f"no example with id {', '.join(unknown)} in examples/"
    return None


def not_executable(example):
    """Why build.py cannot run this example, or None when it can."""
    if example["origin"] != "constructed":
        return ("a real-world example: its report is its README.md, and build.py has no adapter for its "
                "project's build")
    app = app_of(example)
    if app is None:
        return (f"its subject file {example['subject']['file']} is not under {BUILD_ROOT} or "
                + ", ".join(c["root"] for c in TOOL_APPS.values()) + ", so no app builds it")
    if example["approach"]["id"] not in RUNNERS[app]:
        return f"no runner for approach {example['approach']['id']} on {app}"
    if example["approach"]["id"] == "D1" and find_model(example) is None:
        return f"no TLA+ model of {app} is built around {example['subject']['symbol']}"
    return None


# The tools a run calls, by app and approach. Box Office builds with Gradle, which also builds its Java verifier (B8,
# B9, B10); that verifier proves B9 with JBMC; B12 is jvmcontract's `verify` on the Gradle build's classes; D1 is
# TLC. The javac apps are compiled by javac and verified by jvmcontract, which calls JBMC for B9 and B11 unless the
# example names the tool's own checker, and TLC for D1.
PLAN_TOOLS = {
    "boxoffice": {"B8": ["gradle"], "B9": ["gradle", "jbmc"], "B10": ["gradle"], "B12": ["gradle", "jvmcontract"],
                  "D1": ["gradle", "tlc"]},
    "javac": {"B8": ["jvmcontract"], "B9": ["jvmcontract"], "B10": ["jvmcontract"], "B11": ["jvmcontract"],
              "D1": ["jvmcontract", "tlc"]},
}
# What every run writes into the example's folder, and what some runs write too.
PLAN_OUTPUTS = ["result.json", "result.sarif", "verifier-output.txt", "README.md"]


def plan(example):
    """What running an example takes, resolved from its example.json alone, with no side effect: nothing is built,
    copied or run, and no directory is made. build.py executes it (run()), and the verification pipeline takes a
    job's tool needs from it (pipeline.py's example_job_parts()), so the two cannot disagree about what a run calls.

    `executable` is False, with the reason in `notExecuted`, for an example build.py does not run. Otherwise:
    `app` and `module`; `build`, the adapter (gradle or javac), the app's root and what is copied for the patched
    copy; `runner`; `claim`, what is checked: the approach, the target and what the change declares about it;
    `engine`, the checker that decides a B9 or B11 verdict (`jbmc`, `native` or `auto`; None for the others), and
    `options`, the flags it is given; `tools`, `required` (the run cannot go without them) and `optional` (it calls
    them only in some cases: JBMC under `auto`, when the tool's own checker has no verdict); `model`, for D1: the
    specification, its configurations and the generated operators; `outputs`, the files the run writes into the
    example's folder (`maybe`: only when the run produces them)."""
    approach = example["approach"]["id"]
    reason = not_executable(example)
    p = {"example": example["id"], "approach": approach, "executable": reason is None, "notExecuted": reason}
    if reason:
        return p
    app = app_of(example)
    boxoffice = app == "boxoffice"
    root = BUILD_ROOT if boxoffice else TOOL_APPS[app]["root"]
    change = example["change"]
    claim = {"approach": approach, "target": example["subject"]["symbol"], "file": example["subject"]["file"],
             "behaviourChangeIntended": change["behaviourChangeIntended"]}
    for key in ("intendedInputs", "previousSymbol", "previousArguments", "resultsAgreeWhen"):
        if change.get(key) and approach == "B9":
            claim[key] = change[key]
    if approach == "B9" and boxoffice:
        engine = "jbmc"  # the Java verifier knows no other
    elif approach in ("B9", "B11"):
        engine = example["approach"].get("engine") or "jbmc"
    else:
        engine = None
    tools = ["java", "javac"] + PLAN_TOOLS["boxoffice" if boxoffice else "javac"][approach]
    optional = []
    if engine and not boxoffice:
        if engine == "jbmc":
            tools.append("jbmc")
        elif engine == "auto":
            optional.append("jbmc")
    model = None
    if approach == "D1":
        files = find_model(example)
        if boxoffice:
            model = {"spec": f"{root}/{SPEC}/BoxOffice.tla",
                     "configurations": [{"cfg": f"{root}/{SPEC}/BoxOffice.cfg", "label": "the model"}],
                     "operators": [BOX_OFFICE_KERNEL]}
        else:  # paths from the repo's root
            model = {"spec": f"{root}/{files['spec']}",
                     "configurations": [{"cfg": f"{root}/{c['cfg']}", "label": c["label"]} for c in tlc_configurations(files)],
                     "operators": [g["symbol"] for g in [files, *files.get("operators", [])]]}
    maybe = ["statement.java", "statement-N.java"] if approach == "B11" else ["statement.java"] if approach == "B9" and not boxoffice else []
    return {**p, "app": app, "module": module_of(example["subject"]["file"]) if boxoffice else app,
            "build": {"adapter": "gradle" if boxoffice else "javac", "root": root, "copies": COPY if boxoffice else [root]},
            "runner": RUNNERS[app][approach].__name__, "claim": claim, "engine": engine,
            "options": proof_options(example, approach) if not boxoffice else [],
            "tools": {"required": tools, "optional": optional}, "model": model,
            "outputs": {"always": PLAN_OUTPUTS, "maybe": maybe}}


def proof_options(example, approach=None):
    """The flags jvmcontract's proof is given for an example: the engine for B9 and B11, and the unwinding and array
    bounds for B9. Its runners pass exactly these, so the plan names what runs."""
    approach = approach or example["approach"]["id"]
    if approach not in ("B9", "B11"):
        return []
    a = example["approach"]
    flags = ["--engine", a["engine"]] if a.get("engine") else []
    if approach == "B9":
        if a.get("unwind"):
            flags += ["--unwind", str(a["unwind"])]
        if a.get("maxArrayLength"):
            flags += ["--max-array-length", str(a["maxArrayLength"])]
    return flags


def load_example(folder):
    example = json.loads((folder / "example.json").read_text())
    validate(example, "example.schema.json", folder / "example.json")
    if example["id"] != folder.name[:3]:
        sys.exit(f"{folder}: id {example['id']} does not match the folder name")
    unknown = [t for t in example["tags"] if t not in tag_vocabulary()]
    if unknown:
        sys.exit(f"{folder}: tags not in examples/tags.json: {', '.join(unknown)}")
    return example  # whether build.py can run it is not_executable()'s question


_TAGS = {}


def tag_vocabulary():
    """tag -> (facet, description), from examples/tags.json."""
    if not _TAGS:
        for facet, tags in json.loads((EXAMPLES / "tags.json").read_text()).items():
            if not facet.startswith("$"):
                for tag, description in tags.items():
                    _TAGS[tag] = (facet, description)
    return _TAGS


def tag_links(tags, base="../README.md"):
    return ", ".join(f"[{t}]({base}#tag-{t})" for t in tags)


def app_of(example):
    """Which subject application the example changes: 'boxoffice' or a javac app, by its subject file; None if none."""
    file = example["subject"]["file"]
    for app, config in TOOL_APPS.items():
        if file.startswith(config["root"] + "/"):
            return app
    if file.startswith(BUILD_ROOT + "/"):
        return "boxoffice"
    return None


def validate(document, schema_name, path):
    try:
        import jsonschema
    except ImportError:
        # A result that cannot be checked is not published: install it (pip install jsonschema, or the
        # python3-jsonschema package).
        sys.exit(f"{path}: cannot be validated against {schema_name}: the Python module jsonschema is not installed")
    schema = json.loads((EXAMPLES / "schema" / schema_name).read_text())
    try:
        jsonschema.validate(document, schema)
    except jsonschema.ValidationError as e:
        sys.exit(f"{path}: {e.message}")


# How a verifier's run ended, decided before anything in its output is read as a verdict. Only a completed run has a
# verdict; a run that was killed, timed out, failed in the tool or printed what the runner cannot read has none, and
# can never match an example's expectation, a violation least of all.

EXECUTION_STATUSES = ("completed", "timed-out", "killed", "invalid-output", "tool-error")


def last_line(output):
    lines = [line.strip() for line in (output or "").splitlines() if line.strip()]
    return lines[-1] if lines else None


def execution_status(returncode, output, timed_out=None, known=(0, 1)):
    """How a verifier's process ended: {"status", "exitCode", "reason"}. `known` are the exit codes that mean the
    verifier finished (0 verified, 1 violated or cannot be verified, for jvmcontract and the Java verifier); any
    other is the tool's own failure. A negative code is a signal (Python's convention), and so is 128 + N from a shell
    or a wrapper script. `timed_out` is the limit in seconds when the runner gave up waiting."""
    if timed_out is not None:
        return {"status": "timed-out", "exitCode": None, "reason": f"the verifier did not finish within {timed_out} s"}
    if returncode < 0:
        return {"status": "killed", "exitCode": returncode, "reason": f"the verifier was killed by signal {-returncode}"}
    if 128 < returncode <= 128 + 64 and returncode not in known:
        return {"status": "killed", "exitCode": returncode,
                "reason": f"the verifier exited with code {returncode}, a shell's report of signal {returncode - 128}"}
    if returncode not in known:
        line = last_line(output)
        return {"status": "tool-error", "exitCode": returncode,
                "reason": f"the verifier failed with exit code {returncode}" + (f": {line}" if line else ", printing nothing")}
    if not (output or "").strip():
        return {"status": "invalid-output", "exitCode": returncode,
                "reason": f"the verifier exited with code {returncode} and printed nothing"}
    return {"status": "completed", "exitCode": returncode, "reason": None}


def conclude(returncode, output, evidence, reported=True, timed_out=None, known=(0, 1)):
    """The execution and the verdict of a verifier run that exits 0 when the claim holds and 1 when it does not or
    cannot be checked (jvmcontract verify, equivalence and prove; the Java verifier). `evidence` is what the runner
    read from the output to show a violation (counterexamples, changed cases, capability or boundary changes, new
    problem lines), and `reported` whether the verifier wrote its SARIF report. A violation needs both: an exit
    code of 1 with neither a reason it cannot be verified nor anything that shows the violation is output the
    runner cannot read, not a counterexample. Returns (execution, verdict), the verdict None unless completed."""
    execution = execution_status(returncode, output, timed_out, known)
    if execution["status"] != "completed":
        return execution, None
    if returncode == 0:
        return execution, "verified"
    if "cannot be verified" in output:
        return execution, "unverifiable"
    return violation(execution, evidence, reported)


def violation(execution, evidence, reported):
    """A completed run that reports a violation: one, when the runner has read what shows it and the verifier wrote
    its report; otherwise output the runner cannot read."""
    if evidence and reported:
        return execution, "violation"
    reason = ("the verifier reported a violation but wrote no SARIF report" if evidence else
              f"the verifier exited with code {execution['exitCode']}, but its output shows no violation the runner can "
              "read and no reason it cannot be verified")
    return {"status": "invalid-output", "exitCode": execution["exitCode"], "reason": reason}, None


def conclude_outcome(returncode, output, outcome, evidence, reported):
    """`conclude` for a run with `--json`, whose verdict is the outcome's: the exit code must agree with it (0 for
    verified, 1 otherwise), and a violation needs its witness and the report as before. `outcome` is None when the
    verifier's standard output is not one."""
    execution = execution_status(returncode, output)
    if execution["status"] != "completed":
        return execution, None
    if outcome is None:
        return {"status": "invalid-output", "exitCode": returncode,
                "reason": "the verifier's --json output is not an outcome the runner can read"}, None
    verdict = outcome.get("verdict")
    if verdict not in VERDICT_LABEL or (returncode == 0) != (verdict == "verified"):
        return {"status": "invalid-output", "exitCode": returncode,
                "reason": f"the verifier exited with code {returncode}, but its outcome's verdict is {verdict!r}"}, None
    if verdict == "violation":
        return violation(execution, evidence, reported)
    return execution, verdict


def no_verdict_label(execution):
    return f"⚠ No verdict: {execution['reason']}"


def expectation(result, expected):
    """Whether the result is the one the example expects: 'yes', 'no', or 'not-evaluable' when the verifier did not
    complete, so that there is no verdict to compare. The vacuity of a verdict is part of it."""
    if (result.get("execution") or {}).get("status") != "completed" or result.get("verdict") is None:
        return "not-evaluable"
    vacuous = bool((result.get("coverage") or {}).get("vacuous"))
    return "yes" if result["verdict"] == expected["verdict"] and vacuous == expected.get("vacuous", False) else "no"


# Running


def run(folder, example, out):
    """Applies the patch to a copy of the repo, runs the module's tests and the approach's verifier, and collects
    everything into the result dictionary. The approach-specific part is the runner; the rest is shared.

    The run is one attempt, in its own directory `out`: the claim is fingerprinted and written there (claim.json)
    before anything is built, the runner writes its evidence there and nowhere else, and the result ends with the
    claim, the attempt, the conclusion and the bundle of that evidence. main() publishes it once it is checked."""
    patch = (folder / example["change"]["patch"]).read_text()
    before, after = excerpts(patch, example["subject"]["file"], example["subject"].get("symbol"))
    p = plan(example)
    app, module = p["app"], p["module"]
    out = Path(out)
    # The patched copy is the attempt's own (out/copy): kept with its stage logs in a pipeline job, removed when the
    # run ends otherwise.
    tmp = out / "copy"
    with stages(out) as ran:
        try:
            for part in p["build"]["copies"]:
                shutil.copytree(REPO / part, tmp / part, ignore=IGNORE)
            # Inside a repository's tree too, git apply takes the patch's paths relative to the copy (it prefixes them
            # with the directory it runs in), so a copy kept in a work directory is patched like one in /tmp.
            stage("apply the patch", ["git", "apply", "-p1", "-"], input=patch, cwd=tmp, check=True)
            claim = claim_record(example, p, patch, REPO, tmp)
            (out / "claim.json").write_text(json.dumps(claim, indent=2, ensure_ascii=False) + "\n")
            started = datetime.datetime.now(datetime.timezone.utc)
            clock = time.monotonic()

            if app == "boxoffice":
                build = tmp / BUILD_ROOT
                tests = gradle(build, f":{module}:test", check=False, allow_empty=True)
                existing_tests = {"task": f":{module}:test", "passed": tests.returncode == 0,
                                  "failures": failures(build / module / "build/test-results/test")}
            else:
                existing_tests = tool_tests(app, tmp)

            result = {
                "verdict": None,
                "verdictLabel": None,
                "execution": None,
                "matchesExpected": None,
                "expectation": None,
                "existingTests": existing_tests,
                "before": before,
                "after": after,
                "casesTotal": None,
                "domain": None,
                "counterexamples": [],
                "purityViolations": [],
                "trustedCalls": [],
                "contractDiff": None,
                "proof": None,
                "problem": None,
                "statement": None,
                "trace": None,
                "statesExplored": None,
                "invariant": None,
                "property": None,
                "stateMachine": None,
                "coverage": None,
                "sarif": "result.sarif",
                "output": "verifier-output.txt",
            }
            RUNNERS[app][p["approach"]](out, example, tmp, module, result)
            finish(result, example)
            built = tmp / (f"{BUILD_ROOT}/{module}/build/classes/java/main" if app == "boxoffice" else f"{p['build']['root']}/build/main")
            baseline = BEFORE_CLASSES.get(module if app == "boxoffice" else app) if p["approach"] == "B9" else None
            attempt = attempt_record(claim, p, started, time.monotonic() - clock, result,
                                     built if built.is_dir() else None, baseline)
            attempt["stages"] = list(ran)
            kept = kept_workspace()
            attempt["workspace"] = out.relative_to(kept.parent).as_posix() if kept and out.is_relative_to(kept) else None
        finally:
            if not kept_workspace():
                shutil.rmtree(tmp, ignore_errors=True)
    result.update({"claim": claim, "attempt": attempt, "conclusion": conclusion_record(claim, attempt, result),
                   "bundle": bundle_record(out)})
    return result


def finish(result, example):
    """What every runner's result ends with: a runner that recorded no execution did not run the verifier, and a
    run without a verdict has the label that says why. A verdict that rests on no row or input the change reaches is
    vacuous, which the example must expect too."""
    if not result.get("execution"):
        result["execution"] = {"status": "tool-error", "exitCode": None, "reason": "the runner recorded no run of the verifier"}
        result["verdict"] = None
    if result["execution"]["status"] != "completed":
        result["verdict"] = None
    if result["verdict"] is None:
        result["verdictLabel"] = no_verdict_label(result["execution"])
    result["expectation"] = expectation(result, example["expected"])
    result["matchesExpected"] = result["expectation"] == "yes"


# Claims, attempts, conclusions and the evidence bundle. A run checks one claim: what is checked, over which scope,
# against which inputs, fingerprinted and frozen before anything runs. The run is one attempt at it: the engine,
# options and tools it ran with, the bytecode it built, where it ran, and how it ended. Changing the engine, a
# timeout or a tool is another attempt at the same claim; changing the inputs, the array bound or the assumptions
# is another claim, with another id. The conclusion is what the attempt established, refuted or left unresolved,
# per obligation. The bundle lists every file the attempt left as evidence with its hash, so a page can tell its
# evidence from another run's. All four sit next to the flat fields the pages are rendered from (open question 1
# of llm-dlc/loops/build-orchestration.md: the flat result stays until the user decides to retire it).

CLAIM_FORMAT = 1
CONCLUSION = {"verified": "established", "violation": "refuted", "unverifiable": "unresolved"}
# Files a run leaves as its evidence, besides result.json; a published bundle replaces every one of them.
EVIDENCE = re.compile(r"^(result\.sarif|verifier-output\.txt|statement(-\d+)?\.java)$")


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def tree_digest(base, parts, ignore=IGNORE):
    """The content of the files under `parts` of `base` as a run copies them (IGNORE applied, unless `ignore` is
    None: bytecode is all class files): a SHA-256 over every file's path and SHA-256, and the number of files. None
    when none of the parts exists or holds a file."""
    files = []
    for part in parts:
        top = Path(base) / part
        if not top.exists():
            continue
        for directory, dirs, names in os.walk(top):
            ignored = ignore(directory, dirs + names) if ignore else set()
            dirs[:] = sorted(d for d in dirs if d not in ignored)
            for name in sorted(n for n in names if n not in ignored):
                path = Path(directory) / name
                if path.is_file():
                    files.append((path.relative_to(base).as_posix(), file_digest(path)))
    if not files:
        return None
    return {"sha256": canonical_digest(sorted(files)), "files": len(files)}


def claim_record(example, p, patch, before, after):
    """The claim a run checks, frozen before it runs: the plan's statement of what is checked, its scope (the array
    bound and assumptions a proof is over), and the fingerprints of its inputs: the patch, the sources before and
    after it (the app and what the build copies, models, contracts and build files among them), and for D1 the
    model's files. Its id is the digest of all of it, so another input or scope is another claim."""
    scope = claim_scope(example, p)
    inputs = {"patch": hashlib.sha256(patch.encode()).hexdigest(),
              "before": tree_digest(before, p["build"]["copies"]), "after": tree_digest(after, p["build"]["copies"]),
              # Gradle resolves Box Office's libraries by the versions its build files (fingerprinted with the sources)
              # declare; the artifacts themselves are not fingerprinted. The javac apps depend on the JDK alone.
              "dependencies": "declared in the build files" if p["build"]["adapter"] == "gradle" else "the JDK"}
    if p["model"]:
        inputs["model"] = {f: file_digest(Path(after) / f)
                           for f in [p["model"]["spec"], *(c["cfg"] for c in p["model"]["configurations"])]}
    body = {"format": CLAIM_FORMAT, "example": example["id"], "statement": p["claim"], "scope": scope, "inputs": inputs}
    return {"id": canonical_digest(body)[:16], **body}


def claim_scope(example, p):
    """What a proof is over, besides its inputs: B9 and B11 the array bound, B9 the intended inputs."""
    scope = {}
    if p["approach"] in ("B9", "B11"):
        scope["maxArrayLength"] = example["approach"].get("maxArrayLength")  # None: the tool's default bound
    if p["approach"] == "B9":
        scope["intendedInputs"] = p["claim"].get("intendedInputs")
    return scope


SOURCES = {}  # tree_digest of the repo's own copies, per tuple of parts: one walk per render, not per example


def claim_changes(folder, example, claim, base=None):
    """What changed since the claim was frozen, as reasons, or an empty list when it is still the claim the current
    files make. The patched sources are the sources before the patch with the patch applied, and the model's files
    are among them, so comparing the patch and the sources before it covers both: nothing is copied or patched."""
    p = plan(example)
    if not p["executable"]:
        return [f"build.py no longer runs the example ({p['notExecuted']})"]
    if claim.get("format") != CLAIM_FORMAT:
        return [f"the claim is in format {claim.get('format')}, and build.py now writes format {CLAIM_FORMAT}"]
    reasons = []
    if claim.get("example") != example["id"]:
        reasons.append(f"the claim is of example {claim.get('example')}")
    statement = claim.get("statement") or {}
    changed = sorted(k for k in set(statement) | set(p["claim"]) if statement.get(k) != p["claim"].get(k))
    if changed:
        reasons.append("what is checked changed (" + ", ".join(f"`{k}`" for k in changed) + ")")
    scope = claim_scope(example, p)
    changed = sorted(k for k in set(claim.get("scope") or {}) | set(scope) if (claim.get("scope") or {}).get(k) != scope.get(k))
    if changed:
        reasons.append("the scope changed (" + ", ".join(f"`{k}`" for k in changed) + ")")
    inputs = claim.get("inputs") or {}
    patch = (folder / example["change"]["patch"]).read_text()
    if inputs.get("patch") != hashlib.sha256(patch.encode()).hexdigest():
        reasons.append("the patch changed")
    parts = tuple(p["build"]["copies"])
    if base is None:
        if parts not in SOURCES:
            SOURCES[parts] = tree_digest(REPO, parts)
        before = SOURCES[parts]
    else:
        before = tree_digest(base, parts)
    if inputs.get("before") != before:
        reasons.append("the sources the patch applies to changed (" + ", ".join(f"`{part}`" for part in parts) + ")")
    return reasons


def snapshot(folder, example, res):
    """Whether a recorded result is still the result of the current files: `state` is `current` (its claim is the one
    the current files make), `stale` (`reasons` says what changed), or `unknown` (recorded before runs fingerprinted
    their inputs). `evidence` lists why the files beside it are not the run's bundle, whatever the state."""
    evidence = bundle_problems(folder, res) if res.get("bundle") else []
    if not res.get("claim"):
        return {"state": "unknown", "reasons": [], "evidence": evidence}
    reasons = claim_changes(folder, example, res["claim"])
    return {"state": "stale" if reasons else "current", "reasons": reasons, "evidence": evidence}


IDENTITY = {}


def tool_version(command):
    """A tool's identity as it reports itself, or None when it cannot be asked."""
    try:
        proc = stage(f"version of {Path(str(command[0])).name}", command, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (proc.stdout + proc.stderr).strip()
    return text.splitlines()[0] if proc.returncode == 0 and text else None


def attempt_tools(p):
    """What the attempt ran with, by the tools its plan names: Java and javac, jvmcontract by the digest of its
    executable, JBMC and Gradle by their versions, TLC by the digest of its jar. Asked once per process."""
    names = ["java", *p["tools"]["required"], *p["tools"]["optional"]]
    out = {}
    for name in dict.fromkeys(names):
        if name not in IDENTITY:
            if name == "java":
                IDENTITY[name] = tool_version([java(), "-version"])
            elif name == "javac":
                javac_exe = str(Path(java()).parent / "javac") if os.environ.get("JAVA_HOME") else "javac"
                IDENTITY[name] = tool_version([javac_exe, "-version"])
            elif name == "jvmcontract":
                IDENTITY[name] = file_digest(jvmcontract())
            elif name == "jbmc":
                IDENTITY[name] = tool_version(["jbmc", "--version"])  # what jvmcontract runs
            elif name == "tlc":
                IDENTITY[name] = file_digest(os.environ.get("TLA2TOOLS_JAR") or str(Path.home() / "tools/tla2tools.jar"))
            elif name == "gradle":
                properties = REPO / BUILD_ROOT / "gradle/wrapper/gradle-wrapper.properties"
                found = re.search(r"distributionUrl=.*/(gradle-[^/]+)\.zip", properties.read_text()) if properties.is_file() else None
                IDENTITY[name] = found.group(1) if found else None
        out[name] = IDENTITY[name]
    return out


def exploration_record(result):
    """For a symbolic proof: the bounds it searched within, and whether the checker showed its exploration complete
    within them. A verified jvmcontract proof checks unwinding assertions (an unwinding bound reached is no proof),
    so it is complete within the array bound; a violation needs no completeness; anything else is unknown."""
    search = result.get("search") or next((q["search"] for q in result.get("properties") or [] if q.get("search")), None) or {}
    proofs = [result.get("proof")] + [q.get("proof") for q in result.get("properties") or []]
    complete = None
    if result.get("verdict") == "verified" and all(q and "with unwinding assertions" in q for q in proofs if q is not None) \
            and any(proofs):
        complete = True
    return {"unwind": search.get("unwind"), "maxArrayLength": search.get("maxArrayLength"), "complete": complete}


def attempt_record(claim, p, started, seconds, result, after_classes, before_classes):
    """One attempt at the claim: the engine and options, the tools, the bytecode it built from the claim's sources,
    the pipeline job it ran in (VERIFY_JOB_ID, VERIFY_SOURCE_COMMIT and VERIFY_WORKDIR, when it ran in one), when
    and how long, and how it ended."""
    job = {"jobId": os.environ.get("VERIFY_JOB_ID"), "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"),
           "workdir": os.environ.get("VERIFY_WORKDIR")}
    record = {"id": f"{started:%Y%m%dT%H%M%SZ}-{os.urandom(4).hex()}", "claim": claim["id"],
              "startedAt": started.isoformat(timespec="seconds"), "seconds": round(seconds, 1),
              "engine": p["engine"], "options": p["options"], "tools": attempt_tools(p),
              "bytecode": {"before": tree_digest(before_classes, ["."], None) if before_classes else None,
                           "after": tree_digest(after_classes, ["."], None) if after_classes else None},
              "pipeline": job if any(job.values()) else None, "execution": result["execution"]}
    if p["approach"] in ("B9", "B11") and p["app"] != "boxoffice":
        record["exploration"] = exploration_record(result)
    return record


def conclusion_record(claim, attempt, result):
    """What the attempt concluded about the claim: established, refuted or unresolved (None without a verdict), and
    the same for each obligation it checked: each property of a B11 target, each configuration of a D1 model, and
    each generated operator's contract as built."""
    status = CONCLUSION.get(result["verdict"]) if result["verdict"] else None
    obligations = []
    for i, q in enumerate(result.get("properties") or [], 1):
        obligations.append({"name": q.get("harness") or f"property-{i}", "statement": q["assert"],
                            "status": CONCLUSION.get(q["verdict"])})
    for c in result.get("configurations") or []:
        obligations.append({"name": c["label"], "statement": c["cfg"],
                            "status": CONCLUSION.get(c["verdict"]) if c.get("status") == "completed" else None})
    for m in result.get("modelContracts") or []:
        obligations.append({"name": m["symbol"], "statement": "the contract the operator is generated from, as built",
                            "status": "established" if m["connection"] == "verified" or m.get("allowed") else "refuted"})
    return {"claim": claim["id"], "attempt": attempt["id"], "status": status,
            "vacuous": bool((result.get("coverage") or {}).get("vacuous")), "expectation": result["expectation"],
            "obligations": obligations}


def referenced_files(result):
    """The evidence files the result names."""
    names = [result.get("sarif"), result.get("output"), result.get("statement")]
    names += [q.get("statement") for q in result.get("properties") or []]
    return sorted({n for n in names if n})


def bundle_record(out):
    """The attempt's evidence files in its directory, each with its SHA-256 and size."""
    return {"artifacts": [{"path": f.name, "sha256": file_digest(f), "bytes": f.stat().st_size}
                          for f in sorted(Path(out).iterdir()) if f.is_file() and EVIDENCE.match(f.name)]}


def bundle_problems(directory, result):
    """Why the evidence in `directory` is not the bundle the result lists, or an empty list: a file the result names
    that the bundle does not list, a listed file missing or changed, or an evidence file of another run beside it."""
    bundle = result.get("bundle")
    if not bundle:
        return ["the result lists no bundle"]
    listed = {a["path"]: a for a in bundle["artifacts"]}
    problems = [f"{name} is named by the result but not in its bundle" for name in referenced_files(result) if name not in listed]
    for name, artifact in sorted(listed.items()):
        digest = file_digest(Path(directory) / name)
        if digest is None:
            problems.append(f"{name} is missing")
        elif digest != artifact["sha256"]:
            problems.append(f"{name} is not the file the run left (its SHA-256 differs)")
    for f in sorted(Path(directory).iterdir()):
        if f.is_file() and EVIDENCE.match(f.name) and f.name not in listed:
            problems.append(f"{f.name} is not in the bundle: it comes from another run")
    return problems


def check_result(out, result):
    """The whole result validated before anything is published: the schema, then the bundle against the attempt's
    directory. Exits on the first problem, leaving the example's folder as it was."""
    validate(result, "result.schema.json", Path(out) / "result.json")
    problems = bundle_problems(out, result)
    if problems:
        sys.exit(f"{out}: the run's evidence is not its bundle: " + "; ".join(problems))


def attempt_directory(folder):
    """A new, empty directory for one attempt at an example, in the run's scratch directory."""
    out = scratch() / "attempts" / folder.name[:3]
    out.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="attempt-", dir=out))


def publish(folder, out, result):
    """Publishes a checked bundle into the example's folder: each listed file by an atomic rename, then every
    evidence file of an earlier run that the bundle does not list is removed, and result.json goes last. A run
    interrupted on the way leaves a result.json whose bundle the files do not match, which bundle_problems() shows."""
    listed = [a["path"] for a in result["bundle"]["artifacts"]]
    for name in listed:
        staged = folder / f".{name}.publishing"
        shutil.copyfile(Path(out) / name, staged)
        staged.replace(folder / name)
    for f in folder.iterdir():
        if f.is_file() and EVIDENCE.match(f.name) and f.name not in listed:
            f.unlink()
    staged = folder / ".result.json.publishing"
    staged.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    staged.replace(folder / "result.json")


def update_contracts(build, module, result):
    """For an intended change: regenerates the module's contracts and records the diff a reviewer would approve."""
    contract_dir = build / module / "src/contract"
    old = {f.name: f.read_text() for f in contract_dir.glob("*.contract")}
    gradle(build, f":{module}:updateContracts")
    result["contractDiff"] = "".join(
        "".join(difflib.unified_diff(
            old.get(f.name, "").splitlines(True), f.read_text().splitlines(True),
            f"a/{BUILD_ROOT}/{module}/src/contract/{f.name}",
            f"b/{BUILD_ROOT}/{module}/src/contract/{f.name}"))
        for f in sorted(contract_dir.glob("*.contract")))


def run_contracts(folder, example, tmp, module, result):
    """B8 and B10: the module's behavioural and capability contracts, verified by the Gradle build of the patched
    copy. The two share a verifier and a Gradle task; they differ in what the output lists."""
    build = tmp / BUILD_ROOT
    if example["change"]["behaviourChangeIntended"]:
        update_contracts(build, module, result)

    proc = gradle(build, f":{module}:verifyContracts", check=False)
    output = proc.stdout.replace(str(tmp) + "/", "")
    reported = write_evidence(folder, output, build / module / "build/reports/contracts/contracts.sarif", result)

    cases = cases_total(output)
    changes = capability_changes(output)
    found = counterexamples(output) + changes
    execution, verdict = conclude(proc.returncode, output, found + purity_violations(output), reported)
    result.update({
        "verdict": verdict,
        "execution": execution,
        "casesTotal": cases,
        "counterexamples": found,
        "purityViolations": purity_violations(output),
        "trustedCalls": trusted_calls(output),
    })
    if verdict is None:
        return
    if example["approach"]["id"] == "B10":
        m = re.search(r"\((\d+) classes, (\d+) methods, (\d+) capability uses, (\d+) libraries\)", output)
        result["domain"] = f"{m.group(1)} classes, {m.group(2)} methods" if m else None
        result["verdictLabel"] = {
            "violation": f"{VERDICT_LABEL[verdict]}: {len(changes)} capability change{'s' if len(changes) != 1 else ''}",
            "verified": f"{VERDICT_LABEL[verdict]}: capabilities unchanged",
            "unverifiable": VERDICT_LABEL[verdict],
        }[verdict]
        return
    result["verdictLabel"] = {
        "violation": f"{VERDICT_LABEL[verdict]}: {len(result['counterexamples'])} of {cases} cases changed",
        "verified": f"{VERDICT_LABEL[verdict]}: all {cases} cases match",
        "unverifiable": VERDICT_LABEL[verdict],
    }[verdict]


def run_boundaries(folder, example, tmp, module, result):
    """B12 on a Box Office module: the patched copy compiled by Gradle, then `jvmcontract verify` over the module's
    contracts directory, where the boundary contract lives. The verifier is the Rust tool, not the Gradle build's.
    When the change was intended, the contract is regenerated first and the diff recorded; a `!` line that the
    regenerated contract has and the old one did not is then the violation, since the reviewer approves the diff."""
    build = tmp / BUILD_ROOT
    gradle(build, f":{module}:compileJava")
    classes = build / module / "build/classes/java/main"
    resources = build / module / "src/main/resources"
    classpath = gradle_runtime_classpath(build, module)
    contracts = build / module / "src/contract"
    report = build / module / "build/reports/contracts"
    anchor = ["--sources", str(build / module / "src/main/java"), "--base", str(tmp), "--report", str(report)]
    if example["change"]["behaviourChangeIntended"]:
        old = {f.name: f.read_text() for f in contracts.glob("*.contract")}
        proc = stage("jvmcontract update (boundaries)", [jvmcontract(), "update", "--contracts", str(contracts),
                     "--classes", str(classes), "--classpath", classpath, "--resources", str(resources),
                     "--module", module, "--add", "boundaries"])
        if proc.returncode != 0:
            sys.exit(f"jvmcontract update failed:\n{proc.stdout}{proc.stderr}")
        result["contractDiff"] = "".join(
            "".join(difflib.unified_diff(
                old.get(f.name, "").splitlines(True), f.read_text().splitlines(True),
                f"a/{BUILD_ROOT}/{module}/src/contract/{f.name}", f"b/{BUILD_ROOT}/{module}/src/contract/{f.name}"))
            for f in sorted(contracts.glob("*.contract")))
        before = problem_lines(old.get("boundaries.contract", ""))
        new_problems = [p for p in problem_lines((contracts / "boundaries.contract").read_text()) if p not in before]
    else:
        new_problems = []
    proc = stage("jvmcontract verify (boundaries)", [jvmcontract(), "verify", "--contracts", str(contracts),
                 "--classes", str(classes), "--classpath", classpath, "--resources", str(resources),
                 "--module", module, *anchor])
    output = (proc.stdout + proc.stderr).replace(str(tmp) + "/", "")
    if new_problems:
        output += "New `!` lines in the regenerated contract:\n" + "".join(f"  added {p}\n" for p in new_problems)
    reported = write_evidence(folder, output, report / "contracts.sarif", result)
    changes = boundary_changes(output)
    execution, verdict = conclude(proc.returncode, output, changes + new_problems, reported)
    result["execution"] = execution
    if verdict is None:
        result.update({"verdict": None, "counterexamples": changes, "newProblems": new_problems})
        return
    # A `!` line the regenerated contract adds is a violation the reviewer would approve with the diff.
    if new_problems and verdict == "verified":
        verdict = "violation"
    m = re.search(r"\((\d+) beans, (\d+) entry points, (\d+) advised methods, (\d+) configuration keys, (\d+) wire types, "
                  r"(?:(\d+) stored types, )?(\d+) problems\)", output)
    result.update({
        "verdict": verdict,
        "counterexamples": changes,
        "newProblems": new_problems,
        "domain": (f"{m.group(1)} beans, {m.group(2)} entry points, {m.group(3)} advised methods, "
                   f"{m.group(4)} configuration keys, {m.group(5)} wire types, "
                   + (f"{m.group(6)} stored types, " if m.group(6) else "")
                   + f"{m.group(7)} problems") if m else None,
        "verdictLabel": {
            "violation": (f"{VERDICT_LABEL[verdict]}: {len(new_problems)} new problem{'s' if len(new_problems) != 1 else ''}"
                          if new_problems else
                          f"{VERDICT_LABEL[verdict]}: {len(changes)} boundary change{'s' if len(changes) != 1 else ''}"),
            "verified": f"{VERDICT_LABEL[verdict]}: boundaries unchanged",
            "unverifiable": VERDICT_LABEL[verdict],
        }[verdict],
    })


def gradle_runtime_classpath(build, module):
    """The module's runtime class path as Gradle resolves it, through the build's `printRuntimeClasspath` task: the
    dependency jars carry the configuration metadata that declares the framework's keys, and the sibling modules'
    classes are followed for wire types and configuration keys."""
    proc = gradle(build, f":{module}:printRuntimeClasspath")
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    return lines[-1].strip() if lines else ""


def problem_lines(contract):
    """The `!` lines of a boundary contract, each with its block: `wire a.B: ! ...` or `a.B: member: ! ...`."""
    found = []
    block = member = None
    for line in contract.splitlines():
        if not line.strip() or line.startswith("#") or line.startswith(("kind:", "module:")):
            continue
        if line.startswith("    "):
            if line.strip().startswith("! "):
                found.append(f"{block}: {member}: {line.strip()}")
        elif line.startswith("  "):
            member = line.strip()
            if member.startswith("! "):
                found.append(f"{block}: {member}")
        else:
            block = line.split(":", 1)[0]
    return found


def run_equivalence(folder, example, tmp, module, result):
    """B9: the old and new bytecode of one method, proved equivalent (outside the intended inputs) by JBMC."""
    build = tmp / BUILD_ROOT
    gradle(build, f":{module}:compileJava")
    after = build / module / "build/classes/java/main"
    work = tmp / "equivalence"
    report = tmp / "report"
    command = [java(), "-cp", verifier_jar(), "net.terminalvalue.contracts.Main", "equivalence",
               "--before", str(before_classes(module)), "--after", str(after),
               "--target", example["subject"]["symbol"],
               "--work", str(work), "--report", str(report), "--base", str(tmp),
               "--sources", str(build / module / "src/main/java")]
    intended = example["change"].get("intendedInputs")
    if intended:
        command += ["--unchanged-unless", intended]
    proc = stage("the Java verifier's equivalence proof", command)
    output = (proc.stdout + proc.stderr).replace(str(tmp) + "/", "")
    reported = write_evidence(folder, output, report / "equivalence.sarif", result)
    statement = work / "harness/EquivalenceHarness.java"
    if statement.exists():
        shutil.copy(statement, folder / "statement.java")
        result["statement"] = "statement.java"
    else:
        (folder / "statement.java").unlink(missing_ok=True)  # an earlier run's statement is not this run's

    found = counterexamples(output)
    execution, verdict = conclude(proc.returncode, output, found, reported)
    m = re.search(r"domain (.+?)\)$", output, re.M) or re.search(r"over (.+?) in [\d.]+ s", output)
    proof = (re.search(r"^  \((.*)\)$", output, re.M) or re.search(r"\(((?:JBMC|jvmcontract's own checker) .*)\)$", output, re.M)
             or re.search(r"\((its bytecode .*nothing to prove)\)$", output, re.M))
    result.update({
        "verdict": verdict,
        "execution": execution,
        "domain": m.group(1) if m else None,
        "counterexamples": found,
        "proof": proof.group(1) if proof else None,
        "problem": problem(output),
    })
    if verdict is None:
        return
    # The Java verifier replays its witness on the JVM, and says so on its proof line.
    if verdict == "violation" and "replayed on the JVM" in (result["proof"] or ""):
        result["replay"] = {"by": "jvm", "reproduced": True}
    result["verdictLabel"] = {
        "violation": f"{VERDICT_LABEL[verdict]}: counterexample found",
        "verified": f"{VERDICT_LABEL[verdict]}: equivalent on every input" + (" outside the declared change" if intended else ""),
        "unverifiable": VERDICT_LABEL[verdict],
    }[verdict]


SPEC = "spec"  # the TLA+ model, inside BUILD_ROOT
CONTRACT_FILE = "ticketing-domain/src/contract/OrderLifecycle.decide.contract"
BOX_OFFICE_KERNEL = "net.terminalvalue.boxoffice.ticketing.domain.OrderLifecycle#decide"  # the rule the model's state machine is generated from

# The Java operation each TLA+ action models, for the trace.
ACTIONS = {
    "Initial predicate": "the initial state",
    "Hold": "`HoldService.hold`: a customer holds seats",
    "PlaceOrder": "`OrderService.place`: an order is placed and a charge is queued",
    "Cancel": "`OrderService.cancel`",
    "RelayCommand": "`OutboxRelay` (ticketing) publishes to `payments.commands`",
    "HandleCommand": "`PaymentCommandHandler.handle`: the payment service charges or refunds",
    "RelayEvent": "`OutboxRelay` (payments) publishes to `payments.events`",
    "HandleEvent": "`PaymentEventHandler.handle`: ticketing applies the payment outcome",
    "Sweep": "`HoldService.releaseExpiredHolds`",
    "Tick": "the clock advances",
}

INVARIANTS = {
    "NoDoubleSale": "two confirmed orders never share a seat",
    "ConfirmedOrdersOwnTheirSeats": "a confirmed order owns every seat it was placed for",
    "SoldSeatsHaveConfirmedOrders": "a sold seat belongs to a confirmed order",
    "NoMoneyStranded": "captured money is held for a confirmed order, is being refunded, or its capture event is still on its way",
    "NothingDeadLettered": "no record is dead-lettered",
    "AgreementAtQuiescence": "when nothing is in flight, both services agree on every order",
    "TypeOK": "every variable has a value of its type",
}


def run_tlc(folder, example, tmp, module, result):
    """D1: the TLA+ model of the services, checked by TLC. The state machine in the model is generated from the
    behavioural contract of the patched code, regenerated from its classes on every run, so a change to
    OrderLifecycle reaches the model whether or not it was meant to; a change to the contract that was not meant
    makes the verdict a violation whatever TLC found."""
    build = tmp / BUILD_ROOT
    intended = example["change"]["behaviourChangeIntended"]
    baseline = (build / CONTRACT_FILE).read_text()
    update_contracts(build, "ticketing-domain", result)
    candidate = (build / CONTRACT_FILE).read_text()
    connection = model_contract(BOX_OFFICE_KERNEL, CONTRACT_FILE, f"{SPEC}/OrderLifecycleContract.tla", baseline, candidate, intended)
    result["modelContracts"] = [connection]
    if not intended:
        # Only the operator's contract is the model's concern; any other the regeneration rewrote is left out.
        result["contractDiff"] = contract_diff(f"{BUILD_ROOT}/{CONTRACT_FILE}", baseline, candidate) if not connection["allowed"] else None
    spec = build / SPEC
    stage("contract to TLA+", [sys.executable, str(EXAMPLES / "tools/tla/contract_to_tla.py"),
                               str(build / CONTRACT_FILE), str(spec / "OrderLifecycleContract.tla")], check=True)
    library = EXAMPLES / "tools/tla/standard-modules"
    timeout = 1800
    try:
        # One worker, so that the trace TLC reports is the same on every run.
        proc = stage("TLC on BoxOffice.tla", tlc(library) + ["-workers", "1", "-deadlock", "-cleanup", "BoxOffice.tla"],
                     cwd=spec, timeout=timeout)
        raw, returncode, timed_out = proc.stdout + proc.stderr, proc.returncode, None
    except subprocess.TimeoutExpired as e:
        raw = ((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")) \
            + f"\nError: TLC did not finish within {timeout // 60} minutes"
        returncode, timed_out = None, timeout
    output = "\n".join(l for l in raw.replace(str(tmp) + "/", "").replace(str(REPO) + "/", "").splitlines() if not l.startswith("Progress("))
    (folder / "verifier-output.txt").write_text(output + "\n")

    violated = re.search(r"^Error: Invariant (\w+) is violated", output, re.M)
    states = re.search(r"(\d+) states generated, (\d+) distinct states found", output)
    depth = re.search(r"depth of the complete state graph search is (\d+)", output)
    seconds = re.search(r"Finished in (\d+)s", output)
    trace = parse_trace(output) if violated and "The behavior up to this point is:" in output else None
    execution, verdict = tlc_conclusion(returncode, output, timed_out, "No error has been found" in output, violated, trace)
    if verdict is None:
        (folder / "result.sarif").unlink(missing_ok=True)
        result.update({"verdict": None, "execution": execution, "problem": execution["reason"], "sarif": None})
        return
    model = ", ".join(re.findall(r"^\s+(\w+ = .+)$", (spec / "BoxOffice.cfg").read_text(), re.M))
    sarif_line = result["after"]["startLine"]
    findings = []
    if verdict != "verified":
        message = (f"Invariant {violated.group(1)} of {SPEC}/BoxOffice.tla is violated after {len(trace)} steps"
                   if violated else "TLC produced no verdict: " + output.strip().splitlines()[-1])
        findings.append({"ruleId": "invariant-violated" if violated else "unverifiable", "level": "error",
                         "message": {"text": message},
                         "locations": [{"physicalLocation": {"artifactLocation": {"uri": example["subject"]["file"]},
                                                             "region": {"startLine": sarif_line}}}]})
    findings += unauthorized_findings(result, example)
    sarif = {"version": "2.1.0", "$schema": "https://json.schemastore.org/sarif-2.1.0.json", "runs": [{
        "tool": {"driver": {"name": "tlc", "rules": [
            {"id": "invariant-violated", "shortDescription": {"text": "TLC found a behaviour of the model that violates an invariant."}},
            {"id": "unverifiable", "shortDescription": {"text": "TLC could not check the model."}},
            CONTRACT_CHANGED_RULE]}},
        "results": findings}]}
    (folder / "result.sarif").write_text(json.dumps(sarif, indent=2, ensure_ascii=False) + "\n")

    result.update({
        "verdict": verdict,
        "execution": execution,
        "trace": trace,
        "statesExplored": int(states.group(2)) if states else None,
        "invariant": violated.group(1) if violated else None,
        "domain": model,
        "proof": (f"TLC {tlc_version(output)} explored {int(states.group(2)):,} distinct states"
                  f"{' to depth ' + depth.group(1) if depth else ''}"
                  f"{' in ' + seconds.group(1) + ' s' if seconds else ''}, for the model {model}") if states else None,
        "problem": None if verdict != "unverifiable" else output.strip().splitlines()[-1],
    })
    result["verdict"], result["verdictLabel"] = model_verdict(result, verdict, {
        "violation": f"{VERDICT_LABEL[verdict]}: {violated.group(1) if violated else ''}, {len(trace or [])}-step trace",
        "verified": f"{VERDICT_LABEL[verdict]}: all invariants hold in {int(states.group(2)):,} states" if states else VERDICT_LABEL[verdict],
        "unverifiable": VERDICT_LABEL[verdict],
    }[verdict])


def tlc_conclusion(returncode, output, timed_out, verified, violated, trace):
    """The execution and the verdict of a TLC run, from TLC's own report: no error found, or a violation with the
    behaviour that shows it. TLC has no verdict of "cannot be checked": a run that says neither was killed (by the
    runner's timeout, by a signal, as the tool reports either), or failed (a parse error, a Java exception, running out
    of memory). A violation without a trace the runner can read is output it cannot read, not a counterexample.
    `returncode` is None when the runner's own timeout stopped TLC, or when the run went through the tool, which
    reports the end of TLC in its output."""
    if timed_out is not None:
        return {"status": "timed-out", "exitCode": None, "reason": f"TLC did not finish within {timed_out} s"}, None
    if returncode is not None and returncode < 0:
        return {"status": "killed", "exitCode": returncode, "reason": f"TLC was killed by signal {-returncode}"}, None
    killed = re.search(r"^Error: \S+ was killed by signal (\d+)$", output, re.M)
    if killed:
        return {"status": "killed", "exitCode": returncode, "reason": f"TLC was killed by signal {killed.group(1)}"}, None
    late = re.search(r"^Error: \S+ did not finish within (\d+) s$", output, re.M)
    if late:
        return {"status": "timed-out", "exitCode": returncode, "reason": f"TLC did not finish within {late.group(1)} s"}, None
    execution = {"status": "completed", "exitCode": returncode, "reason": None}
    if verified and not violated:
        return execution, "verified"
    if violated and trace:
        return execution, "violation"
    if violated:
        return {"status": "invalid-output", "exitCode": returncode,
                "reason": "TLC reported a violation, but no behaviour the runner can read shows it"}, None
    line = last_line(output)
    return {"status": "tool-error", "exitCode": returncode,
            "reason": "TLC produced no verdict" + (f": {line}" if line else ", printing nothing")}, None


def tlc(library):
    """The TLC command line. TLA-Library makes it parse the committed standard modules, not temporary copies."""
    jar = os.environ.get("TLA2TOOLS_JAR") or str(Path.home() / "tools/tla2tools.jar")
    if Path(jar).exists():
        return [java(), "-XX:+UseParallelGC", f"-DTLA-Library={library}", "-cp", jar, "tlc2.TLC"]
    if shutil.which("tlc"):
        return ["tlc"]
    sys.exit("TLC not found: install tla2tools.jar in ~/tools or set TLA2TOOLS_JAR")


def tlc_version(output):
    m = re.search(r"TLC2 Version (\S+)", output)
    return m.group(1) if m else ""


def parse_trace(output):
    """TLC's counterexample as a list of steps, each with the action and the variables it changed."""
    body = output.split("The behavior up to this point is:", 1)[1]
    steps = []
    previous = {}
    parts = re.split(r"^State (\d+): <([^>]*)>\n", body, flags=re.M)
    for i in range(1, len(parts) - 2, 3):
        number, header, text = parts[i], parts[i + 1], parts[i + 2]
        action = header.split(" line ")[0].strip()
        values = {}
        for assignment in re.split(r"^/\\ ", text.strip().split("\n\n")[0], flags=re.M):
            if "=" not in assignment:
                continue
            name, value = assignment.split(" = ", 1)
            values[name.strip()] = re.sub(r"\s+", " ", value).strip()
        changed = {k: v for k, v in values.items() if previous.get(k) != v}
        steps.append({"step": int(number), "action": action, "changes": changed})
        previous = values
    return steps


# The javac apps (Quorum, Crosscut, Mica), verified by the Rust tool in lib/.


def jvmcontract():
    """The jvmcontract executable: $JVMCONTRACT, or the release build of lib/, built with cargo if missing."""
    if "jvmcontract" in BEFORE_CLASSES:
        return BEFORE_CLASSES["jvmcontract"]
    exe = Path(os.environ["JVMCONTRACT"]) if os.environ.get("JVMCONTRACT") else REPO / "lib/target/release/jvmcontract"
    if not os.environ.get("JVMCONTRACT"):
        cargo = shutil.which("cargo") or str(Path.home() / ".cargo/bin/cargo")
        if Path(cargo).exists():
            proc = stage("cargo build jvmcontract", [cargo, "build", "--release", "--manifest-path", str(REPO / "lib/Cargo.toml")])
            if proc.returncode != 0:
                sys.exit(f"cargo build failed:\n{proc.stderr}")
    if not exe.exists():
        sys.exit(f"jvmcontract not found at {exe}: build lib/ with cargo, or set JVMCONTRACT")
    BEFORE_CLASSES["jvmcontract"] = str(exe)
    return str(exe)


def javac(out, sources, classpath=None, name="javac"):
    out.mkdir(parents=True, exist_ok=True)
    command = [str(Path(java()).parent / "javac") if os.environ.get("JAVA_HOME") else "javac",
               "-parameters", "-g", "-proc:none", "-d", str(out)]
    if classpath:
        command += ["-cp", str(classpath)]
    proc = stage(name, command + [str(s) for s in sources])
    if proc.returncode != 0:
        sys.exit(f"javac failed:\n{proc.stderr}")


def tool_compile(app, root, tests=True, which="patched"):
    """Compiles the app's module under root (a copy of the repo) into its build dir: the main classes, and the test
    classes unless `tests` is False (the unpatched baseline a regression proof compares with needs none). Returns the
    main and test directories (test None when not compiled)."""
    build = root / TOOL_APPS[app]["root"]
    main, test = build / "build/main", build / "build/test"
    javac(main, sorted((build / "src/main/java").rglob("*.java")), name=f"javac {which} {app} main")
    if not tests:
        return main, None
    javac(test, sorted((build / "src/test/java").rglob("*.java")), classpath=main, name=f"javac {which} {app} tests")
    return main, test


def tool_tests(app, root):
    """Runs the module's tests (plain static methods, no framework) and reports which failed."""
    main, test = tool_compile(app, root)
    runner = TOOL_APPS[app]["tests"]
    proc = stage(f"the {app} tests", [java(), "-ea", "-cp", f"{main}{os.pathsep}{test}", runner])
    failing = sorted(re.findall(r"^FAIL (\S+):", proc.stdout, re.M))
    if proc.returncode != 0 and not failing:
        sys.exit(f"the tests did not run:\n{proc.stdout}\n{proc.stderr}")
    return {"task": f"java -ea {runner}", "passed": proc.returncode == 0, "failures": failing}


def tool_before_classes(app):
    """The module's classes compiled from the unpatched repo, built once per run."""
    if app not in BEFORE_CLASSES:
        root = scratch() / f"before-{app}"
        part = TOOL_APPS[app]["root"]
        shutil.copytree(REPO / part, root / part, ignore=IGNORE)
        BEFORE_CLASSES[app] = tool_compile(app, root, tests=False, which="unpatched")[0]
    return BEFORE_CLASSES[app]


def tool(app, root, *args, anchored=True, setup=True):
    """Runs jvmcontract on the patched copy, with findings anchored relative to the copy's root. A step that sets
    the run up (`update`, `tla`) stops the runner when the tool fails or is killed (an exit code other than 0 or 1:
    `update` exits 1 for what it found, as `verify` does); the run that gives the verdict (`setup=False`)
    returns whatever happened, for `conclude` to decide how it ended."""
    build = root / TOOL_APPS[app]["root"]
    anchor = ["--sources", str(build / "src/main/java"), "--base", str(root)] if anchored else []
    proc = stage(f"jvmcontract {args[0]}", [jvmcontract(), *args, *anchor], cwd=build)
    output = (proc.stdout + proc.stderr).replace(str(root) + "/", "")
    if setup and proc.returncode not in (0, 1):
        sys.exit(f"jvmcontract {args[0]} failed with exit code {proc.returncode}:\n{output}")
    return proc, output


def tool_update_contracts(app, root, result):
    """For an intended change: regenerates the module's contracts and records the diff a reviewer would approve."""
    part = TOOL_APPS[app]["root"]
    build = root / part
    contract_dir = build / "src/contract"
    old = {f.name: f.read_text() for f in contract_dir.glob("*.contract")}
    tool(app, root, "update", "--contracts", "src/contract", "--classes", str(build / "build/main"), "--module", app)
    result["contractDiff"] = "".join(
        "".join(difflib.unified_diff(
            old.get(f.name, "").splitlines(True), f.read_text().splitlines(True),
            f"a/{part}/src/contract/{f.name}", f"b/{part}/src/contract/{f.name}"))
        for f in sorted(contract_dir.glob("*.contract")))


def tool_traces(app, root, traces):
    """Records the runs a trace configuration checks: the module's trace writer, a test-side main class, run on the
    patched classes, writes the recorded runs as a TLA+ module the trace specification extends."""
    build = root / TOOL_APPS[app]["root"]
    main, test = build / "build/main", build / "build/test"
    proc = stage("the trace writer", [java(), "-cp", f"{main}{os.pathsep}{test}", traces["writer"]])
    if proc.returncode != 0:
        sys.exit(f"the trace writer {traces['writer']} failed:\n{proc.stdout}\n{proc.stderr}")
    (build / traces["module"]).write_text(proc.stdout)


def tool_state_machine(app, root, symbol):
    """The state machine the patched code implements, as Mermaid, when the symbol's contract is one."""
    build = root / TOOL_APPS[app]["root"]
    proc = stage(f"jvmcontract derive {symbol.rsplit('.', 1)[-1]}", [jvmcontract(), "derive", symbol, "--classes", str(build / "build/main")])
    if proc.returncode != 0:
        return None
    contract = build / "build/derived.contract"
    contract.write_text(proc.stdout)
    proc = stage("jvmcontract statemachine", [jvmcontract(), "statemachine", str(contract), "--format", "mermaid"])
    return proc.stdout if proc.returncode == 0 else None


def run_tool_contracts(folder, example, root, module, result):
    """B8 and B10 on a javac app: `jvmcontract verify` over the module's contracts directory."""
    app = app_of(example)
    build = root / TOOL_APPS[app]["root"]
    if example["change"]["behaviourChangeIntended"]:
        tool_update_contracts(app, root, result)
    proc, output = tool(app, root, "verify", "--contracts", "src/contract", "--classes", str(build / "build/main"),
                        "--module", module, "--report", str(build / "build/reports"), setup=False)
    reported = write_evidence(folder, output, build / "build/reports/contracts.sarif", result)
    cases = cases_total(output, example["subject"]["symbol"])
    changes = capability_changes(output)
    found = counterexamples(output) + changes
    execution, verdict = conclude(proc.returncode, output, found + purity_violations(output), reported)
    result.update({
        "verdict": verdict,
        "execution": execution,
        "casesTotal": cases,
        "counterexamples": found,
        "purityViolations": purity_violations(output),
        "trustedCalls": trusted_calls(output),
    })
    if verdict is None:
        return
    if example["approach"]["id"] == "B10":
        m = re.search(r"\((\d+) classes, (\d+) methods, (\d+) capability uses, (\d+) libraries\)", output)
        result["domain"] = f"{m.group(1)} classes, {m.group(2)} methods" if m else None
        result["verdictLabel"] = {
            "violation": f"{VERDICT_LABEL[verdict]}: {len(changes)} capability change{'s' if len(changes) != 1 else ''}",
            "verified": f"{VERDICT_LABEL[verdict]}: capabilities unchanged",
            "unverifiable": VERDICT_LABEL[verdict],
        }[verdict]
        return
    result["stateMachine"] = tool_state_machine(app, root, example["subject"]["symbol"])
    result["verdictLabel"] = {
        "violation": f"{VERDICT_LABEL[verdict]}: {len(result['counterexamples'])} of {cases} cases changed",
        "verified": f"{VERDICT_LABEL[verdict]}: all {cases} cases match",
        "unverifiable": VERDICT_LABEL[verdict],
    }[verdict]


def finish_symbolic(folder, result, statement, fields, verdict_labels):
    """What B9 and B11 share: the statement, the domain, the proof line, the problem, the vacuity and the verdict
    label. `statement` is the harness the verifier wrote, `fields` the rest as the verifier reported them."""
    if statement is not None and statement.exists():
        shutil.copy(statement, folder / "statement.java")
        result["statement"] = "statement.java"
    else:
        (folder / "statement.java").unlink(missing_ok=True)  # an earlier run's statement is not this run's
    result.update({"domain": fields["domain"], "proof": fields["proof"], "problem": fields["problem"]})
    if result["verdict"] is None:
        return
    result["verdictLabel"] = verdict_labels[result["verdict"]]
    # A verified statement that skips every input in the domain before the calls (a scope every input satisfies, a
    # bound on the arrays below what the scope asks, a constructor that rejects every input) is vacuous: the tool
    # says so, and the example must expect it.
    if fields["vacuous"]:
        result["coverage"] = {"vacuous": True, "reason": fields["vacuous"]}
        result["verdictLabel"] = f"{VERDICT_LABEL[result['verdict']]}, vacuously: no input in the domain reaches the calls"


def without_root(value, root):
    """`value` with the patched copy's root taken out of every string in it, as `tool()` does for text."""
    if isinstance(value, str):
        return value.replace(str(root) + "/", "")
    if isinstance(value, list):
        return [without_root(v, root) for v in value]
    if isinstance(value, dict):
        return {k: without_root(v, root) for k, v in value.items()}
    return value


def is_outcome(value):
    return isinstance(value, dict) and isinstance(value.get("output"), str)


def json_outcome(proc, root):
    """The library's outcome from a run with `--json`, with the patched copy's root taken out, or None when the
    standard output is not one."""
    try:
        outcome = json.loads(proc.stdout)
    except ValueError:
        return None
    return without_root(outcome, root) if is_outcome(outcome) else None


def json_outcomes(proc, root):
    """The library's outcomes from `prove --json`, one per property of the target in the order the properties file
    declares them, with the patched copy's root taken out; None when the standard output is not such a list."""
    try:
        outcomes = json.loads(proc.stdout)
    except ValueError:
        return None
    if not isinstance(outcomes, list) or not outcomes or not all(map(is_outcome, outcomes)):
        return None
    return without_root(outcomes, root)


def typed_call(call, classes):
    """A call from the outcome as the result keeps it, with the SHA-256 of the class file it names in the classes
    the run built (`classes` by `after` and `before`), or None when that file is not there."""
    root = classes.get(call["classes"])
    path = Path(root) / call["class_file"] if root else None
    return {"class": call["class"], "classFile": call["class_file"],
            "classFileSha256": file_digest(path) if path and path.is_file() else None, "classes": call["classes"],
            "method": call["method"], "descriptor": call["descriptor"], "static": call["static"],
            **({"receiver": call["receiver"]} if call.get("receiver") else {}), "arguments": call["arguments"]}


def witness_record(c, classes):
    """The counterexample as data, from the outcome's typed fields: the inputs (and those found before shrinking),
    the patched version's call, and for a regression proof the previous version's. None from a tool that gives
    no typed fields."""
    if not c.get("call") or "inputs" not in c:
        return None
    return {"inputs": c["inputs"], **({"foundInputs": c["found_inputs"]} if c.get("found_inputs") else {}),
            "call": typed_call(c["call"], classes),
            **({"previousCall": typed_call(c["previous_call"], classes)} if c.get("previous_call") else {})}


def equivalence_counterexamples(outcome, classes=None):
    """The outcome's witness as the result's counterexample: the input, what the version before did (`contract`)
    and what the patched one does (`actual`), with the input the checker found before it was shrunk, and the
    witness as data (`witness`) with the class files' digests from `classes`."""
    c = (outcome or {}).get("counterexample")
    if not c:
        return []
    witness = witness_record(c, classes or {})
    return [{"input": c["input"], "contract": c["before"], "actual": c["after"],
             **({"found": c["found"]} if c.get("found") else {}), "shrinkRuns": c.get("shrink_runs", 0),
             **({"witness": witness} if witness else {})}]


def search_record(outcome):
    """The checker run a verdict comes from, from the outcome's `search`: the engine, the checker, its settings and
    time, the input range the verdict was found in, and the own checker's numbers. None when no checker ran."""
    s = (outcome or {}).get("search")
    if not s:
        return None
    record = {"engine": s["engine"], "checker": s["checker"], "seconds": round(s["seconds"], 3), "properties": s["properties"],
              "unwind": s["unwind"], "maxArrayLength": s["max_array_length"], "stage": s.get("stage")}
    if outcome.get("shared"):
        record["sharedCallees"] = outcome["shared"]
    if s.get("fallback"):
        record["fallback"] = s["fallback"]
    if s.get("native"):
        record["native"] = {re.sub(r"_(\w)", lambda m: m.group(1).upper(), k): v for k, v in s["native"].items()}
    return record


def run_tool_equivalence(folder, example, root, module, result):
    """B9 on a javac app: `jvmcontract equivalence` between the unpatched and the patched classes."""
    app = app_of(example)
    build = root / TOOL_APPS[app]["root"]
    work = build / "build/equivalence"
    classes = {"before": tool_before_classes(app), "after": build / "build/main"}
    command = ["equivalence", "--before", str(classes["before"]), "--after", str(classes["after"]),
               "--target", example["subject"]["symbol"], "--work", str(work), "--report", str(build / "build/reports")]
    intended = example["change"].get("intendedInputs")
    if intended:
        command += ["--unchanged-unless", intended]
    if example["change"].get("previousSymbol"):
        command += ["--before-target", example["change"]["previousSymbol"]]
    if example["change"].get("previousArguments"):
        command += ["--before-arguments", example["change"]["previousArguments"]]
    if example["change"].get("resultsAgreeWhen"):
        command += ["--results-agree-when", example["change"]["resultsAgreeWhen"]]
    command += proof_options(example)
    proc, output = tool(app, root, *command, "--json", setup=False)
    outcome = json_outcome(proc, root)
    if outcome is not None:  # the console output is the outcome's own, with what went to standard error after it
        output = outcome["output"] + proc.stderr.replace(str(root) + "/", "")
    reported = write_evidence(folder, output, build / "build/reports/equivalence.sarif", result)
    result["counterexamples"] = equivalence_counterexamples(outcome, classes)
    result["execution"], result["verdict"] = conclude_outcome(proc.returncode, output, outcome, result["counterexamples"], reported)
    completed = result["verdict"] is not None
    result["search"] = search_record(outcome) if completed else None
    replay = (outcome or {}).get("replay")
    result["replay"] = {"by": replay["by"], "reproduced": replay["reproduced"]} if completed and replay else None
    statement = outcome.get("statement") if outcome else None
    fields = {k: (outcome or {}).get(k) for k in ("domain", "proof", "problem", "vacuous")}
    finish_symbolic(folder, result, root / statement if statement else None, fields, {
        "violation": f"{VERDICT_LABEL['violation']}: counterexample found",
        "verified": f"{VERDICT_LABEL['verified']}: equivalent on every input" + (" outside the declared change" if intended else ""),
        "unverifiable": VERDICT_LABEL["unverifiable"],
    })


def property_headline(verdicts):
    """The verdict over a target's properties, every one of them required: a violation when any is refuted (the
    others, unresolved ones included, stay in the result beside it), verified only when every one is, and
    unverifiable otherwise. None when a verdict is not one the runner knows."""
    if not verdicts or any(v not in VERDICT_LABEL for v in verdicts):
        return None
    if "violation" in verdicts:
        return "violation"
    return "verified" if all(v == "verified" for v in verdicts) else "unverifiable"


def property_counterexample(outcome, classes=None):
    """A property outcome's witness as a result's counterexample: the input, the assertion it fails (`contract`;
    null for a property that is its throws clauses alone), what the method did (`actual`), what a throws clause
    required instead, the input the checker found before it was shrunk, and the witness as data."""
    c = outcome.get("counterexample")
    if not c:
        return None
    witness = witness_record(c, classes or {})
    return {"input": c["input"], "contract": property_assertion(outcome), "actual": c["outcome"],
            **({"expected": c["expected"]} if c.get("expected") else {}),
            **({"found": c["found"]} if c.get("found") else {}), "shrinkRuns": c.get("shrink_runs", 0),
            **({"witness": witness} if witness else {})}


def property_assertion(outcome):
    """The assertion as checked, or None for a property that is its throws clauses alone (the tool checks `true`
    beside them: that the method returns where no clause applies)."""
    throws = outcome.get("throws_checked") or outcome.get("throws") or []
    return None if outcome.get("assert") == "true" and throws else outcome.get("assert")


def property_record(outcome, harness, statement, classes=None):
    """One property's outcome as the result keeps it: what it states, its verdict, and its own evidence."""
    throws = outcome.get("throws_checked") or outcome.get("throws") or []
    replay = outcome.get("replay")
    return {"harness": harness, "assert": property_assertion(outcome), "assume": outcome.get("assume"),
            **({"throws": throws} if throws else {}), "verdict": outcome["verdict"], "domain": outcome.get("domain"),
            "proof": outcome.get("proof"), "problem": outcome.get("problem"), "vacuous": outcome.get("vacuous"),
            "counterexample": property_counterexample(outcome, classes), "statement": statement,
            "search": search_record(outcome), "replay": {"by": replay["by"], "reproduced": replay["reproduced"]} if replay else None}


def run_tool_property(folder, example, root, module, result):
    """B11 on a javac app: `jvmcontract prove --json` of every property the module's properties file declares for
    the symbol. Each property keeps its own outcome and evidence under `properties` (the tool's work directory
    `property-N` when there are several), and the result's verdict is the headline over them. The flat fields
    (`property`, `domain`, `proof`, `problem`, `statement`) are the headline property's: the first refuted one, else
    the first unresolved one, else the first; `counterexamples` are every refuted property's witness."""
    app = app_of(example)
    build = root / TOOL_APPS[app]["root"]
    work = build / "build/property"
    proc, output = tool(app, root, "prove", example["subject"]["symbol"], "--properties", "src/contract/properties.contract",
                        "--classes", str(build / "build/main"), "--work", str(work), "--report", str(build / "build/reports"),
                        *proof_options(example), "--json", setup=False)
    outcomes = json_outcomes(proc, root)
    if outcomes is not None:  # the console output is the outcomes' own, with what went to standard error after it
        output = "".join(o["output"] for o in outcomes) + without_root(proc.stderr, root)
    reported = write_evidence(folder, output, build / "build/reports/property.sarif", result)
    for stale in folder.glob("statement-*.java"):  # an earlier run's statements are not this run's
        stale.unlink()
    headline = property_headline([o.get("verdict") for o in outcomes]) if outcomes is not None else None
    several = outcomes is not None and len(outcomes) > 1
    records = []
    if headline is not None:
        for n, o in enumerate(outcomes, 1):
            name = None
            if several and o.get("statement") and (root / o["statement"]).exists():
                name = f"statement-{n}.java"
                shutil.copy(root / o["statement"], folder / name)
            records.append(property_record(o, f"property-{n}" if several else None, name, {"after": build / "build/main"}))
        result["counterexamples"] = [r["counterexample"] for r in records if r["counterexample"]]
    # A violation needs every refuted property's witness.
    refuted = sum(r["verdict"] == "violation" for r in records)
    evidence = result["counterexamples"] if all(r["counterexample"] for r in records if r["verdict"] == "violation") else []
    result["execution"], result["verdict"] = conclude_outcome(
        proc.returncode, output, {"verdict": headline} if outcomes is not None else None, evidence, reported)
    if result["verdict"] is None:  # a run without a verdict leaves no property's evidence as this run's
        records = []
        for copied in folder.glob("statement-*.java"):
            copied.unlink()
    result["properties"] = records or None
    lead = next((i for want in ("violation", "unverifiable", "verified") for i, r in enumerate(records) if r["verdict"] == want), None)
    head, record = (outcomes[lead], records[lead]) if lead is not None else (None, None)
    result["property"] = ({"assert": record["assert"], "assume": record["assume"],
                           **({"throws": record["throws"]} if record.get("throws") else {})} if record else None)
    # The statement of a single property is `statement.java`, as before; of several, each its own.
    statement = root / head["statement"] if head and head.get("statement") and not several else None
    fields = {k: (head or {}).get(k) for k in ("domain", "proof", "problem")}
    # A verified headline rests on every property, so it is vacuous when any of them is; a refuted one is not.
    vacuous = [(n, r["vacuous"]) for n, r in enumerate(records, 1) if r["vacuous"]] if result["verdict"] == "verified" else []
    fields["vacuous"] = (vacuous[0][1] if not several else "; ".join(f"property {n}: {v}" for n, v in vacuous)) if vacuous else None
    total, unresolved = len(records), sum(r["verdict"] == "unverifiable" for r in records)
    finish_symbolic(folder, result, statement, fields, {
        "violation": f"{VERDICT_LABEL['violation']}: counterexample found"
                     + (f" to {refuted} of {total} properties" if several else "")
                     + (f", {unresolved} unresolved" if unresolved else ""),
        "verified": f"{VERDICT_LABEL['verified']}: " + (f"all {total} properties hold" if several else "property holds")
                    + " on every input",
        "unverifiable": VERDICT_LABEL["unverifiable"] + (f": {unresolved} of {total} properties unresolved" if several else ""),
    })
    if several:
        result["statement"] = record["statement"] if record else None
        if vacuous:
            result["verdictLabel"] = (f"{VERDICT_LABEL['verified']}, vacuously for {len(vacuous)} of {total} properties: "
                                      "no input in the domain reaches the calls")


TWOPC = {
    "spec": "spec/TwoPhaseCommit.tla",
    "cfg": "spec/TwoPhaseCommit.cfg",
    "label": "three participants",
    "configurations": [
        {"cfg": "spec/TwoPhaseCommitInductive.cfg", "label": "the inductive step",
         "what": "that the invariant `Inductive` is inductive: TLC starts from every state the invariant admits, reachable or not, "
                 "rather than from the initial state, takes one step, and checks the invariant again, conjunct by conjunct. "
                 "No counterexample is a proof of atomicity by induction, for any run of the protocol however long; a "
                 "counterexample is one step from a state that need not be reachable",
         "initial": "a state the invariant `Inductive` admits, which need not be reachable",
         "startsAnywhere": True},
        {"cfg": "spec/TwoPhaseCommitCrash.cfg", "label": "crashes",
         "what": "every run from the initial state in which the coordinator may crash, twice at most: between steps, or "
                 "after logging a phase change and before the broadcast goes out, and restart on the recovery rule, generated "
                 "from `Recovery#decide`; the same invariants and temporal properties, under the added fairness condition that "
                 "a crashed coordinator restarts"},
        {"cfg": "spec/TwoPhaseCommitCrashInductive.cfg", "label": "the inductive step with crashes",
         "what": "that the invariant `Inductive` is closed under a crash and a restart as well: TLC starts from every state the "
                 "invariant admits, the coordinator up or down, takes one step, and checks the invariant again",
         "initial": "a state the invariant `Inductive` admits, the coordinator up or down, which need not be reachable",
         "startsAnywhere": True},
        {"cfg": "spec/TwoPhaseCommitParticipantCrash.cfg", "label": "participant crashes",
         "what": "every run from the initial state in which a participant may crash, once, between steps or after logging "
                 "a vote and before sending it, and restart on the participant's rule, generated from `Participant#decide`, "
                 "while the coordinator may crash once as well; the same invariants and temporal properties, under the added "
                 "fairness condition that a crashed participant restarts"},
        {"cfg": "spec/TwoPhaseCommitParticipantCrashInductive.cfg", "label": "the inductive step with participant crashes",
         "what": "that the invariant `Inductive` is closed under a participant's crash and restart as well: TLC starts from "
                 "every state the invariant admits, each process up or down, takes one step, and checks the invariant again",
         "initial": "a state the invariant `Inductive` admits, each process up or down, which need not be reachable",
         "startsAnywhere": True},
        {"cfg": "spec/TwoPhaseCommitTrace.cfg", "spec": "spec/TwoPhaseCommitTrace.tla", "label": "the recorded runs",
         "what": "the Java nodes against the model: the coordinator node, its log and its broadcast, and the participant "
                 "nodes, their logs and their votes, run through eleven scripted scenarios with crashes of either process "
                 "injected after a given I/O operation, the state after each step recorded in the model's variables "
                 "(`TwoPhaseCommitTraces.tla`, regenerated from the patched classes); TLC walks each recorded run and checks "
                 "that it starts in the model's initial state and that every step is a step of the model's next-state "
                 "relation. A step the model has no action for is one the glue took that the model's verdicts do not cover",
         "initial": "the model's initial state as the nodes recorded it",
         "explored": "TLC walked the recorded runs, one recorded state after the other, and held each step to the "
                     "model's next-state relation `Next`: the check covers the scripted runs and no others, which is what "
                     "the model's own configurations are for.",
         "recorded": True, "coverage": False,
         "traces": {"writer": "net.terminalvalue.quorum.twopc.Traces", "module": "spec/TwoPhaseCommitTraces.tla"}},
    ],
    "traced": ["net.terminalvalue.quorum.twopc.CoordinatorNode#act", "net.terminalvalue.quorum.twopc.CoordinatorNode#onVote",
               "net.terminalvalue.quorum.twopc.CoordinatorNode#recover", "net.terminalvalue.quorum.twopc.ParticipantNode#act",
               "net.terminalvalue.quorum.twopc.ParticipantNode#giveUp", "net.terminalvalue.quorum.twopc.ParticipantNode#learn",
               "net.terminalvalue.quorum.twopc.ParticipantNode#prepare", "net.terminalvalue.quorum.twopc.ParticipantNode#recover"],
    "contract": "src/contract/Coordinator.decide.contract",
    "operator": "spec/CoordinatorContract.tla",
    "symbol": "net.terminalvalue.quorum.twopc.Coordinator#decide",
    "operators": [{"contract": "src/contract/Recovery.decide.contract", "operator": "spec/RecoveryContract.tla",
                   "symbol": "net.terminalvalue.quorum.twopc.Recovery#decide"},
                  {"contract": "src/contract/Participant.decide.contract", "operator": "spec/ParticipantContract.tla",
                   "symbol": "net.terminalvalue.quorum.twopc.Participant#decide"}],
    "parts": "the participants, the coordinator and the votes in flight",
    "initial": "every participant working, no vote counted, no decision, every process up",
    "actions": {
        "Initial predicate": "the initial state",
        "Vote": "`Participant.prepare`: a participant votes yes (and holds its locks) or no (and aborts), as its rule decides; "
                "it logs the state before it sends the vote, and a crash can fall between the two",
        "ParticipantTimeout": "`Participant.timeout`: a participant that has not voted gives up on its own",
        "Learn": "`Participant.learn`: a participant applies the coordinator's decision",
        "ParticipantCrash": "a participant crashes between steps: it loses nothing it logged, and takes no step until it restarts",
        "ParticipantRecover": "`Participant.recover`: a participant restarts with the state it logged and acts on its rule's "
                              "decision: on the committed rule, a prepared one holds its locks and waits, one that had not voted aborts",
        "ReceiveVote": "`Coordinator.onVote`: the coordinator counts a vote and decides on the tally",
        "CoordinatorTimeout": "`Coordinator.onTimeout`: the collection timer fires with votes missing",
        "Crash": "the coordinator crashes between steps: it loses nothing it logged, and takes no step until it restarts",
        "Recover": "`Recovery.decide`: the coordinator restarts with the phase it logged and acts on the recovery rule's "
                   "decision, which a crash can cut short like any other",
        "TraceNext": "the next state the nodes recorded, after the step the comment in `TwoPhaseCommitTraces.tla` names",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "Atomicity": "once the coordinator or any participant has committed, no participant has aborted",
        "CommitFollowsTheCoordinator": "a participant commits only on the coordinator's decision, and only after voting yes",
        "VotesInFlightAreUncounted": "a vote on its way to the coordinator has not been counted, and a participant votes once",
        "DecisionMatchesThePhase": "what the coordinator broadcast, if anything, is what its phase says: a crash can fall "
                                   "between the logged phase change and the broadcast",
        "BroadcastOnceUp": "a coordinator that is up and decided has its decision out, broadcast when it decided or on restarting",
        "DownOnlyAfterACrash": "the coordinator is down only after a crash",
        "ParticipantsDownOnlyAfterACrash": "participants are down only after crashes: no more of them than have crashed",
        "ParticipantsAgreeWithTheirVotes": "a working participant has not voted, a prepared one voted yes unless a crash took the "
                                           "vote after the state was logged, a no voter has aborted, and a yes voter that aborted "
                                           "did so on the coordinator's say-so",
        "CommitNeedsEveryVote": "the coordinator commits only once every vote is counted and yes",
        "EveryParticipantDecides": "every participant eventually commits or aborts, under the fairness the model assumes: "
                                   "participants vote or give up, the coordinator counts every vote and fires its timer while votes are missing, "
                                   "participants apply a decision once made, and a crashed process restarts",
        "ImplementsTransactionCommit": "every behaviour of the protocol, seen through the participants' states, is one transaction commit "
                                       "(Lamport and Gray's TCommit) allows: a participant commits only once every participant is prepared or "
                                       "committed, and aborts only while none has committed",
        "StartsAtTheInitialState": "the first state of a recorded run is the model's initial state",
        "EveryStepIsOneOfTheModel": "every step the nodes recorded is a step of the model's next-state relation: an action of "
                                    "one part, or a step that changes nothing. A step the model has no action for is one "
                                    "the glue around the rules took, which the model's verdicts do not cover",
    },
    "machine": "The coordinator's decision rule, its recovery rule and the participant's rule inside the model are generated "
               "from the behavioural contracts of the patched code, so the model checks the decisions the processes really "
               "make: the coordinator's on a vote, a timeout and a restart, and a participant's when asked to prepare, when "
               "it gives up, when it reads the decision and when it restarts.",
}

RAFT = {
    "spec": "spec/RaftElection.tla",
    "cfg": "spec/RaftElection.cfg",
    "label": "three servers",
    # The same model under six more configurations, run after the first; the README reports all seven.
    "configurations": [
        {"cfg": "spec/RaftElectionInductive.cfg", "label": "the inductive step",
         "what": "that the invariant `Inductive` is inductive: TLC starts from every state the invariant admits, reachable or not, "
                 "rather than from the initial state, takes one step, and checks the invariant again, conjunct by conjunct. "
                 "No counterexample is a proof of election safety by induction, for any run of the cluster however long; a "
                 "counterexample is one step from a state that need not be reachable",
         "initial": "a state the invariant `Inductive` admits, which need not be reachable",
         "startsAnywhere": True},
        {"cfg": "spec/RaftElectionFour.cfg", "label": "four servers",
         "what": "every run with four servers, a cluster in which a candidate can hold a vote besides its own and still be short "
                 "of a majority, which three servers never show; under a symmetry set, so that of the states that differ only "
                 "by the servers' names TLC explores one"},
        {"cfg": "spec/RaftElectionLive.cfg", "label": "fairness",
         "what": "the two liveness properties, under the fairness conditions `Fairness`: a server whose timer nothing resets "
                 "times out, a candidate asks for the votes it lacks, a leader sends its heartbeats. A counterexample is a run "
                 "that goes on forever without satisfying a property: a prefix, then a state or a cycle the system never leaves"},
        {"cfg": "spec/RaftElectionLogs.cfg", "label": "a server left behind",
         "what": "the election restriction: one server holds the log a deposed leader of term 1 left behind, three entries of "
                 "its term, while the other two hold an entry of term 2 that a majority holds and is therefore committed, so "
                 "that the longer log is the one behind; every run with these logs, which nothing changes, under the invariant "
                 "`LeaderCompleteness` besides the usual ones"},
        {"cfg": "spec/RaftElectionDelayed.cfg", "label": "delayed replies",
         "what": "every run of three servers and two terms in which the reply to a vote request is a step of its own, which "
                 "the candidate may take after it has timed out into a newer term, stepped down, or won; the one-step RPC "
                 "of the other configurations never hands the role machine a reply from an older term than the server's "
                 "own, and this one does, under the usual invariants and action properties"},
        {"cfg": "spec/RaftElectionHistory.cfg", "label": "history",
         "what": "every run of three servers and three terms with the two history variables recording, `elected`, every "
                 "term a server has led, and `voted`, every vote cast, under the two invariants that are about a run rather "
                 "than a state: at most one leader elected per term and at most one vote per server per term, as the paper "
                 "states them. The state invariants of the other configurations hold in a run in which a term's leader steps "
                 "down and the term then elects another; these do not"},
    ],
    "contract": "src/contract/RoleMachine.decide.contract",
    "operator": "spec/RoleMachineContract.tla",
    "symbol": "net.terminalvalue.quorum.raft.RoleMachine#decide",
    # The model's second generated operator: the vote rule, brought in as an instance.
    "operators": [{"contract": "src/contract/VoteRule.decide.contract", "operator": "spec/VoteRuleContract.tla",
                   "symbol": "net.terminalvalue.quorum.raft.VoteRule#decide"}],
    "parts": "the servers, their terms and votes, and the RPCs between them",
    "initial": "every server a follower in term 0, no vote cast, no vote held",
    "actions": {
        "Initial predicate": "the initial state",
        "Timeout": "`Server.onElectionTimeout`: a server's election timer fires, and the server acts on the role machine's decision",
        "Canvass": "`Server.requestVote`: a candidate asks one server for its vote and gets the answer; the request and the reply "
                   "each go through the role machine, then the vote rule on the voter, given its ballot and the candidate's "
                   "term and log against its own, and the tally on the candidate",
        "Ask": "`Server.requestVote`, the request alone: a candidate asks one server for its vote, which the voter decides "
               "as in `Canvass`, and the reply waits on the wire with the term the voter answered in",
        "Answer": "`Server.onVote`: the candidate takes a reply that waited; its term goes through the role machine as it "
                  "compares with the candidate's term now, a granted vote of the current term goes into the tally, and the "
                  "tally through the role machine",
        "Heartbeat": "`Server.appendEntries`: a leader sends one server a heartbeat and gets the answer; the server adopts a newer "
                     "term or yields to the leader of its own, and a stale leader is rejected and steps down",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "ElectionSafety": "at most one leader per term",
        "KernelNeverThrows": "no timeout or RPC any reachable state allows makes the role machine or the vote rule throw: the "
                             "IllegalStateException the Java reserves for an input it holds impossible never fires",
        "LeaderHasAMajority": "a leader holds the votes of a majority of the servers, its own among them",
        "LeaderCompleteness": "a leader's log holds every committed entry, an entry being committed once a majority of the "
                              "servers hold it; the election restriction is what makes it so, a voter granting only a "
                              "candidate whose log is at least as up to date as its own",
        "TermsNeverDecrease": "a term never goes backwards on any server, in any step",
        "LeadersNeverCampaign": "a leader never becomes a candidate: it leaves office as the follower of a newer term, or by "
                                "stepping down, never by starting an election against itself; a property of steps, which no "
                                "invariant can state",
        # The conjuncts of the inductive invariant, which the inductive step checks one by one.
        "VotesAreBound": "a vote in a tally was cast in the tally's term: the voter is still in that term and voted for the "
                         "tally's owner, or has since moved to a newer term",
        "TalliesOfATermAreDisjoint": "no server's vote is in two tallies of one term",
        "CampaignersVoteForThemselves": "a candidate or leader voted for itself in its term, and holds its own vote",
        "TalliesHoldTheirOwnersVote": "a tally is empty, or holds its owner's vote and its owner voted for itself",
        "TermZeroIsQuiet": "nothing happens in term 0: a timer that fires starts term 1",
        "Inductive": "the conjunction of the invariants above, closed under every step of the system",
        # The liveness properties, checked under fairness.
        "ALeaderIsElected": "a run that stays within the term budget elects a leader: with no leader every server's timer "
                            "keeps firing, and each firing starts a term, so a run in which the terms stop and no leader "
                            "comes is a cluster that has stopped trying",
        "StaleLeadersStepDown": "a leader whose term the cluster has left steps down: its heartbeat to a server with a newer "
                                "term, or that server's request for a vote, tells it",
    },
    "machine": "The servers' role machine and vote rule inside the model are generated from the behavioural contracts of "
               "the patched code, so the model checks the role transitions the servers really make and the votes they "
               "really grant.",
}

REPLICATION = {
    "spec": "spec/RaftReplication.tla",
    "cfg": "spec/RaftReplication.cfg",
    "label": "three terms, two entries",
    # The same model under two more configurations, run after the first; the README reports all three.
    "configurations": [
        {"cfg": "spec/RaftReplicationFigureEight.cfg", "label": "figure 8",
         "what": "every run of three servers over four terms with one entry per leader's log, the budget of figure 8 of the "
                 "paper: a leader of term 1 appends an entry it never gets to replicate, a leader of term 2 appends its own "
                 "at the same index, the first comes back as the leader of term 3 and replicates its entry of term 1 to a "
                 "majority, and the second, whose last entry is from the later term, can still be elected in term 4 "
                 "without it; three terms cannot show this, and the same invariants and action properties are checked"},
        {"cfg": "spec/RaftReplicationLive.cfg", "label": "fairness",
         "what": "the three liveness properties, under the fairness conditions `Fairness`: a server whose timer nothing "
                 "resets times out, a candidate asks for the votes it lacks, a leader sends every follower its next entry or "
                 "a heartbeat and marks committed what the commit rule lets it; nothing is assumed of the clients, so the "
                 "properties hold whether or not a request comes. Three servers, three terms and one entry per leader, without the symmetry "
                 "set, since TLC's liveness checking is unsound under one. A counterexample is a run that goes on forever "
                 "without satisfying a property: a prefix, then a state or a cycle the system never leaves"},
        {"cfg": "spec/RaftReplicationDelayed.cfg", "label": "delayed replies",
         "what": "every run of three servers over two terms with logs of up to two entries in which the reply to an "
                 "AppendEntries request is a step of its own (`DelayedReplies = TRUE`): the leader may take it after it has "
                 "sent the follower another request and taken its reply, been deposed, or been elected again in a later "
                 "term, and the network may hand it the same reply twice, or never. The one-step RPC of the other "
                 "configurations hands the reply rule nothing but the request just sent; this one hands it late and "
                 "repeated replies, and checks the leader's record of its followers against what they hold, under the "
                 "same invariants and action properties"},
    ],
    "contract": "src/contract/AppendRule.decide.contract",
    "operator": "spec/AppendRuleContract.tla",
    "symbol": "net.terminalvalue.quorum.raft.AppendRule#decide",
    # The model's other generated operators: the reply rule, the commit rule, the role machine and the vote rule, brought
    # in as instances.
    "operators": [{"contract": "src/contract/ReplyRule.decide.contract", "operator": "spec/ReplyRuleContract.tla",
                   "symbol": "net.terminalvalue.quorum.raft.ReplyRule#decide"},
                  {"contract": "src/contract/CommitRule.decide.contract", "operator": "spec/CommitRuleContract.tla",
                   "symbol": "net.terminalvalue.quorum.raft.CommitRule#decide"},
                  {"contract": "src/contract/RoleMachine.decide.contract", "operator": "spec/RoleMachineContract.tla",
                   "symbol": "net.terminalvalue.quorum.raft.RoleMachine#decide"},
                  {"contract": "src/contract/VoteRule.decide.contract", "operator": "spec/VoteRuleContract.tla",
                   "symbol": "net.terminalvalue.quorum.raft.VoteRule#decide"}],
    "parts": "the servers, their terms, votes and logs, and the AppendEntries RPCs between them",
    "initial": "every server a follower in term 0 with an empty log, no vote cast, nothing committed",
    "actions": {
        "Initial predicate": "the initial state",
        "Timeout": "`Server.onElectionTimeout`: a server's election timer fires, and the server acts on the role machine's decision",
        "Canvass": "`Server.requestVote`: a candidate asks one server for its vote and gets the answer; the request and the reply "
                   "each go through the role machine, then the vote rule on the voter, given its ballot and the candidate's "
                   "term and log against its own, and the tally on the candidate",
        "ClientRequest": "`Server.onClientRequest`: a leader appends an entry of its term to its own log",
        "Replicate": "`Server.appendEntries`: a leader sends one server the entry at that server's next index, or a heartbeat "
                     "if it is caught up, with the entry before it and the leader's commit index, and gets the answer; the "
                     "request goes through the role machine, then the append rule on the follower's log as it stands against "
                     "the leader's, and the reply through the role machine on the leader, then the reply rule on the request "
                     "as it stands against the leader's record of the server, awaited or answered already, which moves the "
                     "server's match index up through the entries sent and its next index past them on an acceptance and "
                     "backs the next index up by one on a refusal",
        "Ask": "`Server.appendEntries`, the request alone, under `RaftReplicationDelayed.cfg`: a leader sends one server the "
               "entry at its next index or a heartbeat, the server decides as in `Replicate`, and its reply waits on the "
               "wire; a leader asks whether or not a reply is outstanding, which is a request sent again",
        "Answer": "`Server.onAppendReply`, under `RaftReplicationDelayed.cfg`: a leader takes a reply that waited, through "
                  "the role machine and then, if the reply is from its own term, the reply rule; the network may hand it "
                  "the same reply again later, or never",
        "AdvanceCommit": "`Server.advanceCommitIndex`: a leader asks the commit rule about an entry it has not marked "
                         "committed, given the entry's term against its own and whether a majority of the servers hold it, and "
                         "marks it committed on a transition, and with it everything before it",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "KernelNeverThrows": "no timeout or RPC any reachable state allows makes the role machine, the vote rule, the append "
                             "rule, the reply rule or the commit rule throw: the IllegalStateException the commit rule "
                             "reserves for an entry from a term after the leader's never fires",
        "MatchIndexIsRight": "a leader's record of a follower is right: while a follower is in the leader's term, it holds "
                             "every entry the leader has recorded it as holding, so that the servers the commit rule counts "
                             "as holding an entry hold it; the reply rule is what maintains the record, and a reply that "
                             "arrives late, or twice, is what could corrupt it",
        "NextIndexPastMatch": "a leader's next index for a follower is past every entry it has recorded the follower as "
                              "holding: the leader never sends a follower an entry it knows it holds",
        "ElectionSafety": "at most one leader per term",
        "LogMatching": "if two logs hold an entry of the same term at the same index, they are the same through that index "
                       "(figure 3 of the paper); the append rule's consistency check is what makes it so",
        "LeaderCompleteness": "a leader holds every entry a server of its term or an earlier one knows committed (figure 3 of "
                              "the paper); the election restriction and the commit rule together are what make it so",
        "StateMachineSafety": "no two servers have committed different entries at one index (figure 3 of the paper)",
        "CommittedEntriesNeverChange": "a committed entry is never overwritten and a commit index never goes backwards, in "
                                       "any step: once a server has applied an entry, that entry stays at its index for good",
        "TermsNeverDecrease": "a term never goes backwards on any server, in any step",
        "LeaderAppendOnly": "a leader never truncates or overwrites its own entries, in any step (figure 3 of the paper)",
        # The liveness properties, checked under fairness, of the runs that stay within the term budget.
        "FollowersCatchUp": "every entry in a leader's log reaches every follower: from some point on, each follower's log "
                            "holds the leader's as a prefix, in every run that stays within the term budget",
        "FollowersLearnCommits": "every follower learns what the leader has committed: from some point on, no follower's "
                                 "commit index is behind the leader's, in every run that stays within the term budget",
        "OwnEntriesAreCommitted": "an entry a leader appended in its term is committed, unless the leader is deposed first, in "
                                  "every run that stays within the term budget; nothing is claimed of an entry from an "
                                  "earlier term, which the commit rule commits only along with a later entry of the "
                                  "leader's own",
    },
    "machine": "The follower's append rule, the leader's reply rule and commit rule, the role machine and the vote rule inside "
               "the model are generated from the behavioural contracts of the patched code, so the model checks the entries "
               "the followers really take, the record the leaders really keep of them, the commits the leaders really make, "
               "and the roles and votes behind them.",
}

IDEMPOTENCY = {
    "spec": "spec/IdempotentReceiver.tla",
    "cfg": "spec/IdempotentReceiver.cfg",
    "label": "the record never expires",
    "configurations": [
        {"cfg": "spec/IdempotentReceiverExpiring.cfg", "label": "expiring record",
         "what": "the same invariants, with the record's time to live allowed to pass at any point: the sweeper asks the "
                 "receiver what to do with the record and applies the decision, and a release ends the record's lifetime, "
                 "so `AtMostOnce` counts the results since the last release. The model has no clock, so the sweeper's clock "
                 "has measured the record's age and nothing else, in particular not whether an execution is still running"},
    ],
    "contract": "src/contract/IdempotentReceiver.decide.contract",
    "operator": "spec/IdempotentReceiverContract.tla",
    "symbol": "net.terminalvalue.crosscut.idempotency.IdempotentReceiver#decide",
    "parts": "the client's attempts, the receiver, and the attempts in flight and executing",
    "initial": "no record for the key, nothing sent, nothing executing, no response",
    "actions": {
        "Initial predicate": "the initial state",
        "Send": "`IdempotentClient.send`: the client sends the request, or retries it without waiting for an answer",
        "Receive": "`IdempotencyFilter.doFilter`: the receiver looks the key up, decides, and applies the decision in one transaction",
        "Finish": "`IdempotencyFilter.onCompleted`: an execution produced a result, which the receiver stores and returns",
        "Fail": "`IdempotencyFilter.onFailure`: an execution died without a result",
        "Expire": "`IdempotencySweeper.sweep`: the record's time to live passed; the sweeper asks the receiver what to do "
                  "with the record and applies the decision",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "OneExecutionAtATime": "no two attempts under one key execute at the same time",
        "AtMostOnce": "once an execution has produced a result, no attempt is executing and none ever will, for as long as "
                      "the record lives (in the configuration where it never expires, at most once outright)",
        "ReplayedResponsesExist": "a client is never answered with a stored response that does not exist",
    },
    "machine": "The receiver's decision rule inside the model is generated from the behavioural contract of "
               "the patched code, so the model checks the decisions the receiver really makes.",
}

CLASSINIT = {
    "spec": "spec/ClassInit.tla",
    "cfg": "spec/ClassInit.cfg",
    "contract": "src/contract/ClassInitialization.decide.contract",
    "operator": "spec/ClassInitContract.tla",
    "symbol": "net.terminalvalue.mica.init.ClassInitialization#decide",
    "parts": "the threads, the class's initialization state and its recorded initializer",
    "initial": "the class uninitialized, no initializer recorded, every thread idle",
    "deadlock": True,
    "actions": {
        "Initial predicate": "the initial state",
        "Request": "`Runtime.initialize`: a thread needs the class, takes the initialization lock and acts on the decision",
        "Recurse": "`Runtime.initialize` from inside `<clinit>`: the initializer touches its own class",
        "Complete": "`Runtime.initialized`: `<clinit>` returned; the waiters are woken and the thread uses the class",
        "Fail": "`Runtime.initializationFailed`: `<clinit>` threw; the waiters are woken and the thread gets the error",
        "Terminating": "every thread is done with the class",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "UsedOnlyWhenInitialized": "a thread uses the class only once it is initialized",
        "InitializedAtMostOnce": "the initializer runs at most once",
        "OneInitializer": "only the recorded initializer runs the initializer",
        "Deadlock": "a state in which no thread can move",
    },
    "machine": "The runtime's decision rule inside the model is generated from the behavioural contract of "
               "the patched code, so the model checks the decisions the runtime really makes.",
}

BREAKER = {
    "spec": "spec/CircuitBreaker.tla",
    "cfg": "spec/CircuitBreaker.cfg",
    "label": "two calls in flight",
    "configurations": [
        {"cfg": "spec/CircuitBreakerLive.cfg", "label": "fairness",
         "what": "the three liveness properties, under the fairness conditions `Fairness`: the caller keeps calling, every "
                 "permitted call completes, the clock ticks, and nothing is assumed of the dependency. A counterexample is a "
                 "run that goes on forever without satisfying a property: a prefix, then a state or a cycle the system never leaves"},
    ],
    "contract": "src/contract/CircuitBreaker.decide.contract",
    "operator": "spec/CircuitBreakerContract.tla",
    "symbol": "net.terminalvalue.crosscut.resilience.CircuitBreaker#decide",
    "parts": "the caller, the owner of the breaker with its window, its probes and its wait, the dependency and the clock",
    "initial": "the breaker closed, the window empty, no call in flight, no wait running, the dependency up or down",
    "actions": {
        "Initial predicate": "the initial state",
        "Request": "`CircuitBreaker.tryAcquirePermission`: a caller asks for a call; the owner reports whether the wait has "
                   "elapsed and applies the decision, which lets the call through, starts a new metrics generation, or starts the wait",
        "Complete": "`CircuitBreaker.onResult`, for a call of the current generation: the owner records the outcome, judges "
                    "the window, and applies the decision",
        "CompleteStale": "`CircuitBreaker.onResult`, for a call from an earlier generation: its outcome is dropped",
        "Tick": "the clock advances: one tick less of the open state's wait",
        "DependencyFlips": "the dependency goes down, or comes back",
    },
    "invariants": {
        "TypeOK": "every variable has a value of its type",
        "NoCallBeforeTheWait": "an open breaker lets nothing through until its wait has elapsed",
        "OpenShieldsTheDependency": "while open, the dependency receives no call of the current generation: everything in "
                                    "flight was permitted before the breaker opened",
        "ClosedOnlyAfterEveryProbe": "half-open closes only once every permitted probe has completed",
        "ProbesAreLimited": "half-open lets at most the permitted number of probes through before it decides",
        "ClosedOnlyBelowTheThreshold": "a closed breaker never sits on a complete window whose failure rate is at the threshold",
        # The liveness properties, checked under fairness.
        "AnOpenBreakerProbesAgain": "an open breaker does not stay open: its wait elapses, and the next call is let through as a probe",
        "ARecoveredDependencyIsUsed": "a dependency that comes back for good is used again: from some point on the breaker is "
                                      "closed and stays so",
        "ADeadDependencyIsLeftAlone": "a dependency that is down for good gets the wait between its probes: the breaker opens "
                                      "again and again, so that no round of probes is followed by another without a wait",
    },
    "machine": "The breaker's decision rule inside the model is generated from the behavioural contract of the patched code, "
               "so the model checks the transitions the breaker really makes; the owner's part, the window, the probe cap and "
               "the wait, is written in the model and applies whatever the rule returns.",
}

# The TLA+ models of each javac app, each built around the state machine of one symbol.
TOOL_MODELS = {"quorum": [TWOPC, RAFT, REPLICATION], "crosscut": [IDEMPOTENCY, BREAKER], "mica": [CLASSINIT]}


def model_of(example):
    """The model a D1 example is checked against: the one of its app built around the example's symbol."""
    model = find_model(example)
    if model is None:
        sys.exit(f"{example['id']}: no TLA+ model of {app_of(example)} is built around {example['subject']['symbol']}")
    return model


def find_model(example):
    app = app_of(example)
    if app == "boxoffice":
        return MODELS["boxoffice"]
    for model in TOOL_MODELS.get(app, []):
        if example["subject"]["symbol"] in [model["symbol"]] + [o["symbol"] for o in model.get("operators", [])] \
                + model.get("traced", []):
            return model
    return None


def tlc_run(build, model_files, configuration, root):
    """One run of TLC on a model under a configuration, through the tool: its parsed JSON, plus the configuration's
    bounds (`domain`) and whether it lists temporal properties. A configuration may name a `spec` of its own, a
    module that extends the model (the trace specification does), and may turn `coverage` off: TLC attributes no
    coverage to a next-state relation it evaluates as an action property."""
    cfg = configuration["cfg"]
    deadlock = ["--deadlock"] if model_files.get("deadlock") else []
    config = [] if cfg == model_files["cfg"] else ["--config", cfg]
    coverage = ["--coverage"] if configuration.get("coverage", True) else []
    # TLC's coverage mode needs more heap than Java's default on a model with many actions (the replication model with
    # delayed replies fails at once with "out of memory" at the default); a cap costs a small model nothing.
    env = {"JVMCONTRACT_JAVA_OPTS": "-Xmx2500m", **os.environ}
    proc = stage(f"jvmcontract tlc {Path(cfg).name}",
                 [jvmcontract(), "tlc", configuration.get("spec", model_files["spec"]), "--json", *coverage, *deadlock, *config,
                  "--library", str(EXAMPLES / "tools/tla/standard-modules")], cwd=build, env=env)
    run = tlc_run_result(proc)
    run["output"] = run["output"].replace(str(root) + "/", "").replace(str(REPO) + "/", "")
    text = (build / cfg).read_text()
    run["domain"] = ", ".join(re.findall(r"^\s+(\w+ = .+)$", text, re.M))
    run["properties"] = bool(re.search(r"^PROPERTIES|^PROPERTY", text, re.M))
    run["deadlockChecked"] = bool(deadlock)
    # How a temporal counterexample goes on after its last step: TLC's counterexample for a liveness property is
    # infinite, a prefix and then either stuttering or a loop back into the prefix.
    run["forever"] = None
    if run["verdict"] == "violation" and run.get("kind") == "temporal":
        run["forever"] = (f"returns to step {run['lasso']} and repeats steps {run['lasso']} to {len(run['trace'])} forever"
                          if run.get("lasso") else "stays in that state forever")
    return run


CHECKPOINT_FORMAT = 1


def checkpoint_dir():
    """Where a configuration's TLC result is kept once it completes: $BUILD_CHECKPOINTS (the pipeline points it at its
    own state, so a job run again after a timeout picks up where it stopped), or examples/.checkpoints, which git
    ignores; `off` keeps none."""
    where = os.environ.get("BUILD_CHECKPOINTS")
    if where == "off":
        return None
    return Path(where) if where else EXAMPLES / ".checkpoints"


def file_digest(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


TOOL_IDENTITY = {}


def tool_identity():
    """What runs TLC, beyond the model: jvmcontract (which runs TLC and reads its coverage), TLC's jar, and Java."""
    if not TOOL_IDENTITY:
        jar = os.environ.get("TLA2TOOLS_JAR") or str(Path.home() / "tools/tla2tools.jar")
        proc = stage("java -version", [java(), "-version"])
        TOOL_IDENTITY.update({"jvmcontract": file_digest(jvmcontract()), "tla2tools": file_digest(jar),
                              "java": (proc.stdout + proc.stderr).strip() or None})
    return TOOL_IDENTITY


def tlc_inputs(build, model_files, configuration):
    """Everything a TLC run under a configuration depends on, by content: every module and configuration file of the
    model's directory (the generated operators and the recorded runs among them), the standard modules, the command,
    and the tools. Not the heap TLC is given: it decides whether a run completes, not what a completed run found."""
    spec_dir = build / Path(model_files["spec"]).parent
    library = EXAMPLES / "tools/tla/standard-modules"
    return {
        "format": CHECKPOINT_FORMAT,
        "spec": configuration.get("spec", model_files["spec"]), "cfg": configuration["cfg"],
        "coverage": configuration.get("coverage", True), "deadlock": bool(model_files.get("deadlock")),
        "files": {f.relative_to(build).as_posix(): file_digest(f)
                  for f in sorted(spec_dir.iterdir()) if f.is_file() and f.suffix in (".tla", ".cfg")},
        "standardModules": {f.relative_to(library).as_posix(): file_digest(f) for f in sorted(library.rglob("*")) if f.is_file()},
        "tools": tool_identity(),
    }


def tlc_checkpointed_run(app, root, build, model_files, configuration, example_id):
    """One configuration's TLC run, kept as soon as it completes and reused only when every input it depends on is
    the same (`tlc_inputs`, hashed as the fingerprint). A run that did not complete is not kept, so it runs again.
    Anything that stops the configuration from running (its recorded runs cannot be written, the tool cannot be
    started) is that configuration's run without a verdict: the configurations before it keep their results. Returns
    the run and the record of where it came from."""
    record = {"label": configuration["label"], "cfg": configuration["cfg"], "fingerprint": None, "reused": False}
    try:
        if configuration.get("traces"):
            tool_traces(app, root, configuration["traces"])
        inputs = tlc_inputs(build, model_files, configuration)
        fingerprint = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
        record["fingerprint"] = fingerprint
        where = checkpoint_dir()
        path = where / f"{fingerprint}.json" if where else None
        if path and path.is_file():
            try:
                kept = json.loads(path.read_text())
            except ValueError:
                kept = None
            if isinstance(kept, dict) and kept.get("fingerprint") == fingerprint and kept.get("inputs") == inputs \
                    and (kept.get("run") or {}).get("execution", {}).get("status") == "completed":
                record.update({"reused": True, "recordedAt": kept.get("recordedAt")})
                return kept["run"], record
        run = tlc_run(build, model_files, configuration, root)
        if path and run["execution"]["status"] == "completed":
            path.parent.mkdir(parents=True, exist_ok=True)
            kept = {"fingerprint": fingerprint, "inputs": inputs, "example": example_id, "label": configuration["label"],
                    "recordedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "run": run}
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(kept, ensure_ascii=False) + "\n")
            temporary.replace(path)
        return run, record
    except (Exception, SystemExit) as e:
        reason = f"the configuration could not be run: {e}".strip()
        execution = {"status": "tool-error", "exitCode": None, "reason": reason}
        return {"verdict": "unverifiable", "execution": execution, "problem": reason, "output": f"Error: {reason}\n",
                "trace": [], "coverage": None, "version": "TLC", "domain": "", "properties": False,
                "deadlockChecked": False, "forever": None}, record


def tlc_run_result(proc):
    """The tool's JSON for one TLC run, with how the run ended (`execution`). The tool exits 0 or 1 with its JSON
    whatever TLC did, reporting a TLC that was killed or ran out of time in the output; a tool that failed, was
    killed, or printed JSON it cannot have meant gives a run with no verdict, its output kept as the evidence."""
    raw = (proc.stdout or "") + (proc.stderr or "")
    execution = execution_status(proc.returncode, proc.stdout)
    run = None
    if execution["status"] == "completed":
        try:
            run = json.loads(proc.stdout)
            if not isinstance(run, dict) or run.get("verdict") not in VERDICT_LABEL or not isinstance(run.get("output"), str):
                raise ValueError("not a TLC result")
        except ValueError:
            run = None
            execution = {"status": "invalid-output", "exitCode": proc.returncode,
                         "reason": "jvmcontract tlc printed no TLC result the runner can read"}
    if run is None:
        return {"verdict": "unverifiable", "execution": execution, "problem": execution["reason"], "output": raw,
                "trace": [], "coverage": None, "version": "TLC"}
    trace = run.get("trace") or []
    execution, verdict = tlc_conclusion(None, run["output"], None, run["verdict"] == "verified",
                                        run["verdict"] == "violation", trace)
    run["execution"] = {**execution, "exitCode": proc.returncode}
    if verdict is None:
        # The run has no verdict: kept as one TLC could not give, with the reason it did not.
        run.update({"verdict": "unverifiable", "problem": execution["reason"]})
    return run


def tlc_label(run):
    """The one-line verdict of a TLC run, as the README's tables show it."""
    if (run.get("execution") or {}).get("status", "completed") != "completed":
        return no_verdict_label(run["execution"])
    verdict = run["verdict"]
    states = run.get("distinct_states")
    if verdict == "violation":
        if len(run["trace"]) == 1:
            return f"{VERDICT_LABEL[verdict]}: {run.get('invariant') or ''}, violated by a starting state"
        return (f"{VERDICT_LABEL[verdict]}: {'deadlock' if run.get('deadlock') else run.get('invariant') or ''}, "
                f"{len(run['trace'])}-step trace{' then forever' if run.get('kind') == 'temporal' else ''}")
    if verdict == "verified" and states is not None:
        return (f"{VERDICT_LABEL[verdict]}: all invariants{' and properties' if run['properties'] else ''} hold in {states:,} states"
                f"{', no deadlock' if run['deadlockChecked'] else ''}")
    return VERDICT_LABEL[verdict]


def tlc_proof(run):
    return (f"{run['version']} explored {run['distinct_states']:,} distinct states"
            f"{' to depth ' + str(run['depth']) if run.get('depth') is not None else ''}"
            f"{' in ' + str(run['seconds']) + ' s' if run.get('seconds') is not None else ''}, for the model {run['domain']}") if run.get("distinct_states") is not None else None


def contract_rows(text):
    """A contract's cases and their outcomes, by case."""
    return dict(re.findall(r"^(\w+\(.*\))\s+=> (.*)$", text, re.M))


def tlc_coverage(configurations, runs, before, after, symbols=None):
    """What the verdict rests on: for each configuration, how its run ended and how many rows of each generated
    operator a step of the model took (TLC's coverage, read back by the tool); the rows the change altered, with the
    configurations whose runs take them and those under which nobody knows; how much of that is known
    (`status`); and whether the verdict is vacuous, which it is when every run finishes, the coverage is complete,
    and no run from an initial state takes any altered row that decides.

    The inductive step starts from every state the invariant admits, not from a run, so it does not count: it only
    says the invariant held one step on. A run that stops at a counterexample, or ends without a verdict, has
    explored a part of the model and its counts are left out. An operator TLC's statistics do not list under an
    action (no statistics were printed, or the reader did not find the operator in them) has counts of zero that
    mean nothing: under that configuration its rows are not known, not untaken. `status` is `complete` when every
    configuration that counts coverage finished and lists every operator the verdict depends on (those with an
    altered row that decides, or all of them when none is), `unavailable` when none lists any, and `partial`
    otherwise; only complete coverage can make a verdict vacuous. Rows that throw are meant never to be taken, so
    they do not make a verdict vacuous: whether a run could take one is for an invariant over the model's events
    to say. Rows with a null argument are not in the model, which never passes null. `symbols` maps each contract
    to the symbol of the operator generated from it."""
    symbols = symbols or {}
    # The reason an outcome records is not in the model, so a row that changes only in its reason has not changed.
    in_the_model = lambda outcome: re.sub(r'^(Unchanged|Rejected)\[.*\]$', r'\1', outcome) if outcome else outcome
    changed, nulls = [], 0
    for contract, rows in after.items():
        for case, outcome in rows.items():
            was = before.get(contract, {}).get(case)
            if in_the_model(was) == in_the_model(outcome):
                continue
            if re.search(r"\(null, |, null\)", case):
                nulls += 1
            else:
                changed.append({"case": case, "symbol": symbols.get(contract), "before": was, "after": outcome})
    reached = {}
    per_configuration = []
    for c, r in zip(configurations, runs):
        execution = r.get("execution") or {"status": "completed", "reason": None}
        verdict = r["verdict"] if execution["status"] == "completed" else None
        finished = verdict == "verified"
        counted = c.get("coverage", True)
        operators = []
        for op in (r.get("coverage") or []) if finished else []:
            listed = bool(op.get("listed"))
            taken = [row["case"] for row in op["rows"] if row["taken"]] if listed else []
            operators.append({"symbol": op["symbol"], "listed": listed, "reached": len(taken), "total": len(op["rows"]),
                              "never": [f"{row['case']} => {row['outcome']}" for row in op["rows"] if not row["taken"]] if listed else []})
            for case in taken:
                reached.setdefault(case, []).append(c["label"])
        listed = {op["symbol"] for op in operators if op["listed"]}
        if not counted:
            status, why = "unavailable", "TLC attributes no coverage to a next-state relation it evaluates as an action property"
        elif not finished:
            status, why = "unavailable", ("the run stopped at a counterexample" if verdict == "violation" else
                                          f"the run ended without a verdict: {execution.get('reason') or 'unknown'}")
        elif not listed:
            status, why = "unavailable", ("the tool read no coverage statistics of a generated operator" if not operators else
                                          "TLC's coverage statistics list no generated operator under any action")
        elif len(listed) < len(operators):
            status, why = "partial", "TLC's coverage statistics do not list " + ", ".join(
                f"`{op['symbol']}`" for op in operators if not op["listed"]) + " under any action"
        else:
            status, why = "complete", None
        per_configuration.append({"label": c["label"], "fromRuns": not c.get("startsAnywhere", False), "finished": finished,
                                  "verdict": verdict, "status": execution["status"], "reason": execution.get("reason"),
                                  "counted": counted, "coverageStatus": status, "coverageReason": why,
                                  "listed": sorted(listed), "operators": operators})
    from_runs = {c["label"] for c in configurations if not c.get("startsAnywhere", False)}
    counting = [c for c in per_configuration if c["counted"]]
    for row in changed:
        row["takenUnder"] = reached.get(row["case"], [])
        # Where the row's count is unknown though the run finished: its operator is not among those listed.
        row["unknownUnder"] = [c["label"] for c in counting if c["finished"] and row["symbol"] not in c["listed"]]
    deciding = [row for row in changed if not row["after"].startswith("throws ")]
    every = {op["symbol"] for c in per_configuration for op in c["operators"]} | set(symbols.values())
    needed = {row["symbol"] for row in deciding} or every
    known = [c for c in counting if c["finished"] and needed <= set(c["listed"])]
    some = [c for c in counting if c["finished"] and needed & set(c["listed"])]
    status = "complete" if counting and len(known) == len(counting) else "partial" if some else "unavailable"
    vacuous = bool(deciding) and status == "complete" and all(c["finished"] for c in per_configuration) \
        and not any(set(row["takenUnder"]) & from_runs for row in deciding)
    return {"status": status, "configurations": per_configuration, "changedRows": changed, "nullRows": nulls,
            "vacuous": vacuous}


def model_contract(symbol, contract, operator, baseline, candidate, intended):
    """How one generated operator is tied to the patched bytecode. The operator is always generated from the
    candidate contract, the one derived from the patched classes in this run: `verified` when that is the committed
    contract (the patched classes still behave as it says), `derived` when it differs. Whether a difference is
    allowed is the example's to say, by `behaviourChangeIntended`; it no longer decides which contract the model
    checks. A row that differs only in an outcome's reason counts: the contract changed, whether or not the model
    reads the reason."""
    before, after = contract_rows(baseline), contract_rows(candidate)
    changed = sum(1 for case in set(before) | set(after) if before.get(case) != after.get(case))
    return {"symbol": symbol, "contract": contract, "operator": operator,
            "connection": "verified" if baseline == candidate else "derived",
            "rowsChanged": changed, "allowed": changed == 0 or intended}


def contract_diff(path, baseline, candidate):
    return "".join(difflib.unified_diff(baseline.splitlines(True), candidate.splitlines(True), f"a/{path}", f"b/{path}"))


def unauthorized(result):
    """The generated operators whose contract the change altered though no behaviour change was intended."""
    return [c for c in result.get("modelContracts") or [] if not c["allowed"]]


def unauthorized_findings(result, example):
    """A SARIF result for each operator the change altered without an intended behaviour change."""
    return [{"ruleId": "contract-changed", "level": "error",
             "message": {"text": f"The patched {c['symbol']} differs from {c['contract']} in {c['rowsChanged']} "
                                 f"row{'s' if c['rowsChanged'] != 1 else ''}, and the change is not meant to alter behaviour; "
                                 "the model was checked on the patched rule"},
             "locations": [{"physicalLocation": {"artifactLocation": {"uri": example["subject"]["file"]},
                                                 "region": {"startLine": result["after"]["startLine"]}}}]}
            for c in unauthorized(result)]


CONTRACT_CHANGED_RULE = {"id": "contract-changed", "shortDescription": {
    "text": "The patched code changes the behavioural contract a generated operator of the model comes from, and the "
            "change is not meant to alter behaviour."}}


def model_verdict(result, verdict, label):
    """The verdict of a D1 run, from TLC's on the patched operators and the operators' connection to the committed
    contracts. A contract the change altered without an intended behaviour change is a refuted obligation of its own,
    so the change fails whatever TLC found; TLC's verdict and label are kept beside it (`modelVerdict`,
    `modelSummary`)."""
    result["modelVerdict"], result["modelSummary"] = verdict, label
    changed = unauthorized(result)
    if verdict != "verified" or not changed:
        return verdict, label
    rows = sum(c["rowsChanged"] for c in changed)
    names = ", ".join(f"`{c['symbol'].rsplit('.', 1)[-1]}`" for c in changed)
    return "violation", (f"{VERDICT_LABEL['violation']}: the patched {names} change{'s' if len(changed) == 1 else ''} "
                         f"{rows} row{'s' if rows != 1 else ''} of {'its' if len(changed) == 1 else 'their'} contract with "
                         f"no behaviour change intended, though the model holds on {'it' if len(changed) == 1 else 'them'}")


def tlc_configurations(model_files):
    """The configurations a model is checked under: the one of its `.cfg`, then any it lists under `configurations`."""
    # The Box Office model predates configurations: its one configuration is the spec's own .cfg.
    primary = {"cfg": model_files.get("cfg", "BoxOffice.cfg"), "label": model_files.get("label", "the model"), "initial": model_files["initial"],
               "what": "every run from the initial state, every interleaving within the configuration's bounds"}
    return [primary] + [{**c, "initial": c.get("initial", model_files["initial"])} for c in model_files.get("configurations", [])]


def tool_model_contracts(app, root, example, generated, result):
    """Ties every generated operator of the model to the patched bytecode: the contract of each operator's symbol is
    derived from the patched classes (`jvmcontract derive`) and written where the operator is generated from, so the
    model checks the rule that was built, whether or not the change was meant to alter it. For an intended change
    the module's contracts are regenerated first, and their diff is the one a reviewer approves; for any other, the
    diff of an operator's contract that changed is recorded as the unauthorized difference. Returns the baseline and
    candidate contracts' rows, or None, with the run recorded as a tool error, when an operator's contract cannot be
    derived: the model would then check a rule nobody showed the patched code to have."""
    part = TOOL_APPS[app]["root"]
    build = root / part
    intended = example["change"]["behaviourChangeIntended"]
    baseline = {g["contract"]: (build / g["contract"]).read_text() for g in generated}
    if intended:
        tool_update_contracts(app, root, result)
    connections, candidates, diffs = [], {}, []
    for g in generated:
        proc = stage(f"jvmcontract derive {g['symbol'].rsplit('.', 1)[-1]}",
                     [jvmcontract(), "derive", g["symbol"], "--classes", str(build / "build/main")])
        if proc.returncode != 0 or not contract_rows(proc.stdout):
            output = (proc.stdout + proc.stderr).replace(str(root) + "/", "")
            reason = f"jvmcontract derive could not derive the contract of {g['symbol']} from the patched classes" \
                     + (f": {last_line(output)}" if last_line(output) else "")
            result.update({"verdict": None, "problem": reason, "sarif": None,
                           "execution": {"status": "tool-error", "exitCode": proc.returncode, "reason": reason}})
            return None, output
        candidate = candidates[g["contract"]] = proc.stdout
        (build / g["contract"]).write_text(candidate)
        connection = model_contract(g["symbol"], g["contract"], g["operator"], baseline[g["contract"]], candidate, intended)
        connections.append(connection)
        if not connection["allowed"]:
            diffs.append(contract_diff(f"{part}/{g['contract']}", baseline[g["contract"]], candidate))
    result["modelContracts"] = connections
    if not intended:
        result["contractDiff"] = "".join(diffs) or None
    return ({c: contract_rows(t) for c, t in baseline.items()}, {c: contract_rows(t) for c, t in candidates.items()}), None


def run_tool_tlc(folder, example, root, module, result):
    """D1 on a javac app: each operator generated from the contract derived from the patched classes, then TLC through
    the tool, once per configuration of the model. The headline, which decides TLC's verdict, is the first
    configuration that finds a violation (or that TLC cannot check), else the first; a contract the change altered
    though no behaviour change was intended makes the verdict a violation whatever TLC found."""
    app = app_of(example)
    build = root / TOOL_APPS[app]["root"]
    model_files = model_of(example)
    generated = [model_files, *model_files.get("operators", [])]
    rows, failed = tool_model_contracts(app, root, example, generated, result)
    if rows is None:
        (folder / "verifier-output.txt").write_text(failed.rstrip("\n") + "\n")
        (folder / "result.sarif").unlink(missing_ok=True)
        return
    rows_before, rows_after = rows
    for g in generated:
        tool(app, root, "tla", g["contract"], g["operator"], anchored=False)
    configurations = tlc_configurations(model_files)
    runs, checkpoints = [], []
    for c in configurations:
        run, checkpoint = tlc_checkpointed_run(app, root, build, model_files, c, example["id"])
        runs.append((c, run))
        checkpoints.append(checkpoint)
    result["checkpoints"] = checkpoints
    result["coverage"] = tlc_coverage(configurations, [r for _, r in runs], rows_before, rows_after,
                                      {g["contract"]: g["symbol"] for g in generated})
    several = len(runs) > 1
    headline = next(((c, r) for c, r in runs if r["verdict"] == "violation"), None) \
        or next(((c, r) for c, r in runs if r["verdict"] == "unverifiable"), None) or runs[0]
    configuration, tlc_result = headline
    if several:
        output = "".join(f"== {c['label']}: {c['cfg']} ==\n{r['output'].rstrip(chr(10))}\n\n" for c, r in runs)
    else:
        output = tlc_result["output"]
    (folder / "verifier-output.txt").write_text(output.rstrip("\n") + "\n")
    # The verdict is the headline run's, when TLC completed it; a run TLC could not finish has no verdict.
    execution = tlc_result["execution"]
    verdict = tlc_result["verdict"] if execution["status"] == "completed" else None
    kind = tlc_result.get("kind")
    trace = [{"step": s["step"], "action": s["action"], "changes": s["changes"]} for s in tlc_result["trace"]] if verdict == "violation" else None
    findings = []
    for c, r in runs:
        if r["verdict"] == "verified":
            continue
        where = f"{model_files['spec']} ({c['label']})" if several else model_files["spec"]
        steps = len(r["trace"])
        if r["verdict"] == "violation" and r.get("deadlock"):
            message = f"{where} deadlocks after {steps} steps: no action is enabled"
        elif r["verdict"] == "violation" and r.get("kind") == "temporal":
            message = f"Temporal property {r['invariant']} of {where} is violated: after {steps} steps the system {r['forever']}"
        elif r["verdict"] == "violation" and r.get("kind") == "action":
            message = f"Action property {r['invariant']} of {where} is violated after {steps} steps"
        elif r["verdict"] == "violation" and steps == 1:
            message = f"Invariant {r['invariant']} of {where} is violated by a starting state"
        elif r["verdict"] == "violation":
            message = f"Invariant {r['invariant']} of {where} is violated after {steps} steps"
        else:
            message = f"TLC produced no verdict for {where}: " + (r.get("problem") or "unknown")
        findings.append({"ruleId": "invariant-violated" if r["verdict"] == "violation" else "unverifiable", "level": "error",
                         "message": {"text": message},
                         "locations": [{"physicalLocation": {"artifactLocation": {"uri": example["subject"]["file"]},
                                                             "region": {"startLine": result["after"]["startLine"]}}}]})
    findings += unauthorized_findings(result, example)
    sarif = {"version": "2.1.0", "$schema": "https://json.schemastore.org/sarif-2.1.0.json", "runs": [{
        "tool": {"driver": {"name": "jvmcontract tlc", "rules": [
            {"id": "invariant-violated", "shortDescription": {"text": "TLC found a behaviour of the model that violates an invariant or a temporal property, or ends in a deadlock."}},
            {"id": "unverifiable", "shortDescription": {"text": "TLC could not check the model."}},
            CONTRACT_CHANGED_RULE]}},
        "results": findings}]}
    (folder / "result.sarif").write_text(json.dumps(sarif, indent=2, ensure_ascii=False) + "\n")
    states = tlc_result.get("distinct_states")
    result.update({
        "verdict": verdict,
        "execution": execution,
        "trace": trace,
        "statesExplored": states,
        "invariant": tlc_result.get("invariant"),
        "violationKind": kind,
        "forever": tlc_result["forever"],
        "domain": tlc_result["domain"],
        "stateMachine": tool_state_machine(app, root, example["subject"]["symbol"]),
        "proof": "; ".join(f"{c['label']}: {tlc_proof(r)}" for c, r in runs if tlc_proof(r)) if several else tlc_proof(tlc_result),
        "problem": tlc_result.get("problem") if verdict != "verified" and verdict != "violation" else None,
    })
    if several:
        result["configurations"] = [{
            "label": c["label"], "cfg": c["cfg"], "verdict": r["verdict"], "status": r["execution"]["status"],
            "reason": r["execution"].get("reason"), "summary": tlc_label(r), "domain": r["domain"],
            "invariant": r.get("invariant"), "violationKind": r.get("kind"), "statesExplored": r.get("distinct_states"),
            "trace": [{"step": s["step"], "action": s["action"], "changes": s["changes"]} for s in r["trace"]] if r["verdict"] == "violation" else None,
            "forever": r["forever"],
        } for c, r in runs]
    if verdict is None:
        return
    label = tlc_label(tlc_result)
    changed = len(result["coverage"]["changedRows"])
    if verdict == "verified" and result["coverage"]["vacuous"]:
        label = f"{VERDICT_LABEL[verdict]}, vacuously: no run takes the {changed} row{'s' if changed != 1 else ''} the change alters"
    elif several and verdict == "violation" and configuration is not configurations[0]:
        label += f" ({configuration['label']})"
    elif several and verdict == "verified":
        label += f", and under {len(runs) - 1} more configuration{'s' if len(runs) > 2 else ''}"
    result["verdict"], result["verdictLabel"] = model_verdict(result, verdict, label)


TOOL_RUNNERS = {"B8": run_tool_contracts, "B9": run_tool_equivalence, "B10": run_tool_contracts,
                "B11": run_tool_property, "D1": run_tool_tlc}
RUNNERS = {
    "boxoffice": {"B8": run_contracts, "B9": run_equivalence, "B10": run_contracts, "B12": run_boundaries, "D1": run_tlc},
    **{app: TOOL_RUNNERS for app in TOOL_APPS},
}


def before_classes(module):
    """The module's classes compiled from the unpatched repo, built once per run."""
    if module not in BEFORE_CLASSES:
        tmp = scratch() / f"before-{module}"
        for part in COPY:
            shutil.copytree(REPO / part, tmp / part, ignore=IGNORE)
        gradle(tmp / BUILD_ROOT, f":{module}:compileJava")  # production classes only: compileJava compiles no tests
        BEFORE_CLASSES[module] = tmp / BUILD_ROOT / module / "build/classes/java/main"
    return BEFORE_CLASSES[module]


def verifier_jar():
    """The verifier, built from examples/tools/contracts (also an included build of the Box Office Gradle project)."""
    jar = REPO / VERIFIER / "build/libs/contract-verifier-0.1.0.jar"
    if "verifier" not in BEFORE_CLASSES:
        gradle(REPO / BUILD_ROOT, "jar", "-p", str(REPO / VERIFIER))
        BEFORE_CLASSES["verifier"] = jar
    return str(jar)


def java():
    home = os.environ.get("JAVA_HOME")
    return str(Path(home) / "bin/java") if home else "java"


def gradle(build, task, *extra, check=True, allow_empty=False):
    proc = stage(f"gradle {task}", ["./gradlew", "-q", *extra, task], cwd=build)
    if check and proc.returncode != 0:
        sys.exit(f"{task} failed:\n{proc.stdout}\n{proc.stderr}")
    if proc.returncode != 0 and not proc.stdout.strip() and not allow_empty:
        sys.exit(f"{task} failed before the verifier ran:\n{proc.stderr}")
    return proc


def write_evidence(folder, output, sarif_path, result):
    """Writes the verifier's console output and its SARIF report, with the report's paths made repo-relative, and
    returns whether there was a report. A missing report is not made up: an earlier run's report is removed, so that
    the folder never shows evidence from another run, and the result records no report."""
    (folder / "verifier-output.txt").write_text(output)
    if not sarif_path.exists():
        (folder / "result.sarif").unlink(missing_ok=True)
        result["sarif"] = None
        return False
    try:
        sarif = json.loads(sarif_path.read_text())
    except json.JSONDecodeError:
        (folder / "result.sarif").unlink(missing_ok=True)
        result["sarif"] = None
        return False
    result["sarif"] = "result.sarif"
    for run_ in sarif["runs"]:
        for res in run_["results"]:
            for loc in res.get("locations", []):
                art = loc["physicalLocation"]["artifactLocation"]
                if not art["uri"].startswith("examples/"):
                    art["uri"] = f"{BUILD_ROOT}/{art['uri']}"  # the Java tool anchors to the Gradle module
    (folder / "result.sarif").write_text(json.dumps(sarif, indent=2, ensure_ascii=False) + "\n")
    return True


def failures(results_dir):
    """Failing tests in a JUnit XML results directory, as Class.method."""
    import xml.etree.ElementTree as ET
    found = set()
    for xml in results_dir.glob("*.xml"):
        for case in ET.parse(xml).getroot().iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                found.add(f"{case.get('classname').rsplit('.', 1)[-1]}.{case.get('name').removesuffix('()')}")
    return sorted(found)


def module_of(file):
    rest = file.removeprefix(BUILD_ROOT + "/")
    return rest.split("/")[0]


# Parsing the verifiers' output


def cases_total(output, symbol=None):
    """The number of cases in the symbol's contract, from the output line that names it (a module with several
    contracts prints one line each), or the first count printed."""
    lines = [l for l in output.splitlines() if symbol is None or symbol in l] or output.splitlines()
    for line in lines:
        m = re.search(r" of (\d+) cases", line) or re.search(r"\((\d+) cases,", line)
        if m:
            return int(m.group(1))
    return None


def trusted_calls(output):
    m = re.search(r"trusting (.*)\)$", output, re.M)
    return [c.strip() for c in m.group(1).split(",")] if m else []


def purity_violations(output):
    m = re.search(r"not provably pure:\n((?:  .*\n)+)", output)
    return [line.strip() for line in m.group(1).splitlines()] if m else []


def problem(output):
    m = re.search(r"cannot be verified: (.*)", output, re.S)
    return m.group(1).strip() if m else None


def capability_changes(output):
    """Added and removed capability uses (B10), as counterexample rows: the capability is the input."""
    found = []
    for m in re.finditer(r"^  (added|removed) (\w+): (.*)$", output, re.M):
        kind, capability, use = m.groups()
        found.append({"input": capability, "contract": None if kind == "added" else use,
                      "actual": use if kind == "added" else None})
    return found


def boundary_changes(output):
    """Added and removed boundary entries (B12), as counterexample rows: the bean and member are the input."""
    found = []
    for m in re.finditer(r"^  (added|removed) ([^:\n]+): (.*)$", output, re.M):
        kind, bean, entry = m.groups()
        found.append({"input": bean, "contract": None if kind == "added" else entry,
                      "actual": entry if kind == "added" else None})
    return found


def counterexamples(output):
    """Changed cases, from either verifier: `contract:/actual:` pairs (B8) or `before:/after:` pairs (B9)."""
    found = []
    pattern = re.compile(
        r"^  (\S.*)\n(?:    (?:contract|before): +(.*)\n    (?:actual|after): +(.*)|    added:    (.*)|    removed: .*\(was (.*)\))$",
        re.M)
    for m in pattern.finditer(output):
        if m.group(2) is not None:
            found.append({"input": m.group(1), "contract": m.group(2), "actual": m.group(3)})
        elif m.group(4) is not None:
            found.append({"input": m.group(1), "contract": None, "actual": m.group(4)})
        else:
            found.append({"input": m.group(1), "contract": m.group(5), "actual": None})
    return found


def excerpts(patch, subject_file, symbol=None):
    """The before and after sides of the patch's hunks in the subject file, with their context lines. When the patch
    deletes the subject file (a method moved into a new class, such as a parameter object), the after side is the
    file of the symbol's class instead."""
    after_file = subject_file
    if re.search(rf"^--- a/{re.escape(subject_file)}\n\+\+\+ /dev/null$", patch, re.M) and symbol and "/src/main/java/" in subject_file:
        root = subject_file[:subject_file.index("/src/main/java/") + len("/src/main/java/")]
        after_file = root + symbol.split("#")[0].split("$")[0].replace(".", "/") + ".java"
    wanted = {"before": subject_file, "after": after_file}
    paths = {"before": None, "after": None}
    sides = {"before": [], "after": []}
    starts = {}
    lines = patch.splitlines()
    for i, line in enumerate(lines):
        # A file's header is a `--- ` line followed by a `+++ ` one, whether or not `diff --git` lines are there.
        if line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            paths["before"] = line[len("--- a/"):] if line.startswith("--- a/") else None
        elif line.startswith("+++ ") and i > 0 and lines[i - 1].startswith("--- "):
            paths["after"] = line[len("+++ b/"):] if line.startswith("+++ b/") else None
        elif line.startswith("diff --git "):
            continue
        else:
            taken = [side for side in sides if paths[side] == wanted[side]]
            if not taken:
                continue
            if line.startswith("@@"):
                m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)", line)
                for side, number in (("before", m.group(1)), ("after", m.group(2))):
                    if side in taken:
                        starts.setdefault(side, max(int(number), 1))
                        if sides[side]:
                            sides[side].append("    // ...")
            elif line.startswith("-"):
                if "before" in taken:
                    sides["before"].append(line[1:])
            elif line.startswith("+"):
                if "after" in taken:
                    sides["after"].append(line[1:])
            elif line.startswith(" "):
                for side in taken:
                    sides[side].append(line[1:])
    if "before" not in starts or "after" not in starts:
        sys.exit(f"the patch does not change the subject file {subject_file}"
                 + (f" and {after_file}" if after_file != subject_file else ""))
    return tuple(
        {"file": wanted[side], "startLine": starts[side], "code": dedent(sides[side])} for side in ("before", "after"))


def dedent(lines):
    indent = min((len(l) - len(l.lstrip()) for l in lines if l.strip()), default=0)
    return "\n".join(l[indent:] for l in lines) + "\n"


# Rendering


def render_example(folder, ex, res, snap=None):
    """The example's page, from its result as recorded and the example's authored text. `snap` is the result's
    snapshot() (computed when not given): a page whose result is stale, or whose evidence is not the run's, says so
    before anything else, and the verdict's explanation is the author's only where the run gave the expected result."""
    snap = snap or snapshot(folder, ex, res)
    file_name = Path(ex["subject"]["file"]).name
    source_link = f"../../{ex['subject']['file']}"
    symbol = ex["subject"]["symbol"].rsplit(".", 1)[-1]
    change = ex["change"]
    lines = [
        "<!-- Generated by examples/tools/build.py from example.json and the verifier's output. Edit example.json. -->",
        f"# {ex['id']} · {ex['title']}",
        "",
        "[← All examples](../README.md)",
        "",
        "| Verdict | Categories | Severity if shipped | Change | Verified unit | Approach |",
        "|---|---|---|---|---|---|",
        f"| **{res['verdictLabel']}** | {', '.join(ex['categories'])} | {ex['severity']} "
        f"| {change['kind']}, behaviour change {'intended' if change['behaviourChangeIntended'] else 'not intended'} "
        f"| [`{symbol}`]({source_link}) "
        f"| [{ex['approach']['id']}: {ex['approach']['name']}](../../{ex['approach']['tool']}/README.md) |",
        "",
        f"> {ex['summary']}",
        "",
        *snapshot_banner(ex, snap),
        f"Tags: {tag_links(ex['tags'])}",
        "",
        "## The change",
        "",
        change["description"],
        "",
    ]
    if change.get("intendedInputs"):
        lines += [
            f"The developer declares which inputs the change is meant to affect: `{change['intendedInputs']}`. "
            "The verifier proves that every other input behaves as before, or shows one that does not.",
            "",
        ]
    if change.get("previousSymbol") or change.get("previousArguments"):
        previous = change.get("previousSymbol") or symbol
        arguments = change.get("previousArguments", "")
        if arguments.startswith("new "):
            # The previous version's receiver, built from the new parameters, comes first.
            receiver, _, rest = arguments.partition(")")
            called = f"`{previous}({rest.strip(', ')})` on `{receiver})`"
            lines += [
                "The record the method belongs to changed, so the developer states how the previous version's receiver "
                f"is built from the new parameters, and how it is called: {called}. The verifier proves that on every "
                "input, the new method agrees with the previous one called that way, or shows one on which it does not.",
                "",
            ]
        else:
            lines += [
                "The method's signature changed, so the developer states how the previous version is called from the "
                f"new parameters: `{previous}({arguments})`. The verifier proves that on every "
                "input, the new method agrees with the previous one called that way, or shows one on which it does not.",
                "",
            ]
    if change.get("resultsAgreeWhen"):
        previous = change.get("previousSymbol") or symbol
        lines += [
            "The result changed its type or its meaning, so the developer states how the two results are related, "
            f"`previous` being the result of `{previous}` and `result` the new method's: `{change['resultsAgreeWhen']}`. "
            "The verifier proves that the relation holds on every input where both versions return, and that they "
            "throw alike where they throw, or shows an input on which they do not.",
            "",
        ]
    lines += [
        f"**Before** ([`{file_name}`]({source_link}), line {res['before']['startLine']}):",
        "",
        "```java",
        res["before"]["code"].rstrip("\n"),
        "```",
        "",
        "**After:**",
        "",
        "```java",
        res["after"]["code"].rstrip("\n"),
        "```",
        "",
        "<details><summary>Patch</summary>",
        "",
        "```diff",
        (folder / change["patch"]).read_text().rstrip("\n"),
        "```",
        "",
        "</details>",
        "",
        "## What the verifier found",
        "",
    ]
    lines += no_verdict_findings(res) if res["verdict"] is None else FINDINGS[ex["approach"]["id"]](ex, res)
    if res.get("stateMachine"):
        lines += [
            "",
            "The state machine the patched code implements, drawn from its derived contract (`jvmcontract statemachine`); "
            "a state with no way in or no way out is marked:",
            "",
            "```mermaid",
            res["stateMachine"].rstrip("\n"),
            "```",
        ]
    lines += [
        "",
        "## Would the existing tests have caught it?",
        "",
        tests_text(res),
        "",
        "## Why it matters",
        "",
        ex["risk"],
        "",
        *explanation_lines(ex, res),
        "## What to do",
        "",
        ex["resolution"],
        "",
    ]
    if ex.get("notes"):
        lines += ["## Notes", ""] + [f"- {note}" for note in ex["notes"]] + [""]
    lines += [
        "## Evidence",
        "",
    ]
    if res["trustedCalls"]:
        lines += [
            "The proof trusted these JDK APIs to be pure: " + ", ".join(f"`{c}`" for c in res["trustedCalls"]) + ".",
            "",
        ]
    several = len(res.get("properties") or []) > 1
    if several:
        lines += ["How each verdict was reached:", ""] + [
            f"- Property {n}: {r['proof'] or r['problem'] or 'the verifier says nothing'}." for n, r in enumerate(res["properties"], 1)] + [""]
    elif res.get("proof"):
        lines += [f"How the verdict was reached: {res['proof']}.", ""]
    if (res.get("coverage") or {}).get("reason"):
        lines += [f"**The proof is vacuous:** {res['coverage']['reason']}. The tool found this by running the statement with the "
                  "calls replaced by the assertion's failure: an input that reaches the calls would violate it, and none does.", ""]
    lines += snapshot_lines(ex, res, snap)
    lines += details("Verifier output", "text", (folder / res["output"]).read_text())
    if several:
        for n, r in enumerate(res["properties"], 1):
            if r.get("statement"):
                lines += details(f"The statement the prover checked for property {n} (generated harness)", "java",
                                 (folder / r["statement"]).read_text())
    elif res.get("statement"):
        lines += details("The statement the prover checked (generated harness)", "java",
                         (folder / res["statement"]).read_text())
    if res.get("sarif"):
        lines += details("SARIF report (as uploaded to GitHub code scanning or SonarQube)", "json",
                         (folder / res["sarif"]).read_text())
    if ex.get("provenance"):
        lines += [f"**Provenance:** {ex['provenance']}", ""]
    for ref in ex.get("references", []):
        lines += [f"- [{ref['title']}]({ref['url']})"]
    lines += [
        "## Reproduce",
        "",
        "```bash",
        f"python3 examples/tools/build.py {ex['id']}",
        "```",
        "",
        "This applies `change.patch` to a temporary copy of the repo, runs the verifier on it, and rewrites this page.",
        "",
    ]
    return "\n".join(lines)


def observed_expectation(res):
    """Whether the run gave the example's expected result: the result's `expectation`, or for a result recorded
    before it had one, its `matchesExpected`."""
    return res.get("expectation") or ("yes" if res.get("matchesExpected") else "no")


def expected_label(ex):
    expected = ex["expected"]
    return VERDICT_LABEL[expected["verdict"]] + (", vacuously" if expected.get("vacuous") else "")


def explanation_lines(ex, res):
    """The author's explanation of the expected verdict. It is the reason for the verdict only when the run gave
    that verdict; otherwise it is labelled as what the example expected, and the run's own result stands apart."""
    if observed_expectation(res) == "yes":
        return ["## Why the verdict is right", "", ex["explanation"], ""]
    observed = ("the run has no verdict" if res["verdict"] is None
                else f"the run's result is **{res['verdictLabel']}**")
    return ["## What the example expected", "",
            f"The example expects **{expected_label(ex)}**, and {observed}. The author's explanation below is of the "
            "expected result, so it is not a reason for this one: what the run found is under "
            "[What the verifier found](#what-the-verifier-found) and Evidence.", "",
            *[f"> {line}" if line else ">" for line in ex["explanation"].split("\n")], ""]


def snapshot_banner(ex, snap):
    """The warning a page leads with when its result is no longer the current files' result, or its evidence is not
    the run's: nothing for a current or unknown snapshot with its evidence intact."""
    lines = []
    if snap["state"] == "stale":
        lines += [f"> ⚠ **Stale result:** {'; '.join(snap['reasons'])} since this run. The verdict on this page is "
                  f"that run's, not a verdict on the current files. `python3 examples/tools/build.py {ex['id']}` runs it again.", ""]
    if snap["evidence"]:
        lines += [f"> ⚠ **The evidence is not the run's:** {'; '.join(snap['evidence'])}.", ""]
    return lines


def snapshot_lines(ex, res, snap):
    """Under Evidence: which run the page renders, and whether its inputs still match the current files."""
    if snap["state"] == "unknown":
        return ["This result was recorded before runs fingerprinted their inputs, so whether it still matches the "
                "current patch and sources is not known.", ""]
    claim, attempt = res["claim"], res.get("attempt") or {}
    run = f"attempt `{attempt.get('id')}` at claim `{claim['id']}`"
    job = (attempt.get("pipeline") or {}).get("jobId")
    if job:
        run += f", in pipeline job `{job}`"
    if snap["state"] == "current":
        text = (f"This page renders {run}. Its claim is still the one the current files make: the patch, the sources it "
                "applies to, what is checked and the scope are those the run fingerprinted.")
    else:
        text = f"This page renders {run}, which is stale: {'; '.join(snap['reasons'])}."
    text += (" The files below are the run's bundle." if res.get("bundle") and not snap["evidence"]
             else " The files below are not all the run's bundle." if snap["evidence"] else "")
    return [text, ""]


def no_verdict_findings(res):
    """What a page says of a run that has no verdict: how the run ended, and that nothing is concluded from it."""
    execution = res["execution"]
    return [f"The verifier's run did not complete (`{execution['status']}`): {execution['reason']}. There is no verdict, "
            "so nothing is concluded about the change, and the example's expectation is not evaluated. The output it left "
            "is under Evidence."]


def findings_contracts(ex, res):
    if res["verdict"] == "violation":
        out = [
            f"The behaviour changed for {len(res['counterexamples'])} of the {res['casesTotal']} possible inputs. "
            "Each row is a concrete input that shows the difference:",
            "",
            "| Input | The contract says | The code now does |",
            "|---|---|---|",
        ]
        for c in res["counterexamples"]:
            out.append(f"| {code(c['input'])} | {code(c['contract']) if c['contract'] else '*(new input)*'} "
                       f"| {code(c['actual']) if c['actual'] else '*(input removed)*'} |")
        return out
    if res["verdict"] == "unverifiable":
        return ["The verifier refused to produce a verdict, because the method is no longer provably pure:", ""] + [
            f"- {code(v)}" for v in res["purityViolations"]]
    out = [f"All {res['casesTotal']} possible inputs give the same outcome as the contract."]
    if res["contractDiff"]:
        out += [
            "",
            "Because the change was intended, the developer regenerated the contract. "
            "This diff is what the reviewer approves:",
            "",
            "```diff",
            res["contractDiff"].rstrip("\n"),
            "```",
        ]
    else:
        out += ["", "The contract file is unchanged, so the pull request contains code changes only."]
    return out


def prover_text(res, whose):
    """How the proof was done, by the checker the proof line names: JBMC's one formula, or the tool's own checker's paths."""
    if (res.get("proof") or "").startswith("jvmcontract's own checker"):
        return ("The tool's own checker ran the harness symbolically, path by path, with its bundled SAT solver deciding "
                "at each branch which sides are feasible, and no feasible path reaches the assertion:")
    return (f"JBMC turned the statement into a satisfiability problem over the bytecode{' ' + whose if whose else ''} "
            "and showed that it has no solution:")


# Where a witness was replayed on both versions (a result's `replay.by`), as the page says it.
REPLAYED = {"interpreter": "in jvmcontract's bytecode interpreter", "jvm": "on the JVM"}


def replayed_where(res):
    """Where the result's witness was replayed, from its `replay` record, or for a result recorded before there was
    one, from its proof line; None when neither says."""
    by = (res.get("replay") or {}).get("by")
    if by is None:
        proof = res.get("proof") or ""
        by = "interpreter" if "replayed in the interpreter" in proof else "jvm" if "replayed on the JVM" in proof else None
    return REPLAYED.get(by)


def findings_equivalence(ex, res):
    intended = ex["change"].get("intendedInputs")
    domain = res.get("domain") or "all inputs"
    if res["verdict"] == "violation":
        where = replayed_where(res)
        out = [
            "The two versions disagree. The prover found this input"
            + (" outside the declared change" if intended else "")
            + (f", and the verifier replayed it {where} against both versions:" if where else
               ", on which the two versions do this:"),
            "",
            "| Input | Before | After |",
            "|---|---|---|",
        ]
        for c in res["counterexamples"]:
            out.append(f"| {code(c['input'])} | {code(c['contract'])} | {code(c['actual'])} |")
        out += ["", f"One disagreeing input is enough to fail the build. The domain is `{domain}`; the search tries "
                    "small values first so that the witness is readable, and would have covered all of it."]
        return out
    if res["verdict"] == "unverifiable":
        return ["The verifier refused to produce a verdict:", "", f"- {code(res['problem'] or 'unknown')}"]
    previous = ex["change"].get("previousArguments")
    relation = ex["change"].get("resultsAgreeWhen")
    return [
        f"For every input{' where `' + intended + '` is false' if intended else ''}, the new code returns "
        + (f"a result related to the old code's by `{relation}`" if relation else "what the old code returned")
        + ", or throws what it threw"
        + (f", the old code being called with the arguments `{previous}` computed from the new parameters" if previous else "")
        + ".",
        "",
        f"This is a proof over the whole domain ({domain}), not a sample. " + prover_text(res, "of both versions")
        + " no input exists on which they differ.",
    ]


def findings_capabilities(ex, res):
    if res["verdict"] == "violation":
        out = [
            f"The module's bytecode now reaches {len(res['counterexamples'])} capabilit"
            f"{'y' if len(res['counterexamples']) == 1 else 'ies'} differently from its contract:",
            "",
            "| Capability | The contract lists | The bytecode now has |",
            "|---|---|---|",
        ]
        for c in res["counterexamples"]:
            out.append(f"| {code(c['input'])} | {code(c['contract']) if c['contract'] else '*(nothing)*'} "
                       f"| {code(c['actual']) if c['actual'] else '*(removed)*'} |")
        out += ["", "Every call from the module's compiled code to a JDK entry point of a capability is listed, "
                    "with the method that makes it, so the finding points at the exact call site."]
        return out
    if res["verdict"] == "unverifiable":
        return ["The verifier refused to produce a verdict:", "", f"- {code(res['problem'] or 'unknown')}"]
    out = [f"The capability contract is unchanged: the module ({res['domain']}) reaches exactly the JDK capabilities "
           "and libraries it did before."]
    if res["contractDiff"]:
        out += ["", "Because the change was intended, the developer regenerated the contracts. This diff is what the "
                    "reviewer approves:", "", "```diff", res["contractDiff"].rstrip("\n"), "```"]
    return out


def findings_boundaries(ex, res):
    if res["verdict"] == "violation":
        out = [
            f"The module's boundaries differ from their contract in {len(res['counterexamples'])} "
            f"line{'s' if len(res['counterexamples']) != 1 else ''}:",
            "",
            "| Bean | The contract has | The bytecode now has |",
            "|---|---|---|",
        ]
        for c in res["counterexamples"]:
            out.append(f"| {code(c['input'])} | {code(c['contract']) if c['contract'] else '*(nothing)*'} "
                       f"| {code(c['actual']) if c['actual'] else '*(removed)*'} |")
        out += ["", "A line is a route, listener, schedule, bean definition or configuration key, the advice on a "
                    "member, a property of a wire type, or a `!` line where an annotation does not do what it says; "
                    "a member's line changes with its signature and parameter annotations."]
        if res.get("newProblems"):
            out += ["", "The change was intended, so the developer regenerated the contract, and the `!` lines above "
                        "are new in it: the regenerated contract records a problem the old one did not have. The "
                        "regeneration is the diff a reviewer approves:", "", "```diff", res["contractDiff"].rstrip("\n"),
                    "```"]
        return out
    if res["verdict"] == "unverifiable":
        return ["The verifier refused to produce a verdict:", "", f"- {code(res['problem'] or 'unknown')}"]
    out = [f"The boundary contract is unchanged: the module ({res['domain']}) has exactly the entry points, advice "
           "and problems it had before."]
    if res["contractDiff"]:
        out += ["", "Because the change was intended, the developer regenerated the contract. This diff is what the "
                    "reviewer approves:", "", "```diff", res["contractDiff"].rstrip("\n"), "```"]
    return out


def property_states(prop):
    """What a property says, as a phrase: that its assertion holds, or that the method returns, with its throws
    clauses, on the inputs its assumption admits."""
    assume, throws = prop.get("assume"), prop.get("throws") or []
    holds = f"`{prop['assert']}` holds" if prop.get("assert") else "the method returns"
    clauses = "".join(f", and throws `{t.split(' when ', 1)[0]}` exactly when `{t.split(' when ', 1)[1]}`" for t in throws)
    return holds + (f" where `{assume}`" if assume else " on every input") + clauses


PROPERTY_VERDICT = {"verified": "✓ holds", "violation": "✗ refuted", "unverifiable": "⚠ unresolved"}


def findings_properties(ex, res):
    """The findings of a target with several properties: each proved or refuted on its own, the change passing only
    when every one holds."""
    props = res["properties"]
    out = [f"The module declares {len(props)} properties of `{ex['subject']['symbol'].split('.')[-1]}`, and the tool "
           "proves each on its own, in its own harness. Every one is required: one refuted property fails the change, "
           "and it passes only when all of them hold.", "",
           "| | The property | Verdict |", "|---|---|---|"]
    for n, r in enumerate(props, 1):
        vacuous = ", vacuously" if r.get("vacuous") else ""
        out.append(f"| {n} | That {property_states(r).replace('|', chr(92) + '|')} | {PROPERTY_VERDICT[r['verdict']]}{vacuous} |")
    refuted = [(n, r) for n, r in enumerate(props, 1) if r["verdict"] == "violation"]
    if refuted:
        with_expected = any((r["counterexample"] or {}).get("expected") for _, r in refuted)
        where = {REPLAYED.get((r.get("replay") or {}).get("by")) for _, r in refuted} - {None}
        out += ["", "The prover found an input for each refuted property, and the tool replayed it on the method"
                + (f" {where.pop()}" if len(where) == 1 else "") + " to show what it does:", "",
                "| Property | Input | The method's outcome |" + (" What the property requires |" if with_expected else ""),
                "|---|---|---|" + ("---|" if with_expected else "")]
        for n, r in refuted:
            c = r["counterexample"]
            out.append(f"| {n} | {code(c['input'])} | {code(c['actual'])} |"
                       + (f" {c.get('expected') or 'the assertion'} |" if with_expected else ""))
    unresolved = [(n, r) for n, r in enumerate(props, 1) if r["verdict"] == "unverifiable"]
    if unresolved:
        out += ["", "The verifier gave no verdict on " + ("these properties" if len(unresolved) > 1 else "this property")
                + ", which stay open whatever the others show:", ""]
        out += [f"- Property {n}: {code(r['problem'] or 'unknown')}" for n, r in unresolved]
    if res["verdict"] == "verified":
        out += ["", f"Each is a proof over the whole domain ({res.get('domain') or 'all inputs'}), not a sample. "
                + prover_text(res, "") + " no input violates any of them."]
    return out


def findings_property(ex, res):
    if len(res.get("properties") or []) > 1:
        return findings_properties(ex, res)
    prop = res.get("property") or {}
    assume = prop.get("assume")
    throws = prop.get("throws") or []
    domain = res.get("domain") or "all inputs"
    where = f" on every input where `{assume}` holds" if assume else " on every input"
    clauses = "".join(f", and throws `{t.split(' when ', 1)[0]}` exactly when `{t.split(' when ', 1)[1]}`" for t in throws)
    holds = f"`{prop['assert']}` holds" if prop.get("assert") else "the method returns"
    if res["verdict"] == "violation":
        with_expected = any(c.get("expected") for c in res["counterexamples"])
        out = [
            (f"The property does not hold: that {holds}{where}{clauses}." if throws
             else f"The property `{prop.get('assert')}` does not hold{where}.")
            + " The prover found this input, and the tool replayed it on the method to show what it does:",
            "",
            "| Input | The method's outcome |" + (" What the property requires |" if with_expected else ""),
            "|---|---|" + ("---|" if with_expected else ""),
        ]
        for c in res["counterexamples"]:
            out.append(f"| {code(c['input'])} | {code(c['actual'])} |" + (f" {c.get('expected') or 'the assertion'} |" if with_expected else ""))
        out += ["", f"One input is enough to fail the build. The domain is `{domain}`; the search tries small values "
                    "first so that the witness is readable, and would have covered all of it."]
        return out
    if res["verdict"] == "unverifiable":
        return ["The verifier refused to produce a verdict:", "", f"- {code(res['problem'] or 'unknown')}"]
    return [
        (f"The method returns without throwing and `{prop.get('assert')}` holds{where}{clauses}." if prop.get("assert")
         else f"The method returns without throwing{where}{clauses}."),
        "",
        f"This is a proof over the whole domain ({domain}), not a sample. " + prover_text(res, "")
        + " no input violates the property.",
    ]


MODELS = {
    "boxoffice": {
        "parts": "the two customers, the two services, Kafka and the clock",
        "initial": "every seat available, no holds, orders or payments, every queue empty, the clock at 0",
        "actions": ACTIONS,
        "invariants": INVARIANTS,
        "machine": "The order state machine inside the model is generated from the behavioural contract of the "
                   "patched code, so the model checks the decisions the services really make.",
    },
}


def tlc_trace_lines(model, trace, initial, starts_anywhere=False, recorded=False):
    """A counterexample as a numbered list: each step one action of one part of the system, or, for a recorded run
    held to the model, the next state the implementation recorded."""
    out = []
    for step in trace:
        what = model["actions"].get(step["action"], step["action"])
        bookkeeping = {"run", "step", "scenario"} if recorded else set()
        changes = ", ".join(f"`{k} = {v}`" for k, v in step["changes"].items() if k not in bookkeeping) or "*(no change)*"
        if step["step"] == 1 and recorded:
            out.append(f"{step['step']}. **Start of the recorded run** `{step['changes'].get('scenario', '')}`, {initial}: {changes}")
        elif step["step"] == 1 and not starts_anywhere:
            out.append(f"{step['step']}. **Initial state**: {initial}.")
        elif step["step"] == 1:
            out.append(f"{step['step']}. **Starting state**, {initial}: {changes}")
        else:
            out.append(f"{step['step']}. **{step['action']}**, {what}. {changes}")
    return out


def findings_tlc(ex, res):
    model = model_of(ex)
    configurations = {c["label"]: c for c in tlc_configurations(model)}
    runs = res.get("configurations") or []
    several = len(runs) > 1
    headline = next((r for r in runs if r["verdict"] == res["verdict"] and r["invariant"] == res.get("invariant")), None) if several else None
    configuration = configurations[headline["label"]] if headline else configurations[next(iter(configurations))]
    out = []
    if several:
        out += [f"The model is checked under {len(runs)} configurations, and the verdict is the first that fails:", "",
                "| Configuration | What it checks | Model | Result |", "|---|---|---|---|"]
        for run in runs:
            out.append(f"| {run['label']} (`{run['cfg']}`) | {configurations[run['label']]['what']} | {run['domain']} | {run['summary']} |")
        out.append("")
    under = f" under {configuration['label']}" if several else ""
    changed = unauthorized(res)
    if changed:
        out += contract_connection_lines(res) + [""]
    if res["verdict"] == "violation" and res.get("trace"):
        inv = res["invariant"]
        kind = res.get("violationKind")
        steps = len(res["trace"])
        if inv == "Deadlock":
            found = (f"TLC found a run of the system{under}, {steps} steps long, after which no action of any part is "
                     f"enabled: a **deadlock**, {model['invariants'].get(inv, 'every part waits for another')}.")
        elif kind == "temporal":
            found = (f"TLC found a run of the system{under} that violates the temporal property **{inv}** ({model['invariants'].get(inv, inv)}): "
                     f"after the {steps} steps below, the system {res['forever']}, and the property never comes true. "
                     "The run respects every fairness condition the model assumes; the parts that could act, do.")
        elif kind == "action":
            found = (f"TLC found a run of the system{under}, {steps} steps long, whose last step violates the action property "
                     f"**{inv}** ({model['invariants'].get(inv, inv)}).")
        elif steps == 1:
            found = (f"TLC found a state{under} that violates the invariant **{inv}** ({model['invariants'].get(inv, inv)}) "
                     "before any step is taken: the invariant the check starts from does not imply it. The state:")
        else:
            found = (f"TLC found a run of the system{under}, {steps} steps long, that violates the invariant "
                     f"**{inv}** ({model['invariants'].get(inv, inv)}).")
        each = " Each step is one action of one part of the system:"
        if configuration.get("recorded"):
            each = " Each step is the next state the implementation recorded:"
        out += [found + (each if steps > 1 else ""), ""]
        out += tlc_trace_lines(model, res["trace"], configuration["initial"], configuration.get("startsAnywhere", False),
                               configuration.get("recorded", False))
        out += ["", configuration.get("explored") or
                    f"The model is small ({res['domain']}), which is what keeps the trace readable. TLC explored every "
                    f"interleaving of {model['parts']} within those bounds."]
        for run in runs:
            if run["verdict"] != "violation" or run is headline:
                continue
            c = configurations[run["label"]]
            inv = run["invariant"]
            what = {"temporal": "temporal property", "action": "action property"}.get(run["violationKind"], "invariant")
            if inv == res["invariant"] and run["trace"] == res["trace"] and run["forever"] == res["forever"]:
                out += ["", f"Under {run['label']} TLC found the same run, and reported it the same way."]
                continue
            out += ["", f"<details><summary>The counterexample under {run['label']}: {what} <b>{inv}</b>, "
                        f"{'a starting state' if len(run['trace']) == 1 else str(len(run['trace'])) + ' steps'}</summary>", "",
                    f"{what.capitalize()} **{inv}**: {model['invariants'].get(inv, inv)}."
                    + (f" After the last step the system {run['forever']}." if run["forever"] else ""), ""]
            out += tlc_trace_lines(model, run["trace"], c["initial"], c.get("startsAnywhere", False), c.get("recorded", False))
            out += ["", "</details>"]
        return out + coverage_lines(res) + ([] if changed else contract_connection_lines(res, "")) + checkpoint_lines(res)
    if res["verdict"] == "unverifiable":
        return out + ["TLC produced no verdict:", "", f"- {code(res['problem'] or 'unknown')}"]
    checked = "Every invariant holds in every reachable state of the model"
    summary = res.get("modelSummary") or res["verdictLabel"]  # TLC's own label, beside a contract changed unasked
    if "then forever" in summary or " and properties " in summary:
        checked = ("Every invariant holds in every reachable state of the model, and every temporal property holds of every "
                   "behaviour, the infinite ones included")
    out += [
        f"{checked}{under}: {res['statesExplored']:,} distinct states, "
        f"which is every interleaving of {model['parts']} within the model's bounds ({res['domain']}).",
        "",
        model["machine"],
    ]
    if several:
        out += ["", "The other configurations hold too, as the table says: " + "; ".join(
            f"{run['label']}, {run['statesExplored']:,} states" for run in runs[1:] if run.get("statesExplored") is not None) + "."]
    return out + coverage_lines(res) + ([] if changed else contract_connection_lines(res, "")) + checkpoint_lines(res)


def contract_connection_lines(res, lead=None):
    """Where the model's generated operators come from: the contract each was generated from, derived from the patched
    classes in the run, and how it stands to the committed one. Leads the findings when the change altered a contract
    without an intended behaviour change, with the diff; follows them otherwise. A result recorded before the runner
    tied every operator to the patched classes has no record, and nothing is said."""
    connections = res.get("modelContracts")
    if not connections:
        return []
    short = lambda symbol: "`" + symbol.rsplit(".", 1)[-1] + "`"
    changed = unauthorized(res)
    out = [] if lead is None else [lead]
    if changed:
        rows = sum(c["rowsChanged"] for c in changed)
        out += [f"**The change alters a rule it is not meant to.** It is not meant to change behaviour, but the contract "
                f"derived from the patched classes differs from the committed one in {rows} row{'s' if rows != 1 else ''} of "
                + ", ".join(short(c["symbol"]) for c in changed) + ". The model was checked on the rule that was built, "
                "and the difference is a finding on its own, whatever TLC found: a reviewer never saw it."]
        if res.get("contractDiff"):
            out += ["", "```diff", res["contractDiff"].rstrip("\n"), "```"]
        if res.get("modelVerdict") == "verified":
            out += ["", "TLC's verdict on the patched rule: " + res["modelSummary"] + "."]
        return out
    out += ["**Where the model's rules come from.** Each operator the model checks is generated from the contract derived "
            "from the patched classes in this run:", ""]
    for c in connections:
        how = ("the committed contract, which the patched classes still match" if c["connection"] == "verified" else
               f"the regenerated contract, {c['rowsChanged']} row{'s' if c['rowsChanged'] != 1 else ''} from the committed one, "
               "as the change intends" if c["rowsChanged"] else "the regenerated contract, with the committed one's rows")
        out.append(f"- {short(c['symbol'])} (`{c['operator']}`): {how}")
    return out


def coverage_lines(res):
    """What the verdict rests on: the rows of the generated operators a step of the model takes under each
    configuration, the rows the change alters and which runs take them, and the rows no step takes."""
    cov = res.get("coverage")
    # A configuration that counts no coverage (the recorded runs: TLC attributes none to an action property) is left out.
    configs = [c for c in (cov or {}).get("configurations", []) if c.get("counted", True) and (c["operators"] or not c["finished"])]
    # Results recorded before the coverage status have no `listed`: every operator they hold was counted.
    finished = [c for c in configs if c["finished"] and any(op.get("listed", True) for op in c["operators"])]
    short = lambda symbol: "`" + symbol.rsplit(".", 1)[-1] + "`"
    if cov and not finished:
        return uncounted_coverage_lines(cov, short)
    if not cov:
        return []
    def cell(c, symbol):
        op = next((op for op in c["operators"] if op["symbol"] == symbol), None)
        return f"{op['reached']} of {op['total']}" if op and op.get("listed", True) else "not counted"
    out = ["", "**What the verdict rests on.** TLC counted how often a step of the model took each row of the generated "
               "operators. A row no step takes is one the model says nothing about, whatever the verdict."]
    operators = finished[0]["operators"]
    if len(configs) > 1:
        out += ["", "| Configuration | " + " | ".join(f"Rows of {short(op['symbol'])} taken" for op in operators) + " |",
                "|---|" + "---|" * len(operators)]
        for c in configs:
            note = "" if c["fromRuns"] else " (from the states the invariant admits, not from a run)"
            cells = [cell(c, op["symbol"]) for op in operators] if c["finished"] else [unfinished_cell(c)] * len(operators)
            out.append(f"| {c['label']}{note} | " + " | ".join(cells) + " |")
    else:
        out += ["", "Rows taken: " + "; ".join(f"{cell(finished[0], op['symbol'])} of {short(op['symbol'])}" for op in operators) + "."]
    changed = cov["changedRows"]
    stopped = [c["label"] for c in configs if not c["finished"]]
    # A run that ended without a verdict did not stop at a counterexample; results recorded before the runs' verdicts
    # were kept here had only counterexamples among their unfinished runs.
    no_verdict = [c for c in configs if not c["finished"] and "verdict" in c and c["verdict"] != "violation"]
    at_counterexample = [c["label"] for c in configs if not c["finished"] and c not in no_verdict]
    if changed:
        from_runs = {c["label"] for c in configs if c["fromRuns"]}
        nulls = f", and {cov['nullRows']} with a null argument, which the model leaves out" if cov.get("nullRows") else ""
        out += ["", f"The change alters {len(changed)} row{'s' if len(changed) != 1 else ''} of the contract{nulls}:", ""]
        for row in changed:
            under, unknown = row["takenUnder"], row.get("unknownUnder") or []
            taken = ", ".join(([f"taken under {', '.join(under)}"] if under else [])
                              + ([f"not counted under {', '.join(unknown)}"] if unknown else [])) \
                or ("taken by no run that finished" if stopped else "taken by no run")
            out.append(f"- {code(row['case'])}: {code(row['before']) if row['before'] else 'a new row'} → {code(row['after'])}, {taken}")
        deciding = [row for row in changed if not row["after"].startswith("throws ")]
        throwing = len(changed) - len(deciding)
        by_a_run = [row for row in deciding if set(row["takenUnder"]) & from_runs]
        only_admitted = [row for row in deciding if row["takenUnder"] and not set(row["takenUnder"]) & from_runs]
        if at_counterexample:
            out += ["", f"The run under {', '.join(at_counterexample)} stopped at its counterexample, the steps above, and its counts are left out: "
                        "the verdict rests on the counterexample."]
        if no_verdict:
            out += ["", f"The run under {', '.join(c['label'] for c in no_verdict)} ended without a verdict "
                        f"({'; '.join(c.get('reason') or 'no reason given' for c in no_verdict)}), and its counts are left out: "
                        "nothing is known about the rows it would have taken."]
        if stopped:
            pass  # the sentences above say what the verdict rests on
        elif cov["vacuous"]:
            why = (" Only the inductive step takes " + ("them" if len(only_admitted) == len(deciding) else f"{len(only_admitted)} of them")
                   + ", from states the invariant admits rather than from a run; that it found nothing says the invariant held one step on, no more."
                   if only_admitted else "")
            out += ["", f"**No run of the model takes any of them.**{why} The verdict is about the model as it was, and says nothing about the change."]
        elif not deciding:
            out += ["", f"{'All' if throwing > 1 else 'The one'} row{'s' if throwing > 1 else ''} the change alters throw{'' if throwing > 1 else 's'}, "
                        "and no run takes them: that is what a row that throws asks. Whether no run can is for an invariant over the model's "
                        "events to say, not for coverage, which counts the steps taken."]
        elif len(by_a_run) == len(deciding):
            out += ["", "Runs of the model take every row the change alters" + (f" that decides; the {throwing} that throw are taken by no run, as they must not be" if throwing else "") + ": the verdict rests on the change."]
        else:
            out += ["", f"Runs of the model take {len(by_a_run)} of the {len(deciding)} rows the change alters{' that decide' if throwing else ''}; "
                        "the verdict rests on those, and says nothing about the others."]
        uncounted = [c for c in configs if c["finished"] and c.get("coverageStatus", "complete") != "complete"]
        if uncounted and not stopped:
            out += ["", "**Some of it is not known.** " + "; ".join(f"Under {c['label']}, {c['coverageReason']}" for c in uncounted)
                    + ". A row nobody counted is not a row no step takes, so the verdict is not called vacuous on that evidence."]
    primary = finished[0]
    never = [(op["symbol"], op["never"]) for op in primary["operators"] if op["never"]]
    if never:
        out += ["", f"<details><summary>Rows no step takes under {primary['label']}</summary>", ""]
        for symbol, rows in never:
            out += [f"`{symbol}`:", "", "```", *rows, "```", ""]
        out += ["</details>"]
    return out


def checkpoint_lines(res):
    """Which configurations' results this run did not make: an earlier run's, kept under the same inputs."""
    reused = [c for c in res.get("checkpoints") or [] if c["reused"]]
    if not reused:
        return []
    return ["", "**Results reused.** " + "; ".join(
        f"Under {c['label']}, TLC was not run again: the result is the one recorded"
        f"{' at ' + c['recordedAt'] if c.get('recordedAt') else ''} by an earlier run whose inputs, the model's modules "
        f"and configurations, the generated operators, the standard modules, the command and the tools, were the same "
        f"(fingerprint `{c['fingerprint'][:12]}`)" for c in reused) + "."]


def unfinished_cell(c):
    """The table cell of a configuration whose run did not finish, by how it ended."""
    if "verdict" not in c or c["verdict"] == "violation":
        return "stopped at the counterexample"
    return {"timed-out": "no verdict: timed out", "killed": "no verdict: killed"}.get(c.get("status"), "no verdict")


def uncounted_coverage_lines(cov, short):
    """When no configuration's run both finished and had its coverage read: nothing for a run that stopped at a
    counterexample (the verdict rests on it), and otherwise what is missing, so that no reader takes a row nobody
    counted for one no step takes. Results recorded before the coverage status had nothing to say here."""
    if "status" not in cov:
        return []
    counted = [c for c in cov.get("configurations", []) if c.get("counted", True) and c["finished"]]
    if not counted:
        return []
    changed = cov["changedRows"]
    rows = (f" Whether a run takes the {len(changed)} row{'s' if len(changed) != 1 else ''} the change alters is not known."
            if changed else "")
    return ["", "**What the verdict rests on is not known.** TLC was asked to count how often a step of the model took each "
                "row of the generated operators, but " + "; ".join(f"under {c['label']}, {c['coverageReason']}" for c in counted)
            + f". A row nobody counted is not a row no step takes, so the verdict is not called vacuous.{rows}"]


FINDINGS = {"B8": findings_contracts, "B9": findings_equivalence, "B10": findings_capabilities, "B12": findings_boundaries,
            "B11": findings_property, "D1": findings_tlc}


def tests_text(res):
    t = res["existingTests"]
    if t["passed"] and res["verdict"] is None:
        return f"Every existing unit test passes (`{t['task']}`, run against the patched code); with no verdict, whether they should is open."
    if t["passed"]:
        verdict = "No: every existing unit test passes" if res["verdict"] != "verified" else "Every existing unit test passes, as it should"
        return f"{verdict} (`{t['task']}`, run against the patched code)."
    names = ", ".join(f"`{f}`" for f in t["failures"]) or "a test"
    return (f"Yes, in this repo: {names} fails (`{t['task']}`). That test was written for this property. "
            "The contract needed no one to anticipate it.")


def tests_cell(res):
    t = res["existingTests"]
    if res["verdict"] is None:
        return "pass" if t["passed"] else "fail"
    if res["verdict"] == "verified":
        return "pass"
    return "caught" if not t["passed"] else "**missed**"


def details(summary, lang, text):
    return [f"<details><summary>{summary}</summary>", "", f"```{lang}", text.rstrip("\n"), "```", "", "</details>", ""]


def code(text):
    return "`" + text.replace("|", "\\|") + "`"


def render_index(folders):
    """The router: the table of every example and the examples by tag in examples/README.md, and index.json."""
    examples = []
    for folder in folders:
        ex = load_example(folder)
        result_file = folder / "result.json"
        res = json.loads(result_file.read_text()) if ex["origin"] == "constructed" and result_file.exists() else None
        examples.append((folder, ex, res))
    vocabulary = tag_vocabulary()
    rows, index = [], []
    for folder, ex, res in examples:
        snap = snapshot(folder, ex, res) if res else None
        if ex["origin"] == "constructed":
            verdict = (res.get("verdictLabel") or VERDICT_LABEL.get(res["verdict"], "no verdict")) if res else "not run"
            if snap and (snap["state"] == "stale" or snap["evidence"]):
                verdict += " (⚠ stale)" if snap["state"] == "stale" else " (⚠ evidence not the run's)"
        else:
            verdict = ex["verdictLabel"]
        approaches = [ex["approach"]["id"], *ex["approach"].get("also", [])]
        rows.append(f"| {ex['id']} | [{ex['title']}]({folder.name}/README.md) | {ex['origin']} | {ex['subject']['system']} "
                    f"| {', '.join(approaches)} | {verdict} | {tests_cell(res) if res else ''} | {', '.join(ex['tags'])} |")
        index.append({
            "id": ex["id"], "path": f"examples/{folder.name}", "title": ex["title"], "summary": ex["summary"],
            "origin": ex["origin"], "system": ex["subject"]["system"], "symbol": ex["subject"]["symbol"],
            "approach": ex["approach"]["id"], "approaches": approaches,
            "tags": {facet: [t for t in ex["tags"] if vocabulary[t][0] == facet] for facet in ("domain", "defect", "technique")},
            "categories": ex["categories"], "severity": ex["severity"], "changeKind": ex["change"]["kind"],
            "verdict": (res["verdict"] if res else None) if ex["origin"] == "constructed" else None,
            "verdictLabel": verdict,
            "vacuous": bool((res or {}).get("coverage") and res["coverage"].get("vacuous")),
            "snapshot": snap["state"] if snap else None,
            "existingTestsPassed": res["existingTests"]["passed"] if res else None,
            "notes": ex.get("notes", []),
            "source": ex.get("source", {}).get("url"),
        })
    by_tag = {}
    for folder, ex, _ in examples:
        for t in ex["tags"]:
            by_tag.setdefault(t, []).append((ex["id"], folder.name))
    tag_lines = ["#### Approach: which verifier", ""]
    names = {"B8": "Behavioural contracts", "B9": "Regression verification", "B10": "Capability contracts",
             "B11": "Property proofs", "B12": "Boundary contracts", "D1": "Protocol model checking"}
    for approach, name in names.items():
        members = [(ex["id"], folder.name) for folder, ex, _ in examples
                   if approach in [ex["approach"]["id"], *ex["approach"].get("also", [])]]
        tag_lines.append(f"- <a id=\"approach-{approach.lower()}\"></a>**{approach} {name}** ({len(members)}): "
                         + ", ".join(f"[{i}]({n}/README.md)" for i, n in members))
    tag_lines.append("")
    for facet, heading in [("domain", "Domain: what the code does"), ("defect", "Defect: what goes, or could go, wrong"),
                           ("technique", "Technique: how it is verified, beyond the approach")]:
        tag_lines += [f"#### {heading}", ""]
        for tag, (f, description) in vocabulary.items():
            if f != facet:
                continue
            members = by_tag.get(tag, [])
            links = ", ".join(f"[{i}]({name}/README.md)" for i, name in members) or "none yet"
            tag_lines.append(f"- <a id=\"tag-{tag}\"></a>**{tag}** ({len(members)}): {description}. {links}")
        tag_lines.append("")
    readme = (EXAMPLES / "README.md").read_text()
    table = "\n".join([
        "<!-- examples:begin (generated by examples/tools/build.py from each example.json) -->",
        "| # | Example | Origin | System | Approach | Verdict | Existing tests | Tags |",
        "|---|---|---|---|---|---|---|---|", *rows, "<!-- examples:end -->"])
    tags = "\n".join(["<!-- tags:begin (generated by examples/tools/build.py from examples/tags.json) -->", "",
                      *tag_lines, "<!-- tags:end -->"])
    for begin, end, text in [("<!-- examples:begin", "<!-- examples:end -->", table), ("<!-- tags:begin", "<!-- tags:end -->", tags)]:
        if begin not in readme:
            sys.exit(f"examples/README.md has no {begin} ... {end} block")
        readme = re.sub(re.escape(begin) + ".*?" + re.escape(end), lambda _: text, readme, flags=re.S)
    (EXAMPLES / "README.md").write_text(readme)
    (EXAMPLES / "index.json").write_text(json.dumps(
        {"schema": "examples-index/v2", "description": "Every example, for finding the ones relevant to a task: "
         "examples/tools/find.py searches it, and examples/tags.json defines the tags.", "examples": index},
        indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

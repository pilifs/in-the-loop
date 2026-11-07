#!/usr/bin/env python3
"""The benchmark corpus of steps 5a and 5b of llm-dlc/loops/sound-verdicts.md: runs every case on each engine under
each gap mode and reports correctness, supported coverage, time and memory apart, and where each engine's time goes,
phase by phase (README.md says what each means).

    python3 lib/benchmark/run.py                       # every case, native and JBMC, strict, assume and advised
    python3 lib/benchmark/run.py --engines native --groups 2,3 --out /tmp/b.json --table /tmp/b.md
    python3 lib/benchmark/run.py --engines native,jbmc,auto --jbmc-staging staged,full-range,tight   # step 2b

JBMC runs are proofs: the full run is a pipeline job, not something to run inline.
"""

import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIB = HERE.parent
REPO = LIB.parent
CONFORMANCE_SOURCE = LIB / "tests/conformance/conformance/Conformance.java"
RUNNER_SOURCE = LIB / "tests/conformance/Runner.java"
ENGINES = ("native", "jbmc")
# JBMC's staging policies (lib/src/deadline.rs's Staging, `--jbmc-staging`): which of its interval stages a check runs.
# A run of an engine that may call JBMC (jbmc, auto) is made once per policy asked for; the first is the one the
# tables of the corpus are over, and the others are compared with it (step 2b of llm-dlc/loops/engine-priorities.md).
STAGING = ("staged", "full-range", "tight")
JBMC_ENGINES = ("jbmc", "auto")
MODES = ("strict", "assume", "advised")
GROUPS = {1: "semantic conformance", 2: "real regressions", 3: "held-out performance cases", 4: "recorded examples"}
# Group 4: recorded examples step 5b names, by number, with their workload: the reviews' case studies, run under the
# same configuration as the corpus. Their expected answer is the recorded one, not the JVM's.
RECORDED = {"141": "binary-search", "142": "utf8"}
# The phases of a run (lib/src/phases.rs), the checker's own and the driver's around it: the record's `phases`.
RUN_PHASES = ("loading", "lowering", "symbolic", "encoding", "solving", "trace")
PHASES = RUN_PHASES + ("checker-other", "gaps", "contracts", "replay", "jvm", "harness", "setup", "driver")
# How far a run's phases may add up past its seconds before it is flagged: a share of them, and seconds besides
# (lib/src/phases.rs's TOLERANCE_SHARE and TOLERANCE_SECONDS). A flagged run is left out of the phase tables, never
# scaled to fit.
PHASE_TOLERANCE = (0.01, 0.005)
# The configuration both engines are given: the same harness, bounds, models and deadline.
UNWIND = 16
MAX_ARRAY_LENGTH = 8


def load_cases(groups, pattern=None):
    cases = []
    if 1 in groups:
        cases += json.loads((HERE / "conformance.json").read_text())["cases"]
    corpus = json.loads((HERE / "corpus.json").read_text())
    cases += [c for c in corpus["cases"] if c["group"] in groups]
    if 4 in groups:
        cases += recorded_cases()
    if pattern:
        cases = [c for c in cases if pattern in c["id"]]
    return cases


def recorded_cases():
    """Group 4: each recorded example of RECORDED as a regression case, its claim read from its example.json (the
    target, the intended inputs as the scope) and its patch applied to its app. Run under strict alone: they reach
    no gap, so the other modes would repeat the same proof."""
    out = []
    for number, workload in RECORDED.items():
        folder = next((REPO / "examples").glob(f"{number}-*"))
        example = json.loads((folder / "example.json").read_text())
        source = example["subject"]["file"]
        out.append({"id": f"example/{number}", "group": 4, "workload": workload, "kind": "regression",
                    "before": f"example-{number}-before", "after": f"example-{number}-after",
                    "target": example["subject"]["symbol"], "unchangedUnless": example["change"].get("intendedInputs"),
                    "expected": example["expected"]["verdict"], "modes": ["strict"],
                    "app": source.split("/src/main/java/")[0], "patch": str(folder / example["change"]["patch"]),
                    "source": f"examples/{folder.name}", "why": "the recorded example's verdict"})
    return out


def compile_examples(build, cases):
    """Each recorded example's app as it is (before) and with the example's patch applied (after)."""
    out = {}
    for case in (c for c in cases if c["group"] == 4):
        root = build / "examples" / case["id"].split("/")[1]
        if root.exists():
            shutil.rmtree(root)
        app = root / "repo" / case["app"]
        shutil.copytree(REPO / case["app"] / "src", app / "src")
        with open(case["patch"]) as patch:
            subprocess.run(["patch", "-s", "-p1", "-d", str(root / "repo")], stdin=patch, check=True)
        for side, tree in (("before", REPO / case["app"]), ("after", app)):
            sources = sorted(str(p) for p in (tree / "src/main/java").rglob("*.java"))
            out[case[side]] = javac(sources, root / side)
    return out


def versions():
    return json.loads((HERE / "corpus.json").read_text())["versions"]


def compile_sources(build):
    """Each version's tree into build/classes/VERSION, and the conformance corpus into build/classes/conformance."""
    out = {}
    trees = dict(versions())
    for name, tree in trees.items():
        sources = sorted(str(p) for p in (HERE / tree).rglob("*.java"))
        out[name] = javac(sources, build / "classes" / name)
    out["conformance"] = javac([str(CONFORMANCE_SOURCE)], build / "classes" / "conformance")
    return out


def javac(sources, target):
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    subprocess.run(["javac", "-parameters", "-g", "-proc:none", "-d", str(target), *sources], check=True)
    return target


def command(case, engine, mode, classes, work, options, staging=None):
    """The jvmcontract command line for one case: the same for both engines but for --engine, and for JBMC's staging
    policy when one is given."""
    common = ["--engine", engine, "--gaps", mode, "--work", str(work), "--timeout", str(options.timeout),
              "--unwind", str(UNWIND), "--max-array-length", str(MAX_ARRAY_LENGTH), "--jbmc", options.jbmc, "--json"]
    if staging:
        common += ["--jbmc-staging", staging]
    if mode == "advised":
        # The protocol with no agent: the contract library's contracts only, none of them trusted.
        common += ["--max-trust", "0"]
    if case["kind"] == "property":
        cmd = [options.jvmcontract, "prove", "--classes", str(classes[case.get("classes", "conformance")]), case["target"]]
        if case.get("assume"):
            cmd += ["--assume", case["assume"]]
        cmd += ["--assert", case["assert"]]
        for clause in case.get("throws") or []:
            cmd += ["--throws", clause]
        return cmd + common
    cmd = [options.jvmcontract, "equivalence", "--before", str(classes[case["before"]]), "--after", str(classes[case["after"]]),
           "--target", case["target"]]
    if case.get("unchangedUnless"):
        cmd += ["--unchanged-unless", case["unchangedUnless"]]
    return cmd + common


def measure(cmd, limit):
    """Runs a command, returning its exit code, output, wall and CPU seconds, and the peak resident memory of it and
    every process it waited for (JBMC, the JVM it tests contracts on) in MB."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        start = time.monotonic()
        process = subprocess.Popen(cmd, stdout=out, stderr=err)
        killed = False
        while True:
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                break
            if time.monotonic() - start > limit and not killed:
                process.kill()
                killed = True
            time.sleep(0.01)
        wall = time.monotonic() - start
        process.returncode = os.waitstatus_to_exitcode(status)
        out.seek(0)
        err.seek(0)
        return {
            "exit": process.returncode,
            "killed": killed,
            "stdout": out.read().decode(errors="replace"),
            "stderr": err.read().decode(errors="replace"),
            "seconds": round(wall, 3),
            "cpuSeconds": round(usage.ru_utime + usage.ru_stime, 3),
            "peakMB": round(usage.ru_maxrss / 1024, 1),
        }


def outcome_of(case, raw):
    """The tool's JSON for the case: a property proof prints a list of one."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        data = data[0] if data else None
    return data


def classify(case, data, measured):
    """What a run's verdict is worth against the case's expected answer."""
    search = (data or {}).get("search") or {}
    gaps = search.get("gaps") or []
    assumed = [g["id"] for g in gaps if g.get("treatment") == "assumed"]
    contracts = [g["id"] for g in gaps if g.get("treatment") == "contract"]
    verdict = (data or {}).get("verdict", "none")
    record = {"verdict": verdict, "assumed": assumed, "contracts": contracts}
    if verdict not in ("verified", "violation"):
        record["class"] = "unsupported"
        record["reason"] = unsupported_reason(data, measured)
        record["problem"] = ((data or {}).get("problem") or measured["stderr"][-300:]).strip()
        return record
    expected = case["expected"]
    if verdict == expected:
        record["class"] = "correct-assuming" if assumed else "correct"
    elif verdict == "verified":
        record["class"] = "false-success-assuming" if assumed else "false-success"
    else:
        record["class"] = "false-alarm"
    return record


def unsupported_reason(data, measured):
    if measured["killed"]:
        return "out of time"
    if data is None:
        return "no output"
    if data.get("advice"):
        return "needs contracts"
    endings = [r.get("ending") or r.get("ended") for r in (data.get("search") or {}).get("runs") or []]
    if any(e in ("timeout", "out-of-time", "killed") for e in endings) or "did not finish within the time limit" in (data.get("problem") or ""):
        return "out of time"
    if "memory-exhausted" in endings:
        return "out of memory"
    if any(g.get("treatment") == "refused" for g in (data.get("search") or {}).get("gaps") or []):
        return "gap"
    problem = data.get("problem") or ""
    if "disagree" in problem:
        return "engines disagree"
    if "does not reproduce" in problem or "not reproduced" in problem or "unconfirmed" in problem:
        return "witness not reproduced"
    return "refused"


def stats_of(data):
    """The solver's side of a run, as far as it says: the own checker's paths and formula, JBMC's runs."""
    search = (data or {}).get("search") or {}
    native = search.get("native") or {}
    keep = {k: native[k] for k in ("paths", "merges", "solver_calls", "solving_seconds", "variables", "clauses") if k in native}
    runs = search.get("runs") or []
    if runs:
        keep["runs"] = [{k: r.get(k) for k in ("checker", "purpose", "stage", "seconds", "ended", "ending", "phases", "formula")} for r in runs]
        for kept, r in zip(keep["runs"], runs):
            if r.get("budget_seconds") is not None:
                kept["budget"] = r["budget_seconds"]
        for kept, r in zip(keep["runs"], runs):
            if r.get("phases_excess"):
                kept["phasesExcess"] = r["phases_excess"]
    return keep


def sat_of(data):
    """The SAT solver the verdict was solved on, as the result's evidence names it (`stated.checker.sat`, the shape of
    `Sat` in lib/src/statement.rs): solver, version, source and configuration. None when no checker ran."""
    return (((data or {}).get("stated") or {}).get("checker") or {}).get("sat")


def sat_solvers(runs):
    """Per engine, each SAT solver its runs were solved on, once: the environment's record of them."""
    out = {}
    for r in runs:
        sat = r.get("sat")
        if sat and sat not in out.setdefault(r["engine"], []):
            out[r["engine"]].append(sat)
    return {engine: sats for engine, sats in out.items() if sats}


def phases_of(data, seconds):
    """A run's wall-clock seconds by phase: its checker runs' phases summed (lib/src/phases.rs), `checker-other`
    what those leave of them (JBMC starting and printing), the driver's steps (gaps, contracts, replay, the JVM,
    the harness, the setup of the work directory), and `driver` the rest of the process. A checker run with no phases, and a process that printed
    nothing, count under `driver`."""
    search = (data or {}).get("search") or {}
    out = dict.fromkeys(PHASES, 0.0)
    for r in search.get("runs") or []:
        p = r.get("phases")
        if not p:
            continue
        for k in RUN_PHASES:
            out[k] += p.get(k, 0.0)
        out["checker-other"] += p.get("other", 0.0)
    check = search.get("phases") or {}
    for k in ("gaps", "contracts", "replay", "jvm", "harness", "setup"):
        out[k] += check.get(k, 0.0)
    out["driver"] = max(seconds - sum(out.values()), 0.0)
    return {k: round(v, 3) for k, v in out.items()}


def phases_excess(data, phases, seconds):
    """The seconds by which a run's phases add up past its time, beyond PHASE_TOLERANCE: its checker runs' own
    excess (`phases_excess`, flagged by lib/src/phases.rs), or its phases short of `driver` past the process's
    seconds. None when they fit."""
    runs = sum(r.get("phases_excess") or 0.0 for r in ((data or {}).get("search") or {}).get("runs") or [])
    over = sum(v for k, v in phases.items() if k != "driver") - seconds
    if over <= PHASE_TOLERANCE[0] * seconds + PHASE_TOLERANCE[1]:
        over = 0.0
    worst = max(runs, over)
    return round(worst, 3) if worst > 0 else None


def formula_of(data):
    """The largest formula of a run's checker runs: JBMC's SSA steps, and the variables and clauses."""
    out = {}
    for r in ((data or {}).get("search") or {}).get("runs") or []:
        for k, v in (r.get("formula") or {}).items():
            if v is not None:
                out[k] = max(out.get(k, 0), v)
    return out


def token(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, list):
        return "[" + ",".join(token(v) for v in value) + "]"
    if isinstance(value, str) and len(value) == 1:
        return str(ord(value))
    return str(value)


def witness_size(inputs):
    """How big a witness is: the elements of its arrays, and the largest magnitude among its values (a `true`
    counts as 1, a `long` or a floating-point value written as a string is read back, a non-finite one is left out).
    None when there is no witness. The record of each run's witness as reported (`witnessSize`, shrunk by
    lib/src/shrink.rs when JBMC found it) and as JBMC found it (`foundSize`)."""
    if inputs is None:
        return None
    size = {"elements": 0, "largest": 0}

    def walk(value):
        if isinstance(value, list):
            size["elements"] += len(value)
            for v in value:
                walk(v)
            return
        if isinstance(value, bool):
            number = int(value)
        elif isinstance(value, (int, float)):
            number = value
        elif isinstance(value, str):
            try:
                number = int(value)
            except ValueError:
                try:
                    number = float(value)
                except ValueError:
                    return
        else:
            return
        if number == number and abs(number) != float("inf"):
            magnitude = abs(number)
            size["largest"] = max(size["largest"], int(magnitude) if magnitude == int(magnitude) else magnitude)

    def visit(typed):
        walk(typed.get("value"))
        for component in typed.get("components") or []:
            visit(component)

    for typed in inputs:
        visit(typed)
    return size


def witness_arguments(data):
    witness = (data or {}).get("counterexample") or {}
    inputs = witness.get("inputs")
    if inputs is None:
        return None
    return ";".join(token(i.get("value")) for i in inputs)


def on_the_jvm(source, classpath_arguments, lines, build, name):
    requests = build / f"{name}.requests"
    requests.write_text("".join(line + "\n" for line in lines))
    result = subprocess.run(["java", str(source), *classpath_arguments, str(requests)], capture_output=True, text=True, check=True)
    return result.stdout.splitlines()


def reference(cases, build, classes, searches):
    """Groups 2 and 3 on the JVM, through Reference.java: each expected violation refuted on its witness, each
    expected proof searched for a refutation. A case whose answer the JVM does not bear out is reported, and not
    counted."""
    own = [c for c in cases if c["group"] in (2, 3)]
    if not own:
        return {}
    lines = ["list"]
    for c in own:
        if c["expected"] == "violation":
            lines.append(f"{c['id']}\tcheck\t{';'.join(token(v) for v in c['witness'])}")
        else:
            lines.append(f"{c['id']}\tsearch\t{searches}")
    said = on_the_jvm(HERE / "Reference.java", [str(classes["v1"].parent)], lines, build, "reference")
    listed = {line.split("\t")[0] for line in said[: len(said) - len(own)]}
    answers = {}
    for c, line in zip(own, said[len(said) - len(own):]):
        field = line.split("\t")
        if c["id"] not in listed or field[0] != c["id"]:
            answers[c["id"]] = {"agrees": False, "said": "Reference.java has no such case"}
        elif c["expected"] == "violation":
            answers[c["id"]] = {"agrees": field[1] == "refuted", "said": " ".join(field[1:])}
        else:
            answers[c["id"]] = {"agrees": field[1] == "held", "said": " ".join(field[1:]), "inputs": int(field[2]) if field[1] == "held" else None}
    for c in own:
        answers.setdefault(c["id"], {"agrees": False, "said": "not asked"})
    return answers


def check_witnesses(runs, cases_by_id, build, classes):
    """Every violation an engine reports, run on the JVM: group 1's through the tool's own harness and the
    conformance runner, as lib/tests/conformance.rs does, groups 2 and 3's through Reference.java. A witness the
    JVM does not reproduce makes the run a false alarm."""
    conformance, own = [], []
    for run in runs:
        if run["verdict"] != "violation" or run.get("witness") is None:
            continue
        case = cases_by_id[run["case"]]
        if case["group"] == 4:
            # A recorded example's answer is its recorded one; its witness is the example's to replay.
            continue
        if case["group"] == 1:
            conformance.append((run, f"check\t{Path(run['work']) / 'harness'}\t{run['witness']}"))
        else:
            own.append((run, f"{case['id']}\tcheck\t{run['witness']}"))
    if conformance:
        said = on_the_jvm(RUNNER_SOURCE, [str(classes["conformance"])], [line for _, line in conformance], build, "witnesses-conformance")
        for (run, _), answer in zip(conformance, said):
            settle_witness(run, answer == "refuted", answer)
    if own:
        said = on_the_jvm(HERE / "Reference.java", [str(classes["v1"].parent)], [line for _, line in own], build, "witnesses")
        for (run, _), answer in zip(own, said):
            settle_witness(run, answer.split("\t")[1:2] == ["refuted"], " ".join(answer.split("\t")[1:]))


def settle_witness(run, reproduced, answer):
    run["witnessOnTheJvm"] = answer
    if not reproduced and run["class"] in ("correct", "correct-assuming", "false-alarm"):
        run["class"] = "false-alarm"


def environment(options):
    def version(cmd):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return (r.stdout or r.stderr).strip().splitlines()[0]
        except (OSError, subprocess.SubprocessError, IndexError):
            return None
    cpu = None
    try:
        lscpu = subprocess.run(["lscpu"], capture_output=True, text=True, timeout=30).stdout
        cpu = next((line.split(":", 1)[1].strip() for line in lscpu.splitlines() if line.startswith("Model name")), None)
    except (OSError, subprocess.SubprocessError):
        pass
    return {
        "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "jvmcontract": version([options.jvmcontract, "--version"]),
        "jbmc": version([options.jbmc, "--version"]),
        "java": version(["java", "-version"]),
        "machine": platform.machine(),
        "cpu": cpu,
        "cpus": os.cpu_count(),
        # The pipeline job the run is, and the commit it ran at, when it is one (verification/pipeline.py sets them).
        "job": os.environ.get("VERIFY_JOB_ID"),
        "commit": os.environ.get("VERIFY_SOURCE_COMMIT"),
    }


def run(options):
    groups = {int(g) for g in options.groups.split(",")}
    engines = options.engines.split(",")
    modes = options.modes.split(",")
    stagings = options.jbmc_staging.split(",")
    unknown = [p for p in stagings if p not in STAGING]
    if unknown:
        raise SystemExit(f"unknown JBMC staging policy {', '.join(unknown)}: {', '.join(STAGING)}")
    cases = load_cases(groups, options.cases)
    cases_by_id = {c["id"]: c for c in cases}
    build = Path(options.build).resolve()
    build.mkdir(parents=True, exist_ok=True)
    classes = {**compile_sources(build), **compile_examples(build, cases)}
    answers = reference(cases, build, classes, options.search)
    runs = []
    for case in cases:
        for engine in engines:
            for mode in modes:
                if mode not in case.get("modes", modes):
                    continue
                first = None
                for staging in stagings if engine in JBMC_ENGINES else [None]:
                    if engine == "auto" and first is not None and not first.get("fallback"):
                        # The own checker decided under the first policy, so JBMC never ran: the policy changes nothing.
                        continue
                    record = run_one(case, engine, mode, staging, classes, build, options)
                    first = first or record
                    runs.append(record)
                    if not options.quiet:
                        print(f"{case['id']:<44} {engine:<6} {mode:<7} {staging or '':<10} {record['verdict']:<12} {record['class']:<22} "
                              f"{record['seconds']:>7.2f} s {record['peakMB']:>7.1f} MB", flush=True)
    check_witnesses(runs, cases_by_id, build, classes)
    for r in runs:
        r.pop("work", None)
    return {
        "about": "Results of lib/benchmark/run.py: see lib/benchmark/README.md.",
        "environment": {**environment(options), "sat": sat_solvers(runs)},
        "settings": {"timeout": options.timeout, "unwind": UNWIND, "maxArrayLength": MAX_ARRAY_LENGTH, "referenceSearch": options.search,
                     "engines": engines, "modes": modes, "groups": sorted(groups), "jbmcStaging": stagings},
        "cases": [{k: c[k] for k in ("id", "group", "workload", "kind", "expected")} for c in cases],
        "reference": answers,
        "runs": runs,
    }


def run_one(case, engine, mode, staging, classes, build, options):
    """One case on one engine under one gap mode (and one JBMC staging policy, for an engine that may call JBMC):
    its command run and measured, and its record."""
    work = build / "work" / case["id"].replace("/", "_") / "-".join(filter(None, (engine, mode, staging)))
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    cmd = command(case, engine, mode, classes, work, options, staging)
    measured = measure(cmd, options.timeout * 1.5 + 60)
    data = outcome_of(case, measured["stdout"])
    return record_of(case, engine, mode, staging, data, measured, work)


def record_of(case, engine, mode, staging, data, measured, work):
    record = {"case": case["id"], "engine": engine, "mode": mode, "work": str(work),
              **{k: measured[k] for k in ("exit", "seconds", "cpuSeconds", "peakMB")}}
    if staging:
        record["staging"] = staging
    record.update(classify(case, data, measured))
    if engine == "auto":
        # Whether the own checker gave no verdict and JBMC's fallback ran: only then does the staging policy count.
        record["fallback"] = bool(((data or {}).get("search") or {}).get("fallback"))
    record["witness"] = witness_arguments(data) if record["verdict"] == "violation" else None
    if record["verdict"] == "violation":
        counterexample = (data or {}).get("counterexample") or {}
        record["witnessSize"] = witness_size(counterexample.get("inputs"))
        if counterexample.get("found_inputs") is not None:
            record["foundSize"] = witness_size(counterexample["found_inputs"])
            record["shrinkRuns"] = counterexample.get("shrink_runs")
    record["solver"] = stats_of(data)
    record["sat"] = sat_of(data)
    record["phases"] = phases_of(data, measured["seconds"])
    excess = phases_excess(data, record["phases"], measured["seconds"])
    if excess:
        record["phasesExcess"] = excess
    record["formula"] = formula_of(data)
    return record


# The tables.

CORRECT = ("correct", "correct-assuming")


def summarize(results):
    """Per group, engine and mode: how many cases are right, unsupported, wrong, and the time and memory taken."""
    cases = {c["id"]: c for c in results["cases"]}
    rows = []
    for group in results["settings"]["groups"]:
        for engine in results["settings"]["engines"]:
            for mode in results["settings"]["modes"]:
                rs = [r for r in results["runs"] if cases[r["case"]]["group"] == group and r["engine"] == engine and r["mode"] == mode]
                if not rs:
                    continue
                count = lambda *classes: sum(r["class"] in classes for r in rs)
                seconds = [r["seconds"] for r in rs]
                rows.append({
                    "group": group, "engine": engine, "mode": mode, "cases": len(rs),
                    "correct": count(*CORRECT), "assuming": count("correct-assuming"),
                    "unsupported": count("unsupported"),
                    "falseSuccess": count("false-success", "false-success-assuming"),
                    "falseSuccessAssuming": count("false-success-assuming"),
                    "falseAlarm": count("false-alarm"),
                    "seconds": round(sum(seconds), 1), "medianSeconds": round(statistics.median(seconds), 2),
                    "maxSeconds": round(max(seconds), 2), "peakMB": max(r["peakMB"] for r in rs),
                    "reasons": reasons(rs),
                })
    return rows


def reasons(runs):
    out = {}
    for r in runs:
        if r["class"] == "unsupported":
            out[r["reason"]] = out.get(r["reason"], 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def by_workload(results, mode="strict"):
    cases = {c["id"]: c for c in results["cases"]}
    rows = []
    workloads = sorted({c["workload"] for c in results["cases"]})
    for workload in workloads:
        for engine in results["settings"]["engines"]:
            rs = [r for r in results["runs"] if cases[r["case"]]["workload"] == workload and r["engine"] == engine and r["mode"] == mode]
            if not rs:
                continue
            decided = [r["seconds"] for r in rs if r["class"] != "unsupported"]
            rows.append({"workload": workload, "engine": engine, "cases": len(rs), "correct": sum(r["class"] in CORRECT for r in rs),
                         "unsupported": sum(r["class"] == "unsupported" for r in rs),
                         "wrong": sum(r["class"] not in CORRECT + ("unsupported",) for r in rs),
                         "medianSeconds": round(statistics.median(decided), 2) if decided else None,
                         "maxSeconds": round(max(r["seconds"] for r in rs), 2), "peakMB": max(r["peakMB"] for r in rs)})
    return rows


def by_phase(results, mode="strict", groups=(1, 2, 3), key="workload"):
    """Per workload (or case) and engine, under one gap mode: the seconds of every run, decided or not (a timeout's
    time is spent too), split by phase, with the phase that dominates and the largest formula."""
    cases = {c["id"]: c for c in results["cases"]}
    rows = []
    for name in sorted({c[key] if key in c else c["id"] for c in results["cases"] if c["group"] in groups}):
        for engine in results["settings"]["engines"]:
            rs = [r for r in results["runs"] if cases[r["case"]]["group"] in groups and (cases[r["case"]].get(key) or cases[r["case"]]["id"]) == name
                  and r["engine"] == engine and r["mode"] == mode and r.get("phases") and not r.get("phasesExcess")]
            if not rs:
                continue
            total = sum(r["seconds"] for r in rs)
            phases = {k: sum(r["phases"].get(k, 0.0) for r in rs) for k in PHASES}
            dominant = max(phases, key=phases.get)
            clauses = [r.get("formula", {}).get("clauses") for r in rs if r.get("formula", {}).get("clauses")]
            rows.append({key: name, "engine": engine, "runs": len(rs), "seconds": round(total, 2),
                         "phases": {k: round(v, 3) for k, v in phases.items()}, "dominant": dominant,
                         "share": {k: (v / total if total else 0.0) for k, v in phases.items()},
                         "maxClauses": max(clauses) if clauses else None,
                         "undecided": sum(r["class"] == "unsupported" for r in rs)})
    return rows


def phase_table(rows, key):
    head = "| " + key + " | engine | runs | s | " + " | ".join(PHASES) + " | dominant | largest formula (clauses) |"
    out = [head, "|---|---|---:|---:|" + "---:|" * len(PHASES) + "---|---:|"]
    for row in rows:
        share = " | ".join(f"{round(100 * row['share'][k])}%" if row["phases"][k] else "·" for k in PHASES)
        undecided = f" ({row['undecided']} undecided)" if row["undecided"] else ""
        out.append(f"| {row[key]} | {row['engine']} | {row['runs']}{undecided} | {row['seconds']} | {share} | **{row['dominant']}** "
                   f"{round(100 * row['share'][row['dominant']])}% | {row['maxClauses'] if row['maxClauses'] is not None else '–'} |")
    return out


# JBMC's staging policies (step 2b of llm-dlc/loops/engine-priorities.md).

def staging_policies(results):
    """The staging policies the runs of jbmc and auto were made under, the first the tables of the corpus are over;
    none for a results file from before the option."""
    return results["settings"].get("jbmcStaging") or []


def primary(results):
    """The results as the corpus's tables read them: every engine's runs under the first staging policy alone, the
    own checker's (which has none) included."""
    policies = staging_policies(results)
    if len(policies) < 2:
        return results
    return {**results, "runs": [r for r in results["runs"] if r.get("staging") in (None, policies[0])]}


def staged_cases(results, engine, mode):
    """Per case, its runs of `engine` under `mode` by staging policy. For auto, only the cases whose first run fell
    back to JBMC: on the others the own checker decided, and the policy changed nothing."""
    out = {}
    for r in results["runs"]:
        if r["engine"] == engine and r["mode"] == mode and r.get("staging"):
            out.setdefault(r["case"], {})[r["staging"]] = r
    first = staging_policies(results)[0]
    if engine == "auto":
        out = {case: by for case, by in out.items() if by.get(first, {}).get("fallback")}
    return out


def larger(size, than):
    """Whether a witness is larger than another: more elements, or a larger value."""
    return bool(size and than) and (size["elements"] > than["elements"] or size["largest"] > than["largest"])


def starved(run):
    """Whether a run without a verdict never gave JBMC's full range a second: it did not run, or its budget was
    under 1 s (step 2a's note: under auto, staged stages out of time can leave the fallback's full range nothing)."""
    if run["class"] != "unsupported":
        return False
    jbmc = [r for r in (run.get("solver") or {}).get("runs") or [] if r.get("checker") == "jbmc"]
    if not jbmc:
        return False
    full = [r for r in jbmc if r.get("stage") is None]
    return not full or (full[-1].get("budget") is not None and full[-1]["budget"] < 1.0)


def by_staging(results):
    """Per engine that may call JBMC, mode and staging policy, the proofs and the counterexamples apart (by the
    case's expected answer): how many are decided correctly, without a verdict, or wrong, the seconds they took,
    how many verdicts differ from the first policy's, and, for the counterexamples, how many witnesses are larger
    than the first policy's after shrinking."""
    policies = staging_policies(results)
    expected = {c["id"]: c["expected"] for c in results["cases"]}
    rows = []
    for engine in (e for e in results["settings"]["engines"] if e in JBMC_ENGINES):
        for mode in results["settings"]["modes"]:
            cases = staged_cases(results, engine, mode)
            if not cases:
                continue
            for side, answer in (("proofs", "verified"), ("counterexamples", "violation")):
                ids = [c for c in cases if expected[c] == answer]
                for policy in policies:
                    rs = [cases[c][policy] for c in ids if policy in cases[c]]
                    if not rs:
                        continue
                    base = [cases[c].get(policies[0]) for c in ids if policy in cases[c]]
                    seconds = [r["seconds"] for r in rs]
                    rows.append({
                        "engine": engine, "mode": mode, "side": side, "staging": policy, "cases": len(rs),
                        "correct": sum(r["class"] in CORRECT for r in rs),
                        "unsupported": sum(r["class"] == "unsupported" for r in rs),
                        "wrong": sum(r["class"] not in CORRECT + ("unsupported",) for r in rs),
                        "seconds": round(sum(seconds), 1), "medianSeconds": round(statistics.median(seconds), 2),
                        "changed": sum(b is not None and r["class"] != b["class"] for r, b in zip(rs, base)),
                        "largerWitnesses": sum(larger(r.get("witnessSize"), (b or {}).get("witnessSize")) for r, b in zip(rs, base)),
                        "shrunk": sum("foundSize" in r for r in rs),
                        "starved": sum(starved(r) for r in rs),
                        "reasons": reasons(rs),
                    })
    return rows


def size_text(size):
    if not size:
        return ""
    return f"{size['elements']} el., max {size['largest']}" if size["elements"] else f"max {size['largest']}"


def staged_cell(run):
    if run is None:
        return ""
    text = cell(run)
    if run.get("witness") is not None:
        text += f", `{run['witness']}` ({size_text(run.get('witnessSize'))}"
        if run.get("foundSize"):
            text += f"; found {size_text(run['foundSize'])}"
        text += ")"
    if starved(run):
        text += ", full range starved"
    return text


def staging_section(results):
    policies = staging_policies(results)
    out = ["", "## JBMC's staging policies", "",
           "Step 2b of [`engine-priorities.md`](../../llm-dlc/loops/engine-priorities.md): every run of `jbmc`, and of `auto` "
           "where the own checker gave no verdict and JBMC's fallback ran, under each of the policies of `--jbmc-staging` "
           "(`lib/src/deadline.rs`): `staged` runs every interval stage that restricts the inputs before the full range, "
           "`full-range` the full range alone, `tight` the first restricting stage on a fortieth of the check, then the full "
           "range. Everything else is the same: the deadline, the bounds, the models and the evidence rules. Proofs (cases "
           "expected `verified`) and counterexamples (expected `violation`) are counted apart. A witness is measured as "
           "reported, after `lib/src/shrink.rs` shrank it in the interpreter: the elements of its arrays and its largest "
           "magnitude. *Changed* counts the runs whose class differs from the same case's under "
           f"`{policies[0]}`, *larger* the witnesses bigger than its, and *starved* the runs left without a verdict that "
           "gave the full range less than a second, or none.", "",
           "| engine | mode | kind | policy | correct | no verdict | wrong | total s | median s | changed | larger witnesses | shrunk | starved | no verdict, why |",
           "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    rows = by_staging(results)
    if not rows:
        out[-2:] = ["No run of `jbmc` was made, and no run of `auto` fell back to JBMC."]
    for row in rows:
        why = ", ".join(f"{n} {w}" for w, n in row["reasons"].items())
        larger_cell = row["largerWitnesses"] if row["side"] == "counterexamples" else "·"
        shrunk_cell = row["shrunk"] if row["side"] == "counterexamples" else "·"
        out.append(f"| {row['engine']} | {row['mode']} | {row['side']} | `{row['staging']}` | {row['correct']} of {row['cases']} | {row['unsupported']} | "
                   f"{row['wrong']} | {row['seconds']} | {row['medianSeconds']} | {row['changed']} | {larger_cell} | {shrunk_cell} | {row['starved']} | {why} |")
    expected = {c["id"]: c["expected"] for c in results["cases"]}
    for engine in (e for e in results["settings"]["engines"] if e in JBMC_ENGINES):
        for mode in results["settings"]["modes"]:
            cases = staged_cases(results, engine, mode)
            if not cases:
                continue
            differ = [c for c, by in cases.items() if len({r["class"] for r in by.values()}) > 1]
            if differ:
                out += ["", f"Cases whose class differs between the policies, {engine} under {mode}: " + ", ".join(f"`{c}`" for c in differ) + "."]
    for engine in (e for e in results["settings"]["engines"] if e in JBMC_ENGINES):
        cases = staged_cases(results, engine, "strict")
        if not cases:
            continue
        what = "case" if engine == "jbmc" else "case where JBMC's fallback ran"
        for side, answer in (("Proofs", "verified"), ("Counterexamples", "violation")):
            ids = [c for c in (c["id"] for c in results["cases"]) if c in cases and expected[c] == answer]
            if not ids:
                continue
            count = f"{len(ids)} case" + ("s" if len(ids) != 1 else "")
            out += ["", f"<details><summary>{side}, {engine} under strict, {count}: each {what}, per policy</summary>", "",
                    "| case | " + " | ".join(f"`{p}`" for p in policies) + " |", "|---|" + "---|" * len(policies)]
            for c in ids:
                out.append(f"| `{c}` | " + " | ".join(staged_cell(cases[c].get(p)) for p in policies) + " |")
            out += ["", "</details>"]
    return out


MARK = {"correct": "✓", "correct-assuming": "✓ₐ", "unsupported": "–", "false-success": "✗", "false-success-assuming": "✗ₐ", "false-alarm": "!"}


def cell(run):
    if run is None:
        return ""
    if run["class"] == "unsupported":
        return f"– {run['reason']} {run['seconds']:.1f} s"
    return f"{MARK[run['class']]} {run['verdict']} {run['seconds']:.2f} s"


def render(results):
    every = results
    results = primary(results)
    s = results["settings"]
    env = results["environment"]
    job = f" as pipeline job `{env['job']}`, at commit `{(env.get('commit') or 'unknown')[:12]}`," if env.get("job") else ""
    out = ["# Benchmark results", "",
           f"Written by `lib/benchmark/run.py` on {env['date']},{job} on {env['cpus']} × {env['cpu']} ({env['machine']}), with "
           f"{env['jvmcontract']}, JBMC {env['jbmc']} and {env['java']}. Every run had a deadline of {s['timeout']} s, loops unwound "
           f"{s['unwind']} times and arrays of up to {s['maxArrayLength']} elements, on both engines. What the columns mean is in "
           "[README.md](README.md).", ""]
    policies = staging_policies(every)
    if len(policies) > 1:
        out[-1:-1] = ["", f"Every run of an engine that may call JBMC was made under each of JBMC's staging policies, "
                          f"{', '.join(f'`{p}`' for p in policies)}. The tables of the corpus are over `{policies[0]}`, and "
                          "[JBMC's staging policies](#jbmcs-staging-policies) compares the others with it."]
    if env.get("sat"):
        names = {"native": "the own checker", "jbmc": "JBMC"}
        solved = "; ".join(f"{names.get(engine, engine)} on " + " and ".join(f"{sat['solver']} {sat.get('version') or '(version unknown)'}, {sat['source']}" for sat in sats)
                           for engine, sats in env["sat"].items())
        out[-1:-1] = ["", f"SAT solvers: {solved}. Their configuration is under `environment.sat` in `results.json`."]
    out += ["## Correctness and coverage", "",
            "| group | engine | mode | cases | correct | of them assuming a gap | unsupported | false success | false alarm | total s | median s | max s | peak MB |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in summarize(results):
        false_success = f"{row['falseSuccess']}" + (f" ({row['falseSuccessAssuming']} naming a gap)" if row["falseSuccessAssuming"] else "")
        out.append(f"| {row['group']} {GROUPS[row['group']]} | {row['engine']} | {row['mode']} | {row['cases']} | {row['correct']} | {row['assuming']} | "
                   f"{row['unsupported']} | {false_success} | {row['falseAlarm']} | {row['seconds']} | {row['medianSeconds']} | {row['maxSeconds']} | {row['peakMB']} |")
    out += ["", "Why the unsupported cases had no verdict:", ""]
    for row in summarize(results):
        if row["reasons"]:
            out.append(f"- group {row['group']}, {row['engine']}, {row['mode']}: " + ", ".join(f"{n} {why}" for why, n in row["reasons"].items()))
    out += ["", "## By workload, under strict", "",
            "| workload | engine | cases | correct | unsupported | wrong | median s (decided) | max s | peak MB |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in by_workload(results):
        out.append(f"| {row['workload']} | {row['engine']} | {row['cases']} | {row['correct']} | {row['unsupported']} | {row['wrong']} | "
                   f"{row['medianSeconds'] if row['medianSeconds'] is not None else '–'} | {row['maxSeconds']} | {row['peakMB']} |")
    if any(r.get("phases") for r in results["runs"]):
        out += ["", "## Where the time goes, by workload, under strict", "",
                "Each engine's seconds over every run of the workload, decided or not, as shares of the phases of "
                "`lib/src/phases.rs`: the checker's own (`loading` to `trace`, and `checker-other`, JBMC starting and "
                "printing), then the driver's (`gaps` and JBMC's preflight, `contracts`, `replay` and shrinking, the `jvm` "
                "witness run, the `harness`, the `setup` of the work directory with the JDK's classes and the models, and the rest "
                "of the process as `driver`). Step 5b of the sound-verdicts brief.", ""]
        out += phase_table(by_phase(results), "workload")
        recorded = by_phase(results, groups=(4,), key="id")
        if recorded:
            out += ["", "### The recorded examples", ""]
            out += phase_table(recorded, "id")
        flagged = [r for r in results["runs"] if r["mode"] == "strict" and r.get("phasesExcess")]
        if flagged:
            out += ["", f"Left out of these tables, because their phases add up to more than their time (beyond "
                        f"{round(100 * PHASE_TOLERANCE[0])}% and {round(1000 * PHASE_TOLERANCE[1])} ms): "
                        + ", ".join(f"`{r['case']}` on {r['engine']} (by {r['phasesExcess']} s)" for r in flagged) + "."]
    runs = {(r["case"], r["engine"], r["mode"]): r for r in results["runs"]}
    columns = [(e, m) for e in s["engines"] for m in s["modes"]]
    header = "| case | expected | the JVM | " + " | ".join(f"{e} {m}" for e, m in columns) + " |"
    rule = "|---|---|---|" + "---|" * len(columns)
    for group in s["groups"]:
        ids = [c for c in results["cases"] if c["group"] == group]
        out += ["", f"## Group {group}: {GROUPS[group]}, case by case", ""]
        if group == 1:
            out += ["The JVM's answer is the conformance test's (`lib/tests/conformance.rs`), on the calls the corpus lists.", "",
                    "<details><summary>All 1 claims</summary>".replace("All 1", f"All {len(ids)}"), ""]
        out += [header, rule]
        for c in ids:
            jvm = {1: "conformance test", 4: "recorded example"}.get(group) or results["reference"].get(c["id"], {}).get("said", "not asked")
            out.append(f"| `{c['id']}` | {c['expected']} | {jvm} | " + " | ".join(cell(runs.get((c["id"], e, m))) for e, m in columns) + " |")
        if group == 1:
            out += ["", "</details>"]
    if len(policies) > 1:
        out += staging_section(every)
    disagreements = [cid for cid, a in results["reference"].items() if not a["agrees"]]
    out += ["", "## The JVM against the corpus", ""]
    out.append("Every expected answer of groups 2 and 3 is borne out on the JVM." if not disagreements else
               "The JVM does not bear out the expected answer of: " + ", ".join(f"`{d}`" for d in disagreements) + ".")
    unreproduced = [r for r in every["runs"] if r.get("witnessOnTheJvm") is not None and r["class"] == "false-alarm"]
    out.append("")
    out.append("Every witness an engine reported reproduces on the JVM." if not unreproduced else
               "Witnesses the JVM does not reproduce: " + "; ".join(f"`{r['case']}` {r['engine']} {r['mode']}{' ' + r['staging'] if r.get('staging') else ''} ({r['witness']})"
                                                                     for r in unreproduced) + ".")
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engines", default=",".join(ENGINES))
    parser.add_argument("--modes", default=",".join(MODES))
    parser.add_argument("--groups", default="1,2,3,4")
    parser.add_argument("--jbmc-staging", default="full-range",
                        help="JBMC's staging policies to run jbmc and auto under, comma-separated (staged, full-range, tight); "
                             "the corpus's tables are over the first, and the others are compared with it. By default the "
                             "tool's own default, full-range, since job 20261106-201041")
    parser.add_argument("--cases", help="only the cases whose id contains this")
    parser.add_argument("--timeout", type=int, default=120, help="seconds each run may take, on either engine")
    parser.add_argument("--search", type=int, default=200000, help="random inputs the JVM tries on each expected proof")
    parser.add_argument("--jvmcontract", default=os.environ.get("JVMCONTRACT") or str(LIB / "target/release/jvmcontract"))
    parser.add_argument("--jbmc", default="jbmc")
    parser.add_argument("--build", default=str(LIB / "target/benchmark"))
    parser.add_argument("--out", help="write the results as JSON here")
    parser.add_argument("--table", help="write the tables as Markdown here")
    parser.add_argument("--render", help="only render the tables of a results file")
    parser.add_argument("--quiet", action="store_true")
    options = parser.parse_args(argv)
    if options.render:
        results = json.loads(Path(options.render).read_text())
    else:
        results = run(options)
        if options.out:
            Path(options.out).write_text(json.dumps(results, indent=1) + "\n")
    table = render(results)
    if options.table:
        Path(options.table).write_text(table)
    else:
        print(table)
    wrong = [r for r in results["runs"] if r["class"] in ("false-success", "false-alarm")]
    disagreements = [cid for cid, a in results["reference"].items() if not a["agrees"]]
    return 1 if wrong or disagreements else 0


if __name__ == "__main__":
    sys.exit(main())

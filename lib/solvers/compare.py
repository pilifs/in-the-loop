#!/usr/bin/env python3
"""The solver comparison of Phase 6c (llm-dlc/loops/engine-priorities.md), on the engine's bit-blasted clauses, or
on its word-level terms (`--words`).

The own checker's full checks over the five workloads where the formula's size dominates (binary search, examples
141 and 142, reverse and prefix sums), each on the bundled CaDiCaL and on Bitwuzla in two configurations, given
the same clauses through the solver interface (lib/src/bmc/sat.rs, bitwuzla.rs). The cases and their command lines
are the benchmark's (lib/benchmark/run.py, imported and not changed), under strict, so a full check here is the run
job -102624 measured, on another solver.

    python3 lib/solvers/compare.py --out lib/solvers/comparison

For each case and solver:

1. the full check, `--repeat` times, with JVMCONTRACT_SOLVER naming the solver. The first run also records its
   solver calls (JVMCONTRACT_TRANSCRIPTS). Its verdict must be the case's expected one on every solver;
2. CaDiCaL's transcripts of the case replayed on every solver (`jvmcontract transcript --solver S --json`),
   `--repeat` times, with no contradiction allowed. A replay asks every solver exactly the same calls, where a full
   check on another solver may take other paths: the engine keeps a path's models, and a split it can settle from
   them costs no call.

It writes `bit-blasted.json` (every run) and `bit-blasted.md` (the tables) to `--out`, and exits 1 if CaDiCaL's
verdict or any decisive verdict is not the expected one, if the solvers' decisive verdicts differ, or if a replay
contradicts its recording. A check that runs out of time on Bitwuzla is a measurement, listed as not decided. Times are medians
of the repeats, with the range beside them; the whole replay's time (reading, adding clauses, calls) is the one to
compare, since Bitwuzla does some of its work on the clauses inside its calls.

With `--words`, the word-level prototype: the same full checks on CaDiCaL and on `bitwuzla-words` in two
configurations, where the engine gives Bitwuzla its gates and word-level operations as terms (lib/src/bmc/sat.rs's
`Terms`) instead of bit-blasting them. There are no transcripts to record or replay then: the solver isn't given
clauses. It writes `word-level.json` and `word-level.md`, and fails as above on the checks.

    python3 lib/solvers/compare.py --words --out lib/solvers/comparison
"""

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
LIB = HERE.parent
REPO = LIB.parent

# The five workloads of the plan's 6c, by their benchmark case: bounded binary search, examples 141 and 142,
# reverse, prefix sums.
CASES = ("real/midpoint/search-within-bound", "example/141", "example/142", "held/reverse", "held/prefix-sums")
SOLVERS = ("cadical", "bitwuzla", "bitwuzla:preprocess=0")
WORD_SOLVERS = ("cadical", "bitwuzla-words", "bitwuzla-words:preprocess=0")
MODE = "strict"


def benchmark():
    """lib/benchmark/run.py as a module: its cases, compilation, command lines and measurement."""
    spec = importlib.util.spec_from_file_location("benchmark_run", LIB / "benchmark/run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def slug(text):
    return "".join(c if c.isalnum() or c in "-." else "_" for c in text)


def spread(values):
    """The median of some seconds, and their range."""
    values = [v for v in values if v is not None]
    if not values:
        return None
    return {"median": round(statistics.median(values), 3), "min": round(min(values), 3), "max": round(max(values), 3), "n": len(values)}


def bitwuzla_library(jvmcontract):
    """Where Bitwuzla's library is, as the binding finds it, with its digest."""
    named = os.environ.get("JVMCONTRACT_BITWUZLA")
    root = Path(named) if named else Path.home() / "tools/bitwuzla/current"
    if root.is_file():
        library = root
    else:
        found = sorted((root / "lib").glob("libbitwuzla.so")) + sorted((root / "lib").glob("*/libbitwuzla.so"))
        library = found[0] if found else None
    if library is None:
        return {"path": None}
    record = {"path": str(library.resolve()), "sha256": hashlib.sha256(library.read_bytes()).hexdigest()}
    build = root.resolve() / "build.json" if root.is_dir() else None
    if build and build.is_file():
        record["build"] = json.loads(build.read_text())
    return record


def environment(run_module, options):
    record = run_module.environment(SimpleNamespace(jvmcontract=options.jvmcontract, jbmc="jbmc"))
    record.pop("jbmc", None)
    record["host"] = platform.node()
    record["bitwuzla"] = bitwuzla_library(options.jvmcontract)
    try:
        record["commit"] = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=30).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        record["commit"] = None
    return record


def check(run_module, case, solver, classes, work, transcripts, options):
    """One full check of a case on a solver; its transcripts go to `transcripts` if that is given."""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    cmd = run_module.command(case, "native", MODE, classes, work, SimpleNamespace(jvmcontract=options.jvmcontract, timeout=options.timeout, jbmc="jbmc"))
    env = dict(os.environ, JVMCONTRACT_SOLVER=solver)
    env.pop("JVMCONTRACT_TRANSCRIPTS", None)
    if transcripts is not None:
        transcripts.mkdir(parents=True, exist_ok=True)
        env["JVMCONTRACT_TRANSCRIPTS"] = str(transcripts)
    measured = measure_env(run_module, cmd, options.timeout * 1.5 + 60, env)
    data = run_module.outcome_of(case, measured["stdout"])
    record = {k: measured[k] for k in ("exit", "seconds", "cpuSeconds", "peakMB")}
    record.update(run_module.classify(case, data, measured))
    record["stats"] = run_module.stats_of(data)
    record["wordOperations"] = (((data or {}).get("search") or {}).get("native") or {}).get("word_operations")
    record["phases"] = run_module.phases_of(data, measured["seconds"])
    stated = ((data or {}).get("stated") or {}).get("checker") or {}
    record["signature"] = stated.get("solver")
    record["checker"] = ((data or {}).get("search") or {}).get("checker")
    if record["class"] not in run_module.CORRECT:
        record["stderr"] = measured["stderr"][-1000:]
    return record


def measure_env(run_module, cmd, limit, env):
    """run.py's `measure`, in an environment of our own: it runs the command in this process's environment."""
    saved = dict(os.environ)
    try:
        os.environ.clear()
        os.environ.update(env)
        return run_module.measure(cmd, limit)
    finally:
        os.environ.clear()
        os.environ.update(saved)


def replay(transcript, solver, options):
    """A transcript run again on a solver, timed from outside as well."""
    start = time.monotonic()
    r = subprocess.run([options.jvmcontract, "transcript", "--solver", solver, "--json", str(transcript)], capture_output=True, text=True, timeout=options.timeout * 4 + 60)
    wall = time.monotonic() - start
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"exit": r.returncode, "wall": round(wall, 3), "problem": (r.stderr or r.stdout)[-500:]}
    return {
        "exit": r.returncode,
        "wall": round(wall, 3),
        "seconds": data["seconds"],
        "solving": data["replayed_seconds"],
        "recorded": data["recorded_seconds"],
        "calls": len(data["calls"]),
        "clauses": data["clauses"],
        "variables": data["variables"],
        "contradictions": data["contradictions"],
        "undecided": data["undecided"],
        "decided": data["decided"],
        "signature": data["solver"],
        "slowest": sorted((c["replayed_seconds"] for c in data["calls"]), reverse=True)[:3],
    }


def run(options):
    run_module = benchmark()
    ids = options.cases.split(",")
    solvers = options.solvers.split(",")
    groups = {2, 3, 4}
    cases = [c for c in run_module.load_cases(groups) if c["id"] in ids]
    missing = sorted(set(ids) - {c["id"] for c in cases})
    if missing:
        raise SystemExit(f"no benchmark case {', '.join(missing)}")
    build = Path(options.build).resolve()
    build.mkdir(parents=True, exist_ok=True)
    classes = {**run_module.compile_sources(build), **run_module.compile_examples(build, cases)}
    checks, replays = [], []
    for case in cases:
        transcripts = {}
        for solver in solvers:
            for n in range(options.repeat):
                work = build / "work" / slug(case["id"]) / slug(solver)
                into = build / "transcripts" / slug(case["id"]) / slug(solver) if n == 0 and not options.words else None
                if into is not None and into.exists():
                    shutil.rmtree(into)
                record = {"case": case["id"], "solver": solver, "run": n + 1, **check(run_module, case, solver, classes, work, into, options)}
                if into is not None:
                    files = sorted(into.glob("*.icnf"), key=lambda p: (len(p.name), p.name))
                    transcripts[solver] = files
                    record["transcripts"] = [{"file": p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]
                checks.append(record)
                if not options.quiet:
                    calls = record["stats"].get("solver_calls")
                    print(f"check  {case['id']:<36} {solver:<24} #{n + 1} {record['verdict']:<12} {record['class']:<10} {record['seconds']:>8.2f} s {calls if calls is not None else '-':>6} calls {record['peakMB']:>7.1f} MB", flush=True)
        for transcript in transcripts.get("cadical", []):
            for solver in solvers:
                for n in range(options.repeat):
                    record = {"case": case["id"], "transcript": transcript.name, "solver": solver, "run": n + 1, **replay(transcript, solver, options)}
                    replays.append(record)
                    if not options.quiet:
                        print(f"replay {case['id']:<36} {transcript.name:<16} {solver:<24} #{n + 1} {record.get('calls', '-'):>6} calls {record.get('seconds', 0):>8.3f} s whole {record.get('solving', 0):>8.3f} s solving, {record.get('contradictions', '-')} contradictions", flush=True)
    about = ("the own checker's full checks on CaDiCaL and on Bitwuzla given the engine's word-level terms" if options.words
             else "the own checker's checks and CaDiCaL's transcripts of them on each solver, on the engine's bit-blasted clauses")
    return {
        "about": f"Results of lib/solvers/compare.py: {about} (Phase 6c of llm-dlc/loops/engine-priorities.md).",
        "kind": "word-level" if options.words else "bit-blasted",
        "environment": environment(run_module, options),
        "settings": {"mode": MODE, "unwind": run_module.UNWIND, "maxArrayLength": run_module.MAX_ARRAY_LENGTH, "timeout": options.timeout, "repeat": options.repeat, "solvers": solvers, "cases": ids},
        "cases": [{k: c[k] for k in ("id", "group", "workload", "kind", "expected")} for c in cases],
        "checks": checks,
        "replays": replays,
    }


DECISIVE = ("verified", "violation")


def problems(results):
    """What makes the comparison fail: CaDiCaL not giving the expected verdict (the baseline), a decisive verdict
    that isn't the expected one on any solver, solvers whose decisive verdicts differ, a replay that contradicts its
    recording or didn't run. Another solver running out of time, or a replay's call stopping at its limit, is a
    measurement ([`undecided`]), not a problem."""
    out = []
    expected = {c["id"]: c["expected"] for c in results["cases"]}
    for r in results["checks"]:
        if r["verdict"] != expected[r["case"]] and (r["solver"] == "cadical" or r["verdict"] in DECISIVE):
            out.append(f"{r['case']} on {r['solver']} (run {r['run']}): {r['verdict']}, expected {expected[r['case']]} ({r.get('reason') or r['class']})")
    for case in expected:
        verdicts = {r["verdict"] for r in results["checks"] if r["case"] == case and r["verdict"] in DECISIVE}
        if len(verdicts) > 1:
            out.append(f"{case}: the solvers' verdicts differ ({', '.join(sorted(verdicts))})")
    for r in results["replays"]:
        if r.get("contradictions") is None:
            out.append(f"{r['case']} {r['transcript']} on {r['solver']}: the replay failed (exit {r['exit']}): {r.get('problem', '').strip()}")
        elif r["contradictions"]:
            out.append(f"{r['case']} {r['transcript']} on {r['solver']}: {r['contradictions']} contradictions")
    return out


def undecided(results):
    """What another solver didn't decide: checks with no verdict, and replays with calls stopped at their limit."""
    out = []
    for r in results["checks"]:
        if r["verdict"] not in DECISIVE and r["solver"] != "cadical":
            out.append(f"{r['case']} on {r['solver']} (run {r['run']}): {r['verdict']} ({r.get('reason') or r['class']}) after {r['seconds']:.1f} s")
    for r in results["replays"]:
        if r.get("undecided"):
            out.append(f"{r['case']} {r['transcript']} on {r['solver']} (run {r['run']}): {r['undecided']} of {r['calls']} calls stopped at their recorded limit")
    return out


def fmt(s):
    if s is None:
        return "–"
    if s["n"] == 1 or s["min"] == s["max"]:
        return f"{s['median']:.3f}"
    return f"{s['median']:.3f} ({s['min']:.3f}–{s['max']:.3f})"


def render(results):
    solvers = results["settings"]["solvers"]
    env = results["environment"]
    words = results.get("kind") == "word-level"
    lines = [f"# The solver comparison, {results.get('kind', 'bit-blasted')}", "",
             f"`lib/solvers/compare.py` at `{(env.get('commit') or '?')[:12]}` on {env.get('host')} ({env.get('machine')}, {env.get('cpu')}, {env.get('cpus')} CPUs), {env.get('date')}: "
             f"{env.get('jvmcontract')}, {env.get('java')}. Each case under {results['settings']['mode']}, unwind {results['settings']['unwind']}, arrays up to {results['settings']['maxArrayLength']}, "
             f"{results['settings']['repeat']} runs of each check and replay; seconds are the median, with the range in brackets.", ""]
    signatures = sorted({r["signature"] for r in results["checks"] if r.get("signature")})
    lines += ["The solvers, as the checks' statements name them:", ""] + [f"- {s}" for s in signatures] + [""]
    library = env.get("bitwuzla") or {}
    if library.get("path"):
        lines += [f"Bitwuzla's library: `{library['path']}`, sha256 `{library['sha256'][:16]}…`.", ""]
    if words:
        lines += ["CaDiCaL is given the engine's clauses; `bitwuzla-words` its gates as Boolean terms and its word-level operations as bit-vector terms, "
                  "so its clause count is only the constant's unit clause, and *Word ops* counts the operations it was given as terms.", ""]
    extra = " Word ops |" if words else ""
    lines += ["## Full checks", "", f"| Case | Solver | Verdict | Seconds | Solver calls | Clauses |{extra} Solving (engine) | Peak MB |", "|---|---|---|---:|---:|---:|" + ("---:|" if words else "") + "---:|---:|"]
    for case in results["settings"]["cases"]:
        for solver in solvers:
            runs = [r for r in results["checks"] if r["case"] == case and r["solver"] == solver]
            if not runs:
                continue
            verdicts = sorted({r["verdict"] for r in runs})
            first = runs[0]["stats"]
            solving = spread([r["stats"].get("solving_seconds") for r in runs])
            ops = f" {runs[0].get('wordOperations') or '–'} |" if words else ""
            lines.append(f"| {case} | {solver} | {', '.join(verdicts)} | {fmt(spread([r['seconds'] for r in runs]))} | {first.get('solver_calls', '–')} | {first.get('clauses', '–')} |{ops} {fmt(solving)} | {max(r['peakMB'] for r in runs):.0f} |")
    if not words:
        lines += replay_table(results, solvers)
    found = problems(results)
    lines += ["", "## Problems", ""] + ([f"- {p}" for p in found] if found else ["None: every decisive verdict is the expected one, CaDiCaL's on every case" + ("." if words else ", and every replay agrees with its recording.")])
    left = undecided(results)
    lines += ["", "## Not decided", ""] + ([f"- {p}" for p in left] if left else ["Nothing: every check gave a verdict" + ("." if words else ", and every replayed call an answer.")])
    return "\n".join(lines) + "\n"


def replay_table(results, solvers):
    lines = ["", "## CaDiCaL's transcripts replayed", "",
              "The same calls on every solver. *Whole* is the replay's own time: reading the transcript, adding the clauses and every call; *solving* is the time inside the calls.", "",
              "| Case | Transcript | Calls | Clauses | Solver | Whole s | Solving s | Contradictions |", "|---|---|---:|---:|---|---:|---:|---:|"]
    keys = []
    for case in results["settings"]["cases"]:
        for r in results["replays"]:
            if r["case"] == case and (case, r["transcript"]) not in keys:
                keys.append((case, r["transcript"]))
    for case, transcript in keys:
        for solver in solvers:
            runs = [r for r in results["replays"] if r["case"] == case and r["transcript"] == transcript and r["solver"] == solver]
            if not runs:
                continue
            first = runs[0]
            contradictions = sum(r.get("contradictions") or 0 for r in runs) if all("contradictions" in r for r in runs) else "failed"
            lines.append(f"| {case} | {transcript} | {first.get('calls', '–')} | {first.get('clauses', '–')} | {solver} | {fmt(spread([r.get('seconds') for r in runs]))} | {fmt(spread([r.get('solving') for r in runs]))} | {contradictions} |")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--solvers", help="names as JVMCONTRACT_SOLVER takes them (default: " + ",".join(SOLVERS) + ", or with --words " + ",".join(WORD_SOLVERS) + ")")
    parser.add_argument("--words", action="store_true", help="the word-level prototype: Bitwuzla given the engine's terms, full checks only")
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=600, help="seconds each check may take")
    parser.add_argument("--jvmcontract", default=os.environ.get("JVMCONTRACT") or str(LIB / "target/release/jvmcontract"))
    parser.add_argument("--build", default=str(LIB / "target/solver-comparison"))
    parser.add_argument("--out", help="write bit-blasted.json and bit-blasted.md (word-level.* with --words) into this directory")
    parser.add_argument("--render", help="only render the tables of a results file")
    parser.add_argument("--quiet", action="store_true")
    options = parser.parse_args(argv)
    if options.solvers is None:
        options.solvers = ",".join(WORD_SOLVERS if options.words else SOLVERS)
    if options.render:
        results = json.loads(Path(options.render).read_text())
    else:
        results = run(options)
    table = render(results)
    if options.out and not options.render:
        out = Path(options.out)
        out.mkdir(parents=True, exist_ok=True)
        name = results.get("kind", "bit-blasted")
        (out / f"{name}.json").write_text(json.dumps(results, indent=1) + "\n")
        (out / f"{name}.md").write_text(table)
    print(table)
    return 1 if problems(results) else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""The economics of the proof cache on the recorded examples (S6 of llm-dlc/loops/foundations-summaries.md).

What a rerun and a change cost once proofs are kept, measured on the recorded B9 and B11 examples of the apps built
with javac (Crosscut, Quorum, Mica), with `jvmcontract equivalence --cache` as build.py runs a B9 example with
`approach.cache`. Every recorded example is listed; the cache serves those whose claim it can key, the B9 examples
proved by the tool's own checker (`--engine native`). The others are counted with the reason: a B9 example under
JBMC (its claim JBMC may decide, and JBMC's identity is not in the key, so the tool refuses to cache it), a B11
example (`prove` has no proof cache).

The runs, in order, each claim checked by a process of its own, one after another:
1. **cold**: each served example's claim as build.py runs it (the unpatched app against the app with the example's
   patch), on an empty cache. It fills the cache the warm runs use.
2. **warm**: the same claims again, on that cache.
3. For each app with a served claim, and each kind of change in examples/tools/economics/ (an unrelated edit, a
   behaviour-preserving helper rewrite, a representation change, a real regression), two sets of claims:
   - **rebased**: each served example of the app with the change beneath it, on both sides: the app with the change
     against the app with the change and the example's patch. An example whose patch doesn't apply on top of the
     change is listed as not rebased.
   - **own**: the change itself, on the targets of the app's served examples: the app against the app with the
     change, with each example's settings and its domain (`--unchanged-unless`), and none of its patch's mappings.
   Each set runs warm (on the cache the runs so far filled) and cold (on an empty cache of its own), and every warm
   verdict must be the cold one.

Per claim it records the verdict, how the cache served it (an exact hit; nothing to prove, the closure being
identical; proved with a changed helper's proof, found in the cache or made in the run; proved or refuted with no
reuse; unresolved), and the time: the process's wall time, the checker's (the outcome's `search.seconds`: symbolic
execution and the solver), the cache's own (computing the claim's key, from both versions' closures, the harness's
digest and the tools', and looking it up, from the tool's note), the changed helpers' own checks (each from its note),
and the rest (preparing the check: loading classes, the harness, the plan; replaying a witness; writing the report).
On an exact hit the helpers' checks, themselves exact hits, are in the rest: the hit's report is the stored one.
Compiling the builds is apart, as `javac` time.

It writes report.json and report.md to --out (examples/tools/economics/ by default), prints the Markdown, and exits
1 when an expectation fails (each is in the report: the warm verdicts are the cold ones; the warm rerun is an exact
hit wherever the cold run stored a result; and what each kind of change should do) or a check failed to run.
`--plan` builds every tree and lists the claims, and proves nothing.

Usage: python3 examples/tools/economics.py [--jvmcontract PATH] [--out DIR] [--plan] [--app APP]...
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402  (TOOL_APPS, proof_options, stage_contracts, app_of, IGNORE)

REPO = build.REPO
CHANGES = HERE / "economics"
KINDS = ("unrelated", "helper-rewrite", "representation", "regression")
KIND_WORDS = {
    "unrelated": "an unrelated edit",
    "helper-rewrite": "a behaviour-preserving helper rewrite",
    "representation": "a representation change",
    "regression": "a real regression",
}

# The notes `jvmcontract equivalence --cache` writes (lib/src/proof_cache.rs).
TIMING = re.compile(r"^note: the proof cache took ([\d.]+) s to compute this claim's key .* and ([\d.]+) s to look it up", re.M)
HELPER_TIME = re.compile(r"^note: ([\w.$]+)'s own check took ([\d.]+) s$", re.M)
HELPER_SHARED = re.compile(r"^note: ([\w.$]+), changed: .*, (found in the proof cache|proved now and stored in the proof cache) \(claim (sha256:\w+)\); one function in both versions$", re.M)
HELPER_KEPT = re.compile(r"^note: ([\w.$]+), changed, stays as written in both versions: (.*)$", re.M)
KEY = re.compile(r"(?:has no result for this claim \(|an exact hit of claim |stored in the proof cache as claim )(sha256:\w+)")
NOT_USED = re.compile(r"^note: the proof cache is not used: (.*)$", re.M)


def served(example):
    """Why the proof cache can't serve an example's claim, or None when it can."""
    a = example["approach"]
    if a["id"] == "B11":
        return "a property proof (`prove`), which has no proof cache: the cache is in `equivalence` only"
    if a.get("engine") != "native":
        return (f"a regression proof under --engine {a.get('engine') or 'jbmc'}, which JBMC may decide: JBMC's identity is "
                "not part of the claim's key, so the tool doesn't cache it")
    return None


def recorded():
    """Every B9 and B11 example in the repository, as (included, excluded): the constructed ones on a javac app,
    each with the reason the cache doesn't serve it (None when it does), and the rest with why they are left out."""
    included, excluded = [], []
    for folder in sorted(build.EXAMPLES.glob("[0-9][0-9][0-9]-*")):
        if not (folder / "example.json").is_file():
            continue
        example = json.loads((folder / "example.json").read_text())
        if example["approach"]["id"] not in ("B9", "B11"):
            continue
        app = build.app_of(example)
        if example["origin"] != "constructed":
            excluded.append({"id": example["id"], "why": "a real-world example: its classes are not in the repository"})
        elif app not in build.TOOL_APPS:
            excluded.append({"id": example["id"], "why": "a Box Office example, built with Gradle"})
        else:
            included.append({"id": example["id"], "folder": folder, "example": example, "app": app, "unserved": served(example)})
    return included, excluded


def settings(example):
    """The flags of an example's proof besides the claim's mappings: engine, gaps, bounds, contracts. Its own cache
    directory (`approach.cache`) is left out: these runs give their own."""
    flags = build.proof_options(example)
    if "--cache" in flags:
        i = flags.index("--cache")
        del flags[i:i + 2]
    return flags


def recorded_claim(x):
    """An example's own claim, as build.py's B9 run states it."""
    change, flags = x["example"]["change"], []
    if change.get("intendedInputs"):
        flags += ["--unchanged-unless", change["intendedInputs"]]
    if change.get("previousSymbol"):
        flags += ["--before-target", change["previousSymbol"]]
    if change.get("previousArguments"):
        flags += ["--before-arguments", change["previousArguments"]]
    if change.get("resultsAgreeWhen"):
        flags += ["--results-agree-when", change["resultsAgreeWhen"]]
    return {"target": x["example"]["subject"]["symbol"], "flags": flags + settings(x["example"])}


def own_claim(x):
    """The claim a change of the app makes on an example's target: the same method in both versions, with the
    example's domain and settings, and none of its patch's mappings (a renamed method, mapped arguments, a relation
    between the results)."""
    intended = x["example"]["change"].get("intendedInputs")
    return {"target": x["example"]["subject"]["symbol"], "flags": (["--unchanged-unless", intended] if intended else []) + settings(x["example"])}


def change_patch(app, kind):
    return CHANGES / f"{app}-{kind}.patch"


class Trees:
    """The builds the runs compare, each an app with some patches applied in order, compiled once with javac."""

    def __init__(self, work):
        self.work = work
        self.built = {}
        self.seconds = 0.0
        self.locks = {}
        self.lock = threading.Lock()

    def key(self, app, patches):
        h = hashlib.sha256(app.encode())
        for p in patches:
            h.update(b"\0" + p.encode())
        return f"{app}-{h.hexdigest()[:12]}"

    def get(self, app, patches, folder=None, example=None):
        """The tree's app root and classes, or (None, why) when a patch doesn't apply. `folder` and `example` stage
        an example's contracts in the tree, as build.py does."""
        name = self.key(app, patches)
        with self.lock:
            tree_lock = self.locks.setdefault(name, threading.Lock())
        with tree_lock:
            self.build(name, app, patches)
        app_root, classes, why = self.built[name]
        if why is None and folder is not None:
            build.stage_contracts(folder, example, app_root)
        return (app_root, classes) if why is None else (None, why)

    def build(self, name, app, patches):
        if name not in self.built:
            root = self.work / "trees" / name
            shutil.rmtree(root, ignore_errors=True)
            part = build.TOOL_APPS[app]["root"]
            shutil.copytree(REPO / part, root / part, ignore=build.IGNORE)
            why = None
            for n, patch in enumerate(patches):
                env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(root.resolve().parent))
                proc = subprocess.run(["git", "apply", "-p1", "--verbose", "-"], input=patch, cwd=root, env=env, capture_output=True, text=True)
                if proc.returncode != 0 or "Skipped patch" in proc.stderr:
                    why = f"patch {n + 1} of {len(patches)} does not apply: " + (proc.stderr.strip().splitlines() or ["no output"])[-1]
                    break
            classes = root / part / "build/main"
            if why is None:
                sources = sorted((root / part / "src/main/java").rglob("*.java"))
                classes.mkdir(parents=True, exist_ok=True)
                started = time.monotonic()
                proc = subprocess.run(["javac", "-parameters", "-g", "-proc:none", "-d", str(classes), *map(str, sources)], capture_output=True, text=True)
                with self.lock:
                    self.seconds += time.monotonic() - started
                if proc.returncode != 0:
                    why = "javac failed: " + (proc.stderr.strip().splitlines() or ["no output"])[0]
            self.built[name] = (root / part, classes, why)


def measure(outcome, output, wall):
    """What a check's outcome and output say about it: its verdict, how the cache served it, and its time."""
    record = {"verdict": (outcome or {}).get("verdict"), "wall": round(wall, 3)}
    reuse = (outcome or {}).get("reuse")
    exact = bool(reuse and reuse.get("kind") == "exact")
    search = (outcome or {}).get("search")
    timing = TIMING.search(output)
    record["checker"] = round(search["seconds"], 3) if search else 0.0
    record["hashing"] = round(float(timing[1]) + float(timing[2]), 3) if timing else 0.0
    key = KEY.search(output)
    record["key"] = key[1] if key else None
    record["stored"] = "note: stored in the proof cache as claim" in output
    not_used = NOT_USED.search(output)
    record["cacheNotUsed"] = not_used[1] if not_used else None
    # A hit's report is the stored one: its helper notes are that run's, not this one's.
    helpers = []
    if not exact:
        times = {m[1]: float(m[2]) for m in HELPER_TIME.finditer(output)}
        for m in HELPER_SHARED.finditer(output):
            helpers.append({"callee": m[1], "shared": True, "found": m[2] == "found in the proof cache", "key": m[3], "seconds": times.get(m[1], 0.0)})
        for m in HELPER_KEPT.finditer(output):
            helpers.append({"callee": m[1], "shared": False, "why": m[2], "seconds": times.get(m[1], 0.0)})
    record["helpers"] = helpers
    record["helperSeconds"] = round(sum(h["seconds"] for h in helpers), 3)
    record["other"] = round(max(0.0, wall - record["checker"] - record["hashing"] - record["helperSeconds"]), 3)
    replay = (outcome or {}).get("replay")
    record["replayed"] = replay.get("reproduced") if replay else None
    proof = (outcome or {}).get("proof") or ""
    if outcome is None:
        record["served"] = "error"
    elif exact:
        record["served"] = "exact hit"
    elif not search and "nothing to prove" in proof:
        record["served"] = "nothing to prove"
    elif record["verdict"] == "unverifiable":
        record["served"] = "unresolved"
    elif any(h["shared"] for h in helpers):
        record["served"] = "helper evidence found" if any(h["shared"] and h["found"] for h in helpers) else "helper proved in the run"
    else:
        record["served"] = "refuted" if record["verdict"] == "violation" else "proved"
    return record


def check(exe, claim, before, after, cwd, cache, work):
    """One claim, checked by a process of its own on `cache`."""
    shutil.rmtree(work, ignore_errors=True)
    command = [exe, "equivalence", "--before", str(before), "--after", str(after), "--target", claim["target"], *claim["flags"],
               "--cache", str(cache), "--work", str(work), "--json"]
    started = time.monotonic()
    proc = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    wall = time.monotonic() - started
    try:
        outcome = json.loads(proc.stdout)
    except ValueError:
        outcome = None
    if not (isinstance(outcome, dict) and isinstance(outcome.get("output"), str)):
        outcome = None
    output = (outcome or {}).get("output", "") + proc.stderr
    record = measure(outcome, output, wall)
    if outcome is None:
        record["error"] = f"exit {proc.returncode}: " + "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-5:])
    return record


def claim_sets(included, apps):
    """The runs' claims: the served examples' own (cold and warm), and per app and kind the rebased and own ones."""
    servable = [x for x in included if x["unserved"] is None and x["app"] in apps]
    base = [{"id": x["id"], "x": x, "claim": recorded_claim(x), "before": [], "after": [x["patch"]]} for x in servable]
    changes = []
    for app in sorted({x["app"] for x in servable}):
        mine = [x for x in servable if x["app"] == app]
        for kind in KINDS:
            path = change_patch(app, kind)
            if not path.is_file():
                sys.exit(f"{path} is missing: each app with a served claim has a change of each kind")
            c = path.read_text()
            rebased = [{"id": x["id"], "x": x, "claim": recorded_claim(x), "before": [c], "after": [c, x["patch"]]} for x in mine]
            own, seen = [], set()
            for x in mine:
                claim = own_claim(x)
                signature = json.dumps(claim)
                if signature not in seen:
                    seen.add(signature)
                    own.append({"id": f"{app}:{claim['target']}" + (f" (as {x['id']})" if len([y for y in mine if y['example']['subject']['symbol'] == claim['target']]) > 1 else ""),
                                "x": x, "claim": claim, "before": [], "after": [c]})
            changes.append({"app": app, "kind": kind, "patch": path.relative_to(REPO).as_posix(), "rebased": rebased, "own": own})
    return base, changes


def run_set(exe, trees, items, cache, work, label):
    """Checks each item on `cache`, in order; an item whose trees don't build is recorded as not run."""
    out = []
    for n, item in enumerate(items):
        x = item["x"]
        before_root, before = trees.get(x["app"], item["before"])
        after_root, after = trees.get(x["app"], item["after"], x["folder"], x["example"])
        row = {"id": item["id"], "example": x["id"], "target": item["claim"]["target"], "flags": item["claim"]["flags"]}
        if before_root is None or after_root is None:
            row.update({"served": "not run", "why": before if before_root is None else after})
        else:
            row.update(check(exe, item["claim"], before, after, after_root, cache, work / f"{label}-{n}"))
        print(f"  {label} {row['id']}: {row.get('verdict')} ({row['served']}, {row.get('wall', 0):.2f} s)", flush=True)
        out.append(row)
    return out


def totals(rows):
    ran = [r for r in rows if r["served"] not in ("not run",)]
    t = {k: round(sum(r.get(k, 0.0) for r in ran), 3) for k in ("wall", "checker", "hashing", "helperSeconds", "other")}
    t["claims"] = len(rows)
    t["served"] = {s: sum(r["served"] == s for r in rows) for s in sorted({r["served"] for r in rows})}
    t["helperChecks"] = sum(len(r.get("helpers", [])) for r in ran)
    return t


def compare(warm, cold):
    """The claims whose warm verdict differs from the cold one."""
    by_id = {r["id"]: r for r in cold}
    return [{"id": r["id"], "warm": r.get("verdict"), "cold": by_id[r["id"]].get("verdict")} for r in warm
            if r["served"] != "not run" and r["id"] in by_id and r.get("verdict") != by_id[r["id"]].get("verdict")]


def expectations(runs):
    """What the runs should show, each with whether it does."""
    out = []

    def expect(what, failures):
        out.append({"expectation": what, "passed": not failures, "failures": failures})

    cold, warm = runs[0]["rows"], runs[1]["rows"]
    errors = [f"{r['name']}: {row['id']}: {row['error']}" for r in runs for row in r["rows"] if row.get("error")]
    expect("every check ran and gave an outcome", errors)
    differing = [f"{r['name']}: {d['id']}: warm {d['warm']}, cold {d['cold']}" for r in runs if r.get("against") for d in r["differs"]]
    expect("every warm verdict is the cold run's", differing)
    stored = {r["id"] for r in cold if r.get("stored")}
    expect("the warm rerun is an exact hit wherever the cold run stored a result, with its verdict",
           [f"{r['id']}: {r['served']}" for r in warm if r["id"] in stored and r["served"] != "exact hit"]
           + [f"{d['id']}: warm {d['warm']}, cold {d['cold']}" for d in compare(warm, cold)])
    for r in runs:
        kind, app, warm_run = r.get("kind"), r.get("app"), r.get("against") is not None
        if not kind or not warm_run:
            continue
        rows = r["rows"]
        if kind == "unrelated" and r["set"] == "rebased":
            expect(f"{app}, {KIND_WORDS[kind]}: every rebased claim the cold run stored is an exact hit",
                   [f"{row['id']}: {row['served']}" for row in rows if row["id"] in stored and row["served"] not in ("exact hit", "not run")])
        if kind == "unrelated" and r["set"] == "own":
            expect(f"{app}, {KIND_WORDS[kind]}: the change's own claims have nothing to prove",
                   [f"{row['id']}: {row['served']}" for row in rows if row["served"] != "nothing to prove"])
        if kind == "helper-rewrite" and r["set"] == "own":
            shared = [row for row in rows if any(h["shared"] for h in row.get("helpers", []))]
            found = [row for row in shared if any(h["shared"] and h["found"] for h in row["helpers"])]
            expect(f"{app}, {KIND_WORDS[kind]}: a claim proves with the rewritten helper as one function, and another finds that helper's proof in the cache",
                   ([] if shared else ["no claim shared the helper"]) + ([] if found else ["no claim found the helper's proof in the cache"]))
        if kind == "representation" and r["set"] == "own":
            expect(f"{app}, {KIND_WORDS[kind]}: no helper is shared, and a claim is proved again",
                   [f"{row['id']}: shared {', '.join(h['callee'] for h in row['helpers'] if h['shared'])}" for row in rows if any(h["shared"] for h in row.get("helpers", []))]
                   + ([] if any(row["served"] == "proved" and row.get("verdict") == "verified" for row in rows) else ["no claim was proved again"]))
        if kind == "regression" and r["set"] == "own":
            expect(f"{app}, {KIND_WORDS[kind]}: a claim is refuted with a witness that replays",
                   [] if any(row.get("verdict") == "violation" and row.get("replayed") for row in rows) else ["no claim refuted with a replayed witness"])
    return out


def markdown(report):
    lines = ["# The proof cache's economics on the recorded examples", "",
             f"Made by `examples/tools/economics.py` at {report['when']}, with jvmcontract `{report['jvmcontract']}`.", "",
             f"Recorded B9 and B11 examples: {report['counts']['recorded']}. Left out: {len(report['excluded'])} "
             "(real-world or Box Office). Of the rest, the cache serves "
             f"{report['counts']['served']}; it does not serve {report['counts']['unserved']}:", ""]
    for why, ids in report["unserved"].items():
        lines.append(f"- {len(ids)}, {why}: {', '.join(ids)}")
    lines += ["", "Times are in seconds, summed over a run's checks: the checker's (symbolic execution and the solver), the "
              "cache's own (the claim's key and its lookup), the changed helpers' own checks, and the rest (preparation, "
              "replay, the report).", "",
              "| Run | Claims | How served | Wall | Checker | Cache | Helpers | Rest | Verdicts as cold |", "|---|---|---|---|---|---|---|---|---|"]
    for r in report["runs"]:
        t = r["totals"]
        served = "; ".join(f"{n} {s}" for s, n in t["served"].items())
        same = "—" if not r.get("against") else ("yes" if not r["differs"] else f"no: {len(r['differs'])} differ")
        lines.append(f"| {r['name']} | {t['claims']} | {served} | {t['wall']:.2f} | {t['checker']:.2f} | {t['hashing']:.2f} | {t['helperSeconds']:.2f} | {t['other']:.2f} | {same} |")
    lines += ["", f"Compiling the builds took {report['javacSeconds']:.1f} s with javac, apart from the runs.", "", "## Expectations", ""]
    for e in report["expectations"]:
        lines.append(f"- {'✓' if e['passed'] else '✗'} {e['expectation']}" + ("" if e["passed"] else ": " + "; ".join(e["failures"][:8])))
    lines += ["", "## Claims", ""]
    for r in report["runs"]:
        lines += [f"### {r['name']}", "", "| Claim | Verdict | How served | Wall | Checker | Cache | Helpers |", "|---|---|---|---|---|---|---|"]
        for row in r["rows"]:
            helpers = "; ".join(f"{h['callee']} {'shared, ' + ('found' if h['found'] else 'proved') if h['shared'] else 'as written'}" for h in row.get("helpers", []))
            if row["served"] == "not run":
                lines.append(f"| {row['id']} | — | not run: {row['why']} | | | | |")
            else:
                lines.append(f"| {row['id']} | {row.get('verdict')} | {row['served']} | {row['wall']:.2f} | {row['checker']:.2f} | {row['hashing']:.3f} | {helpers} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--jvmcontract", default=os.environ.get("JVMCONTRACT") or str(REPO / "lib/target/release/jvmcontract"))
    parser.add_argument("--out", default=str(CHANGES))
    parser.add_argument("--plan", action="store_true", help="build every tree and list the claims; prove nothing")
    parser.add_argument("--app", action="append", help="only this app (repeatable); all by default")
    args = parser.parse_args(argv)
    apps = set(args.app or build.TOOL_APPS)
    included, excluded = recorded()
    for x in included:
        x["patch"] = (x["folder"] / x["example"]["change"]["patch"]).read_text()
    base, changes = claim_sets(included, apps)
    # In a pipeline job, under the job's work directory, kept when the job fails (build.py's kept workspace).
    kept = build.kept_workspace()
    if kept:
        kept.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="economics-", dir=kept))
    trees = Trees(work)
    exe = str(Path(args.jvmcontract).resolve())

    if args.plan:
        items = base + [i for c in changes for i in c["rebased"] + c["own"]]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda i: (trees.get(i["x"]["app"], i["before"]), trees.get(i["x"]["app"], i["after"])), items))
        print(f"served: {len(base)} claims; not served: {sum(1 for x in included if x['unserved'])}; left out: {len(excluded)}")
        for c in changes:
            print(f"{c['app']} {c['kind']}:")
            for s in ("rebased", "own"):
                for i in c[s]:
                    _, why = trees.get(i["x"]["app"], i["after"])
                    _, before_why = trees.get(i["x"]["app"], i["before"])
                    problem = why if isinstance(why, str) else before_why if isinstance(before_why, str) else None
                    print(f"  {s} {i['id']} {i['claim']['target']} {' '.join(i['claim']['flags'])}" + (f"  NOT RUN: {problem}" if problem else ""))
        print(f"javac: {trees.seconds:.1f} s")
        return 0

    if not Path(exe).is_file():
        sys.exit(f"jvmcontract not found at {exe}")
    warm_cache = work / "cache-warm"
    runs = []

    def run(name, items, cache, against=None, **extra):
        print(f"{name}:", flush=True)
        rows = run_set(exe, trees, items, cache, work, name.replace(" ", "-").replace(",", ""))
        entry = {"name": name, "rows": rows, "totals": totals(rows), **extra}
        if against is not None:
            entry["against"] = against["name"]
            entry["differs"] = compare(rows, against["rows"])
        runs.append(entry)
        return entry

    cold = run("cold", base, warm_cache)
    run("warm", base, warm_cache, against=cold)
    for c in changes:
        for s in ("rebased", "own"):
            name = f"{c['app']}, {KIND_WORDS[c['kind']]}, {s}"
            cold = run(f"{name}, cold", c[s], work / f"cache-{c['app']}-{c['kind']}-{s}", app=c["app"], kind=c["kind"], set=s)
            run(f"{name}, warm", c[s], warm_cache, against=cold, app=c["app"], kind=c["kind"], set=s)
    unserved = {}
    for x in included:
        if x["unserved"]:
            unserved.setdefault(x["unserved"], []).append(x["id"])
    tool = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip()
    report = {
        "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "jvmcontract": f"{tool} (sha256:{hashlib.sha256(Path(exe).read_bytes()).hexdigest()[:16]})",
        "counts": {"recorded": len(included) + len(excluded), "served": sum(1 for x in included if not x["unserved"]), "unserved": sum(1 for x in included if x["unserved"])},
        "excluded": excluded,
        "unserved": unserved,
        "changes": [{"app": c["app"], "kind": c["kind"], "patch": c["patch"]} for c in changes],
        "javacSeconds": round(trees.seconds, 1),
        "runs": runs,
    }
    report["expectations"] = expectations(runs)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    text = markdown(report)
    (out / "report.md").write_text(text)
    print(text)
    return 0 if all(e["passed"] for e in report["expectations"]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

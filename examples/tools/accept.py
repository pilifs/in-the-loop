#!/usr/bin/env python3
"""Whether an answer given beside the route is the answer its evidence gives: the acceptance check.

    accept.py NNN [TASK ...]           a line per answer, and why one is not accepted
    accept.py NNN [TASK ...] --json    the same as data, every check with what it compared

A proof task's answer can be given beside the route: a script of the example's own (proofs/prove.py) run as a
verification job, recorded on the task as `besideRoute` (the answer, the job). "The job passed" says only that the
script exited 0. This reads what the job left and derives the answer from it, and accepts the recorded answer only
when every one of these holds; one that fails, or that the evidence has nothing to show (`unbound`), refuses it:

    job         the job's result is in the checkout, passed, of the job file as it is, and names the example
    step        one of its steps ran the example's driver on this task, `python3 [-I] <folder>/proofs/prove.py TASK`
                with the driver at that path in the job's checkout; the outcome is the one that step wrote
    outcome     the outcome file is among the job's collected outputs and has the bytes the result records
    conclusion  the outcome's own verdict is the recorded answer (verified: established, violation: refuted)
    claim       the claim file is the one the job ran (its bytes at the job's source commit) and the one frozen
                (llm-dlc/decisions/*-claims.json, where the example has an entry)
    task        the task's target, claim, expectation, engine, gap mode, revision or pair and allowed change are
                what they were at the job's source commit
    expressions the outcome's assumption, assertion and throws clauses are the claim file's, and for a preservation
                claim the allowed change is the one in the generated pair the job collected, or none where the task
                allows none
    entry       the outcome is about the entry the task's invocation names, or the adapter entry a claim's assumption
                names, or the task's own target: a whole `Class#method`, not a part of one
    domain      the bound is the claim's (a task's own `bounds` does not lower it). A proof at a smaller bound
                establishes nothing about the claim's; a witness found at a smaller bound refutes it, since it lies in
                the claim's domain; the parameters that may be null are the claim's, and a witness's null input is of
                one of them
    mode        the engine and the gap mode are the task's
    complete    (established) no unfinished unwinding and no problem
    non-vacuous (established) some input reaches the property: the probe's witness; for a task with an allowed
                change, one the outcome says lies outside that change (`vacuity.outside`), since the versions are
                compared on no input inside it
    replay      (refuted) the witness reproduced on a JVM, and where the claim assumes something, a record that the
                assumption held on it: the harness the JVM ran, whose source the job collected
                (`work/harness/PropertyHarness.java`), returns before the call wherever the outcome's assumption does
                not hold, so its failure there is on an assumed input
    mutant      (a constructed mutant's task) the JAR's hash in the step's log is the one the mutant replay's receipt
                records
    artifacts   the JARs, the adapter sources and the claim the driver recorded beside the outcome (evidence.json)
                are the ones target.json pins (a constructed mutant's: its base's, but for its own JAR, which is the
                `mutant` check's), and the driver it recorded is the one at the job's source commit. A driver that
                records none leaves a limit, not a refusal: the pinned hashes were then checked by the driver's own
                code and are in no record

`limits` says what an accepted answer still rests on that no record shows; `restsOn` what the checker itself assumed.
A driver writes evidence.json with `record` below. llm-dlc/tools/changes.py counts an answer beside the route only
when this accepts it.

It only reads. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ANSWER = {"verified": "established", "violation": "refuted"}
OK, FAIL, UNBOUND = "ok", "fail", "unbound"
FROZEN = ("kind", "relation", "revision", "pair", "target", "claim", "expected", "engine", "gaps", "allowedChange", "bounds")
TRIAL_FLAGS = ("--max-array-length", "--unwind")
EVIDENCE = "evidence.json"
EVIDENCE_SCHEMA = "beside-route-evidence/v1"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str | None:
    try:
        return sha256(path.read_bytes())
    except OSError:
        return None


def load(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


class Source:
    """A file's bytes at a commit of this repository: git's, by the checkout's own .git or, in a jj workspace that has
    none, the repository jj keeps (`jj git root`). `None` where the commit or the file is not there."""

    def __init__(self, root: Path):
        self.root, self.cache, self.git = root, {}, None

    def git_dir(self) -> list[str] | None:
        if self.git is None:
            self.git = []
            if (self.root / ".git").exists():
                self.git = ["git", "-C", str(self.root)]
            elif (self.root / ".jj").exists():
                r = subprocess.run(["jj", "git", "root", "--ignore-working-copy"], cwd=self.root, capture_output=True, text=True)
                if r.returncode == 0 and r.stdout.strip():
                    self.git = ["git", "--git-dir", r.stdout.strip()]
        return self.git or None

    def has(self, commit: str) -> bool:
        git = self.git_dir()
        return bool(git) and subprocess.run([*git, "cat-file", "-e", f"{commit}^{{commit}}"], capture_output=True).returncode == 0

    def __call__(self, commit: str, path: str) -> bytes | None:
        key = (commit, path)
        if key not in self.cache:
            git = self.git_dir()
            r = subprocess.run([*git, "show", f"{commit}:{path}"], capture_output=True) if git else None
            self.cache[key] = r.stdout if r is not None and r.returncode == 0 else None
        return self.cache[key]


ENTRY = re.compile(r"[\w.$]+#[\w$]+")
ADAPTER_ENTRY = re.compile(r"\badapter entry ([\w.$]+#[\w$]+)")
GATE = "{ return; } // the inputs the property is about"


def read_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return ""


def gates_on(source: str, assume: str) -> bool:
    """Whether a property harness's source returns first, before anything else in `check`, wherever ASSUME does not
    hold: `if (!(ASSUME)) { return; }`, as the checker writes it (lib/src/harness, `property_source`)."""
    lines = [line.strip() for line in source.splitlines()]
    at = next((i for i, line in enumerate(lines) if line.startswith("public static void check(")), None)
    first = next((line for line in lines[at + 1 :] if line), "") if at is not None else ""
    return first == f"if (!({assume})) {GATE}"


def driver_steps(result: dict, folder: str, task: str) -> list[dict]:
    """The job's steps that ran the example's driver on the task: `python3 [-I] <folder>/proofs/prove.py TASK ...`,
    the driver at exactly that path relative to the job's checkout (not one of another checkout, nor a word that only
    names it)."""
    out = []
    for step in result.get("steps") or []:
        try:
            words = shlex.split(step.get("run") or "")
        except ValueError:
            continue
        at = 2 if words[:2] == ["python3", "-I"] else 1
        if words[:1] != ["python3"] or words[at : at + 2] != [f"{folder}/proofs/prove.py", task]:
            continue
        rest = words[at + 2 :]
        work = next((rest[i + 1] for i, w in enumerate(rest[:-1]) if w == "--work"), None)
        out.append({"step": step, "work": work, "trial": [w for w in rest if w.split("=", 1)[0] in TRIAL_FLAGS]})
    return out


def sizes(value) -> list[int]:
    """The lengths of every String and array in a witness's typed value (`{"kind": "string", "units": [...]}`, a list,
    or an object holding either)."""
    if isinstance(value, dict):
        own = [len(value["units"])] if isinstance(value.get("units"), list) else []
        return own + [n for k, v in value.items() if k != "units" for n in sizes(v)]
    if isinstance(value, list):
        return [len(value)] + [n for v in value for n in sizes(v)]
    return []


def replayed_mutant(folder: Path) -> str | None:
    """The hash the newest mutant replay's receipt records for the mutant's own JAR."""
    for receipt in sorted((folder / "receipts/mutant-replay").glob("*/result.json"), reverse=True):
        found: list[str] = []

        def walk(o):
            if isinstance(o, dict):
                if o.get("revision") == "mutant" and o.get("role") == "original" and "sha256" in o:
                    found.append(o["sha256"])
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)

        walk(load(receipt))
        if found:
            return found[0]
    return None


def frozen_claims(root: Path, number: str) -> dict[str, str]:
    """The claim files frozen for the example, each with its hash, from every ledger of a run."""
    out: dict[str, str] = {}
    for ledger in sorted((root / "llm-dlc/decisions").glob("*-claims.json")):
        out.update(((load(ledger) or {}).get(number) or {}).get("files") or {})
    return out


def revisions_of(target: dict, task: dict) -> list[str]:
    if task.get("revision"):
        return [task["revision"]]
    pair = next((p for p in (target.get("history") or {}).get("pairs") or [] if p.get("name") == task.get("pair")), None)
    return [pair["before"], pair["after"]] if pair else []


def check(root: Path, number: str, task_id: str, source=None) -> dict:
    """The acceptance record of one task's answer beside the route."""
    source = source or Source(root)
    checks: list[dict] = []
    limits: list[str] = []

    def said(name: str, status: str, detail: str) -> bool:
        checks.append({"check": name, "status": status, "detail": detail})
        return status == OK

    def done(**more) -> dict:
        refused = [c for c in checks if c["status"] != OK]
        actual = more.get("actual")
        out = {"example": number, "task": task_id, **more, "checks": checks, "limits": limits}
        out["accepted"] = not refused and actual is not None and actual == out.get("claimed")
        if refused:
            out["why"] = f"{refused[0]['check']}: {refused[0]['detail']}"
        return out

    sidecar = next(iter(sorted((root / "examples").glob(f"{number}-*/target.json"))), None)
    target = load(sidecar) if sidecar else None
    if target is None:
        said("job", UNBOUND, f"example {number} has no target.json that reads")
        return done(claimed=None, job=None, actual=None)
    folder = sidecar.parent
    rel = folder.relative_to(root).as_posix()
    task = next((t for t in target.get("tasks") or [] if t.get("id") == task_id), None)
    record = (task or {}).get("besideRoute")
    if not record:
        said("job", UNBOUND, f"{task_id} has no answer beside the route in target.json")
        return done(claimed=None, job=None, actual=None)
    claimed, job_id = record.get("answer"), str(record.get("job"))
    base = {"claimed": claimed, "job": job_id}

    # job
    if "/" in job_id or job_id.startswith("."):
        said("job", FAIL, f"{job_id!r} is not a job's id")
        return done(**base, actual=None)
    result = load(root / "verification/results" / job_id / "result.json")
    if result is None:
        said("job", UNBOUND, f"no result of job {job_id} in this checkout (verification/results)")
        return done(**base, actual=None)
    if result.get("status") != "passed":
        said("job", FAIL, f"job {job_id} ended {result.get('status')}, not passed")
        return done(**base, actual=None)
    job_file = root / "verification/jobs" / f"{job_id}.json"
    job = load(job_file)
    if job is None:
        said("job", UNBOUND, f"job {job_id}'s file is not in this checkout (verification/jobs)")
        return done(**base, actual=None)
    if number not in ((job.get("links") or {}).get("examples") or []):
        said("job", FAIL, f"job {job_id} does not name example {number} (links.examples)")
        return done(**base, actual=None)
    # The result records the job as the runner read it (verification/pipeline.py: the hash of its sorted JSON).
    recorded = (result.get("job") or {}).get("sha256")
    if recorded and recorded != sha256(json.dumps(job, sort_keys=True).encode()):
        said("job", FAIL, f"job {job_id}'s file is not the one its result is of (sha256 {recorded[:12]} recorded)")
        return done(**base, actual=None)
    said("job", OK, f"job {job_id} passed and names example {number}")
    commit = result.get("sourceCommit") or ""
    have_commit = bool(commit) and source.has(commit)
    identity = {"sourceCommit": commit, "libTree": (result.get("jvmcontract") or {}).get("libTree")}

    # step
    steps = [s for s in driver_steps(result, rel, task_id) if s["step"].get("status") == "passed"]
    if not steps:
        said("step", UNBOUND, f"no passed step of job {job_id} ran {rel}/proofs/prove.py {task_id}")
        return done(**base, actual=None, identity=identity)
    chosen = next((s for s in reversed(steps) if not s["trial"]), steps[-1])
    step = chosen["step"]
    if not chosen["work"]:
        said("step", UNBOUND, f"step {step.get('index')} names no --work folder, so its outcome is in no collected file")
        return done(**base, actual=None, identity=identity)
    said("step", OK, f"step {step.get('index')}: {step.get('run')}")
    work = f"{chosen['work'].rstrip('/')}/{task_id}"

    # outcome
    outputs = {o.get("path"): o for o in result.get("outputs") or [] if o.get("change") != "deleted"}

    def collected(path: str, name: str):
        """A collected output's JSON when the file is as the result records it."""
        if path not in outputs:
            said(name, UNBOUND, f"{path} is not among job {job_id}'s outputs")
            return None
        now = file_sha256(root / path)
        if now != outputs[path].get("sha256"):
            said(name, FAIL, f"{path} is {'not in this checkout' if now is None else 'not the file the job wrote (sha256 ' + now[:12] + ', recorded ' + str(outputs[path].get('sha256'))[:12] + ')'}")
            return None
        data = load(root / path)
        if data is None:
            said(name, FAIL, f"{path} is not JSON")
        return data

    outcome = collected(f"{work}/outcome.json", "outcome")
    if outcome is None:
        return done(**base, actual=None, identity=identity)
    if isinstance(outcome, list):
        if len(outcome) != 1:
            said("outcome", FAIL, f"{work}/outcome.json holds {len(outcome)} outcomes, not one")
            return done(**base, actual=None, identity=identity)
        outcome = outcome[0]
    said("outcome", OK, f"{work}/outcome.json, sha256 {outputs[f'{work}/outcome.json']['sha256'][:12]}, as the job wrote it")
    # An equivalence outcome carries the checked property of the pair inside it.
    inner = outcome.get("pair") if isinstance(outcome.get("pair"), dict) else outcome
    stated, search = inner.get("stated") or {}, inner.get("search") or outcome.get("search") or {}

    # conclusion
    verdicts = {outcome.get("verdict"), inner.get("verdict")}
    actual = ANSWER.get(outcome.get("verdict"), "unknown") if len(verdicts) == 1 else "unknown"
    base["actual"] = actual
    if actual == claimed:
        said("conclusion", OK, f"the outcome's verdict is {outcome.get('verdict')}: {actual}")
    else:
        said("conclusion", FAIL, f"the outcome's verdict is {outcome.get('verdict')} ({actual}), and the answer recorded is {claimed}")

    # claim
    claim_rel = f"{rel}/{task.get('claim')}"
    claim_bytes = None
    try:
        claim_bytes = (root / claim_rel).read_bytes()
        claim = json.loads(claim_bytes)
    except (OSError, ValueError):
        claim = None
    if claim is None:
        said("claim", UNBOUND, f"{claim_rel} does not read")
        return done(**base, identity=identity)
    digest, frozen = sha256(claim_bytes), frozen_claims(root, number).get(claim_rel)
    ran = source(commit, claim_rel) if have_commit else None
    if frozen is not None and frozen != digest:
        said("claim", FAIL, f"{claim_rel} is not the claim frozen (sha256 {digest[:12]}, frozen {frozen[:12]})")
    elif have_commit and (ran is None or sha256(ran) != digest):
        said("claim", FAIL, f"{claim_rel} is not the file the job ran at {commit[:12]}")
    elif frozen is None and not have_commit:
        said("claim", UNBOUND, f"{claim_rel} is in no ledger of frozen claims, and the job's source commit {commit[:12] or '(none)'} is not in this checkout")
    else:
        said("claim", OK, f"{claim_rel}, sha256 {digest[:12]}: " + " and ".join(
            ([f"as the job ran it at {commit[:12]}"] if have_commit else []) + (["as frozen"] if frozen else [])))
    if not have_commit:
        limits.append(f"the job's source commit {commit[:12] or '(none)'} is not in this checkout: the task, the pinned artifacts "
                      f"and the adapter sources are not compared with what the job ran")

    # task, and what it pins
    if have_commit:
        then = json.loads(source(commit, f"{rel}/target.json") or b"null")
        then_task = next((t for t in (then or {}).get("tasks") or [] if t.get("id") == task_id), None)
        moved = [k for k in FROZEN if (then_task or {}).get(k) != task.get(k)]
        if then_task is None or moved:
            said("task", FAIL, f"the task is not what it was at {commit[:12]}: " + (", ".join(moved) if then_task else "it was not there"))
        else:
            pins = lambda t: ((t.get("preparation") or {}).get("artifacts"), (t.get("history") or {}).get("revisions"))  # noqa: E731
            # The sources the job compiled are the ones listed at its commit; each must be here as it was. One listed
            # since (an entry for another claim) is not one it compiled, so it changes nothing the answer rests on.
            adapters = ((then or {}).get("preparation") or {}).get("adapters") or []
            added = [a for a in (target.get("preparation") or {}).get("adapters") or [] if a not in adapters]
            changed = [a for a in adapters if source(commit, f"{rel}/{a}") != ((root / rel / a).read_bytes() if (root / rel / a).is_file() else None)]
            if pins(then) != pins(target):
                said("task", FAIL, f"target.json's pinned artifacts or revisions are not what they were at {commit[:12]}")
            elif changed:
                said("task", FAIL, f"the adapter is not the one the job compiled at {commit[:12]}: {', '.join(changed)}")
            else:
                said("task", OK, f"the task, the pinned artifacts and {len(adapters)} adapter source(s) are as at {commit[:12]}"
                     + (f" ({len(added)} listed since, which the job did not compile: {', '.join(added)})" if added else ""))
        driver = source(commit, f"{rel}/proofs/prove.py")
        identity["driver"] = {"path": f"{rel}/proofs/prove.py", "sha256": sha256(driver) if driver else None, "at": commit}

    # expressions
    wrong = [name for name, has, want in (("assume", inner.get("assume"), claim.get("assume")),) if (has or None) != (want or None)]
    if task.get("kind") == "prove":
        if (inner.get("assert") or None) != (claim.get("assert") or None):
            wrong.append("assert")
        if list(inner.get("throws") or []) != list(claim.get("throws") or []):
            wrong.append("throws")
    if wrong:
        said("expressions", FAIL, f"the outcome's {' and '.join(wrong)} {'is' if len(wrong) == 1 else 'are'} not the claim file's")
    elif task.get("kind") == "equivalence":
        allowed = task.get("allowedChange")
        pair_java = f"{work}/work/pair/RegressionPair.java"
        text = (root / pair_java).read_text() if pair_java in outputs and file_sha256(root / pair_java) == outputs[pair_java].get("sha256") else None
        ran_with = re.search(r"meant to affect \(`([^`]*)`", outcome.get("output") or "")
        if not allowed and text is not None and "meantToChange" in text:
            said("expressions", FAIL, f"the generated pair ({pair_java}) skips the inputs of an allowed change, and the task allows none")
        elif not allowed and ran_with:
            said("expressions", FAIL, f"the outcome says it ran with an allowed change (`{ran_with.group(1)}`), and the task allows none")
        elif not allowed:
            said("expressions", OK, "the assumption is the claim file's, and the task allows no change, nor did the run")
        elif text is not None and allowed not in text:
            said("expressions", FAIL, f"the allowed change in the generated pair ({pair_java}) is not the task's")
        elif text is not None:
            said("expressions", OK, "the assumption is the claim file's, and the allowed change in the generated pair is the task's")
        # Without the generated pair among the outputs, the outcome's own account of what it ran says it.
        elif f"meant to affect (`{allowed}`" in (outcome.get("output") or ""):
            said("expressions", OK, "the assumption is the claim file's, and the allowed change the outcome says it ran is the task's")
        elif "meant to affect (`" in (outcome.get("output") or ""):
            said("expressions", FAIL, "the allowed change the outcome says it ran is not the task's")
        else:
            said("expressions", UNBOUND, f"neither the generated pair ({pair_java}, not a collected output as the job wrote it) nor the outcome's text says which allowed change was run")
    else:
        said("expressions", OK, "the assumption, the assertion and the throws clauses are the claim file's")

    # entry
    # Whole names: the invocation's entry, and an adapter entry a claim's assumption names as such (286's and 287's
    # tasks have no invocation entry). A method an assumption mentions otherwise is not the entry.
    named = set(ENTRY.findall((task.get("invocation") or {}).get("entry") or ""))
    named.update(m for a in claim.get("assumptions") or [] for m in ADAPTER_ENTRY.findall(a.get("text", "")))
    entry = outcome.get("target") or ""
    if entry and entry in named:
        said("entry", OK, f"the outcome is about {entry}, the entry the task names")
    elif entry and entry == (task.get("target") or "").split("(", 1)[0]:
        said("entry", OK, f"the outcome is about {entry}, the task's own target")
    else:
        said("entry", FAIL if entry else UNBOUND, f"the outcome is about {entry or 'no target'}, which is neither the task's target nor the entry its invocation or the claim's assumptions name")

    # domain
    want = (claim.get("bounds") or {}).get("maxArrayLength")
    ran_at = search.get("max_array_length")
    bound = {"claim": want, "ran": ran_at, "unwind": search.get("unwind"), "trialFlags": chosen["trial"]}
    witness = (outcome.get("counterexample") or inner.get("counterexample") or {})
    longest = max(sizes([i.get("value") for i in witness.get("inputs") or []]), default=0)
    nullable = sorted(p.get("name") for p in ((stated.get("domain") or {}).get("parameters") or []) if p.get("null"))
    parameters = {a.get("name") for a in ((witness.get("call") or {}).get("arguments") or [])} or None
    null_where_not = [i.get("name") for i in witness.get("inputs") or [] if i.get("value") is None
                      and (parameters is None or i.get("name") in parameters) and i.get("name") not in (claim.get("nullable") or [])]
    if nullable != sorted(claim.get("nullable") or []):
        said("domain", FAIL, f"the parameters that may be null ({', '.join(nullable) or 'none'}) are not the claim's ({', '.join(sorted(claim.get('nullable') or [])) or 'none'})")
    elif actual == "refuted" and null_where_not:
        said("domain", FAIL, f"the witness's {', '.join(null_where_not)} is null, which the claim does not let it be (nullable: {', '.join(sorted(claim.get('nullable') or [])) or 'none'}): it lies outside the claim's domain")
    elif want is None and not chosen["trial"]:
        said("domain", OK, "the claim states no bound on lengths, and the step overrides none")
    elif want is None or ran_at is None:
        said("domain", UNBOUND, f"the claim's bound ({want}) or the outcome's ({ran_at}) is not recorded" + (f", and the step overrides one ({' '.join(chosen['trial'])})" if chosen["trial"] else ""))
    elif actual == "established" and ran_at < want:
        said("domain", FAIL, f"a proof at bound {ran_at} establishes nothing about the claim's bound {want}: a trial run")
    elif actual == "refuted" and longest > want:
        said("domain", FAIL, f"the witness holds a value of length {longest}, outside the claim's bound {want}")
    elif ran_at != want:
        said("domain", OK, f"bound {ran_at} where the claim's is {want}: " + ("the witness lies in the claim's domain" if actual == "refuted" else "the claim's domain is within it"))
    else:
        said("domain", OK, f"the claim's bound, {want}" + (f"; the witness's longest value is {longest}" if actual == "refuted" else ""))

    # mode
    off = [f"{k} {has} where the task says {want_}" for k, has, want_ in (("engine", search.get("engine"), task.get("engine")), ("gap mode", search.get("gap_mode"), task.get("gaps")))
           if want_ not in (None, "auto") and has != want_]
    said("mode", FAIL if off else OK, "; ".join(off) or f"engine {search.get('engine')}, gaps {search.get('gap_mode')}, as the task says")

    if actual == "established":
        bounds = stated.get("bounds") or {}
        if outcome.get("problem") or inner.get("problem") or bounds.get("complete") is not True:
            said("complete", FAIL, f"the outcome does not say the bounds are complete (problem: {outcome.get('problem') or inner.get('problem')}, complete: {bounds.get('complete')})")
        else:
            said("complete", OK, f"no problem, and the unwinding ({bounds.get('unwind')}) is complete")
        vacuity = stated.get("vacuity") or {}
        change = task.get("allowedChange")
        if vacuity.get("status") == "non-vacuous" and vacuity.get("witness") and change is not None and vacuity.get("outside") != change:
            # An input inside the allowed change is one the versions need not agree on: the pair's `agree` returns
            # true on it without calling either. A witness there shows nothing compared.
            if vacuity.get("outside") is None:
                said("non-vacuous", UNBOUND, f"the outcome does not say whether its witness, {vacuity.get('witness')}, lies outside the allowed change, where the versions are compared: one inside it reaches no comparison (an outcome from before the checker said so)")
            else:
                said("non-vacuous", FAIL, f"the witness is said to lie outside `{vacuity.get('outside')}`, which is not the task's allowed change")
        elif vacuity.get("status") == "non-vacuous" and vacuity.get("witness"):
            said("non-vacuous", OK, f"{vacuity.get('basis')}: {vacuity.get('witness')}" + (", outside the allowed change" if change is not None else ""))
        else:
            said("non-vacuous", FAIL if vacuity.get("status") else UNBOUND, f"the outcome names no input that reaches the property (vacuity: {vacuity.get('status') or 'not recorded'})")
    elif actual == "refuted":
        replay = outcome.get("replay") or inner.get("replay") or {}
        if not witness:
            said("replay", FAIL, "the outcome has no witness")
        elif replay.get("by") == "jvm" and replay.get("reproduced") is True:
            assumed = inner.get("assume")
            harness = f"{work}/work/harness/PropertyHarness.java"
            source_ok = harness in outputs and file_sha256(root / harness) == outputs[harness].get("sha256")
            if not assumed:
                said("replay", OK, f"reproduced on a JVM: {witness.get('input')}")
            elif source_ok and gates_on(read_text(root / harness), assumed):
                said("replay", OK, f"reproduced on a JVM: {witness.get('input')}, by the harness the job collected ({harness}), "
                     f"which returns before the call where the assumption does not hold")
            else:
                said("replay", UNBOUND, f"reproduced on a JVM, but no record says the claim's assumption held on {witness.get('input')}: "
                     + (f"the harness the JVM ran ({harness}) does not return first where `{assumed}` does not hold" if source_ok
                        else f"the job collected no harness source ({harness}) as it wrote it"))
        else:
            said("replay", FAIL, f"the witness was not reproduced on a JVM (replay: {json.dumps(replay) if replay else 'not recorded'})")

    # the driver's own record, where it wrote one
    evidence = collected(f"{work}/{EVIDENCE}", "artifacts") if f"{work}/{EVIDENCE}" in outputs else None
    constructed = [r for r in revisions_of(target, task) if "mutant" in ((target.get("history") or {}).get("revisions") or {}).get(r, {})]

    # mutant
    if constructed:
        replayed = replayed_mutant(folder)
        log = step.get("log") or {}
        log_file = root / "verification/results" / job_id / (log.get("path") or "")
        built = (evidence or {}).get("mutant", {}).get("sha256") if evidence else None
        if built is None and log.get("path") and file_sha256(log_file) == log.get("sha256"):
            lines = [m.group(1) for line in log_file.read_text(errors="replace").splitlines() if line.startswith("mutant:")
                     for m in [re.search(r"sha256 ([0-9a-f]{64})", line)] if m]
            built = lines[-1] if lines else None
        if built is None:
            said("mutant", UNBOUND, "neither the driver's record nor the step's log says which JAR the mutant was: its hash is in no record")
        elif replayed is None:
            said("mutant", UNBOUND, "no mutant replay's receipt records the mutant's JAR to compare with")
        elif built != replayed:
            said("mutant", FAIL, f"the mutant's JAR (sha256 {built[:12]}) is not the one the mutant replay ran ({replayed[:12]})")
        else:
            said("mutant", OK, f"the mutant's JAR, sha256 {built[:12]}, is the one the mutant replay ran")

    # artifacts
    if f"{work}/{EVIDENCE}" in outputs:
        if evidence is not None:
            pinned = {(a["revision"], a["url"].rsplit("/", 1)[1]): a["sha256"] for a in (target.get("preparation") or {}).get("artifacts") or []}
            problems = []
            if evidence.get("schema") != EVIDENCE_SCHEMA or evidence.get("task") != task_id:
                problems.append(f"it is not this task's record ({evidence.get('schema')}, task {evidence.get('task')})")
            if (evidence.get("claim") or {}).get("sha256") != digest:
                problems.append("the claim it hashed is not the claim file")
            if (evidence.get("bound") or {}).get("trial") and actual == "established":
                problems.append("it marks the run a trial at a bound that is not the claim's")
            # A constructed mutant's class path is its base's, its own JAR built: the rest are pinned under the base.
            revisions = (target.get("history") or {}).get("revisions") or {}
            base_of = {r: ((v or {}).get("mutant") or {}).get("base", r) for r, v in revisions.items()}
            seen = set()
            for a in evidence.get("artifacts") or []:
                key = (base_of.get(a.get("revision"), a.get("revision")), a.get("name"))
                seen.add(a.get("revision"))
                if a.get("constructed"):
                    continue  # the mutant's own JAR: the `mutant` check
                if pinned.get(key) != a.get("sha256"):
                    problems.append(f"{a.get('name')} of {a.get('revision')} is not the JAR target.json pins")
            missing = [r for r in revisions_of(target, task) if r not in seen]
            if missing:
                problems.append(f"it records no JAR for {', '.join(missing)}")
            ran_driver, at_commit = (evidence.get("driver") or {}).get("sha256"), (identity.get("driver") or {}).get("sha256")
            if have_commit and ran_driver != at_commit:
                problems.append(f"the driver it recorded (sha256 {str(ran_driver)[:12]}) is not {rel}/proofs/prove.py at the source commit ({str(at_commit)[:12]})")
            for path, was in ((evidence.get("adapter") or {}).get("sources") or {}).items():
                if file_sha256(root / path) != was:
                    problems.append(f"the adapter source {path} is not the one it compiled")
            if problems:
                said("artifacts", FAIL, f"{work}/{EVIDENCE}: " + "; ".join(problems))
            else:
                said("artifacts", OK, f"{len(evidence.get('artifacts') or [])} JAR(s), the adapter sources and the claim the driver recorded are the ones pinned")
                identity["jvmcontract"] = evidence.get("jvmcontract")
    else:
        limits.append("the driver recorded no artifact identities beside the outcome: that the JARs are the pinned ones rests on the "
                      "driver's own check of their hashes (its code at the job's source commit), and the compiled adapter and the "
                      "verifier's binary are identified only by that commit and the lib tree")

    models = stated.get("models") or {}
    identity.update(checker=(stated.get("checker") or {}).get("name"), solver=(stated.get("checker") or {}).get("solver"),
                    models=models.get("digest"), jdk=models.get("jdk"))
    rests = [a.get("text") for a in stated.get("assumptions") or [] if a.get("basis") != "stated"]
    return done(**base, bound=bound, identity=identity, restsOn=rests)


def tasks_beside(root: Path, number: str) -> list[str]:
    sidecar = next(iter(sorted((root / "examples").glob(f"{number}-*/target.json"))), None)
    target = load(sidecar) if sidecar else None
    return [t["id"] for t in (target or {}).get("tasks") or [] if t.get("besideRoute")]


def record(work: Path, *, example: str, task: str, claim_file: Path, bound: dict, artifacts: list[dict], adapter_sources: list[Path],
           adapter_classes: list[Path], jvmcontract: str, driver: Path, root: Path = REPO, mutant: dict | None = None) -> Path:
    """What a driver writes beside outcome.json (evidence.json), so that the acceptance check has the identities in a
    record: the claim file's hash, the bound and whether it is the claim's (`bound.trial`), each JAR on the class
    path with its revision and hash (`constructed` for a mutant's own), the adapter's sources and compiled classes,
    the verifier's binary and the driver itself. Paths inside the repository are written relative to it."""
    def name(path: Path) -> str:
        try:
            return Path(path).resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            return Path(path).name

    def tree(folder: Path) -> str:
        files = sorted(p for p in Path(folder).rglob("*") if p.is_file())
        return sha256("".join(f"{p.relative_to(folder).as_posix()} {sha256(p.read_bytes())}\n" for p in files).encode())

    binary = Path(jvmcontract)
    out = {
        "schema": EVIDENCE_SCHEMA, "example": example, "task": task,
        "claim": {"file": name(claim_file), "sha256": sha256(Path(claim_file).read_bytes())},
        "bound": bound,
        "artifacts": artifacts,
        "adapter": {"sources": {name(s): sha256(Path(s).read_bytes()) for s in adapter_sources},
                    "classes": [{"folder": Path(c).name, "sha256": tree(c)} for c in adapter_classes]},
        "jvmcontract": {"path": name(binary), "sha256": file_sha256(binary)},
        "driver": {"path": name(driver), "sha256": sha256(Path(driver).read_bytes())},
    }
    if mutant:
        out["mutant"] = mutant
    path = Path(work) / EVIDENCE
    path.write_text(json.dumps(out, indent=1) + "\n")
    return path


def main(argv: list[str] | None = None, root: Path = REPO) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("example", help="the example's number")
    p.add_argument("tasks", nargs="*", help="its tasks to check; without any, every task with an answer beside the route")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    source = Source(root)
    names = args.tasks or tasks_beside(root, args.example)
    records = [check(root, args.example, t, source) for t in names]
    if args.json:
        print(json.dumps(records, indent=1, ensure_ascii=False))
    else:
        if not records:
            print(f"example {args.example}: no task has an answer beside the route")
        for r in records:
            if r["accepted"]:
                print(f"✓ {r['example']} {r['task']}: {r['claimed']}, accepted (job {r['job']}; {len(r['checks'])} checks)")
            else:
                print(f"✗ {r['example']} {r['task']}: {r.get('claimed')} is not accepted. {r.get('why', 'the evidence gives ' + str(r.get('actual')))}")
        for limit in dict.fromkeys(limit for r in records for limit in r["limits"]):
            print(f"limit: {limit}")
    return 0 if records and all(r["accepted"] for r in records) else 1


if __name__ == "__main__":
    sys.exit(main())

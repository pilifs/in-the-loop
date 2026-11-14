"""Attempt ingestion (W2 of llm-dlc/loops/example-targets-workflow.md): one attempt's raw execution records, bound to
the prepared artifacts, published as one format-2 receipt. workflow.ingest() is this module's publish().

    publish(plan, prepared, records, out) -> Receipt | Unsupported

The receipt goes to out/<attempt>/result.json, beside it plan.json (workflow.plan_record(): what readiness tells a
current receipt from a stale one by) and the evidence under records/, listed with their sha256s in the bundle. Earlier
attempts are never touched. Nothing is published before build.py's check_result() passes: the flat view against
result.schema.json, the round trip through format 2, the stored document against stored-result.schema.json, and the
bundle against the files.

The claim is bound before anything is read as a result: the task's source-level claim (TaskPlan.claim), the sidecar's
sha256, each revision's identity, every classpath entry of each revision in order with its role and sha256, the JDKs,
and the claim, control, adapter and patch files by sha256. Its id is build.py's (canonical digest, 16 hex digits), so
the same task on the same inputs keeps its id across attempts, a vulnerable and a fixed task sharing a claim file get
different ids (their artifacts differ), and another engine or timeout is another attempt at the same claim.

A revision's identity is its full commit SHA. A fixture revision has no commit: its identity is the git tree id of
its source directory, which `git rev-parse <commit>:<path>` reproduces from any commit holding the folder unchanged.
A constructed mutant's is its base's, its patch among the files.

What an attempt shows stays apart: how it ran (execution), what it concluded (status, per obligation), whether that is
what the task expects (expectation), what it is about (scope) and whether its concrete side replayed (replay).
  - A replay task decides no claim: its status is always None. Its controls complete only when every revision ran on
    every JDK its artifact entry names, exited 0 with structured observations, on the prepared bytes, and the case's
    oracle read every one. Its expectation is `yes` only then, and only when each revision's outcome is the one its
    pair's kind says (an exact fix's before violates the oracle and its after holds, a mutation's base holds and its
    mutant violates, and so on) on every JDK alike.
  - A proof task's conclusion is the verifier's, read from its `--json` outcome (ExecutionRecord.observations: the
    list `prove --json` prints, or the one outcome of `equivalence --json`), with build.py's rules: an exit code the
    outcome contradicts, a missing or unreadable outcome, or a violation without a witness is invalid output, never a
    violation; a refusal is unresolved; a kill or timeout has no verdict.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from targets import interfaces, workflow
from targets.interfaces import WORKFLOW, Receipt, Unsupported

EXECUTION = "execution.json"  # the raw records, with what the oracle read in each
SUMMARY = "summary.txt"  # a replay's console output: one line per record
VERIFIER_OUTPUT = "verifier-output.txt"  # the verifier's console output, from its outcome
ORACLE_TIMEOUT = 60
# What each kind of pair says the controls of its two revisions show: `violates` the oracle, or `holds`.
SIDES = {"exact-fix": ("violates", "holds"), "release": ("violates", "holds"), "introduction": ("holds", "violates"),
         "mutation": ("holds", "violates"), "positive": ("holds", "holds")}
PRIORITY = ("killed", "timed-out", "tool-error", "invalid-output")
# Reads each record's observation lines with the oracle's check(lines), in a separate interpreter (-I: the oracle sees
# only the standard library). A ValueError from check() is the oracle refusing an incomplete replay.
ORACLE_RUNNER = r"""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("target_oracle", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
out = []
for lines in json.load(sys.stdin):
    try:
        out.append({"problems": [[p[0], str(p[1])] for p in module.check(lines)]})
    except Exception as e:
        out.append({"error": f"{type(e).__name__}: {e}"})
print(json.dumps(out))
"""


class Refused(Exception):
    """Why the records can't be bound to the claim at all: nothing is published."""

    def __init__(self, reason, stage="bind", diagnostic=None):
        super().__init__(reason)
        self.reason, self.stage, self.diagnostic = reason, stage, diagnostic


def git_tree_id(directory):
    """The git tree id of `directory`'s files, as `git rev-parse <commit>:<path>` gives it for a commit holding them
    unchanged (blobs 100644 or 100755, links 120000, empty directories and __pycache__ left out). None when empty."""
    entries = []
    for p in Path(directory).iterdir():
        if p.name == "__pycache__":
            continue
        if p.is_symlink():
            data, mode = os.readlink(p).encode(), b"120000"
        elif p.is_dir():
            sub = git_tree_id(p)
            if sub is not None:
                entries.append((p.name + "/", b"40000 " + p.name.encode() + b"\0" + bytes.fromhex(sub)))
            continue
        else:
            data = p.read_bytes()
            mode = b"100755" if p.stat().st_mode & stat.S_IXUSR else b"100644"
        blob = hashlib.sha1(b"blob %d\0" % len(data) + data).digest()
        entries.append((p.name, mode + b" " + p.name.encode() + b"\0" + blob))
    if not entries:
        return None
    body = b"".join(e for _, e in sorted(entries, key=lambda x: x[0].encode()))
    return hashlib.sha1(b"tree %d\0" % len(body) + body).hexdigest()


def sidecar_of(plan):
    path = Path(plan.folder) / "target.json"
    try:
        return path, json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise Refused(f"target.json can't be read: {e}") from None


def task_of(target, plan):
    return next((t for t in target.get("tasks", []) if t.get("id") == plan.task), None) or {}


def revision_identity(plan, entry):
    """A revision's identity in claim.target.revisions: its commit, or its fixture sources' git tree id, or for a
    mutant its base's."""
    source = entry.get("mutant", {}).get("base") or entry
    if source.get("commit"):
        return source["commit"]
    if source.get("fixture"):
        directory = Path(plan.folder) / source["fixture"]
        root = Path(plan.folder).resolve()
        if not directory.is_dir() or root not in directory.resolve().parents:
            raise Refused(f"revision {entry['revision']}'s fixture {source['fixture']} is not a directory in the folder")
        found = git_tree_id(directory)
        if found:
            return found
    raise Refused(f"revision {entry['revision']} has no commit and no fixture sources to identify it by")


def bound_revisions(plan, prepared):
    """{revision: (artifact entry, PreparedTarget, identity)} for each revision the plan prepares, or Refused: a
    revision not prepared, not artifacts-ready (a preparation failure stays one), of another example or revision, of
    another commit or fixture than the plan's, or whose classpath names a file it didn't prepare."""
    if not isinstance(prepared, dict):
        raise Refused("the prepared targets are not a mapping of revision names")
    entries = {e.get("revision"): e for e in plan.artifacts}
    out = {}
    for revision in plan.revisions:
        p = prepared.get(revision)
        entry = entries.get(revision)
        if entry is None:
            raise Refused(f"the plan has no artifact source for revision {revision}")
        if not isinstance(p, interfaces.PreparedTarget):
            raise Refused(f"revision {revision} was not prepared: nothing to bind its records to")
        if p.stage != "artifacts-ready":
            raise Refused(f"revision {revision} is {p.stage}, not artifacts-ready: a preparation failure, not an attempt",
                          stage="prepare", diagnostic=p.diagnostic)
        if (p.example, p.revision) != (plan.example, revision):
            raise Refused(f"the preparation given for revision {revision} is example {p.example}'s {p.revision}")
        expected = entry.get("commit") or (f"fixture:{entry['fixture']}" if entry.get("fixture") else None)
        if expected and p.commit != expected:
            raise Refused(f"revision {revision} was prepared from {p.commit}, and the plan names {expected}")
        paths = {a.path for a in p.artifacts}
        stray = [c for c in p.classpath if c not in paths]
        if stray or not p.classpath:
            raise Refused(f"revision {revision}'s classpath " + (f"names {', '.join(stray)}, which it didn't prepare"
                                                                  if stray else "is empty"))
        if not any(a.role == "original" for a in p.artifacts if a.path in p.classpath):
            raise Refused(f"revision {revision}'s classpath has no original artifact")
        out[revision] = (entry, p, revision_identity(plan, entry))
    return out


def oracle_control(plan, target, task):
    """The oracle file the replay is read with, hashed, and checked against the hash the plan froze, if it froze one."""
    frozen = {c.get("path"): c.get("sha256") for c in (plan.claim or {}).get("controls") or [] if c.get("kind") == "oracle"}
    names = list(frozen) or [c["path"] for c in target.get("controls", []) if c.get("kind") == "oracle"
                             and (not c.get("revision") or c["revision"] in plan.revisions)]
    if len(names) != 1:
        raise Refused(f"the task has {len(names)} oracle controls, and a replay is read by exactly one", stage="oracle")
    try:
        found = workflow.hashed(plan.folder, names[0])
    except workflow.ClaimError as e:
        raise Refused(f"the oracle can't be read: {e}", stage="oracle") from None
    if frozen.get(names[0]) not in (None, found["sha256"]):
        raise Refused(f"the oracle {names[0]} changed since the task was planned: replan before ingesting", stage="oracle")
    return found


def claim_files(plan, oracle):
    """The claim, control, model, adapter and patch files the claim rests on, by path: every {path, sha256} the
    source-level claim froze, the adapters' sources, each mutant's patch, and the oracle."""
    files = {}

    def walk(value):
        if isinstance(value, dict):
            if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
                files[value["path"]] = value["sha256"]
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    claim = dict(plan.claim or {})
    if claim.get("file") and claim.get("sha256"):
        files[claim["file"]] = claim["sha256"]
    walk(claim)
    for entry in plan.artifacts:
        walk(entry.get("mutant", {}).get("patch"))
        for name in entry.get("adapters", []):
            try:
                files[name] = workflow.hashed(plan.folder, name)["sha256"]
            except workflow.ClaimError as e:
                raise Refused(f"adapter source {name}: {e}") from None
    if oracle:
        files[oracle["path"]] = oracle["sha256"]
    return {k: files[k] for k in sorted(files) if len(files[k] or "") == 64}


def jdk_feature(version):
    """A `java -version` first line's feature release: 'openjdk version "25.0.5" ...' is 25, "1.8.0_512" 8."""
    found = re.search(r'version "(?:1\.)?(\d+)', version or "")
    return found.group(1) if found else None


def jdks_of(bound, records):
    started = [r.identities.get("jdk") for r in records if r.status != "not-started"]
    built = [((p.toolchain or {}).get("jdk") or {}).get("version") for _, p, _ in bound.values()]
    jdks = sorted({j for j in started + built if isinstance(j, str) and j})
    if not jdks:
        raise Refused("no record or preparation names a JDK: the claim can't be bound to one")
    return jdks


def claim_record(plan, target_path, bound, records, oracle):
    """The executed claim: the source-level claim bound to the prepared artifacts (the module's docstring)."""
    import build
    dependencies = [{"revision": revision, "position": i, "role": a.role, "sha256": a.sha256,
                     **({"coordinates": a.coordinates} if a.coordinates else {})}
                    for revision, (_, p, _) in bound.items()
                    for i, a in enumerate(next(x for x in p.artifacts if x.path == c) for c in p.classpath)]
    trees = {revision: build.tree_digest(plan.folder, [entry["fixture"]]) if entry.get("fixture") else None
             for revision, (entry, _, _) in bound.items()}
    names = list(plan.revisions)
    scope = {}
    if plan.kind in workflow.PROOF_KINDS:
        scope["maxArrayLength"] = (plan.claim.get("bounds") or {}).get("maxArrayLength")
    if plan.kind in ("compare", "equivalence"):
        scope["intendedInputs"] = plan.claim.get("allowedChange")
    body = {"format": build.CLAIM_FORMAT, "example": plan.example,
            "statement": {"approach": "target", "task": plan.task, "kind": plan.kind, "relation": plan.relation,
                          "target": plan.target, "revisions": names, "expected": plan.expected, "gaps": plan.gaps,
                          "claim": json.loads(json.dumps(plan.claim))},
            "scope": scope,
            "inputs": {"patch": None, "before": trees[names[0]] if len(names) > 1 else None, "after": trees[names[-1]],
                       "dependencies": "pinned in target.dependencies"},
            "target": {"task": plan.task, "sidecar": workflow.file_sha256(target_path),
                       "revisions": {revision: identity for revision, (_, _, identity) in bound.items()},
                       "dependencies": dependencies, "jdks": jdks_of(bound, records),
                       "files": claim_files(plan, oracle)}}
    return {"id": build.canonical_digest(body)[:16], **body}


def record_problem(record, bound):
    """Why a record shows nothing about its revision, or None: how its process ended, missing or unreadable
    observations, or bytes other than the ones prepared."""
    feature = jdk_feature(record.identities.get("jdk"))
    where = f"revision {record.revision}" + (f" on JDK {feature}" if feature else "")
    if record.status == "killed":
        return "killed", f"{where}: the JVM was killed" + (f" (exit code {record.exitCode})" if record.exitCode else "")
    if record.status == "timed-out":
        return "timed-out", f"{where}: the JVM did not finish in time"
    if record.status != "exited":
        return "tool-error", f"{where}: the JVM did not start ({record.status})"
    if record.exitCode != 0:
        return "tool-error", f"{where}: the driver exited with code {record.exitCode}"
    if record.observations is None:
        return "invalid-output", f"{where}: the driver's output is missing or malformed"
    prepared = {a.path: a.sha256 for a in bound[record.revision][1].artifacts}
    ran = record.identities.get("classpath") or []
    other = [c.get("path") for c in ran if isinstance(c, dict) and prepared.get(c.get("path")) != c.get("sha256")]
    if other:
        return "invalid-output", f"{where}: ran on {', '.join(map(str, other))}, not the prepared bytes"
    return None


def read_with_oracle(plan, oracle, records):
    """What the oracle's check() says of each record's observations, in order: {"problems": [[input, why]]} or
    {"error": why} (an incomplete replay, or an oracle that failed)."""
    lines = [[json.dumps(o, ensure_ascii=False) for o in r.observations] for r in records]
    if not lines:
        return []
    try:
        proc = subprocess.run([sys.executable, "-I", "-c", ORACLE_RUNNER, str(Path(plan.folder) / oracle["path"])],
                              input=json.dumps(lines), capture_output=True, text=True, timeout=ORACLE_TIMEOUT)
        read = json.loads(proc.stdout) if proc.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError) as e:
        read, proc = None, e
    if not isinstance(read, list) or len(read) != len(lines):
        why = getattr(proc, "stderr", None) or str(proc)
        return [{"error": f"the oracle {oracle['path']} could not be run: {(why or '').strip()[-300:]}"} for _ in lines]
    return read


def expected_sides(target, task, revisions):
    """What each revision's controls should show, `violates` or `holds`, from the kind of the pair the task names,
    or for one revision from every pair it appears in (None when they disagree or none does)."""
    pairs = (target.get("history") or {}).get("pairs") or []
    if task.get("pair"):
        pair = next((p for p in pairs if p.get("name") == task["pair"]), {})
        sides = SIDES.get(pair.get("kind"))
        return dict(zip(revisions, sides)) if sides else {}
    said = {SIDES[p["kind"]][i] for p in pairs if p.get("kind") in SIDES
            for i, side in enumerate(("before", "after")) if p.get(side) == revisions[0]}
    return {revisions[0]: said.pop()} if len(said) == 1 else {}


def replay_outcome(plan, target, bound, records, oracle):
    """The flat fields of a replay attempt: execution, expectation, the label, counterexamples and the replay status,
    and each record's entry for records/execution.json."""
    import build
    task = task_of(target, plan)
    problems, entries = [], []
    usable = []
    for r in records:
        if r.kind != "jvm-control" or r.revision not in bound:
            problems.append(("invalid-output", f"a {r.kind} record of revision {r.revision} is not this replay's"))
            entries.append({**r.as_dict(), "read": "not this replay's"})
            continue
        problem = record_problem(r, bound)
        if problem:
            problems.append(problem)
            entries.append({**r.as_dict(), "read": problem[1]})
        else:
            usable.append(r)
            entries.append(None)
    read = read_with_oracle(plan, oracle, usable)
    outcomes = {}  # revision -> {feature: (violates|holds, problems)}
    for r, verdict in zip(usable, read):
        i = next(i for i, e in enumerate(entries) if e is None)
        entries[i] = {**r.as_dict(), "oracle": verdict}
        feature = jdk_feature(r.identities.get("jdk")) or r.identities.get("jdk") or "?"
        if "error" in verdict:
            problems.append(("invalid-output", f"revision {r.revision} on JDK {feature}: {verdict['error']}"))
            continue
        outcomes.setdefault(r.revision, {})[feature] = ("violates" if verdict["problems"] else "holds", verdict["problems"])
    for revision, (entry, _, _) in bound.items():
        wanted = [str(j) for j in entry.get("jdks") or []]
        got = outcomes.get(revision, {})
        missing = [j for j in wanted if j not in got] if wanted else ([] if got else ["any"])
        if missing:
            problems.append(("invalid-output", f"revision {revision} has no complete control on JDK {', '.join(missing)}: "
                                               "a one-sided or incomplete replay is not reproduced"))
    sides = expected_sides(target, task, list(plan.revisions))
    shown = {rev: {o for o, _ in by_jdk.values()} for rev, by_jdk in outcomes.items()}
    words = [f"{rev} " + ("/".join(sorted(s)) + " (the JDKs disagree)" if len(s) > 1 else next(iter(s)))
             + (" the oracle at " + ", ".join(sorted({str(p[0]) for _, ps in outcomes[rev].values() for p in ps}))
                if any(ps for _, ps in outcomes[rev].values()) else " the oracle")
             for rev, s in shown.items()]
    if problems:
        status = next(s for s in PRIORITY if any(p[0] == s for p in problems))
        first = next(p for p in problems if p[0] == status)
        culprit = next((r for r in records if r.revision and first[1].startswith(f"revision {r.revision}")
                        and r.exitCode not in (None, 0)), None)
        execution = {"status": status, "exitCode": culprit.exitCode if culprit else None,
                     "reason": "; ".join(p[1] for p in problems)}
        expectation, label = "not-evaluable", build.no_verdict_label(execution)
    else:
        execution = {"status": "completed", "exitCode": 0, "reason": None}
        matches = bool(sides) and all(shown.get(rev) == {side} for rev, side in sides.items()) \
            and set(sides) == set(plan.revisions)
        expectation = "yes" if matches else "no"
        pair = task.get("pair")
        said = (f"as the {pair} pair's kind expects" if matches else
                f"not what the {pair} pair's kind expects" if sides else "no pair says what these controls should show")
        label = f"Replay: {'; '.join(words)}, on every JDK named: {said}"
    counterexamples = [{"input": str(p[0]), "contract": f"the oracle ({oracle['path']})",
                        "actual": f"revision {rev} on JDK {feature}: {p[1]}"}
                       for rev, by_jdk in outcomes.items() for feature, (_, ps) in sorted(by_jdk.items()) for p in ps]
    by = "model" if any(r.identities.get("replay") == "model" for r in records) else "jvm"
    fields = {"verdict": None, "verdictLabel": label, "execution": execution, "expectation": expectation,
              "counterexamples": counterexamples, "replay": {"by": by, "reproduced": expectation == "yes"},
              "proof": (f"no proof: {len(usable)} concrete control runs of the driver on the oracle's inputs, read by "
                        f"{oracle['path']}" + (" under generated stubs (model replay)" if by == "model" else "")),
              "problem": execution["reason"]}
    lines = [f"{e.get('kind')} {e.get('revision')} {e.get('identities', {}).get('jdk', '')}: {e.get('status')} "
             f"exit {e.get('exitCode')}: " + (json.dumps(e["oracle"]) if "oracle" in e else e.get("read", ""))
             for e in entries]
    return fields, entries, "\n".join(lines + [label]) + "\n"


def verifier_outcome(plan, bound, records):
    """The flat fields of a proof attempt, from its one verifier record (the module's docstring)."""
    import build
    verifiers = [r for r in records if r.kind == "verifier"]
    if len(verifiers) != 1:
        raise Refused(f"a {plan.kind} attempt has {len(verifiers)} verifier records, not one", stage="records")
    v = verifiers[0]
    outcomes = list(v.observations) if v.observations is not None else None
    if plan.kind != "prove" and outcomes is not None:
        outcomes = outcomes if len(outcomes) == 1 else None
    readable = outcomes is not None and outcomes and all(build.is_outcome(o) for o in outcomes)
    output = "".join(o["output"] for o in outcomes) if readable else ""
    fields = {"counterexamples": [], "proof": None, "problem": None, "domain": None, "replay": None,
              "properties": None, "property": None}
    if v.status in ("timed-out", "not-started"):
        execution = ({"status": "timed-out", "exitCode": None, "reason": f"the verifier did not finish in {v.seconds} s"}
                     if v.status == "timed-out" else
                     {"status": "tool-error", "exitCode": None, "reason": "the verifier did not start"})
    elif v.status == "killed" or v.exitCode is None:
        execution = {"status": "killed", "exitCode": v.exitCode, "reason": "the verifier was killed"}
    else:
        # An exit code jvmcontract uses for a verdict (0 or 1) completes only with a readable outcome.
        execution = build.execution_status(v.exitCode, "--json outcome" if readable else "")
        if execution["status"] == "invalid-output":
            execution["reason"] = (f"the verifier exited with code {v.exitCode}, and its --json outcome is missing or "
                                   "unreadable: no verdict, a violation least of all")
    verdict = None
    if execution["status"] == "completed":
        if plan.kind == "prove":
            props = [build.property_record(o, f"property-{n}" if len(outcomes) > 1 else None, None)
                        for n, o in enumerate(outcomes, 1)]
            headline = build.property_headline([o.get("verdict") for o in outcomes])
            witnesses = [r["counterexample"] for r in props if r["counterexample"]]
            evidence = witnesses if all(r["counterexample"] for r in props if r["verdict"] == "violation") else []
            execution, verdict = build.conclude_outcome(v.exitCode, output, {"verdict": headline}, evidence, True)
            if verdict is not None:
                lead = next(r for want in ("violation", "unverifiable", "verified") for r in props if r["verdict"] == want)
                fields.update({"properties": props, "counterexamples": witnesses, "domain": lead["domain"],
                               "proof": lead["proof"], "problem": lead["problem"],
                               "property": {"assert": lead["assert"], "assume": lead["assume"],
                                            **({"throws": lead["throws"]} if lead.get("throws") else {})}})
        else:
            outcome = outcomes[0]
            witnesses = build.equivalence_counterexamples(outcome)
            execution, verdict = build.conclude_outcome(v.exitCode, output, outcome, witnesses, True)
            if verdict is not None:
                replay = outcome.get("replay")
                fields.update({"counterexamples": witnesses if verdict == "violation" else [], "domain": outcome.get("domain"),
                               "proof": outcome.get("proof"), "problem": outcome.get("problem"),
                               "replay": {"by": replay["by"], "reproduced": replay["reproduced"]} if replay else None})
    vacuous = verdict == "verified" and any((r or {}).get("vacuous") for r in (fields["properties"] or []))
    if vacuous:
        fields["coverage"] = {"vacuous": True, "reason": next(r["vacuous"] for r in fields["properties"] if r.get("vacuous"))}
    status = build.CONCLUSION.get(verdict) if verdict else None
    if execution["status"] != "completed" or verdict is None:
        expectation, label = "not-evaluable", build.no_verdict_label(execution)
    else:
        expectation = "yes" if status == plan.expected and not vacuous else "no"
        label = build.VERDICT_LABEL[verdict] + (", vacuously: no input in the domain reaches the calls" if vacuous else "")
    fields.update({"verdict": verdict, "verdictLabel": label, "execution": execution, "expectation": expectation})
    if fields["problem"] is None and execution["status"] != "completed":
        fields["problem"] = execution["reason"]
    return fields, [{**r.as_dict()} for r in records], output


def excerpt(target_path, revision):
    """Where target.json names the revision: the receipt's `before` and `after` (a target task has no patch, so its
    changed region is the pair of revisions as the sidecar states them)."""
    lines = Path(target_path).read_text().splitlines()
    start = next((i for i, line in enumerate(lines) if '"revisions"' in line), 0)
    at = next((i for i in range(start, len(lines)) if f'"{revision}"' in lines[i]), start)
    return {"file": "target.json", "startLine": at + 1, "code": lines[at].strip()}


def bytecode(p):
    originals = sorted((a.path, a.sha256) for a in p.artifacts if a.role == "original")
    return {"sha256": workflow.canonical_digest(originals), "files": len(originals)} if originals else None


def stage_of(r):
    feature = jdk_feature(r.identities.get("jdk"))
    return {"name": f"{r.kind} {r.revision or 'pair'}" + (f" on JDK {feature}" if feature else ""), "status": r.status,
            "exitCode": r.exitCode, "seconds": float(r.seconds or 0), "stdout": r.stdout, "stderr": r.stderr}


def write_bundle(directory, files):
    import build
    (directory / "records").mkdir()
    artifacts = []
    for name, text in files.items():
        path = directory / "records" / name
        path.write_text(text)
        artifacts.append({"path": f"records/{name}", "sha256": build.file_digest(path), "bytes": path.stat().st_size})
    return {"artifacts": artifacts}


def publish(plan, prepared, records, out):
    """workflow.ingest(): the receipt of one attempt at `plan`, or Unsupported when the records can't be bound or the
    receipt doesn't pass check_result(), in which case nothing is published."""
    import build
    try:
        if not isinstance(plan, interfaces.TaskPlan):
            raise Refused("the plan is not a TaskPlan")
        records = tuple(records or ())
        if not all(isinstance(r, interfaces.ExecutionRecord) for r in records):
            raise Refused("a record is not an ExecutionRecord", stage="records")
        target_path, target = sidecar_of(plan)
        bound = bound_revisions(plan, prepared)
        replay = plan.kind == "replay"
        if replay and any(r.kind == "verifier" for r in records):
            raise Refused("a replay runs no verifier, and its records hold a verifier run", stage="records")
        oracle = oracle_control(plan, target, task_of(target, plan)) if replay else None
        claim = claim_record(plan, target_path, bound, records, oracle)
        if replay:
            fields, entries, text = replay_outcome(plan, target, bound, records, oracle)
            output = SUMMARY
        else:
            fields, entries, text = verifier_outcome(plan, bound, records)
            output = VERIFIER_OUTPUT
    except Refused as e:
        return Unsupported("ingest", WORKFLOW, e.reason, stage=e.stage, diagnostic=e.diagnostic)

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    # The attempt's id (stored-result.schema.json: YYYYMMDDTHHMMSSZ- and 8 hex digits) sorts in start order to the
    # microsecond, which the suffix's first five hex digits carry (999999 is f423f), three random ones after them: path
    # order is attempt order, and discovery reads a task's latest receipt as its last current one.
    attempt_id = f"{started:%Y%m%dT%H%M%SZ}-{started.microsecond:05x}{os.urandom(2).hex()[:3]}"
    staging = out / f".{attempt_id}.publishing"
    staging.mkdir()
    try:
        bundle = write_bundle(staging, {EXECUTION: json.dumps({"task": plan.task, "records": entries}, indent=2,
                                                              ensure_ascii=False) + "\n", output: text})
        job = {"jobId": os.environ.get("VERIFY_JOB_ID"), "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"),
               "workdir": os.environ.get("VERIFY_WORKDIR")}
        names = list(plan.revisions)
        verifier = next((r for r in records if r.kind == "verifier"), None)
        tools = {"java": "; ".join(claim["target"]["jdks"])}
        if verifier is not None:
            tools["jvmcontract"] = verifier.identities.get("jvmcontract")
        attempt = {"id": attempt_id, "claim": claim["id"], "startedAt": started.isoformat(timespec="seconds"),
                   "seconds": round(sum(float(r.seconds or 0) for r in records), 1), "engine": plan.engine,
                   "options": list(verifier.argv[1:]) if verifier else [], "tools": tools,
                   "bytecode": {"before": bytecode(bound[names[0]][1]) if len(names) > 1 else None,
                                "after": bytecode(bound[names[-1]][1])},
                   "pipeline": job if any(job.values()) else None, "execution": fields["execution"],
                   "stages": [stage_of(r) for r in records], "workspace": None}
        if not replay:
            bounds = plan.claim.get("bounds") or {}
            attempt["exploration"] = {"unwind": bounds.get("unwind"), "maxArrayLength": bounds.get("maxArrayLength"),
                                      "complete": True if fields["verdict"] == "verified" and fields["proof"]
                                      and "with unwinding assertions" in fields["proof"] else None}
        # A target task's attempt runs no module tests (its concrete controls are its records), so existingTests is
        # null, never a run that didn't pass; one revision has no before (result.schema.json allows both with a target).
        result = {"existingTests": None,
                  "before": excerpt(target_path, names[0]) if len(names) > 1 else None,
                  "after": excerpt(target_path, names[-1]),
                  "casesTotal": None, "purityViolations": [], "trustedCalls": [], "sarif": None, "output": f"records/{output}",
                  "statement": None, **fields, "matchesExpected": fields["expectation"] == "yes",
                  "claim": claim, "attempt": attempt}
        result = {k: v for k, v in result.items() if not (k in ("properties", "property", "coverage") and v is None)}
        result["conclusion"] = build.conclusion_record(claim, attempt, result)
        result["bundle"] = bundle
        try:
            build.check_result(staging, result)
        except SystemExit as e:
            raise Refused(f"the receipt doesn't pass check_result: {e}", stage="check") from None
        (staging / workflow.PLAN_RECORD).write_text(json.dumps(workflow.plan_record(plan), indent=2, ensure_ascii=False) + "\n")
        (staging / "result.json").write_text(json.dumps(result_format().pack(result), indent=2, ensure_ascii=False) + "\n")
        final = out / attempt_id
        staging.rename(final)
    except Refused as e:
        shutil.rmtree(staging, ignore_errors=True)
        return Unsupported("ingest", WORKFLOW, e.reason, stage=e.stage, diagnostic=e.diagnostic)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    path = (final / "result.json").resolve().relative_to(Path(plan.folder).resolve()).as_posix()
    return Receipt(path=path, claim=claim["id"], attempt=attempt_id, status=result["conclusion"]["status"],
                   execution=fields["execution"]["status"])


def result_format():
    import result_format as module
    return module

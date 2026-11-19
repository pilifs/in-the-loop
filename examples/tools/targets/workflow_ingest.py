"""Attempt ingestion (W2 of llm-dlc/loops/example-targets-workflow.md): one attempt's raw execution records, bound to
the prepared artifacts, published as one format-2 receipt. workflow.ingest() is this module's publish().

    publish(plan, prepared, records, out) -> Receipt | Unsupported

The receipt goes to out/<attempt>/result.json, beside it plan.json (workflow.plan_record(): what readiness tells a
current receipt from a stale one by) and the evidence under records/, listed with their sha256s in the bundle. Earlier
attempts are never touched.

The evidence keeps the raw streams (the user's review item 5, 2026-11-15): each record's stdout and stderr and the
runner's record it names (controls/controls.json, verifier/verifier.json), read from the attempt's directory the
record names (ExecutionRecord.directory, a temporary path that never enters the receipt), are copied into records/
under their own names, each cut to its first STREAM_CAP bytes. records/streams.json lists every one: its stage and
stream, its path in the attempt, its whole size and sha256, what was kept and whether it was cut, or why nothing was
(a record naming no directory, a missing file, a path outside the directory). attempt.stages then points at the
copies, and a not-started stage gives its `reason` (a proof task's controls whose adapter doesn't call the target,
287's guard tasks, for one). Nothing is published before build.py's check_result() passes: the flat view against
result.schema.json, the round trip through format 2, the stored document against stored-result.schema.json, and the
bundle against the files.

The claim is bound before anything is read as a result: the task's source-level claim (TaskPlan.claim), the sidecar's
sha256, each revision's identity, every classpath entry of each revision in order with its role and sha256, the JDKs,
and the claim, control, adapter and patch files by sha256. Its id is build.py's (canonical digest, 16 hex digits), so
the same task on the same inputs keeps its id across attempts, a vulnerable and a fixed task sharing a claim file get
different ids (their artifacts differ), and another engine or timeout is another attempt at the same claim. The
frozen source-level key the plan, the handoff, a refusal record and a job name (workflow.claim_key()) is recorded beside
it as claim.target.claimKey (the user's review item 6, 2026-11-15): compare the key to tell whether two receipts are
about one claim, and the id to tell whether they ran it on the same artifacts.

A revision's identity is its full commit SHA. A fixture revision has no commit: its identity is the git tree id of
its source directory, which `git rev-parse <commit>:<path>` reproduces from any commit holding the folder unchanged.
A constructed mutant's is its base's, its patch among the files. A revision that is an extracted source slice is
labelled so in claim.target.scopes; one whose slice the sidecar checks against published classes
(`preparation.slice.matches`, 307's before against Spring Security 5.2.0.M4) also gets claim.target.matched, each class
its preparation found byte-identical with the published JAR (source.slice.matched; the user's review item 7,
2026-11-15). A preparation that doesn't record exactly the matches its plan declares is not bound.

What an attempt shows stays apart: how it ran (execution), what it concluded (status, per obligation), whether that is
what the task expects (expectation), what it is about (scope) and whether its concrete side replayed (replay).
  - A replay task decides no claim: its status is always None. Its controls complete only when every revision ran on
    every JDK its artifact entry names, exited 0 with structured observations, on the prepared bytes, and the case's
    oracle read every one. Its expectation is `yes` only then, and only when each revision's outcome is the one its
    pair's kind says (an exact fix's before violates the oracle and its after holds, a mutation's base holds and its
    mutant violates, and so on; a release pair is a negative case's fix or a positive case's preserving change, by
    the case's role) on every JDK alike.
  - A proof task's conclusion is the verifier's, read from its `--json` outcome (ExecutionRecord.observations: the
    list `prove --json` prints, or the one outcome of `equivalence --json`), with build.py's rules: an exit code the
    outcome contradicts, a missing or unreadable outcome, or a violation without a witness is invalid output, never a
    violation; a refusal is unresolved; a kill or timeout has no verdict. A refuted property check's flat `replay`
    is its witnesses' (property_replay()), beside each property's own. Each witness call names the plan's revision
    its classes are (`revision`, name_revisions()), since jvmcontract calls a one-revision proof's classes `after`.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import sys
from datetime import datetime, timezone
from pathlib import Path

from targets import executions, interfaces, workflow
from targets.interfaces import WORKFLOW, Receipt, Unsupported

EXECUTION = "execution.json"  # the raw records, with what the oracle read in each
SUMMARY = "summary.txt"  # a replay's console output: one line per record
VERIFIER_OUTPUT = "verifier-output.txt"  # the verifier's console output, from its outcome
STREAMS = "streams.json"  # what each bundled stream and runner record is, its whole size and sha256, and why one isn't kept
# The bytes of one raw stream or runner record a receipt keeps: the first STREAM_CAP, with the whole one's size and
# sha256 in records/streams.json. Under jj's 1 MiB snapshot limit (VF-020), so a collected receipt is committed whole.
STREAM_CAP = 512 * 1024
NO_DIRECTORY = "the record names no attempt directory, so its streams can't be found"
ORACLE_TIMEOUT = 60
# What each kind of pair says the controls of its two revisions show: `violates` the oracle, or `holds`.
SIDES = {"exact-fix": ("violates", "holds"), "introduction": ("holds", "violates"),
         "mutation": ("holds", "violates"), "positive": ("holds", "holds")}
# A `release` pair is only a release comparison (target.schema.json): it brackets a negative case's fix, or a positive
# case's preserving change, so its sides follow the case's role. Another role's (a control's, a calibration's) say
# nothing.
RELEASE_SIDES = {"negative": ("violates", "holds"), "positive": ("holds", "holds")}
# A `correspondence` pair (a source slice against a published build of the same sources) says no side violates or holds:
# it expects the two sides to agree, the same observations and the same oracle problems on every JDK.
CORRESPONDENCE = "correspondence"
PRIORITY = ("killed", "timed-out", "tool-error", "invalid-output")
# Reads each record's observation lines with the oracle's problems(lines), or its check(lines) when it has no problems
# (runtime.py's docstring: the oracle convention), in a separate interpreter (-I: the oracle sees only the standard
# library). An exception (SystemExit included) is the oracle refusing a replay it can't judge; a result that isn't a
# list of (input, problem) pairs is an oracle that doesn't follow the convention, never a verdict.
ORACLE_RUNNER = r"""
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("target_oracle", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
read = getattr(module, "problems", None) if callable(getattr(module, "problems", None)) else module.check
name = read.__name__
out = []
for lines in json.load(sys.stdin):
    try:
        found = read(lines)
        if not isinstance(found, (list, tuple)) or not all(isinstance(p, (list, tuple)) and len(p) == 2 for p in found):
            raise TypeError(f"{name}() returned {type(found).__name__} {str(found)[:120]}, not a list of (input, problem)")
        out.append({"problems": [[p[0], str(p[1])] for p in found]})
    except (Exception, SystemExit) as e:
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
                       "files": claim_files(plan, oracle),
                       **({"claimKey": plan.claim["key"]} if plan.claim.get("key") else {})}}
    scopes = artifact_scopes(bound)
    if scopes:
        body["target"]["scopes"] = scopes
    matched = published_matches(bound)
    if matched:
        body["target"]["matched"] = matched
    return {"id": build.canonical_digest(body)[:16], **body}


def published_matches(bound):
    """{revision: [match]} for each revision whose slice the plan checks against published classes
    (`preparation.slice.matches`), from what its preparation recorded (`source.slice.matched`): the class entry, its
    sha256, and the published JAR by coordinates, URL and sha256. The preparation refuses a slice whose class differs,
    so a listed class is the published one byte for byte. None when no revision declares a match, so the other routes'
    claims and 305's are unchanged. Refused when a preparation doesn't record exactly the matches its plan declares."""
    def key(m):
        return m.get("class"), m.get("sha256"), (m.get("jar") or {}).get("sha256")
    out = {}
    for revision, (entry, prepared, _) in bound.items():
        declared = (entry.get("slice") or {}).get("matches") or []
        found = (((prepared.source or {}).get("slice") or {}).get("matched")) or []
        if sorted(map(key, declared)) != sorted(key(m) for m in found if m.get("identical") is True):
            raise Refused(f"revision {revision}'s preparation doesn't record the published-class match its plan declares "
                          f"({len(declared)} declared in slice.matches, {len(found)} recorded in source.slice.matched): "
                          f"the slice's correspondence with the published build isn't shown", stage="prepare")
        if found:
            out[revision] = [{"class": m["class"], "sha256": m["sha256"],
                              "jar": {k: m["jar"][k] for k in ("coordinates", "url", "sha256")}}
                             for m in sorted(found, key=lambda m: m["class"])]
    return out or None


def artifact_scopes(bound):
    """{revision: scope} when any revision is an extracted source slice (its own, or its mutant base's, route is
    source-slice), else None: a slice's receipt says so per revision, and nothing changes for the other routes."""
    def scope(entry):
        if "mutant" in entry:
            return "constructed-mutation-of-a-slice" if entry.get("route") == "source-slice" else "constructed-mutation"
        return {"source-slice": "extracted-source-slice", "fixture": "constructed-fixture"}.get(entry.get("route"),
                                                                                                 "original-bytecode")
    scopes = {revision: scope(entry) for revision, (entry, _, _) in bound.items()}
    return scopes if any("slice" in s for s in scopes.values()) else None


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
        return "tool-error", f"{where}: the JVM did not start ({record.status})" + (f": {record.reason}" if record.reason else "")
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
    """What each revision's controls should show, `violates` or `holds`, from the kind of the pair the task names (a
    release pair's by the case's role), or for one revision from every pair it appears in (None when they disagree or
    none does)."""
    pairs = (target.get("history") or {}).get("pairs") or []
    role = (target.get("identity") or {}).get("role")

    def kind_sides(pair):
        return RELEASE_SIDES.get(role) if pair.get("kind") == "release" else SIDES.get(pair.get("kind"))

    if task.get("pair"):
        sides = kind_sides(next((p for p in pairs if p.get("name") == task["pair"]), {}))
        return dict(zip(revisions, sides)) if sides else {}
    said = {kind_sides(p)[i] for p in pairs if kind_sides(p)
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
            entries.append({**entry_of(r), "read": "not this replay's"})
            continue
        problem = record_problem(r, bound)
        if problem:
            problems.append(problem)
            entries.append({**entry_of(r), "read": problem[1]})
        else:
            usable.append(r)
            entries.append(None)
    read = read_with_oracle(plan, oracle, usable)
    outcomes = {}  # revision -> {feature: (violates|holds, problems)}
    observed = {}  # revision -> {feature: the observations, as JSON lines}
    for r, verdict in zip(usable, read):
        i = next(i for i, e in enumerate(entries) if e is None)
        entries[i] = {**entry_of(r), "oracle": verdict}
        feature = jdk_feature(r.identities.get("jdk")) or r.identities.get("jdk") or "?"
        if "error" in verdict:
            problems.append(("invalid-output", f"revision {r.revision} on JDK {feature}: {verdict['error']}"))
            continue
        outcomes.setdefault(r.revision, {})[feature] = ("violates" if verdict["problems"] else "holds", verdict["problems"])
        observed.setdefault(r.revision, {})[feature] = [json.dumps(o, sort_keys=True) for o in r.observations or []]
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
        pair = task.get("pair")
        kind = next((x.get("kind") for x in (target.get("history") or {}).get("pairs") or [] if x.get("name") == pair),
                    None)
        if kind == CORRESPONDENCE:
            revs = list(plan.revisions)
            same_problems = len(revs) == 2 and all(
                {f: sorted(json.dumps(p, default=str) for p in ps) for f, (_, ps) in outcomes.get(r, {}).items()}
                == {f: sorted(json.dumps(p, default=str) for p in ps) for f, (_, ps) in outcomes.get(revs[0], {}).items()}
                for r in revs)
            same_observations = len(revs) == 2 and bool(observed.get(revs[0])) \
                and observed.get(revs[0]) == observed.get(revs[1])
            matches = same_problems and same_observations
            said = (f"the same observations and problems on each JDK, as the {pair} correspondence expects" if matches
                    else f"the two sides' {'observations' if same_problems else 'problems'} differ, and the {pair} "
                         f"correspondence expects them alike")
        else:
            matches = bool(sides) and all(shown.get(rev) == {side} for rev, side in sides.items()) \
                and set(sides) == set(plan.revisions)
            said = (f"as the {pair} pair's kind expects" if matches else
                    f"not what the {pair} pair's kind expects" if sides else "no pair says what these controls should show")
        expectation = "yes" if matches else "no"
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
    import checker_output as wire
    from result_format import CONCLUSION
    verifiers = [r for r in records if r.kind == "verifier"]
    if len(verifiers) != 1:
        raise Refused(f"a {plan.kind} attempt has {len(verifiers)} verifier records, not one", stage="records")
    v = verifiers[0]
    outcomes = list(v.observations) if v.observations is not None else None
    if plan.kind != "prove" and outcomes is not None:
        outcomes = outcomes if len(outcomes) == 1 else None
    readable = outcomes is not None and outcomes and all(wire.is_outcome(o) for o in outcomes)
    output = "".join(o["output"] for o in outcomes) if readable else ""
    fields = {"counterexamples": [], "proof": None, "problem": None, "domain": None, "replay": None,
              "properties": None, "property": None}
    if v.status in ("timed-out", "not-started"):
        execution = ({"status": "timed-out", "exitCode": None, "reason": f"the verifier did not finish in {v.seconds} s"}
                     if v.status == "timed-out" else
                     {"status": "tool-error", "exitCode": None,
                      "reason": "the verifier did not start" + (f": {v.reason}" if v.reason else "")})
    elif v.status == "killed" or v.exitCode is None:
        execution = {"status": "killed", "exitCode": v.exitCode, "reason": "the verifier was killed"}
    else:
        # An exit code jvmcontract uses for a verdict (0 or 1) completes only with a readable outcome.
        execution = wire.execution_status(v.exitCode, "--json outcome" if readable else "")
        if execution["status"] == "invalid-output":
            execution["reason"] = (f"the verifier exited with code {v.exitCode}, and its --json outcome is missing or "
                                   "unreadable: no verdict, a violation least of all")
    verdict = None
    if execution["status"] == "completed":
        if plan.kind == "prove":
            props = [wire.property_record(o, f"property-{n}" if len(outcomes) > 1 else None, None)
                        for n, o in enumerate(outcomes, 1)]
            headline = wire.property_headline([o.get("verdict") for o in outcomes])
            witnesses = [r["counterexample"] for r in props if r["counterexample"]]
            evidence = witnesses if all(r["counterexample"] for r in props if r["verdict"] == "violation") else []
            execution, verdict = wire.conclude_outcome(v.exitCode, output, {"verdict": headline}, evidence, True)
            if verdict is not None:
                lead = next(r for want in ("violation", "unverifiable", "verified") for r in props if r["verdict"] == want)
                fields.update({"properties": props, "counterexamples": witnesses, "domain": lead["domain"],
                               "proof": lead["proof"], "problem": lead["problem"],
                               "replay": property_replay(props) if verdict == "violation" else None,
                               "property": {"assert": lead["assert"], "assume": lead["assume"],
                                            **({"throws": lead["throws"]} if lead.get("throws") else {})}})
        else:
            outcome = outcomes[0]
            witnesses = wire.equivalence_counterexamples(outcome)
            execution, verdict = wire.conclude_outcome(v.exitCode, output, outcome, witnesses, True)
            if verdict is not None:
                replay = outcome.get("replay")
                fields.update({"counterexamples": witnesses if verdict == "violation" else [], "domain": outcome.get("domain"),
                               "proof": outcome.get("proof"), "problem": outcome.get("problem"),
                               "replay": {"by": replay["by"], "reproduced": replay["reproduced"]} if replay else None})
    if verdict in ("verified", "violation") and (v.identities.get("recipe") or plan.claim.get("boundEnvironment")
            or any(isinstance(o, dict) for o in plan.claim.get("observations", []))):
        from targets import qualification
        classpaths = {}
        for revision, (_, prepared, _) in bound.items():
            by_path = {a.path: a for a in prepared.artifacts}
            classpaths[revision] = [{"path": a.path, "sha256": a.sha256, "role": a.role}
                                    for a in (by_path[path] for path in prepared.classpath)
                                    if a.role in ("original", "dependency", "stub")]
            if plan.claim.get("adapter"):
                adapters = [{"path": a.path, "sha256": a.sha256, "role": a.role} for a in prepared.artifacts if a.role == "adapter"]
                classpaths[revision] = adapters + classpaths[revision]
        artifact_problem = None
        if plan.claim.get("adapter"):
            _, artifact_problem = qualification.correspondence(plan, {r: p for r, (_, p, _) in bound.items()}, records)
        if v.identities.get("classpath") != classpaths:
            artifact_problem = "the verifier's ordered classpaths are not the prepared artifacts"
        elif not v.identities.get("jvmcontract") or not v.identities.get("jdkRelease"):
            artifact_problem = "the verifier did not identify its checker binary and JDK"
        elif verdict == "verified" and v.directory and (Path(v.directory) / v.stdout).is_file() and (Path(v.directory) / v.stdout).stat().st_size > STREAM_CAP:
            artifact_problem = "the verifier output needed for this establishment exceeds the archived evidence limit"
        entry = v.identities.get("checkedEntry") or plan.target
        independent = v.identities.get("independentReplay")
        if verdict == "violation" and v.identities.get("recipe") and independent is None:
            from targets import replay_candidate
            if replay_candidate.supported(entry, plan.claim):
                artifact_problem = "the candidate lacks independent JVM qualification"
        if independent is not None:
            candidates = [o["counterexample"] for o in outcomes if o.get("counterexample")]
            if len(independent) != len(candidates) or not candidates:
                artifact_problem = "missing independent replay for a candidate"
            else:
                for replay, candidate in zip(independent, candidates):
                    from targets import replay_candidate
                    artifact_problem = artifact_problem or replay_candidate.evidence_problem(plan, bound, v.identities, replay, candidate)
                if artifact_problem is None:
                    fields["replay"] = {"by": "jvm", "reproduced": True}
        for outcome in outcomes:
            if v.identities.get("recipe"):
                reason = artifact_problem or qualification.statement_problem(plan, outcome, entry)
            else:
                reason = artifact_problem or qualification.check(plan.claim, {"target": plan.target}, outcome,
                                                                  plan.claim["bounds"].get("maxArrayLength"))
            if reason:
                execution = {"status": "invalid-output", "exitCode": v.exitCode, "reason": reason}
                verdict = None
                fields.update(proof=None, problem=reason)
                break
        if len(outcomes) == 1:
            fields["stated"] = wire.stated_record(outcomes[0])
    name_revisions(plan, fields["counterexamples"])
    vacuous = verdict == "verified" and any((r or {}).get("vacuous") for r in (fields["properties"] or []))
    if vacuous:
        fields["coverage"] = {"vacuous": True, "reason": next(r["vacuous"] for r in fields["properties"] if r.get("vacuous"))}
    status = CONCLUSION.get(verdict) if verdict else None
    if execution["status"] != "completed" or verdict is None:
        expectation, label = "not-evaluable", wire.no_verdict_label(execution)
    else:
        expectation = "yes" if status == plan.expected and not vacuous else "no"
        label = wire.VERDICT_LABEL[verdict] + (", vacuously: no input in the domain reaches the calls" if vacuous else "")
    fields.update({"verdict": verdict, "verdictLabel": label, "execution": execution, "expectation": expectation})
    if fields["problem"] is None and execution["status"] != "completed":
        fields["problem"] = execution["reason"]
    return fields, [entry_of(r) for r in records], output


def property_replay(props):
    """A refuted property check's flat `replay` (the user's review item 6, 2026-11-15): where its witnesses were run
    again, `reproduced` only when every refuted property's was, and None when any refuted property states no replay or
    they were run by different means. Each property keeps its own under `properties`."""
    replays = [r.get("replay") for r in props if r["verdict"] == "violation"]
    if not replays or not all(replays) or len({r["by"] for r in replays}) != 1:
        return None
    return {"by": replays[0]["by"], "reproduced": all(r["reproduced"] for r in replays)}


def name_revisions(plan, counterexamples):
    """Give each witness call the plan's revision its classes are (item 6): jvmcontract labels a call's classes
    `after` or `before`, the sides of the run it was given, so a one-revision prove calls its only classes `after`,
    whatever the revision (105's `before`, 287's `fixed-release`). The tool's label stays in `classes`."""
    names = list(plan.revisions)
    sides = {"after": names[-1], "before": names[0] if len(names) > 1 else None}
    for c in counterexamples or []:
        witness = (c or {}).get("witness") or {}
        for key in ("call", "previousCall"):
            call = witness.get(key)
            if call and sides.get(call.get("classes")):
                call["revision"] = sides[call["classes"]]


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


def stage_name(r):
    feature = jdk_feature(r.identities.get("jdk"))
    return f"{r.kind} {r.revision or 'pair'}" + (f" on JDK {feature}" if feature else "")


def stage_of(r, kept=None):
    """The attempt's stage for record `r`: its streams' bundled copies (`kept`, by stream) where there are any, else
    the paths relative to the attempt's directory, and a not-started record's reason."""
    kept = kept or {}
    stage = {"name": stage_name(r), "status": r.status, "exitCode": r.exitCode, "seconds": float(r.seconds or 0),
             "stdout": kept.get("stdout", r.stdout), "stderr": kept.get("stderr", r.stderr)}
    if r.status == "not-started" and r.reason:
        stage["reason"] = r.reason
    return stage


def entry_of(r):
    """A record as records/execution.json keeps it: everything but the attempt's temporary directory."""
    entry = r.as_dict()
    entry.pop("directory", None)
    return entry


def raw_streams(records):
    """The raw files of the attempt the records name, for the bundle: ({name: bytes}, streams.json's entries, and per
    record {stream: its copy's path in the receipt}). Each file is read from the record's directory, never outside it,
    and cut to STREAM_CAP bytes; a record naming no directory, or a file that can't be read, keeps its path and says
    why in its entry."""
    taken = {EXECUTION, SUMMARY, VERIFIER_OUTPUT, STREAMS}
    files, entries, kept, seen = {}, [], [], {}

    def copy(r, stream, source, stage):
        entry = {"stage": stage, "stream": stream, "source": source, "kept": None}
        if not r.directory:
            entries.append({**entry, "why": NO_DIRECTORY})
            return None
        base = Path(r.directory).resolve()
        path = (base / source).resolve()
        if not path.is_relative_to(base):
            entries.append({**entry, "why": f"{source} is outside the attempt's directory"})
            return None
        try:
            data = path.read_bytes()
        except OSError as e:
            entries.append({**entry, "why": f"{source} can't be read: {(e.strerror or str(e)).lower()}"})
            return None
        safe = re.sub(r"[^A-Za-z0-9._-]", "-", Path(source).name).lstrip("._-") or stream
        name = safe if safe not in taken else re.sub(r"[^A-Za-z0-9._-]", "-", Path(source).parent.name) + "-" + safe
        n = 2
        while name in taken:
            name, n = f"{n}-{safe}", n + 1
        taken.add(name)
        files[name] = data[:STREAM_CAP]
        entries.append({**entry, "kept": f"records/{name}", "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                        "keptBytes": len(files[name]), "truncated": len(data) > STREAM_CAP})
        return f"records/{name}"

    for r in records:
        stage = stage_name(r)
        kept.append({k: v for k in ("stdout", "stderr") if (v := copy(r, k, getattr(r, k), stage))})
        if r.record and (r.directory, r.record) not in seen:
            seen[(r.directory, r.record)] = copy(r, "record", r.record, None)
    return files, entries, kept


def write_bundle(directory, files):
    import build
    (directory / "records").mkdir()
    artifacts = []
    for name, text in files.items():
        path = directory / "records" / name
        if isinstance(text, bytes):
            path.write_bytes(text)
        else:
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
            try:
                fields, entries, text = verifier_outcome(plan, bound, records)
            except (KeyError, TypeError, ValueError, IndexError, AttributeError) as error:
                raise Refused(f"malformed checker evidence: {error}", stage="records") from None
            output = VERIFIER_OUTPUT
    except Refused as e:
        return Unsupported("ingest", WORKFLOW, e.reason, stage=e.stage, diagnostic=e.diagnostic)

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    ids = {r.identities.get("executionId") for r in records}
    if len(ids) > 1:
        return Unsupported("ingest", WORKFLOW, "mixed execution identities in the completion", stage="records")
    attempt_id = next(iter(ids), None)
    started = datetime.now(timezone.utc)
    completion = None
    if attempt_id is not None:
        if not isinstance(attempt_id, str) or not executions.ID.fullmatch(attempt_id):
            return Unsupported("ingest", WORKFLOW, "invalid execution identity", stage="records")
        journal_path = out / "executions" / attempt_id / "attempt.json"
        if not journal_path.is_file():
            return Unsupported("ingest", WORKFLOW, "execution was never started for this task", stage="records")
        journal = json.loads(journal_path.read_text())
        if (journal["claimKey"] != plan.claim.get("key") or journal["revisions"] != list(plan.revisions)
                or journal["task"] != plan.task):
            return Unsupported("ingest", WORKFLOW, "the execution belongs to another frozen subject", stage="records")
        started = datetime.fromisoformat(journal["startedAt"])
        completion = {"executionId": attempt_id, "digest": workflow.canonical_digest({"claim": claim["id"], "records": entries})}
    else:
        attempt_id = executions.new_id(started)
    final = out / attempt_id
    def existing():
        token = final / "completion.json"
        conflict = Unsupported("ingest", WORKFLOW, "conflicting completion for this execution", stage="records")
        if completion is None or not token.is_file():
            return conflict
        saved = json.loads((final / "result.json").read_text())
        original_token = json.loads(token.read_text())
        if original_token != completion:
            # A sibling task may have been added to target.json since publication. Its file digest
            # is part of a historical bound claim, so compare the stored binding and the raw completion.
            original = saved["claim"]
            changeable = lambda c: {**c, "id": None, "target": {**c["target"], "sidecar": None}}
            if (changeable(original) != changeable(claim)
                    or original_token != {"executionId": attempt_id,
                                          "digest": workflow.canonical_digest({"claim": original["id"], "records": entries})}):
                return conflict
        return Receipt(path=(final / "result.json").relative_to(plan.folder).as_posix(), claim=saved["claim"]["id"],
                       attempt=attempt_id, status=saved["conclusion"]["status"], execution=saved["attempt"]["execution"]["status"])
    if final.exists():
        return existing()
    staging = Path(tempfile.mkdtemp(prefix=f".{attempt_id}.", dir=out))
    try:
        streams, listed, kept = raw_streams(records)
        bundle = write_bundle(staging, {EXECUTION: json.dumps({"task": plan.task, "records": entries}, indent=2,
                                                              ensure_ascii=False) + "\n", output: text,
                                        STREAMS: json.dumps({"cap": STREAM_CAP, "streams": listed}, indent=2,
                                                            ensure_ascii=False) + "\n", **streams})
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
                   "stages": [stage_of(r, k) for r, k in zip(records, kept)], "workspace": None}
        if not replay:
            actual = next(iter(verifier.observations or []), {}) if verifier else {}
            search = actual.get("search") or {}
            stated = actual.get("stated") or {}
            bounds = stated.get("bounds") or {}
            attempt["engine"] = (stated.get("checker") or {}).get("engine") or search.get("engine") or plan.engine
            attempt["exploration"] = {"unwind": bounds.get("unwind", search.get("unwind")),
                                      "maxArrayLength": search.get("max_array_length", bounds.get("max_array_length")),
                                      "complete": bounds.get("complete")}
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
        if completion:
            (staging / "completion.json").write_text(json.dumps(completion) + "\n")
        try:
            staging.rename(final)
        except OSError:
            if not final.is_dir():
                raise
            shutil.rmtree(staging)
            return existing()
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

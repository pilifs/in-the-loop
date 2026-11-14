"""Task planning, attempt ingestion and the index projection: the workflow stream's side of the interfaces
(interfaces.py) of llm-dlc/loops/example-targets.md. plan_task() resolves a task from the sidecar and its claim file
alone (W1), and readiness() derives each task's readiness milestones and summaries from the sidecar, its files and
the folder's receipts (W1). ingest() publishes one attempt's format-2 receipt (W2, workflow_ingest.py). handoff()
fails closed with the named Unsupported result until the workflow stream replaces it (W3); project() reports only what
target.json states until W4 projects readiness() into the index. Signatures are frozen.

A task's claim is frozen twice. Planning freezes the source-level claim: the task's statement, domain, observations,
assumptions, allowed change, models and bounds (the tool's defaults resolved), and `key`, their canonical digest,
which tasks sharing a claim file and relation share whatever revision they run on. Ingestion binds it to the prepared
artifacts, so a vulnerable and a fixed task's executed claims differ while their property is one.
"""

import hashlib
import json
from pathlib import Path

from targets.interfaces import TaskPlan, WORKFLOW, Unsupported

CLAIM_SCHEMA = Path(__file__).resolve().parents[2] / "schema" / "target-claim.schema.json"
CLAIM_VERSION = "example-target-claim/v1"
# The bounds jvmcontract's prove and equivalence take when none is given (lib/src/main.rs: `unwind` 16,
# `max_array_length` 8): planning states them, so a claim never rests on a default the tool might change. A timeout is
# not a bound: a different timeout is another attempt at the same claim.
DEFAULT_BOUNDS = {"unwind": 16, "maxArrayLength": 8}
PROOF_KINDS = ("prove", "compare", "equivalence")
# Which claim kinds a task kind takes.
CLAIM_KINDS = {"prove": ("property",), "compare": ("preservation", "compatibility"),
               "equivalence": ("preservation", "compatibility")}
# The build tools a route needs on the machine: a wrapper brings its own, given the JDK.
BUILD_TOOLS = {"gradle": "gradle", "maven": "maven"}


class ClaimError(ValueError):
    """Why a task's claim file can't be read as its claim."""


def canonical_digest(value):
    """build.py's canonical_digest(), the one claim keys are made with (imported there by name would be circular)."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(folder, name):
    """The file `name` of the example's folder, refused when it resolves outside it (links included) or is missing."""
    root = Path(folder).resolve()
    resolved = (Path(folder) / name).resolve()
    if root not in resolved.parents:
        raise ClaimError(f"{name} resolves outside the example's folder")
    if not resolved.is_file():
        raise ClaimError(f"{name} does not exist")
    return resolved


def hashed(folder, name):
    return {"path": name, "sha256": file_sha256(inside(folder, name))}


def load_claim(folder, name):
    """The claim file `name` of the example in `folder`, parsed and checked against target-claim.schema.json, with
    every file it names inside the folder. Raises ClaimError."""
    path = inside(folder, name)
    try:
        claim = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise ClaimError(f"{name}: not JSON: {e}") from None
    try:
        import jsonschema
    except ImportError:
        raise ClaimError(f"{name}: cannot be validated: the Python module jsonschema is not installed") from None
    validator = jsonschema.Draft202012Validator(json.loads(CLAIM_SCHEMA.read_text()))
    errors = sorted(validator.iter_errors(claim), key=lambda e: list(e.absolute_path))
    if errors:
        e = errors[0]
        where = "/".join(str(p) for p in e.absolute_path) or "(top level)"
        raise ClaimError(f"{name}: {where}: {e.message} (it must be a {CLAIM_VERSION} claim file)")
    for key in ("plan", "contracts"):
        if key in claim:
            inside(folder, claim[key])
    for model in claim.get("models", []):
        inside(folder, model)
    return claim


def refuse(reason, stage="plan", diagnostic=None):
    return Unsupported("task-plan", WORKFLOW, reason, stage=stage, diagnostic=diagnostic)


def revisions_of(target, task):
    """The revision names a task prepares: its revision, or its pair's before and after."""
    if "pair" in task:
        pair = next(p for p in target["history"].get("pairs", []) if p["name"] == task["pair"])
        return (pair["before"], pair["after"])
    return (task["revision"],)


def controls_of(target, task, revisions):
    """The controls that apply to a task: those naming neither a task nor a revision, or this task, or one of its
    revisions."""
    return [c for c in target.get("controls", [])
            if c.get("task", task["id"]) == task["id"] and c.get("revision", revisions[0]) in revisions]


def artifact_sources(folder, target, revisions):
    """Per revision, what preparation starts from (interfaces.ARTIFACT_SOURCE), or a reason it can't start.

    A constructed mutant's entry has no `commit` or `fixture` of its own: `mutant` names its base (with the base's
    commit or fixture), its patch by path and sha256, checked here, and the mutation in words. A preparation that
    doesn't know the key fails on it, rather than preparing the base unpatched. On the published-artifact route the
    base's published artifacts come with it: the mutant itself is built (patched sources against them), never
    fetched."""
    prep = target.get("preparation")
    if prep is None:
        return "the sidecar has no preparation: the case is catalogued, and nothing says how to obtain its artifacts"
    route = prep["route"]
    defined = target["history"]["revisions"]
    out = []
    for name in revisions:
        revision = defined[name]
        entry = {"revision": name, "route": route, "repository": target["history"]["repository"]}
        source = name
        if "mutant" in revision:
            m = revision["mutant"]
            source = m["base"]
            try:
                patch = hashed(folder, m["patch"])
            except ClaimError as e:
                return f"revision {name}: its patch {e}"
            if patch["sha256"] != m["sha256"]:
                return (f"revision {name}: its patch {m['patch']} has sha256 {patch['sha256']}, and the sidecar locks "
                        f"{m['sha256']}: a changed mutant is a different control, never prepared under the old lock")
            base = {"revision": source}
            base.update({k: defined[source][k] for k in ("commit", "fixture") if k in defined[source]})
            entry["mutant"] = {"base": base, "patch": patch, "description": m["description"]}
        elif "commit" in revision:
            entry["commit"] = revision["commit"]
            if "parent" in revision:
                entry["parent"] = revision["parent"]
        else:
            entry["fixture"] = revision["fixture"]
        if route == "published-artifact":
            published = [{k: a[k] for k in ("coordinates", "url", "sha256") if k in a}
                         for a in prep.get("artifacts", []) if a["revision"] == source]
            if not published:
                return f"revision {source}: the published-artifact route names no artifact for it"
            if source == name:
                entry["published"] = published
                if len(published) == 1:
                    entry.update(published[0])
            else:
                entry["mutant"]["base"]["published"] = published
        if route == "upstream-build":
            if "build" not in prep:
                return "the upstream-build route names no build (tool, argv, jdk)"
            entry["build"] = prep["build"]
        fixture = "fixture" in defined[source]
        if (route == "fixture") != fixture:
            return (f"revision {name}: the {route} route and a {'fixture' if fixture else 'commit'} revision"
                    f"{' (the base of a mutant)' if source != name else ''}: only the fixture route builds fixture "
                    "sources, and it builds nothing else")
        entry["adapters"] = list(prep.get("adapters", []))
        entry["jdks"] = list(prep.get("jdks", []))
        out.append(entry)
    return tuple(out)


def tools_of(task, route, prep, controls, artifacts=()):
    """What the task's preparation, controls and verifier call: never JBMC for a native task. A constructed mutant
    needs git (`git apply`), and on the published-artifact route javac, to build its patched sources."""
    mutants = any("mutant" in a for a in artifacts)
    required = ["java"]
    sources = list(prep.get("adapters", [])) + [c["path"] for c in controls]
    if route == "fixture" or any(s.endswith(".java") for s in sources) or (mutants and route == "published-artifact"):
        required.append("javac")
    if route == "upstream-build" or mutants:
        required.append("git")
    if route == "upstream-build":
        tool = BUILD_TOOLS.get(prep["build"]["tool"])
        if tool:
            required.append(tool)
    if any(c["path"].endswith(".py") for c in controls):
        required.append("python3")
    optional = []
    if task["kind"] in PROOF_KINDS:
        required.append("jvmcontract")
        if task.get("engine") == "jbmc":
            required.append("jbmc")
        elif task.get("engine") == "auto":
            optional.append("jbmc")
    return {"required": required, "optional": optional}


def source_claim(folder, target, task, controls):
    """The task's source-level claim, frozen before preparation, or ClaimError."""
    kind = task["kind"]
    stated = None
    if "claim" in task:
        stated = load_claim(folder, task["claim"])
        if kind == "replay":
            raise ClaimError(f"{task['claim']}: a replay task runs concrete controls only, and takes no claim file")
        if stated["kind"] not in CLAIM_KINDS[kind]:
            raise ClaimError(f"{task['claim']}: a {stated['kind']} claim, and task {task['id']} is a {kind} task, which "
                             f"takes a {' or '.join(CLAIM_KINDS[kind])} claim")
    elif kind == "prove":
        raise ClaimError("its claim isn't frozen: a prove task's property is stated in a claim file (claims/), and the "
                         "task names none")
    bounds = dict(DEFAULT_BOUNDS) if kind in PROOF_KINDS else {}
    claimed = (stated or {}).get("bounds", {})
    conflicts = sorted(k for k in set(claimed) & set(task.get("bounds", {})) if claimed[k] != task["bounds"][k])
    if conflicts:
        raise ClaimError(f"the task's bounds disagree with its claim file's ({', '.join(conflicts)}): tasks sharing a "
                         "claim share its bounds")
    explicit = {**claimed, **task.get("bounds", {})}
    bounds.update(explicit)
    stated = stated or {}
    claim = {
        "task": task["id"], "kind": kind, "relation": task["relation"], "target": task["target"],
        "file": task.get("claim"), "sha256": file_sha256(inside(folder, task["claim"])) if "claim" in task else None,
        "property": stated.get("property"), "claimKind": stated.get("kind"),
        "statement": stated.get("statement"), "assume": stated.get("assume"), "assert": stated.get("assert"),
        "throws": stated.get("throws", []), "nullable": stated.get("nullable", []), "mayAlias": stated.get("mayAlias", []),
        "observations": stated.get("observations", ["result", "exception"] if kind in PROOF_KINDS else []),
        "assumptions": stated.get("assumptions", []), "allowedChange": task.get("allowedChange"),
        "bounds": bounds, "explicitBounds": explicit,
        "defaultBounds": sorted(k for k in bounds if k not in explicit),
        "models": [hashed(folder, m) for m in stated.get("models", [])],
        "plan": hashed(folder, stated["plan"]) if "plan" in stated else None,
        "contracts": hashed(folder, stated["contracts"]) if "contracts" in stated else None,
        "gaps": task.get("gaps"), "parent": task.get("parent"),
        "controls": [{"id": c["id"], "kind": c["kind"], **hashed(folder, c["path"])} for c in controls],
    }
    claim["key"] = claim_key(claim)
    return claim


def claim_key(claim):
    """The source-level claim's canonical key: what is checked and over what, without the task's id, its revisions or
    the claim file's path, so a vulnerable and a fixed task stating one property share it. The engine is left out (a
    strategy: another attempt); the gap mode is in (assume changes what a verdict means). A replay's key is its target
    and its controls' contents."""
    if claim["kind"] == "replay":
        body = {"kind": "replay", "relation": claim["relation"], "target": claim["target"],
                "controls": sorted((c["kind"], c["sha256"]) for c in claim["controls"])}
    else:
        body = {k: claim[k] for k in ("kind", "relation", "target", "property", "claimKind", "statement", "assume",
                                       "assert", "throws", "nullable", "mayAlias", "observations", "assumptions",
                                       "allowedChange", "bounds", "gaps", "parent")}
        body["models"] = sorted(m["sha256"] for m in claim["models"])
        body["plan"] = claim["plan"] and claim["plan"]["sha256"]
        body["contracts"] = claim["contracts"] and claim["contracts"]["sha256"]
    return canonical_digest({"format": CLAIM_VERSION, **body})[:16]


def plan_task(folder, example, target, task):
    """The TaskPlan of the task with id `task` in the example's checked sidecar `target`, or Unsupported. Pure: no
    network, build, solver or directory; it reads the sidecar's files. The caller has checked that the task exists.

    Refused, with the reason (route.plan() shows it as `notExecuted`): a catalogued case with no preparation, a route
    missing what it needs, a proof task naming no engine or gap mode (the CLI's defaults are JBMC and strict, and a
    claim never rests on a default), a prove task with no claim file, a claim file that is missing, invalid, of the
    wrong kind or at odds with the task's bounds, a replay with no oracle or driver, and an introduction task until
    the sidecar records an established introduction and an independent oracle."""
    folder = Path(folder)
    t = next(x for x in target["tasks"] if x["id"] == task)
    revisions = revisions_of(target, t)
    if t["relation"] == "introduction":
        status = target["history"].get("introduction", {}).get("status", "unknown")
        oracles = [c for c in controls_of(target, t, revisions) if c["kind"] == "oracle"]
        if status != "established" or not oracles:
            return refuse(f"an introduction task stays unavailable until ancestry and an independent oracle justify it "
                          f"(introduction {status}, {len(oracles)} oracle control{'s' if len(oracles) != 1 else ''})")
    if t["kind"] in PROOF_KINDS:
        missing = [k for k in ("engine", "gaps") if not t.get(k)]
        if missing:
            return refuse(f"a proof task names its {' and '.join(missing)} explicitly (the CLI's defaults are JBMC and "
                          "strict, and a claim never rests on a default)")
    artifacts = artifact_sources(folder, target, revisions)
    if isinstance(artifacts, str):
        return refuse(artifacts, stage="prepare")
    controls = controls_of(target, t, revisions)
    if t["kind"] == "replay":
        kinds = {c["kind"] for c in controls}
        missing = [k for k in ("oracle", "driver") if k not in kinds]
        if missing:
            return refuse(f"a replay needs an independent oracle and a driver among its controls, and it has no "
                          f"{' or '.join(missing)}")
    try:
        claim = source_claim(folder, target, t, controls)
    except ClaimError as e:
        return refuse(str(e), stage="claim")
    prep = target["preparation"]
    return TaskPlan(
        example=example["id"], task=task, kind=t["kind"], relation=t["relation"], target=t["target"],
        revisions=revisions, claim=claim, prerequisites=tuple(t.get("requires", [])), artifacts=artifacts,
        tools=tools_of(t, prep["route"], prep, controls, artifacts), engine=t.get("engine"), gaps=t.get("gaps"),
        expected=t.get("expected"), outputs={"receipts": f"receipts/{task}"}, folder=str(folder.resolve()),
        network=prep["route"] in ("published-artifact", "upstream-build"))



# -- Readiness: independent milestones per task, and the summaries derived from them. None is a proof verdict.

MILESTONES = ("provenanceLocked", "artifactsPrepared", "oracleValidated", "claimFrozen", "capabilityProbed",
              "attemptRecorded")
# The milestones a reproducible scaffold needs: both revisions materialize, the oracle executes, the claim is frozen.
SCAFFOLD = ("provenanceLocked", "artifactsPrepared", "oracleValidated", "claimFrozen")
SUMMARIES = ("catalogued", "partial", "scaffolded", "executable", "blocked")
# An observed blocker of these kinds stops the proof on a sound scaffold (the task is blocked); one of the others
# (provenance, a build, the oracle, the replay) leaves the scaffold itself partial.
CAPABILITY_KINDS = ("java-semantics", "input-construction", "verifier-bug", "resources")
CONFIDENT = ("checked-upstream", "reproduced")
RECEIPTS = "receipts"
# Beside each attempt's result.json, what it ran under: the TaskPlan, its inputs (attempt_inputs()) and their key.
PLAN_RECORD = "plan.json"


def attempt_inputs(plan):
    """Everything an attempt at `plan` depends on that is known before preparation: the task, its frozen source-level
    claim (claim file, controls and models hashed), each revision's artifact source, and the adapter sources by
    content. Another of any of them makes an earlier attempt's evidence inapplicable; the engine and a timeout are
    strategies, left out (another attempt at the same claim)."""
    adapters = sorted({a for entry in plan.artifacts for a in entry.get("adapters", [])})
    hashes = []
    for name in adapters:
        try:
            hashes.append(hashed(plan.folder, name))
        except ClaimError:
            hashes.append({"path": name, "sha256": None})
    return {"example": plan.example, "task": plan.task, "kind": plan.kind, "relation": plan.relation,
            "target": plan.target, "revisions": list(plan.revisions), "claim": plan.claim,
            "artifacts": [dict(a) for a in plan.artifacts], "adapters": hashes}


def plan_record(plan):
    """What ingestion writes beside an attempt's result.json (PLAN_RECORD): the plan it ran under, its inputs and
    their key, which readiness compares with the current plan's to tell a current receipt from a stale one."""
    inputs = json.loads(json.dumps(attempt_inputs(plan)))
    return {"plan": json.loads(json.dumps(plan.as_dict())), "inputs": inputs, "key": canonical_digest(inputs)}


def inputs_key(plan):
    return plan_record(plan)["key"]


def attempts(folder):
    """Every attempt recorded in the example's folder, receipts/<task>/<attempt>/result.json with its plan.json, in
    path order. Read-only. Each is a dict: task, attempt, path, inputsKey, artifacts (the revisions' sources it ran
    on), prepared (the revisions its claim binds to prepared artifacts), execution (how it ended: its `status`), status
    (the conclusion's), expectation, and
    `problem`, why it can't count (not JSON, not format 2, no plan.json, filed under another task), or None. The
    receipt's schemas are checked when ingestion publishes it (W2); this reads what it needs and trusts no more."""
    import result_format
    root = Path(folder) / RECEIPTS
    out = []
    for path in sorted(root.glob("*/*/result.json")) if root.is_dir() else ():
        if path.parent.name.startswith("."):
            continue  # an attempt still being published (workflow_ingest.publish() renames it into place)
        entry = {"task": path.parent.parent.name, "attempt": path.parent.name,
                 "path": path.relative_to(folder).as_posix(), "inputsKey": None, "artifacts": [], "adapters": [],
                 "prepared": [],
                 "execution": None, "status": None, "expectation": None, "problem": None}
        out.append(entry)
        try:
            document = json.loads(path.read_text())
            if result_format.stored_format(document) != 2:
                entry["problem"] = "not a format-2 receipt"
                continue
            record = json.loads((path.parent / PLAN_RECORD).read_text())
        except FileNotFoundError:
            entry["problem"] = f"no {PLAN_RECORD} beside it: what it ran under is unknown"
            continue
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            entry["problem"] = f"unreadable: {e}"
            continue
        target = (document.get("claim") or {}).get("target") or {}
        conclusion = document.get("conclusion") or {}
        entry.update(inputsKey=record.get("key"), artifacts=(record.get("inputs") or {}).get("artifacts", []),
                     adapters=(record.get("inputs") or {}).get("adapters", []),
                     prepared=sorted({d["revision"] for d in target.get("dependencies", [])}),
                     execution=((document.get("attempt") or {}).get("execution") or {}).get("status"),
                     status=conclusion.get("status"),
                     expectation=conclusion.get("expectation"))
        if target.get("task") != entry["task"]:
            entry["problem"] = f"its claim names task {target.get('task')!r}, and it is filed under {entry['task']!r}"
    return out


def milestone(reached, evidence):
    """One milestone: reached (True, False, or None where it doesn't apply to the task's kind) and why."""
    return {"reached": reached, "evidence": evidence}


def provenance(folder, target, task, plan):
    names = revisions_of(target, task)
    confidence = target["identity"].get("sourceConfidence", "researched")
    unresolved = target["history"].get("unresolved", [])
    if confidence not in CONFIDENT:
        return milestone(False, f"the revisions are {confidence}, not checked against upstream "
                                f"(identity.sourceConfidence)")
    if isinstance(plan, Unsupported) and plan.stage == "prepare":
        return milestone(False, plan.reason)
    defined = target["history"]["revisions"]
    for name in names:
        source = defined[name]["mutant"]["base"] if "mutant" in defined[name] else name
        fixture = defined[source].get("fixture")
        resolved = (Path(folder) / fixture).resolve() if fixture else None
        if fixture and not (resolved.is_dir() and Path(folder).resolve() in resolved.parents):
            return milestone(False, f"revision {name}: its fixture sources {fixture} are not a directory in the folder")
    said = f"{', '.join(names)}: immutable and {confidence}"
    if unresolved:
        said += f"; open provenance questions: {'; '.join(unresolved)}"
    return milestone(True, said)


def current_attempts(plan, recorded):
    key = inputs_key(plan)
    return [a for a in recorded if a["task"] == plan.task and not a["problem"] and a["inputsKey"] == key]


def prepared(plan, recorded):
    """Each revision of the plan prepared by some attempt of any task, from the same artifact source and adapter
    sources."""
    adapters = attempt_inputs(plan)["adapters"]
    missing = []
    for entry in plan.artifacts:
        same = json.dumps(dict(entry), sort_keys=True)
        if not any(entry["revision"] in a["prepared"] and not a["problem"] and a["adapters"] == adapters
                   and any(json.dumps(x, sort_keys=True) == same for x in a["artifacts"]) for a in recorded):
            missing.append(entry["revision"])
    if missing:
        return milestone(False, f"no receipt binds {', '.join(missing)} to prepared artifacts from its current source")
    return milestone(True, f"{', '.join(plan.revisions)}: prepared and bound in a receipt")


def oracle(folder, example, target, plan, recorded):
    """Each revision of the plan replayed by a replay task covering it, whose current attempt completed with the
    oracle's expected outcome on every side (W2 sets a replay's expectation to `yes` only then)."""
    missing = []
    for name in plan.revisions:
        replays = [t for t in target["tasks"] if t["kind"] == "replay" and name in revisions_of(target, t)]
        ok = False
        for t in replays:
            p = plan if t["id"] == plan.task else plan_task(folder, example, target, t["id"])
            if isinstance(p, Unsupported):
                continue
            if any(a["execution"] == "completed" and a["expectation"] == "yes" for a in current_attempts(p, recorded)):
                ok = True
                break
        if not ok:
            why = (f"no current validated replay of {', '.join(t['id'] for t in replays)}" if replays
                   else "no replay task covers it")
            missing.append(f"{name} ({why})")
    if missing:
        return milestone(False, f"not validated: {'; '.join(missing)}")
    return milestone(True, f"{', '.join(plan.revisions)}: replayed in separate JVMs and the oracle agreed")


def task_blockers(folder, target, task):
    """The sidecar's blockers of this task, each with whether its packet file is there."""
    out = []
    for b in target.get("handoff", {}).get("blockers", []):
        if b.get("task") != task["id"]:
            continue
        packet = b.get("packet")
        present = None
        if packet:
            try:
                inside(folder, packet)
                present = True
            except ClaimError:
                present = False
        out.append({**b, "packetPresent": present})
    return out


def task_readiness(folder, example, target, task_id, recorded=None):
    """A task's readiness milestones (MILESTONES) and the summary derived from them, from the sidecar, its files and
    the folder's receipts alone: offline and read-only. The summary is catalogued (no preparation), partial (a
    scaffold milestone missing, or an observed provenance, build, oracle or replay blocker), scaffolded (a
    reproducible scaffold, its proof support not yet probed), executable (probed by an attempt, no observed capability
    blocker) or blocked (an observed capability blocker on a sound scaffold). None of them is a proof verdict: the
    claim's status is its receipts'."""
    folder = Path(folder)
    t = next(x for x in target["tasks"] if x["id"] == task_id)
    recorded = attempts(folder) if recorded is None else recorded
    plan = plan_task(folder, example, target, task_id)
    blockers = task_blockers(folder, target, t)
    observed = [b for b in blockers if b["observed"] and b["packetPresent"] is not False]
    replay = t["kind"] == "replay"
    m = {"provenanceLocked": provenance(folder, target, t, plan)}
    if isinstance(plan, Unsupported):
        why = f"the task doesn't plan: {plan.reason}"
        m.update(artifactsPrepared=milestone(False, why), oracleValidated=milestone(False, why),
                 claimFrozen=milestone(None if replay else False, why),
                 capabilityProbed=milestone(None if replay else False, why), attemptRecorded=milestone(False, why))
        current = []
    else:
        current = current_attempts(plan, recorded)
        stale = [a["path"] for a in recorded if a["task"] == task_id and a not in current]
        m["artifactsPrepared"] = prepared(plan, recorded)
        m["oracleValidated"] = oracle(folder, example, target, plan, recorded)
        m["claimFrozen"] = (milestone(None, "a replay checks concrete controls, and has no claim to freeze") if replay
                            else milestone(True, f"source-level claim {plan.claim['key']} "
                                                 f"({plan.claim['file']}), bounds resolved"))
        if replay:
            m["capabilityProbed"] = milestone(None, "a replay runs no verifier")
        elif observed:
            m["capabilityProbed"] = milestone(True, "observed: " + "; ".join(b["summary"] for b in observed))
        elif any(a["execution"] == "completed" for a in current):
            m["capabilityProbed"] = milestone(True, "a current attempt ran the verifier to completion")
        else:
            predicted = [b["summary"] for b in blockers if not b["observed"]]
            m["capabilityProbed"] = milestone(False, "not probed" + (f"; predicted only: {'; '.join(predicted)}"
                                                                      if predicted else ""))
        m["attemptRecorded"] = (milestone(True, ", ".join(a["path"] for a in current)) if current else
                                milestone(False, "no receipt for the current claim and inputs"
                                                 + (f"; stale or unreadable: {', '.join(stale)}" if stale else "")))
    if "preparation" not in target:
        summary = "catalogued"
    elif any(not m[k]["reached"] and m[k]["reached"] is not None for k in SCAFFOLD) or \
            any(b["kind"] not in CAPABILITY_KINDS for b in observed):
        summary = "partial"
    elif any(b["kind"] in CAPABILITY_KINDS for b in observed):
        summary = "blocked"
    elif not replay and m["capabilityProbed"]["reached"]:
        summary = "executable"
    else:
        summary = "scaffolded"
    return {"task": task_id, "summary": summary, "milestones": m,
            "blockers": [{k: b[k] for k in ("kind", "observed", "summary", "packet", "packetPresent") if k in b}
                         for b in blockers],
            "receipts": [a["path"] for a in current]}


def readiness(folder, example, target):
    """The target's readiness: each task's (task_readiness()) and one summary for discovery. Catalogued without a
    preparation or tasks; partial while any task is (or catalogued); blocked when any task is blocked by an observed
    capability gap; executable when every proof task is; scaffolded otherwise."""
    recorded = attempts(folder)
    tasks = {t["id"]: task_readiness(folder, example, target, t["id"], recorded) for t in target["tasks"]}
    summaries = {r["summary"] for r in tasks.values()}
    proofs = [tasks[t["id"]]["summary"] for t in target["tasks"] if t["kind"] != "replay"]
    if "preparation" not in target or not tasks:
        summary = "catalogued"
    elif summaries & {"partial", "catalogued"}:
        summary = "partial"
    elif "blocked" in summaries:
        summary = "blocked"
    elif proofs and all(s == "executable" for s in proofs):
        summary = "executable"
    else:
        summary = "scaffolded"
    return {"summary": summary, "tasks": tasks,
            "unreadable": [{"path": a["path"], "problem": a["problem"]} for a in recorded if a["problem"]]}

def ingest(plan, prepared, records, out):
    """Validates the raw records of one attempt at `plan`, binds them to the prepared artifacts (`prepared`, by
    revision name) and publishes one format-2 receipt under `out`, earlier attempts kept: a Receipt, or
    Unsupported. workflow_ingest.py (W2) says how the claim is bound and what each attempt's receipt holds."""
    from targets import workflow_ingest
    return workflow_ingest.publish(plan, prepared, records, out)


def handoff(folder, example, target, task):
    """The task's handoff packet, for an agent that continues it without rediscovery: its immutable inputs with their
    hashes, the exact commands, its current receipts, the next prerequisite and one recommended action, and for an
    observed gap the brief's capability-gap packet. Predicted and observed gaps stay apart. Offline, read-only: a
    dict, or Unsupported."""
    return Unsupported("handoff", WORKFLOW, "the handoff export is Phase 0's stub until the workflow stream's W3 replaces it",
                       stage="handoff")


def project(folder, example, target):
    """The example's row in the index (examples/index.json's `target`): its family, role, readiness, claim statuses
    and gaps, for find.py. Phase 0 projects what the sidecar states; readiness, claim statuses and observed gaps are
    derived from receipts by W4, and stay None until then."""
    identity = target["identity"]
    return {
        "family": identity["family"],
        "role": identity["role"],
        "case": identity["case"],
        "tasks": [t["id"] for t in target["tasks"]],
        "readiness": None,
        "claims": None,
        "gaps": sorted({b["kind"] for b in target.get("handoff", {}).get("blockers", []) if b["observed"]}),
        "predictedGaps": sorted({b["kind"] for b in target.get("handoff", {}).get("blockers", []) if not b["observed"]}),
        "unsupported": "readiness and claim statuses: Phase 0's stub until the workflow stream's W4 derives them",
    }

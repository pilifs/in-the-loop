"""Task planning, attempt ingestion and the index projection: the workflow stream's side of the interfaces
(interfaces.py) of llm-dlc/loops/example-targets.md. plan_task() resolves a task from the sidecar and its claim file
alone (W1). ingest() and handoff() fail closed with the named Unsupported result until the workflow stream replaces
them (W2, W3); project() reports only what target.json states and derives no readiness until W4 does. Signatures are
frozen.

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


def ingest(plan, prepared, records, out):
    """Validates the raw records of one attempt at `plan`, binds them to the prepared artifacts (`prepared`, by
    revision name) and publishes one format-2 receipt under `out`, earlier attempts kept: a Receipt, or
    Unsupported."""
    return Unsupported("ingest", WORKFLOW, "attempt ingestion is Phase 0's stub until the workflow stream's W2 replaces it",
                       stage="ingest")


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

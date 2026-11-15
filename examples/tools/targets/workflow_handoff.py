"""The handoff packet and the gap inventory (W3 of llm-dlc/loops/example-targets-workflow.md): what an agent needs to
continue one task of an external example without rediscovering its revisions, claim, oracle or blocker, and the
projection of every target's gaps that Phase 5's v1 ranking reads. Offline and read-only: it reads the sidecar, the
files it names and the folder's receipts, and runs nothing.

packet(folder, example, target, task) is workflow.handoff()'s dict:
  inputs        every immutable file the task rests on, by path, role and sha256: the sidecar, the claim file, the
                controls, models, plan and contracts it froze, the files of the folder its claim file cites in its
                text (cited_by_claim()), the adapters, a mutant's patch, each fixture revision's sources (the sha256
                of their listing, with their git tree id), and the gap packets with the records they cite
  commands      the exact commands: the offline plan, then the attempt (a replay runs inline, a proof is queued)
  receipts      the current receipts of the task's claim and inputs (stale and unreadable ones apart)
  prerequisites each prerequisite task, satisfied or not, and nextPrerequisite, the first that isn't
  next          one recommended action, an exact command, and nextReason, why it is the one; for a task an observed
                refusal blocks (a gap packet stating `refusal`), the check that reruns it (workflow_refusal.py N T),
                with the gap id and the inventory's closure test in nextReason
  gaps          each blocker the sidecar records for the task, or for the whole target (one naming no task; a
                capability one only on a task that runs the verifier): kind, observed (true: a probe or attempt
                produced it; false: predicted, a hypothesis until a probe reaches it), class (capability: a library limit;
                scaffold: provenance, a build, the oracle or the replay, which leave the scaffold partial), summary,
                the summary's `recorded` date and a later dated `note` where the sidecar gives them (the summary is
                kept as written), and for an observed one with its packet file the brief's capability-gap packet (gap_packet())
  rules         what continuing may not change: the claim stays as it is; a narrower kernel is a separate task

inventory(rows) groups the observed and predicted gaps of many targets by gap id (a gap packet's diagnostic ids, the
JDK suffix dropped, else the blocker's kind and summary), ranked by the distinct families and the blocked obligations
(case, task and claim) each blocks, never by raw case counts. A priority is an engineering aid, not evidence.

Run as a script: `workflow_handoff.py handoff NNN TASK` prints one packet, `workflow_handoff.py inventory` the
inventory of every example with a target sidecar, and `inventory --markdown` the page examples/gap-inventory.md,
which build.py's render_index() also writes, so `build.py --index-only` and `--render-only` rewrite it with the router.
"""

import hashlib
import json
import re
import shlex
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # examples/tools, for `targets` and build.py

from targets import workflow, workflow_refusal  # noqa: E402
from targets.interfaces import Unsupported  # noqa: E402

SCHEMA = "example-target-handoff/v1"
INVENTORY_SCHEMA = "example-target-gap-inventory/v1"
# The fields of the brief's capability-gap packet (example-targets.md, "The capability-gap packet"). A packet file may
# state any of them as top-level keys, which then stand as written; the rest are derived from a recorded verifier run
# where the file is one ({"record": {"kind": "verifier", "argv", "stdout", "identities", ...}}), and listed under
# `missing` where neither gives them.
PACKET_FIELDS = ("verifier", "command", "diagnostic", "artifacts", "reproducer", "semantics", "why", "needs",
                 "module", "related", "findings", "closure", "strategies")
# The likely owner of a gap, by the checker's gap kind (lib/src/bmc/gaps.rs) or the blocker's kind. A suggestion for
# the packet, never a decision.
GAP_MODULES = {
    "jdk-constructor": "lib/src/models.rs",
    "jdk-void-method": "lib/src/models.rs",
    "jdk-reference-method": "lib/src/models.rs",
    "jdk-primitive-method": "lib/src/models.rs",
    "jdk-static-method": "lib/src/models.rs",
    "string-conversion": "lib/src/bmc/mod.rs",
    "class-initializer": "lib/src/bmc/mod.rs",
    "missing-body": "lib/src/bmc/mod.rs",
    "invokedynamic": "lib/src/bmc/mod.rs",
    "monitor": "lib/src/bmc/mod.rs",
}
KIND_MODULES = {
    "java-semantics": "lib/src/models.rs",
    "input-construction": "lib/src/construction.rs",
    "verifier-interface": "lib/src/main.rs (the command line, such as equivalence's one --classpath)",
    "build-or-dependency": "examples/tools/targets/runtime.py (preparation), or the case's preparation entry",
    "replay": "examples/tools/targets/runtime.py (replay), or the case's driver",
    "source-provenance": "the case's history (target.json)",
    "oracle-ambiguity": "the case's oracle and task statement",
    "resources": "the task's bounds and the job's estimate",
    "verifier-bug": "lib/ (the module the diagnostic names)",
}
MODULE_NOTE = ("a model runs in the checker and in the interpreter alike (lib/src/models.rs); a contract under "
               "--gaps advised (lib/src/gap_contracts.rs) closes it only at the trusted level, which this claim keeps "
               "apart; the gap table is lib/src/bmc/gaps.rs")
RULES = (
    "The claim stays as it is: its domain, observations, assumptions, bounds and allowed change are frozen (key "
    "{key}). A semantically changed proposal is a new claim with a parent link, for review; this one stays unresolved.",
    "A narrower kernel or a surrogate is a separate task with its own claim and explicit correspondence work; it "
    "never discharges this task's obligation without a checked connection.",
    "A gap closes only when this task's unchanged claim is rerun with the extended implementation and its new receipt "
    "decides it; a narrower substitute is useful and doesn't close it.",
    "Proofs are queued (the submit command), never run inline; a replay runs inline. Exit 1, malformed output, a kill "
    "or a timeout is no violation, and a one-sided replay is not reproduced.",
)
BUILD = "python3 examples/tools/build.py"
PIPELINE = "python3 verification/pipeline.py"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def tree_sha256(directory):
    """The sha256 of a directory's files: of its sorted `path sha256` lines (__pycache__ left out)."""
    root = Path(directory)
    lines = [f"{p.relative_to(root).as_posix()} {workflow.file_sha256(p)}"
             for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts]
    return sha256_bytes("\n".join(lines).encode())


def strip_jdk(gap_id):
    """A checker gap id without its JDK suffix (`...@jdk-25.0.5`): the same gap on another JDK build."""
    return re.sub(r"@jdk-[^@]*$", "", gap_id)


# -- the commands


def plan_command(example, task):
    return f"{BUILD} --plan {example['id']} --task {task}"


def run_command(example, task):
    return f"{BUILD} {example['id']} --task {task}"


def submit_command(example, t, key=None):
    title = f"example {example['id']} task {t['id']}: the {t['relation']} {t['kind']} of {t['target']}"
    description = (f"Runs task {t['id']} of example {example['id']} through the target route of build.py: its frozen "
                   f"claim{f' {key}' if key else ''}, engine {t.get('engine')}, gaps {t.get('gaps')}, expected "
                   f"{t.get('expected') or 'none stated'}. The receipt is ingested by workflow.ingest(); an "
                   "unresolved result stays unresolved.")
    return (f"{PIPELINE} submit --example {example['id']} --task {t['id']} --title {shlex.quote(title)} "
            f"--description {shlex.quote(description)}")


def refusal_command(example, task):
    """The check that reruns a task an observed refusal blocks, unchanged, and passes only at the recorded refusal."""
    return f"python3 examples/tools/targets/workflow_refusal.py {example['id']} {task}"


def attempt_command(example, t, key=None):
    """How one attempt at the task runs: a replay inline (small JVM runs), a proof through the pipeline."""
    return run_command(example, t["id"]) if t["kind"] == "replay" else submit_command(example, t, key)


# -- inputs and receipts


CITED = re.compile(r"(?<![\w./-])((?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]+)")  # a relative path with a directory and an extension


def cited_by_claim(folder, name):
    """The files of the example's folder the claim file names in its text (a statement, an assumption's basis, a
    note: 105's `records/pow-gaps.json`), sorted: the user's review item 6 (2026-11-15), so a session handed the
    packet has each by sha256. A path that isn't a file inside the folder (a repository page such as lib/README.md)
    is no input of the task. `$schema` is the claim's format, not something it rests on."""
    try:
        stated = json.loads(workflow.inside(folder, name).read_text())
    except (workflow.ClaimError, OSError, ValueError):
        return []
    if isinstance(stated, dict):
        stated.pop("$schema", None)

    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for v in value.values():
                yield from strings(v)
        elif isinstance(value, list):
            for v in value:
                yield from strings(v)

    found = set()
    for text in strings(stated):
        for path in CITED.findall(text):
            try:
                workflow.inside(folder, path)
            except workflow.ClaimError:
                continue
            found.add(path)
    return sorted(found - {name})


def inputs_of(folder, example, target, t, plan):
    """The task's immutable inputs, each {path, role, sha256}, sorted by path."""
    folder = Path(folder)
    found = {}

    def add(path, role, sha256, **extra):
        if path not in found and sha256:
            found[path] = {"path": path, "role": role, "sha256": sha256, **extra}

    add("target.json", "sidecar", workflow.file_sha256(folder / "target.json"))
    if (folder / "example.json").is_file():
        add("example.json", "router entry", workflow.file_sha256(folder / "example.json"))
    if isinstance(plan, Unsupported):
        if t.get("claim"):
            try:
                add(t["claim"], "claim", workflow.hashed(folder, t["claim"])["sha256"])
            except workflow.ClaimError:
                pass
        return found
    claim = plan.claim
    if claim.get("file"):
        add(claim["file"], "claim", claim["sha256"])
    for c in claim.get("controls", []):
        add(c["path"], f"control: {c['kind']}", c["sha256"])
    for m in claim.get("models", []):
        add(m["path"], "model", m["sha256"])
    for key in ("plan", "contracts"):
        if claim.get(key):
            add(claim[key]["path"], key, claim[key]["sha256"])
    if claim.get("file"):
        for name in cited_by_claim(folder, claim["file"]):
            add(name, "cited by the claim", workflow.file_sha256(folder / name))
    defined = target["history"]["revisions"]
    for entry in plan.artifacts:
        patch = entry.get("mutant", {}).get("patch")
        if patch:
            add(patch["path"], "mutant patch", patch["sha256"])
        for name in entry.get("adapters", []):
            try:
                add(name, "adapter", workflow.hashed(folder, name)["sha256"])
            except workflow.ClaimError:
                pass
        name = entry["revision"]
        base = defined[name]["mutant"]["base"] if "mutant" in defined[name] else name
        fixture = defined[base].get("fixture")
        if fixture and (folder / fixture).is_dir():
            from targets import workflow_ingest
            add(fixture, "fixture sources", tree_sha256(folder / fixture),
                tree=workflow_ingest.git_tree_id(folder / fixture))
    return found


def receipts_of(folder, plan, recorded, task):
    """The task's current receipts (its claim and inputs unchanged), and the stale and unreadable ones apart."""
    current = [] if isinstance(plan, Unsupported) else workflow.current_attempts(plan, recorded)
    paths = {a["path"] for a in current}

    def entry(a):
        out = {k: a[k] for k in ("path", "attempt", "execution", "status", "expectation")}
        out["sha256"] = workflow.file_sha256(Path(folder) / a["path"])
        try:
            document = json.loads((Path(folder) / a["path"]).read_text())
            out["engine"] = (document.get("attempt") or {}).get("engine")
            out["label"] = (document.get("conclusion") or {}).get("label")
        except (OSError, ValueError):
            pass
        return out

    mine = [a for a in recorded if a["task"] == task]
    return ([entry(a) for a in current],
            [{**entry(a), "why": a["problem"] or "its claim or inputs have changed since"} for a in mine
             if a["path"] not in paths])


# -- gaps


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


def recorded_scan(packet_path, document):
    """What a recorded verifier run in a packet file gives: its command, verifier and artifact identities, and the
    gaps its output lists, and the files it cites (`_cited`)."""
    record = (document or {}).get("record") or {}
    if record.get("kind") != "verifier":
        return {}
    out = {}
    identities = dict(record.get("identities") or {})
    tool = identities.pop("jvmcontract", None)
    # commit and libTree: what the binary was built from, which run_verifier names for a pipeline job's own build only.
    out["verifier"] = {"jvmcontract": tool, "commit": identities.pop("commit", None)}
    if "libTree" in identities:
        out["verifier"]["libTree"] = identities.pop("libTree")
    if record.get("argv"):
        out["command"] = list(record["argv"])
    if identities:
        out["artifacts"] = identities
    diagnostic, sites = [], []
    for stream in ("stdout", "stderr"):
        name = record.get(stream)
        if not name:
            continue
        cited = Path(packet_path).parent / name
        if cited.is_file():
            out.setdefault("_cited", []).append((cited, stream))
        if stream == "stdout":
            scan = read_json(cited)
            for g in (scan or {}).get("gaps", []) if isinstance(scan, dict) else []:
                diagnostic.append({k: g.get(k) for k in ("id", "kind", "call", "sites", "approximation")})
                sites.extend(g.get("sites") or [])
            if isinstance(scan, dict) and scan.get("jdk"):
                out["jdk"] = scan["jdk"]
    if diagnostic:
        out["diagnostic"] = diagnostic
        out["callPath"] = sorted(set(sites))
    out["revision"] = record.get("revision")
    return out


def gap_packet(folder, example, target, t, plan, blocker, found, receipts, related):
    """The brief's capability-gap packet of one observed blocker: case, task and claim, the verifier's identity, the
    minimal command and its diagnostic, the artifact identities, the reproducer on the original call path, the Java
    semantics needed and why the claim needs them, what it needs (inputs, exceptions, observations, bounds), the
    likely module, related tasks and findings, the closure test, and the strategies tried with the next bounded
    action. A field the packet file neither states nor gives from a recorded run is listed under `missing`."""
    folder = Path(folder)
    name = blocker.get("packet")
    out = {"file": name, "sha256": None, "present": False}
    document = None
    if name:
        try:
            path = workflow.inside(folder, name)
            out.update(sha256=workflow.file_sha256(path), present=True)
            found.setdefault(name, {"path": name, "role": "gap packet", "sha256": out["sha256"]})
            document = read_json(path)
        except workflow.ClaimError:
            path = None
    claim = None if isinstance(plan, Unsupported) else plan.claim
    out["case"] = target["identity"]["case"]
    out["task"] = t["id"]
    out["claim"] = ({"file": claim.get("file"), "sha256": claim.get("sha256"), "key": claim.get("key")} if claim
                    else {"file": t.get("claim"), "refused": plan.describe()})
    derived = recorded_scan(path, document) if out["present"] else {}
    for cited, stream in derived.pop("_cited", []):
        try:
            rel = cited.resolve().relative_to(folder.resolve()).as_posix()
        except ValueError:
            continue
        found.setdefault(rel, {"path": rel, "role": f"gap record ({stream})", "sha256": workflow.file_sha256(cited)})
    if "verifier" in derived:
        out["verifier"] = derived["verifier"]
    if "command" in derived:
        out["command"] = derived["command"]
    if "artifacts" in derived:
        out["artifacts"] = derived["artifacts"]
    diagnostic = derived.get("diagnostic")
    if diagnostic:
        out["diagnostic"] = diagnostic
        out["reproducer"] = {
            "target": t["target"], "revision": derived.get("revision") or (plan.revisions[0] if claim else None),
            "callPath": derived["callPath"], "command": derived.get("command"),
            "note": "the scan of the original method in the original artifact: no slice or surrogate"}
        out["semantics"] = [{"call": g["call"], "gap": strip_jdk(g["id"] or ""), "kind": g["kind"],
                             "sites": g["sites"], "today": g["approximation"]} for g in diagnostic]
        calls = ", ".join(g["call"] for g in diagnostic if g.get("call"))
        which = f" ({claim.get('key')})" if claim else ""
        out["why"] = (f"the gap scan finds that a strict proof of the claim{which} "
                      f"on {t['target']} reaches {calls} (at {', '.join(derived['callPath'])}), and strict refuses each "
                      "by name: the claim can't be decided until the checker implements them as the JVM does, so the "
                      f"task's expected outcome is {t.get('expected') or 'not stated'} and none is a verdict")
        kinds = sorted({g["kind"] for g in diagnostic if g.get("kind")})
        modules = sorted({GAP_MODULES.get(k, KIND_MODULES.get(blocker["kind"], "lib/")) for k in kinds})
        out["module"] = {"likely": modules, "note": MODULE_NOTE if any(k.startswith("jdk-") for k in kinds) else None}
    elif blocker["kind"] in KIND_MODULES:
        out["module"] = {"likely": [KIND_MODULES[blocker["kind"]]], "note": None}
    if claim:
        out["needs"] = {"inputs": claim.get("assume") or "the task's whole parameter domain (no assume)",
                        "exceptions": claim.get("throws") or [], "observations": claim.get("observations") or [],
                        "bounds": claim.get("bounds") or {}, "nullable": claim.get("nullable") or [],
                        "allowedChange": claim.get("allowedChange")}
    out["related"] = related
    out["findings"] = [blocker["finding"]] if blocker.get("finding") else []
    if claim:
        out["closure"] = {
            "command": attempt_command(example, t, claim.get("key")),
            "check": (f"the unchanged claim {claim.get('key')} rerun on the same artifacts with the extended checker: "
                      "its receipt decides it (established or refuted, not vacuous) and its reasons name none of "
                      + (", ".join(strip_jdk(g["id"]) for g in diagnostic if g.get("id")) if diagnostic else
                         "this packet's gaps")
                      + "; a narrower task's receipt doesn't close it")}
    tried = [{"by": "a recorded verifier run", "command": derived.get("command"), "file": name}] if derived else []
    tried += [{"by": f"attempt {r['attempt']}", "engine": r.get("engine"), "execution": r["execution"],
               "status": r["status"], "label": r.get("label")} for r in receipts]
    out["strategies"] = tried
    authored = document if isinstance(document, dict) else {}
    for field in PACKET_FIELDS:
        if field in authored:
            out[field] = authored[field]
    out["missing"] = [f for f in PACKET_FIELDS if out.get(f) in (None, [], {}) and f not in ("related", "findings",
                                                                                             "strategies")]
    if out.get("verifier") and not out["verifier"].get("commit"):
        out["missing"].append("verifier.commit")
    return out


def gap_ids(gap):
    packet = gap.get("packet") or {}
    return sorted({strip_jdk(d["id"]) for d in packet.get("diagnostic") or [] if d.get("id")})


def gaps_of(folder, example, target, t, plan, found, receipts):
    """The task's blockers as the handoff's gaps, observed and predicted apart by `observed`, capability and scaffold
    apart by `class`."""
    blockers = workflow.task_blockers(folder, target, t)
    out = []
    for b in blockers:
        gap = {"kind": b["kind"], "observed": bool(b["observed"]),
               "class": "capability" if b["kind"] in workflow.CAPABILITY_KINDS else "scaffold",
               "summary": b["summary"], "finding": b.get("finding"), "packet": None}
        for k in ("recorded", "note"):  # the summary's date, and a later dated line (target.schema.json)
            if b.get(k):
                gap[k] = b[k]
        if b["observed"]:
            if b.get("packet") and b["packetPresent"] is False:
                gap["evidence"] = f"missing: {b['packet']} is not in the folder, so it doesn't count as observed"
            related = [{"task": o["task"], "summary": o["summary"]}
                       for o in target.get("handoff", {}).get("blockers", [])
                       if o.get("task") not in (None, t["id"])  # another task's; a target blocker is this one's
                       and (o.get("packet") and o.get("packet") == b.get("packet"))]
            gap["packet"] = gap_packet(folder, example, target, t, plan, b, found, receipts, related)
        else:
            gap["evidence"] = "predicted: a hypothesis until a probe reaches it"
        out.append(gap)
    return out


# -- prerequisites and the next action


def satisfied(folder, example, target, task_id, recorded):
    """Whether a prerequisite task is done: a current attempt that completed, and for a replay one whose oracle
    agreed on every side (expectation yes)."""
    t = next(x for x in target["tasks"] if x["id"] == task_id)
    plan = workflow.plan_task(folder, example, target, task_id)
    if isinstance(plan, Unsupported):
        return False, f"it doesn't plan: {plan.describe()}"
    current = workflow.current_attempts(plan, recorded)
    if t["kind"] == "replay":
        ok = any(a["execution"] == "completed" and a["expectation"] == "yes" for a in current)
        return ok, ("a current replay completed and the oracle agreed" if ok
                    else "no current replay that completed with the oracle agreeing")
    ok = any(a["execution"] == "completed" for a in current)
    return ok, "a current attempt completed" if ok else "no current attempt that completed"


def prerequisite_order(target, task_id, seen=None):
    """The task's prerequisites, depth first, each before what needs it (the sidecar has no cycle)."""
    seen = [] if seen is None else seen
    t = next(x for x in target["tasks"] if x["id"] == task_id)
    for p in t.get("requires", []):
        if p not in seen:
            prerequisite_order(target, p, seen)
            seen.append(p)
    return seen


def refusal_gaps(folder, target, t, capability):
    """The task's observed capability gaps whose packet states a refusal workflow_refusal.py checks, each with its
    prediction. A malformed packet predicts nothing here: workflow_refusal.py reports it when run."""
    try:
        found = workflow_refusal.predictions(folder, target, t["id"])
    except (workflow_refusal.PredictionError, workflow.ClaimError, OSError, ValueError):
        return []
    by_packet = {p["packet"]: p for p in found}
    return [(g, by_packet[g["packet"]["file"]]) for g in capability
            if g.get("packet") and g["packet"].get("file") in by_packet]


def next_action(folder, example, target, t, plan, prerequisites, gaps, receipts, recorded):
    """One recommended action, an exact command, and why it is the one."""
    key = None if isinstance(plan, Unsupported) else plan.claim.get("key")
    if isinstance(plan, Unsupported):
        return plan_command(example, t["id"]), f"the task doesn't plan ({plan.describe()}): its plan shows what is missing"
    waiting = next((p for p in prerequisites if not p["satisfied"]), None)
    if waiting:
        p = next(x for x in target["tasks"] if x["id"] == waiting["task"])
        return (attempt_command(example, p),
                f"prerequisite {p['id']} comes first: {waiting['why']}")
    evidenced = [g for g in gaps if g["observed"] and "evidence" not in g]
    scaffold = [g for g in evidenced if g["class"] == "scaffold"]
    if scaffold:
        return (run_command(example, t["id"]),
                f"an observed {scaffold[0]['kind']} blocker leaves the scaffold partial ({scaffold[0]['summary']}): "
                "rerun the attempt once its preparation or replay is fixed, the claim unchanged")
    capability = [g for g in evidenced if g["class"] == "capability"]
    refused = refusal_gaps(folder, target, t, capability)
    if refused:
        gap, prediction = refused[0]
        ids = ", ".join(gap_ids(gap)) or f"{gap['kind']}: {gap['summary']}"
        closure = (gap["packet"].get("closure") or {}).get("check") or "the gap packet's closure"
        return (refusal_command(example, t["id"]),
                f"blocked by the observed gap {ids} (ranked in examples/gap-inventory.md; packet "
                f"{prediction['packet']}, finding {prediction['finding'] or 'none'}). An ordinary attempt "
                f"({PIPELINE} submit) would end NOT AS EXPECTED: this check reruns the task, claim {key} unchanged, "
                f"and passes only while it stops at the recorded {prediction['stage']} refusal. The gap closes by the "
                f"inventory's closure test: {closure}. When this check fails because the refusal is gone, queue the "
                "ordinary attempt (commands[1]); until then the claim stays unresolved, its expected outcome "
                "unchanged, and a narrower kernel is a separate task")
    done = [r for r in receipts if r["execution"] == "completed"]
    if capability and not receipts:
        return (attempt_command(example, t, key),
                f"reproduce the observed {capability[0]['kind']} blocker as this task's own receipt: the attempt on "
                "the frozen claim records the refusal (expected unresolved, never a verdict)")
    if capability:
        return (attempt_command(example, t, key),
                f"blocked by an observed {capability[0]['kind']} gap ({capability[0]['summary']}): rerun this command "
                "once the gap packet's closure lands; until then the claim stays unresolved, and a narrower kernel "
                "is a separate task")
    if not done:
        return (attempt_command(example, t, key),
                "no current attempt has completed for this claim and these inputs"
                + ("" if t["kind"] == "replay" else ": proofs are queued, never run inline"))
    later = [x for x in target["tasks"]
             if x["id"] != t["id"] and not satisfied(folder, example, target, x["id"], recorded)[0]]
    if later:
        return (plan_command(example, later[0]["id"]),
                f"this task has its current receipt; the target's next task without one is {later[0]['id']}")
    stated = target.get("handoff", {}).get("next")
    return stated, "every task has its current receipt" + ("; the sidecar's handoff.next" if stated else "")


def packet(folder, example, target, task):
    """The handoff packet of one task (module docstring). The task must exist."""
    folder = Path(folder)
    t = next(x for x in target["tasks"] if x["id"] == task)
    recorded = workflow.attempts(folder)
    plan = workflow.plan_task(folder, example, target, task)
    found = inputs_of(folder, example, target, t, plan)
    current, stale = receipts_of(folder, plan, recorded, task)
    readiness = workflow.task_readiness(folder, example, target, task, recorded)
    prerequisites = []
    for p in prerequisite_order(target, task):
        ok, why = satisfied(folder, example, target, p, recorded)
        prerequisites.append({"task": p, "satisfied": ok, "why": why})
    gaps = gaps_of(folder, example, target, t, plan, found, current)
    nxt, reason = next_action(folder, example, target, t, plan, prerequisites, gaps, current, recorded)
    key = None if isinstance(plan, Unsupported) else plan.claim.get("key")
    commands = [plan_command(example, task), attempt_command(example, t, key)]
    identity = target["identity"]
    return {
        "schema": SCHEMA,
        "example": example["id"], "case": identity["case"], "family": identity["family"], "role": identity["role"],
        "task": {k: t.get(k) for k in ("id", "kind", "relation", "target", "expected", "engine", "gaps",
                                       "allowedChange")},
        "revisions": list(workflow.revisions_of(target, t)),
        "plan": ({"executable": False, "notExecuted": plan.describe()} if isinstance(plan, Unsupported) else
                 {"executable": True, "claim": {"file": plan.claim.get("file"), "sha256": plan.claim.get("sha256"),
                                                "key": key, "bounds": plan.claim.get("bounds")},
                  "artifacts": [dict(a) for a in plan.artifacts], "tools": plan.tools}),
        "inputs": [found[k] for k in sorted(found)],
        "commands": commands,
        "receipts": current,
        "staleReceipts": stale,
        "readiness": {"summary": readiness["summary"],
                      "milestones": {k: v["reached"] for k, v in readiness["milestones"].items()}},
        "prerequisites": prerequisites,
        "nextPrerequisite": next((p["task"] for p in prerequisites if not p["satisfied"]), None),
        "next": nxt,
        "nextReason": reason,
        "gaps": gaps,
        "rules": [r.format(key=key or "not frozen: the task doesn't plan") for r in RULES],
    }


# -- the inventory


def observed_run(folder, example, t, packet_):
    """What an observed obligation's packet file records of the run that observed it: the job, the seconds its
    attempt took, the semantics it says are missing, its closure check, and, when the packet states the refusal, the
    check that reruns the task predicting it (workflow_refusal.py). Empty for a packet that records no run."""
    name = packet_.get("file")
    if not name or not packet_.get("present"):
        return {}
    try:
        document = read_json(workflow.inside(Path(folder), name))
    except (workflow.ClaimError, OSError, ValueError):
        return {}
    if not isinstance(document, dict):
        return {}
    seen = document.get("observed") if isinstance(document.get("observed"), dict) else {}
    out = {"packet": name, "job": seen.get("job"), "seconds": seen.get("seconds"),
           "semantics": packet_.get("semantics") if isinstance(packet_.get("semantics"), str) else None,
           "closure": (packet_.get("closure") or {}).get("check")}
    if isinstance(document.get("refusal"), dict):
        out["check"] = refusal_command(example, t["id"])
    return out


def reproducer(obligations):
    """A gap's smallest reproducer: of its observed obligations whose packet states the refusal, the one whose
    recorded attempt took the fewest seconds (one that records none comes last), then by example and task. None
    when no observed obligation has a rerun check."""
    runs = [o for o in obligations if o["observed"] and o.get("check")]
    if not runs:
        return None
    best = min(runs, key=lambda o: (o.get("seconds") is None, o.get("seconds") or 0, o["example"], o["task"]))
    return {k: best.get(k) for k in ("example", "task", "claim", "packet", "job", "seconds", "check", "semantics",
                                     "closure")}


def inventory(rows):
    """The gaps of many targets, grouped and ranked for Phase 5's v1 list. `rows` are (folder, example, target)
    triples. Each group: its gap id (or the blocker's kind and summary), kind and class, whether any target observed
    it, the families, cases and blocked obligations (example, case, task, claim key, observed), and the likely modules
    and closure checks of its packets. Observed groups first, then by distinct families, then blocked obligations;
    `rank` is that order, from 1, and `reproducer` the smallest rerun of an observed obligation (reproducer()). An
    observed obligation also names its packet, the job that observed it and, when the packet states the refusal, the
    check that reruns it (observed_run())."""
    groups = {}
    for folder, example, target in rows:
        identity = target["identity"]
        for t in target["tasks"]:
            if not workflow.task_blockers(folder, target, t):
                continue
            p = packet(folder, example, target, t["id"])
            for gap in p["gaps"]:
                counted = gap["observed"] and "evidence" not in gap
                ids = gap_ids(gap) or [f"{gap['kind']}: {gap['summary']}"]
                for gap_id in ids:
                    g = groups.setdefault(gap_id, {"gap": gap_id, "kind": gap["kind"], "class": gap["class"],
                                                   "observed": False, "families": set(), "cases": set(),
                                                   "roles": set(), "obligations": [], "modules": set(),
                                                   "closures": [], "findings": set(), "recorded": set()})
                    g["observed"] = g["observed"] or counted
                    if gap.get("recorded"):
                        g["recorded"].add(gap["recorded"])
                    g["families"].add(identity["family"])
                    g["cases"].add(identity["case"])
                    g["roles"].add(identity["role"])
                    packet_ = gap.get("packet") or {}
                    g["obligations"].append({"example": example["id"], "case": identity["case"], "task": t["id"],
                                             "claim": (p["plan"].get("claim") or {}).get("key"),
                                             "observed": counted,
                                             **(observed_run(folder, example, t, packet_) if counted else {})})
                    g["modules"].update((packet_.get("module") or {}).get("likely") or [])
                    if packet_.get("closure"):
                        g["closures"].append(packet_["closure"])
                    if gap.get("finding"):
                        g["findings"].add(gap["finding"])
    out = []
    for g in groups.values():
        observed = [o for o in g["obligations"] if o["observed"]]
        out.append({"gap": g["gap"], "kind": g["kind"], "class": g["class"], "observed": g["observed"],
                    "families": sorted(g["families"]), "cases": sorted(g["cases"]),
                    "blockedObligations": len({(o["example"], o["task"], o["claim"]) for o in observed}),
                    "predictedObligations": len({(o["example"], o["task"], o["claim"])
                                                 for o in g["obligations"] if not o["observed"]}),
                    "negativeAndPositive": {"negative", "positive"} <= g["roles"],
                    "obligations": g["obligations"], "modules": sorted(g["modules"]),
                    "closures": g["closures"], "findings": sorted(g["findings"]),
                    "recorded": sorted(g["recorded"])})
    out.sort(key=lambda g: (not g["observed"], -len(g["families"]), -g["blockedObligations"], g["gap"]))
    for rank, g in enumerate(out, 1):
        g["rank"] = rank
        g["reproducer"] = reproducer(g["obligations"])
    return {"schema": INVENTORY_SCHEMA,
            "note": "ranked by observed first, distinct families, then blocked obligations; an engineering aid, not "
                    "evidence, and a predicted gap is a hypothesis until a probe reaches it",
            "gaps": out}


def first_sentence(text, limit=240):
    """A predicted gap's summary, cut at its first sentence (or `limit` characters) for the page's table."""
    text = " ".join(str(text).split())
    m = re.search(r"(?<=[a-z0-9)])\. (?=[A-Z])", text)
    cut = text[:m.start() + 1] if m else text
    return cut if len(cut) <= limit else cut[:limit - 1].rstrip() + "…"


def cell(text):
    return str(text).replace("|", "\\|").replace("\n", " ")


def inventory_markdown(value, folders):
    """examples/gap-inventory.md: the inventory as a page, observed gaps ranked with each one's blocked obligations,
    smallest reproducer, missing semantics, owner modules and closure test, then the predicted gaps apart. `folders`
    maps an example id to its folder's name, for links."""
    def link(example, path=None):
        folder = folders.get(example)
        if not folder:
            return example
        return f"[{example}]({folder}/{path or 'README.md'})"

    observed = [g for g in value["gaps"] if g["observed"]]
    predicted = [g for g in value["gaps"] if not g["observed"]]
    lines = [
        "# The v1 gap inventory of the example targets",
        "",
        "Generated from every example with a target sidecar by `python3 examples/tools/targets/workflow_handoff.py "
        "inventory --markdown`, offline, from the sidecars, their gap packets and the receipts in the tree. "
        "`build.py --index-only` and `--render-only` rewrite it with the router. Don't edit it by hand: "
        "`test_gap_inventory.py` checks that it equals the rendering. The JSON form, without `--markdown`, "
        f"has every field (`{value['schema']}`).",
        "",
        "Phase 5 step 4 of [`example-targets.md`](../llm-dlc/loops/example-targets.md) (decision 11): every observed "
        "capability gap of the portfolio, ranked by observed first, then distinct families, then blocked "
        "obligations (example, task and claim), never by raw case counts. A rank is an engineering aid, not "
        "evidence. Each observed obligation's claim stays unresolved with its `expected` conclusion unchanged, and a "
        "gap closes only when that claim, rerun unchanged with the extended implementation, decides it. "
        "`find.py --gap GAP` finds the examples a gap blocks.",
        "",
        "## Observed gaps, ranked",
        "",
        "| Rank | Gap | Kind | Families | Blocked obligations | CVE and positive | Owner modules | Findings |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for g in observed:
        lines.append(f"| {g['rank']} | `{cell(g['gap'])}` | {g['kind']} | {len(g['families'])}: "
                     f"{', '.join(g['families'])} | {g['blockedObligations']} | "
                     f"{'yes' if g['negativeAndPositive'] else 'no'} | {cell('; '.join(g['modules']))} | "
                     f"{', '.join(g['findings'])} |")
    for g in observed:
        lines += ["", f"### {g['rank']}. `{g['gap']}`", ""]
        tasks = {}
        for o in g["obligations"]:
            if o["observed"]:
                tasks.setdefault(o["example"], []).append(f"`{o['task']}` ({o['claim']})")
        lines.append("- **Blocks**: " + "; ".join(f"{link(e)} {', '.join(ts)}" for e, ts in tasks.items()) + ".")
        r = g.get("reproducer")
        if r:
            took = f", {r['seconds']} s" if r.get("seconds") is not None else ""
            lines.append(f"- **Smallest reproducer**: {link(r['example'], r['packet'])} `{r['task']}`, observed by "
                         f"job `{r['job']}`{took}. Rerun it, predicting the refusal: `{r['check']}`.")
            if r.get("semantics"):
                lines.append(f"- **Missing semantics** (from that packet): {r['semantics']}")
        lines.append(f"- **Owner modules**: {'; '.join(g['modules']) or 'not named'}.")
        if r and r.get("closure"):
            lines.append(f"- **Closure test** (each obligation's, here the reproducer's): {r['closure']}.")
    lines += [
        "",
        "## Predicted gaps, kept apart",
        "",
        "Each is a hypothesis from a static scan, the build files or the docs, until a probe or attempt reaches it. "
        "None blocks a task's readiness, and none is ranked against the observed gaps. A prediction marked "
        "\"(recorded DATE)\" is kept as it was written then; its blocker's dated `note` in the example's `target.json` "
        "says what changed since, such as the observed blockers a later attempt met first.",
        "",
        "| Kind | Class | Obligations | Examples | Prediction |",
        "|---|---|---|---|---|",
    ]
    for g in predicted:
        examples = sorted({o["example"] for o in g["obligations"]})
        summary = g["gap"].split(": ", 1)[1] if g["gap"].startswith(g["kind"] + ": ") else g["gap"]
        dated = f"(recorded {', '.join(g['recorded'])}) " if g.get("recorded") else ""
        lines.append(f"| {g['kind']} | {g['class']} | {g['predictedObligations']} | "
                     f"{', '.join(link(e) for e in examples)} | {dated}{cell(first_sentence(summary))} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="The handoff packet of a target task, or the gap inventory.")
    sub = parser.add_subparsers(dest="command", required=True)
    h = sub.add_parser("handoff", help="one task's handoff packet")
    h.add_argument("example")
    h.add_argument("task")
    i = sub.add_parser("inventory", help="the gap inventory of every example with a target sidecar")
    i.add_argument("--markdown", action="store_true", help="as examples/gap-inventory.md, the page")
    args = parser.parse_args(argv)
    import build
    from targets import sidecar

    def load(folder):
        example = build.load_example(folder)
        return folder, example, sidecar.load(folder, example)

    if args.command == "handoff":
        folders = sorted(build.EXAMPLES.glob(f"{args.example}-*"))
        if len(folders) != 1:
            sys.exit(f"example {args.example}: expected one folder examples/{args.example}-*, found {len(folders)}")
        folder, example, target = load(folders[0])
        if target is None:
            sys.exit(f"example {args.example} has no target sidecar")
        if args.task not in [t["id"] for t in target["tasks"]]:
            sys.exit(f"example {args.example} has no task {args.task!r}")
        value = workflow.handoff(folder, example, target, args.task)
    else:
        rows = []
        for folder in sorted(p.parent for p in build.EXAMPLES.glob("*/example.json")):
            if json.loads((folder / "example.json").read_text()).get("target"):
                rows.append(load(folder))
        value = inventory(r for r in rows if r[2] is not None)
        if args.markdown:
            sys.stdout.write(inventory_markdown(value, {e["id"]: f.name for f, e, _ in rows}))
            return
    print(json.dumps(value, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

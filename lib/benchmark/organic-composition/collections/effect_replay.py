"""Check a finite iterator heap effect and resume the original change-plan observer with it."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from heap_effect import CHAIN, EntryHeap, admit, certify, check_continuation, declared_effect, digest, require

CASE = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE.parent))
from freeze import verify
from plan_run import JDK, ROOT, OUTPUT
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_inventory, runtime_jar, upgrade_replay

SCOPE = CASE / "effect-scope.json"
REPORT = ROOT / OUTPUT / "collections/checked-heap-effect.json"
TRACE_SOURCES = [CASE / "IteratorEffectTrace.java", CASE / "IteratorHeap.java"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_table(path):
    rows = [line.split("\t") for line in path.read_text().splitlines()]
    table = dict(rows)
    require(len(table) == len(rows), "duplicate field in debugger output")
    return table


def write_table(path, table):
    path.write_text("".join(f"{k}\t{v}\n" for k, v in sorted(table.items())))


def source_binding(number, side, classes, spec):
    case = CASE.parent / ("collections-" + number)
    manifest = json.loads((case / side / "prepared.json").read_bytes())
    files = [Path(item["file"]) for item in manifest["classpath"]]
    classpath = [upgrade_replay.sha(f) for f in files]
    require(classpath == [i["sha256"] for i in manifest["classpath"]], "original deployment differs")
    archive = ROOT / OUTPUT / case.name / "first/plans.zip"
    with zipfile.ZipFile(archive) as zipped:
        cold = zipped.read("cold.json")
        plan = json.loads(cold)
        node, = (r for r in plan["claims"] if r["id"] == spec["registeredWorkflow"])
        child, = (r for r in node["children"] if r["arguments"] == spec["arguments"])
        payload = zipped.read(node["receipt"]["path"])
        require(sha(payload) == node["receipt"]["sha256"], "unbound original receipt")
    receipt = json.loads(payload)
    original = receipt["sides"][side]
    trial, = (t for t in original["trials"] if t["input"] == child["input"])
    require(node["status"] == child["status"] == "established" and original["commit"] == manifest["commit"]
            and original["classpath"] == classpath and trial["qualifiedMethodEntries"] == 2
            and len(trial["entryInvocations"]) == 2 and trial["observations"] == [child[side]] * 2,
            "original claim or deployment differs")
    where, = {t["observerCodeIndex"] for t in trial["entryInvocations"] if t["dispatchedTo"] == receipt["entry"]}
    require(all(t["dispatchedTo"] == receipt["entry"] for t in trial["entryInvocations"]), "ambiguous original next")
    registration = json.loads((case / "registration.json").read_bytes())
    for name in ("workflows.json", "stateful.json"):
        require(upgrade_replay.sha(case / name) == registration["inputs"][name], "public registration differs")
    workflow, = (w for w in json.loads((case / "workflows.json").read_bytes())["workflows"] if w["id"] == node["id"])
    row = json.loads((case / workflow["scope"]).read_bytes())["cases"][child["input"]]
    allowed = {edit["input"]: edit["expectedNew"] for edit in workflow["intent"]["allowedChanges"]}
    expected = allowed.get(child["input"], row["expected"]) if side == "new" else row["expected"]
    require(row["args"] == spec["arguments"] and expected == child[side], "observation differs from preregistration")
    for name in ("UpgradeProbe", "UpgradeProbe$Decorated", "UpgradeObservation"):
        require(upgrade_replay.sha(classes / (name + ".class")) == receipt["probeClasses"][name],
                "compiled caller class differs from the original plan: " + name)
    data = runtime_jar.read_class(files[0], CHAIN.replace(".", "/"))
    _, code, _ = runtime_jar._declarations(data, with_code=True)[1]["updateCurrentIterator", "()V"]
    returns = [pc for pc, op in change_inventory.instructions(code) if op == 0xb1]
    return files, data, {
        "layout": spec["endpoints"][number + "-" + side], "commit": manifest["commit"], "classpath": classpath,
        "jdk": json.loads((CASE.parent / "freeze.json").read_bytes())["jdk"], "scopeSha256": upgrade_replay.sha(SCOPE),
        "observerSha256": receipt["probeSha256"], "originalReceipt": node["receipt"], "originalClaim": node["claimKey"],
        "originalPlan": str(archive.relative_to(ROOT)), "coldPlanSha256": sha(cold),
        "inputId": child["id"], "input": child["arguments"], "originalObservation": expected, "publicNextSite": where,
        "helperClassSha256": sha(data), "helperCodeSha256": sha(code), "returnBCIs": returns,
        "checkSources": {p.name: upgrade_replay.sha(p) for p in [*TRACE_SOURCES, Path(__file__), CASE / "heap_effect.py"]},
    }


def verify_sites(sites, binding, spec, chain_class, observer_class):
    require(sites["helper"] == spec["helper"] and sites["helper.pc"] == "0"
            and sites["helper.code"] == binding["helperCodeSha256"] and sites["caller"] == spec["caller"]
            and sites["helper.pool"] == sha(chain_class[10:runtime_jar._pool(chain_class)[1]])
            and sites["observer"] == spec["observer"], "live helper, caller or observer differs")
    for data, role, target in ((chain_class, "caller", spec["helper"]), (observer_class, "observer", spec["caller"])):
        resolve_call(sites, role, data, sites[role + ".pc"], target)


def resolve_call(sites, role, data, pc, target):
    _, name, desc = runtime_jar.parse_target(sites[role])
    callee = runtime_jar.member_at_code_index(data, name, desc, int(pc), code_sha256=sites[role + ".code"],
                                               pool_sha256=sites[role + ".pool"])
    require(callee and callee["opcode"] == "invokevirtual"
            and (callee["owner"], callee["name"], callee["descriptor"]) == runtime_jar.parse_target(target),
            "unexpected original instruction at " + role + "@" + str(pc))


def launch(work, classes, tracer, files, binding, name, certificate=None, refusal=None):
    target = work / name
    target.mkdir()
    arg, = binding["input"]
    cp = os.pathsep.join(map(str, [classes, *files]))
    cmd = [JDK / "bin/java", "-Xmx192m", "-cp", tracer, "IteratorEffectTrace", target, certificate or "-",
           ",".join(map(str, binding["returnBCIs"])), cp, base64.b64encode(arg.encode("utf-16-be")).decode()]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    pid = int((target / "pid").read_text())
    if refusal:
        require(result.returncode != 0 and ("IllegalStateException: " + refusal + "\n") in result.stderr
                and not (target / "completion").exists() and not (target / "next.tsv").exists(),
                f"{name} did not refuse before the public continuation: {result.stderr[-1200:]}")
        return {"pid": pid, "refused": refusal}
    require(result.returncode == 0, name + ": " + result.stderr[-1600:])
    origins = upgrade_replay.class_origins((target / "classes.log").read_text())
    require(origins.get(CHAIN) == {files[0]} and origins.get("UpgradeProbe") == {classes}
            and origins.get("UpgradeObservation") == {classes}, "unexpected loaded class provider")
    before, after, sites, next_call, remove, leaf = (read_table(target / (key + ".tsv")) for key in
                                                    ("before", "after", "sites", "next", "remove", "leaf"))
    record = {"pid": pid, "completion": (target / "completion").read_text(), "before": digest(before),
              "after": digest(after), "sites": digest(sites), "next": next_call, "remove": remove, "leaf": leaf,
              "observation": upgrade_replay.typed_outcome((target / "observation.txt").read_text().splitlines())}
    return before, sites, record


def rejected(operation, reason):
    try:
        operation()
    except ValueError as error:
        require(str(error) == reason, "unexpected control refusal: " + str(error))
        return reason
    raise ValueError("an invalid certificate was accepted")


def run_endpoint(work, number, side, classes, tracer, spec):
    work.mkdir()
    files, data, binding = source_binding(number, side, classes, spec)
    observer = (classes / "UpgradeProbe.class").read_bytes()
    originals = []
    for repetition in (1, 2):
        before, sites, original = launch(work, classes, tracer, files, binding, "original-" + str(repetition))
        verify_sites(sites, binding, spec, data, observer)
        resolve_call(sites, "observer", observer, original["remove"]["site"], CHAIN + "#remove()V")
        originals.append(original)
    writes, roles = declared_effect(before, binding["layout"])
    certificate = certify(binding, before, sites, originals, writes)
    tables = {"before": before, "sites": sites, "writes": writes, "after": before | writes}
    path = work / "certificate"
    path.mkdir()
    for name, table in tables.items():
        write_table(path / (name + ".tsv"), table)
    applied = []
    for repetition in (1, 2):
        admit(certificate, binding, before, sites, originals, writes)
        _, _, trial = launch(work, classes, tracer, files, binding, "apply-" + str(repetition), path)
        applied.append(trial)
    # Two disposable launches exercise the live guards even when the final public value could survive.
    entry = EntryHeap(before)
    stale = before | {entry.slot(roles["mutable"], "cursor"): "I:0"}
    write_table(path / "before.tsv", stale)
    controls = {"changedCursor": launch(work, classes, tracer, files, binding, "stale", path, "live prestate differs")}
    write_table(path / "before.tsv", before)
    omitted = writes.copy()
    del omitted[entry.slot(roles["detached"], "item")]
    write_table(path / "writes.tsv", omitted)
    controls["missingDetachedItem"] = launch(work, classes, tracer, files, binding, "missing-unlink", path, "substituted frame differs")
    record = {"binding": binding, "entryHeap": before, "liveSites": sites, "writes": writes, "roles": roles,
              "certificate": certificate, "originals": originals, "substitutions": applied, "liveControls": controls}
    return record


def audit_endpoint(record):
    binding, before, sites = (record[k] for k in ("binding", "entryHeap", "liveSites"))
    originals, applied = record["originals"], record["substitutions"]
    writes, roles = declared_effect(before, binding["layout"])
    require(record["roles"] == roles and record["writes"] == writes, "archived effect differs")
    certificate = record["certificate"]
    admit(certificate, binding, before, sites, originals, writes)
    require(len(applied) == 2, "two substitutions required")
    for trial in applied:
        check_continuation(trial, roles, binding)
        require(trial["completion"] == "substituted at bytecode entry"
                and all(trial[k] == originals[0][k] for k in ("sites", "before", "after", "next", "remove", "leaf")),
                "substituted continuation differs from the original")
    controls = record["liveControls"]
    require(controls["changedCursor"]["refused"] == "live prestate differs"
            and controls["missingDetachedItem"]["refused"] == "substituted frame differs", "missing live refusal")
    require(len({r["pid"] for r in [*originals, *applied, *controls.values()]}) == 6, "fresh JVM required for each trial")
    no_original = rejected(lambda: certify(binding, before, sites, originals[:1], writes), "two fresh originals required")
    wrong = writes | {EntryHeap(before).slot(roles["parent"], "currentIterator"):
                      roles["sibling"] if roles["selected"] == roles["child"] else roles["child"]}
    wrong_alias = rejected(lambda: certify(binding, before, sites, originals, wrong), "proposed writes differ from the declared effect")
    return {"withheldOriginal": no_original, "wrongReceiver": wrong_alias}


def audit(report):
    spec = json.loads(SCOPE.read_bytes())
    endpoints = report["endpoints"]
    require(set(endpoints) == set(spec["endpoints"]), "missing registered deployment")
    for name, record in endpoints.items():
        require(record["binding"]["scopeSha256"] == upgrade_replay.sha(SCOPE)
                and record["binding"]["layout"] == spec["endpoints"][name], "different registration")
        require(audit_endpoint(record) == record["admissionControls"], "missing admission refusal")
        binding = record["binding"]
        with zipfile.ZipFile(ROOT / binding["originalPlan"]) as original:
            cold = original.read("cold.json")
            receipt = binding["originalReceipt"]
            require(sha(cold) == binding["coldPlanSha256"] and sha(original.read(receipt["path"])) == receipt["sha256"],
                    "original public plan or receipt differs")
        node, = (c for c in json.loads(cold)["claims"] if c["id"] == spec["registeredWorkflow"])
        child, = (c for c in node["children"] if c["arguments"] == spec["arguments"])
        side = name.split("-")[1]
        require(node["claimKey"] == binding["originalClaim"] and node["receipt"] == receipt
                and child["id"] == binding["inputId"] and child[side] == binding["originalObservation"],
                "archived public claim differs")
        # The two flattened histories even share helper bytecode. A certificate still binds its whole deployment.
        other = endpoints[report["crossDeployment"][name]["attemptedOn"]]
        require(other["binding"]["commit"] != binding["commit"], "same deployment in stale control")
        changed = binding | {k: other["binding"][k] for k in ("commit", "classpath")}
        reason = rejected(lambda: admit(record["certificate"], changed, record["entryHeap"], record["liveSites"],
                                        record["originals"], record["writes"]), "certificate belongs to a different deployment or execution")
        require(reason == report["crossDeployment"][name]["refused"], "missing cross-deployment refusal")
    return endpoints


def run():
    verify()
    spec = json.loads(SCOPE.read_bytes())
    endpoints = {}
    with tempfile.TemporaryDirectory(prefix="iterator-effects-") as tmp:
        work = Path(tmp)
        tracer = work / "tracer"
        tracer.mkdir()
        subprocess.run([JDK / "bin/javac", "-proc:none", "-d", tracer, *TRACE_SOURCES], check=True)
        for number in ("628", "755"):
            classes = work / ("caller-" + number)
            classes.mkdir()
            manifest = json.loads((CASE.parent / ("collections-" + number) / "old/prepared.json").read_bytes())
            cp = os.pathsep.join(r["file"] for r in manifest["classpath"])
            subprocess.run([JDK / "bin/javac", "-proc:none", "-g", "-encoding", "UTF-8", "-cp", cp, "-d", classes,
                            upgrade_replay.LAUNCHER, CASE / "UpgradeProbe.java"], check=True)
            for side in ("old", "new"):
                name = number + "-" + side
                record = run_endpoint(work / name, number, side, classes, tracer, spec)
                record["admissionControls"] = audit_endpoint(record)
                endpoints[name] = record
    cross = {}
    for left, right in (("628-old", "755-new"), ("628-new", "755-old"), ("755-old", "628-new"), ("755-new", "628-old")):
        cross[left] = {"attemptedOn": right, "refused": "certificate belongs to a different deployment or execution"}
    report = {"schema": "finite-iterator-effect/v1", "endpoints": endpoints, "crossDeployment": cross}
    audit(report)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true", help="verify the committed finite certificates without starting JVMs")
    args = parser.parse_args()
    checked = audit(json.loads(REPORT.read_bytes()) if args.audit else run())
    for name, row in checked.items():
        print(name, row["binding"]["layout"], len(row["writes"]), "changed fields,", row["originals"][0]["leaf"]["member"])

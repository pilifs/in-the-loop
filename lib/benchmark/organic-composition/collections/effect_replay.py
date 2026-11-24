"""Check a finite iterator heap effect and resume the original change-plan observer with it."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile

from heap_effect import CHAIN, DECORATOR, EntryHeap, admit, certify, check_continuation, effect_for, digest, require

CASE = Path(__file__).resolve().parent
sys.path.insert(0, str(CASE.parent))
from freeze import verify
from plan_run import JDK, ROOT, OUTPUT
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_inventory, runtime_jar, upgrade_replay

SCOPES = {"advanced": CASE / "effect-scope.json", "unmodifiable": CASE / "unmodifiable-scope.json"}
REPORTS = {k: ROOT / OUTPUT / "collections" / name for k, name in
           (("advanced", "checked-heap-effect.json"), ("unmodifiable", "checked-decorator-effect.json"))}
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


def removal_binding(jar, chain_class, observer_path):
    wrapper = runtime_jar.read_class(jar, DECORATOR.replace(".", "/"))
    _, body, _ = runtime_jar._declarations(wrapper, with_code=True)[1]["remove", "()V"]
    _, parent, _ = runtime_jar._declarations(chain_class, with_code=True)[1]["remove", "()V"]
    def calls(data, code, name, desc, target, opcode):
        sites = []
        for pc, op in change_inventory.instructions(code):
            if op != opcode:
                continue
            call = runtime_jar.member_at_code_index(data, name, desc, pc, code_sha256=sha(code),
                                                    pool_sha256=sha(data[10:runtime_jar._pool(data)[1]]))
            if call and (call["owner"], call["name"], call["descriptor"]) == (target, "remove", "()V"):
                sites.append(pc)
        return sites
    dispatch = calls(chain_class, parent, "remove", "()V", "java.util.Iterator", 0xb9)
    observer = observer_path.read_bytes()
    sig = "([Ljava/lang/String;)Ljava/lang/String;"
    _, observe, _ = runtime_jar._declarations(observer, with_code=True)[1]["observe", sig]
    public_sites = calls(observer, observe, "observe", sig, CHAIN, 0xb6)
    disassembly = subprocess.check_output([JDK / "bin/javap", "-c", "-p", observer_path], text=True)
    part = re.search(r"^  public static java.lang.String observe\(java.lang.String\[\]\);$(.*?)(?=^  \S|^})",
                     disassembly, re.M | re.S)
    require(part is not None, "missing original observer disassembly")
    handlers = re.findall(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+Class java/lang/UnsupportedOperationException\s*$",
                          part[1], re.M)
    catches = {str(pc): [int(target) for start, end, target in handlers if int(start) <= pc < int(end)] for pc in public_sites}
    throws = [pc for pc, op in change_inventory.instructions(body) if op == 0xbf]
    require(throws and dispatch and catches and all(len(v) == 1 for v in catches.values()), "unbound removal or exception handler")
    return {"class": sha(wrapper), "code": sha(body), "pool": sha(wrapper[10:runtime_jar._pool(wrapper)[1]]),
            "throwBCIs": throws, "parentCode": sha(parent), "dispatchBCIs": dispatch, "catchByPublicCall": catches}


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
    binding = {
        "layout": spec["endpoints"][number + "-" + side], "commit": manifest["commit"], "classpath": classpath,
        "jdk": json.loads((CASE.parent / "freeze.json").read_bytes())["jdk"],
        "scopeSha256": upgrade_replay.sha(SCOPES[spec["arguments"][0]]),
        "observerSha256": receipt["probeSha256"], "originalReceipt": node["receipt"], "originalClaim": node["claimKey"],
        "originalPlan": str(archive.relative_to(ROOT)), "coldPlanSha256": sha(cold),
        "inputId": child["id"], "input": child["arguments"], "originalObservation": expected, "publicNextSite": where,
        "helperClassSha256": sha(data), "helperCodeSha256": sha(code), "returnBCIs": returns,
        "checkSources": {p.name: upgrade_replay.sha(p) for p in [*TRACE_SOURCES, Path(__file__), CASE / "heap_effect.py"]},
    }
    if spec["arguments"] == ["unmodifiable"]:
        binding["decoratorRemoval"] = removal_binding(files[0], data, classes / "UpgradeProbe.class")
    return files, data, binding


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
    if binding["input"] == ["unmodifiable"]:
        require(origins.get(DECORATOR) == {files[0]}, "wrong loaded decorator provider")
        record["throw"] = read_table(target / "throw.tsv")
        if certificate:
            record["typeResolution"] = read_table(target / "type-resolution.tsv")
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
    writes, roles = effect_for(binding, before)
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
    cursor = entry.slot(roles["mutable"], "cursor")
    stale = before | {cursor: "I:1" if before[cursor] == "I:0" else "I:0"}
    write_table(path / "before.tsv", stale)
    controls = {"changedCursor": launch(work, classes, tracer, files, binding, "stale", path, "live prestate differs")}
    write_table(path / "before.tsv", before)
    omitted = writes.copy()
    del omitted[entry.slot(roles["detached"], "item")]
    write_table(path / "writes.tsv", omitted)
    controls["missingDetachedItem"] = launch(work, classes, tracer, files, binding, "missing-unlink", path, "substituted frame differs")
    if binding["input"] == ["unmodifiable"]:
        locked = entry.slot(roles["child"], "isLocked")
        wrong_lock = "Z:false" if (before | writes)[locked] == "Z:true" else "Z:true"
        for name, bad in (("wrongChildLock", {locked: wrong_lock}),
                          ("bypassedDecorator", {entry.slot(roles["parent"], "currentIterator"): roles["delegate"]})):
            write_table(path / "writes.tsv", writes | bad)
            controls[name] = launch(work, classes, tracer, files, binding, name, path, "substituted frame differs")
    record = {"binding": binding, "entryHeap": before, "liveSites": sites, "writes": writes, "roles": roles,
              "certificate": certificate, "originals": originals, "substitutions": applied, "liveControls": controls}
    return record


def audit_endpoint(record):
    binding, before, sites = (record[k] for k in ("binding", "entryHeap", "liveSites"))
    originals, applied = record["originals"], record["substitutions"]
    writes, roles = effect_for(binding, before)
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
    refusals = {"changedCursor", "missingDetachedItem"}
    decorated = binding["input"] == ["unmodifiable"]
    if decorated:
        for key in ("wrongChildLock", "bypassedDecorator"):
            require(controls[key]["refused"] == "substituted frame differs", "missing decorated-frame refusal")
            refusals.add(key)
        require(all(t["throw"] == originals[0]["throw"] for t in [*originals, *applied]), "exception routes differ")
        for trial in applied:
            resolution = trial["typeResolution"]
            require(resolution["field"] == CHAIN + "#cachedHasNextValue:Ljava/lang/Boolean;"
                    and resolution["type"] == "java.lang.Boolean" and resolution["loader"] == "bootstrap"
                    and resolution["action"] in ("already resolved", "Class.forName with initialization disabled in the field owner's loader")
                    and resolution["entry"] == "same receiver, instruction and complete entry heap",
                    "unqualified cache field type resolution")
    require(set(controls) == refusals and len({r["pid"] for r in [*originals, *applied, *controls.values()]})
            == 4 + len(refusals), "fresh JVM required for each trial")
    no_original = rejected(lambda: certify(binding, before, sites, originals[:1], writes), "two fresh originals required")
    wrong = writes | {EntryHeap(before).slot(roles["parent"], "currentIterator"):
                      roles["sibling"] if roles["selected"] == roles["child"] else roles["child"]}
    wrong_alias = rejected(lambda: certify(binding, before, sites, originals, wrong), "proposed writes differ from the declared effect")
    checks = {"withheldOriginal": no_original, "wrongReceiver": wrong_alias}
    if decorated:
        for key, edit in (("wrongThrowReceiver", {"receiver": roles["mutable"]}), ("wrongThrowSite", {"at": "-1"})):
            forged = originals[0] | {"throw": originals[0]["throw"] | edit}
            checks[key] = rejected(lambda: certify(binding, before, sites, [forged, originals[1]], writes),
                                   "throwing decorator or original exception route differs")
    return checks


def audit(report, history="advanced"):
    scope = SCOPES[history]
    spec = json.loads(scope.read_bytes())
    endpoints = report["endpoints"]
    require(set(endpoints) == set(spec["endpoints"]), "missing registered deployment")
    for name, record in endpoints.items():
        require(record["binding"]["input"] == spec["arguments"] and record["binding"]["scopeSha256"] == upgrade_replay.sha(scope)
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


def run(history):
    verify()
    spec = json.loads(SCOPES[history].read_bytes())
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
    audit(report, history)
    REPORTS[history].write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", choices=SCOPES, default="advanced")
    parser.add_argument("--audit", action="store_true", help="verify the committed finite certificates without starting JVMs")
    args = parser.parse_args()
    checked = audit(json.loads(REPORTS[args.history].read_bytes()) if args.audit else run(args.history), args.history)
    for name, row in checked.items():
        print(name, row["binding"]["layout"], len(row["writes"]), "changed fields,", row["originals"][0]["leaf"]["member"])

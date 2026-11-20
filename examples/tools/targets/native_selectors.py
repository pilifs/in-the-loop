"""Check a finite int selector by exhaustive native execution of its constant call sites."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import struct
import tempfile
import time

from targets import executions, finite_check, interfaces, qualification, recipes
from targets import replay_candidate, route, runtime, runtime_jar, sidecar, workflow, workflow_ingest

PACKAGE = "verificationselectors"


def read(path):
    return json.loads(path.read_text())


def case_name(value):
    return f"m{-value}" if value < 0 else f"p{value}"


def bytecode_selectors(data, owner, low, high, entry=None):
    """Read every authorized method from the class itself, including its constant and call target."""
    if (
        runtime_jar.this_class(data) != PACKAGE + "/" + owner
        or runtime_jar.super_class(data) != "java/lang/Object"
        or runtime_jar.interfaces(data)
    ):
        raise ValueError("unexpected selector class identity or hierarchy")
    pool, methods, _ = runtime_jar._declarations(data, with_code=True)
    expected = {(case_name(n), "()I") for n in range(low, high + 1)}
    if set(methods) != expected | {("<init>", "()V")}:
        raise ValueError("the selector class has unexpected methods or a static initializer")
    admitted = []
    for n in range(low, high + 1):
        flags, instructions, handlers = methods[case_name(n), "()I"]
        if flags != 0x0009 or handlers or not instructions:
            raise ValueError("each selector must be public static with one normal return")
        op = instructions[0]
        if 2 <= op <= 8:
            value, stop = op - 3, 1
        elif op in (0x10, 0x11):
            stop = 2 if op == 0x10 else 3
            value = int.from_bytes(instructions[1:stop], "big", signed=True)
        elif op in (0x12, 0x13):
            stop = 2 if op == 0x12 else 3
            tag, encoded = pool[int.from_bytes(instructions[1:stop], "big")]
            if tag != 3:
                raise ValueError("a selector does not load an integer")
            value = int.from_bytes(encoded, "big", signed=True)
        else:
            raise ValueError("the emitted selector is not a constant")
        tail = instructions[stop:]
        if entry is None:
            if value not in (0, 1) or tail != bytes([0xAC]):
                raise ValueError("the complete guard did not fold to a Boolean")
            if value:
                admitted.append(n)
        else:
            if value != n or len(tail) != 4 or tail[0] != 0xB8 or tail[-1] != 0xAC:
                raise ValueError("the specialization is not exactly a constant, static call and int return")
            tag, (cls, nt) = pool[int.from_bytes(tail[1:3], "big")]
            typ, (method, descriptor) = pool[nt]
            member = (
                runtime_jar._class_name(pool, cls).replace("/", "."),
                runtime_jar._utf8(pool, method),
                runtime_jar._utf8(pool, descriptor),
            )
            if tag not in (10, 11) or typ != 12 or member != entry:
                raise ValueError("the constant call does not reach the frozen class and descriptor")
    return admitted


def java_source(name, bodies):
    return "package " + PACKAGE + ";\npublic final class " + name + " {\n" + "\n".join(bodies) + "\n}\n"


def compile_methods(home, work, name, bodies, cp, classes):
    work.mkdir(parents=True, exist_ok=True)
    classes.mkdir(parents=True, exist_ok=True)
    src = work / (name + ".java")
    src.write_text(java_source(name, bodies))
    run = subprocess.run(
        [
            home / "bin/javac",
            "-J-XX:-UsePerfData",
            "-proc:none",
            "-g:none",
            "-cp",
            os.pathsep.join(map(str, cp)),
            "-d",
            classes,
            src,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if run.returncode:
        raise ValueError(run.stderr[-1200:])
    file = classes / PACKAGE / (name + ".class")
    # The repository ignores .class files. Retain identical bytes under a portable name.
    archived = work / (name + ".jvm-bytecode")
    archived.write_bytes(file.read_bytes())
    return archived


def compiled_calls(home, dest, owner, method, low, high, cp, classes):
    bodies = [
        f"public static int {case_name(v)}() throws Throwable {{ return {owner}.{method}({v}); }}"
        for v in range(low, high + 1)
    ]
    file = compile_methods(home, dest, "Calls", bodies, cp, classes)
    bytecode_selectors(file.read_bytes(), "Calls", low, high, (owner, method, "(I)I"))
    return file


def admission_methods(guard, parameter, low, high):
    if set(re.findall(r"[A-Za-z_$][\w$]*", guard)) != {parameter}:
        raise ValueError("admission must depend only on the int selector")
    bodies = []
    for v in range(low, high + 1):
        ground = re.sub(r"\b" + re.escape(parameter) + r"\b", f"({v})", guard)
        bodies.append(f"public static int {case_name(v)}() {{ return ({ground}) ? 1 : 0; }}")
    return bodies


def admitted_selectors(home, dest, guard, parameter, low, high):
    with tempfile.TemporaryDirectory(prefix="native-selector-guard-") as compiled:
        file = compile_methods(
            home, dest, "Admission", admission_methods(guard, parameter, low, high), [], Path(compiled)
        )
    admitted = bytecode_selectors(file.read_bytes(), "Admission", low, high)
    if not admitted:
        raise ValueError("no admitted selector")
    return admitted, file


def native_case(exe, jdk, cp, compiled, value, bounds, seconds, work, dest):
    method = PACKAGE + ".Calls#" + case_name(value) + "()"
    args = [exe, "prove", method, "--classes", str(compiled)]
    for jar in cp:
        args += ["--classpath", str(jar)]
    args += [
        "--assert",
        "result == 1",
        "--engine",
        "native",
        "--gaps",
        "strict",
        "--unwind",
        str(bounds["unwind"]),
        "--max-array-length",
        str(bounds["maxArrayLength"]),
        "--timeout",
        str(seconds),
        "--work",
        str(work),
        "--json",
    ]
    dest.mkdir(parents=True)
    usage = {}
    status, rc, elapsed = runtime._run_one(
        args,
        work.parent,
        dest / "native.json",
        dest / "stderr",
        seconds + 15,
        env=runtime._verifier_env(jdk),
        usage=usage,
    )
    row = {
        "selector": value,
        "status": "open",
        "target": method,
        "exit": rc,
        "wallSeconds": elapsed,
        "usage": usage,
        "rawSha256": runtime.sha256(dest / "native.json"),
    }
    if status != "exited":
        row["firstBlocker"] = status
        return row
    try:
        (answer,) = read(dest / "native.json")
    except (ValueError, TypeError):
        row["firstBlocker"] = "checker returned incomplete JSON"
        return row
    row["status"], reason = disposition(answer, method, bounds, rc)
    row["assumptions"] = (answer.get("stated") or {}).get("assumptions", [])
    if reason:
        row["firstBlocker"] = reason
    return row


def disposition(answer, method, bounds, rc):
    stated = answer.get("stated") or {}
    search = answer.get("search") or {}
    if (
        answer.get("target") != method
        or answer.get("assume") is not None
        or answer.get("assert") != "result == 1"
        or stated.get("gap_mode") != "strict"
        or (stated.get("checker") or {}).get("engine") != "native"
        or (stated.get("bounds") or {}).get("unwind") != bounds["unwind"]
        or (stated.get("domain") or {}).get("parameters") != []
        or (stated.get("observations") or {}).get("exceptions") != "none may be thrown"
        or search.get("properties") != 1
        or search.get("max_array_length") != bounds["maxArrayLength"]
    ):
        return "open", "the native checker returned a different statement"
    if (
        answer["verdict"] == "verified"
        and stated["bounds"].get("complete")
        and (stated.get("vacuity") or {}).get("status") == "non-vacuous"
        and answer.get("proof")
        and rc == 0
    ):
        return "established", None
    elif (
        answer["verdict"] == "violation"
        and rc == 1
        and (answer.get("replay") or {}).get("by") == "jvm"
        and answer.get("counterexample")
        and (answer.get("replay") or {}).get("reproduced")
    ):
        return "refuted", None
    else:
        return "open", answer.get("problem") or answer.get("output") or answer["verdict"]


def check(plan, prepared, shared, work, out, exe, seconds, first, max_cases, task_start):
    claim = plan.claim
    recipe = recipes.translate(plan)
    if (
        isinstance(recipe, interfaces.Unsupported)
        or plan.kind != "prove"
        or plan.engine != "native"
        or plan.gaps != "strict"
        or (claim.get("assert") or "").strip() != "result == 1"
        or claim.get("observations") != ["result", "exception"]
        or any(
            claim.get(k)
            for k in (
                "models",
                "namedModels",
                "observedInitializers",
                "boundEnvironment",
                "assumptions",
                "allowedChange",
                "contracts",
                "plan",
                "throws",
                "nullable",
                "mayAlias",
            )
        )
        or plan.checkedLemmas
    ):
        raise ValueError("this specialization requires an ordinary strict result == 1 property")
    (rev,) = plan.revisions
    owner, method, desc = runtime_jar.parse_target(recipe.entry)
    if desc != "(I)I":
        raise ValueError("a single int selector and an int return are required")
    p = prepared[rev]
    where = runtime._preparation_dir(p)
    built = {rev: (where, p, runtime._checked(where, p))}
    invocation = recipe.bind(plan, exe, built, "native-selectors", seconds)
    cp_info = invocation.classpaths[rev]
    cp = [where / x["path"] for x in cp_info]
    data = runtime_jar.read_class(cp[0], runtime_jar.internal(owner))
    if not data or not runtime_jar.method_flags(data, method, desc) & 8:
        raise ValueError("the selected entry is not the prepared static method")
    if any(runtime_jar.read_class(j, PACKAGE + "/Calls") is not None for j in cp):
        raise ValueError("the added call-site class would shadow an existing class")
    [parameter], _ = runtime_jar.parameter_names(data, method, desc)
    low, high = finite_check.envelope(claim["assume"], parameter, max_cases)
    jdk = runtime._verifier_jdk(plan, prepared)
    home = Path(jdk["home"])
    bindings = workflow_ingest.bound_revisions(plan, prepared)
    if "controls" not in shared:
        shared["controls"] = runtime.run_controls(plan, prepared, work / "controls")
    controls = shared["controls"]
    if isinstance(controls, interfaces.Unsupported) or any(
        workflow_ingest.record_problem(r, bindings) for r in controls
    ):
        raise ValueError("the original JVM controls do not match the selected bytes")
    correspondence, problem = (
        qualification.correspondence(plan, prepared, controls) if claim.get("adapter") else ([], None)
    )
    if problem:
        raise ValueError(str(problem))
    task_dir = out / "tasks" / plan.task
    admitted, gate = admitted_selectors(home, task_dir, claim["assume"], parameter, low, high)
    key = workflow.canonical_digest(
        {"entry": recipe.entry, "classpath": cp_info, "bounds": claim["bounds"], "envelope": [low, high]}
    )
    shared_dir = out / "calls" / key[:20]
    classpath_root = work / "specializations" / key
    if key not in shared["calls"]:
        file = compiled_calls(home, shared_dir, owner, method, low, high, cp, classpath_root)
        shared["calls"][key] = (file, {})
    file, cases = shared["calls"][key]
    order = list(admitted)
    for reference in reversed(finite_check.evidence(Path(plan.folder), plan)):
        if reference.get("status") == "refuted":
            replay = read(Path(plan.folder) / reference["receipt"]).get("replay") or {}
            inputs = replay.get("inputs") or []
            if len(inputs) == 1 and inputs[0]["value"] in order:
                v = inputs[0]["value"]
                order.remove(v)
                order.insert(0, v)
            break
    if first in order:
        order.remove(first)
        order.insert(0, first)
    record = {
        "schema": "native-selector-proof/v1",
        "identity": finite_check.claim_identity(plan),
        "task": plan.task,
        "revision": rev,
        "entry": recipe.entry,
        "guard": claim["assume"],
        "parameter": parameter,
        "assertion": claim["assert"],
        "bounds": claim["bounds"],
        "envelope": [low, high],
        "maxCases": max_cases,
        "admitted": admitted,
        "JDK": jdk["release"],
        "checker": {**runtime._verifier_build(exe), "sha256": runtime.sha256(exe)},
        "classpath": cp_info,
        "correspondence": correspondence,
        "ruleSha256": runtime.sha256(Path(__file__)),
        "admissionClass": str(gate.relative_to(out)),
        "admissionSha256": runtime.sha256(gate),
        "callsClass": str(file.relative_to(out)),
        "callsSha256": runtime.sha256(file),
        "checked": [],
        "status": "open",
    }
    start = time.monotonic()
    replay_seconds = 0.0
    for v in order:
        dest = shared_dir / "cases" / case_name(v)
        reused = v in cases
        if not reused:
            scratch = work / (plan.task + "-" + case_name(v))
            scratch.mkdir()
            cases[v] = native_case(
                exe, jdk, cp, classpath_root, v, claim["bounds"], seconds, scratch / "checker", dest
            )
        verified = {**cases[v], "raw": str((dest / "native.json").relative_to(out)), "reusedInBatch": reused}
        record["checked"].append(verified)
        if verified["status"] == "refuted":
            inputs = [{"name": parameter, "type": "int", "value": v}]
            replay_start = time.monotonic()
            replay = replay_candidate.check(
                plan, prepared, inputs, work / (plan.task + "-replay"), entry=recipe.entry
            )
            replay_seconds = time.monotonic() - replay_start
            record["originalJVMReplay"] = replay
            if replay.get("reproduced"):
                record["status"] = "refuted"
            else:
                record["firstBlocker"] = (
                    replay.get("reason") or "the original JVM disagrees with the native case"
                )
            break
        if verified["status"] != "established":
            record["firstBlocker"] = verified["firstBlocker"]
            break
    else:
        record["status"] = "established"
    record["wallSeconds"] = round(time.monotonic() - start, 5)
    measured = [r for r in record["checked"] if not r["reusedInBatch"]]
    record["cost"] = {
        "preparationAndCorrespondenceSeconds": round(start - task_start, 5),
        "checkerWallSeconds": round(sum(r["wallSeconds"] for r in measured), 5),
        "originalWitnessReplaySeconds": round(replay_seconds, 5),
        "endToEndSeconds": round(time.monotonic() - task_start, 5),
        "peakNativeRssBytes": max((r["usage"].get("peakRssBytes", 0) for r in measured), default=0),
    }
    executions.save(task_dir / "result.json", record)
    print(
        f"{plan.task} {record['status']}, {len(record['checked'])}/{len(admitted)} admitted selectors",
        flush=True,
    )
    return record["status"] == plan.expected


def archived_bytes(out, name):
    path = out / name
    if not path.is_file() and path.suffix == ".class":
        path = path.parent.parent / (path.stem + ".jvm-bytecode")
    return workflow.inside(out, path.relative_to(out))


def validate_result(folder, plan, path):
    doc = read(path)
    if (
        doc["identity"] != finite_check.claim_identity(plan)
        or doc["task"] != plan.task
        or [doc["revision"]] != list(plan.revisions)
        or not doc["classpath"]
    ):
        raise ValueError("different frozen inputs")
    out = path.parents[2]
    calls = archived_bytes(out, doc["callsClass"])
    gate = archived_bytes(out, doc["admissionClass"])
    if runtime.sha256(calls) != doc["callsSha256"] or runtime.sha256(gate) != doc["admissionSha256"]:
        raise ValueError("different specialization bytecode")
    entry = recipes.translate(plan).entry
    if (
        doc["entry"] != entry
        or doc["guard"] != plan.claim["assume"]
        or doc["assertion"] != plan.claim["assert"]
        or doc["bounds"] != plan.claim["bounds"]
    ):
        raise ValueError("different statement")
    parameter = doc.get("parameter", "code")
    low, high = finite_check.envelope(doc["guard"], parameter, doc.get("maxCases", finite_check.LIMIT))
    if doc["envelope"] != [low, high]:
        raise ValueError("different proved envelope")
    source = workflow.inside(out, (path.parent / "Admission.java").relative_to(out))
    if source.read_text() != java_source(
        "Admission", admission_methods(plan.claim["assume"], parameter, low, high)
    ):
        raise ValueError("the compiled admission source differs from the frozen full guard")
    bytecode_selectors(calls.read_bytes(), "Calls", low, high, runtime_jar.parse_target(entry))
    admitted = bytecode_selectors(gate.read_bytes(), "Admission", low, high)
    checked = doc["checked"]
    ids = [r["selector"] for r in checked]
    if (
        not admitted
        or admitted != doc["admitted"]
        or not set(ids) <= set(admitted)
        or len(set(ids)) != len(ids)
    ):
        raise ValueError("inconsistent admitted cases")
    for r in checked:
        raw = workflow.inside(out, r["raw"])
        if runtime.sha256(raw) != r["rawSha256"]:
            raise ValueError("different raw checker output")
        if r["status"] != "open":
            (answer,) = read(raw)
            name = PACKAGE + ".Calls#" + case_name(r["selector"]) + "()"
            if (
                r["target"] != name
                or disposition(answer, name, doc["bounds"], r["exit"])[0] != r["status"]
                or r.get("assumptions", []) != (answer.get("stated") or {}).get("assumptions", [])
            ):
                raise ValueError("native status does not follow from the retained checker record")
    status = doc["status"]
    if status not in {"established", "refuted", "open"}:
        raise ValueError("unknown native selector disposition")
    if status == "established" and (
        set(ids) != set(admitted) or any(r["status"] != "established" for r in checked)
    ):
        raise ValueError("incomplete native coverage")
    if status == "refuted":
        replay = doc.get("originalJVMReplay", {})
        if (
            not checked
            or checked[-1]["status"] != "refuted"
            or not replay.get("reproduced")
            or replay.get("entry") != entry
        ):
            raise ValueError("the violation lacks an original JVM replay")
        side = replay["sides"][doc["revision"]]
        inputs = [{"name": parameter, "type": "int", "value": checked[-1]["selector"]}]
        if (
            replay.get("claimKey") != plan.claim["key"]
            or replay.get("jdkRelease") != doc["JDK"]
            or not side.get("admitted")
            or side.get("satisfies") is not False
            or side["classpath"] != [x["sha256"] for x in doc["classpath"]]
            or replay["inputs"] != inputs
            or side.get("program") != replay_candidate.source(entry, plan.claim, inputs, [parameter])
        ):
            raise ValueError("different replay binding or input")
    return {
        "status": status,
        "record": os.path.relpath(path, folder),
        "admitted": len(admitted),
        "checked": len(ids),
        "firstBlocker": doc.get("firstBlocker"),
    }


def evidence_roots(folder):
    from targets.claim_history import evidence_folders

    folder = Path(folder).resolve()
    return [
        (directory, manifest)
        for directory, manifest in evidence_folders(folder.parent.parent, folder)
        if (directory / "records/native-selectors").is_dir()
    ]


def evidence(folder, plan, roots=None):
    from targets.claim_history import has_evidence

    folder = Path(folder).resolve()
    accepted = []
    seen = set()
    for directory, manifest in evidence_roots(folder) if roots is None else roots:
        for path in sorted(
            (directory / "records/native-selectors").glob(f"*/*/tasks/{plan.task}/result.json")
        ):
            if not has_evidence(directory, manifest, folder.relative_to(folder.parent.parent), path):
                continue
            signature = (path.parents[2].name, runtime.sha256(path))
            if signature in seen:
                continue
            seen.add(signature)
            try:
                accepted.append(validate_result(folder, plan, path))
            except (OSError, IndexError, ValueError, KeyError, TypeError, struct.error) as exc:
                accepted.append(
                    {
                        "status": "ineligible",
                        "record": os.path.relpath(path, folder),
                        "firstBlocker": str(exc),
                    }
                )
    return sorted(accepted, key=lambda record: Path(record["record"]).parents[2].name)


def main(argv):
    import build

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example")
    parser.add_argument("tasks")
    parser.add_argument("--checker-seconds", type=int, default=90)
    parser.add_argument("--first", type=int, help="check this selector first when the full guard admits it")
    parser.add_argument("--max-cases", type=int, default=finite_check.LIMIT)
    a = parser.parse_args(argv)
    (folder,) = build.EXAMPLES.glob(a.example + "-*")
    example = build.load_example(folder)
    target = sidecar.load(folder, example)
    try:
        names = a.tasks.split(",")
        plans = [route.resolve(folder, example, target, t) for t in names]
        if (
            len(names) != len(set(names))
            or any(not isinstance(p, interfaces.TaskPlan) or len(p.revisions) != 1 for p in plans)
            or len({tuple(p.revisions) for p in plans}) != 1
            or a.checker_seconds <= 0
            or not 1 <= a.max_cases <= 65534
        ):
            raise ValueError("select distinct tasks on one original revision")
        exe = runtime.jvmcontract()
        if not exe:
            raise ValueError("no built native checker")
        exe = str(Path(exe).resolve())
        (rev,) = plans[0].revisions
        out = folder / "records/native-selectors" / rev / executions.new_id(executions.now())
        out.mkdir(parents=True)
        with tempfile.TemporaryDirectory(prefix="native-selectors-") as tmp:
            work = Path(tmp)
            shared = {"prepared": {}, "calls": {}}
            passed = True
            for plan in plans:
                task_start = time.monotonic()
                p = route.prepare_revision(plan, rev, work / "prepare" / plan.task, shared["prepared"])
                if isinstance(p, interfaces.Unsupported) or p.stage != "artifacts-ready":
                    raise ValueError("preparation failed for " + rev)
                passed = (
                    check(
                        plan,
                        {rev: p},
                        shared,
                        work,
                        out,
                        exe,
                        a.checker_seconds,
                        a.first,
                        a.max_cases,
                        task_start,
                    )
                    and passed
                )
            return 0 if passed else 1
    except (OSError, ValueError, KeyError, subprocess.SubprocessError, RuntimeError) as exc:
        parser.exit(1, f"native selector checks unresolved: {exc}\n")

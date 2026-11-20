"""Compare exhaustive exploration, identity-aware sleep sets and an independent sequential oracle."""

import argparse
from dataclasses import dataclass, replace
import hashlib
from itertools import product
import json
import multiprocessing
from pathlib import Path
import resource
import tempfile
import time

from targets import array_induction, interfaces, route, runtime, runtime_jar, runtime_jdk, sidecar, workflow


def replace_at(values, index, value):
    return (*values[:index], value, *values[index + 1 :])


@dataclass(frozen=True, slots=True)
class State:
    pcs: tuple
    owners: tuple
    logs: tuple
    seat_locks: tuple
    log_locks: tuple
    ack: tuple
    history: tuple


def initial(n):
    return State((0,) * n, (0,) * n, ((),) * n, (-1,) * n, (-1,) * n, ((),) * n, ())


def resources(shape, who):
    return (0 if shape == "alias" else who, 0 if shape == "shared-log" else who)


def outcome(s, shape):
    n = len(s.pcs)
    return (
        s.history,
        s.ack,
        tuple(s.owners[resources(shape, w)[0]] for w in range(n)),
        tuple(s.logs[resources(shape, w)[1]] for w in range(n)),
    )


def concrete(s, shape, limits, who, wrong=False):
    pc = s.pcs[who]
    if pc == 8 * limits[who]:
        return None
    phase = pc % 8
    seat, log = resources(shape, who)
    footprint_id = lambda real: who if wrong else real
    changed = replace(s, pcs=replace_at(s.pcs, who, pc + 1))
    if phase in (0, 7):
        return replace(changed, history=(*s.history, (who + 1) * (1 if phase == 0 else -1))), ("history", 0)
    if phase == 1:
        if s.seat_locks[seat] != -1:
            return None
        return replace(changed, seat_locks=replace_at(s.seat_locks, seat, who)), (
            "seat monitor",
            footprint_id(seat),
        )
    if s.seat_locks[seat] != who:
        raise ValueError("seat memory is outside its acquired monitor")
    if phase == 2:
        won = s.owners[seat] == 0
        owner = replace_at(s.owners, seat, who + 1) if won else s.owners
        return replace(changed, owners=owner, ack=replace_at(s.ack, who, (*s.ack[who], 1 if won else -1))), (
            "owner",
            footprint_id(seat),
        )
    if phase == 3:
        if s.log_locks[log] != -1:
            return None
        return replace(changed, log_locks=replace_at(s.log_locks, log, who)), (
            "audit monitor",
            footprint_id(log),
        )
    if phase == 6:
        return replace(changed, seat_locks=replace_at(s.seat_locks, seat, -1)), (
            "seat monitor",
            footprint_id(seat),
        )
    if s.log_locks[log] != who:
        raise ValueError("audit access outside its acquired monitor")
    if phase == 4:
        value = (who + 1) * s.ack[who][-1]
        return replace(changed, logs=replace_at(s.logs, log, (*s.logs[log], value))), (
            "audit sequence",
            footprint_id(log),
        )
    return replace(changed, log_locks=replace_at(s.log_locks, log, -1)), ("audit monitor", footprint_id(log))


def execute(shape, limits, strategy):
    n = len(limits)
    final = set()
    seen = set()
    transitions = pruned = 0
    stack = [(initial(n), frozenset())]
    while stack:
        s, sleep = stack.pop()
        node = (s, sleep)
        if node in seen:
            continue
        seen.add(node)
        if s.pcs == tuple(8 * c for c in limits):
            final.add(outcome(s, shape))
            continue
        enabled = {}
        for who in range(n):
            move = concrete(s, shape, limits, who, strategy == "by-name")
            if move:
                enabled[who] = move
        if not enabled:
            raise ValueError("unfinished deadlocked history")
        if strategy == "by-name":
            # A deliberately incorrect persistent set picks one named monitor
            # when two acquisitions appear independent. A second handle can
            # designate the same seat or the same ordered audit sink.
            seen_kinds = set()
            for who, (_, footprint) in tuple(enabled.items()):
                if s.pcs[who] % 8 in (1, 3):
                    kind = footprint[0]
                    if kind in seen_kinds:
                        del enabled[who]
                        pruned += 1
                    else:
                        seen_kinds.add(kind)
        prior = set(sleep)
        for who, (successor, resource_) in enabled.items():
            if who in prior:
                pruned += 1
                continue
            preserved = set()
            if strategy != "exhaustive":
                for other in prior:
                    if other in enabled and enabled[other][1] != resource_:
                        if strategy == "identity":
                            a = concrete(successor, shape, limits, other)
                            b = concrete(enabled[other][0], shape, limits, who)
                            if not a or not b or a[0] != b[0]:
                                raise ValueError("claimed independent transitions do not commute")
                        preserved.add(other)
                prior.add(who)
            transitions += 1
            stack.append((successor, frozenset(preserved)))
    return final, {"visitedStates": len(seen), "transitions": transitions, "sleepSetPruned": pruned}


def sequential(shape, limits):
    """Enumerate a linearization between each invocation and response. The audit append is inside both locks."""
    n = len(limits)
    final = set()
    seen = set()
    stack = [initial(n)]
    transitions = 0
    while stack:
        s = stack.pop()
        if s in seen:
            continue
        seen.add(s)
        if s.pcs == tuple(3 * k for k in limits):
            final.add(outcome(s, shape))
            continue
        for who, pc in enumerate(s.pcs):
            if pc == 3 * limits[who]:
                continue
            phase = pc % 3
            seat, log = resources(shape, who)
            after = replace(s, pcs=replace_at(s.pcs, who, pc + 1))
            if phase != 1:
                after = replace(after, history=(*s.history, (who + 1) * (1 if phase == 0 else -1)))
            else:
                ack = 1 if s.owners[seat] == 0 else -1
                after = replace(
                    after,
                    owners=replace_at(s.owners, seat, who + 1) if ack == 1 else s.owners,
                    ack=replace_at(s.ack, who, (*s.ack[who], ack)),
                    logs=replace_at(s.logs, log, (*s.logs[log], (who + 1) * ack)),
                )
            transitions += 1
            stack.append(after)
    return final, {"visitedStates": len(seen), "transitions": transitions}


def measured(shape, limits, strategy, destination):
    start = time.perf_counter()
    values, metrics = (
        sequential(shape, limits) if strategy == "sequential" else execute(shape, limits, strategy)
    )
    serial = sorted(json.dumps(x, separators=(",", ":")) for x in values)
    metrics.update(
        outcomes=len(serial),
        outcomesSha256=hashlib.sha256("\n".join(serial).encode()).hexdigest(),
        wallSeconds=round(time.perf_counter() - start, 6),
        peakProcessKiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    )
    destination.write_text(json.dumps({"metrics": metrics, "values": serial}))


def checked_code(jar, home, work, workers):
    classes = {}
    for name in ("seats/Seat", "seats/Audit", "seats/Handles"):
        data = runtime_jar.read_class(jar, name)
        if (
            not data
            or runtime_jar.this_class(data) != name
            or runtime_jar.super_class(data) != "java/lang/Object"
            or runtime_jar.interfaces(data)
            or ("<clinit>", "()V") in runtime_jar.methods(data)
        ):
            raise ValueError("unrepresented seat class or initializer")
        file = work / (name.split("/")[-1] + ".class")
        file.write_bytes(data)
        classes[name] = (*array_induction.methods(home / "bin/javap", file), runtime.sha256(file))

    def verify(name, method, desc, opcodes, members, flags=()):
        entry = classes[name][0][method, desc]
        code = entry["code"]
        if (
            entry["handlers"]
            or [op.op for op in code] != opcodes.split()
            or not set(flags) <= set(entry["header"].split())
            or any(code[i].member != value for i, value in members.items())
        ):
            raise ValueError(f"bytecode differs at {name}.{method}{desc}")
        return code

    reserve = verify(
        "seats/Seat",
        "reserve",
        "(ILseats/Audit;)Z",
        "aload_0 getfield ifeq aload_2 iload_1 ineg invokevirtual iconst_0 ireturn aload_0 iload_1 putfield aload_2 iload_1 invokevirtual iconst_1 ireturn",
        {
            1: "Field owner:I",
            6: "Method seats/Audit.append:(I)V",
            11: "Field owner:I",
            14: "Method seats/Audit.append:(I)V",
        },
        ("synchronized",),
    )
    if int(reserve[2].arg) != reserve[9].pc:
        raise ValueError("the branch no longer tests for an unowned seat")
    verify(
        "seats/Seat",
        "Seat",
        "()V",
        "aload_0 invokespecial return",
        {1: 'Method java/lang/Object."<init>":()V'},
    )
    append = verify(
        "seats/Audit",
        "append",
        "(I)V",
        "aload_0 getfield aload_0 getfield iload_1 iastore aload_0 dup getfield iconst_1 iadd putfield return",
        {1: "Field events:[I", 3: "Field used:I", 8: "Field used:I", 11: "Field used:I"},
        ("synchronized",),
    )
    init = verify(
        "seats/Audit",
        "Audit",
        "()V",
        "aload_0 invokespecial aload_0 bipush newarray putfield return",
        {1: 'Method java/lang/Object."<init>":()V', 5: "Field events:[I"},
    )
    if init[4].arg != "int" or int(init[3].arg) < workers * 2:
        raise ValueError("audit capacity cannot cover the admitted calls")
    handles = verify(
        "seats/Handles",
        "second",
        "(Lseats/Seat;Z)Lseats/Seat;",
        "iload_1 ifeq aload_0 goto new dup invokespecial areturn",
        {4: "class seats/Seat", 6: 'Method seats/Seat."<init>":()V'},
        ("static",),
    )
    if int(handles[1].arg) != handles[4].pc or int(handles[3].arg) != handles[-1].pc:
        raise ValueError("handle identity selection differs")
    return {
        "classes": {k: v[2] for k, v in classes.items()},
        "seat": list(map(vars, reserve)),
        "audit": list(map(vars, append)),
        "fact": "The seat stays locked from the first owner read until after the synchronized audit append. Audit methods acquire no seat monitor.",
    }


def run(folder, example, target, spec, workers):
    plan = route.resolve(folder, example, target, spec["bindingTask"])
    if isinstance(plan, interfaces.Unsupported) or tuple(plan.revisions) != (spec["revision"],):
        raise ValueError("no bound reservation subject")
    key = workflow.canonical_digest({"spec": spec, "lock": runtime.lock(plan, spec["revision"]).source})
    out = folder / "records/schedule-reduction"
    out.mkdir(parents=True, exist_ok=True)
    if workers == 3:
        previous = json.loads((out / "2-workers.json").read_text())
        if previous["sourceKey"] != key or not previous["exactOutcomeAgreement"]:
            raise ValueError("the two-worker corpus must agree first")
    rows = []
    jvm_matches = 0
    with tempfile.TemporaryDirectory(prefix="seat-reduction-") as temp:
        work = Path(temp)
        prepared = route.prepare_revision(plan, spec["revision"], work / "build", {})
        if isinstance(prepared, interfaces.Unsupported) or prepared.stage != "artifacts-ready":
            raise ValueError("seat preparation failed")
        (original,) = [a for a in runtime._checked(work / "build", prepared) if a.role == "original"]
        home = Path(runtime_jdk.home(plan.artifacts[0]["jdks"][0]))
        binding = checked_code(work / "build" / original.path, home, work, workers)
        if workers == 2:
            controls = runtime.run_controls(plan, {spec["revision"]: prepared}, work / "controls")
            if (
                isinstance(controls, interfaces.Unsupported)
                or len(controls) != 1
                or controls[0].exitCode != 0
            ):
                raise ValueError("the JVM controls failed")
            observations = controls[0].observations
        else:
            observations = ()
        context = multiprocessing.get_context("fork")
        for shape_index, shape in enumerate(("distinct", "alias", "shared-log")):
            for limits in product((1, 2), repeat=2) if workers == 2 else [(1,) * 3]:
                metrics = {}
                actual = {}
                for strategy in ("exhaustive", "identity", "sequential", "by-name"):
                    dest = work / "worker.json"
                    child = context.Process(target=measured, args=(shape, limits, strategy, dest))
                    child.start()
                    child.join()
                    if child.exitcode:
                        raise ValueError(f"{strategy} exited {child.exitcode}")
                    result = json.loads(dest.read_text())
                    metrics[strategy] = result["metrics"]
                    actual[strategy] = set(result["values"])
                full = actual["exhaustive"]
                if full != actual["identity"] or full != actual["sequential"]:
                    raise ValueError(f"body/POR/oracle disagreement at {shape} {limits}")
                if not actual["by-name"] <= full:
                    raise ValueError("negative reduction invented an outcome")
                for row in observations:
                    code = row["id"]
                    if code // 12 != shape_index or limits != (1 + (code // 6) % 2, 1 + (code // 3) % 2):
                        continue
                    events = sorted(
                        (tick, (w + 1) * sign)
                        for w in range(2)
                        for key_, sign in (("invoked", 1), ("returned", -1))
                        for tick in row[key_][w]
                        if tick
                    )
                    v = [
                        [event for _, event in events],
                        [a[:m] for a, m in zip(row["ack"], limits)],
                        row["owners"],
                        row["logs"],
                    ]
                    if json.dumps(v, separators=(",", ":")) not in full:
                        raise ValueError("real JVM history missing from exploration")
                    jvm_matches += 1
                missing = sorted(full - actual["by-name"])
                rows.append(
                    {
                        "shape": shape,
                        "calls": limits,
                        "measurements": metrics,
                        "byNameMissing": len(missing),
                        "firstMissing": json.loads(missing[0]) if missing else None,
                    }
                )
    if workers == 2 and jvm_matches != 36:
        raise ValueError("incomplete real JVM history coverage")
    for shape in ("alias", "shared-log"):
        if not any(row["byNameMissing"] for row in rows if row["shape"] == shape):
            raise ValueError("the by-name control failed to distinguish " + shape)
    report = {
        "schema": "java-seat-reduction/v1",
        "sourceKey": key,
        "workers": workers,
        "exactOutcomeAgreement": True,
        "scope": "completed calls under sequential consistency; fixed objects, monitors and audit capacity",
        "bytecode": binding,
        "originalJarSha256": original.sha256,
        "jdk": runtime_jdk.identity(home),
        "checkerSha256": runtime.sha256(Path(__file__)),
        "JVMHistoriesMatched": jvm_matches,
        "cases": rows,
    }
    (out / f"{workers}-workers.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"{workers} workers: {len(rows)} exact set comparisons and {jvm_matches} JVM histories")
    return 0


def evidence(folder, plan, spec):
    if spec["bindingTask"] != plan.task:
        return None
    locked = runtime.lock(plan, spec["revision"])
    if isinstance(locked, interfaces.Unsupported) or locked.stage != "source-locked":
        return None
    key = workflow.canonical_digest({"spec": spec, "lock": locked.source})
    completed = []
    for path in sorted((folder / "records/schedule-reduction").glob("*-workers.json")):
        doc = json.loads(path.read_text())
        if doc.get("sourceKey") != key or not doc.get("exactOutcomeAgreement"):
            continue
        if all(
            len(
                {
                    case["measurements"][name]["outcomesSha256"]
                    for name in ("exhaustive", "identity", "sequential")
                }
            )
            == 1
            for case in doc["cases"]
        ):
            completed.append(
                {
                    "workers": doc["workers"],
                    "cases": len(doc["cases"]),
                    "record": path.relative_to(folder).as_posix(),
                }
            )
    return {"sourceKey": key, "recorded": completed}


def main(argv):
    import build

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example")
    parser.add_argument("--workers", type=int, choices=(2, 3), default=2)
    a = parser.parse_args(argv)
    (folder,) = build.EXAMPLES.glob(a.example + "-*")
    example = build.load_example(folder)
    target = sidecar.load(folder, example)
    try:
        return run(folder, example, target, target["scheduleReduction"], a.workers)
    except (OSError, ValueError, KeyError) as e:
        parser.exit(1, f"schedule reduction unresolved: {e}\n")

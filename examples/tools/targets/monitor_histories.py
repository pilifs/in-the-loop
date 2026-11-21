"""Explore completed, sequentially consistent calls on a fixed monitor-protected Java heap.

Workers execute the selected method's compiled instructions. The main thread
executes explicit starts and joins. Invocation and response events determine real-time order.
"""

import argparse
from collections import deque
from dataclasses import dataclass, replace
from itertools import permutations
import json
from pathlib import Path
import re
import resource
import tempfile
import time

import jvm_disassembly
from targets import interfaces, route, runtime, runtime_jar, runtime_jdk, sidecar, workflow


@dataclass(frozen=True)
class Worker:
    pc: int = -2  # unstarted, then -1 waiting to invoke
    locals: tuple = ()
    stack: tuple = ()
    result: int | None = None  # -3 has returned
    pending: tuple = ()  # a call into the selected JDK wrapper, with its exact mutex


@dataclass(frozen=True)
class State:
    main: int
    workers: tuple
    monitors: tuple
    memory: tuple
    history: tuple


def set_slot(items, index, value):
    return (*items[:index], value, *items[index + 1 :])


def update_monitor(s, obj, worker, enter):
    owner, depth = s.monitors[obj]
    if enter:
        if owner not in (-1, worker):
            return None
        state = (worker, depth + 1)
    else:
        if owner != worker or not depth:
            raise ValueError("reachable monitorexit by a non-owner")
        state = (worker, depth - 1) if depth > 1 else (-1, 0)
    return replace(s, monitors=set_slot(s.monitors, obj, state))


class CounterProgram:
    def __init__(self, methods, selected, receiver="counter"):
        self.methods = methods
        self.method = methods[selected]
        self.code = {i.pc: i for i in self.method["code"]}
        self.follow = {i.pc: j.pc for i, j in zip(self.method["code"], self.method["code"][1:])}
        self.receiver = receiver
        self.synchronized = "synchronized " in self.method["header"]
        if any(i.op == "goto" and int(i.arg) <= i.pc for i in self.method["code"]):
            raise ValueError("a cyclic worker needs an explicit execution bound")
        fields = {i.member for i in self.method["code"] if i.op in ("getfield", "putfield")}
        if len(fields) != 1 or not re.fullmatch(r"Field [\w$]+:I", next(iter(fields))):
            raise ValueError("ticket method must access one identified int field of the receiver")
        self.field = fields.pop()

    def step(self, s, worker):
        w = s.workers[worker]
        if w.pc == -1:
            w = replace(w, pc=-4 if self.synchronized else 0, locals=(self.receiver,) + (None,) * 8)
            return replace(
                s, workers=set_slot(s.workers, worker, w), history=(*s.history, ("invoke", worker))
            ), "invoke"
        if w.pc == -4:
            s = update_monitor(s, 0, worker, True)
            if s is None:
                return None
            return replace(
                s, workers=set_slot(s.workers, worker, replace(w, pc=0))
            ), "acquire synchronized method"
        if w.pc == -5:
            return replace(
                s,
                workers=set_slot(s.workers, worker, replace(w, pc=-3)),
                history=(*s.history, ("return", worker)),
            ), "record response"
        ins = self.code[w.pc]
        pc = self.follow.get(w.pc)
        stack = list(w.stack)
        locals_ = list(w.locals)
        op, arg = ins.op, ins.arg
        if slot := re.fullmatch(r"([ai])(load|store)(?:_(\d))?", op):
            index = int(slot[3] or arg)
            if slot[2] == "store":
                locals_[index] = stack.pop()
            elif locals_[index] is not None:
                stack.append(locals_[index])
            else:
                raise ValueError("read of uninitialized local")
        elif op.startswith("iconst_"):
            stack.append(-1 if op == "iconst_m1" else int(op[7:]))
        elif op == "iadd":
            value = (stack.pop() + stack.pop()) & 0xFFFFFFFF
            stack.append(value - (1 << 32) if value & (1 << 31) else value)
        elif op == "dup":
            stack.append(stack[-1])
        elif op == "dup_x1":
            a, b = stack.pop(), stack.pop()
            stack.extend((a, b, a))
        elif op in ("getfield", "putfield"):
            if op == "putfield":
                value = stack.pop()
            if stack.pop() != self.receiver or ins.member != self.field:
                raise ValueError("unbound receiver or field")
            if op == "getfield":
                stack.append(s.memory[0])
            else:
                s = replace(s, memory=(value,))
        elif op in ("monitorenter", "monitorexit"):
            if stack.pop() != self.receiver:
                raise ValueError("unbound monitor")
            s = update_monitor(s, 0, worker, op == "monitorenter")
            if s is None:
                return None
        elif op == "goto":
            pc = int(arg)
        elif op == "invokevirtual":
            owner, member, descriptor = jvm_disassembly.member_call(ins)
            target = self.methods.get((member, descriptor))
            if (
                owner
                or descriptor != "()V"
                or stack.pop() != self.receiver
                or target is None
                or target["handlers"]
                or [i.op for i in target["code"]] != ["return"]
            ):
                raise ValueError("unrepresented virtual target on the selected exact receiver")
            if s.monitors[0][0] == worker:
                raise ValueError("the JVM witness gate is inside a held monitor")
        elif op == "ireturn":
            value = stack.pop()
            if stack:
                raise ValueError("unexpected stack at method return")
            if self.synchronized:
                s = update_monitor(s, 0, worker, False)
            if s.monitors[0][0] == worker:
                raise ValueError("method returned with an unreleased monitor")
            w = Worker(-5, result=value)
            return replace(s, workers=set_slot(s.workers, worker, w)), f"{ins.pc} ireturn {value}"
        else:
            raise ValueError(f"unsupported reachable instruction at {ins.pc}: {op}")
        w = Worker(pc, tuple(locals_), tuple(stack))
        return replace(s, workers=set_slot(s.workers, worker, w)), f"{ins.pc} {op}"

    @staticmethod
    def accepts(history, values, final):
        def position(event, worker):
            return history.index((event, worker))

        for first, second in permutations(range(2)):
            if position("return", second) < position("invoke", first):
                continue
            if (values[first], values[second], final) == (1, 2, 2):
                return True
        return False


def explore(program, mode):
    first = 1 if mode == "ba" else 0
    second = 1 - first
    actions = (
        (("start", first), ("start", second), ("join", first), ("join", second))
        if mode == "overlap"
        else (("start", first), ("join", first), ("start", second), ("join", second))
    )
    initial = State(0, (Worker(), Worker()), ((-1, 0),), getattr(program, "initial_memory", (0,)), ())
    seen = {initial: None}
    queue = deque([initial])
    transitions = 0
    stuck = 0
    finals = {}
    while queue:
        state = queue.popleft()
        if state.main == len(actions) and all(w.pc == -3 for w in state.workers):
            values = tuple(w.result for w in state.workers)
            key = (state.history, values, state.memory)
            finals.setdefault(key, state)
            continue
        moves = []
        if state.main < len(actions):
            action, who = actions[state.main]
            w = state.workers[who]
            if action == "start" and w.pc == -2:
                moves.append(
                    (
                        replace(state, main=state.main + 1, workers=set_slot(state.workers, who, Worker(-1))),
                        "main",
                        f"start {who}",
                    )
                )
            if action == "join" and w.pc == -3:
                moves.append((replace(state, main=state.main + 1), "main", f"join {who}"))
        for who, w in enumerate(state.workers):
            if w.pc >= -1 or w.pc in (-4, -5):
                nxt = program.step(state, who)
                if nxt:
                    moves.append((nxt[0], who, nxt[1]))
        if not moves:
            stuck += 1
        for nxt, actor, event in moves:
            transitions += 1
            if nxt not in seen:
                seen[nxt] = (state, (actor, event))
                queue.append(nxt)
    results = []
    for (history, values, memory), state in finals.items():
        trace = []
        while seen[state] is not None:
            state, step = seen[state]
            trace.append(step)
        observation = memory[0] if len(memory) == 1 else memory
        results.append(
            {
                "history": history,
                "returns": values,
                "field": observation,
                "linearizable": program.accepts(history, values, observation),
                "schedule": list(reversed(trace)),
            }
        )
    return {"visited": len(seen), "transitions": transitions, "blockedTerminal": stuck, "completed": results}


def source_key(plan, spec):
    locked = runtime.lock(plan, spec["revision"])
    if isinstance(locked, interfaces.Unsupported) or locked.stage != "source-locked":
        raise ValueError("the monitor method has no current source lock")
    return workflow.canonical_digest(
        {
            "model": "two-platform-thread-sc/v1",
            "contract": spec,
            "source": locked.source,
            "commit": locked.commit,
        }
    )


def run(folder, example, target, spec):
    start = time.monotonic()
    plan = route.resolve(folder, example, target, spec["bindingTask"])
    if isinstance(plan, interfaces.Unsupported) or tuple(plan.revisions) != (spec["revision"],):
        raise ValueError("the selected public task does not bind this subject")
    key = source_key(plan, spec)
    with tempfile.TemporaryDirectory(prefix="monitor-histories-") as directory:
        work = Path(directory)
        prepared = route.prepare_revision(plan, spec["revision"], work / "build", {})
        if isinstance(prepared, interfaces.Unsupported) or prepared.stage != "artifacts-ready":
            raise ValueError(f"preparation failed: {prepared}")
        entries = runtime._checked(work / "build", prepared)
        (original,) = [a for a in entries if a.role == "original"]
        jar = work / "build" / original.path
        owner, name, desc = runtime_jar.parse_target(spec["entry"])
        data = runtime_jar.read_class(jar, owner.replace(".", "/"))
        is_map = spec.get("model") == "synchronized-map"
        expected_desc = "(Ljava/lang/String;Ljava/lang/String;)Z" if is_map else "()I"
        if (
            not data
            or desc != expected_desc
            or runtime_jar.super_class(data) != "java/lang/Object"
            or runtime_jar.interfaces(data)
        ):
            raise ValueError("unsupported receiver layout or entry")
        (feat,) = plan.artifacts[0]["jdks"]
        jdk = Path(runtime_jdk.home(feat))
        file = work / (owner.split(".")[-1] + ".class")
        file.write_bytes(data)
        code, dis = jvm_disassembly.methods(jdk / "bin/javap", file)
        ctor = code.get((owner.split(".")[-1], "()V"))
        if ("<clinit>", "()V") in runtime_jar.methods(data):
            raise ValueError("unrepresented receiver startup")
        if not is_map and (
            not ctor
            or [i.op for i in ctor["code"]] != ["aload_0", "invokespecial", "return"]
            or ctor["code"][1].member != 'Method java/lang/Object."<init>":()V'
            or ("<clinit>", "()V") in runtime_jar.methods(data)
        ):
            raise ValueError("unrepresented receiver construction or startup")
        if is_map:
            from targets import synchronized_map

            p = synchronized_map.MapProgram(code, (name, desc), jdk, work, False)
            results = {}
            for distinct in (False, True):
                p.distinct = distinct
                for mode in ("ab", "ba", "overlap"):
                    results[("distinct-" if distinct else "same-") + mode] = explore(p, mode)
        else:
            p = CounterProgram(code, (name, desc))
            results = {mode: explore(p, mode) for mode in ("ab", "ba", "overlap")}
        if any(not m["completed"] or m["blockedTerminal"] for m in results.values()):
            raise ValueError("unfinished or vacuous bounded execution")
        # The independent real-thread control's concrete ordering and terminal heap must occur in the execution set.
        controls = runtime.run_controls(plan, {spec["revision"]: prepared}, work / "controls")
        if isinstance(controls, interfaces.Unsupported) or len(controls) != 1 or controls[0].exitCode != 0:
            raise ValueError("the real JVM thread control did not complete")
        matched = []
        for row in controls[0].observations:
            mode = ("ab", "ba", "overlap")[row["mode"]]
            if is_map:
                mode = ("distinct-" if row["distinct"] else "same-") + mode
                values = row["success"]
                final = tuple((None, "A", "B").index(owner) for owner in row["owners"])
                if row["size"] != sum(value != 0 for value in final):
                    raise ValueError("reported map size and stored owners disagree")
            else:
                values, final = row["tickets"], row["final"]
            events = sorted(
                [(t, ("invoke", i)) for i, t in enumerate(row["invoked"])]
                + [(t, ("return", i)) for i, t in enumerate(row["returned"])]
            )
            history = tuple(event for _, event in events)
            match = next(
                (
                    r
                    for r in results[mode]["completed"]
                    if r["history"] == history and list(r["returns"]) == values and r["field"] == final
                ),
                None,
            )
            if match is None:
                raise ValueError(f"JVM thread history outside the bytecode exploration at {mode}")
            matched.append(
                {
                    "mode": mode,
                    "jvm": row,
                    "linearizable": match["linearizable"],
                    "matchingSchedule": match["schedule"],
                }
            )
        if len(matched) != len(results) or {r["mode"] for r in matched} != set(results):
            raise ValueError("the JVM control omitted an invocation order")
        refuted = any(not r["linearizable"] for x in results.values() for r in x["completed"])
        if refuted and all(r["linearizable"] for r in matched):
            raise ValueError("the non-linearizable history needs a real JVM replay")
        doc = {
            "schema": "java-monitor-histories/v1",
            "sourceKey": key,
            "entry": spec["entry"],
            "revision": spec["revision"],
            "status": "refuted" if refuted else "established",
            "scope": {
                "memory": "sequentially consistent",
                "threads": 2,
                "callsPerThread": 1,
                "receivers": 1,
                "initialValue": 0,
                "completedCalls": 2,
                "allocation": "one exact receiver and two fixed worker identities",
                "scheduling": "all enabled compiled instructions plus start and join",
            },
            "originalJarSha256": original.sha256,
            "classSha256": runtime.sha256(file),
            "synchronizedMethod": p.synchronized,
            "field": p.field,
            "jdk": runtime_jdk.identity(jdk),
            "disassembly": dis,
            "explorations": results,
            "jvmReplays": matched,
            "checkerSha256": runtime.sha256(Path(__file__)),
            "wallSeconds": round(time.monotonic() - start, 5),
            "peakProcessKiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }
        if is_map:
            doc["scope"]["allocation"] = (
                "one reservation receiver, one synchronized wrapper and its private HashMap, two fixed workers and up to two named keys"
            )
            doc["scope"]["initialValue"] = "empty map"
            doc["jdkWrapper"] = {
                "classes": p.classes,
                "methods": p.wrapper,
                "mutex": "the wrapper itself",
                "delegate": p.delegate,
                "translatorSha256": runtime.sha256(Path(synchronized_map.__file__)),
            }
        dest = folder / "records/monitor-histories" / spec["id"] / workflow.canonical_digest(doc)[:20]
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "result.json").write_text(json.dumps(doc, indent=2) + "\n")
        print(
            spec["id"],
            doc["status"],
            {k: (v["visited"], v["transitions"], len(v["completed"])) for k, v in results.items()},
        )
        return doc["status"] == spec["expected"]


def evidence(folder, target, plan):
    result = []
    for spec in target.get("monitorContracts", []):
        if spec["bindingTask"] != plan.task:
            continue
        key = source_key(plan, spec)
        entry = {
            "id": spec["id"],
            "subject": spec["entry"],
            "sourceKey": key,
            "threads": 2,
            "callsPerThread": 1,
        }
        root = folder / "records/monitor-histories" / spec["id"]
        matched = []
        for path in [root / "result.json", *sorted(root.glob("*/result.json"))]:
            if not path.is_file():
                continue
            doc = json.loads(path.read_text())
            runs = doc.get("explorations", {})
            if (doc.get("sourceKey") != key or not runs or not doc.get("jvmReplays")
                or any(run.get("blockedTerminal") or not run.get("completed") for run in runs.values())):
                continue
            status = "refuted" if any(not row["linearizable"] for run in runs.values() for row in run["completed"]) else "established"
            if doc.get("status") == status:
                matched.append({"status": status, "record": path.relative_to(folder).as_posix()})
        if matched:
            entry.update(matched[-1], records=matched)
        result.append(entry)
    return result


def main(argv):
    import build

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example")
    parser.add_argument("contract")
    a = parser.parse_args(argv)
    (folder,) = build.EXAMPLES.glob(a.example + "-*")
    example = build.load_example(folder)
    target = sidecar.load(folder, example)
    match = [s for s in target["monitorContracts"] if s["id"] == a.contract]
    if len(match) != 1:
        parser.error("expected one declared bounded monitor contract")
    try:
        return 0 if run(folder, example, target, match[0]) else 1
    except (OSError, ValueError, KeyError, IndexError) as error:
        parser.exit(1, f"{a.contract}: {error}\n")

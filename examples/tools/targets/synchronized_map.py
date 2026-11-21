"""Code-checked monitor transitions of the stock synchronized-map wrapper on a finite private HashMap."""

import hashlib
import re
import subprocess
import zipfile
from dataclasses import replace
from itertools import permutations
from pathlib import Path

import jvm_disassembly
from targets import runtime, runtime_jar


def signature(ins):
    return re.sub(r"^(?:InterfaceMethod|Method) ", "", ins.member)


def member(ins):
    return ins.member.removeprefix("Field ")


def ops(method):
    return [i.op for i in method["code"]]


def delegate_table(java, work):
    driver = Path(__file__).with_name("java") / "MapTransitions.java"
    raw = subprocess.check_output([java, driver])
    table = {}
    histories = set()
    count = 0
    for row in raw.splitlines():
        length, word, a, b, key, action, value, new_a, new_b, size = map(int, row.split())
        histories.add((length, word))
        before = (a, b)
        after = (new_a, new_b)
        transition = (value, after)
        if size != sum(v != 0 for v in after) or key not in (0, 1) or action not in (0, 1, 2):
            raise ValueError("invalid finite delegate observation")
        if table.setdefault((before, key, action), transition) != transition:
            raise ValueError("two reachable HashMap layouts disagree on the proposed abstraction")
        count += 1
    expected = {(n, w) for n in range(3) for w in range(4**n)}
    if histories != expected or count != 62:
        raise ValueError("incomplete two-write HashMap transition corpus")
    return table, {
        "writeHistories": len(histories),
        "calls": count,
        "stdoutSha256": hashlib.sha256(raw).hexdigest(),
        "driverSha256": runtime.sha256(driver),
        "rows": raw.decode().splitlines(),
    }


def wrapper(jdk, work):
    names = (
        "java/util/Collections",
        "java/util/Collections$SynchronizedMap",
        "java/util/HashMap",
        "java/lang/String",
    )
    classes = {}
    with zipfile.ZipFile(jdk / "jmods/java.base.jmod") as image:
        for name in names:
            data = image.read("classes/" + name + ".class")
            if runtime_jar.this_class(data) != name:
                raise ValueError("mismatched class from the selected runtime image")
            classes[name] = hashlib.sha256(data).hexdigest()
            file = work / (name.split("/")[-1] + ".class")
            file.write_bytes(data)
    factory, _ = jvm_disassembly.methods(jdk / "bin/javap", work / "Collections.class")
    methods, _ = jvm_disassembly.methods(jdk / "bin/javap", work / "Collections$SynchronizedMap.class")
    factory = factory["synchronizedMap", "(Ljava/util/Map;)Ljava/util/Map;"]
    c = factory["code"]
    cls = "java/util/Collections$SynchronizedMap"
    if (
        ops(factory) != ["new", "dup", "aload_0", "invokespecial", "areturn"]
        or c[0].member != "class " + cls
        or signature(c[3]) != cls + '."<init>":(Ljava/util/Map;)V'
    ):
        raise ValueError("unrecognized synchronizedMap factory")
    ctor = methods["Collections$SynchronizedMap", "(Ljava/util/Map;)V"]
    c = ctor["code"]
    if (
        ops(ctor)
        != [
            "aload_0",
            "invokespecial",
            "aload_0",
            "aload_1",
            "invokestatic",
            "checkcast",
            "putfield",
            "aload_0",
            "aload_0",
            "putfield",
            "return",
        ]
        or signature(c[1]) != 'java/lang/Object."<init>":()V'
        or signature(c[4]) != "java/util/Objects.requireNonNull:(Ljava/lang/Object;)Ljava/lang/Object;"
        or c[5].member != "class java/util/Map"
        or member(c[6]) != "m:Ljava/util/Map;"
        or member(c[9]) != "mutex:Ljava/lang/Object;"
    ):
        raise ValueError("the wrapper does not store the private map and use itself as mutex")
    bindings = {}
    for name, desc, n, ret in (
        ("containsKey", "(Ljava/lang/Object;)Z", 1, "ireturn"),
        ("put", "(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;", 2, "areturn"),
        ("get", "(Ljava/lang/Object;)Ljava/lang/Object;", 1, "areturn"),
        ("size", "()I", 0, "ireturn"),
    ):
        method = methods[name, desc]
        instructions = method["code"]
        normal = instructions[: next(i + 1 for i, x in enumerate(instructions) if x.op == ret)]
        slot = n + 1
        want = [
            "aload_0",
            "getfield",
            "dup",
            f"astore_{slot}",
            "monitorenter",
            "aload_0",
            "getfield",
            *[f"aload_{i + 1}" for i in range(n)],
            "invokeinterface",
            f"aload_{slot}",
            "monitorexit",
            ret,
        ]
        if (
            [i.op for i in normal] != want
            or member(normal[1]) != "mutex:Ljava/lang/Object;"
            or member(normal[6]) != "m:Ljava/util/Map;"
            or signature(normal[7 + n]) != f"java/util/Map.{name}:{desc}"
        ):
            raise ValueError(f"unsupported bytecode for the wrapper's {name}")
        # The admitted non-null receiver, exact String keys and measured private HashMap operation return normally.
        bindings[name] = {
            "descriptor": desc,
            "acquire": normal[4].pc,
            "call": normal[7 + n].pc,
            "release": normal[-2].pc,
            "return": normal[-1].pc,
            "normalBytecode": [vars(i) for i in normal],
        }
    return classes, bindings


class MapProgram:
    def __init__(self, methods, selected, jdk, work, distinct):
        self.methods = methods
        self.method = methods[selected]
        self.distinct = distinct
        self.code = {i.pc: i for i in self.method["code"]}
        self.follow = {i.pc: j.pc for i, j in zip(self.method["code"], self.method["code"][1:])}
        self.field = "private HashMap contents through the synchronized wrapper"
        self.synchronized = False
        self.initial_memory = (0, 0)
        if "static" in self.method["header"].split() or "synchronized" in self.method["header"].split():
            raise ValueError("unrepresented reservation method flags")
        ctor = methods["Slots", "()V"]
        c = ctor["code"]
        if (
            ops(ctor)
            != [
                "aload_0",
                "invokespecial",
                "aload_0",
                "new",
                "dup",
                "invokespecial",
                "invokestatic",
                "putfield",
                "return",
            ]
            or signature(c[1]) != 'java/lang/Object."<init>":()V'
            or c[3].member != "class java/util/HashMap"
            or signature(c[5]) != 'java/util/HashMap."<init>":()V'
            or signature(c[6]) != "java/util/Collections.synchronizedMap:(Ljava/util/Map;)Ljava/util/Map;"
            or member(c[7]) != "slots:Ljava/util/Map;"
        ):
            raise ValueError("unrepresented allocation of the receiver, wrapper or private delegate")
        self.classes, self.wrapper = wrapper(jdk, work)
        self.table, self.delegate = delegate_table(jdk / "bin/java", work)
        if any(i.op == "goto" and int(i.arg) <= i.pc for i in self.method["code"]):
            raise ValueError("a cyclic worker needs an execution bound")

    def step(self, s, worker):
        from targets.monitor_histories import Worker, set_slot, update_monitor

        w = s.workers[worker]

        def advance(worker_state, event):
            return replace(s, workers=set_slot(s.workers, worker, worker_state)), event

        if w.pc == -1:
            loc = ("receiver", 1 if self.distinct and worker == 1 else 0, worker + 1, None, None, None)
            s = replace(s, history=(*s.history, ("invoke", worker)))
            return advance(Worker(0, locals=loc), "invoke reservation")
        if w.pc == -5:
            s = replace(s, history=(*s.history, ("return", worker)))
            return advance(replace(w, pc=-3), "record response")
        if w.pending:
            operation, key, action, phase, value = w.pending
            code = self.wrapper[operation]
            if phase in ("acquire", "release"):
                s = update_monitor(s, 0, worker, phase == "acquire")
                if s is None:
                    return None
            elif phase == "call":
                if s.monitors[0][0] != worker:
                    raise ValueError("unsynchronized delegate access")
                value, after = self.table[s.memory, key, action]
                s = replace(s, memory=after)
            next_phase = {"acquire": "call", "call": "release", "release": "return", "return": None}[phase]
            new = (
                replace(w, pending=(operation, key, action, next_phase, value))
                if next_phase
                else replace(w, pending=(), stack=(*w.stack, value))
            )
            return advance(new, f"SynchronizedMap.{operation} {code[phase]} {phase}")
        i = self.code[w.pc]
        pc = self.follow.get(w.pc)
        stack = list(w.stack)
        local = list(w.locals)
        op = i.op
        pending = ()
        if slot := re.fullmatch(r"([ai])(load|store)(?:_(\d))?", op):
            idx = int(slot[3] or i.arg)
            if slot[2] == "store":
                local[idx] = stack.pop()
            else:
                stack.append(local[idx])
        elif op == "getfield":
            if stack.pop() != "receiver" or member(i) != "slots:Ljava/util/Map;":
                raise ValueError("unbound shared field")
            stack.append("wrapper")
        elif op == "dup":
            stack.append(stack[-1])
        elif op == "pop":
            stack.pop()
        elif op in ("iconst_0", "iconst_1"):
            stack.append(int(op[-1]))
        elif op in ("ifeq", "ifne"):
            value = stack.pop()
            if (value == 0) == (op == "ifeq"):
                pc = int(i.arg)
        elif op == "goto":
            pc = int(i.arg)
        elif op in ("monitorenter", "monitorexit"):
            if stack.pop() != "wrapper":
                raise ValueError("the app locks a different monitor")
            s = update_monitor(s, 0, worker, op == "monitorenter")
            if s is None:
                return None
        elif op == "invokeinterface":
            sig = signature(i)
            if sig == "java/util/Map.containsKey:(Ljava/lang/Object;)Z":
                operation, action = "containsKey", 0
            elif sig == "java/util/Map.put:(Ljava/lang/Object;Ljava/lang/Object;)Ljava/lang/Object;":
                operation, action = "put", stack.pop()
            else:
                raise ValueError(f"unrepresented wrapper call {sig}")
            key = stack.pop()
            if stack.pop() != "wrapper":
                raise ValueError("receiver differs from the validated wrapper")
            pending = (operation, key, action, "acquire", 0)
        elif op == "invokevirtual":
            sig = signature(i)
            if (
                sig != "between:()V"
                or stack.pop() != "receiver"
                or ops(self.methods["between", "()V"]) != ["return"]
                or s.monitors[0][0] == worker
            ):
                raise ValueError("unrepresented reservation hook or held mutex")
        elif op == "ireturn":
            value = stack.pop()
            if stack or s.monitors[0][0] == worker:
                raise ValueError("unreleased reservation state")
            return advance(Worker(-5, result=value), f"{i.pc} ireturn {value}")
        else:
            raise ValueError(f"unsupported reachable reservation instruction {i.pc} {op}")
        return advance(Worker(pc, tuple(local), tuple(stack), pending=pending), f"{i.pc} {op}")

    def accepts(self, history, values, final):
        for first, second in permutations(range(2)):
            if history.index(("return", second)) < history.index(("invoke", first)):
                continue
            table = [0, 0]
            success = [0, 0]
            for who in (first, second):
                key = who if self.distinct else 0
                if not table[key]:
                    table[key] = who + 1
                    success[who] = 1
            if tuple(success) == values and tuple(table) == final:
                return True
        return False

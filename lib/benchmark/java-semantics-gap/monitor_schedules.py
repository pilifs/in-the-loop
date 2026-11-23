"""Explore the original monitor caller and worker one JVM instruction at a time under sequential consistency."""
from collections import Counter
from dataclasses import dataclass, replace
from functools import cache
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from campaign import JDK, ROOT, compile_java, digest, javaenv, write
from heap_and_monitors import schedules
import jvm_disassembly

sys.path.insert(0, str(ROOT / "examples/tools"))
from targets.monitor_histories import set_slot, update_monitor
from targets.runtime_jar import super_class

CALLER = "MonitorIdentity"
WORKER = CALLER + "$Worker"
INSTANCE, MIRROR = "worker instance", "Worker.class"
MODES = ("matched", "mixed", "synchronizedMethod")


@dataclass(frozen=True)
class Frame:
    method: tuple
    pc: int
    locals: tuple
    stack: tuple = ()
    lock: str | None = None


@dataclass(frozen=True)
class State:
    threads: tuple
    monitors: tuple = ((-1, 0), (-1, 0))
    allocated: bool = False
    started: bool = False
    static_method: int = 0
    shared: int = 0
    first_read: int | None = None
    result: int | None = None


def frame(method, args, lock=None):
    return Frame(method, 0, tuple(args) + (None,) * (6 - len(args)), lock=lock)


class Program:
    def __init__(self, classes):
        self.code = {}
        self.synchronized = set()
        self.disassembly = {}
        for owner in (CALLER, WORKER):
            classfile = classes / (owner + ".class")
            parent = "java/lang/Thread" if owner == WORKER else "java/lang/Object"
            if super_class(classfile.read_bytes()) != parent:
                raise ValueError(f"{owner}: unexpected superclass for this schedule")
            methods, disassembly = jvm_disassembly.methods(JDK / "bin/javap", classfile)
            self.disassembly[owner] = disassembly
            if ("<clinit>", "()V") in methods:
                raise ValueError("the schedule scope requires default static initialization")
            for (name, descriptor), m in methods.items():
                key = owner, "<init>" if name == owner else name, descriptor
                if "synchronized" in m["header"].split():
                    if "static" not in m["header"].split() or owner != WORKER:
                        raise ValueError("unexpected implicit monitor")
                    self.synchronized.add(key)
                insns = m["code"]
                self.code[key] = {ins.pc: (ins, nxt.pc if nxt else -1)
                                  for ins, nxt in zip(insns, [*insns[1:], None])}
        if any((WORKER, m, "()V") in self.code for m in ("start", "join")):
            raise ValueError("the worker overrides a modeled lifecycle call")

    def step(self, state, actor, ignore_static):
        frames = state.threads[actor]
        f = frames[-1]
        owner = f.method[0]
        ins, pc = self.code[f.method][f.pc]
        op = ins.op
        stack, locals_ = list(f.stack), list(f.locals)
        event = None
        nested = None

        def monitor(s, lock, enter):
            return update_monitor(s, (INSTANCE, MIRROR).index(lock), actor, enter)

        local = re.fullmatch(r"[ai](load|store)(?:_(\d+))?", op)
        if local:
            i = int(local[2] or ins.arg)
            if local[1] == "load":
                if locals_[i] is None: raise ValueError("read an unset local")
                stack.append(locals_[i])
            else:
                locals_[i] = stack.pop()
        elif op.startswith("iconst_") or op == "bipush":
            stack.append(int(ins.arg if op == "bipush" else op[7:]))
        elif op == "dup":
            stack.append(stack[-1])
        elif op in ("new", "ldc") and ins.member == "class " + WORKER:
            if op == "new":
                if state.allocated: raise ValueError("a second worker allocation")
                state = replace(state, allocated=True)
            stack.append(INSTANCE if op == "new" else MIRROR)
        elif op in ("putfield", "getfield") and ins.member in ("Field staticMethod:Z", "Field " + WORKER + ".staticMethod:Z"):
            value = stack.pop() if op == "putfield" else state.static_method
            if stack.pop() != INSTANCE: raise ValueError("invalid worker receiver")
            if op == "putfield": state = replace(state, static_method=value)
            else: stack.append(value)
        elif op in ("putstatic", "getstatic") and ins.member in ("Field shared:I", "Field " + CALLER + ".shared:I"):
            if op == "putstatic":
                state = replace(state, shared=stack.pop())
            else:
                stack.append(state.shared)
                if actor == 0 and state.first_read is None: state = replace(state, first_read=state.shared)
            event = f"{op} shared={state.shared}"
        elif op in ("ifeq", "if_icmpne", "goto"):
            take = True
            if op == "ifeq": take = stack.pop() == 0
            if op == "if_icmpne": take = stack.pop() != stack.pop()
            if take:
                pc = int(ins.arg)
                if pc <= ins.pc: raise ValueError("cyclic bytecode requires a separate bound")
        elif op in ("monitorenter", "monitorexit"):
            lock = stack.pop()
            state = monitor(state, lock, op == "monitorenter")
            if state is None: return None
            event = f"{op} {lock}"
        elif op in ("invokespecial", "invokevirtual", "invokestatic"):
            target = re.fullmatch(r'Method (?:(.+)\.)?("?[\w$<>]+"?):(\([^)]*\).+)', ins.member)
            if not target: raise ValueError(f"unsupported call {ins.member}")
            cls, name, desc = target.groups()
            cls, name = cls or owner, name.strip('"')
            target = cls, name, desc
            if desc not in ("()V", "(ZZ)Z"): raise ValueError(f"unsupported call {target}")
            args = []
            if desc == "(ZZ)Z":
                args = stack[-2:]
                del stack[-2:]
            if op != "invokestatic":
                receiver = stack.pop()
                if receiver != INSTANCE: raise ValueError("a call on an unknown object")
                args.insert(0, receiver)
            if target == ("java/lang/Thread", "<init>", "()V"):
                event = "successful platform-thread construction"
            elif target == (WORKER, "start", "()V"):
                if actor != 0 or state.started: raise ValueError("more than one worker start")
                worker = (frame((WORKER, "run", "()V"), [INSTANCE]),)
                state = replace(state, started=True, threads=set_slot(state.threads, 1, worker))
                event = "start worker"
            elif target == (WORKER, "join", "()V"):
                if not state.started: raise ValueError("join before start")
                if state.threads[1]: return None
                event = "join finished worker"
            else:
                if target not in self.code: raise ValueError(f"unmodeled target {target}")
                lock = None
                if target in self.synchronized and not ignore_static:
                    lock = MIRROR
                    state = monitor(state, lock, True)
                    if state is None: return None
                    event = "enter static synchronized method on " + lock
                nested = frame(target, args, lock)
        elif op in ("ireturn", "return"):
            value = stack.pop() if op == "ireturn" else None
            if stack: raise ValueError("unexpected operands at return")
            if f.lock:
                state = monitor(state, f.lock, False)
                event = "release implicit " + f.lock
            remaining = frames[:-1]
            if value is not None:
                if remaining:
                    parent = remaining[-1]
                    remaining = (*remaining[:-1], replace(parent, stack=(*parent.stack, value)))
                else:
                    state = replace(state, result=value)
            if not remaining: event = f"return {value}" if actor == 0 else "worker finished"
            return replace(state, threads=set_slot(state.threads, actor, remaining)), event
        else:
            raise ValueError(f"unmodeled reachable instruction {f.method} at {ins.pc}: {op}")
        frames = (*frames[:-1], replace(f, pc=pc, stack=tuple(stack), locals=tuple(locals_)))
        if nested: frames = (*frames, nested)
        return replace(state, threads=set_slot(state.threads, actor, frames)), event

    def explore(self, mode, ignore_static=False):
        first = State(((frame((CALLER, mode, "()Z"), []),), ()))
        transitions = 0
        witnesses = {}
        # Each instruction chooses one runnable actor. Memoization combines equal entire states and
        # counts every completed scheduling sequence represented there, including local instructions.
        @cache
        def visit(state):
            nonlocal transitions
            if not any(state.threads):
                if not state.started or state.result not in (0,1) or any(depth for _,depth in state.monitors):
                    raise ValueError("incomplete schedule or unreleased monitor")
                return Counter({(state.first_read, state.shared, state.result): 1})
            counts = Counter()
            for actor, frames in enumerate(state.threads):
                if not frames: continue
                step = self.step(state, actor, ignore_static)
                if step is None: continue
                successor, event = step
                transitions += 1
                for outcome, count in visit(successor).items():
                    if outcome not in counts:
                        witnesses[state, outcome] = successor, actor, event
                    counts[outcome] += count
            if not counts: raise ValueError("a reachable state is deadlocked")
            return counts

        rows = []
        for outcome, count in sorted(visit(first).items()):
            state = first
            events = []
            while (state, outcome) in witnesses:
                successor, actor, event = witnesses[state, outcome]
                if event:
                    f = state.threads[actor][-1]
                    events.append([("caller", "worker")[actor], f.method[0]+"."+f.method[1], f.pc, event])
                state = successor
            read, final, result = outcome
            rows.append({"read": read, "joinedValue": final, "returned": bool(result),
                         "instructionSchedules": count, "witness": events})
        return {"states": visit.cache_info().currsize, "transitions": transitions, "outcomes": rows}


def main():
    directory = ROOT / "examples/391-class-monitor-identity"
    receipt = ROOT / "verification/java-semantics-gap/qualified/monitors/measurement.json"
    frozen = json.loads(receipt.read_bytes())
    dest = ROOT / "verification/java-semantics-gap/monitor-schedules"
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="monitor-schedules-") as tmp:
        work = Path(tmp)
        classes = work / "classes"
        source = directory / "adapter/MonitorIdentity.java"
        compile_java([source], classes, [], javaenv())
        hashes = {c.name: digest(c) for c in classes.glob("*.class")}
        if hashes != frozen["classes"] or digest(source) != frozen["adapterSha256"]:
            raise ValueError("monitor class files differ from the frozen original")
        program = Program(classes)
        listings = {}
        for owner, body in program.disassembly.items():
            listing = dest / (owner + ".javap")
            listing.write_text(body)
            listings[owner] = {"file": listing.name, "sha256": digest(listing)}
        runs = {mode: program.explore(mode) for mode in MODES}
        ignored = program.explore("synchronizedMethod", ignore_static=True)
        def results(row): return {(v["read"], v["joinedValue"], v["returned"]) for v in row["outcomes"]}
        protected = {(5, 6, True)}
        mixed = protected | {(6, 6, False)}
        if any(results(row) != (mixed if name=="mixed" else protected) for name,row in runs.items()) or results(ignored) != mixed:
            raise ValueError("original monitor observations or modifier control disagree")
        original = schedules(work, reader_first=True)
        if any(original["classes"].get(name) != sha for name,sha in hashes.items()):
            raise ValueError("the physical JVM and schedule checker must use the same original classes")
        if original["runs"]["mixed-reader-first"]["observations"] != [
                "mixed after the original read=5 saved=true", "original result=protected"]:
            raise ValueError("the reader-first witness did not reproduce the saved result")
        write(dest/"measurement.json", {"source":os.environ.get("VERIFY_SOURCE_COMMIT"), "job":os.environ.get("VERIFY_JOB_ID"),
              "classes":hashes, "adapterSha256":digest(source), "jdkModulesSha256":digest(JDK/"lib/modules"),
              "modelSha256":digest(__file__), "monitorRulesSha256":digest(ROOT/"examples/tools/targets/monitor_histories.py"),
              "disassemblerSha256":digest(JDK/"bin/javap"), "listings":listings,
              "scope":"All completed sequentially consistent instruction interleavings of the original caller and one worker. Construction, start and uninterrupted join succeed. A lifecycle call is one model transition. Counts omit idle steps, allocation failures and asynchronous exceptions.",
              "runs":runs, "ignoringStaticSynchronized":ignored, "originalJvm":original})
        print({k: [(v["read"],v["returned"],v["instructionSchedules"]) for v in r["outcomes"]] for k,r in runs.items()})


if __name__ == "__main__":
    main()


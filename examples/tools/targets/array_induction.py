"""Inductive verification of a linear Java array traversal on its compiled control-flow graph.

An arbitrary signed 32-bit index observes the heap. The base, back edges, each
return, array access and termination measure are independent SMT obligations.
Unsupported reachable bytecode prevents certification.
"""

import argparse
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

from targets import interfaces, route, runtime, runtime_jar, runtime_jdk, sidecar, workflow


ZERO = "#x00000000"
ONE = "#x00000001"
NEG_ONE = "#xffffffff"
BV = "(_ BitVec 32)"
ARRAY = f"(Array {BV} {BV})"
COMPARE = {"eq": "=", "ne": "distinct", "lt": "bvslt", "le": "bvsle", "gt": "bvsgt", "ge": "bvsge"}


def term(op, *values):
    return "(" + " ".join((op, *values)) + ")"


def both(*values):
    return term("and", *values) if len(values) > 1 else values[0] if values else "true"


def between(lower, value, upper):
    return both(term("bvsle", lower, value), term("bvslt", value, upper))


def word(value):
    return f"#x{value & 0xFFFFFFFF:08x}"


@dataclass(frozen=True)
class Instruction:
    pc: int
    op: str
    arg: str
    member: str


def methods(javap, class_file):
    """Use the pinned JDK disassembler on the exact class file, never a class resolved by javap's search path."""
    dis = subprocess.check_output([javap, "-p", "-c", "-s", class_file], text=True)
    parsed = {}
    header = None
    key = None
    for line in dis.splitlines():
        if re.match(r"^  \S", line):
            header, key = line.strip(), None
        elif header and line.startswith("    descriptor:"):
            if "(" in header or header == "static {};":
                name = (
                    "<clinit>" if header == "static {};" else header.split("(")[0].split()[-1].split(".")[-1]
                )
                key = (name, line.split()[-1])
                parsed[key] = {"header": header, "code": [], "handlers": False}
        elif key and "Exception table:" in line:
            parsed[key]["handlers"] = True
        elif key and (match := re.fullmatch(r"\s*(\d+):\s+(\w+)(?:\s+(.*?))?\s*", line)):
            arg, _, member = (match[3] or "").partition("//")
            parsed[key]["code"].append(Instruction(int(match[1]), match[2], arg.strip(), member.strip()))
    return parsed, dis


@dataclass
class State:
    locals: dict
    stack: tuple = ()
    heap: str = "initial"
    path: tuple = ()

    def push(self, value):
        return replace(self, stack=(*self.stack, value))

    def pop(self):
        if not self.stack:
            raise ValueError("operand stack underflow")
        return self.stack[-1], replace(self, stack=self.stack[:-1])


class Induction:
    def __init__(self, code, rule):
        self.code = code
        self.rule = rule
        self.conditions = []
        self.trace = []

    def vc(self, label, path, conclusion):
        self.conditions.append((label, both(*path), conclusion))

    def walk(self, method, state, pc, stop=None, path_pcs=()):
        """Follow actual branch targets; one cut at the selected loop head defines a transition."""
        instructions = method["code"]
        if method["handlers"] or "static " not in method["header"]:
            raise ValueError("this rule requires a static method without exception handlers")
        positions = {ins.pc: i for i, ins in enumerate(instructions)}
        while True:
            if pc == stop:
                return [("head", state)]
            if pc in path_pcs or pc not in positions:
                raise ValueError(f"unrepresented cycle or invalid branch at {pc}")
            path_pcs = (*path_pcs, pc)
            index = positions[pc]
            ins = instructions[index]
            op, arg = ins.op, ins.arg
            next_pc = instructions[index + 1].pc if index + 1 < len(instructions) else None
            if match := re.fullmatch(r"([ai])(load|store)(?:_(\d))?", op):
                slot = int(match[3] or arg)
                if match[2] == "load":
                    state = state.push(state.locals[slot])
                else:
                    value, state = state.pop()
                    state = replace(state, locals={**state.locals, slot: value})
            elif op.startswith("iconst_"):
                state = state.push(word(-1 if op == "iconst_m1" else int(op[7:])))
            elif op in ("bipush", "sipush"):
                state = state.push(word(int(arg)))
            elif op in ("iadd", "isub"):
                right, state = state.pop()
                left, state = state.pop()
                state = state.push(term("bvadd" if op == "iadd" else "bvsub", left, right))
            elif op == "iinc":
                slot, delta = map(int, arg.split(","))
                state = replace(
                    state, locals={**state.locals, slot: term("bvadd", state.locals[slot], word(delta))}
                )
            elif op in ("arraylength", "iaload", "iastore"):
                if op == "iastore":
                    value, state = state.pop()
                if op != "arraylength":
                    offset, state = state.pop()
                ref, state = state.pop()
                if ref != "@array":
                    raise ValueError(f"unbound heap reference at {pc}")
                if op == "arraylength":
                    state = state.push("length")
                else:
                    self.vc(f"safe array access at {pc}", state.path, between(ZERO, offset, "length"))
                    state = (
                        state.push(term("select", state.heap, offset))
                        if op == "iaload"
                        else replace(state, heap=term("store", state.heap, offset, value))
                    )
            elif op.startswith("if"):
                if op.startswith("if_icmp"):
                    right, state = state.pop()
                    comparison = op[7:]
                else:
                    right, comparison = ZERO, op[2:]
                left, state = state.pop()
                guard = term(COMPARE[comparison], left, right)
                target = int(arg)
                yes = replace(state, path=(*state.path, guard))
                no = replace(state, path=(*state.path, term("not", guard)))
                return self.walk(method, yes, target, stop, path_pcs) + self.walk(
                    method, no, next_pc, stop, path_pcs
                )
            elif op == "goto":
                pc = int(arg)
                continue
            elif op in ("return", "ireturn"):
                if len(state.stack) != (op == "ireturn"):
                    raise ValueError(f"unexpected return stack at {pc}")
                return [(op, state)]
            elif op == "invokestatic":
                owner, name, descriptor = self.call(ins)
                if owner or descriptor != "(III)V":
                    raise ValueError(f"unsupported helper {ins.member}")
                args = state.stack[-3:]
                called = self.code[(name, descriptor)]
                if len(args) != 3 or any(i.op == "invokestatic" for i in called["code"]):
                    raise ValueError("unrepresented range-check call")
                returns = self.walk(called, State(dict(enumerate(args)), heap=state.heap, path=state.path), 0)
                exits = []
                for kind, returned in returns:
                    if kind != "return":
                        raise ValueError("a range check must return void")
                    resumed = replace(state, stack=state.stack[:-3], heap=returned.heap, path=returned.path)
                    exits.extend(self.walk(method, resumed, next_pc, stop, path_pcs))
                return exits
            else:
                # An exception constructor beyond rangeCheck's rejecting branch is permitted only if unreachable.
                self.vc(f"unreachable {op} at {pc} in {method['header']}", state.path, "false")
                return []
            pc = next_pc

    @staticmethod
    def call(ins):
        match = re.fullmatch(r"Method (?:(.+)\.)?([\w$]+):(\([^)]*\).+)", ins.member)
        if not match:
            raise ValueError(f"unresolved constant-pool call at {ins.pc}: {ins.member}")
        return match.groups()

    def invariant(self, state):
        i, heap = state.locals[self.slot], state.heap
        frame = term("=", heap, "initial")
        if self.rule == "first-index":
            prefix = term("=>", between(ZERO, "k", i), term("distinct", term("select", heap, "k"), "target"))
            return both(term("bvsle", ZERO, i), term("bvsle", i, "length"), frame, prefix)
        expected = term("ite", between("from", "k", i), "value", term("select", "initial", "k"))
        return both(
            term("bvsle", "from", i),
            term("bvsle", i, "to"),
            term("=>", between(ZERO, "k", "length"), term("=", term("select", heap, "k"), expected)),
        )

    def generate(self, name, descriptor):
        method = self.code[name, descriptor]
        initial = State({0: "@array", 1: "target", 2: ZERO, 3: "length"})
        domain = [term("bvsle", ZERO, "length")]
        if self.rule == "first-index":
            wrapper = method["code"]
            if method["handlers"] or "static " not in method["header"] or descriptor != "([II)I":
                raise ValueError("first-index requires the public static int-array search descriptor")
            if [i.op for i in wrapper] != [
                "aload_0",
                "iload_1",
                "iconst_0",
                "aload_0",
                "arraylength",
                "invokestatic",
                "ireturn",
            ]:
                raise ValueError("entry does not forward the same array and target with [0,length) bounds")
            owner, helper, desc = self.call(wrapper[-2])
            if owner or desc != "([IIII)I":
                raise ValueError(
                    "array search does not forward to a same-class helper with the checked descriptor"
                )
            method = self.code[helper, desc]
        elif self.rule == "range-fill" and descriptor == "([IIII)V":
            initial = State({0: "@array", 1: "from", 2: "to", 3: "value"})
            domain.extend(
                [term("bvsle", ZERO, "from"), term("bvsle", "from", "to"), term("bvsle", "to", "length")]
            )
        else:
            raise ValueError("unsupported array contract or descriptor")
        code = method["code"]
        back = [i for i in code if i.op == "goto" and int(i.arg) <= i.pc]
        updates = [i for i in code if i.op == "iinc"]
        if len(back) != 1 or len(updates) != 1:
            raise ValueError("expected one loop head and one integral cursor")
        head = int(back[0].arg)
        self.slot = int(updates[0].arg.split(",")[0])
        base = self.walk(method, replace(initial, path=tuple(domain)), 0, head)
        if not base or any(kind != "head" or st.stack for kind, st in base):
            raise ValueError("entry does not reach the induction head on an empty operand stack")
        if set(initial.locals).intersection([self.slot]):
            raise ValueError("the loop cursor aliases an input local")
        for _, st in base:
            self.vc("entry establishes invariant", st.path, self.invariant(st))
            if st.heap != "initial":
                raise ValueError("unrepresented writes before the loop")
            # The range-check path facts at entry constrain parameters only. Carry them together with the invariant.
            abstract = State({**st.locals, self.slot: "cursor"}, heap="heap", path=st.path)
            abstract = replace(abstract, path=(*abstract.path, self.invariant(abstract)))
            # Execute the head once, then recognize an edge back to it as a completed iteration.
            first = next(i for i in code if i.pc == head)
            if first.op not in ("iload", f"iload_{self.slot}"):
                raise ValueError("unsupported first instruction of the array loop")
            if first.op == "iload" and int(first.arg) != self.slot:
                raise ValueError("the head does not load the selected cursor")
            begin = code[code.index(first) + 1].pc
            exits = self.walk(method, abstract.push("cursor"), begin, head)
            if not any(kind == "head" for kind, _ in exits) or not any(
                kind.endswith("return") for kind, _ in exits
            ):
                raise ValueError("loop lacks a checked return or back edge")
            for kind, end in exits:
                if kind == "head":
                    old = {k: v for k, v in abstract.locals.items() if k != self.slot}
                    new = {k: v for k, v in end.locals.items() if k != self.slot}
                    if old != new or end.stack:
                        raise ValueError("an untracked local or stack value changes across the back edge")
                    self.vc("iteration preserves invariant", end.path, self.invariant(end))
                    upper = "length" if self.rule == "first-index" else "to"
                    before = term("bvsub", upper, "cursor")
                    after = term("bvsub", upper, end.locals[self.slot])
                    self.vc(
                        "nonnegative strictly decreasing Java-int variant",
                        end.path,
                        both(
                            term("bvsle", ZERO, after),
                            term("bvslt", after, before),
                            term("bvsle", ZERO, before),
                        ),
                    )
                elif self.rule == "first-index" and kind == "ireturn":
                    result = end.stack[0]
                    absent = both(
                        term("=", result, NEG_ONE),
                        term(
                            "=>",
                            between(ZERO, "k", "length"),
                            term("distinct", term("select", "initial", "k"), "target"),
                        ),
                    )
                    first = both(
                        between(ZERO, result, "length"),
                        term("=", term("select", "initial", result), "target"),
                        term(
                            "=>",
                            between(ZERO, "k", result),
                            term("distinct", term("select", "initial", "k"), "target"),
                        ),
                    )
                    self.vc("return the earliest match or minus one", end.path, term("or", absent, first))
                    self.vc("preserve the input heap", end.path, term("=", end.heap, "initial"))
                elif self.rule == "range-fill" and kind == "return":
                    cell = term("ite", between("from", "k", "to"), "value", term("select", "initial", "k"))
                    self.vc(
                        "return with exactly the range written",
                        end.path,
                        term(
                            "=>", between(ZERO, "k", "length"), term("=", term("select", end.heap, "k"), cell)
                        ),
                    )
                else:
                    raise ValueError("unexpected return descriptor for the selected contract")
        self.trace = [{"pc": i.pc, "op": i.op, "argument": i.arg, "member": i.member} for i in code]
        return domain


def solve(induction, domain, work, seconds):
    solver = shutil.which("z3")
    if not solver:
        raise ValueError("Z3 must be on PATH to check array induction obligations")
    lines = ["(set-logic QF_ABV)"] + [
        f"(declare-const {x} {BV})" for x in ("length", "cursor", "target", "k", "from", "to", "value")
    ]
    lines += [f"(declare-const {x} {ARRAY})" for x in ("initial", "heap", "otherInitial")]
    lines += [f"(declare-const otherLength {BV})", "(declare-const aliases Bool)"]
    checks = [
        ("nonempty input domain", both(*domain), "sat"),
        ("maximal signed length admitted", both(*domain, term("=", "length", word(2**31 - 1))), "sat"),
    ]
    checks.extend(
        (label, both(path, term("not", conclusion)), "unsat")
        for label, path, conclusion in induction.conditions
    )
    for index, (_, assertion, _) in enumerate(checks):
        lines.extend([f"; VC {index}", "(push 1)", f"(assert {assertion})", "(check-sat)", "(pop 1)"])
    smt = "\n".join(lines) + "\n"
    (work / "obligations.smt2").write_text(smt)
    answer = subprocess.run(
        [solver, "-smt2", str(work / "obligations.smt2")],
        capture_output=True,
        text=True,
        timeout=seconds,
        check=True,
    )
    answers = answer.stdout.split()
    if len(answers) != len(checks) or any(a not in ("sat", "unsat", "unknown") for a in answers):
        raise ValueError("incomplete or malformed solver response")
    return (
        smt,
        [
            {"name": label, "expected": want, "obtained": got}
            for (label, _, want), got in zip(checks, answers)
        ],
        {
            "version": subprocess.check_output([solver, "--version"], text=True).strip(),
            "sha256": runtime.sha256(Path(solver)),
        },
    )


def range_caller(induction, method, domain, helper):
    """Check the actual caller's argument order, monitor-free frame and read through the second root."""
    code = method["code"]
    if (
        induction.rule != "range-fill"
        or method["handlers"]
        or "static " not in method["header"]
        or [i.op for i in code]
        != ["aload_0", "iload_2", "iload_3", "iload", "invokestatic", "aload_1", "iload", "iaload", "ireturn"]
        or code[3].arg != "4"
        or code[6].arg != "5"
        or induction.call(code[4]) != helper
    ):
        raise ValueError("the caller does not forward the certified range and read the selected second root")
    old_cell = term("ite", "aliases", term("select", "initial", "k"), term("select", "otherInitial", "k"))
    filled = term("ite", between("from", "k", "to"), "value", term("select", "initial", "k"))
    postcondition = term("=>", between(ZERO, "k", "length"), term("=", term("select", "heap", "k"), filled))
    observed = term("ite", "aliases", term("select", "heap", "k"), term("select", "otherInitial", "k"))
    wanted = term("ite", both("aliases", between("from", "k", "to")), "value", old_cell)
    admitted = [
        *domain,
        term("bvsle", ZERO, "otherLength"),
        between(ZERO, "k", "otherLength"),
        term("=>", "aliases", term("=", "length", "otherLength")),
    ]
    # For distinct roots the helper's only array operand is the first root. For an alias its postcondition supplies the read.
    induction.vc("caller establishes the helper precondition", admitted, both(*domain))
    induction.vc(
        "caller read follows from the proved frame", [*admitted, postcondition], term("=", observed, wanted)
    )


def record_key(folder, target, contract):
    example = json.loads((folder / "example.json").read_text())
    plan = route.resolve(folder, example, target, contract["bindingTask"])
    if (
        isinstance(plan, interfaces.Unsupported)
        or len(plan.revisions) != 1
        or plan.revisions[0] != contract["revision"]
    ):
        raise ValueError("the public artifact-binding task cannot supply the selected revision")
    locked = runtime.lock(plan, contract["revision"])
    if isinstance(locked, interfaces.Unsupported) or locked.stage != "source-locked":
        raise ValueError("the array contract has no current source lock")
    declaration = {
        "schema": "java-array-induction/v1",
        "contract": contract,
        "source": locked.source,
        "commit": locked.commit,
        "lengths": "all already allocated non-null Java arrays",
        "indexArithmetic": "signed 32-bit Java operations",
        "heap": "primitive int cells",
    }
    return plan, workflow.canonical_digest(declaration)


def evidence(folder, target, task):
    out = []
    for spec in target.get("arrayContracts", []):
        if spec["bindingTask"] != task:
            continue
        _, key = record_key(folder, target, spec)
        records = []
        for path in sorted((folder / "records/array-induction" / spec["id"]).glob("*/result.json")):
            doc = json.loads(path.read_text())
            if doc.get("sourceKey") != key:
                continue
            certificate = path.parent / "obligations.smt2"
            disassembly = path.parent / "class.javap"
            answers = doc.get("obligations", [])
            passed = bool(answers) and all(v["expected"] == v["obtained"] for v in answers)
            if (
                certificate.is_file()
                and runtime.sha256(certificate) == doc["certificateSha256"]
                and disassembly.is_file()
                and runtime.sha256(disassembly) == doc["disassemblySha256"]
                and doc["status"] == ("established" if passed else "unresolved")
            ):
                records.append({"status": doc["status"], "record": str(path.relative_to(folder))})
        out.append(
            {
                "id": spec["id"],
                "rule": spec["rule"],
                "sourceKey": key,
                "lengths": "all allocated",
                "records": records,
            }
        )
    return out


def run(folder, target, spec, seconds):
    plan, source_key = record_key(folder, target, spec)
    result_root = folder / "records/array-induction" / spec["id"]
    (feature,) = next(a for a in plan.artifacts if a["revision"] == spec["revision"])["jdks"]
    home = Path(runtime_jdk.home(feature))
    jmod = home / "jmods/java.base.jmod"
    owner, name, descriptor = runtime_jar.parse_target(spec["entry"])
    with tempfile.TemporaryDirectory(prefix="java-array-induction-") as directory:
        work = Path(directory)
        prepared = route.prepare_revision(plan, spec["revision"], work / "prepare", {})
        if isinstance(prepared, interfaces.Unsupported) or prepared.stage != "artifacts-ready":
            raise ValueError("artifact preparation failed: " + str(prepared))
        entries = runtime._checked(work / "prepare", prepared)
        paths = [work / "prepare" / a.path for a in entries if a.role in ("original", "dependency")]
        classes = {}

        def load(cls):
            if cls.startswith("java/"):
                with zipfile.ZipFile(jmod) as image:
                    data = image.read("classes/" + cls + ".class")
                origin = "java.base"
            else:
                matches = [
                    (path, data) for path in paths if (data := runtime_jar.read_class(path, cls)) is not None
                ]
                if len(matches) != 1:
                    raise ValueError(f"expected one selected definition of {cls}")
                path, data = matches[0]
                origin = str(path.relative_to(work / "prepare"))
            if runtime_jar.this_class(data) != cls:
                raise ValueError("class bytes identify a different class")
            classes[cls] = {"sha256": hashlib.sha256(data).hexdigest(), "origin": origin}
            return data

        cls = owner.replace(".", "/")
        data = load(cls)
        class_file = work / (cls.split("/")[-1] + ".class")
        class_file.write_bytes(data)
        code, disassembly = methods(home / "bin/javap", class_file)
        if cls.startswith("java/"):
            # Arrays' only initializer on this image records the class's assertion switch.
            init = code.get(("<clinit>", "()V"), {}).get("code", [])
            if (
                [i.op for i in init]
                != ["ldc", "invokevirtual", "ifne", "iconst_1", "goto", "iconst_0", "putstatic", "return"]
                or init[0].member != "class " + cls
                or init[1].member != "Method java/lang/Class.desiredAssertionStatus:()Z"
                or int(init[2].arg) != init[5].pc
                or int(init[4].arg) != init[6].pc
                or init[6].member != "Field $assertionsDisabled:Z"
                or runtime_jar.super_class(data) != "java/lang/Object"
                or runtime_jar.interfaces(data)
            ):
                raise ValueError("unqualified platform initializer")
        else:
            seen = set()
            pending = [cls]
            while pending:
                cursor = pending.pop()
                if cursor in seen or cursor == "java/lang/Object":
                    continue
                seen.add(cursor)
                parent_data = data if cursor == cls else load(cursor)
                if ("<clinit>", "()V") in runtime_jar.methods(parent_data):
                    raise ValueError(f"unqualified reachable initializer on {cursor}")
                pending.extend(runtime_jar.interfaces(parent_data))
                parent = runtime_jar.super_class(parent_data)
                if parent:
                    pending.append(parent)
        induction = Induction(code, spec["rule"])
        domain = induction.generate(name, descriptor)
        caller_evidence = None
        if caller := spec.get("caller"):
            caller_owner, caller_name, caller_descriptor = runtime_jar.parse_target(caller)
            caller_data = load(caller_owner.replace(".", "/"))
            if (
                caller_descriptor != "([I[IIIII)I"
                or ("<clinit>", "()V") in runtime_jar.methods(caller_data)
                or runtime_jar.super_class(caller_data) != "java/lang/Object"
                or runtime_jar.interfaces(caller_data)
            ):
                raise ValueError("unqualified caller descriptor or initializer")
            caller_file = work / (caller_owner.split(".")[-1] + ".class")
            caller_file.write_bytes(caller_data)
            caller_code, caller_disassembly = methods(home / "bin/javap", caller_file)
            called = caller_code[caller_name, caller_descriptor]
            range_caller(induction, called, domain, (cls, name, descriptor))
            disassembly += "\n" + caller_disassembly
            caller_evidence = {
                "entry": caller,
                "classSha256": classes[caller_owner.replace(".", "/")]["sha256"],
                "callee": spec["entry"],
                "calleeClassSha256": classes[cls]["sha256"],
                "invocationPc": called["code"][4].pc,
                "observationPc": called["code"][7].pc,
                "roots": "the same int array or two distinct int arrays of independent legal lengths",
            }
        smt, obligations, solver = solve(induction, domain, work, seconds)
        passed = all(obl["expected"] == obl["obtained"] for obl in obligations)
        cp = [
            {"path": a.path, "role": a.role, "sha256": a.sha256}
            for a in entries
            if a.role in ("original", "dependency")
        ]
        result = {
            "schema": "java-array-induction-result/v1",
            "sourceKey": source_key,
            "entry": spec["entry"],
            "revision": spec["revision"],
            "rule": spec["rule"],
            "status": "established" if passed else "unresolved",
            "domain": "Every non-null, already allocated int array of legal Java length and all signed scalar inputs"
            + (" with 0 <= from <= to <= length." if spec["rule"] == "range-fill" else "."),
            "preparation": prepared.commit,
            "classpath": cp,
            "classes": classes,
            "jdk": runtime_jdk.identity(home),
            "rulesSha256": runtime.sha256(Path(__file__)),
            "javapSha256": runtime.sha256(home / "bin/javap"),
            "solver": solver,
            "solverTimeoutSeconds": seconds,
            "bytecode": induction.trace,
            "obligations": obligations,
            "certificateSha256": hashlib.sha256(smt.encode()).hexdigest(),
            "disassemblySha256": hashlib.sha256(disassembly.encode()).hexdigest(),
        }
        if caller_evidence:
            result["caller"] = caller_evidence
        record_id = workflow.canonical_digest(result)[:20]
        dest = result_root / record_id
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "obligations.smt2").write_text(smt)
        (dest / "class.javap").write_text(disassembly)
        (dest / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(
            f"{spec['id']}: {result['status']}, {len(obligations)} solver answers, {dest.relative_to(folder)}"
        )
        return passed


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example")
    parser.add_argument("contract")
    parser.add_argument("--checker-seconds", type=int, default=60)
    args = parser.parse_args(argv)
    import build

    (folder,) = build.EXAMPLES.glob(args.example + "-*")
    example = build.load_example(folder)
    target = sidecar.load(folder, example)
    matches = [spec for spec in target.get("arrayContracts", []) if spec["id"] == args.contract]
    if len(matches) != 1 or args.checker_seconds <= 0:
        parser.error("expected one declared array contract and a positive solver deadline")
    try:
        return 0 if run(folder, target, matches[0], args.checker_seconds) else 1
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"{args.contract}: unresolved: {exc}")
        return 1

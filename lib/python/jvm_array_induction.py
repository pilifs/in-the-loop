"""Inductive verification of a linear Java array traversal on its compiled control-flow graph.

An arbitrary signed 32-bit index observes the heap. The base, back edges, each
return, array access and termination measure are independent SMT obligations.
Unsupported reachable bytecode prevents certification.

This is the proof method itself, apart from any example: the walk over a method's disassembled instructions, the
obligations of each rule, and the solver's answers read back. It takes a bound method (a class file and a method's
name and descriptor) and a declared rule, and nothing of where the class came from:

    prove(javap, class_file, name, descriptor, rule, work, seconds, caller=...)   -> Proof
    implementation()                                                              the files that are the rule, by digest

Finding an example, choosing a revision, preparing artifacts, qualifying a class's initializers and publishing a
record stay with the caller (examples/tools/targets/array_induction.py is the first). What a result supports is the
obligations it names, on those bytes: the SMT text and the solver's answers. It certifies no general translation of
Java to SMT.

The rules, selected by name and by the method's descriptor, never by which example asks:

    first-index   `static int f(int[] a, int target)` or `(long[] a, long target)` forwarding to a same-class
                  helper over [0, length): the earliest match or -1, the input heap unchanged. Array cells are 32
                  or 64 bits wide by the descriptor; indices are Java ints either way.
    range-fill    `static void f(int[] a, int from, int to, int value)`: exactly the range written, for
                  0 <= from <= to <= length. A caller of it (`range_caller`) may then be checked against that frame.

Standard library only, with Z3 on the PATH for `solve`.
"""

from dataclasses import dataclass, field, replace
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
from typing import Optional

from jvm_disassembly import Instruction, member_call, methods  # noqa: F401  (Instruction and methods are this module's names too)


ZERO = "#x00000000"
ONE = "#x00000001"
NEG_ONE = "#xffffffff"
BV = "(_ BitVec 32)"
COMPARE = {"eq": "=", "ne": "distinct", "lt": "bvslt", "le": "bvsle", "gt": "bvsgt", "ge": "bvsge"}


def term(op, *values):
    return "(" + " ".join((op, *values)) + ")"


def both(*values):
    return term("and", *values) if len(values) > 1 else values[0] if values else "true"


def between(lower, value, upper):
    return both(term("bvsle", lower, value), term("bvslt", value, upper))


def word(value):
    return f"#x{value & 0xFFFFFFFF:08x}"


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
        self.cell_bits = 32
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
            if match := re.fullmatch(r"([ail])(load|store)(?:_(\d))?", op):
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
            elif op == "lcmp":
                right, state = state.pop()
                left, state = state.pop()
                if self.cell_bits != 64:
                    raise ValueError("unexpected long comparison in an int traversal")
                state = state.push(
                    term(
                        "ite",
                        term("=", left, right),
                        ZERO,
                        term("ite", term("bvslt", left, right), NEG_ONE, ONE),
                    )
                )
            elif op in ("arraylength", "iaload", "laload", "iastore"):
                if op != "arraylength" and ((op == "laload") != (self.cell_bits == 64)):
                    raise ValueError("array opcode and selected cell width disagree")
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
                        if op in ("iaload", "laload")
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
        return member_call(ins)

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
            if (
                method["handlers"]
                or "static " not in method["header"]
                or descriptor not in ("([II)I", "([JJ)I")
            ):
                raise ValueError("first-index requires a static int- or long-array search")
            wide = descriptor == "([JJ)I"
            if wide:
                self.cell_bits = 64
                # The long target takes two JVM local slots. The indexes remain Java ints.
                initial = State({0: "@array", 1: "target", 3: ZERO, 4: "length"})
            if [i.op for i in wrapper] != [
                "aload_0",
                "lload_1" if wide else "iload_1",
                "iconst_0",
                "aload_0",
                "arraylength",
                "invokestatic",
                "ireturn",
            ]:
                raise ValueError("entry does not forward the same array and target with [0,length) bounds")
            owner, helper, desc = self.call(wrapper[-2])
            if owner or desc != ("([JJII)I" if wide else "([IIII)I"):
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
    cell_sort = f"(_ BitVec {induction.cell_bits})"
    lines = ["(set-logic QF_ABV)"] + [
        f"(declare-const {x} {cell_sort if x in ('target', 'value') else BV})"
        for x in ("length", "cursor", "target", "k", "from", "to", "value")
    ]
    lines += [f"(declare-const {x} (Array {BV} {cell_sort}))" for x in ("initial", "heap", "otherInitial")]
    lines += [f"(declare-const otherLength {BV})", "(declare-const aliases Bool)"]
    checks = [
        ("nonempty input domain", both(*domain), "sat"),
        ("maximal signed length admitted", both(*domain, term("=", "length", word(2**31 - 1))), "sat"),
    ]
    if induction.cell_bits == 64:
        cell = term("select", "initial", ZERO)
        checks.append(
            (
                "distinct elements can have identical low 32 bits",
                both(
                    *domain,
                    term("bvslt", ZERO, "length"),
                    term("distinct", cell, "target"),
                    term("=", term("(_ extract 31 0)", cell), term("(_ extract 31 0)", "target")),
                ),
                "sat",
            )
        )
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
            "sha256": file_sha256(Path(solver)),
        },
    )


def range_caller(induction, method, domain, helper):
    """Check each path to the helper, then consume its frame at the actual second-root read."""
    code = method["code"]
    calls = [i for i, ins in enumerate(code) if ins.op == "invokestatic"]
    if (
        induction.rule != "range-fill"
        or method["handlers"]
        or "static " not in method["header"]
        or len(calls) != 1
    ):
        raise ValueError("the caller needs one static range-fill call without exception handlers")
    at = calls[0]
    tail = code[at + 1 :]
    if (
        induction.call(code[at]) != helper
        or [ins.op for ins in tail] != ["aload_1", "iload", "iaload", "ireturn"]
        or tail[1].arg != "5"
    ):
        raise ValueError("the caller must read the observed index of the second root after the helper")
    old_cell = term("ite", "aliases", term("select", "initial", "k"), term("select", "otherInitial", "k"))
    observed = term("ite", "aliases", term("select", "heap", "k"), term("select", "otherInitial", "k"))
    wanted = term("ite", both("aliases", between("from", "k", "to")), "value", old_cell)
    admitted = [
        *domain,
        term("bvsle", ZERO, "otherLength"),
        between(ZERO, "k", "otherLength"),
        term("=>", "aliases", term("=", "length", "otherLength")),
    ]
    entry = State(dict(enumerate(("@array", "@other", "from", "to", "value", "k"))), path=tuple(admitted))
    paths = induction.walk(method, entry, 0, stop=code[at].pc)
    if not paths:
        raise ValueError("no path reaches the range-fill helper")
    for kind, state in paths:
        if (
            kind != "head"
            or len(state.stack) != 4
            or state.stack[0] != "@array"
            or state.heap != "initial"
            or state.locals != entry.locals
        ):
            raise ValueError("unrepresented caller stack, heap, or locals at the helper")
        _, lower, upper, value = state.stack
        helper_domain = both(
            term("bvsle", ZERO, lower), term("bvsle", lower, upper), term("bvsle", upper, "length")
        )
        induction.vc("caller establishes the helper precondition", state.path, helper_domain)
        written = term("ite", between(lower, "k", upper), value, term("select", "initial", "k"))
        frame = term("=>", between(ZERO, "k", "length"), term("=", term("select", "heap", "k"), written))
        induction.vc(
            "caller read follows from the proved frame",
            [*state.path, helper_domain, frame],
            term("=", observed, wanted),
        )
    return code[at].pc, tail[2].pc


def file_sha256(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


# The files whose text is the rule: a result made by them names each by digest, so that a change to the proof
# method is a change to what a new result says it was made by. The caller adds its own file when it decides
# anything the result rests on (the example adapter qualifies class initializers).
RULE_FILES = (Path(__file__).resolve(), Path(__file__).resolve().with_name("jvm_disassembly.py"))


def implementation(extra=(), root=None):
    """The rule implementation a result was made by: {"files": {path: sha256}, "sha256": one digest over them}.
    Paths are relative to `root` (the repository) where they are under it. `extra` are the caller's own files that
    decide part of the result."""
    files = {}
    root = Path(root).resolve() if root else None
    for path in (*RULE_FILES, *(Path(p).resolve() for p in extra)):
        name = path.relative_to(root).as_posix() if root and root in path.parents else path.name
        files[name] = file_sha256(path)
    combined = hashlib.sha256()
    for name in sorted(files):
        combined.update(name.encode() + b"\0" + bytes.fromhex(files[name]))
    return {"files": dict(sorted(files.items())), "sha256": combined.hexdigest()}


@dataclass
class Proof:
    """What `prove` found for one bound method under one rule."""
    rule: str
    name: str
    descriptor: str
    domain: list                 # the admitted inputs, as SMT terms
    cell_bits: int               # the width of an array cell: 32 or 64
    index_bits: int              # the width of an index: Java's int
    trace: list                  # the instructions of the loop's method, as walked
    obligations: list            # [{"name", "expected", "obtained"}], in the order of the certificate
    smt: str                     # the certificate: every obligation as the solver was given it
    disassembly: str             # what the disassembler printed, the caller's class after the entry's
    solver: dict                 # {"version", "sha256"}
    caller: Optional[dict] = None  # {"invocationPc", "observationPc"} of a checked caller
    code: dict = field(default_factory=dict, repr=False)  # the entry class's methods, for a caller's own checks

    @property
    def passed(self):
        return all(o["expected"] == o["obtained"] for o in self.obligations)


def prove(javap, class_file, name, descriptor, rule, work, seconds, *, owner=None, caller=None, disassembled=None):
    """The obligations of `rule` for the method `name``descriptor` of the class file given, each answered by the
    solver: a Proof, established when every answer is the expected one. `work` is a directory for the certificate.

    `caller`, for range-fill, is (class file, name, descriptor) of a method that calls the entry once and then reads
    the second array at the observed index; `owner` is then the entry's class in internal form, as the caller's
    constant pool names it. `disassembled` is `methods(javap, class_file)` when the caller has read it already.
    Raises ValueError for bytecode the rule does not represent: nothing is certified past what it reads."""
    code, disassembly = disassembled or methods(javap, class_file)
    induction = Induction(code, rule)
    domain = induction.generate(name, descriptor)
    checked = None
    if caller is not None:
        caller_file, caller_name, caller_descriptor = caller
        caller_code, caller_disassembly = methods(javap, caller_file)
        invocation_pc, observation_pc = range_caller(induction, caller_code[caller_name, caller_descriptor], domain,
                                                     (owner, name, descriptor))
        disassembly += "\n" + caller_disassembly
        checked = {"invocationPc": invocation_pc, "observationPc": observation_pc}
    smt, obligations, solver = solve(induction, domain, Path(work), seconds)
    return Proof(rule, name, descriptor, domain, induction.cell_bits, 32, induction.trace, obligations, smt, disassembly, solver,
                 checked, code)

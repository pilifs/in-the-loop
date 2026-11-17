#!/usr/bin/env python3
"""What an unchanged callee can read, write and let escape, read from its class files: a record, not a proof.

    python3 -I footprint.py --entry 'pkg/Class#name(descriptor)' --side NAME=CLASSES_DIR [--side NAME=DIR ...]
        [--out FILE]

For 307 the callee is BCrypt.hashpw(byte[], String), which both revisions of hashpw(String, String) call with the
password's bytes. A rule that takes one call of it for the other ("the same code on equal arguments ends alike")
needs side conditions; this script states, for the class files it is given, which of them the bytecode shows and
which it leaves open. It decides nothing about a claim and is no part of the verifier: the verifier's own check of
"the same code" is lib/src/shared.rs (fingerprint, reach), and a rule's side conditions are checked where the rule
is used. Its use is to say beforehand what such a check has to find true of this callee, and to be compared with it.

What it does, with no dependency but the standard library (it parses the class files itself, so a constant-pool
index never enters a comparison):

- the closure: every method of a class in a side's directory that the entry reaches by invokestatic, invokespecial,
  invokevirtual or invokeinterface, resolved in the declaring class or the classes above it that the directory has.
  A virtual or interface call whose owner is in the directory is followed to that owner's method and reported in
  `virtualCalls` (an override elsewhere would be other code: I010's concern); a call into a class the directory
  lacks (the JDK) is listed in `outsideCalls` with what each reference argument may be;
- each method's code as a list of resolved instructions (operands by name, branch targets by instruction number,
  ldc_w as ldc) and its exception table, hashed, so two sides' methods compare by what they do;
- an abstract run of each method over where a reference comes from (a parameter, a static field, an object or
  array made here, a clone, a field of one of those, a call's result), joined at branches, with a summary per
  method taken to a fixed point over the closure. A field's content is the union of everything the closure stores
  in a field of that name and class. From it: every static read and written; every array store and field store
  with where its target may come from, in the terms of the method it is in (`arrayStores`, `fieldStores`); and
  in the entry's terms, what the whole call may write (`entryWrites`), return, and hand to code outside
  (`entryGivesOutside`), each with the subset the caller can still see afterwards (a parameter, a static, a
  result of outside code: anything not made inside the call);
- the classes whose initialization the closure can trigger, and each `athrow` with the class it throws when that
  is an object made there.

What it does not show (each is in the record's `open` list): what code outside the directory does with what it is
given, implicit exceptions (it counts the instructions that can raise one), termination, and the values of the
static tables. `--tables` adds the last one from a JVM: the SHA-256 of each static array's content after the
class is initialized, by reflection, on the `java` given.
"""
import argparse
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

# opcode: (name, operand bytes). Variable-length ones (tableswitch, lookupswitch, wide) are decoded by hand.
OPS = {}


def _ops():
    simple = """0 nop;1 aconst_null;2 iconst_m1;3 iconst_0;4 iconst_1;5 iconst_2;6 iconst_3;7 iconst_4;8 iconst_5;
    9 lconst_0;10 lconst_1;11 fconst_0;12 fconst_1;13 fconst_2;14 dconst_0;15 dconst_1;26 iload_0;27 iload_1;
    28 iload_2;29 iload_3;30 lload_0;31 lload_1;32 lload_2;33 lload_3;34 fload_0;35 fload_1;36 fload_2;37 fload_3;
    38 dload_0;39 dload_1;40 dload_2;41 dload_3;42 aload_0;43 aload_1;44 aload_2;45 aload_3;46 iaload;47 laload;
    48 faload;49 daload;50 aaload;51 baload;52 caload;53 saload;59 istore_0;60 istore_1;61 istore_2;62 istore_3;
    63 lstore_0;64 lstore_1;65 lstore_2;66 lstore_3;67 fstore_0;68 fstore_1;69 fstore_2;70 fstore_3;71 dstore_0;
    72 dstore_1;73 dstore_2;74 dstore_3;75 astore_0;76 astore_1;77 astore_2;78 astore_3;79 iastore;80 lastore;
    81 fastore;82 dastore;83 aastore;84 bastore;85 castore;86 sastore;87 pop;88 pop2;89 dup;90 dup_x1;91 dup_x2;
    92 dup2;93 dup2_x1;94 dup2_x2;95 swap;96 iadd;97 ladd;98 fadd;99 dadd;100 isub;101 lsub;102 fsub;103 dsub;
    104 imul;105 lmul;106 fmul;107 dmul;108 idiv;109 ldiv;110 fdiv;111 ddiv;112 irem;113 lrem;114 frem;115 drem;
    116 ineg;117 lneg;118 fneg;119 dneg;120 ishl;121 lshl;122 ishr;123 lshr;124 iushr;125 lushr;126 iand;127 land;
    128 ior;129 lor;130 ixor;131 lxor;133 i2l;134 i2f;135 i2d;136 l2i;137 l2f;138 l2d;139 f2i;140 f2l;141 f2d;
    142 d2i;143 d2l;144 d2f;145 i2b;146 i2c;147 i2s;148 lcmp;149 fcmpl;150 fcmpg;151 dcmpl;152 dcmpg;172 ireturn;
    173 lreturn;174 freturn;175 dreturn;176 areturn;177 return;190 arraylength;191 athrow;194 monitorenter;
    195 monitorexit"""
    for item in simple.replace("\n", "").split(";"):
        code, name = item.split()
        OPS[int(code)] = (name, 0)
    for code, name, n in [(16, "bipush", 1), (17, "sipush", 2), (18, "ldc", 1), (19, "ldc_w", 2), (20, "ldc2_w", 2), (21, "iload", 1), (22, "lload", 1),
                          (23, "fload", 1), (24, "dload", 1), (25, "aload", 1), (54, "istore", 1), (55, "lstore", 1), (56, "fstore", 1), (57, "dstore", 1),
                          (58, "astore", 1), (132, "iinc", 2), (153, "ifeq", 2), (154, "ifne", 2), (155, "iflt", 2), (156, "ifge", 2), (157, "ifgt", 2),
                          (158, "ifle", 2), (159, "if_icmpeq", 2), (160, "if_icmpne", 2), (161, "if_icmplt", 2), (162, "if_icmpge", 2), (163, "if_icmpgt", 2),
                          (164, "if_icmple", 2), (165, "if_acmpeq", 2), (166, "if_acmpne", 2), (167, "goto", 2), (178, "getstatic", 2), (179, "putstatic", 2),
                          (180, "getfield", 2), (181, "putfield", 2), (182, "invokevirtual", 2), (183, "invokespecial", 2), (184, "invokestatic", 2),
                          (185, "invokeinterface", 4), (186, "invokedynamic", 4), (187, "new", 2), (188, "newarray", 1), (189, "anewarray", 2),
                          (192, "checkcast", 2), (193, "instanceof", 2), (197, "multianewarray", 3), (198, "ifnull", 2), (199, "ifnonnull", 2),
                          (200, "goto_w", 4)]:
        OPS[code] = (name, n)


_ops()
BRANCHES = {"ifeq", "ifne", "iflt", "ifge", "ifgt", "ifle", "if_icmpeq", "if_icmpne", "if_icmplt", "if_icmpge", "if_icmpgt", "if_icmple", "if_acmpeq",
            "if_acmpne", "goto", "ifnull", "ifnonnull", "goto_w"}
# Instructions that can raise an exception no `athrow` names (a null, an index, a size, a zero divisor, a cast).
IMPLICIT = {"iaload", "laload", "faload", "daload", "aaload", "baload", "caload", "saload", "iastore", "lastore", "fastore", "dastore", "aastore",
            "bastore", "castore", "sastore", "arraylength", "idiv", "ldiv", "irem", "lrem", "getfield", "putfield", "checkcast", "newarray",
            "anewarray", "multianewarray", "athrow", "monitorenter", "monitorexit"}
ARRAY_TYPES = {4: "Z", 5: "C", 6: "F", 7: "D", 8: "B", 9: "S", 10: "I", 11: "J"}


class ClassFile:
    def __init__(self, data):
        self.data, self.at = data, 0
        if self.u4() != 0xCAFEBABE:
            raise ValueError("not a class file")
        self.minor, self.major = self.u2(), self.u2()
        n, self.cp, i = self.u2(), [None], 1
        while i < n:
            tag = self.u1()
            if tag == 1:
                length = self.u2()
                self.cp.append(("Utf8", self.take(length).decode("utf-8", "surrogatepass")))
            elif tag in (3, 4):
                self.cp.append(("Int" if tag == 3 else "Float", struct.unpack(">i" if tag == 3 else ">f", self.take(4))[0]))
            elif tag in (5, 6):
                self.cp.append(("Long" if tag == 5 else "Double", struct.unpack(">q" if tag == 5 else ">d", self.take(8))[0]))
                self.cp.append(None)
                i += 1
            elif tag in (7, 8, 16, 19, 20):
                self.cp.append(({7: "Class", 8: "String", 16: "MethodType", 19: "Module", 20: "Package"}[tag], self.u2()))
            elif tag in (9, 10, 11, 12, 17, 18):
                self.cp.append(({9: "Field", 10: "Method", 11: "InterfaceMethod", 12: "NameAndType", 17: "Dynamic", 18: "InvokeDynamic"}[tag], self.u2(), self.u2()))
            elif tag == 15:
                self.cp.append(("MethodHandle", self.u1(), self.u2()))
            else:
                raise ValueError(f"constant pool tag {tag}")
            i += 1
        self.access = self.u2()
        self.name, self.super = self.cls(self.u2()), None
        sup = self.u2()
        self.super = self.cls(sup) if sup else None
        self.interfaces = [self.cls(self.u2()) for _ in range(self.u2())]
        self.fields = [self.member() for _ in range(self.u2())]
        self.methods = [self.member() for _ in range(self.u2())]

    def take(self, n):
        self.at += n
        return self.data[self.at - n:self.at]

    def u1(self):
        return self.take(1)[0]

    def u2(self):
        return struct.unpack(">H", self.take(2))[0]

    def u4(self):
        return struct.unpack(">I", self.take(4))[0]

    def utf(self, i):
        return self.cp[i][1]

    def cls(self, i):
        return self.utf(self.cp[i][1])

    def ref(self, i):
        """A field or method reference as (owner, name, descriptor)."""
        _, c, nt = self.cp[i]
        return self.cls(c), self.utf(self.cp[nt][1]), self.utf(self.cp[nt][2])

    def constant(self, i):
        kind = self.cp[i][0]
        if kind == "String":
            return "String " + json.dumps(self.utf(self.cp[i][1]))
        if kind == "Class":
            return "Class " + self.cls(i)
        return f"{kind} {self.cp[i][1]!r}"

    def member(self):
        access, name, descriptor = self.u2(), self.utf(self.u2()), self.utf(self.u2())
        m = {"access": access, "name": name, "descriptor": descriptor, "code": None, "constant": False}
        for _ in range(self.u2()):
            attribute, length = self.utf(self.u2()), self.u4()
            body = self.take(length)
            if attribute == "Code":
                m["code"] = body
            elif attribute == "ConstantValue":
                m["constant"] = True
        return m


def decode(cf, body):
    """A Code attribute as (instructions, handlers): an instruction is (pc, name, operand) with the operand resolved."""
    max_stack, max_locals, n = struct.unpack(">HHI", body[:8])
    code, out, pc = body[8:8 + n], [], 0
    while pc < n:
        op, start = code[pc], pc
        if op == 170 or op == 171:  # tableswitch, lookupswitch
            pc = (pc + 4) & ~3
            default = struct.unpack(">i", code[pc:pc + 4])[0]
            if op == 170:
                low, high = struct.unpack(">ii", code[pc + 4:pc + 12])
                offsets = struct.unpack(f">{high - low + 1}i", code[pc + 12:pc + 12 + 4 * (high - low + 1)])
                cases = [(low + k, start + o) for k, o in enumerate(offsets)]
                pc += 12 + 4 * (high - low + 1)
            else:
                pairs = struct.unpack(">i", code[pc + 4:pc + 8])[0]
                flat = struct.unpack(f">{2 * pairs}i", code[pc + 8:pc + 8 + 8 * pairs])
                cases = [(flat[2 * k], start + flat[2 * k + 1]) for k in range(pairs)]
                pc += 8 + 8 * pairs
            out.append((start, "tableswitch" if op == 170 else "lookupswitch", ("switch", start + default, cases)))
            continue
        if op == 196:  # wide
            inner = OPS[code[pc + 1]][0]
            index = struct.unpack(">H", code[pc + 2:pc + 4])[0]
            if inner == "iinc":
                out.append((start, "iinc", ("iinc", index, struct.unpack(">h", code[pc + 4:pc + 6])[0])))
                pc += 6
            else:
                out.append((start, inner, ("local", index)))
                pc += 4
            continue
        if op not in OPS:
            raise ValueError(f"opcode {op} at {pc}")
        name, width = OPS[op]
        raw = code[pc + 1:pc + 1 + width]
        pc += 1 + width
        if name in BRANCHES:
            operand = ("target", start + struct.unpack(">h" if width == 2 else ">i", raw)[0])
        elif name in ("ldc", "ldc_w", "ldc2_w"):
            operand, name = ("constant", cf.constant(raw[0] if width == 1 else struct.unpack(">H", raw)[0])), ("ldc" if name != "ldc2_w" else name)
        elif name in ("getstatic", "putstatic", "getfield", "putfield", "invokevirtual", "invokespecial", "invokestatic", "invokeinterface"):
            operand = ("ref",) + cf.ref(struct.unpack(">H", raw[:2])[0])
        elif name == "invokedynamic":
            operand = ("dynamic", struct.unpack(">H", raw[:2])[0])
        elif name in ("new", "anewarray", "checkcast", "instanceof"):
            operand = ("class", cf.cls(struct.unpack(">H", raw)[0]))
        elif name == "multianewarray":
            operand = ("class", cf.cls(struct.unpack(">H", raw[:2])[0]), raw[2])
        elif name == "newarray":
            operand = ("class", "[" + ARRAY_TYPES[raw[0]])
        elif name == "iinc":
            operand = ("iinc", raw[0], struct.unpack(">b", raw[1:])[0])
        elif name in ("bipush", "sipush"):
            operand = ("int", struct.unpack(">b" if width == 1 else ">h", raw)[0])
        elif width == 1:
            operand = ("local", raw[0])
        else:
            operand = None
        out.append((start, name, operand))
    at = 8 + n
    handlers = []
    for k in range(struct.unpack(">H", body[at:at + 2])[0]):
        s, e, h, t = struct.unpack(">HHHH", body[at + 2 + 8 * k:at + 10 + 8 * k])
        handlers.append((s, e, h, cf.cls(t) if t else None))
    return out, handlers, max_locals


def shape(instructions, handlers):
    """The code by what it does: operands by name, targets by instruction number."""
    index = {pc: i for i, (pc, _, _) in enumerate(instructions)}
    index[instructions[-1][0] + 10 ** 6] = len(instructions)

    def number(pc):
        return index.get(pc, len(instructions))

    lines = []
    for pc, name, operand in instructions:
        if operand is None:
            lines.append(name)
        elif operand[0] == "target":
            lines.append(f"{name} @{number(operand[1])}")
        elif operand[0] == "switch":
            lines.append(f"{name} default @{number(operand[1])} " + " ".join(f"{k}:@{number(t)}" for k, t in operand[2]))
        else:
            lines.append(name + " " + " ".join(str(x) for x in operand[1:]))
    for s, e, h, t in handlers:
        lines.append(f"handler @{number(s)}..@{number(e)} -> @{number(h)} {t or 'any'}")
    return lines


def params(descriptor):
    """The parameter types and the return type of a method descriptor."""
    out, i = [], 1
    while descriptor[i] != ")":
        start = i
        while descriptor[i] == "[":
            i += 1
        i = descriptor.index(";", i) + 1 if descriptor[i] == "L" else i + 1
        out.append(descriptor[start:i])
    return out, descriptor[i + 1:]


def is_ref(t):
    return t[0] in "L["


def wide(t):
    return t in ("J", "D")


P1, P2 = (1, frozenset()), (2, frozenset())  # a value: (slots, where a reference may come from)


def ref(*origins):
    return (1, frozenset(origins))


class Side:
    def __init__(self, name, directory):
        self.name, self.dir, self.classes = name, Path(directory), {}
        for path in sorted(self.dir.rglob("*.class")):
            cf = ClassFile(path.read_bytes())
            cf.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            cf.decoded = {}
            self.classes[cf.name] = cf
        self.summary = {}  # method key -> {"writes", "stores", "returns", ...}
        self.fields = {}   # "Owner.name" -> origins stored there

    def find(self, owner, name, descriptor):
        """The method a reference resolves to in the directory's classes, or None (a class outside it)."""
        while owner in self.classes:
            cf = self.classes[owner]
            for m in cf.methods:
                if m["name"] == name and m["descriptor"] == descriptor:
                    return cf, m
            owner = cf.super
        return None

    def code(self, cf, m):
        key = f"{cf.name}#{m['name']}{m['descriptor']}"
        if key not in cf.decoded:
            cf.decoded[key] = decode(cf, m["code"]) if m["code"] is not None else None
        return key, cf.decoded[key]


def resolve(side, origins, seen=()):
    """Origins with each `field:` taken to what the closure stores in that field, down to roots."""
    out = set()
    for o in origins:
        if o.startswith("field:"):
            if o in seen:
                continue
            stored = side.fields.get(o[6:], frozenset())
            out |= resolve(side, stored, seen + (o,)) if stored else {"unset-" + o}
        else:
            out.add(o)
    return out


def run(side, cf, m, record):
    """One abstract pass over a method. Returns its summary; `record` collects the per-instruction facts."""
    key, (instructions, handlers, max_locals) = side.code(cf, m)
    types, _ = params(m["descriptor"])
    locals0, slot, static = {}, 0, bool(m["access"] & 0x0008)
    if not static:
        locals0[0] = ref("param:this")
        slot = 1
    for i, t in enumerate(types):
        locals0[slot] = ref(f"param:{i}") if is_ref(t) else (P2 if wide(t) else P1)
        slot += 2 if wide(t) else 1
    index = {pc: i for i, (pc, _, _) in enumerate(instructions)}
    states, work = {0: ((), tuple(sorted(locals0.items())))}, [0]
    summary = {"writes": set(), "stores": set(), "returns": set(), "calls": set(), "outside": set(), "throws": set(), "statics_read": set(),
               "statics_written": set(), "initializes": set(), "implicit": 0, "dynamic": 0, "monitors": 0, "virtual": set(), "given": set()}

    def join(i, stack, local):
        new = (tuple(stack), tuple(sorted(local.items())))
        old = states.get(i)
        if old is None:
            states[i] = new
            work.append(i)
            return
        if len(old[0]) != len(new[0]):
            raise ValueError(f"{key}: stack heights differ at instruction {i}")
        stack2 = tuple((a[0], a[1] | b[1]) for a, b in zip(old[0], new[0]))
        l_old, l_new = dict(old[1]), dict(new[1])
        local2 = {k: (l_old[k][0], l_old[k][1] | l_new[k][1]) for k in l_old if k in l_new and l_old[k][0] == l_new[k][0]}
        merged = (stack2, tuple(sorted(local2.items())))
        if merged != old:
            states[i] = merged
            work.append(i)

    while work:
        i = work.pop()
        stack, local = list(states[i][0]), dict(states[i][1])
        pc, name, operand = instructions[i]
        for s, e, h, t in handlers:
            if s <= pc < e:
                join(index[h], [ref(f"caught:{t or 'any'}")], local)
        if name in IMPLICIT:
            pass
        nexts, pop = [i + 1], stack.pop
        if name.startswith(("iconst", "bipush", "sipush", "fconst")) or name in ("iload", "fload") or name[:6] in ("iload_", "fload_"):
            stack.append(P1)
        elif name.startswith(("lconst", "dconst")) or name in ("lload", "dload") or name[:6] in ("lload_", "dload_"):
            stack.append(P2)
        elif name == "aconst_null":
            stack.append(ref("null"))
        elif name == "ldc":
            stack.append(ref("constant") if operand[1].startswith(("String", "Class")) else P1)
        elif name == "ldc2_w":
            stack.append(P2)
        elif name == "aload" or name.startswith("aload_"):
            stack.append(local[operand[1] if operand else int(name[-1])])
        elif name in ("istore", "fstore", "astore", "lstore", "dstore") or name[1:7] == "store_":
            local[operand[1] if operand else int(name[-1])] = pop()
        elif name in ("iaload", "faload", "baload", "caload", "saload"):
            pop(), pop(), stack.append(P1)
        elif name in ("laload", "daload"):
            pop(), pop(), stack.append(P2)
        elif name == "aaload":
            pop()
            array = pop()
            stack.append(ref(*(f"element:{o}" for o in array[1])))
        elif name in ("iastore", "fastore", "bastore", "castore", "sastore", "lastore", "dastore", "aastore"):
            value = pop()
            pop()
            array = pop()
            summary["writes"] |= array[1]
            record("arrayStores", key, pc, name, sorted(array[1]))
            if name == "aastore":
                for o in array[1]:
                    summary["stores"].add((f"element:{o}", value[1]))
        elif name == "pop":
            pop()
        elif name == "pop2":
            if pop()[0] == 1:
                pop()
        elif name == "dup":
            stack.append(stack[-1])
        elif name == "dup_x1":
            a, b = pop(), pop()
            stack += [a, b, a]
        elif name == "dup_x2":
            a, b = pop(), pop()
            if b[0] == 2:
                stack += [a, b, a]
            else:
                c = pop()
                stack += [a, c, b, a]
        elif name == "dup2":
            if stack[-1][0] == 2:
                stack.append(stack[-1])
            else:
                stack += stack[-2:]
        elif name in ("dup2_x1", "dup2_x2"):
            raise ValueError(f"{key}: {name} is not handled")
        elif name == "swap":
            a, b = pop(), pop()
            stack += [a, b]
        elif name in ("iadd", "isub", "imul", "idiv", "irem", "ishl", "ishr", "iushr", "iand", "ior", "ixor", "fadd", "fsub", "fmul", "fdiv", "frem"):
            pop(), pop(), stack.append(P1)
        elif name in ("ladd", "lsub", "lmul", "ldiv", "lrem", "land", "lor", "lxor", "dadd", "dsub", "dmul", "ddiv", "drem"):
            pop(), pop(), stack.append(P2)
        elif name in ("lshl", "lshr", "lushr"):
            pop(), pop(), stack.append(P2)
        elif name in ("ineg", "fneg", "i2f", "f2i", "i2b", "i2c", "i2s", "l2i", "l2f", "d2i", "d2f"):
            pop(), stack.append(P1)
        elif name in ("lneg", "dneg", "i2l", "i2d", "f2l", "f2d", "l2d", "d2l"):
            pop(), stack.append(P2)
        elif name in ("lcmp", "fcmpl", "fcmpg", "dcmpl", "dcmpg"):
            pop(), pop(), stack.append(P1)
        elif name == "iinc" or name == "nop":
            pass
        elif name in BRANCHES:
            if name.startswith("if_"):
                pop(), pop()
            elif name.startswith("if"):
                pop()
            nexts = [index[operand[1]]] + ([] if name.startswith("goto") else [i + 1])
        elif name in ("tableswitch", "lookupswitch"):
            pop()
            nexts = [index[operand[1]]] + [index[t] for _, t in operand[2]]
        elif name in ("ireturn", "lreturn", "freturn", "dreturn", "return"):
            nexts = []
        elif name == "areturn":
            summary["returns"] |= pop()[1]
            nexts = []
        elif name == "athrow":
            thrown = pop()
            summary["throws"] |= thrown[1]
            record("throws", key, pc, name, sorted(thrown[1]))
            nexts = []
        elif name in ("getstatic", "putstatic", "getfield", "putfield"):
            _, owner, field, descriptor = operand
            where = f"{owner}.{field}"
            if name == "getstatic":
                summary["statics_read"].add(where)
                summary["initializes"].add(owner)
                stack.append(ref(f"static:{where}") if is_ref(descriptor) else (P2 if wide(descriptor) else P1))
            elif name == "putstatic":
                value = pop()
                summary["statics_written"].add(where)
                summary["initializes"].add(owner)
                if is_ref(descriptor):
                    summary["stores"].add((f"static:{where}", value[1]))
                record("staticWrites", key, pc, where, sorted(value[1]))
            elif name == "getfield":
                pop()
                stack.append(ref(f"field:{where}") if is_ref(descriptor) else (P2 if wide(descriptor) else P1))
            else:
                value = pop()
                target = pop()
                summary["writes"] |= target[1]
                record("fieldStores", key, pc, where, sorted(target[1]))
                if is_ref(descriptor):
                    summary["stores"].add((f"field:{where}", value[1]))
        elif name in ("invokevirtual", "invokespecial", "invokestatic", "invokeinterface"):
            _, owner, method, descriptor = operand
            types2, result = params(descriptor)
            args = [pop() for _ in types2][::-1]
            receiver = pop() if name != "invokestatic" else None
            if name == "invokestatic":
                summary["initializes"].add(owner)
            found = side.find(owner, method, descriptor) if not owner.startswith("[") else None
            target = f"{owner}#{method}{descriptor}"
            if found and found[1]["code"] is not None:
                callee = f"{found[0].name}#{method}{descriptor}"
                summary["calls"].add(callee)
                if name in ("invokevirtual", "invokeinterface") and not (found[1]["access"] & 0x0012) and not (found[0].access & 0x0010):
                    summary["virtual"].add(callee)  # neither private nor final: a subclass could override it
                theirs = side.summary.get(callee)
                bind = {"param:this": receiver[1] if receiver else frozenset()}
                bind.update({f"param:{k}": a[1] for k, a in enumerate(args)})

                def into(origins):
                    out = set()
                    for o in origins:
                        root = o.split(":", 1)
                        out |= bind[o] if o in bind else {o if root[0] in ("static", "field", "constant", "null", "outside", "element") or o.startswith("unset") else f"made-in:{callee}"}
                    return frozenset(out)
                if theirs:
                    summary["writes"] |= into(theirs["writes"])
                    for where, value in theirs["stores"]:
                        summary["stores"].add((where, into(value)))
                    returned = into(theirs["returns"])
                    for what, origins in theirs["given"]:
                        summary["given"].add((what, into(origins)))
                    for k in ("statics_read", "statics_written", "initializes", "virtual"):
                        summary[k] |= theirs[k]
                    summary["throws"] |= {o if o.startswith(("made", "caught")) else "passed-on" for o in theirs["throws"]}
                else:
                    returned = frozenset()
                if is_ref(result):
                    stack.append((1, returned))
                elif result != "V":
                    stack.append(P2 if wide(result) else P1)
            else:
                given = [sorted(receiver[1])] if receiver else []
                given += [sorted(a[1]) for a, t in zip(args, types2) if is_ref(t)]
                summary["outside"].add(target)
                for g in given:
                    summary["given"].add((target, frozenset(g)))
                record("outsideCalls", key, pc, target, given)
                if method == "clone" and owner.startswith("["):
                    stack.append(ref(f"clone@{key}:{pc}"))
                elif is_ref(result):
                    stack.append(ref(f"outside:{target}"))
                elif result != "V":
                    stack.append(P2 if wide(result) else P1)
        elif name == "invokedynamic":
            summary["dynamic"] += 1
            raise ValueError(f"{key}: invokedynamic is not followed; the closure is not closed")
        elif name == "new":
            summary["initializes"].add(operand[1])
            stack.append(ref(f"new {operand[1]}@{key}:{pc}"))
        elif name in ("newarray", "anewarray"):
            pop()
            stack.append(ref(f"new {operand[1]}[]@{key}:{pc}" if name == "anewarray" else f"new {operand[1]}@{key}:{pc}"))
        elif name == "multianewarray":
            for _ in range(operand[2]):
                pop()
            stack.append(ref(f"new {operand[1]}@{key}:{pc}"))
        elif name == "arraylength":
            pop(), stack.append(P1)
        elif name == "checkcast":
            pass
        elif name == "instanceof":
            pop(), stack.append(P1)
        elif name in ("monitorenter", "monitorexit"):
            pop()
            summary["monitors"] += 1
        else:
            raise ValueError(f"{key}: {name} is not handled")
        for n in nexts:
            join(n, stack, local)
    summary["implicit"] = sum(1 for _, name, _ in instructions if name in IMPLICIT or name.startswith("invoke"))
    return key, summary


def analyse(side, entry):
    owner, rest = entry.split("#")
    name, descriptor = rest[:rest.index("(")], rest[rest.index("("):]
    found = side.find(owner, name, descriptor)
    if not found:
        sys.exit(f"{side.name}: no method {entry}")
    facts = {}

    def record(kind, key, pc, what, origins):
        facts.setdefault(kind, {})[(key, pc)] = {"in": key, "pc": pc, "what": what, "from": origins}

    for _ in range(50):
        before = json.dumps([sorted((k, sorted(map(str, v)) if isinstance(v, set) else v) for k, v in s.items()) for _, s in sorted(side.summary.items())], default=str)
        fields_before = dict(side.fields)
        closure, todo = {}, [found]
        facts.clear()
        while todo:
            cf, m = todo.pop()
            key = f"{cf.name}#{m['name']}{m['descriptor']}"
            if key in closure:
                continue
            key, summary = run(side, cf, m, record)
            closure[key] = (cf, m)
            side.summary[key] = summary
            for callee in sorted(summary["calls"]):
                o, r = callee.split("#")
                todo.append(side.find(o, r[:r.index("(")], r[r.index("("):]))
        side.fields = {}
        for key in closure:
            for where, value in side.summary[key]["stores"]:
                if where.startswith("field:"):
                    side.fields[where[6:]] = side.fields.get(where[6:], frozenset()) | value
        after = json.dumps([sorted((k, sorted(map(str, v)) if isinstance(v, set) else v) for k, v in s.items()) for _, s in sorted(side.summary.items())], default=str)
        if after == before and side.fields == fields_before:
            break
    else:
        sys.exit(f"{side.name}: the summaries did not settle")
    return f"{found[0].name}#{name}{descriptor}", closure, facts


def visible(origin):
    """Whether what an origin names outlives the call for the caller: not made inside it."""
    return not origin.startswith(("new ", "clone@", "made-in:", "caught:", "null", "constant"))


def report(side, entry, tables_java):
    top, closure, facts = analyse(side, entry)
    s = side.summary[top]
    methods = {}
    for key, (cf, m) in sorted(closure.items()):
        instructions, handlers, _ = side.code(cf, m)[1]
        lines = shape(instructions, handlers)
        methods[key] = {"instructions": len(instructions), "handlers": len(handlers),
                        "sha256": hashlib.sha256("\n".join(lines).encode()).hexdigest(), "access": m["access"]}
    initializers = {}
    for owner in sorted(s["initializes"]):
        found = side.find(owner, "<clinit>", "()V") if owner in side.classes else None
        if found:
            key, summary = run(side, found[0], found[1], lambda *a: None)
            instructions, handlers, _ = side.code(found[0], found[1])[1]
            initializers[owner] = {"sha256": hashlib.sha256("\n".join(shape(instructions, handlers)).encode()).hexdigest(),
                                   "instructions": len(instructions), "calls": sorted(summary["calls"]), "outsideCalls": sorted(summary["outside"]),
                                   "staticsRead": sorted(summary["statics_read"]), "staticsWritten": sorted(summary["statics_written"])}
        else:
            initializers[owner] = None

    def listed(kind):
        return [facts[kind][k] for k in sorted(facts.get(kind, {}))]

    def resolved(rows):
        out = []
        for row in rows:
            roots = sorted(resolve(side, row["from"]))
            out.append(dict(row, roots=roots))
        return out

    array_stores, field_stores = resolved(listed("arrayStores")), resolved(listed("fieldStores"))
    outside = []
    for row in listed("outsideCalls"):
        given = [sorted(resolve(side, g)) for g in row["from"]]
        outside.append({"in": row["in"], "pc": row["pc"], "what": row["what"], "given": given})
    written = sorted(resolve(side, s["writes"]))
    handed = {}
    for what, origins in s["given"]:
        handed.setdefault(what, set()).update(resolve(side, origins))
    static_fields = {}
    for owner in sorted({w.rsplit(".", 1)[0] for w in s["statics_read"] | s["statics_written"]}):
        cf = side.classes.get(owner)
        for where in sorted(w for w in s["statics_read"] | s["statics_written"] if w.rsplit(".", 1)[0] == owner):
            f = next((f for f in cf.fields if f["name"] == where.rsplit(".", 1)[1]), None) if cf else None
            static_fields[where] = {"inDirectory": cf is not None, "final": bool(f and f["access"] & 0x0010), "descriptor": f["descriptor"] if f else None,
                                    "read": where in s["statics_read"], "written": where in s["statics_written"]}
    out = {
        "classes": {name: cf.sha256 for name, cf in sorted(side.classes.items())},
        "entry": top,
        "methods": methods,
        "virtualCalls": sorted(s["virtual"]),
        "statics": static_fields,
        "initializers": initializers,
        "entryWrites": {"targets": written, "callerVisible": [o for o in written if visible(o)]},
        "entryGivesOutside": {what: {"references": sorted(v), "callerVisible": [o for o in sorted(v) if visible(o)]} for what, v in sorted(handed.items())},
        "arrayStores": array_stores,
        "fieldStores": field_stores,
        "fieldContents": {k: sorted(resolve(side, v)) for k, v in sorted(side.fields.items())},
        "staticWrites": listed("staticWrites"),
        "returns": sorted(resolve(side, s["returns"])),
        "throws": sorted({r["from"][0] if len(r["from"]) == 1 else "|".join(r["from"]) for r in listed("throws")}),
        "throwSites": len(listed("throws")),
        "outsideCalls": outside,
        "implicitExceptionSites": sum(side.summary[k]["implicit"] for k in closure),
        "monitors": sum(side.summary[k]["monitors"] for k in closure),
    }
    if tables_java:
        out["tables"] = tables(side, tables_java, sorted(w for w, f in static_fields.items() if f["inDirectory"]))
    return out


DUMP = """
import java.lang.reflect.*; import java.security.MessageDigest; import java.nio.*;
public class Dump { public static void main(String[] a) throws Exception {
  for (String w : a) { int dot = w.lastIndexOf('.'); Class<?> c = Class.forName(w.substring(0, dot).replace('/', '.'));
    Field f = c.getDeclaredField(w.substring(dot + 1)); f.setAccessible(true); Object v = f.get(null);
    if (v == null || !v.getClass().isArray()) { System.out.println(w + " value " + v); continue; }
    int n = Array.getLength(v); MessageDigest d = MessageDigest.getInstance("SHA-256");
    for (int i = 0; i < n; i++) { Object e = Array.get(v, i); long x = e instanceof Character ? (char) e : ((Number) e).longValue();
      d.update(ByteBuffer.allocate(8).putLong(x).array()); }
    StringBuilder h = new StringBuilder(); for (byte b : d.digest()) h.append(String.format("%02x", b));
    System.out.println(w + " " + v.getClass().getSimpleName() + " " + n + " " + h); } } }
"""


def tables(side, java, statics):
    """Each static array's length and the SHA-256 of its elements (each as eight big-endian bytes), after initialization."""
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "Dump.java").write_text(DUMP)
        javac = str(Path(java).parent / "javac")
        subprocess.run([javac, "-d", tmp, str(Path(tmp) / "Dump.java")], check=True)
        done = subprocess.run([java, "-cp", f"{tmp}:{side.dir}", "Dump", *statics], check=True, capture_output=True, text=True)
        version = subprocess.run([java, "-version"], capture_output=True, text=True).stderr.splitlines()[0]
    out = {"java": version, "fields": {}}
    for line in done.stdout.splitlines():
        parts = line.split(" ")
        out["fields"][parts[0]] = {"value": " ".join(parts[2:])} if parts[1] == "value" else {"type": parts[1], "length": int(parts[2]), "sha256": parts[3]}
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--entry", required=True, help="pkg/Class#name(descriptor)")
    p.add_argument("--side", action="append", required=True, help="NAME=directory of class files")
    p.add_argument("--tables", metavar="JAVA", help="a java binary: also hash the static arrays' contents after initialization")
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    sides = {}
    for item in args.side:
        name, directory = item.split("=", 1)
        sides[name] = report(Side(name, directory), args.entry, args.tables)
    names = list(sides)
    first = sides[names[0]]
    compare = {}
    for other in names[1:]:
        theirs = sides[other]
        differing = sorted(k for k in set(first["methods"]) | set(theirs["methods"]) if first["methods"].get(k, {}).get("sha256") != theirs["methods"].get(k, {}).get("sha256"))
        init = sorted(k for k in set(first["initializers"]) | set(theirs["initializers"]) if (first["initializers"].get(k) or {}).get("sha256") != (theirs["initializers"].get(k) or {}).get("sha256"))
        compare[f"{names[0]}/{other}"] = {
            "methodsDiffering": differing, "initializersDiffering": init,
            "sameFootprint": all(first[k] == theirs[k] for k in ("statics", "entryWrites", "entryGivesOutside", "arrayStores", "fieldStores", "fieldContents", "staticWrites", "returns", "throws", "outsideCalls", "virtualCalls")),
            "sameTables": (first.get("tables") or {}).get("fields") == (theirs.get("tables") or {}).get("fields") if args.tables else None,
        }
    record = {"schema": "callee-footprint/v1", "entry": args.entry, "sides": sides, "compare": compare,
              "open": ["What code outside the directories (the JDK) does with the references it is given (outsideCalls): read from its documentation or the verifier's model, not from here.",
                       "Implicit exceptions (a null, an index, a size, a cast): counted, not enumerated; which are reachable is the verifier's to find.",
                       "Termination, and anything about values: only where references flow is followed.",
                       "A class outside the directories that extends one inside it and overrides a method in virtualCalls."]}
    text = json.dumps(record, indent=1, sort_keys=False) + "\n"
    if args.out:
        args.out.write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()

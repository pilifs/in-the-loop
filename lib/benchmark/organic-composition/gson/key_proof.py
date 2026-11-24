"""Execute the admitted ASCII strings against the selected JDK's own read-only bytecode paths."""
import hashlib
import json
from functools import cache
from pathlib import Path
import sys
import zipfile

from register import DIGITS, PARSE
from plan_run import JDK, ROOT
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_inventory, runtime_jar

LATIN = "java.lang.CharacterDataLatin1"
PRE = "jdk.internal.util.Preconditions"
INT = "java.lang.Integer"
STRING = "java.lang.String"
SINGLETON = ("instance", LATIN)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def key(record):
    return digest(json.dumps(record, sort_keys=True, separators=(",", ":")).encode())


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


@cache
def body(entry):
    cls, method, desc = runtime_jar.parse_target(entry)
    with zipfile.ZipFile(JDK / "jmods/java.base.jmod") as jar:
        data = jar.read("classes/" + cls.replace(".", "/") + ".class")
    pool, methods, _ = runtime_jar._declarations(data, with_code=True)
    flags, code, handlers = methods[method, desc]
    require(code and not handlers and not flags & (0x20 | 0x100), "unqualified monitor, handler or native method")
    ops = dict(change_inventory.instructions(code))
    hashes = {"class": digest(data), "code": digest(code), "pool": digest(data[10:runtime_jar._pool(data)[1]])}
    return pool, code, dict(zip(ops, [*list(ops)[1:], len(code)])), hashes


def java_int(n):
    return (n + 2**31) % 2**32 - 2**31


def prove(text, expected):
    require(text in DIGITS, "outside admitted String contents")
    reads, visited = set(), {}
    budget = 4000
    def run(entry, args):
        nonlocal budget
        pool, code, successors, _ = body(entry)
        slots, stack, pc = dict(enumerate(args)), [], 0
        while True:
            budget -= 1
            require(budget >= 0 and pc in successors, "instruction bound or boundary")
            visited.setdefault(entry, set()).add(pc)
            op, after = code[pc], successors[pc]
            if 2 <= op <= 8:
                stack.append(op - 3)
            elif op in (0x10, 0x11):
                stack.append(int.from_bytes(code[pc+1:after], "big", signed=True))
            elif op == 0x12:
                tag, value = pool[code[pc+1]]
                require(tag == 3, "non-integer constant")
                stack.append(int.from_bytes(value, "big", signed=True))
            elif op in (0x15, 0x19):
                stack.append(slots[code[pc+1]])
            elif 0x1a <= op <= 0x1d or 0x2a <= op <= 0x2d:
                stack.append(slots[(op - (0x1a if op < 0x2a else 0x2a))])
            elif op == 0x36 or 0x3b <= op <= 0x3e:
                slots[code[pc+1] if op == 0x36 else op-0x3b] = stack.pop()
            elif op == 0x84:
                ix = code[pc+1]
                slots[ix] = java_int(slots[ix] + int.from_bytes(code[pc+2:after], "big", signed=True))
            elif op == 0x57:
                stack.pop()
            elif op in (0x60, 0x64, 0x68, 0x6c, 0x7a, 0x7c, 0x7e):
                b, a = stack.pop(), stack.pop()
                if op == 0x6c:
                    require(b != 0, "division by zero")
                    result = abs(a) // abs(b) * (-1 if (a < 0) != (b < 0) else 1)
                elif op == 0x7a:
                    result = a >> (b & 31)
                elif op == 0x7c:
                    result = (a & 0xffffffff) >> (b & 31)
                else:
                    result = {0x60: a + b, 0x64: a - b, 0x68: a * b, 0x7e: a & b}[op]
                stack.append(java_int(result))
            elif op in (0x74, 0x92):
                a = stack.pop()
                stack.append(java_int(-a) if op == 0x74 else a & 65535)
            elif op in (0x99, 0x9a, 0x9b, 0x9d, 0x9e, 0x9f, 0xa0, 0xa1, 0xa2, 0xa3, 0xa4, 0xa7, 0xc7):
                if op == 0xa7:
                    take = True
                elif op == 0xc7:
                    take = stack.pop() is not None
                elif op >= 0x9f:
                    b, a = stack.pop(), stack.pop()
                    take = {0x9f: a == b, 0xa0: a != b, 0xa1: a < b, 0xa2: a >= b, 0xa3: a > b, 0xa4: a <= b}[op]
                else:
                    a = stack.pop()
                    take = {0x99: a == 0, 0x9a: a != 0, 0x9b: a < 0, 0x9d: a > 0, 0x9e: a <= 0}[op]
                if take:
                    after = pc + int.from_bytes(code[pc+1:pc+3], "big", signed=True)
            elif op in (0xb2, 0xb4, 0xb6, 0xb8):
                tag, ref = pool[int.from_bytes(code[pc+1:after], "big")]
                owner, member, desc = runtime_jar._member_ref(pool, ref)
                owner = owner.replace("/", ".")
                if op in (0xb2, 0xb4):
                    require(tag == 9, "unbound field reference")
                    field = owner + "#" + member + ":" + desc
                    reads.add(field)
                    require((op == 0xb4) == (field in (STRING + "#value:[B", STRING + "#coder:B")), "wrong static or instance read")
                    if op == 0xb4:
                        require(stack.pop() == ("string", text), "field on a different receiver")
                    value = {STRING + "#value:[B": ("bytes", text.encode("ascii")), STRING + "#coder:B": 0,
                             STRING + "#COMPACT_STRINGS:Z": 1, LATIN + "#instance:Ljava/lang/CharacterDataLatin1;": SINGLETON,
                             LATIN + "#DIGITS:[B": ("digits",), PRE + "#SIOOBE_FORMATTER:Ljava/util/function/BiFunction;": ("unused formatter",)}[field]
                    stack.append(value)
                else:
                    require(tag == 10, "unbound method reference")
                    params = runtime_jar._parameter_types(desc)
                    result = desc.split(")")[1]
                    count = len(params) + int(op == 0xb6)
                    actual = [stack.pop() for _ in range(count)][::-1]
                    if op == 0xb6:
                        if owner == "java.lang.CharacterData" and actual[0] == SINGLETON:
                            owner = LATIN
                        else:
                            require(owner == STRING and actual[0] == ("string", text), "unsupported dispatch")
                    v = run(owner + "#" + member + desc, actual)
                    if result != "V":
                        stack.append(v)
            elif op == 0xbe:
                array = stack.pop()
                require(array[0] == "bytes", "unexpected array length")
                stack.append(len(array[1]))
            elif op == 0x33:
                i, array = stack.pop(), stack.pop()
                if array == ("digits",):
                    require(i in (48, 49, 50), "unbound digit table slot")
                    reads.add("DIGITS[" + str(i) + "]=" + str(i - 48))
                    stack.append(i - 48)
                else:
                    require(array[0] == "bytes" and 0 <= i < len(array[1]), "String array bound")
                    stack.append(array[1][i])
            elif op in (0xac, 0xb0, 0xb1):
                require(len(stack) == int(op != 0xb1), "return stack shape")
                return stack.pop() if stack else None
            else:
                raise ValueError(f"unqualified instruction {op:#x} at {entry}+{pc}")
            pc = after
    actual = run(PARSE, [("string", text)])
    require(actual == expected, "original parse disagrees with declared key")
    return {"text": text, "result": actual, "instructions": 4000 - budget, "reads": sorted(reads),
            "methods": {m: body(m)[3] | {"visitedOffsets": sorted(v)} for m, v in visited.items()}}


def certificate():
    rows = [prove(s, n) for s, n in DIGITS.items()]
    doc = {"entry": PARSE, "imageRelease": digest((JDK / "release").read_bytes()),
           "qualifier": digest(Path(__file__).read_bytes()), "rows": rows,
           "frame": "Only immutable compact String contents and the registered initialized JDK fields are read. Every reached bytecode and nested call is interpreted. The admitted paths return normally without writes."}
    return doc | {"key": key(doc)}

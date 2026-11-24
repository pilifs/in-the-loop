"""Check the complete updateTime bytecode on every sign of nextFileTime and both mode flags."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import zipfile

from register import PLUGIN, PROCESSOR, sha
from plan_run import ROOT
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_inventory, runtime_jar


def require(ok, why):
    if not ok:
        raise ValueError(why)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def plugin(core):
    with zipfile.ZipFile(core) as jar:
        data = jar.read(PLUGIN)
    offset = 0
    def number(fmt):
        nonlocal offset
        value, = struct.unpack_from(fmt, data, offset)
        offset += struct.calcsize(fmt)
        return value
    def string():
        nonlocal offset
        length = number(">H")
        result = runtime_jar.modified_utf8(data[offset:offset+length])
        offset += length
        return result
    matches = []
    for _ in range(number(">I")):
        category = string()
        for _ in range(number(">I")):
            name, owner, element = string(), string(), string()
            printable, deferred = number(">B"), number(">B")
            if (category, name) == ("fileconverter", "filedatepatternconverter"):
                matches.append([category, name, owner, element, printable, deferred])
    require(offset == len(data) and len(matches) == 1 and matches[0][2] == "org.apache.logging.log4j.core.pattern.FileDatePatternConverter",
            "missing or ambiguous registered file-date factory")
    return {"path": PLUGIN, "sha256": digest(data), "entry": matches[0]}


def prove(core):
    data = runtime_jar.read_class(core, PROCESSOR.replace(".", "/"))
    pool, declarations, _ = runtime_jar._declarations(data, with_code=True)
    flags, code, handlers = declarations["updateTime", "()V"]
    require(flags == 1 and handlers == 0, "expected original public unguarded updateTime")
    ops = dict(change_inventory.instructions(code))
    successors = dict(zip(ops, [*list(ops)[1:], len(code)]))
    partitions, reached = [], set()
    for sign in (-1, 0, 1):
        for flag in (False, True):
            # Symbolic labels preserve arbitrary signed values, including aliases among their values.
            state = {"nextFileTime": "next", "prevFileTime": "previous", "currentFileTime": "current", "isTimeBased": flag}
            stack, pc, visited, writes = [], 0, [], []
            while True:
                require(pc in ops and pc not in visited, "loop or invalid branch")
                visited.append(pc)
                op, after = ops[pc], successors[pc]
                if op == 0x2a: stack.append("this")
                elif op == 0x09: stack.append(0)
                elif op in (0xb4, 0xb5):
                    tag, field = pool[int.from_bytes(code[pc+1:after], "big")]
                    owner, name, desc = runtime_jar._member_ref(pool, field)
                    require(tag == 9 and owner == PROCESSOR.replace(".", "/") and name in state
                            and desc == ("Z" if name == "isTimeBased" else "J"), "field outside receiver frame")
                    if op == 0xb4:
                        require(stack.pop() == "this", "foreign read")
                        stack.append(state[name])
                    else:
                        val = stack.pop()
                        require(stack.pop() == "this" and name in ("prevFileTime", "currentFileTime"), "foreign write")
                        state[name] = val
                        writes.append(name)
                elif op == 0x94:
                    zero, value = stack.pop(), stack.pop()
                    require(value == "next" and zero == 0, "unqualified signed comparison")
                    stack.append(sign)
                elif op == 0x9a:
                    test = stack.pop()
                    require(test in (-1, 0, 1), "unbound branch")
                    if test: after = pc + int.from_bytes(code[pc+1:after], "big", signed=True)
                elif op == 0xb1:
                    require(not stack, "bad return")
                    break
                else: raise ValueError(f"unexpected effect or opcode {op:#x}")
                pc = after
            reached.update(visited)
            update = sign != 0 or not flag
            require(state == {"nextFileTime": "next", "prevFileTime": "next" if update else "previous",
                              "currentFileTime": 0 if update else "current", "isTimeBased": flag}
                    and writes == (["prevFileTime", "currentFileTime"] if update else []), "incorrect scheduling effect")
            partitions.append({"nextSign": sign, "timeBased": flag, "offsets": visited, "writes": writes, "post": state})
    require(reached == set(ops), "unvisited original instructions")
    record = {"entry": PROCESSOR + "#updateTime()V", "code": digest(code), "pool": digest(data[10:runtime_jar._pool(data)[1]]),
              "class": digest(data), "core": sha(core), "partitions": partitions, "qualifier": sha(Path(__file__)),
              "frame": "All long field values and both Boolean modes on a non-null exact PatternProcessor. No external calls, allocation, monitors, exceptions, writes to any other receiver or fields."}
    return record | {"key": digest(json.dumps(record, sort_keys=True).encode())}

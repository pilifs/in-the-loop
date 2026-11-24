"""Read the pinned stream and NIO instruction sequences used by the case's two correspondence checks."""
from pathlib import Path
import sys

from register import STREAM

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "examples/tools"))
from targets import change_inventory, runtime_jar

OWNER = STREAM.replace(".", "/")
NAMES = {0x02: "iconst_m1", 0x03: "iconst_0", 0x15: "iload", 0x1b: "iload_1", 0x1c: "iload_2",
         0x1d: "iload_3", 0x2a: "aload_0", 0x2b: "aload_1", 0x36: "istore", 0x3d: "istore_2",
         0x3e: "istore_3", 0x57: "pop", 0x60: "iadd", 0x64: "isub", 0x9f: "if_icmpeq", 0xac: "ireturn",
         0xb0: "areturn", 0xb1: "return", 0xb4: "getfield", 0xb5: "putfield", 0xb6: "invokevirtual",
         0xb7: "invokespecial", 0xb8: "invokestatic", 0xbf: "athrow"}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


class Body:
    def __init__(self, data, name, descriptor):
        pool, methods, _ = runtime_jar._declarations(data, with_code=True)
        self.flags, self.code, handlers = methods[name, descriptor]
        require(self.code and not handlers, f"unexpected exception table or missing body for {name}{descriptor}")
        self.ops = dict(change_inventory.instructions(self.code))
        self.members = {}
        for pc, op in self.ops.items():
            if 0xb2 <= op <= 0xb9:
                index = int.from_bytes(self.code[pc + 1:pc + 3], "big")
                self.members[pc] = runtime_jar._member_ref(pool, pool[index][1])

    def sequence(self, start=0, end=None):
        result = []
        for pc, op in self.ops.items():
            if pc < start or (end is not None and pc >= end):
                continue
            name = NAMES.get(op, f"op{op:02x}")
            if pc in self.members:
                owner, member, descriptor = self.members[pc]
                name += " " + owner + "." + member + ":" + descriptor
            elif op in (0x15, 0x36):
                name += " " + str(self.code[pc + 1])
            elif op == 0x9f:
                name += " " + str(self.branch(pc))
            result.append(name)
        return result

    def branch(self, pc):
        return pc + int.from_bytes(self.code[pc + 1:pc + 3], "big", signed=True)

    def successors(self, pc):
        op = self.ops[pc]
        if op in (0xbf, 0xac, 0xb0, 0xb1):
            return []
        if op == 0xa7:
            return [self.branch(pc)]
        next_pc = next(i for i in self.ops if i > pc)
        if 0x99 <= op <= 0xa6 or op in (0xc6, 0xc7):
            return [self.branch(pc), next_pc]
        require(op not in (0xa8, 0xa9, 0xaa, 0xab, 0xc4, 0xc8, 0xc9), "unhandled control flow")
        return [next_pc]

    def exits(self, start, stop):
        pending = [start]
        seen, exits = set(), set()
        while pending:
            pc = pending.pop()
            if pc in seen:
                continue
            seen.add(pc)
            if pc < start or pc >= stop:
                exits.add(pc)
            elif self.ops[pc] == 0xbf:
                continue
            elif self.ops[pc] in (0xac, 0xb0, 0xb1):
                exits.add("return")
            else:
                pending.extend(self.successors(pc))
        return exits

    def check_stream_frame(self, start, stop, local_calls):
        # The fresh exact receiver never leaves the stream code. External calls get its buffers or encoder.
        seq = list(self.ops)
        for index, pc in enumerate(seq):
            op = self.ops[pc]
            if not start <= pc < stop:
                continue
            require(op not in (0xb3, 0xb5, 0xb2, 0xba, 0xc2, 0xc3) and not 0x4f <= op <= 0x56,
                    "unexpected store, external static access or dispatch in the stream frame")
            require(op != 0xc4 and not (op == 0x19 and self.code[pc + 1] == 0), "unhandled receiver load")
            if op == 0x2a:
                after = seq[index + 1]
                target = self.members.get(after)
                require(target and target[0] == OWNER and
                        (self.ops[after] == 0xb4 or (self.ops[after] == 0xb7 and target[1:] in local_calls)),
                        "original receiver could escape or call an unchecked method")

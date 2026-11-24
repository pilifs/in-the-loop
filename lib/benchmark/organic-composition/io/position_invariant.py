"""Check the marked-position invariant on normal exits of the original stream bytecode."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

from bytecode import Body, OWNER, require, runtime_jar
from register import CASE, sha
from plan_run import JDK, ROOT, OUTPUT

NIO = "java/nio/"
BUFFER = NIO + "Buffer"
POSITION = "position:()I"


def jdk_summaries(jdk):
    methods = {}
    with zipfile.ZipFile(jdk / "jmods/java.base.jmod") as module:
        def resolve(concrete, name, descriptor):
            owner = NIO + concrete
            while owner:
                data = module.read("classes/" + owner + ".class")
                if (name, descriptor) in runtime_jar._declarations(data)[1]:
                    body = Body(data, name, descriptor)
                    methods[owner + "." + name + descriptor] = {"classSha256": hashlib.sha256(data).hexdigest(),
                                                               "codeSha256": hashlib.sha256(body.code).hexdigest()}
                    return owner, body
                owner = runtime_jar.super_class(data)
            raise ValueError("unresolved NIO dispatch")

        for concrete, parent in (("HeapByteBuffer", "ByteBuffer"), ("StringCharBuffer", "CharBuffer")):
            owner, getter = resolve(concrete, "position", "()I")
            require(owner == BUFFER and getter.sequence() == ["aload_0", "getfield java/nio/Buffer.position:I", "ireturn"],
                    "unexpected actual position getter")
            operations = ["mark"] if parent == "CharBuffer" else ["mark", "position"]
            for operation in operations:
                args = "()" if operation == "mark" else "(I)"
                loads = ["aload_0"] if args == "()" else ["aload_0", "iload_1"]
                specific = args + "L" + NIO + parent + ";"
                base = args + "L" + BUFFER + ";"
                owner, bridge = resolve(concrete, operation, base)
                require(owner == NIO + parent and bridge.sequence() ==
                        loads + ["invokevirtual " + owner + "." + operation + ":" + specific, "areturn"],
                        "unexpected NIO bridge")
                owner, override = resolve(concrete, operation, specific)
                require(owner == NIO + parent and override.sequence() ==
                        loads + ["invokespecial " + BUFFER + "." + operation + ":" + base, "pop", "aload_0", "areturn"],
                        "unexpected concrete NIO override")
        _, mark = resolve("Buffer", "mark", "()Ljava/nio/Buffer;")
        require(mark.sequence() == ["aload_0", "aload_0", "getfield java/nio/Buffer.position:I",
                                    "putfield java/nio/Buffer.mark:I", "aload_0", "areturn"], "mark moves the buffer")
        _, setter = resolve("Buffer", "position", "(I)Ljava/nio/Buffer;")
        require(setter.exits(0, 45) == {45} and setter.sequence(45) ==
                ["aload_0", "iload_1", "putfield java/nio/Buffer.position:I", "aload_0", "areturn"],
                "normal position setter can bypass the requested position")
    return methods


def execute(instructions, state, mark, guards):
    """Translate the admitted straight-line mark and normal reset suffix to equality constraints."""
    stack = []
    for text in instructions:
        op, _, operand = text.partition(" ")
        if op == "aload_0":
            stack.append("stream")
        elif op in ("iconst_0", "iconst_m1"):
            stack.append("0" if op == "iconst_0" else "(- 1)")
        elif op in ("getfield", "putfield"):
            owner, field = operand.split(".")
            name = field.split(":")[0]
            require(owner == OWNER and name in state, "unmodelled stream field")
            if op == "getfield":
                require(stack.pop() == "stream", "wrong field reader")
                stack.append(state[name])
            else:
                value = stack.pop()
                require(stack.pop() == "stream" and name in ("cBufMark", "bBufMark"), "wrong field writer")
                state[name] = value
        elif op == "invokevirtual":
            owner, member = operand.split(".")
            if member == POSITION:
                buf = stack.pop()
                require(owner == NIO + ("CharBuffer" if buf == "chars" else "ByteBuffer")
                        and buf in ("chars", "bytes"), "wrong position receiver")
                stack.append(state[buf])
            elif operand == "java/nio/ByteBuffer.position:(I)Ljava/nio/Buffer;":
                value = stack.pop()
                require(stack.pop() == "bytes", "wrong restored buffer")
                state["bytes"] = value
                stack.append("bytes")
            elif member == "mark:()Ljava/nio/Buffer;":
                require((owner, stack[-1]) in ((NIO + "CharBuffer", "chars"), (NIO + "ByteBuffer", "bytes")),
                        "wrong NIO mark receiver")
            elif operand == OWNER + ".mark:(I)V":
                require(mark and stack.pop() == "0" and stack.pop() == "stream", "unexpected re-mark call")
                execute(mark, state, None, guards)
            else:
                raise ValueError("unmodelled invocation " + operand)
        elif op == "if_icmpeq":
            right, left = stack.pop(), stack.pop()
            guards.append(f"(= {left} {right})")
        elif op == "pop":
            stack.pop()
        elif op == "return":
            require(not stack, "nonempty return stack")
        else:
            raise ValueError("unmodelled normal-path instruction " + text)


def projected(data):
    mark = Body(data, "mark", "(I)V")
    reset = Body(data, "reset", "()V")
    for body in (mark, reset):
        require(list(body.ops.values()).count(0xb1) == 1 and list(body.ops.values())[-1] == 0xb1,
                "unexpected normal method exit")
    require(reset.sequence(0, 8) == ["aload_0", "getfield " + OWNER + ".cBufMark:I", "iconst_m1", "if_icmpeq 170"],
            "changed active-mark check")
    require(reset.exits(8, 89) == {89} and reset.exits(103, 148) == set()
            and reset.ops[100] == 0x9f and reset.branch(100) == 148
            and reset.sequence(89, 103)[-1] == "if_icmpeq 148", "reset can bypass the position check")
    # Any amount of re-encoding may precede the check. Forget both live positions there.
    reset.check_stream_frame(8, 89, {("fillBuffer", "()V")})
    for name, desc in (("fillBuffer", "()V"), ("read", "()I"), ("read", "([BII)I")):
        body = Body(data, name, desc)
        body.check_stream_frame(0, len(body.code), {("fillBuffer", "()V")})
    state = {"cBuf": "chars", "bBuf": "bytes", "cBufMark": "savedC", "bBufMark": "savedB",
             "chars": "liveC", "bytes": "liveB"}
    initial = state.copy()
    entry_guards = []
    execute(mark.sequence(), initial, None, entry_guards)
    require(not entry_guards, "conditional mark initialization")
    guards = []
    execute(reset.sequence(89, 103) + reset.sequence(148), state, mark.sequence(), guards)
    require(guards == ["(= liveC savedC)"], "mismatched character position can escape normally")
    return initial, state, guards, {"normalResetSuffix": reset.sequence(89, 103) + reset.sequence(148),
                                    "mark": mark.sequence(), "resetCodeSha256": hashlib.sha256(reset.code).hexdigest()}


def solve(state, guards, target_chars, target_bytes):
    slots = ("chars", "bytes", "cBufMark", "bBufMark")
    want = [target_chars, target_bytes] * 2
    predicates = " ".join(f"(= {state[k]} {v})" for k, v in zip(slots, want))
    lines = ["(set-logic QF_LIA)"]
    for var in ("savedC", "savedB", "liveC", "liveB"):
        lines.extend((f"(declare-const {var} Int)", f"(assert (and (<= 0 {var}) (<= {var} 2147483647)))"))
    lines.extend(f"(assert {g})" for g in guards)
    lines += [f"(assert (not (and {predicates})))", "(check-sat)"]
    query = "\n".join(lines) + "\n"
    outcome = subprocess.run(["z3", "-in"], input=query, text=True, capture_output=True, check=True, timeout=10).stdout.strip()
    return {"query": query, "counterexample": outcome}


def main():
    profiles = json.loads((ROOT / OUTPUT / "io/charset-profiles.json").read_bytes())["profiles"]
    require({tuple(p["bufferClasses"]) for p in profiles} == {("java.nio.StringCharBuffer", "java.nio.HeapByteBuffer")},
            "unqualified concrete buffer types")
    result = {"scope": "A fresh exact stream with the profiled JDK buffers and an active mark, one thread, and intervening read() or read(byte[],int,int) calls. Every reset in the induction returns normally. Re-encoding positions are unconstrained before the original success guard.",
              "nioMethodBodies": jdk_summaries(JDK), "jdk": json.loads((CASE.parent / "freeze.json").read_bytes())["jdk"],
              "z3": subprocess.check_output(["z3", "--version"], text=True).strip(), "sides": {}}
    for side in ("old", "new"):
        source, = json.loads((CASE / side / "prepared.json").read_bytes())["classpath"]
        jar = Path(source["file"])
        require(sha(jar) == source["sha256"], "changed original JAR")
        data = runtime_jar.read_class(jar, OWNER)
        initial, normal, guards, trace = projected(data)
        base = solve(initial, [], "liveC", "liveB")
        step = solve(normal, guards, "savedC", "savedB")
        require(base["counterexample"] == "unsat" and step["counterexample"] == ("unsat" if side == "new" else "sat"),
                "original deployment gave an unexpected induction result")
        result["sides"][side] = {"jar": source["sha256"], **trace, "normalPositionExpressions": normal,
                                 "markBase": base, "normalResetStep": step}
    out = ROOT / OUTPUT / "io/normal-reset-invariant.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print("Both mark bases proved. Fixed normal-reset step proved. Parent normal-reset step refuted.")


if __name__ == "__main__":
    main()

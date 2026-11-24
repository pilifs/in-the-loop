"""Untrusted keys for the range guard and both branches of a bidirectional fill."""
from prepare import digest
from range_certificate import disassemble


def issue(req, artifact, callee):
    raw = req.read_bytes()
    fields = dict(line.split(" ", 1) for line in raw.decode().splitlines())
    entry = tuple(fields["entry"].split())
    wrapper = tuple(fields["companion"].split())
    owner = disassemble(artifact)
    helper = disassemble(callee)
    # The bridge on this release invokes the same-named bounds check with length, from and to.
    ext = (wrapper[0], "(III)V")
    keys = set()
    for role, (name, desc), code in [
        ("guard", ext, helper[ext]["code"]), ("wrapper", wrapper, owner[wrapper]["code"]),
        ("fill", entry, owner[entry]["code"]),
    ]:
        by_pc = {ins.pc: pos for pos, ins in enumerate(code)}
        heads = [int(ins.arg) for ins in code if ins.op == "goto" and int(ins.arg) < ins.pc]
        queue = [0]
        visited = set()
        while queue:
            pc = queue.pop()
            if pc in visited:
                continue
            visited.add(pc)
            pos = by_pc[pc]
            ins = code[pos]
            prefix = f"{name}{desc}@{pc}>"
            if ins.op == "return":
                keys.add(prefix + "exit " + ("exact-write-frame" if role == "fill" else "normal-unchanged"))
                continue
            fall = code[pos + 1].pc
            if ins.op == "goto":
                dests = [int(ins.arg)]
            elif ins.op.startswith("if"):
                dests = [int(ins.arg)]
                if role != "guard" or code[pos - 1].op == "getstatic":
                    dests.append(fall)
            else:
                dests = [fall]
            for end in dests:
                kinds = ["step"]
                if ins.op == "getstatic":
                    kinds.append("local-static-boolean")
                if ins.op == "arraylength":
                    kinds.append("nonnull")
                if ins.op == "invokestatic":
                    kinds.append("resolved-valid-range")
                if role == "guard" and ins.op.startswith("if"):
                    kinds.append("implied-by-range")
                if role == "fill" and len(heads) == 2:
                    down, up = heads
                    if end == down:
                        kinds.extend(["empty-written-suffix"] if pc < down
                                     else ["variant-decreases", "extend-written-suffix"])
                    if end == up:
                        kinds.extend(["empty-written-prefix"] if pc < up
                                     else ["variant-decreases", "extend-written-prefix"])
                    if down <= pc < up and ins.op == "ifeq" and end != fall:
                        kinds.append("exhausted-cursor-minus-one")
                    if ins.op == "iastore":
                        kinds.append("in-bounds-suffix-store" if pc < up else "in-bounds-prefix-store")
                    if ins.op == "iinc":
                        kinds.append("no-signed-overflow")
                keys.update(prefix + str(end) + " " + k for k in kinds)
            queue.extend(dests)
    return "\n".join(["certificate 1", "request " + digest(raw), "hints prefix-and-suffix remaining", *sorted(keys)]) + "\n"

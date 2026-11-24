"""Issue untrusted cut-point and edge hints for the opt-in range experiment."""

from pathlib import Path
import shutil
import sys
import tempfile

from certificate import methods
from prepare import digest
from controls import JDK

FILL = "([IIII)V"
GUARD = "(III)V"
CALLER = "range-fill-caller-frame-observation-v1"


def disassemble(path):
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "Input.class"
        shutil.copyfile(path, f)
        return methods(JDK / "bin/javap", f)[0]


def collect(table, spec, role, head, keys):
    name, desc = spec
    code = table[spec]["code"]
    offsets = {ins.pc: i for i, ins in enumerate(code)}
    pending = [0]
    seen = set()
    while pending:
        pc = pending.pop()
        if pc in seen:
            continue
        seen.add(pc)
        i = offsets[pc]
        ins = code[i]
        prefix = f"{name}{desc}@{pc}>"
        if ins.op in ("ireturn", "return"):
            for k in {
                "guard": ["normal-unchanged"],
                "fill": ["exact-write-frame"],
                "caller": ["exact-write-frame", "observation"],
            }[role]:
                keys.add(prefix + "exit " + k)
            continue
        dest = []
        if ins.op == "goto" or ins.op.startswith("if"):
            dest.append(int(ins.arg))
        # Both JDK and control guards put the exception allocation on fall-through.
        # The consumer must derive this from the admitted arguments and actual branch.
        if ins.op != "goto" and not (role == "guard" and ins.op.startswith("if")):
            dest.append(code[i + 1].pc)
        for end in dest:
            kinds = ["step"]
            if ins.op == "arraylength":
                kinds.append("nonnull")
            if ins.op == "invokestatic":
                kinds.append("apply-checked-write-frame" if role == "caller" else "resolved-valid-range")
            if role == "guard" and ins.op.startswith("if"):
                kinds.append("implied-by-range")
            if role == "caller" and ins.op == "iaload":
                kinds.extend(["shared-in-range", "shared-outside-range", "distinct-root"])
            if role == "fill":
                if ins.op in ("iastore", "lastore"):
                    kinds.append("in-bounds-prefix-store")
                if ins.op == "iinc":
                    kinds.append("no-signed-overflow")
                if end == head:
                    kinds.extend(
                        ["empty-written-prefix"]
                        if pc < head
                        else ["extend-written-prefix", "variant-decreases"]
                    )
            keys.update(f"{prefix}{end} {k}" for k in kinds)
        pending.extend(dest)


def issue(request, artifact, callee=None):
    data = request.read_bytes()
    fields = dict(line.split(" ", 1) for line in data.decode().splitlines())
    entry, companion = (tuple(fields[k].split()) for k in ("entry", "companion"))
    main = disassemble(artifact)
    if fields["theorem"] == CALLER:
        fills, fill, guard = disassemble(callee), companion, ("rangeCheck", GUARD)
    else:
        fills, fill, guard = main, entry, companion
    code = fills[fill]["code"]
    head = next(int(i.arg) for i in code if i.op == "goto" and int(i.arg) <= i.pc)
    slot = next(int(i.arg.split(",")[0]) for i in code if i.op == "iinc")
    keys = set()
    collect(fills, guard, "guard", head, keys)
    collect(fills, fill, "fill", head, keys)
    if fields["theorem"] == CALLER:
        collect(main, entry, "caller", head, keys)
    return (
        "\n".join(
            [
                "certificate 1",
                "request " + digest(data),
                f"hints written-prefix remaining {head} {slot}",
                *sorted(keys),
            ]
        )
        + "\n"
    )


if __name__ == "__main__":
    request, artifact, dest, *callee = map(Path, sys.argv[1:])
    dest.write_text(issue(request, artifact, *callee))

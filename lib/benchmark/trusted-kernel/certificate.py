"""Untrusted hints derived with javap. The consumer receives only the resulting text."""

from pathlib import Path
import os
import shutil
import sys
import tempfile

from prepare import HERE, SCALAR, digest

sys.path.insert(0, str(HERE.parents[1] / "python"))
from jvm_disassembly import methods


def issue(request, artifact, witness=("7", "7,7")):
    raw = request.read_bytes()
    fields = dict(line.split(" ", 1) for line in raw.decode().splitlines())
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "Input.class"
        shutil.copyfile(artifact, f)
        javap = (
            Path(os.environ.get("JAVA21_HOME", Path.home() / ".sdkman/candidates/java/21.0.13.0+9-tem"))
            / "bin/javap"
        )
        table, _ = methods(javap, f)
    keys = set()
    if fields["theorem"] == SCALAR:
        hint = "hints scalar"
        for side in ("entry", "companion"):
            name, desc = fields[side].split()
            for ins in table[name, desc]["code"]:
                if ins.op == "ireturn":
                    keys.add(f"{name}{desc}@{ins.pc}>exit normal-frame-value")
    elif fields["theorem"] == "least-index-frame-total-v1":
        helper_name, helper_desc = fields["companion"].split()
        helper = table[helper_name, helper_desc]["code"]
        back = next(i for i in helper if i.op == "goto" and int(i.arg) <= i.pc)
        head = int(back.arg)
        inc = next(i for i in helper if i.op == "iinc")
        slot = int(inc.arg.split(",")[0])
        hint = f"hints first-prefix remaining {head} {slot} {witness[0]} {witness[1]}"
        for side in ("entry", "companion"):
            name, desc = fields[side].split()
            code = table[name, desc]["code"]
            for idx, ins in enumerate(code):
                prefix = f"{name}{desc}@{ins.pc}>"
                if ins.op == "ireturn":
                    keys.update([prefix + "exit result", prefix + "exit frame"])
                    continue
                fall = [code[idx + 1].pc] if ins.op != "goto" else []
                dests = fall + ([int(ins.arg)] if ins.op.startswith("if") or ins.op == "goto" else [])
                for end in dests:
                    edge = prefix + str(end) + " "
                    keys.add(edge + "step")
                    if ins.op in ("arraylength", "iaload", "iastore", "laload", "lastore"):
                        keys.add(edge + "safe")
                    if ins.op == "invokestatic":
                        keys.add(edge + "resolved-full-range")
                    if side == "companion" and end == head:
                        if ins.pc < head:
                            keys.add(edge + "invariant-entry")
                        else:
                            keys.update([edge + "invariant-preserved", edge + "variant-decreases"])
    else:
        raise ValueError("no issuer for that theorem")
    return "\n".join(["certificate 1", "request " + digest(raw), hint, *sorted(keys)]) + "\n"


if __name__ == "__main__":
    request, artifact, cert = map(Path, sys.argv[1:4])
    cert.write_text(issue(request, artifact, sys.argv[4:] or ("7", "7,7")))

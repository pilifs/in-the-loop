"""Untrusted hints derived with javap. The consumer receives only the resulting text."""
from pathlib import Path
import os
import shutil
import sys
import tempfile

from prepare import HERE, SCALAR, digest
sys.path.insert(0, str(HERE.parents[1] / "python"))
from jvm_disassembly import methods


def issue(request, artifact):
    raw = request.read_bytes()
    fields = dict(line.split(" ", 1) for line in raw.decode().splitlines())
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "Input.class"
        shutil.copyfile(artifact, f)
        javap = Path(os.environ.get("JAVA21_HOME", Path.home() / ".sdkman/candidates/java/21.0.13.0+9-tem")) / "bin/javap"
        table, _ = methods(javap, f)
    keys = set()
    if fields["theorem"] != SCALAR:
        raise ValueError("no issuer for that theorem")
    for side in ("entry", "companion"):
        name, desc = fields[side].split()
        for ins in table[name,desc]["code"]:
            if ins.op == "ireturn":
                keys.add(f"{name}{desc}@{ins.pc}>exit normal-frame-value")
    return "\n".join(["certificate 1", "request " + digest(raw), "hints scalar", *sorted(keys)]) + "\n"


if __name__ == "__main__":
    request, artifact, cert = map(Path, sys.argv[1:])
    cert.write_text(issue(request, artifact))

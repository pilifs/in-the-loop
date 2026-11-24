"""Check the signed-long remainder theorem against both original production method bodies."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from plan_run import HERE, ROOT, OUTPUT
sys.path.insert(0, str(ROOT/"examples/tools"))
from targets import runtime_jar

def run():
    base = HERE/"threeten"
    theorem = base/"FloorMod.lean"
    kernel = subprocess.run(["lean", theorem], capture_output=True, text=True, check=True, timeout=90)
    match = re.fullmatch(r"'ThreeTen.floorMod86400' depends on axioms: \[([^\]]*)\]\s*", kernel.stdout, re.S)
    if not match or set(match[1].split(", ")) - {"propext", "Classical.choice", "Quot.sound"}:
        raise ValueError("kernel did not establish the signed remainder theorem")
    sides = {}
    for side in ("old","new"):
        manifest = json.loads((base/side/"prepared.json").read_bytes())
        artifact = manifest["classpath"][0]
        jar = Path(artifact["file"])
        if hashlib.sha256(jar.read_bytes()).hexdigest() != artifact["sha256"]:
            raise ValueError("unexpected ThreeTen JAR")
        body = runtime_jar.read_class(jar,"org/threeten/bp/jdk8/Jdk8Methods")
        flags, code, handlers = runtime_jar._declarations(body,with_code=True)[1]["floorMod","(JI)I"]
        # lload_0, iload_2, i2l, lrem, iload_2, i2l, ladd, iload_2, i2l, lrem, l2i, ireturn
        if flags != 9 or handlers != 0 or code != bytes.fromhex("1e1c85711c85611c857188ac"):
            raise ValueError("original helper no longer implements the bound straight-line expression")
        sides[side] = {"commit":manifest["commit"],"jar":artifact["sha256"],
                       "class":hashlib.sha256(body).hexdigest(),"bytecode":code.hex(),"flags":flags,"handlers":handlers}
    out = ROOT/OUTPUT/"threeten"/"all-long-remainder.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps({"theoremSha256":hashlib.sha256(theorem.read_bytes()).hexdigest(),
                              "lean":subprocess.check_output(["lean","--version"],text=True).strip(),
                              "kernel":kernel.stdout.strip(),"sides":sides,
                              "domain":"every signed long dividend, divisor 86400, after successful class initialization",
                              "frame":"the bound instructions read only primitive arguments and write no heap or static field",
                              "oracle":"Euclidean remainder on mathematical integers; both machine conversions fit"},indent=2)+"\n")

if __name__ == "__main__":
    run()

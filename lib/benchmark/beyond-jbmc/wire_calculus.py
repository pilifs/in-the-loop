"""Check the byte-order algebra and finite-record induction in a separate Lean process."""
import os
from pathlib import Path
import subprocess

from history import HERE, OUTPUT, digest, encoded, scratch

LEAN = Path.home()/".elan/toolchains/leanprover--lean4---v4.36.0/bin/lean"
SOURCE = HERE/"wire/WireRecords.lean"
THEOREMS = ("fourCompositions","compatible","palindromeBijection","wrongIdentity","finiteRecords")


if __name__=="__main__":
    with scratch(prefix="wire-lean-") as tmp:
        work=Path(tmp)
        version=subprocess.check_output([LEAN,"--version"],text=True).strip()
        cmd=[str(LEAN),str(SOURCE)]
        result=subprocess.run(cmd,cwd=work,text=True,capture_output=True,timeout=150)
        print(result.stdout,result.stderr,flush=True)
        if result.returncode or "sorry" in result.stdout or not all("WireRecords."+name in result.stdout for name in THEOREMS):
            raise SystemExit("incomplete kernel check")
        control=work/"WrongWire.lean"
        control.write_text(SOURCE.read_text().replace("≠ 0x01020304 := by decide","= 0x01020304 := by decide"))
        wrong=subprocess.run([LEAN,control],cwd=work,text=True,capture_output=True,timeout=150)
        if wrong.returncode==0 or "error:" not in wrong.stdout:
            raise ValueError("wrong wire identity was accepted or not checked")
        out=OUTPUT/"assurance/wire-calculus.json"
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(encoded({"theorems":THEOREMS,"sourceSha256":digest(SOURCE),"argv":cmd,"lean":version,
              "executableSha256":digest(LEAN),"kernelOutput":result.stdout,"rejectedIdentity":wrong.stdout,
              "wrongSourceSha256":digest(control),"job":os.environ.get("VERIFY_JOB_ID"),
              "scope":"fixed-width bit-vector algebra; arbitrary finite sequences conditional on the single-record suffix law"}))

"""Measure an opt-in check in a fresh process. Only allow the consumer to read its bundle."""
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

from prepare import HERE, digest

LEAN = Path(os.environ.get("KERNEL_LEAN_HOME", Path.home() / ".elan/toolchains/leanprover--lean4---v4.36.0"))
READ = "execute,read-file,read-dir"


def measured(command, cwd, env=None):
    with tempfile.TemporaryFile() as out:
        start = time.monotonic()
        proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT)
        _, status, usage = os.wait4(proc.pid, 0)
        proc.returncode = os.waitstatus_to_exitcode(status)
        out.seek(0)
        return {"exit":proc.returncode, "stdout":out.read().decode(errors="replace").strip(),
                "wallSeconds":round(time.monotonic()-start, 6), "peakKiB":usage.ru_maxrss}


def contained(command, folder, libraries=()):
    permissions = ["setpriv", "--no-new-privs", "--landlock-access", "fs",
                   "--landlock-rule", f"path-beneath:{READ}:{folder}"]
    for path in libraries:
        path = Path(path).resolve()
        access = READ if path.is_dir() else "read-file"
        permissions += ["--landlock-rule", f"path-beneath:{access}:{path}"]
    return measured([*permissions, *command], folder, {"PATH":"/usr/bin", "LC_ALL":"C"})


def build_kernel(folder):
    binary = folder / "kernel"
    build = measured(["rustc","--edition=2021","-C","opt-level=2","-C","target-feature=+crt-static",
                      HERE / "main.rs","-o",binary],folder)
    if build["exit"]:
        raise ValueError(build)
    build["binarySha256"] = digest(binary.read_bytes())
    return binary, build


def fresh_rust(binary, request, cert, artifact, support=()):
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp)
        args=[]
        for src, name in [(binary,"kernel"),(request,"external.request"),(cert,"evidence.cert"),
                          (artifact,"artifact.bin"),*((p,f"support-{i}.bin") for i,p in enumerate(support))]:
            shutil.copy2(src,folder/name)
            args.append("./" + name)
        return contained(args, folder)


def summarize(runs):
    if len({(v["exit"],v["stdout"]) for v in runs})!=1:
        raise ValueError("fresh checks disagree")
    return {"exit":runs[0]["exit"],"outcome":runs[0]["stdout"],"checks":runs,
            "medianPeakKiB":statistics.median(v["peakKiB"] for v in runs),
            "medianWallSeconds":statistics.median(v["wallSeconds"] for v in runs)}


def generate(request, artifact, dest):
    result = measured([sys.executable,"-B",HERE / "certificate.py",request,artifact,dest], HERE)
    if result["exit"]:
        raise ValueError(result)
    return result


def lean_check(request, cert, artifact):
    # This adapter selects a kernel-checked theorem only for the measured request.
    # The quoted source bytes are read afresh inside Lean by its artifactBytes elaborator.
    import hashlib
    rows=request.read_text().splitlines()
    if len(rows)!=6 or rows[:3]!=["request 1","theorem scalar-equality-v1","environment initialized-verified-jvm-v1"]:
        return {"exit":3,"stdout":"unsupported external theorem","peakKiB":0,"wallSeconds":0}
    expected_class="class fixtures/Scalar " + hashlib.sha256(artifact.read_bytes()).hexdigest()
    if rows[3]!=expected_class or rows[4]!="entry multiply (I)I":
        return {"exit":2,"stdout":"rejected external binding","peakKiB":0,"wallSeconds":0}
    peers={"companion add (I)I":("add",3),"companion shifted (I)I":("shifted",5)}
    if rows[5] not in peers:
        return {"exit":3,"stdout":"unsupported scalar companion","peakKiB":0,"wallSeconds":0}
    peer,pc=peers[rows[5]]
    expected=["certificate 1","request "+digest(request.read_bytes()),"hints scalar",
              *sorted(["multiply(I)I@3>exit normal-frame-value",f"{peer}(I)I@{pc}>exit normal-frame-value"])]
    if cert.read_text().splitlines()!=expected:
        return {"exit":2,"stdout":"rejected scalar certificate","peakKiB":0,"wallSeconds":0}
    with tempfile.TemporaryDirectory() as tmp:
        folder=Path(tmp)
        shutil.copyfile(artifact,folder/"artifact.bin")
        shutil.copyfile(HERE/"Scalar.lean",folder/"Scalar.lean")
        libs=[LEAN, "/usr/lib", "/lib64", "/dev/urandom"]
        run=contained([str(LEAN/"bin/lean"),"Scalar.lean"],folder,libs)
    if run["exit"]:
        raise ValueError(run)
    # Only these foundational Lean axioms occur, with no native evaluator or proof holes.
    expected_axioms="[propext, Classical.choice, Quot.sound]"
    for theorem in ("originalBytesEqual","shiftedRefuted"):
        if f"'ScalarKernel.{theorem}' depends on axioms: {expected_axioms}" not in run["stdout"].splitlines():
            raise ValueError("unexpected Lean axiom inventory: " + run["stdout"])
    run["stdout"] += ("\naccepted scalar-equality-v1 originalBytesEqual" if peer=="add"
                      else "\nrejected scalar values differ at x=0: shiftedRefuted")
    run["exit"]=0 if peer=="add" else 2
    return run


def scalar(out):
    out.mkdir(parents=True,exist_ok=True)
    artifact=HERE/"inputs/Scalar.bin"
    cases=[]
    with tempfile.TemporaryDirectory() as tmp:
        binary,build=build_kernel(Path(tmp))
        for peer,want in (("add",0),("shifted",2)):
            req=HERE/"requests"/(peer+".request")
            cert=out/(peer+".cert")
            gen=generate(req,artifact,cert)
            for route,runner in [("Rust",lambda: fresh_rust(binary,req,cert,artifact)),
                                 ("Lean",lambda: lean_check(req,cert,artifact))]:
                result=summarize([runner() for _ in range(3)])
                if result["exit"]!=want: raise ValueError(result)
                cases.append({"route":route,"checkerVersion":build["binarySha256"] if route=="Rust" else
                              digest((HERE/"Scalar.lean").read_bytes()),"classSha256":digest(artifact.read_bytes()),
                              "request":req.read_text(),"requestSha256":digest(req.read_bytes()),"control":peer,
                              "expected":"accepted" if want==0 else "rejected","actual":"accepted" if result["exit"]==0 else "rejected",
                              "sizes":{"class":artifact.stat().st_size,"request":req.stat().st_size,"certificate":cert.stat().st_size},
                              "generation":gen,**result})
    record={"schema":"trusted-scalar/v1","rustBuild":build,"rustVersion":subprocess.check_output(["rustc","-V"],text=True).strip(),
            "leanVersion":subprocess.check_output([LEAN/"bin/lean","--version"],text=True).strip(),"cases":cases}
    (out/"measurements.json").write_text(json.dumps(record,indent=2)+"\n")
    print([(v["route"],v["control"],v["actual"]) for v in cases])


if __name__=="__main__":
    scalar(Path(sys.argv[1]) if len(sys.argv)>1 else HERE/"evidence/scalar")

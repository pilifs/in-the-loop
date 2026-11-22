"""Check Avro's original accessor installation and Hadoop's bounded writable-backing contract."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from startup import HERE, ROOT, document, materialize, runtime_jdk, runtime_maven

ROOTS = ["org.apache.avro.Schema", "org.apache.hadoop.io.BytesWritable"]
PROFILE = {"emptyEnvironment": True, "preinitializeTogether": True, "processors": 2, "rootWorkingDirectory": True}


def one(number, side, output):
    folder, = (ROOT / "examples").glob(number + "-*")
    jdk = Path(runtime_jdk.home("21"))
    exe = Path(os.environ["JVMCONTRACT"]).resolve()
    out = output/number/side
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="producer-proofs-") as tmp:
        work = Path(tmp)
        cp, bindings = materialize(folder, side, work)
        sources = ["SchemaRegistration"] + (["WritableBacking"] if number == "355" else [])
        classes = work/"classes"
        classes.mkdir()
        args = [jdk/"bin/javac", "-J-Djava.io.tmpdir="+tmp, "-parameters", "-g", "-classpath", os.pathsep.join(map(str, cp)),
                "-d", classes, *[HERE/(name+".java") for name in sources]]
        subprocess.run(args, check=True)
        env = {"JAVA_HOME": str(jdk), "PATH": str(jdk/"bin")+os.pathsep+os.defpath, "LC_ALL": "C",
               "TMPDIR": tmp, "JVMCONTRACT_JAR_RELEASE": "21"}
        records = []
        tasks = [("SchemaRegistration", m, None) for m in ("originalInstall", "firstInstallation", "priorInstallation")]
        if number == "355":
            tasks += [("WritableBacking", m, scope) for scope in ("ordinary", "observed") for m in ("shrink", "growthChangesBacking")]
        for source, method, scope in tasks:
            name = source+"-"+method+("-"+scope if scope else "")
            jvm = subprocess.run([jdk/"bin/java", "-XX:ActiveProcessorCount=2", "-Djava.io.tmpdir="+tmp,
                            "-cp", os.pathsep.join(map(str, [classes, *cp])), "foundation."+source, method],
                            cwd="/", env={}, capture_output=True, timeout=30)
            if jvm.returncode or jvm.stdout.strip() != b"held":
                raise ValueError(f"{name} original JVM control failed: {jvm.stderr.decode(errors='replace')[-700:]}")
            target = "foundation."+source+"#"+method
            bound = 6 if source == "WritableBacking" else 128
            cmd = [exe, "prove", target, "--classes", classes, "--classpath", os.pathsep.join(map(str, cp)),
                   "--engine", "native", "--gaps", "strict", "--unwind", "64", "--max-array-length", str(bound),
                   "--work", work/name, "--json"]
            if method == "shrink":
                cmd += ["--assume", "length >= 0 && length <= bytes.length"]
            if scope == "observed":
                for root in ROOTS: cmd += ["--observed-initializer", root]
                cmd += ["--observed-runtime", json.dumps(PROFILE)]
            start = time.monotonic()
            checked = subprocess.run(cmd, cwd=work, env=env, capture_output=True, timeout=60)
            elapsed = time.monotonic() - start
            if not checked.stdout:
                raise ValueError(checked.stderr.decode(errors="replace")[-800:])
            native, = json.loads(checked.stdout)
            stated = native["stated"]
            if stated["gap_mode"] != "strict" or native["target"] != target:
                raise ValueError("wrong native checker scope")
            assumptions = [a["id"] for a in stated["assumptions"] if a["kind"] == "library"]
            if scope == "observed":
                claim = json.loads((folder/"claims/direct-limit-writable-startup.json").read_text())
                observed = {s.split(":")[1]:s.split(":")[-1] for s in assumptions}
                if observed != claim["observedInitializers"]:
                    raise ValueError("producer startup differs from the registered direct consumer")
            elif assumptions:
                raise ValueError("ordinary producer used a library assumption")
            path = out/(name+".native.json")
            path.write_bytes(checked.stdout)
            records.append({"claim": name, "verdict": native["verdict"], "problem": native["problem"],
                            "scope": scope or "ordinary", "vacuity": stated.get("vacuity"),
                            "inputGuard": native["assume"], "jvmControl": "held", "seconds": round(elapsed,4),
                            "raw": path.name, "sha256": hashlib.sha256(checked.stdout).hexdigest(),
                            "classSha256": runtime_maven.sha256_of(classes/"foundation"/(source+".class"))})
        document(out/"evidence.json", {"schema": "domain-producer-claims/v1", "inputs": bindings,
                 "checker": runtime_maven.sha256_of(exe), "jdkModules": runtime_maven.sha256_of(jdk/"lib/modules"),
                 "claims": records})
        for r in records: print(number,side,r["claim"],r["verdict"],flush=True)
        return all(r["verdict"] == "verified" and (r["vacuity"] or {}).get("status") == "non-vacuous"
                   for r in records if not (r["scope"] == "ordinary" and r["claim"].startswith("WritableBacking")))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    results = [one(n, side, args.output.resolve()) for n in ("355", "361") for side in ("parent", "fix")]
    raise SystemExit(0 if all(results) else 1)

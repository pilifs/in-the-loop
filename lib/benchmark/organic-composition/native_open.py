"""Keep the first strict native result for the same generated public history on each deployment."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from plan_run import HERE, JDK, ROOT, OUTPUT


def measure(case, method, initializer=None):
    folder = HERE / case
    results = {}
    env = {**os.environ, "JAVA_HOME": str(JDK), "PATH": str(JDK/"bin")+os.pathsep+os.environ["PATH"]}
    checker = os.environ.get("JVMCONTRACT") or ROOT/"lib/target/release/jvmcontract"
    for side in ("old", "new"):
        doc = json.loads((folder/side/"prepared.json").read_bytes())
        cp = os.pathsep.join(r["file"] for r in doc["classpath"])
        with tempfile.TemporaryDirectory(prefix="organic-opening-") as temp:
            subprocess.run([JDK/"bin/javac", "-g", "-parameters", "-proc:none", "-encoding", "UTF-8",
                            "-cp", cp, "-d", temp, folder/"UpgradeProbe.java"], check=True)
            cmd = [str(checker),"prove","--classes",temp,"UpgradeProbe#"+method,"--classpath",cp,"--engine","native",
                   "--assert","result == true","--unwind","16","--json"]
            if initializer:
                cmd.extend(["--observed-initializer", initializer])
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=150)
            results[side] = {"argv": cmd, "exit": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr,
                             "artifacts": doc["classpath"]}
            if not proc.stdout.strip() or not json.loads(proc.stdout):
                raise ValueError(f"missing native disposition on {side}: {proc.stderr[:200]}")
    target = ROOT / OUTPUT / case / ("observed-native.json" if initializer else "first-native.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(results, indent=2)+"\n")


if __name__ == "__main__":
    measure(*sys.argv[1:])

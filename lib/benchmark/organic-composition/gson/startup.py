"""Retry the original strict public observer at the two real Gson startup dependencies."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from register import BASE, CASE, READER, sha
from freeze import verify
from matrix import write
from plan_run import JDK, OUTPUT, ROOT


def main():
    verify()
    target = ROOT / OUTPUT / "gson"
    first = json.loads((target / "first-native.json").read_bytes())
    checker = os.environ.get("JVMCONTRACT") or ROOT / "lib/target/release/jvmcontract"
    environment = os.environ | {"JAVA_HOME": str(JDK), "PATH": str(JDK / "bin") + os.pathsep + os.environ["PATH"]}
    style = BASE + "FormattingStyle"
    results = {"opening": sha(target / "first-native.json"), "sides": {}}
    for side in ("old", "new"):
        manifest = json.loads((CASE / side / "prepared.json").read_bytes())
        cp = os.pathsep.join(row["file"] for row in manifest["classpath"])
        if first[side]["artifacts"] != manifest["classpath"] or "java.lang.String.matches" not in first[side]["disposition"]["reason"]:
            raise ValueError("missing original String.matches opening")
        attempts = []
        with tempfile.TemporaryDirectory(prefix="gson-initializers-") as classes:
            subprocess.run([JDK / "bin/javac", "-g", "-parameters", "-proc:none", "-cp", cp, "-d", classes, CASE / "UpgradeProbe.java"], check=True)
            for owners in ([style], [style, READER]):
                cmd = [checker, "prove", "--classes", classes, "UpgradeProbe#readPaths()Z", "--classpath", cp, "--engine", "native",
                       "--assert", "result == true", "--unwind", "16", "--json"]
                for owner in owners: cmd.extend(["--observed-initializer", owner])
                p = subprocess.run(cmd, env=environment, text=True, capture_output=True, timeout=150)
                if p.stdout.strip():
                    row, = json.loads(p.stdout)
                    if row.get("verdict") not in ("verified", "unverifiable", "refuted"):
                        raise ValueError("missing native public verdict")
                    observation = {"stage": "native", "report": row}
                else:
                    reason = p.stderr.strip()
                    if not p.returncode or not any(reason.startswith("jvmcontract: --observed-initializer " + owner + ":") for owner in owners):
                        raise ValueError("missing initializer or public verdict: " + reason[:360])
                    observation = {"stage": "initializer", "reason": reason}
                attempts.append({"requested": owners, "exit": p.returncode, **observation})
        results["sides"][side] = {"commit": manifest["commit"], "ordered": manifest["classpath"], "attempts": attempts}
    write(target / "observed-frontier.json", results)


if __name__ == "__main__":
    main()

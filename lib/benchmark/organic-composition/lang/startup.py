"""Retry the strict public caller after requesting the actual timezone initializer on each original."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from register import CASE, sha
from freeze import verify
from plan_run import JDK, OUTPUT, ROOT


def main():
    verify()
    target = ROOT / OUTPUT / "lang"
    opening = json.loads((target / "first-native.json").read_bytes())
    owner = "org.apache.commons.lang3.time.TimeZones"
    method = "UpgradeProbe#parseWeek()Z"
    checker = os.environ.get("JVMCONTRACT", str(ROOT / "lib/target/release/jvmcontract"))
    env = os.environ | {"JAVA_HOME": str(JDK), "PATH": str(JDK / "bin") + os.pathsep + os.environ["PATH"]}
    controlled = ["--observed-runtime", '{"emptyEnvironment":true,"processors":2,"rootWorkingDirectory":true}']
    report = {"firstAttempt": sha(target / "first-native.json"), "sides": {}}
    for side in ("old", "new"):
        original = json.loads((CASE / side / "prepared.json").read_bytes())
        sources = original["classpath"]
        jar = Path(sources[0]["file"])
        if len(sources) != 1 or sha(jar) != sources[0]["sha256"] or opening[side]["artifacts"] != sources:
            raise ValueError("different original runtime")
        refusal = opening[side]["disposition"]
        if refusal["verdict"] != "unverifiable" or owner + ".<clinit>()V" not in refusal["reason"]:
            raise ValueError("wrong first startup frontier")
        runs = []
        with tempfile.TemporaryDirectory(prefix="week-initializer-") as classes:
            subprocess.run([JDK / "bin/javac", "-g", "-parameters", "-encoding", "UTF-8", "-proc:none",
                            "-cp", jar, "-d", classes, CASE / "UpgradeProbe.java"], check=True)
            for profile, extra in (("ordinary", []), ("controlled", controlled)):
                command = [checker, "prove", "--classes", classes, method, "--classpath", jar, "--engine", "native",
                           "--assert", "result == true", "--unwind", "16", "--json", "--observed-initializer", owner, *extra]
                proc = subprocess.run(command, env=env, capture_output=True, text=True, timeout=150)
                if proc.stdout.strip():
                    row, = json.loads(proc.stdout)
                    if row.get("verdict") not in ("verified", "refuted", "unverifiable"):
                        raise ValueError("unexpected native disposition")
                    result = {"stage": "native", "verdict": row["verdict"], "reason": row.get("problem"), "report": row}
                else:
                    reason = proc.stderr.strip()
                    prefix = "jvmcontract: --observed-initializer " + owner + ": "
                    if proc.returncode == 0 or not reason.startswith(prefix) or "\n" in reason or len(reason) > 1600:
                        raise ValueError("missing original initializer disposition")
                    result = {"stage": "startup observation", "verdict": "refused before native execution", "reason": reason}
                runs.append({"process": profile, "runtimeArguments": extra, "exit": proc.returncode, **result})
        report["sides"][side] = {"commit": original["commit"], "jar": sources[0]["sha256"], "entry": method,
                                 "initializer": owner, "runs": runs}
    (target / "observed-frontier.json").write_text(json.dumps(report, indent=2) + "\n")
    print([(side, [r["verdict"] for r in entry["runs"]]) for side, entry in report["sides"].items()])


if __name__ == "__main__":
    main()

"""Run the existing application planner on registered inputs and retain its complete records."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = Path("verification/organic-composition")
JDK = Path.home() / ".sdkman/candidates/java/21.0.13.0+9-tem"


def run(case, experiment, modes, seconds):
    folder = HERE / case
    result = ROOT / OUTPUT / case / experiment
    result.mkdir(parents=True, exist_ok=True)
    checker = os.environ.get("JVMCONTRACT") or ROOT / "lib/target/release/jvmcontract"
    with tempfile.TemporaryDirectory(prefix="organic-plans-") as temp:
        work = Path(temp)
        timings = {}
        for mode in modes:
            cmd = [sys.executable, "examples/tools/build.py", "--change-plan", "application",
                   "--before", folder/"old/prepared.json", "--after", folder/"new/prepared.json",
                   "--jdk", JDK, "--checker", checker, "--workflows", folder/"workflows.json",
                   "--seconds", str(seconds), "--output", work/(mode+".json")]
            if mode != "planned":
                cmd.extend(["--run", "--cache", work/("clean-cache" if mode == "clean" else "cache")])
            if mode == "warm":
                cmd.extend(["--previous", work/"cold.json"])
            start = time.monotonic()
            subprocess.run(cmd, cwd=ROOT, check=True)
            timings[mode] = round(time.monotonic()-start, 3)
        summary = {}
        with zipfile.ZipFile(result/"plans.zip", "w", zipfile.ZIP_DEFLATED) as pack:
            for mode in modes:
                path = work/(mode+".json")
                plan = json.loads(path.read_bytes())
                assert plan["claims"] and (mode == "planned" or plan["executionState"] == "complete")
                summary[mode] = [{"id": n["id"], "claimKey": n["claimKey"], "executionKey": n["executionKey"],
                                  "status": n["status"], "firstOpenDependency": n.get("firstOpenDependency"),
                                  "reason": n.get("reason"), "witness": n.get("witness"),
                                  "execution": n.get("execution"), "children": n.get("children")}
                                 for n in plan["claims"]]
                pack.write(path, path.name)
            for path in sorted((work/"receipts").glob("*.json")):
                pack.write(path, str(path.relative_to(work)))
        (result/"summary.json").write_text(json.dumps({"wallSeconds": timings, "plans": summary}, indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case")
    parser.add_argument("experiment")
    parser.add_argument("modes", nargs="+", choices=["planned", "cold", "warm", "clean"])
    parser.add_argument("--seconds", type=int, default=120)
    args = parser.parse_args()
    run(args.case, args.experiment, args.modes, args.seconds)

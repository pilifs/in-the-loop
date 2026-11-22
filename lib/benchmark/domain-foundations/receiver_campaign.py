"""Repeat the 32 frozen native targets and run their registered callers with live receiver evidence."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from startup import HERE, ROOT

EXTERNAL = HERE.parent / "external-upgrades"


def run(group, area, cache, output):
    pilot = json.loads((ROOT/"verification/domain-foundations/results.json").read_bytes())["receivers"]["cases"]
    keys = [k for k, v in pilot.items() if Path(v["receipt"]).parts[-3] == group]
    if not keys:
        raise ValueError("no cases in pilot group " + group)
    checker = Path(os.environ["JVMCONTRACT"]).resolve()
    select = [arg for key in keys for arg in ("--case", key)]
    common = ["--complete", area/"modules", "--repositories", area/"sources/repos.json", "--maven-cache", cache, *select]
    subprocess.run([sys.executable, "-B", EXTERNAL/"engineering.py", "--build", "current", "--checker", checker,
        "--work", area/"slices", "--output", output/group/"overloads", *common], check=True)
    subprocess.run([sys.executable, "-B", EXTERNAL/"check_scenarios.py", "--native-caller", checker,
        "--preparations", area/"slices", "--output", output/group/"callers", *common], check=True)
    for key in keys:
        native = json.loads((output/group/"overloads/current"/(key+".json")).read_bytes())
        caller = json.loads((output/group/"callers"/(key+".json")).read_bytes())
        if native.get("id") != key or not native.get("native"):
            raise ValueError("missing original overload results for "+key)
        if set(caller.get("nativeCaller", {}).get("sides", {})) != {"old", "new"}:
            raise ValueError("missing native caller attempts for "+key+": "+str(caller.get("reason", caller.get("nativeCaller"))))
        for side in caller["sides"].values():
            for trial in side.get("trials", []):
                if trial["qualifiedMethodEntries"] != len(trial.get("receiverAtEntry", [])):
                    raise ValueError("the live receiver and original entry counts differ for "+key)
        print(key, caller["status"], [v["verdict"] for v in caller["nativeCaller"]["sides"].values()], flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=[f"{i:02}" for i in range(1, 8)], required=True)
    parser.add_argument("--area", type=Path, required=True, help="the pilot's prepared original modules, slices and sources")
    parser.add_argument("--maven-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    a = parser.parse_args()
    run(a.group, a.area, a.maven_cache, a.output)

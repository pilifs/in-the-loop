"""Run the registered scheduling calls from fresh process defaults on the canonical API/core graph."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from register import CASE, PLUGIN, PROCESSOR, sha
from matrix import write
from plan_run import JDK, OUTPUT, ROOT
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import upgrade_replay

DRIVER = """import java.util.TimeZone;
class ScheduleProcess {
    public static void main(String[] args) {
        if (!TimeZone.getDefault().getID().equals(args[0])) throw new AssertionError("wrong process default");
        System.out.println("SCHEDULE " + UpgradeProbe.observe(args));
        if (!TimeZone.getDefault().getID().equals(args[0])) throw new AssertionError("lost original process default");
    }
}"""


def main():
    target = ROOT / OUTPUT / "log4j"
    target.mkdir(parents=True, exist_ok=True)
    records = []
    reg = json.loads((CASE / "registration.json").read_bytes())
    if any(sha(CASE / name) != digest for name, digest in reg["inputs"].items()):
        raise ValueError("scheduling registration changed")
    for side in ("old", "new"):
        bound = json.loads((CASE / side / "prepared.json").read_bytes())
        jars = [Path(item["file"]) for item in bound["classpath"]]
        if [sha(j) for j in jars] != [item["sha256"] for item in bound["classpath"]]:
            raise ValueError("different ordered production deployment")
        with tempfile.TemporaryDirectory(prefix="rollover-process-") as directory:
            w = Path(directory)
            cp = os.pathsep.join(map(str, jars))
            (w / "ScheduleProcess.java").write_text(DRIVER)
            subprocess.run([JDK / "bin/javac", "-proc:none", "-g", "-cp", cp, "-d", w,
                            w / "ScheduleProcess.java", CASE / "UpgradeProbe.java"], check=True)
            for workflow in json.loads((CASE / "workflows.json").read_bytes())["workflows"]:
                scope = json.loads((CASE / workflow["scope"]).read_bytes())
                for i, case in enumerate(scope["cases"]):
                    args = case["args"]
                    expected = case["expected"]
                    if side == "new" and workflow["intent"] != "preserve":
                        expected = next(c["expectedNew"] for c in workflow["intent"]["allowedChanges"] if c["input"] == i)
                    repeats = []
                    for _ in range(2):
                        run = subprocess.run([JDK / "bin/java", "-Xmx256m", "-Duser.timezone=" + args[0],
                            "-Duser.language=en", "-Duser.country=US", "-verbose:class", "-cp", str(w) + os.pathsep + cp,
                            "ScheduleProcess", *args], cwd=w, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8"},
                            capture_output=True, text=True, check=True, timeout=12)
                        origins = upgrade_replay.class_origins(run.stdout)
                        loaded = (PROCESSOR, "org.apache.logging.log4j.core.pattern.FileDatePatternConverter",
                                  "org.apache.logging.log4j.core.pattern.DatePatternConverter")
                        if any(origins.get(name) != {jars[1]} for name in loaded):
                            raise ValueError("missing original processor or converter")
                        observed, = (line.removeprefix("SCHEDULE ") for line in run.stdout.splitlines() if line.startswith("SCHEDULE "))
                        if observed != expected["return"]:
                            raise ValueError(f"unexpected {side} schedule for {args}: {observed}")
                        repeats.append(observed)
                    records.append({"side": side, "commit": bound["commit"], "classpath": bound["classpath"],
                        "claim": workflow["id"], "args": args, "loadedFromCore": loaded, "bundledPluginDigest": bound["resources"][PLUGIN],
                        "processDefault": args[0], "observations": repeats})
    write(target / "processes.json", records)
    print(len(records) * 2, "fresh original process histories matched all registered timestamps")


if __name__ == "__main__":
    main()

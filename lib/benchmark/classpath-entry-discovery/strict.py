"""Repeat the independent strict scheduling attempt with its original adapter and API/core deployment."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from transfer import ROOT, JDK
from targets import change_evidence, upgrade_replay


def run(output):
    case = ROOT / "lib/benchmark/organic-composition/log4j"
    checker = os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")
    rows = []
    with tempfile.TemporaryDirectory(prefix="strict-schedule-") as tmp:
        work = Path(tmp)
        for side in ("old", "new"):
            graph = json.loads((case / side / "prepared.json").read_bytes())["classpath"]
            jars = [Path(r["file"]) for r in graph]
            if [upgrade_replay.sha(j) for j in jars] != [r["sha256"] for r in graph]:
                raise ValueError("original core or API artifact differs")
            adapter = work / side
            adapter.mkdir()
            cp = os.pathsep.join(map(str, jars))
            subprocess.run([JDK/"bin/javac", "-proc:none", "-d",adapter,"-cp",cp,case/"UpgradeProbe.java"],check=True)
            argv = [checker,"prove","--classes",adapter,"UpgradeProbe#schedule()Z","--classpath",cp,
                    "--engine","native","--gaps","strict","--assert","result == true","--unwind","16","--json"]
            proc = subprocess.run(argv, cwd=adapter, env={**os.environ, "JAVA_HOME":str(JDK),"JVMCONTRACT_JAR_RELEASE":"21"},
                                  capture_output=True, text=True, timeout=90)
            result, = json.loads(proc.stdout)
            reason = result.get("reason") or result.get("output") or str(result)
            if result["verdict"] != "unverifiable" or "java.util.TimeZone.getDefault()" not in reason:
                raise ValueError(f"{side}: strict boundary differs: {result}")
            rows.append({"revision":side,"entry":"UpgradeProbe#schedule()Z","classPath":graph,
                         "adapterClassSha256":upgrade_replay.sha(adapter/"UpgradeProbe.class"),"status":"open",
                         "firstOpenDependency":reason,"argv":list(map(str,argv)),"exit":proc.returncode})
    change_evidence.write_json(output,rows)
    print("Original strict native scheduling route stopped at TimeZone.getDefault on both revisions")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("output",type=Path)
    run(p.parse_args().output)

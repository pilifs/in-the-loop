"""Compare S16's original parent source slice with the separately labelled public milestone."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from workspace import scratch


def sha(path):
    with path.open("rb") as src:
        return hashlib.file_digest(src, "sha256").hexdigest()


def run():
    inputs = json.loads((HERE / "inputs.json").read_text())
    cache = Path(os.environ.get("SPRING_BOOT_S_CACHE", Path.home() / ".cache/in-the-loop/spring-boot-pr-links-s01-s50"))
    jdk = Path.home() / ".sdkman/candidates/java" / inputs["jdk"]
    if sha(jdk / "release") != inputs["jdkRelease"]:
        raise ValueError("different JDK 8")
    for path, expected in inputs["sha256"].items():
        if sha(cache / path) != expected:
            raise ValueError("different input " + path)
    cp = {name: os.pathsep.join(str(cache / p) for p in files) for name, files in inputs["profiles"].items()}
    result = {"comparison": "parent source slice over M2 and separate M3 release", "exactFixMeasured": False, "profiles": {}}
    with scratch("boot-2017-") as tmp:
        work = Path(tmp)
        classes = work / "classes"
        classes.mkdir()
        subprocess.run([jdk / "bin/javac","-proc:none","-cp",cp["parent-source-slice"],"-d",classes,
                        HERE / "PersonApplication.java"], check=True)
        subprocess.run([jdk / "bin/javac","-proc:none","-cp",str(classes)+os.pathsep+cp["M3-release"],"-d",classes,
                        HERE / "MilestoneClients.java"], check=True)
        result["callerClasses"] = {str(p.relative_to(classes)):sha(p) for p in sorted(classes.rglob("*.class"))}
        for profile, classpath in cp.items():
            rows = {}
            for history in (("intent","control") if profile == "parent-source-slice" else ("intent","control","challenge")):
                proc = subprocess.run([jdk / "bin/java","-Xmx256m","-Dio.netty.eventLoopThreads=2",
                                       "-Dreactor.ipc.netty.workerCount=2","-cp",str(classes)+os.pathsep+classpath,
                                       "fixture.webflux.PersonApplication",history],cwd=work,text=True,
                                      stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=35)
                if proc.returncode:
                    raise RuntimeError(f"{profile} {history}: " + proc.stdout[-3500:])
                origins = [Path(s[7:]) for s in proc.stdout.splitlines() if s.startswith("ORIGIN ")]
                observed = [s[4:] for s in proc.stdout.splitlines() if s.startswith("OBS ")]
                paths = [cache / p for p in inputs["profiles"][profile]]
                expected = paths[0] if profile == "parent-source-slice" else next(p for p in paths if p.name == "spring-boot-autoconfigure-2.0.0.M3.jar")
                if origins != [expected] or len(observed) != 1:
                    raise ValueError(f"{profile} {history}: missing original entry or result")
                rows[history] = observed[0]
                print(profile, history, observed[0], flush=True)
            result["profiles"][profile] = rows
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    receipt = HERE / "observations.json"
    measured = run()
    if args.record:
        receipt.write_text(json.dumps(measured, indent=2) + "\n")
    elif json.loads(receipt.read_text()) != measured:
        raise ValueError("WebFlux observations changed")

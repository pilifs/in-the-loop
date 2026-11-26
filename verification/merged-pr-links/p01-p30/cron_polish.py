"""Compare P29's separately named follow-up to the landing using the original cron caller."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import public_comparison as comparison

FOLDER = ROOT / "examples/506-spring-cron-registration"
OWNER = "org.springframework.scheduling.config.ScheduledTaskRegistrar"
SOURCE = "spring-context/src/main/java/" + OWNER.replace(".", "/") + ".java"
LATER = "daa8c10031e35f1a447917474f203789e009d3b5"


def measure():
    spec = comparison.read(FOLDER / "comparison.json")
    runtime = comparison.read(FOLDER / "runtime.json")
    physical = comparison.read(FOLDER / "observations.json")["deployments"]["pins"]
    expected = {r["id"]: r["outcome"] for r in physical["observations"] if r["side"] == "fix"}
    cache = Path(os.environ.get("PUBLIC_COMPARISON_CACHE", Path.home() / ".cache/in-the-loop" / runtime["cache"])).resolve()
    tree = cache / "worktrees/P29-later"
    jdk = Path(os.environ.get("PUBLIC_COMPARISON_JDK", Path.home() / ".sdkman/candidates/java" / runtime["jdk"]))
    if comparison.upgrade_replay.sha(jdk / "release") != runtime["jdkReleaseSha256"]:
        raise ValueError("original JDK differs")
    landing = spec["revisions"]["fix"]
    git = ["git", "-C", tree]
    header = subprocess.check_output([*git, "cat-file", "commit", LATER]).split(b"\n\n", 1)[0]
    parents = [line[7:].decode("ascii") for line in header.splitlines() if line.startswith(b"parent ")]
    if parents != [landing]:
        raise ValueError("maintainer revision does not immediately follow the registered landing")
    result = {"jdkReleaseSha256": runtime["jdkReleaseSha256"], "source": SOURCE, "revisions": {}}
    with tempfile.TemporaryDirectory(prefix="cron-polish-") as temporary:
        work = Path(temporary)
        cp = comparison.classpath(cache, runtime, runtime["deployments"]["pins"], "fix", work)
        caller = work / "caller"
        comparison.compile_java(jdk, cp, caller, [comparison.upgrade_replay.LAUNCHER, FOLDER / "caller/PublicCaller.java"])
        result["callerClasses"] = comparison.class_digests(caller)
        if result["callerClasses"] != physical["callerClasses"]:
            raise ValueError("different historical caller")
        for side, revision in (("landing", landing), ("later", LATER)):
            source = work / side / Path(SOURCE).name
            source.parent.mkdir()
            source.write_bytes(subprocess.check_output([*git, "show", f"{revision}:{SOURCE}"]))
            classes = work / side / "classes"
            comparison.compile_java(jdk, cp, classes, [source], ["--release", "17", "-parameters", "-implicit:none"])
            bytecode = subprocess.check_output([jdk / "bin/javap", "-c", "-p", "-s", "-classpath", classes, OWNER])
            histories = {}
            for row in spec["questions"]:
                trial = work / side / row["args"][0]
                trial.mkdir()
                actual = comparison.observe(jdk, os.pathsep.join((str(caller), str(classes), cp)), trial, "PublicCaller",
                                            row["args"], {OWNER: classes}, label=f"P29 {side}")
                if actual != expected[row["id"]]:
                    raise ValueError(f"{side} {row['id']}: {actual} differs from the observed landing")
                histories[row["id"]] = actual
            result["revisions"][side] = {
                "revision": revision, "sourceSha256": comparison.upgrade_replay.sha(source),
                "instructionListingSha256": hashlib.sha256(bytecode).hexdigest(), "histories": histories}
    sides = result["revisions"]
    if sides["landing"]["instructionListingSha256"] != sides["later"]["instructionListingSha256"]:
        raise ValueError("the two original registrar classes have different instructions or signatures")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = measure()
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    elif result != comparison.read(HERE / "cron-polish.json"):
        raise SystemExit("follow-up measurements differ")
    print("Two original registrar classes, identical instruction listings, six matching JVM histories.")

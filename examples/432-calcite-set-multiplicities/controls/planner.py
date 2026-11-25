"""Check rule registration, attempted matches, successful transforms and the JDBC result together."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
sys.path.insert(0, str(FOLDER.parent / "tools"))
from targets import public_comparison as comparison, upgrade_replay


def check_history(side, question, data, expected_return):
    role = question["role"]
    queries = {"Intent": 2, "Control": 1, "Challenge": 4}[role]
    if (data["publicReturn"] != expected_return or data["planners"] != queries
            or len(data["converted"]) != queries or len(data["trimmed"]) != queries or not data["otherRulesAttempted"]):
        raise ValueError(f"{side} {role}: incomplete planner events or different JDBC result")
    if role == "Control":
        if (not data["converted"][0].startswith("LogicalProject(LogicalUnion(")
                or not data["trimmed"][0].startswith("LogicalUnion(")):
            raise ValueError(f"{side}: field trimming did not remove the projection above UNION ALL")
        attempts = {}
    else:
        attempts = {"EXCEPT": queries // 2, "INTERSECT": queries // 2}
    produced = attempts if side == "parent" else {}
    if data["transposeAttempts"] != attempts or data["transposeProductions"] != produced:
        raise ValueError(f"{side} {role}: the rule attempted or produced a different transform")


def measure():
    spec = comparison.read(FOLDER / "comparison.json")
    runtime = comparison.read(FOLDER / "runtime.json")
    physical = comparison.read(FOLDER / "observations.json")
    jdk = Path(os.environ.get("PUBLIC_COMPARISON_JDK", Path.home() / ".sdkman/candidates/java" / runtime["jdk"]))
    cache = Path(os.environ.get("PUBLIC_COMPARISON_CACHE", Path.home() / ".cache/in-the-loop" / runtime["cache"])).resolve()
    caller = FOLDER / "caller/PublicCaller.java"
    wrapper = HERE / "PlannerHistory.java"
    if (upgrade_replay.sha(jdk / "release") != runtime["jdkReleaseSha256"]
            or upgrade_replay.sha(caller) != physical["inputs"]["caller/PublicCaller.java"]
            or upgrade_replay.sha(upgrade_replay.LAUNCHER) != physical["launcherSha256"]
            or upgrade_replay.sha(FOLDER / "runtime.json") != physical["runtimeSha256"]
            or upgrade_replay.sha(FOLDER / "comparison.json") != physical["comparisonSha256"]):
        raise ValueError("the original caller, runtime or registration differs")
    reference = physical["deployments"]["pins"]
    observed = {(r["side"], r["id"]): r["outcome"]["return"] for r in reference["observations"]}
    deployment = runtime["deployments"]["pins"]
    report = {"pins": spec["revisions"], "runtimeSha256": physical["runtimeSha256"],
              "wrapperSha256": upgrade_replay.sha(wrapper), "observations": {}}
    with tempfile.TemporaryDirectory(prefix="calcite-listener-") as temp:
        work = Path(temp)
        cp = {side: comparison.classpath(cache, runtime, deployment, side, work) for side in comparison.SIDES}
        classes = work / "classes"
        classes.mkdir()
        subprocess.run([jdk / "bin/javac", "-J-Xmx192m", "-g", "-proc:none", "-encoding", "UTF-8",
                        "-d", classes, "-cp", cp["fix"], upgrade_replay.LAUNCHER, caller, wrapper], check=True)
        for name, digest in reference["callerClasses"].items():
            if upgrade_replay.sha(classes / name) != digest:
                raise ValueError(f"{name} differs from the registered public caller")
        report["callerClasses"] = reference["callerClasses"]
        for side in comparison.SIDES:
            providers = {name: cache / deployment["classpath"][side][index] for name, index in deployment["providers"].items()}
            providers["org.apache.calcite.plan.RelOptListener"] = providers["org.apache.calcite.rel.rules.ProjectSetOpTransposeRule"]
            reports = report["observations"][side] = {}
            for question in spec["questions"]:
                qid = question["id"]
                trials = []
                for _ in range(2):
                    with tempfile.TemporaryDirectory(dir=work) as trial:
                        raw = comparison.observe(jdk, str(classes) + os.pathsep + cp[side], Path(trial),
                                                 "PlannerHistory", question["args"], providers, label=f"{side} {qid}")
                    data = json.loads(raw["return"])
                    check_history(side, question, data, observed[side, qid])
                    trials.append(data)
                if trials[0] != trials[1]:
                    raise ValueError(f"{side} {qid}: planner events differed between fresh JVMs")
                reports[qid] = {"freshJvms": len(trials), **trials[0]}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true", help="save the checked planner histories")
    args = parser.parse_args()
    result = measure()
    output = HERE / "planner.json"
    if args.record:
        output.write_text(json.dumps(result, indent=2) + "\n")
    elif comparison.read(output) != result:
        sys.exit("fresh planner histories differ from the recorded evidence")
    for side, rows in result["observations"].items():
        for key, row in rows.items():
            print(side, key, row["publicReturn"], "attempts", row["transposeAttempts"],
                  "productions", row["transposeProductions"])

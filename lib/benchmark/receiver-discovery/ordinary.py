"""Run the unmodified public target at its original registered scope with JVM-confirmed native witness search."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from callers import JDK, RESULTS, ROOT, read, sha
from investigate import compiler, inventory, write
from process_states import parser_cp, prepare
from property_witness import original_call


def run_one(checker, cp, target, guard, predicate, bounds, tmp):
    env = dict(
        os.environ,
        JAVA_HOME=str(JDK),
        JVMCONTRACT_JAR_RELEASE="21",
        PATH=str(JDK / "bin") + os.pathsep + os.environ["PATH"],
    )
    args = [
        checker,
        "prove",
        target,
        "--classes",
        cp[0],
        "--classpath",
        os.pathsep.join(map(str, cp[1:])),
        "--engine",
        "native",
        "--gaps",
        "strict",
        "--assume",
        guard,
        "--assert",
        predicate,
        "--unwind",
        str(bounds["unwind"]),
        "--max-array-length",
        str(bounds["maxArrayLength"]),
        "--timeout",
        "60",
        "--search-startup-witness",
        "--work",
        tmp,
        "--json",
    ]
    run = subprocess.run(args, env=env, capture_output=True, timeout=135)
    if not run.stdout:
        raise ValueError((run.returncode, run.stderr[-600:]))
    (row,) = json.loads(run.stdout)
    if (
        row["target"] != target
        or row["assume"] != guard
        or row["assert"] != predicate
        or row["verdict"] not in ("verified", "violation", "unverifiable")
    ):
        raise ValueError("ordinary claim drift")
    if row["verdict"] == "verified" and (row["stated"].get("vacuity") or {}).get("status") != "non-vacuous":
        raise ValueError("missing nonvacuity")
    return row


def measure(family):
    frozen = read(RESULTS / "scope.json")
    checker = Path(os.environ["JVMCONTRACT"]).resolve()
    result = {
        "job": os.environ["VERIFY_JOB_ID"],
        "source": os.environ["VERIFY_SOURCE_COMMIT"],
        "checkerSha256": sha(checker),
        "sides": {},
    }
    for side in (("old", "new") if family == "xz" else ("parent", "fix")):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            tools = compiler(tmp)
            if family == "javaparser":
                cp = parser_cp(side, tmp / "prepared")
                claims = {}
                for name in ("postorder", "terminal", "nonempty", "preorder"):
                    pin = frozen["tasks"]["360"][name + "-" + side]
                    if pin["environment"] != "ordinary":
                        raise ValueError("different startup scope")
                    target = pin["entry"].split("(")[0]
                    claims[name] = (target, pin["assume"], pin["assert"], pin["bounds"])
            else:
                cp, _, _ = prepare("xz", side, tmp, frozen)
                pin = frozen["registeredCallers"]["commons-compress-767"]
                prev = read(ROOT / pin["reference"])
                if sha(cp[0] / "UpgradeCallerClaim.class") != prev["nativeCaller"]["adapterClassSha256"]:
                    raise ValueError("different original XZ adapter")
                claims = {
                    "frame": (
                        prev["nativeCaller"]["target"],
                        pin["assume"],
                        "result",
                        {k: pin[k] for k in ("maxArrayLength", "unwind")},
                    )
                }
            measured = {}
            for label, (target, guard, predicate, bounds) in claims.items():
                bound = inventory(checker, cp, target)
                row = run_one(checker, cp, target, guard, predicate, bounds, tmp / ("native-" + label))
                data = {"entryClassSha256": bound["binding"]["sha256"], "native": row}
                if row["verdict"] == "violation":
                    (arg,) = row["counterexample"]["inputs"]
                    replay = original_call(tools, cp, bound, arg["value"])
                    if arg["type"] != "int" or replay[-1] not in ("returned false", "returned 0"):
                        raise ValueError((label, side, replay))
                    data["ordinaryDefaultJvm"] = replay
                measured[label] = data
                print(side, label, row["verdict"], flush=True)
            result["sides"][side] = measured
    out = RESULTS / "transfer" / (family + "-ordinary-native")
    out.mkdir(parents=True, exist_ok=True)
    write(out / "measurement.json", result)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("family", choices=["javaparser", "xz"])
    measure(p.parse_args().family)

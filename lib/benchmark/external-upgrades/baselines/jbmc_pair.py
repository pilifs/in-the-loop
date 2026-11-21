"""Run the JBMC engine on the same bound public calibration that ran under V0 native."""

import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT / "examples/tools")]
from pin import digest
from pinned_task import check_files, tools
from targets import qualification, route, runtime, sidecar
from targets.interfaces import Unsupported


class MatchedPlan(Exception):
    """Stop after matching the generated invocation, before launching either solver."""


def engine_options(argv):
    args = list(argv[1:])
    engine = args.index("--engine") + 1
    args[engine] = "<engine>"
    return args


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", choices=("348", "351"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan-only", action="store_true", help="match the inputs and stop before solver launch")
    args = parser.parse_args()
    number = args.example
    task = {"348": "generated-keys", "351": "roundtrip"}[number]
    folder = next((ROOT / "examples").glob(number + "-*/target.json")).parent
    official = next((ROOT / "verification/results").glob(f"20261120-2347*-{number}-run-the-frozen-v0-*"))
    earlier = next((official / "outputs" / folder.relative_to(ROOT) / "receipts" / task).glob("2*/records/verifier.json"))
    native = json.loads(earlier.read_text())["record"]
    frozen = json.loads((HERE / "v0.json").read_text())
    checker = Path.home() / ".cache/in-the-loop/external-upgrades" / frozen["sha256"]["jvmcontract"] / "jvmcontract"
    jdk = (Path.home() / ".sdkman/candidates/java/21.0.13.0+9-tem").resolve()
    solver = (Path.home() / "tools/bitwuzla/current/lib/x86_64-linux-gnu").resolve()
    cprover = Path(shutil.which("jbmc") or "missing-jbmc")
    if digest(cprover) != frozen["sha256"]["jbmc"]:
        raise ValueError("unmatched JBMC executable")
    source_count = check_files(frozen)
    tools(frozen, checker, jdk, solver)
    os.environ.update(JVMCONTRACT=str(checker), JAVA_HOME=str(jdk), TZ="UTC", LC_ALL="C.UTF-8",
                      PATH=str(jdk / "bin") + os.pathsep + os.environ["PATH"])
    os.environ.pop("JVMCONTRACT_LIB_TREE", None)
    example = json.loads((folder / "example.json").read_text())
    plan = route.resolve(folder, example, sidecar.load(folder, example), task)
    if isinstance(plan, Unsupported):
        raise ValueError(plan.describe())
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    info = {"schema": "external-upgrade-engine-baseline/v1", "example": number, "task": task,
            "sourceClaimKey": plan.claim["key"], "nativeRecord": str(earlier.relative_to(ROOT)),
            "nativeRecordSha256": digest(earlier), "jvmcontractSha256": digest(checker),
            "jbmcSha256": digest(cprover), "protectedSources": source_count, "matchedInvocation": False}
    start = time.monotonic()

    def before_launch(argv, identities):
        if engine_options(argv) != engine_options(native["argv"]):
            raise ValueError("checker arguments differ beyond engine selection")
        fields = ("jvmcontract", "jdkRelease", "gaps", "bounds", "timeout", "checkedEntry",
                  "entryBindings", "classpath", "commits")
        for key in fields:
            if identities[key] != native["identities"][key]:
                raise ValueError(f"native and JBMC bindings differ: {key}")
        info["matchedInvocation"] = True
        info["matchedFields"] = list(fields)
        info["argv"] = list(argv)
        if args.plan_only:
            raise MatchedPlan()

    try:
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            prepared = {side: runtime.prepare(plan, side, work / "prepare" / side) for side in plan.revisions}
            for target in prepared.values():
                if isinstance(target, Unsupported) or target.stage != "artifacts-ready":
                    raise ValueError("incomplete original preparation")
            controls = runtime.run_controls(plan, prepared, work / "controls")
            if isinstance(controls, Unsupported):
                raise ValueError(controls.describe())
            correspondence, problem = qualification.correspondence(plan, prepared, controls)
            if problem:
                raise ValueError(str(problem))
            info["correspondence"] = correspondence
            result = runtime.run_verifier(replace(plan, engine="jbmc"), prepared, work / "verifier",
                                          before_launch=before_launch, timeout=native["identities"]["timeout"])
            if isinstance(result, Unsupported):
                raise ValueError(result.describe())
            info.update(workflowStatus=result.status, toolExit=result.exitCode, observations=result.observations,
                        problem=result.reason, checkerSeconds=result.seconds)
            for name, path in (("checker.stdout", result.stdout), ("checker.stderr", result.stderr)):
                if path and result.directory:
                    shutil.copyfile(Path(result.directory) / path, out / name)
            # Keep the actual checker diagnostics about missing bodies and unwinding with the engine comparison.
            logs = sorted((work / "verifier/work").glob("jbmc*.log"))
            info["jbmcLogs"] = []
            for log in logs:
                selected = [line[:1000] for line in log.read_text(errors="replace").splitlines()
                            if any(w in line.lower() for w in ("unwind", "warning", "verification", "failure"))]
                info["jbmcLogs"].append({"name": log.name, "sha256": digest(log),
                                         "diagnostics": selected[:30], "matchingLines": len(selected)})
            info["qualification"] = ("Assess unwinding and abstraction from these logs and replay any candidate on "
                                     "the unchanged JVM. A job exit alone establishes no application claim.")
    except MatchedPlan:
        info["workflowStatus"] = "matched-plan-only"
    except (OSError, ValueError) as exc:
        info["firstBlocker"] = str(exc)
    info["elapsedSeconds"] = round(time.monotonic() - start, 3)
    info["sourcesAfter"] = check_files(frozen)
    tools(frozen, checker, jdk, solver)
    (out / "measurement.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n")
    print(f"{number}: matched input {info['matchedInvocation']}, tool exit {info.get('toolExit')}, "
          f"measurement {info['elapsedSeconds']}s")
    return int(not info["matchedInvocation"] or "firstBlocker" in info)


if __name__ == "__main__":
    sys.exit(main())

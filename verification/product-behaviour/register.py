"""Bind disclosed public observations to the upstream setup and materialize caller-workflows/v1."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SETUP = Path.home() / ".cache/in-the-loop/organic-pr-20"
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_plan, upgrade_replay


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def jdk(case):
    return Path.home() / ".sdkman/candidates/java" / case.get("jdk", "21.0.13.0+9-tem")


def bind(folder):
    case = read(folder / "case.json")
    bound = {}
    for side, label in (("old", "parent"), ("new", "fix")):
        tree = SETUP / "worktrees" / f"{folder.name}-{case['project']}-{label}"

        def git(*args):
            return subprocess.check_output(["git", "-C", tree, *args])

        commit = git("rev-parse", "HEAD").decode().strip()
        if commit != case["commits"][side]:
            raise ValueError(f"{side} source pin differs")
        git("diff", "--quiet", "HEAD", "--", *case["sourceRoots"])
        sources = git("ls-tree", "-r", "-z", commit, "--", *case["sourceRoots"])
        if not sources:
            raise ValueError("empty production source selection")
        files = [SETUP / f.format(side=label) for f in case["artifacts"]]
        for cp in case.get("supportClasspaths", []):
            listed = (SETUP / cp.format(side=label)).read_text().strip()
            files.extend(Path(f) for f in listed.split(os.pathsep) if f)
        files = list(dict.fromkeys(f.resolve(strict=True) for f in files))
        bound[side] = {
            "commit": commit, "tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
            "scope": case["deployment"], "sourceRoots": case["sourceRoots"],
            "sourceFiles": sources.count(b"\0"), "sourceSha256": hashlib.sha256(sources).hexdigest(),
            "jdkReleaseSha256": upgrade_replay.sha(jdk(case) / "release"),
            "classpath": [{"file": str(f.relative_to(SETUP)), "sha256": upgrade_replay.sha(f)} for f in files],
        }
    write(folder / "bindings.json", bound)


def manifests(folder):
    bound = read(folder / "bindings.json")
    for doc in bound.values():
        for row in doc["classpath"]:
            path = SETUP / row["file"]
            if upgrade_replay.sha(path) != row["sha256"]:
                raise ValueError(f"setup artifact changed: {row['file']}")
            row["file"] = str(path)
    return bound


def materialize(folder, work):
    case = read(folder / "case.json")
    rows = []
    for question in case["questions"]:
        name = question["id"]
        inputs = question["inputs"]
        changes = [{"input": i, "expectedNew": {"return": item["after"]}}
                   for i, item in enumerate(inputs) if item.get("after", item["before"]) != item["before"]]
        scope = {"entry": question.get("entry", case["entry"]), "probeClass": "UpgradeProbe",
                 "observer": question["observer"], "basis": question["basis"],
                 "cases": [{"args": item["args"], "expected": {"return": item["before"]}} for item in inputs]}
        if "invocationVia" in question:
            scope["invocationVia"] = question["invocationVia"]
        if "fixtures" in case:
            scope["fixtures"] = case["fixtures"]
        write(work / (name + ".json"), scope)
        rows.append({"id": name, "scope": name + ".json", "probe": str(folder / "UpgradeProbe.java"),
                     "cohort": "registered", "deterministicUnderAssumptions": True,
                     "assumptions": case["assumptions"], "intent": {"allowedChanges": changes} if changes else "preserve"})
    workflows = work / "workflows.json"
    write(workflows, {"schema": "caller-workflows/v1", "change": case["change"], "workflows": rows})
    change_plan.frozen_workflows(workflows)
    return workflows


def physical(folder):
    """Run the original observers without the debugger as an independent check of the registration."""
    case = read(folder / "case.json")
    java = jdk(case) / "bin"
    bindings = manifests(folder)
    observations = []
    with tempfile.TemporaryDirectory(prefix="product-physical-") as temp:
        work = Path(temp)
        materialize(folder, work)
        for side, doc in bindings.items():
            classes = work / side
            classes.mkdir()
            cp = os.pathsep.join(row["file"] for row in doc["classpath"])
            subprocess.run([java / "javac", "-g", "-proc:none", "-encoding", "UTF-8", "-cp", cp, "-d", classes,
                            upgrade_replay.LAUNCHER, folder / "UpgradeProbe.java"], check=True)
            for question in case["questions"]:
                for item in question["inputs"]:
                    args = [base64.b64encode(s.encode("utf-16-be")).decode() for s in item["args"]]
                    trial = work / ("trial-" + str(len(observations)))
                    trial.mkdir()
                    obs = trial / "observation"
                    env = {"PATH": str(java) + ":/usr/bin:/bin", "HOME": str(trial),
                           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC", "TMPDIR": str(trial)}
                    subprocess.run([java / "java", "-Xmx96m", "-Djava.io.tmpdir=" + str(trial),
                                    "-Dupgrade.observation.file=" + str(obs), "-cp", str(classes) + os.pathsep + cp,
                                    "UpgradeObservation", "UpgradeProbe", *args], check=True, cwd=trial, env=env, timeout=40)
                    observed = upgrade_replay.typed_outcome(obs.read_text().splitlines())
                    expected = item.get("after", item["before"]) if side == "new" else item["before"]
                    if observed != {"return": expected}:
                        raise ValueError(f"{folder.name} {side} {item['args']}: expected {expected!r}, observed {observed}")
                    observations.append({"side": side, "question": question["id"], "args": item["args"], **observed})
    write(folder / "physical.json", {"jdkReleaseSha256": upgrade_replay.sha(jdk(case) / "release"),
          "bindingsSha256": upgrade_replay.sha(folder / "bindings.json"), "caseSha256": upgrade_replay.sha(folder / "case.json"),
          "probeSha256": upgrade_replay.sha(folder / "UpgradeProbe.java"), "freshProcesses": len(observations),
          "observations": observations})
    print(f"{folder.name}: {len(observations)} physical histories matched")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["bind", "physical"])
    parser.add_argument("case")
    args = parser.parse_args()
    folder = HERE / "cases" / args.case
    (bind if args.action == "bind" else physical)(folder)

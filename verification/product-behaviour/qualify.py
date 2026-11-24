"""Run the frozen application plan and compare its qualified public observations with clean runs."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

from register import HERE, ROOT, jdk, manifests, materialize, read, upgrade_replay, write

sys.path.insert(0, str(ROOT / "lib/benchmark/organic-composition"))
import freeze


def summarize(plan, work):
    rows = []
    for node in plan["claims"]:
        row = {k: node.get(k) for k in ("id", "status", "firstOpenDependency", "reason", "claimKey", "executionKey",
                                       "children", "execution", "receipt")}
        row["freshQualifiedEntries"] = 0
        row["reusedQualifiedEntries"] = 0
        if receipt := row["receipt"]:
            path = work / receipt["path"]
            if upgrade_replay.sha(path) != receipt["sha256"]:
                raise ValueError("public evidence digest differs")
            evidence = read(path)
            for side, binding in evidence.get("sides", {}).items():
                action = (row["execution"] or {}).get(side, {}).get("action")
                count = sum(t["qualifiedMethodEntries"] for t in binding.get("trials", []))
                row["reusedQualifiedEntries" if action == "exact reuse" else "freshQualifiedEntries"] += count
        if row["status"] == "open" and row["firstOpenDependency"] is None and not row["reason"]:
            raise ValueError("open public result has no recorded dependency")
        rows.append(row)
    return rows


def outcomes(rows):
    # Keep complete typed observations, their input and the dependency-sensitive identity.
    return [{k: row[k] for k in ("id", "claimKey", "executionKey", "status", "children")} for row in rows]


def run(case_id, label):
    frozen_source = freeze.verify()
    folder = HERE / "cases" / case_id
    case = read(folder / "case.json")
    physical = read(folder / "physical.json")
    for key, name in (("bindingsSha256", "bindings.json"), ("caseSha256", "case.json"), ("probeSha256", "UpgradeProbe.java")):
        if physical[key] != upgrade_replay.sha(folder / name):
            raise ValueError(f"physical registration differs at {name}")
    graphs = manifests(folder)
    result = HERE / "results" / case_id / label
    result.mkdir(parents=True, exist_ok=True)
    checker = Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")).resolve()
    with tempfile.TemporaryDirectory(prefix="product-plan-") as temp:
        work = Path(temp)
        workflows = materialize(folder, work)
        write(work / "old.json", graphs["old"])
        fixed = graphs["new"]
        # Exercise the same paths before and after the relevant edit. Preserve the original classpath order.
        for i, artifact in enumerate(fixed["classpath"][:len(case["artifacts"])]):
            source = Path(artifact["file"])
            target = work / f"provider-{i}" / source.name
            target.parent.mkdir()
            shutil.copyfile(source, target)
            artifact["file"] = str(target)
        write(work / "new.json", fixed)
        runs = {}
        with zipfile.ZipFile(result / "plans.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(work.glob("*.json")):
                archive.write(path, "registration/" + path.name)
            receipts = set()
            for mode, previous, cache in (("cold", None, "repeat"), ("warm", "cold", "repeat"),
                                           ("clean", None, "clean"), ("replacement", "warm", "repeat"),
                                           ("replacement-clean", None, "replacement-clean")):
                if mode == "replacement":
                    for actual, parent in zip(fixed["classpath"][:len(case["artifacts"])], graphs["old"]["classpath"], strict=False):
                        shutil.copyfile(parent["file"], actual["file"])
                        actual["sha256"] = parent["sha256"]
                    fixed.update(commit=graphs["old"]["commit"], sourceSha256=graphs["old"]["sourceSha256"],
                                 scope="Parent production artifacts at the same paths with the originally registered fixed support graph")
                    write(work / "new.json", fixed)
                    archive.write(work / "new.json", "registration/replacement.json")
                path = work / (mode + ".json")
                cmd = [sys.executable, ROOT / "examples/tools/build.py", "--change-plan", "application",
                       "--before", work / "old.json", "--after", work / "new.json", "--workflows", workflows,
                       "--jdk", jdk(case), "--checker", checker, "--seconds", str(case.get("replaySeconds", 180)),
                       "--run", "--cache", work / ("cache-" + cache), "--output", path]
                if previous:
                    cmd.extend(["--previous", work / (previous + ".json")])
                if "fixtures" in case:
                    cmd.extend(["--fixtures", folder])
                start = time.monotonic()
                subprocess.run(cmd, cwd=ROOT, check=True)
                plan = read(path)
                if plan["executionState"] != "complete" or len(plan["claims"]) != len(case["questions"]):
                    raise ValueError(f"incomplete {mode} plan")
                rows = summarize(plan, work)
                binary = plan["deploymentQuestions"]["originalBinary"]
                runs[mode] = {"wallSeconds": round(time.monotonic() - start, 3), "claims": rows,
                              "originalBinaryClaims": summarize(binary, work) if isinstance(binary, dict) else []}
                archive.write(path, mode + ".json")
                for file in sorted((work / "receipts").glob("*.json")):
                    if file.name not in receipts:
                        archive.write(file, "receipts/" + file.name)
                        receipts.add(file.name)
                print(case_id, mode, [(r["id"], r["status"], r["freshQualifiedEntries"]) for r in rows], flush=True)
        for key in ("claims", "originalBinaryClaims"):
            for left, right in (("cold", "warm"), ("warm", "clean"), ("replacement", "replacement-clean")):
                if outcomes(runs[left][key]) != outcomes(runs[right][key]):
                    raise ValueError(f"{left} differs from {right} for {key}")
        # An open initial result is a finding. A changed value or a reused replaced artifact requires investigation.
        questions = {q["id"]: q for q in case["questions"]}
        for row in runs["cold"]["claims"]:
            if row["status"] == "refuted":
                raise ValueError(f"initial result refutes the registered {row['id']}")
        for row in runs["replacement"]["claims"]:
            question = questions[row["id"]]
            changed = any(i.get("after", i["before"]) != i["before"] for i in question["inputs"])
            if row["status"] != "open" and row["status"] != ("refuted" if changed else "established"):
                raise ValueError(f"unexpected same-path result: {row['id']}")
            actions = row["execution"] or {}
            if actions.get("new", {}).get("action") == "exact reuse" and any(
                    a["sha256"] != b["sha256"] for a, b in zip(read(folder / "bindings.json")["old"]["classpath"],
                                                               read(folder / "bindings.json")["new"]["classpath"])):
                raise ValueError("changed provider reused its previous evidence")
        write(result / "summary.json", {"case": case_id, "change": case["change"], "label": label,
              "frozenSource": frozen_source, "comparatorSha256": upgrade_replay.sha(checker),
              "bindingsSha256": physical["bindingsSha256"], "archiveSha256": upgrade_replay.sha(result / "plans.zip"),
              "runs": runs})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case")
    parser.add_argument("--label", default="first")
    args = parser.parse_args()
    run(args.case, args.label)

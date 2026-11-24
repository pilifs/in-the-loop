"""Change the selected Gson bytes at one disposable path and compare original public evidence."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from register import CASE, sha
from freeze import verify
from matrix import semantic, write
from plan_run import JDK, OUTPUT, ROOT


def run():
    verify()
    target = ROOT / OUTPUT / "gson/replacement"
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gson-cache-controls-") as directory:
        work = Path(directory)
        seen, summary, comparisons = set(), {}, {}
        with zipfile.ZipFile(target / "plans.zip", "w", zipfile.ZIP_DEFLATED) as packed:
            for mode, source, cache in (("baseline", "new", "warm"), ("unrelated-warm", "new", "warm"),
                                        ("unrelated-clean", "new", "clean1"), ("changed-warm", "old", "warm"), ("changed-clean", "old", "clean2")):
                manifest = json.loads((CASE / source / "prepared.json").read_bytes())
                artifact = manifest["classpath"][0]
                controlled = work / "gson.jar"
                shutil.copyfile(artifact["file"], controlled)
                if sha(controlled) != artifact["sha256"]:
                    raise ValueError("unexpected disposable Gson bytes")
                artifact["file"] = str(controlled)
                write(work / "after.json", manifest)
                if mode == "unrelated-warm":
                    (work / "outside-classpath.txt").write_text("unselected input\n")
                cmd = [sys.executable, ROOT / "examples/tools/build.py", "--change-plan", "application",
                       "--before", CASE / "old/prepared.json", "--after", work / "after.json", "--workflows", CASE / "workflows.json",
                       "--jdk", JDK, "--checker", os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract"),
                       "--seconds", "180", "--run", "--cache", work / cache, "--output", work / (mode + ".json")]
                if mode.endswith("-warm"):
                    cmd.extend(["--previous", work / "baseline.json"])
                subprocess.run(cmd, cwd=ROOT, check=True)
                plan = json.loads((work / (mode + ".json")).read_bytes())
                if plan["executionState"] != "complete" or len(plan["claims"]) != 4:
                    raise ValueError("incomplete original workflow")
                states = {}
                dependencies = []
                for node in plan["claims"]:
                    differs = node["id"].endswith("-paths") and source == "old"
                    wanted = "refuted" if differs else "established"
                    if node["status"] != wanted or any(c["status"] != wanted for c in node["children"]):
                        raise ValueError("incorrect public comparison at " + mode)
                    actions = {s: a["action"] for s, a in node["execution"].items()}
                    if mode == "changed-warm" and actions != {"old": "exact reuse", "new": "executed"}:
                        raise ValueError("stale deployment or needless parent replay")
                    if mode == "unrelated-warm" and (actions["old"] != "exact reuse" or
                            actions["new"] != ("executed" if node["id"].endswith("-paths") else "exact reuse")):
                        raise ValueError("unexpected action after unrelated edit")
                    ref = node["receipt"]
                    if sha(work / ref["path"]) != ref["sha256"]:
                        raise ValueError("unbound original trial")
                    receipt = json.loads((work / ref["path"]).read_bytes())
                    dependencies.append({s: {k: (b.get(k) if k != "trials" else [
                        {key: t.get(key) for key in ("input", "qualifiedMethodEntries", "entryInvocations", "observations", "loadedUpgradeOnEachReplay")} for t in b[k]])
                        for k in ("classpath", "callerClassSha256", "trials")} for s, b in receipt["sides"].items()})
                    states[node["id"]] = {"status": node["status"], "actions": actions, "receipt": ref}
                summary[mode] = {"afterCommit": manifest["commit"], "afterSha256": artifact["sha256"], "claims": states}
                comparisons[mode] = [semantic(plan), dependencies]
                packed.write(work / (mode + ".json"), mode + ".json")
                for path in sorted((work / "receipts").glob("*.json")):
                    if path.name not in seen:
                        packed.write(path, "receipts/" + path.name)
                        seen.add(path.name)
        if comparisons["baseline"] != comparisons["unrelated-warm"] or comparisons["baseline"] != comparisons["unrelated-clean"] or comparisons["changed-warm"] != comparisons["changed-clean"]:
            raise ValueError("different scopes, observers, original entries or evidence after cache resume")
        write(target / "report.json", summary)
        print("Four changed-path predictions refuted after replacement. Both preserved map workflows and all independent clean checks held.")


if __name__ == "__main__":
    run()

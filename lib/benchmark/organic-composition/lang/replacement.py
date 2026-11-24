"""Replace the fixed JAR at a stable path with its real parent; compare resumed and clean public evidence."""
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
from plan_run import JDK, ROOT, OUTPUT


def run():
    verify()
    output = ROOT / OUTPUT / "lang/replacement"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="same-path-weekday-") as directory:
        work = Path(directory)
        plans, record = {}, {}
        for mode, source, cache in (("baseline", "new", "cache"), ("changed-warm", "old", "cache"),
                                    ("changed-clean", "old", "independent")):
            manifest = json.loads((CASE / source / "prepared.json").read_bytes())
            item, = manifest["classpath"]
            controlled = work / "commons-lang.jar"
            shutil.copyfile(item["file"], controlled)
            if sha(controlled) != item["sha256"]:
                raise ValueError("unbound disposable deployment")
            item["file"] = str(controlled)
            write(work / "after.json", manifest)
            cmd = [sys.executable, ROOT / "examples/tools/build.py", "--change-plan", "application",
                   "--before", CASE / "old/prepared.json", "--after", work / "after.json", "--workflows", CASE / "workflows.json",
                   "--jdk", JDK, "--checker", os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract"),
                   "--seconds", "180", "--run", "--cache", work / cache, "--output", work / (mode + ".json")]
            if mode == "changed-warm":
                cmd += ["--previous", work / "baseline.json"]
            subprocess.run(cmd, cwd=ROOT, check=True)
            plan = json.loads((work / (mode + ".json")).read_bytes())
            plans[mode] = semantic(plan)
            claims = {row["id"]: {k: row[k] for k in ("status", "execution", "receipt", "children")} for row in plan["claims"]}
            if claims["preserved"]["status"] != "established" or claims["mixed"]["status"] != ("established" if source == "new" else "refuted"):
                raise ValueError("wrong public outcome after replacing the JAR")
            record[mode] = {"afterCommit": manifest["commit"], "afterSha256": item["sha256"], "claims": claims}
        if plans["changed-warm"] != plans["changed-clean"]:
            raise ValueError("resumed original parent differs from the clean comparison")
        warm = record["changed-warm"]["claims"]
        if any(n["execution"]["new"]["action"] != "executed" for n in warm.values()):
            raise ValueError("replaced deployment reused a fixed result")
        if any(c["old"] != c["new"] or c["status"] != "refuted" for c in warm["mixed"]["children"]):
            raise ValueError("parent-to-parent comparison did not refute every registered change")
        with zipfile.ZipFile(output / "plans.zip", "w", zipfile.ZIP_DEFLATED) as pack:
            for mode in plans:
                pack.write(work / (mode + ".json"), mode + ".json")
            for path in sorted((work / "receipts").glob("*.json")):
                pack.write(path, "receipts/" + path.name)
        write(output / "report.json", record)
        print("All four registered changes refuted after replacement; the preservation controls and clean comparison agree.")


if __name__ == "__main__":
    run()

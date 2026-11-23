"""Repeat the registered public claims, binding fresh receipts to the frozen campaign inputs."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "verification/receiver-discovery"
EXTERNAL = ROOT / "lib/benchmark/external-upgrades"
ASSETS = Path.home() / ".cache/in-the-loop/receiver-construction"
JDK = Path.home() / ".sdkman/candidates/java/21.0.13.0+9-tem"


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def numbered(number, out, frozen):
    (folder,) = (ROOT / "examples").glob(number + "-*")
    tasks = frozen["tasks"][number]
    manifest = {t["id"]: t for t in read(folder / "target.json")["tasks"]}
    for name, pin in tasks.items():
        if sha(folder / manifest[name]["claim"]) != pin["claimSha256"]:
            raise ValueError("registered claim changed: " + name)

    def receipts(name):
        return set((folder / "receipts" / name).glob("20*/result.json"))

    before = {name: receipts(name) for name in tasks}
    cmd = [
        sys.executable,
        "-B",
        "examples/tools/build.py",
        number,
        "--tasks",
        ",".join(tasks),
        "--checker-seconds",
        "60",
    ]
    with (out / "workflow.log").open("w") as log:
        run = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    rows = {}
    with tarfile.open(out / "receipts.tar.gz", "w:gz") as archive:
        for name, pin in tasks.items():
            (receipt,) = receipts(name) - before[name]
            doc = read(receipt)
            verdict = doc["conclusion"]["status"]
            if verdict not in ("established", "refuted", "unresolved") or doc["conclusion"].get("vacuous"):
                raise ValueError((number, name, verdict))
            obligations = doc["conclusion"]["obligations"]
            if not any(
                o.get("evidence", {}).get("assert") == pin["assert"]
                and o["evidence"].get("assume") == pin["assume"]
                for o in obligations
            ):
                raise ValueError("no matching executed claim: " + name)
            archive.add(receipt, arcname=name + "/result.json")
            rows[name] = {
                "status": verdict,
                "environment": pin["environment"],
                "sha256": sha(receipt),
                "firstOutstanding": doc["evidence"].get("problem"),
            }
    return {"exit": run.returncode, "tasks": rows}


def upgrade(key, out, frozen):
    area = Path.home() / ".cache/in-the-loop/tmp/domain-foundations-receivers"
    cache = ASSETS / "receivers/maven-repository"
    pin = frozen["registeredCallers"][key]
    reference = ROOT / pin["reference"]
    if sha(reference) != pin["sha256"]:
        raise ValueError("source receiver receipt changed: " + key)
    with tempfile.TemporaryDirectory() as tmp:
        observations = Path(tmp)
        subprocess.run(
            [
                sys.executable,
                "-B",
                EXTERNAL / "check_scenarios.py",
                "--case",
                key,
                "--preparations",
                area / "slices",
                "--complete",
                area / "modules",
                "--repositories",
                area / "sources/repos.json",
                "--maven-cache",
                cache,
                "--native-caller",
                os.environ["JVMCONTRACT"],
                "--output",
                observations,
            ],
            cwd=ROOT,
            check=True,
        )
        doc = read(observations / (key + ".json"))
        native = doc["nativeCaller"]
        if doc["cases"] != pin["cases"] or any(
            native[k] != pin[k] for k in ("unwind", "maxArrayLength", "assume")
        ):
            raise ValueError("registered domain changed")
        rows = {}
        for side in ("old", "new"):
            row = native["sides"][side]
            for k in ("commit", "callerClassSha256", "orderedClasspathSha256"):
                if row[k] != pin["sides"][side][k]:
                    raise ValueError((key, side, k))
            trials = doc["sides"][side]["trials"]
            if len(trials) != len(pin["cases"]) or any(not t["qualifiedMethodEntries"] for t in trials):
                raise ValueError("original JVM entry missing")
            if row["verdict"] not in ("verified", "violation", "unverifiable") or not row.get("rawSha256"):
                raise ValueError("missing native execution")
            rows[side] = {k: row[k] for k in ("verdict", "firstOutstanding", "counterexample", "rawSha256")}
            rows[side]["jvmInputsReached"] = len(trials)
        with tarfile.open(out / "receipts.tar.gz", "w:gz") as archive:
            for path in sorted(observations.rglob("*")):
                if path.is_file():
                    archive.add(path, arcname=path.relative_to(observations))
    return {"sides": rows}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("stage")
    p.add_argument("case")
    a = p.parse_args()
    frozen = read(RESULTS / "scope.json")
    out = RESULTS / a.stage / a.case
    out.mkdir(parents=True, exist_ok=True)
    checker = Path(os.environ["JVMCONTRACT"]).resolve()
    data = numbered(a.case, out, frozen) if a.case in frozen["tasks"] else upgrade(a.case, out, frozen)
    data.update(
        case=a.case,
        stage=a.stage,
        checkerSha256=sha(checker),
        job=os.environ["VERIFY_JOB_ID"],
        source=os.environ["VERIFY_SOURCE_COMMIT"],
        receiptPackSha256=sha(out / "receipts.tar.gz"),
    )
    (out / "measurement.json").write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data.get("sides") or {k: v["status"] for k, v in data["tasks"].items()}))


if __name__ == "__main__":
    main()

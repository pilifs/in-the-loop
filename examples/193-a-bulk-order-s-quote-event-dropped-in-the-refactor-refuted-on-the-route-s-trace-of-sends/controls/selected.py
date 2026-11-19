"""Bind the public framework checker and independent two-order JVM observations to separate claims."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parent.parent
sys.path.insert(0, str(FOLDER.parent / "tools"))
from targets import executions, runtime_jdk, workflow


def build(work):
    app = ROOT / "examples/apps/shop"
    patch = FOLDER / "change.patch"
    jdk = Path(runtime_jdk.home("21"))
    classes, hashes, controls = {}, {}, {}
    for side in ("before", "after"):
        root = work / side
        source = root / "examples/apps/shop"
        shutil.copytree(app / "src", source / "src")
        if side == "after":
            subprocess.run(["git", "apply", "--whitespace=nowarn", str(patch)], cwd=root, check=True)
        dest = root / "classes"
        files = sorted((source / "src/main/java").rglob("*.java")) + sorted((source / "src/stubs/java").rglob("*.java"))
        subprocess.run([jdk / "bin/javac", "-proc:none", "-parameters", "-g", "--release", "21", "-d", dest, *files], check=True)
        classes[side] = dest
        hashes[side] = {f.relative_to(dest).as_posix(): workflow.file_sha256(f) for f in sorted(dest.rglob("*.class"))}
        driver = root / "driver"
        subprocess.run([jdk / "bin/javac", "-proc:none", "-cp", dest, "-d", driver, FOLDER / "controls/QuoteCases.java"], check=True)
        output = subprocess.check_output([jdk / "bin/java", "-cp", os.pathsep.join(map(str, (dest, driver))),
                                          "shop.QuoteCases", "99", "100"], text=True)
        controls[side] = [json.loads(line) for line in output.splitlines()]
        expected = [{"cents": 1, "quantity": n, "amount": total,
                     "sends": [{"topic": "quotes", "total": total, "quantity": n}] if n == 99 or side == "before" else []}
                    for n, total in ((99, 90), (100, 90))]
        if controls[side] != expected:
            raise ValueError(f"unexpected JVM observations for {side}: {controls[side]}")
    return classes, hashes, controls, runtime_jdk.identity(jdk)


def run(work, jvm_only):
    classes, hashes, controls, jdk = build(work)
    if jvm_only:
        print(json.dumps(controls, indent=2))
        return True
    checker = os.environ["JVMCONTRACT"]
    passed = True
    for name, expected in (("return-amount", "verified"), ("ordered-events", "refuted")):
        file = FOLDER / "claims" / (name + ".json")
        claim = json.loads(file.read_text())
        start = executions.now()
        execution = executions.new_id(start)
        dest = FOLDER / "receipts" / name / execution
        dest.mkdir(parents=True)
        caps = claim["bounds"]
        argv = [checker, "effects", str(classes["before"]), str(classes["after"]), "--entry", claim["subject"],
                "--observe", claim["observation"], "--unwind", str(caps["unwind"]), "--max-array-length", str(caps["maxArrayLength"]),
                "--trace-bound", str(caps["traceBound"]), "--cache", str(work / (name + "-cache")), "--json"]
        env = {**os.environ, "JAVA_HOME": jdk["home"], "PATH": str(Path(jdk["home"]) / "bin") + os.pathsep + os.environ["PATH"]}
        record = {"schema": "framework-observation-receipt/v1", "claimKey": workflow.canonical_digest(claim),
                  "binding": workflow.canonical_digest([claim, hashes, jdk["release"]]), "claim": claim,
                  "id": execution, "startedAt": start.isoformat(), "argv": argv, "artifacts": hashes, "jdk": jdk,
                  "checkerSha256": workflow.file_sha256(checker), "libTree": os.getenv("JVMCONTRACT_LIB_TREE"),
                  "job": os.getenv("VERIFY_JOB_ID"), "budgetSeconds": 300, "jvmControls": controls,
                  "limits": [claim["environment"]], "cache": "empty at start", "status": "started"}
        path = dest / "receipt.json"
        executions.save(path, record)
        clock = time.monotonic()
        result = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=330)
        (dest / "checker.json").write_text(result.stdout)
        (dest / "stderr.txt").write_text(result.stderr)
        reports = json.loads(result.stdout)
        report, = reports
        checked = report.get("checked") or {}
        outcome = checked.get("outcome") or {}
        accounts = outcome.get("accounting") or []
        observed = [row["observation"] for row in accounts]
        selected = observed == ["result"] if name == "return-amount" else len(observed) == 1 and observed[0].startswith("effect:")
        status = outcome.get("verdict")
        eligible = (report["entry"] == claim["subject"] and selected and status == expected
                    and result.returncode == (0 if expected == "verified" else 1)
                    and all(row["state"] == ("preserved" if name == "return-amount" else "refuted") for row in accounts)
                    and (expected == "verified" or (checked.get("before") is not None and checked.get("after") is not None)))
        record.update(status="completed", verdict=status, eligible=eligible, restsOn=checked.get("assumptions", []),
                      seconds=round(time.monotonic()-clock, 3), problem=report.get("unsupported") or outcome.get("problem"),
                      checkerOutput="checker.json", checkerOutputSha256=workflow.file_sha256(dest / "checker.json"))
        executions.save(path, record)
        print(name, status, "eligible" if eligible else "open", path.relative_to(ROOT))
        passed &= eligible
    return passed


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        sys.exit(0 if run(Path(directory), sys.argv[1:] == ["--jvm-only"]) else 1)

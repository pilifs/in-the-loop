#!/usr/bin/env python3
"""Writes the recorded fixtures under records/ and results/ that every stream's unit checks read, for Phase 0 of
llm-dlc/loops/example-targets.md. Each file says where it came from (`provenance`):

- recorded: a real run made by this script. The fixture JARs' concrete controls (each revision in its own JVM, on
  JDK 25 and 21), and `jvmcontract gaps` on RegexGate, the deliberate capability refusal: a static scan that proves
  nothing, whose binary is identified by its sha256.
- constructed: a record of how a run can go wrong, written by hand for the checks that must reject it: a killed
  control, a control whose output is malformed, a one-sided replay, a verifier that exited 1 with no witness, and a
  format-2 receipt that is incomplete or whose bundle doesn't match its files.

    python3 examples/tools/targets/fixtures/make_records.py [JVMCONTRACT]

Rerunning it rewrites them; the recorded ones change only with the JDK or the jvmcontract binary.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import build_fixtures  # noqa: E402



def load_oracle(path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("fixture_oracle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


JDKS = {"25": Path.home() / ".sdkman/candidates/java/25.0.5.0+8-tem",
        "21": Path.home() / ".sdkman/candidates/java/21.0.13.0+9-tem"}
RECORDS = HERE / "records"
RESULTS = HERE / "results"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def run(argv, stdout_name, cwd):
    started = time.monotonic()
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=60)
    seconds = round(time.monotonic() - started, 3)
    (RECORDS / stdout_name).write_text(proc.stdout)
    (RECORDS / stdout_name.replace(".stdout", ".stderr")).write_text(proc.stderr)
    return proc, seconds


def java_version(home):
    proc = subprocess.run([str(home / "bin/java"), "-version"], capture_output=True, text=True)
    return proc.stderr.strip().splitlines()[0]


def main(argv):
    jvmcontract = Path(argv[0] if argv else REPO / "lib/target/release/jvmcontract")
    if RECORDS.exists():
        shutil.rmtree(RECORDS)
    RECORDS.mkdir()
    work = Path(tempfile.mkdtemp(prefix=".records-", dir=HERE))
    try:
        manifest = build_fixtures.build(work)
        oracle = load_oracle(HERE / "gate/oracle.py")
        probes = [str(p) for p in oracle.PROBES]
        controls = []
        for feature, home in JDKS.items():
            for revision in build_fixtures.REVISIONS:
                classpath = f"driver.jar:adapter-{revision}.jar:{revision}.jar"
                name = f"control-{revision}-jdk{feature}.stdout"
                argv_ = [str(home / "bin/java"), "-cp", classpath, "fixture.driver.GateDriver", *probes]
                proc, seconds = run(argv_, name, work)
                observations = [json.loads(line) for line in proc.stdout.splitlines()]
                controls.append({
                    "kind": "jvm-control", "revision": revision, "argv": ["java", *argv_[1:]], "status": "exited",
                    "exitCode": proc.returncode, "seconds": seconds, "stdout": name,
                    "stderr": name.replace(".stdout", ".stderr"),
                    "identities": {"jdk": java_version(home), "classpath": [
                        {"path": p, "sha256": manifest["jars"][p[:-4]]["sha256"]} for p in classpath.split(":")]},
                    "observations": observations, "control": "gate-driver",
                    "oracleProblems": [list(x) for x in oracle.check(proc.stdout.splitlines())]})
        write(RECORDS / "controls.json", {"provenance": "recorded: each fixture revision's driver in its own JVM, on JDK 25 and 21, by make_records.py",
                                          "fixtures": manifest, "records": controls})
        argv_ = [str(jvmcontract), "gaps", "--classes", "after.jar", "--target", "fixture.RegexGate#allowed", "--json"]
        proc, seconds = run(argv_, "regex-gate-gaps.stdout", work)
        write(RECORDS / "regex-gate-gaps.json", {
            "provenance": "recorded: jvmcontract's static gap scan of RegexGate.allowed in the fixed fixture JAR (it proves nothing); "
                          "a strict proof that reaches these gaps is refused by name",
            "record": {"kind": "verifier", "revision": "after", "argv": ["jvmcontract", *argv_[1:]], "status": "exited",
                       "exitCode": proc.returncode, "seconds": seconds, "stdout": "regex-gate-gaps.stdout",
                       "stderr": "regex-gate-gaps.stderr",
                       "identities": {"jvmcontract": sha256_bytes(jvmcontract.read_bytes()),
                                      "after.jar": manifest["jars"]["after"]["sha256"]},
                       "observations": None, "control": None}})
    finally:
        shutil.rmtree(work, ignore_errors=True)
    constructed()


def constructed():
    base = {"argv": ["java", "-cp", "driver.jar:adapter-after.jar:after.jar", "fixture.driver.GateDriver", "65", "97"],
            "identities": {"jdk": "constructed"}, "control": "gate-driver"}
    (RECORDS / "killed.stdout").write_text('{"input":65,"outcome":"returned","value":false}\n')
    (RECORDS / "malformed.stdout").write_text('{"input":65,"outcome":"returned","value":false}\n{"input":97,"outc\n')
    (RECORDS / "exit-one.stdout").write_text("error: could not load fixture.Gate\n")
    for name in ("killed", "malformed", "exit-one"):
        (RECORDS / f"{name}.stderr").write_text("")
    write(RECORDS / "bad-runs.json", {
        "provenance": "constructed: how a run can go wrong, for the checks that must never read it as a result",
        "records": {
            "killed-control": {**base, "kind": "jvm-control", "revision": "after", "status": "killed", "exitCode": None,
                               "seconds": 30.0, "stdout": "killed.stdout", "stderr": "killed.stderr", "observations": None},
            "malformed-control": {**base, "kind": "jvm-control", "revision": "after", "status": "exited", "exitCode": 0,
                                  "seconds": 0.2, "stdout": "malformed.stdout", "stderr": "malformed.stderr", "observations": None},
            "one-sided-replay": [
                {**base, "kind": "jvm-control", "revision": "before", "status": "exited", "exitCode": 0, "seconds": 0.2,
                 "stdout": "killed.stdout", "stderr": "killed.stderr",
                 "observations": [{"input": 65, "outcome": "returned", "value": False}]},
                {**base, "kind": "jvm-control", "revision": "after", "status": "not-started", "exitCode": None, "seconds": 0.0,
                 "stdout": "exit-one.stdout", "stderr": "exit-one.stderr", "observations": None}],
            "exit-one-verifier": {"kind": "verifier", "revision": "before", "argv": ["jvmcontract", "prove", "--engine", "native"],
                                  "status": "exited", "exitCode": 1, "seconds": 0.5, "stdout": "exit-one.stdout",
                                  "stderr": "exit-one.stderr", "identities": {"jvmcontract": "constructed"},
                                  "observations": None, "control": None},
        }})
    # Receipts: a genuine format-2 result (example 025's) made incomplete, and one whose bundle doesn't match.
    if RESULTS.exists():
        shutil.rmtree(RESULTS)
    source = next(REPO.glob("examples/025-*"))
    genuine = json.loads((source / "result.json").read_text())
    incomplete = {k: v for k, v in genuine.items() if k != "conclusion"}
    write(RESULTS / "incomplete/result.json", incomplete)
    mismatch = RESULTS / "bundle-mismatch"
    mismatch.mkdir(parents=True)
    for a in genuine["bundle"]["artifacts"]:
        shutil.copyfile(source / a["path"], mismatch / a["path"])
    with open(mismatch / "verifier-output.txt", "a") as f:
        f.write("one line the run never wrote\n")
    write(mismatch / "result.json", genuine)
    write(RESULTS / "provenance.json", {"provenance": "constructed from example 025's committed result.json and evidence: "
                                        "incomplete/ lacks its conclusion; bundle-mismatch/ has a verifier-output.txt with one "
                                        "line appended, so its sha256 is not the bundle's"})


if __name__ == "__main__":
    main(sys.argv[1:])

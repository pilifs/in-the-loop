"""Run the hours adapter and a one-line wrong-unit control on the same two original artifacts."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from oracle import totals

FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER.parent / "tools"))
from targets import route, runtime, runtime_jar, sidecar


def run(work):
    example = json.loads((FOLDER / "example.json").read_text())
    target = sidecar.load(FOLDER, example)
    plan = route.resolve(FOLDER, example, target, "replay")
    prepared = {r: runtime.prepare(plan, r, work / "prepare" / r) for r in plan.revisions}
    records = runtime.run_controls(plan, prepared, work / "controls")
    report = {"grid": {"ticks": [0, 191], "minutesPerTick": 15, "start": "2012-06-15T00:00", "unit": "HOURS"},
              "checkedEntry": "civil.Hours#completeHours(II)J", "subject": plan.target, "revisions": {}}
    source = (FOLDER / "adapter/civil/Hours.java").read_text()
    assert source.count("ChronoUnit.HOURS") == 1
    mutant = work / "wrong-unit/Hours.java"
    mutant.parent.mkdir()
    mutant.write_text(source.replace("ChronoUnit.HOURS", "ChronoUnit.MINUTES"))
    for record in records:
        rev = record.revision
        p = prepared[rev]
        if record.status != "exited" or record.exitCode or not record.observations:
            raise ValueError(f"{rev} JVM correspondence failed")
        where = Path(p.workdir)
        cp = runtime._checked(where, p)
        original = where / p.source["target"]["loadedFrom"]
        adapter = next(a for a in cp if a.role == "adapter")
        classes = work / "wrong-unit" / rev
        jdk = Path(record.identities["jdkHome"])
        subprocess.run([jdk / "bin/javac", "-proc:none", "-parameters", "-g", "-cp", original, "-d", classes, mutant], check=True)
        changed_cp = [str(classes) if a.path == adapter.path else str(where / a.path) for a in cp]
        negative = subprocess.run([jdk / "bin/java", "-cp", os.pathsep.join(changed_cp), "civil.ClockCases"],
                                  check=True, text=True, capture_output=True)
        observed = totals([json.dumps(row) for row in record.observations])
        wrong = totals(negative.stdout.splitlines())
        if observed["correspondence"] or wrong["correspondence"] == 0:
            raise ValueError(f"{rev} correspondence admitted a wrong-unit adapter or rejected the hours adapter")
        report["revisions"][rev] = {
            "commit": p.commit, "subjectClassSha256": p.source["target"]["classSha256"], "jdkRelease": record.identities["jdkRelease"],
            "adapterClassSha256": hashlib.sha256(runtime_jar.read_class(where / adapter.path, "civil/Hours")).hexdigest(),
            "classpath": record.identities["classpath"], "actual": observed,
            "wrongUnit": {"classSha256": runtime.sha256(classes / "civil/Hours.class"), **wrong}}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        report = run(Path(directory))
    message = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(message)
    else:
        print(message, end="")

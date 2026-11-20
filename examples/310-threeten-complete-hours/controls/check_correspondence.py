"""Run the hours adapter and a one-line wrong-unit control on the same two original artifacts."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER / "controls"))
sys.path.insert(0, str(FOLDER.parent / "tools"))
from oracle import totals
from targets import route, runtime, runtime_jar, runtime_jdk, sidecar


def check_context(work, prepared):
    service = "META-INF/services/org.threeten.bp.chrono.Chronology"
    empty = work / "empty"
    empty.mkdir()
    configured = work / "configured"
    descriptor = configured / service
    descriptor.parent.mkdir(parents=True)
    descriptor.write_text("control.UnavailableChronology\n")
    jdk = Path(runtime_jdk.home("21"))
    source = FOLDER / "controls/ChronologyContext.java"
    captures = json.loads((FOLDER / "records/registry-probes.json").read_text())["probes"]
    report = {"jdk": runtime_jdk.identity(jdk), "inputs": [94, 97], "checkedEntry": "civil.Hours#completeHours(II)J",
              "descriptor": {"path": service, "contents": descriptor.read_text(), "sha256": runtime.sha256(descriptor)},
              "revisions": {}}
    for rev, p in prepared.items():
        if p.stage != "artifacts-ready":
            raise ValueError(f"{rev}: {p.stage}: {p.diagnostic}")
        where = Path(p.workdir)
        checked = {a.sha256: a for a in runtime._checked(where, p)}
        binding = next(r["artifacts"] for r in captures if r["revision"] == rev)
        artifacts = [checked[binding[flag]] for flag in ("--classes", "--classpath")]
        original_cp = [str(where / a.path) for a in artifacts]
        classes = work / "context-control" / rev
        subprocess.run([jdk / "bin/javac", "-proc:none", "--release", "21", "-cp", os.pathsep.join(original_cp),
                        "-d", classes, source], check=True)
        cp = os.pathsep.join([str(classes), *original_cp])
        runs = {}
        for name, resources in (("empty", empty), ("unavailableProvider", configured)):
            argv = [str(jdk / "bin/java"), "-cp", cp, "ChronologyContext", str(resources)]
            lines = subprocess.check_output(argv, text=True).splitlines()
            expected = ["application=0", "context=0", f"hours={1 if rev == 'parent' else 0}"] if name == "empty" else [
                "application=0", "context=1", "error=java.util.ServiceConfigurationError",
                "message=org.threeten.bp.chrono.Chronology: Provider control.UnavailableChronology not found"]
            if lines != expected:
                raise ValueError(f"{rev} {name}: {lines}")
            runs[name] = {"argv": argv, "stdout": lines}
        report["revisions"][rev] = {"commit": p.commit, "subjectClassSha256": p.source["target"]["classSha256"],
            "classpath": [{"path": a.path, "sha256": a.sha256, "role": a.role} for a in artifacts],
            "controlClassSha256": runtime.sha256(classes / "ChronologyContext.class"), "runs": runs}
    return report


def run(work, context_only=False):
    example = json.loads((FOLDER / "example.json").read_text())
    target = sidecar.load(FOLDER, example)
    plan = route.resolve(FOLDER, example, target, "replay")
    prepared = {r: runtime.prepare(plan, r, work / "prepare" / r) for r in plan.revisions}
    if context_only:
        return check_context(work, prepared)
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
    parser.add_argument("--context-only", action="store_true", help="exercise service discovery on identical application classpaths")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        report = run(Path(directory), args.context_only)
    message = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(message)
    else:
        print(message, end="")

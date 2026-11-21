"""Run standalone JBMC separately on original classpaths when the V0 paired front end rejects them."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from jbmc_pair import HERE, ROOT, check_files, digest, route, runtime, sidecar, tools
from targets.interfaces import Unsupported


HARNESSES = {
    "348": """
        int[] keys = calibration.GeneratedKeys.keys(selected);
        boolean two = keys != null && keys.length == 2 && keys[0] == 1 && keys[1] == 2;
        boolean last = keys != null && keys.length == 1 && keys[0] == 2;
        matches = selected ? last : two;
""",
    "351": """
        long millis = calibration.Projection.roundtrip(selected);
        matches = millis == (selected ? 946684800123L : Long.MAX_VALUE);
""",
}


def harness(number):
    return """public final class CallerBaseline {
    public static void check(boolean selected) {
        boolean matches;
        try {
""" + HARNESSES[number] + """        } catch (Throwable error) {
            matches = false;
        }
        assert matches : "original caller observation";
    }
    public static void main(String[] args) { check(Boolean.parseBoolean(args[0])); }
}
"""


def summarize(raw):
    if raw.stat().st_size > 32 << 20:
        return {"completeJsonRead": False, "reason": "output exceeds 32 MiB", "sha256": digest(raw)}
    try:
        document = json.loads(raw.read_bytes())
    except (ValueError, UnicodeDecodeError):
        return {"completeJsonRead": False, "reason": "incomplete JBMC JSON", "sha256": digest(raw)}
    messages = [row.get("messageText", "") for row in document if "messageText" in row]
    properties = [p for row in document for p in row.get("result", [])]
    selected = []
    for prop in properties:
        if prop.get("status") != "FAILURE":
            continue
        for step in prop.get("trace", []):
            lhs = step.get("lhs", "")
            if "selected" in lhs and "CallerBaseline" in lhs:
                selected.append({"property": prop.get("property"), "lhs": lhs, "value": step.get("value")})
    return {
        "completeJsonRead": True, "sha256": digest(raw),
        "cProverStatus": [r["cProverStatus"] for r in document if "cProverStatus" in r],
        "properties": [{"property": p.get("property"), "description": p.get("description"),
                        "status": p.get("status")} for p in properties],
        "warnings": [m for m in messages if any(term in m.lower() for term in
                     ("warning", "not found", "stub", "no body", "missing", "not implemented", "unwind"))][:50],
        "failingInputAssignments": selected,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", choices=HARNESSES)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--jvm-only", action="store_true", help="exercise the two harness arms without JBMC")
    args = parser.parse_args()
    n = args.example
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    frozen = json.loads((HERE / "v0.json").read_text())
    binary = Path(shutil.which("jbmc") or "missing-jbmc")
    if digest(binary) != frozen["sha256"]["jbmc"]:
        raise ValueError("JBMC binary differs from the V0 comparison")
    jdk = (Path.home() / ".sdkman/candidates/java/21.0.13.0+9-tem").resolve()
    checker = Path.home() / ".cache/in-the-loop/external-upgrades" / frozen["sha256"]["jvmcontract"] / "jvmcontract"
    tools(frozen, checker, jdk, (Path.home() / "tools/bitwuzla/current/lib/x86_64-linux-gnu").resolve())
    check_files(frozen)
    original = next((ROOT / "verification/results").glob(f"20261120-2347*-{n}-run-the-frozen-v0-*"))
    folder = next((ROOT / "examples").glob(n + "-*/target.json")).parent
    record = next((original / "outputs" / folder.relative_to(ROOT)).glob("receipts/*/2*/records/verifier.json"))
    native = json.loads(record.read_text())["record"]["identities"]
    example = json.loads((folder / "example.json").read_text())
    task = {"348": "generated-keys", "351": "roundtrip"}[n]
    plan = route.resolve(folder, example, sidecar.load(folder, example), task)
    if isinstance(plan, Unsupported):
        raise ValueError(plan.describe())
    source = out / "CallerBaseline.java"
    source.write_text(harness(n))
    measurement = {"example": n, "task": task, "sourceClaim": plan.claim["key"], "sourceSha256": digest(source),
                   "nativeResult": str(record.relative_to(ROOT)), "nativeRecordSha256": digest(record),
                   "route": "assisted per-side checks against one independently fixed caller contract",
                   "jbmcSha256": digest(binary), "sourceRevision": frozen["revision"],
                   "unwind": native["bounds"]["unwind"], "arrayBound": native["bounds"]["maxArrayLength"], "sides": {}}
    start = time.monotonic()
    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        for side in plan.revisions:
            prep = work / side
            target = runtime.prepare(plan, side, prep)
            if isinstance(target, Unsupported) or target.stage != "artifacts-ready":
                raise ValueError("original inputs unavailable")
            bound = native["classpath"][side]
            files = [prep / entry["path"] for entry in bound]
            if any(digest(p) != entry["sha256"] for p, entry in zip(files, bound)):
                raise ValueError("classpath differs from the matched native run")
            compiled = work / ("harness-" + side)
            compiled.mkdir()
            cp = os.pathsep.join(map(str, [compiled, *files]))
            subprocess.run([jdk / "bin/javac", "--release", "8", "-g", "-d", compiled, "-cp", cp, source],
                           check=True)
            jvm = {}
            for selected in ("false", "true"):
                result = subprocess.run([jdk / "bin/java", "-Duser.timezone=UTC", "-Duser.language=en",
                                         "-Duser.country=US", "-ea", "-cp", cp, "CallerBaseline", selected],
                                        capture_output=True, text=True, timeout=25)
                failure = n == "348" and side == "new" and selected == "true"
                if result.returncode != int(failure) or (failure and "AssertionError: original caller" not in result.stderr):
                    raise ValueError("harness disagrees with direct original JVM observations")
                jvm[selected] = {"exit": result.returncode, "assertionFailed": failure}
            arm = {"classpath": bound, "harnessClassSha256": digest(compiled / "CallerBaseline.class"), "jvm": jvm}
            measurement["sides"][side] = arm
            if args.jvm_only:
                continue
            # The two actual engine launches share the native search deadline and exact semantic bounds.
            remaining = max(0, native["timeout"] - (time.monotonic() - start))
            if side == plan.revisions[0]:
                remaining /= len(plan.revisions)
            command = [str(binary), "CallerBaseline", "--function", "CallerBaseline.check:(Z)V", "--classpath", cp,
                       "--unwind", str(measurement["unwind"]), "--max-nondet-array-length", str(measurement["arrayBound"]),
                       "--trace", "--throw-runtime-exceptions", "--unwinding-assertions", "--json-ui",
                       "--no-refine-strings", "--sat-solver", "cadical"]
            raw, err = work / (side + ".stdout"), out / (side + ".stderr")
            before = time.monotonic()
            with raw.open("wb") as stdout, err.open("wb") as stderr:
                try:
                    process = subprocess.run(command, stdout=stdout, stderr=stderr, cwd=work, timeout=remaining)
                    code = process.returncode
                except subprocess.TimeoutExpired:
                    code = 124
            arm.update(toolExit=code, seconds=round(time.monotonic() - before, 3),
                       argv=[value.replace(cp, "<ordered original classpath with harness>") for value in command],
                       result=summarize(raw))
            if raw.stat().st_size <= 1024 * 1024:
                shutil.copyfile(raw, out / (side + ".json"))
        if len({r["harnessClassSha256"] for r in measurement["sides"].values()}) != 1:
            raise ValueError("baseline harness class differs between revisions")
    measurement["seconds"] = round(time.monotonic() - start, 3)
    measurement["mode"] = "jvm-control-only" if args.jvm_only else "standalone-jbmc"
    (out / "measurement.json").write_text(json.dumps(measurement, indent=2) + "\n")
    print(n, measurement["mode"], [(s, r.get("toolExit")) for s, r in measurement["sides"].items()])


if __name__ == "__main__":
    main()

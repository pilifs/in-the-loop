"""Repeat ordinary native verdicts with and without LRAT assurance, and challenge the resulting bindings."""

import argparse
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import zipfile

from capture import ROOT, benchmark
from prepare import HERE
sys.path.insert(0, str(ROOT / "lib/python"))
import jvmcontract_lrat as lrat

TASKS = (("336", "first-8-release"), ("393", "conversion-equivalence-classified"),
         ("393", "node-checks-same"), ("395", "exact-order-same-reference"))


def read(file):
    return json.loads(file.read_text())


def check_process(folder, request=None, boundary=None, pack=None):
    run = subprocess.run([sys.executable, "-B", lrat.__file__, "--check", request or folder / "request.json",
                          boundary or folder / "boundary.json", pack or folder / "evidence.zip"],
                         capture_output=True, text=True)
    return run.returncode, run.stdout, run.stderr.strip()


def normal(example, task, flags, env):
    command = [sys.executable, "-B", "examples/tools/build.py", example, "--task", task, *flags]
    start = time.monotonic()
    done = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
    duration = time.monotonic() - start
    print(done.stdout, flush=True)
    if done.returncode:
        raise ValueError(f"{task}: {done.stderr} {done.stdout[-1500:]}")
    path, = re.findall(r", receipt (receipts/.+?/result\.json)$", done.stdout, re.M)
    result = next((ROOT / "examples").glob(example + "-*")) / path
    return result, duration


def run_example(example, task, out, work):
    ordinary_env = {**os.environ, "JVMCONTRACT_TRANSCRIPTS": str(work / "forwarding-control")}
    off, off_time = normal(example, task, [], ordinary_env)
    filtered = not list((work / "forwarding-control").glob("*.icnf"))
    on, on_time = normal(example, task, ["--certify-lrat"], os.environ)
    off_result, on_result = read(off), read(on)
    for key in ("status", "claim", "vacuous"):
        if off_result["conclusion"][key] != on_result["conclusion"][key]:
            raise ValueError(f"{example}/{task}: ordinary {key} changed with certification")
    folder = out / task
    shutil.copytree(on.parent / "lrat", folder)
    # Keep the original receipt to which the independent capture attests together with the run's evidence.
    shutil.copyfile(on, folder / "ordinary.json")
    shutil.copyfile(off, folder / "uncertified.json")
    assurance = read(folder / "assurance.json")
    code, _, error = check_process(folder)
    if code or assurance["status"] != "checked":
        raise ValueError(f"{task}: {error}")
    return {"key": f"{example}/{task}", "qualified": on_result["conclusion"]["status"], "offWallSeconds": off_time,
            "onWallSeconds": on_time, "defaultLauncherFilteredTranscript": filtered,
            "ordinarySha256": lrat.digest(on.read_bytes()), "uncertifiedSha256": lrat.digest(off.read_bytes()),
            "assurance": assurance}


def prefix(out, work):
    case, = benchmark.load_cases([3], "held/prefix-sums")
    classes, bindings = {}, {}
    for side in (case["before"], case["after"]):
        directory = work / side
        cls = directory / "bench/held/PrefixSums.class"
        cls.parent.mkdir(parents=True)
        # Use the exact old compiled classes whose formula and independent rebuild were published.
        frozen = HERE / "evidence/bounded-sat/prefix-inputs" / (side + ".bin")
        shutil.copyfile(frozen, cls)
        expected = read(HERE / "evidence/bounded-sat/capture.json")["fallbackClassSha256"][side]
        if lrat.digest(cls.read_bytes()) != expected:
            raise ValueError(f"prefix-sums {side}: original class differs")
        source = next((benchmark.HERE / benchmark.versions()[side]).rglob("PrefixSums.java"))
        bindings[side] = {"class": "bench.held.PrefixSums", "classSha256": expected,
                          "sourceSha256": lrat.digest(source.read_bytes())}
        classes[side] = directory
    folder = out / "prefix-sums"
    folder.mkdir()
    executable = os.environ["JVMCONTRACT"]
    options = SimpleNamespace(jvmcontract=executable, timeout=120, jbmc="jbmc")
    rows = []
    for enabled in (False, True):
        run_dir = work / ("certified" if enabled else "ordinary")
        run_dir.mkdir()
        cmd = benchmark.command(case, "native", "strict", classes, run_dir, options)
        env = {k: v for k, v in os.environ.items() if k not in ("JVMCONTRACT_TRANSCRIPTS", "JVMCONTRACT_LRAT_MODELS")}
        env["JVMCONTRACT_SOLVER"] = "cadical"
        if enabled:
            env.update(JVMCONTRACT_TRANSCRIPTS=str(work / "prefix-traces"), JVMCONTRACT_LRAT_MODELS="1")
            request = {"schema": "native-sat-request/v1", "run": run_dir.parent.name, "task": case["id"], "claim": case,
                       "argv": [str(a) for a in cmd], "checkerSha256": lrat.digest(Path(executable).read_bytes()),
                       "bindings": bindings, "unwind": benchmark.UNWIND, "maxArrayLength": benchmark.MAX_ARRAY_LENGTH}
            lrat.save(folder / "request.json", request)
        start = time.monotonic()
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=True)
        result = json.loads(proc.stdout)
        if result["verdict"] != "verified":
            raise ValueError("prefix-sums ordinary result changed")
        receipt = folder / ("ordinary.json" if enabled else "uncertified.json")
        receipt.write_text(proc.stdout)
        if enabled:
            anchor = {"status": "established", "receiptSha256": lrat.digest(receipt.read_bytes()),
                      "target": result["target"], "execution": request["run"]}
            boundary, streams = lrat.capture(request, anchor, run_dir, work / "prefix-traces", result["search"]["runs"])
            assurance = lrat.complete(folder, request, boundary, streams)
        rows.append(time.monotonic() - start)
    return {"key": case["id"], "qualified": "established", "offWallSeconds": rows[0], "onWallSeconds": rows[1],
            "assurance": assurance}


def negative_controls(folder, other, tmp):
    """Each item must fail verification against the original caller's retained inputs."""
    results = []
    with zipfile.ZipFile(folder / "evidence.zip") as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    original = json.loads(contents["manifest.json"])
    indices = [i for i, e in enumerate(original["events"]) if e["status"] == "unsat"]
    i = indices[0]
    j = next(j for j in indices[1:] if original["events"][j]["assumptionUnits"] != original["events"][i]["assumptionUnits"])
    for name in ("missing-proof", "duplicate-event", "swapped-assumptions-and-formulas", "swapped-proofs"):
        entries = dict(contents)
        manifest = copy.deepcopy(original)
        a, b = manifest["events"][i], manifest["events"][j]
        first, second = f"proofs/{a['key']}.lrat", f"proofs/{b['key']}.lrat"
        if name == "missing-proof":
            del entries[first]
        elif name == "duplicate-event":
            manifest["events"][i] = dict(b)
        elif name == "swapped-assumptions-and-formulas":
            for field in ("formulaSha256", "assumptionUnits"):
                a[field], b[field] = b[field], a[field]
        else:
            entries[first], entries[second] = entries[second], entries[first]
            a["proofSha256"], b["proofSha256"] = b["proofSha256"], a["proofSha256"]
        entries["manifest.json"] = json.dumps(manifest).encode()
        bad = tmp / (name + ".zip")
        with zipfile.ZipFile(bad, "x", compression=zipfile.ZIP_DEFLATED) as pack:
            for key, value in entries.items():
                pack.writestr(key, value)
        code, _, reason = check_process(folder, pack=bad)
        if not code or a["key"] not in reason:
            raise ValueError(f"{name}: expected first unmatched {a['key']}, got {code}, {reason}")
        results.append({"control": name, "status": "withheld", "reason": reason})
    code, _, reason = check_process(other, pack=folder / "evidence.zip")
    if not code or "top-level request" not in reason:
        raise ValueError(f"transplanted valid bundle: {code}, {reason}")
    results.append({"control": "different-top-level-request", "status": "withheld", "reason": reason})
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        rows = [run_example(example, task, out, work) for example, task in TASKS]
        rows.append(prefix(out, work))
        guava, classified, negative, zero, additive = rows
        proof, probe = guava["assurance"]["passes"]
        if (proof["answers"], probe["answers"]) != ({"sat": 16, "unsat": 8}, {"sat": 2}):
            raise ValueError("Guava's two original passes differ")
        if additive["assurance"]["answers"] != {"sat": 8, "unsat": 10}:
            raise ValueError("prefix sums does not reproduce all 18 original calls")
        if (classified["assurance"]["passes"][0]["attempts"], negative["assurance"]["passes"][0]["attempts"]) != (19, 8):
            raise ValueError("Jackson main proof or refutation count differs")
        classifier = ROOT / "examples/393-wide-floating-conversions/adapter/ConversionEquivalence.java"
        expected_source = "7689850ddf8fca0f4000a7e2002eb72479c3fd576e1277b9a6edd10cb1573eb4"
        if classified["qualified"] != "established" or lrat.digest(classifier.read_bytes()) != expected_source:
            raise ValueError("the ordinary verdict does not establish the pinned parity classifier")
        classification = {"sourceSha256": expected_source, "admittedLongs": 1 << 54,
                          "midpointBins": (1 << 54) // (1 << 31), "mismatchesPerBin": 2}
        classification["disagreements"] = classification["midpointBins"] * classification["mismatchesPerBin"]
        replay = read(out / "node-checks-same/boundary.json")["ordinary"]["jvmReplay"]
        if negative["qualified"] != "refuted" or not any(r.get("by") == "jvm" and r.get("reproduced") for r in replay):
            raise ValueError("Jackson refutation lacks the JVM witness")
        if zero["assurance"]["passes"][0]["attempts"] or not zero["assurance"]["passes"][0]["solverFree"]:
            raise ValueError("UTF-16 did not produce the original zero-call proof")
        controls = negative_controls(out / "first-8-release", out / "exact-order-same-reference", work)
        lrat.save(out / "summary.json", {"schema": "whole-verdict-lrat-evaluation/v1", "workloads": rows,
                  "controls": controls, "jacksonJvmReplay": replay, "jacksonClassification": classification,
                  "scope": "Every SAT model satisfies its actual clause prefix and assumption units. Every UNSAT call has a checked LRAT proof. Java encoding, control flow, bounds and constant folding remain trusted."})
        print(json.dumps([(r["key"], r["assurance"]["answers"]) for r in rows]))


if __name__ == "__main__":
    main()

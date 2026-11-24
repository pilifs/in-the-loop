"""Repeat ordinary native verdicts with and without LRAT assurance, and challenge the resulting bindings."""

import argparse
from collections import Counter
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
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
ORIGINAL_EXECUTIONS = {
    "first-8-release": "20261120T185205Z-3b241b48",
    "conversion-equivalence-classified": "20261123T175658Z-a06b7e22",
    "node-checks-same": "20261123T175647Z-adfae7f5",
    "exact-order-same-reference": "20261123T175757Z-81562309",
}


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


def check_original_request(example, task, request):
    """Independently retain the claim, classpath and bounds specified before certification was implemented."""
    directory, = (ROOT / "examples").glob(f"{example}-*/receipts/{task}")
    original = ORIGINAL_EXECUTIONS[task]
    claim = read(directory / original / "result.json")["claim"]["statement"]
    launch = read(directory / "executions" / original / "attempt.json")["checker"]
    if (request["example"], request["task"], request["kind"], request["target"], request["claim"]) != (
            example, task, claim["kind"], claim["target"], claim["claim"]):
        raise ValueError(f"{example}/{task}: request differs from the frozen ordinary claim")
    for field in ("checkedEntry", "entryBindings", "classpath", "commits", "bounds", "jdkRelease", "engine", "gaps"):
        if request["checker"][field] != launch[field]:
            raise ValueError(f"{example}/{task}: {field} differs from the original ordinary execution")


def independent_guava(receipt, work, bundle, output):
    """Reconstruct the caller's expectation from the earlier claim and the native launch journal."""
    task = "first-8-release"
    origin = receipt.parents[1] / "executions" / receipt.parent.name
    journal = read(origin / "attempt.json")
    native_result = read(origin / "checker.json")
    original = read(receipt.parents[1] / ORIGINAL_EXECUTIONS[task] / "result.json")
    statement = original["claim"]["statement"]
    identities = journal["checker"]
    request = {"schema": "native-sat-request/v1", "run": journal["id"], "example": "336", "task": task,
               "kind": statement["kind"], "target": statement["target"], "claim": statement["claim"],
               "bindings": journal["bindings"], "argv": journal["argv"], "bindingId": journal["bindingId"],
               "sourceCommit": journal["sourceCommit"],
               "checkerBuild": {k: identities[k] for k in ("commit", "libTree") if k in identities},
               "checker": {k: identities[k] for k in ("jvmcontract", "jdkRelease", "engine", "gaps", "bounds",
                           "environment", "classpath", "entryBindings", "checkedEntry", "commits", "scope", "recipe")}}
    check_original_request("336", task, request)
    result = read(receipt)
    conclusion = result["conclusion"]
    if (journal["id"] != receipt.parent.name or native_result["argv"] != request["argv"]
            or native_result["status"] != "exited" or native_result["exitCode"] != 0
            or conclusion["attempt"] != journal["id"] or conclusion["status"] != "established" or conclusion["vacuous"]
            or request["claim"]["key"] != result["claim"]["target"]["claimKey"]):
        raise ValueError("Guava checker completion or frozen request differs")
    native, = (work / ".build-py").glob(f"*/targets/336/{task}/{journal['id']}/verifier")
    anchor = {"status": conclusion["status"], "execution": journal["id"], "conclusion": conclusion,
              "receiptSha256": lrat.digest(receipt.read_bytes()), "jvmReplay": []}
    runs = [run for observation in native_result["outcomes"] for run in observation["search"]["runs"]]
    boundary, streams = lrat.capture(request, anchor, native, native / "solver-traces", runs)
    output.mkdir()
    lrat.save(output / "request.json", request)
    lrat.save(output / "boundary.json", boundary)
    # Retain the inputs used by this observer separately from the bundle handed to the checker.
    with tarfile.open(output / "native-origin.tar.gz", "w:gz") as archive:
        for path in (origin / "attempt.json", origin / "checker.json", receipt):
            archive.add(path, arcname="original/" + path.name)
        paths = [*streams, *native.rglob("bmc.log"), *(native / name for name in boundary["generatedClasses"])]
        for path in paths:
            archive.add(path, arcname="verifier/" + path.relative_to(native).as_posix())
    code, stdout, error = check_process(output, pack=bundle)
    if code:
        raise ValueError(f"independent Guava origin: {error}")
    checked = json.loads(stdout)
    if checked["answers"] != {"sat": 18, "unsat": 8}:
        raise ValueError("independent Guava call inventory differs")
    lrat.save(output / "recheck.json", checked)
    return checked["boundarySha256"]


def run_example(example, task, out, work):
    kept = Path(os.environ.get("VERIFY_WORKDIR", work / "launches"))
    env = {**os.environ, "VERIFY_WORKDIR": str(kept)}
    ordinary_env = {**env, "JVMCONTRACT_TRANSCRIPTS": str(work / "forwarding-control")}
    off, off_time = normal(example, task, [], ordinary_env)
    filtered = not list((work / "forwarding-control").glob("*.icnf"))
    on, on_time = normal(example, task, ["--certify-lrat"], env)
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
    check_original_request(example, task, read(folder / "request.json"))
    code, _, error = check_process(folder)
    if code or assurance["status"] != "checked":
        raise ValueError(f"{task}: {error}")
    if example == "336":
        if independent_guava(on, kept, folder / "evidence.zip", out / "independent-guava") != assurance["boundarySha256"]:
            raise ValueError("independent Guava origin differs from the ordinary certified execution")
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


def report(out):
    """Read the completed experiment and reconcile the table with its ordinary and assurance receipts."""
    if not (out / "summary.json").exists():
        combined = []
        for group in ("core", "extensions"):
            if (out / group / "summary.json").is_file():
                lines = report(out / group).splitlines()
                combined.extend(lines[2:] if combined else lines)
        if not combined:
            raise ValueError(f"{out}: no completed workload summary")
        return "\n".join(combined)
    summary = read(out / "summary.json")
    native = [f"{number}/{task}" for number, task in TASKS]
    expected = {"core": [native[0], "held/prefix-sums"], "extensions": native[1:],
                "all": native + ["held/prefix-sums"]}[summary.get("group", "all")]
    rows = summary["workloads"]
    if [row["key"] for row in rows] != expected:
        raise ValueError("workload inventory differs from the qualification")
    table = [
        "| Ordinary request | Disposition | Native attempts by pass | Ordinary s | Certified s | Generation s | Fresh check s | Bundle bytes |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        key = row["key"]
        folder = out / key.split("/", 1)[1]
        result = read(folder / "ordinary.json")
        request = read(folder / "request.json")
        boundary = read(folder / "boundary.json")
        assurance = read(folder / "assurance.json")
        ordinary = boundary["ordinary"]
        if (assurance != row["assurance"] or assurance["status"] != "checked"
                or assurance["ordinary"] != row["qualified"] or ordinary["status"] != row["qualified"]
                or assurance["requestSha256"] != lrat.identity(request)
                or assurance["boundarySha256"] != lrat.identity(boundary)
                or boundary["requestSha256"] != assurance["requestSha256"]
                or ordinary["execution"] != request["run"]
                or lrat.digest((folder / "ordinary.json").read_bytes()) != ordinary["receiptSha256"]
                or (folder / "evidence.zip").stat().st_size != assurance["bundleBytes"]):
            raise ValueError(f"{key}: measurement differs from the retained execution")
        if key.startswith("held/"):
            if request["task"] != key or result["verdict"] != "verified" or read(folder / "uncertified.json")["verdict"] != "verified":
                raise ValueError(f"{key}: original equivalence result differs")
        else:
            check_original_request(*key.split("/", 1), request)
            off = read(folder / "uncertified.json")
            if (key != f"{request['example']}/{request['task']}"
                    or result["conclusion"] != ordinary["conclusion"]
                    or row["ordinarySha256"] != ordinary["receiptSha256"]
                    or lrat.digest((folder / "uncertified.json").read_bytes()) != row["uncertifiedSha256"]
                    or any(result["conclusion"][k] != off["conclusion"][k] for k in ("status", "claim", "vacuous"))):
                raise ValueError(f"{key}: ordinary receipt or uncertified comparison differs")
        pass_totals = []
        all_calls = Counter()
        for measured, observed in zip(assurance["passes"], boundary["passes"], strict=True):
            counts = {status: observed["calls"].count(code) for code, status in lrat.ANSWERS.items() if code in observed["calls"]}
            free = not any(name in counts for name in ("sat", "unsat", "unknown"))
            if (measured["id"] != observed["id"] or measured["answers"] != counts
                    or measured["attempts"] != len(observed["calls"]) or measured["solverFree"] != free):
                raise ValueError(f"{key} {observed['id']}: call inventory differs")
            all_calls.update(counts)
            answers = ", ".join(f"{n} {name.upper()}" for name, n in counts.items()) or "zero calls"
            pass_totals.append(f"{measured['id']} {answers}")
        if (assurance["answers"] != dict(all_calls) or assurance["satModelsChecked"] != all_calls["sat"]
                or assurance["checkerSha256"] != (lrat.CAKE_SHA if all_calls["unsat"] else None)):
            raise ValueError(f"{key}: checked answer totals differ from the native passes")
        table.append(f"| `{key}` | {row['qualified']} | {' / '.join(pass_totals)} | {row['offWallSeconds']:.3f} "
                     f"| {row['onWallSeconds']:.3f} | {assurance['generationSeconds']:.3f} "
                     f"| {assurance['freshCheckSeconds']:.3f} | {assurance['bundleBytes']:,} |")
    return "\n".join(table)


def core(out, work):
    guava = run_example(*TASKS[0], out, work)
    additive = prefix(out, work)
    proof, probe = guava["assurance"]["passes"]
    if (proof["answers"], probe["answers"]) != ({"sat": 16, "unsat": 8}, {"sat": 2}):
        raise ValueError("Guava's two original passes differ")
    if additive["assurance"]["answers"] != {"sat": 8, "unsat": 10}:
        raise ValueError("prefix sums does not reproduce all 18 original calls")
    controls = negative_controls(out / "first-8-release", out / "prefix-sums", work)
    return {"group": "core", "workloads": [guava, additive], "controls": controls}


def extensions(out, work):
    classified, negative, zero = [run_example(number, task, out, work) for number, task in TASKS[1:]]
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
    return {"group": "extensions", "workloads": [classified, negative, zero],
            "jacksonJvmReplay": replay, "jacksonClassification": classification}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--group", choices=("core", "extensions", "all"), default="all")
    ap.add_argument("--report", action="store_true", help="print measurements from the completed job receipts")
    args = ap.parse_args()
    out = args.output
    if args.report:
        print(report(out))
        return
    out.mkdir(parents=True, exist_ok=True)
    metadata = {"schema": "whole-verdict-lrat-evaluation/v1",
                "scope": "Each SAT assignment satisfies the active clauses and assumption units. Each UNSAT answer has a checked LRAT proof. Java encoding, control flow, bounds and constant folding remain trusted."}
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        if args.group in ("core", "all"):
            first = core(out, work)
            lrat.save(out / ("core-summary.json" if args.group == "all" else "summary.json"), {**metadata, **first})
        if args.group in ("extensions", "all"):
            extra = extensions(out, work)
            summary = {**metadata, **extra}
            if args.group == "all":
                guava, additive = first["workloads"]
                summary.update(group="all", controls=first["controls"], workloads=[guava, *extra["workloads"], additive])
            lrat.save(out / "summary.json", summary)
        print(report(out))


if __name__ == "__main__":
    main()

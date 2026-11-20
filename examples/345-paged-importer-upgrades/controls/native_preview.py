"""Measure native byte-preview proofs on the application and byte-only clients' runtime classpaths."""

import json
import os
from pathlib import Path
import resource
import tempfile
import time

from compose import EXAMPLE, Experiment, digest, jar_classes, runtime

SCENARIOS = (
    ("cold", "parent", "parent", 0),
    ("unchanged", "parent", "parent", 0),
    ("io-only", "fix", "parent", 0),
    ("csv-only", "parent", "fix", 0),
    ("unused-only", "parent", "parent", 1),
    ("both-fixes", "fix", "fix", 0),
)
GUARD = "code >= 0 && code < 96"
ASSERT = "result == 1"


def checked(experiment, exe, adapter, paths, work, out):
    work.mkdir()
    out.mkdir()
    argv = [exe, "prove", "importer.Projection#bytes(int)", "--classes", adapter]
    for path in paths:
        argv += ["--classpath", path]
    argv += [
        "--assume",
        GUARD,
        "--assert",
        ASSERT,
        "--unwind",
        "96",
        "--max-array-length",
        "96",
        "--engine",
        "native",
        "--gaps",
        "strict",
        "--timeout",
        "90",
        "--work",
        work,
        "--json",
    ]
    usage = {}
    raw = out / "native.json"
    status, code, elapsed = runtime._run_one(
        list(map(str, argv)), work, raw, out / "stderr", 105, env=experiment.env, usage=usage
    )
    if status != "exited":
        raise ValueError("byte-preview checker " + status)
    (ans,) = json.loads(raw.read_text())
    stated = ans["stated"]
    if (
        ans["target"] != "importer.Projection#bytes(int)"
        or ans["assume"] != GUARD
        or ans["assert"] != ASSERT
        or stated["checker"]["engine"] != "native"
        or stated["gap_mode"] != "strict"
        or stated["bounds"]["unwind"] != 96
    ):
        raise ValueError("the byte proof describes a different claim")
    if ans["verdict"] == "verified" and ans["proof"] and code == 0 and stated["bounds"]["complete"]:
        answer = "established"
    elif ans["verdict"] == "violation" and (ans.get("replay") or {}).get("reproduced") and code == 1:
        answer = "refuted"
    else:
        raise ValueError(ans.get("problem") or ans["output"])
    inputs = (ans.get("counterexample") or {}).get("inputs", [])
    return {
        "status": answer,
        "selector": inputs[0]["value"] if inputs else None,
        "wallSeconds": elapsed,
        "peakRssBytes": usage.get("peakRssBytes"),
        "cpuSeconds": usage.get("cpuSeconds"),
        "rawSha256": runtime.sha256(raw),
        "raw": str(raw.relative_to(EXAMPLE)),
        "nativeSearchSeconds": (ans.get("search") or {}).get("seconds"),
        "assumptions": stated["assumptions"],
    }


def strategy(name, work, out, exe, catalog):
    started = time.monotonic()
    exp = Experiment(work, [], catalog)
    adapter = work / "projection"
    adapter.mkdir()
    recipe = runtime._fixture_recipe()
    compile_cp = [exp.app, *[exp.jars[k] for k in ("csv-fix", "io-api", "codec")]]
    exp.measured(
        "compile unchanged byte projection",
        [
            exp.home / "bin/javac",
            "--release",
            recipe["release"],
            "-encoding",
            "UTF-8",
            *recipe["flags"],
            "-implicit:none",
            "-d",
            adapter,
            "-cp",
            os.pathsep.join(map(str, compile_cp)),
            EXAMPLE / "adapter/importer/Projection.java",
        ],
    )
    adapter_classes = jar_classes(adapter)
    calibration = json.loads((EXAMPLE / "records/matrix/matrix.json").read_text())
    receipt = next((EXAMPLE / "records/finite-proofs").glob("*/bytes-fix-fix.json"))
    frozen = json.loads(receipt.read_text())["sides"]["fix-fix"]["entry"]["classSha256"]
    if adapter_classes["importer/Projection.class"] != frozen:
        raise ValueError("byte observation class differs from the frozen application")
    witness = work / "witness"
    witness.mkdir()
    source = witness / "ByteObservation.java"
    source.write_text(
        "public class ByteObservation { public static void main(String[] a) throws Exception {"
        "System.out.print(importer.Projection.bytes(Integer.parseInt(a[0]))); } }\n"
    )
    exp.compile("JVM witness", witness, [adapter, exp.app], [source])
    initial_prep = time.monotonic() - started
    prep_peak = max(p["peakRssBytes"] for p in exp.setup + exp.metrics)
    baseline = {}
    scenarios = []
    for scenario, io, csv, unused in SCENARIOS:
        t0 = time.monotonic()
        cell = io + "-" + csv
        paths = [exp.app, exp.jars["io-" + io]]
        if name == "full":
            paths.extend([exp.jars["csv-" + csv], exp.jars["codec"], exp.unused[unused]])
        closure = [
            {"role": "projection", "sha256": digest(adapter_classes)},
            {"role": "application", "sha256": digest(jar_classes(exp.app))},
        ]
        closure.extend({"role": "runtimeJar", "sha256": runtime.sha256(p)} for p in paths[1:])
        key = digest([exp.jdk["release"], runtime.sha256(exe), GUARD, ASSERT, 96, 96, closure])
        cached = baseline.get(key)
        if cached is None:
            proof = checked(
                exp, exe, adapter, paths, work / ("solve-" + scenario), out / (scenario + "-native")
            )
        else:
            proof = cached
        if scenario == "cold":
            baseline[key] = proof
        replay_seconds = 0
        replay_peak = 0
        if proof["status"] != ("refuted" if io == "parent" else "established"):
            raise ValueError("native byte answer contradicts full upstream calibration")
        if proof["status"] == "refuted":
            value = proof["selector"]
            if type(value) is not int or not 0 <= value < 96:
                raise ValueError("native selector is out of range")
            fixture = EXAMPLE / "records/matrix" / (cell + ".jsonl")
            if runtime.sha256(fixture) != calibration["configurations"][cell]["stdoutSha256"]:
                raise ValueError("JVM matrix changed")
            grid = [json.loads(line) for line in fixture.read_bytes().splitlines()]
            observed = grid[value]
            if (
                len(grid) != 96
                or observed["id"] != value
                or observed["adapter"]["bytes"] != 0
                or observed["direct"]["bytes"] == list(observed["input"]["doc"].encode("utf-8"))
            ):
                raise ValueError(
                    "the native counterexample disagrees with the clean original input and byte cursor"
                )
            cp = os.pathsep.join(map(str, [witness, adapter, *paths]))
            raw = exp.measured(
                "independent JVM witness",
                [exp.home / "bin/java", "-XX:-UsePerfData", "-cp", cp, "ByteObservation", str(value)],
            )
            if raw != b"0":
                raise ValueError("native witness failed on this runtime")
            replay_seconds = exp.metrics[-1]["wallSeconds"]
            replay_peak = exp.metrics[-1]["peakRssBytes"]
        wall = time.monotonic() - t0
        # The clean control is timed separately and is never supplied to the reuse strategy.
        separate = checked(
            exp, exe, adapter, paths, work / ("control-" + scenario), out / (scenario + "-clean-control")
        )
        if separate["status"] != proof["status"]:
            raise ValueError("fresh native proof disagreed with cached native evidence")
        scenarios.append(
            {
                "scenario": scenario,
                "cell": cell,
                "preparedClasspath": closure,
                "key": key,
                "cacheHit": cached is not None,
                "preparationSeconds": round(initial_prep if scenario == "cold" else 0, 6),
                "nativeSeconds": 0 if cached else proof["wallSeconds"],
                "independentReplaySeconds": replay_seconds,
                "endToEndSeconds": round(wall + (initial_prep if scenario == "cold" else 0), 6),
                "peakProcessRssBytes": max(
                    prep_peak if scenario == "cold" else 0,
                    0 if cached else proof["peakRssBytes"],
                    replay_peak,
                ),
                "coordinatorHighWaterBytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                "evidence": proof,
                "independentCleanRecomputation": separate,
            }
        )
    return scenarios


def main():
    exe = runtime.jvmcontract()
    if not exe:
        raise ValueError("no built jvmcontract")
    exe = Path(exe).resolve()
    catalog = json.loads((EXAMPLE / "controls/libraries.json").read_text())
    out = EXAMPLE / "records/native-preview"
    out.mkdir(parents=True, exist_ok=True)
    from targets import executions

    dest = out / executions.new_id(executions.now())
    dest.mkdir()
    report = {
        "schema": "native-preview-closure/v1",
        "jdk": runtime.runtime_jdk.identity(Path(runtime.runtime_jdk.home("21"))),
        "checker": {"sha256": runtime.sha256(exe), **runtime._verifier_build(exe)},
        "scope": "Byte preview on all 96 frozen selectors at unwind 96. Both clients compile identical application and projection classes. The byte-only process has exactly the selected IO dependency; the full process also has CSV, Codec and the unused-class control. Every comparison includes a separately timed clean native recomputation.",
        "cachePolicy": "Each scenario begins with only its strategy's cold parent/parent native evidence and matches all ordered class hashes, JDK, binary, guard, assertion and bounds. OS page cache is uncontrolled.",
    }
    with tempfile.TemporaryDirectory(prefix="native-preview-cost-") as temp:
        for name in ("full", "byte-only"):
            work = Path(temp) / name
            work.mkdir()
            (dest / name).mkdir()
            report[name] = strategy(name, work, dest / name, exe, catalog)
    for i in range(len(SCENARIOS)):
        if report["full"][i]["evidence"]["status"] != report["byte-only"][i]["evidence"]["status"]:
            raise ValueError("the two byte clients disagree")
    executions.save(dest / "result.json", report)
    print("Twelve native byte-preview dispositions matched clean recomputation.")


if __name__ == "__main__":
    main()

"""Repeat the two disclosed tokenizer callers against their locked questions and original release graphs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
import os
from pathlib import Path
import time

from packets import BASE, HERE
from history import OUTPUT, ROOT, benchmark, digest, encoded, scratch
from more_wire import prepare_pair
from release_cases import JDK, compile_java, javaenv
from stock_history import classpath
from wire_assurance import certify


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes())


def prepare(slot, work):
    folder = HERE / "references" / slot
    packet = BASE / slot / "packet"
    docket = HERE / "references.json"
    reference, = [r for r in read(docket)["pairs"] if r["slot"] == slot]
    matched = OUTPUT / "blind" / slot / "matched/comparison/results.json.gz"
    frozen = read(matched)
    if (digest(packet / "inputs.json") != reference["packetSha256"]
            or read(packet / "inputs.json") != frozen["inputPacket"]
            or digest(folder / "original-jvm.json") != reference["physicalSha256"]
            or digest(folder / "reference.json") != reference["referenceSha256"]
            or any(digest(folder / file) != sha for file, sha in reference["sources"].items())):
        raise ValueError(f"slot {slot}: original reference or release packet differs")
    graphs = [[packet / e["path"] for e in frozen["inputPacket"][side]] for side in ("old", "new")]
    cp, originals, env, pin = prepare_pair(work, [folder / "ReferenceAPI.java"], *graphs,
                                          [folder / "ReferencePair.java"], ordered=True)
    if pin != frozen["twoCopy"]:
        raise ValueError(f"slot {slot}: reconstructed class bytes or ordered providers differ")
    ids = {"twoCopy": pin, "inputs": frozen["inputPacket"], "sources": reference["sources"],
           "frozenComparisonSha256": digest(matched), "originalJvmSha256": reference["physicalSha256"],
           "docketSha256": digest(docket), "registered": reference["reference"]}
    return cp, originals, env, ids


def physical(work, cp, originals, env, bounds):
    runner = work / "replay"
    compile_java([HERE / "ReplayReference.java"], runner, originals, env)
    # The original bridges load each release through its own platform-parent class loader.
    # A fresh process per input also resets all static state. Compare the relocated harness on every input.
    os.environ.update({key: env[key] for key in ("WIRE_ORIGINAL_BEFORE", "WIRE_ORIGINAL_AFTER")})
    launches = {}
    for profile, paths in (("original", originals), ("relocated", cp)):
        args = [str(JDK / "bin/java"), "-XX:-UsePerfData", "-Xmx128m", "-ea",
                "-cp", classpath([runner, *paths]), "ReplayReference"]

        def replay(n):
            run = benchmark.measure([*args, str(n)], 30)
            if run["exit"] or run["killed"]:
                raise ValueError(f"{profile} at {n}: {run['stderr'][-1000:]}")
            row = list(map(int, run["stdout"].split()))
            if len(row) != 5 or row[0] != n:
                raise ValueError(f"{profile} at {n}: malformed observation")
            return row, run["cpuSeconds"], run["peakMB"]

        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows, cpu, peak = zip(*pool.map(replay, range(bounds[0], bounds[1] + 1)))
        launches[profile] = {"argvPrefix": args, "wallSeconds": round(time.monotonic() - started, 3),
                             "cpuSeconds": round(sum(cpu), 3), "maxProcessMiB": max(peak), "rows": rows}
    if launches["original"]["rows"] != launches["relocated"]["rows"]:
        raise ValueError("original and relocated public calls differ on the registered domain")
    return {"rowColumns": ["n", "old", "new", "oldControl", "newControl"], "checks": ["primary", "control", "!inverse"],
            "runnerSha256": digest(runner / "ReplayReference.class"),
            "originalGraphs": {k: env[k] for k in ("WIRE_ORIGINAL_BEFORE", "WIRE_ORIGINAL_AFTER")}, "launches": launches}


def symbolic(checker, cp, work, method, unwind, temperatures, physical_rows, require_decision):
    target = "ReferencePair#" + method
    case = {"kind": "property", "expected": "violation" if method == "inverse" else "verified"}
    results = []
    for label in temperatures:
        cmd = [str(checker), "prove", target, "--classes", str(cp[0]), "--classpath", classpath(cp[1:]),
               "--engine", "native", "--gaps", "strict", "--assert", "result", "--unwind", str(unwind),
               "--max-array-length", "8", "--timeout", "120", "--cache", str(work / "cache"),
               "--work", str(work / label), "--json"]
        run = benchmark.measure(cmd, 180)
        outcome = benchmark.outcome_of(case, run["stdout"])
        verdict = benchmark.classify(case, outcome, run)
        if benchmark.unreadable(case, outcome, run) or verdict["class"] not in ("correct", "unsupported"):
            raise ValueError(f"{target} {label}: {verdict}")
        if require_decision and verdict["class"] != "correct":
            raise ValueError(f"{target} {label}: expected a decision, got {verdict}")
        if "jdk-constructor:java.util.StringTokenizer." in (verdict.get("problem") or ""):
            raise ValueError(f"{target} {label}: still stops at tokenizer construction")
        record = {"temperature": label, "argv": cmd, "classification": verdict, **run}
        if verdict["verdict"] == "verified":
            stated = outcome["stated"]
            if (stated["vacuity"]["status"] != "non-vacuous" or not stated["bounds"]["complete"]
                    or stated["gap_mode"] != "strict"):
                raise ValueError(f"{target} {label}: incomplete or vacuous claim")
        if verdict["verdict"] == "violation":
            value, = outcome["counterexample"]["inputs"]
            n = value["value"]
            if value["type"] != "int" or type(n) is not int or n not in physical_rows or method != "inverse":
                raise ValueError(f"{target} {label}: witness outside the physically refuted inputs")
            record["originalWitnessRow"] = physical_rows[n]
        results.append(record)
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slot", choices=("08", "10"))
    ap.add_argument("--certify", action="store_true", help="independently check all solver answers of the glyph proof")
    args = ap.parse_args()
    if args.certify and args.slot != "08":
        ap.error("solver assurance requires the completed 08 primary")
    freeze = read(HERE.parent / "freeze.json")
    for path, key in (("lib/modules", "jdkModulesSha256"), ("bin/java", "jdkJavaSha256"), ("bin/javac", "jdkJavacSha256")):
        if digest(JDK / path) != freeze[key]:
            raise ValueError(f"selected JDK differs: {path}")
    os.environ.update(javaenv())
    checker = Path(os.environ.get("JVMCONTRACT", ROOT / "lib/target/release/jvmcontract")).resolve()
    out = OUTPUT / "followup"
    with scratch(prefix="tokenizer-followup-") as tmp:
        work = Path(tmp)
        cp, originals, env, ids = prepare(args.slot, work)
        if args.certify:
            os.environ["JVMCONTRACT"] = str(checker)
            certify("ReferencePair#primary", "ISCWT registered glyph", ids["registered"]["domain"],
                    out / "iscwt-assurance", work / "assurance", env, cp, ids)
            return
        observed = physical(work, cp, originals, env, ids["registered"]["bounds"])
        rows = {r[0]: r for r in observed["launches"]["original"]["rows"]}
        results = {m: symbolic(checker, cp, work / m, m, 16, ("cold", "warm"), rows, args.slot == "08")
                   for m in ("primary", "control", "inverse")}
        if args.slot == "10":
            results["primary-unwind-256"] = symbolic(checker, cp, work / "extended", "primary", 256, ("cold",), rows, False)
        report = {"phase": "post-freeze supplied caller", "slot": args.slot, "job": os.environ.get("VERIFY_JOB_ID"),
                  "sourceCommit": os.environ.get("VERIFY_SOURCE_COMMIT"), "checkerSha256": digest(checker),
                  "frozenCheckerSha256": freeze["checkerSha256"], "identity": ids, "physical": observed, "native": results}
        out.mkdir(parents=True, exist_ok=True)
        (out / f"tokenizer-{args.slot}.json.gz").write_bytes(gzip.compress(encoded(report), mtime=0))
        print(f"Slot {args.slot}: {len(rows)} inputs on both release profiles", flush=True)
        for name, runs in results.items():
            print(name, [r["classification"]["verdict"] for r in runs], flush=True)


if __name__ == "__main__":
    main()

"""Run the frozen construction and action search before loading the independent JGraphT auditor."""

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import tempfile

from callers import ASSETS, JDK, RESULTS, ROOT, read, sha
from investigate import command, native, write

HERE = ROOT / "lib/benchmark/receiver-discovery"
SUBJECT = "org.jgrapht.graph.DirectedAcyclicGraph"
EXPECTED = {"insert": 48, "duplicate": 48, "cycle": 54}


def check_files(pins):
    for path, digest in pins.items():
        if sha(ROOT / path) != digest:
            raise ValueError("changed frozen generator input: " + path)


def evaluate(lines):
    candidates = []
    for line in lines:
        fields = line.split("\t")
        if fields[0] == "candidate":
            row = {
                "entry": fields[1],
                "flags": int(fields[2]),
                "action": fields[3],
                "transitions": [],
                "mismatches": [],
                "missed": [],
            }
            candidates.append(row)
        elif fields[0] in ("setup-miss", "producer-miss"):
            if not candidates:
                candidates.append({"transitions": [], "mismatches": [], "missed": []})
            candidates[-1]["missed"].append(fields[1:])
        elif fields[0] == "transition":
            row["transitions"].append([int(fields[1]), int(fields[2]), fields[3]])
        elif fields[0] == "mismatch":
            row["mismatches"].append(fields[1:])
        elif fields[0] == "total" and int(fields[1]) != len(row["transitions"]):
            raise ValueError(line)
    for row in candidates:
        outcomes = Counter(
            "insert" if r == "true" else "duplicate" if r == "false" else r for _, _, r in row["transitions"]
        )
        row["outcomes"] = dict(outcomes)
        row["startingGraphs"] = len({m for m, _, _ in row["transitions"]})
        row["scopeMatched"] = (
            row["startingGraphs"] == 25
            and len(row["transitions"]) == 150
            and not row["mismatches"]
            and not row["missed"]
        )
    return candidates


def run(tmp, checker, folder, evaluate_native):
    freeze = read(RESULTS / "action-freeze.json")
    check_files(freeze["driver"])
    producer_freeze = RESULTS / "generator-freeze.json"
    if sha(producer_freeze) != freeze["receiverFreezeSha256"]:
        raise ValueError("producer freeze mismatch")
    check_files(read(producer_freeze)["sources"])
    libs = list(
        map(
            Path, (ASSETS / "releases/jgrapht-core-1.5.2/classpath.txt").read_text().strip().split(os.pathsep)
        )
    )
    catalog = read(folder / "controls/libraries.json")
    if [sha(p) for p in libs] != [v["sha256"] for v in catalog.values()]:
        raise ValueError("release classpath differs")
    base, gen, driver, audit = [tmp / n for n in ("capture", "generated", "driver", "audit")]
    for p in (base, driver, audit):
        p.mkdir()
    classpath = lambda paths: os.pathsep.join(map(str, paths))
    javac = [JDK / "bin/javac", "-proc:none", "-g", "-parameters"]
    java = [JDK / "bin/java", "-Xverify:all", "-ea"]
    command([*javac, "-cp", classpath(libs), "-d", base, folder / "original/GraphSink.java"])
    command([*javac, "-d", driver, HERE / "history/ActionCensus.java"])
    env = dict(os.environ, JAVA_HOME=str(JDK), JVMCONTRACT_JAR_RELEASE="21")
    options = [s for p in [base, *libs] for s in ("--classes", p)]
    plans = json.loads(
        command(
            [
                checker,
                "construct",
                SUBJECT,
                "--observer",
                "GraphSink#capture",
                "--output",
                gen,
                "--null-collaborators",
                *options,
            ],
            env=env,
        )
    )
    bounds = freeze["boundsForHoldout"]

    def search(plan, audited):
        args = [
            "ActionCensus",
            SUBJECT,
            "addEdge",
            plan["entry"],
            "GraphSink#captured",
            str(bounds["atoms"]),
            str(bounds["priorActions"]),
        ]
        cp = [gen, driver, base, *libs]
        if audited:
            args.append("GraphAudit")
            cp.append(audit)
        return command([*java, "-cp", classpath(cp), *args], timeout=90).splitlines()

    # Finish every discovery invocation before compiling or loading the audit.
    raw = {p["entry"]: search(p, False) for p in plans["plans"]}
    command(
        [
            *javac,
            "-cp",
            classpath([driver, *libs]),
            "-d",
            audit,
            *sorted((folder / "evaluation").glob("*.java")),
            folder / "original/GraphHistory.java",
        ]
    )
    reports = []
    for plan in plans["plans"]:
        lines = search(plan, True)
        if [v for v in lines if not v.startswith("mismatch\t")] != raw[plan["entry"]]:
            raise ValueError("auditor changed public action outcomes")
        reports.extend({"producer": plan["producer"], **r} for r in evaluate(lines))
    oracle = command([*java, "-cp", classpath([audit, *libs]), "DagCensus"]).splitlines()
    if (
        not oracle
        or oracle[0] != "graphs=25 transitions=150 insert=48 duplicate=48 cycle=54 oracleMismatches=0"
    ):
        raise ValueError(oracle)
    if (
        len(oracle) != 2
        or "unregistered source: returned false" not in oracle[1]
        or "fresh edge, unregistered source: threw IllegalArgumentException" not in oracle[1]
        or "null edge, valid endpoints: threw NullPointerException" not in oracle[1]
    ):
        raise ValueError(oracle)
    qualified = {(m, i, r) for c in reports if c["scopeMatched"] for m, i, r in c["transitions"]}
    counts = Counter(
        "insert" if r == "true" else "duplicate" if r == "false" else "cycle" for _, _, r in qualified
    )
    if qualified and dict(counts) != EXPECTED:
        raise ValueError(counts)
    result = {
        "job": os.environ.get("VERIFY_JOB_ID"),
        "source": os.environ.get("VERIFY_SOURCE_COMMIT"),
        "checkerSha256": sha(checker),
        "jdkModulesSha256": sha(JDK / "lib/modules"),
        "producerFreeze": sha(producer_freeze),
        "actionFreeze": sha(RESULTS / "action-freeze.json"),
        "release": catalog,
        "construction": plans,
        "automatic": reports,
        "evaluatorJvm": oracle,
        "coveredGraphs": len({m for m, _, _ in qualified}),
        "coveredTransitions": len(qualified),
        "outcomes": dict(counts),
    }
    if evaluate_native:
        result["strictIdentityControl"] = native(
            checker,
            [audit, *libs],
            "GraphHistory#identities",
            "selection >= 0 && selection < 3",
            24,
            16,
            60,
            tmp / "native",
        )
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checker", type=Path, default=os.environ.get("JVMCONTRACT"))
    p.add_argument("--example", type=Path, default=next((ROOT / "examples").glob("399-*"), None))
    p.add_argument("--output", type=Path, default=RESULTS / "transfer/jgrapht")
    p.add_argument("--jvm-only", action="store_true")
    a = p.parse_args()
    with tempfile.TemporaryDirectory() as d:
        result = run(Path(d), a.checker.resolve(), a.example, not a.jvm_only)
    a.output.mkdir(parents=True, exist_ok=True)
    write(a.output / "measurement.json", result)
    print(result["coveredGraphs"], result["coveredTransitions"], result["outcomes"])

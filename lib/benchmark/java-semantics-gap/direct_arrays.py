"""Recheck the five frozen array claims and exercise two direct aliases on the original JVM."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path
import tarfile
import tempfile

from campaign import CLAIMS, ROOT, compile_java, digest, integrated, javaenv, jvm_controls, measure, write
from subjects import Claim, Subject

BASE = ROOT / "verification/java-semantics-gap"
PHASE = "direct-arrays"
EXAMPLE = ROOT / "examples/379-nullable-reference-arrays"
PARAM = "ReferenceCells.Item[] values"
SAME = ("DirectCellsReplay.pair(true, Integer.MAX_VALUE)",)
DISTINCT = ("DirectCellsReplay.pair(false, Integer.MAX_VALUE)",)
EMPTY = (("null",), ("new ReferenceCells.Item[0]",), ("new ReferenceCells.Item[2]",))
HISTORIES = Subject(379, "DirectArrayHistories", "jdk", (
    Claim("tracksIdentity", PARAM, holds=(*EMPTY, SAME, DISTINCT,
          ("DirectCellsReplay.pair(true, 0)",), ("DirectCellsReplay.pair(false, -1)",)), nullable="values"),
    Claim("alwaysWritesSecond", PARAM, holds=(*EMPTY, SAME), fails=(DISTINCT,), nullable="values"),
    Claim("neverWritesSecond", PARAM, holds=(*EMPTY, DISTINCT), fails=(SAME,), nullable="values"),
), 2)


def check_run(row):
    if row["disposition"] != "correct" or row["expected"] != row["verdict"]:
        raise ValueError(f'{row["method"]}: {row["disposition"]} ({row["verdict"]})')
    if row["verdict"] == "verified":
        if row["stated"]["vacuity"]["status"] != "non-vacuous" or not row["stated"]["bounds"]["complete"]:
            raise ValueError("unqualified array proof")
    elif row["jvmReplay"]["outcome"] != "refuted" or row["jvmReplay"]["exit"] != 0:
        raise ValueError("array counterexample did not reproduce on the original JVM")


def check_cells(runs):
    first = {"fields": {"value": 2147483647}}
    for row in runs:
        check_run(row)
        if row["method"] in ("alwaysWritesSecond", "neverWritesSecond"):
            cells = row["jvmReplay"]["inputs"][0]["value"]
            expected = [first, first if row["method"] == "alwaysWritesSecond" else {"sameCell": 0}]
            if cells != expected:
                raise ValueError(f'{row["method"]}: wrong initial identities or field values')


def unchanged_inputs(key, current):
    previous = json.loads((BASE / "qualified" / key / "measurement.json").read_bytes())
    for field in ("scope", "claimsSha256", "adapterSha256", "classes", "classpath", "jvmSha256",
                  "modulesSha256", "jbmcSha256", "packagedModelsSha256", "originalJvm"):
        if current[field] != previous[field]:
            raise ValueError(f"{key}: frozen {field} changed")
    return previous


def controls():
    for key in CLAIMS:
        if key == "arrays":
            continue
        report = measure(key, PHASE, ["native"], BASE)
        previous = unchanged_inputs(key, report)
        baseline = {r["method"]: r for r in previous["runs"] if r["engine"] == "native"}
        for row in report["runs"]:
            if baseline[row["method"]]["disposition"] == "correct" or row["verdict"] in ("verified", "violation"):
                check_run(row)


def main():
    frozen = measure("arrays", PHASE, ["native", "jbmc"], BASE)
    unchanged_inputs("arrays", frozen)
    for row in frozen["runs"]:
        if row["engine"] == "native":
            check_run(row)
    src = EXAMPLE / "controls/DirectArrayHistories.java"
    dest = BASE / PHASE / "histories"
    dest.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="direct-arrays-") as tmp:
        work = Path(tmp)
        cp = [work / "classes"]
        env = javaenv()
        compile_java([EXAMPLE / "adapter/ReferenceCells/ReferenceCells.java", src], cp[0], [], env)
        for name, sha in frozen["classes"].items():
            if digest(cp[0] / name) != sha:
                raise ValueError(f"histories changed the original {name}")
        report = {k: frozen[k] for k in ("job", "source", "checkerSha256", "jvmSha256", "modulesSha256", "classpath")}
        report.update(scope=asdict(HISTORIES), sourceSha256=digest(src),
                      classes={p.name: digest(p) for p in sorted(cp[0].glob("*.class"))},
                      originalJvm=jvm_controls(HISTORIES, work, cp, env), runs=[])
        for claim in HISTORIES.claims:
            scratch = work / claim.method
            raw = work / "raw" / claim.method
            scratch.mkdir()
            raw.mkdir(parents=True)
            row = integrated(HISTORIES, claim, "native", scratch, raw, cp, env)
            report["runs"].append(dict(method=claim.method, **row))
        check_cells(report["runs"])
        with tarfile.open(dest / "raw.tar.gz", "w:gz") as archive:
            archive.add(work / "raw", arcname="raw")
        report["rawSha256"] = digest(dest / "raw.tar.gz")
        write(dest / "measurement.json", report)
    print("Five frozen native decisions and three direct mutation histories qualified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controls", action="store_true", help="remeasure the other 55 frozen native claims")
    if parser.parse_args().controls:
        controls()
    else:
        main()

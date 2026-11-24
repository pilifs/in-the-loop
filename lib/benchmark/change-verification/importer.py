"""Grade the frozen example-345 claims against fresh JVMs for every deployment and update."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EXAMPLE = ROOT / "examples/345-paged-importer-upgrades"
sys.path.insert(0, str(ROOT / "examples/tools"))
sys.path.insert(0, str(EXAMPLE / "controls"))
import calibrate
import compose
from targets import change_evidence, change_plan, runtime_jdk, upgrade_replay


def run(work):
    fixture = work / "example"
    fixture.mkdir()
    for name in ("client", "driver", "adapter", "controls"):
        (fixture / name).symlink_to(EXAMPLE / name, target_is_directory=True)
    compiled = work / "compiled"
    compiled.mkdir()
    measured = calibrate.measure(compiled, fixture)
    cells = measured["configurations"]
    clean = {}
    for name, cell in cells.items():
        raw = fixture / "records/matrix" / (name + ".jsonl")
        historical = EXAMPLE / "records/matrix" / raw.name
        if cell["stdoutSha256"] != upgrade_replay.sha(historical):
            raise ValueError(f"{name}: fresh JVM differs from the frozen observation stream")
        rows = {}
        for row in map(json.loads, raw.read_bytes().splitlines()):
            values = row["direct"]
            rows[row["id"]] = {**values, "bytes": bytes(values["bytes"]).hex()}
        clean[name] = compose.digest(rows)

    table = json.loads((EXAMPLE / "controls/table.json").read_text())["cases"]
    libraries = json.loads((EXAMPLE / "controls/libraries.json").read_text())
    strategies = {}
    for strategy in ("inline", "composed"):
        where = work / strategy
        where.mkdir()
        updates, _ = compose.execute(where, strategy, libraries, table)
        for update in updates:
            cell = "-".join(update["cell"])
            if (update["outcomes"]["allRowsSha256"] != clean[cell] or
                    update["outcomes"]["differences"] != cells[cell]["mismatches"]):
                raise ValueError(f"{strategy} differs from the fresh JVM for {cell}")
            update["cpuSeconds"] = round(sum(p["cpuSeconds"] for p in update.pop("phases")), 4)
        strategies[strategy] = updates

    precedence = {}
    java = Path(runtime_jdk.home(21)) / "bin/java"
    for order, cell in ((["io-parent", "io-fix", "csv-fix", "csv-parent"], "parent-fix"),
                        (["io-fix", "io-parent", "csv-parent", "csv-fix"], "fix-parent")):
        jars = [compiled / (name + ".jar") for name in [*order, "codec"]]
        cp = os.pathsep.join(map(str, [compiled / "classes", *jars]))
        output = subprocess.check_output([java, "-XX:-UsePerfData", "-cp", cp, "importer.ImportCases"], timeout=15)
        if output != (fixture / "records/matrix" / (cell + ".jsonl")).read_bytes():
            raise ValueError("shadowed deployment differs from its clean reference")
        precedence[cell] = {"jars": order, "orderedClasspath": [upgrade_replay.sha(j) for j in jars],
                            "freshOutputSha256": cells[cell]["stdoutSha256"], "inputs": len(table)}

    plan = change_plan.example_plan(345)
    claims = []
    for node in plan["claims"]:
        field, cell = node["id"].split("-", 1)
        total = cells[cell]["positiveControls"] if field == "positive" else cells[cell]["inputs"]
        wrong = 0 if field == "positive" else cells[cell]["mismatches"][field]
        status = "refuted" if wrong else "established"
        if status != node["status"] or not any(r["status"] == status for r in node["nativeSelectors"]):
            raise ValueError(f"{node['id']}: independent clean verdict disagrees with the qualified native result")
        proofs = []
        for route, path_key in (("finiteJvm", "receipt"), ("nativeSelectors", "record")):
            for result in node[route]:
                receipt = (EXAMPLE / result[path_key]).resolve()
                proofs.append({"route": route, "status": result["status"], "path": receipt.relative_to(ROOT).as_posix(),
                               "sha256": upgrade_replay.sha(receipt)})
        claims.append({"id": node["id"], "claimKey": node["claimKey"], "entry": node["entry"], "configuration": cell,
                       "cohort": "control" if field == "positive" else "primary", "inputs": total, "disagreements": wrong,
                       "status": status, "monolithic": node["monolithic"], "attempt": (node["attempt"] or {}).get("status"),
                       "receipts": proofs})
    if len(claims) != 16 or sum(c["cohort"] == "primary" for c in claims) != 12:
        raise ValueError("the frozen importer denominator changed")
    return {"schema": "importer-change-evaluation/v1", "change": plan["change"], "scope": "96 frozen importer inputs, 24 in each positive-control subset",
            "claims": claims, "jdk": measured["jdk"]["release"], "clientClasses": measured["clientClasses"],
            "configurations": cells, "incremental": strategies, "classpathPrecedence": precedence,
            "interactionWitness": {c: r["example"] for c, r in cells.items()}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="change-importer-") as directory:
        result = run(Path(directory))
    change_evidence.write_json(args.output, result)
    print("12 primary claims and four controls reproduced on all four original configurations")

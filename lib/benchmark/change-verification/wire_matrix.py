"""Run the public Retrofit callers and compare each resumed result to a clean recomputation."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets import change_evidence, change_inventory, runtime, upgrade_replay

SETUP = Path.home() / ".cache/in-the-loop/change-verification"
HISTORY = ROOT / "verification/external-upgrades/corpus-runs"
GRADING = {"response": HISTORY / "v3-final-finite/01/compsuite-i-1.json",
           "request": HISTORY / "operational/01/compsuite-i-1.json"}
PINS = {"old": "b8d593cf029652eb682434c0217ad92b5cbb005e", "new": "577716be23b960fe24b31b1edcdf6b01e88a692e"}
SUBJECT = "retrofit-converters/wire/src"
J8 = Path.home() / ".sdkman/candidates/java/8.0.512.0+9-tem"


def read(file):
    return json.loads(file.read_text())


def prepare(setup):
    manifests, operands = {}, {}
    for side, pin in PINS.items():
        subject = setup / "src" / ("retrofit-" + side)
        actual = subprocess.check_output(["git", "-C", subject, "rev-parse", "HEAD"], text=True).strip()
        if actual != pin:
            raise ValueError(f"wrong {side} checkout")
        built = setup / "retrofit" / side
        for row in (built / "files.sha256").read_text().splitlines():
            checksum, name = row.split(None, 1)
            if upgrade_replay.sha(built / name) != checksum:
                raise ValueError(f"changed {side} build input {name}")
        source = subject / SUBJECT / "main"
        unit = {"commit": pin, "sourceSha256": change_inventory.file_digest(source),
                "scope": "complete Maven wire converter module", "operandScope": "runtime",
                "modulePomSha256": upgrade_replay.sha(source.parents[1] / "pom.xml"),
                "jdkReleaseSha256": upgrade_replay.sha(J8 / "release")}
        for kind in ("runtime", "test"):
            files = [Path(n) for n in (built / (kind + ".cp")).read_text().strip().split(os.pathsep)]
            cp = [{"file": str(f), "sha256": change_inventory.file_digest(f)} for f in files]
            manifests[side, kind] = {**unit, "classpath": cp}
            if kind == "runtime":
                [operand] = [r for r in cp if Path(r["file"]).name.startswith("wire-runtime-")]
                operands[side] = operand["sha256"]
    return manifests, operands


def adjudicated(plan):
    return {n["id"]: {"claimKey": n["claimKey"], "entry": n["entry"], "status": n["status"],
                      "inputs": n["inputs"], "covered": n["covered"], "assumptions": n["assumptions"],
                      "observations": n["children"]} for n in plan["claims"]}


def run(setup, dest, work, *, baseline_only=False):
    from copy import deepcopy

    originals, operands = prepare(setup)
    fixtures = setup / "src/retrofit-old" / SUBJECT / "test/java/retrofit2/converter/wire"
    cache = work / "cache"
    options = ["--old-dependency", operands["old"], "--new-dependency", operands["new"],
               "--jdk", str(J8), "--workflows", str(HERE / "wire-workflows.json"), "--fixtures", str(fixtures),
               "--checker", os.environ.get("JVMCONTRACT", str(ROOT / "lib/target/release/jvmcontract")), "--run"]
    dest.mkdir(parents=True, exist_ok=True)
    provider = setup / "m2/com/squareup/okio/okio/2.4.1/okio-2.4.1.jar"
    modern = {"file": str(provider), "sha256": upgrade_replay.sha(provider)}
    if modern["sha256"] != "8b3ca9c9fb516ab2623bb4a3cfef0a5fa8580188eed9127cdefc1a0088d1fa7e":
        raise ValueError("wrong alternate Okio artifact")
    matrix = []
    baseline_plan = None
    scenarios = ["cold"] if baseline_only else ["cold", "exact", "test-only edit", "runtime resource", "old provider first", "new provider first"]
    for scenario in scenarios:
        area = work / scenario.replace(" ", "-")
        area.mkdir()
        manifests = deepcopy(originals)
        if scenario == "test-only edit":
            jar = area / "test-only.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr(zipfile.ZipInfo("test-only.properties"), "test.label=revised\n")
            manifests["new", "test"]["classpath"].append({"file": str(jar), "sha256": upgrade_replay.sha(jar)})
        if scenario == "runtime resource":
            jar = area / "wire-resource.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr(zipfile.ZipInfo("deployment.properties"), "mode=caller-control\n")
            manifests["new", "runtime"]["classpath"].append({"file": str(jar), "sha256": upgrade_replay.sha(jar)})
        if scenario.endswith("provider first"):
            graph = manifests["new", "runtime"]["classpath"]
            i = next(i for i, r in enumerate(graph) if Path(r["file"]).name == "okio-1.15.0.jar")
            graph.insert(i + (scenario == "old provider first"), modern)
        flags = []
        for (side, kind), manifest in manifests.items():
            path = area / (side + "-" + kind + ".json")
            change_evidence.write_json(path, manifest)
            flag = "--" + {"old": "before", "new": "after"}[side] + ("-test" if kind == "test" else "")
            flags.extend([flag, str(path)])
        def launch(label, extra):
            output = area / label / "plan.json"
            metrics = {}
            cmd = [sys.executable,
                   str(ROOT / "examples/tools/build.py"), "--change-plan", "upgrade", *flags, *options,
                   "--output", str(output), *extra]
            error = area / (label + ".err")
            state, code, wall = runtime._run_one(cmd, ROOT, area / (label + ".out"), error, 150, usage=metrics)
            if state != "exited" or code:
                raise ValueError(f"{scenario}, {label}: {state} {code}: {error.read_text()[-600:]}")
            return read(output), {"wallSeconds": wall, **metrics}, output

        run_args = ["--cache", str(cache)]
        if baseline_plan:
            run_args.extend(["--previous", str(baseline_plan)])
        inc, cost, planfile = launch("resumed", run_args)
        if scenario == "cold":
            baseline_plan = planfile
            independent = {}
            for n in inc["claims"]:
                receipt = planfile.parent / n["receipt"]["path"]
                dest_receipt = dest / (n["id"] + ".json")
                shutil.copyfile(receipt, dest_receipt)
                independent[n["id"]] = {"path": dest_receipt.name, "sha256": upgrade_replay.sha(dest_receipt)}
        clean, clean_cost, _ = launch("clean", [])
        verdicts = adjudicated(inc)
        if verdicts != adjudicated(clean):
            raise ValueError(f"{scenario}: incremental scopes or original observations differ from clean")
        expected = {"response": "established", "request": "established" if scenario == "new provider first" else "refuted"}
        if {k: v["status"] for k, v in verdicts.items()} != expected or any(v["covered"] != 2 for v in verdicts.values()):
            raise ValueError(f"{scenario}: wrong finite caller result")
        actions = {n["id"]: {s: d["action"] for s, d in n["execution"].items()} for n in inc["claims"]}
        if scenario in ("exact", "test-only edit") and (actions["response"]["new"] != "exact reuse" or actions["request"]["new"] != "executed"):
            raise ValueError("eligible reads must be reused and a divergent write replayed")
        if scenario not in ("cold", "exact", "test-only edit") and any(a["new"] != "executed" for a in actions.values()):
            raise ValueError("a changed production deployment reused an inapplicable result")
        if scenario != "cold" and any(a["old"] != "exact reuse" for a in actions.values()):
            raise ValueError("unchanged positive old-side trials were repeated")
        matrix.append({"scenario": scenario, "actions": actions, "outcomes": verdicts, "incremental": cost, "clean": clean_cost,
                       "cleanEquivalent": True, "launches": {s: {k: inc["launches"][s][k]["key"] for k in ("production", "test")} for s in PINS},
                       "preparationSeconds": inc["preparationSeconds"], "delta": inc.get("delta")})
    # Grade only after the inventory and real public-entry executions.
    cold = read(baseline_plan)
    discovered = {c["entry"] for c in cold["inventory"]["candidates"] if c["independentlyDiscovered"]}
    grading = {}
    for node in cold["claims"]:
        original = GRADING[node["id"]]
        record = read(original)
        matches = node["entry"] in discovered
        typed = all(all(record["sides"][s]["trials"][c["input"]]["observations"] == [c[s], c[s]]
                        for s in ("old", "new")) for c in node["children"])
        grading[node["id"]] = {"independentlyDiscovered": matches, "record": str(original.relative_to(ROOT)),
                               "sha256": upgrade_replay.sha(original), "matchesHistoricalInputs": record["cases"] == node["domain"],
                               "matchesHistoricalOutcomes": typed}
        if not matches or record["entry"] != node["entry"] or not grading[node["id"]]["matchesHistoricalInputs"] or not typed:
            raise ValueError(f"{node['id']}: discovery miss or different historical caller, domain or typed observation")
    return {"schema": "wire-change-evaluation/v1", "change": cold["change"], "cohorts": cold["counts"],
            "scope": "Two registered phone values per direction on each JDK 8 deployment. Alternate Okio precedence is an attribution control.",
            "inventory": cold["inventory"], "launches": {s: {k: cold["launches"][s][k] for k in ("production", "test")} for s in PINS},
            "claims": [{k: n[k] for k in ("id","cohort","claimKey","statement","domain","assumptions")} for n in cold["claims"]],
            "grading": grading, "receipts": independent, "matrix": matrix}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", type=Path, default=SETUP)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-only", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="change-wire-") as work:
        value = run(args.setup.resolve(), args.output.parent, Path(work), baseline_only=args.baseline_only)
        change_evidence.write_json(args.output, value)
    print(f"clean-equivalent Wire configurations: {len(value['matrix'])}")

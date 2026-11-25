"""Measure a registered successor question using the frozen product and the original released deployments."""
import argparse
import os
from pathlib import Path
import subprocess
import zipfile

from evaluate_panel import matched_namespace, measure_automatic
from history import JBMC, MODELS, ROOT
from resource_transfer import discover_packet
from successor import AREA, JDK, OUT, REFS, SLOTS, compressed, digest, draw, packet, read, save, scratch


def frozen():
    selection = read(OUT / "selection.json")
    file = OUT.parent / "scaffold-first/successor-freeze.json"
    if digest(file) != selection["policySha256"]:
        raise ValueError("different successor freeze")
    policy = read(file)
    root = Path(os.environ.get("VERIFY_RUNNER_ROOT", ROOT))
    candidate = root / "verification/.state/tools/jvmcontract" / selection["checkerLibTree"] / "jvmcontract"
    checker = Path(os.environ.get("BEYOND_JBMC_SUCCESSOR_CHECKER", candidate))
    for path, wanted in ((checker, policy["checkerSha256"]), (JDK / "lib/modules", policy["jdkModulesSha256"]),
                         (JBMC, policy["jbmcSha256"]), (MODELS, policy["modelsSha256"])):
        if digest(path) != wanted:
            raise ValueError("a frozen tool no longer matches " + path.name)
    return checker, policy


def registration(slot):
    ref = REFS / slot
    docket = OUT / "scaffolds" / (slot + ".json.gz")
    physical = compressed(docket)
    for key, path in (("question", ref / "reference.json"), ("callerSource", ref / "ReferenceAPI.java"),
                      ("pairSource", ref / "ReferencePair.java"), ("deployment", OUT / "deployments" / (slot + ".json.gz"))):
        if digest(path) != physical[key]:
            raise ValueError("the registered public caller, question or deployment changed")
    if physical["firstScaffoldStop"] is not None:
        raise ValueError(slot + " still has an open scaffolding stop")
    for index, side in enumerate(("old", "new")):
        expected = [[r[0], r[index+1], r[3]] for r in physical["expectedRows"]]
        for mode in ("direct", "record"):
            result = physical["sides"][side][mode]
            if result["exit"] or result["rows"] != expected or not expected:
                raise ValueError("original control or positive observation did not qualify")
    return ref, docket, physical


def resource_files(work, policy):
    root = Path(os.environ.get("VERIFY_RUNNER_ROOT", ROOT))
    revision = read(OUT / "selection.json")["operatorRevision"]
    targets = work / "frozen-targets"
    files = []
    for name, expected in policy["resourceSelector"].items():
        path = targets / Path(name).relative_to("examples/tools/targets")
        path.parent.mkdir(parents=True, exist_ok=True)
        data = subprocess.check_output(["git", "-C", root, "show", revision + ":" + name])
        path.write_bytes(data)
        if digest(path) != expected:
            raise ValueError("resource operator differs from its freeze")
        files.append(path)
    return targets, files


def run(lane, slot, checker, policy):
    ref, docket, physical = registration(slot)
    out = OUT / lane / slot
    out.mkdir(parents=True, exist_ok=True)
    with scratch(prefix="successor-measure-") as temp:
        work = Path(temp)
        inputs = work / "packet"
        packet(slot, inputs)
        packet_hash = digest(inputs / "inputs.json")
        record = {"slot": slot, "source": os.environ.get("VERIFY_SOURCE_COMMIT"), "job": os.environ.get("VERIFY_JOB_ID"),
                  "scaffoldSha256": digest(docket), "packetSha256": packet_hash, "checkerSha256": digest(checker)}
        if lane == "automatic":
            lock = {**policy, "operatorFiles": policy["originalSelector"]}
            store = AREA / "evaluation" / slot / ("automatic-" + lock["checkerSha256"])
            measure_automatic(slot, checker, lock, {"packetSha256": packet_hash}, inputs, out, store, docket)
            report = compressed(out / "report.json.gz")
            if (report.get("status") == "operator failure" or report["inputs"] != read(inputs / "inputs.json")
                    or report["rawSha256"] != digest(out / "executions.zip")):
                raise ValueError("incomplete automatic launch; preserve the first-attempt diagnostics")
            chosen = report["selected"]
            if len(chosen) != len(report["runs"]):
                raise ValueError("candidate dispositions are incomplete")
            directory = work / "resources"
            targets, files = resource_files(work, policy)
            discover_packet(inputs, directory, targets, files)
            discovery = read(directory / "discovery.json")
            if discovery["inputPacketSha256"] != packet_hash:
                raise ValueError("different resource-operator deployment")
            archive = out / "resource-discovery.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
                for artifact in sorted(directory.rglob("*")):
                    if artifact.is_file():
                        z.write(artifact, artifact.relative_to(directory))
            record.update(selected=len(chosen), resourceCandidates=discovery["candidates"], resourceArchiveSha256=digest(archive))
        else:
            # P_old(n) and P_new(n) use independent oracles and the identical compiled consumer.
            # Their conjunction at this input is exactly ReferencePair.primary(n).
            code = matched_namespace(inputs, ref, out, checker, False, "assisted_worker.py")
            state = read(out / "worker.json")
            if code or state.get("status") != "measured":
                raise ValueError("original-deployment comparison stopped before recording both sides")
            record["scope"] = "original-release conjuncts declared before solving"
            for side in ("old", "new"):
                measured = compressed(out / side / "results.json.gz")
                if (measured["primaryApiSha256"] != physical["callerClasses"]["ReferenceAPI.class"]
                        or measured["referenceSha256"] != physical["pairSource"]
                        or measured["checkerSha256"] != policy["checkerSha256"]
                        or [r["method"] for r in measured["rows"]] != ["primary","control","inverse"]
                        or measured["executionsSha256"] != digest(out / side / "executions.zip")):
                    raise ValueError("matched comparator lost an original binding or control")
        save(out / "measurement.json", record)
        print(slot, lane, "recorded", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("lane", choices=("automatic", "matched"))
    p.add_argument("slots", nargs="+", choices=SLOTS)
    args = p.parse_args()
    draw()
    exe, policy = frozen()
    for slot in args.slots:
        run(args.lane, slot, exe, policy)

"""Run a numbered draw slot behind immutable population, reference and prediction barriers."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from eligibility_inventory import HERE, digest, read, relative, write
from functional_scope import decision_hash, identity
from packet_view import ARMS, PreparationStop, export_checker, export_packet, export_product
from reference_rows import check_semantics, reviewed
from sandbox_runner import launch
from sealed_io import committed_input, pack_files
from trace_packets import add_trace_inputs, trace_summary


def filename(arm, index, phase, name):
    return HERE / "arms" / arm / f"{index:02d}" / phase / name


def blob(revision, path):
    if not revision:
        raise ValueError("a committed phase seal is required")
    try:
        return committed_input(revision, relative(path))
    except subprocess.CalledProcessError:
        raise ValueError("phase barrier is incomplete at the specified revision") from None


def at(revision, path):
    return json.loads(blob(revision, path))


def verify_predictions(revision, arm, draw):
    """All 20 attempts, including stops, must exist in one immutable Git tree."""
    records = []
    for index, row in enumerate(draw["cases"], 1):
        attempt = at(revision, filename(arm, index, "predict", "attempt.json"))
        if (attempt["schema"] != "blind-caller-attempt/v1" or attempt["phase"] != "predict"
                or attempt["arm"] != arm or attempt["url"] != row["url"] or attempt["index"] != index
                or attempt["producerRevision"] != draw["producerRevision"]
                or attempt["preregistration"] != draw["preregistration"]
                or attempt["status"] not in ("sealed", "preparation stop", "operator stop")):
            raise ValueError("prediction record belongs to a different arm, draw or producer")
        if attempt["status"] == "sealed":
            raw = blob(revision, filename(arm, index, "predict", "prediction.json"))
            if hashlib.sha256(raw).hexdigest() != attempt["predictionSha256"]:
                raise ValueError("prediction does not match its seal")
        records.append(attempt)
    return records


def verify_traces(revision, cold_seal, reference_seal, draw):
    records = []
    for index, row in enumerate(draw["cases"], 1):
        status = at(revision, filename("test-assisted", index, "trace", "attempt.json"))
        raw = blob(revision, filename("test-assisted", index, "trace", "trace.json"))
        if (status.get("phase") != "trace" or status["arm"] != "test-assisted" or status["index"] != index
                or status["url"] != row["url"] or status["referenceSeal"] != reference_seal or status["coldSeal"] != cold_seal
                or status["producerRevision"] != draw["producerRevision"] or hashlib.sha256(raw).hexdigest() != status.get("traceSha256")):
            raise ValueError("test-assisted arm is missing a committed, independently linked trace or source-only record")
        records.append((status, raw))
    return records


def validate_prediction(value, url, arm):
    if value.get("url") != url or value.get("arm") != arm or not isinstance(value.get("candidates"), list):
        raise ValueError("prediction does not identify its public input and ranked candidates")
    candidates = value["candidates"]
    if len(candidates) > 64 or value.get("primary") != (0 if candidates else None):
        raise ValueError("primary choice or candidate cap differs from the preregistration")
    for candidate in candidates:
        if not isinstance(candidate, dict) or not all(k in candidate for k in ("entry", "history", "fields", "inputs", "prediction")):
            raise ValueError("candidate lacks a registered prediction or public history")
    return len(candidates)


def material_index(packet, counts):
    spec = read(packet / "packet.json")
    names = {"packet.json", spec["productionDiff"], *(p["file"] for p in spec["productionSources"]),
             *(p["file"] for p in spec.get("publicDocumentation", [])),
             *(p["file"] for p in spec.get("upstreamTests", []))}
    if spec.get("testTrace"):
        names.add(spec["testTrace"]["file"])
    return {"counts": counts, "publicTitle": spec["title"], "visiblePRDescription": spec["description"],
            "testScope": spec.get("testScope"), "reviewed": spec.get("reviewed"), "jdkReleaseSha256": spec["jdkReleaseSha256"],
            "functionalReview": spec["functionalReview"], "approvedTestLaunches": spec.get("approvedTestLaunches", []),
            "testTraceAvailability": spec.get("testTraceAvailability"), "testTrace": spec.get("testTrace"),
            "deployments": spec["deployments"], "files": {name: digest(packet / name) for name in sorted(names)}}


def store_new(stage, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Keep incomplete output out of the repository. Both configured directories are on
    # the same filesystem; EXDEV leaves the result unsealed and is explicit to the caller.
    try:
        stage.rename(destination)
    except OSError:
        if not destination.is_dir() or not (destination / "attempt.json").is_file():
            raise
        if read(stage / "attempt.json") != read(destination / "attempt.json"):
            raise ValueError("a different immutable attempt already occupies this slot") from None


def run_one(index, phase, arm, reference_seal, cold_seal, prediction_seal, *, seconds, trace_seal=None):
    if phase == "trace" and arm != "test-assisted":
        raise ValueError("upstream traces are exclusive to the test-assisted diagnostic")
    draw = at(reference_seal, HERE / "draw.json")
    refs = at(reference_seal, HERE / "references.json")
    decisions = at(reference_seal, HERE / "functional-scope.json")
    scope_code_sha = hashlib.sha256(blob(reference_seal, HERE / "functional_scope.py")).hexdigest()
    size = len(draw["cases"])
    if not (1 <= index <= size) or size != 20:
        raise ValueError("a draw slot from 1 through 20 is required")
    if len(refs["references"]) != size or refs["producerRevision"] != draw["producerRevision"] or refs["preregistration"] != draw["preregistration"]:
        raise ValueError("references were not sealed for this entire draw and producer")
    require_match = (decisions.get("producerRevision"), decisions.get("preregistration")) == (draw["producerRevision"], draw["preregistration"])
    if not require_match:
        raise ValueError("functional scope comes from another producer freeze")
    for ordinal, (row, record, decision) in enumerate(zip(draw["cases"], refs["references"], decisions["cases"], strict=True), 1):
        if row["url"] != record["url"]:
            raise ValueError("reference and draw order differ")
        check_semantics(record)
        if (decision["index"] != ordinal or decision["identitySha256"] != identity(row)
                or decision["policySha256"] != scope_code_sha):
            raise ValueError("per-slot functional review is missing or belongs to another PR")
    prior = None
    trace_input = None
    if arm != "cold":
        verify_predictions(cold_seal, "cold", draw)
    if arm == "test-assisted" and phase != "trace":
        trace_input = verify_traces(trace_seal, cold_seal, reference_seal, draw)[index - 1]
    if phase == "measure":
        prior = verify_predictions(prediction_seal, arm, draw)[index - 1]
    row = draw["cases"][index - 1]
    ref = refs["references"][index - 1]
    decision = decisions["cases"][index - 1]
    registered = next(r for r in at(draw["preregistration"], HERE / "eligibility.json")["rows"] if r["number"] == row["number"])
    if not registered["eligible"] or registered["url"] != row["url"] or registered["pins"] != row["pins"]:
        raise ValueError("selected case fails its eligibility join")
    policy_ref = draw["producerFiles"][0]
    policy_bytes = committed_input(draw["producerRevision"], policy_ref["path"])
    if hashlib.sha256(policy_bytes).hexdigest() != policy_ref["sha256"]:
        raise ValueError("different frozen producer policy")
    policy = json.loads(policy_bytes)
    limit = policy[{"predict": "predictionSeconds", "measure": "measurementSeconds", "trace": "traceSeconds"}[phase]]
    if seconds is not None and seconds != limit:
        raise ValueError("requested time budget differs from the frozen producer policy")
    destination = filename(arm, index, phase, "attempt.json").parent
    if (destination / "attempt.json").is_file():
        old = read(destination / "attempt.json")
        if (old["producerRevision"], old["referenceSeal"], old["arm"], old["phase"], old["url"],
            old.get("predictionSeal"), old.get("coldSeal"), old.get("traceSeal")) != (draw["producerRevision"], reference_seal,
                    arm, phase, row["url"], prediction_seal, cold_seal, trace_seal):
            raise ValueError("this slot already holds a different attempt")
        return old["status"]
    with tempfile.TemporaryDirectory(prefix="caller-sealed-view-") as tmp:
        work = Path(tmp)
        stage = work / "receipt"
        stage.mkdir()
        attempt = {"schema": "blind-caller-attempt/v1", "index": index, "phase": phase, "arm": arm, "url": row["url"],
                   "producerRevision": draw["producerRevision"], "preregistration": draw["preregistration"],
                   "functionalDecisionSha256": decision_hash(decision),
                   "referenceSeal": reference_seal, "coldSeal": cold_seal, "predictionSeal": prediction_seal, "traceSeal": trace_seal}
        try:
            if not decision["permitted"] or ref["safetyAbstention"]:
                raise PreparationStop("scoped abstention: ordinary functionality was not affirmatively established")
            if prior is not None and prior["status"] != "sealed":
                raise PreparationStop("prediction stopped before a candidate was sealed")
            if prior is not None and prior["candidateCount"] == 0:
                raise PreparationStop("frozen prediction abstained from nominating a candidate")
            counts = export_packet(registered, arm, work / "view", decision=decision,
                                   registration=reviewed(ref) if arm == "reviewed" else None)
            packet_file = work / "view/packet.json"
            packet = read(packet_file)
            if phase == "trace":
                add_trace_inputs(work / "view", packet, registered, decision)
                write(packet_file, packet)
            elif trace_input:
                trace_attempt, raw = trace_input
                (work / "view/trace.json").write_bytes(raw)
                packet["testTrace"] = {"file": "trace.json", "sha256": trace_attempt["traceSha256"],
                                       "status": trace_attempt["status"]}
                write(packet_file, packet)
            export_product(draw["producerRevision"], policy["sourceFiles"], work / "product")
            if phase != "predict":
                export_checker(policy["checkerSha256"], work / "product")
            view = material_index(work / "view", counts)
            write(stage / "view.json", view)
            attempt["viewSha256"] = digest(stage / "view.json")
            if phase == "trace" and not packet["approvedTestLaunches"]:
                attempt["availability"] = packet["testTraceAvailability"]
                raise PreparationStop("source-only: no independently approved unit method with a complete original runtime")
            if prior and attempt["viewSha256"] != prior["viewSha256"]:
                raise PreparationStop("deployment or visible material changed since prediction")
            sentinel = work / "evaluator-only"
            sentinel.write_bytes(os.urandom(32))
            sealed = None
            if prior:
                sealed = work / "sealed"
                sealed.mkdir()
                (sealed / "prediction.json").write_bytes(blob(prediction_seal, filename(arm, index, "predict", "prediction.json")))
                attempt["predictionSha256"] = prior["predictionSha256"]
            jdk = Path(read(work / "view/packet.json")["jdk"])
            out, boundary = launch(phase, work / "product", work / "view", work / "scratch", jdk, sentinel,
                                   sealed=sealed, seconds=limit)
            attempt["boundary"] = boundary
            if not boundary["landlockSentinelDenied"] or not boundary["networkDenied"]:
                raise ValueError("worker isolation did not pass its independent controls")
            if phase == "predict" and not boundary["predictionSubprocessDenied"]:
                raise ValueError("prediction subprocess barrier failed")
            stopped = boundary["exitCode"] or boundary["timedOut"]
            if phase == "trace":
                trace = out / "trace.json"
                if trace.is_file() and isinstance(read(trace), dict):
                    pack_files(out, stage / "artifacts.zip")
                    attempt["traceCounts"] = trace_summary(work / "view", packet, out)
                    shutil.copyfile(trace, stage / "trace.json")
                    counts = attempt["traceCounts"]
                    status = "bound original test trace" if counts["boundTraceRuns"] else "original test coverage gap" if counts["parityRuns"] else "source-only"
                    attempt.update(status=status, availability=packet["testTraceAvailability"], workerEndedEarly=bool(stopped))
                else:
                    attempt.update(status="source-only", reason="original vetted trace did not return a trace receipt",
                                   availability=packet["testTraceAvailability"])
            elif stopped and (phase == "predict" or not (out / "measurement.json").is_file()):
                attempt.update(status="operator stop", stoppedAt="candidate" if phase == "predict" else "generated and old-API compiled caller",
                               reason="worker exceeded its time limit" if boundary["timedOut"] else f"worker exited {boundary['exitCode']}")
                if phase == "measure":
                    # Preserve complete per-candidate receipts even if the worker stopped
                    # before publishing its aggregate record. They do not earn implicit credit.
                    pack_files(out, stage / "artifacts.zip")
            elif phase == "predict":
                path = out / "prediction.json"
                if not path.is_file():
                    raise ValueError("worker produced no prediction record")
                attempt["candidateCount"] = validate_prediction(read(path), row["url"], arm)
                attempt["predictionSha256"] = digest(path)
                shutil.copyfile(path, stage / path.name)
                attempt["status"] = "sealed"
            else:
                path = out / "measurement.json"
                if not path.is_file() or read(path).get("predictionSha256") != prior["predictionSha256"]:
                    raise ValueError("measurement did not bind the sealed prediction bytes")
                pack_files(out, stage / "artifacts.zip")
                shutil.copyfile(path, stage / path.name)
                attempt["measurementSha256"] = digest(path)
                attempt["status"] = "partial measurement" if stopped else "measured"
                if stopped:
                    attempt.update(stoppedAt="required-side reach", reason="worker exceeded its time limit" if boundary["timedOut"]
                                   else f"worker exited {boundary['exitCode']}")
        except PreparationStop as error:
            attempt.update(status="preparation stop", reason=str(error), stoppedAt="deployment" if not prior else prior.get("stoppedAt", "candidate"))
        except (FileNotFoundError, PermissionError) as error:
            attempt.update(status="preparation stop", stoppedAt="deployment", reason=type(error).__name__ + " for a required view input")
        except ValueError as error:
            attempt.update(status="operator stop", stoppedAt="candidate" if phase == "predict" else "required-side reach", reason=str(error))
        if phase == "trace":
            if not (stage / "trace.json").exists():
                write(stage / "trace.json", {"schema": "blind-test-source-only/v1", "status": "source-only",
                                            "reason": attempt["reason"], "qualifiedTraces": 0, "launches": []})
                attempt["status"] = "source-only"
            attempt["traceSha256"] = digest(stage / "trace.json")
        write(stage / "attempt.json", attempt)
        store_new(stage, destination)
        return attempt["status"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("predict", "measure", "trace"))
    parser.add_argument("arm", choices=ARMS)
    parser.add_argument("--slot", required=True, type=int, action="append")
    parser.add_argument("--reference-seal", required=True)
    parser.add_argument("--cold-seal")
    parser.add_argument("--prediction-seal")
    parser.add_argument("--trace-seal")
    parser.add_argument("--seconds", type=int, help="assert the committed per-phase time limit")
    args = parser.parse_args()
    counts = Counter(run_one(i, args.phase, args.arm, args.reference_seal, args.cold_seal, args.prediction_seal,
                             seconds=args.seconds, trace_seal=args.trace_seal) for i in args.slot)
    print(json.dumps(dict(counts)))

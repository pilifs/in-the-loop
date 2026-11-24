"""Capture the caller's native proof request before launch and check its LRAT assurance beside the ordinary receipt."""

import json
from pathlib import Path
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib/python"))
import jvmcontract_lrat as lrat


def bind(plan, execution):
    def launching(argv, identities):
        execution.launching(argv, identities)
        request = {"schema": "native-sat-request/v1", "run": execution.state["id"], "example": plan.example,
                   "task": plan.task, "kind": plan.kind, "target": plan.target, "claim": dict(plan.claim),
                   "bindings": execution.state["bindings"], "argv": list(argv), "bindingId": execution.state["bindingId"],
                   "sourceCommit": execution.state.get("sourceCommit"),
                   "checkerBuild": {key: identities[key] for key in ("commit", "libTree") if key in identities},
                   "checker": {key: identities[key] for key in (
                       "jvmcontract", "jdkRelease", "engine", "gaps", "bounds", "environment", "classpath",
                       "entryBindings", "checkedEntry", "commits", "scope", "recipe")}}
        lrat.save(execution.directory / "lrat-request.json", request)
    return launching


def certify(plan, execution, prepared, verifier, receipt, work):
    ordinary_path = Path(plan.folder) / receipt.path
    folder = ordinary_path.parent / "lrat"
    folder.mkdir()
    try:
        request_bytes = (execution.directory / "lrat-request.json").read_bytes()
        (folder / "request.json").write_bytes(request_bytes)
        request = json.loads(request_bytes)
        record = json.loads(ordinary_path.read_text())
        ordinary = record["conclusion"]
        if (ordinary.get("claim") != receipt.claim or request["claim"]["key"] != record["claim"]["target"]["claimKey"]
                or request["run"] != receipt.attempt or ordinary.get("attempt") != request["run"]):
            raise ValueError("ordinary conclusion differs from the launch request")
        replay = verifier.identities.get("independentReplay", [])
        if receipt.status == "refuted" and not any(r.get("by") == "jvm" and r.get("reproduced") for r in replay):
            from targets import replay_candidate
            replay = [replay_candidate.check(plan, prepared, c["witness"]["inputs"], work / "lrat-witness" / str(i),
                                              verifier.identities["checkedEntry"], checker=verifier.identities)
                      for i, c in enumerate(record["evidence"].get("counterexamples") or []) if c.get("witness")]
            if not any(r.get("by") == "jvm" and r.get("reproduced") for r in replay):
                why = next((r["reason"] for r in replay if r.get("reason")), "no typed witness")
                raise ValueError(f"ordinary refutation lacks a reproduced original JVM witness: {why}")
        runs = [run for observation in verifier.observations or []
                for run in (observation.get("search") or {}).get("runs", [])]
        anchor = {"status": receipt.status, "receiptSha256": lrat.digest(ordinary_path.read_bytes()),
                  "execution": receipt.attempt, "conclusion": ordinary,
                  "jvmReplay": replay}
        boundary, streams = lrat.capture(request, anchor, work, work / "solver-traces", runs)
        lrat.complete(folder, request, boundary, streams)
    except (OSError, ValueError, KeyError, IndexError, TypeError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        lrat.save(folder / "assurance.json", {"status": "withheld", "ordinary": receipt.status, "reason": str(error)})

"""Task planning, attempt ingestion and the index projection: the workflow stream's side of the interfaces
(interfaces.py), as Phase 0 of llm-dlc/loops/example-targets.md leaves them. plan_task(), ingest() and handoff() fail
closed with the named Unsupported result until the workflow stream replaces them (W1, W2, W3); project() reports only what
target.json states and derives no readiness until W4 does. Signatures are frozen."""

from targets.interfaces import WORKFLOW, Unsupported


def plan_task(folder, example, target, task):
    """The TaskPlan of the task with id `task` in the example's checked sidecar `target`, or Unsupported. Pure: no
    network, build, solver or directory. The caller has checked that the task exists."""
    return Unsupported("task-plan", WORKFLOW, "task planning is Phase 0's stub until the workflow stream's W1 replaces it",
                       stage="plan")


def ingest(plan, prepared, records, out):
    """Validates the raw records of one attempt at `plan`, binds them to the prepared artifacts (`prepared`, by
    revision name) and publishes one format-2 receipt under `out`, earlier attempts kept: a Receipt, or
    Unsupported."""
    return Unsupported("ingest", WORKFLOW, "attempt ingestion is Phase 0's stub until the workflow stream's W2 replaces it",
                       stage="ingest")


def handoff(folder, example, target, task):
    """The task's handoff packet, for an agent that continues it without rediscovery: its immutable inputs with their
    hashes, the exact commands, its current receipts, the next prerequisite and one recommended action, and for an
    observed gap the brief's capability-gap packet. Predicted and observed gaps stay apart. Offline, read-only: a
    dict, or Unsupported."""
    return Unsupported("handoff", WORKFLOW, "the handoff export is Phase 0's stub until the workflow stream's W3 replaces it",
                       stage="handoff")


def project(folder, example, target):
    """The example's row in the index (examples/index.json's `target`): its family, role, readiness, claim statuses
    and gaps, for find.py. Phase 0 projects what the sidecar states; readiness, claim statuses and observed gaps are
    derived from receipts by W4, and stay None until then."""
    identity = target["identity"]
    return {
        "family": identity["family"],
        "role": identity["role"],
        "case": identity["case"],
        "tasks": [t["id"] for t in target["tasks"]],
        "readiness": None,
        "claims": None,
        "gaps": sorted({b["kind"] for b in target.get("handoff", {}).get("blockers", []) if b["observed"]}),
        "predictedGaps": sorted({b["kind"] for b in target.get("handoff", {}).get("blockers", []) if not b["observed"]}),
        "unsupported": "readiness and claim statuses: Phase 0's stub until the workflow stream's W4 derives them",
    }

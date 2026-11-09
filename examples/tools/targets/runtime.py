"""Preparation and separate-JVM execution: the runtime stream's side of the interfaces (interfaces.py), as Phase 0 of
llm-dlc/loops/example-targets.md leaves them. Each fails closed with the named Unsupported result until the runtime
stream replaces it (R1-R4). Signatures are frozen. Acquisition follows the brief's downloads policy: github.com and
Maven Central only, every file's sha256 recorded and rechecked."""

from targets.interfaces import RUNTIME, Unsupported


def prepare(plan, revision, workdir):
    """One revision (a name in target.json) of `plan` made callable under `workdir`: a PreparedTarget at
    source-locked or artifacts-ready, or failed with its stage and diagnostic; or Unsupported."""
    return Unsupported("prepare", RUNTIME, "preparation is Phase 0's stub until the runtime stream's R1 and R2 replace it",
                       stage="prepare")


def run_controls(plan, prepared, workdir):
    """The task's concrete controls, each revision in its own JVM on its own classpath (`prepared`, by revision
    name): a tuple of raw ExecutionRecords, or Unsupported."""
    return Unsupported("run-controls", RUNTIME, "separate-JVM replay is Phase 0's stub until the runtime stream's R4 replaces it",
                       stage="controls")


def run_verifier(plan, prepared, workdir):
    """The verifier on the prepared artifacts, with the plan's engine, gaps and bounds: one raw ExecutionRecord, or
    Unsupported."""
    return Unsupported("run-verifier", RUNTIME, "the verifier on prepared artifacts is Phase 0's stub until the runtime stream's R3 replaces it",
                       stage="verifier")

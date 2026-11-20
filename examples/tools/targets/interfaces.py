"""The three shared interfaces of llm-dlc/loops/example-targets.md, frozen in Phase 0 before the streams fork.

    plan_task(folder, example, target, task)       -> TaskPlan | Unsupported              workflow.py (W1)
    prepare(plan, revision, workdir)               -> PreparedTarget | Unsupported        runtime.py  (R1, R2)
    run_controls(plan, prepared, workdir)          -> tuple[ExecutionRecord] | Unsupported runtime.py (R4)
    run_verifier(plan, prepared, workdir)          -> ExecutionRecord | Unsupported       runtime.py  (R3)
    ingest(plan, prepared, records, out)           -> Receipt | Unsupported               workflow.py (W2)
    project(folder, example, target)               -> dict                                 workflow.py (W4)
    handoff(folder, example, target, task)         -> dict | Unsupported                  workflow.py (W3)

Task metadata goes in, results come out, and the two stay apart: a TaskPlan never carries an outcome, a
PreparedTarget never decides a claim, an ExecutionRecord is raw (an exit code is not a verdict), and only ingestion
turns records into a format-2 receipt. route.py chains them and stops at the first Unsupported.

Each implementation Phase 0 commits fails closed: it returns Unsupported, naming the interface, the stream that owns
it and why, and the stream replaces it. Callers treat Unsupported as "not executable", never as a result. The types
are frozen: an owner may add a field with a default (an additive change, recorded for the merge), never rename,
remove or retype one; anything else is an interface request under its Progress.
"""

import dataclasses
from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

# The owning streams, as their loops are named.
WORKFLOW = "example-targets-workflow"
RUNTIME = "example-targets-runtime"


@dataclass(frozen=True)
class Unsupported:
    """What an interface returns when it cannot do what was asked: never an empty success. `stage` says how far it
    got (for a preparation: the stage that failed); `diagnostic` is the command or output that shows why."""
    interface: str  # task-plan, prepare, run-controls, run-verifier, ingest
    owner: str  # the stream that implements it
    reason: str
    stage: Optional[str] = None
    diagnostic: Optional[str] = None

    def describe(self):
        return f"unsupported: {self.interface} ({self.owner}): {self.reason}"


@dataclass(frozen=True)
class TaskPlan:
    """A named task resolved from the sidecar alone: what it checks, what it needs and what it is expected to show.
    Pure: making one touches no network, builds nothing, runs no solver and makes no directory. The runner executes
    it and the pipeline submits it, so the two can't disagree."""
    example: str  # the example's three digits
    task: str  # the task's id in target.json
    kind: str  # prove, compare, equivalence, replay
    relation: str  # security, preservation, compatibility, introduction, calibration, diagnostic
    target: str  # the original method, <class>#<method>(<descriptor>)
    revisions: Tuple[str, ...]  # the revision names it prepares: one for prove and replay, a pair's two otherwise
    claim: Mapping  # the declared source-level claim: the task's statement, domain, observations, bounds, and its claim file and hash
    prerequisites: Tuple[str, ...]  # task ids, resolved in order
    artifacts: Tuple[Mapping, ...]  # per revision, what preparation starts from (ARTIFACT_SOURCE below)
    tools: Mapping  # {"required": [...], "optional": [...]}: java, javac, jvmcontract ...; never jbmc for a native task
    engine: Optional[str]  # native, jbmc or auto: always explicit for a proof task
    gaps: Optional[str]
    expected: Optional[str]  # the authored semantic expectation: established, refuted, unresolved, or None
    outputs: Mapping  # where its receipt goes, relative to the example's folder: {"receipts": "receipts/<task>"}
    folder: str  # the example's folder, absolute: every path in the plan is relative to it
    network: bool = False  # whether preparation needs acquisition (planning itself never does)
    checkedLemmas: Optional[Mapping] = None  # optional proof strategy, with the input file's SHA-256

    def as_dict(self):
        values = to_dict(self)
        if self.checkedLemmas is None:
            values.pop("checkedLemmas")
        return values


# The keys of one TaskPlan.artifacts entry, one per revision the task prepares, resolved from target.json: `revision`
# (its name), `route` (published-artifact, upstream-build or fixture), `repository`, then `commit` (the full SHA) or
# `fixture` (a control's source directory, relative to the folder), and as the sidecar gives them `coordinates`, `url`
# and `sha256` (a published artifact), `build` (tool, argv, jdk), `adapters` (paths relative to the folder) and `jdks`
# (the JDKs the controls run on). An owner may add keys; these keep their meaning.
ARTIFACT_SOURCE = ("revision", "route", "repository", "commit", "fixture", "coordinates", "url", "sha256", "build",
                   "adapters", "jdks")


@dataclass(frozen=True)
class Artifact:
    """One file a preparation produced or fetched, by content."""
    path: str  # relative to the preparation's work directory
    sha256: str
    role: str  # original, dependency, adapter, driver, oracle, stub
    coordinates: Optional[str] = None  # group:artifact:version for a published artifact
    origin: Optional[str] = None  # where it came from: a URL on an allowed host (runtime_maven.HOSTS), or the build that made it


@dataclass(frozen=True)
class PreparedTarget:
    """One revision of a task made callable, or how far that got. `stage` is source-locked (immutable coordinates,
    paths and recipe, nothing fetched), artifacts-ready (everything resolved, built and hashed: only this supplies a
    proof attempt's identities) or failed (with `failedStage`, the diagnostic, its `blocker`, and whatever artifacts exist). It
    never decides a security claim."""
    example: str
    task: str
    revision: str  # the revision's name in target.json
    commit: str  # its full SHA, or fixture:<path> for a control's fixture revision
    stage: str  # source-locked, artifacts-ready, failed
    source: Mapping  # repository, commit, selected paths, provenance, adapter recipe
    artifacts: Tuple[Artifact, ...] = ()
    classpath: Tuple[str, ...] = ()  # ordered, as the JVM and the verifier are given it
    toolchain: Mapping = field(default_factory=dict)  # {"jdk": {feature, version, home, release}, "build": {...}}
    failedStage: Optional[str] = None  # acquire, build, adapter, classpath ...
    diagnostic: Optional[str] = None
    logs: Tuple[str, ...] = ()
    # Added in Phase 5 (step 1's request 7), after the streams merged:
    workdir: Optional[str] = None  # the preparation's directory, absolute, which `artifacts`, `classpath` and `logs` are relative to; None for a source lock, or a failure before it existed. A temporary path, so never in `source` or a claim
    blocker: Optional[Mapping] = None  # a failed preparation's handoff: stage, command, diagnostic, needs, next

    def as_dict(self):
        return to_dict(self)


@dataclass(frozen=True)
class ExecutionRecord:
    """A raw record of one process: a concrete control in its own JVM, or the verifier. Raw: its exit code, kill or
    timeout is how the process ended, not a violation or a proof; ingestion decides what it means. `observations` is
    the driver's structured output, or None when it could not be read (malformed or missing), which is a replay
    problem, never a result."""
    kind: str  # jvm-control or verifier
    revision: Optional[str]  # None for a verifier run over a pair
    argv: Tuple[str, ...]
    status: str  # exited, killed, timed-out, not-started (as build.py's stages)
    exitCode: Optional[int]
    seconds: float
    stdout: str  # path of the captured stream, relative to the attempt's directory
    stderr: str
    identities: Mapping  # the JDK, tool and artifact identities it ran with
    observations: Optional[Tuple[Mapping, ...]] = None
    control: Optional[str] = None  # the control's id in target.json, for a jvm-control
    # Added in Phase 5 (the user's review item 5, 2026-11-15), so that ingestion can bundle the raw streams:
    directory: Optional[str] = None  # the attempt's directory, absolute, which stdout, stderr and record are relative to. A temporary path, so never in a receipt
    record: Optional[str] = None  # the runner's record of this run (controls/controls.json, verifier/verifier.json), relative to directory
    reason: Optional[str] = None  # why a not-started record didn't start; None for a process that ran

    def as_dict(self):
        return to_dict(self)


@dataclass(frozen=True)
class Receipt:
    """A published format-2 receipt: one per task and attempt, earlier attempts kept beside it."""
    path: str  # relative to the example's folder: receipts/<task>/<attempt>/result.json
    claim: str  # the claim id
    attempt: str  # the attempt id
    status: Optional[str]  # the conclusion's status: established, refuted, unresolved, or None
    execution: str  # how the attempt ended (completed, timed-out, ...), apart from the status

    def as_dict(self):
        return to_dict(self)


def to_dict(value):
    return dataclasses.asdict(value)


def unsupported(value):
    """Whether an interface's return value is the named unsupported result."""
    return isinstance(value, Unsupported)

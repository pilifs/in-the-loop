"""The workload that knows nothing of what a job's commands mean: commands, exit codes, declared outputs.

A workload is the part of the pipeline that understands a kind of work (jobs/README.md). The pipeline itself
(jobs/pipeline.py) owns a job's identity, its attempts, its scheduling, its budget, its outputs and its record, and
asks the job's workload for the rest through the functions below. This one answers with nothing: it looks for a
required tool on PATH and nowhere else, builds nothing, adds nothing to a step's environment, and reads one thing
out of a log, a line that says memory ran out. A job that names no workload gets it, and it is what makes the
pipeline usable on a machine with no checker installed.

Every other workload (`verification.py`, ...) defines the same names. `core` is the pipeline module, set when it
loads the adapter.
"""
import re
import shutil

NAME = "generic"
core = None

# Lines worth lifting out of a log, so a reader need not open it: (tool, kind, pattern).
SIGNALS = [(tool, kind, re.compile(p)) for tool, kind, p in [
    ("memory", "out-of-memory", r"java\.lang\.OutOfMemoryError|ran out of memory|std::bad_alloc|Cannot allocate memory"),
]]
# In a step that passed: a signal that makes the pass worth a look, with what to say of it.
SUSPICIOUS = [("memory:out-of-memory", "the log mentions running out of memory")]
# What a commit of collected results holds besides the results themselves and the outputs applied.
COLLECTORS_OWN = ()


def tools() -> dict:
    """The versions of the tools this workload uses, for a result's record of the machine."""
    return {}


def missing(requires) -> list:
    """Which of a job's requirements this machine lacks."""
    return [r for r in requires if not shutil.which(r)]


def reservation(runner, job, job_plan, source) -> int:
    """The memory the runner sets aside for the job while it runs."""
    return job_plan["memoryLimit"]


def prepare(runner, job, source, work, result, entry) -> None:
    """After the export, before the steps: whatever the job's requirements take to be there. A workload that
    cannot prepare sets the result's status to `error` and says why in its attention."""


def step_env(runner, job, result, work, env) -> None:
    """Adds to the environment every step of the job gets."""


def scan(log_path):
    """(signals, counts, lines) of a step's log: the lines this workload knows how to read."""
    return core.scan_log(log_path, SIGNALS)


def verdicts(steps) -> list:
    """What the summary line says of the signals found."""
    return core.signal_verdicts(steps)


def conclusion(job, result):
    """What the result means for the question the job was asked, at the scope it was asked: None here, where
    nothing is known of the question."""
    return None

"""Read what `jvmcontract prove --json` and `jvmcontract equivalence --json` print: the Python side of the proof
output contract whose Rust side is lib/src/proof_wire.rs.

Three questions, each with its own function, so that no reader answers one of them by accident while asking another:

1. Can these bytes be decoded?                               decode(stdout, command) -> Decoded
2. Did the process end as the command it was asked to run
   ends, with the rows that command prints?                  completion(command, decoded, exit, ...) -> Completion
3. Does this evidence qualify for this claim?                the consumer's own, with its independent checks. What
                                                             is here for it reads a field as the type the contract
                                                             gives it (boolean, text, at, facts) and nothing more.

The first two have one rule for every consumer. The third has none: a benchmark may score a valid refutation as the
right answer where a proof campaign needs a replayed witness for it.

    decode(stdout, command)     the ordered outcomes of one process, or why there are none: not JSON, not that
                                command's shape, or a wire version this reader does not know (`unsupported-version`)
    completion(...)             completed, or timed-out, killed, tool-error (exit 2 and every code that is not a
                                verdict's), unsupported-version, invalid-output, contradictory-exit
    exit_of(verdicts)           the exit a run with these verdicts ends with: 0 when all are verified, else 1
    mistyped(outcome)           the decision fields an outcome holds with another JSON type than the contract's
    boolean(value)              True or False for a JSON boolean, None (unknown) for anything else, "false" included
    facts(outcome)              the typed facts readers decide by, each None where the outcome does not say

The module imports nothing outside the standard library, and nothing of this repository: a frozen export loads it
by path, and so does a consumer that has no examples/ beside it.
"""

import json
from typing import NamedTuple, Optional

# The versions this reader decodes. Output from before the field was added carries none and counts as 0.
SUPPORTED_VERSIONS = (0, 1)
COMMANDS = ("prove", "equivalence")
VERDICTS = ("verified", "violation", "unverifiable")
# The exit codes that carry a verdict (lib/src/lib.rs, Verdict::exit_code); 2 is the tool's own failure.
VERDICT_EXITS = (0, 1)

DECODED, NOT_JSON, NOT_OUTCOME, UNSUPPORTED_VERSION = "decoded", "not-json", "not-outcome", "unsupported-version"
COMPLETED = "completed"


class Decoded(NamedTuple):
    """What decode found. `outcomes` are the raw objects in the order printed, empty unless `status` is `decoded`;
    `versions` the wire version of each (0 for an untagged one), or the one refused; `raw` the text as given."""
    status: str
    outcomes: tuple
    versions: tuple
    reason: Optional[str]
    raw: str

    @property
    def ok(self):
        return self.status == DECODED


class Completion(NamedTuple):
    """How a process ended, as far as its command's contract goes: `status` is `completed` only for a decoded run
    whose rows and exit agree. `exit` is the code as given (None when there was none)."""
    status: str
    exit: Optional[int]
    reason: Optional[str]

    @property
    def ok(self):
        return self.status == COMPLETED

    def as_execution(self):
        """The same as the `execution` object results keep: {"status", "exitCode", "reason"}."""
        return {"status": self.status, "exitCode": self.exit, "reason": self.reason}


def version_of(value):
    """The wire version of one outcome object: an int, or None for a value that is not a version (a string, a
    boolean, a float). An object without the field is version 0."""
    version = value.get("wire_version", 0) if isinstance(value, dict) else None
    return version if type(version) is int else None


def supported_version(value):
    return isinstance(value, dict) and version_of(value) in SUPPORTED_VERSIONS


def is_outcome(value):
    return supported_version(value) and isinstance(value.get("output"), str)


def decode(stdout, command):
    """The ordered raw outcomes of one process, without deriving anything from them. `prove` prints an array with
    one object for each property, `equivalence` one object."""
    if command not in COMMANDS:
        raise ValueError(f"not a proof command: {command!r}")
    raw = stdout if isinstance(stdout, str) else ""
    shape = f"the verifier's standard output is not {command}'s --json outcome"
    try:
        value = json.loads(raw)
    except ValueError as error:
        return Decoded(NOT_JSON, (), (), f"the verifier's standard output is not JSON: {error}", raw)
    outcomes = value if command == "prove" else [value]
    if not isinstance(outcomes, list) or not outcomes:
        return Decoded(NOT_OUTCOME, (), (), shape, raw)
    for outcome in outcomes:
        if isinstance(outcome, dict) and not supported_version(outcome):
            refused = outcome.get("wire_version")
            return Decoded(UNSUPPORTED_VERSION, (), (refused,), f"unsupported checker wire version {refused!r}", raw)
        if not is_outcome(outcome):
            return Decoded(NOT_OUTCOME, (), (), shape, raw)
    return Decoded(DECODED, tuple(outcomes), tuple(version_of(o) for o in outcomes), None, raw)


# The fields readers decide by, each with the JSON type the Rust side writes it with (lib/src/equivalence.rs,
# property.rs, statement.rs). An equivalence outcome's `pair` is a property outcome with the same fields.
_TYPED = (
    (("verdict",), str), (("output",), str), (("proof",), str), (("problem",), str),
    (("stated", "bounds", "complete"), bool), (("stated", "vacuity", "status"), str), (("stated", "gap_mode"), str),
    (("replay", "reproduced"), bool), (("replay", "by"), str),
)


def mistyped(outcome):
    """The decision fields `outcome` holds with another JSON type than the contract gives them, as dotted names
    (`stated.bounds.complete`; the pair's under `pair.`). A field that is absent or null is not mistyped: it is
    unknown, which is for whoever needs it to refuse. A string where a boolean belongs is not a legacy spelling of
    anything, so a row with one is not an outcome a decision may rest on."""
    wrong = []
    for path, kind in _TYPED:
        value = at(outcome, *path)
        if value is not None and not (type(value) is bool if kind is bool else isinstance(value, kind)):
            wrong.append(".".join(path))
    pair = outcome.get("pair") if isinstance(outcome, dict) else None
    if isinstance(pair, dict):
        wrong.extend("pair." + name for name in mistyped(pair))
    return wrong


def exit_of(verdicts):
    """The exit of a run whose rows have these verdicts: each row's own (0 verified, 1 a violation or unverifiable),
    and the maximum over them, so one refuted property among verified ones exits with 1."""
    return max((0 if v == "verified" else 1 for v in verdicts), default=0)


def exit_problem(verdicts, exit_code):
    """Why this exit does not belong to rows with these verdicts, or None when it does. A code that carries no
    verdict is the tool's failure whatever was printed; a verdict that is not one of the three is no row."""
    if type(exit_code) is not int or exit_code not in VERDICT_EXITS:
        return "tool-error", f"the verifier failed with exit code {exit_code}"
    unknown = [v for v in verdicts if not isinstance(v, str) or v not in VERDICTS]
    if unknown or not verdicts:
        return "invalid-output", f"the verifier's outcome has the verdict {unknown[0]!r}" if unknown else "the verifier printed no outcome"
    if exit_of(verdicts) != exit_code:
        said = ", ".join(verdicts)
        return "contradictory-exit", f"the verifier exited with code {exit_code}, but its outcome{'s say' if len(verdicts) > 1 else ' says'} {said}"
    return None


def completion(command, decoded, exit_code, *, timed_out=None, killed=False, rows=None):
    """Whether the process ended as `command` ends. `timed_out` is the limit in seconds when the runner gave up
    waiting, `killed` whether a signal ended it, and `rows` the number of outcomes the request must have printed
    (1 for a single property; None for a properties file, whose rows the caller counts)."""
    if timed_out is not None and timed_out is not False:
        limit = "" if timed_out is True else f" within {timed_out} s"
        return Completion("timed-out", None, f"the verifier did not finish{limit}")
    if killed or (type(exit_code) is int and exit_code < 0):
        return Completion("killed", exit_code, "the verifier was killed" + (f" by signal {-exit_code}" if type(exit_code) is int and exit_code < 0 else ""))
    if type(exit_code) is not int or exit_code not in VERDICT_EXITS:
        return Completion("tool-error", exit_code if type(exit_code) is int else None, f"the verifier failed with exit code {exit_code}")
    if not decoded.ok:
        status = UNSUPPORTED_VERSION if decoded.status == UNSUPPORTED_VERSION else "invalid-output"
        return Completion(status, exit_code, decoded.reason)
    if command == "equivalence":
        rows = 1
    if rows is not None and len(decoded.outcomes) != rows:
        return Completion("invalid-output", exit_code, f"the verifier printed {len(decoded.outcomes)} outcomes where {command} was asked for {rows}")
    problem = exit_problem([o.get("verdict") for o in decoded.outcomes], exit_code)
    if problem:
        return Completion(problem[0], exit_code, problem[1])
    wrong = [name for o in decoded.outcomes for name in mistyped(o)]
    if wrong:
        return Completion("invalid-output", exit_code, f"the verifier's outcome has {', '.join(sorted(set(wrong)))} of another type than the proof output contract's")
    return Completion(COMPLETED, exit_code, None)


def read(stdout, command, exit_code, *, timed_out=None, killed=False, rows=None):
    """decode and completion together: (Decoded, Completion). The outcomes are to be used only when the completion
    is `completed`."""
    decoded = decode(stdout, command)
    return decoded, completion(command, decoded, exit_code, timed_out=timed_out, killed=killed, rows=rows)


def boolean(value):
    """True or False for a JSON boolean; None, meaning unknown, for anything else: the string "false" is truthy in
    Python, and 1 is not what the contract writes."""
    return value if type(value) is bool else None


def text(value):
    """The string, or None for anything else."""
    return value if isinstance(value, str) else None


def integer(value):
    """The integer, or None for anything else (a boolean is not one)."""
    return value if type(value) is int else None


def at(value, *keys):
    """The value under a path of object keys, or None as soon as a level is missing or is not an object."""
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def facts(outcome):
    """The facts of one outcome that readers decide by, each with the type the contract gives it and None where the
    outcome does not say (an older version, a refusal before a statement was built). None is unknown: a claim that
    needs the fact is not satisfied by it.

        version        0 for untagged output, else its wire_version
        verdict        one of VERDICTS, or None
        complete       stated.bounds.complete: every execution within the bounds was covered
        vacuity        stated.vacuity.status (`non-vacuous`, `vacuous`, `unknown`, ...)
        proof          the proof line, when it is non-empty text
        fresh          True when a checker ran for this outcome (`search`), False when it is an exact hit of the proof
                       cache (`reuse.kind` is `exact`, and there is no search), None when neither is said
        reproduced     replay.reproduced
        replayedBy     replay.by (`jvm`, `interpreter`)
        assumedGaps    the ids of the gaps the checker assumed; contractGaps those a contract answered
    """
    gaps = at(outcome, "search", "gaps")
    gaps = [g for g in gaps if isinstance(g, dict)] if isinstance(gaps, list) else []
    search = at(outcome, "search")
    reuse = text(at(outcome, "reuse", "kind"))
    return {
        "version": version_of(outcome),
        "verdict": text(at(outcome, "verdict")) if at(outcome, "verdict") in VERDICTS else None,
        "complete": boolean(at(outcome, "stated", "bounds", "complete")),
        "vacuity": text(at(outcome, "stated", "vacuity", "status")),
        "proof": text(at(outcome, "proof")) or None,
        "fresh": True if isinstance(search, dict) and search else (False if reuse == "exact" else None),
        "reproduced": boolean(at(outcome, "replay", "reproduced")),
        "replayedBy": text(at(outcome, "replay", "by")),
        "assumedGaps": [g.get("id") for g in gaps if g.get("treatment") == "assumed"],
        "contractGaps": [g.get("id") for g in gaps if g.get("treatment") == "contract"],
    }


# What a regression check did with a changed helper (lib/src/proof_wire.rs, HelperAction).
HELPER_ACTIONS = ("shared", "summary-applied", "stays-as-written", "keeps-body")


def helper_decisions(outcome):
    """The typed helper decisions of an equivalence outcome (its `helpers`), or None for an outcome from before the
    field, whose notes are all there is. Each is {"callee", "class", "method", "descriptor", "action", "key",
    "source", "reason", "reasonText", "summary", "seconds"}; `callee` is `Class.method`, as results name a helper.
    A decision whose action or callee is not what the contract writes raises ValueError: nothing is guessed."""
    rows = outcome.get("helpers") if isinstance(outcome, dict) else None
    if rows is None:
        return None
    if not isinstance(rows, list):
        raise ValueError("the outcome's helpers are not a list")
    out = []
    for row in rows:
        cls, method, descriptor = (text(at(row, "callee", k)) for k in ("class", "method", "descriptor"))
        action = text(at(row, "action"))
        if not cls or not method or descriptor is None or action not in HELPER_ACTIONS:
            raise ValueError(f"not a helper decision: {json.dumps(row, sort_keys=True)[:200]}")
        summary = at(row, "summary")
        out.append({
            "callee": cls.rsplit(".", 1)[-1] + "." + method, "class": cls, "method": method, "descriptor": descriptor,
            "action": action, "key": text(at(row, "key")), "source": text(at(row, "source")),
            "reason": text(at(row, "reason", "code")), "reasonText": text(at(row, "reason", "text")),
            "summary": ({"reads": list(summary.get("reads") or []), "facts": list(summary.get("facts") or [])}
                        if isinstance(summary, dict) else None),
            "seconds": row.get("seconds") if type(row.get("seconds")) in (int, float) else None,
        })
    return out

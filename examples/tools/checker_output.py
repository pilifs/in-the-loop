"""Decode jvmcontract proof JSON. Legacy untagged output is version zero; an unknown wire version is refused."""

import hashlib
import json
from pathlib import Path
import re


VERDICT_LABEL = {
    "violation": "✗ Violation",
    "verified": "✓ Verified",
    "unverifiable": "⚠ Unverifiable",
}


def last_line(output):
    lines = [line.strip() for line in (output or "").splitlines() if line.strip()]
    return lines[-1] if lines else None


def execution_status(returncode, output, timed_out=None, known=(0, 1)):
    """How a verifier's process ended: {"status", "exitCode", "reason"}. `known` are the exit codes that mean the
    verifier finished (0 verified, 1 violated or cannot be verified, for jvmcontract and the Java verifier); any
    other is the tool's own failure. A negative code is a signal (Python's convention), and so is 128 + N from a shell
    or a wrapper script. `timed_out` is the limit in seconds when the runner gave up waiting."""
    if timed_out is not None:
        return {"status": "timed-out", "exitCode": None, "reason": f"the verifier did not finish within {timed_out} s"}
    if returncode < 0:
        return {"status": "killed", "exitCode": returncode, "reason": f"the verifier was killed by signal {-returncode}"}
    if 128 < returncode <= 128 + 64 and returncode not in known:
        return {"status": "killed", "exitCode": returncode,
                "reason": f"the verifier exited with code {returncode}, a shell's report of signal {returncode - 128}"}
    if returncode not in known:
        line = last_line(output)
        return {"status": "tool-error", "exitCode": returncode,
                "reason": f"the verifier failed with exit code {returncode}" + (f": {line}" if line else ", printing nothing")}
    if not (output or "").strip():
        return {"status": "invalid-output", "exitCode": returncode,
                "reason": f"the verifier exited with code {returncode} and printed nothing"}
    return {"status": "completed", "exitCode": returncode, "reason": None}


def violation(execution, evidence, reported):
    """A completed run that reports a violation: one, when the runner has read what shows it and the verifier wrote
    its report; otherwise output the runner cannot read."""
    if evidence and reported:
        return execution, "violation"
    reason = ("the verifier reported a violation but wrote no SARIF report" if evidence else
              f"the verifier exited with code {execution['exitCode']}, but its output shows no violation the runner can "
              "read and no reason it cannot be verified")
    return {"status": "invalid-output", "exitCode": execution["exitCode"], "reason": reason}, None


def conclude_outcome(returncode, output, outcome, evidence, reported):
    """`conclude` for a run with `--json`, whose verdict is the outcome's: the exit code must agree with it (0 for
    verified, 1 otherwise), and a violation needs its witness and the report as before. `outcome` is None when the
    verifier's standard output is not one."""
    execution = execution_status(returncode, output)
    if execution["status"] != "completed":
        return execution, None
    if outcome is None:
        return {"status": "invalid-output", "exitCode": returncode,
                "reason": "the verifier's --json output is not an outcome the runner can read"}, None
    verdict = outcome.get("verdict")
    if verdict not in VERDICT_LABEL or (returncode == 0) != (verdict == "verified"):
        return {"status": "invalid-output", "exitCode": returncode,
                "reason": f"the verifier exited with code {returncode}, but its outcome's verdict is {verdict!r}"}, None
    if verdict == "violation":
        return violation(execution, evidence, reported)
    return execution, verdict


def no_verdict_label(execution):
    return f"⚠ No verdict: {execution['reason']}"


def without_root(value, root):
    """`value` with the patched copy's root taken out of every string in it, as `tool()` does for text."""
    if isinstance(value, str):
        return value.replace(str(root) + "/", "")
    if isinstance(value, list):
        return [without_root(v, root) for v in value]
    if isinstance(value, dict):
        return {k: without_root(v, root) for k, v in value.items()}
    return value


def supported_version(value):
    return isinstance(value, dict) and type(value.get("wire_version", 0)) is int and value.get("wire_version", 0) in (0, 1)


def is_outcome(value):
    return supported_version(value) and isinstance(value.get("output"), str)


def decode(stdout, command):
    """Return the ordered raw outcomes of one process without deriving claim eligibility."""
    try:
        value = json.loads(stdout)
    except ValueError as error:
        return None, f"the verifier's standard output is not JSON: {error}"
    outcomes = value if command == "prove" else [value]
    if not isinstance(outcomes, list) or not outcomes:
        return None, f"the verifier's standard output is not {command}'s --json outcome"
    for outcome in outcomes:
        if isinstance(outcome, dict) and not supported_version(outcome):
            return None, f"unsupported checker wire version {outcome['wire_version']!r}"
        if not is_outcome(outcome):
            return None, f"the verifier's standard output is not {command}'s --json outcome"
    return tuple(outcomes), None


def json_outcome(proc, root):
    outcomes, _ = decode(proc.stdout, "equivalence")
    return without_root(outcomes[0], root) if outcomes else None


def json_outcomes(proc, root):
    outcomes, _ = decode(proc.stdout, "prove")
    return without_root(list(outcomes), root) if outcomes else None


def typed_call(call, classes):
    """A call from the outcome as the result keeps it, with the SHA-256 of the class file it names in the classes
    the run built (`classes` by `after` and `before`), or None when that file is not there."""
    root = classes.get(call["classes"])
    path = Path(root) / call["class_file"] if root else None
    return {"class": call["class"], "classFile": call["class_file"],
            "classFileSha256": file_digest(path) if path and path.is_file() else None, "classes": call["classes"],
            "method": call["method"], "descriptor": call["descriptor"], "static": call["static"],
            **({"receiver": call["receiver"]} if call.get("receiver") else {}), "arguments": call["arguments"],
            **({"setup": call["setup"]} if call.get("setup") else {})}


def witness_record(c, classes):
    """The counterexample as data, from the outcome's typed fields: the inputs (and those found before shrinking),
    the patched version's call, and for a regression proof the previous version's. None from a tool that gives
    no typed fields."""
    if not c.get("call") or "inputs" not in c:
        return None
    return {"inputs": c["inputs"], **({"foundInputs": c["found_inputs"]} if c.get("found_inputs") else {}),
            **({"replayObservations": c["replay_observations"]} if c.get("replay_observations") else {}),
            "call": typed_call(c["call"], classes),
            **({"previousCall": typed_call(c["previous_call"], classes)} if c.get("previous_call") else {})}


def equivalence_counterexamples(outcome, classes=None):
    """The outcome's witness as the result's counterexample: the input, what the version before did (`contract`)
    and what the patched one does (`actual`), with the input the checker found before it was shrunk, and the
    witness as data (`witness`) with the class files' digests from `classes`."""
    c = (outcome or {}).get("counterexample")
    if not c:
        return []
    witness = witness_record(c, classes or {})
    return [{"input": c["input"], "contract": c["before"], "actual": c["after"],
             **({"found": c["found"]} if c.get("found") else {}), "shrinkRuns": c.get("shrink_runs", 0),
             **({"witness": witness} if witness else {})}]


def search_record(outcome):
    """The checker run a verdict comes from, from the outcome's `search`: the engine, the checker, its settings and
    time, the input range the verdict was found in, and the own checker's numbers. None when no checker ran."""
    s = (outcome or {}).get("search")
    if not s:
        return None
    record = {"engine": s["engine"], "checker": s["checker"], "seconds": round(s["seconds"], 3), "properties": s["properties"],
              "unwind": s["unwind"], "maxArrayLength": s["max_array_length"], "stage": s.get("stage")}
    if outcome.get("shared"):
        record["sharedCallees"] = outcome["shared"]
    if s.get("fallback"):
        record["fallback"] = s["fallback"]
    if s.get("runs"):
        record["deadlineSeconds"] = s["deadline_seconds"]
        record["runs"] = camel(s["runs"])
    if s.get("native"):
        # Its numbers; what it says in words has fields of its own (a receipt with a loop covered by an invariant
        # was refused at check_result while these were copied with the numbers: example 287's fixed-guard).
        record["native"] = {re.sub(r"_(\w)", lambda m: m.group(1).upper(), k): v for k, v in s["native"].items() if not isinstance(v, list)}
        if s["native"].get("loops"):
            record["loopsCoveredByInvariants"] = s["native"]["loops"]
        if s["native"].get("assumed"):
            record["modelsAssume"] = s["native"]["assumed"]
    if s.get("gap_mode"):
        record["gapMode"] = s["gap_mode"]
    if s.get("gaps"):
        record["gaps"] = [{"id": g["id"], "kind": g["kind"], "call": g["call"], "sites": g["sites"],
                           "approximation": g["approximation"], "treatment": g["treatment"],
                           **({"checker": g["checker"]} if g.get("checker") else {}),
                           **({"contract": camel(g["contract"])} if g.get("contract") else {})} for g in s["gaps"]]
    return record


def camel(value):
    """`value` with every key in it in camelCase, as the result keeps the library's snake_case fields."""
    if isinstance(value, dict):
        return {re.sub(r"_(\w)", lambda m: m.group(1).upper(), k): camel(v) for k, v in value.items()}
    if isinstance(value, list):
        return [camel(v) for v in value]
    return value


def stated_record(outcome):
    """The statement the verdict is about, as data (step 2a of llm-dlc/loops/sound-verdicts.md), from the outcome's
    `stated`: its domain, assumptions with their basis, observations, bounds, models, checker, gap mode and
    confirmation. None from a run that built no statement, or a tool from before it said."""
    s = (outcome or {}).get("stated")
    return camel(s) if s else None


def advice_record(outcome, folder, name):
    """What a run under --gaps advised returned when it stopped at gaps with no contract (step 3a of
    llm-dlc/loops/sound-verdicts.md), from the outcome's `advice`: each gap with what a contract for it must state
    and its template, whose whole file is copied to `name` in the example's folder. None when there is none."""
    a = (outcome or {}).get("advice")
    if not a:
        return None
    (folder / name).write_text(a["template"])
    record = camel({k: v for k, v in a.items() if k not in ("template", "template_file")})
    record["claim"].pop("harness", None)  # the work directory's; the page's harness is statement.java
    record["templateFile"] = name
    return record


def property_headline(verdicts):
    """The verdict over a target's properties, every one of them required: a violation when any is refuted (the
    others, unresolved ones included, stay in the result beside it), verified only when every one is, and
    unverifiable otherwise. None when a verdict is not one the runner knows."""
    if not verdicts or any(v not in VERDICT_LABEL for v in verdicts):
        return None
    if "violation" in verdicts:
        return "violation"
    return "verified" if all(v == "verified" for v in verdicts) else "unverifiable"


def property_counterexample(outcome, classes=None):
    """A property outcome's witness as a result's counterexample: the input, the assertion it fails (`contract`;
    null for a property that is its throws clauses alone), what the method did (`actual`), what a throws clause
    required instead, the input the checker found before it was shrunk, and the witness as data."""
    c = outcome.get("counterexample")
    if not c:
        return None
    witness = witness_record(c, classes or {})
    return {"input": c["input"], "contract": property_assertion(outcome), "actual": c["outcome"],
            **({"expected": c["expected"]} if c.get("expected") else {}),
            **({"found": c["found"]} if c.get("found") else {}), "shrinkRuns": c.get("shrink_runs", 0),
            **({"witness": witness} if witness else {})}


def property_assertion(outcome):
    """The assertion as checked, or None for a property that is its throws clauses alone (the tool checks `true`
    beside them: that the method returns where no clause applies)."""
    throws = outcome.get("throws_checked") or outcome.get("throws") or []
    return None if outcome.get("assert") == "true" and throws else outcome.get("assert")


def property_record(outcome, harness, statement, classes=None, folder=None, template=None):
    """One property's outcome as the result keeps it: what it states, its verdict, and its own evidence; under
    --gaps advised, the advice of a proof that stopped at gaps, its template copied to `template` in `folder`."""
    throws = outcome.get("throws_checked") or outcome.get("throws") or []
    replay = outcome.get("replay")
    return {"harness": harness, "assert": property_assertion(outcome), "assume": outcome.get("assume"),
            **({"throws": throws} if throws else {}), "verdict": outcome["verdict"], "domain": outcome.get("domain"),
            "proof": outcome.get("proof"), "problem": outcome.get("problem"), "vacuous": outcome.get("vacuous"),
            "counterexample": property_counterexample(outcome, classes), "statement": statement,
            "search": search_record(outcome), "replay": {"by": replay["by"], "reproduced": replay["reproduced"]} if replay else None,
            **({"stated": stated_record(outcome)} if outcome.get("stated") else {}),
            **({"advice": advice_record(outcome, folder, template)} if outcome.get("advice") and folder else {})}


def file_digest(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None

"""Measure one immutable native role continuation without transferring credentials or exposing previous cases."""

import json
from pathlib import Path
import shutil
import tempfile
import uuid

import runner_core as core
import control
import isolation


def role_key(stage, case):
    if stage == "plan":
        return "fable-planner"
    if stage == "proof":
        return "fable-proof"
    if stage == "setup":
        return "opus-preparation"
    if stage == "review" and case.name.startswith("reviewer-") and case.name[9:].isdigit():
        return "fable-" + case.name
    raise core.Stopped("role-binding", "Unexpected case role or reviewer path.")


def binding(ledger, stage, case, model):
    root = ledger.root / "role-state" / role_key(stage, case)
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    state = root / "config"
    state.mkdir(mode=0o700, exist_ok=True)
    path = root / "binding.json"
    identity = {
        "case_id": ledger.data["intake"]["case_id"],
        "pairSha256": ledger.data["intake"]["pairSha256"],
        "model": model,
        "role": role_key(stage, case),
    }
    if not path.exists():
        core.exclusive(path, core.bytes_of({**identity, "session": str(uuid.uuid4())}))
    record = core.json_file(path)
    if (
        any(record.get(k) != v for k, v in identity.items())
        or str(uuid.UUID(record["session"])) != record["session"]
    ):
        raise core.Stopped("role-binding", "Trusted role/session identity mismatch.")
    if (state / ".credentials.json").exists():
        raise core.Stopped(
            "role-binding", "The private role state unexpectedly contains credential storage."
        )
    prior = root / "last-request.json"
    return state, record["session"], core.json_file(prior) if prior.is_file() else None


def transcript(state, session):
    project = state / "projects"
    found = list(project.glob("*/" + session + ".jsonl")) if project.is_dir() else []
    if (
        len(found) != 1
        or found[0].is_symlink()
        or not found[0].resolve().is_relative_to(state.resolve())
    ):
        raise core.Stopped(
            "role-history", "The expected single role transcript is missing or outside private state."
        )
    if any(path.name != session + ".jsonl" for path in project.glob("*/*.jsonl")):
        raise core.Stopped("role-history", "Private state contains another conversation.")
    return found[0]


def copy_current(source, state, session, target):
    out = target / source.relative_to(state)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, out)
    # The CLI can spill oversized tool outputs into its own current-session result directory. Copy only this conversation's regular, contained files.
    saved = source.parent / session / "tool-results"
    if saved.exists():
        if saved.is_symlink() or not saved.is_dir():
            raise core.Stopped(
                "role-history", "The current conversation tool results are not a private directory."
            )
        for path in saved.rglob("*"):
            if path.is_symlink() or not path.resolve().is_relative_to(saved.resolve()):
                raise core.Stopped("role-history", "A tool result escaped this conversation.")
            if path.is_dir():
                continue
            if not path.is_file():
                raise core.Stopped("role-history", "A tool result is not a regular file.")
            dest = target / path.relative_to(state)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)


def empty_release(root):
    pairs = root / "neutral-shadow-pair"
    pairs.mkdir()
    release = {"case_id": "context-measurement-only"}
    for side in ("old", "new"):
        d = pairs / side
        d.mkdir()
        (d / "purpose.txt").write_text("Synthetic transport only.")
        release[side] = {"tree_sha256": isolation.hashed(isolation.canonical(isolation.tree(d)))}
    (pairs / "pair.json").write_bytes(isolation.canonical(release) + b"\n")
    return pairs


def measure(ledger, model, state, session, prior, prompt):
    ledger.require_time()
    where = ledger.root / "shadow-work"
    where.mkdir(mode=0o700, exist_ok=True)
    tag = "--resume" if prior else "--session-id"
    original = None
    sha = None
    with tempfile.TemporaryDirectory(prefix="role-", dir=where) as scratch:
        root = Path(scratch)
        pairs = empty_release(root)
        case = root / "measurement"
        isolation.fresh_case(case, pairs, isolation.digest(pairs / "pair.json"))
        if prior:
            original = transcript(state, session)
            sha = isolation.digest(original)
            if sha != prior["transcriptSha256"]:
                raise core.Stopped(
                    "role-history",
                    "The previous native role transcript changed after its measured request.",
                )
            copy_current(original, state, session, case / "work/state")
        settings = {
            "model": model,
            "session": session,
            "mode": tag,
            "prompt": prompt,
            "maxOutputTokens": ledger.profile["oneRequest"]["maxOutputTokens"],
            "options": ledger.profile["explicitSettings"],
            "expectedBlockSha256": prior.get("lastVisibleBlockSha256") if prior else None,
            "expectedToolResultIdSha256": prior.get("lastToolResultIdSha256") if prior else None,
        }
        (case / "work/measure.json").write_bytes(core.bytes_of(settings))
        response = control.execute(
            ledger.shadow_product,
            case,
            {
                "type": "function_call",
                "name": "case_command",
                "arguments": json.dumps({"argv": ["python3", "/opt/operator-shadow/measure.py"]}),
            },
            timeout=ledger.left(),
        )
        if response["exit"]:
            raise core.Stopped(
                "shadow-meter",
                "The credentialless networkless first-party shadow failed before a payable request.",
            )
        result = json.loads(response["output"])
    core.atomic(ledger.root / "last-shadow-observation.json", result)
    if not (
        result.get("model") == model
        and result.get("effort") == "high"
        and result.get("tools") == ["mcp__neutral_case__case_command"]
        and result.get("identityEncoding")
        and result.get("fakeKeyOnly")
        and result.get("promptPresent")
        and result.get("sessionMatched")
        and result.get("maxOutputTokens") == settings["maxOutputTokens"]
        and type(result.get("wireBytes")) is int
        and result["wireBytes"] > 0
        and result.get("priorSignalRestored")
        and result.get("priorToolResultIdRestored")
        and (not prior or result["priorAssistantMessages"] > 0)
    ):
        raise core.Stopped(
            "shadow-meter",
            "The normal client did not reproduce its exact role, prior context, tool catalogue or bounded request.",
        )
    if original is not None and sha != isolation.digest(original):
        raise core.Stopped("role-history", "The read-only shadow changed the original conversation.")
    result["sourceTranscriptSha256"] = sha
    result["mode"] = tag
    return result


def reserve(ledger, measured):
    ledger.require_time()
    n = (
        measured["wireBytes"]
        + ledger.profile["oneRequest"]["metadataFramingAllowance"]
        + ledger.profile["oneRequest"]["maxOutputTokens"]
    )
    remaining = (
        ledger.profile["budget"]["uncachedInputPlusOutputTokens"] - ledger.data["chargedTokens"]
    )
    if ledger.data["reservedTokens"] or n > remaining:
        raise core.Stopped(
            "token-budget",
            f"The measured full native context and maximum generation require {n} tokens; {remaining} remain.",
        )
    ledger.data["reservedTokens"] = n
    core.atomic(ledger.statepath, ledger.data)
    return n

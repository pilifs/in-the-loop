"""Bind the broker's actual outcome to the named tool use and export only the owning role's persisted files."""

import json

import native_result
import resume_meter
import runner_core as core
import isolation


def recorded_outcome(state, session, prior, journal):
    expected = prior.get("lastToolResultIdSha256")
    if not expected or not journal.is_file():
        return {}
    # The native assistant specifies tool-use IDs. The broker records dispatch arguments and results.
    # Match the two records without assuming parallel calls completed in message order.
    arguments = set()
    transcript = resume_meter.transcript(state, session)
    if isolation.digest(transcript) != prior["transcriptSha256"]:
        raise core.Stopped(
            "role-history", "The previous native role transcript changed before outcome binding."
        )
    with transcript.open() as source:
        for line in source:
            item = json.loads(line)
            if item.get("type") != "assistant":
                continue
            blocks = item.get("message", {}).get("content", [])
            for part in blocks if isinstance(blocks, list) else []:
                if (
                    not isinstance(part, dict)
                    or part.get("type") != "tool_use"
                    or part.get("name") != "mcp__neutral_case__case_command"
                    or native_result.digest(str(part.get("id", "")).encode()) != expected
                ):
                    continue
                argv = part.get("input", {}).get("argv")
                if isinstance(argv, list) and all(isinstance(arg, str) for arg in argv):
                    arguments.add(tuple(argv))
    if len(arguments) != 1:
        return {}
    argv = list(arguments.pop())
    outcomes = set()
    with journal.open() as source:
        for line in source:
            row = json.loads(line)
            if row.get("argv") == argv:
                outcomes.add(native_result.outcome({"exit": row["exit"], "output": row["output"]}))
    if len(outcomes) != 1 or None in outcomes:
        return {}
    return {"trustedToolIdSha256": expected, "outcomeSha256": outcomes.pop()}


def bind_copy(copy_base, source, state, session, target):
    copy_base(source, state, session, target)
    prior = core.json_file(state.parent / "last-request.json")
    bound = {k: prior[k] for k in ("trustedToolIdSha256", "outcomeSha256") if k in prior}
    files = {}
    relative = source.relative_to(state).parent / session / "tool-results"
    origin = state / relative
    if origin.is_dir():
        for entry in origin.iterdir():
            if entry.is_symlink() or not entry.is_file():
                continue
            rel = entry.relative_to(state)
            copy = target / rel
            if not copy.is_file() or copy.is_symlink():
                continue
            files[native_result.digest(str(entry).encode())] = {
                "relative": rel.as_posix(),
                "sha256": isolation.digest(copy),
            }
    core.atomic(target.parent / "native-result-bindings.json", {**bound, "files": files})


FLAGS = (
    "wireBytes",
    "identityEncoding",
    "fakeKeyOnly",
    "promptPresent",
    "priorAssistantMessages",
    "priorSignalRestored",
    "priorToolResultIdRestored",
    "sessionMatched",
    "maxOutputTokens",
    "tools",
    "model",
    "effort",
    "nativeRestore",
)


def hook():
    import native_transport
    import reporting

    base_copy = resume_meter.copy_current
    base_measure = resume_meter.measure
    base_request = native_transport.model_request
    base_report = reporting.build_document

    def copy(source, state, session, target):
        return bind_copy(base_copy, source, state, session, target)

    def measure(ledger, model, state, session, prior, prompt):
        path = ledger.root / "last-shadow-observation.json"
        previously = path.stat().st_ino if path.is_file() else None
        summary = {"next_request": len(ledger.data["requests"]) + 1, "accepted": False}
        try:
            result = base_measure(ledger, model, state, session, prior, prompt)
            summary["accepted"] = True
            return result
        except core.Stopped as exc:
            summary["stop"] = exc.code
            raise
        except (OSError, ValueError, RuntimeError) as exc:
            summary["stop"] = type(exc).__name__
            raise
        finally:
            if path.is_file() and path.stat().st_ino != previously:
                observed = core.json_file(path)
                summary.update({key: observed.get(key) for key in FLAGS})
            core.atomic(ledger.root / "last-restore-check.json", summary)

    def request(model, stage, prompt, product, case, ledger, exe):
        before = len(ledger.data["requests"])
        try:
            value = base_request(model, stage, prompt, product, case, ledger, exe)
        finally:
            if len(ledger.data["requests"]) == before + 1:
                shadow = core.json_file(ledger.root / "last-shadow-observation.json")
                ledger.data["requests"][-1]["native_restore"] = shadow.get("nativeRestore")
                core.atomic(ledger.statepath, ledger.data)
        state, session, prior = resume_meter.binding(ledger, stage, case, model)
        if prior and prior.get("lastToolResultIdSha256"):
            journal = ledger.root / "requests" / f"{before + 1:05d}" / "case-tool.jsonl"
            bound = recorded_outcome(state, session, prior, journal)
            if not bound:
                raise core.Stopped(
                    "role-history",
                    "The native tool-use ID could not be bound to one trusted broker outcome.",
                )
            core.atomic(state.parent / "last-request.json", {**prior, **bound})
        return value

    def report(info, root):
        doc = base_report(info, root)
        path = root / "last-restore-check.json"
        if path.is_file():
            doc["terminal_shadow"] = core.json_file(path)
            doc["evidence"].append({"file": path.name, "sha256": isolation.digest(path)})
        return doc

    resume_meter.copy_current = copy
    resume_meter.measure = measure
    native_transport.model_request = request
    reporting.build_document = report

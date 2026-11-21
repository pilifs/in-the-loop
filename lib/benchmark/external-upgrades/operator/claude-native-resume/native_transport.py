"""One payable native request. Resume the kept role transcript only after the separate uncredentialed meter authorizes it."""

import hashlib
import json
import os
import signal
import subprocess
import time

from signals import signal as visible_signal
import runner_core as core
import resume_meter as meter
import isolation


def model_request(model, stage, prompt, product, case, ledger, exe):
    state, session, prior = meter.binding(ledger, stage, case, model)
    started = time.monotonic()
    shadow = meter.measure(ledger, model, state, session, prior, prompt)
    meter_seconds = round(time.monotonic() - started, 3)
    directory = ledger.root / "requests" / f"{len(ledger.data['requests']) + 1:05d}"
    directory.mkdir(parents=True)
    audit = directory / "case-tool.jsonl"
    mcp = directory / "mcp.json"
    core.atomic(
        mcp,
        {
            "mcpServers": {
                "neutral_case": {
                    "type": "stdio",
                    "command": "/usr/bin/python3",
                    "args": [
                        str(core.HERE / "broker.py"),
                        str(product),
                        str(case),
                        str(audit),
                        str(ledger.end),
                    ],
                }
            }
        },
    )
    tmp = directory / "tmp"
    tmp.mkdir()
    core.atomic(directory / "shadow.json", shadow)
    env = {
        k: os.environ[k]
        for k in ("HOME", "USER", "LOGNAME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS")
        if k in os.environ
    }
    env.update(
        {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "TZ": "UTC",
            "TMPDIR": str(tmp),
            "CLAUDE_CONFIG_DIR": str(state),
            "CLAUDE_SECURESTORAGE_CONFIG_DIR": "",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_TELEMETRY": "1",
            "DISABLE_ERROR_REPORTING": "1",
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            "ENABLE_TOOL_SEARCH": "false",
            "CLAUDE_CODE_MAX_RETRIES": "0",
            "DISABLE_COMPACT": "1",
            "CLAUDE_CODE_GZIP_REQUEST_BODY": "0",
            "CLAUDE_CODE_INCREMENTAL_REQUEST_BODY": "0",
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(ledger.profile["oneRequest"]["maxOutputTokens"]),
        }
    )
    if not prior:
        check = subprocess.run(
            [str(exe), "auth", "status", "--json"],
            env=env,
            cwd="/srv",
            capture_output=True,
            text=True,
            timeout=min(10, ledger.left()),
        )
        try:
            status = json.loads(check.stdout)
        except (ValueError, TypeError):
            status = {}
        if (
            check.returncode
            or status.get("loggedIn") is not True
            or status.get("authMethod") != "claude.ai"
        ):
            raise core.Stopped(
                "account-refused",
                "The ordinary first-party credential store did not authenticate this private role. No model request was submitted.",
            )
    command = [
        str(exe),
        "-p",
        "--model",
        model,
        "--effort",
        "high",
        "--restricted",
        "--tools",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        str(mcp),
        "--disable-slash-commands",
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        "mcp__neutral_case__case_command",
        "--max-turns",
        "1",
        "--settings",
        json.dumps(ledger.profile["explicitSettings"]),
        "--output-format",
        "stream-json",
        "--verbose",
        shadow["mode"],
        session,
        "--",
        prompt,
    ]
    reserved = meter.reserve(ledger, shadow)
    start = time.monotonic()
    try:
        proc = subprocess.Popen(
            command,
            env=env,
            cwd="/srv",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        ledger.data["reservedTokens"] = 0
        core.atomic(ledger.statepath, ledger.data)
        raise
    try:
        stdout, stderr = proc.communicate(timeout=ledger.left())
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        raise core.Stopped(
            "time-or-interruption", "The native client was stopped with an unsettled reservation."
        )
    events = []
    for raw in stdout.splitlines():
        try:
            events.append(json.loads(raw))
        except ValueError:
            continue
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    final = next((e for e in reversed(events) if e.get("type") == "result"), {})
    reason = " ".join(
        [
            str(final.get("subtype")),
            str(final.get("result", "")),
            str(final.get("errors", "")),
            stderr.decode(errors="replace"),
        ]
    )
    result_models = final.get("modelUsage") or {}
    try:
        u = core.usage_of(final)
        cost = final["total_cost_usd"]
        assert isinstance(cost, (int, float)) and cost >= 0
    except (ValueError, KeyError, AssertionError):
        raise core.Stopped(
            core.classify_failure(reason),
            "The ordinary client did not supply settled usage. No replacement request was submitted.",
        )
    assistant = [
        e["message"]
        for e in events
        if e.get("type") == "assistant" and isinstance(e.get("message"), dict)
    ]
    ids = {m.get("id") for m in assistant if m.get("id")}
    toolnames = [
        b.get("name") for m in assistant for b in m.get("content", []) if b.get("type") == "tool_use"
    ]
    calls = [json.loads(line) for line in audit.read_text().splitlines()] if audit.is_file() else []
    record = {
        "stage": stage,
        "model": model,
        "seconds": round(time.monotonic() - start, 3),
        "shadowSeconds": meter_seconds,
        "reservation": reserved,
        "shadowWireBytes": shadow["wireBytes"],
        "nativeMode": shadow["mode"],
        "nativeSessionSha256": hashlib.sha256(session.encode()).hexdigest(),
        "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "previousVisibleBlockVerified": shadow["priorSignalRestored"],
        "priorAssistantMessages": shadow["priorAssistantMessages"],
        "tokens": u,
        "estimatedUsd": cost,
        "toolCalls": len(calls),
        "models": list(result_models),
        "assistantMessageCount": len(ids),
        "clientDisposition": final.get("subtype"),
        "exit": proc.returncode,
    }
    ledger.settle(record)
    if (
        final.get("subtype") not in ("success", "error_max_turns")
        or init.get("session_id") != session
        or init.get("model") != model
        or init.get("tools") != ["mcp__neutral_case__case_command"]
        or set(result_models) != {model}
        or len(ids) > 1
        or any(n != "mcp__neutral_case__case_command" for n in toolnames)
    ):
        raise core.Stopped(
            core.classify_failure(reason),
            "The normal role, exact resume session, one-request boundary or restricted tool catalogue did not qualify.",
        )
    # Compare the complete previous native result on its next resumption without retaining a duplicate transcript or thinking text in the report.
    if calls:
        visible = calls[-1]["output"]
    else:
        visible = next(
            (
                b["text"]
                for m in reversed(assistant)
                for b in reversed(m.get("content", []))
                if b.get("type") == "text" and b.get("text")
            ),
            "",
        )
    tool_ids = [
        b["id"]
        for message in assistant
        for b in message.get("content", [])
        if b.get("type") == "tool_use" and b.get("id")
    ]
    if not visible and not tool_ids:
        raise core.Stopped(
            "role-history", "The native request had no visible record to bind its next continuation."
        )
    if (state / ".credentials.json").exists():
        raise core.Stopped(
            "role-storage",
            "An account credential file unexpectedly appeared in private role session state.",
        )
    current = meter.transcript(state, session)
    if prior and isolation.digest(current) == prior["transcriptSha256"]:
        raise core.Stopped(
            "role-history",
            "The native client did not extend its own conversation after the authorized request.",
        )
    core.atomic(
        state.parent / "last-request.json",
        {
            "transcriptSha256": isolation.digest(current),
            "lastVisibleBlockSha256": visible_signal(visible) if visible else None,
            "lastToolResultIdSha256": hashlib.sha256(tool_ids[-1].encode()).hexdigest()
            if tool_ids
            else None,
        },
    )
    return "The native session holds its complete previous turn."

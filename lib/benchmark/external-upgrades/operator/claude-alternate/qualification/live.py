"""Two expressly authorized first-party model smoke sessions over a public toy; no benchmark reports enter either prompt."""

import argparse
import datetime
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROMPT = 'Public synthetic tool qualification. Use the case_command MCP tool once with exactly {"argv":["python3","/case/work/observe_public_case.py"]}. Read its returned JSON. Reply with only the observed nonce and the old and new integers.'
MODELS = ("claude-fable-5-2", "claude-opus-5-5")
CAP = 0.75


def sha(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def check_qualification(path):
    d = json.loads(path.read_bytes())["roles"]
    assert set(d) == set(MODELS)
    for model, row in d.items():
        assert (
            row["exit"] == 0
            and len(row["brokerCalls"]) == 1
            and row["observedToolWrite"]
            and row["noCrossWriteOnControlSide"]
        )
        assert (
            not row.get("createdSessionTranscripts")
            and not row.get("unlistedMcpStarted")
            and not row.get("unlistedHookExecuted")
        )
        assert all(
            x["tools"] == ["mcp__neutral_case__case_command"]
            and x["model"] == model
            and x["effort"] == "high"
            and x["syntheticNeutralPromptPresent"]
            and not x["privateSentinelsInPayload"]
            and x["syntheticApiKeyOnly"]
            for x in row["requests"]
        )
        r = row["toolResponses"]
        v = r["toolu_case_sample"]
        assert (
            v["exit"] == 0
            and v["readExpected"]
            and v["writeExpected"]
            and all(v["outsideDenied"].values())
        )
        for key in ("toolu_builtin_canary", "toolu_agent_canary", "toolu_placeholder_canary"):
            assert r[key]["isError"] and not r[key]["controlSecretDisclosed"]


def known_reason(text):
    t = text.casefold()
    categories = {
        "account authentication refused": (
            "not logged in",
            "authentication_error",
            "invalid api key",
            "unauthorized",
            "please run /login",
            "failed to authenticate",
        ),
        "account quota or rate limit": (
            "rate limit",
            "rate_limit",
            "usage limit",
            "out of usage",
            "quota",
            "you’ve hit",
            "you've hit",
            "too many requests",
        ),
        "account or model access refused": (
            "permission_error",
            "does not have access",
            "not allowed to use",
            "api error: 403",
            "credit balance",
            "billing",
            "model is not available",
            "not available for your",
            "model is unavailable",
        ),
        "client budget limit": ("max_budget", "budget limit", "budget exceeded"),
        "client turn limit": ("max_turns", "maximum number of turns"),
    }
    return next(
        (name for name, patterns in categories.items() if any(x in t for x in patterns)), None
    )


def session(model, root, product, pair, cpid, cli, operator, pin):
    import isolation  # noqa: E402

    stage = root / model
    stage.mkdir()
    case = stage / "case"
    isolation.fresh_case(case, pair, cpid)
    nonce = secrets.token_hex(12)
    (case / "work/challenge").write_text(nonce + "\n")
    shutil.copy2(HERE / "live_subject.py", case / "work/observe_public_case.py")
    audit = stage / "broker-audit.jsonl"
    mcp = stage / "explicit-mcp.json"
    mcp.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "neutral_case": {
                        "type": "stdio",
                        "command": "/usr/bin/python3",
                        "args": [
                            str(HERE / "live_broker.py"),
                            "--baseline",
                            str(operator),
                            "--product",
                            str(product),
                            "--case",
                            str(case),
                            "--audit",
                            str(audit),
                        ],
                    }
                }
            }
        )
    )
    tmp = stage / "tmp"
    tmp.mkdir()
    # No credentials or provider overrides are inherited from the invoking agent. The native client performs its ordinary first-party login itself.
    env = {
        k: os.environ[k]
        for k in ("HOME", "USER", "LOGNAME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS")
        if k in os.environ
    }
    env.update(
        {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "TMPDIR": str(tmp),
            "LANG": "C.UTF-8",
            "TZ": "UTC",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_TELEMETRY": "1",
            "DISABLE_ERROR_REPORTING": "1",
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            "ENABLE_TOOL_SEARCH": "false",
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "1024",
        }
    )
    opts = {
        "claudeMdExcludes": [
            "**/CLAUDE.md",
            "**/CLAUDE.local.md",
            "**/AGENTS.md",
            "**/.claude/rules/**",
        ],
        "autoMemoryEnabled": False,
        "disableAllHooks": True,
    }
    command = [
        str(cli),
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
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        "mcp__neutral_case__case_command",
        "--max-turns",
        "2",
        "--max-budget-usd",
        str(CAP),
        "--settings",
        json.dumps(opts),
        "--output-format",
        "stream-json",
        "--verbose",
        "--",
        PROMPT,
    ]
    started_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    start = time.monotonic()
    proc = subprocess.Popen(
        command,
        env=env,
        cwd="/srv",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    timedout = False
    try:
        stdout, stderr = proc.communicate(timeout=110)
    except subprocess.TimeoutExpired:
        timedout = True
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
    elapsed = round(time.monotonic() - start, 3)
    events = []
    for line in stdout.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    state = next((e for e in reversed(events) if e.get("type") == "result"), {})
    verdict_text = state.get("result", "")
    reason = known_reason(
        " ".join(
            [
                str(state.get("subtype", "")),
                str(verdict_text),
                str(state.get("errors", "")),
                stderr.decode(errors="replace"),
            ]
        )
    )
    output = case / "work/model-tool-result.json"
    written = json.loads(output.read_bytes()) if output.is_file() else None
    calls = [json.loads(line) for line in audit.read_text().splitlines()] if audit.is_file() else []
    models = {
        name: {
            k: m[k]
            for k in (
                "inputTokens",
                "outputTokens",
                "cacheReadInputTokens",
                "cacheCreationInputTokens",
                "costUSD",
                "webSearchRequests",
            )
            if k in m
        }
        for name, m in (state.get("modelUsage") or {}).items()
    }
    usage = state.get("usage") or {}
    mcpstatus = [
        {"name": v.get("name"), "status": v.get("status")} for v in (init.get("mcp_servers") or [])
    ]
    tool_events = []
    for event in events:
        if event.get("type") == "assistant":
            for block in (event.get("message") or {}).get("content", []):
                if block.get("type") == "tool_use":
                    tool_events.append(block.get("name"))
    rec = {
        "modelRequested": model,
        "effort": "high",
        "startedAt": started_utc,
        "elapsedSeconds": elapsed,
        "deadlineSeconds": 120,
        "clientBudgetUsd": CAP,
        "exit": proc.returncode,
        "timedOut": timedout,
        "clientDisposition": state.get("subtype"),
        "clientError": state.get("is_error"),
        "knownRefusal": reason,
        "toolsAtInit": init.get("tools"),
        "mcpAtInit": mcpstatus,
        "initialModel": init.get("model"),
        "toolEvents": tool_events,
        "brokerCalls": calls,
        "nonceReturnedCorrectly": nonce in str(verdict_text),
        "integersReturnedCorrectly": len(
            re.findall(r"(?<![a-z0-9])42(?![a-z0-9])", str(verdict_text).lower())
        )
        >= 2,
        "actualCaseOutcome": None
        if written is None
        else {k: written[k] for k in ("case_id", "old", "new", "checker")},
        "privateWriteVerified": written is not None and written.get("nonce") == nonce,
        "clientEstimatedUsd": state.get("total_cost_usd"),
        "tokens": {
            k: usage[k]
            for k in (
                "input_tokens",
                "output_tokens",
                "cache_read_input_tokens",
                "cache_creation_input_tokens",
            )
            if k in usage
        },
        "actualModelUsage": models,
        "credentialHandling": "First-party client login on the control side; no credential supplied by the probe.",
    }
    rec["qualified"] = bool(
        not timedout
        and proc.returncode == 0
        and not state.get("is_error", True)
        and init.get("model") == model
        and set(models) == {model}
        and init.get("tools") == ["mcp__neutral_case__case_command"]
        and mcpstatus == [{"name": "neutral_case", "status": "connected"}]
        and tool_events == ["mcp__neutral_case__case_command"]
        and len(calls) == 1
        and calls[0]["exit"] == 0
        and calls[0]["exactRequestedCommand"]
        and written
        == {
            "nonce": nonce,
            "case_id": "synthetic-only",
            "old": 42,
            "new": 42,
            "checker": pin["sha256"]["jvmcontract"],
        }
        and rec["nonceReturnedCorrectly"]
        and rec["integersReturnedCorrectly"]
        and rec["clientEstimatedUsd"] is not None
        and rec["clientEstimatedUsd"] < 1.0
    )
    if not rec["qualified"] and not reason:
        rec["diagnosticCategory"] = (
            "Inspect the retained structured fields; no raw client transcript is retained."
        )
    return rec


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--operator", required=True, type=Path)
    p.add_argument("--product", required=True, type=Path)
    p.add_argument("--synthetic-qualification", required=True, type=Path)
    p.add_argument("--scratch", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    operator = a.operator.resolve()
    sys.path.insert(0, str(operator))
    import probe

    check_qualification(a.synthetic_qualification)
    assert not any(Path("/srv").iterdir()) and not any(
        Path(x).exists()
        for x in (
            "/CLAUDE.md",
            "/AGENTS.md",
            "/.claude",
            "/etc/claude-code/managed-settings.json",
            "/etc/claude-code/managed-settings.d",
        )
    )
    root = a.scratch.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    pair, _ = probe.packet(root)
    cpid = sha(pair / "pair.json")
    pin = json.loads((operator.parent / "v0.json").read_bytes())
    cli = Path(shutil.which("claude")).resolve()
    out = {
        "schema": "external-upgrade-claude-alternate-live/v1",
        "purpose": "disclosed public synthetic transport qualification, never a scored case",
        "roleModels": list(MODELS),
        "cliVersion": subprocess.check_output([cli, "--version"], text=True).strip(),
        "cliSha256": sha(cli),
        "sourceRevision": pin["revision"],
        "checkerSha256": pin["sha256"]["jvmcontract"],
        "toolRootSha256": sha(a.product / "manifest.json"),
        "commonReleaseSha256": cpid,
        "promptSha256": hashlib.sha256(PROMPT.encode()).hexdigest(),
        "loopbackQualificationSha256": sha(a.synthetic_qualification),
        "wallLimitPerRole": 120,
        "clientBudgetUsdPerRole": CAP,
        "roles": {},
    }
    for role in MODELS:
        v = session(role, root, a.product, pair, cpid, cli, operator, pin)
        out["roles"][role] = v
        out["totalClientEstimatedUsd"] = sum(
            r["clientEstimatedUsd"] or 0 for r in out["roles"].values()
        )
        out["qualified"] = (
            set(out["roles"]) == set(MODELS)
            and all(r["qualified"] for r in out["roles"].values())
            and out["totalClientEstimatedUsd"] < 2
        )
        a.output.write_text(json.dumps(out, indent=2) + "\n")
        print(
            role,
            "qualified",
            v["qualified"],
            "reason",
            v["knownRefusal"],
            "exit",
            v["exit"],
            "tools",
            v["toolEvents"],
            "API estimate",
            v["clientEstimatedUsd"],
            "seconds",
            v["elapsedSeconds"],
            flush=True,
        )
        if not v["qualified"]:
            break

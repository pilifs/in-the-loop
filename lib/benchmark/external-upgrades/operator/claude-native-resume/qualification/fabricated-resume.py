"""Stock Claude Code against a private loopback Messages endpoint; only generated fake credentials are present."""

import uuid
import shutil
import hashlib
import http.server
import json
from pathlib import Path
import subprocess
import threading
import time

base = Path("/case/work")
settings = json.loads((base / "test-settings.json").read_bytes())
model = settings["model"]
nonce = settings["nonce"]
realtool = "mcp__neutral_case__case_command"
neutral = base / "neutral"
neutral.mkdir()
home = base / settings["sentinels"]["homePath"]
home.mkdir()
config = home / ".claude"
config.mkdir()
(neutral / "CLAUDE.md").write_text(settings["sentinels"]["projectInstructions"])
(home / "CLAUDE.md").write_text(settings["sentinels"]["homeInstructions"])
(config / "CLAUDE.md").write_text(settings["sentinels"]["userInstructions"])
(config / "projects").mkdir()
(config / "projects/earlier.jsonl").write_text(
    json.dumps({"synthetic": settings["sentinels"]["priorTranscript"]})
)
(neutral / "AGENTS.md").write_text(settings["sentinels"]["agentsInstructions"])
(neutral / ".claude/rules").mkdir(parents=True)
(neutral / ".claude/rules/private.md").write_text(settings["sentinels"]["localRules"])
mem = config / "projects/-case-work-neutral/memory"
mem.mkdir(parents=True)
(mem / "MEMORY.md").write_text(settings["sentinels"]["globalMemory"])
(neutral / ".mcp.json").write_text(
    json.dumps(
        {
            "mcpServers": {
                settings["sentinels"]["unlistedMcp"]: {
                    "type": "stdio",
                    "command": "/usr/bin/python3",
                    "args": ["-c", "open('/case/work/unlisted-started','w').write('unexpected')"],
                }
            }
        }
    )
)
(config / "settings.json").write_text(
    json.dumps(
        {
            "hooks": {
                "UserPromptSubmit": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": "printf '%s' "
                                + settings["sentinels"]["userHook"]
                                + "; touch /case/work/unlisted-hook",
                            }
                        ]
                    }
                ]
            }
        }
    )
)
tmp = base / settings["sentinels"]["controlTempPath"]
tmp.mkdir()
private = base / "control-only"
private.mkdir()
(private / "withheld.txt").write_text(settings["sentinels"]["controlPrivate"])
marker = json.loads((base / "test-settings.json").read_bytes())["sentinels"]
subject_code = (base / "subject_cmd.py").read_text()
registry = {
    "mcpServers": {
        "neutral_case": {
            "type": "stdio",
            "command": "/usr/bin/python3",
            "args": ["/case/work/public/lib/benchmark/external-upgrades/operator/relay.py"],
        }
    }
}
mcp = base / (settings["sentinels"]["mcpInternalPath"] + ".json")
mcp.write_text(json.dumps(registry))
# The canary command itself is selected by the dummy model service. The real client dispatches it.
tool_event = {
    "type": "tool_use",
    "id": "toolu_case_sample",
    "name": realtool,
    "input": {"argv": ["python3", "-c", subject_code, nonce]},
}
direct_event = {
    "type": "tool_use",
    "id": "toolu_builtin_canary",
    "name": "Read",
    "input": {"file_path": "/case/work/control-only/withheld.txt"},
}
rows = []
urls = []
raw_results = {}
native_output = base / "cli.process.log"


def compact_meta(value):
    types = {}
    for k, v in (value or {}).items():
        if isinstance(v, str):
            try:
                inner = json.loads(v)
            except (ValueError, TypeError):
                inner = None
            types[k] = sorted(inner) if isinstance(inner, dict) else "string"
        else:
            types[k] = type(v).__name__
    return types


def decode_result(text):
    if isinstance(text, str):
        return text
    if isinstance(text, list):
        return "\n".join(str(t.get("text", "")) for t in text if isinstance(t, dict))
    return ""


def respond(handler, payload, index):
    # Match Anthropic's SSE Messages wire format or its nonstreaming response, according to the stock request.
    phase = active[0]
    if phase == "initial":
        blocks = [tool_event]
        stop = "tool_use"
    elif phase == "decoy":
        blocks = [{"type": "text", "text": decoy_nonce}]
        stop = "end_turn"
    else:
        blocks = [{"type": "text", "text": "Synthetic continued session."}]
        stop = "end_turn"
    head = {
        "id": "msg_synthetic_" + str(index),
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [],
        "stop_reason": None,
        "stop_sequence": None,
        "usage": {"input_tokens": 4, "output_tokens": 1},
    }
    handler.send_response(200)
    handler.send_header("request-id", "req_synthetic_local")
    if not payload.get("stream"):
        message = {**head, "content": blocks, "stop_reason": stop}
        data = json.dumps(message).encode()
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
        return
    events = [("message_start", {"type": "message_start", "message": head})]
    for i, b in enumerate(blocks):
        if b["type"] == "tool_use":
            start = {**b, "input": {}}
            delta = {"type": "input_json_delta", "partial_json": json.dumps(b["input"])}
        else:
            start = {"type": "text", "text": ""}
            delta = {"type": "text_delta", "text": b["text"]}
        events.extend(
            [
                (
                    "content_block_start",
                    {"type": "content_block_start", "index": i, "content_block": start},
                ),
                ("content_block_delta", {"type": "content_block_delta", "index": i, "delta": delta}),
                ("content_block_stop", {"type": "content_block_stop", "index": i}),
            ]
        )
    events.extend(
        [
            (
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": stop, "stop_sequence": None},
                    "usage": {"output_tokens": 12},
                },
            ),
            ("message_stop", {"type": "message_stop"}),
        ]
    )
    out = "".join(
        "event: " + name + "\ndata: " + json.dumps(value) + "\n\n" for name, value in events
    ).encode()
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Content-Length", str(len(out)))
    handler.end_headers()
    handler.wfile.write(out)


class Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        urls.append({"method": "GET", "path": self.path.split("?")[0]})
        self.send_error(404)

    def do_POST(self):
        route = self.path.split("?")[0]
        urls.append({"method": "POST", "path": route})
        n = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(n)
        if route == "/v1/messages/count_tokens":
            data = b'{"input_tokens":12}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if route != "/v1/messages":
            self.send_error(404)
            return
        d = json.loads(raw)
        names = [t.get("name", t.get("type")) for t in d.get("tools", [])]
        serial = json.dumps(d, ensure_ascii=False)
        hits = sorted(k for k, v in marker.items() if v in serial)
        visible_tool_results = []
        for msg in d.get("messages", []):
            for item in msg["content"] if isinstance(msg.get("content"), list) else []:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    uid = item.get("tool_use_id")
                    txt = decode_result(item.get("content"))
                    raw_results[uid] = {"error": bool(item.get("is_error")), "content": txt}
                    visible_tool_results.append(uid)
        row = {
            "phase": active[0],
            "wireBodyBytes": len(raw),
            "sawPriorPositiveCommand": "toolu_case_sample" in serial,
            "sawOwnPriorToolResult": any(i == "toolu_case_sample" for i in visible_tool_results),
            "sawOwnNonce": settings["nonce"] in serial,
            "sawDecoy": decoy_nonce in serial,
            "model": d.get("model"),
            "effort": (d.get("output_config") or {}).get("effort"),
            "tools": names,
            "metadataShape": compact_meta(d.get("metadata")),
            "wireToolContracts": [
                {
                    "name": t.get("name"),
                    "type": t.get("type", "custom"),
                    "deferred": t.get("defer_loading", False),
                    "inputProperties": sorted((t.get("input_schema") or {}).get("properties", {})),
                }
                for t in d.get("tools", [])
            ],
            "privateSentinelsInPayload": hits,
            "syntheticNeutralPromptPresent": settings["prompt"] in serial,
            "neutralWorkingDirectoryInPayload": str(neutral) in serial,
            "sessionToolResultIds": visible_tool_results,
            "wireBodySha256": hashlib.sha256(raw).hexdigest(),
            "bodyKeys": sorted(d),
            "syntheticApiKeyOnly": self.headers.get("x-api-key") == "fixture-only-loopback-key"
            and not self.headers.get("Authorization"),
        }
        index = len(rows)
        rows.append(row)
        if d.get("model") != model or index > 6:
            self.send_error(400)
            return
        respond(self, d, index)


active = [""]
decoy_nonce = "synthetic-decoy-" + uuid.uuid4().hex
secure = home / "separate-authentication-store"
secure.mkdir()
privateA = home / "case-state-A"
privateA.mkdir()
privateB = home / "case-state-B"
privateB.mkdir()
privateShadow = home / "case-shadow"
emptySecure = home / "empty-secure-store"
emptySecure.mkdir()
(secure / ".credentials.json").write_text(
    json.dumps(
        {
            "claudeAiOauth": {
                "accessToken": "fabricated-synthetic-credential",
                "refreshToken": "fabricated-synthetic-renewal",
                "expiresAt": int(time.time() * 1000) + 3600000,
                "scopes": ["user:inference"],
                "subscriptionType": "max",
            }
        }
    )
)
(secure / ".credentials.json").chmod(0o600)
cred_digest = hashlib.sha256((secure / ".credentials.json").read_bytes()).hexdigest()
idA = str(uuid.uuid4())
idB = str(uuid.uuid4())
receipts = []
with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake) as server:
    threading.Thread(target=server.serve_forever, daemon=True).start()
    common = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "LANG": "C.UTF-8",
        "TZ": "UTC",
        "CLAUDE_SECURESTORAGE_CONFIG_DIR": str(secure),
        "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{server.server_address[1]}",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "DISABLE_TELEMETRY": "1",
        "DISABLE_ERROR_REPORTING": "1",
        "NO_PROXY": "127.0.0.1",
        "LD_LIBRARY_PATH": str(base / "runtime-libs"),
        "ENABLE_TOOL_SEARCH": "false",
        "CLAUDE_CODE_MAX_RETRIES": "0",
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "2048",
    }

    # Exercise first-party secure-storage selection with fabricated fixtures only; retain a boolean and the reported auth method.
    def auth(where):
        env = {
            **common,
            "CLAUDE_CONFIG_DIR": str(privateA),
            "CLAUDE_SECURESTORAGE_CONFIG_DIR": str(where),
        }
        r = subprocess.run(
            [str(base / "claude"), "auth", "status", "--json"],
            env=env,
            cwd=neutral,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=8,
        )
        try:
            d = json.loads(r.stdout)
            return {
                "exit": r.returncode,
                "loggedIn": d.get("loggedIn"),
                "authMethod": d.get("authMethod"),
            }
        except ValueError:
            return {"exit": r.returncode, "loggedIn": False, "authMethod": None}

    secure_status = auth(secure)
    empty_status = auth(emptySecure)

    def launch(label, state, session, mode, message):
        active[0] = label
        env = {
            **common,
            "CLAUDE_CONFIG_DIR": str(state),
            "ANTHROPIC_API_KEY": "fixture-only-loopback-key",
        }
        argv = [
            str(base / "claude"),
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
            realtool,
            "--max-turns",
            "1",
            "--max-budget-usd",
            "0.75",
            "--settings",
            json.dumps(
                {
                    "claudeMdExcludes": [
                        "**/CLAUDE.md",
                        "**/CLAUDE.local.md",
                        "**/AGENTS.md",
                        "**/.claude/rules/**",
                    ],
                    "autoMemoryEnabled": False,
                    "disableAllHooks": True,
                }
            ),
            "--output-format",
            "stream-json",
            "--verbose",
            mode,
            session,
            "--",
            message,
        ]
        before = len(rows)
        r = subprocess.run(
            argv, env=env, cwd=neutral, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=14
        )
        items = []
        for line in r.stdout.splitlines():
            try:
                items.append(json.loads(line))
            except ValueError:
                pass
        init = next(
            (e for e in items if e.get("type") == "system" and e.get("subtype") == "init"), {}
        )
        finish = next((e for e in items if e.get("type") == "result"), {})
        receipts.append(
            {
                "phase": label,
                "wireRequests": len(rows) - before,
                "initSessionMatches": init.get("session_id") == session,
                "cliExit": r.returncode,
                "type": finish.get("subtype"),
                "toolUseCount": sum(
                    b.get("type") == "tool_use"
                    for e in items
                    if e.get("type") == "assistant"
                    for b in e.get("message", {}).get("content", [])
                ),
                "missingInitialSession": not bool(init),
                "diagnostic": (r.stderr.decode(errors="replace")[-260:] if not init else None),
            }
        )

    launch("initial", privateA, idA, "--session-id", settings["prompt"])
    launch("decoy", privateB, idB, "--session-id", "Wholly separate synthetic session " + decoy_nonce)
    paths = list(privateA.rglob(idA + ".jsonl"))
    original = paths[0] if len(paths) == 1 else None
    beforeShadow = hashlib.sha256(original.read_bytes()).hexdigest() if original else None
    if original:
        # Shadow the role's own transcript and no account storage. The real role's transcript isn't changed by the preauthorization pass.
        shadowFile = privateShadow / original.relative_to(privateA)
        shadowFile.parent.mkdir(parents=True)
        shutil.copyfile(original, shadowFile)
        launch(
            "shadow",
            privateShadow,
            idA,
            "--resume",
            "Continue this same synthetic session and inspect the prior tool result.",
        )
    unchangedBeforeResume = (
        original is not None and hashlib.sha256(original.read_bytes()).hexdigest() == beforeShadow
    )
    launch(
        "resume",
        privateA,
        idA,
        "--resume",
        "Continue this same synthetic session and inspect the prior tool result.",
    )
    server.shutdown()
result = {
    "model": model,
    "requests": rows,
    "clientCalls": receipts,
    "privateStateSeparated": not list(privateA.rglob(idB + ".jsonl"))
    and not list(privateB.rglob(idA + ".jsonl")),
    "recordedCaseTranscript": original is not None,
    "shadowLeftOriginalUnchanged": unchangedBeforeResume,
    "credentialSeparate": not list(privateA.rglob(".credentials.json"))
    and not list(privateB.rglob(".credentials.json")),
    "syntheticCredentialUnchanged": hashlib.sha256(
        (secure / ".credentials.json").read_bytes()
    ).hexdigest()
    == cred_digest,
    "syntheticAuthStatus": secure_status,
    "emptyAuthStatus": empty_status,
    "requestPaths": urls,
    "initialToolSet": rows[0]["tools"] if rows else [],
    "exit": 0,
    "toolResponses": {},
    "noLiveInference": True,
}
print(json.dumps(result))

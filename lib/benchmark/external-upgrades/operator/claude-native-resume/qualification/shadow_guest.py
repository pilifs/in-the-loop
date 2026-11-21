import hashlib
import http.server
import json
import subprocess
import threading
from pathlib import Path

base = Path("/case/work")
spec = json.loads((base / "measure.json").read_bytes())
records = []
config = base / "state"
config.mkdir(exist_ok=True)
secure = base / "empty-secure"
secure.mkdir(exist_ok=True)


class Sink(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_error(404)

    def do_POST(self):
        if self.path.split("?")[0] != "/v1/messages":
            self.send_error(404)
            return
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        d = json.loads(raw)
        serialized = json.dumps(d, ensure_ascii=False)
        restored = []
        for msg in d.get("messages", []):
            for item in msg.get("content", []) if isinstance(msg.get("content"), list) else []:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    restored.append(json.dumps(item.get("content"), ensure_ascii=False))
        records.append(
            {
                "wireBytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "model": d["model"],
                "effort": (d.get("output_config") or {}).get("effort"),
                "tools": [v.get("name") for v in d.get("tools", [])],
                "initialOrNewPromptPresent": any(
                    spec["prompt"] in (part if isinstance(part, str) else str(part.get("text", "")))
                    for message in d.get("messages", [])
                    for part in (
                        message["content"]
                        if isinstance(message.get("content"), list)
                        else [message.get("content", "")]
                    )
                ),
                "restoresOwnResult": any(spec["nonce"] in x for x in restored),
                "restoresForeignNonce": any(s in serialized for s in spec.get("foreign", [])),
                "hasOnlyFakeApiKey": self.headers.get("x-api-key") == "fixture-only-loopback-key"
                and not self.headers.get("Authorization"),
                "maxTokens": d.get("max_tokens"),
            }
        )
        events = [
            (
                "message_start",
                {
                    "type": "message_start",
                    "message": {
                        "id": "msg_local_shadow",
                        "type": "message",
                        "role": "assistant",
                        "model": d["model"],
                        "content": [],
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                    },
                },
            ),
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
            ),
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": "Synthetic shadow input measured."},
                },
            ),
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
            (
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                    "usage": {"output_tokens": 2},
                },
            ),
            ("message_stop", {"type": "message_stop"}),
        ]
        out = "".join("event: " + k + "\ndata: " + json.dumps(v) + "\n\n" for k, v in events).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Sink) as server:
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/case/work",
        "LANG": "C.UTF-8",
        "TZ": "UTC",
        "TMPDIR": "/tmp",
        "CLAUDE_CONFIG_DIR": str(config),
        "CLAUDE_SECURESTORAGE_CONFIG_DIR": str(secure),
        "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{server.server_address[1]}",
        "ANTHROPIC_API_KEY": "fixture-only-loopback-key",
        "NO_PROXY": "127.0.0.1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "DISABLE_TELEMETRY": "1",
        "DISABLE_ERROR_REPORTING": "1",
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        "ENABLE_TOOL_SEARCH": "false",
        "CLAUDE_CODE_MAX_RETRIES": "0",
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "1024",
        "LD_LIBRARY_PATH": "/case/work/runtime-libs",
    }
    args = [
        str(base / "claude"),
        "-p",
        "--model",
        spec["model"],
        "--effort",
        "high",
        "--restricted",
        "--tools",
        "",
        "--strict-mcp-config",
        "--mcp-config",
        str(base / "mcp.json"),
        "--disable-slash-commands",
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        "mcp__neutral_case__case_command",
        "--max-turns",
        "1",
        "--max-budget-usd",
        "0.75",
        "--settings",
        json.dumps(spec["options"]),
        "--output-format",
        "stream-json",
        "--verbose",
        spec["mode"],
        spec["session"],
        "--",
        spec["prompt"],
    ]
    r = subprocess.run(
        args,
        env=env,
        cwd="/srv",
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=25,
    )
    server.shutdown()
if len(records) != 1 or not records[0]["hasOnlyFakeApiKey"] or r.returncode != 0:
    events = []
    for line in r.stdout.splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if obj.get("type") == "result":
            events.append(
                {
                    "type": obj.get("subtype"),
                    "error": obj.get("is_error"),
                    "text": str(obj.get("result", ""))[-180:],
                }
            )
    print(
        json.dumps(
            {
                "diagnostic": {
                    "requests": len(records),
                    "rows": records,
                    "exit": r.returncode,
                    "events": events,
                    "stderr": r.stderr.decode(errors="replace")[-140:],
                }
            }
        )
    )
    raise SystemExit(2)
print(json.dumps(records[0]))

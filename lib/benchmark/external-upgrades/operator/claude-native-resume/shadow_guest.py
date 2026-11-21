"""Read one stock CLI request at loopback, return a valid mock answer and emit only bounded measurement metadata."""

import hashlib
import http.server
import json
from pathlib import Path
import subprocess
import threading
from signals import contained

BASE = Path("/case/work")
TOOLS = Path("/opt/operator-shadow")


def visible_parts(messages):
    for message in messages:
        data = message.get("content", [])
        for part in data if isinstance(data, list) else [data]:
            if isinstance(part, str):
                yield part
            elif part.get("type") == "text":
                yield part.get("text", "")
            elif part.get("type") == "tool_result":
                result = part.get("content", [])
                for item in result if isinstance(result, list) else [result]:
                    if isinstance(item, str):
                        yield item
                    elif item.get("type") == "text":
                        yield item.get("text", "")


def synthetic_answer(model):
    message = {
        "id": "msg_local_shadow",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [],
        "stop_reason": None,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    events = [
        ("message_start", {"type": "message_start", "message": message}),
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
                "delta": {"type": "text_delta", "text": "Synthetic shadow measured."},
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
    return "".join(f"event: {kind}\ndata: {json.dumps(data)}\n\n" for kind, data in events).encode()


def main():
    spec = json.loads((BASE / "measure.json").read_bytes())
    seen = []

    class Sink(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_error(404)

        def do_POST(self):
            if self.path.split("?")[0] != "/v1/messages":
                self.send_error(404)
                return
            advertised = self.headers.get("Content-Encoding")
            raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if advertised not in (None, "identity"):
                self.send_error(400)
                return
            body = json.loads(raw)
            msgs = body.get("messages", [])
            signals = set()
            contains_prompt = False
            for part in visible_parts(msgs):
                if spec["prompt"] in part:
                    contains_prompt = True
                if part:
                    signals.update(contained(part))
            uid = (body.get("metadata") or {}).get("user_id", "{}")
            try:
                session_match = json.loads(uid).get("session_id") == spec["session"]
            except (ValueError, TypeError, AttributeError):
                session_match = False
            result_ids = {
                hashlib.sha256(str(part.get("tool_use_id")).encode()).hexdigest()
                for message in msgs
                for part in (message["content"] if isinstance(message.get("content"), list) else [])
                if isinstance(part, dict) and part.get("type") == "tool_result"
            }
            expected_result_id = spec.get("expectedToolResultIdSha256")
            need = spec.get("expectedBlockSha256")
            seen.append(
                {
                    "wireBytes": len(raw),
                    "wireSha256": hashlib.sha256(raw).hexdigest(),
                    "model": body.get("model"),
                    "effort": (body.get("output_config") or {}).get("effort"),
                    "tools": [t.get("name") for t in body.get("tools", [])],
                    "promptPresent": contains_prompt,
                    "priorAssistantMessages": sum(m.get("role") == "assistant" for m in msgs),
                    "priorSignalRestored": not need or need in signals,
                    "priorToolResultIdRestored": not expected_result_id
                    or expected_result_id in result_ids,
                    "sessionMatched": session_match,
                    "identityEncoding": True,
                    "fakeKeyOnly": self.headers.get("x-api-key") == "fixture-only-loopback-key"
                    and not self.headers.get("Authorization"),
                    "maxOutputTokens": body.get("max_tokens"),
                }
            )
            answer = synthetic_answer(spec["model"])
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(answer)))
            self.end_headers()
            self.wfile.write(answer)

    config = BASE / "state"
    config.mkdir(exist_ok=True)
    secure = BASE / "empty-secure"
    secure.mkdir(exist_ok=True)
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
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(spec["maxOutputTokens"]),
            "DISABLE_COMPACT": "1",
            "CLAUDE_CODE_GZIP_REQUEST_BODY": "0",
            "CLAUDE_CODE_INCREMENTAL_REQUEST_BODY": "0",
            "LD_LIBRARY_PATH": str(TOOLS / "lib"),
        }
        argv = [
            str(TOOLS / "claude"),
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
            str(TOOLS / "mcp.json"),
            "--disable-slash-commands",
            "--permission-mode",
            "dontAsk",
            "--allowedTools",
            "mcp__neutral_case__case_command",
            "--max-turns",
            "1",
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
        native = subprocess.run(
            argv,
            env=env,
            cwd="/srv",
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        server.shutdown()
    if native.returncode or len(seen) != 1:
        raise SystemExit("Shadow did not emit exactly one successful locally measured role request.")
    print(json.dumps(seen[0]))


if __name__ == "__main__":
    main()

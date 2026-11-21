"""Stock one-turn Fable on synthetic MCP values inside a credentialless offline control namespace."""

import http.server
import json
from pathlib import Path
import subprocess
import sys
import shutil
import threading
import uuid

root = Path("/case/work")
image = Path("/opt/operator-shadow")
sys.path.insert(0, str(image))
sys.path.insert(0, str(image / "public/lib/benchmark/external-upgrades/operator"))
from signals import contained, signal  # noqa: E402
from measure import visible_parts  # noqa: E402
import mcp_server  # noqa: E402

spec = json.loads((root / "synthetic.json").read_bytes())
tool = "mcp__neutral_case__case_command"
model = spec["model"]


def values(shape, group, member):
    tag = f"synthetic-{group}-{member}"
    if group == 1:
        return tag + " short input\n"
    if shape == "error":
        return "sh: 1: synthetic-bin: not found\n"
    if shape == "short":
        return tag + " short output\n"
    if shape == "empty":
        return "" if member == 2 else tag + " with a sibling\n"
    if shape == "plain":
        return tag + " " + " ".join(f"{i:04}" for i in range(2600)) + "\n"
    if shape == "xml":
        return (
            tag
            + "\n"
            + "".join(
                f'    <element id="{i}" value="tag">sample text node</element>\n' for i in range(330)
            )
        )
    if shape == "json":
        return json.dumps({f"key{i:05}": [i, "sample"] for i in range(420)}, indent=2) + "\n"
    if shape == "dense":
        return tag + "\n" + "".join(chr(33 + ((i * 43 + 73) % 90)) for i in range(14890)) + "\n"
    if shape == "unicode":
        return tag + "\n" + "".join(chr(0x4E00 + i % 1300) for i in range(4300)) + "\n"
    if shape == "control":
        return tag + "\n" + "\x01" * 13000 + "\n"
    if shape == "escaped-unicode":
        return tag + "\n" + "".join(chr(0x2028 + i % 2) for i in range(5000)) + "\n"
    if shape == "escapes":
        return tag + "\n" + '\t\x1b\\"\r\f\u0001' * 2100 + "\n"
    raise ValueError("unknown shape")


def truncated(raw):
    shown = raw.encode()[:12000].decode(errors="replace")
    if len(shown) < len(raw):
        shown += "\n[Output truncated. Rerun with a narrower projection.]"
    return shown


def mcp():
    for line in sys.stdin.buffer:
        req = json.loads(line)
        if "id" not in req:
            continue

        def execute(item):
            args = json.loads(item["arguments"])["argv"]
            group, member = map(int, args[1:])
            result = {
                "exit": 127 if spec["shape"] == "error" else 0,
                "output": truncated(values(spec["shape"], group, member)),
            }
            with (root / "audit.jsonl").open("a") as f:
                f.write(
                    json.dumps(
                        {
                            "group": group,
                            "member": member,
                            "length": len(result["output"].encode()),
                            "signal": signal(result["output"]),
                        }
                    )
                    + "\n"
                )
            return result

        print(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": req["id"],
                    "result": mcp_server.reply(req["method"], req.get("params", {}), execute),
                }
            ),
            flush=True,
        )


def events(turn):
    if turn <= 2:
        content = [
            {
                "type": "tool_use",
                "id": f"toolu_public_{turn}_{i}",
                "name": tool,
                "input": {"argv": ["synthetic", str(turn), str(i)]},
            }
            for i in (1, 2)
        ]
        stop = "tool_use"
    else:
        content = [{"type": "text", "text": "Public synthetic complete."}]
        stop = "end_turn"
    head = {
        "id": f"msg_sample_{turn}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [],
        "stop_reason": None,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    rows = [("message_start", {"type": "message_start", "message": head})]
    for i, b in enumerate(content):
        if b["type"] == "tool_use":
            start = {**b, "input": {}}
            delta = {"type": "input_json_delta", "partial_json": json.dumps(b["input"])}
        else:
            start = {"type": "text", "text": ""}
            delta = {"type": "text_delta", "text": b["text"]}
        rows.extend(
            [
                (
                    "content_block_start",
                    {"type": "content_block_start", "index": i, "content_block": start},
                ),
                ("content_block_delta", {"type": "content_block_delta", "index": i, "delta": delta}),
                ("content_block_stop", {"type": "content_block_stop", "index": i}),
            ]
        )
    rows.extend(
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
    return "".join(f"event: {k}\ndata: {json.dumps(v)}\n\n" for k, v in rows).encode()


def main():
    state = root / "state"
    secure = root / "empty-secure"
    state.mkdir()
    secure.mkdir()
    session = str(uuid.uuid4())
    catalog = root / "registry.json"
    catalog.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "neutral_case": {
                        "type": "stdio",
                        "command": "/usr/bin/python3",
                        "args": ["/case/work/stock_guest.py", "mcp"],
                    }
                }
            }
        )
    )
    wire = []
    turn = 0

    class Sink(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.path.split("?")[0] != "/v1/messages":
                self.send_error(404)
                return
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            body = json.loads(raw)
            msgs = body["messages"]
            allvalues = set()
            for text in visible_parts(msgs):
                allvalues.update(contained(text))
            previous = []
            observed = {}
            for msg in msgs:
                for part in msg["content"] if isinstance(msg["content"], list) else []:
                    if part.get("type") != "tool_result":
                        continue
                    rid = part["tool_use_id"]
                    blocks = part.get("content", [])
                    texts = (
                        [blocks]
                        if isinstance(blocks, str)
                        else [b.get("text", "") for b in blocks if isinstance(b, dict)]
                    )
                    observed[rid] = {
                        "lengths": [len(x.encode()) for x in texts],
                        "hasPersistenceMarker": any(
                            "persisted-output" in x or "tool-results/" in x for x in texts
                        ),
                        "hasTypicalTruncationMarker": any("truncat" in x.lower() for x in texts),
                        "types": [b["type"] for b in blocks if isinstance(b, dict)]
                        if isinstance(blocks, list)
                        else ["string"],
                    }
            if turn > 1:
                for i in (1, 2):
                    kind = truncated(values(spec["shape"], turn - 1, i))
                    rid = f"toolu_public_{turn - 1}_{i}"
                    previous.append(
                        {
                            "idPresent": rid in observed,
                            "directVisiblePresent": not kind or signal(kind) in allvalues,
                            "brokerValueBytes": len(kind.encode()),
                            **observed.get(rid, {}),
                        }
                    )
            wire.append(
                {
                    "step": turn,
                    "wireBytes": len(raw),
                    "encoding": self.headers.get("Content-Encoding") in (None, "identity"),
                    "model": body["model"],
                    "effort": body.get("output_config", {}).get("effort"),
                    "tools": [v["name"] for v in body["tools"]],
                    "caseOnlySession": json.loads(body["metadata"]["user_id"])["session_id"]
                    == session,
                    "fakeKeyOnly": self.headers.get("x-api-key") == "synthetic-only"
                    and not self.headers.get("Authorization"),
                    "maxTokens": body["max_tokens"],
                    "promptPresent": any(
                        f"Synthetic wire step {turn}." in x for x in visible_parts(msgs)
                    ),
                    "priorAssistantMessages": sum(m["role"] == "assistant" for m in msgs),
                    "previous": previous,
                }
            )
            out = events(turn)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

    cli = []
    cloned_sidecars = 0
    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), Sink) as server:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(root),
            "TMPDIR": str(root / "tmp"),
            "LANG": "C.UTF-8",
            "TZ": "UTC",
            "CLAUDE_CONFIG_DIR": str(state),
            "CLAUDE_SECURESTORAGE_CONFIG_DIR": str(secure),
            "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{server.server_address[1]}",
            "ANTHROPIC_API_KEY": "synthetic-only",
            "NO_PROXY": "127.0.0.1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_TELEMETRY": "1",
            "DISABLE_ERROR_REPORTING": "1",
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            "ENABLE_TOOL_SEARCH": "false",
            "CLAUDE_CODE_MAX_RETRIES": "0",
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "2048",
            "DISABLE_COMPACT": "1",
            "CLAUDE_CODE_GZIP_REQUEST_BODY": "0",
            "CLAUDE_CODE_INCREMENTAL_REQUEST_BODY": "0",
            "LD_LIBRARY_PATH": str(image / "lib"),
        }
        for turn in (1, 2, 3):
            if turn == 3:
                fresh = root / "independent-resume-state"
                fresh.mkdir()
                original = next((state / "projects").glob("*/" + session + ".jsonl"))
                dest = fresh / original.relative_to(state)
                dest.parent.mkdir(parents=True)
                shutil.copyfile(original, dest)
                saved = original.parent / session / "tool-results"
                if saved.is_dir():
                    for ent in saved.rglob("*"):
                        if ent.is_file() and not ent.is_symlink():
                            to = fresh / ent.relative_to(state)
                            to.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(ent, to)
                            cloned_sidecars += 1
                env["CLAUDE_CONFIG_DIR"] = str(fresh)
            argv = [
                str(image / "claude"),
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
                str(catalog),
                "--disable-slash-commands",
                "--permission-mode",
                "dontAsk",
                "--allowedTools",
                tool,
                "--max-turns",
                "1",
                "--settings",
                json.dumps(spec["options"]),
                "--output-format",
                "stream-json",
                "--verbose",
                "--session-id" if turn == 1 else "--resume",
                session,
                "--",
                f"Synthetic wire step {turn}.",
            ]
            r = subprocess.run(
                argv,
                cwd="/srv",
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=16,
            )
            native = [json.loads(line) for line in r.stdout.splitlines() if line.startswith(b"{")]
            terminal = next((e for e in native if e.get("type") == "result"), {})
            cli.append(
                {
                    "exit": r.returncode,
                    "subtype": terminal.get("subtype"),
                    "calls": sum(
                        b.get("type") == "tool_use"
                        for e in native
                        if e.get("type") == "assistant"
                        for b in e.get("message", {}).get("content", [])
                    ),
                }
            )
        server.shutdown()
    audits = (
        [json.loads(s) for s in (root / "audit.jsonl").read_text().splitlines()]
        if (root / "audit.jsonl").exists()
        else []
    )
    print(
        json.dumps(
            {
                "shape": spec["shape"],
                "wire": wire,
                "cli": cli,
                "brokerCompleted": [(v["group"], v["member"]) for v in audits],
                "copiedResultFiles": cloned_sidecars,
                "noActualModel": True,
            }
        )
    )


if __name__ == "__main__":
    mcp() if sys.argv[1:] == ["mcp"] else main()

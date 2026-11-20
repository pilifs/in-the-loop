"""Capture the stock CLI's advertised tools at a loopback-only mock before model inference."""

import http.server
import json
import os
from pathlib import Path
import subprocess
import threading

base = Path("/case/work/transport")
pin = json.loads(Path("/opt/product-pin.json").read_text())
requests = []


def catalog(data):
    tools = list(data.get("tools", []))
    for item in data["input"]:
        if item.get("type") == "additional_tools":
            tools.extend(item["tools"])
    exposed = {}
    nested = set()
    for tool in tools:
        group = tool.get("name", tool["type"])
        children = tool.get("tools", [])
        exposed[group] = [child["name"] for child in children]
        for child in children:
            desc = child.get("description", "")
            for name in ("exec_command", "apply_patch", "view_image", "web__run"):
                if "### `" + name + "`" in desc:
                    nested.add(name)
    # A custom MCP being listed does not remove the host's native tool namespaces.
    would_allow = bool(tools) and all(
        x.get("type") == "function" and x.get("name") == "mcp__neutral_case__case_command"
        for x in tools
    )
    return {
        "model": data["model"],
        "namespaces": exposed,
        "nestedFileOrNetworkTools": sorted(nested),
        "caseMcpNamespaceMentioned": "mcp__neutral_case" in json.dumps(data["input"]),
        "exactCaseToolOnly": would_allow,
    }


class Sink(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_error(404)

    def do_POST(self):
        if self.path != "/v1/responses":
            self.send_error(404)
            return
        data = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if self.headers.get("Content-Encoding") == "zstd":
            import compression.zstd

            data = compression.zstd.decompress(data)
        requests.append(catalog(json.loads(data)))
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error":{"message":"Synthetic request captured; inference disabled"}}')


with http.server.HTTPServer(("127.0.0.1", 0), Sink) as server:
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    stages = {}
    for role in ("preparation", "plannerAndProver"):
        state = base / ("empty-" + role)
        state.mkdir(mode=0o700)
        config = [
            'model_provider="synthetic"',
            'model_providers.synthetic.name="Synthetic"',
            f'model_providers.synthetic.base_url="http://127.0.0.1:{port}/v1"',
            'model_providers.synthetic.wire_api="responses"',
            "model_providers.synthetic.requires_openai_auth=false",
            "model_providers.synthetic.supports_websockets=false",
            "model_providers.synthetic.request_max_retries=0",
            "model_providers.synthetic.stream_max_retries=0",
            'web_search="disabled"',
            'mcp_servers.neutral_case.command="python3"',
            "mcp_servers.neutral_case.required=true",
            "mcp_servers.neutral_case.args="
            + json.dumps(
                [
                    str(base / "public/lib/benchmark/external-upgrades/operator/mcp_server.py"),
                    "--product",
                    "/absent",
                    "--case",
                    "/absent",
                ]
            ),
            'mcp_servers.neutral_case.enabled_tools=["case_command"]',
            'model_reasoning_effort="high"',
        ]
        argv = [
            str(base / "codex"),
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "-m",
            pin[role]["model"],
            "-s",
            "read-only",
        ]
        for value in config:
            argv.extend(["-c", value])
        for feature in (
            "apps",
            "shell_tool",
            "unified_exec",
            "multi_agent",
            "multi_agent_v2",
            "code_mode",
        ):
            argv.extend(["--disable", feature])
        argv.extend(["--enable", "code_mode_host", pin["neutralPrompt"]])
        before = len(requests)
        proc = subprocess.run(
            argv,
            env={
                **os.environ,
                "CODEX_HOME": str(state),
                "NO_PROXY": "127.0.0.1",
                "CODEX_DISABLE_NETWORK_TELEMETRY": "1",
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
        if len(requests) != before + 1 or proc.returncode == 0:
            raise RuntimeError("stock client did not stop at the test transport")
        stages[role] = requests[-1]
    server.shutdown()
print(json.dumps(stages))

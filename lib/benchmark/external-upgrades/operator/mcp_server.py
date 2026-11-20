"""Expose the case namespace to an authorized client on the control side over stdio."""

import argparse
import json
from pathlib import Path
import sys

import control


def reply(method, parameters, execute):
    if method == "initialize":
        return {
            "protocolVersion": parameters["protocolVersion"],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "neutral-case", "version": "1"},
        }
    if method == "tools/list":
        tool = control.TOOL
        return {
            "tools": [
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": tool["parameters"],
                }
            ]
        }
    if method == "tools/call":
        if set(parameters) - {"name", "arguments", "_meta"}:
            raise ValueError("unexpected tool call fields")
        result = execute(
            {
                "type": "function_call",
                "name": parameters["name"],
                "arguments": json.dumps(parameters["arguments"]),
            }
        )
        return {
            "content": [{"type": "text", "text": json.dumps(result)}],
            "isError": result["exit"] != 0,
        }
    if method == "ping":
        return {}
    if method in ("resources/list", "resources/templates/list", "prompts/list"):
        key = {
            "resources/list": "resources",
            "resources/templates/list": "resourceTemplates",
            "prompts/list": "prompts",
        }[method]
        return {key: []}
    raise ValueError("unregistered MCP method")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    args = parser.parse_args()

    # Roots are fixed by the trusted launcher before reading any model-controlled bytes.
    def execute(item):
        return control.execute(args.product, args.case, item)

    while raw := sys.stdin.buffer.readline(2 * 1024 * 1024 + 1):
        try:
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("oversize control message")
            req = json.loads(raw)
            if req.get("jsonrpc") != "2.0":
                raise ValueError("invalid control message")
            if "id" not in req:
                continue
            try:
                out = {"result": reply(req["method"], req.get("params", {}), execute)}
            except (ValueError, KeyError, OSError, TimeoutError) as error:
                out = {"error": {"code": -32602, "message": str(error)}}
            print(json.dumps({"jsonrpc": "2.0", "id": req["id"], **out}), flush=True)
        except (TypeError, ValueError, KeyError):
            raise SystemExit("invalid control framing")


if __name__ == "__main__":
    main()

"""MCP transport from the neutral client into the host's fixed, single-case tool broker."""

import json
import socket
import sys
from mcp_server import reply


def execute(item):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.connect("/case/work/broker/socket")
        stream = connection.makefile("rwb")
        stream.write(json.dumps(item).encode() + b"\n")
        stream.flush()
        payload = json.loads(stream.readline(1024 * 1024 + 1024))
        return payload


for line in sys.stdin.buffer:
    request = json.loads(line)
    if "id" not in request:
        continue
    try:
        response = {"result": reply(request["method"], request.get("params", {}), execute)}
    except (ValueError, KeyError, OSError, RuntimeError) as exc:
        response = {"error": {"code": -32602, "message": str(exc)}}
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], **response}), flush=True)

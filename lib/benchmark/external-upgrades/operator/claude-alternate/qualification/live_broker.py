"""One control-side MCP process with its roots fixed before the official model client sends a call."""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--baseline", type=Path, required=True)
p.add_argument("--product", type=Path, required=True)
p.add_argument("--case", type=Path, required=True)
p.add_argument("--audit", type=Path, required=True)
args = p.parse_args()
sys.path.insert(0, str(args.baseline))
import control  # noqa: E402
import mcp_server  # noqa: E402


def execute(item):
    start = time.monotonic()
    result = control.execute(args.product, args.case, item, timeout=35)
    # Hash only operator-visible tool details. No outer authenticated context enters the case or the receipt.
    a = json.loads(item["arguments"])
    entry = {
        "tool": item["name"],
        "exactRequestedCommand": a == {"argv": ["python3", "/case/work/observe_public_case.py"]},
        "exit": result["exit"],
        "seconds": round(time.monotonic() - start, 3),
        "outputSha256": hashlib.sha256(result["output"].encode()).hexdigest(),
    }
    with args.audit.open("a") as log:
        log.write(json.dumps(entry) + "\n")
    return result


while raw := sys.stdin.buffer.readline(2 * 1024 * 1024 + 1):
    if len(raw) > 2 * 1024 * 1024:
        raise SystemExit(2)
    try:
        req = json.loads(raw)
        if req.get("jsonrpc") != "2.0":
            raise ValueError("invalid MCP framing")
        if "id" not in req:
            continue
        try:
            msg = {"result": mcp_server.reply(req["method"], req.get("params", {}), execute)}
        except (OSError, ValueError, TypeError, KeyError, TimeoutError) as err:
            msg = {"error": {"code": -32602, "message": str(err)}}
        print(json.dumps({"jsonrpc": "2.0", "id": req["id"], **msg}), flush=True)
    except (ValueError, TypeError):
        raise SystemExit(2)

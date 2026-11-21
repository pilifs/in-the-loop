"""Fixed one-case tool authority. Preserve the model's own latest observation for the next bounded request."""

import argparse
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import control  # noqa: E402
import mcp_server  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("product", type=Path)
    parser.add_argument("case", type=Path)
    parser.add_argument("journal", type=Path)
    parser.add_argument("deadline", type=float)
    args = parser.parse_args()

    def execute(item):
        import time

        remaining = args.deadline - time.time()
        if remaining <= 0:
            raise TimeoutError("case wall budget exhausted")
        result = control.execute(args.product, args.case, item, timeout=remaining)
        # Tools can put long command output in the private case filesystem for subsequent reads.
        shown = result["output"].encode()[:12000].decode(errors="replace")
        if len(shown) < len(result["output"]):
            shown += "\n[Output truncated. Rerun with a narrower projection.]"
        observation = {
            "name": item["name"],
            "argv": control.classify(item),
            "exit": result["exit"],
            "output": shown,
        }
        with args.journal.open("a") as out:
            out.write(json.dumps(observation) + "\n")
            out.flush()
            os.fsync(out.fileno())
        return {"exit": result["exit"], "output": shown}

    while raw := sys.stdin.buffer.readline(2 * 1024 * 1024 + 1):
        if len(raw) > 2 * 1024 * 1024:
            raise SystemExit("oversize MCP message")
        entry = json.loads(raw)
        if entry.get("jsonrpc") != "2.0":
            raise SystemExit("invalid MCP framing")
        if "id" not in entry:
            continue
        try:
            response = {"result": mcp_server.reply(entry["method"], entry.get("params", {}), execute)}
        except (ValueError, KeyError, OSError, TimeoutError) as exc:
            response = {"error": {"code": -32602, "message": str(exc)}}
        print(json.dumps({"jsonrpc": "2.0", "id": entry["id"], **response}), flush=True)


if __name__ == "__main__":
    main()

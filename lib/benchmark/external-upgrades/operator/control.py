"""Control-side Responses tool contract. Every model-controlled command crosses the case namespace."""

import json
import os
import selectors
import subprocess
import time

import isolation

TOOL = {
    "type": "function",
    "name": "case_command",
    "description": "Run a program in this case. Read /case/packet. Write files under /case/work and the generated target under /opt/product/examples/001-case.",
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {"argv": {"type": "array", "items": {"type": "string"}}},
        "required": ["argv"],
        "additionalProperties": False,
    },
}
MAX_OUTPUT = 1024 * 1024


def classify(item):
    if item.get("type") != "function_call" or item.get("name") != TOOL["name"]:
        raise ValueError("control service supplied an unregistered tool")
    args = json.loads(item["arguments"])
    if not isinstance(args, dict) or set(args) != {"argv"}:
        raise ValueError("invalid tool arguments")
    argv = args["argv"]
    if (
        not isinstance(argv, list)
        or not (1 <= len(argv) <= 256)
        or not all(type(a) is str and "\0" not in a for a in argv)
        or not argv[0]
    ):
        raise ValueError("invalid command vector")
    if sum(len(x.encode()) for x in argv) > 256 * 1024:
        raise ValueError("command vector too large")
    return argv


def execute(product, case, item, timeout=60):
    """The caller pins both paths. Incoming arguments cannot select mounts, credentials, routing or environment."""
    argv = classify(item)
    command = isolation.environment(product.resolve(), case.resolve()) + argv
    deadline = time.monotonic() + timeout
    with subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        close_fds=True,
    ) as proc:
        output = bytearray()
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(proc.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise TimeoutError("case tool deadline")
                    block = os.read(proc.stdout.fileno(), 65536)
                    if not block:
                        break
                    output.extend(block)
                    if len(output) > MAX_OUTPUT:
                        raise ValueError("case output limit")
                code = proc.wait(timeout=max(0.01, deadline - time.monotonic()))
        except BaseException:
            proc.kill()
            proc.wait()
            raise
    return {"exit": code, "output": output.decode("utf-8", errors="replace")}

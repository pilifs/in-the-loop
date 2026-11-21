"""Durable scheduling and measurement for one neutral upgrade with the first-party restricted Claude client."""

import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import control  # noqa: E402
import isolation  # noqa: E402


def utc(ts=None):
    return dt.datetime.fromtimestamp(time.time() if ts is None else ts, dt.timezone.utc).isoformat()


def timestamp(value):
    date = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if date.tzinfo is None:
        raise ValueError("receipt time needs an explicit UTC offset")
    return date.timestamp()


def bytes_of(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def exclusive(path, content):
    """Publish a complete file once. A concurrent process or a recovery cannot overwrite it."""
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(content)
            out.flush()
            os.fsync(out.fileno())
        try:
            os.link(temp, path)
        except FileExistsError:
            return False
        parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        return True
    finally:
        os.unlink(temp)


def atomic(path, value):
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".state-")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(bytes_of(value))
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def json_file(path):
    return json.loads(path.read_bytes())


def reservation(model, prompt, profile):
    # One native API request per fresh process. No previous_response cursor, image, file upload or hidden transcript.
    # The complete qualified stock startup envelope (including all tool JSON) is reserved as bytes at twice its observed size.
    # ASCII-escaped prompt bytes upper-bound its byte-level token count, including non-ASCII input and JSON escapes.
    startup = profile["oneRequest"]["wireEnvelopeBytes"][model]
    return (
        2 * startup
        + 8192
        + len(json.dumps(prompt, ensure_ascii=True).encode())
        + profile["oneRequest"]["maxOutputTokens"]
    )


def usage_of(event):
    u = event.get("usage")
    if not isinstance(u, dict):
        raise ValueError("native client supplied no usage receipt")
    fields = (
        "input_tokens",
        "cache_creation_input_tokens",
        "cache_read_input_tokens",
        "output_tokens",
    )
    if any(type(u.get(k)) is not int or u[k] < 0 for k in fields):
        raise ValueError("incomplete native token receipt")
    return {k: u[k] for k in fields}


def charged(u):
    return u["input_tokens"] + u["cache_creation_input_tokens"] + u["output_tokens"]


class Ledger:
    def __init__(self, case_dir, intake, profile, pin_hash):
        self.root = case_dir
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.lockfile = (self.root / "case.lock").open("a")
        fcntl.flock(self.lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.guard = threading.RLock()
        self.received = timestamp(intake["receivedAt"])
        self.end = self.received + profile["budget"]["wallSeconds"]
        self.checkpoint_at = self.received + profile["budget"]["checkpointSeconds"]
        self.profile = profile
        self.timer = None
        self.events = self.root / "events.jsonl"
        self.statepath = self.root / "ledger.json"
        self.existing = self.statepath.exists()
        identity = {**intake, "profileSha256": pin_hash}
        if self.existing:
            self.data = json_file(self.statepath)
            if self.data["intake"] != identity:
                raise ValueError("case store belongs to a different intake")
        else:
            self.data = {
                "intake": identity,
                "phase": "intake",
                "requests": [],
                "chargedTokens": 0,
                "cachedInputTokens": 0,
                "estimatedUsd": 0.0,
                "reservedTokens": 0,
                "humanMinutes": intake["humanMinutes"],
            }
            atomic(self.statepath, self.data)
        if not (self.root / "first-report.json").exists():
            delay = self.checkpoint_at - time.time()
            if delay <= 0:
                self.checkpoint(False)
            else:
                self.timer = threading.Timer(delay, self.checkpoint, args=(False,))
                self.timer.daemon = True
                self.timer.start()

    def event(self, kind, **fields):
        with self.guard:
            row = {"at": utc(), "kind": kind, **fields}
            with self.events.open("a") as out:
                out.write(json.dumps(row) + "\n")
                out.flush()
                os.fsync(out.fileno())
            return row

    def phase(self, name):
        self.data["phase"] = name
        atomic(self.statepath, self.data)
        self.event("phase", stage=name)

    def left(self):
        return max(0, self.end - time.time())

    def require_time(self):
        if self.left() <= 0:
            raise Stopped("time-budget", "The two-hour budget from intake was exhausted.")

    def reserve(self, model, prompt):
        self.require_time()
        amount = reservation(model, prompt, self.profile)
        left = self.profile["budget"]["uncachedInputPlusOutputTokens"] - self.data["chargedTokens"]
        if self.data["reservedTokens"] or amount > left:
            raise Stopped(
                "token-budget",
                f"The next bounded model request needs a reservation of {amount} tokens; {left} remain.",
            )
        self.data["reservedTokens"] = amount
        atomic(self.statepath, self.data)
        return amount

    def settle(self, record):
        reserved = self.data["reservedTokens"]
        u = record["tokens"]
        count = charged(u)
        self.data["chargedTokens"] += count
        self.data["cachedInputTokens"] += u["cache_read_input_tokens"]
        self.data["estimatedUsd"] += record["estimatedUsd"]
        self.data["requests"].append(record)
        self.data["reservedTokens"] = 0
        atomic(self.statepath, self.data)
        self.event(
            "model-request", stage=record["stage"], tokens=count, elapsedSeconds=record["seconds"]
        )
        if (
            count > reserved
            or self.data["chargedTokens"] > self.profile["budget"]["uncachedInputPlusOutputTokens"]
        ):
            raise Stopped(
                "usage-mismatch",
                "The native usage exceeded its pre-authorized reservation. No further request was admitted.",
            )

    def checkpoint(self, early):
        with self.guard:
            cutoff = min(time.time(), self.checkpoint_at)
            events = []
            if self.events.is_file():
                for line in self.events.read_text().splitlines():
                    e = json.loads(line)
                    if timestamp(e["at"]) <= cutoff:
                        events.append(e)
            eligible = [e for e in events if e["kind"] == "evidence"]
            snapshot = {
                "scheduledAt": utc(self.checkpoint_at),
                "observedAt": utc(),
                "finalBeforeCheckpoint": early,
                "stage": next(
                    (e["stage"] for e in reversed(events) if e["kind"] == "phase"), "queued"
                ),
                "modelRequestsFinished": sum(e["kind"] == "model-request" for e in events),
                "lastEvidence": eligible[-1] if eligible else None,
            }
            exclusive(self.root / "checkpoint-900.json", bytes_of(snapshot))

    def seal(self, route, reason, report, extra=None):
        with self.guard:
            if self.timer:
                self.timer.cancel()
            if not (self.root / "checkpoint-900.json").exists():
                self.checkpoint(time.time() < self.checkpoint_at)
            info = {
                "schema": "external-upgrade-first-report/v1",
                "case_id": self.data["intake"]["case_id"],
                "resultRoute": route,
                "disposition": reason,
                "profileSha256": self.data["intake"]["profileSha256"],
                "receivedAt": self.data["intake"]["receivedAt"],
                "sealedAt": utc(),
                "elapsedFromIntakeSeconds": round(time.time() - self.received, 3),
                "report": report,
                "checkpoint": json_file(self.root / "checkpoint-900.json"),
                "measurement": self.data,
                **(extra or {}),
            }
            from reporting import build_document

            info = build_document(info, self.root)
            path = self.root / "first-report.json"
            exclusive(path, bytes_of(info))
            exclusive(self.root / "first-report.sha256", (isolation.digest(path) + "\n").encode())
            return json_file(path)

    def close(self):
        if self.timer:
            self.timer.cancel()
        self.lockfile.close()


class Stopped(Exception):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def case_run(product, case, argv, budget):
    budget.require_time()
    item = {"type": "function_call", "name": "case_command", "arguments": json.dumps({"argv": argv})}
    return control.execute(product, case, item, timeout=budget.left())


def read_inside(product, case, name, budget, limit=60000):
    script = "from pathlib import Path;import sys;p=Path(sys.argv[1]);b=p.read_bytes() if p.is_file() else b'';assert len(b)<=int(sys.argv[2]);sys.stdout.buffer.write(b)"
    r = case_run(product, case, ["python3", "-c", script, name, str(limit)], budget)
    return r["output"] if r["exit"] == 0 else ""


def write_inside(product, case, name, text, budget):
    if len(text.encode()) > 60000:
        raise Stopped("handoff", "Handoff file exceeds the bounded case input.")
    script = "from pathlib import Path;import sys;p=Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(sys.argv[2])"
    r = case_run(product, case, ["python3", "-c", script, name, text], budget)
    if r["exit"]:
        raise Stopped("handoff", "The isolated case could not accept its stage handoff.")


def classify_failure(text):
    s = text.casefold()
    for key, words in [
        (
            "account-refused",
            (
                "authentication_error",
                "not logged in",
                "rate_limit",
                "rate limit",
                "usage limit",
                "credit balance",
                "billing",
                "permission_error",
                "api error: 403",
                "unavailable for your",
                "quota",
                "out of usage",
            ),
        ),
        ("model-unavailable", ("model is not available", "model is unavailable", "unknown model")),
    ]:
        if any(word in s for word in words):
            return key
    return "model-client-error"


def model_request(model, stage, prompt, product, case, ledger, exe):
    reserve = ledger.reserve(model, prompt)
    directory = ledger.root / "requests" / f"{len(ledger.data['requests']) + 1:05d}"
    directory.mkdir(parents=True)
    audit = directory / "case-tool.jsonl"
    mcp = directory / "mcp.json"
    atomic(
        mcp,
        {
            "mcpServers": {
                "neutral_case": {
                    "type": "stdio",
                    "command": "/usr/bin/python3",
                    "args": [
                        str(HERE / "broker.py"),
                        str(product),
                        str(case),
                        str(audit),
                        str(ledger.end),
                    ],
                }
            }
        },
    )
    tmp = directory / "tmp"
    tmp.mkdir()
    opts = ledger.profile["explicitSettings"]
    env = {
        k: os.environ[k]
        for k in ("HOME", "USER", "LOGNAME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS")
        if k in os.environ
    }
    env.update(
        {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "TMPDIR": str(tmp),
            "TZ": "UTC",
            "LANG": "C.UTF-8",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_TELEMETRY": "1",
            "DISABLE_ERROR_REPORTING": "1",
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            "ENABLE_TOOL_SEARCH": "false",
            "CLAUDE_CODE_MAX_RETRIES": "0",
            "DISABLE_COMPACT": "1",
            "CLAUDE_CODE_MAX_CONTEXT_TOKENS": str(
                reserve - ledger.profile["oneRequest"]["maxOutputTokens"]
            ),
            "CLAUDE_CODE_MAX_OUTPUT_TOKENS": str(ledger.profile["oneRequest"]["maxOutputTokens"]),
        }
    )
    argv = [
        str(exe),
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
        "--no-session-persistence",
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        "mcp__neutral_case__case_command",
        "--max-turns",
        "1",
        "--settings",
        json.dumps(opts),
        "--output-format",
        "stream-json",
        "--verbose",
        "--",
        prompt,
    ]
    start = time.monotonic()
    proc = subprocess.Popen(
        argv,
        env=env,
        cwd="/srv",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=ledger.left())
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        raise Stopped(
            "time-or-interruption",
            "The model process was stopped. Its last reservation is retained because final token usage is unavailable.",
        )
    events = []
    for line in stdout.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    reason = " ".join(
        [
            str(result.get("subtype")),
            str(result.get("errors")),
            str(result.get("result", "")),
            stderr.decode(errors="replace"),
        ]
    )
    used = result.get("modelUsage") or {}
    requests = {
        e.get("message", {}).get("id")
        for e in events
        if e.get("type") == "assistant" and e.get("message", {}).get("id")
    }
    tools = [
        b.get("name")
        for e in events
        if e.get("type") == "assistant"
        for b in e.get("message", {}).get("content", [])
        if b.get("type") == "tool_use"
    ]
    calls = [json.loads(line) for line in audit.read_text().splitlines()] if audit.is_file() else []
    try:
        u = usage_of(result)
        cost = result["total_cost_usd"]
        assert isinstance(cost, (int, float)) and cost >= 0
    except (ValueError, KeyError, AssertionError):
        raise Stopped(
            classify_failure(reason),
            "The native client did not issue a final metered receipt. Its entire reservation is retained.",
        )
    record = {
        "stage": stage,
        "model": model,
        "seconds": round(time.monotonic() - start, 3),
        "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "reservation": reserve,
        "tokens": u,
        "estimatedUsd": cost,
        "toolCalls": len(calls),
        "clientDisposition": result.get("subtype"),
        "exit": proc.returncode,
        "models": list(used),
        "assistantMessageCount": len(requests),
    }
    ledger.settle(record)
    legitimate = result.get("subtype") in ("success", "error_max_turns")
    if (
        not legitimate
        or init.get("tools") != ["mcp__neutral_case__case_command"]
        or init.get("model") != model
        or set(used) != {model}
        or len(requests) > 1
        or any(n != "mcp__neutral_case__case_command" for n in tools)
    ):
        raise Stopped(
            classify_failure(reason),
            "The first-party client refused the request or its role, tools or one-request boundary differed from the profile.",
        )
    texts = [
        b.get("text", "")
        for e in events
        if e.get("type") == "assistant"
        for b in e.get("message", {}).get("content", [])
        if b.get("type") == "text"
    ]
    return ("\n".join(texts) + "\n" + json.dumps(calls, ensure_ascii=False))[-12000:]

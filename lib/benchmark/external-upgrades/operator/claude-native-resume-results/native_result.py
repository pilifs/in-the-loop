"""Recognize the stock client's intact broker result or its session-bound persisted preview."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat

from signals import signal

MAX_SIDECAR_BYTES = 1024 * 1024
REMINDERS = re.compile(r"(?:\s*<system-reminder>[\s\S]*?</system-reminder>\s*)+")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def outcome(result):
    if (
        not isinstance(result, dict)
        or set(result) != {"exit", "output"}
        or type(result["exit"]) is not int
        or not isinstance(result["output"], str)
    ):
        return None
    return digest(
        json.dumps([result["exit"], signal(result["output"])], separators=(",", ":")).encode()
    )


def broker_json(text, expected):
    source = text.strip()
    try:
        result, end = json.JSONDecoder().raw_decode(source)
    except (ValueError, RecursionError):
        return None
    if outcome(result) != expected:
        return None
    tail = source[end:].strip()
    if not tail:
        return "full-result"
    return "full-result-with-stock-reminder" if REMINDERS.fullmatch(tail) else None


def texts(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [
            m["text"]
            for m in value
            if isinstance(m, dict) and m.get("type") == "text" and isinstance(m.get("text"), str)
        ]
    return []


def verified_preview(text, tool_id, spec, binding, state):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", tool_id):
        return False
    if not text.startswith("<persisted-output>"):
        return False
    closing = text.rfind("</persisted-output>")
    if closing < 0:
        return False
    tail = text[closing + len("</persisted-output>") :].strip()
    if tail and not REMINDERS.fullmatch(tail):
        return False
    match = re.match(
        r"\A<persisted-output>\s*\nOutput too large \([^\n()]+\)\. Full output saved to: ([^\r\n]+)\r?\n\s*Preview \(first [^\n()]+\):\r?\n",
        text,
    )
    if not match:
        return False
    ref = match[1]
    entry = binding.get("files", {}).get(digest(ref.encode()))
    if not entry:
        return False
    relative = PurePosixPath(entry["relative"])
    expected_dir = PurePosixPath("projects/-srv") / spec["session"] / "tool-results"
    if (
        relative.parent != expected_dir
        or relative.name not in (tool_id + ".json", tool_id + ".txt")
        or not PurePosixPath(ref).is_absolute()
        or ".." in PurePosixPath(ref).parts
    ):
        return False
    path = state.joinpath(*relative.parts)
    try:
        if any(p.is_symlink() for p in [path, *path.parents] if p.is_relative_to(state)):
            return False
        status = path.stat()
        if (
            not stat.S_ISREG(status.st_mode)
            or status.st_size > MAX_SIDECAR_BYTES
            or not path.resolve(strict=True).is_relative_to(state.resolve(strict=True))
        ):
            return False
        data = path.read_bytes()
        if digest(data) != entry["sha256"]:
            return False
        text = data.decode("utf-8")
        if relative.suffix == ".json":
            blocks = json.loads(text)
            if (
                not isinstance(blocks, list)
                or len(blocks) != 1
                or not isinstance(blocks[0], dict)
                or set(blocks[0]) != {"type", "text"}
                or blocks[0]["type"] != "text"
            ):
                return False
            text = blocks[0]["text"]
        return isinstance(text, str) and broker_json(text, binding["outcomeSha256"]) == "full-result"
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return False


def restore(messages, spec, binding, state, old_signals):
    expected_id = spec.get("expectedToolResultIdSha256")
    expected_signal = spec.get("expectedBlockSha256")
    if not expected_id:
        ok = not expected_signal or expected_signal in old_signals
        return {
            "accepted": ok,
            "mode": "initial" if not expected_signal else "assistant-text" if ok else "unverified",
        }
    if binding.get("trustedToolIdSha256") != expected_id or not binding.get("outcomeSha256"):
        return {"accepted": False, "mode": "unbound-tool-result"}
    found = []
    for message in messages:
        blocks = message.get("content")
        if message.get("role") != "user" or not isinstance(blocks, list):
            continue
        for part in blocks:
            if not isinstance(part, dict) or part.get("type") != "tool_result":
                continue
            ident = part.get("tool_use_id")
            if isinstance(ident, str) and digest(ident.encode()) == expected_id:
                found.append((ident, part))
    if len(found) != 1:
        return {"accepted": False, "mode": "missing-or-duplicate-tool-id"}
    ident, part = found[0]
    for text in texts(part.get("content")):
        mode = broker_json(text, binding["outcomeSha256"])
        if mode:
            return {"accepted": True, "mode": mode}
        if verified_preview(text, ident, spec, binding, state):
            return {"accepted": True, "mode": "verified-native-preview"}
    return {"accepted": False, "mode": "unverified-tool-result"}


def from_case(messages, spec, signals):
    base = Path("/case/work")
    file = base / "native-result-bindings.json"
    data = json.loads(file.read_bytes()) if file.is_file() else {}
    return restore(messages, spec, data, base / "state", signals)

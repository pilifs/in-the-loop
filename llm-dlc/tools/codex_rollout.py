"""Codex sessions for sync.py: finding them, and reading them as Claude Code transcripts.

A Codex session is a rollout file, ~/.codex/sessions/YYYY/MM/DD/rollout-<time>-<session id>.jsonl.
sync.py stores a Codex session's log the way it stores a Claude Code session's: the rollout as it
is, redacted, named by its SHA-256. Only reading it differs. `claude_view` turns a rollout's
entries into entries shaped like a Claude Code transcript's, in memory, so the summary, the
manifest, the metrics and `check` read both agents with the same code.

The view has exactly one entry per rollout line, so a line of the view is a line of the log (the
metrics map a commit's log, a prefix of the latest, to a place by its line count). Lines that mean
nothing to a Claude Code reader become {"type": "codex", "codexType": ...} entries that keep only
their timestamp.

What maps to what:
- `item_completed` UserMessage: a prompt (a user entry). Other user-role messages are context
  Codex injects (AGENTS.md, the environment), not prompts.
- assistant messages, reasoning, and the model's tool calls (`function_call`, `custom_tool_call`,
  `local_shell_call`): assistant entries whose message id is the response that produced them, the
  `response_id` of the next `token_usage_record`, which also carries that response's usage.
- tool call outputs: user entries with a tool_result.
- `item_completed` CommandExecution and FileChange, the shell commands and patches a tool call ran:
  a `Bash` or `apply_patch` tool_use of the response that made the call, with its result inline
  (`codexResult`), since both ends are on one line.
- usage: OpenAI's input_tokens includes cached and cache-written tokens, Claude's does not, so the
  cached ones move to cache_read_input_tokens and cache_creation_input_tokens. output_tokens includes
  reasoning in both; the reasoning share goes to output_tokens_details.thinking_tokens.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

CODEX_HOME = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
SESSIONS = CODEX_HOME / "sessions"
SESSION_ID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
MODEL_ITEMS = {"message", "reasoning", "function_call", "custom_tool_call", "local_shell_call"}
OUTPUT_ITEMS = {"function_call_output", "custom_tool_call_output", "local_shell_call_output"}
FAILED_OUTPUT = re.compile(r"^Script (?:failed|error)", re.M)  # the exec cell itself failed, not a command in it


# --------------------------------------------------------------------------- finding sessions

def is_rollout(path: Path) -> bool:
    return path.name.startswith("rollout-")


def session_id(path: Path) -> str:
    """A transcript's session id: the file name of a Claude Code transcript, the id at the end of a rollout's."""
    if is_rollout(path) and (m := SESSION_ID.search(path.stem[-36:])):
        return m[0]
    return path.stem


def rollout_cwd(path: Path) -> str | None:
    """The working directory a rollout's session started in, from its first line (session_meta)."""
    try:
        with path.open("rb") as f:
            first = json.loads(f.readline())
    except (OSError, ValueError):
        return None
    payload = first.get("payload") if first.get("type") == "session_meta" else None
    return payload.get("cwd") if isinstance(payload, dict) else None


_CWD: dict[str, str | None] = {}  # a rollout's folder, by path: its first line does not change


def rollouts_in(repo: Path) -> list[Path]:
    """The rollouts of the Codex sessions that started in this repo or a folder in it, oldest first. A jj
    workspace beside the repo is another checkout, with its own sessions, as it is for Claude Code."""
    root = str(repo)
    found = []
    for p in sorted(SESSIONS.glob("*/*/*/rollout-*.jsonl")):
        key = str(p)
        if key not in _CWD:
            _CWD[key] = rollout_cwd(p)
        cwd = _CWD[key]
        if cwd and (cwd == root or cwd.startswith(root + "/")):
            found.append(p)
    return found


# --------------------------------------------------------------------------- reading as a transcript

def looks_like_rollout(entries: list[dict]) -> bool:
    return bool(entries) and entries[0].get("type") == "session_meta" and isinstance(entries[0].get("payload"), dict)


def looks_like_view(entries: list[dict]) -> bool:
    """Whether these entries are claude_view's of a rollout."""
    return bool(entries) and entries[0].get("codexType") == "session_meta"


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(c.get("text", "") for c in content or [] if isinstance(c, dict))


def _usage(u: dict) -> dict:
    n = {k: int(u.get(k) or 0) for k in ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                                         "output_tokens", "reasoning_output_tokens")}
    return {"input_tokens": max(n["input_tokens"] - n["cached_input_tokens"] - n["cache_write_input_tokens"], 0),
            "cache_read_input_tokens": n["cached_input_tokens"],
            "cache_creation_input_tokens": n["cache_write_input_tokens"],
            "output_tokens": n["output_tokens"],
            "output_tokens_details": {"thinking_tokens": n["reasoning_output_tokens"]}}


def _iso_ms(ms) -> str | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError):
        return None


def _tool_input(p: dict) -> tuple[str, dict]:
    """(name, input) of a model's tool call, the input as Claude Code's tools would have it where one matches."""
    kind = p.get("type")
    if kind == "local_shell_call":
        cmd = (p.get("action") or {}).get("command") or []
        return "Bash", {"command": cmd[-1] if cmd else ""}
    raw = p.get("arguments") if kind == "function_call" else p.get("input")
    if isinstance(raw, str) and kind == "function_call":
        try:
            raw = json.loads(raw)
        except ValueError:
            pass
    name = p.get("name") or kind
    if not isinstance(raw, dict):
        text = raw if isinstance(raw, str) else json.dumps(raw)
        first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        return name, {"code": text, "description": first[:200]}
    if name in ("shell", "exec_command", "container.exec"):
        cmd = raw.get("cmd") or raw.get("command")
        return "Bash", {**raw, "command": cmd[-1] if isinstance(cmd, list) and cmd else cmd}
    return name, raw


def _response_ids(entries: list[dict]) -> list[str | None]:
    """For each line, the id of the model response it belongs to: a model item belongs to the
    response of the next token_usage_record; a command or patch a tool ran, to the response whose
    call is still waiting for its output."""
    ids: list[str | None] = [None] * len(entries)
    pending: list[int] = []
    for i, e in enumerate(entries):
        p = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        if e.get("type") == "response_item" and p.get("type") in MODEL_ITEMS:
            if p.get("type") != "message" or p.get("role") == "assistant":
                pending.append(i)
        elif e.get("type") == "token_usage_record":
            rid = p.get("response_id") or f"codex-response-{i}"
            for j in pending:
                ids[j] = rid
            ids[i], pending = rid, []
        elif e.get("type") == "event_msg" and p.get("type") in ("task_complete", "turn_aborted") and pending:
            for j in pending:  # a response that never reported its usage (an interrupted turn)
                ids[j] = f"codex-response-{pending[0]}"
            pending = []
    for j in pending:
        ids[j] = f"codex-response-{pending[0]}"
    return ids


def claude_view(entries: list[dict]) -> list[dict]:
    """A rollout's entries as Claude Code transcript entries, one per line (see the module doc)."""
    ids = _response_ids(entries)
    usage: dict[str, dict] = {}
    for i, e in enumerate(entries):
        if e.get("type") == "token_usage_record" and isinstance(e.get("payload"), dict):
            usage[ids[i]] = _usage(e["payload"].get("usage") or {})
    out: list[dict] = []
    model, effort, last_response = None, None, None
    for i, e in enumerate(entries):
        p = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        kind, sub, ts = e.get("type"), p.get("type"), e.get("timestamp")
        filler = {"type": "codex", "codexType": f"{kind}/{sub}" if sub else kind, "timestamp": ts}

        def assistant(content: list[dict], rid: str | None = None, when: str | None = None) -> dict:
            rid = rid or ids[i]
            return {"type": "assistant", "timestamp": when or ts, "effort": effort,
                    "message": {"id": rid, "role": "assistant", "model": model, "content": content,
                                "usage": usage.get(rid, {})}}

        if kind == "session_meta":
            out.append({**filler, "version": p.get("cli_version"), "cwd": p.get("cwd")})
        elif kind == "turn_context":
            model = p.get("model") or model
            effort = ((p.get("collaboration_mode") or {}).get("settings") or {}).get("reasoning_effort") or p.get("effort")
            out.append(filler)
        elif kind == "compacted":
            out.append({"type": "system", "subtype": "compact_boundary", "timestamp": ts, "compactMetadata": {}})
        elif kind == "token_usage_record":
            last_response = ids[i]
            out.append(assistant([]))
        elif kind == "response_item" and sub == "message" and p.get("role") == "assistant":
            out.append(assistant([{"type": "text", "text": _text(p.get("content"))}]))
        elif kind == "response_item" and sub == "reasoning":
            out.append(assistant([{"type": "thinking", "thinking": _text(p.get("summary"))}]))
        elif kind == "response_item" and sub in ("function_call", "custom_tool_call", "local_shell_call"):
            name, inp = _tool_input(p)
            out.append(assistant([{"type": "tool_use", "id": p.get("call_id") or p.get("id"), "name": name, "input": inp}]))
        elif kind == "response_item" and sub in OUTPUT_ITEMS:
            o = p.get("output")
            text = o if isinstance(o, str) else _text(o) if isinstance(o, list) else json.dumps(o)
            out.append({"type": "user", "timestamp": ts, "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": p.get("call_id"), "content": text,
                 "is_error": bool(FAILED_OUTPUT.search(text[:4000]))}]}})
        elif kind == "event_msg" and sub == "item_completed":
            item = p.get("item") or {}
            itype = item.get("type")
            if itype == "UserMessage":
                out.append({"type": "user", "timestamp": ts, "message": {"role": "user", "content": _text(item.get("content"))}})
            elif itype in ("CommandExecution", "FileChange"):
                end = _iso_ms(p.get("completed_at_ms")) or ts
                if itype == "CommandExecution":
                    cmd = item.get("command") or []
                    name, inp = "Bash", {"command": cmd[-1] if cmd else ""}
                    result = item.get("aggregated_output") or ""
                    failed = item.get("exit_code") not in (0, None) or item.get("status") == "failed"
                else:
                    changes = item.get("changes") or {}
                    name, inp = "apply_patch", {"file_paths": sorted(changes), "file_path": next(iter(sorted(changes)), None)}
                    result = (item.get("stdout") or "") + (item.get("stderr") or "")
                    failed = item.get("status") == "failed"
                block = {"type": "tool_use", "id": item.get("id") or f"codex-item-{i}", "name": name, "input": inp,
                         "codexResult": {"end": end, "content": result, "is_error": failed}}
                out.append(assistant([block], rid=last_response or f"codex-response-{i}",
                                     when=_iso_ms(p.get("started_at_ms")) or ts))
            else:
                out.append(filler)
        else:
            out.append(filler)
    return out

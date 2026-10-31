#!/usr/bin/env python3
"""Turn redacted session logs into tidy tables: what each session cost, where its time went, and why.

`sync.py` calls this on every sync. Nothing here touches the disk or the clock: the output is a
function of a log, a manifest and llm-dlc/pricing.json, so it can be rebuilt from a published log
and `check` can tell when a file is stale. llm-dlc/specification.md describes the output.

Standard library only.
"""
from __future__ import annotations

import json
import re
from bisect import bisect_left, bisect_right
from datetime import datetime
from typing import Callable, Iterable

SCHEMA = "llm-trace-metrics/v1"
ROLLUP_SCHEMA = "llm-trace-metrics-rollup/v1"
PRICING_SCHEMA = "llm-trace-pricing/v1"

TEXT_LIMIT = 200                  # free text is a label for a chart; the log has the rest
PAUSE_MS = 30 * 60_000            # a gap this long between records is a pause, not work
LARGE_INPUT_TOKENS = 20_000       # a cache write this size, with the cache intact, is one big input
CACHE_BREAK_RATIO = 0.5           # the cache broke if a call read under this share of the last context
TTL_MS = {"5m": 5 * 60_000, "1h": 60 * 60_000}

# Names end in "_tokens", never "_token": the redactor reads `..._token: 12345678` as a secret.
TOKEN_KEYS = ("input_tokens", "output_tokens", "thinking_tokens", "cache_read_tokens",
              "cache_write_tokens", "cache_write_5m_tokens", "cache_write_1h_tokens")
ERROR_KINDS = (("Exit code", "exit_code"), ("The user doesn't want", "denied"),
               ("The server-side auto mode", "blocked"), ("<tool_use_error>", "tool_use_error"))
COMMAND_PREFIXES = ("<command-name>", "<command-message>", "<bash-input>")
OUTPUT_PREFIXES = ("<local-command", "<bash-stdout", "<bash-stderr")

Clean = Callable[[str], str]


# --------------------------------------------------------------------------- small helpers

def _ms(ts: str) -> int:
    return round(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)


def _blocks(msg: dict | None) -> list[dict]:
    content = (msg or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content or [] if isinstance(b, dict)]


def _text(content) -> str:
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict))
    return content if isinstance(content, str) else ""


def _clip(text: str, clean: Clean) -> str:
    """Clean after cutting: a cut can turn harmless text into something a redaction rule matches."""
    text = " ".join(text.split())
    return clean(text if len(text) <= TEXT_LIMIT else text[:TEXT_LIMIT - 1].rstrip() + "…")


def covered_ms(spans: Iterable[tuple[int, int]]) -> int:
    """Milliseconds covered by at least one span. Parallel tool calls overlap; a sum counts them twice."""
    total, reach = 0, None
    for start, end in sorted(spans):
        if reach is None or start > reach:
            total += end - start
            reach = end
        elif end > reach:
            total += end - reach
            reach = end
    return total


def median(values: list[int]) -> int | None:
    return sorted(values)[len(values) // 2] if values else None


# --------------------------------------------------------------------------- classification

def prompt_kind(entry: dict) -> tuple[str, str] | None:
    """(kind, text) if this record starts work: `human`, `command` or `task_notification`. None for
    what only looks like a prompt: tool results, meta records, compaction summaries, command output."""
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isSidechain") or entry.get("isCompactSummary"):
        return None
    blocks = _blocks(entry.get("message"))
    if any(b.get("type") == "tool_result" for b in blocks):
        return None
    text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S).strip()
    if not text or text.startswith(OUTPUT_PREFIXES):
        return None
    if text.startswith("<task-notification"):
        return "task_notification", ""
    if text.startswith(COMMAND_PREFIXES):
        name = re.search(r"<command-name>(.*?)</command-name>", text)
        return "command", name[1] if name else text
    if re.match(r"/[A-Za-z][\w:\-]*(\s|$)", text):
        return "command", text
    return "human", text


def error_kind(text: str) -> str:
    return next((kind for prefix, kind in ERROR_KINDS if text.startswith(prefix)), "other")


def bash_family(command: str) -> str:
    """The program a shell command runs, past `cd`, variable assignments and wrappers."""
    for part in re.split(r"&&|\|\||;|\n", command):
        words = [w for w in part.lstrip(" ({").split() if not re.fullmatch(r"[A-Za-z_]\w*=\S*", w)]
        while words and (words[0] in ("sudo", "time", "env", "exec", "command", "nohup") or words[0].startswith("-")):
            words = words[1:]
        if words and words[0] in ("for", "while", "until", "if", "case"):
            return "shell"
        if words and words[0] not in ("cd", "export", "set", "source", "."):
            name = words[0].rsplit("/", 1)[-1]
            return name if re.fullmatch(r"[\w.+\-]+", name) else "other"
    return "other"


# --------------------------------------------------------------------------- pricing

def costs(row: dict, pricing: dict) -> tuple[float | None, float | None]:
    """(what these tokens cost at list price, what they would have cost without caching)."""
    p = pricing["models"].get(row["model"])
    if p is None:
        return None, None
    usd = (row["input_tokens"] * p["input"] + row["output_tokens"] * p["output"]
           + row["cache_read_tokens"] * p["cache_read"] + row["cache_write_5m_tokens"] * p["cache_write_5m"]
           + row["cache_write_1h_tokens"] * p["cache_write_1h"])
    fresh = row["input_tokens"] + row["cache_read_tokens"] + row["cache_write_tokens"]
    return round(usd / 1e6, 6), round((fresh * p["input"] + row["output_tokens"] * p["output"]) / 1e6, 6)


def tally(rows: Iterable[dict]) -> dict:
    """Add up API calls, or anything already added up by this function."""
    out = {"api_calls": 0, "tool_calls": 0, **{k: 0 for k in TOKEN_KEYS}, "usd": 0.0, "uncached_usd": 0.0,
           "unpriced_calls": 0}
    for r in rows:
        out["api_calls"] += r.get("api_calls", 1)
        out["tool_calls"] += r["tool_calls"]
        for k in TOKEN_KEYS:
            out[k] += r[k]
        out["usd"] += r["usd"] or 0
        out["uncached_usd"] += r["uncached_usd"] or 0
        out["unpriced_calls"] += r.get("unpriced_calls", 0 if r["usd"] is not None else 1)
    out["usd"], out["uncached_usd"] = round(out["usd"], 6), round(out["uncached_usd"], 6)
    return out


def _grouped(rows: list[dict], key: str) -> list[dict]:
    groups: dict = {}
    for r in rows:
        groups.setdefault(r[key], []).append(r)
    return [{key: k, **tally(v)} for k, v in sorted(groups.items(), key=lambda kv: -sum(r["usd"] or 0 for r in kv[1]))]


def _tool_stats(tools: list[dict], key: str) -> list[dict]:
    groups: dict = {}
    for t in tools:
        if t[key] is not None:
            groups.setdefault(t[key], []).append(t)
    rows = []
    for name, ts in groups.items():
        spans = [t["ms"] for t in ts if t["ms"] is not None]
        rows.append({key: name, "calls": len(ts), "errors": sum(t["status"] == "error" for t in ts),
                     "no_result": sum(t["status"] == "no_result" for t in ts), "total_ms": sum(spans),
                     "median_ms": median(spans), "max_ms": max(spans, default=None),
                     "result_chars": sum(t["result_chars"] for t in ts)})
    return sorted(rows, key=lambda r: (-r["calls"], str(r[key])))


def _cache_stats(events: list[dict]) -> list[dict]:
    groups: dict = {}
    for e in events:
        groups.setdefault(e["cause"], []).append(e)
    return [{"cause": cause, "events": len(es), "tokens": sum(e["tokens"] for e in es),
             "write_usd": round(sum(e["write_usd"] or 0 for e in es), 6),
             "excess_usd": round(sum(e["excess_usd"] or 0 for e in es), 6),
             "reread_usd": round(sum(e["reread_usd"] or 0 for e in es), 6)}
            for cause, es in sorted(groups.items(), key=lambda kv: -sum(e["excess_usd"] or 0 for e in kv[1]))]


# --------------------------------------------------------------------------- one transcript

def _new_call(entry: dict, msg: dict, line: int, agent: str | None, window: int, prompt: int | None) -> dict:
    return {"seq": 0, "agent": agent, "line": line, "start": entry["timestamp"], "end": entry["timestamp"],
            "window": window, "prompt": prompt, "commit": None, "model": msg.get("model"), "effort": entry.get("effort"),
            "stop_reason": None, "context_tokens": 0, **{k: 0 for k in TOKEN_KEYS}, "thinking_ms": 0,
            "tool_calls": 0, "tools": [], "usd": None, "uncached_usd": None}


def _add_usage(call: dict, usage: dict) -> None:
    """A message is logged once per content block, each record with the usage so far: keep the highest."""
    write = usage.get("cache_creation_input_tokens") or 0
    five = (usage.get("cache_creation") or {}).get("ephemeral_5m_input_tokens") or 0
    seen = {"input_tokens": usage.get("input_tokens") or 0, "output_tokens": usage.get("output_tokens") or 0,
            "thinking_tokens": (usage.get("output_tokens_details") or {}).get("thinking_tokens") or 0,
            "cache_read_tokens": usage.get("cache_read_input_tokens") or 0, "cache_write_tokens": write,
            "cache_write_5m_tokens": five, "cache_write_1h_tokens": write - five}
    for k, v in seen.items():
        call[k] = max(call[k], v)
    call["context_tokens"] = call["input_tokens"] + call["cache_read_tokens"] + call["cache_write_tokens"]


def _new_tool(block: dict, entry: dict, line: int, call: dict, agent: str | None, clean: Clean) -> dict:
    inp = block.get("input") or {}
    label = next((inp[k] for k in ("description", "file_path", "query", "url", "skill") if inp.get(k)), "")
    command = inp.get("command") if block.get("name") == "Bash" else None
    return {"seq": 0, "agent": agent, "line": line, "name": block.get("name"), "call": call, "prompt": call["prompt"],
            "start": entry["timestamp"], "end": None, "ms": None, "status": "no_result", "error_kind": None,
            "result_chars": 0, "family": clean(bash_family(command)) if isinstance(command, str) else None,
            "label": _clip(str(label), clean), "error": None}


def read_transcript(entries: list[dict], agent: str | None, clean: Clean) -> dict:
    """The raw tables of one transcript, in log order. `line` is 1-based and equals the line of the
    log, so a log that is a prefix of this one can be mapped to a place in these tables."""
    calls: dict[str, dict] = {}
    tools: dict[str, dict] = {}
    requests: dict[str, str] = {}
    prompts, compactions, pauses, stamps = [], [], [], []
    reported, window, last = None, 0, None

    def open_prompt(kind: str, text: str, chars: int, ts: str, line: int) -> None:
        prompts.append({"index": len(prompts), "kind": kind, "ts": ts, "end": ts, "line": line, "window": window,
                        "commit": None, "chars": chars, "text": _clip(text, clean)})

    for line, e in enumerate(entries, 1):
        kind, ts = e.get("type"), e.get("timestamp")
        if ts:
            stamps.append((line, ts))
            if last is not None and _ms(ts) - _ms(last) >= PAUSE_MS:
                pauses.append({"start": last, "end": ts, "ms": _ms(ts) - _ms(last), "line": line,
                               "after_prompt": prompts[-1]["index"] if prompts else None})
            last = ts if last is None or ts > last else last
        if kind == "api-request":
            requests[e.get("id")] = ts
        elif kind == "cost-state":
            reported = (line, e)
        elif kind == "system" and e.get("subtype") == "compact_boundary":
            window += 1
            meta = e.get("compactMetadata") or {}
            compactions.append({"ts": ts, "line": line, "window": window, "trigger": meta.get("trigger"),
                                "pre_tokens": meta.get("preTokens"), "post_tokens": meta.get("postTokens"),
                                "ms": meta.get("durationMs")})
        elif kind == "attachment":
            att = e.get("attachment") or {}
            if att.get("type") == "queued_command" and att.get("commandMode") == "prompt" and isinstance(att.get("prompt"), str):
                open_prompt("human", att["prompt"], len(att["prompt"]), ts, line)
        elif kind == "assistant":
            msg = e.get("message") or {}
            if str(msg.get("model")).startswith("<"):  # written by the client, not a model call
                continue
            prompt = prompts[-1]["index"] if prompts else None
            call = calls.setdefault(msg.get("id") or e.get("requestId"), _new_call(e, msg, line, agent, window, prompt))
            if e.get("requestRef") in requests:
                call["start"] = min(call["start"], requests[e["requestRef"]])
            call["end"] = max(call["end"], ts)
            call["stop_reason"] = msg.get("stop_reason") or call["stop_reason"]
            call["thinking_ms"] += e.get("thinkingDurationMs") or 0
            _add_usage(call, msg.get("usage") or {})
            for b in _blocks(msg):
                if b.get("type") == "tool_use" and b.get("id") not in tools:
                    tools[b.get("id")] = _new_tool(b, e, line, call, agent, clean)
                    call["tools"].append(b.get("name"))
                    call["tool_calls"] += 1
            if prompts:
                prompts[-1]["end"] = max(prompts[-1]["end"], ts)
        elif kind == "user":
            results = [b for b in _blocks(e.get("message")) if b.get("type") == "tool_result"]
            for b in results:
                tool = tools.get(b.get("tool_use_id"))
                if tool is None or tool["end"] is not None:
                    continue
                text = _text(b.get("content"))
                tool.update(end=ts, ms=_ms(ts) - _ms(tool["start"]), result_chars=len(text),
                            status="error" if b.get("is_error") else "ok")
                if b.get("is_error"):
                    tool.update(error_kind=error_kind(text), error=_clip(text, clean))
            if results and prompts:
                prompts[-1]["end"] = max(prompts[-1]["end"], ts)
            elif (found := prompt_kind(e)) is not None:
                open_prompt(found[0], found[1], len(found[1]), ts, line)
    return {"calls": list(calls.values()), "tools": list(tools.values()), "prompts": prompts,
            "compactions": compactions, "pauses": pauses, "stamps": stamps, "reported": reported}


def cache_events(calls: list[dict], pricing: dict) -> list[dict]:
    """Every call that wrote a lot to the cache, and why. Reads falling away from the last context
    mean the prefix was lost. `cause` is the first explanation that applies and `also` lists the
    rest: a compaction rewrites the context whatever else happened, so a model switch at the same
    moment cannot be blamed for that write. A large write with the prefix intact is one large
    input, and costs again on every later call in the window."""
    events, prev, ttl = [], None, TTL_MS["5m"]
    for i, c in enumerate(calls):
        also: list[str] = []
        if prev is None:
            cause = "session_start"
        elif c["cache_read_tokens"] < CACHE_BREAK_RATIO * prev["context_tokens"]:
            gap = _ms(c["start"]) - _ms(prev["start"])
            cause, *also = [name for name, hit in (("compaction", c["window"] != prev["window"]),
                                                   ("model_switch", c["model"] != prev["model"]),
                                                   ("cache_expired", gap > ttl),
                                                   ("effort_change", c["effort"] != prev["effort"])) if hit] or ["unexplained"]
        elif c["cache_write_tokens"] >= LARGE_INPUT_TOKENS:
            cause = "large_input"
        else:
            cause = None
        if cause and c["cache_write_tokens"]:
            p = pricing["models"].get(c["model"])
            write = p and (c["cache_write_5m_tokens"] * p["cache_write_5m"] + c["cache_write_1h_tokens"] * p["cache_write_1h"]) / 1e6
            excess = p and write - c["cache_write_tokens"] * p["cache_read"] / 1e6
            later = [x for x in calls[i + 1:] if x["window"] == c["window"]] if cause == "large_input" else []
            reread = sum(c["cache_write_tokens"] * pricing["models"][x["model"]]["cache_read"] / 1e6
                         for x in later if x["model"] in pricing["models"])
            events.append({"seq": c["seq"], "agent": c["agent"], "start": c["start"], "window": c["window"],
                           "prompt": c["prompt"], "cause": cause, "also": also, "tokens": c["cache_write_tokens"],
                           "cache_read_tokens": c["cache_read_tokens"],
                           "previous_context_tokens": prev["context_tokens"] if prev else None,
                           "gap_ms": _ms(c["start"]) - _ms(prev["start"]) if prev else None,
                           "after_tools": prev["tools"] if prev else [], "later_calls": len(later),
                           "write_usd": None if write is None else round(write, 6),
                           "excess_usd": None if excess is None else round(excess, 6),
                           "reread_usd": round(reread, 6)})
        if c["cache_write_1h_tokens"]:
            ttl = TTL_MS["1h"]
        prev = c
    return events


# --------------------------------------------------------------------------- one session

def _commit_rows(manifest: dict, transcript: dict) -> tuple[list[dict], list[int], list[int]]:
    """A commit's log is a prefix of the session's log, and redaction works line by line, so the line
    count of that log cuts the session in two whatever redaction policy produced it. Returns the
    rows, and for `commit_of` the cut points in order and the row each belongs to."""
    rows, cuts, owners = [], [], []
    stamps, reach = transcript["stamps"], 0
    lines_at = [line for line, _ in stamps]
    for i, c in enumerate(manifest.get("commits", [])):
        log = (manifest.get("logs") or {}).get(c.get("log_sha256")) or {}
        lines = log.get("lines")
        before = bisect_right(lines_at, lines) if lines else 0
        rows.append({"index": i, "change_id": c.get("change_id"), "summary": c.get("summary"),
                     "log_sha256": c.get("log_sha256"), "log_lines": lines, "log_bytes": log.get("bytes"),
                     "log_gzip_bytes": log.get("gzip_bytes"), "ts": stamps[before - 1][1] if before else None})
        if lines and lines > reach:
            reach = lines
            cuts.append(lines)
            owners.append(i)
    return rows, cuts, owners


def _prompt_rows(prompts: list[dict], calls: list[dict], tools: list[dict]) -> None:
    for p in prompts:
        own = [c for c in calls if c["prompt"] == p["index"]]
        own_tools = [t for t in tools if t["prompt"] == p["index"]]
        main = [c for c in own if c["agent"] is None]
        tool_spans = [(_ms(t["start"]), _ms(t["end"])) for t in own_tools if t["agent"] is None and t["end"]]
        model_spans = [(_ms(c["start"]), _ms(c["end"])) for c in main]
        p.update(tally(own))
        p.update(tool_errors=sum(t["status"] == "error" for t in own_tools), models=sorted({c["model"] for c in own}),
                 agent_ms=_ms(p["end"]) - _ms(p["ts"]), model_ms=covered_ms(model_spans),
                 tool_ms=covered_ms(tool_spans), busy_ms=covered_ms(model_spans + tool_spans))


def _reported(found: tuple[int, dict] | None, calls: list[dict]) -> dict | None:
    """What Claude Code itself counted. It includes calls the transcript has no record of: compaction
    and Haiku side calls. It is written when a session stops, so it can trail the end of the log."""
    if found is None:
        return None
    line, e = found
    ours = sum(c["usd"] or 0 for c in calls if c["agent"] is None and c["line"] <= line)
    return {"line": line, "usd": round(e.get("totalCostUSD") or 0, 6), "api_ms": e.get("totalAPIDuration"),
            "tool_ms": e.get("totalToolDuration"), "lines_added": e.get("totalLinesAdded"),
            "lines_removed": e.get("totalLinesRemoved"), "calls_usd": round(ours, 6),
            "unattributed_usd": round((e.get("totalCostUSD") or 0) - ours, 6),
            "models": {name: {"usd": round(u.get("costUSD") or 0, 6), "input_tokens": u.get("inputTokens", 0),
                              "output_tokens": u.get("outputTokens", 0),
                              "cache_read_tokens": u.get("cacheReadInputTokens", 0),
                              "cache_write_tokens": u.get("cacheCreationInputTokens", 0)}
                       for name, u in sorted((e.get("modelUsage") or {}).items())}}


def session(manifest: dict, entries: list[dict], subagents: list[tuple[str, list[dict]]], pricing: dict,
            clean: Clean) -> dict:
    """Everything known about one session. `subagents` is (agent id, entries) for each subagent log."""
    main = read_transcript(entries, None, clean)
    prompts, compactions = main["prompts"], main["compactions"]
    streams = [main["calls"]]
    calls, tools = list(main["calls"]), list(main["tools"])
    prompt_times = [_ms(p["ts"]) for p in prompts]
    for agent, sub_entries in subagents:  # a subagent's lines mean nothing here: place it by time
        sub = read_transcript(sub_entries, agent, clean)
        for row in sub["calls"] + sub["tools"]:
            at = bisect_right(prompt_times, _ms(row["start"])) - 1
            row["prompt"] = prompts[at]["index"] if at >= 0 else None
        streams.append(sub["calls"])
        calls += sub["calls"]
        tools += sub["tools"]

    for seq, c in enumerate(calls):
        c["seq"] = seq
        c["usd"], c["uncached_usd"] = costs(c, pricing)
    for seq, t in enumerate(tools):
        t["seq"], t["call"] = seq, t["call"]["seq"]

    commits, cuts, owners = _commit_rows(manifest, main)

    def commit_of(line: int) -> int | None:
        at = bisect_left(cuts, line)
        return owners[at] if at < len(cuts) else None

    for p in prompts:
        p["commit"] = commit_of(p["line"])
    for row in calls + tools:
        row["commit"] = commit_of(row["line"]) if row["agent"] is None else \
            prompts[row["prompt"]]["commit"] if row["prompt"] is not None else None
    _prompt_rows(prompts, calls, tools)
    for row in commits:
        own = [c for c in calls if c["commit"] == row["index"]]
        row.update(tally(own))
        ps = [p for p in prompts if p["commit"] == row["index"]]
        row.update(prompts=sum(p["kind"] == "human" for p in ps), agent_ms=sum(p["agent_ms"] for p in ps),
                   tool_errors=sum(t["status"] == "error" for t in tools if t["commit"] == row["index"]))

    windows = []
    for w in range(len(compactions) + 1):
        own = [c for c in calls if c["window"] == w and c["agent"] is None]
        windows.append({"index": w, "started": own[0]["start"] if own else None, "ended": own[-1]["end"] if own else None,
                        "prompts": sum(p["window"] == w and p["kind"] == "human" for p in prompts),
                        "peak_context_tokens": max((c["context_tokens"] for c in own), default=0), **tally(own)})

    events = [e for stream in streams for e in cache_events(stream, pricing)]
    stamps = main["stamps"]
    agent_ms = sum(p["agent_ms"] for p in prompts)
    return {
        "schema": SCHEMA,
        "session_id": manifest.get("session_id"),
        "source": {"log_sha256": (manifest.get("log") or {}).get("sha256"), "log_lines": len(entries),
                   "redaction_policy": manifest.get("redaction_policy")},
        "pricing_as_of": pricing.get("as_of"),
        "totals": {"prompts": sum(p["kind"] == "human" for p in prompts),
                   "commands": sum(p["kind"] == "command" for p in prompts),
                   "commits": len(commits), "compactions": len(compactions), "subagents": len(subagents),
                   "tool_errors": sum(t["status"] == "error" for t in tools),
                   "peak_context_tokens": max((c["context_tokens"] for c in calls), default=0), **tally(calls)},
        "after_last_commit": tally(c for c in calls if c["commit"] is None),
        "time": {"elapsed_ms": _ms(stamps[-1][1]) - _ms(stamps[0][1]) if stamps else 0, "agent_ms": agent_ms,
                 "model_ms": sum(p["model_ms"] for p in prompts), "tool_ms": sum(p["tool_ms"] for p in prompts),
                 "busy_ms": sum(p["busy_ms"] for p in prompts),
                 "compaction_ms": sum(c["ms"] or 0 for c in compactions),
                 "paused_ms": sum(p["ms"] for p in main["pauses"])},
        "reported": _reported(main["reported"], calls),
        "by_model": _grouped(calls, "model"),
        "by_effort": _grouped(calls, "effort"),
        "by_tool": _tool_stats(tools, "name"),
        "by_bash_family": _tool_stats(tools, "family"),
        "by_cache_cause": _cache_stats(events),
        "windows": windows,
        "compactions": compactions,
        "pauses": main["pauses"],
        "commits": commits,
        "prompts": prompts,
        "calls": calls,
        "tools": tools,
        "cache_events": events,
    }


# --------------------------------------------------------------------------- all sessions

def rollup(sessions: list[tuple[dict, dict]], pricing: dict) -> dict:
    """All sessions added up. `sessions` is (manifest, metrics) in the order to list them. It reads
    only those, so a sync rewrites it identically."""
    sessions = [(m, s) for m, s in sessions if s["totals"]["api_calls"]]
    calls = [c for _, s in sessions for c in s["calls"]]
    tools = [t for _, s in sessions for t in s["tools"]]
    prompts = [p for _, s in sessions for p in s["prompts"]]
    events = [e for _, s in sessions for e in s["cache_events"]]

    days: dict[str, list[dict]] = {}
    for c in calls:
        days.setdefault(c["start"][:10], []).append(c)
    by_day = [{"date": day, "prompts": sum(p["kind"] == "human" and p["ts"][:10] == day for p in prompts),
               "agent_ms": sum(p["agent_ms"] for p in prompts if p["ts"][:10] == day), **tally(rows)}
              for day, rows in sorted(days.items())]

    commits: dict[str, dict] = {}  # one row per change, which several sessions can have worked on
    for m, s in sessions:
        for c in s["commits"]:
            row = commits.setdefault(c["change_id"], {"change_id": c["change_id"], "summary": c["summary"],
                                                      "sessions": [], "parts": []})
            row["summary"] = row["summary"] or c["summary"]
            row["sessions"].append(m["session_id"])
            row["parts"].append(c)
    commit_rows = []
    for row in commits.values():
        parts = row.pop("parts")
        commit_rows.append({**row, "prompts": sum(p["prompts"] for p in parts),
                            "agent_ms": sum(p["agent_ms"] for p in parts), **tally(parts)})

    reported = [s["reported"] for _, s in sessions if s["reported"]]
    return {
        "schema": ROLLUP_SCHEMA,
        "pricing_as_of": pricing.get("as_of"),
        "totals": {"sessions": len(sessions), "prompts": sum(p["kind"] == "human" for p in prompts),
                   "commits": len(commits), "compactions": sum(s["totals"]["compactions"] for _, s in sessions),
                   "tool_errors": sum(t["status"] == "error" for t in tools),
                   "reported_usd": round(sum(r["usd"] for r in reported), 6),
                   "unattributed_usd": round(sum(r["unattributed_usd"] for r in reported), 6),
                   **tally(calls)},
        "time": {k: sum(s["time"][k] for _, s in sessions) for k in
                 ("elapsed_ms", "agent_ms", "model_ms", "tool_ms", "busy_ms", "compaction_ms", "paused_ms")},
        "by_model": _grouped(calls, "model"),
        "by_effort": _grouped(calls, "effort"),
        "by_tool": _tool_stats(tools, "name"),
        "by_bash_family": _tool_stats(tools, "family"),
        "by_cache_cause": _cache_stats(events),
        "by_day": by_day,
        "sessions": [{"session_id": m["session_id"], "title": m.get("title"), "started": m.get("started"),
                      "ended": m.get("ended"), **s["totals"], **s["time"],
                      "reported_usd": s["reported"]["usd"] if s["reported"] else None} for m, s in sessions],
        "commits": commit_rows,
    }


def dumps(doc: dict) -> str:
    """JSON with one table row per line. A log only grows, so its tables only grow, and a commit's
    diff is the rows it added."""
    def rows(value) -> bool:
        return isinstance(value, list) and bool(value) and all(isinstance(v, dict) for v in value)

    def one(value) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    fields = []
    for key, value in doc.items():
        body = "[\n" + ",\n".join("    " + one(v) for v in value) + "\n  ]" if rows(value) else one(value)
        fields.append(f"  {json.dumps(key)}: {body}")
    return "{\n" + ",\n".join(fields) + "\n}\n"

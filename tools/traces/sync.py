#!/usr/bin/env python3
"""Publish Claude Code session traces for this repo.

Layout (docs/traces.md has the full spec):

  traces/<session-id>/manifest.json          checked in: stats, log pointer, commits
  traces/<session-id>/logs/<sha256>.jsonl.gz gitignored: immutable redacted log snapshots

Public URL of a log: https://terminalvalue.net/raw-traces/<session-id>/<sha256>.jsonl.gz

Identifiers:
  session   the Claude Code session UUID
  log       sha256 of the *uncompressed* redacted JSONL; a snapshot file never changes
  commit    each change made in a session carries the trailer
              LLM-Trace: <session-id> sha256:<log-sha256>
            and the manifest lists those changes (jj change id, git SHA once immutable)

Commands:
  sync.py hook                  Claude Code Stop/SessionEnd hook (hook JSON on stdin)
  sync.py sync [--all | ID...]  snapshot sessions of this repo from ~/.claude/projects
  sync.py commit -m MESSAGE     finish @ with trailers matching its manifest (alias: jj trace-commit)
  sync.py upload                upload logs that commits point at to the CDN, verify, record URLs
  sync.py push [JJ PUSH ARGS]   sync, upload, check, then `jj git push` (alias: jj trace-push)
  sync.py check [--remote]      verify hashes, trailers and redaction (--remote: re-download uploads)
  sync.py init                  per-clone jj config (file size limit, trace-push alias)

Standard library only. The hook never fails a session; errors go to
~/.local/state/llm-traces/hook.log.
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRACES = REPO / "traces"
LANGFUSE_ENV = REPO / "infra" / "langfuse" / ".env"
STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "llm-traces"
EXTRA_REDACTIONS = Path.home() / ".config" / "llm-traces" / "redact.txt"
SCHEMA = "llm-trace-manifest/v1"
REDACTION_POLICY = 2           # bump when redaction changes the bytes it produces
TRAILER = "LLM-Trace"
TRAILER_RE = re.compile(rf"^{TRAILER}: (\S+)(?: sha256:([0-9a-f]{{64}}))?\s*$", re.M)
# Hooks inherit the PATH Claude Code started with, which may predate ~/.local/bin.
JJ = shutil.which("jj") or str(Path.home() / ".local" / "bin" / "jj")
MAX_ATTR = 64 * 1024           # truncate large tool outputs sent to Langfuse
LIVE_SECONDS = 600             # a transcript written this recently may have an unfinished turn
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
# Logs are served from R2 by the Worker in infra/cdn; the URL path is the object key.
CDN_BASE = "https://terminalvalue.net"
CDN_BUCKET = "llm-traces"
CDN_DIR = REPO / "infra" / "cdn"
NODE = shutil.which("node") or str(Path.home() / ".local" / "bin" / "node")
WRANGLER = CDN_DIR / "node_modules" / "wrangler" / "bin" / "wrangler.js"  # pinned in infra/cdn/package.json


# --------------------------------------------------------------------------- redaction

SECRET_PATTERNS = [
    ("anthropic-key", r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("langfuse-key", r"[ps]k-lf-[A-Za-z0-9\-]{16,}"),
    ("github-token", r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    ("aws-key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("slack-token", r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"),
    ("private-key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----"),
    ("bearer", r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}"),
]


def _cmd(*args: str) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=10, cwd=REPO).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def read_env(path: Path) -> dict[str, str]:
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            m = re.match(r"^([A-Z0-9_]+)=(.*)$", line.strip())
            if m:
                env[m[1]] = m[2].strip().strip('"')
    return env


def personal_literals() -> tuple[list[tuple[str, str]], str]:
    """(literal, replacement) pairs for this machine: home path, emails, local secrets."""
    pairs: list[tuple[str, str]] = []
    home, user = str(Path.home()), os.environ.get("USER") or Path.home().name
    pairs += [(home, "~"), (re.sub(r"[^A-Za-z0-9]", "-", home), "-home-user")]
    emails = {_cmd("git", "config", "--get", "user.email"), _cmd(JJ, "config", "get", "user.email")}
    try:
        account = json.loads((Path.home() / ".claude.json").read_text()).get("oauthAccount") or {}
        emails.add(account.get("emailAddress") or "")
    except (OSError, ValueError):
        pass
    pairs += [(e, "user@example.com") for e in emails if e]
    pairs += [(e.split("@")[0], "user") for e in emails if len(e.split("@")[0]) >= 4]
    pairs += [(v, "[REDACTED:local-secret]") for k, v in read_env(LANGFUSE_ENV).items()
              if re.search(r"SECRET|PASSWORD|KEY|SALT|AUTH|DATABASE_URL", k) and len(v) >= 12]
    if EXTRA_REDACTIONS.exists():
        for line in EXTRA_REDACTIONS.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                lit, _, rep = line.partition("=>")
                pairs.append((lit.strip(), rep.strip() or "[REDACTED]"))
    pairs.sort(key=lambda p: -len(p[0]))
    return pairs, user


class Redactor:
    def __init__(self) -> None:
        self.literals, user = personal_literals()
        # Also match right after a literal backslash-n/t/r: JSON echoed inside a tool result
        # keeps its escapes, so there is no word boundary before the name.
        self.user_re = (re.compile(rf"(?:(?<=\\[nrt])|(?<![A-Za-z0-9_])){re.escape(user)}\b")
                        if len(user) >= 3 else None)
        self.secret_res = [(k, re.compile(p, re.S)) for k, p in SECRET_PATTERNS]

    def string(self, text: str) -> str:
        for lit, rep in self.literals:
            text = text.replace(lit, rep)
        for kind, rx in self.secret_res:
            text = rx.sub(f"[REDACTED:{kind}]", text)
        if self.user_re:
            text = self.user_re.sub("user", text)
        return text

    def __call__(self, jsonl: str) -> bytes:
        """Redact every string (keys included) of every JSON line. Working on decoded
        strings matters: in raw JSON "\\nname" hides the word boundary before "name".
        Deterministic and line-local, so an append-only transcript gives an append-only log."""
        out = []
        for line in jsonl.splitlines():
            try:
                obj = json.loads(line)
            except ValueError:
                out.append(self.string(line))
                continue
            out.append(json.dumps(_walk(obj, self.string), ensure_ascii=False, separators=(",", ":")))
        return ("\n".join(out) + "\n" if out else "").encode()

    def leaks(self, jsonl: str) -> list[str]:
        found: set[str] = set()

        def scan(s: str) -> str:
            found.update("personal literal" for lit, _ in self.literals if lit in s)
            found.update(kind for kind, rx in self.secret_res if rx.search(s))
            if self.user_re and self.user_re.search(s):
                found.add("username")
            return s

        for line in jsonl.splitlines():
            try:
                _walk(json.loads(line), scan)
            except ValueError:
                scan(line)
        return sorted(found)


def _walk(obj, fn):
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [_walk(v, fn) for v in obj]
    if isinstance(obj, dict):
        return {fn(k): _walk(v, fn) for k, v in obj.items()}
    return obj


# --------------------------------------------------------------------------- transcripts

def claude_project_dir() -> Path:
    return Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(REPO))


def read_jsonl(data: bytes) -> list[dict]:
    out = []
    for line in data.decode(errors="replace").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def ts_ns(ts: str | None) -> int:
    if not ts:
        return 0
    return int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1e9)


def blocks(msg: dict) -> list[dict]:
    content = (msg or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content or [] if isinstance(b, dict)]


def is_prompt(e: dict) -> bool:
    return (e.get("type") == "user" and not e.get("isSidechain") and not e.get("isMeta")
            and not any(b.get("type") == "tool_result" for b in blocks(e.get("message"))))


def text_of(msg: dict) -> str:
    return "\n".join(b.get("text", "") for b in blocks(msg) if b.get("type") == "text")


def _usage_zero() -> dict:
    return {k: 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}


def _window(index: int, started: str | None) -> dict:
    return {"index": index, "started": started, "ended": None, "turns": 0, "api_calls": 0,
            "usage": _usage_zero(), "peak_context_tokens": 0}


def summarize(entries: list[dict], repo_prefix: str) -> dict:
    """High-level stats of one transcript, split into context windows at compactions."""
    windows = [_window(0, None)]
    seen_msgs, seen_tools, tools, errors, files = set(), set(), {}, 0, set()
    models, title, version, first_prompt = set(), None, None, None
    for e in entries:
        version = version or e.get("version")
        if e.get("type") == "system" and e.get("subtype") == "compact_boundary":
            windows.append(_window(len(windows), e.get("timestamp")))
        w = windows[-1]
        if e.get("timestamp"):
            w["started"] = w["started"] or e["timestamp"]
            w["ended"] = e["timestamp"]
        if e.get("type") == "ai-title":
            title = e.get("aiTitle") or title
        elif is_prompt(e):
            w["turns"] += 1
            first_prompt = first_prompt or text_of(e["message"])[:200]
        elif e.get("type") == "assistant":
            msg = e.get("message") or {}
            if msg.get("model") and not msg["model"].startswith("<"):
                models.add(msg["model"])
            mid = msg.get("id") or e.get("requestId")
            if mid and mid not in seen_msgs:
                seen_msgs.add(mid)
                u = msg.get("usage") or {}
                w["api_calls"] += 1
                for k in w["usage"]:
                    w["usage"][k] += int(u.get(k) or 0)
                ctx = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
                w["peak_context_tokens"] = max(w["peak_context_tokens"], ctx)
            for b in blocks(msg):
                if b.get("type") == "tool_use" and b.get("id") not in seen_tools:
                    seen_tools.add(b.get("id"))
                    tools[b.get("name")] = tools.get(b.get("name"), 0) + 1
                    inp = b.get("input") or {}
                    path = inp.get("file_path") or inp.get("notebook_path")
                    if b.get("name") in EDIT_TOOLS and isinstance(path, str):
                        files.add(path[len(repo_prefix) + 1:] if path.startswith(repo_prefix + "/") else path)
        elif e.get("type") == "user":
            errors += sum(1 for b in blocks(e.get("message")) if b.get("type") == "tool_result" and b.get("is_error"))
    total = _usage_zero()
    for w in windows:
        for k in total:
            total[k] += w["usage"][k]
    started, ended = windows[0]["started"], windows[-1]["ended"]
    return {
        "title": title, "first_prompt": first_prompt,
        "client": f"claude-code {version}" if version else None, "models": sorted(models),
        "started": started, "ended": ended,
        "duration_seconds": round((ts_ns(ended) - ts_ns(started)) / 1e9) if started and ended else None,
        "stats": {"turns": sum(w["turns"] for w in windows), "api_calls": len(seen_msgs),
                  "tool_calls": len(seen_tools), "tool_errors": errors, "compactions": len(windows) - 1,
                  "peak_context_tokens": max(w["peak_context_tokens"] for w in windows), "usage": total},
        "tools": dict(sorted(tools.items(), key=lambda kv: (-kv[1], kv[0]))),
        "files_touched": sorted(files),
        "context_windows": windows,
    }


# --------------------------------------------------------------------------- log snapshots

def session_dir(sid: str) -> Path:
    return TRACES / sid


def log_path(sid: str, sha: str) -> Path:
    return session_dir(sid) / "logs" / f"{sha}.jsonl.gz"


def store_log(sid: str, data: bytes) -> dict:
    """Content-addressed snapshot: named by the sha256 of the uncompressed bytes, never rewritten."""
    sha = hashlib.sha256(data).hexdigest()
    path = log_path(sid, sha)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(data, mtime=0))  # mtime=0: same input, same .gz bytes
        tmp.replace(path)
    gz = path.read_bytes()
    return {"sha256": sha, "bytes": len(data), "lines": data.count(b"\n"),
            "path": str(path.relative_to(REPO)), "gzip_sha256": hashlib.sha256(gz).hexdigest(),
            "gzip_bytes": len(gz), "locations": []}


def load_log(sid: str, sha: str) -> bytes | None:
    path = log_path(sid, sha)
    return gzip.decompress(path.read_bytes()) if path.exists() else None


# --------------------------------------------------------------------------- manifest

def manifest_path(sid: str) -> Path:
    return session_dir(sid) / "manifest.json"


def load_manifest(sid: str) -> dict:
    path = manifest_path(sid)
    return json.loads(path.read_text()) if path.exists() else {}


def save_manifest(sid: str, m: dict) -> None:
    path = manifest_path(sid)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def all_manifests() -> dict[str, dict]:
    return {p.parent.name: json.loads(p.read_text()) for p in sorted(TRACES.glob("*/manifest.json"))}


def sync_session(transcript: Path, redact: Redactor, status: str) -> tuple[str, dict, list[dict]]:
    """Snapshot one session's log (and subagent logs) and rewrite its manifest."""
    sid = transcript.stem
    data = redact(transcript.read_text(errors="replace"))
    entries = read_jsonl(data)
    old = load_manifest(sid)
    log = store_log(sid, data)
    if url := old.get("uploads", {}).get(log["sha256"]):
        log["locations"] = [url]
    subagents = []
    subdir = transcript.parent / sid / "subagents"
    for sub in sorted(subdir.glob("*.jsonl")) if subdir.is_dir() else []:
        sub_data = redact(sub.read_text(errors="replace"))
        s = summarize(read_jsonl(sub_data), redact.string(str(REPO)))
        subagents.append({"agent": sub.stem, "models": s["models"], "stats": s["stats"],
                          "log": store_log(sid, sub_data)})
    m = {
        "schema": SCHEMA,
        "session_id": sid,
        "status": status,
        **summarize(entries, redact.string(str(REPO))),
        "log": log,
        "subagents": subagents,
        "commits": old.get("commits", []),
        "uploads": old.get("uploads", {}),
        "langfuse": {"project": read_env(LANGFUSE_ENV).get("LANGFUSE_INIT_PROJECT_ID"), "session_id": sid},
        "redaction_policy": REDACTION_POLICY,
        "generator": "tools/traces/sync.py",
    }
    save_manifest(sid, m)
    return sid, m, entries


# --------------------------------------------------------------------------- jj

def jj(*args: str) -> subprocess.CompletedProcess:
    # Snapshotting must not skip files; the default limit for new files is 1 MiB.
    return subprocess.run([JJ, "--quiet", "--config", "snapshot.max-new-file-size=100MiB", *args],
                          capture_output=True, text=True, timeout=60, cwd=REPO)


def has_jj() -> bool:
    return (REPO / ".jj").is_dir() and os.access(JJ, os.X_OK)


COMMIT_TEMPLATE = ('change_id ++ "\\t" ++ commit_id ++ "\\t" ++ immutable ++ "\\t" ++ '
                   'json(description) ++ "\\n"')


def jj_commits(revset: str) -> list[dict]:
    r = jj("log", "--no-graph", "-r", revset, "-T", COMMIT_TEMPLATE)
    out = []
    for line in r.stdout.splitlines():
        cid, commit, immutable, desc = line.split("\t", 3)
        out.append({"change_id": cid, "commit_id": commit, "immutable": immutable == "true",
                    "description": json.loads(desc)})
    return out


def set_trailer(desc: str, sid: str, sha: str) -> str:
    """Replace this session's LLM-Trace trailer (any old sha, or none) with the given one."""
    lines = [ln for ln in desc.rstrip("\n").split("\n") if not re.match(rf"^{TRAILER}: {re.escape(sid)}(\s|$)", ln)]
    body = "\n".join(lines).rstrip("\n")
    # Join an existing trailer block (e.g. Co-Authored-By) rather than start a new paragraph.
    sep = "\n" if re.search(r"(^|\n)[A-Za-z][A-Za-z-]*: .+$", body) else ("\n\n" if body else "")
    return f"{body}{sep}{TRAILER}: {sid} sha256:{sha}\n"


def session_trailers(desc: str) -> list[tuple[str, str]]:
    return TRAILER_RE.findall(desc)


def link_commits(sid: str, m: dict) -> None:
    """Stamp this session's trailer on the mutable changes it made, then record every
    change that carries its trailer (mutable or not) in the manifest.

    @ is re-stamped with the latest log on every sync, together with the manifest in its
    tree, so the two always agree. Other changes are stamped once, if they have no
    trailer for this session yet, and then left alone; immutable ones are never touched."""
    if m.get("started"):
        made = f'mutable() & ::@ & author_date(after:"{m["started"]}") & ~(empty() & description(exact:""))'
        at = jj_commits("@")[0]["change_id"]
        for c in jj_commits(made):
            stamped = any(s_id == sid and sha for s_id, sha in session_trailers(c["description"]))
            if c["change_id"] != at and stamped:
                continue
            new = set_trailer(c["description"], sid, m["log"]["sha256"])
            if new != c["description"]:
                jj("describe", "-r", c["change_id"], "-m", new)
    commits = []
    for c in jj_commits(f'description(substring:"{TRAILER}: {sid}")'):
        shas = [s for s_id, s in TRAILER_RE.findall(c["description"]) if s_id == sid]
        commits.append({"change_id": c["change_id"],
                        "commit_id": c["commit_id"] if c["immutable"] else None,
                        "immutable": c["immutable"],
                        "summary": c["description"].split("\n", 1)[0],
                        "log_sha256": (shas[0] or None) if shas else None,
                        "log_url": m.get("uploads", {}).get(shas[0]) if shas and shas[0] else None})
    m["commits"] = sorted(commits, key=lambda c: (not c["immutable"], c["change_id"]))
    save_manifest(sid, m)


def prune_logs(sid: str, m: dict) -> None:
    """Keep the current log and every log a commit trailer points at; drop the rest."""
    keep = {m["log"]["sha256"]} | {s["log"]["sha256"] for s in m.get("subagents", [])}
    keep |= {c["log_sha256"] for c in m.get("commits", []) if c.get("log_sha256")}
    for path in (session_dir(sid) / "logs").glob("*.jsonl.gz"):
        if path.name.split(".")[0] not in keep:
            path.unlink()


# --------------------------------------------------------------------------- Langfuse (OTLP/JSON)

def _id(n: int, *parts: str) -> str:
    return hashlib.sha256("/".join(parts).encode()).hexdigest()[: 2 * n]


def _attr(key: str, value) -> dict:
    if isinstance(value, bool):
        v = {"boolValue": value}
    elif isinstance(value, int):
        v = {"intValue": str(value)}
    else:
        s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        v = {"stringValue": s if len(s) <= MAX_ATTR else s[:MAX_ATTR] + "…[truncated]"}
    return {"key": key, "value": v}


def _span(trace_id, span_id, parent, name, start, end, attrs) -> dict:
    s = {"traceId": trace_id, "spanId": span_id, "name": name, "kind": 1,
         "startTimeUnixNano": str(start), "endTimeUnixNano": str(max(end, start)),
         "attributes": [_attr(k, v) for k, v in attrs.items() if v not in (None, "", [])]}
    if parent:
        s["parentSpanId"] = parent
    return s


def turns_of(entries: list[dict]) -> list[list[dict]]:
    turns, cur = [], None
    for e in entries:
        if is_prompt(e):
            cur = [e]
            turns.append(cur)
        elif cur is not None and e.get("type") in ("assistant", "user"):
            cur.append(e)
    return turns


def turn_spans(sid: str, n: int, turn: list[dict], m: dict) -> list[dict]:
    prompt = turn[0]
    tid = _id(16, sid, prompt["uuid"])
    root = _id(8, tid, "root")
    spans, tools, msgs, last_ts, answer = [], {}, {}, ts_ns(prompt["timestamp"]), ""
    for e in turn[1:]:
        t = ts_ns(e.get("timestamp"))
        if e["type"] == "assistant":
            msg = e.get("message") or {}
            key = msg.get("id") or e.get("uuid")
            g = msgs.setdefault(key, {"start": last_ts, "end": t, "msg": msg, "blocks": []})
            g["end"] = t
            g["blocks"] += blocks(msg)
            for b in blocks(msg):
                if b.get("type") == "tool_use":
                    tools[b.get("id")] = {"name": b.get("name"), "input": b.get("input"), "start": t}
                elif b.get("type") == "text" and b.get("text", "").strip():
                    answer = b["text"]
        else:
            for b in blocks(e.get("message")):
                if b.get("type") == "tool_result" and b.get("tool_use_id") in tools:
                    tools[b["tool_use_id"]].update(end=t, output=b.get("content"), error=b.get("is_error"))
        last_ts = t or last_ts
    for key, g in msgs.items():
        u = g["msg"].get("usage") or {}
        spans.append(_span(tid, _id(8, tid, "gen", key), root, "llm", g["start"], g["end"], {
            "langfuse.observation.type": "generation",
            "gen_ai.request.model": g["msg"].get("model"),
            "gen_ai.usage.input_tokens": int(u.get("input_tokens") or 0),
            "gen_ai.usage.output_tokens": int(u.get("output_tokens") or 0),
            "langfuse.observation.usage_details": {k: int(v) for k, v in u.items() if isinstance(v, int)},
            "langfuse.observation.output": [b for b in g["blocks"] if b.get("type") != "thinking" or b.get("thinking")],
        }))
    for tu_id, tool in tools.items():
        spans.append(_span(tid, _id(8, tid, "tool", tu_id), root, tool["name"] or "tool",
                           tool["start"], tool.get("end", tool["start"]), {
            "langfuse.observation.type": "tool",
            "langfuse.observation.input": tool["input"],
            "langfuse.observation.output": tool.get("output"),
            "langfuse.observation.level": "ERROR" if tool.get("error") else None,
        }))
    end = max([last_ts] + [ts_ns(e.get("timestamp")) for e in turn])
    spans.append(_span(tid, root, None, f"turn {n}", ts_ns(prompt["timestamp"]), end, {
        "langfuse.trace.name": m.get("title") or "claude-code session",
        "session.id": sid,
        "langfuse.trace.input": text_of(prompt.get("message")),
        "langfuse.trace.output": answer,
        "langfuse.trace.tags": ["claude-code"],
        "langfuse.trace.metadata.turn": n,
        "langfuse.trace.metadata.manifest": str(manifest_path(sid).relative_to(REPO)),
        "langfuse.trace.metadata.log_sha256": m["log"]["sha256"],
    }))
    return spans


def export_langfuse(sid: str, entries: list[dict], m: dict, live: bool) -> int:
    env = read_env(LANGFUSE_ENV)
    host, pk, sk = env.get("LANGFUSE_HOST"), env.get("LANGFUSE_INIT_PROJECT_PUBLIC_KEY"), env.get("LANGFUSE_INIT_PROJECT_SECRET_KEY")
    if not (host and pk and sk):
        return 0
    state_file = STATE / f"{sid}.json"
    done = set(json.loads(state_file.read_text())["exported"]) if state_file.exists() else set()
    turns = turns_of(entries)
    if live:  # the last turn may still be running; the Stop hook exports it when it ends
        turns = turns[:-1]
    pending = [(n, t) for n, t in enumerate(turns, 1) if t[0]["uuid"] not in done]
    if not pending:
        return 0
    spans = [s for n, t in pending for s in turn_spans(sid, n, t, m)]
    body = {"resourceSpans": [{"resource": {"attributes": [_attr("service.name", "claude-code")]},
                               "scopeSpans": [{"scope": {"name": "llm-traces/sync.py"}, "spans": spans}]}]}
    req = urllib.request.Request(f"{host}/api/public/otel/v1/traces", data=gzip.compress(json.dumps(body).encode()),
                                 method="POST", headers={
        "Content-Type": "application/json", "Content-Encoding": "gzip",
        "Authorization": "Basic " + base64.b64encode(f"{pk}:{sk}".encode()).decode()})
    with urllib.request.urlopen(req, timeout=15) as r:
        r.read()
    STATE.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"exported": sorted(done | {t[0]["uuid"] for _, t in pending})}))
    return len(pending)


# --------------------------------------------------------------------------- CDN upload

def log_url(sid: str, sha: str) -> str:
    return f"{CDN_BASE}/raw-traces/{sid}/{sha}.jsonl.gz"


def fetch_log(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "llm-traces-sync"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return gzip.decompress(r.read())


def remote_matches(url: str, sha: str) -> bool:
    try:
        return hashlib.sha256(fetch_log(url)).hexdigest() == sha
    except (OSError, EOFError, gzip.BadGzipFile):
        return False


def upload_log(sid: str, sha: str) -> str:
    """Put one log in R2 (unless the CDN already serves it) and prove the CDN returns those bytes."""
    url = log_url(sid, sha)
    if remote_matches(url, sha):
        return url
    path = log_path(sid, sha)
    if not path.exists():
        raise FileNotFoundError(f"log {sha[:12]} of {sid} is neither stored locally nor on the CDN")
    key = f"{CDN_BUCKET}/raw-traces/{sid}/{sha}.jsonl.gz"
    if not WRANGLER.exists():
        raise FileNotFoundError("wrangler is not installed; run: python3 tools/traces/sync.py init")
    r = subprocess.run([NODE, str(WRANGLER), "r2", "object", "put", key, "--remote",
                        "--file", str(path), "--content-type", "application/gzip"],
                       cwd=CDN_DIR, capture_output=True, text=True, timeout=300,
                       env={**os.environ, "WRANGLER_SEND_METRICS": "false"})
    if r.returncode != 0:
        raise RuntimeError(f"wrangler r2 object put failed:\n{r.stdout}{r.stderr}")
    if not remote_matches(url, sha):
        raise RuntimeError(f"uploaded {url} but the CDN does not serve content with sha256 {sha}")
    return url


def cmd_upload() -> int:
    """Upload every log a commit points at (and subagent logs), then record the URLs."""
    failed = 0
    # @'s log is replaced every turn; upload it only once @ stops being the working copy.
    at = jj_commits("@")[0]["change_id"] if has_jj() else None
    for sid, m in all_manifests().items():
        if m.get("schema") != SCHEMA:
            continue
        wanted = {c["log_sha256"] for c in m.get("commits", []) if c.get("log_sha256") and c["change_id"] != at}
        wanted |= {s["log"]["sha256"] for s in m.get("subagents", [])}
        uploads = m.setdefault("uploads", {})
        for sha in sorted(wanted - uploads.keys()):
            try:
                uploads[sha] = upload_log(sid, sha)
                print(f"uploaded {uploads[sha]}")
            except (OSError, RuntimeError) as e:
                print(f"ERROR {e}", file=sys.stderr)
                failed += 1
        for c in m.get("commits", []):
            c["log_url"] = uploads.get(c.get("log_sha256"))
        m["log"]["locations"] = [uploads[m["log"]["sha256"]]] if m["log"]["sha256"] in uploads else []
        save_manifest(sid, m)
    return 1 if failed else 0


# --------------------------------------------------------------------------- commands

def process(transcript: Path, redact: Redactor, status: str, live: bool) -> dict:
    sid, m, entries = sync_session(transcript, redact, status)
    if has_jj():
        link_commits(sid, m)
    prune_logs(sid, m)
    try:
        export_langfuse(sid, entries, m, live)
    except OSError as e:  # Langfuse down: those turns are retried next time
        log(f"langfuse export deferred for {sid}: {e}")
    return m


def cmd_hook() -> None:
    try:
        payload = json.load(sys.stdin)
        status = "ended" if payload.get("hook_event_name") == "SessionEnd" else "open"
        process(Path(payload["transcript_path"]), Redactor(), status, live=False)
    except Exception:
        log(traceback.format_exc())


def cmd_sync(args: list[str]) -> None:
    src = claude_project_dir()
    paths = sorted(src.glob("*.jsonl")) if args in ([], ["--all"]) else [src / f"{a}.jsonl" for a in args]
    redact = Redactor()
    for p in paths:
        live = time.time() - p.stat().st_mtime < LIVE_SECONDS
        old_status = load_manifest(p.stem).get("status")
        m = process(p, redact, "open" if live else (old_status or "ended"), live)
        s = m["stats"]
        print(f"{m['session_id']}  {s['turns']} turns  {s['tool_calls']} tools  log sha256:{m['log']['sha256'][:12]}… "
              f"{m['log']['bytes']:,} B  commits: {len(m['commits'])}{'  (live)' if live else ''}")


def cmd_commit(args: list[str]) -> int:
    """Finish @ with a message whose trailers match the manifest in its tree, then start a new change."""
    if len(args) != 2 or args[0] != "-m":
        print("usage: sync.py commit -m MESSAGE", file=sys.stderr)
        return 2
    cmd_sync([])  # writes manifests and stamps @ with the current log of each session
    at = jj_commits("@")[0]
    desc = args[1]
    for sid, sha in session_trailers(at["description"]):
        if sha:
            desc = set_trailer(desc, sid, sha)
    if jj("describe", "-r", "@", "-m", desc).returncode or jj("new").returncode:
        print("jj describe/new failed", file=sys.stderr)
        return 1
    print(f"committed {at['change_id'][:12]}")
    return 0


def cmd_push(args: list[str]) -> int:
    cmd_sync([])
    if cmd_upload() != 0:
        print("log upload failed; not pushing", file=sys.stderr)
        return 1
    cmd_sync([])  # restamp @ now that the manifest records the uploads
    if cmd_check() != 0:
        print("trace check failed; not pushing", file=sys.stderr)
        return 1
    r = subprocess.run([JJ, "--config", "snapshot.max-new-file-size=100MiB", "git", "push", *args], cwd=REPO)
    if r.returncode == 0:
        cmd_sync([])  # record git SHAs of the commits that just became immutable
    return r.returncode


def cmd_check(remote: bool = False) -> int:
    redact, errors, notes = Redactor(), [], []
    manifests = all_manifests()
    for sid, m in manifests.items():
        if m.get("schema") != SCHEMA:
            errors.append(f"{sid}: unknown schema {m.get('schema')}")
            continue
        logs = [m["log"]] + [s["log"] for s in m.get("subagents", [])]
        logs += [{"sha256": c["log_sha256"]} for c in m.get("commits", []) if c.get("log_sha256")]
        uploads = m.get("uploads", {})
        for sha, url in uploads.items():
            if url != log_url(sid, sha):
                errors.append(f"{sid}: upload URL {url} does not match its sha256")
            elif remote and not remote_matches(url, sha):
                errors.append(f"{sid}: CDN does not serve log {sha[:12]} at {url}")
        for lg in logs:
            data = load_log(sid, lg["sha256"])
            if data is None:
                if lg["sha256"] not in uploads:
                    errors.append(f"{sid}: log {lg['sha256'][:12]} is neither stored locally nor uploaded")
                continue
            if hashlib.sha256(data).hexdigest() != lg["sha256"]:
                errors.append(f"{sid}: log {lg['sha256'][:12]} content does not match its name")
            if leaks := redact.leaks(data.decode(errors="replace")):
                errors.append(f"{sid}: unredacted {leaks} in log {lg['sha256'][:12]}")
        # Logs are append-only: every log a commit points at should be a prefix of the current one.
        current = load_log(sid, m["log"]["sha256"]) or b""
        for c in m.get("commits", []):
            old = c.get("log_sha256") and load_log(sid, c["log_sha256"])
            if old and not current.startswith(old):
                notes.append(f"{sid}: log {c['log_sha256'][:12]} of {c['change_id'][:12]} is not a prefix of the current log")
    if has_jj():
        for c in jj_commits(f'description(substring:"{TRAILER}:")'):
            for sid, sha in TRAILER_RE.findall(c["description"]):
                where = f"change {c['change_id'][:12]}"
                if not sha:
                    notes.append(f"{where}: legacy trailer without sha256 for {sid}")
                elif sid not in manifests:
                    errors.append(f"{where}: session {sid} has no manifest")
                elif load_log(sid, sha) is None and sha not in manifests[sid].get("uploads", {}):
                    errors.append(f"{where}: points at log {sha[:12]} that is not stored")
                else:
                    # The manifest committed in the same tree should name the same log.
                    r = jj("file", "show", "-r", c["commit_id"], f"traces/{sid}/manifest.json")
                    tree_sha = json.loads(r.stdout).get("log", {}).get("sha256") if r.returncode == 0 else None
                    if tree_sha != sha:
                        notes.append(f"{where}: trailer log {sha[:12]} != manifest-in-tree log "
                                     f"{(tree_sha or 'none')[:12]} (committed without trace-commit)")
    for n in notes:
        print("note ", n)
    for e in errors:
        print("ERROR", e)
    print(f"{len(manifests)} session(s), {len(errors)} error(s), {len(notes)} note(s)")
    return 1 if errors else 0


def cmd_init() -> None:
    jj("config", "set", "--repo", "snapshot.max-new-file-size", "100MiB")
    # `jj trace-push [ARGS]` from anywhere in the workspace.
    jj("config", "set", "--repo", "aliases.trace-push", json.dumps(
        ["util", "exec", "--", "bash", "-c",
         'exec python3 "$JJ_WORKSPACE_ROOT/tools/traces/sync.py" push "$@"', "--"]))
    jj("config", "set", "--repo", "aliases.trace-commit", json.dumps(
        ["util", "exec", "--", "bash", "-c",
         'exec python3 "$JJ_WORKSPACE_ROOT/tools/traces/sync.py" commit "$@"', "--"]))
    print("jj repo config set: snapshot.max-new-file-size=100MiB, aliases trace-commit, trace-push")
    r = subprocess.run([shutil.which("npm") or "npm", "ci", "--no-fund", "--no-audit"], cwd=CDN_DIR)
    print("infra/cdn: pinned wrangler installed" if r.returncode == 0 else "infra/cdn: npm ci failed")


def log(msg: str) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    with open(STATE / "hook.log", "a") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} {msg}\n")


def main(argv: list[str]) -> int:
    cmd, args = (argv[0], argv[1:]) if argv else ("", [])
    if cmd == "hook":
        cmd_hook()
    elif cmd == "sync":
        cmd_sync(args)
    elif cmd == "commit":
        return cmd_commit(args)
    elif cmd == "push":
        return cmd_push(args)
    elif cmd == "upload":
        return cmd_upload()
    elif cmd == "check":
        return cmd_check(remote=args == ["--remote"])
    elif cmd == "init":
        cmd_init()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Publish Claude Code session traces for this repo.

Layout (llm-dlc/specification.md has the full spec, llm-dlc/README.md the procedure):

  llm-dlc/index.json                                 checked in: one row per session, for lookups
  llm-dlc/traces/<session-id>/manifest.json          checked in: stats, log pointer, commits
  llm-dlc/traces/<session-id>/summary.md             checked in: readable summary (llm-dlc/summary-template.md)
  llm-dlc/traces/<session-id>/logs/<sha256>.jsonl.gz gitignored: immutable redacted log snapshots

Public URL of a log: https://terminalvalue.net/raw-traces/<session-id>/<sha256>.jsonl.gz

Identifiers:
  session   the Claude Code session UUID
  log       sha256 of the *uncompressed* redacted JSONL; a snapshot file never changes
  commit    each change made in a session carries the trailer
              LLM-Trace: <session-id> sha256:<log-sha256>
            next to links to the session summary and the log
              LLM-Trace-Summary: <repo URL>/blob/main/llm-dlc/traces/<session-id>/summary.md
              LLM-Trace-Log: https://terminalvalue.net/raw-traces/<session-id>/<sha256>.jsonl.gz
            and the manifest lists those changes (jj change id, git SHA once immutable)

Commands:
  sync.py hook                  Claude Code Stop/SessionEnd hook (hook JSON on stdin)
  sync.py sync [--all | ID...]  snapshot sessions of this repo from ~/.claude/projects
  sync.py commit -m MSG [-m ..] finish @ with trailers matching its manifest (alias: jj trace-commit);
                                each -m is one paragraph, as in git
  sync.py upload                upload logs that commits point at to the CDN, verify, record URLs
  sync.py push [JJ PUSH ARGS]   sync, upload, check, then `jj git push` (alias: jj trace-push)
  sync.py check [--remote]      verify hashes, trailers and redaction (--remote: re-download uploads)
  sync.py unpublish SID SHA     delete one log from R2 and purge it from the CDN cache (for leaks)
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
import string
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHANGES = REPO / "llm-dlc"
TRACES = CHANGES / "traces"
# Where older commits keep their manifests: before the changes/ layout, then before llm-dlc/.
LEGACY_TRACES = ("traces", "changes/traces")
INDEX = CHANGES / "index.json"
CHANGES_README = CHANGES / "README.md"
SUMMARY_TEMPLATE = CHANGES / "summary-template.md"
INDEX_SCHEMA = "llm-trace-index/v1"
LANGFUSE_ENV = CHANGES / "infra" / "langfuse" / ".env"
STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "llm-traces"
EXTRA_REDACTIONS = Path.home() / ".config" / "llm-traces" / "redact.txt"
# Cloudflare API token with Zone:Read and Cache Purge on the CDN zone; only `unpublish` uses it.
PURGE_TOKEN = Path.home() / ".config" / "llm-traces" / "cloudflare-token"
SCHEMA = "llm-trace-manifest/v1"
REDACTION_POLICY = 3           # bump when redaction changes the bytes it produces
REDACT_KEYS = {"organizationUuid", "accountUuid"}  # account identifiers Claude Code records in attachments
TRAILER = "LLM-Trace"
TRAILER_RE = re.compile(rf"^{TRAILER}: (\S+)(?: sha256:([0-9a-f]{{64}}))?\s*$", re.M)
LINK_TRAILERS = ("LLM-Trace-Summary", "LLM-Trace-Log")  # convenience links next to LLM-Trace
DEFAULT_BRANCH = "main"        # summary links point at the published copy on this branch
# Hooks inherit the PATH Claude Code started with, which may predate ~/.local/bin.
JJ = shutil.which("jj") or str(Path.home() / ".local" / "bin" / "jj")
MAX_ATTR = 64 * 1024           # truncate large tool outputs sent to Langfuse
LIVE_SECONDS = 600             # a transcript written this recently may have an unfinished turn
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
# Logs are served from R2 by the Worker in llm-dlc/infra/cdn; the URL path is the object key.
CDN_BASE = "https://terminalvalue.net"
CDN_BUCKET = "llm-traces"
CDN_DIR = CHANGES / "infra" / "cdn"
NODE = shutil.which("node") or str(Path.home() / ".local" / "bin" / "node")
WRANGLER = CDN_DIR / "node_modules" / "wrangler" / "bin" / "wrangler.js"  # pinned in llm-dlc/infra/cdn/package.json


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


def personal_literals() -> tuple[list[tuple[re.Pattern, str]], str]:
    """(pattern, replacement) pairs for this machine: home path, emails, local secrets.
    Emails match case-insensitively. GitHub noreply addresses are public by design and are kept."""
    pairs: list[tuple[str, str, int]] = []
    home, user = str(Path.home()), os.environ.get("USER") or Path.home().name
    pairs += [(home, "~", 0), (re.sub(r"[^A-Za-z0-9]", "-", home), "-home-user", 0)]
    emails = {_cmd("git", "config", "--get", "user.email"), _cmd(JJ, "config", "get", "user.email")}
    try:
        account = json.loads((Path.home() / ".claude.json").read_text()).get("oauthAccount") or {}
        emails.add(account.get("emailAddress") or "")
    except (OSError, ValueError):
        pass
    emails = {e.lower() for e in emails if e and not e.lower().endswith("@users.noreply.github.com")}
    pairs += [(e, "user@example.com", re.I) for e in emails]
    pairs += [(e.split("@")[0], "user", re.I) for e in emails if len(e.split("@")[0]) >= 4]
    pairs += [(v, "[REDACTED:local-secret]", 0) for k, v in read_env(LANGFUSE_ENV).items()
              if re.search(r"SECRET|PASSWORD|KEY|SALT|AUTH|DATABASE_URL", k) and len(v) >= 12]
    if PURGE_TOKEN.exists() and len(token := PURGE_TOKEN.read_text().strip()) >= 12:
        pairs.append((token, "[REDACTED:local-secret]", 0))
    if EXTRA_REDACTIONS.exists():
        for line in EXTRA_REDACTIONS.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                lit, _, rep = line.partition("=>")
                pairs.append((lit.strip(), rep.strip() or "[REDACTED]", 0))
    pairs.sort(key=lambda p: -len(p[0]))
    return [(re.compile(re.escape(lit), flags), rep) for lit, rep, flags in pairs], user


class Redactor:
    def __init__(self) -> None:
        self.literals, user = personal_literals()
        # Also match right after a literal backslash-n/t/r: JSON echoed inside a tool result
        # keeps its escapes, so there is no word boundary before the name.
        self.user_re = (re.compile(rf"(?:(?<=\\[nrt])|(?<![A-Za-z0-9_])){re.escape(user)}\b")
                        if len(user) >= 3 else None)
        self.secret_res = [(k, re.compile(p, re.S)) for k, p in SECRET_PATTERNS]

    def string(self, text: str) -> str:
        for rx, rep in self.literals:
            text = rx.sub(lambda _m, r=rep: r, text)
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
            out.append(json.dumps(_walk(_scrub(obj), self.string), ensure_ascii=False, separators=(",", ":")))
        return ("\n".join(out) + "\n" if out else "").encode()

    def leaks(self, jsonl: str) -> list[str]:
        found: set[str] = set()

        def scan(s: str) -> str:
            found.update("personal literal" for rx, _ in self.literals if rx.search(s))
            found.update(kind for kind, rx in self.secret_res if rx.search(s))
            if self.user_re and self.user_re.search(s):
                found.add("username")
            return s

        for line in jsonl.splitlines():
            try:
                obj = json.loads(line)
            except ValueError:
                scan(line)
                continue
            _walk(obj, scan)
            if _unscrubbed(obj):
                found.add("account identifier")
        return sorted(found)


def _walk(obj, fn):
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [_walk(v, fn) for v in obj]
    if isinstance(obj, dict):
        return {fn(k): _walk(v, fn) for k, v in obj.items()}
    return obj


def _scrub(obj):
    """Rules that act on JSON structure rather than on strings: account identifiers that
    Claude Code records under known keys, and thinking-block signatures (opaque bytes)."""
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    if isinstance(obj, dict):
        return {k: "[REDACTED:account-id]" if k in REDACT_KEYS and isinstance(v, str) else _scrub(v)
                for k, v in obj.items() if not (k == "signature" and obj.get("type") == "thinking")}
    return obj


def _unscrubbed(obj) -> bool:
    if isinstance(obj, list):
        return any(_unscrubbed(v) for v in obj)
    if isinstance(obj, dict):
        return any((k in REDACT_KEYS and isinstance(v, str) and not v.startswith("[REDACTED")) or _unscrubbed(v)
                   for k, v in obj.items())
    return False


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
        "client": {"tool": "claude-code", "version": version}, "models": sorted(models),
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
    return {"sha256": sha, **log_info(sid, sha), "path": str(path.relative_to(REPO))}


def log_info(sid: str, sha: str) -> dict:
    """Sizes of a stored log: its content in bytes and lines, and the gzip file in bytes."""
    gz = log_path(sid, sha).read_bytes()
    data = gzip.decompress(gz)
    return {"bytes": len(data), "lines": data.count(b"\n"), "gzip_bytes": len(gz)}


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
        "logs": old.get("logs") or {sha: {"url": url} for sha, url in old.get("uploads", {}).items()},
        "redaction_policy": REDACTION_POLICY,
        "generator": "llm-dlc/tools/sync.py",
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


def repo_web_url() -> str | None:
    """https URL of the `origin` remote on GitHub (or a similar forge), if there is one."""
    url = _cmd("git", "-C", str(REPO), "config", "--get", "remote.origin.url")
    m = re.match(r"^(?:git@([^:]+):|ssh://git@([^/]+)/|https://([^/]+)/)(.+?)(?:\.git)?/?$", url)
    return f"https://{m[1] or m[2] or m[3]}/{m[4]}" if m else None


def summary_url(sid: str) -> str:
    rel = f"{summary_path(sid).relative_to(REPO)}"
    base = repo_web_url()
    return f"{base}/blob/{DEFAULT_BRANCH}/{rel}" if base else rel


def _is_session_trailer(line: str, sid: str) -> bool:
    return bool(re.match(rf"^{TRAILER}: {re.escape(sid)}(\s|$)", line)
                or (re.match(rf"^({'|'.join(LINK_TRAILERS)}): ", line) and f"/{sid}/" in line))


def set_trailer(desc: str, sid: str, sha: str) -> str:
    """Replace this session's trailers (any old sha, or none) with ones for the given log:
    links to the summary and the log, then the LLM-Trace identifier."""
    lines = [ln for ln in desc.rstrip("\n").split("\n") if not _is_session_trailer(ln, sid)]
    body = "\n".join(lines).rstrip("\n")
    # Join an existing trailer block (e.g. Co-Authored-By) rather than start a new paragraph.
    sep = "\n" if re.search(r"(^|\n)[A-Za-z][A-Za-z-]*: .+$", body) else ("\n\n" if body else "")
    return (f"{body}{sep}{LINK_TRAILERS[0]}: {summary_url(sid)}\n"
            f"{LINK_TRAILERS[1]}: {log_url(sid, sha)}\n"
            f"{TRAILER}: {sid} sha256:{sha}\n")


def commit_summary(desc: str) -> str | None:
    """The summary line, or None while the change has no message besides trailers."""
    first = desc.strip().split("\n", 1)[0]
    return None if not first or re.match(r"^[A-Za-z][A-Za-z-]*: ", first) and not commit_body(desc) else first


def commit_body(desc: str) -> str:
    """The description without its summary line and trailer block: the change's narrative."""
    paras = desc.strip().split("\n\n")[1:]
    if paras and all(re.match(r"^[A-Za-z][A-Za-z-]*: ", ln) for ln in paras[-1].split("\n")):
        paras = paras[:-1]
    return "\n\n".join(paras).strip()


def session_trailers(desc: str) -> list[tuple[str, str]]:
    return TRAILER_RE.findall(desc)


def link_commits(sid: str, m: dict, current: bool) -> None:
    """Stamp this session's trailer on the mutable changes it made, then record every
    change that carries its trailer (mutable or not) in the manifest.

    A session "made" the mutable ancestors of @ created while it ran, plus @ itself if the
    session is the one running now (`current`). @ is re-stamped with the latest log on every
    sync, together with the manifest in its tree, so the two always agree. Other changes are
    stamped once, if they have no trailer for this session yet, and then left alone;
    immutable ones are never touched."""
    if m.get("started") and m.get("ended"):
        made = (f'mutable() & ::@ & author_date(after:"{m["started"]}") & author_date(before:"{m["ended"]}")'
                f' & ~(empty() & description(exact:""))')
        if current:
            made = f"({made}) | @"
        at = jj_commits("@")[0]["change_id"]
        for c in jj_commits(made):
            stamped = any(s_id == sid and sha for s_id, sha in session_trailers(c["description"]))
            if c["change_id"] != at and stamped:
                continue
            new = set_trailer(c["description"], sid, m["log"]["sha256"])
            if new != c["description"]:
                jj("describe", "-r", c["change_id"], "-m", new)
    commits = []
    # jj lists children first; the manifest lists commits oldest first.
    for c in reversed(jj_commits(f'description(substring:"{TRAILER}: {sid}")')):
        shas = [s for s_id, s in TRAILER_RE.findall(c["description"]) if s_id == sid]
        commits.append({"change_id": c["change_id"],
                        "commit_id": c["commit_id"] if c["immutable"] else None,
                        "immutable": c["immutable"],
                        "summary": commit_summary(c["description"]),
                        "body": commit_body(c["description"]),
                        "log_sha256": (shas[0] or None) if shas else None})
    m["commits"] = commits
    save_manifest(sid, m)


def finalize_logs(sid: str, m: dict) -> None:
    """m["logs"] lists every log still referenced (current, subagents, commit trailers) with its
    sizes and, once uploaded, its URL. Local snapshots nothing references any more are deleted."""
    keep = {m["log"]["sha256"]} | {s["log"]["sha256"] for s in m.get("subagents", [])}
    keep |= {c["log_sha256"] for c in m.get("commits", []) if c.get("log_sha256")}
    logs = {}
    for sha in sorted(keep):
        entry = {"bytes": None, "lines": None, "gzip_bytes": None, "url": None, **(m.get("logs", {}).get(sha) or {})}
        if log_path(sid, sha).exists():
            entry.update(log_info(sid, sha))
        logs[sha] = entry
    m["logs"] = logs
    for path in (session_dir(sid) / "logs").glob("*.jsonl.gz"):
        if path.name.split(".")[0] not in keep:
            path.unlink()
    save_manifest(sid, m)


# --------------------------------------------------------------------------- summary and index

def summary_path(sid: str) -> Path:
    return session_dir(sid) / "summary.md"


def _when(ts: str | None) -> str:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC") if ts else "?"


def _clip(text: str, limit: int) -> str:
    """Shorten at a paragraph or line break, closing a code fence the cut left open."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    cut = cut[:max(cut.rfind("\n\n"), cut.rfind("\n"), limit // 2)].rstrip()
    if cut.count("```") % 2:
        cut += "\n```"
    return cut + "\n\n*… (shortened; the log has the full text)*"


def _escape_html(text: str) -> str:
    """Keep `<placeholder>` text visible on GitHub, which would drop it as an unknown tag.
    Code spans and fenced blocks are left alone: they already render literally."""
    parts = re.split(r"(```.*?```|`[^`\n]*`)", text, flags=re.S)
    return "".join(p if i % 2 else p.replace("<", "&lt;") for i, p in enumerate(parts))


def _prompt_text(e: dict) -> str:
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text_of(e["message"]), flags=re.S)
    return re.sub(r"\x1b\[[0-9;]*m", "", text).strip()


def _turn_md(n: int, turn: list[dict], repo_prefix: str) -> str | None:
    """One prompt and its outcome, or one line for a slash command; None for noise."""
    first, text = turn[0], _prompt_text(turn[0])
    if first.get("isCompactSummary"):
        return f"*{_when(first.get('timestamp'))}: context compacted; the conversation continues from a summary.*"
    if cmd := re.search(r"<command-name>(.*?)</command-name>", text):
        out = re.search(r"<local-command-stdout>(.*?)</local-command-stdout>", text, re.S)
        return f"*{_when(first.get('timestamp'))}: `{cmd[1]}`{': ' + out[1].strip() if out else ''}*"
    if not text or text.startswith("<local-command") or re.fullmatch(r"/\S+", text):
        return None
    tools, files, reply = {}, [], ""
    for e in turn:
        for b in blocks(e.get("message")) if e.get("type") == "assistant" else []:
            if b.get("type") == "tool_use":
                tools[b.get("name")] = tools.get(b.get("name"), 0) + 1
                path = (b.get("input") or {}).get("file_path")
                if b.get("name") in EDIT_TOOLS and isinstance(path, str):
                    path = path[len(repo_prefix) + 1:] if path.startswith(repo_prefix + "/") else path
                    files += [path] if path not in files else []
            elif b.get("type") == "text" and b.get("text", "").strip():
                reply = b["text"]
    quoted = "\n".join("> " + ln if ln else ">" for ln in _escape_html(_clip(text, 800)).split("\n"))
    parts = [f"### {n}. {_when(first.get('timestamp'))}", quoted]
    if reply:
        parts.append("**Reply:**\n\n" + _escape_html(_clip(reply, 1500)))
    meta = []
    if tools:
        meta.append(f"{sum(tools.values())} tool calls ("
                    + ", ".join(f"{k} {v}" for k, v in sorted(tools.items(), key=lambda kv: -kv[1])) + ")")
    if files:
        meta.append("edited " + ", ".join(f"`{f}`" for f in files))
    if meta:
        parts.append("<sub>" + " · ".join(meta) + "</sub>")
    return "\n\n".join(parts)


def render_summary(sid: str, m: dict, entries: list[dict], repo_prefix: str) -> None:
    """Write summary.md from the template. It is derived only from the redacted log and the
    manifest, so it is safe to publish and can be rebuilt from a published log."""
    s, u = m["stats"], m["stats"]["usage"]
    repo = repo_web_url()
    changes = []
    for c in m.get("commits", []):
        ref = f"[`{c['commit_id'][:12]}`]({repo}/commit/{c['commit_id']})" if c.get("commit_id") and repo \
            else f"change `{c['change_id'][:12]}`"
        if not c.get("summary"):  # the working copy before its first commit message
            changes.append(f"### (in progress)\n\n{ref}, not yet described")
            continue
        log_ref = f" · [log `{c['log_sha256'][:12]}`]({log_url(sid, c['log_sha256'])})" if c.get("log_sha256") else ""
        changes.append(f"### {_escape_html(c['summary'])}\n\n{ref}{log_ref}"
                       + (f"\n\n{_escape_html(c['body'])}" if c.get("body") else ""))
    turns, n = [], 0
    for turn in turns_of(entries):
        if (md := _turn_md(n + 1, turn, repo_prefix)) is not None:
            n += md.startswith("### ")
            turns.append(md)
    subagents = "".join(f"\n- `{a['agent']}`: {a['stats']['turns']} turns, {a['stats']['tool_calls']} tool calls, "
                        f"[log]({log_url(sid, a['log']['sha256'])})" for a in m.get("subagents", []))
    values = {
        "title": m.get("title") or (m.get("first_prompt") or "Untitled session").split("\n")[0][:80],
        "session_id": sid, "status": m["status"],
        "when": f"{_when(m.get('started'))} to {_when(m.get('ended'))}"
                + (f" ({m['duration_seconds'] // 60} min)" if m.get("duration_seconds") else ""),
        "models": ", ".join(f"`{x}`" for x in m.get("models", [])) or "?",
        "client": f"{m['client']['tool']} {m['client']['version'] or ''}".strip(),
        "activity": f"{s['turns']} prompts, {s['api_calls']} API calls, {s['tool_calls']} tool calls "
                    f"({s['tool_errors']} failed), {s['compactions']} compactions",
        "tokens": f"{u['output_tokens']:,} output, {u['input_tokens']:,} input, "
                  f"{u['cache_read_input_tokens']:,} cache read, {u['cache_creation_input_tokens']:,} cache write; "
                  f"peak context {s['peak_context_tokens']:,}",
        "log_url": log_url(sid, m["log"]["sha256"]),
        "log_sha256": m["log"]["sha256"],
        "log_sha256_short": m["log"]["sha256"][:12],
        "log_size": f"{m['log']['gzip_bytes'] / 1e6:.1f} MB",
        "changes": "\n\n".join(changes) or "*No commits yet.*",
        "turns": "\n\n".join(turns) or "*No prompts yet.*",
        "files": "\n".join(f"- `{f}`" for f in m.get("files_touched", [])) or "*None.*",
        "tools": ", ".join(f"{k} {v}" for k, v in m.get("tools", {}).items()) or "*None.*",
        "subagents": subagents.strip() or "*None.*",
    }
    text = string.Template(SUMMARY_TEMPLATE.read_text()).safe_substitute(values)
    summary_path(sid).write_text(re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n")


INDEX_BEGIN, INDEX_END = "<!-- index:begin (generated by llm-dlc/tools/sync.py) -->", "<!-- index:end -->"


def write_index() -> None:
    """llm-dlc/index.json lists every session with the commits it made, so a reader can go from
    a commit or a date to a session without opening every manifest. The same rows are rendered as
    a table in llm-dlc/README.md, between the index markers."""
    rows = []
    for sid, m in all_manifests().items():
        if m.get("schema") != SCHEMA:
            continue
        rows.append({
            "session_id": sid, "title": m.get("title"), "status": m.get("status"),
            "started": m.get("started"), "ended": m.get("ended"), "models": m.get("models", []),
            "turns": m.get("stats", {}).get("turns"),
            "log_sha256": m.get("log", {}).get("sha256"),
            "manifest": str(manifest_path(sid).relative_to(CHANGES)),
            "summary": str(summary_path(sid).relative_to(CHANGES)),
            "commits": [{k: c.get(k) for k in ("change_id", "commit_id", "summary")} for c in m.get("commits", [])],
        })
    rows.sort(key=lambda r: r["started"] or "")
    index = {"schema": INDEX_SCHEMA, "sessions": rows}
    tmp = INDEX.with_suffix(".tmp")
    tmp.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(INDEX)
    if CHANGES_README.exists():
        table = ["| Started | Session | Prompts | Commits | Status |", "|---|---|---|---|---|"]
        for r in reversed(rows):
            title = (r["title"] or r["session_id"]).replace("|", "\\|")
            table.append(f"| {_when(r['started'])} | [{title}]({r['summary']}) | {r['turns']} | "
                         f"{len(r['commits'])} | {r['status']} |")
        readme = CHANGES_README.read_text()
        start, end = readme.find(INDEX_BEGIN), readme.find(INDEX_END)
        if 0 <= start < end:
            CHANGES_README.write_text(readme[:start + len(INDEX_BEGIN)] + "\n" + "\n".join(table) + "\n" + readme[end:])


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
        raise FileNotFoundError("wrangler is not installed; run: python3 llm-dlc/tools/sync.py init")
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
        logs = m.setdefault("logs", {})
        for sha in sorted(wanted):
            if logs.get(sha, {}).get("url"):
                continue
            try:
                logs.setdefault(sha, {})["url"] = upload_log(sid, sha)
                print(f"uploaded {logs[sha]['url']}")
            except (OSError, RuntimeError) as e:
                print(f"ERROR {e}", file=sys.stderr)
                failed += 1
        save_manifest(sid, m)
    return 1 if failed else 0


def cloudflare(method: str, path: str, token: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"https://api.cloudflare.com/client/v4{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.load(e)


def purge_url(url: str) -> None:
    """Evict one URL from every Cloudflare edge cache (including Worker Cache API entries)."""
    if not PURGE_TOKEN.exists():
        raise FileNotFoundError(f"no Cloudflare API token at {PURGE_TOKEN} (llm-dlc/specification.md, Storage)")
    token = PURGE_TOKEN.read_text().strip()
    host = urllib.parse.urlsplit(url).hostname
    zones = cloudflare("GET", f"/zones?name={host}", token)
    if not zones.get("success") or not zones.get("result"):
        raise RuntimeError(f"zone lookup for {host} failed: {zones.get('errors')}")
    r = cloudflare("POST", f"/zones/{zones['result'][0]['id']}/purge_cache", token, {"files": [url]})
    if not r.get("success"):
        raise RuntimeError(f"cache purge failed: {r.get('errors')}")


def cmd_unpublish(args: list[str]) -> int:
    """Take one log off the CDN: delete the R2 object, purge the edge caches, forget the URL.
    A commit that still points at the log breaks invariant 1 until its trailer is rewritten."""
    if len(args) != 2 or not re.fullmatch(r"[0-9a-f]{64}", args[1]):
        print("usage: sync.py unpublish SESSION_ID SHA256", file=sys.stderr)
        return 2
    sid, sha = args
    url = log_url(sid, sha)
    r = subprocess.run([NODE, str(WRANGLER), "r2", "object", "delete",
                        f"{CDN_BUCKET}/raw-traces/{sid}/{sha}.jsonl.gz", "--remote"],
                       cwd=CDN_DIR, capture_output=True, text=True, timeout=300,
                       env={**os.environ, "WRANGLER_SEND_METRICS": "false"})
    if r.returncode != 0:
        print(f"ERROR wrangler r2 object delete failed:\n{r.stdout}{r.stderr}", file=sys.stderr)
        return 1
    try:
        purge_url(url)
    except (OSError, RuntimeError) as e:
        print(f"ERROR deleted from R2 but not purged: {e}", file=sys.stderr)
        return 1
    m = load_manifest(sid)
    if m.get("logs", {}).get(sha, {}).pop("url", None):
        save_manifest(sid, m)
    print(f"unpublished {url}")
    if any(c.get("log_sha256") == sha for c in m.get("commits", [])):
        print("note: a commit still points at this log; rewrite its LLM-Trace line, or `check` will fail")
    return 0


# --------------------------------------------------------------------------- commands

def process(transcript: Path, redact: Redactor, status: str, live: bool, current: bool) -> dict:
    """live: the last turn may be unfinished (Langfuse waits for it). current: the session is
    the one running now, so @ is its working copy."""
    sid, m, entries = sync_session(transcript, redact, status)
    if has_jj():
        link_commits(sid, m, current)
    finalize_logs(sid, m)
    render_summary(sid, m, entries, redact.string(str(REPO)))
    write_index()
    try:
        export_langfuse(sid, entries, m, live)
    except OSError as e:  # Langfuse down: those turns are retried next time
        log(f"langfuse export deferred for {sid}: {e}")
    return m


def cmd_hook() -> None:
    try:
        payload = json.load(sys.stdin)
        status = "ended" if payload.get("hook_event_name") == "SessionEnd" else "open"
        process(Path(payload["transcript_path"]), Redactor(), status, live=False, current=True)
    except Exception:
        log(traceback.format_exc())


def cmd_sync(args: list[str]) -> None:
    src = claude_project_dir()
    paths = sorted(src.glob("*.jsonl")) if args in ([], ["--all"]) else [src / f"{a}.jsonl" for a in args]
    redact = Redactor()
    for p in paths:
        live = time.time() - p.stat().st_mtime < LIVE_SECONDS
        old_status = load_manifest(p.stem).get("status")
        m = process(p, redact, "open" if live else (old_status or "ended"), live, current=live)
        s = m["stats"]
        print(f"{m['session_id']}  {s['turns']} turns  {s['tool_calls']} tools  log sha256:{m['log']['sha256'][:12]}… "
              f"{m['log']['bytes']:,} B  commits: {len(m['commits'])}{'  (live)' if live else ''}")


def cmd_commit(args: list[str]) -> int:
    """Finish @ with a message whose trailers match the manifest in its tree, then start a new change."""
    if not args or len(args) % 2 or any(a != "-m" for a in args[::2]) or not args[1].strip():
        print("usage: sync.py commit -m SUMMARY [-m PARAGRAPH ...]", file=sys.stderr)
        return 2
    message = "\n\n".join(a.strip() for a in args[1::2] if a.strip())
    # Describe first: the sync then stamps the trailer onto this message and writes a manifest
    # that lists @ under its real summary, before `jj new` freezes both into the commit.
    if jj("describe", "-r", "@", "-m", message).returncode:
        print("jj describe failed", file=sys.stderr)
        return 1
    cmd_sync([])
    at = jj_commits("@")[0]
    if jj("new").returncode:
        print("jj new failed", file=sys.stderr)
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
        logs = m.get("logs", {})
        referenced = {m["log"]["sha256"]} | {s["log"]["sha256"] for s in m.get("subagents", [])}
        referenced |= {c["log_sha256"] for c in m.get("commits", []) if c.get("log_sha256")}
        for sha in sorted(referenced - logs.keys()):
            errors.append(f"{sid}: log {sha[:12]} is referenced but missing from logs")
        for sha, info in logs.items():
            url = info.get("url")
            if url and url != log_url(sid, sha):
                errors.append(f"{sid}: URL of log {sha[:12]} does not match its sha256: {url}")
            elif url and remote and not remote_matches(url, sha):
                errors.append(f"{sid}: CDN does not serve log {sha[:12]} at {url}")
            data = load_log(sid, sha)
            if data is None:
                if not url:
                    errors.append(f"{sid}: log {sha[:12]} is neither stored locally nor uploaded")
                continue
            if hashlib.sha256(data).hexdigest() != sha:
                errors.append(f"{sid}: log {sha[:12]} content does not match its name")
            if leaks := redact.leaks(data.decode(errors="replace")):
                errors.append(f"{sid}: unredacted {leaks} in log {sha[:12]}")
        if not summary_path(sid).exists():
            errors.append(f"{sid}: summary.md is missing (run: python3 llm-dlc/tools/sync.py sync {sid})")
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
                elif sha not in manifests[sid].get("logs", {}):
                    errors.append(f"{where}: points at log {sha[:12]} that the manifest does not list")
                else:
                    # The manifest committed in the same tree should name the same log.
                    for path in (manifest_path(sid).relative_to(REPO), *(f"{d}/{sid}/manifest.json" for d in LEGACY_TRACES)):
                        if (r := jj("file", "show", "-r", c["commit_id"], str(path))).returncode == 0:
                            break
                    tree_sha = json.loads(r.stdout).get("log", {}).get("sha256") if r.returncode == 0 else None
                    if tree_sha != sha:
                        notes.append(f"{where}: trailer log {sha[:12]} != manifest-in-tree log "
                                     f"{(tree_sha or 'none')[:12]} (committed without trace-commit)")
    for n in notes:
        print("note ", n)
    for e in errors:
        print("ERROR", e)
    if INDEX.exists() and {r["session_id"] for r in json.loads(INDEX.read_text())["sessions"]} != set(manifests):
        errors.append("llm-dlc/index.json does not list exactly the sessions in llm-dlc/traces (run sync)")
    print(f"{len(manifests)} session(s), {len(errors)} error(s), {len(notes)} note(s)")
    return 1 if errors else 0


def cmd_init() -> None:
    jj("config", "set", "--repo", "snapshot.max-new-file-size", "100MiB")
    # `jj trace-push [ARGS]` from anywhere in the workspace.
    jj("config", "set", "--repo", "aliases.trace-push", json.dumps(
        ["util", "exec", "--", "bash", "-c",
         'exec python3 "$JJ_WORKSPACE_ROOT/llm-dlc/tools/sync.py" push "$@"', "--"]))
    jj("config", "set", "--repo", "aliases.trace-commit", json.dumps(
        ["util", "exec", "--", "bash", "-c",
         'exec python3 "$JJ_WORKSPACE_ROOT/llm-dlc/tools/sync.py" commit "$@"', "--"]))
    print("jj repo config set: snapshot.max-new-file-size=100MiB, aliases trace-commit, trace-push")
    r = subprocess.run([shutil.which("npm") or "npm", "ci", "--no-fund", "--no-audit"], cwd=CDN_DIR)
    print("llm-dlc/infra/cdn: pinned wrangler installed" if r.returncode == 0 else "llm-dlc/infra/cdn: npm ci failed")


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
    elif cmd == "unpublish":
        return cmd_unpublish(args)
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

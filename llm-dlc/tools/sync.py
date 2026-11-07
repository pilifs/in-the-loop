#!/usr/bin/env python3
"""Publish Claude Code session traces for this repo.

Layout (llm-dlc/specification.md has the full spec, llm-dlc/README.md the procedure):

  llm-dlc/index.json                                 checked in: one row per session, for lookups
  llm-dlc/traces/README.md                           checked in: every session added up (llm-dlc/traces-readme-template.md)
  llm-dlc/traces/<session-id>/manifest.json          checked in: stats, log pointer, commits
  llm-dlc/traces/<session-id>/summary.md             checked in: readable summary (llm-dlc/summary-template.md)
  llm-dlc/traces/<session-id>/metrics.json           checked in: per-call tables for charts (metrics.py)
  llm-dlc/traces/<session-id>/runs/<record>.md       checked in: a feature-loop.sh run of the session, redacted
  llm-dlc/traces/metrics.json                        checked in: those tables added up over all sessions
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
  sync.py hook                  Claude Code Stop/SessionEnd hook: Langfuse only, leaves the repo alone
  sync.py hook-commit           Claude Code PostToolUse hook: traces a plain `jj commit` or `git commit`
  sync.py sync [--all | ID...] [--full]
                                snapshot sessions of this repo from ~/.claude/projects: those named, or
                                else those whose transcript, commits, note or files changed since they
                                were last synced (--all: every one); only what a transcript gained since
                                the last sync is redacted, --full redacts it all and trusts no cache;
                                in the default workspace, also publishes the loops' run records (runs/)
  sync.py commit -m MSG [-m ..] finish @ with trailers matching its manifest (alias: jj trace-commit);
                                each -m is one paragraph, as in git; then runs `check` on the result,
                                counting its notes, and fails if it finds an error
  sync.py upload                upload logs that commits point at to the CDN, verify, record URLs
  sync.py push [JJ PUSH ARGS]   record outstanding traces in a last commit, upload, check, then `jj git push`,
                                moving any --bookmark to it, once the revision to push is shown to hold
                                exactly the checked files and uploaded logs; leaves @ empty (alias: jj trace-push)
  sync.py check [--remote] [--full]
                                verify hashes, trailers and redaction (--remote: re-download uploads);
                                a log already scanned under these rules is not scanned again, --full
                                scans every one (LLM_TRACES_FULL=1 does that for sync, check and push)
  sync.py scan [--all | ID...] [--full]
                                preview a publish: what the redactor changed and what it left to judge;
                                a session named by ID is scanned whatever its age. Like review and
                                stamp, it redacts only what a transcript gained since its last sync and
                                does not rescan what check scanned; --full does all of it again
  sync.py unpublish SID SHA [--reason TEXT]
                                delete one log from R2 and purge it from the CDN cache (for leaks);
                                with a reason, record the log as withdrawn in the manifest
  sync.py review [--full]       list what `check` would flag, masked, with an id for each finding
  sync.py review show ID        where one finding occurs, masked
  sync.py review accept ID... --reason TEXT
                                record findings as false positives; a person at a terminal only
  sync.py allow                 the allow list: false positives by value, approved or proposed
  sync.py allow propose ID... --reason TEXT
                                propose open warn findings for the allow list (an agent may)
  sync.py allow approve [ID...] approve proposals, all or those named; a person at a terminal only;
                               commits the decision (--no-commit leaves it in @)
  sync.py allow add VALUE --kind KIND --reason TEXT [--no-commit]
                                allow a value before it is found; a person at a terminal only
  sync.py allow drop ID...      remove entries, proposed or approved
  sync.py stamp [--full]        after a change to redaction_rules.py: rescan everything, then
                                record the rules as applied, so older files aren't scanned again;
                                open warnings become allow-list proposals, open errors refuse it
  sync.py stamp --equivalent    keep the last stamp's date for rules that give the same results as
                                the stamped ones at @- on every transcript, log and published file
  sync.py init                  per-clone jj config (file size limit, trace-push alias)
  sync.py perf [N] [COMMAND]    where the last N commands' time went: phases, bytes, cache hits,
                                subprocesses, network requests (LLM_TRACES_PERF=1 prints each as it ends)
  sync.py langfuse SID[:live]... | --all | --pending
                                send one or more sessions' finished turns to Langfuse by hand (commit and sync never do;
                                the Stop hook does at the end of each turn); --pending lists the sessions
                                with turns to send, --all sends them (tools/langfuse-loop.sh waits for more)

Standard library only. The hook never fails a session; errors go to
~/.local/state/llm-traces/hook.log.
"""
from __future__ import annotations

import base64
import contextlib
import gzip
import hashlib
import hmac
import json
import os
import re
import shutil
import signal
import socket
import string
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import metrics  # llm-dlc/tools/metrics.py
import redaction_rules  # llm-dlc/tools/redaction_rules.py
import redactor  # llm-dlc/tools/redactor.py: what decides a cached result
from measure import perf  # llm-dlc/tools/measure.py
from redactor import LocalCache, _mask, atomic_write, decoded, decompress, finding_id, prefix_digests, sha256
from redaction_rules import NEVER_REVIEWED, REDACTION_POLICY, REVIEW_PATTERNS, older_than_stamp

REPO = Path(__file__).resolve().parents[2]
CHANGES = REPO / "llm-dlc"
TRACES = CHANGES / "traces"
# Where older commits keep their manifests: before the changes/ layout, then before llm-dlc/.
LEGACY_TRACES = ("traces", "changes/traces")
INDEX = CHANGES / "index.json"
CHANGES_README = CHANGES / "README.md"
SUMMARY_TEMPLATE = CHANGES / "summary-template.md"
SESSION_NOTES = CHANGES / "session-notes"
LOOP_SUMMARIES = CHANGES / "loop-summaries"  # feature-loop.sh's run records: gitignored, published redacted (runs/)
TRACES_README = TRACES / "README.md"
TRACES_README_TEMPLATE = CHANGES / "traces-readme-template.md"
METRICS_ROLLUP = TRACES / "metrics.json"
PRICING = CHANGES / "pricing.json"
INDEX_SCHEMA = "llm-trace-index/v1"
LANGFUSE_ENV = CHANGES / "infra" / "langfuse" / ".env"
STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "llm-traces"
EXTRA_REDACTIONS = Path.home() / ".config" / "llm-traces" / "redact.txt"
# Cloudflare API token with Zone:Read and Cache Purge on the CDN zone; only `unpublish` uses it.
PURGE_TOKEN = Path.home() / ".config" / "llm-traces" / "cloudflare-token"
# An R2 API token for the llm-traces bucket (Object Read & Write): account_id=, access_key_id= and
# secret_access_key= lines. With it, puts and deletes go to R2's S3 API (R2Client); without it, wrangler.
R2_CREDENTIALS = Path.home() / ".config" / "llm-traces" / "r2-credentials"
SCHEMA = "llm-trace-manifest/v1"
# Wrangler keeps its OAuth tokens here; the spec forbids printing them, redaction removes them anyway.
WRANGLER_CONFIGS = (Path.home() / ".config" / ".wrangler" / "config" / "default.toml",
                    Path.home() / ".wrangler" / "config" / "default.toml")
# Published logs (SHA-256 prefixes) whose findings a person reviewed and left up, so `check` does
# not raise them again. Listed by hash, not by policy: when a new policy flags other published
# logs, nobody has reviewed those yet, and they should warn. See the specification's history note.
ACCEPTED_LOGS = frozenset({
    "2315687ce7e9", "2ed48e0ccf0e", "3f9d33960b46", "4e5d02bfeb4c", "5026337d0f66", "5ec7a7c2be3b", "7fe45409baf7",
    "9aa1dc1182d6", "9b6989b99898", "ad2f8907be5d", "c57cac191c00", "d0d9da508c7a", "dbfac310a6e0",
})
# False positives a person has reviewed. An entry covers one kind and one exact value, so it survives
# new log snapshots and a different value still warns.
REVIEWED = CHANGES / "reviewed-findings.json"
REVIEWED_SCHEMA = "llm-trace-reviewed/v1"
CONFIRMATION = "false positive"
# The allow list: false positives named by their value, so that a person can read the list and add
# to it without a scan. An agent proposes an entry by finding id, and the value stays out of the
# file until a person approves it at a terminal. Only kinds the redactor leaves in the logs can be
# listed: a value it removes would be published by the list itself.
ALLOWLIST = CHANGES / "allowlist.json"
ALLOWLIST_SCHEMA = "llm-trace-allowlist/v1"
ALLOWABLE_KINDS = frozenset(kind for kind, _, _ in REVIEW_PATTERNS)
# Real values of the findings the last scan saw, by id, so that proposing and approving need no
# rescan. Local to this machine and never printed to an agent.
FINDINGS_CACHE = STATE / "finding-values.json"
TRAILER = "LLM-Trace"
TRAILER_RE =re.compile(rf"^{TRAILER}: (\S+)(?: sha256:([0-9a-f]{{64}}))?\s*$", re.M)
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
UPLOADS = STATE / "uploads.json"  # the upload record (UploadRecord)
UPLOAD_JOBS = 4                # logs a push handles at once (LLM_TRACES_UPLOAD_JOBS)
PUT_JOBS = 1                   # of them, wrangler puts at once (LLM_TRACES_PUT_JOBS); see upload_jobs
PERF_LOG = STATE / "perf.jsonl"  # one record per command: where its time went (`sync.py perf`)
PERF_LOG_LINES = 2000          # kept when the file is trimmed
# Snapshots are named by their uncompressed content, so the level changes only the .gz bytes of
# new snapshots, never an identifier, and stored ones are never rewritten. On a 79 MB log (Nov 3
# 2026): level 9, Python's default, 1.66 s and 16.9% of the size; 6, 1.25 s and 17.0%; 3, 0.49 s and
# 20.2%; 1, 0.42 s and 21.9%. Decompression takes 0.2 s at any level.
GZIP_LEVEL = 6


def format_perf(record: dict) -> str:
    lines = [f"{record['command']} at {record['at']}: {record['wall']:.1f} s wall, {record['cpu']:.1f} s CPU, "
             f"{record['child_cpu']:.1f} s in subprocesses"]
    for path, p in sorted(record["phases"].items(), key=lambda kv: -kv[1]["wall"]):
        lines.append(f"  {p['wall']:8.2f} s wall {p['cpu']:8.2f} s cpu {p['child_cpu']:7.2f} s sub  ×{p['calls']:<4} {path}")
    for key, n in record["counters"].items():
        lines.append(f"  {n:>14,} {key}" if isinstance(n, int) else f"  {n:>14,.3f} {key}")
    return "\n".join(lines)


def save_perf(command: str) -> dict:
    """Append this command's record to PERF_LOG, trimmed to its last PERF_LOG_LINES lines now and then."""
    record = perf.record(command)
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        with open(PERF_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")
        if PERF_LOG.stat().st_size > 4 * 1024 * 1024:
            kept = PERF_LOG.read_text().splitlines()[-PERF_LOG_LINES:]
            atomic_write(PERF_LOG, "\n".join(kept) + "\n")
    except OSError:
        pass  # measurements only
    if os.environ.get("LLM_TRACES_PERF"):
        print(format_perf(record), file=sys.stderr)
    return record


def cmd_perf(args: list[str]) -> int:
    """The last N command records (default 5), or those of one command: `perf [N] [COMMAND]`."""
    n = int(args[0]) if args and args[0].isdigit() else 5
    command = next((a for a in args if not a.isdigit()), None)
    try:
        records = [json.loads(line) for line in PERF_LOG.read_text().splitlines() if line.strip()]
    except (OSError, ValueError):
        records = []
    records = [r for r in records if command in (None, r["command"])][-n:]
    print("\n\n".join(format_perf(r) for r in records) or "no measurements yet")
    return 0


def _cmd(*args: str) -> str:
    perf.count(f"subprocess {Path(args[0]).name}")
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


def read_r2_credentials(path: Path | None = None) -> dict[str, str]:
    """The key=value lines of the R2 token file (R2_CREDENTIALS), keys lowercased; {} without it."""
    out = {}
    path = path or R2_CREDENTIALS
    if path.exists():
        for line in path.read_text().splitlines():
            k, sep, v = line.strip().partition("=")
            if sep and not k.startswith("#"):
                out[k.strip().lower()] = v.strip().strip('"')
    return out


def _hostnames() -> set[str]:
    names = {socket.gethostname()}
    try:
        names.add(Path("/etc/hostname").read_text().strip())
    except OSError:
        pass
    names = {n.split(".")[0] for n in names if n}
    return {n for n in names if len(n) >= 4 and n.lower() not in ("localhost",)}


def personal_literals() -> tuple[list[tuple[str, str, int, str]], str]:
    """(literal, replacement, re flags, kind) for this machine: home path, hostname, emails,
    account identifiers, and the secrets of the local tools. Emails match case-insensitively.
    GitHub noreply addresses are public by design and are kept."""
    pairs: list[tuple[str, str, int, str]] = []
    home, user = str(Path.home()), os.environ.get("USER") or Path.home().name
    pairs += [(home, "~", 0, "home"), (re.sub(r"[^A-Za-z0-9]", "-", home), "-home-user", 0, "home")]
    pairs += [(h, "host", re.I, "hostname") for h in _hostnames()]
    emails = {_cmd("git", "config", "--get", "user.email"), _cmd(JJ, "config", "get", "user.email")}
    try:
        config = json.loads((Path.home() / ".claude.json").read_text())
        account = config.get("oauthAccount") or {}
        emails.add(account.get("emailAddress") or "")
        ids = (account.get("accountUuid"), account.get("organizationUuid"), config.get("userID"))
        pairs += [(v, "[REDACTED:account-id]", 0, "account-id") for v in ids if isinstance(v, str) and len(v) >= 12]
    except (OSError, ValueError):
        pass
    emails = {e.lower() for e in emails if e and not e.lower().endswith("@users.noreply.github.com")}
    pairs += [(e, "user@example.com", re.I, "email") for e in emails]
    pairs += [(e.split("@")[0], "user", re.I, "email") for e in emails if len(e.split("@")[0]) >= 4]
    env = read_env(LANGFUSE_ENV)
    # Values of secret-looking keys, except bare URLs without credentials (NEXTAUTH_URL).
    secrets = [v for k, v in env.items() if re.search(r"SECRET|PASSWORD|KEY|SALT|AUTH|DATABASE_URL", k)
               and len(v) >= 12 and not re.fullmatch(r"[a-z][a-z0-9+.\-]*://[^@]*", v)]
    pk, sk = env.get("LANGFUSE_INIT_PROJECT_PUBLIC_KEY"), env.get("LANGFUSE_INIT_PROJECT_SECRET_KEY")
    if pk and sk:  # the Basic auth header sync.py sends to Langfuse
        secrets.append(base64.b64encode(f"{pk}:{sk}".encode()).decode())
    if PURGE_TOKEN.exists():
        secrets.append(PURGE_TOKEN.read_text().strip())
    # Both keys; the account id is not a secret (it is in every R2 endpoint) and is left alone.
    secrets += [v for k, v in read_r2_credentials().items() if k in ("access_key_id", "secret_access_key")]
    for cfg in WRANGLER_CONFIGS:
        if cfg.exists():
            secrets += re.findall(r'^(?:oauth_token|refresh_token)\s*=\s*"([^"]+)"', cfg.read_text(), re.M)
    pairs += [(v, "[REDACTED:local-secret]", 0, "local-secret") for v in secrets if len(v) >= 12]
    if EXTRA_REDACTIONS.exists():
        for line in EXTRA_REDACTIONS.read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                lit, _, rep = line.partition("=>")
                pairs.append((lit.strip(), rep.strip() or "[REDACTED]", 0, "redact.txt literal"))
    pairs.sort(key=lambda p: -len(p[0]))
    return pairs, user


def load_reviewed() -> dict[str, dict]:
    return json.loads(REVIEWED.read_text())["findings"] if REVIEWED.exists() else {}


def load_allowlist() -> dict[str, dict]:
    return json.loads(ALLOWLIST.read_text())["entries"] if ALLOWLIST.exists() else {}


def allowed_ids() -> dict[str, dict]:
    """Approved entries of the allow list, by finding id, as load_reviewed gives them."""
    return {fid: e for fid, e in load_allowlist().items() if e.get("status") == "approved"}


class Redactor(redactor.Redactor):
    """The rules with this machine's literals, less the false positives a person has reviewed."""

    def __init__(self) -> None:
        super().__init__(personal_literals(), load_reviewed() | allowed_ids())


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
    """Content-addressed snapshot: named by the sha256 of the uncompressed bytes, never rewritten.
    Its sizes come from the bytes in hand; `check` is what proves a stored file holds them."""
    with perf.phase("store log"):
        sha = hashlib.sha256(data).hexdigest()
        path = log_path(sid, sha)
        if not path.exists():
            with perf.phase("compress"):
                gz = gzip.compress(data, compresslevel=GZIP_LEVEL, mtime=0)  # mtime=0: same input, same .gz bytes
            atomic_write(path, gz)
            perf.count("log snapshots written")
            perf.count("log bytes compressed", len(data))
        return {"sha256": sha, "bytes": len(data), "lines": data.count(b"\n"), "gzip_bytes": path.stat().st_size,
                "path": str(path.relative_to(REPO))}


def log_info(sid: str, sha: str) -> dict:
    """Sizes of a stored log: its content in bytes and lines, and the gzip file in bytes."""
    data = load_log(sid, sha)
    return {"bytes": len(data), "lines": data.count(b"\n"), "gzip_bytes": log_path(sid, sha).stat().st_size}


def load_log(sid: str, sha: str) -> bytes | None:
    path = log_path(sid, sha)
    if not path.exists():
        return None
    with perf.phase("decompress"):
        data = gzip.decompress(path.read_bytes())
    perf.count("log loads")
    perf.count("log bytes decompressed", len(data))
    return data


def write_if_changed(path: Path, text: str) -> bool:
    """Write a generated file only when its content differs, atomically. Whether it was written."""
    try:
        if path.read_text() == text:
            perf.count("generated files unchanged")
            return False
    except OSError:
        pass
    atomic_write(path, text)
    perf.count("generated files written")
    return True


# --------------------------------------------------------------------------- local caches
#
# Results kept between commands, on this machine only, so that bytes already redacted or scanned
# are not processed again. An entry is used only when its exact inputs are shown to be the same:
# the content, by its SHA-256, and everything else that decides the result, by a fingerprint.
# Redacted logs, scans and verified snapshots are decided by redactor.py and the rules alone, and
# their fingerprint (Redactor.fingerprint) covers those two files, the Python version and this
# machine's redaction literals: an edit to the rest of sync.py keeps them. What also depends on the
# rest of sync.py or on metrics.py (a session's synced state, check's metrics entries, the Stop
# hook's cursor) adds tools_digest(). Anything else, a missing or damaged file included, means the
# work is done again. `--full` (or LLM_TRACES_FULL=1) trusts no cached result and records fresh
# ones. The files hold digests, lengths, kinds, finding ids, masked values and counts, never a
# finding's value or any log content.

TRANSCRIPT_CACHE = STATE / "transcript-cache.json"
SCAN_CACHE = STATE / "scan-cache.json"
CHECK_CACHE = STATE / "check-cache.json"
SYNC_CACHE = STATE / "sync-cache.json"


def full_audit(args: list[str]) -> bool:
    return "--full" in args or bool(os.environ.get("LLM_TRACES_FULL"))


_tools_digest: str | None = None


def tools_digest() -> str:
    """SHA-256 of the source of sync.py and metrics.py, read once: for results that depend on more
    than the redactor and the rules (Redactor.fingerprint)."""
    global _tools_digest
    if _tools_digest is None:
        h = hashlib.sha256()
        for source in (Path(__file__), Path(metrics.__file__)):
            h.update(source.read_bytes() + b"\0")
        _tools_digest = h.hexdigest()
    return _tools_digest


def redacted_incrementally(raw: bytes, sid: str, key: str, redact: Redactor, cache: LocalCache | None) -> bytes:
    """redactor.redacted_incrementally, reusing session sid's stored logs."""
    return redactor.redacted_incrementally(raw, key, redact, cache, lambda sha: load_log(sid, sha))


class ScanCache(redactor.ScanCache):
    def __init__(self, redact: Redactor, path: Path | None = ..., trusted: bool = True) -> None:
        super().__init__(redact, SCAN_CACHE if path is ... else path, trusted)  # read now: tests point it elsewhere


class CheckCache(redactor.CheckCache):
    def __init__(self, redact: Redactor, path: Path | None = ..., trusted: bool = True) -> None:
        super().__init__(redact, CHECK_CACHE if path is ... else path, trusted)


# --------------------------------------------------------------------------- manifest

def manifest_path(sid: str) -> Path:
    return session_dir(sid) / "manifest.json"


def load_manifest(sid: str) -> dict:
    path = manifest_path(sid)
    return json.loads(path.read_text()) if path.exists() else {}


def save_manifest(sid: str, m: dict) -> None:
    write_if_changed(manifest_path(sid), json.dumps(m, indent=2, ensure_ascii=False) + "\n")


def all_manifests() -> dict[str, dict]:
    return {p.parent.name: json.loads(p.read_text()) for p in sorted(TRACES.glob("*/manifest.json"))}


def redacted(transcript: Path, sid: str, known: str | None, redact: Redactor, key: str,
             cache: LocalCache | None = None) -> bytes:
    """A transcript's log. One older than the rules' stamp was redacted by them when `known`, its
    last log, was stored. Otherwise only what was appended since the cache's entry under `key`."""
    if known and older_than_stamp(transcript) and (data := load_log(sid, known)) is not None:
        perf.count("transcripts not redacted again (older than the stamp)")
        return data
    return redacted_incrementally(transcript.read_bytes(), sid, key, redact, cache)


def transcript_cache(redact: Redactor, full: bool = False) -> LocalCache:
    return LocalCache(TRANSCRIPT_CACHE, redact.fingerprint(), trusted=not (full or full_audit([])))


def sync_cache(redact: Redactor, trusted: bool = True) -> LocalCache:
    """Each session's state (session_state) as it was right after it was last synced. The
    fingerprint covers what process() reads besides the session's own files and commits: the
    rules and redactor (in redact's), the rest of the tools, the templates, prices and reviewed
    findings, and the repo."""
    h = hashlib.sha256(f"{redact.fingerprint()}\0{tools_digest()}\0{REPO}\0{repo_web_url()}\0{has_jj()}\0".encode())
    for source in (SUMMARY_TEMPLATE, PRICING, REVIEWED, ALLOWLIST):
        h.update((source.read_bytes() if source.exists() else b"-") + b"\0")
    return LocalCache(SYNC_CACHE, h.hexdigest(), trusted=trusted and not full_audit([]))


INDEX_TEMPLATE = ('change_id ++ "\\t" ++ commit_id ++ "\\t" ++ immutable ++ "\\t" ++ empty ++ "\\t" ++ '
                  'current_working_copy ++ "\\t" ++ author.timestamp().utc().format("%s") ++ "\\t" ++ '
                  'json(description) ++ "\\n"')


def commit_index() -> list[dict] | None:
    """In one jj call, every change link_commits could stamp or list for any session: those that
    carry a session trailer and the mutable ancestors of @. None without jj, or if the call fails."""
    if not has_jj():
        return None
    r = jj("log", "--no-graph", "-r", f'description(substring:"{TRAILER}: ") | (mutable() & ::@)', "-T", INDEX_TEMPLATE)
    if r.returncode:
        return None
    out = []
    for line in r.stdout.splitlines():
        cid, commit, immutable, empty, at, when, desc = line.split("\t", 6)
        out.append({"change_id": cid, "commit_id": commit, "immutable": immutable == "true", "empty": empty == "true",
                    "at": at == "true", "author": int(when), "description": json.loads(desc)})
    return out


MADE_MARGIN = 120  # seconds around a session's span in which a change may count as made by it


def session_state(transcript: Path, status: str, current: bool, index: list[dict] | None) -> dict:
    """Everything process() reads or writes for one session, read cheaply: the size, time and inode
    of its transcripts (taken before they are read, so a later write shows), the commits that
    link_commits stamps or lists (with a margin around the session's span for the ones it may have
    made), its note, and the bytes of the files it wrote. A session whose state is the one recorded
    right after it was last processed would be processed into the same files and descriptions."""
    sid = transcript.stem

    def stat(p: Path):
        try:
            st = p.stat()
            return [st.st_size, st.st_mtime_ns, st.st_ino]
        except OSError:
            return None

    def digest(p: Path):
        try:
            return sha256(p.read_bytes())
        except OSError:
            return None

    subdir = transcript.parent / sid / "subagents"
    sources = [[p.name, stat(p)] for p in [transcript, *(sorted(subdir.glob("*.jsonl")) if subdir.is_dir() else [])]]
    files = [[p.name, digest(p)] for p in (manifest_path(sid), summary_path(sid), metrics_path(sid), notes_path(sid),
                                           *run_copies(sid))]
    logs = sorted(p.name for p in (session_dir(sid) / "logs").glob("*.jsonl.gz"))
    commits = None
    if index is not None:
        m, span = load_manifest(sid), None
        if m.get("started") and m.get("ended"):
            span = [datetime.fromisoformat(m[k].replace("Z", "+00:00")).timestamp() for k in ("started", "ended")]
        trailer = f"{TRAILER}: {sid}"
        commits = sorted(([c["change_id"], c["immutable"], c["commit_id"] if c["immutable"] else None, c["empty"],
                           c["at"], c["description"]] for c in index
                          if trailer in c["description"] or (current and c["at"])
                          or (span and not c["immutable"] and span[0] - MADE_MARGIN <= c["author"] <= span[1] + MADE_MARGIN)),
                         key=json.dumps)
    return {"status": status, "current": current, "sources": sources, "files": files, "logs": logs, "commits": commits}


def running_session() -> str | None:
    """The session that runs this command, as Claude Code tells its tools."""
    return os.environ.get("CLAUDE_CODE_SESSION_ID") or None


def sync_session(transcript: Path, redact: Redactor, status: str,
                 cache: LocalCache | None = None) -> tuple[str, dict, list[dict], list[tuple]]:
    """Snapshot one session's log (and subagent logs) and rewrite its manifest. Returns the session
    id, the manifest, the log's entries, and (agent, entries) of each subagent log."""
    sid = transcript.stem
    old = load_manifest(sid)
    data = redacted(transcript, sid, old.get("log", {}).get("sha256"), redact, sid, cache)
    entries = read_jsonl(data)
    log = store_log(sid, data)
    known_subagents = {s["agent"]: s["log"]["sha256"] for s in old.get("subagents", [])}
    subagents, subagent_entries = [], []
    subdir = transcript.parent / sid / "subagents"
    for sub in sorted(subdir.glob("*.jsonl")) if subdir.is_dir() else []:
        sub_data = redacted(sub, sid, known_subagents.get(sub.stem), redact, f"{sid}/{sub.stem}", cache)
        sub_entries = read_jsonl(sub_data)
        s = summarize(sub_entries, redact.string(str(REPO)))
        subagents.append({"agent": sub.stem, "models": s["models"], "stats": s["stats"],
                          "log": store_log(sid, sub_data)})
        subagent_entries.append((sub.stem, sub_entries))
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
    return sid, m, entries, subagent_entries


# --------------------------------------------------------------------------- jj

def jj(*args: str) -> subprocess.CompletedProcess:
    # Snapshotting must not skip files; the default limit for new files is 1 MiB.
    started = time.perf_counter()
    try:
        return subprocess.run([JJ, "--quiet", "--config", "snapshot.max-new-file-size=100MiB", *args],
                              capture_output=True, text=True, timeout=60, cwd=REPO)
    finally:
        perf.count(f"subprocess jj {args[0]}")
        perf.count(f"subprocess jj {args[0]} seconds", time.perf_counter() - started)


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


def link_commits(sid: str, m: dict, current: bool, publishing: bool = False) -> None:
    """Stamp this session's trailer on the mutable changes it made, then record every
    change that carries its trailer (mutable or not) in the manifest.

    A session "made" the mutable ancestors of @ created while it ran, plus @ itself if the
    session is the one running now (`current`). @ is re-stamped with the latest log on every
    sync, together with the manifest in its tree, so the two always agree. Other changes are
    stamped once, if they have no trailer for this session yet, and then left alone;
    immutable ones are never touched. When publishing, every change below @ is about to be
    pushed unchanged, so its git SHA is recorded now rather than by a later commit."""
    at = jj_commits("@")[0]["change_id"]
    if m.get("started") and m.get("ended"):
        made = (f'mutable() & ::@ & author_date(after:"{m["started"]}") & author_date(before:"{m["ended"]}")'
                f' & ~(empty() & description(exact:""))')
        if current:
            made = f"({made}) | @"
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
                        "commit_id": c["commit_id"] if c["immutable"] or (publishing and c["change_id"] != at) else None,
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
        if None in (entry["bytes"], entry["lines"], entry["gzip_bytes"]) and log_path(sid, sha).exists():
            entry.update(log_info(sid, sha))  # a log never changes: its name is its hash
        logs[sha] = entry
    m["logs"] = logs
    for path in (session_dir(sid) / "logs").glob("*.jsonl.gz"):
        if path.name.split(".")[0] not in keep:
            path.unlink()
    save_manifest(sid, m)


# --------------------------------------------------------------------------- summary and index

def notes_path(sid: str) -> Path:
    """An optional hand-written note on a session, for what its log and commits cannot say."""
    return SESSION_NOTES / f"{sid}.md"


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
    """Write summary.md from the template. It is derived from the redacted log, the manifest and
    the session's optional hand-written note, which `check` scans for secrets, so it is safe to
    publish and can be rebuilt from a published log and this repo."""
    s, u = m["stats"], m["stats"]["usage"]
    repo = repo_web_url()
    changes = []
    for c in m.get("commits", []):
        ref = f"[`{c['commit_id'][:12]}`]({repo}/commit/{c['commit_id']})" if c.get("commit_id") and repo \
            else f"change `{c['change_id'][:12]}`"
        if not c.get("summary"):  # the working copy before its first commit message
            changes.append(f"### (in progress)\n\n{ref}, not yet described")
            continue
        withdrawn = c.get("log_sha256") and (m.get("logs", {}).get(c["log_sha256"]) or {}).get("withdrawn")
        log_ref = (f" · log `{c['log_sha256'][:12]}` withdrawn: {_escape_html(withdrawn)}" if withdrawn
                   else f" · [log `{c['log_sha256'][:12]}`]({log_url(sid, c['log_sha256'])})" if c.get("log_sha256") else "")
        changes.append(f"### {_escape_html(c['summary'])}\n\n{ref}{log_ref}"
                       + (f"\n\n{_escape_html(c['body'])}" if c.get("body") else ""))
    turns, n = [], 0
    for turn in turns_of(entries):
        if (md := _turn_md(n + 1, turn, repo_prefix)) is not None:
            n += md.startswith("### ")
            turns.append(md)
    subagents = "".join(f"\n- `{a['agent']}`: {a['stats']['turns']} turns, {a['stats']['tool_calls']} tool calls, "
                        f"[log]({log_url(sid, a['log']['sha256'])})" for a in m.get("subagents", []))
    note = notes_path(sid)
    withdrawn = [f"- `{sha[:12]}`: {_escape_html(info['withdrawn'])}"
                 for sha, info in sorted(m.get("logs", {}).items()) if info.get("withdrawn")]
    notes = ([note.read_text().strip()] if note.exists() else []) + \
            (["**Withdrawn logs**, taken off the CDN after publication:\n\n" + "\n".join(withdrawn)] if withdrawn else [])
    values = {
        "notes": "## Notes\n\n" + "\n\n".join(notes) if notes else "",
        "runs": runs_section(sid),
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
    write_if_changed(summary_path(sid), re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n")


# --------------------------------------------------------------------------- run records
#
# feature-loop.sh keeps a record of each run in llm-dlc/loop-summaries/ (gitignored): its header
# names the session, then come the instruction, a line per commit and how the run ended. The record
# holds local paths, so it is published only as a copy redacted by the transcripts' rules, beside
# the session it names (runs/<record>.md), and linked from that session's summary. A record still
# being written is published as it stands and again as it grows: a run that was killed never writes
# an end line, and would otherwise never be published. Only the default workspace publishes: a
# stream's records are its own workspace's, copied into the default one when the streams are merged.

RUN_HEADER = re.compile(r"^Started (?P<started>[^,\n]+), .*?\bsession (?P<sid>[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})\b",
                        re.M)
RUN_END = re.compile(r"^(?P<how>Ended|Stopped|Interrupted) (?P<when>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)(?P<rest>.*)$", re.M)
RUN_CYCLE = re.compile(r"^- cycle \d+, ", re.M)
RUNS_BEGIN, RUNS_END = "<!-- runs:begin (generated by llm-dlc/tools/sync.py) -->", "<!-- runs:end -->"


def runs_dir(sid: str) -> Path:
    return session_dir(sid) / "runs"


def run_copies(sid: str) -> list[Path]:
    """A session's published run records, oldest first (their names start with the start time)."""
    return sorted(runs_dir(sid).glob("*.md"))


def publishes_runs() -> bool:
    """Whether this checkout publishes run records: the default workspace, or a checkout without jj.
    The default workspace is the one that holds the repository, whose .jj/repo is a directory; in a
    workspace added later it is a file naming that one. Told without running jj, as sync runs none."""
    return not (REPO / ".jj").is_dir() or (REPO / ".jj" / "repo").is_dir()


def run_records() -> list[tuple[Path, str | None]]:
    """Each record feature-loop.sh wrote in LOOP_SUMMARIES, with the session its header names (None if
    it names none). Other files there, such as integration reports, are not runs."""
    out = []
    for path in sorted(LOOP_SUMMARIES.glob("*.md")) if LOOP_SUMMARIES.is_dir() else []:
        text = path.read_text(errors="replace")
        if text.startswith("# Feature loop:"):
            out.append((path, m["sid"] if (m := RUN_HEADER.search(text)) else None))
    return out


def redacted_record(path: Path, redact: Redactor) -> str:
    """A run record as published: every line through the rules that redact the transcripts."""
    return "\n".join(redact.string(line) for line in path.read_text(errors="replace").split("\n"))


def publish_runs(redact: Redactor) -> None:
    """Write the redacted copy of each record whose session has a trace here, if it changed."""
    if not publishes_runs():
        return
    with perf.phase("run records"):
        for path, sid in run_records():
            if sid and manifest_path(sid).exists():
                write_if_changed(runs_dir(sid) / path.name, redacted_record(path, redact))


def run_notes(redact: Redactor | None = None) -> list[str]:
    """For `check`: the records that are not published, or not as they stand now."""
    records = run_records()
    if records and not publishes_runs():
        return [f"{len(records)} run record(s) in {LOOP_SUMMARIES.relative_to(REPO)} are not published here: "
                f"only the default workspace publishes them"]
    notes, redact = [], redact or Redactor()
    for path, sid in records:
        if sid is None:
            notes.append(f"run record {path.name} names no session, so it is not published")
        elif not manifest_path(sid).exists():
            notes.append(f"run record {path.name}: its session {sid} has no trace here, so it is not published")
        elif not (copy := runs_dir(sid) / path.name).exists() or copy.read_text() != redacted_record(path, redact):
            notes.append(f"run record {path.name} has changed since it was last published (the next sync publishes it)")
    return notes


def run_line(copy: Path) -> str:
    """One run in a summary's list, read from the published copy: start, end, cycles, how it ended."""
    text = copy.read_text(errors="replace")
    started = m["started"] if (m := RUN_HEADER.search(text)) else "?"
    cycles = len(RUN_CYCLE.findall(text))
    ends = list(RUN_END.finditer(text))
    if ends:
        end = ends[-1]
        how = f"{end['how']}{end['rest']}".strip()
        span, how = f"{started} to {end['when']}", how if how.endswith(".") else how + "."
    else:
        span, how = f"from {started}", "No end recorded: still running when last published, or stopped without a line."
    return (f"- [{copy.stem}](runs/{copy.name}): {span}, {cycles} cycle{'' if cycles == 1 else 's'} with a commit. "
            + _escape_html(how))


def runs_section(sid: str) -> str:
    """The summary's list of the session's loop runs, between markers so that a summary rendered
    elsewhere can be brought up to date in place (splice_runs); empty for a session with none."""
    if not (copies := run_copies(sid)):
        return ""
    return (f"{RUNS_BEGIN}\n## Loop runs\n\nThe runs of `llm-dlc/tools/feature-loop.sh` this session worked in, "
            "each with its record, redacted: the instruction, a line per commit, and how the run ended.\n\n"
            + "\n".join(run_line(c) for c in copies) + f"\n{RUNS_END}")


def splice_runs(sid: str) -> bool:
    """Bring the list of runs in a session's summary.md up to date without rendering the rest, for a
    session whose transcript is not here to render it from. Whether the summary was written."""
    path, block = summary_path(sid), runs_section(sid)
    if not path.exists():
        return False
    text = path.read_text()
    if RUNS_BEGIN in text and RUNS_END in text:
        start, end = text.index(RUNS_BEGIN), text.index(RUNS_END) + len(RUNS_END)
        text = text[:start] + block + text[end:]
    elif block:
        at = text.find("\n## Changes\n")
        text = text[:at + 1] + block + "\n\n" + text[at + 1:] if at >= 0 else text.rstrip() + "\n\n" + block + "\n"
    else:
        return False
    return write_if_changed(path, text)


INDEX_BEGIN, INDEX_END = "<!-- index:begin (generated by llm-dlc/tools/sync.py) -->", "<!-- index:end -->"


def metrics_path(sid: str) -> Path:
    return session_dir(sid) / "metrics.json"


def session_metrics(sid: str, m: dict, entries: list[dict], redact: Redactor,
                    subagents: list[tuple[str, list[dict]]] | None = None) -> str:
    """metrics.json of a session, from its redacted logs and manifest and from the price list.
    `subagents`: (agent, entries) of the manifest's subagent logs, when the caller has them."""
    if subagents is None:
        subagents = [(s["agent"], read_jsonl(load_log(sid, s["log"]["sha256"]) or b"")) for s in m.get("subagents", [])]
    return metrics.dumps(metrics.session(m, entries, subagents, json.loads(PRICING.read_text()), redact.string))


def render_rollup(manifests: dict[str, dict] | None = None) -> str:
    """llm-dlc/traces/metrics.json: a function of the session metrics files, like the overview."""
    manifests = all_manifests() if manifests is None else manifests
    found = [(m, json.loads(metrics_path(sid).read_text())) for sid, m in manifests.items()
             if m.get("schema") == SCHEMA and metrics_path(sid).exists()]
    found.sort(key=lambda pair: pair[0].get("started") or "")
    return metrics.dumps(metrics.rollup(found, json.loads(PRICING.read_text())))


def metrics_problems(sid: str, m: dict, data, redact: Redactor, checks: CheckCache | None = None,
                     logs: list[str | None] | None = None) -> tuple[list[str], list[str]]:
    """(errors, warnings) for a session's metrics.json. Without the log here, as in a fresh clone,
    the file can only be read. With it, the file must be what the log gives, and its token totals
    must equal the manifest's, which `summarize` counts separately. data may be a function giving
    the log. With `checks`, `logs` is the SHA-256 of the content of the log and of each subagent
    log as stored (None for one not stored): whether the file is what they give is then worked out
    once for each set of inputs."""
    path = metrics_path(sid)
    if not path.exists():
        return [f"{sid}: metrics.json is missing (run: python3 llm-dlc/tools/sync.py sync {sid})"], []
    text = path.read_text()
    doc = json.loads(text)
    errors, warnings = [], []
    if doc.get("schema") != metrics.SCHEMA:
        errors.append(f"{sid}: metrics.json has unknown schema {doc.get('schema')}")
    if data is not None:
        key = same = None
        if checks is not None and logs is not None:
            key = "metrics:" + sha256(json.dumps([tools_digest(), logs, m, text, PRICING.read_text()], sort_keys=True,
                                                 ensure_ascii=False).encode())
            if (entry := checks.get(key)) is not None:
                perf.count("metrics cache hits")
                same = entry["same"]
        if same is None:
            same = text == session_metrics(sid, m, read_jsonl(data() if callable(data) else data), redact)
            if key:
                checks.put(key, {"same": same})
        if not same:
            errors.append(f"{sid}: metrics.json does not match the log and manifest (run sync)")
    usages = [m["stats"]["usage"]] + [s["stats"]["usage"] for s in m.get("subagents", [])]
    pairs = (("input_tokens", "input_tokens"), ("output_tokens", "output_tokens"),
             ("cache_read_tokens", "cache_read_input_tokens"), ("cache_write_tokens", "cache_creation_input_tokens"))
    for ours, theirs in pairs:
        if doc.get("totals", {}).get(ours) != sum(u[theirs] for u in usages):
            errors.append(f"{sid}: {ours} in metrics.json differs from the manifest")
    if unpriced := doc.get("totals", {}).get("unpriced_calls"):
        models = [r["model"] for r in doc.get("by_model", []) if r["unpriced_calls"]]
        warnings.append(f"{sid}: {unpriced} model call(s) count as $0: add {models} to llm-dlc/pricing.json")
    return errors, warnings


def write_index() -> None:
    """llm-dlc/index.json lists every session with the commits it made, so a reader can go from
    a commit or a date to a session without opening every manifest. The same rows are rendered as
    a table in llm-dlc/README.md, between the index markers."""
    rows, manifests = [], all_manifests()
    for sid, m in manifests.items():
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
    write_if_changed(INDEX, json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    if CHANGES_README.exists():
        table = ["| Started | Session | Prompts | Commits | Status |", "|---|---|---|---|---|"]
        for r in reversed(rows):
            title = (r["title"] or r["session_id"]).replace("|", "\\|")
            table.append(f"| {_when(r['started'])} | [{title}]({r['summary']}) | {r['turns']} | "
                         f"{len(r['commits'])} | {r['status']} |")
        readme = CHANGES_README.read_text()
        start, end = readme.find(INDEX_BEGIN), readme.find(INDEX_END)
        if 0 <= start < end:
            write_if_changed(CHANGES_README, readme[:start + len(INDEX_BEGIN)] + "\n" + "\n".join(table) + "\n" + readme[end:])
    write_if_changed(TRACES_README, render_traces_readme(manifests))
    write_if_changed(METRICS_ROLLUP, render_rollup(manifests))


def _table(header: list[str], rows: list[list]) -> str:
    """A Markdown table; a header cell ending in `>` right-aligns its numeric column."""
    names = [h.rstrip(">") for h in header]
    rules = ["---:" if h.endswith(">") else "---" for h in header]
    return "\n".join("| " + " | ".join(str(c) for c in row) + " |" for row in [names, rules, *rows])


def _elapsed(seconds: int | None) -> str:
    if seconds is None:
        return "?"
    minutes = seconds // 60
    days, hours, mins = minutes // 1440, minutes // 60 % 24, minutes % 60
    return f"{days} d {hours} h" if days else f"{hours} h {mins} min" if hours else f"{mins} min"


def _cached_share(u: dict) -> str:
    read = u["input_tokens"] + u["cache_read_input_tokens"] + u["cache_creation_input_tokens"]
    return f"{u['cache_read_input_tokens'] / read:.1%}" if read else "n/a"


def render_traces_readme(manifests: dict[str, dict] | None = None) -> str:
    """llm-dlc/traces/README.md: every session added up. It is a function of the manifests and the
    session notes alone, so a sync rewrites it identically and `check` can tell when it is stale."""
    manifests = {sid: m for sid, m in (all_manifests() if manifests is None else manifests).items()
                 if m.get("schema") == SCHEMA}
    ordered = sorted(manifests.items(), key=lambda kv: kv[1].get("started") or "")
    active = [(sid, m) for sid, m in ordered if m["stats"]["turns"]]
    idle = [sid for sid, m in ordered if not m["stats"]["turns"]]
    repo = repo_web_url()
    short = lambda sid: f"[`{sid[:8]}`]({sid}/summary.md)"
    title = lambda sid, m: (m.get("title") or sid).replace("|", "\\|")

    usage = {k: sum(m["stats"]["usage"][k] for _, m in active) for k in
             ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
    total = lambda key: sum(m["stats"][key] for _, m in active)

    commits: dict[str, dict] = {}  # by change id, in order of first appearance
    for sid, m in active:
        for c in m.get("commits", []):
            if c.get("summary"):  # not the working copy
                entry = commits.setdefault(c["change_id"], {**c, "sessions": []})
                entry["commit_id"] = entry.get("commit_id") or c.get("commit_id")
                entry["sessions"].append((sid, c.get("log_sha256")))
    rows = []
    for n, c in enumerate(commits.values(), 1):
        ref = f"[`{c['commit_id'][:8]}`]({repo}/commit/{c['commit_id']})" if c.get("commit_id") and repo \
            else f"change `{c['change_id'][:8]}`"
        traces = ", ".join(short(sid) + (f" ([log]({log_url(sid, sha)}))" if sha else "") for sid, sha in c["sessions"])
        rows.append([n, ref, _escape_html(c["summary"]).replace("|", "\\|"), traces])

    tools: dict[str, list[int]] = {}
    for _, m in active:
        for name, calls in m.get("tools", {}).items():
            tools.setdefault(name, [0, 0])
            tools[name][0] += calls
            tools[name][1] += 1
    calls = sum(c for c, _ in tools.values())

    logs = {(sid, sha): info for sid, m in active for sha, info in m.get("logs", {}).items()}
    gzip_mb = lambda sizes: f"{sum(sizes) / 1e6:.1f} MB"
    notes = [(sid, notes_path(sid).read_text().strip().split("\n")[0]) for sid in manifests if notes_path(sid).exists()]
    dates = [m[k] for _, m in active for k in ("started", "ended") if m.get(k)]

    values = {
        "glance": "\n".join(f"| {k} | {v} |" for k, v in [
            ("Sessions", f"{len(active)}" + (f", plus {len(idle)} empty" if idle else "")),
            ("Period", f"{_when(min(dates))} to {_when(max(dates))}" if dates else "?"),
            ("Prompts", f"{total('turns'):,}"),
            ("Model calls", f"{total('api_calls'):,}"),
            ("Tool calls", f"{total('tool_calls'):,} ({total('tool_errors'):,} failed)"),
            ("Compactions", f"{total('compactions'):,}"),
            ("Subagents", f"{sum(len(m.get('subagents', [])) for _, m in active):,}"),
            ("Tokens written", f"{usage['output_tokens']:,}"),
            ("Tokens read", f"{usage['input_tokens'] + usage['cache_read_input_tokens'] + usage['cache_creation_input_tokens']:,}"
                            f" ({_cached_share(usage)} from cache)"),
            ("Commits with a trace", f"{len(commits):,}"),
            ("Log snapshots", f"{len(logs):,} ({gzip_mb(i.get('gzip_bytes', 0) for i in logs.values())} gzipped, "
                              f"{sum(1 for i in logs.values() if i.get('url')):,} uploaded)"),
        ]),
        "sessions": _table(
            ["Started", "Session", "Status", "Elapsed", "Models", "Prompts>", "Model calls>", "Tool calls>", "Failed>",
             "Compactions>", "Peak context>", "Commits>"],
            [[_when(m.get("started")), f"[{title(sid, m)}]({sid}/summary.md)", m["status"],
              _elapsed(m.get("duration_seconds")), ", ".join(f"`{x}`" for x in m.get("models", [])) or "?",
              f"{m['stats']['turns']:,}", f"{m['stats']['api_calls']:,}", f"{m['stats']['tool_calls']:,}",
              f"{m['stats']['tool_errors']:,}", f"{m['stats']['compactions']:,}",
              f"{m['stats']['peak_context_tokens']:,}", sum(1 for c in m.get("commits", []) if c.get("summary"))]
             for sid, m in active]),
        "empty": ("Empty sessions, with no prompts: " + ", ".join(short(sid) for sid in idle) + ".") if idle else "",
        "tokens": _table(
            ["Session", "Written>", "Fresh input>", "Cache write>", "Cache read>", "Cached>", "Read per token written>"],
            [[short(sid), f"{u['output_tokens']:,}", f"{u['input_tokens']:,}", f"{u['cache_creation_input_tokens']:,}",
              f"{u['cache_read_input_tokens']:,}", _cached_share(u),
              f"{(u['input_tokens'] + u['cache_read_input_tokens'] + u['cache_creation_input_tokens']) / u['output_tokens']:,.0f}"
              if u["output_tokens"] else "n/a"]
             for sid, u in ((sid, m["stats"]["usage"]) for sid, m in active)]),
        "tools": _table(["Tool", "Calls>", "Share>", "Sessions>"],
                        [[f"`{name}`", f"{c:,}", f"{c / calls:.1%}", s]
                         for name, (c, s) in sorted(tools.items(), key=lambda kv: (-kv[1][0], kv[0]))]),
        "commits": _table(["#>", "Commit", "Summary", "Sessions"], rows) if rows else "*No commits yet.*",
        "logs": _table(
            ["Session", "Snapshots>", "Uploaded>", "Size>", "Latest log"],
            [[short(sid), len(m.get("logs", {})), sum(1 for i in m.get("logs", {}).values() if i.get("url")),
              gzip_mb(i.get("gzip_bytes", 0) for i in m.get("logs", {}).values()),
              f"[`{m['log']['sha256'][:12]}`]({log_url(sid, m['log']['sha256'])})"
              if m["log"]["sha256"] in m.get("logs", {}) and m["logs"][m["log"]["sha256"]].get("url")
              else f"`{m['log']['sha256'][:12]}`, not uploaded"]
             for sid, m in active]),
        "notes": "\n".join(f"- [`{sid[:8]}`](../session-notes/{sid}.md): {line}" for sid, line in notes) or "*None.*",
    }
    text = string.Template(TRACES_README_TEMPLATE.read_text()).safe_substitute(values)
    return re.sub(r"\n{3,}", "\n\n", text).rstrip() + "\n"


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
        # None (left out) for a session no sync has stored a log of yet: its turns are sent all the same
        "langfuse.trace.metadata.log_sha256": (m.get("log") or {}).get("sha256"),
    }))
    return spans


def langfuse_state(sid: str) -> dict:
    """What has been sent of a session: "exported", the prompt uuids of the turns sent; "complete",
    the log found to have nothing more to send; "hook_cursor", where the Stop hook reads from."""
    try:
        state = json.loads((STATE / f"{sid}.json").read_text())
    except (OSError, ValueError):
        return {"exported": []}
    return state if isinstance(state, dict) and isinstance(state.get("exported"), list) else {"exported": []}


def save_langfuse_state(sid: str, state: dict) -> None:
    atomic_write(STATE / f"{sid}.json", json.dumps(state))


def export_langfuse(sid: str, entries: list[dict], m: dict, live: bool, first_turn: int = 1) -> int:
    """Send the turns of entries not sent yet. first_turn: the number of the first turn in entries,
    when they are the end of a transcript."""
    if (config := langfuse_config()) is None:
        return 0
    host, pk, sk = config
    done = set(langfuse_state(sid)["exported"])
    turns = turns_of(entries)
    if live:  # the last turn may still be running; the Stop hook exports it when it ends
        turns = turns[:-1]
    pending = [(n, t) for n, t in enumerate(turns, first_turn) if t[0]["uuid"] not in done]
    if not pending:
        return 0
    spans = [s for n, t in pending for s in turn_spans(sid, n, t, m)]
    body = {"resourceSpans": [{"resource": {"attributes": [_attr("service.name", "claude-code")]},
                               "scopeSpans": [{"scope": {"name": "llm-traces/sync.py"}, "spans": spans}]}]}
    req = urllib.request.Request(f"{host}/api/public/otel/v1/traces", data=gzip.compress(json.dumps(body).encode()),
                                 method="POST", headers={
        "Content-Type": "application/json", "Content-Encoding": "gzip",
        "Authorization": "Basic " + base64.b64encode(f"{pk}:{sk}".encode()).decode()})
    perf.count("network requests langfuse")
    with urllib.request.urlopen(req, timeout=15) as r:
        r.read()
    state = langfuse_state(sid)  # read again: keep what else it records
    state["exported"] = sorted(set(state["exported"]) | done | {t[0]["uuid"] for _, t in pending})
    save_langfuse_state(sid, state)
    return len(pending)


# --------------------------------------------------------------------------- CDN upload

def log_url(sid: str, sha: str) -> str:
    return f"{CDN_BASE}/raw-traces/{sid}/{sha}.jsonl.gz"


def fetch_log(url: str) -> bytes:
    perf.count("network requests CDN")
    req = urllib.request.Request(url, headers={"User-Agent": "llm-traces-sync"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return gzip.decompress(r.read())


def remote_matches(url: str, sha: str) -> bool:
    try:
        return hashlib.sha256(fetch_log(url)).hexdigest() == sha
    except (OSError, EOFError, gzip.BadGzipFile):
        return False


class UploadRecord:
    """The durable upload record, on this machine only: for each log ("SESSION/SHA256") a push
    started to upload, "attempted" (written before wrangler starts: the object may be in R2) or
    "verified" (the CDN served the log's content afterwards), with the time. A log not in it was
    never attempted from here. Written through on every change, atomically, so an interrupted push
    leaves it accurate. It tells the cases apart for a person and for the next push, which says
    which logs an interrupted one may have uploaded; what is uploaded is still decided by the
    manifests and the CDN, which also cover uploads from other machines."""

    def __init__(self, path: Path | None = None) -> None:
        self.path, self.lock = path or UPLOADS, threading.Lock()
        try:
            entries = json.loads(self.path.read_text())
            self.entries = entries if isinstance(entries, dict) else {}
        except (OSError, ValueError):
            self.entries = {}

    def state(self, sid: str, sha: str) -> str | None:
        return (self.entries.get(f"{sid}/{sha}") or {}).get("state")

    def mark(self, sid: str, sha: str, state: str | None) -> None:
        """Record a log's new state (None: forget it, as after `unpublish`), durably, before returning."""
        with self.lock:
            key = f"{sid}/{sha}"
            if state is None and key not in self.entries:
                return
            if state is None:
                del self.entries[key]
            else:
                self.entries[key] = {"state": state, "at": datetime.now().isoformat(timespec="seconds")}
            atomic_write(self.path, json.dumps(self.entries, indent=1, sort_keys=True) + "\n", private=True)


def upload_jobs() -> tuple[int, int]:
    """(logs handled at once, puts at once). Logs overlap their CDN reads with each other and with
    the puts. Through R2's S3 API (R2Client) every log may put at once. Through wrangler, puts run
    one at a time unless LLM_TRACES_PUT_JOBS says otherwise: every wrangler process uses the one
    OAuth login, and whether several that refresh it at once keep it valid is untested."""
    def number(name: str, default: int) -> int:
        try:
            return max(1, int(os.environ.get(name, default)))
        except ValueError:
            return default
    jobs = number("LLM_TRACES_UPLOAD_JOBS", UPLOAD_JOBS)
    return jobs, number("LLM_TRACES_PUT_JOBS", jobs if R2Client.configured() else PUT_JOBS)


class R2Client:
    """R2's S3-compatible API, signed with AWS Signature Version 4 (region "auto"), from the token in
    R2_CREDENTIALS: PUT, DELETE and HEAD of one object, standard library only. Thread-safe: it
    keeps no connection. Errors name the S3 error code only, never a key or a signature."""
    SERVICE, REGION = "s3", "auto"

    def __init__(self, account_id: str, access_key_id: str, secret_access_key: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", account_id):
            raise ValueError(f"{R2_CREDENTIALS}: account_id is not a Cloudflare account id")
        self.host = f"{account_id}.r2.cloudflarestorage.com"
        self.access_key_id, self._secret = access_key_id, secret_access_key

    @staticmethod
    def configured() -> bool:
        return R2_CREDENTIALS.exists()

    @classmethod
    def from_file(cls, path: Path | None = None) -> "R2Client":
        c = read_r2_credentials(path)
        missing = [k for k in ("account_id", "access_key_id", "secret_access_key") if not c.get(k)]
        if missing:
            raise ValueError(f"{path or R2_CREDENTIALS} lacks {', '.join(missing)}")
        return cls(c["account_id"], c["access_key_id"], c["secret_access_key"])

    def signed_headers(self, method: str, path: str, headers: dict[str, str], payload_sha256: str,
                       at: datetime) -> dict[str, str]:
        """headers plus host, x-amz-date, x-amz-content-sha256 and Authorization, every header signed.
        path: the request path, already URI-encoded; no query string is used."""
        amz_date, day = at.strftime("%Y%m%dT%H%M%SZ"), at.strftime("%Y%m%d")
        headers = {**headers, "x-amz-date": amz_date, "x-amz-content-sha256": payload_sha256}
        canon = {k.lower().strip(): " ".join(str(v).split()) for k, v in headers.items()}
        canon.setdefault("host", self.host)
        names = sorted(canon)
        request = "\n".join([method, path, "", *(f"{k}:{canon[k]}" for k in names), "", ";".join(names), payload_sha256])
        scope = f"{day}/{self.REGION}/{self.SERVICE}/aws4_request"
        to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(request.encode()).hexdigest()])
        key = f"AWS4{self._secret}".encode()
        for part in (day, self.REGION, self.SERVICE, "aws4_request"):
            key = hmac.new(key, part.encode(), hashlib.sha256).digest()
        signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
        return {**headers, "host": canon["host"], "Authorization":
                f"AWS4-HMAC-SHA256 Credential={self.access_key_id}/{scope}, SignedHeaders={';'.join(names)}, Signature={signature}"}

    def request(self, method: str, bucket: str, key: str, body: bytes = b"", headers: dict[str, str] | None = None,
                timeout: float = 300) -> int:
        """The response status; raises RuntimeError for any other than 2xx (404 too, except for HEAD)."""
        path = "/" + urllib.parse.quote(f"{bucket}/{key}", safe="/-_.~")
        signed = self.signed_headers(method, path, headers or {}, hashlib.sha256(body).hexdigest(),
                                     datetime.now(timezone.utc))
        signed.pop("host")  # urllib sends the same Host itself
        req = urllib.request.Request(f"https://{self.host}{path}", data=body if method == "PUT" else None,
                                     method=method, headers=signed)
        perf.count(f"network requests R2 {method}")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                r.read()
                return r.status
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code == 404:
                return 404
            code = re.search(rb"<Code>([A-Za-z]{1,64})</Code>", e.read(4096) or b"")
            raise RuntimeError(f"R2 {method} {bucket}/{key}: HTTP {e.code}"
                               + (f" {code.group(1).decode()}" if code else "")) from None

    def put(self, bucket: str, key: str, path: Path) -> None:
        self.request("PUT", bucket, key, path.read_bytes(), {"content-type": "application/gzip"})

    def delete(self, bucket: str, key: str) -> None:
        self.request("DELETE", bucket, key)

    def exists(self, bucket: str, key: str) -> bool:
        return self.request("HEAD", bucket, key) != 404


def put_log(key: str, path: Path) -> None:
    """Put a log in R2 at key ("raw-traces/SESSION/SHA.jsonl.gz" in CDN_BUCKET): through the S3 API
    with an R2 token, through wrangler otherwise. Raises RuntimeError if it fails."""
    if R2Client.configured():
        perf.count("r2 puts")
        R2Client.from_file().put(CDN_BUCKET, key, path)
        return
    if not WRANGLER.exists():
        raise FileNotFoundError("wrangler is not installed and there is no R2 token; run: python3 llm-dlc/tools/sync.py init")
    r = wrangler_put(f"{CDN_BUCKET}/{key}", path)
    if r.returncode != 0:
        raise RuntimeError(f"wrangler r2 object put failed:\n{r.stdout}{r.stderr}")


def wrangler_put(key: str, path: Path) -> subprocess.CompletedProcess:
    perf.count("subprocess wrangler r2 put")
    return subprocess.run([NODE, str(WRANGLER), "r2", "object", "put", key, "--remote",
                           "--file", str(path), "--content-type", "application/gzip"],
                          cwd=CDN_DIR, capture_output=True, text=True, timeout=300,
                          env={**os.environ, "WRANGLER_SEND_METRICS": "false"})


class UploadStopped(Exception):
    """A log not uploaded because the upload was interrupted before its put started."""


class Uploader:
    """Puts logs in R2, several at once (upload_jobs). Each log is first looked for on the CDN; one
    not served there is verified against its name and scanned, then put, then read back through the
    CDN. Verifying and scanning take turns (the redactor and caches are not shared between
    threads) and read the caches `check` keeps: by the stored .gz bytes, then by content, so a
    log is scanned again only if check has not scanned exactly that content under these rules.
    With LLM_TRACES_FULL=1 nothing is taken from them."""

    def __init__(self, redact: Redactor, scans: ScanCache | None = None, checks: CheckCache | None = None,
                 record: UploadRecord | None = None, puts: int = 1) -> None:
        self.redact = redact
        self.scans = scans or ScanCache(redact, path=None)
        self.checks = checks or CheckCache(redact, path=None)
        self.record = record or UploadRecord()
        self.cpu, self.puts = threading.Lock(), threading.Semaphore(puts)
        # Set on an interrupt, here or in cmd_upload: a worker freed by it would otherwise start the next
        # queued log before the pool is shut down. A put already running finishes; none starts after.
        self.stopped = threading.Event()

    def __call__(self, sid: str, sha: str) -> str:
        """Put one log in R2 (unless the CDN already serves it) and prove the CDN returns its bytes.
        Nothing the current redactor would change may go public."""
        try:
            return self.upload(sid, sha)
        except BaseException as e:
            if not isinstance(e, Exception):  # KeyboardInterrupt or SystemExit in this worker
                self.stopped.set()
            raise

    def stop_point(self, sid: str, sha: str) -> None:
        if self.stopped.is_set():
            raise UploadStopped(f"log {sha[:12]} of {sid} not uploaded: the upload was interrupted")

    def upload(self, sid: str, sha: str) -> str:
        self.stop_point(sid, sha)
        url = log_url(sid, sha)
        if remote_matches(url, sha):
            self.record.mark(sid, sha, "verified")
            return url
        path = log_path(sid, sha)
        with self.cpu:
            stored = self.checks.snapshot(path)
            if stored is None:
                raise FileNotFoundError(f"log {sha[:12]} of {sid} is neither stored locally nor on the CDN")
            actual, size, data, gz = stored
            if actual != sha:
                raise RuntimeError(f"refusing to upload log {sha[:12]} of {sid}: its content does not match its name")
            found = self.scans.hits(sid, actual, data if data is not None else (lambda gz=gz: decompress(gz)), size)
            del data, gz
            if leaks := self.redact.cached_leaks(found):
                raise RuntimeError(f"refusing to upload log {sha[:12]} of {sid}: unredacted {leaks}")
            for warning in self.redact.cached_review(found):
                print(f"warn  {sid[:8]}/{sha[:12]}: {warning}")
        with self.puts:
            self.stop_point(sid, sha)
            self.record.mark(sid, sha, "attempted")
            put_log(f"raw-traces/{sid}/{sha}.jsonl.gz", path)
        if not remote_matches(url, sha):
            raise RuntimeError(f"uploaded {url} but the CDN does not serve content with sha256 {sha}")
        self.record.mark(sid, sha, "verified")
        return url


def upload_log(sid: str, sha: str, redact: Redactor) -> str:
    """One log, as cmd_upload would put it, without its caches."""
    return Uploader(redact)(sid, sha)


def cmd_upload(include_at: bool = False, full: bool = False) -> int:
    """Upload every log a commit points at (and subagent logs), then record the URLs: each in its
    manifest as soon as the CDN serves it, so an interrupted push keeps what it verified."""
    failed, redact = 0, Redactor()
    full = full or full_audit([])
    # @'s log can still be replaced; upload it only when @ is about to be frozen (include_at).
    at = jj_commits("@")[0]["change_id"] if has_jj() and not include_at else None
    manifests, todo = all_manifests(), []
    for sid, m in manifests.items():
        if m.get("schema") != SCHEMA:
            continue
        wanted = {c["log_sha256"] for c in m.get("commits", []) if c.get("log_sha256") and c["change_id"] != at}
        wanted |= {s["log"]["sha256"] for s in m.get("subagents", [])}
        # A push also publishes each session's current log, which its committed manifest names: a session
        # that made no commit (one opened and left empty, say) would otherwise never be uploaded, and
        # check fails on every other machine, where the log is neither stored nor on the CDN.
        if include_at and m.get("log", {}).get("sha256"):
            wanted.add(m["log"]["sha256"])
        logs = m.setdefault("logs", {})
        todo += [(sid, sha) for sha in sorted(wanted) if not logs.get(sha, {}).get("url")]
    record = UploadRecord()
    if interrupted := [f"{sid[:8]}/{sha[:12]}" for sid, sha in todo if record.state(sid, sha)]:
        print(f"{len(interrupted)} log(s) an earlier push started to upload are looked for on the CDN first: "
              + ", ".join(interrupted))
    jobs, puts = upload_jobs()
    uploader = Uploader(redact, ScanCache(redact, trusted=not full), CheckCache(redact, trusted=not full), record, puts)
    def served(sid: str, sha: str, url: str) -> None:
        manifests[sid]["logs"].setdefault(sha, {})["url"] = url
        save_manifest(sid, manifests[sid])
        perf.count("logs uploaded or found on the CDN")
        print(f"uploaded {url}")

    with perf.phase("upload"):
        pool = ThreadPoolExecutor(max_workers=jobs)
        running = {pool.submit(uploader, sid, sha): (sid, sha) for sid, sha in todo}
        try:
            for done in as_completed(running):
                sid, sha = running.pop(done)
                try:
                    url = done.result()
                except UploadStopped:  # the interrupt that stopped it is raised by its own future
                    continue
                except (OSError, RuntimeError) as e:
                    print(f"ERROR {e}", file=sys.stderr)
                    failed += 1
                    continue
                served(sid, sha, url)
        finally:  # left early by an exception (Ctrl-C): start nothing new, keep what the CDN serves
            uploader.stopped.set()
            pool.shutdown(wait=True, cancel_futures=True)
            for done, (sid, sha) in running.items():
                if not done.cancelled() and done.exception() is None:
                    served(sid, sha, done.result())
    save_previewed(uploader.scans, uploader.checks)  # adds to what check keeps; drops nothing
    for sid, m in manifests.items():
        if m.get("schema") == SCHEMA:
            save_manifest(sid, m)
    return 1 if failed else 0


def cloudflare(method: str, path: str, token: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(f"https://api.cloudflare.com/client/v4{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    perf.count("network requests Cloudflare API")
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
    With --reason, the log is withdrawn: its local copy is deleted too and the manifest records
    why, so `check` reports the commits that point at it as a note instead of an error. The
    content is gone; the hash in the commit trailers still says what it was."""
    reason = None
    if len(args) == 4 and args[2] == "--reason" and args[3].strip():
        args, reason = args[:2], args[3].strip()
    if len(args) != 2 or not re.fullmatch(r"[0-9a-f]{64}", args[1]):
        print("usage: sync.py unpublish SESSION_ID SHA256 [--reason TEXT]", file=sys.stderr)
        return 2
    sid, sha = args
    url = log_url(sid, sha)
    if R2Client.configured():
        try:
            R2Client.from_file().delete(CDN_BUCKET, f"raw-traces/{sid}/{sha}.jsonl.gz")
        except (OSError, RuntimeError, ValueError) as e:
            print(f"ERROR {e}", file=sys.stderr)
            return 1
    else:
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
    UploadRecord().mark(sid, sha, None)
    m = load_manifest(sid)
    entry = m.setdefault("logs", {}).setdefault(sha, {})
    entry.pop("url", None)
    if reason:
        entry["withdrawn"] = reason
        log_path(sid, sha).unlink(missing_ok=True)
    save_manifest(sid, m)
    print(f"unpublished {url}" + (f" and withdrew it: {reason}" if reason else ""))
    if any(c.get("log_sha256") == sha for c in m.get("commits", [])) and not reason:
        print("note: a commit still points at this log; withdraw it with --reason, or `check` will fail")
    return 0


# --------------------------------------------------------------------------- the repository coordinator

class Busy(Exception):
    """Another operation holds the repository and did not finish within the wait asked for."""


class Operation:
    """One sync.py command that changes the repository, its trace files or the local state they
    depend on, serialized with every other such command on this repository.

    Its lock (flock, so the kernel releases it when the holder dies) is exclusive for commands that
    write and shared for check and scan, which only read: they then never see a sync half done. A
    command waits for the holder, saying which command that is; the commit hook waits at most
    HOOK_LOCK_WAIT seconds and otherwise leaves its commit to the next sync, which stamps it anyway.

    Its journal (journal, done) lists the steps under way that an interruption would leave half
    done. It is written before each such step and cleared after, so it is empty whenever nothing is
    under way, and one left by a holder that was killed is read, and its steps recovered or
    reported, by the next exclusive operation (recover_step). The lock, the journal and the holder's
    name are local, under STATE/locks, keyed by the repository's path."""

    def __init__(self, command: str, exclusive: bool = True, wait: float | None = None) -> None:
        base = STATE / "locks" / hashlib.sha256(str(REPO.resolve()).encode()).hexdigest()[:16]
        self.lock_path, self.owner_path, self.journal_path = (base.with_name(base.name + s) for s in
                                                              (".lock", ".owner", ".journal.json"))
        self.command, self.exclusive, self.wait = command, exclusive, wait
        self.steps: dict[str, dict] = {}
        self.fd, self.outer, self.jj_op, self.serial, self.nested = None, None, None, 0, False
        self.started = datetime.now().isoformat(timespec="seconds")

    def holder(self) -> str:
        try:
            o = json.loads(self.owner_path.read_text())
            os.kill(o["pid"], 0)
            return f"`sync.py {o['command']}` (pid {o['pid']}, since {o['started']})"
        except (OSError, ValueError, KeyError, TypeError):
            return "a `sync.py check` or `scan`"

    def __enter__(self) -> "Operation":
        import fcntl
        global operation
        if operation is not None:  # this process holds it already: a second flock would wait for itself
            self.nested = True
            return operation
        self.lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
        mode = fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH
        started = time.perf_counter()
        try:
            try:
                fcntl.flock(self.fd, mode | fcntl.LOCK_NB)
            except BlockingIOError:
                holder = self.holder()
                print(f"waiting for {holder} to finish with this repository", file=sys.stderr, flush=True)
                deadline = None if self.wait is None else time.monotonic() + self.wait
                while True:
                    if deadline is None:
                        fcntl.flock(self.fd, mode)
                        break
                    try:
                        fcntl.flock(self.fd, mode | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() > deadline:
                            raise Busy(holder) from None
                        time.sleep(0.05)
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise
        perf.count("lock wait seconds", time.perf_counter() - started)
        if self.exclusive:
            atomic_write(self.owner_path, json.dumps({"command": self.command, "pid": os.getpid(),
                                                      "started": self.started}), private=True)
        self.outer, operation = operation, self
        try:
            self.recover()
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise
        return self

    def __exit__(self, *exc) -> None:
        global operation
        if self.nested:
            return
        operation = self.outer
        try:
            if self.exclusive:
                if not self.steps:
                    self.journal_path.unlink(missing_ok=True)
                self.owner_path.unlink(missing_ok=True)
        finally:
            os.close(self.fd)  # and with it the lock
            self.fd = None

    def save(self) -> None:
        if self.steps:
            atomic_write(self.journal_path, json.dumps({"command": self.command, "pid": os.getpid(),
                                                        "started": self.started, "jj_op": self.jj_op,
                                                        "steps": self.steps}, indent=1), private=True)
        else:
            self.journal_path.unlink(missing_ok=True)

    def recover(self) -> None:
        try:
            old = json.loads(self.journal_path.read_text())
        except FileNotFoundError:
            return
        except ValueError:  # atomic writes make this a file someone else wrote
            old = {"command": "?", "steps": {}}
        if not self.exclusive:
            print(f"warn: `sync.py {old.get('command')}` was interrupted (pid {old.get('pid')}, started "
                  f"{old.get('started')}); the next sync, commit or push recovers what it left", file=sys.stderr)
            return
        lines = [f"`sync.py {old.get('command')}` (pid {old.get('pid')}, started {old.get('started')}) was "
                 f"interrupted" + (f"; `jj op log` shows what it did after operation {old['jj_op']}" if old.get("jj_op") else "")]
        lines += [f"  {recover_step(step)}" for step in old.get("steps", {}).values()]
        print("\n".join(lines), file=sys.stderr)
        log(" | ".join(lines))
        self.journal_path.unlink(missing_ok=True)

    def begin(self, kind: str, **data) -> str:
        if self.jj_op is None and has_jj():
            self.jj_op = jj("op", "log", "-n1", "--no-graph", "--ignore-working-copy", "-T", "id.short(12)").stdout.strip()
        self.serial += 1
        key = f"{self.serial}"
        self.steps[key] = {"kind": kind, **data}
        self.save()
        return key

    def update(self, key: str, **data) -> None:
        self.steps[key].update(data)
        self.save()

    def end(self, key: str) -> None:
        self.steps.pop(key, None)
        self.save()


operation: Operation | None = None  # the one this process holds, if any


def journal(kind: str, **data) -> str | None:
    """Record in the journal a step an interruption would leave half done; outside an operation (a
    test, a library call) there is none."""
    return operation.begin(kind, **data) if operation and operation.exclusive else None


def journal_update(key: str | None, **data) -> None:
    if key and operation:
        operation.update(key, **data)


def done(key: str | None) -> None:
    if key and operation:
        operation.end(key)


@contextlib.contextmanager
def journaled(kind: str, **data):
    """A step that is done when its block ends normally, a return included. An exception leaves it
    in the journal, to be reported by the next operation, as a kill does."""
    key = journal(kind, **data)
    yield key
    done(key)


def return_working_copy(step: dict) -> str:
    """Undo hook-commit's switch of the working copy to the commit it records: if @ is still that
    commit, edit the change it found as @ again, or start a new one where it had abandoned an empty
    @. Anything else means someone moved @ since, and it is left where it is."""
    at = jj_commits("@")
    if not at or at[0]["change_id"] != step["edited"]:
        return "the working copy had already left the commit the hook recorded; left where it is"
    r = jj("edit", step["back"]) if step.get("back") else jj("new")
    if r.returncode:
        raise RuntimeError(f"could not return the working copy from {step['edited'][:12]}: {r.stderr.strip()}")
    return (f"the working copy was left on the commit it recorded, {step['edited'][:12]}; "
            + (f"returned it to {step['back'][:12]}" if step.get("back") else "started a new change above it"))


def recover_step(step: dict) -> str:
    """Recover or report one step a killed operation left in the journal."""
    kind = step.get("kind")
    if kind == "away":
        return return_working_copy(step)
    if kind == "sync":
        write_index()
        return ("a sync stopped part way: rebuilt the global files; sessions it did not reach are synced "
                "by the next commit, which sees they changed")
    if kind == "describe":
        return (f"a commit described @ as {step.get('summary')!r} but did not finish (`jj new`); run "
                "`sync.py commit` again to finish it, or `jj describe` to change the message")
    if kind == "publish":
        return (f"a push stopped at its {step.get('stage')} stage; run `sync.py push` again. Logs it verified "
                "on the CDN are in the upload record, and a log it may have uploaded is looked for first")
    return f"an unknown step was left: {kind}"


HOOK_LOCK_WAIT = 15  # seconds hook-commit waits for another operation (its hook times out at 60)
# How each command takes the repository lock; commands not listed take none: the Stop hook writes
# only its Langfuse cursor, and hook-commit takes it itself, once it knows the call was a commit.
LOCKING = {"check": "shared", "scan": "shared", "sync": "exclusive", "commit": "exclusive", "push": "exclusive",
           "upload": "exclusive", "unpublish": "exclusive", "stamp": "exclusive", "allow": "exclusive",
           "review": "exclusive", "init": "exclusive"}


def _terminated(signum, frame) -> None:
    """SIGTERM and SIGHUP (a hook's timeout, a closed terminal) unwind like Ctrl-C, so that the
    finally blocks put the working copy back and the journal is current."""
    raise SystemExit(128 + signum)


# --------------------------------------------------------------------------- commands

def process(transcript: Path, redact: Redactor, status: str, live: bool, current: bool,
            publishing: bool = False, cache: LocalCache | None = None) -> dict:
    """Bring a session's own tracked files up to date; the caller rebuilds the global ones once,
    with write_index. Langfuse is not contacted: the Stop hook sends turns. live: the last turn may be
    unfinished. current: the session is the one running now, so @ is its working copy.
    publishing: @ is a trace record, which carries every session with log no commit points at yet."""
    known = {c.get("log_sha256") for c in load_manifest(transcript.stem).get("commits", [])}
    with perf.phase("snapshot"):
        sid, m, entries, subagents = sync_session(transcript, redact, status, cache)
    if publishing:
        current = bool(m["stats"]["turns"]) and m["log"]["sha256"] not in known
    if has_jj():
        with perf.phase("link commits"):
            link_commits(sid, m, current, publishing)
    finalize_logs(sid, m)
    with perf.phase("summary and metrics"):
        render_summary(sid, m, entries, redact.string(str(REPO)))
        write_if_changed(metrics_path(sid), session_metrics(sid, m, entries, redact, subagents))
    return m


def langfuse_config() -> tuple[str, str, str] | None:
    env = read_env(LANGFUSE_ENV)
    host, pk, sk = env.get("LANGFUSE_HOST"), env.get("LANGFUSE_INIT_PROJECT_PUBLIC_KEY"), env.get("LANGFUSE_INIT_PROJECT_SECRET_KEY")
    return (host, pk, sk) if host and pk and sk else None


def langfuse_todo() -> list[str]:
    """Sessions that may have finished turns not yet sent to Langfuse, cheaply: those whose
    end-of-turn hook did not finish a send (hook_unsent), and those with a stored log not marked as
    fully sent. A session whose latest log was found fully sent, once it had ended, is marked in its
    state file by that log's sha."""
    todo = [sid for sid, _ in hook_unsent()]
    for sid, m in all_manifests().items():
        sha = (m.get("log") or {}).get("sha256")
        state_file = STATE / f"{sid}.json"
        try:
            marked = json.loads(state_file.read_text()).get("complete") if state_file.exists() else None
        except ValueError:
            marked = None
        if sha and marked != sha and sid not in todo:
            todo.append(sid)
    return todo


HOOK_GRACE = 120  # seconds: longer than the hooks' 60 s timeout, so a hook still running is not reported


def hook_unsent(older_than: float = 0) -> list[tuple[str, str]]:
    """(session, since) for each session whose end-of-turn hook started a send that did not finish:
    Langfuse was down, or the hook failed, timed out or was killed. The mark is set before a hook
    reads anything and cleared only after everything it found was sent, so a session without it has
    had every finished turn sent. older_than: only marks set at least that many seconds ago."""
    found = []
    for f in sorted(STATE.glob("*-*-*-*-*.json")) if STATE.is_dir() else []:  # sessions', not the caches
        if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", f.stem):
            continue
        try:
            since = json.loads(f.read_text()).get("hook_unsent")
        except (OSError, ValueError, AttributeError):
            continue
        try:
            age = time.time() - datetime.fromisoformat(since).timestamp() if since else None
        except (TypeError, ValueError):
            age = older_than
        if age is not None and age >= older_than:
            found.append((f.stem, since))
    return found


def mark_hook_unsent(sid: str, unsent: bool) -> None:
    """Set or clear the mark that hook_unsent reads, keeping the rest of the state."""
    state = langfuse_state(sid)
    if unsent:
        state["hook_unsent"] = state.get("hook_unsent") or datetime.now(timezone.utc).isoformat(timespec="seconds")
    elif "hook_unsent" in state:
        del state["hook_unsent"]
    else:
        return
    save_langfuse_state(sid, state)


def langfuse_send(sid: str, live: bool | None = None) -> None:
    """Send one session's finished turns: from its transcript while that is on this machine, as the
    Stop hook does, which covers turns no commit has stored yet; otherwise from its stored log. A
    session still running (written in the last LIVE_SECONDS, or `live`) keeps its last turn for its
    Stop hook, and its log is not marked done, so a later run looks at that turn again."""
    if langfuse_config() is None:  # nothing is sent, so nothing is complete
        raise OSError("no Langfuse configured (llm-dlc/infra/langfuse/.env)")
    transcript = claude_project_dir() / f"{sid}.jsonl"
    if transcript.exists():
        if live is None:
            live = time.time() - transcript.stat().st_mtime < LIVE_SECONDS
        hook_export(transcript, Redactor(), live=live)
        mark_hook_unsent(sid, False)
        return
    m = load_manifest(sid)
    data = load_log(sid, m["log"]["sha256"]) if m.get("log") else None
    if data is None:
        if not m.get("log"):  # no transcript and no log was ever stored: nothing can be sent, now or later
            print(f"{sid}: nothing to send, no transcript on this machine and no stored log", file=sys.stderr)
            mark_hook_unsent(sid, False)
        return
    live = m.get("status") != "ended" if live is None else live
    export_langfuse(sid, read_jsonl(data), m, live=live)
    if not live:  # a live log kept its last turn back: it is not done
        state = langfuse_state(sid)
        state["complete"] = m["log"]["sha256"]
        save_langfuse_state(sid, state)
        mark_hook_unsent(sid, False)


def cmd_langfuse(args: list[str]) -> int:
    """Send these sessions' finished turns to Langfuse by hand, redacted as the Stop hook does them:
    for sessions whose hook ran while Langfuse was down or failed (langfuse_send). Commit and sync never contact
    Langfuse. The first failure stops it, and only sent turns are recorded, so a rerun resumes.
    --pending lists the sessions that may have turns to send; --all sends for all of them."""
    if args == ["--pending"]:
        for sid in langfuse_todo():
            print(sid)
        return 0
    if args == ["--all"]:
        args = langfuse_todo()
    args = list(dict.fromkeys(args))  # a session named twice is sent once
    for i, arg in enumerate(args):
        sid, _, flag = arg.partition(":")
        try:
            langfuse_send(sid, True if flag == "live" else None)
        except OSError as e:
            log(f"langfuse export deferred for {sid}: {e}")
            log("to send the sessions not sent yet: python3 llm-dlc/tools/sync.py langfuse " + " ".join(args[i:]))
            return 1
        except Exception:
            log(traceback.format_exc())
    return 0


_MAY_BREAK = re.compile(rb"[\r\x0b\x0c\x1c-\x1e\x80-\xff]")


def lines_in(raw: bytes) -> int:
    """len(decoded(raw).splitlines()): how many lines Rules.__call__ reads, and so writes, for these
    bytes of a transcript, cut after a newline. Bytes without a carriage return, another ASCII line
    break or a non-ASCII byte decode to themselves in any ASCII-compatible encoding."""
    if not _MAY_BREAK.search(raw):
        return raw.count(b"\n") + (not raw.endswith(b"\n") and bool(raw))
    return len(decoded(raw).splitlines())


def hook_export(transcript: Path, redact: Redactor, live: bool = False) -> int:
    """Send a transcript's finished turns, reading it from the hook's cursor: the start of the first
    turn not sent yet, or of the unfinished last line when every turn was sent. Turns before it are
    never sent again, so it is enough to redact and parse what follows it. The cursor is used only
    when the transcript's bytes before it have the recorded SHA-256 under the same rules and tools,
    so a replaced or truncated transcript is read whole, as is every one under --full
    (LLM_TRACES_FULL=1). It records the number of turns before it and the last title there, which
    the turns after it are numbered and named by. Without a cursor, the log `sync` last made of the
    transcript is reused (redacted_incrementally; the cache is not saved). The cursor moves only
    after a send succeeds, and over whole lines of the transcript: one that the decoder or the
    redactor splits in two (a carriage return, a raw U+2028) is read as the lines it gives.
    live: the last turn may still be running, so it is not sent and the cursor stays before it."""
    sid, fingerprint = transcript.stem, sha256(f"{redact.fingerprint()}\0{tools_digest()}".encode())
    raw = transcript.read_bytes()
    state, start, turns_before, title = langfuse_state(sid), 0, 0, None
    cursor = state.get("hook_cursor")
    if (isinstance(cursor, dict) and not full_audit([]) and cursor.get("fingerprint") == fingerprint
            and 0 < cursor.get("source_bytes", -1) <= len(raw)
            and sha256(memoryview(raw)[:cursor["source_bytes"]]) == cursor.get("source_sha256")):
        start, turns_before, title = cursor["source_bytes"], cursor["turns"], cursor["title"]
        perf.count("transcript bytes not read again (hook cursor)", start)
    with perf.phase("redact"):
        if start:
            log = redact(decoded(raw[start:]))
        else:
            log = redacted_incrementally(raw, sid, sid, redact, None if full_audit([]) else transcript_cache(redact))
    perf.count("transcript bytes redacted (hook)", len(raw) - start)
    raw_lines = raw[start:].split(b"\n")
    counts = [lines_in(line + b"\n") for line in raw_lines[:-1]] + [lines_in(raw_lines[-1])]
    log_lines = log.split(b"\n")[:-1]  # Rules.__call__ ends every line it writes with a newline
    if sum(counts) != len(log_lines):  # never, as the redactor works: read it all, move no cursor
        counts, raw_lines = [], [b""]
        lines = [read_jsonl(log)]
    else:
        at = [0]
        for n in counts:
            at.append(at[-1] + n)
        lines = [read_jsonl(b"\n".join(log_lines[a:b])) for a, b in zip(at, at[1:])]  # read_jsonl(log), by raw line
    entries = [e for found in lines for e in found]
    for e in entries:
        if e.get("type") == "ai-title":
            title = e.get("aiTitle") or title
    m = {**load_manifest(sid), "title": title}
    sent = export_langfuse(sid, entries, m, live=live, first_turn=turns_before + 1)
    done = set(langfuse_state(sid)["exported"])
    offset, title = start, cursor["title"] if start else None
    for raw_line, found in zip(raw_lines[:-1], lines):  # the last is unfinished, or empty
        if any(is_prompt(e) and e.get("uuid") not in done for e in found):
            break
        turns_before += sum(1 for e in found if is_prompt(e))
        title = next((e.get("aiTitle") for e in reversed(found) if e.get("type") == "ai-title" and e.get("aiTitle")), title)
        offset += len(raw_line) + 1
    if offset > start:
        state = langfuse_state(sid)
        state["hook_cursor"] = {"fingerprint": fingerprint, "source_bytes": offset,
                                "source_sha256": sha256(memoryview(raw)[:offset]), "turns": turns_before, "title": title}
        save_langfuse_state(sid, state)
    return sent


def cmd_hook() -> None:
    """Stop and SessionEnd: send finished turns to Langfuse, and leave the repo alone. A transcript
    is kept on disk until a commit or a push records it, so nothing depends on this running."""
    try:
        payload = json.load(sys.stdin)
        if langfuse_config() is None:  # before reading and redacting the whole transcript
            return
        transcript = Path(payload["transcript_path"])
        if not transcript.exists():
            # A session that ended without writing a transcript (one opened and closed with no message, say)
            # has nothing to send, now or later: marking it would leave a warning nothing can clear.
            log(f"langfuse: no transcript at {transcript}, nothing to send")
            return
        # Marked before anything is read, cleared once all was sent: a hook that fails, times out
        # or is killed leaves the mark, which `check` reports and `sync.py langfuse --all` acts on.
        mark_hook_unsent(transcript.stem, True)
        hook_export(transcript, Redactor())
        mark_hook_unsent(transcript.stem, False)
    except OSError as e:  # Langfuse down: those turns are retried next time
        log(f"langfuse export deferred: {e}")
    except Exception:
        log(traceback.format_exc())


def trace_owned(path: str) -> bool:
    """Whether the trace tools write this repo path. llm-dlc/README.md counts, because `sync`
    rewrites its session table, so a hand edit to it travels with the trace record."""
    return path.startswith((str(TRACES.relative_to(REPO)) + "/", str(INDEX.relative_to(REPO)),
                            str(CHANGES_README.relative_to(REPO))))


PLAIN_COMMIT = re.compile(r"\b(?:jj\s+(?:commit|ci|new)|git\s+commit)\b")


def cmd_hook_commit() -> None:
    """PostToolUse on Bash: a commit made without `sync.py commit` gets the same treatment, so it
    carries this session's trailer and its manifest whichever way it was made. It reopens the new
    commit as @, syncs into it exactly as `sync.py commit` does, and returns to the working copy."""
    try:
        payload = json.load(sys.stdin)
        transcript = Path(payload["transcript_path"])
        if not PLAIN_COMMIT.search(payload.get("tool_input", {}).get("command", "")) or not has_jj():
            return
        at = jj_commits("@")[0]
        parents = jj_commits("parents(@)")
        if len(parents) != 1 or parents[0]["immutable"] or commit_summary(parents[0]["description"]) is None:
            return
        if any(s == transcript.stem and sha for s, sha in session_trailers(parents[0]["description"])):
            return  # already recorded, for example by `sync.py commit`
        try:
            lock = Operation("hook-commit", wait=HOOK_LOCK_WAIT).__enter__()
        except Busy as e:
            log(f"hook-commit: {e} held the repository; the next sync records {parents[0]['change_id'][:12]}")
            return
        try:
            hook_commit(transcript, at, parents[0])
        finally:
            lock.__exit__(*sys.exc_info())
    except Exception:
        log(traceback.format_exc())


def hook_commit(transcript: Path, at: dict, parent: dict) -> None:
    """hook-commit's work, under the repository lock: @ and its parent are read again, since another
    operation may have moved them while the hook waited."""
    if [c["change_id"] for c in jj_commits("@")] != [at["change_id"]] or \
            [c["change_id"] for c in jj_commits("parents(@)")] != [parent["change_id"]]:
        log("hook-commit: the working copy moved while the hook waited; the next sync records the commit")
        return
    changed = jj("diff", "--name-only").stdout.splitlines()
    if any(trace_owned(p) for p in changed):
        return  # rewriting the commit below would conflict; the next sync stamps it instead
    # Journaled before the switch: a kill after it (a hook's timeout) leaves @ on a finished commit,
    # where the next edits would land, until the next operation puts it back.
    step = {"edited": parent["change_id"], "back": at["change_id"] if changed or at["description"] else None}
    key = journal("away", **step)
    jj("edit", parent["change_id"])  # abandons @ if it is empty and has no message
    try:
        redact = Redactor()
        cache = transcript_cache(redact)
        process(transcript, redact, "open", live=False, current=True, cache=cache)
        cache.save()
        write_index()
    finally:
        return_working_copy(step)
        done(key)


def cmd_sync(args: list[str], publishing: bool = False, redact: "Redactor | None" = None) -> "Redactor":
    """Sync the sessions named, or else every session whose state (session_state) differs from the
    one recorded after it was last synced: one whose transcript grew, whose commits were described,
    rewritten or became immutable, whose note or generated files changed, or that went from open to
    ended. --all and --full sync every session, and so does a publish."""
    src, full = claude_project_dir(), full_audit(args)
    named = [a for a in args if a not in ("--full", "--all")]
    every = full or publishing or "--all" in args
    paths = [src / f"{a}.jsonl" for a in named] if named else sorted(src.glob("*.jsonl"))
    redact = redact or Redactor()
    cache, states = transcript_cache(redact, full), sync_cache(redact, trusted=not every)
    me, index, unchanged = running_session(), commit_index(), 0
    with journaled("sync"):
        publish_runs(redact)  # before the sessions: their summaries list the copies
        for p in paths:
            live = time.time() - p.stat().st_mtime < LIVE_SECONDS
            status, current = "open" if live else "ended", live or p.stem == me
            if not named and not every and states.entries.get(p.stem) == session_state(p, status, current, index):
                unchanged += 1
                perf.count("sessions unchanged, not synced")
                continue
            state = session_state(p, status, current, None)  # its sources, before they are read
            with perf.phase("process"):
                m = process(p, redact, status, live, current=current, publishing=publishing, cache=cache)
            index = commit_index()  # process may have described changes
            if publishing:  # its manifest records git SHAs that a sync outside a publish leaves out
                states.entries.pop(p.stem, None)
            else:
                states.entries[p.stem] = {**session_state(p, status, current, index), "sources": state["sources"]}
            s = m["stats"]
            print(f"{m['session_id']}  {s['turns']} turns  {s['tool_calls']} tools  log sha256:{m['log']['sha256'][:12]}… "
                  f"{m['log']['bytes']:,} B  commits: {len(m['commits'])}{'  (live)' if live else ''}")
        if unchanged:
            print(f"{unchanged} sessions unchanged since their last sync (--all syncs them anyway)")
        publish_runs(redact)  # again, for a session whose trace the loop above started
        for sid in sorted({p.parent.parent.name for p in TRACES.glob("*/runs/*.md")}):
            splice_runs(sid)  # a session rendered above already lists its runs; one traced elsewhere does not
        cache.save()
        states.save()
        with perf.phase("index"):
            write_index()  # once, after every session: it reads all their manifests
    return redact


def transcripts_of(p: Path) -> list[tuple[str, Path]]:
    """A session's transcript and its subagents', each with its key in the transcript cache."""
    subdir = p.parent / p.stem / "subagents"
    return [(p.stem, p)] + ([(f"{p.stem}/{s.stem}", s) for s in sorted(subdir.glob("*.jsonl"))] if subdir.is_dir() else [])


def redacted_now(path: Path, sid: str, key: str, redact: Redactor, cache: LocalCache | None) -> tuple[bytes, bytes]:
    """(raw bytes, log) of a transcript as it is now, redacted only from where the log `sync` last
    stored for it ends (redacted_incrementally). For commands that store no log: the cache entry
    this makes names a log that is never stored, so their caller must not save the cache."""
    raw = path.read_bytes()
    return raw, redacted_incrementally(raw, sid, key, redact, cache)


def preview_caches(redact: Redactor, full: bool) -> tuple[ScanCache, CheckCache, LocalCache]:
    """The caches `scan`, `review` and `stamp` read: what `check` scanned and verified, and what
    `sync` redacted. --full (or LLM_TRACES_FULL=1) trusts none of them."""
    full = full or full_audit([])
    return ScanCache(redact, trusted=not full), CheckCache(redact, trusted=not full), transcript_cache(redact, full)


def save_previewed(scans: ScanCache, checks: CheckCache) -> None:
    """Add what this preview scanned and verified to what the cache files hold now, read again
    (a --full preview read none of it, and a `check` may have saved since): `check` drops the
    entries it no longer needs, a preview reads too little to judge that. An entry is the result
    of its content under the fingerprint, so a fresh one and a stored one are the same. The
    transcript cache is not saved (redacted_now)."""
    for cache in (scans, checks):
        cache.entries = LocalCache(cache.path, cache.fingerprint).entries | cache.entries
        cache.save(keep=set(cache.entries))


def cmd_scan(args: list[str]) -> int:
    """Preview a publish without writing anything: redact each transcript in memory, then report
    what the redactor changed, what it would still change (an error: a rule that is not
    idempotent) and what it leaves for a person to judge. Output is masked, because it lands in
    the transcript of the session that runs it. Only what a transcript gained since its last
    `sync` is redacted, and a log `check` scanned is not scanned again; --full does it all."""
    src, full = claude_project_dir(), full_audit(args)
    args = [a for a in args if a != "--full"]
    named = args not in ([], ["--all"])
    paths = [src / f"{a}.jsonl" for a in args] if named else sorted(src.glob("*.jsonl"))
    redact, errors = Redactor(), 0
    scans, checks, transcripts = preview_caches(redact, full)
    for p in paths:
        for key, path in transcripts_of(p):
            if not named and older_than_stamp(path):
                continue
            name = p.stem if path == p else f"{p.stem} agent {path.stem}"
            raw, data = redacted_now(path, p.stem, key, redact, transcripts)
            found = scans.hits(p.stem, sha256(data), data)
            kinds = Counter(k.decode() for k in re.findall(rb"\[REDACTED:([a-z.\-]+)\]", data))
            print(f"{name}: {len(raw):,} B raw, {len(data):,} B redacted; "
                  + (", ".join(f"{k} {n}" for k, n in kinds.most_common()) if kinds else "no redaction markers"))
            for kind in redact.cached_leaks(found):
                print(f"  ERROR still unredacted after redaction: {kind}")
                errors += 1
            for warning in redact.cached_review(found):
                print(f"  warn  {warning}")
    save_previewed(scans, checks)
    if redact.skipped:
        print(f"left out as reviewed false positives: {_skipped(redact)}")
    return 1 if errors else 0


def _skipped(redact: Redactor) -> str:
    return ", ".join(f"{kind} ×{n}" for kind, n in sorted(redact.skipped.items()))


def texts_to_check(redact: Redactor, everything: bool = False, transcripts: LocalCache | None = None):
    """(session, text) for what a push would publish, plus the tracked files published with it.
    A transcript or log older than the rules' stamp has been checked by them and is left out,
    with whatever it was found to hold, unless `everything` asks for it. With `transcripts`, a
    transcript is redacted only from where its last stored log ends (redacted_now)."""
    for where, _, _, content, _ in scan_targets(redact, everything, transcripts):
        yield where[:8], (content if isinstance(content, bytes) else content()).decode(errors="replace")


def scan_targets(redact: Redactor, everything: bool, transcripts: LocalCache | None,
                 checks: CheckCache | None = None):
    """(session, session or None, SHA-256, content, length) for each text texts_to_check gives, as
    `check` scans it: the second session, for ScanCache.hits, is None for a file that is not a log;
    content is bytes, or for a stored log a function giving them, called only if needed.
    With `checks`, a stored log's .gz bytes verified before are not decompressed to name it."""
    def due(path: Path) -> bool:
        return everything or not older_than_stamp(path)

    for p in sorted(claude_project_dir().glob("*.jsonl")):
        for key, path in transcripts_of(p):
            if due(path):
                data = redacted_now(path, p.stem, key, redact, transcripts)[1] if transcripts is not None \
                    else redact(path.read_text(errors="replace"))
                yield p.stem, p.stem, sha256(data), data, len(data)
    for sid, m in all_manifests().items():
        for sha, info in m.get("logs", {}).items():
            path = log_path(sid, sha)
            if info.get("url") or not path.exists() or not due(path):
                continue
            if checks is None:
                data = load_log(sid, sha)
                yield sid, sid, sha256(data), data, len(data)
            elif (stored := checks.snapshot(path)) is not None:
                actual, size, data, gz = stored
                yield sid, sid, actual, data if data is not None else (lambda gz=gz: decompress(gz)), size
        for path in (summary_path(sid), manifest_path(sid), metrics_path(sid), notes_path(sid), *run_copies(sid)):
            if path.exists():
                yield sid, None, sha256(content := path.read_bytes()), content, len(content)


def open_findings(redact: Redactor, everything: bool = False, values: bool = False,
                  full: bool = False) -> dict[str, dict]:
    """Everything `check` or `scan` would raise now, by id: level, kind, masked value, count and
    where. A text already scanned under these rules (by `check`, `scan` or an earlier call) is
    not scanned again, and a transcript is redacted only from where its last stored log ends;
    --full trusts neither. Each row also has its "value" when it is known, from this scan or the
    last ones (remember_findings); with `values`, every row has it, scanning everything again
    if one is not known. A value is real: never print one unmasked to an agent."""
    scans, checks, transcripts = preview_caches(redact, full)
    skipped = Counter(redact.skipped)
    found: dict[str, dict] = {}
    for where, sid, sha, content, size in scan_targets(redact, everything, transcripts, checks):
        entry, where = scans.hits(sid, sha, content, size), where[:8]
        for level, part in (("ERROR", "leaks"), ("warn", "review")):
            for kind, rows in entry[part].items():
                for fid, (masked, n) in rows.items():
                    if kind not in NEVER_REVIEWED and fid in redact.reviewed:
                        redact.skipped[kind] += n
                        continue
                    row = found.setdefault(fid, {"level": level, "kind": kind, "masked": masked, "count": 0,
                                                 "where": set()})
                    row["count"] += n
                    row["where"].add(where)
    save_previewed(scans, checks)
    known = {fid: (f["kind"], f["value"]) for fid, f in load_findings_cache().items()} | scans.values
    for fid, row in found.items():
        if fid in known and finding_id(*known[fid]) == fid:  # the id names the kind and the value
            row["value"] = known[fid][1]
    if values and any("value" not in row for row in found.values()):
        perf.count("findings scanned again for their values")
        redact.skipped = skipped
        return scanned_findings(redact, everything)
    remember_findings({fid: row for fid, row in found.items() if "value" in row})
    return found


def scanned_findings(redact: Redactor, everything: bool = False) -> dict[str, dict]:
    """open_findings worked out from the texts alone, with every value: no cache is read."""
    found: dict[str, dict] = {}
    for where, _, _, content, _ in scan_targets(redact, everything, None):
        text = content.decode(errors="replace")
        for level, hits in (("ERROR", redact.leak_hits(text)), ("warn", redact.review_hits(text))):
            for kind, values in hits.items():
                for value, n in values.items():
                    row = found.setdefault(finding_id(kind, value), {"level": level, "kind": kind, "masked": _mask(value),
                                                                     "value": value, "count": 0, "where": set()})
                    row["count"] += n
                    row["where"].add(where[:8])
    remember_findings(found)
    return found


def load_findings_cache() -> dict[str, dict]:
    try:
        return json.loads(FINDINGS_CACHE.read_text())
    except (OSError, ValueError):
        return {}


def remember_findings(found: dict[str, dict]) -> None:
    """Keep what a scan found, merged with what earlier scans did, for `allow propose` and
    `allow approve`. The file holds real values, so only its owner can read it."""
    cache = load_findings_cache()
    for fid, f in found.items():
        cache[fid] = {"level": f["level"], "kind": f["kind"], "value": f["value"], "count": f["count"],
                      "where": sorted(f["where"])}
    try:
        atomic_write(FINDINGS_CACHE, json.dumps(cache, ensure_ascii=False), private=True)
    except OSError:
        pass  # a cache: the next propose or approve scans instead


def person_at_terminal() -> bool:
    """A check that an agent's shell fails: it has no terminal, and Claude Code marks its environment."""
    return sys.stdin.isatty() and sys.stdout.isatty() and not os.environ.get("CLAUDECODE")


def save_reviewed(findings: dict[str, dict]) -> None:
    REVIEWED.write_text(json.dumps({"schema": REVIEWED_SCHEMA, "findings": dict(sorted(findings.items()))},
                                   indent=2, ensure_ascii=False) + "\n")


def masked_excerpt(redact: Redactor, line: str, at: int, length: int, reach: int = 80) -> str:
    """The words around a finding, safe for a transcript: every finding in them is masked, and a
    word the cut left partial is dropped, since a piece of a secret no longer looks like one."""
    start, end = max(0, at - reach), at + length + reach
    value = line[at:at + length]
    excerpt = line[start:end]
    if start:
        excerpt = re.sub(r"^\S*\s?", "", excerpt)
    if end < len(line):
        excerpt = re.sub(r"\s?\S*$", "", excerpt)
    # The line is raw JSON: an escape glued to a value, at any depth of quoting, hides it from the
    # rules, which read decoded strings.
    excerpt = re.sub(r'\\+[nrt"]?', " ", excerpt)
    leaks, reviewable = redact.hits_of_line(excerpt)
    for _, hit in sorted(leaks + reviewable + [("", value)], key=lambda hit: -len(hit[1])):
        excerpt = excerpt.replace(hit, _mask(hit))
    return excerpt


def show_finding(prefix: str, limit: int = 4) -> int:
    """Where a finding occurs, masked, so that an agent can help judge it."""
    redact = Redactor()
    found = open_findings(redact, values=True)
    matches = [fid for fid in found if fid.startswith(prefix)]
    if len(matches) != 1:
        print(f"{prefix} matches {len(matches)} open finding(s)", file=sys.stderr)
        return 1
    f = found[matches[0]]
    print(f"{matches[0][:8]}  {f['level']}  {f['kind']}  ×{f['count']}  {f['masked']}  in {', '.join(sorted(f['where']))}")
    excerpts: Counter = Counter()
    for _, text in texts_to_check(redact, transcripts=preview_caches(redact, False)[2]):
        for line in text.splitlines():
            if (at := line.find(f["value"])) >= 0:
                excerpts[masked_excerpt(redact, line, at, len(f["value"]))] += 1
    for excerpt, n in excerpts.most_common(limit):
        print(f"  ×{n}  {excerpt}")
    if len(excerpts) > limit:
        print(f"  and {len(excerpts) - limit} other place(s)")
    return 0


def cmd_stamp(args: list[str]) -> int:
    """After a change to the rules: apply them to everything, then record that, so that the files
    of this moment aren't scanned again. Findings in those files stop being reported at that point.
    An open error refuses the stamp, since it must be fixed or settled first. An open warning does
    not: it goes on the allow list as a proposal, unless it is there already, and `check` warns
    about the proposal until a person approves or drops it. With --equivalent, the rules keep the
    date of their last stamp instead, if they give the same results as the stamped ones."""
    if args == ["--equivalent"]:
        return stamp_equivalent()
    if args not in ([], ["--full"]):
        print("usage: sync.py stamp [--equivalent | --full]", file=sys.stderr)
        return 2
    found = open_findings(Redactor(), everything=True, full=args == ["--full"])
    for fid, f in sorted(found.items()):
        print(f"{fid[:8]}  {f['level']:5}  {f['kind']}  ×{f['count']}  {f['masked']}  in {', '.join(sorted(f['where']))}")
    blocking = {fid for fid, f in found.items() if f["level"] == "ERROR" or f["kind"] not in ALLOWABLE_KINDS}
    if blocking:
        print(f"refused: {len(blocking)} open error(s) would stop being reported; fix or settle them first", file=sys.stderr)
        return 1
    if carried := carry_as_proposals(found):
        print(f"warn  {carried} open warning(s) proposed for the allow list, so they keep warning in `check` "
              f"until a person runs: python3 llm-dlc/tools/sync.py allow approve (or drops them)")
    redaction_rules.write_stamp()
    print(f"stamped {redaction_rules.source_hash()[:12]}")
    return 0


def carry_as_proposals(found: dict[str, dict]) -> int:
    """Propose open warnings that the allow list does not hold yet. A proposal holds no value."""
    entries, added = load_allowlist(), 0
    for fid, f in sorted(found.items()):
        if fid not in entries:
            entries[fid] = {"kind": f["kind"], "masked": f["masked"], "status": "proposed",
                            "reason": f"open when the rules were stamped on {time.strftime('%Y-%m-%d')}; not judged yet",
                            "proposed_by": _who(), "proposed_on": time.strftime("%Y-%m-%d")}
            added += 1
    if added:
        save_allowlist(entries)
    return added


RULES_FILE = "llm-dlc/tools/redaction_rules.py"


def rules_differences(old: redaction_rules.Rules, new: redaction_rules.Rules, lines) -> int:
    """How many of these lines the two sets of rules redact differently, or find different
    findings in, before or after redaction."""
    differ = 0
    for line in lines:
        redacted = new(line)
        out = redacted.decode().rstrip("\n")
        differ += (old(line) != redacted or old.hits_of_line(line) != new.hits_of_line(line)
                   or (out != line and old.hits_of_line(out) != new.hits_of_line(out)))
    return differ


def rules_module(source: str, name: str):
    """The rules module whose source this is, loaded under name, apart from redaction_rules."""
    import types
    module = types.ModuleType(name)
    module.__file__ = f"<{name}>"
    sys.modules[name] = module  # what typing and dataclasses look a class's module up in
    exec(compile(source, f"{name}.py", "exec"), module.__dict__)
    return module


_compared: tuple | None = None  # in a worker of compare_rules: (old rules, new rules)


def _compare_init(old_source: str, new_source: str, inputs: tuple) -> None:
    global _compared
    _compared = (rules_module(old_source, "stamped_rules").Rules(*inputs),
                 rules_module(new_source, "current_rules").Rules(*inputs))


def _compare_worker(lines: list[str]) -> tuple[int, float]:
    start = time.process_time()
    return rules_differences(*_compared, lines), time.process_time() - start


def compare_rules(old_source: str, new_source: str, inputs: tuple, lines, processes: int | None = None) -> int:
    """rules_differences of the rules of the two sources, in one process per CPU (spawned, as
    Redactor's pool is) when there are two or more. Lines go out in batches of about a million
    characters, a few per process at a time, so that memory holds only those in flight."""
    from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
    import multiprocessing
    processes = processes or redactor.pool_processes()
    if processes < 2:
        _compare_init(old_source, new_source, inputs)
        return _compare_worker(list(lines))[0]
    differ, cpu, batches = 0, 0.0, 0

    def batched():
        batch, n = [], 0
        for line in lines:
            batch.append(line)
            n += len(line)
            if n >= 1 << 20:
                yield batch
                batch, n = [], 0
        if batch:
            yield batch

    with ProcessPoolExecutor(processes, mp_context=multiprocessing.get_context("spawn"),
                             initializer=_compare_init, initargs=(old_source, new_source, inputs)) as pool:
        pending: set = set()
        for batch in batched():
            pending.add(pool.submit(_compare_worker, batch))
            batches += 1
            while len(pending) >= 3 * processes:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for f in done:
                    d, c = f.result()
                    differ, cpu = differ + d, cpu + c
        for f in pending:
            d, c = f.result()
            differ, cpu = differ + d, cpu + c
    perf.count("pool processes started", processes)
    perf.count("pool chunks", batches)
    perf.count("pool worker cpu seconds", round(cpu, 3))
    return differ


def _above_stamp(source: str) -> str:
    """The hash redaction_rules.source_hash gives a file with this source."""
    return hashlib.sha256(source[:source.rindex("# --- " + "stamp")].encode()).hexdigest()


def stamp_equivalent(rev: str = "@-") -> int:
    """Keep the last stamp's date for rules whose results are unchanged: the rules committed at
    `rev`, which must carry a valid stamp, and the current ones must redact every line of every
    transcript, stored log and published file the same, and find the same in it. Then the files
    checked under the old stamp are checked under these rules too, and nothing is rescanned.
    Both are compared as source text, the current ones as read from disk now, in a pool; the
    stamp is written only if the file still holds that text when the comparison ends."""
    new_source = Path(redaction_rules.__file__).read_text()
    if _above_stamp(new_source) == redaction_rules.RULES_HASH == redaction_rules.source_hash():
        print("the rules' stamp is valid; nothing to do")
        return 0
    r = jj("file", "show", "-r", rev, RULES_FILE)
    if r.returncode:
        print(f"refused: no {RULES_FILE} at {rev}", file=sys.stderr)
        return 1
    stamped = rules_module(r.stdout, "stamped_rules")
    if stamped.RULES_HASH != _above_stamp(r.stdout):
        print(f"refused: the rules at {rev} are not stamped either; run: python3 llm-dlc/tools/sync.py stamp",
              file=sys.stderr)
        return 1
    inputs = personal_literals()
    seen: set[bytes] = set()

    def lines():
        def distinct(text: str):
            for line in text.splitlines():
                key = hashlib.blake2b(line.encode(errors="replace"), digest_size=16).digest()
                if key not in seen:
                    seen.add(key)
                    yield line
        src = claude_project_dir()
        for p in sorted(src.glob("*.jsonl")):
            subdir = p.parent / p.stem / "subagents"
            for t in [p] + (sorted(subdir.glob("*.jsonl")) if subdir.is_dir() else []):
                yield from distinct(t.read_text(errors="replace"))
        for gz in sorted(TRACES.glob("*/logs/*.jsonl.gz")):
            yield from distinct(gzip.decompress(gz.read_bytes()).decode(errors="replace"))
        for sid in all_manifests():
            for f in (summary_path(sid), manifest_path(sid), metrics_path(sid), notes_path(sid)):
                if f.exists():
                    yield from distinct(f.read_text())
        for f in (REVIEWED, ALLOWLIST):
            if f.exists():
                yield from distinct(f.read_text())

    with perf.phase("compare rules"):
        differ = compare_rules(r.stdout, new_source, inputs, lines())
    if differ:
        print(f"refused: the rules give different results on {differ} of {len(seen)} line(s); "
              f"run: python3 llm-dlc/tools/sync.py stamp", file=sys.stderr)
        return 1
    if redaction_rules.source_hash() != _above_stamp(new_source):
        print(f"refused: {RULES_FILE} changed while it was compared; run this again", file=sys.stderr)
        return 1
    redaction_rules.write_stamp(stamped.RULES_GENERATED)
    print(f"stamped {redaction_rules.source_hash()[:12]}, keeping the date {stamped.RULES_GENERATED}: "
          f"{len(seen):,} distinct lines give the same results under the rules at {rev}")
    return 0


def cmd_review(args: list[str]) -> int:
    """List open findings, masked, or record some as false positives. Listing is open to anyone.
    Accepting is a person's decision, so it shows the real value and asks for it to be confirmed
    at a terminal; an agent is sent back to ask."""
    if args in ([], ["--full"]):
        found = open_findings(Redactor(), full=bool(args))
        proposed = load_allowlist()
        for fid, f in sorted(found.items(), key=lambda kv: (kv[1]["level"], kv[1]["kind"])):
            print(f"{fid[:8]}  {f['level']:5}  {f['kind']}  ×{f['count']}  {f['masked']}  in {', '.join(sorted(f['where']))}"
                  + ("  (proposed for the allow list)" if fid in proposed else ""))
        print(f"{len(found)} open finding(s)")
        return 0
    if args[0] == "show" and len(args) == 2:
        return show_finding(args[1])
    ids = args[1:args.index("--reason")] if "--reason" in args else []
    reason = " ".join(args[args.index("--reason") + 1:]).strip() if "--reason" in args else ""
    if args[0] != "accept" or not ids or not reason:
        print("usage: sync.py review [accept ID... --reason TEXT]", file=sys.stderr)
        return 2
    if not person_at_terminal():
        print("refused: a person must accept findings, from their own terminal. Ask them to run this command.",
              file=sys.stderr)
        return 1
    found = open_findings(Redactor(), values=True)
    chosen = {}
    for prefix in ids:
        matches = [fid for fid in found if fid.startswith(prefix)]
        if len(matches) != 1 or found[matches[0]]["kind"] in NEVER_REVIEWED:
            print(f"cannot accept {prefix}: it matches {len(matches)} open finding(s), or its kind can never be waived",
                  file=sys.stderr)
            return 1
        chosen[matches[0]] = found[matches[0]]
    for fid, f in chosen.items():
        print(f"{fid[:8]}  {f['kind']}  ×{f['count']}  in {', '.join(sorted(f['where']))}\n    {f['value']}")
    if input(f"Reason: {reason}\nType \"{CONFIRMATION}\" to record {len(chosen)} finding(s): ").strip() != CONFIRMATION:
        print("nothing recorded")
        return 1
    reviewed = load_reviewed()
    who = _cmd("git", "config", "--get", "user.name") or "maintainer"
    for fid, f in chosen.items():
        reviewed[fid] = {"kind": f["kind"], "masked": _mask(f["value"]), "reason": reason, "authorized_by": who,
                         "date": time.strftime("%Y-%m-%d")}
    save_reviewed(reviewed)
    print(f"recorded {len(chosen)} finding(s) in {REVIEWED.relative_to(REPO)}; commit it to publish the decision")
    return 0


def reviewed_problems() -> list[str]:
    """The list holds no values, so what can be checked is that each entry says who decided and why."""
    if not REVIEWED.exists():
        return []
    doc = json.loads(REVIEWED.read_text())
    if doc.get("schema") != REVIEWED_SCHEMA:
        return [f"{REVIEWED.name}: unknown schema {doc.get('schema')}"]
    errors = []
    for fid, entry in doc.get("findings", {}).items():
        if not re.fullmatch(r"[0-9a-f]{32}", fid):
            errors.append(f"{REVIEWED.name}: bad id {fid[:12]}")
        if entry.get("kind") in NEVER_REVIEWED:
            errors.append(f"{REVIEWED.name}: {fid[:8]} waives {entry['kind']}, which no review can")
        for field in ("kind", "reason", "authorized_by", "date"):
            if not str(entry.get(field) or "").strip():
                errors.append(f"{REVIEWED.name}: {fid[:8]} has no {field}")
    return errors


def save_allowlist(entries: dict[str, dict]) -> None:
    ALLOWLIST.write_text(json.dumps({"schema": ALLOWLIST_SCHEMA, "entries": dict(sorted(entries.items()))},
                                    indent=2, ensure_ascii=False) + "\n")


def _who() -> str:
    return "agent" if os.environ.get("CLAUDECODE") else _cmd("git", "config", "--get", "user.name") or "maintainer"


def _split_reason(args: list[str]) -> tuple[list[str], str]:
    if "--reason" not in args:
        return args, ""
    at = args.index("--reason")
    return args[:at], " ".join(args[at + 1:]).strip()


def _resolve(prefixes: list[str], pool: dict[str, dict]) -> tuple[dict[str, str], list[str]]:
    """Prefix -> full id for those that name exactly one id in the pool, and those that don't."""
    done, missing = {}, []
    for prefix in prefixes:
        matches = [fid for fid in pool if fid.startswith(prefix)]
        if len(matches) == 1:
            done[prefix] = matches[0]
        else:
            missing.append(prefix)
    return done, missing


def _value_problem(kind: str, value: str, redact: Redactor) -> str | None:
    """Why this value cannot be on the allow list as this kind, if it can't."""
    if kind not in ALLOWABLE_KINDS:
        return (f"{kind} is not a kind the allow list takes ({', '.join(sorted(ALLOWABLE_KINDS))}); "
                f"the redactor removes it from logs, so the list would publish it: use `review accept`")
    leaks, reviewable = redact.hits_of_line(json.dumps(value))
    if leaks:
        return f"it holds {sorted({k for k, _ in leaks})}, which the redactor removes"
    if (kind, value) not in reviewable:
        return f"the rules do not find it as {kind}"
    return None


def cmd_allow(args: list[str]) -> int:
    """The allow list. Listing, proposing and dropping are open to anyone. Approving and adding
    are a person's decision, made at a terminal where they see the real value. None of these
    scans the logs unless a value is not known from the last scan."""
    entries = load_allowlist()
    if not args:
        for fid, e in sorted(entries.items(), key=lambda kv: (kv[1]["status"], kv[1]["kind"])):
            shown = e["value"] if e["status"] == "approved" else e.get("masked", "")
            print(f"{fid[:8]}  {e['status']:8}  {e['kind']}  {shown}  ({e['reason']}; {e['proposed_by']}"
                  + (f", approved by {e['authorized_by']}" if e["status"] == "approved" else "") + ")")
        waiting = sum(e["status"] == "proposed" for e in entries.values())
        print(f"{len(entries) - waiting} approved, {waiting} proposed"
              + ("; a person approves with: python3 llm-dlc/tools/sync.py allow approve" if waiting else ""))
        return 0
    cmd, rest = args[0], args[1:]
    if cmd == "propose":
        ids, reason = _split_reason(rest)
        if not ids or not reason:
            print("usage: sync.py allow propose ID... --reason TEXT", file=sys.stderr)
            return 2
        cache = load_findings_cache()
        done, missing = _resolve(ids, cache)
        if missing:  # not seen by the last scan: scan once
            cache = {fid: {**f, "where": sorted(f["where"])} for fid, f in open_findings(Redactor(), values=True).items()}
            done, missing = _resolve(ids, cache)
        if missing:
            print(f"cannot propose {', '.join(missing)}: no single finding has that id", file=sys.stderr)
            return 1
        redact = Redactor()
        for prefix, fid in done.items():
            f = cache[fid]
            if problem := _value_problem(f["kind"], f["value"], redact):
                print(f"cannot propose {prefix}: {problem}", file=sys.stderr)
                return 1
        for fid in done.values():
            if entries.get(fid, {}).get("status") != "approved":
                entries[fid] = {"kind": cache[fid]["kind"], "masked": _mask(cache[fid]["value"]), "status": "proposed",
                                "reason": reason, "proposed_by": _who(), "proposed_on": time.strftime("%Y-%m-%d")}
        save_allowlist(entries)
        print(f"proposed {len(done)} entr{'y' if len(done) == 1 else 'ies'} in {ALLOWLIST.relative_to(REPO)}; "
              f"they stay open until a person runs: python3 llm-dlc/tools/sync.py allow approve")
        return 0
    if cmd == "drop":
        done, missing = _resolve(rest, entries)
        if not rest or missing:
            print(f"usage: sync.py allow drop ID...; no single entry for {', '.join(missing)}", file=sys.stderr)
            return 1
        for fid in done.values():
            del entries[fid]
        save_allowlist(entries)
        print(f"dropped {len(done)} entr{'y' if len(done) == 1 else 'ies'}")
        return 0
    if cmd not in ("approve", "add"):
        print(__doc__)
        return 2
    no_commit = "--no-commit" in rest
    rest = [a for a in rest if a != "--no-commit"]
    if not person_at_terminal():
        print("refused: a person must approve the allow list, from their own terminal. Ask them to run this command.",
              file=sys.stderr)
        return 1
    redact, today, who = Redactor(), time.strftime("%Y-%m-%d"), _cmd("git", "config", "--get", "user.name") or "maintainer"
    if cmd == "add":
        values, reason = _split_reason(rest)
        kind = values[values.index("--kind") + 1] if "--kind" in values[:-1] else ""
        values = [v for i, v in enumerate(values) if v != "--kind" and (i == 0 or values[i - 1] != "--kind")]
        if len(values) != 1 or not kind or not reason:
            print("usage: sync.py allow add VALUE --kind KIND --reason TEXT", file=sys.stderr)
            return 2
        if problem := _value_problem(kind, values[0], redact):
            print(f"cannot allow it: {problem}", file=sys.stderr)
            return 1
        fid = finding_id(kind, values[0])
        chosen = {fid: {"kind": kind, "masked": _mask(values[0]), "reason": reason, "proposed_by": who,
                        "proposed_on": today, "value": values[0]}}
        print(f"{fid[:8]}  {kind}\n    {values[0]}")
    else:
        proposed = {fid: e for fid, e in entries.items() if e["status"] == "proposed"}
        done, missing = _resolve(rest, proposed) if rest else ({fid: fid for fid in proposed}, [])
        if missing:
            print(f"no single proposal for {', '.join(missing)}", file=sys.stderr)
            return 1
        if not done:
            print("nothing proposed")
            return 0
        cache = load_findings_cache()
        if any(fid not in cache for fid in done.values()):
            print("some values are not known from the last scan; scanning…")
            cache |= {fid: {**f, "where": sorted(f["where"])} for fid, f in open_findings(redact, values=True).items()}
        chosen = {}
        for fid in done.values():
            e = proposed[fid]
            if fid not in cache:
                print(f"{fid[:8]}  {e['kind']}  no longer found anywhere; left as proposed (drop it with `allow drop`)")
                continue
            f = cache[fid]
            problem = ("the cached value does not match the id" if finding_id(e["kind"], f["value"]) != fid
                       else _value_problem(e["kind"], f["value"], redact))
            if problem:
                print(f"{fid[:8]}  {e['kind']}  cannot be approved: {problem}")
                continue
            print(f"{fid[:8]}  {e['kind']}  ×{f['count']}  in {', '.join(f['where'])}  ({e['reason']}; {e['proposed_by']})"
                  f"\n    {f['value']}")
            chosen[fid] = {**e, "value": f["value"]}
        if not chosen:
            return 1
    if input(f"Type \"{CONFIRMATION}\" to allow {len(chosen)} value(s): ").strip() != CONFIRMATION:
        print("nothing recorded")
        return 1
    for fid, e in chosen.items():
        entries[fid] = {**e, "status": "approved", "authorized_by": who, "approved_on": today}
    save_allowlist(entries)
    print(f"allowed {len(chosen)} value(s) in {ALLOWLIST.relative_to(REPO)}. "
          f"Nothing needs rescanning: the next check leaves these values out.")
    if no_commit or not has_jj():
        print("commit it to publish the decision")
        return 0
    return commit_allowlist(chosen, who)


def commit_allowlist(chosen: dict[str, dict], who: str) -> int:
    """Commit a decision just recorded in the allow list, so that it never waits in @ for someone to
    commit it (push refuses uncommitted work). With nothing else changed in @, as `sync.py commit`
    commits, with trace lines and the check after it. With other work in @, the allow list alone,
    by `jj commit PATH`, leaving that work where it was; the next `sync.py commit` adds the trace
    lines. A described @ is left alone: its message belongs to whoever wrote it."""
    path = str(ALLOWLIST.relative_to(REPO))
    lines = [f"{fid[:8]}  {e['kind']}  {e.get('masked') or _mask(e['value'])}: {e['reason']}" for fid, e in chosen.items()]
    summary = f"Allow list: {who} approved {', '.join(fid[:8] for fid in chosen)}"
    body = (f"{who} approved {len(chosen)} value(s) at their terminal with sync.py allow; the command committed "
            "the decision itself.\n\n" + "\n".join(lines))
    others = [p for p in uncommitted_work() if p != path]
    if jj_commits("@")[0]["description"].strip():
        print("@ has a description of its own, so the decision is left there: commit it with `sync.py commit`")
        return 0
    if not others:
        return cmd_commit(["-m", summary, "-m", body])
    r = jj("commit", path, "-m", f"{summary}\n\n{body}")
    if r.returncode:
        print(f"jj commit failed; the decision stays in @:\n{r.stderr}", file=sys.stderr)
        return 1
    print(f"committed {path} alone; {len(others)} other changed path(s) stay in @")
    return 0


def allowlist_problems(redact: Redactor) -> tuple[list[str], list[str]]:
    """(errors, warnings) about the allow list. A proposal must not hold its value, since nobody
    has judged it yet; an approved entry must name a value that its id and kind describe, and
    that the redactor would leave in a log."""
    if not ALLOWLIST.exists():
        return [], []
    doc = json.loads(ALLOWLIST.read_text())
    name = ALLOWLIST.name
    if doc.get("schema") != ALLOWLIST_SCHEMA:
        return [f"{name}: unknown schema {doc.get('schema')}"], []
    errors, waiting = [], 0
    for fid, e in doc.get("entries", {}).items():
        if not re.fullmatch(r"[0-9a-f]{32}", fid):
            errors.append(f"{name}: bad id {fid[:12]}")
        status = e.get("status")
        required = ("kind", "reason", "proposed_by", "proposed_on") + (
            ("value", "authorized_by", "approved_on") if status == "approved" else ())
        errors += [f"{name}: {fid[:8]} has no {field}" for field in required if not str(e.get(field) or "").strip()]
        if status == "proposed":
            waiting += 1
            if "value" in e:
                errors.append(f"{name}: {fid[:8]} is only proposed but holds its value, which nobody has judged yet")
        elif status != "approved":
            errors.append(f"{name}: {fid[:8]} has unknown status {status}")
        elif e.get("value") and e.get("kind"):
            if finding_id(e["kind"], e["value"]) != fid:
                errors.append(f"{name}: {fid[:8]} does not match its kind and value")
            if problem := _value_problem(e["kind"], e["value"], redact):
                errors.append(f"{name}: {fid[:8]}: {problem}")
    warnings = [f"{name}: {waiting} proposed entr{'y awaits' if waiting == 1 else 'ies await'} a person: "
                f"python3 llm-dlc/tools/sync.py allow approve"] if waiting else []
    return errors, warnings


def cmd_commit(args: list[str]) -> int:
    """Finish @ with a message whose trailers match the manifest in its tree, then start a new change."""
    if not args or len(args) % 2 or any(a != "-m" for a in args[::2]) or not args[1].strip():
        print("usage: sync.py commit -m SUMMARY [-m PARAGRAPH ...]", file=sys.stderr)
        return 2
    message = "\n\n".join(a.strip() for a in args[1::2] if a.strip())
    # Describe first: the sync then stamps the trailer onto this message and writes a manifest
    # that lists @ under its real summary, before `jj new` freezes both into the commit.
    with journaled("describe", summary=message.split("\n", 1)[0]):
        if jj("describe", "-r", "@", "-m", message).returncode:
            print("jj describe failed", file=sys.stderr)
            return 1
        redact = cmd_sync([])
        at = jj_commits("@")[0]
        if jj("new").returncode:
            print("jj new failed", file=sys.stderr)
            return 1
    print(f"committed {at['change_id'][:12]}")
    # The check that used to follow every commit, run here on what the commit left: the same one as
    # `sync.py check`, with its caches, so it rescans only what this commit added. The commit stands
    # either way; an error is fixed by a later commit, as before.
    with perf.phase("check"):
        failed = cmd_check([], redact=redact, notes_listed=False)  # LLM_TRACES_FULL=1: trusting no cache
    if failed:
        print(f"the check after commit {at['change_id'][:12]} found errors: fix them and commit the fix", file=sys.stderr)
    return failed


def uncommitted_work() -> list[str]:
    """Paths changed in @ that the trace tools did not write."""
    return [p for p in jj("diff", "--name-only").stdout.splitlines() if not trace_owned(p)]


RECORD_MESSAGE = ("Record session traces\n\nBrings the published traces up to this point: conversation that came "
                  "after a session's last commit, and sessions with no commit of their own.")


def cmd_push(args: list[str]) -> int:
    """Publish everything and leave the repo clean. Whatever the trace tools have to say goes into
    one last commit, which needs no follow-up: nothing is written after the push."""
    if work := uncommitted_work():
        print("uncommitted work in @; commit it first with `sync.py commit`:\n  " + "\n  ".join(work), file=sys.stderr)
        return 1
    with journaled("publish", stage="sync") as step:
        return publish(args, step)


def publish(args: list[str], step: str | None) -> int:
    original = jj_commits("@")[0]["description"]
    described = commit_summary(original) is not None
    if not described:
        jj("describe", "-r", "@", "-m", RECORD_MESSAGE)
    uploads = lambda: {(sid, sha) for sid, m in all_manifests().items() for sha, i in m.get("logs", {}).items() if i.get("url")}
    uploaded = uploads()
    cmd_sync([], publishing=True)
    if cmd_check() != 0:  # before the upload: a log with a leak must not reach the CDN
        print("trace check failed; nothing uploaded", file=sys.stderr)
        return 1
    journal_update(step, stage="upload")
    if cmd_upload(include_at=True) != 0:
        print("log upload failed; not pushing", file=sys.stderr)
        return 1
    journal_update(step, stage="trace record")
    write_index()  # the overview counts uploads
    at = jj_commits("@")[0]["change_id"]
    if any(c["change_id"] == at for m in all_manifests().values() for c in m.get("commits", [])) or uploads() != uploaded:
        jj("new")
        print(f"recorded traces in {at[:12]}")
    else:  # only git SHAs changed: not worth a commit, which would have a new SHA of its own
        jj("restore")
        jj("describe", "-r", "@", "-m", original if described else "")
    journal_update(step, stage="bookmark and push")
    for flag, name in zip(args, args[1:]):
        if flag in ("--bookmark", "-b") and jj("bookmark", "set", name, "-r", "@-").returncode:
            print(f"could not move bookmark {name} to @-", file=sys.stderr)
            return 1
    if cmd_check() != 0:
        print("trace check failed; not pushing", file=sys.stderr)
        return 1
    # The check read the files on disk; what goes out is the revision the bookmarks point at.
    with perf.phase("publication gate"):
        problems = publication_gate(push_revisions(args))
    for p in problems:
        print("ERROR", p)
    if problems:
        print("the revision to push is not the one checked; not pushing", file=sys.stderr)
        return 1
    return subprocess.run([JJ, "--config", "snapshot.max-new-file-size=100MiB", "git", "push", *args], cwd=REPO).returncode


def push_revisions(args: list[str]) -> str:
    """A revset of the commits `jj git push ARGS` would move bookmarks to: the bookmarks, revisions
    and changes it names, all bookmarks for --all, and otherwise every bookmark not already among
    the remote ones' ancestors (more than jj pushes by default, never less)."""
    picked, rest = [], iter(args)
    for a in rest:
        flag, eq, value = a.partition("=")
        if flag in ("--bookmark", "-b", "--revisions", "-r", "--change", "-c") and not eq:
            value = next(rest, "")
        if flag in ("--bookmark", "-b"):
            kind, colon, name = value.partition(":")
            picked.append(f"bookmarks({kind}:{json.dumps(name)})" if colon and kind.isalpha()
                          else f"bookmarks(exact:{json.dumps(value)})")
        elif flag in ("--revisions", "-r", "--change", "-c"):
            picked.append(f"({value})")
        elif a == "--all":
            picked.append("bookmarks()")
    return " | ".join(picked) if picked else "bookmarks() ~ ::remote_bookmarks()"


def git_blob_id(data: bytes, length: int) -> str:
    """The id git gives a file with this content: SHA-1, or SHA-256 in a repository whose object
    ids have 64 digits."""
    return hashlib.new("sha1" if length == 40 else "sha256", b"blob %d\0" % len(data) + data).hexdigest()


def checked_files(manifests: dict[str, dict]) -> dict[str, Path]:
    """The tracked files that `check` reads and scans, by repo path: what a push may publish."""
    paths = [INDEX, TRACES_README, METRICS_ROLLUP, REVIEWED, ALLOWLIST]
    for sid in manifests:
        paths += [manifest_path(sid), summary_path(sid), metrics_path(sid), notes_path(sid), *run_copies(sid)]
    return {str(p.relative_to(REPO)): p for p in paths if p.exists()}


def publication_gate(revset: str) -> list[str]:
    """Errors that make the revisions in `revset` other than what `check` passed: read from git,
    each must hold exactly the trace files on disk, byte for byte, and no other file where trace
    files live; and every log a commit among them or their new ancestors points at must have the
    URL it is published at (or be withdrawn), so a pushed commit never points at a log nobody can
    fetch. Run after `check`, on the revision that is about to be pushed."""
    errors, manifests = [], all_manifests()
    listed = jj("log", "--no-graph", "-r", revset, "-T", 'commit_id ++ "\\n"')
    if listed.returncode:
        return [f"cannot tell what the push would publish from revset {revset}: {listed.stderr.strip()}"]
    targets = listed.stdout.split()
    checked = checked_files(manifests)
    scope = [str(TRACES.relative_to(REPO)), str(SESSION_NOTES.relative_to(REPO)),
             *(str(p.relative_to(REPO)) for p in (INDEX, REVIEWED, ALLOWLIST))]
    for commit in targets:
        r = subprocess.run(["git", "-C", str(REPO), "ls-tree", "-r", "-z", commit, "--", *scope],
                           capture_output=True, timeout=60)
        perf.count("subprocess git ls-tree")
        if r.returncode:
            errors.append(f"commit {commit[:12]}: git cannot list its tree: {r.stderr.decode(errors='replace').strip()}")
            continue
        tree = {}
        for row in filter(None, r.stdout.split(b"\0")):
            meta, path = row.split(b"\t", 1)
            mode, kind, oid = meta.decode().split()
            tree[path.decode()] = (mode, kind, oid)
        for path in sorted(tree.keys() | checked.keys()):
            mode, kind, oid = tree.get(path, (None, None, None))
            if path not in checked:
                errors.append(f"commit {commit[:12]}: {path} is in the revision but was not checked")
            elif oid is None:
                errors.append(f"commit {commit[:12]}: {path} was checked but is not in the revision")
            elif kind != "blob" or mode not in ("100644", "100755") or oid != git_blob_id(checked[path].read_bytes(), len(oid)):
                errors.append(f"commit {commit[:12]}: {path} differs from the copy that was checked")
    if targets:
        for c in jj_commits(f"::({revset}) ~ ::remote_bookmarks()"):
            for sid, sha in TRAILER_RE.findall(c["description"]):
                info = manifests.get(sid, {}).get("logs", {}).get(sha) if sha else None
                if sha and not (info and (info.get("url") == log_url(sid, sha) or info.get("withdrawn"))):
                    errors.append(f"change {c['change_id'][:12]}: points at log {sha[:12]} of {sid}, "
                                  f"which is not uploaded")
    return errors


def check_sessions(manifests: dict[str, dict], redact: Redactor, remote: bool,
                   scans: ScanCache | None = None, checks: CheckCache | None = None) -> tuple[list, list, list, int]:
    """(errors, warnings, notes, logs left out as older than the stamp) for each session's logs,
    files and metrics. A log is scanned by `scans`, which holds only what its content gave before,
    and its .gz bytes, prefixes and metrics are looked up in `checks` by their content: without
    them, every log is decompressed, hashed and scanned in full."""
    errors, warnings, notes, left_out = [], [], [], 0
    scans = scans or ScanCache(redact, path=None)
    checks = checks or CheckCache(redact, path=None)
    for sid, m in manifests.items():
        if m.get("schema") != SCHEMA:
            errors.append(f"{sid}: unknown schema {m.get('schema')}")
            continue
        logs, accepted = m.get("logs", {}), 0
        referenced = {m["log"]["sha256"]} | {s["log"]["sha256"] for s in m.get("subagents", [])}
        referenced |= {c["log_sha256"] for c in m.get("commits", []) if c.get("log_sha256")}
        for sha in sorted(referenced - logs.keys()):
            errors.append(f"{sid}: log {sha[:12]} is referenced but missing from logs")
        # Each stored log is read once and decompressed at most once: not at all when its .gz
        # bytes were verified before. Of the current one the .gz bytes are kept, for the metrics
        # and the prefix check; of the others only the length, once shown to match their name.
        current_sha, current_gz, verified, actual_of, loaded = m["log"]["sha256"], None, {}, {}, []
        for sha, info in logs.items():
            url = info.get("url")
            if url and url != log_url(sid, sha):
                errors.append(f"{sid}: URL of log {sha[:12]} does not match its sha256: {url}")
            elif url and remote and not remote_matches(url, sha):
                errors.append(f"{sid}: CDN does not serve log {sha[:12]} at {url}")
            stored = checks.snapshot(log_path(sid, sha))
            if stored is None:
                if info.get("withdrawn"):
                    notes.append(f"{sid}: log {sha[:12]} was withdrawn ({info['withdrawn']})")
                elif not url:
                    errors.append(f"{sid}: log {sha[:12]} is neither stored locally nor uploaded")
                continue
            actual, size, data, gz = stored
            actual_of[sha] = actual
            if sha == current_sha:
                current_gz = gz
                loaded = [data] if data is not None else []  # decompressed already: kept
            if actual == sha:
                verified[sha] = size
            else:
                errors.append(f"{sid}: log {sha[:12]} content does not match its name")
            if older_than_stamp(log_path(sid, sha)):
                left_out += 1
                continue
            # by what it holds, not by its name; decompressed only if it is scanned
            found = scans.hits(sid, actual, data if data is not None else (lambda gz=gz: decompress(gz)), size)
            if leaks := redact.cached_leaks(found):
                # A log that is not public yet is an error. One that is cannot be fixed, only
                # withdrawn, and whether that is worth it is a person's call: a warning until
                # they have made it, then a note.
                if not url:
                    errors.append(f"{sid}: unredacted {leaks} in log {sha[:12]}")
                elif sha[:12] in ACCEPTED_LOGS:
                    accepted += 1
                else:
                    warnings.append(f"{sid}: published log {sha[:12]} has unredacted {leaks} and is not reviewed: "
                                    f"withdraw it with unpublish --reason, or add it to ACCEPTED_LOGS in sync.py")
            if not url:  # not public yet: what a person should look at before pushing
                warnings += [f"{sid}: log {sha[:12]}: {w}" for w in redact.cached_review(found)]
            del data, gz  # one log in memory at a time, besides the current one's .gz bytes
        if not summary_path(sid).exists():
            errors.append(f"{sid}: summary.md is missing (run: python3 llm-dlc/tools/sync.py sync {sid})")
        for path in (summary_path(sid), manifest_path(sid), metrics_path(sid), notes_path(sid)):  # committed, so published
            if path.exists() and (leaks := redact.cached_leaks(scans.hits(None, sha256(content := path.read_bytes()), content))):
                errors.append(f"{sid}: unredacted {leaks} in {path.relative_to(REPO)}")
        for path in run_copies(sid):  # a loop's record, redacted: like a log not yet published
            found = scans.hits(None, sha256(content := path.read_bytes()), content)
            if leaks := redact.cached_leaks(found):
                errors.append(f"{sid}: unredacted {leaks} in {path.relative_to(REPO)}")
            warnings += [f"{sid}: {path.relative_to(REPO)}: {w}" for w in redact.cached_review(found)]
        def content() -> bytes:
            """The current log, decompressed once and only if something needs it."""
            if not loaded:
                loaded.append((decompress(current_gz) if current_gz is not None else load_log(sid, current_sha)) or b"")
            return loaded[0]

        present = current_gz is not None or (current_sha not in logs and log_path(sid, current_sha).exists())
        # The inputs of the metrics by content: known only when every log they read was verified here.
        inputs = [actual_of.get(current_sha)] + [actual_of.get(s["log"]["sha256"]) if s["log"]["sha256"] in logs
                                                 else "unverified" for s in m.get("subagents", [])]
        with perf.phase("metrics"):
            found_errors, found_warnings = metrics_problems(sid, m, content if present else None, redact, checks,
                                                            inputs if current_gz is not None and "unverified" not in inputs else None)
        errors += found_errors
        warnings += found_warnings
        # Logs are append-only: every log a commit points at should be a prefix of the current one.
        # A verified log is one when the current log's first as many bytes have its hash.
        pointed = {c["log_sha256"] for c in m.get("commits", []) if c.get("log_sha256")}
        lengths = {verified[sha] for sha in pointed if sha in verified}
        if current_gz is not None:
            digests = checks.prefix_digests(actual_of[current_sha], content, lengths)
        else:
            with perf.phase("prefixes"):
                digests = prefix_digests(content(), lengths)
        rewritten = {sha for sha in pointed if sha in verified and verified[sha] and digests.get(verified[sha]) != sha}
        with perf.phase("prefixes"):
            rewritten |= {sha for sha in pointed - verified.keys()  # unlisted or not matching its name: compare bytes
                          if (old := load_log(sid, sha)) and not content().startswith(old)}
        if rewritten:
            notes.append(f"{sid}: {len(rewritten)} older log(s) are not a prefix of the current log, "
                         f"as after a redaction policy change")
        if accepted:
            notes.append(f"{sid}: {accepted} published log(s) have findings that were reviewed and accepted")
    return errors, warnings, notes, left_out


def check_trailers(manifests: dict[str, dict]) -> tuple[list, list]:
    """(errors, notes) for every commit with a trace trailer: its session and log are known, and
    the manifest committed with it names the same log."""
    errors, notes = [], []
    if not has_jj():
        return errors, notes
    traced = jj_commits(f'description(substring:"{TRAILER}:")')
    paths = lambda sid: (str(manifest_path(sid).relative_to(REPO)), *(f"{d}/{sid}/manifest.json" for d in LEGACY_TRACES))
    with perf.phase("read trees"):
        files = tree_files([(c["commit_id"], path) for c in traced for sid, sha in TRAILER_RE.findall(c["description"])
                            if sha and sid in manifests and sha in manifests[sid].get("logs", {}) for path in paths(sid)])
    for c in traced:
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
                found = next((f for path in paths(sid) if (f := files[c["commit_id"], path]) is not None), None)
                tree_sha = json.loads(found).get("log", {}).get("sha256") if found is not None else None
                if tree_sha != sha:
                    notes.append(f"{where}: trailer log {sha[:12]} != manifest-in-tree log "
                                 f"{(tree_sha or 'none')[:12]} (committed without trace-commit)")
    return errors, notes


def tree_files(wanted: list[tuple[str, str]]) -> dict[tuple[str, str], bytes | None]:
    """The content of each (commit SHA, path) in the repository, None where the commit has no such
    file: what `jj file show -r COMMIT PATH` prints, read for all of them by one `git cat-file
    --batch` from the colocated git store. A commit git does not have (or no git at all) is read
    with jj instead."""
    wanted = list(dict.fromkeys(wanted))
    commits = list(dict.fromkeys(c for c, _ in wanted))
    out: dict[tuple[str, str], bytes | None] = {}
    names = [f"{c}^{{commit}}" for c in commits] + [f"{c}:{path}" for c, path in wanted]
    try:
        started = time.perf_counter()
        r = subprocess.run(["git", "-C", str(REPO), "cat-file", "--batch"], input="".join(n + "\n" for n in names).encode(),
                           capture_output=True, timeout=120)
        perf.count("subprocess git cat-file")
        perf.count("subprocess git cat-file seconds", time.perf_counter() - started)
        replies, at = [], 0
        if r.returncode == 0:
            for _ in names:  # "<oid> <type> <size>\n<content>\n", or "<name> missing\n" and the like
                eol = r.stdout.index(b"\n", at)
                header = r.stdout[at:eol].split(b" ")
                if len(header) == 3 and re.fullmatch(rb"[0-9a-f]{40,64}", header[0]) and header[2].isdigit():
                    size = int(header[2])
                    replies.append((header[1].decode(), r.stdout[eol + 1:eol + 1 + size]))
                    at = eol + 1 + size + 1
                else:
                    replies.append((None, None))
                    at = eol + 1
    except (OSError, ValueError, subprocess.SubprocessError):
        replies = []
    if len(replies) == len(names):
        present = {c for c, (kind, _) in zip(commits, replies) if kind == "commit"}
        for (c, path), (kind, data) in zip(wanted, replies[len(commits):]):
            if c in present:
                out[c, path] = data if kind == "blob" else None
    for c, path in wanted:
        if (c, path) not in out:
            r = jj("file", "show", "-r", c, path)
            out[c, path] = r.stdout.encode() if r.returncode == 0 else None
    return out


def check_global_files(manifests: dict[str, dict], redact: Redactor) -> list[str]:
    """Errors in the files generated over all sessions, and in the review lists."""
    errors = []
    if INDEX.exists() and {r["session_id"] for r in json.loads(INDEX.read_text())["sessions"]} != set(manifests):
        errors.append("llm-dlc/index.json does not list exactly the sessions in llm-dlc/traces (run sync)")
    if not TRACES_README.exists() or TRACES_README.read_text() != render_traces_readme(manifests):
        errors.append("llm-dlc/traces/README.md does not match the manifests (run sync)")
    if not METRICS_ROLLUP.exists() or METRICS_ROLLUP.read_text() != render_rollup(manifests):
        errors.append("llm-dlc/traces/metrics.json does not match the session metrics (run sync)")
    for listed in (REVIEWED, ALLOWLIST):
        if listed.exists() and (leaks := redact.leaks(listed.read_text())):
            errors.append(f"unredacted {leaks} in {listed.relative_to(REPO)}")
    return errors


def cmd_check(args: list[str] = (), redact: Redactor | None = None, notes_listed: bool = True) -> int:
    """Everything published or about to be, checked. Logs already scanned with these rules and
    tools are not scanned again (ScanCache), and .gz bytes already verified are not decompressed
    again (CheckCache); --full does all of it again, trusting no earlier result. `commit` runs it
    with notes_listed off: the notes are only counted, since they need no action."""
    remote, full = "--remote" in args, full_audit(args)
    redact, errors, notes, warnings = redact or Redactor(), [], [], []
    scans, checks = ScanCache(redact, trusted=not full), CheckCache(redact, trusted=not full)
    errors += reviewed_problems()
    found_errors, found_warnings = allowlist_problems(redact)
    errors += found_errors
    warnings += found_warnings
    manifests = all_manifests()
    with perf.phase("sessions"):
        found_errors, found_warnings, found_notes, left_out = check_sessions(manifests, redact, remote, scans, checks)
    scans.save()
    checks.save()
    errors += found_errors
    warnings += found_warnings
    notes += found_notes
    with perf.phase("trailers"):
        found_errors, found_notes = check_trailers(manifests)
    errors += found_errors
    notes += found_notes
    with perf.phase("global files"):
        errors += check_global_files(manifests, redact)
    with perf.phase("run records"):
        notes += run_notes(redact)
    if unsent := hook_unsent(older_than=HOOK_GRACE):
        # One warning and one command for them all: `sync.py langfuse` takes several sessions.
        since = ", ".join(f"{sid} since {when}" for sid, when in unsent)
        warnings.append(f"Langfuse may be missing turns of {len(unsent)} session(s) whose end-of-turn hook has not "
                        f"finished a send ({since}); with Langfuse up, run: python3 llm-dlc/tools/sync.py langfuse "
                        + " ".join(sid for sid, _ in unsent))
    if redact.skipped:
        notes.append(f"left out as reviewed false positives: {_skipped(redact)}")
    if redaction_rules.RULES_HASH != redaction_rules.source_hash():
        notes.append("the redaction rules changed since their stamp, so every file was scanned; "
                     "run: python3 llm-dlc/tools/sync.py stamp")
    elif left_out:
        notes.append(f"{left_out} log(s) older than the rules' stamp of {redaction_rules.RULES_GENERATED} were not "
                     f"scanned: they count as checked, and any findings in them are not reported")
    for n in notes if notes_listed else ():
        print("note ", n)
    for w in warnings:
        print("warn ", w)
    for e in errors:
        print("ERROR", e)
    print(f"{len(manifests)} session(s): {len(errors)} error(s), {len(warnings)} warning(s) for a person to judge, "
          f"{len(notes)} note(s) needing no action{'' if notes_listed or not notes else ' (sync.py check lists them)'}")
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
    cmd = argv[0] if argv else ""
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, _terminated)
    try:
        with perf.phase(cmd or "help"):
            if cmd not in LOCKING:
                return run(cmd, argv[1:])
            with Operation(cmd, exclusive=LOCKING[cmd] == "exclusive"):
                return run(cmd, argv[1:])
    finally:
        # The hooks run after every tool call and turn; only the runs that did something are kept.
        if cmd != "perf" and not (cmd.startswith("hook") and perf.phases.get(cmd, [0, 0])[1] < 0.5):
            save_perf(cmd)


def run(cmd: str, args: list[str]) -> int:
    if cmd == "hook":
        cmd_hook()
    elif cmd == "hook-commit":
        cmd_hook_commit()
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
        if set(args) - {"--remote", "--full"}:
            print("usage: sync.py check [--remote] [--full]", file=sys.stderr)
            return 2
        return cmd_check(args)
    elif cmd == "scan":
        return cmd_scan(args)
    elif cmd == "review":
        return cmd_review(args)
    elif cmd == "allow":
        return cmd_allow(args)
    elif cmd == "stamp":
        return cmd_stamp(args)
    elif cmd == "langfuse":
        return cmd_langfuse(args)
    elif cmd == "perf":
        return cmd_perf(args)
    elif cmd == "init":
        cmd_init()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

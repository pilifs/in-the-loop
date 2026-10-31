#!/usr/bin/env python3
"""Publish Claude Code session traces for this repo.

Layout (llm-dlc/specification.md has the full spec, llm-dlc/README.md the procedure):

  llm-dlc/index.json                                 checked in: one row per session, for lookups
  llm-dlc/traces/README.md                           checked in: every session added up (llm-dlc/traces-readme-template.md)
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
  sync.py hook                  Claude Code Stop/SessionEnd hook: Langfuse only, leaves the repo alone
  sync.py hook-commit           Claude Code PostToolUse hook: traces a plain `jj commit` or `git commit`
  sync.py sync [--all | ID...]  snapshot sessions of this repo from ~/.claude/projects
  sync.py commit -m MSG [-m ..] finish @ with trailers matching its manifest (alias: jj trace-commit);
                                each -m is one paragraph, as in git
  sync.py upload                upload logs that commits point at to the CDN, verify, record URLs
  sync.py push [JJ PUSH ARGS]   record outstanding traces in a last commit, upload, check, then `jj git push`,
                                moving any --bookmark to it; leaves @ empty (alias: jj trace-push)
  sync.py check [--remote]      verify hashes, trailers and redaction (--remote: re-download uploads)
  sync.py scan [--all | ID...]  preview a publish: what the redactor changed and what it left to judge
  sync.py unpublish SID SHA [--reason TEXT]
                                delete one log from R2 and purge it from the CDN cache (for leaks);
                                with a reason, record the log as withdrawn in the manifest
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
import socket
import string
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
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
SESSION_NOTES = CHANGES / "session-notes"
TRACES_README = TRACES / "README.md"
TRACES_README_TEMPLATE = CHANGES / "traces-readme-template.md"
INDEX_SCHEMA = "llm-trace-index/v1"
LANGFUSE_ENV = CHANGES / "infra" / "langfuse" / ".env"
STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "llm-traces"
EXTRA_REDACTIONS = Path.home() / ".config" / "llm-traces" / "redact.txt"
# Cloudflare API token with Zone:Read and Cache Purge on the CDN zone; only `unpublish` uses it.
PURGE_TOKEN = Path.home() / ".config" / "llm-traces" / "cloudflare-token"
SCHEMA = "llm-trace-manifest/v1"
REDACTION_POLICY = 4           # bump when redaction changes the bytes it produces
REDACT_KEYS = {"organizationUuid", "accountUuid", "userID"}  # account identifiers Claude Code records
# Wrangler keeps its OAuth tokens here; the spec forbids printing them, redaction removes them anyway.
WRANGLER_CONFIGS = (Path.home() / ".config" / ".wrangler" / "config" / "default.toml",
                    Path.home() / ".wrangler" / "config" / "default.toml")
# Email addresses that are public by design or placeholders; every other address is redacted.
PUBLIC_EMAILS = ("@example.com", "@example.org", "@users.noreply.github.com", "noreply@github.com",
                 "noreply@anthropic.com", "git@github.com", "@langfuse.local", "@localhost")
# Published logs (SHA-256 prefixes) whose findings a person reviewed and left up, so `check` does
# not raise them again. Listed by hash, not by policy: when a new policy flags other published
# logs, nobody has reviewed those yet, and they should warn. See the specification's history note.
ACCEPTED_LOGS = frozenset({
    "2315687ce7e9", "2ed48e0ccf0e", "3f9d33960b46", "4e5d02bfeb4c", "5026337d0f66", "5ec7a7c2be3b", "7fe45409baf7",
    "9aa1dc1182d6", "9b6989b99898", "ad2f8907be5d", "c57cac191c00", "d0d9da508c7a", "dbfac310a6e0",
})
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


# --------------------------------------------------------------------------- redaction

# Credential formats that are recognisable on sight, applied after the personal literals.
# An entry is (kind, pattern), replaced by "[REDACTED:<kind>]", or (kind, pattern, replacement)
# when part of the match must survive: the key of a KEY=VALUE pair, the user of a URL.
# Patterns never match their own replacement, so redaction is idempotent and `leaks` can
# run the same rules over a finished log.
SECRET_PATTERNS = [
    ("anthropic-key", r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    ("langfuse-key", r"[ps]k-lf-[A-Za-z0-9\-]{16,}"),
    ("api-key", r"\bsk-[A-Za-z0-9_\-]{20,}"),  # OpenAI and other sk- keys
    ("github-token", r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    ("gitlab-token", r"\bglpat-[A-Za-z0-9_\-]{20,}"),
    ("aws-key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("google-key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    ("google-oauth", r"\bya29\.[0-9A-Za-z_\-]{20,}"),
    ("slack-token", r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"),
    ("slack-webhook", r"https://hooks\.slack\.com/services/[A-Za-z0-9/]+"),
    ("discord-webhook", r"https://(?:[a-z]+\.)?discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_\-]+"),
    ("npm-token", r"\bnpm_[A-Za-z0-9]{36}\b"),
    ("huggingface-token", r"\bhf_[A-Za-z0-9]{30,}\b"),
    ("stripe-key", r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{20,}"),
    ("sendgrid-key", r"\bSG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}"),
    ("jwt", r"\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),
    ("private-key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----"),
    ("bearer", r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}"),
    ("basic-auth", r"(?i)(authorization[\"']?\s*[:=]\s*[\"']?basic\s+)[A-Za-z0-9+/]{16,}={0,2}",
     r"\1[REDACTED:basic-auth]"),
    # Credentials in URLs and curl arguments: scheme://user:password@host, -u user:password
    ("url-password", r"\b([a-z][a-z0-9+.\-]*://[^/\s:@\"'\\]+):([^@\s/\"'\\\[\$<{%][^@\s/\"'\\]*)@",
     r"\1:[REDACTED:url-password]@"),
    ("curl-user", r"((?:^|\s)(?:-u|--user)[ =])(?![\[\$])([^\s:\"']+:[^\s\"']+)", r"\1[REDACTED:curl-user]"),
    # Account identifiers inside strings (a transcript or ~/.claude.json echoed by a tool),
    # where the structural rule in _scrub cannot see the key.
    ("account-id", r"((?:accountUuid|organizationUuid|userID)\\*[\"']?\s*[:=]\s*\\*[\"']?)([0-9A-Fa-f\-]{32,64})",
     r"\1[REDACTED:account-id]"),
    # KEY=VALUE and "key": "value" pairs whose key says it is a secret: .env files, shell exports,
    # YAML, JSON. Templates (${VAR}, <placeholder>, {{ }}), ${VAR:-defaults}, expressions, paths,
    # flags and short values are left.
    ("env-secret", r"(?i)(\b[A-Z0-9_]*(?:PASSWORD|PASSWD|PASSPHRASE|SECRET|TOKEN|CREDENTIALS?|"
                   r"(?:SECRET|PRIVATE|API|ACCESS|ENCRYPTION|SIGNING|AUTH|LICENSE|SSH)[_-]?KEY|APIKEY|_AUTH|AUTHORIZATION)"
                   r"[\"']?\s*[=:]\s*[\"']?)(?![\[\$<{%(\-~/])([^\s\"'`()\[\]{}<>,;]{8,})(?=$|[\s\"'`)\]}>,;])",
     r"\1[REDACTED:env-secret]"),
]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}(?![A-Za-z0-9\-])")
# Windows account names in paths seen from WSL: /mnt/c/Users/<name>, C:\Users\<name>.
WIN_USER_RE = re.compile(r"((?:/mnt/[A-Za-z]/Users/|[A-Za-z]:\\+Users\\+)(?:[^/\\\s\"'<>|]+))")
WIN_SHARED = {"public", "default", "default user", "all users", "user", "desktop.ini"}

# Findings the redactor does not act on, for a person to judge before a push (`scan`, `check`).
# Each is (kind, pattern, keep): keep(match) says whether the match is worth a warning.
_RESERVED_IP = re.compile(r"^(?:0\.|10\.|127\.|169\.254\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\."
                          r"|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.|22[4-9]\.|2[3-5]\d\."
                          r"|1\.1\.1\.1$|1\.0\.0\.1$|8\.8\.[48]\.[48]$|9\.9\.9\.9$|255\.)")
# A four-part version looks exactly like an IP address, so only its surroundings tell them apart:
# `openjdk version "...`, `java.base@...` (not any `@`: root@<ip> must still warn), or an SDK
# listing whose row goes on to an identifier such as `| ...-graalce`.
VERSION_BEFORE = re.compile(r"(?i)(?:\b(?:version|ver\.?|openjdk|jdk|javac?|adoptium|temurin|corretto|graalvm(?: ce)?)"
                            r"|\b(?:java|jdk)\.[a-z.]+@)[\s\"'=:_\-]*$")
VERSION_AFTER = re.compile(r"\s*\|\s*[\d.]+(?:\+\d+)?-[a-z]")
REVIEW_PATTERNS = [
    ("public-ip",r"(?<![\w.\-+])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\w.\-+])",
     lambda s: not _RESERVED_IP.match(s)),
    ("ipv6", r"(?<![\w:.])(?:[0-9a-fA-F]{1,4}:){5,7}[0-9a-fA-F]{1,4}(?![\w:])",
     lambda s: s.strip("0:") and not s.lower().startswith(("fe80:", "fd", "fc", "::1", "2001:db8:"))),
    ("mac-address", r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b", lambda s: s.lower() != "00:00:00:00:00:00"),
    ("other-home-dir", r"(?<![\w.])/(?:home|Users)/(?!user\b)[A-Za-z][\w.\-]*", lambda s: True),
    ("auth-header", r"(?i)\b(?:authorization|cookie|set-cookie|x-api-key|proxy-authorization)[\"']?\s*[:=]\s*[\"']?[^\s\"']{8,}",
     lambda s: "[REDACTED" not in s),
    # Long mixed-case strings with digits: API keys of unknown formats, base64 blobs. Hashes
    # (hex, lower case) and UUIDs do not match; integrity hashes, file paths and embedded images
    # (base64 PNG, JPEG, GIF, PDF, WEBP, or anything over 1000 characters) are skipped.
    ("long-token", r"(?<![\w/+=\-])(?!sha(?:1|256|384|512)-)(?=[A-Za-z0-9+/_\-]*\d)(?=[A-Za-z0-9+/_\-]*[a-z])"
                   r"(?=[A-Za-z0-9+/_\-]*[A-Z])[A-Za-z0-9+/_\-]{40,}={0,2}(?![\w/+=\-])",
     lambda s: len(s) < 1000 and not s.startswith(("iVBORw0KGgo", "/9j/", "R0lGOD", "JVBERi0", "UklGR"))
     and ("/" not in s or "+" in s or s.endswith("="))),
]
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


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


def _is_version(m: re.Match) -> bool:
    """Whether an address-shaped match is a version number, judged by the text around it."""
    return bool(VERSION_BEFORE.search(m.string, max(0, m.start() - 40), m.start())
                or VERSION_AFTER.match(m.string, m.end()))


def _mask(s: str) -> str:
    """Enough of a finding to recognise it, not enough to repeat it: scan output lands in transcripts."""
    return s if len(s) <= 4 else s[:3] + "…" + s[-2:] + f" ({len(s)} chars)" if len(s) > 12 else s[:2] + "…" + s[-1]


class Redactor:
    def __init__(self) -> None:
        pairs, user = personal_literals()
        self.literals = [(kind, re.compile(rf"(?<![A-Za-z0-9]){re.escape(lit)}(?![A-Za-z0-9])" if kind == "hostname"
                                           else re.escape(lit), flags), rep)
                         for lit, rep, flags, kind in pairs]
        # Also match right after a literal backslash-n/t/r: JSON echoed inside a tool result
        # keeps its escapes, so there is no word boundary before the name.
        self.user_re = (re.compile(rf"(?:(?<=\\[nrt])|(?<![A-Za-z0-9_])){re.escape(user)}\b")
                        if len(user) >= 3 else None)
        self.secret_res = [(p[0], re.compile(p[1], re.S), p[2] if len(p) > 2 else f"[REDACTED:{p[0]}]")
                           for p in SECRET_PATTERNS]
        self.review_res = [(kind, re.compile(pattern), keep) for kind, pattern, keep in REVIEW_PATTERNS]

    @staticmethod
    def _public_email(address: str) -> bool:
        return address.lower().endswith(PUBLIC_EMAILS)

    @staticmethod
    def _win_user(m: re.Match) -> str:
        path = m.group(1)
        prefix, name = re.match(r"(.*[/\\])([^/\\]*)$", path).groups()
        return path if name.lower() in WIN_SHARED else prefix + "user"

    def string(self, text: str) -> str:
        for _kind, rx, rep in self.literals:
            text = rx.sub(lambda _m, r=rep: r, text)
        for _kind, rx, rep in self.secret_res:
            text = rx.sub(rep, text)
        text = EMAIL_RE.sub(lambda m: m.group(0) if self._public_email(m.group(0)) else "[REDACTED:email]", text)
        text = WIN_USER_RE.sub(self._win_user, text)
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

    def leaks(self, text: str) -> list[str]:
        """Kinds of thing the redactor would still change in this text. Empty for its own output."""
        found: set[str] = set()

        def scan(s: str) -> str:
            found.update(kind for kind, rx, _ in self.literals if rx.search(s))
            found.update(kind for kind, rx, _ in self.secret_res if rx.search(s))
            if any(not self._public_email(m.group(0)) for m in EMAIL_RE.finditer(s)):
                found.add("email")
            if WIN_USER_RE.sub(self._win_user, s) != s:
                found.add("windows-user")
            if self.user_re and self.user_re.search(s):
                found.add("username")
            return s

        for line in text.splitlines():
            try:
                obj = json.loads(line)
            except ValueError:
                scan(line)
                continue
            _walk(obj, scan)
            if _unscrubbed(obj):
                found.add("account-id")
        return sorted(found)

    def review(self, text: str) -> list[str]:
        """Warnings for a person: things that may identify someone or something and that no rule
        removes, masked, with counts. Public IPs, foreign home directories, unknown token formats."""
        hits: dict[str, Counter] = {}

        def scan(s: str) -> str:
            s = ANSI_RE.sub("", s)  # colour codes glue digits onto the words they precede
            for kind, rx, keep in self.review_res:
                for m in rx.finditer(s):
                    if keep(m.group(0)) and not (kind == "public-ip" and _is_version(m)):
                        hits.setdefault(kind, Counter())[m.group(0)] += 1
            return s

        for line in text.splitlines():
            try:
                _walk(json.loads(line), scan)
            except ValueError:
                scan(line)
        return [f"{kind} ×{sum(c.values())}: " + ", ".join(_mask(v) for v, _ in c.most_common(3))
                + (f", +{len(c) - 3} more" if len(c) > 3 else "") for kind, c in sorted(hits.items())]


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
        if log_path(sid, sha).exists():
            entry.update(log_info(sid, sha))
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
    TRACES_README.write_text(render_traces_readme())


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


def render_traces_readme() -> str:
    """llm-dlc/traces/README.md: every session added up. It is a function of the manifests and the
    session notes alone, so a sync rewrites it identically and `check` can tell when it is stale."""
    manifests = {sid: m for sid, m in all_manifests().items() if m.get("schema") == SCHEMA}
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


def upload_log(sid: str, sha: str, redact: Redactor) -> str:
    """Put one log in R2 (unless the CDN already serves it) and prove the CDN returns those bytes.
    The log is scanned first: nothing the current redactor would change may go public."""
    url = log_url(sid, sha)
    if remote_matches(url, sha):
        return url
    path = log_path(sid, sha)
    if not path.exists():
        raise FileNotFoundError(f"log {sha[:12]} of {sid} is neither stored locally nor on the CDN")
    data = gzip.decompress(path.read_bytes()).decode(errors="replace")
    if leaks := redact.leaks(data):
        raise RuntimeError(f"refusing to upload log {sha[:12]} of {sid}: unredacted {leaks}")
    for warning in redact.review(data):
        print(f"warn  {sid[:8]}/{sha[:12]}: {warning}")
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


def cmd_upload(include_at: bool = False) -> int:
    """Upload every log a commit points at (and subagent logs), then record the URLs."""
    failed, redact = 0, Redactor()
    # @'s log can still be replaced; upload it only when @ is about to be frozen (include_at).
    at = jj_commits("@")[0]["change_id"] if has_jj() and not include_at else None
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
                logs.setdefault(sha, {})["url"] = upload_log(sid, sha, redact)
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


# --------------------------------------------------------------------------- commands

def process(transcript: Path, redact: Redactor, status: str, live: bool, current: bool,
            publishing: bool = False) -> dict:
    """Bring a session's tracked files up to date. live: the last turn may be unfinished (Langfuse
    waits for it). current: the session is the one running now, so @ is its working copy.
    publishing: @ is a trace record, which carries every session with log no commit points at yet."""
    known = {c.get("log_sha256") for c in load_manifest(transcript.stem).get("commits", [])}
    sid, m, entries = sync_session(transcript, redact, status)
    if publishing:
        current = bool(m["stats"]["turns"]) and m["log"]["sha256"] not in known
    if has_jj():
        link_commits(sid, m, current, publishing)
    finalize_logs(sid, m)
    render_summary(sid, m, entries, redact.string(str(REPO)))
    write_index()
    try:
        export_langfuse(sid, entries, m, live)
    except OSError as e:  # Langfuse down: those turns are retried next time
        log(f"langfuse export deferred for {sid}: {e}")
    return m


def cmd_hook() -> None:
    """Stop and SessionEnd: send finished turns to Langfuse, and leave the repo alone. A transcript
    is kept on disk until a commit or a push records it, so nothing depends on this running."""
    try:
        payload = json.load(sys.stdin)
        transcript, redact = Path(payload["transcript_path"]), Redactor()
        entries = read_jsonl(redact(transcript.read_text(errors="replace")))
        m = {**load_manifest(transcript.stem), **summarize(entries, redact.string(str(REPO)))}
        export_langfuse(transcript.stem, entries, m, live=False)
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
        changed = jj("diff", "--name-only").stdout.splitlines()
        if any(trace_owned(p) for p in changed):
            return  # rewriting the commit below would conflict; the next sync stamps it instead
        jj("edit", parents[0]["change_id"])  # abandons @ if it is empty and has no message
        try:
            process(transcript, Redactor(), "open", live=False, current=True)
        finally:
            jj("edit", at["change_id"]) if changed or at["description"] else jj("new")
    except Exception:
        log(traceback.format_exc())


def cmd_sync(args: list[str], publishing: bool = False) -> None:
    src = claude_project_dir()
    paths = sorted(src.glob("*.jsonl")) if args in ([], ["--all"]) else [src / f"{a}.jsonl" for a in args]
    redact = Redactor()
    for p in paths:
        live = time.time() - p.stat().st_mtime < LIVE_SECONDS
        m = process(p, redact, "open" if live else "ended", live, current=live, publishing=publishing)
        s = m["stats"]
        print(f"{m['session_id']}  {s['turns']} turns  {s['tool_calls']} tools  log sha256:{m['log']['sha256'][:12]}… "
              f"{m['log']['bytes']:,} B  commits: {len(m['commits'])}{'  (live)' if live else ''}")


def cmd_scan(args: list[str]) -> int:
    """Preview a publish without writing anything: redact each transcript in memory, then report
    what the redactor changed, what it would still change (an error: a rule that is not
    idempotent) and what it leaves for a person to judge. Output is masked, because it lands in
    the transcript of the session that runs it."""
    src = claude_project_dir()
    paths = sorted(src.glob("*.jsonl")) if args in ([], ["--all"]) else [src / f"{a}.jsonl" for a in args]
    redact, errors = Redactor(), 0
    for p in paths:
        subdir = p.parent / p.stem / "subagents"
        transcripts = [(p.stem, p)] + ([(f"{p.stem} agent {s.stem}", s) for s in sorted(subdir.glob("*.jsonl"))]
                                       if subdir.is_dir() else [])
        for name, path in transcripts:
            raw = path.read_text(errors="replace")
            data = redact(raw).decode()
            kinds = Counter(re.findall(r"\[REDACTED:([a-z.\-]+)\]", data))
            print(f"{name}: {len(raw):,} B raw, {len(data):,} B redacted; "
                  + (", ".join(f"{k} {n}" for k, n in kinds.most_common()) if kinds else "no redaction markers"))
            for kind in redact.leaks(data):
                print(f"  ERROR still unredacted after redaction: {kind}")
                errors += 1
            for warning in redact.review(data):
                print(f"  warn  {warning}")
    return 1 if errors else 0


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
    if cmd_upload(include_at=True) != 0:
        print("log upload failed; not pushing", file=sys.stderr)
        return 1
    write_index()  # the overview counts uploads
    at = jj_commits("@")[0]["change_id"]
    if any(c["change_id"] == at for m in all_manifests().values() for c in m.get("commits", [])) or uploads() != uploaded:
        jj("new")
        print(f"recorded traces in {at[:12]}")
    else:  # only git SHAs changed: not worth a commit, which would have a new SHA of its own
        jj("restore")
        jj("describe", "-r", "@", "-m", original if described else "")
    for flag, name in zip(args, args[1:]):
        if flag in ("--bookmark", "-b") and jj("bookmark", "set", name, "-r", "@-").returncode:
            print(f"could not move bookmark {name} to @-", file=sys.stderr)
            return 1
    if cmd_check() != 0:
        print("trace check failed; not pushing", file=sys.stderr)
        return 1
    return subprocess.run([JJ, "--config", "snapshot.max-new-file-size=100MiB", "git", "push", *args], cwd=REPO).returncode


def cmd_check(remote: bool = False) -> int:
    redact, errors, notes, warnings = Redactor(), [], [], []
    manifests = all_manifests()
    for sid, m in manifests.items():
        if m.get("schema") != SCHEMA:
            errors.append(f"{sid}: unknown schema {m.get('schema')}")
            continue
        logs, accepted = m.get("logs", {}), 0
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
                if info.get("withdrawn"):
                    notes.append(f"{sid}: log {sha[:12]} was withdrawn ({info['withdrawn']})")
                elif not url:
                    errors.append(f"{sid}: log {sha[:12]} is neither stored locally nor uploaded")
                continue
            if hashlib.sha256(data).hexdigest() != sha:
                errors.append(f"{sid}: log {sha[:12]} content does not match its name")
            text = data.decode(errors="replace")
            if leaks := redact.leaks(text):
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
                warnings += [f"{sid}: log {sha[:12]}: {w}" for w in redact.review(text)]
        if not summary_path(sid).exists():
            errors.append(f"{sid}: summary.md is missing (run: python3 llm-dlc/tools/sync.py sync {sid})")
        for path in (summary_path(sid), manifest_path(sid), notes_path(sid)):  # committed, so published
            if path.exists() and (leaks := redact.leaks(path.read_text())):
                errors.append(f"{sid}: unredacted {leaks} in {path.relative_to(REPO)}")
        # Logs are append-only: every log a commit points at should be a prefix of the current one.
        current = load_log(sid, m["log"]["sha256"]) or b""
        rewritten = {c["log_sha256"] for c in m.get("commits", []) if c.get("log_sha256")
                     and (old := load_log(sid, c["log_sha256"])) and not current.startswith(old)}
        if rewritten:
            notes.append(f"{sid}: {len(rewritten)} older log(s) are not a prefix of the current log, "
                         f"as after a redaction policy change")
        if accepted:
            notes.append(f"{sid}: {accepted} published log(s) have findings that were reviewed and accepted")
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
    if INDEX.exists() and {r["session_id"] for r in json.loads(INDEX.read_text())["sessions"]} != set(manifests):
        errors.append("llm-dlc/index.json does not list exactly the sessions in llm-dlc/traces (run sync)")
    if not TRACES_README.exists() or TRACES_README.read_text() != render_traces_readme():
        errors.append("llm-dlc/traces/README.md does not match the manifests (run sync)")
    for n in notes:
        print("note ", n)
    for w in warnings:
        print("warn ", w)
    for e in errors:
        print("ERROR", e)
    print(f"{len(manifests)} session(s): {len(errors)} error(s), {len(warnings)} warning(s) for a person to judge, "
          f"{len(notes)} note(s) needing no action")
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
        return cmd_check(remote=args == ["--remote"])
    elif cmd == "scan":
        return cmd_scan(args)
    elif cmd == "init":
        cmd_init()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

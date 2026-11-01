#!/usr/bin/env python3
"""What the trace tools treat as sensitive, and how they find it: redaction, leak and review rules.

Standard library only, and no knowledge of this machine: sync.py passes in the literals that are
personal to it. The stamp at the end of this file names these rules and says when they were last
applied to everything. A file older than that has been checked by them and isn't scanned again,
so editing anything above the stamp voids the date until `sync.py stamp` has rescanned.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REDACTION_POLICY = 4           # bump when redaction changes the bytes it produces
REDACT_KEYS = {"organizationUuid", "accountUuid", "userID"}  # account identifiers Claude Code records
# Email addresses that are public by design or placeholders; every other address is redacted.
PUBLIC_EMAILS = ("@example.com", "@example.org", "@users.noreply.github.com", "noreply@github.com",
                 "noreply@anthropic.com", "git@github.com", "@langfuse.local", "@localhost")
# These kinds are real by construction: a match is this machine's secret or account, so no review
# can waive them.
NEVER_REVIEWED = frozenset({"local-secret", "account-id"})
ACCOUNT_ID_HIT = "account identifier under a known key"

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


def _is_version(m: re.Match) -> bool:
    """Whether an address-shaped match is a version number, judged by the text around it."""
    return bool(VERSION_BEFORE.search(m.string, max(0, m.start() - 40), m.start())
                or VERSION_AFTER.match(m.string, m.end()))


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


def _strings(obj):
    """Every string in a JSON value, keys included."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _strings(v)


class Rules:
    """The rules, with the literals of one machine. Hits come back with no judgement applied:
    what a person has reviewed is the caller's business."""

    def __init__(self, pairs: list[tuple[str, str, int, str]], user: str) -> None:
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
        self._seen: dict[bytes, tuple[list, list]] = {}  # logs repeat each other's lines: see hits_of_text

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

    def _leaks_in(self, s: str, out: list) -> None:
        for kind, rx, _ in self.literals + self.secret_res:
            out += [(kind, m.group(0)) for m in rx.finditer(s)]
        out += [("email", m.group(0)) for m in EMAIL_RE.finditer(s) if not self._public_email(m.group(0))]
        out += [("windows-user", m.group(0)) for m in WIN_USER_RE.finditer(s) if self._win_user(m) != m.group(0)]
        if self.user_re:
            out += [("username", m.group(0)) for m in self.user_re.finditer(s)]

    def _reviewable_in(self, s: str, out: list) -> None:
        s = ANSI_RE.sub("", s)  # colour codes glue digits onto the words they precede
        for kind, rx, keep in self.review_res:
            out += [(kind, m.group(0)) for m in rx.finditer(s)
                    if keep(m.group(0)) and not (kind == "public-ip" and _is_version(m))]

    def hits_of_line(self, line: str) -> tuple[list, list]:
        """(what the redactor would still change, what is left for a person), as (kind, value)."""
        leaks: list = []
        reviewable: list = []
        try:
            obj = json.loads(line)
        except ValueError:
            self._leaks_in(line, leaks)
            self._reviewable_in(line, reviewable)
            return leaks, reviewable
        for s in _strings(obj):
            self._leaks_in(s, leaks)
            self._reviewable_in(s, reviewable)
        if _unscrubbed(obj):
            leaks.append(("account-id", ACCOUNT_ID_HIT))
        return leaks, reviewable

    def hits_of_text(self, text: str) -> tuple[dict[str, Counter], dict[str, Counter]]:
        """hits_of_line over a text, by kind and value. Each snapshot of a log repeats the one
        before it, so a line is scanned once; only a digest of it is kept."""
        leaks: dict[str, Counter] = {}
        reviewable: dict[str, Counter] = {}
        for line in text.splitlines():
            key = hashlib.blake2b(line.encode(errors="replace"), digest_size=16).digest()
            if (hits := self._seen.get(key)) is None:
                hits = self._seen[key] = self.hits_of_line(line)
            for found, into in zip(hits, (leaks, reviewable)):
                for kind, value in found:
                    into.setdefault(kind, Counter())[value] += 1
        return leaks, reviewable


def source_hash() -> str:
    """The hash of this file above its stamp."""
    text = Path(__file__).read_text()
    return hashlib.sha256(text[:text.rindex(_STAMP_MARK)].encode()).hexdigest()


def older_than_stamp(path: Path) -> bool:
    """Whether these rules have already been applied to this file. Rules edited since the stamp
    have not seen it, whatever its age."""
    generated = datetime.fromisoformat(RULES_GENERATED).timestamp()
    return RULES_HASH == source_hash() and path.stat().st_mtime < generated


def write_stamp() -> None:
    """Record these rules as applied to everything up to now."""
    file = Path(__file__)
    text = file.read_text()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    head = text[:text.rindex(_STAMP_MARK)]
    file.write_text(head + f"""{_STAMP_MARK}: written by `sync.py stamp`; the hash covers everything above this line.
RULES_HASH = "{source_hash()}"
RULES_GENERATED = "{now}"
RULES_STAMP = f"{{RULES_HASH}}@{{RULES_GENERATED}}"
""")


_STAMP_MARK = "# --- " + "stamp"
# --- stamp: written by `sync.py stamp`; the hash covers everything above this line.
RULES_HASH = "c88cdf5f07fe663ffe4b9fb8d6838b3bfe30e2d1e55ee361eb770ce52be76f0a"
RULES_GENERATED = "2026-11-01T23:27:26+00:00"
RULES_STAMP = f"{RULES_HASH}@{RULES_GENERATED}"

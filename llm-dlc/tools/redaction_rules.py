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
import string
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, NamedTuple

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

# Cheap first tests for rules that are slow on text they do not match: a rule's hint matches
# somewhere in any text the rule matches, so text the hint does not match is skipped, with the
# same result. env-secret backtracks through every word looking for its keywords. Each keyword
# holds one of the hint's words with only letters after it, and the rule needs its separator
# right after the keyword; both compared case-insensitively by the same engine, so ſ, the Kelvin
# sign and dotted İ fold alike. Half the cost on real logs (Nov 3 2026).
HINTS = {"env-secret": r"(?i)(?:pass|secret|token|credential|key|auth)[A-Z0-9_]*[\"']?\s*[=:]"}


class Gate(NamedTuple):
    """What every match of a rule holds: one of `words`, exactly or, with `ignorecase`, compared
    as re.I compares; and a match of `pattern`, which has no lookaround, anchor or \\b, so that it
    matches wherever its text is, whatever surrounds it. Either may be left out; the words are
    tested first, as they are cheaper."""
    words: tuple[str, ...] = ()
    ignorecase: bool = False
    pattern: str = ""


# Per-line gates. A line holds some 50 JSON strings and the rules are some 60, so most of a scan's
# time went into calling rules on strings they cannot match (llm-dlc/performance.md). A string
# holds what its rule's gate names wherever the rule matches it, and then so do the line's strings
# joined, by \0. So the gate is tested once on that joined text, and a rule whose gate fails is
# skipped on every string of the line, with the same result. The redactor's rules run one after
# another on a string, so its later rules see text the earlier ones replaced: a gate there holds
# only until a rule changes the string, and from then on every rule runs. A personal literal gates
# on itself, the username rule on the name, email on @. A rule with no gate runs on every string.
GATES = {
    "anthropic-key": Gate(("sk-ant-",)),
    "langfuse-key": Gate(("k-lf-",)),
    "api-key": Gate(("sk-",)),
    "github-token": Gate(("ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_")),
    "gitlab-token": Gate(("glpat-",)),
    "aws-key": Gate(("AKIA",)),
    "google-key": Gate(("AIza",)),
    "google-oauth": Gate(("ya29.",)),
    "slack-token": Gate(("xoxa-", "xoxb-", "xoxp-", "xoxr-", "xoxs-")),
    "slack-webhook": Gate(("https://hooks.slack.com/services/",)),
    "discord-webhook": Gate(("/api/webhooks/",)),
    "npm-token": Gate(("npm_",)),
    "huggingface-token": Gate(("hf_",)),
    "stripe-key": Gate(("k_live_", "k_test_")),
    "sendgrid-key": Gate(("SG.",)),
    "jwt": Gate(("eyJ",)),
    "private-key": Gate(("-----BEGIN ",)),
    "bearer": Gate(("bearer",), ignorecase=True),
    "basic-auth": Gate(("basic",), ignorecase=True),
    "url-password": Gate(("://",), pattern="@"),
    "curl-user": Gate(("-u ", "-u=", "--user ", "--user=")),
    "account-id": Gate(("accountUuid", "organizationUuid", "userID")),
    # Each keyword holds one of these words, and the hint matches in the rule's match: see HINTS,
    # which is then tested on each string of a line that passes.
    "env-secret": Gate(("pass", "secret", "token", "credential", "key", "auth"), ignorecase=True,
                       pattern=HINTS["env-secret"]),
    "windows-user": Gate(("Users",)),
    # Review rules, tested on the strings with colour codes removed; so are their gates.
    "public-ip": Gate(pattern=r"\d\.\d{1,3}\.\d{1,3}\.\d"),  # the end of the first number to the start of the last
    "ipv6": Gate(pattern=r"[0-9A-Fa-f]:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]"),  # three of its five colons or more
    "mac-address": Gate(pattern=r"[0-9A-Fa-f]:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]{1,4}:[0-9A-Fa-f]"),
    "other-home-dir": Gate(("/home/", "/Users/")),
    "auth-header": Gate(("authorization", "cookie", "x-api-key"), ignorecase=True),  # and set-cookie, proxy-...
    "long-token": Gate(pattern=r"[A-Za-z0-9+/_\-]{40}"),
}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}(?![A-Za-z0-9\-])")
# EMAIL_RE retries its local part from every character of a run of local-part characters, which
# is quadratic on a long run, @ or not. email_spans finds the same matches in linear time; EMAIL_RE
# stays as their definition and is what the tests compare against.
_LOCAL_CHARS = frozenset(string.ascii_letters + string.digits + "._%+-")  # [A-Za-z0-9._%+\-]
_EMAIL_DOMAIN_RE = re.compile(r"[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}(?![A-Za-z0-9\-])")


def email_spans(s: str):
    """(start, end) of each match of EMAIL_RE.finditer(s). A match holds one @, its local part is
    the run of local-part characters before it, and that run cannot reach back past where the last
    match ended: so each @ is looked at once, and its run is walked back from it."""
    pos = 0
    while (at := s.find("@", pos)) >= 0:
        start = at
        while start > pos and s[start - 1] in _LOCAL_CHARS:
            start -= 1
        if start < at and (m := _EMAIL_DOMAIN_RE.match(s, at + 1)):
            yield start, m.end()
            pos = m.end()
        else:
            pos = at + 1

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


def _min_width(rx: re.Pattern) -> int:
    """The fewest characters a match of rx can take: a string shorter than that holds none. 0, so
    that the rule always runs, when the parser that knows it is not there."""
    try:
        return re._parser.parse(rx.pattern, rx.flags).getwidth()[0]
    except Exception:  # noqa: BLE001 - a private module: any failure means "don't know"
        return 0


def _gate_test(gate: Gate | None) -> Callable[[str, str | None], bool] | None:
    """gate as a test of (a line's strings joined, the same lowered if it is all ASCII, else None);
    None when there is no gate. For ASCII text and ASCII words, re.I compares as str.lower does:
    its other folds (ſ, the Kelvin sign, İ, ı) all pair an ASCII letter with a non-ASCII one."""
    if gate is None:
        return None
    words_test = _words_test(gate.words, gate.ignorecase) if gate.words else None
    if not gate.pattern:
        return words_test
    search = re.compile(gate.pattern).search
    if words_test is None:
        return lambda joined, _lowered: search(joined) is not None
    return lambda joined, lowered: words_test(joined, lowered) and search(joined) is not None


def _words_test(words: tuple[str, ...], ignorecase: bool) -> Callable[[str, str | None], bool]:
    if not ignorecase:
        if len(words) == 1:
            word = words[0]
            return lambda joined, _lowered: word in joined
        return lambda joined, _lowered: any(w in joined for w in words)
    search = re.compile("|".join(map(re.escape, words)), re.I).search
    if not all(w.isascii() for w in words):
        return lambda joined, _lowered: search(joined) is not None
    lowered_words = tuple(w.lower() for w in words)
    return lambda joined, lowered: (any(w in lowered for w in lowered_words) if lowered is not None
                                    else search(joined) is not None)


class _Plan(NamedTuple):
    """The rules of a Rules, each with its gate (an index into tests, or -1 for none), the shortest
    string it can match and what it does: finds leaks, finds reviewable text, or redacts."""
    tests: list[Callable[[str, str | None], bool]]
    leaks: list[tuple[int, int, Callable[[str, list], None]]]
    review: list[tuple[int, int, Callable[[str, list], None]]]
    steps: list[tuple[int, int, Callable[[str], str]]]


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
        self._user_hint = (self.user_re, user)  # the name the pattern holds, as long as it is this pattern
        self.secret_res = [(p[0], re.compile(p[1], re.S), p[2] if len(p) > 2 else f"[REDACTED:{p[0]}]")
                           for p in SECRET_PATTERNS]
        self.hints = {kind: re.compile(hint) for kind, hint in HINTS.items()}
        self.review_res = [(kind, re.compile(pattern), keep) for kind, pattern, keep in REVIEW_PATTERNS]
        self._seen: dict[bytes, tuple[list, list]] = {}  # logs repeat each other's lines: see hits_of_text
        # Gates by the pattern they gate, so that a pattern put in place of one of these after
        # construction (tests do) runs ungated. A literal gates on itself, in its case or under re.I.
        self._gates: dict[re.Pattern, Gate] = {
            rx: Gate((lit,), ignorecase=bool(flags & re.I))
            for (_kind, rx, _rep), (lit, _r, flags, _k) in zip(self.literals, pairs) if flags & ~re.I == 0}
        self._gates.update({rx: GATES[kind] for kind, rx, _rep in self.secret_res if kind in GATES})
        self._gates.update({rx: GATES[kind] for kind, rx, _keep in self.review_res if kind in GATES})
        if self.user_re is not None:
            self._gates[self.user_re] = Gate((user,))
        self._gates.update({EMAIL_RE: Gate(("@",)), WIN_USER_RE: GATES["windows-user"]})
        self._plan_key: tuple = ()
        self._plan_value: _Plan | None = None

    @staticmethod
    def _public_email(address: str) -> bool:
        return address.lower().endswith(PUBLIC_EMAILS)

    @staticmethod
    def _win_user(m: re.Match) -> str:
        path = m.group(1)
        prefix, name = re.match(r"(.*[/\\])([^/\\]*)$", path).groups()
        return path if name.lower() in WIN_SHARED else prefix + "user"

    def _may_match(self, kind: str, text: str) -> bool:
        """False only when the rule of this kind cannot match the text: see HINTS."""
        hint = self.hints.get(kind)
        return hint is None or hint.search(text) is not None

    def _user_may_match(self, text: str) -> bool:
        if self.user_re is None:
            return False
        rx, user = self._user_hint
        return rx is not self.user_re or user in text  # the pattern matches the name, case and all

    def _emails_redacted(self, text: str) -> str:
        """EMAIL_RE.sub of the addresses that are not public, by email_spans."""
        out, last = [], 0
        for start, end in email_spans(text):
            address = text[start:end]
            out += [text[last:start], address if self._public_email(address) else "[REDACTED:email]"]
            last = end
        return "".join(out) + text[last:] if out else text

    def _plan(self) -> _Plan:
        """The plan for the rules as they are now: built again when one of the lists of rules or
        the username pattern is replaced."""
        key = (self.literals, self.secret_res, self.user_re, self.review_res, self.hints)
        if self._plan_value is not None and all(a is b for a, b in zip(key, self._plan_key)):
            return self._plan_value
        tests: list = []
        index: dict[Gate, int] = {}

        def gate(rx: re.Pattern) -> int:
            g = self._gates.get(rx)
            if g is None:
                return -1
            if g not in index:
                index[g] = len(tests)
                tests.append(_gate_test(g))
            return index[g]

        def found(kind, rx):
            return lambda s, out: out.extend([(kind, m.group(0)) for m in rx.finditer(s)])

        def hinted(kind, rx):
            return lambda s, out: out.extend([(kind, m.group(0)) for m in rx.finditer(s)] if self._may_match(kind, s) else ())

        def emails(s, out):
            out += [("email", s[a:b]) for a, b in email_spans(s) if not self._public_email(s[a:b])]

        def win_users(s, out):
            out += [("windows-user", m.group(0)) for m in WIN_USER_RE.finditer(s) if self._win_user(m) != m.group(0)]

        def reviewed(kind, rx, keep):
            return lambda s, out: out.extend([(kind, m.group(0)) for m in rx.finditer(s)
                                              if keep(m.group(0)) and not (kind == "public-ip" and _is_version(m))])

        def literal(rx, rep):
            return lambda t: rx.sub(lambda _m: rep, t)

        def secret(kind, rx, rep):
            return lambda t: rx.sub(rep, t) if self._may_match(kind, t) else t

        leaks = [(gate(rx), _min_width(rx), found(kind, rx)) for kind, rx, _ in self.literals]
        leaks += [(gate(rx), _min_width(rx), hinted(kind, rx)) for kind, rx, _ in self.secret_res]
        leaks += [(gate(EMAIL_RE), _min_width(EMAIL_RE), emails), (gate(WIN_USER_RE), _min_width(WIN_USER_RE), win_users)]
        steps = [(gate(rx), _min_width(rx), literal(rx, rep)) for _kind, rx, rep in self.literals]
        steps += [(gate(rx), _min_width(rx), secret(kind, rx, rep)) for kind, rx, rep in self.secret_res]
        steps += [(gate(EMAIL_RE), _min_width(EMAIL_RE), self._emails_redacted),
                  (gate(WIN_USER_RE), _min_width(WIN_USER_RE), lambda t: WIN_USER_RE.sub(self._win_user, t))]
        if (rx := self.user_re) is not None:
            leaks.append((gate(rx), _min_width(rx), lambda s, out: out.extend(
                [("username", m.group(0)) for m in rx.finditer(s)] if self._user_may_match(s) else ())))
            steps.append((gate(rx), _min_width(rx), lambda t: rx.sub("user", t) if self._user_may_match(t) else t))
        review = [(gate(rx), _min_width(rx), reviewed(kind, rx, keep)) for kind, rx, keep in self.review_res]
        self._plan_key, self._plan_value = key, _Plan(tests, leaks, review, steps)
        return self._plan_value

    @staticmethod
    def _passed(tests, joined: str) -> list[bool]:
        """Which gates the strings of one line pass, all tested on the strings joined by \\0."""
        lowered = joined.lower() if joined.isascii() else None
        return [test(joined, lowered) for test in tests]

    def _redacted(self, text: str, steps: list) -> str:
        """The steps of the plan, in order, on one string. steps holds those whose gate the line
        passed; once one changes the string, the gates say nothing about it, so every later step
        of the plan runs."""
        original = text
        for n, (minimum, apply) in steps:
            if len(text) >= minimum:
                text = apply(text)
                if text is not original:
                    for _gate, minimum, apply in self._plan().steps[n + 1:]:
                        if len(text) >= minimum:
                            text = apply(text)
                    return text
        return text

    def _steps_of(self, strings: list[str] | None) -> list:
        """(index in the plan, shortest match, step) of the steps whose gate a line's strings pass;
        every step for strings=None."""
        plan = self._plan()
        passed = self._passed(plan.tests, "\x00".join(strings)) if strings is not None else None
        return [(n, (minimum, apply)) for n, (g, minimum, apply) in enumerate(plan.steps)
                if g < 0 or passed is None or passed[g]]

    def string(self, text: str) -> str:
        return self._redacted(text, self._steps_of(None))

    def __call__(self, jsonl: str) -> bytes:
        """Redact every string (keys included) of every JSON line. Working on decoded
        strings matters: in raw JSON "\\nname" hides the word boundary before "name".
        Deterministic and line-local, so an append-only transcript gives an append-only log."""
        out = []
        for line in jsonl.splitlines():
            try:
                obj = json.loads(line)
            except ValueError:
                out.append(self._redacted(line, self._steps_of([line])))
                continue
            obj = _scrub(obj)
            steps = self._steps_of(list(_strings(obj)))
            out.append(json.dumps(_walk(obj, lambda s: self._redacted(s, steps)), ensure_ascii=False, separators=(",", ":")))
        return ("\n".join(out) + "\n" if out else "").encode()

    def hits_of_line(self, line: str) -> tuple[list, list]:
        """(what the redactor would still change, what is left for a person), as (kind, value)."""
        leaks: list = []
        reviewable: list = []
        try:
            obj = json.loads(line)
        except ValueError:
            obj, strings = None, [line]
        else:
            strings = list(_strings(obj))
        plan = self._plan()
        joined = "\x00".join(strings)
        passed = self._passed(plan.tests, joined)
        finders = [(minimum, find) for g, minimum, find in plan.leaks if g < 0 or passed[g]]
        if finders:
            for s in strings:
                n = len(s)
                for minimum, find in finders:
                    if n >= minimum:
                        find(s, leaks)
        # Colour codes glue digits onto the words they precede: the review rules, and so their
        # gates, see the strings without them.
        if "\x1b" in joined:
            strings = [ANSI_RE.sub("", s) for s in strings]
            passed = self._passed(plan.tests, "\x00".join(strings))
        reviewers = [(minimum, find) for g, minimum, find in plan.review if g < 0 or passed[g]]
        if reviewers:
            for s in strings:
                n = len(s)
                for minimum, find in reviewers:
                    if n >= minimum:
                        find(s, reviewable)
        if obj is not None and _unscrubbed(obj):
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


def write_stamp(generated: str | None = None) -> None:
    """Record these rules as applied to everything up to now, or up to `generated`: the date of the
    last stamp, kept by rules shown to give the same results as the ones stamped then."""
    file = Path(__file__)
    text = file.read_text()
    now = generated or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    head = text[:text.rindex(_STAMP_MARK)]
    file.write_text(head + f"""{_STAMP_MARK}: written by `sync.py stamp`; the hash covers everything above this line.
RULES_HASH = "{source_hash()}"
RULES_GENERATED = "{now}"
RULES_STAMP = f"{{RULES_HASH}}@{{RULES_GENERATED}}"
""")


_STAMP_MARK = "# --- " + "stamp"
# --- stamp: written by `sync.py stamp`; the hash covers everything above this line.
RULES_HASH = "5af6bb15e22867255de50c5382680563e36571c2a25406c207ba1f706a8a8016"
RULES_GENERATED = "2026-11-01T23:27:26+00:00"
RULES_STAMP = f"{RULES_HASH}@{RULES_GENERATED}"

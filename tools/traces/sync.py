#!/usr/bin/env python3
"""Publish Claude Code session traces for this repo.

For each session it:
  1. writes a redacted copy of the transcript to traces/sessions/<session-id>.jsonl
     (plus subagent transcripts under traces/sessions/<session-id>/),
  2. records it in traces/manifest.json (hashes, models, token usage, jj changes),
  3. exports each turn to Langfuse as an OTLP trace (when infra/langfuse/.env exists
     and Langfuse is reachable), and
  4. links jj changes and sessions both ways: the manifest lists the change ids
     a session touched, and each such change's description carries an
     "LLM-Trace: <session-id>" trailer.

Usage:
  sync.py hook                 Claude Code Stop/SessionEnd hook (reads hook JSON on stdin)
  sync.py sync [--all | ID...] backfill sessions of this repo from ~/.claude/projects
  sync.py relink               re-add missing trailers to mutable changes in the manifest
  sync.py check                verify hashes, redaction and trailers (non-zero exit on error)

Standard library only. The hook never fails the session: errors go to
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
SESSIONS = TRACES / "sessions"
MANIFEST = TRACES / "manifest.json"
LANGFUSE_ENV = REPO / "infra" / "langfuse" / ".env"
STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "llm-traces"
EXTRA_REDACTIONS = Path.home() / ".config" / "llm-traces" / "redact.txt"
TRAILER = "LLM-Trace"
# Hooks inherit the PATH Claude Code started with, which may predate ~/.local/bin.
JJ = shutil.which("jj") or str(Path.home() / ".local" / "bin" / "jj")
GZIP_ABOVE = 45 * 1024 * 1024  # GitHub rejects files over 100 MB and warns over 50 MB
MAX_ATTR = 64 * 1024           # truncate large tool outputs sent to Langfuse
LIVE_SECONDS = 600             # a transcript written this recently may have an unfinished turn


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


def personal_literals() -> list[tuple[str, str]]:
    """(literal, replacement) pairs for this machine: home path, user name, emails, local secrets."""
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

    def __call__(self, jsonl: str) -> str:
        """Redact every string (keys included) of every JSON line. Working on decoded
        strings matters: in raw JSON "\\nname" hides the word boundary before "name"."""
        out = []
        for line in jsonl.splitlines():
            try:
                obj = json.loads(line)
            except ValueError:
                out.append(self.string(line))
                continue
            out.append(json.dumps(_walk(obj, self.string), ensure_ascii=False, separators=(",", ":")))
        return "\n".join(out) + "\n" if out else ""

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


def read_jsonl(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
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


def summarize(entries: list[dict]) -> dict:
    usage = {k: 0 for k in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
    seen, models, title, version, first_prompt, turns = set(), set(), None, None, None, 0
    stamps = [e["timestamp"] for e in entries if e.get("timestamp")]
    for e in entries:
        version = version or e.get("version")
        if e.get("type") == "ai-title":
            title = e.get("aiTitle") or title
        elif is_prompt(e):
            turns += 1
            first_prompt = first_prompt or text_of(e["message"])[:200]
        elif e.get("type") == "assistant":
            msg = e.get("message") or {}
            if msg.get("model") and not msg["model"].startswith("<"):
                models.add(msg["model"])
            mid = msg.get("id") or e.get("requestId")
            if mid and mid not in seen:
                seen.add(mid)
                for k in usage:
                    usage[k] += int((msg.get("usage") or {}).get(k) or 0)
    return {"title": title, "first_prompt": first_prompt, "started": min(stamps, default=None),
            "ended": max(stamps, default=None), "client": f"claude-code {version}" if version else None,
            "models": sorted(models), "turns": turns, "api_calls": len(seen), "usage": usage}


# --------------------------------------------------------------------------- manifest

def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"schema": 1,
            "about": "Claude Code session traces for this repo. See docs/traces.md.",
            "sessions": {}}


def save_manifest(m: dict) -> None:
    m["sessions"] = dict(sorted(m["sessions"].items(), key=lambda kv: kv[1].get("started") or ""))
    TRACES.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(MANIFEST)


def write_trace(dest: Path, text: str) -> dict:
    """Write a redacted transcript (gzipped when large) and return its manifest record."""
    data = text.encode()
    for stale in (dest, dest.with_suffix(dest.suffix + ".gz")):
        stale.unlink(missing_ok=True)
    if len(data) > GZIP_ABOVE:
        dest = dest.with_suffix(dest.suffix + ".gz")
        data = gzip.compress(data, mtime=0)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return {"file": str(dest.relative_to(REPO)), "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data), "lines": text.count("\n")}


def sync_session(transcript: Path, redact: Redactor, manifest: dict, live: bool) -> tuple[str, list[dict]]:
    sid = transcript.stem
    text = redact(transcript.read_text(errors="replace"))
    entries = read_jsonl(text)
    record = manifest["sessions"].get(sid, {})
    record.update(write_trace(SESSIONS / f"{sid}.jsonl", text))
    record.update(summarize(entries))
    subdir = transcript.parent / sid / "subagents"
    subs = []
    shutil.rmtree(SESSIONS / sid, ignore_errors=True)
    for sub in sorted(subdir.glob("*.jsonl")) if subdir.is_dir() else []:
        subs.append(write_trace(SESSIONS / sid / "subagents" / sub.name, redact(sub.read_text(errors="replace"))))
    record["subagents"] = subs
    record.setdefault("jj_changes", [])
    record["langfuse"] = {"project": read_env(LANGFUSE_ENV).get("LANGFUSE_INIT_PROJECT_ID"), "session_id": sid}
    record["live"] = live
    manifest["sessions"][sid] = record
    return sid, entries


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


def turn_spans(sid: str, n: int, turn: list[dict], meta: dict) -> list[dict]:
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
        "langfuse.trace.name": meta.get("title") or "claude-code session",
        "session.id": sid,
        "langfuse.trace.input": text_of(prompt.get("message")),
        "langfuse.trace.output": answer,
        "langfuse.trace.tags": ["claude-code"],
        "langfuse.trace.metadata.turn": n,
        "langfuse.trace.metadata.trace_file": meta.get("file"),
        "langfuse.trace.metadata.jj_changes": ",".join(meta.get("jj_changes", [])),
    }))
    return spans


def export_langfuse(sid: str, entries: list[dict], meta: dict, live: bool) -> int:
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
    spans = [s for n, t in pending for s in turn_spans(sid, n, t, meta)]
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


# --------------------------------------------------------------------------- jj

def jj(*args: str) -> subprocess.CompletedProcess:
    # Trace files exceed jj's default 1 MiB limit for snapshotting new files.
    return subprocess.run([JJ, "--quiet", "--config", "snapshot.max-new-file-size=100MiB", *args],
                          capture_output=True, text=True, timeout=30, cwd=REPO)


def has_jj() -> bool:
    return (REPO / ".jj").is_dir() and os.access(JJ, os.X_OK)


def current_change() -> str | None:
    r = jj("log", "--no-graph", "-r", "@", "-T", "change_id")
    return r.stdout.strip() if r.returncode == 0 else None


def relink(manifest: dict) -> int:
    """Add an LLM-Trace trailer for each session to each mutable change the manifest links it to."""
    wanted: dict[str, list[str]] = {}
    for sid, rec in manifest["sessions"].items():
        for cid in rec.get("jj_changes", []):
            wanted.setdefault(cid, []).append(sid)
    if not wanted:
        return 0
    revset = "mutable() & (" + " | ".join(f"present({c})" for c in wanted) + ")"
    r = jj("log", "--no-graph", "-r", revset, "-T", 'change_id ++ "\\t" ++ json(description) ++ "\\n"')
    fixed = 0
    for line in r.stdout.splitlines():
        cid, _, desc_json = line.partition("\t")
        desc = json.loads(desc_json)
        missing = [s for s in wanted.get(cid, []) if f"{TRAILER}: {s}" not in desc]
        if missing:
            body = desc.rstrip("\n")
            # Join an existing trailer block (e.g. Co-Authored-By) rather than start a new paragraph.
            sep = "\n" if re.search(r"(^|\n)[A-Za-z][A-Za-z-]*: .+$", body) else ("\n\n" if body else "")
            new = body + sep + "\n".join(f"{TRAILER}: {s}" for s in missing) + "\n"
            if jj("describe", "-r", cid, "-m", new).returncode == 0:
                fixed += 1
    return fixed


# --------------------------------------------------------------------------- commands

def cmd_hook() -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    try:
        payload = json.load(sys.stdin)
        transcript = Path(payload["transcript_path"])
        redact, manifest = Redactor(), load_manifest()
        sid, entries = sync_session(transcript, redact, manifest, live=False)
        if has_jj() and (cid := current_change()):
            changes = manifest["sessions"][sid]["jj_changes"]
            if cid not in changes:
                changes.append(cid)
        save_manifest(manifest)
        if has_jj():
            relink(manifest)
        try:
            export_langfuse(sid, entries, manifest["sessions"][sid], live=False)
        except OSError as e:  # Langfuse down: those turns are retried on the next hook
            log(f"langfuse export deferred for {sid}: {e}")
    except Exception:
        log(traceback.format_exc())


def cmd_sync(args: list[str]) -> None:
    src = claude_project_dir()
    paths = sorted(src.glob("*.jsonl")) if args in ([], ["--all"]) else [src / f"{a}.jsonl" for a in args]
    redact, manifest = Redactor(), load_manifest()
    for p in paths:
        live = time.time() - p.stat().st_mtime < LIVE_SECONDS
        sid, entries = sync_session(p, redact, manifest, live)
        save_manifest(manifest)
        try:
            n = export_langfuse(sid, entries, manifest["sessions"][sid], live)
        except OSError as e:
            n = f"skipped ({e})"
        rec = manifest["sessions"][sid]
        print(f"{sid}  {rec['turns']} turns  {rec['bytes']:>10,} B  langfuse: {n}{'  (live)' if live else ''}")
    if has_jj():
        print(f"relinked {relink(manifest)} change(s)")


def cmd_check() -> int:
    manifest, redact, errors = load_manifest(), Redactor(), []
    for sid, rec in manifest["sessions"].items():
        for f in [rec] + rec.get("subagents", []):
            path = REPO / f["file"]
            if not path.exists():
                errors.append(f"{sid}: missing {f['file']}")
                continue
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != f["sha256"]:
                errors.append(f"{sid}: sha256 mismatch for {f['file']}")
            text = (gzip.decompress(data) if path.suffix == ".gz" else data).decode(errors="replace")
            if leaks := redact.leaks(text):
                errors.append(f"{sid}: unredacted {sorted(set(leaks))} in {f['file']}")
    if has_jj():
        r = jj("log", "--no-graph", "-r", "all()", "-T", 'change_id ++ "\\t" ++ json(description) ++ "\\n"')
        for line in r.stdout.splitlines():
            cid, _, desc = line.partition("\t")
            for sid in re.findall(rf"{TRAILER}: (\S+)", json.loads(desc)):
                if sid not in manifest["sessions"]:
                    errors.append(f"change {cid[:12]}: {TRAILER} {sid} not in manifest")
    for e in errors:
        print("ERROR", e)
    print(f"{len(manifest['sessions'])} session(s), {len(errors)} error(s)")
    return 1 if errors else 0


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
    elif cmd == "relink":
        print(f"relinked {relink(load_manifest())} change(s)")
    elif cmd == "check":
        return cmd_check()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""The client boundary of a loop's turn: one place that starts or resumes a turn of Claude Code or of Codex.

The loops build one instruction and decide everything around it (feature-loop.sh, run-streams.sh, brief_run.py,
single_run.py); which client carries a turn is decided here and nowhere else. Claude Code's turns are started by
the loops as they always were, with the arguments they always had. A Codex turn is started by this file, which
prints **the same stream the loops already read**: Claude Code's stream-json events (`system`/`init`, `assistant`
with text and tool_use blocks, `system`/`compact_boundary`, and one closing `result`), so what displays progress,
watches for a compaction, reads a turn's report and counts its cost needs no second reader. Diagnostics go to
stderr, never into that stream.

    agent_client.py run --client codex --session ID --model MODEL --effort LEVEL [--cwd DIR] PROMPT
        one turn. The first turn of a session starts a Codex thread; every later one resumes that exact
        thread. Prints the stream, exits 0 when the turn ended with a result.
    agent_client.py compact --client codex --session ID [--cwd DIR]
        compact the session's thread now (the loops do this between cycles). A `/compact` sent as a turn's text
        is only text to Codex, so this asks its app server (`thread/compact/start`) and waits for the end.
    agent_client.py exists --client codex --session ID [--cwd DIR]     exit 0 when the session has a thread
    agent_client.py binding --session ID [--cwd DIR]                   the session's binding, as JSON
    agent_client.py resolve --client CLIENT MODEL                      the model that client runs for MODEL
    agent_client.py plan --client CLIENT --model MODEL --effort LEVEL  client, model and effort as resolved, JSON
    agent_client.py instructions --client codex [--cwd DIR]            whether the client is given this
                                                                      checkout's own instructions (below)

**Models.** A brief names a role's model once, by its Claude name, and the operator's equivalences say what
Codex runs for it (MODELS): Fable 5.2 is Astra 6.2, Opus 5.5 is Sol 6.2. A Codex model named outright is taken
as it is. Any other model has no equivalent and is refused before a turn is spent (`resolve` says so), which is
how a role nobody mapped shows up. The effort is always passed on: the machine's own Codex default may be another
(it is `max` on the authors' VM), and a role that asks for `high` gets `high`.

**Session identity.** A loop names its session by a UUID it chose before the first turn; Codex names its thread
itself. The binding of the one to the other is a file of the workspace the loop runs in,
`llm-dlc/loop-summaries/agent-sessions/SESSION.json` (gitignored, like every run record), written whole and at
once when Codex reports the thread (`thread.started`): client, thread, folder, model, effort, the attempt, and
the session that started the loop when there was one. A resumed turn names that thread, and a turn whose client
reports another thread is ended as an error and changes nothing. Each attempt keeps Codex's own events as they
came, its stderr and its last message under `agent-sessions/attempts/SESSION/`, named by number, time and
process, so two workers starting in the same second do not share a file and a turn that died leaves what it said.

**Identity at the boundary.** A Codex started from a Claude Code session would inherit that session's variables
(CLAUDE_CODE_SESSION_ID, CLAUDECODE), and its commits and jobs would be credited to the watcher. They are
removed from the child's environment here; who started the loop is kept in the binding instead (`parent`).

**Instructions.** Codex is pointed at the checkout's own CLAUDE.md (`project_doc_fallback_filenames`), on the
command line as well as in `.codex/config.toml`, because a fresh sibling workspace is not a project Codex
trusts and its config file would be skipped. `instructions` renders what the model would be given
(`codex debug prompt-input`, no model is called) and checks it privately: that CLAUDE.md's first and last lines
are in it, that no AGENTS.md or AGENTS.override.md shadows it, and that it fits the byte budget. It prints the
sources' paths and digests and pass or fail, never the text.

Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

CLIENTS = ("claude", "codex")
# The operator's equivalences (2026-11-18): what Codex runs for a role a brief names by its Claude model.
MODELS = {"claude-fable-5-2": "gpt-6.2-astra", "claude-opus-5-5": "gpt-6.2-sol"}
EFFORTS = ("low", "medium", "high", "xhigh", "max")
SESSION = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
INSTRUCTIONS = "CLAUDE.md"
NOTES = ("llm-dlc/operating-notes.md",)
SHADOWS = ("AGENTS.override.md", "AGENTS.md")  # Codex reads these before any fallback name
DOC_BUDGET = 32 * 1024  # Codex's default project_doc_max_bytes
# What every Codex turn is started with, whatever the machine's own config says.
CODEX_CONFIG = (f'project_doc_fallback_filenames=["{INSTRUCTIONS}"]',)
# A parent session's identity, which a child of another client must not carry (see the docstring).
PARENT_MARKERS = ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CLAUDE_CODE_ENTRYPOINT", "CODEX_THREAD_ID", "CODEX_SESSION_ID")


class Problem(Exception):
    pass


def resolve(client: str, model: str) -> str:
    """The model CLIENT runs for MODEL, a brief's name for a role's model."""
    if client not in CLIENTS:
        raise Problem(f"{client!r} is not a client this knows ({', '.join(CLIENTS)})")
    if client == "claude":
        if not model.startswith("claude-"):
            raise Problem(f"{model} is not a Claude model: a loop run by Claude Code names one (claude-...)")
        return model
    if model in MODELS:
        return MODELS[model]
    if model.startswith("gpt-"):
        return model
    raise Problem(f"no Codex model stands for {model}: the equivalences cover {', '.join(MODELS)}. Name a Codex model "
                  f"for this role outright (gpt-...), or run the role with Claude Code")


def plan(client: str, model: str, effort: str) -> dict:
    if effort not in EFFORTS:
        raise Problem(f"{effort!r} is not an effort ({', '.join(EFFORTS)})")
    return {"client": client, "model": resolve(client, model), "effort": effort, **({"for": model} if resolve(client, model) != model else {})}


def root_of(cwd: Path) -> Path:
    r = subprocess.run(["jj", "--ignore-working-copy", "workspace", "root"], cwd=cwd, capture_output=True, text=True)
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else cwd


def state_dir(cwd: Path) -> Path:
    return Path(os.environ.get("AGENT_CLIENT_STATE") or root_of(cwd) / "llm-dlc" / "loop-summaries" / "agent-sessions")


def binding(session: str, cwd: Path) -> dict | None:
    try:
        data = json.loads((state_dir(cwd) / f"{session}.json").read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("thread") else None


def bind(session: str, cwd: Path, **fields) -> dict:
    """Write the binding whole, at once: a reader sees the old one or the new one."""
    path = state_dir(cwd) / f"{session}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {**(binding(session, cwd) or {}), **fields, "session": session, "updated": now()}
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=1) + "\n")
    os.replace(tmp, path)
    return data


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# A run's own variables: the watcher's, the loop's and the conductor's. A worker that inherits them takes its own
# commands for the run's (a `sync.py commit` that thinks it is the watcher's, a nested loop that records under the
# run's name). Claude Code's workers get the same from feature-loop.sh and, in a stream's workspace, from
# .claude/settings.local.json, which Codex does not read.
RUN_PREFIXES = ("RUN_STREAMS_", "FEATURE_LOOP_", "LOOP_WATCH_", "PROVE_LOOP_")
RUN_NAMES = ("LOOP_CONDUCTOR",)


def tmp_of(session: str | None) -> Path:
    """A session's own folder for temporary files, on disk: /tmp here is memory with a quota per user, which
    test leftovers have filled, and Claude Code gives each of its sessions a scratch folder that Codex does not.
    Not inside the checkout, where a test's leftovers would be the working copy's."""
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "in-the-loop" / "agent-tmp"
    return base / (session or "none")


def child_env(session: str | None = None) -> tuple[dict, dict | None]:
    """The child's environment without the parent session's identity or a run's variables, with a folder of
    its own for temporary files; and that identity, for the binding."""
    env = dict(os.environ)
    parent = None
    if env.get("CLAUDE_CODE_SESSION_ID"):
        parent = {"client": "claude", "session": env["CLAUDE_CODE_SESSION_ID"]}
    elif env.get("CODEX_THREAD_ID"):
        parent = {"client": "codex", "thread": env["CODEX_THREAD_ID"]}
    for key in [k for k in env if k in PARENT_MARKERS or k in RUN_NAMES or k.startswith(RUN_PREFIXES)]:
        del env[key]
    if session:
        tmp = tmp_of(session)
        tmp.mkdir(parents=True, exist_ok=True)
        env["TMPDIR"] = str(tmp)
    return env, parent


def emit(event: dict) -> None:
    print(json.dumps(event), flush=True)


def usage_of(u: dict) -> dict:
    """Token counts of Codex's (a turn's own: see turn_tokens), under the keys the loops read from Claude Code:
    OpenAI's input count includes the cached tokens, Claude's does not."""
    cached = int(u.get("cached_input_tokens") or 0)
    return {"input_tokens": max(0, int(u.get("input_tokens") or 0) - cached), "cache_read_input_tokens": cached,
            "cache_creation_input_tokens": int(u.get("cache_write_input_tokens") or 0),
            "output_tokens": int(u.get("output_tokens") or 0),
            "reasoning_output_tokens": int(u.get("reasoning_output_tokens") or 0)}


TOKEN_KEYS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens", "reasoning_output_tokens")


def turn_tokens(reported: dict, before: dict | None) -> tuple[dict, dict]:
    """(this turn's tokens, the thread's totals) from what Codex reports when a turn ends, which is **the thread's
    running total**, not the turn's (seen on CLI 0.169, 2026-11-18: five turns of one thread reported 371k, 434k,
    555k, 995k and 1081k input tokens). The turn's own are the rise since the totals the binding kept; a count
    that fell (another counter, a fork) is taken as the turn's."""
    total = {k: int(reported.get(k) or 0) for k in TOKEN_KEYS}
    rise = {k: total[k] - int((before or {}).get(k) or 0) for k in TOKEN_KEYS}
    return (rise if all(v >= 0 for v in rise.values()) else total), total


def translate(event: dict, session: str) -> list[dict]:
    """One of Codex's `exec --json` events as the stream-json events the loops read (none for most)."""
    kind, item = event.get("type"), event.get("item") or {}
    what = item.get("type") or ""

    def says(block: dict) -> dict:
        return {"type": "assistant", "session_id": session, "message": {"role": "assistant", "content": [block]}}

    if kind == "item.completed" and what == "agent_message" and (item.get("text") or "").strip():
        return [says({"type": "text", "text": item["text"]})]
    if kind == "item.started" and what == "command_execution":
        return [says({"type": "tool_use", "id": item.get("id"), "name": "Bash", "input": {"command": item.get("command") or ""}})]
    if kind == "item.completed" and what == "file_change":
        paths = [c.get("path") for c in item.get("changes") or [] if isinstance(c, dict) and c.get("path")]
        return [says({"type": "tool_use", "id": item.get("id"), "name": "apply_patch",
                      "input": {"file_path": ", ".join(paths), "files": paths}})]
    if kind == "item.started" and what in ("mcp_tool_call", "web_search", "collab_tool_call"):
        detail = item.get("tool") or item.get("query") or item.get("server") or ""
        return [says({"type": "tool_use", "id": item.get("id"), "name": what, "input": {"description": str(detail)}})]
    if kind == "item.completed" and what == "error" and item.get("message"):
        return [says({"type": "text", "text": f"(the client reports: {item['message']})"})]
    return []


class Turn:
    """One attempt at a turn: the child, what it said, and how it ended."""

    def __init__(self, session: str, cwd: Path, attempt: Path):
        self.session, self.cwd, self.attempt = session, cwd, attempt
        self.thread = self.last_text = self.error = None
        self.usage: dict | None = None
        self.items = 0
        self.ended = False  # a terminal event came
        self.started = time.monotonic()

    def result(self, subtype: str, text: str, model: str | None = None) -> dict:
        return {"type": "result", "subtype": subtype, "is_error": subtype != "success", "result": text,
                "session_id": self.session, "num_turns": self.items, "duration_ms": int((time.monotonic() - self.started) * 1000),
                "total_cost_usd": None,  # Codex reports tokens, not dollars: unknown stays unknown
                "usage": self.usage, "client": "codex", "thread_id": self.thread, "attempt": str(self.attempt),
                **({"model": model} if model else {})}


def attempt_path(session: str, cwd: Path, n: int) -> Path:
    folder = state_dir(cwd) / "attempts" / session
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{n:03d}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{os.getpid()}.jsonl"


def codex_argv(model: str, effort: str, last: Path, thread: str | None, cwd: Path, sandbox: str, prompt: str) -> list[str]:
    argv = [os.environ.get("AGENT_CLIENT_CODEX") or "codex", "exec", *(["resume"] if thread else []), "--json",
            "--skip-git-repo-check", "-m", model, "-c", f'model_reasoning_effort="{effort}"']
    for setting in CODEX_CONFIG:
        argv += ["-c", setting]
    # `auto` is the counterpart of the `--permission-mode auto` the loops give Claude Code: the workspace-write
    # sandbox, and a request to leave it (sync.py commit writes the repository's store, outside a sibling
    # workspace) goes to Codex's automatic review, since nobody is there to answer. These three settings are what
    # `--approve-for-me` sets, given as settings because **every turn needs them, a resumed one too**: `exec
    # resume` takes no sandbox flag and does not keep the thread's (the first live rehearsal's second cycle found
    # itself read-only with approvals off and could not commit, 2026-11-18, CLI 0.169). Tried the same day: with
    # the approval policy alone, and no reviewer, a headless turn cannot ask at all, and --add-dir does not open
    # the store. A sandbox named outright (read-only, for a role that must not write) is given as it is.
    # The network is open inside that sandbox, by the user's word (2026-11-19): a worker fetches sources and
    # dependencies as a Claude Code worker does. Without the setting a command in the sandbox resolves no host,
    # and each fetch waits on the automatic reviewer (probed that day, CLI 0.170: refused, then let through when
    # asked; with the setting, through at once).
    if sandbox == "auto":
        for setting in ('sandbox_mode="workspace-write"', 'approval_policy="on-request"', 'approvals_reviewer="auto_review"',
                        "sandbox_workspace_write.network_access=true"):
            argv += ["-c", setting]
    else:
        argv += ["-c", f'sandbox_mode="{sandbox}"']
    # A rehearsal's own settings, one to a line (a low model_auto_compact_token_limit, to see a compaction without
    # filling a window): given last, so they stand over the ones above. Not for a run that is to be relied on.
    for setting in (os.environ.get("AGENT_CLIENT_CODEX_SETTINGS") or "").splitlines():
        if setting.strip():
            argv += ["-c", setting.strip()]
    argv += ["-o", str(last)]
    # A resumed thread keeps its folder: `resume` takes none.
    if thread:
        return argv + [thread, prompt]
    return argv + ["-C", str(cwd), prompt]


PLAIN_COMMIT = re.compile(r"\b(?:jj\s+(?:commit|ci|new)|git\s+commit)\b")  # as sync.py's hook-commit reads a command


def rollout_of(thread: str) -> Path | None:
    """The file Codex keeps a thread's log in."""
    home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    found = sorted((home / "sessions").glob(f"*/*/*/rollout-*{thread}.jsonl"))
    return found[-1] if found else None


class Compactions:
    """The compactions Codex makes by itself in the middle of a turn. `exec --json` prints nothing for one (probed
    2026-11-19, CLI 0.170: five in one turn, and the stream held only the turn's items), but the thread's log gets
    a `compacted` line each time, with the size of the context it replaced. So the log is read as the turn goes:
    what was appended since the turn began, at each event of the stream and once more at its end. The loops read
    the boundary as they read Claude Code's (a moonshot's compaction with no commit is put to its watcher)."""

    def __init__(self, thread: str | None):
        self.thread, self.path, self.offset = thread, None, 0
        self.since = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())  # a resumed thread's log holds earlier ones
        self.find()
        if self.path is not None:
            self.offset = self.path.stat().st_size

    def find(self) -> None:
        if self.path is None and self.thread:
            self.path = rollout_of(self.thread)

    def new(self, session: str) -> list[dict]:
        self.find()
        if self.path is None:
            return []
        try:
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                data = f.read()
        except OSError:
            return []
        whole = data[:data.rfind(b"\n") + 1]  # a line still being written is read next time
        self.offset += len(whole)
        out = []
        for line in whole.splitlines():
            if b'"compacted"' not in line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("type") != "compacted" or str(entry.get("timestamp") or "") < self.since:
                continue
            usage = (((entry.get("payload") or {}).get("latest_token_usage_record") or {}).get("usage") or {})
            out.append({"type": "system", "subtype": "compact_boundary", "session_id": session,
                        "compact_metadata": {"trigger": "auto", "pre_tokens": usage.get("total_tokens")}})
        return out


def after_turn(cwd: Path, thread: str, model: str, committed: list[str], log: Path) -> None:
    """What this checkout's hooks do for a session, done here for a turn this ran. The hooks are Claude Code's in
    .claude/settings.json and Codex's in .codex/hooks.json, but Codex loads a project's hooks only where a person
    has trusted the project and reviewed each hook, which a fresh sibling workspace is not, and the way round that
    (--dangerously-bypass-hook-trust) would also run whatever other hooks nobody reviewed. So the two commands are
    run from here with the payload Codex's hooks give: after a commit made without sync.py, `sync.py hook-commit`
    (it gives the commit its session's trace when the commit is still the working copy's parent; otherwise the
    next sync does), and at the turn's end `sync.py hook` (finished turns to Langfuse, where that is set up). Both
    do nothing twice, so a checkout whose own hooks ran as well is none the worse. A failure is written beside
    the attempt and stops nothing: no trace depends on a hook."""
    tool, transcript = root_of(cwd) / "llm-dlc" / "tools" / "sync.py", rollout_of(thread)
    if os.environ.get("AGENT_CLIENT_HOOKS") == "off" or not tool.is_file() or transcript is None:
        return
    env, _ = child_env()
    env["CODEX_THREAD_ID"] = thread  # the session these commands are run for, as Codex names it to its own
    base = {"session_id": thread, "transcript_path": str(transcript), "cwd": str(cwd), "model": model}
    runs = [("hook-commit", {**base, "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": c}})
            for c in committed[-1:]]
    runs.append(("hook", {**base, "hook_event_name": "Stop"}))
    for name, payload in runs:
        try:
            r = subprocess.run([sys.executable, str(tool), name], input=json.dumps(payload), cwd=cwd, env=env,
                               capture_output=True, text=True, timeout=120)
            said = f"status {r.returncode}\n{r.stdout}{r.stderr}" if r.returncode or r.stdout.strip() or r.stderr.strip() else ""
        except (OSError, subprocess.TimeoutExpired) as e:
            said = f"{e}\n"
        if said:  # a hook that ran and had nothing to say leaves no file
            with open(log, "a") as out:
                out.write(f"{now()} sync.py {name}: {said}")


def cmd_run(session: str, model: str, effort: str, cwd: Path, sandbox: str, prompt: str) -> int:
    model = resolve("codex", model)
    if effort not in EFFORTS:
        raise Problem(f"{effort!r} is not an effort ({', '.join(EFFORTS)})")
    if not prompt.strip():
        raise Problem("a turn needs a text")
    before = binding(session, cwd)
    if before and before.get("client") != "codex":
        raise Problem(f"session {session} is bound to {before.get('client')}: a session keeps its client")
    n = int((before or {}).get("attempts") or 0) + 1
    attempt = attempt_path(session, cwd, n)
    last = attempt.with_suffix(".last.md")
    turn = Turn(session, cwd, attempt)
    committed: list[str] = []  # the commands of this turn that made a commit without sync.py
    compactions = Compactions((before or {}).get("thread"))
    tokens: dict | None = None  # the thread's totals, once the turn has ended
    env, parent = child_env(session)
    argv = codex_argv(model, effort, last, (before or {}).get("thread"), cwd, sandbox, prompt)
    # What this attempt was given, by digest: two clients sent the same task show the same one (the loop logs its
    # own for a Claude Code turn), and the text itself stays in the client's own log.
    given = {"prompt": {"sha256": hashlib.sha256(prompt.encode()).hexdigest(), "chars": len(prompt)}, "model": model,
             "effort": effort, "resumed": (before or {}).get("thread"), "started": now()}
    attempt.with_suffix(".given.json").write_text(json.dumps(given, indent=1) + "\n")
    try:
        child = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=open(attempt.with_suffix(".stderr"), "w"), text=True)
    except OSError as e:
        raise Problem(f"could not start {argv[0]}: {e.strerror}")
    cancelled = []

    def stop(signum, _frame):
        cancelled.append(signum)
        try:
            child.terminate()
        except OSError:
            pass

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    mismatch = None
    with open(attempt, "w") as raw:
        for line in child.stdout:
            raw.write(line)
            raw.flush()
            try:
                event = json.loads(line)
            except ValueError:
                continue  # kept in the attempt's file; a line that is not an event is not the stream's
            if not isinstance(event, dict):
                continue
            kind = event.get("type")
            if kind == "thread.started":
                turn.thread = event.get("thread_id")
                if before and before.get("thread") != turn.thread:
                    mismatch = (f"the client resumed thread {turn.thread}, and session {session} is bound to "
                                f"{before.get('thread')}: the turn was ended and the binding left as it was")
                    child.terminate()
                    break
                bind(session, cwd, client="codex", thread=turn.thread, folder=str(cwd), workspace=str(root_of(cwd)),
                     model=model, effort=effort, attempts=n, attempt=str(attempt),
                     **({"started": now()} if not before else {}), **({"parent": parent} if parent else {}))
                emit({"type": "system", "subtype": "init", "session_id": session, "client": "codex",
                      "thread_id": turn.thread, "model": model, "cwd": str(cwd)})
                continue
            if kind in ("item.started", "item.completed"):
                item = event.get("item") or {}
                turn.items += kind == "item.completed"
                if kind == "item.completed" and item.get("type") == "agent_message" and (item.get("text") or "").strip():
                    turn.last_text = item["text"]
                if (kind == "item.completed" and item.get("type") == "command_execution" and item.get("exit_code") == 0
                        and PLAIN_COMMIT.search(item.get("command") or "")):
                    committed.append(item["command"])
            elif kind == "turn.completed":
                own, tokens = turn_tokens(event.get("usage") or {}, (before or {}).get("tokens"))
                turn.usage = usage_of(own)
                turn.ended = True
            elif kind in ("turn.failed", "error"):
                err = event.get("error") if isinstance(event.get("error"), dict) else event
                turn.error = str(err.get("message") or err)[:2000]
                turn.ended = turn.ended or kind == "turn.failed"
            compactions.thread = compactions.thread or turn.thread
            for out in compactions.new(session) + translate(event, session):
                emit(out)
    code = child.wait()
    for out in compactions.new(session):
        emit(out)
    if before or turn.thread:
        bind(session, cwd, attempts=n, attempt=str(attempt), last={"ended": now(), "exit": code, "result": turn.ended and not turn.error},
             **({"tokens": tokens} if tokens else {}))
    if turn.thread and not mismatch and not cancelled:
        after_turn(cwd, turn.thread, model, committed, attempt.with_suffix(".hooks.log"))
    try:
        final = last.read_text().strip()
    except OSError:
        final = ""
    final = final or (turn.last_text or "").strip()
    if mismatch:
        emit(turn.result("error_mismatched_thread", mismatch, model))
        print(f"agent_client.py: {mismatch}", file=sys.stderr)
        return 1
    if cancelled:
        emit(turn.result("error_cancelled", final or "the turn was cancelled before it ended", model))
        return 128 + cancelled[0]
    if turn.error:
        emit(turn.result("error_during_execution", turn.error, model))
        print(f"agent_client.py: the turn failed: {turn.error} (attempt: {attempt})", file=sys.stderr)
        return code or 1
    if not turn.ended:
        why = f"the client exited with status {code} and no result: its events and stderr are in {attempt.parent}"
        emit(turn.result("error_no_result", why, model))
        print(f"agent_client.py: {why}", file=sys.stderr)
        return code or 1
    emit(turn.result("success", final, model))
    return 0


# -- compaction, through the app server

def cmd_compact(session: str, cwd: Path, timeout: float) -> int:
    bound = binding(session, cwd)
    if not bound or bound.get("client") != "codex":
        raise Problem(f"session {session} has no Codex thread here to compact")
    thread = bound["thread"]
    turn = Turn(session, cwd, attempt_path(session, cwd, int(bound.get("attempts") or 0)).with_suffix(".compact.jsonl"))
    turn.thread = thread
    env, _ = child_env()
    try:
        server = subprocess.Popen([os.environ.get("AGENT_CLIENT_CODEX") or "codex", "app-server"], cwd=cwd, env=env,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=open(turn.attempt.with_suffix(".stderr"), "w"))
    except OSError as e:
        raise Problem(f"could not start the app server: {e.strerror}")
    raw = open(turn.attempt, "w")
    until = time.monotonic() + timeout

    pending = [b""]  # what was read past the last whole line: select() sees the pipe, not a reader's buffer

    def send(message: dict) -> None:
        server.stdin.write((json.dumps(message) + "\n").encode())
        server.stdin.flush()

    def read(match) -> dict | None:
        fd = server.stdout.fileno()
        while time.monotonic() < until:
            if b"\n" not in pending[0]:
                ready, _, _ = select.select([fd], [], [], 1)
                if not ready:
                    if server.poll() is not None:
                        return None
                    continue
                chunk = os.read(fd, 65536)
                if not chunk:
                    return None
                pending[0] += chunk
                continue
            data, _, pending[0] = pending[0].partition(b"\n")
            line = data.decode(errors="replace")
            raw.write(line + "\n")
            raw.flush()
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if isinstance(message, dict) and (match(message) or "error" in message and message.get("id") in (1, 2, 3)):
                return message
        return None

    problem = None
    try:
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "in-the-loop", "title": "in-the-loop loop runner", "version": "1"}}})
        if not (m := read(lambda m: m.get("id") == 1)) or "error" in m:
            problem = f"the app server did not start a connection ({(m or {}).get('error') or 'no answer'})"
        if not problem:
            send({"method": "initialized"})
            send({"id": 2, "method": "thread/resume", "params": {"threadId": thread, "cwd": str(cwd), "excludeTurns": True}})
            if not (m := read(lambda m: m.get("id") == 2)) or "error" in m:
                problem = f"thread {thread} could not be resumed ({(m or {}).get('error') or 'no answer'})"
        if not problem:
            send({"id": 3, "method": "thread/compact/start", "params": {"threadId": thread}})
            done = lambda m: (m.get("method") == "item/completed" and ((m.get("params") or {}).get("item") or {}).get("type") == "contextCompaction") \
                or m.get("method") == "thread/compacted" \
                or (m.get("method") == "turn/completed" and ((m.get("params") or {}).get("turn") or {}).get("status") != "completed")
            m = read(done)
            if not m or "error" in m:
                problem = f"the compaction was not confirmed ({(m or {}).get('error') or 'no answer in time'})"
            elif m.get("method") == "turn/completed":
                problem = f"the compaction's turn ended {m['params']['turn'].get('status')}: {m['params']['turn'].get('error')}"
            else:
                read(lambda m: m.get("method") == "turn/completed")  # let it settle before the server goes
    finally:
        raw.close()
        try:
            server.stdin.close()
            server.terminate()
            server.wait(10)
        except (OSError, subprocess.TimeoutExpired):
            server.kill()
    emit({"type": "system", "subtype": "init", "session_id": session, "client": "codex", "thread_id": thread})
    if problem:
        emit(turn.result("error_during_execution", problem))
        print(f"agent_client.py: {problem} (see {turn.attempt})", file=sys.stderr)
        return 1
    bind(session, cwd, compacted=now())
    emit({"type": "system", "subtype": "compact_boundary", "session_id": session, "compact_metadata": {"trigger": "manual"}})
    emit(turn.result("success", "compacted"))
    return 0


# -- whether the client is given this checkout's instructions

def instructions(cwd: Path) -> dict:
    root = root_of(cwd)
    source = root / INSTRUCTIONS
    out = {"client": "codex", "root": str(root), "sources": [], "problems": [],
           "environment": {"removed": [*PARENT_MARKERS, *RUN_NAMES, *(f"{p}*" for p in RUN_PREFIXES)],
                           "TMPDIR": str(tmp_of("SESSION"))}}
    if not source.is_file():
        out["problems"].append(f"{source} is not there")
        return out
    text = source.read_bytes()
    out["sources"].append({"path": str(source), "bytes": len(text), "sha256": hashlib.sha256(text).hexdigest()})
    for name in NOTES:  # what the instructions send a session to read: the same file for both clients
        if (root / name).is_file():
            data = (root / name).read_bytes()
            out["sources"].append({"path": str(root / name), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            if name not in text.decode(errors="replace"):
                out["problems"].append(f"{name} is there and {INSTRUCTIONS} does not name it: no session is sent to read it")
    folder = cwd
    while True:
        for name in SHADOWS:
            if (folder / name).exists():
                out["problems"].append(f"{folder / name} shadows {INSTRUCTIONS}: Codex reads it first")
        if folder == root or folder == folder.parent:
            break
        folder = folder.parent
    if len(text) > DOC_BUDGET:
        out["problems"].append(f"{INSTRUCTIONS} is {len(text)} bytes, over Codex's budget of {DOC_BUDGET}: its end would be cut")
    env, _ = child_env()
    argv = [os.environ.get("AGENT_CLIENT_CODEX") or "codex", "debug", "prompt-input"]
    for setting in CODEX_CONFIG:
        argv += ["-c", setting]
    try:
        r = subprocess.run(argv + ["parity check"], cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        out["problems"].append(f"the client's prompt could not be rendered ({e})")
        return out
    rendered = r.stdout
    try:  # the text as the model would see it, whatever the JSON escaping
        rendered = "\n".join(_strings(json.loads(r.stdout)))
    except ValueError:
        pass
    out["skills"] = skills(root, rendered, out["problems"], out["sources"])
    lines = [line.strip() for line in text.decode(errors="replace").splitlines() if len(line.strip()) >= 40]
    markers = {"first": lines[0], "last": lines[-1]} if lines else {}
    out["delivered"] = {name: marker in rendered for name, marker in markers.items()}
    if r.returncode != 0:
        out["problems"].append(f"the client's prompt could not be rendered (status {r.returncode})")
    elif not all(out["delivered"].values()) or not markers:
        missing = [name for name, found in out["delivered"].items() if not found]
        out["problems"].append(f"the client's prompt does not hold {INSTRUCTIONS}'s {' and '.join(missing) or 'text'} line: it is skipped or cut")
    return out


def skills(root: Path, rendered: str, problems: list[str], sources: list[dict]) -> dict:
    """The checkout's skills as Codex finds them: each `.claude/skills/NAME` is the one source, reached through a
    relative link at `.agents/skills/NAME`, and a skill only the user may start (`disable-model-invocation: true`)
    has the same word for Codex beside it (`agents/openai.yaml`, `allow_implicit_invocation: false`), so a work
    turn cannot pick up publishing or review authority by choosing the skill itself. Where the client's prompt
    lists skills, each is checked against it."""
    out = {}
    listing = "/SKILL.md" in rendered
    folder = root / ".claude" / "skills"
    for skill in sorted(folder.iterdir()) if folder.is_dir() else []:
        body = skill / "SKILL.md"
        if not body.is_file():
            continue
        data = body.read_bytes()
        sources.append({"path": str(body), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        head = data.decode(errors="replace").split("\n---", 1)[0]
        user_only = re.search(r"^disable-model-invocation:\s*true\s*$", head, re.M) is not None
        link = root / ".agents" / "skills" / skill.name
        linked = link.is_symlink() and not os.path.isabs(os.readlink(link)) and link.resolve() == skill.resolve()
        try:
            policy = re.search(r"^\s*allow_implicit_invocation:\s*false\s*$", (skill / "agents" / "openai.yaml").read_text(), re.M) is not None
        except OSError:
            policy = False
        listed = f"/{skill.name}/SKILL.md" in rendered if listing else None
        out[skill.name] = {"linked": linked, "userOnly": user_only, **({"listed": listed} if listing else {})}
        if not linked:
            problems.append(f"the skill {skill.name} has no relative link at .agents/skills/{skill.name}: Codex does not find it")
        if user_only != policy:
            problems.append(f"the skill {skill.name} is {'for the user alone to start' if user_only else 'one a session may start'} "
                            f"in SKILL.md, and its agents/openai.yaml says otherwise: the two clients would differ")
        if listing and linked and listed == user_only:
            problems.append(f"the skill {skill.name} is {'offered to' if listed else 'not offered to'} Codex's work turns, "
                            f"against what its SKILL.md says")
    return out


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)

    def common(p, session=True, client=True):
        if client:
            p.add_argument("--client", choices=CLIENTS, required=True)
        if session:
            p.add_argument("--session", required=True)
        p.add_argument("--cwd", default=".")

    r = sub.add_parser("run")
    common(r)
    r.add_argument("--model", required=True)
    r.add_argument("--effort", required=True)
    r.add_argument("--sandbox", default=os.environ.get("AGENT_CLIENT_SANDBOX") or "auto",
                   help="auto (the default: workspace-write, requests to leave it reviewed automatically), or a "
                        "Codex sandbox named outright: read-only, workspace-write")
    r.add_argument("prompt", help="the turn's text; - reads it from stdin")
    c = sub.add_parser("compact")
    common(c)
    c.add_argument("--timeout", type=float, default=900)
    common(sub.add_parser("exists"))
    common(sub.add_parser("binding"), client=False)
    common(sub.add_parser("thread"), client=False)
    common(sub.add_parser("instructions"), session=False)
    v = sub.add_parser("resolve")
    v.add_argument("--client", choices=CLIENTS, required=True)
    v.add_argument("model")
    p = sub.add_parser("plan")
    p.add_argument("--client", choices=CLIENTS, required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--effort", required=True)
    a = ap.parse_args(argv)
    try:
        if a.command == "resolve":
            print(resolve(a.client, a.model))
            return 0
        if a.command == "plan":
            print(json.dumps(plan(a.client, a.model, a.effort)))
            return 0
        cwd = Path(a.cwd).resolve()
        if a.command == "thread":  # the Codex thread a loop's session is bound to, for the loop's record
            bound = binding(a.session, cwd) or {}
            if not bound.get("thread"):
                return 1
            print(bound["thread"])
            return 0
        if a.command == "binding":
            print(json.dumps(binding(a.session, cwd), indent=1))
            return 0
        if a.command == "instructions":
            out = instructions(cwd)
            print(json.dumps(out, indent=1))
            return 1 if out["problems"] else 0
        if not SESSION.fullmatch(a.session):
            raise Problem(f"not a session id: {a.session}")
        if a.client != "codex":
            raise Problem("Claude Code's turns are started by the loops themselves, as they always were: this runs Codex's")
        if a.command == "exists":
            return 0 if binding(a.session, cwd) else 1
        if a.command == "compact":
            return cmd_compact(a.session, cwd, a.timeout)
        prompt = sys.stdin.read() if a.prompt == "-" else a.prompt
        return cmd_run(a.session, a.model, a.effort, cwd, a.sandbox, prompt)
    except Problem as e:
        print(f"agent_client.py: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

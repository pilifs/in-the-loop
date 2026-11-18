#!/usr/bin/env python3
"""A stand-in for the `codex` client, for the tests of agent_client.py and of the loops that use it: it speaks
what Codex CLI 0.169 spoke on 2026-11-18 (`exec --json` events, `exec resume`, `exec fork`, `queue`, the app server's
`thread/compact/start`, `debug prompt-input`) and calls no model. Tests point AGENT_CLIENT_CODEX at this file.

    CODEX_STANDIN_STATE   a folder for its threads and its call count
    CODEX_STANDIN_LOG     a file that gets one JSON line per call: argv, cwd, and the parent identity it was given
    CODEX_STANDIN_MODES   what each `exec` call does, in order, comma-separated (the last again when used up):
                          ok        an answer and a command
                          commit    writes work.txt and commits it with jj, then answers
                          idle      answers and changes nothing
                          fail      the turn fails as a quota error does (turn.failed)
                          truncated broken lines, then the stream ends with no result
                          hang      starts a turn and waits to be stopped
                          mismatch  on a resume, reports another thread than the one asked for
                          compacts  the thread compacts itself in the middle of the turn
    CODEX_STANDIN_COMPACT `fail` makes the app server refuse a compaction
    CODEX_HOME            with it, a thread's log is started there as Codex names one (sessions/Y/M/D/rollout-*-THREAD.jsonl)
    CODEX_STANDIN_PROMPT  a file whose text `debug prompt-input` renders (the folder's CLAUDE.md without one)
"""
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

VALUE_FLAGS = {"-m", "-c", "-o", "-C", "-s", "--model", "--config", "--sandbox", "--cd", "--output-last-message",
               "--thread", "--message"}
state = Path(os.environ.get("CODEX_STANDIN_STATE") or ".")
state.mkdir(parents=True, exist_ok=True)


def say(event):
    print(json.dumps(event), flush=True)


def log(argv):
    if os.environ.get("CODEX_STANDIN_LOG"):
        with open(os.environ["CODEX_STANDIN_LOG"], "a") as f:
            f.write(json.dumps({"argv": argv, "cwd": os.getcwd(),
                                "identity": sorted(k for k in os.environ if k in ("CLAUDECODE", "CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID")),
                                "tmp": os.environ.get("TMPDIR"),
                                "run": sorted(k for k in os.environ if k.startswith(("RUN_STREAMS_", "FEATURE_LOOP_", "LOOP_WATCH_", "PROVE_LOOP_"))
                                              or k == "LOOP_CONDUCTOR")}) + "\n")


def parse(argv):
    """(options with their values, flags, positionals) of an `exec` call."""
    options, flags, rest, i = {}, [], [], 0
    while i < len(argv):
        a = argv[i]
        if a in VALUE_FLAGS:
            options.setdefault(a, []).append(argv[i + 1])
            i += 2
        elif a.startswith("-"):
            flags.append(a)
            i += 1
        else:
            rest.append(a)
            i += 1
    return options, flags, rest


def next_mode():
    modes = (os.environ.get("CODEX_STANDIN_MODES") or "ok").split(",")
    counter = state / "calls"
    n = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(n + 1))
    return modes[min(n, len(modes) - 1)]


def run_exec(argv):
    options, flags, rest = parse(argv)
    resume = bool(rest) and rest[0] == "resume"
    fork = bool(rest) and rest[0] == "fork"
    rest = rest[1:] if resume or fork else rest
    mode = next_mode()
    if fork:  # a new thread that starts from another session, which is left as it was
        thread, prompt = str(uuid.uuid4()), rest[1]
        (state / f"thread-{thread}.forked-from").write_text(rest[0] + "\n")
    elif resume:
        thread, prompt = rest[0], rest[1]
        if not (state / f"thread-{thread}").exists():
            print(f"no session {thread}", file=sys.stderr)
            return 1
        if mode == "mismatch":
            thread = str(uuid.uuid4())
    else:
        thread, prompt = str(uuid.uuid4()), rest[0]
    turns = state / f"thread-{thread}"
    n = (int(turns.read_text()) if turns.exists() else 0) + 1
    turns.write_text(str(n))
    if os.environ.get("CODEX_HOME"):  # the log Codex keeps of a thread, as far as a hook's payload needs one
        day = Path(os.environ["CODEX_HOME"]) / "sessions" / "2026" / "01" / "01"
        day.mkdir(parents=True, exist_ok=True)
        with open(day / f"rollout-2026-01-01T00-00-00-{thread}.jsonl", "a") as f:
            f.write(json.dumps({"timestamp": "2026-01-01T00:00:00.000Z", "type": "session_meta",
                                "payload": {"id": thread, "cwd": os.getcwd(), "cli_version": "stand-in"}}) + "\n")
    say({"type": "thread.started", "thread_id": thread})
    say({"type": "turn.started"})
    if mode == "hang":
        time.sleep(600)
        return 1
    if mode == "truncated":
        print('{"type": "item.completed", "item": {"id": "item_0", "type": "agent_me', flush=True)
        print("not an event at all", flush=True)
        return 0
    if mode == "fail":
        say({"type": "error", "message": "You've hit your usage limit. Try again later."})
        say({"type": "turn.failed", "error": {"message": "You've hit your usage limit. Try again later."}})
        return 1
    say({"type": "item.completed", "item": {"id": "item_0", "type": "agent_message", "text": f"Starting turn {n}."}})
    if mode == "compacts":
        say({"type": "item.completed", "item": {"id": "item_c", "type": "context_compaction"}})
    command = "jj commit" if mode == "commit" else "true"
    say({"type": "item.started", "item": {"id": "item_1", "type": "command_execution", "command": f"/bin/bash -lc '{command}'",
                                           "aggregated_output": "", "exit_code": None, "status": "in_progress"}})
    if mode == "commit":
        Path("work.txt").write_text(f"turn {n} of thread {thread}\n")
        subprocess.run(["jj", "--quiet", "describe", "-m", f"Made-up work by the stand-in, turn {n}"], check=True)
        subprocess.run(["jj", "--quiet", "new"], check=True)
        say({"type": "item.completed", "item": {"id": "item_p", "type": "file_change", "changes": [{"path": "work.txt", "kind": "add"}], "status": "completed"}})
    say({"type": "item.completed", "item": {"id": "item_1", "type": "command_execution", "command": f"/bin/bash -lc '{command}'",
                                             "aggregated_output": "", "exit_code": 0, "status": "completed"}})
    final = f"the stand-in's report of turn {n} ({mode}); it was told: {prompt[:200]}"
    say({"type": "item.completed", "item": {"id": "item_2", "type": "agent_message", "text": final}})
    for path in options.get("-o", []):
        Path(path).write_text(final + "\n")
    say({"type": "turn.completed", "usage": {"input_tokens": 1000 * n, "cached_input_tokens": 600 * n, "cache_write_input_tokens": 0,
                                              "output_tokens": 40 * n, "reasoning_output_tokens": 7 * n}})  # the thread's totals, as Codex gives
    return 0


def app_server():
    for line in sys.stdin:
        try:
            m = json.loads(line)
        except ValueError:
            continue
        method, mid = m.get("method"), m.get("id")
        if method == "initialize":
            say({"id": mid, "result": {"userAgent": "stand-in"}})
        elif method == "thread/resume":
            thread = m["params"]["threadId"]
            if not (state / f"thread-{thread}").exists():
                say({"id": mid, "error": {"code": -32600, "message": f"no thread {thread}"}})
            else:
                say({"id": mid, "result": {"thread": {"id": thread}}})
        elif method == "thread/compact/start":
            thread = m["params"]["threadId"]
            if os.environ.get("CODEX_STANDIN_COMPACT") == "fail":
                say({"id": mid, "error": {"code": -32000, "message": "compaction is not available"}})
                continue
            say({"id": mid, "result": {}})
            say({"method": "item/started", "params": {"item": {"type": "contextCompaction", "id": "c1"}, "threadId": thread}})
            with open(state / "compacted", "a") as f:
                f.write(thread + "\n")
            say({"method": "item/completed", "params": {"item": {"type": "contextCompaction", "id": "c1"}, "threadId": thread}})
            say({"method": "turn/completed", "params": {"threadId": thread, "turn": {"status": "completed", "error": None}}})
    return 0


def prompt_input():
    source = os.environ.get("CODEX_STANDIN_PROMPT")
    try:
        text = Path(source).read_text() if source else Path("CLAUDE.md").read_text()
    except OSError:
        text = ""
    print(json.dumps([{"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "base instructions"}]},
                      {"type": "message", "role": "user", "content": [{"type": "input_text", "text": text}]}]))
    return 0


def main():
    argv = sys.argv[1:]
    log(argv)
    if argv[:1] == ["exec"]:
        return run_exec(argv[1:])
    if argv[:1] == ["queue"]:
        options, _, _ = parse(argv[1:])
        with open(state / "queued", "a") as f:
            f.write(json.dumps({"thread": options["--thread"][0], "message": options["--message"][0]}) + "\n")
        return 0
    if argv[:1] == ["app-server"]:
        return app_server()
    if argv[:2] == ["debug", "prompt-input"]:
        return prompt_input()
    print(f"the stand-in knows no `codex {' '.join(argv[:2])}`", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())

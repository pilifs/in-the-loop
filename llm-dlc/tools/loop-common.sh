# What feature-loop.sh sources from the root of the repo: log lines, and the live display
# of a turn with its compaction watch.

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*"; }

# Print each stream-json event as it arrives: a turn in text mode stays silent
# until it ends, which can be hours. This only displays, so it must outlive any
# line it cannot read, or a closed pipe would kill claude.
show_progress() {
  python3 -u -c '
import json, os, signal, subprocess, sys, threading, time

def say(text):
    print(time.strftime("[%F %T]"), text, flush=True)

# feature-loop.sh sets these during a turn it watches: a compaction
# with no commit since LOOP_WATCH_BASE (the change at @- when the cycle began, then
# at the last compaction) is put to the conductor when there is one (LOOP_CONDUCTOR,
# a directory, see llm-dlc/tools/conductor.py). The turn ends, with LOOP_WATCH_MARK
# saying why, on a stop from the conductor, or by rule where LOOP_WATCH_STOP is set and
# no conductor answers. Otherwise the compaction is only logged.
base = os.environ.get("LOOP_WATCH_BASE")
stop_rule = bool(os.environ.get("LOOP_WATCH_STOP"))
conductor_dir = os.environ.get("LOOP_CONDUCTOR")
conductor_wait = int(os.environ.get("FEATURE_LOOP_CONDUCTOR_WAIT") or 900)
over = threading.Event()  # the turn has ended by itself
waiter = None

def last_change():
    # Without a snapshot: the working copy is the session at work.
    r = subprocess.run(["jj", "log", "--ignore-working-copy", "--no-graph", "-r", "@-", "-T", "change_id"],
                       capture_output=True, text=True, timeout=120)
    return r.stdout.strip() if r.returncode == 0 else None

def tree(pid):
    # The process and its descendants, so a test run it started does not outlive the turn.
    found = [pid]
    try:
        for task in os.listdir("/proc/%d/task" % pid):
            with open("/proc/%d/task/%s/children" % (pid, task)) as f:
                for child in f.read().split():
                    found += tree(int(child))
    except OSError:
        pass
    return found

def end_turn(why):
    # The reason first: the loop reads the mark once the turn is over.
    with open(os.environ["LOOP_WATCH_MARK"], "w") as f:
        f.write(why + "\n")
    try:
        with open(os.environ["LOOP_WATCH_PID"]) as f:
            pids = tree(int(f.read().strip()))
        os.kill(pids[0], signal.SIGTERM)
        for pid in pids[1:]:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        say("ending the turn: %s" % why)
    except (OSError, ValueError) as err:
        say("%s, but the turn could not be ended: %s" % (why, err))

def keep(text):
    # For the run record, under the line of the cycle once it has one.
    if os.environ.get("LOOP_WATCH_NOTES"):
        with open(os.environ["LOOP_WATCH_NOTES"], "a") as f:
            f.write(text + "\n")

def ask_conductor(at, tokens, since):
    # A session outside the loop judges; the turn goes on while it does. Its stop ends the
    # turn. Its silence until the deadline leaves the turn running, as in a loop with no
    # conductor, unless the rule is on.
    sys.path.insert(0, "llm-dlc/tools")
    import conductor
    from pathlib import Path
    directory = Path(conductor_dir)
    asked = conductor.append_event(
        directory, type="compaction", needsVerdict=True, commitSince=False, tokens=tokens, since=since,
        cycle=os.environ.get("LOOP_WATCH_CYCLE"),
        session=os.environ.get("LOOP_WATCH_SESSION"), transcript=os.environ.get("LOOP_WATCH_TRANSCRIPT"),
        deadline=time.time() + conductor_wait,
        question="The session compacted itself with no commit since change %s (where the cycle began, or the last "
                 "compaction was). Is the work moving, or is the session stuck?" % since[:12])
    say("compacted with no commit%s: asking the conductor (event %s), for up to %s s" % (at, asked["n"], conductor_wait))

    def wait():
        global base
        verdict = None
        while verdict is None and time.time() < asked["deadline"] and not over.is_set():
            verdict = conductor.read_verdict(directory, asked["n"])
            if verdict is None:
                over.wait(1)
        if verdict is None:  # once more: the answer and the end of the turn can come together
            verdict = conductor.read_verdict(directory, asked["n"])
        if verdict and verdict["verdict"] == "continue":
            say("the conductor says continue: %s" % verdict["reason"])
            keep("compacted with no commit%s; the conductor let the turn go on: %s" % (at, verdict["reason"]))
            base = since  # the next compaction with no commit asks again
        elif verdict and over.is_set():
            # Nothing left to end, but the loop stops: the mark is what it reads.
            with open(os.environ["LOOP_WATCH_MARK"], "w") as f:
                f.write("compacted with no commit%s, and the conductor said stop: %s\n" % (at, verdict["reason"]))
            say("the conductor says stop, after the turn had ended: %s" % verdict["reason"])
        elif verdict:
            end_turn("compacted with no commit%s, and the conductor said stop: %s" % (at, verdict["reason"]))
        elif over.is_set():
            conductor.append_event(directory, type="withdrawn", event=asked["n"],
                                   note="the turn ended by itself before a verdict came: nothing to judge")
            say("the turn ended before the conductor answered event %s" % asked["n"])
        elif stop_rule:
            end_turn("compacted with no commit%s, and no verdict came from the conductor in %s s" % (at, conductor_wait))
        else:
            say("no verdict from the conductor in %s s: the turn goes on, as in a loop without one" % conductor_wait)
            keep("compacted with no commit%s; no verdict came from the conductor in %s s, and the turn went on" % (at, conductor_wait))
            base = since

    global waiter
    waiter = threading.Thread(target=wait, daemon=True)
    waiter.start()

def compacted(e):
    global base
    meta = e.get("compact_metadata") or e.get("compactMetadata") or {}
    trigger = meta.get("trigger", "auto")
    tokens = meta.get("pre_tokens") or meta.get("preTokens")
    at = " at %s tokens" % tokens if tokens else ""
    say("compacted (%s)%s" % (trigger, at))
    if not base or trigger == "manual":
        return
    now = last_change()
    if now is None:
        say("could not read the last commit after the compaction; going on")
    elif now != base:
        base = now
    else:
        base = None  # one question at a time: a compaction while it is open asks nothing
        if conductor_dir:
            try:
                ask_conductor(at, tokens, now)
                return
            except Exception as err:
                say("the conductor could not be asked (%s)" % err)
        if stop_rule:
            end_turn("compacted with no commit%s" % at)
        else:
            base = now

def event(e):
    if e.get("type") == "assistant":
        sub = "subagent " if e.get("parent_tool_use_id") else ""
        for block in e["message"]["content"]:
            if block.get("type") == "text" and block["text"].strip():
                say(sub + "says: " + block["text"].strip())
            elif block.get("type") == "tool_use":
                i = block.get("input") or {}
                detail = i.get("description") or i.get("file_path") or i.get("command") or ""
                detail = " ".join(str(detail).split())[:100]
                say("%s%s: %s" % (sub, block.get("name"), detail))
    elif e.get("type") == "system" and e.get("subtype") == "compact_boundary":
        compacted(e)
    elif e.get("type") == "system" and e.get("subtype") == "task_notification":
        say("background task %s: %s" % (e.get("status", "done"), " ".join(str(e.get("summary", "")).split())[:100]))
    elif e.get("type") == "result":
        if "total_cost_usd" in e and e["total_cost_usd"] is None:
            # A client that reports tokens and no dollars (Codex): unknown stays unknown, and no figure is printed
            # that a reader of this line would add up.
            u = e.get("usage") or {}
            read = (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
            say("turn done: %s, %s steps, %.1f min, cost unknown (%s: %s tokens in, %s out)" % (
                e.get("subtype"), e.get("num_turns"), e.get("duration_ms", 0) / 60000,
                e.get("client") or "client", read, u.get("output_tokens") or 0))
        else:
            say("turn done: %s, %s steps, %.1f min, $%.2f" % (
                e.get("subtype"), e.get("num_turns"),
                e.get("duration_ms", 0) / 60000, e.get("total_cost_usd", 0)))

try:
    for line in sys.stdin:
        try:
            event(json.loads(line))
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
except KeyboardInterrupt:
    pass
# A question still open when the turn ends is settled before the loop reads what came of it.
over.set()
if waiter is not None:
    waiter.join(10)
'
}

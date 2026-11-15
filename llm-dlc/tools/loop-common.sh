# Shared by feature-loop.sh and verification-loop.sh, which source it from the
# root of the repo.

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*"; }

# Print each stream-json event as it arrives: a turn in text mode stays silent
# until it ends, which can be hours. This only displays, so it must outlive any
# line it cannot read, or a closed pipe would kill claude.
show_progress() {
  python3 -u -c '
import json, os, signal, subprocess, sys, time

def say(text):
    print(time.strftime("[%F %T]"), text, flush=True)

# feature-loop.sh sets these during a moonshot instruction: a compaction with no
# commit since LOOP_WATCH_BASE (the change at @- when the cycle began, then at the
# last compaction) ends the turn, and LOOP_WATCH_MARK says why.
base = os.environ.get("LOOP_WATCH_BASE")

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
        with open(os.environ["LOOP_WATCH_MARK"], "w") as f:
            f.write("compacted with no commit%s\n" % at)
        try:
            with open(os.environ["LOOP_WATCH_PID"]) as f:
                pids = tree(int(f.read().strip()))
            os.kill(pids[0], signal.SIGTERM)
            for pid in pids[1:]:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
            say("no commit since the cycle began or the last compaction: ending the turn")
        except (OSError, ValueError) as err:
            say("no commit since the last compaction, but the turn could not be ended: %s" % err)
        base = None

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
'
}

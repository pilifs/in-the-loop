#!/usr/bin/env bash
# Repeat one instruction unattended, chosen by name.
#
# Each cycle resumes one Claude Code session and runs: instruction, commit, compact.
# A cycle that leaves no new commit stops the loop, before compacting, so the
# session keeps its full context for the person who has to look at why.
#
# The loop re-executes itself in a systemd scope with a memory cap, so a proof
# that runs away is killed alone and cannot exhaust the machine.
#
# Usage: [FEATURE_LOOP_MEMORY_MAX=4G] llm-dlc/tools/feature-loop.sh PROMPT
#   features  add features and examples to jvmcontract
#   tla       add advanced TLA examples
#
# To end the loop after the current cycle (commit and compact), type `stop` and
# Enter in its terminal while it runs; `resume` takes that back. From elsewhere,
# `touch $STOP_FILE` does the same as `stop`.
#
# Exits 0 when stopped on request, 1 when a cycle made no commit or the scope
# cannot start, 2 for a bad argument, and 130 if interrupted.

set -uo pipefail

SESSION_ID=360e8b8b-8e0c-4b2a-bd69-25b32f2a54eb
MODEL=claude-fable-5-1
EFFORT=high
MEMORY_MAX=${FEATURE_LOOP_MEMORY_MAX:-4G}
SCOPE=feature-loop
STOP_FILE=${XDG_RUNTIME_DIR:-/tmp}/feature-loop.stop

PROMPT=$*
case "$PROMPT" in
  features)
    INSTRUCTION="Add more advanced features along with examples to the jvmcontract library."
    ;;
  tla)
    INSTRUCTION="Add more advanced examples showcasing verification of TLA specs"
    ;;
  *)
    echo "usage: feature-loop.sh features|tla" >&2
    exit 2
    ;;
esac

# Claude Code files a session under the directory it ran in, and the instruction
# is meant for the root of the repo, so run there whatever the caller's directory.
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*"; }

# Shells on WSL sit in init.scope, where an out-of-memory kill can take the whole
# instance down, so the loop moves to a scope of its own. Everything it starts
# inherits the cap, including jbmc, TLC and any Gradle daemon. OOMPolicy=continue
# matters: under the default, systemd stops the scope on the first kill, and
# claude dies with the proof instead of seeing it fail. Without swap the cap is
# exact, and a process over it is killed rather than left thrashing.
contain() {
  grep -q "/$SCOPE\.scope\$" /proc/self/cgroup && return

  # The scope outlives the loop while anything in it runs, such as a Gradle daemon.
  if systemctl --user is-active --quiet "$SCOPE.scope"; then
    log "$SCOPE.scope is active: another loop, or processes left by the last one"
    log "to clear it: systemctl --user stop $SCOPE.scope"
    exit 1
  fi

  # A cap above what is free only protects the loop from itself.
  local available wanted
  available=$(awk '/^MemAvailable:/ { print $2 * 1024 }' /proc/meminfo)
  wanted=$(numfmt --from=iec "$MEMORY_MAX") || exit 1
  if (( available < wanted )); then
    log "$MEMORY_MAX cap, but only $(numfmt --to=iec "$available") is available"
    log "stop the Docker services, or lower FEATURE_LOOP_MEMORY_MAX"
    exit 1
  fi

  log "starting in $SCOPE.scope with a $MEMORY_MAX cap"
  exec systemd-run --user --scope --quiet --collect --unit="$SCOPE" \
    -p MemoryMax="$MEMORY_MAX" -p MemorySwapMax=0 -p OOMPolicy=continue \
    "$BASH" llm-dlc/tools/feature-loop.sh "$PROMPT"
}
contain

# A stop asked for before this run started is not meant for it.
rm -f "$STOP_FILE"

# Read the terminal in the background, so a request to stop can be typed while
# claude works. claude gets /dev/null as its input, or it would compete for the
# lines. A background job's input is /dev/null unless redirected, hence fd 3.
reader=
if [[ -t 0 ]]; then
  exec 3<&0
  (
    while read -r line <&3; do
      case "${line,,}" in
        stop | q | quit)
          touch "$STOP_FILE"
          log "stop requested: the loop ends after this cycle (type resume to take it back)"
          ;;
        resume | continue)
          rm -f "$STOP_FILE"
          log "stop withdrawn: the loop carries on"
          ;;
        "") ;;
        *) log "type stop to end the loop after this cycle, or resume to take that back" ;;
      esac
    done
  ) &
  reader=$!
  exec 3<&-
fi

cleanup() {
  [[ -n "$reader" ]] && kill "$reader" 2>/dev/null
  rm -f "$STOP_FILE"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# `auto` is the mode this session has always run in. With -p nobody can answer a
# prompt, so anything auto mode would ask about is denied rather than left hanging.
run_claude() {
  claude -p "$1" --resume "$SESSION_ID" --model "$MODEL" --effort "$EFFORT" \
    --permission-mode auto --output-format stream-json --verbose </dev/null | show_progress
}

# Print each stream-json event as it arrives: a turn in text mode stays silent
# until it ends, which can be hours. This only displays, so it must outlive any
# line it cannot read, or a closed pipe would kill claude.
show_progress() {
  python3 -u -c '
import json, sys, time

def say(text):
    print(time.strftime("[%F %T]"), text, flush=True)

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

# `sync.py commit` finishes @ and starts an empty change, so a commit moves @-.
# Change IDs, unlike commit IDs, survive a rewrite of the commit.
last_change() { jj log --no-graph -r @- -T change_id; }

log "type stop and Enter to end the loop after the current cycle"
cycle=0
while :; do
  cycle=$((cycle + 1))
  before=$(last_change) || exit 1

  log "cycle $cycle: $PROMPT instruction"
  run_claude "$INSTRUCTION" || log "cycle $cycle: claude exited with status $?"

  after=$(last_change) || exit 1
  if [[ "$after" == "$before" ]]; then
    log "cycle $cycle: no commit, stopping; session $SESSION_ID needs attention"
    exit 1
  fi
  log "cycle $cycle: committed $(jj log --no-graph -r @- -T 'description.first_line()')"

  log "cycle $cycle: compact"
  run_claude "/compact" || log "cycle $cycle: compact exited with status $?"

  if [[ -e "$STOP_FILE" ]]; then
    log "stopping after cycle $cycle, as requested"
    exit 0
  fi
done

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
# Usage: [FEATURE_LOOP_MEMORY_MAX=4G] llm-dlc/tools/feature-loop.sh PROMPT [CYCLES]
#   features  add features and examples to jvmcontract
#   tla       add advanced TLA examples
#   CYCLES    how many cycles to run; without it the loop runs until stopped
#
# While it runs, the number of cycles left can be changed by typing in its
# terminal (see HELP below): +N, -N, =N, inf, or 0 or stop to end after the
# cycle under way. A cycle always finishes, commit and compact included.
#
# Exits 0 when the cycles run out, 1 when a cycle made no commit or the scope
# cannot start, 2 for a bad argument, and 130 if interrupted.

set -uo pipefail

SESSION_ID=360e8b8b-8e0c-4b2a-bd69-25b32f2a54eb
MODEL=claude-fable-5-1
EFFORT=high
MEMORY_MAX=${FEATURE_LOOP_MEMORY_MAX:-4G}
SCOPE=feature-loop

usage() {
  echo "usage: feature-loop.sh features|tla [CYCLES]" >&2
  exit 2
}

(( $# >= 1 && $# <= 2 )) || usage
PROMPT=$1
CYCLES=${2:-inf}
[[ "$CYCLES" == inf || "$CYCLES" =~ ^[1-9][0-9]*$ ]] || usage
case "$PROMPT" in
  features)
    INSTRUCTION="Add more advanced features along with examples to the jvmcontract library."
    ;;
  tla)
    INSTRUCTION="Add more advanced examples showcasing verification of TLA specs"
    ;;
  *) usage ;;
esac

# Claude Code files a session under the directory it ran in, and the instruction
# is meant for the root of the repo, so run there whatever the caller's directory.
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1

# log and show_progress
source llm-dlc/tools/loop-common.sh

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
    "$BASH" llm-dlc/tools/feature-loop.sh "$@"
}
contain "$@"

HELP='while it runs, type a command and Enter:
  +N / -N   run N more / N fewer cycles after this one (+ and - alone mean 1)
  =N or N   run exactly N more cycles after this one
  0, stop   end after this cycle (it still commits and compacts)
  inf       run until stopped
  ?         show where the loop stands'

# The loop and the terminal reader share "cycle remaining" in a state file:
# the cycle under way, and how many cycles start after it ("inf" for no limit).
STATE=$(mktemp "${XDG_RUNTIME_DIR:-/tmp}/feature-loop.XXXXXX") || exit 1
LOCK=$STATE.lock
echo "0 $CYCLES" >"$STATE"

# Run "$@" with $cycle and $remaining read from the state file, under the lock,
# and write them back afterwards.
with_state() {
  {
    flock 9
    read -r cycle remaining <"$STATE"
    "$@"
    echo "$cycle $remaining" >"$STATE"
  } 9>"$LOCK"
}

standing() {
  local total=$(( cycle + ${remaining/inf/0} ))
  if [[ "$remaining" == inf ]]; then
    if (( cycle == 0 )); then
      log "no limit: the loop runs until stopped"
    else
      log "cycle $cycle, no limit: the loop runs until stopped"
    fi
  elif (( cycle == 0 )); then
    log "$remaining cycle(s) to run"
  elif (( remaining == 0 )); then
    log "cycle $cycle is the last: the loop ends after it"
  else
    log "cycle $cycle of $total: $remaining more after this one"
  fi
}

apply() {
  local line=${1,,} n
  line=${line// /}
  case "$line" in
    "" | "?" | status) standing; return ;;
    help | h) printf '%s\n' "$HELP"; return ;;
    stop | q | quit) line=0 ;;
    inf | unlimited) remaining=inf; standing; return ;;
  esac
  if [[ "$line" =~ ^([-+=]?)([0-9]*)$ && -n "$line" ]]; then
    n=${BASH_REMATCH[2]:-1}
    n=$((10#$n))
    case "${BASH_REMATCH[1]}" in
      "" | =) remaining=$n ;;
      +) [[ "$remaining" == inf ]] && { log "no limit already; =N sets one"; return; }
         remaining=$(( remaining + n )) ;;
      -) [[ "$remaining" == inf ]] && { log "no limit to lower; =N sets one, 0 stops"; return; }
         remaining=$(( remaining > n ? remaining - n : 0 )) ;;
    esac
    standing
  else
    log "not a command: $1"
    printf '%s\n' "$HELP"
  fi
}

# Read the terminal in the background, so the count can change while claude
# works. claude gets /dev/null as its input, or it would compete for the lines.
# A background job's input is /dev/null unless redirected, hence fd 3.
reader=
if [[ -t 0 ]]; then
  exec 3<&0
  (
    while read -r line <&3; do
      with_state apply "$line"
    done
  ) &
  reader=$!
  exec 3<&-
fi

cleanup() {
  [[ -n "$reader" ]] && kill "$reader" 2>/dev/null
  rm -f "$STATE" "$LOCK"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# `auto` is the mode this session has always run in. With -p nobody can answer a
# prompt, so anything auto mode would ask about is denied rather than left hanging.
run_claude() {
  claude -p "$1" --resume "$SESSION_ID" --model "$MODEL" --effort "$EFFORT" \
    --permission-mode auto --output-format stream-json --verbose </dev/null | show_progress
}

# `sync.py commit` finishes @ and starts an empty change, so a commit moves @-.
# Change IDs, unlike commit IDs, survive a rewrite of the commit.
last_change() { jj log --no-graph -r @- -T change_id; }

# Start a cycle: count it, and take it from the ones left.
next_cycle() {
  cycle=$(( cycle + 1 ))
  [[ "$remaining" == inf ]] || remaining=$(( remaining - 1 ))
}

if [[ -n "$reader" ]]; then
  printf '%s\n' "$HELP"
else
  log "no terminal: the cycle count can't be changed while it runs"
fi
with_state standing

while :; do
  with_state next_cycle
  before=$(last_change) || exit 1

  log "cycle $cycle: $PROMPT instruction"
  with_state standing
  [[ -n "$reader" ]] && log "type +N, -N, =N, 0 to stop, ? or help"
  run_claude "$INSTRUCTION" || log "cycle $cycle: claude exited with status $?"

  after=$(last_change) || exit 1
  if [[ "$after" == "$before" ]]; then
    log "cycle $cycle: no commit, stopping; session $SESSION_ID needs attention"
    exit 1
  fi
  log "cycle $cycle: committed $(jj log --no-graph -r @- -T 'description.first_line()')"

  log "cycle $cycle: compact"
  run_claude "/compact" || log "cycle $cycle: compact exited with status $?"

  read -r cycle remaining <"$STATE"
  if [[ "$remaining" == 0 ]]; then
    log "no cycles left: stopping after cycle $cycle"
    exit 0
  fi
done

#!/usr/bin/env bash
# The loop under a run: one agent toward one outcome, watched from outside.
#
# llm-dlc/tools/single_run.py starts it for /orchestrate-run, names the run (FEATURE_LOOP_RECORD_AS) and keeps its
# two texts in files. A cycle is one context window of one session:
#
#   the text, the agent's turn, the watcher's verdict, a compact
#
# The first cycle of a run takes FEATURE_LOOP_FIRST's text, and every later one FEATURE_LOOP_CONTINUE's as it
# stands when the cycle starts, so a person can change it between two cycles (never the watcher).
# FEATURE_LOOP_BRIEF names a brief the session is pointed at each cycle, and FEATURE_LOOP_FORK a session to start
# as a fork of. The session stays chained across cycles, so later ones build on earlier ones.
#
# After each cycle, with a commit or without, the loop asks its conductor (LOOP_CONDUCTOR, the run's directory:
# conductor.py's `run` question) whether there is another, and waits FEATURE_LOOP_JUDGE_WAIT seconds (300). `stop`
# ends the run after the compact, with the closing summary. Without a verdict in time a cycle that committed is
# followed by another, and a cycle that did not ends the run where it is, before compacting, so the session keeps
# its full context for the person who has to look at why. FEATURE_LOOP_UNWATCHED cycles in a row without a verdict
# (3) end it too, since nothing else measures the run and the watcher is gone.
#
# Within a turn the session compacts itself at 600k tokens (FEATURE_LOOP_AUTOCOMPACT, 100k to 1M, or auto for
# Claude Code's default), and each compaction is logged. A compaction with no commit since the cycle began, or
# since the last such compaction, is where the work is either hard and going well or stuck. A compaction alone
# doesn't say which, so it is put to the conductor: the turn goes on while it judges, for
# FEATURE_LOOP_CONDUCTOR_WAIT seconds (900). Its stop ends the turn and the loop; its continue, or its silence,
# lets the turn run. FEATURE_LOOP_STOP_ON_COMPACT=1 ends the turn there when the conductor gives no verdict.
#
# The loop re-executes itself in a systemd scope with a memory cap, feature-loop-NAME.scope, so a proof that runs
# away is killed alone and cannot exhaust the machine. On a machine without systemd user scopes it refuses to
# start, unless FEATURE_LOOP_UNCAPPED=1 says to run with no cap at all.
#
# Usage: llm-dlc/tools/feature-loop.sh single-agent [CYCLES]
#
#   CYCLES    how many cycles to run at most; without it there is no limit
#
# The run is its caller's. The session is new unless FEATURE_LOOP_SESSION names one: a session id with no
# transcript yet (one opened but never sent a message) is created by the first turn. FEATURE_LOOP_MODEL,
# FEATURE_LOOP_EFFORT and FEATURE_LOOP_MEMORY_MAX set the model (Fable 5.2), the effort (high) and the cap (3.5G).
# FEATURE_LOOP_CLIENT=codex has the session's turns carried by Codex instead of Claude Code: the instruction, the
# cycle, the commit check, the verdict and the record are the same, and only the starting, resuming and compacting
# of a turn go through llm-dlc/tools/agent_client.py, which prints the stream this script already reads. The run
# keeps its model's name: the operator's equivalences give the Codex model for it (Fable 5.2: Astra 6.2, Opus 5.5:
# Sol 6.2), and a model with none is refused before a turn is spent. The effort is passed on as it is. A Codex
# session cannot start as a fork of a Claude Code conversation.
#
# While it runs, the number of cycles left can be changed by typing in its terminal (see HELP below): +N, -N, =N,
# inf, or 0 or stop to end after the cycle under way. The watcher's commands reach it the same way, through the
# conductor directory (single_run.py cycles, stop). A cycle always finishes, compact included.
#
# Each run keeps a record in llm-dlc/loop-summaries/ (gitignored, never pushed): a line per cycle as it ends, so
# it survives a restart, and when the run ends the session's own summary of it, written for the person reading
# it. Its times are UTC, whatever the machine's zone: sync.py publishes the record redacted and reads from it which
# of the session's prompts were this run's, for the loop statistics (llm-dlc/traces/loops.md), and the session's
# transcript keeps its times in UTC.
#
# Exits 0 when the cycles run out or the watcher ends the run, 1 when a turn or a compaction did not end well, a
# cycle made no commit and no verdict came, or the scope cannot start, 2 for a bad argument, and 130 if interrupted.
#
# Until 2026-11-27 this script ran four kinds of loop: moonshots by name, templated moonshots over a list of
# examples, briefs by name or file, and this one. The others are retired (llm-dlc/retired.md says where to read
# the script as it was), and their names are refused below.

set -uo pipefail

# Run from a private copy. bash reads a script as it runs it, and between two cycles a watcher may land a
# workspace into this checkout, which can rewrite this file under the loop.
if [[ "${FEATURE_LOOP_COPY:-}" != "$0" ]]; then
  FEATURE_LOOP_SELF=$(realpath "${BASH_SOURCE[0]}") || exit 1
  FEATURE_LOOP_COPY=$(mktemp "${TMPDIR:-/tmp}/feature-loop.XXXXXX") || exit 1
  cp -- "$FEATURE_LOOP_SELF" "$FEATURE_LOOP_COPY" || exit 1
  export FEATURE_LOOP_SELF FEATURE_LOOP_COPY
  exec "$BASH" "$FEATURE_LOOP_COPY" "$@"
fi
trap 'rm -f "$FEATURE_LOOP_COPY"' EXIT

SESSION_ID=new
MODEL=claude-fable-5-2
EFFORT=high
MEMORY_MAX=3.5G

usage() {
  echo "usage: feature-loop.sh single-agent [CYCLES]" >&2
  exit 2
}

(( $# >= 1 && $# <= 2 )) || usage
CYCLES=inf
if (( $# == 2 )); then
  [[ "$2" == inf || "$2" =~ ^[1-9][0-9]*$ ]] || usage
  CYCLES=$2
fi
case "$1" in
  single-agent) ;;  # single_run.py looks for this line before it starts a run in a folder
  *)
    echo "feature-loop.sh: '$1' is not a loop this script runs any more: the kind left is single-agent, which llm-dlc/tools/single_run.py starts (/orchestrate-run). llm-dlc/retired.md says what the others were and where to read them" >&2
    exit 2 ;;
esac
ROOT=$(cd "$(dirname "$FEATURE_LOOP_SELF")/../.." && pwd) || exit 1

# The run is the caller's: single_run.py names it and keeps its texts, and the session is new unless it names one.
for v in FEATURE_LOOP_RECORD_AS FEATURE_LOOP_FIRST FEATURE_LOOP_CONTINUE LOOP_CONDUCTOR; do
  [[ -n "${!v:-}" ]] || {
    echo "feature-loop.sh: single-agent takes its run from $v; start it with llm-dlc/tools/single_run.py" >&2
    exit 2
  }
done
[[ "$FEATURE_LOOP_RECORD_AS" =~ ^[a-z0-9][a-z0-9-]*$ ]] || {
  echo "feature-loop.sh: FEATURE_LOOP_RECORD_AS is a run's name, as single-NAME: $FEATURE_LOOP_RECORD_AS" >&2
  exit 2
}
[[ -n "$(tr -d '[:space:]' <"$FEATURE_LOOP_FIRST" 2>/dev/null)" && -n "$(tr -d '[:space:]' <"$FEATURE_LOOP_CONTINUE" 2>/dev/null)" ]] || {
  echo "feature-loop.sh: single-agent needs a text in both $FEATURE_LOOP_FIRST and $FEATURE_LOOP_CONTINUE" >&2
  exit 2
}
PROMPT=$FEATURE_LOOP_RECORD_AS
FORK_FROM=${FEATURE_LOOP_FORK:-}

# The run's instruction for a cycle: the text, and when the run has a brief, one sentence more that names it,
# since after a compact the session's memory of the brief is a summary.
single_text() {
  local text=$1
  if [[ -n "${FEATURE_LOOP_BRIEF:-}" ]]; then
    text+=$'\n\n'"The brief for this work is \`$FEATURE_LOOP_BRIEF\`. Read it in full first, even if you have read it before: what you remember of it may be a summary."
  fi
  printf '%s' "$text"
}
# A text on one line, for the run's record.
one_line() { printf '%s' "$1" | tr '\n' ' ' | sed 's/  */ /g; s/^ //; s/ $//'; }
INSTRUCTION=$(single_text "$(<"$FEATURE_LOOP_FIRST")") || exit 1
single_continue=$(<"$FEATURE_LOOP_CONTINUE") || exit 1
UNWATCHED=${FEATURE_LOOP_UNWATCHED:-3}

SESSION_ID=${FEATURE_LOOP_SESSION:-$SESSION_ID}
AUTOCOMPACT=${FEATURE_LOOP_AUTOCOMPACT:-600k}
# A run's own compaction point (single_run.py --compact-at, the brief author's 600k): the size the client compacts
# at, in place of AUTOCOMPACT's.
COMPACT_AT=${FEATURE_LOOP_COMPACT_AT:-}
# A compaction with no commit is put to the conductor; this ends the turn there by rule when no verdict comes.
STOP_ON_COMPACT=
[[ "${FEATURE_LOOP_STOP_ON_COMPACT:-}" == 1 ]] && STOP_ON_COMPACT=1
MODEL=${FEATURE_LOOP_MODEL:-$MODEL}
EFFORT=${FEATURE_LOOP_EFFORT:-$EFFORT}
# The client that carries the session's turns (see the header): Claude Code unless the run says Codex.
# The model is resolved once, here, and what was asked for is kept for the record.
CLIENT=${FEATURE_LOOP_CLIENT:-claude}
MODEL_ASKED=$MODEL
AGENT_CLIENT=$ROOT/llm-dlc/tools/agent_client.py
case "$CLIENT" in
  claude) ;;
  codex)
    MODEL=$(python3 "$AGENT_CLIENT" resolve --client codex "$MODEL") || exit 2
    python3 "$AGENT_CLIENT" plan --client codex --model "$MODEL" --effort "$EFFORT" >/dev/null || exit 2
    ;;
  *) echo "feature-loop.sh: '$CLIENT' is not a client (claude, codex)" >&2; exit 2 ;;
esac
MEMORY_MAX=${FEATURE_LOOP_MEMORY_MAX:-$MEMORY_MAX}
JUDGE_WAIT=${FEATURE_LOOP_JUDGE_WAIT:-300}
SCOPE=feature-loop-$PROMPT
[[ "$SESSION_ID" == new || "$SESSION_ID" =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]] || {
  echo "feature-loop.sh: not a session id: $SESSION_ID" >&2
  exit 2
}

# Claude Code files a session under the directory it ran in, and the instruction
# is meant for the root of the repo, so run there whatever the caller's directory.
cd "$ROOT" || exit 1

# log and show_progress
source llm-dlc/tools/loop-common.sh

# Shells on WSL sit in init.scope, where an out-of-memory kill can take the whole
# instance down, so the loop moves to a scope of its own. Everything it starts
# inherits the cap, including jbmc, TLC and any Gradle daemon. OOMPolicy=continue
# matters: under the default, systemd stops the scope on the first kill, and
# claude dies with the proof instead of seeing it fail. Without swap the cap is
# exact, and a process over it is killed rather than left thrashing.
# Stop this loop's scope when all it holds is what an ended loop left: fails, leaving the scope alone, when a
# feature loop (it runs from a private copy, feature-loop.XXXXXX) or an agent client is among its processes, or
# when its processes can't be read.
CGROUPS=${FEATURE_LOOP_CGROUP_ROOT:-/sys/fs/cgroup}
clear_leftovers() {
  local group pid cmd left=0
  group=$(systemctl --user show -p ControlGroup --value "$SCOPE.scope" 2>/dev/null)
  [[ -n "$group" && -r "$CGROUPS$group/cgroup.procs" ]] || return 1
  for pid in $(cat "$CGROUPS$group/cgroup.procs" 2>/dev/null); do
    cmd=$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null)
    if [[ "$cmd" == *feature-loop.* || "$cmd" == *agent_client.py* || "$cmd" =~ (^|/)(claude|codex)( |$) ]]; then
      log "$SCOPE.scope: pid $pid is a loop or an agent at work (${cmd:0:80})"
      return 1
    fi
    left=$(( left + 1 ))
  done
  log "$SCOPE.scope holds only what an ended loop left ($left process(es)): stopping it before the loop starts"
  systemctl --user stop "$SCOPE.scope" 2>/dev/null
}

contain() {
  grep -q "/$SCOPE\.scope\$" /proc/self/cgroup && return
  # A loop started from inside another loop's scope is an agent starting a run: a new paid session nobody asked for
  # (VF-045, 2026-11-27). Every loop passes here. The tests' made-up loops set IN_THE_LOOP_NESTED_RUN=allow
  # (lib/tools/cost_tier.py).
  local outer
  outer=$(grep -o -E '/feature-loop-[^/]+\.scope' "${FEATURE_LOOP_CGROUP_FILE:-/proc/self/cgroup}" 2>/dev/null | head -1)
  if [[ -n "$outer" && "${IN_THE_LOOP_NESTED_RUN:-}" != allow ]]; then
    log "refused: this loop would start inside the running loop ${outer#/}; a loop's agent does not start runs (VF-045)"
    log "say in the report what the work needs, and the watcher puts it to the user"
    exit 1
  fi
  if [[ -n "${FEATURE_LOOP_UNCAPPED:-}" ]]; then
    log "FEATURE_LOOP_UNCAPPED: running with no memory cap; a proof that runs away can exhaust the machine"
    return
  fi

  # The scope outlives the loop while anything in it runs, such as a Gradle daemon or the dirmngr a signature
  # check started (on 2026-11-26 one kept a setup's scope active for eight hours, and every start refused: VF-070).
  # What an ended loop left is stopped; a loop or an agent at work in the scope is not.
  if systemctl --user is-active --quiet "$SCOPE.scope" && ! clear_leftovers; then
    log "$SCOPE.scope is active: another loop, or an agent, is at work in it"
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

  # Half the default CPU weight: when the CPUs are contended, an interactive
  # terminal (weight 100) keeps its share ahead of the loops. Verification
  # jobs are capped by CPUQuota instead, within the runner's budget.
  log "starting in $SCOPE.scope with a $MEMORY_MAX cap"
  exec systemd-run --user --scope --quiet --collect --unit="$SCOPE" \
    -p MemoryMax="$MEMORY_MAX" -p MemorySwapMax=0 -p OOMPolicy=continue -p CPUWeight=50 \
    "$BASH" "$0" "$@"
}
contain "$@"

# The run's record: what it was asked, a line per cycle, and how it ended.
SUMMARIES=llm-dlc/loop-summaries
mkdir -p "$SUMMARIES" || exit 1
# The record's clock: UTC, as in the transcripts that loop_stats.py reads it against.
stamp() { date -u '+%F %T'; }
SUMMARY=$SUMMARIES/$(date -u +%F-%H%M%S)-$PROMPT.md
START=$(jj log --no-graph -r @- -T change_id) || exit 1

# A fresh session gets its id here, and it and a session with no transcript yet
# are created by the first turn. Claude Code keeps transcripts under the working
# directory's path with every other character turned into a dash.
PROJECTS=${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects
project_dir() { printf '%s/%s' "$PROJECTS" "$(printf '%s' "$1" | sed 's/[^A-Za-z0-9]/-/g')"; }
FRESH=
if [[ "$SESSION_ID" == new ]]; then
  SESSION_ID=$(python3 -c 'import uuid; print(uuid.uuid4())') || exit 1
  FRESH=1
elif [[ "$CLIENT" == codex ]]; then
  # Codex names its thread itself: the session is bound to it on the first turn (agent_client.py).
  if ! python3 "$AGENT_CLIENT" exists --client codex --session "$SESSION_ID" --cwd "$ROOT"; then
    log "session $SESSION_ID has no Codex thread yet: the first turn starts one"
    FRESH=1
  fi
elif [[ ! -e "$(project_dir "$ROOT")/$SESSION_ID.jsonl" ]]; then
  log "session $SESSION_ID has no transcript yet: the first turn creates it"
  FRESH=1
fi
if [[ "$CLIENT" == codex && -n "$FORK_FROM" && -n "$FRESH" ]]; then
  echo "feature-loop.sh: session $SESSION_ID is to start as a fork of $FORK_FROM, a Claude Code conversation, and Codex cannot continue one: a Codex worker starts from the written handoff (the run's texts and its brief). Drop the fork, or run this loop with Claude Code" >&2
  exit 2
fi

# A session carried by Codex is traced under Codex's own thread id, which the record has to name for the run's
# statistics and its published copy to find the session (loop_stats.py, sync.py). A session that is continued has
# its thread already; a new one has it once its first turn has started, and the line is added then.
CODEX_THREAD=
if [[ "$CLIENT" == codex ]]; then
  CODEX_THREAD=$(python3 "$AGENT_CLIENT" thread --session "$SESSION_ID" --cwd "$ROOT" 2>/dev/null) || CODEX_THREAD=
fi
{
  echo "# Feature loop: $PROMPT"
  echo
  echo "Started $(stamp) UTC, ${CYCLES/inf/no limit on} cycles, session $SESSION_ID, $MODEL at $EFFORT effort, after change $START."
  echo
  if [[ "$CLIENT" != claude ]]; then
    echo "The session's turns are carried by $CLIENT$([[ "$MODEL" != "$MODEL_ASKED" ]] && echo ", which runs $MODEL for the $MODEL_ASKED this loop asks for")."
    echo
    if [[ -n "$CODEX_THREAD" ]]; then
      echo "Codex thread $CODEX_THREAD carries session $SESSION_ID."
      echo
    fi
  fi
  echo "> $(one_line "$INSTRUCTION")"
  echo
  echo "Every later cycle takes the run's continue message as it stands when the cycle starts, and after each cycle a watcher outside the session decides whether there is another. The message at the start:"
  echo
  echo "> $(one_line "$single_continue")"
  echo
  echo "## Commits"
  echo
} >"$SUMMARY"
note() { printf '%s\n' "$*" >>"$SUMMARY"; }
log "keeping a record of this run in $SUMMARY"

HELP='while it runs, type a command and Enter:
  +N / -N   run N more / N fewer cycles after this one (+ and - alone mean 1)
  =N or N   run exactly N more cycles after this one
  0, stop   end after this cycle (it still compacts)
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
  return 0
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
  rm -f "$STATE" "$LOCK" "$STATE.pid" "$STATE.compacted" "$STATE.notes" "$STATE.turn" "$STATE.compact" "$STATE.jj" "$FEATURE_LOOP_COPY"
  # Last, however the loop ended, so the session to resume or read is on screen.
  log "session: $SESSION_ID"
}
trap cleanup EXIT
trap 'note; note "Interrupted $(stamp) during cycle $cycle."; exit 130' INT TERM

# `auto` is the mode this session has always run in. With -p nobody can answer a
# prompt, so anything auto mode would ask about is denied rather than left hanging.
# A second argument names a file that receives the raw event stream as well.
# With LOOP_WATCH_PID set, claude's pid goes into that file, for show_progress to
# end the turn when a compaction finds no commit (see loop-common.sh).
run_claude() {
  local session=(--resume "$SESSION_ID") compact=()
  [[ -n "$FRESH" ]] && session=(--session-id "$SESSION_ID")
  [[ -n "$AUTOCOMPACT" ]] && compact=(--autocompact "$AUTOCOMPACT")
  [[ -n "$COMPACT_AT" ]] && compact=(--autocompact "$COMPACT_AT")
  local codex_compact=()
  [[ -n "$COMPACT_AT" ]] && codex_compact=(--compact-at "$COMPACT_AT")
  FRESH=
  (
    [[ -n "${LOOP_WATCH_PID:-}" ]] && printf '%s\n' "$BASHPID" >"$LOOP_WATCH_PID"
    # The session is given the instruction and nothing of the run that started it: with the loop's and the run's
    # variables in its shell, a test it ran of these very scripts asked the real watcher its made-up questions
    # (2026-11-17). The first and the last prefix are those of two retired workflows, whose variables an old
    # shell may still hold.
    unset "${!RUN_STREAMS_@}" "${!FEATURE_LOOP_@}" "${!LOOP_WATCH_@}" "${!PROVE_LOOP_@}" LOOP_CONDUCTOR
    if [[ "$CLIENT" == codex ]]; then
      # The same instruction, through the other client: agent_client.py prints the stream this pipe reads.
      # Compacting is an operation of the client's, not a text the model is sent.
      if [[ "$1" == /compact ]]; then
        exec python3 "$AGENT_CLIENT" compact --client codex --session "$SESSION_ID" --cwd "$ROOT"
      fi
      exec python3 "$AGENT_CLIENT" run --client codex --session "$SESSION_ID" --model "$MODEL" --effort "$EFFORT" \
        --cwd "$ROOT" "${codex_compact[@]}" "$1"
    fi
    unset CODEX_THREAD_ID CODEX_SESSION_ID  # a Codex session that started this loop is not this session
    exec claude -p "$1" "${session[@]}" --model "$MODEL" --effort "$EFFORT" "${compact[@]}" \
      --permission-mode auto --output-format stream-json --verbose </dev/null
  ) | tee ${2:+"$2"} | show_progress
}

# Print the text of the last result event in a stream-json file.
result_text() {
  python3 -c '
import json, sys
text = None
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if isinstance(e, dict) and e.get("type") == "result" and isinstance(e.get("result"), str):
        text = e["result"]
if text and text.strip():
    print(text.strip())
else:
    sys.exit(1)
' "$1"
}

# Why the turn whose event stream is in a file did not end well, or nothing when it did. A turn ends well with a
# result that says success. One that was cut off or died leaves no result, and one that the client ended with an
# error (a quota, an interruption, a failure of its own) says so in its result: neither is a cycle's work, and
# before 2026-11-19 both were only logged, so a run could end "after N cycle(s)" with status 0 on a last cycle
# that had failed. With `compact` as a second argument the stream is a compaction's, which also ends well with a
# boundary in the stream.
turn_failure() {
  python3 -c '
import json, sys
last, boundary = None, False
try:
    lines = list(open(sys.argv[1], encoding="utf-8", errors="replace"))
except OSError:
    lines = []
for line in lines:
    try:
        e = json.loads(line)
    except ValueError:
        continue
    if not isinstance(e, dict):
        continue
    if e.get("type") == "result":
        last = e
    elif e.get("type") == "system" and e.get("subtype") == "compact_boundary":
        boundary = True
if last is None:
    if not (sys.argv[2:] == ["compact"] and boundary):
        print("the client left no result (it was cut off, or it died)")
elif last.get("subtype") != "success" or last.get("is_error"):
    text = " ".join(str(last.get("result") or "").split())[:300]
    print("the client reported %s%s" % (last.get("subtype") or "an error", ": " + text if text else ""))
' "$@"
}

# Ask the session for a summary of the run's commits and append it to the record.
# It is only a report: it changes nothing, so it can't affect what a push publishes.
summarize() {
  local stream
  stream=$(mktemp "${XDG_RUNTIME_DIR:-/tmp}/feature-loop-summary.XXXXXX") || return 1
  log "summarizing the run into $SUMMARY"
  run_claude "The feature loop is ending after $cycle cycle(s). Summarize the work this run committed, the revisions that \`jj log -r '$START..@-'\` lists, for the user, who was not watching and will read it later. For each commit say what it adds and how it was verified; then list the verification jobs still pending or failed (\`python3 verification/pipeline.py status\` and \`report\`), the warnings \`python3 llm-dlc/tools/sync.py check\` reports that they must judge before pushing, the work deferred because it needs their input, such as credentials or a decision, with what each item needs, and anything else that needs their attention. Reply with the summary in Markdown and nothing else. This turn only reports: don't edit files, commit, push or submit jobs." "$stream" ||
    log "summary: claude exited with status $?"
  note
  note "## Summary"
  note
  if ! result_text "$stream" >>"$SUMMARY"; then
    note "No summary came back; the commits above are the record. Session $SESSION_ID has the details."
    log "summary: no text came back"
  fi
  rm -f "$stream"
}

# After a cycle, committed or not: the run's watcher (the conductor's `run` question) decides whether there is
# another. Sets $decision to continue or stop, $run_reason, and $run_unanswered when the run ends for want of a
# verdict on a cycle with no commit, which is a session that needs attention.
unwatched=0
judge_run() {
  local asked committed=none
  run_unanswered=
  [[ "$after" != "$before" ]] && committed=$(jj log --no-graph -r @- -T 'change_id.short()')
  asked=$(python3 llm-dlc/tools/conductor.py ask "$LOOP_CONDUCTOR" run --answers continue,stop --wait "$JUDGE_WAIT" \
    "cycle=$cycle" "session=$SESSION_ID" "turn=$STATE.turn" "before=$before" "commit=$committed") || asked=none
  if [[ -n "$asked" && "$asked" != none ]]; then
    unwatched=0
    decision=${asked%%$'\t'*}
    run_reason="the watcher: ${asked#*$'\t'}"
  else
    unwatched=$(( unwatched + 1 ))
    if [[ "$committed" == none ]]; then
      decision=stop run_unanswered=1
      run_reason="no verdict came from the watcher in ${JUDGE_WAIT}s, and the cycle made no commit"
    elif (( unwatched >= UNWATCHED )); then
      decision=stop
      run_reason="no verdict came from the watcher after $unwatched cycle(s) in a row, so nothing watches the run"
    else
      decision=continue
      run_reason="no verdict came from the watcher in ${JUDGE_WAIT}s, and the cycle committed, so the run goes on as a loop nobody watches does"
    fi
  fi
  log "cycle $cycle: the run is to $decision: $run_reason"
  note "  - decided to $decision: $run_reason"
}

# The conductor's command lines (conductor.py command), applied as if typed in the terminal.
apply_commands() {
  local line
  while IFS= read -r line; do
    [[ -n "$line" ]] && with_state apply "$line"
  done < <(python3 llm-dlc/tools/conductor.py commands "$LOOP_CONDUCTOR" 2>/dev/null)
}

# Tell whoever watches where the loop is (conductor.py note): an event that asks nothing.
tell() {
  python3 llm-dlc/tools/conductor.py note "$LOOP_CONDUCTOR" "$@" 2>/dev/null
  return 0
}

# `sync.py commit` finishes @ and starts an empty change, so a commit moves @-.
# Change IDs, unlike commit IDs, survive a rewrite of the commit.
#
# Another session's jj operation can meet this workspace's (a watcher landing, a checkpoint), and jj then refuses
# every command here with "The working copy is stale". The loop reads @- before and right after each turn, when
# the agent is not working and nothing else edits this checkout, so it recovers there as CLAUDE.md tells an agent
# to: unstale.py saves what was not committed, updates the working copy and takes the edits back. It says so in the
# log and the summary. When unstale.py can't tell which copy of the edits to keep, the loop stops as it always did,
# with the error in the log: a person decides that.
last_change() {
  local out
  if out=$(jj log --no-graph -r @- -T change_id 2>"$STATE.jj"); then
    printf '%s\n' "$out"
    return 0
  fi
  if ! grep -q 'working copy is stale' "$STATE.jj"; then
    cat "$STATE.jj" >&2
    return 1
  fi
  log "the working copy is stale (another session's jj operation met this one's); recovering with unstale.py" >&2
  if ! python3 llm-dlc/tools/unstale.py >&2; then
    log "unstale.py could not recover the working copy; it needs a person" >&2
    return 1
  fi
  note "- $(stamp): the working copy was stale after another session's jj operation, and unstale.py recovered it"
  jj log --no-graph -r @- -T change_id
}

# Start a cycle: count it, and take it from the ones left.
next_cycle() {
  cycle=$(( cycle + 1 ))
  [[ "$remaining" == inf ]] || remaining=$(( remaining - 1 ))
}

# With FEATURE_LOOP_FORK, a session that has no transcript yet starts as a fork of that one, in a turn of its
# own. Claude Code finds a session to resume under the directory it runs in, and the parent may be a session of
# any workspace of the repository (the watcher's own, say), so its newest transcript is copied here for the fork
# and removed straight after. That turn runs without the repo's hooks or any tool, so the copy is never synced:
# left here, it would be published again as this workspace's.
fork_session() {
  local source here copied= words
  source=$(ls -t "$PROJECTS"/*/"$FORK_FROM.jsonl" 2>/dev/null | head -n 1)
  words="This conversation goes on, from here, as an unattended run of one agent: you are now the session that does the work, alone, in the checkout at \`$ROOT\`, and no longer the one that planned it. The conversation you were forked from carries on separately and watches this run from outside; it will not talk to you, and you don't report to it. From now on work only in that checkout and follow its CLAUDE.md. Tools are off for this one turn: reply in a few sentences with what you know that the work will need. The run's first instruction follows."
  here=$(project_dir "$ROOT")
  if [[ -z "$source" || ! -f "$source" ]]; then
    log "no transcript of session $FORK_FROM to fork, at ${source:-$PROJECTS/*/$FORK_FROM.jsonl}"
    return 1
  fi
  mkdir -p "$here" || return 1
  if [[ "$source" != "$here/$FORK_FROM.jsonl" ]]; then
    cp -- "$source" "$here/$FORK_FROM.jsonl" || return 1
    copied=1
  fi
  log "starting session $SESSION_ID as a fork of $FORK_FROM"
  claude -p "$words" \
    --resume "$FORK_FROM" --fork-session --session-id "$SESSION_ID" --model "$MODEL" --effort "$EFFORT" \
    --setting-sources user --tools "" --output-format stream-json --verbose </dev/null | show_progress
  [[ -n "$copied" ]] && rm -f -- "${here:?}/${FORK_FROM:?}.jsonl"
  if [[ ! -f "$here/$SESSION_ID.jsonl" ]]; then
    log "the fork of session $FORK_FROM made no session $SESSION_ID"
    return 1
  fi
  FRESH=
  note "Session $SESSION_ID was forked from session $FORK_FROM."
  note
}
if [[ -n "$FRESH" && -n "$FORK_FROM" ]]; then
  fork_session || { note "Stopped $(stamp): the fork of session $FORK_FROM failed."; exit 1; }
fi

if [[ -n "$reader" ]]; then
  printf '%s\n' "$HELP"
else
  log "no terminal: the cycle count can't be changed while it runs"
fi
with_state standing

while :; do
  apply_commands
  # A stop that came before this cycle began (before the first, or between the last look and here) ends the loop
  # here: counted as a cycle to start, it left a count below zero, which nothing ended.
  read -r cycle remaining <"$STATE"
  if [[ "$remaining" == 0 ]]; then
    log "stopped, as asked, before cycle $(( cycle + 1 ))"
    (( cycle > 0 )) && summarize
    note; note "Ended $(stamp) after $cycle cycle(s)."
    log "record of the run: $SUMMARY"
    exit 0
  fi
  with_state next_cycle
  before=$(last_change) || exit 1

  # The first cycle of a run takes its first text; every later one the continue message as it stands now.
  if (( cycle > 1 )); then
    # A file that can't be read, or is empty, changes nothing: the message stays the last one read.
    text=$(cat -- "$FEATURE_LOOP_CONTINUE" 2>/dev/null) && [[ -n "${text//[[:space:]]/}" ]] || text=$single_continue
    if [[ "$text" != "$single_continue" ]]; then
      single_continue=$text
      log "cycle $cycle: the continue message has changed"
      note "  - from cycle $cycle the continue message is: $(one_line "$single_continue")"
    fi
    INSTRUCTION=$(single_text "$single_continue")
    log "cycle $cycle: $PROMPT, the continue message"
  else
    log "cycle $cycle: $PROMPT, the run's first text"
  fi
  tell cycle-start "cycle=$cycle" "turn=$STATE.turn" "base=$before"
  with_state standing
  [[ -n "$reader" ]] && log "type +N, -N, =N, 0 to stop, ? or help"
  # The compaction watch of the turn (show_progress, loop-common.sh).
  rm -f "$STATE.compacted" "$STATE.notes"
  export LOOP_WATCH_BASE=$before LOOP_WATCH_PID=$STATE.pid LOOP_WATCH_MARK=$STATE.compacted LOOP_WATCH_NOTES=$STATE.notes
  export LOOP_WATCH_STOP=$STOP_ON_COMPACT
  export LOOP_WATCH_CYCLE=$cycle LOOP_WATCH_SESSION=$SESSION_ID
  export LOOP_WATCH_TRANSCRIPT="$(project_dir "$ROOT")/$SESSION_ID.jsonl"
  [[ "$CLIENT" == codex ]] && export LOOP_WATCH_TRANSCRIPT="$ROOT/llm-dlc/loop-summaries/agent-sessions/$SESSION_ID.json"
  # What the cycle is told, by digest: the same task given to another client shows the same one.
  log "cycle $cycle: the instruction is ${#INSTRUCTION} characters, sha256 $(printf '%s' "$INSTRUCTION" | sha256sum | cut -c1-16), carried by $CLIENT ($MODEL at $EFFORT effort)"
  run_claude "$INSTRUCTION" "$STATE.turn" || log "cycle $cycle: $CLIENT exited with status $?"
  if [[ "$CLIENT" == codex && -z "$CODEX_THREAD" ]]; then
    CODEX_THREAD=$(python3 "$AGENT_CLIENT" thread --session "$SESSION_ID" --cwd "$ROOT" 2>/dev/null) || CODEX_THREAD=
    if [[ -n "$CODEX_THREAD" ]]; then
      note "Codex thread $CODEX_THREAD carries session $SESSION_ID."
      note
    fi
  fi
  unset LOOP_WATCH_BASE LOOP_WATCH_PID LOOP_WATCH_MARK LOOP_WATCH_NOTES LOOP_WATCH_STOP LOOP_WATCH_CYCLE LOOP_WATCH_SESSION LOOP_WATCH_TRANSCRIPT
  if [[ -s "$STATE.compacted" ]]; then
    compacted=$(<"$STATE.compacted")
    log "cycle $cycle: $compacted, stopping; session $SESSION_ID needs attention"
    note; note "Stopped $(stamp): cycle $cycle $compacted; session $SESSION_ID needs attention."
    exit 1
  fi

  after=$(last_change) || exit 1
  failure=$(turn_failure "$STATE.turn")
  if [[ -n "$failure" ]]; then
    # Before any verdict and before the compact, whatever the count of cycles says: the session keeps what it
    # had for whoever looks at why, and the loop's status says that someone must. A turn that ended well and
    # made no commit is another matter, and goes on below.
    made=
    if [[ "$after" != "$before" ]]; then
      made=", after its commit $(jj log --no-graph -r @- -T 'change_id.short()')"
      note "- cycle $cycle, $(stamp), \`$(jj log --no-graph -r @- -T 'change_id.short()')\`: $(jj log --no-graph -r @- -T 'description.first_line()')"
    fi
    log "cycle $cycle: the turn did not end well ($failure)$made, stopping; session $SESSION_ID needs attention"
    note; note "Stopped $(stamp): the turn of cycle $cycle did not end well$made: $failure; session $SESSION_ID needs attention."
    exit 1
  fi
  if [[ "$after" == "$before" ]]; then
    # The watcher decides what a cycle with no commit means (the outcome reached, a question, or stuck).
    log "cycle $cycle: no commit"
    note "- cycle $cycle, $(stamp): no commit"
  else
    log "cycle $cycle: committed $(jj log --no-graph -r @- -T 'description.first_line()')"
    note "- cycle $cycle, $(stamp), \`$(jj log --no-graph -r @- -T 'change_id.short()')\`: $(jj log --no-graph -r @- -T 'description.first_line()')"
  fi
  # What a conductor let go on during the turn, under the cycle's line.
  if [[ -s "$STATE.notes" ]]; then
    while IFS= read -r line; do note "  - $line"; done <"$STATE.notes"
  fi

  decision=continue
  run_unanswered=
  apply_commands  # a stop left during the turn ends the run without a question
  # The last cycle of a count ends the loop anyway, so there is nothing to decide.
  read -r _ left <"$STATE"
  [[ "$left" == 0 ]] || judge_run
  if [[ -n "$run_unanswered" ]]; then
    # Before the compact, so the session keeps its full context for the person who looks at why.
    log "cycle $cycle: no commit and no verdict, stopping; session $SESSION_ID needs attention"
    note; note "Stopped $(stamp): cycle $cycle made no commit, and no verdict came from the watcher; session $SESSION_ID needs attention."
    exit 1
  fi

  log "cycle $cycle: compact"
  run_claude "/compact" "$STATE.compact" || log "cycle $cycle: compact exited with status $?"
  failure=$(turn_failure "$STATE.compact" compact)
  rm -f "$STATE.compact"
  if [[ -n "$failure" ]]; then
    # A cycle is one context window, so the next would start on this one's: the loop stops and says so. A run
    # that was ending here anyway still gets its summary, since its work is committed; its status is not 0.
    log "cycle $cycle: the compaction did not end well ($failure), stopping; session $SESSION_ID needs attention"
    read -r _ left <"$STATE"
    [[ "$decision" == stop || "$left" == 0 ]] && summarize
    note; note "Stopped $(stamp): the compaction after cycle $cycle did not end well: $failure; session $SESSION_ID needs attention."
    log "record of the run: $SUMMARY"
    exit 1
  fi

  apply_commands
  read -r cycle remaining <"$STATE"
  if [[ "$decision" == stop ]]; then
    log "the run ends after cycle $cycle: $run_reason"
    summarize
    note; note "Ended $(stamp) after $cycle cycle(s): the run was ended there ($run_reason)."
    log "record of the run: $SUMMARY"
    exit 0
  fi
  if [[ "$remaining" == 0 ]]; then
    log "no cycles left: stopping after cycle $cycle"
    summarize
    note; note "Ended $(stamp) after $cycle cycle(s)."
    log "record of the run: $SUMMARY"
    exit 0
  fi
done

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
# Usage: [FEATURE_LOOP_MEMORY_MAX=3.5G] llm-dlc/tools/feature-loop.sh PROMPT [CYCLES] [UNTIL]
#   features  add features and examples to jvmcontract
#   tla       add advanced TLA examples
#   spring    make jvmcontract more useful to expert Spring Boot developers
#   relational  make relational verification more efficient and accurate, with examples
#   engines   work through llm-dlc/loops/engine-priorities.md (stock JBMC, native coverage, Bitwuzla)
#   FILE.md   work through the brief in a markdown file (see llm-dlc/loops/)
#   CYCLES    how many cycles to run at most; without it there is no limit
#   UNTIL     instructions the session weighs after each commit to decide whether
#             the loop goes on; a second argument that isn't a count is UNTIL
#
# A stopped loop is continued by running the same command again: the brief fixes
# the session, its Progress section says what is done, and each cycle first
# finishes a change an interrupted cycle left in the working copy, keeping any
# other session's uncommitted files (the verification loop's, say) out of its commit.
#
# A brief is fixed for the run: each cycle tells the session to read it again in
# full, so it outlives every compact, and a brief that changes while the loop
# runs stops it. Its "## Progress" section is the exception: the session keeps it
# current, in the commit that does the work, and edits there don't count as a
# change. Without UNTIL, a brief's own "## Loop until" section is UNTIL,
# and with neither, nor CYCLES, the loop runs until the session decides the
# brief is done.
#
# A brief may also set the session, model and effort in a "## Loop settings"
# section of "- session: ID", "- model: ID" and "- effort: LEVEL" lines.
# FEATURE_LOOP_SESSION, FEATURE_LOOP_MODEL and FEATURE_LOOP_EFFORT override
# both the brief and the defaults. FEATURE_LOOP_SESSION=new starts a fresh
# session that the run's cycles share, and a session id with no transcript yet
# (one opened but never sent a message) is created by the first turn.
#
# With UNTIL, each commit is followed by one more turn, before the compact, in
# which the session applies UNTIL to what it has done and ends its reply with
# "LOOP: continue" or "LOOP: stop". A stop ends the loop after that cycle like
# running out of cycles does; a reply with neither stops it as needing attention.
#
# While it runs, the number of cycles left can be changed by typing in its
# terminal (see HELP below): +N, -N, =N, inf, or 0 or stop to end after the
# cycle under way. A cycle always finishes, commit and compact included.
#
# Each run keeps a log in llm-dlc/loop-summaries/ (gitignored, never pushed): a
# line per commit as it lands, so it survives a restart, and when the cycles run
# out the session's own summary of the run, written for the person reading it.
#
# Exits 0 when the cycles run out or the session decides to stop, 1 when a cycle
# made no commit, the session's decision was unclear, the brief changed or the
# scope cannot start, 2 for a bad argument, and 130 if interrupted.

set -uo pipefail

SESSION_ID=360e8b8b-8e0c-4b2a-bd69-25b32f2a54eb
MODEL=claude-fable-5-1
EFFORT=high
MEMORY_MAX=${FEATURE_LOOP_MEMORY_MAX:-3.5G}
SCOPE=feature-loop

usage() {
  echo "usage: feature-loop.sh features|tla|spring|relational|engines|FILE.md [CYCLES] [UNTIL]" >&2
  exit 2
}

(( $# >= 1 && $# <= 3 )) || usage
PROMPT=$1
CYCLES=inf
UNTIL=
is_count() { [[ "$1" == inf || "$1" =~ ^[1-9][0-9]*$ ]]; }
if (( $# == 3 )); then
  is_count "$2" && [[ -n "$3" ]] || usage
  CYCLES=$2 UNTIL=$3
elif (( $# == 2 )); then
  if is_count "$2"; then CYCLES=$2; else UNTIL=$2; fi
fi
[[ -z "$UNTIL" || -n "${UNTIL//[[:space:]]/}" ]] || usage
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd) || exit 1
BRIEF=
# Names for briefs: the brief's own Loop settings (session, model, effort) and Loop until apply.
case "$PROMPT" in
  engines) PROMPT=llm-dlc/loops/engine-priorities.md ;;
esac
case "$PROMPT" in
  *.md)
    # Found from the caller's directory or the repo's, and named relative to the
    # repo when it is inside it, which is where the loop runs.
    if [[ -f "$PROMPT" ]]; then
      BRIEF=$(realpath "$PROMPT")
    elif [[ -f "$ROOT/$PROMPT" ]]; then
      BRIEF=$(realpath "$ROOT/$PROMPT")
    else
      echo "feature-loop.sh: no brief at $PROMPT" >&2
      exit 2
    fi
    # Without UNTIL, the text under the brief's "## Loop until" heading, up to
    # the next heading, on one line.
    if [[ -z "$UNTIL" ]]; then
      UNTIL=$(awk '/^## / { inside = ($0 ~ /^## +Loop until[[:space:]]*$/); next } inside' "$BRIEF" |
        tr '\n' ' ' | sed 's/  */ /g; s/^ //; s/ $//')
    fi
    # "- key: value" lines under the brief's "## Loop settings" heading.
    setting() {
      awk -v key="$1" '
        /^## / { inside = ($0 ~ /^## +Loop settings[[:space:]]*$/); next }
        inside && match($0, "^[-*] +" key ": *") { v = substr($0, RLENGTH + 1); gsub(/[`[:space:]]/, "", v); print v; exit }
      ' "$BRIEF"
    }
    v=$(setting session); [[ -n "$v" ]] && SESSION_ID=$v
    v=$(setting model); [[ -n "$v" ]] && MODEL=$v
    v=$(setting effort); [[ -n "$v" ]] && EFFORT=$v
    [[ "$BRIEF" == "$ROOT"/* ]] && BRIEF=${BRIEF#"$ROOT"/}
    set -- "$BRIEF" "${@:2}"
    PROMPT=$(basename "$BRIEF" .md)
    if [[ -z "$UNTIL" && "$CYCLES" == inf ]]; then
      UNTIL="Stop when everything the brief in $BRIEF asks for is done, or when what is left needs a person's decision first."
    fi
    ;;
  features)
    INSTRUCTION="Add more advanced features along with examples to the jvmcontract library."
    ;;
  tla)
    INSTRUCTION="Add more advanced examples showcasing verification of TLA specs"
    ;;
  spring)
    INSTRUCTION="Enhance the jvmcontract library to be more useful to expert Spring Boot developers. Think outside the box for this -- consider adding more base models, solvers, examples, or other features you feel may be very impactful that we haven't yet considered. Bias towards making enhancements a first-class citizen of the library itself, though feel free to look elsewhere for inspiration."
    ;;
  relational)
    INSTRUCTION="Enhance relational verification capabilities to be more efficient and accurate, adding examples where appropriate"
    ;;
  *) usage ;;
esac

SESSION_ID=${FEATURE_LOOP_SESSION:-$SESSION_ID}
MODEL=${FEATURE_LOOP_MODEL:-$MODEL}
EFFORT=${FEATURE_LOOP_EFFORT:-$EFFORT}
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

# The run's record: what it was asked, a line per commit, and how it ended.
SUMMARIES=llm-dlc/loop-summaries
mkdir -p "$SUMMARIES" || exit 1
SUMMARY=$SUMMARIES/$(date +%F-%H%M%S)-$PROMPT.md
START=$(jj log --no-graph -r @- -T change_id) || exit 1

# A fresh session gets its id here, and it and a session with no transcript yet
# are created by the first turn. Claude Code keeps transcripts under the working
# directory's path with every other character turned into a dash.
FRESH=
if [[ "$SESSION_ID" == new ]]; then
  SESSION_ID=$(python3 -c 'import uuid; print(uuid.uuid4())') || exit 1
  FRESH=1
elif [[ ! -e "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/$(pwd | sed 's/[^A-Za-z0-9]/-/g')/$SESSION_ID.jsonl" ]]; then
  log "session $SESSION_ID has no transcript yet: the first turn creates it"
  FRESH=1
fi

# The brief without its "## Progress" section, which the session updates as it goes.
brief_hash() {
  awk '/^## / { progress = ($0 ~ /^## +Progress[[:space:]]*$/) } !progress' "$BRIEF" |
    sha256sum | cut -d' ' -f1
}
if [[ -n "$BRIEF" ]]; then
  BRIEF_HASH=$(brief_hash) || exit 1
  INSTRUCTION="Work on the brief in \`$BRIEF\`. Read it in full now, even if you have read it before: it is the instruction for this cycle and every cycle of this loop, and what you remember of it may be a summary. First run \`jj status\` and judge what a change in the working copy is. Another session may be at work in this repository at the same time (the verification loop collects job results and commits them, for one), and its uncommitted files are not yours. A change that belongs to the brief's current work (the step its \`## Progress\` section or your own last turn left in progress) is a cycle that was interrupted: finish, verify and commit it first. Anything else is another session's: leave it alone, never finish, revert or discard it, and keep it out of your commit by moving it below yours and back, as step 5 of \`.claude/skills/run-verification/SKILL.md\` shows. Finishing an interrupted step is this cycle's piece of work. Otherwise take the next piece of work the brief calls for that is not done yet, by its \`## Progress\` section if it has one (it carries over from earlier runs of this loop) and by the commits since (\`jj log -r '$START..@-'\` lists this run's), finish it, verify it, and commit it as CLAUDE.md describes. Don't edit the brief outside its \`## Progress\` section; if it has one, update it in the same commit with what this piece did and what comes next. If the rest of the brief is wrong or out of date, say so in the commit message."
fi
{
  echo "# Feature loop: $PROMPT"
  echo
  echo "Started $(date '+%F %T %Z'), ${CYCLES/inf/no limit on} cycles, session $SESSION_ID, $MODEL at $EFFORT effort, after change $START."
  echo
  echo "> $INSTRUCTION"
  echo
  [[ -n "$BRIEF" ]] && { echo "Brief \`$BRIEF\` at sha256 $BRIEF_HASH."; echo; }
  if [[ -n "$UNTIL" ]]; then
    echo "After each commit the session decides whether to go on:"
    echo
    echo "> $UNTIL"
    echo
  fi
  echo "## Commits"
  echo
} >"$SUMMARY"
note() { printf '%s\n' "$*" >>"$SUMMARY"; }
log "keeping a record of this run in $SUMMARY"

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
trap 'note; note "Interrupted $(date "+%F %T") during cycle $cycle."; exit 130' INT TERM

# `auto` is the mode this session has always run in. With -p nobody can answer a
# prompt, so anything auto mode would ask about is denied rather than left hanging.
# A second argument names a file that receives the raw event stream as well.
run_claude() {
  local session=(--resume "$SESSION_ID")
  [[ -n "$FRESH" ]] && session=(--session-id "$SESSION_ID")
  FRESH=
  claude -p "$1" "${session[@]}" --model "$MODEL" --effort "$EFFORT" \
    --permission-mode auto --output-format stream-json --verbose </dev/null |
    tee ${2:+"$2"} | show_progress
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

# With UNTIL: ask the session whether the loop goes on after this cycle's commit,
# while it still has the cycle in context. Sets $decision to continue, stop or
# unclear, and records the answer.
decide() {
  local stream answer verdict
  stream=$(mktemp "${XDG_RUNTIME_DIR:-/tmp}/feature-loop-decide.XXXXXX") || { decision=unclear; return; }
  log "cycle $cycle: asking whether to go on"
  run_claude "Cycle $cycle of the feature loop is committed. Before the next cycle starts, decide whether the loop should go on, by these instructions from the user: $UNTIL

Weigh them against what this run has done so far (\`jj log -r '$START..@-'\` lists its commits) and what is left. Reply with two or three sentences on why, then a last line that is exactly \`LOOP: continue\` or \`LOOP: stop\`. This turn only decides: don't edit files, commit, push or submit jobs." "$stream" ||
    log "cycle $cycle: decision turn exited with status $?"
  answer=$(result_text "$stream") || answer=
  rm -f "$stream"
  verdict=$(printf '%s\n' "$answer" | awk 'NF { last = $0 } END { print last }' | tr -d '`*_ \t\r' | tr '[:upper:]' '[:lower:]')
  case "$verdict" in
    loop:continue) decision=continue ;;
    loop:stop) decision=stop ;;
    *) decision=unclear ;;
  esac
  log "cycle $cycle: the session says $decision"
  note "  - decided to $decision: $(printf '%s' "$answer" | sed '/^[[:space:]`*_]*LOOP:/Id' | tr '\n' ' ' | sed 's/  */ /g; s/ *$//')"
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
  if [[ -n "$BRIEF" && "$(brief_hash)" != "$BRIEF_HASH" ]]; then
    log "the brief $BRIEF changed during the run, stopping before cycle $cycle"
    note; note "Stopped $(date '+%F %T'): the brief changed before cycle $cycle; restart the loop to work from the new one."
    exit 1
  fi

  log "cycle $cycle: $PROMPT instruction"
  with_state standing
  [[ -n "$reader" ]] && log "type +N, -N, =N, 0 to stop, ? or help"
  run_claude "$INSTRUCTION" || log "cycle $cycle: claude exited with status $?"

  after=$(last_change) || exit 1
  if [[ "$after" == "$before" ]]; then
    log "cycle $cycle: no commit, stopping; session $SESSION_ID needs attention"
    note; note "Stopped $(date '+%F %T'): cycle $cycle made no commit; session $SESSION_ID needs attention."
    exit 1
  fi
  log "cycle $cycle: committed $(jj log --no-graph -r @- -T 'description.first_line()')"
  note "- cycle $cycle, $(date '+%F %T'), \`$(jj log --no-graph -r @- -T 'change_id.short()')\`: $(jj log --no-graph -r @- -T 'description.first_line()')"

  decision=continue
  # The last cycle of a count ends the loop anyway, so there is nothing to decide.
  if [[ -n "$UNTIL" ]]; then
    read -r _ left <"$STATE"
    [[ "$left" == 0 ]] || decide
  fi
  if [[ "$decision" == unclear ]]; then
    log "cycle $cycle: no clear decision, stopping; session $SESSION_ID needs attention"
    note; note "Stopped $(date '+%F %T'): after cycle $cycle the session gave no clear LOOP: continue or LOOP: stop; session $SESSION_ID needs attention."
    exit 1
  fi

  log "cycle $cycle: compact"
  run_claude "/compact" || log "cycle $cycle: compact exited with status $?"

  read -r cycle remaining <"$STATE"
  if [[ "$decision" == stop ]]; then
    log "the session decided to stop: stopping after cycle $cycle"
    summarize
    note; note "Ended $(date '+%F %T') after $cycle cycle(s): the session decided the work was done."
    log "record of the run: $SUMMARY"
    exit 0
  fi
  if [[ "$remaining" == 0 ]]; then
    log "no cycles left: stopping after cycle $cycle"
    summarize
    note; note "Ended $(date '+%F %T') after $cycle cycle(s)."
    log "record of the run: $SUMMARY"
    exit 0
  fi
done

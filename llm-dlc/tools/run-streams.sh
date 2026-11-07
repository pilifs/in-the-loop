#!/usr/bin/env bash
# Run a brief's whole loop unattended, in one terminal: its parallel streams, each
# a feature loop in a jj workspace of its own on a branch of its own, then the
# brief's own loop, which merges them and finishes the work. You are needed only
# once that loop is done.
#
# Usage: [RUN_STREAMS_POLL=300] [RUN_STREAMS_JOB_WAIT=43200] [RUN_STREAMS_INTEGRATION_EVERY=3600] \
#          llm-dlc/tools/run-streams.sh engines|foundations
#   engines      llm-dlc/loops/engine-priorities.md: the streams jbmc and native, then the merge
#   foundations  llm-dlc/loops/foundations.md: the streams heap, summaries, observations and
#                alignment, with an integration check while they run, then the merge
#
# From the default workspace, in order:
#  1. Before any stream has a session, it compacts the conversation that planned
#     the streams, once. Each stream's brief forks its session from it ("- fork:"
#     in its Loop settings), so every stream starts from that conversation.
#  2. It adds a workspace per stream that doesn't have one, ../REPO-STREAM, from
#     the latest commit (@-).
#  3. It starts verification-loop.sh, unless one already runs here, so the jobs
#     the loops submit are run, collected and committed.
#  4. It runs each stream's loop, feature-loop.sh NAME-STREAM, from its
#     workspace, side by side, and looks after each until it is finished.
#     If the brief's Loop settings name "- integration: SCRIPT", it also runs
#     the integration check while they do (below).
#  5. It runs the brief's own loop, feature-loop.sh NAME, here: the merge (see
#     the brief's Streams section), then whatever is left. It starts in a fresh
#     session of its own.
#  6. It stops the verification loop after its run under way, and exits.
#
# Each brief ends its "## Progress" with a status line its loop keeps current:
# "- Status: working", "- Status: waiting on jobs ID ...", "- Status: done" or
# "- Status: blocked: what needs the user". When a loop stops, this script reads
# it: waiting on jobs, it polls every RUN_STREAMS_POLL seconds until each job's
# result is collected here and runs the loop again, which picks up where it
# left off (and counts the loop as blocked after RUN_STREAMS_JOB_WAIT seconds);
# done or blocked, the loop is finished. A loop that stops on an error or a cycle
# with no commit, with no such status, is run once more to finish what it left;
# twice in a row, it counts as blocked. A blocked stream doesn't hold the merge
# up: the merge takes what it committed and lists what needs the user.
#
# Every line comes here, prefixed with its loop ([jbmc], [native], [verify],
# [merge]). Ctrl-C stops them all, each recording the interruption. Running this
# again continues: workspaces and sessions are kept, nothing is compacted again,
# a loop whose status is done or blocked is not run again (set its status back
# to working to run it), and each loop finishes what an interrupted cycle left.
#
# The integration check, for a brief that names one, shows while the streams
# run whether their work fits together, rather than only at the merge. It keeps
# a workspace of its own, integration (../REPO-integration), used for nothing
# else: never committed from or pushed. Whenever a stream's @- has moved since the
# last check, at most once every RUN_STREAMS_INTEGRATION_EVERY seconds, it makes
# there a merge of every stream's @- and runs SCRIPT (a path in the repo, run
# from that workspace's root) in the systemd scope
# feature-loop-NAME-integration.scope with the loops' 3.5 GB cap, so the
# verification runner leaves it room as it does a loop. What it found, with the
# commits it merged, goes to llm-dlc/loop-summaries/NAME-integration.md here
# (NAME being the brief's), which each stream reads every cycle. A merge with
# conflicts is reported, not resolved, and SCRIPT isn't run on it. The previous
# check's merge is abandoned at the next; the reconcile loop forgets the
# workspace. Neither the streams' branches nor the default workspace change.
#
# A brief whose Loop settings say "- verification: separate" runs without the
# pipeline: step 3 is skipped, and nothing waits for a job. Its loops submit and
# commit jobs and go on; their results are for a person to review after the run,
# and a verification loop, if any, is run apart, by hand. A loop whose status
# says it waits on jobs anyway is counted as finished, with the jobs listed for
# that review.
#
# Exits 0 when the brief's own loop is finished, 1 if it is blocked or the setup
# fails, 2 for a bad argument and 130 if interrupted.

set -uo pipefail

usage() {
  echo "usage: run-streams.sh engines|foundations" >&2
  exit 2
}

(( $# == 1 )) || usage
NAME=$1
case "$NAME" in
  engines) BRIEF=llm-dlc/loops/engine-priorities.md STREAMS=(jbmc native) ;;
  foundations) BRIEF=llm-dlc/loops/foundations.md STREAMS=(heap summaries observations alignment) ;;
  *) usage ;;
esac
POLL=${RUN_STREAMS_POLL:-300}
JOB_WAIT=${RUN_STREAMS_JOB_WAIT:-43200}
INTEGRATION_EVERY=${RUN_STREAMS_INTEGRATION_EVERY:-3600}
[[ "$POLL" =~ ^[1-9][0-9]*$ && "$JOB_WAIT" =~ ^[0-9]+$ && "$INTEGRATION_EVERY" =~ ^[0-9]+$ ]] || usage

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd) || exit 1
cd "$ROOT" || exit 1
source llm-dlc/tools/loop-common.sh

if [[ "$(realpath "$(jj workspace root --ignore-working-copy --name default 2>/dev/null)")" != "$ROOT" ]]; then
  log "run this from the default workspace's copy of the script, not $ROOT"
  exit 2
fi

# "- key: value" under a brief's "## Loop settings" heading, as feature-loop.sh reads it.
setting() {
  awk -v key="$2" '
    /^## / { inside = ($0 ~ /^## +Loop settings[[:space:]]*$/); next }
    inside && match($0, "^[-*] +" key ": *") { v = substr($0, RLENGTH + 1); gsub(/[`[:space:]]/, "", v); print v; exit }
  ' "$1"
}
project_dir() { printf '%s/%s' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects" "$(printf '%s' "$1" | sed 's/[^A-Za-z0-9]/-/g')"; }

PARENT=
MODEL=$(setting "$BRIEF" model)
VERIFICATION=$(setting "$BRIEF" verification)
[[ -z "$VERIFICATION" || "$VERIFICATION" == separate ]] || { log "$BRIEF: '- verification: $VERIFICATION' is not a setting this knows (only separate)"; exit 1; }
EFFORT=$(setting "$BRIEF" effort)
declare -A DIR SESSION
fresh=0
for s in "${STREAMS[@]}"; do
  brief=${BRIEF%.md}-$s.md
  [[ -f "$brief" ]] || { log "no brief $brief"; exit 1; }
  ws=$(setting "$brief" workspace)
  [[ "$ws" == "$s" ]] || { log "$brief names workspace '${ws}', expected $s"; exit 1; }
  fork=$(setting "$brief" fork)
  [[ -n "$fork" ]] || { log "$brief has no '- fork:' in its Loop settings"; exit 1; }
  [[ -z "$PARENT" || "$fork" == "$PARENT" ]] || { log "the streams fork different sessions: $PARENT and $fork"; exit 1; }
  PARENT=$fork
  SESSION[$s]=$(setting "$brief" session)
  DIR[$s]=$(jj workspace root --ignore-working-copy --name "$s" 2>/dev/null) || DIR[$s]=
  if [[ -z "${DIR[$s]}" || ! -e "$(project_dir "${DIR[$s]}")/${SESSION[$s]}.jsonl" ]]; then
    fresh=$(( fresh + 1 ))
  fi
done

# The planning session, compacted once: before the first fork, when no stream has a session yet.
if (( fresh == ${#STREAMS[@]} )); then
  transcript=$(project_dir "$ROOT")/$PARENT.jsonl
  if [[ ! -f "$transcript" ]]; then
    log "the streams fork session $PARENT, and it has no transcript here: $transcript"
    log "copy it from the machine it ran on, to that path, before running this; continue it only here from then on"
    exit 1
  fi
  log "compacting session $PARENT, which every stream forks"
  claude -p "/compact" --resume "$PARENT" ${MODEL:+--model "$MODEL"} ${EFFORT:+--effort "$EFFORT"} \
    --permission-mode auto --output-format stream-json --verbose </dev/null | show_progress
  (( PIPESTATUS[0] == 0 )) || { log "the compact failed; nothing started"; exit 1; }
fi

for s in "${STREAMS[@]}"; do
  if [[ -z "${DIR[$s]}" ]]; then
    DIR[$s]=$(dirname "$ROOT")/$(basename "$ROOT")-$s
    log "adding jj workspace $s at ${DIR[$s]}"
    jj workspace add --name "$s" -r @- "${DIR[$s]}" >/dev/null || { log "could not add workspace $s"; exit 1; }
  fi
done

# The last "- Status:" line under a brief's "## Progress", without the label.
status_of() {
  awk '/^## / { inside = ($0 ~ /^## +Progress[[:space:]]*$/); next }
       inside && /^[-*] +Status: */ { s = $0 }
       END { sub(/^[-*] +Status: */, "", s); gsub(/`/, "", s); print s }' "$1"
}
finished() { [[ "$1" == done* || "$1" == blocked* ]]; }

# Whether every job named has its result collected here, by id or id prefix.
jobs_back() {
  local id
  for id in "$@"; do
    compgen -G "$ROOT/verification/results/$id*/result.json" >/dev/null || return 1
  done
}

# Run one loop until it is finished, as the header says: LABEL, the workspace it
# runs in, its name for feature-loop.sh, and its brief there. Exits 0 when its
# brief says done, 3 when it is blocked, 130 if interrupted.
supervise() {
  local label=$1 dir=$2 loop=$3 brief=$2/$4 code status failed=0 waited ids
  while :; do
    # Waiting on jobs, from this run or one before it: they come back first.
    status=$(status_of "$brief")
    if [[ "$VERIFICATION" == separate && "$status" == "waiting on jobs"* ]]; then
      log "[$label] its brief says $status; verification is separate, so nothing waits: counted as finished, the jobs left for review"
      exit 0
    fi
    if [[ "$status" == "waiting on jobs"* ]]; then
      read -ra ids <<<"$(tr ',;' '  ' <<<"${status#waiting on jobs}")"
      if (( ${#ids[@]} )) && ! jobs_back "${ids[@]}"; then
        log "[$label] waiting for ${ids[*]}, checking every ${POLL}s"
        waited=0
        until jobs_back "${ids[@]}"; do
          if (( waited >= JOB_WAIT )); then
            log "[$label] the jobs aren't back after ${JOB_WAIT}s: counted as blocked"
            exit 3
          fi
          sleep "$POLL"
          waited=$(( waited + POLL ))
        done
        log "[$label] the jobs are back"
      fi
    fi
    log "[$label] starting feature-loop.sh $loop in $dir"
    "$dir/llm-dlc/tools/feature-loop.sh" "$loop" </dev/null 2>&1 | sed -u "s/^/[$label] /"
    code=${PIPESTATUS[0]}
    (( code == 130 )) && exit 130
    status=$(status_of "$brief")
    log "[$label] the loop ended with status $code; its brief says: ${status:-no status}"
    case "$status" in
      done*) exit 0 ;;
      blocked*) exit 3 ;;
    esac
    if [[ "$VERIFICATION" == separate && "$status" == "waiting on jobs"* ]]; then
      log "[$label] verification is separate, so nothing waits: counted as finished, the jobs left for review"
      exit 0
    fi
    if [[ "$status" == "waiting on jobs"?* ]]; then
      read -ra ids <<<"$(tr ',;' '  ' <<<"${status#waiting on jobs}")"
      if ! jobs_back "${ids[@]}"; then
        failed=0
        continue
      fi
      log "[$label] it says it waits on jobs that are already back"  # counted as a stop with no reason
      code=1
    fi
    if (( code == 0 )); then
      log "[$label] it decided to stop, and its status doesn't say why: counted as done"
      exit 0
    fi
    failed=$(( failed + 1 ))
    if (( failed >= 2 )); then
      log "[$label] stopped twice in a row without a status that says why: counted as blocked; its session needs a look"
      exit 3
    fi
    log "[$label] running it again once, to finish what it left"
  done
}

# The integration check (see the header), when the brief names a script for it.
INTEGRATION=$(setting "$BRIEF" integration)
if [[ -n "$INTEGRATION" ]]; then
  [[ -x "$INTEGRATION" ]] || { log "the brief's integration script $INTEGRATION isn't an executable file here"; exit 1; }
  INTEGRATION_DIR=$(jj workspace root --ignore-working-copy --name integration 2>/dev/null) || INTEGRATION_DIR=
  if [[ -z "$INTEGRATION_DIR" ]]; then
    INTEGRATION_DIR=$(dirname "$ROOT")/$(basename "$ROOT")-integration
    log "adding jj workspace integration at $INTEGRATION_DIR, for the integration check"
    jj workspace add --name integration -r @- "$INTEGRATION_DIR" >/dev/null || { log "could not add workspace integration"; exit 1; }
  fi
  INTEGRATION_REPORT=$ROOT/llm-dlc/loop-summaries/$(basename "$BRIEF" .md)-integration.md
  INTEGRATION_SCOPE=feature-loop-$(basename "$BRIEF" .md)-integration
fi

# Every stream's @-, as short commit ids, in the order of STREAMS.
stream_heads() {
  local s
  for s in "${STREAMS[@]}"; do
    jj log --ignore-working-copy --no-graph -r "$s@-" -T 'commit_id.short(12) ++ " "' 2>/dev/null || printf '? '
  done
}

# One check of the streams' current commits: merge, run the script, report.
integrate_once() {
  local heads=$1 s revs=() previous conflicted code tmp
  for s in "${STREAMS[@]}"; do revs+=("$s@-"); done
  tmp=$(mktemp) || return 1
  {
    printf '# Integration check of %s\n\n' "$BRIEF"
    printf -- '- When: %s\n' "$(date '+%F %T')"
    printf -- '- Merged: '
    for s in "${!STREAMS[@]}"; do printf '%s@- %s; ' "${STREAMS[$s]}" "$(cut -d' ' -f$(( s + 1 )) <<<"$heads")"; done
    printf '\n- Where: the workspace integration, %s\n' "$INTEGRATION_DIR"
  } >"$tmp"
  previous=$(cd "$INTEGRATION_DIR" && jj log --no-graph -r @ -T 'if(description, "", change_id)' 2>/dev/null)
  if ! (cd "$INTEGRATION_DIR" && jj new --quiet "${revs[@]}" >/dev/null 2>&1); then
    printf -- '- Result: the merge could not be made (jj new failed)\n' >>"$tmp"
    mv "$tmp" "$INTEGRATION_REPORT"
    return 1
  fi
  [[ -n "$previous" ]] && (cd "$INTEGRATION_DIR" && jj abandon --quiet "$previous" >/dev/null 2>&1)
  conflicted=$(cd "$INTEGRATION_DIR" && jj resolve --list 2>/dev/null)
  if [[ -n "$conflicted" ]]; then
    printf -- '- Result: the streams conflict; the script was not run. Files in conflict:\n\n```\n%s\n```\n' "$conflicted" >>"$tmp"
    mv "$tmp" "$INTEGRATION_REPORT"
    log "[integration] the streams conflict: see $INTEGRATION_REPORT"
    return 0
  fi
  log "[integration] running $INTEGRATION on $heads"
  (cd "$INTEGRATION_DIR" && systemd-run --user --scope --quiet --collect --unit="$INTEGRATION_SCOPE" \
    -p MemoryMax=3.5G -p MemorySwapMax=0 -p OOMPolicy=continue \
    timeout 3600 "$INTEGRATION_DIR/$INTEGRATION" </dev/null) >"$tmp.out" 2>&1
  code=$?
  printf -- '- Result: %s (exit %s)\n\n## Output, last 200 lines\n\n```\n' \
    "$( (( code == 0 )) && echo passed || echo failed )" "$code" >>"$tmp"
  tail -n 200 "$tmp.out" >>"$tmp"
  printf '```\n' >>"$tmp"
  rm -f "$tmp.out"
  mv "$tmp" "$INTEGRATION_REPORT"
  log "[integration] $( (( code == 0 )) && echo passed || echo "failed (exit $code)" ): see $INTEGRATION_REPORT"
}

# Runs until killed: a check whenever a stream's @- has moved, at most every INTEGRATION_EVERY seconds.
integrate() {
  local last= heads
  mkdir -p "$(dirname "$INTEGRATION_REPORT")"
  while :; do
    heads=$(stream_heads)
    if [[ "$heads" != "$last" ]]; then
      integrate_once "$heads"
      last=$heads
      sleep "$INTEGRATION_EVERY"
    else
      sleep "$POLL"
    fi
  done
}

# Each stream runs in a process group of its own (job control), so a Ctrl-C here
# reaches only this script, which passes it on to each group whole: the loop, its
# claude and its output. Without job control, bash would start them ignoring
# SIGINT, and a loop could neither be stopped by it nor record it.
set -m
declare -A PID
VERIFY=
INTEGRATE=
stop_all() {
  log "stopping every loop"
  for p in "${PID[@]}" $VERIFY; do kill -INT -- "-$p" 2>/dev/null; done
  [[ -n "$INTEGRATE" ]] && kill -TERM -- "-$INTEGRATE" 2>/dev/null
}
trap 'stop_all; wait; exit 130' INT TERM

# One already running for this repo: a bash running the script, which works from the repo's root.
verification_running() {
  local pid
  for pid in $(pgrep -f 'bash [^ ]*verification-loop\.sh'); do
    [[ "$(readlink "/proc/$pid/cwd")" == "$ROOT" ]] && return 0
  done
  return 1
}
if [[ "$VERIFICATION" == separate ]]; then
  log "verification is separate for this brief: no verification loop is started, and nothing waits for a job"
elif verification_running; then
  log "a verification loop already runs here: the loops' jobs are left to it"
else
  log "starting verification-loop.sh, for the jobs the loops submit"
  llm-dlc/tools/verification-loop.sh </dev/null > >(sed -u "s/^/[verify] /") 2>&1 &
  VERIFY=$!
fi

for s in "${STREAMS[@]}"; do
  brief=${BRIEF%.md}-$s.md
  status=$(status_of "${DIR[$s]}/$brief")
  if finished "$status"; then
    log "[$s] its brief says $status: not run again"
    continue
  fi
  supervise "$s" "${DIR[$s]}" "$NAME-$s" "$brief" &
  PID[$s]=$!
done
if [[ -n "$INTEGRATION" ]] && (( ${#PID[@]} )); then
  log "[integration] checking the streams together as they commit, into $INTEGRATION_REPORT"
  integrate &
  INTEGRATE=$!
fi

for s in "${!PID[@]}"; do
  wait "${PID[$s]}"
  code=$?
  (( code == 130 )) && { log "[$s] interrupted"; stop_all; wait; exit 130; }
  log "[$s] finished: $(status_of "${DIR[$s]}/${BRIEF%.md}-$s.md")"
done
PID=()
if [[ -n "$INTEGRATE" ]]; then
  kill -TERM -- "-$INTEGRATE" 2>/dev/null
  wait "$INTEGRATE" 2>/dev/null
  INTEGRATE=
  log "[integration] stopped: every stream is finished"
fi

code=0
status=$(status_of "$ROOT/$BRIEF")
if finished "$status"; then
  log "[merge] its brief says $status: not run again"
else
  log "every stream is finished: the brief's own loop merges them"
  supervise merge "$ROOT" "$NAME" "$BRIEF" &
  PID[merge]=$!
  wait "${PID[merge]}"
  code=$?
  PID=()
fi
if [[ -n "$VERIFY" ]]; then
  log "stopping the verification loop after its run under way"
  kill -USR1 "$VERIFY" 2>/dev/null
  wait "$VERIFY"
fi
(( code == 130 )) && exit 130
status=$(status_of "$ROOT/$BRIEF")
log "finished: the brief $BRIEF says ${status:-no status}"
log "what needs you: its Progress, verification/findings.md and the run records in llm-dlc/loop-summaries/"
[[ "$status" == done* ]] && exit 0
exit 1

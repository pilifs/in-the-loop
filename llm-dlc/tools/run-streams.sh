#!/usr/bin/env bash
# Run a brief's whole loop unattended, in one terminal: its parallel streams, each
# a feature loop in a jj workspace of its own on a branch of its own, each merged
# into this workspace's line by the run's watcher as soon as it is finished. A
# brief that names no streams is run as its own loop alone. There is no merge
# loop: until 2026-11-17 the brief's own loop ran after every stream had finished,
# to merge them and finish the work.
#
# Usage: [RUN_STREAMS_POLL=60] [RUN_STREAMS_JOB_WAIT=43200] [RUN_STREAMS_INTEGRATION_EVERY=3600] \
#          llm-dlc/tools/run-streams.sh [--plan] NAME|FILE.md
#   NAME is a brief of llm-dlc/loops/ (NAME.md), FILE.md a brief's file. The brief names its streams in its Loop
#   settings, "- streams: a, b, c", each with a brief of its own beside it (NAME-a.md); a brief that names none has
#   no streams, and its own loop is the whole run. --plan prints the brief and its streams and starts nothing.
#   A person starts a run with /run-brief, whose watcher starts this script (llm-dlc/tools/brief_run.py) after the
#   run's foundation stage, and answers what it asks; by hand it runs as before. The briefs older than the
#   setting are still known by name:
#   engines      llm-dlc/loops/engine-priorities.md: the streams jbmc and native
#   foundations  llm-dlc/loops/foundations.md: the streams heap, summaries, observations and
#                alignment, with an integration check while they run
#   cleanup      llm-dlc/loops/cleanup.md: the streams native, jbmc and examples, with an
#                integration check and the verification loop
#   application-core  llm-dlc/loops/application-core.md: the streams objects, values,
#                environment and reuse, with an integration check and the
#                verification loop
#   example-targets  llm-dlc/loops/example-targets.md: the streams runtime, negative,
#                positive and workflow, with an integration check and the
#                verification loop
#   (Each of these ran with the merge loop, which is gone: a brief's own work after its streams is now a brief of
#   its own, run after them.)
#
# From the default workspace, in order:
#  1. Before any stream has a session, it compacts the conversation that planned
#     the streams, once. Each stream's brief forks its session from it ("- fork:"
#     in its Loop settings), so every stream starts from that conversation.
#  2. It adds a workspace per stream that doesn't have one, from the latest
#     commit (@-), named by the stream brief's "- workspace: NAME" and made at
#     ../REPO-NAME. The names must differ from every other workspace's, so a
#     brief names them after itself (cleanup-native); a directory already at
#     that path, such as a forgotten workspace's, stops the run before anything
#     starts.
#  3. It starts verification-loop.sh, unless one already runs here, so the jobs
#     the loops submit are run, collected and committed. With a watcher it starts
#     none: the watcher keeps the queue itself (brief_run.py wait starts the
#     runner when jobs wait, and collects and commits each result), so that it
#     is the one session committing in this workspace while the run is under way.
#  4. It runs each stream's loop, feature-loop.sh NAME-STREAM, from its
#     workspace, side by side, and looks after each until it is finished.
#     If the brief's Loop settings name "- integration: SCRIPT", it also runs
#     the integration check while they do (below).
#  5. With a watcher, it puts each stream to it to merge the moment the stream is
#     finished, while the others still run (conductor.py's `merge` question): the
#     watcher merges the stream's @- into this workspace's line
#     (brief_run.py merge, which also answers). Without one, nothing is merged,
#     and the end of the run names the command that merges each stream.
#     A brief with no streams instead runs its own loop, feature-loop.sh NAME,
#     here, in a fresh session of its own.
#  6. It stops the verification loop it started, if any, after its run under way, and exits.
#
# A stream brief's "- fork:" is optional: without one in any of them, each stream starts a session of its own,
# nothing is compacted, and the brief each cycle reads is all a stream starts from.
#
# With a watcher (RUN_STREAMS_WATCHER, the run's directory: brief_run.py sets it), a loop that ends blocked is put
# to it before it counts as finished (conductor.py's `blocked` question): `rerun` runs the loop again, for a
# stream whose inbox now holds the answer it was blocked on, and `leave`, or no answer within
# RUN_STREAMS_BLOCKED_WAIT seconds (1800), leaves it finished with its blocked status, as without a watcher. So a decision
# made during the run reaches its stream during the run, not after it. A loop is run again this way
# RUN_STREAMS_RERUNS times (2) in one run of this script: the next time it ends blocked it is left without asking,
# as the brief template's timebox leaves an item that failed twice.
#
# A finished stream, blocked or done, is put to the watcher to merge (`merge`, answered `merged` or `leave`):
# a blocked one's commits are worth having too, and the watcher judges whether they stand alone. No answer within
# RUN_STREAMS_MERGE_WAIT seconds (1800) leaves it unmerged.
#
# A run is stopped at a boundary by the file stop-after in its state directory (brief_run.py stop writes it, and
# tells each loop to end after its cycle under way): a loop that ends is then not run again, one waiting on jobs
# stops waiting, no stream is put to the watcher to merge, and the script exits 3. Nothing is interrupted and nothing uncommitted
# is left; running the script again continues, and removes the file.
#
# A stream is run again inside the run by a request in the state directory (rerun/LABEL: brief_run.py rerun
# writes it): once the stream's own process here has ended, however it ended, its loop is started again as at
# the start of the run, with its counts of failures and reruns at nought, and put to the watcher to merge when it
# is finished. A request found at the start runs a stream whose status says done or blocked, which is otherwise
# not run again. Until 2026-11-18 a stream that had ended (a session killed for memory, VF-037) could be started
# again only by hand, outside this script's bookkeeping, or after the whole run.
#
# Before a loop is started its systemd scope (feature-loop-BRIEF.scope) is cleared of what an ended loop left
# there: when the kernel kills a session for memory, the tests it ran live on in the scope, and feature-loop.sh
# refuses to start beside them, which counted as the stream's second failure (VF-037). A scope a loop is still
# at work in (one started by hand) is left alone.
#
# Each brief ends its "## Progress" with a status line its loop keeps current:
# "- Status: working", "- Status: waiting on jobs ID ...", "- Status: done" or
# "- Status: blocked: what needs the user". When a loop stops, this script reads
# it: waiting on jobs, it polls every RUN_STREAMS_POLL seconds until each job's
# result is collected here and runs the loop again, which picks up where it
# left off (and counts the loop as blocked after RUN_STREAMS_JOB_WAIT seconds;
# the poll was 300 seconds until 2026-11-16, which left a stream idle for minutes after its result was in);
# done or blocked, the loop is finished. A loop that stops with no such status,
# on an error, a cycle with no commit, or a decision to stop that left it
# working, is run once more to finish what it left; twice in a row, it counts as
# blocked. (Until 2026-11-08 a decision to stop counted as done whatever the
# status said, and three application-core streams that were waiting on jobs or
# blocked went to the merge as finished.) A blocked stream holds no other up.
#
# Every line comes here, prefixed with its loop ([jbmc], [native], [verify],
# [brief] for a brief without streams). Ctrl-C stops them all, each recording the interruption. Running this
# again continues: workspaces and sessions are kept, nothing is compacted again,
# a loop whose status is done or blocked is not run again (set its status back
# to working to run it), and each loop finishes what an interrupted cycle left.
#
# The integration check, for a brief that names one, shows while the streams
# run whether their work fits together, rather than only at the merge: it keeps
# a rolling integration line (llm-dlc/tools/integration.py, and
# llm-dlc/loops/stream-conductor.md, Design 1), in a workspace of its own,
# NAME-integration (../REPO-NAME-integration), used for nothing else and never
# pushed. Whenever a stream's @- has moved since the last check, at most once
# every RUN_STREAMS_INTEGRATION_EVERY seconds, it makes there a merge of every
# stream's @- and of the line's newest passing merge. The generated trace files
# (llm-dlc/index.json, traces/README.md, traces/metrics.json, README.md's index
# table and the decision views) conflict whenever two streams have committed:
# the merged tree's `sync.py regenerate` rewrites them from the session files,
# which merge cleanly. With no other conflict it runs SCRIPT (a path in the
# repo, run from that workspace's root) in the systemd scope
# feature-loop-NAME-integration.scope with a 6 GB cap and a loop's CPU weight,
# so the verification runner leaves it room as it does a loop. A merge that
# passes is committed on the line, so the line always holds the newest merge
# known to work; `integration.py line BRIEF` names it. A merge with a conflict
# in real work, or one the script fails, is left uncommitted and triaged into
# the decision record and the streams' inboxes in the default workspace: a
# `failure` item for a stream whose changes alone are named, or an open
# question on how two or more streams' changes meet, with a `queued` item for
# each, closed as settled (and each side told it may go on) once a merge passes.
# What it found, with the commits it merged, goes to
# llm-dlc/loop-summaries/NAME-integration.md here (NAME being the brief's),
# which each stream reads every cycle. Neither the streams' branches nor the
# default workspace's line change; the reconcile loop forgets the workspace.
# (Before 2026-11-07 it was named integration, for every brief; before
# stream-conductor step 3 it committed nothing and triaged nothing.)
#
# A brief whose Loop settings say "- verification: separate" runs without the
# pipeline: step 3 is skipped, and this script waits for no job. Its loops submit
# and commit jobs and go on (a session may await a quick one, at a higher
# priority, inside its cycle); the rest are for a person to review after the run,
# and a verification loop, if any, is run apart, by hand. A loop whose status
# says it waits on jobs anyway is counted as finished, with the jobs listed for
# that review.
#
# In tmux, it makes the run easy to follow over ssh. It turns the mouse on for
# the tmux session, so the wheel scrolls back through the output (or Ctrl-b [,
# then PgUp, PgDn and the arrows; q to leave). A pane keeps the history limit it
# was made with, so if this one keeps fewer than RUN_STREAMS_HISTORY lines
# (200000) it raises the session's limit and goes on in a new window,
# streams-NAME, which keeps them; that window stays open with the output after
# the run, until Enter. "- new-window: no" in the brief's Loop settings, or
# RUN_STREAMS_NEW_WINDOW=no (which wins over the brief), keeps it in this pane. And it
# shows a status bar at the bottom of the pane, refreshed every
# RUN_STREAMS_STATUS_EVERY seconds (15): the run's age and spend, then for each
# loop its current cycle, its commits, its spend, its state, and how long since
# its last output line, and the integration check's last result. The same line
# is logged every half hour (every quarter hour outside tmux, where there is no
# bar). Spend is what the "turn done" figures the loops print rose by (each is
# its session's total so far, a fork's starting at its parent's), kept with
# the rest of the state in llm-dlc/loop-summaries/run-streams-NAME/, so it
# survives a restart. llm-dlc/tools/streams_status.py reads and renders it.
#
# Exits 0 when the brief says done at the end (for a brief of streams, brief_run.py merge sets it once every
# stream is merged and done), 1 if it does not or the setup fails, 2 for a bad argument, 3 when stopped at a boundary and 130 if interrupted.

set -uo pipefail

usage() {
  echo "usage: run-streams.sh [--plan] NAME|FILE.md   (a brief of llm-dlc/loops/ by name, or a brief's file)" >&2
  exit 2
}

PLAN=
[[ "${1:-}" == --plan ]] && { PLAN=1; shift; }
(( $# == 1 )) || usage
POLL=${RUN_STREAMS_POLL:-60}
JOB_WAIT=${RUN_STREAMS_JOB_WAIT:-43200}
INTEGRATION_EVERY=${RUN_STREAMS_INTEGRATION_EVERY:-3600}
BLOCKED_WAIT=${RUN_STREAMS_BLOCKED_WAIT:-1800}
MERGE_WAIT=${RUN_STREAMS_MERGE_WAIT:-1800}
RERUNS=${RUN_STREAMS_RERUNS:-2}
[[ "$RERUNS" =~ ^[0-9]+$ ]] || usage
[[ "$POLL" =~ ^[1-9][0-9]*$ && "$JOB_WAIT" =~ ^[0-9]+$ && "$INTEGRATION_EVERY" =~ ^[0-9]+$ && "$BLOCKED_WAIT" =~ ^[0-9]+$ && "$MERGE_WAIT" =~ ^[0-9]+$ ]] || usage

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd) || exit 1
cd "$ROOT" || exit 1
source llm-dlc/tools/loop-common.sh

# "- key: value" under a brief's "## Loop settings" heading, as feature-loop.sh reads it.
setting() {
  awk -v key="$2" '
    /^## / { inside = ($0 ~ /^## +Loop settings[[:space:]]*$/); next }
    inside && match($0, "^[-*] +" key ": *") { v = substr($0, RLENGTH + 1); gsub(/[`[:space:]]/, "", v); print v; exit }
  ' "$1"
}

# The brief, and the name its run goes by: the brief file's, but for the one brief whose run was named otherwise.
NAME=$1
case "$NAME" in
  engines) BRIEF=llm-dlc/loops/engine-priorities.md ;;
  *.md)
    BRIEF=$NAME
    [[ "$BRIEF" == "$ROOT"/* ]] && BRIEF=${BRIEF#"$ROOT"/}
    NAME=$(basename "$BRIEF" .md)
    [[ "$NAME" == engine-priorities ]] && NAME=engines
    ;;
  *) BRIEF=llm-dlc/loops/$NAME.md ;;
esac
[[ "$NAME" =~ ^[a-z0-9][a-z0-9-]*$ ]] || usage
[[ "$BRIEF" != /* && -f "$BRIEF" ]] || { echo "run-streams.sh: no brief $BRIEF in $ROOT" >&2; exit 2; }
# Its streams: the brief's "- streams: a, b" (the setting is read with its spaces removed), or, for the briefs
# written before the setting, the list this script used to hold.
STREAMS=()
IFS=, read -ra STREAMS <<<"$(setting "$BRIEF" streams)"
if (( ${#STREAMS[@]} == 0 )); then
  case "$NAME" in
    engines) STREAMS=(jbmc native) ;;
    foundations) STREAMS=(heap summaries observations alignment) ;;
    cleanup) STREAMS=(native jbmc examples) ;;
    application-core) STREAMS=(objects values environment reuse) ;;
    example-targets) STREAMS=(runtime negative positive workflow) ;;
  esac
fi
for s in "${STREAMS[@]}"; do
  [[ "$s" =~ ^[a-z0-9][a-z0-9-]*$ && "$s" != brief && "$s" != integration ]] || {
    echo "run-streams.sh: $BRIEF names a stream '$s': a stream's name is lower-case letters, digits and hyphens, and not brief or integration" >&2
    exit 2
  }
done
if [[ -n "$PLAN" ]]; then
  echo "name: $NAME"
  echo "brief: $BRIEF"
  for s in "${STREAMS[@]}"; do echo "stream: $s ${BRIEF%.md}-$s.md"; done
  exit 0
fi

if [[ "$(realpath "$(jj workspace root --ignore-working-copy --name default 2>/dev/null)")" != "$ROOT" ]]; then
  log "run this from the default workspace's copy of the script, not $ROOT"
  exit 2
fi

# tmux: scrollback and the status bar (see the header).
PANE=
HISTORY=${RUN_STREAMS_HISTORY:-200000}
# Whether to move to a new window: RUN_STREAMS_NEW_WINDOW, else the brief's "- new-window:", else yes.
NEW_WINDOW=${RUN_STREAMS_NEW_WINDOW:-$(setting "$BRIEF" new-window)}
NEW_WINDOW=${NEW_WINDOW:-yes}
[[ "$NEW_WINDOW" == yes || "$NEW_WINDOW" == no ]] || { log "new-window must be yes or no, not '$NEW_WINDOW'"; exit 2; }
STATUS_EVERY=${RUN_STREAMS_STATUS_EVERY:-15}
[[ "$HISTORY" =~ ^[0-9]+$ && "$STATUS_EVERY" =~ ^[1-9][0-9]*$ ]] || usage
if [[ -n "${TMUX:-}" && -n "${TMUX_PANE:-}" ]] && command -v tmux >/dev/null; then
  tmux set-option -t "$TMUX_PANE" mouse on >/dev/null 2>&1
  have=$(tmux display-message -p -t "$TMUX_PANE" '#{history_limit}' 2>/dev/null)
  if [[ "$have" =~ ^[0-9]+$ ]] && (( have < HISTORY )) && [[ "$NEW_WINDOW" != no ]]; then
    tmux set-option -t "$TMUX_PANE" history-limit "$HISTORY" >/dev/null 2>&1
    passed=()
    while IFS= read -r kv; do passed+=(-e "$kv"); done < <(env | grep -E '^((RUN_STREAMS|FEATURE_LOOP|VERIFICATION_LOOP)_[A-Z_]*|CLAUDE_CONFIG_DIR)=')
    if tmux new-window -n "streams-$NAME" -c "$ROOT" "${passed[@]}" -e RUN_STREAMS_NEW_WINDOW=no -e RUN_STREAMS_IN_WINDOW=1 \
        bash -c '"$0" "$1"; code=$?; printf "\nrun-streams.sh %s ended with status %s. Scroll back with the mouse wheel or Ctrl-b [; press Enter to close this window.\n" "$1" "$code"; read -r' \
        "$ROOT/llm-dlc/tools/run-streams.sh" "$NAME"; then
      log "this pane keeps only $have lines of history, so the run goes on in the new tmux window streams-$NAME, which keeps $HISTORY"
      exit 0
    fi
    log "could not open a tmux window: going on here, with $have lines of history"
  fi
  if [[ "$have" =~ ^[0-9]+$ ]] && (( have < HISTORY )) && [[ "$NEW_WINDOW" == no && -z "${RUN_STREAMS_IN_WINDOW:-}" ]]; then
    tmux set-option -t "$TMUX_PANE" history-limit "$HISTORY" >/dev/null 2>&1
    log "this pane keeps $have lines of history; new panes in this tmux session now keep $HISTORY (new-window is no, so the run stays here)"
  fi
  PANE=$TMUX_PANE
  tmux set-option -p -t "$PANE" pane-border-status bottom >/dev/null 2>&1
  tmux set-option -p -t "$PANE" pane-border-format ' #{@run_streams} ' >/dev/null 2>&1
  tmux set-option -p -t "$PANE" @run_streams "run-streams.sh $NAME: starting" >/dev/null 2>&1
  log "tmux: the mouse wheel scrolls (or Ctrl-b [, then PgUp/PgDn; q to leave); the status bar is at the bottom of this pane"
else
  log "not in tmux: no status bar, and scrollback is the terminal's; run it inside tmux (tmux new -s streams) for both"
fi
project_dir() { printf '%s/%s' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects" "$(printf '%s' "$1" | sed 's/[^A-Za-z0-9]/-/g')"; }

PARENT=
MODEL=$(setting "$BRIEF" model)
VERIFICATION=$(setting "$BRIEF" verification)
[[ -z "$VERIFICATION" || "$VERIFICATION" == separate ]] || { log "$BRIEF: '- verification: $VERIFICATION' is not a setting this knows (only separate)"; exit 1; }
EFFORT=$(setting "$BRIEF" effort)
declare -A DIR SESSION WS
fresh=0
for s in "${STREAMS[@]}"; do
  brief=${BRIEF%.md}-$s.md
  [[ -f "$brief" ]] || { log "no brief $brief"; exit 1; }
  ws=$(setting "$brief" workspace)
  [[ -n "$ws" ]] || { log "$brief has no '- workspace:' in its Loop settings"; exit 1; }
  [[ "$ws" != default && "$ws" != "$NAME-integration" ]] || { log "$brief names workspace '$ws', which this script keeps for itself"; exit 1; }
  for other in "${!WS[@]}"; do
    [[ "${WS[$other]}" != "$ws" ]] || { log "the streams $other and $s both name workspace '$ws'"; exit 1; }
  done
  WS[$s]=$ws
  fork=$(setting "$brief" fork)
  (( ${#WS[@]} == 1 )) || [[ "$fork" == "$PARENT" ]] || { log "the streams fork different sessions: ${PARENT:-none} and ${fork:-none}"; exit 1; }
  PARENT=$fork
  SESSION[$s]=$(setting "$brief" session)
  DIR[$s]=$(jj workspace root --ignore-working-copy --name "$ws" 2>/dev/null) || DIR[$s]=
  if [[ -z "${DIR[$s]}" || ! -e "$(project_dir "${DIR[$s]}")/${SESSION[$s]}.jsonl" ]]; then
    fresh=$(( fresh + 1 ))
  fi
done

# A workspace to add needs its directory free: a forgotten workspace's directory
# stays on disk, and jj would refuse it only after the planning session was compacted.
INTEGRATION=$(setting "$BRIEF" integration)
INTEGRATION_WS=$NAME-integration
INTEGRATION_DIR=
if [[ -n "$INTEGRATION" ]]; then
  INTEGRATION_DIR=$(jj workspace root --ignore-working-copy --name "$INTEGRATION_WS" 2>/dev/null) || INTEGRATION_DIR=
fi
taken=0
for s in "${STREAMS[@]}" ${INTEGRATION:+integration}; do
  if [[ "$s" == integration ]]; then
    [[ -z "$INTEGRATION_DIR" ]] || continue
    want=$(dirname "$ROOT")/$(basename "$ROOT")-$INTEGRATION_WS
  else
    [[ -z "${DIR[$s]}" ]] || continue
    want=$(dirname "$ROOT")/$(basename "$ROOT")-${WS[$s]}
  fi
  if [[ -e "$want" ]]; then
    log "$want already exists, but no jj workspace here is at it: a forgotten workspace's directory? Delete it, or name another workspace in the brief"
    taken=1
  fi
done
(( taken == 0 )) || exit 1

# The planning session, compacted once: before the first fork, when no stream has a session yet.
if [[ -z "$PARENT" ]]; then
  (( ${#STREAMS[@]} == 0 )) || log "the streams fork no session: each starts one of its own, from its brief"
elif (( fresh == ${#STREAMS[@]} )); then
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

# A new workspace has none of the session logs this one stores and has not uploaded yet, and every commit's check
# there would report each as an error: it takes them from here (sync.py adopt-logs).
adopt_logs() {
  (cd "$1" && python3 llm-dlc/tools/sync.py adopt-logs >/dev/null 2>&1) || log "the workspace at $1 could not take the session logs it lacks (sync.py adopt-logs there)"
}

for s in "${STREAMS[@]}"; do
  if [[ -z "${DIR[$s]}" ]]; then
    DIR[$s]=$(dirname "$ROOT")/$(basename "$ROOT")-${WS[$s]}
    log "adding jj workspace ${WS[$s]} at ${DIR[$s]}"
    jj workspace add --name "${WS[$s]}" -r @- "${DIR[$s]}" >/dev/null || { log "could not add workspace ${WS[$s]}"; exit 1; }
    adopt_logs "${DIR[$s]}"
  fi
done

# A stream's run records are its own workspace's (feature-loop.sh writes them where it runs), and
# only this workspace publishes them (sync.py): they are copied here at the start and after each of the
# stream's runs, so the stream's merge publishes them. LABEL names the loop in the log.
collect_records() {
  local dir=$1 label=$2 line
  [[ "$dir" == "$ROOT" ]] && return 0
  python3 "$ROOT/llm-dlc/tools/run_records.py" collect "$dir" "$ROOT" | while IFS= read -r line; do log "[$label] $line"; done
}

# Records a stream's earlier runs left in its workspace (an interrupted run of this script).
for s in "${STREAMS[@]}"; do collect_records "${DIR[$s]}" "$s"; done

# The last "- Status:" line under a brief's "## Progress", without the label.
status_of() {
  awk '/^## / { inside = ($0 ~ /^## +Progress[[:space:]]*$/); next }
       inside && /^[-*] +Status: */ { s = $0 }
       END { sub(/^[-*] +Status: */, "", s); gsub(/`/, "", s); print s }' "$1"
}
finished() { [[ "$1" == done* || "$1" == blocked* ]]; }

# The job ids in a "waiting on jobs ..." status: the words shaped like one
# (20261107-172721-...). Others, such as the template's own "ID" copied in
# ("waiting on jobs ID 2026..."), are skipped: as an id, "ID" never comes back,
# and the loop would wait RUN_STREAMS_JOB_WAIT for nothing (cleanup-jbmc, 2026-11-07).
job_ids() {
  local w
  for w in $(tr ',;' '  ' <<<"${1#waiting on jobs}"); do
    [[ "$w" =~ ^[0-9]{8}-[0-9]{6} ]] && printf '%s ' "$w"
  done
}

# Whether every job named has its result collected here, by id or id prefix.
jobs_back() {
  local id
  for id in "$@"; do
    compgen -G "$ROOT/verification/results/$id*/result.json" >/dev/null || return 1
  done
}

# The status bar's state (see the header): spend and the run's start survive a
# restart; phases, cycles and activity are this invocation's.
STATE=$ROOT/llm-dlc/loop-summaries/run-streams-$NAME
mkdir -p "$STATE" || exit 1
rm -f "$STATE"/*.phase "$STATE"/*.cycle "$STATE"/*.last "$STATE/stop-after"
stopping() { [[ -e "$STATE/stop-after" ]]; }
[[ -s "$STATE/start" ]] || date +%s >"$STATE/start"
START=$(<"$STATE/start")
# A loop's phase, for the status bar, and each change of it with its time (LABEL.phases), which is where a summary's
# time working, waiting on jobs, blocked, and finished while others still ran comes from (brief_run.py).
phase() {
  printf '%s\n' "$2" >"$STATE/$1.phase"
  printf '%s\t%s\n' "$(date +%s)" "$2" >>"$STATE/$1.phases"
}

# With a watcher, whether a loop that ended blocked is run again (see the header): LABEL, its status, its brief.
rerun_blocked() {
  [[ -n "${RUN_STREAMS_WATCHER:-}" ]] || return 1
  local asked
  phase "$1" "blocked: put to the watcher"
  log "[$1] asking the watcher whether it is run again, for ${BLOCKED_WAIT}s at most"
  asked=$(python3 "$ROOT/llm-dlc/tools/conductor.py" ask "$RUN_STREAMS_WATCHER" blocked --answers rerun,leave \
    --wait "$BLOCKED_WAIT" "loop=$1" "brief=$3" "status=$2" 2>/dev/null)
  log "[$1] the watcher: ${asked:-none}"
  [[ "${asked%%$'\t'*}" == rerun ]]
}

# Stop a loop's scope when all it holds is what an ended loop left (see the header): the loop's name, its label,
# the folder it works in. Fails, leaving the scope alone, when a loop is at work in it: a feature loop in that
# folder (a test of these scripts that the ended loop left running works in a folder of its own).
CGROUPS=${RUN_STREAMS_CGROUP_ROOT:-/sys/fs/cgroup}
clear_scope() {
  local scope=feature-loop-$1.scope group pid left=0
  systemctl --user is-active --quiet "$scope" 2>/dev/null || return 0
  group=$(systemctl --user show -p ControlGroup --value "$scope" 2>/dev/null)
  for pid in $(cat "$CGROUPS$group/cgroup.procs" 2>/dev/null); do
    # feature-loop.sh runs from a private copy of itself, feature-loop.XXXXXX
    if [[ "$(readlink "/proc/$pid/cwd" 2>/dev/null)" == "$3" ]] &&
       tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null | grep -q 'feature-loop\.'; then
      log "[$2] a loop is at work in $scope (pid $pid): not started beside it"
      return 1
    fi
    left=$(( left + 1 ))
  done
  log "[$2] $scope holds only what an ended loop left ($left process(es)): stopping it before the loop starts"
  systemctl --user stop "$scope" 2>/dev/null
  return 0
}

# The client the run gives a loop (RUN_STREAMS_AGENTS, "a=codex,b=claude", then RUN_STREAMS_AGENT), or nothing.
client_of() {
  local pair
  for pair in ${RUN_STREAMS_AGENTS//,/ }; do
    [[ "${pair%%=*}" == "$1" ]] && { printf '%s' "${pair#*=}"; return; }
  done
  printf '%s' "${RUN_STREAMS_AGENT:-}"
}

# Run one loop until it is finished, as the header says: LABEL, the workspace it
# runs in, its name, and its brief there, which is what feature-loop.sh is given.
# With a watcher the loop takes command lines from a directory of its own (conductor.py command), which is how it
# is told to end after its cycle under way; a brief's loop is asked nothing through it. Exits 0 when its
# brief says done, 3 when it is blocked, 130 if interrupted.
supervise() {
  local label=$1 dir=$2 loop=$4 brief=$2/$4 code status failed=0 waited ids client
  local commands= reruns=0
  if [[ -n "${RUN_STREAMS_WATCHER:-}" ]]; then
    commands=$STATE/loops/$label
    mkdir -p "$commands"
  fi
  while :; do
    if stopping; then
      log "[$label] the run is stopping at a boundary: not run again; its brief says $(status_of "$brief")"
      phase "$label" "stopped at a boundary"
      exit 4
    fi
    # Waiting on jobs, from this run or one before it: they come back first.
    status=$(status_of "$brief")
    if [[ "$VERIFICATION" == separate && "$status" == "waiting on jobs"* ]]; then
      log "[$label] its brief says $status; verification is separate, so nothing waits: counted as finished, the jobs left for review"
      exit 0
    fi
    if [[ "$status" == "waiting on jobs"* ]]; then
      read -ra ids <<<"$(job_ids "$status")"
      if (( ${#ids[@]} )) && ! jobs_back "${ids[@]}"; then
        phase "$label" "waiting for jobs"
        log "[$label] waiting for ${ids[*]}, checking every ${POLL}s"
        waited=0
        until jobs_back "${ids[@]}"; do
          stopping && continue 2
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
    clear_scope "$(basename "$loop" .md)" "$label" "$dir"
    # Who carries this loop's turns, when the run says (brief_run.py start --agent, --stream-agent): feature-loop.sh
    # takes it over the brief's own `- client:` setting. Without a word from the run, the brief's stands.
    client=$(client_of "$label")
    [[ -n "$client" ]] && export FEATURE_LOOP_CLIENT=$client
    log "[$label] starting feature-loop.sh $loop in $dir"
    phase "$label" running
    LOOP_CONDUCTOR=$commands "$dir/llm-dlc/tools/feature-loop.sh" "$loop" </dev/null 2>&1 | python3 -u "$ROOT/llm-dlc/tools/streams_status.py" tag "$label" "$STATE"
    code=${PIPESTATUS[0]}
    collect_records "$dir" "$label"
    (( code == 130 )) && exit 130
    status=$(status_of "$brief")
    log "[$label] the loop ended with status $code; its brief says: ${status:-no status}"
    case "$status" in
      done*) exit 0 ;;
    esac
    stopping && continue
    case "$status" in
      blocked*)
        if [[ -n "${RUN_STREAMS_WATCHER:-}" ]] && (( reruns >= RERUNS )); then
          log "[$label] blocked again after $reruns rerun(s): left blocked, the watcher is not asked again"
          exit 3
        fi
        rerun_blocked "$label" "$status" "$4" || exit 3
        reruns=$(( reruns + 1 ))
        failed=0
        continue
        ;;
    esac
    if [[ "$VERIFICATION" == separate && "$status" == "waiting on jobs"* ]]; then
      log "[$label] verification is separate, so nothing waits: counted as finished, the jobs left for review"
      exit 0
    fi
    if [[ "$status" == "waiting on jobs"?* ]]; then
      read -ra ids <<<"$(job_ids "$status")"
      if ! jobs_back "${ids[@]}"; then
        failed=0
        continue
      fi
      log "[$label] it says it waits on jobs that are already back"  # counted as a stop with no reason
      code=1
    fi
    # A clean stop with a status that says neither done, blocked nor waiting
    # isn't finished: feature-loop.sh records the status at a stop, so a stop
    # without one is run again like a failure.
    (( code == 0 )) && log "[$label] it decided to stop, but its status doesn't say why (${status:-no status})"
    failed=$(( failed + 1 ))
    if (( failed >= 2 )); then
      log "[$label] stopped twice in a row without a status that says why: counted as blocked; its session needs a look"
      exit 3
    fi
    log "[$label] running it again once, to finish what it left"
  done
}

# Whether a stream's line is in this workspace's: its @- is an ancestor of ours.
merged_in() {
  [[ -n "$(jj log --ignore-working-copy --no-graph -r "${WS[$1]}@- & ::@-" -T change_id 2>/dev/null)" ]]
}

# With a watcher, a finished stream is put to it at once, to merge into this workspace's line (see the header):
# LABEL and its status. Without a watcher, or while the run stops, nothing is asked.
offer_merge() {
  local label=$1 status=$2 asked
  [[ -n "${RUN_STREAMS_WATCHER:-}" ]] || return 0
  stopping && return 0
  if merged_in "$label"; then phase "$label" "finished: $status; merged"; return 0; fi
  phase "$label" "finished: $status; put to the watcher to merge"
  log "[$label] asking the watcher to merge workspace ${WS[$label]} into this line, for ${MERGE_WAIT}s at most"
  asked=$(python3 "$ROOT/llm-dlc/tools/conductor.py" ask "$RUN_STREAMS_WATCHER" merge --answers merged,leave \
    --wait "$MERGE_WAIT" "loop=$label" "workspace=${WS[$label]}" "brief=${BRIEF%.md}-$label.md" "status=$status" 2>/dev/null)
  log "[$label] the watcher: ${asked:-none}"
  if merged_in "$label"; then
    phase "$label" "finished: $status; merged"
  else
    log "[$label] not merged: \`python3 llm-dlc/tools/brief_run.py merge $NAME $label\` merges it"
    phase "$label" "finished: $status; not merged"
  fi
}

# One stream, from its first cycle to its merge: its loop until it is finished (supervise), then the merge.
# Exits as supervise does.
stream() {
  local label=$1 code status
  ( supervise "$@" )
  code=$?
  (( code == 0 || code == 3 )) || exit "$code"
  status=$(status_of "$2/$4")
  log "[$label] finished: $status"
  phase "$label" "finished: $status"
  # asked to be run again already (brief_run.py rerun): its merge is put to the watcher after that run
  [[ -e "$STATE/rerun/$label" ]] || offer_merge "$label" "$status"
  exit "$code"
}

# The integration check (see the header), when the brief names a script for it.
if [[ -n "$INTEGRATION" ]]; then
  [[ -x "$INTEGRATION" ]] || { log "the brief's integration script $INTEGRATION isn't an executable file here"; exit 1; }
  if [[ -z "$INTEGRATION_DIR" ]]; then
    INTEGRATION_DIR=$(dirname "$ROOT")/$(basename "$ROOT")-$INTEGRATION_WS
    log "adding jj workspace $INTEGRATION_WS at $INTEGRATION_DIR, for the integration check"
    jj workspace add --name "$INTEGRATION_WS" -r @- "$INTEGRATION_DIR" >/dev/null || { log "could not add workspace $INTEGRATION_WS"; exit 1; }
    adopt_logs "$INTEGRATION_DIR"
  fi
  INTEGRATION_REPORT=$ROOT/llm-dlc/loop-summaries/$(basename "$BRIEF" .md)-integration.md
  INTEGRATION_SCOPE=feature-loop-$(basename "$BRIEF" .md)-integration
fi

# Every stream's @-, as short commit ids, in the order of STREAMS.
stream_heads() {
  local s
  for s in "${STREAMS[@]}"; do
    jj log --ignore-working-copy --no-graph -r "${WS[$s]}@-" -T 'commit_id.short(12) ++ " "' 2>/dev/null || printf '? '
  done
}

# One run of the rolling integration line (see the header): llm-dlc/tools/integration.py merges, settles the
# generated files, runs the script in its scope, commits a passing merge on the line, triages a failing one
# into the decision record and the streams' inboxes, and writes the report.
integrate_once() {
  local s args=()
  for s in "${STREAMS[@]}"; do args+=(--stream "$s=${WS[$s]}"); done
  log "[integration] merging $1"
  python3 "$ROOT/llm-dlc/tools/integration.py" run --name "$(basename "$BRIEF" .md)" --workspace "$INTEGRATION_DIR" \
    --report "$INTEGRATION_REPORT" "${args[@]}" \
    -- systemd-run --user --scope --quiet --collect --unit="$INTEGRATION_SCOPE" \
      -p MemoryMax=6G -p MemorySwapMax=0 -p OOMPolicy=continue -p CPUWeight=50 \
      timeout 3600 "$INTEGRATION_DIR/$INTEGRATION" </dev/null 2>&1 |
    while IFS= read -r line; do log "[integration] $line"; done
}

# Runs until killed: a check whenever a stream's @- has moved, at most every INTEGRATION_EVERY seconds.
integrate() {
  local last= heads
  mkdir -p "$(dirname "$INTEGRATION_REPORT")"
  while kill -0 "$MAIN" 2>/dev/null; do
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
declare -A PID ENDED
MAIN=$$  # the background loops below end when this script is gone
VERIFY=
INTEGRATE=
STATUS=
stop_all() {
  log "stopping every loop"
  for p in "${PID[@]}" $VERIFY; do kill -INT -- "-$p" 2>/dev/null; done
  [[ -n "$INTEGRATE" ]] && kill -TERM -- "-$INTEGRATE" 2>/dev/null
  [[ -n "$STATUS" ]] && kill -TERM -- "-$STATUS" 2>/dev/null
}
trap 'stop_all; wait; exit 130' INT TERM HUP

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
elif [[ -n "${RUN_STREAMS_WATCHER:-}" ]]; then
  log "the watcher keeps the queue: it starts the runner when jobs wait and collects each result; no verification loop is started"
else
  log "starting verification-loop.sh, for the jobs the loops submit"
  llm-dlc/tools/verification-loop.sh </dev/null > >(sed -u "s/^/[verify] /") 2>&1 &
  VERIFY=$!
fi

# The status line: each stream, or the brief's own loop, from the state above.
STATUS_LOOPS=()
for s in "${STREAMS[@]}"; do STATUS_LOOPS+=("$s=${DIR[$s]}=${BRIEF%.md}-$s.md"); done
(( ${#STREAMS[@]} )) || STATUS_LOOPS+=("brief=$ROOT=$BRIEF")
status_line() {
  python3 "$ROOT/llm-dlc/tools/streams_status.py" render --name "$NAME" --state "$STATE" --start "$START" \
    ${INTEGRATION:+--integration "$INTEGRATION_REPORT"} "${STATUS_LOOPS[@]}" 2>/dev/null
}
show_status() {
  local text
  text=$(status_line) || return 0
  [[ -n "$PANE" ]] && tmux set-option -p -t "$PANE" @run_streams "$text" >/dev/null 2>&1
  [[ -n "${1:-}" ]] && log "[status] $text"
  return 0
}
# Runs until killed: the bar every STATUS_EVERY seconds, the log every half hour (quarter hour without a bar).
status_bar() {
  local every=900 logged=0 now
  [[ -n "$PANE" ]] && every=1800
  while kill -0 "$MAIN" 2>/dev/null; do
    now=$(date +%s)
    if (( now - logged >= every )); then show_status log; logged=$now; else show_status; fi
    sleep "$STATUS_EVERY"
  done
}
# A request to run a stream again (see the header), taken once: LABEL.
rerun_asked() {
  [[ -e "$STATE/rerun/$1" ]] || return 1
  rm -f "$STATE/rerun/$1"
}
for s in "${STREAMS[@]}"; do
  brief=${BRIEF%.md}-$s.md
  status=$(status_of "${DIR[$s]}/$brief")
  if finished "$status" && rerun_asked "$s"; then
    log "[$s] its brief says $status, and the watcher asked for it to be run again"
  elif finished "$status"; then
    log "[$s] its brief says $status: not run again"
    phase "$s" "finished: $status"
    offer_merge "$s" "$status" &  # from an earlier run of this script, perhaps not merged yet
    PID[$s]=$!
    continue
  fi
  stream "$s" "${DIR[$s]}" "$NAME-$s" "$brief" &
  PID[$s]=$!
done
status_bar &
STATUS=$!
if [[ -n "$INTEGRATION" ]] && (( ${#PID[@]} )); then
  log "[integration] checking the streams together as they commit, into $INTEGRATION_REPORT"
  integrate &
  INTEGRATE=$!
fi

# Until every stream's process has ended: one that has ended is run again when the watcher asks (see the header).
while (( ${#PID[@]} )); do
  for s in "${!PID[@]}"; do
    kill -0 "${PID[$s]}" 2>/dev/null && continue
    wait "${PID[$s]}"
    code=$?
    (( code == 130 )) && { log "[$s] interrupted"; stop_all; wait; exit 130; }
    unset "PID[$s]"
    ENDED[$s]=1
  done
  for s in "${STREAMS[@]}"; do
    [[ -n "${ENDED[$s]:-}" ]] || continue
    stopping && break
    rerun_asked "$s" || continue
    log "[$s] run again inside the run, as the watcher asked"
    unset "ENDED[$s]"
    stream "$s" "${DIR[$s]}" "$NAME-$s" "${BRIEF%.md}-$s.md" &
    PID[$s]=$!
  done
  (( ${#PID[@]} )) && sleep "${RUN_STREAMS_RERUN_POLL:-2}"
done
PID=()
if [[ -n "$INTEGRATE" ]]; then
  kill -TERM -- "-$INTEGRATE" 2>/dev/null
  wait "$INTEGRATE" 2>/dev/null
  INTEGRATE=
  log "[integration] stopped: every stream is finished"
fi

for s in "${STREAMS[@]}"; do collect_records "${DIR[$s]}" "$s"; done
code=0
status=$(status_of "$ROOT/$BRIEF")
if (( ${#STREAMS[@]} )); then
  merged=() unmerged=()
  for s in "${STREAMS[@]}"; do if merged_in "$s"; then merged+=("$s"); else unmerged+=("$s"); fi; done
  log "every stream is finished: merged ${merged[*]:-none}; not merged ${unmerged[*]:-none}"
  for s in "${unmerged[@]}"; do log "[$s] not merged: \`python3 llm-dlc/tools/brief_run.py merge $NAME $s\` merges it"; done
elif stopping; then
  log "stopped at a boundary: the brief's own loop is not started"
elif finished "$status"; then
  log "[brief] its brief says $status: not run again"
  phase brief "finished: $status"
else
  log "the brief names no streams: its own loop is the run"
  supervise brief "$ROOT" "$NAME" "$BRIEF" &
  PID[brief]=$!
  wait "${PID[brief]}"
  code=$?
  PID=()
  (( code == 4 )) || phase brief "finished: $(status_of "$ROOT/$BRIEF")"
fi
if [[ -n "$VERIFY" ]]; then
  log "stopping the verification loop after its run under way"
  kill -USR1 "$VERIFY" 2>/dev/null
  wait "$VERIFY"
fi
if [[ -n "$STATUS" ]]; then
  kill -TERM -- "-$STATUS" 2>/dev/null
  wait "$STATUS" 2>/dev/null
  STATUS=
fi
show_status log
(( code == 130 )) && exit 130
if stopping; then
  log "stopped at a boundary, every loop after its cycle under way: running this again continues"
  exit 3
fi
status=$(status_of "$ROOT/$BRIEF")
log "finished: the brief $BRIEF says ${status:-no status}"
# Every loop's session, so the one to resume or read is on screen. The
# integration check is a script, with no session of its own.
if (( ${#STREAMS[@]} )); then
  log "sessions: planning ${PARENT:-none}"
  for s in "${STREAMS[@]}"; do log "sessions: $s ${SESSION[$s]}"; done
else
  log "sessions: the brief's own loop ${FEATURE_LOOP_SESSION:-$(setting "$ROOT/$BRIEF" session)}"
fi
log "what needs you: its Progress, verification/findings.md and the run records in llm-dlc/loop-summaries/"
[[ "$status" == done* ]] && exit 0
exit 1

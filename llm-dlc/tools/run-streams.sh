#!/usr/bin/env bash
# Run the parallel streams of a brief in one terminal, each a feature loop in a
# jj workspace of its own, on a branch of its own.
#
# Usage: llm-dlc/tools/run-streams.sh engines [STREAM...]
#   engines   the streams of llm-dlc/loops/engine-priorities.md: jbmc and native
#   STREAM    only these streams
#
# Run it from the default workspace. Each stream's brief forks its session from
# the conversation that planned the streams ("- fork:" in its Loop settings, the
# same in every stream), so every stream starts from it. Before any stream has a
# session, that planning session is compacted, once. (The brief's own loop, which
# merges the streams, starts a fresh session instead.) It adds a workspace per stream that doesn't have one, as
# ../REPO-STREAM from the latest commit (@-), and starts each stream's loop,
# feature-loop.sh NAME-STREAM, from that workspace's copy of the script.
#
# Every line the loops print comes here, prefixed with its stream. Ctrl-C stops
# them all, each recording the interruption. Running this again continues them:
# workspaces and sessions that exist are kept, nothing is compacted again, and
# each loop finishes what an interrupted cycle left. A stream that stops alone
# (no commit, or done) leaves the others running.
#
# Merging the streams is not this script's work: it is the first piece of work
# of the brief's own loop (feature-loop.sh NAME), once every stream is done.
#
# Exits 0 when every stream ended with 0, 1 otherwise, 2 for a bad argument and
# 130 if interrupted.

set -uo pipefail

usage() {
  echo "usage: run-streams.sh engines [STREAM...]" >&2
  exit 2
}

(( $# >= 1 )) || usage
NAME=$1
shift
case "$NAME" in
  engines) BRIEF=llm-dlc/loops/engine-priorities.md ALL=(jbmc native) ;;
  *) usage ;;
esac
STREAMS=("${@:-${ALL[@]}}")
for s in "${STREAMS[@]}"; do
  [[ " ${ALL[*]} " == *" $s "* ]] || { echo "run-streams.sh: $NAME has no stream $s (it has ${ALL[*]})" >&2; exit 2; }
done

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
if (( fresh == ${#ALL[@]} )); then
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

# Each stream runs in a process group of its own (job control), so a Ctrl-C here
# reaches only this script, which passes it on to each group whole: the loop, its
# claude and its output. Without job control, bash would start them ignoring
# SIGINT, and a loop could neither be stopped by it nor record it.
set -m
declare -A PID
stop_all() {
  log "stopping every stream"
  for s in "${!PID[@]}"; do kill -INT -- "-${PID[$s]}" 2>/dev/null; done
}
trap 'stop_all; wait; exit 130' INT TERM

for s in "${STREAMS[@]}"; do
  log "starting stream $s in ${DIR[$s]}"
  (
    "${DIR[$s]}/llm-dlc/tools/feature-loop.sh" "$NAME-$s" </dev/null 2>&1 | sed -u "s/^/[$s] /"
    exit "${PIPESTATUS[0]}"
  ) &
  PID[$s]=$!
done

status=0
for s in "${STREAMS[@]}"; do
  wait "${PID[$s]}"
  code=$?
  log "stream $s ended with status $code"
  (( code == 0 )) || status=1
done
(( status == 0 )) && log "every stream is done: \`llm-dlc/tools/feature-loop.sh $NAME\` merges them"
exit "$status"

#!/usr/bin/env bash
# Keep the verification queue empty, unattended.
#
# While jobs are queued that this machine can run, or results wait to be
# collected, it starts a fresh Claude Code session on Sonnet that runs the
# run-verification skill until the queue is clear: run, collect, triage,
# resubmit, commit. Each run gets a new session, since the work is mechanical
# and needs no memory of the last one. When nothing is left it polls the queue
# (verification/pipeline.py status, jobs committed at @-) and starts again
# when new jobs arrive.
#
# A run that leaves work behind, such as jobs it resubmitted, is followed by
# another, up to VERIFICATION_LOOP_RUNS in a row. A run that leaves exactly the
# work it found is not repeated, nor is the last of those: the loop waits for
# the queue to change. Jobs this machine can't run (too big for the runner) and
# jobs another runner holds don't start a run.
#
# Usage: [VERIFICATION_LOOP_POLL=60] [VERIFICATION_LOOP_RUNS=4] llm-dlc/tools/verification-loop.sh
#
# While it runs, type a command and Enter (see HELP below): stop ends it after
# the run under way, or at once while it waits; now checks the queue at once.
#
# Exits 0 when stopped, 2 for a bad argument, and 130 if interrupted.

set -uo pipefail

MODEL=claude-sonnet-5-5
EFFORT=medium
POLL=${VERIFICATION_LOOP_POLL:-60}
RUNS=${VERIFICATION_LOOP_RUNS:-4}

(( $# == 0 )) && [[ "$POLL" =~ ^[1-9][0-9]*$ && "$RUNS" =~ ^[1-9][0-9]*$ ]] || {
  echo "usage: [VERIFICATION_LOOP_POLL=SECONDS] [VERIFICATION_LOOP_RUNS=N] verification-loop.sh" >&2
  exit 2
}

INSTRUCTION="/run-verification This is an unattended run started by llm-dlc/tools/verification-loop.sh, in a fresh session: nobody can answer a question, so decide as the skill says and carry on. Work through every step until python3 verification/pipeline.py status shows nothing pending that can run here and nothing finished but not collected: run (in the background, waiting for it to finish), collect, triage, resubmit what needs it, and commit. Don't push. End with the report of step 6."

# Run in the root of the repo, where the sessions are filed and the skill is.
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1

# log and show_progress
source llm-dlc/tools/loop-common.sh

HELP='while it runs, type a command and Enter:
  stop   end after the run under way, or at once while waiting
  now    check the queue at once instead of at the next poll
  ?      show the queue'

# The terminal reader leaves a request (stop or now) in a file for the loop.
REQUEST=$(mktemp "${XDG_RUNTIME_DIR:-/tmp}/verification-loop.XXXXXX") || exit 1

pipeline() { python3 verification/pipeline.py "$@"; }

apply() {
  case "${1,,}" in
    stop | q | quit)
      echo stop >"$REQUEST"
      log "stop requested: the loop ends after the run under way, if any"
      ;;
    now) echo now >"$REQUEST" ;;
    "" | "?" | status) pipeline status ;;
    *) log "not a command: $1"; printf '%s\n' "$HELP" ;;
  esac
}

# Read the terminal in the background, so commands can be typed while claude
# works. claude gets /dev/null as its input, or it would compete for the lines.
# A background job's input is /dev/null unless redirected, hence fd 3.
reader=
if [[ -t 0 ]]; then
  exec 3<&0
  (
    while read -r line <&3; do
      apply "$line"
    done
  ) &
  reader=$!
  exec 3<&-
fi

cleanup() {
  [[ -n "$reader" ]] && kill "$reader" 2>/dev/null
  rm -f "$REQUEST"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

stop_requested() { [[ "$(cat "$REQUEST" 2>/dev/null)" == stop ]]; }

# What would start a run, one job id per line: pending jobs this machine can run,
# and results not collected yet. "running" goes to stderr: jobs another runner
# holds, which this loop waits for rather than starting a second runner.
work() {
  pipeline status --json | python3 -c '
import json, sys
s = json.load(sys.stdin)
for line in s["pending"]:
    if "; cannot run here:" not in line:
        print(line.split()[0])
for line in s["finished, not collected"]:
    print(line.split()[0])
if s["running"]:
    print("%d running" % len(s["running"]), file=sys.stderr)
'
}

run_claude() {
  claude -p "$1" --model "$MODEL" --effort "$EFFORT" \
    --permission-mode auto --output-format stream-json --verbose </dev/null | show_progress
}

# Wait up to POLL seconds, less if a command asks.
wait_poll() {
  local i
  for (( i = 0; i < POLL; i += 2 )); do
    [[ -s "$REQUEST" ]] && break
    sleep 2
  done
  [[ "$(cat "$REQUEST")" == now ]] && : >"$REQUEST"
}

if [[ -n "$reader" ]]; then
  printf '%s\n' "$HELP"
else
  log "no terminal: commands can't be typed, Ctrl-C or a signal stops it"
fi

run=0
streak=0       # runs in a row that left work behind
left=          # work not to start a run for, until the queue changes
idle=          # the state last reported while waiting, so as to say it once
while :; do
  stop_requested && { log "stopping, as requested"; exit 0; }

  if ! found=$(work 2>"$REQUEST.err"); then
    state="pipeline status failed: $(tail -1 "$REQUEST.err")"
  elif [[ -z "$found" ]]; then
    state="queue clear$( [[ -s "$REQUEST.err" ]] && echo ", $(cat "$REQUEST.err") elsewhere")"
  elif [[ "$found" == "$left" ]]; then
    state="$(wc -l <<<"$found") job(s) left as the last run left them, needing a person or a new job; waiting for the queue to change"
  else
    state=
  fi
  rm -f "$REQUEST.err"

  if [[ -n "$state" ]]; then
    if [[ "$state" != "$idle" ]]; then
      log "$state; checking every ${POLL}s (type now to check at once)"
      idle=$state
    fi
    wait_poll
    continue
  fi
  idle=

  run=$(( run + 1 ))
  log "run $run: $(wc -l <<<"$found") job(s) to run or collect, starting $MODEL in a new session"
  [[ -n "$reader" ]] && log "type stop to end after this run, ? for the queue"
  run_claude "$INSTRUCTION" || log "run $run: claude exited with status $?"

  after=$(work 2>/dev/null)
  if [[ -z "$after" ]]; then
    log "run $run: queue clear"
    streak=0
    left=
    continue
  fi
  streak=$(( streak + 1 ))
  log "run $run: left $(wc -l <<<"$after") job(s) to run or collect: $(tr '\n' ' ' <<<"$after")"
  if [[ "$after" == "$found" ]]; then
    log "run $run: no progress, not running again until the queue changes"
    left=$after
    streak=0
  elif (( streak >= RUNS )); then
    log "run $run: $streak runs in a row left work, not running again until the queue changes"
    left=$after
    streak=0
  fi
done

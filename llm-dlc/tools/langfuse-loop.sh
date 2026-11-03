#!/usr/bin/env bash
# Keep Langfuse up to date, unattended.
#
# While sessions have finished turns that were never sent to Langfuse (the Stop
# hook ran while it was down, or the session was recorded on another machine),
# it runs `sync.py langfuse --all`. When nothing is left it polls and starts
# again when new work appears, or when Langfuse comes back. No Claude session is
# involved: the sending is mechanical.
#
# Usage: [LANGFUSE_LOOP_POLL=30] llm-dlc/tools/langfuse-loop.sh
#
# While it runs, type a command and Enter: stop ends it, now checks at once,
# ? lists the sessions waiting. Exits 0 when stopped, 2 for a bad argument,
# and 130 if interrupted.

set -uo pipefail

POLL=${LANGFUSE_LOOP_POLL:-30}
(( $# == 0 )) && [[ "$POLL" =~ ^[1-9][0-9]*$ ]] || {
  echo "usage: [LANGFUSE_LOOP_POLL=SECONDS] langfuse-loop.sh" >&2
  exit 2
}

cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1
source llm-dlc/tools/loop-common.sh   # log

HELP='while it runs, type a command and Enter:
  stop   end the loop
  now    check at once instead of at the next poll
  ?      list the sessions with turns to send'

REQUEST=$(mktemp "${XDG_RUNTIME_DIR:-/tmp}/langfuse-loop.XXXXXX") || exit 1
sync() { python3 llm-dlc/tools/sync.py langfuse "$@"; }

apply() {
  case "${1,,}" in
    stop | q | quit) echo stop >"$REQUEST"; log "stop requested" ;;
    now) echo now >"$REQUEST" ;;
    "" | "?" | status) sync --pending ;;
    *) log "not a command: $1"; printf '%s\n' "$HELP" ;;
  esac
}

reader=
if [[ -t 0 ]]; then
  exec 3<&0
  ( while read -r line <&3; do apply "$line"; done ) &
  reader=$!
  exec 3<&-
  printf '%s\n' "$HELP"
else
  log "no terminal: commands can't be typed, Ctrl-C or a signal stops it"
fi

cleanup() { [[ -n "$reader" ]] && kill "$reader" 2>/dev/null; rm -f "$REQUEST"; }
trap cleanup EXIT
trap 'exit 130' INT TERM

wait_poll() {
  local i
  for (( i = 0; i < POLL; i += 2 )); do
    [[ -s "$REQUEST" ]] && break
    sleep 2
  done
  [[ "$(cat "$REQUEST")" == now ]] && : >"$REQUEST"
}

idle=   # the state last reported while waiting, so as to say it once
while :; do
  [[ "$(cat "$REQUEST" 2>/dev/null)" == stop ]] && { log "stopping, as requested"; exit 0; }

  if ! todo=$(sync --pending 2>&1); then
    state="could not list sessions: $(tail -1 <<<"$todo")"
  elif [[ -z "$todo" ]]; then
    state="nothing to send"
  else
    state=
  fi

  if [[ -n "$state" ]]; then
    [[ "$state" != "$idle" ]] && { log "$state; checking every ${POLL}s (type now to check at once)"; idle=$state; }
    wait_poll
    continue
  fi

  log "$(wc -l <<<"$todo") session(s) to send"
  if out=$(sync --all 2>&1); then
    idle=
    [[ -n "$out" ]] && log "$out"
  else
    state="send failed, Langfuse down? $(tail -1 <<<"$out")"
    [[ "$state" != "$idle" ]] && { log "$state; retrying every ${POLL}s"; idle=$state; }
    wait_poll
  fi
done

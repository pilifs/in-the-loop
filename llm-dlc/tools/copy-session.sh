#!/usr/bin/env bash
# Move a Claude Code session of this repo to another machine, so it can be
# resumed or forked there (run-streams.sh forks the session that planned them).
#
# Usage: llm-dlc/tools/copy-session.sh [options] HOST SESSION
#   HOST      an ssh destination, such as cvm
#   SESSION   the session id, or a prefix of it unique among this repo's sessions
#   --remote-repo PATH   the repo on HOST (default: the same path relative to home)
#   --no-push            don't publish before copying
#   --keep-local         leave the transcript here too (see below)
#   --force              copy although the session looks live here, or HOST
#                        already has a different transcript of it
#
# Run it after closing the session. In order, it:
#  1. refuses a session that is still live here: a process names it, or its
#     transcript changed in the last minute;
#  2. publishes, with `sync.py push --bookmark main`, so the session's last turns
#     and its logs are on the remote and the CDN before the other machine pulls
#     (running this is asking for that push; --no-push skips it);
#  3. copies the transcript, and the session's directory of tool results and
#     subagents if it has one, into HOST's project directory for the repo,
#     refusing to overwrite a different transcript there;
#  4. moves the transcript here out of Claude Code's project directory, into
#     ~/.claude/moved-sessions/, so the session goes on on one machine only. A
#     push from here republishes every session it finds, and would roll back a
#     transcript that has grown on HOST since. To bring it back, move the files
#     back to the path it prints.
#
# Then on HOST: pull (`jj git fetch && jj new main`) and resume or fork it there.

set -uo pipefail

usage() {
  echo "usage: copy-session.sh [--remote-repo PATH] [--no-push] [--keep-local] [--force] HOST SESSION" >&2
  exit 2
}

REMOTE_REPO= PUSH=1 KEEP=0 FORCE=0
args=()
while (( $# )); do
  case "$1" in
    --remote-repo) (( $# >= 2 )) || usage; REMOTE_REPO=$2; shift ;;
    --no-push) PUSH=0 ;;
    --keep-local) KEEP=1 ;;
    --force) FORCE=1 ;;
    -*) usage ;;
    *) args+=("$1") ;;
  esac
  shift
done
(( ${#args[@]} == 2 )) || usage
HOST=${args[0]} WANTED=${args[1]}

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd) || exit 1
source "$ROOT/llm-dlc/tools/loop-common.sh"
CONFIG=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
sanitize() { printf '%s' "$1" | sed 's/[^A-Za-z0-9]/-/g'; }
LOCAL_DIR=$CONFIG/projects/$(sanitize "$ROOT")

# The session, by id or unique prefix.
mapfile -t matches < <(find "$LOCAL_DIR" -maxdepth 1 -name "$WANTED*.jsonl" -printf '%f\n' 2>/dev/null | sed 's/\.jsonl$//')
if (( ${#matches[@]} != 1 )); then
  log "${#matches[@]} sessions of this repo match $WANTED in $LOCAL_DIR${matches:+: ${matches[*]}}"
  exit 1
fi
SID=${matches[0]}
TRANSCRIPT=$LOCAL_DIR/$SID.jsonl
SIDECAR=$LOCAL_DIR/$SID

# 1. Not live here.
if (( !FORCE )); then
  # A claude process whose arguments name it (--resume, --session-id): its program, or node running it.
  others=$(ps -eo pid=,args= | awk -v sid="$SID" 'index($0, sid) {
    n = split($2, a, "/"); m = split($3, b, "/")
    if (a[n] == "claude" || (a[n] == "node" && b[m] ~ /claude/)) print }')
  if [[ -n "$others" ]]; then
    log "a process here names session $SID: close it first (or --force)"
    printf '%s\n' "$others" | cut -c1-160 >&2
    exit 1
  fi
  age=$(( $(date +%s) - $(stat -c %Y "$TRANSCRIPT") ))
  if (( age < 60 )); then
    log "session $SID's transcript changed ${age}s ago: is it still open? Close it, wait a minute, or use --force"
    exit 1
  fi
fi

# Where it goes on HOST.
rel=${ROOT#"$HOME"/}
[[ "$rel" != "$ROOT" ]] || [[ -n "$REMOTE_REPO" ]] || { log "$ROOT is not under \$HOME: give --remote-repo"; exit 1; }
remote_q=$(printf '%q' "${REMOTE_REPO:-$rel}")
read -r REMOTE_ROOT REMOTE_CONFIG < <(ssh -o BatchMode=yes "$HOST" \
  "cd $remote_q 2>/dev/null && printf '%s %s\n' \"\$(pwd -P)\" \"\${CLAUDE_CONFIG_DIR:-\$HOME/.claude}\"") || true
if [[ -z "${REMOTE_ROOT:-}" ]]; then
  log "no repo at ${REMOTE_REPO:-~/$rel} on $HOST (or ssh to $HOST failed): give --remote-repo"
  exit 1
fi
REMOTE_DIR=$REMOTE_CONFIG/projects/$(sanitize "$REMOTE_ROOT")
log "session $SID: $TRANSCRIPT -> $HOST:$REMOTE_DIR/"

# Nothing different there already: HOST may have gone on with it.
local_sum=$(sha256sum "$TRANSCRIPT" | cut -d' ' -f1)
remote_sum=$(ssh -o BatchMode=yes "$HOST" "sha256sum $(printf '%q' "$REMOTE_DIR/$SID.jsonl") 2>/dev/null" | cut -d' ' -f1)
if [[ -n "$remote_sum" && "$remote_sum" != "$local_sum" ]] && (( !FORCE )); then
  log "$HOST already has a different transcript of $SID: it may have gone on there. Not overwriting it (--force does)"
  exit 1
fi

# 2. Publish first, so HOST pulls the session's last turns and its logs.
if (( PUSH )); then
  log "publishing: sync.py push --bookmark main"
  (cd "$ROOT" && python3 llm-dlc/tools/sync.py push --bookmark main) || { log "the push failed: nothing copied"; exit 1; }
fi

# 3. Copy: under a temporary name, then renamed, so HOST never sees half a transcript.
if [[ "$remote_sum" != "$local_sum" ]]; then
  ssh -o BatchMode=yes "$HOST" "mkdir -p $(printf '%q' "$REMOTE_DIR")" || exit 1
  scp -q -p "$TRANSCRIPT" "$HOST:$REMOTE_DIR/.$SID.jsonl.part" || { log "copying the transcript failed"; exit 1; }
  ssh -o BatchMode=yes "$HOST" "mv $(printf '%q' "$REMOTE_DIR/.$SID.jsonl.part") $(printf '%q' "$REMOTE_DIR/$SID.jsonl")" || exit 1
fi
if [[ -d "$SIDECAR" ]]; then
  scp -q -p -r "$SIDECAR" "$HOST:$REMOTE_DIR/" || { log "copying $SIDECAR failed"; exit 1; }
fi
copied=$(ssh -o BatchMode=yes "$HOST" "sha256sum $(printf '%q' "$REMOTE_DIR/$SID.jsonl")" | cut -d' ' -f1)
[[ "$copied" == "$local_sum" ]] || { log "the copy on $HOST doesn't match: left the transcript here as it was"; exit 1; }
log "copied, sha256 $local_sum"

# 4. Retire it here.
if (( KEEP )); then
  log "kept here too (--keep-local): don't resume it on both machines, and don't push from here once it goes on there"
else
  MOVED=$CONFIG/moved-sessions/$(sanitize "$ROOT")
  mkdir -p "$MOVED" || exit 1
  mv -- "$TRANSCRIPT" "$MOVED/" || exit 1
  [[ -d "$SIDECAR" ]] && { mv -- "$SIDECAR" "$MOVED/" || exit 1; }
  printf 'Moved to %s:%s on %s.\n' "$HOST" "$REMOTE_DIR" "$(date '+%F %T')" >"$MOVED/$SID.moved"
  log "moved out of $LOCAL_DIR into $MOVED: it goes on on $HOST only"
  log "to bring it back: mv $MOVED/$SID.jsonl $LOCAL_DIR/"
fi
log "next, on $HOST: cd $REMOTE_ROOT && jj git fetch && jj new main"

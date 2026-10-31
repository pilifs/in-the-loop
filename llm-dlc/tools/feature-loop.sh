#!/usr/bin/env bash
# Grow the jvmcontract library unattended, one feature at a time.
#
# Each cycle resumes one Claude Code session and runs: instruction, commit, compact.
# A cycle that leaves no new commit stops the loop, before compacting, so the
# session keeps its full context for the person who has to look at why.
#
# Usage: llm-dlc/tools/feature-loop.sh
# Exits 1 when a cycle made no commit, and 130 if interrupted.

set -uo pipefail

SESSION_ID=360e8b8b-8e0c-4b2a-bd69-25b32f2a54eb
MODEL=claude-fable-5-1
EFFORT=high
INSTRUCTION="Add more advanced features along with examples to the jvmcontract library."

# Claude Code files a session under the directory it ran in, and the instruction
# is meant for the root of the repo, so run there whatever the caller's directory.
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1

trap 'exit 130' INT TERM

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*"; }

# `auto` is the mode this session has always run in. With -p nobody can answer a
# prompt, so anything auto mode would ask about is denied rather than left hanging.
run_claude() {
  claude -p "$1" --resume "$SESSION_ID" --model "$MODEL" --effort "$EFFORT" \
    --permission-mode auto
}

# `sync.py commit` finishes @ and starts an empty change, so a commit moves @-.
# Change IDs, unlike commit IDs, survive a rewrite of the commit.
last_change() { jj log --no-graph -r @- -T change_id; }

cycle=0
while :; do
  cycle=$((cycle + 1))
  before=$(last_change) || exit 1

  log "cycle $cycle: instruction"
  run_claude "$INSTRUCTION" || log "cycle $cycle: claude exited with status $?"

  after=$(last_change) || exit 1
  if [[ "$after" == "$before" ]]; then
    log "cycle $cycle: no commit, stopping; session $SESSION_ID needs attention"
    exit 1
  fi
  log "cycle $cycle: committed $(jj log --no-graph -r @- -T 'description.first_line()')"

  log "cycle $cycle: compact"
  run_claude "/compact" || log "cycle $cycle: compact exited with status $?"
done

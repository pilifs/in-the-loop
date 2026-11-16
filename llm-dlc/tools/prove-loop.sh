#!/usr/bin/env bash
# Prove examples in a moonshot loop of their own: step 3 of /prove-java-change
# (llm-dlc/runtime.md#the-proof-loop), in a development or a runtime checkout.
#
# Usage: llm-dlc/tools/prove-loop.sh [--fork SESSION] [--cycles N] [--memory SIZE]
#                                    [--no-verification] [--no-isolation] EXAMPLE [EXAMPLE ...]
#
# It gives each example, one per cycle, to feature-loop.sh's `prove-change`
# moonshot: "Formally prove example {} as elegantly and efficiently as
# possible", on Fable 5.2 at high effort, the instruction and nothing else.
#
#   --fork SESSION   the loop's session starts as a fork of that one: the session
#                    that prepared the example hands on what it learned. The fork is
#                    made in one turn without tools, then compacted, and the cycles
#                    follow in it; the parent goes on untouched, and may be mid-turn.
#                    Without it the loop starts a fresh session.
#   --cycles N       at most N cycles (by default one per example)
#   --memory SIZE    the loop's memory cap (FEATURE_LOOP_MEMORY_MAX; doctor.py's
#                    budget proposes one for this machine)
#   --no-verification  don't start verification-loop.sh for the jobs the loop queues.
#                    By default one is started unless one already runs on this
#                    machine, and stopped when the loop has ended and the queue is
#                    clear, or after PROVE_LOOP_DRAIN seconds (default 3600).
#
#   --no-isolation   start the loop's sessions as a plain `claude`. By default, in a
#                    runtime checkout, they start clean: this checkout only, with
#                    none of the user's own Claude Code setup (claude_setup.py). For a
#                    machine where a clean launch does not work, which the skill's
#                    check reports; not recommended otherwise.
#
# The run's state is in llm-dlc/loop-summaries/prove-change/ (gitignored):
#   lock            held while a run is under way: one at a time in a checkout
#   run.json        the session, the examples, the record, how it ended
#   events.jsonl    what the loop asks its conductor (conductor.py), and its end
#   verification.log  the verification loop's output, when this script started it
# feature-loop.sh keeps the run's record beside it, as for every loop.
#
# Exits with feature-loop.sh's status: 0 when the cycles ran out, 1 when a cycle
# made no commit or the session needs attention, 2 for a bad argument.

set -uo pipefail

MODEL=claude-fable-5-2
EFFORT=high
FORK=
CYCLES=
VERIFY=1
EXAMPLES=()

usage() {
  echo "usage: prove-loop.sh [--fork SESSION] [--cycles N] [--memory SIZE] [--no-verification] [--no-isolation] EXAMPLE [EXAMPLE ...]" >&2
  exit 2
}

while (( $# )); do
  case "$1" in
    --fork) [[ $# -ge 2 ]] || usage; FORK=$2; shift 2 ;;
    --cycles) [[ $# -ge 2 && "$2" =~ ^[1-9][0-9]*$ ]] || usage; CYCLES=$2; shift 2 ;;
    --memory) [[ $# -ge 2 ]] || usage; export FEATURE_LOOP_MEMORY_MAX=$2; shift 2 ;;
    --no-verification) VERIFY=; shift ;;
    --no-isolation) export LOOP_ISOLATION=0; shift ;;
    -*) usage ;;
    *) EXAMPLES+=("$1"); shift ;;
  esac
done
(( ${#EXAMPLES[@]} )) || usage
UUID='^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
[[ -z "$FORK" || "$FORK" =~ $UUID ]] || { echo "prove-loop.sh: not a session id: $FORK" >&2; exit 2; }

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd) || exit 1
cd "$ROOT" || exit 1
source llm-dlc/tools/loop-common.sh
isolation || exit 1
# The fork's one turn must not run a development checkout's hooks, which would trace the copied transcript as a
# session of this repository: there it reads the user's settings only. A clean launch reads none of the user's.
FORK_SOURCES=(--setting-sources user)
(( ${#ISOLATION[@]} )) && FORK_SOURCES=("${ISOLATION[@]}")

for example in "${EXAMPLES[@]}"; do
  [[ "$example" =~ ^[0-9]{3}$ ]] && compgen -G "examples/$example-*/example.json" >/dev/null || {
    echo "prove-loop.sh: no example $example (examples/$example-*/example.json)" >&2
    exit 2
  }
done

RUN=llm-dlc/loop-summaries/prove-change
mkdir -p "$RUN" || exit 1
# One run at a time in a checkout: this directory is the run's, and its lock is held until the script ends.
exec 8>"$RUN/lock"
if ! flock -n 8; then
  log "a prove-change loop is already running in this checkout ($RUN/lock is held)"
  exit 1
fi
rm -f "$RUN"/events.jsonl "$RUN"/verdict-*.json "$RUN"/ended.seen "$RUN"/run.json

PROJECTS=${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects
project_dir() { printf '%s/%s' "$PROJECTS" "$(printf '%s' "$1" | sed 's/[^A-Za-z0-9]/-/g')"; }

SESSION=$(python3 -c 'import uuid; print(uuid.uuid4())') || exit 1
export FEATURE_LOOP_SESSION=$SESSION

# The fork: Claude Code resumes a session it finds under the directory it runs in,
# and the parent may have run anywhere (the user's own project), so its transcript
# is copied here for the one turn and removed straight after. That turn runs
# without the repository's hooks or any tool, so in a development checkout the
# copy is never traced as a session of this one. The parent's own file is only read.
if [[ -n "$FORK" ]]; then
  here=$(project_dir "$ROOT")
  source_file=$(ls -t "$PROJECTS"/*/"$FORK.jsonl" 2>/dev/null | head -n 1)
  if [[ -z "$source_file" ]]; then
    log "no transcript of session $FORK under $PROJECTS"
    exit 1
  fi
  mkdir -p "$here" || exit 1
  copied=
  if [[ "$(realpath "$source_file")" != "$(realpath -m "$here/$FORK.jsonl")" ]]; then
    cp -- "$source_file" "$here/$FORK.jsonl" || exit 1
    copied=1
  fi
  log "starting session $SESSION as a fork of $FORK"
  claude -p "This conversation goes on, from here, as the proof loop it prepared: you are now the session that proves example(s) ${EXAMPLES[*]} in the checkout at \`$ROOT\`, and no longer the one orchestrating. The conversation you were forked from carries on separately and watches this loop from outside; it will not talk to you, and you don't report to it. From now on work only in that checkout and follow its CLAUDE.md. Tools are off for this one turn: reply in a few sentences with what you know about the change and the example that the proof will need. The loop's instruction follows." \
    --resume "$FORK" --fork-session --session-id "$SESSION" --model "$MODEL" --effort "$EFFORT" \
    "${FORK_SOURCES[@]}" --tools "" --output-format stream-json --verbose </dev/null | show_progress
  [[ -n "$copied" ]] && rm -f -- "${here:?}/${FORK:?}.jsonl"
  if [[ ! -f "$here/$SESSION.jsonl" ]]; then
    log "the fork of session $FORK made no session $SESSION"
    exit 1
  fi
  log "compacting the fork"
  claude -p "/compact Keep what proving example(s) ${EXAMPLES[*]} needs: the change, its revisions and sources, the claims and their bounds, what was prepared and where, the machine's budget, and anything learned about the code. Drop the setup and installation steps." \
    --resume "$SESSION" --model "$MODEL" --effort "$EFFORT" "${ISOLATION[@]}" \
    --permission-mode auto --output-format stream-json --verbose </dev/null | show_progress
  (( PIPESTATUS[0] == 0 )) || { log "the compact failed; nothing started"; exit 1; }
fi

python3 - "$RUN/run.json" "$SESSION" "$FORK" "${EXAMPLES[@]}" <<'EOF' || exit 1
import json, sys, time
path, session, fork, *examples = sys.argv[1:]
json.dump({"session": session, "forkedFrom": fork or None, "examples": examples,
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ended": None}, open(path, "w"), indent=1)
EOF

# The jobs the loop queues are run by the verification loop, as in every run of
# a loop here. One per repository is enough: its runner reads the jobs of every
# workspace. A loop that runs for another repository on this machine (a runtime
# checkout beside a development one) doesn't see this one's.
store() {  # the jj repository a directory's workspace belongs to
  local repo=$1/.jj/repo
  if [[ -d "$repo" ]]; then realpath "$repo"; elif [[ -f "$repo" ]]; then (cd "$1/.jj" && realpath -m "$(cat repo)"); fi
}
verification_running() {
  local pid mine theirs
  mine=$(store "$ROOT")
  for pid in $(pgrep -u "$(id -u)" -f 'llm-dlc/tools/verification-loop\.sh'); do
    theirs=$(store "$(readlink -f "/proc/$pid/cwd" 2>/dev/null)")
    [[ -n "$theirs" && "$theirs" == "$mine" ]] && return 0
  done
  return 1
}
verifier=
if [[ -n "$VERIFY" ]]; then
  if verification_running; then
    log "a verification loop is already running for this repository: leaving the queue to it"
  else
    log "starting the verification loop (its output: $RUN/verification.log)"
    llm-dlc/tools/verification-loop.sh >"$RUN/verification.log" 2>&1 </dev/null &
    verifier=$!
  fi
fi

# After the loop: give the queue time to clear, then stop the verification loop this script started.
drain() {
  [[ -n "$verifier" ]] || return 0
  local until=$(( SECONDS + ${PROVE_LOOP_DRAIN:-3600} )) left
  while (( SECONDS < until )) && kill -0 "$verifier" 2>/dev/null; do
    left=$(python3 verification/pipeline.py status --json 2>/dev/null | python3 -c '
import json, sys
s = json.load(sys.stdin)
print(len([l for l in s["pending"] if "; cannot run here:" not in l]) + len(s["running"]) + len(s["finished, not collected"]))' 2>/dev/null)
    [[ "$left" == 0 ]] && break
    sleep 30
  done
  kill -USR1 "$verifier" 2>/dev/null
  wait "$verifier" 2>/dev/null
}

export LOOP_CONDUCTOR=$RUN
FEATURE_LOOP_ITEMS="${EXAMPLES[*]}" llm-dlc/tools/feature-loop.sh prove-change ${CYCLES:+"$CYCLES"}
status=$?

record=$(ls -t llm-dlc/loop-summaries/*-prove-change.md 2>/dev/null | head -n 1)
python3 - "$RUN" "$status" "$record" <<'EOF'
import json, sys, time
sys.path.insert(0, "llm-dlc/tools")
import conductor
from pathlib import Path
run, status, record = Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
state = json.loads((run / "run.json").read_text())
state.update(ended=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), status=status, record=record or None)
(run / "run.json").write_text(json.dumps(state, indent=1) + "\n")
conductor.append_event(run, type="ended", status=status, record=record or None, session=state["session"],
                       note="0: the cycles ran out; 1: a cycle made no commit, or the session needs attention")
EOF
drain
log "record of the run: ${record:-none}"
exit "$status"

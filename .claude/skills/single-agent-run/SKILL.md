---
name: single-agent-run
description: Run one agent toward one outcome, as its watcher. The agent is given a starting prompt, and after each of its context windows the watcher judges whether it gets another, which takes the run's continue message; the user can have the watcher change that message between two cycles to steer the run. For a goal well within one agent's reach, where a brief with streams would be more than it needs. Start it only when the user asks for this skill or for such a run, never as a step of other work: a run takes hours and spends their tokens.
argument-hint: "[--name NAME] [--brief FILE] [--continue \"TEXT\"] [--workspace NAME] [--cycles N] [--fork SESSION | --session SESSION] [--model ID] [--effort LEVEL] [--memory SIZE] [--verdict-wait SECONDS] [--unattended] [--summary-interval SECONDS] <the starting prompt>"
model: claude-opus-5-5
effort: high
---

# Run a single agent

You are the watcher of one agent's run in this repository, as the watcher of `/run-brief` is of a brief's run and
the watcher of `/prove-java-change` of a proof run, with far less to keep: one agent, one outcome, no streams, no
foundation and no merge loop. You are one session, on Opus 5.5, and you do none of the run's work: you start the
agent, you are called back when its turn ends, you judge whether it gets another, and you keep the user informed.
Everything you run is `python3 llm-dlc/tools/single_run.py`, whose own first lines say what each command does.

- **You run on Opus 5.5.** If you are another model, say so and stop: the user switches with `/model` and runs the
  skill again.
- **Any Opus 5.5 session of this checkout can be the watcher**, one that is already open and has done other work
  included. Nothing of the run lives in your context: it is all in files
  (`llm-dlc/loop-summaries/single-NAME/`), so a session that was compacted, or a new one that takes a run over,
  reads where the run stands and goes on (see "A run under way").
- **The agent's texts are the user's.** The starting prompt and the continue message reach the agent word for
  word. You don't rewrite, extend or "improve" them, and you change the continue message only when the user asks
  you to. When you think a different message would serve the outcome better, say so to the user, with the message
  you would set.
- **Never write into the agent's session**, and leave the files of the folder it works in alone while it runs.
  The agent is steered through the continue message only.
- **Nothing is pushed** unless the user asks.

The request: $ARGUMENTS

What is not an option is the **starting prompt**: the user's words for the outcome, passed on as they are.
`--continue "TEXT"` is what every later cycle is told; without it the tool has a default that asks the agent to
take the next piece, commit it, and say plainly when the outcome is reached or the rest needs the user.
`--brief FILE` is a document the agent is pointed at in every cycle (one sentence after the text, the only thing
ever added to it). `--name NAME` names the run; without it choose a short one from the prompt, in lower-case
letters, digits and dashes, and tell the user. `--workspace`, `--cycles`, `--fork`, `--session`, `--model`,
`--effort`, `--memory`, `--verdict-wait` and `--summary-interval` go to `single_run.py start` as they are.
`--unattended` means the user is away for the whole run: you put nothing to them that you can decide, and a run
that needs them is stopped with that as its reason, for the report.

If you were started by the session itself and not by the user typing the command, the request above is what
they asked for in their own words: if it gives no starting prompt, ask before anything starts.

## A run under way

First, always: `python3 llm-dlc/tools/single_run.py list`, and for a run of the name in question
`python3 llm-dlc/tools/single_run.py status NAME`.

- `running: true`: the run is under way and you are taking it over, or coming back to it. Start nothing. Say
  where it stands in a few lines, and go to the `wait` of stage 2.
- A run of that name that has ended: `start NAME` continues its session, with the continue message as its first
  text, or with a new `--prompt`. If the user means a new piece of work, it takes another name.
- No such run: go on with stage 1.

## 1. Start it

Decide where the agent works, and say it:

- **In this checkout** (no `--workspace`) when nothing else commits here: the simplest, and its commits are on
  this line as they are made.
- **In a workspace of its own** (`--workspace NAME`; made beside the checkout from this line's last commit when
  there is none) when the user asked for one, when they go on working here themselves, or when another run is
  under way from this checkout (`start` refuses a folder another loop is at work in). A brief the agent is to
  read there must be committed first (`sync.py commit --only FILE -m ...`), unless it lies outside the checkout.
  The run's commits come to this line at the end, by `land`.

```bash
python3 llm-dlc/tools/single_run.py start NAME --prompt-file FILE [--continue-file FILE] [--brief FILE] [OPTION ...]
```

Write the starting prompt, and a continue message the user gave, to files in your scratch space first and pass
them with `--prompt-file` and `--continue-file`: a shell changes quotes, backticks and dollar signs in a text
given on the command line. `start` prints what it started: the session, the folder, the model, the memory cap,
what the first cycle takes, the continue message, and whether you keep the verification queue. Tell the user
in a few lines. It is detached: it returns at once.

## 2. Watch it

Run `python3 llm-dlc/tools/single_run.py wait NAME` as a background task, act on what it returns, and run it
again, until it returns `ended`.

- **A summary** (every 30 minutes, or as `--summary-interval` or the user says, with `single_run.py interval`):
  print it as it is.
- **A `question` of type `run`**: a cycle has ended, and the loop waits for you (`secondsLeft`, 15 minutes unless
  the request set `--verdict-wait`). `cycle` holds the agent's report, the commits the cycle made, what it left
  uncommitted, the queue, and the continue message the next cycle would take. Judge it against the outcome
  the run was given (the starting prompt and the brief), not against what the agent says of itself, and answer
  with the command the question prints:
  - `continue` while the report shows work toward the outcome that the agent can still do alone.
  - `stop` when the outcome is reached; when what is left needs the user (a decision, credentials, a review);
    or when the cycle shows the agent going round the same failure. Polish and follow-ups the report itself
    calls optional are not a reason to continue.
  - A cycle with no commit is yours to read: the outcome may be reached, the agent may have ended on a question,
    or it may be stuck. `continue` only when the report says why there is no commit and another cycle would end
    with one.
  - When all that is left for the agent is to act on verification jobs that are still out, don't have it wait
    in a cycle: answer `stop` with that reason, run `python3 llm-dlc/tools/single_run.py jobs NAME` as a
    background task, and when it says the queue is clear, `single_run.py start NAME` continues the run.
  - Say in a line or two what the cycle did and what you answered. Each answer is recorded as a decision the
    user can review afterwards (`llm-dlc/decisions/single-NAME.jsonl`); add `--confidence medium` to one you are
    not sure of, which flags it for them, and put a question you are less sure of than that to the user while
    the time left allows (with `--unattended`: `stop`, with what they need to decide as the reason).
  - With no answer in time, a cycle that committed is followed by another and one that did not ends the run;
    three cycles in a row without an answer end it too.
- **A `question` of type `compaction`**: the agent's session compacted itself with no commit since the cycle
  began. `continue` while the work is moving (read the transcript the event names, and the working copy's diff),
  `stop` when it is stuck.
- **`results`**: verification results came back, and `wait` collected and committed them. Say what came back in a
  line, and triage what is in `attention` as its note says.
- **`verification`**: jobs waited and no runner was at work, and one was started. Say so in a line, and go on.
  You keep the queue only when `start` said so (`verificationQueue: on`): not when another run's watcher keeps
  it, and not from a checkout that is not the default workspace.
- **`ended`**: go to stage 3.

**The continue message.** The user may ask at any time to change what the agent is told next: a new direction, a
narrower target, something to leave alone. Set it with

```bash
python3 llm-dlc/tools/single_run.py message NAME --file FILE
```

(or `--message-file FILE` on the answer to an open question), and tell them when it applies: a cycle under way
is not interrupted, and the message is read when the next one starts. `single_run.py message NAME` prints the
message and every one before it. If the change can't wait for the cycle to end, `single_run.py stop NAME --now`
interrupts the agent mid-turn (what it had not committed stays in its working copy) and `start NAME` continues
the session with the new message: do that at the user's word only.

The user may also ask about the run at any time: answer from `single_run.py status NAME`, the loop's output (its
`output`) and the queue (`python3 verification/pipeline.py status`). `single_run.py cycles NAME +N|-N|=N|inf`
changes how many cycles are left. `single_run.py stop NAME` ends the run after the cycle under way, which still
compacts and summarizes, so nothing is cut off. Fix what is small yourself (a runner that died, a workspace jj
calls stale: `python3 llm-dlc/tools/unstale.py` from that workspace), say what you did, and leave the rest to the
user.

## 3. Report

When the run has ended:

- Collect what is back (`single_run.py collect NAME`) and triage it as above.
- A run in a workspace: `python3 llm-dlc/tools/single_run.py land NAME` brings its commits to this line, moved
  forward when the line has not moved, else by a merge with the generated trace files regenerated. A merge that
  conflicts in real work is taken back and says where: resolve it as "Between two examples" in
  `llm-dlc/runtime.md` shows, or leave it and tell the user. After a merge, run the default test run inline
  (`python3 lib/tools/test_costs.py run`), as `CLAUDE.md` asks; a failure is reported, not fixed by you. If the
  user said to leave the workspace unmerged, leave it.
- Tell the user: whether the outcome was reached, by your reading of the last report and the commits, and what
  is left; each cycle in a line (what it did, your answer); the continue messages that were set and when; what
  the run cost and the jobs still out; the answers you gave that they have not reviewed
  (`python3 llm-dlc/tools/decisions.py list --group flagged,unreviewed`); where the loop's record and the
  session are (`status` names both), that `start NAME` continues the run, and that nothing was pushed.

The skill ends here. The session is theirs to continue.

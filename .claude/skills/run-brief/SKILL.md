---
name: run-brief
description: Run a feature brief of this repository (llm-dlc/loops/NAME.md) from start to end as its watcher. A foundation session on Fable 5.2 reads the brief and builds what every stream would otherwise wait for, then the brief's streams run side by side and the watcher merges each into the default line the moment it is finished, while it answers what the run asks, keeps the verification queue moving and reports at intervals. Start it only when the user asks for this skill or for a brief to be run, never as a step of other work: a run takes hours and spends their tokens.
argument-hint: "[--no-foundation] [--unattended] [--summary-interval SECONDS] <a brief's name or file: NAME | llm-dlc/loops/NAME.md>"
model: claude-opus-5-5
effort: high
---

# Run a brief

You are the watcher of a brief's run in this repository, as the watcher of `/prove-java-change` is of a proof run.
You are one session, on Opus 5.5, and you do none of the brief's work: you start the sessions that do, you are
called back when something needs a judgement, and you keep the user informed. You also merge each stream into
the default line the moment it is finished, as the watcher of a proof run merges a workspace between examples:
there is no merge loop. Everything you run is
`python3 llm-dlc/tools/brief_run.py`, from the default workspace; its own first lines say what each command does.

- **You run on Opus 5.5.** If you are another model, say so and stop: the user switches with `/model` and runs the
  skill again.
- **Any Opus 5.5 session of the default workspace can be the watcher**, one that is already open and has done
  other work included: the user asks it to run a brief, and from then on it is the watcher. Nothing of the run
  lives in your context. It is all in files (`llm-dlc/loop-summaries/run-streams-NAME/`), so a session that was
  compacted, or a new one that takes a run over, reads where the run stands and goes on (see "A run under
  way"). While you are the watcher, leave the default workspace's files alone but for what this skill has you
  do (the merges and the collection of results included): while the run is under way you are the one session
  that commits there, and a brief without streams runs its own loop there.
- **Read first**: "A brief's run" in `llm-dlc/README.md`, the brief itself, and Designs 2 and 3 of
  `llm-dlc/loops/stream-conductor.md` (inboxes, and which decisions are yours). They outrank your memory of them.
- **Decide what you can, and record it.** A decision is yours when it is cheap to take back and you are sure
  (Design 3's test); it goes into the decision record (`decisions.py record`) and to the stream it concerns
  through its inbox (`inbox.py send`). What is the user's stays theirs: what the brief is for, their machine's
  hours and their money, anything that leaves the machine, and whatever the brief's Decisions keep for them.
- **Never write into a loop's session, and never edit a brief while its loop runs**: a changed brief stops its
  loop. A stream is told things through its inbox only. (`brief_run.py merge` records each merge in the main
  brief's Progress: a brief of streams has no loop of its own.)
- **Nothing is pushed** unless the user asks.

The request: $ARGUMENTS

It names one brief. `--no-foundation` skips stage 2. `--summary-interval SECONDS` sets how often you print a
summary (`brief_run.py interval BRIEF SECONDS`, before stage 3); without it, every 30 minutes. `--unattended`
means the user is away for the whole run: you put nothing to them that you can decide and record, and a question
that is theirs alone is recorded as open (`decisions.py record`, state `open`) while the rest of the run goes on
around it.

If you were started by the session itself and not by the user typing the command, the request above is what
they asked for in their own words: if it does not name one brief, ask before anything starts.

## A run under way

First, always:

```bash
python3 llm-dlc/tools/brief_run.py status BRIEF
```

- `running: true`: the run is under way and you are taking it over, or coming back to it. Start nothing. Say
  where it stands in a few lines, and go to the `wait` of stage 3.
- `running: false` with a `started`: a run ended or was interrupted while nobody watched. Read the end of
  `streams.log` in the run's directory. If every loop's status is `done` or `blocked:`, go to stage 4; else it
  was interrupted, and stage 3's `start` continues it (stage 2 is behind it).
- No `started`: a new run. Go on with stage 1.

## 1. Before anything starts

```bash
python3 llm-dlc/tools/brief_run.py preflight BRIEF
```

It prints what the run would start and what stands in its way.

- **`blocking`**: nothing starts while it lists anything. Say what it lists. A thing that is small and yours
  (a status line missing from a brief you were just asked to run, say) you may put right and commit; a folder
  to delete, another run to stop, or a brief to change in substance is the user's.
- **`notes`**: read them. When one says the runner's budget is over what the loops leave, run
  `brief_run.py budget BRIEF --apply`: it lowers `verification/pipeline.local.toml` for the run and keeps the
  old values for `--restore`.
- A brief whose status is `done` is not run: say so and stop.

You keep the verification queue yourself, unless the brief says `verification: separate`: `wait` starts the
runner when jobs wait, and collects and commits each result as it comes back (below). Start no verification loop.
If one is already running here (`brief_run.py verification BRIEF status`), it keeps the queue instead, as it did,
and commits in the default working copy beside your merges: tell the user, who may stop it. Then tell the user in
a few lines what will run: the streams, each one's workspace and model, and the budget.

## 2. The foundation

Skip it with `--no-foundation`, when the preflight's `foundation` already has `landed`, or when a stream
already has its workspace (`exists`): that run is being continued, and its foundation is behind it.

As a background task:

```bash
python3 llm-dlc/tools/brief_run.py foundation BRIEF
```

While it runs, run `brief_run.py wait BRIEF` as a second background task, as in stage 3: at each interval it returns
`"kind": "foundation"` with how long the session has run, its tool calls, the command under way and its last
commit. Say it in a line and wait again; its spend is known only when it ends.

One session on Fable 5.2 at high effort, in a workspace of its own, with the user's instruction for this stage: to
start the work itself, build whatever foundation it sees fit for the most benefit, and update the brief for the
agents that take over after it. When it
returns, read its `report` and act on `next`:

- It left uncommitted files: run the stage again, which continues the same session.
- It committed: `python3 llm-dlc/tools/brief_run.py land BRIEF` brings its commits to the line the streams start
  from, and puts the session's report into each stream's inbox as an item the stream acknowledges (`handedOff`).
  Files another session wrote into the working copy while the merge was made stay
  uncommitted (`leftUncommitted`): they are that session's. A merge that conflicts in real work is taken back and says so: resolve it as "Between two examples" in
  `llm-dlc/runtime.md` shows for a queued workspace, or run the stage again so the session rebuilds on the line as
  it is now.
- It committed nothing: read why before going on. A brief that needs no foundation is a fine answer.

Then run the preflight again: the session may have changed the plan, and with it the streams. Tell the user what
it built and what it changed in the plan, in a few lines. If it changed what the brief is for, or dropped
something the brief's Decisions settled, that is the user's to confirm before stage 3 (with `--unattended`:
record it as an open decision, and go on only if the streams' work does not depend on it).

## 3. The run

```bash
python3 llm-dlc/tools/brief_run.py start BRIEF
```

starts `run-streams.sh` detached: a workspace and a loop per stream, and the integration check if the brief names
one; a brief without streams runs as its own loop alone. Each stream, once finished, is put to you to merge. Then
watch it: run `python3 llm-dlc/tools/brief_run.py wait BRIEF`
as a background task, act on what it returns, and run it again, until it returns `ended`.

- **A summary**: print it as it is. Its `time` lines say where each loop's time went: working, waiting on jobs,
  blocked, and finished while other streams still ran.
- **`question` of type `merge`**: a stream is finished, `done` or left blocked, while the others may still run. It
  waits half an hour. Merge it now: run the `merge` command the question prints (`brief_run.py merge BRIEF
  STREAM`). It merges the stream's line into the default workspace's (regenerating the generated trace files and
  taking the stream's session logs), answers the question `merged`, records the merge in the brief's Progress, sets
  the brief's status to `done` once every stream is merged and says done, and commits all of it.
  - A merge that conflicts in real work is taken back and says where. If the conflict is small and you can see
    how both sides meet, resolve it by hand as "Between two examples" in `llm-dlc/runtime.md` shows (a merge
    commit of `@-` and `WORKSPACE@-`, the conflicts resolved, `sync.py regenerate`, `sync.py commit`), then run
    `brief_run.py merge` again, which finds it merged and records it. Otherwise answer `leave` with the command
    the question prints, and tell the user what conflicts.
  - Then check what came in as the brief says (its integration script, if it names one) and run the default
    test run inline (`python3 lib/tools/test_costs.py run`), as `CLAUDE.md` asks after a merge, unless the brief
    rules out test runs. Another stream's merge can wait for it. A failure is reported to the user (with
    `--unattended`: an open decision), not fixed by you: it is the brief's work.
  - A stream left blocked is merged too, unless what it committed is broken on its own: say so with `leave`.
- **`question`** of type `blocked`, a loop that ended `blocked:`. It waits half an hour for you. Read
  the loop's status and the Progress of its brief in its workspace, and its open inbox items. If what blocked it
  is settled, or you can settle it (another stream's answer that is committed, a decision that is yours), record
  the decision, send the stream the item that says so (`inbox.py send NAME-STREAM --kind answer|unblocked ...`),
  and answer `rerun`. If it waits for the user, ask them when they are there; otherwise answer `leave`: it is then
  put to you to merge as it stands, and the brief's status names it. Answer with the command the question prints; each answer is recorded as a decision. A loop is run again
  this way twice at most: the third time it ends blocked it is left without a question.
- **`attention`**: the integration check stopped passing, or a decision is open. The check has already told the
  streams it concerns. Read what it names and decide what is yours, as above.
- **`results`**: results came back, and `wait` collected and committed them (`--only` the paths a commit of
  results holds). Say what came back in a line. Triage each one in `attention` as the run-verification skill's
  step 4 says, and record what needs a person in `verification/findings.md` (its step 5): a verdict also goes to
  the stream it concerns, through its inbox; a job out of time or memory is resubmitted (`pipeline.py resubmit`).
  Commit what you changed with `sync.py commit --only $(python3 verification/pipeline.py commit-paths)`. A stream
  waiting on a job goes on by itself once the job's result is collected.
- **`verification`**: jobs waited and no runner was at work, and one was started (`pipeline.py run`, no model).
  Say so in a line, and go on. With a verification loop running here, it says that none ran and one was started.
- **`ended`**: go to stage 4.

The user may ask about the run at any time: answer from `brief_run.py status BRIEF`, the run's output
(`llm-dlc/loop-summaries/run-streams-NAME/streams.log`) and the queue (`python3 verification/pipeline.py status`).
Fix what is small yourself (a runner that died, a job that hangs, a workspace jj calls stale:
`python3 llm-dlc/tools/unstale.py` from that workspace), say what you did, and leave the
rest to the user. `brief_run.py stop BRIEF` stops the run at a boundary: every loop ends after its cycle under way,
nothing is run again and no stream is put to you to merge, so nothing is cut off; `wait` returns `ended` when it has, and
`start` continues. Use it at the user's word, or when the run should not go on as it is. `stop BRIEF --now`
interrupts mid-cycle instead: only when the run is doing damage.

## 4. Report

When the run has ended, put the budget back (`brief_run.py budget BRIEF --restore`), collect what is back
(`brief_run.py collect BRIEF`, as `wait` did), triage it as above, and tell the user:

- each loop's last status and whether it is merged, and for the brief its `Done when` table, criterion by
  criterion: met, not met, or waiting on which jobs;
- what the timebox deferred, and what is blocked on the user, each with what they need to decide;
- the decisions you made that they have not reviewed
  (`python3 llm-dlc/tools/decisions.py list --group flagged,unreviewed`), and that `decisions.py review` accepts
  or overturns them;
- what the run cost, per loop, and the jobs still out;
- what is left on the machine: the streams' workspaces and the foundation's, which
  `python3 llm-dlc/tools/prune_workspaces.py` lists, any stream not merged (`brief_run.py merge BRIEF STREAM`
  merges it), and that nothing was pushed.

The skill ends here. The session is theirs to continue.

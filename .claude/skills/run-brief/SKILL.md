---
name: run-brief
description: Run a feature brief of this repository (llm-dlc/loops/NAME.md) from start to end as its watcher. A foundation session on Fable 5.2 reads the brief and builds what every stream would otherwise wait for, then the brief's streams run side by side and the watcher merges each into the default line the moment it is finished (in an order, when their lines conflict), while it answers what the run asks, restarts a stream whose loop died, hands work no stream owns to a helper session the user named, keeps the verification queue moving and reports at intervals. Start it only when the user asks for this skill or for a brief to be run, never as a step of other work: a run takes hours and spends their tokens.
argument-hint: "[--no-foundation] [--unattended] [--summary-interval SECONDS] [--helper \"tmux 3\"] <a brief's name or file: NAME | llm-dlc/loops/NAME.md>"
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
- **The user's answers are committed by you.** When the user answers an open decision (`decisions.py answer`,
  themselves or through another session), it is written into the run's decision record in the default working
  copy and left uncommitted: nobody else commits there during a run. `wait` commits the record whenever it has
  changed, your own answers with theirs, under a message that says so. If the user asks who commits an answer,
  say that you do; if another session offers to commit in the default workspace, ask it not to.
- **Record an action after it happened, not before.** A line in a brief's Progress, a decision's rationale, an
  inbox item or a commit message says "restarted", "merged" or "sent" only once the command that did it has
  returned and you have seen its result. What you are about to do is said to the user in the conversation, not
  written into a record.
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
around it. `--helper "tmux 3"` names a session the user has open, by its tmux window or pane, as the run's helper
from the start (see "Work no stream owns" in stage 3): add it once the preflight passes, with
`brief_run.py helper BRIEF add helper --at "tmux 3"`. The user may name one, or another, at any time during the
run in the same words.

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
  - When it says your own environment holds a run's variables (`RUN_STREAMS_WATCHER`, `LOOP_CONDUCTOR`), you
    were started inside a loop or another run: don't unset them and go on. Tell the user, who starts the watcher
    from a session of their own. A loop gives its session none of these variables (`feature-loop.sh` drops them
    before it starts `claude`), so that a stream which tests these scripts cannot put made-up questions to you;
    if a question ever reaches you about a stream or a workspace the brief does not name, answer nothing, say
    so, and look at where it came from.
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

**Find out early whether the streams' lines conflict.** "Merge it the moment it is finished" holds only while the
merges don't interact. Once every stream has made its first commits (the first summary shows them), and again
after any summary in which two streams report work in the same files:

```bash
python3 llm-dlc/tools/brief_run.py trial BRIEF
```

It merges every pair of the streams' lines, and each with the default line, on trial: nothing is committed and no
working copy changes. Generated files and the test inventory are regenerated by a merge and are not counted.

- No pair conflicts: nothing to do. Each stream is merged when it is finished, in any order.
- A pair conflicts in real work: tell both streams through their inboxes what meets and where, and **propose a
  merge order to the user**: the stream whose change the other has to build on goes first, and each later one
  merges the default line into its own before it is finished. Record it as a decision (theirs; with
  `--unattended`, yours when the order is plain from the briefs, flagged `--confidence medium`), then set it:
  `brief_run.py order BRIEF FIRST SECOND ...`. From then on `merge` refuses a stream while one before it in the
  order has commits the line lacks, and the `merge` question of a stream that is held back names what to merge
  first (`order.first`).
- **Don't let a finished stream wait hours for one that is still running.** A stream ahead in the order that is
  still at work is merged as far as it has committed: `brief_run.py merge BRIEF STREAM --early` (what its session
  has not committed stays with it, its later commits come in by its own merge at the end, and the brief's status
  is left alone). Do the same, order or not, when a long-running stream holds commits that others are waiting to
  build on, and before the end of a run to shorten the last merge. Answer `leave` to a held-back stream's question
  only when the stream before it cannot be merged even early (its line does not build, or conflicts): say why.

- **A summary**: print it as it is. Its `time` lines say where each loop's time went: working, waiting on jobs,
  blocked, and finished while other streams still ran.
- **`question` of type `merge`**: a stream is finished, `done` or left blocked, while the others may still run. It
  waits half an hour. Merge it now: run the `merge` command the question prints (`brief_run.py merge BRIEF
  STREAM`), after the merges its `order` names, if it has one. It merges the stream's line into the default workspace's (regenerating the generated trace files and
  taking the stream's session logs), answers the question `merged`, records the merge in the brief's Progress, sets
  the brief's status to `done` once every stream is merged and says done, and commits all of it; `nowDue` lists
  the streams the order held back behind it that can be merged now.
  - A merge that conflicts in real work is taken back and says where. If the conflict is small and you can see
    how both sides meet, resolve it by hand as "Between two examples" in `llm-dlc/runtime.md` shows (a merge
    commit of `@-` and `WORKSPACE@-`, the conflicts resolved, `sync.py regenerate`, `sync.py commit`), then run
    `brief_run.py merge` again, which finds it merged and records it. Otherwise answer `leave` with the command
    the question prints, and tell the user what conflicts.
  - Then check what came in as the brief says (its integration script, if it names one) and run
    `python3 lib/tools/default_run.py after-merge`, unless the brief rules out test runs. It runs the default
    test run only when one is due: the last one here failed, or none has passed here in the last hour. A run
    merges often and the default run is the most expensive thing you run, so most merges run none, and it says
    so in a line. When it runs, it runs in a memory cap of its own (8G) with two Rust test binaries at a time,
    so it cannot fill your session's memory. Never run the bare `test_costs.py run` after a merge. Another
    stream's merge can wait for it. A failure is reported to the user (with `--unattended`: an open decision),
    not fixed by you: it is the brief's work, and the next merge runs it again whatever the hour.
  - A stream left blocked is merged too, unless what it committed is broken on its own: say so with `leave`.
- **`question`** of type `blocked`, a loop that ended `blocked:`. It waits half an hour for you. Read
  the loop's status and the Progress of its brief in its workspace, and its open inbox items. If what blocked it
  is settled, or you can settle it (another stream's answer that is committed, a decision that is yours), record
  the decision, send the stream the item that says so (`inbox.py send NAME-STREAM --kind answer|unblocked ...`),
  and answer `rerun`. If it waits for the user, ask them when they are there; otherwise answer `leave`: it is then
  put to you to merge as it stands, and the brief's status names it. Answer with the command the question prints; each answer is recorded as a decision. A loop is run again
  this way twice at most: the third time it ends blocked it is left without a question.
- **`helper`**: a helper's task is done (see "Work no stream owns" below).
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

### A stream whose loop ended without a status

A summary shows a stream that is not `running` and whose status says neither `done` nor `blocked:` (its phase
says it stopped twice without a status, or its cycle and commits have stood still while `streams.log` shows its
loop ended), or one that ended `blocked` on nothing its brief names. Its session died: killed for memory, or
ended on an error. It is not blocked on a decision, and it does not wait for the end of the run.

1. Read the end of its part of `streams.log` and the last lines of its session's output for what ended it. A
   session killed for memory (the kernel's kill in `journalctl --user -k`, or a loop that ended mid-command)
   usually ran tests without a cap: send the stream an inbox item saying to run its changed tests as
   `systemd-run --user --scope -q -p MemoryMax=8G -p MemorySwapMax=0 python3 lib/tools/test_costs.py run --changed --rust-jobs 1`.
2. Run it again inside the run:

   ```bash
   python3 llm-dlc/tools/brief_run.py rerun BRIEF STREAM
   ```

   `run-streams.sh` starts its loop again as soon as the stream's own process there has ended, with its counts of
   failures and reruns at nought, and puts it to you to merge when it is finished. If a `blocked` or `merge`
   question for it is still open, answer it `leave` first, as `rerun` says. Before any loop starts,
   `run-streams.sh` stops a scope that holds only what an ended loop left (the tests a killed session was
   running), so the leftovers no longer make the restart fail; a scope with a loop at work in it is left alone,
   and `rerun` refuses a stream whose loop is running. When the run itself has ended, `rerun` starts it again for
   that stream.
3. Record what you did once it has started (a line to the user, and a finding in `verification/findings.md` when
   the cause is the machine's or the tooling's), not before.

**A stream whose work is to challenge the others' is restarted at once, never held until the run ends**: what it
finds is worth most while the streams it reads are still at work, and every hour it sits idle is an hour of their
work nobody questioned. The same goes for any stream others wait on. A stream that dies a second time the same
way is the user's to hear about (with `--unattended`: an open decision), with what you saw both times.

### Work no stream owns: helpers

You do none of the brief's work, and sometimes work turns up that no stream owns: a tool whose stream has
finished, a fix two streams each took for the other's, a small repair the run needs now. A **helper** takes it: a
Claude Code session the user has open in a tmux pane, which they name when they start the run
(`--helper "tmux 3"`) or at any time after ("use tmux 4 as a helper"). Never pick a pane yourself, and never
start a session to be one.

```bash
python3 llm-dlc/tools/brief_run.py helper BRIEF add NAME --at "tmux 3" [--role TEXT]
python3 llm-dlc/tools/brief_run.py helper BRIEF task NAME --title TEXT --file FILE
python3 llm-dlc/tools/brief_run.py helper BRIEF merge TASK
python3 llm-dlc/tools/brief_run.py helper BRIEF list
```

- **The first helper is for low-hanging work**: small, well-bounded pieces with a plain end, the kind a stream
  would finish in part of a cycle. Name it `helper`. The user may add others during the run for a harder problem,
  each with the role they give it (`--role`): a specialist on a larger model for one wall, say. Give each helper
  only work that fits its role; a sticky problem is not the first helper's, and is put to the user, who may add
  one for it.
- **A task is a narrow brief.** Write what is asked to a file in your scratch space: the one outcome, the files
  it may touch, how it is to be verified, and what is out of its scope. `task` wraps it in the rules a stream
  works under (its own workspace only, `CLAUDE.md`, commits with `sync.py commit`, no merge and no push, stop
  and report rather than widen), puts the helper's workspace, `BRIEF-NAME`, at the default line's last commit
  (made on first use; it refuses while the default workspace is in the middle of a merge), and types one line
  into the helper's pane that names the brief's file. It types nothing into a pane that is at a shell prompt.
  One task at a time for each helper: the next is given once the last is merged.
- **`wait` returns `helper`** when the helper says the task is done, with its report, its commits and what it
  left uncommitted. Read the report against what you asked, then `helper BRIEF merge TASK` brings its commits to
  the line as any merge does, and you tell the streams it concerns through their inboxes
  (`inbox.py send NAME-STREAM --kind delivered --do ... --commit CHANGE`), then `default_run.py after-merge` as
  after a stream's merge. What it left undone or reported as wider than asked is yours to judge: a second task,
  the user, or a finding.
- A helper is not a stream: it has no status line, no loop and no rerun, and its session is the user's. If it
  does not answer, say so to the user; don't type into its pane again by hand. Its workspace is kept for its next
  task and listed at the end of the run.

### Material from outside the run

A session that is no part of the run may produce something for it: another tool's review of a stream's work, a
specialist the user started on one problem, a note the user wrote. None of it reaches a stream by itself.

- **New files only.** Outside material comes in as files of its own (a review, a note, a proposed patch as a
  file), never as edits to files a stream is working on. If it changes existing files, a stream takes it up from
  the new files, or it becomes a helper's task.
- **You merge it.** From a workspace: add its session as a helper with its role and merge as above, or `land` its
  line when the user says it is finished. From files the user hands over: commit them alone
  (`sync.py commit --only PATH ...`). Record the decision to take it in (`decisions.py record`).
- **A stream acknowledges it.** Send each stream it concerns an inbox item that names the files and what to do
  with them (`inbox.py send NAME-STREAM --kind delivered --do ...`); the stream acknowledges it in its Progress,
  which is how you know it was read. Material no stream has acknowledged by its next cycle is said to the user.
- **When a stream is at the same wall for two cycles** (two summaries with the same obstacle in its Progress, or
  a second `blocked:` on the same thing), suggest to the user a specialist: a session on a larger model than the
  stream's, given that one problem and nothing else, whose result comes in as above. Say what the wall is, what
  the stream tried, and what the specialist would be asked. Starting one is the user's decision and their
  session.

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
(`brief_run.py collect BRIEF`, as `wait` did), triage it as above, and, unless the brief rules out test runs, run
`python3 lib/tools/default_run.py after-merge --final`: after the run's last merge the default test run runs
whenever no passed run covers the line as it stands, whatever the hour (a push asks for the same record). Then
tell the user:

- each loop's last status and whether it is merged, and for the brief its `Done when` table, criterion by
  criterion: met, not met, or waiting on which jobs;
- what the timebox deferred, and what is blocked on the user, each with what they need to decide;
- the decisions you made that they have not reviewed
  (`python3 llm-dlc/tools/decisions.py list --group flagged,unreviewed`), and that `decisions.py review` accepts
  or overturns them;
- what the run cost, per loop, and the jobs still out;
- the helpers' tasks, each with whether it is merged (`brief_run.py helper BRIEF list`), and the outside
  material you took in;
- what is left on the machine: the streams' workspaces, the foundation's and each helper's, which
  `python3 llm-dlc/tools/prune_workspaces.py` lists, any stream not merged (`brief_run.py merge BRIEF STREAM`
  merges it), and that nothing was pushed.

The skill ends here. The session is theirs to continue.

# Brief: a conductor for parallel streams

**Drafted 2026-11-14; its [decisions](#decisions) settled by the user the same day. Steps 1–3 of [the plan](#the-plan)
run now, beside example-targets' Phase 5, in the jj workspace `stream-conductor`; this branch is merged, and steps 4–6
start, only after example-targets is done**: it changes `run-streams.sh`, `feature-loop.sh` and `sync.py`, which the
running loop uses. See [This run](#this-run-steps-13-beside-example-targets).

## This run: steps 1–3 beside example-targets

The user started this loop on 2026-11-14 while example-targets' own loop runs Phase 5 in the default workspace
(`../in-the-loop`), from that loop's commit `krnmkrsm`. Keep out of its way:
- Work only in this workspace (`../in-the-loop-stream-conductor`). Never edit, snapshot or run jj commands against the
  default workspace's files, never merge this branch into its line or rebase onto it, and never push. The merge is the
  user's to start once example-targets is `done`, with `sync.py regenerate` after `jj new`.
- Test on made-up data in temporary repositories, as `llm-dlc/tools/test_workspaces.py` does. Don't start Claude
  sessions, `feature-loop.sh`, `run-streams.sh` or systemd scopes: a scope named `feature-loop-*` counts as a loop in the
  verification runner's budget, and a real two-stream trial belongs to step 6.
- No verification jobs are expected. The runner reads the default workspace's queue, so a job submitted here would not
  run until the merge; if one is needed, record it in Progress instead.
- Gitignored local files (`verification/pipeline.local.toml`, uploaded logs) are not in this workspace; nothing in steps
  1–3 needs them.
- Example-targets is the source of the [table above](#where-it-starts-from), and its data may change while you work;
  read it, don't edit its brief or files.

## Direction

Today a parallel run has two phases with nothing between them. The streams work blind to each other, and one merge loop
reconciles everything once the last of them stops. All the coordination work waits for the end, then lands on the merge
loop and on the user at once:
- interface requests between streams;
- disagreements only a merged tree shows;
- questions a stream can't settle itself;
- warnings and allow-list proposals.

A **conductor** is a fifth loop that runs beside the streams and does that work as it comes up:
- keeps a merged, tested revision of the streams current;
- routes to each stream only what it needs to act on;
- **decides what it can safely decide, and records each decision so the user can review it afterwards**, rather than
  approve it first;
- merges a finished stream early where that is worth something.

The streams stay undistracted. The final merge becomes a formality. The user reviews a log of what was decided, and
answers only what couldn't be decided without them.

## Where it starts from

What the last four runs spent after their streams stopped, and what a conductor would have caught earlier:

| Run | What waited for the end | Cost |
|---|---|---|
| foundations (2026-11-07) | The integration check stopped at generated-file conflicts from 05:01; a real `serde(default)` bug surfaced only at the merge. | A defect found hours late. |
| cleanup (2026-11-07) | A for-review list of three user decisions (VF-018, VF-001, VF-020) and the new findings, reviewed in a separate session after the push. | A review session after the run. |
| application-core (2026-11-08) | Seven interface requests (Phase 5 step 1). Two allocation-bound decisions, asked only once the merge loop was blocked. Three streams stopped "working" after a clean stop and needed a restart. | Streams done ~11:57, Phase 5 done 22:15. |
| example-targets (2026-11-14, running) | Positive stopped `done` at 16:28 with a build-route question (answered by the user in another session). The integration check stopped at conflicts from 16:28, with two runtime×workflow disagreements found by a manual check at 17:13 and passed on through the report file. Two streams' logs carry long-token findings, and 15 allow-list proposals await the user. | Ongoing. |

Already in place (`xyootzvm`):
- `sync.py regenerate` settles the generated trace files after any merge, and the integration check uses it.
- `check` reads only the history of `@`, so a stream's commits no longer show as errors elsewhere.

The conductor builds on both.

## Design

### 1. A rolling integration line

The conductor owns the `NAME-integration` workspace, which today only runs the check.
- **Each time a stream commits**, it merges the streams' `@-`, runs `regenerate`, and runs the brief's integration script.
- **A passing merge is committed** on the integration line, never pushed and never committed in the default workspace.
  The line always holds the newest merge known to work.
- **A failing merge is not committed.** The conductor reads the failure, works out which streams' changes disagree from
  the files and tracebacks, and either decides how the two sides meet (3) or queues it for the user. Each side is then
  told what it has to do.
- **A real textual conflict** (source, not generated files) is handled the same way, for the streams that touched the
  file.

### 2. Inboxes: one channel, only what a stream has to act on

A stream can't be told anything today except through the integration report. Editing its brief stops its loop, and its
Progress is its own.
- **Each stream gets an inbox** in the default workspace: `llm-dlc/loop-summaries/NAME-STREAM-inbox.md`, gitignored like
  the reports. `feature-loop.sh` adds one sentence to every cycle's instruction: read the inbox, and acknowledge each item
  by its id in the commit's Progress update.
- **Not distracting the streams is a rule:** an item goes to a stream only if that stream has to change something or
  may now go on.
  - Examples: an integration failure in its code, the rule two streams' interfaces are to meet by, an answer it was
    waiting for, "you're unblocked", a decision overturned that touches its work.
  - What the conductor did elsewhere, its upkeep, and decisions that change nothing for a stream stay out of that
    stream's inbox.
- **Precedence**, stated in the instruction: the brief, then the user's decisions, then the conductor's messages. A
  message that contradicts the brief is to be reported, not obeyed.
- **Streams still talk to the conductor through their commits and Progress**, which it reads. An interface request is a
  Progress line as now, but it is answered during the run, not at the merge.

### 3. Decisions: act first where recovery is cheap, review afterwards

The user's rule ([decision 2](#decisions)): the conductor decides when it is **confident** and the decision is **low
risk**. Risk means how hard the decision would be to recover from or redo later. It leans towards acting, because the
user reviews afterwards instead of approving first.

**The test, applied to each decision and recorded with it:**

- **Confidence.** High only when the choice follows from what is written or tested, and the conductor can name what that
  is:
  - the brief's Direction or Decisions;
  - an existing interface or test;
  - a precedent in an earlier decision.

  The alternatives must have been looked at and found worse for a stated reason. Otherwise it is medium or low.
- **Recovery cost**, one of three classes:
  - **cheap**: undoing it is at most about one stream cycle of work. It is contained in unpushed commits and working
    files, it has no effect outside the repo, and nothing else is likely to build on it before the user's next review.
    Examples: how two streams' interfaces meet, a test fix, a name or number, the order of independent items, a fixture
    detail.
  - **costly**: undoing it is possible but takes real work. Other work will build on it, or it means re-running long
    verification jobs.
  - **irreversible**: it can't be taken back, or not in full. Examples: anything published (a push, an upload, a
    deletion of data, logs or workspaces with unmerged work), anything outside the repo (downloads policy, network,
    installing software), spending beyond the run's budget.
- **What it does with the result:**

  | | cheap | costly | irreversible |
  |---|---|---|---|
  | **high confidence** | decide, log it as `unreviewed` | decide, log it, and **flag** it at the top of the review | queue for the user |
  | **medium** | decide, log it, and flag it | queue for the user | queue for the user |
  | **low** | queue for the user | queue for the user | queue for the user |

- **Never delegated, whatever the test says:**
  - what the brief's Decisions already settled;
  - scope and acceptance criteria;
  - verification bounds;
  - security and redaction: approving an allow-list proposal or accepting a finding stays the user's, by `CLAUDE.md`;
  - pushing.
- **A stream never waits for the end of the run** for a decision it asked for during the run. It is decided at once, or
  queued at once and the stream goes on with other items where it can.

**Recovery cost grows over time.** A cheap decision becomes costly as later commits build on it, so the record lists
what depends on it (`dependents`). When those reach a threshold (proposed: three commits, or any job), the conductor
re-flags the decision for review, before overturning it gets expensive. This is the main cost of acting first, and the
reason reviews are asked for early rather than at the end.

**Overturning.**
1. The user marks a decision `overturned`, with what they'd rather have.
2. The conductor makes that the new decision, with `supersedes`.
3. It sends each affected stream an inbox item with the undo steps the record lists, and sets the old record
   `superseded`.

An overturned decision costs at most its recorded undo, plus whatever its dependents grew to.

**Tradeoffs of acting first, as opposed to approving first:**
- *Gained:*
  - no stream blocks on a question the conductor could answer;
  - the user's time goes into one review of a list, not interruptions;
  - decisions are taken while their context is fresh.
- *Paid:*
  - rework when a decision is overturned (bounded by the cheap class);
  - work built on a decision that later changes (bounded by re-flagging as dependents grow);
  - a review list that can grow (it is sorted, and flagged entries come first);
  - some risk of a confidently wrong decision, which recording the basis makes visible and the merge loop's for-review
    list still includes.
- *Not given up:* nothing irreversible, or already settled, is ever decided without the user.

### 4. The data: one decision record, a projection for each use

Notifications come later ([decision 3](#decisions)). What matters now is data that every later view can be built on.

**`llm-dlc/decisions/NAME.jsonl`**, committed:
- One JSON object per line, one line per change of state. A decision's current state is its last line, so the history
  stays and appending never conflicts within one writer. Only the conductor writes it.
- It is committed with the conductor's Progress update, so a decision's record and its effects land together and are
  published with the run.

Each line holds the following, in a `llm-dlc/decisions/schema.json` validated by `check`:

| Field | What it holds |
|---|---|
| `id`, `run`, `seq` | `NAME-D007`, the run's start, and the line's sequence number |
| `state` | `open` (queued for the user), `decided`, `superseded` |
| `asked` | by whom (a stream, the conductor, the integration line), when, and the question in one sentence |
| `context` | the commits, files, findings (`VF-NNN`), jobs and inbox items it is about |
| `options` | each with an id, a summary and its consequences |
| `decision` | the option, `by` (`conductor` or `user`), when, the rationale, `confidence` with its `basis`, and `recovery` with its class, the undo steps, and the `dependents` so far |
| `review` | `unreviewed`, `accepted`, `overturned` (with the user's note) or `flagged` (with why: costly, medium confidence, or dependents grown) |
| `applied` | the inbox items sent, and the commits that carried it out |
| `blocks` | the streams waiting on it, empty once decided |
| `supersedes` | the decision this one replaces, if any |

**Projections, all generated from it and none written by hand:**
- **the review view:** `llm-dlc/decisions/NAME.md`, rendered by `sync.py` like the other generated files. Flagged
  entries first, then open questions, then unreviewed decisions, then the rest;
- **the status bar:** counts of open, flagged and unreviewed decisions;
- **the inboxes:** the items each decision generated;
- **the merge loop's for-review list:** the decisions still `unreviewed`.

A notification layer added later reads the same file.

**The user's side.** The user reviews or answers in any session: "accept D003–D007", "overturn D004: use a root
parameter", "D009: b". That session appends the review line and nothing else, and the conductor applies it next cycle. A
small `decisions.py` lists, shows, reviews and answers by id, so neither side edits JSON by hand. It writes only `review`
and answer lines, and the conductor alone writes decisions.

### 5. Merging a finished stream early, where it is worth it

This is a judgement for the conductor each time a stream is `done` ([decision 4](#decisions)), not a default. It merges
the stream into the default line early only if one of these holds:
- its work unblocks follow-up items that can start now, such as positive's P3 preparation after decision 1's extension;
- other streams are about to depend on its interfaces;
- its branch is drifting into growing conflicts with the default line.

Otherwise it waits for the final merge. An early merge happens in the conductor's own workspace and the default line.
It never touches the running streams, and tells them nothing unless the merge changes what they have to do. Each early
merge is itself a logged decision (cheap or costly by the test above).

**Superseded on 2026-11-17, at the user's word:** there is no final merge any more. The watcher of `/run-brief`
merges every stream the moment it is finished (`brief_run.py merge`, answering `run-streams.sh`'s `merge`
question), and the brief's own loop no longer runs after the streams ([`llm-dlc/README.md`](../README.md#a-briefs-run)).

### 6. Upkeep the user does today

- Restart a stream that stopped `working` after a clean stop (the application-core bug), instead of counting it done.
- Collect `check` warnings and allow-list proposals as open questions in the decision record (the user still approves in
  their own terminal).
- Keep `findings.md` entries linked to the stream that owns them, and send that stream an inbox item when one about its
  work opens or closes.
- Tell the verification runner when the number of running loops changes, so it can move to a larger budget row in
  `pipeline.local.toml`.

### 7. A moonshot conductor: judging a compaction from outside the loop

Added 2026-11-15 at the user's request, for later, after the streams' steps. Built elsewhere since: the user said on
2026-11-15 that `/prove-java-change` supersedes it, and its session, the watcher, is the moonshot conductor
([`runtime.md`](../runtime.md#the-conductor), `tools/conductor.py`, `tools/watch.py`). This design stays as the
record of what was asked; what it does not have yet is listed under step 7.

A moonshot (a one-line instruction, or one item of a list, repeated by `feature-loop.sh`) has no acceptance criteria, so
nothing says when an item should stop. The user wants its session chained across cycles, so later cycles build on what
earlier ones learned, and the moonshot's input kept to the one line: no added rules, since that would spoil the experiment.
Not finishing an item is fine as long as the work is productive: another pass can come back to it.

The mechanical rule comes first, `uzporttn` (workspace `moonshot`, not yet on the default line on 2026-11-15):
- every moonshot turn passes `--autocompact 600k`;
- an automatic compaction with no commit since the cycle began, or since the last compaction, ends the turn and stops the
  loop for the user.

A compaction is the natural point to judge, but a rule can't tell the two cases apart:
- the work is hard and still going well;
- the session is stuck and needs a person.

The moonshot conductor makes that judgment and acts on it:
- **From outside the loop.** It is a separate session, so the moonshot is not distracted and its input stays the one line.
  That is the conductor's job for streams too.
- **On the compaction event.** It reads what the session did since the cycle began or the last compaction:
  - the transcript;
  - the commits and the working copy's diff;
  - test runs, and jobs submitted or failed;
  - whether the same failure or file keeps coming back.
- **It acts, by Design 3** (act where recovery is cheap, the user reviews afterwards):
  - **let the turn go on**, the default when the work is moving;
  - **stop the loop**, with a decision queued for the user saying why, when the session is stuck;
  - possibly other actions for the implementer to propose, such as ending the item at its last good commit so the loop
    moves to the next item.
  Each judgment goes into the decision record with its basis, as every other decision does.
- **The mechanical rule stays** as the fallback when the conductor isn't running or can't decide. The conductor's
  verdict replaces the rule's stop, not the event that triggers it. `show_progress` in `loop-common.sh` already sees the
  `compact_boundary` event and holds claude's pid, so it is where the hand-off goes.

The run that prompted this: `prove-examples` (examples 285–300), started 2026-11-15 16:13 UTC. Cycle 1 compacted at
477k tokens, committed `lvvpsuxl` 80 minutes in, and went on in the same turn to the next part of the item. The user let
it run because its progress was good. That is the judgment this conductor should be able to make on its own.

### How it runs

The conductor is a `feature-loop.sh` loop in the default workspace (`NAME-conductor`), started by `run-streams.sh` in
place of today's `integrate()` bash loop.
- **It wakes on events, not on a fixed cycle.** `run-streams.sh` already watches for each of them and starts one
  conductor cycle when any happens: a stream's `@-` moves, a stream's status changes, the verification loop commits, a
  review or answer line is appended, or an hour passes.
- **The model, by decision 1:** Sonnet for routing and upkeep. A cycle whose work is a decision or a failure triage runs
  on Opus.
- **It keeps one session for the run**, compacted as usual, so it remembers what it routed.
- **A blocked stream comes back on its own.** A stream that stopped `blocked:` on an open decision is re-run by
  `run-streams.sh` once that decision is `decided` and its inbox says so.
- **Its brief** is the main brief's `## Conductor` section, plus a standing section in `brief-template.md`. That section
  covers the test of 3, the never-delegated list, and the inbox rule.

### 8. Proposed: the watcher as the one conductor, in place of step 4's loop

Proposed 2026-11-16, after the user chose to fold step 4 into the watcher of `/prove-java-change`
([`runtime.md`](../runtime.md#the-watcher)) instead of building a second conductor inside `run-streams.sh`. It is a
proposal for the user to read. Nothing of it is built, and [How it runs](#how-it-runs) and plan step 4 stand as
written until the user says which they want.

**What the watcher already is.** One session on Opus 5.5 that does none of the work. It starts the sessions that
do, blocks in `watch.py wait` until something needs a judgement, answers, and waits again. Since 2026-11-16 each of
its answers is a decision in the record of Design 4 (`llm-dlc/decisions/prove-change.jsonl`), reviewed and
overturned with `decisions.py` like any other. It also merges a queued workspace between two examples and prints a
summary at intervals. That is the conductor of Design 7, and most of the conductor of this section's steps, for one
loop.

**What a parallel run needs beyond that.**

| A parallel run needs | Step 4 as written | With the watcher |
|---|---|---|
| To be woken when something happens | `run-streams.sh` watches and starts one conductor cycle per event | `watch.py wait` reads several runs: each stream's status and `@-`, the integration line's report, new review and answer lines in the record. It returns only what needs a judgement; everything else is counted into the next summary |
| Routing and upkeep (`inbox.py collect`, `send`) | A conductor cycle on Sonnet | A script, run by `wait` before it returns: routing needs no model |
| A decision or a failure triage | A conductor cycle on Opus | The watcher, with `decisions.py record` and `inbox.py send`, under the test of Design 3 |
| A question for the user | Queued in the record as `open` | Asked in the conversation when the user is there, and recorded with their answer; queued as `open` when they are not |
| Starting and re-running streams | `run-streams.sh` | The same script, started detached by `watch.py streams start BRIEF`, as `watch.py loop` starts the proof loop. It keeps re-running a stream that a decision unblocks |
| Early merge (step 5) | The conductor's cycle | The watcher's merge of a queued workspace, which it does today between examples |
| The conductor's brief | `## Conductor` in the brief template | A skill of this repository for the watcher of a parallel run, with the test of Design 3, the never-delegated list and the inbox rule |

**What changes in the plan.** Step 4 becomes: `watch.py wait` over several runs with the streams' events, upkeep
as a script, `watch.py streams start|status`, and the skill. Steps 5 and 6 keep their content; step 6 also measures
what the watcher itself costs per hour of a run. Step 7 is done except for its measurement.

**What it costs, and what is the user's to decide.**

1. **Attended, or not.** Step 4's conductor is started by `run-streams.sh` and outlives the user's terminal. The
   watcher is the user's own Claude Code session. While it is closed the loops go on, since no answer never stops
   one, but a stream that is `blocked:` on a decision stays blocked until a watcher is back. Its state is all in
   files, so a new session takes over where the last one stopped. A parallel run that must decide while nobody is
   there would need a headless watcher (`claude -p` on the same tools) as part of this step. I would build the
   attended watcher first and add the headless one only if step 6 shows blocked hours.
2. **One model.** Decision 1 of this brief splits Sonnet for routing and Opus for decisions. With routing done by a
   script there is no Sonnet session, and every judgement is Opus 5.5 at high effort. That replaces decision 1.
3. **Where it is started.** A skill of its own for a parallel run, sharing `watch.py`, or a mode of
   `/prove-java-change`. I would keep them apart: the plugin's skill is released to users, and a parallel run of
   briefs is how this repository is developed.
4. **One context for several streams.** Four streams send more events than one loop. `wait` keeps what it prints
   small and the state stays in files, but the watcher's own compactions on a long run are something step 6 has to
   look at.

## The plan

1. **The decision record:** `llm-dlc/decisions/schema.json`, `decisions.py` (list, show, review, answer, render), the
   rendered view in `sync.py`'s generated files (and in `regenerate`), and `check`'s validation. It is tested on made-up
   decisions, including an overturn with dependents.
2. **Inboxes:** the file convention, the sentence in `feature-loop.sh`'s instruction, the precedence rule and the
   only-what-to-act-on rule. Tested on a two-stream fixture run.
3. **Rolling integration line:** `integrate()` replaced by commits on the integration line, with failures triaged into
   decisions and inbox items. This keeps today's report file for the status bar.
4. **The conductor loop:** event-driven wake-ups in `run-streams.sh`, the model split, a `NAME-conductor` scope with a
   small cap, re-running streams that a decision unblocks, and `## Conductor` in the brief template.
   [Design 8](#8-proposed-the-watcher-as-the-one-conductor-in-place-of-step-4s-loop) proposes the watcher in its
   place; the user has not yet said which.
5. **Early merge, where it is worth it:** the criteria of 5, the per-stream reconcile, and starting follow-up work.
6. **Measure it on the next parallel run**, against the table above:
   - the time from the last stream finishing to the brief being `done`;
   - integration checks that ran versus stopped;
   - decisions made during the run versus queued;
   - decisions the user overturned, with the rework each cost.

7. **The moonshot conductor** ([Design 7](#7-a-moonshot-conductor-judging-a-compaction-from-outside-the-loop)), after
   step 6, when these streams are picked up again: the compaction hand-off from `show_progress`, the judgment session,
   its actions, and its decision records. Measured on the next moonshot run: the stops it avoided, and the stops it made
   that the user agreed with. Done outside this brief, in `/prove-java-change` (merged here on 2026-11-16). Its
   verdicts go to a decision record since 2026-11-16 (`llm-dlc/decisions/prove-change.jsonl`, written by
   `conductor.py decide`). One thing is open: nothing has measured them on a real run yet.

Each step is one commit with its tests. Steps 1–3 are useful before the conductor session exists: a session can write
decisions and inbox items by hand, as was done on 2026-11-14.

## Decisions

Settled by the user on 2026-11-14:
1. **Model:** Sonnet for routing and upkeep, and Opus for a decision or a failure triage.
2. **What may be decided without the user:** high-confidence, low-risk decisions, where risk is how hard a decision would
   be to recover from or redo. The conductor leans towards acting, because the user reviews afterwards, not before. The
   mechanism and its tradeoffs are [Design 3](#3-decisions-act-first-where-recovery-is-cheap-review-afterwards).
3. **Notifications:** later. The right data comes first ([Design 4](#4-the-data-one-decision-record-a-projection-for-each-use)),
   and any notification is layered on top of it.
4. **Early merge of a finished stream:** contextual, only where it is worth something, and never at the cost of
   distracting the running streams ([Design 5](#5-merging-a-finished-stream-early-where-it-is-worth-it)).
5. **No rebase onto the integration line for now.** It may come back later, or brief by brief where the subject calls
   for it, as a stream's own `- sync: integration` setting.

Open, for the implementing session to propose:
- the dependents threshold for re-flagging (proposed: three commits or any job);
- whether `decisions.py` is part of `sync.py` or its own tool (proposed: its own, like `streams_status.py`).

## Risks

- **Commits in the default workspace collide** with the verification loop's, which sweeps uncommitted files. The
  conductor commits each edit at once and keeps others' files out, as run-verification's step 6 does.
- **A confidently wrong decision** costs a rework. The cheap class bounds it, the recorded basis makes it visible, and
  re-flagging as dependents grow keeps it from compounding.
- **Inbox instructions that drift from the brief.** The precedence rule, and a stream reports a contradiction instead of
  following it.
- **Review fatigue** from a long log. Sorting puts flagged entries first, and accepting a range at once is one line.
- **Cost:** another session. Waking on events, with Sonnet for routine cycles, keeps it mostly idle and cheap. Today's
  coordination already costs a merge loop's hours plus the user's.

## Done when

The next parallel run uses the conductor:
- no integration check stops at generated files;
- every interface request is answered during the run;
- no stream waits for the end of the run for a decision;
- every decision made without the user is in the record with its basis and recovery class;
- the time from the last stream finishing to the brief being `done` is at most an hour, apart from follow-up jobs.

## Progress

- 2026-11-14, drafted after the user asked for a runtime orchestrator, from today's example-targets run and the last
  three runs' records.
- 2026-11-14, the user's directional answers to the five decisions folded in. Design 3 is now act-first with a recovery
  test and review afterwards, and Design 4 is the decision record and its projections. Early merge is contextual, and
  there is no rebase.
- 2026-11-14, the user chose to run steps 1–3 now in the workspace `stream-conductor`, beside example-targets' Phase 5
  (see [This run](#this-run-steps-13-beside-example-targets)); steps 4–6 wait for its merge. Next: step 1, the decision
  record.
- 2026-11-14, step 1 done: the decision record.
  - `llm-dlc/decisions/schema.json` and `llm-dlc/tools/decisions.py`, a tool of its own as proposed (`list`, `show`,
    `counts`, `review`, `answer`, `render`, `check`, and the conductor's `record` and `depend`).
  - The views are rendered by `sync.py` with its other generated files and by `regenerate`. `check` validates the
    records against the schema, plus the rules it can't state, Design 3's action table among them. Leak scanning
    covers the records too.
  - Tests: `test_decisions.py` (15, including an overturn after dependents grew, and agreement with `jsonschema`) and
    two more in `test_workspaces.py`. All 210 tool tests pass.
  - The two open items, taken as proposed:
    - the re-flag threshold is three commits or any job (`DEPENDENTS_THRESHOLD`);
    - `decisions.py` is its own tool.
  - Beyond Design 4's field table:
    - every line has a `kind` (`decision`, or the user's `review` and `answer` lines) and an `at`, so a review never
      rewrites the conductor's snapshot;
    - the views add an "overturned, waiting for the conductor" group between unreviewed and the rest.
  - Next: step 2, inboxes.
- 2026-11-14, a fix found by step 1's own commit: `check` reported 8 false errors on example-targets commits under
  this branch.
  - Cause: session `d34058d5`, still at work in the default workspace, had stamped them, and only that line's copy of
    its manifest lists the log.
  - Fix: such a trailer is now a note when another workspace's working copy holds a manifest that lists the log.
  - Two tests in `test_workspaces.py`; 212 tool tests pass.
- 2026-11-14, step 2 done: inboxes, `llm-dlc/tools/inbox.py`.
  - The convention: `llm-dlc/loop-summaries/NAME-STREAM-inbox.md` in the default workspace, rendered from
    `NAME-STREAM-inbox.jsonl` beside it. Both are gitignored, and `send` and `collect` find the default workspace from
    any workspace.
  - Item ids are `NAME-STREAM-I001`. Open items are shown in full; acknowledged ones get a line each.
  - The sentence: `feature-loop.sh` adds `inbox.py instruction NAME` to every brief's cycle instruction. It names the
    inbox path, says to acknowledge each item by its id in the Progress update, and states the precedence (brief,
    then the user's decisions, then the conductor; a contradiction is reported, not obeyed). The inbox's own header
    repeats it.
  - The only-what-to-act-on rule as `send` enforces it:
    - an item is one of six kinds, each from Design 2's list: `failure`, `interface`, `answer`, `unblocked`,
      `overturned`, and `queued`;
    - `queued` is my addition, from Design 3's "queued at once and the stream goes on";
    - every item says what to `do` and names a decision or commit as its source;
    - a decision it names must be in the state the kind needs;
    - anything else is refused and nothing is written.
  - An item sent for a decision is added to that decision's `applied.inbox`.
  - `collect` takes acknowledgements from each stream's committed Progress (`WORKSPACE@-`), keeping the commit and the
    Progress line, so a reported contradiction shows.
  - Tests: `test_inbox.py` (8), including the two-stream fixture run. That run is a real jj repo with a default
    workspace and two stream workspaces:
    - the conductor sends an interface rule to both streams, and the upkeep item is refused;
    - each stream finds its inbox through the sentence's path from its own workspace;
    - one stream acknowledges in a commit, while an uncommitted edit doesn't count;
    - after the user overturns the decision, both streams get the undo;
    - one stream reports the stale item as contradicting its brief.

    All 220 tool tests pass.
  - Next: step 3, the rolling integration line.
- 2026-11-14, step 3 done: the rolling integration line, `llm-dlc/tools/integration.py`. `run-streams.sh`'s
  `integrate_once` now calls it, with the systemd scope around the script only. `integrate()` still decides when.
  - Each run merges every stream's `@-` in `NAME-integration`, with the line's newest passing merge as a parent too, so
    the line is one chain. It settles the generated files with that tree's `sync.py regenerate`. With no other conflict
    it runs the script, then drops whatever the script wrote into the tree.
  - A passing merge is committed there with `Integration-Line: NAME` and an `Integration-Head: STREAM COMMIT` per stream.
    `integration.py line NAME` names the newest. Nothing is pushed or committed in the default workspace.
  - A failing merge, a real conflict or a failing script, is left uncommitted and triaged. It is attributed to the
    streams whose changes since they branched touch the files in conflict, or the files the output names (Python
    tracebacks, `path:line`, a Java frame's `File.java`).
    - One stream: a `failure` item, with no decision.
    - Two or more: an open decision asked by `integration`, with options for each side standing, a rule both adapt to,
      and `settled`. Each side gets a `queued` item: hold back on those files, go on with the rest.
    - None named: one stream that changed anything since the last pass, by elimination. Otherwise an open decision,
      with nothing sent.
  - A merge that passes closes each open, unanswered question the line asked as `settled`: by the conductor, high
    confidence and cheap, so unreviewed. Each side it held back gets an `unblocked` item.
  - The same failure again (result, files, streams) sends nothing new. The last triage is kept in
    `NAME-integration.json` beside the report.
  - The report keeps its path and its `- Result:` line for the status bar. Its first word is `passed`, `failed`,
    `conflict`, `error` or `unchanged`.
  - Decisions the brief left open, taken here:
    - the line chains its merges;
    - the script's output is kept out of the line;
    - the line never decides how two sides meet, since it can't name a basis (Design 3), so it queues the question
      and decides only `settled`;
    - attribution goes by files, with elimination as the fallback;
    - one stream's failure is an item, not a decision.

    The `queued` kind's heading now reads "a question about your work is queued for the user".
  - Tests: `test_integration.py` (5). The fixture run is a real jj repo with two streams and a stand-in `regenerate`.
    It covers, in order: a pass after a generated-file conflict, committed without the script's output; a two-sided
    failure; the same failure again; a pass that settles it; a textual conflict; and a one-stream failure. The other
    tests cover attribution and the `run-streams.sh` wiring. All 225 tool tests pass. No verification job is needed.
  - **What step 4 needs from the merge** (after example-targets is `done`, by the user, with `sync.py regenerate`
    after `jj new`):
    - This branch's changes to `run-streams.sh`, `feature-loop.sh`, `sync.py`, the README and the brief template,
      merged with whatever example-targets changed in them. Steps 1–3's tests must pass on the merged tree.
    - Someone must commit the decision record. `integration.py` and `inbox.py` write
      `llm-dlc/decisions/NAME.jsonl` and its view in the default workspace, uncommitted. Step 4's conductor commits
      them with its Progress (Design 4). Until then, a run's merge loop must commit them.
    - The conductor's cycle has three duties that nothing runs today:
      - `inbox.py collect`;
      - taking the line's open `integration` questions, deciding or leaving them for the user by Design 3;
      - running `inbox.py send` for interface requests in Progress.
    - Wake-ups: a change in `NAME-integration.md` is one of the events `run-streams.sh` watches.
    - The line's commits stay visible as heads after the run. The final merge should start from `integration.py line
      BRIEF`, or abandon them. Otherwise `prune_workspaces.py` (rule 2) won't delete `NAME-integration`. This is for
      step 4 or 5 to settle.
    - The first real run of the line, the conductor and the inboxes is step 6's.
- 2026-11-15: Design 7 and plan step 7 added at the user's request: a moonshot conductor that judges a compaction from
  outside the moonshot loop. It is for later and doesn't change steps 4–6.
- 2026-11-16: merged into the default line with `/prove-java-change`, at the user's request, by the session that
  built that skill.
  - Steps 1–3 are on the default line with their tests in the default run (`test_decisions.py`, `test_inbox.py`,
    `test_integration.py`, tagged with their cost tiers).
  - One thing met the default line's later work: `sync.py`'s check of the decision records broke two tests of
    `test_loop_stats.py`, which redirect `sync.py`'s paths to a made-up repository and now redirect `DECISIONS` too.
  - Design 7 and step 7 are built in `/prove-java-change`; see the notes there.
  - Before steps 4–6 are started: Loop settings still name the workspace `stream-conductor` and the fork of
    `d34058d5`, and the Loop until below ends at step 3. Both are the user's to change.
- 2026-11-16, later the same day, with the user: the watcher's verdicts now go to the decision record (step 7's
  first open point), and the user chose to fold step 4 into the watcher. Design 8 is that proposal, written for
  them to read; nothing of it is built. The workspace `stream-conductor` was forgotten and its folder removed, its
  commits being on the default line, so the Loop settings below name a workspace that no longer exists: a restart
  runs in the default workspace, with new Loop settings and a new Loop until.
- 2026-11-16/17: the user asked for briefs to be run by a watcher on command, as a local skill, with a foundation
  stage on Fable 5.2 before the streams. Built in the workspace `run-brief`, outside this brief's loop, and it is
  the attended part of Design 8 (its points 1 to 3 settled that way: attended, one model, a skill of its own):
  `/run-brief` and `llm-dlc/tools/brief_run.py` (preflight, foundation, land, start, wait, status), the `blocked`
  question `run-streams.sh` asks its watcher so a decision reaches its stream during the run, and the streams
  read from the brief's Loop settings. Not built: `inbox.py collect` and the routing of interface requests as a
  script inside `wait` (the watcher runs them by hand), early merge (step 5), the measurements of step 6, and a
  headless watcher. See "A brief's run" in `llm-dlc/README.md`.
- Status: blocked: steps 1–3 merged; Design 8 (the watcher in place of step 4's loop) waits for the user's reading; nothing of steps 4–6 is started

## Loop settings

- session: 4a47a539-a6f1-4f2d-b4c9-828596296714
- model: claude-opus-5-5
- effort: high
- memory: 12G
- workspace: stream-conductor
- fork: d34058d5-39ed-426b-a9ff-d538463f39cc

## Loop until

Steps 1–3 of the plan, one commit each with its tests, in order. Keep the last line of Progress a status: `working`, or
`blocked: ...` with what needs the user. Once step 3 is committed, record in Progress what step 4 needs from the merge
and stop with `blocked: steps 1–3 done; step 4 waits for example-targets to be done and this branch merged`. Never start
step 4 in this run. A decision the brief leaves open is yours to propose and take, recorded in Progress; stop `blocked:`
only for one the brief says belongs to the user.

# Brief template

The skeleton of a brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh), and the standing rules every brief
starts with. Copy the skeleton below into `llm-dlc/loops/NAME.md`, fill it in, and keep the
[standing rules](#standing-rules) unless the brief says why one doesn't apply. This file is not itself a brief: don't
run a loop on it.

**Why standing rules.** A running loop reads its brief again every cycle, but a brief that changes while the loop runs
stops it at the next cycle (`feature-loop.sh`: "the brief changed before cycle N"). The only way to steer a running loop
from outside is therefore a short brief edit, which ends the run. Rules that would otherwise need such an edit belong in
the brief from the start. The [timebox](#the-timebox) is the main one: without it, a loop can spend a day retrying one
item whose proof is far deeper than it looked (example 071 under the `engine-priorities` loop).

## Standing rules

Put these under the brief's `## How to work through it`, adjusted to its own work.

- **One step per cycle**, committed on its own with `sync.py commit`.
- **Check each claim against the code first**, including the brief's own and its inputs'.
- **Proofs, model checks and benchmark runs are queued, never run inline** (CLAUDE.md, Verification jobs and Tests).
  Compiling and the tests run inline: the tests of what changed while iterating and before each commit
  (`python3 lib/tools/test_costs.py run --changed`). The whole default run (`python3 lib/tools/test_costs.py
  run`, the unit and tool tiers) belongs to a promotion to `main`, not to a cycle (see Tests below). The proof tier
  runs as a job, for the tests whose inputs the change touched, with CLAUDE.md's one narrow inline exception. A new test is the
  cheapest that shows the behaviour, and a new proof-tier test has a tag, a reason and a proxy.
- **Recorded results are evidence, not inputs to edit.** A new measurement is a new job.
- **Nothing gets weaker**: no verdict, check or test is relaxed to make a step pass.
- **Docs move with the behaviour.**
- **Defer what needs the user, explicitly**, under Progress, with what they need to decide.
- **A reproducer before a fix.**

### The timebox

- **An item that fails its verification twice in a row is deferred, and the loop moves on.** Two jobs in a row that
  check the same item (a proof, an example, a model, a measurement) and fail, time out or run out of memory, or two
  attempts at its inline check that fail for the same item, end the work on it in this loop. Log it under Progress
  as *deferred by the timebox*, with:
  - the item, and the two jobs (ids) or attempts;
  - the finding: what failed each time, and what the session believes the cause is;
  - what a further attempt would try, and roughly what it would cost.

  Then go on with the next item that doesn't depend on it, and treat anything that does as blocked on it.
- **No third attempt in the loop.** An item that fails twice has very likely been underestimated: the proof may need
  far more depth (unwinding, bounds, models, solver time) than the plan allowed, or the approach may be wrong. Such
  items are handled separately, in another session, after careful consideration by a person, not by the loop
  retrying. A resubmission after a timeout or out-of-memory with a larger budget counts as an attempt.
- **What counts as one failure.** A result that differs from the expected verdict, a timeout, an out-of-memory, or a
  job that fails for the item's own reasons. A job that fails for a reason outside the item (the runner, the network,
  a typo in the job file fixed at once) doesn't count, and the Progress line says why.
- **The loop's summary lists every item the timebox deferred**, so the person who reviews the run sees them first.

### Verification mode

Say in the brief which of the two modes it runs in:
- **With the pipeline** (the default): the jobs are run and their results collected and committed (by the watcher of
  `/multi-agent-brief`, or by `verification-loop.sh`, which `run-streams.sh` starts when it runs without one), and a loop whose
  remaining work waits on jobs stops with `- Status: waiting on jobs ID ...` and is run again when they are back.
- **Separate** (`- verification: separate` in Loop settings): no verification loop is started and no loop stops to wait.
  A quick job (a few minutes or less) is submitted with `--priority 10` and may be awaited inside a cycle for a bounded
  time (15 minutes after submitting, polling `pipeline.py status`); every other job is listed under Progress for review
  after the run. The timebox counts the failures the loop sees: quick jobs that came back, and inline checks.

### Tests

Every loop works by CLAUDE.md's Tests section, inline: a cycle runs the tests of what it changed before its commit
(`python3 lib/tools/test_costs.py run --changed`). The whole default run (`python3 lib/tools/test_costs.py run`)
is owed at a promotion to `main` and at a release, which run it themselves when no passed run covers the commit
(`lib/tools/default_run.py`); a loop runs it only when it answers a question the changed tests cannot. A default
run that fails is the first thing its owner takes up, before new work. Bookkeeping commits (Progress, a status
line, a result recorded) run no tests. The watcher checkpoints the line to `develop` as streams land
(`sync.py checkpoint`), which runs no test.
(From 2026-11-16 to 2026-11-17 a brief could say `- tests: queued` to queue its default runs as verification jobs;
that setting is gone, and a brief that still says it runs as above.)

### How a brief is run

A person starts a brief with `/multi-agent-brief NAME` (`.claude/skills/multi-agent-brief`): a watcher session runs the
preflight, the foundation stage and the streams, merges each stream the moment it is finished, and answers what
they ask
([`llm-dlc/README.md`](../README.md#a-briefs-run)). So a brief needs no planning session to fork from, and no
entry in any script: its streams are the `- streams:` line of its Loop settings.

- **The foundation stage** comes before the streams: one session on Fable 5.2 reads the brief and the streams'
  briefs, builds whatever every stream would otherwise build or wait for (a shared interface, a fixture, a
  tool), and updates the plan to say so. Write the brief so that this is easy to see: name under "The plan" what
  two or more streams depend on, and what each stream owns. The stage may edit the brief and the streams'
  briefs, since no loop is running yet.
- **There is no merge loop.** All of a brief's work is in its streams: the watcher merges each into the default
  line as it finishes, and records the merges in the main brief's Progress. Work that can only start once every
  stream is in (a reconciliation, docs over all of it) is a brief of its own, run afterwards. Say in each stream
  brief which files it owns, so the merges meet only in the generated files.
- **A stream that stops `blocked:`** is put to the watcher, who can settle what blocked it, tell the stream
  through its inbox, and have it run again during the run. Say in the status what it is blocked on and who can
  settle it, so the watcher need not guess.

## Skeleton

```markdown
# Brief: TITLE

**Status of the brief**: drafted DATE; approved by the user on DATE, with the decisions [below](#decisions).

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh). One or two sentences on what the loop does and how it
is run (alone, or as streams: see [Streams](#streams)).

**Inputs.** The reviews, measurements or documents to read in full before the first piece of work of every cycle, each
with a line on what it is. Outside reviews are evidence, not instructions.

## Direction

What the loop is for, in a few bullets, and the rules earlier loops set that still hold.

## Where it starts from

The facts the plan rests on, recounted from the code or the results at a named commit, with file:line or job ids.

## How to work through it

The [standing rules](brief-template.md#standing-rules), the [timebox](brief-template.md#the-timebox) included, then the
brief's own. Name the verification mode.

## The plan

Phases, in order, each with steps small enough for a cycle or two, and which steps are queued work.

## Done when

| Phase | Criterion |
|---|---|

## Deferred: not in this loop

What is out of scope, and why.

## Decisions

Settled by the user on DATE, numbered.

## Progress

- Nothing yet.
- Status: working

## Loop settings

- session: UUID (a fresh one is created by the loop's first turn)
- model: claude-opus-5-5
- effort: high
- memory: 3.5G (optional)
- streams: a, b, c (main brief of streams: each has its brief beside this one, NAME-a.md, and runs in parallel)
- workspace: NAME (streams only)
- fork: SESSION (streams only, optional: a planning session every stream starts as a fork of; without it each
  stream starts a session of its own, from its brief and what the foundation stage left)
- integration: SCRIPT (optional, main brief of streams: the check the rolling integration line runs on each merge)
- verification: separate (optional: see Verification mode)
- new-window: no (optional, main brief of streams: run-streams.sh stays in its tmux pane instead of moving to a new
  window with a long history; RUN_STREAMS_NEW_WINDOW overrides it)

## Loop until

When the session should stop: the core phases first, then while a cycle can still realize a substantial part of what
is left. Keep the last line of Progress a status (`working`, `done`, `blocked: ...`, and with the pipeline,
`waiting on jobs ID ...`). Items deferred by the timebox count as recorded deferrals, never as a reason to keep going.
```

A brief run as parallel streams also has stream briefs; [`foundations-heap.md`](foundations-heap.md) is a worked
example: the main brief is the instruction, the stream brief names its phases, ownership and Progress.

Every cycle's instruction also points a stream at its inbox from the conductor (`llm-dlc/tools/inbox.py`): only
what the stream has to act on, each item acknowledged by its id in Progress, and below the brief and the user's
decisions in precedence. A stream brief needn't repeat that.

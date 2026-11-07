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
- **Proofs, model checks and benchmark runs are queued, never run inline** (CLAUDE.md, Verification jobs). Compiling,
  unit tests and conformance cases on a real `java` run inline.
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
- **With the pipeline** (the default): `run-streams.sh` starts `verification-loop.sh`, and a loop whose remaining work
  waits on jobs stops with `- Status: waiting on jobs ID ...` and is run again when they are back.
- **Separate** (`- verification: separate` in Loop settings): no verification loop is started and no loop stops to wait.
  A quick job (a few minutes or less) is submitted with `--priority 10` and may be awaited inside a cycle for a bounded
  time (15 minutes after submitting, polling `pipeline.py status`); every other job is listed under Progress for review
  after the run. The timebox counts the failures the loop sees: quick jobs that came back, and inline checks.

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
- workspace: NAME (streams only)
- fork: SESSION (streams only: the planning session)
- integration: SCRIPT (optional, main brief of streams: the integration check)
- verification: separate (optional: see Verification mode)

## Loop until

When the session should stop: the core phases first, then while a cycle can still realize a substantial part of what
is left. Keep the last line of Progress a status (`working`, `done`, `blocked: ...`, and with the pipeline,
`waiting on jobs ID ...`). Items deferred by the timebox count as recorded deferrals, never as a reason to keep going.
```

A brief run as parallel streams also has stream briefs; [`foundations-heap.md`](foundations-heap.md) is a worked
example: the main brief is the instruction, the stream brief names its phases, ownership and Progress.

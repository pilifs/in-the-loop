# Stream brief: foundations, the relational heap

One of four streams of [`foundations.md`](foundations.md) that run in parallel, each in its own jj workspace on its
own branch. The others are [`foundations-summaries.md`](foundations-summaries.md),
[`foundations-observations.md`](foundations-observations.md) and [`foundations-alignment.md`](foundations-alignment.md).
Once all are finished, a reconcile loop merges them; [Streams](foundations.md#streams) in the main brief says how.

Started with the others by `llm-dlc/tools/run-streams.sh foundations` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh foundations-heap` from this stream's workspace (`jj workspace root --name heap`): the
loop refuses any other.

**The main brief is the instruction.** Read [`foundations.md`](foundations.md) in full every cycle, and its three
inputs too. Its direction, starting point, working rules, deferrals and decisions all apply here. This file says which
part of its plan is yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section;
edit implementation files according to the ownership rules below.

**Every cycle, read the integration check** first: `$(jj workspace root --name default)/llm-dlc/loop-summaries/foundations-integration.md`,
if it exists. A failure in your part of the [integration contract](foundations.md#phase-0-the-shared-ir-and-the-integration-contract)
on the latest combined commits is your next piece of work.

## Your phases

Priority 1: proofs over objects, and between objects of different shapes. In order:

- **H0. Arrays of references**: done by the `engine-priorities` loop (rechecked 2026-11-07): `anewarray`, `aaload`
  and `aastore` over known objects or null. Arrays of references as *parameters* are H2's.
- **H1. Symbolic references.** A reference that may denote one of a finite set of objects, or null, guarded by path
  conditions. `if_acmp`, `ifnull` and `ifnonnull` over such references become formulas; `getfield` and `putfield`
  through one read and write each candidate under its guard. Paths that differ only in a reference merge into one.
  Keep `Val::R` as the fast path: a reference whose target is known stays concrete, and every existing test and verdict
  must hold inline; the benchmark's formula sizes are a job, submitted for review. The aliasing cases among objects a method makes (`aliasedLocals`,
  `aliasedObjects`, `writeThrough`) keep their verdicts; they need no symbolic reference.
- **H2. Object inputs.** A parameter of an application class, within Phase 0's domain: classes allowed, an
  input-object bound, nullability, and which parameters may alias. Made as the main brief's
  [decision 2](foundations.md#decisions) settled: by constructor or factory with symbolic arguments. Every result over such inputs carries the domain's label, "objects made by these constructors or
  factories, under these argument constraints"; it never claims states a constructor doesn't make (an `Account` made
  with `balance = 0` says nothing about one after deposits). Fields of reference type point into the same bounded set.
  The conformance corpus's input cases outside the domain today become its first targets: `twoArrays` with the same
  array twice, and `length` and `lengthOrMinusOne` with a null array, each as the JVM decides it once the domain allows
  aliasing or null. Start with classes whose fields are primitives, primitive arrays, or references to such classes; refuse the rest as
  named gaps. Both versions get corresponding inputs from the same construction, the old version's objects made under
  `before/` as records are today.
- **H3. Heap observations.** At the end of a regression check, compare Phase 0's observations: field paths into the
  result and into each mutable parameter, and identity relations within each version, compared as "holds in old iff
  in new" (`result.left == result.right`; `result == p`). Physical object ids are never compared across versions,
  and internal allocations are not compared at all. Defaults, where no observation spec chooses: the result's reachable
  primitive fields and its identity relations within the bound, and each parameter's fields and identity relations as
  both versions leave them, as array parameters are compared today. An observation spec may choose fewer (a wire
  response observes values only), and the result says which were compared.
- **H4. Witnesses with identity**, required with H2: a witness over objects is a construction recipe that keeps
  aliasing, replayed in the interpreter, run as Java on the JVM (`jvm_witness.rs`), and shrunk (`shrink.rs`) without
  merging or splitting objects. A witness that needs two parameters to be the same object replays with one object.
  H2 and H3 aren't done until their witnesses replay.
- **H5. Correspondence between different shapes.** A regression check where the old and new versions take or return
  different classes, under a Phase 0 correspondence below the preservation contract: the old internal input is made
  from the new one's values through the input equations, the outputs must satisfy the output equations, and the
  preservation contract's external inputs and observations stay as they are. Bounds are per version: input-object
  and allocation bounds can differ where one representation needs more objects (a value object wrapping a primitive).
  A bound that is reached narrows the stated claim or leaves the result unresolved; it never drops an observation.
  Vacuity is checked as for `--before-arguments`. Do first the narrow case the joint example needs, then widen.

**Your core:** H1–H4, and H5's narrow case for the joint example (its correspondence row of the integration contract).
The rest of H5 comes after.

Each phase gets examples from your reserved block: a correct change proved, and siblings with planted defects. The
alias-to-copy defect (an alias turned into a copy with the same primitive values, which a caller sees by mutating
one) is required, and so is a bug only in a state outside the constructor-made domain, which must show as outside the
claim. Tag them from `examples/tags.json`; an `aliasing` or `object-inputs` tag may be needed, added with a
description.

Not yours: the cache key (summaries; it digests the canonical claim, which includes your new domain fields), inferring
correspondences (alignment), entry-point effects and the effect-log hook (observations, through Phase 0's interface).

## Boundaries

You own `lib/src/bmc/`, `lib/src/harness/` apart from Phase 0's effect-log hook, `witness.rs`, `jvm_witness.rs`,
`shrink.rs`, `relocate.rs` and their tests. `lib/models/` is shared with no other stream this time, but a model change
still says under Progress which JBMC results it may change. JBMC need not follow every new capability: where it can't
take an object input, the own checker decides alone and the result says so; `--confirm` refuses rather than
confirming a different claim.

The shared files are the main brief's [list](foundations.md#streams). Name every change to one of them under Progress.

## Working in a stream

- **Commit only here**, with `sync.py commit` as CLAUDE.md says. Never push, merge, rebase onto another branch, or
  move a bookmark. The branch is this workspace's `@-` line; the reconcile loop merges it.
- **Quick jobs are awaited briefly; long jobs never** (the main brief's [rule](foundations.md#how-to-work-through-it)).
  Heavy work is still never run inline: submit it with `verification/pipeline.py submit`, stating the verdict or
  figure it should give, commit it with the change, and list it under Progress with its id. A quick job (a few
  minutes or less) goes in with `--priority 10`, and you may await it within the cycle: work on, then poll
  `python3 "$(jj workspace root --name default)/verification/pipeline.py" status` about once a minute, for at most
  15 minutes after submitting; if it is back, use its `report` like an inline result and record it. Otherwise, and
  for every long job, go on: it is *for review* after the run, and you don't wait for, poll or read it again. A step
  is done when its code, its inline tests and its jobs are committed; a criterion only an unreturned job can show is
  met pending review.
- **The timebox** (the main brief's [rule](foundations.md#how-to-work-through-it)): an item that fails its verification
  twice in a row (two quick jobs that came back, or two inline attempts) is logged under Progress as *deferred by the
  timebox*, with both jobs or attempts, the finding, and what a further attempt would try and cost; then move on to
  work that doesn't depend on it. No third attempt: it has very likely been underestimated, and a person handles it
  separately, in another session. If it is part of your core, your status at the end is `blocked: ...` naming it.
- **Status.** The last line of `## Progress` is a status, kept current in every commit and read by `run-streams.sh`:
  `- Status: working` while there is work you can do, `- Status: done` when your phases are finished, or
  `- Status: blocked: ...` with what needs the user. Never `waiting on jobs`. `done` requires that your part of the
  integration contract passes on this branch and that every job you submitted is listed under Progress; it doesn't
  require any job's result.
- **Another session is not your concern**: the other streams work in their own directories and never touch this
  working copy.
- **Where you started.** Your session is a fork of the conversation that planned the streams (session `ae994066`,
  compacted), so you share its context with the other streams. What it settled is in the briefs; where your memory of
  it and a brief differ, the brief wins.

## Progress

- Nothing yet.
- Status: working

## Loop settings

- session: 750c8a36-92b9-44e3-adad-ef96dc6aa676
- model: claude-opus-5-5
- effort: high
- workspace: heap
- fork: ae994066-d1ea-4620-b03e-176a07061175

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. Your core is above: don't stop before
it unless a step needs the user. When a step's evidence is a long job, submit it and go on; a job is never a reason to stop, and a quick one is awaited only as above. Stop
with `done` when your phases are finished, or `blocked: ...` when what is left needs the user and is recorded under
Progress. Items deferred by the timebox count as recorded deferrals, never as a reason to keep going. Don't go on to polish, and don't start another stream's work.

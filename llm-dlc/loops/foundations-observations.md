# Stream brief: foundations, entry-point observations

One of four streams of [`foundations.md`](foundations.md) that run in parallel, each in its own jj workspace on its
own branch. The others are [`foundations-heap.md`](foundations-heap.md),
[`foundations-summaries.md`](foundations-summaries.md) and [`foundations-alignment.md`](foundations-alignment.md).
Once all are finished, a reconcile loop merges them; [Streams](foundations.md#streams) in the main brief says how.

Started with the others by `llm-dlc/tools/run-streams.sh foundations` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh foundations-observations` from this stream's workspace
(`jj workspace root --name observations`): the loop refuses any other.

**The main brief is the instruction.** Read [`foundations.md`](foundations.md) in full every cycle, and its three
inputs too. Its direction, starting point, working rules, deferrals and decisions all apply here. This file says which
part of its plan is yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section;
edit implementation files according to the ownership rules below.

**Every cycle, read the integration check** first: `$(jj workspace root --name default)/llm-dlc/loop-summaries/foundations-integration.md`,
if it exists. A failure in your part of the [integration contract](foundations.md#phase-0-the-shared-ir-and-the-integration-contract)
on the latest combined commits is your next piece of work.

## Your phases

Priority 3: move checking from methods to what an application's consumers observe. In order:

- **O1. An observation spec per entry point.** From the boundary analysis, for each route, listener and schedule:
  - its inputs: the bound request parts and their wire types, or the message payload. These are the external inputs
    of the entry point's preservation contract, which inference below it can't change;
  - what a consumer observes: the response's wire type, the status for each outcome (from `failures.rs`'s mapping),
    and each effect: `writes` to a store (with the document type), `sends`, `publishes` and outgoing `calls`, each
    with its payload type and its place relative to the transaction;
  - which identity relations count at this boundary (none for a serialized response; for a Java API returning
    mutable objects, the heap stream's defaults);
  - what the analysis can't see, named (a call it couldn't resolve, a dynamic route). An unresolved boundary stays in
    the spec as unresolved; it never vanishes from it.

  As Phase 0's observations, with a stable id per entry point and per observation, from a new command
  (`jvmcontract observations`, `--json`). Box Office is the test bed; every entry point there gets a spec, checked by
  hand against its source once and then by a test.
- **O2. Two builds compared into obligations, accounted for.** Match entry points across two builds (same route and
  verb, same topic or queue, same schedule; a renamed handler is still the same entry point), and for each pair list
  the obligations: each required observation preserved, changed (a status mapping, a payload's shape, an effect moved
  out of the transaction), new or removed, and what a proof of each would need. The accounting is the point: every
  observation of the old build is in the count as preserved, changed with approval, or unresolved. An unchanged
  payload *type* doesn't discharge preservation of payload *values*; it only means the obligation is well formed.
  Static, no proofs. Checked on Box Office examples 110–119, whose recorded boundary diffs are the ground truth.
- **O3. The first obligations discharged.** The contract, deliberately narrow: *the ordered trace of modeled
  boundary-call attempts, with the response and the supported failure outcome, is preserved under an explicit
  environment model.* For an entry point whose handler's decision path is within the own checker's fragment
  (primitive and record inputs today; objects once the heap stream merges), generate the regression check:
  - **Recording stubs.** The store's, broker's and client's methods the spec names are replaced, in both versions, by
    stubs that append to the effect log through Phase 0's hook: the call's kind and target, and a *snapshot* of its
    observed payload values taken at the call, never a reference inspected later.
  - **One environment for both versions.** Corresponding calls receive the same modeled outcome (a return value or a
    failure), chosen symbolically within what the environment model allows. Neither version gets outcomes the other
    doesn't, and "every call succeeds", if chosen, is stated as the model's restriction.
  - **Exact order** first. It may reject harmless reorderings; that is preferable to assuming effects commute.
  - **Bounds visible.** A log that reaches its bound makes the result unresolved, never a shorter trace.
  - **What it means.** A recorded `save` means the application attempted it, not that anything was committed or
    delivered. The stubs and the environment model are named as assumptions, and a witness replayed on the JVM is
    replayed *under the modeled dependencies*, which the result says; it is not a run against real infrastructure.

  Do first the case the joint example needs (its boundary-preservation row): its one entry point and one outgoing
  effect, with a dropped effect and a duplicated one refuted by replayed witnesses. Then, from your reserved block, a
  Box Office or Crosscut entry point refactored correctly and proved, with the same two defects in siblings.

**Your core:** O1, O2, and O3's narrow case for the joint example. The rest of O3 comes after.

Not yours: object inputs (heap; until it merges, refuse entry points that need them, as a named gap), the cache
(summaries), inferring a handler's internal correspondence (alignment). The effect-transition IR, persistence and
delivery semantics and TLA+ from effects are [deferred](foundations.md#deferred-not-in-this-loop): the spec and the
trace here are their inputs, so keep them free of anything proof-engine-specific.

## Boundaries

You own `lib/src/boundaries.rs`, `reach.rs`, `failures.rs`, `wire.rs`, `store.rs`, the new observation module and its
command, the recording stubs and the environment model, the effect-log hook behind Phase 0's interface, and Box
Office's examples and build logic, with their tests. The boundary contract keeps its format: `boundaries.contract`
files and their drift check don't change unless a test shows a bug.

The shared files are the main brief's [list](foundations.md#streams). Name every change to one of them under Progress.
O3's checks go through `equivalence.rs` as a new caller of the existing harness, with effects through the hook; the
rest of `harness/` is the heap stream's. If the hook's interface turns out too narrow, extend it by adding, and say so
under Progress.

## Working in a stream

As in the `engine-priorities` streams ([`engine-priorities-jbmc.md`](engine-priorities-jbmc.md#working-in-a-stream)):
commit only here with `sync.py commit`, never push, merge, rebase or move a bookmark; submit jobs as usual and read
their results from the default workspace's `verification/`; keep the last line of Progress a status. `done` requires
that none of your jobs is pending and that your part of the integration contract passes on this branch. Your session
is a fork of the conversation that planned the streams; where your memory and a brief differ, the brief wins.

## Progress

- Nothing yet.
- Status: working

## Loop settings

- model: claude-opus-5-5
- effort: high
- workspace: observations

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. Your core is above: don't stop before
it unless a step waits on a job or on the user. When everything left waits on jobs, set the status to
`waiting on jobs ID ...` and stop. Stop with `done` when your phases are finished, or `blocked: ...` when what is left
needs the user and is recorded under Progress. Don't go on to polish, and don't start another stream's work.

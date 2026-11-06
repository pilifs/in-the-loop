# Stream brief: foundations, entry-point observations

One of four streams of [`foundations.md`](foundations.md) that run in parallel, each in its own jj workspace on its
own branch. The others are [`foundations-heap.md`](foundations-heap.md),
[`foundations-summaries.md`](foundations-summaries.md) and [`foundations-alignment.md`](foundations-alignment.md).
Once all have stopped, a reconcile loop merges them; [Streams](foundations.md#streams) in the main brief says how.

Started with the others by `llm-dlc/tools/run-streams.sh foundations` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh foundations-observations` from this stream's workspace
(`jj workspace root --name observations`): the loop refuses any other.

**The main brief is the instruction.** Read [`foundations.md`](foundations.md) in full every cycle, and its two inputs
too. Its direction, starting point, working rules, deferrals and decisions all apply here. This file only says which
part of its plan is yours, and keeps your Progress. Don't edit the main brief, another stream's brief, or anything
outside this file's `## Progress` section.

## Your phases

Priority 3: move checking from methods to what an application's consumers observe. In order:

- **O1. An observation spec per entry point.** From the boundary analysis, for each route, listener and schedule:
  - its inputs: the bound request parts and their wire types, or the message payload;
  - what a consumer observes: the response's wire type, the status for each outcome (from `failures.rs`'s mapping),
    and each effect: `writes` to a store (with the document type), `sends`, `publishes` and outgoing `calls`, each
    with its payload type and its place relative to the transaction;
  - what the analysis can't see, named (a call it couldn't resolve, a dynamic route), so the spec says where it is
    incomplete.

  As Phase 0's observations, with a stable id per entry point and per observation, from a new command
  (`jvmcontract observations`, `--json`). Box Office is the test bed; every entry point there gets a spec, checked by
  hand against its source once and then by a test.
- **O2. Two builds compared into obligations.** Match entry points across two builds (same route and verb, same topic
  or queue, same schedule; a renamed handler is still the same entry point), and for each pair list the obligations:
  each observation preserved, changed (a status mapping, a payload's shape, an effect moved out of the transaction),
  new or removed. Static, no proofs: the report is the obligation list a later proof discharges, with what each would
  need. Checked on Box Office examples 110–119, whose recorded boundary diffs are the ground truth.
- **O3. The first obligations discharged.** For an entry point whose handler's decision path is within the own
  checker's fragment (primitive and record inputs today; objects once the heap stream merges), generate the regression
  check that its observations are preserved: the response and its status, and its effects. Effects are observed by
  recording stubs: the store's, broker's and client's methods the spec names are replaced, in both versions, by stubs
  that append the call and its observed payload fields to a log the harness compares. The stubs are named as
  assumptions (the store's and broker's own semantics are not proved). From your reserved block: a Box Office or
  Crosscut entry point refactored correctly and proved, and a sibling that drops or duplicates an effect, refuted
  with a replayed witness.

O1 and O2 are the core. O3 is the bridge to proofs: do the smallest version that discharges one real obligation end
to end, and record what the next version needs.

Not yours: object inputs (heap; until it merges, refuse entry points that need them, as a named gap), the cache
(summaries), inferring a handler's correspondence (alignment). The effect-transition IR and TLA+ from effects are
[deferred](foundations.md#deferred-not-in-this-loop): the spec here is their input, so keep it free of anything
proof-engine-specific.

## Boundaries

You own `lib/src/boundaries.rs`, `reach.rs`, `failures.rs`, `wire.rs`, `store.rs`, the new observation module and its
command, the recording stubs, and Box Office's examples and build logic, with their tests. The boundary contract keeps
its format: `boundaries.contract` files and their drift check don't change unless a test shows a bug.

The shared files are the main brief's [list](foundations.md#streams). Name every change to one of them under Progress.
O3's harness work goes through `equivalence.rs` as a new caller of the existing harness, not a change to it; if the
harness needs a new observation kind, add it to Phase 0's types and say so for the heap stream's owner of
`harness/` to see at the merge.

## Working in a stream

As in the `engine-priorities` streams ([`engine-priorities-jbmc.md`](engine-priorities-jbmc.md#working-in-a-stream)):
commit only here with `sync.py commit`, never push, merge, rebase or move a bookmark; submit jobs as usual and read
their results from the default workspace's `verification/`; keep the last line of Progress a status. Your session is a
fork of the conversation that planned the streams; where your memory and a brief differ, the brief wins.

## Progress

- Nothing yet.
- Status: working

## Loop settings

- model: claude-opus-5-5
- effort: high
- workspace: observations

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. O1 and O2 are the core: don't stop
before them unless a step waits on a job or on the user. When everything left waits on jobs, set the status to
`waiting on jobs ID ...` and stop. Stop with `done` when your phases are finished, or `blocked: ...` when what is left
needs the user and is recorded under Progress. Don't go on to polish, and don't start another stream's work.

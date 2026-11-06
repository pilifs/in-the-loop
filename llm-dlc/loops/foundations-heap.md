# Stream brief: foundations, the relational heap

One of four streams of [`foundations.md`](foundations.md) that run in parallel, each in its own jj workspace on its
own branch. The others are [`foundations-summaries.md`](foundations-summaries.md),
[`foundations-observations.md`](foundations-observations.md) and [`foundations-alignment.md`](foundations-alignment.md).
Once all have stopped, a reconcile loop merges them; [Streams](foundations.md#streams) in the main brief says how.

Started with the others by `llm-dlc/tools/run-streams.sh foundations` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh foundations-heap` from this stream's workspace (`jj workspace root --name heap`): the
loop refuses any other.

**The main brief is the instruction.** Read [`foundations.md`](foundations.md) in full every cycle, and its two inputs
too. Its direction, starting point, working rules, deferrals and decisions all apply here. This file only says which
part of its plan is yours, and keeps your Progress. Don't edit the main brief, another stream's brief, or anything
outside this file's `## Progress` section.

## Your phases

Priority 1: proofs over objects, and between objects of different shapes. In order:

- **H0. Arrays of references**, only if the `engine-priorities` merge left them undone: `anewarray`, `aaload`,
  `aastore` over known objects, with conformance cases checked on the JVM.
- **H1. Symbolic references.** A reference that may denote one of a finite set of objects, or null, guarded by path
  conditions. `if_acmp`, `ifnull` and `ifnonnull` over such references become formulas; `getfield` and `putfield`
  through one read and write each candidate under its guard. Paths that differ only in a reference merge into one.
  Keep `Val::R` as the fast path: a reference whose target is known stays concrete, and every existing test, verdict
  and the benchmark's formula sizes must hold. The aliasing cases of the conformance corpus (`aliasedLocals`,
  `aliasedObjects`, `writeThrough`) get verdicts that match the JVM.
- **H2. Object inputs.** A parameter of an application class, within Phase 0's domain: classes allowed, an object
  bound, nullability, and which parameters may alias. Made as the main brief's [decision 2](foundations.md#open-decisions)
  settles (by constructor with symbolic arguments, unless decided otherwise). Fields of reference type point into the
  same bounded set. Start with classes whose fields are primitives, primitive arrays, or references to such classes;
  refuse the rest as named gaps. Both versions get corresponding inputs: the same construction, with the old version's
  objects made under `before/` as records are today.
- **H3. Heap observations.** At the end of a regression check, compare Phase 0's observations: field paths into the
  result and into each mutable parameter, and alias facts (does the result alias an input?). Defaults: the result's
  reachable primitive fields within the bound, and each parameter's fields as both versions leave them, as array
  parameters are compared today. Internal allocations are never compared by identity.
- **H4. Witnesses with identity.** A witness over objects is a construction recipe that keeps aliasing: replayed in the
  interpreter, run as Java on the JVM (`jvm_witness.rs`), and shrunk (`shrink.rs`) without merging or splitting
  objects. A witness that needs two parameters to be the same object must replay with one object.
- **H5. Correspondence between different shapes.** A regression check where the old and new versions take or return
  different classes, under a Phase 0 correspondence stated by the user: the old input is made from the new one's
  values through the input equations, and the outputs must satisfy the output equations. Vacuity is checked as for
  `--before-arguments`. This is what the alignment stream's field candidates feed.

H1–H3 are the core. Each phase gets examples from your reserved block: a correct change proved and a sibling with a
planted defect (an aliasing bug a test with distinct objects would miss is the model case). Tag them from
`examples/tags.json`; an `aliasing` or `object-inputs` tag may be needed, added with a description.

Not yours: the cache key (summaries; it digests your new domain fields generically), inferring correspondences
(alignment), entry-point effects (observations).

## Boundaries

You own `lib/src/bmc/`, `lib/src/harness/`, `witness.rs`, `jvm_witness.rs`, `shrink.rs`, `relocate.rs` and their tests.
`lib/models/` is shared with no other stream this time, but a model change still says under Progress which JBMC
results it may change. JBMC need not follow every new capability: where it can't take an object input, the own checker
decides alone and the result says so; `--confirm` refuses rather than confirming a different claim.

The shared files are the main brief's [list](foundations.md#streams). Name every change to one of them under Progress.

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
- workspace: heap

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. H1–H3 are the core: don't stop before
them unless a step waits on a job or on the user. When everything left waits on jobs, set the status to
`waiting on jobs ID ...` and stop. Stop with `done` when your phases are finished, or `blocked: ...` when what is left
needs the user and is recorded under Progress. Don't go on to polish, and don't start another stream's work.

# Stream brief: foundations, mapping and alignment inference

One of four streams of [`foundations.md`](foundations.md) that run in parallel, each in its own jj workspace on its
own branch. The others are [`foundations-heap.md`](foundations-heap.md),
[`foundations-summaries.md`](foundations-summaries.md) and [`foundations-observations.md`](foundations-observations.md).
Once all have stopped, a reconcile loop merges them; [Streams](foundations.md#streams) in the main brief says how.

Started with the others by `llm-dlc/tools/run-streams.sh foundations` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh foundations-alignment` from this stream's workspace
(`jj workspace root --name alignment`): the loop refuses any other.

**The main brief is the instruction.** Read [`foundations.md`](foundations.md) in full every cycle, and its two inputs
too. Its direction, starting point, working rules, deferrals and decisions all apply here. This file only says which
part of its plan is yours, and keeps your Progress. Don't edit the main brief, another stream's brief, or anything
outside this file's `## Progress` section.

## Your phases

Priority 4: the tool proposes the relation, and the developer steps in only where intent can't be inferred. In order:

- **A1. The ground truth.** From examples 121–139 (and any other recorded example with `--before-target`,
  `--before-arguments` or `--results-agree-when`), a table of the hand-written mappings: method correspondence,
  argument expressions, record component maps, result relations. Every later phase is scored against it: found,
  found among several (asked), wrong, missed. A wrong mapping that a proof accepts is the worst outcome and is
  counted on its own.
- **A2. Method correspondence.** `jvmcontract align --before DIR --after DIR`: for each changed or vanished method of
  the old build, candidate new methods (same name and descriptor; renamed or moved with the same body shape; a
  changed signature with a similar body and the same callers), ranked, each with its evidence. Written to Phase 0's
  hints file as candidates. Static, no proofs.
- **A3. Argument, record and result mappings.** For a corresponding pair with different signatures, candidate
  `before-arguments` (parameters and record components matched by type, name and data flow into the same uses) and
  candidate result relations from a small catalogue (equal; equal after a widening or a known conversion; a boolean
  against a comparison of the new result). Each candidate is checked by the existing regression proof:
  - one candidate proved and not vacuous: *validated*, recorded with its proof;
  - several proved: ask, listing them; never pick;
  - none proved: report the mappings tried and their counterexamples, so the developer sees whether the change is a
    bug or the mapping is missing.

  The hand-written mappings of A1 are the test: run `align` on each example's builds and score it.
- **A4. Field correspondence candidates.** For classes that changed shape between builds (fields renamed, split,
  merged, wrapped in a value object), candidate field-path equations in Phase 0's correspondence format, from names,
  types and how constructors in each version route their parameters into fields. These feed the heap stream's H5;
  until it merges, score them against hand-made expectations on your own examples.
- **A5. The question, well put.** Where a decision is the developer's, the output says exactly what to decide, with
  the candidates and what each would mean (a counterexample under each, say), and a one-line way to pin the answer in
  the hints file. A run on a pinned hints file asks nothing.

A1–A3 are the core.

Not yours: object inputs and correspondence proofs (heap), the cache (summaries; its claim key covers the mapping, so
a validated mapping's proof is reused there), entry-point matching (observations' O2 matches entry points; you match
methods). Loop and control-flow alignment and LLM-proposed mappings are
[deferred](foundations.md#deferred-not-in-this-loop).

## Boundaries

You own the new alignment module, the `align` command, the hints file's reading and writing, and the scoring tool for
A1, with their tests. You call into `equivalence.rs` to validate candidates as a caller, not by changing how a check
runs. The refusal messages that suggest an expression today (`equivalence.rs:760-808`) may call your inference
instead of their own matching, as a hook.

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
- workspace: alignment

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. A1–A3 are the core: don't stop before
them unless a step waits on a job or on the user. When everything left waits on jobs, set the status to
`waiting on jobs ID ...` and stop. Stop with `done` when your phases are finished, or `blocked: ...` when what is left
needs the user and is recorded under Progress. Don't go on to polish, and don't start another stream's work.

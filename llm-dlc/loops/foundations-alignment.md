# Stream brief: foundations, mapping and alignment inference

One of four streams of [`foundations.md`](foundations.md) that run in parallel, each in its own jj workspace on its
own branch. The others are [`foundations-heap.md`](foundations-heap.md),
[`foundations-summaries.md`](foundations-summaries.md) and [`foundations-observations.md`](foundations-observations.md).
Once all are finished, a reconcile loop merges them; [Streams](foundations.md#streams) in the main brief says how.

Started with the others by `llm-dlc/tools/run-streams.sh foundations` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh foundations-alignment` from this stream's workspace
(`jj workspace root --name alignment`): the loop refuses any other.

**The main brief is the instruction.** Read [`foundations.md`](foundations.md) in full every cycle, and its three
inputs too. Its direction, starting point, working rules, deferrals and decisions all apply here. This file says which
part of its plan is yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section;
edit implementation files according to the ownership rules below.

**Every cycle, read the integration check** first: `$(jj workspace root --name default)/llm-dlc/loop-summaries/foundations-integration.md`,
if it exists. A failure in your part of the [integration contract](foundations.md#phase-0-the-shared-ir-and-the-integration-contract)
on the latest combined commits is your next piece of work.

## Your phases

Priority 4: the tool proposes the internal relation, and the developer steps in only where meaning changes. All of
it works under the comparison's [preservation contract](foundations.md#direction), which inference may never weaken:
it relates internal representations, and leaves the external inputs' meaning, the required observations and the
accepted behaviour as they are. In order:

- **A1. The ground truth.** From examples 121–139 (and any other recorded example with `--before-target`,
  `--before-arguments` or `--results-agree-when`), a table of the hand-written mappings: method correspondence,
  argument expressions, record component maps, result relations. For each, which parts are anchored by something
  external (an unchanged parameter, a field reached from a route) and which are internal. Every later phase is scored
  against it: found, asked about, wrong, missed. A wrong mapping that a proof accepts is the worst outcome and is
  counted on its own.
- **A2. Method correspondence.** `jvmcontract align --before DIR --after DIR`: for each changed or vanished method of
  the old build, candidate new methods (same name and descriptor; renamed or moved with the same body shape; a
  changed signature with a similar body and the same callers), ranked, each with its evidence. Written to Phase 0's
  hints file as proposed, evidence unchecked. Static, no proofs.
- **A3. Argument, record and result mappings, under the contract.** For a corresponding pair with different
  signatures:
  - **What may be inferred.** An anchored input keeps its meaning: for a parameter that both versions take from the
    same external value, the mapping is fixed to that value, and no arithmetic or other transformation of it is
    proposed. Inference proposes only how *internal* representations relate (a parameter split into a record's
    components, a reordering, a widening of a parameter the contract doesn't fix) and result relations only for
    results that aren't required observations. A required observation is compared as the contract says, never under
    an inferred relation. The `price` case of the main brief (`before.c = after.c + 1`) must never be proposed for an
    anchored input; it's a planted defect in your examples, and the test is that no candidate hides it.
  - **Candidates**, from type, name and data flow into the same uses, and a small catalogue of result relations
    (equal; equal after a widening or a known conversion; a boolean against a comparison of the new result), each
    checked by the existing regression proof.
  - **Collapse before asking.** Candidates equivalent under the contract (they give every external input the same
    old-side value; checked by a proof, or by syntax where trivially the same) are one candidate.
  - **The outcome.** One candidate proved and not vacuous: evidence "proved for claim key K", intent still proposed.
    Several after collapsing: ask, listing them and what tells them apart. None: report the mappings tried and their
    counterexamples, so the developer sees whether the change is a bug or the mapping is missing.
  - **No anchor.** For a standalone method with nothing external fixing its inputs, a proved mapping is reported as
    "this relation is proved; whether it is the intended one is unconfirmed", not as an approved refactor.
  - **Accounting.** Every observation the old version is held to stays in the result's count: preserved, changed with
    approval, or unresolved. A mapping can't remove one.

  The hand-written mappings of A1 are the test: run `align` on each example's builds and score it.
- **A4. Field correspondence candidates.** For classes that changed shape between builds (fields renamed, split,
  merged, wrapped in a value object), candidate field-path equations in Phase 0's correspondence format, from names,
  types and how constructors in each version route their parameters into fields. They relate internal state only,
  under the same rules as A3. Do first the case the joint example needs (its automatic-mapping row: a primitive
  amount becoming a value object), checked by the heap stream's H5 through the integration check; then widen.
- **A5. The question, well put.** Where a decision is the developer's, the output says exactly what to decide, with
  the candidates and what each would mean (a counterexample under each, say), and a one-line way to approve one in
  the hints file. Approving sets the intent state only; the evidence state still comes from a proof under the current
  claim key, and goes stale when either version changes. A run on a hints file whose entries are all approved and
  proved asks nothing.

**Your core:** A1–A3, and A4's narrow case for the joint example. The rest of A4, and A5, come after.

Not yours: object inputs and correspondence proofs (heap), the cache (summaries; its claim key covers the mapping, so
a proved mapping's evidence is reused there), entry-point matching (observations' O2 matches entry points; you match
methods), the preservation contract's external part (it comes from the observation spec or the signature, not from
you). Loop and control-flow alignment and LLM-proposed mappings are [deferred](foundations.md#deferred-not-in-this-loop).

## Boundaries

You own the new alignment module, the `align` command, the hints file's reading and writing, and the scoring tool for
A1, with their tests. You call into `equivalence.rs` to check candidates as a caller, not by changing how a check
runs. The refusal messages that suggest an expression today (`equivalence.rs:760-808`) may call your inference
instead of their own matching, as a hook.

The shared files are the main brief's [list](foundations.md#streams). Name every change to one of them under Progress.

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
- workspace: alignment

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. Your core is above: don't stop before
it unless a step waits on a job or on the user. When everything left waits on jobs, set the status to
`waiting on jobs ID ...` and stop. Stop with `done` when your phases are finished, or `blocked: ...` when what is left
needs the user and is recorded under Progress. Don't go on to polish, and don't start another stream's work.

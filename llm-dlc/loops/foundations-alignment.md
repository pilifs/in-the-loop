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

You own `lib/src/spec/align.rs`, your interface in the shared IR, which returns a named `Unsupported` until your
part is done; your checks in `lib/tests/foundations.rs` turn from unsupported to passed as you do it. You also own the new alignment module, the `align` command, the hints file's reading and writing, and the scoring tool for
A1, with their tests. You call into `equivalence.rs` to check candidates as a caller, not by changing how a check
runs. The refusal messages that suggest an expression today (`equivalence.rs:768-810`) may call your inference
instead of their own matching, as a hook.

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

- **A1 done** (2026-11-07): the ground truth, [`examples/tools/alignment/ground-truth.json`](../../examples/tools/alignment/ground-truth.json),
  with its page and scoring rules in [`examples/tools/alignment/README.md`](../../examples/tools/alignment/README.md)
  and its checker `examples/tools/alignment.py` (`check`, `check --signatures`, `render`; tests in
  `test_alignment.py`). All 19 B9 examples 121–139, 85 parts: 50 anchored inputs, 8 internal inputs, 4 methods
  (2 renamed, 2 moved), 4 new inputs left free, 15 results equal, 2 record results by component, 2 changed results
  that are a person's decision; 7 scopes counted as a person's decisions. The parts rebuild each example's flags
  exactly, and both versions' signatures were checked against the compiled classes (`check --signatures`: 0
  problems). No example outside 121–139 has a hand-written mapping. Scoring (found, asked, wrong, missed, and wrong
  and accepted on its own) is defined on the page; its code comes with A2's first output.
- Shared files changed: `examples/README.md` (one line in its tools list).
- Next: A2, `jvmcontract align --before DIR --after DIR`, method correspondence written as hints, scored on the
  four method parts and on the fifteen examples whose method kept its name (where it must propose no other method).
- Status: working

## Loop settings

- session: 11f93b59-b830-4090-8775-33313957ef5c
- model: claude-opus-5-5
- effort: high
- workspace: alignment
- fork: ae994066-d1ea-4620-b03e-176a07061175

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. Your core is above: don't stop before
it unless a step needs the user. When a step's evidence is a long job, submit it and go on; a job is never a reason to stop, and a quick one is awaited only as above. Stop
with `done` when your phases are finished, or `blocked: ...` when what is left needs the user and is recorded under
Progress. Items deferred by the timebox count as recorded deferrals, never as a reason to keep going. Don't go on to polish, and don't start another stream's work.

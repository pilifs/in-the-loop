# Stream brief: foundations, summaries and proof caching

One of four streams of [`foundations.md`](foundations.md) that run in parallel, each in its own jj workspace on its
own branch. The others are [`foundations-heap.md`](foundations-heap.md),
[`foundations-observations.md`](foundations-observations.md) and [`foundations-alignment.md`](foundations-alignment.md).
Once all have stopped, a reconcile loop merges them; [Streams](foundations.md#streams) in the main brief says how.

Started with the others by `llm-dlc/tools/run-streams.sh foundations` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh foundations-summaries` from this stream's workspace
(`jj workspace root --name summaries`): the loop refuses any other.

**The main brief is the instruction.** Read [`foundations.md`](foundations.md) in full every cycle, and its two inputs
too. Its direction, starting point, working rules, deferrals and decisions all apply here. This file only says which
part of its plan is yours, and keeps your Progress. Don't edit the main brief, another stream's brief, or anything
outside this file's `## Progress` section.

## Your phases

Priority 2: make repeated verification cheap without making it weaker. In order:

- **S1. Code closure digests.** For a target in a build, a digest of everything its proof reads: the bytecode of each
  application method it may reach (with `shared.rs`'s `shape`, constant-pool references resolved), the classes whose
  layout or initializers it depends on, and the models it uses. Per method, so that a change names which closures it
  touches. Unit tests: a change outside the closure keeps the digest; a change inside it, in a superclass's field, or in
  a model changes it.
- **S2. The proof cache.** Phase 0's claim key, digested, maps to a stored result in a local directory
  (`--cache DIR`, or as the main brief's [decision 3](foundations.md#open-decisions) settles). A hit returns the stored
  result marked as reused, with the run it came from; a miss proves and stores. Only verified and refuted results are
  stored; a refuted one is stored with its witness, which is replayed again on reuse. Unverifiable is never cached.
  Tests change each part of the key in turn (each version's closure, domain, observations, correspondence, bounds,
  gap mode, contracts, models, JDK, checker configuration, tool version) and each must miss. A key part you can't
  digest yet makes the claim uncacheable, not a hit.
- **S3. Change impact.** `jvmcontract impact --before DIR --after DIR` (or a flag on an existing command): for a set of
  claims (a `build.py` run's, say), which ones a change invalidates and why (which method's digest changed). Checked on
  the recorded examples' own before/after builds: for each, the claims it names are exactly those whose closure
  changed.
- **S4. Callees proved equivalent, shared.** Today a callee is shared in both versions only when its bytecode is
  identical. Extend `shared.rs`: a callee pair whose own equivalence proof is in the cache (or proved first, on demand,
  within the time budget) is replaced by the same stub in both versions, with the callee's proof recorded as an
  assumption with basis `proved` and its claim key. The callee's proof must cover the domain the caller passes it:
  its bounds and domain must contain the caller's, or it isn't used. An example from your reserved block where a
  refactored helper is proved once and its caller then proves fast, and a sibling where the helper's change is
  wrong and the caller's proof finds it.
- **S5. Refinement per callee.** When a counterexample under the stubs doesn't replay, find which stubbed callee's
  approximation was spurious (replay each call against the real callee) and unstub only that one, instead of all.
- **S6. The economics, as a job.** One pipeline job over the recorded B9 and B11 examples: a cold run, then a warm run
  with the cache, then a run after a one-method change to each app. Report CPU time and hit rates per run, and that
  every verdict is the same as cold. `build.py` gets a cache option for this; its recorded results are untouched.

S1–S3 are the core.

Not yours: the shared IR's claim key definition (Phase 0; you implement its digest), object domains (heap), observation
specs (observations).

## Boundaries

You own `lib/src/shared.rs`, `digest.rs`, the new cache module, the `impact` command, and `examples/tools/build.py`'s
cache option, with their tests. `equivalence.rs` and `property.rs` are shared: the cache lookup goes in as one call at
the start of a check and one at the end, nothing more. `build.py`'s existing claim records (`claim_record`,
`attempt_record`) are a starting point for what a key needs; reuse them rather than defining a second notion of
staleness.

The shared files are the main brief's [list](foundations.md#streams). Name every change to one of them under Progress.
The heap and observation streams will add fields to `Statement`'s domain and observations: digest the serialized
`Statement` rather than listing its fields, so their additions are in the key without a change here.

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
- workspace: summaries

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. S1–S3 are the core: don't stop before
them unless a step waits on a job or on the user. When everything left waits on jobs, set the status to
`waiting on jobs ID ...` and stop. Stop with `done` when your phases are finished, or `blocked: ...` when what is left
needs the user and is recorded under Progress. Don't go on to polish, and don't start another stream's work.

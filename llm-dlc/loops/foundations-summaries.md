# Stream brief: foundations, summaries and proof caching

One of four streams of [`foundations.md`](foundations.md) that run in parallel, each in its own jj workspace on its
own branch. The others are [`foundations-heap.md`](foundations-heap.md),
[`foundations-observations.md`](foundations-observations.md) and [`foundations-alignment.md`](foundations-alignment.md).
Once all are finished, a reconcile loop merges them; [Streams](foundations.md#streams) in the main brief says how.

Started with the others by `llm-dlc/tools/run-streams.sh foundations` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh foundations-summaries` from this stream's workspace
(`jj workspace root --name summaries`): the loop refuses any other.

**The main brief is the instruction.** Read [`foundations.md`](foundations.md) in full every cycle, and its three
inputs too. Its direction, starting point, working rules, deferrals and decisions all apply here. This file says which
part of its plan is yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section;
edit implementation files according to the ownership rules below.

**Every cycle, read the integration check** first: `$(jj workspace root --name default)/llm-dlc/loop-summaries/foundations-integration.md`,
if it exists. A failure in your part of the [integration contract](foundations.md#phase-0-the-shared-ir-and-the-integration-contract)
on the latest combined commits is your next piece of work.

## Your phases

Priority 2: make repeated verification cheap without making it weaker. Exact caching shows a rerun is cheap;
reusing a changed helper's proof is what makes refactors cheaper, and both are in your core. In order:

- **S1. Code closure digests.** For a target in a build, a digest of everything its proof reads. `shared.rs`'s `shape`
  is an exact fingerprint of a method's body (checked: constant-pool references and catch types resolved), so start
  from it, and add what lies outside the body: the class hierarchy of every class involved, the set of targets each
  virtual or interface call may dispatch to, field declarations and initializers, the annotations and configuration
  the claim depends on, and the models used. Per method, so that a change names which closures it touches.
- **S2. The proof cache.** Phase 0's canonical claim, digested, maps to a result record in a local directory
  (`--cache DIR`, local and never committed, as the main brief's [decision 3](foundations.md#decisions) settled). The lookup happens on
  the *prepared* claim: after flags, hints, inferred mappings, models and generated observations are resolved, never
  before the claim's meaning is known. A hit returns the stored result marked as an exact reuse, with the run it came
  from; a miss proves and stores. Only verified and refuted results are stored; a refuted one is stored with its
  witness, which is replayed again on reuse. Unverifiable is never cached. The key is a projection of the claim, not
  a digest of the whole `Statement`: result- and run-dependent fields (verdict, vacuity, confirmation, timings, ids,
  reuse provenance) stay out, and a claim field the projection doesn't know makes the claim uncacheable, so that
  another stream's new field can't be silently left out of the key.
- **S2's invalidation tests**, adversarial, each a miss or a refusal to reuse:
  - each part of the canonical claim changed in turn (each version's closure, the preservation contract, domain,
    observations, correspondence, bounds, gap mode, contracts, stubs, environment model, models, JDK, checker
    configuration);
  - a new class that adds a possible dispatch target, with no method body changed;
  - a framework annotation or configuration value the claim uses;
  - the constructor or factory a domain makes its inputs with, or the domain's policy;
  - a recording stub or the observation policy;
  - a change to the assumptions of a callee proof the result reused;
  - the verifier binary rebuilt with no version bump (the key holds the binary's digest).
- **S3. Change impact.** `jvmcontract impact --before DIR --after DIR` (or a flag on an existing command): for a set of
  claims (a `build.py` run's, say), which ones a change invalidates and why (which part of which closure changed).
  Checked on the recorded examples' own before/after builds: for each, the claims it names are exactly those whose
  closure changed.
- **S4. Pure helpers proved equivalent, shared**, narrowly. Today a callee is shared in both versions only when its
  bytecode is identical. Extend `shared.rs` to a deliberately narrow class: a pure, deterministic helper pair, with the
  same parameter and result types, whose own equivalence proof (in the cache, or proved first, on demand, within the
  time budget) shows equal outcomes over its domain, exceptional outcomes included. Such a pair gets the same stub in
  both versions, and the helper's proof is recorded as an assumption with basis `proved` and its claim key.
  - **Applicability at the call site.** The caller's check must show that the actual arguments at each call, in both
    versions, lie in the domain the helper's proof covers: its bounds and its assumptions become assertions at the
    call. Comparing numeric bounds alone is not enough.
  - **Acyclic.** A helper's proof may not rest, directly or through others, on the proof it is used in.
  - Helpers with different representations, or whose outputs are only related rather than equal, stay as written.
  - From your reserved block: a refactored helper proved once and its caller then proving with it, and a sibling where
    the helper's change is wrong and the caller's check finds it. This is your part of the joint example
    (its compositional-reuse row).
- **S5. Refinement per callee.** When a counterexample under the stubs doesn't replay, find which stubbed callee's
  approximation was spurious (replay each call against the real callee) and unstub only that one, instead of all.
- **S6. The economics, as a job.** One pipeline job over the recorded B9 and B11 examples: a cold run, then a warm run
  with the cache, then runs after changes of four kinds to each app: an unrelated edit, a behaviour-preserving helper
  rewrite, a representation change, and a real regression. Report, per run, preparation and hashing time apart from
  solver time, exact hits apart from reused helper evidence, and that every verdict is the one a cold run gives.
  `build.py` gets a cache option for this; its recorded results are untouched.

**Your core:** S1–S4, S4 in its narrow form. S5 and S6 come after.

Not yours: the canonical claim's definition (Phase 0; you implement its projection and digest), object domains (heap),
observation specs (observations).

## Boundaries

You own `lib/src/spec/cache.rs`, your interface in the shared IR, which returns a named `Unsupported` until your
part is done; your checks in `lib/tests/foundations.rs` turn from unsupported to passed as you do it. You also own `lib/src/shared.rs`, `digest.rs`, the new cache module, the `impact` command, and `examples/tools/build.py`'s
cache option, with their tests. `equivalence.rs` and `property.rs` are shared: the cache goes in as one call once the
claim is prepared and one when the result is known, nothing more. `build.py`'s existing claim records
(`claim_record`, `attempt_record`) are a starting point for what a key needs; reuse them rather than defining a second
notion of staleness.

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

- **S1 done** (2026-11-07): code closure digests, `lib/src/closure.rs` (new, this stream's: the first part of the proof
  cache). A target's closure in a build is a map of parts to digests: each application method it may run (by
  resolution, by every dispatch target, lambda bodies, the initializers of the classes involved), each application
  class involved (hierarchy, fields with constants and annotations, annotations), each virtual or interface call's
  set of dispatch targets, and the application files for a closure that touches Spring. `Closure::changes` names the
  parts that differ between two builds, which S3's impact report will print. The JDK, the models and the binary are
  left to the canonical claim's `ToolIdentity`, not repeated per closure.
  - Tests: `lib/tests/summaries.rs` (new), 11 cases on small `javac` builds: a recompile, a changed callee, an
    unrelated class, a constant field, a new overriding subclass with no body changed (the dispatch part changes), a
    subclass that overrides nothing (no change), a changed superclass, a route annotation, configuration in a
    Spring closure only, a missing target, and the case below.
  - **Found and fixed in `shared.rs`'s `shape`**: a dynamic constant was printed by its bootstrap index, not
    resolved, so `case Color.GREEN` against `case Color.BLUE` in a pattern switch gave equal shapes, and
    `shared::identical_closure` called the two versions identical: a regression check could have said "nothing to
    prove" for a changed body. Reproduced first (the last test above failed), then fixed by resolving a dynamic
    constant through its bootstrap entry, recursively. The change only makes more bodies differ, so it can turn an
    identical-closure verdict into a proof, never the reverse. The unit tests (183, the known flaky timing test
    passing on its rerun), `integration.rs` (64) and `foundations.rs` (3) pass.
  - Shared files changed: `lib/src/lib.rs` (`pub mod closure`), `lib/tests/summaries.rs` (new), `lib/README.md` (a
    paragraph on code closures, and the dynamic-constant note in the regression proof's step 3).
- Next: S2, the proof cache on the canonical claim (`spec/cache.rs`'s `key`, `lookup`, `store`), its invalidation
  tests, and the cache's one call each way in `equivalence.rs`.
- Status: working

## Loop settings

- session: be22079e-0c8d-41e4-ace3-12f7f213f1f9
- model: claude-opus-5-5
- effort: high
- workspace: summaries
- fork: ae994066-d1ea-4620-b03e-176a07061175

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. Your core is above: don't stop before
it unless a step needs the user. When a step's evidence is a long job, submit it and go on; a job is never a reason to stop, and a quick one is awaited only as above. Stop
with `done` when your phases are finished, or `blocked: ...` when what is left needs the user and is recorded under
Progress. Items deferred by the timebox count as recorded deferrals, never as a reason to keep going. Don't go on to polish, and don't start another stream's work.

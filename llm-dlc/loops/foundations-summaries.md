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
- **S2 split in two** (2026-11-07): S2a, the key, the cache and the invalidation tests; S2b, the hook in
  `equivalence.rs` with `--cache DIR`. A hit there has to give back a whole `equivalence::Outcome`, and the
  witness and statement types it holds don't deserialize, so the hook is a step of its own.
- **S2a done** (2026-11-07): `spec/cache.rs`'s `key`, `lookup` and `store`.
  - The key is `sha256:` and the SHA-256 of the canonical claim written canonically (object keys sorted), under a
    projection version line. The projection knows every claim field by its path (`cache::KNOWN`). A field it
    doesn't know makes the claim uncacheable rather than being left out of the key, and so does a computed part left
    empty (a closure digest or a tool identity).
  - The cache is `DIR/claims/HH/HEX.json`, holding one `ResultRecord`, written to a temporary file and renamed. It
    stores verified results, and refuted ones only with a witness. Storing an unresolved result is an error. An
    entry that is corrupt, is for another key, or holds something never stored is a miss.
  - New: `closure::version_digest`, a version's code as the closures of its roots, the target and every constructor
    or factory its inputs are made with. Also new is `lib/src/proof_cache.rs`, the tool identity: the running
    executable's bytes, the JDK's whole `release` file, and the models' digest.
  - Tests: 11 more in `lib/tests/summaries.rs` (22 in all).
    - Every leaf and array of a claim with every part filled is changed in turn (60 or more changes, each a
      different key).
    - Each item the brief lists is named, from each version's closure through the binary rebuilt with no version
      bump.
    - The key doesn't depend on field order, and a field the projection doesn't know is refused.
    - A part that was never computed is refused, and the binary identity is the digest of its bytes.
    - In the code: a new dispatch target, the constructor the inputs are made with, a route annotation and a
      configuration value each change the version digest, and an unrelated change doesn't.
    - The cache: a round trip, nothing stored for an unresolved result or a bare refutation, and the misses.
  - Checked that the tests can fail: with `closures` dropped from what the key digests, both claim-wide tests fail.
  - The integration contract's "summaries keys" and "summaries cache" now pass. Unit tests (183), `integration.rs`
    (64) and `foundations.rs` (3) pass too.
  - The golden claims' computed parts are placeholders ("computed by cache::key"). `key` takes them as given
    strings. It can't compute closures without the builds; the caller fills them (S2b).
  - Shared files changed: `lib/src/lib.rs` (`pub mod proof_cache`), `lib/tests/summaries.rs`, and `lib/README.md`
    (a paragraph on the key and the cache).
  - `sync.py check` reports 3 errors, none from this branch: sessions with no manifest, behind the heap, observations
    and alignment streams' commits (`uyqkxslyysrm`, `lslmmpwrvxuz`, `yomwzkpyqppx`). Each manifest lives on its
    stream's branch; the errors clear at the merge.
- **S2b done** (2026-11-07): `equivalence --cache DIR`, in `lib/src/proof_cache.rs` (`Regression`, `Entry`).
  - The hooks in `equivalence.rs`: one lookup once the claim is prepared (after the harness is made and the shared
    callees are planned, before any checker runs), and one store before the last return.
  - The claim is the preservation contract (the target and its parameters, by identity or `--before-arguments`), the
    observations, the flags' correspondence, and the bounds. It also has the statement's assumptions and domain, the
    harness's digest, and each version's closure from the target and every record constructor. The tools carry every
    setting that can change a verdict: gap mode, the contracts' digest, the contract library, max trust, the solver
    record, shrinking, and the JDK.
  - The deadline is left out of the key: it only decides whether a verdict is reached, and an unresolved result is
    never stored.
  - Only `--engine native` is cacheable: under `jbmc` or `auto`, JBMC may decide the claim, and its identity isn't
    in the key yet. Any other engine gets a note, and nothing is stored.
  - A verified hit gives back the stored result and statement, with `Outcome.reuse = Reuse::Exact { key, from }`.
    No checker runs.
  - A refuted hit replays the stored witness in the harness on both versions as they are now, and is a miss if it
    no longer reproduces. A refutation whose witness, as stored, doesn't reproduce in the interpreter is never stored
    (one confirmed only on a JVM, say).
  - The check's own report is stored beside the record (`cache::store_detail`): output, proof line, statement,
    findings, counterexample. Its witness types are mirrored here, since `witness.rs` is the heap stream's.
  - Tests: 5 more in `lib/tests/summaries.rs` (27 in all), with native checks on small `javac` builds.
    - A rerun is an exact hit with the same statement, gap mode and vacuity included.
    - A different after version, unwinding bound, array bound, scope, gap mode, no models, or no shared callees
      each miss.
    - A refuted hit gives back the same counterexample, and a stored witness edited to an input both versions agree on
      is a miss and is proved again.
    - Every argument type reads back from a stored witness. Found by it and fixed: a `null` array argument read back
      as no value.
    - Under `auto`, nothing is stored.
  - Checked that the tests can fail: with the replay of a refuted hit skipped, or the after version's closure fixed,
    the matching test fails.
  - Unit tests (183), `conformance.rs` (9), `integration.rs` (64), `foundations.rs` (3) and `summaries.rs` (27)
    pass. The CLI was run twice on one claim: a miss that stores, then an exact hit.
  - Shared files changed:
    - `lib/src/equivalence.rs`: `Options.cache`, `Outcome.reuse` (with `reuse: None` added to its 7 literals),
      `Confirmed` derives `Deserialize`, and the two calls.
    - `lib/src/statement.rs`: `Deserialize` on the statement's types. `gap_mode` is `skip_deserializing` because
      `GapMode` is the heap stream's; the cache restores it by name. Two `Vec` fields get `default`.
    - `lib/src/main.rs`: `--cache` on `equivalence`.
    - `lib/tests/summaries.rs`, and `lib/README.md` (a paragraph on `--cache`).
    - Own files: `spec/cache.rs` (`lookup_detail`, `store_detail`, and `Reuse::Exact` gains `key`) and
      `proof_cache.rs`.
  - Notes for the reconcile loop:
    - A field another stream adds to `Statement` must deserialize, or be `skip_deserializing`. If not, the merge
      fails to compile, loudly.
    - Another stream's new field on `equivalence::Outcome` goes beside `reuse` in the same literals.
- `sync.py check` after S2b reports 6 errors, none from this branch. Each is a session with no manifest, behind
  another stream's commit:
  - heap: `uyqkxslyysrm`;
  - observations: `lslmmpwrvxuz`, `zmqrplsqzwmm`;
  - alignment: `yomwzkpyqppx`, `prrxuoknonuz`, `szkpqzylrnmv`.

  None of them is an ancestor of `@`. Each manifest lives on its stream's branch, so the errors clear at the merge.
- **S3 done** (2026-11-07): `jvmcontract impact --before DIR --after DIR`, in `lib/src/impact.rs` (new, this
  stream's).
  - The claims come from `--target`, or from a `--claims` file. `build.py`'s `claim.json` and its `--plan` output
    serve as they are, with `previousSymbol` (or `beforeTarget`) for a renamed method.
  - A claim's code is what its cache key digests: the closures of the target and of the canonical constructor of
    each record its inputs are made with (`impact::roots`).
  - Each claim gets one of three verdicts:
    - invalidated, with the parts that differ, or the reason when the target is gone from the second build;
    - unchanged;
    - unresolved, when the first build has no such method.
  - The verdict comes from `closure::digest_of_version` (new, split out of `version_digest`), the function the key
    uses.
  - Tests: 4 more in `lib/tests/summaries.rs` (31 in all).
    - A callee's change names its callers and that one part, and leaves the rest unchanged.
    - A renamed target, a target that is gone, and one not in the first build.
    - A record input's constructor is in the claim's code, though the target never calls it.
    - Claims are read from `build.py`'s records.
  - **Checked on the recorded examples** with `examples/tools/impact_check.py` (new), inline: 15 s of wall time
    with 4 javac processes at once.
    - The examples are the 59 B9 and B11 examples of Crosscut, Quorum and Mica. For each, `impact` was asked about
      every claim of its app between the unpatched build and the build with its patch.
    - The report is judged against the class files, independently of the closure walk:
      - the example's own claim is invalidated;
      - every part named lies in a class whose bytes changed;
      - a claim whose class-level reach (the classes it refers to and their subclasses, transitively) holds no
        changed class is unchanged;
      - "unresolved" only where the first build has no such method.
    - Result: all 59 pass. Over the reports, 170 claims are invalidated, 1123 unchanged and 84 unresolved.
      - The unresolved ones are 147–149 in every Crosscut report: their patches add the `Jitter` class.
      - 15 of the unchanged claims have a changed class in their reach but don't call the changed method. That is
        what method-level closures add over class-level reach.
    - Checked that the rules can fail: with every claim reported unchanged, each example's own claim fails. With
      every claim invalidated, 2216 failures.
  - The unit tests, `conformance.rs`, `integration.rs`, `foundations.rs` and `summaries.rs` (31) pass.
  - Shared files changed:
    - `lib/src/lib.rs` (`pub mod impact`);
    - `lib/src/main.rs` (the `impact` command);
    - `lib/tests/summaries.rs`;
    - `lib/README.md` (a paragraph on `impact`);
    - `examples/tools/impact_check.py` (new).
  - Own file: `closure.rs` (`digest_of_version`).
- `sync.py check` after S3 reports 15 errors, none from this branch's work:
  - 9 sessions with no manifest, behind other streams' commits, none an ancestor of `@`:
    - heap: `uyqkxslyysrm`, `lonuluzqnlmt`, and `uvmurzwkyukn` (a verification record on its branch);
    - observations: `lslmmpwrvxuz`, `zmqrplsqzwmm`, `xstwptusvqsx`;
    - alignment: `yomwzkpyqppx`, `prrxuoknonuz`, `szkpqzylrnmv`.
  - 5 commits from before the fork, ancestors of `@`, point at log `1f2230c9f137` of session `c2bd9df4`:
    `olwyzkwouyln`, `xrkxxnnuwwuq`, `nnqrnknuvslx`, `xpsxzuolnwop`, `kxnqrntnkztt`. Another workspace rewrote them at
    04:44 on 2026-11-07, after S2b, and jj rebased this branch onto the rewrite. The default workspace's manifest of
    `c2bd9df4` lists that log, and this branch's copy, from before the rewrite, doesn't. This branch may not edit
    `llm-dlc/traces/`, so the errors clear at the merge.
- **S4 split in two** (2026-11-07): S4a is the mechanism, its tests and the integration contract's "summaries reuse"
  check. S4b is examples 160 and 161, which need `build.py` to run an example with `--cache`, and a job.
- **S4a done** (2026-11-07): a changed helper proved equivalent, shared in its callers.
  - **Found first:** under `--engine native`, no callee was ever shared. The stub class and the redirected classes
    went only on JBMC's class path, and the own checker proved with every callee as written. For an identical callee
    that costs nothing, since the checker's hashing makes both versions' calls one circuit (example 120's notes say
    so). The cache is native-only, so a proved helper has to be shared under the own checker.
  - **How it is shared.** Under the own checker, the one function is the helper's new version itself. The previous
    version's calls of it are redirected to the new method (`shared::substitute_directory`). The two versions have
    the same outcome on every input and neither has an effect, so the redirected previous version behaves exactly as
    written. The proof is exact: a counterexample is a real one, and no refinement is needed. The memo stub of an
    unchanged callee is still what JBMC would get.
  - **The narrow class** (`shared::plan_with`). The helper:
    - is a static method both versions call, pure in each (no fields, arrays or effects);
    - works over integral values only (a regression proof's comparison doesn't tell `0.0` from `-0.0`);
    - raises no exception of its own, so it can throw only the JVM's `ArithmeticException` (a regression proof
      compares exceptions by class, not message);
    - has no static initializer in its classes, nor in their application superclasses, in either version, since a
      redirected call would initialize the other version's class;
    - is not trivial in both versions.
  - **The proof** (`proof_cache::Helpers`). With `--cache` and `--engine native`, the helper is checked first as a
    check of its own: the same builds and settings, the helper as the target, nothing restricting its inputs. It runs
    within half the caller's time, and the caller's deadline loses what it took. Or the proof is found in the cache
    under that check's key.
    - It is used only if verified, complete, in the cache, and resting on no assumption beyond the checker's own and
      other helpers' proofs.
    - The caller's statement then gains an assumption of kind `callee`, basis `proved`, with the helper proof's key
      as its id. It is in the caller's claim, so the caller's key changes with the helper's proof.
    - If the caller's proof ends up not using it, the assumption is dropped from the result (`keep_used`).
    - A helper that can't be shared is left as written, with a note saying why: refuted (with its counterexample),
      unresolved, no time left, or a cycle.
  - **Applicability at the call site.** Only a proof over every input of the helper's parameter types is used, so
    every call, in either version and with any arguments, is in its domain. The assertion at the call is then
    `true`, and nothing is compared by numeric bounds. A helper proof with a narrower domain (`--unchanged-unless`,
    mapped arguments, a relation between results) is never used, since it would need a real assertion at each call.
  - **Acyclic.** The checks in progress on a thread are a stack, and a helper on it stays as written. No cycle can
    form through the cache either, since a claim's key digests the keys of the helper proofs it rests on.
  - `cache::callee_reuse` plans a subject's check without running it. The integration contract's "summaries reuse
    of shop.Pricing#discount in shop.Pricing#total" now passes, with the fixture's `discount` proved natively. All
    three summaries checks pass.
  - Tests: 5 more in `lib/tests/summaries.rs` (36 in all).
    - A refactored helper is proved once, and is one function in both versions of each of its two callers. The
      second caller finds the proof in the cache. The previous version's calls are redirected, the proof line names
      the claim, and the key is the one a check of the helper alone gets.
    - A helper that rounds up is refuted and stays as written, and its caller's check finds the regression with a
      replayed counterexample.
    - A helper changed only where one caller never calls it is refuted. That caller is proved with it as written,
      and its other caller is refuted.
    - A helper that throws its own exception, and one over `double`, are never offered for proof.
    - Mutually recursive helpers: the helper's stored proof was made with its caller as written.
  - S2b's exact-hit test now finds two cache entries: `Fee.base`, rewritten from `n * 3` to `n + n + n`, is a changed
    helper and is proved first.
  - Checked that the tests can fail:
    - With the cycle check off, the acyclicity test fails: the inner proof rests on the outer one.
    - With a refuted helper proof accepted, both the rounded-up regression and the one above a thousand are
      "verified", and two tests fail.
  - The unit tests (183), `conformance.rs` (9), `integration.rs` (64), `foundations.rs` (3) and `summaries.rs` (36)
    pass.
  - Shared files changed:
    - `lib/src/equivalence.rs`:
      - the plan is made with `shared::plan_with` and `proof_cache::Helpers`;
      - `claim_assumptions` gains the helpers' assumptions; it is now `mut`, and the `stated` closure moved below the
        plan to allow that;
      - the deadline is shortened by the helpers' time;
      - the proof line's sharing clause comes from `shared::sharing`, with the same text as before for unchanged
        callees;
      - the native run's class path gets the redirected previous version, and `shared_used` is set for it;
      - `keep_used` is applied to the final statement.
    - `lib/src/statement.rs`: `AssumptionKind::Callee`, and a sentence in `Basis::Proved`'s doc.
    - `examples/schema/result.schema.json`: the `callee` kind, and the basis description.
    - `lib/tests/summaries.rs`, and `lib/README.md` (a paragraph on proved helpers).
    - Own files: `shared.rs`, `proof_cache.rs` (`Helpers`, `applicable`, `keep_used`, and the keys recorded per
      thread) and `spec/cache.rs` (`callee_reuse`).
  - Note for the reconcile loop: a hook another stream adds to `equivalence.rs` between the harness and the plan,
    and calls `stated` from, has to go below the plan now.
- `sync.py check` after S4a reports 18 errors, none from this branch's work: the 15 listed after S3, and 4 more
  sessions with no manifest, behind other streams' commits that are not ancestors of `@`. They are heap's
  `nmrmkovpnwqy` and `xkutknnpsxmn`, and alignment's `vvtltnmzuwru` and `orvwtmzmlqts`. They clear at the merge.
- **S4b done** (2026-11-07), pending the two quick jobs below: examples 160 and 161, and `build.py`'s cache option.
  S4, and with it this stream's core, is done.
  - **Found first, in S4a, and fixed:** the `callee` assumption's text named the run the helper's proof came from:
    its time and its build directories. The assumption is part of the caller's claim, so two cold runs of the same
    caller on the same code got different keys, against decision 3's portable keys. The text now names the helper's
    claim only, and the run stays in the note and in `Proved.from`. A new test in `lib/tests/summaries.rs` (37 in
    all) checks it: the same builds compiled into other directories, checked a second later into another cache,
    store the same two keys. It failed before the fix, on the assumption's text.
  - **The examples**, on Crosscut's token bucket. Both check `RetryAfter#nanosUntilToken`, which is unchanged, and
    change its helper `TokenBucket.lastAfter`. Example 120 is the case with both helpers unchanged.
    - 160: `now - (now - last) % period` becomes `last + (now - last) / period * period`. The helper's own proof holds
      on every input, so the caller is proved with it as one function in both versions. Expected: verified, with
      `lastAfter` shared. Measured inline when written: 0.19 s for the helper's proof and 0.00 s for the caller's.
      With the helper as written in both versions, the caller's proof takes 1.2 s.
    - 161: `now - now % period` aligns the credit to the clock's grid, which is wrong. The helper's own proof is
      refuted, so it stays as written. The caller's proof, scoped to the module's precondition as in example 132,
      finds the regression, replayed: `nanosUntilToken(tokens=0, lastNanos=1, nowNanos=1, periodNanos=2,
      capacity=1)` was 2 and is 1, so a client told to wait comes back early and is refused again. Expected:
      violation, with no helper shared.
    - Crosscut's 48 tests pass on both patches. Neither patch adds a file to the app, so no other example's claim
      goes stale. The gap scan finds no gap in either.
  - **`build.py`'s cache option.** An example's `approach.cache` adds `--cache build/proof-cache` to its B9 run, a
    directory removed before the run in the patched copy and never kept. The claim's scope gains `proofCache`, only
    when it is set, so the recorded claims are unchanged. The result gains `helpers`, parsed from the tool's notes:
    each changed helper, whether it was shared, and the note. The page says what came of each, and a `callee`
    assumption in the statement paragraph reads as the helper's proof, not as a gap's contract.
    `expected.sharedHelpers` makes the shared helpers part of the expectation, so a run where the helper silently
    stays as written is not "as expected".
  - Tests: 7 more in `examples/tools/test_build.py` (168 in all, passing). They cover:
    - the option, and that a stale cache is gone before the run;
    - the claim's scope, with and without the cache;
    - both kinds of note, parsed and rendered, checked against the result schema;
    - the expectation with `sharedHelpers`;
    - the statement's wording.
  - The unit tests (183), `conformance.rs` (9), `integration.rs` (64), `foundations.rs` (3) and `summaries.rs`
    (37) pass.
  - Jobs, both quick (`--priority 10`):
    - `20261107-053635-example-160-a-changed-refill-helper-prov`: example 160, expected verified as above;
    - `20261107-053635-example-161-a-refill-helper-aligned-to-t`: example 161, expected violation as above.
  - Shared files changed:
    - `lib/tests/summaries.rs`, `lib/README.md` (key portability, and `build.py`'s option);
    - `examples/tags.json` (`proved-helpers`), `examples/README.md` and `examples/index.json` (rendered);
    - `examples/approaches.md` (B9: a changed helper shared on its own proof);
    - `examples/schema/example.schema.json` (`approach.cache`, `expected.sharedHelpers`);
    - `examples/schema/result.schema.json` (`helpers`);
    - `examples/tools/test_build.py`;
    - the examples 160 and 161.
  - Own files: `proof_cache.rs` (the assumption's text) and `build.py`'s cache option.
- The integration check of 05:01 (S3's commit for this stream) didn't run the tests. The merge conflicted in
  `lib/README.md`, which all four streams add to, and in the generated `llm-dlc/` files: `README.md`, `index.json`,
  `traces/README.md` and `traces/metrics.json`. A conflict in a shared file is the reconcile loop's to resolve, so
  nothing in this stream's part failed.
- Next: S5, refinement per callee. The memo stub of an unchanged callee is used on JBMC's class path only, since
  the own checker never stubs (S4a), so S5 is about `--engine jbmc` and `auto`. When a counterexample under the stubs
  doesn't replay, it replays each stubbed call against the real callee, and unstubs only the callees whose stub
  answered differently, instead of all. Its test needs JBMC, so its evidence is a job, or a library test that skips
  without JBMC.
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

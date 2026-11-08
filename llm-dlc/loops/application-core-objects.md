# Stream brief: application core, objects and lifecycle inputs

One of four streams of [`application-core.md`](application-core.md) that run in parallel, each in its own jj
workspace on its own branch. The others are [`application-core-values.md`](application-core-values.md),
[`application-core-environment.md`](application-core-environment.md) and
[`application-core-reuse.md`](application-core-reuse.md). Once all four are finished, the main brief's loop merges
them ([Reconciling](application-core.md#reconciling)).

Started with the others by `llm-dlc/tools/run-streams.sh application-core` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh application-core-objects` from this stream's workspace
(`jj workspace root --name application-core-objects`). The loop refuses any other.

**The main brief is the instruction.** Read [`application-core.md`](application-core.md) and the acceptance contract
[`application-core-acceptance.md`](application-core-acceptance.md) in full every cycle, with their inputs. Their
direction, starting point, working rules, safety rules, deferrals and decisions all apply here. This file says which
items are yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section. Edit
implementation files according to the main brief's [ownership](application-core.md#streams).

**Every cycle, read the integration check first**:
`$(jj workspace root --name default)/llm-dlc/loop-summaries/application-core-integration.md`, if it exists. A failure
in your files on the latest combined commits is your next piece of work, and a conflict in a file you own is a
coordination task: record it under Progress, don't work around it.

## Goal

Check the instance methods developers actually write, with explicit bounded construction and replay. Cover a small
state domain beyond the values right after the constructor.

## Starting evidence

Recounted in the main brief's [Where it starts from](application-core.md#where-it-starts-from). In short:
- `equivalence.rs` takes an instance receiver only when it is a record of primitive components, and refuses ordinary
  non-record receivers;
- `property.rs` refuses non-static targets;
- ordinary constructor-made application parameters already exist. Extend that capability; don't build a second heap
  system.

The documented object inputs flatten primitive constructor leaves and refuse array constructor arguments. Phase 0's
domain-validation audit is the gate. It doesn't license reinterpreting unsupported policies.

## Your items

In order, with acceptance rows O1–O3 of the [contract](application-core-acceptance.md#mandatory-rows).

### O1. One construction path for receivers and parameters (required)

- Use the existing construction semantics to support an ordinary non-null receiver, in both regression
  (`equivalence`, `compare`) and property (`prove`) checks. Keep `this` a named root for field observations and for
  the argument aliases the plan allows. A nullable invocation target, if one is ever modelled, is a property of the
  call site, never a target receiver that is silently nullable.
- Generalize a constructor's leaves from primitives to bounded primitive arrays:
  - keep the array nullability and aliasing choices the plan explicitly allows;
  - keep copies apart between the before and after heaps, without breaking sharing within one version.
- Add only narrow selection machinery: the existing unambiguous constructor, or one explicitly selected
  constructor or factory descriptor.
  - Ambiguous constructors are a named choice, never a guess.
  - A factory must have a supported body, modelled or executable, and its dependencies enter the claim.
  - Broad factory inference is optional.
- Feed the common plan through `equivalence`, `prove` and `compare`. Alignment consumes the new layout through its
  existing thin interface. Don't weaken external anchoring or rewrite alignment.

### O2. Construction, snapshots and replay agree (required)

- Represent construction as a typed bounded DAG with stable node ids. The same node reused at two argument or field
  paths means one object, not two equal copies. A reference choice inside a nested object is supported only where
  the construction recipe can realize it; otherwise it is refused.
- Snapshot these through the existing observation system: receiver mutations, parameter mutations, the relevant
  nested identities, and results. Rebuild exactly those identities on the real JVM.
- Shrinking checks that the new recipe is still legal and still reproduces the same failure.
- Use the values stream's String and list adapter for construction and replay. Don't add separate representations
  of those values to the witness layer.
- Register every constructor, factory, model and setup method used as a claim root, for reuse.

Required negative controls:
- a receiver returned as a copy;
- an array defensively copied before, but leaked after;
- two parameters that were one object becoming distinct;
- unsupported side effects in a constructor;
- a narrower new constructor under an externally anchored input domain.

### O3. A short explicit setup sequence (required, narrow)

- Support a fixed sequence of one or two setup method calls with symbolic arguments, before the target. The
  sequence is selected, bounded and serialized. There is no search over histories and no invariant inference.
- Both versions start from corresponding constructions and get the same logical setup inputs.
  - Setup outcomes and effects are compared when externally visible.
  - Alternatively, an explicitly stated setup-only domain may hide them, and is then never reported as preserving
    the full history.
  - An input one version rejects is never silently dropped from an anchored compatibility claim.
- The witness is the constructor or factory, then the setup calls, then the target call. The claim names that exact
  domain. Zero-step and one-step claims are distinct, and neither result can pass for the other.
- Model it on the existing constructor-only defect pattern (example 195): a defect that is absent right after
  construction becomes reachable after a setup call, and must be refuted with the whole history replayed.

### Optional, after the core

One more unambiguous factory route, or a bounded construction of reference arrays that the values stream needs.

Out of scope: wider inheritance, cycles, arbitrary field-by-field states, deserialization semantics, and unrestricted
sequences of public methods.

## Ownership and cooperation

- **Yours**: the construction and sequence code, `harness/`, `spec/heap.rs`, `equivalence.rs`, `property.rs`, and the
  plumbing for object witnesses, replay and shrinking.
- **Not yours**:
  - values owns `bmc/`, the interpreter's and the models' semantics, and its value adapter;
  - environment owns the effect harness rewriting;
  - reuse owns the cache implementations.

  Apply only the agreed prepared-claim hook in `property.rs`, not a second cache.
- Ask the coordinator, through Progress, for a change to a shared schema or registration file.
- Put your tests in a stream-specific file. Don't edit generated indexes or another stream's fixture variants.
- Example numbers 240–249.

## Acceptance

- O1 and O2 pass for both regression and property checks, with JVM replay and correct identity observations.
- A receiver with a primitive-array constructor is accepted without a hand-written application adapter.
- O3 finds the defect that only a history reaches, and labels its coverage precisely.
- Each of these changes the claim or makes it uncacheable: a construction descriptor, the setup order, a setup
  argument domain, nullability, aliasing, or a bound.
- The combined quote and lifecycle fixtures (Q and H) exercise this stream's real interface.

## Working rules

The main brief's [How to work through it](application-core.md#how-to-work-through-it): the pipeline and the two-failure
timebox. Queue proofs, and record each job's revision and id. When a core item depends on another stream and is
blocked, say so under Progress, and keep it visible through acceptance. Meanwhile, work on independent fixtures.
Never relax the interface to unblock it.

## Progress

- Forked 2026-11-08 after the main brief's [launch prerequisites](application-core.md#launch-prerequisites), Phase 0
  included. No integration report yet at the first cycle.
- 2026-11-08, **O1's first part: an ordinary receiver made by its constructor**, in `equivalence` and `prove`.
  - **What**: `construction::receiver(cp, class)` makes the receiver as an object parameter is made
    (`equivalence::made_of`, no second heap system), named `this`. In `equivalence`, both versions' receivers must
    be made the same way; their fields are compared after the call, and `this` is a new root of the identity
    relations (`harness::Root::Receiver`). In `prove`, the target is called on its receiver (`invokevirtual`), and
    the expressions read `this.f`. The JVM run of a witness and the cache's closure roots (the receiver's
    constructor) come from the existing paths.
  - **Refused by name**: a constructor argument that is an array, a String or a dependency says "the objects
    stream builds it". Several constructors, a superclass and cycles are named boundaries. So are `--nullable this`,
    `--before-arguments`, and a correspondence's equations about an ordinary receiver.
  - **Verified inline** (native, no JBMC): the contract's O1 passes, with the throttle's `allows` verified and
    `one-short` replayed. `tests/application_core_objects.rs` has five tests: a receiver's mutation refuted on
    `field:this` and run on a JVM; a receiver returned as a copy refuted on identity with `this`; properties over
    `this.f`, proved and refuted; the refusals; and the cache, where an exact rerun reuses the proof and an edit of
    the constructor alone misses it. The lib tests and the contracts `heap`, `foundations`, `compare`, `effects`,
    `application_core`, `observations`, `alignment` and `summaries` pass.
  - **Job** `20261108-045000-application-core-objects-o1-lib-tests-in` (pending): `lib/tests/integration.rs`
    (JBMC), and examples 190–196. Their kernels recorded `Quote#quantity` as unresolved for being an instance
    method, so their kernel lines may change, but not their verdicts.
  - **Found: an unsound cache hit, for the reuse stream** (`proof_cache.rs` is its file, so this is a coordination
    item, not fixed here). `Regression::claim` roots each version's closure at a made object's own constructor, not
    at the inner objects' constructors, which the harness calls apart (`RecordType::constructors` lists every one).
    So an edit of an inner class's constructor alone doesn't change the key.
    - **Reproducer**: `tests/application_core_objects.rs`'s `an_inner_objects_constructor_is_part_of_the_cached_claim`,
      ignored until the fix. A rewrite of `get(Wrap w)` over `Wrap(Inner in, int k)` is verified and stored. A
      build whose `Inner(int v)` stores `v + 1` then reuses that `verified`, although it is refuted without the
      cache (`get(new Wrap(new Inner(0), 0))`: before 0, after 1).
    - **Scope**: it predates this wave, and hits any regression check under `--cache` with a nested object input
      (foundations H2).
    - **The likely fix**: root each version at `record.constructors()` in place of the record's own `<init>`, then
      un-ignore the test.
  - **Next**: O1's second part, a constructor's leaves generalized to bounded primitive arrays (keeping a plan's
    nullability and aliasing, and copies apart between versions). Then the plan's selection of a constructor, and
    `--plan` through `equivalence`, `prove` and `compare`.
- 2026-11-08, **O1's plan and O3's setup sequence**, through `equivalence --plan`, `prove --plan` and a planned
  claim (`spec::heap::check`).
  - **What**: `construction::check_plans` accepts the plans a check makes, and `construction::root` makes each root
    by its node's constructor descriptor. That descriptor is the explicit choice among several constructors.
    `construction::setup_calls` gives one or two void calls on the receiver (`harness::Setup`). The regression
    harness calls them in each version before the target. A setup call that throws ends that version's history:
    its exception, in the step's own category, is the outcome compared, so an input one version's setup rejects is
    a difference, not dropped. The property harness skips such a history, as it skips a rejected construction. The
    interpreter replay runs the history. The JVM run comes for free, since it runs the harness. The statement has
    the `setup` assumption and `setupCalls`. A planned claim's result names its label and restrictions. The domain
    gate compares a plan's classes with the claim's.
  - **Refused by name** ("the objects stream builds it", or the values stream's for an adapted value): arrays,
    nullable or shared nodes, factories, dependencies, setup calls that return a value, more than two setup calls,
    and plans whose roots or setup sequences differ between the versions. A plan with a correspondence,
    `--before-*` or `--results-agree-when`, `--nullable` or `--may-alias` is refused too. A claim with setup calls
    runs uncached, with a note. `prove --cache --plan` is refused.
  - **Verified inline** (native, no JBMC). `tests/application_core_objects.rs` adds four tests:
    - O3 on the frozen throttle claims, with only their allocation bound at 1 (see Found). `after-setup` is
      verified constructor-only, labelled so, and refuted after one `take`, with the whole history in the witness
      and run on a JVM. `one-short` is refuted under both claims, `after` verified under both.
    - A plan selecting one of `Window`'s two constructors. Verified and refuted, with a missing constructor and a
      misnamed leaf refused.
    - A setup rejection in one version, refuted on `exception`.
    - `prove` over the states a setup call reaches.
    The lib tests (226) and the suites `heap` (its planned-domain test now checks the plan), `foundations`,
    `compare`, `effects`, `observations`, `alignment`, `summaries`, `conformance` and `skill` pass.
    `application_core` passes except O3, below.
  - **Found, for the coordinator: the frozen throttle claims' allocation bound is wrong.**
    - Both claims say `allocations: 0`, but `allows` and `take` each allocate the `IllegalArgumentException` they
      throw. The gate counts it, so from this commit the contract's O3 is unresolved ("the previous version's code
      may make 1 objects in one call, more than the claim's allocation bound of 0") where `expected.json` says
      verified or refuted.
    - It never showed before, because the plan was refused before the gate. The integration check fails on O3
      until the fixture changes.
    - The fix is the fixture's, not the gate's: bound both claims at 1, or decide in the main brief that a
      thrown exception isn't counted. I changed neither, since a stream doesn't relax a frozen expectation.
    - A related open question: the gate counts the target's allocations only, not the setup calls'.
  - **Interface requests**:
    - reuse: root the setup methods in `proof_cache::Regression::claim`, and read the plan in the property key and
      in `spec::cache::key`, which refuses a planned domain as uncacheable today. Until then, the guards above.
    - coordinator, then reuse: a `setup` field in `witness::Call` and in `proof_cache`'s stored call, so the typed
      witness carries the setup calls. The rendered input and the typed inputs (`setup.0.n`) carry them today.
    - coordinator: a way to give `compare` a plan per subject (`main.rs`). Its kernel passes a planned claim
      through `heap::check_with` as it is.
  - **Coordination**: reuse closed the cache hole of the entry above in `qssovxor` (its branch). Un-ignore
    `an_inner_objects_constructor_is_part_of_the_cached_claim` at the merge.
  - **No job**: the harness changes apply only to a layout with setup calls, which no existing example or JBMC test
    has. The job above, `20261108-045000-…`, still covers the JBMC integration tests and examples 190–196.
  - **Next**: O2. Bounded primitive arrays as constructor leaves (`PlanValue::Array`), kept apart between the
    versions; then nullable and shared nodes; then the five negative controls.
- 2026-11-08, **O1's arrays: a bounded primitive array as a constructor's argument**, with or without a plan, and
  O2's negative control of an array copied before and leaked after.
  - **What**: `harness::is_leaf`, a primitive or an array of integral or boolean elements, is what a construction
    takes as a symbolic leaf. That covers `RecordType::made`, `emit_construct`, the interpreter's `construct` and
    `equivalence::made_of`, so `Buffer(int[] data)` needs no adapter.
    - **The two heaps apart**: the previous version's object is made from the harness's copy of the array, as an
      array parameter's call is. Within a version, the object and the caller share the array the caller passed.
    - **The caller's array**: compared after the call (`array:this.data`), and in the interpreter replay too.
    - **The domain and the bounds**: the domain says `each array of its construction of length ≤ N, not null, and
      no two the same array`. `construction::stated_bounds` states the array bound, which the shared
      `Domain::has_arrays` doesn't see for an array inside an object.
    - **A plan**: its `array` values are roots or constructor arguments. Their `max_length` must equal the check's
      bound, or they are refused by name.
  - **Refused by name**: a null array, one value given at two paths (`check_plans`), and a property's reading of an
    object's array field (`this.data`, `harness/expr.rs`, unchanged).
  - **Verified inline** (native, no JBMC). `tests/application_core_objects.rs` adds three tests:
    - a `Buffer` receiver made with no adapter: `total` rewritten is verified and a defect refuted, run on a JVM. A
      rewrite of `bump`, which writes into the receiver's own array, is verified, so the versions' arrays are apart.
      `prove`'s `size() <= 3` is verified and `total() >= 0` refuted;
    - the leak, refuted on `array:this.data` alone, the receivers' fields agreeing, and replayed on a JVM; `total`
      over the leak is verified;
    - a plan's array leaf, with its bound and a null array refused.
    The lib tests (226) and every inline suite pass, except the contract's O3, which still waits on the fixture
    finding above.
  - **No job**: no example has an application class whose constructor takes a primitive array except the quote
    fixture's `QuoteRequest`, whose String is still refused, so no example's result changes.
  - **Next**: O2. Nullable and shared nodes of a plan (`same_as`, a node at two paths), the identities they make
    rebuilt on the JVM, and the remaining negative controls: two parameters that were one object becoming distinct,
    unsupported side effects in a constructor, and a narrower new constructor under an anchored domain. Then a
    shrinking check of the recipe's legality, and the claim roots. Optional: array fields in property expressions.
- 2026-11-08, **O2's choices and shared nodes of a plan**, and the negative control of two parameters that were
  one object becoming distinct.
  - **What**: a plan's root node may be null (`nullable`), or one of other roots' objects (`same_as`), each a flag
    of the harness made as `--nullable` and `--may-alias` make it (`construction::choices`, `Layout::choose`). One
    node at two roots is one object, always, with no flag: `harness::Choice::always`, set by `Layout::share`, and
    honoured by both harnesses' bytecode and source, `Layout::made` (so the witness, the interpreter replay and the
    JVM run) and the domain (`b: the same object as a`). Both versions' plans must make the same choices, so that
    their identity relations start alike. The claim key covers it through the harness's hash.
  - **Refused by name**: a choice, or a node shared with a root or another argument, inside a nested object (the
    recipe makes an inner object as its constructor's argument; the harness chooses only among the roots); a
    shared node with a choice as well; a `same_as` naming itself or no root's node; a nullable receiver; plans whose
    choices differ between the versions.
  - **Verified inline** (native, no JBMC). Unit tests `a_plans_roots_may_be_null_or_one_object_…` (construction)
    and `a_shared_object_is_the_earlier_roots_object_with_no_flag` (harness). `tests/application_core_objects.rs`
    adds four tests:
    - the negative control: `twice(a, b)` rewritten to keep its first read of `b` is verified over two nodes, and
      refuted over one node and over a `same_as` choice, with `b=the same object as a` in the witness, replayed in
      the interpreter and run on a JVM;
    - `pick` rewritten to hand back `b`: verified over one node, refuted on identity over two;
    - a nullable root: a dropped null check refuted on `a=null`, verified where the root isn't nullable;
    - `prove` over a shared node: `twice` on one cell of 3 returns 10, verified over one node, refuted over two.
    The lib tests (228) and every inline suite pass, except the contract's O3, which still waits on the fixture
    finding of the second entry.
  - **No job**: the harness changes apply only to a plan with a shared node, which no example or JBMC test has.
  - **Next**: O2's remaining negative controls: unsupported side effects in a constructor, and a narrower new
    constructor under an anchored domain. Then a shrinking check of the recipe's legality, and the claim roots.
    Optional: array fields in property expressions.
- 2026-11-08, **the integration check** (05:36, at this stream's `52f2c3e8`) stopped at the merge, on a 4-sided
  conflict in `lib/README.md` and in the generated `llm-dlc/README.md`, `index.json` and `traces/` files.
  - **The README**: this stream's paragraphs (an ordinary receiver, a construction plan and a setup sequence, a
    plan's choices and shared nodes, arrays a constructor takes) were added after the application-core paragraph of
    "The foundations IR", where reuse and, before it moved, values added theirs. This commit moves them, unchanged,
    to the end of "How a regression proof works" (before "How a property proof works"), where no other stream adds.
    Verified: the `skill` suite, which reads the README, passes.
  - **The generated files** are `sync.py`'s, for the merge (every stream's commit regenerates them).
  - **For the merge, not additive**: `lib/README.md`'s Limits still says "Property proofs (`prove`) are still over
    static methods", which O1's receiver makes out of date. A stream takes additions only there, so it waits.
  - **Next**: as the entry above: O2's remaining negative controls (unsupported side effects in a constructor, a
    narrower new constructor under an anchored domain), a shrinking check of the recipe's legality, and the claim
    roots.
- Status: working

## Loop settings

- session: 3ba3cc03-2dbc-4a1f-ac36-a1cc13b778a9
- model: claude-opus-5-5
- effort: high
- memory: 4G
- workspace: application-core-objects
- fork: 3da21514-fe46-49d5-8200-08d3cf89ea17

## Loop until

Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with
`waiting on jobs ID ...`. Stop with `done` when O1–O3 and your share of the combined acceptance pass, or each is
deferred by the timebox with the finding. Stop with `blocked: ...` when what is left needs the user or another stream,
and is recorded under Progress. Optional construction work must not delay the core or grow into a heap project.
Anything new you find goes under Progress, for the main brief's for-review list.

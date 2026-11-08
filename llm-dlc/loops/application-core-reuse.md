# Stream brief: application core, compositional reuse and preparation

One of four streams of [`application-core.md`](application-core.md) that run in parallel, each in its own jj
workspace on its own branch. The others are [`application-core-objects.md`](application-core-objects.md),
[`application-core-values.md`](application-core-values.md) and
[`application-core-environment.md`](application-core-environment.md). Once all four are finished, the main brief's
loop merges them ([Reconciling](application-core.md#reconciling)).

Started with the others by `llm-dlc/tools/run-streams.sh application-core` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh application-core-reuse` from this stream's workspace
(`jj workspace root --name application-core-reuse`). The loop refuses any other.

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

- Extend exact evidence reuse to property proofs.
- Establish the first boundary for reusing a helper that reads the heap.
- Cut repeated preparation where a small measurement finds it.

Faster identical reruns are not cheaper meaningful refactors: don't confuse the two.

## Starting evidence

Recounted in the main brief's [Where it starts from](application-core.md#where-it-starts-from). In short:
- `proof_cache.rs` covers native regression checking and the proofs of changed pure helpers;
- `property.rs` has no cache hook;
- `shared.rs` restricts helpers to pure primitive behaviour, and rejects fields, arrays and general state;
- the cache lookup happens after preparation;
- the verification runner already caches the verifier build by the `lib/` tree: don't build that again.

## Your items

In order, with acceptance rows R1, R2, J3 and J4 of the
[contract](application-core-acceptance.md#mandatory-rows).

### R1. Caching native property results (required)

- Use the existing canonical claim and local proof store, adding a property projection of the claim, not a second
  cache. The projection includes:
  - assumptions, the assertion or law, the throws specification and the old-state semantics;
  - the construction or receiver plan, the domain and every bound;
  - the model and code closure, the checker's configuration, and the semantic dependency proofs.
- The objects stream applies the agreed hook in `property.rs`.
- Validate the claim before the lookup. An unknown semantic field makes the claim uncacheable or unsupported, never
  silently ignored.
- An exact verified hit keeps its stated assurance level. A cached refutation is replayed on the current artifacts
  before it is used. A timeout or unknown is never cached as a proof.
- These must not collide:
  - property and regression claims;
  - constructor-only and setup-sequence claims.

  Include the actual execution and model roots, not only the class of the declared method.

### R2. Reusing read-only heap helpers (required, narrow)

- **One conservative category**: deterministic helpers, total and read-only, over supported receiver fields and
  primitive arguments, with primitive results.
  - Excluded at first: allocation, writes, exceptions the program creates, external calls, unknown dispatch,
    recursion and escaping references.
  - Bounded reads of primitive arrays come only after the field-only case works.
- **A summary names**:
  - the fields it reads and their values in the pre-state;
  - the alias and null relationships it needs;
  - its domain and bounds;
  - the relation between outcomes.

  Prove the restriction to that footprint, never a heuristic list of likely reads. Changes outside the declared
  footprint may be ignored only once the footprint is established.
- **Applicability at the caller** is discharged on the actual pre-call state.
  - An old proof over constructor-made states doesn't cover every later receiver state by default.
  - The summary has to apply to both versions' arguments and state, under the required relation.
  - Any representation adapter is established explicitly, never by redirecting a method of the old layout to code of
    the new.
- **The first case**: receivers of the same shape and equal outcomes. Key an abstraction on every relevant state value
  and alias fact, not on the reference alone. Two calls on one object, before and after a mutation, are different
  inputs unless their whole read footprints agree.
- **Reuse in a real caller**: a changed helper is proved on its own, and its evidence is reused there.
  - Where applicability isn't established, keep the real body, inlined, or return unresolved. Never assume it.
  - Dependency proofs stay acyclic.
  - Refine a spurious abstract witness before reporting it.

Required adversarial cases:
- the helper starts reading an extra field;
- the caller mutates a read field between calls;
- a precondition holds at one call but not the next;
- an alias invalidates a footprint assumption;
- a summary for the constructor domain is offered at a state a history reached.

### R3. One improvement to preparation reuse (a required investigation, implemented only if the evidence calls for it)

- **Measure first**: a small `compare` run with several claims, and an unchanged rerun.
  - Time these apart: compilation, preparing the code and its closure, hashing, generating the harness, solving and
    replay.
  - Look at the existing caches first, the cached verifier builds and the binary and JDK identities included.
  - The measurement is a queued job, like any benchmark.
- **If a repeated stage is material**, cache exactly one immutable product of preparation, keyed by all its inputs:
  a decoded build snapshot, a resolved closure graph or a generated harness, say.
  - Prefer sharing per-build preparation within one `compare` run to a persistent build cache.
  - A change of source, classpath or configuration invalidates it.
  - Never replace the canonical proof key with a timestamp or a source file's name.
- **If no repeated stage is worth it**, deliver the measurement and record why no new preparation cache is justified.
  Don't invent a speed target or start a rewrite of the build system to fill the phase.

### Optional R4. A first local write summary

Only after R1 and R2 pass.
- **The case**: one receiver with a fixed footprint of primitive-field writes, no allocation, no change of identity
  and no external effects.
- **Establish**: the read set, the write set, the frame condition, the state transition on normal and exceptional
  exit, and applicability.
- Apply it only once the alias conditions are discharged, and replay any refutation against the original body.

One correct and defective pair is enough. This is outside the mandatory joint milestone: general summaries of a
mutable heap, abstraction refinement and summary repair stay later work. A bounded slice that fails is a named
finding, not a reason to generalize the engine.

## Ownership and cooperation

- **Yours**: `shared.rs`, `proof_cache.rs`, `spec/cache.rs`, `closure.rs`, `impact.rs`, the preparation-reuse module,
  and limited hooks in `examples/tools/build.py`.
- **Not yours**: don't edit the objects stream's property or equivalence logic directly. Use Phase 0's hooks and the
  construction and model-root interface.
- Register every new semantic field from objects, values and environment in the key projection and its invalidation
  tests. The coordinator owns the shared schemas.
- Don't add JBMC identity or caching for symmetry: native reuse is the required path here.
- Example numbers 270–279.

## Acceptance

- Native property successes and refutations are reused, with correct invalidation and witness replay.
- A changed heap-reading helper's evidence is reused by a caller, not only by its own identical rerun.
- Summary cases that are inapplicable or break a precondition refuse reuse, or are inlined, and reach the right
  result.
- These affect claims as they should: construction history, model outcomes, String and list bounds, and changes to
  the read footprint.
- The small measurement tells apart exact hits, helper evidence and preparation reuse. Costs are reported with and
  without compilation, and a gain in proving alone is never presented as a gain for the whole build.

## Working rules

The main brief's [How to work through it](application-core.md#how-to-work-through-it): the pipeline and the
two-failure timebox. One local cache: no distributed proof service and no general build-cache project. Every earlier
measurement stays as recorded.

## Progress

- Not started. Forks after the main brief's [launch prerequisites](application-core.md#launch-prerequisites),
  Phase 0 included.
- 2026-11-08, **R1, the native property cache**, in `lib/src/reuse.rs`:
  - **The claim**: `reuse::property_claim` keeps property results in the regression store
    (`spec::cache`), under the same digest. It projects:
    - the target's parameters by name and type;
    - the closure of the target and of every constructor its object inputs, its result and its declared
      exceptions are made with, recursively, plus a plan's makers and setup calls;
    - as assumptions: a first one that it is a property claim (`PROPERTY_CLAIM`), then the assumption, the
      assertion, the throws clauses, the meaning of `\old`, the null and alias choices and the construction plan
      whole;
    - the bounds, and the tools with every checker setting.
  - **Every field of `property::Options` is named** in `PROPERTY_OPTIONS`. A field the list doesn't know refuses
    the check under `--cache`, read from the options' `Debug`, so another stream's new field is never silently left
    out of the key. `--engine jbmc` and `auto` are refused too.
  - **Lookup and store**: the lookup comes before anything is prepared. A verified hit gives back the stored outcome
    and statement, marked as reused. A refutation is stored with its harness (the key determines it), and only if
    its witness fails that harness in the interpreter. A refuted hit is used only once its witness fails the stored
    harness again on the current classes; otherwise the check proves again. Nothing unresolved is stored.
  - **Verified inline**: `lib/tests/reuse.rs`, 7 tests: a verified and a refuted exact hit, a stale witness proved
    again, a changed constructor of an input invalidating a proof of an unchanged method (it fails when the
    constructor roots are taken out), a key per assertion, assumption, throws clause, domain, bound, model, gap
    mode, target and plan history (constructor-only and setup are two keys), none for an unrelated change, and no
    key shared with the target's regression claim in one cache. The contract's R1 now reaches `verified`, cold and
    rerun. 230 unit tests, the contract and `summaries.rs` pass.
  - **Interface requests for the merge** (files not this stream's):
    - `property.rs` (objects): `reuse::property_store` should take `&mut Outcome`, so that its note ("stored as
      claim K", or why not) goes in the output; it is on the standard error for now. `property::Outcome` should get
      a `reuse` field (`spec::cache::Reuse`), so that `--json` carries the reuse as data, not only in `output` and
      `proof`.
    - `main.rs` (shared): the doc of `prove --cache` still says "Refused until that stream builds it", and so does
      the comment at the hook in `property::run`.
  - **Next**: J3, registering the streams' new claim fields (a planned domain's plans, a call's model) in
    `spec::cache::KNOWN`, with their invalidation tests. Then R2.
- 2026-11-08, **J3, the key over the streams' new claim parts**, in `lib/src/spec/cache.rs`:
  - **Registered whole, as strict types**: `TYPED` names `domain.made_by.before`, `domain.made_by.after` (a
    construction plan each) and `environment.calls[].model` (a call model). Each is digested whole once it reads back
    exactly as its type of `spec::plans`, which refuses every field and variant it doesn't declare. A field a stream
    adds to one of those types is in the digest with the rest, never left out; one the type doesn't declare, or a
    plan that doesn't read back as written, makes the claim uncacheable by name. Listing the plans' paths one by one
    in `KNOWN` would only repeat the types (a returned object holds a whole plan again).
  - **Verified inline**, `tests/reuse.rs`, 3 tests: the 8 frozen claims each have a key, none shared; 27 changes to
    them each give a key of their own, none an earlier one's: histories (no setup call, a second one, another method
    or argument type, the setup bound alone, another constructor, a factory, a restriction, either version's plan
    alone), model outcomes (one fewer, another exception, a choice or a script for a query, the query's key, the call
    bound, the operation, a model on another call), value bounds and models (a String's length, nullability and
    evidence level, an array's length, a dependency's class, a list's length, element kind and what its model leaves
    out), and a returned object's identity, nullability and plan; an undeclared field in a plan or a model, an
    unknown coupling and an empty setup spelled out are each refused. The contract's J3 now passes on distinct keys,
    not on the refusal. 230 unit tests, the contract, `summaries.rs`, `heap.rs`, `effects.rs` and `foundations.rs`
    pass.
  - **Left for R2**: J3's helper assumptions. A summary's applicability record is not in any claim yet; R2 puts the
    summaries a caller's proof used into its claim, with their keys.
  - **Found, from the objects stream** (their reproducer `an_inner_objects_constructor_is_part_of_the_cached_claim`
    in `tests/application_core_objects.rs`, `#[ignore]`d, on their branch): `proof_cache::Regression::claim` roots each
    version's closure at a made object's own constructor only, not at the constructors of the objects it is made from,
    which the harness calls too. So a build changing only an inner constructor reuses another's `verified`
    (`get(new Wrap(new Inner(0), 0))`: before 0, after 1). It predates this wave, and it is in this stream's file.
  - **Next**: that cache hole, with a reproducer here first (the closure rooted at every constructor the harness
    calls, both versions). Then R2.
- 2026-11-08, **the regression cache's hole closed**, in `lib/src/proof_cache.rs`:
  - **The fix**: `Regression::claim` roots each version's closure at every constructor the harness calls to make
    an input (`RecordType::constructors`, the objects an input is made from included), for the slots of both
    versions and for a previous version's receiver and records, not at the made object's own constructor alone.
  - **The reproducer first**, `tests/reuse.rs`'s
    `an_inner_objects_constructor_in_either_version_is_part_of_a_regression_claim`: `get(new Wrap(new Inner(v), k))`.
    A rewrite of `get` is verified, and an unchanged rerun is an exact hit. Then a build changing only `Inner`'s
    constructor, after and then before, must miss the cache and be refuted. Before the fix the first of those reused
    `verified`. The objects stream's ignored test of the same case should pass at the merge, un-ignored.
  - **Also**: `tests/reuse.rs` compiled into shared directories and removed them first, so tests running side by
    side could remove each other's classes (a key test failed once with no claim). Each build is now compiled once
    per run.
  - **Verified inline**: `tests/reuse.rs` (11, three runs), the 230 unit tests, `application_core` (14), `compare`,
    `effects`, `foundations`, `heap`, `observations` and `summaries` pass. `integration.rs` stays a job's.
  - **Next**: R2, read-only heap helper summaries. First the footprint of a field-only helper, proved rather than
    listed, and its summary as the `spec::plans::Summary` applicability record. Then applicability at the call site,
    the adversarial cases, and reuse in a changed caller, whose claim carries the summaries it used with their keys
    (J3's helper assumptions).
- 2026-11-08, **R2, first part: a read-only helper's footprint, proved, and its summary from a proof of its own**, in
  `lib/src/reuse/footprint.rs` (a submodule of `reuse.rs`, so no shared file changed), `reuse::summarize` and
  `proof_cache::lifted_proof`:
  - **The footprint** (`footprint::footprint`) is established from the bytecode, not listed. The helper is an
    instance method that no application class overrides, with primitive parameters and a primitive result. The only
    reference it may handle is its receiver, loaded only by an `aload_0` that a `getfield` of a primitive field
    consumes at once. Its static callees are walked under the same rules with no reference at all. So its
    `getfield`s are all it reads of the heap, and since it writes nothing, its outcome is a function of those fields'
    values and its arguments. Each exclusion of the brief is refused by name: a write, an allocation, an exception of
    its own, a static field, an external call, a call on an object, an override, recursion, an escaping or other
    reference, and an array. So are a division by anything but a non-zero constant (not total), a switch, and
    floating point.
  - **The explicit representation adapter** (`footprint::lift`): the helper as a static method of a class of its
    own, `quotes/QuoteService$Footprint$fee`. Its parameters are the helper's arguments, then the values of the fields
    either version reads (their union). Its code is the helper's, with each field read replaced by a parameter. It is
    tested against the helper on a real JVM over 560 cases, lifted over one field more than it reads.
  - **The summary** (`reuse::summarize`): the two versions' lifted helpers are proved by a regression check of their
    own, under the caller's cache, engine and bounds, in the proof stack that keeps dependency proofs acyclic. The
    `spec::plans::Summary` names:
    - that proof's claim key;
    - `reads` (`this.feeCents`, `arg0`);
    - the domain: every value of those fields, on any receiver, whatever else it holds;
    - relation `equal`, effects `read-only`, and the helper proofs it rests on.

    No summary is given for a helper whose versions differ (`helper-extra-field`: lifted over the fee and the floor,
    refuted), or for versions that read fields the other's receiver doesn't declare alike (a change of layout, with no
    adapter established).
  - **Verified inline**, in a new `tests/reuse_summaries.rs` (5 tests):
    - `fee` reads `feeCents`, before and after, and the defect also reads `floorCents`;
    - 17 helpers outside the category are each refused in the words of their case;
    - the JVM conformance of the lifting;
    - `fee`'s summary, with its proof verified in the cache, and an exact rerun giving the same summary, nothing new
      stored;
    - the extra read and the layout change have no summary.

    Also passing: the 231 unit tests, `reuse` (11), `application_core` (14), `summaries`, `compare`, `heap`,
    `effects` and `foundations`.
  - **Found, for the claim key**: the lifted proof is of a function positional in the fields' values. Its key doesn't
    name which field is which parameter. That mapping is the summary's `reads`, established again from each version's
    bytecode every time. So a caller's claim has to carry the whole summary, not only its proof's key: that is the
    next part.
  - **The contract's R2 row** still stops at the objects stream's refusal (`construction::receiver`), because it
    checks `fee` through the plain regression entry point. A summary doesn't need that, and isn't that row's path
    until the merge.
  - **Next**: applicability at the call site and reuse in a changed caller. Under `--cache` and the own checker,
    `shared::plan_with` takes, for an instance call on a helper with a summary, a per-version adapter that reads the
    footprint from the actual receiver at each call and calls the new version's lifted helper. That adapter is
    reached through the receiver's own class, since a private field can't be read from another class. The caller's
    claim then carries each summary it used, with its key. After that come the adversarial cases at a caller: a read
    field mutated between two calls, a precondition holding at one call and not the next, an alias, and a
    constructor-domain summary offered at a state a history reached.
- Status: working

## Loop settings

- session: aa238023-596d-49bd-8039-52502ec096fc
- model: claude-opus-5-5
- effort: high
- memory: 4G
- workspace: application-core-reuse
- fork: 3da21514-fe46-49d5-8200-08d3cf89ea17

## Loop until

Go on while an item has a step that needs nothing but your own work. When everything left waits on jobs, stop with
`waiting on jobs ID ...`. Stop with `done` when R1, R2, R3's justified outcome and your share of the combined
acceptance pass, or each is deferred by the timebox with the finding. R4 may be left out without changing that. Stop
with `blocked: ...` when what is left needs the user or another stream, and is recorded under Progress. Anything new
you find goes under Progress, for the main brief's for-review list.

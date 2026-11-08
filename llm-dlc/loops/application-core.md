# Brief: application core, making native change verification useful for ordinary service code

**Drafted 2026-11-07, from an outside plan; its [decisions](#decisions) were settled by the user on 2026-11-08.** It
starts after the [launch prerequisites](#launch-prerequisites), which include Phase 0.

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh). It widens the before/after verification of the
native checker in [four streams run in parallel](#streams), each a loop of its own with a short brief that names its
items:
- **objects**: stateful objects as receivers and inputs;
- **values**: bounded Strings and a short immutable list;
- **environment**: dependencies that return values or fail;
- **reuse**: proof reuse beyond pure primitive helpers.

This brief is the instruction for all four. Its own loop, `llm-dlc/tools/feature-loop.sh application-core` in the
default workspace, merges them once all are finished, then runs the joint acceptance at the merge.

**Inputs.** Read these in full before the first piece of work of every cycle:
- [`application-core-acceptance.md`](application-core-acceptance.md), the acceptance contract. It defines the three
  fixture families and the mandatory rows.
- Your stream brief, if you are a stream.
- [`verification/findings.md`](../../verification/findings.md)'s open entries, read from the default workspace
  (`$(jj workspace root --name default)/verification/findings.md`). An entry in a file you own is context, not an item:
  the cleanup loop or the `/run-verification` agent owns it.
- This brief's [Where it starts from](#where-it-starts-from), recounted against the code.

For background, read the rationale of [`foundations.md`](foundations.md),
[`foundations-review-platform.md`](foundations-review-platform.md) and `lib/solvers/README.md`.

**Where the plan comes from.** An outside review drafted it on 2026-11-07, as a coordinator brief, four stream briefs
and an acceptance matrix. Shared by the user, it was adapted here to this repository's briefs. The review read the
repository on GitHub at `cbf183a`, without building or running anything. It is evidence, not instructions. Current
code and collected job results take precedence over it, and every claim it made was recounted
[below](#where-it-starts-from).

## Direction

- **The product stays the same**: preservation from before to after, under a fixed external contract. This wave makes
  it useful for ordinary bounded Java application code:
  - objects with state;
  - Strings and short lists;
  - dependencies that return values or fail;
  - proof reuse for more than pure primitive helpers.
- **The native engine on CaDiCaL stays the main investment.** Stock JBMC stays optional, for comparison and as a
  fallback where it can check the identical claim. No solver migration, no JBMC fork, no broad external evaluation.
- **Small vertical capabilities.** A type is not supported just because the symbolic executor recognizes it.
  Construction, observation, evidence, cache identity and replay must all agree on what it means.
- **Soundness first.** The rules of [`sound-verdicts.md`](sound-verdicts.md) and
  [`engine-priorities.md`](engine-priorities.md) still hold:
  - the JVM is the semantic reference;
  - only JBMC's `VERIFICATION SUCCESSFUL` is a JBMC proof;
  - an engine that can't decide gives no verdict, never a wrong one.
- **Don't rebuild what exists.** `compare` already composes the foundations' steps, so extend it. Where the cleanup
  loop or later work already delivered something, don't implement it again.

## Where it starts from

Drafted at `wwlnosom` (2026-11-07), while the cleanup streams still ran. Recounted at the merge, at `main`'s
`yzpmxwnx` (commit `08d23149`, 2026-11-08), after the cleanup and stub-reachability loops
([launch prerequisite 2](#launch-prerequisites)). Every row still held there. Only line numbers moved, and they are
the recount's.

| Area | What the code does | Stream |
|---|---|---|
| `compare` | `compare::run` (`lib/src/compare.rs:116`) already composes the observations, the effect check with the cache, alignment's inferred correspondences, and the kernel's heap proof under the cache. Don't rebuild it. | all |
| Receivers in regression checks | Parameters go through `object_of`, which takes records, then constructor-made objects (`equivalence.rs:680–693`). The receiver goes through `record_of` only (876), and anything else is refused: "… is an instance method; a method of a record whose components are primitive is proved on the record's components, otherwise only static methods are" (876). | objects |
| Receivers in property checks | `property.rs:292` refuses every non-static target: "only static methods are supported". | objects |
| The constructor domain | `made_of` and `fields_of` (`equivalence.rs:697–770`) take a class that extends `Object` directly and has one usable constructor, whose arguments are primitives or constructor-made objects. They refuse: arrays and Strings as constructor arguments (729); String fields (770); several constructors (710); superclasses (704, 752); self-reference (697, 748). Null and alias choices are per parameter only (`spec/heap.rs:83` refuses field paths). `lib/README.md:222` documents the fragment. | objects |
| Strings | `bmc/mod.rs:25`: "strings only as opaque objects". Concatenation gives an opaque string (61), and each literal is one opaque interned object (62). `String.length`, `equals` and the like are the gap `jdk-primitive-method`, with no assume form (60). `effects.rs:23` snapshots a String payload only when it is a literal. | values |
| Lists | `lib/models/README.md:30–31` marks the `List.of`/`copyOf` and `ImmutableCollections` models JBMC-only. Native never runs them (`classpath.rs:288–292`, `CHECKER_RUNS` at `models.rs:77`). A `List.of` is the gap `jdk-static-method`, with no verdict. No example kernel uses a list. The Quorum and Mica `Decision` classes and examples 013 and 071 touch them. | values |
| Effects | `effects.rs` records the ordered attempts at modelled boundary calls, snapshots their payloads and replays under stubs (doc 1–35). It refuses a used result: "… uses the result of …: a modeled return value comes after the narrow case" (908). It refuses any outcome but a normal return: "modeled failures come after the narrow case" (421). | environment |
| Shared helpers | `shared.rs` shares only pure functions of primitive arguments (doc 1–3). `pure_closure` (525) rejects fields, statics and arrays (565–566), and floating point (552). | reuse |
| The proof cache | `proof_cache.rs` covers regression (`Regression`, `lookup` at 421) and changed helpers (`Helpers`). Effect and heap checks reach it through `equivalence::run`. `property.rs` doesn't use the cache at all. The lookup comes after the harness is generated and the shared callees are planned (`equivalence.rs:1215–1297`). | reuse |
| The verifier build | `verification/pipeline.py:829–836` already caches the `jvmcontract` binary by `lib/`'s tree hash. Don't rebuild it. | reuse |
| **Checked exceptions in the equivalence harness (VF-015)** | **In scope, for Phase 0** ([decision 7](#decisions)). The equivalence harness's call handlers catch only `harness::EXCEPTIONS` (`lib/src/harness/mod.rs:37`), unchecked exceptions, and then `RuntimeException` and `Error`. A checked exception leaves `EquivalenceHarness.check` uncaught, and JBMC's "no uncaught exception" property fails. So no equivalence over a method that throws one can be verified. The property harness already handles a declared exception (its throws clauses, `harness/mod.rs:2896`). Found by the stub-reachability loop on 2026-11-08: example 109's old `toDigit` throws commons-codec's `DecoderException`, and job `20261108-011411-vf-015-…` failed at step 5. Deferred there by the timebox as VF-015's second failure. Its step 4 passed only because `test $? -eq 1` also accepts "cannot be verified". | Phase 0 |
| **Domain options nobody reads** | **A hole for Phase 0.** `ObjectDomain` (`spec/mod.rs:97–137`) has `classes`, `bounds`, `nullable`, `may_alias`, `made_by` (`Constructors{calls}`, `FieldByField`, `Invariant`) and `label`. `heap::check_with` enforces `nullable` and `may_alias`, refusing field paths (`spec/heap.rs:83`), and both bounds, `input_objects` and (since the cleanup loop) `allocations` (`spec/heap.rs:116–135`), after the check runs, as an unresolved result. It never reads `made_by` (any variant, and `calls`), `classes` or `label`, which only the cache key projects (`spec/cache.rs:69–84`). So a claim with `made_by: FieldByField` or `Invariant`, or with `calls` naming other constructors, runs as the constructor domain the check happens to make. It is latent, because no production path fills an `ObjectDomain` yet: `Statement.spec` is always `None` (`statement.rs:50–52`), `compare` passes `domain: None`, and only tests build one. This wave starts filling it, so Phase 0 makes every unread option enforced or refused before a verdict. | Phase 0 |

**Fixtures to extend**, per the [acceptance contract](application-core-acceptance.md#small-fixture-families):
- **Q, the quote service**: `examples/apps/shop` (`Pricing`, `Quote`, `QuoteEvent`, `QuotesController`), the fixtures
  `lib/tests/fixtures/foundations/` with their defects, examples 190–196, and `lib/tests/compare.rs`.
- **H, the lifecycle**: `TokenBucket` and `RetryAfter` in `examples/apps/crosscut/…/ratelimit/` (examples 031, 120,
  132, 133, 160 and 161), and `Throttle` (150–152). Their cleanup entries (VF-017, VF-016) are closed at the merge.
- **L, the list**: no kernel exists yet. Phase 0 writes its skeleton.

**What the cleanup run left.** It merged and closed most of its entries. Four stay open:
- VF-002 (examples 147–149, blocked in `build.py`);
- VF-015 (in scope here: [decision 7](#decisions));
- VF-018 (JBMC timeouts, deferred to the user);
- VF-020 (a large `changes.diff` jj won't snapshot).

None but VF-015 is in this loop's files. Both the foundations and the cleanup integration checks reported merge
conflicts while their streams ran. That is why this brief gives shared files a [single writer](#streams).

## How to work through it

The [standing rules](brief-template.md#standing-rules) apply, the [timebox](brief-template.md#the-timebox) included:
- one step per cycle, committed on its own with `sync.py commit`;
- check each claim against the code first, this brief's and the outside review's included;
- proofs, model checks and benchmark runs are queued, never run inline;
- recorded results are evidence, not inputs to edit;
- nothing gets weaker;
- docs move with the behaviour;
- defer what needs the user, explicitly;
- **a reproducer before a fix**.

Compiling, unit tests and small conformance cases on a real `java` run inline.

In addition:
- **Verification runs with the pipeline**, as in cleanup ([decision 2](#decisions)). `run-streams.sh` starts
  `verification-loop.sh` in the default workspace, and it runs the jobs every workspace commits.
  - Each job's description names:
    - the exact revision and the acceptance row it serves;
    - the expected verdict and the expected process status;
    - the domain, the engine and the bounds.

    `matchesExpected`, the job's success and the proof's verdict are three different things.
  - Commit the job with the change: `(verification pending)` on the summary line, the job id in a paragraph.
  - Go on with any item that doesn't depend on the job.
  - When everything left waits on jobs, end Progress with `- Status: waiting on jobs ID ...`. Read the results with
    `python3 "$(jj workspace root --name default)/verification/pipeline.py" report ID ...`.
- **The timebox** applies to substantive items:
  - Two failures in a row on one item end it in this loop, logged as *deferred by the timebox*, with both jobs, the
    finding, and what a further attempt would try and cost. There is no third attempt.
  - A failure of the infrastructure is recorded apart, as the template says.
  - A required item deferred by the timebox blocks its acceptance row: the row is not done. An optional item may be
    deferred without blocking the core work.
- **Every capability comes with four things**:
  - a correct case;
  - a planted defect;
  - a named unsupported boundary;
  - tests that its cached evidence is invalidated.

  Correctness across the boundary between the JVM and a model is required. Sampled conformance is never relabelled
  a proof of a model.
- **No new allow-list entry or relaxed expectation** just to pass.
- **A stream never pushes, merges, rebases, or moves another workspace's bookmark.**

## Safety and semantic rules

- **The external contract on inputs and observations is kept.** Inference can't repair a regression by changing what
  inputs mean, or by removing observations.
- **Intent and evidence stay apart.** Approved doesn't mean proved, and cached evidence is tied to its exact claim.
- **Domains are claims of their own.**
  - Constructor-made and setup-sequence domains are different claims.
  - A bounded prefix is not all reachable states, nor an inductive invariant.
  - Under an externally anchored compatibility claim, a new constructor that rejects an input the old one accepted
    must not vanish into the intersection of the two domains. Check admission separately, or report the narrowed
    claim explicitly as unresolved preservation.
- **Bounds are visible.**
  - String, sequence, allocation, environment-call and history bounds are part of the claim key.
  - Overflow gives an unresolved or bounded result, as the contract states, never truncation under a stronger claim.
- **Replays are faithful.**
  - A replay keeps identity, the modelled dependency choices and every compared observation.
  - Shrinking replays a candidate before accepting it.
- **Summaries need applicability at the actual call site.** A proof over constructor-made receivers doesn't cover a
  receiver after mutation.
- **Every new model records its evidence level**: implemented, modelled, tested, trusted or proved.
- **JBMC doesn't need every native feature.** `--confirm` refuses a claim it can't check identically.

## Launch prerequisites

The planning session is `3da21514-fe46-49d5-8200-08d3cf89ea17`, the conversation that adapted this brief in the default
workspace. The streams fork from it, so Phase 0 is its work, done before any fork.

1. **The cleanup loop merged** (done: merged and pushed 2026-11-07). Its reconcile is committed, with its for-review
   list. Its required native checks on safety, replay and schema pass at the merge.
   - A JBMC-only timeout it defers (VF-018) doesn't block native feature work.
   - That deferral never licenses weakening a cleanup test, or claiming confirmation.
2. **The baseline recounted at the merge.**
   - Update [Where it starts from](#where-it-starts-from) at the merge commit.
   - Run the small integration contracts inline (`lib/tests/foundations.rs`, `compare.rs`, `effects.rs`).
   - Name the collected example results that hold at that revision. Use the exact revision's evidence where it
     applies, and launch no broad benchmark just to start.
3. **Phase 0** ([below](#phase-0-thin-interfaces-not-a-rewrite)), committed.
4. **The names** (done 2026-11-07):
   - `application-core` and `application-core-STREAM` in `feature-loop.sh`;
   - `application-core` with its four streams in `run-streams.sh`;
   - the integration check `llm-dlc/tools/application-core-integration.sh`.
5. **This brief, its four stream briefs and the acceptance contract committed** (done 2026-11-07), with the session
   ids in their Loop settings, and the [decisions](#decisions) settled by the user (done 2026-11-08).
6. **Push**, at the user's request.
7. **Set this brief's status to `working`.** `run-streams.sh` doesn't run a loop whose status is `done` or `blocked`.
   Then **close the planning session**. The user then runs
   `FEATURE_LOOP_MEMORY_MAX=4G CARGO_BUILD_JOBS=8 llm-dlc/tools/run-streams.sh application-core` from the default
   workspace, in a tmux pane with a long history. It compacts the planning session once, before the forks.

## Phase 0: thin interfaces, not a rewrite

Done by the planning session after the cleanup merge, before the fork. It extends the existing `spec`, harness and
cache structures, and is no competing specification system. The names below are conceptual: follow the code's.

| Interface | Least it means | Producer, then consumers |
|---|---|---|
| A validated construction plan | Typed leaves, bounded arrays, constructor or factory descriptors, shared node identities, the receiver root, an optional short setup sequence, and explicit restrictions on the supported domain | objects; then values, environment and reuse |
| A value and snapshot adapter | Generate a value, compare or snapshot it, encode it in a witness and replay it. Each implementation declares its bounds and semantic evidence. | values; then objects and environment |
| An environment outcome plan | A stable id for the modelled operation, the argument key, the occurrence policy, the permitted results or exceptions, the bound, and the coupling rule | environment; then the cache and replay |
| A summary applicability record | The pre-state and read footprint required, alias facts, the domain and bounds, the relation between outcomes, restrictions on effects, and the keys of dependency proofs | reuse; then the checker and claim reporting |

The construction plan is a bounded DAG, not an arbitrary heap allocator. Shared nodes express aliasing, and cycles
stay unsupported. A setup sequence is selected and bounded, not an inference of every reachable state.

The steps, each committed:
1. **The domain gate.** Every option of the claim's domain is enforced, or refused before proof and cache lookup,
   with a reproducer first.
   - Today `made_by` (its kind and `calls`), `classes` and `label` are read by nothing
     ([above](#where-it-starts-from)). `calls` and `classes` can only be checked against the constructors the check
     actually makes its inputs with, which `equivalence::run` knows once its harness layout is built. So the check
     reports them, and `check_with` compares them before any verdict. `label` is the claim's own words: the result
     states the check's domain, and the claim key covers the label.
   - An unsupported `made_by`, field-by-field or invariant policy, factory choice, class, alias or allocation policy
     can never fall back to the constructor domain.
   - Don't redo what cleanup fixed.
2. **The four interfaces** as types in `spec/`, with serialization tests and strict tests for unknown fields and
   variants. A capability not yet implemented returns a named unsupported result.
3. **The hooks in shared files**: small dispatch and call sites in `spec/mod.rs`, `statement.rs`, `main.rs`, `lib.rs`,
   `equivalence.rs` and `property.rs`.
   - Each stream gets a module of its own, already registered, so that it needn't edit a shared file to begin. They
     are `lib/src/construction.rs`, `values.rs`, `environment.rs` and `reuse.rs`, or the code's own names.
   - Extract only the seams that keep writers apart. Don't rewrite the big checker or harness modules.
4. **The integration contract**, `lib/tests/application_core.rs`, run by the integration check. One test per row of
   the [acceptance contract](application-core-acceptance.md#mandatory-rows) that a unit-level run can reach. Each
   asserts its final verdict, or the named unsupported result its stream hasn't replaced yet. Anything else fails.
5. **The fixture skeletons** of Q, H and L, frozen: the before and after Java and the defective siblings, with the
   claim projections they are checked under. Their semantics are fixed now, not after seeing which proof succeeds.
6. **The JSON schemas** a stream will need (`examples/schema/`), with the new kinds added as named variants.
7. **Checked exceptions in the equivalence harness, closing VF-015** ([decision 7](#decisions)).
   - **The reproducer first**: a unit test in `harness/`'s tests, failing before. An equivalence over a method that
     throws a checked exception gives "cannot be verified" today, and should give a verdict.
   - **The fix**: the call handlers catch the exceptions the two versions declare (a handler for each class in either
     version's `throws` clause, most specific first), then `java.lang.Exception`, as the property harness handles a
     declared exception. An exception thrown is part of the outcome the two versions are compared on, by class.
   - **Nothing gets weaker**: a checked exception that only one version throws, or that the two throw on different
     inputs, is a difference, refuted with a replayed witness.
   - **The check**, as a job: VF-015's job resubmitted with its steps unchanged except step 4. Step 4 checks that the
     change is found (the result names a violation, and the witness replays) instead of `test $? -eq 1`, which also
     accepts "cannot be verified". The result is stricter, as VF-015's triage asks. The title names "closes VF-015
     when it passes". Expected: step 3 proved, step 4 refuted with a Unicode digit (`ch > 127`), step 5 verified.
   - The environment stream's E2 (modelled failures, their catch and propagation) builds on this. A modelled
     exception may be checked.

## Streams

| Loop | Brief | jj workspace | Rows | Owns |
|---|---|---|---|---|
| `application-core-objects` | [`application-core-objects.md`](application-core-objects.md) | `application-core-objects` | O1–O3 | the construction and sequence module, `harness/`, `spec/heap.rs`, `equivalence.rs`, `property.rs`, the plumbing of object witnesses, replay and shrinking |
| `application-core-values` | [`application-core-values.md`](application-core-values.md) | `application-core-values` | V1–V3 | the values module, `bmc/`, the semantics of `interp/`, `lib/models/` and `models.rs`, its model conformance tests |
| `application-core-environment` | [`application-core-environment.md`](application-core-environment.md) | `application-core-environment` | E1–E3 | the environment module, `effects.rs`, `spec/observe.rs`, the observation-boundary changes its cases need |
| `application-core-reuse` | [`application-core-reuse.md`](application-core-reuse.md) | `application-core-reuse` | R1–R3, J3, J4 | the reuse module, `shared.rs`, `proof_cache.rs`, `spec/cache.rs`, `closure.rs`, `impact.rs`, limited hooks in `build.py` |
| `application-core` | this brief | `default` | G0, J1, J2 | the merge, and the joint acceptance at the merge |

**Workspace names** are the brief's own, `application-core-STREAM`, at `../in-the-loop-application-core-STREAM`.
`run-streams.sh` stops before compacting anything if a directory is already taken.

**Shared files have one writer** ([decision 3](#decisions)). The planning session writes:
- `spec/mod.rs`, `statement.rs`, `main.rs`, `lib.rs` and `Cargo.toml`;
- the shared JSON schemas, the launcher, the generated indexes and the integration fixtures.

It writes them in Phase 0, with each stream's hooks in place. While the streams run, no stream edits them. A stream
that needs a change records an interface request under its Progress, and works on what doesn't depend on it:
- a request that is purely additive (one new variant, option or registration line) may go in a block marked with the
  stream's name;
- anything else waits for the main loop's merge.

`lib/README.md`, `examples/tags.json` and `examples/README.md` take additions only. Each stream's tests are in files
of its own. A stream never edits another owner's implementation files.

**Example numbers**, after cleanup's 197–229:
- this brief and Phase 0: 230–239;
- objects 240–249;
- values 250–259;
- environment 260–269;
- reuse 270–279.

**Memory.** Four streams at 4 GB each (`- memory: 4G`, and `FEATURE_LOOP_MEMORY_MAX=4G` on the command line) plus the
integration check's 3.5 GB scope come to 19.5 GB of the machine's 46. That leaves the runner about 24 GB once about
2.5 GB is kept for the OS: `--memory 24G`, with fewer workers than cleanup's 10. `CARGO_BUILD_JOBS=8` keeps a
stream's first clean build under its cap (cleanup measured 3.1 GiB at 28 jobs).

**Running it all**, by the user, from the default workspace in tmux:
`FEATURE_LOOP_MEMORY_MAX=4G CARGO_BUILD_JOBS=8 llm-dlc/tools/run-streams.sh application-core`. It:
- compacts the planning session once;
- adds the four workspaces from the latest commit;
- starts `verification-loop.sh`;
- runs the streams side by side with the integration check, then this brief's own loop.

A stream that ends `waiting on jobs ID ...` is rerun once those results are collected, up to `RUN_STREAMS_JOB_WAIT`
(12 hours by default).

**Each stream can start on its own**:
- objects on primitive and array cases;
- values on static String kernels;
- environment on a static fixture that returns a primitive;
- reuse on the existing primitive properties, and a read-only POJO helper with explicit construction.

Full integration follows once the interfaces are stable, never through edits across branches.

### The integration check

`run-streams.sh` merges the four streams' current `@-` in its `application-core-integration` workspace whenever one
moves, at most hourly, and runs [`application-core-integration.sh`](../tools/application-core-integration.sh) on the
merge. The report goes to `llm-dlc/loop-summaries/application-core-integration.md` in the default workspace, and
names all four revisions. Its outcomes are distinct:
- a merge conflict, reported by `run-streams.sh` with the files in conflict;
- `COMPILE FAILED`;
- `CONTRACT FAILED`, from `lib/tests/application_core.rs`;
- `TESTS FAILED`: the unit tests, the earlier contracts, `build.py`'s suite, or `sync.py`'s review, run-record and
  performance suites.

Each stream reads the report at the start of every cycle. A failure in its own files is its next piece of work. A
conflict in an owned interface is a coordination task, recorded under Progress, never ignored until the end: a check
that never gets past the merge gives no evidence of integration. Tests that run solvers, the joint fixture checks
included, stay jobs.

### Reconciling

This follows [`cleanup.md`](cleanup.md#reconciling)'s steps, for four streams:
1. Check all four are finished (status `done` or `blocked`, not only an inactive scope), and that
   `feature-loop-application-core-integration.scope` is inactive too.
2. Wait for the verification loop to commit anything it left uncommitted in this working copy. Don't move or commit
   its files.
3. Record each stream's last turns, and copy their logs.
4. Merge with
   `jj new @- application-core-objects@- application-core-values@- application-core-environment@- application-core-reuse@-`,
   and commit.
5. Fold their Progress here, with every item the timebox deferred first, and every interface request that waited for
   the merge.
6. Forget the five workspaces. Their directories are the user's to delete.

## The plan

### Phase 0: interfaces and fixtures (the planning session, before the fork)

As [above](#phase-0-thin-interfaces-not-a-rewrite). It closes row G0's gate, apart from the merge's jobs.

### Phases 1–4: the streams

Each stream brief lists its items in order. All four run at once.

### Phase 5: after the merge (this brief's own loop)

1. **Reconcile** ([above](#reconciling)), then apply the interface requests that waited for it.
2. **The joint acceptance at the merge**, as jobs: J1 (the quote family composing O, V, E and R), J2 (the new native
   claims with JBMC unavailable), and the H and L families. Correct changes prove. Defective siblings refute, with
   their witnesses replayed. Exact cache reuse, reuse of helper evidence, and invalidation after a relevant semantic
   change are all shown.
3. **The existing examples at the merge**: 190–196, the cleanup merge's reruns and the examples the streams touched
   keep their expected outcomes. One job per app.
4. **The small cost report** (J4): cold, an unchanged rerun, an unrelated edit, a safe rewrite of a helper, and a real
   defect, with preparation, solving and replay timed apart. The figures are labelled for these fixtures only.
5. **The for-review list**, in this brief's Progress:
   - every row and its state, with the job that closed it, or the job that would close it and why it hasn't;
   - the timebox's deferrals;
   - the unsupported cases that remain;
   - the optional work left out;
   - every job still pending.

## Done when

| Phase | Criterion |
|---|---|
| 0 | G0's gate: the domain gate refuses every unread option, with reproducers; the four interfaces, hooks, contract test and frozen fixture skeletons committed; VF-015's harness fix committed with its reproducer, and its job passing, or deferred to the user with the finding (it has no timebox attempt left) |
| 1, objects | O1–O3 pass, or each is deferred by the timebox with the finding |
| 2, values | V1–V3 pass, or each is deferred by the timebox with the finding |
| 3, environment | E1–E3 pass, or each is deferred by the timebox with the finding |
| 4, reuse | R1, R2, and R3's justified outcome, or each deferred by the timebox with the finding |
| 5 | The merge committed, with the integration check passing on it. Every mandatory row passes on the merged revision, or is named partial or blocked with its evidence. The existing examples keep their expected outcomes. No new capability depends on JBMC being installed. |

A stopped process, a passing schema, a passing unit test or a queued job is not acceptance alone. Don't weaken this to
make all four streams green.

## Deferred: not in this loop

- **Evaluation campaigns**: a large CVE campaign, a corpus of 20–30 external changes, the full Box Office refactor.
- **Distributed systems**: protocol experiments, transaction or outbox verification, generating TLA+ effect
  transitions.
- **The general heap and libraries**: unrestricted heap state or arbitrary invariants; general `Map`, `Set`, streams,
  regex and reflection; broad dynamic dispatch; floating point.
- **Platforms**: a solver migration, a Lean or certificate platform, a remote proof store, a JBMC fork.
- **External JBMC work**, as cleanup's decision 1 left it.

A new SAT or SMT backend is no substitute for a missing Java domain or model. Add no JDK methods without a named
acceptance case that needs them.

## Decisions

Settled by the user on 2026-11-08, as the planning session proposed them on 2026-11-07, with the seventh added:
1. **The four streams and their scope**, as the outside plan drew them. Optional work stays optional and never blocks
   a row: objects' factory routes, values' extra method, environment's clock or response script, and reuse's R4.
2. **Verification with the pipeline**, not separate, so that rows can close in the loop.
3. **One writer for shared files**: the planning session, in Phase 0. Streams make only marked additive edits, and
   record other interface requests for the merge. This is stricter than cleanup's "add, don't rewrite", because of the
   merge conflicts of the foundations and cleanup runs.
4. **Phase 0 runs in the planning session**, after the cleanup merge and before the fork, so that every stream
   inherits it.
5. **Memory**: each stream's scope capped at 4 GB, and the runner given about 24 GB.
6. **Model and effort**: `claude-opus-5-5` at high effort for every loop.
7. **VF-015 is in scope**, as [Phase 0's step 7](#phase-0-thin-interfaces-not-a-rewrite): the equivalence harness
   catches checked exceptions. The stub-reachability loop's timebox deferred it to a person on 2026-11-08, and this is
   that person's decision. It goes in Phase 0, not in a stream, for three reasons:
   - the fix is in `harness/`, which the objects stream owns;
   - the environment stream's E2 needs it;
   - it is small: a harness change with unit tests, and one job of a few seconds of JBMC.

   It has no timebox attempt left. If the job fails again, it goes back to the user with the finding, and the streams
   launch without it.

## Progress

- Drafted 2026-11-07 by the planning session, from the outside plan, while the cleanup run was still going. The
  starting point was recounted at `wwlnosom`, and the names were registered in `feature-loop.sh` and `run-streams.sh`
  with the integration script.
- 2026-11-08: the user settled the six decisions as proposed, and brought VF-015 in scope as Phase 0's step 7
  (decision 7). The cleanup loop is merged and pushed (prerequisite 1). Prerequisites 2, 3 and 6–7 are left: the
  recount at the merge, then Phase 0 by the planning session.
- 2026-11-08, prerequisite 2 done, at `yzpmxwnx` (`08d23149`):
  - **The table**: [Where it starts from](#where-it-starts-from) recounted. Every row held, with line numbers moved,
    and the domain options are still read by nothing.
  - **The contracts**: `lib/tests/foundations.rs`, `compare.rs` and `effects.rs` pass inline (23 tests).
  - **The evidence that holds**: the cleanup merge's four reruns passed at the merge (jobs `20261107-215001-…`:
    150–152 and 160–161, 170–172, 190–196, and `lib/tests/integration.rs`).
  - **Since then**: only the stub-reachability loop changed checker code, in the JBMC gap preflight, and its guard
    job `20261108-011441-…` passed.
  - Phase 0 is next.
- 2026-11-08, Phase 0, by the planning session:
  - **Step 1, the domain gate** (`wtvnuryt`): a domain made field by field or of invariants is refused by
    `spec::heap::check_with`, and `equivalence::run` refuses, once its layout is built and before any helper proof,
    cache lookup or proof, a domain whose `calls` or `classes` aren't exactly the ones its harness makes
    (`spec::heap::made_with`). Its reproducer (`tests/heap.rs`) verified a field-by-field claim before. Four heap
    tests had changed a reused kernel claim's classes but not its Quote constructors, and now name their own.
  - **Step 7, VF-015**: the equivalence harness tells apart, after the listed unchecked exceptions, the checked
    exceptions either version declares, most specific first, then `java.lang.Exception`
    (`harness::Layout::checked`), and the replay numbers them alike. Reproducers: `tests/integration.rs`'s
    `a_method_that_declares_a_checked_exception_is_compared_on_it_and_a_change_in_it_is_found` failed before with
    "an uncaught before.fixtures.BadDigit leaves the harness". It now verifies a rewrite and refutes three defects
    on the exception (thrown on another input, another class, no exception), each replayed. Also the harness unit
    test `generates_a_harness_that_catches_the_declared_checked_exceptions`. A method without a `throws` clause
    gets the harness it had. VF-015's closing job is `20261108-024648-vf-015-example-109-revisited-hex-todigit`,
    with step 4 made stricter (a violation, replayed, on a char above 127). It has no timebox attempt left.
- Status: blocked: Phase 0, by the planning session, before the fork

## Loop settings

- session: 6ca21bdf-4743-4500-90ea-7fe6280624b2
- model: claude-opus-5-5
- effort: high
- integration: llm-dlc/tools/application-core-integration.sh
- new-window: no

## Loop until

The reconcile comes first. Don't stop before the merge is committed, unless a stream is unfinished or the merge needs
the user. Then Phase 5. Keep the last line of Progress a status: `working`, `waiting on jobs ID ...`, `done`, or
`blocked: ...` with what needs the user. Stop with `done` once Phase 5's criterion is met and the for-review list
names every row's state. A missing core result is recorded as partial or blocked, never as done. Don't turn optional
work into a second project. Items deferred by the timebox count as recorded deferrals, never as a reason to keep going.

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
  - **Step 2, the four interfaces**, in `lib/src/spec/plans.rs`: `ConstructionPlan` (carried by a new
    `Construction::Planned` domain), `ValueDomain` and `WitnessValue`, `CallModel` (on a `ModeledCall`, as its
    optional `model`), and `Summary`. Every struct refuses unknown fields and every enum unknown variants, with
    serialization tests. `Part` has the four streams. Until a stream builds its part, a planned domain is refused by
    the heap check (`Part::Objects`) and a call's model by the effect check (`Part::Environment`), tested in
    `tests/heap.rs` and `tests/effects.rs`. Neither is in the claim key's known fields yet, so such a claim is
    uncacheable until the reuse stream registers them.
  - **Step 3, the hooks**: the streams' modules `lib/src/construction.rs` (objects), `values.rs`, `environment.rs`
    and `reuse.rs`, registered in `lib.rs`, each returning `Unsupported` naming its stream until it builds its
    part. Their call sites are in place:
    - the domain gate asks `construction::check_plans` for a planned domain;
    - an instance method asks `construction::receiver` (`equivalence` and `property`);
    - a String or List parameter asks `values::adapter`;
    - a call's model asks `environment::check_model`;
    - `prove --cache` asks `reuse::property_lookup`, then `property_store`.

    The flags `--plan FILE` (`equivalence`, `prove`), `--environment FILE` (`effects`, `compare`, through
    `effects::check_builds` and `compare::Options::environment`) and `prove --cache` load into the checks'
    options, and the checks refuse what they don't take yet. `StatementSpec` carries the environment and the
    summaries a check used.
  - **Step 5, the frozen fixtures**, in `lib/tests/fixtures/application-core/` (its README): Q, the quote service
    (`quotes`: a receiver with a fee policy, a rate query that may throw the checked `RateUnavailable`, a nullable
    `Offer`, one event, the helper `fee`, and `Codes.vip`), with seven defects; H, the throttle, with `after-setup`
    (a defect only a setup call reaches) and `one-short`; L, the basket over an immutable list, with four defects.
    Eight frozen claims with planned domains, and `golden/expected.json` naming every build's verdict under every
    claim and under five plain regression checks. On JDK 25.0.5, `after` agrees with `before` on every case of the
    grids (30,240, 315 and 43), and each defect differs exactly in the methods its expectations name
    (`Conformance.java`). `tests/application_core.rs` starts with their round trips and compilation.
  - **Step 4, the integration contract**, `lib/tests/application_core.rs`: one test per row a unit run reaches (G0,
    O1–O3, V1, V2, E1, E2, R1, R2, J3), on the frozen fixtures, the native engine and no JBMC (J2's guard). Each
    case must reach its `expected.json` verdict, or be refused in the words of a stream that owns its row.
    Anything else fails, a refusal by another stream included. Today G0 reaches its verdicts (the gate refuses
    each unsupported policy, and the kernel's own claim is verified), and every other row stops at its streams'
    named refusals. `environment::check` is E1's and E2's entry point. The integration check passes on it.
  - **Step 6, the schemas**: `examples/schema/result.schema.json`'s statement registers, as named variants, a
    `value` parameter, the `environment`, `summary` and `setup` assumptions, the bounds `maxValueLength`,
    `setupCalls` and `traceBound`, the value models with their evidence levels, and a replay `by` `model` (a JVM
    under the environment model's stubs). `lib/src/statement.rs` has the same: `ParameterKind::Value`,
    `AssumptionKind::{Environment, Summary, Setup}`, `Bounds::{max_value_length, setup_calls, trace_bound}` and
    `Models::values`. Each is absent or unchosen until a stream fills it, and all 157 recorded example results still
    validate. The contract's `the_result_schema_registers_the_statements_new_kinds` holds the two together.
  - **Phase 0 is committed** (launch prerequisite 3). VF-015's job `20261108-024648-…` ran at `eea1a8a8` and
    failed at step 5 only, triaged by the verification loop (`ponxovxr`, `verification/findings.md`):
    - **The harness fix works.** Step 5 no longer fails on the uncaught-exception property: JBMC proves the harness.
      The tool then refuses that proof because JBMC runs four class initializers otherwise than the JVM
      (`throwing-initializer` at `CharEncoding.<clinit>` and `Hex.<clinit>`, both versions, as possibly throwing a
      NullPointerException, probably through its `StandardCharsets` stub). That guard is separate from VF-015's
      harness cause.
    - **Step 4's replay is half a replay.** The change is found (`toDigit(ch='٧', index=-1)`: before 7), but the
      new version's replay fails ("String.format depends on the default locale"), and the outcome still says
      `reproduced: true`: an outcome the interpreter couldn't produce counts as a difference. Not caused by step 7,
      but step 4's stricter check passed on it.
    - Per decision 7, there is no timebox attempt left: **this goes back to the user**, and the streams may launch
      without it. A further attempt could:
      1. run step 5 with `--engine native`, whose checker reads the JDK's own charset classes: one job of seconds,
         a native verdict that JBMC doesn't confirm;
      2. have the throwing-initializer check ask JBMC's solver whether a path reaches the throw, as the gap
         preflight does for stubs (`jbmc_gaps.rs`): about a day, with its own reproducer and job;
      3. model the `StandardCharsets` constants for JBMC (`lib/models`, the values stream's).

      Separately, a replay that can't run one version shouldn't count as reproduced (`witness::differences`, the
      objects stream's replay plumbing).
- 2026-11-08, **VF-015 deferred by the user**: the streams launch without it. Other ways of proving step 5 are for
  later; the options above stand. The planning session pushed (prerequisite 6) and set this status (prerequisite 7).
- 2026-11-08, **the reconcile's step 1, checked at `ntyolumk`: three streams aren't finished**, so nothing was merged.
  Every stream's loop has stopped (no `feature-loop-application-core-*` scope but this loop's, the integration
  check's included), and the queue is empty (298 collected, none pending). But only values ends `blocked: ...`
  (at `pymxzpyu`). Objects (`nqpqroqp`), environment (`xlxxtpul`) and reuse (`womryvut`) still end
  `- Status: working`: each session decided to stop without setting its status, and `run-streams.sh` counts such a
  stop as done ("its status doesn't say why"). Each still has work of its own:
  - **objects**: record O2's job `20261108-074116-…`, now passed and collected (`d3739c98`), then a status: it
    waits on the merge for O2's String adapter (values' `nlkuyptr`), and on a decision about O3's frozen
    allocation bound of 0, under which `application_core`'s O3 is unresolved rather than `expected.json`'s verdict;
  - **environment**: E3 and the Q integration wait on the objects stream's construction plan and the values
    stream's String adapter, so `blocked: ...` by its own account, which its last turn couldn't write;
  - **reuse**: read job `20261108-063259`'s figures (collected) into R3's record, which closes R3. R4 is optional.

  The integration check's last report (09:36) merged the four `@-` and conflicts only in generated files
  (`llm-dlc/README.md`, `index.json`, `traces/README.md`, `traces/metrics.json`), which `sync.py` regenerates.
- 2026-11-08, **why the three stopped, and the rerun**: each session answered `LOOP: stop` in `feature-loop.sh`'s
  decision turn, which may not edit or commit, and wrote there the status it meant (objects and reuse
  `waiting on jobs ...`, environment `blocked: ...`); no cycle had been asked to keep the status line current. The
  user had the loop tooling fixed (`kppsnzyn`, and the same files committed in each of the three workspaces:
  objects `umqkzwlp`, environment `wvournln`, reuse `ropyotpk`): a stop that leaves a status `working` now gets a
  turn to set it, and `run-streams.sh` reruns such a stop instead of counting it done. The user restarted
  `run-streams.sh`, which reruns the three streams, then this loop. O3's allocation bound still needs the user.
- 2026-11-08, **O3's allocation bound, decided by the user**: the frozen throttle claims
  (`golden/throttle-constructed-claim.json`, `golden/throttle-setup-claim.json`) are bounded at 1 allocation in
  each version, not 0: `allows` makes the `IllegalArgumentException` it throws, which the gate counts, as
  `checked-claim`'s bound of 1 already counts its own. The bound covers the target call only; setup calls are
  bounded by the plan's `setup_calls` and their outcomes are compared, so the gate stays as it is. `expected.json`
  is unchanged. Applied on the objects branch (`tzsluzns`), where the contract test passes 14 of 14; the merge
  takes it as a deliberate change to a frozen fixture, not a stream relaxing one. Also: `feature-loop.sh` now
  reads a stream's own brief, not the default workspace's copy (`unwrvwqw`); the reuse stream, already running,
  keeps the old reading until it stops.
- 2026-11-08, **the reconcile (Phase 5, step 1): the four streams merged**, in the merge commit
  `Merge the four application-core streams`.
  - **Steps 1–3**: all four streams had finished: objects `blocked` (`tzsluzns`), values `blocked` (`pymxzpyu`),
    environment `blocked` (`qrsyvrmk`), and reuse `done` (`tvrqpusw`). No stream's scope or the integration check's
    was active, and no job was pending. Each stream's last turns were recorded on its branch (`Record session traces`:
    objects `qqywzsvy`, values `kyqtplry`, environment `krwlnoop`, reuse `yxlnwoss`). Their 46 logs not yet here
    were copied in. Their run records were already in `llm-dlc/loop-summaries/`, copied by `run-streams.sh`.
  - **Step 4, the merge**: `jj new` of the default line's `tvwtmzkx` and the four branches. It conflicted only in the
    generated `llm-dlc/README.md` session table, `index.json`, `traces/README.md` and `traces/metrics.json`; the
    default line's side was taken, and the commit regenerates them. Files changed on more than one line merged
    cleanly: `lib/README.md` (each stream's paragraphs, in places of their own), `lib/tests/conformance.rs` (objects
    and values), and `feature-loop.sh` and `run-streams.sh`, whose identical stop-status fix the user committed on
    each line.
  - **Verified on the merge**, inline:
    - the integration check, `application-core-integration.sh`, passes: the contract 14 of 14, the library's unit
      tests (254), `foundations` 5, `compare` 1, `effects` 18, and the `build.py`, review, run-record and performance
      suites;
    - every other test binary but `integration.rs`, whose tests run JBMC: `alignment` 34, `application_core_objects`
      21 (1 ignored, item 4 below), `conformance` 10 (2 JBMC), `environment` 16, `heap` 49 (9 JBMC), `observations`
      12, `reuse` 11, `reuse_summaries` 14, `skill` 1, `summaries` 40, `values` 16 (1 ignored, item 3), with
      `preparation`'s benchmark ignored as it always is;
    - every Python suite: `examples/tools`, `lib/benchmark`, `lib/solvers`, `llm-dlc/tools` and `verification`.
  - **Step 6**: the workspaces `application-core-objects`, `-values`, `-environment`, `-reuse` and `-integration`
    are forgotten. Their directories, `../in-the-loop-application-core-*`, are the user's to delete.
  - **Deferred by the timebox**: none, in any stream. **Deferred by the user**: VF-015's step 5 (above).
  - **Interface requests that waited for the merge**, Phase 5 step 1's work, by the owner of the file:
    1. **The String and list parameter wiring** (objects' `harness/`, `equivalence.rs`, `property.rs`, `jbmc.rs`'s
       `arguments`, the replay), the values stream's two requests: take a String or list parameter in the layout,
       give the checker `StringAdapter::bound` or make the list by `ListAdapter::choices` and `java`, read the
       witness with the adapters' `read`, rebuild it with `rebuild`, and state `Bounds::max_value_length` and
       `Models::values`. Then `values::adapter` returns the adapters (one line). It is objects' O2 String adapter and
       what V1's and V2's rows wait on, and the environment stream's Q rows need it for the quote's code.
    2. **`values::resolve`** in `construction::check_plans` and wherever a modelled call's `Returned::Adapted` is read,
       before `proof_cache` digests a claim (V3's identity reaching the checks).
    3. **VF-023**: in `equivalence::confirm`'s `Verdict::Violation` arm, a JBMC refutation that doesn't reproduce and
       whose preflight found a stub is `Confirmed::NoVerdict`, naming the stubs. Then un-ignore values'
       `confirm_takes_a_refutation_through_a_jbmc_stub_that_does_not_reproduce_for_no_verdict`, and rerun job
       `20261108-070211-…`'s step 2 unchanged. VF-023 has one failure, so one attempt is left.
    4. **The cache's roots of a setup sequence**: root `proof_cache::Regression::claim` at
       `Layout::construction_roots(previous)`, drop the uncached guard for setup sequences in `equivalence.rs`, and
       un-ignore objects' `an_inner_objects_constructor_is_part_of_the_cached_claim` (reuse's `qssovxor` closed the
       inner-constructor hole itself). Also a `setup` field in `witness::Call` and in the cache's stored call.
    5. **E3**, the environment stream's last required item: a nullable DTO response (`Returned::Object`) made through
       the merged construction plan, with its identity policy in the claim, the null branch replayed, and unmodelled
       methods, fields and cycles refused. Then Q's E1 and E2 rows through `environment::check`, after item 1.
    6. **Smaller requests**: `compare` given a plan per subject (`main.rs`); `reuse::property_store` taking
       `&mut Outcome` and `property::Outcome` a `reuse` field; `jvm_witness::run` sizing `max_stack` from the
       parameters' widths, so that wide witnesses replay; the class reader keeping a `CONSTANT_Utf8`'s code units;
       `ElementKind::String` with a bound; the stale help and docs of `--environment` and `prove --cache`
       (`main.rs`, `compare.rs`, `property::run`), and `compare`'s effort report counting a declared environment.
    7. **`lib/README.md`'s sentences that streams couldn't rewrite**: Limits' "property proofs are still over static
       methods"; "an input a constructor of either version rejects is outside the statement"; "a used result is
       refused until modeled return values come"; and arrays of references' "cells hold objects or `null`".
  - **Found by the streams, for the for-review list** (each in its stream's Progress):
    - objects: a regression check doesn't observe the target's own writes to static fields, and no doc says so;
    - values: the interpreter's `Character` classification uses Rust's Unicode tables (`Character.digit('٧',
      16)` is -1, where the JVM gives 7); `render::primitive` writes a surrogate `char` as U+FFFD; the interpreter
      names a `List12` `ListN`; `List.of(E...)` has no evidence record; the checker's time limit overshoots
      (20 s ended at 138 s); a property witness that couldn't be replayed at all was printed as violated; and
      `bmc::bits`' timing test fails under load;
    - environment: whether a reordering of reads preserves depends on the declared coupling (a query or a choice),
      and the result names it;
    - reuse: an array-reading helper's summary compares an out-of-bounds throw as an outcome, which departs from the
      brief's "total"; R3's cache is in `jimage.rs`, a file in no stream's ownership row; a route's effect proof
      doesn't use helper evidence, so a helper rewrite proves the route again; R4 is left out.
  - **Rows at the merge, by the streams' accounts**: O1, O3, R1 and J3 reach their verdicts in the contract. O2's
    rows pass but its String adapter waits for item 1. V1 and V2 stop at the values stream's named refusal until
    item 1. E1 and E2 are done on the stream's fixtures, but Q's rows stop at the merge's items 1 and 5. R2 stands at
    unit level, and its contract row should reach `fee`'s summary now that the receiver is built. The contract
    accepts a named refusal as passing, so Phase 5's for-review list has to name each row's state from a run that
    tells the two apart.
  - **Next**: Phase 5 step 1's interface requests, in the order above, each a cycle with its reproducer. Then step
    2's joint acceptance as jobs, and step 3's examples with `lib/tests/integration.rs` (JBMC) at the merged
    revision.
- 2026-11-08, **Phase 5 step 1, interface request 1 (its String half): a String parameter of a regression check**,
  for V1. The list half is the next cycle.
  - **The reproducer**: the contract's V1 row accepted the values stream's refusal. It now accepts none
    (`regressions("quote", "quotes.Codes#vip", &[])`), and it failed before the wiring.
  - **The wiring**:
    - `values::adapter` gives the regression check the String adapter: at most `--max-array-length` code units, and
      never null, as an array parameter isn't.
    - The harness passes the one String to both versions, and the own checker makes it under that bound
      (`bmc::Parameters::max_string_length`, in the proof and in the vacuity probe).
    - The witness is a new `jbmc::Argument::String`. It is read and rebuilt by the rules the adapter's `read` and
      `rebuild` apply (`values::string_units`, `values::new_string`), so the snapshot digest covers the checks too;
      the digest is unchanged.
    - It is shrunk by dropping a unit, or by making one that isn't printable ASCII an `a`, each candidate replayed
      before it is taken. It is rendered as a Java literal, with every other unit escaped.
    - It is also run on a JVM, as `new String(char[])`, since the interpreter's String is a model.
    - The statement states the parameter as `ParameterKind::Value` with its bound, `Bounds::max_value_length` and
      `Models::values`. The cache's claim key covers the bound and the String model's identity, and a stored witness
      reads back.
    - JBMC is not asked: `--engine jbmc` is refused by name, and `--confirm` records `not-asked`.
  - **Checks**:
    - The contract passes 14 of 14, and V1 reaches its verdicts: the rewrite is proved, and `wrong-prefix` is
      refuted on `vip("VI")`, replayed in the interpreter and on JDK 25.0.5.
    - The new `tests/value_parameters.rs` (4 tests):
      - the correct case and the defect, with the statement;
      - an isolated surrogate, `"\udbff"`, crossing to the JVM unit for unit. Shifting the units the JVM run passes
        fails it;
      - the named refusals;
      - a cached proof reused exactly, and proved again under another bound.
    - `integration.rs`'s String test now expects the JBMC refusal (run inline: it never reaches JBMC).
    - The integration check passes, and so does every other test binary but `integration.rs`. No recorded example
      result named the old refusal.
  - **Still refused by name** (for the for-review list):
    - a String parameter of a property check, since the expressions have no String terms;
    - a String result, since the harness compares it with `Objects.equals`, a gap the own checker refuses;
    - a String plan root, and a null String.
  - **Docs**: `lib/README.md` (the String adapter's paragraph), `--max-array-length`'s help, and the schema's
    description of a witness value (`{"kind": "string", "units": [...]}`).
  - **Next**: item 1's list half (V2's rows, the basket's regressions and planned claims), then items 2–7.
- 2026-11-08, **Phase 5 step 1, interface request 1 (its list half, for plain regression checks): a list parameter
  of a regression check**, for V2's two `regressions` rows. The planned claims' adapted list root is the next cycle.
  - **The reproducer**: the contract's V2 regressions accepted the values stream's refusal. They now accept none
    (`regressions_within("basket", …, &[], Some(3))`, under the frozen claims' list bound of 3), and they failed
    before the wiring.
  - **The wiring**:
    - A `List<E>` parameter, its element class read from the method's generic signature, is a new
      `harness::Slot::List` of at most `--max-array-length` elements (10 at most), never null.
    - The element is an application object made by its constructor, or a record. Its construction and fields must
      be primitive, and of the same shape in both versions.
    - The harness makes `max_length` objects (`lines.m0` …) in each version from the same leaves. It builds each
      version's list from the adapter's int choices (`ListAdapter::choices`) in the shape `ListAdapter::java`
      writes, and skips what `admitted` doesn't admit before anything is made.
    - `List.of` is called through a branchless helper class of version 52 (`harness::LISTS_CLASS`). The harness's
      own version 49 has no `invokestatic` of an interface method.
    - The objects' fields are compared after the calls, as an object parameter's are.
    - The witness stays flat ints and leaves, so the reader, shrinker, cache and JVM run take it unchanged.
    - Its list is read by `ListAdapter::read`, rendered as `List.of(new Line(1, 1), the same object as lines[0])`,
      typed as a list of nodes, and rebuilt over each version's objects by `rebuild` for the replay.
    - It is also run on a JVM. `jvm_witness` now sizes `max_stack` from the arguments' widths, the JVM-run part of
      item 6: an 8-line witness failed with "Stack size too large" before.
    - The statement states `java.util.List<E>` as a value with its bound, `Bounds::max_value_length`, the list
      model, and one constructor assumption for the objects.
    - The claim key covers the list model, the elements' constructors (as roots) and the helper's digest.
    - JBMC is not asked: `--engine jbmc` is refused (VF-023), and `--confirm` records `not-asked`.
  - **Checks**:
    - The contract passes 14 of 14. V2's regressions reach `expected.json`'s ten verdicts: `total` and `clearAll`
      proved; `duplicate-skipped` and `alias-blind` refuted on a witness whose second element is the first's
      object, replayed in the interpreter and on JDK 25.0.5.
    - At the default bound of 8, `clearAll`'s proof takes 27 s in a release build, and about 100 s in debug.
    - `tests/value_parameters.rs` has 3 new tests (7 in all):
      - the correct cases and the two defects, with the statement and the typed list;
      - the named refusals;
      - a cached proof reused exactly, but not under another bound or after an edit of the element's constructor.
    - Two sabotages fail them: the harness ignoring the picks, and the replay rebuilding distinct elements.
    - The integration check passes, and so does every other test binary but `integration.rs` (JBMC).
  - **Still refused by name** (for the for-review list):
    - a raw list, a wildcard's or a type variable's;
    - elements made from arrays or objects, or holding one;
    - an object result, which could be an element (`Basket#first`: an identity not observed yet);
    - a list with `--before-target`, `--before-arguments`, `--results-agree-when` or a correspondence;
    - `--nullable` or `--may-alias` of a list, a plan's adapted list root, and a list parameter of a property check.
    - Every made object is constructed whether the list holds it or not, so a version that rejects an unused
      object's leaves is a difference. This is sound but stricter than the list alone.
  - **Docs**: `lib/README.md` (the list adapter's paragraph and a new one), `--max-array-length`'s help, and the
    schema's description of a witness value (the list of nodes).
  - **Next**: item 1's last part, the planned domain's adapted list root (the three `basket-*-claim`s through
    `spec::heap::check`, `first`'s `identity:result==lines[0]` included); then items 2–7.
- 2026-11-08, **Phase 5 step 1, interface request 1 (its last part): a plan's adapted list root, and a result's
  identity with the list's elements**, for V2's three frozen claims.
  - **The reproducer**: the contract's V2 claims accepted the objects' and values' refusals. They now accept none,
    and they failed before: the plan's root `lines` was refused by `construction::check_plans`.
  - **The plan's root**:
    - `construction::check_plans` takes a root that is a `PlanValue::Adapted` list of objects, named as the root.
      It resolves the domain under this tool's list model (`values::resolve`, item 2's first call site), which
      refuses another model's identity, another JDK or a stronger level.
    - It refuses a list that may be null, an adapted String root, and an adapted root that differs between the
      versions. An adapted value inside a node is still refused as before.
    - `construction::root` gives it as `Rooted::List`, and the check makes it as a list parameter, under the
      domain's own bound (the frozen claims' 3), not `--max-array-length` (their 4).
  - **The result's identity**: an object result that the check follows into its fields (`Basket#first`'s `Line`)
    is no longer refused.
    - The harness, the replay and the Java text compare it for identity with each of the list's objects, before and
      now (`harness::Root::Element`). The first object is named `lines[0]`, which it always is when the list has an
      element 0. The others are `lines.m1` and so on: each is the element at every index whose pick is it.
    - So comparing the result with each object compares it with every element.
    - A result the check doesn't follow (`Object`, an interface) is still refused.
  - **The accounting**:
    - The statement states the list's objects as one observation of the list (`lines: m0.unitCents, …`), so a
      claim's `field:lines` is compared.
    - The list counts among the input objects, so the frozen claims count 4 = 3 lines + the list.
    - A contract input may name a generic parameter by its erased type (`java.util.List`).
  - **Checks**:
    - The contract passes 14 of 14. `basket-total-claim` and `basket-clear-claim` reach all of `expected.json`'s
      ten verdicts: the rewrite verified, `duplicate-skipped` refuted on `result` under total, `alias-blind` on
      `result` under clear, each witness replayed on a JVM.
    - `basket-first-claim` reaches four of its five: `after`, `alias-blind` and `duplicate-skipped` verified,
      `identity:result==lines[0]` preserved, and `last-not-first` refuted on `result`. `copied-first` is left
      unresolved, as below.
    - `tests/value_parameters.rs` has 3 new tests (10 in all):
      - the plan's own bound, and the identity preserved by the rewrite and refuted on `copied-first` with the
        claim's allocation bound raised to 2, replayed on a JVM. `firstOf` without a plan is proved with the
        identities `result == xs[0]`, `xs.m1` and `xs.m2` stated;
      - seven refusals of a plan's list root, by name;
      - a planned claim's cached proof reused exactly, but not with the list bounded at 2.
    - Two sabotages fail the test: identity references without the list's objects, and the replay reading them
      as null.
    - The integration check passes, and so does every other test binary but `integration.rs` (JBMC).
  - **For the user: `basket-first-claim`'s allocation bound** (a frozen fixture against its expectation, as O3's
    was).
    - The claim bounds each version's allocations at 0. `copied-first`'s code makes 2 objects: the copied `Line`,
      and the `IllegalArgumentException` its constructor may throw.
    - So the allocation gate leaves it unresolved ("the new version's code may make 2 objects in one call, more
      than the claim's allocation bound of 0"), where `expected.json` says refuted on `identity:result==lines[0]`.
      The gate stays as it is.
    - Until the user decides, the contract holds that one case to exactly the gate's outcome, and every other case
      to `expected.json`.
    - The options:
      1. bound the claim's allocations at 2 in each version, as O3's decision counted the exception `allows`
         throws. Then the case is refuted on the identity, as the new test shows;
      2. keep 0, and expect `unresolved` for `copied-first`: a defect outside the claim.
  - **Docs**: `lib/README.md` (the list paragraph and the plan paragraph's refusals).
  - **Next**: the rest of item 2, `values::resolve` wherever a modelled call's `Returned::Adapted` is read. Then
    items 3–7.
- 2026-11-08, **Phase 5 step 1, interface request 2 done: a claim's value domains are resolved before its key**.
  - **The reproducer**: `tests/values.rs`'s new
    `a_claims_value_domains_are_resolved_before_its_key_and_its_checks`. It failed before on each of the three call
    sites below, each taken out alone:
    - `basket-total-claim` in the frozen claims' words and the same claim stated by the models' identities had two
      keys;
    - a modelled call's String result under another model was refused only as an adapted result;
    - the quote request's code under another model was refused only as an adapted value inside a node.
  - **The change**:
    - `values::resolve_claim` (and `ValueModels::resolve_claim`) resolves every value domain a claim carries:
      - a plan's adapted values, at its roots, inside its nodes and in its setup calls, in each version;
      - a modelled call's adapted response, and the adapted values of an object response's plan.
    - `spec::cache::key` resolves the claim first. A claim stated under another model, another JDK or a stronger
      level, or over a domain the adapters refuse, is uncacheable, naming the domain's path and the reason. It is
      never keyed.
    - `environment::lower` resolves an adapted result before refusing it. The refusal now says what is missing (no
      stub makes an adapter's value), not "waits for the values stream's adapter".
    - `construction::check_plans` resolves an adapted value inside a node before refusing it.
  - **Checks**:
    - The new test checks `values::resolve_claim` against the test file's reference walk on all eight frozen claims.
      It also checks that resolving twice changes nothing.
    - It checks each refusal by name: another model, a stronger level, in the key, in the effect check and in the
      plan check.
    - The integration check passes (the contract 14 of 14). So do the other binaries but `integration.rs` (JBMC):
      alignment 34, application_core_objects 21, conformance 10, environment 16, heap 49, observations 12, reuse 11,
      reuse_summaries 14, skill 1, summaries 40, values 17, value_parameters 10.
  - **A test of the reuse stream changed, for the for-review list.** `tests/reuse.rs`'s
    `every_semantic_part_of_a_plan_or_a_model_changes_the_key` expected another key for three changes. Two are
    the frozen claim once resolved, because `ValueModels::resolve` (the values stream's design, documented there)
    replaces a stated evidence record with the model's own: a String model stated at `tested`, the model's own level
    (the frozen claim says `modelled`), and a list model that says it leaves out nothing. Neither changes what is
    checked, so the test now asserts that each gives the frozen claim's key. The third, a list of Strings, is now
    never keyed (the adapter refuses it). The test asserts that, and that a String model stated as `proved` is never
    keyed. A change of the model itself still changes every key over it (`tests/values.rs`).
  - **Docs**: `lib/README.md`'s claim-key paragraph, the doc of `spec::cache` and of `environment`.
  - **Next**: item 3, VF-023's rule in `equivalence::confirm`, with values' ignored reproducer un-ignored, and job
    `20261108-070211-…`'s step 2 rerun unchanged. Then items 4–7.
- 2026-11-08, **Phase 5 step 1, interface request 3 (VF-023's rule): a JBMC refutation through a stub that doesn't
  reproduce is no verdict** under `--confirm` (verification pending).
  - **The reproducer**: values' `confirm_takes_a_refutation_through_a_jbmc_stub_that_does_not_reproduce_for_no_verdict`
    (`tests/values.rs`), un-ignored. It passes now, and fails with the rule taken out ("the engines disagree").
  - **The change**: in `equivalence::confirm`'s `Verdict::Violation` arm, a refutation whose witness the interpreter
    doesn't reproduce and whose preflight finds a stub (a gap record) is `Confirmed::NoVerdict`, the reason naming
    each stub, as a defect already made it. The own checker's proof stands, not confirmed. A witness that reproduces
    is still a disagreement, and a preflight that can't read the program leaves it one too.
  - **Checks**: `conformance` 10 (`confirm_reports_what_jbmc_made_of_a_proof_of_the_own_checker` still gets its
    disagreement, whose stand-in program reaches no stub), `values` 18, and the integration check passes.
  - **The job**: `20261108-141443-vf-023-rerun-the-conformance-corpus-unde`, job `20261108-070211-…`'s step 2
    unchanged. It closes VF-023 when it passes, and is VF-023's last attempt under the timebox.
  - **Docs**: `lib/README.md`'s `--confirm` paragraph, and the doc of `equivalence::confirm`.
  - **Next**: item 4, the cache's roots of a setup sequence. Then items 5–7.
- 2026-11-08, **Phase 5 step 1, interface request 4 done: a regression claim with a setup sequence is cached, its
  key rooting the setup methods**, and the typed witness carries the setup calls.
  - **The reproducer**: `tests/application_core_objects.rs`'s
    `o2_a_setup_methods_edit_alone_is_another_claim_never_reused` now also asks that the exact reruns of the proof and
    of the refutation are reused, and that the witness's typed calls list the history. It failed before, on the
    rerun ("note: a claim with a setup sequence is not cached yet"). With the guard dropped but the setup methods not
    rooted, it failed on the stale hit: an edit of the setup method `add` alone was answered by the stored proof.
  - **The change**:
    - `proof_cache::Regression::claim` roots each version's closure at the target, then at
      `Layout::construction_roots(previous)`: the constructors (the inner objects' included, as the reuse stream's
      `qssovxor` already had them) and the setup calls, each once. The uncached guard for setup sequences in
      `equivalence::run_check` is gone.
    - `witness::Call` has a `setup` field: each setup call's method, descriptor and typed arguments, mapped to their
      inputs (`setup.0.n`). Absent without a setup sequence. `proof_cache`'s stored call keeps it, so a reused
      refutation's witness keeps its history. The result schema's `typedCall` registers it, and `build.py` keeps it.
    - `application_core_objects`' `an_inner_objects_constructor_is_part_of_the_cached_claim` is un-ignored. It
      passes, on the reuse stream's fix.
  - **Checks**: `application_core_objects` 22 of 22. `build.py`'s new
    `test_a_witness_keeps_its_setup_calls_and_they_validate` passes. The integration check passes (the contract 14 of
    14). So do the other binaries but `integration.rs` (JBMC): alignment 34, conformance 10, environment 16, heap 49,
    observations 12, reuse 11, reuse_summaries 14, skill 1, summaries 40, values 18, value_parameters 10.
  - **Found, for item 6**: `property::run` still refuses `prove --cache --plan` ("the property claim's key does not
    read the construction plan yet"). The reuse stream's property key reads the plan whole, with its makers and setup
    calls among the roots (`reuse.rs`), but no test has run a planned property check under the cache end to end. So
    lifting that guard needs a test of its own, an exact rerun reused and an edited setup method proved again.
  - **Docs**: `lib/README.md`'s plan paragraph and "What makes the inputs is part of the claim", and the doc of
    `proof_cache`.
  - **Next**: item 5, E3 (a nullable DTO response made through the construction plan), then Q's E1 and E2 rows.
    Then items 6–7.
- 2026-11-08, **Phase 5 step 1, interface request 5 (its E3 half): a dependency's DTO response, made by the
  construction plan**, on the environment stream's own Spring fixture. Q's E1 and E2 rows through
  `environment::check` are the next cycle.
  - **The reproducer**: the new `tests/environment_responses.rs`, 8 tests. Each failed before on
    `environment::lower`'s refusal ("a DTO response made by a construction plan: the environment stream's E3, not
    built yet").
  - **The change**:
    - `environment::lower` takes `Returned::Object` as a `Response`: the plan's one node, made by the constructor it
      names, from integral or boolean leaves named from the plan's root (`result.unitCents`), nullable or not, of a
      fresh or a stable identity. The call must return that class. Each table entry's answer is then its null flag
      and its leaves (`offers.find[0].null`, `offers.find[0].unitCents`).
    - Refused by name: an array, a String or adapted field, an inner object, a dependency, a factory, a setup call,
      several roots, a nullable or aliased root, and a stable identity under a per-call choice.
    - `environment::check_response` checks the class in each build. It must have primitive instance fields only, no
      static field and no method beside its constructors. Then `construction::root` (the objects stream's plan, so
      the environment has no object builder of its own) makes it, and its leaves must be the model's.
    - The effect check (`effects::response_uses`) refuses, in each build: a call of a method on the DTO's class, a
      write of its field outside its constructors, and `Object`'s `hashCode`, `toString`, `wait` and `notify` in a
      method that handles one. javac names those on `Object`, so their receiver isn't followed.
    - The stubs make the response from the chosen entry: null by its flag, else a new object by the constructor
      (fresh), or the entry's object kept for the trace (stable). A constructor that throws on the chosen leaves sets
      a new unresolved bit ("a response its constructor wouldn't make"), never passes its exception off as the
      dependency's. The mark's bits widen to 7, and the build tag moves to 128.
    - The witness names each answer (`gives a new Offer(unitCents=…, minimumUnits=…)`, `gives null`, or under a
      stable identity `one object for every call of that key`). The assumptions and the domain say how the response
      is made and what its identity is.
  - **Checks**:
    - `environment_responses` 8 of 8:
      - the correct case, a rewrite that tests for null the other way round;
      - a changed null branch refuted on `gives null`, and a changed field test refuted on a made `Offer`, each
        replayed on a JVM;
      - the identity policy deciding: `a == b` of two responses is proved equal to `1` under `stable` and refuted
        (0 against 1, replayed) under `fresh`;
      - a constructor that rejects the leaves left unresolved;
      - five builds beyond data refused by name (a DTO method, an object field, a static field, `hashCode` on it, a
        field written);
      - the claim key: an exact rerun reused, a reused refutation replayed again, and `stable`, never-null and an
        edited DTO constructor each another key;
      - six refusals of the model's shape.
    - Two sabotages fail them: a fresh identity kept like a stable one fails the identity and key tests, and an
      ignored null flag fails the null-branch and key tests.
    - The integration check passes (the contract 14 of 14, the unit tests 254, `effects` 18, `compare` 1,
      `foundations` 5, the Python suites), and so do `environment` 16 and `observations` 12, the other binaries
      that reach the effect check.
  - **Docs**: `lib/README.md` (a new paragraph, and the refusal list no longer names a DTO), the module docs of
    `environment` and `effects`.
  - **Next**: item 5's other half, Q's E1 and E2 rows through `environment::check`: the quote fixture's receiver and
    request made by their plan, a String key (`Rates.rate(code)`, `Offers.find(code)`), the String in the event's
    snapshot, and `offer-claim`'s DTO. The effect check takes integral handler inputs only today, so this is a
    harness of its own, or `equivalence` with stubs. Then items 6–7.
- 2026-11-08, **Phase 5 step 1, interface request 5 done (its second half): Q's E1 and E2 rows through
  `environment::check`**, on the frozen quote fixture.
  - **The reproducer**: the contract's E1 and E2 rows accepted the environment, objects and values streams'
    refusals. They now accept none (`claims("quote", …, &[], environment::check)`), and they failed before on
    `environment::check`'s refusal.
  - **The change**:
    - `environment::check` runs the new `effects::check_planned`. The effect check's generated method takes the
      plan's flat inputs (`this.feeCents`, `this.floorCents`, `request.code`, `request.quantities`) and the
      environment's tables. It makes each root by the constructor its node names, every dependency of an
      application interface passed null and reached only through the stubs, and calls the method.
    - A constructor's exception is the outcome, as the call's is, so an input only one build's constructors accept
      is a difference.
    - `construction::flat_roots` reads the plan this way: a primitive leaf, a bounded array, the values stream's
      String (resolved, never null), or a dependency. A plan that bounds a String or an array otherwise than the
      claim's `max_array_length` is refused, never checked under another label.
    - A modelled call's String key is compared by its content (`environment::lower` accepts it). A call keyed by
      a String past the bound marks the log unresolved (a new mark bit, 128; the build tag moves to 256), since
      answering it as the default would couple two such keys.
    - Under a plan, a payload String is snapshotted by its content: its length, then its code units, in a block of
      the attempt. One past the bound leaves the result unresolved. The Spring path keeps its literal snapshots.
    - A payload path of a call of one argument is read from it: the frozen claim's `code` of
      `send(QuoteEvent event)` is `event.code`.
    - The domain is enforced as the regression check's gate does: its classes must be the plans', and a version
      whose plan makes more input objects than its bound, or whose code may make more objects in one call than its
      allocation bound (`spec::heap::allocations`, now `pub(crate)`), leaves the result unresolved.
    - Refused by name: an object inside another, a null or shared root, a factory, a setup sequence, a
      correspondence, and an observation other than the result, the exception and the effects.
    - The witness shows Strings and arrays (`request.code="VIP"`, `request.quantities={1, 2}`), and the JVM run
      passes them.
  - **Checks**:
    - The contract's E1 and E2 reach all sixteen of `expected.json`'s verdicts, with no refusal accepted, in about
      65 s:
      - `quote-claim`: `after` and `alias-to-copy` verified; `ignored-rate`, `wrong-query-key`, `wrong-prefix` and
        `helper-extra-field` refuted on the result, `missing-catch` on the exception, `wrong-branch-event` on the
        event; each witness replayed on a JVM.
      - `offer-claim`: `helper-extra-field` refuted on the result, the other seven verified.
    - The new `tests/environment_quotes.rs` (4 tests):
      - a wrong String key refuted with the environment naming `"STD"`, and an event on the wrong branch with its
        code shown by content;
      - a key and a payload String past the bound each left unresolved;
      - six refusals by name, and an allocation bound of 0 left unresolved;
      - a cached proof reused exactly, but not under a String and array bound of 3 or a never-null response.
    - Three sabotages fail them: keys compared by identity; no bound on a key; no bound on a payload String.
    - Changed tests, each a refusal of a String key that no longer holds:
      - `environment`'s unit tests now lower a String key, and load a `double` result's refusal instead;
      - `tests/effects.rs`'s void result keyed by a String topic is still refused by name, now as a void result
        where the call returns an object.
    - The integration check passes, and so do `environment` 16, `environment_responses` 8 and `observations` 12.
    - Two of the integration check's four runs failed only on `bmc::bits`' timing test, the flake already on the
      for-review list. It passed in the other runs and in six runs of the library's suite on their own, debug and
      release. This change touches no `bmc` code.
  - **For the for-review list**:
    - A planned subject runs no boundary walk: its effects are the claim's observed calls, and every call on a
      dependency goes through a stub, a modelled one or one that marks the log.
    - A constructor's exception counts as the outcome, which is stricter than leaving the input outside the domain.
    - The frozen claim's relative payload paths are read from the call's one argument, an interpretation.
  - **Docs**: `lib/README.md` (a new paragraph, the String key in the modelled-results paragraph, E2's sentence),
    the module docs of `environment` and `effects`.
  - **Next**: item 6's smaller requests, then item 7's README sentences. Then step 2's joint acceptance as jobs.
- 2026-11-08, **Phase 5 step 1, interface request 6 (its first part): a declared environment counted as a person's
  decision, and the stale help and docs**. The rest of item 6 is the next cycles.
  - **The reproducer**: `tests/environment.rs`'s new `compare_counts_a_declared_environment_as_a_persons_decision`.
    It failed before: under one modelled call, `compare`'s effort report counted 0 environment assumptions.
  - **The change**:
    - `compare::run` counts each modelled call of `Options::environment` as one environment assumption a person made.
      The other categories stay 0, and a run without one still counts none.
    - The help of `effects --environment` and `compare --environment` no longer says "Refused until it builds them":
      it says what a model may be and that the rest is refused by name. The same goes for `--plan` (`equivalence`,
      `prove`) and `prove --cache`, which says what the key covers and "not yet with `--plan`". The docs of
      `compare::Options::environment`, `property::Options::{cache, plan}`, `equivalence::Options::plan`, and the
      comment at `property::run`'s cache hook, are updated the same way.
    - The effect check's replay error no longer blames "the JVM runner's 16 words": `jvm_witness::run` sizes its
      stack from the arguments since item 1. `lib/README.md`'s E2 sentence about it is replaced, and the effort
      paragraph says how a declared environment counts.
  - **Checks**: `environment` 17 of 17, and the integration check passes (the contract 14 of 14, the unit tests 254,
    `compare` 1, `effects` 18, `foundations` 5, the Python suites).
  - **Next**: item 6's property cache, `reuse::property_store` taking `&mut Outcome`, a `reuse` field on
    `property::Outcome`, and `prove --cache --plan`'s guard lifted with an end-to-end test. Then `compare` with a
    plan per subject, the class reader's `CONSTANT_Utf8` code units and `ElementKind::String`'s bound. Then item 7.
- 2026-11-08, **Phase 5 step 1, interface request 6 (its property cache): `prove --cache --plan`**, and a property
  result's reuse in its outcome.
  - **The reproducer**: `tests/reuse.rs`'s new
    `a_planned_property_is_cached_and_an_edit_of_its_setup_method_alone_is_proved_again`. It failed before on
    `property::run`'s guard ("prove --cache with --plan: the property claim's key does not read the construction plan
    yet").
  - **The change**:
    - The guard is gone. The reuse stream's property key already reads the plan whole, and roots its makers and
      setup calls in the closure.
    - `property::Outcome` has a `reuse` field, `Reuse::Exact` with the key and the stored run's provenance on a hit,
      as `equivalence::Outcome` has.
    - `reuse::property_store` takes `&mut Outcome`. A result it can't store says why in the outcome's output, not on
      the standard error.
  - **Checks**:
    - The new test, on a counter whose `add` is the plan's setup call, under `this.step < 1000`:
      - `count <= 4 * step` is verified and stored, and its exact rerun is reused (`reuse`, no checker run, the same
        statement);
      - a build that edits only `add` is another claim. It is proved again, and refuted with the history
        `after the setup this.add(setup.0.n=4)`. Its rerun reuses the refutation, with that history;
      - the plan without the setup call is a third key;
      - a cache that is a file leaves the verdict and notes the failure in the output.
    - A sabotage fails it: with the setup calls taken out of the key's roots, the edit of `add` is answered by the
      stored proof.
    - `reuse` 12 of 12, `application_core_objects` 22, `value_parameters` 10 and `summaries` 40 pass. So does the
      integration check: the contract 14 of 14, the unit tests 254, `compare` 1, `effects` 18, `foundations` 5, and
      the Python suites.
  - **Docs**: `prove --cache`'s help (what the key covers, and no "Not yet with `--plan`"), `lib/README.md`'s plan and
    property-cache paragraphs, and the docs of `reuse` and `property::Options::cache`.
  - **Next**: the rest of item 6: `compare` with a plan per subject, the class reader's `CONSTANT_Utf8` code units,
    and `ElementKind::String`'s bound. Then item 7.
- 2026-11-08, **Phase 5 step 1, interface request 6 (the class reader's `CONSTANT_Utf8`): a string literal is read
  by its code units**, an isolated surrogate in its source included.
  - **The reproducers**, each failing before:
    - the new `tests/string_literals.rs` (2 tests). `"\uDBFF".charAt(0)` rewritten to the constant `0xDBFF` was
      refuted (`before: 65533`), and the JVM run "confirmed" it, because `relocate` had copied the old version's
      literal as `"�"`. A cached proof was reused for a build whose literal differs only in its surrogate
      (`"\uDBFE"`): the two bodies' shapes, and so the closures, were one.
    - `tests/effects.rs`'s new `a_payload_literal_with_an_isolated_surrogate_is_snapshotted_unit_for_unit`: a send
      whose topic changed from `"q\uDBFF"` to `"q\uDBFE"` was **verified**, a wrong proof, since both builds' classes
      held `"q�"`.
    - the values corpus's new `literalLoneSurrogate` and `literalsOfLoneSurrogates` cases (JVM, interpreter, own
      checker).
  - **The change**:
    - `classfile`: `Constant::Utf8` keeps the code units of an entry that isn't well-formed UTF-16, beside its text
      (U+FFFD in its place, which names and descriptors are still read by). `ConstantPool::utf16` gives the units.
      Such a String constant loads as the new `BootstrapArg::Units`; a reader that takes only `Str` refuses it.
      `decode_modified_utf16`, `encode_modified_utf16`, and the writer's `string_units` are new.
    - `relocate` keeps an entry's bytes unless renaming changes its text.
    - The interpreter interns literals by code units (`ldc`, `ConstantValue`, a concatenation's recipe and
      constants, a `typeSwitch` String label). The own checker's literal identity is its units (`ldc`,
      `ConstantValue`, concatenation). The effect check's payload literals are units, and its snapshot `ldc`s them
      as they are. `shared::shape`, and so a closure's digest, prints `Units([..])`, and a pure helper may load one.
    - The ldc record of `values::OPERATIONS` admits isolated surrogates and leaves nothing out. That record is part
      of the String model's identity, so every claim over the String model gets a new key: a cache miss, as a
      change of the model should be.
  - **Checks**:
    - A sabotage, `relocate` copying the entry as text again, fails all three new tests.
    - Inline: the library's unit tests 256 (2 new: `classfile`'s and `relocate`'s), `string_literals` 2, `values` 18,
      `effects` 19, `value_parameters` 10; alignment 34, application_core_objects 22, conformance 10, environment
      17, environment_quotes 4, environment_responses 8, heap 49, observations 12, reuse 12, reuse_summaries 14,
      skill 1, summaries 40.
    - The integration check passes: the contract 14 of 14, the unit tests 256, `compare` 1, `effects` 19,
      `foundations` 5, and the Python suites.
  - **Docs**: `lib/README.md`'s values paragraph, and `bmc`'s module table.
  - **Next**: the rest of item 6, `ElementKind::String`'s bound and `compare` with a plan per subject. Then item 7.
- 2026-11-08, **Phase 5 step 1, interface request 6 (`ElementKind::String`'s bound): a list of Strings bounds its
  elements**, and no variant of the shared interfaces drops a field it doesn't have.
  - **The reproducers**, each failing before:
    - `spec::plans`' `values_and_witnesses_round_trip_with_every_code_unit`: a list of Strings stated with its
      elements' bound (`{"kind": "string", "max_length": 4}`) read back **without** it. The unit variant
      `ElementKind::String` took the field and dropped it, though the enum denies unknown fields.
    - The new `a_variant_without_fields_refuses_one`: every unit variant of `spec/plans.rs` did the same, all eight
      (`ValueKind::String`, `ElementKind::String`, `WitnessValue::Null`, `Coupling::Query`, `Occurrence::PerCall`,
      `Returned::Void`, `OutcomeRelation::Equal`, `Effects::ReadOnly`). serde's `deny_unknown_fields` doesn't reach a
      unit variant of an internally tagged enum. So `{"kind": "per-call", "results": [0, 1]}` in an `--environment`
      file was a per-call choice with its script dropped, and `{"kind": "read-only", "fields": [...]}` a read-only
      summary: a mode stated and not read, which Phase 0's gate and the contract's adversarial checks forbid.
    - `tests/value_parameters.rs`' list refusals: a `List<String>` parameter was refused as "java.lang.String, which
      is no application class", not as a list of Strings.
  - **The change**:
    - `ElementKind::String { max_length }`: the elements' code units, bounded apart from the list's length. A bound
      left out is refused.
    - Each unit variant of `spec/plans.rs` is an empty struct variant (`Query {}`), which `deny_unknown_fields`
      reaches. The JSON is the same, so no frozen fixture or claim key changes for it.
    - `values::ListAdapter` still refuses a list of Strings by name, now for what is true: it makes lists of an
      application class's objects only, and no acceptance case needs a list of Strings, so no harness, witness or
      replay makes one. The list model's record says the same. That record is part of the list model's identity, so
      every list claim gets a new key, a cache miss.
    - A regression check's `List<String>` parameter is refused in the adapter's words, its elements bounded as a
      String parameter is (`--max-array-length`).
  - **Checks**: the library's unit tests 257; `values` 18, `value_parameters` 10, `reuse` 12, `environment` 17,
    `environment_responses` 8, `environment_quotes` 4, `reuse_summaries` 14, `application_core_objects` 22, `heap`
    49, `string_literals` 2, `alignment` 34, `conformance` 10, `observations` 12, `summaries` 40, `skill` 1. The
    integration check passes: the contract 14 of 14 (every frozen claim still reads), the unit tests, `compare` 1,
    `effects` 19, `foundations` 5, and the Python suites.
  - **For the for-review list**: a list of Strings stays refused by name. Its domain can now say its bound, but
    building it would be a capability of its own (harness, witness, replay), and no row needs it.
  - **Docs**: `lib/README.md`'s list paragraph and its interfaces paragraph, and the module doc of `spec::plans`.
  - **Next**: the last of item 6, `compare` with a plan per subject. Then item 7.
- 2026-11-08, **Phase 5 step 1, interface request 6 done (its last part): `compare --domains`, a kernel subject's
  declared domain**, a construction plan with its setup calls passed to the heap check as it is.
  - **The reproducer**: `compare` on the throttle family's `before` and `after-setup` (one unit short only once a call
    has taken some) **verified** `Throttle#allows` over the constructor domain, and had no way to state the setup
    plan's domain: `--domains` was an unknown argument, and `compare::run` built every kernel claim with
    `domain: None`. The new `tests/compare_domains.rs` refutes it under the declared plan, and failed before.
  - **Why a domain, not a bare plan**: a plan doesn't say the claim's classes, input and allocation bounds or label,
    which the heap check enforces and which the user decided twice for frozen claims (O3, `basket-first-claim`). So
    the file states each subject's whole domain, a frozen claim's `domain` as it is, `made_by: planned` carrying the
    plan. The tool doesn't choose those for a person.
  - **The change**:
    - `compare --domains FILE` (`compare::load_domains`, `Options::domains`): a JSON object from each new method
      (`pkg.Class#method`, as the report names it) to its `ObjectDomain`. A subject's kernel claim has that domain as
      it is, so `heap::check_with` enforces or refuses each part of it, as it does a frozen claim's.
    - A domain for a subject the run checks no claim of (an unchanged method, an entry point's handler, a misspelt
      name) is refused before any proof, naming the kernel's pairs. A subject that isn't a method, and a plan
      `construction::check_plans` refuses, are refused on reading.
    - Each declared domain counts as one domain restriction a person made, in the effort report.
    - **A serde hole closed with it**, as cycle 13's was in `spec/plans.rs`: `spec/mod.rs` had no
      `deny_unknown_fields` at all, so a domain stated with a misspelt option (`"nulable"`) was read as the domain
      without it. `ObjectDomain`, `VersionBounds`, `ObjectBounds` and `Construction` now refuse a field they don't
      have, and `Construction::FieldByField` is an empty struct variant (`FieldByField {}`), which the attribute
      reaches. The JSON is the same, and every frozen claim still reads.
  - **Checks**:
    - `compare_domains` 3 of 3:
      - the correct case and the defect: over the constructor domain `after-setup` is verified, labelled so; over the
        setup plan it is refuted on the result, the witness the whole history (`after the setup this.take(…)`) run
        on a JVM, the claim carrying the domain as declared and the effort counting one domain restriction; `after`
        is verified over it; over the constructor-only plan `after-setup` is verified, labelled "right after its
        constructor", and `one-short` refuted;
      - the cached evidence: an exact rerun under the setup plan is the stored result; the constructor-only plan is
        another key, checked again; an edit of the target under the setup plan is never answered by the stored
        proof;
      - the refusals: a domain for `Throttle#take` (unchanged) or a misspelt subject, a field-by-field domain (the
        kernel pair unsupported, "field by field"), and files with a misspelt domain field, a bounds field, a field
        under `field-by-field`, a subject that isn't a method, and a plan whose new version renames the receiver its
        setup call is made on.
        The command line reads the file, and exits 1 on the refutation.
    - Two sabotages fail them: the kernel claim ignoring the declared domain fails all three tests, and
      `ObjectDomain` without `deny_unknown_fields` fails the misspelt option.
    - Inline: the library's unit tests 257, `compare` 1, `heap` 49, `summaries` 40, `environment` 17, `effects` 19,
      `application_core_objects` 22, `value_parameters` 10, `values` 18, `reuse` 12, `reuse_summaries` 14,
      `environment_responses` 8, `environment_quotes` 4 (`preparation`'s benchmark ignored, as always). The
      integration check passes: the contract 14 of 14 (every frozen claim reads under the strict domain), the unit
      tests, `compare` 1, `effects` 19, `foundations` 5, and the Python suites.
  - **For the for-review list**: the proof cache keys the check a domain makes (its harness, the methods that make
    its inputs, the stated domain), not the domain's label or bounds, which the heap check enforces after the proof.
    So the constructor-only plan, which makes exactly the constructor domain's harness, and no declared domain share
    one stored proof, each result stating its own domain. Sound, since the proof is the same, but the brief's Phase 0
    says "the claim key covers the label": that holds of `spec::cache::key`, not of the regression key a heap check is
    reused under. The test states it.
  - **Docs**: `lib/README.md` (the `compare` usage, its paragraph and effort sentence, the plan paragraph, the
    interfaces paragraph), `compare --domains`'s help, and the docs of `compare` and `spec::ObjectDomain`.
  - **Item 6 is done.** **Next**: item 7, `lib/README.md`'s four sentences the streams couldn't rewrite. Then step 2's
    joint acceptance as jobs.
- 2026-11-08, **Phase 5 step 1, interface request 7 done: `lib/README.md`'s sentences the streams couldn't rewrite**,
  each checked against the code first. **Step 1's interface requests are all done.**
  - **The four sentences**:
    - Limits' "Property proofs (`prove`) are still over static methods": `property::run` takes an instance method on
      a receiver made by its constructor (`construction::receiver`) or by a `--plan`'s root `this` and setup calls. It
      now says so, pointing at **An ordinary receiver**.
    - "How a regression proof works", step 5's record rule: "an input a constructor of either version rejects is
      outside the statement" now says an input both reject is outside, and one only one version's constructor rejects
      is a difference on the `exception`, pointing at **A narrower constructor** (`Layout::compares_admission`). The
      `--before-arguments` sentence keeps the old rule, as the code does.
    - The effect-trace paragraph's "a handler that uses a modeled call's result is refused until modeled return values
      come": such a call is refused only without a model of its results, and answered from one (**Modelled
      results**).
    - The own checker's fragment: arrays of references' "cells hold objects or `null`" now names the symbolic
      reference an `aastore` stores as it is when every object it may be is of the element type, and the split
      otherwise, as `bmc`'s module table already did.
  - **Two more stale clauses, the same kind**: the fragment's "strings and other objects only as opaque values" (the
    own checker's Strings have content, the paragraph below it), and Limits' "the tool's own checker covers methods
    over integers, arrays of them and records of them, without other objects", which now names constructor- and
    plan-made objects, bounded Strings and the short immutable lists.
  - **The refusal itself was stale too**: `effects::check` refused an unmodelled used result with "a modeled return
    value comes after the narrow case". It now says the call has no model of its results, and how to give it one (a
    `CallModel`, as with `--environment FILE`). The reproducer: `tests/effects.rs`'s
    `a_handler_that_uses_a_modeled_calls_result_is_refused_by_name` asks for that and no "comes after"; it failed
    before. The brief's [Where it starts from](#where-it-starts-from) row "Effects" quotes the old message, as the
    recount at the merge read it.
  - **Checks**: `effects` 19 of 19, `skill` 1 (it reads the README), `environment` 17, `environment_quotes` 4,
    `environment_responses` 8. The integration check passes.
  - **An infrastructure failure, recorded apart**: the integration check's first run failed in
    `llm-dlc/tools/test_performance.py` (3 of 3 runs of the suite, none alone), in no file this cycle touched. The
    cause was `test_an_r2_error_names_its_code_and_no_key`'s `HTTPError`, never closed, whose `ResourceWarning` was
    raised by the garbage collector inside the next test, which compares its captured stderr. The test now closes it
    (`addCleanup`); no assertion changed. The suite then passes 3 of 3, and so does the integration check.
  - **Next**: step 2's joint acceptance at the merge, as jobs: J1 (the quote family composing O, V, E and R), J2 (the
    new native claims with JBMC unavailable), and the H and L families, each correct change proved, each defect
    refuted with its witness replayed, and exact reuse, helper reuse and invalidation shown. Then step 3's examples
    with `lib/tests/integration.rs`, J4 and the for-review list.
- 2026-11-08, **Phase 5 step 2: the joint acceptance at the merge, as a job** (verification pending), and a gap it
  found.
  - **The test**: the new `lib/tests/application_core_joint.rs`, one test per row:
    - J1, the quote family: `quote-claim` and `offer-claim` through the planned effect check, `Codes#vip` as a plain
      regression, `fee`'s read-only summary, and `units`' property under the cache;
    - H, the throttle: both frozen claims, `allows` as a regression and as a property;
    - L, the basket: the three frozen claims, `total` and `clearAll` as regressions within 3;
    - J2: the native claims under `--engine auto` with JBMC unavailable.

    Unlike the integration contract, it accepts no refusal:
    - every case must reach `expected.json`'s verdict;
    - each refutation must be on the observation it names, its witness replayed;
    - each verified result must have every observation of its claim preserved.

    Each frozen claim and plain regression runs twice under one proof cache:
    - the rerun must be the stored result under the same key;
    - every build whose verdict differs from `after`'s must have another key, never answered by a stored result.

    Invalidation is shown three ways, each another key, checked again: a modelled outcome less (`quote-claim`
    without `RateUnavailable`), a smaller list bound (`basket-total-claim` within 2), and another assertion.

    J2's `--confirm` must be explicit: `allows` left unconfirmed ("jbmc is not installed"), and `vip` and `total`
    not asked (a String, a list). Each run prints its evidence record (`evidence: {json}`) into the job's log.
    `basket-first-claim`'s `copied-first` is held to the allocation gate's outcome, as in the contract, until the
    user decides.
  - **The job**: `20261108-180246-application-core-phase-5-step-2-the-join`, at this commit. One step per row, then
    J2's guard: every step runs with a `jbmc` first on `PATH` that records being called, and the last step fails if
    it was. That covers the claim checks, which take no `jbmc` option.
  - **Run inline first**, so that a bug of the test's own costs no attempt:
    - H passed in 12 s, L in 14 s and J2 in 7 s (debug), and the recording `jbmc` was never called.
    - J1 was run in two parts. The planned claims and `vip`'s regressions took 55 s, and the invalidation, the
      summary and the property cache 62 s.
    - Two assertions of the test's own were wrong and were fixed:
      - a confirmation JBMC was asked for names it as `JBMC`, with no version;
      - the heap check stores the proof and applies the allocation gate again to a stored one, so an unresolved
        rerun may be a hit.
  - **Found: J1's O2 and R2 parts are refused on the quote family**, which the contract hid by accepting the
    streams' refusals. `checked-claim` is refused by the heap check ("a construction with dependencies"), and `fee`
    as a plain regression by the regression check ("only a concrete class made by its constructor"). The receiver's
    constructor takes the service's three interface dependencies, which neither method reaches. Only the effect
    check's planned harness makes such a receiver: each dependency null, reached only through the stubs.
    - Both are in the test's `j1_o2_and_r2_a_receiver_with_dependencies`, ignored with that reason and not in the
      job. It is the reproducer of the next piece of work.
    - O2 and R2 pass on their streams' own fixtures (receivers without dependencies), so on Q they are **partial**
      until then.
    - The refusal's own words are stale too ("the objects stream builds it").
  - **The contract tightened** (`tests/application_core.rs`): O1's property and R1's cache now reach their verdicts,
    so they accept no refusal; R1's rerun must be the stored result. O2's claim and R2's regression still accept
    theirs, until the gap above is closed.
  - **For the J4 report**: under the cache, an edit outside a claim's closure is answered by `after`'s stored
    result. Six of `offer-claim`'s eight builds were, seven of `vip`'s, and three or four of each basket claim's.
  - **Stale help**, the same kind as item 7: `--engine`'s help (`equivalence`, `prove`) said the own checker was for
    "integers, arrays of them and records". It now names constructor- and plan-made objects, bounded Strings and
    short immutable lists, as `lib/README.md`'s Limits do.
  - **Checks**: the integration check passes, and so does the tightened contract.
  - **Next**: make a receiver whose constructor takes dependencies in the heap and regression checks, each
    dependency null and refused by name where the method's closure reaches it, so that `checked-claim` and `fee`
    reach their verdicts. The ignored test is un-ignored and goes in a job of its own. Then step 3's examples with
    `lib/tests/integration.rs`, J4 and the for-review list, with this job's results read once they are collected.
- 2026-11-08, **step 2's job passed**: `20261108-180246-…` at `388dfe54`, 6 of 6 steps in 5m04s (peak 1.8 GiB),
  recorded by the verification loop (`zutylomy`). J1 (its planned claims, `vip`, the invalidation, `fee`'s summary and
  `units`' property cache), H, L and J2 reach their verdicts on the merged revision with no refusal accepted, and the
  recording `jbmc` was never called. `basket-first-claim`'s `copied-first` was held to the allocation gate's outcome.
- 2026-11-08, **Phase 5: a receiver whose constructor takes dependencies, each passed null** (verification pending),
  so J1's R2 part reaches its verdicts on the quote family.
  - **The reproducer**: step 2's ignored `j1_o2_and_r2_a_receiver_with_dependencies`. Its `fee` half, now
    `j1_r2_a_receiver_with_dependencies`, failed before on "only a concrete class made by its constructor", and it is
    un-ignored. So did `tests/application_core_objects.rs`'s `Timer#since`, whose clock it never reads.
  - **The change**:
    - A constructor argument of an application interface is a dependency, in the regression check (`made_of`) and in
      a plan's node (`PlanValue::Dependency`, its path and class checked against the constructor). It is
      `harness::RecordType::dependencies`, passed `null` by the harness, the interpreter's replay and the witness
      (`new QuoteService(0, -100, null, null, null)`, typed as `null`). The domain names it (`clock: null, a dependency
      of deps.Clock`). It is never an input object, a class of the claim, or a cache root.
    - **Refused by name where reached**: before any helper proof, cache lookup or proof, `equivalence` and `prove`
      walk each version's closure (`construction::dependency_reached`). A method that calls one on the interface, or
      reads or writes a field of its type (a null test, a hand-off), refuses the target in that version's words. A
      null stands for no object a run could have. Only the effect check answers a dependency, through its stubs.
    - **Found on the way: a package-private target can't be replayed on a JVM.** `fee`'s refutation was found
      (before 0, after -1), and then reported as the interpreter's error. The harness, in the unnamed package, got
      `IllegalAccessError` in both versions, and the run read that as agreement: `relocate::opened` opens fields,
      constructors and static methods only. `relocate::opened_with`, used by `jvm_witness`, now also makes public a
      protected instance method, and a package-private one where no class of another package that extends its class
      declares the same method, so no override changes (JVMS 5.4.5). One that might keep its access, and the access
      error leaves the witness unreported, as before: a missing verdict, never a wrong one. `opened` itself is
      unchanged.
  - **Checks**:
    - J1's R2 reaches `expected.json`'s eight verdicts with no refusal accepted: `after` and six defects verified, and
      `helper-extra-field` refuted with its witness run on a JVM. Each rerun is the stored result under its key.
    - The new `tests/dependencies.rs`, 3 tests:
      - a package-private `Timer.since` rewrite proved with its clock null, and an off-by-one refuted and run on a
        JVM, in the regression and in the property check;
      - a call, a field test, a hand-off and an abstract class refused by name, and a plan's dependency path and
        class checked;
      - a cached proof reused exactly, a build that reaches the clock refused before the lookup, and an edit of the
        constructor another key.
    - `relocate`'s new unit test checks which instance methods `opened_with` opens.
    - Two sabotages fail them: without the reachability check, the refusal and cache tests fail; with no
      package-private method opened, the JVM run fails the refutation.
    - The integration check passes: the contract 14 of 14, the unit tests 258, `compare` 1, `effects` 19,
      `foundations` 5, and the Python suites. So do `application_core_joint`'s J1 and R2 (release), and every other
      binary but `integration.rs` (JBMC): alignment 34, application_core_objects 22, compare_domains 3, conformance 10,
      dependencies 3, environment 17, environment_quotes 4, environment_responses 8, heap 49, observations 12, reuse 12,
      reuse_summaries 14, skill 1, string_literals 2, summaries 40, value_parameters 10, values 18.
  - **The contract tightened**: R2's `fee` row accepts no refusal. O2's `checked-claim` accepts only the values'
    refusal, which is its gap now.
  - **The job**: `20261108-185910-application-core-phase-5-a-receiver-whos`. It runs J1's R2 and the dependency
    tests, with the recording `jbmc` guard.
  - **J1's O2 is still refused**, by the next gap: `checked-claim`'s request carries a String code. The heap check's
    plan doesn't make an adapted value inside a node, and the regression check neither makes a String constructor
    argument nor observes a String field (`fields_of`). The joint test's
    `j1_o2_a_receiver_with_dependencies_and_a_request_with_a_string` is ignored with that reason, and is its
    reproducer.
  - **For the for-review list**: the JVM run's opening of instance methods changes what any JVM replay can call, so
    step 3's example reruns are at a revision that has it.
  - **Docs**: `lib/README.md` (a new paragraph **A receiver with dependencies**; the receiver's and the plan's refusal
    lists no longer name a dependency), the docs of `construction`, `relocate::opened_with` and `jvm_witness`.
  - **Next**: a String inside an object for the regression and heap checks: the String adapter's value as a
    constructor argument (a plan's adapted node argument, and `made_of`'s), and a String field compared by content.
    Then `checked-claim` reaches its verdicts, and the ignored test goes in a job of its own. Then step 3's examples
    with `lib/tests/integration.rs`, J4 and the for-review list.
- 2026-11-08, **the dependencies job passed**: `20261108-185910-…` at `c99d01a3`, 4 of 4 steps in 3m27s (peak
  2.3 GiB), recorded by the verification loop (`usommrqt`). J1's R2 (`fee` on every quote build) and the three
  dependency tests pass on the own checker, and the recording `jbmc` was never called.
- 2026-11-08, **Phase 5: a String inside an object**, for the regression and heap checks, so that J1's O2 part
  (`checked-claim`) reaches its verdicts on the quote family (verification pending).
  - **The reproducer**: `tests/application_core_joint.rs`'s `j1_o2_a_receiver_with_dependencies_and_a_request_with_a_string`,
    ignored since the dependencies piece, is un-ignored. It failed before on the request's String code, an adapted
    value inside a node. So did each test of the new `tests/object_strings.rs`, on a constructor's String argument
    ("a constructor's arguments must be primitives, …").
  - **The change**:
    - A constructor's String argument is a leaf of its construction (`harness::is_leaf`), in `made_of` and in a plan's
      node (`PlanValue::Adapted` of a String, named by its path, never null). It is a value of the String adapter, as
      a String parameter is: every content up to the check's bound (`--max-array-length`, or the claim's
      `max_array_length`; a plan's String bounded otherwise is refused), the one object both versions get.
    - The domain names the bound (`each String of its construction of ≤ 4 code units, not null`), and the statement
      states `maxValueLength` and the String model. The witness writes the String as a literal (`new Request("a", 0)`),
      and it is run on a JVM.
    - A String field is `harness::FieldKind::String`, compared by content: null in both, or `String.equals`, which the
      own checker models. Never by identity. The witness shows it by content (`Request{code="V", count=1}`).
    - JBMC is not asked, as for a String parameter. A property check refuses a String inside an object by name, since
      its expressions have no String terms. So does a list inside a node.
  - **Checks**:
    - The new `tests/object_strings.rs`, 3 tests:
      - four rewrites proved (a `startsWith` by `charAt`, `equals` turned round on a receiver's String, a result whose
        code is a concatenation, a field set to a copy), and three defects refuted on what they change, each run on a
        JVM;
      - the refusals by name, a planned rewrite proved and its defect refuted;
      - an exact rerun reused, but not under another bound or after an edit of the constructor that takes the String.
    - Two sabotages fail them: a String field compared by identity, and no String bound given to the checker.
    - J1's O2 reaches `expected.json`'s verdicts, with no refusal accepted, on every build but `alias-to-copy`; each
      rerun is the stored result.
    - `tests/values.rs`' resolution test now expects the request's String code taken under this tool's model, and
      still refused under another.
    - Three tests named a refusal that no longer holds, and now name what does:
      - `tests/heap.rs`'s `Tagged` fixture had a String field as its unsupported field. It is now an `Object`
        field, still a named gap, in both its regression and its property test;
      - `tests/value_parameters.rs`'s list-element refusal names a String among the fields left out;
      - `tests/values.rs` (above).
    - The integration check passes: the contract 14 of 14, the unit tests 258, `compare` 1, `effects` 19,
      `foundations` 5, and the Python suites. So does every other binary but `integration.rs` (JBMC), in release:
      alignment 34, application_core_joint 6 (all, J1's O2 among them), application_core_objects 22, compare_domains
      3, conformance 10, dependencies 3, environment 17, environment_quotes 4, environment_responses 8, heap 49,
      object_strings 3, observations 12, reuse 12, reuse_summaries 14, skill 1, string_literals 2, summaries 40,
      value_parameters 10, values 18.
  - **For the user: `checked-claim`'s allocation bound**, the same kind of decision as `basket-first-claim`'s.
    - The claim bounds each version's allocations at 1. `alias-to-copy`'s code may make 3 objects in one call: the
      copy, the `IllegalArgumentException` its constructor may throw, and the method's own.
    - So the allocation gate leaves it unresolved ("may make 3 objects in one call, more than the claim's allocation
      bound of 1"), where `expected.json` says refuted on `identity:result==request`. The gate stays as it is.
    - Until the user decides, the contract and the joint test hold that one case to exactly the gate's outcome, and
      every other case to `expected.json`.
    - The options:
      1. bound the claim's allocations at 3 in each version. Then the case is refuted on the identity alone, its
         witness run on a JVM, and `after` stays verified, as the joint test shows;
      2. keep 1, and expect `unresolved` for `alias-to-copy`: a defect outside the claim.
  - **The contract tightened**: O2's `checked-claim` accepts no refusal.
  - **The job**: `20261108-195222-application-core-phase-5-a-string-inside`. It runs J1's O2 and the String tests, with the recording `jbmc` guard.
  - **Docs**: `lib/README.md` (a new paragraph, **A String inside an object**; the receiver's and the plan's refusal
    lists), `--plan`'s help (`equivalence`, `prove`), the docs of `harness::is_leaf`, `FieldKind` and `construction`.
  - **Next**: step 3's examples with `lib/tests/integration.rs`, one job per app, at a revision that has the JVM
    run's opening of instance methods. Then J4 and the for-review list. Two user decisions are open, the allocation
    bounds of `basket-first-claim` and `checked-claim`; neither blocks the rest.
- 2026-11-08, **Phase 5 step 3: the existing examples at the merged revision, as four jobs** (verification pending),
  one per app as the cleanup merge's reruns were, at this commit. It has `relocate::opened_with` (`szqvvxuv`) and every
  Phase 5 piece so far.
  - **Which examples**: 190–196 and the cleanup merge's reruns (150–152, 160–161, 170–172). The streams touched none.
    No file under `examples/` changed since the cleanup merge but `examples/schema/` and `examples/tools/`, so "the
    examples the streams touched" adds none.
  - **The jobs**, each step running even if one fails:
    - `20261108-195650-application-core-phase-5-step-3-shop-s-e`: build.py on 190–196 (`compare`, native, a fresh
      proof cache). Expected: 190 and 195 verified, 191–194 violation, 196 unverifiable.
    - `20261108-195650-application-core-phase-5-step-3-crosscut`: 150–152 and 160–161 (`equivalence`, native,
      `--gaps strict`). Expected: 150, 152 and 160 verified, 151 and 161 violation.
    - `20261108-195650-application-core-phase-5-step-3-deliveri`: 170–172 (`effects`, native). Expected: 170 verified,
      171 and 172 violation.
    - `20261108-195703-application-core-phase-5-step-3-lib-test`: `lib/tests/integration.rs` as it is, 65 tests, none
      ignored, JBMC's included. The merge's and the later cycles' inline checks ran every other binary, never this
      one. It compiles at this commit.
  - **To read with the results**: the shop examples' notes say what stays unresolved in each run ("the instance method
    `Quote#quantity`", string concatenation). The streams widened what `compare`'s kernel claims check, so a part
    other than the subject may now be checked. The subject's verdict is what must hold. A changed part is a note to
    update in that example's `example.json`, not a failure.
  - **Next**: step 4, J4's cost report. The reuse stream reported J4's figures from job `20261108-114325` (`tvrqpusw`)
    at its own commit, so this checks what holds at the merge before running anything new. Then step 5's for-review
    list, with the step 3 jobs and `20261108-195222` read once they are collected. The two allocation-bound decisions
    are still open.
- 2026-11-08, **Phase 5 step 4: J4's cost report at the merged revision, as a job** (verification pending).
  - **What holds of the reuse stream's figures**: its report (`lib/benchmark/preparation/j4.json`, job
    `20261108-114325`, `tvrqpusw`) was taken at its own commit `283aa75d`. Since then the library changed in 33 files
    of `lib/src`, and the benchmark by one line (`compare::Options` gained `domains`). So its figures are the stream's,
    not the merge's. They stay as recorded.
  - **The smoke run, inline** (debug, 1 repeat, 61 s, passed). It got the stream's verdicts and cache outcomes in all
    six scenarios:
    - `after`, the unrelated edit and the helper rewrite verify `POST /quotes`, `discount`, `total` and
      `withQuantity`. `POST /quotes/text` is unresolved, and `Money#cents` and `Quote#quantity` unchecked;
    - `offset` refutes the route and `total`;
    - the reruns and the unrelated edit prove nothing again;
    - the helper rewrite proves `total` again on a new proof of `discount`.
  - **The job**: `20261108-200158-application-core-phase-5-step-4-j4-s-cos`, the stream's step unchanged (release,
    7 repeats) at this commit. It writes `j4-merge.json` and `.md` beside the stream's report.
  - **Next**: step 5's for-review list, with the pending jobs named. Read their results once they are collected: step
    3's four, `20261108-195222` (finished, passed, not yet collected) and this one. Then J4's figures go into the
    list. The two allocation-bound decisions are still open.
- 2026-11-08, **Phase 5 step 5: the for-review list**, at `loozqmzm` (`9a1b3b3a`). Five of the six jobs it names have
  finished, all passed, and wait for the verification loop to collect them. Their results are read here from its
  runner's state: their `result.json`, logs and output files. J4's rerun is still running.
  - **Step 3's examples kept their expected outcomes**. All four jobs ran at `c1bc0820`:
    - shop `20261108-195650-…-shop-s-e`, 31 s: 190 and 195 verified, 191–194 violation, 196 unverifiable;
    - crosscut `-crosscut`, 21 s: 150, 152 and 160 verified, 151 and 161 violation;
    - deliveries `-deliveri`, 14 s: 170 verified, 171 and 172 violation;
    - `20261108-195703-…-lib-test`, 2m19s: `lib/tests/integration.rs` 65 of 65, JBMC's tests included.

    Compared with the recorded results, each conclusion is unchanged. Only some wording, claim digests and timings
    differ:
    - the constructor assumption now says "an input both versions' constructors reject", step 5's rule since item 7;
    - `lastAfter`'s helper claim has a new key.

    One part changed, in all seven shop examples. `shop.Quote#quantity` is still unverifiable, now for a different
    reason: "the receiver is made differently in the two versions" (`Quote(long, int)` before, `Quote(Money, int)`
    now). It was refused as an instance method before. Each example's note "What stays unresolved in every example of
    the set" names the old reason. It is updated once the job is collected, so that the collected README and the
    note agree.
  - **The rows on the merged revision** (the contract's mandatory rows, then the stream items V3, E3 and R3):
    - **G0, passes.**
      - Phase 0's gate refuses every unread option, with its reproducers. The contract's G0 verifies the kernel's
        own claim and refuses each unsupported policy.
      - The cleanup merge's reruns passed (`20261107-215001-…`, four jobs), and step 3 reran them at the merged
        revision.
      - The integration check passed on the merge.
      - VF-015's job `20261108-024648-…` failed at step 5 (a JBMC class-initializer guard, not the harness fix), and
        the user deferred it.
    - **O1, passes.**
      - The objects stream's job `20261108-045000-…`.
      - Step 2's job `20261108-180246-…`: H's `allows` as a regression and as a property, verified and refuted with
        replay, no refusal accepted.
    - **O2, partial: one case waits on the user.**
      - The stream's jobs `20261108-072230-…` and `-074116-…`.
      - On the quote family: J1's O2 (`checked-claim`) in job `20261108-195222-…`, finished and passed, not yet
        collected.
      - Every build reaches `expected.json`'s verdict but `alias-to-copy`. That one is held to the allocation gate's
        unresolved outcome until the user decides `checked-claim`'s bound (1 or 3; see that entry).
    - **O3, passes.** Step 2's job, H: both frozen throttle claims, under the user's bound of 1. The setup-domain
      refutation is replayed with its whole history, and the constructor-only claim is labelled so.
    - **V1, passes.** Step 2's job, J1's `Codes#vip`: the rewrite proved, `wrong-prefix` refuted on content and run
      on a JVM. Also job `20261108-195222-…`'s String-inside-an-object tests.
    - **V2, partial: one case waits on the user.**
      - Step 2's job, L: `basket-total-claim`, `basket-clear-claim`, and `total` and `clearAll` within 3.
      - `basket-first-claim`'s `copied-first` is held to the gate's unresolved outcome until the user decides its
        bound (0 or 2).
      - Unsupported implementations are refused by name (`tests/value_parameters.rs`).
    - **E1 and E2, pass.** Step 2's job, J1: `quote-claim`'s and `offer-claim`'s sixteen verdicts through the
      planned effect check, under one declared environment. The DTO is made by the shared construction plan.
    - **R1, passes.** Step 2's job: the contract's R1, and J1's `units` property under the cache, with an exact rerun
      reused.
    - **R2, passes.** Step 2's job (J1's `fee` summary), and job `20261108-185910-…`: `fee` on every quote build,
      with a receiver whose dependencies are null.
    - **J1, partial**, by O2's one case. Every other part reaches its verdicts on the real combined revision, with
      no adapter written by hand. Each verified result has every observation of its claim preserved (step 2's job,
      `20261108-185910-…`, `20261108-195222-…`).
    - **J2, passes.** In step 2's job and the two after it, every step ran with a recording `jbmc` first on `PATH`,
      and it was never called. `--confirm` is explicit: `allows` is unconfirmed ("jbmc is not installed"), and the
      String and list claims are not asked.
    - **J3, passes.**
      - The reuse stream's key over the new claim parts (`tests/reuse.rs`, in the contract).
      - Step 2's job's three kinds of invalidation, each another key, checked again: a modelled outcome less, a
        smaller list bound, and another assertion.
      - Each build whose verdict differs from `after`'s gets another key.
    - **J4, passes on the merged revision.** Job `20261108-200158-…` (at `9a1b3b3a`, passed, 3m43s, peak 1.9 GiB)
      reran the reuse stream's step unchanged and wrote `lib/benchmark/preparation/j4-merge.{json,md}`. The stream's
      own report, job `20261108-114325-…` at its `283aa75d`, stays as recorded in `j4.*`. Release, medians of 7, for
      these fixtures only.
      - **The verdicts and cache outcomes are the stream's**, in all six scenarios: the benchmark's assertions held.
        `after`, the unrelated edit and the helper rewrite verify `POST /quotes`, `discount`, `total` and
        `withQuantity`. `offset` refutes the route and `total`. In every scenario `POST /quotes/text` is unresolved,
        and `Money#cents` and `Quote#quantity` unchecked.
        - The two reruns and the unrelated edit: 5 exact hits of 5.
        - The helper rewrite: 1 hit (`withQuantity`), and `total` proved again on a new proof of `discount`.
        - The helper proofs' keys differ from the stream's (`discount`'s cold key `sha256:1ac7558b…`, was
          `776dae08…`). That is expected, since the binary changed (13.7 MB, was 12.9 MB).
      - **Times in process, merge (stream)**:

        | Case | ms | Solving | After the runs (replay, JVM) | Before each proof |
        |---|---|---|---|---|
        | cold | 62.9 (71.5) | 44.0 (50.0) | 9.2 (10.2) | 6.2 (6.8) |
        | unchanged rerun | 9.2 (9.5) | 0 | 0 | 5.7 (6.1) |
        | unrelated edit | 9.3 (8.9) | 0 | 0 | 5.9 (5.8) |
        | helper rewrite | 71.1 (79.2) | 52.0 (59.0) | 8.6 (9.4) | 6.4 (6.8) |
        | defect, cold | 1439.2 (1450.7) | 1350.0 (1364.0) | 35.2 (53.9) | 48.7 (48.0) |
        | defect, rerun | 51.6 (31.7) | 0 | 0 | 47.2 (27.3) |

        - Almost all of the defect's cold time is solving `total`'s refutation, as at the stream (1300 ms of it).
        - The rerun of the defect is no slower at the merge. Its repeats are bimodal in both reports, about 32 ms or
          about 52 ms each, depending on `discount`'s "before" (about 22 ms or 42 ms). The stream's median fell in
          the fast mode (5 of 7), and the merge's in the slow one (4 of 7).
        - The repeated stages are within a millisecond of the stream's. Opening the JDK's image is 7.70 ms the
          first time and 0.07 ms after (R3's shared table). The binary's digest takes 38.3 ms, once per process.
      - **The finding is unchanged**: an exact rerun or an unrelated edit costs no solving, and preparation before
        each proof stays the larger part of a cached run.
    - **V3, passes.** It ran inline only: `tests/values.rs`, the evidence records, and value domains resolved before
      the key.
      - VF-023 was closed by job `20261108-141443-…`, its last attempt.
      - The values stream's three VF-023 probe jobs passed.
    - **E3, passes.** Inline, `tests/environment_responses.rs` 8 of 8. On Q, `offer-claim`'s nullable `Offer` is in
      step 2's job.
    - **R3, done** with a justified outcome: the JDK image's class table shared within the process. Jobs
      `20261108-060410-…` and `-063259-…`.
  - **Deferred by the timebox**: none, in any stream or in Phase 5. **Deferred by the user**: VF-015's step 5.
  - **For the user**: the allocation bounds of `basket-first-claim` (0 or 2) and `checked-claim` (1 or 3). Each
    decides one case of V2 and O2, and nothing else waits on it.
  - **Unsupported, refused by name**. Each was recorded in its piece above.
    - Strings:
      - a String parameter or field in a property check, which has no String terms;
      - a String result;
      - a String plan root;
      - a null String;
      - a list of Strings (its domain can state the bound, but nothing makes one);
      - string concatenation at a route (`POST /quotes/text` in 190–196);
      - JBMC on a String or list claim (`--engine jbmc` refused, `--confirm` not asked).
    - Lists:
      - a raw list, a wildcard's or a type variable's;
      - elements made from arrays or objects;
      - a list with `--before-target`, `--before-arguments`, `--results-agree-when` or a correspondence;
      - `--nullable` or `--may-alias` of a list;
      - a list inside a node, or as a property check's parameter.

      Every made object is constructed whether the list holds it or not, which is sound but stricter.
    - Objects:
      - a result the check doesn't follow (`Object`, an interface);
      - a receiver made differently in the two versions (`Quote#quantity`);
      - a method of a class the old build lacks (`Money#cents`);
      - a dependency the method's closure reaches, and an abstract class as a dependency;
      - array fields in property expressions;
      - a package-private method that an override in another package might change, whose JVM replay is left
        unreported.
    - Environment:
      - a DTO with a method, an object or static field, `hashCode` on it, or a field written;
      - a planned subject with an object inside another, a null or shared root, a factory, a setup sequence, a
        correspondence, or an observation other than the result, the exception and the effects;
      - a `double` result.
  - **Found, for review**:
    - The merge entry's list stands (the static-field writes, `Character` classification, the surrogate render, the
      `List12` name, `List.of(E...)`'s evidence record, the checker's time limit, an unreplayable property witness,
      `bmc::bits`' timing flake, the coupling-dependent reordering, the array helper's out-of-bounds outcome,
      `jimage.rs`'s ownership, a route's effect proof not using helper evidence).
    - Phase 5 added:
      - The heap check's proof cache keys the harness, not the domain's label or bounds. Phase 0's "the claim key
        covers the label" holds of `spec::cache::key` only.
      - A planned subject runs no boundary walk.
      - A constructor's exception counts as the outcome.
      - The frozen claim's relative payload paths are read from the call's one argument.
      - The JVM run opens instance methods (`relocate::opened_with`).
      - `tests/reuse.rs` asserts the frozen key for two resolved evidence records.
      - `Money#cents` and `Quote#quantity` are unchecked in J4's scenarios, for the reasons above.
  - **Optional, left out**: reuse's R4 (the local write summary); objects' factory routes and reference arrays;
    values' extra String or list method; environment's clock and response script.
  - **Pending jobs**:
    - finished and passed, not yet collected: `20261108-195222-application-core-phase-5-a-string-inside`, and
      `20261108-195650-application-core-phase-5-step-3-shop-s-e`, `-crosscut`, `-deliveri`,
      `20261108-195703-application-core-phase-5-step-3-lib-test`;
    - running: `20261108-200158-application-core-phase-5-step-4-j4-s-cos`.
  - **Next**, once they are collected:
    - update the seven shop examples' note on `Quote#quantity`;
    - read job `20261108-200158-…`'s figures into J4's row, comparing them with the stream's.

    Then Phase 5's criterion is met, apart from the two user decisions, which leave O2, V2 and J1 partial with
    their evidence.
- 2026-11-08, **the six jobs were collected while the list above was being committed**, all passed, in the
  verification loop's `yxtmunzo` ("Record verification results: …"). It committed the working copy this brief's edit
  was in, so the list is in that commit, not in its own `zpsmsyyp`. J4's rerun wrote
  `lib/benchmark/preparation/j4-merge.{json,md}`. **Next**: the two items the list leaves:
  - the shop examples' `Quote#quantity` note;
  - J4's figures at the merge, compared with the stream's.
- 2026-11-08, **the shop examples' `Quote#quantity` note updated**, in 190–196's `example.json` (note 3, "What stays
  unresolved in every example of the set"), their pages re-rendered with `build.py --render-only`. It now gives the
  reason the collected results give (`shop-s-e`'s job, in each `result.json` and `verifier-output.txt`): the receiver
  is made differently in the two versions, `Quote(long, int)` before and `Quote(Money, int)` now, and says it was
  refused as an instance method before the merge. The other two parts it names (`POST /quotes/text`, `Money#cents`)
  are unresolved for the reasons it gives. **Next**: J4's figures at the merge (`j4-merge.*`, job
  `20261108-200158-…`), compared with the stream's, into J4's row.
- 2026-11-08, **J4's figures at the merge, in J4's row** of the for-review list above. Job `20261108-200158-…` reached
  the stream's verdicts and cache outcomes in all six scenarios, with times within a few milliseconds of the stream's.
  The one larger gap, in the defect's rerun, is the same two timing modes split differently over the repeats. J4
  passes on the merged revision.
  - **Phase 5's criterion is met**, and the list names every row's state:
    - G0, O1, O3, V1, E1, E2, R1, R2, J2, J3 and J4 pass, and the stream items V3, E3 and R3 too;
    - O2, V2 and J1 are partial, with their evidence: V2 by `basket-first-claim`'s `copied-first`, and O2 and J1 by
      `checked-claim`'s `alias-to-copy`, each held to the allocation gate's unresolved outcome.
  - No job is pending. Nothing the timebox deferred, or optional left out, is taken up.
  - **What needs the user**: the two allocation bounds. Once they are decided, applying them is one piece of work,
    a job included. Either way the three rows close: as passing, or with the case expected unresolved.
    - `basket-first-claim`: 0 or 2;
    - `checked-claim`: 1 or 3.
- 2026-11-08, **the two allocation bounds, decided by the user: 2 and 3**, as O3's was, the gate counting the
  exceptions a call may throw. `golden/basket-first-claim.json` bounds each version's allocations at 2 (was 0), and
  `golden/checked-claim.json` at 3 (was 1). `expected.json` is unchanged; the gate stays as it is.
  - **No case is held any more**: the contract's O2 and V2 rows (`lib/tests/application_core.rs`) and the joint
    test's J1 (O2) and L (`lib/tests/application_core_joint.rs`) hold every case to `expected.json`, so
    `copied-first` and `alias-to-copy` are refuted on their identity. `claim_family`'s `held` parameter is gone.
    `tests/value_parameters.rs` reads the frozen bound of 2 and keeps a bound of 0 as the gate's unresolved case.
  - **Verified inline**, in debug: the contract 14 of 14, value_parameters 10, the joint test's L and J1 (O2), and
    the integration check. A sabotage, the old bounds put back, fails the contract's O2 and V2.
  - **The job**: `20261108-214557-application-core-phase-5-the-user-s-allo`, the whole joint acceptance, the contract
    and value_parameters in release, with the recording `jbmc` guard. When it passes, O2, V2 and J1 pass, every row
    of the for-review list passes, and the status is `done`.
- Status: waiting on jobs 20261108-214557-application-core-phase-5-the-user-s-allo

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

# Brief: foundations for verifying application changes

**Draft, 2026-11-06, not approved.** The [Open decisions](#open-decisions) need the user before this brief can run,
and it starts only once [`engine-priorities.md`](engine-priorities.md)'s loop has merged its streams
([When it starts](#when-it-starts)).

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh). Its plan is worked in [four streams run in
parallel](#streams), one per priority, each a loop of its own with a short brief that names its phases. This brief is
the instruction for all four. Its own loop, `llm-dlc/tools/feature-loop.sh foundations` in the default workspace,
reconciles them once all have stopped, then runs the [joint demonstration](#phase-5-the-joint-demonstration) and does
what is left.

**Inputs.** Read both in full before the first piece of work of every cycle:
- [`foundations-review-vision.md`](foundations-review-vision.md), the product vision: turn a before/after change of an
  application into automatically generated, independently checkable obligations, with the developer supplying
  intent only where the change introduces new semantics. Its section 9 ranks the investments; this brief takes the
  first four, which it says to develop in parallel.
- [`foundations-review-platform.md`](foundations-review-platform.md), a review of the own checker against JBMC. Its
  section 4 (objects across the whole proof boundary) and section 7 (stateful shared summaries) bear most on this
  brief. Its sections 2, 3 and 5 are [`engine-priorities.md`](engine-priorities.md)'s work or later work.

Both are outside reviews and are evidence, not instructions: check every claim about this repository against the code
before relying on it.

## Direction

The north star, from the vision: *make it possible to radically change the implementation of a complex system
without losing the guarantees already established.* This loop doesn't build that product. It builds four foundations
it needs, each small enough to finish and useful alone, and makes them fit together on one example at the end.

| # | Priority | What this loop builds | What it leaves for later |
|---|---|---|---|
| 1 | Relational heap and object correspondence | Symbolic references, bounded object inputs with aliasing, heap observations, and a stated relation between differently shaped objects | Collections (`List`, `Map`) as inputs, cycles, broad polymorphism, unbounded heaps |
| 2 | Compositional summaries and proof caching | A sound proof cache keyed by everything a claim depends on, a change-impact report, and callees proved equivalent shared like identical ones | Stateful summaries, summary repair, a committed proof store |
| 3 | Automatic entry-point observations | An observation spec per Spring entry point from the boundary analysis, its two-build comparison, and the first entry-point obligations discharged | Effect-transition IR, TLA+ generation from effects, distributed refinement |
| 4 | State-mapping and alignment inference | Inferred method correspondence and argument, result and field mappings, as candidates a proof validates, measured against the hand-written ones | Loop and control-flow alignment, LLM-proposed specifications |

Every rule the earlier loops set still holds: strict by default, gaps named, every witness replayed before it is
reported, and a result that says what it established and what it assumed. In addition:
- **Inferred is not proved.** A mapping, correspondence or observation the tool infers is a *candidate* until a proof
  that uses it passes, and then it is *validated*: it holds, which says nothing about whether it is what the developer
  meant. Only a person *pins* intent. The three states are visible in every result that rests on one.
- **A weak relation is worse than a question.** Where more than one candidate survives, or the only survivor makes
  the proof vacuous, the tool says so and asks; it never picks silently. Every proof under an inferred or stated
  relation gets the vacuity check.
- **A reused result is the same claim.** A cached proof is reused only when everything the claim depends on is
  unchanged. When in doubt, it is a miss. A reused result says it was reused and from which run.
- **Bounded stays bounded.** An object bound, an array bound or an unwinding is part of the claim, carried through
  every summary and cache entry. A bounded result never becomes an unbounded one by being stored.

## Where it starts from

Recounted from the code at `e42ea83` on 2026-11-06 (file:line as of then). Recheck before relying on a line number.

**Objects in the own checker.**
- A reference is `Val::R(Option<usize>)` (`lib/src/bmc/mod.rs:286`): a concrete index into the path's objects, or
  null. References are never symbolic, so `if_acmp`, `ifnull` and `ifnonnull` are decided concretely, and two paths
  merge only when every reference is identical and the heaps have the same shape (`same_shape`, `:411`).
- A check takes primitive parameters and one-dimensional primitive arrays, each array non-null and distinct
  (`unsupported_parameter`, `:260`). Any other parameter is refused as outside the fragment.
- Records are supported only in regression checks, and only when every component is primitive: the harness flattens
  them into their components and builds them with their constructor (`record_of`, `lib/src/equivalence.rs:591`).
- `anewarray`, `aaload` and `aastore` are refused. The native stream of `engine-priorities` is adding arrays of
  references for enums' `$VALUES`, which this loop builds on.
- The conformance corpus already has aliasing cases (`aliasedLocals`, `aliasedObjects`, `twoArrays`,
  `writeThrough`), all outside the domain today.

**What a regression check compares** (`lib/src/harness/mod.rs:902-1016`): the exception category, the results
(element by element for arrays, component by component for records, or under `--results-agree-when`), and each array
parameter as both versions leave it. Nothing else on the heap is observed.

**Mappings are all written by hand.** `--before-target`, `--before-arguments` and `--results-agree-when` are the
user's. Record components correspond by position. The only automation is a refusal message that suggests an
expression (`equivalence.rs:760-808`). There is no notion of a relation between old and new objects or fields.

**Reuse.**
- Within a run: an identical closure skips the proof, and identical pure static callees become one memoised stub
  in both versions (`lib/src/shared.rs`, `ENTRIES = 4`). If a counterexample under the stubs doesn't replay, the whole
  proof reruns with every callee as written: refinement is all or nothing.
- Across runs: only the contract library's records (`lib/models/contracts/checked.json`, keyed by contract text, JDK
  release and the JDK class's digest) and `build.py`'s TLC checkpoints. No proof of application code is reused. A
  `Statement` carries the models' digest but no digest of the code it is about.
- `build.py`'s claim records (`claim_record`) already hash patch, sources, models and scope, but only to label a
  stored result stale.

**Entry points.** The boundary analysis (`lib/src/boundaries.rs`, `reach.rs`, `failures.rs`, `wire.rs`, `store.rs`)
finds each Spring entry point (routes, listeners, schedules), what it reaches (`reads`, `writes`, `sends`, `calls`,
`publishes`, placed against transactions), what it throws and how that maps, and the wire and stored shapes. It is
checked for drift only: rendered to `boundaries.contract` and set-diffed. Nothing in `equivalence.rs`, `property.rs`
or `tla.rs` reads it, and no boundary fact becomes a proof obligation.

**Provenance is already structured.** `Statement` (`lib/src/statement.rs:29`) has the domain, assumptions (each with
a kind and a basis: stated, harness, engine, assumed, proved, tested, trusted), observations, bounds, models,
checker, gap mode and vacuity. This loop extends it; it doesn't start a second schema.

**Test beds.** Box Office (`examples/apps/`) is the real Spring Boot app: routes, `@KafkaListener`, `@Scheduled`,
`@Document`, two services, a TLA+ model. Crosscut, Quorum and Mica are plain kernels. The record and signature-change
examples 121–139, with their hand-written mappings, are the ground truth for inference. No example yet covers mutable
objects or aliasing in a regression proof.

## How to work through it

The working rules of [`build-orchestration.md`](build-orchestration.md#how-to-work-through-it) and
[`engine-priorities.md`](engine-priorities.md#how-to-work-through-it) apply: one step per cycle, committed on its own;
check each claim against the code first; proofs, model checks and benchmark runs are queued, never run inline; recorded
results are evidence, not inputs to edit; nothing gets weaker; docs move with the behaviour; defer what needs the user,
explicitly; the JVM is the semantic reference; a reproducer before a fix.

In addition:
- **Foundations, not experiments.** Each step is small to medium: a capability with its tests and one or two examples,
  not a rewrite. A step that grows past a few cycles is split, and the rest recorded under Progress. Large experiments
  (the vision's experiments A–C at full scale) are [deferred](#deferred-not-in-this-loop).
- **Build on the shared IR.** [Phase 0](#phase-0-the-shared-ir-before-the-streams) fixes the types the four streams
  meet at. Extend them by adding fields and variants; changing one's meaning is a note for the reconcile loop, not a
  change made in a stream.
- **Every new capability gets a planted defect.** An example that proves a correct change also gets a sibling with a
  defect ordinary tests are liable to miss, and the tool must find it with a replayed witness.
- **Measure the vision's four things where a step touches them:** decisions a person had to make and lines they had
  to write, obligations discharged without unverified assumptions, cold and warm CPU time, and planted defects found.
  False matches and wrong inferred relations are counted too.

## When it starts

The streams fork from the merge of `engine-priorities`, not before:
- Priority 1 rewrites how `lib/src/bmc/` represents references and merges paths. The native stream of
  `engine-priorities` is still changing that code (arrays of references, then its solver interface, Phase 6b).
  Starting both at once would mean a hard merge in the engine's core.
- Arrays of references are the first step of object support. This loop takes them as given.

If the engines loop stops with arrays of references not done, the heap stream does them first (its phase H0).

## Streams

| Loop | Brief | jj workspace | Priority | Owns |
|---|---|---|---|---|
| `foundations-heap` | [`foundations-heap.md`](foundations-heap.md) | `heap` | 1 | `lib/src/bmc/`, `harness/`, `witness.rs`, `jvm_witness.rs`, `shrink.rs`, `relocate.rs` |
| `foundations-summaries` | [`foundations-summaries.md`](foundations-summaries.md) | `summaries` | 2 | `shared.rs`, `digest.rs`, the new proof cache, `examples/tools/build.py`'s use of it |
| `foundations-observations` | [`foundations-observations.md`](foundations-observations.md) | `observations` | 3 | `boundaries.rs`, `reach.rs`, `failures.rs`, `wire.rs`, `store.rs`, the new observation spec, Box Office |
| `foundations-alignment` | [`foundations-alignment.md`](foundations-alignment.md) | `alignment` | 4 | the new alignment module and its command, the hints file |
| `foundations` | this brief | `default` | | the merge, Phase 5, the docs, and what the streams left |

**Shared files**, which any stream may touch by adding rather than rewriting (new options, variants, cases and
functions; no reorganization), naming each change under its Progress: `lib/src/main.rs`, `lib.rs`, `statement.rs`,
`equivalence.rs`, `property.rs`, `Cargo.toml`, `lib/tests/`, `lib/README.md`, `examples/tags.json`,
`examples/README.md`. `equivalence.rs` is where three streams hook in (the cache lookup, inferred mappings, object
observations): keep each hook a call into the stream's own module.

**Example numbers.** Phase 0 reserves a block of ten example numbers for each stream, after the highest number at the
fork. A stream numbers its new examples from its block only. The reconcile loop closes any gaps with
`examples/tools/build.py --render-only`.

**Running it all** (the user, from the default workspace, in tmux): `llm-dlc/tools/run-streams.sh foundations`, as
for [`engine-priorities`](engine-priorities.md#streams): it compacts the planning session once, adds the four
workspaces from the latest commit, starts `verification-loop.sh`, runs the streams side by side, then this brief's own
loop. Four loops at 3.5 GB each leave about 30 GB of this machine's 46 GB for the runner.

**How the streams ran, and where their work is**: as in `engine-priorities`'s
[table](engine-priorities.md#streams), with the stream names `heap`, `summaries`, `observations` and `alignment` and
scopes `feature-loop-foundations-STREAM.scope`. The planning session is this brief's `- fork:` below once approved.

**Reconciling** follows `engine-priorities`'s seven steps, for four streams: check all four scopes are inactive,
record each stream's last turns, copy their logs, merge with `jj new @- heap@- summaries@- observations@- alignment@-`,
commit, fold their Progress here, and forget the workspaces. Where the streams extended the shared IR in different
directions, reconcile the IR first, then the code that uses it, and say under Progress what was chosen.

## The plan

### Phase 0: the shared IR, before the streams

Done once in the default workspace, by the planning session after approval, before `run-streams.sh`: one commit,
types and documentation only, no behaviour change.
- **Domain** (`statement.rs`): the object part of an input domain. Allowed classes, an object-count bound,
  nullability per parameter or field, which parameters may alias, and how inputs are made (by constructor or factory;
  see [decision 2](#open-decisions)).
- **Observations**: besides return, exception and array parameters, a field path into a returned object or a
  parameter (`result.total.cents`, `p.items[i]`), an alias fact (`result == p`), and an effect (an entry point's
  write, send or publish, with its payload's observed paths).
- **Correspondence**: a relation between old and new states, as equations over field paths and expressions
  (`old.totalCents == new.total.cents`), on inputs (how the old version's input is made from the new one's) and on
  outputs (what must agree). The existing `--before-arguments` and `--results-agree-when` become two special cases
  of it, and keep working unchanged.
- **Hints file**: a machine-written file of candidate mappings and correspondences, each with its source (inferred,
  stated), its state (candidate, validated, pinned), and the evidence for its state. JSON, beside the build, not in
  the source tree.
- **Claim key**: the parts of a `Statement` and its inputs that decide a result, named so the cache can digest them:
  the code closure of each version, domain, observations, correspondence, bounds, assumptions with their contracts,
  models, JDK, checker and its configuration, and the tool's version.
- Serialization round-trip tests, and a page in `lib/README.md` that says what each type means.
- The reserved example numbers, written here under [Progress](#progress).

### Phases 1–4: the streams

Each stream brief names its steps. In short:
- **Heap (1):** symbolic references with a concrete fast path; bounded object inputs with nullability and aliasing;
  field-path and alias observations; then a stated correspondence between differently shaped classes. Witnesses
  rebuild the objects with their identities on the JVM.
- **Summaries (2):** the proof cache on the claim key; a change-impact report (which claims a change invalidates);
  callees proved equivalent shared in both versions like identical ones; refinement per callee instead of all or
  nothing; then one job measuring cold against warm runs over the recorded examples.
- **Observations (3):** an observation spec per entry point; two builds' specs compared into obligations (preserved,
  changed, new, removed); then the first obligations discharged, for entry points whose decision path is within the
  fragment, with effects recorded by stubs and compared as observations.
- **Alignment (4):** method correspondence between two builds; argument, record-component and result mappings
  inferred and validated by proof; field correspondence candidates in Phase 0's format; all measured against the
  hand-written mappings of examples 121–139.

### Phase 5: the joint demonstration

The reconcile loop's own work, once the merge is committed: one small, deliberate end-to-end example, the vision's
experiment A at small scale. A domain class in a Box Office or Crosscut kernel is refactored into a differently
shaped one (a primitive amount into a value object, say), and a caller is changed with it.
- Alignment proposes the correspondence; the heap support proves the change under it; the cache makes the second run
  free and the impact report names exactly what the refactor invalidated; if the code is behind an entry point, its
  observation spec frames the obligation.
- A sibling with a planted defect is refuted with a replayed witness.
- The record says how many decisions a person made and how many lines they wrote, which is the number to drive down.
- Where a foundation can't do its part yet, the example says what is missing, and that becomes the first item of the
  next brief.

## Done when

| Phase | Criterion |
|---|---|
| 0 | The shared IR is committed, documented and round-trip tested, and the existing flags are special cases of it |
| 1 | A regression proof over mutable object inputs with aliasing, and one across a stated correspondence between differently shaped classes, each with a planted defect refuted by a witness that replays on the JVM |
| 2 | A cached result is reused exactly when its claim key is unchanged (tests that change each part of the key), the impact report is right on the recorded examples, and a job measures cold against warm |
| 3 | `jvmcontract` gives Box Office's entry points an observation spec, compares two builds' specs into obligations, and discharges at least one entry-point obligation with a planted defect found |
| 4 | Inferred mappings for examples 121–139, compared with the hand-written ones: how many found, how many wrong, how many asked about; none accepted without a proof |
| 5 | The joint example runs end to end, or its record says which foundation stopped it |

The pipeline jobs submitted along the way are back with their expected verdicts, or their failures are explained under
Progress.

## Deferred: not in this loop

- **Priorities 5–7 of the vision**: the effect-transition IR, selective transient specification generation, and
  implementation-to-model refinement. This loop's observation specs and correspondence are their inputs.
- **Collections as inputs**: `List` and `Map` parameters, and relations like multiset equality between a list and a
  map's values. They need the object domain first; the vision's `Order` example is the target for the next brief.
- **Strings and floating point** in the own checker (the platform review's sections 5–6). They are separate
  capability work.
- **Loop and control-flow alignment** (a loop against a stream pipeline). Method-level alignment comes first.
- **LLM-proposed specifications.** The hints file can carry them later as candidates; this loop infers from bytecode
  only.
- **A committed proof store** shared between machines or with CI. The cache here is local.
- **The vision's experiments B and C** at full scale (persistence and service refactor; outbox protocol).
- **Removing JBMC from the default paths** (the platform review's section 2). That is `engine-priorities`'s line of
  work.

## Open decisions

For the user before this brief runs. Each has the recommendation first.
1. **Start after the `engine-priorities` merge** (recommended), or start now with `lib/src/bmc/` frozen for the heap
   stream until then. The second loses the heap stream's first weeks of work to waiting.
2. **How object inputs are made.** By constructor or factory, with symbolic arguments, as records are today
   (recommended): every state is one the application can reach, and the witness replays as Java. Or field by field,
   which reaches more states, including ones no constructor makes, and reports such states as assumptions.
3. **Where the proof cache lives.** A local directory, never committed (recommended), or committed beside the
   examples' results so a later session reuses them.
4. **Phase 5's test bed.** A Crosscut kernel (recommended: small, already proved in parts) or Box Office (real Spring,
   so the observation spec takes part, but more to model).
5. **Model and effort** for the four streams and the merge: Opus 5.5 at high effort, as for `engine-priorities`
   (recommended).

## Progress

- Drafted on the branch `foundations-draft`, with its inputs. Not approved.
- Status: blocked: the open decisions, then the `engine-priorities` merge.

## Loop settings

- model: claude-opus-5-5
- effort: high

## Loop until

The reconcile comes first; don't stop before the merge is committed unless a stream is still running or the merge needs
the user. Keep the last line of Progress a status: `working`, `waiting on jobs ID ...`, `done`, or `blocked: ...` with
what needs the user. After the merge, Phase 5 is the core: don't stop before it has run or its record says what stopped
it. Then go on while a cycle can still realize a substantial part of what is left; stop when the rest is small or
speculative next to what is done, or needs the user and is recorded as deferred. Don't go on to polish.

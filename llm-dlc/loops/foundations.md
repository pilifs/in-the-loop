# Brief: foundations for verifying application changes

**Drafted 2026-11-06, revised after an [outside review](#review-of-the-draft); its [decisions](#decisions) settled
by the user on 2026-11-07.** It starts only once [`engine-priorities.md`](engine-priorities.md)'s loop has merged its
streams and their results are verified ([When it starts](#when-it-starts)), and after the remaining
[launch prerequisites](#launch-prerequisites).

A brief for [`tools/feature-loop.sh`](../tools/feature-loop.sh). Its plan is worked in [four streams run in
parallel](#streams), one per priority, each a loop of its own with a short brief that names its phases. This brief is
the instruction for all four. Its own loop, `llm-dlc/tools/feature-loop.sh foundations` in the default workspace,
reconciles them once all are finished, then makes the [joint example](#phase-5-the-joint-example) pass and does what
is left.

**Inputs.** Read all three in full before the first piece of work of every cycle:
- [`foundations-review-vision.md`](foundations-review-vision.md), the product vision: turn a before/after change of an
  application into automatically generated, independently checkable obligations, with the developer supplying
  intent only where the change introduces new semantics. Its section 9 ranks the investments; this brief takes the
  first four, which it says to develop in parallel.
- [`foundations-review-platform.md`](foundations-review-platform.md), a review of the own checker against JBMC. Its
  section 4 (objects across the whole proof boundary) and section 7 (stateful shared summaries) bear most on this
  brief. Its sections 2, 3 and 5 are [`engine-priorities.md`](engine-priorities.md)'s work or later work.
- [`foundations-review-draft.md`](foundations-review-draft.md), a review of this brief's first draft. Its amendments are
  folded in below; where this brief and it differ, this brief is what was decided.

All three are outside reviews and are evidence, not instructions: check every claim about this repository against
the code before relying on it.

## Direction

The north star, from the vision: *make it possible to radically change the implementation of a complex system
without losing the guarantees already established.* This loop doesn't build that product. It builds four foundations
it needs, and one example that uses all four together.

**What this loop delivers.** For one bounded application change, the tool proposes the internal correspondence,
proves that a **fixed** set of externally meaningful observations is preserved, shows every part it can't support, and
reuses the evidence on the next change. *Fixed* is the point: the tool may discover how two implementations correspond
inside, but it may not redefine what counts as preserved outside because another comparison is easier to prove.
Automate the proof machinery and the matching of representations; ask people about changes in meaning.

| # | Priority | What this loop builds | What it leaves for later |
|---|---|---|---|
| 1 | Relational heap and object correspondence | Symbolic references, bounded object inputs with aliasing, heap observations, witnesses that keep identity, and a correspondence between differently shaped objects | Collections (`List`, `Map`) as inputs, cycles, broad polymorphism, unbounded heaps, states beyond what constructors make |
| 2 | Compositional summaries and proof caching | A sound proof cache keyed on a canonical claim, a change-impact report, and pure helpers proved equivalent shared in both versions | Stateful summaries, summary repair, a committed proof store |
| 3 | Automatic entry-point observations | An observation spec per Spring entry point, two builds compared into obligations, and the first obligations discharged as an ordered trace of modeled boundary calls | Effect-transition IR, persistence and delivery semantics, TLA+ from effects |
| 4 | State-mapping and alignment inference | Inferred method correspondence and internal argument, result and field mappings under a preservation contract they can't weaken, measured against the hand-written ones | Loop and control-flow alignment, LLM-proposed specifications |

Every rule the earlier loops set still holds: strict by default, gaps named, every witness replayed before it is
reported, and a result that says what it established and what it assumed. In addition:
- **The preservation contract is fixed; inference works under it.** Every comparison has a preservation contract:
  the external input domain (how both versions' inputs come from the same logical request or call) and the required
  observations. Inference may relate internal representations under it. It may not change what an external input
  means, drop or weaken a required observation, or accept different behaviour, without a person's explicit
  authorization. The model case: `price(c)` returns `c`, then `c + 1`; the input mapping `before.c = after.c + 1`
  makes the results agree, is not vacuous and is even a bijection, and it hides a regression. Such a mapping must be
  impossible to infer for an anchored input.
- **Observations are accounted for.** Every observation the old version was held to is, in the result, preserved,
  changed with a person's approval, or unresolved. Nothing leaves the count silently, by mapping or by projection.
- **Intent and evidence are separate.** A mapping, correspondence or observation has an intent state (proposed, or
  approved by a person) and an evidence state (unchecked; proved for claim key K; refuted; unknown; stale). A person
  can approve before a proof, an approved relation can later be refuted, and a proof is evidence only for the exact
  claim key it was made under. "Pinned" never implies proved, and "validated" never outlives its key.
- **A standalone method has no anchor.** Where nothing external fixes what the inputs mean, the honest result is
  "this relation is proved; whether it is the intended one is unconfirmed", not an approved refactor.
- **A weak relation is worse than a question.** Where several candidates survive after collapsing the ones that are
  equivalent under the contract, or the only survivor makes the proof vacuous, the tool asks; it never picks. Every
  proof under an inferred or stated relation gets the vacuity check, which is necessary and not sufficient.
- **A reused result is the same claim.** A cached proof is reused only when the canonical claim is unchanged. When in
  doubt, it is a miss. A reused result says it was reused, how (an exact hit, or a callee's evidence), and from which
  run.
- **Bounded stays bounded, and the domain says what it is.** Object bounds, allocation bounds, array bounds and
  unwinding are part of the claim, carried through every summary and cache entry. Exhausting a bound narrows the
  stated claim or leaves it unresolved; it never truncates observations under a broader verdict. A domain of objects
  made by constructors is labelled as exactly that.
- **Successes are not independently certified.** A refutation is checked by replaying its witness; a proof is not
  checked by an independent certificate. That stays a stated limit of this loop's results.

## Where it starts from

Recounted from the code at `e42ea83` on 2026-11-06, and rechecked on 2026-11-07 against `main` at `ea315037`, after the
`engine-priorities` merge (file:line as of then). Recheck before relying on a line number.

**Objects in the own checker.**
- A reference is `Val::R(Option<usize>)` (`lib/src/bmc/mod.rs:316`): a concrete index into the path's objects, or
  null. References are never symbolic, so `if_acmp`, `ifnull` and `ifnonnull` are decided concretely, and two paths
  merge only when every reference is identical and the heaps have the same shape (`same_shape`, `:486`).
- A check takes primitive parameters and one-dimensional primitive arrays, each array non-null and distinct
  (`unsupported_parameter`, `:290`). Any other parameter is refused as outside the fragment.
- Records are supported only in regression checks, and only when every component is primitive: the harness flattens
  them into their components and builds them with their constructor (`record_of`, `lib/src/equivalence.rs:616`).
- Since the `engine-priorities` merge, `anewarray`, `aaload` and `aastore` work on arrays of references whose cells hold
  known objects or null; an index that is not a constant splits the path per cell (the module table at the top of
  `bmc/mod.rs`). Application static fields and class initialization (JVMS §5.5) are implemented too. Arrays of
  references are still refused as parameters and in a few array operations (`:617`, `:1449`, `:1483`). H0 is done.
- Aliasing among objects a method makes itself is decided already, since their references are concrete: the
  conformance cases `aliasedLocals`, `aliasedObjects` and `writeThrough` have verdicts in every mode
  (`lib/tests/conformance.rs:181-186`). What is outside the domain is aliasing and null among *inputs*: `twoArrays`
  is outside for the same array passed twice (`[0];@0`, "no two the same array"), and `length` and
  `lengthOrMinusOne` for a null array.

**What a regression check compares** (`lib/src/harness/mod.rs:902-1016`): the exception category, the results
(element by element for arrays, component by component for records, or under `--results-agree-when`), and each array
parameter as both versions leave it. Nothing else on the heap is observed.

**Mappings are all written by hand.** `--before-target`, `--before-arguments` and `--results-agree-when` are the
user's. Record components correspond by position. The only automation is a refusal message that suggests an
expression (`equivalence.rs:768-810`). There is no notion of a relation between old and new objects or fields.

**Reuse.**
- Within a run: an identical closure skips the proof, and identical pure static callees become one memoised stub
  in both versions (`lib/src/shared.rs`, `ENTRIES = 4`). If a counterexample under the stubs doesn't replay, the whole
  proof reruns with every callee as written: refinement is all or nothing.
- "Identical" is `same_method` (`shared.rs:275`): the same class name and access flags, and the same `shape`, which is
  each instruction with its constant-pool references resolved, plus the exception table with catch types resolved
  (`:282`). That is an exact fingerprint of a method's body. It says nothing about what lies outside the body: the
  class hierarchy, which targets a virtual call may dispatch to, field declarations, annotations or configuration.
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
checker, gap mode and vacuity. This loop extends it; it doesn't start a second schema. Some of its fields describe a
result rather than a claim (vacuity, confirmation): the cache key is a projection of it, not all of it.

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
  (the vision's experiments B and C) are [deferred](#deferred-not-in-this-loop).
- **The joint example comes first in each stream's core.** Each stream's core includes its narrow part of the
  [integration contract](#phase-0-the-shared-ir-and-the-integration-contract). Broad work beyond it comes after.
- **Build on the shared IR.** [Phase 0](#phase-0-the-shared-ir-and-the-integration-contract) fixes the types and
  interfaces the four streams meet at. Extend them by adding fields and variants; changing one's meaning is a note
  for the reconcile loop, not a change made in a stream.
- **Defects aimed at the abstractions.** An example that proves a correct change also gets a sibling with a planted
  defect that the tool must find with a replayed witness. Besides ordinary application bugs, plant defects that an
  automation layer could hide by redefining, narrowing or reusing the claim:
  - an offset mapping that hides a changed result (the `price` case above);
  - an alias turned into a copy with identical primitive values;
  - a dropped or duplicated effect;
  - a bug only in a state outside the constructor-made domain, which must show as outside the claim, not as proved;
  - a stale cached result after a change to metadata, configuration or a model.

  The question each answers: *can any automation layer make this bug disappear?*
- **Measure what the vision measures, honestly.** Where a step touches them: obligations discharged without
  unverified assumptions; preparation and hashing time apart from solver time; exact cache hits apart from reused
  callee evidence; planted defects found; false matches and wrong inferred relations. Human effort counts every
  decision a person made, not only mapping lines written: approved exclusions, domain restrictions, observation
  changes and environment assumptions too, so effort can't hide by moving category.
- **Results name what they checked.** Every result records the commit of the code it checked and the configuration it
  ran with, so a stream's result can be told from another's after the merge.
- **Quick jobs are awaited briefly; long jobs never.** This brief runs with verification separate
  (`- verification: separate` in its Loop settings): `run-streams.sh` starts no verification loop, a person may run
  one apart, and no loop stops to wait for a job. Heavy work (proofs over examples, benchmarks, `build.py` on
  B9/B11/D1 examples, anything over a minute or 1 GB) is still never run inline: submit it with
  `verification/pipeline.py submit`, stating in its description the verdict or figure it should give, commit it with
  the change (`(verification pending)` on the summary line, the job id in a paragraph), and list it under Progress
  with its id.
  - **A quick job**, one estimated at a few minutes or less, is submitted with `--priority 10`, so a runner takes it
    before the long ones. The session may await it within its cycle: go on with other work, then poll
    `python3 "$(jj workspace root --name default)/verification/pipeline.py" status` about once a minute, for at most
    15 minutes after submitting. If its result is back by then (`report`), use it like an inline result and record it
    under Progress. If not, treat the job as a long one from then on.
  - **A long job** is submitted at the default priority and never awaited, polled or read in this run: it is listed
    under Progress as *for review*, and a person reviews its result after the run.

  A step is done when its code, its inline tests (compiling, unit tests, the integration contract's tests,
  conformance cases on a real `java`) and its jobs are committed, with the results of any quick job that came back. A
  criterion only an unreturned job can show is met *pending review*, and the Progress line says which job shows it.
  Nothing is decided from a long job's result: where a choice would depend on one, take the conservative option and
  record the job that would confirm it. Waiting never ends a cycle or sets a status: no loop of this brief says
  `waiting on jobs`.
- **The timebox** ([template](brief-template.md#the-timebox)): an item that fails its verification twice in a row (two
  quick jobs that came back, or two attempts at its inline check, failing, timing out or running out of memory) is
  logged under Progress as *deferred by the timebox*, with both jobs or attempts, the finding, and what a further
  attempt would try and cost, and the loop moves on to work that doesn't depend on it. There is no third attempt in
  this run: an item that fails twice has very likely been underestimated (its proof may need far more depth than the
  plan allowed), and it is handled separately, in another session, after careful consideration by a person. In the
  joint example, a row whose item the timebox deferred makes Phase 5 partial.

## When it starts

The streams fork from the merge of `engine-priorities`, not before:
- Priority 1 rewrites how `lib/src/bmc/` represents references and merges paths. The native stream of
  `engine-priorities` is still changing that code (arrays of references, then its solver interface, Phase 6b).
  Starting both at once would mean a hard merge in the engine's core.
- Arrays of references are the first step of object support. This loop takes them as given.

Arrays of references were done by that loop (rechecked on 2026-11-07), so the heap stream's H0 is skipped.

## Launch prerequisites

The planning session is `ae994066-d1ea-4620-b03e-176a07061175`, the conversation that drafted this brief, in the
default workspace. The streams fork from it (`- fork:`), so it does the last steps before launch itself, and nothing
else is done in it afterwards.

Done on the branch `foundations-draft` (2026-11-06):
1. **The names.** `foundations` and `foundations-STREAM` in `feature-loop.sh`, and `foundations` with its four streams
   in `run-streams.sh`.
2. **The integration check** in `run-streams.sh` ([below](#the-integration-check)), run for a brief whose Loop settings
   name `- integration: SCRIPT`; this brief's is `llm-dlc/tools/foundations-integration.sh`. Tested on a throwaway jj
   repository: a clean merge runs the script and reports, a new commit in one stream triggers the next check and
   abandons the previous merge, and conflicting streams are reported with the files in conflict, the script not run.
   The engines brief names no script, so its run is unchanged.
3. **Session ids** in the five briefs' Loop settings, and `- fork:` naming the planning session in the four streams'.

Still to do, in this order, once `engine-priorities` is merged into `main` and its jobs are back and verified:
4. **Bring the branch up to date.** Rebase `foundations-draft` onto the merged `main`, and recheck
   [Where it starts from](#where-it-starts-from) against the merged code: the engines streams changed `statement.rs`,
   `equivalence.rs` and `main.rs`, and may have finished arrays of references (H0).
5. **Phase 0** on top of it, by the planning session: the types, interfaces, fixture and `lib/tests/foundations.rs`,
   whose tests `foundations-integration.sh` runs. It wasn't done on the draft branch because it rewrites
   `statement.rs`, which the jbmc stream is changing.
6. **Merge the branch into the default workspace's line**, so that `run-streams.sh foundations` runs from the default
   workspace with the new scripts, and forget the `foundations` workspace.
7. **Close the planning session**, then the user runs `llm-dlc/tools/run-streams.sh foundations` from the default
   workspace in tmux. It compacts the planning session once, before the forks.

## Streams

| Loop | Brief | jj workspace | Priority | Owns |
|---|---|---|---|---|
| `foundations-heap` | [`foundations-heap.md`](foundations-heap.md) | `heap` | 1 | `lib/src/bmc/`, `harness/` (apart from Phase 0's effect-log hook), `witness.rs`, `jvm_witness.rs`, `shrink.rs`, `relocate.rs` |
| `foundations-summaries` | [`foundations-summaries.md`](foundations-summaries.md) | `summaries` | 2 | `shared.rs`, `digest.rs`, the new proof cache, the `impact` command, `examples/tools/build.py`'s use of the cache |
| `foundations-observations` | [`foundations-observations.md`](foundations-observations.md) | `observations` | 3 | `boundaries.rs`, `reach.rs`, `failures.rs`, `wire.rs`, `store.rs`, the new observation spec, the recording stubs, Box Office |
| `foundations-alignment` | [`foundations-alignment.md`](foundations-alignment.md) | `alignment` | 4 | the new alignment module and its command, the hints file |
| `foundations` | this brief | `default` | | the merge, Phase 5, the docs, and what the streams left |

**Shared files**, which any stream may touch by adding rather than rewriting (new options, variants, cases and
functions; no reorganization), naming each change under its Progress: `lib/src/main.rs`, `lib.rs`, `statement.rs`,
`equivalence.rs`, `property.rs`, `Cargo.toml`, `lib/tests/`, `lib/README.md`, `examples/tags.json`,
`examples/README.md`. `equivalence.rs` is where three streams hook in (the cache lookup, inferred mappings, object
and effect observations): keep each hook a call into the stream's own module.

**Example numbers.** Phase 0 reserves a block of ten example numbers for each stream, after the highest number at the
fork, and the joint example's numbers. A stream numbers its new examples from its block only. The reconcile loop
closes any gaps with `examples/tools/build.py --render-only`.

**Running it all** (the user, from the default workspace, in tmux): `llm-dlc/tools/run-streams.sh foundations`, as
for [`engine-priorities`](engine-priorities.md#streams): it compacts the planning session once, adds the four
workspaces from the latest commit, runs the streams side by side with the integration check, then this brief's own
loop. It starts no verification loop (`- verification: separate`). Four loops at 3.5 GB each, and the integration
check's 3.5 GB, leave about 25 GB of this machine's 46 GB for a verification loop the user may run apart. It stays in the pane it was started in
(`- new-window: no`), with the status bar at the bottom of that pane and the mouse turned on for scrolling. A pane
keeps the history limit it was made with, so start it in a pane made after `tmux set -g history-limit 200000` (or
with that line in `~/.tmux.conf`), or the pane scrolls back only tmux's default 2000 lines.

**Stopped and finished are different.** A stream's scope going inactive means only that its process stopped. It is
finished only when its status says `done` or `blocked`. No status here says `waiting on jobs`: no loop stops to wait
for a job (a quick one is awaited only inside a cycle), and `run-streams.sh` counts such a status as finished, with
its jobs left for review. `done` requires that its
part of the integration contract passes on its branch and that every job it submitted is listed under its Progress
for review; it doesn't require any long job's result. The reconcile loop starts on finished streams, never on inactive ones
alone.

### The integration check

So that a disagreement between streams (alignment emits a relation the heap engine reads differently; observations
produces an effect kind the harness can't record) shows up while they run, not after:
- `run-streams.sh` keeps a disposable workspace of its own, `integration` (`../in-the-loop-integration`). Whenever a
  stream's `@-` has moved since the last check, at most once an hour (`RUN_STREAMS_INTEGRATION_EVERY`), it makes
  there a merge of the four streams' current `@-` commits, `jj new heap@- summaries@- observations@- alignment@-`, and
  runs `llm-dlc/tools/foundations-integration.sh` on it: the integration contract's tests, compiling and unit-level
  only (proofs stay queued). The script runs in the scope `feature-loop-foundations-integration.scope` with the loops'
  3.5 GB cap, so a verification runner, if one is run apart, leaves it room as it does a loop's.
- It writes what it found, with the four commit ids, to `llm-dlc/loop-summaries/foundations-integration.md` in the
  default workspace. Each stream reads that file at the start of every cycle (by its absolute path) and treats a
  failure in its own part as the next piece of work. A merge conflict is reported with the files in conflict, and the
  tests aren't run on it.
- The workspace is never committed from, pushed, or used for anything else; each check abandons the previous one's
  merge. The streams' rule against merging or rebasing their own branches is unchanged. It needs its own build, about
  3 GB on disk, like each stream's workspace.

**How the streams ran, and where their work is**: as in `engine-priorities`'s
[table](engine-priorities.md#streams), with the stream names `heap`, `summaries`, `observations` and `alignment`,
scopes `feature-loop-foundations-STREAM.scope`, and the integration file above. The planning session is this brief's
`- fork:` once approved.

**Reconciling** follows `engine-priorities`'s seven steps, for four streams: check all four are finished (status,
not only inactive scope) and that `feature-loop-foundations-integration.scope` is inactive too, record each stream's
last turns, copy their logs, merge with
`jj new @- heap@- summaries@- observations@- alignment@-`, commit, fold their Progress here, and forget the
workspaces (and `integration`). Where the streams extended the shared IR in different directions, reconcile the IR
first, then the code that uses it, and say under Progress what was chosen. Nothing waits for the streams' jobs: fold
them, with their ids and expected results, into one *for review* list in this brief's Progress, and put above it
every item a stream deferred by the timebox, with its finding, so the person reviewing the run sees those first. If a verification
loop the user runs apart has left uncommitted files in this working copy, wait for it to commit them before merging,
rather than moving or committing them (as `engine-priorities`'s step 4 says); results it collected are evidence for
the review, not inputs to this loop.

## The plan

### Phase 0: the shared IR and the integration contract

Done once in the default workspace, by the planning session after approval, before `run-streams.sh`. Types,
interfaces, fixtures and tests; no behaviour change to any existing command.

**The types** (in `statement.rs` and beside it):
- **Preservation contract.** The external input domain and the required observations of a comparison: how both
  versions' inputs are derived from one logical request or call (identity for an unchanged signature; a stated
  derivation otherwise), and the observations the old version is held to. Inference may not change it; only a person
  may, and the change is recorded as an approved observation change.
- **Domain.** The object part of an input domain: allowed classes; an input-object bound, apart from an allocation
  bound for what the code makes, each settable per version where representations differ (a value object wrapping a
  primitive adds an object without changing behaviour); nullability per parameter or field; which parameters may
  alias; and how inputs are made, labelled in every result: "objects made by these constructors or factories, under
  these argument constraints" (see [decision 2](#decisions)). A field-by-field or invariant-constrained domain is
  a later variant, named now so the label has somewhere to go.
- **Observations.** Besides return, exception and array parameters: a field path into a returned object or a
  parameter (`result.total.cents`); an identity relation *within* a version (`result.left == result.right`,
  `result == p`), compared across versions as "holds in old iff it holds in new", never by comparing object ids
  across versions; and an effect (see below). Which identity relations count is the observation spec's choice per
  boundary: they matter for a Java API that returns mutable objects, not for a wire response observed as serialized
  values.
- **Effects.** An effect is a *modeled boundary-call attempt*: the call's kind and target, and a snapshot of its
  observed payload values taken at the call (never a reference read later). The first contract is an ordered trace of
  such attempts with the response and the supported failure outcome, compared in exact order, under an explicit
  environment model: corresponding calls in the two versions receive the same modeled outcome (return value or
  failure), and the model says which outcomes it allows. A trace bound that is reached makes the result unresolved,
  never a shorter trace. A recorded `save` means the application attempted it, not that anything was committed or
  delivered.
- **Correspondence.** A relation between old and new internal states, as equations over field paths and
  expressions (`old.totalCents == new.total.cents`), on inputs (how the old version's internal input is made from the
  new one's, below the preservation contract) and on outputs. The existing `--before-arguments` and
  `--results-agree-when` become special cases of it and keep working unchanged; a hand-written one is a stated
  derivation with a person's authority.
- **Hints file.** A machine-written JSON file beside the build, not in the source tree: candidate mappings,
  correspondences and observation changes, each with its source (inferred or stated), its intent state (proposed or
  approved), and its evidence state (unchecked, proved for claim key K, refuted, unknown, stale).
- **Canonical claim.** A projection of the prepared claim, after flags, hints, inferred mappings, models and
  generated observations are resolved: the preservation contract, each version's code closure, domain,
  observations, correspondence, bounds, assumptions with their contracts and stubs, environment model, models, JDK,
  checker and its configuration, and the tool's identity (the binary's digest, not only its version). Excluded:
  anything that depends on the result or the run (verdict, vacuity, confirmation, timings, run ids, reuse
  provenance). A result record is the claim key plus verdict, evidence and run provenance.

**The interfaces**, each with a stub implementation that returns a named unsupported result:
- the harness's effect-log hook: where recording stubs append, and how the harness compares two logs;
- alignment's output consumed by the check (hints file in, prepared claim out);
- the cache's lookup on a prepared claim and its store of a result record;
- the observation spec's output consumed by the comparison of two builds.

**The integration contract**, executable:
- the joint example's fixture ([Phase 5](#phase-5-the-joint-example)): the before and after builds and each defective
  sibling, committed under the joint example's reserved numbers;
- golden files of its preservation contract, domain, observations, correspondence and canonical claim;
- `lib/tests/foundations.rs`, a test per stream's part and per case, with the final verdict each must reach. A test
  passes when its part reaches that verdict or still stops with its named unsupported result, and fails on anything
  else (a different error, a wrong verdict, two parts disagreeing about a type). It prints which parts are still
  unsupported, so the integration report shows progress as well as breakage. `foundations-integration.sh` runs it;
  the joint example is done when nothing is unsupported;
- the parts each stream owns, listed in its brief.

Also: serialization round-trip tests, a page in `lib/README.md` on what each type means, and the reserved example
numbers written here under [Progress](#progress).

### Phases 1–4: the streams

Each stream brief names its steps. In short:
- **Heap (1):** symbolic references with a concrete fast path; bounded object inputs with nullability and aliasing;
  field-path and identity observations; witnesses that rebuild objects with their identities on the JVM, required
  with object inputs; then correspondence between differently shaped classes, narrowly, for the joint example.
- **Summaries (2):** closure digests that cover dispatch, hierarchy, annotations and configuration; the proof cache
  on the canonical claim, with adversarial invalidation tests; a change-impact report; pure helpers proved
  equivalent, shared in both versions under a call-site applicability check; refinement per callee; one job measuring
  categorized changes.
- **Observations (3):** an observation spec per entry point; two builds compared into obligations, accounted for;
  then the first obligations discharged as ordered traces of modeled calls under an explicit environment model.
- **Alignment (4):** the ground truth from examples 121–139; method correspondence; internal argument, record and
  result mappings inferred under the preservation contract, collapsed and validated by proof; field correspondence
  candidates for the joint example.

### Phase 5: the joint example

The acceptance gate of this loop, the vision's experiment A at small scale: a small Crosscut-style kernel behind one
thin, real annotated entry point (a Spring route or listener), so that every stream takes part. Its fixture is fixed in
Phase 0. The change combines a primitive amount becoming a value object, an internal method or field mapping, one
changed pure helper, and one recorded outgoing effect. The external request's meaning and the required observations
stay fixed.

The reconcile loop makes it pass once the merge is committed. Its checks are small, so they run inline, as the
integration contract's tests and conformance cases; anything heavier (a rerun of the recorded examples with the cache,
say) is a job submitted for review, not a condition of passing. It passes when:

| Requirement | Evidence |
|---|---|
| Automatic mapping | Alignment proposes the internal relation, with no hand-written mapping for this fixture |
| Object correspondence | The relation is checked over the declared bounded domain |
| Boundary preservation | The required response and effect observations are proved preserved, and the accounting shows none dropped |
| Exact reuse | An unchanged rerun is an exact cache hit |
| Compositional reuse | The changed helper's proved equivalence is used in the caller's proof |
| Defect detection | Each defective sibling (the abstraction-aimed defects above included) gives a replayed counterexample, or is outside the stated claim and says so |
| Honest incompleteness | One unsupported case stays visibly unresolved |
| Effort | The number of decisions a person made, by category |

**Partial is not done.** If a foundation can't do its part, the loop may stop there, but its status records a
*partial* Phase 5: which rows pass, which don't, and what each missing one needs. That becomes the first item of the
next brief. Only a passing example counts as this loop's milestone.

## Done when

| Phase | Criterion |
|---|---|
| 0 | The shared IR, interfaces and integration contract are committed, documented and tested, and the existing flags are special cases of the IR |
| 1 | Regression proofs over mutable object inputs with aliasing, with witnesses that replay on the JVM with their identities, each with planted defects refuted (the alias-to-copy one included); the joint example's correspondence part passes |
| 2 | A cached result is reused exactly when its canonical claim is unchanged (the invalidation tests pass), the impact report is right on the recorded examples, a changed helper's proof is reused in a caller, and a job to measure categorized changes is submitted |
| 3 | Box Office's entry points have observation specs, two builds' specs compare into accounted obligations, and the joint example's effect obligation is discharged with a dropped effect and a duplicated one refuted |
| 4 | Inferred mappings for examples 121–139 scored against the hand-written ones (found, asked, wrong, missed), none accepted without a proof, the offset-mapping defect never accepted, and the joint example's mapping proposed |
| 5 | The joint example passes every row above |

Criteria that only a long or unreturned job can show are met pending review; a quick job's result that came back counts
like an inline one. Every job submitted along the way is listed under Progress,
with its id, what it checks and the result it is expected to give, so that the person who reviews the results after
the run can tell a pass from a failure without the session.

## Deferred: not in this loop

- **Priorities 5–7 of the vision**: the effect-transition IR, selective transient specification generation, and
  implementation-to-model refinement. This loop's observation specs, effect traces and correspondence are their
  inputs.
- **Persistence and delivery semantics**: committed state, transactions' atomicity, delivery guarantees. The effect
  trace here is of attempted calls under a stated environment model.
- **Collections as inputs**: `List` and `Map` parameters, and relations like multiset equality between a list and a
  map's values. The vision's `Order` example is the target for the next brief.
- **Object states beyond construction**: bounded sequences of method calls after construction, and states
  constrained by inferred invariants. The domain label leaves room for them; general invariant inference is not
  started.
- **Stateful summaries** and proofs that depend on each other recursively.
- **Strings and floating point** in the own checker (the platform review's sections 5–6).
- **Loop and control-flow alignment** (a loop against a stream pipeline). Method-level alignment comes first.
- **LLM-proposed specifications.** The hints file can carry them later as proposed; this loop infers from bytecode
  only.
- **A committed proof store** shared between machines or with CI. The cache here is local; its claim keys and result
  records are portable, so a shared store can come later.
- **Independent certificates for successful proofs.** Refutations are checked by replay; proofs are not
  independently checked. A stated limit, not a workstream for now.
- **The vision's experiments B and C** at full scale (persistence and service refactor; outbox protocol).
- **Removing JBMC from the default paths** (the platform review's section 2). That is `engine-priorities`'s line of
  work.

## Decisions

Settled by the user on 2026-11-07, each as recommended (the outside review agreed with each):
1. **Start after the `engine-priorities` merge**, and after its jobs are back and verified. Not now with
   `lib/src/bmc/` frozen.
2. **Object inputs are made by constructor or factory**, with symbolic arguments, as records are today, labelled as
   that domain in every result and never claimed to cover every valid state. Field-by-field inputs are a later variant.
3. **The proof cache is a local directory**, never committed, with portable claim keys and result records.
4. **The joint example is a small Crosscut-style kernel behind one thin, real annotated entry point**: not a kernel
   alone, and not Box Office itself.
5. **Opus 5.5 at high effort** for the four streams and the merge, as for `engine-priorities`, so that this run changes
   the acceptance controls and not the agents as well.

## Review of the draft

The first draft was reviewed on 2026-11-06 ([`foundations-review-draft.md`](foundations-review-draft.md)). It kept
the scope, the split and the deferrals, and changed the acceptance contract. Taken in:
- the preservation contract that inference can't weaken, observation accounting, and intent apart from evidence;
- one working four-stream example as the gate, its fixture and interfaces fixed in Phase 0, each stream's part in
  its core, a partial result recorded as partial;
- the integration check while the streams run, and finished told apart from stopped;
- the domain labelled as constructor-made, identity relations within a version, input-object and allocation bounds
  apart, and replay required with object inputs;
- a canonical claim projection for the cache key, adversarial invalidation tests, a call-site applicability check
  and acyclic dependencies for shared helpers, and a mandatory narrow S4;
- effects as an ordered trace of modeled call attempts with payload snapshots, a coupled environment model and
  visible bounds;
- defects aimed at the abstractions, and effort measured across every category of human decision;
- the wording of the stream briefs' editing rule.

Checked against the code rather than taken from it: whether `shared.rs`'s `shape` is an exact fingerprint. It is, for
a method's body (constant-pool references and catch types resolved); it doesn't cover dispatch, hierarchy,
annotations or configuration, which S1 adds.

## Progress

- Drafted on the branch `foundations-draft`, with its inputs, and revised after the review of the draft.
- Launch prerequisites 1–3 done on that branch: the names, the integration check, the session ids.
- Decisions settled by the user on 2026-11-07 ([Decisions](#decisions)).
- Status: blocked: the `engine-priorities` merge and its verified results, then launch prerequisites 4–7.

## Loop settings

- session: 2df7775c-45a1-40a7-924b-75602d8ad256
- model: claude-opus-5-5
- effort: high
- integration: llm-dlc/tools/foundations-integration.sh
- verification: separate
- new-window: no

## Loop until

The reconcile comes first; don't stop before the merge is committed unless a stream is unfinished or the merge needs
the user. Keep the last line of Progress a status: `working`, `done`, or `blocked: ...` with what needs the user;
never `waiting on jobs`: a quick job is awaited only within a cycle, and a long one not at all. After the merge, Phase 5 is the core: `done` only when the joint example passes every row; if a
row can't pass without the user or a later brief, stop with `blocked: Phase 5 partial: ...` naming the rows. Then go
on while a cycle can still realize a substantial part of what is left; stop when the rest is small or speculative
next to what is done, or needs the user and is recorded as deferred. Items deferred by the timebox count as recorded deferrals, never as a reason to keep going. Don't go on to polish.

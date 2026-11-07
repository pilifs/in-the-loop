# Stream brief: foundations, the relational heap

One of four streams of [`foundations.md`](foundations.md) that run in parallel, each in its own jj workspace on its
own branch. The others are [`foundations-summaries.md`](foundations-summaries.md),
[`foundations-observations.md`](foundations-observations.md) and [`foundations-alignment.md`](foundations-alignment.md).
Once all are finished, a reconcile loop merges them; [Streams](foundations.md#streams) in the main brief says how.

Started with the others by `llm-dlc/tools/run-streams.sh foundations` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh foundations-heap` from this stream's workspace (`jj workspace root --name heap`): the
loop refuses any other.

**The main brief is the instruction.** Read [`foundations.md`](foundations.md) in full every cycle, and its three
inputs too. Its direction, starting point, working rules, deferrals and decisions all apply here. This file says which
part of its plan is yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section;
edit implementation files according to the ownership rules below.

**Every cycle, read the integration check** first: `$(jj workspace root --name default)/llm-dlc/loop-summaries/foundations-integration.md`,
if it exists. A failure in your part of the [integration contract](foundations.md#phase-0-the-shared-ir-and-the-integration-contract)
on the latest combined commits is your next piece of work.

## Your phases

Priority 1: proofs over objects, and between objects of different shapes. In order:

- **H0. Arrays of references**: done by the `engine-priorities` loop (rechecked 2026-11-07): `anewarray`, `aaload`
  and `aastore` over known objects or null. Arrays of references as *parameters* are H2's.
- **H1. Symbolic references.** A reference that may denote one of a finite set of objects, or null, guarded by path
  conditions. `if_acmp`, `ifnull` and `ifnonnull` over such references become formulas; `getfield` and `putfield`
  through one read and write each candidate under its guard. Paths that differ only in a reference merge into one.
  Keep `Val::R` as the fast path: a reference whose target is known stays concrete, and every existing test and verdict
  must hold inline; the benchmark's formula sizes are a job, submitted for review. The aliasing cases among objects a method makes (`aliasedLocals`,
  `aliasedObjects`, `writeThrough`) keep their verdicts; they need no symbolic reference.
- **H2. Object inputs.** A parameter of an application class, within Phase 0's domain: classes allowed, an
  input-object bound, nullability, and which parameters may alias. Made as the main brief's
  [decision 2](foundations.md#decisions) settled: by constructor or factory with symbolic arguments. Every result over such inputs carries the domain's label, "objects made by these constructors or
  factories, under these argument constraints"; it never claims states a constructor doesn't make (an `Account` made
  with `balance = 0` says nothing about one after deposits). Fields of reference type point into the same bounded set.
  The conformance corpus's input cases outside the domain today become its first targets: `twoArrays` with the same
  array twice, and `length` and `lengthOrMinusOne` with a null array, each as the JVM decides it once the domain allows
  aliasing or null. Start with classes whose fields are primitives, primitive arrays, or references to such classes; refuse the rest as
  named gaps. Both versions get corresponding inputs from the same construction, the old version's objects made under
  `before/` as records are today.
- **H3. Heap observations.** At the end of a regression check, compare Phase 0's observations: field paths into the
  result and into each mutable parameter, and identity relations within each version, compared as "holds in old iff
  in new" (`result.left == result.right`; `result == p`). Physical object ids are never compared across versions,
  and internal allocations are not compared at all. Defaults, where no observation spec chooses: the result's reachable
  primitive fields and its identity relations within the bound, and each parameter's fields and identity relations as
  both versions leave them, as array parameters are compared today. An observation spec may choose fewer (a wire
  response observes values only), and the result says which were compared.
- **H4. Witnesses with identity**, required with H2: a witness over objects is a construction recipe that keeps
  aliasing, replayed in the interpreter, run as Java on the JVM (`jvm_witness.rs`), and shrunk (`shrink.rs`) without
  merging or splitting objects. A witness that needs two parameters to be the same object replays with one object.
  H2 and H3 aren't done until their witnesses replay.
- **H5. Correspondence between different shapes.** A regression check where the old and new versions take or return
  different classes, under a Phase 0 correspondence below the preservation contract: the old internal input is made
  from the new one's values through the input equations, the outputs must satisfy the output equations, and the
  preservation contract's external inputs and observations stay as they are. Bounds are per version: input-object
  and allocation bounds can differ where one representation needs more objects (a value object wrapping a primitive).
  A bound that is reached narrows the stated claim or leaves the result unresolved; it never drops an observation.
  Vacuity is checked as for `--before-arguments`. Do first the narrow case the joint example needs, then widen.

**Your core:** H1–H4, and H5's narrow case for the joint example (its correspondence row of the integration contract).
The rest of H5 comes after.

Each phase gets examples from your reserved block: a correct change proved, and siblings with planted defects. The
alias-to-copy defect (an alias turned into a copy with the same primitive values, which a caller sees by mutating
one) is required, and so is a bug only in a state outside the constructor-made domain, which must show as outside the
claim. Tag them from `examples/tags.json`; an `aliasing` or `object-inputs` tag may be needed, added with a
description.

Not yours: the cache key (summaries; it digests the canonical claim, which includes your new domain fields), inferring
correspondences (alignment), entry-point effects and the effect-log hook (observations, through Phase 0's interface).

## Boundaries

You own `lib/src/spec/heap.rs`, your interface in the shared IR, which returns a named `Unsupported` until your
part is done; your checks in `lib/tests/foundations.rs` turn from unsupported to passed as you do it. You also own `lib/src/bmc/`, `lib/src/harness/` apart from Phase 0's effect-log hook, `witness.rs`, `jvm_witness.rs`,
`shrink.rs`, `relocate.rs` and their tests. `lib/models/` is shared with no other stream this time, but a model change
still says under Progress which JBMC results it may change. JBMC need not follow every new capability: where it can't
take an object input, the own checker decides alone and the result says so; `--confirm` refuses rather than
confirming a different claim.

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

- **H1 done (2026-11-07), pending review of job `20261107-041414`.** The own checker has symbolic references:
  `Val::C`, a [`Choice`](../../lib/src/bmc/mod.rs) of the path's objects or null under exclusive guards, made where
  paths that differ only in a reference merge (`Engine::absorb`, through `choose`), and by a read through one.
  `if_acmp`, `ifnull`, `ifnonnull` and `instanceof` on one are formulas; `getfield` chooses among the candidates'
  fields and `putfield` writes each under its guard, with `NullPointerException` where it is null; every other use
  that needs the object (a call's receiver, a JDK call's or intrinsic's argument, array instructions, `checkcast`,
  `athrow`, monitors) splits the path per candidate (`Engine::concrete_ref`), substituting the known reference for
  every copy of the choice. `Val::R` stays the fast path: a known reference is never a formula. Arrays of references
  still hold known cells (an `aastore` of a choice splits first), and paths whose objects differ in number or class
  still don't merge.
  - Evidence inline: `lib/tests/heap.rs` (new), three claims each checked merged from the start and never merged,
    same verdicts, every violation's witness failing the claim on the JVM: ten independent choices then a write
    through the chosen one, 22 paths merged against 1024; with null among the options, 30 against 1024; across two
    classes with `instanceof`, a cast and a virtual call, 22 against 1024. Conformance cases `swaps`, `swapsOrNull`
    and `swapsThenNull` (past the 512-path merge threshold) agree with the JVM. Unit tests (183), `integration.rs`
    (64), `conformance.rs` and `foundations.rs` pass; the aliasing cases keep their verdicts.
  - *For review*: job `20261107-041414`, the benchmark on the own checker against `lib/benchmark/results.json`:
    expected no verdict changed, no formula grown past 10%, and paths or merges changed only in the three new cases.
  - Shared files changed: `lib/README.md` (the merging paragraph), `lib/tests/conformance.rs` and
    `lib/tests/conformance/conformance/Conformance.java` (three cases), `lib/tests/heap.rs` (new), and the generated
    `lib/benchmark/conformance.json`.
- **H2, first step (2026-11-07): null and one-array parameters in property checks.** `jvmcontract prove` takes
  `--nullable a` and `--may-alias a,b` (closed under chains) for array parameters; the domain line says so
  (`a: int[] of length ≤ 8, or null`; `a and b may be the same array`), and so does the statement (`null`,
  `shared_arrays`, the new `may_alias` groups). The own checker alone takes such a domain
  ([`bmc::Parameters`](../../lib/src/bmc/mod.rs)): each such parameter is an H1 choice among null, its own array
  and the own arrays of the parameters before it in its group, and a witness reads back which it holds
  (`raw_same`, `Argument::Same`). `--engine jbmc` and `--confirm` refuse it (JBMC would prove a narrower claim), and
  `auto` doesn't fall back to JBMC. Properties say which it is with `a == null` and `a == b` (new in the
  expression language). Witnesses keep identity: `twoArrays(a=[0], b=the same array as a)` passes one array twice in
  the interpreter, the shrinker (which never splits or joins arrays) and the JVM run (`jvm_witness.rs` now passes
  null and shared arrays). The harness's `\old` copy of a null array is null.
  - Evidence inline: the conformance corpus's outside-the-domain calls became claims: `twoArrays` under
    `--may-alias a,b` (`result == (a == b ? 2 : 1)` V; `result == 1` X, witness `[0]` twice, refuted on the JVM),
    `length` and `lengthOrMinusOne` under `--nullable a` (two V, two X with a null witness); the default-domain
    claims keep their verdicts and their domain words. Unit tests for the engine's choices (merged and unmerged)
    and a JVM run with one array twice and with null (`lib/tests/heap.rs`). Unit tests (185), `integration.rs`,
    `conformance.rs`, `foundations.rs` and `heap.rs` pass. One run of `integration.rs` under the other streams'
    load (617 s) failed `the_tools_own_checker_agrees_with_jbmc_on_integer_proofs` at a native regression check
    (no output kept); alone it passed in 17 s. A stream that sees it again should suspect a budget under load first.
  - *For review*: job `20261107-043420`, the corpus's ignored tests (JBMC, `auto`, `auto --confirm`): expected to
    pass, the six widened claims refused (unverifiable) under JBMC and `--confirm`, and as the own checker says
    under `auto`.
  - Shared files changed: `lib/src/main.rs` (two flags), `property.rs` (the options), `equivalence.rs` (its
    `locals_of` now the witness module's, and the vacuity probe takes the parameters), `statement.rs` (`may_alias`
    on `Domain`, skipped when empty), `lib/README.md` (a paragraph), `lib/tests/conformance.rs` (claims with a
    domain, six of them; left out of the benchmark's group 1, whose runner passes no domain flags), and
    `lib/tests/heap.rs`. `jbmc.rs` gained `raw_same` and `Argument::Same` (owned by no stream; a witness type).
- `sync.py check` on this branch reports errors that aren't this stream's and that it may not fix (they are under
  `llm-dlc/traces/`): the other streams' sessions (`be22079e`, `e65240e3`, `11f93b59`, `3ef2aade`) have no manifest
  here, and five planning-era commits (`olwyzkwouyln`, `xrkxxnnuwwuq`, `nnqrnknuvslx`, `xpsxzuolnwop`,
  `kxnqrntnkztt`) point at session `c2bd9df4`'s log `1f2230c9f137`, which that session's manifest lists in the
  default workspace but not in this branch's copy from the fork. Both should clear at the reconcile merge.
- **H2, second step (2026-11-07): objects made by their constructor as regression inputs.** Done in regression
  checks first rather than property checks as the last Next said, since the integration contract's heap part is
  regression checks and the record machinery (`Layout`, `Slot::Record`) was there to generalize. A parameter of an
  application class is made in the harness by its one usable constructor, whose arguments are primitives or objects
  made the same way ([`RecordType::made`](../../lib/src/harness/mod.rs): `params`, `inner`, and `components` the
  primitive leaves by path, `l.price.cents`); both versions get their own objects from the same leaves, the old
  one's under `before/`, and their fields after the calls are compared ([`Fields`](../../lib/src/harness/mod.rs):
  primitives, primitive arrays, objects of application classes followed, nulls agreeing). The domain says
  `l: a Line made by its constructor, Line(price: Money(cents: long), quantity: int), from any arguments it accepts`;
  `stated.observations.objects` lists the compared paths; the witness is a recipe, `bump(l=new Line(new Money(0),
  1))`, and the replay says what each version left in the object. Refused as named gaps, by field or argument: a
  superclass other than `Object`, several constructors, a constructor argument or field of another type (`String`),
  a class reaching itself, and an object made differently in the two versions (H5's).
  - Evidence inline: `lib/tests/heap.rs`, five regression checks on the own checker over `Line(Money, int)`: a
    rewrite verified with the domain words and the observed paths; a changed result refuted with a recipe witness;
    a change seen only in the object as left (`l.quantity += 2` in a void method) refuted, its rewrite verified; a
    difference only where the constructor rejects verified, the domain and the constructible assumption saying so;
    a `String` field refused naming it. Unit tests (185), `heap.rs` (9), `integration.rs` (64), `conformance.rs` and
    `foundations.rs` pass. A first run of `integration.rs` under the other streams' load (611 s) failed one test,
    whose name its cut output didn't keep; the full rerun passed all 64 in 23 s, as last step's did.
  - Not yet: identity is not observed (an alias-to-copy passes; H3), nullability and aliasing among object
    parameters, receivers and results of such classes (a result of one is still compared with `Objects.equals`), and
    property checks over objects. The JVM run of a regression witness (`jvm_witness.rs`, reached only for a witness
    through a contract) runs the harness, whose `getfield` on a package-private or private field is an
    `IllegalAccessError` on a JVM, as it already was for a record result's fields: H4 has to give it accessible
    reads.
  - Shared files changed: `equivalence.rs` (`object_of`, `made_of`, `fields_of`, the parameter refusal's words, the
    identical-closure check over every constructor the harness calls), `statement.rs` (`ParameterKind::Object`,
    `Observations.objects`, the constructible assumption's words for objects), `lib/README.md` (step 5 of the
    regression proof, the limits, the domain's kinds), `lib/tests/heap.rs`. No job: every check is inline and small.
- **H3, first step (2026-11-07): results of made classes by their fields, and identity within each version.** In
  regression checks, a result of an application class other than a record of primitive components is compared field
  by field as an object parameter is ([`Layout::result_fields`](../../lib/src/harness/mod.rs)), where it was compared
  by `Objects.equals`, which is identity across two versions' distinct classes; a result class with a field outside
  the supported kinds is a named gap, and one whose fields changed between the versions is refused for H5. Identity
  relations are observed within each version and compared as "holds before iff it holds now"
  ([`Layout::references`, `identity_pairs`](../../lib/src/harness/mod.rs)): the references are the result, each
  array parameter, each object parameter made by its constructor and every object or array field those reach; every
  two under the same path in both versions and of one static type are compared by `if_acmp` (pairs of different
  types are left out: the classes followed extend `Object` directly, so they are never one object). A field of null
  reads as null, a version that throws has a null result, and records of primitive components stay values, compared
  by components only. `stated.observations.identities` lists them (`result == l`, `result.price == l.price`), and
  the replay states which hold in each version (`…, with result == l and result.price == l.price` against `…, with
  result.price == l.price`), so a witness that differs only in identity replays as different.
  - Evidence inline: `lib/tests/heap.rs`, four new checks on the own checker: `withQuantity` handing back its
    argument, rewritten, verified with both relations listed; the alias-to-copy defect (a copy with the same values
    and the same `Money`) refuted, its two replays reading alike but for the relation; a `Line` result compared
    field by field (a rewrite verified, `quantity * 3` refuted with `Line{price=Money{cents=…}, …}`); an array
    filled in place then copied, refuted by `result == a`. Unit tests (185), `heap.rs` (13), `conformance.rs`,
    `foundations.rs` and `integration.rs` pass. `integration.rs` under the other streams' load (615 s, load 5.3)
    timed out once in `the_tools_own_checker_agrees_with_jbmc_on_integer_proofs` ("the solver did not finish within
    the time limit"), as in both earlier steps; alone it passed in 11.6 s. It is a primitive check this change
    doesn't reach.
  - Not yet: a result is compared field by field only where both versions' result classes have the same
    fields (H5 relates different ones), identity relations under `--before-arguments` cover the result alone, and
    the JVM run of such a witness has the `getfield` access problem named under H2 (H4).
  - Shared files changed: `equivalence.rs` (the result's fields worked out and refused by name, the previous
    version's own layout given them, the replays' texts ending in the relations that hold, the observations'
    identities), `statement.rs` (`Observations.identities`, skipped when empty; the words for a result compared
    field by field), `lib/README.md` (step 5 of the regression proof, the JSON's observations), `lib/tests/heap.rs`.
    No job: every check is inline and small.
- **H5's narrow case and `spec::heap::check` (2026-11-07): the joint example's two shapes of `Quote` related by the
  correspondence.** A regression check takes a correspondence (`equivalence::Options::correspondence`, filled by
  `spec::heap::check` from the claim; no command-line flag yet) whose input equations relate a field path of a
  parameter's object in each version, `old.q.cents == new.q.amount.cents`, `old.q.quantity == new.q.quantity`
  ([`spec::heap::relate`](../../lib/src/spec/heap.rs), [`harness::Corresponds`](../../lib/src/harness/mod.rs)). The
  previous version's object is made from the new one's leaves as the equations name them, and an input on which the
  two objects as made don't satisfy them is skipped (the domain, the constructible assumption and the vacuity probe
  say so). After the calls the parameter's objects, and a result of the same pair of classes, are compared under the
  equations, a path through null reading as absent; identity relations are those both versions have (`result == q`).
  The replays are compared through the equations too (`Replayed::views`), each showing its own object, and a
  counterexample names the observations it differs in (`differs`). Refused by name: an equation not between two paths
  (the offset mapping `new.q.amount.cents + 1` included), output relations, a field of the previous version's object
  in no equation (it would leave the count), a leaf of its construction no equation gives, and equations about a
  parameter other than the one in its place; equations about a parameter neither version has are left out with a
  note. Bounds are per version: `stated.domain.input_objects` counts each version's input objects (`[1, 2]`).
  `spec::heap::check` runs the native strict check under the claim's bounds and correspondence and accounts for every
  required observation: preserved where a proof compared it, refuted where the witness differs in it (the rest
  unresolved), unresolved where the check doesn't compare it or the witness differs only elsewhere, and the whole
  result unresolved where a version's inputs need more objects than its bound. A refusal is `Unsupported` with the
  gap's words. `spec::Outcome` gained `problem`.
  - Evidence inline: the integration contract's heap part went from 6 unsupported to 6 passed (`after` `total`,
    `withQuantity` with `identity:result==q`, `discount`; `offset` `total` refuted, witness `total(q=new Quote(new
    Money(0), 1)): before, 0; after, 1`; `alias-to-copy` `withQuantity` refuted; `outside-domain` `total` verified,
    its domain saying constructor-made). `lib/tests/heap.rs`, five new tests on the fixture's kernel: the two shapes
    proved for `total` and `withQuantity`; the offset refuted with the result refuted and the exception unresolved;
    the alias-to-copy defect, where its copy can be made (`--unchanged-unless "quantity <= 0"`), refuted with
    `differs` = `identity:result==q` alone, `before: Quote{cents=0, quantity=1}, with result == q` against `after:
    Quote{amount=Money{cents=0}, quantity=1}`, and the harness source checked; a witness that differs only in an
    observation the claim doesn't require giving unresolved; a correspondence leaving `q.cents` out, no
    correspondence, and an input-object bound of 1 for the new version, each never proved. Two unit tests of
    `relate`. Unit tests (187), `heap.rs` (18), `foundations.rs`, `conformance.rs` and `integration.rs` (64, 26 s at
    load 1.7) pass.
  - For the reconcile loop, about the fixture (not changed here): the `alias-to-copy` defect's copy is made by the
    constructor, which rejects a quantity of 0 or less, so there the defect also throws, and the claim-level witness
    is that exception (`withQuantity(q=new Quote(new Money(0), 1), quantity=0)`); `expected.json`'s "every field
    agrees" holds for a quantity of 1 or more, where only `result == q` tells the versions apart. The kernel claim's
    `allocations: 0` is not checked (the own checker follows every allocation within the unwinding bound), and the
    alias-to-copy copy allocates one `Quote`. The kernel claim is reused for `discount`, whose parameters aren't `q`:
    its contract's inputs (`q: shop.Quote`) don't match the method, which `check` doesn't compare.
  - Also fixed: the harness's Java rendering wrote `before.Object` as the type of an object result (H3).
  - Not yet: output relations and equations other than path = path, a correspondence flag on `regress`, the JVM run
    of such a witness (H4), and examples in 150–159.
  - Shared files changed: `equivalence.rs` (`Options::correspondence`, its reading through `spec::heap::roots` and
    `relate`, the result's equations, the vacuity reason, the replays compared through the views, `differs`),
    `statement.rs` (`Domain::input_objects`, the observations' and the constructible assumption's words under a
    correspondence), `spec/mod.rs` (`Outcome::problem`), `lib/README.md` (step 5 of the regression proof, and
    `spec::heap::check` under the foundations IR), `lib/tests/heap.rs`. No job: every check is inline and small.
- **H4, first step (2026-11-07): regression witnesses over objects run on the JVM with their identities.** A
  counterexample over objects (an object parameter made by its constructor, a result compared field by field, or
  versions differing in a field of an object or an identity relation; `equivalence::observes_objects`) is run on a
  real JVM after the interpreter's replay and the shrinking: the harness on the input, which makes each version's
  objects from the same leaves, with the same identities, as in the interpreter. The JVM loads copies of the
  application classes the harness names (its constant pool's class entries) with the class, its fields, its
  constructors and its static methods made public ([`relocate::opened`](../../lib/src/relocate.rs), placed first on
  the class path by [`jvm_witness`](../../lib/src/jvm_witness.rs)): a record's fields are private and a class's often
  package-private, which a JVM refuses to another package's `getfield`. Field resolution and those calls don't
  depend on access; instance methods keep theirs, which decides overriding. The proof line says `replayed in the
  interpreter and run on a JVM (JDK ...), where the harness fails on it too`, and the counterexample has `jvm`, the
  JDK. Where the JVM's harness holds on the witness the result is unverifiable (the JVM is the reference); where it
  could not run, the interpreter's replay stands and the proof line says why. `spec::heap::check` gives a refutation
  only with that confirmation, and unresolved otherwise. Shrinking changes only the leaves, so it never merges or
  splits objects.
  - Evidence inline: every object refutation in `lib/tests/heap.rs` (a changed result, a change in the object as
    left, the alias-to-copy defect, a `Line` result field by field, an array handed back in place of a copy, the
    joint example's alias-to-copy under the correspondence) now asserts the JVM's confirmation; with the opened
    copies left out, the JVM's harness throws `IllegalAccessError` and the two tests over records' private fields
    fail, as they should. A unit test of `opened` (a private constructor, private and protected fields and a static
    method made public; a private instance method and `<clinit>` left; the code and the pool unchanged). The
    integration contract's heap part: 6 passed, its refutations confirmed on the JVM. Unit tests (188), `heap.rs`
    (18), `foundations.rs` and `conformance.rs` pass. `integration.rs` under the other streams' load (612 s) passed 63
    of 64, failing `the_tools_own_checker_agrees_with_jbmc_on_integer_proofs` as in every earlier step; alone it
    passed in 10.9 s. It is a primitive check, which runs no JVM confirmation.
  - Not yet: a JVM confirmation that disagrees with the interpreter has no test (no such disagreement is known);
    object parameters that may be null or the same object (H2's rest), so a witness with two parameters one object
    is still only an array's, in property checks; property checks over objects.
  - Shared files changed: `equivalence.rs` (`observes_objects`, the JVM run after shrinking, `Counterexample::jvm`),
    `lib/README.md` (step 6 of the regression proof, `spec::heap::check`'s paragraph), `lib/tests/heap.rs`. No job:
    every check is inline and small.
- **Examples 150–152 (2026-11-07): a mutable object input in a subject system.** Crosscut gained a kernel for them,
  gRPC-style retry throttling (`retry.ThrottleLimits`, a record; `retry.Throttle`, a mutable class every call on a
  channel shares, made full by its one constructor; `retry.RetryThrottling`, `recorded` and `reconfigured`), with
  its tests. 150 rewrites `recorded` with `Math.max`/`Math.min`, verified; 151 is the alias-to-copy defect
  (`reconfigured` hands back a copy with the same tokens and limits object where it handed back the throttle),
  refuted by `result == throttle` alone, the witness run on a JVM; 152 is 150's rewrite without the floor at zero,
  wrong only on a throttle calls have drained, which the constructor never makes, so it is verified within the
  constructor-made claim. So that such a verdict can't read as a proof over every state, the verified headline over
  an object made by its constructor now says `behaves as before on every input of constructor-made objects`
  (`equivalence::made_by_constructor`). Tags `aliasing` (defect) and `object-inputs` (technique) added.
  - Evidence inline: the three checks run by the CLI on the classes the patches make (150 and 152 verified with the
    new headline, 151 refuted with `reconfigured(throttle=new Throttle(new ThrottleLimits(1, 1)), …)` and confirmed
    on the JVM); 152's defect shown on a JVM by hand (a two-token throttle after three failures: 1000, 0, 0 against
    1000, 0, −1000 thousandths, then 11 against 21 successes before a retry); Crosscut's tests (52) pass;
    `jvmcontract verify` on Crosscut's contracts passes. `heap.rs` asserts the new headline. Unit tests (188, one
    of them, `jbmc::tests::a_run_that_dies_gives_no_verdict_whatever_it_printed`, a stand-in script's run, failed
    once under load and passed alone), `heap.rs` (18), `foundations.rs`, `conformance.rs` and `integration.rs`
    (64) pass.
  - *For review*, quick jobs submitted at priority 10 but not back within the cycle (no runner was active), the
    build.py runs that record the results and pages: `20261107-064330-example-150…` (verified, the headline `on
    every input of constructor-made objects`), `20261107-064331-example-151…` (violation, the replays differing
    only in `result == throttle`, run on a JVM), `20261107-064331-example-152…` (verified, as 150). Their pages
    are not rendered until then.
  - *For review*, a long job: `20261107-064838`, rerunning the nine Crosscut examples whose recorded claims
    fingerprint the app's sources (025, 076, 120, 127–130, 132, 133), which the new kernel made stale and whose
    pages now say so; expected each to give its recorded verdict (025, 128, 130, 132 violation; the rest
    verified) and none stale after.
  - Shared files changed: `equivalence.rs` (the headline's words, `made_by_constructor`), `lib/README.md` (step 5:
    the headline), `lib/tests/heap.rs`, `examples/tags.json` (two tags), `examples/README.md` and `index.json`
    (rendered; the nine stale pages too, with their warning). Also changed, owned by no stream: Crosscut's sources, tests, README (a row) and `api.contract`,
    which `jvmcontract update` regenerated and which was stale before (`ratelimit.Window` and `retry.Backoff`
    were missing from it).
- **H2, third step, and H4's rest (2026-11-07): object parameters that may be null or one object, in regression
  checks.** `jvmcontract equivalence` takes `--nullable l` and `--may-alias from,to` (closed under chains; the
  receiver as `this`) for object parameters made by their constructor, and `spec::heap::check` passes a claim's
  `ObjectDomain` `nullable` and `may_alias` (parameters only; a field path is `Unsupported`). The harness makes each
  choice with a boolean input of its own appended after every leaf (`l.null`, `to.same.from`;
  [`Layout::choose`](../../lib/src/harness/mod.rs), `Choice`, `Made`), in both versions alike: null first, then the
  same object as an earlier parameter of the group, a choice naming a parameter that is null itself passed over so
  that a parameter that may not be null never is, otherwise its own object; an object made null has no fields to
  compare. The own checker's H1 merging turns the three ways into one choice. The domain says so (`…, from any
  arguments it accepts, or null`; `; from and to may be the same object`), and so do `stated.domain`'s `null` and
  `may_alias`. Witnesses keep identity: `move(from=new Line(new Money(0), 1), to=the same object as from)` is one
  object in the interpreter's replay, the shrinker (`shrink_in_harness_keeping`, which never changes a flag) and the
  JVM run, and `--json`'s call gives it as `{"same": "from"}`; `size(l=null)` likewise. So H4's "a witness that
  needs two parameters to be the same object replays with one object" now holds in regression checks too. Refused
  by name: a record of primitive components, an array or primitive parameter (arrays are a property check's), a
  parameter the previous version gets through `--before-arguments`, `--nullable this`, and two parameters of
  different classes. JBMC checks the same harness (the choices are plain boolean inputs), so `--engine jbmc` and
  `--confirm` need no refusal.
  - Evidence inline: `lib/tests/heap.rs`, four new tests: a buffered `move(from, to)` verified over two lines of
    their own and refuted under `--may-alias from,to` with one object (`differs` has `field:from`, both replays
    `with from == to`), confirmed on the JVM, while the rewrite in the other order is verified there; a dropped null
    check verified by default and refuted under `--nullable l` with `size(l=null)` on the JVM, its correct rewrite
    verified; refusals for an `int` and an array parameter; the kernel claim with `q` nullable verified under the
    correspondence and a field path unsupported. A harness unit test of the flags' places, the resolution rule, the
    domain words, the Java rendering and the bytecode's branch targets. Unit tests (189), `heap.rs` (22),
    `foundations.rs`, `conformance.rs` and `integration.rs` (64, 23 s at load 0.9) pass.
  - Not yet: property checks over objects; a field of an input object that may be null or shared (its object's
    constructor decides it); arrays that may be null or one in a regression check. No example: Crosscut's kernels
    have no method whose bug needs two parameters to be one object, and a source change there makes its recorded
    examples stale again (job `20261107-064838` is rerunning them).
  - Shared files changed: `equivalence.rs` (`Options::nullable`, `may_alias`, the choices made after the layout, the
    shrinker keeping the flags), `statement.rs` (the parameter's `null` and the domain's `may_alias` for objects),
    `main.rs` (two flags on `equivalence`), `lib/README.md` (step 5, `--json`'s domain), `lib/tests/heap.rs`. No job:
    every check is inline and small.
- **H2's rest (2026-11-07): object parameters in property checks.** `jvmcontract prove` takes a static method with
  parameters of application classes, each made in the harness by its constructor from symbolic leaves, as in a
  regression check (`equivalence::made_of`, a record by its canonical constructor too), and an object result read by
  its fields ([`harness::generate_property_over`](../../lib/src/harness/mod.rs) over a `Layout`). An input a
  constructor rejects is skipped (a constructible assumption in the statement), and so is one on which the
  assumption throws. The expression language reads field paths, `l.price.cents`, and under `\old` before the call
  (`Expr::Field`, `Expr::OldField`, read by the harness first, a path through null throwing when read), and compares
  references, `result == l`, `result.price == l.price`, `l == null` (`Expr::Refs`;
  [`expr::parse_over_objects`](../../lib/src/harness/expr.rs)). `--nullable l` and `--may-alias from,to` on object
  parameters are the harness's flags (`Layout::choose_in`), so JBMC takes them too, unlike an array's. The domain
  and the headline say what is covered (`on every input of constructor-made objects`). A witness is a recipe that
  keeps its choices (`move(from=new Line(new Money(0), 1), to=the same object as from)`, `size(l=null)`); since the
  property reads the heap, the interpreter checks it by running the harness itself, the shrinker keeps the flags,
  and the harness runs on a JVM with the classes opened, which is the reference.
  - Evidence inline: `lib/tests/heap.rs`, six new tests on the own checker over the object kernel: `bump`'s
    `l.quantity == \old(l.quantity) + 1 && …` verified, and its `+= 2` defect refuted with `bump(l=new Line(new
    Money(0), 1))`, leaving `quantity=3`; `withQuantity`'s `result == l && …` verified and the alias-to-copy defect
    refuted (while the same property without `result == l` holds on it); `size` under `--nullable l` verified, and the
    dropped null check refuted with `size(l=null)`, an assumption through null skipping the input; `move` under
    `--may-alias from,to` verified, and the buffered defect refuted with one object, though it holds on two of their
    own; `checked`, wrong only on a quantity the constructor rejects, verified within the constructor-made claim;
    refusals by name (a `String` field, `\old(l)`, `l.price == l`, an unknown field, `--nullable` on an `int`). Every
    refutation confirmed on the JVM. A harness unit test (the leaves and flags, the Java rendering, the `\old` read,
    the bytecode's branch targets, and the plain harness's handlers unchanged). Unit tests (190), `heap.rs` (28),
    `foundations.rs`, `conformance.rs` and `integration.rs` (64, 25 s at load 4.8) pass.
  - *For review* unless it comes back in this cycle: quick job `20261107-072431`, the new ignored test in `heap.rs`,
    the eight properties under `--engine jbmc` and `auto --confirm`: expected exit 0, the four correct ones verified
    and the four defects refuted with witnesses confirmed on the JVM.
  - Not yet: an array parameter's `--nullable`/`--may-alias` in a property that has object parameters too (refused);
    an array field in an expression; a call of the method under proof when it takes objects; which throws clause
    applied, in a counterexample over objects (the conditions are evaluated in the harness only). From the earlier
    steps: a field of an input object that may be null or shared, and arrays that may be null or one in a
    regression check.
  - Shared files changed: `property.rs` (the object layout, the choices split between arrays and objects, the
    witness checked in the harness and on a JVM), `equivalence.rs` (`made_of`, `fields_of` and
    `made_by_constructor` made `pub(crate)`), `statement.rs` (`property_assumptions`), `main.rs` (the two flags'
    help), `lib/README.md` (a paragraph under the property proof, the limits), `lib/tests/heap.rs`.
- **H5's rest, first step (2026-11-07): output relations for the result, and `--correspondence FILE`.** A
  correspondence's output relation for the result takes the place of `--results-agree-when`: a boolean over
  `old.result`, `new.result` and the new parameters, rewritten to one over `previous` and `result`
  ([`spec::heap::output_relation`](../../lib/src/spec/heap.rs)), so a result that became a value object is related
  by `old.result == new.result.cents`. A result that is an object of an application class is in a result relation
  (either kind) by its field paths, of whatever shape in each version, `old.result.cents == new.result.amount.cents
  && …`, read through the objects in the harness ([`harness::Relation`](../../lib/src/harness/mod.rs)'s
  `previous_object`, `result_object`; `Fields::under`); two nulls agree, one alone does not, a path through null
  doesn't hold. Identity relations are still compared, so the alias-to-copy defect is refuted under such a relation
  by `result == q`. A replay evaluates it on each result's field paths as the call left them
  (`Replayed::result_paths`, [`expr::eval_reading`](../../lib/src/harness/expr.rs)), the harness run in the
  interpreter deciding the rest; a witness the relation fails on differs in `result`, and the JVM runs it.
  `jvmcontract equivalence --correspondence FILE` reads the IR's JSON (`golden/correspondence.json` as it is). In
  `spec::heap::check`, a required observation under an output relation is compared under it, not for equality, so
  it is unresolved whatever the check finds (`true` would otherwise hide the offset defect) until the contract's
  `approved_changes` has it, then changed with approval if proved, refuted if the witness breaks the relation. Also
  fixed: the previous version called without `--before-arguments` compared its parameter types with the flat leaves,
  so a result relation with an object parameter was refused; it compares with the layout's types now.
  - Evidence inline: `lib/tests/heap.rs`, four new tests: `objects.Kernel#price` (a `long` that became a `Money`)
    verified under `old.result == new.result.cents`, refused without it, and a cent too much refuted with
    `price(l=new Line(new Money(0), 1))`, `0` against `Money[cents=1]`, on the JVM too; the fixture's `withQuantity`
    between the two `Quote`s with its result related by field paths verified, the alias-to-copy defect refuted by
    `identity:result==q` and never by `result`, and a relation the versions break refuted with the note and
    `differs = [result]`, on the JVM; the claim's accounting (`true` on the offset build unresolved, approved changed
    with approval; a broken relation unresolved); the CLI with the golden file (verified on `after`, exit 1 on
    `offset`, a malformed file named). A unit test of `output_relation` (renaming, words left alone, three
    refusals). Unit tests (191), `heap.rs` (32), `foundations.rs` and `conformance.rs` pass; `integration.rs` passed
    63 of 64 in 612 s under load, failing `the_tools_own_checker_agrees_with_jbmc_on_integer_proofs` as in every
    earlier step, which passed alone in 8.2 s (a primitive check this change doesn't reach).
  - *For review*: quick job `20261107-080218` (no runner was active), the new ignored test in `heap.rs`, the five
    checks under `--engine jbmc` and `auto --confirm`: expected exit 0, the two correct ones verified and the three
    others refuted with witnesses run on a JVM.
  - Not yet: output relations for other observations (a parameter's field, an identity relation) or over the
    previous version's parameters; equations other than path = path; a result relation's object paths through an
    array field.
  - Shared files changed: `equivalence.rs` (the result relation taken from the correspondence, an object result's
    fields under a relation, the replay's evaluation of it), `main.rs` (`--correspondence`), `lib/README.md` (step
    5, `spec::heap::check`'s paragraph), `lib/tests/heap.rs` (a `price` method in the object kernel's three builds).
- **H5's rest, second step (2026-11-07): input equations that compute.** An input equation's new side may be an
  expression over primitive field paths of one parameter's new object that are leaves of its construction, giving
  the previous version's field (`int`, `long`, `boolean`): `Price(long cents)` before and `Price(long dollars, int
  cents)` now are related by `old.p.cents == new.p.dollars * 100 + new.p.cents`
  ([`harness::Computed`](../../lib/src/harness/mod.rs), `Source`, `Leaf`; `FieldEquation::computed`). The harness
  computes the previous constructor's argument from the new leaves before the calls (`new
  before.prices.Price((long) (p_dollars * 100 + p_cents))`), and after them compares the expression over the new
  object's paths with the previous field, for the parameter as left and a result of the same pair of classes, absent
  where a path goes through null; a division by zero skips the input as a constructor's rejection does, in the
  harness and the replay alike. The interpreter's replay and the `--json` call compute it too, and the replays'
  views read through it. In `spec::heap::check`, an equation that computes a field of an input the preservation
  contract anchors (derivation `identity`) is `Unsupported`, the right expression as well as an offset one, which the
  tool can't tell apart; under a derivation a person stated, an equation among its `&&` conjuncts stands, and one it
  doesn't have is refused ([`spec::heap::anchored`](../../lib/src/spec/heap.rs)). An input the contract doesn't name
  is internal, and the correspondence's to state. Refused by name: an old side that is not a path, a new side that
  reads the previous version's input, a parameter as a whole, several parameters, a path that is no leaf, or has a
  type that doesn't fit the field.
  - Evidence inline: `lib/tests/heap.rs`, a price kernel (`prices.Price`, `prices.Prices`) and two tests:
    `total`, `doubled` and `raise` verified between the two shapes, the harness's source checked; a cent too much in
    `total` refuted (`differs = [result]`) and a carry into the dollars dropped in `raise` refuted (`differs =
    [field:p]`), both on the JVM; the offset equation `… + 1` proving the defect equivalent where no contract anchors
    `p` (the model case), refused by a claim that anchors `p`, as is the right one, and under a stated derivation the
    right one refuting the defect and proving the rewrite, the offset one stated proving the defect, and an equation
    the statement doesn't have refused. Three unit tests (`relate` with an expression, seven refusals, the anchoring
    rule). Unit tests (194), `heap.rs` (34), `foundations.rs`, `conformance.rs` and `integration.rs` (64, 22 s at
    load 1.2) pass.
  - *For review* unless it comes back in this cycle: quick job `20261107-083358`, the new ignored test in `heap.rs`,
    the five checks under `--engine jbmc` and `auto --confirm`: expected exit 0, the three correct ones verified and
    the two defects refuted with witnesses run on a JVM.
  - Not yet: an expression over several parameters (`old.q.total == new.q.price * new.n`), or over fields that are
    not leaves of the construction; a computed equation whose field is of another primitive type (`short`, a float);
    an old side that is an expression.
  - Shared files changed: `equivalence.rs` (two comments, the `correspondence` option's doc), `lib/README.md` (step
    5, `spec::heap::check`'s paragraph), `lib/tests/heap.rs` (the price kernel).
- **H5's rest, third step (2026-11-07): output relations for an object parameter's field as the calls leave it.**
  A correspondence's output relation for `field:p.cents` (a previous version's path; `field:p` for the whole object)
  is a boolean over primitive field paths of that parameter's two objects, `old.p.…` and `new.p.…`
  ([`harness::FieldRelation`](../../lib/src/harness/mod.rs) on `Corresponds::relations`, made by
  [`spec::heap::relate`](../../lib/src/spec/heap.rs)), compared after the calls in place of the input equations about
  that path or under it, which still make the previous object and are still assumed of the two as made: a `raise`
  that now rounds up to whole dollars is related by `new.p.dollars * 100 + new.p.cents - old.p.cents >= 0 && … <
  100`. A path through null makes it fail. The observations say so (`p: under the correspondence; p.cents under the
  output relation …`); the replay evaluates it on both objects' paths as left (`Replayed::object_paths`), and a
  witness it fails on differs in `field:p.cents`, with a note (`p.cents as the calls leave it is not related by …`).
  A counterexample's `differs` now also names each previous version's path its correspondence views read differently
  (`field:p` and `field:p.cents`), so that a claim requiring a path can be refuted in it. In `spec::heap::check`, a
  relation for a field path bears on the required observations of that path, of paths under it and of the object
  above it, and is approved by a change of its own path or one above it: unresolved without approval (`true` on the
  dropped-carry defect included), changed with approval when proved, refuted when the witness breaks it. Refused by
  name: a relation for a parameter no input equation relates, for a path the previous object doesn't have, two that
  overlap, one that reads another parameter or a parameter as a whole, one that is not a boolean, and still one for
  an identity relation.
  - Evidence inline: `lib/tests/heap.rs`, a `rounded` build of the price kernel and two tests: rounding up refuted
    under the equation alone (`differs = [field:p, field:p.cents]`) and verified under the relation, with the
    observations' words and the harness's source checked; the exact `raise` verified under it; the dropped carry
    refuted in `field:p.cents` with the note, on the JVM; an unknown path named. The claim's accounting: refuted in
    `field:p.cents` without the relation; unresolved under it, and under `true` on the defect; approved by
    `field:p.cents` or `field:p`, changed with approval, and the defect refuted; an approval of `field:p.dollars`
    approving nothing. Two unit tests (the relation's reads, evaluation and refusals; `within` and `overlaps`), and
    `output_relation` leaving field relations to `relate`. Unit tests (196), `heap.rs` (36), `foundations.rs`,
    `conformance.rs` and `integration.rs` (64, 22 s at load 1.4) pass.
  - *For review*: quick job `20261107-085410` (no runner was active), the new ignored test in `heap.rs`, the four
    checks under `--engine jbmc` and `auto --confirm`: expected exit 0, `rounded` without the relation and `defect`
    under it refuted with witnesses run on a JVM, `rounded` and `after` under it verified.
  - Not yet: output relations for identity relations or over the previous version's parameters as the call got
    them; a relation for a field of a parameter whose two versions have the same shape and no input equations; a
    view's paths through an object field (`differs` names leaf paths only under a correspondence).
  - Shared files changed: `equivalence.rs` (the refusal of a relation no parameter took, the replays' evaluation of
    field relations, the `correspondence` option's doc), `statement.rs` (the objects' words under a field relation),
    `lib/README.md` (step 5, `differs`, `spec::heap::check`'s paragraph), `lib/tests/heap.rs` (the `rounded` build,
    the relation test's words for `field:l.quantity` changed to the new refusal).
- Next: H5's rest, fourth step: an input equation's expression over several of the new version's parameters,
  primitives among them (`old.q.total == new.q.price * new.n`), made before the call and compared after it.
- Status: working

## Loop settings

- session: 750c8a36-92b9-44e3-adad-ef96dc6aa676
- model: claude-opus-5-5
- effort: high
- workspace: heap
- fork: ae994066-d1ea-4620-b03e-176a07061175

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. Your core is above: don't stop before
it unless a step needs the user. When a step's evidence is a long job, submit it and go on; a job is never a reason to stop, and a quick one is awaited only as above. Stop
with `done` when your phases are finished, or `blocked: ...` when what is left needs the user and is recorded under
Progress. Items deferred by the timebox count as recorded deferrals, never as a reason to keep going. Don't go on to polish, and don't start another stream's work.

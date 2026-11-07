# Stream brief: foundations, entry-point observations

One of four streams of [`foundations.md`](foundations.md) that run in parallel, each in its own jj workspace on its
own branch. The others are [`foundations-heap.md`](foundations-heap.md),
[`foundations-summaries.md`](foundations-summaries.md) and [`foundations-alignment.md`](foundations-alignment.md).
Once all are finished, a reconcile loop merges them; [Streams](foundations.md#streams) in the main brief says how.

Started with the others by `llm-dlc/tools/run-streams.sh foundations` from the default workspace, or alone with
`llm-dlc/tools/feature-loop.sh foundations-observations` from this stream's workspace
(`jj workspace root --name observations`): the loop refuses any other.

**The main brief is the instruction.** Read [`foundations.md`](foundations.md) in full every cycle, and its three
inputs too. Its direction, starting point, working rules, deferrals and decisions all apply here. This file says which
part of its plan is yours, and keeps your Progress. Within the briefs, edit only this file's `## Progress` section;
edit implementation files according to the ownership rules below.

**Every cycle, read the integration check** first: `$(jj workspace root --name default)/llm-dlc/loop-summaries/foundations-integration.md`,
if it exists. A failure in your part of the [integration contract](foundations.md#phase-0-the-shared-ir-and-the-integration-contract)
on the latest combined commits is your next piece of work.

## Your phases

Priority 3: move checking from methods to what an application's consumers observe. In order:

- **O1. An observation spec per entry point.** From the boundary analysis, for each route, listener and schedule:
  - its inputs: the bound request parts and their wire types, or the message payload. These are the external inputs
    of the entry point's preservation contract, which inference below it can't change;
  - what a consumer observes: the response's wire type, the status for each outcome (from `failures.rs`'s mapping),
    and each effect: `writes` to a store (with the document type), `sends`, `publishes` and outgoing `calls`, each
    with its payload type and its place relative to the transaction;
  - which identity relations count at this boundary (none for a serialized response; for a Java API returning
    mutable objects, the heap stream's defaults);
  - what the analysis can't see, named (a call it couldn't resolve, a dynamic route). An unresolved boundary stays in
    the spec as unresolved; it never vanishes from it.

  As Phase 0's observations, with a stable id per entry point and per observation, from a new command
  (`jvmcontract observations`, `--json`). Box Office is the test bed; every entry point there gets a spec, checked by
  hand against its source once and then by a test.
- **O2. Two builds compared into obligations, accounted for.** Match entry points across two builds (same route and
  verb, same topic or queue, same schedule; a renamed handler is still the same entry point), and for each pair list
  the obligations: each required observation preserved, changed (a status mapping, a payload's shape, an effect moved
  out of the transaction), new or removed, and what a proof of each would need. The accounting is the point: every
  observation of the old build is in the count as preserved, changed with approval, or unresolved. An unchanged
  payload *type* doesn't discharge preservation of payload *values*; it only means the obligation is well formed.
  Static, no proofs. Checked on Box Office examples 110–119, whose recorded boundary diffs are the ground truth.
- **O3. The first obligations discharged.** The contract, deliberately narrow: *the ordered trace of modeled
  boundary-call attempts, with the response and the supported failure outcome, is preserved under an explicit
  environment model.* For an entry point whose handler's decision path is within the own checker's fragment
  (primitive and record inputs today; objects once the heap stream merges), generate the regression check:
  - **Recording stubs.** The store's, broker's and client's methods the spec names are replaced, in both versions, by
    stubs that append to the effect log through Phase 0's hook: the call's kind and target, and a *snapshot* of its
    observed payload values taken at the call, never a reference inspected later.
  - **One environment for both versions.** Corresponding calls receive the same modeled outcome (a return value or a
    failure), chosen symbolically within what the environment model allows. Neither version gets outcomes the other
    doesn't, and "every call succeeds", if chosen, is stated as the model's restriction.
  - **Exact order** first. It may reject harmless reorderings; that is preferable to assuming effects commute.
  - **Bounds visible.** A log that reaches its bound makes the result unresolved, never a shorter trace.
  - **What it means.** A recorded `save` means the application attempted it, not that anything was committed or
    delivered. The stubs and the environment model are named as assumptions, and a witness replayed on the JVM is
    replayed *under the modeled dependencies*, which the result says; it is not a run against real infrastructure.

  Do first the case the joint example needs (its boundary-preservation row): its one entry point and one outgoing
  effect, with a dropped effect and a duplicated one refuted by replayed witnesses. Then, from your reserved block, a
  Box Office or Crosscut entry point refactored correctly and proved, with the same two defects in siblings.

**Your core:** O1, O2, and O3's narrow case for the joint example. The rest of O3 comes after.

Not yours: object inputs (heap; until it merges, refuse entry points that need them, as a named gap), the cache
(summaries), inferring a handler's internal correspondence (alignment). The effect-transition IR, persistence and
delivery semantics and TLA+ from effects are [deferred](foundations.md#deferred-not-in-this-loop): the spec and the
trace here are their inputs, so keep them free of anything proof-engine-specific.

## Boundaries

You own `lib/src/spec/observe.rs`, your interface in the shared IR, which returns a named `Unsupported` until your
part is done; your checks in `lib/tests/foundations.rs` turn from unsupported to passed as you do it. You also own `lib/src/boundaries.rs`, `reach.rs`, `failures.rs`, `wire.rs`, `store.rs`, the new observation module and its
command, the recording stubs and the environment model, the effect-log hook behind Phase 0's interface, and Box
Office's examples and build logic, with their tests. The boundary contract keeps its format: `boundaries.contract`
files and their drift check don't change unless a test shows a bug.

The shared files are the main brief's [list](foundations.md#streams). Name every change to one of them under Progress.
O3's checks go through `equivalence.rs` as a new caller of the existing harness, with effects through the hook; the
rest of `harness/` is the heap stream's. If the hook's interface turns out too narrow, extend it by adding, and say so
under Progress.

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

- **O1, step 1 (2026-11-07): the observation spec module and its command, on the joint example.**
  `lib/src/observations.rs` builds one `EntryPointSpec` per route, message listener, schedule and application-event
  listener from the boundary analysis's facts: stable ids (`POST /quotes`, `kafka TOPIC`, `schedule ARGS`,
  `event TYPE`, with the handler appended only when two share one), inputs with their bindings (identity
  derivations), the result, exception and a route's status per outcome (from `failures.rs`), one effect observation
  per modeled call with its payload snapshot paths, each effect site with its kind, target and transaction
  placement, the identity policy (none at a serialized boundary), the environment model (every modeled call, reads
  included, outcome `returns`, trace bound 4, exact order; the restriction to normal returns stated as an
  assumption), and the unresolved parts (dynamic call sites such as string concatenation, calls the walk can't
  follow, computed targets, framework-supplied parameters, destinations from configuration).
  `reach.rs` now records each effect's call site (`Reach::sites`, `dynamic`, `unresolved`); the boundary contract's
  text is unchanged (the integration tests' drift checks pass). `observe::entry_points` returns the specs, so the
  integration contract's `observations specs before` passes. New command `jvmcontract observations PATHS
  [--classpath] [--json]`. Tested by `lib/tests/observations.rs` (4 tests: the spec of `POST /quotes` field by field;
  `POST /quotes/text`'s concatenation named as unresolved; the refactor leaves every spec unchanged, the effect
  defects leave the observations unchanged, the renamed route is another id; the command's text and JSON).
  Shared files touched, by adding: `lib/src/main.rs` (the command), `lib/src/lib.rs` (the module), `lib/tests/observations.rs`
  (new), `lib/README.md` (a section, and the command under Commands). `EntryPointSpec` in `observe.rs` gained fields
  (`kind`, `declared`, `bindings`, `response`, `statuses`, `effects`, `identity`, `assumptions`, `source_line`,
  `method`), all with serde defaults; its existing fields keep their meaning.
- **O1, step 2 (2026-11-07): Box Office, every entry point.** The 13 routes, listeners and schedules of
  `ticketing-service` (9), `payment-service` (3) and `messaging` (1) have specs (the boundary contracts' larger
  entry-point counts include `@Bean` definitions). Checked by hand against the source and the boundary contracts,
  which turned up three bugs, now fixed: the walk didn't follow sibling modules, so the outbox and inbox writes,
  the placement inside `Transactions.run` and the guards' 500s were missing (`observations::analyse` now takes the
  entry-point classes and the followed classes apart, as `boundaries::analyse_in` does, and the command has
  `--base DIR`, as `verify` has); a `Class` argument was expanded into the document's fields as payload
  (`reach.rs`'s `argument_types` now keeps a class literal's declared type); and a method inherited from the
  library (`Enum.ordinal`, `Object.getClass`) was named unresolved (now a library call). The trace bound is now at
  least the number of effect sites (the payment listener has five). After the fixes the specs' reads, writes, sends
  and throws match the boundary contracts', and `verify` still passes on all three modules. Tested by two new tests in
  `lib/tests/observations.rs`, which build Box Office offline with its own Gradle build in a copy under the target
  folder (about 7 s): every module's specs equal golden text in `lib/tests/fixtures/boxoffice-observations/`
  (`JVMCONTRACT_BLESS=1` rewrites it), and the facts read off the source hold (`POST /orders` writes the order and
  the outbox entry inside one transaction, its statuses 500/409/404 and an unknown one for the `ResponseEntity`; the
  hold route's three bindings; the payments listener's payload and inbox write; the sweep's configured schedule;
  the relay's computed topic named as unresolved). Shared files touched, by adding: `lib/src/main.rs` (`--base`),
  `lib/tests/observations.rs`, `lib/tests/fixtures/boxoffice-observations/` (new), `lib/README.md`. O1 is done.
- Not this stream's to fix: `sync.py check` reports "session … has no manifest" for the other streams' commits
  (alignment, summaries and heap alike), whose manifests are on their own branches; the reconcile merge brings them
  together. None is in this branch's own commits.
- **O2, step 1 (2026-11-07): two builds' specs compared into accounted obligations, on the joint example.**
  `observations::compare` (behind `observe::compare`) matches entry points by what consumers address: verb and route
  with path variable names erased, topic or queue, schedule; a renamed handler is the same entry point, a renamed
  route is removed plus new (the handler now serving the new route is named), and several under one key whose
  handlers all changed are unresolved. Each observation of each old entry point gets exactly one obligation:
  preserved (to prove: the shapes agree, which discharges nothing), changed (a shared outcome mapped to another known
  status, a status only one build can answer when all are known, a payload path gone or added, an effect site moved
  into or out of a transaction or to another target, another response type), removed, or unresolved (a status
  unknown, or no way to tell the pair). Two further obligations: `inputs` (changed when the external inputs or their
  bindings differ, since the input domain is the contract's) and `unresolved` (what the analysis can't see of either
  build). Each says what discharging it would need; differences that change no shape (an outcome replaced by one with
  the same status, a second call site) are listed for the proof. `observations::unaccounted` checks the accounting.
  New option `jvmcontract observations ... --against OLD.json` prints the obligations (text with the count, or
  `--json`). The integration contract's six `observations compare` checks now pass (7 passed, 17 unsupported, 0
  failed, with `observations specs before`). Tested by five new tests in `lib/tests/observations.rs` (the joint
  example's builds and defects; a renamed handler and a renamed path variable; each kind of changed shape on a spec
  changed by hand; entry points a key doesn't tell apart; the command), and Box Office's specs compared with
  themselves give nothing changed, removed or new. Full `cargo test` passes (rustfmt and clippy aren't installed
  here, so neither was run). The dropped and duplicated effects give no static difference, as expected: their
  effect obligation is preserved-to-prove, for O3's trace to refute. Shared files touched, by adding:
  `lib/src/main.rs` (`--against`), `lib/tests/observations.rs`, `lib/README.md` (a paragraph and the command).
  `Obligation` in `observe.rs` gained `new_entry`, `differences` and `needs`, with serde defaults, and `Change`
  derives `PartialOrd`/`Ord`; their existing meaning is unchanged.
- **O2, step 2 (2026-11-07): Box Office examples 110–119, each compared with Box Office as it is.** A new test in
  `lib/tests/observations.rs` applies each example's patch to a copy of the sources, compiles the modules it changes
  with `javac -parameters` (as the Gradle build does) against the base build's class path, compares every module's
  specs with the base's, and holds every obligation that isn't preserved-to-prove or unresolved to what the example's
  recorded boundary diff says changed at the entry points, with the differences that say it. The gaps it showed are
  closed in the spec: an outcome the framework takes before the handler runs, with the requests it is for
  (`StatusOutcome::when`): Bean Validation of a `@Valid` or `@Validated` body (`MethodArgumentNotValidException`, 400
  unless an `@ExceptionHandler` takes it, for a body that fails one of the constraints it runs), and a parameter that
  can't bind, from `binding::check` (`MissingPathVariableException`, a 500 on every request); and a body's wire shape
  as the input domain (`Binding::shape`, the wire block's lines with their `!` lines). The comparison gained: such an
  outcome only one build has, or for other requests, is changed (110's dropped `@Valid`, 113's new `@NotNull billing`
  with `! constraints on Billing are not checked` named in `inputs`); a build that fails every request before the
  handler changes every observation of the handler (118); a status one build answers for an exception and no
  exception of the other does is changed even beside a normal return whose status is unknown (119: the 409 is gone);
  beside an effect attempt that is gone, what the new build attempts instead is named (117); a new effect in an entry
  point the old build has needs approval or a proof it's never reached, and the count says how many (116, 117). 111,
  112 and 114 change no spec at all: what no entry-point spec observes (configuration values, what an encoded payload
  holds beyond its snapshot paths, advice such as caching, field names in query strings) is printed under every
  comparison (`observations::NOT_OBSERVED`). 115 is a changed insert payload path. Also fixed: `observations --base .`
  (relative) followed no sibling module, since the class path entries are absolute; the base is now compared
  canonically, as `verify` does. Each example's `notes` says what its comparison gives. The two lines O1 step 2 added
  to `examples/apps/boxoffice/README.md` are removed again: `build.py` digests the whole tree into its claim records,
  so they marked the recorded results of 006, 012, 110 and 111 stale; `lib/README.md` says the same. Full `cargo
  test` passes; the observations suite takes about a minute (the Gradle build and ten javac builds). Shared files
  touched, by adding: `lib/src/main.rs` (`--base` canonical), `lib/tests/observations.rs`, `lib/README.md`,
  `examples/index.json` (rendered notes). `observe.rs` gained `Binding::shape` and `StatusOutcome::when`, with serde
  defaults. O2 is done.
- Also not this stream's to fix: `sync.py check` reports five old `main` commits whose trailers point at session
  `c2bd9df4`'s log `1f2230c9f137`, which their manifest doesn't list; the verification loop rewrote them at 04:44
  in a change (`uvmurzwkyukn`) whose manifest lists it, and that change isn't in this branch.
- Next: O3, narrow case: the effect-log hook (`observe::effect_log`) and `observe::check` for the joint example's
  `POST /quotes`, with recording stubs for its one outgoing send, one environment model for both versions, exact
  order and a visible bound, through `equivalence.rs` as a new caller of the harness; the dropped and the duplicated
  effect refuted with witnesses replayed under the modeled dependencies, and the refactor proved (a quick job if it
  needs a proof run).
- Status: working

## Loop settings

- session: e65240e3-5cf7-41e9-b648-0b36ce9f1129
- model: claude-opus-5-5
- effort: high
- workspace: observations
- fork: ae994066-d1ea-4620-b03e-176a07061175

## Loop until

Go on while one of your phases has a step that needs nothing but your own work. Your core is above: don't stop before
it unless a step needs the user. When a step's evidence is a long job, submit it and go on; a job is never a reason to stop, and a quick one is awaited only as above. Stop
with `done` when your phases are finished, or `blocked: ...` when what is left needs the user and is recorded under
Progress. Items deferred by the timebox count as recorded deferrals, never as a reason to keep going. Don't go on to polish, and don't start another stream's work.

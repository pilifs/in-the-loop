# Brief: domain advances, the preservation stream

A stream of [domain-advances.md](domain-advances.md), which is the instruction: read it in full first, its
Direction and "How to work through it" above all. You own one outcome across the whole stack.

## The outcome

**Intent.** A security fix that adds an input restriction to a public entry leaves the entry's approved behaviour
unchanged everywhere else. For CVE-2025-22228 (example 287): `BCryptPasswordEncoder.matches` on 6.3.8 rejects a
candidate of more than 72 UTF-8 bytes, and for every other candidate and stored hash, null and malformed ones
included, it ends as 6.3.7 does: the same result or the same exception.

**Working formalization.** `claims/in-range-matching-preserved.json` of example 287, frozen: over the adapter's
parameters (`candidate`, `storedHash`, each null or at most 80 units), outside the allowed change (`candidate !=
null && candidate.getBytes(UTF_8).length > 72`), both releases agree. Expected: established.

**Why it is hard.** Both releases run bcrypt. Only `BCrypt.hashpw(byte[], String, boolean)` differs between them
(`sources.lock.json`); `crypt_raw`, the key schedule and the S-boxes are the same bytecode. The checker covers
bcrypt's loops with invariants it finds ([`lib/src/bmc/loops.rs`](../../lib/src/bmc/loops.rs)), and such an
invariant forgets what the loop wrote: the S-box contents become any values, on each side independently. Two
executions that are equal in fact are then not equal in the formula, and no amount of unwinding brings that back
(a key schedule runs `2^cost` times). What is lost is the *relation* between the sides, not precision on either.

## Your work

1. **Reproduce the first failure on today's checker.** Example 287's `proofs/prove.py` has no equivalence branch
   (it is "prove only"). Give it one in the shape of 289's driver (`examples/289-*/proofs/prove.py`: `jvmcontract
   equivalence --before ... --after ... --before-classpath ... --assume ... --unchanged-unless ...`, with
   `accept.record` and the mutant rule), and queue `preservation` at the frozen bound as a job, with a `--work`
   folder of its own. The README's last observation (2026-11-16) was a refusal before any proof: a nullable String
   in a regression check (VF-028), and a String parameter in the allowed-change expression. 289's preservation,
   decided a day later, passes String expressions through javac, so the second may be gone; find out where it
   stops now and record it in the example's notes with the job. Do not narrow the claim to get past a refusal:
   lift the refusal, or record it.
2. **Find the smallest boundary at which the two sides can be related.** Candidates, cheapest first; pick by
   evidence, and say in Progress why:
   - *The unchanged callee as one function of both sides.* Where old and new call a method whose bytecode and
     whose callees' bytecode are identical, on arguments and reachable state the formula shows equal, the call's
     result and effects are equal: run it once, or twice with the results identified. `lib/src/shared.rs` and
     `equivalence.rs:1800` already do this for a changed *pure helper of primitives* proved equivalent; bcrypt
     needs it for an *unchanged* method over arrays that reads final static tables and writes arrays it was
     given or made. The side conditions are the content: the same bytecode closure, equal arguments including
     array contents, no aliasing difference, the static tables never written, the same exceptional exits.
   - *A coupled loop invariant.* Run the two loops in step and let the invariant say "this array on the old side
     equals that one on the new side", which the independent invariants cannot state.
   - *Joint execution from the point the sides converge.* After `hashpw`'s changed prefix, if both sides reach
     `crypt_raw` in equal states, one continuation serves both.
   The congruence machinery (`lib/src/congruence.rs`, and how the own checker ties equal products in
   `lib/src/bmc/bits.rs`) is the existing precedent for "a function gives equal results on equal arguments".
3. **Make it sound before making it general.** For whichever rule you add, the challenge stream will try: a
   changed round or helper inside the closure; unequal initial arrays; an alias on one side only; a dependence on
   a mutable static; an exceptional exit on one side. Write those countermodels yourself first (fixtures beside
   `lib/tests/fixtures/claims/claims/Effects.java`, or pairs written inline as `lib/tests/pairing.rs` does), each
   failing before the rule's side condition is in. The foundation found the lemma mechanism unsound in exactly
   this way: a summary used in a state other than the one it was proved in.
4. **The pairing itself** (the plan's E0, item 4, yours because you are changing pairing): old and new share the
   JDK's state, and without `--before-classpath` a library's statics (`lib/src/pairing.rs:39-41`,
   `lib/src/equivalence.rs:1061-1102`); the previous version runs first; exceptions are compared by category in
   `harness::EXCEPTIONS` order, so two different `RuntimeException` subclasses agree (`pairing.rs:105-146`,
   `harness/mod.rs:39-55`). 287's and 307's claims say "the same exception". Make the comparison exact for the
   classes a claim observes (a relocated `before.X` is `X`), and either isolate the shared state the claim can
   reach or state it in the outcome so that `accept.py` can hold a claim to it. Countermodels first.
5. **Decide 287's preservation**, by a job at the frozen bound, accepted by `python3 examples/tools/accept.py 287
   preservation`. Then its mutation control if the example gains one for preservation.
6. **Transfer to 307** (`examples/307-*`, the positive change: `password.getBytes("UTF-8")` with its catch,
   against `getBytes(StandardCharsets.UTF_8)`). It needs a driver (there is none), the extracted-source slice as
   the artifacts (`preparation.slice`), nullable `password` and `salt`, seven fixed salts, bound 80 and unwind
   513 from the claim. Expected: `preservation` established, `mutant-preservation` refuted at the non-ASCII
   probes. What the second use shows to have been accidental in the first (an array layout, an exception policy,
   a purity assumption that hid a static read) goes into the rule and into `lib/README.md`. Only now consider
   whether the rule deserves a name and an interface.
7. **288's preservation as a second family**, if the time is there (VF-031: 1h32m, no verdict; the lemmas alone
   take 85 and 93 s each run). Profile before changing anything (`search.phases` in the outcome): the cost may be
   path growth in the locale table, not the matcher.

## What you own in this run

`lib/src/pairing.rs`, `lib/src/equivalence.rs`, `lib/src/shared.rs`, `lib/src/bmc/loops.rs`, `lib/src/congruence.rs`,
`lib/src/relocate.rs`; examples 287, 307 and 288's preservation task; `lib/tests/pairing.rs`. In
`lib/src/bmc/mod.rs` keep to what the relation needs. `examples/tools/accept.py` is the evidence stream's: if a
relational result needs a new check (the rule's applications recorded in the outcome, say), ask through the inbox.

## Done when

- 287 `preservation` is decided at bound 80 and accepted; or the first failure, the boundary tried and a second
  approach are each recorded with their jobs, and what a third would be.
- 307's two tasks likewise, by the same technique, with exception classes compared exactly.
- The pairing countermodels (shared state, exception class) each fail on the checker as it was and pass now, or
  the limit is stated in the outcome and enforced by `accept.py`.

## Progress

- 2026-11-17, step 1 (the first failure reproduced; *working formalization* and *accepted claim* unchanged).
  287's `proofs/prove.py` has an equivalence branch in 289's shape and 289's three properties (`evidence.json`,
  the mutant checked against the replay's JAR, a trial marked); the mutant recipe was checked by hand to rebuild
  the replay's JAR (`1d099295…`). Finding against the brief: both refusals of 2026-11-16 are gone (a nullable
  String now makes the check a property of the pair, whose allowed change javac compiles), and the first stop
  is not the cryptography: a capped probe stops in 13 s at `reads static field java.util.logging.Level.WARNING`,
  the encoder's `logger.warn` for a null, empty or non-bcrypt stored hash (spring-jcl's `JavaUtilLog.warn`:
  `isLoggable`, a `LogRecord`, `Logger.log`), where the checker models java.util.logging only below INFO. The
  claim's domain includes those stored values, so the path is lifted, not excluded. Job
  `20261117-130445-example-287-preservation-through-the-ada` records the stop at bound 80; 287's notes say so.
- 2026-11-17, the inbox taken in (a merge, no step of the brief). I001: merged smxzwqlr; `test_brief_run.py`
  passes in this workspace without the `env -u` workaround. I002: merged rkxyyqwnvlqz (a merge in place of a
  rebase, so this stream's two commits keep their ids); 287's driver is now theirs on `beside_route.Run` with the
  equivalence branch put back as the task's own arguments, and a trial probe at bound 8 stops where job
  `20261117-130445-…` expects (its paths are the module's too). I003: merged yypzyxmwluyt (the five fixtures and
  `lib/tests/pairing_countermodels.rs`); the fix is step 4, taken next.
- 2026-11-17, step 4 (the pairing; I003 done). The challenge stream's checker-side test is in
  `lib/tests/pairing_countermodels.rs` and failed on all five (each Verified). Two changes:
  - Exceptions are compared by class: `RegressionPair.thrown` takes `getClass().getName()`, with a copy's
    `before.` taken off on a JVM (the checker already names a copy by its own class). The checker now models
    `getClass()` of a Throwable the run made, since its handlers already take such an object for its class.
  - Each of the scope, the previous version and the new one starts as if it ran alone. `RegressionPair.fresh()`
    comes before each; at it the checker (`bmc/mod.rs`) and the interpreter clear the path's statics and class
    initialization, which hold the default locale too. On a JVM `fresh()` sets the default locale back.
  I chose isolation over refusing writes because it is the claims' own reading ("ends as 6.3.7 does") and needs
  no write tracking. All seven runs (five, two swapped) are now violations, each confirmed by replay. Capped
  probes at the frozen bounds: 289's and 290's preservation still verify (62 s, 1 s), and 287 still stops at
  `Level.WARNING`. Job `20261117-134306-examples-289-and-290-preservation-again` reruns both so `accept.py` can
  settle them under the exact statement; the evidence stream is told. Limit: on a JVM a library's statics stay
  shared without `--before-classpath`, so a witness that only they show is dropped there, never proved.
- 2026-11-17, step 1 continued (the warning path lifted; *working formalization* and *accepted claim* unchanged).
  The checker (`bmc/runtime.rs`) now models java.util.logging at INFO, WARNING and SEVERE as the default
  configuration has it, and spring-jcl's `JavaUtilLog.warn`: `new LogRecord(level, message)` (NPE for null), the
  record's setters, the Logger's bundle (null), and `Logger.log(record)` returning normally, under a second stated
  assumption (the default ConsoleHandler only; no filter, handler or bundle). The handler formats the record and
  calls its getters, so `log` is modelled only for a record whose class is confined to itself (a bytecode scan;
  spring's `LocationResolvingLogRecord` passes). `String.valueOf(Object)` of a String or null is modelled too; of
  another object it stays a gap, and the scan still names it. Countermodels first, in
  `lib/tests/fixtures/claims/claims/Logged.java`, each false or throwing on a JVM: a record that counts its
  formatting (falsely verified without the confinement scan, checked by disabling it), a level, a filter, a
  handler set on a logger, and `valueOf` of an object whose `toString` counts; all stop the proof. Probes on 287:
  a trial at bound 8 verifies (no stored hash that short reaches bcrypt); at the claim's bound 80 (`--timeout
  200`) the pair reaches both sides' bcrypt and ends on a spurious counterexample past the invariants of
  `crypt_raw` (pc 165) and `ekskey` (pc 260, pc 60), which a JVM run shows to be no counterexample. 191 of the
  200 s go to the solver, at 3.6 million variables. This is the relational failure the brief describes. 287's
  notes record it. No new inbox items. I001 to I003 were acknowledged above.
- 2026-11-17, step 4 again (I004 and I005; no step of 287 moved). Merged ymzlyksq (I004: the vacuity check outside
  the allowed change, which accept.py now asks of a preservation outcome) and roqtqlpm (I005: the challenge stream's
  `fresh-pair-countermodels`), each with its line. Two more side conditions in the pair (`pairing.rs`), each
  necessary: with either one undone, its countermodel is Verified again.
  - The scope `meantToChange` is called on copies of its own of the array arguments, so a scope that writes a cell
    no longer decides what both versions see (`first`).
  - An exception is compared by its class's name and those of every class above it up to `Object`
    (`same(ea, eb)`, recursive over `Class.getSuperclass()`, which the checker and the interpreter now answer
    for a class literal). So two `app.Failure`s, one extending `IllegalArgumentException` and the other
    `IllegalStateException`, are two answers (`failing`). The interfaces a class implements are not compared:
    this is stated in the note, the module and `lib/README.md`.
  A first try that built the chain as one String ran past the checker's 64-unit cap and left `failing`
  Unverifiable, not refuted. The README's checker-side test is in `lib/tests/fresh_pair_countermodels.rs` and
  passes, both as violations. Capped probes at the frozen bounds:
  - 289 verifies in 55 s, with a witness outside its change;
  - 290 verifies in about 1 s, with `servlets=[0]`.
  Job `20261117-151521-examples-289-and-290-preservation-once-m` reruns both and supersedes `20261117-134306-…`,
  whose statement is no longer the pair's. Evidence stream: accept 289's and 290's preservation from it, not from
  the earlier one. The default run passed after the merge.
- 2026-11-17, steps 2 and 3 (the boundary chosen, made sound first; *working formalization* and *accepted claim*
  unchanged). The boundary is the third candidate, joint execution from where the sides converge, taken at a loop's
  summary: the state past a summarized loop is named by the state it was summarized from, so a summary of the same
  code from the same state takes the same bits on either side (`lib/src/bmc/ties.rs`, wired into `loops.rs` and
  `mod.rs`; `shared::fingerprint` compares the code). Why, by the evidence:
  - The relational failure is free bits made at a summary, one set per side; nothing else differs. A miniature (one
    table-mixing loop past the bound, the versions differing by a prefix check) gave 287's message exactly.
  - The unchanged callee as one function would have to carry `crypt_raw`'s effects (the fields of the `BCrypt` it is
    called on) from one side's heap to the other's. A coupled invariant needs both loops run in step. The tie needs
    neither: each side runs its own code, and only the values are shared.
  The key is everything an iteration can read: the code's fingerprint and the head, the live locals, the objects
  reachable from them and from the static fields that code uses (numbered as reached, so an alias is part of it), the
  JDK's statics, and the classes' initialization. A read past such a loop at an index the path does not follow is
  named by the array's content (its cells, or the summary and each write since) and the index. One thing more: after
  `fresh()` a side is no longer past the other's loops (`path.loose`), so both read their tables alike.
  Countermodels first, in `lib/tests/pairing.rs` (`mix`, seven variants). Each countermodel differs on a JVM and is
  not proved; with its side condition taken out (a temporary switch, removed) each was Verified:
  - `callee`: the code fingerprint;
  - `cells`: a cell of the table;
  - `alias`: the numbering by object;
  - `mutable`: a static the loop reads;
  - `after`: a write past the loop on one side.
  `shorter` (an exception on one side) is not proved in either case, since each side leaves by its own code. `same`
  is now proved in 0.5 s, where it was "cannot be verified". Their differences show past round 50, so the bound's
  rounds leave the states equal but for what each changes; a first set whose differences showed earlier tested
  nothing.
  Capped probe of 287 at bound 80 (`--timeout 240`): the new release's summaries of `ekskey` (pc 60, 260) and
  `crypt_raw` (pc 165) take the previous release's bits, and the spurious counterexample is gone. The check then
  reaches the stored hashes whose cost runs the key schedule and stops at the limit: 9.7 million variables, 189 of
  240 s solving, mostly `crypt_raw`'s rounds loop, whose invariant search summarizes `key()`'s loops 32 times on
  one side and about 20 on the other, with a written set that grows by the arrays earlier calls left. 287's notes
  record it. `test_costs.py run --changed` passes. Its first try failed
  `the_encoding_estimate_does_not_count_a_large_circuit_many_times_over`, which passes alone (load, not this
  change). No new inbox items. I001 to I005 were acknowledged above.
- 2026-11-17, the inbox read after that commit (no step moved). Four items came in during the cycle:
  - I006: a soundness hole in this stream's logging model (step 1): `confined_record` admits a `LogRecord` subclass
    whose getters write a static of their own class or sneak-throw a `Throwable`. Taken next: merge `lqvlvwsm` and
    make its `lg` test pass.
  - I009: the pair still lets a caller's handler tell two exceptions apart by an interface, the message or an
    exception's own field. The brief's step 4 asks for "the same exception", so this is in scope. Taken next with
    I006: merge `pklttqzw`, then compare more or state the limit, choosing by what 287's, 289's and 290's claims
    say.
  - I007 (287's claims accept a check-only guard) and I008 (307's claim accepts the platform default charset) each
    call for a new or changed claim, which the brief leaves frozen and CLAUDE.md leaves to the user. I record them
    here and in each example's step and change no claim. They are a question for the user, not a blocker.
- 2026-11-17, I006 and I009 (soundness of steps 1 and 4; no step of 287 moved). Merged `pklttqzw`, which brings
  `lqvlvwsm`; the default run passed after it.
  - I006 (the logging model, `bmc/runtime.rs`): `confined_record` now also refuses an `athrow` and a write of any
    field but a number field (`int`, `boolean`, `byte`, `char`, `short`, `long`). After a modelled `log`, each such
    field the record's own classes declare holds any value, on every object of those classes (`Engine::formatted`),
    since a getter the handler's formatting calls may have written it on a record the caller holds. The README's `lg`
    test is in `lib/tests/rule_countermodels.rs` and passes:
    - `seen` is a violation, replayed at 1;
    - `escaped` stops at the `log` gap.
    Spring's `LocationResolvingLogRecord` writes only its `boolean resolved` and throws nothing. A trial probe of
    287 at bound 8 still verifies through the logging path.
  - I009 (the pair's exceptions, `pairing.rs`): two exceptions now agree only if their classes also implement the
    same interfaces, transitively. That is compared in the class files when the pair is written: a copy whose
    interfaces are not its twin's is named in `apart`, and `same` takes it for two answers. So `marked` is a
    violation and `based` stays one.
    What is not compared is stated instead, in the outcome's note, the module and `lib/README.md`: the message,
    the cause and the exception's own fields. So `messaged` and `coded` are proved under that note, and `wrapped`
    stops at a gap.
    Why the limit and not a wider comparison: the brief asks for "exception classes compared exactly" and expects
    307's `preservation` established. For a null password, a JVM's `NullPointerException` message names the method
    the null met, and 307's two versions call `getBytes(String)` and `getBytes(Charset)`. A message comparison would
    refute what the claim means to hold.
    The README's test is in `lib/tests/thrown_pair_countermodels.rs`. It passes, and holds `messaged` and `coded`
    to the note.
    Capped probes at the frozen bounds:
    - 289 and 290 still verify;
    - `apart` is empty for 287, 289 and 290, as the challenge stream's audit found.
    For the evidence stream: the rerun of job `20261117-151521-…` compared what this checker compares on those
    two examples. A claim that says "the same exception" is now held to the note's reading. If `accept.py` should
    check that the note is there, that check is the evidence stream's to add.
- 2026-11-17, step 5 (the cost of the search; *working formalization* and *accepted claim* unchanged). Profiled first,
  with a temporary log of each loop summary and of each solver call over half a second (removed before the commit).
  A correction to the step 2 entry: `crypt_raw`'s rounds loop (`key()` twice a round) is at pc 130, and pc 165 is the
  64 rounds of `encipher`. What the profile showed, and the three changes (`bmc/loops.rs`, `bmc/ties.rs`):
  - The new release searched again for every invariant the previous one had found from the same state. Now a
    summary from a state of a key already summarized takes over that summary's written places and invariant, by
    the key's object numbers, where the path's condition has every literal the first was proved under. The outcome
    counts them (`search.native.summaries_reused`, and `tied`).
  - On the third path (a cost of 5 or more), the new release's `key()` loops were summarized at their entry (i = 0),
    because the check had summarized them on another path. The previous release's had been summarized past the
    bound, so nothing tied. Now, in a pair, a loop is summarized at its entry only where this path summarized it
    since its version began (`Path::summarized`, cleared at `fresh()`, intersected at a merge). The test
    `two_versions_summarize_a_loop_at_its_entry_alike_on_every_fork` (`lib/tests/pairing.rs`) failed under the
    check's history, with a spurious counterexample, and passes now.
  - A loop's written set leaves out arrays nothing reachable holds (each `key()` call's `koffp` and `lr`), which
    halved the solver calls.
  The `mix` countermodels are still not proved. Capped probe of 287 at bound 80 (`--timeout 240`):
  - 621 paths and 208 summaries taken over, against 509 paths before;
  - on the three paths whose both sides ran, the new release added no variable;
  - the time goes to the previous release's runs over further stored-hash shapes, about 100 s each, and the run
    did not finish.
  289 and 290 still verify at their frozen bounds, and a 287 trial at bound 8 verifies. Job
  `20261117-180758-example-287-preservation-at-the-frozen-b` decides it at bound 80 (fresh `--work`, up to 3.5
  hours). The jobs `20261117-130445-…` (287's first failure) and `20261117-151521-…` (289 and 290) passed on the
  default line. No new inbox items; I001 to I009 were acknowledged above.
- Next: when the job is back, accept 287 `preservation` with `accept.py` if it verifies. Otherwise record where it
  stopped as step 5's second approach. Step 6 (307) can start meanwhile: it needs only the technique.
- Status: working

## Loop settings

- session: f28025bc-e46b-4a87-a943-bfb79dea5465
- model: claude-opus-5-5
- effort: high
- workspace: domain-advances-preservation

## Loop until

Steps 1 to 6 first, then 7 while a cycle can still realize a substantial part of it. Stop with `waiting on jobs ID
...` when what is left waits on jobs, `done` when the criteria are met or recorded as the brief allows, `blocked:
...` when the next step is the user's. Keep the last line of Progress a status.

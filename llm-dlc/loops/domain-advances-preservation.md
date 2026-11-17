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
- 2026-11-17, the inbox read after that commit (no step moved). Two items came in during the cycle:
  - I010: the code fingerprint (`shared.rs` `reach`) skips JDK virtual and interface calls, which may dispatch
    into application code, so a tie can join two runs whose code differs. That is a hole in step 2's tie (and so
    in the summaries taken over). Taken next: merge `qnlomnmx`'s fixtures, then close the reach or add the
    overriding methods, with the README's test in `lib/tests/tie_countermodels.rs`. Job
    `20261117-180758-…` was queued before this item. Its verdict is accepted only if the fix leaves 287's
    fingerprints as they were (bcrypt's loops call no JDK interface on an application object, to be checked);
    otherwise 287 is rerun.
  - I011: merge the default line (with the evidence stream's line, at `qrxtwtlo`), then rerun 289's and 290's
    preservation on one checker with both streams' fixes, and record what it gives. Taken with I010, so the
    rerun has the tie fix too.
- 2026-11-17, I010 and I011 (the merge and the tie's soundness; step 5's job read). Merged the default line (`zmxknqty`,
  the evidence stream's line in it) and `qnlomnmx` (the challenge stream's tie countermodels). The notes of 287, 289
  and 290 kept both sides'. `costs.json` was re-estimated and the trace pages regenerated. The merge had dropped 289's
  job `20261117-122454-…` results and `.work-289/recorded`, because the challenge line never had them; they were
  restored from the default line.
  - I010 (`shared.rs`): the reach that both the identical-bytecode shortcut and the ties' code fingerprint rest on
    is now open wherever a call into the JDK may come back into the application. That covers:
    - a JDK interface or an overridable JDK method;
    - an argument whose methods the JDK may call, such as `String.valueOf(Object)`, a `Comparator` or a string
      concatenation of an object;
    - a charset looked up by name;
    - a JDK constructor called on an application object (`super(...)`), except `Object`, `Record` and `Enum`.

    The reach also takes in the initializers of the application classes the code uses. The README's test is in
    `lib/tests/tie_countermodels.rs` and passes; it failed on all three, as the item said. The initializer gap was
    mine to find: `a_class_initializer_the_code_runs_is_part_of_the_code_compared` (`lib/tests/pairing.rs`) failed
    with that part taken out ("nothing to prove"). A loop whose iteration initializes a class was already refused
    by the loop summary, so it reached only the shortcut. The `mix` countermodels are still not proved.

    287's fingerprints: bcrypt's loop methods call only an `int[]`'s `clone` and
    `new IllegalArgumentException(String)`, and `BCrypt.<clinit>` calls nothing. A capped probe at bound 80 still
    takes over 208 summaries.
  - Job `20261117-180758-…` (step 5) failed undecided: after 424 s and 1187 paths, no invariant was found for the
    previous release's `BCrypt.key` loop at pc 39, because "an iteration changes local 1, which holds a reference".
    That local is `key`'s array argument, which the loop never assigns. Capped probes reach about 540 paths and do
    not get there, and two miniatures of the shape I suspected (a choice of arrays split in a callee and merged
    again) are proved. So the refusal now names what the reference held at the head and back at it.
    - Job `20261117-185613-example-287-preservation-at-the-frozen-b` reruns 287 at bound 80 on the fixed checker,
      which I010 called for anyway. Nothing was accepted from the job that failed.
    - The third approach, if it stops there again, is in 287's notes: compare a reference by what it denotes under
      the path's condition.
  - I011: job `20261117-185623-examples-289-and-290-preservation-on-one` reruns both on one checker with both
    streams' fixes and I010's. Capped probes on it verify both (289 in 1373 paths, 290 in 573). 290's restated
    claim stays the user's question (D023).

  The default run after the merge failed four tests, now fixed:
  - the tier inventory (estimated and tagged);
  - 289's acceptance (the dropped results);
  - two shortcut tests over a record, whose `Record.<init>` the first rule took for a call back.
- 2026-11-17, the inbox read before that commit (two items came in during the cycle).
  - I012, an outside review: weighed against the brief, with nothing in it contradicting the brief.
    - Its first point, closing I010 in `reach` and guarding both the fingerprint and `plan.identical`, is what this
      entry did. That includes unknown bootstraps and initializers followed as code.
    - It asked for more controls: a JDK static that calls back is added
      (`a_jdk_method_given_an_application_object_leaves_the_code_compared_open`, which was "nothing to prove"
      without the argument rule); the initializer one is above; an exceptional exit is the `mix` set's `shorter`.
    - Its order (I010, I011's reruns, then 307, then a bounded decision on 287 rather than further 240-second
      tuning) is the order taken here. Its suggestion for 287's cost is to move the relation outward to
      `crypt_raw` as a checked unchanged callee, which is the brief's first candidate of step 2. It is recorded as
      the alternative to the third approach in 287's notes and is weighed when job `20261117-185613-…` returns.
    - I007 and I008 stay the user's questions.
  - I013: job `20261117-180758-…` decided nothing, and nothing was taken from it (above).
- 2026-11-17, step 6 (307; *working formalization* and *accepted claim* unchanged; the frozen claim's hash kept).
  - **The driver.** 307's `proofs/prove.py` runs `preservation` and `mutant-preservation` on the route's own slices
    (`runtime.prepare`), at the claim's bound, with the claim's assumption and nullable `password` and `salt`. Each
    slice JAR must be the one its replay ran (before `ea4dfaa1…`, after `f6aec1ce…`, mutant `54a1f226…`). It keeps
    `beside_route`'s three properties. It is beside the route only for the time: the route gives the verifier ten
    minutes. Finding against the brief: `beside_route.Run` needs an adapter and pinned JARs, and 307 has neither, so
    the driver subclasses it for the slices.
  - **First stop:** `String.getBytes(String)` on before's side. It is now modelled for the names the JDK takes for
    UTF-8. `getBytes(US_ASCII)`, the mutant's, is modelled too. Both are sampled on the JVM, the interpreter and the
    checker (String model 7).
  - **Second stop.** At unwind 513 every loop of bcrypt is followed to its end, so nothing is summarized and the loop
    ties never apply. A capped probe filled 4 GB in 39 s.
  - **What the second use showed was accidental in the first:** 287's claim leaves its loops past the bound. So
    the boundary moved to the brief's first candidate, the unchanged callee as one function of both sides
    (`bmc/ties.rs`, `shared::one_function`):
    - a call of a static method both versions share is not run;
    - its outcome is new bits, related by congruence to every earlier call of the same code on the path;
    - its inputs (arguments and the statics of the classes it uses) are compared by length and cells;
    - its outcomes are the result, whether it throws and which class, and the cells of every array it reaches.

    Side conditions:
    - the same code in both versions;
    - parameters, statics and result only of numbers, Strings and arrays of numbers;
    - those classes initialized;
    - a loop in the code;
    - no static field written outside an initializer, and none of the JDK's read;
    - no lambda, and no exception of the application's own class;
    - JDK calls only from a list that reads no state a run can change.

    The outcome states that each such call is taken to end.
  - **Countermodels first:** `ONCES` in `lib/tests/pairing.rs`, eight of them:
    - a changed helper;
    - an unequal cell;
    - an alias on one side;
    - a mutable static;
    - an exception one caller catches;
    - a written cell read before the call on one side;
    - the clock;
    - an initializer the call would run.

    Each differs on a JVM (`each_onces_countermodel_differs_on_a_jvm`). Each is not proved, and each was proved with
    its side condition taken out (a temporary switch, removed). `alias` and `init` first had to be reshaped, because
    another condition covered them. `mix` and the fork test now pass their helper an unused `Object`, so their loops
    still run and still test the ties.
  - **The reach (I017, a finding of its own).** Every method calling `Integer.parseInt` had no fingerprint: the reach
    follows `Integer`'s code, and on JDK 25 `parseInt` builds its message with `String.format(Object[])`. A followed
    JDK class's own calls into the JDK now leave the reach closed. The application's call into one is checked as any
    JDK call is, which it was not before. The countermodel is
    `a_followed_jdk_method_given_an_application_object_leaves_the_code_compared_open`, `parseInt(CharSequence, ...)`
    given the application's: it was "nothing to prove" without the entry check.
  - **Probes at the claim's bound on JDK 25:**
    - `preservation` verified in about 100 s (72 calls taken, 66 related);
    - `mutant-preservation` refuted at `"\uffc0\ub000"` under a valid salt, reproduced on a JVM with the real cipher;
    - 289 and 290 still verify at their former path counts.

    Jobs `20261117-210114-example-307-preservation-at-the-frozen-b` and
    `20261117-210114-example-307-mutant-preservation-after-ag` decide both.
  - **Limits, stated in `lib/README.md`:**
    - The rule takes no instance method, so not 287's `crypt_raw`.
    - A counterexample through calls whose inputs differ may rest on values no run gives. One that does not reproduce
      leaves the check undecided where the call as written would refute it (`cells`, `alias`, `thrown`).
    - The mutant's refutation therefore depends on the solver's first candidate, which I018 says can be one that does
      not replay. A check the rule leaves otherwise undecided runs again as written.
  - **Name and interface.** The rule has a name in the outcome (`calls_as_one_function`, `calls_related`), in the
    proof's words, and in `bmc::Options`. It has no flag: in a pair it is the checker's own, and a proof through it is
    a proof. Whether it deserves one waits for 287.
  - **For the evidence stream (`accept.py`, three things 307 will meet):**
    - The outcome's target names `hashpw`'s parameter types (the method is overloaded), and the entry check compares a
      bare `Class#method`.
    - The slices are built from source, recorded as constructed, so only the mutant's is checked against a receipt.
      A slice route would check each against its replay's.
    - A pair's harness is at `work/pair-work/harness/PropertyHarness.java`, where the refutation's replay check looks
      for `work/harness/`.
- 2026-11-17, the inbox read during that cycle (I014 to I019 came in).
  - I017: done above.
  - I016: the user's D028 and D029 are recorded in 307's note: the I008 limit stands with the result, and the result
    holds on the pinned JDK 21 and 25 builds, where the two forms encode alike. The packet's points (1) to (3) are
    what this entry found.
  - I014, I015, I018 and I019 are taken next. They need the default line merged: the specialist's packets, the
    `callee-countermodels` and `reach-countermodels` fixtures, and the two job results.
- 2026-11-17, the merge, I014 and I019 (no step of 287 or 307 moved; *working formalization* and *accepted claim*
  unchanged).
  - **The merge.** The default line (to `okuplpys`: the 307 specialist's two packets, `callee-countermodels`, and the
    results of jobs `20261117-185613-…` and `20261117-185623-…`) and the challenge stream's `tqmpowvx`
    (`reach-countermodels`). Only generated files conflicted. The default run passed on the merged tree.
  - **I014 (290's relative `-Xlog` path).** The state stream had already fixed it (`zlvqxmst`). I took its line in
    `observed.rs` and its test in `claims.rs` byte for byte, so the two lines merge cleanly. A capped probe of 290 with
    the job's relative `--work` verifies (573 paths), and the observer's logs are in the work folder. Job
    `20261117-213024-examples-289-and-290-preservation-again` reruns 290's step, and 289's beside it on this checker.
  - **I019 (the reach, `shared.rs`).** Five changes, each needed:
    - a field is compared by the class that declares it (JVMS §5.4.3.2), which closes `hidden`;
    - a static's initializer is the declaring class's, which closes `constant` and `looped`;
    - a class's use initializes each superinterface with a default method, which closes `defaulted`;
    - the root's own class's initializer is part of the code, which closes `own`;
    - the shortcut walks both versions' reaches, which closes `removed`.

    The README's checker-side test is in `lib/tests/reach_countermodels.rs` and passes. With each change undone in
    turn (a temporary edit, removed), exactly its own rows are proved again. The first five are no longer taken as
    identical. `looped` is no verdict as on the challenge line: the spurious `agree(k=3)` does not replay, and nothing
    ties, because the two `Limits` initializers differ in the fingerprint.

    A capped probe of 307's `preservation` at the frozen bound still verifies, with the same 72 calls taken and 66
    related, since BCrypt implements nothing and declares every field it uses. `lib/README.md` says what the reach
    takes in.
  - **Inbox.** I014 and I019 are done above. I015 (job `20261117-185613-…`: 287 unverifiable again at `BCrypt.key` pc
    39, with the same counts) and I018 (`callee-countermodels`, and `crypt_raw` as the boundary) are the next piece:
    287's third approach. I016 and I017 were done in step 6. No item came in after I019.
  - **Warnings.** The commit check warns on bcrypt test hashes (`long-token`, `If6…`) in this session's log and two
    others. They are 307's public test vectors and are already proposed for the allow list (`d6616e20`), awaiting
    the user.
- 2026-11-17, step 5's third approach (I015, I018 and I020; *working formalization* and *accepted claim* unchanged).
  - **I018, the fixture.** `callee-countermodels` against this line's rule on JDK 25 (`check.py --rule-landed`):
    `same`, `copied` and `parsed` verified, no countermodel proved, exit 0, before and after this entry's change.
    `table` and `aliased` end with no verdict (a witness the interpreter cannot run, `getBytes(Charset)`), not refuted.
  - **The rule at `crypt_raw`** (`bmc/ties.rs`, `shared::one_function`), as I012 and the 307 specialist suggested:
    - an instance method is taken where nothing can read its receiver after the call (no live local of any frame,
      a handler counted as a way on; no other place on a stack, no static, no other object), its fields among the
      inputs; `hashpw` makes a `BCrypt`, calls `crypt_raw` on it and drops it;
    - an array result is taken where the code returns an array it made, of a length it computes from constants and
      static tables' lengths, constant at the call (`new byte[cdata.length * 4]`: 24);
    - what a call may write is what it reaches through an argument, the receiver, or a static its code takes other
      than to copy at once, so bcrypt's tables, which it only clones, stay inputs.
    Countermodels first, `KEYED` in `lib/tests/pairing.rs`: `kept`, `held`, `caught` (the receiver read after the call
    by a live local, a static, a handler), `field`, `returned`, `table`. Each differs on a JVM and is not proved. With
    each side condition switched off in turn (a temporary switch, removed), exactly its own rows were proved.
    `returned` first tested nothing: its new side fell to the default body, so the two differed in any model.
    An array of any cells past a loop's summary is now an input by the name of its content, so the fork test's
    `inner` was taken as one function and its loops no longer ran. It takes an unused `Object` now, as `rounds` does.
  - **What the probes found on the way, both in the rule.**
    - Two calls whose inputs were the same formulas were related only under a literal asking whether a symbolic
      length is within the cells, so each outcome split cost a solver call. Now there is no such literal where both
      arrays have one length and as many cells.
    - `decode_base64`'s result, whose length a loop counts, made each read of it a fork. An array result of a
      length that is no constant at the call now runs as written.
    - When the first run used the whole budget, the outcome was the empty fallback's. With under a second left it is
      now the first run's.
  - **Probes at the frozen bounds.** 287 `preservation` verified in 112 s (53 paths, 52 calls taken, 48 related, no
    loop summarized). 307 `preservation` verified (61 s) and `mutant-preservation` refuted (41 s). 289 and 290 verify
    at their former path counts. Job `20261117-230459-example-287-preservation-at-the-frozen-b` decides 287.
  - **Inbox.** I015 and I018 are done above. I020 (D032, VF-039): 287's notes now say its claims do not tell a
    check-only guard from the fix, and no claim is prepared. No item came in after I020.
- 2026-11-17, I021 and I022 (soundness of steps 1 and 2; no step of 287 or 307 moved). Merged the challenge stream's
  `zmpzxkqn` (with `mnwtrnrp`: the `log-`, `stand-in-` and `supertype-countermodels`); only generated files conflicted.
  - **I021 (the logging model, `bmc/runtime.rs`).** `confined_record` now refuses an `Error` the code itself decides,
    which the handler's `catch (Exception)` lets out of `log`:
    - an array of a length other than a constant up to 1024, pushed just before and reached by no jump, and any
      `multianewarray`;
    - a call among the record's own classes that can come back to itself, taking every method of the name and
      descriptor as the callee, so an override counts.
    The JVM's own limits (a heap or a stack already all but full) are left unmodelled, as everywhere else in the
    checker; the module and `lib/README.md` say so. Each rule is the only one that refuses its fixture: `huge` makes an
    array and does not recurse, and `deep` recurses and makes no array. Both now stop at `Logger.log`, a gap. The
    README's test is in `lib/tests/log_countermodels.rs` and passes. Spring's `LocationResolvingLogRecord` neither
    allocates nor recurses, and 287's probe below still goes through the warning path.
  - **I022 (the reach, `shared.rs`).** The reach now collects every application class the code names, with its
    supertypes (`Reach::named`). That covers a method's owner as named and as resolved, a field's owner, a class
    made, and the class an `instanceof`, `checkcast`, `anewarray`, `multianewarray`, `ldc` or catch type names. Each is
    compared by its header (superclass, interfaces in order, whether it is an interface, or absent) in both versions
    in `same_everywhere`, and each header is part of the ties' fingerprint. The README's test is in
    `lib/tests/supertype_countermodels.rs` and passes:
    - `rebased`, `marked`, `cast` and `mixed` are no longer "identical; nothing to prove", and go to the solver (here
      a missing JBMC);
    - `looped` is no verdict, since nothing ties and its spurious `agree(k=3)` does not replay.
  - **Probes at the frozen bounds, all as before:**
    - 287 `preservation`: verified in 111 s (53 paths, 52 calls taken, 48 related);
    - 307 `preservation`: verified (72 taken, 66 related);
    - 307 `mutant-preservation`: refuted;
    - 289: verified (1373 paths);
    - 290: verified (573 paths).
    So job `20261117-230459-…` (287), queued before these fixes, is still to be accepted when it returns.
  - **Job results, read on the default line:**
    - `20261117-210114-…`: 307's `preservation` holds (2m22s) and `mutant-preservation` fails, as expected;
    - `20261117-213024-…`: 289 and 290 hold.
    They are not merged into this line yet.
  - `test_costs.py run --changed` passes, and the tier inventory is estimated, tagged and linted.
  - **Inbox.** I021 and I022 are done above. Nothing came in after I022.
- 2026-11-17, steps 5 and 6 decided (*working formalization* and *accepted claim* unchanged). Merged the default line
  (to `vpxltztt`: the results of jobs `20261117-210114-…`, `20261117-213024-…` and `20261117-230459-…`, and D023 and
  VF-039); only generated files conflicted.
  - **287 `preservation`: established and accepted.** Job `20261117-230459-…` verified the frozen claim at bound 80 in
    1m50s at 2.2 GiB (53 paths, `crypt_raw` taken as one function, no loop summarized). `accept.py 287 preservation`
    accepts it (13 checks), and the task's `besideRoute` names the job. The job ran the checker before I021 and I022;
    the capped probes on the fixed checker gave the same verdict and counts. VF-039's limit goes with it, in the notes
    and on the page.
  - **307's two tasks: decided, not yet accepted.** Job `20261117-210114-…` verified `preservation` (2m22s) and
    refuted `mutant-preservation` (1m17s, its witness replayed), exceptions compared by class, superclasses and
    interfaces. Each task's `besideRoute` names its job. `accept.py 307` refuses both on its `entry` check alone. The
    outcome's target is `BCrypt#hashpw(java.lang.String, java.lang.String)`, since the method is overloaded. The check
    compares it with the task's target cut at `(`, which is `BCrypt#hashpw`. Every other check passes.
  - **For the evidence stream (`accept.py` is theirs):** please let `entry` accept an outcome target with parameter
    types when they are the task descriptor's (`(Ljava/lang/String;Ljava/lang/String;)…` here). Then
    `accept.py 307 preservation mutant-preservation` should accept both as recorded. The other two points of step 6
    still stand: the slices are recorded as constructed, and the harness is at `work/pair-work/harness/`.
  - **Done when.** 287 is decided at bound 80 and accepted. 307's two tasks are decided by the same technique, with
    exception classes compared exactly, and wait only on that check. The pairing countermodels pass, with their
    limits stated.
  - **Inbox.** No item came in after I022.
- Next:
  1. Step 7: 288's preservation, profiled first (VF-031).
  2. When `accept.py` takes a typed target, rerun `accept.py 307` and record the result.
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

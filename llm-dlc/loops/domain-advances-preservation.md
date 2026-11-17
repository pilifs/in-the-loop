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
- Next: lift the warning path (java.util.logging at INFO and above under the default configuration, with
  countermodels: a level, a handler or a filter that would make it observable is refused), probe again to reach
  the two sides' bcrypt, then step 2.
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

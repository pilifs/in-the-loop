# Brief: domain advances, the challenge stream

A stream of [domain-advances.md](domain-advances.md), which is the instruction: read it in full first, its
Direction and "How to work through it" above all. You are the independent challenger: your work is to show that
something the run believes is false, and you succeed when you do.

## The outcome

**Intent.** No result of this run rests on a mechanism nobody tried to break, and no accepted claim says less than
the intent it is offered for without saying so.

**How the foundation found three false proofs in a day**, which is the method: take a mechanism that lets one
thing stand in for another (a hypothesis for a recursive call, a summary for a call, one side of a pair for the
other, an observed state for an initializer), ask what the stand-in *does not say* (effects, exceptions, the state
it was proved in), write the smallest Java whose behaviour depends on exactly that, state a property that is false
on a JVM, and run it. `lib/tests/fixtures/claims/claims/Effects.java` and the three tests after
`a_lemma_is_proved_first...` in `lib/tests/claims.rs` are the worked example; `Effects.main` prints what a JVM says,
and a test holds the fixture to it.

## Your work

Not in a fixed order: start with 1 and 2, which are stated but open, then follow what the other streams commit.

1. **Pairing** (`lib/src/pairing.rs`, `lib/src/equivalence.rs`; the preservation stream will change both, so
   write these first and send them). The generated pair calls the previous version first, then the new one, in one
   run:
   - *Shared JDK state.* Old calls `Locale.setDefault(tr)` and lower-cases; new only lower-cases. In the pair they
     agree; run separately they differ. The module says so (`pairing.rs:39-41`) and nothing guards it. Is the
     order observable: does swapping the two calls change a verdict?
   - *Shared library statics* without `--before-classpath` (`equivalence.rs:1102`): a static the old version
     writes is the one the new version reads.
   - *Exceptions by category* (`pairing.rs:105-146`, `harness/mod.rs:39-55`): two different `RuntimeException`
     subclasses, or `IllegalArgumentException` against a subclass of it, "agree". 287's and 307's claims say the
     same exception.
   - *The allowed change*: `meantToChange` is new-version code run before both calls. Can it change what they see?
   For each: the pair, what a JVM says of each side alone, the property the checker wrongly establishes.
2. **Observed initializers** (`lib/src/observed.rs`; with the evidence stream). The outside review's countermodel:
   `A.<clinit> { B.x = 1; k = 7; }`: after reading `A.k` the checker sees `B.x == 0` where Java sees 1. Reproduce
   it. Then: an initializer whose result depends on the default locale, on a system property, on class path
   order; an observation taken on one class file and used on another.
3. **What the foundation's own fixes leave.** They refuse; they do not prove the refusals complete. Try: a lemma
   whose method reads a *final* static that an initializer cycle leaves unset at the call; a final field holding a
   mutable object reached by a method the engine models rather than runs (a `StringBuilder`, a collection model, a
   `Pattern`); a read through reflection or a lambda's captured value; a static of a *model* class; the summary
   used inside the lemma's own proof; an induction whose measure reads state. `Engine::reads` and `Engine::keeps`
   in `lib/src/bmc/mod.rs` are the two gates; the question for each read or write instruction and each modelled
   JDK call is whether it passes one of them.
4. **Loop invariants** (`lib/src/bmc/loops.rs`): the invariant search is what makes bcrypt's loops finite. It
   "forgets" what a loop writes and keeps candidates that survive an iteration. Is anything kept that an iteration
   can break after the first check (a relation between two cells, a value a callee writes, an array reached
   through two names)? A false invariant is a false proof of everything after the loop.
5. **Each new rule of the other streams**, as it lands: the preservation stream's relation between the two sides'
   unchanged callees (a changed round inside the closure; unequal initial arrays; an alias on one side; a
   dependence on a mutable static; an exceptional exit on one side), the state stream's effect contract (a write
   through an alias the frame does not name; a setter that writes through a callee; an exception after a partial
   write; a contract used in a state its reads differ in). Read their commits, not their summaries: every
   stream's line is visible from your workspace (`jj log -r '::domain-advances-preservation@- & ~::@-'`, then
   `jj diff -r CHANGE` or `jj file show -r CHANGE PATH`), and you need not wait for a merge.
6. **The formalizations.** For each claim the run decides, ask whether a wrong implementation would satisfy it.
   The existing example: 290's preservation compares only the count of matchers by type, so a release that built
   a different matcher passes (VF-033). 286's decision lemma is satisfied by a binder that denies every field,
   which is why its preservation claim exists, and that one is still open. For 287, 307 and 286's protected
   state: write the wrong implementation as a mutant (a patch under `controls/`), predict the claim's answer on
   it, and report a claim that cannot tell it from the fix. A new claim file is the owner's and the user's; yours
   is the mutant and the argument.
7. **The acceptance check.** `examples/tools/accept.py` is also a mechanism that lets one thing stand in for
   another. Build evidence it accepts for an answer that is false: an outcome from another claim with the same
   expressions; a job whose step ran a different driver at the same path; a witness inside the bound but outside
   the assumption; a pair's vacuity witness inside the allowed change. Each becomes a control in
   `test_accept.py`, sent to the evidence stream.

## How you report

- A reproduced false result is a **test that fails**, with what a JVM says. If the mechanism is one no stream is
  changing this cycle, commit the test with a conservative refusal that makes it pass (refuse the case by name;
  never loosen a check to get there), and say in the message which results could have rested on the hole. If a
  stream is changing it, send the test as text through its inbox (`python3 llm-dlc/tools/inbox.py send
  domain-advances-STREAM --kind failure ...`) and record it here, so that two streams do not edit one function.
- A hole you could not reproduce is recorded as tried, with the code that guards it.
- A weak formalization is an inbox item to the owner and an entry in the example's notes.
- Every finding gets an audit line: which accepted results, if any, used the mechanism, and whether they are
  affected. An accepted result that rests on a hole is reported to the watcher at once.

## What you own in this run

`lib/tests/fixtures/claims/claims/Effects.java` and the countermodel tests in `lib/tests/claims.rs`; new
countermodel fixtures and tests anywhere; mutants under an example's `controls/` that no task uses yet. You change
`lib/src/` only to refuse.

## Done when

- Items 1 and 2 are each reproduced and handed over, or recorded as guarded with where.
- Every rule the other streams added in this run has countermodel tests from you, or a line saying why none could
  be built.
- Each decided claim of the run has a "could a wrong implementation satisfy it" entry in its example's notes.

## Progress

- 2026-11-17, item 1, pairing (`yypzyxmwluyt`): **all four holes reproduced** as false proofs on the checker as it
  was (`lupovnmv`), with five countermodels in `lib/tests/fixtures/pairing-countermodels` (its README has the table,
  the reproduction and the checker-side test). Each pair differs when each version runs alone on a JVM
  (`each_version_alone_is_what_a_jvm_says_it_is`) and is **Verified** as agreeing: `locale` (the previous version sets
  a Turkish default the new one lowers under), `flag` (a library static shared without `--before-classpath`),
  `thrown` (two unrelated `RuntimeException`s), `argument` (`IllegalArgumentException` against a subclass), `scoped`
  (a scope that is false everywhere but sets the default locale, run before both calls). The order is observable:
  with the roles swapped `flag` is a violation, and so is `flag` with `--before-classpath` in either order (test
  `in_the_other_order_or_on_its_own_library_the_pair_sees_the_static_differ`); `locale` swapped is unverifiable
  only because the interpreter lowers without the locale (`interp/natives.rs`, a conservative miss, not a false
  proof). The pairing is the preservation stream's this run, so no refusal is committed here: the failing checker
  test is sent to `domain-advances-preservation` as a `failure` item, to land with its fix.
  *Audit*: the accepted results that used the pair are 289's and 290's `preservation`. Both pass
  `--before-classpath`, their allowed changes call no release code, their adapters set no default locale: not
  affected by `locale`, `flag` or `scoped`. Both claims say "throw the same exception", which the pair checks by
  category: **to the watcher**, each says less than its claim on any input where the releases throw different
  classes of one category; whether one exists is not shown, so they stand open on that point until a rerun under
  exact classes (notes added to both examples). 288's adapter sets the default before each read, and 286, 287
  and 307 have no decided preservation.
- Test note: `test_costs.py run --changed` chose `llm-dlc/tools/test_brief_run.py`, which fails inside a stream
  because it inherits `RUN_STREAMS_WATCHER` and puts its made-up streams to the real watcher (the watcher answered
  `leave`, citing its D001); it passes with the variable unset (39 tests).
- 2026-11-17, item 2, observed initializers: **reproduced, three handed over and two refused**.
  - The fixtures are in `lib/tests/fixtures/observed-countermodels`; its README has the table, the audit and the checker-side test.
  - `lib/tests/observed_countermodels.rs` holds each fixture to a JVM.
  - These were proved on the checker as it was (`yypzyxmw`), where a JVM says otherwise:
    - `crossed`, the outside review's `A.<clinit> { B.x = 1; k = 7; }`: `result == 0` is proved where a JVM gives 1. Only `A`'s own fields are taken.
    - `lowered`, `"I".toLowerCase()` observed in a Turkish JVM: `result == 305` is proved, and the result no longer states the locale assumption it states without the observation. The observer's JVM takes its locale from the environment.
    - `configured`, `System.getProperty` observed with the property set: proved.
    - `released`, a multi-release JAR. Without any observation, `result == 1` is proved where a JVM 17+ gives 20. With the class observed, the versioned file's state is put on the base file's code: the observation is taken on one class file and used on another.
    - `shadowed`, a class path copy of the JDK's `org.xml.sax.helpers.AttributesImpl`: `result == 42` is proved where a JVM gives 0.
  - The observation's stated assumption covers none of the first three. The last two are holes in the class path reader rather than in the observation.
  - Class path order was otherwise tried and found guarded: the observer gets the check's class path in the check's order (`observed.rs`), and both it and `ClassPath::load` take the first entry. The JDK's packages were the exception, and are now refused.
  - **Handed over**: `crossed`, `lowered` and `configured` go to `domain-advances-evidence`, whose brief's item 5 binds an observation. The test is in the fixtures' README, and it is sent as a `failure` item citing this commit, once the commit is in (the inbox needs a commit). Its id goes in the next entry.
  - **Refused here**: `released` and `shadowed`, by `ClassPath::refused` in `lib/src/classpath.rs`. No stream owns the class path reader.
    - A class is refused by name, on load or when copied for a pair, if a multi-release JAR holds a versioned file of it, or if an entry holds it in a package of the JDK's image.
    - Exempt from the second case: a class file identical to the image's own, and the tool's own models. The tool puts both on a class path itself (a contract's proof against the JDK's bytecode, and JBMC's class path); 13 tests caught the first, broader version.
    - Enumerating every class still reads the first entry's file.
    - Not covered: an override that only a versioned file declares, and resources.
  - *Audit*:
    - 290's `fixed-security` and `preservation` rest on five observed classes. Read from the hash-checked JARs, no `<clinit>` of the five writes another class's static. The two servlet classes read the default locale, but into a field the observation does not hold, so a read of it is refused. Not affected.
    - Of the examples' JARs, only 288's spring-core 6.1.13/14 are multi-release, with one versioned class (`VirtualThreadDelegate`). 288's adapter reaches none of the 7 classes that name it.
    - No example's JAR holds a class of a JDK package.
    - No accepted result rests on these holes, so there is nothing for the watcher.
- Inbox:
  - `domain-advances-challenge-I001`: `test_brief_run.py` inherits the watcher. Noted, and neither changed nor blocked on: this cycle's runs unset `RUN_STREAMS_WATCHER`.
  - Last cycle's pairing failure item went to preservation as `domain-advances-preservation-I003`.
- Tests: `test_costs.py run --changed`, which is the whole Rust default tier since `lib/src` changed, passed on the final code. Its only failure was the JBMC timing test `jbmc::tests::a_run_that_dies_gives_no_verdict_whatever_it_printed`, which is flaky: it failed once and passed on retry, and it is unrelated. An earlier run had the same with `..._never_meets_the_second_attempt`.
- Next: item 3, what the foundation's fixes leave (`Engine::reads` and `Engine::keeps`), starting with the final static that an initializer cycle leaves unset at a lemma's call.
- Status: working

## Loop settings

- session: f8bc7b54-f877-4ee9-8e3a-b5ffbba621bc
- model: claude-opus-5-5
- effort: high
- workspace: domain-advances-challenge

## Loop until

Items 1 to 4 first, then 6 and 7, which need nobody; 5 for as long as another stream is still working, since their
commits are your input. When you have nothing left to attack while they still work, stop with `blocked: waiting for
the other streams' next commits`, not `done`: the watcher can run a blocked stream again, twice at most, so spend
those on real waits. `done` when the other three streams are finished and their last rules are challenged, or
when the reruns are spent, with what was left unchallenged listed. Keep the last line of Progress a status.

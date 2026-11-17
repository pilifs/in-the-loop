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
- The item 2 failure went to evidence as `domain-advances-evidence-I004`, citing `mqkqvvmw`.
- **To the watcher**: `sync.py check` on this line reports `ERROR change yypzyxmwluyt: session f28025bc-… has no manifest`.
  - How it happened: the preservation stream merged `yypzyxmw` (my item 1) into its line (`kwyxmlns`). Its `sync.py` then stamped its own session's `LLM-Trace` lines on that commit (operation `3cfb3c0eb24b`, from `domain-advances-preservation@`).
  - The cause: `link_commits` in `llm-dlc/tools/sync.py` counts as a session's every mutable ancestor of its `@` authored while the session ran, and a commit merged in from another stream qualifies.
  - The manifest for `f28025bc` exists only on the preservation line, so the error should clear once the lines meet.
  - I have not touched the trace lines or `sync.py`.
  - Any stream that merges another's commits while that stream is still mutable can do the same.
- 2026-11-17, item 3, what the foundation's fixes leave: **seven false proofs reproduced, all refused or now refuted**.
  - The fixtures are in `lib/tests/fixtures/lemma-countermodels`; its README has the table, what was tried and the audit.
  - `lib/tests/lemma_countermodels.rs` holds each to a JVM and the checker to its verdict.
  - Each was **Verified** at `llwznzwm`, where a JVM says otherwise:
    - *An initializer cycle*: `Base.SEEN = Derived.limit()` before `Base.LIMIT` is written, with the lemma `Derived#limit == 7`. A JVM gives 0. The foundation's guard looked only at the method's own class, which is initialized. The same happens with no inheritance (`Holder`/`Reader`), the class initialized by the lemma's assumption.
    - *A final static whose initializer reads what a caller changes first*: `Own.LIMIT = Settings.value` (5 against the proved 0), `Lowered.I = "I".toLowerCase()` under a default the caller set to Turkish (305 against 105), and `Copied.FIRST = Table.T[0]` (5 against 0). The proof ran the initializer in the harness's state.
    - *A StringBuilder a final static holds*: `LOG.length()` directly and through `LOG::length` (1 against 0). The model's reads never asked `Engine::reads`.
  - **Refused here**: summaries are no stream's this run.
    - No summary stands in for a call while any class is being initialized; the call runs as written. `seen` and `heldSeen` are now violations, as on a JVM, and the lemma is still used once initialization is over (`derivedLimit`).
    - A class initializer that a lemma's proof runs is held to what the lemma is held to (`Engine::in_lemma`). Objects that exist when an initializer starts or returns count as there before the call. Its own class's statics, and those of a class being initialized, are exempt.
    - A lemma reads no StringBuilder that was there before the call.
    - claims.rs (18 tests, the foundation's worked example included) passes unchanged.
  - **Tried and guarded**, with the guard named in the README:
    - a lambda's captured array;
    - the ArrayList model;
    - reflection (a gap);
    - a lemma about a method that calls itself;
    - two lemmas about methods that call each other (a lemma's proof gets no lemma);
    - Pattern and Matcher;
    - a model class's statics (none are mutable);
    - an induction whose measure reads state (`keeps`).
  - *Audit*: the only lemma in use is `PatternMatchUtils.simpleMatch` (286, 288). In the pinned JARs its class has no statics and no initializer, it calls only String methods, and nothing calls it from an initializer. 286's decided result is not affected, and 288 has no proof verdict.
- Inbox: no open items.
- 2026-11-17, item 4, loop invariants: **tried and found guarded**, no false proof. Reading the engine's array models for it turned up **three more false proofs of item 3's kind**, now refused.
  - The loop fixtures are in `lib/tests/fixtures/loop-countermodels`; its README has the table and what guards each.
  - `lib/tests/loop_countermodels.rs` holds them to a JVM and the checker to its verdicts.
  - Seven loops, each with a late iteration that does what the first ones do not, read after the loop:
    - a local written once another reaches 5;
    - two statics a callee writes;
    - an array under two names;
    - a relation between two cells;
    - an object reached through an array's cell;
    - a loop inside a loop;
    - a table of 100 cells written at a computed index.
  - At `--unwind 2` none is proved: each is no verdict, its witness spurious and the loop named. At `--unwind 7`, `late` is refuted.
  - What guards them, all in `covered`/`differences` in `loops.rs`:
    - The iteration is rerun from the state with what it wrote set to any value, until it writes nothing new.
    - What is written is read off the states, by each object's allocation, so a write through a callee or a second name counts.
    - Candidates are of one number each.
    - A changed reference, a builder's content, a newly initialized class and a non-empty stack are each refused.
    - A table of more than 64 cells is any value past the loop (`Obj::unknown`), and every bulk reader of cells goes through `Obj::as_array`.
  - **Refused here** (the new item 3 holes):
    - A lemma read the cells of an array that was there before the call through `clone()`, `Arrays.copyOf` and `MessageDigest.isEqual`; `Engine::reads` was asked of an array load only.
    - `Cloned#cloned` and `#copiedOf` (`result == 0`) and `#zeroKey` (`result`) were each **Verified** for a caller that writes the final static array first; a JVM gives 5, 5 and 0.
    - Each is now refused by name, as is `String.join`'s array (`mod.rs`, `bytes.rs`, `regex.rs`).
    - The fixtures are in `lemma-countermodels` (`Cloned`), with a new test in `lemma_countermodels.rs`.
  - *Audit*:
    - The results resting on a loop invariant are 287's (`fixed-guard`, `fixed-security`). No attempt gave a false proof, so they are not affected.
    - The only lemma in use, `simpleMatch` (286, 288), reads no array, so the new refusal touches no result.
- 2026-11-17, item 5, the preservation stream's fresh pair (`zmvkptqz`): **two false proofs reproduced on its checker**, to be handed over.
  - The rule: each version starts from a fresh state (`fresh()`), and an exception is compared by its class's name.
  - The fixtures are in `lib/tests/fixtures/fresh-pair-countermodels`. Its README has the table, the commands, the audit and the checker-side test.
  - `lib/tests/fresh_pair_countermodels.rs` holds the fixtures to a JVM.
  - Both are **Verified** and non-vacuous on `domain-advances-preservation@-` (built apart):
    - `first`, with the scope `app.Entry.zeroed(cells)`. `meantToChange` is called on the caller's own arrays, and each version's copy is taken after it, so a scope that writes a cell decides what both see. Alone on `{5}`, the versions give 5 and 0. This was also Verified on this line's checker: it is older than the fresh state.
    - `failing`: two classes named `app.Failure`, one an `IllegalArgumentException` and the other an `IllegalStateException`, are one answer by name. A caller's handler catches one and not the other.
  - The README's checker-side test fails on both cases there, as it should. No refusal is committed here, since the pairing is the preservation stream's.
  - The test goes as a `failure` item to `domain-advances-preservation`, citing this commit once it is in. Its id goes in the next entry.
  - *Audit*:
    - The allowed changes of 288 to 290 only read, so the scope hole affects none of them.
    - Exceptions by name: 289's and 290's accepted preservation answers are already refused by the evidence stream's `ymzlyksq` until a rerun. Whether a class the adapters reach changes its superclass between releases was not checked, so the check belongs with the fix, before that rerun is accepted.
    - Nothing for the watcher.
  - Also read for item 5:
    - `mktymxvt` changes only `sync.py`'s trace check, which is not a rule of the run's results. Nothing to attack under this brief.
    - `rkxyyqwn` and `ymzlyksq` go with item 7, the acceptance check.
- The fresh-pair failure went to preservation as `domain-advances-preservation-I005`, citing `roqtqlpm`.
- 2026-11-17, item 5, the state stream's models on request of ArrayDeque and HashSet (`kztoupry`): **three false
  proofs under `--gaps assume`**, to be handed over.
  - The fixtures are in `lib/tests/fixtures/model-countermodels`; its README has the table, the commands, what was tried, the audit and the checker-side test.
  - `lib/tests/model_countermodels.rs` holds the fixtures to a JVM.
  - The hole: under assume, a gap's object is `Obj::new(class)`, with no field written. A gap is a constructor or a method the model does not keep. When the check runs a model of that class, the model's `size()` reads those fields. Without the model, `size()` is a gap that has no assume form.
  - Each was **Verified** `result == 0` on `domain-advances-state@-` (`qrqtplwq`, built apart), where a JVM gives 1:
    - `cloned`: `ArrayDeque.clone()` returns an `ArrayDeque`. Every assumption the result states is true of the JDK.
    - `copied`: `ArrayDeque(Collection)`.
    - `listed`: `ArrayList(Collection)`, which also reproduces on this line, since the ArrayList model is older than the run.
    - The last two state "keeps nothing of its arguments", which is false of the JDK, but nothing tells the reader it became a value.
  - The README's checker-side test fails on all three there, as it should. The models on request are the state stream's this run, so no refusal is committed here. The test goes as a `failure` item to `domain-advances-state`, citing this commit; its id goes in the next entry.
  - **Tried and guarded**:
    - Under strict, `clone`, `equals`, `hashCode` and `toString` of either class, and a set as a map key: each is a gap refused by name, with no fall-through to `Object`'s.
    - `HashSet(int)` under advised: the library's contract says "modifies nothing", which would leave `map` null, but the run reports the model's methods as gaps with no contract and solves nothing.
    - An element whose hash changes after `add`: proved not found, as on the JDK. The interpreter's set looks up by `equals` alone (`interp/natives.rs`), a refusal, not a false result.
    - A lemma reading a deque from before the call is refused by `Engine::reads`.
    - The exception classes match JDK 25.
  - *Audit*: no example task runs under `--gaps assume`. 286's and 290's drivers ask for the models under strict, and 147 to 149, the only `advised` tasks, ask for none. Nothing for the watcher.
- The models failure went to state as `domain-advances-state-I004`, citing `lqyqxwqv`.
- **To the watcher**: since the evidence stream (session 7ece8184) merged `mqkqvvmw` and `yypzyxmw` into its line, `sync.py check` here reports `session 7ece8184 has no manifest` on both, beside the known f28025bc one on `yypzyxmw`. The cause is the one recorded above (`link_commits`). The manifest is on the evidence line, so the errors should clear once the lines meet. I have not touched the trace lines.
- 2026-11-17, item 5, the state stream's write set (`qrqtplwq`, `prove --writes`): **three false proofs**, to be handed over.
  - The fixtures are in `lib/tests/fixtures/frame-countermodels`; its README has the table, the commands, what was tried, the audit and the checker-side test.
  - `lib/tests/frame_countermodels.rs` holds the fixtures to a JVM.
  - The frame is part of the assertion, so it is read only after a normal return, and only on distinct object inputs. A JVM sees the protected field written in each of these, all **Verified**:
    - `Bean#rename`, with `--throws 'java.lang.IllegalArgumentException when length < 0'`, sets `admin` and then throws. Without the throws clause, the same exit is a violation.
    - `Bean#promote(other)` with the write set `other.admin`, when `b.promote(b)`.
    - static `grant(from, to)` with the write set `to.admin`, when `grant(b, b)`. Nothing in the domain says the two beans are distinct objects.
  - Reproduced on the state checker at `qrqtplwq` and at its next commit `vwktulky`, each built apart. The README's checker-side test fails on all three at both, as it should.
  - The write set is the state stream's this run, so no refusal is committed here. The test goes as a `failure` item to `domain-advances-state`, citing this commit; its id goes in the next entry.
  - **Tried and guarded**:
    - a write through a callee, a lambda, or a recursion is refuted by the frame;
    - `Locale.setDefault` is refused by name;
    - a StringBuilder parameter is not taken;
    - an inherited field cannot occur, since `fields_of` refuses a subclass;
    - the identity of a String field after 16 String operations matches JDK 25, or is a gap.
  - *Audit*: no example task passes `--writes` on any line, so no accepted result rests on these holes. Nothing for the watcher. Both holes bear on 286's protected state, the claim the write set is for.
- Inbox: no open items.
- The write-set failure went to state as `domain-advances-state-I005`, citing `synvlnls`.
- 2026-11-17, item 5, the state stream's effect contract at a call (`vwktulky`): **three false proofs of a caller's property**, to be handed over.
  - The fixtures are in `lib/tests/fixtures/effect-countermodels`; its README has the table, the commands, the contracts, what was tried, the audit and the checker-side test.
  - `lib/tests/effect_countermodels.rs` holds them to a JVM.
  - Each contract is proved, and the caller's property through it is **Verified** on `vwktulky` (built apart), where a JVM breaks it:
    - `lockedLevel`: the setter reads a final static that its class's initializer takes from a setting the caller changed first. The contract's proof initialized the class in a fresh state. A JVM gives 0 for 5.
    - `pairedLevel`: `bean.setBoth(bean, mine, theirs)`. The method writes the argument's field and then the receiver's, while the stub writes in the `writes:` order. The contract's proof never passes one object twice. A JVM gives 1 where the proof says 2.
    - `linkedAdmin`: an argument of a subclass whose override, called by the setter, grants admin. Only the receiver's class is checked to be exact.
  - The README's checker-side test fails on all three there. The effect contract is the state stream's, so no refusal is committed here. The test goes as a `failure` item to `domain-advances-state`, citing this commit; its id goes in the next entry.
  - Whether I005's holes carry into a caller: an exceptional exit does not (`throws:` is refused, and an undeclared throw refutes the contract, tried). Aliasing does, through `pairedLevel`. `prove --may-alias this,other` already makes the frame refute I005's `promote`, so it is a ready fix.
  - Also found: the stub names a nested object-parameter class with its `$`, which javac rejects. That is a refusal, not a false result.
  - *Audit*: no example task has a `writes:` lemma or passes `--writes` on any line, so no accepted result rests on these holes. Nothing for the watcher. All three bear on 286's protected state.
- The effect-contract failure went to state as `domain-advances-state-I007`, citing `qmtxwupn`.
- 2026-11-17, item 7, the acceptance check (`examples/tools/accept.py` on the evidence line at `krptozvm`, through `rkxyyqwn`, `ymzlyksq`, `mzllzmkq` and `wowqurku`): **seven controls it accepts**, to be handed over.
  - Written in `lib/tests/fixtures/accept-countermodels/README.md`, which has the table, the controls' code, what was tried, the fix options and the audit.
  - The controls are tests on `test_accept.py`'s own made-up checkout. All 7 fail on the evidence line's `accept.py` (10 failures with subtests), each because the answer is accepted:
    - *entry*: the outcome's target is matched as a substring of the invocation's entry or of an assumption's text. An outcome about `GateAdapter#allowed`, or about the same class name in another package, stands for `GateAdapter#allowedTwice`, and so does a method an assumption mentions.
    - *step*: a driver word is any word ending in `proofs/prove.py` that contains the folder. A driver of another checkout counts, and so does `echo`.
    - *domain*:
      - a witness's null inputs are not held to the claim's `nullable`;
      - nothing holds a witness to the claim's assumption;
      - a task's `bounds` lower the claim's.
    - *expressions*: a task with no allowed change accepts a pair that ran with one.
  - A vacuity witness inside the allowed change is guarded where the task has one, since `vacuity.outside` must be the task's change. A prefix of the change is caught there too.
  - `accept.py` is the evidence stream's, so nothing is changed here. The controls go as a `failure` item to `domain-advances-evidence`, citing this commit; its id goes in the next entry.
  - *Audit*: with the source commits, the evidence line accepts 13 answers, and none rests on these holes. Nothing for the watcher. The 13 are 286's and 287's three each, 288's `fixed-security`, and 289's and 290's security answers.
    - Every outcome is about the entry named, every step runs the example's driver, and every recorded driver hash is the source commit's.
    - Null witness inputs are of nullable parameters.
    - Every equivalence task has an allowed change, and no task has bounds.
    - 286 and 287 pass the entry check only by the substring route, through the claim's "adapter entry" assumption, so a fix must keep that route.
  - This also reads `mzllzmkq` and `wowqurku` as far as acceptance goes: 288's `fixed-security` and 286's three are among the 13.
- Inbox: no open items.
- The acceptance-check controls went to evidence as `domain-advances-evidence-I007`, citing `zwrpkwnl`.
- 2026-11-17, item 5, the three rules that landed since: state's `qysmsruu`, evidence's `lzpqszyo` and preservation's
  `unswkkxp`. **Nine false proofs past them**, each **Verified** on its own line built apart, where a JVM says
  otherwise. To be handed over.
  - The fixtures are in `lib/tests/fixtures/rule-countermodels`. Its README has the tables, the commands, the options
    and the checker-side test for each stream. `lib/tests/rule_countermodels.rs` holds the fixtures to a JVM.
  - *State, `qysmsruu`* (`wd`). Under `--gaps assume`, an assumed object is made of exactly the class its descriptor
    declares, and the new refusal keys on that class. `HashSet.clone()` and `Date.clone()` are declared to return
    `Object`, so `copy instanceof HashSet` (`--model java.util.HashSet`), the cast's `size()`, and
    `copy instanceof Date` are each proved false.
    - Every assumption the two HashSet results state is true of the JDK.
    - The Date case reproduces on this line too, with no model: it is the approximation's, older than the run.
    - The fix itself holds: `a_model_does_not_read_fields_no_constructor_of_it_wrote` passes at `qysmsruu`, so
      I004's three cases are refused by name. Evidence's I004 test,
      `an_observed_initializer_is_bound_to_what_it_was_observed_on`, passes at `krptozvm`.
    - Method note: a lib exported with `git archive` carries the commit's time as its mtime. Built into a target folder
      that already holds newer artifacts, cargo keeps the old library. The first debug run here "failed" the state
      fix that way. Every verdict above is from a build whose sources were touched first, checked against the CLI of
      the release build. The debug-test results of earlier entries (I005 at `vwktulky`, I007) may have come from such
      a build. Their release-CLI probes stand, and the state stream's fixes (`sltlykpk`, `nslmqyry`) are next to
      challenge anyway.
  - *Evidence, `lzpqszyo`* (`ob`):
    - An initializer that writes its superclass's static (`inherited`) or a superinterface's array (`filled`). The
      observer leaves supertypes out of the comparison, and the checker initializes them itself. No stated assumption
      is false.
    - A property read through `System.getProperties().get` (`bypassed`): the result says "it read no system
      property". `Recording` overrides `getProperty` alone.
    - The default time zone (`zoned`) and an environment variable (`environ`): not stated. These are of the kind of
      I004's `lowered` and `configured`, through settings the binding does not list.
  - *Preservation, `unswkkxp`* (`lg`). A `LogRecord` subclass passes `confined_record`, yet the default handler's
    formatting calls its `getMessage`:
    - one that counts in a field of the record the caller holds (`seen`, 1 against the proved 0; every stated
      assumption is true of the JDK);
    - one that throws a `Throwable`, which `StreamHandler.publish`'s `catch (Exception)` lets out of `log`
      (`escaped`).
  - Each README test fails on its stream's line: state at `qysmsruu`, evidence at `krptozvm`, preservation at
    `unswkkxp`. None of these rules is mine, so nothing in `lib/src` changes here. Each goes as a `failure` item to
    its stream, citing this commit; the ids go in the next entry.
  - *Audit*: no accepted result rests on these holes, so there is nothing for the watcher.
    - No example task runs under assume.
    - 290's five observed classes, read with `javap` from the pinned JARs: each `putstatic` is of the class's own
      field, and none calls `getenv`, `TimeZone` or `getProperties`. The servlet classes' `getBundle` reads the
      locale, which is stated.
    - 287's preservation logs through spring-jcl's `LocationResolvingLogRecord`, which is made inside `JavaUtilLog`
      and dropped after `log`.
- 2026-11-17, item 6, the formalizations of 287, 307 and 286's protected state. **Each claim accepts a wrong
  implementation**. Each mutant is a patch under its example's `controls/`, which no task uses yet; the reasoning is
  in each example's notes.
  - **287**, `check-only-guard.patch` on 6.3.8: `if (for_check && passwordb.length > 72)`.
    - `matches` and both `checkpw` run the fix's code, so all three claims are predicted to say of it what they say
      of 6.3.8. Its driver lines equal 6.3.8's on all 33 probes, and the oracle says it holds.
    - But `encode` of 73 bytes returns a hash again, and the 72-byte prefix matches it: the advisory's defect,
      through the encoder no claim covers.
  - **307**, `default-charset.patch`: `password.getBytes()`, the platform charset the commit removes.
    - On JDK 18+ the default is UTF-8, so it equals after on all 45 probes.
    - Under `-Dfile.encoding=COMPAT` with `LANG=C` it differs on 17 probes. The claim fixes no default charset
      ("on one and the same JDK").
  - **286**, `first-suppressed-only.patch` on 5.3.19: `checkAllowedFields` returns after the first suppressed value.
    - `isAllowed` is the fix's, and the protected-state claim binds one value, so all three claims are predicted to
      be decided as on 5.3.19.
    - On a JVM, `age=5, Age=32` binds 32. The probes catch it (`bind-list-upstream`, `bind-map-upstream`); no claim
      does.
  - Each goes as an inbox item to its owner: 287 and 307 to preservation, 286 to state. A new claim is theirs and the
    user's.
- Tests: `test_costs.py run --changed` passed (42 Rust test binaries, 23 Python suites), and
  `validate_example.py` passed for 286, 287 and 307.
- Sent, each citing `lqvlvwsm`:
  - the item 5 failures: `domain-advances-state-I008` (`wd`), `domain-advances-evidence-I008` (`ob`) and
    `domain-advances-preservation-I006` (`lg`);
  - the item 6 formalizations: `domain-advances-preservation-I007` (287), `domain-advances-preservation-I008` (307)
    and `domain-advances-state-I009` (286's protected state).
- **To the watcher**: `sync.py check` here now reports 8 `has no manifest` errors. Besides the three recorded above,
  session f28025bc is now stamped on `roqtqlpm`, `smnuqrou`, `uktunxxo` and `llwznzwm` too. The cause is the same
  (`link_commits`: the preservation stream merged them), the manifests are on the other lines, and evidence's
  `mktymxvt` makes such a stamp a note once the lines meet. I have not touched the trace lines.
- 2026-11-17, item 5, the state stream's fixes for I005 (`sltlykpk`) and I007 (`nslmqyry`): **both hold, and two new
  false proofs past the second**, to be handed over.
  - Built apart at `nslmqyry`, with the sources touched first: `frame_countermodels.rs` and
    `effect_countermodels.rs` pass. Each of the six earlier cases is refuted, or refused, or proved as JML's
    `assignable` states it (`this == other || this.admin == \old(this.admin)`).
  - The new hole: the read gate exempts a **final instance field** of an object that was there before the call. A
    contract's proof makes the receiver and the arguments with their constructors in the harness's fresh state, and a
    caller's object was made in another state.
  - The fixture is `lib/tests/fixtures/contract-countermodels`; its README has the table, the commands, the options,
    what was tried and the checker-side test. `lib/tests/contract_countermodels.rs` holds it to a JVM.
  - Each is **Verified** `result == level` at `nslmqyry`, with no assumption stated, where a JVM gives 0 for 5:
    - `snapshotLevel`: the receiver's `final boolean locked = Config.locked`, made with the setting on and the setting
      put back before the call;
    - `scaledLevel`: the same, through an argument's final field.
  - The README's checker-side test fails on both there, as it should. The effect contract is the state stream's, so
    nothing in `lib/src` changes here. It goes as a `failure` item to `domain-advances-state`, citing this commit; the
    id goes in the next entry.
  - **Tried and guarded**:
    - a contract whose call starts a class initializer, refused by `Engine::initializes_in_frame`;
    - a receiver of a class with two constructors, refused by the layout.
  - *Audit*: no example task has a `writes:` lemma or passes `--writes` on any line. No accepted result rests on the
    hole, so there is nothing for the watcher.
- Inbox:
  - `domain-advances-challenge-I002` (the lemma rule and the write-set rule meet in `Engine::call`): taken on.
    - Its first case, a framed method or an effect contract whose call starts a class initializer, is tried on
      state's line above and is guarded there.
    - The other two need both rules in one tree, and no line has both yet: a lemma whose proof runs a framed method or
      a call a contract stands in for, and an effect contract inside a summarized method. The default line has
      neither stream.
    - Next: a trial merge of this line and state's, built apart with the conflict in `Engine::call` resolved as the
      inbox item describes, or the default line once the watcher has merged both.
- The contract failure went to state as `domain-advances-state-I010`, citing `ukukylmu`.
- 2026-11-17, item 5, preservation's `wokytpkz`, its fix for I003 and I005: **both hold, and three false proofs
  past the exception comparison**, to be handed over.
  - The fix:
    - the scope is read on copies of its own;
    - an exception is its class's name and the names of every class above it up to `Object`.
  - Built apart at `wokytpkz` (sources touched first), `pairing_countermodels.rs` and `fresh_pair_countermodels.rs`
    pass, their checker-side tests included.
  - The fixture is `lib/tests/fixtures/thrown-pair-countermodels`; its README has the table, the commands, the
    options, what was tried and the checker-side test. `lib/tests/thrown_pair_countermodels.rs` holds it to a JVM.
  - Each is **Verified** "agree on every input where k >= 0 && k < 4", non-vacuous, with no assumption stated, where
    a caller's handler tells the versions apart on a JVM:
    - `marked`: an interface the previous version's exception implements. The module says interfaces are not
      compared, so this one is the documented limit, reproduced.
    - `messaged`: the message.
    - `coded`: a field of the exception's own class (403 against 404).
  - The README's checker-side test fails on exactly these three there.
  - **Tried and guarded**:
    - a superclass's superclass that changed under kept names, refuted;
    - a cause, a gap under strict;
    - a shallow copy for the scope, which is whole for the arrays the pair takes.
  - The pairing is preservation's, so nothing in `lib/src` changes here. The test goes as a `failure` item to
    `domain-advances-preservation`, citing this commit; the id goes in the next entry.
  - *Audit*:
    - 289's and 290's `preservation` say "throw the same exception". The rerun on this checker reads that as one class
      name and one chain of superclass names.
    - Across the releases' pinned JARs (hashes checked), no class named `*Exception` or `*Error` differs in what it
      extends, what it implements or its members (`javap -p`; 101 classes for 289, 191 for 290). So `marked` and
      `coded` cannot occur there.
    - Messages were not compared.
    - A note in both examples records this; it is also their item 6 entry for preservation. Nothing for the watcher.
- Inbox: no open items.
- The exception failure went to preservation as `domain-advances-preservation-I009`, citing `pklttqzw`.
- 2026-11-17, items 5 and 7, evidence's `kqxwrwrx`, its fix for I007: **the fix holds, and four more controls
  accepted past it**, to be handed over.
  - All seven earlier controls pass against `accept.py` at `kqxwrwrx`, and its own `test_accept.py` passes 38 tests.
  - The new hole is in the step check. It reads a step's words up to the task's name and the first `--work`. The
    pipeline runs the whole step with `bash -c`, and nothing else in the job is read.
  - Each control below is accepted with no limit on `test_accept.py`'s made-up checkout (4 tests, 7 failures with the
    subtests):
    - *a shell suffix*: `; cp …` or `&& sed -i …` after the driver rewrites the outcome. evidence.json does not hash
      it.
    - *an earlier step*: it replaces the driver in the job's checkout, or writes the outcome folder. The driver hash
      the artifacts check compares is written by whatever driver ran.
    - *`--work` given twice*: accept.py takes the first, the driver's argparse the last. `--work=DIR` is not read at
      all.
    - *`--jvmcontract PATH`*: the outcome comes from another binary. evidence.json names its sha256, which nothing
      compares.
  - Written in `lib/tests/fixtures/accept-countermodels/README.md`, "Past the fix", with the controls' code, the fix
    options and what was tried. `accept.py` is the evidence stream's, so nothing is changed here. The controls go
    as a `failure` item to `domain-advances-evidence`, citing this commit; its id goes in the next entry.
  - **Tried and guarded**:
    - a witness on which the assumption throws: only an `AssertionError` counts as reproduced, and `Threw` is
      unverifiable;
    - the gate's record over objects, which is left unbound;
    - a null witness input, written as JSON `null`, which the check reads.
  - Noted, not a hole: the gate's record is the checker's rendering for readers, not the class file the JVM ran.
  - *Audit*: every step of the 13 accepted answers' jobs is a plain driver run, with one `--work`, no
    `--jvmcontract` and no shell operator. Nothing for the watcher.
- The acceptance-check controls past the fix went to evidence as `domain-advances-evidence-I010`, citing `xnqlyxnw`.
- 2026-11-17, item 5, state's `llyzwmyp` (the observation binding copied onto its line, with a lambda named by what
  it was defined from) and `vvpxytqs` (its fix for I008): **three false proofs past the binding**, to be handed over;
  `vvpxytqs` holds.
  - The fixture is `lib/tests/fixtures/binding-countermodels`; its README has the table, the commands, the options,
    what was tried and the checker-side test. `lib/tests/binding_countermodels.rs` holds it to a JVM.
  - Each is **Verified** with `--observed-initializer`, where a JVM says otherwise and the checker without the
    observation finds the violation:
    - `rehooked`: the initializer has another class put a lambda of its own in that class's static (`() -> n` for
      `() -> 1`). Both are named `bc.Hooks$$Lambda` now: proved 1, a JVM gives 5. Verified at `vvpxytqs`. At
      evidence's `nsnxmlmt` it is refused, because the name there carries the address.
    - `boxed`: the initializer writes a field of an object another class's final static holds. Unheld, it is compared
      by its class's name. Proved 0, a JVM gives 5, at both lines (it is `lzpqszyo`'s).
    - `relocaled`: the initializer sets the JDK's default locale to Turkish. The observer reads the locale before the
      initialization and compares classes of the class path only. Proved 105, a JVM gives 305, at both lines. Every
      stated assumption reads as true of a JVM that starts in English.
  - The first two fall under the stated "what it holds nothing of is taken to be the same too", false here; the third
    under none. The binding is evidence's and state holds a copy, so nothing in `lib/src` changes here. The test goes
    as a `failure` item to both, citing this commit; the ids go in the next entry.
  - `vvpxytqs` **holds** for what was tried: an `aastore`, a string concatenation (`String.valueOf`, refused), a
    virtual call, a cast and `instanceof` are each refused. A gap's `null` is stated ("never null"). A lemma's
    argument cannot be of a subclass, being a primitive or a String.
  - *Audit*: 290's five observed classes, read with `javap -c` from the pinned JARs:
    - none sets a locale, a time zone or a property;
    - none has a `putfield` or an `invokedynamic` in its `<clinit>`;
    - each `putstatic` is its own class's.
    Not affected, and nothing for the watcher.
- Tool fix: `test_costs.py estimate` failed on this session's own log. A `python3 -m unittest` run from an export in
  `/tmp` resolved outside the checkout, and `cost_inventory.python_runs` guarded that for a file but not for a dotted
  module. It is now guarded the same way (`lib/tools/cost_inventory.py`).
- Tests: `test_costs.py run --changed` passed (45 Rust test binaries and the Python suites).
- I002: a trial merge of this line (`xnqlyxnw`) and state's (`vvpxytqs`), made with `git merge-tree`, conflicts in
  `lib/src/bmc/mod.rs` only at `Engine::call`. It is resolved by keeping both blocks, and is being built apart in
  `/tmp/trial` for the next cycle.
- Inbox: no open items.
- The binding failure went to evidence as `domain-advances-evidence-I011` and to state as
  `domain-advances-state-I011`, both citing `klqnuoxw`.
- 2026-11-17, I002 and item 5, where the lemma rule and the write-set rule meet: **two false proofs through an
  effect contract's stub**, to be handed over to state.
  - The trial merge (`xnqlyxnw` with state's `vvpxytqs`, the `Engine::call` conflict resolved by keeping both blocks)
    built apart.
  - I002's two remaining cases cannot occur as worded. A lemma's proof and a contract's proof are given no lemma and
    no contract (`lemmas: None` in `property.rs`). A framed method or a contracted call inside a lemma's proof runs as
    written, and `Engine::keeps` sees it.
  - What can occur: a check's own `--decreases` or `--writes` with a contract in `--lemmas`. The stub's `effect`
    intrinsic puts each written field into the object directly, and does not ask `keeps`.
  - The fixture is `lib/tests/fixtures/stub-countermodels`; its README has the table, the commands, the options, what
    was tried and the checker-side test. `lib/tests/stub_countermodels.rs` holds it to a JVM.
  - Each is **Verified** on the trial merge and on state's `twtuqvvr` (built apart, sources touched), and refused
    there without the contract:
    - `Store.f`, by induction on `k`: the method writes a static's bean through the setter, calls itself, and reads
      the bean. The hypothesis drops the call's write. `result == 0` is proved, non-vacuous; a JVM gives `f(2) == -1`.
    - `Touch.touch` with `--writes ''`: it writes a static's bean through the setter, and is proved. The statement
      says nothing of the write set, since a static method over primitives has no field to read after the call.
  - The effect contract is state's, so nothing in `lib/src` changes here. The test goes as a `failure` item to
    `domain-advances-state`, citing this commit; the id goes in the next entry. The fix offered is one call of
    `keeps` per write in the intrinsic.
  - *Audit*: the only `decreases:` of any example, on all four lines, is the `simpleMatch` lemma of 286 and 288,
    whose proof takes no contract, and no example has a `writes:` or passes `--writes`. Nothing for the watcher.
  - I002 is answered by this entry.
- New on the other lines since the last cycle, not yet challenged:
  - state's `twtuqvvr` (its fix for I010);
  - evidence's `mmnoqopr` (the binding over supertypes, the Properties map, the time zone and the environment: I008);
  - preservation's `owrsowqm` (a pair's two runs of one loop past the bound go on from one state).
- Tests: `test_costs.py run --changed` passed.
- Inbox: no open items.
- The stub failure went to state as `domain-advances-state-I013`, citing `uqrzluvx`.
- 2026-11-17, item 5, preservation's `owrsowqm` (a pair's two summaries of one loop take one set of bits where the
  code and the state are the same): **two false proofs past the ties, and one older false proof by the same cause**,
  to be handed over.
  - The cause is in `reach` (`lib/src/shared.rs`), which both rest on. It follows no call whose owner is a JDK class
    or interface, so an application class's code run through `IntUnaryOperator` is in no fingerprint.
  - The fixture is `lib/tests/fixtures/tie-countermodels`; its README has the table, the commands, the options, what
    was tried, the checker-side test and the audit. `lib/tests/tie_countermodels.rs` holds it to a JVM.
  - `old` and `new` differ only in `Step`'s private helper and in `Config`'s initializer. A JVM gives 2 against 1
    past 1000:
    - `summed` and `configured` are each **Verified** at `lmyvttyt` (preservation's line, built apart), non-vacuous,
      with no assumption, `k < 2000`, `--unwind 2`. The class surface leaves out private methods, and a class that
      only the operator reads is not in `uses`, so its static is not in the key. On this line, without the ties,
      both get no verdict.
    - `supplied`, under the defaults without `--assume`: "behaves as before on every input (... identical in both
      versions; nothing to prove)". This is on every line, this one included: the shortcut `plan.identical` is older
      than the run.
  - The pairing and `shared.rs` are preservation's this run, so nothing in `lib/src` changes here. The test goes as
    a `failure` item to `domain-advances-preservation`, citing this commit; the id goes in the next entry.
  - *Audit*:
    - The ties are on preservation's line only. They are made for 287's preservation, which is open, and its loops
      call only `BCrypt`'s own statics.
    - The shortcut is not taken with `--before-classpath`, which every decided pair of the run (289, 290) passes.
    - Nothing for the watcher.
- **To the watcher**: `sync.py check` on this line reports 15 `has no manifest` errors, up from 8. Preservation's
  merge `lmyvttyt` stamped session f28025bc on seven more of my commits (`pklttqzw`, `ukukylmu`, `lqvlvwsm`,
  `zwrpkwnl`, `qmtxwupn`, `synvlnls` and `lqyqxwqv`). The cause is the one recorded above (`link_commits`). I have
  not touched the trace lines.
- New on the other lines since the last cycle, not yet challenged: evidence's `wxpoysws` (its fix for I010, the step
  check) and state's `uxomquou` (the binding of `mmnoqopr` taken whole).
- Inbox: no open items.
- The tie failure went to preservation as `domain-advances-preservation-I010`, citing `qnlomnmx`.
- 2026-11-17, item 5, evidence's `mmnoqopr` (its fix for I008) and `vqquvmnm` (its fix for I011): **both hold, and six
  false proofs past the binding**, to be handed over.
  - Built apart at `qxstltmq` and `vqquvmnm`, with the sources touched. `observed_countermodels.rs` passes at both, so
    I008's five cases are refused or stated. At `vqquvmnm` the I011 test passes too.
  - The new holes are settings the binding does not see.
  - The fixture is `lib/tests/fixtures/setting-countermodels`. Its README has the table, the commands, what was tried,
    the options and the checker-side test. `lib/tests/setting_countermodels.rs` holds each case to a JVM, under the
    setting and under another.
  - Each is **Verified** at `vqquvmnm` with the class observed under its setting. The result says "it read no system
    property" and nothing of the setting:
    - `mapped`: `Optional.of(k).map(System::getProperty)`. A lambda's frame is hidden, so the recorder takes
      `java.util.Optional` for the reader and counts the read as the JDK's own.
    - `kept`: the value `Properties.putIfAbsent` returns where the property is set. It is not overridden, and nothing
      changes. `clearProperty`'s return value was Verified at `qxstltmq`; `vqquvmnm` refuses it as a changed setting.
    - `looked`: `getenv` through a method handle looked up by name. The module documents this limit, but the result
      does not state it.
    - three settings the JDK takes at startup: `availableProcessors()` (`counted`), the working directory through
      `File.getAbsolutePath` (`rooted`), and the default charset through `getBytes()` (`encoded`).
  - The README's checker-side test fails on all six at `vqquvmnm`, as it should. The binding is evidence's, and state's
    `uxomquou` takes it whole, so nothing in `lib/src` changes here. The test goes as a `failure` item to
    `domain-advances-evidence`, citing this commit; the id goes in the next entry.
  - *Audit*: 290's five observed classes, read with `javap -c -p` from the hash-checked JARs:
    - none of their initializers calls any of these methods;
    - `UrlPathHelper`'s logger setup reaches JUL's configuration through JDK frames, but the observation does not hold
      the logger (`{"u": ...}`), and a read of it is refused.
    Not affected, and nothing for the watcher.
- Inbox: `domain-advances-challenge-I003` (cycle 17 OOM-killed, VF-037).
  - The uncapped run this cycle started again was stopped by its own process group.
  - The changed tests ran under `MemoryMax=8G` with `--rust-jobs 1` and passed: 48 test binaries, exit 0.
  - After `cleared` became `kept`, the new test and `test_costs.py lint` were run again under the cap and pass.
  - Its next step, preservation's call-level rule, is taken next. Preservation's `kskmpmny` looks like it: "closed
    against calls back through the JDK", merged with this stream's tie countermodels.
- Not yet challenged: preservation's `kskmpmny` and `lqkwokqq` (I006, I009); evidence's `wxpoysws`; state's
  `twtuqvvr`, `qlylowvo` (a stand-in sampled on a JVM) and `krxzxzow`/`lwxvoqsy`.
- Next:
  - item 5: preservation's `kskmpmny` first, as I003 asks; then state's `qlylowvo` stand-ins and `twtuqvvr`, and
    evidence's `wxpoysws`;
  - item 5: `nzsypymy` (290's preservation restated, also item 6);
  - item 6's entries for 288's `fixed-security` and 289's other answers.
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

# Brief: domain advances, the state stream

A stream of [domain-advances.md](domain-advances.md), which is the instruction: read it in full first, its
Direction and "How to work through it" above all. You own one outcome across the whole stack.

## The outcome

**Intent.** Permitted updates preserve authorization-relevant state: when an application binds request parameters
onto a bean and protects some of its properties, no request the binder accepts changes a protected property.

**Why the existing result is not this.** Example 286's decided claim is the *decision lemma*: `isAllowed` denies a
field that a disallowed pattern matches ignoring case. That is about a field's name. Consider a bean whose permitted
setter does more than its name says:

```java
void setDisplayName(String name) {
    this.displayName = name;
    this.isAdmin = name.startsWith("admin:");
}
```

Denying the field name `isAdmin` establishes nothing about this bean: a permitted update writes the protected
state. The intent needs a statement about *what binding writes*, which crosses the application's policy, the
library's binding path (`DataBinder`, `BeanWrapperImpl`, `java.beans.Introspector`, type conversion) and the heap.

**Working formalization.** `claims/protected-age-not-mutated.json` of example 286, frozen: with `age` protected by
the one disallowed pattern, `DataBinder.bind` of one property value named `field` with the value `"32"` onto a
fresh `ProtectedBean` returns normally and leaves `age` 0, for every simple property name of at most 8 units.
Entry: `example286.adapter.BindingAdapter#ageAfterBinding(ZLjava/lang/String;)I`. Expected: refuted on 5.3.18
(binding `Age` writes it), established on 5.3.19. This formalization is a hypothesis: `ProtectedBean` has only
honest setters, so it cannot tell the binder's guarantee from the bean's. Whether the accepted statement should be
"binding writes only what the permitted setters write" composed with "each permitted setter writes only its own
field" is yours to find out.

## Your work

1. **Find today's first blocker on the real path.** On 2026-11-15 `ageAfterBinding` stopped at
   `java.util.ArrayList.<init>(int)` in `MutablePropertyValues.<init>:61`. Since then example 290 runs an
   `ArrayList` model on request (`--model java.util.ArrayList`) and observed initializers
   (`--observed-initializer`, `lib/src/observed.rs`). Give 286's `proofs/prove.py` the protected-state tasks (it
   is "prove only" and has the entry's adapter already; add 289's three properties: `accept.record`, the mutant
   rule, the trial mark), queue `fixed-protected-state-mutation` with the model and a `--work` folder of its own,
   and record where it stops now. Expect reflection: `BeanWrapperImpl`, `CachedIntrospectionResults`,
   `Introspector`, `Method.invoke`.
2. **The refutation first.** `vulnerable-protected-state-mutation` needs one path that binds `Age` and writes
   `age`, and its witness replays on a JVM whatever the models are: a refutation rests on none of them. It is the
   cheaper of the two and shows the path end to end. Decide it and have `accept.py` accept it.
3. **The smallest sound account of the binding path.** The establishment needs every path of `bind` for the
   domain. Options, and what each would rest on:
   - run the reflection as the JVM does it for the classes in play (the bean is known: its properties, setters
     and types are finite and can be *observed* on a JVM and bound to the class bytes, as 290 observes
     initializers; the evidence stream is binding those observations to what they were observed on, and you need
     the same binding);
   - a contract for the introspection step, checked against the JVM by sampling, that says which setter a
     property name resolves to;
   - an *effect contract* for the callee the binder reaches.
4. **A first effect contract**, as small as the claim needs: for a method, what it may read; its normal and
   exceptional postconditions; what it writes and what it leaves (a frame); what it allocates and which aliases
   it may create; that it returns. The checker already refuses writes inside a summarized method
   (`Engine::keeps`, `lib/src/bmc/mod.rs`) and, since the foundation, reads of what a caller can change
   (`Engine::reads`); a contract that *states* a write set is the generalization, and the use site must check that
   what the contract reads and frames matches the state it is used in. The foundation's countermodels
   (`lib/tests/fixtures/claims/claims/Effects.java`) show how such a rule fails when the use site's state is not
   the proof's.
5. **The adversarial fixture.** A small bean beside `ProtectedBean` whose permitted setter also writes the
   protected field (the `isAdmin` example), and an honest twin. The setter's contract ("writes `displayName`
   only") must be refuted on the first and established on the second; the application-level statement must be
   refuted on the first *through an allowed field name*, with a witness that replays. This is the test that the
   capability answers the intent and not the field-name lemma.
6. **Connect to the real path, then a second consumer**: the same contract used by `bind` on 5.3.19 (286) and by
   one more caller or revision: 288's binding task (the same binder under locales) is the nearest. What the
   second use shows to have been accidental goes into the contract's form.

## What you own in this run

Example 286's protected-state tasks, its adapter and driver; `lib/src/observed.rs` as far as binding reflection
needs it (the evidence stream changes how an observation is *bound*: coordinate through the inbox before either of
you changes its format); `lib/src/summary.rs` and the summary side of `lib/src/property.rs` when a contract grows
out of a lemma; the heap side of `lib/src/bmc/` (`reuse/footprint.rs` is the existing static footprint analysis).
The preservation stream owns pairing; `examples/tools/accept.py` is the evidence stream's.

## Done when

- Both protected-state tasks of 286 are decided at bound 8 and accepted; or the chain of blockers on the real path
  is recorded as observed gaps (`records/refusals/`), each with the job that observed it and a test that closes it.
- An effect contract exists that the adversarial setter fails and the honest one meets, with a countermodel test
  for each side condition of its use, and two consumers; or the record of what form it would need and why the
  cycle's attempts did not reach it.
- The example's notes say which statement was accepted: the frozen claim, or a corrected formalization proposed to
  the user as a new claim file.

## Progress

- 2026-11-17, step 1 (the working formalization and the accepted claim unchanged; nothing decided). 286's
  `proofs/prove.py` runs the protected-state tasks: entry `BindingAdapter#ageAfterBinding`, `--model
  java.util.ArrayList`, the simpleMatch lemma, unwind 16, and 289's three properties (`accept.record` writes
  `evidence.json`; a mutant that is not the replay's ends the run; another bound is marked a trial). The mutant is
  now built by the route's recipe and is byte for byte the JAR `receipts/mutant-replay` ran (`48323d21…`; before,
  `--release 8` and a re-deflated copy gave `12be51f1…`), so the evidence stream can rerun `mutant-security` on it.
  **Where bind stops now** (probe at bound 2, a trial): past `ArrayList`, under strict gaps at
  `java.util.ArrayDeque.<init>()` (`AbstractErrors.<init>:44`, the binding result, made on every path) and
  `String.toLowerCase()` at `DataBinder.isAllowed:828` on a non-ASCII field. The second is a finding about the
  frozen claim: unlike the decision claim it does not restrict `field` to ASCII, and the checker lowers ASCII only.
  Job `20261117-130335-example-286-protected-state-tasks-at-the` records both tasks at bound 8 (expected exit 1).
- 2026-11-17, step 1 continued, to the reflection (nothing decided; the frozen claim unchanged). Inbox:
  `domain-advances-state-I002` taken: this line is rebased onto `rkxyyqwn`, and 286's driver now runs through
  `examples/tools/beside_route.py`, keeping only each claim's entry, models, observed initializers and unwinding (the
  decision claim's runs are as the evidence stream left them: no model, the verifier's unwinding).
  `domain-advances-state-I001` noted: that test was run with `RUN_STREAMS_WATCHER` unset, not changed. Two models on
  request, as `ArrayList`'s: `java.util.ArrayDeque` (a stack: `push`, `pop`, `peek`, `size`, `isEmpty`, `clear`) and
  `java.util.HashSet` (the keys of the `HashMap` model: `add`, `contains`, `size`, `isEmpty`; `AbstractSet()` is now
  an exact JDK call, as `AbstractCollection()` was), each with a fixture of its definition written out (`claims.Deques`,
  `claims.Sets`) proved with the model, sampled on a JVM, and shown to fail on a mutated model. **Where bind stops
  now** (probes at bound 2, trials): past `ArrayDeque.<init>` and `HashSet.<init>` (the binding result's), past
  `PropertyEditorRegistrySupport`'s initializer (observed), at `CachedIntrospectionResults`: observed, its static
  `strongClassCache` is a `ConcurrentHashMap` the observation does not hold. That is the reflection: `forClass` misses
  the empty caches and introspects the bean through `java.beans.Introspector`; the setter is then called by
  `Method.invoke`, after type conversion by the default editors. Sent `domain-advances-evidence-I006`: coordinate
  `observed.rs`'s format with the evidence stream's binding change before step 3 adds held kinds. Job
  `20261117-130335-…` (queued in cycle 1) runs the driver as it now is.
- 2026-11-17, steps 4 and 5, the checking side of a first effect contract (nothing of 286 decided; the frozen claim
  unchanged). Inbox: nothing open. **A write set** (`prove --writes this.displayName`, own checker only): the
  fields of the receiver and object parameters a method may write. The check proves the frame with the property:
  after a normal return, every other field of those inputs is unchanged (a primitive by value, a String or object by
  identity, through the new `p == \old(p)`). That frame is conjoined to the assertion, so a write outside the set is
  refuted by the harness and replayed on a JVM. Inside the call, generalizing `Engine::keeps` (`Options::frame`), the
  engine refuses a write to anything else that existed before the call: a static field, an array, an object no input
  is (even one a named field holds), or a class initialization (an object the initializer makes would look new to the
  call). Fixture `claims.Frames` (`lib/tests/fixtures/claims`): the brief's adversarial `setDisplayName` (also writes
  `admin`) is refuted, its witness run on a JVM. The honest twin and a setter that writes `admin` and puts it back
  are established. A copy of a String counts as a write. One countermodel per refusal, each writing on a JVM
  (`Frames.main`), and a mutation switching the engine's frame off makes the refusal test fail. The beans are the
  lib fixture's, not yet beside `ProtectedBean`: a new adapter source in 286's `target.json` changes the adapter set
  `accept.py` compares for every 286 task (its line 326), under the evidence stream's queued jobs, and the
  application-level statement they serve needs the binding path (step 3). Not yet: the reads, allocation and alias
  parts of step 4, and the contract's use at a call.
- 2026-11-17, step 4's use side, and step 5 at the application level in the lib fixture (nothing of 286 decided; the
  frozen claim unchanged). Inbox: `domain-advances-state-I003` taken: step 3 will add the held kinds it needs (an empty
  `ConcurrentHashMap`, a bean's property descriptors) as new `Object` variants in `observed.rs`, leaving `Slot`, the
  existing variants and the keying as they are, and will take the evidence stream's `on` record once `mqkqvvmw` is
  merged; nothing in `observed.rs` changed in this cycle. **An effect contract at a call** (`--lemmas`, a declaration
  with `writes:`): it is proved first with its frame and *as reading nothing that was there before the call* (no
  field of the receiver or an object argument, no non-final static, no array, no default locale, no identity
  comparison of such an object: `Options::closed_frame`, generalizing `Engine::reads` and `Engine::compares` as the
  write set generalized `keeps`). What it writes is then a function of its arguments. At a call on a receiver of
  exactly its class, with arguments within its `arrays:` bound, a stub of the claim's class runs instead
  (`bmc::Effect`, the `effect` intrinsic): a field the assertion gives a parameter (`this.f == p`, now also a String
  by identity) takes it, another written primitive takes any value, and nothing else changes; elsewhere the method
  runs as written. The run names the contract among what it rests on. `claims.Frames` gives the application-level
  statement "a rename makes no account an admin". With the honest setter's contract it is proved ("an admin stays one,
  under the new name"). The adversarial setter's contract is refuted, so the check resting on it is refused, and
  without it a rename to `admin:` refutes the statement, a replayed witness through the allowed `displayName`. Each
  side condition of the use has a countermodel that grants admin on a JVM, and each was a false proof with its rule
  switched off (by mutation): a name longer than the bound, a receiver field a caller set (`setRole`), a static
  switch, a literal's identity, a subclass's hook reached through the inherited setter. Not yet: a stated read set,
  the postcondition beyond parameter equalities, escaping allocations, a second consumer, and the use at a reflective
  call (`Method.invoke`, how the binder reaches a setter).
- 2026-11-17, a soundness fix to the models on request (nothing of 286 decided; the frozen claim unchanged). Inbox:
  `domain-advances-state-I004` taken. The challenge stream's countermodels (`lqyqxwqv`) showed that under `--gaps
  assume`, with `--model` of the class, the own checker proved `ArrayDeque.clone()`, `ArrayDeque(Collection)` and
  `ArrayList(Collection)` give an empty collection where a JVM gives one element: assume made or constructed an object
  with no field written, and the model's `size()` read those fields. Such a gap is now refused by name under assume
  when its object (the one a constructor constructs, or the new one a method is taken to return) is of a class whose
  model the check runs (`ClassPath::checker_runs`, which also covers the `HashMap` model the checker always runs), and
  a constructor's contract under advised is refused likewise, since it writes none of the model's fields. The
  fixture, its README and its JVM test are copied unchanged from `lqyqxwqv`; the README's test
  `a_model_does_not_read_fields_no_constructor_of_it_wrote` is added to `lib/tests/model_countermodels.rs` and also
  requires the refusal to name the call; it fails with the refusal switched off. No accepted result used the hole
  (every example task is strict).
- 2026-11-17, a soundness fix to the write set (nothing of 286 decided; the frozen claim unchanged). Inbox:
  `domain-advances-state-I005` taken. The challenge stream's countermodels (`synvlnls`, `fc.Framed`) showed the frame
  proved where a JVM sees `admin` written, in two ways. First, a write before a declared exception: the frame was
  part of the assertion, read after a normal return only. It now holds on a declared exceptional exit too (the
  harness checks it after the expected exception, `harness::generate_property_framed`), so `rename("b", -1)` is
  refuted with a witness a JVM replays. Second, one bean passed as two inputs: the frame is now of locations, as JML's
  `assignable` is. Every two inputs of one class may be one object (the check adds the alias choice and the domain
  says so), and a field one of them names is framed in the other only where they differ (`this == other ||
  this.admin == \old(this.admin)`). So `promote` and `grant` are proved with that frame, which a JVM keeps, and
  never with `this.admin == \old(this.admin)` alone, which it breaks. The README's test is adapted to that: the
  exceptional case must be refuted, and the alias cases must not prove the unaliased frame. A test that what the
  frame names is proved on either exit and alias, and a countermodel of my own (`claims.Frames$Linking#link`, which
  writes its own name only where `other` is itself), is refuted only because aliasing is explored. Each fails with
  its fix switched off (by mutation). An effect contract is proved through the same check, so its stub's writes now
  rest on a frame of locations. `domain-advances-state-I006` noted: the observation binding (`lzpqszyo`) is not on
  this line yet; step 3's held kinds will be built on `observed.rs` as it stands there, and an observer line needs its
  `on` record.
- 2026-11-17, a soundness fix to the effect contract's use (nothing of 286 decided; the frozen claim unchanged).
  Inbox: `domain-advances-state-I007` taken. The challenge stream's countermodels (`qmtxwupn`, `ec.Uses`) showed
  three callers proved through a proved contract where a JVM breaks them. The one bean passed twice (`pairedLevel`)
  was already refuted on this line: since the last cycle the contract is proved with inputs of one class that may be
  one object, and `Pair#setBoth`'s assertion then fails. The other two are fixed. *A final static an initializer
  computed* (`Locked.LOCKED = Config.locked`): an effect contract's proof now reads no static field but a constant
  (final, with a `ConstantValue`), since the initializer ran in whatever state a caller left and the proof's in the
  harness's fresh one. The contract is refused by name. *An argument of a subclass* (`Rogue`, whose `linked()` sets
  `admin`): the stub stands in only where each object argument too, a String aside, is null or of exactly its
  declared class, so `linkedAdmin` runs `link` as written and is refuted, with a witness a JVM replays. The stub also
  names a nested parameter class as javac takes it (`a.b.Outer.Owner`, not `Outer$Owner`). A new case in
  `claims.Frames` (`Mentor#adopt(Honest mentee, …)`) is proved through its contract, with the contract among what it
  rests on. The fixture, its README and its JVM test are copied unchanged from `qmtxwupn`, and the README's
  `an_effect_contract_does_not_prove_a_call_a_jvm_breaks` is added to `lib/tests/effect_countermodels.rs`. Each of
  the three rules, switched off by mutation, makes a test fail. Not changed: a lemma (not an effect contract) may
  still read a final static an initializer computed (`claims.Effects#limit`). The challenge README names that as its
  item 3's hole, which is not in this inbox. A merge with the challenge line conflicts on the fixture and test files
  added on both: take this line's.
- 2026-11-17, step 3 begun: the observation binding taken, and the account of the binding path chosen (nothing of
  286 decided; the frozen claim unchanged). Inbox: nothing open. `lzpqszyo`'s binding is on this line, its files
  copied unchanged (`observed.rs`, `ObservedInitializer.java`, `ClassPath::refused` with `mqkqvvmw`'s
  `observed_countermodels.rs` and fixtures, `lib/README.md`'s paragraph), not merged: a merge would have this
  session's `sync.py` stamp the evidence line's commits of today. With it 286's probe ended before `bind`: the
  initialization of `CachedIntrospectionResults` initializes `ReflectionUtils`, and the binding took its
  `USER_DECLARED_METHODS` lambda for a write, since a JVM names a lambda's hidden class with an address that differs
  from run to run. The observer now names a hidden class by what it was defined from (`R$$Lambda`); `claims.Hooked`
  holds that (`tests/claims.rs`), and fails with the address kept. Sent `domain-advances-evidence-I009`, as their
  I008 work changes the same file. The probe (bound 2, a trial) then stops where it did, at `strongClassCache`.
  **The account chosen**, from 5.3.19's bytecode: below `forClass` the path is reflection and caches throughout:
  `strongClassCache` (a `ConcurrentHashMap`), `softClassCache` (Spring's `ConcurrentReferenceHashMap`: segments, locks,
  reference queues), `new CachedIntrospectionResults` (`Introspector`, the `BeanInfoFactory` list,
  `GenericTypeAwarePropertyDescriptor`s over `Method`s), the type descriptor cache (another
  `ConcurrentReferenceHashMap`; annotations read by reflection), some forty default editors made at the first
  conversion, `Method.invoke` of the getter (`extractOldValueForEditor`) and the setter, and for an unknown name
  `PropertyMatch` over `BeanUtils.getPropertyDescriptors`. Observing all of it (option 1) needs held objects of
  `java.beans` and `java.lang.reflect` classes, whose fields reflection does not read without opening `java.base`, and
  a model of each JDK call on them; a held empty `ConcurrentHashMap` alone only moves the stop to its `get`. So step
  3 takes option 2.
- 2026-11-17, a soundness fix to the gaps under assume (nothing of 286 decided; the frozen claim unchanged). Inbox:
  `domain-advances-state-I008` taken. The challenge stream's countermodels (`lqvlvwsm`, `wd.Widened`) showed that
  under `--gaps assume` the object a JDK call is taken to return was made of exactly the class its descriptor
  declares, so `HashSet.clone()` and `Date.clone()` (declared `Object`) were proved to return no `HashSet` and no
  `Date`; my I004 refusal compared the declared class for equality and so did not see it. The README's first option
  is taken, as it covers the I004 case too: the object is of the declared class only where that class is final, and
  otherwise of one at or below it that the engine does not know (`Obj::assumed`). A virtual call on it (an override
  may run), a throw of it, a cast, an `instanceof` or a lambda's argument cast the declared class does not settle,
  `sameClass`, and an effect contract's exact-class test are refused by name, while what the declared class settles
  is still proved. The fixture, its README and the JVM test are copied unchanged from `lqvlvwsm`; the README's
  `an_assumed_objects_class_is_not_taken_to_be_its_declared_one` is added to `lib/tests/rule_countermodels.rs`. A
  countermodel of my own, `claims.Cloned` (`tests/claims.rs`): `Object.clone()` of a class whose `toString` counts,
  then `toString()` on the copy, was proved to count nothing (an `Object.toString` gap assumed), where a JVM counts
  one. Both tests fail with the flag switched off (by mutation). `domain-advances-state-I009` noted, not obeyed: the
  frozen claim binds one property value, so the challenge stream's `controls/first-suppressed-only.patch` (only the
  first suppressed value removed) is accepted by it, whereas a JVM binds `Age=32` after `age=5`. A claim over two values is
  a new claim file, which is the user's decision. It goes into the corrected formalization this stream proposes (with
  the ASCII restriction on `field` from cycle 1), as "Done when" allows; the frozen claim is not edited.
- 2026-11-17, a soundness fix to the effect contract's proof (nothing of 286 decided; the frozen claim unchanged).
  Inbox: `domain-advances-state-I010` taken. The challenge stream's countermodels (`ukukylmu`, `cc.Held`) showed two
  callers proved through a proved contract where a JVM gives 0 for 5: the contract's proof exempted a final field of
  the receiver or an argument from the read gate, but it made those objects with their constructors in the harness's
  fresh state, and a caller's were made in its own (`final boolean locked = Config.locked`, read by `setLevel`; an
  argument's `final int scale`, read by `setFrom`). The README's first option is taken: inside an effect contract's
  proof a final field of an object that was there before the call is refused by name like any other field, which is
  what the contract's note and `summary.rs` already said it reads. The second option (keep the exemption for a field
  every constructor sets from its parameters alone) would need an analysis of the constructors and no setter the
  claim needs reads a final field. A lemma (not an effect contract) still reads final fields: its objects are the
  ones a static field leads to, the challenge README's item 3, not in this inbox. The fixture, its README and the JVM
  test are copied unchanged from `ukukylmu`; the README's
  `an_effect_contract_reads_no_final_field_a_caller_made_in_another_state` is added to
  `lib/tests/contract_countermodels.rs`, with the refusal also required to name the read. It fails with the refusal
  switched off (by mutation).
- 2026-11-17, the observation binding brought level with the evidence line (nothing of 286 decided; the frozen claim
  unchanged). Inbox: `domain-advances-state-I012` taken now rather than at a merge: `mmnoqopr`'s
  `lib/src/observed.rs`, `lib/src/observed/ObservedInitializer.java`, `lib/tests/observed_countermodels.rs` and
  `lib/README.md`'s observed-initializer paragraph are copied unchanged (they hold this line's `Dump.nameOf`; the
  other paragraphs of the README this line changed are kept; the `ob` fixtures were already here), and the cost
  inventory is regenerated. `domain-advances-state-I011` (the binding countermodels of `klqnuoxw`): the evidence
  stream lands the fix, as the binding is its own, its line merges first (D021) and its inbox carries the same item
  (`domain-advances-evidence-I011`); an item sent to it says so and that this line copies the fix whole, changing
  nothing in the binding meanwhile. Until then this line has the three false proofs the item names (none in an
  accepted result: 290's observed classes set no locale and write no other class's state). Step 3, from 5.3.19's
  bytecode: the binder's wrapper extracts the old value for the editor (`BeanPropertyBindingResult.createBeanWrapper`),
  so the getter runs before each write, and recording a `TypeMismatchException` (binding `"32"` to `someMap`) reads
  the property's type through the same reflection (`AbstractPropertyBindingResult.getFieldType`, `getPropertyType`),
  so a stand-in for `processLocalProperty` alone leaves that read on the real path: the stand-in has to answer the
  property's type too, or stand at `BeanWrapperImpl.getLocalPropertyHandler`.
- 2026-11-17, a soundness fix to the effect contract's stub (nothing of 286 decided; the frozen claim unchanged).
  Inbox: `domain-advances-state-I013` taken. The challenge stream's countermodels (`uqrzluvx`, `sc.Store`, `sc.Touch`)
  showed the stub's `effect` intrinsic put each written field into the object without asking `Engine::keeps`, the gate
  every `putfield` meets, so a proof by induction (`Store.f`, where a JVM gives `f(2) == -1`) and an empty write set
  (`Touch.touch`, which writes a static's bean) were proved through `sc.Bean#setLevel`'s contract. The README's first
  option is taken: each write of the stub now asks `keeps` before it is made, so both are refused for the same write
  as when the method runs as written. And the verdict now states a write set ("and writes nothing that was there before
  the call"), also where no field is left to read after the call. The fixture, its README and its JVM
  test are copied unchanged from `uqrzluvx`; the README's test is added to `lib/tests/effect_countermodels.rs`
  (`an_effect_contracts_writes_meet_the_induction_and_the_write_set`), also requiring the contract to be proved and
  the refusal to name the write. It fails with the gate removed (by mutation). No example rests on it (no example has
  `writes:`, and the one `decreases:` is a lemma whose proof takes no contract).
- 2026-11-17, the observation binding brought level with the evidence line again (nothing of 286 decided; the frozen
  claim unchanged). Inbox: `domain-advances-state-I014` taken, which also lands `domain-advances-state-I011`'s fix on
  this line: `vqquvmnm`'s `lib/src/observed.rs`, `lib/src/observed/ObservedInitializer.java` and
  `lib/tests/observed_countermodels.rs` are copied whole (they hold this line's `nameOf`), with the binding
  countermodels (`lib/tests/binding_countermodels.rs`, `fixtures/binding-countermodels`) and `lib/README.md`'s
  observed-initializer paragraph; the cost inventory is regenerated. The three false proofs of `klqnuoxw` are refused
  here too. **Where bind stops now** (capped probes at bound 2, trials): observing `CachedIntrospectionResults` is now
  refused before the run, since its initialization initializes `SpringFactoriesLoader`, whose `logger` holds a
  `java.util.logging.Logger` the observer does not describe (the stricter check is right: that logger is the JDK's
  shared one). Without that observation, `PropertyEditorRegistrySupport` is still observed and the run reaches
  `CachedIntrospectionResults.<clinit>` at `BeanWrapperImpl.getCachedIntrospectionResults:174`, beside the
  `toLowerCase()` gap of cycle 1. So step 3's stand-in should stand at `getLocalPropertyHandler` or above, where the
  introspection caches are off the path, and the driver then drops that observation.
- 2026-11-17, step 3, option 2: stand-ins sampled on a JVM (nothing of 286 decided; the frozen claim unchanged).
  Inbox: nothing open. **`prove --stand-in CLASS`** (`lib/src/stand_in.rs`, the call in `bmc::StandIn`): each public
  static method of the class but `main` stands in for an instance method. Its first parameter's class is the exact
  class of the receivers it covers, and the rest of its descriptor is the method's, which that class declares or
  inherits. A call resolving to that method on a receiver of exactly that class runs the stand-in. A subclass's
  receiver, and the stand-in's own calls, run the method as written, so a stand-in hands back what it does not cover.
  Its `main` samples it against the method (`sample<TAB>input<TAB>method's outcome<TAB>stand-in's outcome`). The
  tool runs that `main` first, on the check's class path, and takes the stand-in only if every sample is the same.
  A result that used it says so among what it rests on: sampled, not proved. Refused: JBMC and `--cache`.
  - Fixture `lib/tests/fixtures/stand-ins` (a reflective property writer); tests in `lib/tests/stand_in.rs`.
    With the stand-in a claim the method leaves undecided is proved and names the stand-in, and a refutation
    replays on a JVM. A subclass's receiver, and a bean the stand-in hands back, stop at the method's gap as without
    it. A stand-in that forgets `Age`, one that samples nothing, and one with a public helper are refused.
  - With the exact-receiver check or the sample comparison switched off (by mutation), a test fails.
  - 286's stand-in is drafted, not committed: `org.springframework.beans.ProtectedBeanStandIn`, for
    `setPropertyValue(PropertyValue)` on a `BeanWrapperImpl` of exactly a `ProtectedBean`. It covers the six
    properties' lookup (exact, uncapitalized, capitalized), the getter, `NumberUtils.parseNumber` for `age`, and the
    mismatch exceptions; anything else goes back to the method.
  - Sampled against 5.3.19: 38,400 samples, all the same. These cover names (case variants, every name of at most 2
    units over 12 letters, 200 random, some non-ASCII), 12 values, and the extract, suppress and optional flags.
- 2026-11-17, step 3 wired into 286 and step 2 reached: the refutation on the real binder (frozen claim unchanged;
  nothing accepted yet). Inbox: nothing open.
  - **The driver.** The stand-in is `proofs/stand-ins/org/springframework/beans/ProtectedBeanStandIn.java`. The driver
    compiles it against the release beside the adapter and passes `--stand-in`. Its source and classes are recorded
    among the adapter's in `evidence.json`, which `accept.py` compares with the job's commit, so `target.json`'s
    adapter set is unchanged. `CachedIntrospectionResults` is no longer observed.
  - **The stand-in, revised.** The lookup needs no case tables: of the 65,536 chars, only `A` to `Z` lower-case to a
    property's first unit, and none upper-cases to one. The sampler now sweeps every char as the first unit. `age`
    converts by `Integer.parseInt` only for an optional sign and 1 to 9 ASCII digits. Every other text, and every
    other hand-back, goes to the method before the stand-in changes anything. 463,616 samples, all the same on
    5.3.19; with ten digits allowed (by mutation), 16 differ.
  - **Two JDK steps the path needed.** The `ArrayList` model keeps `remove(Object)`, which `checkAllowedFields` uses
    to drop a disallowed value. It is checked by `claims.M#removed`, sampled on a JVM, and refuted with its `modCount`
    change removed. `Boolean.TRUE` and `Boolean.FALSE` are one object each, written to `conversionNecessary`; a call
    on one stays the JDK's (`claims.M#truths`, `#truthTold`).
  - **Probes** (inline, capped):
    - `vulnerable-protected-state-mutation` is **refuted at the claim's bound 8** in 63 s:
      `ageAfterBinding(false, "Age")` returns 32, run on a JVM, so the refutation rests on no stand-in or model.
    - `fixed-protected-state-mutation` stops only at non-ASCII `toLowerCase()` (`isAllowed:828`).
    - With `field` also ASCII (not the frozen claim), the next stop at bound 7 is `PropertyChangeEvent.<init>` on the
      `someMap` mismatch path.
  - Job `20261117-181750-example-286-protected-state-tasks-at-the` runs both tasks at bound 8: the refutation for
    `accept.py`, and the fixed task's blocker for the record.
- 2026-11-17, step 3 continued: the `someMap` mismatch path, begun (frozen claim unchanged; nothing accepted yet).
  Inbox: nothing open. Job 181750 has no result yet.
  - **A model on request of `java.beans.PropertyChangeEvent`** (`--model java.beans.PropertyChangeEvent`; it also
    runs the model of `java.util.EventObject` above it, `models::COMPANIONS`). The model is the event's fields,
    getters and the null source's `IllegalArgumentException`. Fixture `claims.Events`: proved with the model,
    sampled on a JVM, and with a getter mutated no longer proved.
  - **`ClassUtils.getDescriptiveType`'s class facts** (`bmc/runtime.rs`): `Object.getClass()` of a String,
    `Class.getTypeName()` of a class literal that is no array, and `Proxy.isProxyClass` of a class literal (false).
    `claims.M#typed` and `#unproxied` are proved and sampled.
  - **A second stand-in**, `ProtectedBeanTypeStandIn.getPropertyType`, for the property type the binding result
    asks when it records an error. It covers every property but `age`, whose `int.class` is `Integer.TYPE`, and gives
    null for other simple names. 397,649 samples, all equal on 5.3.19; with one type mutated, 4 differ.
    - It is a class of its own because `accept.py` compares `ProtectedBeanStandIn.java` with what job 181750
      compiled.
  - **The driver** runs the protected-state tasks with the model, `ClassUtils` observed, and both stand-ins.
    5.3.18 is still refuted (a trial at bound 3).
  - **Where the path stops now.** Probe with `field` restricted to `someMap` and `SomeMap`: at
    `LinkedHashSet.<init>()` in `DefaultMessageCodesResolver.resolveMessageCodes:152`.
  - **Tried and dropped:** extending the "unwritten model fields" refusal to JDK classes below a model. A call on an
    `IndexedPropertyChangeEvent` meets the JDK gap, not the model, so there was no hole to close.
- 2026-11-17, job 181750's failure fixed and the job run again (frozen claim unchanged; nothing accepted yet). Inbox:
  `domain-advances-state-I015` and `domain-advances-state-I016` (its correction) taken.
  - **The failure.** Job 181750 stopped before the check: with a relative `--work`, the observer's JVM ran in
    `observed/` and was given a relative `-Xlog` file (and log argument), so it refused the option.
  - **The fix.** `observed::observe` now makes its folder absolute (`std::path::absolute`), so the log, the
    `-Xlog` option and the observer's argument are absolute.
  - **The test.** `an_observed_initializer_is_observed_with_a_relative_work_folder` (`lib/tests/claims.rs`) runs
    the CLI from another directory with `--work work/observed`. Before the fix it failed with the job's "Invalid -Xlog
    option"; now it proves `claims.M#observed` and leaves the log in the work folder.
  - **The driver.** A capped probe with a relative `--work` refutes the vulnerable task at a trial bound 3.
  - **The job.** Job `20261117-192205-example-286-protected-state-tasks-at-the` runs both tasks at bound 8 with 2
    CPUs, through the driver as it now is (with the `PropertyChangeEvent` model, `ClassUtils` observed and both
    stand-ins). `ProtectedBeanStandIn.java` is unchanged, as `accept.py` compares it.
- 2026-11-17, step 3 continued: the mismatch path through the message codes (frozen claim unchanged; nothing
  accepted yet). Inbox: nothing open. Job 192205 has no result yet.
  - **`java.util.LinkedHashSet`, a model on request** (`--model java.util.LinkedHashSet`). It is the `HashSet` model
    with its elements in the order first added: `add`, `toArray()` and `toArray(T[])`. A check that asks for it also
    runs the `HashSet` model, as if asked (`models::BRINGS`; `models::requested` now gives each model a request
    runs), and the result names both.
  - **`java.util.StringJoiner`, a model on request** (`--model java.util.StringJoiner`): `add` and `toString`. The
    JDK's join is always a new String, but the checker's builder gives the literal `""` when empty, so an empty
    result is the JDK's `new String()`, a gap.
  - Each model's fixture (`claims.LinkedSets`, `claims.Joiners`) is proved with the model against its definition,
    sampled on a JVM, and shows a left-out method still the JDK's.
    - Mutations, each failing the test: no null after the elements (the test now pre-fills the given array, after the
      first version let it pass), reversed order, no delimiter, `""` for an empty join, `"nul"` for null.
  - **`String.lastIndexOf(int)`** (`bmc/strings.rs`, `index_of_unit`'s test at every index, the last hit kept):
    `claims.T#lastIndexOfPoint` is proved; with the first hit taken (by mutation) it is not. Its evidence record
    (`values::OPERATIONS`, ten boundary cases in `tests/values.rs`) gives one outcome on the JVM, in the interpreter
    and in the checker.
  - **`Class.isArray()` of a class literal** (`bmc/runtime.rs`): `claims.Arrayed`.
  - **A fix found on the way:** a `Class` method of a primitive result on a class the engine holds no literal of
    (`isAssignableFrom`, now `isArray`) was met under `--gaps assume` as an assumable reference gap that pushed no
    value: "operand stack underflow", no verdict.
    - It is now a primitive gap, refused by name in both modes (`mod.rs`, the class-method fallback).
    - The test requires the name and fails with the old kind (by mutation). It was never a false verdict.
  - **The driver** runs the protected-state tasks with both new models; 5.3.18 is still refuted (a trial at bound 3).
  - The new tests run their JVMs with `-XX:-UsePerfData`: in a parallel run a JVM printed an hsperfdata warning to
    stdout, and the sampled "ok" was missed.
  - **Where the path stops now** (capped probe, `field` restricted to `someMap`/`SomeMap`, bound 7):
    `resolveMessageCodes` runs to its end, and the next stop is `PropertyAccessException.getLocalizedMessage()` in
    `DefaultBindingErrorProcessor.processPropertyAccessException:79`, the error's default message.
- 2026-11-17, step 2 done: the refutation accepted (the frozen claim is the accepted statement for 5.3.18). Inbox:
  nothing open.
  - **Job 192205 passed.** `vulnerable-protected-state-mutation` is refuted at the claim's own bound 8.
    - The witness: `ageAfterBinding(false, "Age")` returns 32 on a JVM.
    - So the refutation rests on none of the models, observed initializers or stand-ins the run used.
  - **Recorded and accepted.** The task's `besideRoute` is in 286's `target.json`, and `accept.py 286
    vulnerable-protected-state-mutation` accepts it with 12 checks, every one ok.
  - **The job's files on this line.** `accept.py` reads the job's result and outputs from the checkout. The result
    collector's commit (`lsuuqtnq`) is not on this line, so its result folder and `verification/.work-286/state-stand-in/`
    are restored from it unchanged (`jj restore --from`). A merge adds the same bytes on both sides.
  - **The fixed task in the same job:** no verdict, at two strict gaps.
    - `LinkedHashSet.<init>()` (since modelled, cycle 18).
    - Non-ASCII `toLowerCase()` (`isAllowed:828`).
  - **The example.** The README's table row, a paragraph under the decision claim's results, the open item, the
    verdict label (the router regenerated) and a note.
  - `validate_example 286` and `run --changed` (26 of 26) pass.
  - `mutant-security` is still not accepted, as before: its driver recorded no mutant JAR hash. That is the evidence
    stream's.
  - **What the acceptance pins.** `accept.py` compares the tree's files with the job:
    - target.json's adapter set, with the commit the job ran;
    - every source in `evidence.json` (the adapter and both stand-ins), by hash.
    - So changing any of them, or adding a bean to the adapter set, un-accepts the refutation until the task runs
      again. Step 5's beans go beside them, in files of their own.
- 2026-11-17, step 3: the mismatch path to its end, and the fixed task proved over ASCII names in a probe (frozen
  claim unchanged; nothing newly accepted). Inbox: nothing open.
  - **An exception's message and cause** (`lib/src/bmc/throwables.rs`). The own checker keeps what a JDK
    exception's constructor sets: `()`, `(String)` and `(String, Throwable)`. On such an exception it models
    `Throwable`'s `getMessage`, `getCause`, `getLocalizedMessage` and `toString`, where the method the JVM runs is
    `Throwable`'s own. `getLocalizedMessage` runs an application's `getMessage` in its place, as Spring's
    `NestedRuntimeException` needs.
    - Also modelled: `getClass()` of a JDK exception no JDK call returned, and the builder's `StringBuilder(int)` (a
      constant capacity) and `append(Object)` (a String, null, or such an exception).
    - A read of the kept message goes through the effect contract's read gate, like a field's.
  - **Two holes closed, each a false proof before.**
    - A JDK exception's constructor was exact whatever its code. It is now exact only where its bytecode just
      passes its arguments up to `Throwable`'s (`plain_constructor`; JDK 25's flight-recorder hook in `Error`'s is
      allowed). `UnknownFormatConversionException(null)` throws on a JVM, and is now a gap.
    - An application's `fillInStackTrace()` override runs inside `Throwable`'s constructor. That constructor is now
      refused by name.
    - Without a JDK image, `jdk_facts` lists the plain constructors. A unit test checks that list against the
      image.
  - **The concatenation cap is 256 code units** (was 64): `TypeMismatchException`'s message is about 150.
    `values.rs`'s cap test moved with it: 72 units proved, 261 a named limit.
  - **Tests.**
    - `claims.Thrown` (`an_exceptions_message_and_cause_are_kept_from_the_jdks_constructor`): four statements
      proved and true on a JVM. Four cases a JVM breaks stay unverifiable by name.
    - Each of five mutations makes a test fail: no `fillInStackTrace` refusal, the old exact rule, the `toString`
      override ignored, no cause sentinel, the JFR hook refused.
    - `run --changed`: 23 of 23 pass. The first run caught the engine's unit tests, whose class path has no JDK
      image; the built-in facts fixed that.
  - **Where the path is now** (capped probes):
    - with `field` restricted to `someMap`/`SomeMap`, bound 7: proved (113 s);
    - with `field` ASCII (I009's other half aside), bound 7, through `prove.py`: **proved** in 108 s.
      - It rests on the five models, both stand-ins (sampled), `PropertyEditorRegistrySupport` and `ClassUtils`
        observed, the locale assumption and the `simpleMatch` lemma.
    - the frozen claim's whole domain at bound 8: past the 5-minute cap, so a job.
  - **The driver.** `prove.py --assume-also EXPR` conjoins EXPR to the claim's assumption as a trial. Its record
    says so, and `accept.py` refuses its answer, since the assumption is not the claim file's.
    - `accept.py` reads the driver at the job's commit, so the accepted refutation stands.
  - **Job `20261117-222610-example-286-s-fixed-protected-state-task`**, each step with a work folder of its own:
    - the frozen claim at bound 8, expected to stop only at non-ASCII `toLowerCase()`;
    - the ASCII trial at bound 8, expected proved.
- 2026-11-17, a soundness fix to lemmas proved through a stand-in (nothing of 286 decided; the frozen claim
  unchanged). Inbox: `domain-advances-state-I017` taken, the README's first option.
  - **The hole.** A check that used a lemma (or an effect contract) stated it as `proved` and nothing of what its
    proof rested on. `sn.Use#viaLemma` was proved through a lemma whose proof took a narrow stand-in, with no word of
    the stand-in, where a JVM gives 32.
  - **The fix.** `property.rs`'s lemma loop now carries each lemma's and effect contract's engine, gap and contract
    assumptions into the using check's statement, each marked "(what the proof of the lemma about X rested on)",
    where the check's own run does not state it already. It also adds a text note.
  - **Tests.**
    - The fixture, its README and the JVM test are copied unchanged from `mnwtrnrp`.
    - The README's test `a_check_through_a_lemma_states_the_stand_in_the_lemmas_proof_rested_on` is added to
      `lib/tests/stand_in.rs`. It also requires the lemma's name and the text note.
    - It fails with the carry-over switched off (by mutation).
  - **The audit holds.** 286's `simpleMatch` lemma calls only String methods, so its statements lose nothing.
- Next:
  - Step 5: the adversarial and honest beans beside `ProtectedBean`, in files of their own, and the
    application-level refutation through `displayName`. The adapter set and the stand-in sources stay as they are,
    or the acceptance breaks. Then the effect contract at the stand-in's setter call.
  - Job 222610's result: record the fixed task's blocker under the frozen claim, and the ASCII trial.
  - Still open from cycle 1:
    - non-ASCII `toLowerCase()`, the fixed task's one blocker under the frozen claim;
    - the corrected formalization: I009's two values and an ASCII `field`. It is a new claim file, the user's
      decision; the trial is its evidence.
- Status: working

## Loop settings

- session: 9896d870-fb47-4f3c-ba4d-5b1d3e64719c
- model: claude-opus-5-5
- effort: high
- workspace: domain-advances-state

## Loop until

Steps 1 to 5 first, then 6 while a cycle can still realize a substantial part of it. Stop with `waiting on jobs ID
...` when what is left waits on jobs, `done` when the criteria are met or recorded as the brief allows, `blocked:
...` when the next step is the user's. Keep the last line of Progress a status.

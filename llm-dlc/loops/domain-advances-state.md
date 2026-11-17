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
- Next: step 3: how bind resolves a property name to its write method. That means taking `lzpqszyo` into this line,
  a held kind for `CachedIntrospectionResults`' empty `strongClassCache` (an `Object` variant, printed
  deterministically by the observer's `Dump.value`), then observing a bean's property descriptors, or an
  introspection contract sampled on a JVM, and the effect contract applied at `Method.invoke` of the resolved setter. Then the adversarial bean and twin beside `ProtectedBean` (when the evidence
  stream's 286 jobs no longer hang on the adapter set) and the app-level refutation through `displayName` on the real
  binder. Still open from cycle 1: non-ASCII `toLowerCase()` (a Unicode lowering model or an ASCII claim for the
  user).
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

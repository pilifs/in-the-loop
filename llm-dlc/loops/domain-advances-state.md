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
- Next: step 3 needs the evidence stream's answer on `observed.rs`; meanwhile steps 4 and 5, which do not need the
  binding path: the adversarial bean beside `ProtectedBean` (a `setDisplayName` that writes `isAdmin`) and its honest
  twin, and a first effect contract stated over a method (a write set, its frame and the rest of step 4) that the
  checker establishes on the honest setter and refutes on the adversarial one, generalizing `Engine::keeps`. Then step
  3's form: an introspection contract (name to write method for the bean, sampled on a JVM) and an effect contract at
  the property accessor, likely a smaller account than running `Introspector`, `Method.invoke` and the default
  editors. Still open from cycle 1: non-ASCII `toLowerCase()` (a Unicode lowering model or an ASCII claim for the
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

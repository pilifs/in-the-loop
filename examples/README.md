# Examples

> **Start with examples 034 to 056** if you work on the JVM itself or on the libraries closest to it, **023 to 033** if you build services on Spring Boot, or **013 to 022** if you build the replicated systems under them, then 006 to 012. Examples 001 to 005 were created by Opus 5.5, the rest by Fable 5.1.
> The later examples go significantly beyond what can be achieved with type checking.

Each example is one code change to a subject system, run through a formal verifier, with the verdict and why it matters.
Together they show what verification catches that code review and tests miss, and what it lets through.
None of it needs the reader to write a specification: each verifier derives its statement from the code, the types, the previous version, or a one-line property committed next to the code.

There are four subject systems. [Box Office](apps/boxoffice/README.md) (examples 001 to 012) is a ticketing system of two Spring Boot services over Kafka, verified by the Java proof of concept in [`tools/contracts`](tools/contracts/README.md).
[Quorum](apps/quorum/README.md) (examples 013 to 022) is a library of the pure decision kernels a replicated system is built from, Raft's vote rule and role machine, quorum arithmetic, backoff, a hybrid logical clock, last-writer-wins resolution and a two-phase-commit coordinator.
[Crosscut](apps/crosscut/README.md) (examples 023 to 033) is the kernels behind the cross-cutting concerns of a Spring Boot service: the transaction interceptor's rollback rule, a circuit breaker, a retry policy, a rate limiter, an `Idempotency-Key` receiver, a Kafka partitioner and batch commit, a JWT validator's clock skew and a cache's expiry.
[Mica](apps/mica/README.md) (examples 034 to 056) is the decision kernels of a small JVM written in Java: the class initialization procedure of JVMS §5.5, the type checker's assignability relation, access control, `idiv` and `fcmp` with their corner cases, a `lookupswitch` bisection and the sort of its pairs, the exception table's handler lookup and its well-formedness check, the stack map frame offsets, the length of a `Code` attribute, constant pool numbering, `max_stack`, javac's switch heuristic, a power-of-two table size and the modified UTF-8 of the constant pool.
The three are verified by [`jvmcontract`](../lib/README.md), the Rust tool, with no JVM in the loop: a bytecode interpreter checking the kernels of a bytecode interpreter.
One proof is unfinished: [a regression proof of `ModifiedUtf8#encodeInto`](apps/mica/pending/README.md) is proved up to 4 characters, and needs a machine with more memory at the default of 8.

The examples use five approaches, numbered as in [`approaches.md`](approaches.md). The common principle is that a checked-in artifact may change only where the developer intends a change, and the diff of that artifact is what the reviewer approves.

| Approach | What is checked | How it is proved | Examples |
|---|---|---|---|
| [B8 Behavioural contracts](tools/contracts/README.md) | A method's outcome on every input of a finite domain | Purity proved from bytecode, then every input executed | 001 to 005, 014, 025, 026, 038 to 040 |
| [B9 Regression verification](tools/contracts/README.md#regression-verification-methods-with-unbounded-inputs) | A method with unbounded inputs behaves as its previous version, outside the inputs the developer declared as changed | Both versions compiled into one program; JBMC proves the statement or finds a counterexample, replayed on the JVM | 006 to 008, 013, 027, 035 to 037 |
| [B10 Capability contracts](tools/contracts/README.md#capability-contracts-what-a-module-can-do) | What a module's bytecode can reach: the clock, the network, randomness, reflection, class loading, threads, ... | Closed-world inspection of every call site in the compiled classes | 009, 010, 019, 028, 041 |
| [B11 Property proofs](../lib/README.md#how-a-property-proof-works) | A property the developer states about a method, on every input: a postcondition, or a law such as commutativity | A generated harness assumes, calls and asserts; JBMC proves it or finds an input, which the tool shrinks and replays; arrays are quantified over with JML's `\forall`, `\exists`, `\sum`, `\num_of`, `\max` and `\min`; a throws clause (JML's `signals`) brings the exceptional path under the proof; `\old` reads an array as the call received it | 015 to 018, 022 to 024, 031 to 034, 044 to 056 |
| [D1 Protocol model checking](apps/boxoffice/spec/README.md) | The safety invariants of a protocol over every interleaving within bounds, and freedom from deadlock | TLC explores the state space of a TLA+ model whose state machine is generated from the B8 contract | 011, 012, 020, 021, 029, 030, 042, 043 |

A type system could do some of what 001 to 005 do. It could not find a one-cent rounding drift across 2^96 inputs (006), prove that a pricing change touches only the groups it says it touches (007), notice that a codec started loading classes named by Kafka messages (009), or produce the nine-step interleaving in which a paid customer loses their seat and their refund (011).
Nor could it tell that a Raft vote rule rewritten as "longest log wins" will elect a leader that overwrites committed entries (013), that `(n + 1) / 2` is not a majority (015), that a hybrid logical clock with one branch folded away hands out a timestamp older than the message it just received (018), or that a two-phase-commit coordinator which presumes commit on timeout commits over a participant's no vote that is still in flight (020).
Nor that a transaction rollback rule rewritten as "a RuntimeException rolls back" commits after an `OutOfMemoryError` (025), that a switch rewrite of a retry policy stops retrying the 5xx statuses it did not name (027), that an idempotency key which runs a retry while the first attempt is in flight executes the request twice (029), or that a Kafka partitioner written with `Math.abs` sends one key in two billion to a negative partition (023).
Nor that a verifier which answers "everything is an `Object`" one line too early lets an uninitialized object through (038), that a NaN check written as `== Float.NaN` turns `fcmpl` into `fcmpg` (035), that an `idiv` with an overflow check throws where the specification says to return `Integer.MIN_VALUE` (034), or that a class initialization with one rule for every requester deadlocks on its own thread (043).
Nor that a rewritten binary search still finds every key in every sorted table (046), that an exception table whose `end_pc` is read as inclusive hands an exception to the wrong handler (047), or that a constant-pool encoder which writes supplementary characters in four bytes produces a class no JVM will load (048).
Nor that a stack map offset loop with its first-frame special case removed still places every frame (049), that a `Code` attribute length which leaves out its nested attributes' headers is six bytes short per attribute (050), that a constant-pool numbering which counts the `long` entry itself points one past it (051), or that `max_stack` is still the deepest point when the depth is checked only after a push (052), the refutations shrunk to a witness of one element.
Nor that an `idiv` which leaves division by zero to the host throws exactly where the check it removed did (053), or that a class file check which compares `end_pc` like the other offsets rejects every handler that covers the last instruction of a method (054), both on the exceptional path a throws clause brings under the proof.
Nor that an encoder which zero-terminates the string into the caller's buffer overwrites a byte past what it returns (055), or that a `lookupswitch` pair sort which compares keys by difference swaps two keys just over 2^31 apart (056), the first against a frame condition and the second against a permutation, both stated with JML's `\old`.

<!-- examples:begin (generated by examples/tools/build.py) -->
| # | Example | Approach | Verdict | Existing tests | Categories | Severity if shipped | Change |
|---|---|---|---|---|---|---|---|
| 001 | [A switch cleanup that keeps the money for declined orders](001-merged-case-keeps-money/README.md) | B8 | ✗ Violation: 2 of 36 cases changed | caught | functional | high | cleanup |
| 002 | [A refactor believed equivalent that changes null handling](002-equality-refactor-changes-null-handling/README.md) | B8 | ✗ Violation: 1 of 36 cases changed | **missed** | functional, compatibility | medium | refactor |
| 003 | [Logging a timestamp makes the decision unverifiable](003-timestamp-makes-decision-nondeterministic/README.md) | B8 | ⚠ Unverifiable | **missed** | determinism | medium | logging |
| 004 | [An equivalent refactor passes without touching the contract](004-equivalent-refactor-passes/README.md) | B8 | ✓ Verified: all 36 cases match | pass | no-false-positive | none | refactor |
| 005 | [An intended change, reviewed as a one-line contract diff](005-intended-change-reviewed-as-contract-diff/README.md) | B8 | ✓ Verified: all 36 cases match | pass | functional | none | feature |
| 006 | [A per-seat discount that rounds differently from the per-total one](006-per-seat-discount-rounds-differently/README.md) | B9 | ✗ Violation: counterexample found | **missed** | functional | medium | refactor |
| 007 | [A doubled group discount, proved to change only groups](007-doubled-group-discount-proved-confined/README.md) | B9 | ✓ Verified: equivalent on every input outside the declared change | pass | functional, no-false-positive | none | feature |
| 008 | [A new tier, written as one formula, also changes groups of six and seven](008-percentage-rewrite-leaks-outside-new-tier/README.md) | B9 | ✗ Violation: counterexample found | **missed** | functional | medium | feature |
| 009 | [A codec that loads whatever class a Kafka message names](009-codec-loads-classes-named-by-payload/README.md) | B10 | ✗ Violation: 1 capability change | **missed** | security | critical | feature |
| 010 | [A codec setting that changes payloads but not what the module can do](010-sorted-payload-keeps-capabilities/README.md) | B10 | ✓ Verified: capabilities unchanged | pass | no-false-positive | none | configuration |
| 011 | [Skipping one query in a Kafka listener strands a customer's money](011-skipped-seat-check-strands-the-money/README.md) | D1 | ✗ Violation: NoMoneyStranded, 9-step trace | **missed** | functional | high | refactor |
| 012 | [Deleting the hold sweeper, proved safe for every interleaving](012-deleting-the-sweeper-is-safe/README.md) | D1 | ✓ Verified: all invariants hold in 3,604 states | pass | no-false-positive | none | cleanup |
| 013 | [A "longest log wins" vote rule lets a Raft leader overwrite committed entries](013-longest-log-wins-breaks-election-safety/README.md) | B9 | ✗ Violation: counterexample found | **missed** | functional | critical | refactor |
| 014 | [A leader that ignores newer terms in replies keeps serving a term the cluster has left](014-leader-that-ignores-newer-terms-in-replies/README.md) | B8 | ✗ Violation: 1 of 52 cases changed | **missed** | functional | high | refactor |
| 015 | [A majority rewritten as "half, rounded up" lets two quorums miss each other](015-rounded-half-is-not-a-majority/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional | critical | cleanup |
| 016 | [A backoff cleanup that removes the overflow guard turns the delay negative](016-backoff-cleanup-overflows-into-a-negative-delay/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional | high | cleanup |
| 017 | [A hybrid logical clock rewritten with max(), proved to never go backwards on any input](017-hybrid-logical-clock-refactor-proved-monotonic/README.md) | B11 | ✓ Verified: property holds on every input | pass | functional, no-false-positive | none | refactor |
| 018 | [A hybrid logical clock that drops one case stamps a receive before the message](018-hybrid-logical-clock-that-goes-backwards/README.md) | B11 | ✗ Violation: counterexample found | caught | functional | critical | refactor |
| 019 | [Adding jitter inside the backoff kernel gives a pure module a random number generator](019-jitter-makes-the-kernel-unsimulatable/README.md) | B10 | ✗ Violation: 2 capability changes | **missed** | determinism, functional | high | feature |
| 020 | [A 2PC coordinator that presumes commit on timeout splits the participants](020-coordinator-that-presumes-commit-on-timeout/README.md) | D1 | ✗ Violation: Atomicity, 3-step trace | **missed** | functional | critical | feature |
| 021 | [Aborting on the first no vote, proved safe for every interleaving of three participants](021-aborting-on-the-first-no-proved-safe/README.md) | D1 | ✓ Verified: all invariants hold in 644 states | pass | functional, no-false-positive | none | feature |
| 022 | [A skew-tolerant tie-break for last-writer-wins lets replicas keep different values](022-skew-tolerant-tie-break-splits-the-replicas/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional | high | feature |
| 023 | [A partitioner written with Math.abs sends one key in two billion to a negative partition](023-abs-partitioner-sends-one-key-to-a-negative-partition/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional | high | cleanup |
| 024 | [A JWT validator that applies clock skew on the wrong side rejects fresh tokens](024-clock-skew-applied-on-the-wrong-side-of-not-before/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional, security | high | bug-fix |
| 025 | [A rollback rule rewritten as "unchecked means RuntimeException" commits after an Error](025-transaction-that-commits-after-an-error/README.md) | B8 | ✗ Violation: 1 of 22 cases changed | **missed** | functional | high | refactor |
| 026 | [A half-open circuit breaker that closes on the first good probe flaps through an outage](026-half-open-breaker-that-closes-on-the-first-good-probe/README.md) | B8 | ✗ Violation: 2 of 44 cases changed | **missed** | functional, performance | high | feature |
| 027 | [A switch rewrite of the retry policy stops retrying the 5xx statuses it did not list](027-switch-rewrite-of-the-retry-policy-drops-the-unlisted-5xx/README.md) | B9 | ✗ Violation: counterexample found | **missed** | functional | medium | refactor |
| 028 | [A retry helper that sleeps out the Retry-After delay gives a pure module a thread call](028-retry-that-sleeps-on-the-caller-thread/README.md) | B10 | ✗ Violation: 2 capability changes | **missed** | performance, determinism | high | feature |
| 029 | [An idempotency key that executes a retry while the first attempt is in flight pays twice](029-retry-in-progress-executes-twice/README.md) | D1 | ✗ Violation: OneExecutionAtATime, 5-step trace | **missed** | functional | critical | bug-fix |
| 030 | [Storing a failed attempt's response under its key, proved at-most-once for every retry](030-stored-failures-proved-at-most-once/README.md) | D1 | ✓ Verified: all invariants hold in 131 states | pass | functional, no-false-positive | none | feature |
| 031 | [A token bucket that stamps each refill with "now" never refills under steady traffic](031-rate-limiter-that-never-refills-under-steady-polling/README.md) | B11 | ✗ Violation: counterexample found | caught | functional | high | cleanup |
| 032 | [A batch listener that commits the whole batch after a failed record loses the rest of it](032-batch-listener-that-commits-past-a-failed-record/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional | critical | bug-fix |
| 033 | [A cache expiry rewritten as a stored deadline, proved on every nanosecond and the sentinel](033-cache-expiry-as-a-deadline-proved-on-every-nanosecond/README.md) | B11 | ✓ Verified: property holds on every input | pass | functional, no-false-positive | none | refactor |
| 034 | [An idiv that throws on Integer.MIN_VALUE / -1, where the JVM must return the dividend](034-idiv-overflow-check-throws-where-the-jvm-returns-min-value/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional, compatibility | high | bug-fix |
| 035 | [A NaN check written as == Float.NaN never fires, and fcmpl quietly becomes fcmpg](035-nan-compared-with-equals-turns-fcmpl-into-fcmpg/README.md) | B9 | ✗ Violation: counterexample found | **missed** | functional | high | cleanup |
| 036 | [Switch lowering costs computed in int pick the wrong instruction for wide labels](036-switch-lowering-costs-in-int-overflow-on-wide-labels/README.md) | B9 | ✗ Violation: counterexample found | **missed** | functional, performance | medium | cleanup |
| 037 | [tableSizeFor rewritten with numberOfLeadingZeros, proved equal on all 2^32 inputs](037-table-size-rewritten-with-leading-zeros-proved-equal/README.md) | B9 | ✓ Verified: equivalent on every input | pass | functional, no-false-positive | none | refactor |
| 038 | [A verifier fast path for "everything is an Object" lets an uninitialized object pass](038-verifier-object-fast-path-accepts-uninitialized-objects/README.md) | B8 | ✗ Violation: 2 of 289 cases changed | **missed** | security, functional | critical | refactor |
| 039 | [Protected access without the receiver rule opens every superclass object to a subclass](039-protected-access-without-the-receiver-rule/README.md) | B8 | ✗ Violation: 1 of 120 cases changed | **missed** | security, functional | critical | cleanup |
| 040 | [Nest-based private access (JEP 181), reviewed as four lines of a 120-line contract](040-nestmate-private-access-reviewed-as-a-contract-diff/README.md) | B8 | ✓ Verified: all 120 cases match | pass | functional, no-false-positive | none | feature |
| 041 | [Looking up StrictMath intrinsics by name on the host gives a pure interpreter reflection](041-math-intrinsics-through-method-handles-give-the-interpreter-reflection/README.md) | B10 | ✗ Violation: 2 capability changes | **missed** | security, determinism | high | feature |
| 042 | [Letting other threads proceed while <clinit> runs hands out a half-built class](042-class-init-that-proceeds-while-another-thread-initializes/README.md) | D1 | ✗ Violation: UsedOnlyWhenInitialized, 3-step trace | **missed** | functional | critical | bug-fix |
| 043 | [One rule for every class-init request waits on its own thread, and TLC finds the deadlock](043-class-init-that-waits-on-its-own-thread-deadlocks/README.md) | D1 | ✗ Violation: deadlock, 5-step trace | **missed** | functional | critical | cleanup |
| 044 | [A constant-pool encoder that writes NUL as one byte emits the byte no class file may hold](044-modified-utf8-with-a-one-byte-nul/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional, compatibility | high | bug-fix |
| 045 | [A bisection midpoint written as (low + high) / 2, proved safe for every lookupswitch index](045-lookupswitch-midpoint-by-division-proved-safe-within-a-code-attribute/README.md) | B11 | ✓ Verified: property holds on every input | pass | functional, no-false-positive | none | refactor |
| 046 | [A lookupswitch bisection rewritten half-open, proved to find every key in a sorted table](046-lookupswitch-bisection-rewritten-half-open-proved-to-find-every-key/README.md) | B11 | ✓ Verified: property holds on every input | pass | functional, no-false-positive | none | refactor |
| 047 | [An exception table read with an inclusive end_pc hands an exception to the wrong handler](047-exception-table-with-an-inclusive-end-pc/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional, compatibility | high | cleanup |
| 048 | [A constant-pool encoder that writes supplementary characters in four bytes, as UTF-8 does](048-constant-pool-encoder-that-writes-supplementary-characters-in-four-bytes/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional, compatibility | high | bug-fix |
| 049 | [A stack map offset loop without the first-frame special case, proved to place every frame](049-stack-map-offset-loop-without-the-first-frame-special-case/README.md) | B11 | ✓ Verified: property holds on every input | pass | functional, no-false-positive | none | refactor |
| 050 | [A Code attribute length that omits the nested attributes' headers truncates the method](050-code-attribute-length-that-leaves-out-the-nested-attribute-headers/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional, compatibility | high | cleanup |
| 051 | [A constant-pool index that counts the long entry itself points one past the entry](051-constant-pool-index-that-counts-the-long-entry-itself/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional | high | refactor |
| 052 | [A max_stack that checks the depth only after a push, proved to find the deepest point](052-max-stack-that-checks-the-depth-only-after-a-push/README.md) | B11 | ✓ Verified: property holds on every input | pass | functional, performance, no-false-positive | none | refactor |
| 053 | [An idiv that leaves division by zero to the host, proved to throw exactly there](053-idiv-that-leaves-division-by-zero-to-the-host/README.md) | B11 | ✓ Verified: property holds on every input | pass | functional, no-false-positive | none | cleanup |
| 054 | [An exception table check that rejects a handler range ending at code_length](054-exception-table-check-that-rejects-a-range-ending-at-code-length/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional, compatibility | critical | cleanup |
| 055 | [An encoder that zero-terminates the string into the caller's buffer](055-encoder-that-zero-terminates-into-the-callers-buffer/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional | high | feature |
| 056 | [A lookupswitch pair sort that compares keys by difference](056-switch-pair-sort-that-compares-keys-by-difference/README.md) | B11 | ✗ Violation: counterexample found | **missed** | functional | high | refactor |
<!-- examples:end -->

The *Existing tests* column is measured, not claimed: the generator runs the module's unit tests against each patch. A **missed** entry means the tests pass and the change would have shipped.

**Verdicts:**
- **✗ Violation:** behaviour changed, but the developer did not intend it. The build fails, with a concrete witness: an input whose outcome changed, a call site that gained a capability, or a step-by-step run of the system that breaks an invariant.
- **✓ Verified:** the code behaves exactly as its contract, its previous version, or its invariants say, for every possible input or interleaving within the stated bounds.
  An intended change passes once its contract is regenerated or its scope is declared, and that diff or declaration is what the reviewer approves.
- **⚠ Unverifiable:** the verifier refuses to give a verdict, for example because the code is no longer provably pure. The build fails, because "we could not check" must not read as "fine".

## How to read an example

Each example's page has the same sections:

| Section | Content |
|---|---|
| Summary table | Verdict, categories, severity if the change shipped unnoticed, what kind of change it was, the verified unit, the approach |
| The change | What the developer meant to do, the code before and after, and the patch |
| What the verifier found | The counterexamples (inputs whose outcome changed, capability changes, or a trace of the system), the reason for refusing, or the contract diff |
| Would the existing tests have caught it? | The module's unit tests, run against the same patch: the baseline the verifier is compared with |
| Why it matters | The production risk |
| Why the verdict is right | How the verifier reached it, and why it is a proof and not a sample |
| What to do | The resolution |
| Evidence | The verifier's console output and SARIF report, unedited; the JDK APIs a proof trusted; for a symbolic proof, the generated statement the prover checked |

For a state machine (014, 020, 021, 025, 026, 029, 030, 042, 043), the page also draws the machine the patched code implements, from its derived contract, with unreachable and terminal states marked.

## Layout

```
examples/
  README.md                  this page; the table above is generated
  index.json                 the same list, for tools (generated)
  NNN-short-name/
    example.json             written by hand: the change, its risk, the expected verdict, the explanation
    change.patch             written by hand: a unified diff against the repo
    result.json              generated: verdict, counterexamples or trace, before and after excerpts, contract diff
    result.sarif             generated: the verifier's SARIF report
    verifier-output.txt      generated: the verifier's console output
    statement.java           generated (B9): the harness JBMC proved or refuted
    README.md                generated: the page you read
  schema/
    example.schema.json      the format of example.json
    result.schema.json       the format of result.json
  approaches.md              the verification approaches by level, and the plan for the demos
  apps/boxoffice/            the first subject system (001 to 012): the ticketing services
  apps/boxoffice/spec/       its TLA+ model (D1)
  apps/quorum/               the second subject system (013 to 022): the distributed-systems kernels, with their contracts and properties
  apps/quorum/spec/          its TLA+ model of two-phase commit (D1)
  apps/crosscut/             the third subject system (023 to 033): the kernels of a Spring Boot service's cross-cutting concerns
  apps/crosscut/spec/        its TLA+ model of an idempotent receiver (D1)
  apps/mica/                 the fourth subject system (034 to 056): the decision kernels of a small JVM written in Java
  apps/mica/spec/            its TLA+ model of class initialization, checked for deadlock as well (D1)
  apps/mica/pending/         a proof waiting for a larger machine, and the two planned examples that depend on it
  tools/contracts/           the Java verifier for B8, B9 and B10, used by 001 to 012
  tools/tla/                 the generator of the model's state machine from the B8 contract, and the TLA+ standard modules TLC parses
  tools/build.py             the generator: runs every example and writes the generated files
  setup/                     the toolchain installer
../lib/                      jvmcontract, the Rust verifier for B8 to B11 and D1, used by 013 to 056
```

Everything a verifier says is generated by running it, so no example can claim a result the tool did not produce.
The generator also fails when a verdict differs from the example's `expected.verdict`, so the examples double as regression tests of the verifiers.

## Run or add an example

```bash
python3 examples/tools/build.py          # run every example, then rewrite the pages and the table
python3 examples/tools/build.py 002      # run one
python3 examples/tools/build.py 013 014 015 016 017 018 019 020 021 022   # the Quorum examples, about 20 seconds in all
python3 examples/tools/build.py 023 024 025 026 027 028 029 030 031 032 033   # the Crosscut examples, about 20 seconds in all
python3 examples/tools/build.py 034 035 036 037 038 039 040 041 042 043 044 045 046 047 048 049 050 051 052 053 054 055 056   # the Mica examples, about two minutes in all
```

It needs Java 25, JBMC for the B9 and B11 examples, TLC (`~/tools/tla2tools.jar`, as [`setup`](setup/README.md) installs it) for the D1 examples, and `cargo` (or a built `lib/target/release/jvmcontract`, or `JVMCONTRACT` pointing at one) for the Quorum, Crosscut and Mica examples; no Docker.
A Box Office example takes from a few seconds to a minute, because its patch is applied to a temporary copy of the Gradle build, which is then compiled, tested and verified. A Quorum, Crosscut or Mica example takes a second or two: `javac`, the tests, and `jvmcontract`.

To add an example:

1. Make the change in your working copy, and save it with `jj diff --git > examples/NNN-short-name/change.patch`. Then undo the change.
   A Box Office D1 example changes the Java and the matching action of [`apps/boxoffice/spec/BoxOffice.tla`](apps/boxoffice/spec/BoxOffice.tla) in the same patch; a Quorum, Crosscut or Mica D1 example changes the state machine the model is built around (the coordinator, the receiver, the class initialization), and the model picks the change up through the regenerated contract.
2. Write `examples/NNN-short-name/example.json`, following [`schema/example.schema.json`](schema/example.schema.json). An editor that understands JSON Schema will complete and check the fields.
   The `approach.id` picks the verifier, and the `subject.file` picks the subject system. For B9, `change.intendedInputs` declares the inputs the change is meant to affect. For B11, the property is the one declared for the symbol in the app's `properties.contract` ([Quorum](apps/quorum/src/contract/properties.contract), [Crosscut](apps/crosscut/src/contract/properties.contract), [Mica](apps/mica/src/contract/properties.contract)).
3. Run `python3 examples/tools/build.py NNN`, and read the generated page.

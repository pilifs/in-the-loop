# Contracts: behavioural, regression and capability

A proof of concept: catch unintended changes in CI, the way SonarQube catches new code smells, but with a proof behind each verdict instead of a heuristic.

**The idea.** Derive a *contract* from the compiled code, check it in next to the code, and fail the build when the code no longer matches it.
A developer who changes behaviour on purpose regenerates the contract, and the pull request then shows reviewers each changed case, and only those.
Refactors that preserve behaviour pass without touching the contract. So the contract changes exactly when behaviour does, and the diff says how. Nobody writes a specification.

One tool, three kinds of contract, each with its own proof:

| Contract | For | The contract is | Proved by | Approach |
|---|---|---|---|---|
| [Behavioural](#behavioural-contracts-methods-with-finite-inputs) | A pure method with finitely many inputs (enums, booleans, records, sealed types) | The outcome of every input | Purity from bytecode, then execution of every input | B8 |
| [Regression](#regression-verification-methods-with-unbounded-inputs) | A method with unbounded inputs (`long`, `int`, ...) | The previous version, outside the inputs the developer declares as changed | Bounded model checking of both versions' bytecode with JBMC | B9 |
| [Capability](#capability-contracts-what-a-module-can-do) | A whole module | Every JDK capability and library its bytecode can reach | Closed-world inspection of every call site | B10 |

All three run in `./gradlew check` through the [`boxoffice.contracts`](../../apps/boxoffice/build-logic/src/main/kotlin/boxoffice.contracts.gradle.kts) convention plugin, and all three emit SARIF for GitHub code scanning and SonarQube.
The [examples](../../README.md) show each of them on real changes to Box Office, with the verifier's unedited output.

## Behavioural contracts: methods with finite inputs

For a method, the contract is the complete list of its inputs and the outcome of each one, derived from the compiled bytecode.
[`OrderLifecycle#decide`](../../apps/boxoffice/ticketing-domain/src/main/java/net/terminalvalue/boxoffice/ticketing/domain/OrderLifecycle.java), the Box Office order state machine, has the contract [`OrderLifecycle.decide.contract`](../../apps/boxoffice/ticketing-domain/src/contract/OrderLifecycle.decide.contract):

```
domain: OrderStatus (6) × OrderInput (6) = 36 cases

decide(PENDING_PAYMENT, PaymentCaptured[seatsStillHeld=true])  => Transition[next=CONFIRMED, effects=[SELL_SEATS]]
decide(DECLINED, PaymentCaptured[seatsStillHeld=true])         => Transition[next=REFUND_PENDING, effects=[REQUEST_REFUND]]
decide(null, PaymentDeclined[])                                => throws NullPointerException
...
```

Three changes were tried against it while building this POC:

**1. A "cleanup" that merges a case into its neighbours.** It looks harmless, but it keeps a customer's money for a declined order ([example 001](../../001-merged-case-keeps-money/README.md)):

```diff
-                case DECLINED -> transition(REFUND_PENDING, REQUEST_REFUND);
-                case CONFIRMED, REFUND_PENDING, REFUNDED -> unchanged("payment already recorded");
+                case CONFIRMED, DECLINED, REFUND_PENDING, REFUNDED -> unchanged("payment already recorded");
```
```
✗ Behaviour of ...OrderLifecycle#decide differs from its contract in 2 of 36 cases:
  decide(DECLINED, PaymentCaptured[seatsStillHeld=false])
    contract: Transition[next=REFUND_PENDING, effects=[REQUEST_REFUND]]
    actual:   Unchanged[reason="payment already recorded"]
  decide(DECLINED, PaymentCaptured[seatsStillHeld=true])
    ...
```

**2. A refactor that was meant to preserve behaviour.** It was written by the agent building this tool, which believed it was equivalent ([example 002](../../002-equality-refactor-changes-null-handling/README.md)):

```diff
-            case PaymentRefunded _ -> switch (current) {
-                case REFUND_PENDING -> transition(REFUNDED);
-                case PENDING_PAYMENT, CONFIRMED, DECLINED, REFUNDED -> unchanged("no refund outstanding");
-            };
+            case PaymentRefunded _ ->
+                current == REFUND_PENDING ? transition(REFUNDED) : unchanged("no refund outstanding");
```
```
✗ Behaviour of ...OrderLifecycle#decide differs from its contract in 1 of 36 cases:
  decide(null, PaymentRefunded[])
    contract: throws NullPointerException
    actual:   Unchanged[reason="no refund outstanding"]
```

A `switch` on null throws, but `==` does not. The same refactor with `default ->` passes ([example 004](../../004-equivalent-refactor-passes/README.md)).

**3. Logging a timestamp in the decision.** Execution can no longer stand for a proof, so the verifier refuses ([example 003](../../003-timestamp-makes-decision-nondeterministic/README.md)):

```
✗ ...OrderLifecycle#decide cannot be verified: not provably pure:
  ...OrderLifecycle.unchanged calls java.time.Instant.now, which is not known to be pure
```

### How a verdict is proved

The verifier derives a contract in three steps. Each step can refuse, and a refusal fails the build.

1. **Purity, from bytecode.** Using the JDK's ClassFile API, it walks every application method the target can reach.
   Virtual calls are followed through sealed hierarchies, and a call into an open hierarchy is rejected.
   It also rejects:
   - writes to static fields, and reads of mutable static fields;
   - writes to fields outside constructors;
   - native methods;
   - any JDK call outside a short list of pure APIs in [`TrustedApi.java`](src/main/java/net/terminalvalue/contracts/TrustedApi.java), such as `List.of` and `Objects.requireNonNull`. The clock, randomness, I/O, threads and reflection are all outside it.

   That list, together with the JVM, is the trusted base. Each run prints which entries it relied on.
2. **A finite domain, from types.** Enums, booleans, records of finite types and sealed interfaces have finitely many values, and the verifier enumerates them.
   This is where modern Java helps: algebraic data types make many domain functions finite.
   Each reference parameter also takes `null`.
3. **Execution of every input.** A pure method with finitely many inputs is fully described by its outcomes on all of them.
   The verifier also runs each input twice, as a check on step 1.

Steps 1 and 2 are what turn "we ran every case" into a proof: the result holds for every call the program can make, and is not a sample.
This is bounded model checking with a complete bound. The method's input space is small enough that the bound covers all of it.

## Regression verification: methods with unbounded inputs

[`HoldPolicy#totalCents(long priceCents, int seats)`](../../apps/boxoffice/ticketing-domain/src/main/java/net/terminalvalue/boxoffice/ticketing/domain/HoldPolicy.java) has 2^96 inputs, so no contract can list them and no test can sweep them.
What can be stated is a relation between two versions of the method: *the new one behaves as the old one on every input*, or, for an intended change, *on every input except those the developer declares*.
That statement is proved or refuted symbolically, from the bytecode of both versions:

1. **One program, two versions.** The old classes are relocated into a `before` package by rewriting their constant pools ([`Relocate.java`](src/main/java/net/terminalvalue/contracts/Relocate.java)), so both versions load side by side.
2. **A generated statement.** A harness calls both versions on the same symbolic arguments, catches what each throws, and asserts that the results and the exception types agree ([`Equivalence.java`](src/main/java/net/terminalvalue/contracts/Equivalence.java)).
   With `--unchanged-unless "seats >= 8"`, the harness returns early on those inputs: that Java expression, checked by the compiler, is the developer's claim about the change.
3. **JBMC.** [JBMC](https://github.com/diffblue/cbmc), the bounded model checker for JVM bytecode, turns the harness into a satisfiability problem over bit-vectors.
   Unsatisfiable means no input exists on which the versions differ; a satisfying assignment is an input on which they do.
   The real bytecode of `java.lang.Math` is put on JBMC's classpath, so `Math.multiplyExact` is analysed as written rather than modelled.
   Loops are unwound to a bound with unwinding assertions, so a loop the bound does not cover makes the verdict *unverifiable* rather than wrong.
4. **Replay.** A counterexample is run through both versions on a real JVM, and the two observed outcomes are what the report shows. Small inputs are searched first, so that the witness is readable; the proof is over the full domain.

```
✗ Behaviour of ...HoldPolicy#totalCents changed outside the intended inputs (seats >= 8):
  totalCents(priceCents=5, seats=7)
    before: 32
    after:  31
  (found by JBMC 6.11.0 in 0.4 s searching inputs in [0:100], replayed on the JVM; domain priceCents: long × seats: int)
```

[Example 006](../../006-per-seat-discount-rounds-differently/README.md) refutes a rounding refactor, [007](../../007-doubled-group-discount-proved-confined/README.md) proves a doubled discount confined to the seat counts it declares, and [008](../../008-percentage-rewrite-leaks-outside-new-tier/README.md) shows such a declaration failing when a rewrite also touched the old tier.

In CI the previous version is the merge base: build its classes, build the branch's classes, and run

```bash
java -cp contract-verifier.jar net.terminalvalue.contracts.Main equivalence \
    --before base/classes --after head/classes --target net.example.HoldPolicy#totalCents \
    --unchanged-unless "seats >= 8" --report build/reports/contracts
```

for each method the pull request touches whose inputs are not finite. The [examples generator](../build.py) does exactly this for the B9 examples.

## Capability contracts: what a module can do

A module's capability contract lists, from its compiled classes, every call to a JDK entry point that reaches beyond pure computation, grouped by capability, together with the libraries the module calls ([`Capabilities.java`](src/main/java/net/terminalvalue/contracts/Capabilities.java)).
The capabilities are the clock, the console, the environment, the file system, JNDI, native code, the network, processes, randomness, reflection and class loading, scripting, serialization and threads.
Box Office's [`contracts` module](../../apps/boxoffice/contracts/src/contract/capabilities.contract), which holds the Kafka messages and their codec, has none of them:

```
module: contracts, 10 classes, 52 methods

clock: none
...
reflection: none
...
libraries:
  tools.jackson.databind
```

A change that makes the codec resolve a class name from the payload ([example 009](../../009-codec-loads-classes-named-by-payload/README.md)) fails the build with the call site:

```
✗ Capabilities of module contracts differ from its contract:
  added reflection: net.terminalvalue.boxoffice.contracts.MessageCodec.decode calls java.lang.Class.forName
```

**Why this is a proof and not a grep.** On the JVM every capability is exercised through a JDK entry point, so bytecode that contains no call to the entry points of a capability cannot exercise it.
The ways around that argument are reflection, method handles, class loaders, `ServiceLoader`, native code and deserialization, and those are capabilities on the list themselves.
A module whose contract says `reflection: none` and `native: none` therefore has no way to reach what the rest of the list denies it.
The check is a complete walk over every instruction of every method of the module, so it cannot miss a call site; what it does not see is what the module's *libraries* do with the calls it makes into them, which is why the libraries are listed and a new one shows up as a diff.

## Use

In a Gradle build (here, through the [`boxoffice.contracts`](../../apps/boxoffice/build-logic/src/main/kotlin/boxoffice.contracts.gradle.kts) convention plugin):

```bash
./gradlew check                    # includes verifyContracts; fails on any drift
./gradlew updateContracts          # rewrite every contract from the code, after an intended change
./gradlew :ticketing-domain:updateContracts -Ptarget=net.example.Pricing#discount   # add a behavioural contract
./gradlew :contracts:updateContracts -Ptarget=capabilities                           # add a module's capability contract
```

Each run writes `build/reports/contracts/contracts.sarif`, with findings anchored to the method's source line, or to the call site that gained a capability.
SARIF is the format GitHub code scanning accepts, and SonarQube imports it through `sonar.sarifReportPaths`.
That makes this a drop-in stage in an existing pipeline, alongside the static analysers a team already runs.

The verifier's own tests: `./gradlew -p ../../tools/contracts test`, run from `examples/apps/boxoffice`. The regression-verification tests need `jbmc` on the PATH and are skipped without it.

## Limits of this POC, and where to take it

- **Behavioural contracts cover finite domains and static methods.** Instance methods need the receiver's state as part of the domain. Purity is approximate: stores into arrays and collections that were passed in are not tracked yet, and constructors may write any field.
- **Regression verification covers primitive parameters and straight-line arithmetic well, and gets expensive with it.** Equivalence of two 64-bit multiplications and the overflow check behind `Math.multiplyExact` is proved in about fifteen seconds; add a 64-bit division to each side and the SAT and SMT back ends available here (MiniSat, Z3, cvc5) no longer finish in ten minutes, which the tool reports as *unverifiable*. `String` and object parameters, loops that the unwinding bound does not cover, and pattern-matching `switch` (which JBMC 6.11 does not model) are outside it for now. A bytecode pre-pass that lowers `typeSwitch` to `instanceof` chains would bring state machines like `OrderLifecycle` into reach, and would let the two approaches meet: finite parameters enumerated, unbounded ones symbolic.
- **Capability contracts stop at the module's own bytecode.** A dependency's capabilities are a separate contract per dependency jar, which the same analysis could produce; the libraries list is the hook for it.
- **Other contract kinds.** The same lockfile-and-diff workflow fits allocation and loop bounds per method, for performance, and the HTTP routes and their status codes, for API compatibility.
- **Cost.** A behavioural or capability contract takes under a second. A symbolic proof takes seconds to minutes and belongs in a background job that posts SARIF to the pull request, the way SonarQube analyses run.

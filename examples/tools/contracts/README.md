# Behavioural contracts

A proof of concept: catch unintended behaviour changes in CI, the way SonarQube catches new code smells, but with a proof behind each verdict instead of a heuristic.

**The idea.** For a method, the *contract* is the complete list of its inputs and the outcome of each one, derived from the compiled bytecode and checked in next to the code.
The build fails when the code's behaviour no longer matches the contract.
A developer who changes behaviour on purpose regenerates the contract, and the pull request then shows reviewers each changed case, and only those.
Refactors that preserve behaviour pass without touching the contract.

So the contract changes exactly when behaviour does, and the diff says how. Nobody writes a specification.

## Example

[`OrderLifecycle#decide`](../../apps/boxoffice/ticketing-domain/src/main/java/net/terminalvalue/boxoffice/ticketing/domain/OrderLifecycle.java), the Box Office order state machine, has the contract [`OrderLifecycle.decide.contract`](../../apps/boxoffice/ticketing-domain/src/contract/OrderLifecycle.decide.contract):

```
domain: OrderStatus (6) × OrderInput (6) = 36 cases

decide(PENDING_PAYMENT, PaymentCaptured[seatsStillHeld=true])  => Transition[next=CONFIRMED, effects=[SELL_SEATS]]
decide(DECLINED, PaymentCaptured[seatsStillHeld=true])         => Transition[next=REFUND_PENDING, effects=[REQUEST_REFUND]]
decide(null, PaymentDeclined[])                                => throws NullPointerException
...
```

Three changes were tried against it while building this POC:

**1. A "cleanup" that merges a case into its neighbours.** It looks harmless, but it keeps a customer's money for a declined order:

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

**2. A refactor that was meant to preserve behaviour.** It was written by the agent building this tool, which believed it was equivalent:

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

A `switch` on null throws, but `==` does not. The same refactor with `default ->` passes.

**3. Logging a timestamp in the decision.** Execution can no longer stand for a proof, so the verifier refuses:

```
✗ ...OrderLifecycle#decide cannot be verified: not provably pure:
  ...OrderLifecycle.unchanged calls java.time.Instant.now, which is not known to be pure
```

## How a verdict is proved

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

## Use

In a Gradle build (here, through the [`boxoffice.contracts`](../../apps/boxoffice/build-logic/src/main/kotlin/boxoffice.contracts.gradle.kts) convention plugin):

```bash
./gradlew check                    # includes verifyContracts; fails on any drift
./gradlew updateContracts          # rewrite every contract from the code, after an intended change
./gradlew :ticketing-domain:updateContracts -Ptarget=net.example.Pricing#discount   # add one
```

Each run writes `build/reports/contracts/contracts.sarif`, with findings anchored to the method's source line.
SARIF is the format GitHub code scanning accepts, and SonarQube imports it through `sonar.sarifReportPaths`.
That makes this a drop-in stage in an existing pipeline, alongside the static analysers a team already runs.

The verifier's own tests: `./gradlew -p ../../tools/contracts test`, run from `examples/apps/boxoffice`.

## Limits of this POC, and where to take it

- **Finite domains only.** A `long` or `String` parameter is refused.
  The next step is symbolic: prove `old(x) == new(x)` for all `x` outside the cases the developer marked as changed (regression verification), using JBMC or an SMT solver.
  JBMC 6.11 cannot do this for modern Java as it ships. It treats the `typeSwitch` invokedynamic of a pattern `switch` as an unknown value and reports spurious failures. It also has no models for `List.of`, `List.copyOf`, record `equals`, or `Math.multiplyExact`.
  A bytecode pre-pass that lowers `typeSwitch` to `instanceof` chains, plus models for the immutable collections, would fix the first two of those.
- **Static methods only.** Instance methods need the receiver's state as part of the domain.
- **Purity is approximate.** Stores into arrays and collections that were passed in are not tracked yet, and constructors may write any field.
- **Other contract kinds.** The same lockfile-and-diff workflow fits other properties that should change only on purpose, each with its own engine:
  - which external APIs a module can reach: network, process, reflection, environment, for security and configuration;
  - allocation and loop bounds per method, for performance;
  - the HTTP routes and their status codes, for API compatibility.
- **Cost.** This target takes under a second. Expensive engines, such as symbolic checks or proofs in Lean, belong in a background job that posts SARIF to the pull request, the way SonarQube analyses run.

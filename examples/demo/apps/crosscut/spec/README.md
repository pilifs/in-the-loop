# The Crosscut protocol models

Two TLA+ models, each around a kernel of this module: the [idempotent receiver](#the-idempotent-receiver-model) and the [circuit breaker](#the-circuit-breaker-model).

## The idempotent-receiver model

A TLA+ model of an `Idempotency-Key` receiver as a distributed system: a client that sends a request and retries it under the same key, the receiver with its record for the key, the attempts in flight between them, and the attempts executing inside the receiver.
TLC explores every interleaving for the attempts in `IdempotentReceiver.cfg` and checks the invariants in every state it reaches.
This is approach D1 in [`approaches.md`](../../../../approaches.md), applied to the third subject system; the [Box Office model](../../boxoffice/spec/README.md) describes the idea at length.

| File | Content |
|---|---|
| [`IdempotentReceiver.tla`](IdempotentReceiver.tla) | The model. One action per operation of the client (send, or retry) and of the receiver (decide on an arriving attempt, finish an execution with a result, lose an execution to a failure). Each action names the Java operation it stands for |
| [`IdempotentReceiver.cfg`](IdempotentReceiver.cfg) | The bounds TLC checks: one request sent three times, and the list of invariants |
| [`IdempotentReceiverContract.tla`](IdempotentReceiverContract.tla) | **Generated.** The receiver's decision rule, as the TLA+ operator `Decide(key, event)`, written by `jvmcontract tla` from the [behavioural contract](../src/contract/IdempotentReceiver.decide.contract) of `IdempotentReceiver#decide` |

The invariants:

- **OneExecutionAtATime.** No two attempts under one key execute at the same time.
- **AtMostOnce.** Once an execution has produced a result, no attempt is executing and none ever will: the request's effect happens at most once.
- **ReplayedResponsesExist.** A client is never answered with a stored response that does not exist.
- **TypeOK.**

What the model leaves out: one key, whose attempts all carry the same request, so the fingerprint always matches; the record does not expire within the run; the receiver's lookup of the record and its decision are one atomic step, which is what the filter's transaction provides.
An attempt that dies releases the key, so a retry after a failure executes again, which is at-most-once in the sense that matters: at most one execution ever produces a result.

### Run it

```bash
cd examples/demo/apps/crosscut
jvmcontract tla src/contract/IdempotentReceiver.decide.contract spec/IdempotentReceiverContract.tla
jvmcontract tlc spec/IdempotentReceiver.tla --library ../../tools/tla/standard-modules
```

TLC checks 168 states in under a second. [Example 029](../../../029-retry-in-progress-executes-twice/README.md) shows a four-step counterexample; [example 030](../../../030-stored-failures-proved-at-most-once/README.md) shows an intended change proved safe.

## The circuit-breaker model

A TLA+ model of a circuit breaker as a system: the component that owns the breaker (Resilience4j's `CircuitBreakerStateMachine`, or the `@CircuitBreaker` aspect), the calls it lets through to a dependency that is up or down, the sliding window of their outcomes, the probes of the half-open state, and the clock that ends the open state's wait.
The kernel decides the transitions; the owner keeps the window, caps the probes, runs the timer and chooses which outcomes to report. The model writes the owner's part down and lets TLC run the two together.
It was written with the [`/add-tla-model`](../../../../../plugins/jvmcontract/README.md#add-tla-model-check-your-own-invariants-with-a-tla-model) skill's procedure, as its worked example.

| File | Content |
|---|---|
| [`CircuitBreaker.tla`](CircuitBreaker.tla) | The model. One action per operation of the owner (a permission requested, a call of the current metrics generation completed, a stale call completed) and of the environment (the wait timer ticks, the dependency goes down or comes back). Each action names the owner's operation it stands for |
| [`CircuitBreaker.cfg`](CircuitBreaker.cfg) | The bounds TLC checks: a window of two calls, a failure rate of one in two, two probes, a wait of two ticks, two calls in flight at once, and the list of invariants |
| [`CircuitBreakerContract.tla`](CircuitBreakerContract.tla) | **Generated.** The breaker's decision rule, as the TLA+ operator `Decide(state, event)`, written by `jvmcontract tla` from the [behavioural contract](../src/contract/CircuitBreaker.decide.contract) of `CircuitBreaker#decide` |

The invariants:

- **NoCallBeforeTheWait.** An open breaker lets nothing through until its wait has elapsed.
- **OpenShieldsTheDependency.** While open, the dependency receives no call of the current metrics generation: everything in flight was permitted before the breaker opened.
- **ClosedOnlyAfterEveryProbe.** Half-open closes only once every permitted probe has completed; one good probe is not evidence enough.
- **ProbesAreLimited.** Half-open lets at most `PermittedProbes` calls through, in flight or completed, before it decides.
- **ClosedOnlyBelowTheThreshold.** A closed breaker never sits on a complete window whose failure rate is at the threshold: it opens on the call that completes it.
- **TypeOK.**

What the model leaves out: the window is count-based; a call fails exactly when the dependency is down; the owner stamps each permitted call with the metrics generation and drops the outcome of a call from an earlier generation (one permitted before the breaker opened, or before the probes started), which is what the OPEN rows of the kernel assume; a request that would exceed the probe cap is refused by the owner and is not modelled.
That generation rule is a decision the kernel leaves to its owner, and writing the model is what made it explicit: an owner that reports every outcome counts a straggler from before the breaker opened as a probe.

### Run it

```bash
cd examples/demo/apps/crosscut
jvmcontract tla src/contract/CircuitBreaker.decide.contract spec/CircuitBreakerContract.tla
jvmcontract tlc spec/CircuitBreaker.tla --library ../../tools/tla/standard-modules
```

TLC checks 102 states in under a second. With the kernel of [example 026](../../../026-half-open-breaker-that-closes-on-the-first-good-probe/README.md) (half-open closes on the first good probe), the contract changes in two rows, the operator is regenerated from it, and the model reports `ClosedOnlyAfterEveryProbe` violated after ten steps: two failures open the breaker, the wait elapses, one probe is permitted, the dependency comes back, and that single probe closes it.

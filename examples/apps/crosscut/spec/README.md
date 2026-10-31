# The idempotent-receiver protocol model

A TLA+ model of an `Idempotency-Key` receiver as a distributed system: a client that sends a request and retries it under the same key, the receiver with its record for the key, the attempts in flight between them, and the attempts executing inside the receiver.
TLC explores every interleaving for the attempts in `IdempotentReceiver.cfg` and checks the invariants in every state it reaches.
This is approach D1 in [`approaches.md`](../../../approaches.md), applied to the third subject system; the [Box Office model](../../boxoffice/spec/README.md) describes the idea at length.

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

## Run it

```bash
cd examples/apps/crosscut
jvmcontract tla src/contract/IdempotentReceiver.decide.contract spec/IdempotentReceiverContract.tla
jvmcontract tlc spec/IdempotentReceiver.tla --library ../../tools/tla/standard-modules
```

TLC checks 168 states in under a second. [Example 029](../../../029-retry-in-progress-executes-twice/README.md) shows a four-step counterexample; [example 030](../../../030-stored-failures-proved-at-most-once/README.md) shows an intended change proved safe.

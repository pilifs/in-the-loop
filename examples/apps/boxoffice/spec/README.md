# The Box Office protocol model

A TLA+ model of Box Office as a distributed system: customers, the ticketing service, Kafka, the payment service, and the clock that expires holds.
TLC, the TLA+ model checker, explores every interleaving of those parts within small bounds and checks the [invariants of the README](../README.md#invariants-what-verification-should-establish) in every state it reaches.
This is approach D1 in [`approaches.md`](../../../approaches.md).

| File | Content |
|---|---|
| [`BoxOffice.tla`](BoxOffice.tla) | The model. One action per transaction of each service, one per outbox relay, one for the sweeper, one for the clock. Each action names the Java operation it stands for |
| [`BoxOffice.cfg`](BoxOffice.cfg) | The bounds TLC checks: two customers, one seat, four clock ticks, holds that last one tick, and the list of invariants |
| [`OrderLifecycleContract.tla`](OrderLifecycleContract.tla) | **Generated.** The order state machine, as the TLA+ operator `Decide(status, input)`, written by [`contract_to_tla.py`](../../../tools/tla/contract_to_tla.py) from the [behavioural contract](../ticketing-domain/src/contract/OrderLifecycle.decide.contract) of `OrderLifecycle#decide` |

## Why a model, and what it is worth

A unit test exercises one method on one input. A system test exercises one interleaving of the whole system, the one its timing happens to produce.
The failures that matter in a distributed system live in the interleavings nobody thought of: a lease that expires while a message is in flight, a retry that lands after the state has moved on.
TLC enumerates them. For the bounds in `BoxOffice.cfg` that is a few thousand states and about two seconds; for two seats and five ticks it is a hundred thousand states and under a minute.

What a run proves is exactly this: *within those bounds, no interleaving of the modelled actions reaches a state that violates the invariants.* It does not prove the Java code correct. The model is a hand-written account of what each transaction does, and it is only as faithful as its author. Two things narrow that gap here:

- **The state machine is not transcribed.** `Decide` is generated from the behavioural contract, which the build proves the bytecode satisfies on every input ([`tools/contracts`](../../../tools/contracts/README.md)). A change to `OrderLifecycle` reaches the model through its proof, not through someone remembering to update a spec.
- **Each action is one transaction.** The actions are written against the store operations the Java code calls (`TicketingStore.heldBy`, `OrderTransitions.apply`, and so on), and each comment names its Java counterpart, so a reviewer can hold the two side by side. The examples that change a handler change the Java and the matching action in one patch.

The step after this, which the model does not take, is trace validation: instrument the services, record what they actually do under load and fault injection, and check that every recorded run is a behaviour the model allows. That closes the gap from the other side.

## Run it

```bash
cd examples/apps/boxoffice/spec
python3 ../../../tools/tla/contract_to_tla.py ../ticketing-domain/src/contract/OrderLifecycle.decide.contract OrderLifecycleContract.tla
java -cp ~/tools/tla2tools.jar tlc2.TLC -workers auto -deadlock BoxOffice.tla
```

`-deadlock` turns off deadlock checking, because a system that has finished every order is meant to stop.
A violated invariant prints the shortest run that reaches it, state by state; [example 011](../../../011-skipped-seat-check-strands-the-money/README.md) shows one rendered step by step.

## What the model leaves out

- One hold and one order per customer, so the customer, the hold id and the order id are one value.
- Relays publish each outbox entry once. Kafka delivers at least once in reality, but the inbox turns a redelivery into a no-op, which is what the model assumes.
- A transaction that keeps failing is dead-lettered in one step, rather than after the retries the real listener makes.
- Liveness. The invariants are safety properties; "every order eventually leaves PENDING_PAYMENT" would need fairness assumptions and a temporal property, which TLC can also check.

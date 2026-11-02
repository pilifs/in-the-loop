# The two-phase-commit protocol model

A TLA+ model of two-phase commit around the Quorum coordinator: the participants, the coordinator, the votes in flight between them, and the two timeouts.
TLC explores every interleaving for the participants in `TwoPhaseCommit.cfg` and checks the invariants in every state it reaches.
This is approach D1 in [`approaches.md`](../../../../approaches.md), applied to the second subject system; the [Box Office model](../../boxoffice/spec/README.md) describes the idea at length.

| File | Content |
|---|---|
| [`TwoPhaseCommit.tla`](TwoPhaseCommit.tla) | The model. One action per operation of a participant (vote, give up, apply the decision) and of the coordinator (count a vote, time out). Each action names the Java operation it stands for |
| [`TwoPhaseCommit.cfg`](TwoPhaseCommit.cfg) | The bounds TLC checks: three participants, and the list of invariants |
| [`CoordinatorContract.tla`](CoordinatorContract.tla) | **Generated.** The coordinator's decision rule, as the TLA+ operator `Decide(phase, event)`, written by `jvmcontract tla` from the [behavioural contract](../src/contract/Coordinator.decide.contract) of `Coordinator#decide` |

The invariants:

- **Atomicity.** Once the coordinator or any participant has committed, no participant has aborted: every participant that decides, decides the same way.
- **CommitFollowsTheCoordinator.** A participant commits only on the coordinator's decision, and only after voting yes.
- **TypeOK.**

What the model leaves out: one transaction; messages can be reordered but not lost or duplicated; the coordinator's decision is a broadcast every participant can read. A participant that voted yes cannot give up, which is the blocking property of the protocol.

## Run it

```bash
cd examples/demo/apps/quorum
jvmcontract tla src/contract/Coordinator.decide.contract spec/CoordinatorContract.tla
jvmcontract tlc spec/TwoPhaseCommit.tla --library ../../tools/tla/standard-modules
```

TLC checks 728 states in about a second. [Example 020](../../../020-coordinator-that-presumes-commit-on-timeout/README.md) shows a three-step counterexample; [example 021](../../../021-aborting-on-the-first-no-proved-safe/README.md) shows an intended change proved safe.

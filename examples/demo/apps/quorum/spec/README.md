# The two-phase-commit protocol model

A TLA+ model of two-phase commit around the Quorum coordinator: the participants, the coordinator, the votes in flight between them, and the two timeouts.
TLC explores every interleaving for the participants in `TwoPhaseCommit.cfg`, checks the invariants in every state it reaches, and then checks two temporal properties over every behaviour, the infinite ones included: that every participant eventually decides, and that the protocol implements Lamport and Gray's transaction-commit specification.
This is approach D1 in [`approaches.md`](../../../../approaches.md), applied to the second subject system; the [Box Office model](../../boxoffice/spec/README.md) describes the idea at length.

| File | Content |
|---|---|
| [`TwoPhaseCommit.tla`](TwoPhaseCommit.tla) | The model. One action per operation of a participant (vote, give up, apply the decision) and of the coordinator (count a vote, time out). Each action names the Java operation it stands for |
| [`TwoPhaseCommit.cfg`](TwoPhaseCommit.cfg) | The bounds TLC checks: three participants, the list of invariants, and the two temporal properties |
| [`TCommit.tla`](TCommit.tla) | Transaction commit as Lamport and Gray specify it, with no coordinator, messages or timers: a participant commits only once every participant is prepared or committed, and aborts only while none has committed. `TwoPhaseCommit.tla` instantiates it on the participants' states and is checked to implement it |
| [`CoordinatorContract.tla`](CoordinatorContract.tla) | **Generated.** The coordinator's decision rule, as the TLA+ operator `Decide(phase, event)`, written by `jvmcontract tla` from the [behavioural contract](../src/contract/Coordinator.decide.contract) of `Coordinator#decide` |

The invariants:

- **Atomicity.** Once the coordinator or any participant has committed, no participant has aborted: every participant that decides, decides the same way.
- **CommitFollowsTheCoordinator.** A participant commits only on the coordinator's decision, and only after voting yes.
- **TypeOK.**

The temporal properties, checked after the invariants:

- **EveryParticipantDecides.** Every participant eventually commits or aborts: `\A p \in Participants : <>(pstate[p] \in {"COMMITTED", "ABORTED"})`. A participant that voted yes holds its locks until it hears the decision, so this is the property that the coordinator always decides and that the decision reaches everyone. It is checked under the model's fairness conditions (`Fairness`): participants vote or give up, the coordinator counts every vote that reaches it and fires its timer while votes are missing, and participants apply a decision once made. Nothing is assumed about which vote a participant casts or when one gives up. A counterexample is an infinite behaviour, which TLC shows as a finite prefix and how it goes on: stuttering in the last state forever, or returning to an earlier state and repeating.
- **ImplementsTransactionCommit.** Every behaviour of the protocol, seen through the participants' states alone, is a behaviour of `TCommit.tla`: `TC!TCSpec` with `TC == INSTANCE TCommit`. TLC checks it as an action property, every step of the protocol against the next-state relation of transaction commit.

TLC does not say which temporal property a counterexample violates, so `jvmcontract tlc` checks them one at a time when the configuration lists several, and names the one that fails.

What the model leaves out: one transaction; messages can be reordered but not lost or duplicated; the coordinator's decision is a broadcast every participant can read. A participant that voted yes cannot give up, which is the blocking property of the protocol.

## Run it

```bash
cd examples/demo/apps/quorum
jvmcontract tla src/contract/Coordinator.decide.contract spec/CoordinatorContract.tla
jvmcontract tlc spec/TwoPhaseCommit.tla --library ../../tools/tla/standard-modules
```

TLC checks 728 states in about a second. [Example 020](../../../020-coordinator-that-presumes-commit-on-timeout/README.md) shows a three-step counterexample; [example 021](../../../021-aborting-on-the-first-no-proved-safe/README.md) shows an intended change proved safe. [Example 057](../../../057-coordinator-that-waits-for-the-last-yes-vote-blocks-forever/README.md) shows a liveness counterexample, a coordinator that never decides; [example 058](../../../058-grace-period-for-the-last-vote-proved-live-and-a-refinement/README.md) shows a change proved live and still a refinement of transaction commit.

# The protocol models

Two TLA+ models, each built around one of Quorum's state machines: [two-phase commit](#the-two-phase-commit-model) around the coordinator, and [Raft leader election](#the-raft-election-model) around the role machine. In both, the state machine is generated from the behavioural contract of the Java, and everything else is written against the Java, action by action.

## The two-phase-commit model

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

### Run it

```bash
cd examples/demo/apps/quorum
jvmcontract tla src/contract/Coordinator.decide.contract spec/CoordinatorContract.tla
jvmcontract tlc spec/TwoPhaseCommit.tla --library ../../tools/tla/standard-modules
```

TLC checks 728 states in about a second. [Example 020](../../../020-coordinator-that-presumes-commit-on-timeout/README.md) shows a three-step counterexample; [example 021](../../../021-aborting-on-the-first-no-proved-safe/README.md) shows an intended change proved safe. [Example 057](../../../057-coordinator-that-waits-for-the-last-yes-vote-blocks-forever/README.md) shows a liveness counterexample, a coordinator that never decides; [example 058](../../../058-grace-period-for-the-last-vote-proved-live-and-a-refinement/README.md) shows a change proved live and still a refinement of transaction commit.

## The Raft election model

A TLA+ model of Raft leader election (Ongaro and Ousterhout, section 5.2) around the Quorum role machine: the servers, their terms and votes, and the RPCs between them.
TLC explores every interleaving for the servers and terms in `RaftElection.cfg`, checks the invariants in every state it reaches, and checks two action properties on every step.

| File | Content |
|---|---|
| [`RaftElection.tla`](RaftElection.tla) | The model. One action per operation of a server: its election timer fires; it canvasses one server for a vote; it sends one server a heartbeat. An RPC is one step, the request and its reply together, and the request and the reply each go through the role machine. Each action names the Java operation it stands for |
| [`RaftElection.cfg`](RaftElection.cfg) | The bounds TLC checks: three servers and three terms, the list of invariants, and the two action properties |
| [`RoleMachineContract.tla`](RoleMachineContract.tla) | **Generated.** A server's role transitions, as the TLA+ operator `Decide(role, event)`, written by `jvmcontract tla` from the [behavioural contract](../src/contract/RoleMachine.decide.contract) of `RoleMachine#decide`. The role machine sees a message's term only as it compares with the server's own (`NEWER`, `CURRENT`, `OLDER`), as the Java does |

The vote itself is `VoteRule.grant` written in TLA+ without the log comparison: a candidate from the past is refused, and otherwise the vote is granted when the candidate's term is ahead of the voter's, or the voter has not voted in its term, or voted for this candidate. That rule is stated for a voter that has already adopted the candidate's term, which is what the role machine does on a request from a newer term; example 059 is what happens when it stops doing so.

The invariants:

- **ElectionSafety.** At most one leader per term (figure 3 of the paper).
- **LeaderHasAMajority.** A leader holds the votes of a majority of the servers, its own among them.
- **TypeOK.**

The action properties, `[][A]_vars` formulas that TLC checks on every step rather than on every state:

- **TermsNeverDecrease.** `[][\A s \in Servers : currentTerm'[s] >= currentTerm[s]]_vars`.
- **LeadersNeverCampaign.** `[][\A s \in Servers : role[s] = "LEADER" => role'[s] # "CANDIDATE"]_vars`: a leader leaves office as the follower of a newer term, or by stepping down, never by starting an election against itself. The states on either side of such a step are states the protocol allows, a leader in one term and a candidate in the next, which is why no invariant can state this and the model states it as a property of steps. TLC reports an action property by name, and its counterexample is the run up to the offending step.

What the model leaves out: the log, so there is no election restriction and a heartbeat is an empty AppendEntries; message delay, since an RPC is one step, so a server always answers with the term it has now and a stale server learns of a newer term the moment it talks to one that has it; and liveness, since Raft elects a leader eventually by randomizing the timeouts, which is a matter of timing, and the model has no clock. Terms stop at `MaxTerm`, past which no timer fires.

### Run it

```bash
cd examples/demo/apps/quorum
jvmcontract tla src/contract/RoleMachine.decide.contract spec/RoleMachineContract.tla
jvmcontract tlc spec/RaftElection.tla --library ../../tools/tla/standard-modules
```

TLC checks 610 states in under a second. [Example 059](../../../059-vote-granted-without-adopting-the-term-elects-two-leaders/README.md) shows a five-step run to two leaders in one term; [example 060](../../../060-one-timeout-rule-makes-a-leader-campaign-against-itself/README.md) shows an action property violated by a step between two unremarkable states; [example 061](../../../061-leader-that-steps-down-on-its-own-timeout-proved-safe/README.md) shows a leader that steps down on its own timer, proved safe in 1,153 states.

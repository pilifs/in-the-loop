# The protocol models

Two TLA+ models, each built around one of Quorum's state machines: [two-phase commit](#the-two-phase-commit-model) around the coordinator, and [Raft leader election](#the-raft-election-model) around the role machine. In both, the state machine is generated from the behavioural contract of the Java, and everything else is written against the Java, action by action.

## The two-phase-commit model

A TLA+ model of two-phase commit around the Quorum coordinator: the participants, the coordinator, the votes in flight between them, and the two timeouts.
TLC explores every interleaving for the participants in `TwoPhaseCommit.cfg`, checks the invariants in every state it reaches, and then checks two temporal properties over every behaviour, the infinite ones included: that every participant eventually decides, and that the protocol implements Lamport and Gray's transaction-commit specification. A second configuration, `TwoPhaseCommitInductive.cfg`, checks that an invariant of the model is inductive, which proves atomicity for runs of any length.
This is approach D1 in [`approaches.md`](../../../../approaches.md), applied to the second subject system; the [Box Office model](../../boxoffice/spec/README.md) describes the idea at length.

| File | Content |
|---|---|
| [`TwoPhaseCommit.tla`](TwoPhaseCommit.tla) | The model. One action per operation of a participant (vote, give up, apply the decision) and of the coordinator (count a vote, time out). Each action names the Java operation it stands for |
| [`TwoPhaseCommit.cfg`](TwoPhaseCommit.cfg) | The bounds TLC checks: three participants, the list of invariants, and the two temporal properties |
| [`TwoPhaseCommitInductive.cfg`](TwoPhaseCommitInductive.cfg) | The inductive step: `INIT InductiveInit` in place of `SPECIFICATION Spec`, so that TLC starts from every state the invariant `Inductive` admits, reachable or not, takes one step, and checks each conjunct again |
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

The inductive invariant, `Inductive`, is what makes atomicity true, written out: the invariants above and four more, about the votes counted and in flight, which every reachable state agrees on and an arbitrary state need not.

- **VotesInFlightAreUncounted.** A vote on its way to the coordinator has not been counted, and a participant votes once.
- **DecisionMatchesThePhase.** What the coordinator broadcast is what its phase says.
- **ParticipantsAgreeWithTheirVotes.** A working participant has not voted, a prepared one voted yes, a no voter has aborted, and a yes voter that aborted did so on the coordinator's say-so.
- **CommitNeedsEveryVote.** The coordinator commits only once every vote is counted and yes.

`Atomicity` alone is not inductive: a state with the coordinator committed and a vote still in flight satisfies it, and one step later the vote is counted as a no. `Inductive` is, and `TwoPhaseCommitInductive.cfg` has TLC check it the way the [Raft model's](#the-raft-election-model) inductive configuration does: the invariant as the initial predicate, every state it admits, one step of `Next`, the conjuncts listed one by one so that TLC names the one that fails. It admits 736 states against 728 reachable, which is how close four conjuncts about the votes come to describing the protocol. The proof of `TwoPhase` in Lamport and Gray's paper rests on an invariant of the same shape, about the messages that have been sent; a message-passing model's invariant is inductive once it says what a message in flight means about its sender.

What the model leaves out: one transaction; messages can be reordered but not lost or duplicated; the coordinator's decision is a broadcast every participant can read. A participant that voted yes cannot give up, which is the blocking property of the protocol.

### Run it

```bash
cd examples/demo/apps/quorum
jvmcontract tla src/contract/Coordinator.decide.contract spec/CoordinatorContract.tla
jvmcontract tlc spec/TwoPhaseCommit.tla --library ../../tools/tla/standard-modules
jvmcontract tlc spec/TwoPhaseCommit.tla --config spec/TwoPhaseCommitInductive.cfg --library ../../tools/tla/standard-modules
```

TLC checks 728 states in about a second, and the 736 states the inductive invariant admits in another; an example of this model is checked under both configurations, and its verdict is the first that fails. [Example 020](../../../020-coordinator-that-presumes-commit-on-timeout/README.md) shows a three-step counterexample; [example 021](../../../021-aborting-on-the-first-no-proved-safe/README.md) shows an intended change proved safe. [Example 057](../../../057-coordinator-that-waits-for-the-last-yes-vote-blocks-forever/README.md) shows a liveness counterexample, a coordinator that never decides; [example 058](../../../058-grace-period-for-the-last-vote-proved-live-and-a-refinement/README.md) shows a change proved live and still a refinement of transaction commit, with the inductive invariant told about the new phase. [Example 067](../../../067-coordinator-that-commits-after-aborting-when-late-votes-are-all-yes/README.md) shows a coordinator that commits after aborting on timeout, found as a nine-step run and as the one step that leaves the invariant; [example 068](../../../068-coordinator-that-answers-a-late-vote-with-its-decision-proved-safe/README.md) shows a coordinator that answers late votes with its decision again, proved safe by search and by induction.

## The Raft election model

A TLA+ model of Raft leader election (Ongaro and Ousterhout, section 5.2) around the Quorum role machine: the servers, their terms and votes, and the RPCs between them.
TLC explores every interleaving for the servers and terms in `RaftElection.cfg`, checks the invariants in every state it reaches, and checks two action properties on every step. Three more configurations check the same model other ways: `RaftElectionInductive.cfg` checks that the invariant `Inductive` is inductive, `RaftElectionFour.cfg` checks four servers under a symmetry set, and `RaftElectionLive.cfg` checks two liveness properties under fairness conditions.

| File | Content |
|---|---|
| [`RaftElection.tla`](RaftElection.tla) | The model. One action per operation of a server: its election timer fires; it canvasses one server for a vote; it sends one server a heartbeat. An RPC is one step, the request and its reply together, and the request and the reply each go through the role machine. Each action names the Java operation it stands for |
| [`RaftElection.cfg`](RaftElection.cfg) | The bounds TLC checks: three servers and three terms, the list of invariants, and the two action properties |
| [`RaftElectionInductive.cfg`](RaftElectionInductive.cfg) | The inductive step: `INIT InductiveInit` in place of `SPECIFICATION Spec`, so that TLC starts from every state the invariant `Inductive` admits, reachable or not, takes one step, and checks each conjunct again |
| [`RaftElectionFour.cfg`](RaftElectionFour.cfg) | Four servers, where a candidate can hold a vote besides its own and still be short of a majority, under `SYMMETRY Perms`: of the states that differ only by a permutation of the servers' names, TLC explores one |
| [`RaftElectionLive.cfg`](RaftElectionLive.cfg) | The liveness check: `SPECIFICATION LiveSpec`, the model under its fairness conditions, with the two liveness properties after the invariants and the action properties. A counterexample is a run that goes on forever |
| [`RaftElectionEnabled.cfg`](RaftElectionEnabled.cfg) | A check of the model itself: that the enabling predicates the fairness conditions use agree with TLC's `ENABLED` in every reachable state. Slow by design, run after changing an action |
| [`RoleMachineContract.tla`](RoleMachineContract.tla) | **Generated.** A server's role transitions, as the TLA+ operator `Decide(role, event)`, written by `jvmcontract tla` from the [behavioural contract](../src/contract/RoleMachine.decide.contract) of `RoleMachine#decide`. The role machine sees a message's term only as it compares with the server's own (`NEWER`, `CURRENT`, `OLDER`), as the Java does |

The vote itself is `VoteRule.grant` written in TLA+ without the log comparison: a candidate from the past is refused, and otherwise the vote is granted when the candidate's term is ahead of the voter's, or the voter has not voted in its term, or voted for this candidate. That rule is stated for a voter that has already adopted the candidate's term, which is what the role machine does on a request from a newer term; example 059 is what happens when it stops doing so.

The invariants:

- **ElectionSafety.** At most one leader per term (figure 3 of the paper).
- **LeaderHasAMajority.** A leader holds the votes of a majority of the servers, its own among them.
- **KernelNeverThrows.** No timeout or RPC any reachable state allows makes the role machine throw. The Java throws `IllegalStateException` on one input, a leader hearing a leader of its own term, which is a claim that the input never occurs. Each action computes its next state as a record that says whether a decision it goes through is `Throws`, and takes no such step; the invariant says there is never one to take, so the claim is checked rather than assumed, in every configuration. The inductive configuration lists it as well, so that TLC says whether `Inductive` implies it: on the committed kernel it does, by election safety.
- **TypeOK.**

The action properties, `[][A]_vars` formulas that TLC checks on every step rather than on every state:

- **TermsNeverDecrease.** `[][\A s \in Servers : currentTerm'[s] >= currentTerm[s]]_vars`.
- **LeadersNeverCampaign.** `[][\A s \in Servers : role[s] = "LEADER" => role'[s] # "CANDIDATE"]_vars`: a leader leaves office as the follower of a newer term, or by stepping down, never by starting an election against itself. The states on either side of such a step are states the protocol allows, a leader in one term and a candidate in the next, which is why no invariant can state this and the model states it as a property of steps. TLC reports an action property by name, and its counterexample is the run up to the offending step.

The inductive invariant, `Inductive`, is what makes election safety true, written out: the invariants above and five more, each a reason two leaders cannot share a term.

- **VotesAreBound.** A vote in a tally was cast in the tally's term: the voter is still in that term and voted for the tally's owner, or has since moved to a newer term.
- **TalliesOfATermAreDisjoint.** No server's vote is in two tallies of one term.
- **CampaignersVoteForThemselves.** A candidate or leader voted for itself in its term, and holds its own vote.
- **TalliesHoldTheirOwnersVote.** A tally is empty, or holds its owner's vote and its owner voted for itself.
- **TermZeroIsQuiet.** Nothing happens in term 0.

`ElectionSafety` alone is not inductive: a state with two candidates of one term, each one vote short, satisfies it, and one step does not. `Inductive` is: from any state it admits, every step of `Next` lands in a state it admits, which `RaftElectionInductive.cfg` has TLC check by using the invariant as the initial predicate (Lamport, [Using TLC to Check Inductive Invariance](https://lamport.azurewebsites.net/tla/inductive-invariant.pdf)). Since `Init` satisfies it and it implies `ElectionSafety`, that proves election safety by induction, for every run of the configured cluster however long; it is the form of argument that carries over to any cluster size, where exploring the runs does not. `InductiveInit` is the same predicate written so that TLC can enumerate it: each variable drawn from its type, each conjunct placed right after the last variable it mentions, so that a partial state is dropped as soon as one fails. A counterexample is one step from a state that need not be reachable, so it is either a bug or a conjunct too strong for a correct change, and the configurations that run from `Init` tell which. The conjuncts are listed one by one in the configuration, so that TLC names the one that fails.

The liveness properties, checked by `RaftElectionLive.cfg` under `Fairness`, which says what each server is assumed to get round to: a server whose election timer nothing resets times out (a leader's timer is off, and a leader's heartbeats, when the server accepts them, reset it: `Unled`), a candidate with a vote to ask for asks, a leader with a heartbeat to send sends it. Nothing is assumed about which timer fires first or how often.

- **ALeaderIsElected.** `WithinTheBudget => <>(\E s \in Servers : role[s] = "LEADER")`: a run in which every term stays below `MaxTerm` elects a leader. With no leader, every server's timer keeps firing and each firing starts a term, so the only runs without a leader are the ones that spend the budget; a run in which the terms stop and no leader comes is a cluster that has stopped trying. The condition is what a model without a clock can state: Raft elects a leader by randomizing the timeouts so that eventually one fires alone, and every term can split, so no number of terms is enough in every run. The property is not vacuous: the stronger `\A s : WithinTheBudget => <>(role[s] = "LEADER")` fails, so runs within the budget exist.
- **StaleLeadersStepDown.** `(role[l] = "LEADER" /\ \E s : currentTerm[s] > currentTerm[l]) ~> role[l] # "LEADER"`: a leader whose term the cluster has left steps down, told by its heartbeat to a server with a newer term, or by that server's request for a vote.

Each fairness condition is weak fairness, `WF_vars(A)`, written out as TLA+ defines it: `<>[]CanA => []<><<A>>_vars`, if `A` is enabled from some point on, it happens infinitely often, with the enabling condition stated as a predicate (`CanTimeout`, `CanCanvass`, `CanHeartbeat`: the action's guard, and a step that changes some variable). Written with `WF_vars` itself, the check took TLC a minute on 610 states: `ENABLED` of an action with the role machine inside it is computed symbolically, once per step of the liveness check. The predicates are the same condition evaluated directly, each action computes its next state as a record (`TimeoutNext` and the others) so that the step and the predicate are one computation, and `RaftElectionEnabled.cfg` checks that the predicates agree with `ENABLED` in every reachable state. The liveness configuration has no symmetry set, since TLC's liveness checking is unsound under one.

What the model leaves out: the log, so there is no election restriction and a heartbeat is an empty AppendEntries; message delay, since an RPC is one step, so a server always answers with the term it has now and a stale server learns of a newer term the moment it talks to one that has it; and time, which is why the liveness property is conditioned on the term budget. Terms stop at `MaxTerm`, past which no timer fires.

### Run it

```bash
cd examples/demo/apps/quorum
jvmcontract tla src/contract/RoleMachine.decide.contract spec/RoleMachineContract.tla
jvmcontract tlc spec/RaftElection.tla --library ../../tools/tla/standard-modules
jvmcontract tlc spec/RaftElection.tla --config spec/RaftElectionInductive.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/RaftElection.tla --config spec/RaftElectionFour.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/RaftElection.tla --config spec/RaftElectionLive.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/RaftElection.tla --config spec/RaftElectionEnabled.cfg --library ../../tools/tla/standard-modules   # after changing an action; about 45 s
```

TLC checks 610 states in under a second, the 17,470 states the inductive invariant admits in about four seconds, 829 states of four servers in a second (16,974 without the symmetry set), and the 610 states again with their liveness properties in a second. An example of this model is checked under all four configurations, and its verdict is the first that fails. [Example 059](../../../059-vote-granted-without-adopting-the-term-elects-two-leaders/README.md) shows a five-step run to two leaders in one term; [example 060](../../../060-one-timeout-rule-makes-a-leader-campaign-against-itself/README.md) shows an action property violated by a step between two unremarkable states; [example 061](../../../061-leader-that-steps-down-on-its-own-timeout-proved-safe/README.md) shows a leader that steps down on its own timer, proved safe in 1,153 states. [Example 062](../../../062-candidate-that-retries-without-voting-again-elects-two-leaders/README.md) shows a candidate that retries without voting for itself again, found three ways: a seven-step run of three servers, the one step that breaks `CampaignersVoteForThemselves`, and an eight-step run of four servers in which a vote of term 1 is counted in term 2; [example 063](../../../063-candidate-that-retries-in-the-same-term-proved-safe-but-not-live/README.md) shows a candidate that retries in the same term, proved safe under the three safety configurations, and the run the liveness check finds: three candidates of term 1 asking each other forever. [Example 064](../../../064-candidate-that-stands-down-on-a-timeout-proved-safe-and-live/README.md) shows a candidate that stands down on a timeout instead, proved safe and live under all four; [example 065](../../../065-leader-that-ignores-vote-requests-from-newer-terms-votes-twice/README.md) shows a leader that ignores vote requests from newer terms and so votes twice in a term, found by the three safety configurations and reported once more by the fourth. [Example 066](../../../066-leader-that-treats-a-vote-request-of-its-term-as-impossible-crashes/README.md) shows a leader that treats a vote request of its own term as impossible and throws, an exception the model reaches in four steps, through a split vote, and that the inductive invariant admits outright.

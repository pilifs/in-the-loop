# Quorum

A small library of the decision kernels a replicated system is built from, written as pure functions so that they can be proved, and so that a deterministic simulator can drive a whole cluster of them through seeded runs and replay any failure.
It is the second subject system of the [examples](../../README.md) (013 onwards), and the one verified by [`jvmcontract`](../../../lib/README.md), the Rust tool, rather than by the Java proof of concept.

The design rule is the one deterministic-simulation-tested systems follow: a kernel takes its inputs as arguments (the clock reading, the vote, the message's term) and returns a decision; nothing below the simulator reads a clock, a random source or a socket of its own. Every kernel is therefore a function, and every function here has a contract, a property, or a model checked on every build.

## The kernels

| Kernel | What it decides | Verified by | Examples |
|---|---|---|---|
| [`Quorum`](src/main/java/net/terminalvalue/quorum/Quorum.java) | The majority of a cluster of `n` | A property: any two majorities share a node, for every `n` | 015 |
| [`raft.RoleMachine`](src/main/java/net/terminalvalue/quorum/raft/RoleMachine.java) | A Raft server's role transitions (follower, candidate, leader) | A [behavioural contract](src/contract/RoleMachine.decide.contract): all 52 (role, event) cases, and a [TLA+ model](spec/README.md#the-raft-election-model) of leader election around it, checked by TLC for election safety, for the kernels' exceptions being unreachable, and for two action properties under seven configurations: three servers, the inductive step of an inductive invariant, four servers under a symmetry set, liveness under fairness, a server left behind by a deposed leader, vote replies that wait on the wire, and a history of every term led and every vote cast, for what the paper claims of a whole run; TLC's coverage says which of the 36 rows a step of the model takes under each (27 with three servers, 33 with delayed replies) and which none does, so that a change on a row the model never exercises is reported as verified vacuously | 014, 059 to 066, 074, 081 to 086 |
| [`raft.VoteRule`](src/main/java/net/terminalvalue/quorum/raft/VoteRule.java) | Whether a server grants its vote (the election restriction) | A [behavioural contract](src/contract/VoteRule.decide.contract) of the rule proper, `decide`: all 40 (ballot, request) cases, the second generated operator of the election model, which checks it under a configuration in which one server's log is behind; three [property proofs](src/contract/properties.contract) of the arithmetic around it, `grant`: one vote per term, no vote for the past, the election restriction; and regression proofs against the previous version, over 2^448 inputs; TLC's coverage shows the steps of the model taking 4 of the 40 rows with three servers and 12 with a server left behind, the rest being the model's abstractions written out | 013, 069 to 074 |
| [`raft.AppendRule`](src/main/java/net/terminalvalue/quorum/raft/AppendRule.java) | What a Raft follower does with the entries a leader sends: the consistency check, the append in place of what it held, and its commit index following the leader's | A [behavioural contract](src/contract/AppendRule.decide.contract): all 36 (match, request) cases, and the generated operator of a [TLA+ model of log replication](spec/README.md#the-raft-replication-model) with the logs live, checked by TLC for log matching, leader completeness and state machine safety and for three action properties under two configurations, three terms with two entries and the four terms of the paper's figure 8, for liveness under a third and with replies delayed and repeated under a fourth; TLC's coverage says which of the 24 rows a step takes under each (16 with two entries, 10 with one, 10 with delayed replies) | 096, 098 to 101 |
| [`raft.ReplyRule`](src/main/java/net/terminalvalue/quorum/raft/ReplyRule.java) | What a Raft leader does with a follower's reply: the match and next indices move up on an acceptance, the next index backs up by one on a refusal, and a reply the record reflects already changes nothing | A [behavioural contract](src/contract/ReplyRule.decide.contract): all 9 (status, reply) cases, the replication model's third generated operator, which checks it under all four configurations, the delayed replies one being the one that hands it late and repeated replies and checks the two invariants of the leader's record; steps take 3 of its 4 rows under a one-step RPC and all 4 with replies delayed | 102 to 104 |
| [`raft.CommitRule`](src/main/java/net/terminalvalue/quorum/raft/CommitRule.java) | When a Raft leader marks an entry committed: a majority holds it, and it is from the leader's own term | A [behavioural contract](src/contract/CommitRule.decide.contract): all 21 (status, replication) cases, the replication model's second generated operator, which checks it under the four configurations, the figure 8 one being the smallest that shows why an earlier term's entry is never committed by counting; steps take 4 of its 12 rows, the two that throw being proved unreachable | 097 |
| [`backoff.Backoff`](src/main/java/net/terminalvalue/quorum/backoff/Backoff.java) | The delay before a retry | A property: between the base and the cap, and never shorter than the previous attempt | 016, 019 |
| [`clock.HybridLogicalClock`](src/main/java/net/terminalvalue/quorum/clock/HybridLogicalClock.java) | Timestamps that track physical time and order causally related events | Properties: a new timestamp is later than everything it saw, and `receive` is symmetric | 017, 018 |
| [`replication.LastWriterWins`](src/main/java/net/terminalvalue/quorum/replication/LastWriterWins.java) | Which of two concurrent writes a replica keeps | A law: `winner(a, b) == 1 - winner(b, a)`, so that replicas converge | 022 |
| [`twopc.Coordinator`](src/main/java/net/terminalvalue/quorum/twopc/Coordinator.java) | A two-phase-commit coordinator's decision | A [behavioural contract](src/contract/Coordinator.decide.contract), and a [TLA+ model](spec/README.md) of the protocol around it, checked by TLC for its invariants, its liveness and its refinement of transaction commit, under a second configuration for an inductive invariant about the votes counted and in flight, and under two more in which the coordinator crashes and restarts | 020, 021, 057, 058, 067, 068 |
| [`twopc.Recovery`](src/main/java/net/terminalvalue/quorum/twopc/Recovery.java) | What a restarted coordinator does with the phase it logged | A [behavioural contract](src/contract/Recovery.decide.contract), the second generated operator of the two-phase-commit model, which checks it under two configurations in which the coordinator crashes between steps or between logging a decision and sending it, over every run and by induction | 087 to 089 |
| [`twopc.Participant`](src/main/java/net/terminalvalue/quorum/twopc/Participant.java) | What a two-phase-commit participant does when asked to prepare, when it gives up, when it reads the decision, and when it restarts | A [behavioural contract](src/contract/Participant.decide.contract), the third generated operator of the two-phase-commit model, which checks it under two configurations in which the participants crash between steps or between logging a vote and sending it, over every run and by induction | 092, 093, 095 |
| [`twopc.CoordinatorNode`](src/main/java/net/terminalvalue/quorum/twopc/CoordinatorNode.java), [`twopc.ParticipantNode`](src/main/java/net/terminalvalue/quorum/twopc/ParticipantNode.java) | The nodes around the rules: the coordinator's tally, log and broadcast, and the participants' logs and votes | Trace validation: the nodes' runs through scripted scenarios with crashes of either process injected, recorded by [`Traces`](src/test/java/net/terminalvalue/quorum/twopc/Traces.java) and held to the two-phase-commit model's next-state relation under its last configuration, [`TwoPhaseCommitTrace.cfg`](spec/TwoPhaseCommitTrace.cfg) | 090, 091, 094 |

The module as a whole has a [capability contract](src/contract/capabilities.contract) (every capability is `none`: no clock, no randomness, no threads, no I/O, which is the determinism guarantee written down) and an [API contract](src/contract/api.contract).

## Layout

```
src/main/java/        the kernels
src/test/java/        plain tests, run by Tests.main; no framework, no build system
src/contract/         the contracts the build checks:
  *.decide.contract     behavioural contracts of the kernels (generated by `jvmcontract update`)
  properties.contract   the properties proved by JBMC (written by hand; the proofs are regenerated)
  capabilities.contract what the module's bytecode can reach (generated)
  api.contract          the public surface (generated)
spec/                 the TLA+ models of two-phase commit, of Raft leader election and of Raft log replication, the last two checked for liveness under fairness as well; CoordinatorContract.tla, RecoveryContract.tla, ParticipantContract.tla, RoleMachineContract.tla, VoteRuleContract.tla, AppendRuleContract.tla, ReplyRuleContract.tla and CommitRuleContract.tla are generated from the contracts, TwoPhaseCommitTraces.tla from the nodes' recorded runs
verify.sh             compile, test, and run every check below
```

## Verify it

```bash
examples/apps/quorum/verify.sh
```

which is, step by step (from this directory, with `jvmcontract` on the `PATH`, as `cargo install --path ../../../lib` puts it):

```bash
javac -parameters -g -d build/main $(find src/main/java -name '*.java')
javac -parameters -g -cp build/main -d build/test $(find src/test/java -name '*.java')
java -ea -cp build/main:build/test net.terminalvalue.quorum.Tests

jvmcontract verify --contracts src/contract --classes build/main --module quorum --sources src/main/java
jvmcontract prove --properties src/contract/properties.contract --classes build/main
jvmcontract tla src/contract/Coordinator.decide.contract spec/CoordinatorContract.tla
jvmcontract tla src/contract/Recovery.decide.contract spec/RecoveryContract.tla
jvmcontract tla src/contract/Participant.decide.contract spec/ParticipantContract.tla
jvmcontract tlc spec/TwoPhaseCommit.tla --library ../../tools/tla/standard-modules
jvmcontract tlc spec/TwoPhaseCommit.tla --config spec/TwoPhaseCommitInductive.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/TwoPhaseCommit.tla --config spec/TwoPhaseCommitCrash.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/TwoPhaseCommit.tla --config spec/TwoPhaseCommitCrashInductive.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/TwoPhaseCommit.tla --config spec/TwoPhaseCommitParticipantCrash.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/TwoPhaseCommit.tla --config spec/TwoPhaseCommitParticipantCrashInductive.cfg --library ../../tools/tla/standard-modules
java -cp build/main:build/test net.terminalvalue.quorum.twopc.Traces > spec/TwoPhaseCommitTraces.tla
jvmcontract tlc spec/TwoPhaseCommitTrace.tla --config spec/TwoPhaseCommitTrace.cfg --library ../../tools/tla/standard-modules
jvmcontract tla src/contract/RoleMachine.decide.contract spec/RoleMachineContract.tla
jvmcontract tla src/contract/VoteRule.decide.contract spec/VoteRuleContract.tla
jvmcontract tlc spec/RaftElection.tla --coverage --library ../../tools/tla/standard-modules   # --coverage: the rows of each generated operator a step takes, and the rows none does
jvmcontract tlc spec/RaftElection.tla --config spec/RaftElectionInductive.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/RaftElection.tla --config spec/RaftElectionFour.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/RaftElection.tla --config spec/RaftElectionLive.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/RaftElection.tla --config spec/RaftElectionLogs.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/RaftElection.tla --config spec/RaftElectionDelayed.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/RaftElection.tla --config spec/RaftElectionHistory.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/RaftElection.tla --config spec/RaftElectionEnabled.cfg --library ../../tools/tla/standard-modules
jvmcontract tla src/contract/AppendRule.decide.contract spec/AppendRuleContract.tla
jvmcontract tla src/contract/ReplyRule.decide.contract spec/ReplyRuleContract.tla
jvmcontract tla src/contract/CommitRule.decide.contract spec/CommitRuleContract.tla
jvmcontract tlc spec/RaftReplication.tla --library ../../tools/tla/standard-modules
jvmcontract tlc spec/RaftReplication.tla --config spec/RaftReplicationFigureEight.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/RaftReplication.tla --config spec/RaftReplicationLive.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/RaftReplication.tla --config spec/RaftReplicationDelayed.cfg --library ../../tools/tla/standard-modules
jvmcontract tlc spec/RaftReplication.tla --config spec/RaftReplicationEnabled.cfg --library ../../tools/tla/standard-modules
```

Compiling takes a second, the tests less, the contract check milliseconds, the eight property proofs about five seconds with JBMC, and TLC about a second for each model (728 states of two-phase commit, 736 that its inductive invariant admits, 3,448 with the coordinator crashing and 2,728 that the invariant admits with crashes, 610 of the election, 829 of the election with four servers, 610 again for its liveness, 461 with a server left behind), about three seconds for the 20,351 states of the election with delayed replies, a second for the 4,798 states of the election with its history recording, about four seconds for the inductive step of the election (17,470 states the invariant admits), about four seconds for the 20,253 states of log replication and two for the 8,838 of its figure 8 configuration, about a minute for the 14,388 states of its liveness configuration (three terms and one entry, no symmetry set), about three minutes for the 261,060 states of its delayed replies configuration, and about two and four minutes (the latter with two workers) for the two checks that the election and replication models' enabling predicates agree with TLC's `ENABLED` in every state, which is the reason the fairness conditions use predicates rather than `ENABLED`.
No Gradle and no JVM start is needed for the contracts: `jvmcontract` reads the class files and the JDK's image directly.

To change a kernel's behaviour on purpose: make the change, run `jvmcontract update --contracts src/contract --classes build/main --module quorum`, and commit the contract diff with the code. To state a new guarantee: add a block to `properties.contract`.

#!/usr/bin/env bash
# Compiles the Quorum module, runs its tests, and runs every check jvmcontract provides for it: the behavioural,
# capability and API contracts, the property proofs (JBMC), and the two-phase-commit and Raft election models (TLC),
# the former under four configurations and the latter under seven, plus a check that the election model's enabling
# predicates agree with ENABLED, and the trace check of the two-phase-commit nodes: their recorded runs, held to the
# model's next-state relation.
# Needs javac and java on the PATH, jvmcontract (on the PATH, or $JVMCONTRACT, or built in ../../../lib), jbmc, and
# tla2tools.jar in ~/tools or $TLA2TOOLS_JAR.
set -euo pipefail
cd "$(dirname "$0")"

JVMCONTRACT="${JVMCONTRACT:-$(command -v jvmcontract || echo ../../../lib/target/release/jvmcontract)}"
if [ ! -x "$JVMCONTRACT" ]; then
    echo "jvmcontract not found: cargo build --release --manifest-path ../../../lib/Cargo.toml, or set JVMCONTRACT" >&2
    exit 2
fi

rm -rf build
javac -parameters -g -proc:none -d build/main $(find src/main/java -name '*.java')
javac -parameters -g -proc:none -cp build/main -d build/test $(find src/test/java -name '*.java')
java -ea -cp "build/main:build/test" net.terminalvalue.quorum.Tests

"$JVMCONTRACT" verify --contracts src/contract --classes build/main --module quorum --sources src/main/java --report build/reports
"$JVMCONTRACT" prove --properties src/contract/properties.contract --classes build/main --sources src/main/java --report build/reports
"$JVMCONTRACT" tla src/contract/Coordinator.decide.contract spec/CoordinatorContract.tla
"$JVMCONTRACT" tla src/contract/Recovery.decide.contract spec/RecoveryContract.tla
"$JVMCONTRACT" tlc spec/TwoPhaseCommit.tla --library ../../tools/tla/standard-modules
"$JVMCONTRACT" tlc spec/TwoPhaseCommit.tla --config spec/TwoPhaseCommitInductive.cfg --library ../../tools/tla/standard-modules
"$JVMCONTRACT" tlc spec/TwoPhaseCommit.tla --config spec/TwoPhaseCommitCrash.cfg --library ../../tools/tla/standard-modules
"$JVMCONTRACT" tlc spec/TwoPhaseCommit.tla --config spec/TwoPhaseCommitCrashInductive.cfg --library ../../tools/tla/standard-modules
java -cp "build/main:build/test" net.terminalvalue.quorum.twopc.Traces > spec/TwoPhaseCommitTraces.tla
"$JVMCONTRACT" tlc spec/TwoPhaseCommitTrace.tla --config spec/TwoPhaseCommitTrace.cfg --library ../../tools/tla/standard-modules
"$JVMCONTRACT" tla src/contract/RoleMachine.decide.contract spec/RoleMachineContract.tla
"$JVMCONTRACT" tla src/contract/VoteRule.decide.contract spec/VoteRuleContract.tla
"$JVMCONTRACT" tlc spec/RaftElection.tla --library ../../tools/tla/standard-modules
"$JVMCONTRACT" tlc spec/RaftElection.tla --config spec/RaftElectionInductive.cfg --library ../../tools/tla/standard-modules
"$JVMCONTRACT" tlc spec/RaftElection.tla --config spec/RaftElectionFour.cfg --library ../../tools/tla/standard-modules
"$JVMCONTRACT" tlc spec/RaftElection.tla --config spec/RaftElectionLive.cfg --library ../../tools/tla/standard-modules
"$JVMCONTRACT" tlc spec/RaftElection.tla --config spec/RaftElectionLogs.cfg --library ../../tools/tla/standard-modules
"$JVMCONTRACT" tlc spec/RaftElection.tla --config spec/RaftElectionDelayed.cfg --library ../../tools/tla/standard-modules
"$JVMCONTRACT" tlc spec/RaftElection.tla --config spec/RaftElectionHistory.cfg --library ../../tools/tla/standard-modules
"$JVMCONTRACT" tlc spec/RaftElection.tla --config spec/RaftElectionEnabled.cfg --library ../../tools/tla/standard-modules

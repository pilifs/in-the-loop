package net.terminalvalue.quorum.twopc;

import static net.terminalvalue.quorum.Tests.check;
import static net.terminalvalue.quorum.Tests.equal;

import java.util.Map;
import java.util.Set;

/** The nodes around the rules: the coordinator's log and broadcast, the participants' logs and votes, and a crash between a log write and a send. */
public final class NodesTest {

    private NodesTest() {}

    private static final Set<String> ALL = Set.of("p1", "p2", "p3");

    public static void commitsOnceEveryVoteIsYes() {
        Faults faults = new Faults();
        Network network = new Network(faults);
        CoordinatorNode coordinator = new CoordinatorNode(ALL, new CoordinatorLog(faults), network);
        ParticipantNode p1 = participant("p1", network);
        p1.prepare(true);
        coordinator.onVote(network.deliver("p1"));
        equal(Outcome.NONE, network.decision());
        coordinator.onVote(new VoteMessage("p2", Vote.YES));
        coordinator.onVote(new VoteMessage("p3", Vote.YES));
        equal(Phase.COMMITTED, coordinator.phase());
        equal(Outcome.COMMIT, network.decision());
        check(p1.learn(), "p1 learns the decision");
        equal(ParticipantState.COMMITTED, p1.state());
    }

    public static void abortsOnceEveryVoteIsInAndOneIsNo() {
        Faults faults = new Faults();
        Network network = new Network(faults);
        CoordinatorNode coordinator = new CoordinatorNode(ALL, new CoordinatorLog(faults), network);
        coordinator.onVote(new VoteMessage("p2", Vote.NO));
        equal(Phase.COLLECTING, coordinator.phase());
        equal(Map.of("p2", Vote.NO), coordinator.tally());
        coordinator.onVote(new VoteMessage("p1", Vote.YES));
        coordinator.onVote(new VoteMessage("p3", Vote.YES));
        equal(Phase.ABORTED, coordinator.phase());
        equal(Outcome.ABORT, network.decision());
    }

    public static void abortsOnTheTimerWithAVoteMissing() {
        Faults faults = new Faults();
        Network network = new Network(faults);
        CoordinatorNode coordinator = new CoordinatorNode(ALL, new CoordinatorLog(faults), network);
        coordinator.onVote(new VoteMessage("p1", Vote.YES));
        coordinator.onTimeout();
        equal(Phase.ABORTED, coordinator.phase());
        equal(Outcome.ABORT, network.decision());
    }

    public static void aCrashAfterTheLogLosesTheBroadcastAndTheRestartSendsItAgain() {
        Faults faults = new Faults();
        CoordinatorLog log = new CoordinatorLog(faults);
        Network network = new Network(faults);
        CoordinatorNode coordinator = new CoordinatorNode(ALL, log, network);
        coordinator.onVote(new VoteMessage("p1", Vote.YES));
        coordinator.onVote(new VoteMessage("p2", Vote.YES));
        faults.crashAfter(1);
        boolean crashed = false;
        try {
            coordinator.onVote(new VoteMessage("p3", Vote.YES));
        } catch (Faults.Crashed e) {
            crashed = true;
        }
        check(crashed, "the scheduled crash happened");
        equal(Phase.COMMITTED, log.phase());
        equal(Outcome.NONE, network.decision());
        CoordinatorNode restarted = new CoordinatorNode(ALL, log, network);
        restarted.recover();
        equal(Outcome.COMMIT, network.decision());
    }

    public static void aParticipantThatGivesUpNeverVotes() {
        Network network = new Network(new Faults());
        ParticipantNode p1 = participant("p1", network);
        p1.giveUp();
        equal(ParticipantState.ABORTED, p1.state());
        check(network.inFlight().isEmpty(), "no vote in flight");
        check(!p1.learn(), "nothing to learn without a decision");
    }

    public static void aParticipantThatCrashesAfterLoggingItsYesLosesTheVoteAndRestartsPrepared() {
        Network network = new Network(new Faults());
        Faults faults = new Faults("p1");
        ParticipantLog log = new ParticipantLog(faults);
        ParticipantNode p1 = new ParticipantNode("p1", log, network, faults);
        faults.crashAfter(1);
        boolean crashed = false;
        try {
            p1.prepare(true);
        } catch (Faults.Crashed e) {
            crashed = true;
        }
        check(crashed, "the scheduled crash happened");
        equal(ParticipantState.PREPARED, log.state());
        check(network.inFlight().isEmpty(), "the vote was lost with the crash");
        ParticipantNode restarted = new ParticipantNode("p1", log, network, faults);
        restarted.recover();
        equal(ParticipantState.PREPARED, restarted.state()); // holds its locks until the coordinator decides
        check(network.inFlight().isEmpty(), "a restart sends nothing");
    }

    public static void aParticipantThatCrashesBeforeVotingRestartsAborted() {
        Network network = new Network(new Faults());
        Faults faults = new Faults("p1");
        ParticipantLog log = new ParticipantLog(faults);
        ParticipantNode restarted = new ParticipantNode("p1", log, network, faults);
        restarted.recover();
        equal(ParticipantState.ABORTED, restarted.state());
        equal(ParticipantState.ABORTED, log.state());
        check(network.inFlight().isEmpty(), "no vote went out");
    }

    private static ParticipantNode participant(String name, Network network) {
        Faults faults = new Faults(name);
        return new ParticipantNode(name, new ParticipantLog(faults), network, faults);
    }

    public static void theScriptedRunsAllFinish() {
        for (Traces.Script script : Traces.scripts()) {
            Traces.Run run = Traces.run(script);
            check(run.stopped == null, script.name + " stopped early: " + run.stopped);
            equal(script.steps.size() + 1, run.states.size());
        }
    }
}

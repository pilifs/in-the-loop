package net.terminalvalue.quorum.twopc;

import static net.terminalvalue.quorum.Tests.check;
import static net.terminalvalue.quorum.Tests.equal;

import java.util.Map;
import java.util.Set;

/** The nodes around the rules: the coordinator's log and broadcast, the participants, and a crash between the two. */
public final class NodesTest {

    private NodesTest() {}

    private static final Set<String> ALL = Set.of("p1", "p2", "p3");

    public static void commitsOnceEveryVoteIsYes() {
        Faults faults = new Faults();
        Network network = new Network(faults);
        CoordinatorNode coordinator = new CoordinatorNode(ALL, new CoordinatorLog(faults), network);
        ParticipantNode p1 = new ParticipantNode("p1", network);
        p1.prepare(true);
        coordinator.onVote(network.deliver("p1"));
        equal(Outcome.NONE, network.decision());
        coordinator.onVote(new VoteMessage("p2", Vote.YES));
        coordinator.onVote(new VoteMessage("p3", Vote.YES));
        equal(Phase.COMMITTED, coordinator.phase());
        equal(Outcome.COMMIT, network.decision());
        check(p1.learn(), "p1 learns the decision");
        equal(ParticipantNode.State.COMMITTED, p1.state());
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
        ParticipantNode p1 = new ParticipantNode("p1", network);
        p1.giveUp();
        equal(ParticipantNode.State.ABORTED, p1.state());
        check(network.inFlight().isEmpty(), "no vote in flight");
        check(!p1.learn(), "nothing to learn without a decision");
    }

    public static void theScriptedRunsAllFinish() {
        for (Traces.Script script : Traces.scripts()) {
            Traces.Run run = Traces.run(script);
            check(run.stopped == null, script.name + " stopped early: " + run.stopped);
            equal(script.steps.size() + 1, run.states.size());
        }
    }
}

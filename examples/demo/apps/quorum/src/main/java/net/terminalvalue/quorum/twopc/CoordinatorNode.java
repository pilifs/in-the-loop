package net.terminalvalue.quorum.twopc;

import java.util.Collection;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import net.terminalvalue.quorum.Decision;
import net.terminalvalue.quorum.Decision.Transition;
import net.terminalvalue.quorum.Decision.Unchanged;
import net.terminalvalue.quorum.twopc.CoordinatorEvent.Tally;
import net.terminalvalue.quorum.twopc.CoordinatorEvent.Timeout;
import net.terminalvalue.quorum.twopc.RecoveryEvent.Restarted;

/**
 * The coordinator as a process: the glue around {@link Coordinator#decide} and {@link Recovery#decide}. It keeps
 * the tally, builds the event each rule decides on, and carries the decision out: the phase change and the tally go
 * to the log first, then the decision goes out on the network, so that a crash between the two loses the broadcast
 * and not the decision, which the restart sends again. The rules are verified against their contracts and the
 * protocol around them is model checked; this class is what the trace check holds to the model.
 */
public final class CoordinatorNode {

    private final Set<String> participants;
    private final CoordinatorLog log;
    private final Network network;
    private Phase phase;
    private final Map<String, Vote> tally;

    /** A coordinator process starting, or restarting, from what its log holds. */
    public CoordinatorNode(Set<String> participants, CoordinatorLog log, Network network) {
        this.participants = Set.copyOf(participants);
        this.log = log;
        this.network = network;
        this.phase = log.phase();
        this.tally = new TreeMap<>(log.tally());
    }

    public Phase phase() {
        return phase;
    }

    public Map<String, Vote> tally() {
        return Map.copyOf(tally);
    }

    /** Coordinator.onVote: a vote arrives; count it, then decide on the tally. */
    public void onVote(VoteMessage message) {
        tally.put(message.from(), message.vote());
        boolean complete = tally.keySet().containsAll(participants);
        act(Coordinator.decide(phase, new Tally(complete, unanimous(tally.values()))));
    }

    /** Coordinator.onTimeout: the collection timer fires. */
    public void onTimeout() {
        act(Coordinator.decide(phase, new Timeout(unanimous(tally.values()))));
    }

    /** Recovery.decide: a restarted coordinator acts on the phase it logged. */
    public void recover() {
        act(Recovery.decide(phase, new Restarted()));
    }

    private static boolean unanimous(Collection<Vote> votes) {
        return votes.stream().allMatch(v -> v == Vote.YES);
    }

    private void act(Decision<Phase, CoordinatorEffect> decision) {
        switch (decision) {
            case Transition<Phase, CoordinatorEffect> t -> {
                phase = t.next();
                log.write(phase, tally); // logged before it is acted on: a crash from here on loses the broadcast only
                for (CoordinatorEffect effect : t.effects()) {
                    network.broadcast(effect == CoordinatorEffect.SEND_COMMIT ? Outcome.COMMIT : Outcome.ABORT);
                }
            }
            case Unchanged<Phase, CoordinatorEffect> u -> log.write(phase, tally); // the tally is logged with every vote
            case Decision.Rejected<Phase, CoordinatorEffect> r -> throw new IllegalStateException(r.reason());
        }
    }
}

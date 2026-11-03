package net.terminalvalue.quorum.twopc;

import net.terminalvalue.quorum.Decision;
import net.terminalvalue.quorum.Decision.Transition;
import net.terminalvalue.quorum.Decision.Unchanged;
import net.terminalvalue.quorum.twopc.ParticipantEvent.GiveUp;
import net.terminalvalue.quorum.twopc.ParticipantEvent.Learned;
import net.terminalvalue.quorum.twopc.ParticipantEvent.Prepare;
import net.terminalvalue.quorum.twopc.ParticipantEvent.Restarted;

/**
 * A participant as a process: the glue around {@link Participant#decide}. It builds the event the rule decides on
 * and carries the decision out: the state change goes to the log first, then the vote goes out on the network, so
 * that a crash between the two loses the vote and not the state, which the restart acts on. The rule is verified
 * against its contract and the protocol around it is model checked; this class is what the trace check holds to
 * the model.
 */
public final class ParticipantNode {

    private final String name;
    private final ParticipantLog log;
    private final Network network;
    private final Faults faults;
    private ParticipantState state;

    /** A participant process starting, or restarting, from what its log holds. */
    public ParticipantNode(String name, ParticipantLog log, Network network, Faults faults) {
        this.name = name;
        this.log = log;
        this.network = network;
        this.faults = faults;
        this.state = log.state();
    }

    public String name() {
        return name;
    }

    public ParticipantState state() {
        return state;
    }

    /** Participant.prepare: asked to prepare, the participant can do its part and votes yes, or cannot, votes no and aborts. */
    public void prepare(boolean able) {
        act(Participant.decide(state, new Prepare(able)));
    }

    /** Participant.timeout: a participant that has not voted gives up on its own, and then never votes. */
    public void giveUp() {
        act(Participant.decide(state, new GiveUp()));
    }

    /** Participant.learn: applies the coordinator's decision if one is out; says whether it did. */
    public boolean learn() {
        return act(Participant.decide(state, new Learned(network.decision())));
    }

    /** Participant.recover: a restarted participant acts on the state it logged. */
    public void recover() {
        act(Participant.decide(state, new Restarted()));
    }

    private boolean act(Decision<ParticipantState, ParticipantEffect> decision) {
        return switch (decision) {
            case Transition<ParticipantState, ParticipantEffect> t -> {
                state = t.next();
                log.write(state); // logged before the vote goes out: a crash from here on loses the vote only
                for (ParticipantEffect effect : t.effects()) {
                    network.send(new VoteMessage(name, effect == ParticipantEffect.VOTE_YES ? Vote.YES : Vote.NO), faults);
                }
                yield true;
            }
            case Unchanged<ParticipantState, ParticipantEffect> u -> false;
            case Decision.Rejected<ParticipantState, ParticipantEffect> r -> throw new IllegalStateException(name + ": " + r.reason());
        };
    }
}

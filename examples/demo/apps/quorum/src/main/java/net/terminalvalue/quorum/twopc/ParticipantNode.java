package net.terminalvalue.quorum.twopc;

/**
 * A participant as a process: it votes when asked to prepare, may give up while it has not voted, and applies the
 * coordinator's decision once it is out. A participant that voted yes holds its locks until then.
 */
public final class ParticipantNode {

    public enum State {
        WORKING,
        PREPARED,
        COMMITTED,
        ABORTED
    }

    private final String name;
    private final Network network;
    private State state = State.WORKING;

    public ParticipantNode(String name, Network network) {
        this.name = name;
        this.network = network;
    }

    public String name() {
        return name;
    }

    public State state() {
        return state;
    }

    /** Participant.prepare: the participant can do its part and votes yes, or cannot, votes no and aborts. */
    public void prepare(boolean able) {
        if (state != State.WORKING) {
            throw new IllegalStateException(name + " has already voted");
        }
        state = able ? State.PREPARED : State.ABORTED;
        network.send(new VoteMessage(name, able ? Vote.YES : Vote.NO));
    }

    /** Participant.timeout: a participant that has not voted gives up on its own, and then never votes. */
    public void giveUp() {
        if (state != State.WORKING) {
            throw new IllegalStateException(name + " has already voted");
        }
        state = State.ABORTED;
    }

    /** Participant.learn: applies the coordinator's decision if one is out; says whether it did. */
    public boolean learn() {
        Outcome decision = network.decision();
        if (decision == Outcome.NONE || state == State.COMMITTED || state == State.ABORTED) {
            return false;
        }
        state = decision == Outcome.COMMIT ? State.COMMITTED : State.ABORTED;
        return true;
    }
}

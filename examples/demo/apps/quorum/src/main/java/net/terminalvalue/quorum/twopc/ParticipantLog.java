package net.terminalvalue.quorum.twopc;

/**
 * A participant's durable log: its state, which survives a crash. A real one is a file written before the
 * participant acts; this one stands in for it in a simulation.
 */
public final class ParticipantLog {

    private final Faults faults;
    private ParticipantState state = ParticipantState.WORKING;

    public ParticipantLog(Faults faults) {
        this.faults = faults;
    }

    /** Writes the state. */
    public void write(ParticipantState state) {
        this.state = state;
        faults.io();
    }

    public ParticipantState state() {
        return state;
    }
}

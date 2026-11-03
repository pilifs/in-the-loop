package net.terminalvalue.quorum.twopc;

import java.util.Map;

/**
 * The coordinator's durable log: its phase and the votes it has counted, which survive a crash. A real one is a
 * file written before the coordinator acts; this one stands in for it in a simulation.
 */
public final class CoordinatorLog {

    private final Faults faults;
    private Phase phase = Phase.COLLECTING;
    private Map<String, Vote> tally = Map.of();

    public CoordinatorLog(Faults faults) {
        this.faults = faults;
    }

    /** Writes the phase and the tally, as one record. */
    public void write(Phase phase, Map<String, Vote> tally) {
        this.phase = phase;
        this.tally = Map.copyOf(tally);
        faults.io();
    }

    public Phase phase() {
        return phase;
    }

    public Map<String, Vote> tally() {
        return tally;
    }
}

package net.terminalvalue.quorum.twopc;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

/**
 * The messages between the participants and the coordinator: votes on their way to the coordinator, which it takes
 * in any order, and the coordinator's decision, a broadcast every participant can read once it is out. The
 * coordinator's broadcast reports to the fault injection the network is built with, the coordinator's; a
 * participant's send reports to the participant's own.
 */
public final class Network {

    private final Faults faults;
    private final List<VoteMessage> inFlight = new ArrayList<>();
    private Outcome decision = Outcome.NONE;

    public Network(Faults faults) {
        this.faults = faults;
    }

    /** A participant sends its vote: one of its I/O operations. */
    public void send(VoteMessage message, Faults sender) {
        inFlight.add(message);
        sender.io();
    }

    /** The vote from a participant reaches the coordinator. */
    public VoteMessage deliver(String from) {
        for (Iterator<VoteMessage> it = inFlight.iterator(); it.hasNext(); ) {
            VoteMessage m = it.next();
            if (m.from().equals(from)) {
                it.remove();
                return m;
            }
        }
        throw new IllegalStateException("no vote from " + from + " in flight");
    }

    /** The coordinator sends its decision to every participant. */
    public void broadcast(Outcome outcome) {
        decision = outcome;
        faults.io();
    }

    public List<VoteMessage> inFlight() {
        return List.copyOf(inFlight);
    }

    public Outcome decision() {
        return decision;
    }
}

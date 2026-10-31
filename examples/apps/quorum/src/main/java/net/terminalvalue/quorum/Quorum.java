package net.terminalvalue.quorum;

/** Quorum arithmetic. Every consensus and replication protocol in this library rests on these two lines. */
public final class Quorum {

    private Quorum() {}

    /**
     * The smallest number of nodes that is more than half of a cluster of {@code n}. Any two majorities share a
     * node, which is what lets a new leader learn every committed entry from the nodes that elected it.
     */
    public static int majority(int n) {
        if (n <= 0) {
            throw new IllegalArgumentException("a cluster has at least one node");
        }
        return n / 2 + 1;
    }

    /** How many nodes a cluster of {@code n} can lose and still form a majority. */
    public static int faultsTolerated(int n) {
        return n - majority(n);
    }
}

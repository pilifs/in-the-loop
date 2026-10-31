package net.terminalvalue.quorum.replication;

/**
 * Last-writer-wins conflict resolution for a replicated register: given two concurrent writes, every replica must
 * pick the same one, or replicas diverge for good. The pick is by timestamp, and between equal timestamps by the
 * id of the writing node, which makes it a total order on distinct writes.
 */
public final class LastWriterWins {

    private LastWriterWins() {}

    /**
     * Which of two writes wins: {@code 0} for the first (timestamp {@code tsA} from node {@code nodeA}), {@code 1}
     * for the second. Two replicas that see the writes in either order must agree, so for distinct writes
     * {@code winner(a, b) == 1 - winner(b, a)}.
     */
    public static int winner(long tsA, int nodeA, long tsB, int nodeB) {
        if (tsA != tsB) {
            return tsA > tsB ? 0 : 1;
        }
        return nodeA >= nodeB ? 0 : 1;
    }
}

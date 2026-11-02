package net.terminalvalue.quorum.raft;

/**
 * Whether a Raft server grants its vote to a candidate (Ongaro and Ousterhout, section 5.4.1). The log comparison
 * is the election restriction: a candidate's log must be at least as up to date as the voter's, where "up to date"
 * compares the term of the last entry first and its index second. That order is what guarantees that a new leader
 * holds every committed entry.
 */
public final class VoteRule {

    /** The value of {@code votedFor} when the server has not voted in the current term. */
    public static final int NO_VOTE = -1;

    private VoteRule() {}

    /**
     * @param currentTerm the voter's current term
     * @param votedFor the candidate the voter voted for in {@code currentTerm}, or {@link #NO_VOTE}
     * @param lastLogTerm the term of the voter's last log entry
     * @param lastLogIndex the index of the voter's last log entry
     * @param candidate the candidate's id
     * @param candidateTerm the candidate's term
     * @param candidateLastLogTerm the term of the candidate's last log entry
     * @param candidateLastLogIndex the index of the candidate's last log entry
     */
    public static boolean grant(long currentTerm, int votedFor, long lastLogTerm, long lastLogIndex,
                                int candidate, long candidateTerm, long candidateLastLogTerm, long candidateLastLogIndex) {
        if (candidateTerm < currentTerm) {
            return false; // a candidate from the past
        }
        // A newer term resets the vote; in the current term, one vote per server.
        boolean free = candidateTerm > currentTerm || votedFor == NO_VOTE || votedFor == candidate;
        boolean upToDate = candidateLastLogTerm > lastLogTerm
                || (candidateLastLogTerm == lastLogTerm && candidateLastLogIndex >= lastLogIndex);
        return free && upToDate;
    }
}

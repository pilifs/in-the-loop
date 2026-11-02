package net.terminalvalue.quorum.raft;

import static net.terminalvalue.quorum.Decision.rejected;
import static net.terminalvalue.quorum.Decision.transition;
import static net.terminalvalue.quorum.raft.Ballot.FOR_THE_CANDIDATE;
import static net.terminalvalue.quorum.raft.LogOrder.AHEAD;
import static net.terminalvalue.quorum.raft.LogOrder.BEHIND;
import static net.terminalvalue.quorum.raft.LogOrder.EVEN;
import static net.terminalvalue.quorum.raft.TermOrder.CURRENT;
import static net.terminalvalue.quorum.raft.TermOrder.NEWER;
import static net.terminalvalue.quorum.raft.TermOrder.OLDER;
import static net.terminalvalue.quorum.raft.VoteEffect.GRANT;

import net.terminalvalue.quorum.Decision;

/**
 * Whether a Raft server grants its vote to a candidate (Ongaro and Ousterhout, section 5.4.1). The log comparison
 * is the election restriction: a candidate's log must be at least as up to date as the voter's, where "up to date"
 * compares the term of the last entry first and its index second. That order is what guarantees that a new leader
 * holds every committed entry.
 *
 * <p>The decision is {@link #decide}, a total function from the voter's ballot and the request, each reduced to
 * how it compares with the voter's own state; {@link #grant} does the comparing.
 */
public final class VoteRule {

    /** The value of {@code votedFor} when the server has not voted in the current term. */
    public static final int NO_VOTE = -1;

    private VoteRule() {}

    /**
     * The vote rule proper: a candidate from the past is refused; a newer term is a new vote, and in the current
     * term the vote is one per server, which the same candidate may collect again; and a candidate whose log is
     * behind the voter's is refused whatever its term.
     */
    public static Decision<Ballot, VoteEffect> decide(Ballot ballot, VoteRequest request) {
        if (request.term() == OLDER) {
            return rejected("a candidate from the past");
        }
        if (request.term() == CURRENT && ballot == Ballot.FOR_ANOTHER) {
            return rejected("one vote per term");
        }
        if (request.log() == BEHIND) {
            return rejected("a log behind the voter's");
        }
        return transition(FOR_THE_CANDIDATE, GRANT);
    }

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
        TermOrder term = candidateTerm < currentTerm ? OLDER : candidateTerm == currentTerm ? CURRENT : NEWER;
        Ballot ballot = votedFor == NO_VOTE ? Ballot.OPEN : votedFor == candidate ? FOR_THE_CANDIDATE : Ballot.FOR_ANOTHER;
        LogOrder log = candidateLastLogTerm != lastLogTerm
                ? (candidateLastLogTerm > lastLogTerm ? AHEAD : BEHIND)
                : candidateLastLogIndex > lastLogIndex ? AHEAD : candidateLastLogIndex == lastLogIndex ? EVEN : BEHIND;
        return decide(ballot, new VoteRequest(term, log)) instanceof Decision.Transition;
    }
}

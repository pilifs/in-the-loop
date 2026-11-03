package net.terminalvalue.quorum.raft;

import static net.terminalvalue.quorum.Decision.transition;
import static net.terminalvalue.quorum.Decision.unchanged;
import static net.terminalvalue.quorum.raft.CommitEffect.APPLY;
import static net.terminalvalue.quorum.raft.EntryStatus.COMMITTED;

import net.terminalvalue.quorum.Decision;

/**
 * When a Raft leader marks an entry committed (Ongaro and Ousterhout, section 5.4.2): once a majority of the servers
 * hold it, and only if it is from the leader's own term. An entry from an earlier term is never committed by
 * counting the servers that hold it, however many: a later leader without it could still be elected and overwrite
 * it (figure 8 of the paper). It is committed, with everything before it, when an entry of the current term after
 * it is.
 */
public final class CommitRule {

    private CommitRule() {}

    public static Decision<EntryStatus, CommitEffect> decide(EntryStatus status, Replication replication) {
        return switch (status) {
            case COMMITTED -> unchanged("already committed");
            case PENDING -> switch (replication.term()) {
                case NEWER -> throw new IllegalStateException("an entry from a term after the leader's");
                case OLDER -> unchanged("an entry from an earlier term is committed only along with one of the current term");
                case CURRENT -> replication.majority() ? transition(COMMITTED, APPLY) : unchanged("waiting for a majority");
            };
        };
    }
}

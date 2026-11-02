package net.terminalvalue.quorum.raft;

import static net.terminalvalue.quorum.Decision.transition;
import static net.terminalvalue.quorum.Decision.unchanged;
import static net.terminalvalue.quorum.raft.ReplyEffect.ADVANCE;
import static net.terminalvalue.quorum.raft.ReplyEffect.BACK_UP;
import static net.terminalvalue.quorum.raft.RequestStatus.ANSWERED;

import net.terminalvalue.quorum.Decision;

/**
 * What a Raft leader does with a follower's reply to an AppendEntries request (Ongaro and Ousterhout, section 5.3,
 * and the rules for leaders of figure 2): on an acceptance, the follower's match index moves up through the entries
 * sent and its next index past them; on a refusal, the next index moves back by one, and the next request tries from
 * one entry earlier, until the consistency check passes.
 *
 * <p>A reply the leader's record reflects already, a late or repeated one, changes nothing: an acceptance of entries
 * the leader knows the follower holds moves nothing backwards, and a refusal of a request the leader has moved on
 * from, or at an entry it knows the follower holds, does not back it up again. The term check comes before this
 * rule, in {@link RoleMachine}: a reply from a newer term deposes the leader, and one from an older term, to a
 * request of an earlier term of its own, is dropped.
 */
public final class ReplyRule {

    private ReplyRule() {}

    public static Decision<RequestStatus, ReplyEffect> decide(RequestStatus status, AppendReply reply) {
        return switch (status) {
            case AWAITED -> reply.accepted() ? transition(ANSWERED, ADVANCE) : transition(ANSWERED, BACK_UP);
            case ANSWERED -> reply.accepted()
                    ? unchanged("holds what the leader has recorded already")
                    : unchanged("a refusal the leader has moved on from");
        };
    }
}

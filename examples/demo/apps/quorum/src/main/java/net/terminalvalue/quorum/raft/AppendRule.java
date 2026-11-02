package net.terminalvalue.quorum.raft;

import static net.terminalvalue.quorum.Decision.rejected;
import static net.terminalvalue.quorum.Decision.transition;
import static net.terminalvalue.quorum.Decision.unchanged;
import static net.terminalvalue.quorum.raft.AppendEffect.ADVANCE_COMMIT;
import static net.terminalvalue.quorum.raft.AppendEffect.APPEND;
import static net.terminalvalue.quorum.raft.AppendEffect.TRUNCATE;
import static net.terminalvalue.quorum.raft.LogMatch.MATCHING;

import net.terminalvalue.quorum.Decision;

/**
 * What a Raft follower does with a leader's AppendEntries request (Ongaro and Ousterhout, section 5.3): the
 * consistency check first, which refuses the request unless the follower holds the entry before the ones sent, so
 * that the leader backs up and tries again from one entry earlier; then the entry sent goes in, in place of
 * whatever the follower held at its index; and the follower's commit index follows the leader's, as far as the
 * entries it now holds in common with it.
 *
 * <p>The check is what makes the log matching property hold: a follower accepts an entry only after the entry
 * before it, so two logs that agree on an entry agree on everything before it. The term check comes before this
 * rule, in {@link RoleMachine}: a stale leader's request is refused there.
 *
 * <p>The rule returns what the follower's log then is against the leader's: {@link LogMatch#MATCHING} through the
 * entry sent on a request it accepts, and a rejection otherwise.
 */
public final class AppendRule {

    private AppendRule() {}

    public static Decision<LogMatch, AppendEffect> decide(LogMatch previous, AppendRequest request) {
        return switch (previous) {
            case MISSING -> rejected("no entry at the previous index");
            case CONFLICTING -> rejected("another entry at the previous index");
            case MATCHING -> switch (request.entry()) {
                case NONE, SAME -> request.commitAhead()
                        ? transition(MATCHING, ADVANCE_COMMIT)
                        : unchanged("holds what was sent, and nothing new to commit");
                case ABSENT -> request.commitAhead()
                        ? transition(MATCHING, APPEND, ADVANCE_COMMIT)
                        : transition(MATCHING, APPEND);
                case CONFLICTING -> request.commitAhead()
                        ? transition(MATCHING, TRUNCATE, APPEND, ADVANCE_COMMIT)
                        : transition(MATCHING, TRUNCATE, APPEND);
            };
        };
    }
}

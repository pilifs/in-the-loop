package net.terminalvalue.quorum.raft;

import static net.terminalvalue.quorum.Decision.rejected;
import static net.terminalvalue.quorum.Decision.transition;
import static net.terminalvalue.quorum.Decision.unchanged;
import static net.terminalvalue.quorum.raft.Role.CANDIDATE;
import static net.terminalvalue.quorum.raft.Role.FOLLOWER;
import static net.terminalvalue.quorum.raft.Role.LEADER;
import static net.terminalvalue.quorum.raft.RoleEffect.ADOPT_TERM;
import static net.terminalvalue.quorum.raft.RoleEffect.INCREMENT_TERM;
import static net.terminalvalue.quorum.raft.RoleEffect.REQUEST_VOTES;
import static net.terminalvalue.quorum.raft.RoleEffect.RESET_ELECTION_TIMER;
import static net.terminalvalue.quorum.raft.RoleEffect.SEND_HEARTBEATS;
import static net.terminalvalue.quorum.raft.RoleEffect.VOTE_FOR_SELF;
import static net.terminalvalue.quorum.raft.TermOrder.NEWER;

import net.terminalvalue.quorum.Decision;
import net.terminalvalue.quorum.raft.RoleEvent.AppendEntries;
import net.terminalvalue.quorum.raft.RoleEvent.ElectionTimeout;
import net.terminalvalue.quorum.raft.RoleEvent.RequestVote;
import net.terminalvalue.quorum.raft.RoleEvent.Response;
import net.terminalvalue.quorum.raft.RoleEvent.VotesCounted;

/**
 * The role transitions of a Raft server (Ongaro and Ousterhout, figure 4), as a total function from (role, event)
 * to a decision.
 *
 * <p>The rule that matters most is the one for every server: a message from a newer term makes the server a
 * follower of that term, whatever it was doing. A leader that misses it keeps serving a term the cluster has moved
 * on from.
 */
public final class RoleMachine {

    private RoleMachine() {}

    public static Decision<Role, RoleEffect> decide(Role role, RoleEvent event) {
        return switch (event) {
            case ElectionTimeout _ -> switch (role) {
                case FOLLOWER, CANDIDATE -> transition(CANDIDATE, INCREMENT_TERM, VOTE_FOR_SELF, REQUEST_VOTES);
                case LEADER -> unchanged("a leader does not hold elections");
            };
            case VotesCounted votes -> switch (role) {
                case CANDIDATE -> votes.majority() ? transition(LEADER, SEND_HEARTBEATS) : unchanged("no majority yet");
                case FOLLOWER, LEADER -> unchanged("votes of an election this server is no longer in");
            };
            case AppendEntries entries -> switch (entries.term()) {
                case NEWER -> transition(FOLLOWER, ADOPT_TERM, RESET_ELECTION_TIMER);
                case CURRENT -> switch (role) {
                    case FOLLOWER -> transition(FOLLOWER, RESET_ELECTION_TIMER);
                    case CANDIDATE -> transition(FOLLOWER, RESET_ELECTION_TIMER); // another server won this term
                    case LEADER -> throw new IllegalStateException("two leaders in one term");
                };
                case OLDER -> rejected("stale leader");
            };
            case RequestVote vote -> vote.term() == NEWER
                    ? transition(FOLLOWER, ADOPT_TERM)
                    : unchanged("the vote itself is decided by the vote rule");
            case Response response -> response.term() == NEWER
                    ? transition(FOLLOWER, ADOPT_TERM)
                    : unchanged("a reply from the current or an older term changes no role");
        };
    }
}

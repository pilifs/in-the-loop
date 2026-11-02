package net.terminalvalue.quorum.raft;

import static net.terminalvalue.quorum.Tests.check;
import static net.terminalvalue.quorum.Tests.equal;

import java.util.List;
import net.terminalvalue.quorum.Decision;
import net.terminalvalue.quorum.Decision.Transition;

public final class RoleMachineTest {

    private RoleMachineTest() {}

    public static void followerBecomesCandidateOnTimeout() {
        Decision<Role, RoleEffect> d = RoleMachine.decide(Role.FOLLOWER, new RoleEvent.ElectionTimeout());
        equal(new Transition<>(Role.CANDIDATE, List.of(RoleEffect.INCREMENT_TERM, RoleEffect.VOTE_FOR_SELF, RoleEffect.REQUEST_VOTES)), d);
    }

    public static void candidateWithMajorityBecomesLeader() {
        equal(new Transition<>(Role.LEADER, List.of(RoleEffect.SEND_HEARTBEATS)),
                RoleMachine.decide(Role.CANDIDATE, new RoleEvent.VotesCounted(true)));
        check(RoleMachine.decide(Role.CANDIDATE, new RoleEvent.VotesCounted(false)) instanceof Decision.Unchanged, "no majority: wait");
    }

    public static void candidateYieldsToTheLeaderOfItsTerm() {
        equal(new Transition<>(Role.FOLLOWER, List.of(RoleEffect.RESET_ELECTION_TIMER)),
                RoleMachine.decide(Role.CANDIDATE, new RoleEvent.AppendEntries(TermOrder.CURRENT)));
    }

    public static void leaderStepsDownForANewerLeader() {
        equal(new Transition<>(Role.FOLLOWER, List.of(RoleEffect.ADOPT_TERM, RoleEffect.RESET_ELECTION_TIMER)),
                RoleMachine.decide(Role.LEADER, new RoleEvent.AppendEntries(TermOrder.NEWER)));
    }

    public static void staleLeaderIsRejected() {
        check(RoleMachine.decide(Role.FOLLOWER, new RoleEvent.AppendEntries(TermOrder.OLDER)) instanceof Decision.Rejected, "stale");
    }
}

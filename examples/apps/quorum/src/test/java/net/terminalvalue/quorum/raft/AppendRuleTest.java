package net.terminalvalue.quorum.raft;

import static net.terminalvalue.quorum.Tests.check;
import static net.terminalvalue.quorum.Tests.equal;
import static net.terminalvalue.quorum.raft.AppendEffect.ADVANCE_COMMIT;
import static net.terminalvalue.quorum.raft.AppendEffect.APPEND;
import static net.terminalvalue.quorum.raft.AppendEffect.TRUNCATE;
import static net.terminalvalue.quorum.raft.LogMatch.CONFLICTING;
import static net.terminalvalue.quorum.raft.LogMatch.MATCHING;
import static net.terminalvalue.quorum.raft.LogMatch.MISSING;

import java.util.List;
import net.terminalvalue.quorum.Decision;
import net.terminalvalue.quorum.Decision.Transition;

public final class AppendRuleTest {

    private AppendRuleTest() {}

    public static void refusesARequestWhosePreviousEntryItLacks() {
        check(AppendRule.decide(MISSING, new AppendRequest(NewEntry.ABSENT, false)) instanceof Decision.Rejected, "log ends before the previous index");
        check(AppendRule.decide(CONFLICTING, new AppendRequest(NewEntry.ABSENT, true)) instanceof Decision.Rejected, "another entry at the previous index");
    }

    public static void appendsAfterAMatchingEntry() {
        equal(new Transition<>(MATCHING, List.of(APPEND)), AppendRule.decide(MATCHING, new AppendRequest(NewEntry.ABSENT, false)));
        equal(new Transition<>(MATCHING, List.of(TRUNCATE, APPEND)), AppendRule.decide(MATCHING, new AppendRequest(NewEntry.CONFLICTING, false)));
    }

    public static void aHeartbeatOrADuplicateChangesNothing() {
        check(AppendRule.decide(MATCHING, new AppendRequest(NewEntry.NONE, false)) instanceof Decision.Unchanged, "heartbeat");
        check(AppendRule.decide(MATCHING, new AppendRequest(NewEntry.SAME, false)) instanceof Decision.Unchanged, "already held");
    }

    public static void theCommitIndexFollowsTheLeaders() {
        equal(new Transition<>(MATCHING, List.of(ADVANCE_COMMIT)), AppendRule.decide(MATCHING, new AppendRequest(NewEntry.NONE, true)));
        equal(new Transition<>(MATCHING, List.of(APPEND, ADVANCE_COMMIT)), AppendRule.decide(MATCHING, new AppendRequest(NewEntry.ABSENT, true)));
        equal(new Transition<>(MATCHING, List.of(TRUNCATE, APPEND, ADVANCE_COMMIT)), AppendRule.decide(MATCHING, new AppendRequest(NewEntry.CONFLICTING, true)));
    }
}

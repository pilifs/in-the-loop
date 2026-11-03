package net.terminalvalue.quorum.raft;

import static net.terminalvalue.quorum.Tests.check;
import static net.terminalvalue.quorum.Tests.equal;
import static net.terminalvalue.quorum.raft.EntryStatus.COMMITTED;
import static net.terminalvalue.quorum.raft.EntryStatus.PENDING;

import java.util.List;
import net.terminalvalue.quorum.Decision;
import net.terminalvalue.quorum.Decision.Transition;

public final class CommitRuleTest {

    private CommitRuleTest() {}

    public static void commitsAnEntryOfTheCurrentTermHeldByAMajority() {
        equal(new Transition<>(COMMITTED, List.of(CommitEffect.APPLY)), CommitRule.decide(PENDING, new Replication(TermOrder.CURRENT, true)));
        check(CommitRule.decide(PENDING, new Replication(TermOrder.CURRENT, false)) instanceof Decision.Unchanged, "a minority");
    }

    public static void neverCommitsAnEntryOfAnEarlierTermByCounting() {
        check(CommitRule.decide(PENDING, new Replication(TermOrder.OLDER, true)) instanceof Decision.Unchanged, "figure 8");
    }

    public static void aCommittedEntryStaysCommitted() {
        check(CommitRule.decide(COMMITTED, new Replication(TermOrder.CURRENT, false)) instanceof Decision.Unchanged, "committed");
    }

    public static void anEntryFromALaterTermIsImpossible() {
        try {
            CommitRule.decide(PENDING, new Replication(TermOrder.NEWER, true));
        } catch (IllegalStateException expected) {
            return;
        }
        throw new AssertionError("expected an IllegalStateException");
    }
}

package net.terminalvalue.quorum.raft;

import static net.terminalvalue.quorum.Tests.check;
import static net.terminalvalue.quorum.Tests.equal;
import static net.terminalvalue.quorum.raft.ReplyEffect.ADVANCE;
import static net.terminalvalue.quorum.raft.ReplyEffect.BACK_UP;
import static net.terminalvalue.quorum.raft.RequestStatus.ANSWERED;
import static net.terminalvalue.quorum.raft.RequestStatus.AWAITED;

import java.util.List;
import net.terminalvalue.quorum.Decision;
import net.terminalvalue.quorum.Decision.Transition;

public final class ReplyRuleTest {

    private ReplyRuleTest() {}

    public static void anAcceptanceMovesTheFollowerUp() {
        equal(new Transition<>(ANSWERED, List.of(ADVANCE)), ReplyRule.decide(AWAITED, new AppendReply(true)));
    }

    public static void aRefusalBacksUpByOne() {
        equal(new Transition<>(ANSWERED, List.of(BACK_UP)), ReplyRule.decide(AWAITED, new AppendReply(false)));
    }

    public static void aLateOrRepeatedReplyChangesNothing() {
        check(ReplyRule.decide(ANSWERED, new AppendReply(true)) instanceof Decision.Unchanged, "late acceptance");
        check(ReplyRule.decide(ANSWERED, new AppendReply(false)) instanceof Decision.Unchanged, "late refusal");
    }
}

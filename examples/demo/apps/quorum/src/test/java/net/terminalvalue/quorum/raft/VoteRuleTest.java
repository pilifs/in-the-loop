package net.terminalvalue.quorum.raft;

import static net.terminalvalue.quorum.Tests.check;
import static net.terminalvalue.quorum.Tests.equal;
import static net.terminalvalue.quorum.raft.VoteRule.NO_VOTE;

import java.util.List;
import net.terminalvalue.quorum.Decision;
import net.terminalvalue.quorum.Decision.Transition;

public final class VoteRuleTest {

    private VoteRuleTest() {}

    public static void grantsToAnUpToDateCandidate() {
        check(VoteRule.grant(3, NO_VOTE, 3, 10, 7, 4, 3, 10), "same log, newer term");
        check(VoteRule.grant(3, NO_VOTE, 3, 10, 7, 4, 3, 12), "longer log, newer term");
    }

    public static void refusesACandidateFromThePast() {
        check(!VoteRule.grant(5, NO_VOTE, 3, 10, 7, 4, 3, 10), "older term");
    }

    public static void oneVotePerTerm() {
        check(!VoteRule.grant(4, 2, 3, 10, 7, 4, 3, 10), "already voted for 2 in term 4");
        check(VoteRule.grant(4, 7, 3, 10, 7, 4, 3, 10), "the same candidate may ask again");
        check(VoteRule.grant(4, 2, 3, 10, 7, 5, 3, 10), "a new term is a new vote");
    }

    public static void refusesAShorterLogOfTheSameTerm() {
        check(!VoteRule.grant(3, NO_VOTE, 3, 10, 7, 4, 3, 9), "shorter log");
    }

    public static void theRuleGrantsOneVotePerTerm() {
        equal(new Transition<>(Ballot.FOR_THE_CANDIDATE, List.of(VoteEffect.GRANT)),
                VoteRule.decide(Ballot.OPEN, new VoteRequest(TermOrder.CURRENT, LogOrder.EVEN)));
        equal(new Transition<>(Ballot.FOR_THE_CANDIDATE, List.of(VoteEffect.GRANT)),
                VoteRule.decide(Ballot.FOR_THE_CANDIDATE, new VoteRequest(TermOrder.CURRENT, LogOrder.EVEN)));
        check(VoteRule.decide(Ballot.FOR_ANOTHER, new VoteRequest(TermOrder.CURRENT, LogOrder.AHEAD)) instanceof Decision.Rejected, "voted for another");
        check(VoteRule.decide(Ballot.FOR_ANOTHER, new VoteRequest(TermOrder.NEWER, LogOrder.EVEN)) instanceof Decision.Transition, "a new term is a new vote");
    }

    public static void theRuleRefusesThePastAndALogBehind() {
        check(VoteRule.decide(Ballot.OPEN, new VoteRequest(TermOrder.OLDER, LogOrder.AHEAD)) instanceof Decision.Rejected, "older term");
        check(VoteRule.decide(Ballot.OPEN, new VoteRequest(TermOrder.NEWER, LogOrder.BEHIND)) instanceof Decision.Rejected, "log behind");
    }
}

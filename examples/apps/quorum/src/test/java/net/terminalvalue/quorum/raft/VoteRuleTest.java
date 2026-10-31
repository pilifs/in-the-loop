package net.terminalvalue.quorum.raft;

import static net.terminalvalue.quorum.Tests.check;
import static net.terminalvalue.quorum.raft.VoteRule.NO_VOTE;

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
}

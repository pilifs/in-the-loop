package net.terminalvalue.quorum;

import static net.terminalvalue.quorum.Tests.equal;
import static net.terminalvalue.quorum.Tests.throwsIllegalArgument;

public final class QuorumTest {

    private QuorumTest() {}

    public static void majorityOfOddClusters() {
        equal(1, Quorum.majority(1));
        equal(2, Quorum.majority(3));
        equal(3, Quorum.majority(5));
        equal(4, Quorum.majority(7));
    }

    public static void faultsTolerated() {
        equal(0, Quorum.faultsTolerated(1));
        equal(1, Quorum.faultsTolerated(3));
        equal(2, Quorum.faultsTolerated(5));
    }

    public static void emptyClusterIsRefused() {
        throwsIllegalArgument(() -> Quorum.majority(0));
    }
}

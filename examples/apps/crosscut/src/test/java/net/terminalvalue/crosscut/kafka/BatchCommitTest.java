package net.terminalvalue.crosscut.kafka;

import static net.terminalvalue.crosscut.Tests.equal;
import static net.terminalvalue.crosscut.Tests.throwsIllegalArgument;

public final class BatchCommitTest {

    private BatchCommitTest() {}

    public static void commitsPastTheWholeBatchWhenEveryRecordIsDone() {
        equal(1_010L, BatchCommit.offsetToCommit(1_000, 10, BatchCommit.NONE_FAILED));
    }

    public static void commitsUpToTheFailedRecord() {
        equal(1_003L, BatchCommit.offsetToCommit(1_000, 10, 3));
    }

    public static void refusesBadArguments() {
        throwsIllegalArgument(() -> BatchCommit.offsetToCommit(1_000, 0, BatchCommit.NONE_FAILED));
        throwsIllegalArgument(() -> BatchCommit.offsetToCommit(1_000, 10, 10));
    }
}

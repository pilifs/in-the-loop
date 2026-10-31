package net.terminalvalue.crosscut.kafka;

/**
 * Which offset a batch listener commits after a batch, in the semantics of Spring Kafka's {@code DefaultErrorHandler}
 * for a {@code BatchListenerFailedException}: the records before the one that failed are done, the failed record and
 * every record after it are redelivered. A committed offset is the next record to read, so it is one past the last
 * record that is done.
 */
public final class BatchCommit {

    private BatchCommit() {}

    /** No record of the batch failed. */
    public static final int NONE_FAILED = -1;

    /**
     * The offset to commit for a batch of {@code batchSize} records starting at {@code batchStart}, given the index
     * within the batch of the record that failed, or {@link #NONE_FAILED}.
     */
    public static long offsetToCommit(long batchStart, int batchSize, int failedIndex) {
        if (batchStart < 0 || batchSize <= 0 || failedIndex < NONE_FAILED || failedIndex >= batchSize) {
            throw new IllegalArgumentException("batchStart >= 0, batchSize > 0 and -1 <= failedIndex < batchSize are required");
        }
        return failedIndex == NONE_FAILED ? batchStart + batchSize : batchStart + failedIndex;
    }
}

package net.terminalvalue.crosscut.tx;

/** What the transaction manager does when a transactional method ends. */
public enum TransactionOutcome {
    COMMIT,
    ROLLBACK,
    /**
     * The method returned, but the transaction had been marked rollback-only (by an inner method that threw and
     * was caught, or by {@code setRollbackOnly}): roll back, and tell the caller with an
     * {@code UnexpectedRollbackException}.
     */
    ROLLBACK_UNEXPECTED
}

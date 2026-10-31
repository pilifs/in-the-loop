package net.terminalvalue.crosscut.tx;

/** How a transactional method takes part in the transaction that is (or is not) already running. */
public enum Enlistment {
    /** Run inside the existing transaction. */
    JOIN,
    /** Begin a new transaction; there was none. */
    BEGIN,
    /** Suspend the existing transaction and begin a new, independent one. */
    SUSPEND_AND_BEGIN,
    /** Run inside the existing transaction with a savepoint to roll back to. */
    SAVEPOINT,
    /** Run without a transaction; there was none. */
    RUN_OUTSIDE,
    /** Suspend the existing transaction and run without one. */
    SUSPEND_AND_RUN_OUTSIDE
}

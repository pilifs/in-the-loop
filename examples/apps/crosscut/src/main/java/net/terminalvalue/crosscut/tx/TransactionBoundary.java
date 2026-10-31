package net.terminalvalue.crosscut.tx;

import static net.terminalvalue.crosscut.tx.Completion.ThrowableKind.CHECKED_EXCEPTION;
import static net.terminalvalue.crosscut.tx.Enlistment.BEGIN;
import static net.terminalvalue.crosscut.tx.Enlistment.JOIN;
import static net.terminalvalue.crosscut.tx.Enlistment.RUN_OUTSIDE;
import static net.terminalvalue.crosscut.tx.Enlistment.SAVEPOINT;
import static net.terminalvalue.crosscut.tx.Enlistment.SUSPEND_AND_BEGIN;
import static net.terminalvalue.crosscut.tx.Enlistment.SUSPEND_AND_RUN_OUTSIDE;
import static net.terminalvalue.crosscut.tx.TransactionOutcome.COMMIT;
import static net.terminalvalue.crosscut.tx.TransactionOutcome.ROLLBACK;
import static net.terminalvalue.crosscut.tx.TransactionOutcome.ROLLBACK_UNEXPECTED;

import net.terminalvalue.crosscut.tx.Completion.Returned;
import net.terminalvalue.crosscut.tx.Completion.Threw;

/**
 * The two decisions a transaction interceptor makes around a {@code @Transactional} method: how the method enlists
 * in the transaction that may already be running, and whether the transaction commits or rolls back when the
 * method ends. These are the rules of Spring's {@code AbstractPlatformTransactionManager} and
 * {@code RuleBasedTransactionAttribute}, as two total functions.
 */
public final class TransactionBoundary {

    private TransactionBoundary() {}

    /** How a method with the given propagation enlists, given whether a transaction is active. */
    public static Enlistment enter(Propagation propagation, boolean active) {
        return switch (propagation) {
            case REQUIRED -> active ? JOIN : BEGIN;
            case REQUIRES_NEW -> active ? SUSPEND_AND_BEGIN : BEGIN;
            case SUPPORTS -> active ? JOIN : RUN_OUTSIDE;
            case NOT_SUPPORTED -> active ? SUSPEND_AND_RUN_OUTSIDE : RUN_OUTSIDE;
            case MANDATORY -> {
                if (!active) {
                    throw new IllegalStateException("No existing transaction found for transaction marked with propagation 'mandatory'");
                }
                yield JOIN;
            }
            case NEVER -> {
                if (active) {
                    throw new IllegalStateException("Existing transaction found for transaction marked with propagation 'never'");
                }
                yield RUN_OUTSIDE;
            }
            case NESTED -> active ? SAVEPOINT : BEGIN;
        };
    }

    /**
     * Whether the transaction commits or rolls back when the method ends. The default rule is Spring's: a
     * {@code RuntimeException} or an {@code Error} rolls back, a checked exception commits. An explicit
     * {@code rollbackFor} or {@code noRollbackFor} rule that matches the exception overrides the default. A
     * transaction marked rollback-only never commits, whatever the method did.
     */
    public static TransactionOutcome exit(Completion completion, boolean rollbackOnly) {
        return switch (completion) {
            case Returned _ -> rollbackOnly ? ROLLBACK_UNEXPECTED : COMMIT;
            case Threw threw -> rollbackOnly || rollsBack(threw) ? ROLLBACK : COMMIT;
        };
    }

    private static boolean rollsBack(Threw threw) {
        return switch (threw.rule()) {
            case ROLLBACK_FOR -> true;
            case NO_ROLLBACK_FOR -> false;
            case NONE -> threw.kind() != CHECKED_EXCEPTION;
        };
    }
}

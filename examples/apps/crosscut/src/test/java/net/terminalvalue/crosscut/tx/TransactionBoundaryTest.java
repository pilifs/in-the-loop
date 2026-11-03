package net.terminalvalue.crosscut.tx;

import static net.terminalvalue.crosscut.Tests.equal;
import static net.terminalvalue.crosscut.Tests.throwsIllegalState;
import static net.terminalvalue.crosscut.tx.Completion.RollbackRule.NONE;
import static net.terminalvalue.crosscut.tx.Completion.RollbackRule.NO_ROLLBACK_FOR;
import static net.terminalvalue.crosscut.tx.Completion.RollbackRule.ROLLBACK_FOR;
import static net.terminalvalue.crosscut.tx.Completion.ThrowableKind.CHECKED_EXCEPTION;
import static net.terminalvalue.crosscut.tx.Completion.ThrowableKind.RUNTIME_EXCEPTION;

import net.terminalvalue.crosscut.tx.Completion.Returned;
import net.terminalvalue.crosscut.tx.Completion.Threw;

public final class TransactionBoundaryTest {

    private TransactionBoundaryTest() {}

    public static void requiredJoinsOrBegins() {
        equal(Enlistment.JOIN, TransactionBoundary.enter(Propagation.REQUIRED, true));
        equal(Enlistment.BEGIN, TransactionBoundary.enter(Propagation.REQUIRED, false));
    }

    public static void requiresNewSuspendsTheOuterTransaction() {
        equal(Enlistment.SUSPEND_AND_BEGIN, TransactionBoundary.enter(Propagation.REQUIRES_NEW, true));
        equal(Enlistment.BEGIN, TransactionBoundary.enter(Propagation.REQUIRES_NEW, false));
    }

    public static void nestedUsesASavepoint() {
        equal(Enlistment.SAVEPOINT, TransactionBoundary.enter(Propagation.NESTED, true));
    }

    public static void mandatoryAndNeverRefuse() {
        throwsIllegalState(() -> TransactionBoundary.enter(Propagation.MANDATORY, false));
        throwsIllegalState(() -> TransactionBoundary.enter(Propagation.NEVER, true));
        equal(Enlistment.RUN_OUTSIDE, TransactionBoundary.enter(Propagation.NEVER, false));
    }

    public static void aReturnCommits() {
        equal(TransactionOutcome.COMMIT, TransactionBoundary.exit(new Returned(), false));
    }

    public static void aRuntimeExceptionRollsBack() {
        equal(TransactionOutcome.ROLLBACK, TransactionBoundary.exit(new Threw(RUNTIME_EXCEPTION, NONE), false));
    }

    public static void aCheckedExceptionCommitsByDefault() {
        equal(TransactionOutcome.COMMIT, TransactionBoundary.exit(new Threw(CHECKED_EXCEPTION, NONE), false));
    }

    public static void explicitRulesOverrideTheDefault() {
        equal(TransactionOutcome.ROLLBACK, TransactionBoundary.exit(new Threw(CHECKED_EXCEPTION, ROLLBACK_FOR), false));
        equal(TransactionOutcome.COMMIT, TransactionBoundary.exit(new Threw(RUNTIME_EXCEPTION, NO_ROLLBACK_FOR), false));
    }

    public static void rollbackOnlyNeverCommits() {
        equal(TransactionOutcome.ROLLBACK_UNEXPECTED, TransactionBoundary.exit(new Returned(), true));
        equal(TransactionOutcome.ROLLBACK, TransactionBoundary.exit(new Threw(CHECKED_EXCEPTION, NONE), true));
    }
}

package net.terminalvalue.crosscut.tx;

/** How a transactional method ended: it returned, or it threw. */
public sealed interface Completion {

    /** The method returned normally. */
    record Returned() implements Completion {}

    /**
     * The method threw. {@code kind} is what was thrown, and {@code rule} which of the method's explicit rollback
     * rules ({@code rollbackFor}, {@code noRollbackFor}) matched it most closely, if any.
     */
    record Threw(ThrowableKind kind, RollbackRule rule) implements Completion {}

    enum ThrowableKind {
        RUNTIME_EXCEPTION,
        ERROR,
        CHECKED_EXCEPTION
    }

    enum RollbackRule {
        /** No explicit rule matched: the default applies. */
        NONE,
        /** The closest matching rule is a {@code rollbackFor}. */
        ROLLBACK_FOR,
        /** The closest matching rule is a {@code noRollbackFor}. */
        NO_ROLLBACK_FOR
    }
}

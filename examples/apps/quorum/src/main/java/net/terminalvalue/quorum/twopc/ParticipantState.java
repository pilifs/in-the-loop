package net.terminalvalue.quorum.twopc;

/** Where a two-phase-commit participant is: working, prepared (voted yes, holding its locks), or decided. */
public enum ParticipantState {
    WORKING,
    PREPARED,
    COMMITTED,
    ABORTED
}

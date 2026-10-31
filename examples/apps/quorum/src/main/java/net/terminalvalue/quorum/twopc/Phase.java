package net.terminalvalue.quorum.twopc;

/** The phase of a two-phase-commit coordinator for one transaction. */
public enum Phase {
    /** Prepare was sent; votes are coming in. */
    COLLECTING,
    COMMITTED,
    ABORTED
}

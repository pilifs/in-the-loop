package net.terminalvalue.quorum.twopc;

/** The messages a coordinator sends when it decides. */
public enum CoordinatorEffect {
    SEND_COMMIT,
    SEND_ABORT
}

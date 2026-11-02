package net.terminalvalue.quorum.twopc;

/** What the coordinator has broadcast: nothing yet, commit, or abort. */
public enum Outcome {
    NONE,
    COMMIT,
    ABORT
}

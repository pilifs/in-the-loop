package net.terminalvalue.crosscut.idempotency;

/** What the receiver has recorded for an idempotency key. */
public enum KeyState {
    /** No record: the key has never been seen, or its record expired. */
    ABSENT,
    /** An attempt with this key is executing. */
    IN_PROGRESS,
    /** An attempt with this key finished and its response is stored. */
    COMPLETED
}

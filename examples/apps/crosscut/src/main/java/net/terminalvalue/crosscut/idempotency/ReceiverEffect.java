package net.terminalvalue.crosscut.idempotency;

/** What the filter owning the receiver does on the kernel's decision. */
public enum ReceiverEffect {
    /** Run the request. */
    EXECUTE,
    /** Store the response under the key. */
    STORE_RESPONSE,
    /** Answer with the stored response. */
    REPLAY_RESPONSE,
    /** Delete the record. */
    RELEASE_KEY
}

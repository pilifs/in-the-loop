package net.terminalvalue.crosscut.idempotency;

/** What happens to one idempotency key at the receiver. */
public sealed interface ReceiverEvent {

    /**
     * A request with this key arrived. {@code sameFingerprint} says whether its method, path and body hash match
     * the record's (false when there is no record is impossible, and is decided the same as true).
     */
    record Request(boolean sameFingerprint) implements ReceiverEvent {}

    /** The executing attempt produced a response. */
    record Completed() implements ReceiverEvent {}

    /** The executing attempt died before producing a response: the worker crashed, the transaction rolled back. */
    record Failed() implements ReceiverEvent {}

    /** The record's time to live passed. */
    record Expired() implements ReceiverEvent {}
}

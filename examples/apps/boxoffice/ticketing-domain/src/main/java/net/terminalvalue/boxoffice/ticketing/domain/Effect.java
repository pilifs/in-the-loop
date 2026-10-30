package net.terminalvalue.boxoffice.ticketing.domain;

/** A side effect that the service must apply in the same transaction as the status change. */
public enum Effect {
    /** Mark the order's seats SOLD. They must still be held by the order's hold. */
    SELL_SEATS,
    /** Make the order's seats AVAILABLE, whether they are held by its hold or sold to it. */
    RELEASE_SEATS,
    /** Publish a refund command for the order's payment, through the outbox. */
    REQUEST_REFUND,
}

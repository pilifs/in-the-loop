package net.terminalvalue.boxoffice.ticketing.domain;

/** Something that happened to an order: a payment outcome, or a request from the customer. */
public sealed interface OrderInput {

    /**
     * The customer was charged.
     *
     * @param seatsStillHeld whether every seat of the order is still held by its hold. It is false when the hold
     *     expired and the seats were released, or sold to someone else, before the payment came back.
     */
    record PaymentCaptured(boolean seatsStillHeld) implements OrderInput {}

    record PaymentDeclined() implements OrderInput {}

    record PaymentRefunded() implements OrderInput {}

    record CancellationRequested() implements OrderInput {}
}

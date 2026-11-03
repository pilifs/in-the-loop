package net.terminalvalue.boxoffice.ticketing.domain;

/**
 * The life of an order.
 *
 * <pre>
 * PENDING_PAYMENT --captured, seats still held--> CONFIRMED --cancelled--> REFUND_PENDING --refunded--> REFUNDED
 *        |  \--captured, hold lost to expiry-------------------------------^
 *        \--declined--> DECLINED --captured (never expected)----------------^
 * </pre>
 */
public enum OrderStatus {
    /** The order exists and its payment has been requested. */
    PENDING_PAYMENT,
    /** Paid, and the seats are sold to this order. */
    CONFIRMED,
    /** The charge was refused. No money moved and the seats were released. */
    DECLINED,
    /** Money was captured but the order will not be fulfilled, so a refund has been requested. */
    REFUND_PENDING,
    /** The money was returned. */
    REFUNDED;

    /**
     * Nothing more is expected for the order. The one exception is a capture reported for a declined order, which
     * {@link OrderLifecycle} still refunds.
     */
    public boolean isFinal() {
        return this == DECLINED || this == REFUNDED;
    }
}

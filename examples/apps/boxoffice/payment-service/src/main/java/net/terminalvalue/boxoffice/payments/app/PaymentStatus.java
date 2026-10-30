package net.terminalvalue.boxoffice.payments.app;

/**
 * <pre>
 * (none) --charge--> CAPTURED --refund--> REFUNDED
 *    |  \--charge--> DECLINED
 *    \--refund--> VOIDED    (a refund that overtook its charge: the charge is then refused)
 * </pre>
 */
public enum PaymentStatus {
    CAPTURED,
    DECLINED,
    REFUNDED,
    VOIDED,
}

package net.terminalvalue.boxoffice.contracts;

/**
 * Kafka topics. Every record is keyed by order ID, so all messages about one order land on one partition, in order.
 */
public final class Topics {

    /** Commands from ticketing to payments: {@link PaymentCommand}. */
    public static final String PAYMENT_COMMANDS = "payments.commands";

    /** Outcomes from payments back to ticketing: {@link PaymentEvent}. */
    public static final String PAYMENT_EVENTS = "payments.events";

    /** Suffix of the dead-letter topic that receives records a consumer failed to process. */
    public static final String DEAD_LETTER_SUFFIX = ".DLT";

    private Topics() {}
}

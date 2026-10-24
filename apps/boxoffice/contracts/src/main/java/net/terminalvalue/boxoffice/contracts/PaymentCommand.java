package net.terminalvalue.boxoffice.contracts;

import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;
import java.time.Instant;
import java.util.UUID;

/** A request from ticketing to the payment service, published on {@link Topics#PAYMENT_COMMANDS}. */
@JsonTypeInfo(use = JsonTypeInfo.Id.NAME, property = "type")
@JsonSubTypes({
    @JsonSubTypes.Type(value = PaymentCommand.ChargePayment.class, name = "ChargePayment"),
    @JsonSubTypes.Type(value = PaymentCommand.RefundPayment.class, name = "RefundPayment"),
})
public sealed interface PaymentCommand extends Message {

    /** Charge the customer for an order. The payment service charges each order at most once. */
    record ChargePayment(
            UUID eventId, String orderId, Instant occurredAt, String customerId, long amountCents, String paymentToken)
            implements PaymentCommand {}

    /** Refund an order's payment in full. */
    record RefundPayment(UUID eventId, String orderId, Instant occurredAt, String reason) implements PaymentCommand {}
}

package net.terminalvalue.boxoffice.contracts;

import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;
import java.time.Instant;
import java.util.UUID;

/** An outcome reported by the payment service, published on {@link Topics#PAYMENT_EVENTS}. */
@JsonTypeInfo(use = JsonTypeInfo.Id.NAME, property = "type")
@JsonSubTypes({
    @JsonSubTypes.Type(value = PaymentEvent.PaymentCaptured.class, name = "PaymentCaptured"),
    @JsonSubTypes.Type(value = PaymentEvent.PaymentDeclined.class, name = "PaymentDeclined"),
    @JsonSubTypes.Type(value = PaymentEvent.PaymentRefunded.class, name = "PaymentRefunded"),
})
public sealed interface PaymentEvent extends Message {

    /** The customer was charged. */
    record PaymentCaptured(UUID eventId, String orderId, Instant occurredAt, String paymentId, long amountCents)
            implements PaymentEvent {}

    /** The charge was refused, so no money moved. */
    record PaymentDeclined(UUID eventId, String orderId, Instant occurredAt, String reason) implements PaymentEvent {}

    /** A captured payment was returned to the customer. */
    record PaymentRefunded(UUID eventId, String orderId, Instant occurredAt, String paymentId, long amountCents)
            implements PaymentEvent {}
}

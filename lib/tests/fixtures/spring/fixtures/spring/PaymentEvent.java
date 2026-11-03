package fixtures.spring;

import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;

/** A message family: the type id is in the payload. Voided is permitted but not registered. */
@JsonTypeInfo(use = JsonTypeInfo.Id.NAME, property = "type")
@JsonSubTypes({
    @JsonSubTypes.Type(value = PaymentEvent.Captured.class, name = "PaymentCaptured"),
    @JsonSubTypes.Type(value = PaymentEvent.Declined.class),
})
public sealed interface PaymentEvent {
    record Captured(String orderId, long amountCents) implements PaymentEvent {}

    record Declined(String orderId, String reason) implements PaymentEvent {}

    record Voided(String orderId) implements PaymentEvent {}
}

package net.terminalvalue.boxoffice.contracts;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import tools.jackson.core.JacksonException;

class MessageCodecTest {

    @Test
    void roundTripsEachMessageThroughItsSealedInterface() {
        var now = Instant.parse("2026-10-24T12:00:00Z");
        Message[] messages = {
            new PaymentCommand.ChargePayment(UUID.randomUUID(), "o-1", now, "c-1", 4500, "tok_visa"),
            new PaymentCommand.RefundPayment(UUID.randomUUID(), "o-1", now, "customer cancelled"),
            new PaymentEvent.PaymentCaptured(UUID.randomUUID(), "o-1", now, "p-1", 4500),
            new PaymentEvent.PaymentDeclined(UUID.randomUUID(), "o-1", now, "card declined"),
            new PaymentEvent.PaymentRefunded(UUID.randomUUID(), "o-1", now, "p-1", 4500),
        };
        for (Message message : messages) {
            Class<? extends Message> base =
                    message instanceof PaymentCommand ? PaymentCommand.class : PaymentEvent.class;
            assertThat(MessageCodec.decode(MessageCodec.encode(message), base)).isEqualTo(message);
        }
    }

    @Test
    void writesTheTypeAndIsoTimestampsIntoThePayload() {
        var json = MessageCodec.encode(new PaymentEvent.PaymentDeclined(
                UUID.fromString("00000000-0000-0000-0000-000000000001"),
                "o-1",
                Instant.parse("2026-10-24T12:00:00Z"),
                "card declined"));
        assertThat(json)
                .contains("\"type\":\"PaymentDeclined\"")
                .contains("\"occurredAt\":\"2026-10-24T12:00:00Z\"");
    }

    @Test
    void rejectsAMessageOfTheWrongFamily() {
        var command = MessageCodec.encode(
                new PaymentCommand.RefundPayment(UUID.randomUUID(), "o-1", Instant.now(), "test"));
        assertThatThrownBy(() -> MessageCodec.decode(command, PaymentEvent.class))
                .isInstanceOf(JacksonException.class);
    }
}

package net.terminalvalue.boxoffice.ticketing.events;

import net.terminalvalue.boxoffice.contracts.MessageCodec;
import net.terminalvalue.boxoffice.contracts.PaymentEvent;
import net.terminalvalue.boxoffice.contracts.Topics;
import net.terminalvalue.boxoffice.ticketing.app.PaymentEventHandler;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

/**
 * Consumes payment outcomes. The offset is committed only after {@link PaymentEventHandler} returns, so a crash
 * redelivers the event, and the handler's inbox makes the redelivery harmless.
 */
@Component
class PaymentEventListener {

    private final PaymentEventHandler handler;

    PaymentEventListener(PaymentEventHandler handler) {
        this.handler = handler;
    }

    @KafkaListener(topics = Topics.PAYMENT_EVENTS, groupId = "ticketing")
    void on(ConsumerRecord<String, String> record) {
        handler.handle(MessageCodec.decode(record.value(), PaymentEvent.class));
    }
}

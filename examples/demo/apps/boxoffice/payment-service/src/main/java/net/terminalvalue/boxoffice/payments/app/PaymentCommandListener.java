package net.terminalvalue.boxoffice.payments.app;

import net.terminalvalue.boxoffice.contracts.MessageCodec;
import net.terminalvalue.boxoffice.contracts.PaymentCommand;
import net.terminalvalue.boxoffice.contracts.Topics;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
class PaymentCommandListener {

    private final PaymentCommandHandler handler;

    PaymentCommandListener(PaymentCommandHandler handler) {
        this.handler = handler;
    }

    @KafkaListener(topics = Topics.PAYMENT_COMMANDS, groupId = "payments")
    void on(ConsumerRecord<String, String> record) {
        handler.handle(MessageCodec.decode(record.value(), PaymentCommand.class));
    }
}

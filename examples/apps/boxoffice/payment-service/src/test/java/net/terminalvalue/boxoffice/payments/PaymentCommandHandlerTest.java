package net.terminalvalue.boxoffice.payments;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.data.mongodb.core.query.Criteria.where;
import static org.springframework.data.mongodb.core.query.Query.query;

import java.time.Instant;
import java.util.List;
import java.util.UUID;
import net.terminalvalue.boxoffice.contracts.MessageCodec;
import net.terminalvalue.boxoffice.contracts.PaymentCommand.ChargePayment;
import net.terminalvalue.boxoffice.contracts.PaymentCommand.RefundPayment;
import net.terminalvalue.boxoffice.contracts.PaymentEvent;
import net.terminalvalue.boxoffice.messaging.Outbox;
import net.terminalvalue.boxoffice.payments.app.PaymentCommandHandler;
import net.terminalvalue.boxoffice.payments.app.PaymentDocument;
import net.terminalvalue.boxoffice.payments.app.PaymentStatus;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.data.domain.Sort;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.kafka.KafkaContainer;
import org.testcontainers.mongodb.MongoDBContainer;

/**
 * The handler's answers to duplicated and reordered commands, which the end-to-end tests cannot provoke. The outbox
 * relay is stopped by a long poll interval, so each test reads exactly what the handler queued.
 */
@SpringBootTest(properties = "boxoffice.outbox.poll-interval=1h")
@Testcontainers
class PaymentCommandHandlerTest {

    @Container
    @ServiceConnection
    static final KafkaContainer kafka = new KafkaContainer("apache/kafka:4.2.1");

    @Container
    @ServiceConnection
    static final MongoDBContainer mongo = new MongoDBContainer("mongo:8.0").withReplicaSet();

    @Autowired
    PaymentCommandHandler handler;

    @Autowired
    MongoTemplate db;

    @Test
    void aSecondChargeForTheSameOrderRepeatsTheOutcomeWithoutChargingAgain() {
        String order = newOrder();
        handler.handle(charge(order, "tok_visa"));
        handler.handle(charge(order, "tok_visa"));

        assertThat(payment(order).status()).isEqualTo(PaymentStatus.CAPTURED);
        var events = events(order);
        assertThat(events).hasSize(2).allMatch(PaymentEvent.PaymentCaptured.class::isInstance);
        assertThat(events.stream().map(e -> ((PaymentEvent.PaymentCaptured) e).paymentId()).distinct()).hasSize(1);
    }

    @Test
    void aRedeliveredCommandIsSkipped() {
        String order = newOrder();
        var command = charge(order, "tok_visa");
        handler.handle(command);
        handler.handle(command);

        assertThat(events(order)).hasSize(1);
    }

    @Test
    void aDeclinedChargeStaysDeclined() {
        String order = newOrder();
        handler.handle(charge(order, "tok_declined"));
        handler.handle(charge(order, "tok_visa"));

        assertThat(payment(order).status()).isEqualTo(PaymentStatus.DECLINED);
        assertThat(events(order)).hasSize(2).allMatch(PaymentEvent.PaymentDeclined.class::isInstance);
    }

    @Test
    void aRefundIsAppliedOnceAndReportedEachTime() {
        String order = newOrder();
        handler.handle(charge(order, "tok_visa"));
        handler.handle(refund(order));
        handler.handle(refund(order));

        assertThat(payment(order).status()).isEqualTo(PaymentStatus.REFUNDED);
        assertThat(events(order))
                .map(e -> e.getClass().getSimpleName())
                .containsExactly("PaymentCaptured", "PaymentRefunded", "PaymentRefunded");
    }

    @Test
    void aRefundThatOvertakesItsChargeVoidsThePayment() {
        String order = newOrder();
        handler.handle(refund(order));
        handler.handle(charge(order, "tok_visa"));

        assertThat(payment(order).status()).isEqualTo(PaymentStatus.VOIDED);
        assertThat(events(order)).singleElement().isInstanceOf(PaymentEvent.PaymentDeclined.class);
    }

    private static String newOrder() {
        return UUID.randomUUID().toString();
    }

    private static ChargePayment charge(String order, String token) {
        return new ChargePayment(UUID.randomUUID(), order, Instant.now(), "customer", 4500, token);
    }

    private static RefundPayment refund(String order) {
        return new RefundPayment(UUID.randomUUID(), order, Instant.now(), "test");
    }

    private PaymentDocument payment(String order) {
        return db.findById(order, PaymentDocument.class);
    }

    private List<PaymentEvent> events(String order) {
        return db.find(query(where("key").is(order)).with(Sort.by("_id")), Outbox.Entry.class).stream()
                .map(entry -> MessageCodec.decode(entry.payload(), PaymentEvent.class))
                .toList();
    }
}

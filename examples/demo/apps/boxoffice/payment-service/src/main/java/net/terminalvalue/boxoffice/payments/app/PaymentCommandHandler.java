package net.terminalvalue.boxoffice.payments.app;

import static org.springframework.data.mongodb.core.query.Criteria.where;
import static org.springframework.data.mongodb.core.query.Query.query;

import java.time.Clock;
import java.time.Instant;
import java.util.UUID;
import net.terminalvalue.boxoffice.contracts.PaymentCommand;
import net.terminalvalue.boxoffice.contracts.PaymentCommand.ChargePayment;
import net.terminalvalue.boxoffice.contracts.PaymentCommand.RefundPayment;
import net.terminalvalue.boxoffice.contracts.PaymentEvent;
import net.terminalvalue.boxoffice.contracts.Topics;
import net.terminalvalue.boxoffice.messaging.Inbox;
import net.terminalvalue.boxoffice.messaging.Outbox;
import net.terminalvalue.boxoffice.messaging.Transactions;
import net.terminalvalue.boxoffice.payments.gateway.PaymentGateway;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.mongodb.core.MongoTemplate;
import org.springframework.data.mongodb.core.query.Update;
import org.springframework.stereotype.Service;

/**
 * Charges and refunds orders. Each order is charged at most once, however often it is asked: the payment record is
 * keyed by order ID, and the gateway call uses the order ID as its idempotency key.
 *
 * <p>The gateway call runs inside the MongoDB transaction. If the transaction then fails, the retry calls the gateway
 * again with the same key and gets the same answer, so no money moves twice.
 */
@Service
public class PaymentCommandHandler {

    static final String CONSUMER = "payments";

    private static final Logger log = LoggerFactory.getLogger(PaymentCommandHandler.class);

    private final MongoTemplate mongo;
    private final Transactions transactions;
    private final Inbox inbox;
    private final Outbox outbox;
    private final PaymentGateway gateway;
    private final Clock clock;

    public PaymentCommandHandler(
            MongoTemplate mongo,
            Transactions transactions,
            Inbox inbox,
            Outbox outbox,
            PaymentGateway gateway,
            Clock clock) {
        this.mongo = mongo;
        this.transactions = transactions;
        this.inbox = inbox;
        this.outbox = outbox;
        this.gateway = gateway;
        this.clock = clock;
    }

    public void handle(PaymentCommand command) {
        transactions.run(() -> {
            if (!inbox.firstDelivery(CONSUMER, command)) {
                log.info("Skipping {} for order {}: already processed", command.getClass().getSimpleName(), command.orderId());
                return;
            }
            var payment = mongo.findById(command.orderId(), PaymentDocument.class);
            switch (command) {
                case ChargePayment charge -> charge(charge, payment);
                case RefundPayment refund -> refund(refund, payment);
            }
        });
    }

    private void charge(ChargePayment command, PaymentDocument payment) {
        Instant now = clock.instant();
        if (payment != null) {
            // A second charge request for the order: report the first outcome again, and charge nothing.
            switch (payment.status()) {
                case CAPTURED, REFUNDED -> publishCaptured(payment, now);
                case DECLINED, VOIDED -> publish(new PaymentEvent.PaymentDeclined(
                        UUID.randomUUID(), payment.orderId(), now, payment.reason()));
            }
            return;
        }
        var result = gateway.charge(command.orderId(), command.paymentToken(), command.amountCents());
        payment = switch (result) {
            case PaymentGateway.ChargeResult.Captured captured -> new PaymentDocument(
                    command.orderId(), command.customerId(), command.amountCents(), PaymentStatus.CAPTURED,
                    captured.reference(), null, now, now);
            case PaymentGateway.ChargeResult.Declined declined -> new PaymentDocument(
                    command.orderId(), command.customerId(), command.amountCents(), PaymentStatus.DECLINED,
                    null, declined.reason(), now, now);
        };
        mongo.insert(payment);
        log.info("Order {} charged {} cents: {}", payment.orderId(), payment.amountCents(), payment.status());
        if (payment.status() == PaymentStatus.CAPTURED) {
            publishCaptured(payment, now);
        } else {
            publish(new PaymentEvent.PaymentDeclined(UUID.randomUUID(), payment.orderId(), now, payment.reason()));
        }
    }

    private void refund(RefundPayment command, PaymentDocument payment) {
        Instant now = clock.instant();
        if (payment == null) {
            // The refund overtook its charge. Record the void so that the charge, when it arrives, is refused.
            mongo.insert(new PaymentDocument(
                    command.orderId(), null, 0, PaymentStatus.VOIDED, null, "refunded before charge", now, now));
            log.warn("Order {} refunded before it was charged; voided", command.orderId());
            return;
        }
        switch (payment.status()) {
            case CAPTURED -> {
                gateway.refund("refund-" + payment.orderId(), payment.gatewayReference(), payment.amountCents());
                mongo.updateFirst(
                        query(where("_id").is(payment.orderId()).and("status").is(PaymentStatus.CAPTURED)),
                        new Update().set("status", PaymentStatus.REFUNDED).set("updatedAt", now),
                        PaymentDocument.class);
                log.info("Order {} refunded {} cents", payment.orderId(), payment.amountCents());
                publishRefunded(payment, now);
            }
            case REFUNDED -> publishRefunded(payment, now);
            case DECLINED, VOIDED -> log.warn("Order {} has no captured payment to refund", payment.orderId());
        }
    }

    private void publishCaptured(PaymentDocument payment, Instant now) {
        publish(new PaymentEvent.PaymentCaptured(
                UUID.randomUUID(), payment.orderId(), now, payment.gatewayReference(), payment.amountCents()));
    }

    private void publishRefunded(PaymentDocument payment, Instant now) {
        publish(new PaymentEvent.PaymentRefunded(
                UUID.randomUUID(), payment.orderId(), now, payment.gatewayReference(), payment.amountCents()));
    }

    private void publish(PaymentEvent event) {
        outbox.enqueue(Topics.PAYMENT_EVENTS, event);
    }
}

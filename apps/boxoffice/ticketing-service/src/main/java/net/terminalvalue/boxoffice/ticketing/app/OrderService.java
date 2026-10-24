package net.terminalvalue.boxoffice.ticketing.app;

import java.time.Clock;
import java.time.Instant;
import java.util.UUID;
import net.terminalvalue.boxoffice.contracts.PaymentCommand;
import net.terminalvalue.boxoffice.contracts.Topics;
import net.terminalvalue.boxoffice.messaging.Outbox;
import net.terminalvalue.boxoffice.messaging.Transactions;
import net.terminalvalue.boxoffice.ticketing.domain.Decision;
import net.terminalvalue.boxoffice.ticketing.domain.OrderInput;
import net.terminalvalue.boxoffice.ticketing.domain.OrderStatus;
import net.terminalvalue.boxoffice.ticketing.store.OrderDocument;
import net.terminalvalue.boxoffice.ticketing.store.TicketingStore;
import org.springframework.stereotype.Service;

/**
 * Orders, asynchronously: placing or cancelling an order records the intent and returns at once, and the payment
 * service's answer arrives later over Kafka ({@link PaymentEventHandler}). Clients poll the order for its status.
 */
@Service
public class OrderService {

    private final TicketingStore store;
    private final Transactions transactions;
    private final Outbox outbox;
    private final OrderTransitions transitions;
    private final Clock clock;

    public OrderService(
            TicketingStore store, Transactions transactions, Outbox outbox, OrderTransitions transitions, Clock clock) {
        this.store = store;
        this.transactions = transactions;
        this.outbox = outbox;
        this.transitions = transitions;
        this.clock = clock;
    }

    /**
     * Turns an unexpired hold into an order and requests payment for it. Placing an order twice for one hold returns
     * the first order, so a client may retry safely.
     */
    public Created<OrderDocument> place(String holdId, String paymentToken) {
        return transactions.run(() -> {
            var earlier = store.orderForHold(holdId);
            if (earlier.isPresent()) {
                return new Created<>(earlier.get(), false);
            }
            var hold = store.hold(holdId).orElseThrow(() -> new NotFoundException("no hold " + holdId));
            Instant now = clock.instant();
            if (store.heldUnexpiredBy(holdId, now) != hold.seatLabels().size()) {
                throw new ConflictException("hold " + holdId + " has expired");
            }
            var order = new OrderDocument(
                    UUID.randomUUID().toString(),
                    holdId,
                    hold.concertId(),
                    hold.seatLabels(),
                    hold.customerId(),
                    hold.amountCents(),
                    OrderStatus.PENDING_PAYMENT,
                    now,
                    now);
            store.insert(order);
            outbox.enqueue(
                    Topics.PAYMENT_COMMANDS,
                    new PaymentCommand.ChargePayment(
                            UUID.randomUUID(), order.id(), now, order.customerId(), order.amountCents(), paymentToken));
            return new Created<>(order, true);
        });
    }

    /** Cancels a confirmed order: its seats are released now, and the refund follows asynchronously. */
    public OrderDocument cancel(String orderId) {
        return transactions.run(() -> {
            var order = get(orderId);
            if (transitions.apply(order, new OrderInput.CancellationRequested()) instanceof Decision.Rejected r) {
                throw new ConflictException(r.reason());
            }
            return get(orderId);
        });
    }

    public OrderDocument get(String orderId) {
        return store.order(orderId).orElseThrow(() -> new NotFoundException("no order " + orderId));
    }
}

package net.terminalvalue.boxoffice.ticketing.app;

import java.time.Clock;
import java.time.Instant;
import java.util.UUID;
import net.terminalvalue.boxoffice.contracts.PaymentCommand;
import net.terminalvalue.boxoffice.contracts.Topics;
import net.terminalvalue.boxoffice.messaging.Outbox;
import net.terminalvalue.boxoffice.messaging.Transactions;
import net.terminalvalue.boxoffice.ticketing.domain.Decision;
import net.terminalvalue.boxoffice.ticketing.domain.Effect;
import net.terminalvalue.boxoffice.ticketing.domain.OrderInput;
import net.terminalvalue.boxoffice.ticketing.domain.OrderLifecycle;
import net.terminalvalue.boxoffice.ticketing.store.OrderDocument;
import net.terminalvalue.boxoffice.ticketing.store.TicketingStore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Applies an {@link OrderLifecycle} decision to the database: its effects, then the status change. The caller's
 * transaction makes them atomic, and the status change is conditional on the status the decision was made from.
 */
@Component
public class OrderTransitions {

    private static final Logger log = LoggerFactory.getLogger(OrderTransitions.class);

    private final TicketingStore store;
    private final Outbox outbox;
    private final Clock clock;

    public OrderTransitions(TicketingStore store, Outbox outbox, Clock clock) {
        this.store = store;
        this.outbox = outbox;
        this.clock = clock;
    }

    public Decision apply(OrderDocument order, OrderInput input) {
        Transactions.requireActive("OrderTransitions.apply");
        Decision decision = OrderLifecycle.decide(order.status(), input);
        if (!(decision instanceof Decision.Transition transition)) {
            log.info("Order {} stays {} on {}: {}", order.id(), order.status(), input, decision);
            return decision;
        }
        Instant now = clock.instant();
        for (Effect effect : transition.effects()) {
            switch (effect) {
                case SELL_SEATS -> {
                    long sold = store.sell(order.holdId(), order.id());
                    if (sold != order.seatLabels().size()) {
                        throw new IllegalStateException(
                                "order " + order.id() + " sold " + sold + " of " + order.seatLabels().size() + " seats");
                    }
                }
                case RELEASE_SEATS -> store.release(order.holdId(), order.id());
                case REQUEST_REFUND ->
                    outbox.enqueue(
                            Topics.PAYMENT_COMMANDS,
                            new PaymentCommand.RefundPayment(UUID.randomUUID(), order.id(), now, input.toString()));
            }
        }
        if (!store.transition(order.id(), order.status(), transition.next(), now)) {
            throw new IllegalStateException("order " + order.id() + " changed status concurrently");
        }
        log.info("Order {} {} -> {} on {}, effects {}", order.id(), order.status(), transition.next(), input, transition.effects());
        return decision;
    }
}

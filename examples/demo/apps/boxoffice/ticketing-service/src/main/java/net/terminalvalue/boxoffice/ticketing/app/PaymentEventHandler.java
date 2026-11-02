package net.terminalvalue.boxoffice.ticketing.app;

import net.terminalvalue.boxoffice.contracts.PaymentEvent;
import net.terminalvalue.boxoffice.messaging.Inbox;
import net.terminalvalue.boxoffice.messaging.Transactions;
import net.terminalvalue.boxoffice.ticketing.domain.OrderInput;
import net.terminalvalue.boxoffice.ticketing.store.TicketingStore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

/** Applies payment outcomes to orders, exactly once per event. */
@Service
public class PaymentEventHandler {

    static final String CONSUMER = "ticketing";

    private static final Logger log = LoggerFactory.getLogger(PaymentEventHandler.class);

    private final TicketingStore store;
    private final Transactions transactions;
    private final Inbox inbox;
    private final OrderTransitions transitions;

    public PaymentEventHandler(TicketingStore store, Transactions transactions, Inbox inbox, OrderTransitions transitions) {
        this.store = store;
        this.transactions = transactions;
        this.inbox = inbox;
        this.transitions = transitions;
    }

    public void handle(PaymentEvent event) {
        transactions.run(() -> {
            if (!inbox.firstDelivery(CONSUMER, event)) {
                log.info("Skipping {} for order {}: already processed", event.getClass().getSimpleName(), event.orderId());
                return;
            }
            var order = store.order(event.orderId()).orElse(null);
            if (order == null) {
                // Payment is only requested after the order commits, so this indicates a bug or a foreign message.
                log.error("Ignoring {} for unknown order {}", event.getClass().getSimpleName(), event.orderId());
                return;
            }
            OrderInput input = switch (event) {
                case PaymentEvent.PaymentCaptured _ ->
                    new OrderInput.PaymentCaptured(store.heldBy(order.holdId()) == order.seatLabels().size());
                case PaymentEvent.PaymentDeclined _ -> new OrderInput.PaymentDeclined();
                case PaymentEvent.PaymentRefunded _ -> new OrderInput.PaymentRefunded();
            };
            transitions.apply(order, input);
        });
    }
}

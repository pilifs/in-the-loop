package net.terminalvalue.boxoffice.ticketing.domain;

import java.util.List;

/** What to do with an order in response to an {@link OrderInput}. */
public sealed interface Decision {

    /** Move to {@code next} and apply {@code effects}, in order, atomically with the move. */
    record Transition(OrderStatus next, List<Effect> effects) implements Decision {
        public Transition {
            effects = List.copyOf(effects);
        }
    }

    /**
     * Leave the order as it is. This is the answer to a redelivered message, which at-least-once delivery makes
     * routine.
     */
    record Unchanged(String reason) implements Decision {}

    /** Refuse a customer request that is invalid in the current status. */
    record Rejected(String reason) implements Decision {}
}

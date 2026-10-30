package net.terminalvalue.boxoffice.ticketing.domain;

import static net.terminalvalue.boxoffice.ticketing.domain.Effect.RELEASE_SEATS;
import static net.terminalvalue.boxoffice.ticketing.domain.Effect.REQUEST_REFUND;
import static net.terminalvalue.boxoffice.ticketing.domain.Effect.SELL_SEATS;
import static net.terminalvalue.boxoffice.ticketing.domain.OrderStatus.CONFIRMED;
import static net.terminalvalue.boxoffice.ticketing.domain.OrderStatus.DECLINED;
import static net.terminalvalue.boxoffice.ticketing.domain.OrderStatus.PENDING_PAYMENT;
import static net.terminalvalue.boxoffice.ticketing.domain.OrderStatus.REFUNDED;
import static net.terminalvalue.boxoffice.ticketing.domain.OrderStatus.REFUND_PENDING;

import java.util.List;
import net.terminalvalue.boxoffice.ticketing.domain.OrderInput.CancellationRequested;
import net.terminalvalue.boxoffice.ticketing.domain.OrderInput.PaymentCaptured;
import net.terminalvalue.boxoffice.ticketing.domain.OrderInput.PaymentDeclined;
import net.terminalvalue.boxoffice.ticketing.domain.OrderInput.PaymentRefunded;

/**
 * The order state machine: a total function from (status, input) to a decision.
 *
 * <p>Two properties are meant to hold for every input sequence, including duplicated and reordered payment events:
 *
 * <ul>
 *   <li><b>No money kept without seats:</b> every capture leads to CONFIRMED or to a refund request.
 *   <li><b>No seats without money:</b> seats are sold only on a capture, and released whenever the order stops being
 *       CONFIRMED.
 * </ul>
 */
public final class OrderLifecycle {

    private OrderLifecycle() {}

    public static Decision decide(OrderStatus current, OrderInput input) {
        return switch (input) {
            case PaymentCaptured captured -> switch (current) {
                case PENDING_PAYMENT ->
                    captured.seatsStillHeld()
                            ? transition(CONFIRMED, SELL_SEATS)
                            : transition(REFUND_PENDING, REQUEST_REFUND);
                // The payment service charges an order at most once, so this is not expected. If it happens anyway,
                // the money must go back.
                case DECLINED -> transition(REFUND_PENDING, REQUEST_REFUND);
                case CONFIRMED, REFUND_PENDING, REFUNDED -> unchanged("payment already recorded");
            };
            case PaymentDeclined _ -> switch (current) {
                case PENDING_PAYMENT -> transition(DECLINED, RELEASE_SEATS);
                case CONFIRMED, DECLINED, REFUND_PENDING, REFUNDED -> unchanged("payment outcome already recorded");
            };
            case PaymentRefunded _ -> switch (current) {
                case REFUND_PENDING -> transition(REFUNDED);
                case PENDING_PAYMENT, CONFIRMED, DECLINED, REFUNDED -> unchanged("no refund outstanding");
            };
            case CancellationRequested _ -> switch (current) {
                case CONFIRMED -> transition(REFUND_PENDING, RELEASE_SEATS, REQUEST_REFUND);
                case REFUND_PENDING, REFUNDED -> unchanged("already cancelled");
                case PENDING_PAYMENT -> new Decision.Rejected("payment is in progress; try again shortly");
                case DECLINED -> new Decision.Rejected("the order was never paid");
            };
        };
    }

    private static Decision transition(OrderStatus next, Effect... effects) {
        return new Decision.Transition(next, List.of(effects));
    }

    private static Decision unchanged(String reason) {
        return new Decision.Unchanged(reason);
    }
}

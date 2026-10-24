package net.terminalvalue.boxoffice.ticketing.domain;

import static net.terminalvalue.boxoffice.ticketing.domain.Effect.RELEASE_SEATS;
import static net.terminalvalue.boxoffice.ticketing.domain.Effect.REQUEST_REFUND;
import static net.terminalvalue.boxoffice.ticketing.domain.Effect.SELL_SEATS;
import static net.terminalvalue.boxoffice.ticketing.domain.OrderStatus.CONFIRMED;
import static net.terminalvalue.boxoffice.ticketing.domain.OrderStatus.DECLINED;
import static net.terminalvalue.boxoffice.ticketing.domain.OrderStatus.PENDING_PAYMENT;
import static net.terminalvalue.boxoffice.ticketing.domain.OrderStatus.REFUNDED;
import static net.terminalvalue.boxoffice.ticketing.domain.OrderStatus.REFUND_PENDING;
import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import net.terminalvalue.boxoffice.ticketing.domain.OrderInput.CancellationRequested;
import net.terminalvalue.boxoffice.ticketing.domain.OrderInput.PaymentCaptured;
import net.terminalvalue.boxoffice.ticketing.domain.OrderInput.PaymentDeclined;
import net.terminalvalue.boxoffice.ticketing.domain.OrderInput.PaymentRefunded;
import org.junit.jupiter.api.Test;

class OrderLifecycleTest {

    private static final List<OrderInput> INPUTS = List.of(
            new PaymentCaptured(true),
            new PaymentCaptured(false),
            new PaymentDeclined(),
            new PaymentRefunded(),
            new CancellationRequested());

    /** The only edges of the state machine. */
    private static final Map<OrderStatus, Set<OrderStatus>> EDGES = Map.of(
            PENDING_PAYMENT, Set.of(CONFIRMED, DECLINED, REFUND_PENDING),
            CONFIRMED, Set.of(REFUND_PENDING),
            DECLINED, Set.of(REFUND_PENDING),
            REFUND_PENDING, Set.of(REFUNDED),
            REFUNDED, Set.of());

    @Test
    void happyPath() {
        assertThat(OrderLifecycle.decide(PENDING_PAYMENT, new PaymentCaptured(true)))
                .isEqualTo(new Decision.Transition(CONFIRMED, List.of(SELL_SEATS)));
    }

    @Test
    void lateCaptureAfterTheHoldWasLostIsRefunded() {
        assertThat(OrderLifecycle.decide(PENDING_PAYMENT, new PaymentCaptured(false)))
                .isEqualTo(new Decision.Transition(REFUND_PENDING, List.of(REQUEST_REFUND)));
    }

    @Test
    void declineReleasesTheSeats() {
        assertThat(OrderLifecycle.decide(PENDING_PAYMENT, new PaymentDeclined()))
                .isEqualTo(new Decision.Transition(DECLINED, List.of(RELEASE_SEATS)));
    }

    @Test
    void cancellingAConfirmedOrderReleasesSeatsAndRefunds() {
        assertThat(OrderLifecycle.decide(CONFIRMED, new CancellationRequested()))
                .isEqualTo(new Decision.Transition(REFUND_PENDING, List.of(RELEASE_SEATS, REQUEST_REFUND)));
        assertThat(OrderLifecycle.decide(REFUND_PENDING, new PaymentRefunded()))
                .isEqualTo(new Decision.Transition(REFUNDED, List.of()));
    }

    @Test
    void cancellingWhilePaymentIsInFlightIsRejected() {
        assertThat(OrderLifecycle.decide(PENDING_PAYMENT, new CancellationRequested()))
                .isInstanceOf(Decision.Rejected.class);
    }

    @Test
    void everyTransitionFollowsAnEdge() {
        for (OrderStatus from : OrderStatus.values()) {
            for (OrderInput input : INPUTS) {
                if (OrderLifecycle.decide(from, input) instanceof Decision.Transition t) {
                    assertThat(EDGES.get(from)).as("%s on %s", from, input).contains(t.next());
                }
            }
        }
    }

    @Test
    void finalStatusesOnlyLeaveToReturnMoney() {
        for (OrderStatus from : OrderStatus.values()) {
            if (!from.isFinal()) {
                continue;
            }
            for (OrderInput input : INPUTS) {
                if (OrderLifecycle.decide(from, input) instanceof Decision.Transition t) {
                    assertThat(t.effects()).as("%s on %s", from, input).containsExactly(REQUEST_REFUND);
                }
            }
        }
    }

    @Test
    void duplicateDeliveryOfAnyEventChangesNothing() {
        for (OrderStatus from : OrderStatus.values()) {
            for (OrderInput input : INPUTS) {
                if (OrderLifecycle.decide(from, input) instanceof Decision.Transition first
                        && !(input instanceof CancellationRequested)) {
                    assertThat(OrderLifecycle.decide(first.next(), input))
                            .as("%s on %s twice", from, input)
                            .isInstanceOf(Decision.Unchanged.class);
                }
            }
        }
    }

    /**
     * Bounded model check of the two properties in {@link OrderLifecycle}'s documentation: every sequence of up to
     * six inputs, starting from PENDING_PAYMENT.
     */
    @Test
    void moneyAndSeatsStayConsistentForEveryInputSequence() {
        explore(new Model(PENDING_PAYMENT, false, false, false), 6, new ArrayList<>());
    }

    /** What a sequence of decisions has done so far. */
    private record Model(OrderStatus status, boolean captured, boolean refundRequested, boolean seatsSold) {}

    private static void explore(Model model, int depth, List<OrderInput> trace) {
        assertThat(!model.captured() || model.status() == CONFIRMED || model.refundRequested())
                .as("captured money is either kept for a confirmed order or refunded: %s", trace)
                .isTrue();
        assertThat(model.seatsSold() == (model.status() == CONFIRMED))
                .as("seats are sold exactly while the order is confirmed: %s", trace)
                .isTrue();
        if (depth == 0) {
            return;
        }
        for (OrderInput input : INPUTS) {
            // A capture can only be reported if payment was requested, which is once, at order creation, and the
            // refund only after the refund was requested.
            if (input instanceof PaymentCaptured && model.captured()) {
                continue;
            }
            if (input instanceof PaymentRefunded && !model.refundRequested()) {
                continue;
            }
            trace.add(input);
            explore(step(model, input), depth - 1, trace);
            trace.removeLast();
        }
    }

    private static Model step(Model model, OrderInput input) {
        boolean captured = model.captured() || input instanceof PaymentCaptured;
        if (!(OrderLifecycle.decide(model.status(), input) instanceof Decision.Transition t)) {
            return new Model(model.status(), captured, model.refundRequested(), model.seatsSold());
        }
        boolean sold = model.seatsSold();
        boolean refund = model.refundRequested();
        for (Effect effect : t.effects()) {
            switch (effect) {
                case SELL_SEATS -> sold = true;
                case RELEASE_SEATS -> sold = false;
                case REQUEST_REFUND -> refund = true;
            }
        }
        return new Model(t.next(), captured, refund, sold);
    }
}

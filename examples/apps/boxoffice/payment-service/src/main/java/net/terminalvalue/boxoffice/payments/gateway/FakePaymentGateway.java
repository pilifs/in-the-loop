package net.terminalvalue.boxoffice.payments.gateway;

import java.time.Duration;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * An in-memory gateway with test tokens that pick the outcome:
 *
 * <ul>
 *   <li>{@code tok_declined}: the charge is declined.
 *   <li>{@code tok_slow}: the charge succeeds after {@code boxoffice.gateway.slow-delay}, long enough for a hold to
 *       expire in the meantime.
 *   <li>anything else: the charge succeeds.
 * </ul>
 */
@Component
public class FakePaymentGateway implements PaymentGateway {

    public static final String DECLINED_TOKEN = "tok_declined";
    public static final String SLOW_TOKEN = "tok_slow";

    private final ConcurrentMap<String, ChargeResult> charges = new ConcurrentHashMap<>();
    private final ConcurrentMap<String, String> refunds = new ConcurrentHashMap<>();
    private final Duration slowDelay;

    public FakePaymentGateway(@Value("${boxoffice.gateway.slow-delay:5s}") Duration slowDelay) {
        this.slowDelay = slowDelay;
    }

    @Override
    public ChargeResult charge(String idempotencyKey, String paymentToken, long amountCents) {
        if (SLOW_TOKEN.equals(paymentToken) && !charges.containsKey(idempotencyKey)) {
            sleep(slowDelay);
        }
        return charges.computeIfAbsent(idempotencyKey, _ -> switch (paymentToken) {
            case DECLINED_TOKEN -> new ChargeResult.Declined("card declined");
            default -> new ChargeResult.Captured("ch_" + UUID.randomUUID());
        });
    }

    @Override
    public void refund(String idempotencyKey, String reference, long amountCents) {
        refunds.putIfAbsent(idempotencyKey, reference);
    }

    private static void sleep(Duration delay) {
        try {
            Thread.sleep(delay);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("interrupted", e);
        }
    }
}

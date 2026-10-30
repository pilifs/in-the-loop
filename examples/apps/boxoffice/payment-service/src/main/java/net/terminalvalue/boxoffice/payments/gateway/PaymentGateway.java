package net.terminalvalue.boxoffice.payments.gateway;

/**
 * An external card processor. Both calls take an idempotency key, as real processors do: a call repeated with the
 * same key returns the first call's result and moves no more money. That makes it safe for the payment service to
 * repeat a call after a crash or a transaction retry.
 */
public interface PaymentGateway {

    sealed interface ChargeResult {
        record Captured(String reference) implements ChargeResult {}

        record Declined(String reason) implements ChargeResult {}
    }

    ChargeResult charge(String idempotencyKey, String paymentToken, long amountCents);

    void refund(String idempotencyKey, String reference, long amountCents);
}

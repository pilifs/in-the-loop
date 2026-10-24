package net.terminalvalue.boxoffice.payments.app;

import java.time.Instant;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

/**
 * The payment for one order. The ID is the order ID, so the database itself guarantees at most one payment per order.
 *
 * @param gatewayReference the gateway's charge ID, set once CAPTURED
 */
@Document("payments")
public record PaymentDocument(
        @Id String orderId,
        String customerId,
        long amountCents,
        PaymentStatus status,
        String gatewayReference,
        String reason,
        Instant createdAt,
        Instant updatedAt) {}

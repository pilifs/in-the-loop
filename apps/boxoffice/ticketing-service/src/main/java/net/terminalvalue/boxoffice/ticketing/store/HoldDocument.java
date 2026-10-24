package net.terminalvalue.boxoffice.ticketing.store;

import java.time.Instant;
import java.util.List;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

/**
 * A customer's claim on some seats until {@code expiresAt}. The seats themselves record whether the claim still
 * stands; this document only remembers what was asked for and what it costs.
 *
 * @param idempotencyKey the client's {@code Idempotency-Key}, if it sent one
 */
@Document("holds")
public record HoldDocument(
        @Id String id,
        String concertId,
        List<String> seatLabels,
        String customerId,
        long amountCents,
        Instant createdAt,
        Instant expiresAt,
        String idempotencyKey) {}

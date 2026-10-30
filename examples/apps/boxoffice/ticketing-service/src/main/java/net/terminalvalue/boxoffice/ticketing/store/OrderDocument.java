package net.terminalvalue.boxoffice.ticketing.store;

import java.time.Instant;
import java.util.List;
import net.terminalvalue.boxoffice.ticketing.domain.OrderStatus;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

/** An order for the seats of one hold. There is at most one order per hold. */
@Document("orders")
public record OrderDocument(
        @Id String id,
        String holdId,
        String concertId,
        List<String> seatLabels,
        String customerId,
        long amountCents,
        OrderStatus status,
        Instant createdAt,
        Instant updatedAt) {}

package net.terminalvalue.boxoffice.ticketing.store;

import java.time.Instant;
import java.util.List;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

@Document("concerts")
public record ConcertDocument(
        @Id String id,
        String name,
        String venue,
        Instant startsAt,
        long priceCents,
        List<String> seatLabels,
        Instant createdAt) {}

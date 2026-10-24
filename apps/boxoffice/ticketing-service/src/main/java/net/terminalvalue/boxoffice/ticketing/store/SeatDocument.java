package net.terminalvalue.boxoffice.ticketing.store;

import java.time.Instant;
import net.terminalvalue.boxoffice.ticketing.domain.SeatStatus;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

/**
 * One seat of one concert. Seats are separate documents so that each one changes status with a single-document
 * conditional update, which MongoDB applies atomically.
 *
 * @param holdId set while HELD, and kept once SOLD to show which hold became the order
 * @param expiresAt set while HELD
 * @param orderId set while SOLD
 */
@Document("seats")
public record SeatDocument(
        @Id String id,
        String concertId,
        String label,
        SeatStatus status,
        String holdId,
        Instant expiresAt,
        String orderId) {

    public static String id(String concertId, String label) {
        return concertId + "/" + label;
    }
}

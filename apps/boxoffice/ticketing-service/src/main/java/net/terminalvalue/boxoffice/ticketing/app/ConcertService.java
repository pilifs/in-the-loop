package net.terminalvalue.boxoffice.ticketing.app;

import java.time.Clock;
import java.time.Instant;
import java.util.List;
import java.util.UUID;
import java.util.stream.IntStream;
import net.terminalvalue.boxoffice.messaging.Transactions;
import net.terminalvalue.boxoffice.ticketing.domain.SeatStatus;
import net.terminalvalue.boxoffice.ticketing.store.ConcertDocument;
import net.terminalvalue.boxoffice.ticketing.store.SeatDocument;
import net.terminalvalue.boxoffice.ticketing.store.TicketingStore;
import org.springframework.stereotype.Service;

@Service
public class ConcertService {

    /** A seat as a customer sees it: a held seat whose hold has expired shows as available. */
    public record SeatAvailability(String label, SeatStatus status) {}

    public record Availability(ConcertDocument concert, List<SeatAvailability> seats) {}

    private final TicketingStore store;
    private final Transactions transactions;
    private final Clock clock;

    public ConcertService(TicketingStore store, Transactions transactions, Clock clock) {
        this.store = store;
        this.transactions = transactions;
        this.clock = clock;
    }

    /** Creates a concert with seats {@code A1..A<n>, B1..B<n>, ...} for the given rows. */
    public ConcertDocument create(
            String name, String venue, Instant startsAt, long priceCents, List<String> rows, int seatsPerRow) {
        var labels = rows.stream()
                .flatMap(row -> IntStream.rangeClosed(1, seatsPerRow).mapToObj(n -> row + n))
                .toList();
        var concert = new ConcertDocument(
                UUID.randomUUID().toString(), name, venue, startsAt, priceCents, labels, clock.instant());
        transactions.run(() -> store.insert(concert));
        return concert;
    }

    public Availability availability(String concertId) {
        var concert = store.concert(concertId).orElseThrow(() -> new NotFoundException("no concert " + concertId));
        Instant now = clock.instant();
        var seats = store.seats(concertId).stream()
                .map(seat -> new SeatAvailability(seat.label(), effectiveStatus(seat, now)))
                .sorted((a, b) -> concert.seatLabels().indexOf(a.label()) - concert.seatLabels().indexOf(b.label()))
                .toList();
        return new Availability(concert, seats);
    }

    private static SeatStatus effectiveStatus(SeatDocument seat, Instant now) {
        return seat.status() == SeatStatus.HELD && SeatStatus.isHoldable(seat.status(), seat.expiresAt(), now)
                ? SeatStatus.AVAILABLE
                : seat.status();
    }
}
